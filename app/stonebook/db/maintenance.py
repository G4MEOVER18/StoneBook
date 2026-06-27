"""DB-Wartung: Vacuum (Kompaktierung), Groesse, SQLite-Selbstpruefung."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def database_size_bytes(conn: sqlite3.Connection) -> int:
    """Logische Datenbankgroesse in Bytes (Seitenzahl x Seitengroesse).

    Bezieht sich auf die Hauptdatei, ohne WAL/SHM, ohne Free-Pages-Defrag.
    Zum Vergleich vor/nach :func:`vacuum`.
    """
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    return int(page_count) * int(page_size)


def free_page_count(conn: sqlite3.Connection) -> int:
    """Zahl der nicht belegten Seiten (Indikator: lohnt sich ein VACUUM?)."""
    return int(conn.execute("PRAGMA freelist_count").fetchone()[0])


def vacuum(conn: sqlite3.Connection) -> tuple[int, int]:
    """Fuehrt ``VACUUM`` aus; gibt (bytes_vorher, bytes_nachher) zurueck.

    Schreibt die DB-Datei komplett neu, gibt Speicherplatz frei und defragmentiert.
    Erfordert keine offene Transaktion; SQLite oeffnet/schliesst sie selbst.
    """
    before = database_size_bytes(conn)
    conn.execute("VACUUM")
    after = database_size_bytes(conn)
    return before, after


def analyze(conn: sqlite3.Connection) -> int:
    """Fuehrt ``ANALYZE`` aus; gibt die Zahl der erfassten ``sqlite_stat1``-Eintraege zurueck.

    ``ANALYZE`` sammelt Verteilungs-Kennzahlen ueber alle Indizes und legt sie in
    der internen Tabelle ``sqlite_stat1`` ab. Der Query-Planner nutzt sie, um die
    selektivere von zwei alternativen Index-Strategien zu waehlen - z.B. bei
    Filter-Kombinationen aus :func:`ObjectRepo.list_objects`, die ueber mehrere
    Spalten gleichzeitig filtern. Sinnvoll nach groesseren Datenaenderungen
    (Migration, Stapel-Import, Massenarchivierung) und vor ``VACUUM`` im
    Wartungsfenster, weil ``VACUUM`` die DB komplett neu schreibt, aber die
    Statistiken nicht aktualisiert. Idempotent; mehrfacher Aufruf veraendert nur
    die Statistik, nicht die Nutzdaten. Spiegelt :func:`vacuum` als zweite
    optimierende Wartungsoperation: ``VACUUM`` reduziert die Datei-Groesse,
    ``ANALYZE`` verbessert die Query-Plaene.
    """
    conn.execute("ANALYZE")
    conn.commit()
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='sqlite_stat1'"
    ).fetchone()
    if not row[0]:
        return 0
    return int(conn.execute("SELECT COUNT(*) FROM sqlite_stat1").fetchone()[0])


def optimize(conn: sqlite3.Connection) -> int:
    """Fuehrt ``PRAGMA optimize`` aus; gibt die Zahl der ``sqlite_stat1``-Eintraege zurueck.

    ``PRAGMA optimize`` ist die SQLite-empfohlene periodische Wartungs-Operation
    auf der Query-Planner-Achse und spiegelt :func:`analyze` als selektive
    Variante: waehrend ``ANALYZE`` immer eine vollstaendige Verteilungs-
    Erfassung ueber alle Indizes erzwingt (unabhaengig davon, ob sich die
    Tabellen-Inhalte seit dem letzten Lauf merklich geaendert haben),
    untersucht ``PRAGMA optimize`` zunaechst die Tabellen und fuehrt
    ``ANALYZE`` nur dort aus, wo SQLite die bestehenden Statistiken als
    veraltet einstuft (z.B. nach merklicher Aenderung der Zeilenzahl seit dem
    letzten Lauf; die Heuristik liegt in den Header-Kommentaren der SQLite-
    Quellen unter ``sqlite3Optimize`` dokumentiert). Damit ist ``PRAGMA
    optimize`` die leichtgewichtige Operation fuer regelmaessige Wartungs-
    Cron-Jobs (taeglich/wochentags ohne Performance-Einbruch), waehrend
    ``ANALYZE`` als manueller Voll-Refresh nach Migration / Stapel-Import /
    Massenarchivierung gedacht ist. Idempotent: zwei Aufrufe in Folge sind
    sicher; SQLite ueberspringt die zweite Iteration komplett, weil die
    Statistiken bereits frisch sind. Liefert die Anzahl der vorhandenen
    Index-Statistik-Eintraege zurueck - spiegelt :func:`analyze` im Rueckgabe-
    Format, damit beide Operationen austauschbar in CLI/JSON-Reportern sind.
    """
    conn.execute("PRAGMA optimize")
    conn.commit()
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='sqlite_stat1'"
    ).fetchone()
    if not row[0]:
        return 0
    return int(conn.execute("SELECT COUNT(*) FROM sqlite_stat1").fetchone()[0])


def fts_integrity_check(conn: sqlite3.Connection) -> list[str]:
    """SQLite-FTS5-eigene Konsistenzpruefung des ``objects_fts``-Index.

    Spiegelt :func:`quick_check`/:func:`deep_check` (Page-/Index-Korruption der
    Basistabellen) und :func:`foreign_key_check` (referentielle Achse) auf die
    FTS-Achse: ``INSERT INTO objects_fts(objects_fts) VALUES('integrity-check')``
    laesst die FTS5-Engine ihre internen Segment-Strukturen gegen den
    Content-Table (``content='objects'``) abgleichen und meldet Inkonsistenzen
    als ``sqlite3.DatabaseError`` (typisch nach manueller DB-Edition mit
    ``PRAGMA foreign_keys=OFF``, JSON-Restore aus partiellen Backups oder
    abgebrochenen Migrations-Laeufen, die die FTS-Trigger nicht durchlaufen
    haben). Liefert ``[]`` bei intaktem FTS-Index, sonst die Fehler-Meldungen
    der Engine als String-Liste - spiegelt das Listen-Format von
    :func:`quick_check`/:func:`deep_check` exakt, damit Cron-Reporter und
    JSON-CLI-Pfade die gleiche Auswertung nutzen koennen.

    Behoben wird ein gemeldeter Schaden ueber :func:`fts_rebuild`, das den
    FTS-Index vollstaendig aus dem Content-Table neu aufbaut.

    Verwendet die FTS5-Variante ``('integrity-check', 1)``: das ``rank=1``-
    Argument schaltet die zusaetzliche Pruefung gegen den Content-Table
    (``content='objects'``) frei - ohne dieses Argument prueft FTS5 nur die
    internen Index-Strukturen (B-Tree-Konsistenz), nicht aber die Spiegelung
    zwischen Content-Table und Index-Eintraegen, sodass Trigger-Bypass-
    Inkonsistenzen unentdeckt blieben.
    """
    try:
        conn.execute(
            "INSERT INTO objects_fts(objects_fts, rank) "
            "VALUES('integrity-check', 1)")
        return []
    except sqlite3.DatabaseError as exc:
        return [str(exc)]


def fts_optimize(conn: sqlite3.Connection) -> None:
    """Fuehrt ``INSERT INTO objects_fts(objects_fts) VALUES('optimize')`` aus.

    Spiegelt :func:`optimize` (Query-Planner-Statistiken) auf die FTS-Achse:
    waehrend ``PRAGMA optimize`` die ``sqlite_stat1``-Verteilungen pflegt,
    pflegt ``fts_optimize`` den FTS5-Segment-Layout. Nach vielen
    Update/Delete-Operationen liegt der FTS-Index fragmentiert in vielen
    kleinen Segmenten, die jede MATCH-Suche linear durchsuchen muss; die
    Optimize-Operation merged sie zu einem einzigen grossen Segment und
    macht die Suche deutlich schneller. Idempotent: zwei Aufrufe in Folge
    sind sicher; SQLite ueberspringt die zweite Iteration komplett, weil
    der Index bereits maximal kompakt ist.

    Geeignet fuer Wartungs-Cron neben :func:`optimize` und :func:`vacuum`:
    ``vacuum`` reduziert die Datei-Groesse, ``optimize`` die Query-Plaene,
    ``fts_optimize`` die FTS-Such-Latenz. Liefert ``None`` zurueck (kein
    sinnvolles Mass wie bei ``optimize``/``analyze`` - die Engine meldet
    weder die vorherige Segment-Zahl noch die neue im SQL-Interface).
    """
    conn.execute("INSERT INTO objects_fts(objects_fts) VALUES('optimize')")
    conn.commit()


def fts_rebuild(conn: sqlite3.Connection) -> int:
    """Baut den ``objects_fts``-Index vollstaendig aus den Inhalten neu auf.

    Spiegelt :func:`fts_integrity_check` als die zugehoerige Reparatur-
    Operation: wenn der Integrity-Check eine FTS-Inkonsistenz meldet (typisch
    nach manuellem Direkt-Insert in ``objects`` ohne die Insert-Trigger, nach
    JSON-Restore aus einem Backup, dessen FTS-Tabelle leer war, oder nach
    Schema-Aenderungen, die die FTS-Trigger nicht durchlaufen haben), stellt
    ``INSERT INTO objects_fts(objects_fts) VALUES('rebuild')`` den Index
    bit-genau aus dem Content-Table (``content='objects'``) wieder her.

    Liefert die Anzahl Zeilen in ``objects_fts`` nach dem Rebuild zurueck -
    spiegelt damit das Rueckgabe-Format von :func:`analyze`/:func:`optimize`
    (Zaehler) und macht den Erfolg fuer Cron-Reporter messbar (Anzahl muss
    der ``objects``-Zeilenzahl entsprechen).
    """
    conn.execute("INSERT INTO objects_fts(objects_fts) VALUES('rebuild')")
    conn.commit()
    return int(conn.execute("SELECT COUNT(*) FROM objects_fts").fetchone()[0])


def quick_check(conn: sqlite3.Connection) -> list[str]:
    """SQLite-eigene Konsistenzpruefung (Schnell-Variante).

    Liefert ``[]`` bei intakter DB; sonst eine Liste mit Befund-Strings,
    die SQLite zurueckgibt. Erkennt Korruption an Indizes/Bloeben, NICHT
    inhaltliche Inkonsistenzen (dafuer :func:`stonebook.db.integrity.check_integrity`).
    """
    rows = conn.execute("PRAGMA quick_check").fetchall()
    msgs = [r[0] for r in rows]
    return [] if msgs == ["ok"] else msgs


def deep_check(conn: sqlite3.Connection) -> list[str]:
    """SQLite-eigene Konsistenzpruefung (Voll-Variante, ``PRAGMA integrity_check``).

    Liefert ``[]`` bei intakter DB; sonst eine Liste mit Befund-Strings, die
    SQLite zurueckgibt. Spiegelt :func:`quick_check` exakt im Output-Format
    (Liste von Strings, leer = ok), aber laeuft die vollstaendige Pruefung der
    DB-Datei statt der schnellen Stichproben - inklusive Index-Konsistenz
    gegen die Basistabellen, NULL-Spalten mit NOT-NULL-Constraint und
    UNIQUE-Constraint-Verletzungen, die ``quick_check`` ueberspringt. Aequivalent
    zu ``quick_check`` fuer Cron/Health-Probe (gleiche Liste-Semantik), aber als
    deep-scan vor Backup, Release oder vor dem manuellen Wiederherstellungsplan
    geeignet. Performance: O(DB-Groesse) statt O(DB-Groesse) mit Sampling -
    fuer die StoneBook-DB im MB-Bereich vernachlaessigbar, fuer multi-GB-DBs
    aber merklich langsamer. Komplementaer zu :func:`foreign_key_check`
    (referentielle Achse, separate PRAGMA): zusammen decken die drei Funktionen
    die drei orthogonalen SQLite-Korruptions-Achsen ab - Page/Index-Schaden
    (quick_check), Voll-Pruefung inkl. UNIQUE/NOT-NULL (deep_check) und FK-
    Verletzungen (foreign_key_check).
    """
    rows = conn.execute("PRAGMA integrity_check").fetchall()
    msgs = [r[0] for r in rows]
    return [] if msgs == ["ok"] else msgs


def foreign_key_check(conn: sqlite3.Connection) -> list[tuple[str, int | None, str, int]]:
    """SQLite-eigene Foreign-Key-Pruefung (``PRAGMA foreign_key_check``).

    Liefert ``[]`` bei intakter DB; sonst eine Liste von
    ``(table, rowid, parent_table, fkid)``-Tupels - genau das Format, das
    SQLite zurueckgibt. Spiegelt :func:`quick_check` (Page-/Index-Korruption)
    auf die referentielle Achse: ``foreign_key_check`` erkennt verwaiste Zeilen,
    deren Foreign Key auf eine nicht (mehr) existierende Eltern-Zeile zeigt -
    unabhaengig davon, ob ``PRAGMA foreign_keys`` zur Schreibzeit aktiv war
    (genau die Faelle, die orphan_images / alias_to_missing aus
    :mod:`stonebook.db.integrity` ueber SQL-Joins ebenfalls finden, aber dort
    je Beziehung einzeln; ``foreign_key_check`` deckt alle drei
    Cascade-Beziehungen objects-images, objects-aliases, objects-ki_analysen
    in einem PRAGMA-Aufruf ab).

    ``rowid`` ist ``None`` fuer WITHOUT-ROWID-Tabellen (StoneBook hat keine,
    aber das Format gehoert zur Spezifikation); ``fkid`` ist der numerische
    Index des FK in der Constraint-Liste der Kind-Tabelle (vgl.
    ``PRAGMA foreign_key_list(<table>)``), damit bei Mehrfach-FKs eindeutig
    bleibt, welche Beziehung verletzt ist.
    """
    return [
        (r[0], r[1], r[2], r[3])
        for r in conn.execute("PRAGMA foreign_key_check").fetchall()
    ]


def db_file_bytes(db_file: Path) -> int:
    """Tatsaechliche Dateigroesse der SQLite-Datei in Bytes (oder 0, wenn fehlt)."""
    p = Path(db_file)
    return p.stat().st_size if p.is_file() else 0


def delete_orphan_images(conn: sqlite3.Connection) -> int:
    """Entfernt Bild-Eintraege, deren ``obj_id`` auf kein Objekt mehr verweist.

    Pendant zu ``IntegrityReport.orphan_images`` aus
    :mod:`stonebook.db.integrity`: dort wird das Problem erkannt, hier behoben.
    Im Normalbetrieb erzeugt das ``ON DELETE CASCADE`` der FK-Beziehung nie
    Orphans; sie entstehen durch ``PRAGMA foreign_keys=OFF`` (manuelle DB-
    Editierung, JSON-Restore aus partiellen Backups, fehlerhafte Migrations-
    skripte). Gibt die Anzahl tatsaechlich geloeschter Zeilen zurueck.
    """
    cur = conn.execute(
        "DELETE FROM images WHERE obj_id NOT IN (SELECT obj_id FROM objects)")
    conn.commit()
    return cur.rowcount


def delete_orphan_ki_analysen(conn: sqlite3.Connection) -> int:
    """Entfernt KI-Analyse-Eintraege ohne zugehoeriges Objekt.

    Spiegelt :func:`delete_orphan_images` auf die ``ki_analysen``-Tabelle:
    auch hier sorgt ``ON DELETE CASCADE`` im Schema fuer Sauberkeit im
    regulaeren Betrieb; Orphans treten nur ueber die gleichen
    PRAGMA-OFF-Pfade auf. Pendant zu ``IntegrityReport.orphan_ki_analysen``.
    """
    cur = conn.execute(
        "DELETE FROM ki_analysen WHERE obj_id NOT IN (SELECT obj_id FROM objects)")
    conn.commit()
    return cur.rowcount


def delete_dangling_aliases(conn: sqlite3.Connection) -> int:
    """Entfernt Alias-Eintraege, deren Kanon-Objekt fehlt.

    Pendant zu ``IntegrityReport.alias_to_missing``: in der regulaeren Anwendung
    (delete-Pfad ueber ObjectRepo) niemals erzeugt - das FK auf objects(obj_id)
    mit ON DELETE CASCADE haelt das sauber. Sie koennen aber durch JSON-Restore
    aus einem partiellen Backup (nur aliases-Tabelle ohne die zugehoerigen
    canonical-Objekte), direkte DB-Editierung mit PRAGMA foreign_keys=OFF oder
    fehlerhafte Migrations-Skripte entstehen. Gibt die Anzahl tatsaechlich
    geloeschter Zeilen zurueck.
    """
    cur = conn.execute(
        "DELETE FROM aliases WHERE canonical_id NOT IN (SELECT obj_id FROM objects)")
    conn.commit()
    return cur.rowcount
