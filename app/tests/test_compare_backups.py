"""compare_backups: Diff-Stats zwischen zwei Backups (added/removed/modified)."""
import json
from pathlib import Path

import pytest

from stonebook.db.database import connect, open_db
from stonebook.export.backup_cli import main
from stonebook.export.json_export import (compare_backup_to_db, compare_backups,
                                          export_json)
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def test_compare_gleiche_backups(tmp_path, migrated_db):
    """Backup gegen sich selbst -> alles unchanged, nichts added/removed/modified."""
    a = tmp_path / "a.json"
    conn = connect(migrated_db)
    export_json(conn, a)
    conn.close()
    diff = compare_backups(a, a)
    assert diff["objects"]["added"] == 0
    assert diff["objects"]["removed"] == 0
    assert diff["objects"]["modified"] == 0
    assert diff["objects"]["unchanged"] == 546
    assert diff["images"]["added"] == 0
    assert diff["images"]["unchanged"] == 63
    assert diff["aliases"]["unchanged"] == 54


def test_compare_added_removed_objects(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, {
        "objects": [{"obj_id": "OBJ_0001"}, {"obj_id": "OBJ_0002"}],
        "images": [], "aliases": [], "ki_analysen": [],
    })
    _write(b, {
        "objects": [{"obj_id": "OBJ_0002"}, {"obj_id": "OBJ_0003"}],
        "images": [], "aliases": [], "ki_analysen": [],
    })
    diff = compare_backups(a, b)
    assert diff["objects"]["added"] == 1   # OBJ_0003
    assert diff["objects"]["removed"] == 1  # OBJ_0001
    assert diff["objects"]["unchanged"] == 1  # OBJ_0002
    assert diff["objects"]["modified"] == 0


def test_compare_modified_objects(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, {"objects": [
        {"obj_id": "OBJ_0001", "Name": "Original"},
        {"obj_id": "OBJ_0002", "Name": "Konstant"},
    ]})
    _write(b, {"objects": [
        {"obj_id": "OBJ_0001", "Name": "Geaendert"},
        {"obj_id": "OBJ_0002", "Name": "Konstant"},
    ]})
    diff = compare_backups(a, b)
    assert diff["objects"]["modified"] == 1
    assert diff["objects"]["unchanged"] == 1
    assert diff["objects"]["modified_obj_ids"] == ["OBJ_0001"]


def test_compare_images_added_removed(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, {"objects": [{"obj_id": "OBJ_0001"}],
               "images": [{"id": 1, "obj_id": "OBJ_0001", "rel_path": "a.jpg"}]})
    _write(b, {"objects": [{"obj_id": "OBJ_0001"}],
               "images": [{"id": 2, "obj_id": "OBJ_0001", "rel_path": "b.jpg"}]})
    diff = compare_backups(a, b)
    assert diff["images"]["added"] == 1
    assert diff["images"]["removed"] == 1
    assert diff["images"]["unchanged"] == 0


def test_compare_aliases_added_removed(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, {"objects": [{"obj_id": "OBJ_0001"}],
               "aliases": [
        {"alias_id": "OBJ_0002", "canonical_id": "OBJ_0001"}]})
    _write(b, {"objects": [{"obj_id": "OBJ_0001"}],
               "aliases": [
        {"alias_id": "OBJ_0003", "canonical_id": "OBJ_0001"}]})
    diff = compare_backups(a, b)
    assert diff["aliases"]["added"] == 1
    assert diff["aliases"]["removed"] == 1


def test_compare_modified_ids_limited_to_100(tmp_path):
    """modified_obj_ids ist auf 100 Eintraege begrenzt (Listen-Hygiene)."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    objs_a = [{"obj_id": f"OBJ_{i:04d}", "Name": "A"} for i in range(1, 151)]
    objs_b = [{"obj_id": f"OBJ_{i:04d}", "Name": "B"} for i in range(1, 151)]
    _write(a, {"objects": objs_a})
    _write(b, {"objects": objs_b})
    diff = compare_backups(a, b)
    assert diff["objects"]["modified"] == 150
    assert len(diff["objects"]["modified_obj_ids"]) == 100
    assert diff["objects"]["modified_obj_ids"][0] == "OBJ_0001"


def test_compare_empty_backups(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, {})
    _write(b, {})
    diff = compare_backups(a, b)
    assert diff["objects"]["added"] == 0
    assert diff["objects"]["removed"] == 0
    assert diff["objects"]["unchanged"] == 0


def test_compare_kaputtes_backup_wirft(tmp_path):
    a = tmp_path / "ok.json"
    b = tmp_path / "kaputt.json"
    _write(a, {"objects": []})
    b.write_text("nicht json", encoding="utf-8")
    with pytest.raises(ValueError):
        compare_backups(a, b)


def test_cli_compare_gibt_json(tmp_path, capsys):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, {"objects": [{"obj_id": "OBJ_0001"}]})
    _write(b, {"objects": [{"obj_id": "OBJ_0002"}]})
    code = main(["compare", str(a), str(b)])
    assert code == 0
    diff = json.loads(capsys.readouterr().out)
    assert diff["objects"]["added"] == 1
    assert diff["objects"]["removed"] == 1


# compare_backup_to_db: spiegelt compare_backups auf die Datei-vs-DB-Achse.


def test_compare_db_gegen_eigenes_backup_alles_unchanged(tmp_path, migrated_db):
    """Backup aus der DB gegen genau diese DB -> alles unchanged.

    Spiegelt test_compare_gleiche_backups auf die Datei-vs-DB-Achse: ein
    direkt aus der DB gezogenes Backup, sofort wieder gegen dieselbe DB
    geprueft, muss komplett unchanged sein - sonst gehen export_json und
    _db_to_backup_dict beim Spalten-Layout / Typ-Mapping auseinander.
    """
    backup = tmp_path / "backup.json"
    conn = connect(migrated_db)
    try:
        export_json(conn, backup)
        diff = compare_backup_to_db(conn, backup)
    finally:
        conn.close()
    assert diff["objects"]["added"] == 0
    assert diff["objects"]["removed"] == 0
    assert diff["objects"]["modified"] == 0
    assert diff["objects"]["unchanged"] == 546
    assert diff["images"]["added"] == 0
    assert diff["images"]["removed"] == 0
    assert diff["aliases"]["unchanged"] == 54


def test_compare_db_added_objekte_im_backup(tmp_path):
    """Objekte, die nur im Backup stehen, zaehlen als ``added``.

    DB nimmt die Rolle von a, Backup die Rolle von b ein (Restore-Semantik:
    was wuerde durch das Backup neu in die DB kommen).
    """
    db_file = tmp_path / "db.sqlite3"
    conn = open_db(db_file)
    conn.execute("INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
                 ("OBJ_0001", "DB-Stueck"))
    conn.commit()
    db_row = dict(conn.execute(
        "SELECT * FROM objects WHERE obj_id=?", ("OBJ_0001",)).fetchone())

    backup = tmp_path / "backup.json"
    _write(backup, {
        "objects": [db_row,
                    {"obj_id": "OBJ_0002", "Name": "Backup-only"}],
        "images": [], "aliases": [], "ki_analysen": [],
    })
    try:
        diff = compare_backup_to_db(conn, backup)
    finally:
        conn.close()
    # OBJ_0002 fehlt in der DB, kaeme nach restore neu dazu.
    assert diff["objects"]["added"] == 1
    assert diff["objects"]["removed"] == 0
    assert diff["objects"]["modified"] == 0
    assert diff["objects"]["unchanged"] == 1


def test_compare_db_removed_objekte_nur_in_db(tmp_path):
    """Objekte nur in der DB zaehlen als ``removed`` (Restore wuerde sie verlieren).

    Spiegelt test_compare_added_removed_objects: pre-flight check warnt
    den User, dass z.B. 3 in der laufenden DB nachgepflegte Stuecke beim
    restore aus einem aelteren Backup verloren gingen.
    """
    db_file = tmp_path / "db.sqlite3"
    conn = open_db(db_file)
    conn.execute("INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
                 ("OBJ_0001", "Bleibt"))
    conn.execute("INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
                 ("OBJ_0002", "Wuerde-verschwinden"))
    conn.commit()
    row_bleibt = dict(conn.execute(
        "SELECT * FROM objects WHERE obj_id=?", ("OBJ_0001",)).fetchone())

    backup = tmp_path / "backup.json"
    _write(backup, {
        "objects": [row_bleibt],
        "images": [], "aliases": [], "ki_analysen": [],
    })
    try:
        diff = compare_backup_to_db(conn, backup)
    finally:
        conn.close()
    assert diff["objects"]["added"] == 0
    assert diff["objects"]["removed"] == 1   # OBJ_0002 nur in der DB
    assert diff["objects"]["unchanged"] == 1


def test_compare_db_modified_objekte(tmp_path):
    """Objekte mit anderem Inhalt im Backup als in der DB zaehlen als ``modified``.

    Listet die modified obj_ids identisch zu compare_backups (max 100,
    sortiert) - Restore wuerde diese Stuecke mit dem Backup-Stand
    ueberschreiben.
    """
    db_file = tmp_path / "db.sqlite3"
    conn = open_db(db_file)
    conn.execute("INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
                 ("OBJ_0001", "DB-Name"))
    conn.commit()

    backup = tmp_path / "backup.json"
    # Full row mit allen Spalten, damit nur Name den Diff ausmacht.
    db_row = conn.execute("SELECT * FROM objects WHERE obj_id=?",
                          ("OBJ_0001",)).fetchone()
    changed = dict(db_row)
    changed["Name"] = "Backup-Name"
    _write(backup, {
        "objects": [changed],
        "images": [], "aliases": [], "ki_analysen": [],
    })
    try:
        diff = compare_backup_to_db(conn, backup)
    finally:
        conn.close()
    assert diff["objects"]["modified"] == 1
    assert diff["objects"]["unchanged"] == 0
    assert diff["objects"]["modified_obj_ids"] == ["OBJ_0001"]


def test_compare_db_kaputtes_backup_wirft(tmp_path):
    """Spiegelt test_compare_kaputtes_backup_wirft auf die DB-Achse."""
    db_file = tmp_path / "db.sqlite3"
    conn = open_db(db_file)
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("nicht json", encoding="utf-8")
    try:
        with pytest.raises(ValueError):
            compare_backup_to_db(conn, kaputt)
    finally:
        conn.close()


def test_compare_db_images_aliases(tmp_path):
    """images/aliases werden ueber id/alias_id verglichen, analog compare_backups."""
    db_file = tmp_path / "db.sqlite3"
    conn = open_db(db_file)
    conn.execute("INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
                 ("OBJ_0001", "x"))
    conn.execute(
        "INSERT INTO images (id, obj_id, kategorie, rel_path) "
        "VALUES (1, 'OBJ_0001', 'uebersicht', 'a.jpg')")
    conn.execute(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES ('ALT_01', 'OBJ_0001')")
    conn.commit()

    backup = tmp_path / "backup.json"
    _write(backup, {
        "objects": [{"obj_id": "OBJ_0001", "Name": "x"}],
        "images": [
            {"id": 1, "obj_id": "OBJ_0001", "kategorie": "uebersicht", "rel_path": "a.jpg"},
            {"id": 2, "obj_id": "OBJ_0001", "kategorie": "kamera", "rel_path": "b.jpg"},
        ],
        "aliases": [
            {"alias_id": "ALT_02", "canonical_id": "OBJ_0001"},
        ],
        "ki_analysen": [],
    })
    try:
        diff = compare_backup_to_db(conn, backup)
    finally:
        conn.close()
    assert diff["images"]["added"] == 1     # id=2 ist nur im Backup
    assert diff["images"]["removed"] == 0
    assert diff["images"]["unchanged"] == 1
    assert diff["aliases"]["added"] == 1    # ALT_02 nur im Backup
    assert diff["aliases"]["removed"] == 1  # ALT_01 nur in der DB


def test_cli_compare_db_gibt_json(tmp_path, capsys):
    """CLI compare-db: gibt das JSON-Diff aus, Exit 0 (spiegelt _cmd_compare)."""
    db_file = tmp_path / "db.sqlite3"
    conn = open_db(db_file)
    conn.execute("INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
                 ("OBJ_0001", "DB"))
    conn.commit()
    conn.close()

    backup = tmp_path / "backup.json"
    _write(backup, {"objects": [{"obj_id": "OBJ_0002"}]})

    code = main(["compare-db", str(backup), "--db", str(db_file)])
    assert code == 0
    diff = json.loads(capsys.readouterr().out)
    assert diff["objects"]["added"] == 1   # OBJ_0002 im Backup, fehlt in DB
    assert diff["objects"]["removed"] == 1  # OBJ_0001 in DB, fehlt im Backup


def test_cli_compare_db_fehlende_db(tmp_path, capsys):
    """CLI compare-db: fehlende DB -> Exit 2 (spiegelt write/restore-Pfad)."""
    backup = tmp_path / "backup.json"
    _write(backup, {"objects": []})
    fehlt = tmp_path / "fehlt.sqlite3"
    code = main(["compare-db", str(backup), "--db", str(fehlt)])
    assert code == 2
