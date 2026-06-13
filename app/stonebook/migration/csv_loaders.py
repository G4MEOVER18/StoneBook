"""Loader für die drei historischen CSV-Formate → Standard-Felddicts."""
import csv
import re
from pathlib import Path

from stonebook.fields import DATA_FIELDS, NUMERIC_TYPES, FIELD_BY_NAME
from stonebook.migration.id_utils import normalize_id
from stonebook.migration.validators import parse_iso_date

_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def parse_range(text) -> tuple[float | None, float | None]:
    """'6.5–7' → (6.5, 7.0); 'ca. 2.65' → (2.65, 2.65); '' → (None, None)."""
    if text is None:
        return None, None
    nums = [float(n.replace(",", ".")) for n in _NUM_RE.findall(str(text))]
    if not nums:
        return None, None
    return nums[0], nums[-1]


def _num(text) -> float | None:
    lo, _ = parse_range(text)
    return lo


def _int(text) -> int | None:
    v = _num(text)
    return int(v) if v is not None else None


def _join_notes(*parts) -> str:
    return "\n".join(p.strip() for p in parts if p and str(p).strip())


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


_COMMON_DELIMS = (",", ";", "\t", "|")


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
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        text = f.read()
    if not text.strip():
        return []
    # Erste nicht-leere Zeile als Header für die Delimiter-Erkennung
    header_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    delim = _detect_delimiter(header_line)
    reader = csv.DictReader(text.splitlines(), delimiter=delim)
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
    for row in _read_csv(path):
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
    for row in _read_csv(path):
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


def load_standard(path: Path) -> dict[str, dict]:
    """Liest eine CSV im aktuellen Export-Schema (ID + 43 Standardfelder + status + notizen).

    Gegenstück zu :func:`stonebook.export.csv_export.export_csv` und für externes
    Re-Import gedacht. Im Gegensatz zu load_v2 werden auch ``status`` und
    ``notizen`` übernommen, sofern in der Quelle vorhanden.
    """
    result = {}
    extra_cols = {"status", "notizen"}
    for row in _read_csv_robust(path):
        obj_id = normalize_id(row.get("ID"))
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
    for row in _read_csv(path):
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
