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
