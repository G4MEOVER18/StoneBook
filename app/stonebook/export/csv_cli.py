"""CLI fuer den CSV-Export/-Import (Standard-Schema, 43 Felder + status/notizen).

Beispiele:
    python -m stonebook.export.csv_cli export OBJ_0001 OBJ_0043 --out export.csv
    python -m stonebook.export.csv_cli export --status aktiv --out aktiv.csv
    python -m stonebook.export.csv_cli export --all --out voll.csv
    python -m stonebook.export.csv_cli export --ids-from-file liste.txt --out sel.csv
    python -m stonebook.export.csv_cli import import.csv
    python -m stonebook.export.csv_cli import import.csv --merge-only
    python -m stonebook.export.csv_cli import import.csv --no-create-missing
    python -m stonebook.export.csv_cli import import.csv --dry-run

Ergaenzt :mod:`stonebook.export.docx_cli` und :mod:`stonebook.export.backup_cli`
um die noch fehlende CSV-Verwaltung auf der Kommandozeile.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stonebook.db.database import connect, default_db_file, open_db
from stonebook.export.csv_export import export_csv, import_csv
from stonebook.migration.id_utils import normalize_id, read_ids_from_file


# Sentinel fuer "ID-Datei fehlt/nicht lesbar" - unterscheidet sich vom leeren
# Wahl-Ergebnis (leere Datei ohne Kommentare = 0 IDs = ebenfalls Fehler, aber
# aus anderer Ursache) und vom "kein Filter"-None. Der Aufrufer prueft auf
# Identity und beendet mit exit 2, nachdem die stderr-Meldung schon geflossen
# ist.
_IDS_ERROR = object()


def _collect_obj_ids(conn, args: argparse.Namespace) -> list[str] | None | object:
    """Stellt die zu exportierende ID-Liste zusammen oder ``None`` (= alle).

    Spiegelt :func:`stonebook.export.docx_cli._collect_obj_ids`: Bei ``--all``
    wird ``None`` zurueckgegeben (entspricht dem ``obj_ids=None``-Default von
    :func:`export_csv` = kein Filter, alle Objekte). ``--status`` wird vom
    Caller separat verwendet; positionale IDs und die per
    ``--ids-from-file`` eingelesene Liste werden vereinigt (Datei zuerst,
    dann positional) und reihenfolge-erhaltend dedupliziert, spiegelt
    :func:`stonebook.export.docx_cli._collect_obj_ids`. Bei Ungueltigkeit
    einer ID / nicht lesbarer Datei wird der Sentinel ``_IDS_ERROR``
    zurueckgegeben (Fehlermeldung auf stderr, exit 2 im Aufrufer).
    """
    if args.all:
        return None
    if not args.obj_ids and args.ids_from_file is None:
        return None
    raw_ids: list[str] = []
    if args.ids_from_file is not None:
        file_ids = read_ids_from_file(args.ids_from_file)
        if file_ids is None:
            print(f"ID-Datei nicht lesbar: {args.ids_from_file}", file=sys.stderr)
            return _IDS_ERROR
        raw_ids.extend(file_ids)
    raw_ids.extend(args.obj_ids)
    ids: list[str] = []
    seen: set[str] = set()
    for raw in raw_ids:
        norm = normalize_id(raw)
        if norm is None:
            print(f"Ungueltige Objekt-ID: {raw!r}", file=sys.stderr)
            return _IDS_ERROR
        if norm in seen:
            continue
        seen.add(norm)
        ids.append(norm)
    return ids


def _cmd_export(args: argparse.Namespace) -> int:
    db_file = args.db if args.db else default_db_file()
    if not db_file.is_file():
        print(f"DB-Datei fehlt: {db_file}", file=sys.stderr)
        return 2
    conn = connect(db_file)
    try:
        obj_ids = _collect_obj_ids(conn, args)
        if obj_ids is _IDS_ERROR:
            return 2
        n = export_csv(conn, args.out, obj_ids=obj_ids, status=args.status)
    finally:
        conn.close()
    if not args.quiet:
        print(f"Geschrieben: {n} Objekte -> {args.out}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    if not args.path.is_file():
        print(f"CSV-Datei fehlt: {args.path}", file=sys.stderr)
        return 2
    db_file = args.db if args.db else default_db_file()
    # Beim Import ist es legitim, eine frische DB anzulegen, wenn das Ziel
    # noch leer ist - open_db ruft init_db auf. Bei vorhandener DB wird
    # connect verwendet (kein Schema-Re-Init noetig). Bei --dry-run wird die
    # bestehende DB read-only inspiziert und nicht mutiert; existiert die DB
    # noch nicht, verweigert der Dry-Run das Anlegen einer leeren Schema-DB
    # (das waere eine sichtbare Nebenwirkung entgegen der Zusage "nichts
    # veraendern") und meldet stattdessen als Fehler.
    if db_file.is_file():
        conn = connect(db_file)
    elif args.dry_run:
        print(f"DB-Datei fehlt: {db_file} (Dry-Run legt keine leere DB an)",
              file=sys.stderr)
        return 2
    else:
        conn = open_db(db_file)
    try:
        rep = import_csv(
            conn, args.path,
            create_missing=not args.no_create_missing,
            merge_only=args.merge_only,
            dry_run=args.dry_run,
        )
    finally:
        conn.close()
    if args.json:
        json.dump(rep.as_dict(), sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    elif not args.quiet:
        if args.dry_run:
            print("Dry-Run: keine DB-Aenderung, folgende Wirkung waere eingetreten:")
        print(f"Angelegt: {len(rep.angelegt)}")
        print(f"Aktualisiert: {len(rep.aktualisiert)}")
        print(f"Uebersprungen: {len(rep.uebersprungen)}")
        if rep.konflikte:
            print(f"Konflikte (merge-only): {len(rep.konflikte)} Objekte")
        if rep.duplikate:
            # Doppelte IDs in derselben CSV: die spaetere Zeile hat die
            # fruehere ueberschrieben (load_standard-dict-Semantik), ohne
            # diesen Hinweis waere der Datenverlust unsichtbar.
            print(f"Doppelte IDs in Quelle: {len(rep.duplikate)} "
                  f"(letzte Zeile gewinnt)")
        if rep.zeilen_ohne_id:
            # Zeilen ohne verwertbare ID werden von load_standard kommentarlos
            # verworfen - hier explizit sichtbar machen, symmetrisch zum
            # Duplikat-Hinweis. Zeilennummern sind 1-basiert ueber die
            # Datenzeilen (Header zaehlt nicht).
            print(f"Zeilen ohne ID: {len(rep.zeilen_ohne_id)} "
                  f"(verworfen; Zeilen {', '.join(map(str, rep.zeilen_ohne_id))})")
        if rep.funddatum_invalid:
            # Nicht parsbare Funddatum-Werte werden von _convert_standard
            # silent gedroppt (die Zeile bleibt, das Feld fehlt) - hier
            # explizit sichtbar machen mit Roh-Wert, damit der User den
            # Tippfehler direkt findet. Symmetrisch zum ID-Silent-Drop-Hinweis.
            details = ", ".join(
                f"Zeile {n}: {raw!r}" for n, raw in rep.funddatum_invalid)
            print(f"Ungueltige Funddatum-Werte: {len(rep.funddatum_invalid)} "
                  f"(Feld verworfen; {details})")
        if rep.numeric_invalid:
            # Silent-Drop-Pendant auf der numerischen Achse: alle
            # float/int/scale-Felder buendeln in einem Report-Eintrag,
            # damit der User Zeile + Spalte + Roh-Wert in einem Zug sieht
            # (``Zeile 5 Gewicht_g: 'sehr schwer'``). Reihenfolge = Zeile-
            # primaer, Spalte-sekundaer entlang der Header-Reihenfolge des
            # Files - spiegelt find_rows_with_invalid_numeric_fields.
            details = ", ".join(
                f"Zeile {n} {col}: {raw!r}"
                for n, col, raw in rep.numeric_invalid)
            print(f"Ungueltige numerische Werte: {len(rep.numeric_invalid)} "
                  f"(Feld verworfen; {details})")
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m stonebook.export.csv_cli",
        description="CSV-Export/-Import fuer StoneBook (Standard-Schema).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser(
        "export", help="Objekte als CSV exportieren (Excel-tauglich, BOM + UTF-8).")
    sp.add_argument("obj_ids", nargs="*",
                    help="Objekt-IDs (OBJ_0001, '1', 'Objekt 1' ...). Leer "
                         "lassen und --all oder --status fuer Sammelexport.")
    sp.add_argument("--out", type=Path, required=True,
                    help="Ziel-CSV.")
    sp.add_argument("--db", type=Path, default=None,
                    help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3).")
    group = sp.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true",
                       help="Alle Objekte exportieren (Default ohne IDs).")
    group.add_argument("--status", default=None,
                       help="Nur Objekte mit diesem Lebenszyklus-Status (z.B. 'aktiv').")
    sp.add_argument("--ids-from-file", type=Path, default=None, metavar="PATH",
                    help="Textdatei mit einer Objekt-ID pro Zeile ('#'-Kommentare "
                         "und Leerzeilen erlaubt). Wird mit positionalen IDs "
                         "vereinigt (Datei zuerst); von --all/--status ueberschrieben. "
                         "Spiegelt --ids-from-file von docx_cli.")
    sp.add_argument("--quiet", action="store_true",
                    help="Keine Status-Zeile auf stdout.")
    sp.set_defaults(func=_cmd_export)

    sp = sub.add_parser(
        "import", help="CSV in die DB einspielen (Upsert oder merge-only).")
    sp.add_argument("path", type=Path,
                    help="Quell-CSV im export_csv-Schema (ID/obj_id + Feldspalten).")
    sp.add_argument("--db", type=Path, default=None,
                    help="Pfad zur SQLite-DB (Default: <repo>/data/db/stonebook.sqlite3). "
                         "Falls die DB noch nicht existiert, wird sie angelegt.")
    sp.add_argument("--merge-only", action="store_true",
                    help="Bestehende Werte NICHT ueberschreiben (nur leere Felder fuellen, "
                         "Konflikte werden gemeldet).")
    sp.add_argument("--no-create-missing", action="store_true",
                    help="Unbekannte obj_ids ueberspringen statt anlegen.")
    sp.add_argument("--dry-run", action="store_true",
                    help="Nur vorhersagen, was passieren wuerde: keine "
                         "INSERT/UPDATE, keine Statusaktualisierung. Zeigt "
                         "trotzdem den vollstaendigen Import-Report "
                         "(angelegt/aktualisiert/uebersprungen/konflikte/"
                         "Silent-Drop-Warnungen).")
    sp.add_argument("--json", action="store_true",
                    help="Report als JSON auf stdout (mit angelegt/aktualisiert/"
                         "uebersprungen/konflikte).")
    sp.add_argument("--quiet", action="store_true",
                    help="Keine Status-Zeile auf stdout (ueberschrieben von --json).")
    sp.set_defaults(func=_cmd_import)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
