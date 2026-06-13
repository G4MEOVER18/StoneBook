"""Konsistenzprüfungen über die DB."""
import datetime
from pathlib import Path

import pytest

from stonebook.db.database import connect, open_db
from stonebook.db.integrity import check_integrity
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_conn(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    c = connect(db_file)
    yield c
    c.close()


def test_migrierte_db_ist_konsistent(migrated_conn):
    rep = check_integrity(migrated_conn)
    assert rep.is_clean
    assert rep.alias_to_missing == []
    assert rep.alias_id_collisions == []
    assert rep.invalid_funddatum == []


def test_check_files_findet_fehlendes_bild(migrated_conn, tmp_path):
    # Fake-Repo ohne Bilddateien → alle Bildreferenzen muessten als fehlend gelten
    rep = check_integrity(migrated_conn, root=tmp_path, check_files=True)
    assert len(rep.missing_image_files) == 63
    assert not rep.is_clean


def test_invalid_funddatum_wird_erkannt(tmp_path):
    db = tmp_path / "x.sqlite3"
    c = open_db(db)
    c.execute(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        ("OBJ_0001", "32.13.2024"),
    )
    c.execute(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        ("OBJ_0002", "2024-06-13"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.invalid_funddatum == ["OBJ_0001"]
    c.close()


def test_alias_collision_wird_erkannt(tmp_path):
    db = tmp_path / "x.sqlite3"
    c = open_db(db)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    c.execute(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES (?, ?)",
        ("OBJ_0002", "OBJ_0001"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.alias_id_collisions == ["OBJ_0002"]
    c.close()


def test_numeric_out_of_range_wird_erkannt(tmp_path):
    c = open_db(tmp_path / "x.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, Gewicht_g, "
        "Seltenheit_global_1_10, Mohs_Haerte_min) VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", 150, 10.0, 5, 7.0),    # Confidence > 100
            ("OBJ_0002", 80, -2.5, 5, 7.0),     # negatives Gewicht
            ("OBJ_0003", 80, 10.0, 11, 7.0),    # Seltenheit > 10
            ("OBJ_0004", 80, 10.0, 5, 7.0),     # alles ok
        ],
    )
    c.commit()
    rep = check_integrity(c)
    fields = {(oid, f) for oid, f, _ in rep.numeric_out_of_range}
    assert ("OBJ_0001", "Confidence_Prozent") in fields
    assert ("OBJ_0002", "Gewicht_g") in fields
    assert ("OBJ_0003", "Seltenheit_global_1_10") in fields
    assert not any(oid == "OBJ_0004" for oid, _, _ in rep.numeric_out_of_range)
    assert not rep.is_clean
    c.close()


def test_range_inverted_wird_erkannt(tmp_path):
    c = open_db(tmp_path / "x.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max, "
        "Dichte_min_gcm3, Dichte_max_gcm3) VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", 7.0, 5.0, 2.6, 2.7),   # Mohs invertiert
            ("OBJ_0002", 5.0, 7.0, 3.0, 2.5),   # Dichte invertiert
            ("OBJ_0003", 5.0, 7.0, 2.6, 2.7),   # ok
            ("OBJ_0004", None, 7.0, 2.6, None), # halb leer → ueberspringen
        ],
    )
    c.commit()
    rep = check_integrity(c)
    inverted = {(oid, p) for oid, p in rep.range_inverted}
    assert ("OBJ_0001", "Mohs_Haerte_min>Mohs_Haerte_max") in inverted
    assert ("OBJ_0002", "Dichte_min_gcm3>Dichte_max_gcm3") in inverted
    assert not any(oid == "OBJ_0003" for oid, _ in rep.range_inverted)
    assert not any(oid == "OBJ_0004" for oid, _ in rep.range_inverted)
    c.close()


def test_alias_self_referencing_wird_erkannt(tmp_path):
    """Ein Alias auf sich selbst ist eine Inkonsistenz (Migration produziert das nie)."""
    c = open_db(tmp_path / "self.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    # Self-Alias: OBJ_0002 → OBJ_0002 (manuell, simuliert Edit-Fehler)
    c.execute(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES (?, ?)",
        ("OBJ_0002", "OBJ_0002"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.alias_self_referencing == ["OBJ_0002"]
    # Self-Alias kollidiert auch zwangslaeufig mit dem Objekt
    assert "OBJ_0002" in rep.alias_id_collisions
    assert not rep.is_clean
    c.close()


def test_unknown_image_kategorie_wird_erkannt(tmp_path):
    c = open_db(tmp_path / "cat.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg"),
            ("OBJ_0001", "TypoKat", "b.jpg"),  # unbekannt
            ("OBJ_0001", "Mikroskop", "c.jpg"),
            ("OBJ_0001", "", "d.jpg"),  # leer
        ],
    )
    c.commit()
    rep = check_integrity(c)
    kats = {kat for _, kat in rep.unknown_image_kategorie}
    assert "TypoKat" in kats
    assert "" in kats
    assert "Kamera" not in kats
    assert "Mikroskop" not in kats
    assert not rep.is_clean
    c.close()


def test_migrierte_db_alle_image_kategorien_bekannt(migrated_conn):
    rep = check_integrity(migrated_conn)
    assert rep.unknown_image_kategorie == []
    assert rep.alias_self_referencing == []


def test_migrierte_db_keine_numerischen_ausreisser(migrated_conn):
    rep = check_integrity(migrated_conn)
    assert rep.numeric_out_of_range == []
    assert rep.range_inverted == []


def test_as_dict_ist_serialisierbar(migrated_conn):
    import json

    rep = check_integrity(migrated_conn)
    json.dumps(rep.as_dict())


def test_future_funddatum_wird_erkannt(tmp_path):
    """Funddaten, die nach 'today' liegen, sind verdaechtig (Tippfehler/Vorgriff)."""
    c = open_db(tmp_path / "fut.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2020-06-13"),   # Vergangenheit → ok
            ("OBJ_0002", "2024-06-13"),   # heute → ok
            ("OBJ_0003", "2024-06-14"),   # Zukunft → flag
            ("OBJ_0004", "2099-12-31"),   # weit in der Zukunft → flag
            ("OBJ_0005", ""),             # leer → uebergangen
        ],
    )
    c.commit()
    rep = check_integrity(c, today=datetime.date(2024, 6, 13))
    flagged = {oid for oid, _ in rep.future_funddatum}
    assert flagged == {"OBJ_0003", "OBJ_0004"}
    assert ("OBJ_0004", "2099-12-31") in rep.future_funddatum
    # Zukunftsdaten zaehlen nicht als 'invalid' (parseable ISO)
    assert rep.invalid_funddatum == []
    assert not rep.is_clean
    c.close()


def test_future_funddatum_default_today_keine_falsch_positiven(migrated_conn):
    """Die echte DB enthaelt keine Zukunftsdaten (Default-today reicht aus)."""
    rep = check_integrity(migrated_conn)
    assert rep.future_funddatum == []


def test_aktiv_ohne_inhalt_wird_erkannt(tmp_path):
    """status='aktiv' ohne Daten und ohne Bilder ist eine Inkonsistenz."""
    c = open_db(tmp_path / "leer_aktiv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, status, Name) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "aktiv", "Vollstaendig"),         # ok: hat Name
            ("OBJ_0002", "aktiv", None),                    # leer + aktiv → flag
            ("OBJ_0003", "platzhalter", None),              # leer + platzhalter → ok
            ("OBJ_0004", "archiviert", None),               # leer + archiviert → ok
            ("OBJ_0005", "aktiv", "   "),                   # nur Whitespace → flag
        ],
    )
    # OBJ_0006 ist aktiv, hat keine Daten, aber ein Bild → ok
    c.execute("INSERT INTO objects (obj_id, status) VALUES ('OBJ_0006', 'aktiv')")
    c.execute(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        ("OBJ_0006", "Kamera", "a.jpg"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.aktiv_ohne_inhalt == ["OBJ_0002", "OBJ_0005"]
    assert not rep.is_clean
    # as_dict serialisierbar
    import json
    json.dumps(rep.as_dict())
    c.close()


def test_aktiv_ohne_inhalt_migrierte_db_clean(migrated_conn):
    """Die migrierte DB darf keine inkonsistenten 'aktiv'-Objekte enthalten."""
    rep = check_integrity(migrated_conn)
    assert rep.aktiv_ohne_inhalt == []


def test_find_duplicate_image_sha256(tmp_path):
    """Bilder mit identischem SHA-256 werden gruppiert (id-Liste pro Hash)."""
    from stonebook.db.integrity import find_duplicate_image_sha256
    c = open_db(tmp_path / "dup.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path, sha256) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg", "aaaa"),
            ("OBJ_0002", "Kamera", "b.jpg", "aaaa"),     # Dublette zu a.jpg
            ("OBJ_0001", "Mikroskop", "c.jpg", "bbbb"),  # einmalig
            ("OBJ_0001", "UV365", "d.jpg", "cccc"),
            ("OBJ_0002", "UV365", "e.jpg", "cccc"),
            ("OBJ_0002", "UV395", "f.jpg", "cccc"),      # Dreifach-Gruppe
            ("OBJ_0001", "Sonstige", "g.jpg", None),     # NULL → ignoriert
            ("OBJ_0001", "Sonstige", "h.jpg", ""),       # leer → ignoriert
        ],
    )
    c.commit()
    dups = find_duplicate_image_sha256(c)
    assert len(dups) == 2
    # Groesste Gruppe zuerst (cccc mit 3), danach aaaa mit 2
    assert dups[0][0] == "cccc"
    assert len(dups[0][1]) == 3
    assert dups[1][0] == "aaaa"
    assert len(dups[1][1]) == 2
    # id-Listen sind aufsteigend sortiert
    assert dups[0][1] == sorted(dups[0][1])
    c.close()


def test_find_duplicate_image_sha256_keine_dubletten(tmp_path):
    from stonebook.db.integrity import find_duplicate_image_sha256
    c = open_db(tmp_path / "k.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path, sha256) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg", "aaaa"),
            ("OBJ_0001", "Mikroskop", "b.jpg", "bbbb"),
        ],
    )
    c.commit()
    assert find_duplicate_image_sha256(c) == []
    c.close()


def test_find_duplicate_image_sha256_in_migrierter_db(migrated_conn):
    """Auf der echten DB darf der Aufruf nicht crashen und liefert eine Liste."""
    from stonebook.db.integrity import find_duplicate_image_sha256
    dups = find_duplicate_image_sha256(migrated_conn)
    assert isinstance(dups, list)
    # Format-Sanity: jede Gruppe ist (str, list[int])
    for sha, ids in dups:
        assert isinstance(sha, str) and sha
        assert all(isinstance(i, int) for i in ids)
        assert len(ids) > 1
