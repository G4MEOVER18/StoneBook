"""validate_backup: prueft Konsistenz eines Backups ohne Restore.

Komplement zu inspect_backup, das nur Counts zeigt: validate_backup findet
referenzielle Probleme (orphan FK, doppelte IDs, leere IDs), die beim
import_json erst durch SQLite-FK-Verstoesse auffallen wuerden - dann ist
aber die Ziel-DB schon geleert.
"""
import gzip
import json
from pathlib import Path

import pytest

from stonebook.export.backup_cli import main
from stonebook.export.json_export import (export_json, validate_backup,
                                          write_rotated_backup)
from stonebook.migration.migrate import migrate
from stonebook.db.database import connect

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def clean_backup(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    conn = connect(db_file)
    backup = tmp_path_factory.mktemp("bk") / "clean.json"
    export_json(conn, backup)
    conn.close()
    return backup


def _write_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_sauberes_backup_ist_valide(clean_backup):
    info = validate_backup(clean_backup)
    assert info["ok"] is True
    assert info["errors"] == []
    assert info["counts"]["objects"] == 546
    assert info["counts"]["images"] == 63
    assert info["counts"]["aliases"] == 54


def test_doppelte_obj_id_wird_erkannt(tmp_path):
    p = tmp_path / "dup.json"
    _write_payload(p, {
        "objects": [
            {"obj_id": "OBJ_0001", "Name": "Erstes"},
            {"obj_id": "OBJ_0001", "Name": "Zweites"},
        ],
        "images": [],
        "aliases": [],
        "ki_analysen": [],
    })
    info = validate_backup(p)
    assert info["ok"] is False
    assert any("doppelte obj_id" in e and "OBJ_0001" in e for e in info["errors"])


def test_leere_obj_id_wird_erkannt(tmp_path):
    p = tmp_path / "leer.json"
    _write_payload(p, {
        "objects": [
            {"obj_id": "", "Name": "Leer"},
            {"obj_id": None, "Name": "None"},
            {"Name": "Fehlt"},
        ],
    })
    info = validate_backup(p)
    assert info["ok"] is False
    msgs = "\n".join(info["errors"])
    assert "objects[0]" in msgs
    assert "objects[1]" in msgs
    assert "objects[2]" in msgs


def test_orphan_image_wird_erkannt(tmp_path):
    p = tmp_path / "orphan.json"
    _write_payload(p, {
        "objects": [{"obj_id": "OBJ_0001"}],
        "images": [
            {"obj_id": "OBJ_0001", "kategorie": "Uebersicht",
             "rel_path": "a.jpg"},
            {"obj_id": "OBJ_9999", "kategorie": "Uebersicht",
             "rel_path": "b.jpg"},  # orphan
        ],
        "aliases": [],
    })
    info = validate_backup(p)
    assert info["ok"] is False
    msgs = "\n".join(info["errors"])
    assert "images[1]" in msgs and "OBJ_9999" in msgs
    assert "images[0]" not in msgs  # erste Zeile ist sauber


def test_orphan_alias_wird_erkannt(tmp_path):
    p = tmp_path / "orphan_alias.json"
    _write_payload(p, {
        "objects": [{"obj_id": "OBJ_0001"}],
        "aliases": [
            {"alias_id": "OBJ_0002", "canonical_id": "OBJ_0001"},
            {"alias_id": "OBJ_0003", "canonical_id": "OBJ_9999"},
        ],
    })
    info = validate_backup(p)
    assert info["ok"] is False
    msgs = "\n".join(info["errors"])
    assert "aliases[1]" in msgs and "OBJ_9999" in msgs


def test_alias_kollidiert_mit_obj_id(tmp_path):
    """alias_id darf nicht gleichzeitig als kanonisches Objekt existieren."""
    p = tmp_path / "kollision.json"
    _write_payload(p, {
        "objects": [
            {"obj_id": "OBJ_0001"},
            {"obj_id": "OBJ_0002"},
        ],
        "aliases": [
            # OBJ_0002 ist sowohl Alias als auch eigenstaendiges Objekt
            {"alias_id": "OBJ_0002", "canonical_id": "OBJ_0001"},
        ],
    })
    info = validate_backup(p)
    assert info["ok"] is False
    assert any("kollidiert" in e and "OBJ_0002" in e for e in info["errors"])


def test_leere_alias_felder(tmp_path):
    p = tmp_path / "leer_alias.json"
    _write_payload(p, {
        "objects": [{"obj_id": "OBJ_0001"}],
        "aliases": [
            {"alias_id": "", "canonical_id": "OBJ_0001"},
            {"alias_id": "OBJ_0002", "canonical_id": None},
        ],
    })
    info = validate_backup(p)
    assert info["ok"] is False
    msgs = "\n".join(info["errors"])
    assert "alias_id leer" in msgs
    assert "canonical_id leer" in msgs


def test_orphan_ki_analyse_wird_erkannt(tmp_path):
    p = tmp_path / "orphan_ki.json"
    _write_payload(p, {
        "objects": [{"obj_id": "OBJ_0001"}],
        "ki_analysen": [
            {"obj_id": "OBJ_0001", "modell": "test", "antwort_json": "{}"},
            {"obj_id": "OBJ_9999", "modell": "test", "antwort_json": "{}"},
        ],
    })
    info = validate_backup(p)
    assert info["ok"] is False
    msgs = "\n".join(info["errors"])
    assert "ki_analysen[1]" in msgs and "OBJ_9999" in msgs


def test_validate_akzeptiert_gzipped_backup(tmp_path):
    """Gzipte .json.gz-Backups werden symmetrisch zu inspect_backup gelesen."""
    p = tmp_path / "kleines.json.gz"
    payload = {
        "objects": [{"obj_id": "OBJ_0001"}],
        "images": [{"obj_id": "OBJ_0001", "kategorie": "X",
                    "rel_path": "x.jpg"}],
        "aliases": [],
    }
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    info = validate_backup(p)
    assert info["ok"] is True
    assert info["counts"]["objects"] == 1


def test_validate_korruptes_backup_wirft_value_error(tmp_path):
    p = tmp_path / "kaputt.json"
    p.write_text("kein json", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_backup(p)


def test_cli_validate_exit_0_bei_sauber(clean_backup, capsys):
    code = main(["validate", str(clean_backup)])
    assert code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["ok"] is True
    assert info["errors"] == []


def test_cli_validate_exit_1_bei_fehler(tmp_path, capsys):
    p = tmp_path / "kaputt.json"
    _write_payload(p, {
        "objects": [{"obj_id": "OBJ_0001"}],
        "images": [{"obj_id": "OBJ_X", "kategorie": "X", "rel_path": "x.jpg"}],
    })
    code = main(["validate", str(p)])
    assert code == 1
    info = json.loads(capsys.readouterr().out)
    assert info["ok"] is False
    assert info["errors"]


def test_rotated_backup_bleibt_valide(tmp_path):
    """write_rotated_backup produziert per Definition ein konsistentes Backup."""
    db_file = tmp_path / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    conn = connect(db_file)
    backup_path = write_rotated_backup(conn, tmp_path / "backups")
    conn.close()
    info = validate_backup(backup_path)
    assert info["ok"] is True, info["errors"]
