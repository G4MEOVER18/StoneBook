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
