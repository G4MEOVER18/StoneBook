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
