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
    """Ohne Seltenheits-Eintraege erscheint der Rarity-Block nicht."""
    from stonebook.db.database import open_db
    db_file = tmp_path / "selt0.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.close()
    main(["--db", str(db_file)])
    out = capsys.readouterr().out
    assert "Seltenheit global" not in out
    assert "Seltenheit Fundort" not in out
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
