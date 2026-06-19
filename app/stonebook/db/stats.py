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
    by_varietaet: dict[str, int] = field(default_factory=dict)
    by_gesteinsart: dict[str, int] = field(default_factory=dict)
    by_kategorie: dict[str, int] = field(default_factory=dict)
    by_kristallsystem: dict[str, int] = field(default_factory=dict)
    by_glanz: dict[str, int] = field(default_factory=dict)
    by_transparenz: dict[str, int] = field(default_factory=dict)
    by_magnetismus: dict[str, int] = field(default_factory=dict)
    by_spaltbarkeit: dict[str, int] = field(default_factory=dict)
    by_bruch: dict[str, int] = field(default_factory=dict)
    by_beste_verwendung: dict[str, int] = field(default_factory=dict)
    by_fundort: dict[str, int] = field(default_factory=dict)
    by_funddatum_jahr: dict[str, int] = field(default_factory=dict)
    by_funddatum_jahrzehnt: dict[str, int] = field(default_factory=dict)
    by_funddatum_monat: dict[str, int] = field(default_factory=dict)
    by_erstellt_am_jahr: dict[str, int] = field(default_factory=dict)
    by_seltenheit_global: dict[str, int] = field(default_factory=dict)
    by_seltenheit_fundort: dict[str, int] = field(default_factory=dict)
    by_nachfrage: dict[str, int] = field(default_factory=dict)
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
    wert_pro_varietaet: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_gesteinsart: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_fundort: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_kategorie: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_kristallsystem: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_glanz: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_transparenz: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_magnetismus: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_spaltbarkeit: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_bruch: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_beste_verwendung: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_status: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_funddatum_jahr: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_funddatum_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_funddatum_monat: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_seltenheit_global: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_seltenheit_fundort: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_nachfrage: list[tuple[str, float]] = field(default_factory=list)
    wert_pro_confidence_bucket: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_mineral: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_varietaet: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_gesteinsart: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_fundort: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_kategorie: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_kristallsystem: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_glanz: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_transparenz: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_magnetismus: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_spaltbarkeit: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_bruch: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_beste_verwendung: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_status: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_funddatum_jahr: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_funddatum_jahrzehnt: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_funddatum_monat: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_seltenheit_global: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_seltenheit_fundort: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_nachfrage: list[tuple[str, float]] = field(default_factory=list)
    gewicht_pro_confidence_bucket: list[tuple[str, float]] = field(default_factory=list)
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
            "by_varietaet": dict(self.by_varietaet),
            "by_gesteinsart": dict(self.by_gesteinsart),
            "by_kategorie": dict(self.by_kategorie),
            "by_kristallsystem": dict(self.by_kristallsystem),
            "by_glanz": dict(self.by_glanz),
            "by_transparenz": dict(self.by_transparenz),
            "by_magnetismus": dict(self.by_magnetismus),
            "by_spaltbarkeit": dict(self.by_spaltbarkeit),
            "by_bruch": dict(self.by_bruch),
            "by_beste_verwendung": dict(self.by_beste_verwendung),
            "by_fundort": dict(self.by_fundort),
            "by_funddatum_jahr": dict(self.by_funddatum_jahr),
            "by_funddatum_jahrzehnt": dict(self.by_funddatum_jahrzehnt),
            "by_funddatum_monat": dict(self.by_funddatum_monat),
            "by_erstellt_am_jahr": dict(self.by_erstellt_am_jahr),
            "by_seltenheit_global": dict(self.by_seltenheit_global),
            "by_seltenheit_fundort": dict(self.by_seltenheit_fundort),
            "by_nachfrage": dict(self.by_nachfrage),
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
            "wert_pro_varietaet": [
                (var, round(w, 2)) for var, w in self.wert_pro_varietaet
            ],
            "wert_pro_gesteinsart": [
                (ges, round(w, 2)) for ges, w in self.wert_pro_gesteinsart
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
            "wert_pro_glanz": [
                (g, round(w, 2)) for g, w in self.wert_pro_glanz
            ],
            "wert_pro_transparenz": [
                (t, round(w, 2)) for t, w in self.wert_pro_transparenz
            ],
            "wert_pro_magnetismus": [
                (m, round(w, 2)) for m, w in self.wert_pro_magnetismus
            ],
            "wert_pro_spaltbarkeit": [
                (sp, round(w, 2)) for sp, w in self.wert_pro_spaltbarkeit
            ],
            "wert_pro_bruch": [
                (b, round(w, 2)) for b, w in self.wert_pro_bruch
            ],
            "wert_pro_beste_verwendung": [
                (bv, round(w, 2)) for bv, w in self.wert_pro_beste_verwendung
            ],
            "wert_pro_status": [
                (s, round(w, 2)) for s, w in self.wert_pro_status
            ],
            "wert_pro_funddatum_jahr": [
                (j, round(w, 2)) for j, w in self.wert_pro_funddatum_jahr
            ],
            "wert_pro_funddatum_jahrzehnt": [
                (d, round(w, 2)) for d, w in self.wert_pro_funddatum_jahrzehnt
            ],
            "wert_pro_funddatum_monat": [
                (m, round(w, 2)) for m, w in self.wert_pro_funddatum_monat
            ],
            "wert_pro_seltenheit_global": [
                (s, round(w, 2)) for s, w in self.wert_pro_seltenheit_global
            ],
            "wert_pro_seltenheit_fundort": [
                (s, round(w, 2)) for s, w in self.wert_pro_seltenheit_fundort
            ],
            "wert_pro_nachfrage": [
                (s, round(w, 2)) for s, w in self.wert_pro_nachfrage
            ],
            "wert_pro_confidence_bucket": [
                (b, round(w, 2)) for b, w in self.wert_pro_confidence_bucket
            ],
            "gewicht_pro_mineral": [
                (mineral, round(g, 2)) for mineral, g in self.gewicht_pro_mineral
            ],
            "gewicht_pro_varietaet": [
                (var, round(g, 2)) for var, g in self.gewicht_pro_varietaet
            ],
            "gewicht_pro_gesteinsart": [
                (ges, round(g, 2)) for ges, g in self.gewicht_pro_gesteinsart
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
            "gewicht_pro_glanz": [
                (glz, round(g, 2)) for glz, g in self.gewicht_pro_glanz
            ],
            "gewicht_pro_transparenz": [
                (t, round(g, 2)) for t, g in self.gewicht_pro_transparenz
            ],
            "gewicht_pro_magnetismus": [
                (m, round(g, 2)) for m, g in self.gewicht_pro_magnetismus
            ],
            "gewicht_pro_spaltbarkeit": [
                (sp, round(g, 2)) for sp, g in self.gewicht_pro_spaltbarkeit
            ],
            "gewicht_pro_bruch": [
                (b, round(g, 2)) for b, g in self.gewicht_pro_bruch
            ],
            "gewicht_pro_beste_verwendung": [
                (bv, round(g, 2)) for bv, g in self.gewicht_pro_beste_verwendung
            ],
            "gewicht_pro_status": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_status
            ],
            "gewicht_pro_funddatum_jahr": [
                (j, round(g, 2)) for j, g in self.gewicht_pro_funddatum_jahr
            ],
            "gewicht_pro_funddatum_jahrzehnt": [
                (d, round(g, 2)) for d, g in self.gewicht_pro_funddatum_jahrzehnt
            ],
            "gewicht_pro_funddatum_monat": [
                (m, round(g, 2)) for m, g in self.gewicht_pro_funddatum_monat
            ],
            "gewicht_pro_seltenheit_global": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_seltenheit_global
            ],
            "gewicht_pro_seltenheit_fundort": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_seltenheit_fundort
            ],
            "gewicht_pro_nachfrage": [
                (s, round(g, 2)) for s, g in self.gewicht_pro_nachfrage
            ],
            "gewicht_pro_confidence_bucket": [
                (b, round(g, 2)) for b, g in self.gewicht_pro_confidence_bucket
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


def _count_funddatum_monat(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro Funddatum-Monat (01..12), ueber alle Jahre aggregiert.

    Komplementaer zu :func:`_count_funddatum_jahr` (chronologisch) und
    :func:`_count_funddatum_jahrzehnt` (Dekaden): zeigt die Saison-Verteilung
    eines Sammler-Lebens - typisch sind Spitzen in Juli/August (Berg-Saison)
    und Dezember (Mineralienboerse Tucson/Muenchen). Label sind die Monats-
    Ziffern (``"01"`` .. ``"12"``); Monate ohne Treffer fehlen im Dict.

    Akzeptiert nur Funddaten in ISO-Form ``YYYY-MM-DD``/``YYYY-MM`` mit
    gueltigem Monatsteil 01-12; reine Jahresangaben (``"2024"``) haben keinen
    Monatsteil und werden ignoriert (sonst wuerden sie als "Monat 00" auf
    einen Default-Bucket fallen und die Saison-Statistik verzerren).
    """
    sql = (
        "SELECT substr(Funddatum, 6, 2) AS monat, COUNT(*) AS n FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
        "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "AND substr(Funddatum, 6, 2) GLOB '[0-1][0-9]' "
        "AND CAST(substr(Funddatum, 6, 2) AS INTEGER) BETWEEN 1 AND 12 "
        "GROUP BY monat ORDER BY monat ASC"
    )
    return {r["monat"]: r["n"] for r in conn.execute(sql).fetchall()}


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


def _count_erstellt_am_jahr(conn: sqlite3.Connection) -> dict[str, int]:
    """Zaehlt Objekte pro ``erstellt_am``-Jahr (Sammlungswachstum).

    Antwort auf die Sammler-Frage "wie ist meine Sammlung gewachsen?". Im
    Gegensatz zu :func:`_count_funddatum_jahr` (wann wurde gefunden) zaehlt
    dieser Block, wann das Objekt erfasst wurde - also wie aktiv pro Jahr
    erfasst/digitalisiert wurde, unabhaengig vom Fundzeitpunkt.

    ``erstellt_am`` wird beim Insert in repository.py auf
    ``YYYY-MM-DD HH:MM:SS`` gesetzt; der Substring-Trick auf den ersten vier
    Ziffern reicht und ist analog zu :func:`_count_funddatum_jahr`. NULL/
    Whitespace und Eintraege ohne vierstelligen Jahres-Praefix bleiben aus
    der Statistik (historische Imports koennten leere Stempel haben).

    Sortierung: chronologisch aufsteigend (aelteste Jahre zuerst), damit das
    Wachstums-Histogramm zeitlich lesbar bleibt. Ohne Limit, weil die Zahl der
    Jahre ueberschaubar bleibt (~10-30 ueber eine Sammler-Karriere).
    """
    sql = (
        "SELECT substr(erstellt_am, 1, 4) AS jahr, COUNT(*) AS n FROM objects "
        "WHERE erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
        "AND substr(erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
        "GROUP BY jahr ORDER BY jahr ASC"
    )
    return {r["jahr"]: r["n"] for r in conn.execute(sql).fetchall()}


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


SCALE_1_10_COLUMNS: frozenset[str] = frozenset({
    "Seltenheit_global_1_10", "Seltenheit_Fundort_1_10", "Nachfrage_1_10",
})


def _count_scale_1_10(conn: sqlite3.Connection, column: str) -> dict[str, int]:
    """Zaehlt Objekte pro 1..10-Skalenwert (Seltenheit/Nachfrage).

    Ignoriert NULL und out-of-range-Werte (die werden separat in
    :func:`check_integrity` gemeldet und wuerden die Bucket-Sicht verzerren).
    Liefert ein Dict in chronologischer Skalen-Reihenfolge (1..10 aufsteigend);
    Skalenwerte ohne Treffer fehlen, damit der Dashboard-Bar-Chart nicht von
    leeren Buckets dominiert wird. Komplementaer zu :func:`_confidence_buckets`
    (0..100 in 5 Bucketts), hier feiner aufgeloest weil die Skala kleiner ist.

    ``column`` wird gegen :data:`SCALE_1_10_COLUMNS` validiert, um SQL-Injection
    ueber freie Spaltennamen auszuschliessen.
    """
    if column not in SCALE_1_10_COLUMNS:
        raise ValueError(f"Unzulaessige Skalen-Spalte: {column}")
    rows = conn.execute(
        f"SELECT {column} AS k, COUNT(*) AS n FROM objects "
        f"WHERE {column} IS NOT NULL AND {column} BETWEEN 1 AND 10 "
        f"GROUP BY k ORDER BY k ASC"
    ).fetchall()
    return {str(r["k"]): r["n"] for r in rows}


def _sum_by_scale_1_10(conn: sqlite3.Connection, column: str, value_sql: str,
                       extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach 1..10-Skalenwert.

    Pendant zu :func:`_count_scale_1_10` (Anzahl), aber summiert Wert/Gewicht
    je Skalen-Bucket. Komplementaer zum ``seltenheit_global_min/max``-Filter
    (Drill-down auf einzelne Stuecke); hier die Wert-/Massen-Verteilung ueber
    die Rarity-/Nachfrage-Achse - macht "wo steckt der Wert in der seltenen
    Spitze (>=8) vs. in der Masse (<=3)?" sichtbar.

    Sortierung: absteigend nach Summe, Tie-Break aufsteigend nach Skalenwert
    (analog zu :func:`_sum_by`). Ohne Limit, weil maximal 10 Buckets vorkommen
    koennen - die Ausgabe wird nie laenger. Out-of-Range-Werte (<1 / >10)
    bleiben ausgeschlossen, damit die Aggregate nicht durch kaputte Skalen-
    Eintraege verzerrt werden (Integrity meldet die separat).

    ``column`` wird gegen :data:`SCALE_1_10_COLUMNS` validiert, um SQL-Injection
    ueber freie Spaltennamen auszuschliessen.
    """
    if column not in SCALE_1_10_COLUMNS:
        raise ValueError(f"Unzulaessige Skalen-Spalte: {column}")
    where = f"{column} IS NOT NULL AND {column} BETWEEN 1 AND 10"
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT {column} AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC"
    )
    return [(str(r["k"]), float(r["w"])) for r in conn.execute(sql).fetchall()]


CONFIDENCE_BUCKET_ORDER: tuple[str, ...] = ("ohne", "0-24", "25-49", "50-74", "75-100")


def _confidence_bucket_case_sql(column: str = "Confidence_Prozent") -> str:
    """SQL-CASE-Ausdruck, der einen Confidence-Wert auf den Bucket-Namen abbildet.

    Geteilt von :func:`_confidence_buckets` (Anzahl) und
    :func:`_sum_by_confidence_bucket` (Wert/Gewicht), damit die Bucket-Grenzen
    nur an einer Stelle definiert sind und die beiden Aggregate garantiert
    deckungsgleich klassifizieren.
    """
    return (
        "CASE "
        f"  WHEN {column} IS NULL THEN 'ohne' "
        f"  WHEN {column} BETWEEN 0 AND 24 THEN '0-24' "
        f"  WHEN {column} BETWEEN 25 AND 49 THEN '25-49' "
        f"  WHEN {column} BETWEEN 50 AND 74 THEN '50-74' "
        f"  WHEN {column} BETWEEN 75 AND 100 THEN '75-100' "
        "  ELSE NULL END"
    )


def _sum_by_confidence_bucket(conn: sqlite3.Connection, value_sql: str,
                              extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Confidence-Bucket.

    Pendant zu :func:`_confidence_buckets` (Anzahl): summiert Wert/Gewicht je
    25-Prozent-Klasse plus 'ohne' (NULL Confidence). Beantwortet die
    Sammler-Frage "wieviel Wert/Masse haengt an Stuecken, denen die KI nicht
    vertraut (<50) vs. an sicheren Bestimmungen (75-100)?".

    Sortierung: absteigend nach Summe, Tiebreak nach
    :data:`CONFIDENCE_BUCKET_ORDER` (also 'ohne' vor '0-24' vor ...).
    Out-of-Range-Werte (<0 oder >100) zaehlen nicht; sie werden in
    :func:`check_integrity` separat gemeldet und wuerden hier nur Rauschen
    produzieren.
    """
    where = "1=1"
    if extra_where:
        where = extra_where
    bucket_sql = _confidence_bucket_case_sql()
    sql = (
        f"SELECT {bucket_sql} AS bucket, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY bucket HAVING bucket IS NOT NULL AND w > 0"
    )
    rows = [(str(r["bucket"]), float(r["w"]))
            for r in conn.execute(sql).fetchall()]
    order_index = {b: i for i, b in enumerate(CONFIDENCE_BUCKET_ORDER)}
    rows.sort(key=lambda r: (-r[1], order_index.get(r[0], len(CONFIDENCE_BUCKET_ORDER))))
    return rows


def _confidence_buckets(conn: sqlite3.Connection) -> dict[str, int]:
    """Verteilung der Confidence-Werte auf 25-Prozent-Klassen + 'ohne' (NULL).

    Liefert ein Dict in fester Reihenfolge ``CONFIDENCE_BUCKET_ORDER``; Klassen
    ohne Treffer bleiben mit 0 enthalten, damit das Dashboard eine stabile
    Bar-Reihenfolge zeichnen kann. Out-of-Range-Werte (<0 oder >100) zaehlen
    nicht mit; sie werden separat in :func:`check_integrity` gemeldet.
    """
    counts = dict.fromkeys(CONFIDENCE_BUCKET_ORDER, 0)
    rows = conn.execute(
        f"SELECT {_confidence_bucket_case_sql()} AS bucket, COUNT(*) AS n "
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


def _sum_by_funddatum_monat(conn: sqlite3.Connection, value_sql: str,
                            extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Funddatum-Monat (01..12).

    Pendant zu :func:`_sum_by_funddatum_jahr`, aggregiert ueber alle Jahre.
    Selektiert nur Eintraege mit gueltigem Monatsteil 01..12; reine Jahres-
    angaben ohne Monat fallen weg (siehe :func:`_count_funddatum_monat`).

    Top-N absteigend nach Summe; Tie-Break aufsteigend nach Monat. Ohne Limit,
    weil maximal 12 Monate vorkommen koennen - die Ausgabe wird nie laenger.
    """
    where = ("Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
             "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
             "AND substr(Funddatum, 6, 2) GLOB '[0-1][0-9]' "
             "AND CAST(substr(Funddatum, 6, 2) AS INTEGER) BETWEEN 1 AND 12")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(Funddatum, 6, 2) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_funddatum_jahrzehnt(conn: sqlite3.Connection, value_sql: str,
                                extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Funddatum-Jahrzehnt (Dekade).

    Pendant zu :func:`_count_funddatum_jahrzehnt` (Anzahl), aber summiert
    Wert/Gewicht je Dekaden-Bucket. Label folgt der Sammler-Konvention
    (``1980er``, ``1990er``, ...). Sortierung absteigend nach Summe; bei
    Gleichstand chronologisch aufsteigend. Ohne Limit, weil die Zahl der
    Dekaden (~10-15 ueber ein Sammlerleben) klein bleibt.
    """
    where = ("Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
             "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT (CAST(substr(Funddatum, 1, 4) AS INTEGER) / 10) * 10 AS dekade, "
        f"       SUM({value_sql}) AS w FROM objects WHERE {where} "
        f"GROUP BY dekade HAVING w > 0 "
        f"ORDER BY w DESC, dekade ASC"
    )
    return [(f"{r['dekade']}er", float(r["w"])) for r in conn.execute(sql).fetchall()]


def _sum_by_funddatum_jahr(conn: sqlite3.Connection, value_sql: str,
                           limit: int,
                           extra_where: str = "") -> list[tuple[str, float]]:
    """Aggregiert ``SUM(value_sql)`` gruppiert nach Funddatum-Jahr.

    Pendant zu :func:`_sum_by` fuer Spalten, ergaenzt um den Substring-Trick fuer
    das Funddatum-Jahr. Selektiert nur Eintraege mit gueltigem Jahres-Praefix
    (vier Ziffern); andere Funddaten haben kein verlaessliches Jahr und wuerden
    die Aggregate verzerren (siehe :func:`_count_funddatum_jahr`).

    Top-N absteigend nach Summe; Tie-Break aufsteigend nach Jahr - damit das
    "bestes Sammeljahr"-Ranking stabil bleibt und gleichwertige Jahre
    chronologisch hintereinander stehen.
    """
    where = ("Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
             "AND substr(Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
    if extra_where:
        where = f"{where} AND {extra_where}"
    sql = (
        f"SELECT substr(Funddatum, 1, 4) AS k, SUM({value_sql}) AS w "
        f"FROM objects WHERE {where} "
        f"GROUP BY k HAVING w > 0 "
        f"ORDER BY w DESC, k ASC LIMIT ?"
    )
    return [(r["k"], float(r["w"])) for r in conn.execute(sql, (int(limit),)).fetchall()]


def compute_statistics(conn: sqlite3.Connection, top_fundorte: int = 10,
                       top_wert: int = 10, top_jahre: int | None = None,
                       top_wert_mineral: int = 10,
                       top_gewicht_mineral: int = 10,
                       top_wert_varietaet: int = 10,
                       top_gewicht_varietaet: int = 10,
                       top_wert_gesteinsart: int = 10,
                       top_gewicht_gesteinsart: int = 10,
                       top_wert_fundort: int = 10,
                       top_gewicht_fundort: int = 10,
                       top_wert_kategorie: int = 10,
                       top_gewicht_kategorie: int = 10,
                       top_wert_kristallsystem: int = 10,
                       top_gewicht_kristallsystem: int = 10,
                       top_wert_glanz: int = 10,
                       top_gewicht_glanz: int = 10,
                       top_wert_transparenz: int = 10,
                       top_gewicht_transparenz: int = 10,
                       top_wert_magnetismus: int = 10,
                       top_gewicht_magnetismus: int = 10,
                       top_wert_spaltbarkeit: int = 10,
                       top_gewicht_spaltbarkeit: int = 10,
                       top_wert_bruch: int = 10,
                       top_gewicht_bruch: int = 10,
                       top_wert_beste_verwendung: int = 10,
                       top_gewicht_beste_verwendung: int = 10,
                       top_gewicht: int = 10,
                       top_bilder: int = 10,
                       top_confidence: int = 10,
                       top_wert_funddatum_jahr: int = 10,
                       top_gewicht_funddatum_jahr: int = 10) -> Statistik:
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
    # Varietaeten-Verteilung als feinere Sicht unter dem Hauptmineral: Quarz allein
    # sagt wenig - "Bergkristall", "Milchquarz", "Rauchquarz" trennt die Sammlung
    # auf der fuer Sammler interessanten Granularitaet. Ergaenzt by_mineral, das
    # auf der mineralogischen Hauptgruppe bleibt.
    st.by_varietaet = _count_by(conn, "Varietaet")
    # Petrologische Sicht: welche Gesteinsart traegt die Sammlung? Granit/Gneis/
    # Basalt/Sandstein gruppieren Stuecke nach geologischem Zusammenhang, der
    # weder durch Mineral_Primaer (mineralogisch) noch durch Kategorie (Form/
    # Aufbewahrung) abgedeckt ist. Ergaenzt by_varietaet (Mineral-Familie) um
    # die uebergeordnete Gesteins-Sicht.
    st.by_gesteinsart = _count_by(conn, "Gesteinsart")
    st.by_kategorie = _count_by(conn, "Kategorie")
    st.by_kristallsystem = _count_by(conn, "Kristallsystem")
    # Optische Sicht: welche Glanz-Charakteristik dominiert die Sammlung?
    # Glasiger Quarz vs. metallischer Pyrit vs. matter Sandstein trennt die
    # Sammlung auf einer Achse, die weder mineralogisch (by_mineral) noch
    # kristallographisch (by_kristallsystem) sichtbar ist. Sieben Enum-Werte
    # aus dem Feldwoerterbuch (glasig/wachsig/matt/metallisch/fettig/seidig/perlmutt).
    st.by_glanz = _count_by(conn, "Glanz")
    # Lichtdurchlaessigkeits-Sicht: wie transparent ist die Sammlung im Schnitt?
    # Komplementaer zu by_glanz (Oberflaechen-Reflexion vs. Volumen-Lichtgang):
    # durchsichtiger Bergkristall, durchscheinender Achat, opaker Pyrit liegen
    # optisch nebeneinander, brauchen aber unterschiedliches Licht-Setup beim
    # Fotografieren. Drei Enum-Werte (durchsichtig/durchscheinend/opak).
    st.by_transparenz = _count_by(conn, "Transparenz")
    # Magnetismus-Sicht: welcher Anteil der Sammlung reagiert auf den Magneten?
    # Drei Enum-Werte aus dem Feldwoerterbuch (ja/schwach/nein) - praktischer
    # Indikator fuer Magnetit/Pyrrhotin-Anteil (stark), Haematit/Ilmenit
    # (schwach) und alles uebrige (nein). Komplementaer zu by_mineral
    # (mineralogisch) und by_glanz (optisch): hier die physikalische
    # Eisengehalt-Achse, die mineralogisch quer durch alle Hauptgruppen geht.
    st.by_magnetismus = _count_by(conn, "Magnetismus")
    # Mineralogische Sicht: welche Spaltbarkeit dominiert die Sammlung?
    # Fuenf Enum-Werte aus dem Feldwoerterbuch (vollkommen/gut/deutlich/
    # undeutlich/keine) - klassische Lehrbuch-Sicht (Calcit/Fluorit/Glimmer:
    # vollkommen; Quarz: keine; Granat: deutlich). Komplementaer zu by_bruch
    # (Bruchverhalten) und by_glanz (Oberflaechen-Reflexion): hier die
    # Spaltflaechen-Charakteristik, die das Polieren/Praeparieren bestimmt.
    st.by_spaltbarkeit = _count_by(conn, "Spaltbarkeit")
    # Mineralogische Sicht: welches Bruchverhalten dominiert die Sammlung?
    # Sechs Enum-Werte aus dem Feldwoerterbuch (muschelig/uneben/splittrig/
    # faserig/erdig/glatt) - klassische Lehrbuch-Sicht (Quarz/Obsidian:
    # muschelig; Kupfer/Silber: hakig-uneben; Asbest: faserig). Komplementaer
    # zu by_spaltbarkeit (Spaltflaechen): Stuecke mit keiner Spaltbarkeit
    # zeigen ihr Bruchverhalten am deutlichsten - der Block macht das transparent.
    st.by_bruch = _count_by(conn, "Bruch")
    st.by_beste_verwendung = _count_by(conn, "Beste_Verwendung")
    st.by_fundort = _count_by(conn, "Fundort", limit=top_fundorte)
    # Diversitaets-Kennzahlen: Anzahl distinct, unabhaengig von Top-N-Limits.
    st.mineral_arten_total = _count_distinct(conn, "Mineral_Primaer")
    st.fundorte_total = _count_distinct(conn, "Fundort")

    st.by_funddatum_jahr = _count_funddatum_jahr(conn, limit=top_jahre)
    st.by_funddatum_jahrzehnt = _count_funddatum_jahrzehnt(conn)
    st.by_funddatum_monat = _count_funddatum_monat(conn)
    # Sammlungswachstum-Histogramm: Objekte pro Jahr ihres erstellt_am-Stempels.
    # Komplementaer zu by_funddatum_jahr (wann gefunden) - hier wann erfasst.
    # Beantwortet "in welchen Jahren bin ich besonders aktiv im Digitalisieren gewesen?"
    # und macht ungleichmaessige Migrations-Wellen (z.B. eine grosse Erfassungs-
    # session 2026) sichtbar, die in der reinen Funddatums-Sicht untergehen.
    st.by_erstellt_am_jahr = _count_erstellt_am_jahr(conn)
    # Rarity-Histogramm: wie verteilt sich die Sammlung auf der globalen
    # Seltenheits-Skala (1=haeufig .. 10=sehr selten)? Komplementaer zu den
    # seltenheit_global_min/max-Filtern: zeigt nicht nur "ein Stueck ist hier
    # >=8", sondern wo das ganze Bestand-Schwerpunkt liegt. Sammler-typische
    # Diagnose vor Versicherungseinschaetzung (viel haeufiges Material vs.
    # konzentriert teure Rarit?ten).
    st.by_seltenheit_global = _count_scale_1_10(conn, "Seltenheit_global_1_10")
    # Fundort-Rarity-Histogramm: am Standort selten vs. global selten - oft
    # verschieden, siehe SORTABLE_COLUMNS-Kommentar zu Seltenheit_Fundort. Ein
    # Stueck kann am Fundort haeufig (Quarz aus Berner Oberland) aber global
    # selten sein (oder umgekehrt: lokale Rarit?t aus einem ausgeschoepften
    # Stollen). Spiegelt by_seltenheit_global; nutzt denselben Helper und denselben
    # 1..10-Skala-Validator (out-of-range bleibt der Integrity ueberlassen).
    st.by_seltenheit_fundort = _count_scale_1_10(conn, "Seltenheit_Fundort_1_10")
    # Marktnachfrage-Histogramm 1..10: wo liegt der Marktdruck-Schwerpunkt der
    # Sammlung? Komplementaer zum nachfrage_min/max-Filter (Drill-down auf
    # Verkaufs-Kandidaten); hier die Gesamtverteilung. Beantwortet Sammler-
    # typische Frage vor Boersenbesuch ("habe ich genug Stuecke mit Nachfrage>=7,
    # die sich verkaufen lassen, oder sitze ich auf reinem Tauschmaterial?").
    st.by_nachfrage = _count_scale_1_10(conn, "Nachfrage_1_10")
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
    # Varietaeten-Wert-Sicht: feinere Aufteilung unter dem Hauptmineral.
    # Komplementaer zu wert_pro_mineral (Hauptgruppe): "Bergkristall" vs.
    # "Milchquarz" innerhalb der Quarz-Familie laufen wertlich oft weit
    # auseinander; der Block zeigt, welche Varietaet das Geld traegt.
    st.wert_pro_varietaet = _sum_by(conn, "Varietaet", wert_sql, top_wert_varietaet)
    # Petrologische Wert-Sicht: welche Gesteinsart traegt den Sammlungswert?
    # Granit-Stuecke vs. Gneis-/Basalt-Stuecke liegen oft auf ganz unterschied-
    # lichen Preis-Niveaus (z.B. Edelgranite vs. Halden-Basalt); der Block
    # macht das transparent, komplementaer zu by_gesteinsart (Anzahl).
    st.wert_pro_gesteinsart = _sum_by(
        conn, "Gesteinsart", wert_sql, top_wert_gesteinsart)
    st.wert_pro_fundort = _sum_by(conn, "Fundort", wert_sql, top_wert_fundort)
    st.wert_pro_kategorie = _sum_by(conn, "Kategorie", wert_sql, top_wert_kategorie)
    # Kristallographische Sicht: welcher Symmetrietyp dominiert wertmaessig?
    # Komplementaer zu by_kristallsystem (Anzahl): trigonal-Quarz koennte ueber
    # viele kleine Stuecke den Wert dominieren, kubisch (Pyrit/Granat) hingegen
    # ueber wenige grosse - der Block macht das sichtbar.
    st.wert_pro_kristallsystem = _sum_by(
        conn, "Kristallsystem", wert_sql, top_wert_kristallsystem)
    # Optische Wert-Sicht: welcher Glanztyp traegt den Sammlungswert? Glasige
    # Quarz-Sammlungen vs. metallische Sulfide vs. matte Sedimentstuecke laufen
    # wertlich oft weit auseinander; der Block macht das transparent.
    # Komplementaer zu by_glanz (Anzahl).
    st.wert_pro_glanz = _sum_by(
        conn, "Glanz", wert_sql, top_wert_glanz)
    # Lichtdurchlaessigkeits-Wert-Sicht: welcher Transparenz-Typ traegt den
    # Sammlungswert? Komplementaer zu by_transparenz (Anzahl) und
    # wert_pro_glanz (Oberflaechen-Reflexion): durchsichtiger Bergkristall vs.
    # durchscheinender Achat vs. opaker Pyrit liegen wertlich oft auf ganz
    # unterschiedlichen Niveaus - der Block macht das transparent. Drei
    # Enum-Werte (durchsichtig/durchscheinend/opak); Limit von 10 reicht ueber-
    # gross, damit alle vorhandenen Stufen durchkommen.
    st.wert_pro_transparenz = _sum_by(
        conn, "Transparenz", wert_sql, top_wert_transparenz)
    # Magnetismus-Wert-Sicht: welcher Eisengehalts-Typ traegt den Sammlungswert?
    # Magnetit/Pyrrhotin-Stuecke (ja) liegen wertlich oft auf einem ganz anderen
    # Niveau als inerte Quarz-/Calcit-Stuecke (nein) oder schwach magnetische
    # Haematit-Stuecke (schwach). Komplementaer zu by_magnetismus (Anzahl) und
    # wert_pro_glanz/wert_pro_transparenz (optische Achsen): hier die
    # physikalische Eisengehalt-Achse.
    st.wert_pro_magnetismus = _sum_by(
        conn, "Magnetismus", wert_sql, top_wert_magnetismus)
    # Spaltbarkeits-Wert-Sicht: welche Spaltflaechen-Klasse traegt den
    # Sammlungswert? Komplementaer zu by_spaltbarkeit (Anzahl): Calcit/Fluorit
    # (vollkommen) ergeben oft viele kleine wertvolle Stuecke, Quarz (keine)
    # traegt ueber wenige grosse Stuecke. Praeparier-relevant: gut spaltbare
    # Stuecke lassen sich saubrer schneiden, was die Polier-Empfehlung und
    # damit Wert_CHF_poliert beeinflusst. Fuenf Enum-Werte aus dem Feld-
    # woerterbuch (vollkommen/gut/deutlich/undeutlich/keine); Limit von 10
    # reicht uebergross, damit alle vorhandenen Stufen durchkommen.
    st.wert_pro_spaltbarkeit = _sum_by(
        conn, "Spaltbarkeit", wert_sql, top_wert_spaltbarkeit)
    # Bruch-Wert-Sicht: welche Bruchverhalten-Klasse traegt den Sammlungswert?
    # Komplementaer zu by_bruch (Anzahl) und wert_pro_spaltbarkeit
    # (Spaltflaechen): muschelig brechende Quarz-/Obsidian-Stuecke liegen
    # wertlich oft auf einem anderen Niveau als fasrige Asbest-/Aktinolith-
    # Stuecke oder hakig-unebene Kupfer-/Silber-Plaettchen. Sechs Enum-Werte
    # aus dem Feldwoerterbuch (muschelig/uneben/splittrig/faserig/erdig/glatt).
    st.wert_pro_bruch = _sum_by(
        conn, "Bruch", wert_sql, top_wert_bruch)
    # Verwendungs-Sicht: wo steckt der Wert je Empfehlung (Schmuck/Sammlung/
    # Forschung/Industrie/Talisman/Dekoration)? Beantwortet "lohnt sich ein
    # Schmuck-Verkauf, oder steckt der Wert eher in Forschungs-/Sammler-Stuecken?".
    st.wert_pro_beste_verwendung = _sum_by(
        conn, "Beste_Verwendung", wert_sql, top_wert_beste_verwendung)
    # status: nur drei Werte (aktiv/platzhalter/archiviert); Limit von 10 reicht
    # uebergross, damit alle vorhandenen Status durchkommen. Beantwortet die Frage
    # "Wieviel Sammlungswert steckt im Archiv vs. aktiv vs. noch unbeschriftet?".
    st.wert_pro_status = _sum_by(conn, "status", wert_sql, 10)
    gewicht_where = "Gewicht_g IS NOT NULL AND Gewicht_g > 0"
    st.gewicht_pro_mineral = _sum_by(
        conn, "Mineral_Primaer", "Gewicht_g", top_gewicht_mineral,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_varietaet: welche Varietaet dominiert
    # gewichtsmaessig? Milchquarz-Geroelle vs. wenige feine Bergkristalle
    # entkoppeln sich oft vom Wert (viel Masse fuer wenig Geld).
    st.gewicht_pro_varietaet = _sum_by(
        conn, "Varietaet", "Gewicht_g", top_gewicht_varietaet,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_gesteinsart: welche Gesteinsart bringt die meiste
    # Masse? Basalt-/Granit-Geroelle dominieren oft die Sammlung gewichts-
    # maessig, ohne wertlich vorne zu liegen - der Block macht das sichtbar.
    st.gewicht_pro_gesteinsart = _sum_by(
        conn, "Gesteinsart", "Gewicht_g", top_gewicht_gesteinsart,
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
    # Spiegelbild zu wert_pro_glanz: welcher Glanztyp dominiert gewichtsmaessig?
    # Matte Geroellstuecke (Sediment) tragen oft die Sammlungsmasse, glasige
    # Kristalle den Wert - die Wert/Gewicht-Entkopplung wird auf der optischen
    # Achse sichtbar (analog zu kristallsystem-/varietaet-/gesteinsart-Aufteilung).
    st.gewicht_pro_glanz = _sum_by(
        conn, "Glanz", "Gewicht_g", top_gewicht_glanz,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_transparenz: welcher Transparenz-Typ traegt die
    # meiste Masse? Opake Geroellstuecke (Sediment, Pyrit) dominieren oft die
    # Sammlungsmasse, durchsichtige Kristalle den Wert - die Wert/Gewicht-
    # Entkopplung wird auch auf der Lichtdurchlaessigkeits-Achse sichtbar.
    st.gewicht_pro_transparenz = _sum_by(
        conn, "Transparenz", "Gewicht_g", top_gewicht_transparenz,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_magnetismus: welcher Eisengehalts-Typ traegt die
    # meiste Masse? Schwere Magnetit-Brocken (ja) heben das Gewicht in einer
    # Kategorie, die wertlich oft hinter klassischen Quarz-Stuecken zurueckbleibt.
    # Die Wert/Gewicht-Entkopplung wird auch auf der Magnetismus-Achse sichtbar.
    st.gewicht_pro_magnetismus = _sum_by(
        conn, "Magnetismus", "Gewicht_g", top_gewicht_magnetismus,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_spaltbarkeit: welche Spaltflaechen-Klasse traegt
    # die meiste Masse? Glimmer-Plaettchen (vollkommen) sind oft leicht und
    # zahlreich, dichte Quarz-Brocken (keine) tragen den Schwerteil. Die
    # Wert/Gewicht-Entkopplung wird auch auf der Spaltflaechen-Achse sichtbar.
    st.gewicht_pro_spaltbarkeit = _sum_by(
        conn, "Spaltbarkeit", "Gewicht_g", top_gewicht_spaltbarkeit,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_bruch: welche Bruchverhalten-Klasse traegt die
    # meiste Masse? Dichte muschelig brechende Obsidian-Brocken tragen oft
    # den Schwerteil, fasrige Aktinolith-Buendel bleiben leicht. Die Wert/
    # Gewicht-Entkopplung wird auch auf der Bruchverhalten-Achse sichtbar.
    st.gewicht_pro_bruch = _sum_by(
        conn, "Bruch", "Gewicht_g", top_gewicht_bruch,
        extra_where=gewicht_where)
    # Spiegelbild zu wert_pro_beste_verwendung: welche Verwendungs-Kategorie
    # bringt die meiste Masse? Industrie/Dekoration oft schwer, Schmuck oft
    # leicht aber hochpreisig - der Block macht den Unterschied sichtbar.
    st.gewicht_pro_beste_verwendung = _sum_by(
        conn, "Beste_Verwendung", "Gewicht_g", top_gewicht_beste_verwendung,
        extra_where=gewicht_where)
    st.gewicht_pro_status = _sum_by(
        conn, "status", "Gewicht_g", 10, extra_where=gewicht_where)
    # Zeit-Sicht des Sammlungswerts: "in welchem Funddatum-Jahr ist der hoechste
    # Wert/das hoechste Gewicht zusammengekommen?" Komplementaer zu
    # by_funddatum_jahr (Anzahl): zeigt nicht "wie viele Stuecke", sondern "wie
    # wertvoll/schwer war die Ausbeute". Beantwortet Sammler-Fragen wie "mein
    # bestes Jahr 2019 hatte zwar wenige Funde, aber einen seltenen Riesen-
    # kristall - taucht hier ganz oben auf".
    st.wert_pro_funddatum_jahr = _sum_by_funddatum_jahr(
        conn, wert_sql, top_wert_funddatum_jahr)
    st.gewicht_pro_funddatum_jahr = _sum_by_funddatum_jahr(
        conn, "Gewicht_g", top_gewicht_funddatum_jahr,
        extra_where=gewicht_where)
    # Dekaden-Sicht des Sammlungswerts: "in welchem Jahrzehnt habe ich am meisten
    # Wert/Masse zusammengetragen?". Komplementaer zu wert_pro_funddatum_jahr
    # (Einzeljahres-Rauschen): zeigt grobe Aktivitaetsphasen ohne Verzerrung
    # durch einzelne Ausreisserjahre. Ohne Limit (max ~10-15 Dekaden).
    st.wert_pro_funddatum_jahrzehnt = _sum_by_funddatum_jahrzehnt(conn, wert_sql)
    st.gewicht_pro_funddatum_jahrzehnt = _sum_by_funddatum_jahrzehnt(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Saison-Sicht des Sammlungswerts: "welcher Monat bringt am meisten Wert/
    # Gewicht?". Komplementaer zu by_funddatum_monat (Anzahl): zeigt nicht
    # "wie oft sammle ich im Juli", sondern "wie ergiebig ist die Juli-Saison".
    # Berg-Saison (Jul/Aug) gegen Boersen-Spitzen (Dez/Feb) werden so
    # vergleichbar; keine Limit-Parameter, weil max 12 Eintraege moeglich.
    st.wert_pro_funddatum_monat = _sum_by_funddatum_monat(conn, wert_sql)
    st.gewicht_pro_funddatum_monat = _sum_by_funddatum_monat(
        conn, "Gewicht_g", extra_where=gewicht_where)
    # Rarity-Wert-/Gewicht-Sicht: wie verteilt sich Sammlungswert/Masse auf der
    # globalen Seltenheits-Skala (1..10)? Komplementaer zu by_seltenheit_global
    # (Anzahl): zeigt nicht "wie viele Stuecke pro Stufe", sondern "wo steckt
    # der Wert/das Gewicht" - typisch konzentriert sich der Wert in den oberen
    # Stufen (>=8 Rarit?ten), waehrend das Gewicht in der haeufigen Masse (<=3)
    # liegt. Skala-Spalte wird ueber SCALE_1_10_COLUMNS validiert.
    st.wert_pro_seltenheit_global = _sum_by_scale_1_10(
        conn, "Seltenheit_global_1_10", wert_sql)
    st.gewicht_pro_seltenheit_global = _sum_by_scale_1_10(
        conn, "Seltenheit_global_1_10", "Gewicht_g",
        extra_where=gewicht_where)
    # Standort-Rarity-Wert-/Gewicht-Sicht: spiegelt wert_/gewicht_pro_seltenheit_global,
    # diesmal auf der lokalen Skala. Am Standort haeufiger Quarz (lokal niedrig)
    # kann global selten und damit wertvoll sein - oder umgekehrt: eine lokale
    # Rarit?t aus einem ausgeschoepften Stollen wertet weniger als global selten.
    # Beide Aggregate zusammen zeigen, ob "lokale Spitze" und "globale Spitze"
    # zusammenfallen oder auseinanderdriften (interessant fuer Sammlungs-Schwerpunkte).
    st.wert_pro_seltenheit_fundort = _sum_by_scale_1_10(
        conn, "Seltenheit_Fundort_1_10", wert_sql)
    st.gewicht_pro_seltenheit_fundort = _sum_by_scale_1_10(
        conn, "Seltenheit_Fundort_1_10", "Gewicht_g",
        extra_where=gewicht_where)
    # Marktnachfrage-Wert-/Gewicht-Sicht: wo liegt der Verkaufs-Druck im
    # Sammlungs-Wert/-Gewicht? Komplementaer zu by_nachfrage (Anzahl) und
    # nachfrage_min/max-Filter (Drill-down auf einzelne Stuecke): zeigt, ob
    # die hochpreisigen Stuecke gerade auf den begehrten Skalen-Stufen (>=7)
    # liegen oder ob das Geld in Tauschmaterial (<=3) gebunden ist.
    # Sammler-typisch vor Boersenbesuch: "habe ich genug verkaufsfaehige Masse,
    # oder traegt die Verkaufs-Spitze nur Einzelstuecke?".
    st.wert_pro_nachfrage = _sum_by_scale_1_10(
        conn, "Nachfrage_1_10", wert_sql)
    st.gewicht_pro_nachfrage = _sum_by_scale_1_10(
        conn, "Nachfrage_1_10", "Gewicht_g",
        extra_where=gewicht_where)
    # Confidence-Wert-Sicht: wieviel Sammlungswert haengt an "sicheren"
    # Bestimmungen (75-100) vs. an noch unsicheren Stuecken (<50) vs. an
    # unbestimmten Stuecken (Confidence NULL, Bucket 'ohne')? Spiegelt
    # confidence_buckets (Anzahl) auf die Wert-Achse: konzentriert sich der
    # Sammlungswert dort, wo die KI sicher ist - oder steckt er gerade in
    # den noch zu pruefenden Stuecken, deren Pruefempfehlungen prioritaer
    # sind? Komplementaer zu top_confidence_objekte (Spitze) und
    # durchschnitt_/median_confidence_prozent (zentrale Tendenz).
    st.wert_pro_confidence_bucket = _sum_by_confidence_bucket(conn, wert_sql)
    # Spiegelbild zu wert_pro_confidence_bucket: wieviel Sammlungs-Gewicht
    # haengt an unbestimmten Stuecken (Bucket 'ohne') vs. an sicher
    # identifizierten (75-100)? Wert/Gewicht-Entkopplung auf der Confidence-
    # Achse: typisch sitzen schwere Geroellstuecke ohne KI-Analyse im
    # 'ohne'-Bucket, waehrend wertvolle Kristalle mit klarer Bestimmung den
    # 75-100-Bucket fuellen - der Block macht das transparent.
    st.gewicht_pro_confidence_bucket = _sum_by_confidence_bucket(
        conn, "Gewicht_g", extra_where=gewicht_where)
    return st
