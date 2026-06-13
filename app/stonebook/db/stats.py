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
    by_funddatum_jahr: dict[str, int] = field(default_factory=dict)
    bilder_by_kategorie: dict[str, int] = field(default_factory=dict)
    wert_summe_chf: float = 0.0
    wert_roh_summe_chf: float = 0.0
    wert_max_chf: float = 0.0
    wert_durchschnitt_chf: float = 0.0
    objekte_mit_wert: int = 0
    top_wert_objekte: list[tuple[str, str, float]] = field(default_factory=list)
    gewicht_summe_g: float = 0.0
    durchschnitt_confidence_prozent: float | None = None

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
            "by_funddatum_jahr": dict(self.by_funddatum_jahr),
            "bilder_by_kategorie": dict(self.bilder_by_kategorie),
            "wert_summe_chf": round(self.wert_summe_chf, 2),
            "wert_roh_summe_chf": round(self.wert_roh_summe_chf, 2),
            "wert_max_chf": round(self.wert_max_chf, 2),
            "wert_durchschnitt_chf": round(self.wert_durchschnitt_chf, 2),
            "objekte_mit_wert": self.objekte_mit_wert,
            "top_wert_objekte": [
                (oid, name, round(w, 2)) for oid, name, w in self.top_wert_objekte
            ],
            "gewicht_summe_g": round(self.gewicht_summe_g, 2),
            "durchschnitt_confidence_prozent": (
                round(self.durchschnitt_confidence_prozent, 1)
                if self.durchschnitt_confidence_prozent is not None else None
            ),
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


def _count_funddatum_jahr(conn: sqlite3.Connection, limit: int | None = None) -> dict[str, int]:
    """Zaehlt Objekte pro Funddatum-Jahr (Substring 1..4 von ISO YYYY-MM-DD).

    Nur Werte mit vier Ziffern am Anfang werden beruecksichtigt; ungueltige
    Funddaten werden ignoriert (siehe check_integrity).
    """
    sql = (
        "SELECT substr(Funddatum, 1, 4) AS jahr, COUNT(*) AS n FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY jahr ORDER BY jahr ASC"
    )
    rows = conn.execute(sql).fetchall()
    pairs = [(r["jahr"], r["n"]) for r in rows]
    if limit is not None:
        pairs.sort(key=lambda p: (-p[1], p[0]))
        pairs = pairs[:int(limit)]
        pairs.sort(key=lambda p: p[0])
    return {j: n for j, n in pairs}


def wert_pro_objekt_sql() -> str:
    """Per-Row-Summe der CHF-Wertfelder (für Sortierung/Aggregation/Filter)."""
    return "(" + " + ".join(f"COALESCE({c}, 0)" for c in WERT_FELDER) + ")"


# Backwards-Kompatibilitaet: vorheriger Privatname.
_wert_pro_objekt_sql = wert_pro_objekt_sql


def compute_statistics(conn: sqlite3.Connection, top_fundorte: int = 10,
                       top_wert: int = 10, top_jahre: int | None = None) -> Statistik:
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

    st.by_funddatum_jahr = _count_funddatum_jahr(conn, limit=top_jahre)

    st.bilder_by_kategorie = {
        r["kategorie"]: r["n"]
        for r in conn.execute(
            "SELECT kategorie, COUNT(*) AS n FROM images "
            "GROUP BY kategorie ORDER BY n DESC, kategorie ASC"
        ).fetchall()
    }

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
        + ", COALESCE(SUM(Gewicht_g), 0) AS gewicht, "
        "AVG(Confidence_Prozent) AS conf_avg FROM objects"
    ).fetchone()
    st.wert_summe_chf = float(sum(sums[c] for c in WERT_FELDER))
    st.wert_roh_summe_chf = float(sums["Wert_CHF_roh"])
    st.gewicht_summe_g = float(sums["gewicht"])
    st.durchschnitt_confidence_prozent = (
        float(sums["conf_avg"]) if sums["conf_avg"] is not None else None
    )

    wert_sql = wert_pro_objekt_sql()
    row = conn.execute(
        f"SELECT COALESCE(MAX({wert_sql}), 0) AS wmax, "
        f"COUNT(*) AS n FROM objects WHERE {wert_sql} > 0"
    ).fetchone()
    st.wert_max_chf = float(row["wmax"])
    st.objekte_mit_wert = int(row["n"])
    if st.objekte_mit_wert:
        st.wert_durchschnitt_chf = st.wert_summe_chf / st.objekte_mit_wert
    st.top_wert_objekte = [
        (r["obj_id"], r["Name"] or "", float(r["w"]))
        for r in conn.execute(
            f"SELECT obj_id, Name, {wert_sql} AS w FROM objects "
            f"WHERE {wert_sql} > 0 ORDER BY w DESC, obj_id LIMIT ?",
            (int(top_wert),),
        ).fetchall()
    ]
    return st
