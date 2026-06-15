"""CLI fuer die Konsistenzpruefung."""
import json
from pathlib import Path

import pytest

from stonebook.db.database import open_db
from stonebook.db.integrity_cli import main
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def test_clean_db_exit_0_text(migrated_db, capsys):
    exit_code = main(["--db", str(migrated_db)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "OK" in out


def test_clean_db_exit_0_json(migrated_db, capsys):
    exit_code = main(["--db", str(migrated_db), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["is_clean"] is True


def test_kaputte_db_exit_1(tmp_path, capsys):
    """Inkonsistenz im Funddatum: CLI muss exit 1 zurueckgeben."""
    db_file = tmp_path / "bad.sqlite3"
    c = open_db(db_file)
    try:
        c.execute(
            "INSERT INTO objects (obj_id, Funddatum) VALUES ('OBJ_0001', '32.13.2024')")
        c.commit()
    finally:
        c.close()
    exit_code = main(["--db", str(db_file)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "FEHLER" in out
    assert "invalid_funddatum" in out
    # Text-Bericht nennt mindestens die betroffene ID direkt — User muss nicht
    # erst die JSON-Form anschauen, um zu wissen, welches Objekt das Problem ist.
    assert "OBJ_0001" in out


def test_text_bericht_zeigt_max_3_beispiele(tmp_path, capsys):
    """Bei vielen Befunden werden 3 IDs gelistet, der Rest als '+N weitere'."""
    db_file = tmp_path / "many.sqlite3"
    c = open_db(db_file)
    try:
        c.executemany(
            "INSERT INTO objects (obj_id, Funddatum) VALUES (?, '32.13.2024')",
            [(f"OBJ_{i:04d}",) for i in range(1, 8)],
        )
        c.commit()
    finally:
        c.close()
    exit_code = main(["--db", str(db_file)])
    assert exit_code == 1
    out = capsys.readouterr().out
    # Erste drei IDs werden gezeigt, vierte nicht
    assert "OBJ_0001" in out
    assert "OBJ_0002" in out
    assert "OBJ_0003" in out
    assert "OBJ_0004" not in out
    # Zaehler fuer den Rest
    assert "+4 weitere" in out


def test_text_bericht_zeigt_tuple_befunde(tmp_path, capsys):
    """Tupel-Listen (z.B. numeric_out_of_range) werden lesbar zusammengezogen."""
    db_file = tmp_path / "oor.sqlite3"
    c = open_db(db_file)
    try:
        c.execute(
            "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES ('OBJ_0001', 150)")
        c.commit()
    finally:
        c.close()
    exit_code = main(["--db", str(db_file)])
    assert exit_code == 1
    out = capsys.readouterr().out
    # ID + Feld + Wert tauchen in derselben Beispiel-Zeile auf
    assert "OBJ_0001" in out
    assert "Confidence_Prozent" in out


def test_fehlende_db_exit_2(tmp_path, capsys):
    exit_code = main(["--db", str(tmp_path / "fehlt.sqlite3")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err


def test_check_files_findet_fehlende_bilder(migrated_db, tmp_path, capsys):
    """--check-files --root <leerer Ordner> findet 63 fehlende Bilder."""
    exit_code = main([
        "--db", str(migrated_db),
        "--check-files",
        "--root", str(tmp_path),
        "--json",
    ])
    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["missing_image_files"]) == 63
