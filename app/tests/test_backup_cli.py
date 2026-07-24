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


def test_gfs_preview_listet_prune_kandidaten_ohne_zu_loeschen(tmp_path, capsys):
    """gfs-preview Subcommand: prune-gfs-Kandidaten listen, ohne zu loeschen.

    Spiegelt :func:`test_stale_listet_alte_backups_ohne_zu_loeschen` (Zeit-Achse)
    und :func:`test_excess_listet_alte_backups_ohne_zu_loeschen` (Count-Achse)
    auf die Bucket-Achse: gleicher Aufbau wie :func:`test_prune_gfs_...`,
    aber ``gfs-preview`` ist der check-Modus - Dateien bleiben, Kandidaten
    werden nur ausgegeben. Exit-Code 1 bei Fund (spiegelt stale/excess).
    """
    import datetime as dt
    backup_dir = tmp_path / "gfsp"
    backup_dir.mkdir()
    today = dt.date.today()
    for days_back in range(10):
        stamp = today - dt.timedelta(days=days_back)
        p = (backup_dir /
             f"stonebook_backup_{stamp.strftime('%Y%m%d')}_120000.json.gz")
        p.write_bytes(b"")

    exit_code = main(["gfs-preview", "--backup-dir", str(backup_dir),
                      "--daily", "3", "--weekly", "0", "--monthly", "0"])

    assert exit_code == 1
    out = capsys.readouterr().out
    # Die aeltesten 7 Kalendertage waeren die Prune-Kandidaten.
    for days_back in range(3, 10):
        stamp = today - dt.timedelta(days=days_back)
        assert stamp.strftime("%Y%m%d") in out
    # Die juengsten 3 Kalendertage bleiben ausserhalb der Preview-Liste.
    for days_back in range(3):
        stamp = today - dt.timedelta(days=days_back)
        assert stamp.strftime("%Y%m%d") not in out
    # Nichts geloescht.
    assert len(list(backup_dir.iterdir())) == 10


def test_gfs_preview_ohne_kandidaten_exit_0(tmp_path, capsys):
    """gfs-preview Subcommand: nichts zu prunen -> keine Ausgabe, Exit 0.

    Cron-Reporter-Pfad: gruen bedeutet leere Ausgabe und Exit 0. Kein
    Rausch-Log fuer "alles im Bucket". Spiegelt
    :func:`test_stale_ohne_kandidaten_exit_0` /
    :func:`test_excess_ohne_kandidaten_exit_0` auf die Bucket-Achse.
    """
    import datetime as dt
    backup_dir = tmp_path / "gfspf"
    backup_dir.mkdir()
    today = dt.date.today()
    p = (backup_dir /
         f"stonebook_backup_{today.strftime('%Y%m%d')}_120000.json.gz")
    p.write_bytes(b"")

    exit_code = main(["gfs-preview", "--backup-dir", str(backup_dir),
                      "--daily", "7", "--weekly", "4", "--monthly", "12"])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert p.exists() is True


def test_gfs_preview_ignoriert_fremde_dateien(tmp_path, capsys):
    """gfs-preview Subcommand ignoriert Fremd-Dateien im Backup-Ordner.

    Spiegelt :func:`test_prune_gfs_ignoriert_fremde_dateien`: nur Dateien
    nach dem Backup-Namensschema koennen als Prune-Kandidat auftauchen.
    """
    backup_dir = tmp_path / "gfspx"
    backup_dir.mkdir()
    alt = backup_dir / "stonebook_backup_19700101_000000.json.gz"
    alt.write_bytes(b"")
    fremd = backup_dir / "notes.md"
    fremd.write_text("nicht angetastet", encoding="utf-8")

    exit_code = main(["gfs-preview", "--backup-dir", str(backup_dir),
                      "--daily", "0", "--weekly", "0", "--monthly", "0"])

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "19700101" in out
    assert "notes.md" not in out
    # Nichts geloescht.
    assert alt.exists() is True
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


def test_stale_listet_alte_backups_ohne_zu_loeschen(tmp_path, capsys):
    """stale Subcommand: alte Backups werden gelistet, Files bleiben da.

    Spiegelt :func:`test_prune_age_loescht_alte_backups`: gleicher Aufbau
    (1970-Stempel + heute-Stempel, Cutoff 30 Tage), aber ``stale`` ist der
    check-Modus - Dateien bleiben, Kandidaten werden nur ausgegeben.
    Exit-Code 1 bei Fund (spiegelt fts-check/check).
    """
    backup_dir = tmp_path / "s"
    backup_dir.mkdir()
    alt = backup_dir / "stonebook_backup_19700101_000000.json.gz"
    alt.write_bytes(b"")
    today = time.strftime("%Y%m%d")
    jung = backup_dir / f"stonebook_backup_{today}_120000.json.gz"
    jung.write_bytes(b"")

    exit_code = main(["stale", "--backup-dir", str(backup_dir),
                      "--max-age-days", "30"])

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "19700101" in out
    assert today not in out
    # Nichts wurde geloescht:
    assert alt.exists() is True
    assert jung.exists() is True


def test_stale_ohne_kandidaten_exit_0(tmp_path, capsys):
    """stale Subcommand: nichts stale -> keine Ausgabe, Exit 0.

    Cron-Reporter-Pfad: gruen bedeutet leere Ausgabe und Exit 0. Kein
    Rausch-Log fuer "alles frisch".
    """
    backup_dir = tmp_path / "sf"
    backup_dir.mkdir()
    today = time.strftime("%Y%m%d")
    jung = backup_dir / f"stonebook_backup_{today}_120000.json.gz"
    jung.write_bytes(b"")

    exit_code = main(["stale", "--backup-dir", str(backup_dir),
                      "--max-age-days", "30"])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert jung.exists() is True


def test_excess_listet_alte_backups_ohne_zu_loeschen(tmp_path, capsys):
    """excess Subcommand: aeltere Backups jenseits keep werden gelistet, Files bleiben da.

    Spiegelt :func:`test_stale_listet_alte_backups_ohne_zu_loeschen` auf
    die Count-Achse: statt Cutoff nach Alter jetzt Cutoff nach
    Anzahl. Vier Backups mit unterschiedlichen Stempeln, ``--keep 2``
    listet die zwei aeltesten (die :func:`_cmd_prune` loeschen wuerde),
    ohne etwas zu bewegen. Exit-Code 1 bei Fund (spiegelt
    stale/fts-check/check).
    """
    backup_dir = tmp_path / "e"
    backup_dir.mkdir()
    stamps = ["19700101_000000", "20200101_000000",
              "20230101_000000", "20240101_000000"]
    paths = []
    for s in stamps:
        p = backup_dir / f"stonebook_backup_{s}.json.gz"
        p.write_bytes(b"")
        paths.append(p)

    exit_code = main(["excess", "--backup-dir", str(backup_dir),
                      "--keep", "2"])

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "19700101" in out
    assert "20200101" in out
    assert "20230101" not in out
    assert "20240101" not in out
    for p in paths:
        assert p.exists() is True


def test_excess_ohne_kandidaten_exit_0(tmp_path, capsys):
    """excess Subcommand: <= keep Backups -> keine Ausgabe, Exit 0.

    Cron-Reporter-Pfad: gruen bedeutet leere Ausgabe und Exit 0. Kein
    Rausch-Log fuer "unter der Grenze".
    """
    backup_dir = tmp_path / "ef"
    backup_dir.mkdir()
    for s in ("20230101_000000", "20240101_000000"):
        (backup_dir / f"stonebook_backup_{s}.json.gz").write_bytes(b"")

    exit_code = main(["excess", "--backup-dir", str(backup_dir),
                      "--keep", "5"])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_excess_ignoriert_fremde_dateien(tmp_path, capsys):
    """excess Subcommand ignoriert Fremd-Dateien im Backup-Ordner.

    Spiegelt :func:`test_prune_ignoriert_fremde_dateien` /
    :func:`test_stale_.*ignoriert.*` : nur ``stonebook_backup_*.json[.gz]``
    zaehlt fuer die Grenze, die Fremd-Datei bleibt garantiert erhalten und
    darf die keep-Zaehlung nicht verschieben.
    """
    backup_dir = tmp_path / "ex"
    backup_dir.mkdir()
    alt = backup_dir / "stonebook_backup_19700101_000000.json.gz"
    alt.write_bytes(b"")
    jung = backup_dir / "stonebook_backup_20240101_000000.json.gz"
    jung.write_bytes(b"")
    fremd = backup_dir / "README.txt"
    fremd.write_text("nicht ein Backup", encoding="utf-8")

    exit_code = main(["excess", "--backup-dir", str(backup_dir),
                      "--keep", "1"])

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "19700101" in out
    assert "20240101" not in out
    assert "README" not in out
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
        "average_bytes": None,
        "median_bytes": None,
        "min_bytes": None,
        "max_bytes": None,
        "range_bytes": None,
        "stddev_bytes": None,
        "variationskoeffizient_bytes_prozent": None,
        "oldest_stamp": None,
        "newest_stamp": None,
        "days_span": None,
        "average_gap_days": None,
        "median_gap_days": None,
        "min_gap_days": None,
        "max_gap_days": None,
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


def test_latest_druckt_juengsten_backup_pfad(tmp_path, capsys):
    """latest Subcommand: druckt den Pfad zum juengsten Backup nach Filename-Stempel.

    Spiegelt :func:`test_write_list_und_restore_round_trip` (list) auf den
    Ein-Datei-Fall: waehrend ``list`` alle Backup-Pfade aufsteigend druckt,
    druckt ``latest`` genau den Pfad zum juengsten Backup. Ordner mit
    mehreren Backups zeigt den mit dem juengsten Filename-Stempel; die
    Auswahl basiert auf dem Dateinamen (nicht mtime/ctime), damit vom NAS
    kopierte Backups ihr originales Alter behalten - spiegelt
    :func:`prune_backups_by_age`- und :func:`latest_backup`-Konvention.
    """
    backup_dir = tmp_path / "lt"
    backup_dir.mkdir()
    # Drei Pseudo-Backups mit unterschiedlichem Zeitstempel.
    paths = []
    for stamp in ("20240101_000000", "20240102_000000", "20240103_000000"):
        p = backup_dir / f"stonebook_backup_{stamp}.json.gz"
        p.write_bytes(b"")
        paths.append(p)
    exit_code = main(["latest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = Path(capsys.readouterr().out.strip())
    # Das juengste (2024-01-03) ist der neueste Filename-Stempel.
    assert out == paths[2]


def test_latest_leerer_ordner_exit_2(tmp_path, capsys):
    """latest Subcommand: leerer/fehlender Ordner -> Exit 2 mit Fehlerhinweis.

    Spiegelt :func:`test_restore_latest_leerer_ordner_exit_2` auf die
    read-only Auto-Auswahl-Achse: ohne verfuegbares Backup ist ``latest``
    semantisch undefiniert, der Aufrufer soll den Fehler ohne stille
    Zeichenkette abfangen koennen (sonst laeuft die Shell-Kette bei
    fehlendem Backup mit leerem Pfad weiter und erwischt still das
    falsche Ziel).
    """
    exit_code = main(["latest", "--backup-dir", str(tmp_path / "nichts")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "Kein Backup" in err


def test_latest_ignoriert_fremde_dateien(tmp_path, capsys):
    """latest Subcommand: fremde Dateien im Ordner werden nicht als Backup betrachtet.

    Spiegelt :func:`test_prune_ignoriert_fremde_dateien` auf die
    read-only Achse: die Auto-Auswahl folgt exakt dem Filename-Schema
    von :func:`write_rotated_backup`, sodass eine README oder ein
    fremder Export im Backup-Ordner nicht faelschlich als "juengstes
    Backup" gedruckt wird.
    """
    backup_dir = tmp_path / "mix"
    backup_dir.mkdir()
    (backup_dir / "stonebook_backup_20240101_000000.json.gz").write_bytes(b"")
    (backup_dir / "README.md").write_bytes(b"Backup-Ordner\n")
    (backup_dir / "export.csv").write_bytes(b"id,name\n")
    (backup_dir / "stonebook_backup_20240102_000000.json.gz").write_bytes(b"")
    exit_code = main(["latest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("stonebook_backup_20240102_000000.json.gz")


def test_oldest_druckt_aeltesten_backup_pfad(tmp_path, capsys):
    """oldest Subcommand: druckt den Pfad zum aeltesten Backup nach Filename-Stempel.

    Spiegelt :func:`test_latest_druckt_juengsten_backup_pfad` auf den
    Gegen-Endpunkt der Backup-Halde. Ordner mit mehreren Backups zeigt
    den mit dem aeltesten Filename-Stempel; damit hat der Aufrufer einen
    direkten Anker fuer Prune-Preview und historische Diff-Analysen
    (``compare $(oldest) $(latest)``).
    """
    backup_dir = tmp_path / "ol"
    backup_dir.mkdir()
    paths = []
    for stamp in ("20240101_000000", "20240102_000000", "20240103_000000"):
        p = backup_dir / f"stonebook_backup_{stamp}.json.gz"
        p.write_bytes(b"")
        paths.append(p)
    exit_code = main(["oldest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = Path(capsys.readouterr().out.strip())
    # Das aelteste (2024-01-01) ist der frueheste Filename-Stempel.
    assert out == paths[0]


def test_oldest_leerer_ordner_exit_2(tmp_path, capsys):
    """oldest Subcommand: leerer/fehlender Ordner -> Exit 2 mit Fehlerhinweis.

    Spiegelt :func:`test_latest_leerer_ordner_exit_2` auf den Gegen-Endpunkt.
    """
    exit_code = main(["oldest", "--backup-dir", str(tmp_path / "nichts")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "Kein Backup" in err


def test_oldest_ignoriert_fremde_dateien(tmp_path, capsys):
    """oldest Subcommand: fremde Dateien im Ordner werden nicht als Backup betrachtet.

    Spiegelt :func:`test_latest_ignoriert_fremde_dateien` auf den
    Gegen-Endpunkt.
    """
    backup_dir = tmp_path / "mix"
    backup_dir.mkdir()
    (backup_dir / "stonebook_backup_20240101_000000.json.gz").write_bytes(b"")
    (backup_dir / "README.md").write_bytes(b"Backup-Ordner\n")
    (backup_dir / "stonebook_backup_20240102_000000.json.gz").write_bytes(b"")
    exit_code = main(["oldest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("stonebook_backup_20240101_000000.json.gz")


def test_largest_druckt_groessten_backup_pfad(tmp_path, capsys):
    """largest Subcommand: druckt den Pfad zum groessten Backup (Bytes auf Platte).

    Spiegelt :func:`test_latest_druckt_juengsten_backup_pfad` auf die
    Volume-Achse: waehrend ``latest`` das juengste Backup nach Filename-
    Stempel liefert, liefert ``largest`` das groesste Backup nach
    ``st_size``. Drei Backups mit unterschiedlichen Groessen; das mit
    dem hoechsten Byte-Count wird gedruckt.
    """
    backup_dir = tmp_path / "lg"
    backup_dir.mkdir()
    # Drei Backups mit unterschiedlicher Groesse (Byte-Count spielt hier
    # die Rolle des Sortier-Schluessels, nicht der Filename-Stempel).
    (backup_dir / "stonebook_backup_20240101_000000.json.gz").write_bytes(b"x" * 100)
    (backup_dir / "stonebook_backup_20240102_000000.json.gz").write_bytes(b"x" * 500)
    (backup_dir / "stonebook_backup_20240103_000000.json.gz").write_bytes(b"x" * 200)
    exit_code = main(["largest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = Path(capsys.readouterr().out.strip())
    # Groesstes Backup (500 Bytes) ist das vom 2024-01-02, nicht das juengste.
    assert out.name == "stonebook_backup_20240102_000000.json.gz"


def test_largest_leerer_ordner_exit_2(tmp_path, capsys):
    """largest Subcommand: leerer/fehlender Ordner -> Exit 2 mit Fehlerhinweis.

    Spiegelt :func:`test_latest_leerer_ordner_exit_2` auf die Volume-Achse.
    """
    exit_code = main(["largest", "--backup-dir", str(tmp_path / "nichts")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "Kein Backup" in err


def test_largest_ignoriert_fremde_dateien(tmp_path, capsys):
    """largest Subcommand: fremde Dateien im Ordner werden nicht betrachtet.

    Auch wenn eine fremde Datei groesser ist als jedes echte Backup,
    liefert ``largest`` immer nur einen Pfad, der zum
    :func:`write_rotated_backup`-Schema passt - spiegelt
    :func:`test_latest_ignoriert_fremde_dateien` auf die Volume-Achse.
    """
    backup_dir = tmp_path / "mix"
    backup_dir.mkdir()
    (backup_dir / "stonebook_backup_20240101_000000.json.gz").write_bytes(b"x" * 100)
    (backup_dir / "stonebook_backup_20240102_000000.json.gz").write_bytes(b"x" * 200)
    # Fremde Datei mit viel mehr Bytes darf nicht als "groesstes Backup"
    # ausgegeben werden - der Ordner-Filter ueber _BACKUP_RE greift schon
    # in list_backups.
    (backup_dir / "haufen_daten.bin").write_bytes(b"x" * 100_000)
    exit_code = main(["largest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("stonebook_backup_20240102_000000.json.gz")


def test_smallest_druckt_kleinsten_backup_pfad(tmp_path, capsys):
    """smallest Subcommand: druckt den Pfad zum kleinsten Backup (Bytes auf Platte).

    Spiegelt :func:`test_largest_druckt_groessten_backup_pfad` auf den
    Gegen-Endpunkt der Volume-Achse - geeignet als Verdachts-Anker fuer
    abgebrochene Schreiben oder Backups aus fruehen Sammlungs-Phasen.
    """
    backup_dir = tmp_path / "sm"
    backup_dir.mkdir()
    (backup_dir / "stonebook_backup_20240101_000000.json.gz").write_bytes(b"x" * 100)
    (backup_dir / "stonebook_backup_20240102_000000.json.gz").write_bytes(b"x" * 500)
    (backup_dir / "stonebook_backup_20240103_000000.json.gz").write_bytes(b"x" * 200)
    exit_code = main(["smallest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = Path(capsys.readouterr().out.strip())
    # Kleinstes Backup (100 Bytes) ist das vom 2024-01-01, nicht das aelteste
    # zufaellig - hier stimmt beides zusammen, aber der Sortier-Schluessel
    # ist Byte-Count.
    assert out.name == "stonebook_backup_20240101_000000.json.gz"


def test_smallest_leerer_ordner_exit_2(tmp_path, capsys):
    """smallest Subcommand: leerer/fehlender Ordner -> Exit 2 mit Fehlerhinweis.

    Spiegelt :func:`test_largest_leerer_ordner_exit_2`.
    """
    exit_code = main(["smallest", "--backup-dir", str(tmp_path / "nichts")])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "Kein Backup" in err


def test_smallest_ignoriert_fremde_dateien(tmp_path, capsys):
    """smallest Subcommand: fremde Dateien im Ordner werden nicht betrachtet.

    Auch wenn eine fremde Datei kleiner ist (z.B. leere README) als jedes
    echte Backup, liefert ``smallest`` immer nur einen Pfad, der zum
    :func:`write_rotated_backup`-Schema passt - spiegelt
    :func:`test_largest_ignoriert_fremde_dateien` auf den Gegen-Endpunkt.
    """
    backup_dir = tmp_path / "mix"
    backup_dir.mkdir()
    (backup_dir / "stonebook_backup_20240101_000000.json.gz").write_bytes(b"x" * 500)
    (backup_dir / "stonebook_backup_20240102_000000.json.gz").write_bytes(b"x" * 200)
    # Fremde Datei mit weniger Bytes darf nicht als "kleinstes Backup"
    # ausgegeben werden.
    (backup_dir / "leere_notiz.txt").write_bytes(b"")
    exit_code = main(["smallest", "--backup-dir", str(backup_dir)])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("stonebook_backup_20240102_000000.json.gz")


def _prepend_utf8_bom(path: Path) -> None:
    """Prependet ``EF BB BF`` an eine plain-JSON-Backup-Datei.

    Simuliert eine externe Bearbeitungs-Kette, die das BOM einfuegt:
    ``Backup in Notepad oeffnen -> Speichern`` schreibt auf Windows 11
    per Default UTF-8-BOM voran. Wird von den BOM-Toleranz-Tests fuer
    ``inspect`` / ``validate`` / ``restore`` und ``compare`` verwendet,
    damit die BOM-Toleranz nicht nur auf der plain-JSON-Achse, sondern
    auch fuer alle Backup-Lese-Pfade verifiziert ist. Die urspruengliche
    JSON-Semantik bleibt intakt (nur das Byte-Level-BOM-Praefix aendert
    sich); der :func:`_read_text`-``utf-8-sig``-Fix strippt es beim
    Lesen transparent.
    """
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return
    path.write_bytes(b"\xef\xbb\xbf" + raw)


def test_restore_toleriert_utf8_bom_prefix(migrated_db, tmp_path, capsys):
    """Eine extern mit BOM re-gespeicherte Backup-Datei bleibt wiederherstellbar.

    Vor dem ``utf-8-sig``-Fix in :func:`_read_text` haette
    :func:`json.loads` mit ``JSONDecodeError: Unexpected UTF-8 BOM
    (decode using utf-8-sig)`` abgebrochen und der Restore verweigert,
    obwohl die Daten korrekt sind. Sammler-Workflow: Backup zur
    Sichtung im Editor oeffnen, versehentlich speichern (Notepad-
    Default-Encoding auf Windows 11 = UTF-8 mit BOM), spaeter Restore
    versuchen -> vor dem Fix Fehlermeldung "Backup-Datei ist kein
    gueltiges JSON", nach dem Fix normaler Restore.
    """
    backup_dir = tmp_path / "backup_bom"
    exit_code = main(["write", "--backup-dir", str(backup_dir),
                      "--db", str(migrated_db), "--no-compress"])
    assert exit_code == 0
    written = Path(capsys.readouterr().out.strip())
    assert written.suffix == ".json"
    _prepend_utf8_bom(written)
    assert written.read_bytes().startswith(b"\xef\xbb\xbf")

    new_db = tmp_path / "restored_bom.sqlite3"
    exit_code = main(["restore", str(written), "--db", str(new_db)])
    assert exit_code == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}


def test_restore_toleriert_utf8_bom_prefix_gzip(migrated_db, tmp_path, capsys):
    """Auch im gzip-Fall darf ein BOM im dekomprimierten JSON-Stream nicht crashen.

    Symmetrisch zu :func:`test_restore_toleriert_utf8_bom_prefix` auf
    den gzip-Zweig von :func:`_read_text`. Das BOM sitzt hier innerhalb
    des komprimierten Streams (nicht am Anfang der ``.gz``-Datei),
    kommt aber beim Dekomprimieren als U+FEFF-Praefix im Text-Stream
    an - ohne den ``utf-8-sig``-Codec beim ``gzip.open`` bleibt der
    BOM als U+FEFF stehen und :func:`json.loads` crasht identisch zum
    plain-JSON-Fall. Realistisch: Sammler entpackt/re-komprimiert das
    Backup mit einem GUI-Tool, das intern durch einen BOM-hinzufuegen-
    den Editor laeuft (7-Zip mit einer Editor-Pipeline oder ein
    Windows-Kontextmenue-Handler).
    """
    import gzip as _gzip

    backup_dir = tmp_path / "backup_bom_gz"
    exit_code = main(["write", "--backup-dir", str(backup_dir),
                      "--db", str(migrated_db)])
    assert exit_code == 0
    written = Path(capsys.readouterr().out.strip())
    assert written.suffix == ".gz"
    # gzip -> decompress -> BOM voranstellen -> re-gzip: simuliert das
    # oben beschriebene externe Bearbeitungs-Szenario auf der Byte-Ebene.
    with _gzip.open(written, "rb") as f:
        decompressed = f.read()
    with _gzip.open(written, "wb") as f:
        f.write(b"\xef\xbb\xbf" + decompressed)

    new_db = tmp_path / "restored_bom_gz.sqlite3"
    exit_code = main(["restore", str(written), "--db", str(new_db)])
    assert exit_code == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts == {"objects": 546, "images": 63, "aliases": 54, "ki_analysen": 0}


def test_inspect_und_validate_tolerieren_utf8_bom_prefix(
        migrated_db, tmp_path, capsys):
    """``inspect`` und ``validate`` bleiben stabil, wenn die Datei ein BOM hat.

    Spiegelt :func:`test_restore_toleriert_utf8_bom_prefix` auf die
    Lese-/Report-Achse: der User sichtet ein extern re-gespeichertes
    Backup vor dem Restore, und ohne den ``utf-8-sig``-Fix wuerden
    beide Kommandos mit ``ValueError: Backup-Datei ist kein gueltiges
    JSON`` abbrechen, obwohl die Datei semantisch korrekt ist.
    """
    backup_dir = tmp_path / "inspect_bom"
    exit_code = main(["write", "--backup-dir", str(backup_dir),
                      "--db", str(migrated_db), "--no-compress"])
    assert exit_code == 0
    written = Path(capsys.readouterr().out.strip())
    _prepend_utf8_bom(written)

    exit_code = main(["inspect", str(written)])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    # Ankert die Basis-Struktur der Inspect-Ausgabe (counts-Block); die
    # exakten Zahlen kommen aus der migrierten Referenz-DB.
    assert info["counts"]["objects"] == 546

    exit_code = main(["validate", str(written)])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["ok"] is True
