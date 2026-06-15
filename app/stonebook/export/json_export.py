"""JSON-Vollexport/-Import: objects + images + aliases (Backup/Re-Import)."""
from __future__ import annotations

import datetime
import gzip
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable

# Schreib-/Leseordnung respektiert die Foreign-Key-Beziehungen
# (ki_analysen haengt an objects.obj_id und kommt nach objects).
TABLES: tuple[str, ...] = ("objects", "images", "aliases", "ki_analysen")

# Versionierung des JSON-Backup-Formats. Erhoehen, sobald sich die
# Struktur (zusaetzliche Tabellen, geaenderte Spaltenbedeutung) aendert.
BACKUP_FORMAT_VERSION: int = 1
_META_KEY = "_meta"


def _is_gzip_path(path: Path) -> bool:
    return path.suffix.lower() == ".gz"


def _write_text(path: Path, text: str) -> None:
    if _is_gzip_path(path):
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def _read_text(path: Path) -> str:
    if _is_gzip_path(path):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return f.read()
    return Path(path).read_text(encoding="utf-8")


def _load_backup_dict(path: Path) -> dict:
    """Liest und parst eine Backup-Datei; garantiert ein dict am Top-Level.

    Wirft ``ValueError`` mit Pfad-Kontext, wenn die Datei kein JSON ist oder
    nicht das Backup-Format (Top-Level-Objekt) hat. So sieht der Aufrufer
    sofort, welche Datei das Problem ist statt eines abstrakten AttributeError.
    """
    p = Path(path)
    try:
        data = json.loads(_read_text(p))
    except json.JSONDecodeError as e:
        raise ValueError(f"Backup-Datei ist kein gueltiges JSON: {p} ({e.msg})") from e
    if not isinstance(data, dict):
        raise ValueError(
            f"Backup-Datei hat falsches Format (erwartet JSON-Objekt am Top-Level): {p}")
    return data


def export_json(conn: sqlite3.Connection, path: Path,
                obj_ids: Iterable[str] | None = None) -> dict[str, int]:
    """Schreibt objects/images/aliases als JSON.

    Mit ``obj_ids`` werden nur die genannten Objekte exportiert; ``images``
    werden auf diese IDs gefiltert, ``aliases`` nur, wenn ihr ``canonical_id``
    enthalten ist. Endet ``path`` auf ``.gz``, wird transparent gzip-komprimiert
    geschrieben (geeignet fuer grosse Backups).
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
        if table == "ki_analysen":
            return [r for r in all_rows if r["obj_id"] in wanted]
        if table == "aliases":
            return [r for r in all_rows if r["canonical_id"] in wanted]
        return all_rows

    data: dict = {table: rows(table) for table in TABLES}
    data[_META_KEY] = {
        "format_version": BACKUP_FORMAT_VERSION,
        "erstellt_am": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "selektion": sorted(wanted) if wanted is not None else None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=1))
    return {k: len(data[k]) for k in TABLES}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def read_backup_meta(path: Path) -> dict:
    """Liefert die ``_meta``-Sektion eines Backups (oder ``{}`` bei aelteren Formaten).

    Akzeptiert ``.json`` und gzipte ``.json.gz``-Backups. Wirft ``ValueError``
    bei beschaedigten oder format-fremden Dateien.
    """
    data = _load_backup_dict(path)
    meta = data.get(_META_KEY)
    return dict(meta) if isinstance(meta, dict) else {}


def inspect_backup(path: Path) -> dict:
    """Inspiziert ein Backup, ohne es zu restaurieren.

    Liefert ``{"counts": {...}, "meta": {...}}`` mit den Tabellen-Zeilenanzahlen
    und der Meta-Sektion (leer bei aelteren Backups). Geeignet fuer Backup-Browser
    / Wiederherstellungs-Dialog: zeigt dem User vorher, was drin ist. Akzeptiert
    ``.json`` und gzipte ``.json.gz``-Backups. Wirft ``ValueError`` bei
    beschaedigten Dateien.
    """
    data = _load_backup_dict(path)
    counts = {}
    for table in TABLES:
        rows = data.get(table, [])
        counts[table] = len(rows) if isinstance(rows, list) else 0
    meta = data.get(_META_KEY)
    return {
        "counts": counts,
        "meta": dict(meta) if isinstance(meta, dict) else {},
    }


BACKUP_PREFIX = "stonebook_backup_"
# Erkennt sowohl .json als auch .json.gz mit ISO-Datumstempel im Dateinamen
_BACKUP_RE = re.compile(
    rf"^{re.escape(BACKUP_PREFIX)}(\d{{8}}_\d{{6}})\.json(?:\.gz)?$"
)


def list_backups(backup_dir: Path) -> list[Path]:
    """Listet vorhandene Backup-Dateien aus :func:`write_rotated_backup` (sortiert, aelteste zuerst)."""
    if not backup_dir.is_dir():
        return []
    matches = [p for p in backup_dir.iterdir() if _BACKUP_RE.match(p.name)]
    matches.sort(key=lambda p: p.name)
    return matches


def prune_old_backups(backup_dir: Path, keep: int) -> list[Path]:
    """Loescht aelteste Backups im Verzeichnis bis nur noch ``keep`` uebrig sind.

    Beruehrt ausschliesslich Dateien, die zum :func:`write_rotated_backup`-Schema
    passen (``stonebook_backup_*.json[.gz]``); andere Dateien im Ordner bleiben
    unangetastet. Liefert die geloeschten Pfade zurueck.

    ``keep < 1`` wirft ``ValueError``. Nicht-loeschbare Dateien (Lock, Parallel-
    Loeschung) werden uebersprungen statt zu crashen.
    """
    if keep < 1:
        raise ValueError("keep muss >= 1 sein")
    existing = list_backups(backup_dir)
    deleted: list[Path] = []
    while len(existing) > keep:
        oldest = existing.pop(0)
        try:
            oldest.unlink()
            deleted.append(oldest)
        except OSError:
            pass
    return deleted


def write_rotated_backup(conn: sqlite3.Connection, backup_dir: Path, *,
                         keep: int = 10, compress: bool = True,
                         now: datetime.datetime | None = None) -> Path:
    """Schreibt ein Vollbackup mit Zeitstempel und entfernt alte Backups.

    Dateiname: ``stonebook_backup_YYYYMMDD_HHMMSS.json[.gz]``. Aeltere Dateien
    nach Stand des Aufrufs werden geloescht, sodass hoechstens ``keep``
    Backups uebrig bleiben. ``compress=True`` (Default) schreibt gzip-komprimiert.
    Greift in nichts anderes ein als Dateien, die zum Backup-Namensschema passen.
    """
    if keep < 1:
        raise ValueError("keep muss >= 1 sein")
    now = now or datetime.datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    suffix = ".json.gz" if compress else ".json"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{BACKUP_PREFIX}{stamp}{suffix}"
    export_json(conn, target)
    prune_old_backups(backup_dir, keep)
    return target


def import_json(conn: sqlite3.Connection, path: Path, *, replace: bool = True) -> dict[str, int]:
    """Liest eine export_json-Datei zurück in die DB.

    Mit ``replace=True`` (Default) werden vorhandene Datensaetze über den
    Primärschlüssel ersetzt — geeignet für Backup-Restore. Mit
    ``replace=False`` werden Konflikte übersprungen (INSERT OR IGNORE).
    Unbekannte Spalten in der Quelle werden ignoriert. Eine optionale
    ``_meta``-Sektion (Schema-Version, Erstellzeit) wird stillschweigend
    uebersprungen; ihre Inhalte koennen ueber :func:`read_backup_meta`
    separat ausgelesen werden.

    Atomisch: Schlaegt eine Tabelle fehl (z.B. dangling FK in aliases/images),
    wird die gesamte Transaktion zurueckgerollt, sodass keine Halb-Imports
    in der DB bleiben.
    """
    data = _load_backup_dict(path)
    mode = "REPLACE" if replace else "IGNORE"
    counts: dict[str, int] = {}
    try:
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
    except Exception:
        conn.rollback()
        raise
    return counts
