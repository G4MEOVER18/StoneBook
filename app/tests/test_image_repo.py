"""ImageRepo: Lesen/Loeschen einzelner Bild-Eintraege."""
from stonebook.db.database import open_db
from stonebook.db.repository import ImageRepo, ObjectRepo


def _setup(tmp_path):
    c = open_db(tmp_path / "img.sqlite3")
    ObjectRepo(c).create("OBJ_0001")
    return c, ImageRepo(c)


def _add(repo: ImageRepo, obj_id: str, kategorie: str, rel_path: str) -> int:
    repo.add(obj_id, kategorie, rel_path, dateiname=rel_path.rsplit("/", 1)[-1])
    return repo.conn.execute(
        "SELECT id FROM images WHERE rel_path = ?", (rel_path,)).fetchone()[0]


def test_get_liefert_zeile(tmp_path):
    c, repo = _setup(tmp_path)
    iid = _add(repo, "OBJ_0001", "Kamera", "objects/OBJ_0001/a.jpg")
    row = repo.get(iid)
    assert row is not None
    assert row["obj_id"] == "OBJ_0001"
    assert row["kategorie"] == "Kamera"
    assert row["rel_path"] == "objects/OBJ_0001/a.jpg"
    c.close()


def test_get_unbekannte_id_ist_none(tmp_path):
    c, repo = _setup(tmp_path)
    assert repo.get(999) is None
    c.close()


def test_delete_entfernt_zeile(tmp_path):
    c, repo = _setup(tmp_path)
    iid = _add(repo, "OBJ_0001", "Kamera", "objects/OBJ_0001/a.jpg")
    assert repo.delete(iid) is True
    assert repo.get(iid) is None
    assert repo.count() == 0
    c.close()


def test_delete_idempotent(tmp_path):
    c, repo = _setup(tmp_path)
    iid = _add(repo, "OBJ_0001", "Kamera", "objects/OBJ_0001/a.jpg")
    assert repo.delete(iid) is True
    assert repo.delete(iid) is False
    c.close()


def test_delete_nur_eines_von_mehreren(tmp_path):
    """delete entfernt nur die Ziel-Zeile, nicht die uebrigen Bilder."""
    c, repo = _setup(tmp_path)
    a = _add(repo, "OBJ_0001", "Kamera", "objects/OBJ_0001/a.jpg")
    b = _add(repo, "OBJ_0001", "Kamera", "objects/OBJ_0001/b.jpg")
    repo.delete(a)
    assert repo.count() == 1
    assert repo.get(b) is not None
    c.close()
