import csv
from pathlib import Path

import pytest

from stonebook.db.database import connect, open_db
from stonebook.export.csv_export import export_csv, import_csv
from stonebook.export.docx_export import export_docx, export_docx_batch
from stonebook.export.json_export import export_json, import_json
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    c = connect(db_file)
    yield c
    c.close()


def test_csv_export(conn, tmp_path):
    out = tmp_path / "export.csv"
    n = export_csv(conn, out)
    assert n == 546
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 546
    o43 = next(r for r in rows if r["ID"] == "OBJ_0043")
    assert o43["Gewicht_g"] == "41.0"
    assert "Quarz" in o43["Mineral_Primaer"]


def test_csv_export_status_filter(conn, tmp_path):
    """status-Filter beschraenkt den CSV-Export auf einen Lebenszyklusstatus."""
    out = tmp_path / "aktiv.csv"
    n_aktiv = export_csv(conn, out, status="aktiv")
    assert 0 < n_aktiv < 546
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == n_aktiv
    assert all(r["status"] == "aktiv" for r in rows)


def test_csv_export_obj_ids_und_status_kombiniert(conn, tmp_path):
    out = tmp_path / "combo.csv"
    n = export_csv(conn, out, obj_ids=["OBJ_0043", "OBJ_0500"], status="aktiv")
    # OBJ_0500 ist platzhalter, faellt durch Status-Filter raus
    assert n == 1
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["ID"] for r in rows] == ["OBJ_0043"]


def test_json_export(conn, tmp_path):
    out = tmp_path / "export.json"
    counts = export_json(conn, out)
    assert counts == {"objects": 546, "images": 63, "aliases": 54}


def test_json_export_selektive_obj_ids(conn, tmp_path):
    """obj_ids-Filter exportiert nur die genannten Objekte; Bilder/Aliase werden mitgefiltert."""
    out = tmp_path / "sel.json"
    counts = export_json(conn, out, obj_ids=["OBJ_0001", "OBJ_0043"])
    assert counts["objects"] == 2
    # Bilder werden nach obj_id gefiltert
    import json as _json
    data = _json.loads(out.read_text(encoding="utf-8"))
    bilder_ids = {r["obj_id"] for r in data["images"]}
    assert bilder_ids <= {"OBJ_0001", "OBJ_0043"}
    # OBJ_0001 hat Aliase mit canonical_id=OBJ_0001 → muessen drin sein
    alias_canons = {r["canonical_id"] for r in data["aliases"]}
    assert alias_canons <= {"OBJ_0001", "OBJ_0043"}
    assert "OBJ_0001" in alias_canons


def test_json_export_obj_ids_leer(conn, tmp_path):
    out = tmp_path / "leer.json"
    counts = export_json(conn, out, obj_ids=[])
    assert counts == {"objects": 0, "images": 0, "aliases": 0}


def test_json_roundtrip(conn, tmp_path):
    dump = tmp_path / "export.json"
    export_json(conn, dump)
    fresh_db = tmp_path / "fresh.sqlite3"
    fresh = open_db(fresh_db)
    counts = import_json(fresh, dump)
    assert counts == {"objects": 546, "images": 63, "aliases": 54}
    assert fresh.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 546
    assert fresh.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 63
    assert fresh.execute("SELECT COUNT(*) FROM aliases").fetchone()[0] == 54
    o43 = fresh.execute("SELECT * FROM objects WHERE obj_id='OBJ_0043'").fetchone()
    assert o43 is not None
    assert o43["Gewicht_g"] == 41.0
    # FTS-Trigger füllt den Index nach
    fts = fresh.execute(
        "SELECT obj_id FROM objects WHERE rowid IN "
        "(SELECT rowid FROM objects_fts WHERE objects_fts MATCH '\"Quarz\"*')"
    ).fetchall()
    assert any(r[0] == "OBJ_0043" for r in fts)
    fresh.close()


def test_json_import_ignoriert_unbekannte_spalten(tmp_path):
    src = tmp_path / "fremd.json"
    src.write_text(
        '{"objects": [{"obj_id": "OBJ_0999", "Name": "Test", "future_col": "x"}],'
        ' "images": [], "aliases": []}',
        encoding="utf-8",
    )
    db = tmp_path / "db.sqlite3"
    c = open_db(db)
    counts = import_json(c, src)
    assert counts["objects"] == 1
    row = c.execute("SELECT obj_id, Name FROM objects").fetchone()
    assert row["obj_id"] == "OBJ_0999"
    assert row["Name"] == "Test"
    c.close()


def test_csv_import_roundtrip(conn, tmp_path):
    """export_csv → import_csv in eine frische DB ergibt dieselben Felder."""
    dump = tmp_path / "export.csv"
    export_csv(conn, dump, obj_ids=["OBJ_0043"])
    fresh_db = tmp_path / "fresh.sqlite3"
    fresh = open_db(fresh_db)
    rep = import_csv(fresh, dump)
    assert rep.angelegt == ["OBJ_0043"]
    assert rep.aktualisiert == []
    o43 = fresh.execute("SELECT * FROM objects WHERE obj_id='OBJ_0043'").fetchone()
    assert o43["Gewicht_g"] == 41.0
    assert "Quarz" in o43["Mineral_Primaer"]
    assert o43["status"] == "aktiv"
    fresh.close()


def test_csv_import_aktualisiert_bestehend(tmp_path):
    src = tmp_path / "src.csv"
    src.write_text(
        "ID,Mineral_Primaer,Gewicht_g\nOBJ_0001,Quarz,12.0\n",
        encoding="utf-8",
    )
    db = open_db(tmp_path / "x.sqlite3")
    rep1 = import_csv(db, src)
    assert rep1.angelegt == ["OBJ_0001"]

    # Update: neuer Wert für Gewicht
    src2 = tmp_path / "src2.csv"
    src2.write_text(
        "ID,Gewicht_g\nOBJ_0001,15.5\n",
        encoding="utf-8",
    )
    rep2 = import_csv(db, src2)
    assert rep2.angelegt == []
    assert rep2.aktualisiert == ["OBJ_0001"]
    row = db.execute("SELECT * FROM objects WHERE obj_id='OBJ_0001'").fetchone()
    assert row["Gewicht_g"] == 15.5
    assert row["Mineral_Primaer"] == "Quarz"  # alter Wert bleibt erhalten
    db.close()


def test_csv_import_merge_only_konflikt(tmp_path):
    """merge_only: vorhandene Werte werden NICHT ueberschrieben, Konflikte gemeldet."""
    db = open_db(tmp_path / "x.sqlite3")
    src1 = tmp_path / "src.csv"
    src1.write_text(
        "ID,Mineral_Primaer,Gewicht_g\nOBJ_0001,Quarz,10.0\n",
        encoding="utf-8",
    )
    import_csv(db, src1)

    src2 = tmp_path / "src2.csv"
    src2.write_text(
        "ID,Mineral_Primaer,Gewicht_g,Farbe_beobachtet\n"
        "OBJ_0001,Calcit,10.0,gruen\n",  # Mineral abweichend, Gewicht identisch, Farbe neu
        encoding="utf-8",
    )
    rep = import_csv(db, src2, merge_only=True)
    assert rep.aktualisiert == ["OBJ_0001"]
    assert rep.konflikte == {"OBJ_0001": ["Mineral_Primaer"]}
    row = db.execute("SELECT * FROM objects WHERE obj_id='OBJ_0001'").fetchone()
    assert row["Mineral_Primaer"] == "Quarz"   # alter Wert bleibt
    assert row["Gewicht_g"] == 10.0
    assert row["Farbe_beobachtet"] == "gruen"  # leeres Feld wurde gefuellt
    db.close()


def test_csv_import_merge_only_legt_neue_an(tmp_path):
    """merge_only erlaubt das Neuanlegen unbekannter IDs (keine Konflikte moeglich)."""
    db = open_db(tmp_path / "y.sqlite3")
    src = tmp_path / "src.csv"
    src.write_text("ID,Mineral_Primaer\nOBJ_0042,Calcit\n", encoding="utf-8")
    rep = import_csv(db, src, merge_only=True)
    assert rep.angelegt == ["OBJ_0042"]
    assert rep.konflikte == {}
    db.close()


def test_import_report_as_dict_serialisierbar(tmp_path):
    import json
    db = open_db(tmp_path / "z.sqlite3")
    src = tmp_path / "src.csv"
    src.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\n", encoding="utf-8")
    rep = import_csv(db, src)
    json.dumps(rep.as_dict())  # darf nicht crashen
    db.close()


def test_csv_import_create_missing_false(tmp_path):
    src = tmp_path / "src.csv"
    src.write_text("ID,Mineral_Primaer\nOBJ_0999,Calcit\n", encoding="utf-8")
    db = open_db(tmp_path / "x.sqlite3")
    rep = import_csv(db, src, create_missing=False)
    assert rep.uebersprungen == ["OBJ_0999"]
    assert rep.angelegt == []
    assert db.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0
    db.close()


def test_docx_export(conn, tmp_path):
    out = tmp_path / "bericht.docx"
    result = export_docx(conn, REPO, "OBJ_0043", out)
    assert result.is_file()
    from docx import Document
    doc = Document(str(result))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Objekt 43" in text
    assert "OBJ_0043" in text
    # Bilder eingebettet (OBJ_0043 hat Fotos)
    assert doc.inline_shapes is not None and len(doc.inline_shapes) > 0


def test_docx_batch_export(conn, tmp_path):
    out_dir = tmp_path / "berichte"
    progress_calls = []
    paths = export_docx_batch(
        conn, REPO, ["OBJ_0001", "OBJ_0043"], out_dir,
        progress=lambda done, total, obj: progress_calls.append((done, total, obj)),
    )
    assert len(paths) == 2
    assert all(p.is_file() and p.parent == out_dir for p in paths)
    assert {p.name for p in paths} == {
        "Objekt_001_Analysebericht.docx", "Objekt_043_Analysebericht.docx"
    }
    assert progress_calls == [(1, 2, "OBJ_0001"), (2, 2, "OBJ_0043")]


def test_docx_batch_export_leer(conn, tmp_path):
    assert export_docx_batch(conn, REPO, [], tmp_path) == []
