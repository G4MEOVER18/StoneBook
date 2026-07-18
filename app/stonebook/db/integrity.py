"""Konsistenzprüfungen über die Objekt-DB (für Wartung/Diagnose)."""
from __future__ import annotations

import datetime
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from stonebook.fields import DATA_FIELDS, FIELD_BY_NAME, IMAGE_CATEGORIES
from stonebook.migration.validators import parse_iso_date

# Trailing parenthesized Annotation ("(mikrokristallin)", "(rhomboedrisch)",
# "[saeulenfoermig]"). In mineralogischen Notizen sehr verbreitet als
# Sub-Klassifizierungs-Suffix nach dem Enum-Wert: Kristallgroesse
# ("(mikrokristallin)"), Kristallhabitus ("(saeulenfoermig)") oder alternative
# Schreibweise ("(rhomboedrisch)" zu trigonal). Die Annotation aendert die
# Basis-Klassifikation nicht und gehoert in den Freitext (notizen), wird aber
# vom Sammler oft direkt am Enum-Wert mitgefuehrt. Strip + Re-Vergleich gegen
# den Enum spiegelt das parse_iso_date-Konzept (Klammer-Suffix wird vor dem
# Re-Parsing entfernt). Single-Level (keine geschachtelten Klammern), drei
# Klammer-Varianten (rund/eckig/geschwungen) symmetrisch zu _TRAILING_PAREN_
# REMARK in validators.py.
_TRAILING_ENUM_ANNOTATION = re.compile(
    r"\s*[\(\[\{][^\(\)\[\]\{\}]*[\)\]\}]\s*$"
)

# Trailing Slash-basierte Sub-Klassifikation ("Sammlung/Lehrzwecke",
# "Sammlung/Museum", "Forschung/Univ. Bern"). In DE-Sammler-Notation als
# Kompound-Klassifikation ueblich: Basis-Verwendung vor dem Slash + Zweck/
# Zielinstitution/Vertriebsweg nach dem Slash - der Sammler notiert die
# Sub-Klassifikation direkt am Enum-Wert, um den Empfehlungs-Kontext zu
# behalten ("Sammlung/Lehrzwecke" = ich behalte das Stueck fuer die Sammlung,
# konkret als Anschauungs-/Lehrbeispiel; "Forschung/Univ. Bern" = ich schicke
# das Stueck zur Forschung, konkret an die Uni Bern). Spiegelt
# :data:`_TRAILING_ENUM_ANNOTATION` (Klammer-Sub-Klassifikation) auf die
# Slash-Separator-Achse: dieselbe Semantik (Basis-Enum-Wert wird durch die
# Sub-Klassifikation nicht veraendert), aber die andere in Sammler-Notation
# gaengige Trenner-Konvention. Wird ausschliesslich auf die Beste_Verwendung-
# Achse angewandt, weil die anderen Enum-Felder (Kategorie, Kristallsystem,
# Magnetismus, Status) keine Slash-Sub-Klassifikationen in der Sammler-
# Konvention kennen (Magnetismus/schwach-Haematit gibt es als Klammer-Form,
# aber nicht als Slash-Form; kristallographische Symmetrie ist immer die
# Basis-Klasse ohne Zweck-Zusatz). Single-Level (kein geschachteltes /A/B/C),
# alles nach dem ersten Slash bis zum Zeilenende wird gestrippt - kollisionsfrei
# zur bracketed-Klammer-Strip, die davor laeuft (Reihenfolge egal, weil die
# beiden Patterns disjunkte Suffixe treffen).
_TRAILING_SLASH_SUBCLASSIFICATION = re.compile(r"\s*/[^/]*$")

# Status-Werte, die das Schema (status TEXT NOT NULL DEFAULT 'platzhalter')
# zulaesst, aber die Anwendungslogik kennt nur diese drei. Spiegelt
# repository.VALID_STATUSES; lokal redefiniert statt importiert, weil
# integrity.py keine Abhaengigkeit auf den repository-Modul-Layer haben
# soll (das Modul wird vom CLI auch ohne ObjectRepo-Initialisierung importiert).
_VALID_STATUSES: frozenset[str] = frozenset({"aktiv", "platzhalter", "archiviert"})
# Gueltige Kategorie-Werte aus dem Feldwoerterbuch (ohne Default-Leerstring,
# der "noch nicht kategorisiert" bedeutet und legitim ist). Spiegelt
# repository.VALID_KATEGORIEN. Aus FIELD_BY_NAME abgeleitet statt als Literal,
# weil die Liste Umlaute und Bindestriche enthaelt ("Mineral-Korn", "Handstück",
# "Dünnschliff", "Geröll") und re-typische Tippfehler hier still Daten
# verfaelschen wuerden - die Single-Source-of-Truth bleibt im Feldwoerterbuch.
_VALID_KATEGORIEN: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Kategorie"].enum_values if v
)
# Gueltige Kristallsystem-Werte aus dem Feldwoerterbuch (ohne Default-Leerstring,
# der "noch nicht eingeordnet" bedeutet und legitim ist). Spiegelt
# _VALID_KATEGORIEN auf die kristallographische Symmetrie-Achse: das Schema
# hat keine CHECK-Klausel auf Kristallsystem, daher koennen invalide Werte
# durch direkte DB-Editierung, fehlerhafte CSV-/JSON-Imports (load_standard
# kopiert Kristallsystem ueber _convert_standard ohne Enum-Validierung) oder
# Migration aus inkonsistenten Quell-CSVs entstehen. Aus FIELD_BY_NAME
# abgeleitet statt als Literal, weil die Liste sieben Standard-Symmetrie-
# Klassen plus die amorphe "Sonder"-Klasse umfasst (kubisch/tetragonal/
# hexagonal/trigonal/orthorhombisch/monoklin/triklin/amorph) und re-typische
# Tippfehler hier still Daten verfaelschen wuerden - die Single-Source-of-
# Truth bleibt im Feldwoerterbuch.
_VALID_KRISTALLSYSTEME: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Kristallsystem"].enum_values if v
)
# Gueltige Magnetismus-Werte aus dem Feldwoerterbuch (ohne Default-Leerstring,
# der "noch nicht geprueft" bedeutet und legitim ist). Spiegelt
# _VALID_KRISTALLSYSTEME / _VALID_KATEGORIEN auf die magnetische Reaktions-Achse:
# das Schema hat keine CHECK-Klausel auf Magnetismus, daher koennen invalide
# Werte durch direkte DB-Editierung, fehlerhafte CSV-/JSON-Imports
# (load_standard kopiert das Feld ueber _convert_standard ohne Enum-Validierung)
# oder Migration aus inkonsistenten Quell-CSVs einfliessen. Aus FIELD_BY_NAME
# abgeleitet statt als Literal, weil die Liste die drei Standard-Reaktions-
# Stufen (nein/schwach/ja) umfasst und re-typische Tippfehler ("Nein" mit
# Grossbuchstabe, "ferromagnetisch" als physikalische Sub-Klassifizierung,
# "kein" ohne Endung) hier still Daten verfaelschen wuerden - die Single-
# Source-of-Truth bleibt im Feldwoerterbuch.
_VALID_MAGNETISMUS: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Magnetismus"].enum_values if v
)
# Gueltige Beste_Verwendung-Werte aus dem Feldwoerterbuch (ohne Default-
# Leerstring, der "noch nicht entschieden" bedeutet und legitim ist). Spiegelt
# _VALID_MAGNETISMUS / _VALID_KRISTALLSYSTEME / _VALID_KATEGORIEN auf die
# Verwendungs-/Vermarktungs-Achse: das Schema hat keine CHECK-Klausel auf
# Beste_Verwendung, daher koennen invalide Werte durch direkte DB-Editierung,
# fehlerhafte CSV-/JSON-Imports (load_standard kopiert das Feld ueber
# _convert_standard ohne Enum-Validierung) oder Migration aus inkonsistenten
# Quell-CSVs einfliessen. Aus FIELD_BY_NAME abgeleitet statt als Literal, weil
# die Liste sechs Verwendungs-Klassen umfasst (Schmuck/Sammlung/Forschung/
# Industrie/Talisman/Dekoration) und re-typische Tippfehler ("schmuck" mit
# Kleinbuchstabe, englische Form "jewelry", Kombinationsformen "Schmuck+Sammlung",
# veraltete Klassifizierungen "Verkauf"/"Handel") hier still Daten verfaelschen
# wuerden - die Single-Source-of-Truth bleibt im Feldwoerterbuch.
_VALID_BESTE_VERWENDUNG: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Beste_Verwendung"].enum_values if v
)

# Wertbereiche pro Feld. Ungleich angegebene Felder werden nicht geprueft.
# Format: feldname -> (untergrenze | None, obergrenze | None)
NUMERIC_RANGES: dict[str, tuple[float | None, float | None]] = {
    "Mohs_Haerte_min": (0.0, 10.0),
    "Mohs_Haerte_max": (0.0, 10.0),
    "Dichte_min_gcm3": (0.0, 25.0),  # Iridium ~22.6 g/cm3 → realistische Obergrenze
    "Dichte_max_gcm3": (0.0, 25.0),
    "Laenge_mm": (0.0, None),
    "Breite_mm": (0.0, None),
    "Hoehe_mm": (0.0, None),
    "Gewicht_g": (0.0, None),
    "Wert_CHF_roh": (0.0, None),
    "Wert_CHF_poliert": (0.0, None),
    "Wert_CHF_Schmuck": (0.0, None),
    "Wert_USD_Talisman": (0.0, None),
    "Marktwert_Industrie": (0.0, None),
    "Wissenschaftlicher_Wert_CHF": (0.0, None),
    "Seltenheit_global_1_10": (1.0, 10.0),
    "Seltenheit_Fundort_1_10": (1.0, 10.0),
    "Nachfrage_1_10": (1.0, 10.0),
    "Confidence_Prozent": (0.0, 100.0),
}

# (min-Feld, max-Feld) Paare, bei denen min <= max gelten muss
RANGE_PAIRS: tuple[tuple[str, str], ...] = (
    ("Mohs_Haerte_min", "Mohs_Haerte_max"),
    ("Dichte_min_gcm3", "Dichte_max_gcm3"),
)

# Geometrische Dimensionen in der durch das Feldwoerterbuch festgelegten
# Reihenfolge: Laenge_mm = "Maximale Ausdehnung", Breite_mm = "Zweite
# Ausdehnung", Hoehe_mm = "Dritte Ausdehnung". Per Definition muss daher
# Laenge_mm >= Breite_mm >= Hoehe_mm gelten - wer Laenge=10 und Breite=20
# einträgt, hat die Achsen verwechselt (entweder Laenge ist tatsaechlich 20
# oder Breite ist tatsaechlich 10). Im Gegensatz zu RANGE_PAIRS (Mohs/Dichte
# min<=max - logische Unmoeglichkeit, kein Ausnahmefall) ist die Dimension-
# Reihenfolge eine Konvention auf Feldwoerterbuch-Ebene, deren Verletzung
# semantisch falsch ist (das Stueck wird unter falschen Achsen-Labels gefuehrt,
# Foto-Setup/Inventar-Sortierung passen nicht). Spiegelt RANGE_PAIRS auf die
# Dimensions-Achse: paarweise statt 3-tupel, weil so ein Verstoss exakt das
# verwechselte Paar nennt (Laenge<Breite vs. Breite<Hoehe) statt der gesamten
# 3er-Reihenfolge - das macht die Diagnose im Report unmittelbar lesbar.
DIMENSION_ORDER_PAIRS: tuple[tuple[str, str], ...] = (
    ("Laenge_mm", "Breite_mm"),
    ("Breite_mm", "Hoehe_mm"),
)


@dataclass
class IntegrityReport:
    orphan_images: list[int] = field(default_factory=list)          # image.id
    orphan_ki_analysen: list[int] = field(default_factory=list)     # ki_analysen.id
    alias_to_missing: list[str] = field(default_factory=list)       # alias_id
    alias_id_collisions: list[str] = field(default_factory=list)    # alias_id existiert auch als Objekt
    alias_self_referencing: list[str] = field(default_factory=list) # alias_id == canonical_id
    alias_canonical_is_alias: list[tuple[str, str]] = field(default_factory=list)
    # (alias_id, canonical_id) - canonical_id taucht zugleich als alias_id auf
    # (Kette A->B->C: A->B ist defekt, sollte direkt A->C zeigen)
    invalid_funddatum: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, roher Funddatum-Wert)
    future_funddatum: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, iso)
    future_erstellt_am: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, erstellt_am) - in der Zukunft (Clock-Skew / JSON-Import / manuelle Editierung)
    future_geaendert_am: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, geaendert_am) - in der Zukunft (Clock-Skew / JSON-Import / manuelle Editierung)
    missing_image_files: list[tuple[int, str]] = field(default_factory=list)  # (id, rel_path)
    numeric_out_of_range: list[tuple[str, str, float]] = field(default_factory=list)
    range_inverted: list[tuple[str, str, float, float]] = field(default_factory=list)  # (obj_id, "min_feld>max_feld", min_wert, max_wert)
    dimension_order_inverted: list[tuple[str, str, float, float]] = field(default_factory=list)  # (obj_id, "groesseres_feld<kleineres_feld", groesseres_wert, kleineres_wert) - Konvention Laenge>=Breite>=Hoehe verletzt
    unknown_image_kategorie: list[tuple[int, str]] = field(default_factory=list)  # (id, kategorie)
    aktiv_ohne_inhalt: list[str] = field(default_factory=list)  # obj_id mit status='aktiv', aber keine Daten und keine Bilder
    platzhalter_mit_inhalt: list[str] = field(default_factory=list)  # obj_id mit status='platzhalter', aber Daten oder Bilder vorhanden
    unknown_status: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, status) - status nicht in {aktiv,platzhalter,archiviert}
    unknown_kategorie: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, kategorie) - Kategorie nicht im Feldwoerterbuch-Enum
    unknown_kristallsystem: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, kristallsystem) - Kristallsystem nicht im Feldwoerterbuch-Enum
    unknown_magnetismus: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, magnetismus) - Magnetismus nicht im Feldwoerterbuch-Enum
    unknown_beste_verwendung: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, beste_verwendung) - Beste_Verwendung nicht im Feldwoerterbuch-Enum
    geaendert_vor_erstellt: list[tuple[str, str, str]] = field(default_factory=list)  # (obj_id, erstellt_am, geaendert_am) - logisch unmoeglich

    @property
    def is_clean(self) -> bool:
        return not (self.orphan_images or self.orphan_ki_analysen
                    or self.alias_to_missing
                    or self.alias_id_collisions or self.alias_self_referencing
                    or self.alias_canonical_is_alias
                    or self.invalid_funddatum or self.future_funddatum
                    or self.future_erstellt_am
                    or self.future_geaendert_am
                    or self.missing_image_files or self.numeric_out_of_range
                    or self.range_inverted
                    or self.dimension_order_inverted
                    or self.unknown_image_kategorie
                    or self.aktiv_ohne_inhalt
                    or self.platzhalter_mit_inhalt
                    or self.unknown_status
                    or self.unknown_kategorie
                    or self.unknown_kristallsystem
                    or self.unknown_magnetismus
                    or self.unknown_beste_verwendung
                    or self.geaendert_vor_erstellt)

    def as_dict(self) -> dict:
        return {
            "orphan_images": list(self.orphan_images),
            "orphan_ki_analysen": list(self.orphan_ki_analysen),
            "alias_to_missing": list(self.alias_to_missing),
            "alias_id_collisions": list(self.alias_id_collisions),
            "alias_self_referencing": list(self.alias_self_referencing),
            "alias_canonical_is_alias": [list(t) for t in self.alias_canonical_is_alias],
            "invalid_funddatum": [list(t) for t in self.invalid_funddatum],
            "future_funddatum": [list(t) for t in self.future_funddatum],
            "future_erstellt_am": [list(t) for t in self.future_erstellt_am],
            "future_geaendert_am": [list(t) for t in self.future_geaendert_am],
            "missing_image_files": [list(t) for t in self.missing_image_files],
            "numeric_out_of_range": [list(t) for t in self.numeric_out_of_range],
            "range_inverted": [list(t) for t in self.range_inverted],
            "dimension_order_inverted": [list(t) for t in self.dimension_order_inverted],
            "unknown_image_kategorie": [list(t) for t in self.unknown_image_kategorie],
            "aktiv_ohne_inhalt": list(self.aktiv_ohne_inhalt),
            "platzhalter_mit_inhalt": list(self.platzhalter_mit_inhalt),
            "unknown_status": [list(t) for t in self.unknown_status],
            "unknown_kategorie": [list(t) for t in self.unknown_kategorie],
            "unknown_kristallsystem": [list(t) for t in self.unknown_kristallsystem],
            "unknown_magnetismus": [list(t) for t in self.unknown_magnetismus],
            "unknown_beste_verwendung": [list(t) for t in self.unknown_beste_verwendung],
            "geaendert_vor_erstellt": [list(t) for t in self.geaendert_vor_erstellt],
            "is_clean": self.is_clean,
        }


def check_integrity(conn: sqlite3.Connection, root: Path | None = None,
                    check_files: bool = False,
                    today: datetime.date | None = None,
                    now: datetime.datetime | None = None) -> IntegrityReport:
    """Sammelt typische Inkonsistenzen.

    ``check_files=True`` und ``root`` gesetzt → prüft zusätzlich, ob die in
    ``images.rel_path`` referenzierten Dateien auf der Platte existieren.
    ``today`` setzt das Referenzdatum fuer die Zukunfts-Pruefung des Funddatums
    (Default: ``datetime.date.today()``); explizit setzen macht den Test
    deterministisch. ``now`` setzt analog den Zeitstempel-Referenzpunkt fuer
    die Zukunfts-Pruefung von ``erstellt_am`` (Default:
    ``datetime.datetime.now()``); spiegelt ``today`` auf die Sekunden-Achse.
    """
    rep = IntegrityReport()
    today_iso = (today or datetime.date.today()).isoformat()
    # _now()-Format ist "YYYY-MM-DD HH:MM:SS" (siehe repository.py); spiegelt
    # das hier exakt, damit der String-Vergleich gegen erstellt_am sortierbar
    # und kollisionsfrei zur DB-Konvention bleibt.
    now_iso = (now or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

    rep.orphan_images = [r[0] for r in conn.execute(
        "SELECT i.id FROM images i "
        "LEFT JOIN objects o ON o.obj_id = i.obj_id "
        "WHERE o.obj_id IS NULL ORDER BY i.id"
    ).fetchall()]

    # ki_analysen-Orphans spiegeln orphan_images auf die KI-Analyse-Tabelle:
    # das Schema hat ein FK mit ON DELETE CASCADE auf objects(obj_id), so dass
    # die regulaere Anwendung (delete-Pfad ueber ObjectRepo) niemals Orphans
    # erzeugt. Sie koennen aber durch JSON-Restore aus einem partiellen Backup
    # (nur ki_analysen-Tabelle wiederhergestellt, ohne die zugehoerigen Objekte),
    # direkte DB-Editierung mit PRAGMA foreign_keys=OFF oder fehlerhafte
    # Migrations-Skripte entstehen - genau die Faelle, in denen orphan_images
    # ebenfalls auftritt. Spiegelt das orphan_images-Format: reine Liste der
    # ki_analysen.id-Werte (nicht obj_id), damit die betroffene Analyse direkt
    # ueber den Primaerschluessel adressierbar ist.
    rep.orphan_ki_analysen = [r[0] for r in conn.execute(
        "SELECT k.id FROM ki_analysen k "
        "LEFT JOIN objects o ON o.obj_id = k.obj_id "
        "WHERE o.obj_id IS NULL ORDER BY k.id"
    ).fetchall()]

    rep.alias_to_missing = [r[0] for r in conn.execute(
        "SELECT a.alias_id FROM aliases a "
        "LEFT JOIN objects o ON o.obj_id = a.canonical_id "
        "WHERE o.obj_id IS NULL ORDER BY a.alias_id"
    ).fetchall()]

    rep.alias_id_collisions = [r[0] for r in conn.execute(
        "SELECT a.alias_id FROM aliases a "
        "JOIN objects o ON o.obj_id = a.alias_id ORDER BY a.alias_id"
    ).fetchall()]

    rep.alias_self_referencing = [r[0] for r in conn.execute(
        "SELECT alias_id FROM aliases WHERE alias_id = canonical_id ORDER BY alias_id"
    ).fetchall()]

    # Kette A->B->C: A.canonical_id (=B) ist selbst ein Alias.
    # Selbstreferenzen (A==B==C in einer Zeile) sind bereits in alias_self_referencing
    # gemeldet und werden hier ausgeschlossen, um Doppelmeldung zu vermeiden.
    rep.alias_canonical_is_alias = [
        (r["alias_id"], r["canonical_id"])
        for r in conn.execute(
            "SELECT a.alias_id, a.canonical_id FROM aliases a "
            "JOIN aliases b ON b.alias_id = a.canonical_id "
            "WHERE a.alias_id != a.canonical_id "
            "ORDER BY a.alias_id"
        ).fetchall()
    ]

    known_categories = set(IMAGE_CATEGORIES)
    rep.unknown_image_kategorie = [
        (r["id"], r["kategorie"])
        for r in conn.execute("SELECT id, kategorie FROM images ORDER BY id").fetchall()
        if r["kategorie"] not in known_categories
    ]

    # Status-Validierung: das Schema hat keine CHECK-Klausel auf status, daher
    # koennen invalide Werte durch direkte DB-Editierung, fehlerhafte CSV-/
    # JSON-Imports (load_standard kopiert ``status`` ohne Validierung) oder
    # aeltere Migrations-Versionen entstehen. ObjectRepo.set_status validiert
    # zwar gegen VALID_STATUSES, fasst aber nur die laufende Anwendung ab -
    # die Integrity-Pruefung deckt die DB-Sicht ab und macht stille Workflow-
    # Fehlbedienungen ("aktiv/Aktiv/Active"-Tippfehler) sichtbar. Komplementaer
    # zu aktiv_ohne_inhalt / platzhalter_mit_inhalt (semantische Status-
    # Konsistenz): hier geht es um den syntaktischen Wertebereich, dort um den
    # Daten-/Bilder-Kontext. NULL waere durch das NOT-NULL-Constraint im
    # Schema bereits verhindert, taucht hier also nicht auf.
    rep.unknown_status = [
        (r["obj_id"], r["status"])
        for r in conn.execute(
            "SELECT obj_id, status FROM objects ORDER BY obj_id"
        ).fetchall()
        if r["status"] not in _VALID_STATUSES
    ]

    # Kategorie-Validierung: das Schema hat keine CHECK-Klausel auf Kategorie,
    # daher koennen invalide Werte durch direkte DB-Editierung, fehlerhafte
    # CSV-/JSON-Imports (load_standard kopiert ``Kategorie`` ohne Validierung
    # in den text-Pfad von _convert_standard) oder Migration aus inkonsistenten
    # Quell-CSVs (v1 hatte z.B. teilweise "Handstück" als Sub-Bezeichnung im
    # Notizfeld statt im Kategorie-Feld) entstehen. ObjectRepo.list_objects mit
    # kategorie_in validiert zwar gegen VALID_KATEGORIEN, fasst aber nur die
    # Filter-Eingabe ab - die Integrity-Pruefung deckt die DB-Sicht ab und macht
    # stille Tippfehler/Falschwerte ("Handstuck" ohne Umlaut, "Mineralkorn" ohne
    # Bindestrich, "kristall" mit Kleinbuchstabe, frei erfundene Werte wie
    # "Probe"/"Fossil") sichtbar. Komplementaer zu unknown_status (status-Wert-
    # Validierung) und unknown_image_kategorie (Bildkategorie auf der image-
    # Tabelle): hier geht es um den syntaktischen Wertebereich der Objekt-
    # Kategorie auf der objects-Tabelle. Leerstring "" und NULL sind gueltig
    # ("noch nicht kategorisiert") und werden uebergangen, damit der Pflege-
    # Restbestand (noch nicht kategorisierte Stuecke) keine falsch-positiven
    # erzeugt; tatsaechliche Tippfehler werden so isoliert sichtbar. Format
    # spiegelt unknown_status: (obj_id, kategorie)-Tuples, damit sowohl die
    # betroffene ID als auch der konkrete Falschwert direkt im Report stehen.
    rep.unknown_kategorie = [
        (r["obj_id"], r["Kategorie"])
        for r in conn.execute(
            "SELECT obj_id, Kategorie FROM objects "
            "WHERE Kategorie IS NOT NULL AND TRIM(Kategorie) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        if r["Kategorie"] not in _VALID_KATEGORIEN
    ]

    # Kristallsystem-Validierung: spiegelt unknown_kategorie auf die
    # kristallographische Symmetrie-Achse. Das Schema hat keine CHECK-Klausel
    # auf Kristallsystem; load_standard / _convert_standard kopiert das Feld
    # ohne Enum-Validierung, sodass Tippfehler ("Trigonal" mit Grossbuchstabe
    # vs. "trigonal" im Feldwoerterbuch), Synonyme ("rhomboedrisch" als
    # alternative Schreibweise zu "trigonal"), Falschwerte ("Tetragonal-Spinell"
    # mit redundanter Sub-Klassifizierung) oder veraltete Schreibweisen
    # ("rhombisch" statt "orthorhombisch") still durch CSV-/JSON-Imports
    # oder direkte DB-Editierung einfliessen koennen. Komplementaer zu
    # unknown_kategorie (Objekt-Kategorie) und unknown_status (Lifecycle):
    # hier die mineralogisch-strukturelle Achse. Leerstring/NULL bleibt
    # legitim als "noch nicht eingeordnet" und wird uebergangen, damit der
    # Pflege-Restbestand (Stuecke ohne Symmetrietyp-Einordnung, der Normalfall
    # vor mineralogischer Bestimmung) keine falsch-positiven erzeugt;
    # tatsaechliche Tippfehler werden so isoliert sichtbar. Format spiegelt
    # unknown_kategorie / unknown_status: (obj_id, kristallsystem)-Tuples,
    # damit sowohl die betroffene ID als auch der konkrete Falschwert direkt
    # im Report stehen - ohne zusaetzliche SQL-Abfrage zur Diagnose.
    # Trailing-Klammer-Annotationen (Kristallgroesse "(mikrokristallin)",
    # alternative Schreibweise "(rhomboedrisch)", Habitus "(saeulenfoermig)")
    # werden vor dem Enum-Vergleich gestrippt - die Annotation aendert die
    # Basis-Symmetrie nicht und ist in mineralogischen Notizen ueblich;
    # spiegelt das parse_iso_date-Konzept (Klammer-Suffix wird vor Re-Parsing
    # entfernt). "trigonal (mikrokristallin)" passt dadurch gegen den
    # Enum-Wert "trigonal" und gilt als gueltig.
    rep.unknown_kristallsystem = [
        (r["obj_id"], r["Kristallsystem"])
        for r in conn.execute(
            "SELECT obj_id, Kristallsystem FROM objects "
            "WHERE Kristallsystem IS NOT NULL AND TRIM(Kristallsystem) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        if _TRAILING_ENUM_ANNOTATION.sub("", r["Kristallsystem"]).strip()
        not in _VALID_KRISTALLSYSTEME
    ]

    # Magnetismus-Validierung: spiegelt unknown_kristallsystem / unknown_kategorie
    # auf die magnetische Reaktions-Achse. Das Schema hat keine CHECK-Klausel auf
    # Magnetismus; load_standard / _convert_standard kopiert das Feld ohne
    # Enum-Validierung, sodass Tippfehler ("Nein" mit Grossbuchstabe vs. "nein"
    # im Feldwoerterbuch), englische Form ("no" statt "nein"), physikalische
    # Sub-Klassifizierung ("ferromagnetisch", "paramagnetisch", "diamagnetisch"
    # statt der grobkoernigen 3-Stufen-Skala) oder veraltete/freie Werte
    # ("magnetisch", "kein") still durch CSV-/JSON-Imports oder direkte
    # DB-Editierung einfliessen koennen. Komplementaer zu unknown_kategorie
    # (Objekt-Kategorie), unknown_status (Lifecycle) und unknown_kristallsystem
    # (kristallographische Symmetrie): hier die magnetische Reaktions-Achse als
    # einer der wichtigsten qualitativen Pruefparameter neben HCl-Reaktion und
    # Strichfarbe. Leerstring/NULL bleibt legitim als "noch nicht geprueft"
    # (der Normalfall, bevor das Stueck mit einem Magneten getestet wurde, oder
    # Migration-Restbestaende aus alten v1/obj043-CSVs ohne Magnetismus-Spalte)
    # und wird uebergangen, damit der Pflege-Restbestand keine falsch-positiven
    # erzeugt; tatsaechliche Tippfehler werden so isoliert sichtbar. Trailing-
    # Klammer-Annotationen ("schwach (Haematit-Beimischung)", "ja [stark]",
    # "nein {gepruefter Neodym-Magnet}") werden vor dem Enum-Vergleich gestrippt
    # - die Sub-Klassifizierung in Klammern (Erklaerung der Reaktion, Mess-
    # Bedingungen, vermutete Ursache) aendert die Basis-Stufe nicht und ist in
    # mineralogischen Pruef-Notizen ueblich; spiegelt das parse_iso_date-Konzept
    # exakt wie bei unknown_kristallsystem. Format spiegelt unknown_kategorie /
    # unknown_status / unknown_kristallsystem: (obj_id, magnetismus)-Tuples mit
    # dem Roh-Wert (nicht der gestrippten Form), damit sowohl die betroffene ID
    # als auch der konkrete Falschwert direkt im Report stehen - ohne
    # zusaetzliche SQL-Abfrage zur Diagnose.
    rep.unknown_magnetismus = [
        (r["obj_id"], r["Magnetismus"])
        for r in conn.execute(
            "SELECT obj_id, Magnetismus FROM objects "
            "WHERE Magnetismus IS NOT NULL AND TRIM(Magnetismus) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        if _TRAILING_ENUM_ANNOTATION.sub("", r["Magnetismus"]).strip()
        not in _VALID_MAGNETISMUS
    ]

    # Beste_Verwendung-Validierung: spiegelt unknown_magnetismus /
    # unknown_kristallsystem / unknown_kategorie auf die Verwendungs-/
    # Vermarktungs-Empfehlungs-Achse. Das Schema hat keine CHECK-Klausel auf
    # Beste_Verwendung; load_standard / _convert_standard kopiert das Feld ohne
    # Enum-Validierung, sodass Tippfehler ("schmuck" mit Kleinbuchstabe vs.
    # "Schmuck" im Feldwoerterbuch), englische Form ("jewelry" statt "Schmuck",
    # "collection" statt "Sammlung"), Kombinationsformen ("Schmuck+Sammlung"
    # als informelle Doppelklassifikation, "Sammlung/Forschung" mit Slash-
    # Trenner) oder veraltete/freie Werte ("Verkauf", "Handel", "Boerse")
    # still durch CSV-/JSON-Imports oder direkte DB-Editierung einfliessen
    # koennen. Komplementaer zu unknown_kategorie (Objekt-Klassifikation:
    # was IST das Stueck?), unknown_status (Lifecycle: wie ist der Pflegestand?),
    # unknown_kristallsystem (kristallographische Symmetrie) und
    # unknown_magnetismus (physikalische Reaktion): hier die vom Sammler
    # gewaehlte Zielvermarktung als eine der wichtigsten Sortier-/Filter-Achsen
    # neben der Kategorie - vor Boersenbesuch, Schmuck-Verkauf oder Museums-
    # Uebergabe will man alle passenden Stuecke beisammen sehen (spiegelt die
    # Beste_Verwendung-Sortier-/Filter-Achse aus repository.py, wo
    # beste_verwendung_in als Mengen-Filter und Beste_Verwendung als
    # Sortier-Spalte gefuehrt werden). Leerstring/NULL bleibt legitim als
    # "noch nicht entschieden" (der Normalfall, bevor die Empfehlung
    # feststeht, oder Migrations-Restbestaende aus alten v1/obj043-CSVs ohne
    # Beste_Verwendung-Spalte) und wird uebergangen, damit der Pflege-
    # Restbestand keine falsch-positiven erzeugt; tatsaechliche Tippfehler
    # werden so isoliert sichtbar. Trailing-Klammer-Annotationen ("Schmuck
    # (Anhaenger)", "Sammlung [Vitrine 3]", "Forschung {Uni Bern}") werden vor
    # dem Enum-Vergleich gestrippt - die Sub-Klassifizierung in Klammern
    # (Vermarktungs-Details, Vitrinen-Platz, Zielinstitution) aendert die
    # Basis-Verwendung nicht und ist in Pflege-Notizen ueblich; spiegelt das
    # parse_iso_date-Konzept exakt wie bei unknown_magnetismus / unknown_
    # kristallsystem. Format spiegelt unknown_kategorie / unknown_status /
    # unknown_kristallsystem / unknown_magnetismus: (obj_id, beste_verwendung)-
    # Tuples mit dem Roh-Wert (nicht der gestrippten Form), damit sowohl die
    # betroffene ID als auch der konkrete Falschwert direkt im Report stehen -
    # ohne zusaetzliche SQL-Abfrage zur Diagnose.
    rep.unknown_beste_verwendung = [
        (r["obj_id"], r["Beste_Verwendung"])
        for r in conn.execute(
            "SELECT obj_id, Beste_Verwendung FROM objects "
            "WHERE Beste_Verwendung IS NOT NULL AND TRIM(Beste_Verwendung) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        if _TRAILING_SLASH_SUBCLASSIFICATION.sub(
            "", _TRAILING_ENUM_ANNOTATION.sub("", r["Beste_Verwendung"])
        ).strip() not in _VALID_BESTE_VERWENDUNG
    ]

    for row in conn.execute(
        "SELECT obj_id, Funddatum FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != ''"
    ).fetchall():
        iso = parse_iso_date(row["Funddatum"])
        if iso is None:
            # Format spiegelt unknown_status / unknown_kategorie / future_funddatum:
            # (obj_id, roh-Wert)-Tupel, damit sowohl die betroffene ID als auch
            # der konkrete unparsbare Eintrag direkt im Report stehen - ohne
            # zusaetzliche SQL-Abfrage zur Diagnose. Vorher war es eine reine
            # obj_id-Liste, was die Sicht auf den Falschwert verzoegerte.
            rep.invalid_funddatum.append((row["obj_id"], row["Funddatum"]))
        elif iso > today_iso:
            rep.future_funddatum.append((row["obj_id"], iso))

    cols = ", ".join(NUMERIC_RANGES)
    for row in conn.execute(f"SELECT obj_id, {cols} FROM objects").fetchall():
        for field_name, (lo, hi) in NUMERIC_RANGES.items():
            v = row[field_name]
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if (lo is not None and fv < lo) or (hi is not None and fv > hi):
                rep.numeric_out_of_range.append((row["obj_id"], field_name, fv))

    pair_cols = {c for pair in RANGE_PAIRS for c in pair}
    cols2 = ", ".join(pair_cols)
    for row in conn.execute(f"SELECT obj_id, {cols2} FROM objects").fetchall():
        for lo_field, hi_field in RANGE_PAIRS:
            lo, hi = row[lo_field], row[hi_field]
            if lo is None or hi is None:
                continue
            lo_f, hi_f = float(lo), float(hi)
            if lo_f > hi_f:
                # Format spiegelt numeric_out_of_range: konkrete Werte direkt im
                # Report, damit die Diagnose ohne SQL-Roundtrip moeglich ist
                # ("min=10.0 vs max=5.0" laesst die Vertauschung sofort erkennen,
                # waehrend die reine Feldpaar-Marke nur sagt _dass_ etwas
                # vertauscht ist). _format_example joint die Tupel ":"-getrennt,
                # was im CLI als ``OBJ_0042:Mohs_Haerte_min>Mohs_Haerte_max:10.0:5.0``
                # erscheint - kompakt und ohne Schema-Bruch fuer JSON-Konsumenten.
                rep.range_inverted.append(
                    (row["obj_id"], f"{lo_field}>{hi_field}", lo_f, hi_f))

    # Dimensions-Konvention: Laenge_mm >= Breite_mm >= Hoehe_mm laut Feldwoerter-
    # buch ("Maximale/Zweite/Dritte Ausdehnung"). Verstoesse entstehen typisch
    # durch verwechselte Achsen beim Vermessen (Schiebelehre quer statt laengs
    # angesetzt) oder durch verdrehte Eingabe ins Datenblatt (Werte richtig
    # gemessen, aber in der falschen Spalte gelandet). Spiegelt RANGE_PAIRS auf
    # die Dimensions-Achse, mit demselben 4-Tupel-Format
    # ``(obj_id, "groesseres_feld<kleineres_feld", groesseres_wert, kleineres_wert)``
    # damit die Diagnose ohne SQL-Roundtrip direkt im Report steht. Beide Werte
    # muessen gesetzt sein - halb leere Eintraege (nur Laenge ohne Breite) sind
    # legitim und werden uebergangen. Gleichheit (Wuerfel: 30x30x30) bleibt
    # zulaessig: nur strikte Inversion wird gemeldet.
    dim_cols = {c for pair in DIMENSION_ORDER_PAIRS for c in pair}
    cols3 = ", ".join(dim_cols)
    for row in conn.execute(f"SELECT obj_id, {cols3} FROM objects").fetchall():
        for big_field, small_field in DIMENSION_ORDER_PAIRS:
            big, small = row[big_field], row[small_field]
            if big is None or small is None:
                continue
            big_f, small_f = float(big), float(small)
            if big_f < small_f:
                rep.dimension_order_inverted.append(
                    (row["obj_id"], f"{big_field}<{small_field}", big_f, small_f))

    # Zeitstempel-Konsistenz: geaendert_am muss >= erstellt_am sein. Die App
    # selbst setzt beide bei create() auf denselben _now()-Stempel und ueber-
    # schreibt geaendert_am bei jedem update_fields(); die umgekehrte Reihen-
    # folge ist logisch unmoeglich, kann aber durch JSON-Import aus einer
    # korrupten Quelle, manuelle DB-Editierung oder Clock-Skew zwischen
    # Migrationsmaschinen entstehen. Lexikographischer Vergleich reicht, weil
    # _now() ISO-8601-Format "YYYY-MM-DD HH:MM:SS" schreibt (sortierbar).
    # Leere oder NULL-Stempel werden ignoriert (die Format-Validitaet ist
    # ein separates Anliegen und wuerde hier falsch-positive erzeugen).
    rep.geaendert_vor_erstellt = [
        (r["obj_id"], r["erstellt_am"], r["geaendert_am"])
        for r in conn.execute(
            "SELECT obj_id, erstellt_am, geaendert_am FROM objects "
            "WHERE erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
            "AND geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
            "AND geaendert_am < erstellt_am "
            "ORDER BY obj_id"
        ).fetchall()
    ]

    # Zukunfts-Pruefung auf erstellt_am: ein Erfassungs-Zeitstempel in der
    # Zukunft ist logisch unmoeglich (das Objekt kann nicht "morgen" erfasst
    # worden sein), kann aber durch Clock-Skew zwischen Migrationsmaschinen,
    # manuelle DB-Editierung (Excel-CSV-Re-Import mit verstellter System-Uhr),
    # JSON-Restore aus einem inkonsistenten Backup oder Reise mit verstellter
    # Laptop-Zeit (z.B. ueber Datumsgrenze) entstehen. Spiegelt
    # future_funddatum auf die erstellt_am-Achse (Erfassungs-Zeitpunkt statt
    # Fund-Zeitpunkt) und ergaenzt geaendert_vor_erstellt (Inter-Stempel-
    # Konsistenz): hier geht es um die absolute Zukunfts-Lage, dort um die
    # relative Reihenfolge. Lexikographischer Vergleich reicht, weil _now()
    # ISO-8601-Format "YYYY-MM-DD HH:MM:SS" schreibt (sortierbar) und now_iso
    # exakt dieses Format spiegelt. Leere/NULL-Stempel werden ignoriert
    # (Format-Validitaet ist ein separates Anliegen).
    rep.future_erstellt_am = [
        (r["obj_id"], r["erstellt_am"])
        for r in conn.execute(
            "SELECT obj_id, erstellt_am FROM objects "
            "WHERE erstellt_am IS NOT NULL AND TRIM(erstellt_am) != '' "
            "AND erstellt_am > ? "
            "ORDER BY obj_id",
            (now_iso,),
        ).fetchall()
    ]

    # Zukunfts-Pruefung auf geaendert_am: spiegelt future_erstellt_am auf die
    # letzte-Aenderungs-Achse und vervollstaendigt das Trio der Zukunfts-Stempel-
    # Pruefungen (Funddatum / Erfassungs-Zeit / Aenderungs-Zeit). Eine geaendert_am
    # in der Zukunft entsteht nicht durch die Anwendung selbst (update_fields setzt
    # _now()), kann aber durch JSON-Restore aus einem Backup mit verstellter
    # System-Uhr, manuelle DB-Editierung oder Sync ueber Maschinen mit Clock-Skew
    # entstehen. geaendert_vor_erstellt deckt nur die relative Reihenfolge zwischen
    # den zwei Stempeln ab (geaendert < erstellt → Inversion); ein Stempel-Paar
    # erstellt_am=2024 + geaendert_am=2099 bestaende den Inter-Stempel-Test, waere
    # aber offensichtlich falsch - jetzt deckt future_geaendert_am diese Achse ab.
    # Lexikographischer Vergleich reicht (gleiche Konvention wie future_erstellt_am).
    rep.future_geaendert_am = [
        (r["obj_id"], r["geaendert_am"])
        for r in conn.execute(
            "SELECT obj_id, geaendert_am FROM objects "
            "WHERE geaendert_am IS NOT NULL AND TRIM(geaendert_am) != '' "
            "AND geaendert_am > ? "
            "ORDER BY obj_id",
            (now_iso,),
        ).fetchall()
    ]

    # 'aktiv' impliziert: irgendwo Daten oder mindestens ein Bild. Wenn beides
    # fehlt, ist der Status verkettet falsch (typischerweise nachtraegliches
    # Loeschen aller Bilder/Felder ohne Statusrueckfuehrung). refresh_status
    # repariert das pro Objekt; hier nur erkennen.
    data_check = " OR ".join(
        f"(TRIM(COALESCE({f.name}, '')) != '')" for f in DATA_FIELDS
    )
    rep.aktiv_ohne_inhalt = [r[0] for r in conn.execute(
        f"SELECT o.obj_id FROM objects o "
        f"WHERE o.status = 'aktiv' "
        f"AND NOT ({data_check}) "
        f"AND NOT EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id) "
        f"ORDER BY o.obj_id"
    ).fetchall()]
    # Spiegelbild: 'platzhalter' mit tatsaechlichem Inhalt (Daten oder Bild).
    # Tritt auf, wenn nach Datenpflege/Bilder-Import refresh_status nie lief.
    rep.platzhalter_mit_inhalt = [r[0] for r in conn.execute(
        f"SELECT o.obj_id FROM objects o "
        f"WHERE o.status = 'platzhalter' "
        f"AND (({data_check}) "
        f"  OR EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id)) "
        f"ORDER BY o.obj_id"
    ).fetchall()]

    if check_files and root is not None:
        for row in conn.execute("SELECT id, rel_path FROM images").fetchall():
            full = root / row["rel_path"]
            if not full.is_file():
                rep.missing_image_files.append((row["id"], row["rel_path"]))

    return rep


def find_duplicate_image_sha256(conn: sqlite3.Connection) -> list[tuple[str, list[int]]]:
    """Findet Bilder mit identischem SHA-256 (gleicher Inhalt mehrfach gespeichert).

    Ergebnis: Liste von ``(sha256, [image_ids])`` absteigend nach Gruppengroesse,
    aufsteigend nach sha256 als Tie-Break. NULL/leere SHA-Werte werden ignoriert.

    Duplikate sind nicht zwingend ein Fehler (z.B. dasselbe Bild legitim als
    Uebersicht UND Kamera abgelegt) — die Funktion liefert reine Information
    und gehoert daher nicht in :func:`check_integrity`.
    """
    rows = conn.execute(
        "SELECT sha256, GROUP_CONCAT(id) AS ids, COUNT(*) AS n FROM images "
        "WHERE sha256 IS NOT NULL AND TRIM(sha256) != '' "
        "GROUP BY sha256 HAVING n > 1 "
        "ORDER BY n DESC, sha256 ASC"
    ).fetchall()
    return [
        (r["sha256"], sorted(int(x) for x in r["ids"].split(",")))
        for r in rows
    ]
