"""CLI fuer die Konsistenzpruefung der StoneBook-DB.

Beispiele:
    python -m stonebook.db.integrity_cli                       # Default-DB
    python -m stonebook.db.integrity_cli --db <pfad>           # eigene DB
    python -m stonebook.db.integrity_cli --json                # JSON-Ausgabe
    python -m stonebook.db.integrity_cli --check-files --root <repo>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stonebook.db.database import connect, default_db_file
from stonebook.db.integrity import IntegrityReport, check_integrity


def _format_text(report: IntegrityReport) -> str:
    if report.is_clean:
        return "OK: keine Inkonsistenzen gefunden."
    lines = ["FEHLER: Inkonsistenzen gefunden:"]
    d = report.as_dict()
    for key, value in d.items():
        if key == "is_clean":
            continue
        if not value:
            continue
        if isinstance(value, list):
            count = len(value)
        else:
            count = 1
        lines.append(f"  - {key}: {count}")
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m stonebook.db.integrity_cli",
        description="Prueft die StoneBook-DB auf Inkonsistenzen.",
    )
    p.add_argument("--db", type=Path, default=None,
                   help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3).")
    p.add_argument("--root", type=Path, default=None,
                   help="Repo-Root fuer --check-files (Pfad mit objects/).")
    p.add_argument("--check-files", action="store_true",
                   help="Prueft zusaetzlich, ob alle in images.rel_path referenzierten "
                        "Dateien existieren.")
    p.add_argument("--json", action="store_true",
                   help="JSON-Bericht auf stdout statt menschenlesbarem Text.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return 2
    conn = connect(db_file)
    try:
        report = check_integrity(
            conn, root=args.root, check_files=bool(args.check_files))
    finally:
        conn.close()
    if args.json:
        json.dump(report.as_dict(), sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        print(_format_text(report))
    return 0 if report.is_clean else 1


if __name__ == "__main__":
    sys.exit(main())
