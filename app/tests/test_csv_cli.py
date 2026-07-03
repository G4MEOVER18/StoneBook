"""CLI fuer den CSV-Export/-Import."""
import csv
import json
from pathlib import Path

import pytest

from stonebook.export.csv_cli import main
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_export_all_default_ohne_ids(migrated_db, tmp_path, capsys):
    """Ohne IDs/--all/--status wird die gesamte DB exportiert."""
    out = tmp_path / "voll.csv"
    code = main(["export", "--out", str(out), "--db", str(migrated_db)])
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) == 546
    captured = capsys.readouterr().out
    assert "546" in captured and str(out) in captured


def test_export_explizite_obj_ids(migrated_db, tmp_path, capsys):
    out = tmp_path / "sel.csv"
    code = main(["export", "OBJ_0001", "OBJ_0043",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert {r["ID"] for r in rows} == {"OBJ_0001", "OBJ_0043"}
    # --quiet unterdrueckt die Status-Zeile
    assert capsys.readouterr().out == ""


def test_export_normalisiert_alternativ_ids(migrated_db, tmp_path):
    """Kurzformen wie '43' / 'OBJ-43' werden zu OBJ_0043 normalisiert."""
    out = tmp_path / "kurz.csv"
    code = main(["export", "43", "OBJ-1",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert {r["ID"] for r in rows} == {"OBJ_0001", "OBJ_0043"}


def test_export_status_filter(migrated_db, tmp_path):
    out = tmp_path / "aktiv.csv"
    code = main(["export", "--status", "aktiv",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    rows = _read_csv(out)
    assert len(rows) > 0
    assert all(r["status"] == "aktiv" for r in rows)


def test_export_all_flag_ist_aequivalent_zu_kein_filter(migrated_db, tmp_path):
    out = tmp_path / "all.csv"
    code = main(["export", "--all",
                 "--out", str(out), "--db", str(migrated_db), "--quiet"])
    assert code == 0
    assert len(_read_csv(out)) == 546


def test_export_ungueltige_id_gibt_2(migrated_db, tmp_path, capsys):
    out = tmp_path / "x.csv"
    code = main(["export", "Quatsch",
                 "--out", str(out), "--db", str(migrated_db)])
    assert code == 2
    err = capsys.readouterr().err
    assert "Ungueltige Objekt-ID" in err
    # Bei Fehler darf die Zieldatei nicht entstehen
    assert not out.exists()


def test_export_fehlende_db_gibt_2(tmp_path, capsys):
    out = tmp_path / "x.csv"
    code = main(["export", "OBJ_0001",
                 "--out", str(out), "--db", str(tmp_path / "fehlt.sqlite3")])
    assert code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err


def test_import_legt_neue_objekte_an(tmp_path, capsys):
    src = tmp_path / "src.csv"
    src.write_text(
        "ID,Mineral_Primaer,Gewicht_g\nOBJ_0999,Calcit,12.5\n",
        encoding="utf-8",
    )
    db = tmp_path / "neu.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Angelegt: 1" in captured
    # Die frische DB enthaelt das Objekt
    import sqlite3
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM objects WHERE obj_id='OBJ_0999'").fetchone()
    assert row is not None
    assert row["Mineral_Primaer"] == "Calcit"
    assert row["Gewicht_g"] == 12.5
    c.close()


def test_import_json_report(tmp_path, capsys):
    """--json schreibt den Report als JSON auf stdout."""
    src = tmp_path / "src.csv"
    src.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\n",
        encoding="utf-8",
    )
    db = tmp_path / "j.sqlite3"
    code = main(["import", str(src), "--db", str(db), "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["angelegt"] == ["OBJ_0001"]
    assert report["aktualisiert"] == []
    assert report["konflikte"] == {}


def test_import_merge_only_meldet_konflikte(tmp_path, capsys):
    db = tmp_path / "m.sqlite3"
    src1 = tmp_path / "1.csv"
    src1.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\n", encoding="utf-8")
    main(["import", str(src1), "--db", str(db), "--quiet"])
    capsys.readouterr()

    src2 = tmp_path / "2.csv"
    src2.write_text(
        "ID,Mineral_Primaer,Farbe_beobachtet\nOBJ_0001,Calcit,gelb\n",
        encoding="utf-8")
    code = main(["import", str(src2), "--db", str(db), "--merge-only", "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["aktualisiert"] == ["OBJ_0001"]
    assert report["konflikte"] == {"OBJ_0001": ["Mineral_Primaer"]}
    # Alter Wert bleibt erhalten, leeres Feld wurde gefuellt
    import sqlite3
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM objects WHERE obj_id='OBJ_0001'").fetchone()
    assert row["Mineral_Primaer"] == "Quarz"
    assert row["Farbe_beobachtet"] == "gelb"
    c.close()


def test_import_no_create_missing_uebergeht_unbekannte(tmp_path, capsys):
    src = tmp_path / "src.csv"
    src.write_text("ID,Mineral_Primaer\nOBJ_0999,Calcit\n", encoding="utf-8")
    db = tmp_path / "x.sqlite3"
    code = main(["import", str(src), "--db", str(db),
                 "--no-create-missing", "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["uebersprungen"] == ["OBJ_0999"]
    assert report["angelegt"] == []


def test_import_fehlende_csv_gibt_2(tmp_path, capsys):
    code = main(["import", str(tmp_path / "fehlt.csv"),
                 "--db", str(tmp_path / "x.sqlite3")])
    assert code == 2
    err = capsys.readouterr().err
    assert "CSV-Datei fehlt" in err


def test_import_meldet_duplikate_text_und_json(tmp_path, capsys):
    """CLI-Text zeigt "Doppelte IDs in Quelle: N" und --json enthaelt "duplikate".

    Spiegelt die Konflikte-Meldung: Zeile erscheint nur, wenn es Duplikate
    gibt (kein "Doppelte IDs: 0"-Noise), analog "Konflikte (merge-only)".
    """
    src = tmp_path / "dup.csv"
    src.write_text(
        "ID,Mineral_Primaer\n"
        "OBJ_0001,Quarz\n"
        "OBJ_0001,Amethyst\n",
        encoding="utf-8",
    )
    db = tmp_path / "dup.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Doppelte IDs in Quelle: 1" in out

    # --json: duplikate-Feld enthaelt die ID.
    src2 = tmp_path / "dup2.csv"
    src2.write_text(
        "ID,Mineral_Primaer\n"
        "OBJ_0002,Calcit\n"
        "OBJ_0002,Aragonit\n",
        encoding="utf-8",
    )
    db2 = tmp_path / "dup2.sqlite3"
    code = main(["import", str(src2), "--db", str(db2), "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["duplikate"] == ["OBJ_0002"]


def test_import_ohne_duplikate_zeigt_keine_zeile(tmp_path, capsys):
    """Ohne Duplikate erscheint die "Doppelte IDs"-Zeile nicht in der Text-Ausgabe."""
    src = tmp_path / "ok.csv"
    src.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\nOBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    db = tmp_path / "ok.sqlite3"
    code = main(["import", str(src), "--db", str(db)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Doppelte IDs" not in out


def test_export_import_roundtrip(migrated_db, tmp_path):
    """Export aus voller DB -> Import in frische DB liefert dieselben Felder."""
    out = tmp_path / "rt.csv"
    main(["export", "OBJ_0043",
          "--out", str(out), "--db", str(migrated_db), "--quiet"])
    fresh = tmp_path / "fresh.sqlite3"
    main(["import", str(out), "--db", str(fresh), "--quiet"])
    import sqlite3
    c = sqlite3.connect(str(fresh))
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM objects WHERE obj_id='OBJ_0043'").fetchone()
    assert row is not None
    assert "Quarz" in row["Mineral_Primaer"]
    assert row["Gewicht_g"] == 41.0
    c.close()
