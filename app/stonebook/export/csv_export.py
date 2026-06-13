"""CSV-Export: alle Standardfelder in Feldwörterbuch-Reihenfolge (Excel-tauglich)."""
import csv
from pathlib import Path

from stonebook.fields import FIELDS

COLUMNS = [f.name for f in FIELDS]  # beginnt mit ID


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
