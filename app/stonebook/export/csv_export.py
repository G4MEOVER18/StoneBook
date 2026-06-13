"""CSV-Export: alle Standardfelder in Feldwörterbuch-Reihenfolge (Excel-tauglich)."""
import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from stonebook.db.repository import ObjectRepo
from stonebook.fields import FIELDS, is_empty
from stonebook.migration.csv_loaders import load_standard

COLUMNS = [f.name for f in FIELDS]  # beginnt mit ID
_IMPORT_EXTRA = {"status", "notizen"}


def export_csv(conn, path: Path, obj_ids: list[str] | None = None) -> int:
    sql = "SELECT * FROM objects ORDER BY obj_id"
    rows = conn.execute(sql).fetchall()
    if obj_ids is not None:
        wanted = set(obj_ids)
        rows = [r for r in rows if r["obj_id"] in wanted]
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

    def as_dict(self) -> dict:
        return {
            "angelegt": list(self.angelegt),
            "aktualisiert": list(self.aktualisiert),
            "uebersprungen": list(self.uebersprungen),
        }


def import_csv(conn: sqlite3.Connection, path: Path, *,
               create_missing: bool = True) -> ImportReport:
    """Liest eine Standard-CSV (Format von :func:`export_csv`) zurück in die DB.

    Bestehende Objekte werden mit den nicht-leeren Spalten aktualisiert
    (Upsert). Mit ``create_missing=False`` werden unbekannte obj_ids
    übersprungen statt neu angelegt. Toleriert Auto-Delimiter (siehe
    ``load_standard``).
    """
    data = load_standard(path)
    objects = ObjectRepo(conn)
    rep = ImportReport()
    for obj_id, fields_ in data.items():
        clean = {k: v for k, v in fields_.items() if not is_empty(v)}
        if objects.exists(obj_id):
            objects.update_fields(obj_id, clean)
            rep.aktualisiert.append(obj_id)
        elif create_missing:
            objects.create(obj_id, **clean)
            rep.angelegt.append(obj_id)
        else:
            rep.uebersprungen.append(obj_id)
    for obj_id in rep.angelegt + rep.aktualisiert:
        objects.refresh_status(obj_id)
    return rep
