"""compare_backups: Diff-Stats zwischen zwei Backups (added/removed/modified)."""
import json
from pathlib import Path

import pytest

from stonebook.db.database import connect
from stonebook.export.backup_cli import main
from stonebook.export.json_export import compare_backups, export_json
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
