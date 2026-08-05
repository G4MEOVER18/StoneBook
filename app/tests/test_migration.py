"""End-to-End-Migration gegen das echte Repo (read-only auf Quellen, DB in tmp)."""
from pathlib import Path

import pytest

from stonebook.db.database import connect
from stonebook.migration.image_indexer import folder_category
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    report = migrate(REPO, db_file, log=lambda *_: None)
    conn = connect(db_file)
    yield conn, report
    conn.close()


def test_kennzahlen(migrated):
    _, report = migrated
    assert report["objekte"] == 546        # 600 - 54 Aliase
    assert report["aliase"] == 54
    assert report["bilder"] == 63          # Bilder unter objects\ (legacy/docs zählen nicht)
    assert report["parse_fehler"] == 0
    assert 0 < report["aktiv"] < 100       # nur dokumentierte Objekte sind aktiv


def test_obj43_felder(migrated):
    conn, _ = migrated
    row = conn.execute("SELECT * FROM objects WHERE obj_id = 'OBJ_0043'").fetchone()
    assert row is not None
    assert "Quarz" in row["Mineral_Primaer"]
    assert row["Gewicht_g"] == 41.0
    assert row["status"] == "aktiv"


def test_obj44_ist_alias_von_43(migrated):
    conn, _ = migrated
    assert conn.execute("SELECT 1 FROM objects WHERE obj_id = 'OBJ_0044'").fetchone() is None
    row = conn.execute("SELECT canonical_id FROM aliases WHERE alias_id = 'OBJ_0044'").fetchone()
    assert row["canonical_id"] == "OBJ_0043"


def test_obj1_bilder_kategorien(migrated):
    conn, _ = migrated
    cats = {r[0] for r in conn.execute(
        "SELECT DISTINCT kategorie FROM images WHERE obj_id = 'OBJ_0001'")}
    assert {"Kamera", "Mikroskop", "Sonderaufnahmen", "UV395"} <= cats


def test_alias_bilder_umgehaengt(migrated):
    conn, _ = migrated
    # OBJ_0002 ist Alias von OBJ_0001 — dessen Bilder hängen am Kanon mit Herkunft
    rows = conn.execute(
        "SELECT COUNT(*) FROM images WHERE obj_id = 'OBJ_0001' AND herkunft_obj_id = 'OBJ_0002'"
    ).fetchone()
    assert rows[0] > 0


def test_fts_suche(migrated):
    conn, _ = migrated
    rows = conn.execute(
        "SELECT obj_id FROM objects WHERE rowid IN "
        "(SELECT rowid FROM objects_fts WHERE objects_fts MATCH '\"Jaspis\"*')").fetchall()
    ids = {r[0] for r in rows}
    assert "OBJ_0001" in ids


def test_folder_category_mapping():
    assert folder_category("Übersicht") == "Uebersicht"
    assert folder_category("uebersicht") == "Uebersicht"
    assert folder_category("Kamera") == "Kamera"
    assert folder_category("UV 365 nm") == "UV365"
    assert folder_category("UV365") == "UV365"
    assert folder_category("UV 395 nm") == "UV395"
    assert folder_category("Sonderaufnahmen") == "Sonderaufnahmen"
    assert folder_category("  Mikroskop  ") == "Mikroskop"
    assert folder_category("blabla") == "Sonstige"
    # Mojibake-Form aus dem Repo
    assert folder_category("├£bersicht") == "Uebersicht"


def test_img_ext_deckt_webp_ab():
    """``.webp`` gehoert zu den erkannten Raster-Formaten des Index-Filters.

    Google-VP8L/VP8-Format, systemseitiger Default-Screenshot-Format-Setz auf
    Android seit 4.2.1 (2013) und de-facto-Standard fuer WhatsApp-Media-Cache,
    Discord-/Signal-Uploads und Web-Referenz-Bilder aus mindat.org /
    mineralienatlas.de / gemdat.org. Ergaenzt symmetrisch zur bereits
    vorhandenen HEIC-Achse (iOS-Kamera-Default seit iOS 11) die Suffix-Menge
    des Index-Filters um das Google-Plattform-Pendant, damit ein Sammler, der
    Referenz-Screenshots oder Handy-Fotos per WhatsApp-Backup direkt in den
    Objekt-Ordner kopiert, die Bilder in der DB-Index-Ansicht sehen kann
    (statt still durch das Suffix-Filter zu fallen).

    Case-Insensitivitaet ist bereits durch die ``f.suffix.lower()``-
    Normalisierung in :func:`index_images` und im ``NewObjectWizard``
    garantiert (die Menge selbst enthaelt nur lowercase Suffixes, spiegelt
    die uebrigen Eintraege). Anker-Test: die bisherigen Suffixes bleiben
    unveraendert (jpg/jpeg/png/bmp/tif/tiff/heic).
    """
    from stonebook.migration.image_indexer import IMG_EXT
    assert ".webp" in IMG_EXT
    for existing in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".heic"):
        assert existing in IMG_EXT


def test_index_images_findet_webp_datei(tmp_path):
    """End-to-End: ein ``.webp``-Bild im Objekt-Ordner landet in der images-Tabelle.

    Deckt den echten Index-Pfad (``index_images`` mit ``Path.rglob``,
    Kategorie-Zuordnung aus dem Unterordner-Namen, EXIF-/Groessen-Read via
    Pillow) und stellt sicher, dass die Suffix-Menge-Erweiterung nicht nur
    lokal wirkt, sondern das Bild bis in die DB durchgereicht wird. Ein
    parallel angelegtes ``.jpg`` im gleichen Kategorie-Ordner verankert die
    Regress-Symmetrie: beide Formate werden gefunden, beide bekommen die
    gleiche Kategorie und einen SHA256-Hash.
    """
    from PIL import Image

    from stonebook.db.database import open_db
    from stonebook.db.repository import ImageRepo, ObjectRepo
    from stonebook.migration.image_indexer import index_images

    root = tmp_path
    (root / "meta").mkdir()
    obj_dir = root / "objects" / "OBJ_0001" / "Kamera"
    obj_dir.mkdir(parents=True)
    Image.new("RGB", (20, 10), color=(255, 0, 0)).save(obj_dir / "test.webp")
    Image.new("RGB", (20, 10), color=(0, 255, 0)).save(obj_dir / "anker.jpg")

    db_file = tmp_path / "stonebook.sqlite3"
    conn = open_db(db_file)
    try:
        objects = ObjectRepo(conn)
        objects.create("OBJ_0001", Name="Test")
        images = ImageRepo(conn)
        n = index_images(root, images, known_ids={"OBJ_0001"},
                         alias_map={}, log=lambda *_: None)
        assert n == 2
        rows = conn.execute(
            "SELECT dateiname, kategorie, sha256, breite_px, hoehe_px "
            "FROM images WHERE obj_id = 'OBJ_0001' ORDER BY dateiname").fetchall()
        namen = [r["dateiname"] for r in rows]
        assert namen == ["anker.jpg", "test.webp"]
        for r in rows:
            assert r["kategorie"] == "Kamera"
            # Pillow konnte das Format oeffnen und Groessen auslesen
            assert r["breite_px"] == 20
            assert r["hoehe_px"] == 10
            # SHA256 hex-String, 64 Zeichen
            assert len(r["sha256"]) == 64
    finally:
        conn.close()


def test_platzhalter_status(migrated):
    conn, _ = migrated
    row = conn.execute("SELECT status FROM objects WHERE obj_id = 'OBJ_0500'").fetchone()
    assert row["status"] == "platzhalter"


def test_main_cli_report_json(tmp_path, capsys):
    """CLI ``--report-json`` schreibt ausschliesslich gueltiges JSON auf stdout."""
    import json

    from stonebook.migration.migrate import main
    db_file = tmp_path / "cli.sqlite3"
    exit_code = main([str(REPO), "--db", str(db_file), "--report-json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["objekte"] == 546
    assert report["aliase"] == 54
    assert report["bilder"] == 63
    assert db_file.is_file()


def test_main_cli_quiet_kein_progress(tmp_path, capsys):
    """``--quiet`` unterdrueckt die Schritt-Logs (kein '1/5 ...' auf stdout)."""
    from stonebook.migration.migrate import main
    db_file = tmp_path / "q.sqlite3"
    main([str(REPO), "--db", str(db_file), "--quiet"])
    out = capsys.readouterr().out
    assert "1/5" not in out
    assert "Fertig" not in out


def test_main_cli_fehlerhaftes_repo(tmp_path, capsys):
    """Beim nicht-existenten Repo: exit 1, Fehlermeldung auf stderr."""
    from stonebook.migration.migrate import main
    exit_code = main([str(tmp_path), "--db", str(tmp_path / "x.sqlite3")])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "Kein StoneBook-Repo" in err
