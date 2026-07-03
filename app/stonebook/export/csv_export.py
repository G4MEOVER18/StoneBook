"""CSV-Export: alle Standardfelder in Feldwörterbuch-Reihenfolge (Excel-tauglich)."""
import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from stonebook.db.repository import ObjectRepo
from stonebook.fields import FIELDS, is_empty
from stonebook.migration.csv_loaders import (
    find_duplicate_ids,
    find_rows_with_invalid_funddatum,
    find_rows_with_invalid_numeric_fields,
    find_rows_without_id,
    load_standard,
)

COLUMNS = [f.name for f in FIELDS]  # beginnt mit ID
_IMPORT_EXTRA = {"status", "notizen"}


def export_csv(conn, path: Path, obj_ids: list[str] | None = None,
               status: str | None = None) -> int:
    """Schreibt alle Standardfelder + status/notizen als CSV.

    ``obj_ids`` schraenkt auf die genannten IDs ein; ``status`` (z.B. ``'aktiv'``)
    schraenkt auf einen Lebenszyklusstatus ein. Beide kombinierbar.
    """
    sql = "SELECT * FROM objects ORDER BY obj_id"
    rows = conn.execute(sql).fetchall()
    if obj_ids is not None:
        wanted = set(obj_ids)
        rows = [r for r in rows if r["obj_id"] in wanted]
    if status is not None:
        rows = [r for r in rows if r["status"] == status]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS + ["status", "notizen"])
        for r in rows:
            line = [r["obj_id"]]
            for col in COLUMNS[1:]:
                v = r[col]
                line.append("" if v is None else v)
            line += [r["status"], r["notizen"] or ""]
            w.writerow(line)
    return len(rows)


@dataclass
class ImportReport:
    angelegt: list[str] = field(default_factory=list)
    aktualisiert: list[str] = field(default_factory=list)
    uebersprungen: list[str] = field(default_factory=list)  # leere/unbekannte IDs
    konflikte: dict[str, list[str]] = field(default_factory=dict)  # obj_id → Feldnamen
    # obj_ids, die in der Quelle mehrfach als Zeile vorkamen. Aus load_standard
    # gewinnt die spaetere Zeile (dict-Ueberschreibung); ohne Report waere der
    # frueher-Zeilen-Verlust in nutzer-editierten CSVs unsichtbar. Deterministisch
    # in der Reihenfolge des zweiten Vorkommens (spiegelt find_duplicate_ids).
    duplikate: list[str] = field(default_factory=list)
    # 1-basierte Zeilennummern (ueber Datenzeilen, ohne Header und ohne
    # vollstaendig leere Zeilen), in denen die ID-Spalte leer oder unlesbar
    # war. load_standard verwirft solche Zeilen kommentarlos - symmetrisches
    # silent-data-loss-Pendant zu ``duplikate``.
    zeilen_ohne_id: list[int] = field(default_factory=list)
    # (Zeilennummer, Roh-Wert)-Paare fuer Zeilen mit einer Funddatum-Spalte,
    # deren Wert nicht als ISO-Datum geparst werden konnte (Tippfehler wie
    # ``32.13.2024``, unstrukturierter Freitext wie ``Sommer 84``). Die Zeile
    # selbst wird uebernommen, aber die Funddatum-Spalte fehlt danach im
    # Objekt-Dict - silent drop im Feld-Level, spiegelt die zeilen-Level-
    # Verluste in ``duplikate``/``zeilen_ohne_id``. Explizite "keine Angabe"-
    # Marker (``k.a.``, ``n/a`` etc., siehe validators.DATE_NO_DATA_MARKERS)
    # zaehlen nicht als "invalid" - der User hat explizit gesagt "kein Datum",
    # da ist nichts verloren gegangen. Reihenfolge = Reihenfolge im File.
    funddatum_invalid: list[tuple[int, str]] = field(default_factory=list)
    # (Zeilennummer, Spaltenname, Roh-Wert)-Tripel fuer alle numerischen
    # Standardfelder, in denen ``_num`` das Zellen-Token nicht parsen konnte.
    # ``_convert_standard`` uebergibt in diesem Fall ``(True, None)``, ``import_csv``
    # filtert das Feld ueber ``is_empty(None)`` aus dem Update-Dict - der
    # Roh-Text ist verloren, ohne dass der Report ihn sichtbar macht. Symmetrie-
    # Vervollstaendigung zu ``funddatum_invalid`` auf der numerischen Achse:
    # waehrend die Datum-Variante genau eine Spalte pflegt (Funddatum als
    # einziges date-Feld im Feldwoerterbuch), pflegt diese Variante alle
    # float/int/scale-Felder (Gewicht_g, Wert_CHF_*, Mohs_Haerte_*,
    # Confidence_Prozent, Seltenheit_*_1_10, ...) in einer einzigen Liste,
    # damit der Report mit einer festen Struktur auskommt. Reihenfolge = Zeile-
    # primaer, Spalte-sekundaer in Header-Reihenfolge.
    numeric_invalid: list[tuple[int, str, str]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "angelegt": list(self.angelegt),
            "aktualisiert": list(self.aktualisiert),
            "uebersprungen": list(self.uebersprungen),
            "konflikte": {k: list(v) for k, v in self.konflikte.items()},
            "duplikate": list(self.duplikate),
            "zeilen_ohne_id": list(self.zeilen_ohne_id),
            # Tupel als Liste serialisieren, damit JSON-Konsumenten die
            # (Zeile, Roh-Wert)-Paare als [Zeile, Roh-Wert]-Arrays sehen -
            # spiegelt die Konvention der uebrigen Listen-Felder und macht
            # den CLI --json-Weg deterministisch.
            "funddatum_invalid": [list(t) for t in self.funddatum_invalid],
            # (Zeile, Spalte, Roh-Wert)-Tripel analog zu funddatum_invalid,
            # ebenfalls als Array-of-Arrays serialisiert (JSON kennt keine
            # Tupel), damit CLI --json und externe Report-Konsumenten die
            # Silent-Drop-Daten deterministisch als List-Struktur sehen.
            "numeric_invalid": [list(t) for t in self.numeric_invalid],
        }


def import_csv(conn: sqlite3.Connection, path: Path, *,
               create_missing: bool = True, merge_only: bool = False) -> ImportReport:
    """Liest eine Standard-CSV (Format von :func:`export_csv`) zurück in die DB.

    Bestehende Objekte werden mit den nicht-leeren Spalten aktualisiert
    (Upsert). Mit ``create_missing=False`` werden unbekannte obj_ids
    übersprungen statt neu angelegt. Mit ``merge_only=True`` werden bei
    bestehenden Objekten nur leere Felder gefuellt; abweichende vorhandene
    Werte bleiben erhalten und landen in ``report.konflikte``. Toleriert
    Auto-Delimiter (siehe ``load_standard``).
    """
    data = load_standard(path)
    objects = ObjectRepo(conn)
    rep = ImportReport()
    rep.duplikate = find_duplicate_ids(path)
    rep.zeilen_ohne_id = find_rows_without_id(path)
    rep.funddatum_invalid = find_rows_with_invalid_funddatum(path)
    rep.numeric_invalid = find_rows_with_invalid_numeric_fields(path)
    for obj_id, fields_ in data.items():
        clean = {k: v for k, v in fields_.items() if not is_empty(v)}
        if objects.exists(obj_id):
            if merge_only:
                conflicts = objects.merge_nonempty(obj_id, clean)
                if conflicts:
                    rep.konflikte[obj_id] = conflicts
            else:
                objects.update_fields(obj_id, clean)
            rep.aktualisiert.append(obj_id)
        elif create_missing:
            objects.create(obj_id, **clean)
            rep.angelegt.append(obj_id)
        else:
            rep.uebersprungen.append(obj_id)
    if rep.angelegt or rep.aktualisiert:
        objects.refresh_status_all()
    return rep
