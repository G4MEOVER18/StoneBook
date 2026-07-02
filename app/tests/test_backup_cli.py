"""CLI fuer JSON-Backup-Verwaltung."""
import json
import time
from pathlib import Path

import pytest

from stonebook.export.backup_cli import main
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    return db_file


def test_write_list_und_restore_round_trip(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "backups"
    # 1) write
    exit_code = main(["write", "--backup-dir", str(backup_dir),
                      "--db", str(migrated_db), "--keep", "3"])
    assert exit_code == 0
    written = Path(capsys.readouterr().out.strip())
    assert written.is_file()
    assert written.suffix == ".gz"
    assert written.parent == backup_dir

    # 2) list zeigt das eine Backup
    exit_code = main(["list", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    listed = [Path(p) for p in capsys.readouterr().out.splitlines()]
    assert listed == [written]

    # 3) restore in eine neue DB
    new_db = tmp_path / "restored.sqlite3"
    exit_code = main(["restore", str(written), "--db", str(new_db)])
    assert exit_code == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}


def test_write_no_compress(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "no_gz"
    exit_code = main(["write", "--backup-dir", str(backup_dir),
                      "--db", str(migrated_db), "--no-compress"])
    assert exit_code == 0
    p = Path(capsys.readouterr().out.strip())
    assert p.suffix == ".json"


def test_inspect_zeigt_counts(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "i"
    main(["write", "--backup-dir", str(backup_dir),
          "--db", str(migrated_db)])
    written = Path(capsys.readouterr().out.strip())
    main(["inspect", str(written)])
    info = json.loads(capsys.readouterr().out)
    assert info["counts"] == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}
    assert "meta" in info


def test_prune_loescht_alte_backups(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "p"
    backup_dir.mkdir()
    # Drei Pseudo-Backups mit unterschiedlichem Zeitstempel
    paths = []
    for stamp in ("20240101_000000", "20240102_000000", "20240103_000000"):
        p = backup_dir / f"stonebook_backup_{stamp}.json.gz"
        p.write_bytes(b"")
        paths.append(p)
    exit_code = main(["prune", "--backup-dir", str(backup_dir), "--keep", "1"])
    assert exit_code == 0
    # Die zwei aeltesten geloescht; nur das neueste bleibt
    assert paths[0].exists() is False
    assert paths[1].exists() is False
    assert paths[2].exists() is True


def test_restore_fordert_force_bei_existierender_db(migrated_db, tmp_path, capsys):
    backup_dir = tmp_path / "f"
    main(["write", "--backup-dir", str(backup_dir),
          "--db", str(migrated_db)])
    backup = Path(capsys.readouterr().out.strip())

    existing = tmp_path / "existing.sqlite3"
    existing.write_bytes(b"placeholder")
    exit_code = main(["restore", str(backup), "--db", str(existing)])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "existiert" in err

    # Mit --force klappt es
    exit_code = main(["restore", str(backup), "--db", str(existing), "--force"])
    assert exit_code == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts["objects"] == 546


def test_prune_age_loescht_alte_backups(tmp_path, capsys):
    """prune-age Subcommand: alte Backups (Datei-Stempel) werden geloescht.

    Spiegelt :func:`test_prune_loescht_alte_backups` auf die Zeit-Achse:
    Count-Pruning haelt die letzten N, Age-Pruning haelt alle der letzten K Tage.
    Verwendet einen Stempel aus den 70ern, der garantiert aelter ist als
    jeder vernuenftige max_age_days-Wert (unabhaengig vom aktuellen Datum
    des Test-Laufs).
    """
    backup_dir = tmp_path / "page"
    backup_dir.mkdir()
    alt = backup_dir / "stonebook_backup_19700101_000000.json.gz"
    alt.write_bytes(b"")
    # Junger Stempel: einen Tag in der Vergangenheit (immer juenger als 30 Tage).
    today = time.strftime("%Y%m%d")
    jung = backup_dir / f"stonebook_backup_{today}_120000.json.gz"
    jung.write_bytes(b"")
    exit_code = main(["prune-age", "--backup-dir", str(backup_dir),
                      "--max-age-days", "30"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "19700101" in out
    assert today not in out
    assert alt.exists() is False
    assert jung.exists() is True


def test_prune_gfs_taegliche_woechentliche_monatliche_verduennung(tmp_path, capsys):
    """prune-gfs Subcommand: neuestes Backup pro Tag/Woche/Monat behalten.

    Spiegelt :func:`test_prune_loescht_alte_backups` (Count) und
    :func:`test_prune_age_loescht_alte_backups` (Zeit) auf die Bucket-Achse.
    Layout: heute + 100 Tage rueckwaerts (je eine Datei), --daily 3
    --weekly 0 --monthly 0 laesst nur die drei jungsten Dateien uebrig.
    """
    import datetime as dt
    backup_dir = tmp_path / "gfs"
    backup_dir.mkdir()
    today = dt.date.today()
    for days_back in range(100):
        stamp = today - dt.timedelta(days=days_back)
        p = (backup_dir /
             f"stonebook_backup_{stamp.strftime('%Y%m%d')}_120000.json.gz")
        p.write_bytes(b"")
    exit_code = main(["prune-gfs", "--backup-dir", str(backup_dir),
                      "--daily", "3", "--weekly", "0", "--monthly", "0"])
    assert exit_code == 0
    remaining = sorted(backup_dir.iterdir())
    assert len(remaining) == 3
    # Die drei juengsten Kalendertage
    for days_back in range(3):
        stamp = today - dt.timedelta(days=days_back)
        expected = f"stonebook_backup_{stamp.strftime('%Y%m%d')}_120000.json.gz"
        assert (backup_dir / expected).exists()


def test_prune_gfs_ignoriert_fremde_dateien(tmp_path, capsys):
    """prune-gfs Subcommand: Dateien ausserhalb des Namensschemas bleiben.

    Spiegelt :func:`test_prune_age_ignoriert_fremde_dateien`.
    """
    import datetime as dt
    backup_dir = tmp_path / "gfsf"
    backup_dir.mkdir()
    alt = backup_dir / "stonebook_backup_19700101_000000.json.gz"
    alt.write_bytes(b"")
    fremd = backup_dir / "notes.md"
    fremd.write_text("nicht angetastet", encoding="utf-8")
    exit_code = main(["prune-gfs", "--backup-dir", str(backup_dir),
                      "--daily", "0", "--weekly", "0", "--monthly", "0"])
    assert exit_code == 0
    assert alt.exists() is False
    assert fremd.exists() is True


def test_prune_age_ignoriert_fremde_dateien(tmp_path, capsys):
    """prune-age Subcommand: Dateien ausserhalb des Namensschemas bleiben.

    Spiegelt :func:`test_prune_loescht_alte_backups`: fremde Dateien
    (README.txt, Backups eines anderen Schemas) werden nicht angefasst.
    """
    backup_dir = tmp_path / "pagef"
    backup_dir.mkdir()
    alt = backup_dir / "stonebook_backup_19700101_000000.json.gz"
    alt.write_bytes(b"")
    fremd = backup_dir / "notes.md"
    fremd.write_text("nicht angetastet", encoding="utf-8")
    exit_code = main(["prune-age", "--backup-dir", str(backup_dir),
                      "--max-age-days", "30"])
    assert exit_code == 0
    assert alt.exists() is False
    assert fremd.exists() is True


def test_write_fehlende_db_exit_2(tmp_path, capsys):
    exit_code = main(["write",
                      "--backup-dir", str(tmp_path / "x"),
                      "--db", str(tmp_path / "fehlt.sqlite3")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "DB-Datei fehlt" in err


def test_stats_zeigt_report(migrated_db, tmp_path, capsys):
    """stats Subcommand: Ordner mit zwei Backups liefert count/bytes/Stempel.

    Spiegelt :func:`test_inspect_zeigt_counts` auf die Ordner-Achse
    (statt einer einzelnen Backup-Datei): der Report fasst den ganzen
    Backup-Ordner numerisch zusammen. Sowohl Grenzstempel (aeltestes /
    juengstes Backup) als auch Gesamt-Bytes werden geprueft.
    """
    backup_dir = tmp_path / "sd"
    main(["write", "--backup-dir", str(backup_dir), "--db", str(migrated_db)])
    _ = capsys.readouterr()  # Pfad-Output verwerfen
    # Zweites Backup, damit oldest_stamp und newest_stamp unterscheidbar sind.
    time.sleep(1.1)
    main(["write", "--backup-dir", str(backup_dir), "--db", str(migrated_db)])
    _ = capsys.readouterr()

    exit_code = main(["stats", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["count"] == 2
    assert info["total_bytes"] > 0
    assert info["oldest_stamp"] is not None
    assert info["newest_stamp"] is not None
    assert info["oldest_stamp"] <= info["newest_stamp"]


def test_stats_leerer_ordner_liefert_null_report(tmp_path, capsys):
    """stats Subcommand: nicht existierender Ordner liefert Null-Report, Exit 0.

    Spiegelt :func:`test_backup_directory_stats_leerer_und_nichtexistierender_ordner`
    auf der CLI-Achse - kein Crash, Cron-Reporter kann den Report vor der
    ersten Backup-Schreibe machen ohne Exit-Code-Sonderbehandlung.
    """
    exit_code = main(["stats", "--backup-dir", str(tmp_path / "nichts")])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {
        "count": 0,
        "total_bytes": 0,
        "oldest_stamp": None,
        "newest_stamp": None,
    }


def test_restore_latest_waehlt_juengstes_backup(migrated_db, tmp_path, capsys):
    """restore-latest Subcommand: das juengste Backup wird ausgewaehlt und eingespielt.

    Spiegelt :func:`test_write_list_und_restore_round_trip` auf die Auto-
    Auswahl-Achse: der User muss nicht den Datei-Pfad tippen, sondern nur
    den Ordner - der Restore geht auf das juengste Backup (Filename-
    Stempel). Die Counts auf stdout muessen identisch zum ``restore``-
    Subcommand sein (spiegelt das JSON-Ausgabeformat), damit Downstream-
    Auswerter beide CLI-Pfade uniform verarbeiten koennen. Der ausgewaehlte
    Pfad steht auf stderr als informativer Hinweis.
    """
    backup_dir = tmp_path / "backups"
    # Zwei Backups schreiben; das juengste soll gewaehlt werden.
    main(["write", "--backup-dir", str(backup_dir),
          "--db", str(migrated_db), "--keep", "5"])
    _ = capsys.readouterr()  # Pfad-Ausgabe verwerfen
    # Zweites Backup mit spaeterer Zeit (write_rotated_backup ohne now nutzt
    # datetime.now(), das minimal spaeter ist als das erste Backup)
    time.sleep(1.1)
    main(["write", "--backup-dir", str(backup_dir),
          "--db", str(migrated_db), "--keep", "5"])
    zweites = Path(capsys.readouterr().out.strip())

    new_db = tmp_path / "restored.sqlite3"
    exit_code = main(["restore-latest",
                      "--backup-dir", str(backup_dir),
                      "--db", str(new_db)])
    assert exit_code == 0
    captured = capsys.readouterr()
    counts = json.loads(captured.out)
    assert counts == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}
    # Der informative Hinweis auf stderr enthaelt den ausgewaehlten Pfad
    assert str(zweites) in captured.err


def test_restore_latest_leerer_ordner_exit_2(tmp_path, capsys):
    """restore-latest ohne Backup im Ordner: Exit 2, klarer Fehlerhinweis.

    Spiegelt :func:`test_write_fehlende_db_exit_2` auf die Auto-Auswahl-
    Achse: ohne verfuegbares Backup ist ``restore-latest`` semantisch
    identisch zu ``restore`` mit fehlender Datei - der User muss sofort
    sehen, warum kein Restore stattfand, statt dass ein leerer Restore
    stillschweigend durchlaeuft. Exit 2 spiegelt die uebrigen
    "fehlende Grundvoraussetzung"-Faelle (fehlende DB in write/compare-db,
    existierende Ziel-DB ohne --force in restore).
    """
    backup_dir = tmp_path / "leer"
    backup_dir.mkdir()
    exit_code = main(["restore-latest",
                      "--backup-dir", str(backup_dir),
                      "--db", str(tmp_path / "neu.sqlite3")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "Kein Backup" in err


def test_restore_latest_fordert_force_bei_existierender_db(migrated_db, tmp_path, capsys):
    """restore-latest ueberschreibt keine existierende Ziel-DB ohne --force.

    Spiegelt :func:`test_restore_fordert_force_bei_existierender_db` auf
    die Auto-Auswahl-Achse: die Force-Semantik ist identisch zum ``restore``-
    Subcommand, damit User nicht per Zufall ihre laufende DB durch ein
    Backup ueberschreiben, nur weil sie sich in einem Automations-Script
    auf ``restore-latest`` verlassen. Mit --force geht es dann durch
    (spiegelt ``restore --force``).
    """
    backup_dir = tmp_path / "fr"
    main(["write", "--backup-dir", str(backup_dir),
          "--db", str(migrated_db)])
    _ = capsys.readouterr()

    existing = tmp_path / "existing.sqlite3"
    existing.write_bytes(b"placeholder")
    exit_code = main(["restore-latest",
                      "--backup-dir", str(backup_dir),
                      "--db", str(existing)])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "existiert" in err

    exit_code = main(["restore-latest",
                      "--backup-dir", str(backup_dir),
                      "--db", str(existing), "--force"])
    assert exit_code == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts["objects"] == 546
