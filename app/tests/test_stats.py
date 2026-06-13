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
