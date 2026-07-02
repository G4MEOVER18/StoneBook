"""CLI fuer JSON-Backups (schreiben, listen, inspizieren, einspielen).

Beispiele:
    python -m stonebook.export.backup_cli write   --backup-dir backups/
    python -m stonebook.export.backup_cli list    --backup-dir backups/
    python -m stonebook.export.backup_cli latest  --backup-dir backups/
    python -m stonebook.export.backup_cli oldest  --backup-dir backups/
    python -m stonebook.export.backup_cli stats   --backup-dir backups/
    python -m stonebook.export.backup_cli prune-age --backup-dir backups/ --max-age-days 30
    python -m stonebook.export.backup_cli prune-gfs --backup-dir backups/ --daily 7 --weekly 4 --monthly 12
    python -m stonebook.export.backup_cli inspect <file>
    python -m stonebook.export.backup_cli validate <file>
    python -m stonebook.export.backup_cli compare <alt> <neu>
    python -m stonebook.export.backup_cli compare-db <file>
    python -m stonebook.export.backup_cli diff-object <alt> <neu> OBJ_0001
    python -m stonebook.export.backup_cli diff-object-db <file> OBJ_0001
    python -m stonebook.export.backup_cli restore <file> --db <pfad>
    python -m stonebook.export.backup_cli restore-latest --backup-dir backups/ --db <pfad>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stonebook.db.database import connect, default_db_file, open_db
from stonebook.export.json_export import (backup_directory_stats,
                                          compare_backup_to_db, compare_backups,
                                          diff_backup_object_fields,
                                          diff_backup_to_db_object_fields,
                                          import_json, inspect_backup,
                                          latest_backup, list_backups,
                                          oldest_backup, prune_backups_by_age,
                                          prune_backups_gfs, prune_old_backups,
                                          validate_backup, write_rotated_backup)


def _cmd_write(args: argparse.Namespace) -> int:
    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return 2
    conn = connect(db_file)
    try:
        path = write_rotated_backup(
            conn, args.backup_dir,
            keep=args.keep, compress=not args.no_compress)
    finally:
        conn.close()
    print(path)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    for p in list_backups(args.backup_dir):
        print(p)
    return 0


def _cmd_latest(args: argparse.Namespace) -> int:
    """Gibt den Pfad zum juengsten Backup im Ordner aus (Filename-Stempel).

    Spiegelt :func:`_cmd_list` (alle Backups) auf den Ein-Datei-Fall:
    waehrend ``list`` alle Backup-Pfade aufsteigend druckt, druckt
    ``latest`` genau den Pfad zum juengsten Backup - das gleiche Backup,
    das :func:`_cmd_restore_latest` fuer den Auto-Restore auswaehlt. Der
    Nutzen liegt in Skript-Ketten und Cron-Reportern, die den Pfad ohne
    ``list ... | tail -n 1``-Umweg brauchen (``latest=$(python -m ... latest
    --backup-dir X)``); geeignet als Anker fuer ``inspect``/``validate``/
    ``compare-db`` auf das juengste Backup, ohne dass der Caller das
    Filename-Sortierverhalten selbst nachbauen muss. Leerer Ordner /
    nicht existierender Ordner liefern Exit 2 mit klarer Meldung auf
    stderr (spiegelt :func:`_cmd_restore_latest`), sodass die Shell-
    Kette bei fehlendem Backup nicht mit einem leeren String weiter-
    laeuft und still das falsche Ziel-Objekt erwischt.
    """
    latest = latest_backup(args.backup_dir)
    if latest is None:
        print(f"Kein Backup im Ordner: {args.backup_dir}", file=sys.stderr)
        return 2
    print(latest)
    return 0


def _cmd_oldest(args: argparse.Namespace) -> int:
    """Gibt den Pfad zum aeltesten Backup im Ordner aus (Filename-Stempel).

    Spiegelt :func:`_cmd_latest` auf den Gegen-Endpunkt der Backup-Halde:
    waehrend ``latest`` das juengste Backup liefert (typisch fuer Restore-
    Dialoge und "letztes Backup ist X Stunden alt"-Reporter), beantwortet
    ``oldest`` die naheliegende komplementaere Wartungs-Frage "wie weit
    reicht meine Halde zurueck?" in einem Schritt (statt ``list ... |
    head -n 1``). Geeignet als Anker fuer Prune-Preview ("was ist das
    aelteste Backup, das ``prune-age --max-age-days 30`` loeschen wuerde?"),
    als Sanity-Check nach Rotations-Jobs ("ist mein aeltestes Backup
    juenger als das erwartete Cutoff?") und als Startpunkt fuer historische
    Diff-Analysen (``compare $(oldest) $(latest)`` zeigt, wie sich die
    Sammlung ueber die ganze Halden-Zeitspanne entwickelt hat). Leerer
    Ordner / nicht existierender Ordner liefern Exit 2 mit klarer Meldung
    auf stderr, spiegelt :func:`_cmd_latest` exakt - der Aufrufer
    unterscheidet ohne Sonderbehandlung zwischen "leere Halde" und
    "erfolgreiche Ausgabe".
    """
    oldest = oldest_backup(args.backup_dir)
    if oldest is None:
        print(f"Kein Backup im Ordner: {args.backup_dir}", file=sys.stderr)
        return 2
    print(oldest)
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:
    deleted = prune_old_backups(args.backup_dir, keep=args.keep)
    for p in deleted:
        print(p)
    return 0


def _cmd_prune_age(args: argparse.Namespace) -> int:
    """Loescht Backups, deren Dateinamen-Stempel aelter als max_age_days ist.

    Spiegelt :func:`_cmd_prune` auf die Zeit-Achse (max_age_days statt keep).
    Beide Strategien werden in Backup-Rotations-Cron-Jobs oft kombiniert -
    eine Count-Obergrenze plus eine Age-Obergrenze garantieren das absolute
    Disk-Budget unabhaengig von der Schreibe-Frequenz.
    """
    deleted = prune_backups_by_age(args.backup_dir, max_age_days=args.max_age_days)
    for p in deleted:
        print(p)
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    """Report ueber Backup-Ordner: Anzahl, Gesamt-Bytes, aeltester/neuester Stempel.

    Spiegelt :func:`_cmd_list` (Aufzaehlung) auf die Volume-Achse:
    ``list`` liefert die einzelnen Pfade, ``stats`` fasst den Ordner
    numerisch zusammen. Geeignet fuer Cron-Reporter und Wartungs-
    Dashboards vor einer Prune-Entscheidung.
    """
    info = backup_directory_stats(args.backup_dir)
    json.dump(info, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_prune_gfs(args: argparse.Namespace) -> int:
    """Loescht Backups per Grandfather-Father-Son (Newest-per-Bucket).

    Spiegelt :func:`_cmd_prune` (Count-Achse) und :func:`_cmd_prune_age`
    (Zeit-Achse) auf die Bucket-Achse: behaelt das jeweils neueste Backup
    pro Kalendertag/-woche/-monat der letzten daily/weekly/monthly Perioden.
    Erlaubt lange Retention (12 Monate zurueck) bei begrenztem
    Festplatten-Verbrauch (max. daily+weekly+monthly Backups).
    """
    deleted = prune_backups_gfs(
        args.backup_dir,
        daily=args.daily, weekly=args.weekly, monthly=args.monthly)
    for p in deleted:
        print(p)
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    info = inspect_backup(args.path)
    json.dump(info, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Prueft die innere Konsistenz eines Backups vor dem Restore.

    Exit-Code 0 bei sauberem Backup, 1 bei gefundenen Inkonsistenzen
    (orphan FK-Verweise, doppelte obj_ids, leere IDs). Geeignet als
    Pre-Flight-Check in Restore-Scripten/Cronjobs.
    """
    info = validate_backup(args.path)
    json.dump(info, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0 if info["ok"] else 1


def _cmd_compare(args: argparse.Namespace) -> int:
    """Vergleicht zwei Backups (added/removed/modified je Tabelle).

    Geeignet als Sanity-Check vor restore: zeigt, was sich zwischen dem
    aktuell laufenden Backup (a) und einem alten/anderen Backup (b)
    aendern wuerde.
    """
    diff = compare_backups(args.a, args.b)
    json.dump(diff, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_compare_db(args: argparse.Namespace) -> int:
    """Vergleicht ein Backup gegen den aktuellen DB-Stand.

    Spiegelt :func:`_cmd_compare` (Datei vs. Datei) auf die Datei-vs-DB-
    Achse: beantwortet die Pre-Flight-Frage vor einem ``restore``, was sich
    in der laufenden DB aendern wuerde, wenn das Backup eingespielt wird -
    wieviele Objekte verloren gingen (``removed``), wieviele neu kaemen
    (``added``), wieviele veraendert wuerden (``modified``). Eignet sich
    damit als Cron-Reporter-Check oder als Bestaetigungs-Dialog vor
    ``restore --force``.

    Exit-Code 0 immer; die Diff-Zahlen sind kein Fehlerkriterium, der
    Caller entscheidet ueber die Bewertung (spiegelt :func:`_cmd_compare`).
    """
    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return 2
    conn = connect(db_file)
    try:
        diff = compare_backup_to_db(conn, args.path)
    finally:
        conn.close()
    json.dump(diff, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_diff_object(args: argparse.Namespace) -> int:
    """Feld-Diff fuer ein einzelnes Objekt zwischen zwei Backups.

    Ergaenzt :func:`_cmd_compare` (Aggregat-Counts) um die Spalten-Sicht:
    zeigt genau, welche Spalten sich in Objekt X zwischen Backup a und b
    unterscheiden. Exit-Code 0 immer (spiegelt _cmd_compare); der Status im
    JSON (``modified``/``unchanged``/``added``/``removed``/``missing``) ist
    Aufrufer-Signal.
    """
    diff = diff_backup_object_fields(args.a, args.b, args.obj_id)
    json.dump(diff, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_diff_object_db(args: argparse.Namespace) -> int:
    """Feld-Diff fuer ein einzelnes Objekt zwischen DB und Backup.

    Spiegelt :func:`_cmd_diff_object` auf die Datei-vs-DB-Achse, exakt wie
    :func:`_cmd_compare_db` die Achse zu :func:`_cmd_compare` spiegelt. DB
    nimmt die Rolle von ``a``, Backup die Rolle von ``b`` ein (Restore-
    Semantik). Fehlende DB -> Exit 2 (spiegelt write/restore/compare-db-Pfad).
    """
    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return 2
    conn = connect(db_file)
    try:
        diff = diff_backup_to_db_object_fields(conn, args.path, args.obj_id)
    finally:
        conn.close()
    json.dump(diff, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    target = args.db if args.db else default_db_file()
    if target.exists() and not args.force:
        print(f"Ziel-DB existiert: {target} (mit --force ueberschreiben)",
              file=sys.stderr)
        return 2
    if target.exists():
        target.unlink()
    conn = open_db(target)
    try:
        counts = import_json(conn, args.path, replace=True)
    finally:
        conn.close()
    json.dump(counts, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_restore_latest(args: argparse.Namespace) -> int:
    """Restauriert das juengste Backup im Ordner ohne expliziten Datei-Pfad.

    Spiegelt :func:`_cmd_restore` auf die Auto-Auswahl-Achse: waehrend
    ``restore`` einen konkreten Backup-Pfad braucht, sucht ``restore-latest``
    das neueste Backup im Ordner via :func:`latest_backup` (Filename-Stempel
    als Single-Source-of-Truth, spiegelt ``prune_backups_by_age``). Der
    Restore-Pfad selbst ist identisch (Target-DB muss leer sein oder
    ``--force`` gesetzt sein; ``INSERT OR REPLACE``; atomische Transaktion
    ueber ``import_json``). Geeignet als Standard-Wiederherstellungs-
    Befehl in Cron-Recovery-Scripten und Restore-Dialogen, die dem User
    das juengste Backup vorschlagen, ohne dass er den Datei-Pfad tippen
    muss.

    Der ausgewaehlte Pfad wird auf stderr geschrieben (informativer
    Hinweis, wie ``write`` seinen Pfad auf stdout schreibt); die
    JSON-Counts kommen auf stdout (spiegelt ``restore`` exakt, sodass
    Downstream-Auswerter das gleiche Ausgabeformat verarbeiten). Bei
    leerem Ordner (kein Backup vorhanden) wird auf stderr eine Meldung
    geschrieben und Exit-Code 2 zurueckgegeben (spiegelt ``restore`` mit
    fehlender Datei), damit der Aufrufer den Fehler klar von einem
    erfolgreichen Restore unterscheiden kann.
    """
    latest = latest_backup(args.backup_dir)
    if latest is None:
        print(f"Kein Backup im Ordner: {args.backup_dir}", file=sys.stderr)
        return 2
    target = args.db if args.db else default_db_file()
    if target.exists() and not args.force:
        print(f"Ziel-DB existiert: {target} (mit --force ueberschreiben)",
              file=sys.stderr)
        return 2
    if target.exists():
        target.unlink()
    print(f"Restore aus: {latest}", file=sys.stderr)
    conn = open_db(target)
    try:
        counts = import_json(conn, latest, replace=True)
    finally:
        conn.close()
    json.dump(counts, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m stonebook.export.backup_cli",
        description="StoneBook JSON-Backup verwalten.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("write", help="Vollbackup mit Rotation schreiben.")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--keep", type=int, default=10)
    sp.add_argument("--no-compress", action="store_true",
                    help="Schreibt unkomprimiertes .json statt .json.gz.")
    sp.set_defaults(func=_cmd_write)

    sp = sub.add_parser("list", help="Vorhandene Backups auflisten.")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.set_defaults(func=_cmd_list)

    sp = sub.add_parser(
        "latest",
        help="Pfad zum juengsten Backup drucken (Filename-Stempel); "
             "Exit 2 bei leerer/fehlender Halde.")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.set_defaults(func=_cmd_latest)

    sp = sub.add_parser(
        "oldest",
        help="Pfad zum aeltesten Backup drucken (Filename-Stempel); "
             "Exit 2 bei leerer/fehlender Halde.")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.set_defaults(func=_cmd_oldest)

    sp = sub.add_parser(
        "stats",
        help="Backup-Ordner zusammenfassen (Anzahl, Gesamt-Bytes, "
             "aeltester/neuester Stempel) als JSON-Report.")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.set_defaults(func=_cmd_stats)

    sp = sub.add_parser("prune", help="Alte Backups loeschen (nur ``keep`` neueste bleiben).")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.add_argument("--keep", type=int, required=True)
    sp.set_defaults(func=_cmd_prune)

    sp = sub.add_parser(
        "prune-age",
        help="Backups loeschen, deren Dateinamen-Stempel aelter als "
             "max_age_days ist (Zeit-Achse statt Count-Achse).")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.add_argument("--max-age-days", type=int, required=True,
                    help="Hoechst-Alter in Tagen; aeltere Backups werden geloescht.")
    sp.set_defaults(func=_cmd_prune_age)

    sp = sub.add_parser(
        "prune-gfs",
        help="Grandfather-Father-Son-Rotation: neuestes Backup pro Tag/"
             "Woche/Monat der letzten N Perioden behalten (Bucket-Achse).")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.add_argument("--daily", type=int, default=7,
                    help="Anzahl Kalendertage (Default 7).")
    sp.add_argument("--weekly", type=int, default=4,
                    help="Anzahl ISO-Kalenderwochen (Default 4).")
    sp.add_argument("--monthly", type=int, default=12,
                    help="Anzahl Kalendermonate (Default 12).")
    sp.set_defaults(func=_cmd_prune_gfs)

    sp = sub.add_parser("inspect", help="Backup-Inhalt anzeigen (counts + meta).")
    sp.add_argument("path", type=Path)
    sp.set_defaults(func=_cmd_inspect)

    sp = sub.add_parser(
        "validate",
        help="Innere Konsistenz pruefen (orphan FK, doppelte IDs); Exit 1 bei Fehlern.")
    sp.add_argument("path", type=Path)
    sp.set_defaults(func=_cmd_validate)

    sp = sub.add_parser(
        "compare",
        help="Zwei Backups vergleichen (added/removed/modified je Tabelle).")
    sp.add_argument("a", type=Path, help="Erstes Backup (Basis).")
    sp.add_argument("b", type=Path, help="Zweites Backup (Vergleichs-Ziel).")
    sp.set_defaults(func=_cmd_compare)

    sp = sub.add_parser(
        "compare-db",
        help="Backup gegen den aktuellen DB-Stand vergleichen "
             "(Pre-Flight-Check vor restore).")
    sp.add_argument("path", type=Path, help="Backup-Datei.")
    sp.add_argument("--db", type=Path, default=None,
                    help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3).")
    sp.set_defaults(func=_cmd_compare_db)

    sp = sub.add_parser(
        "diff-object",
        help="Feld-Diff fuer ein einzelnes Objekt zwischen zwei Backups.")
    sp.add_argument("a", type=Path, help="Erstes Backup (Basis).")
    sp.add_argument("b", type=Path, help="Zweites Backup (Vergleichs-Ziel).")
    sp.add_argument("obj_id", type=str, help="Objekt-ID (z.B. OBJ_0001).")
    sp.set_defaults(func=_cmd_diff_object)

    sp = sub.add_parser(
        "diff-object-db",
        help="Feld-Diff fuer ein einzelnes Objekt zwischen DB und Backup "
             "(Pre-Flight-Detail vor restore).")
    sp.add_argument("path", type=Path, help="Backup-Datei.")
    sp.add_argument("obj_id", type=str, help="Objekt-ID (z.B. OBJ_0001).")
    sp.add_argument("--db", type=Path, default=None,
                    help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3).")
    sp.set_defaults(func=_cmd_diff_object_db)

    sp = sub.add_parser("restore", help="Backup in eine DB einspielen.")
    sp.add_argument("path", type=Path)
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--force", action="store_true",
                    help="Ziel-DB ueberschreiben, falls vorhanden.")
    sp.set_defaults(func=_cmd_restore)

    sp = sub.add_parser(
        "restore-latest",
        help="Juengstes Backup im Ordner in eine DB einspielen "
             "(Auto-Auswahl ueber Filename-Stempel).")
    sp.add_argument("--backup-dir", type=Path, required=True)
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--force", action="store_true",
                    help="Ziel-DB ueberschreiben, falls vorhanden.")
    sp.set_defaults(func=_cmd_restore_latest)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
