"""SQLite-Verbindung und Schema-Initialisierung."""
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def default_db_file() -> Path:
    """Standardpfad zur SQLite-DB (Repo-Root + ``data/db/stonebook.sqlite3``).

    Gemeinsamer Default fuer alle CLIs; jede CLI darf das per ``--db`` ueberschreiben.
    """
    return Path(__file__).resolve().parents[3] / "data" / "db" / "stonebook.sqlite3"


def connect(db_file: Path) -> sqlite3.Connection:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def open_db(db_file: Path) -> sqlite3.Connection:
    conn = connect(db_file)
    init_db(conn)
    return conn
