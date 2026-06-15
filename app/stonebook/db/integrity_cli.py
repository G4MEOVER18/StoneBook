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


_TEXT_EXAMPLE_LIMIT = 3


def _format_example(item) -> str:
    """Formatiert einen Listeneintrag der Integrity-Listen kompakt fuer die Text-Ausgabe.

    Tuples (z.B. ``(obj_id, feld, wert)`` aus ``numeric_out_of_range``) werden
    Doppelpunkt-getrennt zusammengezogen; reine IDs/Strings bleiben unveraendert.
    """
    if isinstance(item, (list, tuple)):
        return ":".join(str(p) for p in item)
    return str(item)


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
            # Erste paar Beispiele anhaengen, damit man direkt sieht, welche IDs
            # konkret betroffen sind (statt "es gibt 7 Konflikte, viel Spass beim
            # Suchen"). Bei kleinen Mengen alles, sonst ``+N more``.
            examples = ", ".join(_format_example(v) for v in value[:_TEXT_EXAMPLE_LIMIT])
            rest = count - _TEXT_EXAMPLE_LIMIT
            suffix = f" (+{rest} weitere)" if rest > 0 else ""
            lines.append(f"  - {key}: {count} [{examples}{suffix}]")
        else:
            lines.append(f"  - {key}: 1")
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
