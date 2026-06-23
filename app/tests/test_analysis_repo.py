"""AnalysisRepo: KI-Analysen schreiben/lesen, einzeln loeschen, prunen."""
import json
import time

from stonebook.db.database import open_db
from stonebook.db.repository import AnalysisRepo, ObjectRepo


def _setup(tmp_path):
    c = open_db(tmp_path / "ki.sqlite3")
    ObjectRepo(c).create("OBJ_0001")
    ObjectRepo(c).create("OBJ_0002")
    return c, AnalysisRepo(c)


def _add_analyses(repo: AnalysisRepo, obj_id: str, n: int) -> list[int]:
    ids = []
    for i in range(n):
        ids.append(repo.add(obj_id, "claude-sonnet-4-6",
                            json.dumps({"i": i, "obj": obj_id})))
        # Sekundenaufloesung im Zeitstempel -> ohne Pause haetten alle die selbe
        # Zeit und 'neueste zuerst' waere durch die ID-Reihenfolge bestimmt
        time.sleep(0.01)
    return ids


def test_add_und_for_object(tmp_path):
    c, repo = _setup(tmp_path)
    a1 = repo.add("OBJ_0001", "claude-sonnet-4-6", '{"x": 1}')
    a2 = repo.add("OBJ_0001", "claude-opus-4-7", '{"x": 2}')
    rows = repo.for_object("OBJ_0001")
    assert [r["id"] for r in rows] == [a2, a1]   # neueste zuerst
    assert repo.count_for("OBJ_0001") == 2
    assert repo.count_for("OBJ_0002") == 0
    c.close()


def test_get_und_delete(tmp_path):
    c, repo = _setup(tmp_path)
    aid = repo.add("OBJ_0001", "claude-sonnet-4-6", '{"x": 1}')
    row = repo.get(aid)
    assert row is not None and row["obj_id"] == "OBJ_0001"
    assert repo.delete(aid) is True
    assert repo.get(aid) is None
    # zweites Loeschen ist no-op
    assert repo.delete(aid) is False
    c.close()


def test_prune_keep_neueste(tmp_path):
    c, repo = _setup(tmp_path)
    ids = _add_analyses(repo, "OBJ_0001", 5)
    # Die zwei juengsten sollen erhalten bleiben (= letzte beiden hinzugefuegt)
    geloescht = repo.prune("OBJ_0001", keep=2)
    assert geloescht == 3
    rows = repo.for_object("OBJ_0001")
    assert [r["id"] for r in rows] == [ids[-1], ids[-2]]
    c.close()


def test_prune_keep_null_loescht_alle(tmp_path):
    c, repo = _setup(tmp_path)
    _add_analyses(repo, "OBJ_0001", 3)
    geloescht = repo.prune("OBJ_0001", keep=0)
    assert geloescht == 3
    assert repo.count_for("OBJ_0001") == 0
    c.close()


def test_prune_keep_groesser_anzahl_no_op(tmp_path):
    c, repo = _setup(tmp_path)
    _add_analyses(repo, "OBJ_0001", 2)
    geloescht = repo.prune("OBJ_0001", keep=10)
    assert geloescht == 0
    assert repo.count_for("OBJ_0001") == 2
    c.close()


def test_prune_isoliert_pro_objekt(tmp_path):
    """prune('OBJ_A') beruehrt OBJ_B nicht."""
    c, repo = _setup(tmp_path)
    _add_analyses(repo, "OBJ_0001", 3)
    _add_analyses(repo, "OBJ_0002", 2)
    repo.prune("OBJ_0001", keep=1)
    assert repo.count_for("OBJ_0001") == 1
    assert repo.count_for("OBJ_0002") == 2
    c.close()


def test_prune_negativ_wirft_value_error(tmp_path):
    import pytest
    c, repo = _setup(tmp_path)
    with pytest.raises(ValueError):
        repo.prune("OBJ_0001", keep=-1)
    c.close()


def test_count_total(tmp_path):
    """count() spiegelt count_for ueber alle Objekte."""
    c, repo = _setup(tmp_path)
    assert repo.count() == 0
    _add_analyses(repo, "OBJ_0001", 3)
    _add_analyses(repo, "OBJ_0002", 2)
    assert repo.count() == 5
    assert repo.count_for("OBJ_0001") == 3
    assert repo.count_for("OBJ_0002") == 2
    c.close()


def test_prune_all_keep_neueste_je_objekt(tmp_path):
    """prune_all behaelt die N neuesten je Objekt - nicht global die N neuesten."""
    c, repo = _setup(tmp_path)
    ids_a = _add_analyses(repo, "OBJ_0001", 4)
    ids_b = _add_analyses(repo, "OBJ_0002", 3)
    geloescht = repo.prune_all(keep=2)
    # 4-2=2 fuer OBJ_0001, 3-2=1 fuer OBJ_0002 ⇒ 3 geloescht
    assert geloescht == 3
    rows_a = repo.for_object("OBJ_0001")
    rows_b = repo.for_object("OBJ_0002")
    assert [r["id"] for r in rows_a] == [ids_a[-1], ids_a[-2]]
    assert [r["id"] for r in rows_b] == [ids_b[-1], ids_b[-2]]
    c.close()


def test_prune_all_keep_null_loescht_alle(tmp_path):
    c, repo = _setup(tmp_path)
    _add_analyses(repo, "OBJ_0001", 2)
    _add_analyses(repo, "OBJ_0002", 3)
    geloescht = repo.prune_all(keep=0)
    assert geloescht == 5
    assert repo.count() == 0
    c.close()


def test_prune_all_keep_groesser_als_alle_no_op(tmp_path):
    c, repo = _setup(tmp_path)
    _add_analyses(repo, "OBJ_0001", 2)
    _add_analyses(repo, "OBJ_0002", 1)
    assert repo.prune_all(keep=10) == 0
    assert repo.count() == 3
    c.close()


def test_prune_all_negativ_wirft_value_error(tmp_path):
    import pytest
    c, repo = _setup(tmp_path)
    with pytest.raises(ValueError):
        repo.prune_all(keep=-1)
    c.close()
