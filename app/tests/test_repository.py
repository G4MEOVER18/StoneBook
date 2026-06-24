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


def test_sort_by_aliase_desc(repo):
    """Sortierung nach Alias-Zahl (Merge-Tiefe) findet die am staerksten konsolidierten
    Kanon-Objekte - die spiegel-Sicht zu bilder (Foto-Pflege) auf die Provenienz-Achse.

    aliase ist ein COUNT-Subquery auf die aliases-Tabelle; Objekte ohne Alias erhalten
    0 (kein NULL), die Sortier-Reihenfolge ist dadurch komplett vergleichbar. Die
    migrierte DB hat per Duplikat-Gruppen-Verfahren ~30 Merge-Gruppen, der Top-Eintrag
    muss also mindestens einen Alias haben.
    """
    rows = repo.list_objects(sort_by="aliase", sort_desc=True)
    counts = [r["aliase"] for r in rows]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] >= 1


def test_sort_by_aliase_asc_zero_first(tmp_path):
    """Aufsteigend nach aliase: Objekte ohne Alias (0) zuerst, dann nach Merge-Tiefe.

    Deckt die COUNT-0-Konvention ab (kein NULL): Objekte ohne Alias landen bei der
    Aufwaerts-Sortierung am Anfang, nicht ans Ende wie bei der NULL-an-Ende-Logik
    fuer Schema-Spalten. Tie-Break auf obj_id (lexikographisch) sichert determini-
    stische Reihenfolge fuer Eintraege mit gleicher Merge-Tiefe.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "a.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    c.executemany(
        "INSERT INTO aliases (alias_id, canonical_id, merge_quelle) "
        "VALUES (?, ?, 'test')",
        [
            # OBJ_0002 hat 2 Aliase (Merge-Tiefe 2)
            ("ALT_0002A", "OBJ_0002"),
            ("ALT_0002B", "OBJ_0002"),
            # OBJ_0004 hat 1 Alias (Merge-Tiefe 1)
            ("ALT_0004A", "OBJ_0004"),
            # OBJ_0001, OBJ_0003 haben 0 Aliase
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="aliase")
    ids = [r["obj_id"] for r in rows]
    counts = [r["aliase"] for r in rows]
    assert counts == [0, 0, 1, 2]
    # Tie-Break auf obj_id: OBJ_0001 vor OBJ_0003 (beide 0 Aliase)
    assert ids == ["OBJ_0001", "OBJ_0003", "OBJ_0004", "OBJ_0002"]
    c.close()


def test_sort_by_analysen_desc(repo):
    """Sortierung nach KI-Analyse-Zahl (Analyse-Tiefe) findet die am intensivsten
    analysierten Objekte - die spiegel-Sicht zu bilder (Foto-Pflege) und aliase
    (Merge-Tiefe) auf die KI-Pflege-Achse.

    analysen ist ein COUNT-Subquery auf die ki_analysen-Tabelle; Objekte ohne
    Analyse erhalten 0 (kein NULL), die Sortier-Reihenfolge ist dadurch komplett
    vergleichbar. Die migrierte DB hat keinen garantierten Mindestbestand an
    KI-Analysen (sie werden erst zur Laufzeit erzeugt) - der Test prueft nur die
    monotone DESC-Reihenfolge, nicht den Top-Wert.
    """
    rows = repo.list_objects(sort_by="analysen", sort_desc=True)
    counts = [r["analysen"] for r in rows]
    assert counts == sorted(counts, reverse=True)


def test_sort_by_analysen_asc_zero_first(tmp_path):
    """Aufsteigend nach analysen: Objekte ohne KI-Analyse (0) zuerst, dann nach
    Analyse-Tiefe. Deckt die COUNT-0-Konvention ab (kein NULL): Objekte ohne
    Analyse landen bei der Aufwaerts-Sortierung am Anfang, nicht ans Ende wie
    bei der NULL-an-Ende-Logik fuer Schema-Spalten. Tie-Break auf obj_id
    (lexikographisch) sichert deterministische Reihenfolge fuer Eintraege mit
    gleicher Analyse-Tiefe.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "a.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json) "
        "VALUES (?, 'claude-test', '{}')",
        [
            # OBJ_0002 hat 2 Analysen (Analyse-Tiefe 2)
            ("OBJ_0002",), ("OBJ_0002",),
            # OBJ_0004 hat 1 Analyse (Analyse-Tiefe 1)
            ("OBJ_0004",),
            # OBJ_0001, OBJ_0003 haben 0 Analysen
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="analysen")
    ids = [r["obj_id"] for r in rows]
    counts = [r["analysen"] for r in rows]
    assert counts == [0, 0, 1, 2]
    # Tie-Break auf obj_id: OBJ_0001 vor OBJ_0003 (beide 0 Analysen)
    assert ids == ["OBJ_0001", "OBJ_0003", "OBJ_0004", "OBJ_0002"]
    c.close()


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


def test_sort_by_haerte_und_dichte(tmp_path):
    """Sortierung nach Mohs-Haerte/Dichte-Untergrenze; NULLs landen am Ende."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hd.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Dichte_min_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.5, 2.7),   # Calcit
            ("OBJ_0002", 7.0, 2.6),   # Quarz
            ("OBJ_0003", 1.0, 2.3),   # Talk
            ("OBJ_0004", None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Mohs_Haerte_min")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0001", "OBJ_0002"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Dichte_min_gcm3", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_haerte_max_und_dichte_max(tmp_path):
    """Sortierung nach Mohs-Haerte/Dichte-Obergrenze; NULLs landen am Ende.

    Symmetrie zu test_sort_by_haerte_und_dichte (_min); fuer Sammler-Fragen wie
    "wer ist robust genug zum Polieren?" (Mohs_Haerte_max-Obergrenze).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hdmax.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_max, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 3.5, 2.8),   # Calcit-Bereich
            ("OBJ_0002", 7.5, 2.7),   # Quarz mit Obergrenze
            ("OBJ_0003", 1.5, 2.4),   # Talk
            ("OBJ_0004", None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Mohs_Haerte_max")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0001", "OBJ_0002"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Dichte_max_gcm3", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_dimensionen(tmp_path):
    """Sortierung nach Laenge_mm/Breite_mm/Hoehe_mm fuer Vitrinen-/Schubladen-Auswahl."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "dim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) "
        "VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", 120.0, 80.0, 40.0),   # gross flach
            ("OBJ_0002",  60.0, 50.0, 50.0),   # mittel kompakt
            ("OBJ_0003",  30.0, 20.0, 80.0),   # klein hoch
            ("OBJ_0004",  None, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Laenge_mm")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Breite_mm", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    rows = repo.list_objects(sort_by="Hoehe_mm", sort_desc=True)
    # OBJ_0003 hat 80mm Hoehe → vorne; dann OBJ_0002 (50), OBJ_0001 (40)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    c.close()


def test_sort_by_seltenheit_und_nachfrage(tmp_path):
    """Sortierung nach 1..10-Skalen (Seltenheit/Nachfrage) - Begleitung zu den
    seltenheit_/nachfrage_-Filtern: erst Rarity-Bereich, dann absteigend sortieren.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "rs.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10, "
        "Seltenheit_Fundort_1_10, Nachfrage_1_10) VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", 2, 9, 4),    # lokal selten, global haeufig
            ("OBJ_0002", 5, 5, 7),    # mittel/gefragt
            ("OBJ_0003", 9, 2, 9),    # global rar, lokal haeufig
            ("OBJ_0004", None, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Seltenheit_global_1_10", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Seltenheit_Fundort_1_10", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    rows = repo.list_objects(sort_by="Nachfrage_1_10", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    c.close()


def test_sort_by_kristallsystem(tmp_path):
    """Sortierung nach Kristallsystem gruppiert die Liste kristallographisch.

    Vor Mikroskop-/Diffraktometer-Sitzungen will man alle Stuecke gleicher
    Symmetrie nebeneinander sehen - spiegelt kristallsystem_in /
    by_kristallsystem / wert_pro_kristallsystem auf die Sortier-Achse.
    Alphabetisch sortiert ergibt amorph/hexagonal/kubisch/monoklin/
    orthorhombisch/tetragonal/trigonal/triklin.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ks.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [
            ("OBJ_0001", "trigonal"),     # Quarz
            ("OBJ_0002", "kubisch"),      # Pyrit
            ("OBJ_0003", "amorph"),       # Obsidian
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Kristallsystem")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Kristallsystem", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_beste_verwendung(tmp_path):
    """Sortierung nach Beste_Verwendung gruppiert die Liste nach Empfehlung.

    Vor Boersenbesuch / Schmuck-Verkauf: alle "Schmuck"-Stuecke beisammen,
    alle "Forschung"-Stuecke beisammen - spiegelt beste_verwendung_in /
    by_beste_verwendung / wert_pro_beste_verwendung auf die Sortier-Achse.
    Sechs Enum-Werte, alphabetisch geordnet ergibt Dekoration/Forschung/
    Industrie/Sammlung/Schmuck/Talisman.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [
            ("OBJ_0001", "Schmuck"),
            ("OBJ_0002", "Forschung"),
            ("OBJ_0003", "Dekoration"),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Beste_Verwendung")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Beste_Verwendung", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_glanz(tmp_path):
    """Sortierung nach Glanz gruppiert die Liste optisch.

    Vor Foto-Sessions will man alle glasigen Quarze und alle metallischen
    Pyrite beisammen haben, weil sie gleiches Licht-Setup brauchen (glasig:
    gerichtetes Streiflicht, metallisch: diffuser Schirm). Spiegelt
    glanz_in / by_glanz / wert_pro_glanz auf die Sortier-Achse.
    Sieben Enum-Werte, alphabetisch sortiert ergibt fettig/glasig/matt/
    metallisch/perlmutt/seidig/wachsig.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gl.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?, ?)",
        [
            ("OBJ_0001", "metallisch"),
            ("OBJ_0002", "glasig"),
            ("OBJ_0003", "fettig"),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Glanz")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Glanz", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_transparenz(tmp_path):
    """Sortierung nach Transparenz gruppiert die Liste nach Lichtdurchlaessigkeit.

    Komplementaer zur Sortierung nach Glanz (Oberflaechen-Reflexion vs. Volumen-
    Lichtgang) - durchsichtige Stuecke brauchen Backlight beim Fotografieren,
    opake Frontlight. Drei Enum-Werte, alphabetisch ergibt durchscheinend/
    durchsichtig/opak. Spiegelt transparenz_in / by_transparenz /
    wert_pro_transparenz auf die Sortier-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tr.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?, ?)",
        [
            ("OBJ_0001", "opak"),
            ("OBJ_0002", "durchsichtig"),
            ("OBJ_0003", "durchscheinend"),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Transparenz")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Transparenz", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_magnetismus(tmp_path):
    """Sortierung nach Magnetismus gruppiert die Liste nach Eisen-Reaktion.

    Vor einer Magnet-Diagnostik-Runde will man alle erwartet reagierenden
    Stuecke (ja: Magnetit/Pyrrhotin; schwach: Haematit/Ilmenit) beisammen
    testen, ohne zwischen inerten Quarz-/Calcit-Stuecken hin- und herzuspringen.
    Drei Enum-Werte (ja/nein/schwach), alphabetisch sortiert ergibt
    ja/nein/schwach. Spiegelt magnetismus_in / by_magnetismus /
    wert_pro_magnetismus auf die Sortier-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mag.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [
            ("OBJ_0001", "schwach"),
            ("OBJ_0002", "ja"),
            ("OBJ_0003", "nein"),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Magnetismus")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0002", "OBJ_0003", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Magnetismus", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0003", "OBJ_0002"]
    c.close()


def test_sort_by_spaltbarkeit(tmp_path):
    """Sortierung nach Spaltbarkeit gruppiert die Liste nach Spaltflaechen-Klasse.

    Vor einer Schnitt-/Polier-Session will man die gut spaltbaren Stuecke
    (Calcit/Fluorit/Glimmer) beisammen haben, weil sie ein anderes Werkzeug-
    Setup brauchen als zaehe quarz-/obsidian-aehnliche Stuecke ohne Spalt-
    flaechen. Fuenf Enum-Werte (vollkommen/gut/deutlich/undeutlich/keine),
    alphabetisch sortiert ergibt deutlich/gut/keine/undeutlich/vollkommen.
    Spiegelt spaltbarkeit_in / by_spaltbarkeit / wert_pro_spaltbarkeit auf
    die Sortier-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "sp.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?, ?)",
        [
            ("OBJ_0001", "vollkommen"),
            ("OBJ_0002", "gut"),
            ("OBJ_0003", "deutlich"),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Spaltbarkeit")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Spaltbarkeit", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_bruch(tmp_path):
    """Sortierung nach Bruch gruppiert die Liste nach Bruchverhalten.

    Komplementaer zur Sortierung nach Spaltbarkeit (Spaltflaechen): muschelig
    brechende Quarz-/Obsidian-Stuecke erzeugen scharfe Kanten, splittrige noch
    mehr - die Sortier-Achse hilft beim Beisammen-Halten der Hand-Vorsichts-
    Klassen vor Polier-/Schneid-Sitzungen. Sechs Enum-Werte (muschelig/uneben/
    splittrig/faserig/erdig/glatt), alphabetisch sortiert ergibt erdig/faserig/
    glatt/muschelig/splittrig/uneben. Spiegelt bruch_in / by_bruch /
    wert_pro_bruch auf die Sortier-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "br.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?, ?)",
        [
            ("OBJ_0001", "muschelig"),
            ("OBJ_0002", "faserig"),
            ("OBJ_0003", "erdig"),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Bruch")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Bruch", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    c.close()


def test_sort_by_gesteinsart(tmp_path):
    """Sortierung nach Gesteinsart gruppiert die Liste petrologisch.

    Komplementaer zur Sortierung nach Mineral_Primaer/Varietaet (mineralogische
    Familie/Sub) - Gesteinsart liefert die petrologische Einbettung (Granit/Gneis/
    Basalt/Sandstein), die in den mineralogischen Achsen quer durchgeht. Listen
    werden zur Standort-/Boersen-Vorbereitung typisch nach Gesteinsart gruppiert,
    weil Anbieter ihre Stuecke meist petrologisch sortieren.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ga.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [
            ("OBJ_0001", "Sandstein"),
            ("OBJ_0002", "Basalt"),
            ("OBJ_0003", "Granit"),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Gesteinsart")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0002", "OBJ_0003", "OBJ_0001"]
    assert rows[-1]["obj_id"] == "OBJ_0004"  # NULL ans Ende
    rows = repo.list_objects(sort_by="Gesteinsart", sort_desc=True)
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0003", "OBJ_0002"]
    c.close()


def test_sort_by_kategorie_und_varietaet(tmp_path):
    """Sortierung nach kategorischen Spalten gruppiert Listen visuell.

    list_objects gibt nur eine SELECT-Untermenge zurueck (Kategorie/Varietaet
    sind nicht enthalten); die Reihenfolge wird daher ueber obj_id geprueft -
    OBJ_id-Belegung ist so gewaehlt, dass die alphabetische Sortierung eindeutig
    eine bestimmte obj_id-Reihenfolge erzeugt.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "kv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie, Varietaet) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Handstueck", "Jaspis"),
            ("OBJ_0002", "Kristall", "Bergkristall"),
            ("OBJ_0003", "Geroell", "Achat"),
            ("OBJ_0004", "Handstueck", "Achat"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Kategorie aufsteigend: Geroell (OBJ_0003), Handstueck (OBJ_0001, OBJ_0004),
    # Kristall (OBJ_0002). Stabile Zweitsortierung nach obj_id macht die Mitte deterministisch.
    rows = repo.list_objects(sort_by="Kategorie")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0001", "OBJ_0004", "OBJ_0002"]
    # Varietaet aufsteigend: Achat (OBJ_0003, OBJ_0004), Bergkristall (OBJ_0002), Jaspis (OBJ_0001).
    rows = repo.list_objects(sort_by="Varietaet")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004", "OBJ_0002", "OBJ_0001"]
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


def test_has_ki_analyse_filter(tmp_path):
    """has_ki_analyse trennt bereits analysierte Objekte von ausstehenden Batches."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hki.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",), ("OBJ_0005",)],
    )
    # OBJ_0001: eine Analyse; OBJ_0002: mehrere (Mehrfach-Eintraege zaehlen einmal);
    # OBJ_0005: eine Analyse - sollen alle has_ki_analyse=True ergeben.
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "claude-sonnet-4-6", "{}"),
            ("OBJ_0002", "claude-sonnet-4-6", "{}"),
            ("OBJ_0002", "claude-opus-4-7", "{}"),
            ("OBJ_0005", "claude-sonnet-4-6", "{}"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_ki_analyse=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    assert [r["obj_id"] for r in repo.list_objects(has_ki_analyse=False)] \
        == ["OBJ_0003", "OBJ_0004"]
    # None laesst alle durch
    assert len(repo.list_objects(has_ki_analyse=None)) == 5
    c.close()


def test_has_ki_analyse_uebernommen_filter(tmp_path):
    """has_ki_analyse_uebernommen findet Objekte mit mind. einem uebernommenen Vorschlag."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hkiu.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",), ("OBJ_0005",)],
    )
    # OBJ_0001: zwei Analysen, eine uebernommen.
    # OBJ_0002: zwei Analysen, beide nicht uebernommen (NULL / leerer String).
    # OBJ_0003: eine Analyse, nicht uebernommen.
    # OBJ_0004: gar keine Analyse.
    # OBJ_0005: eine Analyse, vollstaendig uebernommen.
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json, uebernommen_json) "
        "VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", "claude-sonnet-4-6", "{}", '{"a":1}'),
            ("OBJ_0001", "claude-opus-4-7", "{}", None),
            ("OBJ_0002", "claude-sonnet-4-6", "{}", None),
            ("OBJ_0002", "claude-sonnet-4-6", "{}", ""),
            ("OBJ_0003", "claude-sonnet-4-6", "{}", "   "),
            ("OBJ_0005", "claude-sonnet-4-6", "{}", '{"x":42}'),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Wahr: OBJ_0001 (eine uebernommene Analyse) und OBJ_0005 (alles uebernommen)
    assert [r["obj_id"] for r in repo.list_objects(has_ki_analyse_uebernommen=True)] \
        == ["OBJ_0001", "OBJ_0005"]
    # Falsch: OBJ_0002 (analysiert, aber nichts uebernommen), OBJ_0003 (Whitespace zaehlt
    # wie leer), OBJ_0004 (keine Analyse vorhanden = trivially "noch nichts uebernommen")
    assert [r["obj_id"] for r in repo.list_objects(has_ki_analyse_uebernommen=False)] \
        == ["OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # None laesst alle durch
    assert len(repo.list_objects(has_ki_analyse_uebernommen=None)) == 5
    # Verworfene KI-Vorschlaege: KI-Lauf gemacht, aber nichts uebernommen
    rows = repo.list_objects(has_ki_analyse=True, has_ki_analyse_uebernommen=False)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    c.close()


def test_has_alias_filter(tmp_path):
    """has_alias trennt gemergte Kanon-Objekte von nicht-gemergten Originalen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ha.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    # OBJ_0001 hat zwei Aliase (zwei alte IDs reingefolgt), OBJ_0003 einen.
    # Mehrfach-Eintraege duerfen die Liste nicht duplizieren (EXISTS, nicht JOIN).
    c.executemany(
        "INSERT INTO aliases (alias_id, canonical_id, merge_quelle) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0100", "OBJ_0001", "duplikat_gruppen.json"),
            ("OBJ_0101", "OBJ_0001", "manuell"),
            ("OBJ_0102", "OBJ_0003", "manuell"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_alias=True)] \
        == ["OBJ_0001", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_alias=False)] \
        == ["OBJ_0002", "OBJ_0004"]
    # None laesst alle durch
    assert len(repo.list_objects(has_alias=None)) == 4
    c.close()


def test_has_ki_analyse_kombinierbar_mit_has_confidence(tmp_path):
    """KI-analysiert ohne Confidence-Wert: noch nicht uebernommener Vorschlag."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hki_combo.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 80),     # KI-analysiert + Confidence gesetzt
            ("OBJ_0002", None),   # KI-analysiert, aber Confidence noch leer
            ("OBJ_0003", 90),     # Confidence gesetzt, aber ohne KI-Lauf (manuell)
            ("OBJ_0004", None),   # weder noch
        ],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json) VALUES (?, ?, ?)",
        [("OBJ_0001", "claude-sonnet-4-6", "{}"),
         ("OBJ_0002", "claude-sonnet-4-6", "{}")],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Asymmetrische Pflege: KI-Lauf gemacht, aber Confidence nie uebernommen.
    rows = repo.list_objects(has_ki_analyse=True, has_confidence=False)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Umgekehrt: manueller Confidence-Wert ohne KI-Lauf.
    rows = repo.list_objects(has_ki_analyse=False, has_confidence=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
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


def test_has_kategorie_filter(tmp_path):
    """has_kategorie: dokumentierte Objekt-Kategorie (Inventar-/ID-Gruppen-Achse).

    Kategorie (Mineral-Korn/Handstueck/Duennschliff/Kristall/Geroell/Sonstiges)
    ist die erste Identifikations-/Inventar-Achse - was ist das Stueck
    physisch? Findet unkategorisierte Stuecke fuer die Inventar-
    Vorklassifizierung, typisch nach Migration alter v1/obj043-Bestaende
    ohne Kategorie-Spalte. Spiegelt has_mineral/has_kristallsystem auf
    die ID-Gruppe; ergaenzt den kategorie_in-Mengenfilter (konkrete
    Kategorien-Auswahl). Whitespace zaehlt wie leer.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hk.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
        [
            ("OBJ_0001", "Handstück"),
            ("OBJ_0002", "Kristall"),
            ("OBJ_0003", "Mineral-Korn"),
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
            ("OBJ_0006", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_kategorie=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_kategorie=False)] \
        == ["OBJ_0004", "OBJ_0005", "OBJ_0006"]
    assert len(repo.list_objects(has_kategorie=None)) == 6
    # Kombinierbar mit kategorie_in (Schnittmenge): dokumentiert UND
    # konkret aus {Handstueck, Kristall}, ohne Mineral-Korn-Stueck OBJ_0003.
    rows = repo.list_objects(has_kategorie=True,
                             kategorie_in=["Handstück", "Kristall"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
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


def test_has_uv_reaktion_filter(tmp_path):
    """has_uv_reaktion: dokumentierte Fluoreszenz im 365- oder 254-nm-Feld."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "huv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, UV_365nm, UV_254nm) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "blau", None),          # nur 365 nm dokumentiert
            ("OBJ_0002", None, "schwach gruen"), # nur 254 nm dokumentiert
            ("OBJ_0003", "keine", "keine"),      # beide dokumentiert (Inhalt egal)
            ("OBJ_0004", None, None),            # nichts dokumentiert
            ("OBJ_0005", "", "   "),             # leer/Whitespace zaehlt wie None
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_uv_reaktion=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_uv_reaktion=False)] \
        == ["OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_uv_reaktion=None)) == 5
    c.close()


def test_has_uv_reaktion_kombinierbar_mit_uv395_bild(tmp_path):
    """UV-Bild ohne dokumentierte Reaktion: typischer Pflege-Hinweis."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "huv2.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, UV_365nm) VALUES (?, ?)",
        [("OBJ_0001", "gelb"), ("OBJ_0002", None)],
    )
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "UV395", "objects/OBJ_0001/UV 395 nm/a.jpg"),
            ("OBJ_0002", "UV395", "objects/OBJ_0002/UV 395 nm/b.jpg"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(has_image_kategorie="UV395", has_uv_reaktion=False)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_has_strichfarbe_filter(tmp_path):
    """has_strichfarbe: dokumentierter Strichtest (klassische Diagnose-Probe)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hsf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Strichfarbe) VALUES (?, ?)",
        [
            ("OBJ_0001", "rot"),         # Haematit
            ("OBJ_0002", "schwarz"),     # Magnetit
            ("OBJ_0003", "weiss"),       # Quarz (Strich farblos/weiss)
            ("OBJ_0004", None),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_strichfarbe=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_strichfarbe=False)] \
        == ["OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_strichfarbe=None)) == 5
    c.close()


def test_has_hcl_reaktion_filter(tmp_path):
    """has_hcl_reaktion: dokumentierter Salzsaeure-Test (Karbonat-Diagnostik)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hhcl.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, HCl_Reaktion) VALUES (?, ?)",
        [
            ("OBJ_0001", "stark kalt"),     # Calcit
            ("OBJ_0002", "schwach warm"),   # Dolomit
            ("OBJ_0003", "keine"),          # Quarz (Nicht-Karbonat dokumentiert)
            ("OBJ_0004", None),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_hcl_reaktion=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_hcl_reaktion=False)] \
        == ["OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_hcl_reaktion=None)) == 5
    c.close()


def test_has_mohs_filter(tmp_path):
    """has_mohs: dokumentierte Mohs-Haerte (eines der beiden Bereichsfelder reicht)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hmohs.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 6.5, 7.0),    # voller Bereich Quarz
            ("OBJ_0002", 5.0, None),   # nur Untergrenze
            ("OBJ_0003", None, 9.0),   # nur Obergrenze (Korund-Verdacht)
            ("OBJ_0004", None, None),  # nichts dokumentiert
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_mohs=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_mohs=False)] \
        == ["OBJ_0004"]
    assert len(repo.list_objects(has_mohs=None)) == 4
    c.close()


def test_has_dichte_filter(tmp_path):
    """has_dichte: dokumentierte Dichte (eines der beiden Bereichsfelder reicht)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hdichte.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.65, 2.65),  # Quarz, voller Bereich
            ("OBJ_0002", 2.7, None),   # nur Untergrenze
            ("OBJ_0003", None, 5.0),   # nur Obergrenze (Erz-Verdacht)
            ("OBJ_0004", None, None),  # nichts dokumentiert
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_dichte=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_dichte=False)] \
        == ["OBJ_0004"]
    assert len(repo.list_objects(has_dichte=None)) == 4
    c.close()


def test_has_farbe_filter(tmp_path):
    """has_farbe: dokumentierte Farbe (Farbe_beobachtet) - primaeres Beschreibungsfeld."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Farbe_beobachtet) VALUES (?, ?)",
        [
            ("OBJ_0001", "rosa-orange"),
            ("OBJ_0002", "milchig-weiss"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_farbe=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_farbe=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_farbe=None)) == 5
    c.close()


def test_has_bruch_filter(tmp_path):
    """has_bruch: dokumentiertes Bruchverhalten (Bruchflaechen-Achse).

    Bruch ist die Bruchflaechen-Achse (muschelig/uneben/splittrig/faserig/
    erdig/glatt) - die andere Hand-Vorsichts-Achse neben has_spaltbarkeit
    (Spaltflaechen). Findet Stuecke, an denen der Bruch-Test
    (Hammer/Schlag-Beobachtung) nachzuholen ist - zentrale Verletzungs-
    risiko-Diagnose vor Polier-/Schneid-Sitzungen. Komplementaer zum
    bruch_in-Mengenfilter und zur Bruch-Sortier-Spalte.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hbr.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?, ?)",
        [
            ("OBJ_0001", "muschelig"),   # Quarz/Obsidian (scharfe Kanten)
            ("OBJ_0002", "splittrig"),   # noch scharfere Kanten
            ("OBJ_0003", "faserig"),     # Aktinolith
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
            ("OBJ_0006", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_bruch=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_bruch=False)] \
        == ["OBJ_0004", "OBJ_0005", "OBJ_0006"]
    assert len(repo.list_objects(has_bruch=None)) == 6
    # Kombinierbar mit bruch_in-Mengenfilter (Schnittmenge): dokumentiert UND
    # scharfkantig (muschelig/splittrig), ohne faserige Aktinolith-Stuecke.
    rows = repo.list_objects(has_bruch=True, bruch_in=["muschelig", "splittrig"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_has_magnetismus_filter(tmp_path):
    """has_magnetismus: dokumentierte Magnet-Reaktion (Eisen-Diagnose-Achse).

    Magnetismus ist die Eisen-Diagnose-Achse (ja/schwach/nein) - der Test am
    Neodym-Magneten ist schnell und zerstoerungsfrei, wird aber oft vergessen
    oder bei offensichtlich nicht-magnetischen Stuecken nicht eingetragen.
    Findet Stuecke ohne Magnet-Test fuer diagnostische Nachpflege, besonders
    relevant bei dunklen/metallisch-glaenzenden Stuecken (Magnetit/Haematit/
    Ilmenit-Trennung).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hmg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [
            ("OBJ_0001", "ja"),         # Magnetit/Pyrrhotin
            ("OBJ_0002", "schwach"),    # Haematit/Ilmenit
            ("OBJ_0003", "nein"),       # Quarz/Calcit
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
            ("OBJ_0006", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_magnetismus=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_magnetismus=False)] \
        == ["OBJ_0004", "OBJ_0005", "OBJ_0006"]
    assert len(repo.list_objects(has_magnetismus=None)) == 6
    # Kombinierbar mit magnetismus_in (Schnittmenge): dokumentiert UND
    # reagierend (ja/schwach), ohne die inerten Quarz-/Calcit-Stuecke.
    rows = repo.list_objects(has_magnetismus=True,
                             magnetismus_in=["ja", "schwach"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_has_spaltbarkeit_filter(tmp_path):
    """has_spaltbarkeit: dokumentierte Spaltbarkeit (Spaltflaechen-Achse).

    Spaltbarkeit ist die Spaltflaechen-Achse (vollkommen/gut/deutlich/
    undeutlich/keine) - komplementaer zu has_bruch (Bruchflaechen). In der
    Praxis werden beide Tests oft zusammen durchgefuehrt (Hammer-Schlag plus
    Beobachtung). Findet Stuecke, an denen der Spaltbarkeits-Test nachzuholen
    ist - Werkzeug-Setup-Achse vor Praeparier-/Polier-Sitzungen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hsp.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?, ?)",
        [
            ("OBJ_0001", "vollkommen"),   # Calcit/Glimmer
            ("OBJ_0002", "gut"),          # Fluorit
            ("OBJ_0003", "keine"),        # Quarz/Obsidian
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
            ("OBJ_0006", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_spaltbarkeit=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_spaltbarkeit=False)] \
        == ["OBJ_0004", "OBJ_0005", "OBJ_0006"]
    assert len(repo.list_objects(has_spaltbarkeit=None)) == 6
    # Kombinierbar mit spaltbarkeit_in (Schnittmenge): dokumentiert UND sauber
    # spaltbar (vollkommen/gut), ohne zaehe Quarz-Brocken (keine).
    rows = repo.list_objects(has_spaltbarkeit=True,
                             spaltbarkeit_in=["vollkommen", "gut"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_has_glanz_filter(tmp_path):
    """has_glanz: dokumentierter Glanz (optische Oberflaechen-Reflexions-Achse).

    Glanz ist die zentrale optische Diagnose- und Foto-Setup-Achse (glasig/
    wachsig/matt/metallisch/fettig/seidig/perlmutt) - die Beleuchtung wird auf
    den Glanz abgestimmt (diffus gegen Spiegelung bei glasig, Streiflicht zur
    Akzentuierung bei metallisch). Findet Stuecke, an denen der Glanz-Eintrag
    nachzuholen ist - typischerweise erste Felddatenpflege, weil der Glanz
    unmittelbar sichtbar ist und keinen Test (Hammer/Saeure/Magnet) braucht.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hgl.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?, ?)",
        [
            ("OBJ_0001", "glasig"),     # Quarz/Calcit
            ("OBJ_0002", "metallisch"), # Galenit/Pyrit
            ("OBJ_0003", "matt"),       # Erdige Mineralien
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
            ("OBJ_0006", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_glanz=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_glanz=False)] \
        == ["OBJ_0004", "OBJ_0005", "OBJ_0006"]
    assert len(repo.list_objects(has_glanz=None)) == 6
    # Kombinierbar mit glanz_in (Schnittmenge): dokumentiert UND glasig/metallisch
    # fuer die zwei "schwierigen" Foto-Setups (Spiegelungs- vs. Reflex-Lichtfuehrung).
    rows = repo.list_objects(has_glanz=True, glanz_in=["glasig", "metallisch"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_has_transparenz_filter(tmp_path):
    """has_transparenz: dokumentierte Transparenz (Lichtdurchlaessigkeits-Achse).

    Transparenz (durchsichtig/durchscheinend/opak) ist die Lichtdurchlaessigkeits-
    Achse - komplementaer zu has_glanz (Oberflaechen-Reflexion) auf die andere
    optische Achse: durchsichtige Stuecke brauchen Hintergrund-Beleuchtung
    (Lichttisch/Backlight), opake Stuecke direkte Front-Beleuchtung. Findet
    Stuecke ohne Transparenz-Eintrag fuer die Foto-Vorbereitung.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "htr.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?, ?)",
        [
            ("OBJ_0001", "durchsichtig"),    # Bergkristall
            ("OBJ_0002", "durchscheinend"),  # Milchquarz/Calcit
            ("OBJ_0003", "opak"),            # Granit/Sandstein
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
            ("OBJ_0006", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_transparenz=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_transparenz=False)] \
        == ["OBJ_0004", "OBJ_0005", "OBJ_0006"]
    assert len(repo.list_objects(has_transparenz=None)) == 6
    # Kombinierbar mit transparenz_in (Schnittmenge): dokumentiert UND Licht-
    # durchlassend (durchsichtig/durchscheinend) fuer Backlight-Foto-Setup,
    # ohne die opaken Stuecke (die direkte Front-Beleuchtung brauchen).
    rows = repo.list_objects(has_transparenz=True,
                             transparenz_in=["durchsichtig", "durchscheinend"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_has_beste_verwendung_filter(tmp_path):
    """has_beste_verwendung: dokumentierte Verwendungs-Empfehlung (Markt-/Anwendungs-Positionierung).

    Beste_Verwendung (Schmuck/Sammlung/Forschung/Industrie/Talisman/Dekoration)
    ist die Markt-/Anwendungs-Positionierung - die Empfehlung, was das Stueck
    letztlich werden soll. In der Praxis erst nach mineralogischer Bestimmung
    und Wert-Einschaetzung gesetzt, daher in Sammlungsbestaenden mit Pflege-
    Rueckstaenden oft die letzte Felddatenachse, die ausgefuellt wird.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hbv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [
            ("OBJ_0001", "Schmuck"),
            ("OBJ_0002", "Sammlung"),
            ("OBJ_0003", "Forschung"),
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
            ("OBJ_0006", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_beste_verwendung=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_beste_verwendung=False)] \
        == ["OBJ_0004", "OBJ_0005", "OBJ_0006"]
    assert len(repo.list_objects(has_beste_verwendung=None)) == 6
    # Kombinierbar mit beste_verwendung_in (Schnittmenge): dokumentiert UND
    # Sammler-orientiert (Schmuck/Sammlung), ohne Forschungs-Stuecke.
    rows = repo.list_objects(has_beste_verwendung=True,
                             beste_verwendung_in=["Schmuck", "Sammlung"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_has_kristallsystem_filter(tmp_path):
    """has_kristallsystem: dokumentierter Symmetrietyp (kristallographische Hauptachse)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hks.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [
            ("OBJ_0001", "trigonal"),     # Quarz
            ("OBJ_0002", "kubisch"),      # Pyrit
            ("OBJ_0003", "amorph"),       # Obsidian
            ("OBJ_0004", None),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_kristallsystem=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["obj_id"] for r in repo.list_objects(has_kristallsystem=False)] \
        == ["OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_kristallsystem=None)) == 5
    c.close()


def test_has_varietaet_filter(tmp_path):
    """has_varietaet: dokumentierte Varietaet (mineralogische Sub-Klassifizierung)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?, ?)",
        [
            ("OBJ_0001", "Bergkristall"),
            ("OBJ_0002", "Rauchquarz"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_varietaet=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_varietaet=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_varietaet=None)) == 5
    c.close()


def test_has_reaktionshinweis_filter(tmp_path):
    """has_reaktionshinweis: dokumentierter Reaktions-Kommentar (Begleit-Notiz)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hrh.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Reaktionshinweis) VALUES (?, ?)",
        [
            ("OBJ_0001", "Reaktion warm verstaerkt"),
            ("OBJ_0002", "nur Risskanten fluoreszieren"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_reaktionshinweis=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_reaktionshinweis=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_reaktionshinweis=None)) == 5
    c.close()


def test_has_gesteinsart_filter(tmp_path):
    """has_gesteinsart: dokumentierte Gesteinsart (petrologische Klassifizierung)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hga.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [
            ("OBJ_0001", "Granit"),
            ("OBJ_0002", "Gneis"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_gesteinsart=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_gesteinsart=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_gesteinsart=None)) == 5
    c.close()


def test_has_fundort_filter(tmp_path):
    """has_fundort: dokumentierter Fundort (Standort-Achse der Sammlung)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hfo.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "Grimsel, Schweiz"),
            ("OBJ_0002", "Boerse Sainte-Marie-aux-Mines"),
            ("OBJ_0003", None),
            ("OBJ_0004", ""),
            ("OBJ_0005", "   "),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_fundort=True)] \
        == ["OBJ_0001", "OBJ_0002"]
    assert [r["obj_id"] for r in repo.list_objects(has_fundort=False)] \
        == ["OBJ_0003", "OBJ_0004", "OBJ_0005"]
    assert len(repo.list_objects(has_fundort=None)) == 5
    c.close()


def test_has_dimensionen_filter(tmp_path):
    """has_dimensionen: mindestens eine der drei Achsen (Laenge/Breite/Hoehe) gemessen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hd.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", 100.0, 50.0, 30.0),   # alle drei
            ("OBJ_0002", 120.0, None, None),   # nur Laenge
            ("OBJ_0003", None, 80.0, None),    # nur Breite
            ("OBJ_0004", None, None, 25.0),    # nur Hoehe
            ("OBJ_0005", None, None, None),    # unvermessenes Stueck
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert [r["obj_id"] for r in repo.list_objects(has_dimensionen=True)] \
        == ["OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    assert [r["obj_id"] for r in repo.list_objects(has_dimensionen=False)] \
        == ["OBJ_0005"]
    assert len(repo.list_objects(has_dimensionen=None)) == 5
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


def test_funddatum_jahr_in_filter(tmp_path):
    """funddatum_jahr_in akzeptiert diskrete Jahresmenge ('2018 ODER 2022 ODER 2024')."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "yi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2018-05-13"),
            ("OBJ_0002", "2020-08-01"),
            ("OBJ_0003", "2022-01-01"),
            ("OBJ_0004", "2024-11-30"),
            ("OBJ_0005", ""),
            ("OBJ_0006", "kein-datum"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Diskrete Mengen-Auswahl: nur die genannten Jahre
    rows = repo.list_objects(funddatum_jahr_in=[2018, 2022, 2024])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # Einzelnes Jahr verhaelt sich wie min=max
    rows = repo.list_objects(funddatum_jahr_in=[2020])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Tupel akzeptiert
    rows = repo.list_objects(funddatum_jahr_in=(2020, 2022))
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(funddatum_jahr_in=[])
    assert len(rows) == 6
    # Jahr ohne Treffer -> leeres Ergebnis, kein Crash
    rows = repo.list_objects(funddatum_jahr_in=[1999])
    assert rows == []
    # Kombiniert mit Bereichsfilter (Schnittmenge): {2018,2020,2024} ∩ [2020..2023]
    rows = repo.list_objects(funddatum_jahr_in=[2018, 2020, 2024],
                              funddatum_jahr_min=2020, funddatum_jahr_max=2023)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Ungueltige Jahresangaben (ausserhalb 1800..2999) -> ValueError
    import pytest as _pytest
    with _pytest.raises(ValueError, match="Unbekannte Funddatum-Jahre"):
        repo.list_objects(funddatum_jahr_in=[2020, 9999])
    with _pytest.raises(ValueError, match="Unbekannte Funddatum-Jahre"):
        repo.list_objects(funddatum_jahr_in=[1700])
    c.close()


def test_funddatum_monat_in_filter(tmp_path):
    """funddatum_monat_in waehlt mehrere Monate aus (Berg-Saison Juli ODER August)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "monat_in.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2020-07-15"),
            ("OBJ_0002", "2021-08-20"),
            ("OBJ_0003", "2022-12-10"),  # Dezember (Boerse)
            ("OBJ_0004", "2024-02-01"),  # Februar (Tucson)
            ("OBJ_0005", "2024-03-20"),
            ("OBJ_0006", "2024"),         # ohne Monatsteil
            ("OBJ_0007", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Berg-Saison: Juli ODER August
    rows = repo.list_objects(funddatum_monat_in=[7, 8])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Boersen-Spitzen: Dezember ODER Februar
    rows = repo.list_objects(funddatum_monat_in=[12, 2])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Einzelner Monat ist OK
    rows = repo.list_objects(funddatum_monat_in=[3])
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Tupel akzeptiert
    rows = repo.list_objects(funddatum_monat_in=(7, 8))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(funddatum_monat_in=[])
    assert len(rows) == 7
    # Kombiniert mit Jahresfilter (Schnittmenge)
    rows = repo.list_objects(funddatum_monat_in=[7, 8], funddatum_jahr_min=2021)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Validierung
    import pytest as _pytest
    with _pytest.raises(ValueError, match="Unbekannte Funddatum-Monate"):
        repo.list_objects(funddatum_monat_in=[7, 13])
    with _pytest.raises(ValueError, match="Unbekannte Funddatum-Monate"):
        repo.list_objects(funddatum_monat_in=[0])
    c.close()


def test_funddatum_jahrzehnt_in_filter(tmp_path):
    """funddatum_jahrzehnt_in akzeptiert diskrete Dekaden ('1980er ODER 2010er').

    Spiegelt funddatum_jahr_in, gruppiert aber per Integer-Div durch 10.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "di.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "1985-05-13"),   # 1980er
            ("OBJ_0002", "1989-11-30"),   # 1980er (rand)
            ("OBJ_0003", "1990-01-01"),   # 1990er (rand)
            ("OBJ_0004", "2015-08-01"),   # 2010er
            ("OBJ_0005", "2024-11-30"),   # 2020er
            ("OBJ_0006", ""),
            ("OBJ_0007", "kein-datum"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Diskrete Dekaden-Auswahl
    rows = repo.list_objects(funddatum_jahrzehnt_in=[1980, 2010])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelne Dekade
    rows = repo.list_objects(funddatum_jahrzehnt_in=[2020])
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Tupel akzeptiert
    rows = repo.list_objects(funddatum_jahrzehnt_in=(1990, 2020))
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0005"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(funddatum_jahrzehnt_in=[])
    assert len(rows) == 7
    # Dekade ohne Treffer
    rows = repo.list_objects(funddatum_jahrzehnt_in=[1900])
    assert rows == []
    # Kombiniert mit Jahres-Bereichsfilter (Schnittmenge: 1980er ∩ [1986..1989])
    rows = repo.list_objects(funddatum_jahrzehnt_in=[1980],
                              funddatum_jahr_min=1986)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Validierung: Nicht-Dekaden-Startzahlen sind ein Programmierfehler
    import pytest as _pytest
    with _pytest.raises(ValueError, match="Unbekannte Funddatum-Jahrzehnte"):
        repo.list_objects(funddatum_jahrzehnt_in=[1985])  # nicht durch 10 teilbar
    with _pytest.raises(ValueError, match="Unbekannte Funddatum-Jahrzehnte"):
        repo.list_objects(funddatum_jahrzehnt_in=[1700])  # vor 1800
    with _pytest.raises(ValueError, match="Unbekannte Funddatum-Jahrzehnte"):
        repo.list_objects(funddatum_jahrzehnt_in=[3000])  # nach 2990
    c.close()


def test_funddatum_monat_filter(tmp_path):
    """Saison-Filter ueber alle Jahre: 'alle Juli-Funde' unabhaengig vom Jahr."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "monat.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2020-07-15"),
            ("OBJ_0002", "2021-07-20"),   # auch Juli, anderes Jahr
            ("OBJ_0003", "2022-08-10"),   # August - faellt raus
            ("OBJ_0004", "2024-07-01"),
            ("OBJ_0005", "2024"),         # ohne Monatsteil - faellt raus
            ("OBJ_0006", ""),             # leer - faellt raus
            ("OBJ_0007", None),           # NULL - faellt raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(funddatum_monat=7)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Monat ohne Treffer -> leere Liste, kein Crash
    rows = repo.list_objects(funddatum_monat=3)
    assert rows == []
    c.close()


def test_funddatum_monat_kombiniert_mit_jahresbereich(tmp_path):
    """Schnittmenge mit Jahres-Filter: 'Juli-Funde 2021-2024'."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_y.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2019-07-15"),   # Juli, aber zu alt
            ("OBJ_0002", "2021-07-20"),
            ("OBJ_0003", "2024-07-01"),
            ("OBJ_0004", "2024-08-01"),   # August - faellt raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(funddatum_monat=7,
                              funddatum_jahr_min=2021, funddatum_jahr_max=2024)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    c.close()


def test_funddatum_monat_ungueltig_wirft_value_error(tmp_path):
    """Tippfehler 0/13/-1 erzeugen einen klaren Fehler statt eines leeren Ergebnisses."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "x.sqlite3")
    c.execute("INSERT INTO objects (obj_id, Funddatum) VALUES ('OBJ_0001', '2024-07-01')")
    c.commit()
    repo = ObjectRepo(c)
    with pytest.raises(ValueError, match="funddatum_monat"):
        repo.list_objects(funddatum_monat=0)
    with pytest.raises(ValueError, match="funddatum_monat"):
        repo.list_objects(funddatum_monat=13)
    with pytest.raises(ValueError, match="funddatum_monat"):
        repo.list_objects(funddatum_monat=-1)
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


def test_laenge_min_max_filter(tmp_path):
    """Vitrinen-/Sortierkasten-Auswahl per Laenge_mm-Bereich."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "lm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm) VALUES (?, ?)",
        [
            ("OBJ_0001", 30.0),
            ("OBJ_0002", 80.0),
            ("OBJ_0003", 200.0),
            ("OBJ_0004", None),     # ohne Vermessung -> faellt aus min-Filter raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Nur Min: alle ab 50 mm
    rows = repo.list_objects(laenge_min=50.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # Nur Max: alle bis 100 mm (NULL ist nicht <= 100)
    rows = repo.list_objects(laenge_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Kombiniert: 50 <= L <= 100
    rows = repo.list_objects(laenge_min=50.0, laenge_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_breite_min_max_filter(tmp_path):
    """Breiten-Filter analog Laenge_min/_max (Vitrinen-Auswahl auf zweiter Achse)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Breite_mm) VALUES (?, ?)",
        [
            ("OBJ_0001", 20.0),
            ("OBJ_0002", 60.0),
            ("OBJ_0003", 150.0),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(breite_min=40.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    rows = repo.list_objects(breite_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(breite_min=40.0, breite_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_hoehe_min_max_filter(tmp_path):
    """Hoehen-Filter analog Laenge_min/_max (Vitrinen-Auswahl auf dritter Achse)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Hoehe_mm) VALUES (?, ?)",
        [
            ("OBJ_0001", 10.0),
            ("OBJ_0002", 40.0),
            ("OBJ_0003", 90.0),
            ("OBJ_0004", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(hoehe_min=30.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    rows = repo.list_objects(hoehe_max=50.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(hoehe_min=30.0, hoehe_max=50.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_dimensionen_filter_kombiniert(tmp_path):
    """Vitrinen-Auswahl: alle drei Achsen gleichzeitig (passt in 100x100x50 Fach?)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "dim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", 80.0, 60.0, 30.0),    # passt komplett
            ("OBJ_0002", 80.0, 60.0, 80.0),    # zu hoch
            ("OBJ_0003", 120.0, 60.0, 30.0),   # zu lang
            ("OBJ_0004", 80.0, 120.0, 30.0),   # zu breit
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(
        laenge_max=100.0, breite_max=100.0, hoehe_max=50.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_mohs_min_max_filter(tmp_path):
    """Mohs-Haerte-Filter: Untergrenze auf Mohs_Haerte_min, Obergrenze auf Mohs_Haerte_max.

    Sammler-Fragen: ``mohs_min=7`` liefert schmucktaugliche Stuecke (Quarz und
    haerter), ``mohs_max=3`` liefert weiche Stuecke (Gips/Calcit). NULL-
    Eintraege fallen aus dem Filter raus (nicht bestimmte Haerte).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mohs.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 1.5, 2.0),    # Gips: weich
            ("OBJ_0002", 3.0, 3.0),    # Calcit
            ("OBJ_0003", 5.5, 6.0),    # Feldspat
            ("OBJ_0004", 7.0, 7.0),    # Quarz: schmucktauglich
            ("OBJ_0005", 8.0, 8.0),    # Topas
            ("OBJ_0006", None, None),  # nicht bestimmt
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Schmuck-Auswahl: nur Quarz und haerter.
    rows = repo.list_objects(mohs_min=7.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004", "OBJ_0005"]
    # Weiche Stuecke: nichts ueber 3 Mohs.
    rows = repo.list_objects(mohs_max=3.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Mittlere Haerte-Auswahl: Min>=3 UND Max<=7 (ganzer Bereich in 3..7).
    rows = repo.list_objects(mohs_min=3.0, mohs_max=7.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003", "OBJ_0004"]
    c.close()


def test_dichte_min_max_filter(tmp_path):
    """Dichte-Filter analog Mohs: Untergrenze auf Dichte_min_gcm3, Obergrenze auf _max.

    Sammler-Frage: ``dichte_min=5.0`` selektiert schwere Erz-Verdaechtige
    (Magnetit/Haematit/Galenit liegen ueber 5 g/cm3), ``dichte_max=2.0``
    selektiert leichte Aussen-Rohstoffe (Bims/Vulkanglas). NULL-Eintraege
    (nicht vermessen) fallen aus dem Filter raus.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "dichte.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 0.7, 0.9),    # Bims: leicht
            ("OBJ_0002", 2.5, 2.7),    # Quarz/Calcit-Familie
            ("OBJ_0003", 3.5, 4.0),    # Granat
            ("OBJ_0004", 5.0, 5.3),    # Haematit/Magnetit-Bereich
            ("OBJ_0005", 7.4, 7.6),    # Galenit (schwer)
            ("OBJ_0006", None, None),  # nicht vermessen
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Schwere Stuecke (Erz-Verdaechtige): nur Haematit-Bereich und Galenit.
    rows = repo.list_objects(dichte_min=5.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004", "OBJ_0005"]
    # Leichte Stuecke: nur Bims.
    rows = repo.list_objects(dichte_max=2.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Sammler-typische Mittel-Auswahl 2.5..4.0.
    rows = repo.list_objects(dichte_min=2.5, dichte_max=4.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    c.close()


def test_seltenheit_global_min_max_filter(tmp_path):
    """Globale Seltenheit (1..10) als Bereichsfilter mit Validierung.

    Sammler-Fragen: ``seltenheit_global_min=8`` selektiert die Vitrinen-
    Schaustuecke (Top-Rare), ``seltenheit_global_max=3`` liefert haeufige
    Stuecke (Tauschmaterial). Tippfehler 0/11 erzeugen einen klaren Fehler.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "selt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 1),     # haeufig
            ("OBJ_0002", 3),     # alltaeglich
            ("OBJ_0003", 6),     # gehobenes Mittel
            ("OBJ_0004", 8),     # selten
            ("OBJ_0005", 10),    # sehr selten
            ("OBJ_0006", None),  # nicht bewertet
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(seltenheit_global_min=8)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004", "OBJ_0005"]
    rows = repo.list_objects(seltenheit_global_max=3)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(seltenheit_global_min=4, seltenheit_global_max=8)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Validierung: out-of-range Tippfehler -> ValueError
    with pytest.raises(ValueError, match="1..10"):
        repo.list_objects(seltenheit_global_min=0)
    with pytest.raises(ValueError, match="1..10"):
        repo.list_objects(seltenheit_global_max=11)
    c.close()


def test_seltenheit_fundort_min_max_filter(tmp_path):
    """Standort-Seltenheit (1..10) als Bereichsfilter mit Validierung.

    Sammler-Frage: ``seltenheit_fundort_min=8`` selektiert Stuecke, die am
    Fundort selten sind (lokal interessant fuer lokale Sammler), waehrend
    ``seltenheit_fundort_max=3`` haeufige Fundort-Standardware liefert.
    Komplementaer zur globalen Sicht (siehe ``seltenheit_global_min/max``).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "selt_fo.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 1),     # am Standort sehr haeufig
            ("OBJ_0002", 3),     # haeufig
            ("OBJ_0003", 6),     # mittel
            ("OBJ_0004", 8),     # selten
            ("OBJ_0005", 10),    # am Standort sehr selten
            ("OBJ_0006", None),  # nicht bewertet
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(seltenheit_fundort_min=8)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004", "OBJ_0005"]
    rows = repo.list_objects(seltenheit_fundort_max=3)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(seltenheit_fundort_min=4, seltenheit_fundort_max=8)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Validierung: out-of-range Tippfehler -> ValueError
    with pytest.raises(ValueError, match="1..10"):
        repo.list_objects(seltenheit_fundort_min=0)
    with pytest.raises(ValueError, match="1..10"):
        repo.list_objects(seltenheit_fundort_max=11)
    c.close()


def test_seltenheit_fundort_und_global_kombiniert(tmp_path):
    """Filter laufen orthogonal: lokal selten UND global selten = Top-Vitrine."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "selt_kombi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10, "
        "Seltenheit_Fundort_1_10) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 9, 9),   # lokal+global selten -> Vitrinen-Schaustueck
            ("OBJ_0002", 9, 2),   # global selten, lokal Massenware
            ("OBJ_0003", 2, 9),   # global haeufig, lokal selten
            ("OBJ_0004", 2, 2),   # ueberall haeufig
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(seltenheit_global_min=8, seltenheit_fundort_min=8)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_nachfrage_min_max_filter(tmp_path):
    """Nachfrage (1..10) als Bereichsfilter mit Validierung.

    Sammler-Frage: ``nachfrage_min=7`` selektiert die Verkaufs-Kandidaten,
    ``nachfrage_max=3`` Tauschmaterial ohne akute Marktattraktivitaet.
    Tippfehler 0/11 erzeugen einen klaren Fehler.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 1),     # kaum Nachfrage
            ("OBJ_0002", 3),     # gering
            ("OBJ_0003", 5),     # mittel
            ("OBJ_0004", 7),     # gut
            ("OBJ_0005", 10),    # stark gefragt
            ("OBJ_0006", None),  # nicht bewertet
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(nachfrage_min=7)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004", "OBJ_0005"]
    rows = repo.list_objects(nachfrage_max=3)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(nachfrage_min=4, nachfrage_max=8)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    with pytest.raises(ValueError, match="1..10"):
        repo.list_objects(nachfrage_min=0)
    with pytest.raises(ValueError, match="1..10"):
        repo.list_objects(nachfrage_max=11)
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


def test_fundort_in_filter(tmp_path):
    """fundort_in akzeptiert Freitext-Mengen ('Davos ODER Zermatt ODER St. Gallen').

    Spiegelt mineral_in/varietaet_in/gesteinsart_in: Fundort ist Freitext
    (Ort plus optionale Detail-Angabe wie 'St. Gallen, Sitter'), daher
    keine Enum-Validierung; leere Strings werden uebersprungen.
    Sammler-Frage: 'zeig mir alle Funde meiner Lieblings-Fundorte'.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "fi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "Davos"),
            ("OBJ_0002", "Zermatt"),
            ("OBJ_0003", "St. Gallen, Sitter"),
            ("OBJ_0004", "Davos"),
            ("OBJ_0005", "Andermatt"),
            ("OBJ_0006", None),
            ("OBJ_0007", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Drei Lieblings-Fundorte
    rows = repo.list_objects(
        fundort_in=["Davos", "Zermatt", "St. Gallen, Sitter"])
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie fundort=
    rows = repo.list_objects(fundort_in=["Davos"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(fundort_in=[])
    assert len(rows) == 7
    # Tupel akzeptiert
    rows = repo.list_objects(fundort_in=("Andermatt",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Leere Strings werden uebersprungen (degeneriert nicht)
    rows = repo.list_objects(fundort_in=["", "Zermatt"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    rows = repo.list_objects(fundort_in=["", ""])
    assert len(rows) == 7
    # Unbekannter Fundort -> leeres Ergebnis (Freitext-Domaene)
    rows = repo.list_objects(fundort_in=["Mondsee"])
    assert rows == []
    # Kombiniert mit fundort= (Schnittmenge)
    rows = repo.list_objects(
        fundort="Davos",
        fundort_in=["Davos", "Zermatt"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit fundort_contains (Regions-Substring): findet exakte
    # Eintraege, die ZUSAETZLICH einen Substring enthalten - hier nur
    # St. Gallen mit Detail-Angabe.
    rows = repo.list_objects(
        fundort_in=["Davos", "Zermatt", "St. Gallen, Sitter"],
        fundort_contains="Sitter")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
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


def test_status_in_filter(tmp_path):
    """status_in akzeptiert Mengen ('aktiv ODER archiviert'); Tippfehler werfen ValueError."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "si.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, status) VALUES (?, ?)",
        [
            ("OBJ_0001", "aktiv"),
            ("OBJ_0002", "platzhalter"),
            ("OBJ_0003", "archiviert"),
            ("OBJ_0004", "aktiv"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter aktiv ODER archiviert
    rows = repo.list_objects(status_in=["aktiv", "archiviert"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # Einzelnes Element in der Liste (verhaelt sich wie status=)
    rows = repo.list_objects(status_in=["archiviert"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(status_in=[])
    assert len(rows) == 4
    # Tupel akzeptiert (unveraenderlich, fuer Default-Werte hilfreich)
    rows = repo.list_objects(status_in=("aktiv",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit status= (Schnittmenge, beide muessen passen)
    rows = repo.list_objects(status="aktiv", status_in=["aktiv", "archiviert"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Schnittmenge wird leer, wenn status nicht in status_in liegt
    rows = repo.list_objects(status="platzhalter", status_in=["aktiv", "archiviert"])
    assert rows == []
    # Tippfehler → ValueError
    with pytest.raises(ValueError, match="Unbekannte Status"):
        repo.list_objects(status_in=["geloescht"])
    c.close()


def test_kristallsystem_in_filter(tmp_path):
    """kristallsystem_in akzeptiert Mengen ('trigonal ODER hexagonal' fuer Quarz-Familie); Tippfehler werfen ValueError."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ksi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [
            ("OBJ_0001", "trigonal"),
            ("OBJ_0002", "hexagonal"),
            ("OBJ_0003", "kubisch"),
            ("OBJ_0004", "trigonal"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter trigonal ODER hexagonal (Quarz-Familie)
    rows = repo.list_objects(kristallsystem_in=["trigonal", "hexagonal"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie kristallsystem=
    rows = repo.list_objects(kristallsystem_in=["kubisch"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(kristallsystem_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(kristallsystem_in=("trigonal",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit kristallsystem= (Schnittmenge)
    rows = repo.list_objects(
        kristallsystem="trigonal",
        kristallsystem_in=["trigonal", "hexagonal"],
    )
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Schnittmenge wird leer, wenn kristallsystem nicht in der Menge liegt
    rows = repo.list_objects(
        kristallsystem="kubisch",
        kristallsystem_in=["trigonal", "hexagonal"],
    )
    assert rows == []
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Kristallsystem-Werte"):
        repo.list_objects(kristallsystem_in=["pseudokubisch"])
    # Mehrere Tippfehler werden gemeinsam gemeldet
    with pytest.raises(ValueError, match="pseudokubisch"):
        repo.list_objects(kristallsystem_in=["trigonal", "pseudokubisch"])
    c.close()


def test_glanz_in_filter(tmp_path):
    """glanz_in akzeptiert Mengen ('glasig ODER metallisch'); Tippfehler werfen ValueError."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "glz.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?, ?)",
        [
            ("OBJ_0001", "glasig"),
            ("OBJ_0002", "metallisch"),
            ("OBJ_0003", "matt"),
            ("OBJ_0004", "glasig"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter glasig ODER metallisch (optische Auswahl)
    rows = repo.list_objects(glanz_in=["glasig", "metallisch"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie glanz=
    rows = repo.list_objects(glanz_in=["matt"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(glanz_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(glanz_in=("glasig",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit glanz= (Schnittmenge)
    rows = repo.list_objects(
        glanz="glasig",
        glanz_in=["glasig", "metallisch"],
    )
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Schnittmenge wird leer, wenn glanz nicht in der Menge liegt
    rows = repo.list_objects(
        glanz="matt",
        glanz_in=["glasig", "metallisch"],
    )
    assert rows == []
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Glanz-Werte"):
        repo.list_objects(glanz_in=["spiegelnd"])
    # Mehrere Tippfehler werden gemeinsam gemeldet
    with pytest.raises(ValueError, match="spiegelnd"):
        repo.list_objects(glanz_in=["glasig", "spiegelnd"])
    c.close()


def test_transparenz_in_filter(tmp_path):
    """transparenz_in akzeptiert Mengen ('durchsichtig ODER durchscheinend'); Tippfehler werfen ValueError."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "trz.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?, ?)",
        [
            ("OBJ_0001", "durchsichtig"),
            ("OBJ_0002", "durchscheinend"),
            ("OBJ_0003", "opak"),
            ("OBJ_0004", "durchsichtig"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter durchsichtig ODER durchscheinend (Foto-Setup mit Backlight)
    rows = repo.list_objects(transparenz_in=["durchsichtig", "durchscheinend"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie transparenz=
    rows = repo.list_objects(transparenz_in=["opak"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(transparenz_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(transparenz_in=("durchsichtig",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit transparenz= (Schnittmenge)
    rows = repo.list_objects(
        transparenz="durchsichtig",
        transparenz_in=["durchsichtig", "durchscheinend"],
    )
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Schnittmenge wird leer, wenn transparenz nicht in der Menge liegt
    rows = repo.list_objects(
        transparenz="opak",
        transparenz_in=["durchsichtig", "durchscheinend"],
    )
    assert rows == []
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Transparenz-Werte"):
        repo.list_objects(transparenz_in=["halbtransparent"])
    # Mehrere Tippfehler werden gemeinsam gemeldet
    with pytest.raises(ValueError, match="halbtransparent"):
        repo.list_objects(transparenz_in=["durchsichtig", "halbtransparent"])
    c.close()


def test_magnetismus_in_filter(tmp_path):
    """magnetismus_in akzeptiert Mengen ('ja ODER schwach'); Tippfehler werfen ValueError.

    Eisen-Auswahl: alle reagierenden Stuecke (Magnetit/Pyrrhotin/Haematit) in
    einer Sicht, ohne die inerten Quarz-/Calcit-Stuecke. Spiegelt
    transparenz_in/glanz_in: gegen VALID_MAGNETISMUS validiert.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mag.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [
            ("OBJ_0001", "ja"),
            ("OBJ_0002", "schwach"),
            ("OBJ_0003", "nein"),
            ("OBJ_0004", "ja"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter ja ODER schwach (alle eisenhaltigen Stuecke)
    rows = repo.list_objects(magnetismus_in=["ja", "schwach"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag
    rows = repo.list_objects(magnetismus_in=["nein"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(magnetismus_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(magnetismus_in=("ja",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Magnetismus-Werte"):
        repo.list_objects(magnetismus_in=["paramagnetisch"])
    # Mehrere Tippfehler werden gemeinsam gemeldet
    with pytest.raises(ValueError, match="paramagnetisch"):
        repo.list_objects(magnetismus_in=["ja", "paramagnetisch"])
    c.close()


def test_spaltbarkeit_in_filter(tmp_path):
    """spaltbarkeit_in akzeptiert Mengen ('vollkommen ODER gut'); Tippfehler werfen ValueError.

    Praeparier-Auswahl: alle sauber spaltbaren Stuecke (Calcit/Fluorit/Glimmer)
    in einer Sicht, ohne die zaehen Quarz-Brocken (keine). Spiegelt
    magnetismus_in/transparenz_in: gegen VALID_SPALTBARKEIT validiert.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "spk.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?, ?)",
        [
            ("OBJ_0001", "vollkommen"),
            ("OBJ_0002", "gut"),
            ("OBJ_0003", "keine"),
            ("OBJ_0004", "vollkommen"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter vollkommen ODER gut (alle sauber spaltbaren Stuecke)
    rows = repo.list_objects(spaltbarkeit_in=["vollkommen", "gut"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag
    rows = repo.list_objects(spaltbarkeit_in=["keine"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(spaltbarkeit_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(spaltbarkeit_in=("vollkommen",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Spaltbarkeit-Werte"):
        repo.list_objects(spaltbarkeit_in=["nicht_existent"])
    # Mehrere Tippfehler werden gemeinsam gemeldet
    with pytest.raises(ValueError, match="nicht_existent"):
        repo.list_objects(spaltbarkeit_in=["vollkommen", "nicht_existent"])
    c.close()


def test_bruch_in_filter(tmp_path):
    """bruch_in akzeptiert Mengen ('muschelig ODER splittrig'); Tippfehler werfen ValueError.

    Schaerfekanten-Auswahl: Stuecke, die ohne Spaltflaechen scharfe Kanten
    erzeugen (Obsidian/Quarz/Feuerstein), in einer Sicht ohne fasrige
    Aktinolith-Stuecke. Spiegelt spaltbarkeit_in/magnetismus_in: gegen
    VALID_BRUCH validiert.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "br.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?, ?)",
        [
            ("OBJ_0001", "muschelig"),
            ("OBJ_0002", "splittrig"),
            ("OBJ_0003", "faserig"),
            ("OBJ_0004", "muschelig"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter muschelig ODER splittrig (Schaerfekanten-Stuecke)
    rows = repo.list_objects(bruch_in=["muschelig", "splittrig"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag
    rows = repo.list_objects(bruch_in=["faserig"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(bruch_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(bruch_in=("muschelig",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Bruch-Werte"):
        repo.list_objects(bruch_in=["ungueltig"])
    # Mehrere Tippfehler werden gemeinsam gemeldet
    with pytest.raises(ValueError, match="ungueltig"):
        repo.list_objects(bruch_in=["muschelig", "ungueltig"])
    c.close()


def test_beste_verwendung_in_filter(tmp_path):
    """beste_verwendung_in akzeptiert Mengen ('Schmuck ODER Sammlung'); Tippfehler werfen ValueError."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bvi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [
            ("OBJ_0001", "Schmuck"),
            ("OBJ_0002", "Sammlung"),
            ("OBJ_0003", "Industrie"),
            ("OBJ_0004", "Schmuck"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter Schmuck ODER Sammlung (Sammler-typische Frage)
    rows = repo.list_objects(beste_verwendung_in=["Schmuck", "Sammlung"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie beste_verwendung=
    rows = repo.list_objects(beste_verwendung_in=["Industrie"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(beste_verwendung_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(beste_verwendung_in=("Schmuck",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit beste_verwendung= (Schnittmenge)
    rows = repo.list_objects(
        beste_verwendung="Schmuck",
        beste_verwendung_in=["Schmuck", "Sammlung"],
    )
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Beste_Verwendung-Werte"):
        repo.list_objects(beste_verwendung_in=["Goldschmuck"])
    c.close()


def test_kategorie_in_filter(tmp_path):
    """kategorie_in akzeptiert Mengen ('Handstueck ODER Kristall'); Tippfehler werfen ValueError."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "kati.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
        [
            ("OBJ_0001", "Handstück"),
            ("OBJ_0002", "Kristall"),
            ("OBJ_0003", "Geröll"),
            ("OBJ_0004", "Handstück"),
            ("OBJ_0005", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter Handstueck ODER Kristall
    rows = repo.list_objects(kategorie_in=["Handstück", "Kristall"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie kategorie=
    rows = repo.list_objects(kategorie_in=["Geröll"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste → kein Filter
    rows = repo.list_objects(kategorie_in=[])
    assert len(rows) == 5
    # Tupel akzeptiert
    rows = repo.list_objects(kategorie_in=("Handstück",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit kategorie= (Schnittmenge)
    rows = repo.list_objects(
        kategorie="Handstück",
        kategorie_in=["Handstück", "Kristall"],
    )
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Schnittmenge wird leer, wenn kategorie nicht in der Menge liegt
    rows = repo.list_objects(
        kategorie="Geröll",
        kategorie_in=["Handstück", "Kristall"],
    )
    assert rows == []
    # Tippfehler → ValueError mit klarer Diagnose
    with pytest.raises(ValueError, match="Unbekannte Kategorie-Werte"):
        repo.list_objects(kategorie_in=["Pseudo-Kategorie"])
    # Mehrere Tippfehler werden gemeinsam gemeldet
    with pytest.raises(ValueError, match="Pseudo"):
        repo.list_objects(kategorie_in=["Kristall", "Pseudo-Kategorie"])
    c.close()


def test_mineral_in_filter(tmp_path):
    """mineral_in akzeptiert Freitext-Mengen ('Quarz ODER Calcit ODER Pyrit').

    Mineral_Primaer ist Freitext (kein Feldwoerterbuch-Enum), daher keine
    Enum-Validierung wie bei kategorie_in/status_in - der GUI-Caller liefert
    die Werte aus distinct_values(). Leere Strings werden uebersprungen,
    damit kein degenerierter IN-Filter entsteht.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer) VALUES (?, ?)",
        [
            ("OBJ_0001", "Quarz"),
            ("OBJ_0002", "Calcit"),
            ("OBJ_0003", "Pyrit"),
            ("OBJ_0004", "Quarz"),
            ("OBJ_0005", "Feldspat"),
            ("OBJ_0006", None),
            ("OBJ_0007", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Mengen-Filter: drei klassische Mineral-Familien gleichzeitig
    rows = repo.list_objects(mineral_in=["Quarz", "Calcit", "Pyrit"])
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie mineral=
    rows = repo.list_objects(mineral_in=["Quarz"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Leere Liste -> kein Filter (alle 7 Test-Objekte)
    rows = repo.list_objects(mineral_in=[])
    assert len(rows) == 7
    # Tupel akzeptiert (unveraenderlich, fuer Default-Werte hilfreich)
    rows = repo.list_objects(mineral_in=("Calcit",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Leere Strings in der Menge werden uebersprungen (entstehen z.B. aus
    # einem "Alle"-Eintrag im Multiselect); der Filter degeneriert nicht.
    rows = repo.list_objects(mineral_in=["", "Pyrit"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Reine Leerstrings -> kein Filter (alle 7 Test-Objekte)
    rows = repo.list_objects(mineral_in=["", ""])
    assert len(rows) == 7
    # Unbekanntes Mineral -> leeres Ergebnis, kein Crash (Freitext-Domaene)
    rows = repo.list_objects(mineral_in=["Mondgestein"])
    assert rows == []
    # Kombiniert mit mineral= (Schnittmenge, beide muessen passen)
    rows = repo.list_objects(
        mineral="Quarz", mineral_in=["Quarz", "Calcit"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Schnittmenge wird leer, wenn mineral nicht in der Menge liegt
    rows = repo.list_objects(
        mineral="Pyrit", mineral_in=["Quarz", "Calcit"])
    assert rows == []
    # Kombiniert mit mineral_contains (Familien-Substring): Schnittmenge
    # findet "Quarz" UND alles, was den Substring 'arz' enthaelt
    rows = repo.list_objects(
        mineral_in=["Quarz", "Calcit"], mineral_contains="arz")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    c.close()


def test_has_und_missing_image_kategorie_filter(tmp_path):
    """Foto-Workflow: finde Objekte mit/ohne Bild einer bestimmten Bild-Kategorie."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "imc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Uebersicht", "objects/OBJ_0001/u1.jpg"),
            ("OBJ_0001", "UV365",       "objects/OBJ_0001/uv.jpg"),
            ("OBJ_0002", "Uebersicht", "objects/OBJ_0002/u2.jpg"),
            # OBJ_0003 hat ueberhaupt kein Bild
            ("OBJ_0004", "Kamera",      "objects/OBJ_0004/k.jpg"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Objekte mit Uebersichts-Bild
    rows = repo.list_objects(has_image_kategorie="Uebersicht")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Objekte MIT UV365-Bild
    rows = repo.list_objects(has_image_kategorie="UV365")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Objekte OHNE UV365-Bild (inkl. ohne Bilder ueberhaupt)
    rows = repo.list_objects(missing_image_kategorie="UV365")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Kombinierbar: hat Uebersicht UND es fehlt UV365 → OBJ_0002
    rows = repo.list_objects(has_image_kategorie="Uebersicht",
                             missing_image_kategorie="UV365")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Unbekannte Kategorie → ValueError (Tippschutz)
    with pytest.raises(ValueError):
        repo.list_objects(has_image_kategorie="UV999")
    with pytest.raises(ValueError):
        repo.list_objects(missing_image_kategorie="UV999")
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


def test_varietaet_in_filter(tmp_path):
    """varietaet_in akzeptiert Freitext-Mengen ('Bergkristall ODER Milchquarz').

    Spiegelt mineral_in: Varietaet ist Freitext, keine Enum-Validierung;
    leere Strings werden uebersprungen. Sammler-Frage: 'zeig mir alle
    benannten Quarz-Varianten' (Auswahl aus dem distinct_values-Dropdown).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?, ?)",
        [
            ("OBJ_0001", "Bergkristall"),
            ("OBJ_0002", "Milchquarz"),
            ("OBJ_0003", "Rauchquarz"),
            ("OBJ_0004", "Bergkristall"),
            ("OBJ_0005", "Achat"),
            ("OBJ_0006", None),
            ("OBJ_0007", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Quarz-Familien-Auswahl
    rows = repo.list_objects(
        varietaet_in=["Bergkristall", "Milchquarz", "Rauchquarz"])
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie varietaet=
    rows = repo.list_objects(varietaet_in=["Bergkristall"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(varietaet_in=[])
    assert len(rows) == 7
    # Tupel akzeptiert
    rows = repo.list_objects(varietaet_in=("Achat",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Leere Strings werden uebersprungen (degeneriert nicht)
    rows = repo.list_objects(varietaet_in=["", "Rauchquarz"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    rows = repo.list_objects(varietaet_in=["", ""])
    assert len(rows) == 7
    # Unbekannte Varietaet -> leeres Ergebnis (Freitext-Domaene)
    rows = repo.list_objects(varietaet_in=["Mondquarz"])
    assert rows == []
    # Kombiniert mit varietaet= (Schnittmenge)
    rows = repo.list_objects(
        varietaet="Bergkristall",
        varietaet_in=["Bergkristall", "Milchquarz"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit varietaet_contains (Substring-Familie)
    rows = repo.list_objects(
        varietaet_in=["Bergkristall", "Milchquarz", "Achat"],
        varietaet_contains="quarz")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
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


def test_gesteinsart_in_filter(tmp_path):
    """gesteinsart_in akzeptiert Freitext-Mengen ('Granit ODER Gneis ODER Basalt').

    Spiegelt mineral_in/varietaet_in: Gesteinsart ist Freitext, keine
    Enum-Validierung; leere Strings werden uebersprungen. Sammler-Frage:
    'zeig mir alle magmatischen Gesteine in der Sammlung'.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [
            ("OBJ_0001", "Granit"),
            ("OBJ_0002", "Gneis"),
            ("OBJ_0003", "Basalt"),
            ("OBJ_0004", "Granit"),
            ("OBJ_0005", "Sandstein"),
            ("OBJ_0006", None),
            ("OBJ_0007", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Magmatisch + metamorph
    rows = repo.list_objects(gesteinsart_in=["Granit", "Gneis", "Basalt"])
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Einzelner Eintrag verhaelt sich wie gesteinsart=
    rows = repo.list_objects(gesteinsart_in=["Granit"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(gesteinsart_in=[])
    assert len(rows) == 7
    # Tupel akzeptiert
    rows = repo.list_objects(gesteinsart_in=("Sandstein",))
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Leere Strings werden uebersprungen (degeneriert nicht)
    rows = repo.list_objects(gesteinsart_in=["", "Basalt"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    rows = repo.list_objects(gesteinsart_in=["", ""])
    assert len(rows) == 7
    # Unbekannte Gesteinsart -> leeres Ergebnis (Freitext-Domaene)
    rows = repo.list_objects(gesteinsart_in=["Mondgestein"])
    assert rows == []
    # Kombiniert mit gesteinsart= (Schnittmenge)
    rows = repo.list_objects(
        gesteinsart="Granit",
        gesteinsart_in=["Granit", "Gneis"])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Kombiniert mit gesteinsart_contains (Substring-Familie)
    rows = repo.list_objects(
        gesteinsart_in=["Granit", "Gneis", "Sandstein"],
        gesteinsart_contains="stein")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    c.close()


def test_gesteinsart_contains_filter(tmp_path):
    """Substring-Filter ueber Gesteinsart findet Gesteins-Familien (Granit-Klan)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [
            ("OBJ_0001", "Biotitgranit"),
            ("OBJ_0002", "Rosa Granit"),
            ("OBJ_0003", "Basalt"),
            ("OBJ_0004", "Gran_4 Probe"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring matched beide Granit-Varianten
    rows = repo.list_objects(gesteinsart_contains="Granit")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # ASCII-case-insensitive
    rows = repo.list_objects(gesteinsart_contains="granit")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Andere Gesteinsart
    rows = repo.list_objects(gesteinsart_contains="Basalt")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Metazeichen wortwoertlich (_ wird nicht als beliebiges Zeichen interpretiert)
    rows = repo.list_objects(gesteinsart_contains="Gran_4")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    rows = repo.list_objects(gesteinsart_contains="GranX4")
    assert rows == []
    # NULL Gesteinsart fliegt automatisch raus
    rows = repo.list_objects(gesteinsart_contains="a")
    assert all(r["obj_id"] != "OBJ_0005" for r in rows)
    # Kombinierbar mit exaktem gesteinsart-Filter (Schnittmenge)
    rows = repo.list_objects(gesteinsart_contains="Granit", gesteinsart="Rosa Granit")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
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


def test_erstellt_am_jahr_range_filter(tmp_path):
    """erstellt_am_jahr_min/max filtert nach Erfassungs-Jahr (analog funddatum_jahr).

    Spiegelt funddatum_jahr_min/_max auf die Erfassungs-Achse und ergaenzt das
    by_erstellt_am_jahr-Aggregat aus stats.py um den Listen-Drill-down.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ey.sqlite3")
    # erstellt_am direkt setzen, damit der Test deterministisch ist (sonst
    # waere alles auf das aktuelle Jahr fixiert via _now()).
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2018-05-13 10:00:00"),
            ("OBJ_0002", "2020-08-01 11:30:00"),
            ("OBJ_0003", "2022-01-01 12:00:00"),
            ("OBJ_0004", "2024-11-30 14:15:00"),
            ("OBJ_0005", ""),            # ohne Stempel → faellt raus
            ("OBJ_0006", "kein-datum"),  # ungueltig → faellt raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(erstellt_am_jahr_min=2020, erstellt_am_jahr_max=2022)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]

    rows = repo.list_objects(erstellt_am_jahr_min=2023)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]

    rows = repo.list_objects(erstellt_am_jahr_max=2018)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_geaendert_am_jahr_range_filter(tmp_path):
    """geaendert_am_jahr_min/max filtert nach Aenderungs-Jahr.

    Spiegelt erstellt_am_jahr_min/_max auf die zweite Zeitstempel-Achse
    (geaendert_am, redaktionelle Pflege) und beantwortet die Frage
    "welche Stuecke habe ich dieses Jahr noch beruehrt?". Default-Verhalten
    der Anwendung: bei create() ist erstellt_am == geaendert_am; beide
    Achsen divergieren erst durch ein update_fields() nach dem Anlegen.
    Hier setzt der Test die geaendert_am-Spalte direkt, damit das Pflege-
    Szenario unabhaengig vom Erfassungs-Stempel testbar bleibt.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gy.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) "
        "VALUES (?, ?, ?)",
        [
            # Erfasst 2018, seit Jahren unangetastet (geaendert == erstellt).
            ("OBJ_0001", "2018-05-13 10:00:00", "2018-05-13 10:00:00"),
            # Erfasst 2018, aber 2020 ueberarbeitet (Datenblatt-Update).
            ("OBJ_0002", "2018-05-13 10:00:00", "2020-08-01 11:30:00"),
            # Erfasst 2020, 2022 ueberarbeitet.
            ("OBJ_0003", "2020-01-01 09:00:00", "2022-01-01 12:00:00"),
            # Erfasst 2022, 2024 ueberarbeitet (frische Pflege).
            ("OBJ_0004", "2022-03-15 08:00:00", "2024-11-30 14:15:00"),
            ("OBJ_0005", "", ""),                  # ohne Stempel -> faellt raus
            ("OBJ_0006", "kein-datum", "kein-datum"),  # ungueltig -> faellt raus
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # 2020..2022 angefasst: nur Stuecke mit einem Pflege-Touch in dem Zeitraum.
    rows = repo.list_objects(geaendert_am_jahr_min=2020, geaendert_am_jahr_max=2022)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]

    rows = repo.list_objects(geaendert_am_jahr_min=2023)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]

    rows = repo.list_objects(geaendert_am_jahr_max=2018)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]

    # Orthogonal zur Erfassungs-Achse: OBJ_0002 ist 2018 erfasst, aber
    # 2020 angefasst worden - der Schnitt der beiden Achsen ist nicht leer.
    rows = repo.list_objects(erstellt_am_jahr_max=2018,
                              geaendert_am_jahr_min=2020)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_geaendert_am_jahr_in_filter(tmp_path):
    """geaendert_am_jahr_in akzeptiert diskrete Aenderungs-Jahre (Pflege-Schuebe).

    Spiegelt erstellt_am_jahr_in / funddatum_jahr_in auf die zweite Zeitstempel-
    Spalte: ein Stueck zaehlt fuer das Jahr, in dem die letzte redaktionelle
    Beruehrung stattfand. Typische Anwendung: zwei Pflege-Wellen nach
    Boersen-Besuchen ("nach Tucson 2022 ODER nach Muenchen 2024 nachbearbeitet").
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gyi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) "
        "VALUES (?, ?, ?)",
        [
            # Erfasst 2018, seit Jahren unangetastet (geaendert == erstellt).
            ("OBJ_0001", "2018-05-13 10:00:00", "2018-05-13 10:00:00"),
            # 2018 erfasst, 2020 ueberarbeitet.
            ("OBJ_0002", "2018-05-13 10:00:00", "2020-08-01 11:30:00"),
            # 2020 erfasst, 2022 ueberarbeitet (Tucson-Nachbearbeitung).
            ("OBJ_0003", "2020-01-01 09:00:00", "2022-01-01 12:00:00"),
            # 2022 erfasst, 2024 ueberarbeitet (Muenchen-Nachbearbeitung).
            ("OBJ_0004", "2022-03-15 08:00:00", "2024-11-30 14:15:00"),
            ("OBJ_0005", "", ""),
            ("OBJ_0006", "kein-datum", "kein-datum"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Diskrete Mengen-Auswahl: zwei Pflege-Wellen (Tucson 2022, Muenchen 2024).
    rows = repo.list_objects(geaendert_am_jahr_in=[2022, 2024])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Einzelnes Jahr verhaelt sich wie min=max
    rows = repo.list_objects(geaendert_am_jahr_in=[2020])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Tupel akzeptiert
    rows = repo.list_objects(geaendert_am_jahr_in=(2018, 2022))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0003"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(geaendert_am_jahr_in=[])
    assert len(rows) == 6
    # Jahr ohne Treffer -> leeres Ergebnis
    rows = repo.list_objects(geaendert_am_jahr_in=[1999])
    assert rows == []
    # Kombiniert mit Bereichsfilter (Schnittmenge)
    rows = repo.list_objects(geaendert_am_jahr_in=[2018, 2020, 2024],
                              geaendert_am_jahr_min=2020,
                              geaendert_am_jahr_max=2023)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Orthogonal zur Erfassungs-Achse: OBJ_0002 ist 2018 erfasst, aber 2020
    # angefasst worden - der Schnitt der beiden Achsen ist nicht leer.
    rows = repo.list_objects(erstellt_am_jahr_in=[2018],
                              geaendert_am_jahr_in=[2020])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Ungueltige Jahresangaben -> ValueError
    with pytest.raises(ValueError, match="Unbekannte Geaendert-am-Jahre"):
        repo.list_objects(geaendert_am_jahr_in=[2020, 9999])
    with pytest.raises(ValueError, match="Unbekannte Geaendert-am-Jahre"):
        repo.list_objects(geaendert_am_jahr_in=[1700])
    c.close()


def test_geaendert_am_jahrzehnt_in_filter(tmp_path):
    """geaendert_am_jahrzehnt_in akzeptiert diskrete Aenderungs-Dekaden.

    Spiegelt erstellt_am_jahrzehnt_in / funddatum_jahrzehnt_in auf die zweite
    Zeitstempel-Spalte: gruppiert das Jahr per Integer-Div durch 10 und
    vergleicht mit der angegebenen Dekaden-Startzahl. 2010er trennt typisch
    die haendische Pflege-Generation vom Migrations-/KI-Schub der 2020er.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gdi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) "
        "VALUES (?, ?, ?)",
        [
            # 2010er-Welle (haendische Pflege).
            ("OBJ_0001", "2012-05-13 10:00:00", "2012-05-13 10:00:00"),
            ("OBJ_0002", "2018-05-13 10:00:00", "2019-08-01 11:30:00"),
            # 2020er-Welle (Migrations-/KI-Phase, Rand-Jahr 2020 zaehlt zur 2020er).
            ("OBJ_0003", "2020-01-01 09:00:00", "2020-01-01 09:00:00"),
            ("OBJ_0004", "2022-03-15 08:00:00", "2024-11-30 14:15:00"),
            ("OBJ_0005", "", ""),
            ("OBJ_0006", "kein-datum", "kein-datum"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Diskrete Dekaden-Auswahl
    rows = repo.list_objects(geaendert_am_jahrzehnt_in=[2010, 2020])
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Einzelne Dekade
    rows = repo.list_objects(geaendert_am_jahrzehnt_in=[2010])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(geaendert_am_jahrzehnt_in=[2020])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Tupel akzeptiert
    rows = repo.list_objects(geaendert_am_jahrzehnt_in=(2020,))
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(geaendert_am_jahrzehnt_in=[])
    assert len(rows) == 6
    # Dekade ohne Treffer
    rows = repo.list_objects(geaendert_am_jahrzehnt_in=[1980])
    assert rows == []
    # Kombiniert mit Jahres-Bereichsfilter (Schnittmenge): 2010er ∩ [>=2015]
    rows = repo.list_objects(geaendert_am_jahrzehnt_in=[2010],
                              geaendert_am_jahr_min=2015)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Ungueltige Dekaden (nicht durch 10 teilbar / ausserhalb 1800..2990)
    with pytest.raises(ValueError, match="Unbekannte Geaendert-am-Jahrzehnte"):
        repo.list_objects(geaendert_am_jahrzehnt_in=[2015])
    with pytest.raises(ValueError, match="Unbekannte Geaendert-am-Jahrzehnte"):
        repo.list_objects(geaendert_am_jahrzehnt_in=[1700])
    with pytest.raises(ValueError, match="Unbekannte Geaendert-am-Jahrzehnte"):
        repo.list_objects(geaendert_am_jahrzehnt_in=[3000])
    c.close()


def test_geaendert_am_monat_filter(tmp_path):
    """geaendert_am_monat filtert nach Aenderungs-Monat ueber alle Jahre.

    Spiegelt erstellt_am_monat / funddatum_monat auf die zweite Zeitstempel-
    Spalte: in welchen Monaten habe ich zuletzt redaktionell am Bestand
    gearbeitet? Typisch Winter-Pflege (Indoor-Phase November-Januar,
    Boersen-Nachbearbeitung Februar/Maerz nach Tucson).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) "
        "VALUES (?, ?, ?)",
        [
            # Januar-Pflege (Indoor-Phase)
            ("OBJ_0001", "2018-07-13 10:00:00", "2020-01-15 10:00:00"),
            # Februar-Pflege (Tucson-Nachbearbeitung)
            ("OBJ_0002", "2018-05-13 10:00:00", "2021-02-20 11:30:00"),
            # Juli-Pflege (selten)
            ("OBJ_0003", "2020-01-01 09:00:00", "2022-07-10 12:00:00"),
            # Dezember-Pflege (Muenchen-Nachbearbeitung)
            ("OBJ_0004", "2022-03-15 08:00:00", "2024-12-01 14:15:00"),
            # Geaendert_am ohne Monatsteil -> faellt raus
            ("OBJ_0005", "2024-05-13 10:00:00", "2024"),
            ("OBJ_0006", "", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(geaendert_am_monat=1)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    rows = repo.list_objects(geaendert_am_monat=12)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    rows = repo.list_objects(geaendert_am_monat=7)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Monat ohne Treffer
    rows = repo.list_objects(geaendert_am_monat=8)
    assert rows == []
    # Orthogonal zur Erfassungs-Achse: OBJ_0003 ist im Januar erfasst, aber
    # im Juli gepflegt - der Schnitt der beiden Achsen ist nicht leer.
    rows = repo.list_objects(erstellt_am_monat=1, geaendert_am_monat=7)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Validierung
    with pytest.raises(ValueError, match="geaendert_am_monat"):
        repo.list_objects(geaendert_am_monat=0)
    with pytest.raises(ValueError, match="geaendert_am_monat"):
        repo.list_objects(geaendert_am_monat=13)
    c.close()


def test_geaendert_am_monat_in_filter(tmp_path):
    """geaendert_am_monat_in akzeptiert diskrete Aenderungs-Monate (Pflege-Spitzen).

    Spiegelt erstellt_am_monat_in / funddatum_monat_in auf die Aenderungs-Achse:
    mehrere Pflege-Spitzen kombinieren (Indoor-Block November/Dezember/Januar
    oder Boersen-Nachbearbeitung Februar Tucson + Oktober Sainte-Marie-aux-Mines).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gmi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) "
        "VALUES (?, ?, ?)",
        [
            # November-Pflege
            ("OBJ_0001", "2018-05-13 10:00:00", "2020-11-10 10:00:00"),
            # Dezember-Pflege
            ("OBJ_0002", "2018-05-13 10:00:00", "2020-12-15 11:30:00"),
            # Januar-Pflege
            ("OBJ_0003", "2020-01-01 09:00:00", "2022-01-20 12:00:00"),
            # Juli-Pflege (faellt aus Indoor-Block raus)
            ("OBJ_0004", "2022-03-15 08:00:00", "2024-07-05 14:15:00"),
            # Geaendert_am ohne Monatsteil -> faellt raus
            ("OBJ_0005", "2024-05-13 10:00:00", "2024"),
            ("OBJ_0006", "", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Indoor-Block November/Dezember/Januar
    rows = repo.list_objects(geaendert_am_monat_in=[11, 12, 1])
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Einzelner Monat verhaelt sich wie geaendert_am_monat
    rows = repo.list_objects(geaendert_am_monat_in=[7])
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    # Tupel akzeptiert
    rows = repo.list_objects(geaendert_am_monat_in=(11, 12))
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(geaendert_am_monat_in=[])
    assert len(rows) == 6
    # Monate ohne Treffer
    rows = repo.list_objects(geaendert_am_monat_in=[3, 4, 5])
    assert rows == []
    # Kombiniert mit Bereichsfilter (Schnittmenge): Indoor-Block ∩ 2022+
    rows = repo.list_objects(geaendert_am_monat_in=[11, 12, 1],
                              geaendert_am_jahr_min=2022)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Ungueltige Monate -> ValueError
    with pytest.raises(ValueError, match="Unbekannte Geaendert-am-Monate"):
        repo.list_objects(geaendert_am_monat_in=[1, 13])
    with pytest.raises(ValueError, match="Unbekannte Geaendert-am-Monate"):
        repo.list_objects(geaendert_am_monat_in=[0])
    c.close()


def test_erstellt_am_jahr_in_filter(tmp_path):
    """erstellt_am_jahr_in akzeptiert diskrete Erfassungs-Jahre (Migrations-Wellen)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "eyi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2018-05-13 10:00:00"),
            ("OBJ_0002", "2020-08-01 11:30:00"),
            ("OBJ_0003", "2022-01-01 12:00:00"),
            ("OBJ_0004", "2024-11-30 14:15:00"),
            ("OBJ_0005", ""),
            ("OBJ_0006", "kein-datum"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Diskrete Mengen-Auswahl
    rows = repo.list_objects(erstellt_am_jahr_in=[2018, 2022, 2024])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # Einzelnes Jahr verhaelt sich wie min=max
    rows = repo.list_objects(erstellt_am_jahr_in=[2020])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Tupel akzeptiert
    rows = repo.list_objects(erstellt_am_jahr_in=(2020, 2022))
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(erstellt_am_jahr_in=[])
    assert len(rows) == 6
    # Jahr ohne Treffer -> leeres Ergebnis
    rows = repo.list_objects(erstellt_am_jahr_in=[1999])
    assert rows == []
    # Kombiniert mit Bereichsfilter (Schnittmenge)
    rows = repo.list_objects(erstellt_am_jahr_in=[2018, 2020, 2024],
                              erstellt_am_jahr_min=2020, erstellt_am_jahr_max=2023)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Kombiniert mit funddatum_jahr_in: orthogonale Achsen
    c.execute("UPDATE objects SET Funddatum = '1985-05-13' WHERE obj_id = 'OBJ_0001'")
    c.execute("UPDATE objects SET Funddatum = '2024-08-01' WHERE obj_id = 'OBJ_0002'")
    c.commit()
    rows = repo.list_objects(erstellt_am_jahr_in=[2020],
                              funddatum_jahr_in=[2024])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Ungueltige Jahresangaben -> ValueError
    with pytest.raises(ValueError, match="Unbekannte Erstellt-am-Jahre"):
        repo.list_objects(erstellt_am_jahr_in=[2020, 9999])
    with pytest.raises(ValueError, match="Unbekannte Erstellt-am-Jahre"):
        repo.list_objects(erstellt_am_jahr_in=[1700])
    c.close()


def test_erstellt_am_jahrzehnt_in_filter(tmp_path):
    """erstellt_am_jahrzehnt_in akzeptiert diskrete Erfassungs-Dekaden.

    Spiegelt funddatum_jahrzehnt_in auf die Erfassungs-Achse: gruppiert das
    Jahr per Integer-Div durch 10 und vergleicht mit der angegebenen
    Dekaden-Startzahl (``2010`` selektiert 2010..2019).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "edi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2012-05-13 10:00:00"),   # 2010er
            ("OBJ_0002", "2019-08-01 11:30:00"),   # 2010er (rand)
            ("OBJ_0003", "2020-01-01 12:00:00"),   # 2020er (rand)
            ("OBJ_0004", "2024-11-30 14:15:00"),   # 2020er
            ("OBJ_0005", ""),
            ("OBJ_0006", "kein-datum"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Diskrete Dekaden-Auswahl
    rows = repo.list_objects(erstellt_am_jahrzehnt_in=[2010, 2020])
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Einzelne Dekade
    rows = repo.list_objects(erstellt_am_jahrzehnt_in=[2010])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    rows = repo.list_objects(erstellt_am_jahrzehnt_in=[2020])
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Tupel akzeptiert
    rows = repo.list_objects(erstellt_am_jahrzehnt_in=(2020,))
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(erstellt_am_jahrzehnt_in=[])
    assert len(rows) == 6
    # Dekade ohne Treffer
    rows = repo.list_objects(erstellt_am_jahrzehnt_in=[1980])
    assert rows == []
    # Kombiniert mit Jahres-Bereichsfilter (Schnittmenge): 2010er ∩ [>=2015]
    rows = repo.list_objects(erstellt_am_jahrzehnt_in=[2010],
                              erstellt_am_jahr_min=2015)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Ungueltige Dekaden (nicht durch 10 teilbar / ausserhalb 1800..2990)
    with pytest.raises(ValueError, match="Unbekannte Erstellt-am-Jahrzehnte"):
        repo.list_objects(erstellt_am_jahrzehnt_in=[2015])
    with pytest.raises(ValueError, match="Unbekannte Erstellt-am-Jahrzehnte"):
        repo.list_objects(erstellt_am_jahrzehnt_in=[1700])
    with pytest.raises(ValueError, match="Unbekannte Erstellt-am-Jahrzehnte"):
        repo.list_objects(erstellt_am_jahrzehnt_in=[3000])
    c.close()


def test_erstellt_am_monat_filter(tmp_path):
    """erstellt_am_monat filtert nach Erfassungs-Monat ueber alle Jahre.

    Spiegelt funddatum_monat auf die Erfassungs-Achse - typische Indoor-
    Erfassungs-Spitze ist Januar/Februar/Maerz (Boersen-Vorbereitung).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "em.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2020-01-15 10:00:00"),   # Januar
            ("OBJ_0002", "2021-02-20 11:30:00"),   # Februar (Tucson)
            ("OBJ_0003", "2022-07-10 12:00:00"),   # Juli
            ("OBJ_0004", "2024-12-01 14:15:00"),   # Dezember (Muenchen)
            ("OBJ_0005", "2024"),                  # ohne Monatsteil → faellt raus
            ("OBJ_0006", ""),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(erstellt_am_monat=1)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    rows = repo.list_objects(erstellt_am_monat=12)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    rows = repo.list_objects(erstellt_am_monat=7)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Monat ohne Treffer
    rows = repo.list_objects(erstellt_am_monat=8)
    assert rows == []
    # Validierung
    with pytest.raises(ValueError, match="erstellt_am_monat"):
        repo.list_objects(erstellt_am_monat=0)
    with pytest.raises(ValueError, match="erstellt_am_monat"):
        repo.list_objects(erstellt_am_monat=13)
    c.close()


def test_erstellt_am_monat_in_filter(tmp_path):
    """erstellt_am_monat_in waehlt mehrere Erfassungs-Monate aus.

    Spiegelt funddatum_monat_in: Indoor-Welle ('Januar ODER Februar ODER
    Dezember') vs. Sommer-Pause waehrend Feld-Saison.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "emi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2020-01-15 10:00:00"),
            ("OBJ_0002", "2021-02-20 11:30:00"),
            ("OBJ_0003", "2022-07-10 12:00:00"),
            ("OBJ_0004", "2024-12-01 14:15:00"),
            ("OBJ_0005", "2024-03-20 15:00:00"),
            ("OBJ_0006", "2024"),
            ("OBJ_0007", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Indoor-Welle: Januar ODER Februar ODER Dezember
    rows = repo.list_objects(erstellt_am_monat_in=[1, 2, 12])
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0004"]
    # Tupel akzeptiert
    rows = repo.list_objects(erstellt_am_monat_in=(7,))
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Leere Liste -> kein Filter
    rows = repo.list_objects(erstellt_am_monat_in=[])
    assert len(rows) == 7
    # Kombiniert mit Jahresfilter (Schnittmenge)
    rows = repo.list_objects(erstellt_am_monat_in=[1, 2],
                              erstellt_am_jahr_min=2021)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Validierung
    with pytest.raises(ValueError, match="Unbekannte Erstellt-am-Monate"):
        repo.list_objects(erstellt_am_monat_in=[7, 13])
    with pytest.raises(ValueError, match="Unbekannte Erstellt-am-Monate"):
        repo.list_objects(erstellt_am_monat_in=[0])
    c.close()
