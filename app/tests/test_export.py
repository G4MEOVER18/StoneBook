import csv
from pathlib import Path

import pytest

from stonebook.db.database import connect, open_db
from stonebook.export.csv_export import export_csv
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


def test_json_export(conn, tmp_path):
    out = tmp_path / "export.json"
    counts = export_json(conn, out)
    assert counts == {"objects": 546, "images": 63, "aliases": 54}


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
