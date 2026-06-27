"""CLI fuer die Wartung der DB (size/check/vacuum)."""
import json

from stonebook.db.database import connect as connect_check, open_db
from stonebook.db.maintenance_cli import main
from stonebook.db.repository import ObjectRepo


def _seed_objects(c, n: int) -> None:
    repo = ObjectRepo(c)
    for i in range(1, n + 1):
        repo.create(f"OBJ_{i:04d}", Mineral_Primaer="Quarz")


def test_size_text(tmp_path, capsys):
    db_file = tmp_path / "s.sqlite3"
    open_db(db_file).close()
    exit_code = main(["size", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Logisch:" in out
    assert "Datei (mit WAL):" in out
    assert "Free-Pages:" in out


def test_size_json(tmp_path, capsys):
    db_file = tmp_path / "sj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["size", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["db_file"] == str(db_file)
    assert info["logical_bytes"] > 0
    assert info["file_bytes"] > 0
    assert info["free_pages"] == 0


def test_check_text_ok(tmp_path, capsys):
    db_file = tmp_path / "c.sqlite3"
    open_db(db_file).close()
    exit_code = main(["check", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_check_json_ok(tmp_path, capsys):
    db_file = tmp_path / "cj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["check", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True, "messages": []}


def test_deepcheck_text_ok(tmp_path, capsys):
    """deepcheck Subcommand: leere DB → OK + Exit 0 (spiegelt check)."""
    db_file = tmp_path / "dc.sqlite3"
    open_db(db_file).close()
    exit_code = main(["deepcheck", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_deepcheck_json_ok(tmp_path, capsys):
    """deepcheck Subcommand JSON: leere DB → ok=True, messages=[] (spiegelt check)."""
    db_file = tmp_path / "dcj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["deepcheck", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True, "messages": []}


def test_fkcheck_text_ok(tmp_path, capsys):
    """fkcheck Subcommand: leere DB → OK + Exit 0 (spiegelt check)."""
    db_file = tmp_path / "fkc.sqlite3"
    open_db(db_file).close()
    exit_code = main(["fkcheck", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_fkcheck_json_ok(tmp_path, capsys):
    """fkcheck Subcommand JSON: leere DB → ok=True, violations=[] (spiegelt check)."""
    db_file = tmp_path / "fkcj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["fkcheck", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True, "violations": []}


def test_fkcheck_meldet_orphan(tmp_path, capsys):
    """fkcheck Subcommand: durch FK-OFF eingefuegter Orphan → Exit 1 + Verletzung im Output.

    Spiegelt das ``foreign_key_check_orphan_image_erkannt``-Pattern aus
    :mod:`tests.test_maintenance` auf den CLI-Pfad: Orphan im JSON-Output und
    Exit-Code 1 (geeignet fuer Cron/CI, parallel zum quick_check).
    """
    db_file = tmp_path / "fk_orph_cli.sqlite3"
    c = open_db(db_file)
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        ("OBJ_0099_ghost", "Kamera", "objects/OBJ_0099/foto.jpg"),
    )
    c.commit()
    c.close()
    exit_code = main(["fkcheck", "--db", str(db_file), "--json"])
    assert exit_code == 1
    info = json.loads(capsys.readouterr().out)
    assert info["ok"] is False
    assert len(info["violations"]) == 1
    v = info["violations"][0]
    assert v["table"] == "images"
    assert v["parent_table"] == "objects"
    assert isinstance(v["rowid"], int)


def test_dupimg_text_keine_dubletten(tmp_path, capsys):
    """dupimg Subcommand: leere DB → OK + Exit 0 (spiegelt check)."""
    db_file = tmp_path / "di_empty.sqlite3"
    open_db(db_file).close()
    exit_code = main(["dupimg", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_dupimg_json_keine_dubletten(tmp_path, capsys):
    """dupimg Subcommand JSON: leere DB → groups=[] (Pendant zu fkcheck-OK-Pfad)."""
    db_file = tmp_path / "di_empty_j.sqlite3"
    open_db(db_file).close()
    exit_code = main(["dupimg", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"groups": []}


def test_dupimg_meldet_gruppen(tmp_path, capsys):
    """dupimg Subcommand: zwei Bilder mit gleichem SHA-256 → Treffer im JSON-Output.

    Spiegelt das Bibliotheks-Pendant test_find_duplicate_image_sha256 auf den
    CLI-Pfad: Hash und sortierte ID-Liste pro Gruppe in der JSON-Form, Exit 0
    (Dubletten sind nicht zwingend ein Fehler - der Caller bewertet).
    """
    db_file = tmp_path / "di_dup.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path, sha256) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg", "aaaa"),
            ("OBJ_0002", "Kamera", "b.jpg", "aaaa"),
            ("OBJ_0001", "Mikroskop", "c.jpg", "bbbb"),
        ],
    )
    c.commit()
    c.close()
    exit_code = main(["dupimg", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert len(info["groups"]) == 1
    g = info["groups"][0]
    assert g["sha256"] == "aaaa"
    assert len(g["image_ids"]) == 2
    assert g["image_ids"] == sorted(g["image_ids"])


def test_dupimg_text_meldet_gruppen(tmp_path, capsys):
    """dupimg Subcommand Text-Output: Gruppen-Anzahl + Hash + IDs sichtbar.

    Spiegelt das JSON-Test-Setup auf die textuelle Variante (Cron-/Console-
    Inspektion ohne JSON-Parser).
    """
    db_file = tmp_path / "di_dup_text.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path, sha256) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg", "ffff"),
            ("OBJ_0002", "Kamera", "b.jpg", "ffff"),
        ],
    )
    c.commit()
    c.close()
    exit_code = main(["dupimg", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "1 Dubletten-Gruppe" in out
    assert "ffff" in out


def test_cleanup_text_keine_orphans(tmp_path, capsys):
    """cleanup Subcommand: leere DB → OK + Exit 0 (parallel zu dupimg/check)."""
    db_file = tmp_path / "cl_empty.sqlite3"
    open_db(db_file).close()
    exit_code = main(["cleanup", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "geloescht: 0" in out


def test_cleanup_json_keine_orphans(tmp_path, capsys):
    """cleanup Subcommand JSON: leere DB → alle counts 0 (Pendant zu fkcheck-OK-Pfad)."""
    db_file = tmp_path / "cl_empty_j.sqlite3"
    open_db(db_file).close()
    exit_code = main(["cleanup", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {
        "dry_run": False,
        "orphan_images": 0,
        "orphan_ki_analysen": 0,
        "dangling_aliases": 0,
        "total": 0,
    }


def test_cleanup_loescht_orphan_images(tmp_path, capsys):
    """cleanup Subcommand: durch FK-OFF eingefuegter Orphan wird tatsaechlich geloescht.

    Spiegelt das ``fkcheck_meldet_orphan``-Pattern auf den fix-Pfad: fkcheck
    erkennt, cleanup behebt; nach cleanup ist die Tabelle sauber.
    """
    db_file = tmp_path / "cl_orph.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg"),     # valid
            ("OBJ_0099_ghost", "Kamera", "g.jpg"),  # orphan
            ("OBJ_0099_ghost", "Mikroskop", "g2.jpg"),  # orphan
        ],
    )
    c.commit()
    c.close()
    exit_code = main(["cleanup", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["orphan_images"] == 2
    assert info["orphan_ki_analysen"] == 0
    assert info["dangling_aliases"] == 0
    assert info["total"] == 2
    assert info["dry_run"] is False

    # Verifikation: nur das gueltige Bild bleibt uebrig
    c2 = connect_check(db_file)
    rows = c2.execute("SELECT obj_id, rel_path FROM images ORDER BY rel_path").fetchall()
    c2.close()
    assert [(r[0], r[1]) for r in rows] == [("OBJ_0001", "a.jpg")]


def test_cleanup_dry_run_aendert_nichts(tmp_path, capsys):
    """cleanup --dry-run zaehlt korrekt, mutiert die DB aber nicht.

    Pendant zur fkcheck-Diagnose: spiegelt den ``check`` -> ``fix``-Workflow
    auf die Vorstufe, in der der Sammler die Befunde inspiziert bevor er die
    Loeschung tatsaechlich ausloest.
    """
    db_file = tmp_path / "cl_dry.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        ("OBJ_0099_ghost", "Kamera", "ghost.jpg"),
    )
    c.execute(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES (?, ?)",
        ("OBJ_OLD", "OBJ_MISSING"),
    )
    c.commit()
    c.close()

    exit_code = main(["cleanup", "--db", str(db_file), "--dry-run", "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["dry_run"] is True
    assert info["orphan_images"] == 1
    assert info["dangling_aliases"] == 1
    assert info["total"] == 2

    # Verifikation: nichts wurde tatsaechlich geloescht.
    c2 = connect_check(db_file)
    n_img = c2.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    n_al = c2.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    c2.close()
    assert n_img == 1
    assert n_al == 1


def test_cleanup_text_meldet_loeschungen(tmp_path, capsys):
    """cleanup Subcommand Text-Output: Gesamtsumme + pro-Tabellen-Zeilen sichtbar."""
    db_file = tmp_path / "cl_text.sqlite3"
    c = open_db(db_file)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT INTO ki_analysen (obj_id, modell, antwort_json) VALUES (?, ?, ?)",
        ("OBJ_0099_ghost", "claude-sonnet-4-6", "{}"),
    )
    c.commit()
    c.close()
    exit_code = main(["cleanup", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "FK-Orphans geloescht: 1" in out
    assert "KI-Analysen ohne Objekt:   1" in out


def test_vacuum_text(tmp_path, capsys):
    db_file = tmp_path / "v.sqlite3"
    c = open_db(db_file)
    repo = ObjectRepo(c)
    for i in range(1, 101):
        repo.create(f"OBJ_{i:04d}", Name=f"Name {i}" * 30)
    c.execute("DELETE FROM objects")
    c.commit()
    c.close()
    exit_code = main(["vacuum", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "VACUUM abgeschlossen" in out


def test_vacuum_json(tmp_path, capsys):
    db_file = tmp_path / "vj.sqlite3"
    c = open_db(db_file)
    repo = ObjectRepo(c)
    for i in range(1, 51):
        repo.create(f"OBJ_{i:04d}", Name=f"Name {i}" * 30)
    c.execute("DELETE FROM objects")
    c.commit()
    c.close()
    exit_code = main(["vacuum", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["before_bytes"] >= info["after_bytes"]
    assert info["saved_bytes"] == info["before_bytes"] - info["after_bytes"]


def test_fehlende_db_datei(tmp_path, capsys):
    """Nicht-existente DB → Exit 2 mit Hinweis auf stderr."""
    bad = tmp_path / "nope.sqlite3"
    exit_code = main(["size", "--db", str(bad)])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "fehlt" in err


def test_analyze_text(tmp_path, capsys):
    """analyze-Subcommand: Text-Output enthaelt die Anzahl Stat-Eintraege."""
    db_file = tmp_path / "an.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 10)
    c.close()
    exit_code = main(["analyze", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "ANALYZE abgeschlossen" in out
    assert "Index-Statistik-Eintraege" in out


def test_analyze_json(tmp_path, capsys):
    """analyze-Subcommand JSON: stat_entries >= 0, Exit 0."""
    db_file = tmp_path / "anj.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 10)
    c.close()
    exit_code = main(["analyze", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["stat_entries"] >= 0


def test_analyze_fehlende_db(tmp_path, capsys):
    """analyze auf nicht existierender DB liefert Exit 2 (spiegelt size/check)."""
    bad = tmp_path / "fehlt.sqlite3"
    exit_code = main(["analyze", "--db", str(bad)])
    assert exit_code == 2
    assert "fehlt" in capsys.readouterr().err


def test_optimize_text(tmp_path, capsys):
    """optimize-Subcommand: Text-Output enthaelt PRAGMA-optimize-Meldung."""
    db_file = tmp_path / "opt.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 10)
    c.close()
    exit_code = main(["optimize", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "PRAGMA optimize abgeschlossen" in out
    assert "Index-Statistik-Eintraege" in out


def test_optimize_json(tmp_path, capsys):
    """optimize-Subcommand JSON: stat_entries >= 0, Exit 0."""
    db_file = tmp_path / "optj.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 10)
    c.close()
    exit_code = main(["optimize", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info["stat_entries"] >= 0


def test_optimize_fehlende_db(tmp_path, capsys):
    """optimize auf nicht existierender DB liefert Exit 2 (spiegelt analyze)."""
    bad = tmp_path / "fehlt.sqlite3"
    exit_code = main(["optimize", "--db", str(bad)])
    assert exit_code == 2
    assert "fehlt" in capsys.readouterr().err


def test_fts_check_text_ok(tmp_path, capsys):
    """fts-check Subcommand: leere DB -> OK + Exit 0 (spiegelt check/deepcheck)."""
    db_file = tmp_path / "ftsc.sqlite3"
    open_db(db_file).close()
    exit_code = main(["fts-check", "--db", str(db_file)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_fts_check_json_ok(tmp_path, capsys):
    """fts-check JSON: leere DB -> ok=True, messages=[] (spiegelt deepcheck-Format)."""
    db_file = tmp_path / "ftscj.sqlite3"
    open_db(db_file).close()
    exit_code = main(["fts-check", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True, "messages": []}


def test_fts_check_meldet_inkonsistenz(tmp_path, capsys):
    """fts-check JSON: kaputter Index -> Exit 1 + Meldung im Output.

    Spiegelt :func:`test_fkcheck_meldet_orphan` auf die FTS-Achse: nach einem
    Insert ohne FTS-Trigger ist der Index nicht mehr konsistent, der CLI-Pfad
    erkennt das und gibt Exit 1 + Meldungs-Liste zurueck.
    """
    db_file = tmp_path / "fts_broken_cli.sqlite3"
    c = open_db(db_file)
    c.execute("DROP TRIGGER objects_ai")
    c.execute("INSERT INTO objects(obj_id, Name) VALUES ('OBJ_X', 'Geist')")
    c.commit()
    c.close()
    exit_code = main(["fts-check", "--db", str(db_file), "--json"])
    assert exit_code == 1
    info = json.loads(capsys.readouterr().out)
    assert info["ok"] is False
    assert info["messages"] != []


def test_fts_check_fehlende_db(tmp_path, capsys):
    """fts-check auf nicht existierender DB liefert Exit 2 (spiegelt check)."""
    bad = tmp_path / "fehlt.sqlite3"
    exit_code = main(["fts-check", "--db", str(bad)])
    assert exit_code == 2
    assert "fehlt" in capsys.readouterr().err


def test_fts_optimize_text(tmp_path, capsys):
    """fts-optimize Subcommand: Text-Output enthaelt Abschluss-Meldung."""
    db_file = tmp_path / "ftso.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 5)
    c.close()
    exit_code = main(["fts-optimize", "--db", str(db_file)])
    assert exit_code == 0
    assert "FTS5 optimize abgeschlossen" in capsys.readouterr().out


def test_fts_optimize_json(tmp_path, capsys):
    """fts-optimize JSON: ok=True, Exit 0 (spiegelt optimize-Vertrag)."""
    db_file = tmp_path / "ftsoj.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 5)
    c.close()
    exit_code = main(["fts-optimize", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"ok": True}


def test_fts_optimize_fehlende_db(tmp_path, capsys):
    """fts-optimize auf nicht existierender DB liefert Exit 2."""
    bad = tmp_path / "fehlt.sqlite3"
    exit_code = main(["fts-optimize", "--db", str(bad)])
    assert exit_code == 2
    assert "fehlt" in capsys.readouterr().err


def test_fts_rebuild_text(tmp_path, capsys):
    """fts-rebuild Subcommand: Text-Output enthaelt Zeilen-Zaehler."""
    db_file = tmp_path / "ftsr.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 6)
    c.close()
    exit_code = main(["fts-rebuild", "--db", str(db_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "FTS5 rebuild abgeschlossen" in out
    assert "6 Eintraege" in out


def test_fts_rebuild_json(tmp_path, capsys):
    """fts-rebuild JSON: fts_rows entspricht der objects-Zeilenzahl."""
    db_file = tmp_path / "ftsrj.sqlite3"
    c = open_db(db_file)
    _seed_objects(c, 4)
    c.close()
    exit_code = main(["fts-rebuild", "--db", str(db_file), "--json"])
    assert exit_code == 0
    info = json.loads(capsys.readouterr().out)
    assert info == {"fts_rows": 4}


def test_fts_rebuild_repariert_kaputten_index(tmp_path, capsys):
    """fts-rebuild reparariert nach manuellem Bypass die FTS-Tabelle.

    Spiegelt :func:`test_fts_check_meldet_inkonsistenz` und den check->fix-
    Workflow aus :func:`test_cleanup_*`: erst check entdeckt das Problem,
    dann rebuild stellt den Index wieder her, dann ist check wieder sauber.
    """
    db_file = tmp_path / "ftsr_repair.sqlite3"
    c = open_db(db_file)
    c.execute("DROP TRIGGER objects_ai")
    c.execute("INSERT INTO objects(obj_id, Name) VALUES ('OBJ_X', 'Geist')")
    c.commit()
    c.close()
    # Check meldet das Problem
    assert main(["fts-check", "--db", str(db_file)]) == 1
    capsys.readouterr()  # drain output
    # Rebuild stellt es her
    assert main(["fts-rebuild", "--db", str(db_file)]) == 0
    capsys.readouterr()
    # Check ist wieder OK
    assert main(["fts-check", "--db", str(db_file)]) == 0


def test_fts_rebuild_fehlende_db(tmp_path, capsys):
    """fts-rebuild auf nicht existierender DB liefert Exit 2."""
    bad = tmp_path / "fehlt.sqlite3"
    exit_code = main(["fts-rebuild", "--db", str(bad)])
    assert exit_code == 2
    assert "fehlt" in capsys.readouterr().err
