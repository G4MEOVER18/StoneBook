"""Loader für die drei historischen CSV-Formate → Standard-Felddicts."""
import csv
import io
import re
from pathlib import Path

from stonebook.fields import DATA_FIELDS, NUMERIC_TYPES, FIELD_BY_NAME
from stonebook.migration.id_utils import normalize_id
from stonebook.migration.validators import parse_iso_date

_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

# Eindeutig erkennbare Tausender-Strukturen (Komma+Punkt oder Punkt+Komma in einer Zahl,
# oder mehrere Trenner desselben Typs in Folge). ``(?<!\d)``/``(?!\d)`` stellen sicher,
# dass die Zahl als Ganzes erkannt wird (kein Anschnitt einer laengeren Ziffernfolge).
_EN_THOUSANDS_WITH_DECIMAL = re.compile(
    r"(?<!\d)(\d{1,3}(?:,\d{3})+\.\d+)(?!\d)"
)
_DE_THOUSANDS_WITH_DECIMAL = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d{3})+,\d+)(?!\d)"
)
_EN_THOUSANDS_PURE = re.compile(
    r"(?<!\d)(\d{1,3}(?:,\d{3}){2,})(?!\d)"
)
_DE_THOUSANDS_PURE = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d{3}){2,})(?!\d)"
)
# Whitespace als Tausender-Trenner (FR/Swiss-French/SI-Konvention). Im
# Gegensatz zum ASCII-Komma/Punkt werden die typografischen Whitespace-
# Varianten (NBSP U+00A0, schmales NBSP U+202F, THIN SPACE U+2009)
# genauso wie das ASCII-Leerzeichen unterstuetzt - franzoesische Excel-/
# LibreOffice-Exporte schreiben Tausender meist als NBSP (``1\xa0234,56``),
# Hand-Eingaben dagegen oft mit gewoehnlichem Leerzeichen
# (``1 234,56``), und das BIPM-SI-Brochure / NIST-konforme Typografie
# (wissenschaftliche Publikationen, LaTeX-Output mit ``\,``) verwendet
# THIN SPACE U+2009 als das eigentliche spec-empfohlene Tausender-
# Zeichen (NBSP ist Excel-Praxis, aber das SI-Brochure 8th edition,
# section 5.3.4 schreibt explizit "thin space"). Bisher fielen alle
# THIN-SPACE-Formen stille auf eine Mehrfach-Zahl-Zerlegung
# (``"1 000.50"`` lieferte ``(1.0, 1.0)`` statt ``(1000.5, 1000.5)``,
# weil die Whitespace-Klasse THIN SPACE nicht enthielt und das
# Re-Pattern statt einer Zahl ``1000.5`` zwei Token ``1`` und ``000.5``
# fand), was bei der Migration aus typografisch sauber gesetzten
# Mineralogie-Publikationen, LaTeX-/TeX-Exporten oder ISO-31-0-
# konformen Datensaetzen silenten Wert-Datenverlust erzeugte.
# Symmetrisch zu den EN/DE-Patterns: bei vorhandener Dezimal-Trennung
# reicht eine Gruppe, ohne Dezimal sind mindestens zwei Gruppen noetig -
# die einzelne Gruppe ``1 234`` bleibt ambivalent (koennte Range-
# Tippfehler "Wert 1 bis 234" oder Tausender sein) und wird wie bei
# den EN/DE-Patterns nicht angetastet.
_SP_THOUSAND_CHARS = r"[ \xa0  ]"
_SPACE_THOUSANDS_WITH_DECIMAL = re.compile(
    rf"(?<!\d)(\d{{1,3}}(?:{_SP_THOUSAND_CHARS}\d{{3}})+[.,]\d+)(?!\d)"
)
_SPACE_THOUSANDS_PURE = re.compile(
    rf"(?<!\d)(\d{{1,3}}(?:{_SP_THOUSAND_CHARS}\d{{3}}){{2,}})(?!\d)"
)
_SPACE_THOUSAND_CHAR_RE = re.compile(_SP_THOUSAND_CHARS)


def _strip_locale_thousands(s: str) -> str:
    """Entfernt eindeutig erkennbare Tausender-Trenner aus EN/DE/FR-Excel-Exporten.

    Beruehrt nur Zahl-Token, deren Struktur unmissverstaendlich ist:
    ``1,000.50``/``1.000,50`` (gemischte Trenner ⇒ rechter ist Dezimal),
    ``1,000,000``/``1.000.000`` (≥2 gleichartige Trennergruppen ⇒ Tausender)
    sowie die SI-/FR-Whitespace-Form ``1 234,56``/``1\xa0234.56``/
    ``1 234 567`` (Leerzeichen, NBSP, schmales NBSP). Mehrdeutige Faelle
    wie ``1,000`` / ``1.000`` / ``1 234`` (eine Trennergruppe) werden
    nicht angetastet, damit ``2,55`` weiterhin als Dezimal-2.55 gelesen wird.
    """
    s = _EN_THOUSANDS_WITH_DECIMAL.sub(lambda m: m.group(1).replace(",", ""), s)
    s = _DE_THOUSANDS_WITH_DECIMAL.sub(
        lambda m: m.group(1).replace(".", "").replace(",", "."), s)
    s = _EN_THOUSANDS_PURE.sub(lambda m: m.group(1).replace(",", ""), s)
    s = _DE_THOUSANDS_PURE.sub(lambda m: m.group(1).replace(".", ""), s)
    s = _SPACE_THOUSANDS_WITH_DECIMAL.sub(
        lambda m: _SPACE_THOUSAND_CHAR_RE.sub("", m.group(1)), s)
    s = _SPACE_THOUSANDS_PURE.sub(
        lambda m: _SPACE_THOUSAND_CHAR_RE.sub("", m.group(1)), s)
    return s


def normalize_numeric_locale(text: str) -> str:
    """Bereitet einen Freitext fuers Zahl-Token-Parsing vor.

    Spiegelt die Vorverarbeitung, die :func:`parse_range` intern macht, in
    eine eigene Funktion fuer andere Module mit lokaler Zahl-Extraktion
    (z.B. die KI-Antwort-Koerzitierung in :mod:`stonebook.ai.providers`).
    Strippt den Schweizer Apostroph-Tausender (``1'500.00`` → ``1500.00``)
    und die eindeutig erkennbaren EN/DE/FR-Tausender-Strukturen via
    :func:`_strip_locale_thousands`; mehrdeutige Einzel-Trenner
    (``1,000`` / ``1.000`` / ``1 234``) bleiben unangetastet, damit
    ``2,55`` weiterhin als Dezimal-2,55 lesbar bleibt.

    Der Caller entscheidet selbst, ob er das Ergebnis als Range parst
    (``parse_range``) oder per ``_LEADING_NUMBER.search`` nur die erste
    Zahl extrahiert (Providers): die Kommazahl-zu-Punktzahl-Umsetzung
    macht jeder fuer sich, weil sie auf den jeweiligen Match-String
    geht und nicht auf den ganzen Freitext (sonst wuerden Tausenderpunkte
    in DE-Notation unbeabsichtigt zu Dezimalpunkten).
    """
    s = text.replace("'", "").replace("’", "")
    return _strip_locale_thousands(s)


def parse_range(text) -> tuple[float | None, float | None]:
    """'6.5–7' → (6.5, 7.0); 'ca. 2.65' → (2.65, 2.65); '' → (None, None).

    Wenn die letzte gefundene Zahl kleiner als die erste ist (z.B.
    Unsicherheitsnotation ``'5.5(3)'`` oder Tippfehler ``'7-5'``), wird ein
    inverted Range vermieden: es zaehlt nur der erste Wert als (n, n).

    Schweizer Tausendertrenner ``'`` (z.B. ``1'500.00``) werden entfernt, damit
    Excel-/Buchhaltungsexporte mit CHF-Betraegen nicht in Einzelziffern zerfallen.
    Eindeutige EN/DE-Tausender (``1,000.50`` / ``1.000,50`` / ``1,000,000``) werden
    ebenfalls normalisiert; ambivalente Faelle wie ``2,55`` bleiben Dezimalwerte.
    """
    if text is None:
        return None, None
    s = normalize_numeric_locale(str(text))
    nums = [float(n.replace(",", ".")) for n in _NUM_RE.findall(s)]
    if not nums:
        return None, None
    lo, hi = nums[0], nums[-1]
    if hi < lo:
        return lo, lo
    return lo, hi


def _num(text) -> float | None:
    lo, _ = parse_range(text)
    return lo


def _int(text) -> int | None:
    v = _num(text)
    return int(v) if v is not None else None


def _join_notes(*parts) -> str:
    return "\n".join(p.strip() for p in parts if p and str(p).strip())


_COMMON_DELIMS = (",", ";", "\t", "|")
_ENCODING_FALLBACKS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
# UTF-16-Byte-Order-Marks: \xff\xfe = LE, \xfe\xff = BE. Excel speichert beim
# Export-Typ "Unicode Text (*.txt)" UTF-16-LE mit BOM und Tab-Separator; in
# einigen DE-/CH-Office-Installationen ist das der Default fuer "CSV mit
# Sonderzeichen". Ohne BOM-Erkennung fiele die Datei aktuell durch utf-8-sig/
# utf-8 (beide scheitern an \xff bzw. \xfe als ungueltigem Startbyte) auf
# cp1252 zurueck und wuerde dort als Doppel-Byte-Muell dekodiert (jeder ASCII-
# Buchstabe als ``X\x00``, dann auch der ID-Header zerfaellt). Die explizite
# BOM-Pruefung vor dem Fallback-Loop liefert sauberen Unicode-Text fuer beide
# UTF-16-Varianten; ohne BOM bleiben wir bei der bestehenden Heuristik (keine
# stille UTF-16-Annahme, weil reine ASCII-Daten als BOM-loses UTF-16-LE
# fast immer Unsinn waeren).
_UTF16_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe", "utf-16"),  # LE - Excel "Unicode Text" Default
    (b"\xfe\xff", "utf-16"),  # BE - selten, aber spec-konform
)


def _read_text_any_encoding(path: Path) -> str:
    """Liest Text mit UTF-8/BOM-bevorzugt; faellt auf cp1252/latin-1 zurueck.

    Excel-Exporte aus aelteren Windows-Versionen sind oft cp1252-kodiert.
    Latin-1 als letzter Schritt ist verlustfrei fuer Single-Byte-Streams.
    UTF-16-mit-BOM (Excel "Unicode Text"-Export) wird via BOM-Pruefung erkannt,
    damit ``\\xff\\xfe...``-Bytes nicht durch cp1252 als Doppelbyte-Muell
    dekodiert werden.
    """
    raw = path.read_bytes()
    for bom, enc in _UTF16_BOMS:
        if raw.startswith(bom):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                break
    for enc in _ENCODING_FALLBACKS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _detect_delimiter(header_line: str) -> str:
    """Wählt das Trennzeichen mit den meisten Treffern in der Headerzeile.

    Fällt auf Komma zurück, wenn keines der gängigen Zeichen vorkommt.
    """
    best, best_n = ",", 0
    for d in _COMMON_DELIMS:
        n = header_line.count(d)
        if n > best_n:
            best, best_n = d, n
    return best


def _read_csv_robust(path: Path) -> list[dict]:
    """Toleranter CSV-Reader für nutzer-editierte/externe Quellen.

    Erkennt Delimiter (``,`` / ``;`` / Tab / ``|``), strippt Whitespace aus den
    Spaltennamen und überspringt komplett leere Zeilen. Für die historischen
    Repo-CSVs nicht nötig; gedacht für ``load_standard``.

    Multi-Line-Zellen (eingebettete Newlines in quoted Felder wie ``notizen``)
    bleiben erhalten: der Reader bekommt einen ``StringIO``-Stream (nicht eine
    ``splitlines``-Liste), damit ``csv.DictReader`` seine eigene Zeilenlogik
    anwenden kann. Sonst wuerde ein langes Notiz-Feld mit ``\\n`` in nutzlose
    Halbzeilen zerfallen.
    """
    text = _read_text_any_encoding(path)
    if not text.strip():
        return []
    # Erste nicht-leere Zeile als Header fuer die Delimiter-Erkennung. Hier ist
    # splitlines unschaedlich, weil der Header nie quoted Newlines enthaelt.
    header_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    delim = _detect_delimiter(header_line)
    # StringIO statt splitlines(): erhaelt Multi-Line-Zellen wie "Zeile1\nZeile2"
    # in quoted Spalten. csv.DictReader nutzt seine eigene Newline-Erkennung,
    # die quoted Newlines beruecksichtigt.
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if reader.fieldnames:
        reader.fieldnames = [(h or "").strip() for h in reader.fieldnames]
    rows: list[dict] = []
    for row in reader:
        # Leere Zeilen / "alle Zellen leer" überspringen
        if not any((v or "").strip() for v in row.values() if v is not None):
            continue
        rows.append(row)
    return rows


def load_v1(path: Path) -> dict[str, dict]:
    """21 Spalten, Objekte 1-42."""
    result = {}
    for row in _read_csv_robust(path):
        obj_id = normalize_id(row.get("ID"))
        if not obj_id:
            continue
        h_min, h_max = parse_range(row.get("Härte"))
        d_min, d_max = parse_range(row.get("Dichte"))
        result[obj_id] = {
            "Name": row.get("Name", "").strip(),
            "Mineral_Primaer": row.get("Mineralart", "").strip(),
            "Fundort": row.get("Fundort", "").strip(),
            "UV_365nm": row.get("UV-Reaktion", "").strip(),
            "Mohs_Haerte_min": h_min, "Mohs_Haerte_max": h_max,
            "Dichte_min_gcm3": d_min, "Dichte_max_gcm3": d_max,
            "Transparenz": row.get("Transparenz", "").strip(),
            "Farbe_beobachtet": row.get("Farbe", "").strip(),
            "Wert_CHF_roh": _num(row.get("Wert_CHF_roh")),
            "Wert_CHF_poliert": _num(row.get("Wert_CHF_poliert")),
            "Wert_CHF_Schmuck": _num(row.get("Wert_CHF_Schmuck")),
            "Wert_USD_Talisman": _num(row.get("Wert_USD_Talisman")),
            "Marktwert_Industrie": _num(row.get("Marktwert")),
            "Wissenschaftlicher_Wert_CHF": _num(row.get("Wissenschaftlicher_Wert")),
            "Seltenheit_global_1_10": _int(row.get("Seltenheit_global")),
            "Seltenheit_Fundort_1_10": _int(row.get("Seltenheit_Fundort")),
            "Nachfrage_1_10": _int(row.get("Nachfrage")),
            "Beste_Verwendung": row.get("Beste_Verwendung", "").strip(),
            "notizen": _join_notes(row.get("Beschreibung"), row.get("Inhaltsstoffe")),
        }
    return result


_STANDARD_COLS = frozenset(f.name for f in DATA_FIELDS)


def _convert_standard(col: str, raw) -> tuple[bool, object]:
    """Konvertiert eine Rohzelle gemaess Feldwörterbuch-Typ.

    Gibt (übernehmen?, wert) zurück; übernehmen=False für ungueltige Datumsangaben.
    """
    fdef = FIELD_BY_NAME[col]
    if fdef.ftype in NUMERIC_TYPES:
        return True, _int(raw) if fdef.ftype in ("int", "scale") else _num(raw)
    if fdef.ftype == "date":
        iso = parse_iso_date(raw)
        return (iso is not None), iso
    return True, str(raw).strip()


def load_v2(path: Path) -> dict[str, dict]:
    """41 Spalten ≈ Feldwörterbuch-Standard, 1:1-Übernahme mit Typkonvertierung."""
    result = {}
    for row in _read_csv_robust(path):
        obj_id = normalize_id(row.get("ID"))
        if not obj_id:
            continue
        fields: dict = {}
        for col, raw in row.items():
            if col not in _STANDARD_COLS or raw is None:
                continue
            take, val = _convert_standard(col, raw)
            if take:
                fields[col] = val
        result[obj_id] = fields
    return result


_ID_COLUMNS = ("ID", "obj_id")


def find_duplicate_ids(path: Path) -> list[str]:
    """Findet obj_ids, die in derselben Standard-CSV mehrfach als Zeile vorkommen.

    :func:`load_standard` (und damit :func:`stonebook.export.csv_export.import_csv`)
    baut das Ergebnis als ``dict[str, dict]`` auf, sodass eine zweite Zeile mit
    derselben ID die erste kommentarlos ueberschreibt - typischer Datenverlust-
    Fall bei nutzer-editierten CSVs, wo dieselbe ID doppelt eingetragen wurde
    (z.B. beim Merge mehrerer Auszuege in Excel) und die spaetere Zeile alle
    Werte der frueheren Zeile verdraengt, obwohl beide Zeilen nur teilweise
    gefuellt sind. Diese Funktion pre-scannt die Datei und liefert die Liste
    der doppelten IDs zurueck, ohne die Loesch-Semantik selbst zu aendern.

    Normalisiert IDs ueber :func:`normalize_id` (spiegelt :func:`load_standard`),
    sodass ``obj_1`` und ``OBJ_0001`` als dieselbe ID erkannt werden. Leere/
    ungueltige IDs (die von :func:`load_standard` sowieso uebersprungen werden)
    zaehlen hier nicht als Duplikat. Reihenfolge der Rueckgabe = Reihenfolge
    der zweiten Vorkommen im File (deterministisch fuer Reporter/Log-Ausgabe).
    Rueckgabe enthaelt jede ID hoechstens einmal, unabhaengig davon, wie oft
    sie ueber die erste hinaus vorkommt.

    Akzeptiert dieselben ID-Spalten wie :func:`load_standard` (``ID`` oder
    ``obj_id``). Wirft ``ValueError`` (analog :func:`load_standard`), wenn
    die CSV Zeilen enthaelt, aber weder ``ID`` noch ``obj_id`` als Header.
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    seen: set[str] = set()
    duplikate: list[str] = []
    duplikat_set: set[str] = set()
    for row in rows:
        obj_id = normalize_id(row.get("ID") or row.get("obj_id"))
        if not obj_id:
            continue
        if obj_id in seen:
            if obj_id not in duplikat_set:
                duplikate.append(obj_id)
                duplikat_set.add(obj_id)
        else:
            seen.add(obj_id)
    return duplikate


def find_rows_without_id(path: Path) -> list[int]:
    """Findet Zeilennummern (1-basiert ueber die Datenzeilen), in denen die ID-Spalte
    leer ist oder :func:`normalize_id` sie nicht auf eine gueltige obj_id abbilden kann.

    :func:`load_standard` (und damit :func:`stonebook.export.csv_export.import_csv`)
    verwirft solche Zeilen kommentarlos - ein user-editierter Tippfehler in der
    ID-Zelle (leer, ``??`` oder ``TODO``) laesst die Zeile silent verschwinden,
    obwohl die uebrigen Spalten voll gepflegt sein koennen. Symmetrisches
    Blindfleck-Pendant zu :func:`find_duplicate_ids` (Doppel-Zeile-Silent-
    Ueberschreibung): beide melden zeilen-basierte silent data loss, ohne die
    Semantik von :func:`load_standard` selbst zu aendern.

    Reihenfolge = Reihenfolge im File. Vollstaendig leere Zeilen zaehlen nicht
    (die filtert bereits :func:`_read_csv_robust`); gemeldet werden nur Zeilen
    mit Inhalt, aber ohne verwertbare ID. Wirft ``ValueError`` analog zu
    :func:`find_duplicate_ids` / :func:`load_standard`, wenn die CSV Zeilen
    enthaelt, aber weder ``ID`` noch ``obj_id`` als Header hat.
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    ohne_id: list[int] = []
    for idx, row in enumerate(rows, start=1):
        obj_id = normalize_id(row.get("ID") or row.get("obj_id"))
        if not obj_id:
            ohne_id.append(idx)
    return ohne_id


def load_standard(path: Path) -> dict[str, dict]:
    """Liest eine CSV im aktuellen Export-Schema (ID + 43 Standardfelder + status + notizen).

    Gegenstück zu :func:`stonebook.export.csv_export.export_csv` und für externes
    Re-Import gedacht. Im Gegensatz zu load_v2 werden auch ``status`` und
    ``notizen`` übernommen, sofern in der Quelle vorhanden. Als ID-Spalte werden
    sowohl ``ID`` (CSV-Standard) als auch ``obj_id`` (DB-/JSON-Format)
    akzeptiert, damit JSON-Exporte ohne Spaltenumbenennung re-importierbar sind.

    Wirft ``ValueError`` wenn die CSV Zeilen enthaelt, aber weder eine Spalte
    ``ID`` noch ``obj_id`` -- so faellt eine falsch zugeordnete Datei (z.B.
    ``load_standard`` auf einer v1/v2-CSV mit Header ``Name,Mineralart,...``)
    nicht stillschweigend leer durch.
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    result = {}
    extra_cols = {"status", "notizen"}
    for row in rows:
        obj_id = normalize_id(row.get("ID") or row.get("obj_id"))
        if not obj_id:
            continue
        fields: dict = {}
        for col, raw in row.items():
            if raw is None:
                continue
            if col in _STANDARD_COLS:
                take, val = _convert_standard(col, raw)
                if take:
                    fields[col] = val
            elif col in extra_cols:
                fields[col] = str(raw).strip()
        result[obj_id] = fields
    return result


def load_obj043(path: Path) -> dict[str, dict]:
    """10-Spalten-Einzelobjektformat (voll verifiziert, höchste Priorität)."""
    result = {}
    for row in _read_csv_robust(path):
        obj_id = normalize_id(row.get("ID"))
        if not obj_id:
            continue
        h_min, h_max = parse_range(row.get("Härte"))
        d_min, d_max = parse_range(row.get("Dichte"))
        result[obj_id] = {
            "Fundort": row.get("Fundort", "").strip(),
            "Mineral_Primaer": row.get("Mineralart", "").strip(),
            "Farbe_beobachtet": row.get("Farbe", "").strip(),
            "Mohs_Haerte_min": h_min, "Mohs_Haerte_max": h_max,
            "Dichte_min_gcm3": d_min, "Dichte_max_gcm3": d_max,
            "UV_365nm": row.get("UV-Reaktion", "").strip(),
            "Gewicht_g": _num(row.get("Gewicht (g)")),
            "notizen": _join_notes(row.get("Struktur"), row.get("Besonderheiten")),
        }
    return result
