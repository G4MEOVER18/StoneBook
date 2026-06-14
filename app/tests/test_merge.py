"""merge_into_canonical: programmatisches Verschmelzen zweier Objekte."""
import pytest

from stonebook.db.database import open_db
from stonebook.db.merge import merge_into_canonical
from stonebook.db.repository import AliasRepo, ImageRepo, ObjectRepo


def _setup(tmp_path, db_name="m.sqlite3"):
    c = open_db(tmp_path / db_name)
    return c, ObjectRepo(c), ImageRepo(c), AliasRepo(c)


def test_merge_into_canonical_haengt_bilder_um(tmp_path):
    """Bilder des Members wandern auf den Kanon, herkunft_obj_id wird gesetzt."""
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001", Name="Kanon")
    objects.create("OBJ_0002", Name="Member")
    images.add("OBJ_0001", "Kamera", "a.jpg")
    images.add("OBJ_0002", "Mikroskop", "b.jpg")
    images.add("OBJ_0002", "UV365", "c.jpg")

    merge_into_canonical(objects, images, aliases, "OBJ_0002", "OBJ_0001")

    kanon_imgs = images.for_object("OBJ_0001")
    paths = {r["rel_path"] for r in kanon_imgs}
    assert paths == {"a.jpg", "b.jpg", "c.jpg"}
    # Umgehaengte Bilder erhalten herkunft_obj_id
    umgehaengt = [r for r in kanon_imgs if r["herkunft_obj_id"] == "OBJ_0002"]
    assert {r["rel_path"] for r in umgehaengt} == {"b.jpg", "c.jpg"}
    c.close()


def test_merge_into_canonical_traegt_alias_ein(tmp_path):
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001")
    objects.create("OBJ_0002")
    merge_into_canonical(objects, images, aliases, "OBJ_0002", "OBJ_0001",
                         quelle="manuell")
    assert aliases.canonical_for("OBJ_0002") == "OBJ_0001"
    # Quelle wird mitgespeichert
    row = c.execute(
        "SELECT merge_quelle FROM aliases WHERE alias_id=?", ("OBJ_0002",)
    ).fetchone()
    assert row["merge_quelle"] == "manuell"
    c.close()


def test_merge_into_canonical_loescht_member(tmp_path):
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001")
    objects.create("OBJ_0002")
    merge_into_canonical(objects, images, aliases, "OBJ_0002", "OBJ_0001")
    assert not objects.exists("OBJ_0002")
    assert objects.exists("OBJ_0001")
    c.close()


def test_merge_into_canonical_merged_leere_kanon_felder(tmp_path):
    """Leere Felder im Kanon werden durch Member-Werte gefuellt (keine Konflikte)."""
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001", Name="Kanon")  # nur Name
    objects.create("OBJ_0002", Mineral_Primaer="Quarz",
                   Farbe_beobachtet="weiss")
    conflicts = merge_into_canonical(objects, images, aliases,
                                     "OBJ_0002", "OBJ_0001")
    assert conflicts == []
    kanon = objects.get("OBJ_0001")
    assert kanon["Name"] == "Kanon"
    assert kanon["Mineral_Primaer"] == "Quarz"
    assert kanon["Farbe_beobachtet"] == "weiss"
    c.close()


def test_merge_into_canonical_meldet_konflikte_und_haelt_kanon(tmp_path):
    """Abweichende vorhandene Kanon-Werte bleiben erhalten und werden gemeldet."""
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001", Name="Kanon", Mineral_Primaer="Quarz")
    objects.create("OBJ_0002", Name="Member", Mineral_Primaer="Calcit",
                   Farbe_beobachtet="weiss")
    conflicts = merge_into_canonical(objects, images, aliases,
                                     "OBJ_0002", "OBJ_0001")
    assert set(conflicts) == {"Name", "Mineral_Primaer"}
    kanon = objects.get("OBJ_0001")
    assert kanon["Name"] == "Kanon"            # Kanon behalten
    assert kanon["Mineral_Primaer"] == "Quarz"  # Kanon behalten
    assert kanon["Farbe_beobachtet"] == "weiss"  # leeres Feld gefuellt
    c.close()


def test_merge_into_canonical_selbst_merge_raises(tmp_path):
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001")
    with pytest.raises(ValueError, match="Selbst-Merge"):
        merge_into_canonical(objects, images, aliases, "OBJ_0001", "OBJ_0001")
    c.close()


def test_merge_into_canonical_unbekannter_member_raises(tmp_path):
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001")
    with pytest.raises(ValueError, match="Member-Objekt"):
        merge_into_canonical(objects, images, aliases, "OBJ_9999", "OBJ_0001")
    c.close()


def test_merge_into_canonical_unbekannter_kanon_raises(tmp_path):
    c, objects, images, aliases = _setup(tmp_path)
    objects.create("OBJ_0001")
    with pytest.raises(ValueError, match="Kanon-Objekt"):
        merge_into_canonical(objects, images, aliases, "OBJ_0001", "OBJ_9999")
    # OBJ_0001 muss noch existieren (kein Halb-Merge)
    assert objects.exists("OBJ_0001")
    c.close()
