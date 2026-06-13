"""End-to-End-Migration gegen das echte Repo (read-only auf Quellen, DB in tmp)."""
from pathlib import Path

import pytest

from stonebook.db.database import connect
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    report = migrate(REPO, db_file, log=lambda *_: None)
    conn = connect(db_file)
    yield conn, report
    conn.close()


def test_kennzahlen(migrated):
    _, report = migrated
    assert report["objekte"] == 546        # 600 - 54 Aliase
    assert report["aliase"] == 54
    assert report["bilder"] == 63          # Bilder unter objects\ (legacy/docs zählen nicht)
    assert report["parse_fehler"] == 0
    assert 0 < report["aktiv"] < 100       # nur dokumentierte Objekte sind aktiv


def test_obj43_felder(migrated):
    conn, _ = migrated
    row = conn.execute("SELECT * FROM objects WHERE obj_id = 'OBJ_0043'").fetchone()
    assert row is not None
    assert "Quarz" in row["Mineral_Primaer"]
    assert row["Gewicht_g"] == 41.0
    assert row["status"] == "aktiv"


def test_obj44_ist_alias_von_43(migrated):
    conn, _ = migrated
    assert conn.execute("SELECT 1 FROM objects WHERE obj_id = 'OBJ_0044'").fetchone() is None
    row = conn.execute("SELECT canonical_id FROM aliases WHERE alias_id = 'OBJ_0044'").fetchone()
    assert row["canonical_id"] == "OBJ_0043"


def test_obj1_bilder_kategorien(migrated):
    conn, _ = migrated
    cats = {r[0] for r in conn.execute(
        "SELECT DISTINCT kategorie FROM images WHERE obj_id = 'OBJ_0001'")}
    assert {"Kamera", "Mikroskop", "Sonderaufnahmen", "UV395"} <= cats


def test_alias_bilder_umgehaengt(migrated):
    conn, _ = migrated
    # OBJ_0002 ist Alias von OBJ_0001 — dessen Bilder hängen am Kanon mit Herkunft
    rows = conn.execute(
        "SELECT COUNT(*) FROM images WHERE obj_id = 'OBJ_0001' AND herkunft_obj_id = 'OBJ_0002'"
    ).fetchone()
    assert rows[0] > 0


def test_fts_suche(migrated):
    conn, _ = migrated
    rows = conn.execute(
        "SELECT obj_id FROM objects WHERE rowid IN "
        "(SELECT rowid FROM objects_fts WHERE objects_fts MATCH '\"Jaspis\"*')").fetchall()
    ids = {r[0] for r in rows}
    assert "OBJ_0001" in ids


def test_platzhalter_status(migrated):
    conn, _ = migrated
    row = conn.execute("SELECT status FROM objects WHERE obj_id = 'OBJ_0500'").fetchone()
    assert row["status"] == "platzhalter"
