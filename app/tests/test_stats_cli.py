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


def test_text_ausgabe_zeigt_median_confidence(tmp_path, capsys):
    """Median-Confidence-Zeile erscheint, sobald gueltige Werte vorliegen."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "mc.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 60), ("OBJ_0002", 80), ("OBJ_0003", 90)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Median Confidence:" in out
    assert "80.0" in out


def test_text_ausgabe_ohne_confidence_keine_median_zeile(tmp_path, capsys):
    """Ohne gueltige Werte erscheint die Median-Zeile gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "noc.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", None), ("OBJ_0002", None)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Median Confidence:" not in out


def test_text_ausgabe_zeigt_top_wert_und_gewicht(tmp_path, capsys):
    """Top-Wertobjekte und Top-Gewichtsobjekte erscheinen im Text-Bericht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tw.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Name, Wert_CHF_roh, Gewicht_g) VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", "Citrindruse",  1500.0, 250.0),
            ("OBJ_0002", "Bergkristall",   50.0,  10.0),
            ("OBJ_0003", "Pyritrose",   None,   500.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Wertobjekte" in out
    assert "Citrindruse" in out
    assert "Top-Gewichtsobjekte" in out
    assert "Pyritrose" in out


def test_text_ausgabe_ohne_werte_keine_top_listen(tmp_path, capsys):
    """Leere DB → keine Top-Listen (Format bleibt schlank)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "leer.sqlite3"
    c = open_db(db_file)
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Wertobjekte" not in out
    assert "Top-Gewichtsobjekte" not in out


def test_text_ausgabe_zeigt_ki_analysen(migrated_db, capsys):
    """KI-Analysen-Zeile gibt total + Objekte + uebernommene aus."""
    main(["--db", str(migrated_db)])
    out = capsys.readouterr().out
    assert "KI-Analysen:" in out
    assert "uebernommen" in out


def test_text_ausgabe_zeigt_funddatum_spanne(tmp_path, capsys):
    """Funddatum-Spanne erscheint in der Text-Ausgabe, sobald ein gueltiges Datum vorliegt."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "spanne.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", "2019-01-01"), ("OBJ_0002", "2024-12-31")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funddatum-Spanne:" in out
    assert "2019-01-01" in out
    assert "2024-12-31" in out


def test_text_ausgabe_ohne_funddatum_keine_spanne_zeile(tmp_path, capsys):
    """Bei DB ohne gueltige Funddaten erscheint die Spanne-Zeile gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "leer.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", None), ("OBJ_0002", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funddatum-Spanne:" not in out


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
