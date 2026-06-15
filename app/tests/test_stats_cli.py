"""CLI fuer die Statistik-Ausgabe."""
import json
from pathlib import Path

import pytest

from stonebook.db.stats_cli import main
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def test_text_ausgabe(migrated_db, capsys):
    exit_code = main(["--db", str(migrated_db)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Objekte gesamt:" in out
    assert "546" in out
    assert "Bilder:" in out
    assert "Top-Minerale:" in out


def test_text_ausgabe_zeigt_confidence_buckets(migrated_db, capsys):
    """Confidence-Verteilung wird in den Text-Bericht aufgenommen, sobald Werte da sind."""
    main(["--db", str(migrated_db)])
    out = capsys.readouterr().out
    assert "Confidence-Verteilung:" in out
    # Mindestens ein Klassenlabel im Output
    assert "75-100" in out or "0-24" in out or "ohne" in out


def test_json_ausgabe(migrated_db, capsys):
    exit_code = main(["--db", str(migrated_db), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["objekte_total"] == 546
    assert payload["bilder_total"] == 63
    assert payload["aliase_total"] == 54
    assert "by_mineral" in payload
    # Buckets sind in der JSON-Form enthalten (Dashboard/Reports lesen das hier)
    assert "confidence_buckets" in payload
    assert set(payload["confidence_buckets"]) == {"ohne", "0-24", "25-49", "50-74", "75-100"}


def test_fehlende_db_exit_2(tmp_path, capsys):
    exit_code = main(["--db", str(tmp_path / "fehlt.sqlite3")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err
