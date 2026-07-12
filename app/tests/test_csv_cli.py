"""CLI fuer den CSV-Export/-Import."""
import csv
import json
from pathlib import Path

import pytest

from stonebook.export.csv_cli import main
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_export_all_default_ohne_ids(migrated_db, tmp_path, capsys):
    """Ohne IDs/--all/--status wird die gesamte DB exportiert."""
    out = tmp_path / "voll.csv"
    code = main(["export", "--out", str(out), "--db", str(migrated_db)])
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) == 546
    captured = capsys.readouterr().out
    assert "546" in captured and str(out) in captured


def test_export_explizite_obj_ids(migrated_db, tmp_path, capsys):
    out = tmp_path / "sel.csv"
    code = main(["export", "OBJ_0001", "OBJ_0043",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert {r["ID"] for r in rows} == {"OBJ_0001", "OBJ_0043"}
    # --quiet unterdrueckt die Status-Zeile
    assert capsys.readouterr().out == ""


def test_export_normalisiert_alternativ_ids(migrated_db, tmp_path):
    """Kurzformen wie '43' / 'OBJ-43' werden zu OBJ_0043 normalisiert."""
    out = tmp_path / "kurz.csv"
    code = main(["export", "43", "OBJ-1",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert {r["ID"] for r in rows} == {"OBJ_0001", "OBJ_0043"}


def test_export_status_filter(migrated_db, tmp_path):
    out = tmp_path / "aktiv.csv"
    code = main(["export", "--status", "aktiv",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) > 0
    assert all(r["status"] == "aktiv" for r in rows)


def test_export_ungueltiger_status_gibt_2(migrated_db, tmp_path, capsys):
    """--status akzeptiert nur VALID_STATUSES; Tippfehler -> exit 2 mit klarer Meldung.

    Vor der Validierung erzeugte ein Tippfehler wie ``--status aktief`` still
    eine leere CSV mit Exit 0 (Filter in :func:`export_csv` per exakter
    String-Gleichheit -> 0 Treffer, geschrieben mit "Geschrieben: 0 Objekte
    -> aktief.csv"), sodass der User die Ursache erst am unerwartet
    leeren Ergebnis merkte. Spiegelt die Validierung in
    :func:`stonebook.db.repository._append_enum_in_filter` (dort mit dem
    Kommentar "Validiert gegen VALID_STATUSES, damit Tippfehler keinen
    leeren Filter erzeugen") auf die CLI-Grenze, damit der Fehler an
    der Aufruf-Stelle sichtbar wird und die Fehlermeldung die drei
    erlaubten Werte nennt, ohne dass der User in die DB / das Feld-
    Woerterbuch schauen muss.
    """
    out = tmp_path / "typo.csv"
    code = main(["export", "--status", "aktief",
                 "--out", str(out), "--db", str(migrated_db)])
    assert code == 2
    err = capsys.readouterr().err
    assert "Ungueltiger --status" in err
    assert "'aktief'" in err
    # Die drei kanonischen Werte werden in der Fehlermeldung genannt,
    # damit der User den Tippfehler direkt korrigieren kann.
    assert "aktiv" in err
    assert "platzhalter" in err
    assert "archiviert" in err
    # Bei Fehler darf die Zieldatei nicht entstehen (silent-empty-Regress).
    assert not out.exists()


def test_export_status_case_sensitiv(migrated_db, tmp_path, capsys):
    """--status ist case-sensitiv; ``AKTIV``/``Aktiv`` sind Tippfehler.

    Die DB speichert Status durchgehend klein ("aktiv"/"platzhalter"/
    "archiviert"), :data:`VALID_STATUSES` enthaelt nur die Kleinschreibung.
    Case-Abweichung ohne Validierung wuerde denselben leere-CSV-Regress
    wie unbekannte Werte ausloesen - dieser Test verankert die
    Case-Strenge symmetrisch zur repository-seitigen Validierung.
    """
    out = tmp_path / "case.csv"
    code = main(["export", "--status", "AKTIV",
                 "--out", str(out), "--db", str(migrated_db)])
    assert code == 2
    err = capsys.readouterr().err
    assert "Ungueltiger --status" in err
    assert "'AKTIV'" in err
    assert not out.exists()


def test_export_status_alle_valid_werte_akzeptiert(migrated_db, tmp_path):
    """Regress-Anker: die drei kanonischen VALID_STATUSES bleiben akzeptiert.

    Waehrend die vorstehenden Tests die Rejection ungueltiger Werte
    verankern, verankert dieser Test die andere Seite - jeder der drei
    kanonischen Werte fuehrt weiter zu Exit 0 (die Anzahl Treffer kann
    0 sein, z.B. wenn die Test-DB keine archivierten Objekte enthaelt,
    aber der Filter darf nicht abgewiesen werden).
    """
    for status in ("aktiv", "platzhalter", "archiviert"):
        out = tmp_path / f"{status}.csv"
        code = main(["export", "--status", status,
                     "--out", str(out), "--db", str(migrated_db), "--quiet"])
        assert code == 0, f"{status} soll akzeptiert werden"
        rows = _read_csv(out)
        # Nur pruefen, dass jede zurueckgegebene Zeile den erwarteten
        # Status traegt - die Test-DB muss nicht zwingend jeden Status
        # tatsaechlich enthalten.
        assert all(r["status"] == status for r in rows)


def test_export_all_flag_ist_aequivalent_zu_kein_filter(migrated_db, tmp_path):
    out = tmp_path / "all.csv"
    code = main(["export", "--all",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    assert len(_read_csv(out)) == 546


def test_export_ungueltige_id_gibt_2(migrated_db, tmp_path, capsys):
    out = tmp_path / "x.csv"
    code = main(["export", "Quatsch",
                 "--out", str(out), "--db", str(migrated_db)])
    assert code == 2
    err = capsys.readouterr().err
    assert "Ungueltige Objekt-ID" in err
    # Bei Fehler darf die Zieldatei nicht entstehen
    assert not out.exists()


def test_export_fehlende_db_gibt_2(tmp_path, capsys):
    out = tmp_path / "x.csv"
    code = main(["export", "OBJ_0001",
                 "--out", str(out), "--db", str(tmp_path / "fehlt.sqlite3")])
    assert code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err


def test_export_ids_from_file_akzeptiert_kommentare_und_leerzeilen(
        migrated_db, tmp_path):
    """--ids-from-file liest eine ID pro Zeile, ignoriert Kommentare/Leerzeilen.

    Spiegelt das Verhalten von docx_cli --ids-from-file, damit die beiden
    Export-CLIs kompatible Ausdruecke akzeptieren (Sammler-Workflow: eine
    Datei = eine Selektion, egal ob Berichte oder CSV gebraucht werden).
    """
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text(
        "# Erste Charge\n"
        "OBJ_0001\n"
        "\n"
        "  OBJ-43   # inline-Kommentar\n"
        "Objekt 3\n",
        encoding="utf-8",
    )
    out = tmp_path / "sel.csv"
    code = main(["export", "--ids-from-file", str(ids_file),
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert {r["ID"] for r in rows} == {"OBJ_0001", "OBJ_0003", "OBJ_0043"}


def test_export_ids_from_file_und_positional_werden_vereinigt_und_dedupliziert(
        migrated_db, tmp_path):
    """Datei-IDs + positionale IDs werden dedupliziert (Datei zuerst).

    Analog docx_cli: OBJ_0001 aus Datei + OBJ_0001 aus Kommandozeile
    landen nur einmal im Export. Die frueher naive positional-Liste (kein
    Dedup) haette hier zwei Zeilen mit derselben ID erzeugt.
    """
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("OBJ_0001\n3\n", encoding="utf-8")
    out = tmp_path / "sel.csv"
    code = main(["export", "43", "OBJ_0001",
                 "--ids-from-file", str(ids_file),
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    ids = [r["ID"] for r in rows]
    # Ergebnis-Reihenfolge folgt der DB (export_csv sortiert nach obj_id),
    # nicht der Aufruf-Reihenfolge - relevant ist nur, dass jede ID genau
    # einmal auftaucht und alle drei Zielobjekte enthalten sind.
    assert sorted(ids) == ["OBJ_0001", "OBJ_0003", "OBJ_0043"]
    assert len(ids) == 3


def test_export_ids_from_file_ungueltige_id_gibt_2(migrated_db, tmp_path, capsys):
    """Nicht normalisierbare Zeile in der ID-Datei -> exit 2, keine Ausgabe-Datei."""
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("OBJ_0001\nQuatsch\n", encoding="utf-8")
    out = tmp_path / "sel.csv"
    code = main(["export", "--ids-from-file", str(ids_file),
                 "--out", str(out), "--db", str(migrated_db)])
    assert code == 2
    err = capsys.readouterr().err
    assert "Ungueltige Objekt-ID" in err
    assert "Quatsch" in err
    assert not out.exists()


def test_export_ids_from_file_datei_fehlt_gibt_2(migrated_db, tmp_path, capsys):
    """Nicht lesbare Datei -> exit 2 mit spezifischer stderr-Meldung."""
    out = tmp_path / "sel.csv"
    code = main(["export", "--ids-from-file", str(tmp_path / "fehlt.txt"),
                 "--out", str(out), "--db", str(migrated_db)])
    assert code == 2
    err = capsys.readouterr().err
    assert "ID-Datei nicht lesbar" in err
    assert not out.exists()


def test_export_ids_from_file_utf8_bom_wird_transparent_gestrippt(
        migrated_db, tmp_path):
    """UTF-8-BOM (Windows-Notepad-Default) darf die erste ID nicht kaputt machen.

    Ohne den ``utf-8-sig``-Fix in :func:`read_ids_from_file` wuerde die
    erste ID mit U+FEFF beginnen (``﻿OBJ_0001``), von
    :func:`normalize_id` als ungueltig zurueckgewiesen und der Aufruf
    mit exit 2 abbrechen ("Ungueltige Objekt-ID: '﻿OBJ_0001'").
    Sammler-Workflow: IDs in Notepad tippen (Default-Encoding auf
    Windows 11 = UTF-8 mit BOM), speichern, ``--ids-from-file``
    uebergeben. Ende-zu-Ende-Anker fuer den Direkt-Test in
    :func:`tests.test_csv_loaders.test_read_ids_from_file_utf8_bom_wird_gestrippt`.
    """
    ids_file = tmp_path / "ids_bom.txt"
    ids_file.write_bytes(b"\xef\xbb\xbfOBJ_0001\nOBJ_0043\n")
    out = tmp_path / "sel.csv"
    code = main(["export", "--ids-from-file", str(ids_file),
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert {r["ID"] for r in rows} == {"OBJ_0001", "OBJ_0043"}


def test_export_all_gewinnt_gegen_ids_from_file(migrated_db, tmp_path):
    """--all uebergeht die ID-Datei (dokumentierte Praezedenz)."""
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("OBJ_0001\n", encoding="utf-8")
    out = tmp_path / "all.csv"
    code = main(["export", "--all", "--ids-from-file", str(ids_file),
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    # Volles Set trotz einzelner ID in der Datei
    assert len(_read_csv(out)) == 546


def test_export_status_gewinnt_gegen_ids_from_file(migrated_db, tmp_path):
    """--status uebergeht die ID-Datei (Praezedenz symmetrisch zu --all)."""
    ids_file = tmp_path / "ids.txt"
    # Absichtlich eine ID, die vermutlich NICHT status=aktiv hat, damit
    # der Test bei falscher Praezedenz sichtbar bricht.
    ids_file.write_text("OBJ_0001\n", encoding="utf-8")
    out = tmp_path / "aktiv.csv"
    code = main(["export", "--status", "aktiv",
                 "--ids-from-file", str(ids_file),
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert all(r["status"] == "aktiv" for r in rows)


def test_import_legt_neue_objekte_an(tmp_path, capsys):
    src = tmp_path / "src.csv"
    src.write_text(
        "ID,Mineral_Primaer,Gewicht_g\nOBJ_0999,Calcit,12.5\n",
        encoding="utf-8",
    )
    db = tmp_path / "neu.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Angelegt: 1" in captured
    # Die frische DB enthaelt das Objekt
    import sqlite3
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM objects WHERE obj_id='OBJ_0999'").fetchone()
    assert row is not None
    assert row["Mineral_Primaer"] == "Calcit"
    assert row["Gewicht_g"] == 12.5
    c.close()


def test_import_json_report(tmp_path, capsys):
    """--json schreibt den Report als JSON auf stdout."""
    src = tmp_path / "src.csv"
    src.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\n",
        encoding="utf-8",
    )
    db = tmp_path / "j.sqlite3"
    code = main(["import", str(src), "--db", str(db), "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["angelegt"] == ["OBJ_0001"]
    assert report["aktualisiert"] == []
    assert report["konflikte"] == {}


def test_import_merge_only_meldet_konflikte(tmp_path, capsys):
    db = tmp_path / "m.sqlite3"
    src1 = tmp_path / "1.csv"
    src1.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\n", encoding="utf-8")
    main(["import", str(src1), "--db", str(db), "--quiet"])
    capsys.readouterr()

    src2 = tmp_path / "2.csv"
    src2.write_text(
        "ID,Mineral_Primaer,Farbe_beobachtet\nOBJ_0001,Calcit,gelb\n",
        encoding="utf-8")
    code = main(["import", str(src2), "--db", str(db), "--merge-only", "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["aktualisiert"] == ["OBJ_0001"]
    assert report["konflikte"] == {"OBJ_0001": ["Mineral_Primaer"]}
    # Alter Wert bleibt erhalten, leeres Feld wurde gefuellt
    import sqlite3
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM objects WHERE obj_id='OBJ_0001'").fetchone()
    assert row["Mineral_Primaer"] == "Quarz"
    assert row["Farbe_beobachtet"] == "gelb"
    c.close()


def test_import_no_create_missing_uebergeht_unbekannte(tmp_path, capsys):
    src = tmp_path / "src.csv"
    src.write_text("ID,Mineral_Primaer\nOBJ_0999,Calcit\n", encoding="utf-8")
    db = tmp_path / "x.sqlite3"
    code = main(["import", str(src), "--db", str(db),
                 "--no-create-missing", "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["uebersprungen"] == ["OBJ_0999"]
    assert report["angelegt"] == []


def test_import_fehlende_csv_gibt_2(tmp_path, capsys):
    code = main(["import", str(tmp_path / "fehlt.csv"),
                 "--db", str(tmp_path / "x.sqlite3")])
    assert code == 2
    err = capsys.readouterr().err
    assert "CSV-Datei fehlt" in err


def test_import_meldet_duplikate_text_und_json(tmp_path, capsys):
    """CLI-Text zeigt "Doppelte IDs in Quelle: N" und --json enthaelt "duplikate".

    Spiegelt die Konflikte-Meldung: Zeile erscheint nur, wenn es Duplikate
    gibt (kein "Doppelte IDs: 0"-Noise), analog "Konflikte (merge-only)".
    """
    src = tmp_path / "dup.csv"
    src.write_text(
        "ID,Mineral_Primaer\n"
        "OBJ_0001,Quarz\n"
        "OBJ_0001,Amethyst\n",
        encoding="utf-8",
    )
    db = tmp_path / "dup.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Doppelte IDs in Quelle: 1" in out

    # --json: duplikate-Feld enthaelt die ID.
    src2 = tmp_path / "dup2.csv"
    src2.write_text(
        "ID,Mineral_Primaer\n"
        "OBJ_0002,Calcit\n"
        "OBJ_0002,Aragonit\n",
        encoding="utf-8",
    )
    db2 = tmp_path / "dup2.sqlite3"
    code = main(["import", str(src2), "--db", str(db2), "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["duplikate"] == ["OBJ_0002"]


def test_import_ohne_duplikate_zeigt_keine_zeile(tmp_path, capsys):
    """Ohne Duplikate erscheint die "Doppelte IDs"-Zeile nicht in der Text-Ausgabe."""
    src = tmp_path / "ok.csv"
    src.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\nOBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    db = tmp_path / "ok.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Doppelte IDs" not in out


def test_import_meldet_zeilen_ohne_id_text_und_json(tmp_path, capsys):
    """CLI-Text zeigt "Zeilen ohne ID: N" und --json enthaelt "zeilen_ohne_id".

    Symmetrisch zur Duplikat-Meldung: Zeile erscheint nur, wenn Zeilen ohne
    verwertbare ID vorkommen (kein "Zeilen ohne ID: 0"-Noise).
    """
    src = tmp_path / "leer.csv"
    src.write_text(
        "ID,Mineral_Primaer\n"
        "OBJ_0001,Quarz\n"
        ",Calcit\n"
        "OBJ_0002,Amethyst\n"
        "??,Turmalin\n",
        encoding="utf-8",
    )
    db = tmp_path / "leer.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Zeilen ohne ID: 2" in out
    # Zeilennummern (1-basiert ueber Datenzeilen) muessen im Text auftauchen.
    assert "Zeilen 2, 4" in out

    src2 = tmp_path / "leer2.csv"
    src2.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\n,Calcit\n",
        encoding="utf-8",
    )
    db2 = tmp_path / "leer2.sqlite3"
    code = main(["import", str(src2), "--db", str(db2), "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["zeilen_ohne_id"] == [2]


def test_import_ohne_id_luecken_zeigt_keine_zeile(tmp_path, capsys):
    """Ohne fehlende IDs erscheint die "Zeilen ohne ID"-Zeile nicht in der Text-Ausgabe."""
    src = tmp_path / "ok2.csv"
    src.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\nOBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    db = tmp_path / "ok2.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Zeilen ohne ID" not in out


def test_import_meldet_ungueltiges_funddatum_text_und_json(tmp_path, capsys):
    """CLI-Text zeigt "Ungueltige Funddatum-Werte: N" und --json enthaelt
    "funddatum_invalid".

    Symmetrisch zur Duplikat-/ID-Luecken-Meldung: Zeile erscheint nur, wenn
    kaputte Werte vorkommen (kein "0"-Noise). Der Roh-Wert wird im Text
    mit angegeben, damit der User den Tippfehler direkt sieht.
    """
    src = tmp_path / "fd.csv"
    src.write_text(
        "ID,Funddatum,Mineral_Primaer\n"
        "OBJ_0001,2024-06-13,Quarz\n"
        "OBJ_0002,32.13.2024,Calcit\n"
        "OBJ_0003,Sommer 84,Amethyst\n",
        encoding="utf-8",
    )
    db = tmp_path / "fd.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Ungueltige Funddatum-Werte: 2" in out
    # Roh-Wert taucht im Text auf (repr fuer eindeutige Whitespace-Sichtbarkeit).
    assert "'32.13.2024'" in out
    assert "'Sommer 84'" in out

    src2 = tmp_path / "fd2.csv"
    src2.write_text(
        "ID,Funddatum,Mineral_Primaer\nOBJ_0001,kaputt,Quarz\n",
        encoding="utf-8",
    )
    db2 = tmp_path / "fd2.sqlite3"
    code = main(["import", str(src2), "--db", str(db2), "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    # JSON serialisiert Tupel als Listen (JSON kennt keine Tupel).
    assert report["funddatum_invalid"] == [[1, "kaputt"]]


def test_import_ohne_funddatum_luecken_zeigt_keine_zeile(tmp_path, capsys):
    """Ohne kaputte Datumswerte erscheint die "Ungueltige Funddatum"-Zeile nicht.

    Symmetrisch zu duplikate/zeilen_ohne_id: kein "0"-Noise fuer sauberen Import.
    """
    src = tmp_path / "fdok.csv"
    src.write_text(
        "ID,Funddatum,Mineral_Primaer\n"
        "OBJ_0001,2024-06-13,Quarz\n"
        "OBJ_0002,,Calcit\n",
        encoding="utf-8",
    )
    db = tmp_path / "fdok.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Ungueltige Funddatum" not in out


def test_import_meldet_ungueltige_numerische_werte_text_und_json(tmp_path, capsys):
    """CLI-Text zeigt "Ungueltige numerische Werte: N" und --json enthaelt
    "numeric_invalid".

    Symmetrisch zur Datum-Meldung: Zeile erscheint nur, wenn Silent-Drops
    vorkommen (kein "0"-Noise). Zeile + Spalte + Roh-Wert werden im Text
    zusammengefasst, damit der User den Tippfehler direkt lokalisieren kann.
    """
    src = tmp_path / "nu.csv"
    src.write_text(
        "ID,Gewicht_g,Wert_CHF_roh,Mineral_Primaer\n"
        "OBJ_0001,42.5,500,Quarz\n"
        "OBJ_0002,sehr schwer,teuer,Calcit\n",
        encoding="utf-8",
    )
    db = tmp_path / "nu.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Ungueltige numerische Werte: 2" in out
    # Zeile + Spalte + Roh-Wert (repr) tauchen im Text auf.
    assert "Zeile 2 Gewicht_g: 'sehr schwer'" in out
    assert "Zeile 2 Wert_CHF_roh: 'teuer'" in out

    src2 = tmp_path / "nu2.csv"
    src2.write_text(
        "ID,Gewicht_g,Mineral_Primaer\nOBJ_0001,kaputt,Quarz\n",
        encoding="utf-8",
    )
    db2 = tmp_path / "nu2.sqlite3"
    code = main(["import", str(src2), "--db", str(db2), "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    # JSON serialisiert Tripel als Listen (JSON kennt keine Tupel).
    assert report["numeric_invalid"] == [[1, "Gewicht_g", "kaputt"]]


def test_import_ohne_numerische_luecken_zeigt_keine_zeile(tmp_path, capsys):
    """Ohne kaputte Zahl-Werte erscheint die "Ungueltige numerische"-Zeile nicht.

    Spiegelt die Kein-0-Noise-Regel von duplikate/zeilen_ohne_id/
    funddatum_invalid: sauberer Import darf keine Silent-Drop-Meldung erzeugen.
    """
    src = tmp_path / "nuok.csv"
    src.write_text(
        "ID,Gewicht_g,Wert_CHF_roh,Mineral_Primaer\n"
        "OBJ_0001,42.5,500,Quarz\n"
        "OBJ_0002,,,Calcit\n",
        encoding="utf-8",
    )
    db = tmp_path / "nuok.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Ungueltige numerische" not in out


def test_export_import_roundtrip(migrated_db, tmp_path):
    """Export aus voller DB -> Import in frische DB liefert dieselben Felder."""
    out = tmp_path / "rt.csv"
    main(["export", "OBJ_0043",
          "--out", str(out), "--db", str(migrated_db), "--quiet"])
    fresh = tmp_path / "fresh.sqlite3"
    main(["import", str(out), "--db", str(fresh), "--quiet"])
    import sqlite3
    c = sqlite3.connect(str(fresh))
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM objects WHERE obj_id='OBJ_0043'").fetchone()
    assert row is not None
    assert "Quarz" in row["Mineral_Primaer"]
    assert row["Gewicht_g"] == 41.0
    c.close()


def test_import_dry_run_meldet_neue_ohne_zu_schreiben(tmp_path, capsys):
    """--dry-run zeigt "Angelegt: 1", legt aber in der DB nichts an."""
    src = tmp_path / "src.csv"
    src.write_text(
        "ID,Mineral_Primaer,Gewicht_g\nOBJ_0999,Calcit,12.5\n",
        encoding="utf-8",
    )
    # DB existiert bereits (leer, aber initialisiert), damit --dry-run
    # keinen Anlege-Fehler wirft.
    from stonebook.db.database import open_db
    db = tmp_path / "dry.sqlite3"
    open_db(db).close()

    code = main(["import", str(src), "--db", str(db), "--dry-run"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Dry-Run" in captured
    assert "Angelegt: 1" in captured
    # DB blieb unveraendert
    import sqlite3
    c = sqlite3.connect(str(db))
    n = c.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    c.close()
    assert n == 0


def test_import_dry_run_meldet_updates_ohne_zu_schreiben(tmp_path, capsys):
    """--dry-run zeigt "Aktualisiert: 1", laesst den DB-Wert aber unangetastet."""
    from stonebook.db.database import open_db
    db = tmp_path / "dryupd.sqlite3"
    src1 = tmp_path / "src1.csv"
    src1.write_text(
        "ID,Mineral_Primaer,Gewicht_g\nOBJ_0001,Quarz,10.0\n",
        encoding="utf-8",
    )
    main(["import", str(src1), "--db", str(db), "--quiet"])
    capsys.readouterr()

    src2 = tmp_path / "src2.csv"
    src2.write_text(
        "ID,Gewicht_g\nOBJ_0001,42.0\n",
        encoding="utf-8",
    )
    code = main(["import", str(src2), "--db", str(db), "--dry-run"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Dry-Run" in captured
    assert "Aktualisiert: 1" in captured
    # DB blieb beim alten Gewicht
    import sqlite3
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    row = c.execute(
        "SELECT Gewicht_g FROM objects WHERE obj_id='OBJ_0001'").fetchone()
    c.close()
    assert row["Gewicht_g"] == 10.0


def test_import_dry_run_json_merge_only_konflikt(tmp_path, capsys):
    """--dry-run --merge-only --json meldet Konflikte ohne DB-Aenderung."""
    from stonebook.db.database import open_db
    db = tmp_path / "drym.sqlite3"
    src1 = tmp_path / "1.csv"
    src1.write_text("ID,Mineral_Primaer\nOBJ_0001,Quarz\n", encoding="utf-8")
    main(["import", str(src1), "--db", str(db), "--quiet"])
    capsys.readouterr()

    src2 = tmp_path / "2.csv"
    src2.write_text(
        "ID,Mineral_Primaer,Farbe_beobachtet\nOBJ_0001,Calcit,rot\n",
        encoding="utf-8",
    )
    code = main(["import", str(src2), "--db", str(db),
                 "--merge-only", "--dry-run", "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["aktualisiert"] == ["OBJ_0001"]
    assert report["konflikte"] == {"OBJ_0001": ["Mineral_Primaer"]}
    # DB blieb beim alten Wert; das leere Farbe-Feld wurde NICHT gefuellt.
    import sqlite3
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM objects WHERE obj_id='OBJ_0001'").fetchone()
    c.close()
    assert row["Mineral_Primaer"] == "Quarz"
    assert row["Farbe_beobachtet"] in (None, "")


def test_import_dry_run_ohne_db_datei_gibt_2(tmp_path, capsys):
    """--dry-run auf fehlender DB gibt 2 zurueck und legt KEINE leere DB an."""
    src = tmp_path / "src.csv"
    src.write_text("ID,Mineral_Primaer\nOBJ_0001,Quarz\n", encoding="utf-8")
    db = tmp_path / "fehlt.sqlite3"
    code = main(["import", str(src), "--db", str(db), "--dry-run"])
    assert code == 2
    assert not db.exists()
    err = capsys.readouterr().err
    assert "Dry-Run" in err
