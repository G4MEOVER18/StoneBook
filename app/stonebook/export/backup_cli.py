"""CLI fuer JSON-Backups (schreiben, listen, inspizieren, einspielen).

Beispiele:
    python -m stonebook.export.backup_cli write   --backup-dir backups/
    python -m stonebook.export.backup_cli list    --backup-dir backups/
    python -m stonebook.export.backup_cli prune-age --backup-dir backups/ --max-age-days 30
    python -m stonebook.export.backup_cli inspect <file>
    python -m stonebook.export.backup_cli validate <file>
    python -m stonebook.export.backup_cli compare <alt> <neu>
    python -m stonebook.export.backup_cli restore <file> --db <pfad>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stonebook.db.database import connect, default_db_file, open_db
from stonebook.export.json_export import (compare_backups, import_json,
                                          inspect_backup, list_backups,
                                          prune_backups_by_age,
                                          prune_old_backups, validate_backup,
                                          write_rotated_backup)


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

    sp = sub.add_parser("restore", help="Backup in eine DB einspielen.")
    sp.add_argument("path", type=Path)
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--force", action="store_true",
                    help="Ziel-DB ueberschreiben, falls vorhanden.")
    sp.set_defaults(func=_cmd_restore)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
