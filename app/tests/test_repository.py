"""list_objects: Filter und Sortierung gegen die migrierte DB."""
from pathlib import Path

import pytest

from stonebook.db.database import connect
from stonebook.db.repository import ObjectRepo
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    c = connect(db_file)
    yield ObjectRepo(c)
    c.close()


def test_default_sort_obj_id(repo):
    rows = repo.list_objects(status="aktiv")
    ids = [r["obj_id"] for r in rows]
    assert ids == sorted(ids)


def test_sort_by_confidence_desc(repo):
    rows = repo.list_objects(status="aktiv", sort_by="Confidence_Prozent", sort_desc=True)
    confs = [r["Confidence_Prozent"] for r in rows if r["Confidence_Prozent"] is not None]
    assert confs == sorted(confs, reverse=True)


def test_sort_by_bilder_desc(repo):
    rows = repo.list_objects(sort_by="bilder", sort_desc=True)
    counts = [r["bilder"] for r in rows]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] >= 1


def test_sort_invalid_column_raises(repo):
    with pytest.raises(ValueError):
        repo.list_objects(sort_by="; DROP TABLE objects --")


def test_sort_by_erstellt_am_desc(tmp_path):
    """Sortierung nach Erstellzeit liefert neueste Objekte zuerst."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ea.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-01-01 10:00:00"),
            ("OBJ_0002", "2024-06-13 10:00:00"),
            ("OBJ_0003", "2024-03-15 10:00:00"),
            ("OBJ_0004", None),  # NULL → ans Ende
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="erstellt_am", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0002", "OBJ_0003", "OBJ_0001"]
    # NULL bleibt am Ende
    assert rows[-1]["obj_id"] == "OBJ_0004"
    c.close()


def test_min_confidence_filter(repo):
    rows = repo.list_objects(min_confidence=70)
    assert rows
    for r in rows:
        assert r["Confidence_Prozent"] is not None and r["Confidence_Prozent"] >= 70


def test_min_confidence_high_eliminates_all_platzhalter(repo):
    rows = repo.list_objects(status="platzhalter", min_confidence=10)
    assert rows == []


def test_max_confidence_filter(tmp_path):
    """max_confidence findet Objekte zum Nachpruefen (NULL-Confidence faellt raus)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 95),
            ("OBJ_0002", 50),
            ("OBJ_0003", 30),
            ("OBJ_0004", None),  # ohne Bewertung → faellt aus <=-Filter raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(max_confidence=60)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # Bereich 40..60
    rows = repo.list_objects(min_confidence=40, max_confidence=60)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_has_confidence_filter(tmp_path):
    """has_confidence=False findet noch nicht analysierte Objekte."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 85),
            ("OBJ_0002", 50),
            ("OBJ_0003", None),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_confidence=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_confidence=False)] \
        == ["OBJ_0003", "OBJ_0004"]
    c.close()


def test_has_mineral_filter(tmp_path):
    """has_mineral findet noch nicht mineralogisch identifizierte Objekte."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer) VALUES (?, ?)",
        [
            ("OBJ_0001", "Quarz"),
            ("OBJ_0002", "Calcit"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),       # leer zaehlt wie None
            ("OBJ_0005", "   "),    # nur Whitespace zaehlt wie None
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_mineral=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_mineral=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    # None laesst alle durch
    assert len(repo.list_objects(has_mineral=None)) == 5
    c.close()


def test_has_pruefempfehlungen_filter(tmp_path):
    """has_pruefempfehlungen findet Objekte mit offenen Bestaetigungstests."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hp.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Pruefempfehlungen) VALUES (?, ?)",
        [
            ("OBJ_0001", "Strichprobe noch ausstehend"),
            ("OBJ_0002", "Saeuretest mit HCl 10%"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_pruefempfehlungen=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_pruefempfehlungen=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_pruefempfehlungen=None)) == 5
    c.close()


def test_has_gewicht_filter(tmp_path):
    """has_gewicht trennt gewogene Objekte von ungewogenen; 0/negativ zaehlt wie 'ohne'."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [
            ("OBJ_0001", 125.5),
            ("OBJ_0002", 0.1),
            ("OBJ_0003", None),
            ("OBJ_0004", 0.0),     # 0 zaehlt wie 'nicht gewogen'
            ("OBJ_0005", -1.0),    # negative Werte ebenso (defensiv; sollte nicht auftreten)
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_gewicht=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_gewicht=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    # None laesst alle durch
    assert len(repo.list_objects(has_gewicht=None)) == 5
    c.close()


def test_has_wert_filter(tmp_path):
    """has_wert nutzt die Summe aller CHF-Wertfelder (analog statistics.objekte_mit_wert)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hw.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh, Wert_CHF_poliert, "
        "Wert_CHF_Schmuck, Marktwert_Industrie, Wissenschaftlicher_Wert_CHF) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", 100.0, None, None, None, None),     # rein roh
            ("OBJ_0002", None, 50.0, 200.0, None, None),     # zwei Felder gesetzt
            ("OBJ_0003", None, None, None, None, None),      # gar nichts
            ("OBJ_0004", 0.0, 0.0, 0.0, 0.0, 0.0),           # alles 0 zaehlt wie 'ohne Wert'
            ("OBJ_0005", None, None, None, 10.5, None),      # nur Industrie
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_wert=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    assert [r["obj_id"] for r in repo.list_objects(has_wert=False)] \
        == ["OBJ_0003", "OBJ_0004"]
    # None laesst alle durch
    assert len(repo.list_objects(has_wert=None)) == 5
    c.close()


def test_has_notizen_filter(tmp_path):
    """has_notizen unterscheidet dokumentierte von undokumentierten Objekten."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hn.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, notizen) VALUES (?, ?)",
        [
            ("OBJ_0001", "Fund am Sitterufer 2024"),
            ("OBJ_0002", "Vermutlich Pyrit-Einschluss"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),         # leer zaehlt wie None
            ("OBJ_0005", "   "),      # nur Whitespace zaehlt wie None
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_notizen=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_notizen=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_notizen=None)) == 5
    c.close()


def test_has_funddatum_false_default(repo):
    # Testdaten enthalten kein Funddatum → has_funddatum=True liefert nichts
    assert repo.list_objects(has_funddatum=True) == []
    # has_funddatum=False muss komplett die DB enthalten
    assert len(repo.list_objects(has_funddatum=False)) == 546


def test_only_images_filter(repo):
    rows = repo.list_objects(only_images=True)
    assert rows
    for r in rows:
        assert r["bilder"] >= 1


def test_has_bilder_false_findet_objekte_ohne_bilder(repo):
    """has_bilder=False ist der Workflow-Filter 'noch fotografieren'."""
    rows = repo.list_objects(has_bilder=False)
    assert rows
    for r in rows:
        assert r["bilder"] == 0
    # Disjunktion mit has_bilder=True ergibt Gesamtmenge
    with_imgs = repo.list_objects(has_bilder=True)
    assert len(rows) + len(with_imgs) == repo.count()


def test_has_bilder_ueberschreibt_only_images(tmp_path):
    """Explizites has_bilder=False schlaegt only_images=True (Default-Konflikt)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hb.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.execute("INSERT INTO images (obj_id, kategorie, rel_path) "
              "VALUES ('OBJ_0001', 'Kamera', 'a.jpg')")
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(only_images=True, has_bilder=False)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_funddatum_iso_range_filter(tmp_path):
    """Tagesgenauer Funddatum-Filter ueber ISO-Strings (lexikographisch)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "fd.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-03-15"),
            ("OBJ_0002", "2024-06-13"),
            ("OBJ_0003", "2024-09-30"),
            ("OBJ_0004", "2025-01-05"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # April..August 2024
    rows = repo.list_objects(funddatum_min="2024-04-01", funddatum_max="2024-08-31")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Alles ab 2024-09
    rows = repo.list_objects(funddatum_min="2024-09-01")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Alles bis Ende 2024
    rows = repo.list_objects(funddatum_max="2024-12-31")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_funddatum_jahr_range_filter(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "y.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2018-05-13"),
            ("OBJ_0002", "2020-08-01"),
            ("OBJ_0003", "2022-01-01"),
            ("OBJ_0004", "2024-11-30"),
            ("OBJ_0005", ""),          # ohne Funddatum → faellt raus
            ("OBJ_0006", "kein-datum"),# ungueltig → faellt raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(funddatum_jahr_min=2020, funddatum_jahr_max=2022)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]

    rows = repo.list_objects(funddatum_jahr_min=2023)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]

    rows = repo.list_objects(funddatum_jahr_max=2018)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_wert_min_max_filter(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh, Wert_CHF_poliert) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 10.0, 20.0),   # 30
            ("OBJ_0002", 100.0, None),  # 100
            ("OBJ_0003", None, 500.0),  # 500
            ("OBJ_0004", None, None),   # 0
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(wert_min=50.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]

    rows = repo.list_objects(wert_min=1.0, wert_max=200.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_sort_by_gesamtwert_chf_desc(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "s.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [
            ("OBJ_0001", 50.0),
            ("OBJ_0002", 200.0),
            ("OBJ_0003", None),
            ("OBJ_0004", 100.0),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="gesamtwert_chf", sort_desc=True)
    # NULL/0 wandert (via COALESCE) auf Wert 0; SELECT-Alias gesamtwert_chf
    # ist niemals NULL durch COALESCE, also alle gleichwertig im NULL-Check.
    werte = [r["gesamtwert_chf"] for r in rows]
    assert werte == sorted(werte, reverse=True)
    assert rows[0]["obj_id"] == "OBJ_0002"
    c.close()


def test_kristallsystem_und_beste_verwendung_filter(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "k.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem, Beste_Verwendung) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "trigonal", "Sammlung"),
            ("OBJ_0002", "trigonal", "Schmuck"),
            ("OBJ_0003", "kubisch", "Sammlung"),
            ("OBJ_0004", "kubisch", "Industrie"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(kristallsystem="trigonal")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(beste_verwendung="Sammlung")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0003"]
    # Beide kombiniert
    rows = repo.list_objects(kristallsystem="kubisch", beste_verwendung="Sammlung")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    c.close()


def test_gewicht_min_max_filter(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [
            ("OBJ_0001", 5.0),
            ("OBJ_0002", 50.0),
            ("OBJ_0003", 500.0),
            ("OBJ_0004", None),     # ohne Gewicht → faellt aus min-Filter raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # nur Min: alles ab 10g
    rows = repo.list_objects(gewicht_min=10.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # nur Max: alles bis 100g (NULL ist nicht <= 100)
    rows = repo.list_objects(gewicht_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Kombination: 10 <= g <= 100
    rows = repo.list_objects(gewicht_min=10.0, gewicht_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_refresh_status_all_setzt_aktiv_und_platzhalter(tmp_path):
    """Bulk-refresh ist semantisch identisch zu pro-Objekt-refresh_status."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "rs.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, status) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Quarz",   "platzhalter"),  # → aktiv (hat Daten)
            ("OBJ_0002", "",        "aktiv"),        # → platzhalter (keine Daten/Bilder)
            ("OBJ_0003", "Calcit",  "aktiv"),        # unveraendert
            ("OBJ_0004", "",        "archiviert"),   # unangetastet
            ("OBJ_0005", "",        "platzhalter"),  # unveraendert (kein Bild, keine Daten)
        ],
    )
    # OBJ_0006: platzhalter, aber mit Bild → aktiv
    c.execute("INSERT INTO objects (obj_id, status) VALUES ('OBJ_0006', 'platzhalter')")
    c.execute("INSERT INTO images (obj_id, kategorie, rel_path) "
              "VALUES ('OBJ_0006', 'Kamera', 'a.jpg')")
    c.commit()
    repo = ObjectRepo(c)
    changed = repo.refresh_status_all()
    assert changed == 3  # OBJ_0001, OBJ_0002, OBJ_0006

    statuses = {r["obj_id"]: r["status"] for r in
                c.execute("SELECT obj_id, status FROM objects").fetchall()}
    assert statuses == {
        "OBJ_0001": "aktiv",
        "OBJ_0002": "platzhalter",
        "OBJ_0003": "aktiv",
        "OBJ_0004": "archiviert",
        "OBJ_0005": "platzhalter",
        "OBJ_0006": "aktiv",
    }
    # Erneuter Aufruf aendert nichts
    assert repo.refresh_status_all() == 0
    c.close()


def test_fundort_filter(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "f.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "Davos"),
            ("OBJ_0002", "Davos"),
            ("OBJ_0003", "Zermatt"),
            ("OBJ_0004", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(fundort="Davos")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_fundort_contains_filter(tmp_path):
    """Substring-Filter findet Sammel-Regionen mit unterschiedlichen Detail-Ortsangaben."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "fc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "St. Gallen, Sitter"),
            ("OBJ_0002", "St. Gallen, Bahnhof"),
            ("OBJ_0003", "Zermatt"),
            ("OBJ_0004", "Davos, Schwarzhorn"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring matched alle St.-Gallen-Eintraege
    rows = repo.list_objects(fundort_contains="St. Gallen")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # ASCII-case-insensitive
    rows = repo.list_objects(fundort_contains="sitter")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Anderer Ort
    rows = repo.list_objects(fundort_contains="Davos")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    # Kombinierbar mit anderen Filtern
    rows = repo.list_objects(fundort_contains="St.", status="platzhalter")
    assert len(rows) == 2  # Default-Status, beide Test-Objekte sind platzhalter
    c.close()


def test_fundort_contains_escaped_metacharacters(tmp_path):
    """LIKE-Metazeichen %%/_ in der Suche treffen wortwoertlich, nicht als Wildcards."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "esc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "Halde 50% Rest"),
            ("OBJ_0002", "Mine_42"),
            ("OBJ_0003", "Davos"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # '%' im Suchstring trifft nur den wortwoertlichen Eintrag
    rows = repo.list_objects(fundort_contains="50%")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # '_' im Suchstring trifft nur den wortwoertlichen Eintrag
    rows = repo.list_objects(fundort_contains="Mine_4")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Ohne Escape wuerde '_' als beliebiges Zeichen interpretiert
    rows = repo.list_objects(fundort_contains="MineX4")
    assert rows == []
    c.close()


def test_name_contains_filter(tmp_path):
    """Substring-Filter ueber Name (Bezeichnung); LIKE-Metazeichen werden escapet."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
        [
            ("OBJ_0001", "Rauchquarz aus Davos"),
            ("OBJ_0002", "Bergkristall aus Davos"),
            ("OBJ_0003", "Calcit-Drusenstueck"),
            ("OBJ_0004", "Mine_42 Probe"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring-Match
    rows = repo.list_objects(name_contains="Davos")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # ASCII-case-insensitive
    rows = repo.list_objects(name_contains="calcit")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Metazeichen wortwoertlich (_ wird nicht als beliebiges Zeichen interpretiert)
    rows = repo.list_objects(name_contains="Mine_4")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    rows = repo.list_objects(name_contains="MineX4")
    assert rows == []
    # NULL Name fliegt automatisch raus (LIKE-Match liefert NULL)
    rows = repo.list_objects(name_contains="x")
    assert all(r["obj_id"] != "OBJ_0005" for r in rows)
    c.close()


def test_notizen_contains_filter(tmp_path):
    """Substring-Filter ueber notizen-Freitext (Sammlungs-Anmerkungen)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nz.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, notizen) VALUES (?, ?)",
        [
            ("OBJ_0001", "Vom Vater geerbt 1985."),
            ("OBJ_0002", "Gefunden im Bachbett.\nMit UV-Lampe getestet."),
            ("OBJ_0003", None),
            ("OBJ_0004", "Sonderprobe 100% rein."),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Einfacher Substring-Match
    rows = repo.list_objects(notizen_contains="Vater")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Findet Eintraege mit eingebetteten Zeilenumbruechen
    rows = repo.list_objects(notizen_contains="UV-Lampe")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Metazeichen wortwoertlich (% wird nicht als Wildcard interpretiert)
    rows = repo.list_objects(notizen_contains="100%")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    # Kombinierbar mit anderen Filtern
    rows = repo.list_objects(notizen_contains="geerbt", has_notizen=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_mineral_contains_filter(tmp_path):
    """Substring-Filter ueber Mineral_Primaer findet Mineral-Familien-Varianten."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer) VALUES (?, ?)",
        [
            ("OBJ_0001", "Quarz"),
            ("OBJ_0002", "Rauchquarz"),
            ("OBJ_0003", "Rosenquarz"),
            ("OBJ_0004", "Calcit"),
            ("OBJ_0005", "Mine_Spec"),
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Quarz-Familie: drei Varianten mit Substring 'quarz'
    rows = repo.list_objects(mineral_contains="quarz")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # ASCII-case-insensitive
    rows = repo.list_objects(mineral_contains="QUARZ")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Kein Match
    rows = repo.list_objects(mineral_contains="Pyrit")
    assert rows == []
    # Anderes Mineral
    rows = repo.list_objects(mineral_contains="Calcit")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    # LIKE-Metazeichen wortwoertlich (_ wird nicht als beliebiges Zeichen interpretiert)
    rows = repo.list_objects(mineral_contains="Mine_S")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    rows = repo.list_objects(mineral_contains="MineXS")
    assert rows == []
    # NULL-Eintraege fliegen automatisch raus (LIKE auf NULL liefert NULL)
    rows = repo.list_objects(mineral_contains="z")
    assert all(r["obj_id"] != "OBJ_0006" for r in rows)
    # Kombinierbar mit has_mineral
    rows = repo.list_objects(mineral_contains="quarz", has_mineral=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_varietaet_contains_filter(tmp_path):
    """Substring-Filter ueber Varietaet findet Familien-Varianten (Jaspis-Klan)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?, ?)",
        [
            ("OBJ_0001", "Roter Jaspis"),
            ("OBJ_0002", "Bunter Jaspis"),
            ("OBJ_0003", "Milchquarz"),
            ("OBJ_0004", "Mine_4 Probe"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring matched alle Jaspis-Eintraege
    rows = repo.list_objects(varietaet_contains="Jaspis")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # ASCII-case-insensitive
    rows = repo.list_objects(varietaet_contains="jaspis")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Andere Varietaet
    rows = repo.list_objects(varietaet_contains="quarz")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Metazeichen wortwoertlich (_ wird nicht als beliebiges Zeichen interpretiert)
    rows = repo.list_objects(varietaet_contains="Mine_4")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    rows = repo.list_objects(varietaet_contains="MineX4")
    assert rows == []
    # NULL Varietaet fliegt automatisch raus
    rows = repo.list_objects(varietaet_contains="z")
    assert all(r["obj_id"] != "OBJ_0005" for r in rows)
    # Kombinierbar mit exaktem varietaet-Filter (Schnittmenge)
    rows = repo.list_objects(varietaet_contains="Jaspis", varietaet="Roter Jaspis")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_varietaet_und_gesteinsart_filter(tmp_path):
    """Strukturierter Filter fuer Varietaet und Gesteinsart (exakter Match)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet, Gesteinsart) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Jaspis", "Sediment"),
            ("OBJ_0002", "Jaspis", "Vulkanit"),
            ("OBJ_0003", "Milchquarz", "Sediment"),
            ("OBJ_0004", "", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(varietaet="Jaspis")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(gesteinsart="Sediment")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0003"]
    # Kombiniert: Jaspis + Sediment → nur OBJ_0001
    rows = repo.list_objects(varietaet="Jaspis", gesteinsart="Sediment")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_set_status_validiert(tmp_path):
    """Ungueltige Status-Werte werden mit ValueError abgewiesen (Tippschutz)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "st.sqlite3")
    repo = ObjectRepo(c)
    repo.create("OBJ_0001")
    repo.set_status("OBJ_0001", "aktiv")
    repo.set_status("OBJ_0001", "platzhalter")
    repo.set_status("OBJ_0001", "archiviert")
    with pytest.raises(ValueError):
        repo.set_status("OBJ_0001", "geloescht")
    with pytest.raises(ValueError):
        repo.set_status("OBJ_0001", "")
    c.close()


def test_archive_und_unarchive(tmp_path):
    """archive setzt 'archiviert'; unarchive berechnet Folgestatus aus dem Inhalt."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ar.sqlite3")
    repo = ObjectRepo(c)
    repo.create("OBJ_0001", Name="Hat Inhalt")
    repo.create("OBJ_0002")  # bleibt leer

    repo.archive("OBJ_0001")
    repo.archive("OBJ_0002")
    assert repo.get("OBJ_0001")["status"] == "archiviert"
    assert repo.get("OBJ_0002")["status"] == "archiviert"

    # refresh_status laesst archivierte Objekte in Ruhe
    repo.refresh_status_all()
    assert repo.get("OBJ_0001")["status"] == "archiviert"

    # Unarchive: Objekt mit Inhalt -> aktiv, leeres Objekt -> platzhalter
    repo.unarchive("OBJ_0001")
    repo.unarchive("OBJ_0002")
    assert repo.get("OBJ_0001")["status"] == "aktiv"
    assert repo.get("OBJ_0002")["status"] == "platzhalter"
    c.close()


def test_unarchive_unbekannte_id_no_op(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "u.sqlite3")
    repo = ObjectRepo(c)
    # Darf keinen Fehler werfen, auch wenn obj_id nicht existiert
    repo.unarchive("OBJ_9999")
    c.close()
