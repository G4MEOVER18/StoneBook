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
