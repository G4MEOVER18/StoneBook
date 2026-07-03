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
    # objekte_mit_alias <= aliase_total (mehrere Aliase pro Kanon-Objekt moeglich,
    # daher Anzahl gemergter Kanon-Objekte i.d.R. kleiner als Summe der Aliase)
    assert 0 < st.objekte_mit_alias <= st.aliase_total
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
    assert st.wert_min_chf == 300.0
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


def test_wert_min_chf_aus_seed_db(tmp_path):
    """wert_min_chf ist der kleinste Objekt-Wert > 0; NULL und 0 zaehlen nicht mit.

    Spiegelt test_gewicht_kennzahlen_aus_seed_db auf die Wert-Achse.
    Objekte ohne dokumentierten Wert (alle WERT_FELDER NULL) bleiben aussen
    vor, damit die Minimums-Achse nicht auf 0 zusammenbricht - spiegelt die
    objekte_mit_wert-Konvention.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wmin.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [
            ("OBJ_0001", 10.0),
            ("OBJ_0002", 50.0),
            ("OBJ_0003", 200.0),
            ("OBJ_0004", None),  # ignoriert
            ("OBJ_0005", 0.0),   # ignoriert (kein echter Wert)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 3
    assert st.wert_min_chf == 10.0
    assert st.wert_max_chf == 200.0
    assert st.wert_summe_chf == 260.0
    d = st.as_dict()
    assert d["wert_min_chf"] == 10.0
    assert d["wert_max_chf"] == 200.0
    c.close()


def test_wert_min_chf_leer(tmp_path):
    """Leere DB / keine Objekte mit Wert → wert_min_chf == 0.0 (dataclass-Default).

    Spiegelt test_gewicht_kennzahlen_leer auf die Wert-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 0
    assert st.wert_min_chf == 0.0
    assert st.wert_max_chf == 0.0
    c.close()


def test_wert_min_chf_einzelobjekt_gleich_max(tmp_path):
    """Bei genau einem Objekt mit Wert kollabieren Min und Max auf denselben Wert.

    Spiegelt test_gewicht_min_einzelobjekt_gleich_max auf die Wert-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wmin_single.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 42.5), ("OBJ_0002", None), ("OBJ_0003", 0.0)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 1
    assert st.wert_min_chf == 42.5
    assert st.wert_max_chf == 42.5
    c.close()


def test_wert_min_chf_summiert_ueber_wert_felder(tmp_path):
    """wert_min_chf nutzt wert_pro_objekt_sql = Summe aller WERT_FELDER, nicht Einzelfeld.

    Kein Objekt haette einzeln den kleinsten Wert, wenn nur eines der 5
    WERT_FELDER betrachtet wuerde - hier zeigt der Test, dass die
    Aggregation aus wert_pro_objekt_sql greift (analog zu wert_max_chf /
    wert_summe_chf, die dieselbe Summe verwenden).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wmin_sum.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh, Wert_CHF_poliert, "
        "Wert_CHF_Schmuck, Marktwert_Industrie, Wissenschaftlicher_Wert_CHF) "
        "VALUES (?,?,?,?,?,?)",
        [
            # 5 + 5 + 5 + 5 + 5 = 25 (kleinster Objekt-Wert)
            ("OBJ_0001", 5.0, 5.0, 5.0, 5.0, 5.0),
            # 100 + 200 = 300
            ("OBJ_0002", 100.0, 200.0, None, None, None),
            # 50 + 400 = 450
            ("OBJ_0003", 50.0, None, None, None, 400.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 3
    assert st.wert_min_chf == 25.0
    assert st.wert_max_chf == 450.0
    c.close()


def test_wert_standardabweichung_aus_seed_db(tmp_path):
    """kollektion_standardabweichung = Populations-Std ueber Objekt-Werte.

    Ergaenzt Ø/Median (zentrale Tendenz) um die Dispersions-Achse. Vier
    Werte 100/200/300/400 → Ø=250, Varianz=((100-250)^2 + (200-250)^2 +
    (300-250)^2 + (400-250)^2)/4 = (22500+2500+2500+22500)/4 = 50000/4 =
    12500 → σ = sqrt(12500) ≈ 111.803. Spiegelt
    test_gewicht_standardabweichung_aus_seed_db auf die Wert-Achse;
    Population-Divisor n (nicht n-1).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_std.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [
            ("OBJ_0001", 100.0),
            ("OBJ_0002", 200.0),
            ("OBJ_0003", 300.0),
            ("OBJ_0004", 400.0),
            ("OBJ_0005", None),  # ignoriert
            ("OBJ_0006", 0.0),   # ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_durchschnitt_chf == 250.0
    assert st.wert_standardabweichung_chf == pytest.approx(
        12500.0 ** 0.5, abs=1e-9)
    d = st.as_dict()
    assert d["wert_standardabweichung_chf"] == pytest.approx(111.80, abs=1e-2)
    c.close()


def test_wert_standardabweichung_leer(tmp_path):
    """Ohne Wert-Pflege bleibt die Standardabweichung 0.0 (dataclass-Default).

    Spiegelt die uebrigen leeren-Wert-Kennzahlen (min/max/median/Ø = 0.0
    bei leerer DB), damit as_dict deterministisch bleibt und die CLI-Zeile
    im ohne-Wert-Fall gar nicht ausgibt (if objekte_mit_wert:).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_std_leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_standardabweichung_chf == 0.0
    d = st.as_dict()
    assert d["wert_standardabweichung_chf"] == 0.0
    c.close()


def test_wert_standardabweichung_einzelobjekt(tmp_path):
    """Bei einem einzelnen Wert-Eintrag kollabiert die Streuung auf 0.0.

    Keine Dispersion moeglich; spiegelt gewicht_standardabweichung Single-
    Point-Kollaps auf die Wert-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_std_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 500.0), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 1
    assert st.wert_standardabweichung_chf == 0.0
    c.close()


def test_wert_standardabweichung_uniform(tmp_path):
    """Bei identischen Werten ist die Streuung 0.0.

    Reine Feldspat-Sammlung ohne Preisdispersion: fuenf Stuecke CHF 50 →
    sigma 0.0. Kern-Eigenschaft der Populations-Std.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_std_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_%04d" % i, 50.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_standardabweichung_chf == 0.0
    c.close()


def test_wert_standardabweichung_reagiert_auf_ausreisser(tmp_path):
    """Standardabweichung reagiert stark auf Wert-Ausreisser (Komplement zum Median).

    Typische versicherungsrelevante Konstellation: neun gleichmaessige
    Feldspat-Stuecke (CHF 50) plus ein Investment-Bergkristall (CHF 5000).
    Ø = (9*50 + 5000)/10 = 545, Var = (9*(50-545)^2 + (5000-545)^2)/10 =
    (9*245025 + 19847025)/10 = (2205225 + 19847025)/10 = 22052250/10 =
    2205225 → σ = sqrt(2205225) = 1485.0 exakt (1485*1485 = 2205225).
    Spiegelt test_gewicht_standardabweichung_reagiert_auf_ausreisser auf
    die Wert-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_std_ausreisser.sqlite3")
    feldspat = [("OBJ_%04d" % i, 50.0) for i in range(1, 10)]
    feldspat.append(("OBJ_0010", 5000.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        feldspat,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_standardabweichung_chf == pytest.approx(1485.0, abs=1e-6)
    # Median bleibt bei 50.0 (5. Element der sortierten Liste)
    assert st.wert_median_chf == 50.0
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


def test_by_erstellt_am_jahr_aus_seed_db(tmp_path):
    """Sammlungswachstum-Histogramm zaehlt Objekte pro erstellt_am-Jahr."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "wachstum.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-01-15 09:00:00"),
            ("OBJ_0002", "2024-08-13 14:30:00"),
            ("OBJ_0003", "2025-03-01 11:00:00"),
            ("OBJ_0004", "2026-06-19 08:45:00"),
            ("OBJ_0005", "2026-06-19 09:00:00"),
            ("OBJ_0006", ""),        # leer
            ("OBJ_0007", None),      # NULL
            ("OBJ_0008", "kaputt"),  # kein Jahres-Praefix
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Chronologisch aufsteigend, kaputte/leere Stempel ignoriert
    assert list(st.by_erstellt_am_jahr.items()) == [
        ("2024", 2), ("2025", 1), ("2026", 2),
    ]
    c.close()


def test_by_erstellt_am_jahr_leer(tmp_path):
    """Leere DB → leeres Wachstums-Histogramm (kein Crash)."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_wachstum.sqlite3")
    st = compute_statistics(c)
    assert st.by_erstellt_am_jahr == {}
    c.close()


def test_by_erstellt_am_jahr_im_as_dict(tmp_path):
    """Neues Feld erscheint serialisiert in as_dict() (JSON-tauglich)."""
    import json

    from stonebook.db.database import open_db

    c = open_db(tmp_path / "ad.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        ("OBJ_0001", "2026-06-19 08:00:00"),
    )
    c.commit()
    d = compute_statistics(c).as_dict()
    assert d["by_erstellt_am_jahr"] == {"2026": 1}
    json.dumps(d, ensure_ascii=False)
    c.close()


def test_by_erstellt_am_jahrzehnt_aus_seed_db(tmp_path):
    """Erfassungs-Dekaden-Histogramm aggregiert die Jahre auf 10er-Schritte."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dekade_e.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            # 2010er: 2x (handgepflegte Phase)
            ("OBJ_0001", "2014-05-12 09:00:00"),
            ("OBJ_0002", "2018-11-03 16:45:00"),
            # 2020er: 4x (Excel-Migrationswelle)
            ("OBJ_0003", "2020-01-15 09:00:00"),
            ("OBJ_0004", "2024-06-13 14:30:00"),
            ("OBJ_0005", "2025-03-01 11:00:00"),
            ("OBJ_0006", "2029-12-31 23:59:59"),
            # Ausgeschlossene: leer/NULL/kein Jahres-Praefix
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
            ("OBJ_0009", "kaputt"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Chronologisch aufsteigend, Label mit 'er'-Suffix
    assert list(st.by_erstellt_am_jahrzehnt.items()) == [
        ("2010er", 2), ("2020er", 4),
    ]
    c.close()


def test_by_erstellt_am_jahrzehnt_leer(tmp_path):
    """Ohne erstellt_am-Stempel ist die Erfassungs-Dekaden-Verteilung leer."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_dekade_e.sqlite3")
    st = compute_statistics(c)
    assert st.by_erstellt_am_jahrzehnt == {}
    c.close()


def test_by_erstellt_am_jahrzehnt_im_as_dict(tmp_path):
    """by_erstellt_am_jahrzehnt erscheint serialisiert in as_dict() (JSON-tauglich)."""
    import json

    from stonebook.db.database import open_db

    c = open_db(tmp_path / "ad_dekade_e.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        ("OBJ_0001", "2026-06-19 08:00:00"),
    )
    c.commit()
    d = compute_statistics(c).as_dict()
    assert d["by_erstellt_am_jahrzehnt"] == {"2020er": 1}
    json.dumps(d, ensure_ascii=False)
    c.close()


def test_by_erstellt_am_monat_aus_seed_db(tmp_path):
    """Erfassungs-Saisonalitaet aggregiert ueber alle Jahre zu Monatsziffern 01..12."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "monat_e.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            # Januar (2024 + 2026)
            ("OBJ_0001", "2024-01-15 09:00:00"),
            ("OBJ_0002", "2026-01-04 11:30:00"),
            # Juni (2024 + 2025 + 2026)
            ("OBJ_0003", "2024-06-13 14:30:00"),
            ("OBJ_0004", "2025-06-01 10:00:00"),
            ("OBJ_0005", "2026-06-19 08:45:00"),
            # August (2025)
            ("OBJ_0006", "2025-08-21 16:00:00"),
            # Ungueltig / leer
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
            ("OBJ_0009", "kaputt"),
            ("OBJ_0010", "2024-13-01 00:00:00"),  # Monat 13 → ungueltig
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Aufsteigend nach Monat (01..12), kaputte Eintraege bleiben aussen vor
    assert list(st.by_erstellt_am_monat.items()) == [
        ("01", 2), ("06", 3), ("08", 1),
    ]
    c.close()


def test_by_erstellt_am_monat_leer(tmp_path):
    """Leere DB → leere Saison-Statistik (kein Crash)."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_monat_e.sqlite3")
    st = compute_statistics(c)
    assert st.by_erstellt_am_monat == {}
    c.close()


def test_by_geaendert_am_jahr_aus_seed_db(tmp_path):
    """Pflege-Aktivitaets-Histogramm zaehlt Objekte pro geaendert_am-Jahr."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "pflege.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-01-15 09:00:00"),
            ("OBJ_0002", "2024-08-13 14:30:00"),
            ("OBJ_0003", "2025-03-01 11:00:00"),
            ("OBJ_0004", "2026-06-19 08:45:00"),
            ("OBJ_0005", "2026-06-19 09:00:00"),
            ("OBJ_0006", ""),        # leer
            ("OBJ_0007", None),      # NULL
            ("OBJ_0008", "kaputt"),  # kein Jahres-Praefix
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Chronologisch aufsteigend, kaputte/leere Stempel ignoriert
    assert list(st.by_geaendert_am_jahr.items()) == [
        ("2024", 2), ("2025", 1), ("2026", 2),
    ]
    c.close()


def test_by_geaendert_am_jahr_leer(tmp_path):
    """Leere DB → leeres Pflege-Histogramm (kein Crash)."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_pflege.sqlite3")
    st = compute_statistics(c)
    assert st.by_geaendert_am_jahr == {}
    c.close()


def test_by_geaendert_am_jahr_im_as_dict(tmp_path):
    """Neues Feld erscheint serialisiert in as_dict() (JSON-tauglich)."""
    import json

    from stonebook.db.database import open_db

    c = open_db(tmp_path / "ad_pflege.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        ("OBJ_0001", "2026-06-19 08:00:00"),
    )
    c.commit()
    d = compute_statistics(c).as_dict()
    assert d["by_geaendert_am_jahr"] == {"2026": 1}
    json.dumps(d, ensure_ascii=False)
    c.close()


def test_by_geaendert_am_jahrzehnt_aus_seed_db(tmp_path):
    """Pflege-Dekaden-Histogramm aggregiert die Jahre auf 10er-Schritte."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dekade_p.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [
            # 2010er: 2x (handgepflegte Phase)
            ("OBJ_0001", "2014-05-12 09:00:00"),
            ("OBJ_0002", "2018-11-03 16:45:00"),
            # 2020er: 4x (KI-Welle)
            ("OBJ_0003", "2020-01-15 09:00:00"),
            ("OBJ_0004", "2024-06-13 14:30:00"),
            ("OBJ_0005", "2025-03-01 11:00:00"),
            ("OBJ_0006", "2029-12-31 23:59:59"),
            # Ausgeschlossene: leer/NULL/kein Jahres-Praefix
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
            ("OBJ_0009", "kaputt"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Chronologisch aufsteigend, Label mit 'er'-Suffix
    assert list(st.by_geaendert_am_jahrzehnt.items()) == [
        ("2010er", 2), ("2020er", 4),
    ]
    c.close()


def test_by_geaendert_am_jahrzehnt_leer(tmp_path):
    """Ohne geaendert_am-Stempel ist die Pflege-Dekaden-Verteilung leer."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_dekade_p.sqlite3")
    st = compute_statistics(c)
    assert st.by_geaendert_am_jahrzehnt == {}
    c.close()


def test_by_geaendert_am_jahrzehnt_im_as_dict(tmp_path):
    """by_geaendert_am_jahrzehnt erscheint serialisiert in as_dict() (JSON-tauglich)."""
    import json

    from stonebook.db.database import open_db

    c = open_db(tmp_path / "ad_dekade_p.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        ("OBJ_0001", "2026-06-19 08:00:00"),
    )
    c.commit()
    d = compute_statistics(c).as_dict()
    assert d["by_geaendert_am_jahrzehnt"] == {"2020er": 1}
    json.dumps(d, ensure_ascii=False)
    c.close()


def test_by_geaendert_am_monat_aus_seed_db(tmp_path):
    """Pflege-Saisonalitaet aggregiert ueber alle Jahre zu Monatsziffern 01..12."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "monat_p.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [
            # Januar (2024 + 2026) - Winter-Indoor-Pflege
            ("OBJ_0001", "2024-01-15 09:00:00"),
            ("OBJ_0002", "2026-01-04 11:30:00"),
            # Juni (2024 + 2025 + 2026) - KI-Analyse-Welle
            ("OBJ_0003", "2024-06-13 14:30:00"),
            ("OBJ_0004", "2025-06-01 10:00:00"),
            ("OBJ_0005", "2026-06-19 08:45:00"),
            # August (2025) - Sommer-Sammlungsdurchsicht
            ("OBJ_0006", "2025-08-21 16:00:00"),
            # Ungueltig / leer - werden defensiv ausgeschlossen
            ("OBJ_0007", ""),
            ("OBJ_0008", None),
            ("OBJ_0009", "kaputt"),
            ("OBJ_0010", "2024-13-01 00:00:00"),  # Monat 13 → ungueltig
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Aufsteigend nach Monat (01..12), kaputte Eintraege bleiben aussen vor
    assert list(st.by_geaendert_am_monat.items()) == [
        ("01", 2), ("06", 3), ("08", 1),
    ]
    c.close()


def test_by_geaendert_am_monat_leer(tmp_path):
    """Leere DB → leere Pflege-Saison-Statistik (kein Crash)."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_monat_p.sqlite3")
    st = compute_statistics(c)
    assert st.by_geaendert_am_monat == {}
    c.close()


def test_by_geaendert_am_monat_im_as_dict(tmp_path):
    """by_geaendert_am_monat erscheint serialisiert in as_dict() (JSON-tauglich)."""
    import json

    from stonebook.db.database import open_db

    c = open_db(tmp_path / "ad_monat_p.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        ("OBJ_0001", "2026-06-19 08:00:00"),
    )
    c.commit()
    d = compute_statistics(c).as_dict()
    assert d["by_geaendert_am_monat"] == {"06": 1}
    json.dumps(d, ensure_ascii=False)
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


def test_by_seltenheit_global_aus_seed_db(tmp_path):
    """Histogramm der globalen Seltenheit (1..10), aufsteigend nach Skalenwert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "selt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 1),
            ("OBJ_0002", 1),
            ("OBJ_0003", 5),
            ("OBJ_0004", 8),
            ("OBJ_0005", 10),
            ("OBJ_0006", None),  # NULL ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Reihenfolge: chronologisch nach Skalenwert (1..10 aufsteigend) - sorgt fuer
    # ein lesbares Rarity-Profil. Werte ohne Treffer fehlen im Dict.
    assert list(st.by_seltenheit_global.items()) == [
        ("1", 2), ("5", 1), ("8", 1), ("10", 1),
    ]
    assert st.as_dict()["by_seltenheit_global"] == {
        "1": 2, "5": 1, "8": 1, "10": 1,
    }
    c.close()


def test_by_seltenheit_global_ignoriert_out_of_range(tmp_path):
    """Out-of-range-Werte (<1 / >10) zaehlen nicht (Integrity meldet die separat)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "selt_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 0),       # out-of-range
            ("OBJ_0002", 11),      # out-of-range
            ("OBJ_0003", 5),       # gueltig
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_seltenheit_global == {"5": 1}
    c.close()


def test_by_seltenheit_global_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_seltenheit_global == {}
    c.close()


def test_by_seltenheit_fundort_aus_seed_db(tmp_path):
    """Standort-Rarity-Histogramm 1..10 spiegelt by_seltenheit_global."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "selt_fo.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 2),
            ("OBJ_0002", 2),
            ("OBJ_0003", 2),
            ("OBJ_0004", 6),
            ("OBJ_0005", 9),
            ("OBJ_0006", None),  # NULL ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert list(st.by_seltenheit_fundort.items()) == [
        ("2", 3), ("6", 1), ("9", 1),
    ]
    assert st.as_dict()["by_seltenheit_fundort"] == {"2": 3, "6": 1, "9": 1}
    c.close()


def test_by_seltenheit_fundort_ignoriert_out_of_range(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "selt_fo_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 0),       # out-of-range
            ("OBJ_0002", 11),      # out-of-range
            ("OBJ_0003", 7),       # gueltig
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_seltenheit_fundort == {"7": 1}
    c.close()


def test_by_seltenheit_fundort_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer_fo.sqlite3")
    st = compute_statistics(c)
    assert st.by_seltenheit_fundort == {}
    c.close()


def test_by_nachfrage_aus_seed_db(tmp_path):
    """Marktnachfrage-Histogramm 1..10 spiegelt by_seltenheit_global."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nach.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 3),
            ("OBJ_0002", 3),
            ("OBJ_0003", 7),
            ("OBJ_0004", 8),
            ("OBJ_0005", 10),
            ("OBJ_0006", None),  # NULL ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert list(st.by_nachfrage.items()) == [
        ("3", 2), ("7", 1), ("8", 1), ("10", 1),
    ]
    assert st.as_dict()["by_nachfrage"] == {"3": 2, "7": 1, "8": 1, "10": 1}
    c.close()


def test_by_nachfrage_ignoriert_out_of_range(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nach_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?, ?)",
        [
            ("OBJ_0001", 0),       # out-of-range
            ("OBJ_0002", 11),      # out-of-range
            ("OBJ_0003", 4),       # gueltig
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_nachfrage == {"4": 1}
    c.close()


def test_by_nachfrage_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer_nach.sqlite3")
    st = compute_statistics(c)
    assert st.by_nachfrage == {}
    c.close()


def test_count_scale_1_10_validiert_spalte(tmp_path):
    """_count_scale_1_10 weist nicht-gewhitelistete Spalten ab (kein SQL-Injection-Vektor)."""
    from stonebook.db.database import open_db
    from stonebook.db.stats import _count_scale_1_10
    c = open_db(tmp_path / "v.sqlite3")
    with pytest.raises(ValueError, match="Skalen-Spalte"):
        _count_scale_1_10(c, "Confidence_Prozent")  # nicht in Whitelist
    with pytest.raises(ValueError, match="Skalen-Spalte"):
        _count_scale_1_10(c, "1; DROP TABLE objects --")
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


def test_wert_pro_erstellt_am_jahr_aus_seed_db(tmp_path):
    """Wertsumme pro erstellt_am-Jahr, absteigend; spiegelt wert_pro_funddatum_jahr.

    Spiegelt die Erfassungs-Achse: Migrations-Wellen (viele Altbestaende auf
    einmal eingespielt) tauchen hier nach Wert sortiert auf, waehrend
    wert_pro_funddatum_jahr nach Fund-Jahr aggregiert. Tie-Break bleibt
    chronologisch wie beim Fund-Pendant.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpej.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # 2024: ein Riesenstueck (1000)
            ("OBJ_0001", "2024-05-13 09:00:00", 1000.0, None),
            # 2025: zwei Stuecke -> 300
            ("OBJ_0002", "2025-04-01 14:00:00", 100.0, 200.0),
            ("OBJ_0003", "2025-09-15 10:00:00", None, None),     # 0
            # 2026: drei Stuecke -> 300 (Tie-Break: chronologisch nach 2025)
            ("OBJ_0004", "2026-03-01 08:00:00", 100.0, None),
            ("OBJ_0005", "2026-07-10 11:30:00", 100.0, None),
            ("OBJ_0006", "2026-11-30 16:00:00", 100.0, None),
            # 2027: ein Stueck ohne Wert -> faellt raus
            ("OBJ_0007", "2027-01-01 09:00:00", None, None),
            # Ungueltige/leere erstellt_am -> ignoriert
            ("OBJ_0008", "", 999.0, None),
            ("OBJ_0009", None, 999.0, None),
            ("OBJ_0010", "kaputt", 999.0, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 2024 (1000) > 2025 (300) == 2026 (300) -> Tie-Break aufsteigend nach Jahr.
    assert st.wert_pro_erstellt_am_jahr == [
        ("2024", 1000.0),
        ("2025", 300.0),
        ("2026", 300.0),
    ]
    assert st.as_dict()["wert_pro_erstellt_am_jahr"] == [
        ("2024", 1000.0), ("2025", 300.0), ("2026", 300.0),
    ]
    c.close()


def test_wert_pro_erstellt_am_jahr_limit(tmp_path):
    """top_wert_erstellt_am_jahr begrenzt die Listenlaenge; behalten die Top-N."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpej_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"20{i:02d}-01-01 12:00:00", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_erstellt_am_jahr=3)
    assert len(st.wert_pro_erstellt_am_jahr) == 3
    werte = [w for _, w in st.wert_pro_erstellt_am_jahr]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_erstellt_am_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_erstellt_am_jahr == []
    c.close()


def test_gewicht_pro_erstellt_am_jahr_aus_seed_db(tmp_path):
    """Gewichtsumme pro erstellt_am-Jahr; NULL/0 zaehlen nicht, kaputte Stempel ignoriert.

    Spiegelt gewicht_pro_funddatum_jahr auf die Erfassungs-Achse: zeigt, in
    welchem Erfassungs-Jahr die schwerste Masse eingespielt wurde - typisch
    fuer Migrations-Wellen mit Geroell-Altbestaenden.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpej.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "2024-05-13 09:00:00", 1000.0),
            ("OBJ_0002", "2025-04-01 14:00:00", 100.0),
            ("OBJ_0003", "2025-09-15 10:00:00", 150.0),   # 2025 total 250
            ("OBJ_0004", "2026-03-01 08:00:00", 50.0),
            ("OBJ_0005", "2026-07-10 11:30:00", None),    # NULL -> ignoriert
            ("OBJ_0006", "2026-11-30 16:00:00", 0.0),     # 0 -> ignoriert
            # Kaputte Stempel werden ignoriert
            ("OBJ_0007", "kaputt", 9999.0),
            ("OBJ_0008", None, 9999.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_erstellt_am_jahr == [
        ("2024", 1000.0),
        ("2025", 250.0),
        ("2026", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_erstellt_am_jahr"] == [
        ("2024", 1000.0), ("2025", 250.0), ("2026", 50.0),
    ]
    c.close()


def test_gewicht_pro_erstellt_am_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_erstellt_am_jahr == []
    c.close()


def test_wert_pro_geaendert_am_jahr_aus_seed_db(tmp_path):
    """Wertsumme pro geaendert_am-Jahr, absteigend; vervollstaendigt das Zeit-Trio.

    Aenderungs-Achse: zeigt, in welchem Pflege-Jahr wertlich am meisten
    redaktionell angefasst wurde - unterscheidet sich strukturell von
    wert_pro_erstellt_am_jahr bei nachgepflegten Stuecken, deren
    geaendert_am vom urspruenglichen Erfassungs-Jahr abdriftet.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpgj.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # 2024 (1000) - nie nachgepflegt nach Erfassung
            ("OBJ_0001", "2024-05-13 09:00:00", 1000.0, None),
            # 2025 zwei Stuecke -> 300
            ("OBJ_0002", "2025-04-01 14:00:00", 100.0, 200.0),
            ("OBJ_0003", "2025-09-15 10:00:00", None, None),     # 0
            # 2026 drei Stuecke -> 300 (Tie-Break: chronologisch nach 2025)
            ("OBJ_0004", "2026-03-01 08:00:00", 100.0, None),
            ("OBJ_0005", "2026-07-10 11:30:00", 100.0, None),
            ("OBJ_0006", "2026-11-30 16:00:00", 100.0, None),
            # 2027 ohne Wert -> faellt raus
            ("OBJ_0007", "2027-01-01 09:00:00", None, None),
            # Ungueltige/leere geaendert_am -> ignoriert
            ("OBJ_0008", "", 999.0, None),
            ("OBJ_0009", None, 999.0, None),
            ("OBJ_0010", "kaputt", 999.0, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 2024 (1000) > 2025 (300) == 2026 (300) -> Tie-Break aufsteigend nach Jahr.
    assert st.wert_pro_geaendert_am_jahr == [
        ("2024", 1000.0),
        ("2025", 300.0),
        ("2026", 300.0),
    ]
    assert st.as_dict()["wert_pro_geaendert_am_jahr"] == [
        ("2024", 1000.0), ("2025", 300.0), ("2026", 300.0),
    ]
    c.close()


def test_wert_pro_geaendert_am_jahr_limit(tmp_path):
    """top_wert_geaendert_am_jahr begrenzt die Listenlaenge; behalten die Top-N."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpgj_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"20{i:02d}-01-01 12:00:00", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_geaendert_am_jahr=3)
    assert len(st.wert_pro_geaendert_am_jahr) == 3
    werte = [w for _, w in st.wert_pro_geaendert_am_jahr]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_geaendert_am_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_geaendert_am_jahr == []
    c.close()


def test_gewicht_pro_geaendert_am_jahr_aus_seed_db(tmp_path):
    """Gewichtsumme pro geaendert_am-Jahr; NULL/0 zaehlen nicht, kaputte Stempel ignoriert.

    Spiegelt gewicht_pro_erstellt_am_jahr auf die Aenderungs-Achse; bei
    nie-aktualisierten Alt-Eintraegen konvergieren beide Aggregate.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpgj.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "2024-05-13 09:00:00", 1000.0),
            ("OBJ_0002", "2025-04-01 14:00:00", 100.0),
            ("OBJ_0003", "2025-09-15 10:00:00", 150.0),   # 2025 total 250
            ("OBJ_0004", "2026-03-01 08:00:00", 50.0),
            ("OBJ_0005", "2026-07-10 11:30:00", None),    # NULL -> ignoriert
            ("OBJ_0006", "2026-11-30 16:00:00", 0.0),     # 0 -> ignoriert
            # Kaputte Stempel werden ignoriert
            ("OBJ_0007", "kaputt", 9999.0),
            ("OBJ_0008", None, 9999.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_geaendert_am_jahr == [
        ("2024", 1000.0),
        ("2025", 250.0),
        ("2026", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_geaendert_am_jahr"] == [
        ("2024", 1000.0), ("2025", 250.0), ("2026", 50.0),
    ]
    c.close()


def test_gewicht_pro_geaendert_am_jahr_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_geaendert_am_jahr == []
    c.close()


def test_wert_pro_erstellt_am_monat_aus_seed_db(tmp_path):
    """Wertsumme pro erstellt_am-Monat aggregiert ueber alle Jahre.

    Spiegelt wert_pro_funddatum_monat auf die Erfassungs-Achse: zeigt
    Indoor-Erfassungs-Spitzen (Winter/Boersen-Vorbereitung) wertlich.
    Sortierung absteigend nach Summe, Tie-Break aufsteigend nach Monat.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpem.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # Januar (2024+2026): 100+200 = 300
            ("OBJ_0001", "2024-01-15 09:00:00", 100.0, None),
            ("OBJ_0002", "2026-01-04 11:30:00", 100.0, 100.0),
            # Juni (2024+2025+2026): 50+50+50 = 150
            ("OBJ_0003", "2024-06-13 14:30:00", 50.0, None),
            ("OBJ_0004", "2025-06-01 10:00:00", 50.0, None),
            ("OBJ_0005", "2026-06-19 08:45:00", 50.0, None),
            # August (2025): 150 - genau wie Juni → Tie-Break aufsteigend "06" vor "08"
            ("OBJ_0006", "2025-08-21 16:00:00", 150.0, None),
            # Ohne Wert -> faellt raus
            ("OBJ_0007", "2024-03-01 12:00:00", None, None),
            # Ungueltig / leer
            ("OBJ_0008", "", 999.0, None),
            ("OBJ_0009", None, 999.0, None),
            ("OBJ_0010", "kaputt", 999.0, None),
            ("OBJ_0011", "2024-13-01 00:00:00", 999.0, None),  # Monat 13 → ungueltig
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 01 (300) > 06 (150) == 08 (150) → Tie-Break "06" vor "08"
    assert st.wert_pro_erstellt_am_monat == [
        ("01", 300.0),
        ("06", 150.0),
        ("08", 150.0),
    ]
    assert st.as_dict()["wert_pro_erstellt_am_monat"] == [
        ("01", 300.0), ("06", 150.0), ("08", 150.0),
    ]
    c.close()


def test_wert_pro_erstellt_am_monat_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_erstellt_am_monat == []
    c.close()


def test_gewicht_pro_erstellt_am_monat_aus_seed_db(tmp_path):
    """Gewichtsumme pro erstellt_am-Monat; NULL/0 zaehlen nicht, kaputte ignoriert.

    Spiegelt wert_pro_erstellt_am_monat - schwere Erfassungs-Spitzen
    (Geroell-Migrations-Wellen) entkoppeln sich oft vom Wert-Profil.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpem.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Gewicht_g) VALUES (?,?,?)",
        [
            # Januar: 600
            ("OBJ_0001", "2024-01-15 09:00:00", 300.0),
            ("OBJ_0002", "2026-01-04 11:30:00", 300.0),
            # Juni: 200
            ("OBJ_0003", "2024-06-13 14:30:00", 100.0),
            ("OBJ_0004", "2025-06-01 10:00:00", 100.0),
            # Mai: NULL/0 → ignoriert
            ("OBJ_0005", "2024-05-13 09:00:00", None),
            ("OBJ_0006", "2024-05-14 09:00:00", 0.0),
            # Ungueltige Stempel: ignoriert
            ("OBJ_0007", "kaputt", 9999.0),
            ("OBJ_0008", "2024-13-01 00:00:00", 9999.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_erstellt_am_monat == [
        ("01", 600.0),
        ("06", 200.0),
    ]
    assert st.as_dict()["gewicht_pro_erstellt_am_monat"] == [
        ("01", 600.0), ("06", 200.0),
    ]
    c.close()


def test_gewicht_pro_erstellt_am_monat_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_erstellt_am_monat == []
    c.close()


def test_wert_pro_geaendert_am_monat_aus_seed_db(tmp_path):
    """Wertsumme pro geaendert_am-Monat aggregiert ueber alle Jahre.

    Spiegelt wert_pro_erstellt_am_monat auf die Aenderungs-Achse: zeigt
    Pflege-Spitzen (Boersen-Nachpflege, Neu-Klassifizierungs-Wellen) wertlich.
    Sortierung absteigend nach Summe, Tie-Break aufsteigend nach Monat.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpgm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # Januar (2024+2026): 100+200 = 300
            ("OBJ_0001", "2024-01-15 09:00:00", 100.0, None),
            ("OBJ_0002", "2026-01-04 11:30:00", 100.0, 100.0),
            # Juni (2024+2025+2026): 50+50+50 = 150
            ("OBJ_0003", "2024-06-13 14:30:00", 50.0, None),
            ("OBJ_0004", "2025-06-01 10:00:00", 50.0, None),
            ("OBJ_0005", "2026-06-19 08:45:00", 50.0, None),
            # August (2025): 150 - genau wie Juni -> Tie-Break aufsteigend "06" vor "08"
            ("OBJ_0006", "2025-08-21 16:00:00", 150.0, None),
            # Ohne Wert -> faellt raus
            ("OBJ_0007", "2024-03-01 12:00:00", None, None),
            # Ungueltig / leer
            ("OBJ_0008", "", 999.0, None),
            ("OBJ_0009", None, 999.0, None),
            ("OBJ_0010", "kaputt", 999.0, None),
            ("OBJ_0011", "2024-13-01 00:00:00", 999.0, None),  # Monat 13 -> ungueltig
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 01 (300) > 06 (150) == 08 (150) -> Tie-Break "06" vor "08"
    assert st.wert_pro_geaendert_am_monat == [
        ("01", 300.0),
        ("06", 150.0),
        ("08", 150.0),
    ]
    assert st.as_dict()["wert_pro_geaendert_am_monat"] == [
        ("01", 300.0), ("06", 150.0), ("08", 150.0),
    ]
    c.close()


def test_wert_pro_geaendert_am_monat_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_geaendert_am_monat == []
    c.close()


def test_gewicht_pro_geaendert_am_monat_aus_seed_db(tmp_path):
    """Gewichtsumme pro geaendert_am-Monat; NULL/0 zaehlen nicht, kaputte ignoriert.

    Spiegelt wert_pro_geaendert_am_monat - schwere Pflege-Spitzen entkoppeln
    sich oft vom Wert-Profil (eine Geroell-Nachpflege-Welle traegt Masse,
    aber wenig Wert).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpgm.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am, Gewicht_g) VALUES (?,?,?)",
        [
            # Januar: 600
            ("OBJ_0001", "2024-01-15 09:00:00", 300.0),
            ("OBJ_0002", "2026-01-04 11:30:00", 300.0),
            # Juni: 200
            ("OBJ_0003", "2024-06-13 14:30:00", 100.0),
            ("OBJ_0004", "2025-06-01 10:00:00", 100.0),
            # Mai: NULL/0 -> ignoriert
            ("OBJ_0005", "2024-05-13 09:00:00", None),
            ("OBJ_0006", "2024-05-14 09:00:00", 0.0),
            # Ungueltige Stempel: ignoriert
            ("OBJ_0007", "kaputt", 9999.0),
            ("OBJ_0008", "2024-13-01 00:00:00", 9999.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_geaendert_am_monat == [
        ("01", 600.0),
        ("06", 200.0),
    ]
    assert st.as_dict()["gewicht_pro_geaendert_am_monat"] == [
        ("01", 600.0), ("06", 200.0),
    ]
    c.close()


def test_gewicht_pro_geaendert_am_monat_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_geaendert_am_monat == []
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


def test_wert_pro_erstellt_am_jahrzehnt_aus_seed_db(tmp_path):
    """Wertsumme pro Erfassungs-Dekade; absteigend nach Summe, Tie-Break chronologisch.

    Spiegelt wert_pro_funddatum_jahrzehnt auf die Erfassungs-Achse: macht
    uebergreifende Erfassungs-Wellen (Excel-Migration 2020+) wertlich sichtbar,
    die im Einzeljahr-Histogramm durch Rauschen verdeckt sind.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpeej.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # 2000er: ein Riesenstueck (1000)
            ("OBJ_0001", "2005-06-13 09:00:00", 1000.0, None),
            # 2010er: zwei Stuecke -> 300
            ("OBJ_0002", "2013-01-01 14:00:00", 100.0, 200.0),
            ("OBJ_0003", "2018-09-15 10:00:00", None, None),     # 0
            # 2020er: drei Stuecke -> 300 (Tie-Break: chronologisch nach 2010er)
            ("OBJ_0004", "2020-03-01 08:00:00", 100.0, None),
            ("OBJ_0005", "2024-07-10 11:30:00", 100.0, None),
            ("OBJ_0006", "2029-11-30 16:00:00", 100.0, None),
            # Ungueltige/leere erstellt_am -> ignoriert
            ("OBJ_0007", "", 999.0, None),
            ("OBJ_0008", None, 999.0, None),
            ("OBJ_0009", "kaputt", 999.0, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 2000er (1000) > 2010er (300) == 2020er (300) -> Tie-Break aufsteigend.
    assert st.wert_pro_erstellt_am_jahrzehnt == [
        ("2000er", 1000.0),
        ("2010er", 300.0),
        ("2020er", 300.0),
    ]
    assert st.as_dict()["wert_pro_erstellt_am_jahrzehnt"] == [
        ("2000er", 1000.0), ("2010er", 300.0), ("2020er", 300.0),
    ]
    c.close()


def test_wert_pro_erstellt_am_jahrzehnt_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_erstellt_am_jahrzehnt == []
    c.close()


def test_gewicht_pro_erstellt_am_jahrzehnt_aus_seed_db(tmp_path):
    """Gewichtsumme pro Erfassungs-Dekade; NULL/0 zaehlen nicht, kaputte Stempel ignoriert.

    Spiegelt gewicht_pro_funddatum_jahrzehnt auf die Erfassungs-Achse: zeigt,
    in welcher Erfassungs-Dekade die schwerste Masse eingespielt wurde - typisch
    fuer Migrations-Wellen mit Geroell-Altbestaenden.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpeej.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "2005-06-13 09:00:00", 1000.0),
            ("OBJ_0002", "2013-04-01 14:00:00", 100.0),
            ("OBJ_0003", "2018-09-15 10:00:00", 150.0),   # 2010er total 250
            ("OBJ_0004", "2020-03-01 08:00:00", 50.0),
            ("OBJ_0005", "2025-07-10 11:30:00", None),    # NULL -> ignoriert
            ("OBJ_0006", "2029-11-30 16:00:00", 0.0),     # 0 -> ignoriert
            # Kaputte Stempel werden ignoriert
            ("OBJ_0007", "kaputt", 9999.0),
            ("OBJ_0008", None, 9999.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_erstellt_am_jahrzehnt == [
        ("2000er", 1000.0),
        ("2010er", 250.0),
        ("2020er", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_erstellt_am_jahrzehnt"] == [
        ("2000er", 1000.0), ("2010er", 250.0), ("2020er", 50.0),
    ]
    c.close()


def test_gewicht_pro_erstellt_am_jahrzehnt_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_erstellt_am_jahrzehnt == []
    c.close()


def test_wert_pro_geaendert_am_jahrzehnt_aus_seed_db(tmp_path):
    """Wertsumme pro Pflege-Dekade; absteigend nach Summe, Tie-Break chronologisch.

    Spiegelt wert_pro_erstellt_am_jahrzehnt auf die Aenderungs-Achse; bei aktiv
    nachgepflegten Stuecken driftet die Spitze von der Erfassungs- in die
    Pflege-Dekade.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpgaj.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            # 2000er: ein Riesenstueck (1000)
            ("OBJ_0001", "2005-06-13 09:00:00", 1000.0, None),
            # 2010er: zwei Stuecke -> 300
            ("OBJ_0002", "2013-01-01 14:00:00", 100.0, 200.0),
            ("OBJ_0003", "2018-09-15 10:00:00", None, None),     # 0
            # 2020er: drei Stuecke -> 300 (Tie-Break: chronologisch nach 2010er)
            ("OBJ_0004", "2020-03-01 08:00:00", 100.0, None),
            ("OBJ_0005", "2024-07-10 11:30:00", 100.0, None),
            ("OBJ_0006", "2029-11-30 16:00:00", 100.0, None),
            # Ungueltige/leere geaendert_am -> ignoriert
            ("OBJ_0007", "", 999.0, None),
            ("OBJ_0008", None, 999.0, None),
            ("OBJ_0009", "kaputt", 999.0, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # 2000er (1000) > 2010er (300) == 2020er (300) -> Tie-Break aufsteigend.
    assert st.wert_pro_geaendert_am_jahrzehnt == [
        ("2000er", 1000.0),
        ("2010er", 300.0),
        ("2020er", 300.0),
    ]
    assert st.as_dict()["wert_pro_geaendert_am_jahrzehnt"] == [
        ("2000er", 1000.0), ("2010er", 300.0), ("2020er", 300.0),
    ]
    c.close()


def test_wert_pro_geaendert_am_jahrzehnt_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_geaendert_am_jahrzehnt == []
    c.close()


def test_gewicht_pro_geaendert_am_jahrzehnt_aus_seed_db(tmp_path):
    """Gewichtsumme pro Pflege-Dekade; NULL/0 zaehlen nicht, kaputte Stempel ignoriert.

    Spiegelt gewicht_pro_erstellt_am_jahrzehnt auf die Aenderungs-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpgaj.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "2005-06-13 09:00:00", 1000.0),
            ("OBJ_0002", "2013-04-01 14:00:00", 100.0),
            ("OBJ_0003", "2018-09-15 10:00:00", 150.0),   # 2010er total 250
            ("OBJ_0004", "2020-03-01 08:00:00", 50.0),
            ("OBJ_0005", "2025-07-10 11:30:00", None),    # NULL -> ignoriert
            ("OBJ_0006", "2029-11-30 16:00:00", 0.0),     # 0 -> ignoriert
            # Kaputte Stempel werden ignoriert
            ("OBJ_0007", "kaputt", 9999.0),
            ("OBJ_0008", None, 9999.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_geaendert_am_jahrzehnt == [
        ("2000er", 1000.0),
        ("2010er", 250.0),
        ("2020er", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_geaendert_am_jahrzehnt"] == [
        ("2000er", 1000.0), ("2010er", 250.0), ("2020er", 50.0),
    ]
    c.close()


def test_gewicht_pro_geaendert_am_jahrzehnt_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_geaendert_am_jahrzehnt == []
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


def test_erstellt_am_spanne_aus_seed_db(tmp_path):
    """frueheste/spaeteste = MIN/MAX gueltiger erstellt_am-Werte (lex. sortierbar).

    Spiegelt test_funddatum_spanne_aus_seed_db auf die Erfassungs-Achse: zeigt
    den Zeitraum, in dem die Sammlung digitalisiert wurde. Voller Zeitstempel
    inkl. HH:MM:SS wird durchgereicht (anders als Funddatum mit reiner Tag-
    Aufloesung); kaputte/leere Stempel werden uebergangen, damit ein einzelner
    fehlerhafter Eintrag die Grenze nicht verzerrt.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "spanne_erstellt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-03-15 12:30:00"),
            ("OBJ_0002", "2023-06-01 08:00:00"),  # frueheste
            ("OBJ_0003", "2026-01-10 17:45:33"),  # spaeteste
            ("OBJ_0004", ""),                      # ignoriert
            ("OBJ_0005", None),                    # ignoriert
            ("OBJ_0006", "kaputt"),                # ignoriert (kein Jahres-Praefix)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.erstellt_am_frueheste == "2023-06-01 08:00:00"
    assert st.erstellt_am_spaeteste == "2026-01-10 17:45:33"
    d = st.as_dict()
    assert d["erstellt_am_frueheste"] == "2023-06-01 08:00:00"
    assert d["erstellt_am_spaeteste"] == "2026-01-10 17:45:33"
    c.close()


def test_erstellt_am_spanne_leer(tmp_path):
    """Ohne gueltige erstellt_am-Werte sind beide Grenzen None.

    Spiegelt test_funddatum_spanne_leer: leere/NULL/kaputte Stempel fallen aus
    der Spanne; bei einer Bestands-DB ohne Erfassungs-Stempel (alle Eintraege
    historisch importiert ohne Zeit-Information) liefern beide Grenzen None.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_erstellt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [("OBJ_0001", ""), ("OBJ_0002", None), ("OBJ_0003", "unbekannt")],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.erstellt_am_frueheste is None
    assert st.erstellt_am_spaeteste is None
    c.close()


def test_geaendert_am_spanne_aus_seed_db(tmp_path):
    """frueheste/spaeteste = MIN/MAX gueltiger geaendert_am-Werte.

    Vervollstaendigt das Zeit-Spannen-Trio (Fund / Erfassung / Aenderung) auf
    der letzten-Aenderung-Achse. Minimum verraet das aelteste Bestand-Datum
    (nie-aktualisierte Alt-Eintraege bleiben mit ihrem urspruenglichen geaendert_am
    sichtbar), Maximum die letzte Datenpflege-Aktivitaet im Gesamtbestand.
    Voller Zeitstempel inkl. HH:MM:SS wird durchgereicht; kaputte/leere Stempel
    werden uebergangen (spiegelt das _funddatum_spanne/_erstellt_am_spanne-
    Verhalten).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "spanne_geaendert.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-08-20 11:15:00"),
            ("OBJ_0002", "2023-12-01 09:00:00"),  # frueheste
            ("OBJ_0003", "2026-06-22 14:00:55"),  # spaeteste
            ("OBJ_0004", ""),                      # ignoriert
            ("OBJ_0005", None),                    # ignoriert
            ("OBJ_0006", "kaputt"),                # ignoriert (kein Jahres-Praefix)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.geaendert_am_frueheste == "2023-12-01 09:00:00"
    assert st.geaendert_am_spaeteste == "2026-06-22 14:00:55"
    d = st.as_dict()
    assert d["geaendert_am_frueheste"] == "2023-12-01 09:00:00"
    assert d["geaendert_am_spaeteste"] == "2026-06-22 14:00:55"
    c.close()


def test_geaendert_am_spanne_leer(tmp_path):
    """Ohne gueltige geaendert_am-Werte sind beide Grenzen None."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "leer_geaendert.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, geaendert_am) VALUES (?, ?)",
        [("OBJ_0001", ""), ("OBJ_0002", None), ("OBJ_0003", "unbekannt")],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.geaendert_am_frueheste is None
    assert st.geaendert_am_spaeteste is None
    c.close()


def test_mohs_spanne_aus_seed_db(tmp_path):
    """kollektion_min/max = MIN/MAX der Mohs-Haerte ueber die Sammlung.

    Spiegelt test_funddatum_spanne_aus_seed_db auf die physikalische Haerte-
    Achse: zeigt die Haerte-Bandbreite des dokumentierten Bestands ("vom
    weichsten Talk-Stueck zum haertesten Korund-Stueck"). Reuse der has_mohs-/
    objekte_mit_mohs-Konvention (ein Objekt zaehlt, sobald eines der beiden
    Bereichsfelder gesetzt ist); Single-Point-Faelle (nur min ODER nur max
    gesetzt) tragen mit dem einen Wert zu beiden Grenzen bei. Eintraege ohne
    jegliche Haerte-Pflege bleiben aus der Spanne.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_spanne.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 6.5, 7.0),     # Quarz-Bereich
            ("OBJ_0002", 1.0, 1.0),     # Talk: untere Grenze der Sammlung
            ("OBJ_0003", 8.5, 9.0),     # Topas/Korund: obere Grenze
            ("OBJ_0004", 5.0, None),    # Point-only min → 5.0/5.0
            ("OBJ_0005", None, 7.5),    # Point-only max → 7.5/7.5
            ("OBJ_0006", None, None),   # ignoriert (keine Haerte-Pflege)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_min == 1.0
    assert st.mohs_kollektion_max == 9.0
    d = st.as_dict()
    assert d["mohs_kollektion_min"] == 1.0
    assert d["mohs_kollektion_max"] == 9.0
    c.close()


def test_mohs_spanne_leer(tmp_path):
    """Ohne dokumentierte Mohs-Haerte sind beide Grenzen None.

    Spiegelt test_funddatum_spanne_leer: bei einem Bestand ohne jegliche
    Mohs-Pflege (z.B. frisch importierte CSV ohne Haerte-Spalte) bleiben
    beide Grenzen None - die Spanne-Zeile entfaellt damit in der CLI.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_min is None
    assert st.mohs_kollektion_max is None
    d = st.as_dict()
    assert d["mohs_kollektion_min"] is None
    assert d["mohs_kollektion_max"] is None
    c.close()


def test_mohs_spanne_einzelner_eintrag(tmp_path):
    """Ein einziges gepflegtes Stueck → Spanne kollabiert auf den Punkt.

    Konsistent zur Funddatum-Spanne mit nur einem Eintrag (frueheste ==
    spaeteste). Bei einem Point-only-Eintrag (nur min ODER nur max gesetzt)
    tragen beide Grenzen denselben Wert.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_single.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        ("OBJ_0001", 7.0, None),
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_min == 7.0
    assert st.mohs_kollektion_max == 7.0
    c.close()


def test_mohs_durchschnitt_aus_seed_db(tmp_path):
    """kollektion_durchschnitt = arithmetischer Mittelwert der Mohs-Mittelpunkte.

    Spiegelt test_mohs_spanne_aus_seed_db (Extent-Sicht) auf die zentrale-
    Tendenz-Sicht: waehrend die Spanne die Bandbreite beziffert, beziffert
    der Durchschnitt die "typische" Haerte des dokumentierten Bestands. Pro
    Objekt der Mittelpunkt des dokumentierten Bereichs (min UND max: (a+b)/2;
    Single-Point-Pflege: der eine Wert), gemittelt ueber alle Objekte mit
    mindestens einem gesetzten Bereichsfeld. Eintraege ohne jegliche Mohs-
    Pflege bleiben aus dem Durchschnitt.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_avg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 6.0, 8.0),     # Mittelpunkt 7.0
            ("OBJ_0002", 3.0, 5.0),     # Mittelpunkt 4.0
            ("OBJ_0003", 7.0, None),    # Point-only min → 7.0
            ("OBJ_0004", None, 2.0),    # Point-only max → 2.0
            ("OBJ_0005", None, None),   # ignoriert (keine Pflege)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # (7.0 + 4.0 + 7.0 + 2.0) / 4 = 5.0
    assert st.mohs_kollektion_durchschnitt == 5.0
    d = st.as_dict()
    assert d["mohs_kollektion_durchschnitt"] == 5.0
    c.close()


def test_mohs_durchschnitt_leer(tmp_path):
    """Ohne dokumentierte Mohs-Haerte bleibt der Durchschnitt None.

    Spiegelt test_mohs_spanne_leer: bei einem Bestand ohne jegliche Mohs-
    Pflege bleibt der Durchschnitt None - die CLI-Zeile entfaellt damit
    (kein nichtssagendes 0.0).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_avg_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_durchschnitt is None
    d = st.as_dict()
    assert d["mohs_kollektion_durchschnitt"] is None
    c.close()


def test_mohs_durchschnitt_einzelpunkt(tmp_path):
    """Ein Point-only-Eintrag → Durchschnitt kollabiert auf diesen Wert."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_avg_single.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        ("OBJ_0001", 5.5, None),
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_durchschnitt == 5.5
    c.close()


def test_mohs_median_ungerade_anzahl(tmp_path):
    """kollektion_median = mittleres Element der sortierten Mohs-Mittelpunkte.

    Spiegelt test_mohs_durchschnitt_aus_seed_db (arithmetisches Mittel) auf die
    ausreisser-robuste zentrale Tendenz: bei ungerader Anzahl das mittlere
    Element, spiegelt das gewicht_median_g-/wert_median_chf-Verhalten. Fuenf
    Mittelpunkte 7.0/4.0/7.0/2.0/9.5 → sortiert [2.0, 4.0, 7.0, 7.0, 9.5]
    → Median 7.0 (mittleres Element).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_med.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 6.0, 8.0),     # Mittelpunkt 7.0
            ("OBJ_0002", 3.0, 5.0),     # Mittelpunkt 4.0
            ("OBJ_0003", 7.0, None),    # Point-only min → 7.0
            ("OBJ_0004", None, 2.0),    # Point-only max → 2.0
            ("OBJ_0005", 9.0, 10.0),    # Mittelpunkt 9.5
            ("OBJ_0006", None, None),   # ignoriert (keine Pflege)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # sortiert: [2.0, 4.0, 7.0, 7.0, 9.5] → Median 7.0
    assert st.mohs_kollektion_median == 7.0
    d = st.as_dict()
    assert d["mohs_kollektion_median"] == 7.0
    c.close()


def test_mohs_median_gerade_anzahl(tmp_path):
    """Bei gerader Anzahl: Mittelwert der zwei mittleren sortierten Elemente.

    Spiegelt test_gewicht_median_gerade_anzahl auf die Haerte-Achse: vier
    Mittelpunkte 7.0/4.0/7.0/2.0 → sortiert [2.0, 4.0, 7.0, 7.0] → Median
    (4.0 + 7.0) / 2 = 5.5.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_med_even.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 6.0, 8.0),   # Mittelpunkt 7.0
            ("OBJ_0002", 3.0, 5.0),   # Mittelpunkt 4.0
            ("OBJ_0003", 7.0, None),  # Point-only min → 7.0
            ("OBJ_0004", None, 2.0),  # Point-only max → 2.0
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # sortiert: [2.0, 4.0, 7.0, 7.0] → Median (4.0 + 7.0) / 2 = 5.5
    assert st.mohs_kollektion_median == 5.5
    c.close()


def test_mohs_median_leer(tmp_path):
    """Ohne Mohs-Pflege bleibt der Median None (spiegelt _mohs_durchschnitt)."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_med_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_median is None
    d = st.as_dict()
    assert d["mohs_kollektion_median"] is None
    c.close()


def test_mohs_median_ausreisser_robust(tmp_path):
    """Median bleibt gegen einen einzelnen weit entfernten Ausreisser robust.

    Kern-Eigenschaft der Median-Achse zur Durchschnitts-Achse: neun typische
    Calcit-Stuecke (Mohs ~3) plus ein Diamant-Splitter (Mohs 10) - der
    Durchschnitt wird nach oben gezogen (~3.7), der Median bleibt bei 3.0
    (mittleres Element der sortierten Calcit-Cluster).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_ausreisser.sqlite3")
    calcite = [("OBJ_%04d" % i, 3.0, 3.0) for i in range(1, 10)]  # 9x Mohs 3.0
    calcite.append(("OBJ_0010", 10.0, 10.0))  # Diamant-Ausreisser
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        calcite,
    )
    c.commit()
    st = compute_statistics(c)
    # sortiert: 9x 3.0 + 10.0 → Median = (3.0 + 3.0) / 2 = 3.0 (Ausreisser
    # ignoriert)
    assert st.mohs_kollektion_median == 3.0
    # Durchschnitt reagiert dagegen sichtbar auf den Ausreisser
    assert st.mohs_kollektion_durchschnitt > 3.0
    c.close()


def test_mohs_standardabweichung_aus_seed_db(tmp_path):
    """kollektion_standardabweichung = Populations-Std ueber die Mittelpunkte.

    Ergaenzt Ø/Median (zentrale Tendenz) um die Dispersions-Achse. Vier
    Mittelpunkte 3.0/3.0/7.0/7.0 → Ø=5.0, Varianz = ((3-5)^2 + (3-5)^2 +
    (7-5)^2 + (7-5)^2)/4 = 16/4 = 4.0 → σ = 2.0. Population-Divisor n
    (nicht n-1), weil die Sammlung als vollstaendige Grundgesamtheit gilt.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_std.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 3.0, 3.0),
            ("OBJ_0002", 2.0, 4.0),   # Mittelpunkt 3.0
            ("OBJ_0003", 7.0, None),  # Point-only min → 7.0
            ("OBJ_0004", None, 7.0),  # Point-only max → 7.0
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_durchschnitt == 5.0
    assert st.mohs_kollektion_standardabweichung == pytest.approx(2.0, abs=1e-9)
    d = st.as_dict()
    assert d["mohs_kollektion_standardabweichung"] == 2.0
    c.close()


def test_mohs_standardabweichung_leer(tmp_path):
    """Ohne Mohs-Pflege bleibt die Standardabweichung None."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_std_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_standardabweichung is None
    d = st.as_dict()
    assert d["mohs_kollektion_standardabweichung"] is None
    c.close()


def test_mohs_standardabweichung_einzelpunkt(tmp_path):
    """Bei einem einzelnen Eintrag kollabiert die Streuung auf 0.0.

    Keine Dispersion moeglich; spiegelt _mohs_spanne (Single-Point kollabiert
    auf Punkt) auf die Dispersions-Achse. Der max(...,0.0)-Guard faengt
    Floating-Point-Artefakte ab (E[X^2]=E[X]^2 kann durch Rundung auf -1e-16
    fallen und sqrt liefert NaN).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_std_1.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        ("OBJ_0001", 7.0, 7.0),
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_standardabweichung == 0.0
    c.close()


def test_mohs_standardabweichung_uniform(tmp_path):
    """Bei identischen Mittelpunkten ist die Streuung 0.0.

    Kern-Eigenschaft der Populations-Std: E[X^2] = E[X]^2 wenn alle Werte
    identisch sind → σ = 0. Zehn Quarz-Stuecke mit Mohs 7 haben keine
    Dispersion.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_std_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_%04d" % i, 7.0, 7.0) for i in range(1, 11)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_standardabweichung == 0.0
    c.close()


def test_mohs_standardabweichung_reagiert_auf_ausreisser(tmp_path):
    """Standardabweichung reagiert stark auf Ausreisser (im Gegensatz zum Median).

    Komplementaer zu test_mohs_median_ausreisser_robust: waehrend der Median
    bei 9x Mohs 3.0 + 1x Diamant 10.0 unbeeinflusst bei 3.0 bleibt, zieht
    der Diamant die Standardabweichung deutlich nach oben. Kern-Eigenschaft
    der Dispersions-Achse zur Median-Achse - beide sind komplementaere
    Sichten auf die Verteilung.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "mohs_std_ausreisser.sqlite3")
    calcite = [("OBJ_%04d" % i, 3.0, 3.0) for i in range(1, 10)]
    calcite.append(("OBJ_0010", 10.0, 10.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        calcite,
    )
    c.commit()
    st = compute_statistics(c)
    # Ø = (9*3 + 10) / 10 = 3.7, Var = (9*(3-3.7)^2 + (10-3.7)^2)/10
    # = (9*0.49 + 39.69) / 10 = 44.1/10 = 4.41 → σ = 2.1
    assert st.mohs_kollektion_standardabweichung == pytest.approx(2.1, abs=1e-9)
    # Median bleibt bei 3.0 (siehe test_mohs_median_ausreisser_robust)
    assert st.mohs_kollektion_median == 3.0
    c.close()


def test_dichte_spanne_aus_seed_db(tmp_path):
    """kollektion_min/max = MIN/MAX der Dichte (g/cm3) ueber die Sammlung.

    Spiegelt test_mohs_spanne_aus_seed_db auf die physikalische Dichte-Achse:
    zeigt die Massendichte-Bandbreite des dokumentierten Bestands ("vom
    leichtesten Bims-/Opal-Stueck zum schwersten Pyrit-/Galenit-Stueck").
    Reuse der has_dichte-/objekte_mit_dichte-Konvention (ein Objekt zaehlt,
    sobald eines der beiden Bereichsfelder gesetzt ist); Single-Point-Faelle
    (nur min ODER nur max gesetzt) tragen mit dem einen Wert zu beiden
    Grenzen bei. Eintraege ohne jegliche Dichte-Pflege bleiben aus der Spanne.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_spanne.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.65, 2.66),    # Quarz-Bereich
            ("OBJ_0002", 1.00, 1.10),    # Bims/Opal: untere Grenze
            ("OBJ_0003", 7.40, 7.60),    # Galenit: obere Grenze
            ("OBJ_0004", 3.18, None),    # Point-only min → 3.18/3.18
            ("OBJ_0005", None, 5.02),    # Point-only max → 5.02/5.02
            ("OBJ_0006", None, None),    # ignoriert (keine Dichte-Pflege)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_min == 1.00
    assert st.dichte_kollektion_max == 7.60
    d = st.as_dict()
    assert d["dichte_kollektion_min"] == 1.00
    assert d["dichte_kollektion_max"] == 7.60
    c.close()


def test_dichte_spanne_leer(tmp_path):
    """Ohne dokumentierte Dichte sind beide Grenzen None.

    Spiegelt test_mohs_spanne_leer: bei einem Bestand ohne jegliche
    Dichte-Pflege (z.B. frisch importierte CSV ohne Dichte-Spalte) bleiben
    beide Grenzen None - die Spanne-Zeile entfaellt damit in der CLI.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_min is None
    assert st.dichte_kollektion_max is None
    d = st.as_dict()
    assert d["dichte_kollektion_min"] is None
    assert d["dichte_kollektion_max"] is None
    c.close()


def test_dichte_spanne_einzelner_eintrag(tmp_path):
    """Ein einziges gepflegtes Stueck → Spanne kollabiert auf den Punkt.

    Konsistent zur Mohs-Spanne mit nur einem Eintrag. Bei einem Point-only-
    Eintrag (nur min ODER nur max gesetzt) tragen beide Grenzen denselben
    Wert. Spiegelt die Single-Point-Tabellen-Uebernahme aus Mineral-
    Datenbanken (z.B. Quarz 2.65 als min=max=2.65).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_single.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        ("OBJ_0001", 2.65, None),
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_min == 2.65
    assert st.dichte_kollektion_max == 2.65
    c.close()


def test_dichte_durchschnitt_aus_seed_db(tmp_path):
    """kollektion_durchschnitt = arithmetischer Mittelwert der Dichte-Mittelpunkte.

    Spiegelt test_mohs_durchschnitt_aus_seed_db auf die Dichte-Achse: pro
    Objekt der Mittelpunkt des dokumentierten Bereichs (min UND max: (a+b)/2;
    Single-Point-Pflege: der eine Wert), gemittelt ueber alle Objekte mit
    mindestens einem gesetzten Bereichsfeld. Eintraege ohne jegliche Dichte-
    Pflege bleiben aus dem Durchschnitt.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_avg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.60, 2.80),   # Mittelpunkt 2.70 (Quarz-Range)
            ("OBJ_0002", 1.00, 1.20),   # Mittelpunkt 1.10 (Bims)
            ("OBJ_0003", 5.00, None),   # Point-only min → 5.00
            ("OBJ_0004", None, 3.20),   # Point-only max → 3.20
            ("OBJ_0005", None, None),   # ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # (2.70 + 1.10 + 5.00 + 3.20) / 4 = 3.00
    assert st.dichte_kollektion_durchschnitt == 3.00
    d = st.as_dict()
    # Serialisierung: 2 Nachkommastellen (Mineraldatenbank-Konvention)
    assert d["dichte_kollektion_durchschnitt"] == 3.00
    c.close()


def test_dichte_durchschnitt_leer(tmp_path):
    """Ohne dokumentierte Dichte bleibt der Durchschnitt None.

    Spiegelt test_mohs_durchschnitt_leer / test_dichte_spanne_leer: leere
    Pflege laesst die Kennzahl None, damit die CLI-Zeile entfaellt.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_avg_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_durchschnitt is None
    d = st.as_dict()
    assert d["dichte_kollektion_durchschnitt"] is None
    c.close()


def test_dichte_durchschnitt_einzelpunkt(tmp_path):
    """Ein Point-only-Eintrag → Durchschnitt kollabiert auf diesen Wert."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_avg_single.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        ("OBJ_0001", 2.65, None),
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_durchschnitt == 2.65
    c.close()


def test_dichte_median_aus_seed_db(tmp_path):
    """kollektion_median = Median der Dichte-Mittelpunkte in g/cm3.

    Spiegelt test_mohs_median_aus_seed_db auf die Dichte-Achse: pro Objekt
    der Mittelpunkt des dokumentierten Bereichs (min UND max: (a+b)/2;
    Single-Point-Pflege: der eine Wert - COALESCE-Konvention identisch zum
    Durchschnitt), sortiert, mittleres Element bei ungerader Anzahl. Fuenf
    Mittelpunkte 2.70/1.10/5.00/3.20/7.50 → sortiert
    [1.10, 2.70, 3.20, 5.00, 7.50] → Median 3.20 als mittleres Element.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_med.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.60, 2.80),   # Mittelpunkt 2.70 (Quarz-Range)
            ("OBJ_0002", 1.00, 1.20),   # Mittelpunkt 1.10 (Bims)
            ("OBJ_0003", 5.00, None),   # Point-only min → 5.00
            ("OBJ_0004", None, 3.20),   # Point-only max → 3.20
            ("OBJ_0005", 7.00, 8.00),   # Mittelpunkt 7.50 (Galenit)
            ("OBJ_0006", None, None),   # ignoriert (keine Pflege)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # sortiert: [1.10, 2.70, 3.20, 5.00, 7.50] → Median 3.20
    assert st.dichte_kollektion_median == 3.20
    d = st.as_dict()
    # Serialisierung: 2 Nachkommastellen (Mineraldatenbank-Konvention)
    assert d["dichte_kollektion_median"] == 3.20
    c.close()


def test_dichte_median_gerade_anzahl(tmp_path):
    """Bei gerader Anzahl: Mittelwert der zwei mittleren sortierten Elemente.

    Spiegelt test_mohs_median_gerade_anzahl auf die Dichte-Achse: vier
    Mittelpunkte 2.70/1.10/5.00/3.20 → sortiert [1.10, 2.70, 3.20, 5.00] →
    Median (2.70 + 3.20) / 2 = 2.95.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_med_even.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.60, 2.80),   # Mittelpunkt 2.70
            ("OBJ_0002", 1.00, 1.20),   # Mittelpunkt 1.10
            ("OBJ_0003", 5.00, None),   # Point-only min → 5.00
            ("OBJ_0004", None, 3.20),   # Point-only max → 3.20
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # sortiert: [1.10, 2.70, 3.20, 5.00] → Median (2.70 + 3.20) / 2 = 2.95
    assert st.dichte_kollektion_median == pytest.approx(2.95)
    c.close()


def test_dichte_median_leer(tmp_path):
    """Ohne Dichte-Pflege bleibt der Median None (spiegelt _dichte_durchschnitt)."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_med_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_median is None
    d = st.as_dict()
    assert d["dichte_kollektion_median"] is None
    c.close()


def test_dichte_median_ausreisser_robust(tmp_path):
    """Median bleibt gegen einen einzelnen sehr schweren Ausreisser robust.

    Kern-Eigenschaft der Median-Achse zur Durchschnitts-Achse: neun typische
    Quarz-Stuecke (2.65) plus ein Galenit-Ausreisser (7.50) - der Durchschnitt
    wird nach oben gezogen (~2.15 -> ~3.14), der Median bleibt beim Cluster-Wert
    2.65 (mittleres Element der sortierten Quarz-Reihe). Spiegelt
    test_mohs_median_ausreisser_robust auf die Massendichte-Achse.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_ausreisser.sqlite3")
    quarze = [("OBJ_%04d" % i, 2.65, 2.65) for i in range(1, 10)]  # 9x Quarz 2.65
    quarze.append(("OBJ_0010", 7.50, 7.50))  # Galenit-Ausreisser
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        quarze,
    )
    c.commit()
    st = compute_statistics(c)
    # sortiert: 9x 2.65 + 7.50 → Median = (2.65 + 2.65) / 2 = 2.65
    assert st.dichte_kollektion_median == 2.65
    # Durchschnitt reagiert dagegen sichtbar auf den Ausreisser
    assert st.dichte_kollektion_durchschnitt > 2.65
    c.close()


def test_dichte_standardabweichung_aus_seed_db(tmp_path):
    """kollektion_standardabweichung = Populations-Std ueber die Mittelpunkte.

    Ergaenzt Ø/Median (zentrale Tendenz) um die Dispersions-Achse. Vier
    Mittelpunkte 2.0/2.0/4.0/4.0 → Ø=3.0, Varianz=((2-3)^2*2 + (4-3)^2*2)/4
    = 4/4 = 1.0 → σ = 1.0. Spiegelt test_mohs_standardabweichung_aus_seed_db
    auf die Dichte-Achse; Population-Divisor n (nicht n-1).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_std.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.0, 2.0),
            ("OBJ_0002", 1.5, 2.5),   # Mittelpunkt 2.0
            ("OBJ_0003", 4.0, None),  # Point-only min → 4.0
            ("OBJ_0004", None, 4.0),  # Point-only max → 4.0
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_durchschnitt == 3.0
    assert st.dichte_kollektion_standardabweichung == pytest.approx(1.0, abs=1e-9)
    d = st.as_dict()
    assert d["dichte_kollektion_standardabweichung"] == 1.0
    c.close()


def test_dichte_standardabweichung_leer(tmp_path):
    """Ohne Dichte-Pflege bleibt die Standardabweichung None."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_std_leer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", None, None), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_standardabweichung is None
    d = st.as_dict()
    assert d["dichte_kollektion_standardabweichung"] is None
    c.close()


def test_dichte_standardabweichung_einzelpunkt(tmp_path):
    """Bei einem einzelnen Eintrag kollabiert die Streuung auf 0.0.

    Keine Dispersion moeglich (spiegelt _dichte_spanne / _mohs_standardabweichung
    Single-Point-Kollaps). Der max(...,0.0)-Guard faengt Floating-Point-Rundung.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_std_1.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        ("OBJ_0001", 2.65, 2.65),
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_standardabweichung == 0.0
    c.close()


def test_dichte_standardabweichung_uniform(tmp_path):
    """Bei identischen Mittelpunkten ist die Streuung 0.0.

    Reine Quarz-Familie ohne Dispersion: zehn Stuecke Dichte 2.65 → sigma 0.0.
    Kern-Eigenschaft der Populations-Std (E[X^2] = E[X]^2 wenn alle Werte
    identisch).
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_std_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_%04d" % i, 2.65, 2.65) for i in range(1, 11)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_standardabweichung == 0.0
    c.close()


def test_dichte_standardabweichung_reagiert_auf_ausreisser(tmp_path):
    """Standardabweichung reagiert stark auf Dichte-Ausreisser (Komplement zum Median).

    Komplementaer zu test_dichte_median_ausreisser_robust: waehrend der Median
    bei 9x Quarz 2.65 + 1x Galenit 7.50 unbeeinflusst bleibt, zieht der
    Galenit die Streuung deutlich nach oben. Spiegelt
    test_mohs_standardabweichung_reagiert_auf_ausreisser auf die Massendichte-
    Achse. Ø = (9*2.65 + 7.5)/10 = 3.135, Var = (9*(2.65-3.135)^2 +
    (7.5-3.135)^2)/10 = (9*0.235225 + 19.052225)/10 = 21.169250/10 = 2.116925
    → σ ≈ 1.4550.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "dichte_std_ausreisser.sqlite3")
    quarze = [("OBJ_%04d" % i, 2.65, 2.65) for i in range(1, 10)]
    quarze.append(("OBJ_0010", 7.50, 7.50))
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        quarze,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_standardabweichung == pytest.approx(
        1.4550, abs=1e-3)
    # Median bleibt bei 2.65 (siehe test_dichte_median_ausreisser_robust)
    assert st.dichte_kollektion_median == 2.65
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
    # Nur OBJ_0001 hat eine uebernommene Analyse (die zweite mit None zaehlt nicht)
    assert st.objekte_mit_ki_analyse_uebernommen == 1
    c.close()


def test_ki_analysen_leere_db(tmp_path):
    """Leere DB → alle KI-Zaehler 0 (kein Crash)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.ki_analysen_total == 0
    assert st.ki_analysen_uebernommen == 0
    assert st.objekte_mit_ki_analyse == 0
    assert st.objekte_mit_ki_analyse_uebernommen == 0
    c.close()


def test_objekte_mit_ki_analyse_uebernommen_distinct(tmp_path):
    """Mehrere uebernommene Analysen am selben Objekt zaehlen einmal (DISTINCT obj_id)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "kiu_distinct.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",)],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json, uebernommen_json) "
        "VALUES (?, ?, ?, ?)",
        [
            # OBJ_0001: zwei uebernommene Analysen - zaehlt als ein Objekt
            ("OBJ_0001", "claude-sonnet-4-6", "{}", '{"a":1}'),
            ("OBJ_0001", "claude-opus-4-7", "{}", '{"b":2}'),
            # OBJ_0002: eine uebernommen, eine nicht (None / Whitespace)
            ("OBJ_0002", "claude-sonnet-4-6", "{}", None),
            ("OBJ_0002", "claude-sonnet-4-6", "{}", '{"c":3}'),
            # OBJ_0003: nur nicht-uebernommene Analysen
            ("OBJ_0003", "claude-sonnet-4-6", "{}", None),
            ("OBJ_0003", "claude-sonnet-4-6", "{}", "   "),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.ki_analysen_total == 6
    # Summe der uebernommenen Eintraege (Doppelzaehlung pro Objekt erlaubt)
    assert st.ki_analysen_uebernommen == 3
    # Anzahl Objekte mit mind. einer uebernommenen Analyse (DISTINCT)
    assert st.objekte_mit_ki_analyse_uebernommen == 2
    c.close()


def test_objekte_mit_alias_distinct_canonical(tmp_path):
    """objekte_mit_alias zaehlt die unique Kanon-IDs, nicht die Alias-Eintraege."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "alias.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",)],
    )
    # OBJ_0001 hat drei Aliase (drei alte IDs reingefolgt), OBJ_0002 einen,
    # OBJ_0003 keinen.
    c.executemany(
        "INSERT INTO aliases (alias_id, canonical_id, merge_quelle) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0100", "OBJ_0001", "duplikat_gruppen.json"),
            ("OBJ_0101", "OBJ_0001", "manuell"),
            ("OBJ_0102", "OBJ_0001", "manuell"),
            ("OBJ_0103", "OBJ_0002", "duplikat_gruppen.json"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.aliase_total == 4         # vier Alias-Eintraege
    assert st.objekte_mit_alias == 2    # OBJ_0001 und OBJ_0002 sind Kanon-Objekte mit Aliasen
    c.close()


def test_objekte_mit_alias_leere_db(tmp_path):
    """Leere DB / keine Aliase → 0 (kein Crash)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer_alias.sqlite3")
    st = compute_statistics(c)
    assert st.aliase_total == 0
    assert st.objekte_mit_alias == 0
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


def test_by_bruch_aus_seed_db(tmp_path):
    """Verteilung nach Bruch ignoriert leere Eintraege (6 Enum-Stufen).

    Klassische Lehrbuch-Sicht: Quarz/Obsidian (muschelig) vs. Kupfer/Silber
    (hakig-uneben) vs. Asbest (faserig). Spiegelt Spaltbarkeit auf der
    Bruchverhalten-Achse - Stuecke mit ``keiner`` Spaltbarkeit zeigen ihr
    Bruchverhalten am deutlichsten.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "br.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?, ?)",
        [
            ("OBJ_0001", "muschelig"),
            ("OBJ_0002", "muschelig"),
            ("OBJ_0003", "muschelig"),
            ("OBJ_0004", "uneben"),
            ("OBJ_0005", "uneben"),
            ("OBJ_0006", "splittrig"),
            ("OBJ_0007", "faserig"),
            ("OBJ_0008", ""),
            ("OBJ_0009", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.by_bruch == {
        "muschelig": 3, "uneben": 2, "splittrig": 1, "faserig": 1,
    }
    assert st.as_dict()["by_bruch"]["muschelig"] == 3
    c.close()


def test_by_bruch_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.by_bruch == {}
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
    assert st.quote_mit_gewicht_prozent is None
    assert st.quote_mit_dimensionen_prozent is None
    assert st.quote_mit_mohs_prozent is None
    assert st.quote_mit_dichte_prozent is None
    assert st.quote_mit_ki_analyse_prozent is None
    assert st.quote_mit_confidence_prozent is None
    assert st.quote_mit_kategorie_prozent is None
    assert st.quote_mit_mineral_prozent is None
    assert st.quote_mit_varietaet_prozent is None
    assert st.quote_mit_gesteinsart_prozent is None
    assert st.quote_mit_kristallsystem_prozent is None
    assert st.quote_mit_magnetismus_prozent is None
    assert st.quote_mit_glanz_prozent is None
    assert st.quote_mit_transparenz_prozent is None
    assert st.quote_mit_spaltbarkeit_prozent is None
    assert st.quote_mit_bruch_prozent is None
    assert st.quote_mit_beste_verwendung_prozent is None
    assert st.quote_mit_fundort_prozent is None
    assert st.quote_mit_notizen_prozent is None
    assert st.quote_mit_alias_prozent is None
    d = st.as_dict()
    assert d["quote_mit_bildern_prozent"] is None
    assert d["quote_mit_gewicht_prozent"] is None
    assert d["quote_mit_dimensionen_prozent"] is None
    assert d["quote_mit_mohs_prozent"] is None
    assert d["quote_mit_dichte_prozent"] is None
    assert d["quote_mit_ki_analyse_prozent"] is None
    assert d["quote_mit_confidence_prozent"] is None
    assert d["quote_mit_kategorie_prozent"] is None
    assert d["quote_mit_mineral_prozent"] is None
    assert d["quote_mit_varietaet_prozent"] is None
    assert d["quote_mit_gesteinsart_prozent"] is None
    assert d["quote_mit_kristallsystem_prozent"] is None
    assert d["quote_mit_magnetismus_prozent"] is None
    assert d["quote_mit_glanz_prozent"] is None
    assert d["quote_mit_transparenz_prozent"] is None
    assert d["quote_mit_spaltbarkeit_prozent"] is None
    assert d["quote_mit_bruch_prozent"] is None
    assert d["quote_mit_beste_verwendung_prozent"] is None
    assert d["quote_mit_fundort_prozent"] is None
    assert d["quote_mit_notizen_prozent"] is None
    assert d["quote_mit_alias_prozent"] is None
    c.close()


def test_quote_mit_gewicht_und_ki_analyse_aus_seed_db(tmp_path):
    """Coverage-Quoten fuer Gewicht und KI-Analyse spiegeln die Bildern-/Wert-Quoten:
    Anteil der Objekte mit mindestens einem Gewicht-Wert bzw. mit einer
    KI-Analyse, gerechnet ueber objekte_total."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qkw.sqlite3")
    # 4 Objekte: zwei mit Gewicht (50%), eines mit KI-Analyse (25%; zwei
    # Eintraege auf demselben Objekt zaehlen distinkt nur einmal).
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?,?)",
        [
            ("OBJ_0001", 12.5),
            ("OBJ_0002", 0.0),       # 0 zaehlt wie kein Gewicht
            ("OBJ_0003", 7.0),
            ("OBJ_0004", None),
        ],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json) VALUES (?,?,?)",
        [
            ("OBJ_0001", "claude-sonnet-4-6", "{}"),
            ("OBJ_0001", "claude-opus-4-7", "{}"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.quote_mit_gewicht_prozent == 50.0
    assert st.quote_mit_ki_analyse_prozent == 25.0
    d = st.as_dict()
    assert d["quote_mit_gewicht_prozent"] == 50.0
    assert d["quote_mit_ki_analyse_prozent"] == 25.0
    c.close()


def test_quote_mit_dimensionen_aus_seed_db(tmp_path):
    """Coverage-Quote fuer geometrische Dimensionen (Laenge/Breite/Hoehe in mm)
    spiegelt die Gewicht-Quote auf die geometrische Mess-Achse: Anteil der
    Objekte mit mindestens einer dokumentierten Achse, gerechnet ueber
    objekte_total. Spiegelt has_dimensionen-Filter-Konvention exakt: in der
    Praxis wird oft nur die laengste Achse erfasst (Vitrinen-Index), Breite/
    Hoehe erst beim Praeparieren nachgereicht - daher disjunktiv (mindestens
    eine Achse genuegt). Die Differenz quote_mit_gewicht - quote_mit_dimensionen
    beziffert die Vermessungs-Luecke (gewogen, aber nicht vermessen)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qd.sqlite3")
    # 5 Objekte: drei mit mindestens einer Dimension (60%), zwei ohne (alle
    # drei NULL). Spiegelt die has_dimensionen-Konvention: eine Achse genuegt.
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 50.0, 30.0, 20.0),  # alle drei → zaehlt
            ("OBJ_0002", 80.0, None, None),  # nur Laenge → zaehlt
            ("OBJ_0003", None, None, 5.0),   # nur Hoehe → zaehlt
            ("OBJ_0004", None, None, None),  # nichts → zaehlt nicht
            ("OBJ_0005", None, None, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_dimensionen == 3
    assert st.quote_mit_dimensionen_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_dimensionen"] == 3
    assert d["quote_mit_dimensionen_prozent"] == 60.0
    c.close()


def test_quote_mit_mohs_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Mohs-Haerte (Mohs_Haerte_min / Mohs_Haerte_max)
    spiegelt die has_mohs-Filter-Konvention exakt: ein Objekt zaehlt als
    geprueft, sobald eines der beiden Bereichsfelder gesetzt ist - obere und
    untere Grenze werden nicht immer zusammen gepflegt, oft steht nur eine
    Roh-Skala ('5-6') mit min=5, max=NULL oder umgekehrt. Disjunktive Logik
    (eine Achse genuegt) symmetrisch zu quote_mit_dimensionen_prozent
    (Laenge/Breite/Hoehe). Niedriger Wert ist normal, weil Mohs typisch erst
    nach Mineral-Bestimmung gepflegt wird."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qm.sqlite3")
    # 5 Objekte: drei mit mindestens einer Haerte-Grenze (60%), zwei ohne.
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 7.0, 7.0),     # beide gesetzt → zaehlt
            ("OBJ_0002", 5.0, None),    # nur min → zaehlt
            ("OBJ_0003", None, 4.0),    # nur max → zaehlt
            ("OBJ_0004", None, None),   # nichts → zaehlt nicht
            ("OBJ_0005", None, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_mohs == 3
    assert st.quote_mit_mohs_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_mohs"] == 3
    assert d["quote_mit_mohs_prozent"] == 60.0
    c.close()


def test_quote_mit_dichte_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Dichte (Dichte_min_gcm3 / Dichte_max_gcm3) spiegelt
    die has_dichte-/has_mohs-Filter-Konvention exakt: ein Objekt zaehlt als
    geprueft, sobald eines der beiden Bereichsfelder gesetzt ist - obere und
    untere Grenze werden nicht immer zusammen gepflegt, oft steht nur ein
    Punkt-Wert (Reinmineral) oder eine Roh-Skala ('2.6-2.7') als Standard-
    Tabellenwert aus der Mineraldatenbank uebernommen. Disjunktive Logik
    symmetrisch zu quote_mit_mohs_prozent / quote_mit_dimensionen_prozent.
    Niedriger Wert ist typisch in Sammler-Bestaenden, weil die Dichte-Messung
    nicht so trivial ist wie der Mohs-Kratztest."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qd.sqlite3")
    # 5 Objekte: drei mit mindestens einer Dichte-Grenze (60%), zwei ohne.
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 2.65, 2.66),    # beide gesetzt → zaehlt (Quarz-Punkt)
            ("OBJ_0002", 2.60, None),    # nur min → zaehlt
            ("OBJ_0003", None, 2.71),    # nur max → zaehlt (Calcit)
            ("OBJ_0004", None, None),    # nichts → zaehlt nicht
            ("OBJ_0005", None, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_dichte == 3
    assert st.quote_mit_dichte_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_dichte"] == 3
    assert d["quote_mit_dichte_prozent"] == 60.0
    c.close()


def test_quote_mit_kategorie_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Kategorie (Inventar-Klassifizierung) spiegelt die
    Mineral-/Fundort-Quoten: Anteil der Objekte mit dokumentierter Kategorie,
    gerechnet ueber objekte_total. Whitespace/NULL zaehlt wie leer (spiegelt
    die has_kategorie-Filter-Konvention). Komplementaer zu by_kategorie, das
    distinkte Kategorien-Werte zaehlt (Verteilung): quote_mit_kategorie beziffert
    Coverage (Anteil-Sicht), by_kategorie die Streuung ueber die Klassen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qk.sqlite3")
    # 5 Objekte: drei mit dokumentierter Kategorie (60%), zwei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?,?)",
        [
            ("OBJ_0001", "Handstück"),
            ("OBJ_0002", "Kristall"),
            ("OBJ_0003", "Mineral-Korn"),
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_kategorie == 3
    assert st.quote_mit_kategorie_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_kategorie"] == 3
    assert d["quote_mit_kategorie_prozent"] == 60.0
    c.close()


def test_quote_mit_mineral_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Mineral_Primaer spiegelt die Funddatum-Quote: Anteil
    der Objekte mit dokumentiertem Hauptmineral, gerechnet ueber objekte_total.
    Whitespace/NULL zaehlt wie leer (spiegelt die has_mineral-Filter-Konvention)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qm.sqlite3")
    # 5 Objekte: zwei mit dokumentiertem Mineral (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer) VALUES (?,?)",
        [
            ("OBJ_0001", "Quarz"),
            ("OBJ_0002", "Calcit"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_mineral == 2
    assert st.quote_mit_mineral_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_mineral"] == 2
    assert d["quote_mit_mineral_prozent"] == 40.0
    c.close()


def test_quote_mit_varietaet_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Varietaet (mineralogische Sub-Klassifizierung) spiegelt
    die Mineral_Primaer-Quote auf die feinere Sub-Achse: Anteil der Objekte mit
    dokumentierter Varietaet, gerechnet ueber objekte_total. Whitespace/NULL
    zaehlt wie leer (spiegelt die has_varietaet-Filter-Konvention). Komplementaer
    zu by_varietaet, das distinkte Varietaets-Werte zaehlt (Streuung):
    quote_mit_varietaet beziffert Coverage (Anteil-Sicht), by_varietaet die
    Streuung ueber die Sub-Klassen. Die Differenz zu quote_mit_mineral
    beziffert die Sub-Klassifizierungs-Luecke (Stuecke mit Familie, aber ohne
    Auspraegung)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qv.sqlite3")
    # 5 Objekte: zwei mit dokumentierter Varietaet (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, Varietaet) VALUES (?,?)",
        [
            ("OBJ_0001", "Bergkristall"),
            ("OBJ_0002", "Rauchquarz"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_varietaet == 2
    assert st.quote_mit_varietaet_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_varietaet"] == 2
    assert d["quote_mit_varietaet_prozent"] == 40.0
    c.close()


def test_quote_mit_gesteinsart_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Gesteinsart (petrologische Einordnung) spiegelt die
    Mineral_Primaer-/Varietaet-Quoten auf die petrologische Achse: Anteil der
    Objekte mit dokumentierter Gesteinsart, gerechnet ueber objekte_total.
    Mineral_Primaer beantwortet "welche Mineral-Familie?" (mineralogisch),
    Varietaet "welche Auspraegung?" (mineralogische Sub-Achse), Gesteinsart
    "in welcher Gesteins-Einbettung?" (Granit/Gneis/Basalt/Sandstein -
    geologischer Bildungs-Kontext). Whitespace/NULL zaehlt wie leer (spiegelt
    has_gesteinsart-Filter-Konvention). Komplementaer zu by_gesteinsart, das
    distinkte Werte zaehlt (Streuung): quote_mit_gesteinsart beziffert Coverage."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qg.sqlite3")
    # 5 Objekte: zwei mit dokumentierter Gesteinsart (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, Gesteinsart) VALUES (?,?)",
        [
            ("OBJ_0001", "Granit"),
            ("OBJ_0002", "Gneis"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_gesteinsart == 2
    assert st.quote_mit_gesteinsart_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_gesteinsart"] == 2
    assert d["quote_mit_gesteinsart_prozent"] == 40.0
    c.close()


def test_quote_mit_confidence_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Confidence_Prozent (Bestimmungs-Sicherheitsgrad)
    spiegelt die KI-Analyse-Quoten auf die separate Confidence-Achse: Anteil
    der Objekte mit gueltigem 0..100-Score, gerechnet ueber objekte_total.
    Reuse derselben Filter-Konvention wie median_/durchschnitt_confidence
    (BETWEEN 0 AND 100), damit out-of-range-Werte (Integrity-Pruefung) in
    keiner der drei Sichten gezaehlt werden. NULL zaehlt wie nicht erfasst."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qc.sqlite3")
    # 5 Objekte: drei mit gueltigem Score (60%), eins mit out-of-range
    # (zaehlt nicht; Integrity meldet das separat), eins mit NULL.
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?,?)",
        [
            ("OBJ_0001", 90),
            ("OBJ_0002", 50),
            ("OBJ_0003", 0),     # 0 ist gueltig (Skala-Grenze)
            ("OBJ_0004", 150),   # out-of-range, Integrity meldet das
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_confidence == 3
    assert st.quote_mit_confidence_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_confidence"] == 3
    assert d["quote_mit_confidence_prozent"] == 60.0
    c.close()


def test_quote_mit_kristallsystem_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Kristallsystem (kristallographische Symmetrie-
    Klassifizierung) spiegelt die Mineral_Primaer-/Varietaet-/Gesteinsart-Quoten
    auf die strukturelle Achse: Anteil der Objekte mit dokumentiertem
    Kristallsystem, gerechnet ueber objekte_total. Mineral_Primaer beantwortet
    "welche Mineral-Familie?" (mineralogisch), Varietaet "welche Auspraegung?"
    (mineralogische Sub-Achse), Gesteinsart "in welcher Gesteins-Einbettung?"
    (petrologische Achse), Kristallsystem "welcher Symmetrietyp?" (kubisch/
    tetragonal/hexagonal/trigonal/orthorhombisch/monoklin/triklin/amorph -
    7+1 Enum-Werte aus dem Feldwoerterbuch). Whitespace/NULL zaehlt wie leer
    (spiegelt has_kristallsystem-Filter-Konvention). Komplementaer zu
    by_kristallsystem, das distinkte Werte zaehlt (Streuung):
    quote_mit_kristallsystem beziffert Coverage."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qks.sqlite3")
    # 5 Objekte: zwei mit dokumentiertem Kristallsystem (40%), drei ohne (NULL/
    # leer/nur Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?,?)",
        [
            ("OBJ_0001", "trigonal"),
            ("OBJ_0002", "kubisch"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_kristallsystem == 2
    assert st.quote_mit_kristallsystem_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_kristallsystem"] == 2
    assert d["quote_mit_kristallsystem_prozent"] == 40.0
    c.close()


def test_quote_mit_magnetismus_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Magnetismus (qualitative magnetische Reaktion)
    spiegelt die Kristallsystem-Quote auf die physikalisch-magnetische Pruef-
    Achse: Anteil der Objekte mit dokumentiertem Magnetismus, gerechnet ueber
    objekte_total. Magnetismus klassifiziert die qualitative Eisengehalts-
    Reaktion (nein/schwach/ja - die drei Enum-Werte aus dem Feldwoerterbuch),
    spiegelt das has_magnetismus-Filter-Verhalten exakt. Whitespace/NULL
    zaehlt wie leer (spiegelt has_magnetismus-Filter-Konvention).
    Komplementaer zu by_magnetismus, das distinkte Werte zaehlt (Streuung):
    quote_mit_magnetismus beziffert Coverage."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qmg.sqlite3")
    # 5 Objekte: zwei mit dokumentiertem Magnetismus (40%), drei ohne (NULL/
    # leer/nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei mit
    # demselben "nein"-Wert sind in der Coverage gleichwertig zu zwei
    # unterschiedlichen Reaktions-Stufen - die Coverage-Sicht ist ortho-
    # gonal zur Streuung-Sicht (by_magnetismus).
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?,?)",
        [
            ("OBJ_0001", "nein"),
            ("OBJ_0002", "ja"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_magnetismus == 2
    assert st.quote_mit_magnetismus_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_magnetismus"] == 2
    assert d["quote_mit_magnetismus_prozent"] == 40.0
    c.close()


def test_quote_mit_glanz_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Glanz (optische Oberflaechen-Reflexion) spiegelt die
    Magnetismus-/Kristallsystem-Quote auf die optische Diagnose-Achse: Anteil
    der Objekte mit dokumentiertem Glanz, gerechnet ueber objekte_total. Glanz
    klassifiziert die qualitative Oberflaechen-Reflexion (glasig/wachsig/matt/
    metallisch/fettig/seidig/perlmutt - die sieben Enum-Werte aus dem
    Feldwoerterbuch), spiegelt das has_glanz-Filter-Verhalten exakt. Whitespace/
    NULL zaehlt wie leer (spiegelt has_glanz-Filter-Konvention). Komplementaer
    zu by_glanz, das distinkte Werte zaehlt (Streuung): quote_mit_glanz
    beziffert Coverage."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qg.sqlite3")
    # 5 Objekte: zwei mit dokumentiertem Glanz (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei mit demselben
    # "glasig"-Wert sind in der Coverage gleichwertig zu zwei unterschiedlichen
    # Reflexions-Typen - die Coverage-Sicht ist orthogonal zur Streuung-Sicht
    # (by_glanz).
    c.executemany(
        "INSERT INTO objects (obj_id, Glanz) VALUES (?,?)",
        [
            ("OBJ_0001", "glasig"),
            ("OBJ_0002", "metallisch"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_glanz == 2
    assert st.quote_mit_glanz_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_glanz"] == 2
    assert d["quote_mit_glanz_prozent"] == 40.0
    c.close()


def test_quote_mit_transparenz_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Transparenz (Lichtdurchlaessigkeit) spiegelt die
    Glanz-Quote auf die zweite optische Diagnose-Achse: Anteil der Objekte mit
    dokumentierter Transparenz, gerechnet ueber objekte_total. Transparenz
    klassifiziert die qualitative Lichtdurchlaessigkeit (durchsichtig/
    durchscheinend/opak - die drei Enum-Werte aus dem Feldwoerterbuch),
    spiegelt das has_transparenz-Filter-Verhalten exakt. Whitespace/NULL zaehlt
    wie leer (spiegelt has_transparenz-Filter-Konvention). Komplementaer zu
    by_transparenz, das distinkte Werte zaehlt (Streuung): quote_mit_transparenz
    beziffert Coverage."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qt.sqlite3")
    # 5 Objekte: zwei mit dokumentierter Transparenz (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei mit unterschied-
    # lichen Transparenz-Werten zaehlen in der Coverage gleich; die Streuung
    # (by_transparenz) bleibt orthogonal.
    c.executemany(
        "INSERT INTO objects (obj_id, Transparenz) VALUES (?,?)",
        [
            ("OBJ_0001", "durchsichtig"),
            ("OBJ_0002", "opak"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_transparenz == 2
    assert st.quote_mit_transparenz_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_transparenz"] == 2
    assert d["quote_mit_transparenz_prozent"] == 40.0
    c.close()


def test_quote_mit_spaltbarkeit_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Spaltbarkeit (mechanisches Bruchverhalten) spiegelt
    die Glanz-/Transparenz-/Magnetismus-Quoten auf die mechanisch-strukturelle
    Diagnose-Achse: Anteil der Objekte mit dokumentierter Spaltbarkeit, gerechnet
    ueber objekte_total. Spaltbarkeit klassifiziert das mechanische Bruchverhalten
    entlang kristallographisch bevorzugter Ebenen (vollkommen/gut/deutlich/
    undeutlich/keine - die fuenf Enum-Werte aus dem Feldwoerterbuch), spiegelt das
    has_spaltbarkeit-Filter-Verhalten exakt. Whitespace/NULL zaehlt wie leer
    (spiegelt has_spaltbarkeit-Filter-Konvention). Komplementaer zu by_spaltbarkeit,
    das distinkte Werte zaehlt (Streuung): quote_mit_spaltbarkeit beziffert Coverage."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qs.sqlite3")
    # 5 Objekte: zwei mit dokumentierter Spaltbarkeit (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei mit unterschied-
    # lichen Spaltbarkeits-Werten zaehlen in der Coverage gleich; die Streuung
    # (by_spaltbarkeit) bleibt orthogonal.
    c.executemany(
        "INSERT INTO objects (obj_id, Spaltbarkeit) VALUES (?,?)",
        [
            ("OBJ_0001", "vollkommen"),   # Glimmer-typisch
            ("OBJ_0002", "keine"),        # Quarz-typisch
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_spaltbarkeit == 2
    assert st.quote_mit_spaltbarkeit_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_spaltbarkeit"] == 2
    assert d["quote_mit_spaltbarkeit_prozent"] == 40.0
    c.close()


def test_quote_mit_bruch_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Bruch (ungeordnetes mechanisches Versagen ausserhalb
    der Spaltebenen: muschelig/uneben/splittrig/faserig/erdig/glatt - die
    sechs Enum-Werte aus dem Feldwoerterbuch) spiegelt die Spaltbarkeits-Quote
    auf die paarweise Bruchverhalten-Achse. Anteil der Objekte mit
    dokumentiertem Bruch, gerechnet ueber objekte_total. Whitespace/NULL
    zaehlt wie leer (spiegelt has_bruch-Filter-Konvention). Komplementaer
    zu by_bruch, das distinkte Werte zaehlt (Streuung): quote_mit_bruch
    beziffert Coverage. Schliesst die mechanisch-strukturelle Diagnose-Doppel-
    Achse Spaltbarkeit -> Bruch."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qb.sqlite3")
    # 5 Objekte: zwei mit dokumentiertem Bruch (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei mit unter-
    # schiedlichen Bruch-Werten (Quarz-typisch muschelig, Asbest-typisch
    # faserig) zaehlen in der Coverage gleich; die Streuung (by_bruch)
    # bleibt orthogonal.
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch) VALUES (?,?)",
        [
            ("OBJ_0001", "muschelig"),   # Quarz/Obsidian-typisch
            ("OBJ_0002", "faserig"),     # Asbest-typisch
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_bruch == 2
    assert st.quote_mit_bruch_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_bruch"] == 2
    assert d["quote_mit_bruch_prozent"] == 40.0
    c.close()


def test_quote_mit_beste_verwendung_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Beste_Verwendung (empfohlene Verwendungs-Kategorie:
    Schmuck/Sammlung/Forschung/Industrie/Talisman/Dekoration - die sechs Enum-
    Werte aus dem Feldwoerterbuch) schliesst die Coverage-Reihe der strukturierten
    Enum-Achsen ab. Spiegelt die Diagnose-Coverage-Quoten (Magnetismus/Glanz/
    Transparenz/Spaltbarkeit/Bruch - objektive Beobachtungen am Stueck) auf die
    Verwendungs-/Empfehlungs-Achse (subjektive Sammler-Entscheidung ueber den
    weiteren Lebensweg des Stuecks). Anteil der Objekte mit dokumentierter
    Verwendungs-Empfehlung, gerechnet ueber objekte_total. Whitespace/NULL zaehlt
    wie leer (spiegelt has_beste_verwendung-Filter-Konvention). Komplementaer zu
    by_beste_verwendung (Streuung-Sicht ueber Verwendungs-Kategorien) und wert_/
    gewicht_pro_beste_verwendung (Wert-/Gewicht-Aufteilung): quote_mit_beste_
    verwendung beziffert Coverage, beide gemeinsam ergeben Vollstaendigkeit vs.
    Streuung der Verwendungs-Planung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qbv.sqlite3")
    # 5 Objekte: zwei mit dokumentierter Verwendungs-Empfehlung (40%), drei
    # ohne (NULL/leer/nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei
    # mit unterschiedlichen Verwendungs-Werten (Schmuck-Empfehlung fuer polier-
    # bare Stuecke, Sammlung-Empfehlung fuer Vitrinen-Stuecke) zaehlen in der
    # Coverage gleich; die Streuung (by_beste_verwendung) bleibt orthogonal.
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?,?)",
        [
            ("OBJ_0001", "Schmuck"),
            ("OBJ_0002", "Sammlung"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_beste_verwendung == 2
    assert st.quote_mit_beste_verwendung_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_beste_verwendung"] == 2
    assert d["quote_mit_beste_verwendung_prozent"] == 40.0
    c.close()


def test_quote_mit_fundort_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Fundort spiegelt die Funddatum-/Mineral-Quote: Anteil
    der Objekte mit dokumentiertem Fundort, gerechnet ueber objekte_total.
    Whitespace/NULL zaehlt wie leer (spiegelt die has_fundort-Filter-Konvention).
    Komplementaer zu fundorte_total, das distinkte Fundorte zaehlt (Diversitaet):
    quote_mit_fundort beziffert Coverage, fundorte_total Streuung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qf.sqlite3")
    # 5 Objekte: zwei mit dokumentiertem Fundort (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei dokumentierte
    # Stuecke vom selben Fundort: Coverage 40%, Diversitaet (fundorte_total) 1.
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "Davos"),
            ("OBJ_0002", "Davos"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_fundort == 2
    assert st.quote_mit_fundort_prozent == 40.0
    # Diversitaets-Achse bleibt orthogonal: 2 Objekte am selben Fundort = 1 Ort.
    assert st.fundorte_total == 1
    d = st.as_dict()
    assert d["objekte_mit_fundort"] == 2
    assert d["quote_mit_fundort_prozent"] == 40.0
    c.close()


def test_quote_mit_farbe_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Farbe_beobachtet (tatsaechlich gesehene Mineral-
    Farbe - die niederschwelligste visuelle Diagnose-Achse aus dem
    Feldwoerterbuch, keine Werkzeuge noetig, am Tageslicht beobachtbar).
    Spiegelt die optischen Coverage-Quoten (quote_mit_glanz/transparenz auf
    Enum-Skalen) und die diagnostisch invariante Pulverfarbe (Strichfarbe)
    auf die freie str-Farb-Achse. Anteil der Objekte mit dokumentierter
    Farbe, gerechnet ueber objekte_total. Whitespace/NULL zaehlt wie leer
    (spiegelt has_farbe-Filter-Konvention der repository.filter_objects-API)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qfb.sqlite3")
    # 5 Objekte: zwei mit dokumentierter Farbe (40%), drei ohne (NULL/leer/
    # nur Whitespace zaehlen alle wie nicht-dokumentiert). Zwei unterschied-
    # liche Farb-Beobachtungen (rauchgrau fuer Quarz-typisch, ziegelrot fuer
    # Haematit-typisch) zaehlen in der Coverage gleich; die Werte selbst
    # werden nicht weiter klassifiziert (freie str-Spalte ohne Enum-Validierung).
    c.executemany(
        "INSERT INTO objects (obj_id, Farbe_beobachtet) VALUES (?,?)",
        [
            ("OBJ_0001", "rauchgrau"),    # Quarz-typische Farbe
            ("OBJ_0002", "ziegelrot"),    # Haematit-typische Farbe
            ("OBJ_0003", ""),             # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),          # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_farbe == 2
    assert st.quote_mit_farbe_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_farbe"] == 2
    assert d["quote_mit_farbe_prozent"] == 40.0
    c.close()


def test_quote_mit_farbe_leere_db(tmp_path):
    """Leere DB: quote_mit_farbe_prozent ist None (nicht 0%) - keine Objekte
    zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_farbe_prozent is None
    assert st.as_dict()["quote_mit_farbe_prozent"] is None
    c.close()


def test_quote_mit_strichfarbe_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Strichfarbe (Farbe des Pulvers auf Porzellan-
    Strichplaette - einer der drei klassischen qualitativen Bestimmungs-
    Pruefparameter aus dem Feldwoerterbuch neben Magnetismus und HCl-Reaktion).
    Spiegelt die Enum-Coverage-Quoten der qualitativen Pruef-Achsen
    (quote_mit_magnetismus_prozent als Enum-validierte Reaktions-Achse) auf
    die freie str-Pruef-Achse Strichfarbe. Anteil der Objekte mit
    dokumentierter Strichfarbe, gerechnet ueber objekte_total. Whitespace/
    NULL zaehlt wie leer (spiegelt die has_notizen-/has_fundort-Filter-
    Konvention der freien str-Spalten). Niedriger Wert ist typisch, weil der
    Strichtest invasiv ist (das Mineral wird abgerieben) und eine Porzellan-
    Strichplaette erfordert - er wird erst nach erster Mineral-Hypothese als
    Bestaetigung durchgefuehrt, nicht routinemaessig fuer jedes Stueck."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qsf.sqlite3")
    # 5 Objekte: zwei mit dokumentierter Strichfarbe (40%), drei ohne
    # (NULL/leer/Whitespace zaehlen alle wie nicht-dokumentiert). Zwei
    # unterschiedliche Strichfarben (gelblich-weiss fuer Calcit-typisch,
    # gruenlich-schwarz fuer Pyrit-typisch) zaehlen in der Coverage gleich;
    # die Werte selbst werden nicht weiter klassifiziert (freie str-Spalte
    # ohne Enum-Validierung).
    c.executemany(
        "INSERT INTO objects (obj_id, Strichfarbe) VALUES (?,?)",
        [
            ("OBJ_0001", "gelblich-weiss"),    # Calcit-typische Farbe
            ("OBJ_0002", "gruenlich-schwarz"), # Pyrit-typische Farbe
            ("OBJ_0003", ""),                  # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),               # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_strichfarbe == 2
    assert st.quote_mit_strichfarbe_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_strichfarbe"] == 2
    assert d["quote_mit_strichfarbe_prozent"] == 40.0
    c.close()


def test_quote_mit_strichfarbe_leere_db(tmp_path):
    """Leere DB: quote_mit_strichfarbe_prozent ist None (nicht 0%) - keine
    Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_strichfarbe_prozent is None
    assert st.as_dict()["quote_mit_strichfarbe_prozent"] is None
    c.close()


def test_quote_mit_hcl_reaktion_aus_seed_db(tmp_path):
    """Coverage-Quote fuer HCl-Reaktion (Salzsaeure-Test) schliesst die
    Pruefparameter-Trias der drei klassischen qualitativen Bestimmungs-
    Pruefparameter aus dem Feldwoerterbuch (Magnetismus, Strichfarbe,
    HCl-Reaktion) ab. Anteil der Objekte mit dokumentierter HCl-Reaktion,
    gerechnet ueber objekte_total. Whitespace/NULL zaehlt wie leer (spiegelt
    has_hcl_reaktion-Filter-Konvention)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qhcl.sqlite3")
    # 5 Objekte: zwei mit dokumentierter HCl-Reaktion (40%), drei ohne
    # (NULL/leer/Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, HCl_Reaktion) VALUES (?,?)",
        [
            ("OBJ_0001", "stark"),           # Calcit-typisch
            ("OBJ_0002", "keine"),           # Quarz-typisch
            ("OBJ_0003", ""),                # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),             # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_hcl_reaktion == 2
    assert st.quote_mit_hcl_reaktion_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_hcl_reaktion"] == 2
    assert d["quote_mit_hcl_reaktion_prozent"] == 40.0
    c.close()


def test_quote_mit_hcl_reaktion_leere_db(tmp_path):
    """Leere DB: quote_mit_hcl_reaktion_prozent ist None (nicht 0%) - keine
    Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_hcl_reaktion_prozent is None
    assert st.as_dict()["quote_mit_hcl_reaktion_prozent"] is None
    c.close()


def test_quote_mit_uv_365nm_aus_seed_db(tmp_path):
    """Coverage-Quote fuer UV-Reaktion bei 365 nm (Langwellen-UV, Standard-
    Wellenlaenge fuer Fluoreszenz-Sammler) spiegelt die qualitativen
    Pruefparameter-Trias (Magnetismus/Strichfarbe/HCl-Reaktion) auf die
    optisch-UV-Diagnose-Achse: Anteil der Objekte mit dokumentierter UV-
    Reaktion, gerechnet ueber objekte_total. Whitespace/NULL zaehlt wie
    leer."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "quv.sqlite3")
    # 5 Objekte: zwei mit dokumentierter UV-Reaktion (40%), drei ohne
    # (NULL/leer/Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, UV_365nm) VALUES (?,?)",
        [
            ("OBJ_0001", "stark gruen"),     # Willemit-typisch
            ("OBJ_0002", "keine"),           # Quarz-typisch
            ("OBJ_0003", ""),                # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),             # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_uv_365nm == 2
    assert st.quote_mit_uv_365nm_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_uv_365nm"] == 2
    assert d["quote_mit_uv_365nm_prozent"] == 40.0
    c.close()


def test_quote_mit_uv_365nm_leere_db(tmp_path):
    """Leere DB: quote_mit_uv_365nm_prozent ist None (nicht 0%) - keine
    Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_uv_365nm_prozent is None
    assert st.as_dict()["quote_mit_uv_365nm_prozent"] is None
    c.close()


def test_quote_mit_uv_254nm_aus_seed_db(tmp_path):
    """Coverage-Quote fuer UV-Reaktion bei 254 nm (Kurzwellen-UV) - paarweise
    Komplement-Achse zur Langwellen-Quote quote_mit_uv_365nm_prozent.
    Vervollstaendigt das UV-Doppel-Wellenlaengen-Coverage. Anteil der Objekte
    mit dokumentierter Kurzwellen-Reaktion, gerechnet ueber objekte_total.
    Whitespace/NULL zaehlt wie leer."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "quv254.sqlite3")
    # 5 Objekte: zwei mit dokumentierter UV_254nm (40%), drei ohne
    # (NULL/leer/Whitespace zaehlen alle wie nicht-dokumentiert).
    c.executemany(
        "INSERT INTO objects (obj_id, UV_254nm) VALUES (?,?)",
        [
            ("OBJ_0001", "stark blauweiss"),  # Scheelit-typisch
            ("OBJ_0002", "keine"),            # Quarz-typisch
            ("OBJ_0003", ""),                 # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),              # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_uv_254nm == 2
    assert st.quote_mit_uv_254nm_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_uv_254nm"] == 2
    assert d["quote_mit_uv_254nm_prozent"] == 40.0
    c.close()


def test_quote_mit_uv_254nm_leere_db(tmp_path):
    """Leere DB: quote_mit_uv_254nm_prozent ist None (nicht 0%) - keine
    Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_uv_254nm_prozent is None
    assert st.as_dict()["quote_mit_uv_254nm_prozent"] is None
    c.close()


def test_quote_mit_reaktionshinweis_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Reaktionshinweis (erklaerende Begleit-Notiz zu
    UV/HCl/Magnetismus-Reaktionen) spiegelt die Coverage-Quoten der
    strukturellen Reaktions-Pruef-Achsen (Magnetismus/HCl/UV_365/UV_254) auf
    die zugehoerige Erklaer-Achse. Anteil der Objekte mit dokumentierter
    Interpretations-Notiz, gerechnet ueber objekte_total. Whitespace/NULL
    zaehlt wie leer (spiegelt has_reaktionshinweis-Filter-Konvention)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qrh.sqlite3")
    # 5 Objekte: zwei mit dokumentiertem Reaktionshinweis (40%), drei ohne
    # (NULL/leer/Whitespace zaehlen alle wie nicht-dokumentiert). Mehrzeiliger
    # Eintrag (Newline) ist legitim und zaehlt mit, weil TRIM nur fuehrende/
    # abschliessende Whitespace strippt - text-Spalte erlaubt mehrzeilige
    # mineralogische Erklaerungen.
    c.executemany(
        "INSERT INTO objects (obj_id, Reaktionshinweis) VALUES (?,?)",
        [
            # Calcit/Mischcarbonat-typische Erklaerung
            ("OBJ_0001", "schwaeche Reaktion wegen Mg-Anteil (Dolomit-Mischphase)"),
            # Fluorit-typische Begleit-Notiz
            ("OBJ_0002", "Fluoreszenz nur unter Langwelle\nKurzwelle ohne Antwort"),
            ("OBJ_0003", ""),       # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),    # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_reaktionshinweis == 2
    assert st.quote_mit_reaktionshinweis_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_reaktionshinweis"] == 2
    assert d["quote_mit_reaktionshinweis_prozent"] == 40.0
    c.close()


def test_quote_mit_reaktionshinweis_leere_db(tmp_path):
    """Leere DB: quote_mit_reaktionshinweis_prozent ist None (nicht 0%) - keine
    Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_reaktionshinweis_prozent is None
    assert st.as_dict()["quote_mit_reaktionshinweis_prozent"] is None
    c.close()


def test_quote_mit_pruefempfehlungen_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Pruefempfehlungen (empfohlene Bestaetigungstests
    aus der Sonstiges-Gruppe des Feldwoerterbuchs) spiegelt die Coverage-
    Quote quote_mit_reaktionshinweis_prozent auf die naechste-Schritt-Achse:
    waehrend Reaktionshinweis rueckblickend die schon beobachteten Reaktionen
    interpretiert, plant Pruefempfehlungen die noch offene Pruef-Liste.
    Anteil der Objekte mit dokumentiertem Pruef-Plan, gerechnet ueber
    objekte_total. Whitespace/NULL zaehlt wie leer (spiegelt die
    has_pruefempfehlungen-Filter-Konvention aus stonebook.db.repository)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qpe.sqlite3")
    # 5 Objekte: zwei mit dokumentierten Pruefempfehlungen (40%), drei ohne
    # (NULL/leer/Whitespace zaehlen alle wie nicht-dokumentiert). Mehrzeiliger
    # Eintrag (Newline) ist legitim und zaehlt mit, weil TRIM nur fuehrende/
    # abschliessende Whitespace strippt - text-Spalte erlaubt mehrzeilige
    # Pruef-Plaene mit mehreren Methoden untereinander.
    c.executemany(
        "INSERT INTO objects (obj_id, Pruefempfehlungen) VALUES (?,?)",
        [
            # Quarz-/Bergkristall-typischer naechster Pruefschritt
            ("OBJ_0001", "Dichtebestimmung mit Pyknometer zur Trennung Quarz vs. Glas"),
            # Mehrzeiliger Pruef-Plan mit mehreren Methoden
            ("OBJ_0002", "EDX-Analyse VHS-Kurs\nXRD-Messung Uni-Labor"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_pruefempfehlungen == 2
    assert st.quote_mit_pruefempfehlungen_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_pruefempfehlungen"] == 2
    assert d["quote_mit_pruefempfehlungen_prozent"] == 40.0
    c.close()


def test_quote_mit_pruefempfehlungen_leere_db(tmp_path):
    """Leere DB: quote_mit_pruefempfehlungen_prozent ist None (nicht 0%) -
    keine Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-
    Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_pruefempfehlungen_prozent is None
    assert st.as_dict()["quote_mit_pruefempfehlungen_prozent"] is None
    c.close()


def test_quote_mit_notizen_aus_seed_db(tmp_path):
    """Coverage-Quote fuer freie Notizen (notizen-Spalte) spiegelt die
    Strukturfeld-Coverage-Quoten (Bildern/Funddatum/Mineral/Fundort) auf die
    unstrukturierte Freitext-Achse: Anteil der Objekte mit irgendeinem
    nicht-leeren notizen-Eintrag, gerechnet ueber objekte_total. Whitespace/
    NULL zaehlt wie leer (spiegelt has_notizen-Filter-Konvention). Niedriger
    Wert ist typisch - notizen ist die "Sonstiges"-Spalte, die nur bei
    Beobachtungs-Anlass gepflegt wird."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qn.sqlite3")
    # 5 Objekte: zwei mit Notizen (40%), drei ohne (NULL/leer/Whitespace
    # zaehlen alle wie nicht-dokumentiert). Multi-Line-Eintrag (Newline) ist
    # legitim und zaehlt mit, weil der TRIM nur fuehrende/abschliessende
    # Whitespace strippt.
    c.executemany(
        "INSERT INTO objects (obj_id, notizen) VALUES (?,?)",
        [
            ("OBJ_0001", "Auffaelliger Habitus, saeulenfoermig"),
            ("OBJ_0002", "Geerbt von Onkel\nProvenienz unsicher"),
            ("OBJ_0003", ""),        # leerer Eintrag → ignoriert
            ("OBJ_0004", "   "),     # nur Whitespace → ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_notizen == 2
    assert st.quote_mit_notizen_prozent == 40.0
    d = st.as_dict()
    assert d["objekte_mit_notizen"] == 2
    assert d["quote_mit_notizen_prozent"] == 40.0
    c.close()


def test_quote_mit_ki_analyse_uebernommen_aus_seed_db(tmp_path):
    """Coverage-Quote fuer uebernommene KI-Analysen spiegelt quote_mit_ki_analyse
    auf die feinere Granularitaet "Anteil der Sammlung, der durch KI tatsaechlich
    verbessert wurde". Differenz beider Quoten beziffert die Akzeptanz-/Pflege-
    Luecke (KI lief, aber Vorschlaege wurden nicht uebernommen)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qkiu.sqlite3")
    # 5 Objekte: zwei mit uebernommener KI-Analyse (40%), eines mit KI-Analyse
    # ohne Uebernahme (zaehlt nicht), zwei ohne Analyse.
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",), ("OBJ_0004",), ("OBJ_0005",)],
    )
    c.executemany(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json, uebernommen_json) "
        "VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", "claude-opus-4-7", "{}", '{"a":1}'),
            ("OBJ_0002", "claude-opus-4-7", "{}", '{"b":2}'),
            # OBJ_0003: KI lief, aber kein uebernommen_json - zaehlt nicht
            ("OBJ_0003", "claude-opus-4-7", "{}", None),
            ("OBJ_0003", "claude-opus-4-7", "{}", "   "),
            # OBJ_0004, OBJ_0005: keine Analyse
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # objekte_mit_ki_analyse = 3 (OBJ_0001/02/03), uebernommen = 2 (OBJ_0001/02)
    assert st.objekte_mit_ki_analyse == 3
    assert st.objekte_mit_ki_analyse_uebernommen == 2
    assert st.quote_mit_ki_analyse_prozent == 60.0
    assert st.quote_mit_ki_analyse_uebernommen_prozent == 40.0
    d = st.as_dict()
    assert d["quote_mit_ki_analyse_uebernommen_prozent"] == 40.0
    c.close()


def test_quote_mit_ki_analyse_uebernommen_leere_db(tmp_path):
    """Leere DB: quote_mit_ki_analyse_uebernommen_prozent ist None (nicht 0%)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_ki_analyse_uebernommen_prozent is None
    assert st.as_dict()["quote_mit_ki_analyse_uebernommen_prozent"] is None
    c.close()


def test_quote_mit_alias_aus_seed_db(tmp_path):
    """Merge-Quote (Provenienz-Coverage) spiegelt das Coverage-Vokabular auf die
    Aliase-Achse: Anteil der Kanon-Objekte mit mindestens einem Alias, gerechnet
    ueber objekte_total. Komplementaer zu aliase_total (Roh-Volumen aller
    Eintraege, eine Kanon-ID kann mehrfach gemergt sein) und objekte_mit_alias
    (Anzahl-Sicht) - quote_mit_alias bezieht das auf den Gesamtbestand."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qal.sqlite3")
    # 5 Objekte: OBJ_0001 hat zwei Aliase (zweimal gemergt), OBJ_0002 einen,
    # OBJ_0003/04/05 keinen. objekte_mit_alias = 2 (DISTINCT canonical_id),
    # aliase_total = 3 (Summe Eintraege), quote_mit_alias = 2/5 = 40 %.
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",),
         ("OBJ_0004",), ("OBJ_0005",)],
    )
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
    st = compute_statistics(c)
    assert st.aliase_total == 3
    assert st.objekte_mit_alias == 2
    assert st.quote_mit_alias_prozent == 40.0
    d = st.as_dict()
    assert d["quote_mit_alias_prozent"] == 40.0
    c.close()


def test_quote_mit_alias_leere_db(tmp_path):
    """Leere DB: quote_mit_alias_prozent ist None (nicht 0%), spiegelt das
    Verhalten der uebrigen Coverage-Quoten bei 0 Objekten."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.quote_mit_alias_prozent is None
    assert st.as_dict()["quote_mit_alias_prozent"] is None
    c.close()


def test_quote_mit_alias_ohne_merges(tmp_path):
    """Sammlung ohne Merges: quote_mit_alias_prozent = 0 % (saubere Erfassungs-Linie)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "nomerge.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.aliase_total == 0
    assert st.objekte_mit_alias == 0
    assert st.quote_mit_alias_prozent == 0.0
    assert st.as_dict()["quote_mit_alias_prozent"] == 0.0
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
    # kategorien_total spiegelt die uebrigen Diversitaets-Kennzahlen auf die
    # Inventar-Klassifizierungs-Achse: bei leerer DB bleibt der Zaehler bei 0
    # (dataclass-Default), damit as_dict deterministisch bleibt und die
    # Dashboard-Downstream-Konsumenten nicht zwischen 0 und None differenzieren
    # muessen (spiegelt mineral_arten_total / fundorte_total).
    assert st.kategorien_total == 0
    # varietaeten_total: analog zur Inventar-Klassifizierungs-Achse
    # (kategorien_total) hier die mineralogische Sub-Klassifizierungs-Achse
    # (Bergkristall/Amethyst/Rauchquarz innerhalb Quarz). Bei leerer DB bleibt
    # der Zaehler bei 0 (dataclass-Default, spiegelt mineral_arten_total /
    # fundorte_total / kategorien_total).
    assert st.varietaeten_total == 0
    # gesteinsarten_total: petrologische Klassifizierungs-Achse (Granit/Gneis/
    # Kalkstein/...) als fuenfter Diversitaets-Zaehler. Bei leerer DB bleibt
    # der Zaehler bei 0 (dataclass-Default, spiegelt mineral_arten_total /
    # fundorte_total / kategorien_total / varietaeten_total).
    assert st.gesteinsarten_total == 0


def test_kategorien_total_zaehlt_distinct(tmp_path):
    """kategorien_total spiegelt mineral_arten_total auf die Kategorie-Achse.

    Zaehlt distinct dokumentierte Objekt-Kategorien (Handstueck/Kristall/
    Duennschliff/...), unabhaengig von Top-N-Limits in by_kategorie und
    ohne NULL/leere Zeichen. Downstream-Konsumenten (Dashboards, JSON-Export)
    lesen den Skalar direkt statt len(by_kategorie) zu berechnen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "kdiv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
        [
            ("OBJ_0001", "Handstueck"),
            ("OBJ_0002", "Handstueck"),   # Duplikat, zaehlt nur 1x
            ("OBJ_0003", "Kristall"),
            ("OBJ_0004", "Duennschliff"),
            ("OBJ_0005", ""),             # leere Kategorie -> ignoriert
            ("OBJ_0006", "   "),          # Whitespace-only -> ignoriert
            ("OBJ_0007", None),           # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.kategorien_total == 3   # Handstueck, Kristall, Duennschliff
    d = st.as_dict()
    assert d["kategorien_total"] == 3
    # by_kategorie enthaelt die drei Kategorien - kategorien_total spiegelt
    # deren Anzahl exakt, macht die Zaehlung aber ohne Umweg ueber die
    # Dict-Laenge verfuegbar (spiegelt mineral_arten_total-Rolle).
    assert len(st.by_kategorie) == st.kategorien_total
    c.close()


def test_varietaeten_total_zaehlt_distinct(tmp_path):
    """varietaeten_total spiegelt mineral_arten_total auf die Varietaet-Achse.

    Zaehlt distinct dokumentierte Mineral-Varietaeten (Bergkristall/Amethyst/
    Rauchquarz innerhalb der Familie Quarz), unabhaengig von Top-N-Limits
    in by_varietaet und ohne NULL/leere Zeichen. Downstream-Konsumenten
    (Dashboards, JSON-Export) lesen den Skalar direkt statt len(by_varietaet)
    zu berechnen. Spiegelt kategorien_total: dieselbe Distinct-Semantik,
    andere Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vdiv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Varietaet) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Quarz", "Bergkristall"),
            ("OBJ_0002", "Quarz", "Bergkristall"),  # Duplikat, zaehlt nur 1x
            ("OBJ_0003", "Quarz", "Amethyst"),
            ("OBJ_0004", "Quarz", "Rauchquarz"),
            ("OBJ_0005", "Calcit", ""),             # leere Varietaet -> ignoriert
            ("OBJ_0006", "Calcit", "   "),          # Whitespace-only -> ignoriert
            ("OBJ_0007", "Calcit", None),           # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.varietaeten_total == 3   # Bergkristall, Amethyst, Rauchquarz
    d = st.as_dict()
    assert d["varietaeten_total"] == 3
    # by_varietaet enthaelt die drei Varietaeten - varietaeten_total spiegelt
    # deren Anzahl exakt, macht die Zaehlung aber ohne Umweg ueber die
    # Dict-Laenge verfuegbar (spiegelt mineral_arten_total-Rolle).
    assert len(st.by_varietaet) == st.varietaeten_total
    # Diversitaets-Achsen sind orthogonal: hier eine Mineral-Familie (Quarz)
    # mit drei dokumentierten Varietaeten - mineral_arten_total unterscheidet
    # nur zwischen Quarz und Calcit (2), varietaeten_total zaehlt die feineren
    # Auspraegungen (3). Die zwei Kennzahlen antworten auf verschiedene Fragen.
    assert st.mineral_arten_total == 2
    c.close()


def test_gesteinsarten_total_zaehlt_distinct(tmp_path):
    """gesteinsarten_total spiegelt mineral_arten_total auf die Gesteinsart-Achse.

    Zaehlt distinct dokumentierte Gesteinsarten (Granit/Gneis/Kalkstein/...),
    unabhaengig von Top-N-Limits in by_gesteinsart und ohne NULL/leere Zeichen.
    Downstream-Konsumenten (Dashboards, JSON-Export) lesen den Skalar direkt
    statt len(by_gesteinsart) zu berechnen. Spiegelt varietaeten_total /
    kategorien_total: dieselbe Distinct-Semantik, andere Achse (petrologische
    Wirt-/Einbettungs-Sicht neben mineralogischer Familien- und Sub-Klassi-
    fizierungs-Achse).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gdiv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mineral_Primaer, Gesteinsart) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Quarz", "Granit"),
            ("OBJ_0002", "Quarz", "Granit"),      # Duplikat, zaehlt nur 1x
            ("OBJ_0003", "Quarz", "Sandstein"),
            ("OBJ_0004", "Calcit", "Kalkstein"),
            ("OBJ_0005", "Calcit", ""),           # leere Gesteinsart -> ignoriert
            ("OBJ_0006", "Calcit", "   "),        # Whitespace-only -> ignoriert
            ("OBJ_0007", "Achat", None),          # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gesteinsarten_total == 3   # Granit, Sandstein, Kalkstein
    d = st.as_dict()
    assert d["gesteinsarten_total"] == 3
    # by_gesteinsart enthaelt die drei Gesteinsarten - gesteinsarten_total
    # spiegelt deren Anzahl exakt, macht die Zaehlung aber ohne Umweg ueber
    # die Dict-Laenge verfuegbar (spiegelt mineral_arten_total-Rolle).
    assert len(st.by_gesteinsart) == st.gesteinsarten_total
    # Diversitaets-Achsen sind orthogonal: hier drei Mineral-Familien (Quarz/
    # Calcit/Achat) in drei Gesteinsarten (Granit/Sandstein/Kalkstein) -
    # mineral_arten_total zaehlt die Familien (3), gesteinsarten_total die
    # Wirt-Einbettungen (3). Die zwei Kennzahlen antworten auf verschiedene
    # Fragen: "welche mineralogische Familie?" vs. "in welcher Gesteins-
    # Einbettung?".
    assert st.mineral_arten_total == 3
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
    assert st.gewicht_min_g == 10.0
    assert st.gewicht_max_g == 200.0
    assert st.gewicht_median_g == 50.0           # mittlerer von [10, 50, 200]
    assert st.gewicht_durchschnitt_g == pytest.approx(260.0 / 3)
    d = st.as_dict()
    assert d["objekte_mit_gewicht"] == 3
    assert d["gewicht_min_g"] == 10.0
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
    assert st.gewicht_min_g == 0.0
    assert st.gewicht_max_g == 0.0
    assert st.gewicht_median_g == 0.0
    assert st.gewicht_durchschnitt_g == 0.0
    c.close()


def test_gewicht_min_einzelobjekt_gleich_max(tmp_path):
    """Bei genau einem Objekt mit Gewicht kollabieren Min und Max auf denselben Wert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_single.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_0001", 42.5), ("OBJ_0002", None), ("OBJ_0003", 0.0)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_gewicht == 1
    assert st.gewicht_min_g == 42.5
    assert st.gewicht_max_g == 42.5
    c.close()


def test_gewicht_standardabweichung_aus_seed_db(tmp_path):
    """kollektion_standardabweichung = Populations-Std ueber Gewicht_g.

    Ergaenzt Ø/Median (zentrale Tendenz) um die Dispersions-Achse. Vier
    Gewichte 10/20/30/40 → Ø=25, Varianz=((10-25)^2 + (20-25)^2 +
    (30-25)^2 + (40-25)^2)/4 = (225+25+25+225)/4 = 500/4 = 125.0 →
    σ = sqrt(125) ≈ 11.1803. Spiegelt test_mohs_standardabweichung_aus_seed_db
    auf die Massen-Achse; Population-Divisor n (nicht n-1).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_std.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [
            ("OBJ_0001", 10.0),
            ("OBJ_0002", 20.0),
            ("OBJ_0003", 30.0),
            ("OBJ_0004", 40.0),
            ("OBJ_0005", None),  # ignoriert
            ("OBJ_0006", 0.0),   # ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_durchschnitt_g == 25.0
    assert st.gewicht_standardabweichung_g == pytest.approx(
        125.0 ** 0.5, abs=1e-9)
    d = st.as_dict()
    assert d["gewicht_standardabweichung_g"] == pytest.approx(11.18, abs=1e-2)
    c.close()


def test_gewicht_standardabweichung_leer(tmp_path):
    """Ohne Gewicht-Pflege bleibt die Standardabweichung 0.0 (dataclass-Default).

    Spiegelt die uebrigen leeren-Gewicht-Kennzahlen (min/max/median/Ø = 0.0
    bei leerer DB), damit as_dict deterministisch bleibt (round(0.0) = 0.0
    statt None) und die CLI-Zeile die Zeile im ohne-Gewicht-Fall gar nicht
    ausgibt (if objekte_mit_gewicht:).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_std_leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_standardabweichung_g == 0.0
    d = st.as_dict()
    assert d["gewicht_standardabweichung_g"] == 0.0
    c.close()


def test_gewicht_standardabweichung_einzelobjekt(tmp_path):
    """Bei einem einzelnen Gewicht-Eintrag kollabiert die Streuung auf 0.0.

    Keine Dispersion moeglich; spiegelt _mohs_/_dichte_standardabweichung
    Single-Point-Kollaps auf die Massen-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_std_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_0001", 42.5), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_gewicht == 1
    assert st.gewicht_standardabweichung_g == 0.0
    c.close()


def test_gewicht_standardabweichung_uniform(tmp_path):
    """Bei identischen Gewichten ist die Streuung 0.0.

    Kern-Eigenschaft der Populations-Std (E[(x-mean)^2] = 0 wenn alle Werte
    identisch); spiegelt test_mohs_standardabweichung_uniform auf die Massen-
    Achse. Fuenf Stuecke mit 100 g → sigma 0.0.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_std_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_%04d" % i, 100.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_standardabweichung_g == 0.0
    c.close()


def test_gewicht_standardabweichung_reagiert_auf_ausreisser(tmp_path):
    """Standardabweichung reagiert stark auf Gewicht-Ausreisser (Komplement zum Median).

    Komplementaer zu test_gewicht_min_einzelobjekt_gleich_max: bei 9x kleinen
    Splittern (1 g) + 1x schwerer Handstueck (100 g) bleibt der Median klein,
    die Streuung wird deutlich groesser. Ø = (9*1 + 100)/10 = 10.9,
    Var = (9*(1-10.9)^2 + (100-10.9)^2)/10 = (9*98.01 + 7938.81)/10 =
    (882.09 + 7938.81)/10 = 8820.9/10 = 882.09 → σ ≈ 29.7.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_std_ausreisser.sqlite3")
    splitter = [("OBJ_%04d" % i, 1.0) for i in range(1, 10)]
    splitter.append(("OBJ_0010", 100.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        splitter,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_standardabweichung_g == pytest.approx(29.7, abs=1e-1)
    # Median bleibt bei 1.0 (5. Element von [1,1,1,1,1,1,1,1,1,100])
    assert st.gewicht_median_g == 1.0
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


def test_wert_pro_bruch_aus_seed_db(tmp_path):
    """Wertsumme pro Bruch, absteigend sortiert (Bruchverhalten-Wert-Sicht).

    Komplementaer zu by_bruch (Anzahl): zeigt, welche Bruchverhalten-Klasse
    den Sammlungswert traegt. Muschelig brechende Quarz-/Obsidian-Stuecke
    liegen wertlich oft auf einem anderen Niveau als fasrige Asbest-Stuecke.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpb.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch, Wert_CHF_roh, Wert_CHF_poliert) "
        "VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "muschelig", 100.0, 200.0),    # muschelig: 300
            ("OBJ_0002", "muschelig", 50.0, None),      # +50 -> 350
            ("OBJ_0003", "uneben", 1000.0, None),       # uneben: 1000
            ("OBJ_0004", "uneben", None, None),         # 0
            ("OBJ_0005", "faserig", 10.0, None),
            ("OBJ_0006", "", 999.0, None),              # leer -> ignoriert
            ("OBJ_0007", None, 999.0, None),            # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_bruch == [
        ("uneben", 1000.0),
        ("muschelig", 350.0),
        ("faserig", 10.0),
    ]
    d = st.as_dict()
    assert d["wert_pro_bruch"] == [
        ("uneben", 1000.0), ("muschelig", 350.0), ("faserig", 10.0),
    ]
    c.close()


def test_wert_pro_bruch_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpb_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch, Wert_CHF_roh) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Br{i}", float(i)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_wert_bruch=3)
    assert len(st.wert_pro_bruch) == 3
    werte = [w for _, w in st.wert_pro_bruch]
    assert werte == [7.0, 6.0, 5.0]
    c.close()


def test_wert_pro_bruch_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_bruch == []
    c.close()


def test_gewicht_pro_bruch_aus_seed_db(tmp_path):
    """Gewichtsumme pro Bruch, absteigend sortiert; 0/NULL zaehlen nicht.

    Spiegelbild zu wert_pro_bruch: dichte Obsidian-Brocken (muschelig) tragen
    oft den Schwerteil der Sammlungsmasse, fasrige Aktinolith-Buendel bleiben
    leicht - die Wert/Gewicht-Entkopplung wird auch auf der Bruchverhalten-
    Achse sichtbar.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpb.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", "muschelig", 1000.0),    # muschelig total 1000
            ("OBJ_0002", "muschelig", 500.0),     # muschelig total 1500
            ("OBJ_0003", "uneben", 100.0),        # uneben total 100
            ("OBJ_0004", "uneben", None),         # NULL -> ignoriert
            ("OBJ_0005", "faserig", 200.0),
            ("OBJ_0006", "", 999.0),              # leer -> ignoriert
            ("OBJ_0007", None, 999.0),            # NULL -> ignoriert
            ("OBJ_0008", "muschelig", 0.0),       # 0 -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_bruch == [
        ("muschelig", 1500.0),
        ("faserig", 200.0),
        ("uneben", 100.0),
    ]
    assert st.as_dict()["gewicht_pro_bruch"] == [
        ("muschelig", 1500.0), ("faserig", 200.0), ("uneben", 100.0),
    ]
    c.close()


def test_gewicht_pro_bruch_limit(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpb_lim.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Bruch, Gewicht_g) VALUES (?,?,?)",
        [(f"OBJ_{i:04d}", f"Br{i}", float(i * 10)) for i in range(1, 8)],
    )
    c.commit()
    st = compute_statistics(c, top_gewicht_bruch=3)
    assert len(st.gewicht_pro_bruch) == 3
    g = [v for _, v in st.gewicht_pro_bruch]
    assert g == [70.0, 60.0, 50.0]
    c.close()


def test_gewicht_pro_bruch_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_bruch == []
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


def test_wert_pro_seltenheit_global_aus_seed_db(tmp_path):
    """Wertsumme pro globalem Seltenheits-Bucket (1..10), absteigend nach Summe.

    Komplementaer zu by_seltenheit_global (Anzahl): zeigt nicht "wieviele
    Stuecke pro Rarity-Stufe", sondern "wo steckt der Wert in der Rarity-
    Verteilung" - typisch konzentriert sich der Wert in den oberen Stufen
    (>=8). Out-of-Range-Werte (<1 / >10) bleiben ausgeschlossen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpsg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10, "
        "Wert_CHF_roh, Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 1, 50.0, None),       # Stufe 1: 50
            ("OBJ_0002", 1, 30.0, None),       # +30 -> 80
            ("OBJ_0003", 8, 1000.0, 500.0),    # Stufe 8: 1500
            ("OBJ_0004", 8, None, None),       # 0 -> bleibt 1500
            ("OBJ_0005", 5, 100.0, None),      # Stufe 5: 100
            ("OBJ_0006", 0, 999.0, None),      # out-of-range -> ignoriert
            ("OBJ_0007", 11, 999.0, None),     # out-of-range -> ignoriert
            ("OBJ_0008", None, 999.0, None),   # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_seltenheit_global == [
        ("8", 1500.0),
        ("5", 100.0),
        ("1", 80.0),
    ]
    assert st.as_dict()["wert_pro_seltenheit_global"] == [
        ("8", 1500.0), ("5", 100.0), ("1", 80.0),
    ]
    c.close()


def test_wert_pro_seltenheit_global_tiebreaker_aufsteigend(tmp_path):
    """Bei Gleichstand sortiert nach Skalenwert aufsteigend (analog _sum_by)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpsg_tie.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10, Wert_CHF_roh) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 3, 100.0),
            ("OBJ_0002", 7, 100.0),
            ("OBJ_0003", 5, 100.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_seltenheit_global == [
        ("3", 100.0), ("5", 100.0), ("7", 100.0),
    ]
    c.close()


def test_wert_pro_seltenheit_global_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_seltenheit_global == []
    c.close()


def test_gewicht_pro_seltenheit_global_aus_seed_db(tmp_path):
    """Gewichtsumme pro globalem Seltenheits-Bucket; 0/NULL zaehlen nicht.

    Spiegelbild zu wert_pro_seltenheit_global: typisch liegt die Masse in
    den haeufigen Stufen (<=3), waehrend die wertvollen Rarit?ten (>=8)
    leichter sind - die Wert/Gewicht-Entkopplung wird auf der Rarity-Achse
    sichtbar.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpsg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10, Gewicht_g) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 1, 5000.0),       # Stufe 1: 5000
            ("OBJ_0002", 1, 3000.0),       # +3000 -> 8000
            ("OBJ_0003", 8, 50.0),         # Stufe 8: 50
            ("OBJ_0004", 5, 100.0),        # Stufe 5: 100
            ("OBJ_0005", 5, 0.0),          # 0 -> ignoriert
            ("OBJ_0006", 5, None),         # NULL -> ignoriert
            ("OBJ_0007", 0, 999.0),        # out-of-range -> ignoriert
            ("OBJ_0008", 11, 999.0),       # out-of-range -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_seltenheit_global == [
        ("1", 8000.0),
        ("5", 100.0),
        ("8", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_seltenheit_global"] == [
        ("1", 8000.0), ("5", 100.0), ("8", 50.0),
    ]
    c.close()


def test_gewicht_pro_seltenheit_global_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_seltenheit_global == []
    c.close()


def test_wert_pro_seltenheit_fundort_aus_seed_db(tmp_path):
    """Standort-Rarity-Wert-Aggregat: spiegelt wert_pro_seltenheit_global auf der lokalen Skala.

    Lokal selten (>=8) ist nicht immer global selten - eine lokale Rarit?t aus
    einem ausgeschoepften Stollen kann global haeufig sein. Der Block zeigt,
    wo lokal der Wert sitzt; out-of-range bleibt ausgeschlossen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpsf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10, "
        "Wert_CHF_roh, Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 2, 50.0, None),       # Stufe 2: 50
            ("OBJ_0002", 7, 800.0, 200.0),     # Stufe 7: 1000
            ("OBJ_0003", 7, None, None),       # +0 -> 1000
            ("OBJ_0004", 4, 100.0, None),      # Stufe 4: 100
            ("OBJ_0005", 0, 999.0, None),      # out-of-range -> ignoriert
            ("OBJ_0006", 11, 999.0, None),     # out-of-range -> ignoriert
            ("OBJ_0007", None, 999.0, None),   # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_seltenheit_fundort == [
        ("7", 1000.0),
        ("4", 100.0),
        ("2", 50.0),
    ]
    assert st.as_dict()["wert_pro_seltenheit_fundort"] == [
        ("7", 1000.0), ("4", 100.0), ("2", 50.0),
    ]
    c.close()


def test_wert_pro_seltenheit_fundort_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_seltenheit_fundort == []
    c.close()


def test_gewicht_pro_seltenheit_fundort_aus_seed_db(tmp_path):
    """Standort-Rarity-Gewicht-Aggregat: 0/NULL zaehlen nicht; spiegelt Global-Sicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpsf.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10, Gewicht_g) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 2, 4000.0),       # Stufe 2: 4000
            ("OBJ_0002", 2, 1000.0),       # +1000 -> 5000
            ("OBJ_0003", 7, 80.0),         # Stufe 7: 80
            ("OBJ_0004", 4, 0.0),          # 0 -> ignoriert
            ("OBJ_0005", 4, None),         # NULL -> ignoriert
            ("OBJ_0006", 0, 999.0),        # out-of-range -> ignoriert
            ("OBJ_0007", 11, 999.0),       # out-of-range -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_seltenheit_fundort == [
        ("2", 5000.0),
        ("7", 80.0),
    ]
    assert st.as_dict()["gewicht_pro_seltenheit_fundort"] == [
        ("2", 5000.0), ("7", 80.0),
    ]
    c.close()


def test_gewicht_pro_seltenheit_fundort_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_seltenheit_fundort == []
    c.close()


def test_wert_pro_nachfrage_aus_seed_db(tmp_path):
    """Marktnachfrage-Wert-Aggregat: spiegelt seltenheit-Bloecke auf der Demand-Skala.

    Komplementaer zu by_nachfrage (Anzahl): zeigt, ob der Sammlungs-Wert auf
    hochbegehrten Stuecken (Stufe >=7) konzentriert ist oder in
    Tauschmaterial (<=3) gebunden bleibt. Out-of-Range ignoriert.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "wpn.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10, "
        "Wert_CHF_roh, Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 9, 900.0, 600.0),    # Stufe 9: 1500
            ("OBJ_0002", 6, 200.0, None),     # Stufe 6: 200
            ("OBJ_0003", 3, 100.0, None),     # Stufe 3: 100
            ("OBJ_0004", 3, None, None),      # 0 -> bleibt 100
            ("OBJ_0005", 0, 999.0, None),     # out-of-range -> ignoriert
            ("OBJ_0006", 11, 999.0, None),    # out-of-range -> ignoriert
            ("OBJ_0007", None, 999.0, None),  # NULL -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_nachfrage == [
        ("9", 1500.0),
        ("6", 200.0),
        ("3", 100.0),
    ]
    assert st.as_dict()["wert_pro_nachfrage"] == [
        ("9", 1500.0), ("6", 200.0), ("3", 100.0),
    ]
    c.close()


def test_wert_pro_nachfrage_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_nachfrage == []
    c.close()


def test_gewicht_pro_nachfrage_aus_seed_db(tmp_path):
    """Marktnachfrage-Gewicht-Aggregat: 0/NULL zaehlen nicht; spiegelt Wert-Sicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "gpn.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10, Gewicht_g) "
        "VALUES (?,?,?)",
        [
            ("OBJ_0001", 2, 2500.0),       # Stufe 2: 2500
            ("OBJ_0002", 2, 1500.0),       # +1500 -> 4000
            ("OBJ_0003", 7, 60.0),         # Stufe 7: 60
            ("OBJ_0004", 5, 0.0),          # 0 -> ignoriert
            ("OBJ_0005", 5, None),         # NULL -> ignoriert
            ("OBJ_0006", 0, 999.0),        # out-of-range -> ignoriert
            ("OBJ_0007", 11, 999.0),       # out-of-range -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_nachfrage == [
        ("2", 4000.0),
        ("7", 60.0),
    ]
    assert st.as_dict()["gewicht_pro_nachfrage"] == [
        ("2", 4000.0), ("7", 60.0),
    ]
    c.close()


def test_gewicht_pro_nachfrage_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_nachfrage == []
    c.close()


def test_sum_by_scale_1_10_validiert_spalte(tmp_path):
    """SQL-Injection-Schutz: nur SCALE_1_10_COLUMNS-Werte zulaessig (analog _count_scale_1_10)."""
    from stonebook.db.database import open_db
    from stonebook.db.stats import _sum_by_scale_1_10
    c = open_db(tmp_path / "guard.sqlite3")
    with pytest.raises(ValueError):
        _sum_by_scale_1_10(c, "Beliebige_Spalte", "Wert_CHF_roh")
    with pytest.raises(ValueError):
        _sum_by_scale_1_10(c, "Mineral_Primaer", "Wert_CHF_roh")
    c.close()


def test_wert_pro_confidence_bucket_aus_seed_db(tmp_path):
    """Confidence-Wert-Aggregat: spiegelt confidence_buckets auf die Wert-Achse.

    Ordnet jeden Wert dem 25-Prozent-Klassen-Bucket (oder 'ohne' bei NULL) zu;
    Out-of-Range (<0 / >100) bleibt ausgeschlossen. Sortierung: Summe DESC mit
    CONFIDENCE_BUCKET_ORDER-Tiebreak.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "wpcb.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, "
        "Wert_CHF_roh, Wert_CHF_poliert) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", 95, 800.0, 200.0),   # 75-100: 1000
            ("OBJ_0002", 80, 400.0, None),    # +400 -> 1400
            ("OBJ_0003", 60, 300.0, None),    # 50-74: 300
            ("OBJ_0004", 30, 150.0, None),    # 25-49: 150
            ("OBJ_0005", 10, 50.0, None),     # 0-24:  50
            ("OBJ_0006", None, 600.0, None),  # ohne:  600
            ("OBJ_0007", 50, 0.0, None),      # 0-Wert -> ignoriert
            ("OBJ_0008", -5, 999.0, None),    # out-of-range -> ignoriert
            ("OBJ_0009", 150, 999.0, None),   # out-of-range -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_pro_confidence_bucket == [
        ("75-100", 1400.0),
        ("ohne", 600.0),
        ("50-74", 300.0),
        ("25-49", 150.0),
        ("0-24", 50.0),
    ]
    assert st.as_dict()["wert_pro_confidence_bucket"] == [
        ("75-100", 1400.0),
        ("ohne", 600.0),
        ("50-74", 300.0),
        ("25-49", 150.0),
        ("0-24", 50.0),
    ]
    c.close()


def test_wert_pro_confidence_bucket_tiebreak_in_bucket_order(tmp_path):
    """Gleicher Summen-Wert -> CONFIDENCE_BUCKET_ORDER bestimmt die Reihenfolge."""
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "wpcb_tie.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, Wert_CHF_roh) VALUES (?,?,?)",
        [
            ("OBJ_0001", 80, 100.0),   # 75-100: 100
            ("OBJ_0002", 60, 100.0),   # 50-74:  100
            ("OBJ_0003", 30, 100.0),   # 25-49:  100
            ("OBJ_0004", None, 100.0), # ohne:   100
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # alle Buckets bei 100 -> CONFIDENCE_BUCKET_ORDER ('ohne','0-24',...) entscheidet
    assert st.wert_pro_confidence_bucket == [
        ("ohne", 100.0),
        ("25-49", 100.0),
        ("50-74", 100.0),
        ("75-100", 100.0),
    ]
    c.close()


def test_wert_pro_confidence_bucket_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_pro_confidence_bucket == []
    c.close()


def test_gewicht_pro_confidence_bucket_aus_seed_db(tmp_path):
    """Confidence-Gewicht-Aggregat: spiegelt wert_pro_confidence_bucket auf Masse.

    Wert/Gewicht-Entkopplung auf der KI-Bestimmungs-Achse: schwere
    Geroellstuecke ohne KI-Bestimmung (Bucket 'ohne') vs. leichte aber sicher
    bestimmte Kristalle (75-100). Out-of-Range / NULL / 0-Gewicht bleiben aus.
    """
    from stonebook.db.database import open_db

    c = open_db(tmp_path / "gpcb.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, Gewicht_g) VALUES (?,?,?)",
        [
            ("OBJ_0001", None, 3000.0),    # ohne:   3000
            ("OBJ_0002", None, 1000.0),    # +1000 -> 4000
            ("OBJ_0003", 90, 80.0),        # 75-100: 80
            ("OBJ_0004", 60, 200.0),       # 50-74:  200
            ("OBJ_0005", 30, 150.0),       # 25-49:  150
            ("OBJ_0006", 10, 50.0),        # 0-24:   50
            ("OBJ_0007", 50, 0.0),         # 0-Gewicht -> ignoriert
            ("OBJ_0008", 50, None),        # NULL -> ignoriert
            ("OBJ_0009", -5, 999.0),       # out-of-range -> ignoriert
            ("OBJ_0010", 150, 999.0),      # out-of-range -> ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_pro_confidence_bucket == [
        ("ohne", 4000.0),
        ("50-74", 200.0),
        ("25-49", 150.0),
        ("75-100", 80.0),
        ("0-24", 50.0),
    ]
    assert st.as_dict()["gewicht_pro_confidence_bucket"] == [
        ("ohne", 4000.0),
        ("50-74", 200.0),
        ("25-49", 150.0),
        ("75-100", 80.0),
        ("0-24", 50.0),
    ]
    c.close()


def test_gewicht_pro_confidence_bucket_leer(tmp_path):
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_pro_confidence_bucket == []
    c.close()


def test_quote_mit_seltenheit_global_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Seltenheit_global_1_10 (globale Rarity-Skala, 1=
    haeufig .. 10=sehr selten global - die zentrale Markt-/Versicherungs-
    Achse aus dem Feldwoerterbuch). Spiegelt das Coverage-Vokabular der
    quantitativen Bestimmungs-Achse (Confidence_Prozent mit BETWEEN-Filter
    und Out-of-Range-Ausschluss) auf die ordinale Rarity-Skala. Anteil der
    Objekte mit gueltigem Rarity-Score (1..10), gerechnet ueber objekte_total.
    NULL und out-of-range-Werte (<1 / >10) zaehlen wie nicht-erfasst (spiegelt
    objekte_mit_confidence-Verhalten); die out-of-range-Werte werden in der
    Integrity separat gemeldet."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qsg.sqlite3")
    # 5 Objekte: drei mit gueltiger Rarity (60% - Werte 3, 7, 9 als typische
    # Haeufig-/Standard-/Selten-Auspraegungen der Skala), zwei ohne (NULL und
    # out-of-range 11 zaehlen nicht). Der out-of-range-Wert simuliert einen
    # korrupten Migrations-/Hand-Eintrag, der durch die Integrity-Pruefung
    # separat aufgefangen wird und in der Coverage-/Verteilungs-Sicht
    # ausgeschlossen bleibt.
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_global_1_10) VALUES (?,?)",
        [
            ("OBJ_0001", 3),    # haeufig
            ("OBJ_0002", 7),    # standard-selten
            ("OBJ_0003", 9),    # sehr selten
            ("OBJ_0004", None),  # nicht erfasst -> ignoriert
            ("OBJ_0005", 11),    # out-of-range -> ignoriert (Integrity)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_seltenheit_global == 3
    assert st.quote_mit_seltenheit_global_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_seltenheit_global"] == 3
    assert d["quote_mit_seltenheit_global_prozent"] == 60.0
    c.close()


def test_quote_mit_seltenheit_global_leere_db(tmp_path):
    """Leere DB: quote_mit_seltenheit_global_prozent ist None (nicht 0%) -
    keine Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.objekte_mit_seltenheit_global == 0
    assert st.quote_mit_seltenheit_global_prozent is None
    assert st.as_dict()["quote_mit_seltenheit_global_prozent"] is None
    c.close()


def test_quote_mit_seltenheit_fundort_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Seltenheit_Fundort_1_10 (Standort-Rarity-Skala 1..10,
    1=haeufig am Fundort .. 10=sehr selten am Fundort). Spiegelt
    quote_mit_seltenheit_global_prozent auf die zweite ordinale Rarity-Achse
    aus dem Feldwoerterbuch. Anteil der Objekte mit gueltigem Fundort-Rarity-
    Score (1..10), gerechnet ueber objekte_total. NULL und out-of-range-Werte
    (<1 / >10) zaehlen wie nicht-erfasst (Integrity meldet die separat,
    spiegelt das objekte_mit_seltenheit_global-Verhalten)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qsf.sqlite3")
    # 5 Objekte: drei mit gueltiger Fundort-Rarity (60 % - Werte 2, 5, 8 als
    # typische Haeufig-/Standard-/Selten-Auspraegungen der Skala), zwei ohne
    # (NULL und out-of-range 0 zaehlen nicht). Der out-of-range-Wert simuliert
    # einen korrupten Migrations-/Hand-Eintrag, der durch die Integrity-
    # Pruefung separat aufgefangen wird und in der Coverage-/Verteilungs-Sicht
    # ausgeschlossen bleibt.
    c.executemany(
        "INSERT INTO objects (obj_id, Seltenheit_Fundort_1_10) VALUES (?,?)",
        [
            ("OBJ_0001", 2),    # haeufig am Fundort
            ("OBJ_0002", 5),    # Standard-Auspraegung
            ("OBJ_0003", 8),    # selten am Fundort
            ("OBJ_0004", None),  # nicht erfasst -> ignoriert
            ("OBJ_0005", 0),     # out-of-range -> ignoriert (Integrity)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_seltenheit_fundort == 3
    assert st.quote_mit_seltenheit_fundort_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_seltenheit_fundort"] == 3
    assert d["quote_mit_seltenheit_fundort_prozent"] == 60.0
    c.close()


def test_quote_mit_seltenheit_fundort_leere_db(tmp_path):
    """Leere DB: quote_mit_seltenheit_fundort_prozent ist None (nicht 0%) -
    keine Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention
    und das Verhalten von quote_mit_seltenheit_global_prozent."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.objekte_mit_seltenheit_fundort == 0
    assert st.quote_mit_seltenheit_fundort_prozent is None
    assert st.as_dict()["quote_mit_seltenheit_fundort_prozent"] is None
    c.close()


def test_quote_mit_nachfrage_aus_seed_db(tmp_path):
    """Coverage-Quote fuer Nachfrage_1_10 (Marktnachfrage-Skala 1..10, 1=keine
    Nachfrage .. 10=hoechste Marktnachfrage). Spiegelt quote_mit_seltenheit_
    global_prozent / quote_mit_seltenheit_fundort_prozent auf die dritte
    ordinale 1..10-Skala aus dem Feldwoerterbuch und schliesst die Coverage-
    Trias der drei Markt-/Bewertungs-Skalen (Seltenheit global / Seltenheit
    Fundort / Nachfrage) ab. NULL und out-of-range-Werte (<1 / >10) zaehlen
    wie nicht-erfasst (Integrity meldet die separat)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qn.sqlite3")
    # 5 Objekte: drei mit gueltigem Marktnachfrage-Score (60 % - Werte 1, 5, 10
    # als typische Keine-/Standard-/Hoechst-Auspraegungen der Skala), zwei ohne
    # (NULL und out-of-range 11 zaehlen nicht). Werte 1 und 10 testen die
    # Skalen-Raender explizit (in-range), 11 testet die out-of-range-Ignorierung.
    c.executemany(
        "INSERT INTO objects (obj_id, Nachfrage_1_10) VALUES (?,?)",
        [
            ("OBJ_0001", 1),     # keine Nachfrage
            ("OBJ_0002", 5),     # Standard-Auspraegung
            ("OBJ_0003", 10),    # hoechste Nachfrage
            ("OBJ_0004", None),  # nicht erfasst -> ignoriert
            ("OBJ_0005", 11),    # out-of-range -> ignoriert (Integrity)
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_nachfrage == 3
    assert st.quote_mit_nachfrage_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_nachfrage"] == 3
    assert d["quote_mit_nachfrage_prozent"] == 60.0
    c.close()


def test_quote_mit_nachfrage_leere_db(tmp_path):
    """Leere DB: quote_mit_nachfrage_prozent ist None (nicht 0%) - keine
    Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention
    und das Verhalten der beiden Seltenheits-Coverage-Quoten."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.objekte_mit_nachfrage == 0
    assert st.quote_mit_nachfrage_prozent is None
    assert st.as_dict()["quote_mit_nachfrage_prozent"] is None
    c.close()


def test_quote_mit_koordinaten_aus_seed_db(tmp_path):
    """Coverage-Quote fuer geocoded Fundort-Subset: Anteil der Objekte, deren
    freitext-Fundort ein per parse_coordinates erkennbares Lat/Lon-Paar enthaelt.
    Spiegelt quote_mit_fundort_prozent (broader Provenienz-Coverage) auf den
    geocoded-Subset und beziffert die Voraussetzung der Bounding-Box-Filter-
    Achse (list_objects_in_bbox). Die Differenz quote_mit_fundort -
    quote_mit_koordinaten beziffert den freitext-only-Anteil (Ortsnamen ohne
    Koordinaten - 'Berner Oberland', 'alte Halde bei X')."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "qk.sqlite3")
    # 5 Objekte: zwei mit parsebaren Koordinaten (40 % - Dezimal mit Hemisphaere
    # und reine Dezimal-Schreibweise als typische Sammler-Notationen), eines mit
    # reinem Ortsnamen ohne Koordinaten (zaehlt nicht-geocoded, aber sehr wohl
    # zur Fundort-Coverage), zwei ohne Fundort (NULL und Whitespace -> beide
    # Coverage-Quoten ignorieren).
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.95° N, 7.45° E"),    # geocoded (Hemisphaeren-Suffix)
            ("OBJ_0002", "47.3769, 8.5417"),       # geocoded (reine Dezimal)
            ("OBJ_0003", "Berner Oberland"),       # Fundort ohne Koordinaten
            ("OBJ_0004", None),                    # kein Fundort
            ("OBJ_0005", "   "),                   # Whitespace
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Geocoded-Subset: 2 von 5 Objekten -> 40.0 %
    assert st.objekte_mit_koordinaten == 2
    assert st.quote_mit_koordinaten_prozent == 40.0
    # Broader Provenienz-Achse: 3 von 5 Objekten haben einen Fundort-Eintrag
    # (zwei geocoded + ein reiner Ortsname), Whitespace/NULL zaehlen nicht.
    # Differenz beziffert den freitext-only-Anteil (hier 1 Objekt = 20 %).
    assert st.objekte_mit_fundort == 3
    assert st.quote_mit_fundort_prozent == 60.0
    d = st.as_dict()
    assert d["objekte_mit_koordinaten"] == 2
    assert d["quote_mit_koordinaten_prozent"] == 40.0
    c.close()


def test_quote_mit_koordinaten_leere_db(tmp_path):
    """Leere DB: quote_mit_koordinaten_prozent ist None (nicht 0%) - keine
    Objekte zum Beziehen der Quote vorhanden, spiegelt _quote-Konvention
    der uebrigen quote_mit_X_prozent-Properties."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.objekte_mit_koordinaten == 0
    assert st.quote_mit_koordinaten_prozent is None
    assert st.as_dict()["quote_mit_koordinaten_prozent"] is None
    c.close()


def test_quote_mit_koordinaten_alle_geocoded(tmp_path):
    """Vollstaendig geocoded: quote_mit_koordinaten_prozent == 100 - obere
    Grenze der Coverage-Skala bei einer durchgehend GPS-protokollierten
    Sammlung (typisch fuer ausschliesslich nach 2010 erfasste Bestaende).
    DMS-Schreibweise zaehlt explizit mit, spiegelt die Akzeptanz-Liste
    von parse_coordinates (Dezimal mit/ohne Hemisphaere, DMS, ISO 6709)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "vg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
            ("OBJ_0002", "47°22'37\"N 8°32'30\"E"),  # DMS
            ("OBJ_0003", "46.95°N 7.45°E"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_koordinaten == 3
    assert st.quote_mit_koordinaten_prozent == 100.0
    # quote_mit_fundort ebenfalls 100 % - jedes geocoded-Stueck ist per
    # Definition auch ein dokumentierter Fundort, daher Obergrenze beider
    # Coverage-Achsen identisch bei vollstaendiger Geocoding.
    assert st.quote_mit_fundort_prozent == 100.0
    c.close()


def test_koordinaten_bbox_aus_seed_db(tmp_path):
    """Geografische Bounding-Box ueber alle geocoded Fundort-Eintraege -
    Aggregations-Achse zur punktuellen list_objects_in_bbox-Sicht. Beziffert
    'wie weit reicht meine Sammlung geografisch?' als minimal-umschliessende
    Lat/Lon-Box. Spiegelt die funddatum_frueheste/spaeteste-Konvention auf
    die geografische Achse: zwei aeussere Grenzen (Min/Max in beiden
    Dimensionen). Whitespace/NULL und Freitext-only-Eintraege (ohne parsbare
    Koordinaten) bleiben aus der Box - spiegelt das None-Verhalten von
    parse_coordinates und die objekte_mit_koordinaten-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bbox.sqlite3")
    # 5 Objekte mit unterschiedlichen Koordinaten-Formen: Bern (~46.95, 7.45),
    # Zuerich (~47.38, 8.54), Sankt Moritz (~46.50, 9.84) als geocoded; ein
    # reiner Ortsname (Berner Oberland) als Freitext-only, eines ohne Fundort.
    # Erwartete Box: lat 46.50..47.38 (Min Moritz, Max Zuerich),
    # lon 7.45..9.84 (Min Bern, Max Moritz).
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.95° N, 7.45° E"),     # Bern
            ("OBJ_0002", "47.3769, 8.5417"),       # Zuerich
            ("OBJ_0003", "46.5000, 9.8400"),       # Sankt Moritz
            ("OBJ_0004", "Berner Oberland"),       # Freitext-only, ignoriert
            ("OBJ_0005", None),                    # kein Fundort, ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_koordinaten == 3
    assert st.koordinaten_bbox is not None
    lat_min, lat_max, lon_min, lon_max = st.koordinaten_bbox
    assert lat_min == pytest.approx(46.5000)
    assert lat_max == pytest.approx(47.3769)
    assert lon_min == pytest.approx(7.45)
    assert lon_max == pytest.approx(9.84)
    # Inverted-Box-Konvention: Min <= Max in beiden Dimensionen,
    # spiegelt list_objects_in_bbox (BETWEEN-inklusiv).
    assert lat_min <= lat_max
    assert lon_min <= lon_max
    # as_dict serialisiert die Box als JSON-taugliche Liste statt Tuple
    # (Tuples sind in JSON nicht direkt darstellbar).
    d = st.as_dict()
    assert d["koordinaten_bbox"] == [lat_min, lat_max, lon_min, lon_max]
    c.close()


def test_koordinaten_bbox_leere_db(tmp_path):
    """Leere DB: koordinaten_bbox ist None (kein Wertegrund fuer Min/Max) -
    spiegelt funddatum_frueheste/spaeteste-Konvention bei leerer Spalte."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.koordinaten_bbox is None
    assert st.as_dict()["koordinaten_bbox"] is None
    c.close()


def test_koordinaten_bbox_punkt_box_bei_einem_geocoded(tmp_path):
    """Bei genau einem geocoded-Stueck kollabiert die Box zur Punkt-Box
    (lat_min == lat_max, lon_min == lon_max). Konsistent zur list_objects_in_bbox-
    Konvention (BETWEEN-inklusiv akzeptiert auch eine entartete Box mit Min==Max)
    und liefert eine gueltige Box, kein None - der Caller kann eine Punkt-Box
    weiterhin als Box-Filter benutzen."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "punkt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),  # einziger geocoded-Eintrag
            ("OBJ_0002", "Berner Oberland"),  # Freitext-only, ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_koordinaten == 1
    assert st.koordinaten_bbox is not None
    lat_min, lat_max, lon_min, lon_max = st.koordinaten_bbox
    assert lat_min == lat_max == pytest.approx(47.3769)
    assert lon_min == lon_max == pytest.approx(8.5417)
    c.close()


def test_koordinaten_bbox_nur_freitext_fundorte(tmp_path):
    """Sammlung mit Fundort-Eintraegen, aber ohne parsbare Koordinaten
    (typisch fuer historisch gewachsene Vor-GPS-Sammlungen): koordinaten_bbox
    bleibt None, obwohl objekte_mit_fundort > 0. Die Differenz zu
    objekte_mit_koordinaten == 0 isoliert den freitext-only-Pflege-Aufwand."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "freitext.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", "alte Halde bei Goschenen"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_fundort == 2
    assert st.objekte_mit_koordinaten == 0
    assert st.koordinaten_bbox is None
    c.close()


def test_koordinaten_zentrum_aus_seed_db(tmp_path):
    """Arithmetisches Mittel von Lat/Lon ueber alle geocoded Fundort-Eintraege -
    geometrische Schwerpunkts-Achse zur Extent-Achse koordinaten_bbox: waehrend
    die Box die aeusseren Grenzen beziffert, gibt das Zentrum den Schwerpunkt
    der Sammlung an. Natuerlicher Default-Mittelpunkt fuer die K-NN-Sicht
    (list_objects_nearest). Freitext-only-Eintraege und NULL bleiben aus dem
    Mittel - spiegelt die objekte_mit_koordinaten/bbox-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "centroid.sqlite3")
    # Drei geocoded Schweiz-Stuecke mit klaren Mittelwerten:
    # lats: 46.0, 47.0, 48.0 -> Mittel 47.0
    # lons: 7.0, 8.0, 9.0 -> Mittel 8.0
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 7.0"),
            ("OBJ_0002", "47.0, 8.0"),
            ("OBJ_0003", "48.0, 9.0"),
            ("OBJ_0004", "Berner Oberland"),   # freitext-only, ignoriert
            ("OBJ_0005", None),                # ohne Fundort, ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_zentrum is not None
    lat_c, lon_c = st.koordinaten_zentrum
    assert lat_c == pytest.approx(47.0)
    assert lon_c == pytest.approx(8.0)
    # Zentrum liegt per Konstruktion innerhalb der Bounding-Box (Mittelwert
    # ueber Min/Max-eingeschlossene Werte), spiegelt die geometrische
    # Grundeigenschaft des arithmetischen Mittels.
    assert st.koordinaten_bbox is not None
    lat_min, lat_max, lon_min, lon_max = st.koordinaten_bbox
    assert lat_min <= lat_c <= lat_max
    assert lon_min <= lon_c <= lon_max
    # as_dict serialisiert das Zentrum als JSON-taugliche Liste statt Tuple.
    d = st.as_dict()
    assert d["koordinaten_zentrum"] == [pytest.approx(47.0), pytest.approx(8.0)]
    c.close()


def test_koordinaten_zentrum_leere_db(tmp_path):
    """Leere DB: koordinaten_zentrum ist None (kein Wertegrund fuer Mittelwert) -
    spiegelt die koordinaten_bbox-Konvention bei leerer Geocoding-Subsammlung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.koordinaten_zentrum is None
    assert st.as_dict()["koordinaten_zentrum"] is None
    c.close()


def test_koordinaten_zentrum_bei_einem_geocoded(tmp_path):
    """Bei genau einem geocoded-Stueck kollabiert das Zentrum auf das Stueck
    selbst (lat_zentrum == lat_einzig, lon_zentrum == lon_einzig). Konsistent
    zur Box-Konvention (Punkt-Box bei einem geocoded-Stueck) und zur
    arithmetischen Mittelwert-Definition ueber einen einzelnen Wert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "einer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_zentrum is not None
    lat_c, lon_c = st.koordinaten_zentrum
    assert lat_c == pytest.approx(47.3769)
    assert lon_c == pytest.approx(8.5417)
    c.close()


def test_koordinaten_radius_max_km_aus_seed_db(tmp_path):
    """Maximale geodaetische Distanz vom Zentrum zu einem geocoded Stueck -
    Streuungs-Achse zum Extent (koordinaten_bbox) und Centroid (koordinaten_
    zentrum). Beziffert die geodaetische Reichweite der Sammlung vom
    Schwerpunkt aus und ist der natuerliche Default-Radius fuer
    list_objects_in_radius mit Zentrum als Mittelpunkt. Freitext-only-
    Eintraege und NULL bleiben aus dem Max - spiegelt die objekte_mit_
    koordinaten/bbox/zentrum-Konvention."""
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "radius.sqlite3")
    # Drei geocoded Schweiz-Stuecke wie im Zentrum-Test:
    # lats: 46.0, 47.0, 48.0 -> Mittel 47.0
    # lons: 7.0, 8.0, 9.0 -> Mittel 8.0
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 7.0"),
            ("OBJ_0002", "47.0, 8.0"),
            ("OBJ_0003", "48.0, 9.0"),
            ("OBJ_0004", "Berner Oberland"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_max_km is not None
    # OBJ_0002 liegt exakt am Zentrum -> Distanz 0; OBJ_0001 und OBJ_0003
    # liegen symmetrisch zum Zentrum, der Max bestimmt sich aus einem der
    # beiden Eck-Stuecke. Haversine-Distanz von (47.0, 8.0) zu (46.0, 7.0):
    earth_radius_km = 6371.0
    lat_c_rad = math.radians(47.0)
    lat_rad = math.radians(46.0)
    dlat = lat_rad - lat_c_rad
    dlon = math.radians(7.0) - math.radians(8.0)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat_c_rad) * math.cos(lat_rad) * math.sin(dlon / 2) ** 2)
    expected = 2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a)))
    assert st.koordinaten_radius_max_km == pytest.approx(expected)
    # Radius muss positiv sein, weil mindestens ein Stueck nicht am Zentrum
    # liegt (Eck-Stuecke sind 1 Grad lat + 1 Grad lon vom Zentrum entfernt).
    assert st.koordinaten_radius_max_km > 0.0
    # Radius bleibt in plausibler Groessenordnung (~100 km fuer 1 Grad
    # Lat/Lon-Versatz in der Naehe der Schweiz).
    assert 100.0 < st.koordinaten_radius_max_km < 200.0
    d = st.as_dict()
    assert d["koordinaten_radius_max_km"] == round(expected, 3)
    c.close()


def test_koordinaten_radius_max_km_leere_db(tmp_path):
    """Leere DB: koordinaten_radius_max_km ist None (kein Wertegrund fuer
    Max-Distanz) - spiegelt die koordinaten_bbox/_zentrum-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer.sqlite3")
    st = compute_statistics(c)
    assert st.koordinaten_radius_max_km is None
    assert st.as_dict()["koordinaten_radius_max_km"] is None
    c.close()


def test_koordinaten_radius_max_km_bei_einem_geocoded(tmp_path):
    """Bei genau einem geocoded-Stueck kollabiert das Zentrum auf das Stueck
    selbst und der Radius auf 0.0 (Distanz vom Punkt zu sich selbst).
    Konsistent zur Punkt-Box-Konvention (lat_min == lat_max) und zur
    Definition des max-Operators ueber einen einzelnen Wert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "einer.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_max_km == pytest.approx(0.0)
    c.close()


def test_koordinaten_radius_max_km_nur_freitext_fundorte(tmp_path):
    """Sammlung mit nur Freitext-Fundorten (keine geocodeden Stuecke):
    koordinaten_radius_max_km ist None, obwohl objekte_mit_fundort > 0.
    Spiegelt die koordinaten_bbox/_zentrum-Konvention bei leerer Geocoding-
    Subsammlung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "freitext.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", "Schwarzwald"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_fundort == 2
    assert st.objekte_mit_koordinaten == 0
    assert st.koordinaten_radius_max_km is None
    assert st.as_dict()["koordinaten_radius_max_km"] is None
    c.close()


def test_koordinaten_radius_durchschnitt_km_aus_seed_db(tmp_path):
    """Arithmetisches Mittel der Haversine-Distanzen vom Zentrum zu jedem
    geocoded Stueck - robuste "typische Streuung"-Achse zur ausreisser-
    dominierten Max-Achse koordinaten_radius_max_km. Spiegelt das wert_
    durchschnitt_chf / wert_max_chf-Paar auf die geografische Streuungs-
    Achse: Mittel + Max = paarweise Aggregations-Sicht (typisch vs.
    extrem) ueber dieselbe Verteilung."""
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "radius_avg.sqlite3")
    # Drei geocoded Schweiz-Stuecke wie im Max-Test: Mittel-Stueck am Zentrum
    # (Distanz 0), zwei Eck-Stuecke mit symmetrischer Distanz (~136 km je).
    # Mittel ueber {0, ~136, ~136} = ~91 km, Max bleibt ~136 km.
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 7.0"),
            ("OBJ_0002", "47.0, 8.0"),
            ("OBJ_0003", "48.0, 9.0"),
            ("OBJ_0004", "Berner Oberland"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_durchschnitt_km is not None
    # Erwarteter Mittelwert: Haversine-Distanzen vom Zentrum (47, 8) zu jedem
    # Punkt - analytisch nachgerechnet.
    earth_radius_km = 6371.0
    lat_c_rad = math.radians(47.0)
    lon_c_rad = math.radians(8.0)
    dists: list[float] = []
    for lat, lon in [(46.0, 7.0), (47.0, 8.0), (48.0, 9.0)]:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        dlat = lat_rad - lat_c_rad
        dlon = lon_rad - lon_c_rad
        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat_c_rad) * math.cos(lat_rad) * math.sin(dlon / 2) ** 2)
        dists.append(2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a))))
    expected = sum(dists) / 3
    assert st.koordinaten_radius_durchschnitt_km == pytest.approx(expected)
    # Mittel muss strikt unter Max liegen, weil mindestens ein Stueck am
    # Zentrum sitzt (Distanz 0 zieht den Mittelwert unter den Max-Wert).
    assert st.koordinaten_radius_durchschnitt_km < st.koordinaten_radius_max_km
    assert st.koordinaten_radius_durchschnitt_km > 0.0
    # Plausibilitaets-Spanne: zwei von drei Punkten ~136 km weg, einer auf
    # dem Zentrum -> Mittel um 91 km.
    assert 80.0 < st.koordinaten_radius_durchschnitt_km < 100.0
    d = st.as_dict()
    assert d["koordinaten_radius_durchschnitt_km"] == round(expected, 3)
    c.close()


def test_koordinaten_radius_durchschnitt_km_leere_db(tmp_path):
    """Leere DB: koordinaten_radius_durchschnitt_km ist None (kein Wertegrund
    fuer Mittelwert) - spiegelt die koordinaten_radius_max_km/zentrum/bbox-
    Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer_avg.sqlite3")
    st = compute_statistics(c)
    assert st.koordinaten_radius_durchschnitt_km is None
    assert st.as_dict()["koordinaten_radius_durchschnitt_km"] is None
    c.close()


def test_koordinaten_radius_durchschnitt_km_bei_einem_geocoded(tmp_path):
    """Bei genau einem geocoded-Stueck kollabieren Max und Durchschnitt
    beide auf 0.0 (Distanz vom Punkt zu sich selbst). Konsistent zur Max-
    Konvention und zur Definition des arithmetischen Mittels ueber einen
    einzelnen Wert."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "einer_avg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_durchschnitt_km == pytest.approx(0.0)
    assert st.koordinaten_radius_max_km == pytest.approx(0.0)
    c.close()


def test_koordinaten_radius_durchschnitt_km_nur_freitext_fundorte(tmp_path):
    """Sammlung mit nur Freitext-Fundorten (keine geocodeden Stuecke):
    koordinaten_radius_durchschnitt_km ist None, obwohl objekte_mit_fundort > 0.
    Spiegelt die koordinaten_radius_max_km-Konvention bei leerer Geocoding-
    Subsammlung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "freitext_avg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", "Schwarzwald"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_durchschnitt_km is None
    assert st.as_dict()["koordinaten_radius_durchschnitt_km"] is None
    c.close()


def test_koordinaten_radius_durchschnitt_km_ausreisser_schiefe(tmp_path):
    """Bei stark ausreisser-dominierten Sammlungen liegt der Durchschnitt
    deutlich unter Max/2 - das ist die Kern-Eigenschaft, die das Mittel-
    Paar zur Max-Achse aussagekraeftig macht. Neun Stuecke am Schweizer-
    Schwerpunkt plus ein einzelner Skandinavien-Ausreisser: das Mittel
    folgt nur leicht dem Ausreisser, sodass der Mittel-Wert nahe der
    Cluster-Konzentration bleibt waehrend der Max-Wert vom Ausreisser
    diktiert wird."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "schief.sqlite3")
    rows = [
        # Neun eng beisammenliegende Bern-Cluster-Stuecke (lat/lon-Streuung
        # innerhalb der Stadt). Der Zentroid bewegt sich nur um ~1/10
        # Richtung Oslo, sodass die Cluster-Punkte nahe am Zentrum bleiben.
        ("OBJ_0001", "46.95, 7.45"),
        ("OBJ_0002", "46.96, 7.45"),
        ("OBJ_0003", "46.95, 7.46"),
        ("OBJ_0004", "46.94, 7.45"),
        ("OBJ_0005", "46.95, 7.44"),
        ("OBJ_0006", "46.93, 7.47"),
        ("OBJ_0007", "46.96, 7.48"),
        ("OBJ_0008", "46.97, 7.43"),
        ("OBJ_0009", "46.94, 7.46"),
        # Ein einzelner Skandinavien-Ausreisser (Oslo).
        ("OBJ_0010", "59.91, 10.75"),
    ]
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)", rows)
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_max_km is not None
    assert st.koordinaten_radius_durchschnitt_km is not None
    # Ausreisser-Schiefe: Durchschnitt deutlich unter Max/2, weil neun von
    # zehn Stuecken nahe beim Schwerpunkt liegen und nur das eine Oslo-Stueck
    # die Max-Achse hochzieht. Bei 9-zu-1-Verteilung liegt das Mittel
    # rechnerisch bei ~Oslo_Distanz * 18 / 100 vs. Max bei ~Oslo_Distanz * 9 / 10,
    # also Mittel / Max ~ 0.2.
    assert (st.koordinaten_radius_durchschnitt_km
            < st.koordinaten_radius_max_km / 2)
    c.close()


def test_koordinaten_radius_median_km_aus_seed_db(tmp_path):
    """Median der Haversine-Distanzen vom Zentrum zu jedem geocoded Stueck -
    ausreisser-robusteste der drei Streuungs-Achsen (Max + Mittel + Median).
    Spiegelt das wert_median_chf / gewicht_median_g-Muster auf die
    geografische Streuungs-Achse."""
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "radius_median.sqlite3")
    # Drei geocoded Schweiz-Stuecke: Mittel-Stueck am Zentrum (47/8,
    # Distanz 0), Eck-Stuecke (46/7) und (48/9). Haversine ist breiten-
    # abhaengig, daher d zu (46,7) != d zu (48,9). Sortiert: [0, d_min,
    # d_max] -> Median = d_min (mittleres Element bei n=3).
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 7.0"),
            ("OBJ_0002", "47.0, 8.0"),
            ("OBJ_0003", "48.0, 9.0"),
            ("OBJ_0004", "Berner Oberland"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_median_km is not None
    earth_radius_km = 6371.0
    lat_c_rad = math.radians(47.0)
    lon_c_rad = math.radians(8.0)
    dists: list[float] = []
    for lat, lon in [(46.0, 7.0), (47.0, 8.0), (48.0, 9.0)]:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        dlat = lat_rad - lat_c_rad
        dlon = lon_rad - lon_c_rad
        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat_c_rad) * math.cos(lat_rad) * math.sin(dlon / 2) ** 2)
        dists.append(2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a))))
    dists.sort()
    expected_median = dists[1]
    assert st.koordinaten_radius_median_km == pytest.approx(expected_median)
    # Median liegt zwischen Mittel und Max: das Zentrum-Stueck zieht den
    # Mittelwert unter den Median, der entfernteste Eck-Punkt zieht den Max
    # darueber. Mittel < Median < Max in dieser Konstellation.
    assert (st.koordinaten_radius_durchschnitt_km
            < st.koordinaten_radius_median_km
            < st.koordinaten_radius_max_km)
    d = st.as_dict()
    assert d["koordinaten_radius_median_km"] == round(expected_median, 3)
    c.close()


def test_koordinaten_radius_median_km_leere_db(tmp_path):
    """Leere DB: koordinaten_radius_median_km ist None (kein Wertegrund fuer
    Median) - spiegelt die koordinaten_radius_max_km/durchschnitt_km/zentrum/
    bbox-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer_median.sqlite3")
    st = compute_statistics(c)
    assert st.koordinaten_radius_median_km is None
    assert st.as_dict()["koordinaten_radius_median_km"] is None
    c.close()


def test_koordinaten_radius_median_km_bei_einem_geocoded(tmp_path):
    """Bei genau einem geocoded-Stueck kollabieren Max, Mittel und Median
    alle auf 0.0 (Distanz vom Punkt zu sich selbst). Spiegelt die Max-/
    Mittel-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "einer_median.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_median_km == pytest.approx(0.0)
    assert st.koordinaten_radius_durchschnitt_km == pytest.approx(0.0)
    assert st.koordinaten_radius_max_km == pytest.approx(0.0)
    c.close()


def test_koordinaten_radius_median_km_nur_freitext_fundorte(tmp_path):
    """Sammlung mit nur Freitext-Fundorten (keine geocodeden Stuecke):
    koordinaten_radius_median_km ist None, obwohl objekte_mit_fundort > 0.
    Spiegelt die koordinaten_radius_max_km/durchschnitt_km-Konvention bei
    leerer Geocoding-Subsammlung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "freitext_median.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", "Schwarzwald"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_median_km is None
    assert st.as_dict()["koordinaten_radius_median_km"] is None
    c.close()


def test_koordinaten_radius_median_km_ausreisser_robust(tmp_path):
    """Kern-Eigenschaft des Median gegenueber Mittel und Max: der Oslo-
    Ausreisser zieht das Zentrum von Bern weg, sodass alle Bern-Cluster-
    Distanzen vom Zentroid in einem engen Band liegen (sortiert: 9 enge
    Bern-zu-Zentroid-Werte + 1 grosser Oslo-Wert). Der Median ist der
    mittlere Bern-zu-Zentroid-Wert (am Oslo-Wert vorbei), das Mittel
    haengt am Oslo-Wert anteilig, der Max bleibt der Oslo-Wert selbst.
    Median < Mittel ≪ Max ist die Robustheits-Signatur."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "median_robust.sqlite3")
    rows = [
        ("OBJ_0001", "46.95, 7.45"),
        ("OBJ_0002", "46.96, 7.45"),
        ("OBJ_0003", "46.95, 7.46"),
        ("OBJ_0004", "46.94, 7.45"),
        ("OBJ_0005", "46.95, 7.44"),
        ("OBJ_0006", "46.93, 7.47"),
        ("OBJ_0007", "46.96, 7.48"),
        ("OBJ_0008", "46.97, 7.43"),
        ("OBJ_0009", "46.94, 7.46"),
        ("OBJ_0010", "59.91, 10.75"),
    ]
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)", rows)
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_median_km is not None
    assert st.koordinaten_radius_durchschnitt_km is not None
    assert st.koordinaten_radius_max_km is not None
    # Median strikt unter Mittel: der Oslo-Wert hebt nur den Mittelwert
    # anteilig (1/10 des Beitrags), nicht den Median (der wird allein
    # vom mittleren sortierten Element bestimmt, ein Bern-zu-Zentroid-Wert).
    assert (st.koordinaten_radius_median_km
            < st.koordinaten_radius_durchschnitt_km)
    # Robustheits-Spread: Max / Median > 5 - der Oslo-Wert dominiert die
    # Max-Achse vollstaendig, waehrend der Median im Bern-zu-Zentroid-
    # Band bleibt.
    assert (st.koordinaten_radius_max_km
            > 5 * st.koordinaten_radius_median_km)
    c.close()


def test_koordinaten_radius_median_km_gerade_anzahl(tmp_path):
    """Bei gerader Anzahl geocoded-Stueck wird der Median als Mittel der
    beiden mittleren sortierten Elemente berechnet (klassische Median-
    Definition, spiegelt wert_median_chf/gewicht_median_g exakt)."""
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "median_gerade.sqlite3")
    # Vier geocoded Stuecke um das Zentroid (46.5/7.5). Haversine ist
    # breitenabhaengig (cos(lat)-Term), daher liefern die zwei suedlichen
    # Eck-Punkte einen anderen Distanzwert als die zwei noerdlichen.
    # Sortiert [d_n, d_n, d_s, d_s] -> Median = (d_n + d_s) / 2, was wegen
    # der paarweisen Symmetrie auch dem Mittelwert aller vier Distanzen
    # entspricht (Median == Mittel bei gleichgewichtigem Nord/Sued-Paar).
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 7.0"),
            ("OBJ_0002", "46.0, 8.0"),
            ("OBJ_0003", "47.0, 7.0"),
            ("OBJ_0004", "47.0, 8.0"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_median_km is not None
    earth_radius_km = 6371.0
    lat_c_rad = math.radians(46.5)
    lon_c_rad = math.radians(7.5)
    dists: list[float] = []
    for lat, lon in [(46.0, 7.0), (46.0, 8.0), (47.0, 7.0), (47.0, 8.0)]:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        dlat = lat_rad - lat_c_rad
        dlon = lon_rad - lon_c_rad
        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat_c_rad) * math.cos(lat_rad) * math.sin(dlon / 2) ** 2)
        dists.append(2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a))))
    dists.sort()
    expected_median = (dists[1] + dists[2]) / 2
    assert st.koordinaten_radius_median_km == pytest.approx(expected_median)
    # Median == Mittel bei gleichgewichtigem Nord/Sued-Paar (jede der zwei
    # Distanzen kommt genau zweimal vor) - der Median-Wert ist (d_n + d_s)/2,
    # der Mittelwert ist (2*d_n + 2*d_s)/4 = (d_n + d_s)/2.
    assert st.koordinaten_radius_median_km == pytest.approx(
        st.koordinaten_radius_durchschnitt_km)
    # Max ist die groessere der beiden Distanzen (suedliches Paar), strikt
    # ueber dem Median.
    assert st.koordinaten_radius_max_km > st.koordinaten_radius_median_km
    c.close()


def test_koordinaten_radius_min_km_aus_seed_db(tmp_path):
    """Kleinste Haversine-Distanz vom Zentrum zu einem geocoded Stueck -
    Innen-Achse (naechster Fund am Schwerpunkt) als symmetrisches Pendant
    zur Aussen-Achse koordinaten_radius_max_km. Spiegelt das
    mohs_kollektion_min/max, dichte_kollektion_min/max, wert_min/max_chf-
    Paar-Muster auf die geografische Streuungs-Achse."""
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "radius_min.sqlite3")
    # Drei geocoded Stuecke entlang derselben Laenge, asymmetrisch zum
    # Zentroid: (45,8), (47,8), (48,8). Zentroid = ((45+47+48)/3, 8) =
    # (46.667, 8). Alle drei Distanzen unterscheiden sich - das nahe
    # Stueck (47,8) ist am Zentroid am naechsten und definiert Min,
    # das entfernte Stueck (45,8) definiert Max.
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "45.0, 8.0"),
            ("OBJ_0002", "47.0, 8.0"),
            ("OBJ_0003", "48.0, 8.0"),
            ("OBJ_0004", "Berner Oberland"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_min_km is not None
    earth_radius_km = 6371.0
    lat_c = (45.0 + 47.0 + 48.0) / 3
    lon_c = 8.0
    lat_c_rad = math.radians(lat_c)
    lon_c_rad = math.radians(lon_c)
    dists: list[float] = []
    for lat, lon in [(45.0, 8.0), (47.0, 8.0), (48.0, 8.0)]:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        dlat = lat_rad - lat_c_rad
        dlon = lon_rad - lon_c_rad
        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat_c_rad) * math.cos(lat_rad) * math.sin(dlon / 2) ** 2)
        dists.append(2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a))))
    expected_min = min(dists)
    assert st.koordinaten_radius_min_km == pytest.approx(expected_min)
    # Ordnungs-Invariante der vier Achsen: Min <= Mittel <= Max, wobei die
    # Ungleichungen strikt sind, weil die drei Distanzen paarweise
    # verschieden sind.
    assert (st.koordinaten_radius_min_km
            < st.koordinaten_radius_durchschnitt_km
            < st.koordinaten_radius_max_km)
    # Median liegt zwischen Min und Max (bei drei paarweise verschiedenen
    # Werten ist der Median das mittlere sortierte Element).
    assert (st.koordinaten_radius_min_km
            < st.koordinaten_radius_median_km
            < st.koordinaten_radius_max_km)
    d = st.as_dict()
    assert d["koordinaten_radius_min_km"] == round(expected_min, 3)
    c.close()


def test_koordinaten_radius_min_km_leere_db(tmp_path):
    """Leere DB: koordinaten_radius_min_km ist None (kein Wertegrund fuer
    Min) - spiegelt die koordinaten_radius_max_km/durchschnitt_km/median_km/
    zentrum/bbox-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer_min.sqlite3")
    st = compute_statistics(c)
    assert st.koordinaten_radius_min_km is None
    assert st.as_dict()["koordinaten_radius_min_km"] is None
    c.close()


def test_koordinaten_radius_min_km_bei_einem_geocoded(tmp_path):
    """Bei genau einem geocoded-Stueck kollabieren Min, Max, Mittel und
    Median alle auf 0.0 (Distanz vom Punkt zu sich selbst). Spiegelt die
    Max-/Mittel-/Median-Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "einer_min.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_min_km == pytest.approx(0.0)
    assert st.koordinaten_radius_durchschnitt_km == pytest.approx(0.0)
    assert st.koordinaten_radius_median_km == pytest.approx(0.0)
    assert st.koordinaten_radius_max_km == pytest.approx(0.0)
    c.close()


def test_koordinaten_radius_min_km_nur_freitext_fundorte(tmp_path):
    """Sammlung mit nur Freitext-Fundorten (keine geocodeden Stuecke):
    koordinaten_radius_min_km ist None, obwohl objekte_mit_fundort > 0.
    Spiegelt die koordinaten_radius_max_km/durchschnitt_km/median_km-
    Konvention bei leerer Geocoding-Subsammlung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "freitext_min.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", "Schwarzwald"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_min_km is None
    assert st.as_dict()["koordinaten_radius_min_km"] is None
    c.close()


def test_koordinaten_radius_min_km_isotrope_verteilung(tmp_path):
    """Zwei geocoded Stuecke symmetrisch um den Schwerpunkt: alle Distanzen
    vom Zentroid sind gleich, daher Min == Max == Mittel == Median. Die
    isotrope Rand-Konfiguration - jeder Fund liegt exakt auf dem gleichen
    Ring um den Schwerpunkt herum."""
    import math
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "isotrop_min.sqlite3")
    # Zwei Punkte symmetrisch entlang derselben Laenge um den Schwerpunkt
    # (47,8): (46,8) und (48,8). Zentroid = (47,8), beide Distanzen exakt
    # gleich (Haversine ist symmetrisch entlang der Laenge bei gleicher
    # Distanz von der mittleren Breite).
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 8.0"),
            ("OBJ_0002", "48.0, 8.0"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_radius_min_km is not None
    earth_radius_km = 6371.0
    lat_c_rad = math.radians(47.0)
    lon_c_rad = math.radians(8.0)
    dists: list[float] = []
    for lat, lon in [(46.0, 8.0), (48.0, 8.0)]:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        dlat = lat_rad - lat_c_rad
        dlon = lon_rad - lon_c_rad
        a = (math.sin(dlat / 2) ** 2
             + math.cos(lat_c_rad) * math.cos(lat_rad) * math.sin(dlon / 2) ** 2)
        dists.append(2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a))))
    assert dists[0] == pytest.approx(dists[1])
    assert st.koordinaten_radius_min_km == pytest.approx(dists[0])
    # Kollaps aller vier Achsen bei isotroper Ring-Verteilung: Min = Max
    # = Mittel = Median = der einzige vorkommende Distanz-Wert.
    assert st.koordinaten_radius_min_km == pytest.approx(
        st.koordinaten_radius_max_km)
    assert st.koordinaten_radius_min_km == pytest.approx(
        st.koordinaten_radius_durchschnitt_km)
    assert st.koordinaten_radius_min_km == pytest.approx(
        st.koordinaten_radius_median_km)
    c.close()


def _haversine_km(lat1: float, lon1: float,
                  lat2: float, lon2: float) -> float:
    """Test-Helper: Haversine-Distanz zwischen zwei Punkten in km.

    Spiegelt die in compute_statistics und repository.list_objects_in_radius/
    _nearest verwendete Formel exakt (Erd-Sphaere mit Radius 6371.0 km) -
    damit der erwartete Diameter unabhaengig in den Tests berechnet werden
    kann, ohne die Implementierung zu spiegeln.
    """
    import math
    earth_radius_km = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    return 2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a)))


def test_koordinaten_diameter_km_aus_seed_db(tmp_path):
    """Maximaler paarweise Abstand zwischen je zwei geocoded Stuecken -
    die geografische Sammlungs-Spannweite als Punkt-Paar-Achse zur
    Schwerpunkts-Achse koordinaten_radius_max_km. Spiegelt das Punkt-Paar-
    Konzept als orthogonale Sicht zur Zentroid-Sicht."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "diameter.sqlite3")
    # Drei geocoded Stuecke: (46,7), (47,8), (48,9). Das groesste Paar ist
    # (46,7) <-> (48,9), spiegelt list_objects_in_bbox-typische Sammlungs-
    # Geometrie. Freitext-/None-Eintraege werden ignoriert wie bei
    # koordinaten_radius_*.
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 7.0"),
            ("OBJ_0002", "47.0, 8.0"),
            ("OBJ_0003", "48.0, 9.0"),
            ("OBJ_0004", "Berner Oberland"),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_diameter_km is not None
    expected = _haversine_km(46.0, 7.0, 48.0, 9.0)
    assert st.koordinaten_diameter_km == pytest.approx(expected)
    # Geometrische Invariante: radius_max <= diameter <= 2*radius_max.
    # Linke Schranke gilt strikt < hier, weil das mittlere Stueck (47,8)
    # mit dem Zentroid kollidiert und die Aussen-Stuecke das paarweise
    # Maximum bilden.
    assert (st.koordinaten_radius_max_km
            <= st.koordinaten_diameter_km
            <= 2 * st.koordinaten_radius_max_km)
    d = st.as_dict()
    assert d["koordinaten_diameter_km"] == round(expected, 3)
    c.close()


def test_koordinaten_diameter_km_leere_db(tmp_path):
    """Leere DB: koordinaten_diameter_km ist None (kein Wertegrund fuer
    paarweise Maximum) - spiegelt die koordinaten_radius_*/zentrum/bbox-
    Konvention."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "leer_diameter.sqlite3")
    st = compute_statistics(c)
    assert st.koordinaten_diameter_km is None
    assert st.as_dict()["koordinaten_diameter_km"] is None
    c.close()


def test_koordinaten_diameter_km_bei_einem_geocoded(tmp_path):
    """Bei genau einem geocoded-Stueck kollabiert der Durchmesser auf 0.0
    (kein Paar, der Punkt zu sich selbst hat Distanz 0). Spiegelt die
    koordinaten_radius_max/durchschnitt/median-Konvention bei n=1."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "einer_diameter.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "47.3769, 8.5417"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_diameter_km == pytest.approx(0.0)
    assert st.koordinaten_radius_max_km == pytest.approx(0.0)
    c.close()


def test_koordinaten_diameter_km_nur_freitext_fundorte(tmp_path):
    """Sammlung mit nur Freitext-Fundorten: koordinaten_diameter_km ist None,
    obwohl objekte_mit_fundort > 0. Spiegelt die koordinaten_radius_*-Konvention
    bei leerer Geocoding-Subsammlung."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "freitext_diameter.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "Berner Oberland"),
            ("OBJ_0002", "Schwarzwald"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_diameter_km is None
    assert st.as_dict()["koordinaten_diameter_km"] is None
    c.close()


def test_koordinaten_diameter_km_groesser_als_radius_max_bei_bipolarer_sammlung(
        tmp_path):
    """Bipolare Sammlung (zwei diametrale Cluster um den Zentroid):
    diameter ~ 2*radius_max - der Zentroid liegt genau zwischen den zwei
    aeussersten Stuecken, sodass beide etwa gleich weit vom Schwerpunkt
    entfernt sind und ihr paarweiser Abstand die maximale Spannweite
    bildet. Differenziert klar vom einseitig geclusterten Fall (siehe
    Schiefe-Test), wo diameter deutlich unter 2*radius_max liegt."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "bipolar_diameter.sqlite3")
    # Zwei spiegelsymmetrische Stuecke um (47,8): (46,7) und (48,9).
    # Zentroid = (47,8) genau in der Mitte. Radius_max ist die Distanz
    # vom Zentroid zu einem der Eckpunkte, der Durchmesser ist die
    # Distanz zwischen den zwei Eckpunkten -> exakt 2*radius_max
    # (modulo Sphaeren-Verzerrung, die bei 2 Grad Spannweite minimal ist).
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)",
        [
            ("OBJ_0001", "46.0, 7.0"),
            ("OBJ_0002", "48.0, 9.0"),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_diameter_km is not None
    assert st.koordinaten_radius_max_km is not None
    # Bei diametraler Verteilung um den Zentroid liegt der Durchmesser
    # nahe 2*radius_max (Sphaeren-Verzerrung bei 2 Grad Lat/Lon-Span
    # bleibt klein, daher Abweichung < 0.5 %).
    assert st.koordinaten_diameter_km == pytest.approx(
        2 * st.koordinaten_radius_max_km, rel=0.005)
    c.close()


def test_koordinaten_diameter_km_einseitig_geclusterte_sammlung(tmp_path):
    """Einseitig geclusterte Sammlung (9 enge Stuecke + 1 Ausreisser):
    der Zentroid wird zum Ausreisser gezogen, sodass radius_max gross wird
    (Distanz vom verschobenen Zentroid zum am weitesten weg liegenden
    Cluster-Punkt) - der Durchmesser bleibt jedoch konstant der Cluster-
    zu-Ausreisser-Abstand. Diameter < 2*radius_max ist die Schiefe-
    Signatur, klar abgegrenzt vom bipolaren Fall (diameter ~ 2*radius_max)."""
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "schief_diameter.sqlite3")
    # 9 Bern-Stuecke (46.95/7.45 +/- 0.02) + 1 Oslo-Stueck. Der Durchmesser
    # ist die Bern-zu-Oslo-Distanz (alle anderen Paare sind enger). Der
    # Zentroid wird durch Oslo um ca. 1/10 in Richtung Oslo verschoben.
    rows = [
        ("OBJ_0001", "46.95, 7.45"),
        ("OBJ_0002", "46.96, 7.45"),
        ("OBJ_0003", "46.95, 7.46"),
        ("OBJ_0004", "46.94, 7.45"),
        ("OBJ_0005", "46.95, 7.44"),
        ("OBJ_0006", "46.93, 7.47"),
        ("OBJ_0007", "46.96, 7.48"),
        ("OBJ_0008", "46.97, 7.43"),
        ("OBJ_0009", "46.94, 7.46"),
        ("OBJ_0010", "59.91, 10.75"),
    ]
    c.executemany(
        "INSERT INTO objects (obj_id, Fundort) VALUES (?,?)", rows)
    c.commit()
    st = compute_statistics(c)
    assert st.koordinaten_diameter_km is not None
    assert st.koordinaten_radius_max_km is not None
    # Durchmesser ist die Bern-zu-Oslo-Distanz. Naehert sich der Bern-
    # zu-Oslo-Direktdistanz nicht ueber radius_max hinaus an (radius_max
    # ist die Distanz vom verschobenen Zentroid zum aeussersten Punkt,
    # der Durchmesser ist die volle Bern-Oslo-Distanz).
    bern_oslo = _haversine_km(46.95, 7.45, 59.91, 10.75)
    assert st.koordinaten_diameter_km == pytest.approx(bern_oslo, rel=0.01)
    # Schiefe-Signatur: diameter strikt < 2*radius_max (Bern-Cluster zieht
    # den Zentroid in Richtung Bern, sodass radius_max nur knapp ueber der
    # Haelfte des Durchmessers liegt - wenn Oslo der einzige weit-entfernte
    # Punkt ist, dominiert er die Radius-Berechnung und liegt nahe der
    # vollen Durchmesser-Distanz).
    assert st.koordinaten_diameter_km < 2 * st.koordinaten_radius_max_km
    # Geometrische Invariante: radius_max <= diameter immer.
    assert st.koordinaten_radius_max_km <= st.koordinaten_diameter_km
    c.close()


def test_wert_variationskoeffizient_aus_seed_db(tmp_path):
    """CV = sigma / mean * 100 in Prozent, dimensionslose Dispersions-Achse.

    Vier Werte 100/200/300/400 → Ø=250, sigma=sqrt(12500)≈111.803.
    CV = 111.803 / 250 * 100 ≈ 44.72 %. Spiegelt
    test_wert_standardabweichung_aus_seed_db (gleicher Seed) auf die
    dimensionslose Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_cv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [
            ("OBJ_0001", 100.0),
            ("OBJ_0002", 200.0),
            ("OBJ_0003", 300.0),
            ("OBJ_0004", 400.0),
            ("OBJ_0005", None),
            ("OBJ_0006", 0.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_durchschnitt_chf == 250.0
    expected_cv = (12500.0 ** 0.5) / 250.0 * 100.0
    assert st.wert_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-9)
    d = st.as_dict()
    assert d["wert_variationskoeffizient_prozent"] == pytest.approx(
        44.72, abs=1e-2)
    c.close()


def test_wert_variationskoeffizient_leer(tmp_path):
    """Ohne Wert-Pflege bleibt der CV None (dataclass-Default).

    CV ist mathematisch undefined bei mean = 0 (Division durch Null),
    anders als sigma (0.0 bei leerer DB). Die None-Konvention macht den
    Undefined-Zustand fuer Downstream-Konsumenten (as_dict / CLI-Zeile /
    Dashboard) transparent unterscheidbar. Spiegelt die mohs_kollektion_
    / dichte_kollektion_-None-Konvention (mean-basierte Groessen mit
    None statt 0.0 im Undefined-Fall).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_cv_leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_variationskoeffizient_prozent is None
    d = st.as_dict()
    assert d["wert_variationskoeffizient_prozent"] is None
    c.close()


def test_wert_variationskoeffizient_einzelobjekt(tmp_path):
    """Bei einem einzelnen Wert-Eintrag kollabiert der CV auf 0.0.

    sigma = 0 bei nur einem Datenpunkt → CV = 0/mean * 100 = 0.0. Die
    Sammlung hat 100% Homogenitaet (weil nur ein Stueck vorhanden ist).
    CV ist definiert (nicht None), weil mean > 0 (der Einzelwert selbst).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_cv_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 500.0), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 1
    assert st.wert_variationskoeffizient_prozent == 0.0
    c.close()


def test_wert_variationskoeffizient_uniform(tmp_path):
    """Bei identischen Werten ist der CV 0.0 (voellige Homogenitaet).

    Reine Feldspat-Sammlung ohne Preisdispersion: fuenf Stuecke CHF 50 →
    sigma = 0.0 → CV = 0.0 %. Kern-Eigenschaft der skalen-unabhaengigen
    Dispersions-Achse: nicht der Preis-Level, sondern die relative
    Streuung ist massgeblich.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_cv_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_%04d" % i, 50.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_variationskoeffizient_prozent == 0.0
    c.close()


def test_wert_variationskoeffizient_skalen_invariant(tmp_path):
    """CV ist skalen-invariant: eine 10-fache Aufwertung aendert CV nicht.

    Kern-Eigenschaft des Variationskoeffizienten (sigma/mean skaliert
    mit demselben Faktor wie die Werte). Zwei Sammlungen 10/20/30/40 und
    100/200/300/400 haben unterschiedliche sigma (1x vs. 10x) und
    unterschiedliche mean (1x vs. 10x), aber identische CVs.
    """
    from stonebook.db.database import open_db
    c1 = open_db(tmp_path / "w_cv_klein.sqlite3")
    c1.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 10.0), ("OBJ_0002", 20.0),
         ("OBJ_0003", 30.0), ("OBJ_0004", 40.0)],
    )
    c1.commit()
    cv_klein = compute_statistics(c1).wert_variationskoeffizient_prozent
    c1.close()

    c2 = open_db(tmp_path / "w_cv_gross.sqlite3")
    c2.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 100.0), ("OBJ_0002", 200.0),
         ("OBJ_0003", 300.0), ("OBJ_0004", 400.0)],
    )
    c2.commit()
    cv_gross = compute_statistics(c2).wert_variationskoeffizient_prozent
    c2.close()

    assert cv_klein is not None and cv_gross is not None
    assert cv_klein == pytest.approx(cv_gross, abs=1e-9)


def test_wert_variationskoeffizient_reagiert_auf_ausreisser(tmp_path):
    """CV reagiert auf Wert-Ausreisser (Erbe von sigma).

    Neun gleichmaessige Feldspat-Stuecke (CHF 50) plus ein Investment-
    Bergkristall (CHF 5000). Aus test_wert_standardabweichung_reagiert_
    auf_ausreisser: Ø = 545, sigma = 1485.0 exakt. CV = 1485/545 * 100
    ≈ 272.48 %. Zeigt die versicherungsrelevante Charakterisierung
    "eine hoch-heterogene Sammlung mit dominierender Einzel-Position"
    an einer einzigen dimensionslosen Kennzahl (im Kontrast zur
    Feldspat-Klasse mit CV 0%).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_cv_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 50.0) for i in range(1, 10)]
    rows.append(("OBJ_0010", 5000.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)", rows)
    c.commit()
    st = compute_statistics(c)
    expected_cv = 1485.0 / 545.0 * 100.0
    assert st.wert_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-9)
    c.close()


def test_gewicht_variationskoeffizient_aus_seed_db(tmp_path):
    """CV Gewicht = sigma / mean * 100 in Prozent auf der Massen-Achse.

    Spiegelt test_wert_variationskoeffizient_aus_seed_db auf die Gewicht-
    Achse. Aus test_gewicht_standardabweichung_aus_seed_db (gleicher
    Seed): 10/20/30/40 → Ø=25, sigma=sqrt(125)≈11.180.
    CV = 11.180 / 25 * 100 ≈ 44.72 % (identisch zum Wert-CV bei gleichen
    proportionalen Werten, weil CV skalen-invariant ist).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_cv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [
            ("OBJ_0001", 10.0),
            ("OBJ_0002", 20.0),
            ("OBJ_0003", 30.0),
            ("OBJ_0004", 40.0),
            ("OBJ_0005", None),
            ("OBJ_0006", 0.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_durchschnitt_g == 25.0
    expected_cv = (125.0 ** 0.5) / 25.0 * 100.0
    assert st.gewicht_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-9)
    d = st.as_dict()
    assert d["gewicht_variationskoeffizient_prozent"] == pytest.approx(
        44.72, abs=1e-2)
    c.close()


def test_gewicht_variationskoeffizient_leer(tmp_path):
    """Ohne Gewicht-Pflege bleibt der CV None (dataclass-Default).

    Spiegelt die wert_variationskoeffizient_prozent-None-Konvention:
    CV ist mathematisch undefined bei mean = 0, anders als sigma (0.0
    bei leerer DB). None macht den Undefined-Zustand fuer Downstream-
    Konsumenten (as_dict / CLI / Dashboard) transparent unterscheidbar.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_cv_leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_variationskoeffizient_prozent is None
    d = st.as_dict()
    assert d["gewicht_variationskoeffizient_prozent"] is None
    c.close()


def test_gewicht_variationskoeffizient_einzelobjekt(tmp_path):
    """Bei einem einzelnen Gewicht-Eintrag kollabiert der CV auf 0.0.

    sigma = 0 bei nur einem Datenpunkt → CV = 0/mean * 100 = 0.0.
    Spiegelt test_wert_variationskoeffizient_einzelobjekt auf die
    Massen-Achse. CV ist definiert (nicht None), weil mean > 0 (der
    Einzel-Gewicht-Wert selbst).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_cv_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_0001", 42.5), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_gewicht == 1
    assert st.gewicht_variationskoeffizient_prozent == 0.0
    c.close()


def test_gewicht_variationskoeffizient_uniform(tmp_path):
    """Bei identischen Gewichten ist der CV 0.0 (voellige Homogenitaet).

    Kern-Eigenschaft der skalen-unabhaengigen Dispersions-Achse:
    fuenf Stuecke a 100 g → sigma 0.0 → CV 0.0 %. Spiegelt
    test_wert_variationskoeffizient_uniform auf die Massen-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_cv_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_%04d" % i, 100.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_variationskoeffizient_prozent == 0.0
    c.close()


def test_gewicht_variationskoeffizient_skalen_invariant(tmp_path):
    """CV Gewicht ist skalen-invariant: eine 10-fache Umskalierung aendert CV nicht.

    Kern-Eigenschaft des Variationskoeffizienten (sigma/mean skaliert
    mit demselben Faktor wie die Werte). Zwei Sammlungen 1/2/3/4 g und
    10/20/30/40 g haben unterschiedliche sigma und unterschiedliche
    mean, aber identische CVs.
    """
    from stonebook.db.database import open_db
    c1 = open_db(tmp_path / "g_cv_klein.sqlite3")
    c1.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_0001", 1.0), ("OBJ_0002", 2.0),
         ("OBJ_0003", 3.0), ("OBJ_0004", 4.0)],
    )
    c1.commit()
    cv_klein = compute_statistics(c1).gewicht_variationskoeffizient_prozent
    c1.close()

    c2 = open_db(tmp_path / "g_cv_gross.sqlite3")
    c2.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_0001", 10.0), ("OBJ_0002", 20.0),
         ("OBJ_0003", 30.0), ("OBJ_0004", 40.0)],
    )
    c2.commit()
    cv_gross = compute_statistics(c2).gewicht_variationskoeffizient_prozent
    c2.close()

    assert cv_klein is not None and cv_gross is not None
    assert cv_klein == pytest.approx(cv_gross, abs=1e-9)


def test_gewicht_variationskoeffizient_reagiert_auf_ausreisser(tmp_path):
    """CV Gewicht reagiert auf Massen-Ausreisser (Erbe von sigma).

    Aus test_gewicht_standardabweichung_reagiert_auf_ausreisser: neun
    Splitter (1 g) + ein Handstueck (100 g). Ø = 10.9, sigma ≈ 29.7.
    CV = 29.7 / 10.9 * 100 ≈ 272 %. Zeigt die hochgradig heterogene
    Massen-Verteilung an einer einzigen dimensionslosen Kennzahl,
    komplementaer zu Median (bleibt bei 1.0 g).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_cv_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 1.0) for i in range(1, 10)]
    rows.append(("OBJ_0010", 100.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)", rows)
    c.commit()
    st = compute_statistics(c)
    # sigma ≈ sqrt(882.09), mean = 10.9
    expected_cv = (882.09 ** 0.5) / 10.9 * 100.0
    assert st.gewicht_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-6)
    c.close()


def test_mohs_variationskoeffizient_aus_seed_db(tmp_path):
    """CV Mohs = sigma / mean * 100 in Prozent auf der Haerte-Achse.

    Spiegelt test_wert_variationskoeffizient_aus_seed_db und
    test_gewicht_variationskoeffizient_aus_seed_db auf die Mohs-Achse.
    Vier Mohs-Mittelpunkte 3/4/5/6 → Ø=4.5, Varianz=((3-4.5)^2 +
    (4-4.5)^2 + (5-4.5)^2 + (6-4.5)^2)/4 = (2.25+0.25+0.25+2.25)/4 =
    5/4 = 1.25 → sigma = sqrt(1.25) ≈ 1.118. CV = 1.118 / 4.5 * 100
    ≈ 24.85 %.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_cv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 3.0, 3.0),
            ("OBJ_0002", 4.0, 4.0),
            ("OBJ_0003", 5.0, 5.0),
            ("OBJ_0004", 6.0, 6.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_durchschnitt == pytest.approx(4.5, abs=1e-9)
    expected_cv = (1.25 ** 0.5) / 4.5 * 100.0
    assert st.mohs_kollektion_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-6)
    d = st.as_dict()
    assert d["mohs_kollektion_variationskoeffizient_prozent"] == pytest.approx(
        24.85, abs=1e-2)
    c.close()


def test_mohs_variationskoeffizient_leer(tmp_path):
    """Ohne Mohs-Pflege bleibt der CV None (dataclass-Default).

    Spiegelt die mohs_kollektion_standardabweichung- / _durchschnitt-
    None-Konvention: mean-basierte Groessen sind bei mean-Undefined
    ebenfalls None, nicht 0.0.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_cv_leer.sqlite3")
    st = compute_statistics(c)
    assert st.mohs_kollektion_variationskoeffizient_prozent is None
    d = st.as_dict()
    assert d["mohs_kollektion_variationskoeffizient_prozent"] is None
    c.close()


def test_mohs_variationskoeffizient_uniform(tmp_path):
    """Bei identischer Mohs-Haerte ist der CV 0.0 (voellige Homogenitaet).

    Reine Quarz-Sammlung mit fuenf Stuecken Mohs 7.0 → sigma 0.0 →
    CV 0.0 %. Spiegelt test_wert_variationskoeffizient_uniform /
    test_gewicht_variationskoeffizient_uniform.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_cv_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_%04d" % i, 7.0, 7.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_variationskoeffizient_prozent == pytest.approx(
        0.0, abs=1e-9)
    c.close()


def test_mohs_variationskoeffizient_reagiert_auf_ausreisser(tmp_path):
    """CV Mohs reagiert auf Haerte-Ausreisser (Erbe von sigma).

    Neun Quarz-Stuecke (Mohs 7.0) + ein Talk-Ausreisser (Mohs 1.0).
    Ø = (9*7 + 1)/10 = 6.4. Varianz = (9*(7-6.4)^2 + (1-6.4)^2)/10 =
    (9*0.36 + 29.16)/10 = (3.24 + 29.16)/10 = 3.24 → sigma = sqrt(3.24)
    = 1.8. CV = 1.8 / 6.4 * 100 = 28.125 %. Zeigt die mineralogische
    Heterogenitaet an einer skalen-unabhaengigen Kennzahl direkt
    vergleichbar mit CV Wert und CV Gewicht.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_cv_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 7.0, 7.0) for i in range(1, 10)]
    rows.append(("OBJ_0010", 1.0, 1.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)", rows)
    c.commit()
    st = compute_statistics(c)
    expected_cv = 1.8 / 6.4 * 100.0
    assert st.mohs_kollektion_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-4)
    c.close()


def test_dichte_variationskoeffizient_aus_seed_db(tmp_path):
    """CV Dichte = sigma / mean * 100 in Prozent auf der Dichte-Achse.

    Vervollstaendigt das CV-Quartett Wert / Gewicht / Mohs / Dichte.
    Vier Dichte-Mittelpunkte 2.0/3.0/4.0/5.0 g/cm3 → Ø=3.5,
    Varianz=((2-3.5)^2 + (3-3.5)^2 + (4-3.5)^2 + (5-3.5)^2)/4 =
    (2.25+0.25+0.25+2.25)/4 = 5/4 = 1.25 → sigma = sqrt(1.25) ≈ 1.118.
    CV = 1.118 / 3.5 * 100 ≈ 31.94 %.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_cv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.0, 2.0),
            ("OBJ_0002", 3.0, 3.0),
            ("OBJ_0003", 4.0, 4.0),
            ("OBJ_0004", 5.0, 5.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_durchschnitt == pytest.approx(3.5, abs=1e-9)
    expected_cv = (1.25 ** 0.5) / 3.5 * 100.0
    assert st.dichte_kollektion_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-6)
    d = st.as_dict()
    assert d["dichte_kollektion_variationskoeffizient_prozent"] == pytest.approx(
        31.94, abs=1e-2)
    c.close()


def test_dichte_variationskoeffizient_leer(tmp_path):
    """Ohne Dichte-Pflege bleibt der CV None (dataclass-Default).

    Spiegelt die dichte_kollektion_standardabweichung- / _durchschnitt-
    None-Konvention.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_cv_leer.sqlite3")
    st = compute_statistics(c)
    assert st.dichte_kollektion_variationskoeffizient_prozent is None
    d = st.as_dict()
    assert d["dichte_kollektion_variationskoeffizient_prozent"] is None
    c.close()


def test_dichte_variationskoeffizient_uniform(tmp_path):
    """Bei identischer Dichte ist der CV 0.0 (voellige Homogenitaet).

    Reine Quarz-Sammlung mit fuenf Stuecken Dichte 2.65 g/cm3 →
    sigma 0.0 → CV 0.0 %. Vervollstaendigt die Uniform-Kollaps-
    Konvention aus dem CV-Quartett.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_cv_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_%04d" % i, 2.65, 2.65) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_variationskoeffizient_prozent == pytest.approx(
        0.0, abs=1e-9)
    c.close()


def test_dichte_variationskoeffizient_reagiert_auf_ausreisser(tmp_path):
    """CV Dichte reagiert auf Dichte-Ausreisser (Erbe von sigma).

    Neun Quarz-Stuecke (Dichte 2.65) + ein Galenit-Ausreisser (7.5).
    Ø = (9*2.65 + 7.5)/10 = (23.85 + 7.5)/10 = 3.135.
    Varianz = (9*(2.65-3.135)^2 + (7.5-3.135)^2)/10
            = (9*0.235225 + 19.053225)/10
            = (2.117025 + 19.053225)/10 = 21.17025/10 = 2.117025
    → sigma = sqrt(2.117025) ≈ 1.4550...
    CV ≈ 1.4550 / 3.135 * 100 ≈ 46.4 %.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_cv_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 2.65, 2.65) for i in range(1, 10)]
    rows.append(("OBJ_0010", 7.5, 7.5))
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)", rows)
    c.commit()
    st = compute_statistics(c)
    expected_cv = (2.117025 ** 0.5) / 3.135 * 100.0
    assert st.dichte_kollektion_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-2)
    c.close()


def test_confidence_min_prozent_aus_seed_db(tmp_path):
    """confidence_min_prozent = kleinster gueltiger Confidence-Score.

    Fuenf Stuecke mit Confidence 30/55/70/85/95 - min = 30. Spiegelt
    das wert_min_chf / gewicht_min_g-Randlage-Konzept auf die
    Confidence-Achse (Untergrenze der zentralen-Tendenz-Achse
    durchschnitt_/median_confidence_prozent).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_min.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 30),
            ("OBJ_0002", 55),
            ("OBJ_0003", 70),
            ("OBJ_0004", 85),
            ("OBJ_0005", 95),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_min_prozent == 30
    assert st.as_dict()["confidence_min_prozent"] == 30
    c.close()


def test_confidence_min_prozent_leer(tmp_path):
    """Ohne Confidence-Pflege bleibt der Min-Wert None (dataclass-Default).

    Spiegelt die median_/durchschnitt_confidence_prozent-None-Konvention:
    score-basierte Groessen mit None statt 0 im Undefined-Fall, damit
    Downstream-Konsumenten den Undefined-Zustand transparent unterscheiden
    koennen (kein Kollaps auf 0, was faelschlich "perfekte Unsicherheit"
    suggerieren wuerde).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_min_leer.sqlite3")
    st = compute_statistics(c)
    assert st.confidence_min_prozent is None
    assert st.as_dict()["confidence_min_prozent"] is None
    c.close()


def test_confidence_min_prozent_ignoriert_out_of_range(tmp_path):
    """Out-of-Range-Werte (<0 / >100) zaehlen nicht ins Minimum.

    Spiegelt die median_/durchschnitt_confidence_prozent- und
    objekte_mit_confidence-Konvention: die Extrem-Kennzahl darf nicht
    durch einen Integrity-Verstoss verzerrt werden. Ein Eintrag mit
    Confidence -50 sollte nicht als "kleinster Confidence-Wert der
    Sammlung" gezaehlt werden - das Integrity-Modul meldet solche
    Datensaetze separat.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_min_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", -50),   # out-of-range, ignoriert
            ("OBJ_0002", 40),
            ("OBJ_0003", 200),   # out-of-range, ignoriert
            ("OBJ_0004", 90),
            ("OBJ_0005", None),  # NULL, ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Kleinster gueltiger Wert: 40 (nicht -50)
    assert st.confidence_min_prozent == 40
    c.close()


def test_confidence_min_prozent_einzelobjekt(tmp_path):
    """Bei genau einem Confidence-Eintrag ist Min == Median == Durchschnitt.

    Kern-Konsequenz der Extremum-Definition ueber die sortierte
    conf_werte-Liste: bei n=1 kollabieren alle drei zentralen Kennzahlen
    (min/median/durchschnitt) auf denselben Wert.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_min_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 77), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_min_prozent == 77
    assert st.median_confidence_prozent == 77.0
    assert st.durchschnitt_confidence_prozent == 77.0
    c.close()


def test_confidence_max_prozent_aus_seed_db(tmp_path):
    """confidence_max_prozent = groesster gueltiger Confidence-Score.

    Fuenf Stuecke mit Confidence 30/55/70/85/95 - max = 95. Spiegelt
    das wert_max_chf / gewicht_max_g-Randlage-Konzept auf die
    Confidence-Achse (Obergrenze der zentralen-Tendenz-Achse
    durchschnitt_/median_confidence_prozent) und ergaenzt damit das
    Extremum-Paar (min + max) symmetrisch zur Wert-/Gewicht-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_max.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 30),
            ("OBJ_0002", 55),
            ("OBJ_0003", 70),
            ("OBJ_0004", 85),
            ("OBJ_0005", 95),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_max_prozent == 95
    assert st.confidence_min_prozent == 30
    assert st.as_dict()["confidence_max_prozent"] == 95
    c.close()


def test_confidence_max_prozent_leer(tmp_path):
    """Ohne Confidence-Pflege bleibt der Max-Wert None (dataclass-Default).

    Spiegelt die confidence_min_prozent- und median_/durchschnitt_
    confidence_prozent-None-Konvention: score-basierte Groessen mit None
    statt 0 im Undefined-Fall - im Gegensatz zu wert_max_chf /
    gewicht_max_g (Waehrungs-/Massen-Groessen mit 0.0 als Default), weil
    Confidence "unbewertet" nicht mit "0 % Sicherheit" verwechselt
    werden darf.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_max_leer.sqlite3")
    st = compute_statistics(c)
    assert st.confidence_max_prozent is None
    assert st.as_dict()["confidence_max_prozent"] is None
    c.close()


def test_confidence_max_prozent_ignoriert_out_of_range(tmp_path):
    """Out-of-Range-Werte (<0 / >100) zaehlen nicht ins Maximum.

    Spiegelt die confidence_min_prozent- und median_confidence_prozent-
    Konvention: die Extrem-Kennzahl darf nicht durch einen Integrity-
    Verstoss (z.B. Confidence 200) verzerrt werden. Der groesste gueltige
    Wert unter 90 und 200 ist 90, nicht 200 - das Integrity-Modul meldet
    den 200er-Datensatz separat.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_max_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 40),
            ("OBJ_0002", 90),
            ("OBJ_0003", 200),   # out-of-range, ignoriert
            ("OBJ_0004", -50),   # out-of-range, ignoriert
            ("OBJ_0005", None),  # NULL, ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    # Groesster gueltiger Wert: 90 (nicht 200)
    assert st.confidence_max_prozent == 90
    c.close()


def test_confidence_max_prozent_bei_einem_eintrag_gleich_min(tmp_path):
    """Bei genau einem Confidence-Eintrag ist Min == Max == Median == Ø.

    Extremum-Kollaps analog zu wert_min_chf / wert_max_chf beim einzigen
    Datenpunkt: alle vier Kennzahlen (min/max/median/durchschnitt)
    zeigen denselben Einzelwert.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_max_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 77), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_max_prozent == 77
    assert st.confidence_min_prozent == 77
    assert st.median_confidence_prozent == 77.0
    assert st.durchschnitt_confidence_prozent == 77.0
    c.close()


def test_confidence_standardabweichung_prozent_aus_bekannten_werten(tmp_path):
    """σ Confidence = Populations-Standardabweichung ueber gueltige Scores.

    Fuenf Confidence-Werte 20/40/60/80/100 mit Ø 60 - die Abweichungen zum
    Mittel sind ±40, ±20, 0 (0, 20, 20, 40, 40 in Absolut), Varianz
    (1600+400+0+400+1600)/5 = 800, sigma = sqrt(800) ≈ 28.2843. Spiegelt
    die wert_standardabweichung_chf / gewicht_standardabweichung_g /
    mohs_kollektion_standardabweichung / dichte_kollektion_standardabweichung-
    Semantik (Populations-Variante mit Divisor n).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_sigma.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 20),
            ("OBJ_0002", 40),
            ("OBJ_0003", 60),
            ("OBJ_0004", 80),
            ("OBJ_0005", 100),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.durchschnitt_confidence_prozent == 60.0
    assert st.confidence_standardabweichung_prozent == pytest.approx(
        800.0 ** 0.5, abs=1e-9)
    # as_dict rundet auf 2 Nachkommastellen (spiegelt wert/gewicht-sigma-
    # Serialisierung).
    assert st.as_dict()["confidence_standardabweichung_prozent"] == round(
        800.0 ** 0.5, 2)
    c.close()


def test_confidence_standardabweichung_prozent_leer(tmp_path):
    """Ohne Confidence-Pflege bleibt sigma None (dataclass-Default).

    Spiegelt die durchschnitt_/median_/confidence_min_/confidence_max_-
    prozent-None-Konvention: score-basierte Groessen mit None statt 0 im
    Undefined-Fall, damit Downstream-Konsumenten den Undefined-Zustand
    transparent unterscheiden koennen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_sigma_leer.sqlite3")
    st = compute_statistics(c)
    assert st.confidence_standardabweichung_prozent is None
    assert st.as_dict()["confidence_standardabweichung_prozent"] is None
    c.close()


def test_confidence_standardabweichung_prozent_ignoriert_out_of_range(tmp_path):
    """Out-of-Range-Werte (<0 / >100) zaehlen nicht in die Streuung.

    Spiegelt die confidence_min_/max_/median_prozent-Konvention: die
    Populations-Streuung darf nicht durch einen Integrity-Verstoss (z.B.
    Confidence 200) verzerrt werden. Der reine 60/70/80-Cluster ergibt
    lokal Ø 70 und sigma sqrt(((60-70)^2+(70-70)^2+(80-70)^2)/3) =
    sqrt(200/3). Der SQL-basierte durchschnitt_confidence_prozent nimmt
    dagegen alle non-NULL-Werte (72.0), aber sigma verwendet den strikten
    lokalen Mittelwert - andernfalls waere die (x-mean)^2-Summe ueber
    einer Range-gefilterten Menge mit einem Mittelwert einer nicht-
    gefilterten Menge inkonsistent (dokumentiert im stats.py-Kommentar).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_sigma_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 60),
            ("OBJ_0002", 70),
            ("OBJ_0003", 80),
            ("OBJ_0004", 200),   # out-of-range, ignoriert
            ("OBJ_0005", -50),   # out-of-range, ignoriert
            ("OBJ_0006", None),  # NULL, ignoriert
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_standardabweichung_prozent == pytest.approx(
        (200.0 / 3.0) ** 0.5, abs=1e-9)
    c.close()


def test_confidence_standardabweichung_prozent_bei_einem_eintrag_ist_null(tmp_path):
    """Bei genau einem Confidence-Eintrag kollabiert sigma auf 0.0.

    Single-Point-Kollaps analog zu wert_/gewicht_/mohs_/dichte_
    standardabweichung: ohne Dispersion (nur ein Datenpunkt) ist die
    Streuung mathematisch 0.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_sigma_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 77), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_standardabweichung_prozent == 0.0
    c.close()


def test_confidence_standardabweichung_prozent_bei_uniformen_werten_ist_null(tmp_path):
    """Bei uniformen Confidence-Scores (alle gleich) kollabiert sigma auf 0.0.

    Uniform-Kollaps analog zu den vier anderen sigma-Groessen: alle
    Abweichungen zum Mittel sind 0, damit ist die Varianz und sigma 0.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_sigma_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 85),
            ("OBJ_0002", 85),
            ("OBJ_0003", 85),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.durchschnitt_confidence_prozent == 85.0
    assert st.confidence_standardabweichung_prozent == 0.0
    c.close()


def test_confidence_variationskoeffizient_aus_bekannten_werten(tmp_path):
    """CV Confidence = sigma / mean * 100 in Prozent auf der Sicherheits-Achse.

    Spiegelt test_wert_variationskoeffizient_aus_seed_db /
    test_gewicht_variationskoeffizient_aus_seed_db /
    test_mohs_variationskoeffizient_aus_seed_db /
    test_dichte_variationskoeffizient_aus_seed_db auf die Confidence-Achse.
    Fuenf Confidence-Werte 20/40/60/80/100 → Ø=60, Varianz=800, sigma=
    sqrt(800) ≈ 28.28. CV = 28.28 / 60 * 100 ≈ 47.14 %. Reuse der
    bekannten Verteilung aus dem sigma-Test, damit die CV-Rechnung direkt
    auf denselben Werten nachvollziehbar bleibt.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_cv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 20),
            ("OBJ_0002", 40),
            ("OBJ_0003", 60),
            ("OBJ_0004", 80),
            ("OBJ_0005", 100),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    expected_cv = (800.0 ** 0.5) / 60.0 * 100.0
    assert st.confidence_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-6)
    # as_dict rundet auf 2 Nachkommastellen (spiegelt wert/gewicht/mohs/
    # dichte-CV-Serialisierung).
    assert st.as_dict()["confidence_variationskoeffizient_prozent"] == round(
        expected_cv, 2)
    c.close()


def test_confidence_variationskoeffizient_leer(tmp_path):
    """Ohne Confidence-Pflege bleibt der CV None (dataclass-Default).

    Spiegelt die confidence_standardabweichung_/durchschnitt_/median_/min_/
    max_prozent-None-Konvention: score-basierte Groessen mit None statt 0.0
    im Undefined-Fall, damit Downstream-Konsumenten den Undefined-Zustand
    transparent unterscheiden koennen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_cv_leer.sqlite3")
    st = compute_statistics(c)
    assert st.confidence_variationskoeffizient_prozent is None
    assert st.as_dict()["confidence_variationskoeffizient_prozent"] is None
    c.close()


def test_confidence_variationskoeffizient_bei_uniformen_werten_ist_null(tmp_path):
    """Bei uniformen Confidence-Scores kollabiert CV auf 0.0 (sigma=0).

    Spiegelt die Uniform-Kollaps-Semantik der CV-Wert / CV-Gewicht /
    CV-Mohs / CV-Dichte: alle Abweichungen zum Mittel sind 0, damit ist
    sigma 0 und CV = 0 / mean * 100 = 0.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_cv_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 85), ("OBJ_0002", 85), ("OBJ_0003", 85)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_variationskoeffizient_prozent == pytest.approx(
        0.0, abs=1e-9)
    c.close()


def test_confidence_variationskoeffizient_bei_einem_eintrag_ist_null(tmp_path):
    """Bei genau einem Confidence-Eintrag ist sigma 0.0 und damit CV 0.0.

    Single-Point-Kollaps analog CV Wert / CV Gewicht / CV Mohs / CV Dichte.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_cv_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 77), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_variationskoeffizient_prozent == pytest.approx(
        0.0, abs=1e-9)
    c.close()


def test_confidence_variationskoeffizient_reagiert_auf_ausreisser(tmp_path):
    """CV Confidence reagiert auf Bestimmungs-Sicherheits-Ausreisser.

    Neun Referenz-Bestimmungen (Confidence 90) + ein tentativer
    Feldbestimmung-Ausreisser (Confidence 20). Ø = (9*90 + 20)/10 = 83.
    Varianz = (9*(90-83)^2 + (20-83)^2)/10 = (9*49 + 3969)/10 =
    (441 + 3969)/10 = 441 → sigma = sqrt(441) = 21. CV = 21 / 83 * 100
    ≈ 25.30 %. Zeigt die Bestimmungs-Sicherheits-Heterogenitaet an einer
    skalen-unabhaengigen Kennzahl direkt vergleichbar mit CV Wert / CV
    Gewicht / CV Mohs / CV Dichte.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_cv_ausreisser.sqlite3")
    rows = [(f"OBJ_{i:04d}", 90) for i in range(1, 10)]
    rows.append(("OBJ_0010", 20))
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        rows,
    )
    c.commit()
    st = compute_statistics(c)
    expected_cv = 21.0 / 83.0 * 100.0
    assert st.confidence_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-6)
    c.close()


def test_confidence_variationskoeffizient_ignoriert_out_of_range(tmp_path):
    """Out-of-Range-Confidence-Werte (<0 / >100) fliessen weder in mean noch sigma.

    Spiegelt die confidence_standardabweichung_prozent-Konvention (strikter
    lokaler Mittelwert ueber BETWEEN 0 AND 100). Der reine 60/70/80-Cluster
    ergibt lokal Ø=70, Varianz=200/3, sigma=sqrt(200/3), CV=sigma/70*100.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "conf_cv_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 60),
            ("OBJ_0002", 70),
            ("OBJ_0003", 80),
            ("OBJ_0004", 200),
            ("OBJ_0005", -50),
            ("OBJ_0006", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    expected_sigma = (200.0 / 3.0) ** 0.5
    expected_cv = expected_sigma / 70.0 * 100.0
    assert st.confidence_variationskoeffizient_prozent == pytest.approx(
        expected_cv, abs=1e-9)
    c.close()


def test_wert_spanweite_aus_seed_db(tmp_path):
    """Spannweite = max - min in Original-Einheiten CHF.

    Vier Werte 100/200/300/400 -> min=100, max=400, Spannweite=300 CHF.
    Spiegelt test_wert_variationskoeffizient_aus_seed_db (gleicher Seed)
    auf die Original-Einheiten-Bandbreiten-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_span.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [
            ("OBJ_0001", 100.0),
            ("OBJ_0002", 200.0),
            ("OBJ_0003", 300.0),
            ("OBJ_0004", 400.0),
            ("OBJ_0005", None),
            ("OBJ_0006", 0.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_min_chf == 100.0
    assert st.wert_max_chf == 400.0
    assert st.wert_spanweite_chf == pytest.approx(300.0, abs=1e-9)
    d = st.as_dict()
    assert d["wert_spanweite_chf"] == pytest.approx(300.0, abs=1e-9)
    c.close()


def test_wert_spanweite_leer(tmp_path):
    """Ohne Wert-Pflege bleibt die Spannweite 0.0 (dataclass-Default).

    Spiegelt die uebrigen Wert-Kennzahlen min/max/median/durchschnitt/
    sigma = 0.0 bei leerer DB - anders als CV, das None bleibt: max-min
    ist bei leerer DB semantisch 0.0 (leere Bandbreite = keine Spanne),
    waehrend CV mathematisch undefined ist (Division durch mean = 0).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_span_leer.sqlite3")
    st = compute_statistics(c)
    assert st.wert_spanweite_chf == 0.0
    d = st.as_dict()
    assert d["wert_spanweite_chf"] == 0.0
    c.close()


def test_wert_spanweite_einzelobjekt(tmp_path):
    """Bei einem einzelnen Wert-Eintrag kollabiert die Spannweite auf 0.0.

    min == max = Einzelwert selbst -> Spannweite = 0 CHF. Spiegelt die
    sigma-Uniform-Kollaps-Semantik: nur ein Datenpunkt hat keine Streuung
    und keine Bandbreite.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_span_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_0001", 500.0), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_wert == 1
    assert st.wert_spanweite_chf == 0.0
    c.close()


def test_wert_spanweite_uniform(tmp_path):
    """Bei identischen Werten ist die Spannweite 0.0 (voellige Homogenitaet).

    Reine Feldspat-Sammlung ohne Preisdispersion: fuenf Stuecke CHF 50 ->
    min == max = 50 -> Spannweite = 0 CHF. Spiegelt die sigma-/CV-
    Uniform-Kollaps-Semantik.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_span_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [("OBJ_%04d" % i, 50.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_spanweite_chf == 0.0
    c.close()


def test_wert_spanweite_reagiert_auf_ausreisser(tmp_path):
    """Die Spannweite reagiert auf einzelne Extremwerte, nicht auf die
    Dichte dazwischen.

    Zehn Stuecke CHF 50 daneben ein einzelner Bergkristall CHF 5000:
    min=50, max=5000, Spannweite=4950 - trotz kleinem sigma (mean ~500,
    sigma ~1500). Kernunterschied zur Standardabweichung: sigma reagiert
    auf die Verteilungsform, die Spannweite auf die Extremwerte.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_span_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 50.0) for i in range(1, 11)]
    rows.append(("OBJ_0011", 5000.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        rows,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_min_chf == 50.0
    assert st.wert_max_chf == 5000.0
    assert st.wert_spanweite_chf == pytest.approx(4950.0, abs=1e-9)
    c.close()


def test_wert_spanweite_konsistent_mit_min_max(tmp_path):
    """Invariante: spanweite == max - min immer, exakt (float-Subtraktion).

    Spiegelt die "reuse der bereits berechneten min/max"-Konvention -
    die Spannweite ist definitorisch max - min und muss numerisch
    konsistent sein, damit Dashboard-/Report-Konsumenten sich auf die
    Identitaet verlassen koennen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "w_span_konsistent.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Wert_CHF_roh) VALUES (?, ?)",
        [
            ("OBJ_0001", 12.34),
            ("OBJ_0002", 567.89),
            ("OBJ_0003", 90.12),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.wert_spanweite_chf == st.wert_max_chf - st.wert_min_chf
    c.close()


def test_gewicht_spanweite_aus_seed_db(tmp_path):
    """gewicht_spanweite_g = gewicht_max_g - gewicht_min_g in Gramm.

    Vier Gewichte 10/20/30/40 -> min=10, max=40, Spannweite=30 g.
    Spiegelt test_wert_spanweite_aus_seed_db (gleicher Aufbau) auf die
    Massen-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_span.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [
            ("OBJ_0001", 10.0),
            ("OBJ_0002", 20.0),
            ("OBJ_0003", 30.0),
            ("OBJ_0004", 40.0),
            ("OBJ_0005", None),
            ("OBJ_0006", 0.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_min_g == 10.0
    assert st.gewicht_max_g == 40.0
    assert st.gewicht_spanweite_g == pytest.approx(30.0, abs=1e-9)
    d = st.as_dict()
    assert d["gewicht_spanweite_g"] == pytest.approx(30.0, abs=1e-9)
    c.close()


def test_gewicht_spanweite_leer(tmp_path):
    """Ohne Gewicht-Pflege bleibt die Spannweite 0.0 (dataclass-Default).

    Spiegelt test_wert_spanweite_leer und die uebrigen Gewicht-Kennzahlen
    (min/max/median/durchschnitt/sigma) = 0.0 bei leerer DB.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_span_leer.sqlite3")
    st = compute_statistics(c)
    assert st.gewicht_spanweite_g == 0.0
    d = st.as_dict()
    assert d["gewicht_spanweite_g"] == 0.0
    c.close()


def test_gewicht_spanweite_einzelobjekt(tmp_path):
    """Bei einem einzelnen Gewicht-Eintrag kollabiert die Spannweite auf 0.0.

    min == max = Einzelgewicht -> Spannweite = 0 g. Spiegelt
    test_wert_spanweite_einzelobjekt und die sigma-Kollaps-Konvention.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_span_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_0001", 250.0), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_gewicht == 1
    assert st.gewicht_spanweite_g == 0.0
    c.close()


def test_gewicht_spanweite_uniform(tmp_path):
    """Bei identischen Gewichten ist die Spannweite 0.0 (voellige Homogenitaet).

    Reine Mineralkorn-Serie mit exakt 5 g pro Korn: min == max = 5 ->
    Spannweite = 0 g. Spiegelt test_wert_spanweite_uniform und die
    Gewicht-sigma-/CV-Uniform-Kollaps-Semantik.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_span_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [("OBJ_%04d" % i, 5.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_spanweite_g == 0.0
    c.close()


def test_gewicht_spanweite_reagiert_auf_ausreisser(tmp_path):
    """Spannweite reagiert auf Extremwerte, nicht auf die Dichte dazwischen.

    Zehn Mineralkoerner a 5 g plus ein Handstueck 5000 g: min=5, max=5000,
    Spannweite=4995 - trotz kleinem sigma. Spiegelt
    test_wert_spanweite_reagiert_auf_ausreisser auf die Massen-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_span_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 5.0) for i in range(1, 11)]
    rows.append(("OBJ_0011", 5000.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        rows,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_min_g == 5.0
    assert st.gewicht_max_g == 5000.0
    assert st.gewicht_spanweite_g == pytest.approx(4995.0, abs=1e-9)
    c.close()


def test_gewicht_spanweite_konsistent_mit_min_max(tmp_path):
    """Invariante: gewicht_spanweite_g == gewicht_max_g - gewicht_min_g.

    Spiegelt test_wert_spanweite_konsistent_mit_min_max: die Spannweite ist
    definitorisch max - min und muss numerisch konsistent bleiben, damit
    Dashboard-/Report-Konsumenten sich auf die Identitaet verlassen koennen.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "g_span_konsistent.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Gewicht_g) VALUES (?, ?)",
        [
            ("OBJ_0001", 1.23),
            ("OBJ_0002", 456.78),
            ("OBJ_0003", 9.01),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.gewicht_spanweite_g == st.gewicht_max_g - st.gewicht_min_g
    c.close()


def test_mohs_spanweite_aus_seed_db(tmp_path):
    """mohs_kollektion_spanweite = mohs_kollektion_max - mohs_kollektion_min.

    Vier Mohs-Mittelpunkte 3.0/4.0/5.0/6.0 -> min=3.0, max=6.0,
    Spannweite=3.0. Spiegelt test_gewicht_spanweite_aus_seed_db (gleicher
    Aufbau) auf die Haerte-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_span.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 3.0, 3.0),
            ("OBJ_0002", 4.0, 4.0),
            ("OBJ_0003", 5.0, 5.0),
            ("OBJ_0004", 6.0, 6.0),
            ("OBJ_0005", None, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_min == 3.0
    assert st.mohs_kollektion_max == 6.0
    assert st.mohs_kollektion_spanweite == pytest.approx(3.0, abs=1e-9)
    d = st.as_dict()
    assert d["mohs_kollektion_spanweite"] == pytest.approx(3.0, abs=1e-9)
    c.close()


def test_mohs_spanweite_leer(tmp_path):
    """Ohne Mohs-Pflege bleibt die Spannweite None (dataclass-Default).

    Anders als wert_/gewicht_spanweite (die auf 0.0 kollabieren, weil deren
    min/max ebenfalls 0.0 sind), spiegelt mohs_kollektion_spanweite die
    None-Konvention der uebrigen Mohs-Bereichsgroessen (min/max/median/
    durchschnitt/sigma/CV = None bei leerer DB) - Bereichsgroessen bleiben
    im Undefined-Fall None statt 0.0.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_span_leer.sqlite3")
    st = compute_statistics(c)
    assert st.mohs_kollektion_spanweite is None
    d = st.as_dict()
    assert d["mohs_kollektion_spanweite"] is None
    c.close()


def test_mohs_spanweite_einzelobjekt(tmp_path):
    """Bei einem einzelnen Mohs-Eintrag kollabiert die Spannweite auf 0.0.

    min == max = Einzel-Mohs -> Spannweite = 0.0. Spiegelt
    test_gewicht_spanweite_einzelobjekt und die sigma-Kollaps-Konvention.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_span_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", 7.0, 7.0), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_mohs == 1
    assert st.mohs_kollektion_spanweite == 0.0
    c.close()


def test_mohs_spanweite_uniform(tmp_path):
    """Bei identischen Mohs-Punkten ist die Spannweite 0.0 (Homogenitaet).

    Reine Quarz-Sammlung mit fuenf Stuecken Mohs 7.0 -> min == max = 7.0 ->
    Spannweite = 0.0. Spiegelt test_gewicht_spanweite_uniform und die
    Mohs-sigma-/CV-Uniform-Kollaps-Semantik.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_span_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [("OBJ_%04d" % i, 7.0, 7.0) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_spanweite == 0.0
    c.close()


def test_mohs_spanweite_reagiert_auf_ausreisser(tmp_path):
    """Spannweite reagiert auf Extremwerte, nicht auf die Dichte dazwischen.

    Neun Calcit-Stuecke (Mohs 3.0) + ein Diamant (Mohs 10.0): min=3.0,
    max=10.0, Spannweite=7.0 - trotz kleinem sigma. Spiegelt
    test_gewicht_spanweite_reagiert_auf_ausreisser auf die Haerte-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_span_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 3.0, 3.0) for i in range(1, 10)]
    rows.append(("OBJ_0010", 10.0, 10.0))
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)", rows,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_min == 3.0
    assert st.mohs_kollektion_max == 10.0
    assert st.mohs_kollektion_spanweite == pytest.approx(7.0, abs=1e-9)
    c.close()


def test_mohs_spanweite_konsistent_mit_min_max(tmp_path):
    """Invariante: mohs_kollektion_spanweite == max - min immer.

    Spiegelt test_gewicht_spanweite_konsistent_mit_min_max: die Spannweite
    ist definitorisch max - min und muss numerisch konsistent bleiben,
    damit Dashboard-/Report-Konsumenten sich auf die Identitaet verlassen
    koennen. Reuse-Pfad greift die bereits gesetzten mohs_kollektion_max
    und mohs_kollektion_min ab.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "m_span_konsistent.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 1.5, 2.5),
            ("OBJ_0002", 6.0, 7.0),
            ("OBJ_0003", 8.5, 9.0),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.mohs_kollektion_spanweite == (
        st.mohs_kollektion_max - st.mohs_kollektion_min)
    c.close()


def test_dichte_spanweite_aus_seed_db(tmp_path):
    """dichte_kollektion_spanweite = dichte_kollektion_max - _min in g/cm3.

    Vier Dichte-Mittelpunkte 2.0/3.0/4.0/5.0 -> min=2.0, max=5.0,
    Spannweite=3.0 g/cm3. Spiegelt test_mohs_spanweite_aus_seed_db auf
    die Dichte-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_span.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 2.0, 2.0),
            ("OBJ_0002", 3.0, 3.0),
            ("OBJ_0003", 4.0, 4.0),
            ("OBJ_0004", 5.0, 5.0),
            ("OBJ_0005", None, None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_min == 2.0
    assert st.dichte_kollektion_max == 5.0
    assert st.dichte_kollektion_spanweite == pytest.approx(3.0, abs=1e-9)
    d = st.as_dict()
    assert d["dichte_kollektion_spanweite"] == pytest.approx(3.0, abs=1e-9)
    c.close()


def test_dichte_spanweite_leer(tmp_path):
    """Ohne Dichte-Pflege bleibt die Spannweite None (dataclass-Default).

    Spiegelt mohs_kollektion_spanweite: Bereichsgroessen bleiben im
    Undefined-Fall None statt 0.0 (anders als wert_/gewicht_spanweite die
    0.0 liefern - Konvention der Dichte-Bereichsgroessen).
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_span_leer.sqlite3")
    st = compute_statistics(c)
    assert st.dichte_kollektion_spanweite is None
    d = st.as_dict()
    assert d["dichte_kollektion_spanweite"] is None
    c.close()


def test_dichte_spanweite_einzelobjekt(tmp_path):
    """Bei einem einzelnen Dichte-Eintrag kollabiert die Spannweite auf 0.0.

    min == max = Einzel-Dichte -> Spannweite = 0.0. Spiegelt
    test_mohs_spanweite_einzelobjekt und die sigma-Kollaps-Konvention.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_span_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_0001", 2.65, 2.65), ("OBJ_0002", None, None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_dichte == 1
    assert st.dichte_kollektion_spanweite == 0.0
    c.close()


def test_dichte_spanweite_uniform(tmp_path):
    """Bei identischen Dichten ist die Spannweite 0.0 (Homogenitaet).

    Reine Quarz-Familie mit fuenf Stuecken 2.65 g/cm3 -> min == max = 2.65 ->
    Spannweite = 0.0. Spiegelt test_mohs_spanweite_uniform und die
    Dichte-sigma-/CV-Uniform-Kollaps-Semantik.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_span_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [("OBJ_%04d" % i, 2.65, 2.65) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_spanweite == 0.0
    c.close()


def test_dichte_spanweite_reagiert_auf_ausreisser(tmp_path):
    """Spannweite reagiert auf Extremwerte, nicht auf die Dichte dazwischen.

    Neun Quarz-Stuecke (2.65 g/cm3) + ein Galenit-Stueck (7.5 g/cm3):
    min=2.65, max=7.5, Spannweite=4.85 - trotz kleinem sigma. Spiegelt
    test_mohs_spanweite_reagiert_auf_ausreisser auf die Dichte-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_span_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 2.65, 2.65) for i in range(1, 10)]
    rows.append(("OBJ_0010", 7.5, 7.5))
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)", rows,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_min == 2.65
    assert st.dichte_kollektion_max == 7.5
    assert st.dichte_kollektion_spanweite == pytest.approx(4.85, abs=1e-9)
    c.close()


def test_dichte_spanweite_konsistent_mit_min_max(tmp_path):
    """Invariante: dichte_kollektion_spanweite == max - min immer.

    Spiegelt test_mohs_spanweite_konsistent_mit_min_max: die Spannweite
    ist definitorisch max - min und muss numerisch konsistent bleiben,
    damit Dashboard-/Report-Konsumenten sich auf die Identitaet verlassen
    koennen. Reuse-Pfad greift die bereits gesetzten dichte_kollektion_max
    und dichte_kollektion_min ab.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "d_span_konsistent.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Dichte_min_gcm3, Dichte_max_gcm3) "
        "VALUES (?, ?, ?)",
        [
            ("OBJ_0001", 1.05, 1.15),
            ("OBJ_0002", 2.55, 2.75),
            ("OBJ_0003", 7.45, 7.55),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.dichte_kollektion_spanweite == (
        st.dichte_kollektion_max - st.dichte_kollektion_min)
    c.close()


def test_confidence_spanweite_aus_seed_db(tmp_path):
    """confidence_spanweite_prozent = confidence_max - confidence_min.

    Vier Confidence 40/60/80/95 -> min=40, max=95, Spannweite=55.
    Spiegelt test_dichte_spanweite_aus_seed_db auf die Confidence-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "c_span.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 40),
            ("OBJ_0002", 60),
            ("OBJ_0003", 80),
            ("OBJ_0004", 95),
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_min_prozent == 40
    assert st.confidence_max_prozent == 95
    assert st.confidence_spanweite_prozent == 55
    d = st.as_dict()
    assert d["confidence_spanweite_prozent"] == 55
    c.close()


def test_confidence_spanweite_leer(tmp_path):
    """Ohne Confidence-Pflege bleibt die Spannweite None (dataclass-Default).

    Spiegelt mohs_/dichte_kollektion_spanweite: score-basierte Groessen
    bleiben im Undefined-Fall None statt 0 (anders als wert_/gewicht_
    spanweite die 0.0 liefern) - stellt Symmetrie zu confidence_min_/max_/
    sigma/CV her.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "c_span_leer.sqlite3")
    st = compute_statistics(c)
    assert st.confidence_spanweite_prozent is None
    d = st.as_dict()
    assert d["confidence_spanweite_prozent"] is None
    c.close()


def test_confidence_spanweite_einzelobjekt(tmp_path):
    """Bei einem einzelnen Confidence-Eintrag kollabiert die Spannweite auf 0.

    min == max = Einzel-Confidence -> Spannweite = 0. Spiegelt
    test_dichte_spanweite_einzelobjekt und die sigma-Kollaps-Konvention.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "c_span_1.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_0001", 75), ("OBJ_0002", None)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.objekte_mit_confidence == 1
    assert st.confidence_spanweite_prozent == 0
    c.close()


def test_confidence_spanweite_uniform(tmp_path):
    """Bei identischen Confidence-Werten ist die Spannweite 0 (Homogenitaet).

    Fuenf Objekte mit Confidence 80 -> min == max = 80 -> Spannweite = 0.
    Spiegelt test_dichte_spanweite_uniform und die confidence-sigma-/CV-
    Uniform-Kollaps-Semantik.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "c_span_uniform.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [("OBJ_%04d" % i, 80) for i in range(1, 6)],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_spanweite_prozent == 0
    c.close()


def test_confidence_spanweite_reagiert_auf_ausreisser(tmp_path):
    """Spannweite reagiert auf Extremwerte, nicht auf die Dichte dazwischen.

    Neun Sichere-KI-Bestimmungen (Confidence 90) + eine unsichere (20):
    min=20, max=90, Spannweite=70 - trotz kleinem sigma. Spiegelt
    test_dichte_spanweite_reagiert_auf_ausreisser auf die Confidence-Achse.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "c_span_ausreisser.sqlite3")
    rows = [("OBJ_%04d" % i, 90) for i in range(1, 10)]
    rows.append(("OBJ_0010", 20))
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        rows,
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_min_prozent == 20
    assert st.confidence_max_prozent == 90
    assert st.confidence_spanweite_prozent == 70
    c.close()


def test_confidence_spanweite_ignoriert_out_of_range(tmp_path):
    """Out-of-Range-Confidence (<0 / >100) fliesst nicht in die Spannweite.

    Spiegelt die confidence_min_/max_/sigma/CV-Konvention: die Spannweite
    darf nicht durch einen Integrity-Verstoss verzerrt werden (ein
    Datensatz mit Confidence -50 wuerde die Spannweite kuenstlich auf
    140 aufblasen, ein Confidence 200 auf 190). Das Integrity-Modul meldet
    solche Datensaetze separat; die Spannweite bleibt strikt auf 0..100.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "c_span_oor.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", -50),   # out-of-range, ignoriert
            ("OBJ_0002", 40),
            ("OBJ_0003", 90),
            ("OBJ_0004", 200),   # out-of-range, ignoriert
            ("OBJ_0005", None),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_min_prozent == 40
    assert st.confidence_max_prozent == 90
    assert st.confidence_spanweite_prozent == 50
    c.close()


def test_confidence_spanweite_konsistent_mit_min_max(tmp_path):
    """Invariante: confidence_spanweite_prozent == max - min immer.

    Spiegelt test_dichte_spanweite_konsistent_mit_min_max: die Spannweite
    ist definitorisch max - min und muss numerisch konsistent bleiben,
    damit Dashboard-/Report-Konsumenten sich auf die Identitaet verlassen
    koennen. Reuse-Pfad greift die bereits gesetzten confidence_max_prozent
    und confidence_min_prozent ab.
    """
    from stonebook.db.database import open_db
    c = open_db(tmp_path / "c_span_konsistent.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent) VALUES (?, ?)",
        [
            ("OBJ_0001", 12),
            ("OBJ_0002", 47),
            ("OBJ_0003", 78),
            ("OBJ_0004", 99),
        ],
    )
    c.commit()
    st = compute_statistics(c)
    assert st.confidence_spanweite_prozent == (
        st.confidence_max_prozent - st.confidence_min_prozent)
    c.close()
