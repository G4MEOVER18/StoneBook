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


def find_excess_backups(backup_dir: Path, keep: int) -> list[Path]:
    """Listet die aeltesten Backups, die ``prune_old_backups(keep)`` loeschen wuerde.

    Reine Lese-/Check-Variante von :func:`prune_old_backups` - berechnet die
    gleiche Kandidatenmenge (die ``len(list_backups) - keep`` aeltesten
    Dateien nach Filename-Stempel), loescht aber nichts. Bildet damit das
    check-Ende des check/fix-Paares auf der Count-Achse, symmetrisch zu
    :func:`find_stale_backups` (check-Ende von :func:`prune_backups_by_age`
    auf der Zeit-Achse) und zu :func:`stonebook.db.integrity.find_orphan_images`
    (check-Ende von ``delete_orphan_images`` auf der FK-Achse).

    Nutzen: Cron-Reporter kann die excess-Liste erst loggen, dann prune
    entscheiden lassen (oder gar nicht); ein Bestaetigungs-Dialog kann dem
    User zeigen, welche konkreten Dateien beim naechsten ``prune``
    verloren gingen, bevor er OK klickt; ein Monitoring-Job kann Exit 1
    liefern, sobald mehr als ``keep`` Backups herumliegen, ohne selbst
    pruning-Rechte zu brauchen.

    Reihenfolge = ``list_backups``-Reihenfolge (aeltester Dateiname zuerst,
    spiegelt die Loesch-Reihenfolge von :func:`prune_old_backups`), damit
    die Ausgabe deterministisch bleibt und ein CLI-Reporter direkt
    "aeltestes zuerst" listen kann.

    ``keep < 1`` wirft ``ValueError`` (spiegelt :func:`prune_old_backups`).
    Fehlender Ordner -> ``[]`` (spiegelt :func:`list_backups` /
    :func:`find_stale_backups`). Ordner mit ``<= keep`` Backups liefert
    ``[]`` (nichts zu tun).
    """
    if keep < 1:
        raise ValueError("keep muss >= 1 sein")
    existing = list_backups(backup_dir)
    if len(existing) <= keep:
        return []
    return existing[:len(existing) - keep]


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

    ``range_bytes`` ist die Original-Einheiten-Dispersions-Achse der
    Bytes-Verteilung: ``max_bytes - min_bytes``. Spiegelt das
    Spanweiten-Pattern aus ``stats.py`` (``wert_spanweite_chf``,
    ``gewicht_spanweite_g``, ``mohs_kollektion_spanweite``,
    ``dichte_kollektion_spanweite``, ``confidence_spanweite_prozent``,
    ``koordinaten_radius_spanweite_km``) auf die Backup-Volume-Achse und
    ergaenzt die Innen-/Aussen-Rand-Achsen (``min_bytes`` / ``max_bytes``)
    um die vorberechnete Differenz - der Caller kann die Streubreite ohne
    zweiten Rechenschritt ablesen. Beantwortet in einem Schritt "wie stark
    schwanken die Backup-Groessen?" fuer Kapazitaetsplanung und macht
    heterogene Backup-Halden sichtbar (viele Delta-Snapshots neben einem
    Voll-Backup: kleiner ``median_bytes`` + grosser ``range_bytes``).
    Wird als integer ausgeliefert (Bytes-Achse ist diskret, spiegelt
    ``min_bytes`` / ``max_bytes``). Bei ``count == 1`` faellt
    ``range_bytes`` auf ``0`` (min == max), spiegelt die Grenzfall-
    Konvention der Spanweiten-Achsen in ``stats.py`` (gleiche Werte →
    keine Streuung). Basiert auf derselben Menge der tatsaechlich
    lesbaren Dateien wie ``min_bytes`` / ``max_bytes`` - unlesbare
    Dateien werden uebersprungen und beeinflussen die Spanweite nicht.
    ``range_bytes`` ist ``None`` bei ``count == 0`` (kein leeres-min/
    max-Crash, spiegelt die None-Konvention der Zentraltendenz- und
    Rand-Achsen bei fehlendem Bestand).

    ``stddev_bytes`` ist die Populations-Standardabweichung der
    Bytes-Verteilung als Streuungs-Achse in Original-Einheiten (Bytes)
    zur Zentraltendenz-Achse ``average_bytes``. Spiegelt das
    ``wert_standardabweichung_chf`` / ``gewicht_standardabweichung_g``
    / ``mohs_kollektion_standardabweichung`` /
    ``dichte_kollektion_standardabweichung`` /
    ``confidence_standardabweichung_prozent`` /
    ``koordinaten_radius_standardabweichung_km``-Muster auf die
    Backup-Volume-Achse. Waehrend ``range_bytes`` nur auf die zwei
    Extremwerte reagiert (Groessen-Bandbreite), reagiert sigma auf die
    volle Verteilungsform - eine Halde mit gleichmaessig grossen
    Backups hat kleines sigma, eine mit einem grossen Voll-Backup
    neben vielen Delta-Snapshots hat grosses sigma trotz aehnlicher
    Bandbreite. Populations-Variante (Divisor ``n`` statt ``n-1``)
    spiegelt die Backup-Halde-als-Grundgesamtheit-Konvention der
    uebrigen Volume-Achsen (``average_bytes`` / ``median_bytes``
    verwenden ebenfalls die volle Menge, keine Stichproben-Korrektur).
    Numerisch stabile Formel via ``(x - mean)^2`` statt
    ``E[X^2] - E[X]^2``, spiegelt die stddev-Berechnung in
    ``stats.py`` (bei Backup-Groessen im GiB-Bereich mit kleiner
    Varianz zwischen Delta-Snapshots waere die Kancellations-Version
    numerisch instabil). Bei ``count == 1`` kollabiert ``stddev_bytes``
    auf ``0`` (kein Streuungs-Grund bei Einzel-Stichprobe, spiegelt
    die Grenzfall-Konvention der Radial-Streuungs-Achse und die
    Min/Max/Mittel/Median-Single-Point-Kollaps-Konvention). Wird als
    ``round()``-integer ausgeliefert (Bytes-Achse ist diskret,
    spiegelt ``average_bytes`` / ``median_bytes``). Basiert auf der
    Menge der tatsaechlich lesbaren Dateien - unlesbare Dateien
    werden uebersprungen und beeinflussen sigma nicht (spiegelt das
    ``total_bytes``-Verhalten). Reuse-Pfad: nutzt die bereits
    berechnete ``sizes``-Liste und den ``total_bytes``-Zwischenwert
    fuer den Mittelwert (kein zweiter Pass ueber die Backup-Halde,
    kein zweiter ``st_size``-Zugriff). Die Differenz
    ``range_bytes - stddev_bytes`` zeigt, wie stark die Streuung von
    Ausreissern statt der volleren Verteilungsform getrieben ist.

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

    ``variationskoeffizient_bytes_prozent`` ist der dimensionslose
    Variationskoeffizient (CV = ``stddev_bytes / average_bytes * 100``)
    auf der Backup-Volume-Achse. Spiegelt das
    ``koordinaten_radius_variationskoeffizient_prozent`` /
    ``wert_variationskoeffizient_prozent`` /
    ``gewicht_variationskoeffizient_prozent`` /
    ``mohs_kollektion_variationskoeffizient_prozent`` /
    ``dichte_kollektion_variationskoeffizient_prozent`` /
    ``confidence_variationskoeffizient_prozent``-Muster aus ``stats.py``
    auf die Backup-Halde. Waehrend ``stddev_bytes`` die Streuung in
    Original-Einheiten (Bytes) beziffert, normiert der CV sigma auf den
    Durchschnitts-Verbrauch und macht die Backup-Homogenitaet skalen-
    unabhaengig vergleichbar: eine Halde von Delta-Snapshots mit
    Ø 5 MB und sigma 500 KB (CV 10%) hat dieselbe relative Streuung
    wie eine Voll-Backup-Halde mit Ø 500 MB und sigma 50 MB (CV 10%),
    obwohl die Absolutwerte um Faktor 100 auseinanderliegen -
    "wie einheitlich sind meine Backup-Groessen, unabhaengig vom
    Skalenniveau?". Ausgabe in Prozent (``sigma/mean * 100``, auf 2
    Nachkommastellen gerundet), spiegelt die CV-Achsen-Konvention aus
    ``stats.py``. Guarded gegen ``mean == 0`` (Kollaps bei leerer /
    unlesbarer Halde): CV wird dann ``None`` statt
    ``ZeroDivisionError``, damit der Report und Downstream-Konsumenten
    den Undefined-Zustand transparent unterscheiden koennen - anders
    als sigma (``0`` bei uniformer Verteilung) ist CV mathematisch
    undefined bei ``mean == 0``, nicht ``0``. Bei ``count == 1``
    kollabiert CV auf ``0.0`` (sigma = 0 durch Single-Point-Konvention,
    mean = size des einzigen Backups), konsistent zum ``stddev_bytes ==
    range_bytes == 0`` bei Einzel-Stichproben. Bei uniformer Verteilung
    (alle Backups gleich gross) faellt CV ebenfalls auf ``0.0`` als
    natuerliche Konsequenz der ``sigma == 0``-Voraussetzung. Reuse-Pfad:
    nutzt die bereits berechnete ``sizes``-Liste und den ``stddev_bytes``-
    Zwischenwert (kein zweiter Pass ueber die Backup-Halde, kein zweiter
    ``st_size``-Zugriff, kein zweiter sigma-Rechenschritt); der Mittelwert
    wird lokal aus ``sum(sizes) / len(sizes)`` unabhaengig vom gerundeten
    ``average_bytes`` neu berechnet (spiegelt die _stddev_int-Konvention,
    damit CV nicht durch die 0.5-Byte-Rundung von ``average_bytes``
    verzerrt wird).

    ``average_gap_days`` ist der durchschnittliche Abstand in Tagen
    zwischen aufeinanderfolgenden Backups (``days_span / (count - 1)``)
    - spiegelt ``average_bytes`` (Durchschnitts-Volumen pro Backup) auf
    die Zeit-Frequenz-Achse. Waehrend ``days_span`` die absolute
    Retention-Tiefe beziffert (wie weit reicht die Halde zurueck),
    beantwortet ``average_gap_days`` die Frequenz-Frage "wie oft wird
    typischerweise ein Backup geschrieben?" ohne dass der Caller die
    Formel selbst rechnen muss. Nutzen im Cron-Reporter: bei einer
    taeglichen Backup-Rotation liefert der Wert ~1.0; bei einer
    stuendlichen ~1/24; ein Wert > 1 zeigt sporadische Backups (z.B.
    manuelles Backup nach Bearbeitungssessions), ein Wert < 1/24
    hyperaktives Snapshotting. Kombiniert mit ``count`` bewacht die
    Kennzahl die Retention-Vorgabe: bei einer 30-Tage / 30-Backups-
    Rotation soll ``average_gap_days ~= 1``, ein deutlich groesserer
    Wert deutet auf ausgefallene Backup-Cronjobs hin. Reuse-Pfad:
    berechnet als ``days_span / (count - 1)`` aus den bereits vor-
    handenen Werten (single-source-of-truth, keine parallele stamps-
    Iteration); die (count - 1)-Divisor-Semantik spiegelt die
    "Zaun-Post-Regel" der consecutive-intervals-Konvention aus der
    Time-Series-Statistik (n Punkte haben n-1 Intervalle). Bei
    ``count < 2`` liefert der Wert ``None`` (keine Intervalle definier-
    bar - bei 0 Backups gibt es weder Zeit noch Frequenz, bei 1
    Backup gibt es keinen Vorgaenger als Intervall-Anker), spiegelt
    die Grenzfall-Konvention von ``stddev_bytes`` bei Einzel-
    Stichproben (kein Streuungs-Grund). Bei ``count >= 2`` mit
    ``days_span == 0`` (mehrere Backups im gleichen Sekunden-Stempel,
    unwahrscheinlich aber moeglich bei Batch-Import) liefert der Wert
    ``0.0`` (Intervalle sind alle null - die Divison ``0 / (n-1)``
    ist mathematisch wohldefiniert und gibt 0). Als ``float`` aus-
    geliefert, spiegelt die ``days_span``-Konvention (Zeit-Achse ist
    kontinuierlich, keine Integer-Rundung).

    ``days_span`` ist die Zeit-Achsen-Spanweite in Tagen zwischen
    ``oldest_stamp`` und ``newest_stamp`` - spiegelt ``range_bytes``
    (Spanweite auf der Volume-Achse) auf die Zeit-Achse. Waehrend
    ``oldest_stamp`` und ``newest_stamp`` die Rand-Zeitstempel als
    ISO-Strings liefern, beantwortet ``days_span`` in einem Schritt
    "wie weit reicht die Backup-Halde zeitlich zurueck?" ohne dass der
    Caller die Zeitstempel selbst parsen und differenzieren muss - der
    Wert entspricht ``(newest_stamp - oldest_stamp).total_seconds() /
    86400`` und ist damit ohne Zeitzone-/Sommerzeit-Umkehr direkt
    vergleichbar (Filename-Zeitstempel sind konventionell in lokaler
    Zeit ohne TZ-Anhang, spiegelt die
    :func:`_parse_backup_stamp`-Konvention). Nutzen im Cron-Reporter:
    zeigt die tatsaechliche Retention-Tiefe der Halde neben der
    Zaehlung (``count``) und dem Volumen (``total_bytes``); bei einer
    30-Tage-Rotation via :func:`prune_backups_by_age` bewacht
    ``days_span`` die Retention-Vorgabe (``days_span <= 30`` als
    Cron-Assertion). Bei erwarteter Retention-Ausdehnung durch
    :func:`prune_backups_gfs` (GFS-Backups mit weit zurueckreichenden
    Monats-Snapshots) zeigt ``days_span`` die gewuenschte Tiefe an.
    Als ``float`` ausgeliefert (Zeit-Achse ist kontinuierlich, spiegelt
    die Prozent-Achsen ``variationskoeffizient_bytes_prozent`` -
    Bytes/Prozent-Achse wird auf Integer/2-Nachkommastellen gerundet,
    Zeit-Achse bleibt voller Float damit sub-Tag-Aufloesung nicht
    verloren geht: eine Halde mit stundenweisen Snapshots zeigt Bruch-
    Tage). Bei ``count == 1`` faellt ``days_span`` auf ``0.0`` (oldest
    == newest, keine Zeit-Spanne moeglich), spiegelt die Grenzfall-
    Konvention von ``range_bytes == 0`` und der uebrigen
    Rand-Extreme-Kollaps-Konventionen. Bei ``count == 0`` liefert der
    Wert ``None`` (kein Zeitstempel-Bezugswert vorhanden, spiegelt die
    None-Konvention von ``oldest_stamp`` / ``newest_stamp`` /
    ``range_bytes`` bei fehlendem Bestand). Backups ohne parsbaren
    Filename-Zeitstempel (Race gegen Rename, korrupte Namen) tragen
    nicht zur Spanne bei - der Wert bleibt konsistent mit
    ``oldest_stamp`` / ``newest_stamp``, die ebenfalls nur die
    parsbaren Stempel beruecksichtigen.

    ``median_gap_days`` ist die ausreisser-robuste Zentraltendenz auf
    der Frequenz-Achse - spiegelt das
    :func:`_median_int`/``median_bytes``-vs-``average_bytes``-Paar aus
    dem Volume-Bereich auf die Zeit-Achse. Waehrend ``average_gap_days``
    von einem einzelnen sehr weiten Intervall verzerrt wird (eine
    Ferien-Luecke von 6 Wochen in einer sonst taeglichen Backup-
    Rotation zieht den Durchschnitts-Abstand deutlich hoch), liegt der
    Median unverzerrt auf dem typischen Sekunden-Intervall zwischen
    Backups und macht die tatsaechliche Backup-Kadenz sichtbar. Kern-
    Formel: sortiere die Stamps aufsteigend, bilde die (n-1)
    aufeinanderfolgenden Diffs in Tagen, gib den Median dieser Diffs
    aus. Bei uniformer Kadenz (alle Intervalle gleich lang, z.B.
    taegliches Cronjob-Backup) faellt ``median_gap_days`` mit
    ``average_gap_days`` zusammen; die Differenz beider Achsen
    beziffert die Schiefe der Intervall-Verteilung - ein deutlich
    kleinerer Median gegenueber dem Durchschnitt zeigt eine Halde
    mit sonst enger Kadenz aber einzelnen langen Luecken (Ferien,
    Cron-Ausfall). Als ``float`` ausgeliefert (Zeit-Achse ist
    kontinuierlich, spiegelt die ``days_span``/``average_gap_days``-
    Float-Konvention - Sub-Tag-Aufloesung bleibt bei stundenweiser
    Rotation erhalten und wird nicht durch Integer-Trunkierung
    verloren). Bei ``len(stamps) < 2`` liefert der Wert ``None``
    (keine Intervalle definierbar, spiegelt die Grenzfall-Konvention
    von ``average_gap_days``). Reuse-Pfad: die sortierten Stamps und
    die Sekunden-Diffs werden lokal berechnet, damit die
    Zeit-Achsen-Achsen ``days_span`` / ``average_gap_days`` /
    ``median_gap_days`` alle auf derselben Halden-Stamp-Menge
    beruhen (single-source-of-truth).

    Leerer Ordner / nur fremde Dateien liefert
    ``{"count": 0, "total_bytes": 0, "average_bytes": None,
    "median_bytes": None, "min_bytes": None, "max_bytes": None,
    "range_bytes": None, "stddev_bytes": None,
    "variationskoeffizient_bytes_prozent": None,
    "oldest_stamp": None, "newest_stamp": None, "days_span": None,
    "average_gap_days": None, "median_gap_days": None}``.
    Nicht existierender Ordner liefert dasselbe (spiegelt
    :func:`list_backups`, das bei fehlendem Ordner eine leere Liste
    zurueckgibt statt zu crashen - geeignet fuer Cron-Reporter, die den
    Report-Aufruf vor der ersten Backup-Schreibe machen).
    ``average_bytes``, ``median_bytes``, ``min_bytes``, ``max_bytes``,
    ``range_bytes``, ``stddev_bytes`` und
    ``variationskoeffizient_bytes_prozent`` sind ``None`` bei
    ``count == 0`` (kein Division-by-Zero-Crash bei ``average`` /
    ``stddev`` / CV, kein Index-Fehler bei ``median``, kein leeres-
    ``max``- oder leeres-``min``-Crash, keine irrefuehrende ``0``-
    Streuung die wie "identische Backup-Groessen" aussaehe - spiegelt
    die None-Konvention der Zeitstempel bei fehlendem Bestand).
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
    stddev = _stddev_int(sizes) if sizes else None
    if sizes:
        mean = sum(sizes) / len(sizes)
        # CV nutzt das ungerundete sigma statt _stddev_int (das die Rundung auf
        # Integer vollzieht), damit die 2-Nachkommastellen-CV-Ausgabe nicht
        # durch die 0.5-Byte-Rundung von stddev_bytes verzerrt wird - spiegelt
        # die Konvention der ungerundeten sigma-Weiterverwendung in
        # koordinaten_radius_variationskoeffizient_prozent aus stats.py.
        variance = sum((v - mean) ** 2 for v in sizes) / len(sizes)
        raw_sigma = variance ** 0.5
        cv_prozent = round(raw_sigma / mean * 100.0, 2) if mean > 0 else None
    else:
        cv_prozent = None
    if stamps:
        oldest = min(stamps)
        newest = max(stamps)
        # (newest - oldest).total_seconds() / 86400 - Float bleibt voll, damit
        # sub-Tag-Aufloesung nicht verloren geht (stundenweise Snapshots
        # ergeben Bruch-Tage, nicht 0 durch Integer-Trunkierung).
        days_span = (newest - oldest).total_seconds() / 86400.0
    else:
        oldest = None
        newest = None
        days_span = None
    # average_gap_days = days_span / (count - 1) mit Zaun-Post-Regel: n
    # Zeitstempel haben n-1 aufeinanderfolgende Intervalle. Bei count < 2
    # sind keine Intervalle definierbar (spiegelt stddev-Konvention bei
    # Einzel-Stichproben) - beide Zaehler (count == 0 mit days_span None,
    # count == 1 mit days_span == 0.0) sollen None liefern statt eine
    # irrefuehrende 0 (die Fall count == 1 wuerde sonst als "0 Tage
    # zwischen Backups" gelesen und ein Cron-Alarm ausloesen).
    if len(stamps) >= 2:
        average_gap_days = days_span / (len(stamps) - 1)
        # median_gap_days: ausreisser-robuste Zentraltendenz auf der
        # Frequenz-Achse. Spiegelt das median_bytes-vs-average_bytes-Paar auf
        # die Zeit-Achse: waehrend average_gap_days von einem einzelnen sehr
        # weiten Intervall verzerrt wird (Ferien-Luecke von 6 Wochen in einer
        # sonst taeglichen Rotation zieht den Durchschnitt hoch), liegt der
        # Median unverzerrt auf dem typischen Sekunden-Intervall und macht die
        # tatsaechliche Backup-Kadenz sichtbar. Reuse-Pfad: Sekunden-Diffs
        # aufeinanderfolgender sortierter Stamps, dann _median_float.
        ordered_stamps = sorted(stamps)
        gaps_days = [
            (ordered_stamps[i + 1] - ordered_stamps[i]).total_seconds() / 86400.0
            for i in range(len(ordered_stamps) - 1)
        ]
        median_gap_days = _median_float(gaps_days)
    else:
        average_gap_days = None
        median_gap_days = None
    return {
        "count": count,
        "total_bytes": total_bytes,
        "average_bytes": round(total_bytes / count) if count else None,
        "median_bytes": _median_int(sizes) if sizes else None,
        "min_bytes": min(sizes) if sizes else None,
        "max_bytes": max(sizes) if sizes else None,
        "range_bytes": (max(sizes) - min(sizes)) if sizes else None,
        "stddev_bytes": stddev,
        "variationskoeffizient_bytes_prozent": cv_prozent,
        "oldest_stamp": oldest.isoformat() if oldest else None,
        "newest_stamp": newest.isoformat() if newest else None,
        "days_span": days_span,
        "average_gap_days": average_gap_days,
        "median_gap_days": median_gap_days,
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


def _median_float(values: list[float]) -> float:
    """Median einer Zeit-/Frequenz-Liste als voller Float (keine Rundung).

    Symmetrisches Pendant zu :func:`_median_int` auf der kontinuierlichen
    Achse - waehrend Bytes diskret sind und auf Integer gerundet werden,
    ist die Zeit-Achse kontinuierlich und darf keine Sub-Tag-Aufloesung
    durch Integer-Trunkierung verlieren (spiegelt die
    ``days_span``/``average_gap_days``-Float-Konvention). Bei gerader
    Anzahl wird das arithmetische Mittel der beiden mittleren Werte
    ausgeliefert (Population-Median mit Divisor 2, konsistent zu
    :func:`_median_int` und den Median-Berechnungen in
    :mod:`stonebook.db.stats`).
    """
    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        return float(ordered[n // 2])
    return (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0


def _stddev_int(values: list[int]) -> int:
    """Populations-Standardabweichung einer Bytes-Liste, gerundet auf Integer.

    Divisor ``n`` (nicht ``n-1``) spiegelt die Backup-Halde-als-
    Grundgesamtheit-Konvention, konsistent mit den ``stddev``-
    Berechnungen in :mod:`stonebook.db.stats` (``koordinaten_radius_
    standardabweichung_km``, ``mohs_kollektion_standardabweichung`` &c).
    Numerisch stabile Formel via ``(x - mean)^2`` statt
    ``E[X^2] - E[X]^2`` - spiegelt die stddev-Berechnung in ``stats.py``
    und vermeidet Kancellations-Rundungsfehler bei Backup-Groessen im
    GiB-Bereich mit kleiner Varianz zwischen Delta-Snapshots. Rundung
    auf Integer spiegelt die :func:`backup_directory_stats.average_bytes`
    / ``median_bytes``-Konvention (Bytes-Achse ist diskret). Bei
    ``len(values) == 1`` faellt die Streuung auf ``0`` (kein
    Streuungs-Grund bei Einzel-Stichprobe, spiegelt die
    Single-Point-Kollaps-Konvention der uebrigen Volume-Achsen).
    """
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return round(variance ** 0.5)


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
