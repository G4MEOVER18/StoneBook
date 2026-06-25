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
    assert "Top-Foto-Objekte" not in out


def test_text_ausgabe_zeigt_top_bilder_objekte(tmp_path, capsys):
    """Top-Foto-Objekte erscheinen mit Objekt + Bildanzahl absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tb.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
        [
            ("OBJ_0001", "EinFoto"),
            ("OBJ_0002", "DreiFotos"),
            ("OBJ_0003", "OhneFoto"),
        ],
    )
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        [
            # rel_path muss pro DB einzigartig sein (UNIQUE constraint)
            ("OBJ_0001", "uebersicht", "OBJ_0001/u.jpg"),
            ("OBJ_0002", "uebersicht", "OBJ_0002/u.jpg"),
            ("OBJ_0002", "kamera",     "OBJ_0002/k.jpg"),
            ("OBJ_0002", "mikroskop",  "OBJ_0002/m.jpg"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Foto-Objekte (Bilder):" in out
    block = out.split("Top-Foto-Objekte (Bilder):", 1)[1]
    # DreiFotos kommt vor EinFoto; OhneFoto erscheint nicht (HAVING n > 0)
    assert block.index("DreiFotos") < block.index("EinFoto")
    assert "OhneFoto" not in block


def test_text_ausgabe_ohne_bilder_keine_top_foto_objekte_zeile(tmp_path, capsys):
    """Ohne irgendwelche Bilder erscheint der Top-Foto-Objekte-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tb0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
        [("OBJ_0001", "A"), ("OBJ_0002", "B")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Foto-Objekte" not in out


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


def test_text_ausgabe_zeigt_gewicht_und_ki_quoten(tmp_path, capsys):
    """Coverage-Block fuehrt Gewicht- und KI-Analyse-Quoten zusaetzlich zu Bildern/Funddatum/Wert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gki.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?,?)",
        [("OBJ_0001", 12.5), ("OBJ_0002", None),
         ("OBJ_0003", 0.0), ("OBJ_0004", 7.0)],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json) VALUES (?,?,?)",
        [("OBJ_0001", "claude-sonnet-4-6", "{}")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Gewicht:" in out
    assert "KI-Analyse:" in out


def test_text_ausgabe_zeigt_dimensionen_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Dimensionen-Quote direkt unter Gewicht auf.
    Geometrische Mess-Achse symmetrisch zur Masse-Achse - die Differenz beider
    Quoten beziffert die Vermessungs-Luecke (gewogen aber nicht vermessen).
    Spiegelt has_dimensionen-Filter-Konvention: eine Achse genuegt fuer Coverage."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "dim.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) "
        "VALUES (?,?,?,?)",
        [("OBJ_0001", 50.0, 30.0, 20.0),
         ("OBJ_0002", 80.0, None, None),  # nur Laenge → zaehlt
         ("OBJ_0003", None, None, None),
         ("OBJ_0004", None, None, None)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Dimensionen:" in out
    # 2 von 4 Objekten haben dokumentierte Dimensionen → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_mohs_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Mohs-Haerte-Quote direkt unter Dimensionen auf.
    Physikalische Haerte-Achse symmetrisch zur Masse- und Geometrie-Achse:
    Masse -> Geometrie -> Haerte ist die Reihenfolge der quantitativen
    physikalischen Mess-Achsen. Spiegelt has_mohs-Filter-Konvention: eine
    Grenze (min ODER max) genuegt fuer Coverage."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "mohs.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?,?,?)",
        [("OBJ_0001", 7.0, 7.0),
         ("OBJ_0002", 5.0, None),    # nur min → zaehlt
         ("OBJ_0003", None, None),
         ("OBJ_0004", None, None)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Mohs-Haerte:" in out
    # 2 von 4 Objekten haben dokumentierte Mohs-Haerte → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_dichte_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Dichte-Quote direkt unter Mohs-Haerte auf.
    Physikalische Dichte-Achse symmetrisch zur Haerte-Achse: Mohs (Kratztest)
    und Dichte (Wasserverdraengung/Pyknometer) sind die zwei zentralen
    quantitativen Pruef-Methoden zur Mineral-Bestimmung; gemeinsam trennen sie
    Mineralien wie Pyrit (~5.0) vs. Markasit (~4.9), die ueber Mohs allein
    nicht unterscheidbar sind. Spiegelt has_dichte-/has_mohs-Filter-Konvention:
    eine Grenze (min ODER max) genuegt fuer Coverage."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "dichte.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?,?,?)",
        [("OBJ_0001", 2.65, 2.66),   # Quarz-Punkt
         ("OBJ_0002", 2.60, None),   # nur min → zaehlt
         ("OBJ_0003", None, None),
         ("OBJ_0004", None, None)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Dichte:" in out
    # 2 von 4 Objekten haben dokumentierte Dichte → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_kategorie_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Kategorie-Quote zusaetzlich zu Bildern/Funddatum/Wert/Gewicht/KI auf.

    Kategorie (Inventar-Klassifizierung) ist die erste ID-Achse - vor Mineral/Fundort
    in der CLI-Ausgabe, weil sie die vorgelagerte Inventar-Sortierung steuert.
    Symmetrische CLI-Sichtbarkeit fuer das Datenpflege-Dashboard."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "kat.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?,?)",
        [("OBJ_0001", "Handstück"), ("OBJ_0002", "Kristall"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Kategorie:" in out
    # 2 von 4 Objekten haben dokumentierte Kategorie → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_mineral_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Mineral_Primaer-Quote zusaetzlich zu Bildern/Funddatum/Wert/Gewicht/KI auf."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "min.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer) VALUES (?,?)",
        [("OBJ_0001", "Quarz"), ("OBJ_0002", "Calcit"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Mineral_Primaer:" in out
    # 2 von 4 Objekten haben dokumentiertes Mineral → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_varietaet_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Varietaet-Quote direkt unter Mineral_Primaer auf.
    Spiegelt die mineralogische Identifikations-Achse auf die feinere Sub-
    Klassifizierung (Bergkristall/Milchquarz/Rauchquarz innerhalb der Quarz-
    Familie) - symmetrische CLI-Sichtbarkeit fuer das Datenpflege-Dashboard,
    weil die Differenz zur Mineral_Primaer-Quote die Sub-Klassifizierungs-
    Luecke beziffert (Stuecke mit Familie, aber ohne Auspraegung)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "var.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?,?)",
        [("OBJ_0001", "Bergkristall"), ("OBJ_0002", "Rauchquarz"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Varietaet:" in out
    # 2 von 4 Objekten haben dokumentierte Varietaet → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_gesteinsart_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Gesteinsart-Quote direkt unter Varietaet auf.
    Petrologische Achse (Granit/Gneis/Basalt/Sandstein) symmetrisch zur
    mineralogischen Achse (Mineral_Primaer/Varietaet) - die petrologische
    Einordnung sagt etwas anderes ueber das Stueck aus als die mineralogische
    Familie (ein Quarz-Stueck kann aus Pegmatit oder Hydrothermal-Ader stammen,
    der mineralogische Befund bleibt gleich aber die Gesteinsart sagt etwas
    anderes ueber den geologischen Bildungs-Kontext aus). Symmetrische CLI-
    Sichtbarkeit fuer das Datenpflege-Dashboard."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "ges.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?,?)",
        [("OBJ_0001", "Granit"), ("OBJ_0002", "Gneis"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Gesteinsart:" in out
    # 2 von 4 Objekten haben dokumentierte Gesteinsart → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_confidence_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Confidence-Quote direkt unter den KI-Analyse-Quoten
    auf. Confidence ist konzeptionell verwandt (Bestimmungs-Qualitaet), aber
    auf einer separaten Achse: KI-Analyse misst die Anwendungs-Durchdringung,
    Confidence den quantitativen Sicherheits-Score je Stueck (handgepflegt
    oder von der KI uebertragen). Ohne Confidence ist ein Stueck zwischen
    'sicher' (>=75) und 'unsicher' (<25) nicht einzuordnen - die naechste
    typische Pflege-Achse nach KI-Analyse. Symmetrische CLI-Sichtbarkeit
    fuer das Datenpflege-Dashboard."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "conf.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?,?)",
        [("OBJ_0001", 90), ("OBJ_0002", 50),
         ("OBJ_0003", None), ("OBJ_0004", None)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Confidence:" in out
    # 2 von 4 Objekten haben dokumentierte Confidence → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_kristallsystem_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Kristallsystem-Quote direkt unter Gesteinsart auf.
    Kristallographische Symmetrie-Achse (kubisch/tetragonal/hexagonal/trigonal/
    orthorhombisch/monoklin/triklin/amorph) symmetrisch zur mineralogischen
    Achse (Mineral_Primaer/Varietaet) und zur petrologischen Achse (Gesteinsart)
    - das Kristallsystem sagt etwas anderes ueber das Stueck aus als die
    Mineral-Familie oder die Gesteins-Einbettung (es beschreibt den inneren
    Symmetrie-Aufbau, der haendisch aus der Mineralart abzuleiten ist).
    Symmetrische CLI-Sichtbarkeit fuer das Datenpflege-Dashboard."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "ks.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?,?)",
        [("OBJ_0001", "trigonal"), ("OBJ_0002", "kubisch"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Kristallsystem:" in out
    # 2 von 4 Objekten haben dokumentiertes Kristallsystem → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_magnetismus_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Magnetismus-Quote direkt unter Kristallsystem auf.
    Magnetisch-physikalische Pruef-Achse (nein/schwach/ja) symmetrisch zur
    kristallographischen Symmetrie-Achse (kubisch/tetragonal/...) - beide sind
    kurze Enum-Skalen aus dem Feldwoerterbuch und beide spiegeln den Pflege-
    Stand qualitativer Pruefparameter. Symmetrische CLI-Sichtbarkeit fuer das
    Datenpflege-Dashboard auf der Achse "wieviele Stuecke wurden mit dem
    (Hand-)Magneten geprueft?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "mg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?,?)",
        [("OBJ_0001", "nein"), ("OBJ_0002", "ja"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Magnetismus:" in out
    # 2 von 4 Objekten haben dokumentierten Magnetismus → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_glanz_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Glanz-Quote direkt unter Magnetismus auf. Optisch-
    physikalische Diagnose-Achse (glasig/wachsig/matt/metallisch/fettig/seidig/
    perlmutt) symmetrisch zur magnetisch-physikalischen Pruef-Achse (nein/
    schwach/ja) - beide sind kurze Enum-Skalen aus dem Feldwoerterbuch und
    beide spiegeln qualitative Pruefparameter ohne instrumentelle Mess-Mittel.
    Symmetrische CLI-Sichtbarkeit fuer das Datenpflege-Dashboard auf der Achse
    "wieviele Stuecke wurden auf die Glanz-Auspraegung hin charakterisiert?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gl.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?,?)",
        [("OBJ_0001", "glasig"), ("OBJ_0002", "metallisch"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Glanz:" in out
    # 2 von 4 Objekten haben dokumentierten Glanz → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_transparenz_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Transparenz-Quote direkt unter Glanz auf. Optisch-
    physikalische Diagnose-Achse (durchsichtig/durchscheinend/opak) symmetrisch
    zur Oberflaechen-Reflexions-Achse (glasig/wachsig/matt/...) - beide sind
    kurze Enum-Skalen aus dem Feldwoerterbuch und beide spiegeln qualitative
    Pruefparameter ohne instrumentelle Mess-Mittel (Auflicht vs. Durchlicht).
    Symmetrische CLI-Sichtbarkeit fuer das Datenpflege-Dashboard auf der Achse
    "wieviele Stuecke wurden auf die Transparenz hin charakterisiert?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tp.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?,?)",
        [("OBJ_0001", "durchsichtig"), ("OBJ_0002", "opak"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Transparenz:" in out
    # 2 von 4 Objekten haben dokumentierte Transparenz → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_spaltbarkeit_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Spaltbarkeit-Quote direkt unter Transparenz auf.
    Mechanisch-strukturelle Diagnose-Achse (vollkommen/gut/deutlich/undeutlich/
    keine) symmetrisch zur optisch-physikalischen Diagnose-Doppel-Achse (Glanz/
    Transparenz) - waehrend Glanz/Transparenz die optische Eigenschaft beschreiben,
    beschreibt Spaltbarkeit das mechanische Bruchverhalten entlang kristallo-
    graphisch bevorzugter Ebenen. Symmetrische CLI-Sichtbarkeit fuer das Daten-
    pflege-Dashboard auf der Achse "wieviele Stuecke wurden auf die Spaltbarkeit
    hin charakterisiert?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "sp.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?,?)",
        [("OBJ_0001", "vollkommen"), ("OBJ_0002", "keine"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Spaltbarkeit:" in out
    # 2 von 4 Objekten haben dokumentierte Spaltbarkeit → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_bruch_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Bruch-Quote direkt unter Spaltbarkeit auf.
    Schliesst die mechanisch-strukturelle Diagnose-Doppel-Achse: Spaltbarkeit
    (geordnete Bruchrichtung entlang kristallographisch bevorzugter Ebenen) ->
    Bruch (ungeordnetes Versagensmuster ausserhalb der Spaltebenen, sechs
    Enum-Werte muschelig/uneben/splittrig/faserig/erdig/glatt). Symmetrische
    CLI-Sichtbarkeit fuer das Datenpflege-Dashboard auf der Achse "wieviele
    Stuecke wurden auf das Bruchverhalten hin charakterisiert?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "br.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?,?)",
        [("OBJ_0001", "muschelig"), ("OBJ_0002", "faserig"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Bruch:" in out
    # 2 von 4 Objekten haben dokumentierten Bruch → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_beste_verwendung_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Beste-Verwendung-Quote direkt unter Bruch auf.
    Schliesst die Coverage-Reihe der strukturierten Enum-Felder aus dem Feldwoerterbuch
    ab: nach der Diagnose-Reihe (Magnetismus/Glanz/Transparenz/Spaltbarkeit/Bruch
    - objektive Beobachtungen am Stueck) folgt die Verwendungs-/Empfehlungs-Achse
    (Schmuck/Sammlung/Forschung/Industrie/Talisman/Dekoration - subjektive
    Sammler-Entscheidung ueber den weiteren Lebensweg des Stuecks). Symmetrische
    CLI-Sichtbarkeit fuer das Datenpflege-Dashboard auf der Achse "wieviele
    Stuecke tragen ueberhaupt eine Verwendungs-Empfehlung?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "bv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?,?)",
        [("OBJ_0001", "Schmuck"), ("OBJ_0002", "Sammlung"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Beste Verwendung:" in out
    # 2 von 4 Objekten haben dokumentierte Beste_Verwendung → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_fundort_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Fundort-Quote zusaetzlich zu Bildern/Funddatum/Wert/Gewicht/KI/Mineral auf.
    Spiegelt die mineralogische Identifikations-Achse (Mineral_Primaer) auf die
    geografische Provenienz-Achse - symmetrische CLI-Sichtbarkeit fuer das
    Datenpflege-Dashboard."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fundort.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [("OBJ_0001", "Davos"), ("OBJ_0002", "Zermatt"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Fundort:" in out
    # 2 von 4 Objekten haben dokumentierten Fundort → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_farbe_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Farbe-Quote (tatsaechlich gesehene Mineral-Farbe)
    direkt nach Fundort und vor Strichfarbe auf. Farbe_beobachtet ist die
    niederschwelligste visuelle Diagnose-Achse - keine Werkzeuge noetig, am
    Tageslicht beobachtbar - und damit die paarweise Farb-Achse zur
    diagnostisch invarianten Strichfarbe. Symmetrische CLI-Sichtbarkeit
    fuer das Datenpflege-Dashboard auf der Achse "wie tief ist der erste
    Blick auf das Stueck erfasst?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fb.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Farbe_beobachtet) VALUES (?,?)",
        [("OBJ_0001", "rauchgrau"), ("OBJ_0002", "ziegelrot"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Farbe (beobachtet):" in out
    # 2 von 4 Objekten haben Farbe → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_strichfarbe_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Strichfarbe-Quote (Farbe des Pulvers auf
    Porzellan-Strichplaette) direkt nach Fundort und vor Notizen auf.
    Strichfarbe ist die freie str-Pruef-Achse neben dem Enum-validierten
    Magnetismus und einer der drei klassischen qualitativen Bestimmungs-
    Pruefparameter aus dem Feldwoerterbuch (neben Magnetismus und HCl-
    Reaktion); eine niedrige Quote ist typisch, weil der Strichtest invasiv
    ist und nicht routinemaessig durchgefuehrt wird. Symmetrische CLI-
    Sichtbarkeit fuer das Datenpflege-Dashboard auf der Achse "wie tief ist
    die mineralogische Bestimmung durch Strichtest bestaetigt?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "sf.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Strichfarbe) VALUES (?,?)",
        [("OBJ_0001", "gelblich-weiss"),
         ("OBJ_0002", "gruenlich-schwarz"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Strichfarbe:" in out
    # 2 von 4 Objekten haben Strichfarbe → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_hcl_reaktion_quote(tmp_path, capsys):
    """Coverage-Block fuehrt HCl-Reaktion-Quote (Salzsaeure-Test) direkt nach
    Strichfarbe und vor Notizen auf. HCl-Reaktion schliesst die Pruefparameter-
    Coverage-Trias (Magnetismus, Strichfarbe, HCl-Reaktion) aus dem
    Feldwoerterbuch ab; eine niedrige Quote ist typisch, weil der Salzsaeure-
    Test invasiv ist und nur fuer carbonat-verdaechtige Stuecke durchgefuehrt
    wird."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "hcl.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, HCl_Reaktion) VALUES (?,?)",
        [("OBJ_0001", "stark"), ("OBJ_0002", "keine"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "HCl-Reaktion:" in out
    # 2 von 4 Objekten haben HCl-Reaktion → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_uv_365nm_quote(tmp_path, capsys):
    """Coverage-Block fuehrt UV-365nm-Quote (Fluoreszenz bei Langwellen-UV)
    direkt nach HCl-Reaktion und vor Notizen auf. UV-365nm spiegelt die
    qualitativen Pruefparameter-Trias (Magnetismus/Strichfarbe/HCl-Reaktion)
    auf die optisch-UV-Diagnose-Achse - vierte zentrale Pruef-Achse aus dem
    Feldwoerterbuch, bevor mit Notizen die freie Sonstiges-Achse beginnt.
    Eine niedrige Quote ist typisch in Sammlungen ohne dedizierte UV-Box."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "uv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, UV_365nm) VALUES (?,?)",
        [("OBJ_0001", "stark gruen"), ("OBJ_0002", "keine"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "UV 365 nm:" in out
    # 2 von 4 Objekten haben UV_365nm → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_uv_254nm_quote(tmp_path, capsys):
    """Coverage-Block fuehrt UV-254nm-Quote (Fluoreszenz bei Kurzwellen-UV)
    direkt nach UV-365nm und vor Notizen auf - paarweise Komplement-Achse,
    damit die Doppel-Wellenlaengen-Achse als gemeinsamer Block lesbar ist.
    Eine typischerweise deutlich niedrigere Quote als UV_365nm, weil die
    254-nm-Lampen teurer und gesundheitlich riskanter sind und nur in
    Sammlungen mit erweiterter UV-Ausruestung gepflegt werden."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "uv254.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, UV_254nm) VALUES (?,?)",
        [("OBJ_0001", "stark blauweiss"), ("OBJ_0002", "keine"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "UV 254 nm:" in out
    # 2 von 4 Objekten haben UV_254nm → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_reaktionshinweis_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Reaktionshinweis-Quote (erklaerende Begleit-Notiz
    zu UV/HCl/Magnetismus) direkt nach UV 254 nm und vor Notizen auf -
    thematisch fokussierter Freitext zu den Reaktions-Spalten, vor der
    allgemeinen Sonstiges-Achse Notizen. Symmetrische CLI-Sichtbarkeit fuer
    das Datenpflege-Dashboard auf der Achse "Wie viel Anteil der Sammlung
    traegt eine mineralogische Reaktions-Erklaerung neben der
    Roh-Beobachtung?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "rh.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Reaktionshinweis) VALUES (?,?)",
        [("OBJ_0001", "Dolomit-Mischphase erklaert die schwache HCl-Reaktion"),
         ("OBJ_0002", "Fluoreszenz nur unter Langwelle"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Reaktionshinweis:" in out
    # 2 von 4 Objekten haben Reaktionshinweis → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_pruefempfehlungen_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Pruefempfehlungen-Quote (empfohlene
    Bestaetigungstests aus der Sonstiges-Gruppe des Feldwoerterbuchs)
    direkt nach Reaktionshinweis und vor Notizen auf - die drei Freitext-
    Achsen decken zusammen den vollstaendigen Bestimmungs-Workflow ab
    (Reaktionshinweis interpretiert die Vergangenheit, Pruefempfehlungen
    plant die Zukunft, Notizen begleitet die Gegenwart). Symmetrische
    CLI-Sichtbarkeit fuer das Datenpflege-Dashboard auf der Achse "wie
    viel Anteil der Sammlung traegt einen dokumentierten Pruef-Plan?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "pe.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Pruefempfehlungen) VALUES (?,?)",
        [("OBJ_0001", "Dichtebestimmung mit Pyknometer"),
         ("OBJ_0002", "EDX-Analyse VHS-Kurs"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Pruefempfehlungen:" in out
    # 2 von 4 Objekten haben Pruefempfehlungen → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_notizen_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Notizen-Quote (freie Beobachtungs-Spalte) am Ende
    der Feld-Sektion auf, vor der Merge-Quote. Notizen sind die "Sonstiges"-
    Achse jenseits der 43 strukturierten Standardfelder; eine niedrige Quote
    ist typisch, weil der Sammler die Spalte nur bei Beobachtungs-Anlass
    pflegt. Symmetrische CLI-Sichtbarkeit fuer das Datenpflege-Dashboard auf
    der Achse "wie viel Anteil der Sammlung traegt eine handgepflegte freie
    Beobachtung?"."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "nz.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, notizen) VALUES (?,?)",
        [("OBJ_0001", "Habitus saeulenfoermig"), ("OBJ_0002", "Geerbt von Onkel"),
         ("OBJ_0003", None), ("OBJ_0004", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Notizen:" in out
    # 2 von 4 Objekten haben Notizen → 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_merge_quote(tmp_path, capsys):
    """Coverage-Block fuehrt die Merge-Quote (Anteil der Kanon-Objekte aus
    Duplikat-Merges) zusaetzlich zu den Feld-Coverage-Quoten auf. Spiegelt das
    Coverage-Vokabular auf die Provenienz-Achse - symmetrische CLI-Sichtbarkeit
    fuer die Sammlungs-Konsolidierungs-Tiefe."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "merge.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    # OBJ_0001 hat zwei Aliase, OBJ_0002 einen -> 2 von 4 Kanon-Objekten
    # sind aus Merges hervorgegangen (Merge-Quote 50 %).
    c.executemany(
        "INSERT INTO aliases (alias_id, canonical_id, merge_quelle) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0100", "OBJ_0001", "duplikat_gruppen.json"),
            ("OBJ_0101", "OBJ_0001", "manuell"),
            ("OBJ_0102", "OBJ_0002", "duplikat_gruppen.json"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Merge (Aliase):" in out
    # 2 von 4 Kanon-Objekten haben mindestens einen Alias -> 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_ki_analyse_uebernommen_quote(tmp_path, capsys):
    """Coverage-Block fuehrt die uebernommene-KI-Quote zusaetzlich zur reinen
    KI-Analyse-Quote. Die Differenz beider Zeilen beziffert die Akzeptanz-
    Luecke (KI lief, aber Vorschlaege wurden noch nicht uebernommen)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "kiu.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",)],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json, uebernommen_json) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "claude-opus-4-7", "{}", '{"a":1}'),
            # OBJ_0002: KI lief, aber Vorschlag noch nicht uebernommen
            ("OBJ_0002", "claude-opus-4-7", "{}", None),
            # OBJ_0003, OBJ_0004: keine Analyse
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "KI-Analyse (ueb.):" in out
    # 2 von 4 mit Analyse (50%), 1 von 4 uebernommen (25%)
    assert "50.0 %" in out
    assert "25.0 %" in out


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


def test_text_ausgabe_zeigt_wert_pro_mineral(tmp_path, capsys):
    """Wert-pro-Mineral-Block summiert CHF-Felder pro Mineraltyp und sortiert absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Quarz",   100.0,  50.0),  # Quarz total 150
            ("OBJ_0002", "Quarz",   200.0, None),   # Quarz total 350
            ("OBJ_0003", "Calcit",  None,  800.0),  # Calcit total 800
            ("OBJ_0004", "Pyrit",    25.0, None),   # Pyrit  total  25
            ("OBJ_0005", "Pyrit",   None,  None),   # Pyrit  bleibt 25
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Mineral (CHF):" in out
    # Reihenfolge absteigend nach Summe: Calcit (800), Quarz (350), Pyrit (25)
    # Nur im Wert-Block pruefen, da Calcit/Quarz/Pyrit auch in Top-Minerale stehen.
    block = out.split("Wert pro Mineral (CHF):", 1)[1]
    assert block.index("Calcit") < block.index("Quarz") < block.index("Pyrit")


def test_text_ausgabe_ohne_werte_keine_wert_pro_mineral_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Block gar nicht (Liste leer)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer) VALUES (?, ?)",
        [("OBJ_0001", "Quarz"), ("OBJ_0002", "Calcit")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Mineral" not in out


def test_top_flag_steuert_wert_pro_mineral_laenge(tmp_path, capsys):
    """--top N begrenzt auch die Wert-pro-Mineral-Liste."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpmt.sqlite3"
    c = open_db(db_file)
    # 6 Mineralien mit absteigenden Werten
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Mineral_{i:02d}", float(100 - i)) for i in range(1, 7)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file), "--top", "3"])
    out = capsys.readouterr().out
    assert "Mineral_01" in out  # Hoechster Wert (99) - immer erste 3
    assert "Mineral_02" in out
    assert "Mineral_03" in out
    # Wert-Liste hat <=3 Eintraege; Mineral_04..06 nicht enthalten.
    # (Mineral_04..06 koennen sonst in by_mineral auftauchen; pruefe gezielt im
    # Wert-pro-Mineral-Block.)
    block = out.split("Wert pro Mineral (CHF):", 1)[1]
    assert "Mineral_04" not in block
    assert "Mineral_05" not in block
    assert "Mineral_06" not in block


def test_text_ausgabe_zeigt_wert_pro_fundort(tmp_path, capsys):
    """Wert-pro-Fundort-Block summiert CHF-Felder pro Fundort und sortiert absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpf.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Davos",   100.0,  50.0),  # Davos total 150
            ("OBJ_0002", "Davos",   200.0, None),   # Davos total 350
            ("OBJ_0003", "Zermatt", None,  800.0),  # Zermatt total 800
            ("OBJ_0004", "St. Gallen", 25.0, None), # St. Gallen total 25
            ("OBJ_0005", "St. Gallen", None, None), # St. Gallen bleibt 25
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Fundort (CHF):" in out
    # Reihenfolge absteigend: Zermatt (800), Davos (350), St. Gallen (25)
    block = out.split("Wert pro Fundort (CHF):", 1)[1]
    assert block.index("Zermatt") < block.index("Davos") < block.index("St. Gallen")


def test_text_ausgabe_ohne_werte_keine_wert_pro_fundort_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Fundort-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpf0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [("OBJ_0001", "Davos"), ("OBJ_0002", "Zermatt")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Fundort" not in out


def test_text_ausgabe_zeigt_funde_pro_jahr(tmp_path, capsys):
    """Funde-pro-Jahr-Block listet Jahre chronologisch mit Trefferanzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fpj.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2019-06-13"),
            ("OBJ_0002", "2019-08-01"),
            ("OBJ_0003", "2021-05-10"),
            ("OBJ_0004", "2024-12-31"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funde pro Jahr:" in out
    block = out.split("Funde pro Jahr:", 1)[1]
    # Chronologisch: 2019, 2021, 2024
    assert block.index("2019") < block.index("2021") < block.index("2024")


def test_text_ausgabe_ohne_funddatum_keine_jahr_zeile(tmp_path, capsys):
    """Ohne gueltige Funddaten erscheint der Funde-pro-Jahr-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fpj0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", None), ("OBJ_0002", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funde pro Jahr:" not in out


def test_top_flag_begrenzt_funde_pro_jahr(tmp_path, capsys):
    """--top N begrenzt die Jahres-Histogramm-Laenge (Top-N nach Trefferzahl)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fpjt.sqlite3"
    c = open_db(db_file)
    # 5 Jahre mit absteigender Trefferzahl: 2024 (5), 2023 (4), 2022 (3), 2021 (2), 2020 (1)
    rows = []
    obj_n = 0
    for year, count in [(2024, 5), (2023, 4), (2022, 3), (2021, 2), (2020, 1)]:
        for _ in range(count):
            obj_n += 1
            rows.append((f"OBJ_{obj_n:04d}", f"{year}-06-13"))
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)", rows)
    c.commit()
    c.close()
    main(["--db", str(db_file), "--top", "3"])
    out = capsys.readouterr().out
    # Block strikt auf den Jahres-Abschnitt eingrenzen (Dekaden-Block laeuft
    # darunter und enthaelt 2020er als Label - sonst falsche Positiv-Treffer).
    block = out.split("Funde pro Jahr:", 1)[1].split("Funde pro Jahrzehnt:", 1)[0]
    # Top-3 nach Anzahl: 2024, 2023, 2022 (chronologisch sortiert).
    assert "2022" in block
    assert "2023" in block
    assert "2024" in block
    # 2020/2021 fallen heraus (nur 1/2 Treffer).
    assert "2020" not in block
    assert "2021" not in block


def test_text_ausgabe_zeigt_funde_pro_jahrzehnt(tmp_path, capsys):
    """Dekaden-Block liegt unter dem Jahres-Block und summiert die Jahre auf 10er-Schritte."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fpd.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "1985-01-01"),
            ("OBJ_0002", "1989-12-31"),
            ("OBJ_0003", "1995-06-13"),
            ("OBJ_0004", "2024-06-13"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funde pro Jahrzehnt:" in out
    block = out.split("Funde pro Jahrzehnt:", 1)[1]
    # Chronologisch aufsteigend, Label mit 'er'-Suffix
    assert "1980er" in block
    assert "1990er" in block
    assert "2020er" in block
    assert block.index("1980er") < block.index("1990er") < block.index("2020er")


def test_text_ausgabe_ohne_funddatum_keine_jahrzehnt_zeile(tmp_path, capsys):
    """Ohne gueltige Funddaten erscheint auch der Dekaden-Block nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fpd0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", None), ("OBJ_0002", "")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funde pro Jahrzehnt:" not in out


def test_text_ausgabe_zeigt_sammlung_erfasst_pro_jahr(tmp_path, capsys):
    """Sammlungswachstum-Block listet Erfassungs-Jahre chronologisch."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "sepj.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-01-15 09:00:00"),
            ("OBJ_0002", "2025-06-13 14:30:00"),
            ("OBJ_0003", "2025-12-01 08:00:00"),
            ("OBJ_0004", "2026-06-19 08:45:00"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Sammlung erfasst pro Jahr:" in out
    block = out.split("Sammlung erfasst pro Jahr:", 1)[1]
    # Chronologisch aufsteigend
    assert block.index("2024") < block.index("2025") < block.index("2026")


def test_text_ausgabe_ohne_erstellt_am_jahr_keine_zeile(tmp_path, capsys):
    """open_db() ohne INSERTs → keine Objekte → Sammlungswachstum-Block bleibt aus."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "sepj0.sqlite3"
    c = open_db(db_file)
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Sammlung erfasst pro Jahr:" not in out
    assert "Sammlung erfasst pro Monat:" not in out


def test_text_ausgabe_zeigt_sammlung_erfasst_pro_jahrzehnt(tmp_path, capsys):
    """Erfassungs-Dekaden-Block liegt unter dem Jahres-Block und ist chronologisch sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "sepd.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            # 2010er-Phase
            ("OBJ_0001", "2014-05-12 09:00:00"),
            ("OBJ_0002", "2018-11-03 16:45:00"),
            # 2020er-Welle
            ("OBJ_0003", "2024-01-15 09:00:00"),
            ("OBJ_0004", "2025-06-13 14:30:00"),
            ("OBJ_0005", "2026-06-19 08:45:00"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Sammlung erfasst pro Jahrzehnt:" in out
    block = out.split("Sammlung erfasst pro Jahrzehnt:", 1)[1]
    # Chronologisch aufsteigend: 2010er vor 2020er
    assert block.index("2010er") < block.index("2020er")
    # Liegt unter dem Jahres-Block, ueber dem Monats-Block
    assert (out.index("Sammlung erfasst pro Jahr:")
            < out.index("Sammlung erfasst pro Jahrzehnt:")
            < out.index("Sammlung erfasst pro Monat:"))


def test_text_ausgabe_ohne_erstellt_am_jahrzehnt_keine_zeile(tmp_path, capsys):
    """Leere DB → Erfassungs-Dekaden-Block bleibt aus (analog zum Jahres-Block)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "sepd0.sqlite3"
    c = open_db(db_file)
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Sammlung erfasst pro Jahrzehnt:" not in out


def test_text_ausgabe_zeigt_sammlung_erfasst_pro_monat(tmp_path, capsys):
    """Erfassungs-Saisonalitaet-Block liegt unter dem Jahres-Block und ist 01..12 sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "sepm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-03-15 09:00:00"),
            ("OBJ_0002", "2025-03-13 14:30:00"),
            ("OBJ_0003", "2025-06-01 08:00:00"),
            ("OBJ_0004", "2026-11-19 08:45:00"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Sammlung erfasst pro Monat:" in out
    block = out.split("Sammlung erfasst pro Monat:", 1)[1]
    # 01..12 chronologisch: 03 vor 06 vor 11
    assert block.index("03") < block.index("06") < block.index("11")
    # Jahres-Block kommt zuerst (spiegelt _format_text-Reihenfolge)
    assert (out.index("Sammlung erfasst pro Jahr:")
            < out.index("Sammlung erfasst pro Monat:"))


def test_text_ausgabe_zeigt_pflege_aktivitaet_pro_jahr(tmp_path, capsys):
    """Pflege-Aktivitaets-Block liegt unter den Erfassungs-Bloecken und ist chronologisch sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "paj.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) VALUES (?, ?, ?)",
        [
            # Nie nachgepflegt: erstellt_am == geaendert_am
            ("OBJ_0001", "2024-01-15 09:00:00", "2024-01-15 09:00:00"),
            # Spaeter nachgepflegt (KI-Analyse uebernommen 2025)
            ("OBJ_0002", "2024-08-13 14:30:00", "2025-03-22 11:00:00"),
            # Spaeter nachgepflegt (Foto nachgereicht 2026)
            ("OBJ_0003", "2024-12-05 10:00:00", "2026-02-19 16:00:00"),
            ("OBJ_0004", "2025-06-19 08:45:00", "2026-06-19 09:00:00"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Pflege-Aktivitaet pro Jahr:" in out
    block = out.split("Pflege-Aktivitaet pro Jahr:", 1)[1]
    # Chronologisch aufsteigend: 2024 (1x) -> 2025 (1x) -> 2026 (2x)
    assert block.index("2024") < block.index("2025") < block.index("2026")
    # Liegt unter den Erfassungs-Bloecken (spiegelt _format_text-Reihenfolge)
    assert (out.index("Sammlung erfasst pro Monat:")
            < out.index("Pflege-Aktivitaet pro Jahr:"))


def test_text_ausgabe_ohne_geaendert_am_jahr_keine_zeile(tmp_path, capsys):
    """Leere DB → Pflege-Aktivitaets-Block bleibt aus (analog zu den Erfassungs-Bloecken)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "paj0.sqlite3"
    c = open_db(db_file)
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Pflege-Aktivitaet pro Jahr:" not in out


def test_text_ausgabe_zeigt_pflege_aktivitaet_pro_jahrzehnt(tmp_path, capsys):
    """Pflege-Dekaden-Block liegt unter dem Pflege-Jahres-Block und ist chronologisch sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "pad.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [
            # 2010er-Phase (handgepflegt)
            ("OBJ_0001", "2014-05-12 09:00:00"),
            ("OBJ_0002", "2018-11-03 16:45:00"),
            # 2020er-Welle (KI-Welle)
            ("OBJ_0003", "2024-01-15 09:00:00"),
            ("OBJ_0004", "2025-06-13 14:30:00"),
            ("OBJ_0005", "2026-06-19 08:45:00"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Pflege-Aktivitaet pro Jahrzehnt:" in out
    block = out.split("Pflege-Aktivitaet pro Jahrzehnt:", 1)[1]
    # Chronologisch aufsteigend: 2010er vor 2020er
    assert block.index("2010er") < block.index("2020er")
    # Liegt unter dem Pflege-Jahres-Block (spiegelt _format_text-Reihenfolge)
    assert (out.index("Pflege-Aktivitaet pro Jahr:")
            < out.index("Pflege-Aktivitaet pro Jahrzehnt:"))


def test_text_ausgabe_ohne_geaendert_am_jahrzehnt_keine_zeile(tmp_path, capsys):
    """Leere DB → Pflege-Dekaden-Block bleibt aus (analog zum Pflege-Jahres-Block)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "pad0.sqlite3"
    c = open_db(db_file)
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Pflege-Aktivitaet pro Jahrzehnt:" not in out


def test_text_ausgabe_zeigt_funde_pro_monat(tmp_path, capsys):
    """Monats-Block liegt unter Jahr/Jahrzehnt und gibt 01..12 chronologisch aus."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fpm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2020-07-15"),
            ("OBJ_0002", "2021-07-20"),
            ("OBJ_0003", "2022-08-10"),
            ("OBJ_0004", "2023-12-05"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funde pro Monat:" in out
    block = out.split("Funde pro Monat:", 1)[1]
    # Aufsteigend nach Monatsziffer: 07 -> 08 -> 12
    assert block.index("07") < block.index("08") < block.index("12")


def test_text_ausgabe_zeigt_seltenheit_global(tmp_path, capsys):
    """Rarity-Histogramm 1..10 wird chronologisch nach Skalenwert ausgegeben."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "selt.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 2),
            ("OBJ_0002", 2),
            ("OBJ_0003", 7),
            ("OBJ_0004", 10),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Seltenheit global (1..10):" in out
    block = out.split("Seltenheit global (1..10):", 1)[1].splitlines()
    # Reihenfolge: 2 -> 7 -> 10 (aufsteigend nach Skala, nicht nach Anzahl)
    stufen = [line.strip().split()[0] for line in block if line.strip()][:3]
    assert stufen == ["2", "7", "10"]


def test_text_ausgabe_ohne_seltenheit_keine_zeile(tmp_path, capsys):
    """Ohne Seltenheits-Eintraege erscheint der Histogramm-Block nicht.

    Geprueft wird der voll qualifizierte Block-Header (``Seltenheit global
    (1..10):``) als eindeutiger Marker des Histogramm-Blocks - der lose
    Substring ``Seltenheit global`` wuerde sonst auch die Coverage-Zeile
    treffen (``Seltenheit global:   0.0 %`` im Coverage-Block), die per
    Konvention immer erscheint, sobald objekte_total > 0 ist (spiegelt das
    Verhalten der Confidence-Coverage-Zeile, die ebenfalls bei 0 % gezeigt
    wird, weil der Pflege-Stand-Indikator gerade dann interessant ist).
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "selt0.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Seltenheit global (1..10):" not in out
    assert "Seltenheit Fundort (1..10):" not in out
    assert "Nachfrage (1..10):" not in out


def test_text_ausgabe_zeigt_seltenheit_fundort(tmp_path, capsys):
    """Fundort-Rarity-Histogramm 1..10 spiegelt by_seltenheit_global im CLI."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "selt_fo.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 3),
            ("OBJ_0002", 3),
            ("OBJ_0003", 5),
            ("OBJ_0004", 9),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Seltenheit Fundort (1..10):" in out
    block = out.split("Seltenheit Fundort (1..10):", 1)[1].splitlines()
    stufen = [line.strip().split()[0] for line in block if line.strip()][:3]
    assert stufen == ["3", "5", "9"]


def test_text_ausgabe_zeigt_nachfrage(tmp_path, capsys):
    """Marktnachfrage-Histogramm 1..10 spiegelt by_seltenheit_global im CLI."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "nach.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 1),
            ("OBJ_0002", 4),
            ("OBJ_0003", 4),
            ("OBJ_0004", 8),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Nachfrage (1..10):" in out
    block = out.split("Nachfrage (1..10):", 1)[1].splitlines()
    stufen = [line.strip().split()[0] for line in block if line.strip()][:3]
    assert stufen == ["1", "4", "8"]


def test_text_ausgabe_ohne_funddatum_keine_monat_zeile(tmp_path, capsys):
    """Ohne gueltige Funddaten erscheint auch der Monats-Block nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "fpm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", None), ("OBJ_0002", ""), ("OBJ_0003", "2024")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Funde pro Monat:" not in out


def test_text_ausgabe_zeigt_wert_pro_funddatum_jahr(tmp_path, capsys):
    """Wert-pro-Funddatum-Jahr-Block listet die wertvollsten Sammeljahre absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpfj.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "2020-05-13", 1000.0, None),     # 2020: 1000
            ("OBJ_0002", "2021-04-01", 100.0, 200.0),     # 2021: 300
            ("OBJ_0003", "2022-03-01", 50.0, None),       # 2022: 50
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Funddatum-Jahr (CHF):" in out
    block = out.split("Wert pro Funddatum-Jahr (CHF):", 1)[1]
    assert block.index("2020") < block.index("2021") < block.index("2022")


def test_text_ausgabe_ohne_werte_keine_wert_pro_funddatum_jahr_zeile(tmp_path, capsys):
    """Ohne CHF-Werte erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpfj0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", "2020-05-13"), ("OBJ_0002", "2021-04-01")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Funddatum-Jahr" not in out


def test_text_ausgabe_zeigt_gewicht_pro_funddatum_jahr(tmp_path, capsys):
    """Gewicht-pro-Funddatum-Jahr-Block listet die schwersten Sammeljahre."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpfj.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2020-05-13", 1000.0),
            ("OBJ_0002", "2021-04-01", 250.0),
            ("OBJ_0003", "2022-03-01", 50.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Funddatum-Jahr (g):" in out
    block = out.split("Gewicht pro Funddatum-Jahr (g):", 1)[1]
    assert block.index("2020") < block.index("2021") < block.index("2022")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_funddatum_jahr_zeile(tmp_path, capsys):
    """Ohne Gewichts-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpfj0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", "2020-05-13"), ("OBJ_0002", "2021-04-01")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Funddatum-Jahr" not in out


def test_text_ausgabe_zeigt_wert_pro_erstellt_am_jahr(tmp_path, capsys):
    """Wert-pro-Erfassungs-Jahr-Block listet die wertvollsten Erfassungs-Jahrgaenge.

    Spiegelt wert_pro_funddatum_jahr auf der Erfassungs-Achse - macht
    Migrations-Wellen sichtbar (z.B. grosse Altbestand-Erfassung in 2026).
    Sortierung absteigend nach Summe.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpej.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", "2024-05-13 09:00:00", 1000.0, None),     # 2024: 1000
            ("OBJ_0002", "2025-04-01 14:00:00", 100.0, 200.0),     # 2025: 300
            ("OBJ_0003", "2026-03-01 08:00:00", 50.0, None),       # 2026: 50
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Erfassungs-Jahr (CHF):" in out
    block = out.split("Wert pro Erfassungs-Jahr (CHF):", 1)[1]
    assert block.index("2024") < block.index("2025") < block.index("2026")


def test_text_ausgabe_ohne_werte_keine_wert_pro_erstellt_am_jahr_zeile(tmp_path, capsys):
    """Ohne CHF-Werte erscheint der Erfassungs-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpej0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", "2024-05-13 09:00:00"),
         ("OBJ_0002", "2025-04-01 14:00:00")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Erfassungs-Jahr" not in out


def test_text_ausgabe_zeigt_gewicht_pro_erstellt_am_jahr(tmp_path, capsys):
    """Gewicht-pro-Erfassungs-Jahr-Block listet die schwersten Erfassungs-Jahrgaenge.

    Spiegelt gewicht_pro_funddatum_jahr; zeigt schwere Migrations-Wellen
    (Geroell-Altbestaende), die in der Fund-Achse untergehen koennen.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpej.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2024-05-13 09:00:00", 1000.0),
            ("OBJ_0002", "2025-04-01 14:00:00", 250.0),
            ("OBJ_0003", "2026-03-01 08:00:00", 50.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Erfassungs-Jahr (g):" in out
    block = out.split("Gewicht pro Erfassungs-Jahr (g):", 1)[1]
    assert block.index("2024") < block.index("2025") < block.index("2026")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_erstellt_am_jahr_zeile(tmp_path, capsys):
    """Ohne Gewichts-Daten erscheint der Erfassungs-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpej0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", "2024-05-13 09:00:00"),
         ("OBJ_0002", "2025-04-01 14:00:00")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Erfassungs-Jahr" not in out


def test_text_ausgabe_zeigt_wert_pro_erstellt_am_monat(tmp_path, capsys):
    """Wert-pro-Erfassungs-Monat-Block listet Indoor-Erfassungs-Spitzen wertlich.

    Spiegelt wert_pro_funddatum_monat auf die Erfassungs-Achse - Januar-
    Spitzen (Boersen-Vorbereitung, Indoor-Phasen) tauchen hier sortiert auf.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpem.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Wert_CHF_roh) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2024-01-15 09:00:00", 500.0),   # Januar 500
            ("OBJ_0002", "2025-06-13 14:30:00", 200.0),   # Juni 200
            ("OBJ_0003", "2026-08-21 16:00:00", 50.0),    # August 50
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Erfassungs-Monat (CHF):" in out
    block = out.split("Wert pro Erfassungs-Monat (CHF):", 1)[1]
    assert block.index("01") < block.index("06") < block.index("08")


def test_text_ausgabe_ohne_werte_keine_wert_pro_erstellt_am_monat_zeile(tmp_path, capsys):
    """Ohne CHF-Werte erscheint der Erfassungs-Wert-Monat-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpem0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", "2024-01-15 09:00:00"),
         ("OBJ_0002", "2025-06-13 14:30:00")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Erfassungs-Monat" not in out


def test_text_ausgabe_zeigt_gewicht_pro_erstellt_am_monat(tmp_path, capsys):
    """Gewicht-pro-Erfassungs-Monat-Block listet schwerste Erfassungs-Monate."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpem.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2024-01-15 09:00:00", 500.0),
            ("OBJ_0002", "2025-06-13 14:30:00", 200.0),
            ("OBJ_0003", "2026-08-21 16:00:00", 50.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Erfassungs-Monat (g):" in out
    block = out.split("Gewicht pro Erfassungs-Monat (g):", 1)[1]
    assert block.index("01") < block.index("06") < block.index("08")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_erstellt_am_monat_zeile(tmp_path, capsys):
    """Ohne Gewichts-Daten erscheint der Erfassungs-Gewicht-Monat-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpem0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", "2024-01-15 09:00:00"),
         ("OBJ_0002", "2025-06-13 14:30:00")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Erfassungs-Monat" not in out


def test_text_ausgabe_erfassungs_monat_unter_funddatum_monat(tmp_path, capsys):
    """Erfassungs-Monat-Bloecke folgen direkt auf die Funddatum-Monat-Bloecke.

    Layout-Konvention: Wert/Gewicht pro Funddatum-Monat zuerst, danach das
    Erfassungs-Pendant - genau wie bei den Jahres-Bloecken.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "monat_reihenfolge.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, erstellt_am, Wert_CHF_roh, "
        "Gewicht_g) VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", "2020-05-13", "2024-01-15 09:00:00", 100.0, 50.0),
            ("OBJ_0002", "2021-04-01", "2025-06-13 14:30:00", 200.0, 100.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert (out.index("Wert pro Funddatum-Monat (CHF):")
            < out.index("Gewicht pro Funddatum-Monat (g):")
            < out.index("Wert pro Erfassungs-Monat (CHF):")
            < out.index("Gewicht pro Erfassungs-Monat (g):"))


def test_text_ausgabe_erfassungs_jahr_unter_funddatum_jahr(tmp_path, capsys):
    """Erfassungs-Jahr-Bloecke folgen direkt auf die Funddatum-Jahr-Bloecke.

    Sammler-Frage "wann gefunden vs. wann erfasst" lebt von der direkten
    Nebeneinanderstellung; die Reihenfolge im Bericht spiegelt die
    Erfassungs-Achse direkt unter der Fund-Achse.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wert_reihenfolge.sqlite3"
    c = open_db(db_file)
    # Beide Achsen mit Wert+Gewicht fuellen, damit alle vier Bloecke erscheinen.
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, erstellt_am, Wert_CHF_roh, "
        "Gewicht_g) VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", "2020-05-13", "2024-05-13 09:00:00", 100.0, 50.0),
            ("OBJ_0002", "2021-04-01", "2025-04-01 14:00:00", 200.0, 100.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert (out.index("Wert pro Funddatum-Jahr (CHF):")
            < out.index("Gewicht pro Funddatum-Jahr (g):")
            < out.index("Wert pro Erfassungs-Jahr (CHF):")
            < out.index("Gewicht pro Erfassungs-Jahr (g):"))


def test_text_ausgabe_zeigt_wert_pro_funddatum_jahrzehnt(tmp_path, capsys):
    """Wert-pro-Funddatum-Jahrzehnt-Block listet die wertvollsten Dekaden absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpfd.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "1995-05-13", 1000.0),  # 1990er
            ("OBJ_0002", "2005-04-01", 250.0),   # 2000er
            ("OBJ_0003", "2015-03-01", 50.0),    # 2010er
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Funddatum-Jahrzehnt (CHF):" in out
    block = out.split("Wert pro Funddatum-Jahrzehnt (CHF):", 1)[1]
    assert block.index("1990er") < block.index("2000er") < block.index("2010er")


def test_text_ausgabe_ohne_werte_keine_wert_pro_funddatum_jahrzehnt_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpfd0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", "1995-05-13"), ("OBJ_0002", "2005-04-01")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Funddatum-Jahrzehnt" not in out


def test_text_ausgabe_zeigt_gewicht_pro_funddatum_jahrzehnt(tmp_path, capsys):
    """Gewicht-pro-Funddatum-Jahrzehnt-Block listet die schwersten Dekaden absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpfd.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "1995-05-13", 1000.0),  # 1990er
            ("OBJ_0002", "2005-04-01", 250.0),   # 2000er
            ("OBJ_0003", "2015-03-01", 50.0),    # 2010er
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Funddatum-Jahrzehnt (g):" in out
    block = out.split("Gewicht pro Funddatum-Jahrzehnt (g):", 1)[1]
    assert block.index("1990er") < block.index("2000er") < block.index("2010er")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_funddatum_jahrzehnt_zeile(tmp_path, capsys):
    """Ohne Gewichts-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpfd0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", "1995-05-13"), ("OBJ_0002", "2005-04-01")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Funddatum-Jahrzehnt" not in out


def test_text_ausgabe_zeigt_wert_pro_erstellt_am_jahrzehnt(tmp_path, capsys):
    """Wert-pro-Erfassungs-Jahrzehnt-Block listet die wertvollsten Dekaden absteigend.

    Spiegelt wert_pro_funddatum_jahrzehnt auf die Erfassungs-Achse - macht
    Migrations-Wellen (Excel-Altbestand 2020+) wertlich sichtbar.
    Sortierung absteigend nach Summe.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpeej.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Wert_CHF_roh) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2005-05-13 09:00:00", 1000.0),   # 2000er
            ("OBJ_0002", "2015-04-01 14:00:00", 250.0),    # 2010er
            ("OBJ_0003", "2025-03-01 08:00:00", 50.0),     # 2020er
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Erfassungs-Jahrzehnt (CHF):" in out
    block = out.split("Wert pro Erfassungs-Jahrzehnt (CHF):", 1)[1]
    assert block.index("2000er") < block.index("2010er") < block.index("2020er")


def test_text_ausgabe_ohne_werte_keine_wert_pro_erstellt_am_jahrzehnt_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpeej0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", "2005-05-13 09:00:00"),
         ("OBJ_0002", "2015-04-01 14:00:00")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Erfassungs-Jahrzehnt" not in out


def test_text_ausgabe_zeigt_gewicht_pro_erstellt_am_jahrzehnt(tmp_path, capsys):
    """Gewicht-pro-Erfassungs-Jahrzehnt-Block listet die schwersten Erfassungs-Dekaden absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpeej.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2005-05-13 09:00:00", 1000.0),   # 2000er
            ("OBJ_0002", "2015-04-01 14:00:00", 250.0),    # 2010er
            ("OBJ_0003", "2025-03-01 08:00:00", 50.0),     # 2020er
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Erfassungs-Jahrzehnt (g):" in out
    block = out.split("Gewicht pro Erfassungs-Jahrzehnt (g):", 1)[1]
    assert block.index("2000er") < block.index("2010er") < block.index("2020er")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_erstellt_am_jahrzehnt_zeile(tmp_path, capsys):
    """Ohne Gewichts-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpeej0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", "2005-05-13 09:00:00"),
         ("OBJ_0002", "2015-04-01 14:00:00")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Erfassungs-Jahrzehnt" not in out


def test_text_ausgabe_erstellt_am_jahrzehnt_block_folgt_auf_funddatum_jahrzehnt(tmp_path, capsys):
    """Erfassungs-Dekaden-Bloecke stehen direkt unter den Funddatum-Dekaden-Bloecken.

    Die Reihenfolge spiegelt die compute_statistics-Anordnung: erst Funddatum-
    Jahrzehnt (Fund-Achse), dann Erfassungs-Jahrzehnt (Erfassungs-Achse). Beide
    Bloecke kommen zwischen den Jahr- und den Monat-Bloecken.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "ord_jzd.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, erstellt_am, Wert_CHF_roh, Gewicht_g) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", "1995-05-13", "2005-05-13 09:00:00", 1000.0, 1000.0),
            ("OBJ_0002", "2005-04-01", "2015-04-01 14:00:00", 250.0, 250.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert (out.index("Wert pro Funddatum-Jahrzehnt (CHF):")
            < out.index("Gewicht pro Funddatum-Jahrzehnt (g):")
            < out.index("Wert pro Erfassungs-Jahrzehnt (CHF):")
            < out.index("Gewicht pro Erfassungs-Jahrzehnt (g):"))


def test_text_ausgabe_zeigt_wert_pro_funddatum_monat(tmp_path, capsys):
    """Wert-pro-Funddatum-Monat-Block listet die wertvollsten Monate absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpfm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2020-07-15", 1000.0),
            ("OBJ_0002", "2022-08-10", 250.0),
            ("OBJ_0003", "2023-12-05", 50.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Funddatum-Monat (CHF):" in out
    block = out.split("Wert pro Funddatum-Monat (CHF):", 1)[1]
    # Reihenfolge nach Summe absteigend: 07 (1000), 08 (250), 12 (50)
    assert block.index("07") < block.index("08") < block.index("12")


def test_text_ausgabe_ohne_werte_keine_wert_pro_funddatum_monat_zeile(tmp_path, capsys):
    """Ohne CHF-Werte erscheint der Monat-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpfm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", "2020-07-15"), ("OBJ_0002", "2024-08-01")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Funddatum-Monat" not in out


def test_text_ausgabe_zeigt_gewicht_pro_funddatum_monat(tmp_path, capsys):
    """Gewicht-pro-Funddatum-Monat-Block listet die schwersten Monate."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpfm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2020-07-15", 1000.0),
            ("OBJ_0002", "2022-08-10", 250.0),
            ("OBJ_0003", "2023-12-05", 50.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Funddatum-Monat (g):" in out
    block = out.split("Gewicht pro Funddatum-Monat (g):", 1)[1]
    assert block.index("07") < block.index("08") < block.index("12")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_funddatum_monat_zeile(tmp_path, capsys):
    """Ohne Gewichts-Daten erscheint der Monat-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpfm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", "2020-07-15"), ("OBJ_0002", "2024-08-01")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Funddatum-Monat" not in out


def test_text_ausgabe_zeigt_objekte_pro_kategorie(tmp_path, capsys):
    """Objekte-pro-Kategorie-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opk.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
        [
            ("OBJ_0001", "Handstueck"),
            ("OBJ_0002", "Handstueck"),
            ("OBJ_0003", "Handstueck"),
            ("OBJ_0004", "Kristall"),
            ("OBJ_0005", "Kristall"),
            ("OBJ_0006", "Geroell"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Kategorie:" in out
    # Reihenfolge absteigend: Handstueck (3), Kristall (2), Geroell (1)
    block = out.split("Objekte pro Kategorie:", 1)[1]
    assert block.index("Handstueck") < block.index("Kristall") < block.index("Geroell")


def test_text_ausgabe_ohne_kategorie_keine_zeile(tmp_path, capsys):
    """Ohne Kategorie-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opk0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Kategorie:" not in out


def test_text_ausgabe_zeigt_objekte_pro_kristallsystem(tmp_path, capsys):
    """Objekte-pro-Kristallsystem-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opks.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [
            ("OBJ_0001", "trigonal"),
            ("OBJ_0002", "trigonal"),
            ("OBJ_0003", "trigonal"),
            ("OBJ_0004", "kubisch"),
            ("OBJ_0005", "kubisch"),
            ("OBJ_0006", "hexagonal"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Kristallsystem:" in out
    # Reihenfolge absteigend: trigonal (3), kubisch (2), hexagonal (1)
    block = out.split("Objekte pro Kristallsystem:", 1)[1]
    assert block.index("trigonal") < block.index("kubisch") < block.index("hexagonal")


def test_text_ausgabe_ohne_kristallsystem_keine_zeile(tmp_path, capsys):
    """Ohne Kristallsystem-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opks0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Kristallsystem:" not in out


def test_text_ausgabe_zeigt_objekte_pro_glanz(tmp_path, capsys):
    """Objekte-pro-Glanz-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?, ?)",
        [
            ("OBJ_0001", "glasig"),
            ("OBJ_0002", "glasig"),
            ("OBJ_0003", "glasig"),
            ("OBJ_0004", "metallisch"),
            ("OBJ_0005", "metallisch"),
            ("OBJ_0006", "seidig"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Glanz:" in out
    # Reihenfolge absteigend: glasig (3), metallisch (2), seidig (1)
    block = out.split("Objekte pro Glanz:", 1)[1]
    assert block.index("glasig") < block.index("metallisch") < block.index("seidig")


def test_text_ausgabe_ohne_glanz_keine_zeile(tmp_path, capsys):
    """Ohne Glanz-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opg0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Glanz:" not in out


def test_text_ausgabe_zeigt_objekte_pro_transparenz(tmp_path, capsys):
    """Objekte-pro-Transparenz-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opt.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?, ?)",
        [
            ("OBJ_0001", "opak"),
            ("OBJ_0002", "opak"),
            ("OBJ_0003", "opak"),
            ("OBJ_0004", "durchscheinend"),
            ("OBJ_0005", "durchscheinend"),
            ("OBJ_0006", "durchsichtig"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Transparenz:" in out
    # Reihenfolge absteigend: opak (3), durchscheinend (2), durchsichtig (1)
    block = out.split("Objekte pro Transparenz:", 1)[1]
    assert block.index("opak") < block.index("durchscheinend") < block.index("durchsichtig")


def test_text_ausgabe_ohne_transparenz_keine_zeile(tmp_path, capsys):
    """Ohne Transparenz-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opt0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Transparenz:" not in out


def test_text_ausgabe_zeigt_objekte_pro_magnetismus(tmp_path, capsys):
    """Objekte-pro-Magnetismus-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [
            ("OBJ_0001", "nein"),
            ("OBJ_0002", "nein"),
            ("OBJ_0003", "nein"),
            ("OBJ_0004", "schwach"),
            ("OBJ_0005", "schwach"),
            ("OBJ_0006", "ja"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Magnetismus:" in out
    # Reihenfolge absteigend: nein (3), schwach (2), ja (1)
    block = out.split("Objekte pro Magnetismus:", 1)[1]
    assert block.index("nein") < block.index("schwach") < block.index("ja")


def test_text_ausgabe_ohne_magnetismus_keine_zeile(tmp_path, capsys):
    """Ohne Magnetismus-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Magnetismus:" not in out


def test_text_ausgabe_zeigt_objekte_pro_spaltbarkeit(tmp_path, capsys):
    """Objekte-pro-Spaltbarkeit-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opsp.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?, ?)",
        [
            ("OBJ_0001", "keine"),
            ("OBJ_0002", "keine"),
            ("OBJ_0003", "keine"),
            ("OBJ_0004", "vollkommen"),
            ("OBJ_0005", "vollkommen"),
            ("OBJ_0006", "deutlich"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Spaltbarkeit:" in out
    # Reihenfolge absteigend: keine (3), vollkommen (2), deutlich (1)
    block = out.split("Objekte pro Spaltbarkeit:", 1)[1]
    assert block.index("keine") < block.index("vollkommen") < block.index("deutlich")


def test_text_ausgabe_ohne_spaltbarkeit_keine_zeile(tmp_path, capsys):
    """Ohne Spaltbarkeit-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opsp0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Spaltbarkeit:" not in out


def test_text_ausgabe_zeigt_objekte_pro_bruch(tmp_path, capsys):
    """Objekte-pro-Bruch-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opb.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?, ?)",
        [
            ("OBJ_0001", "muschelig"),
            ("OBJ_0002", "muschelig"),
            ("OBJ_0003", "muschelig"),
            ("OBJ_0004", "uneben"),
            ("OBJ_0005", "uneben"),
            ("OBJ_0006", "faserig"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Bruch:" in out
    # Reihenfolge absteigend: muschelig (3), uneben (2), faserig (1)
    block = out.split("Objekte pro Bruch:", 1)[1]
    assert block.index("muschelig") < block.index("uneben") < block.index("faserig")


def test_text_ausgabe_ohne_bruch_keine_zeile(tmp_path, capsys):
    """Ohne Bruch-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opb0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Bruch:" not in out


def test_text_ausgabe_zeigt_objekte_pro_beste_verwendung(tmp_path, capsys):
    """Objekte-pro-Beste-Verwendung-Block zaehlt absteigend nach Anzahl."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opbv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [
            ("OBJ_0001", "Sammlung"),
            ("OBJ_0002", "Sammlung"),
            ("OBJ_0003", "Sammlung"),
            ("OBJ_0004", "Schmuck"),
            ("OBJ_0005", "Schmuck"),
            ("OBJ_0006", "Forschung"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Beste-Verwendung:" in out
    # Reihenfolge absteigend: Sammlung (3), Schmuck (2), Forschung (1)
    block = out.split("Objekte pro Beste-Verwendung:", 1)[1]
    assert block.index("Sammlung") < block.index("Schmuck") < block.index("Forschung")


def test_text_ausgabe_ohne_beste_verwendung_keine_zeile(tmp_path, capsys):
    """Ohne Beste-Verwendung-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "opbv0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Objekte pro Beste-Verwendung:" not in out


def test_text_ausgabe_zeigt_wert_pro_kategorie(tmp_path, capsys):
    """Wert-pro-Kategorie-Block summiert CHF-Felder pro Kategorie und sortiert absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpk.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Handstueck", 600.0, 400.0),   # Handstueck 1000
            ("OBJ_0002", "Kristall",   200.0, 150.0),   # Kristall    350
            ("OBJ_0003", "Geroell",     10.0, None),    # Geroell      10
            ("OBJ_0004", "Geroell",   None,  None),     # Geroell bleibt 10
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Kategorie (CHF):" in out
    # Reihenfolge absteigend nach Summe: Handstueck (1000), Kristall (350), Geroell (10)
    block = out.split("Wert pro Kategorie (CHF):", 1)[1]
    assert block.index("Handstueck") < block.index("Kristall") < block.index("Geroell")


def test_text_ausgabe_ohne_werte_keine_wert_pro_kategorie_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Kategorie-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpk0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
        [("OBJ_0001", "Handstueck"), ("OBJ_0002", "Kristall")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Kategorie" not in out


def test_text_ausgabe_zeigt_gewicht_pro_mineral(tmp_path, capsys):
    """Gewicht-pro-Mineral-Block summiert g je Mineraltyp und sortiert absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Quarz",   100.0),  # Quarz total 250
            ("OBJ_0002", "Quarz",   150.0),
            ("OBJ_0003", "Calcit",  800.0),  # Calcit total 800
            ("OBJ_0004", "Pyrit",    20.0),  # Pyrit  total  20
            ("OBJ_0005", "Pyrit",   None),   # NULL zaehlt nicht
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Mineral (g):" in out
    # Reihenfolge absteigend: Calcit (800), Quarz (250), Pyrit (20)
    block = out.split("Gewicht pro Mineral (g):", 1)[1]
    assert block.index("Calcit") < block.index("Quarz") < block.index("Pyrit")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_mineral_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Gewicht-pro-Mineral-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer) VALUES (?, ?)",
        [("OBJ_0001", "Quarz"), ("OBJ_0002", "Calcit")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Mineral" not in out


def test_text_ausgabe_zeigt_gewicht_pro_fundort(tmp_path, capsys):
    """Gewicht-pro-Fundort-Block summiert g pro Fundort und sortiert absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpf.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Davos",       100.0),  # Davos total 250
            ("OBJ_0002", "Davos",       150.0),
            ("OBJ_0003", "Zermatt",     800.0),  # Zermatt total 800
            ("OBJ_0004", "St. Gallen",   20.0),  # St. Gallen total 20
            ("OBJ_0005", "St. Gallen",  None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Fundort (g):" in out
    # Reihenfolge absteigend: Zermatt (800), Davos (250), St. Gallen (20)
    block = out.split("Gewicht pro Fundort (g):", 1)[1]
    assert block.index("Zermatt") < block.index("Davos") < block.index("St. Gallen")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_fundort_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Gewicht-pro-Fundort-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpf0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?, ?)",
        [("OBJ_0001", "Davos"), ("OBJ_0002", "Zermatt")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Fundort" not in out


def test_text_ausgabe_zeigt_gewicht_pro_kategorie(tmp_path, capsys):
    """Gewicht-pro-Kategorie-Block summiert g pro Objekt-Kategorie und sortiert absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpk.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Handstueck", 600.0),   # Handstueck 1000
            ("OBJ_0002", "Handstueck", 400.0),
            ("OBJ_0003", "Kristall",   150.0),   # Kristall   150
            ("OBJ_0004", "Geroell",     10.0),   # Geroell     10
            ("OBJ_0005", "Geroell",   None),     # NULL zaehlt nicht
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Kategorie (g):" in out
    # Reihenfolge absteigend: Handstueck (1000), Kristall (150), Geroell (10)
    block = out.split("Gewicht pro Kategorie (g):", 1)[1]
    assert block.index("Handstueck") < block.index("Kristall") < block.index("Geroell")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_kategorie_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Gewicht-pro-Kategorie-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpk0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
        [("OBJ_0001", "Handstueck"), ("OBJ_0002", "Kristall")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Kategorie" not in out


def test_text_ausgabe_zeigt_wert_pro_status(tmp_path, capsys):
    """Wert-pro-Status-Block zeigt CHF-Summen je Status (aktiv/platzhalter/archiviert)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wps.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, status, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "aktiv",       600.0, 400.0),  # aktiv 1000
            ("OBJ_0002", "archiviert",  200.0, 150.0),  # archiviert 350
            ("OBJ_0003", "platzhalter",  10.0, None),   # platzhalter 10
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Status (CHF):" in out
    block = out.split("Wert pro Status (CHF):", 1)[1]
    # Reihenfolge absteigend: aktiv (1000), archiviert (350), platzhalter (10)
    assert block.index("aktiv") < block.index("archiviert") < block.index("platzhalter")


def test_text_ausgabe_ohne_werte_keine_wert_pro_status_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Wert-pro-Status-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wps0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, status) VALUES (?, ?)",
        [("OBJ_0001", "aktiv"), ("OBJ_0002", "platzhalter")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Status" not in out


def test_text_ausgabe_zeigt_gewicht_pro_status(tmp_path, capsys):
    """Gewicht-pro-Status-Block zeigt g-Summen je Status, absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gps.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, status, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "archiviert",  800.0),
            ("OBJ_0002", "aktiv",       100.0),
            ("OBJ_0003", "aktiv",       150.0),  # aktiv total 250
            ("OBJ_0004", "platzhalter",  20.0),
            ("OBJ_0005", "platzhalter", None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Status (g):" in out
    block = out.split("Gewicht pro Status (g):", 1)[1]
    # Reihenfolge absteigend: archiviert (800), aktiv (250), platzhalter (20)
    assert block.index("archiviert") < block.index("aktiv") < block.index("platzhalter")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_status_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Gewicht-pro-Status-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gps0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, status) VALUES (?, ?)",
        [("OBJ_0001", "aktiv"), ("OBJ_0002", "platzhalter")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Status" not in out


def test_text_ausgabe_zeigt_wert_pro_kristallsystem(tmp_path, capsys):
    """Wert-pro-Kristallsystem-Block summiert CHF je Symmetrietyp, absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpks.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "kubisch",   600.0, 400.0),   # kubisch  1000
            ("OBJ_0002", "trigonal",  200.0, 150.0),   # trigonal  350
            ("OBJ_0003", "hexagonal",  10.0, None),    # hexagonal  10
            ("OBJ_0004", "hexagonal", None, None),     # bleibt 10
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Kristallsystem (CHF):" in out
    block = out.split("Wert pro Kristallsystem (CHF):", 1)[1]
    assert block.index("kubisch") < block.index("trigonal") < block.index("hexagonal")


def test_text_ausgabe_ohne_werte_keine_wert_pro_kristallsystem_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpks0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [("OBJ_0001", "trigonal"), ("OBJ_0002", "kubisch")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Kristallsystem" not in out


def test_text_ausgabe_zeigt_gewicht_pro_kristallsystem(tmp_path, capsys):
    """Gewicht-pro-Kristallsystem-Block summiert g je Symmetrietyp, absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpks.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "kubisch",   600.0),
            ("OBJ_0002", "kubisch",   400.0),  # kubisch total 1000
            ("OBJ_0003", "trigonal",  150.0),
            ("OBJ_0004", "hexagonal",  10.0),
            ("OBJ_0005", "hexagonal", None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Kristallsystem (g):" in out
    block = out.split("Gewicht pro Kristallsystem (g):", 1)[1]
    assert block.index("kubisch") < block.index("trigonal") < block.index("hexagonal")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_kristallsystem_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpks0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [("OBJ_0001", "trigonal"), ("OBJ_0002", "kubisch")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Kristallsystem" not in out


def test_text_ausgabe_zeigt_wert_pro_glanz(tmp_path, capsys):
    """Wert-pro-Glanz-Block summiert CHF je Glanztyp, absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "metallisch", 600.0, 400.0),  # metallisch 1000
            ("OBJ_0002", "glasig",     200.0, 150.0),  # glasig      350
            ("OBJ_0003", "matt",        10.0, None),   # matt         10
            ("OBJ_0004", "matt",       None,  None),   # matt bleibt  10
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Glanz (CHF):" in out
    block = out.split("Wert pro Glanz (CHF):", 1)[1]
    assert block.index("metallisch") < block.index("glasig") < block.index("matt")


def test_text_ausgabe_ohne_werte_keine_wert_pro_glanz_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Glanz-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpg0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?, ?)",
        [("OBJ_0001", "glasig"), ("OBJ_0002", "metallisch")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Glanz" not in out


def test_text_ausgabe_zeigt_gewicht_pro_glanz(tmp_path, capsys):
    """Gewicht-pro-Glanz-Block summiert g je Glanztyp, absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "matt",       600.0),
            ("OBJ_0002", "matt",       400.0),  # matt total 1000
            ("OBJ_0003", "glasig",     150.0),
            ("OBJ_0004", "metallisch",  10.0),
            ("OBJ_0005", "metallisch", None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Glanz (g):" in out
    block = out.split("Gewicht pro Glanz (g):", 1)[1]
    assert block.index("matt") < block.index("glasig") < block.index("metallisch")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_glanz_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Glanz-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpg0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?, ?)",
        [("OBJ_0001", "glasig"), ("OBJ_0002", "metallisch")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Glanz" not in out


def test_text_ausgabe_zeigt_wert_pro_transparenz(tmp_path, capsys):
    """Wert-pro-Transparenz-Block summiert CHF je Transparenz-Klasse, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpt.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "durchsichtig",   600.0, 400.0),
            ("OBJ_0002", "durchscheinend", 200.0, 150.0),
            ("OBJ_0003", "opak",            10.0, None),
            ("OBJ_0004", "opak",           None,  None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Transparenz (CHF):" in out
    block = out.split("Wert pro Transparenz (CHF):", 1)[1]
    assert (block.index("durchsichtig")
            < block.index("durchscheinend")
            < block.index("opak"))


def test_text_ausgabe_ohne_werte_keine_wert_pro_transparenz_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Transparenz-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpt0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?, ?)",
        [("OBJ_0001", "opak"), ("OBJ_0002", "durchsichtig")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Transparenz" not in out


def test_text_ausgabe_zeigt_gewicht_pro_transparenz(tmp_path, capsys):
    """Gewicht-pro-Transparenz-Block summiert g je Transparenz-Klasse, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpt.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "opak",            600.0),
            ("OBJ_0002", "opak",            400.0),  # opak total 1000
            ("OBJ_0003", "durchscheinend",  150.0),
            ("OBJ_0004", "durchsichtig",     10.0),
            ("OBJ_0005", "durchsichtig",    None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Transparenz (g):" in out
    block = out.split("Gewicht pro Transparenz (g):", 1)[1]
    assert (block.index("opak")
            < block.index("durchscheinend")
            < block.index("durchsichtig"))


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_transparenz_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Transparenz-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpt0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?, ?)",
        [("OBJ_0001", "opak"), ("OBJ_0002", "durchsichtig")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Transparenz" not in out


def test_text_ausgabe_zeigt_wert_pro_magnetismus(tmp_path, capsys):
    """Wert-pro-Magnetismus-Block summiert CHF je Eisengehalt-Typ, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "ja",      600.0, 400.0),  # ja      1000
            ("OBJ_0002", "schwach", 200.0, 150.0),  # schwach  350
            ("OBJ_0003", "nein",     10.0, None),   # nein      10
            ("OBJ_0004", "nein",    None,  None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Magnetismus (CHF):" in out
    block = out.split("Wert pro Magnetismus (CHF):", 1)[1]
    assert block.index("ja") < block.index("schwach") < block.index("nein")


def test_text_ausgabe_ohne_werte_keine_wert_pro_magnetismus_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Magnetismus-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [("OBJ_0001", "ja"), ("OBJ_0002", "nein")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Magnetismus" not in out


def test_text_ausgabe_zeigt_gewicht_pro_magnetismus(tmp_path, capsys):
    """Gewicht-pro-Magnetismus-Block summiert g je Eisengehalt-Typ, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpm.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "ja",      600.0),
            ("OBJ_0002", "ja",      400.0),  # ja total 1000
            ("OBJ_0003", "schwach", 150.0),
            ("OBJ_0004", "nein",     10.0),
            ("OBJ_0005", "nein",    None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Magnetismus (g):" in out
    block = out.split("Gewicht pro Magnetismus (g):", 1)[1]
    assert block.index("ja") < block.index("schwach") < block.index("nein")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_magnetismus_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Magnetismus-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpm0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [("OBJ_0001", "ja"), ("OBJ_0002", "nein")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Magnetismus" not in out


def test_text_ausgabe_zeigt_wert_pro_spaltbarkeit(tmp_path, capsys):
    """Wert-pro-Spaltbarkeit-Block summiert CHF je Spaltflaechen-Klasse, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpsp.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "vollkommen", 600.0, 400.0),  # vollkommen 1000
            ("OBJ_0002", "gut",        200.0, 150.0),  # gut         350
            ("OBJ_0003", "keine",       10.0, None),   # keine        10
            ("OBJ_0004", "keine",      None,  None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Spaltbarkeit (CHF):" in out
    block = out.split("Wert pro Spaltbarkeit (CHF):", 1)[1]
    assert block.index("vollkommen") < block.index("gut") < block.index("keine")


def test_text_ausgabe_ohne_werte_keine_wert_pro_spaltbarkeit_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Spaltbarkeit-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpsp0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?, ?)",
        [("OBJ_0001", "vollkommen"), ("OBJ_0002", "keine")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Spaltbarkeit" not in out


def test_text_ausgabe_zeigt_gewicht_pro_spaltbarkeit(tmp_path, capsys):
    """Gewicht-pro-Spaltbarkeit-Block summiert g je Spaltflaechen-Klasse, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpsp.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "keine",      600.0),
            ("OBJ_0002", "keine",      400.0),  # keine total 1000
            ("OBJ_0003", "gut",        150.0),
            ("OBJ_0004", "vollkommen",  10.0),
            ("OBJ_0005", "vollkommen", None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Spaltbarkeit (g):" in out
    block = out.split("Gewicht pro Spaltbarkeit (g):", 1)[1]
    assert block.index("keine") < block.index("gut") < block.index("vollkommen")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_spaltbarkeit_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Spaltbarkeit-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpsp0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?, ?)",
        [("OBJ_0001", "vollkommen"), ("OBJ_0002", "keine")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Spaltbarkeit" not in out


def test_text_ausgabe_zeigt_wert_pro_bruch(tmp_path, capsys):
    """Wert-pro-Bruch-Block summiert CHF je Bruchverhalten-Klasse, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpb.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "muschelig", 600.0, 400.0),  # muschelig 1000
            ("OBJ_0002", "uneben",    200.0, 150.0),  # uneben     350
            ("OBJ_0003", "faserig",    10.0, None),   # faserig     10
            ("OBJ_0004", "faserig",   None,  None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Bruch (CHF):" in out
    block = out.split("Wert pro Bruch (CHF):", 1)[1]
    assert block.index("muschelig") < block.index("uneben") < block.index("faserig")


def test_text_ausgabe_ohne_werte_keine_wert_pro_bruch_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Bruch-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpb0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?, ?)",
        [("OBJ_0001", "muschelig"), ("OBJ_0002", "faserig")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Bruch" not in out


def test_text_ausgabe_zeigt_gewicht_pro_bruch(tmp_path, capsys):
    """Gewicht-pro-Bruch-Block summiert g je Bruchverhalten-Klasse, absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpb.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "muschelig", 600.0),
            ("OBJ_0002", "muschelig", 400.0),  # muschelig total 1000
            ("OBJ_0003", "uneben",    150.0),
            ("OBJ_0004", "faserig",    10.0),
            ("OBJ_0005", "faserig",   None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Bruch (g):" in out
    block = out.split("Gewicht pro Bruch (g):", 1)[1]
    assert block.index("muschelig") < block.index("uneben") < block.index("faserig")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_bruch_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Bruch-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpb0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?, ?)",
        [("OBJ_0001", "muschelig"), ("OBJ_0002", "faserig")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Bruch" not in out


def test_text_ausgabe_zeigt_wert_pro_varietaet(tmp_path, capsys):
    """Wert-pro-Varietaet-Block summiert CHF je Varietaet, absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Milchquarz",   600.0, 400.0),   # Milchquarz  1000
            ("OBJ_0002", "Bergkristall", 200.0, 150.0),   # Bergkristall 350
            ("OBJ_0003", "Rauchquarz",    10.0, None),    # Rauchquarz    10
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Varietaet (CHF):" in out
    block = out.split("Wert pro Varietaet (CHF):", 1)[1]
    assert block.index("Milchquarz") < block.index("Bergkristall") < block.index("Rauchquarz")


def test_text_ausgabe_ohne_werte_keine_wert_pro_varietaet_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Wert-pro-Varietaet-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpv0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?, ?)",
        [("OBJ_0001", "Bergkristall"), ("OBJ_0002", "Milchquarz")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Varietaet" not in out


def test_text_ausgabe_zeigt_gewicht_pro_varietaet(tmp_path, capsys):
    """Gewicht-pro-Varietaet-Block summiert g je Varietaet, absteigend sortiert."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Milchquarz",   600.0),
            ("OBJ_0002", "Milchquarz",   400.0),  # Milchquarz total 1000
            ("OBJ_0003", "Bergkristall", 150.0),
            ("OBJ_0004", "Rauchquarz",    10.0),
            ("OBJ_0005", "Rauchquarz",   None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Varietaet (g):" in out
    block = out.split("Gewicht pro Varietaet (g):", 1)[1]
    assert block.index("Milchquarz") < block.index("Bergkristall") < block.index("Rauchquarz")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_varietaet_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Gewicht-pro-Varietaet-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpv0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?, ?)",
        [("OBJ_0001", "Bergkristall"), ("OBJ_0002", "Milchquarz")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Varietaet" not in out


def test_text_ausgabe_zeigt_wert_pro_gesteinsart(tmp_path, capsys):
    """Wert-pro-Gesteinsart-Block summiert CHF je petrologischer Gruppe."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Gneis",  600.0, 400.0),   # Gneis  1000
            ("OBJ_0002", "Granit", 200.0, 150.0),   # Granit  350
            ("OBJ_0003", "Basalt",  10.0, None),    # Basalt   10
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Gesteinsart (CHF):" in out
    block = out.split("Wert pro Gesteinsart (CHF):", 1)[1]
    assert block.index("Gneis") < block.index("Granit") < block.index("Basalt")


def test_text_ausgabe_ohne_werte_keine_wert_pro_gesteinsart_zeile(tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Wert-pro-Gesteinsart-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpg0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [("OBJ_0001", "Granit"), ("OBJ_0002", "Basalt")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Gesteinsart" not in out


def test_text_ausgabe_zeigt_gewicht_pro_gesteinsart(tmp_path, capsys):
    """Gewicht-pro-Gesteinsart-Block summiert g je petrologischer Gruppe."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Gneis",  600.0),
            ("OBJ_0002", "Gneis",  400.0),   # Gneis total 1000
            ("OBJ_0003", "Granit", 150.0),
            ("OBJ_0004", "Basalt",  10.0),
            ("OBJ_0005", "Basalt", None),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Gesteinsart (g):" in out
    block = out.split("Gewicht pro Gesteinsart (g):", 1)[1]
    assert block.index("Gneis") < block.index("Granit") < block.index("Basalt")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_gesteinsart_zeile(tmp_path, capsys):
    """Ohne Gewichtsdaten erscheint der Gewicht-pro-Gesteinsart-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpg0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [("OBJ_0001", "Granit"), ("OBJ_0002", "Basalt")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Gesteinsart" not in out


def test_text_ausgabe_zeigt_top_confidence_objekte(tmp_path, capsys):
    """Top-Confidence-Objekte-Block listet die zuverlaessigsten Identifikationen absteigend."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tcoc.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Name, Confidence_Prozent) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Unsicher", 30),
            ("OBJ_0002", "Solide",   75),
            ("OBJ_0003", "Sicher",   95),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Confidence-Objekte (%):" in out
    block = out.split("Top-Confidence-Objekte (%):", 1)[1]
    assert block.index("Sicher") < block.index("Solide") < block.index("Unsicher")


def test_text_ausgabe_ohne_confidence_keine_top_confidence_zeile(tmp_path, capsys):
    """Ohne Confidence-Werte erscheint der Top-Confidence-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tcoc0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Confidence-Objekte" not in out


def test_text_ausgabe_zeigt_wert_pro_beste_verwendung(tmp_path, capsys):
    """Wert-pro-Beste-Verwendung-Block summiert CHF je Verwendungs-Kategorie."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpbv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung, Wert_CHF_roh, "
        "Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Sammlung",  600.0, 400.0),   # Sammlung 1000
            ("OBJ_0002", "Schmuck",   200.0, 150.0),   # Schmuck   350
            ("OBJ_0003", "Forschung",  10.0, None),    # Forschung  10
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Beste-Verwendung (CHF):" in out
    block = out.split("Wert pro Beste-Verwendung (CHF):", 1)[1]
    assert block.index("Sammlung") < block.index("Schmuck") < block.index("Forschung")


def test_text_ausgabe_ohne_werte_keine_wert_pro_beste_verwendung_zeile(tmp_path, capsys):
    """Ohne CHF-Werte erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpbv0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [("OBJ_0001", "Schmuck"), ("OBJ_0002", "Sammlung")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Beste-Verwendung" not in out


def test_text_ausgabe_zeigt_gewicht_pro_beste_verwendung(tmp_path, capsys):
    """Gewicht-pro-Beste-Verwendung-Block summiert g je Verwendungs-Kategorie."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpbv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Industrie", 1000.0),
            ("OBJ_0002", "Sammlung",   150.0),
            ("OBJ_0003", "Schmuck",     10.0),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Beste-Verwendung (g):" in out
    block = out.split("Gewicht pro Beste-Verwendung (g):", 1)[1]
    assert block.index("Industrie") < block.index("Sammlung") < block.index("Schmuck")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_beste_verwendung_zeile(tmp_path, capsys):
    """Ohne Gewichts-Daten erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpbv0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [("OBJ_0001", "Schmuck"), ("OBJ_0002", "Sammlung")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Beste-Verwendung" not in out


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


def test_text_ausgabe_zeigt_erstellt_am_spanne(tmp_path, capsys):
    """Erfassungs-Spanne erscheint in der Text-Ausgabe, sobald gueltige erstellt_am-Stempel vorliegen.

    Spiegelt test_text_ausgabe_zeigt_funddatum_spanne auf die Erfassungs-Achse:
    voller Zeitstempel inkl. HH:MM:SS bleibt erhalten, weil erstellt_am im
    Insert-Pfad mit Sekunden-Aufloesung gesetzt wird.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "erstellt_spanne.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2023-06-01 08:00:00"),
            ("OBJ_0002", "2026-01-10 17:45:33"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Erfassungs-Spanne:" in out
    assert "2023-06-01 08:00:00" in out
    assert "2026-01-10 17:45:33" in out


def test_text_ausgabe_ohne_erstellt_am_keine_spanne_zeile(tmp_path, capsys):
    """Bei DB ohne gueltige erstellt_am-Stempel erscheint die Erfassungs-Spanne-Zeile gar nicht.

    Spiegelt test_text_ausgabe_ohne_funddatum_keine_spanne_zeile: leere/NULL/
    kaputte Stempel fallen aus der Spanne, die Zeile wird nicht ausgegeben.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "erstellt_leer.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", None), ("OBJ_0002", ""), ("OBJ_0003", "kaputt")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Erfassungs-Spanne:" not in out


def test_text_ausgabe_zeigt_geaendert_am_spanne(tmp_path, capsys):
    """Aenderungs-Spanne erscheint, sobald gueltige geaendert_am-Stempel vorliegen.

    Vervollstaendigt das Trio der Spanne-Zeilen (Funddatum / Erfassung /
    Aenderung) in der Text-Ausgabe.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "geaendert_spanne.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2023-12-01 09:00:00"),
            ("OBJ_0002", "2026-06-22 14:00:55"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Aenderungs-Spanne:" in out
    assert "2023-12-01 09:00:00" in out
    assert "2026-06-22 14:00:55" in out


def test_text_ausgabe_ohne_geaendert_am_keine_spanne_zeile(tmp_path, capsys):
    """Bei DB ohne gueltige geaendert_am-Stempel erscheint die Aenderungs-Spanne-Zeile gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "geaendert_leer.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [("OBJ_0001", None), ("OBJ_0002", ""), ("OBJ_0003", "kaputt")],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Aenderungs-Spanne:" not in out


def test_json_ausgabe(migrated_db, capsys):
    exit_code = main(["--db", str(migrated_db), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["objekte_total"] == 546
    assert payload["bilder_total"] == 63
    assert payload["aliase_total"] == 54
    assert "by_mineral" in payload
    assert "by_varietaet" in payload
    assert "by_gesteinsart" in payload
    # Buckets sind in der JSON-Form enthalten (Dashboard/Reports lesen das hier)
    assert "confidence_buckets" in payload
    assert set(payload["confidence_buckets"]) == {"ohne", "0-24", "25-49", "50-74", "75-100"}


def test_text_ausgabe_zeigt_top_varietaeten(tmp_path, capsys):
    """Top-Varietaeten-Block erscheint, sobald Varietaet-Werte da sind."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tv.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?, ?)",
        [
            ("OBJ_0001", "Bergkristall"),
            ("OBJ_0002", "Bergkristall"),
            ("OBJ_0003", "Milchquarz"),
            ("OBJ_0004", "Rauchquarz"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Varietaeten:" in out
    block = out.split("Top-Varietaeten:", 1)[1]
    # Bergkristall fuehrt (2 Objekte) vor Milchquarz/Rauchquarz (je 1)
    assert block.index("Bergkristall") < block.index("Milchquarz")
    assert block.index("Bergkristall") < block.index("Rauchquarz")


def test_text_ausgabe_ohne_varietaet_keine_zeile(tmp_path, capsys):
    """Ohne Varietaet-Eintraege erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tv0.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Varietaeten" not in out


def test_text_ausgabe_zeigt_top_gesteinsarten(tmp_path, capsys):
    """Top-Gesteinsarten-Block erscheint, sobald Gesteinsart-Werte da sind."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [
            ("OBJ_0001", "Granit"),
            ("OBJ_0002", "Granit"),
            ("OBJ_0003", "Granit"),
            ("OBJ_0004", "Gneis"),
            ("OBJ_0005", "Basalt"),
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Gesteinsarten:" in out
    block = out.split("Top-Gesteinsarten:", 1)[1]
    # Granit fuehrt (3 Objekte) vor Gneis/Basalt (je 1)
    assert block.index("Granit") < block.index("Gneis")
    assert block.index("Granit") < block.index("Basalt")


def test_text_ausgabe_ohne_gesteinsart_keine_zeile(tmp_path, capsys):
    """Ohne Gesteinsart-Eintraege erscheint der Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "tg0.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Top-Gesteinsarten" not in out


def test_text_ausgabe_zeigt_wert_pro_seltenheit_global(tmp_path, capsys):
    """Wert-pro-Seltenheit-Block summiert CHF je Rarity-Bucket, absteigend.

    Komplementaer zum Anzahl-Block ``Seltenheit global (1..10)``: dort die
    Bestand-Verteilung, hier der Wert-Schwerpunkt - typisch konzentriert
    sich der Wert auf die oberen Stufen (>=8) waehrend die Masse der Stuecke
    in den haeufigen Stufen (<=3) liegt.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpsg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10, "
        "Wert_CHF_roh, Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 9, 1500.0, 500.0),   # Stufe 9: 2000
            ("OBJ_0002", 5, 400.0, None),     # Stufe 5: 400
            ("OBJ_0003", 1, 50.0, None),      # Stufe 1: 50
            ("OBJ_0004", 1, 30.0, None),      # +30 -> 80
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Seltenheit global (CHF):" in out
    block = out.split("Wert pro Seltenheit global (CHF):", 1)[1]
    # Reihenfolge absteigend nach Wertsumme: 9 (2000) > 5 (400) > 1 (80)
    assert block.index("9") < block.index("5") < block.index("1")


def test_text_ausgabe_ohne_werte_keine_wert_pro_seltenheit_global_zeile(
        tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Rarity-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpsg0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?, ?)",
        [("OBJ_0001", 5), ("OBJ_0002", 8)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Seltenheit global" not in out


def test_text_ausgabe_zeigt_gewicht_pro_seltenheit_global(tmp_path, capsys):
    """Gewicht-pro-Seltenheit-Block summiert g je Rarity-Bucket, absteigend.

    Spiegelbild zu Wert-pro-Seltenheit: die Sammlungsmasse liegt typisch in
    den haeufigen Stufen (<=3), waehrend Rarit?ten (>=8) leicht bleiben.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpsg.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10, Gewicht_g) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 1, 5000.0),    # Stufe 1: 5000
            ("OBJ_0002", 1, 3000.0),    # +3000 -> 8000
            ("OBJ_0003", 5, 200.0),     # Stufe 5: 200
            ("OBJ_0004", 9, 25.0),      # Stufe 9: 25
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Seltenheit global (g):" in out
    block = out.split("Gewicht pro Seltenheit global (g):", 1)[1]
    # Reihenfolge absteigend nach Gewichtsumme: 1 (8000) > 5 (200) > 9 (25)
    assert block.index("1") < block.index("5") < block.index("9")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_seltenheit_global_zeile(
        tmp_path, capsys):
    """Ohne Gewichts-Eintraege erscheint der Rarity-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpsg0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?, ?)",
        [("OBJ_0001", 5), ("OBJ_0002", 8)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Seltenheit global" not in out


def test_text_ausgabe_zeigt_wert_pro_seltenheit_fundort(tmp_path, capsys):
    """Standort-Rarity-Wert-Block: spiegelt wert_pro_seltenheit_global im CLI.

    Komplementaer zu ``Wert pro Seltenheit global``: lokale Spitze und globale
    Spitze fallen nicht immer zusammen; der Block zeigt den lokalen Wert-
    Schwerpunkt.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpsf.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10, "
        "Wert_CHF_roh, Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 8, 1200.0, 300.0),   # Stufe 8: 1500
            ("OBJ_0002", 4, 200.0, None),     # Stufe 4: 200
            ("OBJ_0003", 2, 60.0, None),      # Stufe 2: 60
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Seltenheit Fundort (CHF):" in out
    block = out.split("Wert pro Seltenheit Fundort (CHF):", 1)[1]
    assert block.index("8") < block.index("4") < block.index("2")


def test_text_ausgabe_ohne_werte_keine_wert_pro_seltenheit_fundort_zeile(
        tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Standort-Rarity-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpsf0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?, ?)",
        [("OBJ_0001", 5), ("OBJ_0002", 8)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Seltenheit Fundort" not in out


def test_text_ausgabe_zeigt_gewicht_pro_seltenheit_fundort(tmp_path, capsys):
    """Standort-Rarity-Gewicht-Block: spiegelt gewicht_pro_seltenheit_global im CLI."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpsf.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10, Gewicht_g) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 2, 3000.0),
            ("OBJ_0002", 2, 2000.0),    # Stufe 2: 5000
            ("OBJ_0003", 5, 100.0),     # Stufe 5: 100
            ("OBJ_0004", 9, 20.0),      # Stufe 9: 20
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Seltenheit Fundort (g):" in out
    block = out.split("Gewicht pro Seltenheit Fundort (g):", 1)[1]
    assert block.index("2") < block.index("5") < block.index("9")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_seltenheit_fundort_zeile(
        tmp_path, capsys):
    """Ohne Gewichts-Eintraege erscheint der Standort-Rarity-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpsf0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?, ?)",
        [("OBJ_0001", 5), ("OBJ_0002", 8)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Seltenheit Fundort" not in out


def test_text_ausgabe_zeigt_wert_pro_nachfrage(tmp_path, capsys):
    """Marktnachfrage-Wert-Block: spiegelt seltenheit-Bloecke im CLI auf der Demand-Skala.

    Komplementaer zu ``Wert pro Seltenheit global``: zeigt nicht Rarit?ts-,
    sondern Verkaufs-Druck-Schwerpunkt.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpn.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10, "
        "Wert_CHF_roh, Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 9, 1500.0, 500.0),   # Stufe 9: 2000
            ("OBJ_0002", 5, 400.0, None),     # Stufe 5: 400
            ("OBJ_0003", 1, 80.0, None),      # Stufe 1: 80
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Nachfrage (CHF):" in out
    block = out.split("Wert pro Nachfrage (CHF):", 1)[1]
    # Reihenfolge absteigend nach Wertsumme: 9 (2000) > 5 (400) > 1 (80)
    assert block.index("9") < block.index("5") < block.index("1")


def test_text_ausgabe_ohne_werte_keine_wert_pro_nachfrage_zeile(
        tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Nachfrage-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpn0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?, ?)",
        [("OBJ_0001", 5), ("OBJ_0002", 8)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Nachfrage" not in out


def test_text_ausgabe_zeigt_gewicht_pro_nachfrage(tmp_path, capsys):
    """Marktnachfrage-Gewicht-Block: spiegelt seltenheit-Gewichts-Bloecke im CLI."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpn.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10, Gewicht_g) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 2, 4000.0),
            ("OBJ_0002", 2, 1000.0),    # Stufe 2: 5000
            ("OBJ_0003", 5, 150.0),     # Stufe 5: 150
            ("OBJ_0004", 9, 25.0),      # Stufe 9: 25
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Nachfrage (g):" in out
    block = out.split("Gewicht pro Nachfrage (g):", 1)[1]
    assert block.index("2") < block.index("5") < block.index("9")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_nachfrage_zeile(
        tmp_path, capsys):
    """Ohne Gewichts-Eintraege erscheint der Nachfrage-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpn0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?, ?)",
        [("OBJ_0001", 5), ("OBJ_0002", 8)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Nachfrage" not in out


def test_text_ausgabe_zeigt_wert_pro_confidence_bucket(tmp_path, capsys):
    """Confidence-Wert-Block: spiegelt confidence_buckets im CLI auf die Wert-Achse.

    Reihenfolge absteigend nach Wert-Summe; 'ohne'-Bucket (NULL Confidence)
    mit hohem Wert taucht ganz oben auf - das sind die wichtigsten naechsten
    Pruefkandidaten vor der Pruefempfehlungs-Abarbeitung.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpcb.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, Wert_CHF_roh) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 90, 2000.0),     # 75-100: 2000
            ("OBJ_0002", None, 800.0),    # ohne:   800
            ("OBJ_0003", 30, 150.0),      # 25-49:  150
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Confidence (CHF):" in out
    block = out.split("Wert pro Confidence (CHF):", 1)[1]
    # Reihenfolge absteigend: 75-100 (2000) > ohne (800) > 25-49 (150)
    assert block.index("75-100") < block.index("ohne") < block.index("25-49")


def test_text_ausgabe_ohne_werte_keine_wert_pro_confidence_bucket_zeile(
        tmp_path, capsys):
    """Ohne CHF-Wertfelder erscheint der Confidence-Wert-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "wpcb0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 50), ("OBJ_0002", 80)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Wert pro Confidence" not in out


def test_text_ausgabe_zeigt_gewicht_pro_confidence_bucket(tmp_path, capsys):
    """Confidence-Gewicht-Block: spiegelt wert_pro_confidence_bucket im CLI auf Masse.

    Typisch sitzt die Masse im 'ohne'-Bucket (schwere Geroellstuecke ohne
    KI-Analyse), waehrend sicher bestimmte Kristalle leicht bleiben.
    """
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpcb.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, Gewicht_g) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", None, 5000.0),   # ohne:   5000
            ("OBJ_0002", 60, 250.0),      # 50-74:  250
            ("OBJ_0003", 90, 30.0),       # 75-100: 30
        ],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Confidence (g):" in out
    block = out.split("Gewicht pro Confidence (g):", 1)[1]
    assert block.index("ohne") < block.index("50-74") < block.index("75-100")


def test_text_ausgabe_ohne_gewicht_keine_gewicht_pro_confidence_bucket_zeile(
        tmp_path, capsys):
    """Ohne Gewichts-Eintraege erscheint der Confidence-Gewicht-Block gar nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "gpcb0.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 50), ("OBJ_0002", 80)],
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Gewicht pro Confidence" not in out


def test_top_flag_steuert_listenlaenge(tmp_path, capsys):
    """--top N begrenzt sowohl by_mineral als auch top_wert_objekte gemeinsam."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "top.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Mineral_{i:02d}", float(i)) for i in range(1, 16)],
    )
    c.commit()
    c.close()
    # --top 3: Top-Listen enthalten nur 3 Eintraege
    main(["--db", str(db_file), "--top", "3"])
    out = capsys.readouterr().out
    # Top-Wertobjekt: nur die drei groessten (15, 14, 13)
    assert "OBJ_0015" in out
    assert "OBJ_0014" in out
    assert "OBJ_0013" in out
    # Vierter Eintrag (OBJ_0012, Wert 12) darf nicht erscheinen
    assert "OBJ_0012" not in out


def test_top_flag_ungueltig_exit_2(tmp_path, capsys):
    """--top 0 oder negativ ist ungueltig (mind. 1 Eintrag pro Liste)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "x.sqlite3"
    open_db(db_file).close()
    exit_code = main(["--db", str(db_file), "--top", "0"])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "--top" in err


def test_fehlende_db_exit_2(tmp_path, capsys):
    exit_code = main(["--db", str(tmp_path / "fehlt.sqlite3")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err


def test_text_ausgabe_zeigt_nachfrage_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Nachfrage-Quote direkt unter Seltenheit Fundort
    auf und schliesst die Coverage-Trias der drei 1..10-Markt-/Bewertungs-
    Skalen aus dem Feldwoerterbuch ab. Symmetrisch zum CLI-Layout der beiden
    Seltenheits-Quoten - alle drei sind ordinale 1..10-Skalen mit definiertem
    Wertebereich und teilen denselben out-of-range-Ausschluss (Integrity
    meldet separat). Typisch niedrigste Quote der drei Skalen in privaten
    Sammler-Bestaenden, weil die Marktnachfrage aktives Marktbeobachtungs-
    Wissen erfordert (Auktions-Ergebnisse, Boersenpreise)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "nach_q.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?,?)",
        [("OBJ_0001", 1), ("OBJ_0002", 10),
         ("OBJ_0003", None), ("OBJ_0004", 11)],  # 11 = out-of-range, ignoriert
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Nachfrage:" in out
    # 2 von 4 Objekten haben gueltige Marktnachfrage-Werte (1 und 10); 11 ist
    # out-of-range, None nicht erfasst -> 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_seltenheit_fundort_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Seltenheit-Fundort-Quote direkt unter Seltenheit
    global auf - beide gehoeren zur ordinalen 1..10-Rarity-Achse mit
    definiertem Wertebereich und teilen denselben out-of-range-Ausschluss
    (Integrity meldet separat). Spiegelt das CLI-Layout der globalen Rarity-
    Coverage auf die Standort-Achse; die Differenz beider Quoten beziffert die
    typische Pflege-Asymmetrie zwischen Markt-Sicht (globale Skala, aus
    Mineraldatenbanken ableitbar) und lokalem Fundgebiets-Wissen (Fundort-
    Skala, setzt eigene Touren oder Vereins-Berichte voraus)."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "selt_fo_q.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?,?)",
        [("OBJ_0001", 2), ("OBJ_0002", 7),
         ("OBJ_0003", None), ("OBJ_0004", 0)],  # 0 = out-of-range, ignoriert
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Seltenheit Fundort:" in out
    # 2 von 4 Objekten haben gueltige Fundort-Rarity-Werte (2 und 7); 0 ist
    # out-of-range, None nicht erfasst -> 50.0 %
    assert "50.0 %" in out


def test_text_ausgabe_zeigt_seltenheit_global_quote(tmp_path, capsys):
    """Coverage-Block fuehrt Seltenheit-global-Quote direkt unter Confidence
    auf - beide gehoeren zur Bestimmungs-/Bewertungs-Qualitaets-Achse mit
    definiertem Wertebereich (Confidence 0..100, Seltenheit_global 1..10) und
    schliessen out-of-range-Werte in der Coverage symmetrisch aus (Integrity
    meldet die separat). Komplementaer zu by_seltenheit_global/wert_pro_/
    gewicht_pro_seltenheit_global (innere Verteilung der gepflegten Stuecke);
    hier die Coverage-Sicht ueber den Gesamtbestand. Symmetrische CLI-
    Sichtbarkeit fuer das Datenpflege-Dashboard."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "selt.sqlite3"
    c = open_db(db_file)
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?,?)",
        [("OBJ_0001", 3), ("OBJ_0002", 8),
         ("OBJ_0003", None), ("OBJ_0004", 11)],  # 11 = out-of-range, ignoriert
    )
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Coverage:" in out
    assert "Seltenheit global:" in out
    # 2 von 4 Objekten haben gueltige Rarity-Werte (3 und 8); 11 ist
    # out-of-range, None nicht erfasst → 50.0 %
    assert "50.0 %" in out
