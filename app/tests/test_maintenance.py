"""DB-Wartung: vacuum, Groesse, quick_check, foreign_key_check."""
from stonebook.db.database import open_db
from stonebook.db.maintenance import (database_size_bytes, db_file_bytes,
                                      foreign_key_check, free_page_count,
                                      quick_check, vacuum)
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


def test_foreign_key_check_neu_angelegte_db_ok(tmp_path):
    """Frisch migrierte DB hat keine FK-Verletzungen (Schema mit ON DELETE CASCADE)."""
    c = open_db(tmp_path / "fk_ok.sqlite3")
    try:
        assert foreign_key_check(c) == []
    finally:
        c.close()


def test_foreign_key_check_orphan_image_erkannt(tmp_path):
    """``PRAGMA foreign_key_check`` erkennt Orphans, die durch deaktivierte
    Foreign-Keys eingefuegt wurden - die ueblichen Faelle aus JSON-Restore
    partieller Backups, direkter DB-Editierung oder fehlerhaften Migrations-
    skripten. Spiegelt das ``orphan_images``-Pattern aus
    :mod:`stonebook.db.integrity`, aber auf SQLite-PRAGMA-Ebene statt SQL-Join.
    """
    c = open_db(tmp_path / "fk_orph.sqlite3")
    try:
        # FK deaktivieren, um den Orphan-Pfad zu simulieren (regulaer wuerde
        # SQLite den Insert mit aktivem PRAGMA blockieren). PRAGMA wirkt nur
        # ausserhalb von Transaktionen, daher Commit zwischen den Schritten.
        c.commit()
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute(
            "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
            ("OBJ_0099_ghost", "Kamera", "objects/OBJ_0099/foto.jpg"),
        )
        c.commit()
        c.execute("PRAGMA foreign_keys = ON")
        rows = foreign_key_check(c)
        # Genau eine Verletzung: images-Zeile zeigt auf nicht existentes objects.
        assert len(rows) == 1
        table, rowid, parent, fkid = rows[0]
        assert table == "images"
        assert parent == "objects"
        assert isinstance(rowid, int)
        assert isinstance(fkid, int)
    finally:
        c.close()


def test_foreign_key_check_idempotent(tmp_path):
    """Wiederholter Aufruf darf weder DB-State noch Ergebnis veraendern."""
    c = open_db(tmp_path / "fk_idem.sqlite3")
    ObjectRepo(c).create("OBJ_0001", Name="Test")
    try:
        first = foreign_key_check(c)
        second = foreign_key_check(c)
        assert first == second == []
        # Daten ueberleben
        assert c.execute(
            "SELECT Name FROM objects WHERE obj_id='OBJ_0001'"
        ).fetchone()["Name"] == "Test"
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
