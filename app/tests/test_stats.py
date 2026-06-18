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


def test_by_funddatum_jahrzehnt_aus_seed_db(tmp_path):
    """Dekaden-Histogramm aggregiert die Jahre auf 10er-Schritte."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dekade.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            # 1980er: 2x
            ("OBJ_0001", "1985-01-01"),
            ("OBJ_0002", "1989-12-31"),
            # 1990er: 1x
            ("OBJ_0003", "1995-06-13"),
            # 2020er: 3x
            ("OBJ_0004", "2020-01-01"),
            ("OBJ_0005", "2024-06-13"),
            ("OBJ_0006", "2029-01-01"),
            # Ausgeschlossene: leer/NULL/ungueltig
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
            ("OBJ_0009", "Fruehling"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Chronologisch aufsteigend, Label mit 'er'-Suffix
    assert list(st.by_funddatum_jahrzehnt.items()) == [
        ("1980er", 2), ("1990er", 1), ("2020er", 3),
    ]
    c.close()


def test_by_funddatum_jahrzehnt_leer(tmp_path):
    """Ohne Funddaten ist die Dekaden-Verteilung leer."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "dl.sqlite3")
    st = compute_statistics(c)
    assert st.by_funddatum_jahrzehnt == {}
    c.close()


def test_by_funddatum_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_funddatum_jahr == {}
    c.close()


def test_by_funddatum_monat_aus_seed_db(tmp_path):
    """Monats-Histogramm aggregiert ueber alle Jahre zu Monatsziffern 01..12."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "monat.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            # Juli: 3x (verschiedene Jahre, gleicher Monat)
            ("OBJ_0001", "2020-07-15"),
            ("OBJ_0002", "2021-07-20"),
            ("OBJ_0003", "2024-07-01"),
            # August: 2x
            ("OBJ_0004", "2022-08-10"),
            ("OBJ_0005", "2024-08-31"),
            # Dezember: 1x (z.B. Mineralienboerse)
            ("OBJ_0006", "2023-12-05"),
            # Ausgeschlossene: leer/NULL/ungueltig/reine Jahresangabe
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
            ("OBJ_0009", "Fruehling"),
            ("OBJ_0010", "2024"),         # ohne Monatsteil -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Chronologisch aufsteigend nach Monatsziffer, Monate ohne Treffer fehlen
    assert list(st.by_funddatum_monat.items()) == [
        ("07", 3), ("08", 2), ("12", 1),
    ]
    assert st.as_dict()["by_funddatum_monat"] == {"07": 3, "08": 2, "12": 1}
    c.close()


def test_by_funddatum_monat_ignoriert_unsinnige_monatsteile(tmp_path):
    """Monat 00/13 (z.B. aus kaputten Importen) faellt aus dem Histogramm."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "monat_bad.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-00-15"),   # Monat 0 -> ignoriert
            ("OBJ_0002", "2024-13-01"),   # Monat 13 -> ignoriert
            ("OBJ_0003", "2024-07-01"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_funddatum_monat == {"07": 1}
    c.close()


def test_by_funddatum_monat_leer(tmp_path):
    """Ohne gueltige Funddaten ist die Monatsverteilung leer."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_funddatum_monat == {}
    c.close()


def test_wert_pro_funddatum_jahr_aus_seed_db(tmp_path):
    """Wertsumme pro Funddatum-Jahr, absteigend sortiert; Tie-Break chronologisch."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpfj.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # 2020: ein Riesenstueck (1000)
            ("OBJ_0001", "2020-05-13", 1000.0, None),
            # 2021: zwei Stuecke -> 300
            ("OBJ_0002", "2021-04-01", 100.0, 200.0),
            ("OBJ_0003", "2021-09-15", None, None),     # 0
            # 2022: drei Stuecke -> 300 (Tie-Break: chronologisch nach 2021)
            ("OBJ_0004", "2022-03-01", 100.0, None),
            ("OBJ_0005", "2022-07-10", 100.0, None),
            ("OBJ_0006", "2022-11-30", 100.0, None),
            # 2024: ein Stueck ohne Wert -> faellt raus
            ("OBJ_0007", "2024-01-01", None, None),
            # Ungueltige/leere Funddaten -> ignoriert
            ("OBJ_0008", "", 999.0, None),
            ("OBJ_0009", None, 999.0, None),
            ("OBJ_0010", "Fruehling", 999.0, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 2020 (1000) > 2021 (300) == 2022 (300) -> Tie-Break aufsteigend nach Jahr.
    assert st.wert_pro_funddatum_jahr == [
        ("2020", 1000.0),
        ("2021", 300.0),
        ("2022", 300.0),
    ]
    assert st.as_dict()["wert_pro_funddatum_jahr"] == [
        ("2020", 1000.0), ("2021", 300.0), ("2022", 300.0),
    ]
    c.close()


def test_wert_pro_funddatum_jahr_limit(tmp_path):
    """top_wert_funddatum_jahr begrenzt die Listenlaenge."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpfj_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"20{i:02d}-01-01", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_funddatum_jahr=3)
    assert len(st.wert_pro_funddatum_jahr) == 3
    werte = [w for _, w in st.wert_pro_funddatum_jahr]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_funddatum_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_funddatum_jahr == []
    c.close()


def test_gewicht_pro_funddatum_jahr_aus_seed_db(tmp_path):
    """Gewichtsumme pro Funddatum-Jahr; NULL/0 zaehlen nicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpfj.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "2020-05-13", 1000.0),
            ("OBJ_0002", "2021-04-01", 100.0),
            ("OBJ_0003", "2021-09-15", 150.0),   # 2021 total 250
            ("OBJ_0004", "2022-03-01", 50.0),
            ("OBJ_0005", "2022-07-10", None),    # NULL -> ignoriert
            ("OBJ_0006", "2022-11-30", 0.0),     # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_funddatum_jahr == [
        ("2020", 1000.0),
        ("2021", 250.0),
        ("2022", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_funddatum_jahr"] == [
        ("2020", 1000.0), ("2021", 250.0), ("2022", 50.0),
    ]
    c.close()


def test_gewicht_pro_funddatum_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_funddatum_jahr == []
    c.close()


def test_wert_pro_funddatum_jahrzehnt_aus_seed_db(tmp_path):
    """Wertsumme pro Dekade; absteigend nach Summe, Tie-Break chronologisch."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpfd.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # 1990er: ein Riesenstueck (1000)
            ("OBJ_0001", "1995-06-13", 1000.0, None),
            # 2000er: zwei Stuecke -> 300
            ("OBJ_0002", "2003-01-01", 100.0, 200.0),
            ("OBJ_0003", "2008-09-15", None, None),     # 0
            # 2010er: drei Stuecke -> 300 (Tie-Break: chronologisch nach 2000er)
            ("OBJ_0004", "2010-03-01", 100.0, None),
            ("OBJ_0005", "2014-07-10", 100.0, None),
            ("OBJ_0006", "2019-11-30", 100.0, None),
            # Ungueltige/leere Funddaten -> ignoriert
            ("OBJ_0007", "", 999.0, None),
            ("OBJ_0008", None, 999.0, None),
            ("OBJ_0009", "Fruehling", 999.0, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 1990er (1000) > 2000er (300) == 2010er (300) -> Tie-Break aufsteigend.
    assert st.wert_pro_funddatum_jahrzehnt == [
        ("1990er", 1000.0),
        ("2000er", 300.0),
        ("2010er", 300.0),
    ]
    assert st.as_dict()["wert_pro_funddatum_jahrzehnt"] == [
        ("1990er", 1000.0), ("2000er", 300.0), ("2010er", 300.0),
    ]
    c.close()


def test_wert_pro_funddatum_jahrzehnt_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_funddatum_jahrzehnt == []
    c.close()


def test_gewicht_pro_funddatum_jahrzehnt_aus_seed_db(tmp_path):
    """Gewichtsumme pro Dekade; NULL/0 zaehlen nicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpfd.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "1995-06-13", 1000.0),
            ("OBJ_0002", "2003-04-01", 100.0),
            ("OBJ_0003", "2008-09-15", 150.0),   # 2000er total 250
            ("OBJ_0004", "2010-03-01", 50.0),
            ("OBJ_0005", "2015-07-10", None),    # NULL -> ignoriert
            ("OBJ_0006", "2019-11-30", 0.0),     # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_funddatum_jahrzehnt == [
        ("1990er", 1000.0),
        ("2000er", 250.0),
        ("2010er", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_funddatum_jahrzehnt"] == [
        ("1990er", 1000.0), ("2000er", 250.0), ("2010er", 50.0),
    ]
    c.close()


def test_gewicht_pro_funddatum_jahrzehnt_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_funddatum_jahrzehnt == []
    c.close()


def test_wert_pro_funddatum_monat_aus_seed_db(tmp_path):
    """Wertsumme pro Funddatum-Monat ueber alle Jahre; absteigend nach Summe."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpfm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # Juli ueber zwei Jahre: 300 + 400 = 700
            ("OBJ_0001", "2020-07-15", 100.0, 200.0),
            ("OBJ_0002", "2024-07-20", 400.0, None),
            # August: 250
            ("OBJ_0003", "2022-08-10", 250.0, None),
            # Dezember (Boerse): 50
            ("OBJ_0004", "2023-12-05", 50.0, None),
            # Ohne Wert -> faellt raus
            ("OBJ_0005", "2024-03-01", None, None),
            # Ohne gueltiges Funddatum -> ignoriert
            ("OBJ_0006", "", 999.0, None),
            ("OBJ_0007", "2024", 999.0, None),     # ohne Monatsteil
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_funddatum_monat == [
        ("07", 700.0),
        ("08", 250.0),
        ("12", 50.0),
    ]
    assert st.as_dict()["wert_pro_funddatum_monat"] == [
        ("07", 700.0), ("08", 250.0), ("12", 50.0),
    ]
    c.close()


def test_wert_pro_funddatum_monat_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_funddatum_monat == []
    c.close()


def test_gewicht_pro_funddatum_monat_aus_seed_db(tmp_path):
    """Gewichtsumme pro Funddatum-Monat ueber alle Jahre; 0/NULL ignoriert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpfm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum, Gewicht_g) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2020-07-15", 100.0),
            ("OBJ_0002", "2024-07-20", 400.0),    # Juli: 500
            ("OBJ_0003", "2022-08-10", 250.0),    # August: 250
            ("OBJ_0004", "2023-12-05", 50.0),     # Dezember: 50
            ("OBJ_0005", "2024-03-01", None),     # NULL -> ignoriert
            ("OBJ_0006", "2024-03-01", 0.0),      # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_funddatum_monat == [
        ("07", 500.0),
        ("08", 250.0),
        ("12", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_funddatum_monat"] == [
        ("07", 500.0), ("08", 250.0), ("12", 50.0),
    ]
    c.close()


def test_gewicht_pro_funddatum_monat_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_funddatum_monat == []
    c.close()


def test_funddatum_spanne_aus_seed_db(tmp_path):
    """frueheste/spaeteste = MIN/MAX gueltiger Funddatum-Werte (ISO sortierbar)."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "spanne.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2021-05-13"),
            ("OBJ_0002", "2019-01-01"),
            ("OBJ_0003", "2024-12-31"),
            ("OBJ_0004", ""),           # ignoriert
            ("OBJ_0005", "Fruehling"),  # ignoriert (kein Jahres-Praefix)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.funddatum_frueheste == "2019-01-01"
    assert st.funddatum_spaeteste == "2024-12-31"
    d = st.as_dict()
    assert d["funddatum_frueheste"] == "2019-01-01"
    assert d["funddatum_spaeteste"] == "2024-12-31"
    c.close()


def test_funddatum_spanne_leer(tmp_path):
    """Ohne gueltige Funddatum-Werte sind beide Grenzen None."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [("OBJ_0001", ""), ("OBJ_0002", None), ("OBJ_0003", "unbekannt")],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.funddatum_frueheste is None
    assert st.funddatum_spaeteste is None
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
    assert st.median_confidence_prozent is None
    assert st.wert_roh_summe_chf == 0.0


def test_median_confidence_ungerade_anzahl(tmp_path):
    """Median bei 3 Confidence-Werten = mittlerer Wert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mc1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 50), ("OBJ_0002", 80), ("OBJ_0003", 90)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.median_confidence_prozent == 80.0
    assert st.as_dict()["median_confidence_prozent"] == 80.0
    c.close()


def test_median_confidence_gerade_anzahl(tmp_path):
    """Median bei 4 Werten = Mittel der beiden mittleren."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mc2.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 40), ("OBJ_0002", 50),
         ("OBJ_0003", 70), ("OBJ_0004", 80)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.median_confidence_prozent == 60.0    # (50+70)/2
    c.close()


def test_median_confidence_ignoriert_null_und_out_of_range(tmp_path):
    """NULL und Out-of-Range-Werte zaehlen weder in Mittel noch Median."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mc3.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 50),
            ("OBJ_0002", 80),
            ("OBJ_0003", None),     # ignoriert
            ("OBJ_0004", -10),      # out-of-range, ignoriert
            ("OBJ_0005", 150),      # out-of-range, ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.median_confidence_prozent == 65.0   # (50+80)/2 ueber [50, 80]
    c.close()


def test_confidence_buckets_verteilung(tmp_path):
    """Confidence-Werte landen in 25-Prozent-Klassen; NULL faellt auf 'ohne'."""
    from stonebook.db.database import open_db
    from stonebook.db.stats import CONFIDENCE_BUCKET_ORDER
    c = open_db(tmp_path / "buckets.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 0),     # 0-24
            ("OBJ_0002", 24),    # 0-24 (Grenze inklusiv)
            ("OBJ_0003", 25),    # 25-49 (Grenze)
            ("OBJ_0004", 49),    # 25-49 (Grenze inklusiv)
            ("OBJ_0005", 50),    # 50-74
            ("OBJ_0006", 74),    # 50-74 (Grenze inklusiv)
            ("OBJ_0007", 75),    # 75-100
            ("OBJ_0008", 100),   # 75-100 (Grenze inklusiv)
            ("OBJ_0009", None),  # ohne
            ("OBJ_0010", None),  # ohne
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_buckets == {
        "ohne": 2, "0-24": 2, "25-49": 2, "50-74": 2, "75-100": 2,
    }
    # Reihenfolge ist stabil (Dashboard zeichnet in dieser Reihenfolge)
    assert list(st.confidence_buckets) == list(CONFIDENCE_BUCKET_ORDER)
    c.close()


def test_confidence_buckets_leere_db(tmp_path):
    """Leere DB → alle Klassen 0, Reihenfolge bleibt."""
    from stonebook.db.database import open_db
    from stonebook.db.stats import CONFIDENCE_BUCKET_ORDER
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.confidence_buckets == {k: 0 for k in CONFIDENCE_BUCKET_ORDER}
    c.close()


def test_ki_analysen_zaehler(tmp_path):
    """ki_analysen_total/uebernommen/objekte_mit_analyse zaehlen die KI-Spalten korrekt."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ki.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",)],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json, uebernommen_json) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", "2024-06-13 10:00:00", "claude-opus", "{}", '{"a":1}'),
            ("OBJ_0001", "2024-06-14 10:00:00", "claude-opus", "{}", None),
            ("OBJ_0002", "2024-06-13 10:00:00", "claude-opus", "{}", None),
            ("OBJ_0002", "2024-06-15 10:00:00", "claude-opus", "{}", ""),
            # OBJ_0003: keine Analyse
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.ki_analysen_total == 4
    assert st.ki_analysen_uebernommen == 1   # nur OBJ_0001's erste
    assert st.objekte_mit_ki_analyse == 2    # OBJ_0001 und OBJ_0002
    c.close()


def test_ki_analysen_leere_db(tmp_path):
    """Leere DB → alle KI-Zaehler 0 (kein Crash)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.ki_analysen_total == 0
    assert st.ki_analysen_uebernommen == 0
    assert st.objekte_mit_ki_analyse == 0
    c.close()


def test_confidence_buckets_ignoriert_out_of_range(tmp_path):
    """Confidence < 0 oder > 100 ist out-of-range (Integrity meldet das separat) und faellt aus den Buckets."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", -5),     # out-of-range
            ("OBJ_0002", 150),    # out-of-range
            ("OBJ_0003", 80),     # 75-100
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_buckets["75-100"] == 1
    # Out-of-range Werte tauchen nicht in einem Bucket auf
    assert sum(st.confidence_buckets.values()) == 1


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


def test_by_glanz_aus_seed_db(tmp_path):
    """Verteilung nach Glanz ignoriert leere Eintraege (optische Charakteristik)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "glz.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?, ?)",
        [
            ("OBJ_0001", "glasig"),
            ("OBJ_0002", "glasig"),
            ("OBJ_0003", "glasig"),
            ("OBJ_0004", "metallisch"),
            ("OBJ_0005", "matt"),
            ("OBJ_0006", ""),
            ("OBJ_0007", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_glanz == {"glasig": 3, "matt": 1, "metallisch": 1}
    assert st.as_dict()["by_glanz"]["glasig"] == 3
    c.close()


def test_by_glanz_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_glanz == {}
    c.close()


def test_by_transparenz_aus_seed_db(tmp_path):
    """Verteilung nach Transparenz ignoriert leere Eintraege (3 Enum-Stufen)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "trz.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?, ?)",
        [
            ("OBJ_0001", "durchsichtig"),
            ("OBJ_0002", "durchsichtig"),
            ("OBJ_0003", "durchscheinend"),
            ("OBJ_0004", "opak"),
            ("OBJ_0005", "opak"),
            ("OBJ_0006", "opak"),
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_transparenz == {"opak": 3, "durchsichtig": 2, "durchscheinend": 1}
    assert st.as_dict()["by_transparenz"]["opak"] == 3
    c.close()


def test_by_transparenz_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_transparenz == {}
    c.close()


def test_by_magnetismus_aus_seed_db(tmp_path):
    """Verteilung nach Magnetismus ignoriert leere Eintraege (3 Enum-Stufen).

    Praktischer Eisengehalt-Indikator: nein (Quarz/Calcit), schwach
    (Haematit/Ilmenit), ja (Magnetit/Pyrrhotin). Geht mineralogisch quer
    durch alle Hauptgruppen - eine Sicht, die by_mineral nicht abdeckt.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "mag.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [
            ("OBJ_0001", "nein"),
            ("OBJ_0002", "nein"),
            ("OBJ_0003", "nein"),
            ("OBJ_0004", "schwach"),
            ("OBJ_0005", "ja"),
            ("OBJ_0006", "ja"),
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_magnetismus == {"nein": 3, "ja": 2, "schwach": 1}
    assert st.as_dict()["by_magnetismus"]["nein"] == 3
    c.close()


def test_by_magnetismus_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_magnetismus == {}
    c.close()


def test_by_spaltbarkeit_aus_seed_db(tmp_path):
    """Verteilung nach Spaltbarkeit ignoriert leere Eintraege (5 Enum-Stufen).

    Klassische Lehrbuch-Sicht: Calcit/Fluorit/Glimmer (vollkommen) vs. Quarz
    (keine) vs. Granat (deutlich). Spiegelt Bruch und Glanz auf der
    mineralogischen Achse - praktisch fuer Polier-/Praeparier-Entscheidungen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "spk.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?, ?)",
        [
            ("OBJ_0001", "keine"),
            ("OBJ_0002", "keine"),
            ("OBJ_0003", "keine"),
            ("OBJ_0004", "vollkommen"),
            ("OBJ_0005", "vollkommen"),
            ("OBJ_0006", "deutlich"),
            ("OBJ_0007", "undeutlich"),
            ("OBJ_0008", ""),
            ("OBJ_0009", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_spaltbarkeit == {
        "keine": 3, "vollkommen": 2, "deutlich": 1, "undeutlich": 1,
    }
    assert st.as_dict()["by_spaltbarkeit"]["keine"] == 3
    c.close()


def test_by_spaltbarkeit_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_spaltbarkeit == {}
    c.close()


def test_by_varietaet_aus_seed_db(tmp_path):
    """Verteilung nach Varietaet ignoriert leere Eintraege (Quarz-Familie zerfaellt)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "var.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?, ?)",
        [
            ("OBJ_0001", "Bergkristall"),
            ("OBJ_0002", "Bergkristall"),
            ("OBJ_0003", "Milchquarz"),
            ("OBJ_0004", "Rauchquarz"),
            ("OBJ_0005", ""),
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_varietaet == {
        "Bergkristall": 2, "Milchquarz": 1, "Rauchquarz": 1,
    }
    assert st.as_dict()["by_varietaet"]["Bergkristall"] == 2
    c.close()


def test_by_varietaet_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_varietaet == {}
    c.close()


def test_by_gesteinsart_aus_seed_db(tmp_path):
    """Verteilung nach Gesteinsart ignoriert leere Eintraege (petrologische Gruppen)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "ges.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?, ?)",
        [
            ("OBJ_0001", "Granit"),
            ("OBJ_0002", "Granit"),
            ("OBJ_0003", "Gneis"),
            ("OBJ_0004", "Basalt"),
            ("OBJ_0005", ""),
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_gesteinsart == {"Granit": 2, "Basalt": 1, "Gneis": 1}
    assert st.as_dict()["by_gesteinsart"]["Granit"] == 2
    c.close()


def test_by_gesteinsart_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_gesteinsart == {}
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


def test_wert_pro_kategorie_aus_seed_db(tmp_path):
    """Wertsumme pro Objekt-Kategorie, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpk.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Kristall", 100.0, 200.0),    # 300
            ("OBJ_0002", "Kristall", 50.0, None),      # 50 -> Kristall 350
            ("OBJ_0003", "Handstück", 1000.0, None),   # 1000
            ("OBJ_0004", "Handstück", None, None),     # 0
            ("OBJ_0005", "Geröll", 10.0, None),        # 10
            ("OBJ_0006", "", 999.0, None),             # leere Kategorie -> ignoriert
            ("OBJ_0007", None, 999.0, None),           # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_kategorie == [
        ("Handstück", 1000.0),
        ("Kristall", 350.0),
        ("Geröll", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_kategorie"] == [
        ("Handstück", 1000.0), ("Kristall", 350.0), ("Geröll", 10.0),
    ]
    c.close()


def test_wert_pro_kategorie_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpk_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Kat{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_kategorie=3)
    assert len(st.wert_pro_kategorie) == 3
    werte = [w for _, w in st.wert_pro_kategorie]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_kategorie_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_kategorie == []
    c.close()


def test_gewicht_pro_kategorie_aus_seed_db(tmp_path):
    """Gewichtsumme pro Objekt-Kategorie, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpk.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Kristall", 100.0),
            ("OBJ_0002", "Kristall", 50.0),       # Kristall total 150
            ("OBJ_0003", "Handstück", 1000.0),    # Handstück total 1000
            ("OBJ_0004", "Handstück", None),      # NULL → ignoriert
            ("OBJ_0005", "Geröll", 10.0),
            ("OBJ_0006", "", 999.0),              # leere Kategorie → ignoriert
            ("OBJ_0007", None, 999.0),            # NULL Kategorie → ignoriert
            ("OBJ_0008", "Mineral-Korn", 0.0),    # 0 zaehlt nicht
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_kategorie == [
        ("Handstück", 1000.0),
        ("Kristall", 150.0),
        ("Geröll", 10.0),
    ]
    assert st.as_dict()["gewicht_pro_kategorie"] == [
        ("Handstück", 1000.0), ("Kristall", 150.0), ("Geröll", 10.0),
    ]
    c.close()


def test_gewicht_pro_kategorie_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpk_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Kat{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_kategorie=3)
    assert len(st.gewicht_pro_kategorie) == 3
    g = [v for _, v in st.gewicht_pro_kategorie]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_kategorie_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_kategorie == []
    c.close()


def test_wert_pro_status_aus_seed_db(tmp_path):
    """Wertsumme pro Status (aktiv/platzhalter/archiviert), absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wps.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, status, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "aktiv", 100.0, 200.0),       # aktiv: 300
            ("OBJ_0002", "aktiv", 50.0, None),         # aktiv: +50 -> 350
            ("OBJ_0003", "archiviert", 1000.0, None),  # archiviert: 1000
            ("OBJ_0004", "platzhalter", 10.0, None),   # platzhalter: 10
            ("OBJ_0005", "platzhalter", None, None),   # 0 -> egal
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_status == [
        ("archiviert", 1000.0),
        ("aktiv", 350.0),
        ("platzhalter", 10.0),
    ]
    assert st.as_dict()["wert_pro_status"] == [
        ("archiviert", 1000.0), ("aktiv", 350.0), ("platzhalter", 10.0),
    ]
    c.close()


def test_wert_pro_status_leer(tmp_path):
    """Leere DB → leere Liste, kein Crash."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_status == []
    c.close()


def test_gewicht_pro_status_aus_seed_db(tmp_path):
    """Gewichtsumme pro Status, absteigend sortiert; 0/NULL zaehlen nicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gps.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, status, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "aktiv", 100.0),
            ("OBJ_0002", "aktiv", 50.0),          # aktiv total 150
            ("OBJ_0003", "archiviert", 1000.0),   # archiviert 1000
            ("OBJ_0004", "platzhalter", 10.0),    # platzhalter 10
            ("OBJ_0005", "platzhalter", None),    # NULL → ignoriert
            ("OBJ_0006", "aktiv", 0.0),           # 0 zaehlt nicht
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_status == [
        ("archiviert", 1000.0),
        ("aktiv", 150.0),
        ("platzhalter", 10.0),
    ]
    assert st.as_dict()["gewicht_pro_status"] == [
        ("archiviert", 1000.0), ("aktiv", 150.0), ("platzhalter", 10.0),
    ]
    c.close()


def test_gewicht_pro_status_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_status == []
    c.close()


def test_gewicht_pro_fundort_aus_seed_db(tmp_path):
    """Gewichtsumme pro Fundort, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Davos", 100.0),
            ("OBJ_0002", "Davos", 50.0),       # Davos total 150
            ("OBJ_0003", "Zermatt", 1000.0),
            ("OBJ_0004", "Zermatt", None),     # NULL → ignoriert
            ("OBJ_0005", "Andermatt", 10.0),
            ("OBJ_0006", "", 999.0),           # leerer Fundort
            ("OBJ_0007", None, 999.0),         # NULL Fundort
            ("OBJ_0008", "Davos", 0.0),        # Null-Gewicht zaehlt nicht
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_fundort == [
        ("Zermatt", 1000.0),
        ("Davos", 150.0),
        ("Andermatt", 10.0),
    ]
    assert st.as_dict()["gewicht_pro_fundort"] == [
        ("Zermatt", 1000.0), ("Davos", 150.0), ("Andermatt", 10.0),
    ]
    c.close()


def test_gewicht_pro_fundort_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpf_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Ort{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_fundort=3)
    assert len(st.gewicht_pro_fundort) == 3


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


def test_top_gewicht_objekte_aus_seed_db(tmp_path):
    """Schwerste Objekte absteigend nach Gewicht_g (NULL/0 ignoriert)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Name, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Leicht", 10.0),
            ("OBJ_0002", "Mittel", 100.0),
            ("OBJ_0003", "Schwer", 500.0),
            ("OBJ_0004", "OhneMasse", None),
            ("OBJ_0005", "NullMasse", 0.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.top_gewicht_objekte == [
        ("OBJ_0003", "Schwer", 500.0),
        ("OBJ_0002", "Mittel", 100.0),
        ("OBJ_0001", "Leicht", 10.0),
    ]
    d = st.as_dict()
    assert d["top_gewicht_objekte"] == [
        ("OBJ_0003", "Schwer", 500.0),
        ("OBJ_0002", "Mittel", 100.0),
        ("OBJ_0001", "Leicht", 10.0),
    ]
    c.close()


def test_top_gewicht_objekte_limit_respektiert(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tg_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?,?)",
        [(f"OBJ_{i:04d}", float(i)) for i in range(1, 21)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht=3)
    assert len(st.top_gewicht_objekte) == 3
    gewichte = [g for _, _, g in st.top_gewicht_objekte]
    assert gewichte == [20.0, 19.0, 18.0]
    c.close()


def test_top_gewicht_objekte_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.top_gewicht_objekte == []
    c.close()


def test_top_bilder_objekte_aus_seed_db(tmp_path):
    """Best-fotografierte Objekte absteigend nach Bildanzahl (Objekte ohne Foto ignoriert)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tb.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Name) VALUES (?,?)",
        [
            ("OBJ_0001", "EinFoto"),
            ("OBJ_0002", "DreiFotos"),
            ("OBJ_0003", "FuenfFotos"),
            ("OBJ_0004", "OhneFoto"),
        ],
    )
    # Verschiedene Foto-Kategorien (die zaehlen alle gleich fuer top_bilder).
    # rel_path muss pro DB einzigartig sein (UNIQUE constraint), daher obj_id-praefix.
    image_rows = [
        ("OBJ_0001", "uebersicht", "OBJ_0001/uebersicht.jpg"),
        ("OBJ_0002", "uebersicht", "OBJ_0002/u.jpg"),
        ("OBJ_0002", "kamera",     "OBJ_0002/k.jpg"),
        ("OBJ_0002", "mikroskop",  "OBJ_0002/m.jpg"),
        ("OBJ_0003", "uebersicht", "OBJ_0003/u.jpg"),
        ("OBJ_0003", "kamera",     "OBJ_0003/k.jpg"),
        ("OBJ_0003", "mikroskop",  "OBJ_0003/m.jpg"),
        ("OBJ_0003", "uv_365nm",   "OBJ_0003/uv.jpg"),
        ("OBJ_0003", "sonder",     "OBJ_0003/s.jpg"),
    ]
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        image_rows,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.top_bilder_objekte == [
        ("OBJ_0003", "FuenfFotos", 5),
        ("OBJ_0002", "DreiFotos", 3),
        ("OBJ_0001", "EinFoto", 1),
    ]
    # JSON-Form bleibt mit int erhalten (kein float-Rounding)
    d = st.as_dict()
    assert d["top_bilder_objekte"] == [
        ("OBJ_0003", "FuenfFotos", 5),
        ("OBJ_0002", "DreiFotos", 3),
        ("OBJ_0001", "EinFoto", 1),
    ]
    c.close()


def test_top_bilder_objekte_limit_respektiert(tmp_path):
    """top_bilder=3 schneidet die Top-3 ab; sonst werden bis zu top_bilder Eintraege geliefert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tb_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [(f"OBJ_{i:04d}",) for i in range(1, 8)],
    )
    # OBJ_n bekommt n Bilder (n=1..7)
    image_rows = [
        (f"OBJ_{i:04d}", "uebersicht", f"u{i}_{j}.jpg")
        for i in range(1, 8) for j in range(1, i + 1)
    ]
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        image_rows,
    )
    c.commit()
    st = compute_statistics(c, top_bilder=3)
    assert len(st.top_bilder_objekte) == 3
    zahlen = [n for _, _, n in st.top_bilder_objekte]
    assert zahlen == [7, 6, 5]
    c.close()


def test_top_bilder_objekte_leer(tmp_path):
    """Ohne Bilder bleibt die Liste leer (HAVING n > 0 schliesst Null-Eintraege aus)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.top_bilder_objekte == []
    c.close()


def test_by_beste_verwendung_aus_seed_db(tmp_path):
    """Verteilung nach 'Beste Verwendung' (Enum); leere Werte ignoriert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [
            ("OBJ_0001", "Sammlung"),
            ("OBJ_0002", "Sammlung"),
            ("OBJ_0003", "Schmuck"),
            ("OBJ_0004", "Forschung"),
            ("OBJ_0005", ""),       # leer → ignoriert
            ("OBJ_0006", None),     # NULL → ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_beste_verwendung == {
        "Sammlung": 2, "Forschung": 1, "Schmuck": 1,
    }
    d = st.as_dict()
    assert d["by_beste_verwendung"]["Sammlung"] == 2
    c.close()


def test_by_beste_verwendung_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_beste_verwendung == {}
    c.close()


def test_wert_pro_kristallsystem_aus_seed_db(tmp_path):
    """Wertsumme pro Kristallsystem, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpks.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem, Wert_CHF_roh, "
        "Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "trigonal", 100.0, 200.0),     # trigonal: 300
            ("OBJ_0002", "trigonal", 50.0, None),       # trigonal: +50 -> 350
            ("OBJ_0003", "kubisch", 1000.0, None),      # kubisch: 1000
            ("OBJ_0004", "kubisch", None, None),        # 0
            ("OBJ_0005", "hexagonal", 10.0, None),
            ("OBJ_0006", "", 999.0, None),              # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),            # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_kristallsystem == [
        ("kubisch", 1000.0),
        ("trigonal", 350.0),
        ("hexagonal", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_kristallsystem"] == [
        ("kubisch", 1000.0), ("trigonal", 350.0), ("hexagonal", 10.0),
    ]
    c.close()


def test_wert_pro_kristallsystem_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpks_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem, Wert_CHF_roh) "
        "VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Sys{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_kristallsystem=3)
    assert len(st.wert_pro_kristallsystem) == 3
    werte = [w for _, w in st.wert_pro_kristallsystem]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_kristallsystem_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_kristallsystem == []
    c.close()


def test_gewicht_pro_kristallsystem_aus_seed_db(tmp_path):
    """Gewichtsumme pro Kristallsystem, absteigend sortiert; 0/NULL zaehlen nicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpks.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "trigonal", 100.0),
            ("OBJ_0002", "trigonal", 50.0),       # trigonal total 150
            ("OBJ_0003", "kubisch", 1000.0),      # kubisch total 1000
            ("OBJ_0004", "kubisch", None),        # NULL -> ignoriert
            ("OBJ_0005", "hexagonal", 10.0),
            ("OBJ_0006", "", 999.0),              # leer -> ignoriert
            ("OBJ_0007", None, 999.0),            # NULL -> ignoriert
            ("OBJ_0008", "monoklin", 0.0),        # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_kristallsystem == [
        ("kubisch", 1000.0),
        ("trigonal", 150.0),
        ("hexagonal", 10.0),
    ]
    assert st.as_dict()["gewicht_pro_kristallsystem"] == [
        ("kubisch", 1000.0), ("trigonal", 150.0), ("hexagonal", 10.0),
    ]
    c.close()


def test_gewicht_pro_kristallsystem_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpks_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Sys{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_kristallsystem=3)
    assert len(st.gewicht_pro_kristallsystem) == 3
    g = [v for _, v in st.gewicht_pro_kristallsystem]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_kristallsystem_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_kristallsystem == []
    c.close()


def test_wert_pro_glanz_aus_seed_db(tmp_path):
    """Wertsumme pro Glanz, absteigend sortiert (optische Wert-Sicht)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "glasig", 100.0, 200.0),    # glasig: 300
            ("OBJ_0002", "glasig", 50.0, None),      # glasig: +50 -> 350
            ("OBJ_0003", "metallisch", 1000.0, None),  # metallisch: 1000
            ("OBJ_0004", "metallisch", None, None),  # 0
            ("OBJ_0005", "matt", 10.0, None),
            ("OBJ_0006", "", 999.0, None),           # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),         # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_glanz == [
        ("metallisch", 1000.0),
        ("glasig", 350.0),
        ("matt", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_glanz"] == [
        ("metallisch", 1000.0), ("glasig", 350.0), ("matt", 10.0),
    ]
    c.close()


def test_wert_pro_glanz_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpg_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Glanz{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_glanz=3)
    assert len(st.wert_pro_glanz) == 3
    werte = [w for _, w in st.wert_pro_glanz]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_glanz_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_glanz == []
    c.close()


def test_gewicht_pro_glanz_aus_seed_db(tmp_path):
    """Gewichtsumme pro Glanz, absteigend sortiert; 0/NULL zaehlen nicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "matt", 1000.0),         # matt total 1000 (Geroelle schwer)
            ("OBJ_0002", "matt", 500.0),          # matt total 1500
            ("OBJ_0003", "glasig", 100.0),        # glasig total 100 (Kristalle leicht)
            ("OBJ_0004", "glasig", None),         # NULL -> ignoriert
            ("OBJ_0005", "metallisch", 200.0),
            ("OBJ_0006", "", 999.0),              # leer -> ignoriert
            ("OBJ_0007", None, 999.0),            # NULL -> ignoriert
            ("OBJ_0008", "seidig", 0.0),          # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_glanz == [
        ("matt", 1500.0),
        ("metallisch", 200.0),
        ("glasig", 100.0),
    ]
    assert st.as_dict()["gewicht_pro_glanz"] == [
        ("matt", 1500.0), ("metallisch", 200.0), ("glasig", 100.0),
    ]
    c.close()


def test_gewicht_pro_glanz_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpg_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Glanz{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_glanz=3)
    assert len(st.gewicht_pro_glanz) == 3
    g = [v for _, v in st.gewicht_pro_glanz]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_glanz_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_glanz == []
    c.close()


def test_wert_pro_transparenz_aus_seed_db(tmp_path):
    """Wertsumme pro Transparenz, absteigend sortiert (Licht-Wert-Sicht).

    Pendant zu wert_pro_glanz auf der Lichtdurchlaessigkeits-Achse: glasige
    durchsichtige Kristalle vs. opake Pyrit-Stuecke liegen wertlich oft auf
    unterschiedlichen Niveaus, der Block macht das transparent.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "durchsichtig", 100.0, 200.0),   # durchsichtig: 300
            ("OBJ_0002", "durchsichtig", 50.0, None),     # +50 -> 350
            ("OBJ_0003", "opak", 1000.0, None),           # opak: 1000
            ("OBJ_0004", "opak", None, None),             # 0
            ("OBJ_0005", "durchscheinend", 10.0, None),
            ("OBJ_0006", "", 999.0, None),                # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),              # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_transparenz == [
        ("opak", 1000.0),
        ("durchsichtig", 350.0),
        ("durchscheinend", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_transparenz"] == [
        ("opak", 1000.0), ("durchsichtig", 350.0), ("durchscheinend", 10.0),
    ]
    c.close()


def test_wert_pro_transparenz_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpt_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Trans{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_transparenz=3)
    assert len(st.wert_pro_transparenz) == 3
    werte = [w for _, w in st.wert_pro_transparenz]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_transparenz_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_transparenz == []
    c.close()


def test_gewicht_pro_transparenz_aus_seed_db(tmp_path):
    """Gewichtsumme pro Transparenz, absteigend sortiert; 0/NULL zaehlen nicht.

    Spiegelbild zu wert_pro_transparenz: opake Sedimentstuecke tragen oft die
    Sammlungsmasse, durchsichtige Kristalle den Wert - die Wert/Gewicht-
    Entkopplung wird auf der Lichtdurchlaessigkeits-Achse sichtbar.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "opak", 1000.0),          # opak total 1000
            ("OBJ_0002", "opak", 500.0),           # opak total 1500
            ("OBJ_0003", "durchsichtig", 100.0),   # durchsichtig total 100
            ("OBJ_0004", "durchsichtig", None),    # NULL -> ignoriert
            ("OBJ_0005", "durchscheinend", 200.0),
            ("OBJ_0006", "", 999.0),               # leer -> ignoriert
            ("OBJ_0007", None, 999.0),             # NULL -> ignoriert
            ("OBJ_0008", "durchsichtig", 0.0),     # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_transparenz == [
        ("opak", 1500.0),
        ("durchscheinend", 200.0),
        ("durchsichtig", 100.0),
    ]
    assert st.as_dict()["gewicht_pro_transparenz"] == [
        ("opak", 1500.0), ("durchscheinend", 200.0), ("durchsichtig", 100.0),
    ]
    c.close()


def test_gewicht_pro_transparenz_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpt_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Trans{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_transparenz=3)
    assert len(st.gewicht_pro_transparenz) == 3
    g = [v for _, v in st.gewicht_pro_transparenz]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_transparenz_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_transparenz == []
    c.close()


def test_wert_pro_magnetismus_aus_seed_db(tmp_path):
    """Wertsumme pro Magnetismus, absteigend sortiert (Eisengehalts-Wert-Sicht).

    Komplementaer zu wert_pro_glanz/wert_pro_transparenz: hier die physikalische
    Eisengehalt-Achse. Magnetit-Stuecke (ja) sind oft markant teurer als ein
    durchschnittliches Quarz-Stueck, schwach magnetische Haematit-Brocken
    liegen dazwischen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "ja", 100.0, 200.0),       # ja: 300
            ("OBJ_0002", "ja", 50.0, None),         # +50 -> 350
            ("OBJ_0003", "nein", 1000.0, None),     # nein: 1000
            ("OBJ_0004", "nein", None, None),       # 0
            ("OBJ_0005", "schwach", 10.0, None),
            ("OBJ_0006", "", 999.0, None),          # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),        # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_magnetismus == [
        ("nein", 1000.0),
        ("ja", 350.0),
        ("schwach", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_magnetismus"] == [
        ("nein", 1000.0), ("ja", 350.0), ("schwach", 10.0),
    ]
    c.close()


def test_wert_pro_magnetismus_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpm_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Mag{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_magnetismus=3)
    assert len(st.wert_pro_magnetismus) == 3
    werte = [w for _, w in st.wert_pro_magnetismus]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_magnetismus_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_magnetismus == []
    c.close()


def test_gewicht_pro_magnetismus_aus_seed_db(tmp_path):
    """Gewichtsumme pro Magnetismus, absteigend sortiert; 0/NULL zaehlen nicht.

    Spiegelbild zu wert_pro_magnetismus: Magnetit-Brocken sind dicht und schwer,
    waehrend ein durchschnittlicher Quarz-Stueck im Gewicht oft hinter dem
    Sammlungs-Durchschnitt zurueckbleibt - die Wert/Gewicht-Entkopplung wird
    auch hier sichtbar.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "ja", 1000.0),         # ja total 1000 (Magnetit dicht)
            ("OBJ_0002", "ja", 500.0),          # ja total 1500
            ("OBJ_0003", "nein", 100.0),        # nein total 100
            ("OBJ_0004", "nein", None),         # NULL -> ignoriert
            ("OBJ_0005", "schwach", 200.0),
            ("OBJ_0006", "", 999.0),            # leer -> ignoriert
            ("OBJ_0007", None, 999.0),          # NULL -> ignoriert
            ("OBJ_0008", "ja", 0.0),            # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_magnetismus == [
        ("ja", 1500.0),
        ("schwach", 200.0),
        ("nein", 100.0),
    ]
    assert st.as_dict()["gewicht_pro_magnetismus"] == [
        ("ja", 1500.0), ("schwach", 200.0), ("nein", 100.0),
    ]
    c.close()


def test_gewicht_pro_magnetismus_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpm_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Mag{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_magnetismus=3)
    assert len(st.gewicht_pro_magnetismus) == 3
    g = [v for _, v in st.gewicht_pro_magnetismus]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_magnetismus_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_magnetismus == []
    c.close()


def test_wert_pro_spaltbarkeit_aus_seed_db(tmp_path):
    """Wertsumme pro Spaltbarkeit, absteigend sortiert (Spaltflaechen-Wert-Sicht).

    Komplementaer zu by_spaltbarkeit (Anzahl): zeigt, welche Spaltflaechen-
    Klasse den Sammlungswert traegt. Calcit/Fluorit (vollkommen) liegen
    wertlich oft auf einem anderen Niveau als Quarz-Stuecke (keine).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wps.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "vollkommen", 100.0, 200.0),    # vollkommen: 300
            ("OBJ_0002", "vollkommen", 50.0, None),      # +50 -> 350
            ("OBJ_0003", "keine", 1000.0, None),         # keine: 1000
            ("OBJ_0004", "keine", None, None),           # 0
            ("OBJ_0005", "deutlich", 10.0, None),
            ("OBJ_0006", "", 999.0, None),               # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),             # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_spaltbarkeit == [
        ("keine", 1000.0),
        ("vollkommen", 350.0),
        ("deutlich", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_spaltbarkeit"] == [
        ("keine", 1000.0), ("vollkommen", 350.0), ("deutlich", 10.0),
    ]
    c.close()


def test_wert_pro_spaltbarkeit_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wps_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Sp{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_spaltbarkeit=3)
    assert len(st.wert_pro_spaltbarkeit) == 3
    werte = [w for _, w in st.wert_pro_spaltbarkeit]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_spaltbarkeit_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_spaltbarkeit == []
    c.close()


def test_gewicht_pro_spaltbarkeit_aus_seed_db(tmp_path):
    """Gewichtsumme pro Spaltbarkeit, absteigend sortiert; 0/NULL zaehlen nicht.

    Spiegelbild zu wert_pro_spaltbarkeit: dichte Quarz-Brocken (keine) tragen
    den Schwerteil der Sammlungsmasse, leichte Glimmer-Plaettchen (vollkommen)
    bleiben gewichtsmaessig oft hinter dem Wert zurueck - die Wert/Gewicht-
    Entkopplung wird auch auf der Spaltflaechen-Achse sichtbar.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gps.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "keine", 1000.0),       # keine total 1000 (Quarz dicht)
            ("OBJ_0002", "keine", 500.0),        # keine total 1500
            ("OBJ_0003", "vollkommen", 100.0),   # vollkommen total 100
            ("OBJ_0004", "vollkommen", None),    # NULL -> ignoriert
            ("OBJ_0005", "deutlich", 200.0),
            ("OBJ_0006", "", 999.0),             # leer -> ignoriert
            ("OBJ_0007", None, 999.0),           # NULL -> ignoriert
            ("OBJ_0008", "keine", 0.0),          # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_spaltbarkeit == [
        ("keine", 1500.0),
        ("deutlich", 200.0),
        ("vollkommen", 100.0),
    ]
    assert st.as_dict()["gewicht_pro_spaltbarkeit"] == [
        ("keine", 1500.0), ("deutlich", 200.0), ("vollkommen", 100.0),
    ]
    c.close()


def test_gewicht_pro_spaltbarkeit_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gps_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Sp{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_spaltbarkeit=3)
    assert len(st.gewicht_pro_spaltbarkeit) == 3
    g = [v for _, v in st.gewicht_pro_spaltbarkeit]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_spaltbarkeit_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_spaltbarkeit == []
    c.close()


def test_wert_pro_varietaet_aus_seed_db(tmp_path):
    """Wertsumme pro Varietaet, absteigend sortiert (feinere Aufteilung unter Mineral)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Bergkristall", 100.0, 200.0),   # 300
            ("OBJ_0002", "Bergkristall", 50.0, None),     # +50 -> 350
            ("OBJ_0003", "Milchquarz", 1000.0, None),     # 1000
            ("OBJ_0004", "Milchquarz", None, None),       # 0
            ("OBJ_0005", "Rauchquarz", 10.0, None),
            ("OBJ_0006", "", 999.0, None),                # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),              # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_varietaet == [
        ("Milchquarz", 1000.0),
        ("Bergkristall", 350.0),
        ("Rauchquarz", 10.0),
    ]
    assert st.as_dict()["wert_pro_varietaet"] == [
        ("Milchquarz", 1000.0), ("Bergkristall", 350.0), ("Rauchquarz", 10.0),
    ]
    c.close()


def test_wert_pro_varietaet_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpv_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Var{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_varietaet=3)
    assert len(st.wert_pro_varietaet) == 3
    werte = [w for _, w in st.wert_pro_varietaet]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_varietaet_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_varietaet == []
    c.close()


def test_gewicht_pro_varietaet_aus_seed_db(tmp_path):
    """Gewichtsumme pro Varietaet, absteigend; 0/NULL zaehlen nicht (analog zu Kristallsystem)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Bergkristall", 100.0),
            ("OBJ_0002", "Bergkristall", 50.0),   # 150
            ("OBJ_0003", "Milchquarz", 1000.0),   # 1000
            ("OBJ_0004", "Milchquarz", None),     # NULL -> ignoriert
            ("OBJ_0005", "Rauchquarz", 10.0),
            ("OBJ_0006", "", 999.0),              # leer -> ignoriert
            ("OBJ_0007", None, 999.0),            # NULL -> ignoriert
            ("OBJ_0008", "Jaspis", 0.0),          # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_varietaet == [
        ("Milchquarz", 1000.0),
        ("Bergkristall", 150.0),
        ("Rauchquarz", 10.0),
    ]
    assert st.as_dict()["gewicht_pro_varietaet"] == [
        ("Milchquarz", 1000.0), ("Bergkristall", 150.0), ("Rauchquarz", 10.0),
    ]
    c.close()


def test_gewicht_pro_varietaet_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpv_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Var{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_varietaet=3)
    assert len(st.gewicht_pro_varietaet) == 3
    g = [v for _, v in st.gewicht_pro_varietaet]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_varietaet_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_varietaet == []
    c.close()


def test_wert_pro_gesteinsart_aus_seed_db(tmp_path):
    """Wertsumme pro Gesteinsart, absteigend sortiert (petrologische Sicht)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Granit", 100.0, 200.0),    # Granit 300
            ("OBJ_0002", "Granit", 50.0, None),      # +50 -> 350
            ("OBJ_0003", "Gneis", 1000.0, None),     # Gneis 1000
            ("OBJ_0004", "Gneis", None, None),       # 0
            ("OBJ_0005", "Basalt", 10.0, None),
            ("OBJ_0006", "", 999.0, None),           # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),         # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_gesteinsart == [
        ("Gneis", 1000.0),
        ("Granit", 350.0),
        ("Basalt", 10.0),
    ]
    assert st.as_dict()["wert_pro_gesteinsart"] == [
        ("Gneis", 1000.0), ("Granit", 350.0), ("Basalt", 10.0),
    ]
    c.close()


def test_wert_pro_gesteinsart_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpg_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Ges{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_gesteinsart=3)
    assert len(st.wert_pro_gesteinsart) == 3
    werte = [w for _, w in st.wert_pro_gesteinsart]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_gesteinsart_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_gesteinsart == []
    c.close()


def test_gewicht_pro_gesteinsart_aus_seed_db(tmp_path):
    """Gewichtsumme pro Gesteinsart, absteigend; 0/NULL zaehlen nicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Granit", 100.0),
            ("OBJ_0002", "Granit", 50.0),       # Granit 150
            ("OBJ_0003", "Gneis", 1000.0),      # Gneis 1000
            ("OBJ_0004", "Gneis", None),        # NULL -> ignoriert
            ("OBJ_0005", "Basalt", 10.0),
            ("OBJ_0006", "", 999.0),            # leer -> ignoriert
            ("OBJ_0007", None, 999.0),          # NULL -> ignoriert
            ("OBJ_0008", "Sandstein", 0.0),     # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_gesteinsart == [
        ("Gneis", 1000.0),
        ("Granit", 150.0),
        ("Basalt", 10.0),
    ]
    assert st.as_dict()["gewicht_pro_gesteinsart"] == [
        ("Gneis", 1000.0), ("Granit", 150.0), ("Basalt", 10.0),
    ]
    c.close()


def test_gewicht_pro_gesteinsart_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpg_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Ges{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_gesteinsart=3)
    assert len(st.gewicht_pro_gesteinsart) == 3
    g = [v for _, v in st.gewicht_pro_gesteinsart]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_gesteinsart_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_gesteinsart == []
    c.close()


def test_top_confidence_objekte_aus_seed_db(tmp_path):
    """Am verlaesslichsten identifizierte Objekte absteigend nach Confidence."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tc.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Name, Confidence_Prozent) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Unsicher", 30),
            ("OBJ_0002", "Solide",   75),
            ("OBJ_0003", "Sicher",   95),
            ("OBJ_0004", "OhneConf", None),    # ignoriert (NULL)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.top_confidence_objekte == [
        ("OBJ_0003", "Sicher", 95),
        ("OBJ_0002", "Solide", 75),
        ("OBJ_0001", "Unsicher", 30),
    ]
    d = st.as_dict()
    assert d["top_confidence_objekte"] == [
        ("OBJ_0003", "Sicher", 95),
        ("OBJ_0002", "Solide", 75),
        ("OBJ_0001", "Unsicher", 30),
    ]
    c.close()


def test_top_confidence_objekte_ignoriert_out_of_range(tmp_path):
    """Out-of-Range-Werte (<0 / >100) tauchen nicht in der Liste auf."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tc_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Name, Confidence_Prozent) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Negativ", -5),    # out-of-range
            ("OBJ_0002", "Ueber",  150),    # out-of-range
            ("OBJ_0003", "Gueltig", 80),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.top_confidence_objekte == [("OBJ_0003", "Gueltig", 80)]
    c.close()


def test_top_confidence_objekte_limit_respektiert(tmp_path):
    """top_confidence=3 schneidet die Liste auf 3 Eintraege."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "tc_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [(f"OBJ_{i:04d}", i) for i in range(50, 100)],
    )
    c.commit()
    st = compute_statistics(c, top_confidence=3)
    assert len(st.top_confidence_objekte) == 3
    werte = [c for _, _, c in st.top_confidence_objekte]
    assert werte == [99, 98, 97]
    c.close()


def test_top_confidence_objekte_leer(tmp_path):
    """Ohne Confidence-Werte bleibt die Liste leer."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.top_confidence_objekte == []
    c.close()


def test_wert_pro_beste_verwendung_aus_seed_db(tmp_path):
    """Wertsumme pro Beste_Verwendung, absteigend sortiert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpbv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung, Wert_CHF_roh, "
        "Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Schmuck",   100.0, 200.0),    # Schmuck 300
            ("OBJ_0002", "Schmuck",    50.0, None),     # +50 -> 350
            ("OBJ_0003", "Sammlung", 1000.0, None),     # Sammlung 1000
            ("OBJ_0004", "Sammlung",  None, None),      # 0
            ("OBJ_0005", "Forschung",  10.0, None),     # Forschung 10
            ("OBJ_0006", "",          999.0, None),     # leer -> ignoriert
            ("OBJ_0007", None,        999.0, None),     # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_beste_verwendung == [
        ("Sammlung", 1000.0),
        ("Schmuck", 350.0),
        ("Forschung", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_beste_verwendung"] == [
        ("Sammlung", 1000.0), ("Schmuck", 350.0), ("Forschung", 10.0),
    ]
    c.close()


def test_wert_pro_beste_verwendung_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpbv_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung, Wert_CHF_roh) "
        "VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Use{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_beste_verwendung=3)
    assert len(st.wert_pro_beste_verwendung) == 3
    werte = [w for _, w in st.wert_pro_beste_verwendung]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_beste_verwendung_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_beste_verwendung == []
    c.close()


def test_gewicht_pro_beste_verwendung_aus_seed_db(tmp_path):
    """Gewichtsumme pro Beste_Verwendung, absteigend sortiert; 0/NULL ignoriert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpbv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "Industrie", 1000.0),
            ("OBJ_0002", "Sammlung",   100.0),
            ("OBJ_0003", "Sammlung",    50.0),   # Sammlung total 150
            ("OBJ_0004", "Schmuck",     10.0),
            ("OBJ_0005", "Schmuck",   None),     # NULL ignoriert
            ("OBJ_0006", "",          999.0),    # leer ignoriert
            ("OBJ_0007", None,        999.0),    # NULL ignoriert
            ("OBJ_0008", "Talisman",    0.0),    # 0 ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_beste_verwendung == [
        ("Industrie", 1000.0),
        ("Sammlung", 150.0),
        ("Schmuck", 10.0),
    ]
    assert st.as_dict()["gewicht_pro_beste_verwendung"] == [
        ("Industrie", 1000.0), ("Sammlung", 150.0), ("Schmuck", 10.0),
    ]
    c.close()


def test_gewicht_pro_beste_verwendung_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpbv_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Use{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_beste_verwendung=3)
    assert len(st.gewicht_pro_beste_verwendung) == 3
    g = [v for _, v in st.gewicht_pro_beste_verwendung]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_beste_verwendung_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_beste_verwendung == []
    c.close()
