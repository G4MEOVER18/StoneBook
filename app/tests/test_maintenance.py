"""DB-Wartung: vacuum, Groesse, quick_check, foreign_key_check, Orphan-Cleanup."""
from stonebook.db.database import open_db
from stonebook.db.maintenance import (database_size_bytes, db_file_bytes,
                                      deep_check, delete_dangling_aliases,
                                      delete_orphan_images,
                                      delete_orphan_ki_analysen,
                                      foreign_key_check,
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


def test_deep_check_neu_angelegte_db_ok(tmp_path):
    """Frisch angelegte DB hat keine Korruption (spiegelt quick_check)."""
    c = open_db(tmp_path / "deep_ok.sqlite3")
    try:
        assert deep_check(c) == []
    finally:
        c.close()


def test_deep_check_findet_quick_check_subset(tmp_path):
    """deep_check meldet auf der intakten DB exakt das gleiche wie quick_check
    (beide leer); dies fixiert die Kontrakt-Symmetrie der zwei Selbst-Pruefungen.
    """
    c = open_db(tmp_path / "deep_eq.sqlite3")
    ObjectRepo(c).create("OBJ_0001", Name="Test")
    try:
        assert deep_check(c) == quick_check(c) == []
    finally:
        c.close()


def test_deep_check_idempotent(tmp_path):
    """Wiederholter Aufruf darf weder DB-State noch Ergebnis veraendern."""
    c = open_db(tmp_path / "deep_idem.sqlite3")
    ObjectRepo(c).create("OBJ_0001", Name="Test")
    try:
        first = deep_check(c)
        second = deep_check(c)
        assert first == second == []
        assert c.execute(
            "SELECT Name FROM objects WHERE obj_id='OBJ_0001'"
        ).fetchone()["Name"] == "Test"
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


def _insert_orphan_image(c, obj_id="OBJ_0099_ghost", rel_path="objects/OBJ_0099/foto.jpg"):
    """Erzeugt ein verwaistes Bild ueber den FK-OFF-Pfad (Simulation von Korrekt-DB-Editierung)."""
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
              (obj_id, "Kamera", rel_path))
    c.commit()
    c.execute("PRAGMA foreign_keys = ON")


def _insert_orphan_ki_analyse(c, obj_id="OBJ_0099_ghost"):
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) "
              "VALUES (?, ?, ?, ?)",
              (obj_id, "2025-01-01 00:00:00", "claude-sonnet-4-6", "{}"))
    c.commit()
    c.execute("PRAGMA foreign_keys = ON")


def _insert_dangling_alias(c, alias_id="OBJ_9999", canonical_id="OBJ_0099_ghost"):
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("INSERT INTO aliases (alias_id, canonical_id, merge_quelle) "
              "VALUES (?, ?, ?)",
              (alias_id, canonical_id, "test"))
    c.commit()
    c.execute("PRAGMA foreign_keys = ON")


def test_delete_orphan_images_entfernt_nur_orphans(tmp_path):
    c = open_db(tmp_path / "orph.sqlite3")
    repo = ObjectRepo(c)
    try:
        repo.create("OBJ_0001")
        c.execute("INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
                  ("OBJ_0001", "Kamera", "objects/OBJ_0001/x.jpg"))
        c.commit()
        _insert_orphan_image(c)
        deleted = delete_orphan_images(c)
        assert deleted == 1
        # Echtes Bild bleibt
        assert c.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 1
    finally:
        c.close()


def test_delete_orphan_images_leer_no_op(tmp_path):
    c = open_db(tmp_path / "clean.sqlite3")
    try:
        assert delete_orphan_images(c) == 0
    finally:
        c.close()


def test_delete_orphan_ki_analysen_entfernt_nur_orphans(tmp_path):
    c = open_db(tmp_path / "orph_ki.sqlite3")
    repo = ObjectRepo(c)
    try:
        repo.create("OBJ_0001")
        c.execute("INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) "
                  "VALUES (?, ?, ?, ?)",
                  ("OBJ_0001", "2025-01-01 00:00:00", "claude-sonnet-4-6", "{}"))
        c.commit()
        _insert_orphan_ki_analyse(c)
        deleted = delete_orphan_ki_analysen(c)
        assert deleted == 1
        assert c.execute("SELECT COUNT(*) FROM ki_analysen").fetchone()[0] == 1
    finally:
        c.close()


def test_delete_dangling_aliases_entfernt_nur_dangling(tmp_path):
    c = open_db(tmp_path / "dang.sqlite3")
    repo = ObjectRepo(c)
    try:
        repo.create("OBJ_0001")
        # Gueltiger Alias auf existierendes Objekt
        c.execute("INSERT INTO aliases (alias_id, canonical_id, merge_quelle) "
                  "VALUES (?, ?, ?)", ("OBJ_0002", "OBJ_0001", "merge"))
        c.commit()
        _insert_dangling_alias(c)
        deleted = delete_dangling_aliases(c)
        assert deleted == 1
        assert c.execute("SELECT COUNT(*) FROM aliases").fetchone()[0] == 1
    finally:
        c.close()


def test_orphan_cleanup_macht_foreign_key_check_sauber(tmp_path):
    """Nach delete_orphan_images darf foreign_key_check keine Verletzung mehr melden."""
    c = open_db(tmp_path / "fixed.sqlite3")
    try:
        _insert_orphan_image(c)
        assert len(foreign_key_check(c)) == 1
        delete_orphan_images(c)
        assert foreign_key_check(c) == []
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
