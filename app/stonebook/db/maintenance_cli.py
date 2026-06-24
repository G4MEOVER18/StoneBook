"""CLI fuer DB-Wartung (VACUUM, quick_check, deep_check, foreign_key_check, Groessenmessung).

Beispiele:
    python -m stonebook.db.maintenance_cli size                     # Default-DB
    python -m stonebook.db.maintenance_cli size --db <pfad>
    python -m stonebook.db.maintenance_cli check                    # quick_check
    python -m stonebook.db.maintenance_cli deepcheck                # integrity_check (voll)
    python -m stonebook.db.maintenance_cli fkcheck                  # foreign_key_check
    python -m stonebook.db.maintenance_cli dupimg                   # Bild-Dubletten (SHA-256)
    python -m stonebook.db.maintenance_cli vacuum                   # VACUUM
    python -m stonebook.db.maintenance_cli vacuum --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stonebook.db.database import connect, default_db_file
from stonebook.db.integrity import find_duplicate_image_sha256
from stonebook.db.maintenance import (database_size_bytes, db_file_bytes,
                                      deep_check, foreign_key_check,
                                      free_page_count, quick_check, vacuum)


def _resolve_db(args: argparse.Namespace) -> Path | None:
    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return None
    return db_file


def _cmd_size(args: argparse.Namespace) -> int:
    db_file = _resolve_db(args)
    if db_file is None:
        return 2
    conn = connect(db_file)
    try:
        info = {
            "db_file": str(db_file),
            "logical_bytes": database_size_bytes(conn),
            "file_bytes": db_file_bytes(db_file),
            "free_pages": free_page_count(conn),
        }
    finally:
        conn.close()
    if args.json:
        json.dump(info, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        print(f"DB:                {info['db_file']}")
        print(f"Logisch:           {info['logical_bytes']:,} Bytes")
        print(f"Datei (mit WAL):   {info['file_bytes']:,} Bytes")
        print(f"Free-Pages:        {info['free_pages']}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    db_file = _resolve_db(args)
    if db_file is None:
        return 2
    conn = connect(db_file)
    try:
        messages = quick_check(conn)
    finally:
        conn.close()
    if args.json:
        json.dump({"ok": not messages, "messages": messages},
                  sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    elif messages:
        print("FEHLER: SQLite quick_check meldet Probleme:")
        for m in messages:
            print(f"  - {m}")
    else:
        print("OK: SQLite quick_check ohne Befund.")
    # Exit-Code 1 bei Korruption, 0 wenn sauber - geeignet fuer Cron/CI.
    return 0 if not messages else 1


def _cmd_deepcheck(args: argparse.Namespace) -> int:
    db_file = _resolve_db(args)
    if db_file is None:
        return 2
    conn = connect(db_file)
    try:
        messages = deep_check(conn)
    finally:
        conn.close()
    # Spiegelt _cmd_check exakt (gleiche Output-/Exit-Konvention); deep_check
    # ist die Voll-Variante des SQLite-Selbstchecks.
    if args.json:
        json.dump({"ok": not messages, "messages": messages},
                  sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    elif messages:
        print("FEHLER: SQLite integrity_check meldet Probleme:")
        for m in messages:
            print(f"  - {m}")
    else:
        print("OK: SQLite integrity_check ohne Befund.")
    return 0 if not messages else 1


def _cmd_fkcheck(args: argparse.Namespace) -> int:
    db_file = _resolve_db(args)
    if db_file is None:
        return 2
    conn = connect(db_file)
    try:
        violations = foreign_key_check(conn)
    finally:
        conn.close()
    # Tuples (table, rowid, parent_table, fkid) - dict-Form fuer JSON / Print.
    items = [
        {"table": t, "rowid": r, "parent_table": p, "fkid": f}
        for t, r, p, f in violations
    ]
    if args.json:
        json.dump({"ok": not items, "violations": items},
                  sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    elif items:
        print(f"FEHLER: PRAGMA foreign_key_check meldet {len(items)} Verletzung(en):")
        for v in items:
            print(f"  - {v['table']} rowid={v['rowid']} → {v['parent_table']} (fkid={v['fkid']})")
    else:
        print("OK: PRAGMA foreign_key_check ohne Befund.")
    # Spiegelt _cmd_check: Exit-Code 1 bei FK-Verletzung, 0 wenn sauber.
    return 0 if not items else 1


def _cmd_dupimg(args: argparse.Namespace) -> int:
    """Listet Bild-Dubletten (gleicher SHA-256-Hash mehrfach in der image-Tabelle).

    Spiegelt :func:`_cmd_fkcheck` auf die diagnostische Achse: das Pendant in
    der Datenmodell-Bibliothek (:func:`stonebook.db.integrity.find_duplicate_image_sha256`)
    findet Mehrfach-Speicherung desselben Bildinhalts unter verschiedenen
    Bildeintraegen, ist aber bisher CLI-seitig nicht erreichbar gewesen -
    nur ueber das Python-API oder den GUI-Pfad. Dubletten sind nicht zwingend
    ein Fehler (z.B. dasselbe Foto legitim als Uebersicht UND Kamera abgelegt
    sein - der Sammler will beide Eintraege), daher liefern wir Exit-Code 0
    auch wenn Treffer gefunden werden; der Caller entscheidet ueber die
    Bewertung. NULL-/Leerwerte beim SHA-256-Feld werden vom Bibliotheks-
    Aufruf bereits ignoriert. Output spiegelt _cmd_fkcheck (text- und JSON-
    Variante) auf die Hash-/Image-Achse: Hash + sortierte ID-Liste pro Gruppe.
    """
    db_file = _resolve_db(args)
    if db_file is None:
        return 2
    conn = connect(db_file)
    try:
        groups = find_duplicate_image_sha256(conn)
    finally:
        conn.close()
    items = [{"sha256": sha, "image_ids": ids} for sha, ids in groups]
    if args.json:
        json.dump({"groups": items}, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    elif items:
        total = sum(len(g["image_ids"]) for g in items)
        print(f"{len(items)} Dubletten-Gruppe(n) ({total} betroffene Bilder):")
        for g in items:
            ids = ", ".join(str(i) for i in g["image_ids"])
            print(f"  - {g['sha256']}: {len(g['image_ids'])} Bilder [{ids}]")
    else:
        print("OK: keine Bild-Dubletten (SHA-256) gefunden.")
    return 0


def _cmd_vacuum(args: argparse.Namespace) -> int:
    db_file = _resolve_db(args)
    if db_file is None:
        return 2
    conn = connect(db_file)
    try:
        before, after = vacuum(conn)
    finally:
        conn.close()
    saved = before - after
    info = {
        "before_bytes": before,
        "after_bytes": after,
        "saved_bytes": saved,
    }
    if args.json:
        json.dump(info, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        print(f"VACUUM abgeschlossen: {before:,} → {after:,} Bytes "
              f"({saved:+,} Bytes)")
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m stonebook.db.maintenance_cli",
        description="DB-Wartung: VACUUM, quick_check, Groessenmessung.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("size", help="Aktuelle DB-Groesse + Free-Pages anzeigen.")
    sp.add_argument("--db", type=Path, default=None,
                    help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3).")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_size)

    sp = sub.add_parser("check", help="SQLite quick_check ausfuehren.")
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_check)

    sp = sub.add_parser("deepcheck",
                        help="SQLite integrity_check (Voll-Variante) ausfuehren "
                             "- prueft Indexe, UNIQUE/NOT-NULL gegen Basistabellen.")
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_deepcheck)

    sp = sub.add_parser("fkcheck",
                        help="SQLite foreign_key_check ausfuehren "
                             "(erkennt orphans und referentielle Luecken).")
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_fkcheck)

    sp = sub.add_parser("dupimg",
                        help="Bild-Dubletten anhand SHA-256 anzeigen "
                             "(gleicher Bildinhalt mehrfach in image-Tabelle).")
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_dupimg)

    sp = sub.add_parser("vacuum", help="Datenbank kompaktieren (VACUUM).")
    sp.add_argument("--db", type=Path, default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_vacuum)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
