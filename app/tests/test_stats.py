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
