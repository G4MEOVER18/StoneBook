"""Konsistenzprüfungen über die DB."""
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


def test_as_dict_ist_serialisierbar(migrated_conn):
    import json

    rep = check_integrity(migrated_conn)
    json.dumps(rep.as_dict())
