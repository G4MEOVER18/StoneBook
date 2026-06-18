"""CRUD-Schicht über der SQLite-DB."""
import datetime
import sqlite3

from stonebook.fields import DATA_FIELDS, FIELD_BY_NAME, IMAGE_CATEGORIES, is_empty

DATA_COLS = [f.name for f in DATA_FIELDS]

VALID_STATUSES: frozenset[str] = frozenset({"aktiv", "platzhalter", "archiviert"})

# Gueltige Kristallsysteme aus dem Feldwoerterbuch (ohne den leeren Default-Eintrag).
# Werden fuer den kristallsystem_in-Mengenfilter zur Validierung benutzt, damit
# Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses erzeugen.
VALID_KRISTALLSYSTEME: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Kristallsystem"].enum_values if v
)
# Analog: gueltige Beste-Verwendung-Werte aus dem Feldwoerterbuch (ohne Default).
# Trennt den Mengenfilter (z.B. "Schmuck ODER Sammlung") sauber von Freitext.
VALID_BESTE_VERWENDUNG: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Beste_Verwendung"].enum_values if v
)
# Analog: gueltige Kategorie-Werte aus dem Feldwoerterbuch (ohne Default).
# Fuer den kategorie_in-Mengenfilter ("Handstueck ODER Kristall").
VALID_KATEGORIEN: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Kategorie"].enum_values if v
)
# Analog: gueltige Glanz-Werte aus dem Feldwoerterbuch (ohne Default).
# Fuer den glanz_in-Mengenfilter ("glasig ODER metallisch ODER seidig" als
# optische Auswahl: alle glasigen Quarze + alle metallischen Pyrite zusammen).
VALID_GLANZ: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Glanz"].enum_values if v
)
# Analog: gueltige Transparenz-Werte aus dem Feldwoerterbuch (ohne Default).
# Fuer den transparenz_in-Mengenfilter ("durchsichtig ODER durchscheinend" als
# Foto-Setup-Auswahl: lichtdurchlaessige Stuecke brauchen Backlight, opake nicht).
VALID_TRANSPARENZ: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Transparenz"].enum_values if v
)
# Analog: gueltige Magnetismus-Werte aus dem Feldwoerterbuch (ohne Default).
# Fuer den magnetismus_in-Mengenfilter ("ja ODER schwach" als Eisen-Auswahl:
# alle reagierenden Stuecke separat von inerten Quarz-/Calcit-Stuecken).
VALID_MAGNETISMUS: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Magnetismus"].enum_values if v
)
# Analog: gueltige Spaltbarkeits-Werte aus dem Feldwoerterbuch (ohne Default).
# Fuer den spaltbarkeit_in-Mengenfilter ("vollkommen ODER gut" als Praeparier-
# Auswahl: alle sauber spaltbaren Stuecke separat von zaehen Quarz-Brocken,
# die nur per Saege/Polier bearbeitet werden koennen).
VALID_SPALTBARKEIT: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Spaltbarkeit"].enum_values if v
)
# Analog: gueltige Bruch-Werte aus dem Feldwoerterbuch (ohne Default).
# Fuer den bruch_in-Mengenfilter ("muschelig ODER splittrig" als
# Schaerfekanten-Auswahl: Stuecke, die ohne Spaltflaechen scharfe Kanten
# erzeugen, separat von fasrigen/erdigen Brocken).
VALID_BRUCH: frozenset[str] = frozenset(
    v for v in FIELD_BY_NAME["Bruch"].enum_values if v
)

# Whitelist für Sortierung in list_objects (verhindert SQL-Injection bei freier Spalte).
SORTABLE_COLUMNS: frozenset[str] = frozenset({
    "obj_id", "Name", "Mineral_Primaer", "Varietaet", "Kategorie",
    "Fundort", "status",
    "Confidence_Prozent", "Funddatum", "Gewicht_g",
    # Physikalische Eigenschaften: sowohl untere (``_min``) als auch obere
    # Bereichsgrenze (``_max``). Sammler-Reihenfolge "vom weichsten zum haertesten"
    # arbeitet mit _min; "wer hat das robusteste/dichteste Maximum?" mit _max
    # (z.B. fuer Polier-Auswahl per Mohs-Obergrenze).
    "Mohs_Haerte_min", "Mohs_Haerte_max",
    "Dichte_min_gcm3", "Dichte_max_gcm3",
    # Geometrische Dimensionen fuer Vitrinen-/Schubladen-Auswahl: nach jeder
    # Achse einzeln sortierbar. Volumen waere idealer, ist aber kein Schema-Feld.
    "Laenge_mm", "Breite_mm", "Hoehe_mm",
    "erstellt_am", "geaendert_am",
    "bilder", "gesamtwert_chf",
})

# Berechnete Aliase im SELECT (kein o.-Prefix beim ORDER BY).
_COMPUTED_COLUMNS: frozenset[str] = frozenset({"bilder", "gesamtwert_chf"})


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fts_query(text: str) -> str:
    tokens = [t.replace('"', "") for t in text.split() if t.strip()]
    return " ".join(f'"{t}"*' for t in tokens)


def _like_escape(text: str) -> str:
    """Escapt SQL-LIKE-Metazeichen (``%``/``_``/``\\``) im Nutzereingabe-Pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _order_by_clause(sort_by: str | None, sort_desc: bool) -> str:
    if not sort_by:
        return " ORDER BY o.obj_id"
    if sort_by not in SORTABLE_COLUMNS:
        raise ValueError(f"Unzulaessige Sortierspalte: {sort_by}")
    direction = "DESC" if sort_desc else "ASC"
    # Berechnete Aliase (z.B. 'bilder', 'gesamtwert_chf') stehen ohne o.-Prefix.
    prefix = "" if sort_by in _COMPUTED_COLUMNS else "o."
    # NULLs hinten + stabile Zweitsortierung nach ID
    return (f" ORDER BY ({prefix}{sort_by} IS NULL), "
            f"{prefix}{sort_by} {direction}, o.obj_id")


class ObjectRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_objects(self, search: str = "", status: str = "",
                     status_in: list[str] | tuple[str, ...] | None = None,
                     mineral: str = "",
                     mineral_in: list[str] | tuple[str, ...] | None = None,
                     kategorie: str = "",
                     kategorie_in: list[str] | tuple[str, ...] | None = None,
                     only_images: bool = False,
                     has_bilder: bool | None = None,
                     has_image_kategorie: str = "",
                     missing_image_kategorie: str = "",
                     min_confidence: int | None = None,
                     max_confidence: int | None = None,
                     has_confidence: bool | None = None,
                     has_funddatum: bool | None = None,
                     has_mineral: bool | None = None,
                     has_notizen: bool | None = None,
                     has_pruefempfehlungen: bool | None = None,
                     has_gewicht: bool | None = None,
                     has_wert: bool | None = None,
                     funddatum_jahr_min: int | None = None,
                     funddatum_jahr_max: int | None = None,
                     funddatum_jahr_in: list[int] | tuple[int, ...] | None = None,
                     funddatum_monat: int | None = None,
                     funddatum_min: str | None = None,
                     funddatum_max: str | None = None,
                     fundort: str = "",
                     fundort_in: list[str] | tuple[str, ...] | None = None,
                     fundort_contains: str = "",
                     mineral_contains: str = "",
                     name_contains: str = "",
                     notizen_contains: str = "",
                     wert_min: float | None = None,
                     wert_max: float | None = None,
                     gewicht_min: float | None = None,
                     gewicht_max: float | None = None,
                     laenge_min: float | None = None,
                     laenge_max: float | None = None,
                     breite_min: float | None = None,
                     breite_max: float | None = None,
                     hoehe_min: float | None = None,
                     hoehe_max: float | None = None,
                     kristallsystem: str = "",
                     kristallsystem_in: list[str] | tuple[str, ...] | None = None,
                     beste_verwendung: str = "",
                     beste_verwendung_in: list[str] | tuple[str, ...] | None = None,
                     glanz: str = "",
                     glanz_in: list[str] | tuple[str, ...] | None = None,
                     transparenz: str = "",
                     transparenz_in: list[str] | tuple[str, ...] | None = None,
                     magnetismus_in: list[str] | tuple[str, ...] | None = None,
                     spaltbarkeit_in: list[str] | tuple[str, ...] | None = None,
                     bruch_in: list[str] | tuple[str, ...] | None = None,
                     varietaet: str = "",
                     varietaet_in: list[str] | tuple[str, ...] | None = None,
                     varietaet_contains: str = "",
                     gesteinsart: str = "",
                     gesteinsart_in: list[str] | tuple[str, ...] | None = None,
                     gesteinsart_contains: str = "",
                     sort_by: str | None = None,
                     sort_desc: bool = False) -> list[sqlite3.Row]:
        from stonebook.db.stats import wert_pro_objekt_sql
        wert_sql = wert_pro_objekt_sql()
        sql = f"""
            SELECT o.obj_id, o.Name, o.Mineral_Primaer, o.Fundort, o.status,
                   o.Confidence_Prozent, o.Funddatum,
                   (SELECT COUNT(*) FROM images i WHERE i.obj_id = o.obj_id) AS bilder,
                   {wert_sql} AS gesamtwert_chf
            FROM objects o
        """
        where, params = [], []
        if search.strip():
            where.append("o.rowid IN (SELECT rowid FROM objects_fts WHERE objects_fts MATCH ?)")
            params.append(_fts_query(search))
        if status:
            where.append("o.status = ?")
            params.append(status)
        # status_in: Mengen-Filter ("aktiv ODER archiviert, aber nicht platzhalter").
        # Ergaenzend zum exakten ``status``-Filter; beide kombinierbar (Schnittmenge).
        # Validiert gegen VALID_STATUSES, damit Tippfehler keinen leeren Filter erzeugen.
        if status_in:
            statuses = [s for s in status_in if s]
            invalid = [s for s in statuses if s not in VALID_STATUSES]
            if invalid:
                raise ValueError(
                    f"Unbekannte Status-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_STATUSES)})")
            if statuses:
                placeholders = ", ".join("?" * len(statuses))
                where.append(f"o.status IN ({placeholders})")
                params.extend(statuses)
        if mineral:
            where.append("o.Mineral_Primaer = ?")
            params.append(mineral)
        # mineral_in: Mengen-Filter ("Quarz ODER Calcit ODER Pyrit") fuer das
        # Multiselect-Dropdown der Mineral-Liste. Mineral_Primaer ist Freitext
        # (kein Feldwoerterbuch-Enum), daher keine Enum-Validierung wie bei
        # kategorie_in/status_in - der GUI-Caller liefert die Werte ohnehin
        # aus distinct_values("Mineral_Primaer"). Leere Eintraege werden
        # uebersprungen, damit kein degenerierter IN-Filter entsteht.
        # Kombinierbar mit dem exakten ``mineral``-Filter (Schnittmenge) und
        # mit ``mineral_contains`` (LIKE-Substring auf der Familien-Ebene).
        if mineral_in:
            minerals = [m for m in mineral_in if m]
            if minerals:
                placeholders = ", ".join("?" * len(minerals))
                where.append(f"o.Mineral_Primaer IN ({placeholders})")
                params.extend(minerals)
        if kategorie:
            where.append("o.Kategorie = ?")
            params.append(kategorie)
        # kategorie_in: Mengen-Filter ("Handstueck ODER Kristall", aber nicht
        # Geroell/Sonstiges). Spiegelt status_in / kristallsystem_in /
        # beste_verwendung_in: validiert gegen VALID_KATEGORIEN aus dem
        # Feldwoerterbuch, damit Tippfehler einen klaren Fehler statt eines
        # stillen Leerergebnisses erzeugen. Kombinierbar mit dem exakten
        # ``kategorie``-Filter (Schnittmenge).
        if kategorie_in:
            kats = [k for k in kategorie_in if k]
            invalid = [k for k in kats if k not in VALID_KATEGORIEN]
            if invalid:
                raise ValueError(
                    f"Unbekannte Kategorie-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_KATEGORIEN)})")
            if kats:
                placeholders = ", ".join("?" * len(kats))
                where.append(f"o.Kategorie IN ({placeholders})")
                params.extend(kats)
        # has_bilder ist die kanonische Form (True/False/None); only_images bleibt
        # als Legacy-Alias erhalten und mappt auf has_bilder=True, falls dieses
        # noch nicht gesetzt ist (kein Konflikt zwischen den beiden Flags).
        effective_has_bilder = has_bilder if has_bilder is not None else (
            True if only_images else None)
        if effective_has_bilder is True:
            where.append("EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id)")
        elif effective_has_bilder is False:
            where.append("NOT EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id)")
        # has_image_kategorie: nur Objekte mit mindestens einem Bild der genannten Kategorie.
        # missing_image_kategorie: nur Objekte ohne Bild dieser Kategorie - typische
        # Foto-Workflow-Frage ("welche Objekte fehlen UV365-Aufnahmen?").
        # Beide validieren gegen IMAGE_CATEGORIES, damit Tippfehler keinen leeren
        # Filter erzeugen (sondern einen klaren Fehler).
        if has_image_kategorie:
            if has_image_kategorie not in IMAGE_CATEGORIES:
                raise ValueError(f"Unbekannte Bild-Kategorie: {has_image_kategorie!r}")
            where.append(
                "EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id "
                "AND i.kategorie = ?)")
            params.append(has_image_kategorie)
        if missing_image_kategorie:
            if missing_image_kategorie not in IMAGE_CATEGORIES:
                raise ValueError(
                    f"Unbekannte Bild-Kategorie: {missing_image_kategorie!r}")
            where.append(
                "NOT EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id "
                "AND i.kategorie = ?)")
            params.append(missing_image_kategorie)
        if min_confidence is not None:
            where.append("o.Confidence_Prozent >= ?")
            params.append(int(min_confidence))
        if max_confidence is not None:
            where.append("o.Confidence_Prozent <= ?")
            params.append(int(max_confidence))
        if has_confidence is True:
            where.append("o.Confidence_Prozent IS NOT NULL")
        elif has_confidence is False:
            where.append("o.Confidence_Prozent IS NULL")
        if has_funddatum is True:
            where.append("o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != ''")
        elif has_funddatum is False:
            where.append("(o.Funddatum IS NULL OR TRIM(o.Funddatum) = '')")
        if has_mineral is True:
            where.append("o.Mineral_Primaer IS NOT NULL AND TRIM(o.Mineral_Primaer) != ''")
        elif has_mineral is False:
            where.append("(o.Mineral_Primaer IS NULL OR TRIM(o.Mineral_Primaer) = '')")
        if has_notizen is True:
            where.append("o.notizen IS NOT NULL AND TRIM(o.notizen) != ''")
        elif has_notizen is False:
            where.append("(o.notizen IS NULL OR TRIM(o.notizen) = '')")
        if has_pruefempfehlungen is True:
            where.append("o.Pruefempfehlungen IS NOT NULL AND TRIM(o.Pruefempfehlungen) != ''")
        elif has_pruefempfehlungen is False:
            where.append("(o.Pruefempfehlungen IS NULL OR TRIM(o.Pruefempfehlungen) = '')")
        # has_gewicht: tri-state Filter fuer Objekte mit/ohne Wiegegewicht.
        # 0.0 zaehlt wie 'kein Wert' (in der Praxis nicht gewogen, nicht echt 0 g).
        if has_gewicht is True:
            where.append("o.Gewicht_g IS NOT NULL AND o.Gewicht_g > 0")
        elif has_gewicht is False:
            where.append("(o.Gewicht_g IS NULL OR o.Gewicht_g <= 0)")
        # has_wert: tri-state Filter ueber die Summe aller CHF-Wertfelder.
        # Selbe Definition wie objekte_mit_wert in der Statistik
        # (wert_pro_objekt_sql() > 0). Findet Objekte, die noch geschaetzt werden muessen.
        if has_wert is True:
            where.append(f"{wert_sql} > 0")
        elif has_wert is False:
            where.append(f"{wert_sql} <= 0")
        if funddatum_jahr_min is not None or funddatum_jahr_max is not None:
            where.append("substr(o.Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
            if funddatum_jahr_min is not None:
                where.append("CAST(substr(o.Funddatum, 1, 4) AS INTEGER) >= ?")
                params.append(int(funddatum_jahr_min))
            if funddatum_jahr_max is not None:
                where.append("CAST(substr(o.Funddatum, 1, 4) AS INTEGER) <= ?")
                params.append(int(funddatum_jahr_max))
        # funddatum_jahr_in: diskrete Jahres-Menge ("Funde aus 2018 ODER 2020 ODER
        # 2024") - komplementaer zum Bereichsfilter funddatum_jahr_min/_max, der
        # ein zusammenhaengendes Intervall vorgibt. Validierung: jeder Eintrag
        # muss ein realistisches Jahr 1800..2999 sein; sonst ValueError mit klarer
        # Diagnose (statt eines stillen Leerergebnisses fuer "2023" als String).
        if funddatum_jahr_in:
            jahre = [int(j) for j in funddatum_jahr_in]
            invalid = [j for j in jahre if not 1800 <= j <= 2999]
            if invalid:
                raise ValueError(
                    f"Unbekannte Funddatum-Jahre: {invalid} "
                    f"(erwartet 1800..2999)")
            if jahre:
                placeholders = ", ".join("?" * len(jahre))
                where.append(
                    f"substr(o.Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    f"AND CAST(substr(o.Funddatum, 1, 4) AS INTEGER) IN "
                    f"({placeholders})")
                params.extend(jahre)
        # funddatum_monat: Saison-Filter ("alle Juli-Funde", ueber alle Jahre).
        # Komplementaer zum Jahres-Bereich oben (zeit-vs-saisonal); spiegelt das
        # by_funddatum_monat-Aggregat in der Statistik. Erwartet 1..12 (Tippfehler
        # 0/13 erzeugen einen klaren Fehler statt eines leeren Ergebnisses).
        # Pruefung gegen Monatsteil 01..12 (siehe _count_funddatum_monat); reine
        # Jahresangaben ohne Monat fallen automatisch heraus.
        if funddatum_monat is not None:
            m = int(funddatum_monat)
            if not 1 <= m <= 12:
                raise ValueError(
                    f"funddatum_monat muss zwischen 1 und 12 liegen (war: {m})")
            where.append(
                "o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != '' "
                "AND substr(o.Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                "AND substr(o.Funddatum, 6, 2) GLOB '[0-1][0-9]' "
                "AND CAST(substr(o.Funddatum, 6, 2) AS INTEGER) = ?")
            params.append(m)
        # Funddatum-Bereich auf Tagesgenauigkeit: ISO YYYY-MM-DD lexikographisch
        # vergleichbar. Akzeptiert auch YYYY-MM oder YYYY allein.
        if funddatum_min is not None:
            where.append("o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != '' "
                         "AND o.Funddatum >= ?")
            params.append(str(funddatum_min))
        if funddatum_max is not None:
            where.append("o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != '' "
                         "AND o.Funddatum <= ?")
            params.append(str(funddatum_max))
        if fundort:
            where.append("o.Fundort = ?")
            params.append(fundort)
        # fundort_in: Mengen-Filter ("Davos ODER Zermatt ODER St. Gallen")
        # fuer Reise- oder Regions-Auswertungen. Fundort ist Freitext (Ort plus
        # optionale Detail-Angabe wie "St. Gallen, Sitter"), daher keine
        # Enum-Validierung; leere Eintraege werden uebersprungen. Kombinierbar
        # mit exaktem ``fundort``-Filter und mit ``fundort_contains`` (Regions-
        # Substring fuer "St. Gallen, Sitter" + "St. Gallen, Bahnhof").
        if fundort_in:
            orte = [o for o in fundort_in if o]
            if orte:
                placeholders = ", ".join("?" * len(orte))
                where.append(f"o.Fundort IN ({placeholders})")
                params.extend(orte)
        if fundort_contains:
            # Substring-Filter fuer Sammel-Regionen ("St. Gallen, Sitter" + "St. Gallen, Bahnhof").
            # LIKE ist case-insensitive fuer ASCII; fuer Umlaute reicht das in der CH-Praxis aus.
            where.append("o.Fundort LIKE ? ESCAPE '\\'")
            params.append("%" + _like_escape(fundort_contains) + "%")
        # Substring-Filter ueber Name (Bezeichnung) und notizen (Freitext); LIKE-Metas
        # werden escapet, sodass z.B. "_42" wortwoertlich trifft. Volltext-Suche
        # ueber FTS gibt es bereits via ``search`` -- diese Filter sind die schlanke
        # Alternative, ohne MATCH-Syntax und mit garantiertem Substring-Match (FTS5
        # tokenisiert; "Mineral_42" wuerde dort nicht direkt als ein Token treffen).
        if mineral_contains:
            # Substring-Filter ueber Mineral_Primaer: findet Familien-Varianten
            # ("Quarz" trifft "Rauchquarz", "Rosenquarz", "Bergkristall" nicht, aber
            # "quarz" trifft alle Quarz-Varietaeten ohne Kenntnis der exakten Schreibweise).
            # Komplementaer zum exakten ``mineral``-Filter (Dropdown-Auswahl).
            where.append("o.Mineral_Primaer LIKE ? ESCAPE '\\'")
            params.append("%" + _like_escape(mineral_contains) + "%")
        if name_contains:
            where.append("o.Name LIKE ? ESCAPE '\\'")
            params.append("%" + _like_escape(name_contains) + "%")
        if notizen_contains:
            where.append("o.notizen LIKE ? ESCAPE '\\'")
            params.append("%" + _like_escape(notizen_contains) + "%")
        if wert_min is not None:
            where.append(f"{wert_sql} >= ?")
            params.append(float(wert_min))
        if wert_max is not None:
            where.append(f"{wert_sql} <= ?")
            params.append(float(wert_max))
        if gewicht_min is not None:
            where.append("o.Gewicht_g >= ?")
            params.append(float(gewicht_min))
        if gewicht_max is not None:
            where.append("o.Gewicht_g <= ?")
            params.append(float(gewicht_max))
        # Dimensionen-Filter fuer Vitrinen-/Schubladen-Auswahl: "welche Stuecke
        # passen in einen 100mm-Sortierkasten?" -> laenge_max=100. Drei Achsen
        # einzeln filterbar, weil ein langes flaches Stueck (200x50x10) in eine
        # andere Vitrine passt als ein wuerfelfoermiges (60x60x60). NULL-Eintraege
        # (nicht vermessene Stuecke) bleiben durch die ?-Vergleiche aussen vor.
        if laenge_min is not None:
            where.append("o.Laenge_mm >= ?")
            params.append(float(laenge_min))
        if laenge_max is not None:
            where.append("o.Laenge_mm <= ?")
            params.append(float(laenge_max))
        if breite_min is not None:
            where.append("o.Breite_mm >= ?")
            params.append(float(breite_min))
        if breite_max is not None:
            where.append("o.Breite_mm <= ?")
            params.append(float(breite_max))
        if hoehe_min is not None:
            where.append("o.Hoehe_mm >= ?")
            params.append(float(hoehe_min))
        if hoehe_max is not None:
            where.append("o.Hoehe_mm <= ?")
            params.append(float(hoehe_max))
        if kristallsystem:
            where.append("o.Kristallsystem = ?")
            params.append(kristallsystem)
        # kristallsystem_in: Mengen-Filter ("trigonal ODER hexagonal" fuer Quarz-Familie).
        # Spiegelt status_in: validiert gegen VALID_KRISTALLSYSTEME aus dem Feldwoerterbuch,
        # damit Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses erzeugen.
        # Kombinierbar mit dem exakten ``kristallsystem``-Filter (Schnittmenge).
        if kristallsystem_in:
            systems = [s for s in kristallsystem_in if s]
            invalid = [s for s in systems if s not in VALID_KRISTALLSYSTEME]
            if invalid:
                raise ValueError(
                    f"Unbekannte Kristallsystem-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_KRISTALLSYSTEME)})")
            if systems:
                placeholders = ", ".join("?" * len(systems))
                where.append(f"o.Kristallsystem IN ({placeholders})")
                params.extend(systems)
        if beste_verwendung:
            where.append("o.Beste_Verwendung = ?")
            params.append(beste_verwendung)
        # beste_verwendung_in: Mengen-Filter ("Schmuck ODER Sammlung", aber nicht
        # Industrie/Talisman). Spiegelt status_in / kristallsystem_in: validiert
        # gegen VALID_BESTE_VERWENDUNG, damit Tippfehler einen klaren Fehler
        # statt eines stillen Leerergebnisses erzeugen.
        if beste_verwendung_in:
            uses = [v for v in beste_verwendung_in if v]
            invalid = [v for v in uses if v not in VALID_BESTE_VERWENDUNG]
            if invalid:
                raise ValueError(
                    f"Unbekannte Beste_Verwendung-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_BESTE_VERWENDUNG)})")
            if uses:
                placeholders = ", ".join("?" * len(uses))
                where.append(f"o.Beste_Verwendung IN ({placeholders})")
                params.extend(uses)
        if glanz:
            where.append("o.Glanz = ?")
            params.append(glanz)
        # glanz_in: Mengen-Filter ("glasig ODER metallisch ODER seidig") fuer die
        # optische Auswahl. Spiegelt kristallsystem_in / beste_verwendung_in:
        # validiert gegen VALID_GLANZ aus dem Feldwoerterbuch, damit Tippfehler
        # einen klaren Fehler statt eines stillen Leerergebnisses erzeugen.
        # Kombinierbar mit dem exakten ``glanz``-Filter (Schnittmenge).
        if glanz_in:
            glanze = [g for g in glanz_in if g]
            invalid = [g for g in glanze if g not in VALID_GLANZ]
            if invalid:
                raise ValueError(
                    f"Unbekannte Glanz-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_GLANZ)})")
            if glanze:
                placeholders = ", ".join("?" * len(glanze))
                where.append(f"o.Glanz IN ({placeholders})")
                params.extend(glanze)
        if transparenz:
            where.append("o.Transparenz = ?")
            params.append(transparenz)
        # transparenz_in: Mengen-Filter ("durchsichtig ODER durchscheinend")
        # fuer Foto-Setup-Auswahl: lichtdurchlaessige Stuecke brauchen Back-
        # light, opake nicht. Spiegelt glanz_in / kristallsystem_in: validiert
        # gegen VALID_TRANSPARENZ (durchsichtig/durchscheinend/opak), damit
        # Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses
        # erzeugen. Kombinierbar mit dem exakten ``transparenz``-Filter.
        if transparenz_in:
            trs = [t for t in transparenz_in if t]
            invalid = [t for t in trs if t not in VALID_TRANSPARENZ]
            if invalid:
                raise ValueError(
                    f"Unbekannte Transparenz-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_TRANSPARENZ)})")
            if trs:
                placeholders = ", ".join("?" * len(trs))
                where.append(f"o.Transparenz IN ({placeholders})")
                params.extend(trs)
        # magnetismus_in: Mengen-Filter ("ja ODER schwach") als Eisen-Auswahl -
        # alle magnetisch reagierenden Stuecke (Magnetit/Pyrrhotin/Haematit/
        # Ilmenit) in einer Sicht, ohne dass die inerten Quarz-/Calcit-Stuecke
        # mitkommen. Spiegelt glanz_in/transparenz_in: validiert gegen
        # VALID_MAGNETISMUS (ja/schwach/nein), damit Tippfehler einen klaren
        # Fehler statt eines stillen Leerergebnisses erzeugen.
        if magnetismus_in:
            mags = [m for m in magnetismus_in if m]
            invalid = [m for m in mags if m not in VALID_MAGNETISMUS]
            if invalid:
                raise ValueError(
                    f"Unbekannte Magnetismus-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_MAGNETISMUS)})")
            if mags:
                placeholders = ", ".join("?" * len(mags))
                where.append(f"o.Magnetismus IN ({placeholders})")
                params.extend(mags)
        # spaltbarkeit_in: Mengen-Filter ("vollkommen ODER gut") als Praeparier-
        # Auswahl - alle sauber spaltbaren Stuecke (Calcit/Fluorit/Glimmer) in
        # einer Sicht, ohne dass die zaehen Quarz-Brocken (keine) mitkommen.
        # Spiegelt magnetismus_in/transparenz_in: validiert gegen
        # VALID_SPALTBARKEIT (vollkommen/gut/deutlich/undeutlich/keine), damit
        # Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses
        # erzeugen.
        if spaltbarkeit_in:
            sps = [s for s in spaltbarkeit_in if s]
            invalid = [s for s in sps if s not in VALID_SPALTBARKEIT]
            if invalid:
                raise ValueError(
                    f"Unbekannte Spaltbarkeit-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_SPALTBARKEIT)})")
            if sps:
                placeholders = ", ".join("?" * len(sps))
                where.append(f"o.Spaltbarkeit IN ({placeholders})")
                params.extend(sps)
        # bruch_in: Mengen-Filter ("muschelig ODER splittrig") als Schaerfe-
        # kanten-Auswahl - Stuecke, die ohne Spaltflaechen scharfe Kanten
        # erzeugen (Obsidian/Quarz/Feuerstein), in einer Sicht ohne fasrige
        # Aktinolith-/erdige Limonit-Stuecke. Spiegelt spaltbarkeit_in/
        # magnetismus_in: validiert gegen VALID_BRUCH (muschelig/uneben/
        # splittrig/faserig/erdig/glatt), damit Tippfehler einen klaren
        # Fehler statt eines stillen Leerergebnisses erzeugen.
        if bruch_in:
            brs = [b for b in bruch_in if b]
            invalid = [b for b in brs if b not in VALID_BRUCH]
            if invalid:
                raise ValueError(
                    f"Unbekannte Bruch-Werte: {invalid} "
                    f"(erwartet aus {sorted(VALID_BRUCH)})")
            if brs:
                placeholders = ", ".join("?" * len(brs))
                where.append(f"o.Bruch IN ({placeholders})")
                params.extend(brs)
        if varietaet:
            where.append("o.Varietaet = ?")
            params.append(varietaet)
        # varietaet_in: Mengen-Filter ("Bergkristall ODER Milchquarz ODER Rauchquarz")
        # innerhalb einer Mineral-Familie. Freitext-Feld wie Mineral_Primaer (kein
        # Feldwoerterbuch-Enum), daher keine Enum-Validierung; leere Eintraege
        # werden uebersprungen. Kombinierbar mit exaktem ``varietaet``-Filter und
        # mit ``varietaet_contains`` (Substring-Familie).
        if varietaet_in:
            vars_ = [v for v in varietaet_in if v]
            if vars_:
                placeholders = ", ".join("?" * len(vars_))
                where.append(f"o.Varietaet IN ({placeholders})")
                params.extend(vars_)
        if varietaet_contains:
            # Substring-Filter ueber Varietaet: findet Familien wie "Jaspis" (Roter Jaspis,
            # Bunter Jaspis, Brekzien-Jaspis) ohne Kenntnis der exakten Notation.
            # Komplementaer zum exakten ``varietaet``-Filter (Dropdown-Auswahl).
            where.append("o.Varietaet LIKE ? ESCAPE '\\'")
            params.append("%" + _like_escape(varietaet_contains) + "%")
        if gesteinsart:
            where.append("o.Gesteinsart = ?")
            params.append(gesteinsart)
        # gesteinsart_in: Mengen-Filter ("Granit ODER Gneis ODER Basalt") fuer
        # die petrologische Auswahl. Freitext-Feld wie Mineral_Primaer/Varietaet
        # (kein Feldwoerterbuch-Enum), daher keine Enum-Validierung; leere
        # Eintraege werden uebersprungen. Kombinierbar mit exaktem
        # ``gesteinsart``-Filter und mit ``gesteinsart_contains``.
        if gesteinsart_in:
            ges = [g for g in gesteinsart_in if g]
            if ges:
                placeholders = ", ".join("?" * len(ges))
                where.append(f"o.Gesteinsart IN ({placeholders})")
                params.extend(ges)
        if gesteinsart_contains:
            # Substring-Filter ueber Gesteinsart: findet Gesteins-Familien wie "Granit"
            # (Biotitgranit, Rosa Granit, Granitporphyr) ohne Kenntnis der exakten Notation.
            # Komplementaer zum exakten ``gesteinsart``-Filter (Dropdown-Auswahl);
            # spiegelt das Muster der anderen *_contains-Filter (Fundort/Mineral/Varietaet).
            where.append("o.Gesteinsart LIKE ? ESCAPE '\\'")
            params.append("%" + _like_escape(gesteinsart_contains) + "%")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += _order_by_clause(sort_by, sort_desc)
        return self.conn.execute(sql, params).fetchall()

    def get(self, obj_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM objects WHERE obj_id = ?", (obj_id,)).fetchone()

    def exists(self, obj_id: str) -> bool:
        return self.get(obj_id) is not None

    def create(self, obj_id: str, **fields) -> None:
        cols = ["obj_id", "erstellt_am", "geaendert_am"]
        vals = [obj_id, _now(), _now()]
        for k, v in fields.items():
            cols.append(k)
            vals.append(v)
        sql = f"INSERT INTO objects ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        self.conn.execute(sql, vals)
        self.conn.commit()

    def update_fields(self, obj_id: str, fields: dict) -> None:
        if not fields:
            return
        fields = dict(fields)
        fields["geaendert_am"] = _now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE objects SET {sets} WHERE obj_id = ?",
                          [*fields.values(), obj_id])
        self.conn.commit()

    def merge_nonempty(self, obj_id: str, fields: dict) -> list[str]:
        """Setzt nur nicht-leere Werte; gibt Liste der Konfliktfelder zurück (vorhandener Wert != neuer Wert)."""
        current = self.get(obj_id)
        if current is None:
            return []
        conflicts, updates = [], {}
        for k, v in fields.items():
            if is_empty(v):
                continue
            old = current[k]
            if not is_empty(old) and str(old) != str(v):
                conflicts.append(k)
                continue
            updates[k] = v
        if updates:
            self.update_fields(obj_id, updates)
        return conflicts

    def delete(self, obj_id: str) -> None:
        self.conn.execute("DELETE FROM objects WHERE obj_id = ?", (obj_id,))
        self.conn.commit()

    def set_status(self, obj_id: str, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Ungueltiger Status: {status!r} "
                f"(erwartet einen aus {sorted(VALID_STATUSES)})")
        self.update_fields(obj_id, {"status": status})

    def archive(self, obj_id: str) -> None:
        """Markiert ein Objekt als ``archiviert`` (refresh_status laesst es danach in Ruhe)."""
        self.set_status(obj_id, "archiviert")

    def unarchive(self, obj_id: str) -> None:
        """Hebt eine Archivierung auf; Folgestatus (aktiv/platzhalter) wird automatisch bestimmt."""
        row = self.get(obj_id)
        if row is None:
            return
        if row["status"] == "archiviert":
            # Auf platzhalter zuruecksetzen, damit refresh_status den passenden Status berechnet
            self.conn.execute(
                "UPDATE objects SET status = 'platzhalter' WHERE obj_id = ?", (obj_id,))
            self.conn.commit()
            self.refresh_status(obj_id)

    def refresh_status(self, obj_id: str) -> None:
        """platzhalter → aktiv, sobald Felddaten oder Bilder vorhanden sind."""
        row = self.get(obj_id)
        if row is None or row["status"] == "archiviert":
            return
        has_data = any(not is_empty(row[c]) for c in DATA_COLS)
        has_images = self.conn.execute(
            "SELECT 1 FROM images WHERE obj_id = ? LIMIT 1", (obj_id,)).fetchone() is not None
        status = "aktiv" if (has_data or has_images) else "platzhalter"
        if status != row["status"]:
            self.conn.execute("UPDATE objects SET status = ? WHERE obj_id = ?", (status, obj_id))
            self.conn.commit()

    def refresh_status_all(self) -> int:
        """Setzt status fuer alle nicht-archivierten Objekte in einem SQL-Statement.

        Aequivalent zu :meth:`refresh_status` ueber alle Objekte, aber O(1)
        Roundtrips statt O(N). Liefert die Anzahl tatsaechlich geaenderter
        Zeilen. ``archiviert`` bleibt erhalten.
        """
        data_check = " OR ".join(
            f"(TRIM(COALESCE({c}, '')) != '')" for c in DATA_COLS
        )
        # Ziel-Status berechnen; nur schreiben, wenn er sich aendert (sonst
        # erzeugt das UPDATE unnoetige FTS-Trigger-Aktivitaet).
        sql = (
            "UPDATE objects SET status = CASE "
            f"WHEN ({data_check}) OR EXISTS("
            "  SELECT 1 FROM images i WHERE i.obj_id = objects.obj_id"
            ") THEN 'aktiv' ELSE 'platzhalter' END "
            "WHERE status != 'archiviert' "
            f"  AND status != CASE WHEN ({data_check}) OR EXISTS("
            "    SELECT 1 FROM images i WHERE i.obj_id = objects.obj_id"
            "  ) THEN 'aktiv' ELSE 'platzhalter' END"
        )
        cur = self.conn.execute(sql)
        self.conn.commit()
        return cur.rowcount

    def next_free_id(self) -> str:
        rows = self.conn.execute(
            "SELECT obj_id FROM objects UNION SELECT alias_id FROM aliases").fetchall()
        max_n = 0
        for r in rows:
            try:
                max_n = max(max_n, int(str(r[0]).split("_")[1]))
            except (IndexError, ValueError):
                pass
        return f"OBJ_{max_n + 1:04d}"

    def distinct_values(self, column: str) -> list[str]:
        if column not in DATA_COLS:
            raise ValueError(f"Unbekannte Spalte: {column}")
        rows = self.conn.execute(
            f"SELECT DISTINCT {column} FROM objects "
            f"WHERE {column} IS NOT NULL AND TRIM({column}) != '' ORDER BY {column}").fetchall()
        return [r[0] for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]

    def statistics(self) -> dict:
        """Legacy-Adapter mit fixierter Dict-Form fuer das Dashboard.

        Delegiert an :func:`stonebook.db.stats.compute_statistics`; behaelt die
        bisherigen Schluessel bei (gesamt/status/top_minerals/mit_bildern/...).
        """
        from stonebook.db.stats import compute_statistics

        st = compute_statistics(self.conn, top_fundorte=0, top_wert=0)
        avg = st.durchschnitt_confidence_prozent
        return {
            "gesamt": st.objekte_total,
            "status": dict(st.by_status),
            "top_minerals": list(st.by_mineral.items())[:10],
            "mit_bildern": st.objekte_mit_bildern,
            "bilder_gesamt": st.bilder_total,
            "aliase": st.aliase_total,
            "wert_roh_chf": round(st.wert_roh_summe_chf, 2),
            "durchschnitt_confidence": round(avg, 1) if avg is not None else None,
        }


class ImageRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, obj_id: str, kategorie: str, rel_path: str, dateiname: str = "",
            sha256: str = "", exif_datum: str = "", breite_px: int | None = None,
            hoehe_px: int | None = None, herkunft_obj_id: str = "") -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO images
               (obj_id, kategorie, rel_path, dateiname, sha256, exif_datum,
                breite_px, hoehe_px, herkunft_obj_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (obj_id, kategorie, rel_path, dateiname, sha256, exif_datum,
             breite_px, hoehe_px, herkunft_obj_id))
        self.conn.commit()

    def for_object(self, obj_id: str, kategorie: str = "") -> list[sqlite3.Row]:
        sql = "SELECT * FROM images WHERE obj_id = ?"
        params: list = [obj_id]
        if kategorie:
            sql += " AND kategorie = ?"
            params.append(kategorie)
        sql += " ORDER BY kategorie, dateiname"
        return self.conn.execute(sql, params).fetchall()

    def reassign(self, from_obj: str, to_obj: str) -> None:
        self.conn.execute(
            "UPDATE images SET obj_id = ?, herkunft_obj_id = ? WHERE obj_id = ?",
            (to_obj, from_obj, from_obj))
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]


class AliasRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, alias_id: str, canonical_id: str, quelle: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO aliases (alias_id, canonical_id, merge_quelle) VALUES (?,?,?)",
            (alias_id, canonical_id, quelle))
        self.conn.commit()

    def canonical_for(self, alias_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT canonical_id FROM aliases WHERE alias_id = ?", (alias_id,)).fetchone()
        return row[0] if row else None

    def aliases_for(self, canonical_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT alias_id FROM aliases WHERE canonical_id = ? ORDER BY alias_id",
            (canonical_id,)).fetchall()
        return [r[0] for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]


class AnalysisRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, obj_id: str, modell: str, antwort_json: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) VALUES (?,?,?,?)",
            (obj_id, _now(), modell, antwort_json))
        self.conn.commit()
        return cur.lastrowid

    def set_uebernommen(self, analysis_id: int, uebernommen_json: str) -> None:
        self.conn.execute("UPDATE ki_analysen SET uebernommen_json = ? WHERE id = ?",
                          (uebernommen_json, analysis_id))
        self.conn.commit()

    def for_object(self, obj_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM ki_analysen WHERE obj_id = ? "
            "ORDER BY zeitpunkt DESC, id DESC",
            (obj_id,)).fetchall()

    def get(self, analysis_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM ki_analysen WHERE id = ?", (analysis_id,)).fetchone()

    def delete(self, analysis_id: int) -> bool:
        """Loescht eine einzelne KI-Analyse; gibt True zurueck, wenn etwas geloescht wurde."""
        cur = self.conn.execute("DELETE FROM ki_analysen WHERE id = ?", (analysis_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def prune(self, obj_id: str, keep: int) -> int:
        """Behaelt nur die ``keep`` neuesten Analysen je Objekt; loescht aeltere.

        ``keep < 0`` wirft ``ValueError``; ``keep == 0`` loescht alle Analysen
        des Objekts. Gibt die Zahl tatsaechlich geloeschter Zeilen zurueck.
        """
        if keep < 0:
            raise ValueError("keep muss >= 0 sein")
        cur = self.conn.execute(
            "DELETE FROM ki_analysen WHERE obj_id = ? AND id NOT IN ("
            " SELECT id FROM ki_analysen WHERE obj_id = ?"
            " ORDER BY zeitpunkt DESC, id DESC LIMIT ?)",
            (obj_id, obj_id, keep))
        self.conn.commit()
        return cur.rowcount

    def count_for(self, obj_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM ki_analysen WHERE obj_id = ?", (obj_id,)).fetchone()[0]
