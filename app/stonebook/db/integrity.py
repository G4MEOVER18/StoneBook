"""Konsistenzprüfungen über die Objekt-DB (für Wartung/Diagnose)."""
from __future__ import annotations

import datetime
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from stonebook.fields import DATA_FIELDS, FIELD_BY_NAME, IMAGE_CATEGORIES
from stonebook.migration.validators import parse_iso_date

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


@dataclass
class IntegrityReport:
    orphan_images: list[int] = field(default_factory=list)          # image.id
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
    unknown_image_kategorie: list[tuple[int, str]] = field(default_factory=list)  # (id, kategorie)
    aktiv_ohne_inhalt: list[str] = field(default_factory=list)  # obj_id mit status='aktiv', aber keine Daten und keine Bilder
    platzhalter_mit_inhalt: list[str] = field(default_factory=list)  # obj_id mit status='platzhalter', aber Daten oder Bilder vorhanden
    unknown_status: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, status) - status nicht in {aktiv,platzhalter,archiviert}
    unknown_kategorie: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, kategorie) - Kategorie nicht im Feldwoerterbuch-Enum
    geaendert_vor_erstellt: list[tuple[str, str, str]] = field(default_factory=list)  # (obj_id, erstellt_am, geaendert_am) - logisch unmoeglich

    @property
    def is_clean(self) -> bool:
        return not (self.orphan_images or self.alias_to_missing
                    or self.alias_id_collisions or self.alias_self_referencing
                    or self.alias_canonical_is_alias
                    or self.invalid_funddatum or self.future_funddatum
                    or self.future_erstellt_am
                    or self.future_geaendert_am
                    or self.missing_image_files or self.numeric_out_of_range
                    or self.range_inverted or self.unknown_image_kategorie
                    or self.aktiv_ohne_inhalt
                    or self.platzhalter_mit_inhalt
                    or self.unknown_status
                    or self.unknown_kategorie
                    or self.geaendert_vor_erstellt)

    def as_dict(self) -> dict:
        return {
            "orphan_images": list(self.orphan_images),
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
            "unknown_image_kategorie": [list(t) for t in self.unknown_image_kategorie],
            "aktiv_ohne_inhalt": list(self.aktiv_ohne_inhalt),
            "platzhalter_mit_inhalt": list(self.platzhalter_mit_inhalt),
            "unknown_status": [list(t) for t in self.unknown_status],
            "unknown_kategorie": [list(t) for t in self.unknown_kategorie],
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
