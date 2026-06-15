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


def db_file_bytes(db_file: Path) -> int:
    """Tatsaechliche Dateigroesse der SQLite-Datei in Bytes (oder 0, wenn fehlt)."""
    p = Path(db_file)
    return p.stat().st_size if p.is_file() else 0
