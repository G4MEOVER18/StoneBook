"""CLI fuer die Wartung der DB (size/check/vacuum)."""
import json

from stonebook.db.database import open_db
from stonebook.db.maintenance_cli import main
from stonebook.db.repository import ObjectRepo


def test_size_text(tmp_path, capsys):
    db_file = tmp_path / "s.sqlite3"
    open_db(db_file).close()
    exit_code = main(["size", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Logisch:" in out
    assert "Datei (mit WAL):" in out
    assert "Free-Pages:" in out


def test_size_json(tmp_path, capsys):
    db_file = tmp_path / "sj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["size", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["db_file"] == str(db_file)
    assert info["logical_bytes"] > 0
    assert info["file_bytes"] > 0
    assert info["free_pages"] == 0


def test_check_text_ok(tmp_path, capsys):
    db_file = tmp_path / "c.sqlite3"
    open_db(db_file).close()
    exit_code = main(["check", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_check_json_ok(tmp_path, capsys):
    db_file = tmp_path / "cj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["check", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True, "messages": []}


def test_deepcheck_text_ok(tmp_path, capsys):
    """deepcheck Subcommand: leere DB → OK + Exit 0 (spiegelt check)."""
    db_file = tmp_path / "dc.sqlite3"
    open_db(db_file).close()
    exit_code = main(["deepcheck", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_deepcheck_json_ok(tmp_path, capsys):
    """deepcheck Subcommand JSON: leere DB → ok=True, messages=[] (spiegelt check)."""
    db_file = tmp_path / "dcj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["deepcheck", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True, "messages": []}


def test_fkcheck_text_ok(tmp_path, capsys):
    """fkcheck Subcommand: leere DB → OK + Exit 0 (spiegelt check)."""
    db_file = tmp_path / "fkc.sqlite3"
    open_db(db_file).close()
    exit_code = main(["fkcheck", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_fkcheck_json_ok(tmp_path, capsys):
    """fkcheck Subcommand JSON: leere DB → ok=True, violations=[] (spiegelt check)."""
    db_file = tmp_path / "fkcj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["fkcheck", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True, "violations": []}


def test_fkcheck_meldet_orphan(tmp_path, capsys):
    """fkcheck Subcommand: durch FK-OFF eingefuegter Orphan → Exit 1 + Verletzung im Output.

    Spiegelt das ``foreign_key_check_orphan_image_erkannt``-Pattern aus
    :mod:`tests.test_maintenance` auf den CLI-Pfad: Orphan im JSON-Output und
    Exit-Code 1 (geeignet fuer Cron/CI, parallel zum quick_check).
    """
    db_file = tmp_path / "fk_orph_cli.sqlite3"
    c = open_db(db_file)
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        ("OBJ_0099_ghost", "Kamera", "objects/OBJ_0099/foto.jpg"),
    )
    c.commit()
    c.close()
    exit_code = main(["fkcheck", "--db", str(db_file), "--json"])
    assert exit_code == 1
    info = json.loads(capsys.readouterr().out)
    assert info["ok"] is False
    assert len(info["violations"]) == 1
    v = info["violations"][0]
    assert v["table"] == "images"
    assert v["parent_table"] == "objects"
    assert isinstance(v["rowid"], int)


def test_vacuum_text(tmp_path, capsys):
    db_file = tmp_path / "v.sqlite3"
    c = open_db(db_file)
    repo = ObjectRepo(c)
    for i in range(1, 101):
        repo.create(f"OBJ_{i:04d}", Name=f"Name {i}" * 30)
    c.execute("DELETE FROM objects")
    c.commit()
    c.close()
    exit_code = main(["vacuum", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "VACUUM abgeschlossen" in out


def test_vacuum_json(tmp_path, capsys):
    db_file = tmp_path / "vj.sqlite3"
    c = open_db(db_file)
    repo = ObjectRepo(c)
    for i in range(1, 51):
        repo.create(f"OBJ_{i:04d}", Name=f"Name {i}" * 30)
    c.execute("DELETE FROM objects")
    c.commit()
    c.close()
    exit_code = main(["vacuum", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["before_bytes"] >= info["after_bytes"]
    assert info["saved_bytes"] == info["before_bytes"] - info["after_bytes"]


def test_fehlende_db_datei(tmp_path, capsys):
    """Nicht-existente DB → Exit 2 mit Hinweis auf stderr."""
    bad = tmp_path / "nope.sqlite3"
    exit_code = main(["size", "--db", str(bad)])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "fehlt" in err
