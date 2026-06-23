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
