"""Aggregierte Kennzahlen über die Objekt-DB (Grundlage für Dashboard/Berichte)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

# Felder, die in WERTSUMME einfliessen
WERT_FELDER = (
    "Wert_CHF_roh",
    "Wert_CHF_poliert",
    "Wert_CHF_Schmuck",
    "Marktwert_Industrie",
    "Wissenschaftlicher_Wert_CHF",
)


@dataclass
class Statistik:
    objekte_total: int = 0
    objekte_aktiv: int = 0
    objekte_platzhalter: int = 0
    objekte_archiviert: int = 0
    objekte_mit_bildern: int = 0
    objekte_mit_funddatum: int = 0
    bilder_total: int = 0
    aliase_total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_mineral: dict[str, int] = field(default_factory=dict)
    by_kategorie: dict[str, int] = field(default_factory=dict)
    by_fundort: dict[str, int] = field(default_factory=dict)
    wert_summe_chf: float = 0.0
    gewicht_summe_g: float = 0.0

    def as_dict(self) -> dict:
        return {
            "objekte_total": self.objekte_total,
            "objekte_aktiv": self.objekte_aktiv,
            "objekte_platzhalter": self.objekte_platzhalter,
            "objekte_archiviert": self.objekte_archiviert,
            "objekte_mit_bildern": self.objekte_mit_bildern,
            "objekte_mit_funddatum": self.objekte_mit_funddatum,
            "bilder_total": self.bilder_total,
            "aliase_total": self.aliase_total,
            "by_status": dict(self.by_status),
            "by_mineral": dict(self.by_mineral),
            "by_kategorie": dict(self.by_kategorie),
            "by_fundort": dict(self.by_fundort),
            "wert_summe_chf": round(self.wert_summe_chf, 2),
            "gewicht_summe_g": round(self.gewicht_summe_g, 2),
        }


def _count_by(conn: sqlite3.Connection, column: str, limit: int | None = None) -> dict[str, int]:
    sql = (
        f"SELECT {column} AS k, COUNT(*) AS n FROM objects "
        f"WHERE {column} IS NOT NULL AND TRIM({column}) != '' "
        f"GROUP BY {column} ORDER BY n DESC, {column} ASC"
    )
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return {r["k"]: r["n"] for r in conn.execute(sql).fetchall()}


def compute_statistics(conn: sqlite3.Connection, top_fundorte: int = 10) -> Statistik:
    """Berechnet alle Kennzahlen in einer Sammlung von SQL-Aggregaten."""
    st = Statistik()
    st.objekte_total = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    st.bilder_total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    st.aliase_total = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]

    st.by_status = {
        r["status"]: r["n"]
        for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM objects GROUP BY status"
        ).fetchall()
    }
    st.objekte_aktiv = st.by_status.get("aktiv", 0)
    st.objekte_platzhalter = st.by_status.get("platzhalter", 0)
    st.objekte_archiviert = st.by_status.get("archiviert", 0)

    st.by_mineral = _count_by(conn, "Mineral_Primaer")
    st.by_kategorie = _count_by(conn, "Kategorie")
    st.by_fundort = _count_by(conn, "Fundort", limit=top_fundorte)

    st.objekte_mit_bildern = conn.execute(
        "SELECT COUNT(DISTINCT obj_id) FROM images"
    ).fetchone()[0]
    st.objekte_mit_funddatum = conn.execute(
        "SELECT COUNT(*) FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != ''"
    ).fetchone()[0]

    sums = conn.execute(
        "SELECT "
        + ", ".join(f"COALESCE(SUM({c}), 0) AS {c}" for c in WERT_FELDER)
        + ", COALESCE(SUM(Gewicht_g), 0) AS gewicht FROM objects"
    ).fetchone()
    st.wert_summe_chf = float(sum(sums[c] for c in WERT_FELDER))
    st.gewicht_summe_g = float(sums["gewicht"])
    return st
