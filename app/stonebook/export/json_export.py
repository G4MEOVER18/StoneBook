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


def compare_backups(path_a: Path, path_b: Path) -> dict:
    """Vergleicht zwei Backups und liefert die strukturellen Diff-Stats.

    Geeignet als Sanity-Check vor einem Restore: ``compare_backups(alt, neu)``
    zeigt vorher, was sich gegenueber dem aktuellen Stand aendern wuerde -
    wieviele Objekte verschwinden, wieviele kommen dazu, wieviele werden
    veraendert. Vergleicht jeweils auf Zeilen-Ebene per Primaer-Key
    (``obj_id`` fuer objects/images/ki_analysen ueber id, ``alias_id`` fuer
    aliases) und auf Spalten-Ebene fuer objects-Eintraege, die in beiden
    Backups existieren.

    Liefert ein Dict pro Tabelle mit ``added`` (neu in b), ``removed`` (fehlt
    in b), ``modified`` (existiert in beiden mit unterschiedlichem Inhalt,
    nur fuer objects) und ``unchanged``. Zusaetzlich ``modified_obj_ids``
    fuer eine begrenzte Liste der veraenderten obj_ids (max 100, sortiert).

    Wirft ``ValueError`` bei kaputten/format-fremden Dateien.
    """
    data_a = _load_backup_dict(path_a)
    data_b = _load_backup_dict(path_b)

    def _ids(rows, key):
        return {r.get(key) for r in (rows or []) if isinstance(r, dict) and r.get(key)}

    def _by_id(rows, key):
        out = {}
        for r in rows or []:
            if isinstance(r, dict) and r.get(key):
                out[r[key]] = r
        return out

    result: dict[str, dict] = {}

    objs_a = _by_id(data_a.get("objects"), "obj_id")
    objs_b = _by_id(data_b.get("objects"), "obj_id")
    added = sorted(set(objs_b) - set(objs_a))
    removed = sorted(set(objs_a) - set(objs_b))
    common = set(objs_a) & set(objs_b)
    modified_ids = sorted(oid for oid in common if objs_a[oid] != objs_b[oid])
    result["objects"] = {
        "added": len(added),
        "removed": len(removed),
        "modified": len(modified_ids),
        "unchanged": len(common) - len(modified_ids),
        "modified_obj_ids": modified_ids[:100],
    }

    for table, key in (("images", "id"), ("aliases", "alias_id"),
                       ("ki_analysen", "id")):
        ids_a = _ids(data_a.get(table), key)
        ids_b = _ids(data_b.get(table), key)
        result[table] = {
            "added": len(ids_b - ids_a),
            "removed": len(ids_a - ids_b),
            "unchanged": len(ids_a & ids_b),
        }

    return result


def validate_backup(path: Path) -> dict:
    """Prueft die innere Konsistenz eines Backups, ohne es zu restaurieren.

    Liest objects/images/aliases/ki_analysen aus der Datei und sucht nach
    referenziellen Problemen, die beim eigentlichen ``import_json`` erst durch
    SQLite-Foreign-Keys auffallen wuerden - dann ist die Ziel-DB aber schon
    geleert. Geeignet als Pre-Flight-Check vor ``restore`` und als
    Sanity-Check fuer alte Backups, deren Ursprungs-DB nicht mehr existiert.

    Geprueft werden:
    - leere/fehlende ``obj_id`` in objects (Primaer-Key waere NULL)
    - doppelte ``obj_id`` in objects (zweite Zeile wuerde die erste
      ueberschreiben, faktischer Datenverlust)
    - leere/fehlende ``alias_id`` bzw. ``canonical_id`` in aliases
    - ``aliases.canonical_id`` ohne passenden Eintrag in objects (orphan)
    - ``images.obj_id`` ohne passenden Eintrag in objects (orphan)
    - ``ki_analysen.obj_id`` ohne passenden Eintrag in objects (orphan)
    - ``aliases.alias_id`` kollidiert mit einer ``obj_id`` aus objects
      (das gemerg-te Original wuerde sich selbst aliasieren)

    Liefert ``{"ok": bool, "errors": [str, ...], "counts": {...}}``;
    ``ok`` ist genau dann ``True``, wenn ``errors`` leer ist. Akzeptiert
    ``.json`` und ``.json.gz``. Wirft ``ValueError`` bei kaputten Dateien
    (Parse-/Format-Fehler aus :func:`_load_backup_dict`).
    """
    data = _load_backup_dict(path)
    counts = {}
    for table in TABLES:
        rows = data.get(table, [])
        counts[table] = len(rows) if isinstance(rows, list) else 0

    errors: list[str] = []

    objects = data.get("objects", []) or []
    obj_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for i, row in enumerate(objects):
        if not isinstance(row, dict):
            errors.append(f"objects[{i}]: kein JSON-Objekt")
            continue
        oid = row.get("obj_id")
        if not oid or not str(oid).strip():
            errors.append(f"objects[{i}]: obj_id leer oder fehlt")
            continue
        if oid in obj_ids:
            duplicate_ids.add(oid)
        else:
            obj_ids.add(oid)
    for dup in sorted(duplicate_ids):
        errors.append(f"objects: doppelte obj_id {dup!r}")

    aliases = data.get("aliases", []) or []
    for i, row in enumerate(aliases):
        if not isinstance(row, dict):
            errors.append(f"aliases[{i}]: kein JSON-Objekt")
            continue
        alias_id = row.get("alias_id")
        canonical = row.get("canonical_id")
        if not alias_id or not str(alias_id).strip():
            errors.append(f"aliases[{i}]: alias_id leer oder fehlt")
        if not canonical or not str(canonical).strip():
            errors.append(f"aliases[{i}]: canonical_id leer oder fehlt")
            continue
        if canonical not in obj_ids:
            errors.append(
                f"aliases[{i}]: canonical_id {canonical!r} ohne objects-Eintrag")
        if alias_id in obj_ids:
            errors.append(
                f"aliases[{i}]: alias_id {alias_id!r} kollidiert mit objects.obj_id")

    for table in ("images", "ki_analysen"):
        for i, row in enumerate(data.get(table, []) or []):
            if not isinstance(row, dict):
                errors.append(f"{table}[{i}]: kein JSON-Objekt")
                continue
            oid = row.get("obj_id")
            if not oid or not str(oid).strip():
                errors.append(f"{table}[{i}]: obj_id leer oder fehlt")
                continue
            if oid not in obj_ids:
                errors.append(
                    f"{table}[{i}]: obj_id {oid!r} ohne objects-Eintrag")

    return {"ok": not errors, "errors": errors, "counts": counts}


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


def _parse_backup_stamp(path: Path) -> datetime.datetime | None:
    """Liest den Zeitstempel ``YYYYMMDD_HHMMSS`` aus einem Backup-Dateinamen.

    Spiegelt das Namensschema von :func:`write_rotated_backup`. Liefert
    ``None``, wenn der Dateiname nicht zum Schema passt oder der Stempel
    semantisch ungueltig ist (z.B. Monat 13). Wird von
    :func:`prune_backups_by_age` als reine Filenamen-Auswertung verwendet,
    sodass weder ``mtime`` noch ``ctime`` der Datei (die durch Kopieren/
    Verschieben veraenderlich sind) das Pruning-Verhalten beeinflussen -
    der Wert im Dateinamen ist die Single-Source-of-Truth.
    """
    m = _BACKUP_RE.match(path.name)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def prune_backups_by_age(backup_dir: Path, max_age_days: int, *,
                         now: datetime.datetime | None = None) -> list[Path]:
    """Loescht Backups, deren Dateinamen-Zeitstempel aelter als ``max_age_days`` ist.

    Spiegelt :func:`prune_old_backups` auf die Zeit-Achse: waehrend die
    Count-Variante eine harte Obergrenze ueber die Anzahl behaelt (Default
    der Rotation, ``keep=10`` letzte Backups), behaelt die Age-Variante
    eine harte Obergrenze ueber das Alter (``max_age_days=30`` zuletzt
    aufgenommene Backups). Beide Strategien werden in Backup-Rotations-
    Cron-Jobs oft kombiniert: ``write -> prune_old_backups(keep=10) ->
    prune_backups_by_age(max_age_days=30)`` haelt sowohl die Datei-Anzahl
    als auch die Festplatten-Belegung in absoluten Grenzen, unabhaengig
    von der Frequenz der Backup-Erstellung. Bei reiner Count-Pflege wachsen
    Backups bei seltener Schreibe Quintessenz-monatelang an (10 Backups
    aus einem Jahr); bei reiner Age-Pflege haeufen sich bei taeglicher
    Schreibe ueber 30 Tage 30 Backups an. Erst die Kombination beider
    Achsen liefert die Volume-Garantie.

    Beruehrt ausschliesslich Dateien, die zum :func:`write_rotated_backup`-
    Schema passen (``stonebook_backup_*.json[.gz]``) - alle anderen
    Dateien im Ordner bleiben unangetastet (spiegelt
    :func:`prune_old_backups`). Der Vergleich basiert auf dem Dateinamen-
    Stempel (nicht ``mtime``/``ctime``), damit Backups, die vom Backup-
    Server / NAS kopiert oder verschoben wurden, ihr originales Alter
    behalten. ``now`` ist injizierbar fuer Tests/Replay.

    ``max_age_days < 0`` wirft ``ValueError`` (spiegelt
    :func:`prune_old_backups` mit ``keep < 1``). ``max_age_days == 0``
    loescht alle Backups, deren Stempel vor dem ``now``-Zeitpunkt liegt
    (geeignet als Cleanup-Befehl vor einem Voll-Reset). Nicht-loeschbare
    Dateien (Lock, Parallel-Loeschung) werden uebersprungen statt zu
    crashen (spiegelt :func:`prune_old_backups`). Liefert die geloeschten
    Pfade zurueck.
    """
    if max_age_days < 0:
        raise ValueError("max_age_days muss >= 0 sein")
    now = now or datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=max_age_days)
    deleted: list[Path] = []
    for p in list_backups(backup_dir):
        stamp = _parse_backup_stamp(p)
        if stamp is None or stamp >= cutoff:
            continue
        try:
            p.unlink()
            deleted.append(p)
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
