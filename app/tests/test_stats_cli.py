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


def test_text_ausgabe_zeigt_durchschnitt_und_median_wert_gewicht(tmp_path, capsys):
    """Ø/Median Wert + Ø/Median/Max Gewicht stehen unter den Summenzeilen."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "avg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 100.0, 10.0),
            ("OBJ_0002", 200.0, 30.0),
            ("OBJ_0003", 600.0, 200.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Ø Wert (CHF):" in out
    assert "Median Wert (CHF):" in out
    assert "Ø Gewicht (g):" in out
    assert "Median Gewicht (g):" in out
    assert "Maximales Gewicht:" in out
    # Median Wert = mittlerer von [100, 200, 600] = 200
    assert "200" in out
    # Max Gewicht = 200
    assert "200.0" in out


def test_text_ausgabe_ohne_werte_keine_durchschnitt_zeilen(tmp_path, capsys):
    """Ohne Wert/Gewicht erscheinen die Durchschnitt-/Median-Zeilen nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "leer.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Ø Wert" not in out
    assert "Median Wert" not in out
    assert "Ø Gewicht" not in out
    assert "Median Gewicht" not in out


def test_text_ausgabe_zeigt_coverage_quoten(tmp_path, capsys):
    """Coverage-Block zeigt Bild-/Funddatum-/Wert-Quoten als Sammler-Coverage."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "cov.sqlite3"
    c = open_db(db_file)
    # 4 Objekte: 2 mit Bild (50%), 1 mit Funddatum (25%), 2 mit Wert (50%)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh) VALUES (?,?,?)",
        [
            ("OBJ_0001", "2024-06-13", 100.0),
            ("OBJ_0002", None, 50.0),
            ("OBJ_0003", None, None),
            ("OBJ_0004", None, None),
        ],
    )
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        [("OBJ_0001", "Kamera", "a.jpg"), ("OBJ_0002", "Kamera", "b.jpg")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    # Drei Quoten in einer 50/25/50-Konstellation
    assert "50.0 %" in out
    assert "25.0 %" in out


def test_text_ausgabe_ohne_objekte_keine_coverage(tmp_path, capsys):
    """Leere DB: Coverage-Block ausgelassen (Quoten waeren None)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "leer.sqlite3"
    c = open_db(db_file)
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" not in out


def test_text_ausgabe_zeigt_bilder_pro_kategorie(tmp_path, capsys):
    """Bilder-pro-Kategorie-Block zeigt Foto-Coverage je Aufnahme-Art."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "bk.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg"),
            ("OBJ_0001", "Kamera", "b.jpg"),
            ("OBJ_0001", "Mikroskop", "c.jpg"),
            ("OBJ_0001", "UV365", "d.jpg"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Bilder pro Kategorie:" in out
    assert "Kamera" in out
    assert "Mikroskop" in out
    assert "UV365" in out


def test_text_ausgabe_ohne_bilder_keine_kategorie_zeile(tmp_path, capsys):
    """Ohne indexierte Bilder erscheint der Kategorie-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "nob.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Bilder pro Kategorie:" not in out


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
