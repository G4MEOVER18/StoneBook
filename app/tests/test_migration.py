"""End-to-End-Migration gegen das echte Repo (read-only auf Quellen, DB in tmp)."""
from pathlib import Path

import pytest

from stonebook.db.database import connect
from stonebook.migration.image_indexer import folder_category
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    report = migrate(REPO, db_file, log=lambda *_: None)
    conn = connect(db_file)
    yield conn, report
    conn.close()


def test_kennzahlen(migrated):
    _, report = migrated
    assert report["objekte"] == 546        # 600 - 54 Aliase
    assert report["aliase"] == 54
    assert report["bilder"] == 63          # Bilder unter objects\ (legacy/docs zählen nicht)
    assert report["parse_fehler"] == 0
    assert 0 < report["aktiv"] < 100       # nur dokumentierte Objekte sind aktiv


def test_obj43_felder(migrated):
    conn, _ = migrated
    row = conn.execute("SELECT * FROM objects WHERE obj_id = 'OBJ_0043'").fetchone()
    assert row is not None
    assert "Quarz" in row["Mineral_Primaer"]
    assert row["Gewicht_g"] == 41.0
    assert row["status"] == "aktiv"


def test_obj44_ist_alias_von_43(migrated):
    conn, _ = migrated
    assert conn.execute("SELECT 1 FROM objects WHERE obj_id = 'OBJ_0044'").fetchone() is None
    row = conn.execute("SELECT canonical_id FROM aliases WHERE alias_id = 'OBJ_0044'").fetchone()
    assert row["canonical_id"] == "OBJ_0043"


def test_obj1_bilder_kategorien(migrated):
    conn, _ = migrated
    cats = {r[0] for r in conn.execute(
        "SELECT DISTINCT kategorie FROM images WHERE obj_id = 'OBJ_0001'")}
    assert {"Kamera", "Mikroskop", "Sonderaufnahmen", "UV395"} <= cats


def test_alias_bilder_umgehaengt(migrated):
    conn, _ = migrated
    # OBJ_0002 ist Alias von OBJ_0001 — dessen Bilder hängen am Kanon mit Herkunft
    rows = conn.execute(
        "SELECT COUNT(*) FROM images WHERE obj_id = 'OBJ_0001' AND herkunft_obj_id = 'OBJ_0002'"
    ).fetchone()
    assert rows[0] > 0


def test_fts_suche(migrated):
    conn, _ = migrated
    rows = conn.execute(
        "SELECT obj_id FROM objects WHERE rowid IN "
        "(SELECT rowid FROM objects_fts WHERE objects_fts MATCH '\"Jaspis\"*')").fetchall()
    ids = {r[0] for r in rows}
    assert "OBJ_0001" in ids


def test_folder_category_mapping():
    assert folder_category("Übersicht") == "Uebersicht"
    assert folder_category("uebersicht") == "Uebersicht"
    assert folder_category("Kamera") == "Kamera"
    assert folder_category("UV 365 nm") == "UV365"
    assert folder_category("UV365") == "UV365"
    assert folder_category("UV 395 nm") == "UV395"
    assert folder_category("Sonderaufnahmen") == "Sonderaufnahmen"
    assert folder_category("  Mikroskop  ") == "Mikroskop"
    assert folder_category("blabla") == "Sonstige"
    # Mojibake-Form aus dem Repo
    assert folder_category("├£bersicht") == "Uebersicht"


def test_platzhalter_status(migrated):
    conn, _ = migrated
    row = conn.execute("SELECT status FROM objects WHERE obj_id = 'OBJ_0500'").fetchone()
    assert row["status"] == "platzhalter"


def test_main_cli_report_json(tmp_path, capsys):
    """CLI ``--report-json`` schreibt ausschliesslich gueltiges JSON auf stdout."""
    import json

    from stonebook.migration.migrate import main
    db_file = tmp_path / "cli.sqlite3"
    exit_code = main([str(REPO), "--db", str(db_file), "--report-json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["objekte"] == 546
    assert report["aliase"] == 54
    assert report["bilder"] == 63
    assert db_file.is_file()


def test_main_cli_quiet_kein_progress(tmp_path, capsys):
    """``--quiet`` unterdrueckt die Schritt-Logs (kein '1/5 ...' auf stdout)."""
    from stonebook.migration.migrate import main
    db_file = tmp_path / "q.sqlite3"
    main([str(REPO), "--db", str(db_file), "--quiet"])
    out = capsys.readouterr().out
    assert "1/5" not in out
    assert "Fertig" not in out


def test_main_cli_fehlerhaftes_repo(tmp_path, capsys):
    """Beim nicht-existenten Repo: exit 1, Fehlermeldung auf stderr."""
    from stonebook.migration.migrate import main
    exit_code = main([str(tmp_path), "--db", str(tmp_path / "x.sqlite3")])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "Kein StoneBook-Repo" in err
