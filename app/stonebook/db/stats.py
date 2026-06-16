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
    ki_analysen_total: int = 0
    ki_analysen_uebernommen: int = 0
    objekte_mit_ki_analyse: int = 0
    mineral_arten_total: int = 0
    fundorte_total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_mineral: dict[str, int] = field(default_factory=dict)
    by_kategorie: dict[str, int] = field(default_factory=dict)
    by_kristallsystem: dict[str, int] = field(default_factory=dict)
    by_beste_verwendung: dict[str, int] = field(default_factory=dict)
    by_fundort: dict[str, int] = field(default_factory=dict)
    by_funddatum_jahr: dict[str, int] = field(default_factory=dict)
    by_funddatum_jahrzehnt: dict[str, int] = field(default_factory=dict)
    bilder_by_kategorie: dict[str, int] = field(default_factory=dict)
    funddatum_frueheste: str | None = None
    funddatum_spaeteste: str | None = None
    wert_summe_chf: float = 0.0
    wert_roh_summe_chf: float = 0.0
    wert_max_chf: float = 0.0
    wert_durchschnitt_chf: float = 0.0
    wert_median_chf: float = 0.0
    objekte_mit_wert: int = 0
    top_wert_objekte: list[tuple[str, str, float]] = field(default_factory=list)
    top_gewicht_objekte: list[tuple[str, str, float]] = field(default_factory=list)
    top_bilder_objekte: list[tuple[str, str, int]] = field(default_factory=list)
    top_confidence_objekte: list[tuple[str, str, int]] = field(default_factory=list)
    wert_pro_mineral: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_fundort: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_kategorie: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_kristallsystem: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_status: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_mineral: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_fundort: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_kategorie: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_kristallsystem: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_status: list[tuple[str, float]] = field(default_factory=list)
    gewicht_summe_g: float = 0.0
    gewicht_durchschnitt_g: float = 0.0
    gewicht_median_g: float = 0.0
    gewicht_max_g: float = 0.0
    objekte_mit_gewicht: int = 0
    durchschnitt_confidence_prozent: float | None = None
    median_confidence_prozent: float | None = None
    confidence_buckets: dict[str, int] = field(default_factory=dict)

    def _quote(self, n: int) -> float | None:
        if self.objekte_total <= 0:
            return None
        return n / self.objekte_total * 100.0

    @property
    def quote_mit_bildern_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_bildern)

    @property
    def quote_mit_funddatum_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_funddatum)

    @property
    def quote_mit_wert_prozent(self) -> float | None:
        return self._quote(self.objekte_mit_wert)

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
            "ki_analysen_total": self.ki_analysen_total,
            "ki_analysen_uebernommen": self.ki_analysen_uebernommen,
            "objekte_mit_ki_analyse": self.objekte_mit_ki_analyse,
            "mineral_arten_total": self.mineral_arten_total,
            "fundorte_total": self.fundorte_total,
            "by_status": dict(self.by_status),
            "by_mineral": dict(self.by_mineral),
            "by_kategorie": dict(self.by_kategorie),
            "by_kristallsystem": dict(self.by_kristallsystem),
            "by_beste_verwendung": dict(self.by_beste_verwendung),
            "by_fundort": dict(self.by_fundort),
            "by_funddatum_jahr": dict(self.by_funddatum_jahr),
            "by_funddatum_jahrzehnt": dict(self.by_funddatum_jahrzehnt),
            "bilder_by_kategorie": dict(self.bilder_by_kategorie),
            "funddatum_frueheste": self.funddatum_frueheste,
            "funddatum_spaeteste": self.funddatum_spaeteste,
            "wert_summe_chf": round(self.wert_summe_chf, 2),
            "wert_roh_summe_chf": round(self.wert_roh_summe_chf, 2),
            "wert_max_chf": round(self.wert_max_chf, 2),
            "wert_durchschnitt_chf": round(self.wert_durchschnitt_chf, 2),
            "wert_median_chf": round(self.wert_median_chf, 2),
            "objekte_mit_wert": self.objekte_mit_wert,
            "top_wert_objekte": [
                (oid, name, round(w, 2)) for oid, name, w in self.top_wert_objekte
            ],
            "top_gewicht_objekte": [
                (oid, name, round(g, 2)) for oid, name, g in self.top_gewicht_objekte
            ],
            "top_bilder_objekte": [
                (oid, name, int(n)) for oid, name, n in self.top_bilder_objekte
            ],
            "top_confidence_objekte": [
                (oid, name, int(c)) for oid, name, c in self.top_confidence_objekte
            ],
            "wert_pro_mineral": [
                (mineral, round(w, 2)) for mineral, w in self.wert_pro_mineral
            ],
            "wert_pro_fundort": [
                (ort, round(w, 2)) for ort, w in self.wert_pro_fundort
            ],
            "wert_pro_kategorie": [
                (kat, round(w, 2)) for kat, w in self.wert_pro_kategorie
            ],
            "wert_pro_kristallsystem": [
                (ks, round(w, 2)) for ks, w in self.wert_pro_kristallsystem
            ],
            "wert_pro_status": [
                (s, round(w, 2)) for s, w in self.wert_pro_status
            ],
            "gewicht_pro_mineral": [
                (mineral, round(g, 2)) for mineral, g in self.gewicht_pro_mineral
            ],
            "gewicht_pro_fundort": [
                (ort, round(g, 2)) for ort, g in self.gewicht_pro_fundort
            ],
            "gewicht_pro_kategorie": [
                (kat, round(g, 2)) for kat, g in self.gewicht_pro_kategorie
            ],
            "gewicht_pro_kristallsystem": [
                (ks, round(g, 2)) for ks, g in self.gewicht_pro_kristallsystem
            ],
            "gewicht_pro_status": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_status
            ],
            "gewicht_summe_g": round(self.gewicht_summe_g, 2),
            "gewicht_durchschnitt_g": round(self.gewicht_durchschnitt_g, 2),
            "gewicht_median_g": round(self.gewicht_median_g, 2),
            "gewicht_max_g": round(self.gewicht_max_g, 2),
            "objekte_mit_gewicht": self.objekte_mit_gewicht,
            "durchschnitt_confidence_prozent": (
                round(self.durchschnitt_confidence_prozent, 1)
                if self.durchschnitt_confidence_prozent is not None else None
            ),
            "median_confidence_prozent": (
                round(self.median_confidence_prozent, 1)
                if self.median_confidence_prozent is not None else None
            ),
            "confidence_buckets": dict(self.confidence_buckets),
            "quote_mit_bildern_prozent": _round_or_none(self.quote_mit_bildern_prozent),
            "quote_mit_funddatum_prozent": _round_or_none(self.quote_mit_funddatum_prozent),
            "quote_mit_wert_prozent": _round_or_none(self.quote_mit_wert_prozent),
        }


def _round_or_none(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None else None


def _count_distinct(conn: sqlite3.Connection, column: str) -> int:
    """Anzahl der verschiedenen Werte in ``column`` (NULL/leer ignoriert)."""
    return conn.execute(
        f"SELECT COUNT(DISTINCT {column}) FROM objects "
        f"WHERE {column} IS NOT NULL AND TRIM({column}) != ''"
    ).fetchone()[0]


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


def _count_funddatum_jahrzehnt(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro Funddatum-Jahrzehnt (Dekade), Label ``1980er``, ``1990er`` ...

    Aggregiert die Jahres-Verteilung auf 10er-Schritte; das Label ist die
    Dekaden-Startzahl mit Suffix ``er`` (Sammler-Konvention: "Funde aus den
    1990ern"). Ohne Limit, weil die Zahl der Dekaden ueberschaubar bleibt
    (~10-15 ueber ein Sammlerleben).

    Komplementaer zu :func:`_count_funddatum_jahr`: zeigt grobe
    Aktivitaetsphasen ohne Einzeljahres-Rauschen. Sortierung: chronologisch
    aufsteigend (aelteste Dekade zuerst), damit das Histogramm zeitlich
    lesbar bleibt.
    """
    sql = (
        "SELECT (CAST(substr(Funddatum, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        "       COUNT(*) AS n FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY dekade ORDER BY dekade ASC"
    )
    return {f"{r['dekade']}er": r["n"] for r in conn.execute(sql).fetchall()}


def _funddatum_spanne(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    """Liefert (fruehestes, spaetestes) Funddatum als ISO-String.

    Beruecksichtigt nur Werte, die mit vier Ziffern beginnen (siehe
    :func:`_count_funddatum_jahr`); ISO YYYY-MM-DD ist lexikographisch
    sortierbar. Reine Jahresangaben (``"2024"``) werden mit einbezogen
    und tauchen so als Grenze auf, sofern keine spezifischere Angabe da ist.
    Leere DB → ``(None, None)``.
    """
    row = conn.execute(
        "SELECT MIN(Funddatum) AS lo, MAX(Funddatum) AS hi FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'"
    ).fetchone()
    return (row["lo"], row["hi"])


CONFIDENCE_BUCKET_ORDER: tuple[str, ...] = ("ohne", "0-24", "25-49", "50-74", "75-100")


def _confidence_buckets(conn: sqlite3.Connection) -> dict[str, int]:
    """Verteilung der Confidence-Werte auf 25-Prozent-Klassen + 'ohne' (NULL).

    Liefert ein Dict in fester Reihenfolge ``CONFIDENCE_BUCKET_ORDER``; Klassen
    ohne Treffer bleiben mit 0 enthalten, damit das Dashboard eine stabile
    Bar-Reihenfolge zeichnen kann. Out-of-Range-Werte (<0 oder >100) zaehlen
    nicht mit; sie werden separat in :func:`check_integrity` gemeldet.
    """
    counts = dict.fromkeys(CONFIDENCE_BUCKET_ORDER, 0)
    rows = conn.execute(
        "SELECT CASE "
        "  WHEN Confidence_Prozent IS NULL THEN 'ohne' "
        "  WHEN Confidence_Prozent BETWEEN 0 AND 24 THEN '0-24' "
        "  WHEN Confidence_Prozent BETWEEN 25 AND 49 THEN '25-49' "
        "  WHEN Confidence_Prozent BETWEEN 50 AND 74 THEN '50-74' "
        "  WHEN Confidence_Prozent BETWEEN 75 AND 100 THEN '75-100' "
        "  ELSE NULL END AS bucket, COUNT(*) AS n "
        "FROM objects GROUP BY bucket"
    ).fetchall()
    for r in rows:
        b = r["bucket"]
        if b in counts:
            counts[b] = r["n"]
    return counts


def wert_pro_objekt_sql() -> str:
    """Per-Row-Summe der CHF-Wertfelder (für Sortierung/Aggregation/Filter)."""
    return "(" + " + ".join(f"COALESCE({c}, 0)" for c in WERT_FELDER) + ")"


def _sum_by(conn: sqlite3.Connection, group_col: str, value_sql: str,
            limit: int, extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach ``group_col`` und liefert die
    Top-N absteigend nach Summe (Tiebreaker: Gruppenname aufsteigend).

    ``group_col`` darf nur ein Spaltenname sein (Whitelist-Validierung beim
    Aufrufer). ``extra_where`` ist optional und wird per AND angefuegt.
    """
    where = (f"{group_col} IS NOT NULL AND TRIM({group_col}) != ''")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT {group_col} AS k, SUM({value_sql}) AS w FROM objects "
        f"WHERE {where} "
        f"GROUP BY {group_col} HAVING w > 0 "
        f"ORDER BY w DESC, {group_col} ASC LIMIT ?"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql, (int(limit),)).fetchall()]


# Backwards-Kompatibilitaet: vorheriger Privatname.
_wert_pro_objekt_sql = wert_pro_objekt_sql


def compute_statistics(conn: sqlite3.Connection, top_fundorte: int = 10,
                       top_wert: int = 10, top_jahre: int | None = None,
                       top_wert_mineral: int = 10,
                       top_gewicht_mineral: int = 10,
                       top_wert_fundort: int = 10,
                       top_gewicht_fundort: int = 10,
                       top_wert_kategorie: int = 10,
                       top_gewicht_kategorie: int = 10,
                       top_wert_kristallsystem: int = 10,
                       top_gewicht_kristallsystem: int = 10,
                       top_gewicht: int = 10,
                       top_bilder: int = 10,
                       top_confidence: int = 10) -> Statistik:
    """Berechnet alle Kennzahlen in einer Sammlung von SQL-Aggregaten."""
    st = Statistik()
    st.objekte_total = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    st.bilder_total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    st.aliase_total = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    st.ki_analysen_total = conn.execute("SELECT COUNT(*) FROM ki_analysen").fetchone()[0]
    st.ki_analysen_uebernommen = conn.execute(
        "SELECT COUNT(*) FROM ki_analysen "
        "WHERE uebernommen_json IS NOT NULL AND TRIM(uebernommen_json) != ''"
    ).fetchone()[0]
    st.objekte_mit_ki_analyse = conn.execute(
        "SELECT COUNT(DISTINCT obj_id) FROM ki_analysen"
    ).fetchone()[0]

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
    st.by_kristallsystem = _count_by(conn, "Kristallsystem")
    st.by_beste_verwendung = _count_by(conn, "Beste_Verwendung")
    st.by_fundort = _count_by(conn, "Fundort", limit=top_fundorte)
    # Diversitaets-Kennzahlen: Anzahl distinct, unabhaengig von Top-N-Limits.
    st.mineral_arten_total = _count_distinct(conn, "Mineral_Primaer")
    st.fundorte_total = _count_distinct(conn, "Fundort")

    st.by_funddatum_jahr = _count_funddatum_jahr(conn, limit=top_jahre)
    st.by_funddatum_jahrzehnt = _count_funddatum_jahrzehnt(conn)
    st.funddatum_frueheste, st.funddatum_spaeteste = _funddatum_spanne(conn)

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
    # Median Confidence: symmetrisch zu wert_median_chf/gewicht_median_g.
    # Out-of-Range-Werte (<0 / >100) zaehlen nicht; sie werden in der Integrity
    # separat gemeldet und wuerden die zentrale Tendenz verzerren.
    conf_werte = [int(r["c"]) for r in conn.execute(
        "SELECT Confidence_Prozent AS c FROM objects "
        "WHERE Confidence_Prozent IS NOT NULL "
        "AND Confidence_Prozent BETWEEN 0 AND 100 "
        "ORDER BY c"
    ).fetchall()]
    if conf_werte:
        n = len(conf_werte)
        st.median_confidence_prozent = float(
            conf_werte[n // 2] if n % 2
            else (conf_werte[n // 2 - 1] + conf_werte[n // 2]) / 2
        )
    st.confidence_buckets = _confidence_buckets(conn)

    gewichte = [float(r["g"]) for r in conn.execute(
        "SELECT Gewicht_g AS g FROM objects "
        "WHERE Gewicht_g IS NOT NULL AND Gewicht_g > 0 ORDER BY g"
    ).fetchall()]
    st.objekte_mit_gewicht = len(gewichte)
    if gewichte:
        st.gewicht_max_g = gewichte[-1]
        st.gewicht_durchschnitt_g = sum(gewichte) / len(gewichte)
        n = len(gewichte)
        st.gewicht_median_g = (gewichte[n // 2] if n % 2
                               else (gewichte[n // 2 - 1] + gewichte[n // 2]) / 2)

    wert_sql = wert_pro_objekt_sql()
    row = conn.execute(
        f"SELECT COALESCE(MAX({wert_sql}), 0) AS wmax, "
        f"COUNT(*) AS n FROM objects WHERE {wert_sql} > 0"
    ).fetchone()
    st.wert_max_chf = float(row["wmax"])
    st.objekte_mit_wert = int(row["n"])
    if st.objekte_mit_wert:
        st.wert_durchschnitt_chf = st.wert_summe_chf / st.objekte_mit_wert
        werte = [float(r["w"]) for r in conn.execute(
            f"SELECT {wert_sql} AS w FROM objects "
            f"WHERE {wert_sql} > 0 ORDER BY w"
        ).fetchall()]
        n = len(werte)
        st.wert_median_chf = (werte[n // 2] if n % 2
                              else (werte[n // 2 - 1] + werte[n // 2]) / 2)
    st.top_wert_objekte = [
        (r["obj_id"], r["Name"] or "", float(r["w"]))
        for r in conn.execute(
            f"SELECT obj_id, Name, {wert_sql} AS w FROM objects "
            f"WHERE {wert_sql} > 0 ORDER BY w DESC, obj_id LIMIT ?",
            (int(top_wert),),
        ).fetchall()
    ]
    st.top_gewicht_objekte = [
        (r["obj_id"], r["Name"] or "", float(r["g"]))
        for r in conn.execute(
            "SELECT obj_id, Name, Gewicht_g AS g FROM objects "
            "WHERE Gewicht_g IS NOT NULL AND Gewicht_g > 0 "
            "ORDER BY g DESC, obj_id LIMIT ?",
            (int(top_gewicht),),
        ).fetchall()
    ]
    # Best-fotografierte Objekte (analog top_wert/top_gewicht): zeigt, welche Stuecke
    # die hoechste Bilder-Coverage haben. Aggregiert ueber alle Foto-Kategorien.
    st.top_bilder_objekte = [
        (r["obj_id"], r["Name"] or "", int(r["n"]))
        for r in conn.execute(
            "SELECT o.obj_id AS obj_id, o.Name AS Name, COUNT(i.id) AS n "
            "FROM objects o JOIN images i ON i.obj_id = o.obj_id "
            "GROUP BY o.obj_id, o.Name HAVING n > 0 "
            "ORDER BY n DESC, o.obj_id LIMIT ?",
            (int(top_bilder),),
        ).fetchall()
    ]
    # Top-Confidence-Objekte: am verlaesslichsten identifizierte Stuecke (analog
    # top_wert/top_gewicht/top_bilder). Out-of-Range-Werte (<0 / >100) bleiben
    # ausgeschlossen, damit die Tabelle nicht von kaputten Confidence-Eintraegen
    # dominiert wird (Integrity meldet die separat).
    st.top_confidence_objekte = [
        (r["obj_id"], r["Name"] or "", int(r["c"]))
        for r in conn.execute(
            "SELECT obj_id, Name, Confidence_Prozent AS c FROM objects "
            "WHERE Confidence_Prozent IS NOT NULL "
            "AND Confidence_Prozent BETWEEN 0 AND 100 "
            "ORDER BY c DESC, obj_id LIMIT ?",
            (int(top_confidence),),
        ).fetchall()
    ]
    st.wert_pro_mineral = _sum_by(conn, "Mineral_Primaer", wert_sql, top_wert_mineral)
    st.wert_pro_fundort = _sum_by(conn, "Fundort", wert_sql, top_wert_fundort)
    st.wert_pro_kategorie = _sum_by(conn, "Kategorie", wert_sql, top_wert_kategorie)
    # Kristallographische Sicht: welcher Symmetrietyp dominiert wertmaessig?
    # Komplementaer zu by_kristallsystem (Anzahl): trigonal-Quarz koennte ueber
    # viele kleine Stuecke den Wert dominieren, kubisch (Pyrit/Granat) hingegen
    # ueber wenige grosse - der Block macht das sichtbar.
    st.wert_pro_kristallsystem = _sum_by(
        conn, "Kristallsystem", wert_sql, top_wert_kristallsystem)
    # status: nur drei Werte (aktiv/platzhalter/archiviert); Limit von 10 reicht
    # uebergross, damit alle vorhandenen Status durchkommen. Beantwortet die Frage
    # "Wieviel Sammlungswert steckt im Archiv vs. aktiv vs. noch unbeschriftet?".
    st.wert_pro_status = _sum_by(conn, "status", wert_sql, 10)
    gewicht_where = "Gewicht_g IS NOT NULL AND Gewicht_g > 0"
    st.gewicht_pro_mineral = _sum_by(
        conn, "Mineral_Primaer", "Gewicht_g", top_gewicht_mineral,
        extra_where=gewicht_where)
    st.gewicht_pro_fundort = _sum_by(
        conn, "Fundort", "Gewicht_g", top_gewicht_fundort,
        extra_where=gewicht_where)
    st.gewicht_pro_kategorie = _sum_by(
        conn, "Kategorie", "Gewicht_g", top_gewicht_kategorie,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_kristallsystem: welcher Symmetrietyp traegt die
    # meiste Masse? Bei Quarz-/Pyrit-lastigen Sammlungen oft entkoppelt vom Wert.
    st.gewicht_pro_kristallsystem = _sum_by(
        conn, "Kristallsystem", "Gewicht_g", top_gewicht_kristallsystem,
        extra_where=gewicht_where)
    st.gewicht_pro_status = _sum_by(
        conn, "status", "Gewicht_g", 10, extra_where=gewicht_where)
    return st
