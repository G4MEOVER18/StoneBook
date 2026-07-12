"""CLI fuer den DOCX-Analysebericht-Export (einzel/Stapel).

Beispiele:
    python -m stonebook.export.docx_cli OBJ_0001 OBJ_0043 --out-dir berichte/
    python -m stonebook.export.docx_cli --status aktiv --out-dir berichte/
    python -m stonebook.export.docx_cli --all --out-dir berichte/
    python -m stonebook.export.docx_cli --ids-from-file liste.txt --out-dir berichte/
    python -m stonebook.export.docx_cli --all --dry-run
    python -m stonebook.export.docx_cli OBJ_0043     # ohne --out-dir: objects/<id>/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stonebook.db.database import connect, default_db_file
from stonebook.export.docx_export import export_docx_batch
from stonebook.migration.id_utils import normalize_id, read_ids_from_file


def _collect_obj_ids(conn, args: argparse.Namespace) -> list[str]:
    """Stellt die zu exportierende Liste zusammen (manuell ODER --status ODER --all).

    Positionale IDs und ``--ids-from-file`` werden zusammengefuehrt (Datei zuerst,
    dann positional), Duplikate reihenfolge-erhaltend entfernt. ``--all`` und
    ``--status`` gewinnen weiter gegenueber der ID-Liste.
    """
    if args.all:
        return [r[0] for r in conn.execute(
            "SELECT obj_id FROM objects ORDER BY obj_id").fetchall()]
    if args.status:
        return [r[0] for r in conn.execute(
            "SELECT obj_id FROM objects WHERE status = ? ORDER BY obj_id",
            (args.status,)).fetchall()]
    raw_ids: list[str] = []
    if args.ids_from_file is not None:
        file_ids = read_ids_from_file(args.ids_from_file)
        if file_ids is None:
            print(f"ID-Datei nicht lesbar: {args.ids_from_file}", file=sys.stderr)
            return []
        raw_ids.extend(file_ids)
    raw_ids.extend(args.obj_ids)
    ids: list[str] = []
    seen: set[str] = set()
    for raw in raw_ids:
        norm = normalize_id(raw)
        if norm is None:
            print(f"Ungueltige Objekt-ID: {raw!r}", file=sys.stderr)
            return []
        if norm in seen:
            continue
        seen.add(norm)
        ids.append(norm)
    return ids


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m stonebook.export.docx_cli",
        description="DOCX-Analyseberichte fuer ein oder mehrere Objekte erzeugen.",
    )
    p.add_argument("obj_ids", nargs="*",
                   help="Objekt-IDs (OBJ_0001, OBJ-1, 'Objekt 1', '1' ...). "
                        "Leer lassen, wenn --status / --all / --ids-from-file gesetzt ist.")
    p.add_argument("--db", type=Path, default=None,
                   help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3).")
    p.add_argument("--root", type=Path, default=None,
                   help="Repo-Root mit objects/ und data/ (Default: aus --db abgeleitet).")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="Zielordner fuer alle Berichte. Ohne --out-dir landet jeder Bericht "
                        "unter objects/<obj_id>/ wie beim Einzelexport.")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true",
                       help="Alle Objekte exportieren.")
    group.add_argument("--status", default=None,
                       help="Nur Objekte mit diesem Lebenszyklus-Status (z.B. 'aktiv').")
    p.add_argument("--ids-from-file", type=Path, default=None, metavar="PATH",
                   help="Textdatei mit einer Objekt-ID pro Zeile ('#'-Kommentare "
                        "und Leerzeilen erlaubt). Wird mit positionalen IDs "
                        "vereinigt (Datei zuerst); von --all/--status ueberschrieben.")
    p.add_argument("--dry-run", action="store_true",
                   help="Nur die ausgewaehlten IDs auf stdout ausgeben, keine "
                        "DOCX-Dateien schreiben.")
    p.add_argument("--continue-on-error", action="store_true",
                   help="Bei Einzelfehlern weiterfahren statt abzubrechen.")
    p.add_argument("--quiet", action="store_true",
                   help="Keine pro-Objekt-Zeile auf stdout.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if (not args.obj_ids and not args.all and not args.status
            and args.ids_from_file is None):
        print("Bitte Objekt-IDs angeben oder --status / --all / --ids-from-file setzen.",
              file=sys.stderr)
        return 2

    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return 2
    root = args.root if args.root else db_file.parent.parent.parent
    if not (root / "objects").is_dir():
        print(f"Repo-Root ohne objects/-Ordner: {root}", file=sys.stderr)
        return 2

    conn = connect(db_file)
    try:
        obj_ids = _collect_obj_ids(conn, args)
        if not obj_ids:
            # Fehlermeldung wurde bereits in _collect_obj_ids ausgegeben, oder
            # die Selektion lieferte keine Treffer.
            return 2

        if args.dry_run:
            # Nur die ausgewaehlten IDs auflisten; keine Datei-I/O. Auch mit
            # --quiet werden die IDs geschrieben, weil sie das primaere
            # Ergebnis eines Dry-Runs sind - --quiet unterdrueckt lediglich
            # die Zusammenfassungs-Zeile am Ende.
            for oid in obj_ids:
                print(oid)
            if not args.quiet:
                print(f"Dry-Run: {len(obj_ids)} Objekte (keine Dateien geschrieben)")
            return 0

        errors: list[tuple[str, str]] = []

        def _on_error(obj_id: str, exc: BaseException) -> None:
            errors.append((obj_id, str(exc)))
            print(f"FEHLER {obj_id}: {exc}", file=sys.stderr)

        def _progress(done: int, total: int, obj_id: str) -> None:
            if not args.quiet:
                print(f"[{done}/{total}] {obj_id}")

        written = export_docx_batch(
            conn, root, obj_ids,
            out_dir=args.out_dir,
            progress=_progress,
            continue_on_error=args.continue_on_error,
            on_error=_on_error,
        )
    finally:
        conn.close()

    if not args.quiet:
        print(f"Geschrieben: {len(written)} / {len(obj_ids)} "
              f"({len(errors)} Fehler)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
