from pathlib import Path

import pytest

from stonebook.db.database import connect
from stonebook.db.repository import ObjectRepo
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def objects(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    conn = connect(db_file)
    yield ObjectRepo(conn)
    conn.close()


def test_statistics_struktur(objects):
    s = objects.statistics()
    assert s["gesamt"] == 546
    assert s["aliase"] == 54
    assert s["bilder_gesamt"] == 63
    assert s["mit_bildern"] > 0
    assert isinstance(s["top_minerals"], list)
    assert s["status"]["platzhalter"] > 0
    # Quarz/Jaspis sollte unter den Top-Mineralen sein
    names = " ".join(name for name, _ in s["top_minerals"]).lower()
    assert "quarz" in names or "jaspis" in names
