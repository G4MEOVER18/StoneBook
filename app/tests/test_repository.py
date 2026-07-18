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


def test_sort_by_mohs_haerte_mitte(tmp_path):
    """Sortierung nach Mohs_Haerte_Mitte als Bereichs-Mittelpunkt-Achse.

    Ergaenzt Mohs_Haerte_min/Mohs_Haerte_max: waehrend die Einzel-Grenzen bei
    Single-Point-Pflege ("Quarz 7" nur als min gepflegt, "Diamant 10" nur als
    max) unterschiedliche Achsen bedienen und ein Mix-Bestand nicht konsistent
    sortiert (der min-only-Quarz und der max-only-Diamant tauchen in
    Mohs_Haerte_min-Sortierung als 7 und NULL auf, obwohl beide klar Punkt-
    Haerten sind), liefert Mohs_Haerte_Mitte den natuerlichen typischen Wert
    pro Stueck: bei zweiseitigem Bereich ((min+max)/2), bei Single-Point-Pflege
    den einzelnen Wert via COALESCE. Beide NULL -> Mittelpunkt NULL, faellt
    ans Listenende (NULL-an-Ende-Konvention, spiegelt Volumen_mm3).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mmi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            # Zweiseitiger Bereich: (min+max)/2 = 5.5 (Apatit-typisch)
            ("OBJ_0001", 5.0, 6.0),
            # Single-Point min only -> 7.0 (Quarz)
            ("OBJ_0002", 7.0, None),
            # Single-Point max only -> 10.0 (Diamant)
            ("OBJ_0003", None, 10.0),
            # Zweiseitiger Bereich: (1.0+2.0)/2 = 1.5 (Talk-Uebergang)
            ("OBJ_0004", 1.0, 2.0),
            # Beide NULL -> Mittelpunkt NULL -> ans Ende
            ("OBJ_0005", None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Mohs_Haerte_Mitte", sort_desc=True)
    # OBJ_0003 (10.0) > OBJ_0002 (7.0) > OBJ_0001 (5.5) > OBJ_0004 (1.5),
    # NULL-Traeger am Ende.
    assert [r["obj_id"] for r in rows[:4]] == [
        "OBJ_0003", "OBJ_0002", "OBJ_0001", "OBJ_0004"]
    assert [r["Mohs_Haerte_Mitte"] for r in rows[:4]] == [10.0, 7.0, 5.5, 1.5]
    assert rows[-1]["obj_id"] == "OBJ_0005"
    assert rows[-1]["Mohs_Haerte_Mitte"] is None
    # Aufsteigend: weichstes Stueck zuerst, NULL weiterhin ans Ende.
    rows = repo.list_objects(sort_by="Mohs_Haerte_Mitte")
    assert [r["obj_id"] for r in rows[:4]] == [
        "OBJ_0004", "OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert rows[-1]["obj_id"] == "OBJ_0005"
    c.close()


def test_sort_by_dichte_mitte(tmp_path):
    """Sortierung nach Dichte_Mitte als Bereichs-Mittelpunkt-Achse auf der
    Massendichte-Achse. Spiegelt test_sort_by_mohs_haerte_mitte auf die Dichte-
    Ebene: dieselbe COALESCE-Semantik, dieselbe NULL-an-Ende-Konvention.

    Punkt-Pflege bei physikalisch feststehenden Werten (Quarz 2.65 g/cm3,
    Galenit 7.5 g/cm3) wird per COALESCE zum beidseitigen Grenzwert und liefert
    den einzelnen Wert - damit sind die typischen Sammler-Punkt-Eintraege in
    der Dichte-Reihenfolge sichtbar, ohne dass der Sortier-Konsument die
    Pflege-Konvention (nur min bzw. nur max gesetzt) kennen muss.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "dmi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            # Zweiseitiger Bereich: (2.6+2.7)/2 = 2.65 (Quarz-Familie)
            ("OBJ_0001", 2.6, 2.7),
            # Single-Point min only -> 7.5 (Galenit)
            ("OBJ_0002", 7.5, None),
            # Single-Point max only -> 5.0 (Pyrit-Bereichs-Max)
            ("OBJ_0003", None, 5.0),
            # Zweiseitiger Bereich: (1.9+2.3)/2 = 2.1 (Opal-Uebergang)
            ("OBJ_0004", 1.9, 2.3),
            # Beide NULL -> Mittelpunkt NULL -> ans Ende
            ("OBJ_0005", None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Dichte_Mitte", sort_desc=True)
    # OBJ_0002 (7.5) > OBJ_0003 (5.0) > OBJ_0001 (2.65) > OBJ_0004 (2.1),
    # NULL-Traeger am Ende. Float-Vergleich mit Toleranz gegen die uebliche
    # IEEE-754-Rundung (2.6+2.7)/2 = 2.6500000000000004.
    assert [r["obj_id"] for r in rows[:4]] == [
        "OBJ_0002", "OBJ_0003", "OBJ_0001", "OBJ_0004"]
    assert [round(r["Dichte_Mitte"], 4) for r in rows[:4]] == [7.5, 5.0, 2.65, 2.1]
    assert rows[-1]["obj_id"] == "OBJ_0005"
    assert rows[-1]["Dichte_Mitte"] is None
    # Aufsteigend: leichtestes Stueck zuerst, NULL weiterhin ans Ende.
    rows = repo.list_objects(sort_by="Dichte_Mitte")
    assert [r["obj_id"] for r in rows[:4]] == [
        "OBJ_0004", "OBJ_0001", "OBJ_0003", "OBJ_0002"]
    assert rows[-1]["obj_id"] == "OBJ_0005"
    c.close()


def test_sort_by_wert_pro_gewicht_chf_g(tmp_path):
    """Sortierung nach Wert_pro_Gewicht_chf_g als spezifische Marktwert-Dichte
    (CHF pro Gramm). Sammler-/Verkaeufer-Frage 'welche Stuecke sind pro Gramm
    am wertvollsten?': kleine Diamant-/Rubin-/Smaragd-Portionen ganz oben,
    faustgrosse Quarze/Calcite unten. Spiegelt gesamtwert_chf auf die
    Massen-spezifische Achse: waehrend gesamtwert_chf die absolute Summe
    beziffert (grosse schwere Stuecke oben), zeigt Wert_pro_Gewicht_chf_g die
    Wert-Dichte pro Masseneinheit.

    NULL-Konvention: Gewicht_g IS NULL ODER = 0 -> Wert-Dichte NULL -> ans
    Listenende (spiegelt Volumen_mm3-Semantik: fehlt eine Bezugsgroesse, ist
    die Ableitung nicht definiert). SUM-COALESCE-Konvention der Zaehler-
    Wert-Felder bleibt aus gesamtwert_chf uebernommen: fehlende Einzel-Wert-
    Felder zaehlen als 0 CHF. Ergibt spezifische Werte in CHF/g mit typischen
    Sammler-Reihenfolgen: Diamant (~50-500 CHF/g Rohstein) > Rubin/Smaragd
    (~5-50 CHF/g) > Bergkristall in Sammler-Qualitaet (~0.5-5 CHF/g) >
    Baumarkt-Quarz-Handstueck (~0.05 CHF/g).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g, Wert_CHF_roh) VALUES (?, ?, ?)",
        [
            # 500 CHF / 100 g = 5.0 CHF/g (Sammler-Bergkristall)
            ("OBJ_0001", 100.0, 500.0),
            # 200 CHF / 2 g = 100.0 CHF/g (Rubin-Splitter)
            ("OBJ_0002", 2.0, 200.0),
            # 50 CHF / 500 g = 0.1 CHF/g (Handstueck)
            ("OBJ_0003", 500.0, 50.0),
            # Gewicht NULL -> Wert-Dichte NULL, ans Ende
            ("OBJ_0004", None, 300.0),
            # Gewicht 0 -> Wert-Dichte NULL, ans Ende (keine Division-durch-Null)
            ("OBJ_0005", 0.0, 100.0),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Wert_pro_Gewicht_chf_g", sort_desc=True)
    # OBJ_0002 (100.0) > OBJ_0001 (5.0) > OBJ_0003 (0.1), NULL-Traeger hinten
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0002", "OBJ_0001", "OBJ_0003"]
    assert [round(r["Wert_pro_Gewicht_chf_g"], 4) for r in rows[:3]] == [
        100.0, 5.0, 0.1]
    # Beide NULL-Traeger stehen am Ende, Tie-Break lexikographisch auf obj_id
    assert [r["obj_id"] for r in rows[-2:]] == ["OBJ_0004", "OBJ_0005"]
    assert rows[-1]["Wert_pro_Gewicht_chf_g"] is None
    # Aufsteigend: kleinste Dichte zuerst, NULL weiterhin ans Ende
    rows = repo.list_objects(sort_by="Wert_pro_Gewicht_chf_g")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0001", "OBJ_0002"]
    assert rows[-1]["Wert_pro_Gewicht_chf_g"] is None
    c.close()


def test_sort_by_wert_pro_gewicht_chf_g_summiert_alle_wertfelder(tmp_path):
    """Wert_pro_Gewicht_chf_g nutzt die volle WERT_FELDER-Summe im Zaehler,
    identisch zur gesamtwert_chf-Konvention. Ein Stueck mit gemischten
    Wert-Feldern (Rohwert + Polierwert + Schmuckwert + Industrie +
    Wissenschaftlich) laeuft ueber die gesamte 5-Felder-Summe, nicht nur
    ueber Wert_CHF_roh - kein Drift zwischen der absoluten und der
    spezifischen Marktwert-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpg2.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g, Wert_CHF_roh, "
        "Wert_CHF_poliert, Wert_CHF_Schmuck, Marktwert_Industrie, "
        "Wissenschaftlicher_Wert_CHF) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            # 10 g, alle 5 Wert-Felder zusammen 100 CHF -> 10 CHF/g
            ("OBJ_0001", 10.0, 20.0, 30.0, 20.0, 10.0, 20.0),
            # 10 g, nur Rohwert 50 -> 5 CHF/g
            ("OBJ_0002", 10.0, 50.0, None, None, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Wert_pro_Gewicht_chf_g", sort_desc=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    assert [round(r["Wert_pro_Gewicht_chf_g"], 4) for r in rows] == [10.0, 5.0]
    # gesamtwert_chf-Konsistenz: die Summe im Zaehler entspricht dem gesamtwert
    assert round(rows[0]["gesamtwert_chf"], 4) == 100.0
    assert round(rows[1]["gesamtwert_chf"], 4) == 50.0
    c.close()


def test_sort_by_wert_pro_volumen_chf_mm3(tmp_path):
    """Sortierung nach Wert_pro_Volumen_chf_mm3 als spezifische Marktwert-Dichte
    (CHF pro mm3 Bounding-Box). Sammler-Frage 'welche Stuecke rentieren sich
    pro Vitrinen-/Schubladen-Platz am meisten?': kleine Diamant-/Rubin-/Smaragd-
    Splitter ganz oben, faustgrosse Quarze/Handstuecke unten. Spiegelt
    Wert_pro_Gewicht_chf_g auf die Volumen-Achse: waehrend die Massen-Dichte
    "welches Stueck traegt am meisten pro Gramm Transport-Gepaeck?" beantwortet,
    zeigt die Volumen-Dichte "welches Stueck traegt am meisten pro Aufbewahrungs-
    mm3?" - kritisch bei knapper Vitrine/Schublade.

    NULL-Konvention: mindestens eine Dimension (Laenge/Breite/Hoehe) NULL ODER
    Bounding-Box-Produkt = 0 -> Wert-Dichte NULL -> ans Listenende (spiegelt
    Volumen_mm3-Semantik: ohne komplette Vermessung ist keine Volumen-Dichte
    definiert). SUM-COALESCE-Konvention der Zaehler-Wert-Felder bleibt aus
    gesamtwert_chf uebernommen: fehlende Einzel-Wert-Felder zaehlen als 0 CHF.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm, "
        "Wert_CHF_roh) VALUES (?, ?, ?, ?, ?)",
        [
            # 500 CHF / (10*10*10) = 0.5 CHF/mm3 (Sammler-Splitter)
            ("OBJ_0001", 10.0, 10.0, 10.0, 500.0),
            # 200 CHF / (2*2*2) = 25.0 CHF/mm3 (Rubin-Splitter, klein)
            ("OBJ_0002", 2.0, 2.0, 2.0, 200.0),
            # 50 CHF / (50*40*20) = 0.00125 CHF/mm3 (grosses Handstueck)
            ("OBJ_0003", 50.0, 40.0, 20.0, 50.0),
            # Laenge NULL -> Volumen-Dichte NULL, ans Ende
            ("OBJ_0004", None, 10.0, 10.0, 300.0),
            # Breite NULL -> Volumen-Dichte NULL, ans Ende
            ("OBJ_0005", 10.0, None, 10.0, 100.0),
            # Hoehe NULL -> Volumen-Dichte NULL, ans Ende
            ("OBJ_0006", 10.0, 10.0, None, 100.0),
            # Eine Achse 0 -> Bounding-Box 0 -> NULL (keine Division-durch-Null)
            ("OBJ_0007", 10.0, 10.0, 0.0, 100.0),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Wert_pro_Volumen_chf_mm3", sort_desc=True)
    # OBJ_0002 (25.0) > OBJ_0001 (0.5) > OBJ_0003 (0.00125), NULL-Traeger hinten
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0002", "OBJ_0001", "OBJ_0003"]
    assert [round(r["Wert_pro_Volumen_chf_mm3"], 6) for r in rows[:3]] == [
        25.0, 0.5, 0.00125]
    # Alle vier NULL-Traeger stehen am Ende, Tie-Break lexikographisch auf obj_id
    assert [r["obj_id"] for r in rows[-4:]] == [
        "OBJ_0004", "OBJ_0005", "OBJ_0006", "OBJ_0007"]
    assert rows[-1]["Wert_pro_Volumen_chf_mm3"] is None
    # Aufsteigend: kleinste Dichte zuerst, NULL weiterhin ans Ende
    rows = repo.list_objects(sort_by="Wert_pro_Volumen_chf_mm3")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0001", "OBJ_0002"]
    assert rows[-1]["Wert_pro_Volumen_chf_mm3"] is None
    c.close()


def test_sort_by_wert_pro_volumen_chf_mm3_summiert_alle_wertfelder(tmp_path):
    """Wert_pro_Volumen_chf_mm3 nutzt die volle WERT_FELDER-Summe im Zaehler,
    identisch zur gesamtwert_chf-Konvention und symmetrisch zur
    Wert_pro_Gewicht_chf_g-Achse. Ein Stueck mit gemischten Wert-Feldern
    (Rohwert + Polierwert + Schmuckwert + Industrie + Wissenschaftlich)
    laeuft ueber die gesamte 5-Felder-Summe, nicht nur ueber Wert_CHF_roh -
    kein Drift zwischen der absoluten und der spezifischen Marktwert-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpv2.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm, "
        "Wert_CHF_roh, Wert_CHF_poliert, Wert_CHF_Schmuck, Marktwert_Industrie, "
        "Wissenschaftlicher_Wert_CHF) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # 10x10x10 = 1000 mm3, alle 5 Wert-Felder zusammen 100 CHF -> 0.1 CHF/mm3
            ("OBJ_0001", 10.0, 10.0, 10.0, 20.0, 30.0, 20.0, 10.0, 20.0),
            # 10x10x10 = 1000 mm3, nur Rohwert 50 -> 0.05 CHF/mm3
            ("OBJ_0002", 10.0, 10.0, 10.0, 50.0, None, None, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Wert_pro_Volumen_chf_mm3", sort_desc=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    assert [round(r["Wert_pro_Volumen_chf_mm3"], 6) for r in rows] == [0.1, 0.05]
    # gesamtwert_chf-Konsistenz: die Summe im Zaehler entspricht dem gesamtwert
    assert round(rows[0]["gesamtwert_chf"], 4) == 100.0
    assert round(rows[1]["gesamtwert_chf"], 4) == 50.0
    c.close()


def test_wert_pro_volumen_min_max_filter(tmp_path):
    """wert_pro_volumen_min/max als Filter-Ebenen-Pendant zur Wert_pro_Volumen_chf_mm3-
    Sortier-Achse. Spezifische Marktwert-Dichte (CHF/mm3) als Bereichs-Grenze -
    Sammler-Frage 'welche Stuecke rentieren sich pro Vitrinen-mm3 ueberhaupt fuer
    die Aufbewahrung?'. Spiegelt wert_pro_gewicht_min/max auf die Volumen-Achse.
    NULL-Semantik: mindestens eine fehlende Dimension oder Null-Produkt laesst
    die CASE-Expression NULL werden - solche Objekte fallen implizit aus dem
    Filter (spiegelt die volumen_-/wert_pro_gewicht_-/mohs_-/dichte_-Konvention).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpvf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm, "
        "Wert_CHF_roh) VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", 10.0, 10.0, 10.0, 500.0),    # 0.5 CHF/mm3 (Sammler-Splitter)
            ("OBJ_0002", 2.0, 2.0, 2.0, 200.0),        # 25.0 CHF/mm3 (Rubin)
            ("OBJ_0003", 50.0, 40.0, 20.0, 50.0),      # 0.00125 CHF/mm3 (Handstueck)
            ("OBJ_0004", None, 10.0, 10.0, 300.0),     # NULL-Dim -> Filter uebergangen
            ("OBJ_0005", 10.0, None, 10.0, 300.0),     # NULL-Dim -> Filter uebergangen
            ("OBJ_0006", 10.0, 10.0, None, 300.0),     # NULL-Dim -> Filter uebergangen
            ("OBJ_0007", 10.0, 10.0, 0.0, 100.0),      # 0-Produkt -> Filter uebergangen
            ("OBJ_0008", 10.0, 10.0, 10.0, 0.0),       # 0.0 CHF/mm3 (wertloses Stueck)
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Aufbewahrungs-Untergrenze: >= 0.01 CHF/mm3 rentiert sich fuer Vitrine
    rows = repo.list_objects(wert_pro_volumen_min=0.01)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Karat-Kandidaten: >= 1 CHF/mm3 typisch fuer Rubin-/Smaragd-/Diamant-Splitter
    rows = repo.list_objects(wert_pro_volumen_min=1.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Handstueck-Kandidaten: <= 0.01 CHF/mm3
    rows = repo.list_objects(wert_pro_volumen_max=0.01)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0008"]
    # Kombiniert: mittleres Volumen-Dichte-Segment (Sammler-Qualitaet, aber nicht Karat)
    rows = repo.list_objects(wert_pro_volumen_min=0.01, wert_pro_volumen_max=1.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Grenzfall exakt 0.00125 CHF/mm3: OBJ_0003 gerade nicht mehr im min>=0.01
    rows = repo.list_objects(wert_pro_volumen_min=0.00125)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # NULL-/Null-Volumen-Traeger fallen aus beiden Filtern raus
    rows = repo.list_objects(wert_pro_volumen_min=0.0)
    ids = [r["obj_id"] for r in rows]
    assert "OBJ_0004" not in ids
    assert "OBJ_0005" not in ids
    assert "OBJ_0006" not in ids
    assert "OBJ_0007" not in ids
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


def test_sort_by_volumen_mm3(tmp_path):
    """Sortierung nach Volumen_mm3 (L*B*H) als kombinierte Groessen-Achse.

    Ergaenzt die einzelnen L/B/H-Sortierungen: bei ungleichen Achsen liefert
    keine der Einzel-Achsen die Vitrinen-Gesamtgroesse (ein flach-breites Stueck
    kann groesser sein als ein hohes-schlankes trotz kleinerer Laenge). Product-
    NULL-Semantik: fehlt eine der drei Achsen, ist Volumen NULL und faellt
    nach der NULL-an-Ende-Konvention ans Listenende (spiegelt Laenge_mm/
    Breite_mm/Hoehe_mm-Sortierung).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vol.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) "
        "VALUES (?, ?, ?, ?)",
        [
            # Volumen ergibt: 384000 / 150000 / 48000
            ("OBJ_0001", 120.0, 80.0, 40.0),   # gross flach -> 384000
            ("OBJ_0002",  60.0, 50.0, 50.0),   # mittel kompakt -> 150000
            ("OBJ_0003",  30.0, 20.0, 80.0),   # klein hoch -> 48000
            ("OBJ_0004",  None, None, None),   # NULL -> ans Ende
            ("OBJ_0005", 100.0, 100.0, None),  # Teil-NULL -> Produkt NULL -> ans Ende
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    rows = repo.list_objects(sort_by="Volumen_mm3", sort_desc=True)
    # OBJ_0001 (384k) > OBJ_0002 (150k) > OBJ_0003 (48k), NULL-Objekte hinten.
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    assert [r["Volumen_mm3"] for r in rows[:3]] == [384000.0, 150000.0, 48000.0]
    # Beide NULL-Traeger stehen am Ende, Tie-Break lexikographisch auf obj_id.
    assert [r["obj_id"] for r in rows[-2:]] == ["OBJ_0004", "OBJ_0005"]
    assert rows[-1]["Volumen_mm3"] is None
    # Aufsteigend: kleinstes Volumen zuerst, NULL weiterhin ans Ende.
    rows = repo.list_objects(sort_by="Volumen_mm3")
    assert [r["obj_id"] for r in rows[:3]] == ["OBJ_0003", "OBJ_0002", "OBJ_0001"]
    assert rows[-1]["Volumen_mm3"] is None
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


def test_analysen_min_max_filter(tmp_path):
    """analysen_min/max verfeinert has_ki_analyse auf konkrete Lauf-Zahlgrenzen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "amm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    # OBJ_0001: 0 Analysen (noch nicht analysiert)
    # OBJ_0002: 1 Analyse (Erst-Lauf)
    # OBJ_0003: 3 Analysen (Erst + Re-Analyse mit Tilt/UV)
    # OBJ_0004: 5 Analysen (mineralogisch unsicherer Fall mit vielen Re-Laufen)
    entries = []
    for count, obj_id in ((1, "OBJ_0002"), (3, "OBJ_0003"), (5, "OBJ_0004")):
        for k in range(count):
            entries.append((obj_id, "claude-sonnet-4-6", "{}"))
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json) VALUES (?, ?, ?)",
        entries,
    )
    c.commit()
    repo = ObjectRepo(c)
    # Nur Min: mindestens 2 Laeufe - trennt die einmalig/nicht analysierten weg
    rows = repo.list_objects(analysen_min=2)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Nur Max: hoechstens 3 Laeufe - Nachhol-Kandidaten
    rows = repo.list_objects(analysen_max=3)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Kombiniert: 2..4 Laeufe
    rows = repo.list_objects(analysen_min=2, analysen_max=4)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Grenzfall analysen_min=0: keine Wirkung, alle Objekte
    rows = repo.list_objects(analysen_min=0)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Grenzfall analysen_max=0: nur die Objekte ohne Analyse (== has_ki_analyse=False)
    rows = repo.list_objects(analysen_max=0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    hki_false = repo.list_objects(has_ki_analyse=False)
    assert [r["obj_id"] for r in rows] == [r["obj_id"] for r in hki_false]
    # Grenzfall analysen_min=1: Aequivalent zu has_ki_analyse=True
    rows_min1 = repo.list_objects(analysen_min=1)
    rows_hki_true = repo.list_objects(has_ki_analyse=True)
    assert [r["obj_id"] for r in rows_min1] == [r["obj_id"] for r in rows_hki_true]
    # Kombination mit has_ki_analyse=True bleibt Schnittmenge (redundant)
    rows = repo.list_objects(analysen_min=3, has_ki_analyse=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    c.close()


def test_analysen_min_max_negativ_wirft(tmp_path):
    """Negative Grenzwerte werfen ValueError (Analyse-Anzahl kann nicht negativ sein)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "amn.sqlite3")
    c.commit()
    repo = ObjectRepo(c)
    with pytest.raises(ValueError, match="analysen_min"):
        repo.list_objects(analysen_min=-1)
    with pytest.raises(ValueError, match="analysen_max"):
        repo.list_objects(analysen_max=-1)
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


def test_aliase_min_max_filter(tmp_path):
    """aliase_min/max verfeinert has_alias auf konkrete Merge-Tiefe-Grenzen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "aliamm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    # OBJ_0001: 0 Aliase (kein Merge, Original)
    # OBJ_0002: 1 Alias (eine alte ID reingefolgt)
    # OBJ_0003: 3 Aliase (dokumentierte Duplikat-Gruppe mit drei Alt-IDs)
    # OBJ_0004: 5 Aliase (Sammel-Merge mit vielen historischen IDs)
    entries = []
    counter = 100
    for count, obj_id in ((1, "OBJ_0002"), (3, "OBJ_0003"), (5, "OBJ_0004")):
        for _ in range(count):
            entries.append((f"OBJ_{counter:04d}", obj_id, "duplikat_gruppen.json"))
            counter += 1
    c.executemany(
        "INSERT INTO aliases (alias_id, canonical_id, merge_quelle) VALUES (?, ?, ?)",
        entries,
    )
    c.commit()
    repo = ObjectRepo(c)
    # Nur Min: mindestens 2 Aliase - tiefe Merge-Historie
    rows = repo.list_objects(aliase_min=2)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Nur Max: hoechstens 3 Aliase - flache Merge-Historie
    rows = repo.list_objects(aliase_max=3)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Kombiniert: 2..4 Aliase
    rows = repo.list_objects(aliase_min=2, aliase_max=4)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Grenzfall aliase_min=0: keine Wirkung, alle Objekte
    rows = repo.list_objects(aliase_min=0)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Grenzfall aliase_max=0: nur nicht-gemergte Originale (== has_alias=False)
    rows = repo.list_objects(aliase_max=0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    ha_false = repo.list_objects(has_alias=False)
    assert [r["obj_id"] for r in rows] == [r["obj_id"] for r in ha_false]
    # Grenzfall aliase_min=1: Aequivalent zu has_alias=True
    rows_min1 = repo.list_objects(aliase_min=1)
    rows_ha_true = repo.list_objects(has_alias=True)
    assert [r["obj_id"] for r in rows_min1] == [r["obj_id"] for r in rows_ha_true]
    # Erst-Merge-Kandidaten: genau ein Alias (aliase_min=1 UND aliase_max=1)
    rows = repo.list_objects(aliase_min=1, aliase_max=1)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Kombination mit has_alias=True bleibt Schnittmenge (redundant)
    rows = repo.list_objects(aliase_min=3, has_alias=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    c.close()


def test_aliase_min_max_negativ_wirft(tmp_path):
    """Negative Grenzwerte werfen ValueError (Alias-Anzahl kann nicht negativ sein)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "alian.sqlite3")
    c.commit()
    repo = ObjectRepo(c)
    with pytest.raises(ValueError, match="aliase_min"):
        repo.list_objects(aliase_min=-1)
    with pytest.raises(ValueError, match="aliase_max"):
        repo.list_objects(aliase_max=-1)
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


def test_bilder_min_max_filter(tmp_path):
    """bilder_min/bilder_max verfeinert has_bilder auf konkrete Foto-Zahlgrenzen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bmm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    # OBJ_0001: 0 Bilder (nicht fotografiert)
    # OBJ_0002: 1 Bild
    # OBJ_0003: 3 Bilder
    # OBJ_0004: 5 Bilder (Foto-Reifegrad Vitrinen-Reife)
    images = []
    for count, obj_id in ((1, "OBJ_0002"), (3, "OBJ_0003"), (5, "OBJ_0004")):
        for k in range(count):
            images.append((obj_id, "Kamera", f"{obj_id}_{k}.jpg"))
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        images,
    )
    c.commit()
    repo = ObjectRepo(c)
    # Nur Min: mindestens 2 Fotos - schneidet die 0/1-Foto-Restanten weg
    rows = repo.list_objects(bilder_min=2)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Nur Max: hoechstens 3 Fotos - Foto-Pflege-Restanten
    rows = repo.list_objects(bilder_max=3)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Kombiniert: 2..4 Fotos
    rows = repo.list_objects(bilder_min=2, bilder_max=4)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Grenzfall bilder_min=0: keine Wirkung, alle Objekte
    rows = repo.list_objects(bilder_min=0)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0004"]
    # Grenzfall bilder_max=0: nur die 0-Foto-Objekte (== has_bilder=False)
    rows = repo.list_objects(bilder_max=0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    hb_false = repo.list_objects(has_bilder=False)
    assert [r["obj_id"] for r in rows] == [r["obj_id"] for r in hb_false]
    # Grenzfall bilder_min=1: Aequivalent zu has_bilder=True
    rows_min1 = repo.list_objects(bilder_min=1)
    rows_hb_true = repo.list_objects(has_bilder=True)
    assert [r["obj_id"] for r in rows_min1] == [r["obj_id"] for r in rows_hb_true]
    # Kombination mit has_bilder=True bleibt Schnittmenge (redundant, kein Konflikt)
    rows = repo.list_objects(bilder_min=3, has_bilder=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    c.close()


def test_bilder_min_max_negativ_wirft(tmp_path):
    """Negative Grenzwerte werfen ValueError (Foto-Anzahl kann nicht negativ sein)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bmn.sqlite3")
    c.commit()
    repo = ObjectRepo(c)
    with pytest.raises(ValueError, match="bilder_min"):
        repo.list_objects(bilder_min=-1)
    with pytest.raises(ValueError, match="bilder_max"):
        repo.list_objects(bilder_max=-1)
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


def test_wert_chf_schmuck_min_max_filter(tmp_path):
    """wert_chf_schmuck_min/max als Filter-Ebenen-Pendant zur Wert_CHF_Schmuck-
    Sortier-Achse. Isoliert den reinen Schmuck-Verkaufs-Schaetzwert (Cabochon-/
    Facetten-/Perlen-/Anhaenger-Bewertung) von der Summen-Achse wert_min/wert_max
    (die Wissenschafts-Meilenstein-Belege und Industrie-Massenware mit-filtert).
    NULL-Semantik: nicht Schmuck-bewertete Stuecke fallen automatisch aus dem
    Filter (spiegelt die gewicht_-/laenge_-/mohs_-/dichte_-Konvention).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wcs.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_Schmuck, Wert_CHF_roh, "
        "Wissenschaftlicher_Wert_CHF) VALUES (?, ?, ?, ?)",
        [
            # Schmuck-Kandidat mittleres Segment: 300 CHF Cabochon
            ("OBJ_0001", 300.0, 50.0, None),
            # Premium-Schmuck: 900 CHF Facette
            ("OBJ_0002", 900.0, 100.0, None),
            # Wissenschaftlicher Meilenstein-Beleg ohne Schmuck-Relevanz -
            # unter wert_min>=500 (Summen-Achse) wuerde OBJ_0003 erscheinen,
            # unter wert_chf_schmuck_min>=500 NICHT (das ist der Punkt).
            ("OBJ_0003", None, None, 5000.0),
            # Roh-Stueck ohne Schmuck-Bewertung
            ("OBJ_0004", None, 200.0, None),
            # Kleines Schmuck-Segment: 50 CHF Kettenanhaenger
            ("OBJ_0005", 50.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Boersen-Verkaufs-Untergrenze: >= 500 CHF Schmuck-Bewertung
    rows = repo.list_objects(wert_chf_schmuck_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Mittleres Segment (Cabochon-Vorstufe): 100-500 CHF
    rows = repo.list_objects(wert_chf_schmuck_min=100.0,
                             wert_chf_schmuck_max=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Kleine Anhaenger-Kategorie: <= 100 CHF
    rows = repo.list_objects(wert_chf_schmuck_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Alle mit dokumentierter Schmuck-Bewertung: >= 0
    rows = repo.list_objects(wert_chf_schmuck_min=0.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # Kontrast zur Summen-Achse: wert_min=500 (Summen-Achse) selektiert
    # OBJ_0002 (900 Schmuck) UND OBJ_0003 (5000 Wissenschaft) - die
    # isolierte Schmuck-Achse blendet OBJ_0003 aus (das ist der Vorteil
    # der neuen Achse gegenueber der Summen-Achse).
    rows = repo.list_objects(wert_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    rows = repo.list_objects(wert_chf_schmuck_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_wissenschaftlicher_wert_min_max_filter(tmp_path):
    """wissenschaftlicher_wert_min/max als Filter-Ebenen-Pendant zur
    Wissenschaftlicher_Wert_CHF-Sortier-Achse. Spiegelt strukturell den
    wert_chf_schmuck_min/_max-Block auf die Wissenschafts-Achse: isoliert
    den reinen Forschungs-/Museums-Wert (Holotypen, Typmaterial-Belege,
    Meilenstein-Funde) von der Summen-Achse wert_min/wert_max (die
    Schmuck-Kandidaten und Industrie-Massenware mit-filtert). NULL-Semantik:
    nicht wissenschaftlich bewertete Stuecke fallen automatisch aus dem
    Filter (spiegelt die gewicht_-/laenge_-/mohs_-/dichte_-/wert_chf_schmuck_-
    Konvention).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wwc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wissenschaftlicher_Wert_CHF, "
        "Wert_CHF_Schmuck, Wert_CHF_roh) VALUES (?, ?, ?, ?)",
        [
            # Mittleres Forschungs-Segment: 300 CHF Referenzbeleg
            ("OBJ_0001", 300.0, None, 50.0),
            # Premium-Meilenstein: 5000 CHF Holotyp
            ("OBJ_0002", 5000.0, None, None),
            # Schmuck-Kandidat ohne wissenschaftliche Relevanz -
            # unter wert_min>=500 (Summen-Achse) wuerde OBJ_0003 erscheinen,
            # unter wissenschaftlicher_wert_min>=500 NICHT (der Punkt).
            ("OBJ_0003", None, 900.0, None),
            # Roh-Stueck ohne wissenschaftliche Bewertung
            ("OBJ_0004", None, None, 200.0),
            # Kleines Forschungs-Segment: 50 CHF Publikations-Beleg
            ("OBJ_0005", 50.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Museumsleihgabe-Untergrenze: >= 1000 CHF wissenschaftliche Bewertung
    rows = repo.list_objects(wissenschaftlicher_wert_min=1000.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Mittleres Segment (Referenzstuecke): 100-500 CHF
    rows = repo.list_objects(wissenschaftlicher_wert_min=100.0,
                             wissenschaftlicher_wert_max=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Kleine Publikations-Belege: <= 100 CHF
    rows = repo.list_objects(wissenschaftlicher_wert_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Alle mit dokumentierter Forschungs-Bewertung: >= 0
    rows = repo.list_objects(wissenschaftlicher_wert_min=0.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # Kontrast zur Summen-Achse: wert_min=500 (Summen-Achse) selektiert
    # OBJ_0002 (5000 Wissenschaft) UND OBJ_0003 (900 Schmuck) - die
    # isolierte Wissenschafts-Achse blendet OBJ_0003 aus (das ist der
    # Vorteil der neuen Achse gegenueber der Summen-Achse).
    rows = repo.list_objects(wert_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    rows = repo.list_objects(wissenschaftlicher_wert_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_marktwert_industrie_min_max_filter(tmp_path):
    """marktwert_industrie_min/max als Filter-Ebenen-Pendant zur
    Marktwert_Industrie-Sortier-Achse. Schliesst den Ring der drei isolierten
    Verwendungs-Wert-Filter (Schmuck / Wissenschaft / Industrie) neben der
    Summen-Achse wert_min/wert_max. Spiegelt strukturell den wert_chf_schmuck_-
    und wissenschaftlicher_wert_-Block auf die Industrie-Massenware-Achse.
    NULL-Semantik: nicht industriell bewertete Stuecke fallen automatisch aus
    dem Filter (spiegelt die gewicht_-/laenge_-/mohs_-/dichte_-Konvention).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wmi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Marktwert_Industrie, "
        "Wert_CHF_Schmuck, Wissenschaftlicher_Wert_CHF) VALUES (?, ?, ?, ?)",
        [
            # Mittleres Industrie-Segment: 300 CHF Baryt-Fund
            ("OBJ_0001", 300.0, None, None),
            # Premium-Industrie: 900 CHF Bentonit-Charge
            ("OBJ_0002", 900.0, None, None),
            # Schmuck-Kandidat ohne Industrie-Relevanz -
            # unter wert_min>=500 (Summen-Achse) wuerde OBJ_0003 erscheinen,
            # unter marktwert_industrie_min>=500 NICHT (der Punkt).
            ("OBJ_0003", None, 700.0, None),
            # Wissenschaftlicher Meilenstein-Beleg ohne Industrie-Bewertung
            ("OBJ_0004", None, None, 2000.0),
            # Kleines Industrie-Segment: 50 CHF Kies-Restposten
            ("OBJ_0005", 50.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Boersen-Verkaufs-Untergrenze: >= 500 CHF Industrie-Bewertung
    rows = repo.list_objects(marktwert_industrie_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Mittleres Segment (Restposten-Vorstufe): 100-500 CHF
    rows = repo.list_objects(marktwert_industrie_min=100.0,
                             marktwert_industrie_max=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Kleine Restposten-Kategorie: <= 100 CHF
    rows = repo.list_objects(marktwert_industrie_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Alle mit dokumentierter Industrie-Bewertung: >= 0
    rows = repo.list_objects(marktwert_industrie_min=0.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # Kontrast zur Summen-Achse: wert_min=500 (Summen-Achse) selektiert
    # OBJ_0002 (900 Industrie), OBJ_0003 (700 Schmuck) UND OBJ_0004 (2000
    # Wissenschaft) - die isolierte Industrie-Achse blendet OBJ_0003 und
    # OBJ_0004 aus (das ist der Vorteil der neuen Achse gegenueber der
    # Summen-Achse).
    rows = repo.list_objects(wert_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003", "OBJ_0004"]
    rows = repo.list_objects(marktwert_industrie_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_wert_usd_talisman_min_max_filter(tmp_path):
    """wert_usd_talisman_min/max als Filter-Ebenen-Pendant zur Wert_USD_Talisman-
    Sortier-Achse. Als USD-Feld bewusst NICHT Teil der CHF-Summen-Achse
    wert_min/wert_max - der Talisman-Wert wuerde sonst mit CHF-Werten ohne
    Wechselkurs-Umrechnung vermischt. Spiegelt strukturell die anderen
    Verwendungs-Wert-Filter (Schmuck/Wissenschaft/Industrie) auf die einzige
    USD-Achse. NULL-Semantik: nicht Talisman-bewertete Stuecke fallen
    automatisch aus dem Filter.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wut.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_USD_Talisman, "
        "Wert_CHF_Schmuck, Wissenschaftlicher_Wert_CHF) VALUES (?, ?, ?, ?)",
        [
            # Mittleres Talisman-Segment: 300 USD Chakra-Stein
            ("OBJ_0001", 300.0, None, None),
            # Premium-Talisman: 900 USD Rutil-Quarz-Anhaenger
            ("OBJ_0002", 900.0, None, None),
            # Wissenschaftlicher Meilenstein ohne Talisman-Relevanz -
            # unter dem Talisman-Filter faellt OBJ_0003 raus, obwohl er
            # in der CHF-Summe (wert_min>=500) via Wissenschaft>=5000 waere.
            ("OBJ_0003", None, None, 5000.0),
            # Schmuck-Kandidat ohne Talisman-Bewertung
            ("OBJ_0004", None, 800.0, None),
            # Kleines Talisman-Segment: 50 USD Roll-Stein
            ("OBJ_0005", 50.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # US-Boersen-Untergrenze: >= 500 USD Talisman-Bewertung
    rows = repo.list_objects(wert_usd_talisman_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Mittleres Segment (Etsy-Kandidaten): 100-500 USD
    rows = repo.list_objects(wert_usd_talisman_min=100.0,
                             wert_usd_talisman_max=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Kleine Roll-Stein-Kategorie: <= 100 USD
    rows = repo.list_objects(wert_usd_talisman_max=100.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Alle mit dokumentierter Talisman-Bewertung: >= 0
    rows = repo.list_objects(wert_usd_talisman_min=0.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # Kontrast zur CHF-Summen-Achse: die USD-Werte fliessen bewusst NICHT
    # in {wert_sql} ein, sodass OBJ_0002 (900 USD Talisman) in wert_min=500
    # NICHT erscheint (er hat keine CHF-Werte), waehrend OBJ_0003 (5000
    # CHF Wissenschaft) und OBJ_0004 (800 CHF Schmuck) via CHF-Summe
    # erscheinen. Der Kontrast belegt die strukturelle Trennung der zwei
    # Waehrungs-Domains (USD-Talisman vs. CHF-Summe).
    rows = repo.list_objects(wert_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    rows = repo.list_objects(wert_usd_talisman_min=500.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_wert_pro_gewicht_min_max_filter(tmp_path):
    """wert_pro_gewicht_min/max als Filter-Ebenen-Pendant zur Wert_pro_Gewicht_chf_g-
    Sortier-Achse. Spezifische Marktwert-Dichte (CHF/g) als Bereichs-Grenze -
    Sammler-/Verkaeufer-Frage 'welche Stuecke rentieren sich pro Gramm ueberhaupt
    fuer den Boersen-Transport?'. Spiegelt volumen_min/max und wert_min/max
    auf die computed-column-Achse. NULL-Semantik: fehlende oder Null-Masse
    (Gewicht_g IS NULL OR = 0) laesst die CASE-Expression NULL werden -
    solche Objekte fallen implizit aus dem Filter (spiegelt die volumen_-/
    mohs_-/dichte_-Konvention).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpgf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g, Wert_CHF_roh) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 100.0, 500.0),   # 5.0 CHF/g (Sammler-Bergkristall)
            ("OBJ_0002", 2.0, 200.0),     # 100.0 CHF/g (Rubin-Splitter)
            ("OBJ_0003", 500.0, 50.0),    # 0.1 CHF/g (Handstueck)
            ("OBJ_0004", None, 300.0),    # Gewicht NULL -> Filter uebergangen
            ("OBJ_0005", 0.0, 100.0),     # Gewicht 0 -> Filter uebergangen
            ("OBJ_0006", 10.0, 0.0),      # 0.0 CHF/g (wertloses Stueck)
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Boersen-Transport-Untergrenze: >= 1 CHF/g rentiert sich
    rows = repo.list_objects(wert_pro_gewicht_min=1.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Karat-Kandidaten: >= 10 CHF/g typisch fuer Rubin-/Smaragd-/Diamant-Splitter
    rows = repo.list_objects(wert_pro_gewicht_min=10.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Handstueck-Kandidaten: <= 1 CHF/g
    rows = repo.list_objects(wert_pro_gewicht_max=1.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0006"]
    # Kombiniert: mittleres Wert-Dichte-Segment (Sammler-Qualitaet, aber nicht Karat)
    rows = repo.list_objects(wert_pro_gewicht_min=1.0, wert_pro_gewicht_max=50.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Grenzfall exakt 0.1 CHF/g: OBJ_0003 gerade nicht mehr im min>=1
    rows = repo.list_objects(wert_pro_gewicht_min=0.1)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # NULL/Null-Gewicht-Traeger fallen aus beiden Filtern raus
    rows = repo.list_objects(wert_pro_gewicht_min=0.0)
    assert "OBJ_0004" not in [r["obj_id"] for r in rows]
    assert "OBJ_0005" not in [r["obj_id"] for r in rows]
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


def test_sort_by_wert_chf_schmuck(tmp_path):
    """Sortierung nach Wert_CHF_Schmuck isoliert die Schmuck-Verkaufsschaetzung.

    Waehrend sort_by='gesamtwert_chf' die Summe aller CHF-Wertfelder ordnet
    (roh + poliert + Schmuck + Marktwert_Industrie + Wissenschaftlich) und damit
    Vitrinen-Wissenschafts-Belege sowie Industrie-Massenware in die Top-Liste
    mischt, isoliert sort_by='Wert_CHF_Schmuck' den Schmuck-Wert und liefert
    die reine Schmuck-Top-Reihenfolge. NULL-Eintraege wandern via
    _order_by_clause ans Listenende (spiegelt die anderen Einzelfeld-Sortier-
    Achsen wie Gewicht_g/Mohs_Haerte_min).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ws.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_Schmuck, "
        "Wissenschaftlicher_Wert_CHF, Marktwert_Industrie) VALUES (?, ?, ?, ?)",
        [
            # OBJ_0001: mittlere Schmuck-Wertung, sonst nichts
            ("OBJ_0001", 300.0, None, None),
            # OBJ_0002: hoechster Schmuck-Wert - Top bei DESC
            ("OBJ_0002", 900.0, None, None),
            # OBJ_0003: niedriger Schmuck-Wert, aber hoher Wissenschafts-Wert
            # -> waere via gesamtwert_chf oben, aber via Schmuck-Achse unten.
            ("OBJ_0003", 50.0, 5000.0, None),
            # OBJ_0004: kein Schmuck-Wert (NULL) trotz hoher Industrie-Bewertung
            # -> faellt via Wert_CHF_Schmuck ans Listenende (NULL-an-Ende).
            ("OBJ_0004", None, None, 2000.0),
            # OBJ_0005: hoher Schmuck-Wert - Rang 2
            ("OBJ_0005", 500.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # DESC: hoechster Schmuck-Wert zuerst, NULL ans Ende
    rows = repo.list_objects(sort_by="Wert_CHF_Schmuck", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0002", "OBJ_0005", "OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # ASC: niedrigster Schmuck-Wert zuerst, NULL immer noch ans Ende
    rows = repo.list_objects(sort_by="Wert_CHF_Schmuck", sort_desc=False)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0001", "OBJ_0005", "OBJ_0002", "OBJ_0004"]
    # Kontrast zu gesamtwert_chf DESC: hier steht OBJ_0003 oben
    # (Wissenschafts-Wert 5000) und OBJ_0004 (Industrie 2000) auf Rang 2 -
    # die Schmuck-Reihenfolge unterscheidet sich davon fundamental.
    rows = repo.list_objects(sort_by="gesamtwert_chf", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0004", "OBJ_0002", "OBJ_0005", "OBJ_0001"]
    c.close()


def test_sort_by_wissenschaftlicher_wert_chf(tmp_path):
    """Sortierung nach Wissenschaftlicher_Wert_CHF isoliert den Forschungs-Wert.

    Spiegelt test_sort_by_wert_chf_schmuck auf die Wissenschafts-Achse:
    waehrend gesamtwert_chf die Summe aller CHF-Wertfelder ordnet
    (roh + poliert + Schmuck + Marktwert_Industrie + Wissenschaftlich) und
    damit Schmuck-Werte sowie Industrie-Werte in die Top-Liste mischt,
    isoliert sort_by='Wissenschaftlicher_Wert_CHF' den reinen Forschungs-
    /Museums-Wert. NULL-Eintraege wandern via _order_by_clause ans Listenende.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ww.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wissenschaftlicher_Wert_CHF, "
        "Wert_CHF_Schmuck, Marktwert_Industrie) VALUES (?, ?, ?, ?)",
        [
            # OBJ_0001: mittlerer Wissenschafts-Wert, sonst nichts
            ("OBJ_0001", 300.0, None, None),
            # OBJ_0002: hoechster Wissenschafts-Wert - Top bei DESC (Holotyp-Beleg)
            ("OBJ_0002", 900.0, None, None),
            # OBJ_0003: niedriger Wissenschafts-Wert, aber hoher Schmuck-Wert
            # -> waere via gesamtwert_chf oben, aber via Wissenschafts-Achse unten
            ("OBJ_0003", 50.0, 5000.0, None),
            # OBJ_0004: kein Wissenschafts-Wert (NULL) trotz hoher Industrie-Bewertung
            # -> faellt via Wissenschaftlicher_Wert_CHF ans Listenende (NULL-an-Ende)
            ("OBJ_0004", None, None, 2000.0),
            # OBJ_0005: hoher Wissenschafts-Wert - Rang 2
            ("OBJ_0005", 500.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # DESC: hoechster Wissenschafts-Wert zuerst, NULL ans Ende
    rows = repo.list_objects(sort_by="Wissenschaftlicher_Wert_CHF", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0002", "OBJ_0005", "OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # ASC: niedrigster Wissenschafts-Wert zuerst, NULL immer noch ans Ende
    rows = repo.list_objects(sort_by="Wissenschaftlicher_Wert_CHF", sort_desc=False)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0001", "OBJ_0005", "OBJ_0002", "OBJ_0004"]
    # Kontrast zu gesamtwert_chf DESC: hier steht OBJ_0003 oben (Schmuck 5000)
    # und OBJ_0004 (Industrie 2000) auf Rang 2 - die Wissenschafts-Reihenfolge
    # unterscheidet sich fundamental.
    rows = repo.list_objects(sort_by="gesamtwert_chf", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0004", "OBJ_0002", "OBJ_0005", "OBJ_0001"]
    c.close()


def test_sort_by_wert_chf_roh_und_poliert(tmp_path):
    """Sortierung nach Wert_CHF_roh und Wert_CHF_poliert isoliert die Prozess-
    Wert-Achsen (Grundmaterial vor Bearbeitung / Bearbeitetes Endprodukt).

    Ergaenzt die drei bereits isolierten Verwendungs-Wert-Achsen (Schmuck /
    Wissenschaft / Industrie) um die zwei Prozess-Wert-Achsen. Damit sind alle
    fuenf Einzelwert-Achsen aus dem Feldwoerterbuch (roh, poliert, Schmuck,
    Marktwert_Industrie, Wissenschaftlich) als eigenstaendige Sortier-Achsen
    neben der Summen-Achse gesamtwert_chf verfuegbar. NULL-Eintraege wandern
    via _order_by_clause ans Listenende (spiegelt die anderen Einzelfeld-
    Sortier-Achsen wie Gewicht_g/Mohs_Haerte_min).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "rp.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?, ?, ?)",
        [
            # OBJ_0001: mittlerer Roh-Wert, kein Poliert-Wert
            ("OBJ_0001", 300.0, None),
            # OBJ_0002: hoechster Roh-Wert - Top bei Roh-DESC, kein Poliert-Wert
            # (grober Rohkristall, noch nicht bearbeitet)
            ("OBJ_0002", 900.0, None),
            # OBJ_0003: niedriger Roh-Wert, aber hoher Poliert-Wert (der
            # Sammler hat das Stueck geschliffen und der Wert-Delta ist gross)
            ("OBJ_0003", 50.0, 5000.0),
            # OBJ_0004: kein Roh-Wert (NULL) trotz hohem Poliert-Wert - der
            # Sammler hat das Stueck bereits poliert erworben, kein Roh-
            # Zustand dokumentiert -> faellt via Roh-Achse ans Listenende
            ("OBJ_0004", None, 2000.0),
            # OBJ_0005: hoher Roh-Wert - Rang 2 bei Roh-DESC
            ("OBJ_0005", 500.0, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # DESC: hoechster Roh-Wert zuerst, NULL ans Ende
    rows = repo.list_objects(sort_by="Wert_CHF_roh", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0002", "OBJ_0005", "OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # ASC: niedrigster Roh-Wert zuerst, NULL immer noch ans Ende
    rows = repo.list_objects(sort_by="Wert_CHF_roh", sort_desc=False)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0001", "OBJ_0005", "OBJ_0002", "OBJ_0004"]
    # Poliert-Achse: OBJ_0003 (5000) oben, OBJ_0004 (2000) auf Rang 2,
    # dann drei NULL-Eintraege in obj_id-Reihenfolge ans Ende
    rows = repo.list_objects(sort_by="Wert_CHF_poliert", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0004", "OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # Kontrast zu gesamtwert_chf DESC: OBJ_0003 (50+5000=5050) oben,
    # OBJ_0004 (0+2000=2000) auf Rang 2 - die Wert-Summen-Reihenfolge
    # unterscheidet sich fundamental von der reinen Roh-Achse.
    rows = repo.list_objects(sort_by="gesamtwert_chf", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0004", "OBJ_0002", "OBJ_0005", "OBJ_0001"]
    c.close()


def test_sort_by_marktwert_industrie(tmp_path):
    """Sortierung nach Marktwert_Industrie isoliert den Industrie-Marktwert.

    Schliesst den Ring der drei isolierten Wert-Achsen (Wert_CHF_Schmuck,
    Wissenschaftlicher_Wert_CHF, Marktwert_Industrie). Waehrend gesamtwert_chf
    die Summe aller CHF-Wertfelder ordnet (roh + poliert + Schmuck +
    Marktwert_Industrie + Wissenschaftlich) und damit Schmuck-Werte sowie
    Wissenschafts-Werte in die Top-Liste mischt, isoliert sort_by=
    'Marktwert_Industrie' den reinen Industrie-Wert (Baryt-/Bentonit-/Talk-/
    Feldspat-Massenware fuer Baumaterial, Keramik, Fuellstoff, Chemikalien).
    NULL-Eintraege wandern via _order_by_clause ans Listenende (spiegelt die
    anderen Einzelfeld-Sortier-Achsen wie Gewicht_g/Mohs_Haerte_min).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Marktwert_Industrie, "
        "Wert_CHF_Schmuck, Wissenschaftlicher_Wert_CHF) VALUES (?, ?, ?, ?)",
        [
            # OBJ_0001: mittlerer Industrie-Wert, sonst nichts
            ("OBJ_0001", 300.0, None, None),
            # OBJ_0002: hoechster Industrie-Wert - Top bei DESC (Grossmengen-Baryt)
            ("OBJ_0002", 900.0, None, None),
            # OBJ_0003: niedriger Industrie-Wert, aber hoher Schmuck-Wert
            # -> waere via gesamtwert_chf oben, aber via Industrie-Achse unten
            ("OBJ_0003", 50.0, 5000.0, None),
            # OBJ_0004: kein Industrie-Wert (NULL) trotz hoher Wissenschafts-Bewertung
            # -> faellt via Marktwert_Industrie ans Listenende (NULL-an-Ende)
            ("OBJ_0004", None, None, 2000.0),
            # OBJ_0005: hoher Industrie-Wert - Rang 2
            ("OBJ_0005", 500.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # DESC: hoechster Industrie-Wert zuerst, NULL ans Ende
    rows = repo.list_objects(sort_by="Marktwert_Industrie", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0002", "OBJ_0005", "OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # ASC: niedrigster Industrie-Wert zuerst, NULL immer noch ans Ende
    rows = repo.list_objects(sort_by="Marktwert_Industrie", sort_desc=False)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0001", "OBJ_0005", "OBJ_0002", "OBJ_0004"]
    # Kontrast zu gesamtwert_chf DESC: hier steht OBJ_0003 oben (Schmuck 5000)
    # und OBJ_0004 (Wissenschaft 2000) auf Rang 2 - die Industrie-Reihenfolge
    # unterscheidet sich fundamental.
    rows = repo.list_objects(sort_by="gesamtwert_chf", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0004", "OBJ_0002", "OBJ_0005", "OBJ_0001"]
    c.close()


def test_sort_by_wert_usd_talisman(tmp_path):
    """Sortierung nach Wert_USD_Talisman isoliert die Talisman-USD-Bewertung.

    Schliesst den Ring der sechs Einzelwert-Achsen ab (Wert_CHF_roh,
    Wert_CHF_poliert, Wert_CHF_Schmuck, Marktwert_Industrie,
    Wissenschaftlicher_Wert_CHF, Wert_USD_Talisman). Als einziges USD-
    denominiertes Wertfeld ist Wert_USD_Talisman bewusst nicht Bestandteil
    der CHF-Summe gesamtwert_chf (US-Talisman-/Metaphysical-Markt mit
    eigener USD-Skala, Etsy-/eBay-Notierungen) und damit ueber die Summen-
    Sortierung nie sichtbar - die isolierte Sortier-Achse ist der einzige
    Zugriff auf die Talisman-Top-Liste. NULL-Eintraege wandern via
    _order_by_clause ans Listenende (spiegelt die anderen Einzelfeld-
    Sortier-Achsen wie Gewicht_g/Mohs_Haerte_min).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ut.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_USD_Talisman, "
        "Wert_CHF_Schmuck, Wissenschaftlicher_Wert_CHF) VALUES (?, ?, ?, ?)",
        [
            # OBJ_0001: mittlerer Talisman-Wert, sonst nichts
            ("OBJ_0001", 300.0, None, None),
            # OBJ_0002: hoechster Talisman-Wert - Top bei DESC (grosses
            # Amethyst-Cluster als Meditationsraum-Zentrum)
            ("OBJ_0002", 900.0, None, None),
            # OBJ_0003: niedriger Talisman-Wert, aber hoher Schmuck-Wert
            # -> waere via gesamtwert_chf oben (5000 CHF Schmuck), aber via
            # Talisman-Achse unten (der Facetten-Schmuck-Stein bedient nicht
            # den Metaphysical-Markt).
            ("OBJ_0003", 50.0, 5000.0, None),
            # OBJ_0004: kein Talisman-Wert (NULL) trotz hoher Wissenschafts-
            # Bewertung (Holotyp-Referenzstueck ohne Metaphysical-Markt-
            # Relevanz) -> faellt via Talisman-Achse ans Listenende
            ("OBJ_0004", None, None, 2000.0),
            # OBJ_0005: hoher Talisman-Wert - Rang 2 (kalibrierter
            # Bergkristall-Trommelstein als Meditations-Set)
            ("OBJ_0005", 500.0, None, None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # DESC: hoechster Talisman-Wert zuerst, NULL ans Ende
    rows = repo.list_objects(sort_by="Wert_USD_Talisman", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0002", "OBJ_0005", "OBJ_0001", "OBJ_0003", "OBJ_0004"]
    # ASC: niedrigster Talisman-Wert zuerst, NULL immer noch ans Ende
    rows = repo.list_objects(sort_by="Wert_USD_Talisman", sort_desc=False)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0001", "OBJ_0005", "OBJ_0002", "OBJ_0004"]
    # Kontrast zu gesamtwert_chf DESC: hier steht OBJ_0003 oben (Schmuck 5000)
    # und OBJ_0004 (Wissenschaft 2000) auf Rang 2 - Wert_USD_Talisman fliesst
    # bewusst NICHT in die CHF-Summe ein (USD-Denomination), sodass die
    # Talisman-Werte in der Summen-Sortierung fehlen und die Reihenfolge sich
    # fundamental unterscheidet.
    rows = repo.list_objects(sort_by="gesamtwert_chf", sort_desc=True)
    assert [r["obj_id"] for r in rows] == [
        "OBJ_0003", "OBJ_0004", "OBJ_0001", "OBJ_0002", "OBJ_0005"]
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


def test_volumen_min_max_filter(tmp_path):
    """Volumen-Filter als kombinierte Groessen-Achse (Produkt L*B*H).

    Ergaenzt die drei Einzel-Achsen laenge_/breite_/hoehe_min/max um die
    Vitrinen-Gesamtgroesse - "welche Stuecke sind sammelwuerdig (>=10 cm3)?"
    -> volumen_min=10000. Spiegelt die Volumen_mm3-Sortier-Achse auf die
    Filter-Ebene und die Produkt-NULL-Semantik (mind. eine Dimension NULL
    -> Produkt NULL -> faellt aus dem Filter raus, spiegelt Einzel-Achsen-
    Filter).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) "
        "VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", 120.0, 80.0, 40.0),   # 384000 mm3 - grosses Handstueck
            ("OBJ_0002",  60.0, 50.0, 50.0),   # 150000 mm3 - mittel
            ("OBJ_0003",  30.0, 20.0, 80.0),   #  48000 mm3 - klein
            ("OBJ_0004",  10.0, 10.0, 10.0),   #   1000 mm3 - Mineral-Korn
            ("OBJ_0005",  None, None, None),   # nicht vermessen
            ("OBJ_0006", 100.0, 100.0, None),  # teil-vermessen (Produkt NULL)
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Untergrenze: nur Stuecke ab 100k mm3 (100 cm3).
    rows = repo.list_objects(volumen_min=100_000.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Obergrenze: nur bis 50k mm3.
    rows = repo.list_objects(volumen_max=50_000.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Mittelbereich: 30k..200k mm3.
    rows = repo.list_objects(volumen_min=30_000.0, volumen_max=200_000.0)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # NULL/teil-NULL faellt in allen drei Faellen raus (spiegelt L/B/H-Filter).
    rows = repo.list_objects(volumen_min=0.0)  # inklusiv-Grenze
    assert "OBJ_0005" not in {r["obj_id"] for r in rows}
    assert "OBJ_0006" not in {r["obj_id"] for r in rows}
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


def test_pruefempfehlungen_contains_filter(tmp_path):
    """Substring-Filter ueber Pruefempfehlungen (Freitext-Empfehlungen fuer Bestaetigungstests).

    Sammler-/Labor-Frage: "welche Stuecke warten auf eine XRD-Analyse?" oder
    "welche brauchen noch ein Refraktometer-Nachmessen?" -> Bulk-Selektion fuer
    geplante Lab-Besuche. Spiegelt notizen_contains: LIKE mit ESCAPE,
    ASCII-case-insensitive, NULL faellt implizit heraus.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "pec.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Pruefempfehlungen) VALUES (?, ?)",
        [
            ("OBJ_0001", "XRD-Analyse zur Phasenbestimmung."),
            ("OBJ_0002", "Refraktometer-Nachmessung und Oelimmersion 1,540."),
            ("OBJ_0003", None),
            ("OBJ_0004", "SEM-EDS Bulk-Chemie."),
            ("OBJ_0005", "Sonderpruefung mit 50_100 nm-Aufloesung."),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring-Match auf Test-Namen
    rows = repo.list_objects(pruefempfehlungen_contains="XRD")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # ASCII-case-insensitive
    rows = repo.list_objects(pruefempfehlungen_contains="xrd")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # Substring-Match innerhalb laengerer Beschreibung
    rows = repo.list_objects(pruefempfehlungen_contains="Refraktometer")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # LIKE-Metazeichen '_' bleibt wortwoertlich
    rows = repo.list_objects(pruefempfehlungen_contains="50_100")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    rows = repo.list_objects(pruefempfehlungen_contains="50X100")
    assert rows == []
    # NULL faellt implizit heraus
    rows = repo.list_objects(pruefempfehlungen_contains="a")
    assert all(r["obj_id"] != "OBJ_0003" for r in rows)
    # Leerer Substring ist no-op -> alle 5 Objekte
    rows = repo.list_objects(pruefempfehlungen_contains="")
    assert len(rows) == 5
    # Kombinierbar mit has_pruefempfehlungen (Schnittmenge)
    rows = repo.list_objects(pruefempfehlungen_contains="Oelimmersion",
                             has_pruefempfehlungen=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    c.close()


def test_farbe_contains_filter(tmp_path):
    """Substring-Filter ueber Farbe_beobachtet: findet Farbfamilien in Freitext-Notation.

    Farbe_beobachtet ist Freitext-Feld ohne kontrolliertes Vokabular; Sammler
    kodieren semantisch identische Farbtoene in mehreren Wortstaemmen
    (``rot`` in ``rot-braun`` / ``rotstichig`` / ``blutrot`` / ``dunkelrot``),
    sodass der exakte Feld-Match nur eine der Varianten treffen wuerde. Der
    Substring-Filter mit LIKE gibt die natuerliche Suche ueber die
    Farbfamilie. Spiegelt die Pattern der bestehenden *_contains-Filter
    (Fundort/Mineral/Name/Notizen/Varietaet/Gesteinsart): ASCII-case-insensitive,
    LIKE-Metazeichen (``%``/``_``) werden via ESCAPE wortwoertlich behandelt,
    NULL-Eintraege fallen implizit aus dem Match.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "fc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Farbe_beobachtet) VALUES (?, ?)",
        [
            ("OBJ_0001", "rot-braun"),
            ("OBJ_0002", "Blutrot mit weissen Adern"),
            ("OBJ_0003", "milchig weiss"),
            ("OBJ_0004", "hellgrau, matt"),
            ("OBJ_0005", "10Y_5/2"),  # Munsell-Notation mit LIKE-Metazeichen
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring-Match auf Farbfamilie 'rot' trifft beide rot-Notationen
    rows = repo.list_objects(farbe_contains="rot")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # ASCII-case-insensitive: 'ROT' matcht wie 'rot'
    rows = repo.list_objects(farbe_contains="ROT")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Substring innerhalb eines Kompositums
    rows = repo.list_objects(farbe_contains="milchig")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # LIKE-Metazeichen '_' bleibt wortwoertlich, matcht nur den Munsell-Eintrag
    rows = repo.list_objects(farbe_contains="10Y_5")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    # Ohne ESCAPE wuerde '_' als beliebiges Zeichen interpretieren und
    # damit auch Werte wie '10YX5' matchen - der Test verankert das ESCAPE-
    # Verhalten explizit.
    rows = repo.list_objects(farbe_contains="10YX5")
    assert rows == []
    # NULL-Eintraege fallen implizit heraus
    rows = repo.list_objects(farbe_contains="")
    # Leerer Substring ist no-op (kein LIKE angehangen) -> alle 6 Objekte
    assert len(rows) == 6
    # Kombinierbar mit has_farbe (Schnittmenge = nur mit Farbnotation + Substring)
    rows = repo.list_objects(farbe_contains="grau", has_farbe=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    c.close()


def test_strichfarbe_contains_filter(tmp_path):
    """Substring-Filter ueber Strichfarbe: findet Pulver-/Strichfarben-Familien.

    Strichfarbe ist diagnostisch komplementaer zur Stueck-Farbe: Haematit
    zeigt metallisch-silbrige Stueck-Oberflaeche, aber blutroten Strich;
    Pyrit messing-golden, aber schwarzen Strich; Chalkopyrit gruen-golden,
    aber schwarz-gruenlichen Strich. Der Substring-Filter erlaubt die
    Suche nach Strichfarben-Familien ohne exakte Notation und spiegelt
    ``farbe_contains`` auf die Pulver-Farb-Achse (LIKE mit ESCAPE, ASCII-
    case-insensitive, Metazeichen wortwoertlich, NULL faellt implizit raus).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "sfc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Strichfarbe) VALUES (?, ?)",
        [
            ("OBJ_0001", "rot"),                    # Haematit
            ("OBJ_0002", "kirschrot bis braunrot"), # Haematit-Variante
            ("OBJ_0003", "schwarz"),                # Magnetit/Pyrit
            ("OBJ_0004", "gruenschwarz metallisch"),# Chalkopyrit
            ("OBJ_0005", "rot_1 Notation"),         # LIKE-Metazeichen-Test
            ("OBJ_0006", None),                     # NULL-Eintrag
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring 'rot' trifft alle drei Rot-Varianten
    rows = repo.list_objects(strichfarbe_contains="rot")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # ASCII-case-insensitive
    rows = repo.list_objects(strichfarbe_contains="ROT")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # Substring 'schwarz' trifft schwarze und gruenschwarze Notationen
    rows = repo.list_objects(strichfarbe_contains="schwarz")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # LIKE-Metazeichen '_' bleibt wortwoertlich (ESCAPE-Verhalten)
    rows = repo.list_objects(strichfarbe_contains="rot_1")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    rows = repo.list_objects(strichfarbe_contains="rotX1")
    assert rows == []
    # NULL faellt implizit heraus
    rows = repo.list_objects(strichfarbe_contains="a")
    assert all(r["obj_id"] != "OBJ_0006" for r in rows)
    # Leerer Substring ist no-op -> alle 6 Objekte
    rows = repo.list_objects(strichfarbe_contains="")
    assert len(rows) == 6
    # Kombinierbar mit has_strichfarbe (Schnittmenge, LIKE bereits impliziert)
    rows = repo.list_objects(strichfarbe_contains="rot", has_strichfarbe=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0005"]
    # Kombinierbar mit farbe_contains (unterschiedliche Achsen: Stueck vs. Pulver)
    c.execute("UPDATE objects SET Farbe_beobachtet = 'metallisch silbrig' "
              "WHERE obj_id = 'OBJ_0001'")
    c.commit()
    rows = repo.list_objects(
        strichfarbe_contains="rot", farbe_contains="metallisch")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_hcl_reaktion_contains_filter(tmp_path):
    """Substring-Filter ueber HCl_Reaktion (Salzsaeure-Reaktions-Freitext).

    Sammler-Frage: "welche Stuecke sprudeln stark mit HCl?" oder
    "welche warten auf einen Warm-HCl-Retest?" -> Bulk-Selektion nach
    Reaktions-Staerke bzw. Temperatur-Modifikator. Spiegelt
    farbe_contains/strichfarbe_contains: LIKE mit ESCAPE, ASCII-case-
    insensitive, LIKE-Metazeichen wortwoertlich, NULL faellt implizit
    heraus.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "hcl.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, HCl_Reaktion) VALUES (?, ?)",
        [
            ("OBJ_0001", "stark, kalt"),                # Calcit
            ("OBJ_0002", "stark warm sprudelnd"),       # Aragonit
            ("OBJ_0003", "schwach, nur mit warmer 30% HCl"),  # Dolomit
            ("OBJ_0004", "keine"),                      # Quarz/Silikat
            ("OBJ_0005", "sprudelt mit 10_HCl"),        # LIKE-Metazeichen-Test
            ("OBJ_0006", None),                         # NULL-Eintrag
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring 'stark' trifft beide starken Reaktions-Varianten
    rows = repo.list_objects(hcl_reaktion_contains="stark")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # ASCII-case-insensitive
    rows = repo.list_objects(hcl_reaktion_contains="STARK")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Temperatur-Modifikator 'warm' trifft beide Warm-Notationen
    rows = repo.list_objects(hcl_reaktion_contains="warm")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # 'keine' schliesst nicht-reagierende Silikate ein
    rows = repo.list_objects(hcl_reaktion_contains="keine")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    # LIKE-Metazeichen '_' bleibt wortwoertlich (ESCAPE-Verhalten)
    rows = repo.list_objects(hcl_reaktion_contains="10_HCl")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    rows = repo.list_objects(hcl_reaktion_contains="10XHCl")
    assert rows == []
    # NULL faellt implizit heraus
    rows = repo.list_objects(hcl_reaktion_contains="a")
    assert all(r["obj_id"] != "OBJ_0006" for r in rows)
    # Leerer Substring ist no-op -> alle 6 Objekte
    rows = repo.list_objects(hcl_reaktion_contains="")
    assert len(rows) == 6
    # Kombinierbar mit has_hcl_reaktion (Schnittmenge, LIKE bereits impliziert)
    rows = repo.list_objects(hcl_reaktion_contains="stark", has_hcl_reaktion=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Kombinierbar mit farbe_contains (diagnostisch andere Achse)
    c.execute("UPDATE objects SET Farbe_beobachtet = 'weiss' "
              "WHERE obj_id = 'OBJ_0001'")
    c.commit()
    rows = repo.list_objects(
        hcl_reaktion_contains="stark", farbe_contains="weiss")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    c.close()


def test_uv_365nm_contains_filter(tmp_path):
    """Substring-Filter ueber UV_365nm (Langwellen-UV-Fluoreszenz-Freitext).

    Sammler-Frage: "welche Stuecke leuchten orange unter Langwelle?" oder
    "welche zeigen Nachleuchten?" -> Bulk-Selektion nach Fluoreszenzfarbe
    bzw. Persistenz. Spiegelt hcl_reaktion_contains: LIKE mit ESCAPE,
    ASCII-case-insensitive, LIKE-Metazeichen wortwoertlich, NULL faellt
    implizit heraus.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "uv365.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, UV_365nm) VALUES (?, ?)",
        [
            ("OBJ_0001", "orange, mittel"),                     # Calcit
            ("OBJ_0002", "gelb-orange stark nachleuchtend"),    # Franklinit
            ("OBJ_0003", "grün nachleuchtend"),                 # Willemit
            ("OBJ_0004", "keine"),                              # Quarz
            ("OBJ_0005", "hellblau bei 365_nm"),                # LIKE-Metazeichen
            ("OBJ_0006", None),                                 # NULL-Eintrag
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring 'orange' trifft beide Orange-Notationen
    rows = repo.list_objects(uv_365nm_contains="orange")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # ASCII-case-insensitive
    rows = repo.list_objects(uv_365nm_contains="ORANGE")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # Persistenz-Modifikator 'nachleucht' trifft beide Nachleuchten-Notationen
    rows = repo.list_objects(uv_365nm_contains="nachleucht")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    # 'keine' schliesst nicht-fluoreszierende Stuecke ein
    rows = repo.list_objects(uv_365nm_contains="keine")
    assert [r["obj_id"] for r in rows] == ["OBJ_0004"]
    # LIKE-Metazeichen '_' bleibt wortwoertlich (ESCAPE-Verhalten)
    rows = repo.list_objects(uv_365nm_contains="365_nm")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    rows = repo.list_objects(uv_365nm_contains="365Xnm")
    assert rows == []
    # NULL faellt implizit heraus
    rows = repo.list_objects(uv_365nm_contains="a")
    assert all(r["obj_id"] != "OBJ_0006" for r in rows)
    # Leerer Substring ist no-op -> alle 6 Objekte
    rows = repo.list_objects(uv_365nm_contains="")
    assert len(rows) == 6
    # Kombinierbar mit has_uv_reaktion (Schnittmenge, LIKE bereits impliziert)
    rows = repo.list_objects(uv_365nm_contains="orange", has_uv_reaktion=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_uv_254nm_contains_filter(tmp_path):
    """Substring-Filter ueber UV_254nm (Kurzwellen-UV-Fluoreszenz-Freitext).

    Diagnostisch komplementaer zu uv_365nm_contains: Kurzwelle zeigt bei
    vielen Mineralien andere Farben als Langwelle (Scheelit hellblau nur
    unter Kurzwelle, Calcit rot nur unter Langwelle). Sammler-Frage:
    "welche Stuecke leuchten unter Kurzwelle anders als unter Langwelle?"
    -> Kombination von uv_254nm_contains + uv_365nm_contains mit
    unterschiedlichen Farbnotationen. Spiegelt uv_365nm_contains: LIKE
    mit ESCAPE, ASCII-case-insensitive, Metazeichen wortwoertlich, NULL
    implizit raus.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "uv254.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, UV_365nm, UV_254nm) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", None, "hellblau stark"),           # Scheelit
            ("OBJ_0002", "grün mittel", "grün stark"),      # Willemit
            ("OBJ_0003", "orange", None),                   # Calcit
            ("OBJ_0004", "keine", "keine"),                 # Quarz
            ("OBJ_0005", None, "blau bei 254_nm"),          # LIKE-Metazeichen
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring 'hellblau' trifft Scheelit
    rows = repo.list_objects(uv_254nm_contains="hellblau")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001"]
    # ASCII-case-insensitive
    rows = repo.list_objects(uv_254nm_contains="STARK")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    # LIKE-Metazeichen '_' bleibt wortwoertlich (ESCAPE-Verhalten)
    rows = repo.list_objects(uv_254nm_contains="254_nm")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    rows = repo.list_objects(uv_254nm_contains="254Xnm")
    assert rows == []
    # NULL faellt implizit heraus (OBJ_0003 hat UV_254nm=NULL)
    rows = repo.list_objects(uv_254nm_contains="a")
    assert all(r["obj_id"] != "OBJ_0003" for r in rows)
    # Leerer Substring ist no-op -> alle 5 Objekte
    rows = repo.list_objects(uv_254nm_contains="")
    assert len(rows) == 5
    # Kombinierbar mit uv_365nm_contains (unterschiedliche Wellenlaengen-Achsen)
    # Willemit leuchtet auf beiden Wellenlaengen gruen
    rows = repo.list_objects(uv_365nm_contains="grün", uv_254nm_contains="grün")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Kombinierbar mit has_uv_reaktion (Schnittmenge)
    rows = repo.list_objects(uv_254nm_contains="stark", has_uv_reaktion=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_reaktionshinweis_contains_filter(tmp_path):
    """Substring-Filter ueber Reaktionshinweis (Freitext-Begleit-Notiz).

    Sammler-Frage: "welche Stuecke haben eine Temperatur-Bedingung im
    Reaktions-Kommentar dokumentiert (warm/kalt)?" oder "welche haben
    raeumlich differenzierte Reaktionen (Kern vs Rand vs Ader)?" ->
    Bulk-Selektion nach Reaktions-Notiz-Familie. Spiegelt
    hcl_reaktion_contains/uv_365nm_contains/uv_254nm_contains: LIKE mit
    ESCAPE, ASCII-case-insensitive, LIKE-Metazeichen wortwoertlich, NULL
    faellt implizit heraus.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "rh.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Reaktionshinweis) VALUES (?, ?)",
        [
            ("OBJ_0001", "nur mit warmer 30% HCl schwach"),
            ("OBJ_0002", "Nachleuchten haelt 3 Sekunden"),
            ("OBJ_0003", "Fluoreszenz kommt vom Kern, Rand nicht"),
            ("OBJ_0004", "kalt keine Reaktion, warm sprudelnd"),
            ("OBJ_0005", "Magnet-Test bei 254_nm negativ"),  # LIKE-Metazeichen
            ("OBJ_0006", None),                              # NULL-Eintrag
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Substring 'warm' trifft alle Warm-HCl-Notationen
    rows = repo.list_objects(reaktionshinweis_contains="warm")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # ASCII-case-insensitive
    rows = repo.list_objects(reaktionshinweis_contains="WARM")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
    # Raeumliche Differenzierung 'kern' trifft nur OBJ_0003
    rows = repo.list_objects(reaktionshinweis_contains="kern")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003"]
    # Nachleuchten-Persistenz
    rows = repo.list_objects(reaktionshinweis_contains="nachleucht")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # LIKE-Metazeichen '_' bleibt wortwoertlich (ESCAPE-Verhalten)
    rows = repo.list_objects(reaktionshinweis_contains="254_nm")
    assert [r["obj_id"] for r in rows] == ["OBJ_0005"]
    rows = repo.list_objects(reaktionshinweis_contains="254Xnm")
    assert rows == []
    # NULL faellt implizit heraus (OBJ_0006 hat Reaktionshinweis=NULL)
    rows = repo.list_objects(reaktionshinweis_contains="a")
    assert all(r["obj_id"] != "OBJ_0006" for r in rows)
    # Leerer Substring ist no-op -> alle 6 Objekte
    rows = repo.list_objects(reaktionshinweis_contains="")
    assert len(rows) == 6
    # Kombinierbar mit has_reaktionshinweis (Schnittmenge, LIKE bereits impliziert)
    rows = repo.list_objects(reaktionshinweis_contains="warm",
                             has_reaktionshinweis=True)
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0004"]
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


def test_erstellt_am_iso_range_filter(tmp_path):
    """erstellt_am_min/_max filtert tagesgenau ueber ISO-Strings (lexikographisch).

    Spiegelt funddatum_min/_max auf die Erfassungs-Achse: ISO YYYY-MM-DD[ HH:MM:SS]
    ist lexikographisch vergleichbar, daher reicht ein direkter String-Vergleich
    ohne Datums-Parsing. Komplementaer zu den groberen Jahr/Jahrzehnt/Monat-Filtern
    auf der gleichen Achse, wenn ein tagesgenauer Stichtag noetig ist
    (KI-Welle-Start, Migrationsdatum, Boersen-Nachbearbeitungs-Beginn).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ei.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-03-15 10:00:00"),
            ("OBJ_0002", "2024-06-13 11:30:00"),
            ("OBJ_0003", "2024-09-30 12:00:00"),
            ("OBJ_0004", "2025-01-05 14:15:00"),
            ("OBJ_0005", ""),
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # April..August 2024
    rows = repo.list_objects(erstellt_am_min="2024-04-01", erstellt_am_max="2024-08-31")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Alles ab 2024-09
    rows = repo.list_objects(erstellt_am_min="2024-09-01")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Alles bis Ende 2024
    rows = repo.list_objects(erstellt_am_max="2024-12-31")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Sekundengenauer Stichtag: erstellt_am-Stempel direkt vergleichen
    rows = repo.list_objects(erstellt_am_min="2024-06-13 12:00:00")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Kombination mit erstellt_am_jahr_in: Schnittmenge
    rows = repo.list_objects(erstellt_am_min="2024-06-01", erstellt_am_jahr_in=[2024])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    c.close()


def test_geaendert_am_iso_range_filter(tmp_path):
    """geaendert_am_min/_max filtert tagesgenau ueber ISO-Strings (lexikographisch).

    Spiegelt erstellt_am_min/_max auf die Aenderungs-Achse und funddatum_min/
    _max auf die Fund-Achse - schliesst die Tagesgenau-Stichtag-Trias der
    drei Zeitstempel-Spalten ab. Beantwortet die typische Pflege-Frage
    'welche Stuecke wurden seit dem letzten Boersen-Besuch redaktionell
    beruehrt?' tagesgenau, waehrend die existierenden Jahr/Jahrzehnt/Monat-
    Filter auf der Aenderungs-Achse nur grobe Diskretisierungen boten.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gi.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-03-15 10:00:00"),
            ("OBJ_0002", "2024-06-13 11:30:00"),
            ("OBJ_0003", "2024-09-30 12:00:00"),
            ("OBJ_0004", "2025-01-05 14:15:00"),
            ("OBJ_0005", ""),
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # April..August 2024
    rows = repo.list_objects(geaendert_am_min="2024-04-01", geaendert_am_max="2024-08-31")
    assert [r["obj_id"] for r in rows] == ["OBJ_0002"]
    # Alles ab 2024-09
    rows = repo.list_objects(geaendert_am_min="2024-09-01")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Alles bis Ende 2024
    rows = repo.list_objects(geaendert_am_max="2024-12-31")
    assert [r["obj_id"] for r in rows] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Sekundengenauer Stichtag direkt auf dem voll qualifizierten Stempel
    rows = repo.list_objects(geaendert_am_min="2024-06-13 12:00:00")
    assert [r["obj_id"] for r in rows] == ["OBJ_0003", "OBJ_0004"]
    # Kombination mit geaendert_am_jahr_in (Schnittmenge)
    rows = repo.list_objects(geaendert_am_min="2024-06-01", geaendert_am_jahr_in=[2024])
    assert [r["obj_id"] for r in rows] == ["OBJ_0002", "OBJ_0003"]
    c.close()


def test_list_objects_in_bbox_filtert_nach_koordinaten(tmp_path):
    """list_objects_in_bbox parst Fundort-Koordinaten und filtert nach Bounding-Box.

    Verdrahtet die bisher ungenutzte parse_coordinates-Funktion aus
    stonebook.migration.validators in die Repository-Schicht. Die Bounding-Box
    deckt die typische Sammler-Frage 'welche Stuecke aus meiner naechsten
    Tour-Region?' ab, ohne dass Fundort als strukturierte Lat/Lon-Spalte
    gepflegt werden muss - Koordinaten werden direkt aus dem Freitext gezogen.

    Decken muss: ein Treffer im Box-Inneren, ein Treffer genau auf einer
    Box-Kante (inklusiv), ein Eintrag knapp ausserhalb (ausgeschlossen),
    Fundort ohne Koordinaten (reiner Ortsname, uebergangen), leerer/NULL
    Fundort (uebergangen), DMS- und Hemisphaeren-Notationen (beide vom
    parse_coordinates-Parser unterstuetzt, hier durchgereicht).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bbox.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),         # Zuerich, in Box
            ("OBJ_0002", "46.5197, 6.6323"),         # Lausanne, in Box
            ("OBJ_0003", "48.8566, 2.3522"),         # Paris, ausserhalb Lon
            ("OBJ_0004", "Berner Oberland"),         # Ortsname ohne Koords
            ("OBJ_0005", "46.0°N 7.0°E"),            # Hemisphaeren-Suffix, in Box
            ("OBJ_0006", "47°22'37\"N 8°32'30\"E"),  # DMS-Notation Zuerich, in Box
            ("OBJ_0007", ""),                        # leer
            ("OBJ_0008", None),                      # NULL
            ("OBJ_0009", "60.0, 30.0"),              # St. Petersburg, ausserhalb Lat
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Schweizer Box (45.8..47.9 N, 5.9..10.5 E) deckt das gesamte Land ab
    hits = repo.list_objects_in_bbox(lat_min=45.8, lat_max=47.9,
                                     lon_min=5.9, lon_max=10.5)
    ids = [r[0] for r in hits]
    assert ids == ["OBJ_0001", "OBJ_0002", "OBJ_0005", "OBJ_0006"]
    # Treffer enthalten die geparsten Lat/Lon-Werte (nicht den rohen Text)
    obj1 = next(r for r in hits if r[0] == "OBJ_0001")
    assert obj1[1] == pytest.approx(47.3769)
    assert obj1[2] == pytest.approx(8.5417)
    c.close()


def test_list_objects_in_bbox_grenzen_inklusiv(tmp_path):
    """Bounding-Box-Grenzen sind inklusiv (BETWEEN-Konvention der SQL-Filter)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bbox_edge.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.0, 8.0"),  # exakt auf Min-Lat und Min-Lon
            ("OBJ_0002", "48.0, 9.0"),  # exakt auf Max-Lat und Max-Lon
            ("OBJ_0003", "46.9999, 8.0"),  # knapp ausserhalb Min-Lat
            ("OBJ_0004", "48.0001, 9.0"),  # knapp ausserhalb Max-Lat
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    hits = repo.list_objects_in_bbox(lat_min=47.0, lat_max=48.0,
                                     lon_min=8.0, lon_max=9.0)
    assert [r[0] for r in hits] == ["OBJ_0001", "OBJ_0002"]
    c.close()


def test_list_objects_in_bbox_leere_db(tmp_path):
    """Leere DB -> leere Trefferliste; kein Crash."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bbox_empty.sqlite3")
    repo = ObjectRepo(c)
    assert repo.list_objects_in_bbox(-90, 90, -180, 180) == []
    c.close()


def test_list_objects_ohne_koordinaten_pflege_liste(tmp_path):
    """list_objects_ohne_koordinaten liefert die Arbeitsliste der nicht
    geocodeden Stuecke - Pflege-Komplement zur quote_mit_koordinaten_prozent-
    Coverage. Filtert Objekte mit nicht-leerem Fundort, deren Freitext kein
    per parse_coordinates erkennbares Lat/Lon-Paar enthaelt; Objekte ohne
    Fundort werden uebergangen (sie laufen ueber has_fundort=False auf der
    eigenen Pflege-Achse Fundort-Akquise vs. Geocoding-Ergaenzung).

    Decken muss: Fundort mit Koordinaten (geocoded -> uebergangen), Fundort
    nur als Ortsname (Pflege-Treffer), Fundort mit fehlgeformter Koordinaten-
    Notation (Pflege-Treffer), Fundort leer/NULL/Whitespace (uebergangen, da
    has_fundort negativ), DMS- und Hemisphaeren-Notation als alternative
    geocoded Auspraegungen (uebergangen). Reihenfolge aufsteigend nach
    obj_id, damit die Pflege-Liste deterministisch ist.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "pflege.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),         # geocoded, uebergangen
            ("OBJ_0002", "Berner Oberland"),         # Pflege-Treffer
            ("OBJ_0003", "47°22'37\"N 8°32'30\"E"),  # geocoded (DMS), uebergangen
            ("OBJ_0004", "alte Halde bei Davos"),    # Pflege-Treffer
            ("OBJ_0005", "46.0°N 7.0°E"),            # geocoded (Hemisphaere), uebergangen
            ("OBJ_0006", ""),                        # kein Fundort, uebergangen
            ("OBJ_0007", "   "),                     # Whitespace, uebergangen
            ("OBJ_0008", None),                      # NULL, uebergangen
            ("OBJ_0009", "kaputt 47.X"),             # nicht parsebar, Pflege-Treffer
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    pflege = repo.list_objects_ohne_koordinaten()
    # Pflege-Liste: nur die nicht-geocodeden Eintraege mit Fundort, aufsteigend
    assert [p[0] for p in pflege] == ["OBJ_0002", "OBJ_0004", "OBJ_0009"]
    # Roh-Fundort wird durchgereicht (kein Lookup-Round-Trip noetig)
    assert pflege[0] == ("OBJ_0002", "Berner Oberland")
    assert pflege[1] == ("OBJ_0004", "alte Halde bei Davos")
    assert pflege[2] == ("OBJ_0009", "kaputt 47.X")
    c.close()


def test_list_objects_ohne_koordinaten_alles_geocoded(tmp_path):
    """Vollstaendig geocoded -> leere Pflege-Liste. Spiegelt den 100 %
    Coverage-Fall der quote_mit_koordinaten_prozent: wenn die Quote die
    obere Grenze erreicht hat, gibt es nichts mehr zu pflegen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
            ("OBJ_0002", "46.0°N 7.0°E"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert repo.list_objects_ohne_koordinaten() == []
    c.close()


def test_list_objects_ohne_koordinaten_leere_db(tmp_path):
    """Leere DB -> leere Pflege-Liste; kein Crash."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    repo = ObjectRepo(c)
    assert repo.list_objects_ohne_koordinaten() == []
    c.close()


def test_list_objects_mit_ungueltigem_funddatum_pflege_liste(tmp_path):
    """list_objects_mit_ungueltigem_funddatum liefert die Arbeitsliste der
    Objekte mit nicht-striktem Funddatum - Pflege-Spiegel von
    list_objects_ohne_koordinaten auf der Funddatum-Achse. Filtert Objekte
    mit nicht-leerem Funddatum, deren Rohtext nicht die YYYY-MM-DD-Form aus
    dem Feldwoerterbuch trifft; Objekte ohne Funddatum werden uebergangen
    (sie laufen ueber has_funddatum=False auf der eigenen Pflege-Achse
    Datums-Akquise vs. Formatnorm).

    Decken muss: strikte YYYY-MM-DD-Form (uebergangen), DE-Punkt-Notation
    "13.06.2024" (Pflege-Treffer, weil die App diese Form nur als
    parse_iso_date-Input akzeptiert und nicht als DB-Zielwert), Jahr-nur
    "2024" (Pflege-Treffer, weil unvollstaendig), Freitext "unbekannt"
    (Pflege-Treffer), semantisch ungueltiges Datum "2024-13-01" (Monat 13
    -> Pflege-Treffer) und "2024-02-30" (Tag 30 im Feb -> Pflege-Treffer),
    ISO-Datetime "2024-06-13T10:00" (Zusatz-Zeit-Anteil -> Pflege-Treffer),
    leerer/NULL/Whitespace-Funddatum (uebergangen). Reihenfolge aufsteigend
    nach obj_id, damit die Pflege-Liste deterministisch ist.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "pflege.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-06-13"),          # strikt gueltig, uebergangen
            ("OBJ_0002", "13.06.2024"),          # DE-Punkt, Pflege-Treffer
            ("OBJ_0003", "2024"),                # Jahr-nur, Pflege-Treffer
            ("OBJ_0004", "unbekannt"),           # Freitext, Pflege-Treffer
            ("OBJ_0005", "2024-13-01"),          # Monat 13, Pflege-Treffer
            ("OBJ_0006", "2024-02-30"),          # Tag 30 Feb, Pflege-Treffer
            ("OBJ_0007", "2024-06-13T10:00"),    # ISO-Datetime, Pflege-Treffer
            ("OBJ_0008", ""),                    # leer, uebergangen
            ("OBJ_0009", "   "),                 # Whitespace, uebergangen
            ("OBJ_0010", None),                  # NULL, uebergangen
            ("OBJ_0011", "1999-12-31"),          # strikt gueltig, uebergangen
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    pflege = repo.list_objects_mit_ungueltigem_funddatum()
    # Pflege-Liste: alle nicht-strikt-ISO-Eintraege mit nicht-leerem Funddatum
    assert [p[0] for p in pflege] == [
        "OBJ_0002", "OBJ_0003", "OBJ_0004",
        "OBJ_0005", "OBJ_0006", "OBJ_0007",
    ]
    # Roh-Funddatum wird durchgereicht (kein Lookup-Round-Trip noetig)
    assert pflege[0] == ("OBJ_0002", "13.06.2024")
    assert pflege[3] == ("OBJ_0005", "2024-13-01")
    assert pflege[4] == ("OBJ_0006", "2024-02-30")
    c.close()


def test_list_objects_mit_ungueltigem_funddatum_alles_strikt(tmp_path):
    """Vollstaendig striktes Funddatum -> leere Pflege-Liste. Spiegelt den
    100 % strikten Fall der Coverage: wenn alle Datumsstempel in
    YYYY-MM-DD stehen, gibt es keine Pflege-Restmenge."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-06-13"),
            ("OBJ_0002", "1999-12-31"),
            ("OBJ_0003", "2020-01-01"),
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert repo.list_objects_mit_ungueltigem_funddatum() == []
    c.close()


def test_list_objects_mit_ungueltigem_funddatum_leere_db(tmp_path):
    """Leere DB -> leere Pflege-Liste; kein Crash."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    repo = ObjectRepo(c)
    assert repo.list_objects_mit_ungueltigem_funddatum() == []
    c.close()


def test_list_objects_in_radius_filtert_nach_distanz(tmp_path):
    """list_objects_in_radius liefert Stuecke im Umkreis um einen Mittelpunkt.

    Disk-Pendant zu list_objects_in_bbox: waehrend die Box ein rechteckiges
    Lat/Lon-Gebiet beschreibt (grobe Annaeherung an "in der Naehe"), ist der
    Umkreis die natuerliche Form der Sammler-Frage 'welche Stuecke liegen
    in X km um meinen Standort?'. Beide Filter teilen die Reuse-Logik
    (parse_coordinates auf Fundort, Eintraege ohne Koords uebergangen),
    unterscheiden sich nur in der Such-Geometrie. Decken muss: Treffer im
    Inneren, Treffer am Rand (Distanz exakt = Radius), knapp ausserhalb des
    Radius (ausgeschlossen), Fundort ohne Koordinaten (uebergangen), leerer/
    NULL Fundort (uebergangen), DMS-/Hemisphaeren-Notationen (durchgereicht
    an parse_coordinates), Sortierung nach Distanz aufsteigend.
    """
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "radius.sqlite3")
    # Mittelpunkt: Zuerich Hauptbahnhof (47.3779, 8.5403)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),         # Zuerich nahe, ~0.2 km
            ("OBJ_0002", "47.5596, 7.5886"),         # Basel, ~73 km
            ("OBJ_0003", "46.5197, 6.6323"),         # Lausanne, ~210 km
            ("OBJ_0004", "Berner Oberland"),         # Ortsname, uebergangen
            ("OBJ_0005", "47°22'37\"N 8°32'30\"E"),  # DMS Zuerich, ~0 km
            ("OBJ_0006", ""),                        # leer
            ("OBJ_0007", None),                      # NULL
            ("OBJ_0008", "48.8566, 2.3522"),         # Paris, ~490 km
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # 100 km Umkreis um Zuerich -> Zuerich + Basel
    hits = repo.list_objects_in_radius(47.3779, 8.5403, 100.0)
    ids = [r[0] for r in hits]
    assert ids == ["OBJ_0005", "OBJ_0001", "OBJ_0002"]
    # Distanzen aufsteigend
    distances = [r[3] for r in hits]
    assert distances == sorted(distances)
    # Lat/Lon werden durchgereicht
    obj1 = next(r for r in hits if r[0] == "OBJ_0001")
    assert obj1[1] == pytest.approx(47.3769)
    assert obj1[2] == pytest.approx(8.5417)
    # Distanz zu Zuerich nahe == ~0.2 km
    assert obj1[3] < 1.0
    # Distanz Basel ~73 km
    obj2 = next(r for r in hits if r[0] == "OBJ_0002")
    assert obj2[3] == pytest.approx(73.0, abs=2.0)
    # 500 km Umkreis schliesst auch Lausanne und Paris ein
    weite = repo.list_objects_in_radius(47.3779, 8.5403, 500.0)
    assert set(r[0] for r in weite) == {
        "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0005", "OBJ_0008",
    }
    c.close()


def test_list_objects_in_radius_grenze_inklusiv(tmp_path):
    """Disk-Grenze ist inklusiv (distance == radius zaehlt mit), spiegelt
    die BETWEEN-Konvention der SQL-Range-Filter und list_objects_in_bbox.

    Berechnet die exakte Haversine-Distanz zu einem Testpunkt, setzt
    den Radius auf genau diese Distanz und prueft, dass der Punkt
    enthalten ist; ein Punkt minimal weiter draussen faellt aus.
    """
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "radius_edge.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.5, 8.5"),  # nahe Zuerich, definierter Ankerpunkt
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # Distanz von Zuerich (47.0, 8.0) zu (47.5, 8.5) per Haversine berechnen
    earth_r = 6371.0
    lat1, lon1 = math.radians(47.0), math.radians(8.0)
    lat2, lon2 = math.radians(47.5), math.radians(8.5)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    exact = 2 * earth_r * math.asin(math.sqrt(a))
    # Genau auf der Grenze -> Treffer
    hits = repo.list_objects_in_radius(47.0, 8.0, exact)
    assert [r[0] for r in hits] == ["OBJ_0001"]
    # Minimal kleiner -> keine Treffer
    hits = repo.list_objects_in_radius(47.0, 8.0, exact - 0.001)
    assert hits == []
    c.close()


def test_list_objects_in_radius_negativ_und_leere_db(tmp_path):
    """Negativer Radius -> leer (semantisch leere Disk); leere DB -> leer."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "radius_misc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [("OBJ_0001", "47.0, 8.0")],
    )
    c.commit()
    repo = ObjectRepo(c)
    assert repo.list_objects_in_radius(47.0, 8.0, -1.0) == []
    assert repo.list_objects_in_radius(47.0, 8.0, 0.0) != []  # exakt zentrierter Punkt
    c.close()
    # Leere DB -> leere Trefferliste
    c2 = open_db(tmp_path / "leer.sqlite3")
    repo2 = ObjectRepo(c2)
    assert repo2.list_objects_in_radius(47.0, 8.0, 100.0) == []
    c2.close()


def test_list_objects_nearest_liefert_naechste_in_distanz_reihenfolge(tmp_path):
    """list_objects_nearest liefert die N nahesten Stuecke aufsteigend nach Distanz.

    K-Nearest-Neighbors-Pendant zu list_objects_in_radius: waehrend die
    Disk-Suche eine Distanz-Grenze setzt (alle Stuecke innerhalb X km),
    beantwortet die K-NN-Variante die spiegelbildliche Frage 'welche
    sind die N nahesten?'. Beide teilen die Reuse-Logik
    (parse_coordinates auf Fundort, Eintraege ohne Koords uebergangen,
    Haversine-Distanz mit Erdradius 6371.0 km), unterscheiden sich nur
    in der Trefferschranke. Decken muss: K-NN-Trefferzahl bei
    typischem limit, Sortierung nach Distanz aufsteigend, Stuecke
    ausserhalb der naechsten N (uebergangen), Fundort ohne
    Koordinaten/leer/NULL (uebergangen), DMS-Notation (durchgereicht).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nearest.sqlite3")
    # Mittelpunkt: Zuerich Hauptbahnhof (47.3779, 8.5403)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),         # Zuerich nahe, ~0.2 km
            ("OBJ_0002", "47.5596, 7.5886"),         # Basel, ~73 km
            ("OBJ_0003", "46.5197, 6.6323"),         # Lausanne, ~210 km
            ("OBJ_0004", "Berner Oberland"),         # Ortsname, uebergangen
            ("OBJ_0005", "47°22'37\"N 8°32'30\"E"),  # DMS Zuerich, ~0 km
            ("OBJ_0006", ""),                        # leer
            ("OBJ_0007", None),                      # NULL
            ("OBJ_0008", "48.8566, 2.3522"),         # Paris, ~490 km
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # 3 naheste Stuecke um Zuerich -> Zuerich (DMS) + Zuerich nahe + Basel
    hits = repo.list_objects_nearest(47.3779, 8.5403, 3)
    ids = [r[0] for r in hits]
    assert ids == ["OBJ_0005", "OBJ_0001", "OBJ_0002"]
    # Distanzen aufsteigend
    distances = [r[3] for r in hits]
    assert distances == sorted(distances)
    # Lat/Lon werden durchgereicht
    obj1 = next(r for r in hits if r[0] == "OBJ_0001")
    assert obj1[1] == pytest.approx(47.3769)
    assert obj1[2] == pytest.approx(8.5417)
    assert obj1[3] < 1.0
    # 5 naheste -> alle 5 geocoded-en Stuecke (4 + 1 DMS), Reihenfolge nach Distanz
    weite = repo.list_objects_nearest(47.3779, 8.5403, 5)
    assert [r[0] for r in weite] == [
        "OBJ_0005", "OBJ_0001", "OBJ_0002", "OBJ_0003", "OBJ_0008",
    ]
    c.close()


def test_list_objects_nearest_grenzwerte(tmp_path):
    """limit <= 0 -> leer; limit > Anzahl -> alle verfuegbaren; Bindung deterministisch.

    Spiegelt die Grenzwert-Konvention von list_objects_in_radius
    (negativer Radius -> leer): semantisch leere K-NN-Anfrage liefert
    nichts, ueberschiessendes limit liefert keine Polsterung. Bei
    Distanz-Bindung sortiert die obj_id-Sekundaerschluessel-Konvention
    deterministisch (zwei Stuecke aus exakt derselben Lokalitaet).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nearest_edge.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0002", "47.5, 8.5"),  # gleiche Lokalitaet wie OBJ_0001
            ("OBJ_0001", "47.5, 8.5"),  # gleiche Lokalitaet wie OBJ_0002
            ("OBJ_0003", "48.0, 9.0"),  # weiter weg
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # limit == 0 -> leer
    assert repo.list_objects_nearest(47.0, 8.0, 0) == []
    # limit < 0 -> leer
    assert repo.list_objects_nearest(47.0, 8.0, -5) == []
    # limit > Anzahl geocoded -> alle 3, keine Polsterung
    alle = repo.list_objects_nearest(47.0, 8.0, 99)
    assert len(alle) == 3
    # Distanz-Bindung: OBJ_0001 vor OBJ_0002 (gleiche Distanz, sekundaer obj_id)
    assert [r[0] for r in alle[:2]] == ["OBJ_0001", "OBJ_0002"]
    assert alle[0][3] == pytest.approx(alle[1][3])
    c.close()


def test_list_objects_nearest_leere_db(tmp_path):
    """Leere DB -> leere Trefferliste, unabhaengig vom limit."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nearest_leer.sqlite3")
    repo = ObjectRepo(c)
    assert repo.list_objects_nearest(47.0, 8.0, 5) == []
    assert repo.list_objects_nearest(47.0, 8.0, 1) == []
    c.close()
    # Auch DB mit ausschliesslich nicht-geocoded-en Eintraegen -> leere Liste
    c2 = open_db(tmp_path / "nearest_keine_koords.sqlite3")
    c2.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", ""),
            ("OBJ_0003", None),
        ],
    )
    c2.commit()
    repo2 = ObjectRepo(c2)
    assert repo2.list_objects_nearest(47.0, 8.0, 5) == []
    c2.close()


def test_list_objects_farthest_liefert_weiteste_in_distanz_reihenfolge(tmp_path):
    """list_objects_farthest liefert die N weitesten Stuecke absteigend nach Distanz.

    K-Farthest-Neighbors-Pendant zu list_objects_nearest: waehrend die
    K-NN-Variante die Naehe-Achse beantwortet ('welche sind die N
    nahesten?'), beantwortet die K-FN-Variante die Ferne-Achse ('welche
    sind die N weitesten?') - typisch das Souvenir-Ausreisser-Stueck.
    Beide teilen die Reuse-Logik (parse_coordinates auf Fundort,
    Eintraege ohne Koords uebergangen, Haversine-Distanz mit Erdradius
    6371.0 km), unterscheiden sich nur in der Sortier-Richtung. Decken
    muss: K-FN-Trefferzahl bei typischem limit, Sortierung nach Distanz
    absteigend, Stuecke innerhalb der weitesten N (uebergangen),
    Fundort ohne Koordinaten/leer/NULL (uebergangen), DMS-Notation
    (durchgereicht).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "farthest.sqlite3")
    # Mittelpunkt: Zuerich Hauptbahnhof (47.3779, 8.5403)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),         # Zuerich nahe, ~0.2 km
            ("OBJ_0002", "47.5596, 7.5886"),         # Basel, ~73 km
            ("OBJ_0003", "46.5197, 6.6323"),         # Lausanne, ~210 km
            ("OBJ_0004", "Berner Oberland"),         # Ortsname, uebergangen
            ("OBJ_0005", "47°22'37\"N 8°32'30\"E"),  # DMS Zuerich, ~0 km
            ("OBJ_0006", ""),                        # leer
            ("OBJ_0007", None),                      # NULL
            ("OBJ_0008", "48.8566, 2.3522"),         # Paris, ~490 km
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # 3 weiteste Stuecke von Zuerich -> Paris + Lausanne + Basel
    hits = repo.list_objects_farthest(47.3779, 8.5403, 3)
    ids = [r[0] for r in hits]
    assert ids == ["OBJ_0008", "OBJ_0003", "OBJ_0002"]
    # Distanzen absteigend
    distances = [r[3] for r in hits]
    assert distances == sorted(distances, reverse=True)
    # Lat/Lon werden durchgereicht
    paris = next(r for r in hits if r[0] == "OBJ_0008")
    assert paris[1] == pytest.approx(48.8566)
    assert paris[2] == pytest.approx(2.3522)
    assert paris[3] > 400.0
    # 5 weiteste -> alle 5 geocoded-en Stuecke, Reihenfolge nach Distanz absteigend
    weite = repo.list_objects_farthest(47.3779, 8.5403, 5)
    assert [r[0] for r in weite] == [
        "OBJ_0008", "OBJ_0003", "OBJ_0002", "OBJ_0001", "OBJ_0005",
    ]
    c.close()


def test_list_objects_farthest_grenzwerte(tmp_path):
    """limit <= 0 -> leer; limit > Anzahl -> alle verfuegbaren; Bindung deterministisch.

    Spiegelt die Grenzwert-Konvention von list_objects_nearest
    (semantisch leere K-Extrema-Anfrage liefert nichts, ueberschiessendes
    limit liefert keine Polsterung). Bei Distanz-Bindung sortiert die
    obj_id-Sekundaerschluessel-Konvention deterministisch aufsteigend
    (spiegelt K-NN: zwei Stuecke aus exakt derselben fernen Lokalitaet
    haben identische Distanz).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "farthest_edge.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0002", "48.0, 9.0"),  # gleiche Ferne wie OBJ_0001
            ("OBJ_0001", "48.0, 9.0"),  # gleiche Ferne wie OBJ_0002
            ("OBJ_0003", "47.5, 8.5"),  # naeher
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    # limit == 0 -> leer
    assert repo.list_objects_farthest(47.0, 8.0, 0) == []
    # limit < 0 -> leer
    assert repo.list_objects_farthest(47.0, 8.0, -5) == []
    # limit > Anzahl geocoded -> alle 3, keine Polsterung
    alle = repo.list_objects_farthest(47.0, 8.0, 99)
    assert len(alle) == 3
    # Weitester zuerst, dann die beiden gleich-weit (aufsteigend obj_id), dann der nahe
    assert [r[0] for r in alle] == ["OBJ_0001", "OBJ_0002", "OBJ_0003"]
    # Distanz-Bindung: OBJ_0001 == OBJ_0002 an Distanz
    assert alle[0][3] == pytest.approx(alle[1][3])
    # OBJ_0003 ist naeher -> kleinere Distanz an letzter Stelle
    assert alle[2][3] < alle[0][3]
    c.close()


def test_list_objects_farthest_leere_db(tmp_path):
    """Leere DB -> leere Trefferliste, unabhaengig vom limit. Spiegelt K-NN."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "farthest_leer.sqlite3")
    repo = ObjectRepo(c)
    assert repo.list_objects_farthest(47.0, 8.0, 5) == []
    assert repo.list_objects_farthest(47.0, 8.0, 1) == []
    c.close()
    # Auch DB mit ausschliesslich nicht-geocoded-en Eintraegen -> leere Liste
    c2 = open_db(tmp_path / "farthest_keine_koords.sqlite3")
    c2.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", ""),
            ("OBJ_0003", None),
        ],
    )
    c2.commit()
    repo2 = ObjectRepo(c2)
    assert repo2.list_objects_farthest(47.0, 8.0, 5) == []
    c2.close()


def test_list_objects_farthest_und_nearest_sind_gegenpole(tmp_path):
    """Die N weitesten aus alle Ergebnissen == die N ersten von farthest,
    die N nahesten == die N ersten von nearest - beide sind Sortierungs-
    Gegenpole ueber derselben Trefferliste.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gegenpole.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),  # Zuerich nahe
            ("OBJ_0002", "47.5596, 7.5886"),  # Basel
            ("OBJ_0003", "46.5197, 6.6323"),  # Lausanne
            ("OBJ_0004", "48.8566, 2.3522"),  # Paris
        ],
    )
    c.commit()
    repo = ObjectRepo(c)
    nearest_all = repo.list_objects_nearest(47.3779, 8.5403, 99)
    farthest_all = repo.list_objects_farthest(47.3779, 8.5403, 99)
    # Beide enthalten dieselbe Menge Objekte, nur in umgekehrter Reihenfolge
    assert [r[0] for r in nearest_all] == list(reversed([r[0] for r in farthest_all]))
    # Distanzen sind identisch (nur Sortier-Richtung unterscheidet sich)
    assert sorted(r[3] for r in nearest_all) == sorted(r[3] for r in farthest_all)
