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


def _diff_backup_dicts(data_a: dict, data_b: dict) -> dict:
    """Reine Diff-Logik zwischen zwei Backup-Dicts (Datei oder DB-Spiegelung).

    Geteilte Implementation hinter :func:`compare_backups` (Datei vs. Datei)
    und :func:`compare_backup_to_db` (DB vs. Datei). Vergleicht jeweils auf
    Zeilen-Ebene per Primaer-Key (``obj_id`` fuer objects/images/ki_analysen
    ueber id, ``alias_id`` fuer aliases) und auf Spalten-Ebene fuer
    objects-Eintraege, die in beiden Quellen existieren.
    """
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

    def _row_eq(row_a: dict, row_b: dict) -> bool:
        # Normalisiert auf die Vereinigung der Schluessel: fehlende Schluessel
        # zaehlen als None. Spiegelt damit die restore-Semantik von
        # :func:`import_json`, das fehlende JSON-Spalten ueber das ``INSERT
        # OR REPLACE``-Statement implizit als NULL einfuegt. Ohne diese
        # Normalisierung wuerde ein direkt aus der DB gezogenes Backup
        # (alle 43 Objects-Spalten) systematisch != zu einem hand-geschriebenen
        # JSON mit Teil-Spalten sein, obwohl beide nach dem Restore zu
        # identischen DB-Zeilen fuehren.
        for k in set(row_a) | set(row_b):
            if row_a.get(k) != row_b.get(k):
                return False
        return True

    modified_ids = sorted(oid for oid in common if not _row_eq(objs_a[oid], objs_b[oid]))
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


def _diff_row_fields(row_a: dict, row_b: dict) -> dict[str, dict]:
    """Reine Feld-Diff-Logik zwischen zwei Zeilen (dict).

    Normalisiert auf die Vereinigung der Schluessel und markiert fehlende
    Schluessel als ``None``, spiegelt damit die _row_eq-Konvention in
    :func:`_diff_backup_dicts` (restore-Semantik von :func:`import_json`,
    das fehlende JSON-Spalten als NULL einfuegt). Liefert nur die Spalten,
    die sich tatsaechlich unterscheiden.
    """
    diffs: dict[str, dict] = {}
    for k in set(row_a) | set(row_b):
        va = row_a.get(k)
        vb = row_b.get(k)
        if va != vb:
            diffs[k] = {"a": va, "b": vb}
    return diffs


def _diff_object_fields(data_a: dict, data_b: dict, obj_id: str) -> dict:
    """Feld-Diff fuer ein einzelnes Objekt aus zwei Backup-Dicts.

    Ergaenzt :func:`_diff_backup_dicts`, das nur Aggregat-Counts und die Liste
    der modifizierten obj_ids liefert. Fuer die Restore-Entscheidung ist aber
    genau die Spalten-Ebene relevant: bei einem "modified: 3"-Report muss der
    User wissen, ob nur ein Name-Tippfehler oder ein Wert_CHF_roh-Update
    verantwortlich ist, bevor er ``restore --force`` bestaetigt.

    Liefert ``{"obj_id": ..., "status": ..., "fields": {col: {"a":.., "b":..}}}``
    mit ``status`` in ``{"unchanged", "modified", "added", "removed", "missing"}``:
    - ``unchanged``: obj_id in beiden Quellen, alle Spalten identisch (nach
      Normalisierung ueber die Vereinigung der Schluessel)
    - ``modified``: obj_id in beiden Quellen, mindestens eine Spalte unterschiedlich
    - ``added``: obj_id nur in b (kaeme nach restore neu in die Ziel-DB dazu)
    - ``removed``: obj_id nur in a (ginge nach restore verloren)
    - ``missing``: obj_id in keiner Quelle vorhanden (Aufrufer-Tippfehler o.ae.)
    """
    def _find(rows, oid):
        for r in rows or []:
            if isinstance(r, dict) and r.get("obj_id") == oid:
                return r
        return None

    row_a = _find(data_a.get("objects"), obj_id)
    row_b = _find(data_b.get("objects"), obj_id)
    if row_a is None and row_b is None:
        return {"obj_id": obj_id, "status": "missing", "fields": {}}
    if row_a is None:
        return {"obj_id": obj_id, "status": "added", "fields": {}}
    if row_b is None:
        return {"obj_id": obj_id, "status": "removed", "fields": {}}
    fields = _diff_row_fields(row_a, row_b)
    return {
        "obj_id": obj_id,
        "status": "modified" if fields else "unchanged",
        "fields": fields,
    }


def diff_backup_object_fields(path_a: Path, path_b: Path, obj_id: str) -> dict:
    """Feld-Diff fuer ein einzelnes Objekt zwischen zwei Backups.

    Ergaenzt :func:`compare_backups` um die Spalten-Sicht: waehrend
    ``compare_backups`` nur die Aggregat-Counts (``added``/``removed``/
    ``modified``/``unchanged``) und maximal 100 modifizierte obj_ids liefert,
    beantwortet ``diff_backup_object_fields`` die naheliegende Folge-Frage
    "welche Spalten haben sich in Objekt X geaendert?". Typischer Workflow:
    ``compare_backups(alt, neu)`` liefert die Liste veraenderter obj_ids,
    dann iteriert der Aufrufer ueber diese Liste mit
    ``diff_backup_object_fields(alt, neu, oid)`` und bekommt pro Objekt die
    veraenderten Spalten mit ``a``-/``b``-Wert - genug Kontext, um vor
    ``restore --force`` bewusst zu entscheiden.

    Wirft ``ValueError`` bei kaputten/format-fremden Backup-Dateien (spiegelt
    :func:`compare_backups`).
    """
    data_a = _load_backup_dict(path_a)
    data_b = _load_backup_dict(path_b)
    return _diff_object_fields(data_a, data_b, obj_id)


def diff_backup_to_db_object_fields(conn: sqlite3.Connection, path: Path,
                                    obj_id: str) -> dict:
    """Feld-Diff fuer ein einzelnes Objekt zwischen DB und Backup.

    Spiegelt :func:`diff_backup_object_fields` (Datei vs. Datei) auf die
    Datei-vs-DB-Achse, exakt wie :func:`compare_backup_to_db` die Achse zu
    :func:`compare_backups` spiegelt. DB nimmt die Rolle von ``a``, Backup
    die Rolle von ``b`` ein (Restore-Semantik: was wuerde sich in der
    laufenden DB aendern, wenn dieses Backup eingespielt wird). Typischer
    Workflow: ``compare_backup_to_db(conn, path)`` liefert die Liste der
    obj_ids, die sich unterscheiden, dann liefert
    ``diff_backup_to_db_object_fields(conn, path, oid)`` fuer jede ID die
    veraenderten Spalten mit ``a`` = DB-Stand, ``b`` = Backup-Stand.

    Wirft ``ValueError`` bei kaputten/format-fremden Backup-Dateien (spiegelt
    :func:`compare_backup_to_db`).
    """
    data_db = _db_to_backup_dict(conn)
    data_backup = _load_backup_dict(path)
    return _diff_object_fields(data_db, data_backup, obj_id)


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
    return _diff_backup_dicts(data_a, data_b)


def _db_to_backup_dict(conn: sqlite3.Connection) -> dict:
    """Spiegelt den DB-Zustand als Backup-Dict (objects/images/aliases/ki_analysen).

    Verwendet das gleiche Spalten-Layout wie :func:`export_json` (alle Spalten
    aus ``SELECT *``), sodass das Resultat strukturgleich mit einer Backup-
    Datei ist und sich direkt mit einem geladenen Backup-Dict vergleichen
    laesst. Geteilte Implementation hinter :func:`compare_backup_to_db`.
    """
    return {
        table: [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
        for table in TABLES
    }


def compare_backup_to_db(conn: sqlite3.Connection, path: Path) -> dict:
    """Vergleicht ein Backup gegen den aktuellen DB-Stand.

    Spiegelt :func:`compare_backups` (Datei vs. Datei) auf die Datei-vs-DB-
    Achse: waehrend ``compare_backups`` zwei archivierte Backups gegeneinander
    stellt, beantwortet ``compare_backup_to_db`` die naheliegende Restore-
    Vorfeld-Frage "was wuerde sich gegenueber dem aktuellen DB-Stand
    veraendern, wenn ich dieses Backup einspiele?". Das Ergebnis ist
    struktur-identisch zu :func:`compare_backups` (gleiche Schluessel pro
    Tabelle), damit Cron-Reporter und Restore-Dialoge denselben Auswerter
    benutzen koennen.

    DB nimmt die Rolle von ``a``, Backup die Rolle von ``b`` ein - in der
    Restore-Semantik des CLI ``restore``-Pfads (DB wird vor dem Import
    geloescht und aus dem Backup neu aufgebaut) heisst das: ``added`` =
    Eintraege, die nach dem Restore neu da waeren; ``removed`` = Eintraege,
    die nach dem Restore verloren gingen; ``modified`` = Objekte, die im
    Backup mit anderem Inhalt liegen als in der DB; ``unchanged`` =
    Identitaet auf beiden Seiten. Eignet sich damit als Pre-Flight-Check vor
    ``restore --force``: der User sieht vorher, wieviele DB-Aenderungen seit
    dem Backup verloren gingen.

    Wirft ``ValueError`` bei kaputten/format-fremden Backup-Dateien (gleich
    wie :func:`compare_backups`).
    """
    data_db = _db_to_backup_dict(conn)
    data_backup = _load_backup_dict(path)
    return _diff_backup_dicts(data_db, data_backup)


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


def latest_backup(backup_dir: Path) -> Path | None:
    """Liefert das neueste Backup aus dem Ordner (Filename-Stempel), oder ``None``.

    Spiegelt :func:`list_backups` auf den Ein-Datei-Fall: waehrend
    ``list_backups`` alle Backup-Pfade als aufsteigend sortierte Liste
    liefert, beantwortet ``latest_backup`` die naheliegende Cron-/Restore-
    Frage "was ist das juengste Backup?" in einem Schritt, ohne dass der
    Caller ``[-1]`` oder ``max()`` neu formulieren muss. Geeignet als
    Ziel-Anker fuer ``restore-latest`` (statt einer expliziten Datei),
    als Anker-Kennzahl fuer Cron-Reporter ("letztes Backup ist X Stunden
    alt", vgl. ``_parse_backup_stamp``) und als Standard-Auswahl im
    Restore-Dialog eines UI (vorgefuellt mit dem juengsten Eintrag).

    Beruehrt ausschliesslich Dateien, die zum :func:`write_rotated_backup`-
    Schema passen (``stonebook_backup_YYYYMMDD_HHMMSS.json[.gz]``) - fremde
    Dateien im Ordner (README, andere Exporte, Lock-Files) bleiben
    unbetrachtet, spiegelt exakt das Filtern von :func:`list_backups` und
    der prune-Funktionen ueber ``_BACKUP_RE``. Die Sortierung basiert auf
    dem Dateinamen-Stempel (nicht ``mtime``/``ctime``), damit Backups,
    die vom Backup-Server / NAS kopiert oder verschoben wurden, ihr
    originales Alter behalten - Single-Source-of-Truth = Filename-Stempel,
    spiegelt :func:`prune_backups_by_age`.

    Leerer Ordner / nur fremde Dateien / nicht existierender Ordner
    liefern ``None`` (spiegelt das ``list_backups``-Verhalten bei
    fehlendem Ordner: leere Liste statt Crash), sodass ``latest_backup``
    ohne Sonderbehandlung vor der ersten Backup-Schreibe aufrufbar
    bleibt und der Caller mit einem einfachen ``if latest is None``-Guard
    "noch kein Backup vorhanden" abfangen kann.
    """
    backups = list_backups(backup_dir)
    return backups[-1] if backups else None


def oldest_backup(backup_dir: Path) -> Path | None:
    """Liefert das aelteste Backup aus dem Ordner (Filename-Stempel), oder ``None``.

    Spiegelt :func:`latest_backup` auf den Gegen-Endpunkt der Backup-Halde:
    waehrend ``latest_backup`` das juengste Backup liefert (typisch fuer
    Restore-Dialoge und "letztes Backup ist X Stunden alt"-Reporter),
    beantwortet ``oldest_backup`` die naheliegende komplementaere
    Wartungs-Frage "wie weit reicht meine Halde zurueck?" in einem Schritt
    (statt ueber ``list_backups[0]``). Geeignet als Anker fuer
    Prune-Preview ("was ist das aelteste Backup, das prune-age
    --max-age-days 30 loeschen wuerde?", vgl. :func:`prune_backups_by_age`),
    als Sanity-Check nach Rotations-Jobs ("ist mein aeltestes Backup
    juenger als das erwartete Cutoff?") und als Startpunkt fuer historische
    Diff-Analysen (``compare_backups(oldest_backup(dir), latest_backup(dir))``
    zeigt, wie sich die Sammlung ueber die ganze Halden-Zeitspanne
    entwickelt hat).

    Beruehrt ausschliesslich Dateien, die zum :func:`write_rotated_backup`-
    Schema passen - fremde Dateien im Ordner bleiben unbetrachtet, spiegelt
    exakt das Filtern von :func:`latest_backup` / :func:`list_backups`
    ueber ``_BACKUP_RE``. Die Sortierung basiert auf dem Dateinamen-Stempel
    (nicht ``mtime``/``ctime``), damit Backups, die vom Backup-Server /
    NAS kopiert oder verschoben wurden, ihr originales Alter behalten -
    Single-Source-of-Truth = Filename-Stempel, spiegelt
    :func:`prune_backups_by_age` / :func:`latest_backup`. Ordner mit
    genau einer Backup-Datei liefern dieselbe Datei fuer oldest und
    latest (spiegelt :func:`backup_directory_stats` mit
    ``oldest_stamp == newest_stamp``).

    Leerer Ordner / nur fremde Dateien / nicht existierender Ordner
    liefern ``None`` (spiegelt das ``latest_backup``/``list_backups``-
    Verhalten bei fehlendem Ordner: keine Datei statt Crash), sodass
    ``oldest_backup`` ohne Sonderbehandlung vor der ersten Backup-Schreibe
    aufrufbar bleibt und der Caller mit einem einfachen ``if oldest is
    None``-Guard "noch kein Backup vorhanden" abfangen kann.
    """
    backups = list_backups(backup_dir)
    return backups[0] if backups else None


def _backup_size(path: Path) -> int | None:
    """Liest die Dateigroesse eines Backups oder ``None`` bei OS-Fehler.

    Kapselt den ``st_size``-Zugriff genau wie :func:`backup_directory_stats`
    es intern macht: Race gegen paralleles Loeschen (Cron-Prune vs. Report)
    darf den Aufrufer nicht crashen, sondern soll die Datei stille
    ueberspringen. Wird von :func:`largest_backup` / :func:`smallest_backup`
    geteilt, damit beide Extrema-Reporter dasselbe Fehler-Verhalten haben
    wie der Aggregat-Reporter.
    """
    try:
        return path.stat().st_size
    except OSError:
        return None


def largest_backup(backup_dir: Path) -> Path | None:
    """Liefert das groesste Backup aus dem Ordner (Bytes auf Platte), oder ``None``.

    Spiegelt :func:`latest_backup` / :func:`oldest_backup` (Zeit-Achse
    ueber den Filename-Stempel) auf die Volume-Achse (Bytes auf Platte).
    Waehrend ``latest_backup`` das juengste Backup als Restore-Anker
    liefert, beantwortet ``largest_backup`` die naheliegende Wartungs-
    Frage "welches Backup belegt am meisten Platz?" in einem Schritt,
    ohne dass der Caller ``max(list_backups(dir), key=st_size)`` neu
    formulieren muss. Geeignet als Anker fuer Anomalie-Detektion
    ("ist das juengste Backup groesser als sonst? -> mehr Objekte,
    oder Wachstum durch neue Bilder-Metadaten?"), als Startpunkt fuer
    Kompressions-Vergleiche (``.json`` vs. ``.json.gz`` desselben
    Zeitraums) und als Auswahl im Speicher-Report ("welche Datei
    beim naechsten Prune zuerst freigeben?").

    Beruehrt ausschliesslich Dateien, die zum :func:`write_rotated_backup`-
    Schema passen - fremde Dateien im Ordner bleiben unbetrachtet,
    spiegelt exakt das Filtern von :func:`latest_backup` /
    :func:`oldest_backup` / :func:`list_backups` ueber ``_BACKUP_RE``.
    Die Sortierung basiert auf ``st_size`` (nicht auf dem Filename-
    Stempel wie bei den Zeit-Extrema), damit umbenannte oder verschobene
    Backups mit korrektem Byte-Count erfasst werden. Bei gleichem
    ``st_size`` gewinnt der lexikographisch groessere Filename (das
    juengere Backup) - deterministisches Verhalten fuer Test-Fixtures
    und Cron-Reporter, spiegelt die Zweitsortierung-Konvention der
    Zeit-Extrema (deterministische Wahl bei Gleichstand).

    Dateien, deren ``st_size``-Aufruf mit OSError faellt (Race gegen
    paralleles Loeschen, Lock, defekter Mount), werden uebersprungen
    statt zu crashen (spiegelt :func:`backup_directory_stats` /
    :func:`prune_old_backups`). Leerer Ordner / nur fremde Dateien /
    nicht existierender Ordner / alle Dateien unlesbar liefern
    ``None`` (spiegelt das ``latest_backup``/``oldest_backup``-
    Verhalten bei fehlendem Ordner: keine Datei statt Crash), sodass
    ``largest_backup`` ohne Sonderbehandlung vor der ersten Backup-
    Schreibe aufrufbar bleibt und der Caller mit einem einfachen
    ``if largest is None``-Guard "noch kein Backup vorhanden"
    abfangen kann.
    """
    sized = [(p, _backup_size(p)) for p in list_backups(backup_dir)]
    sized = [(p, size) for p, size in sized if size is not None]
    if not sized:
        return None
    return max(sized, key=lambda ps: (ps[1], ps[0].name))[0]


def smallest_backup(backup_dir: Path) -> Path | None:
    """Liefert das kleinste Backup aus dem Ordner (Bytes auf Platte), oder ``None``.

    Spiegelt :func:`largest_backup` auf den Gegen-Endpunkt der Volume-
    Achse, exakt wie :func:`oldest_backup` das Gegenstueck zu
    :func:`latest_backup` auf der Zeit-Achse bildet. Waehrend
    ``largest_backup`` das groesste Backup als Anomalie-Kandidat
    ("plotzlich viel Wachstum?") liefert, beantwortet
    ``smallest_backup`` die Kehrfrage "welches Backup ist am
    schlanksten - potentiell abgebrochene Schreibe, fehlerhaft
    komprimiert, oder aus einer sehr fruehen Phase mit kleinerer
    Sammlung?" in einem Schritt. Geeignet als Verdachts-Anker fuer
    Backup-Integritaets-Checks (auffaellig kleine Dateien via
    :func:`validate_backup` gegenchecken), als Referenz fuer die
    Baseline-Grosse einer frisch-migrierten DB und als Ergaenzung zu
    :func:`largest_backup` bei Speicher-Reports (der Range
    ``largest - smallest`` beziffert die Varianz der Backup-Groessen
    ueber die Halden-Zeitspanne).

    Beruehrt ausschliesslich Dateien, die zum :func:`write_rotated_backup`-
    Schema passen - fremde Dateien im Ordner bleiben unbetrachtet
    (spiegelt :func:`largest_backup`). Die Sortierung basiert auf
    ``st_size`` (nicht auf dem Filename-Stempel), damit umbenannte
    oder verschobene Backups mit korrektem Byte-Count erfasst werden.
    Bei gleichem ``st_size`` gewinnt der lexikographisch kleinere
    Filename (das aeltere Backup) - deterministisches Verhalten fuer
    Test-Fixtures und Cron-Reporter, spiegelt die Zweitsortierung-
    Konvention der Zeit-Extrema (deterministische Wahl bei Gleichstand,
    hier gewinnt das aeltere Backup als Konsistenz zu
    :func:`oldest_backup`).

    Dateien, deren ``st_size``-Aufruf mit OSError faellt, werden
    uebersprungen statt zu crashen (spiegelt :func:`largest_backup`).
    Leerer Ordner / nur fremde Dateien / nicht existierender Ordner /
    alle Dateien unlesbar liefern ``None`` (spiegelt
    :func:`largest_backup` / :func:`latest_backup` / :func:`oldest_backup`),
    sodass ``smallest_backup`` ohne Sonderbehandlung vor der ersten
    Backup-Schreibe aufrufbar bleibt.
    """
    sized = [(p, _backup_size(p)) for p in list_backups(backup_dir)]
    sized = [(p, size) for p, size in sized if size is not None]
    if not sized:
        return None
    return min(sized, key=lambda ps: (ps[1], ps[0].name))[0]


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


def find_stale_backups(backup_dir: Path, max_age_days: int, *,
                       now: datetime.datetime | None = None) -> list[Path]:
    """Listet Backups, deren Dateinamen-Zeitstempel aelter als ``max_age_days`` ist.

    Reine Lese-/Check-Variante von :func:`prune_backups_by_age` - berechnet
    exakt dieselbe Kandidatenmenge (gleiche Cutoff-Semantik, gleiches
    Namensschema-Filter, gleicher ``now``-Parameter), loescht aber nichts.
    Bildet damit das check-Ende des check/fix-Paares, wie
    :func:`stonebook.db.integrity.find_orphan_images` /
    ``delete_orphan_images`` es fuer die FK-Achse tut.

    Nutzen: Cron-Reporter kann die stale-Liste erst loggen, dann prune
    entscheiden lassen (oder gar nicht); ein Bestaetigungs-Dialog kann dem
    User zeigen, welche konkreten Dateien beim naechsten ``prune-age``
    verloren gingen, bevor er OK klickt; ein Monitoring-Job kann Exit 1
    liefern, sobald Backups > N Tage alt herumliegen, ohne selbst pruning-
    Rechte zu brauchen.

    Reihenfolge = ``list_backups``-Reihenfolge (aeltester Dateiname zuerst),
    damit die Ausgabe deterministisch bleibt und ein CLI-Reporter direkt
    "aeltestes zuerst" listen kann. Ignoriert nicht-parsbare Zeitstempel
    (spiegelt :func:`prune_backups_by_age`).

    ``max_age_days < 0`` wirft ``ValueError`` (spiegelt
    :func:`prune_backups_by_age`). Fehlender Ordner -> ``[]`` (spiegelt
    :func:`list_backups`).
    """
    if max_age_days < 0:
        raise ValueError("max_age_days muss >= 0 sein")
    now = now or datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=max_age_days)
    stale: list[Path] = []
    for p in list_backups(backup_dir):
        stamp = _parse_backup_stamp(p)
        if stamp is None or stamp >= cutoff:
            continue
        stale.append(p)
    return stale


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

    Die Kandidatenauswahl teilt sich mit :func:`find_stale_backups` -
    identische Cutoff-Semantik, hier zusaetzlich mit tatsaechlicher
    Loeschung. Fuer den reinen Pre-Flight-Check ohne Side-Effect
    ``find_stale_backups`` verwenden.
    """
    deleted: list[Path] = []
    for p in find_stale_backups(backup_dir, max_age_days, now=now):
        try:
            p.unlink()
            deleted.append(p)
        except OSError:
            pass
    return deleted


def backup_directory_stats(backup_dir: Path) -> dict:
    """Fasst den Backup-Ordner als Disk-Belegungs-Report zusammen.

    Spiegelt :func:`list_backups` (Aufzaehlung) auf die Volume-Achse:
    waehrend ``list_backups`` einzelne Pfade liefert, fasst
    ``backup_directory_stats`` den Ordner in einem Schritt zu einem
    numerischen Report zusammen - Anzahl Backups, Gesamt-Bytes auf Platte,
    Durchschnitts-Bytes pro Backup, frueheste und spaeteste Zeitstempel.
    Ergaenzt das prune-Vokabular (:func:`prune_old_backups`,
    :func:`prune_backups_by_age`) um einen read-only Reporter fuer
    Cron-Jobs und Wartungs-Dashboards, die vor einer Prune-Entscheidung
    wissen wollen, wie viel Speicher die aktuelle Backup-Halde belegt und
    wie weit der aelteste Eintrag zurueckreicht.

    Beruehrt ausschliesslich Dateien, die zum
    :func:`write_rotated_backup`-Schema passen
    (``stonebook_backup_*.json[.gz]``) - fremde Dateien im Ordner
    (README, andere Exporte, Lock-Files) bleiben unangetastet und zaehlen
    weder in ``count`` noch in ``total_bytes`` noch in ``average_bytes``.
    ``oldest_stamp`` und ``newest_stamp`` beziehen sich auf den
    Dateinamen-Zeitstempel (nicht ``mtime``/``ctime``), damit Backups,
    die vom Backup-Server kopiert oder verschoben wurden, ihr originales
    Alter behalten (Single-Source-of-Truth = Filename-Stempel, spiegelt
    :func:`prune_backups_by_age`).

    ``average_bytes`` ist der mittlere Bytes-Verbrauch pro Backup als
    natuerliche Ergaenzung zu ``total_bytes`` auf der Volume-Achse -
    spiegelt das Durchschnitts-Pattern aus ``stats.py``
    (``wert_durchschnitt_chf``, ``gewicht_durchschnitt_g``,
    ``mohs_kollektion_durchschnitt``, ``dichte_kollektion_durchschnitt``)
    auf die Backup-Halde. Beantwortet in einem Schritt "wie gross ist
    ein typisches Backup?" fuer Kapazitaetsplanung und macht damit
    Groessen-Anomalien ohne separate largest/smallest-Aufrufe erkennbar
    (Backup mit ``st_size >> average_bytes`` verdient einen
    :func:`inspect_backup`-Check). Wird als ``round()``-integer
    ausgeliefert (Bytes-Achse ist diskret), spiegelt die
    Integer-Konvention von ``total_bytes``. Divison durch ``count``
    (nicht ``len(size-lesbare Backups)``) ist konsistent mit
    ``total_bytes``, wo eine einzelne unlesbare Datei zwar in ``count``
    zaehlt aber nicht zur Summe beitraegt - der Durchschnitt darf durch
    Race-Conditions minimal nach unten gezogen werden, aber nicht
    divergieren.

    ``median_bytes`` ist die ausreisser-robuste Zentraltendenz auf der
    Volume-Achse - spiegelt das Median-Pattern aus ``stats.py``
    (``wert_median_chf``, ``gewicht_median_g``,
    ``mohs_kollektion_median``, ``dichte_kollektion_median``) auf die
    Backup-Halde. Waehrend ``average_bytes`` von einem einzelnen sehr
    grossen oder sehr kleinen Backup deutlich verzerrt werden kann (ein
    Voll-Backup nach einer Mass-Import-Aktion neben Delta-Snapshots),
    liegt der Median unverzerrt in der Mitte der Groessenverteilung und
    macht die "typische Backup-Groesse" auch bei asymmetrischer
    Verteilung sichtbar. Bei uniformer Verteilung (alle Backups gleicher
    Groesse) faellt der Median mit dem Durchschnitt zusammen; die
    Differenz beider Achsen beziffert die Schiefe der Bytes-Verteilung.
    Wird als integer ausgeliefert (Bytes-Achse ist diskret, spiegelt
    ``average_bytes``); bei gerader ``count`` wird der Median als
    gerundetes Mittel der beiden mittleren Werte berechnet, spiegelt die
    Median-Konvention aus ``stats.py``. Basiert auf der Menge der
    tatsaechlich lesbaren Dateien - unlesbare Dateien (Race gegen
    paralleles Loeschen) werden uebersprungen und beeinflussen den Median
    nicht, spiegelt das ``total_bytes``-Verhalten.

    ``max_bytes`` ist die Aussen-Rand-Achse der Bytes-Verteilung -
    spiegelt das Max-Pattern aus ``stats.py`` (``wert_max_chf``,
    ``gewicht_max_g``, ``mohs_kollektion_max``, ``dichte_kollektion_max``,
    ``koordinaten_radius_max_km``) auf die Backup-Halde. Beantwortet die
    naheliegende Speicher-Frage "wie gross ist das umfangreichste
    Backup?" in einem Schritt aus dem Aggregat-Report, ohne dass der
    Caller zusaetzlich :func:`largest_backup` aufrufen und dann
    ``st_size`` neu abfragen muss (spart einen zweiten Pass ueber die
    Backup-Halde bei Cron-Reportern, die den Volume-Report bereits
    haben). Vervollstaendigt gemeinsam mit ``median_bytes`` und
    ``average_bytes`` die Zentraltendenz-plus-Rand-Sicht auf die
    Bytes-Verteilung; die Differenz ``max_bytes - average_bytes`` macht
    die obere Ausreisser-Neigung sichtbar (grosser Voll-Backup neben
    Delta-Snapshots). Basiert auf derselben Menge der tatsaechlich
    lesbaren Dateien wie ``median_bytes`` und ``average_bytes`` -
    unlesbare Dateien werden uebersprungen und beeinflussen den Max
    nicht (spiegelt das ``total_bytes``-Verhalten). Bei ``count == 1``
    faellt ``max_bytes`` mit ``median_bytes`` und ``average_bytes``
    zusammen, spiegelt die Grenzfall-Konvention bei Einzel-Stichproben.
    Wird als integer ausgeliefert (Bytes-Achse ist diskret, spiegelt
    ``average_bytes`` / ``median_bytes``). Semantisch identisch zu
    ``largest_backup().stat().st_size`` bei lesbaren Dateien, aber
    ohne zweiten I/O-Pfad ueber :func:`largest_backup` und ohne den
    Pfad-Wrapper - der Aggregat-Report liefert die Byte-Zahl direkt.

    ``min_bytes`` ist die Innen-Rand-Achse der Bytes-Verteilung -
    symmetrisches Pendant zu ``max_bytes`` und spiegelt das
    Min-Pattern aus ``stats.py`` (``wert_min_chf``, ``gewicht_min_g``,
    ``mohs_kollektion_min``, ``dichte_kollektion_min``,
    ``koordinaten_radius_min_km``) auf die Backup-Halde.
    Vervollstaendigt gemeinsam mit ``max_bytes``, ``median_bytes`` und
    ``average_bytes`` das Aggregations-Quartett min/max/durchschnitt/
    median auf der Volume-Achse: min und max sind die beiden
    Rand-Extreme derselben Verteilung, durchschnitt und median die
    typischen Zentraltendenzen dazwischen. Beantwortet in einem Schritt
    "wie klein ist das kompakteste Backup?" fuer Kapazitaetsplanung und
    macht damit Unter-Ausreisser sichtbar (Delta-Snapshot neben
    Voll-Backups; ein Backup mit ``st_size == min_bytes`` deutlich unter
    ``median_bytes`` verdient einen :func:`inspect_backup`-Check, ob es
    beim Schreiben abgebrochen wurde). Die Differenz ``max_bytes -
    min_bytes`` (Range) beziffert die Gesamt-Spannweite der
    Bytes-Verteilung, ``median_bytes - min_bytes`` die untere Half-Range
    - beide Achsen zusammen mit ``max_bytes`` und ``median_bytes``
    liefern ein vollstaendiges Fuenf-Zahlen-Bild ohne separaten
    :func:`smallest_backup`-Aufruf. Basiert auf derselben Menge der
    tatsaechlich lesbaren Dateien wie ``max_bytes`` / ``median_bytes`` /
    ``average_bytes`` - unlesbare Dateien werden uebersprungen und
    beeinflussen den Min nicht (spiegelt das ``total_bytes``-Verhalten).
    Bei ``count == 1`` faellt ``min_bytes`` mit ``max_bytes`` /
    ``median_bytes`` / ``average_bytes`` zusammen, spiegelt die
    Grenzfall-Konvention bei Einzel-Stichproben. Wird als integer
    ausgeliefert (Bytes-Achse ist diskret, spiegelt ``average_bytes``
    / ``median_bytes`` / ``max_bytes``). Semantisch identisch zu
    ``smallest_backup().stat().st_size`` bei lesbaren Dateien, aber
    ohne zweiten I/O-Pfad ueber :func:`smallest_backup` und ohne den
    Pfad-Wrapper - der Aggregat-Report liefert die Byte-Zahl direkt.

    Leerer Ordner / nur fremde Dateien liefert
    ``{"count": 0, "total_bytes": 0, "average_bytes": None,
    "median_bytes": None, "min_bytes": None, "max_bytes": None,
    "oldest_stamp": None, "newest_stamp": None}``.
    Nicht existierender Ordner liefert dasselbe (spiegelt
    :func:`list_backups`, das bei fehlendem Ordner eine leere Liste
    zurueckgibt statt zu crashen - geeignet fuer Cron-Reporter, die den
    Report-Aufruf vor der ersten Backup-Schreibe machen).
    ``average_bytes``, ``median_bytes``, ``min_bytes`` und ``max_bytes``
    sind ``None`` bei ``count == 0`` (kein Division-by-Zero-Crash bei
    ``average``, kein Index-Fehler bei ``median``, kein leeres-``max``-
    oder leeres-``min``-Crash, kein irrefuehrender ``0``-Report der wie
    "durchschnittlich leere Backups" aussaehe - spiegelt die
    None-Konvention der Zeitstempel bei fehlendem Bestand).
    Unlesbare Dateien (Race gegen paralleles Loeschen) werden beim
    ``st_size``-Zugriff uebersprungen statt zu crashen, spiegelt das
    ``try: unlink except OSError``-Verhalten der prune-Funktionen.
    Zeitstempel werden als ISO-8601-String ``YYYY-MM-DDTHH:MM:SS``
    ausgegeben (nicht als ``datetime``-Objekt), damit der Report ohne
    Konvertierung durch ``json.dumps`` laeuft - spiegelt das
    Ausgabeformat von :func:`inspect_backup` / :func:`validate_backup`.
    """
    count = 0
    total_bytes = 0
    sizes: list[int] = []
    stamps: list[datetime.datetime] = []
    for p in list_backups(backup_dir):
        count += 1
        try:
            size = p.stat().st_size
        except OSError:
            size = None
        if size is not None:
            total_bytes += size
            sizes.append(size)
        stamp = _parse_backup_stamp(p)
        if stamp is not None:
            stamps.append(stamp)
    return {
        "count": count,
        "total_bytes": total_bytes,
        "average_bytes": round(total_bytes / count) if count else None,
        "median_bytes": _median_int(sizes) if sizes else None,
        "min_bytes": min(sizes) if sizes else None,
        "max_bytes": max(sizes) if sizes else None,
        "oldest_stamp": min(stamps).isoformat() if stamps else None,
        "newest_stamp": max(stamps).isoformat() if stamps else None,
    }


def _median_int(values: list[int]) -> int:
    """Median einer Bytes-Liste, gerundet auf Integer.

    Bytes sind diskret, daher wird der Median bei gerader Anzahl als
    ``round((v[n//2-1] + v[n//2]) / 2)`` ausgeliefert - spiegelt die
    Rundungs-Konvention von :func:`backup_directory_stats.average_bytes`.
    Population-Median (Divisor 2 statt 1) ist konsistent mit den
    Median-Berechnungen in :mod:`stonebook.db.stats`.
    """
    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        return int(ordered[n // 2])
    return round((ordered[n // 2 - 1] + ordered[n // 2]) / 2)


def prune_backups_gfs(backup_dir: Path, *,
                     daily: int = 7, weekly: int = 4, monthly: int = 12,
                     now: datetime.datetime | None = None) -> list[Path]:
    """Grandfather-Father-Son-Rotation: Newest-per-Bucket-Retention.

    Spiegelt :func:`prune_old_backups` (Count-Achse) und
    :func:`prune_backups_by_age` (Alter-Achse) auf die Bucket-Achse:
    waehrend die Count-Variante die N neuesten Backups behaelt (unabhaengig
    von deren Zeit-Verteilung: 10 Backups aus einem Tag zaehlen als 10) und
    die Age-Variante alle Backups juenger als K Tage (unabhaengig von deren
    Anzahl: bei taeglicher Schreibe 30 Backups pro 30 Tage), behaelt die
    GFS-Variante das jeweils *neueste* Backup pro Zeit-Bucket. Damit
    entsteht eine natuerliche Verduennung mit der Zeit - die letzten Tage
    granular pro Tag, die vergangenen Wochen granular pro Woche, die noch
    aelteren Monate granular pro Monat -, das in Produktionssystemen
    etablierte Standard-Rotations-Muster ("Grossvater-Vater-Sohn"). Erlaubt
    damit lange Retention (12 Monate zurueck) bei begrenztem Festplatten-
    Verbrauch (hoechstens ``daily+weekly+monthly`` = 23 Backups statt 365
    bei taeglicher Schreibe).

    Buckets werden relativ zu ``now`` gebildet:

    - ``daily=N``: die letzten N Kalendertage (inkl. dem ``now``-Tag),
      pro Tag das neueste Backup dieses Tages.
    - ``weekly=M``: die letzten M ISO-Kalenderwochen (inkl. ``now``-Woche),
      pro Woche das neueste Backup dieser Woche.
    - ``monthly=K``: die letzten K Kalendermonate (inkl. ``now``-Monat),
      pro Monat das neueste Backup dieses Monats.

    Die drei Behalt-Mengen ueberlappen sich frei; ein Backup, das zugleich
    das neueste des Tages, der Woche und des Monats ist, zaehlt nur einmal.
    Ein einzelnes Argument darf ``0`` sein: dann entfaellt der jeweilige
    Bucket-Layer komplett (``daily=0, weekly=4, monthly=0`` behaelt nur die
    neueste Version pro Woche); alle drei ``0`` loescht alle Backups mit
    Stempel strikt vor ``now`` (Cleanup-Befehl vor Voll-Reset). Ein
    negativer Wert wirft ``ValueError`` (spiegelt :func:`prune_old_backups`
    mit ``keep < 1`` und :func:`prune_backups_by_age` mit
    ``max_age_days < 0``).

    Beruehrt ausschliesslich Dateien, die zum
    :func:`write_rotated_backup`-Schema passen
    (``stonebook_backup_*.json[.gz]``); alle anderen Dateien im Ordner
    bleiben unangetastet (spiegelt :func:`prune_old_backups` /
    :func:`prune_backups_by_age`). Der Vergleich basiert auf dem
    Dateinamen-Stempel (nicht ``mtime``/``ctime``), damit vom NAS
    kopierte/verschobene Backups ihr originales Alter behalten.

    Backups mit Stempel strikt nach ``now`` bleiben unangetastet
    (parallel schreibender Job, Uhr-Skew) - spiegelt implizit das
    Verhalten von :func:`prune_backups_by_age` fuer Zukunfts-Stempel
    (``stamp >= cutoff`` deckt dort ebenfalls Zukunfts-Stempel ab).

    ``now`` ist injizierbar fuer Tests/Replay (spiegelt
    :func:`prune_backups_by_age`). Nicht-loeschbare Dateien (Lock,
    Parallel-Loeschung) werden uebersprungen statt zu crashen (spiegelt
    :func:`prune_old_backups`). Liefert die geloeschten Pfade zurueck.
    """
    if daily < 0 or weekly < 0 or monthly < 0:
        raise ValueError("daily/weekly/monthly muss >= 0 sein")
    now = now or datetime.datetime.now()
    stamped: list[tuple[Path, datetime.datetime]] = []
    for p in list_backups(backup_dir):
        stamp = _parse_backup_stamp(p)
        if stamp is not None:
            stamped.append((p, stamp))
    # Sortierung: neuestes zuerst - "first seen per bucket" ist damit das
    # neueste des jeweiligen Buckets.
    stamped.sort(key=lambda x: x[1], reverse=True)

    keep: set[Path] = set()
    # Stempel >= now bleiben unangetastet (paralleler Writer, Clock-Skew,
    # gleichzeitige Schreibe) - spiegelt :func:`prune_backups_by_age`, wo
    # ``stamp >= cutoff`` (mit ``cutoff = now - max_age_days``) ebenfalls
    # "behalten" bedeutet und deren max_age_days=0-Verhalten das Behalten
    # der == now-Stempel garantiert.
    for p, stamp in stamped:
        if stamp >= now:
            keep.add(p)

    now_date = now.date()
    now_year_iso, now_week_iso, _ = now.isocalendar()

    def _add_newest_per_bucket(in_window, bucket_of) -> None:
        seen: dict = {}
        for p, stamp in stamped:
            if stamp >= now:
                continue
            if not in_window(stamp):
                continue
            k = bucket_of(stamp)
            if k in seen:
                continue
            seen[k] = p
        keep.update(seen.values())

    if daily > 0:
        daily_cutoff = now_date - datetime.timedelta(days=daily - 1)
        _add_newest_per_bucket(
            lambda s: daily_cutoff <= s.date() <= now_date,
            lambda s: s.date(),
        )

    if weekly > 0:
        # ISO-Kalenderwochen: (year, week)-Tupel identifiziert eine Woche
        # eindeutig ueber Jahresgrenzen hinweg (Silvester-Woche kann in
        # unterschiedliche ISO-Jahre gehoeren). Die Rueckrechnung ueber
        # date.fromisocalendar+timedelta(weeks) liefert das ISO-Jahr-und
        # -Wochen-Tupel der Cutoff-Woche.
        now_week_monday = datetime.date.fromisocalendar(
            now_year_iso, now_week_iso, 1)
        cutoff_monday = now_week_monday - datetime.timedelta(weeks=weekly - 1)
        cutoff_year_iso, cutoff_week_iso, _ = cutoff_monday.isocalendar()
        cutoff_week_key = (cutoff_year_iso, cutoff_week_iso)
        now_week_key = (now_year_iso, now_week_iso)

        def _week_in_window(s: datetime.datetime) -> bool:
            sy, sw, _ = s.isocalendar()
            return cutoff_week_key <= (sy, sw) <= now_week_key

        _add_newest_per_bucket(
            _week_in_window,
            lambda s: s.isocalendar()[:2],
        )

    if monthly > 0:
        # Monats-Rueckrechnung: (year, month) als Bucket-Schluessel,
        # (K - 1) Monate zurueck fuer den Cutoff. Kein date.replace-Trick,
        # weil das mit dem Monats-Tag interferieren kann - reine
        # (year, month)-Arithmetik ist eindeutig.
        total_month = now.year * 12 + (now.month - 1) - (monthly - 1)
        cutoff_year, cutoff_month0 = divmod(total_month, 12)
        cutoff_month_key = (cutoff_year, cutoff_month0 + 1)
        now_month_key = (now.year, now.month)

        def _month_in_window(s: datetime.datetime) -> bool:
            return cutoff_month_key <= (s.year, s.month) <= now_month_key

        _add_newest_per_bucket(
            _month_in_window,
            lambda s: (s.year, s.month),
        )

    deleted: list[Path] = []
    for p, _stamp in stamped:
        if p in keep:
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
