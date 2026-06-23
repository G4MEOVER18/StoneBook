"""AliasRepo: einzelnen Alias-Eintrag loeschen (Fehl-Merge-Korrektur)."""
from stonebook.db.database import open_db
from stonebook.db.repository import AliasRepo, ObjectRepo


def _setup(tmp_path):
    c = open_db(tmp_path / "alias.sqlite3")
    objects = ObjectRepo(c)
    objects.create("OBJ_0001")
    objects.create("OBJ_0010")
    return c, AliasRepo(c)


def test_delete_entfernt_eintrag(tmp_path):
    c, repo = _setup(tmp_path)
    repo.add("OBJ_0002", "OBJ_0001", quelle="manuell")
    assert repo.canonical_for("OBJ_0002") == "OBJ_0001"
    assert repo.delete("OBJ_0002") is True
    assert repo.canonical_for("OBJ_0002") is None
    assert repo.count() == 0
    c.close()


def test_delete_idempotent(tmp_path):
    c, repo = _setup(tmp_path)
    repo.add("OBJ_0002", "OBJ_0001", quelle="manuell")
    assert repo.delete("OBJ_0002") is True
    assert repo.delete("OBJ_0002") is False
    c.close()


def test_delete_beruehrt_andere_aliase_nicht(tmp_path):
    """Ein delete entfernt nur den genannten Eintrag, andere bleiben unangetastet."""
    c, repo = _setup(tmp_path)
    repo.add("OBJ_0002", "OBJ_0001", quelle="merge")
    repo.add("OBJ_0003", "OBJ_0001", quelle="merge")
    repo.add("OBJ_0011", "OBJ_0010", quelle="merge")
    repo.delete("OBJ_0002")
    assert repo.canonical_for("OBJ_0003") == "OBJ_0001"
    assert repo.canonical_for("OBJ_0011") == "OBJ_0010"
    assert repo.aliases_for("OBJ_0001") == ["OBJ_0003"]
    assert repo.count() == 2
    c.close()


def test_delete_unbekannte_id_no_op(tmp_path):
    c, repo = _setup(tmp_path)
    repo.add("OBJ_0002", "OBJ_0001", quelle="merge")
    assert repo.delete("OBJ_9999") is False
    assert repo.count() == 1
    c.close()
