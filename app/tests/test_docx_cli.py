"""CLI fuer DOCX-Stapelexport."""
from pathlib import Path

import pytest

from stonebook.export.docx_cli import main
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def test_einzel_obj_id_normalisiert_und_schreibt(migrated_db, tmp_path, capsys):
    out = tmp_path / "berichte"
    exit_code = main(["OBJ-43", "--db", str(migrated_db), "--root", str(REPO),
                      "--out-dir", str(out)])
    assert exit_code == 0
    written = list(out.glob("*.docx"))
    assert len(written) == 1
    assert written[0].name == "Objekt_043_Analysebericht.docx"
    captured = capsys.readouterr()
    assert "[1/1] OBJ_0043" in captured.out
    assert "Geschrieben: 1 / 1" in captured.out


def test_mehrere_obj_ids(migrated_db, tmp_path):
    out = tmp_path / "mehrere"
    exit_code = main(["OBJ_0001", "43", "--db", str(migrated_db),
                      "--root", str(REPO), "--out-dir", str(out), "--quiet"])
    assert exit_code == 0
    namen = {p.name for p in out.glob("*.docx")}
    assert namen == {"Objekt_001_Analysebericht.docx",
                     "Objekt_043_Analysebericht.docx"}


def test_status_filter_aktiv(migrated_db, tmp_path):
    out = tmp_path / "aktiv"
    exit_code = main(["--status", "aktiv", "--db", str(migrated_db),
                      "--root", str(REPO), "--out-dir", str(out), "--quiet"])
    assert exit_code == 0
    written = list(out.glob("*.docx"))
    # nur dokumentierte Objekte ('aktiv') werden exportiert -> < 100, > 0
    assert 0 < len(written) < 100


def test_status_und_obj_ids_schliessen_sich_aus(migrated_db, tmp_path, capsys):
    # argparse-Eltern: --status und --all sind exklusiv. --status mit
    # positionalen IDs ist erlaubt, aber --status gewinnt (positional wird
    # ignoriert). Dokumentiert das Verhalten:
    out = tmp_path / "egal"
    code = main(["OBJ_0001", "--status", "aktiv", "--db", str(migrated_db),
                 "--root", str(REPO), "--out-dir", str(out), "--quiet"])
    assert code == 0
    # mehr als 1 Objekt -> Status-Filter hat gegriffen
    assert len(list(out.glob("*.docx"))) > 1


def test_keine_ids_keine_selektion_gibt_2(migrated_db, capsys):
    code = main(["--db", str(migrated_db), "--root", str(REPO)])
    assert code == 2
    err = capsys.readouterr().err
    assert "Bitte Objekt-IDs" in err


def test_fehlende_db_gibt_2(tmp_path, capsys):
    code = main(["OBJ_0001", "--db", str(tmp_path / "fehlt.sqlite3"),
                 "--root", str(REPO)])
    assert code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err


def test_ungueltige_id_gibt_2(migrated_db, tmp_path, capsys):
    code = main(["Quatsch", "--db", str(migrated_db),
                 "--root", str(REPO), "--out-dir", str(tmp_path / "x")])
    assert code == 2
    err = capsys.readouterr().err
    assert "Ungueltige Objekt-ID" in err


def test_continue_on_error_meldet_fehler_und_liefert_1(migrated_db, tmp_path, capsys):
    out = tmp_path / "mit_fehler"
    # OBJ_9999 existiert nicht -> export_docx wirft ValueError; continue-on-error
    # faehrt mit OBJ_0043 weiter und liefert exit 1.
    code = main(["OBJ_9999", "OBJ_0043", "--db", str(migrated_db),
                 "--root", str(REPO), "--out-dir", str(out),
                 "--continue-on-error", "--quiet"])
    assert code == 1
    err = capsys.readouterr().err
    assert "FEHLER OBJ_9999" in err
    # Das gueltige Objekt wurde trotzdem geschrieben
    assert (out / "Objekt_043_Analysebericht.docx").is_file()


def test_falscher_root_gibt_2(migrated_db, tmp_path, capsys):
    code = main(["OBJ_0001", "--db", str(migrated_db),
                 "--root", str(tmp_path), "--out-dir", str(tmp_path / "x")])
    assert code == 2
    err = capsys.readouterr().err
    assert "objects/" in err


def test_dry_run_listet_ids_und_schreibt_nichts(migrated_db, tmp_path, capsys):
    out = tmp_path / "dry"
    # --dry-run darf --out-dir ignorieren; die Datei soll NICHT entstehen.
    code = main(["OBJ_0001", "43", "--db", str(migrated_db), "--root", str(REPO),
                 "--out-dir", str(out), "--dry-run"])
    assert code == 0
    captured = capsys.readouterr()
    assert "OBJ_0001" in captured.out
    assert "OBJ_0043" in captured.out
    assert "Dry-Run: 2 Objekte" in captured.out
    # kein DOCX-Output
    assert not out.exists() or not list(out.glob("*.docx"))


def test_dry_run_quiet_unterdrueckt_summary_aber_nicht_ids(migrated_db, capsys):
    code = main(["OBJ_0001", "--db", str(migrated_db), "--root", str(REPO),
                 "--dry-run", "--quiet"])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "OBJ_0001"


def test_ids_from_file_akzeptiert_kommentare_und_leerzeilen(migrated_db, tmp_path):
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text(
        "# Erste Charge\n"
        "OBJ_0001\n"
        "\n"
        "  OBJ-43   # inline-Kommentar\n"
        "Objekt 3\n",
        encoding="utf-8",
    )
    out = tmp_path / "berichte"
    code = main(["--ids-from-file", str(ids_file), "--db", str(migrated_db),
                 "--root", str(REPO), "--out-dir", str(out), "--quiet"])
    assert code == 0
    namen = {p.name for p in out.glob("*.docx")}
    assert namen == {"Objekt_001_Analysebericht.docx",
                     "Objekt_003_Analysebericht.docx",
                     "Objekt_043_Analysebericht.docx"}


def test_ids_from_file_und_positional_werden_vereinigt_und_dedupliziert(
        migrated_db, tmp_path, capsys):
    ids_file = tmp_path / "ids.txt"
    # OBJ_0001 kommt sowohl aus der Datei als auch positional -> nur einmal.
    ids_file.write_text("OBJ_0001\n3\n", encoding="utf-8")
    code = main(["43", "OBJ_0001", "--ids-from-file", str(ids_file),
                 "--db", str(migrated_db), "--root", str(REPO), "--dry-run"])
    assert code == 0
    captured = capsys.readouterr()
    ids = [line for line in captured.out.splitlines() if line.startswith("OBJ_")]
    # Datei zuerst, dann positional; OBJ_0001 nur einmal.
    assert ids == ["OBJ_0001", "OBJ_0003", "OBJ_0043"]


def test_ids_from_file_ungueltige_id_gibt_2(migrated_db, tmp_path, capsys):
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("OBJ_0001\nQuatsch\n", encoding="utf-8")
    code = main(["--ids-from-file", str(ids_file), "--db", str(migrated_db),
                 "--root", str(REPO)])
    assert code == 2
    err = capsys.readouterr().err
    assert "Ungueltige Objekt-ID" in err
    assert "Quatsch" in err


def test_ids_from_file_datei_fehlt_gibt_2(migrated_db, tmp_path, capsys):
    code = main(["--ids-from-file", str(tmp_path / "fehlt.txt"),
                 "--db", str(migrated_db), "--root", str(REPO)])
    assert code == 2
    err = capsys.readouterr().err
    assert "ID-Datei nicht lesbar" in err


def test_ids_from_file_utf8_bom_wird_transparent_gestrippt(
        migrated_db, tmp_path, capsys):
    """UTF-8-BOM (Windows-Notepad-Default) darf die erste ID nicht kaputt machen.

    Spiegelt den End-zu-End-Anker in csv_cli auf die DOCX-Batch-Achse:
    ohne den ``utf-8-sig``-Fix in :func:`read_ids_from_file` wuerde die
    erste ID mit U+FEFF beginnen und der Aufruf mit exit 2 abbrechen
    ("Ungueltige Objekt-ID: '﻿OBJ_0001'"). ``--dry-run`` genuegt fuer
    die Verifikation, weil der ID-Parse-Pfad identisch zum echten Lauf
    ist - der Test bleibt schlank ohne DOCX-Dateien zu schreiben.
    """
    ids_file = tmp_path / "ids_bom.txt"
    ids_file.write_bytes(b"\xef\xbb\xbfOBJ_0001\nOBJ_0043\n")
    code = main(["--ids-from-file", str(ids_file), "--db", str(migrated_db),
                 "--root", str(REPO), "--dry-run"])
    assert code == 0
    captured = capsys.readouterr()
    ids = [line for line in captured.out.splitlines() if line.startswith("OBJ_")]
    assert ids == ["OBJ_0001", "OBJ_0043"]


def test_keine_ids_hilfetext_erwaehnt_ids_from_file(migrated_db, capsys):
    code = main(["--db", str(migrated_db), "--root", str(REPO)])
    assert code == 2
    err = capsys.readouterr().err
    assert "--ids-from-file" in err


def test_all_gewinnt_gegen_ids_from_file(migrated_db, tmp_path, capsys):
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("OBJ_0001\n", encoding="utf-8")
    code = main(["--ids-from-file", str(ids_file), "--all",
                 "--db", str(migrated_db), "--root", str(REPO), "--dry-run"])
    assert code == 0
    captured = capsys.readouterr()
    ids = [line for line in captured.out.splitlines() if line.startswith("OBJ_")]
    # --all liefert weit mehr als 1 Objekt.
    assert len(ids) > 1
    assert "OBJ_0001" in ids
