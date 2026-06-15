"""CLI fuer JSON-Backup-Verwaltung."""
import json
from pathlib import Path

import pytest

from stonebook.export.backup_cli import main
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def test_write_list_und_restore_round_trip(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "backups"
    # 1) write
    exit_code = main(["write", "--backup-dir", str(backup_dir),
                      "--db", str(migrated_db), "--keep", "3"])
    assert exit_code == 0
    written = Path(capsys.readouterr().out.strip())
    assert written.is_file()
    assert written.suffix == ".gz"
    assert written.parent == backup_dir

    # 2) list zeigt das eine Backup
    exit_code = main(["list", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    listed = [Path(p) for p in capsys.readouterr().out.splitlines()]
    assert listed == [written]

    # 3) restore in eine neue DB
    new_db = tmp_path / "restored.sqlite3"
    exit_code = main(["restore", str(written), "--db", str(new_db)])
    assert exit_code == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts == {"objects": 546, "images": 63, "aliases": 54}


def test_write_no_compress(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "no_gz"
    exit_code = main(["write", "--backup-dir", str(backup_dir),
                      "--db", str(migrated_db), "--no-compress"])
    assert exit_code == 0
    p = Path(capsys.readouterr().out.strip())
    assert p.suffix == ".json"


def test_inspect_zeigt_counts(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "i"
    main(["write", "--backup-dir", str(backup_dir),
          "--db", str(migrated_db)])
    written = Path(capsys.readouterr().out.strip())
    main(["inspect", str(written)])
    info = json.loads(capsys.readouterr().out)
    assert info["counts"] == {"objects": 546, "images": 63, "aliases": 54}
    assert "meta" in info


def test_prune_loescht_alte_backups(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "p"
    backup_dir.mkdir()
    # Drei Pseudo-Backups mit unterschiedlichem Zeitstempel
    paths = []
    for stamp in ("20240101_000000", "20240102_000000", "20240103_000000"):
        p = backup_dir / f"stonebook_backup_{stamp}.json.gz"
        p.write_bytes(b"")
        paths.append(p)
    exit_code = main(["prune", "--backup-dir", str(backup_dir), "--keep", "1"])
    assert exit_code == 0
    # Die zwei aeltesten geloescht; nur das neueste bleibt
    assert paths[0].exists() is False
    assert paths[1].exists() is False
    assert paths[2].exists() is True


def test_restore_fordert_force_bei_existierender_db(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "f"
    main(["write", "--backup-dir", str(backup_dir),
          "--db", str(migrated_db)])
    backup = Path(capsys.readouterr().out.strip())

    existing = tmp_path / "existing.sqlite3"
    existing.write_bytes(b"placeholder")
    exit_code = main(["restore", str(backup), "--db", str(existing)])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "existiert" in err

    # Mit --force klappt es
    exit_code = main(["restore", str(backup), "--db", str(existing), "--force"])
    assert exit_code == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts["objects"] == 546


def test_write_fehlende_db_exit_2(tmp_path, capsys):
    exit_code = main(["write",
                      "--backup-dir", str(tmp_path / "x"),
                      "--db", str(tmp_path / "fehlt.sqlite3")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err
