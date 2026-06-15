"""CLI fuer JSON-Backups (schreiben, listen, inspizieren, einspielen).

Beispiele:
    python -m stonebook.export.backup_cli write   --backup-dir backups/
    python -m stonebook.export.backup_cli list    --backup-dir backups/
    python -m stonebook.export.backup_cli inspect <file>
    python -m stonebook.export.backup_cli restore <file> --db <pfad>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stonebook.db.database import connect, open_db
from stonebook.export.json_export import (import_json, inspect_backup,
                                          list_backups, prune_old_backups,
                                          write_rotated_backup)


def _default_db_file() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "db" / "stonebook.sqlite3"


def _cmd_write(args: argparse.Namespace) -> int:
    db_file = args.db if args.db else _default_db_file()
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


def _cmd_inspect(args: argparse.Namespace) -> int:
    info = inspect_backup(args.path)
    json.dump(info, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    target = args.db if args.db else _default_db_file()
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

    sp = sub.add_parser("inspect", help="Backup-Inhalt anzeigen (counts + meta).")
    sp.add_argument("path", type=Path)
    sp.set_defaults(func=_cmd_inspect)

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
