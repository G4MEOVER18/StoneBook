"""Aggregierte Kennzahlen über die gesamte migrierte DB."""
from pathlib import Path

import pytest

from stonebook.db.database import connect
from stonebook.db.stats import compute_statistics
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    c = connect(db_file)
    yield c
    c.close()


def test_grundkennzahlen(conn):
    st = compute_statistics(conn)
    assert st.objekte_total == 546
    assert st.bilder_total == 63
    assert st.aliase_total == 54
    assert st.objekte_aktiv + st.objekte_platzhalter + st.objekte_archiviert == 546
    assert st.objekte_aktiv > 0


def test_by_status_summe_passt(conn):
    st = compute_statistics(conn)
    assert sum(st.by_status.values()) == st.objekte_total


def test_by_mineral_enthaelt_quarz(conn):
    st = compute_statistics(conn)
    # OBJ_0043 ist Quarz — mind. ein Quarz-Eintrag muss auftauchen
    assert any("Quarz" in k for k in st.by_mineral)


def test_top_fundorte_limit(conn):
    st = compute_statistics(conn, top_fundorte=3)
    assert len(st.by_fundort) <= 3


def test_objekte_mit_bildern(conn):
    st = compute_statistics(conn)
    # Mindestens OBJ_0001 hat Bilder
    assert st.objekte_mit_bildern >= 1
    assert st.objekte_mit_bildern <= st.objekte_total


def test_wert_und_gewicht_summen_nicht_negativ(conn):
    st = compute_statistics(conn)
    assert st.wert_summe_chf >= 0.0
    assert st.gewicht_summe_g >= 41.0  # OBJ_0043 allein wiegt 41g


def test_as_dict_serialisierbar(conn):
    import json

    st = compute_statistics(conn)
    d = st.as_dict()
    json.dumps(d, ensure_ascii=False)  # darf nicht crashen
    assert d["objekte_total"] == 546


def test_wert_kennzahlen_aus_seed_db(tmp_path):
    """Werte-Aggregate gegen eine kleine, kontrollierte DB."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "seed.sqlite3")
    # OBJ_0001: roh 100 + poliert 200 = 300
    # OBJ_0002: roh 50, Schmuck 50, wiss. Wert 400 = 500
    # OBJ_0003: alles NULL → kein Wert
    c.executemany(
        "INSERT INTO objects (obj_id, Name, Wert_CHF_roh, Wert_CHF_poliert, "
        "Wert_CHF_Schmuck, Wissenschaftlicher_Wert_CHF) VALUES (?,?,?,?,?,?)",
        [
            ("OBJ_0001", "Erstes", 100.0, 200.0, None, None),
            ("OBJ_0002", "Zweites", 50.0, None, 50.0, 400.0),
            ("OBJ_0003", "Drittes", None, None, None, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 2
    assert st.wert_max_chf == 500.0
    assert st.wert_summe_chf == 800.0
    assert st.wert_durchschnitt_chf == 400.0
    # Top-Wert-Liste sortiert nach Wert absteigend
    ids = [oid for oid, _, _ in st.top_wert_objekte]
    werte = [w for _, _, w in st.top_wert_objekte]
    assert ids == ["OBJ_0002", "OBJ_0001"]
    assert werte == [500.0, 300.0]
    c.close()


def test_wert_median_ungerade_anzahl(tmp_path):
    """Median bei 3 Werten = mittlerer Wert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "med.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 10.0), ("OBJ_0002", 100.0), ("OBJ_0003", 1000.0)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_median_chf == 100.0
    c.close()


def test_wert_median_gerade_anzahl(tmp_path):
    """Median bei 4 Werten = Mittel der beiden mittleren."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "med2.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 10.0), ("OBJ_0002", 20.0),
         ("OBJ_0003", 30.0), ("OBJ_0004", 40.0)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_median_chf == 25.0  # (20+30)/2
    c.close()


def test_wert_median_ignoriert_nullwerte(tmp_path):
    """Objekte ohne Wert (alles NULL) zaehlen nicht in den Median."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "med3.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 10.0), ("OBJ_0002", 50.0),
         ("OBJ_0003", None), ("OBJ_0004", None)],
    )
    c.commit()
    st = compute_statistics(c)
    # Nur 10 und 50 zaehlen; Median = (10+50)/2 = 30
    assert st.wert_median_chf == 30.0
    assert st.objekte_mit_wert == 2
    c.close()


def test_wert_median_leere_db(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_median_chf == 0.0
    c.close()


def test_top_wert_limit_respektiert(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "limit.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?,?)",
        [(f"OBJ_{i:04d}", float(i)) for i in range(1, 21)],
    )
    c.commit()
    st = compute_statistics(c, top_wert=3)
    assert len(st.top_wert_objekte) == 3
    werte = [w for _, _, w in st.top_wert_objekte]
    assert werte == [20.0, 19.0, 18.0]
    c.close()


def test_by_funddatum_jahr_aus_seed_db(tmp_path):
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "jahr.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2021-05-13"),
            ("OBJ_0002", "2021-08-01"),
            ("OBJ_0003", "2023-01-01"),
            ("OBJ_0004", "2019-11-30"),
            ("OBJ_0005", ""),          # leer
            ("OBJ_0006", None),        # NULL
            ("OBJ_0007", "Fruehling"), # ungueltig - kein Jahres-Praefix
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_funddatum_jahr == {"2019": 1, "2021": 2, "2023": 1}
    c.close()


def test_by_funddatum_jahr_limit(tmp_path):
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "jahr_limit.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2018-01-01"),
            ("OBJ_0002", "2020-01-01"),
            ("OBJ_0003", "2020-06-01"),
            ("OBJ_0004", "2021-01-01"),
            ("OBJ_0005", "2021-03-01"),
            ("OBJ_0006", "2021-12-01"),
        ],
    )
    c.commit()
    st = compute_statistics(c, top_jahre=2)
    # Top 2 nach Haeufigkeit: 2021 (3) und 2020 (2); aufsteigend nach Jahr ausgegeben
    assert list(st.by_funddatum_jahr.items()) == [("2020", 2), ("2021", 3)]
    c.close()


def test_by_funddatum_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_funddatum_jahr == {}
    c.close()


def test_durchschnitt_confidence_und_wert_roh(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, Wert_CHF_roh, "
        "Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 80, 100.0, 50.0),
            ("OBJ_0002", 60, 200.0, None),
            ("OBJ_0003", None, None, 999.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.durchschnitt_confidence_prozent == 70.0   # (80+60)/2, NULL ignoriert
    assert st.wert_roh_summe_chf == 300.0               # nur Wert_CHF_roh
    assert st.wert_summe_chf == 1349.0                  # alle Wertfelder
    c.close()


def test_durchschnitt_confidence_ohne_werte(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.durchschnitt_confidence_prozent is None
    assert st.wert_roh_summe_chf == 0.0


def test_wert_pro_mineral_aus_seed_db(tmp_path):
    """Wertsumme pro Hauptmineral, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Wert_CHF_roh, "
        "Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Quarz", 100.0, 200.0),     # 300
            ("OBJ_0002", "Quarz", 50.0, None),       # 50 → Quarz total 350
            ("OBJ_0003", "Calcit", 1000.0, None),    # 1000
            ("OBJ_0004", "Calcit", None, None),      # 0
            ("OBJ_0005", "Achat", 10.0, None),       # 10
            ("OBJ_0006", "", 999.0, None),           # leeres Mineral → ignoriert
            ("OBJ_0007", None, 999.0, None),         # NULL Mineral → ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_mineral == [
        ("Calcit", 1000.0),
        ("Quarz", 350.0),
        ("Achat", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_mineral"] == [
        ("Calcit", 1000.0), ("Quarz", 350.0), ("Achat", 10.0),
    ]
    c.close()


def test_wert_pro_mineral_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpm_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Min{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_mineral=3)
    assert len(st.wert_pro_mineral) == 3
    werte = [w for _, w in st.wert_pro_mineral]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_mineral_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_mineral == []
    c.close()


def test_by_kristallsystem_aus_seed_db(tmp_path):
    """Verteilung nach Kristallsystem ignoriert leere Eintraege."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "kris.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [
            ("OBJ_0001", "trigonal"),
            ("OBJ_0002", "trigonal"),
            ("OBJ_0003", "kubisch"),
            ("OBJ_0004", "hexagonal"),
            ("OBJ_0005", ""),
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_kristallsystem == {"trigonal": 2, "hexagonal": 1, "kubisch": 1}
    assert st.as_dict()["by_kristallsystem"] == {"trigonal": 2, "hexagonal": 1, "kubisch": 1}
    c.close()


def test_by_kristallsystem_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_kristallsystem == {}
    c.close()


def test_bilder_by_kategorie_aus_migrierter_db(conn):
    st = compute_statistics(conn)
    # Migrierte DB hat 63 Bilder verteilt auf Kategorien
    assert sum(st.bilder_by_kategorie.values()) == st.bilder_total == 63
    # OBJ_0001 hat u.a. Kamera, Mikroskop, UV395, Sonderaufnahmen
    assert {"Kamera", "Mikroskop", "UV395", "Sonderaufnahmen"} <= set(st.bilder_by_kategorie)


def test_bilder_by_kategorie_seed(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bilder.sqlite3")
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
    st = compute_statistics(c)
    assert st.bilder_by_kategorie == {"Kamera": 2, "Mikroskop": 1, "UV365": 1}
    c.close()


def test_bilder_by_kategorie_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.bilder_by_kategorie == {}
    c.close()


def test_wert_kennzahlen_bei_leerer_db(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.objekte_total == 0
    assert st.wert_max_chf == 0.0
    assert st.wert_durchschnitt_chf == 0.0
    assert st.objekte_mit_wert == 0
    assert st.top_wert_objekte == []
    c.close()


def test_quoten_aus_seed_db(tmp_path):
    """Coverage-Quoten = Anteil der Objekte mit Bildern/Funddatum/Wert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "q.sqlite3")
    # 4 Objekte: zwei mit Wert (50%), eines mit Funddatum (25%), zwei mit Bildern (50%)
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
        [
            ("OBJ_0001", "Kamera", "a.jpg"),
            ("OBJ_0002", "Kamera", "b.jpg"),
            ("OBJ_0002", "Mikroskop", "c.jpg"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.quote_mit_bildern_prozent == 50.0
    assert st.quote_mit_funddatum_prozent == 25.0
    assert st.quote_mit_wert_prozent == 50.0
    d = st.as_dict()
    assert d["quote_mit_bildern_prozent"] == 50.0
    assert d["quote_mit_funddatum_prozent"] == 25.0
    assert d["quote_mit_wert_prozent"] == 50.0
    c.close()


def test_quoten_bei_leerer_db_sind_none(tmp_path):
    """Bei 0 Objekten gibt es keine Quote (nicht 0%, sondern undefiniert)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_bildern_prozent is None
    assert st.quote_mit_funddatum_prozent is None
    assert st.quote_mit_wert_prozent is None
    d = st.as_dict()
    assert d["quote_mit_bildern_prozent"] is None
    c.close()


def test_mineral_und_fundort_arten_total(tmp_path):
    """mineral_arten_total/fundorte_total zaehlen distinct Werte (unabhaengig von Top-N)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "div.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Fundort) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Quarz", "Davos"),
            ("OBJ_0002", "Quarz", "Davos"),
            ("OBJ_0003", "Calcit", "Zermatt"),
            ("OBJ_0004", "Achat", ""),         # leerer Fundort → ignoriert
            ("OBJ_0005", "", "Andermatt"),     # leeres Mineral → ignoriert
            ("OBJ_0006", None, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mineral_arten_total == 3   # Quarz, Calcit, Achat
    assert st.fundorte_total == 3        # Davos, Zermatt, Andermatt
    d = st.as_dict()
    assert d["mineral_arten_total"] == 3
    assert d["fundorte_total"] == 3
    c.close()


def test_mineral_arten_total_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.mineral_arten_total == 0
    assert st.fundorte_total == 0
    c.close()


def test_wert_pro_fundort_aus_seed_db(tmp_path):
    """Wertsumme pro Fundort, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort, Wert_CHF_roh) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Davos", 100.0),
            ("OBJ_0002", "Davos", 50.0),       # Davos total 150
            ("OBJ_0003", "Zermatt", 1000.0),   # Zermatt total 1000
            ("OBJ_0004", "Zermatt", None),     # NULL → 0
            ("OBJ_0005", "Andermatt", 10.0),
            ("OBJ_0006", "", 999.0),           # leerer Fundort → ignoriert
            ("OBJ_0007", None, 999.0),         # NULL Fundort → ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_fundort == [
        ("Zermatt", 1000.0),
        ("Davos", 150.0),
        ("Andermatt", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_fundort"] == [
        ("Zermatt", 1000.0), ("Davos", 150.0), ("Andermatt", 10.0),
    ]
    c.close()


def test_wert_pro_fundort_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpf_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Ort{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_fundort=3)
    assert len(st.wert_pro_fundort) == 3
    w = [v for _, v in st.wert_pro_fundort]
    assert w == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_fundort_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_fundort == []
    c.close()


def test_gewicht_pro_mineral_aus_seed_db(tmp_path):
    """Gewichtsumme pro Hauptmineral, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Quarz", 100.0),
            ("OBJ_0002", "Quarz", 50.0),       # Quarz total 150
            ("OBJ_0003", "Calcit", 1000.0),    # Calcit total 1000
            ("OBJ_0004", "Calcit", None),      # NULL → ignoriert
            ("OBJ_0005", "Achat", 10.0),
            ("OBJ_0006", "", 999.0),           # leeres Mineral → ignoriert
            ("OBJ_0007", None, 999.0),         # NULL Mineral → ignoriert
            ("OBJ_0008", "Pyrit", 0.0),        # 0 → keine echte Masse
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_mineral == [
        ("Calcit", 1000.0),
        ("Quarz", 150.0),
        ("Achat", 10.0),
    ]
    d = st.as_dict()
    assert d["gewicht_pro_mineral"] == [
        ("Calcit", 1000.0), ("Quarz", 150.0), ("Achat", 10.0),
    ]
    c.close()


def test_gewicht_pro_mineral_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpm_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Min{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_mineral=3)
    assert len(st.gewicht_pro_mineral) == 3
    g = [v for _, v in st.gewicht_pro_mineral]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_mineral_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_mineral == []
    c.close()


def test_gewicht_kennzahlen_aus_seed_db(tmp_path):
    """Avg/Median/Max ueber Gewicht_g; NULL und 0 zaehlen nicht mit."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [
            ("OBJ_0001", 10.0),
            ("OBJ_0002", 50.0),
            ("OBJ_0003", 200.0),
            ("OBJ_0004", None),  # ignoriert
            ("OBJ_0005", 0.0),   # ignoriert (kein echtes Gewicht)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_gewicht == 3
    assert st.gewicht_summe_g == 260.0
    assert st.gewicht_max_g == 200.0
    assert st.gewicht_median_g == 50.0           # mittlerer von [10, 50, 200]
    assert st.gewicht_durchschnitt_g == pytest.approx(260.0 / 3)
    d = st.as_dict()
    assert d["objekte_mit_gewicht"] == 3
    assert d["gewicht_max_g"] == 200.0
    assert d["gewicht_median_g"] == 50.0
    c.close()


def test_gewicht_median_gerade_anzahl(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g2.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_0001", 10.0), ("OBJ_0002", 20.0),
         ("OBJ_0003", 30.0), ("OBJ_0004", 40.0)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_median_g == 25.0           # (20+30)/2
    c.close()


def test_gewicht_kennzahlen_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.objekte_mit_gewicht == 0
    assert st.gewicht_max_g == 0.0
    assert st.gewicht_median_g == 0.0
    assert st.gewicht_durchschnitt_g == 0.0
    c.close()


def test_quoten_auf_migrierter_db_plausibel(conn):
    st = compute_statistics(conn)
    # 546 Objekte, einige mit Bildern → Quote zwischen 0 und 100, Rundung 1 Stelle
    assert 0.0 < st.quote_mit_bildern_prozent <= 100.0
    # Migrierte DB hat kein Funddatum gesetzt
    assert st.quote_mit_funddatum_prozent == 0.0
