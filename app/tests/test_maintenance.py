"""DB-Wartung: vacuum, Groesse, quick_check."""
from stonebook.db.database import open_db
from stonebook.db.maintenance import (database_size_bytes, db_file_bytes,
                                      free_page_count, quick_check, vacuum)
from stonebook.db.repository import ObjectRepo


def test_database_size_und_dateigroesse_positiv(tmp_path):
    f = tmp_path / "x.sqlite3"
    c = open_db(f)
    try:
        assert database_size_bytes(c) > 0
        assert db_file_bytes(f) > 0
    finally:
        c.close()


def test_quick_check_neu_angelegte_db_ok(tmp_path):
    c = open_db(tmp_path / "ok.sqlite3")
    try:
        assert quick_check(c) == []
    finally:
        c.close()


def test_vacuum_verkleinert_db_nach_loesch(tmp_path):
    c = open_db(tmp_path / "v.sqlite3")
    repo = ObjectRepo(c)
    try:
        # Genug Objekte anlegen, damit nach dem Loeschen Free-Pages anfallen
        for i in range(1, 401):
            repo.create(f"OBJ_{i:04d}", Name=f"Name {i}" * 50,
                        Reaktionshinweis="Wartungs-Test " * 50)
        bytes_voll = database_size_bytes(c)
        # Alles loeschen → Free-Pages
        c.execute("DELETE FROM objects")
        c.commit()
        assert free_page_count(c) > 0
        before, after = vacuum(c)
        # VACUUM defragmentiert und gibt die Free-Pages frei
        assert after <= before
        assert after < bytes_voll
        assert free_page_count(c) == 0
    finally:
        c.close()


def test_vacuum_quick_check_idempotent(tmp_path):
    """Mehrfach hintereinander VACUUM darf die DB-Pruefung nicht beschaedigen."""
    c = open_db(tmp_path / "i.sqlite3")
    ObjectRepo(c).create("OBJ_0001", Name="Test")
    try:
        vacuum(c)
        vacuum(c)
        assert quick_check(c) == []
        # Daten ueberleben
        assert c.execute(
            "SELECT Name FROM objects WHERE obj_id='OBJ_0001'"
        ).fetchone()["Name"] == "Test"
    finally:
        c.close()
