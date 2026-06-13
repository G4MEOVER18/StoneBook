"""JSON-Vollexport/-Import: objects + images + aliases (Backup/Re-Import)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

# Schreib-/Leseordnung respektiert die Foreign-Key-Beziehungen
TABLES: tuple[str, ...] = ("objects", "images", "aliases")


def export_json(conn: sqlite3.Connection, path: Path,
                obj_ids: Iterable[str] | None = None) -> dict[str, int]:
    """Schreibt objects/images/aliases als JSON.

    Mit ``obj_ids`` werden nur die genannten Objekte exportiert; ``images``
    werden auf diese IDs gefiltert, ``aliases`` nur, wenn ihr ``canonical_id``
    enthalten ist.
    """
    wanted: set[str] | None = None if obj_ids is None else set(obj_ids)

    def rows(table: str) -> list[dict]:
        all_rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
        if wanted is None:
            return all_rows
        if table == "objects":
            return [r for r in all_rows if r["obj_id"] in wanted]
        if table == "images":
            return [r for r in all_rows if r["obj_id"] in wanted]
        if table == "aliases":
            return [r for r in all_rows if r["canonical_id"] in wanted]
        return all_rows

    data = {table: rows(table) for table in TABLES}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {k: len(v) for k, v in data.items()}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def import_json(conn: sqlite3.Connection, path: Path, *, replace: bool = True) -> dict[str, int]:
    """Liest eine export_json-Datei zurück in die DB.

    Mit ``replace=True`` (Default) werden vorhandene Datensaetze über den
    Primärschlüssel ersetzt — geeignet für Backup-Restore. Mit
    ``replace=False`` werden Konflikte übersprungen (INSERT OR IGNORE).
    Unbekannte Spalten in der Quelle werden ignoriert.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    mode = "REPLACE" if replace else "IGNORE"
    counts: dict[str, int] = {}
    for table in TABLES:
        rows = data.get(table, [])
        if not rows:
            counts[table] = 0
            continue
        known = _table_columns(conn, table)
        cols = [c for c in rows[0].keys() if c in known]
        if not cols:
            counts[table] = 0
            continue
        placeholders = ", ".join("?" * len(cols))
        sql = f"INSERT OR {mode} INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        conn.executemany(sql, [[r.get(c) for c in cols] for r in rows])
        counts[table] = len(rows)
    conn.commit()
    return counts
