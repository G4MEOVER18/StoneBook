import csv
import datetime
from pathlib import Path

import pytest

from stonebook.db.database import connect, open_db
from stonebook.export.csv_export import export_csv, import_csv
from stonebook.export.docx_export import export_docx, export_docx_batch
from stonebook.export.json_export import (BACKUP_FORMAT_VERSION,
                                          backup_directory_stats, export_json,
                                          import_json, inspect_backup,
                                          largest_backup, latest_backup,
                                          list_backups, oldest_backup,
                                          prune_backups_by_age,
                                          prune_old_backups, read_backup_meta,
                                          smallest_backup, write_rotated_backup)
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
    assert counts == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}


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


def test_json_export_meta_und_read_backup_meta(conn, tmp_path):
    """export_json schreibt _meta mit Schema-Version; read_backup_meta liest es aus."""
    out = tmp_path / "meta.json"
    export_json(conn, out, obj_ids=["OBJ_0043"])
    meta = read_backup_meta(out)
    assert meta["format_version"] == BACKUP_FORMAT_VERSION
    assert meta["selektion"] == ["OBJ_0043"]
    assert "erstellt_am" in meta and meta["erstellt_am"]


def test_json_export_meta_vollexport_hat_selektion_none(conn, tmp_path):
    out = tmp_path / "voll.json"
    export_json(conn, out)
    meta = read_backup_meta(out)
    assert meta["selektion"] is None


def test_inspect_backup_zeigt_counts_und_meta(conn, tmp_path):
    """inspect_backup liefert Tabellen-Zeilen + Meta ohne Import."""
    out = tmp_path / "in.json"
    export_json(conn, out, obj_ids=["OBJ_0001", "OBJ_0043"])
    info = inspect_backup(out)
    assert info["counts"]["objects"] == 2
    # Bilder werden auf die obj_ids gefiltert
    assert info["counts"]["images"] >= 0
    assert info["meta"]["format_version"] == BACKUP_FORMAT_VERSION
    assert info["meta"]["selektion"] == ["OBJ_0001", "OBJ_0043"]


def test_inspect_backup_gzip(conn, tmp_path):
    out = tmp_path / "in.json.gz"
    export_json(conn, out)
    info = inspect_backup(out)
    assert info["counts"]["objects"] == 546
    assert info["counts"]["images"] == 63
    assert info["counts"]["aliases"] == 54


def test_inspect_backup_altes_format_ohne_meta(tmp_path):
    """Backups ohne _meta liefern leeres Meta-Dict aber korrekte Counts."""
    p = tmp_path / "alt.json"
    p.write_text(
        '{"objects": [{"obj_id": "OBJ_0001"}, {"obj_id": "OBJ_0002"}],'
        ' "images": [], "aliases": [{"alias_id": "OBJ_0003", "canonical_id": "OBJ_0001"}]}',
        encoding="utf-8",
    )
    info = inspect_backup(p)
    assert info["counts"] == {"objects": 2, "images": 0, "aliases": 1, "ki_analysen": 0}
    assert info["meta"] == {}


def test_backup_funktionen_werfen_valueerror_bei_kaputter_datei(tmp_path):
    """import_json/inspect_backup/read_backup_meta liefern Klartext-Fehler bei Muell."""
    from stonebook.db.database import open_db
    bad = tmp_path / "kaputt.json"
    bad.write_text("{not json}", encoding="utf-8")
    db = open_db(tmp_path / "x.sqlite3")
    with pytest.raises(ValueError, match="kein gueltiges JSON"):
        import_json(db, bad)
    with pytest.raises(ValueError, match="kein gueltiges JSON"):
        inspect_backup(bad)
    with pytest.raises(ValueError, match="kein gueltiges JSON"):
        read_backup_meta(bad)
    db.close()


def test_backup_funktionen_werfen_valueerror_bei_falschem_format(tmp_path):
    """Top-Level muss ein Objekt sein - JSON-Array wird klar abgewiesen."""
    from stonebook.db.database import open_db
    p = tmp_path / "array.json"
    p.write_text("[]", encoding="utf-8")
    db = open_db(tmp_path / "x.sqlite3")
    with pytest.raises(ValueError, match="falsches Format"):
        import_json(db, p)
    with pytest.raises(ValueError, match="falsches Format"):
        inspect_backup(p)
    with pytest.raises(ValueError, match="falsches Format"):
        read_backup_meta(p)
    db.close()


def test_read_backup_meta_altes_format(tmp_path):
    """Backups ohne _meta-Sektion liefern ein leeres Meta-Dict (keine Crashs)."""
    p = tmp_path / "alt.json"
    p.write_text(
        '{"objects": [{"obj_id": "OBJ_0001"}], "images": [], "aliases": []}',
        encoding="utf-8",
    )
    assert read_backup_meta(p) == {}


def test_json_import_ignoriert_meta_sektion(tmp_path):
    """import_json ueberspringt _meta sauber, importiert nur Tabellen."""
    from stonebook.db.database import open_db
    src = tmp_path / "mit_meta.json"
    src.write_text(
        '{"_meta": {"format_version": 1, "erstellt_am": "2026-01-01 00:00:00"},'
        ' "objects": [{"obj_id": "OBJ_0001", "Name": "Mit Meta"}],'
        ' "images": [], "aliases": []}',
        encoding="utf-8",
    )
    c = open_db(tmp_path / "x.sqlite3")
    counts = import_json(c, src)
    assert counts["objects"] == 1
    row = c.execute("SELECT obj_id, Name FROM objects").fetchone()
    assert row["obj_id"] == "OBJ_0001"
    assert row["Name"] == "Mit Meta"
    c.close()


def test_json_export_gzip(conn, tmp_path):
    """Pfade mit .gz-Endung werden transparent gzip-komprimiert geschrieben."""
    import gzip
    out = tmp_path / "backup.json.gz"
    counts = export_json(conn, out, obj_ids=["OBJ_0043"])
    assert counts["objects"] == 1
    # gzip-Magic 1f 8b am Dateianfang
    assert out.read_bytes()[:2] == b"\x1f\x8b"
    # Inhalt lesbar
    with gzip.open(out, "rt", encoding="utf-8") as f:
        data = f.read()
    assert "OBJ_0043" in data
    # read_backup_meta funktioniert auch fuer .gz
    meta = read_backup_meta(out)
    assert meta["format_version"] == BACKUP_FORMAT_VERSION
    assert meta["selektion"] == ["OBJ_0043"]


def test_json_gzip_roundtrip(conn, tmp_path):
    """Vollbackup als .json.gz schreiben und in frische DB importieren."""
    dump = tmp_path / "voll.json.gz"
    export_json(conn, dump)
    fresh = open_db(tmp_path / "fresh.sqlite3")
    counts = import_json(fresh, dump)
    assert counts == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}
    fresh.close()


def test_json_export_obj_ids_leer(conn, tmp_path):
    out = tmp_path / "leer.json"
    counts = export_json(conn, out, obj_ids=[])
    assert counts == {"objects": 0, "images": 0, "aliases": 0, "ki_analysen": 0}


def test_json_roundtrip(conn, tmp_path):
    dump = tmp_path / "export.json"
    export_json(conn, dump)
    fresh_db = tmp_path / "fresh.sqlite3"
    fresh = open_db(fresh_db)
    counts = import_json(fresh, dump)
    assert counts == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}
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


def test_json_import_ist_atomar_bei_fk_fehler(tmp_path):
    """Wenn eine Tabelle ein FK-Constraint verletzt, wird die ganze Transaktion zurueckgerollt."""
    import sqlite3
    src = tmp_path / "bad.json"
    src.write_text(
        '{"objects": [{"obj_id": "OBJ_0001", "Name": "OK"}],'
        ' "images": [{"obj_id": "OBJ_NOPE", "kategorie": "Kamera", "rel_path": "x.jpg"}],'
        ' "aliases": []}',
        encoding="utf-8",
    )
    db = open_db(tmp_path / "x.sqlite3")
    with pytest.raises(sqlite3.IntegrityError):
        import_json(db, src)
    # Keine Halbimporte: OBJ_0001 darf NICHT drin sein
    assert db.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 0
    db.close()


def test_json_import_ist_atomar_bei_alias_fk_fehler(tmp_path):
    """Auch ein FK-Verstoss in der dritten Tabelle (aliases) rollt objects mit zurueck."""
    import sqlite3
    src = tmp_path / "bad.json"
    src.write_text(
        '{"objects": [{"obj_id": "OBJ_0001", "Name": "OK"}],'
        ' "images": [],'
        ' "aliases": [{"alias_id": "OBJ_0042", "canonical_id": "OBJ_NOTHERE"}]}',
        encoding="utf-8",
    )
    db = open_db(tmp_path / "x.sqlite3")
    with pytest.raises(sqlite3.IntegrityError):
        import_json(db, src)
    assert db.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM aliases").fetchone()[0] == 0
    db.close()


def test_json_export_und_import_inklusive_ki_analysen(tmp_path):
    """KI-Analysen muessen in Backup/Restore mitgesichert werden (sonst Datenverlust)."""
    src = open_db(tmp_path / "src.sqlite3")
    src.executemany(
        "INSERT INTO objects (obj_id, Name) VALUES (?, ?)",
        [("OBJ_0001", "Mit Analyse"), ("OBJ_0002", "Ohne Analyse")],
    )
    src.executemany(
        "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json, uebernommen_json) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", "2024-06-13 10:00:00", "claude-opus", '{"a":1}', '{"a":1}'),
            ("OBJ_0001", "2024-06-14 10:00:00", "claude-sonnet", '{"b":2}', None),
        ],
    )
    src.commit()
    dump = tmp_path / "voll.json"
    counts = export_json(src, dump)
    assert counts["ki_analysen"] == 2
    src.close()

    fresh = open_db(tmp_path / "fresh.sqlite3")
    counts = import_json(fresh, dump)
    assert counts["ki_analysen"] == 2
    rows = fresh.execute(
        "SELECT obj_id, modell, uebernommen_json FROM ki_analysen ORDER BY id"
    ).fetchall()
    assert [(r["obj_id"], r["modell"]) for r in rows] == [
        ("OBJ_0001", "claude-opus"), ("OBJ_0001", "claude-sonnet"),
    ]
    assert rows[0]["uebernommen_json"] == '{"a":1}'
    assert rows[1]["uebernommen_json"] is None
    fresh.close()


def test_json_export_filtert_ki_analysen_per_obj_id(tmp_path):
    """obj_ids-Filter beschraenkt KI-Analysen auf die genannten Objekte."""
    src = open_db(tmp_path / "src.sqlite3")
    src.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",)],
    )
    src.executemany(
        "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) "
        "VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", "2024-06-13 10:00:00", "m", "{}"),
            ("OBJ_0002", "2024-06-13 11:00:00", "m", "{}"),
            ("OBJ_0003", "2024-06-13 12:00:00", "m", "{}"),
        ],
    )
    src.commit()
    out = tmp_path / "sel.json"
    counts = export_json(src, out, obj_ids=["OBJ_0001", "OBJ_0003"])
    assert counts["ki_analysen"] == 2
    import json as _json
    data = _json.loads(out.read_text(encoding="utf-8"))
    assert {r["obj_id"] for r in data["ki_analysen"]} == {"OBJ_0001", "OBJ_0003"}
    src.close()


def test_json_import_aelteres_backup_ohne_ki_analysen(tmp_path):
    """Alte Backups ohne ki_analysen-Schluessel laufen weiterhin sauber durch."""
    src = tmp_path / "alt.json"
    src.write_text(
        '{"objects": [{"obj_id": "OBJ_0001", "Name": "Alt"}],'
        ' "images": [], "aliases": []}',
        encoding="utf-8",
    )
    c = open_db(tmp_path / "x.sqlite3")
    counts = import_json(c, src)
    assert counts["objects"] == 1
    assert counts["ki_analysen"] == 0
    assert c.execute("SELECT COUNT(*) FROM ki_analysen").fetchone()[0] == 0
    c.close()


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


def test_docx_batch_default_bricht_bei_fehler_ab(conn, tmp_path):
    """Ohne continue_on_error wirft die erste fehlgeschlagene ID."""
    with pytest.raises(ValueError, match="nicht gefunden"):
        export_docx_batch(conn, REPO, ["OBJ_0043", "OBJ_9999"], tmp_path)


def test_docx_batch_continue_on_error(conn, tmp_path):
    """continue_on_error sammelt Fehler statt Abbruch; on_error informiert."""
    errs: list[tuple[str, Exception]] = []
    paths = export_docx_batch(
        conn, REPO, ["OBJ_0043", "OBJ_9999", "OBJ_0001"], tmp_path,
        continue_on_error=True, on_error=lambda oid, exc: errs.append((oid, exc)),
    )
    assert len(paths) == 2  # nur die existierenden
    assert {p.name for p in paths} == {
        "Objekt_001_Analysebericht.docx", "Objekt_043_Analysebericht.docx"
    }
    assert [oid for oid, _ in errs] == ["OBJ_9999"]
    assert isinstance(errs[0][1], ValueError)


def test_rotated_backup_schreibt_und_rotiert(tmp_path):
    """Vier aufeinanderfolgende Backups mit keep=2 belassen nur die 2 neuesten."""
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id, Name) VALUES ('OBJ_0001', 'Test')")
    db.commit()
    backups_dir = tmp_path / "backups"
    base = datetime.datetime(2024, 6, 13, 10, 0, 0)
    written = [
        write_rotated_backup(db, backups_dir, keep=2,
                             now=base + datetime.timedelta(minutes=i))
        for i in range(4)
    ]
    # Alle 4 Aufrufe melden ihren Zieldateipfad
    assert all(p.is_file() or i < 2 for i, p in enumerate(written))
    # Nach Rotation: nur die 2 juengsten Backups bleiben uebrig
    remaining = list_backups(backups_dir)
    assert len(remaining) == 2
    assert remaining == sorted(remaining, key=lambda p: p.name)
    # Die juengsten beiden Stempel
    assert "20240613_100200" in remaining[0].name
    assert "20240613_100300" in remaining[1].name
    db.close()


def test_rotated_backup_compress_false(tmp_path):
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    target = write_rotated_backup(db, tmp_path / "b", compress=False)
    assert target.name.endswith(".json") and not target.name.endswith(".gz")
    # gzip-Magic darf NICHT am Anfang stehen
    assert target.read_bytes()[:2] != b"\x1f\x8b"
    db.close()


def test_rotated_backup_compress_true_ist_default(tmp_path):
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    target = write_rotated_backup(db, tmp_path / "b")
    assert target.name.endswith(".json.gz")
    assert target.read_bytes()[:2] == b"\x1f\x8b"
    db.close()


def test_rotated_backup_inhalt_ist_restaurierbar(tmp_path):
    """Eine rotierte Backup-Datei ist ein vollwertiges import_json-Backup."""
    src = open_db(tmp_path / "src.sqlite3")
    src.execute("INSERT INTO objects (obj_id, Name) VALUES ('OBJ_0042', 'Rot')")
    src.commit()
    target = write_rotated_backup(src, tmp_path / "bk")
    src.close()
    # Frische DB mit identischen Daten?
    fresh = open_db(tmp_path / "fresh.sqlite3")
    counts = import_json(fresh, target)
    assert counts["objects"] == 1
    row = fresh.execute("SELECT obj_id, Name FROM objects").fetchone()
    assert row["obj_id"] == "OBJ_0042"
    assert row["Name"] == "Rot"
    fresh.close()


def test_rotated_backup_ignoriert_fremde_dateien(tmp_path):
    """Rotation laesst andere Dateien im Backup-Ordner unangetastet."""
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    backups_dir.mkdir()
    fremd = backups_dir / "wichtige_notizen.txt"
    fremd.write_text("nicht anfassen", encoding="utf-8")
    for i in range(3):
        write_rotated_backup(db, backups_dir, keep=1,
                             now=datetime.datetime(2024, 6, 13, 10, i, 0))
    assert fremd.is_file()
    assert fremd.read_text(encoding="utf-8") == "nicht anfassen"
    assert len(list_backups(backups_dir)) == 1
    db.close()


def test_rotated_backup_keep_zu_klein_raises(tmp_path):
    db = open_db(tmp_path / "x.sqlite3")
    with pytest.raises(ValueError):
        write_rotated_backup(db, tmp_path / "b", keep=0)
    db.close()


def test_list_backups_leerer_ordner(tmp_path):
    assert list_backups(tmp_path / "nichtda") == []
    leer = tmp_path / "leer"
    leer.mkdir()
    assert list_backups(leer) == []


def test_latest_backup_leerer_ordner(tmp_path):
    """latest_backup liefert None bei fehlendem/leerem/fremd-nur Ordner.

    Spiegelt :func:`test_list_backups_leerer_ordner`: der Ein-Datei-Wrapper
    muss dieselben Grenzfaelle abfangen wie der Listen-Wrapper (fehlender
    Ordner → keine Datei; leerer Ordner → keine Datei; Ordner mit nur
    fremden Dateien → keine passende Datei), damit Cron-Reporter und
    Restore-Dialoge ohne Sonderbehandlung "noch kein Backup vorhanden"
    ueber ``if latest is None``-Guard abfangen koennen.
    """
    assert latest_backup(tmp_path / "nichtda") is None
    leer = tmp_path / "leer"
    leer.mkdir()
    assert latest_backup(leer) is None
    # Nur fremde Dateien -> auch None (spiegelt list_backups-Filter ueber _BACKUP_RE)
    (leer / "README.txt").write_text("keine Backup", encoding="utf-8")
    (leer / "andere_backup_20240101_000000.json.gz").write_bytes(b"")
    assert latest_backup(leer) is None


def test_latest_backup_liefert_juengsten_stempel(tmp_path):
    """latest_backup liefert die Datei mit dem groessten Filename-Stempel.

    Filename-Stempel als Single-Source-of-Truth (spiegelt
    :func:`prune_backups_by_age`): auch wenn eine spaeter geschriebene Datei
    einen frueheren Namens-Stempel traegt (z.B. weil sie von einem
    NAS-Backup-Server kopiert wurde), gewinnt der lexikographisch groessere
    Name. Reihenfolge der Erstellung im Test sind absichtlich verwuerfelt,
    damit ``mtime``-basierte Implementierungen scheitern wuerden.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    # Reihenfolge der Erstellung: aeltester Stempel zuerst geschrieben,
    # dann juengster, dann mittlerer - damit mtime-basierte Auswahl auf den
    # mittleren zeigen wuerde (letzte Schreibe), aber der juengste Namens-
    # Stempel korrekt gewinnt.
    stamps = ("20240613_100000", "20240613_120000", "20240613_110000")
    for stamp in stamps:
        write_rotated_backup(
            db, backups_dir, keep=99,
            now=datetime.datetime.strptime(stamp, "%Y%m%d_%H%M%S"))
    latest = latest_backup(backups_dir)
    assert latest is not None
    assert "20240613_120000" in latest.name  # juengster Stempel
    db.close()


def test_latest_backup_ignoriert_fremde_dateien(tmp_path):
    """Fremde Dateien im Ordner (README, andere Backup-Schemata) werden ignoriert.

    Spiegelt :func:`test_prune_backups_by_age_ignoriert_fremde_dateien`
    auf die latest-Achse: nur Dateien, die zum ``stonebook_backup_
    YYYYMMDD_HHMMSS.json[.gz]``-Muster passen, kommen als "juengstes
    Backup" in Frage. Eine lexikographisch groessere fremde Datei
    (``zzz_neuer.json.gz`` oder ``andere_backup_29990101_000000.json.gz``)
    darf das echte juengste Backup nicht verdraengen, sonst wuerde
    ``restore-latest`` das falsche File einspielen.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    now = datetime.datetime(2024, 6, 13, 10, 0, 0)
    write_rotated_backup(db, backups_dir, keep=99, now=now)
    # Fremde Datei mit lexikographisch groesserem Namen als das echte Backup
    fremd = backups_dir / "zzz_andere_backup_29990101_000000.json.gz"
    fremd.write_bytes(b"")
    latest = latest_backup(backups_dir)
    assert latest is not None
    assert "20240613_100000" in latest.name
    assert latest != fremd
    db.close()


def test_latest_backup_einzelne_datei(tmp_path):
    """Ein einzelnes Backup ist gleichzeitig das juengste.

    Grenzfall count=1: die Datei ist gleichzeitig ``list_backups[0]`` und
    ``list_backups[-1]``; spiegelt :func:`prune_backups_by_age_null_loescht
    _alles_vor_now`, wo der Ein-Datei-Fall in denselben Wrapper-Funktionen
    korrekt behandelt sein muss. Wichtiger Sanity-Check fuer die Auto-
    Auswahl im Restore-Dialog: nach der ersten Backup-Schreibe muss
    ``restore-latest`` auf dieses einzige Backup zeigen.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    write_rotated_backup(
        db, backups_dir, keep=99,
        now=datetime.datetime(2024, 6, 13, 10, 0, 0))
    latest = latest_backup(backups_dir)
    assert latest is not None
    assert latest == list_backups(backups_dir)[0]
    db.close()


def test_oldest_backup_leerer_ordner(tmp_path):
    """oldest_backup liefert None bei fehlendem/leerem/fremd-nur Ordner.

    Spiegelt :func:`test_latest_backup_leerer_ordner` auf den Gegen-Endpunkt
    der Backup-Halde: der Ein-Datei-Wrapper muss dieselben Grenzfaelle
    abfangen wie sein Symmetrie-Partner (fehlender Ordner → keine Datei;
    leerer Ordner → keine Datei; Ordner mit nur fremden Dateien → keine
    passende Datei), damit Wartungs-Dashboards und Prune-Preview ohne
    Sonderbehandlung "noch kein Backup vorhanden" ueber ``if oldest is
    None``-Guard abfangen koennen.
    """
    assert oldest_backup(tmp_path / "nichtda") is None
    leer = tmp_path / "leer"
    leer.mkdir()
    assert oldest_backup(leer) is None
    (leer / "README.txt").write_text("keine Backup", encoding="utf-8")
    (leer / "andere_backup_20240101_000000.json.gz").write_bytes(b"")
    assert oldest_backup(leer) is None


def test_oldest_backup_liefert_aeltesten_stempel(tmp_path):
    """oldest_backup liefert die Datei mit dem kleinsten Filename-Stempel.

    Spiegelt :func:`test_latest_backup_liefert_juengsten_stempel` auf den
    Gegen-Endpunkt: waehrend latest_backup den lexikographisch groessten
    Namen liefert, liefert oldest_backup den lexikographisch kleinsten.
    Filename-Stempel als Single-Source-of-Truth (spiegelt
    :func:`prune_backups_by_age`): auch wenn eine frueher geschriebene
    Datei einen spaeteren Namens-Stempel traegt (weil ein alter NAS-
    Backup nachtraeglich importiert wurde), gewinnt der lexikographisch
    kleinere Name. Reihenfolge der Erstellung im Test sind absichtlich
    verwuerfelt, damit ``mtime``-basierte Implementierungen scheitern
    wuerden.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    stamps = ("20240613_110000", "20240613_100000", "20240613_120000")
    for stamp in stamps:
        write_rotated_backup(
            db, backups_dir, keep=99,
            now=datetime.datetime.strptime(stamp, "%Y%m%d_%H%M%S"))
    oldest = oldest_backup(backups_dir)
    assert oldest is not None
    assert "20240613_100000" in oldest.name  # aeltester Stempel
    db.close()


def test_oldest_backup_ignoriert_fremde_dateien(tmp_path):
    """Fremde Dateien im Ordner (README, andere Backup-Schemata) werden ignoriert.

    Spiegelt :func:`test_latest_backup_ignoriert_fremde_dateien` auf den
    Gegen-Endpunkt: eine lexikographisch kleinere fremde Datei
    (``aaaa_frueher.json.gz`` oder ``andere_backup_19700101_000000.json.gz``)
    darf das echte aelteste Backup nicht verdraengen, sonst wuerde
    Prune-Preview auf die falsche Datei zeigen und Wartungs-Reporter
    falsche Halden-Zeitspannen anzeigen.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    now = datetime.datetime(2024, 6, 13, 10, 0, 0)
    write_rotated_backup(db, backups_dir, keep=99, now=now)
    # Fremde Datei mit lexikographisch kleinerem Namen als das echte Backup
    fremd = backups_dir / "aaaa_andere_backup_19700101_000000.json.gz"
    fremd.write_bytes(b"")
    oldest = oldest_backup(backups_dir)
    assert oldest is not None
    assert "20240613_100000" in oldest.name
    assert oldest != fremd
    db.close()


def test_largest_und_smallest_backup_leerer_ordner(tmp_path):
    """largest/smallest_backup liefern None bei fehlendem/leerem/fremd-nur Ordner.

    Spiegelt :func:`test_latest_backup_leerer_ordner` und
    :func:`test_oldest_backup_leerer_ordner` auf die Volume-Achse (Bytes):
    beide Ein-Datei-Wrapper der Grosse-Achse muessen dieselben Grenzfaelle
    abfangen wie die Zeit-Achsen-Wrapper (fehlender Ordner → keine Datei;
    leerer Ordner → keine Datei; Ordner mit nur fremden Dateien → keine
    passende Datei), damit Anomalie-Detektoren und Speicher-Reports ohne
    Sonderbehandlung "noch kein Backup vorhanden" ueber ``if None``-Guard
    abfangen koennen.
    """
    for fn in (largest_backup, smallest_backup):
        assert fn(tmp_path / "nichtda") is None
        leer = tmp_path / f"leer_{fn.__name__}"
        leer.mkdir()
        assert fn(leer) is None
        (leer / "README.txt").write_text("keine Backup", encoding="utf-8")
        (leer / "andere_backup_20240101_000000.json.gz").write_bytes(b"x" * 999)
        assert fn(leer) is None


def test_largest_backup_liefert_groesste_datei(tmp_path):
    """largest_backup waehlt die Datei mit dem groessten ``st_size``.

    Spiegelt :func:`test_latest_backup_liefert_juengsten_stempel` auf die
    Volume-Achse: waehrend die Zeit-Achse den Filename-Stempel als
    Auswahl-Kriterium nimmt, greift die Volume-Achse auf ``st_size``
    zu. Die drei geschriebenen Backups tragen alle denselben Byte-Count,
    daher wird der mittlere gezielt vergroessert (``.write_bytes`` mit
    Padding), damit der Groessen-Vergleich eindeutig funktioniert und
    nicht auf die deterministische Zweitsortierung (Filename)
    zurueckfaellt.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    stamps = ("20240613_100000", "20240613_110000", "20240613_120000")
    for stamp in stamps:
        write_rotated_backup(
            db, backups_dir, keep=99,
            now=datetime.datetime.strptime(stamp, "%Y%m%d_%H%M%S"))
    files = list_backups(backups_dir)
    # Mittleres Backup gezielt vergroessern (Padding ans Ende, .gz bleibt lesbar
    # als "kaputt", aber der st_size-Vergleich prueft nur die Roh-Bytes).
    middle = files[1]
    middle.write_bytes(middle.read_bytes() + b"\x00" * 50_000)
    largest = largest_backup(backups_dir)
    assert largest == middle
    db.close()


def test_smallest_backup_liefert_kleinste_datei(tmp_path):
    """smallest_backup waehlt die Datei mit dem kleinsten ``st_size``.

    Spiegelt :func:`test_largest_backup_liefert_groesste_datei` auf den
    Gegen-Endpunkt der Volume-Achse. Konstruktion analog: alle drei
    Backups tragen initial denselben Byte-Count, das mittlere wird
    gezielt verkleinert (auf Null-Bytes ueberschrieben), damit der
    Groessen-Vergleich eindeutig auf ``st_size`` und nicht auf die
    Filename-Zweitsortierung faellt.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    stamps = ("20240613_100000", "20240613_110000", "20240613_120000")
    for stamp in stamps:
        write_rotated_backup(
            db, backups_dir, keep=99,
            now=datetime.datetime.strptime(stamp, "%Y%m%d_%H%M%S"))
    files = list_backups(backups_dir)
    # Mittleres Backup gezielt verkleinern
    files[1].write_bytes(b"")
    smallest = smallest_backup(backups_dir)
    assert smallest == files[1]
    db.close()


def test_largest_und_smallest_backup_ignorieren_fremde_dateien(tmp_path):
    """Fremde Dateien im Ordner werden von beiden Extrema-Reportern ignoriert.

    Spiegelt :func:`test_latest_backup_ignoriert_fremde_dateien` und
    :func:`test_oldest_backup_ignoriert_fremde_dateien` auf die Volume-
    Achse: fremde Dateien im Backup-Ordner (README, andere Backup-
    Schemata) sind vom ``_BACKUP_RE``-Filter ausgeschlossen, auch wenn
    sie deutlich groesser oder kleiner sind als das echte Backup - sonst
    wuerden Anomalie-Reports auf Ordner-Artefakte statt echte Backups
    zeigen.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    write_rotated_backup(
        db, backups_dir, keep=99,
        now=datetime.datetime(2024, 6, 13, 10, 0, 0))
    only_backup = list_backups(backups_dir)[0]
    # Fremde Dateien mit extremen Groessen
    (backups_dir / "README.txt").write_bytes(b"x" * 10_000_000)
    (backups_dir / "andere_backup_20240101_000000.json.gz").write_bytes(b"")
    # Beide Extrema-Reporter zeigen ausschliesslich auf das echte Backup
    assert largest_backup(backups_dir) == only_backup
    assert smallest_backup(backups_dir) == only_backup
    db.close()


def test_largest_und_smallest_backup_bei_einzelbackup_identisch(tmp_path):
    """Ein einzelnes Backup ist gleichzeitig groesstes und kleinstes.

    Spiegelt :func:`test_oldest_und_latest_bei_einzelbackup_identisch`
    auf die Volume-Achse: bei count=1 fallen alle vier Ein-Datei-Wrapper
    (latest, oldest, largest, smallest) auf dieselbe Datei zusammen -
    Sanity-Check fuer Halden-Reporter, die die Ein-Datei-Grenzfall nicht
    als Sonderfall behandeln muessen.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    write_rotated_backup(
        db, backups_dir, keep=99,
        now=datetime.datetime(2024, 6, 13, 10, 0, 0))
    only_backup = list_backups(backups_dir)[0]
    assert largest_backup(backups_dir) == only_backup
    assert smallest_backup(backups_dir) == only_backup
    assert largest_backup(backups_dir) == smallest_backup(backups_dir)
    db.close()


def test_largest_und_smallest_gleiche_groesse_deterministische_wahl(tmp_path):
    """Bei gleichem ``st_size`` gewinnt eine deterministische Filename-Wahl.

    Bei zwei Backups mit identischen Bytes ist die Extrema-Auswahl ohne
    Zweitsortierung nichtdeterministisch (dict-Reihenfolge, Filesystem-
    Traversal-Order). Der Wrapper faellt auf den Filename zurueck:
    largest bevorzugt den lexikographisch groesseren (juengeren) Namen,
    smallest den lexikographisch kleineren (aelteren). Damit sind
    Anomalie-Reports und Test-Fixtures reproduzierbar.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    stamps = ("20240613_100000", "20240613_120000")
    for stamp in stamps:
        write_rotated_backup(
            db, backups_dir, keep=99,
            now=datetime.datetime.strptime(stamp, "%Y%m%d_%H%M%S"))
    files = list_backups(backups_dir)
    assert files[0].stat().st_size == files[1].stat().st_size
    # largest waehlt den juengeren (lex-groesseren) Filename bei Gleichstand
    assert largest_backup(backups_dir) == files[1]
    # smallest waehlt den aelteren (lex-kleineren) Filename bei Gleichstand
    assert smallest_backup(backups_dir) == files[0]
    db.close()


def test_oldest_und_latest_bei_einzelbackup_identisch(tmp_path):
    """Ein einzelnes Backup ist gleichzeitig aeltestes und juengstes.

    Grenzfall count=1: oldest == latest == list_backups[0] == list_backups[-1];
    spiegelt :func:`test_latest_backup_einzelne_datei` auf die Symmetrie-
    Achse und die Konvention von :func:`backup_directory_stats`, wo
    oldest_stamp == newest_stamp bei genau einer Datei zusammenfallen.
    Sanity-Check fuer Halden-Reporter, die den Ein-Datei-Fall nicht als
    Sonderfall behandeln muessen.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    write_rotated_backup(
        db, backups_dir, keep=99,
        now=datetime.datetime(2024, 6, 13, 10, 0, 0))
    assert oldest_backup(backups_dir) == latest_backup(backups_dir)
    db.close()


def test_prune_old_backups_loescht_alte(tmp_path):
    """prune_old_backups laesst nur die juengsten ``keep`` Backups uebrig."""
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    base = datetime.datetime(2024, 6, 13, 10, 0, 0)
    for i in range(5):
        write_rotated_backup(db, backups_dir, keep=99,
                             now=base + datetime.timedelta(minutes=i))
    assert len(list_backups(backups_dir)) == 5
    # Auf 2 reduzieren
    deleted = prune_old_backups(backups_dir, keep=2)
    assert len(deleted) == 3
    remaining = list_backups(backups_dir)
    assert len(remaining) == 2
    assert "20240613_100300" in remaining[0].name
    assert "20240613_100400" in remaining[1].name
    db.close()


def test_prune_old_backups_nichts_zu_tun(tmp_path):
    """Wenn weniger Backups als keep da sind, wird nichts geloescht."""
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    write_rotated_backup(db, backups_dir, keep=99)
    deleted = prune_old_backups(backups_dir, keep=10)
    assert deleted == []
    assert len(list_backups(backups_dir)) == 1
    db.close()


def test_prune_old_backups_keep_zu_klein_raises(tmp_path):
    with pytest.raises(ValueError):
        prune_old_backups(tmp_path / "b", keep=0)


def test_prune_backups_by_age_loescht_alte(tmp_path):
    """prune_backups_by_age entfernt alle Backups aelter als max_age_days.

    Spiegelt :func:`test_prune_old_backups_loescht_alte` auf die Zeit-Achse:
    Count-Pruning haelt die letzten N Backups, Age-Pruning haelt alle Backups
    der letzten K Tage.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    now = datetime.datetime(2024, 6, 13, 10, 0, 0)
    # Drei Backups, je 1 Tag auseinander
    for days_back in (40, 20, 5):
        stamp = now - datetime.timedelta(days=days_back)
        write_rotated_backup(db, backups_dir, keep=99, now=stamp)
    assert len(list_backups(backups_dir)) == 3
    # Cutoff 30 Tage -> loescht das 40-Tage-alte Backup
    deleted = prune_backups_by_age(backups_dir, max_age_days=30, now=now)
    assert len(deleted) == 1
    assert "_40" not in deleted[0].name  # nicht im Stempel, aber Sanity
    remaining = list_backups(backups_dir)
    assert len(remaining) == 2
    # Die zwei juengeren Backups bleiben
    assert any("20240524" in p.name for p in remaining)  # 20 Tage zurueck
    assert any("20240608" in p.name for p in remaining)  # 5 Tage zurueck
    db.close()


def test_prune_backups_by_age_nichts_zu_tun(tmp_path):
    """Sind alle Backups juenger als das Cutoff, wird nichts geloescht."""
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    now = datetime.datetime(2024, 6, 13, 10, 0, 0)
    write_rotated_backup(db, backups_dir, keep=99,
                         now=now - datetime.timedelta(days=5))
    deleted = prune_backups_by_age(backups_dir, max_age_days=30, now=now)
    assert deleted == []
    assert len(list_backups(backups_dir)) == 1
    db.close()


def test_prune_backups_by_age_negativer_wert_raises(tmp_path):
    """Negative max_age_days sind sinnlos und werden abgelehnt."""
    with pytest.raises(ValueError):
        prune_backups_by_age(tmp_path / "b", max_age_days=-1)


def test_prune_backups_by_age_null_loescht_alles_vor_now(tmp_path):
    """max_age_days=0 loescht alle Backups, deren Stempel < now ist.

    Geeignet als Cleanup-Befehl vor einem Voll-Reset, ohne den Ordner zu
    entfernen oder neuere Backups (== now-Stempel, wie eines simultanen
    Schreibers) zu beruehren.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    now = datetime.datetime(2024, 6, 13, 10, 0, 0)
    # Zwei alte Backups; eines exakt zur "jetzt"-Sekunde
    write_rotated_backup(db, backups_dir, keep=99,
                         now=now - datetime.timedelta(days=1))
    write_rotated_backup(db, backups_dir, keep=99, now=now)
    deleted = prune_backups_by_age(backups_dir, max_age_days=0, now=now)
    assert len(deleted) == 1
    remaining = list_backups(backups_dir)
    assert len(remaining) == 1
    assert "20240613_100000" in remaining[0].name
    db.close()


def test_prune_backups_by_age_ignoriert_fremde_dateien(tmp_path):
    """Dateien, die nicht zum Backup-Namensschema passen, bleiben unberuehrt.

    Spiegelt das Verhalten von :func:`prune_old_backups`: nur Dateien, die
    zum ``stonebook_backup_YYYYMMDD_HHMMSS.json[.gz]``-Muster passen, werden
    erfasst. Andere Dateien (README, fremde Backups, Konfig-Dateien) bleiben.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    now = datetime.datetime(2024, 6, 13, 10, 0, 0)
    write_rotated_backup(db, backups_dir, keep=99,
                         now=now - datetime.timedelta(days=50))
    fremd = backups_dir / "README.txt"
    fremd.write_text("nicht ein Backup", encoding="utf-8")
    fremdes_archiv = backups_dir / "andere_backup_20100101_000000.json.gz"
    fremdes_archiv.write_bytes(b"")
    deleted = prune_backups_by_age(backups_dir, max_age_days=30, now=now)
    assert len(deleted) == 1
    assert fremd.exists()
    assert fremdes_archiv.exists()
    db.close()


def test_backup_directory_stats_leerer_und_nichtexistierender_ordner(tmp_path):
    """Leerer und nicht existierender Ordner liefern beide den Null-Report.

    Spiegelt :func:`list_backups`, das bei fehlendem Ordner eine leere Liste
    statt einer Exception zurueckgibt - geeignet fuer Cron-Reporter, die
    den Report vor der ersten Backup-Schreibe machen.
    """
    empty = tmp_path / "leer"
    empty.mkdir()
    info = backup_directory_stats(empty)
    assert info == {
        "count": 0,
        "total_bytes": 0,
        "oldest_stamp": None,
        "newest_stamp": None,
    }
    info = backup_directory_stats(tmp_path / "existiert_nicht")
    assert info == {
        "count": 0,
        "total_bytes": 0,
        "oldest_stamp": None,
        "newest_stamp": None,
    }


def test_backup_directory_stats_zaehlt_und_summiert(tmp_path):
    """Drei Backups liefern korrektes Count/Bytes/frueheste/spaeteste Stempel-Tupel.

    Verifiziert das Kern-Verhalten des Reports: Zaehlung stimmt mit
    :func:`list_backups`, Bytes-Summe stimmt mit ``sum(p.stat().st_size)``,
    und die Zeitstempel spiegeln den Dateinamen (nicht ``mtime``).
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    stamps = [
        datetime.datetime(2024, 1, 15, 10, 0, 0),
        datetime.datetime(2024, 3, 20, 12, 30, 0),
        datetime.datetime(2024, 6, 1, 8, 15, 0),
    ]
    for stamp in stamps:
        write_rotated_backup(db, backups_dir, keep=99, now=stamp)
    db.close()

    info = backup_directory_stats(backups_dir)
    assert info["count"] == 3
    expected_bytes = sum(p.stat().st_size for p in list_backups(backups_dir))
    assert info["total_bytes"] == expected_bytes
    assert info["total_bytes"] > 0
    assert info["oldest_stamp"] == "2024-01-15T10:00:00"
    assert info["newest_stamp"] == "2024-06-01T08:15:00"


def test_backup_directory_stats_ignoriert_fremde_dateien(tmp_path):
    """Fremde Dateien im Backup-Ordner zaehlen weder in count noch in total_bytes.

    Spiegelt das Verhalten von :func:`list_backups` und den prune-Funktionen:
    nur Dateien, die zum ``stonebook_backup_YYYYMMDD_HHMMSS.json[.gz]``-Muster
    passen, werden erfasst. README-Dateien, andere Exporte, Lock-Files
    bleiben unangetastet vom Report.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    stamp = datetime.datetime(2024, 6, 13, 10, 0, 0)
    write_rotated_backup(db, backups_dir, keep=99, now=stamp)
    db.close()
    fremd = backups_dir / "README.txt"
    fremd.write_text("nicht ein Backup", encoding="utf-8")
    (backups_dir / "andere_backup_20100101_000000.json.gz").write_bytes(
        b"x" * 10_000)

    info = backup_directory_stats(backups_dir)
    assert info["count"] == 1
    only_backup_bytes = list_backups(backups_dir)[0].stat().st_size
    assert info["total_bytes"] == only_backup_bytes
    # Fremdes Archiv (10_000 Byte) darf nicht in total_bytes einfliessen
    assert info["total_bytes"] < 10_000
    assert info["oldest_stamp"] == "2024-06-13T10:00:00"
    assert info["newest_stamp"] == "2024-06-13T10:00:00"


def test_backup_directory_stats_einzelnes_backup(tmp_path):
    """Bei einem einzigen Backup sind oldest_stamp und newest_stamp identisch.

    Kein Edge-Case-Fehler beim Grenzfall count=1 - die min/max-Reduktion
    ueber die stamps-Liste liefert deterministisch denselben Wert.
    """
    db = open_db(tmp_path / "x.sqlite3")
    db.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    db.commit()
    backups_dir = tmp_path / "b"
    stamp = datetime.datetime(2024, 6, 13, 14, 30, 45)
    write_rotated_backup(db, backups_dir, keep=99, now=stamp)
    db.close()

    info = backup_directory_stats(backups_dir)
    assert info["count"] == 1
    assert info["oldest_stamp"] == info["newest_stamp"] == "2024-06-13T14:30:45"
