"""CRUD-Schicht über der SQLite-DB."""
import datetime
import re
import sqlite3

from stonebook.fields import DATA_FIELDS, FIELD_BY_NAME, IMAGE_CATEGORIES, is_empty

DATA_COLS = [f.name for f in DATA_FIELDS]

# Strikte YYYY-MM-DD-Form ohne Uhrzeit-Zusatz. Wird von
# ``list_objects_mit_ungueltigem_funddatum`` als Pflege-Filter benutzt:
# Rohtext-Regex + datetime.date-Konstruktion, damit sowohl Struktur (10-Zeichen-
# Form) als auch semantische Gueltigkeit (kein 2024-13-01, kein 2024-02-30) in
# einem Zug geprueft werden.
_STRICT_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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
    "obj_id", "Name", "Mineral_Primaer", "Varietaet", "Gesteinsart", "Kategorie",
    # Gesteinsart als dritte mineralogische Sortier-Achse neben Mineral_Primaer
    # (Familie) und Varietaet (Sub-Klassifizierung): gruppiert Listen petrologisch
    # (Granit/Gneis/Basalt/Sandstein), waehrend Varietaet die mineralogische
    # Sub-Achse abdeckt - oft komplementaer, weil ein Quarz-Stueck eine andere
    # Gesteins-Einbettung hat als seine mineralogische Verwandtschaft (z.B.
    # Pegmatit-Quarz vs. Hydrothermal-Quarz). Spiegelt has_gesteinsart/
    # gesteinsart_in/wert_pro_gesteinsart auf die Sortier-Achse.
    "Fundort", "status",
    "Confidence_Prozent", "Funddatum", "Gewicht_g",
    # Physikalische Eigenschaften: sowohl untere (``_min``) als auch obere
    # Bereichsgrenze (``_max``). Sammler-Reihenfolge "vom weichsten zum haertesten"
    # arbeitet mit _min; "wer hat das robusteste/dichteste Maximum?" mit _max
    # (z.B. fuer Polier-Auswahl per Mohs-Obergrenze). Mohs_Haerte_Mitte ist die
    # Bereichs-Mittelpunkt-Achse als computed Column (spiegelt Volumen_mm3 auf
    # die Mohs-Achse): waehrend min/max nur die untere/obere Bereichsgrenze
    # zeigen (und bei Single-Point-Pflege wie "7" nur eines der beiden Felder
    # gesetzt ist, was Mohs_Haerte_min-Sortierung um "7 max only"-Stuecke
    # verschiebt), zeigt Mohs_Haerte_Mitte den typischen Wert pro Stueck
    # ((min+max)/2 bei zweiseitigem Bereich, der eine Wert bei Single-Point
    # via COALESCE) - die natuerliche Vitrinen-/Polier-Sortier-Frage "welche
    # Stuecke sind typisch weich/hart?" ohne separate Auswahl der Grenzachse.
    # Spiegelt die _mohs_durchschnitt/_mohs_median-Kollektions-Aggregation aus
    # stats.py auf die Listen-Sortier-Sicht (dort AVG/Median ueber alle
    # Mittelpunkte, hier der Mittelpunkt pro Objekt als Sortier-Achse).
    "Mohs_Haerte_min", "Mohs_Haerte_max", "Mohs_Haerte_Mitte",
    # Dichte_Mitte spiegelt Mohs_Haerte_Mitte auf die Massendichte-Achse:
    # dieselbe COALESCE-Kette ueber die zweiseitigen Dichte-Grenzen und dieselben
    # Single-Point-/Beide-NULL-Konventionen, damit die Kollektions-Aggregation
    # aus stats.py (_dichte_durchschnitt / _dichte_median / _dichte_standard-
    # abweichung, die alle auf demselben Objekt-Mittelpunkt-Ausdruck arbeiten)
    # in der Listen-Sortier-Sicht identisch verfuegbar ist. Sortier-Frage
    # "welche Stuecke sind typisch leicht/schwer (Bims/Opal vs. Pyrit/Galenit)?"
    # ohne separate Auswahl der Bereichsgrenze.
    "Dichte_min_gcm3", "Dichte_max_gcm3", "Dichte_Mitte",
    # Geometrische Dimensionen fuer Vitrinen-/Schubladen-Auswahl: nach jeder
    # Achse einzeln sortierbar. Volumen_mm3 (Produkt L*B*H) ist die kombinierte
    # Groessen-Achse als computed Column (spiegelt bilder/aliase/analysen/
    # gesamtwert_chf auf die Dimensions-Ebene): fuer die reine Vitrinen-Sortierung
    # "welches Stueck ist mein groesstes/kleinstes?" ist der Produkt-Wert die
    # natuerliche Antwort ohne dreifache Achsen-Vergleiche.
    "Laenge_mm", "Breite_mm", "Hoehe_mm", "Volumen_mm3",
    # Wert_pro_Gewicht_chf_g als spezifische Marktwert-Dichte je Gramm
    # (gesamtwert_chf / Gewicht_g) und Nutzwert-Ergaenzung zur bereits vorhandenen
    # gesamtwert_chf-Sortier-Achse: waehrend gesamtwert_chf die absolute Wert-
    # Summe pro Stueck beziffert (grosse schwere Stuecke stehen bei DESC oben,
    # unabhaengig davon, ob der Wert aus Masse oder aus Rarity kommt), zeigt die
    # spezifische Achse die "Wert-Dichte" - die Sammler-/Verkaeufer-Frage
    # "welche Stuecke sind pro Gramm am wertvollsten?" (Diamant/Rubin/Smaragd
    # in kleinen Karat-Portionen oben, faustgrosse Quarze/Calcite unten).
    # Komplementaer zu den drei Wert-Sichten: absolute Summe (gesamtwert_chf),
    # spezifische Massen-Dichte (dieses Feld) und spezifische Volumen-Dichte
    # (Wert_pro_Volumen_chf_mm3, eigene Achse). Sortier-Frage "welches Stueck
    # rentiert sich am meisten pro Gepaeck-Gramm bei Transport zur Boerse?" oder
    # "welche Vitrinen-Plaetze traegt am meisten Versicherungswert pro Kilo?".
    # NULL bei fehlender/Null-Masse (Gewicht_g IS NULL OR = 0) - die Division
    # waere entweder undefined oder unendlich, spiegelt die NULL-an-Ende-Konvention.
    "Wert_pro_Gewicht_chf_g",
    # Wert_pro_Volumen_chf_mm3 als spezifische Marktwert-Dichte je mm3 Bounding-
    # Box (gesamtwert_chf / (Laenge_mm * Breite_mm * Hoehe_mm)). Spiegelt
    # Wert_pro_Gewicht_chf_g auf die Volumen-Achse: waehrend die Massen-Dichte
    # die Frage "welche Stuecke rentieren sich pro Gramm?" beantwortet (kritisch
    # fuer Transport/Kurier), beantwortet die Volumen-Dichte "welche Stuecke
    # rentieren sich pro Vitrinen-/Schubladen-Platz?" (kritisch fuer knappen
    # Aufbewahrungs-Raum - Rubin-/Diamant-Splitter oben, faustgrosse Quarze
    # unten). Bereits im Sortier-Achsen-Kommentar oben als "eigene Achse"
    # angekuendigt und fuellt die dritte Wert-Sicht neben absoluter Summe
    # (gesamtwert_chf) und Massen-Dichte (Wert_pro_Gewicht_chf_g).
    # Der Nenner ist die axis-aligned Bounding-Box aus dem Volumen_mm3-Ausdruck;
    # NULL bei fehlender/Null-Vermessung (mindestens eine Dimension NULL oder
    # Produkt = 0) - die Division waere entweder undefined oder unendlich,
    # spiegelt die NULL-an-Ende-Konvention. Sammler-Reihenfolgen: Diamant-
    # Karat (~50-500 CHF/mm3) > Rubin-/Smaragd-Splitter (~5-50 CHF/mm3) >
    # Sammler-Bergkristall (~0.01-0.1 CHF/mm3) > faustgrosses Handstueck
    # (~0.001 CHF/mm3).
    "Wert_pro_Volumen_chf_mm3",
    # 1..10-Skalen aus dem Feldwoerterbuch: nach Seltenheit/Nachfrage sortieren
    # ist die natuerliche Begleitung zu den seltenheit_/nachfrage_-Filtern -
    # erst nach Rarity filtern, dann absteigend sortieren, um die Top-Stuecke
    # zu sehen. Seltenheit_Fundort ergaenzt die globale Sicht um die Standort-
    # Rarity (am Fundort selten vs. global selten - oft verschieden).
    "Seltenheit_global_1_10", "Seltenheit_Fundort_1_10", "Nachfrage_1_10",
    # Beste_Verwendung als Sortier-Achse fuer Verwendungs-Vorbereitung:
    # gruppiert die Liste nach Empfehlung (Schmuck/Sammlung/Forschung/Industrie/
    # Talisman/Dekoration) - vor Boersenbesuch oder Schmuck-Verkauf will man alle
    # passenden Stuecke beisammen sehen. Spiegelt beste_verwendung_in/by_beste_
    # verwendung/wert_pro_beste_verwendung auf die Sortier-Achse.
    "Beste_Verwendung",
    # Kristallsystem als Sortier-Achse fuer kristallographische Vorbereitung:
    # gruppiert die Liste nach Symmetrietyp (kubisch/tetragonal/hexagonal/
    # trigonal/orthorhombisch/monoklin/triklin/amorph). Vor Mikroskop-/
    # Diffraktometer-Sitzungen will man alle gleich-symmetrischen Stuecke
    # nebeneinander sehen. Spiegelt kristallsystem_in/by_kristallsystem/
    # wert_pro_kristallsystem auf die Sortier-Achse.
    "Kristallsystem",
    # Glanz als Sortier-Achse fuer optische Vorbereitung (Foto-/Vitrinen-Setup):
    # gruppiert die Liste nach Oberflaechen-Reflexion (glasig/wachsig/matt/
    # metallisch/fettig/seidig/perlmutt) - vor Foto-Session will man alle
    # glasigen Quarze und alle metallischen Pyrite beisammen haben, weil sie
    # gleiches Licht-Setup brauchen (glasig: gerichtetes Streiflicht, metallisch:
    # diffuser Schirm). Spiegelt glanz_in/by_glanz/wert_pro_glanz auf die
    # Sortier-Achse.
    "Glanz",
    # Transparenz als Sortier-Achse fuer Foto-/Vitrinen-Vorbereitung (Licht-Gang
    # vs. -Reflexion): gruppiert die Liste nach Lichtdurchlaessigkeit
    # (durchsichtig/durchscheinend/opak) - komplementaer zu Glanz (Oberflaechen-
    # Reflexion vs. Volumen-Lichtgang): durchsichtige Stuecke (Bergkristall)
    # brauchen Backlight, opake (Pyrit/Sediment) Frontlight. Drei Enum-Werte,
    # alphabetisch ergibt durchscheinend/durchsichtig/opak. Spiegelt
    # transparenz_in/by_transparenz/wert_pro_transparenz auf die Sortier-Achse.
    "Transparenz",
    # Magnetismus als Sortier-Achse fuer Eisen-Sortier-Sitzungen am Magneten:
    # gruppiert die Liste nach Reaktion (ja/schwach/nein) - vor einer Diagnostik-
    # Runde mit dem Neodym-Magneten will man alle erwartet reagierenden Stuecke
    # (Magnetit/Pyrrhotin: ja; Haematit/Ilmenit: schwach) beisammen testen, ohne
    # zwischen Quarz-/Calcit-Stuecken hin- und herzuspringen. Drei Enum-Werte,
    # alphabetisch ergibt ja/nein/schwach. Spiegelt magnetismus_in/by_magnetismus/
    # wert_pro_magnetismus auf die Sortier-Achse.
    "Magnetismus",
    # Spaltbarkeit als Sortier-Achse fuer Praeparier-/Polier-Sitzungen: gruppiert
    # die Liste nach Spaltflaechen-Klasse (vollkommen/gut/deutlich/undeutlich/
    # keine) - vor einer Schnitt-/Polier-Session will man die gut spaltbaren
    # Stuecke (Calcit/Fluorit/Glimmer) beisammen haben, weil sie ein anderes
    # Werkzeug-Setup brauchen als zaehe quarz-/obsidian-aehnliche Stuecke ohne
    # Spaltflaechen (Saege statt Hammer/Meissel). Fuenf Enum-Werte, alphabetisch
    # ergibt deutlich/gut/keine/undeutlich/vollkommen. Spiegelt spaltbarkeit_in/
    # by_spaltbarkeit/wert_pro_spaltbarkeit auf die Sortier-Achse.
    "Spaltbarkeit",
    # Bruch als Sortier-Achse fuer Bruchverhalten-Fotografie (Kantenlicht-
    # Session) und Verletzungs-Risiko-Sortierung: gruppiert die Liste nach
    # Bruchverhalten (muschelig/uneben/splittrig/faserig/erdig/glatt) -
    # komplementaer zu Spaltbarkeit (Spaltflaechen): muschelig brechende
    # Quarz-/Obsidian-Stuecke erzeugen scharfe Kanten, splittrige Stuecke noch
    # mehr - die Sortier-Achse hilft beim Beisammen-Halten der Hand-Vorsichts-
    # Klassen vor Polier-/Schneid-Sitzungen. Sechs Enum-Werte, alphabetisch
    # ergibt erdig/faserig/glatt/muschelig/splittrig/uneben. Spiegelt bruch_in/
    # by_bruch/wert_pro_bruch auf die Sortier-Achse.
    "Bruch",
    "erstellt_am", "geaendert_am",
    # Berechnete Spalten: bilder (Foto-Pflege-Sortierung), gesamtwert_chf
    # (Wert-Sortierung ueber alle Wert-Felder zusammen), aliase (Merge-Tiefe
    # pro Kanon-Objekt), analysen (KI-Analyse-Tiefe pro Objekt). aliase spiegelt
    # bilder auf die Provenienz-Achse: waehrend bilder die Foto-Pflege misst
    # (wie viele Aufnahmen pro Stueck), misst aliase die Merge-Historie (wie
    # viele historische Doppel-IDs sind auf dieses Kanon-Objekt zusammengefuehrt).
    # analysen spiegelt bilder/aliase auf die KI-Analyse-Achse: wie viele
    # KI-Laeufe wurden fuer dieses Stueck schon archiviert (Erst-Analyse, Re-
    # Analyse mit besserer Foto-Lage, A/B-Vergleich verschiedener Modelle).
    # Sortier-Achse fuer die KI-Pflege: "welche Objekte haben die tiefste KI-
    # Historie?" zeigt die am intensivsten analysierten Stuecke - typisch die
    # mineralogisch unsicheren Faelle, fuer die der Sammler mehrere Anfragen
    # gestartet hat (oft mit Tilt-/UV-/Mikroskop-Nachschuessen). Spiegelt
    # ki_analysen_total und objekte_mit_ki_analyse / quote_mit_ki_analyse_prozent
    # in stats.py auf die Listen-Sortier-Sicht. Objekte ohne Analyse erhalten
    # Zaehler 0 (COUNT-Subquery, kein NULL); die NULL-an-Ende-Konvention von
    # _order_by_clause greift hier also nicht, alle Werte sind sortier-vergleichbar.
    "bilder", "gesamtwert_chf", "aliase", "analysen",
})

# Berechnete Aliase im SELECT (kein o.-Prefix beim ORDER BY).
# Volumen_mm3 unterscheidet sich von den COUNT-basierten Alias-Zaehlern (bilder/
# aliase/analysen liefern 0 fuer leere Bezuege) und von der Wert-Aggregation
# (gesamtwert_chf liefert 0.0 via COALESCE): das Produkt Laenge_mm * Breite_mm *
# Hoehe_mm gibt NULL zurueck, sobald eine der drei Achsen NULL ist - das ist
# semantisch korrekt (ohne komplette Vermessung ist kein Volumen definiert) und
# spiegelt die NULL-an-Ende-Konvention der Einzel-Dimensions-Sortierung.
# Mohs_Haerte_Mitte teilt die NULL-Semantik der Dimensions-/Volumen-Achse:
# nur bei komplett fehlender Mohs-Pflege (min UND max NULL) liefert der Ausdruck
# NULL und faellt ans Listenende; Single-Point-Pflege ("7" ohne max) wird via
# COALESCE zum beidseitigen Grenzwert und liefert den einzelnen Wert.
# Dichte_Mitte spiegelt die COALESCE-/NULL-Konvention exakt auf die Massendichte-
# Achse: strukturidentisch zur Mohs-Mitte, damit die Kollektions-Aggregation aus
# stats.py (dichte_kollektion_durchschnitt/median/sigma) und die Listen-Sortier-
# Achse auf demselben Objekt-Ausdruck ruhen (kein Drift zwischen Statistik-
# Definition und Sortier-Definition).
_COMPUTED_COLUMNS: frozenset[str] = frozenset(
    {"bilder", "gesamtwert_chf", "aliase", "analysen", "Volumen_mm3",
     "Mohs_Haerte_Mitte", "Dichte_Mitte", "Wert_pro_Gewicht_chf_g",
     "Wert_pro_Volumen_chf_mm3"})


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fts_query(text: str) -> str:
    tokens = [t.replace('"', "") for t in text.split() if t.strip()]
    return " ".join(f'"{t}"*' for t in tokens)


def _like_escape(text: str) -> str:
    """Escapt SQL-LIKE-Metazeichen (``%``/``_``/``\\``) im Nutzereingabe-Pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _append_has_text_filter(where: list[str], value: bool | None, column: str) -> None:
    """Haengt einen tri-state Vollstaendigkeits-Filter auf eine TEXT-Spalte an ``where``.

    Konsolidiert die has_funddatum/has_mineral/has_notizen/has_pruefempfehlungen/
    has_strichfarbe/has_hcl_reaktion-Bloecke: Wahr = Feld dokumentiert
    (``IS NOT NULL AND TRIM != ''``), Falsch = leer/NULL/Whitespace. ``None``
    bleibt no-op (Filter wird nicht angefuegt). ``column`` ist callerseitig
    hardcodiert (Whitelist-Validierung implizit, keine SQL-Injection-Flaeche).
    """
    if value is True:
        where.append(f"o.{column} IS NOT NULL AND TRIM(o.{column}) != ''")
    elif value is False:
        where.append(f"(o.{column} IS NULL OR TRIM(o.{column}) = '')")


def _append_has_related_filter(where: list[str], value: bool | None,
                               table: str, fk_column: str,
                               extra_where: str = "") -> None:
    """tri-state Filter: existiert mind. ein verknuepfter Eintrag in ``table``?

    Konsolidiert die has_bilder/has_ki_analyse/has_alias/has_ki_analyse_uebernommen-
    Bloecke: alle folgen dem ``EXISTS (SELECT 1 FROM <table> r WHERE r.<fk> =
    o.obj_id [AND <extra>])``-Muster. ``table``/``fk_column``/``extra_where`` sind
    callerseitig hardcodiert (Whitelist-Validierung implizit, keine SQL-Injection-
    Flaeche - der Caller setzt nie Nutzereingaben hierher). ``extra_where``
    erlaubt zusaetzliche Bedingungen auf die verknuepfte Tabelle ("nur uebernommene
    Analysen", "nur Bilder einer bestimmten Kategorie"); ``None``-Wert bleibt
    no-op, ``True`` ergibt EXISTS, ``False`` ergibt NOT EXISTS.
    """
    if value is None:
        return
    extra = f" AND {extra_where}" if extra_where else ""
    inner = (f"SELECT 1 FROM {table} r WHERE r.{fk_column} = o.obj_id{extra}")
    keyword = "EXISTS" if value else "NOT EXISTS"
    where.append(f"{keyword} ({inner})")


def _append_scale_1_10_filter(where: list[str], params: list,
                              name: str, column: str,
                              val_min: int | None, val_max: int | None) -> None:
    """Haengt einen ``>=/<=``-Range-Filter auf eine 1..10-Skala an where/params.

    Spiegelt die drei Filterpaare ``seltenheit_global_min/max``,
    ``seltenheit_fundort_min/max`` und ``nachfrage_min/max``. Out-of-range-Werte
    (0/11) erzeugen einen klaren ``ValueError`` mit ``name`` als Diagnose
    (statt einer stillen Leerausgabe). NULL-Eintraege (nicht bewertet)
    fallen automatisch raus, weil ``NULL >=/<= ?`` immer NULL/False ergibt.
    """
    for bound, op in ((val_min, ">="), (val_max, "<=")):
        if bound is None:
            continue
        b = int(bound)
        if not 1 <= b <= 10:
            raise ValueError(f"{name} muss in 1..10 liegen (war: {b})")
        where.append(f"o.{column} {op} ?")
        params.append(b)


def _append_enum_in_filter(where: list[str], params: list,
                           value: list[str] | tuple[str, ...] | None,
                           column: str, label: str,
                           valid_values: frozenset[str]) -> None:
    """Haengt einen ``IN``-Mengenfilter auf eine Enum-Spalte an where/params.

    Konsolidiert die status_in/kategorie_in/kristallsystem_in/beste_verwendung_in/
    glanz_in/transparenz_in/magnetismus_in/spaltbarkeit_in/bruch_in-Bloecke: alle
    neun folgten dem gleichen 13-Zeilen-Muster (leere Eintraege filtern, gegen
    VALID_*-Frozenset validieren, ``IN (?,?,?)``-Klausel anhaengen). ``label``
    ist die Diagnose-Bezeichnung in der ValueError-Meldung (z.B. "Status",
    "Kristallsystem"), ``column`` ist callerseitig hardcodiert (Whitelist-
    Validierung implizit, keine SQL-Injection-Flaeche). Leere Werte sowie
    reine Whitespace-/Falsy-Listen bleiben no-op (Filter wird nicht angefuegt).
    """
    if not value:
        return
    items = [v for v in value if v]
    invalid = [v for v in items if v not in valid_values]
    if invalid:
        raise ValueError(
            f"Unbekannte {label}-Werte: {invalid} "
            f"(erwartet aus {sorted(valid_values)})")
    if items:
        placeholders = ", ".join("?" * len(items))
        where.append(f"o.{column} IN ({placeholders})")
        params.extend(items)


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
                     bilder_min: int | None = None,
                     bilder_max: int | None = None,
                     has_image_kategorie: str = "",
                     missing_image_kategorie: str = "",
                     min_confidence: int | None = None,
                     max_confidence: int | None = None,
                     has_confidence: bool | None = None,
                     has_funddatum: bool | None = None,
                     has_kategorie: bool | None = None,
                     has_mineral: bool | None = None,
                     has_varietaet: bool | None = None,
                     has_gesteinsart: bool | None = None,
                     has_notizen: bool | None = None,
                     has_pruefempfehlungen: bool | None = None,
                     has_gewicht: bool | None = None,
                     has_wert: bool | None = None,
                     has_uv_reaktion: bool | None = None,
                     has_strichfarbe: bool | None = None,
                     has_hcl_reaktion: bool | None = None,
                     has_reaktionshinweis: bool | None = None,
                     has_farbe: bool | None = None,
                     has_kristallsystem: bool | None = None,
                     has_glanz: bool | None = None,
                     has_transparenz: bool | None = None,
                     has_beste_verwendung: bool | None = None,
                     has_bruch: bool | None = None,
                     has_spaltbarkeit: bool | None = None,
                     has_magnetismus: bool | None = None,
                     has_fundort: bool | None = None,
                     has_mohs: bool | None = None,
                     has_dichte: bool | None = None,
                     has_dimensionen: bool | None = None,
                     has_ki_analyse: bool | None = None,
                     analysen_min: int | None = None,
                     analysen_max: int | None = None,
                     has_ki_analyse_uebernommen: bool | None = None,
                     has_alias: bool | None = None,
                     aliase_min: int | None = None,
                     aliase_max: int | None = None,
                     funddatum_jahr_min: int | None = None,
                     funddatum_jahr_max: int | None = None,
                     funddatum_jahr_in: list[int] | tuple[int, ...] | None = None,
                     funddatum_jahrzehnt_in: list[int] | tuple[int, ...] | None = None,
                     funddatum_monat: int | None = None,
                     funddatum_monat_in: list[int] | tuple[int, ...] | None = None,
                     funddatum_min: str | None = None,
                     funddatum_max: str | None = None,
                     erstellt_am_jahr_min: int | None = None,
                     erstellt_am_jahr_max: int | None = None,
                     erstellt_am_jahr_in: list[int] | tuple[int, ...] | None = None,
                     erstellt_am_jahrzehnt_in: list[int] | tuple[int, ...] | None = None,
                     erstellt_am_monat: int | None = None,
                     erstellt_am_monat_in: list[int] | tuple[int, ...] | None = None,
                     erstellt_am_min: str | None = None,
                     erstellt_am_max: str | None = None,
                     geaendert_am_jahr_min: int | None = None,
                     geaendert_am_jahr_max: int | None = None,
                     geaendert_am_jahr_in: list[int] | tuple[int, ...] | None = None,
                     geaendert_am_jahrzehnt_in: list[int] | tuple[int, ...] | None = None,
                     geaendert_am_monat: int | None = None,
                     geaendert_am_monat_in: list[int] | tuple[int, ...] | None = None,
                     geaendert_am_min: str | None = None,
                     geaendert_am_max: str | None = None,
                     fundort: str = "",
                     fundort_in: list[str] | tuple[str, ...] | None = None,
                     fundort_contains: str = "",
                     mineral_contains: str = "",
                     name_contains: str = "",
                     notizen_contains: str = "",
                     wert_min: float | None = None,
                     wert_max: float | None = None,
                     wert_pro_gewicht_min: float | None = None,
                     wert_pro_gewicht_max: float | None = None,
                     wert_pro_volumen_min: float | None = None,
                     wert_pro_volumen_max: float | None = None,
                     gewicht_min: float | None = None,
                     gewicht_max: float | None = None,
                     laenge_min: float | None = None,
                     laenge_max: float | None = None,
                     breite_min: float | None = None,
                     breite_max: float | None = None,
                     hoehe_min: float | None = None,
                     hoehe_max: float | None = None,
                     volumen_min: float | None = None,
                     volumen_max: float | None = None,
                     mohs_min: float | None = None,
                     mohs_max: float | None = None,
                     dichte_min: float | None = None,
                     dichte_max: float | None = None,
                     seltenheit_global_min: int | None = None,
                     seltenheit_global_max: int | None = None,
                     seltenheit_fundort_min: int | None = None,
                     seltenheit_fundort_max: int | None = None,
                     nachfrage_min: int | None = None,
                     nachfrage_max: int | None = None,
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
                   (SELECT COUNT(*) FROM aliases a WHERE a.canonical_id = o.obj_id) AS aliase,
                   (SELECT COUNT(*) FROM ki_analysen k WHERE k.obj_id = o.obj_id) AS analysen,
                   {wert_sql} AS gesamtwert_chf,
                   (o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) AS Volumen_mm3,
                   ((COALESCE(o.Mohs_Haerte_min, o.Mohs_Haerte_max)
                    + COALESCE(o.Mohs_Haerte_max, o.Mohs_Haerte_min))
                    / 2.0) AS Mohs_Haerte_Mitte,
                   ((COALESCE(o.Dichte_min_gcm3, o.Dichte_max_gcm3)
                    + COALESCE(o.Dichte_max_gcm3, o.Dichte_min_gcm3))
                    / 2.0) AS Dichte_Mitte,
                   (CASE WHEN o.Gewicht_g IS NULL OR o.Gewicht_g = 0 THEN NULL
                         ELSE {wert_sql} * 1.0 / o.Gewicht_g END)
                    AS Wert_pro_Gewicht_chf_g,
                   (CASE WHEN o.Laenge_mm IS NULL OR o.Breite_mm IS NULL
                              OR o.Hoehe_mm IS NULL
                              OR (o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) = 0
                         THEN NULL
                         ELSE {wert_sql} * 1.0
                              / (o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) END)
                    AS Wert_pro_Volumen_chf_mm3
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
        _append_enum_in_filter(where, params, status_in, "status", "Status",
                               VALID_STATUSES)
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
        _append_enum_in_filter(where, params, kategorie_in, "Kategorie",
                               "Kategorie", VALID_KATEGORIEN)
        # has_bilder ist die kanonische Form (True/False/None); only_images bleibt
        # als Legacy-Alias erhalten und mappt auf has_bilder=True, falls dieses
        # noch nicht gesetzt ist (kein Konflikt zwischen den beiden Flags).
        effective_has_bilder = has_bilder if has_bilder is not None else (
            True if only_images else None)
        _append_has_related_filter(where, effective_has_bilder, "images", "obj_id")
        # bilder_min/bilder_max: Zaehl-basierter Bereichsfilter ueber die Foto-Anzahl
        # pro Objekt. Verfeinert has_bilder (tri-state 0 vs. >0) auf konkrete
        # Grenzen ("mindestens 3 Fotos" fuer Vitrinen-Reife oder Auktions-Beleg,
        # "hoechstens 1 Foto" fuer Foto-Pflege-Restanten). Spiegelt gewicht_min/max
        # und laenge_min/max auf die berechnete Spalte ``bilder``: derselbe
        # (SELECT COUNT(*)...)-Subquery wie in der SELECT-Liste, damit der Filter
        # exakt mit der spaeteren Sortier-Spalte uebereinstimmt (Sortier-nach-
        # ``bilder`` + Filter ``bilder_min=2`` selektieren dieselbe Zahlen-Domain).
        # Negative Werte werfen ValueError (Foto-Anzahl kann nicht negativ sein);
        # bilder_min=0 ist no-op semantisch, wird aber trotzdem ausgefuehrt, um
        # NULL-Verhalten transparent zu halten (COUNT(*) liefert nie NULL).
        # Kombinierbar mit has_bilder (bilder_min=1 == has_bilder=True als
        # redundantes Aequivalent; bilder_max=0 == has_bilder=False).
        if bilder_min is not None:
            b = int(bilder_min)
            if b < 0:
                raise ValueError(f"bilder_min muss >= 0 sein (war: {b})")
            where.append(
                "(SELECT COUNT(*) FROM images i WHERE i.obj_id = o.obj_id) >= ?")
            params.append(b)
        if bilder_max is not None:
            b = int(bilder_max)
            if b < 0:
                raise ValueError(f"bilder_max muss >= 0 sein (war: {b})")
            where.append(
                "(SELECT COUNT(*) FROM images i WHERE i.obj_id = o.obj_id) <= ?")
            params.append(b)
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
        _append_has_text_filter(where, has_funddatum, "Funddatum")
        # has_kategorie: tri-state Filter fuer dokumentierte Objekt-Kategorie.
        # Kategorie (Mineral-Korn/Handstueck/Duennschliff/Kristall/Geroell/Sonstiges)
        # ist die erste Identifikations-/Inventar-Achse - sie sagt, was das Stueck
        # physisch ueberhaupt ist, bevor mineralogische Bestimmung (Mineral_Primaer)
        # oder geografische Provenienz (Fundort) ueberhaupt sinnvoll werden.
        # Spiegelt has_mineral/has_kristallsystem/has_glanz auf die ID-Gruppen-Achse
        # und ergaenzt den kategorie_in-Mengenfilter ("Handstueck ODER Kristall"):
        # has_kategorie selektiert die Anwesenheits-Dimension (irgendeine Kategorie
        # vs. keine), kategorie_in selektiert die konkrete Kategorien-Auswahl.
        # Findet unkategorisierte Stuecke (typisch fuer frisch importierte Bestaende
        # ohne Inventar-Vorklassifizierung oder Migrations-Restbestaende, wo
        # Kategorie weder im v1/obj043-Loader noch im v2-Schema gesetzt war) -
        # zentrale Pflege-Achse, weil die Kategorie das Foto-Setup vorgibt
        # (Duennschliff: Mikroskop-Aufnahme, Handstueck: Uebersichts-Foto,
        # Mineral-Korn: Makro/Mikroskop, Kristall: Lichttisch fuer durchsichtige).
        # Whitespace zaehlt wie leer (spiegelt _append_has_text_filter-Konvention,
        # kompatibel zur Enum-Liste mit Leerstring als "noch nicht kategorisiert"-Wert).
        _append_has_text_filter(where, has_kategorie, "Kategorie")
        _append_has_text_filter(where, has_mineral, "Mineral_Primaer")
        # has_varietaet: tri-state Filter fuer dokumentierte Varietaet.
        # Die Varietaet ist die feinere Sub-Klassifizierung unter dem Hauptmineral
        # (Quarz → Bergkristall/Milchquarz/Rauchquarz/Amethyst/Citrin); ohne sie
        # bleibt der Eintrag auf der Familien-Ebene stehen. Spiegelt has_mineral
        # (Hauptmineral-Vollstaendigkeit) und ergaenzt den varietaet_in-Mengen-
        # filter (der NULL/Leereintraege ohnehin uebergeht). Findet Stuecke, an
        # denen die mineralogische Sub-Bestimmung nachzuholen ist (typisch nach
        # KI-Vorbestimmung auf Familien-Ebene, vor manueller Varietaet-Pruefung).
        _append_has_text_filter(where, has_varietaet, "Varietaet")
        # has_gesteinsart: tri-state Filter fuer dokumentierte Gesteinsart.
        # Die Gesteinsart (Granit/Gneis/Basalt/Sandstein/...) ist die petrologische
        # Klassifizierung und damit die dritte Mineralogie-Achse neben Mineral_Primaer
        # (mineralogische Familie) und Varietaet (Sub-Klassifizierung). Spiegelt
        # has_mineral/has_varietaet und ergaenzt den gesteinsart_in-Mengenfilter
        # (der NULL/Leereintraege ohnehin uebergeht). Findet Stuecke ohne
        # petrologischen Kontext - typisch fuer Einzelmineral-Funde aus Klueften,
        # wo der Wirtsgesteins-Bezug nachgereicht werden muss.
        _append_has_text_filter(where, has_gesteinsart, "Gesteinsart")
        _append_has_text_filter(where, has_notizen, "notizen")
        _append_has_text_filter(where, has_pruefempfehlungen, "Pruefempfehlungen")
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
        # has_uv_reaktion: tri-state Filter fuer dokumentierte UV-Fluoreszenz.
        # Wahr, sobald eines der beiden UV-Felder (UV_365nm langwellig oder
        # UV_254nm kurzwellig) ueberhaupt einen Eintrag hat - der Inhalt selbst
        # ("blau", "schwach gruen", "keine") bleibt Freitext und wird nicht
        # interpretiert (Daten-Vollstaendigkeit, nicht Reaktiv-vs-inert). Spiegelt
        # die has_funddatum/has_notizen-Logik. Ergaenzt UV-Foto-Auswahl per
        # has_image_kategorie='UV365'/'UV395': UV-Bilder ohne dokumentierte
        # Reaktion sind ein Hinweis auf nachzutragende Beobachtung.
        if has_uv_reaktion is True:
            where.append("((o.UV_365nm IS NOT NULL AND TRIM(o.UV_365nm) != '') "
                         "OR (o.UV_254nm IS NOT NULL AND TRIM(o.UV_254nm) != ''))")
        elif has_uv_reaktion is False:
            where.append("(o.UV_365nm IS NULL OR TRIM(o.UV_365nm) = '') "
                         "AND (o.UV_254nm IS NULL OR TRIM(o.UV_254nm) = '')")
        # has_strichfarbe: tri-state Filter fuer dokumentierten Strichtest.
        # Der Strich auf der Porzellantafel ist die klassische Diagnose-Probe
        # fuer metallische Minerale (Haematit: rot, Magnetit: schwarz, Pyrit:
        # gruenlich-schwarz) und entscheidet oft eine zweideutige Identifikation.
        # Findet Stuecke, an denen der Strichtest nachzuholen ist - typische
        # Vorbereitung vor KI-Analyse, weil die Strichfarbe Mineral-Vorschlaege
        # wirksam disambiguiert.
        _append_has_text_filter(where, has_strichfarbe, "Strichfarbe")
        # has_hcl_reaktion: tri-state Filter fuer dokumentierten Salzsaeure-Test.
        # HCl identifiziert Karbonate eindeutig (Calcit/Aragonit: starke Reaktion
        # kalt; Dolomit: schwach kalt, stark warm; Magnesit: nur warm).
        # Komplementaer zu has_strichfarbe (metallische Diagnostik) - HCl deckt
        # den Karbonat-Strang ab.
        _append_has_text_filter(where, has_hcl_reaktion, "HCl_Reaktion")
        # has_reaktionshinweis: tri-state Filter fuer dokumentierten Reaktions-Kommentar.
        # Reaktionshinweis ist die erklaerende Begleit-Notiz zu UV/HCl/Magnet-
        # Beobachtungen ("Reaktion warm verstaerkt", "nur Risskanten fluoreszieren",
        # "Pulver schwach blasenbildend"). Oft fehlt sie, obwohl die Trigger-
        # Beobachtung selbst (HCl_Reaktion/UV_365nm/...) gepflegt ist - der Filter
        # macht diese asymmetrische Pflege sichtbar, komplementaer zu
        # has_hcl_reaktion/has_uv_reaktion (Trigger ohne Erklaerung).
        _append_has_text_filter(where, has_reaktionshinweis, "Reaktionshinweis")
        # has_farbe: tri-state Filter fuer dokumentierte Farbe (Farbe_beobachtet).
        # Die beobachtete Farbe ist der erste Eindruck eines Stuecks und das
        # primaere Freitext-Beschreibungsfeld - ohne Farbnotiz fehlt selbst die
        # grobste Vor-Identifikation. Komplementaer zu has_strichfarbe (Pulver
        # auf Porzellan, oft anders als die Stueck-Farbe: Haematit silbrig-
        # metallisch, Strich aber rot). Findet unbeschriftete Stuecke, an denen
        # die Bestandsaufnahme nachzuholen ist.
        _append_has_text_filter(where, has_farbe, "Farbe_beobachtet")
        # has_kristallsystem: tri-state Filter fuer dokumentierten Symmetrietyp.
        # Das Kristallsystem (kubisch/tetragonal/hexagonal/trigonal/orthorhombisch/
        # monoklin/triklin/amorph) ist die kristallographische Hauptachse - oft
        # erst nach Mikroskop-/Diffraktometer-Analyse setzbar, daher in Sammlungs-
        # bestaenden haeufig leer. Komplementaer zum kristallsystem_in-Mengen-
        # filter, der konkrete Symmetrien selektiert; hier nur die Anwesenheit.
        _append_has_text_filter(where, has_kristallsystem, "Kristallsystem")
        # has_glanz: tri-state Filter fuer dokumentierten Glanz.
        # Glanz (glasig/wachsig/matt/metallisch/fettig/seidig/perlmutt) ist die
        # optische Oberflaechen-Reflexions-Achse - zentrales Diagnose- und
        # Foto-Setup-Kriterium: glasige Quarz-/Calcit-Stuecke brauchen
        # diffuse Beleuchtung gegen Spiegelung, metallische Galenit-/Pyrit-
        # Stuecke profitieren von Streiflicht zur Akzentuierung der Reflexe,
        # matte/erdige Stuecke vertragen direktes Licht. Komplementaer zu
        # has_transparenz (Lichtdurchlaessigkeit) auf die optische Diagnose-
        # Achse; ergaenzt glanz_in (konkrete Klassen-Auswahl), by_glanz (Verteilung)
        # und wert_pro_glanz (Wertbeitrag) sowie die Glanz-Sortier-Spalte
        # (gleiches Licht-Setup beisammen vor Foto-Sitzungen). Findet Stuecke
        # ohne dokumentierten Glanz fuer Foto-/Diagnose-Nachpflege - oft die
        # erste Felddatenpflege, weil der Glanz unmittelbar sichtbar ist und
        # keinen separaten Test (Hammer/Saeure/Magnet) erfordert.
        _append_has_text_filter(where, has_glanz, "Glanz")
        # has_transparenz: tri-state Filter fuer dokumentierte Transparenz.
        # Transparenz (durchsichtig/durchscheinend/opak) ist die Lichtdurchlaessigkeits-
        # Achse - komplementaer zu has_glanz (Oberflaechen-Reflexion) auf die
        # optische Diagnose-Doppel-Achse: Glanz beschreibt, wie Licht reflektiert
        # wird (Oberflaechen-Wirkung), Transparenz, wie Licht durchgelassen wird
        # (Volumen-Wirkung). Beide zusammen liefern die optische Vorsortierung
        # vor jeder Foto-Sitzung - durchsichtige/durchscheinende Stuecke brauchen
        # Hintergrund-Beleuchtung (Lichttisch/Backlight), opake Stuecke direkte
        # Front-Beleuchtung. Spiegelt has_glanz auf die orthogonale optische
        # Achse; ergaenzt transparenz_in (konkrete Klassen-Auswahl), by_transparenz
        # (Verteilung) und wert_pro_transparenz (Wertbeitrag) sowie die
        # Transparenz-Sortier-Spalte (gleiches Licht-Setup beisammen). Findet
        # Stuecke ohne dokumentierte Transparenz fuer Foto-/Diagnose-Nachpflege -
        # in der Praxis oft mit has_glanz zusammen gepflegt (beide Diagnose-
        # Eintragspunkte am visuell sichtbaren Stueck, kein Test noetig).
        _append_has_text_filter(where, has_transparenz, "Transparenz")
        # has_beste_verwendung: tri-state Filter fuer dokumentierte Verwendungs-
        # Empfehlung. Beste_Verwendung (Schmuck/Sammlung/Forschung/Industrie/
        # Talisman/Dekoration) ist die Markt-/Anwendungs-Positionierungs-Achse -
        # die Empfehlung, was das Stueck letztlich werden soll: Polierter Schmuck-
        # Cabochon? Vitrinen-Stueck fuer die wissenschaftliche Sammlung? Roh-
        # material fuer Talisman-Schnitzerei? In der Praxis erst nach mineralogischer
        # Bestimmung und Wert-/Seltenheits-Einschaetzung gesetzt - daher in
        # Sammlungsbestaenden mit Pflege-Rueckstaenden oft die letzte Felddaten-
        # achse, die ausgefuellt wird. Komplementaer zum beste_verwendung_in-
        # Mengenfilter (konkrete Auswahl: nur "Schmuck" und "Sammlung"); findet
        # Stuecke ohne Verwendungs-Empfehlung fuer den Workflow "was tun mit
        # diesem Stueck?" - typisch nach Massen-Migration oder Erbschafts-Import,
        # wo die Positionierung der einzelnen Stuecke nach Bestimmung noch
        # nachgereicht werden muss. Ergaenzt by_beste_verwendung (Verteilung),
        # wert_pro_beste_verwendung (Wertbeitrag) und die Beste_Verwendung-
        # Sortier-Spalte (gleiche Verwendungs-Klasse beisammen vor Sitzungen).
        _append_has_text_filter(where, has_beste_verwendung, "Beste_Verwendung")
        # has_bruch: tri-state Filter fuer dokumentiertes Bruchverhalten.
        # Bruch (muschelig/uneben/splittrig/faserig/erdig/glatt) ist die
        # Bruchflaechen-Achse - komplementaer zu has_spaltbarkeit (Spaltflaechen
        # vorhanden), das die andere Hand-Vorsichts-Achse abdeckt: ein Quarz hat
        # keine Spaltbarkeit (keine), aber muscheligen Bruch (scharfe Kanten),
        # waehrend Calcit beides hat. Findet Stuecke, an denen der Bruch-Test
        # (Hammer/Schlag-Beobachtung) nachzuholen ist - zentrale Verletzungs-
        # risiko-Diagnose vor Polier-/Schneid-Sitzungen. Komplementaer zum
        # bruch_in-Mengenfilter (konkrete Klassen) und zur Bruch-Sortier-Spalte.
        _append_has_text_filter(where, has_bruch, "Bruch")
        # has_spaltbarkeit: tri-state Filter fuer dokumentierte Spaltbarkeit.
        # Spaltbarkeit (vollkommen/gut/deutlich/undeutlich/keine) ist die
        # Spaltflaechen-Achse - komplementaer zu has_bruch (Bruchflaechen):
        # Calcit/Fluorit/Glimmer haben vollkommen-/gute Spaltbarkeit und kommen
        # bei Schlag entlang glatter Flaechen auseinander, waehrend Quarz/
        # Obsidian "keine" Spaltbarkeit, dafuer muscheligen Bruch (scharfe
        # Kanten) zeigen - in der Praxis werden beide Tests oft zusammen
        # durchgefuehrt (Hammer-Schlag plus Beobachtung der Bruchstuecke).
        # Findet Stuecke, an denen der Spaltbarkeits-Test nachzuholen ist -
        # Werkzeug-Setup-Achse vor Praeparier-/Polier-Sitzungen. Komplementaer
        # zum spaltbarkeit_in-Mengenfilter und zur Spaltbarkeit-Sortier-Spalte.
        _append_has_text_filter(where, has_spaltbarkeit, "Spaltbarkeit")
        # has_magnetismus: tri-state Filter fuer dokumentierte Magnet-Reaktion.
        # Magnetismus (ja/schwach/nein) ist die Eisen-Diagnose-Achse - der Test
        # am Neodym-Magneten ist schnell und zerstoerungsfrei, wird aber oft
        # vergessen oder bei offensichtlich nicht-magnetischen Stuecken (Quarz/
        # Calcit) ueberhaupt nicht eingetragen. Findet Stuecke ohne Magnet-Test
        # fuer diagnostische Nachpflege - besonders relevant bei dunklen/
        # metallisch-glaenzenden Stuecken (Magnetit vs. Haematit vs. Ilmenit
        # unterscheidet sich vor allem in der Magnet-Reaktion). Komplementaer
        # zu has_bruch/has_spaltbarkeit (physikalische Diagnose) und zu
        # has_uv_reaktion/has_hcl_reaktion (chemische Diagnose); spiegelt
        # magnetismus_in (konkrete Reaktions-Klassen) und die Magnetismus-
        # Sortier-Spalte (Magnet-Sitzungs-Vorbereitung).
        _append_has_text_filter(where, has_magnetismus, "Magnetismus")
        # has_fundort: tri-state Filter fuer dokumentierten Fundort.
        # Der Fundort ist die Standort-Achse der Sammlung (Berg/Steinbruch/Boerse)
        # und Voraussetzung fuer alle ortsbezogenen Auswertungen (by_fundort,
        # wert_pro_fundort, fundort_in-Mengenfilter). Geerbte Stuecke ohne
        # Standort-Notiz sind ein typischer Pflege-Rueckstand - der Filter
        # macht die Luecke direkt sichtbar, komplementaer zum fundort_contains-
        # Substring-Filter (der NULL/Leereintraege ohnehin uebergeht).
        _append_has_text_filter(where, has_fundort, "Fundort")
        # has_mohs: tri-state Filter fuer dokumentierte Mohs-Haerte.
        # Wahr, sobald eines der beiden Bereichsfelder (Mohs_Haerte_min/_max)
        # gesetzt ist - die obere und untere Grenze des Haertebereichs werden
        # nicht immer zusammen gepflegt (oft nur ``5-6`` als min, max wird leer
        # gelassen). Spiegelt has_uv_reaktion (zwei Felder, eines reicht); haerte-
        # spezifischer als der mohs_min/max-Bereichsfilter, der konkrete Schwellen
        # vorgibt, aber NULL-Eintraege ueberspringt. Findet Stuecke, an denen der
        # Haertetest nachzuholen ist - zentrale Diagnose-Achse vor KI-Analyse.
        if has_mohs is True:
            where.append("(o.Mohs_Haerte_min IS NOT NULL OR o.Mohs_Haerte_max IS NOT NULL)")
        elif has_mohs is False:
            where.append("(o.Mohs_Haerte_min IS NULL AND o.Mohs_Haerte_max IS NULL)")
        # has_dichte: tri-state Filter fuer dokumentierte Dichte (eines der beiden
        # Bereichsfelder reicht). Spiegelt has_mohs exakt: Dichte und Mohs sind
        # die zwei zentralen physikalischen Diagnose-Achsen, die in der Praxis oft
        # gemeinsam gepflegt werden (gewogenes Stueck + Polier-Test). Findet
        # Stuecke, an denen die Dichte-Messung (per Auftriebs-/Pyknometer-Methode)
        # nachzuholen ist - z.B. um Quarz (2.65) von Calcit (2.71) zu trennen,
        # wenn die Farbe mehrdeutig ist.
        if has_dichte is True:
            where.append("(o.Dichte_min_gcm3 IS NOT NULL OR o.Dichte_max_gcm3 IS NOT NULL)")
        elif has_dichte is False:
            where.append("(o.Dichte_min_gcm3 IS NULL AND o.Dichte_max_gcm3 IS NULL)")
        # has_dimensionen: tri-state Filter fuer dokumentierte geometrische Masse.
        # Wahr, sobald mindestens eine der drei Achsen (Laenge/Breite/Hoehe in mm)
        # gemessen ist - in der Praxis wird oft nur die laengste Achse erfasst
        # und die anderen nachgereicht (oder umgekehrt). Findet unvermessene
        # Stuecke fuer die Vitrinen-/Schubladen-Auswahl (Pendant zum laenge_/
        # breite_/hoehe_min/max-Bereichsfilter, der NULL-Eintraege ueberspringt).
        # Komplementaer zu has_gewicht (Masse), das die andere physische
        # Bestands-Kennzahl abdeckt.
        if has_dimensionen is True:
            where.append("(o.Laenge_mm IS NOT NULL OR o.Breite_mm IS NOT NULL "
                         "OR o.Hoehe_mm IS NOT NULL)")
        elif has_dimensionen is False:
            where.append("(o.Laenge_mm IS NULL AND o.Breite_mm IS NULL "
                         "AND o.Hoehe_mm IS NULL)")
        # has_ki_analyse: tri-state Filter fuer Objekte mit/ohne KI-Analyse-Eintrag.
        # Spiegelt das objekte_mit_ki_analyse-Aggregat in der Statistik (EXISTS
        # in ki_analysen). Findet Bestaende, an denen die KI-Analyse nachzuholen
        # ist (False) bzw. die bereits durchgelaufen sind (True) - typische
        # Workflow-Achse vor Sammel-Batches. Komplementaer zu has_confidence
        # (gesetzter Confidence-Wert): Confidence kann manuell vergeben sein,
        # ohne dass je eine KI-Analyse abgespeichert wurde. ki_analysen.obj_id
        # ist FK auf objects.obj_id mit ON DELETE CASCADE - geloeschte Objekte
        # haben automatisch keine verwaisten Analyse-Eintraege.
        _append_has_related_filter(where, has_ki_analyse, "ki_analysen", "obj_id")
        # analysen_min/analysen_max: Zaehl-basierter Bereichsfilter ueber die KI-
        # Analyse-Anzahl pro Objekt. Verfeinert has_ki_analyse (tri-state 0 vs. >0)
        # auf konkrete Grenzen ("mindestens 3 Laeufe" fuer intensiv analysierte
        # mineralogisch unsichere Faelle, "hoechstens 1 Lauf" fuer flache KI-Historie).
        # Spiegelt bilder_min/max auf die berechnete Spalte ``analysen``: derselbe
        # (SELECT COUNT(*) FROM ki_analysen...)-Subquery wie in der SELECT-Liste,
        # damit der Filter exakt mit der Sortier-Spalte uebereinstimmt (Sortier-
        # nach-``analysen`` + Filter ``analysen_min=2`` selektieren dieselbe
        # Zahlen-Domain, kein Drift zwischen Filter- und Sortier-Definition).
        # Sammler-Frage: "welche Stuecke haben die tiefste KI-Analyse-Historie
        # (>=3 Laeufe, typisch fuer mineralogisch unsichere Faelle mit mehreren
        # Re-Analysen unter Tilt/UV/Mikroskop)?" -> analysen_min=3; "welche haben
        # noch keinen Re-Lauf (max. 1 Analyse) und koennten mit besserer Foto-Lage
        # profitieren?" -> analysen_max=1. Negative Werte werfen ValueError (KI-
        # Analyse-Anzahl kann nicht negativ sein); analysen_min=0 ist no-op
        # semantisch (COUNT(*) liefert nie NULL, alle Objekte passen die Bedingung),
        # analysen_max=0 == has_ki_analyse=False, analysen_min=1 == has_ki_analyse=
        # True. Kombinierbar mit has_ki_analyse als redundante Schnittmenge und
        # mit has_ki_analyse_uebernommen zur Diagnose "3 Laeufe, keiner
        # uebernommen" (Verwerfungs-Kandidaten fuer Re-Analyse mit neuer Foto-Lage).
        if analysen_min is not None:
            a = int(analysen_min)
            if a < 0:
                raise ValueError(f"analysen_min muss >= 0 sein (war: {a})")
            where.append(
                "(SELECT COUNT(*) FROM ki_analysen k WHERE k.obj_id = o.obj_id) >= ?")
            params.append(a)
        if analysen_max is not None:
            a = int(analysen_max)
            if a < 0:
                raise ValueError(f"analysen_max muss >= 0 sein (war: {a})")
            where.append(
                "(SELECT COUNT(*) FROM ki_analysen k WHERE k.obj_id = o.obj_id) <= ?")
            params.append(a)
        # has_ki_analyse_uebernommen: tri-state Filter fuer Objekte mit mindestens
        # einer uebernommenen KI-Analyse. Feinere Granularitaet als has_ki_analyse:
        # ein KI-Lauf erzeugt zunaechst nur einen Antwort-Eintrag (antwort_json);
        # erst wenn der User Vorschlaege auf Objektfelder uebernimmt, wird
        # uebernommen_json gesetzt. has_ki_analyse_uebernommen=True ist also "die
        # KI hat geliefert UND der User hat zugegriffen", komplementaer zu
        # has_ki_analyse=True (Lauf gemacht) und has_confidence=True (Sicherheit
        # gesetzt). Kombination has_ki_analyse=True + has_ki_analyse_uebernommen=
        # False findet KI-Laeufe, die verworfen wurden (Vorschlaege passten nicht,
        # Objekt blieb wie es war) - typische Pflege-Frage vor Re-Analyse-Batch.
        # Spiegelt die ki_analysen_uebernommen-Statistik (zaehlt Eintraege mit
        # gesetztem uebernommen_json) auf den Listen-Filter.
        _append_has_related_filter(
            where, has_ki_analyse_uebernommen, "ki_analysen", "obj_id",
            extra_where="r.uebernommen_json IS NOT NULL "
                        "AND TRIM(r.uebernommen_json) != ''")
        # has_alias: tri-state Filter fuer Objekte mit/ohne Alias-Eintrag.
        # Aliases speichern die alten Objekt-IDs nach einem Merge (~30 dokumen-
        # tierte Duplikat-Gruppen aus der Migration plus spaeter manuell ueber
        # merge_into_canonical zusammengefuehrte Stuecke). has_alias=True findet
        # alle Kanon-Objekte, in die mindestens ein Duplikat geflossen ist -
        # zentrale Schluesselrolle fuer Provenienz-Recherche ("welche alten
        # IDs sind im aktuellen OBJ_0007 versammelt?"). has_alias=False bleibt
        # die Mehrheit (nicht-gemergte Originale). Spiegelt has_ki_analyse auf
        # die parallele Existenz-Pruefung in einer verknuepften Tabelle
        # (aliases.canonical_id ist FK auf objects.obj_id mit ON DELETE CASCADE -
        # geloeschte Objekte hinterlassen keine verwaisten Alias-Eintraege).
        _append_has_related_filter(where, has_alias, "aliases", "canonical_id")
        # aliase_min/aliase_max: Zaehl-basierter Bereichsfilter ueber die Merge-
        # Tiefe pro Kanon-Objekt. Verfeinert has_alias (tri-state 0 vs. >0) auf
        # konkrete Merge-Anzahl-Grenzen. Spiegelt bilder_min/max und analysen_min/max
        # auf die berechnete Spalte ``aliase``: derselbe (SELECT COUNT(*) FROM
        # aliases...)-Subquery wie in der SELECT-Liste, damit der Filter exakt mit
        # der Sortier-Spalte uebereinstimmt (Sortier-nach-``aliase`` + Filter
        # ``aliase_min=2`` selektieren dieselbe Zahlen-Domain). Provenienz-Frage:
        # "welche Kanon-Objekte haben die tiefste Merge-Historie (>=3 alte IDs
        # zusammengefuehrt, typisch fuer die dokumentierten Duplikat-Gruppen mit
        # mehreren Foto-Serien unter verschiedenen Alt-IDs)?" -> aliase_min=3;
        # "welche haben genau einen Alias (Erst-Merge-Kandidaten fuer weitere
        # Duplikat-Suche mit besserer Foto-Vergleichs-Software)?" -> aliase_min=1
        # kombiniert mit aliase_max=1. Aus Datenpflege-Sicht auch relevant fuer
        # den Sammler-Report "wieviele historische IDs sind in dem aktuellen
        # Bestand versammelt?" pro Kanon-Objekt in einem einzigen Filter-Durchgang.
        # Negative Werte werfen ValueError (Alias-Anzahl kann nicht negativ sein,
        # spiegelt bilder_min/analysen_min-Konvention); aliase_min=0 ist no-op
        # semantisch (COUNT(*) liefert nie NULL, alle Objekte passen die Bedingung),
        # wird aber trotzdem als SQL-Klausel ausgefuehrt fuer uniformes NULL-Verhalten.
        # aliase_max=0 == has_alias=False (nur nicht-gemergte Originale), aliase_min=1
        # == has_alias=True (alle Kanon-Objekte mit mindestens einem Merge).
        # Kombinierbar mit has_alias als redundante Schnittmenge (kein Konflikt).
        if aliase_min is not None:
            a = int(aliase_min)
            if a < 0:
                raise ValueError(f"aliase_min muss >= 0 sein (war: {a})")
            where.append(
                "(SELECT COUNT(*) FROM aliases a WHERE a.canonical_id = o.obj_id) >= ?")
            params.append(a)
        if aliase_max is not None:
            a = int(aliase_max)
            if a < 0:
                raise ValueError(f"aliase_max muss >= 0 sein (war: {a})")
            where.append(
                "(SELECT COUNT(*) FROM aliases a WHERE a.canonical_id = o.obj_id) <= ?")
            params.append(a)
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
        # funddatum_jahrzehnt_in: diskrete Dekaden-Menge ("Funde aus den 1980er
        # ODER 2010er") - komplementaer zu funddatum_jahr_in (Einzeljahre) und
        # zum Bereichsfilter funddatum_jahr_min/_max. Spiegelt das
        # by_funddatum_jahrzehnt-Aggregat: gruppiert das Jahr per Integer-Div
        # durch 10 und vergleicht mit der angegebenen Dekaden-Startzahl
        # (``1980`` selektiert 1980..1989, nicht "1980er"-String). Validierung:
        # jeder Eintrag muss ein realistisches Dekaden-Start sein
        # (1800..2990, durch 10 teilbar); sonst ValueError mit klarer Diagnose.
        if funddatum_jahrzehnt_in:
            dekaden = [int(d) for d in funddatum_jahrzehnt_in]
            invalid = [d for d in dekaden
                       if not (1800 <= d <= 2990 and d % 10 == 0)]
            if invalid:
                raise ValueError(
                    f"Unbekannte Funddatum-Jahrzehnte: {invalid} "
                    f"(erwartet 1800..2990, durch 10 teilbar)")
            if dekaden:
                placeholders = ", ".join("?" * len(dekaden))
                where.append(
                    f"substr(o.Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    f"AND (CAST(substr(o.Funddatum, 1, 4) AS INTEGER) / 10) * 10 "
                    f"IN ({placeholders})")
                params.extend(dekaden)
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
        # funddatum_monat_in: Mengen-Saison-Filter ("Berg-Saison Juli ODER August"
        # oder "Boersen-Spitzen Februar/Dezember"). Komplementaer zum einzelnen
        # funddatum_monat-Filter; spiegelt funddatum_jahr_in / funddatum_jahrzehnt_in
        # in der diskreten Mengen-Notation. Erwartet jeden Eintrag in 1..12
        # (Tippfehler 0/13 erzeugen einen klaren Fehler).
        if funddatum_monat_in:
            monate = [int(m) for m in funddatum_monat_in]
            invalid = [m for m in monate if not 1 <= m <= 12]
            if invalid:
                raise ValueError(
                    f"Unbekannte Funddatum-Monate: {invalid} "
                    f"(erwartet 1..12)")
            if monate:
                placeholders = ", ".join("?" * len(monate))
                where.append(
                    "o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != '' "
                    "AND substr(o.Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    "AND substr(o.Funddatum, 6, 2) GLOB '[0-1][0-9]' "
                    f"AND CAST(substr(o.Funddatum, 6, 2) AS INTEGER) IN "
                    f"({placeholders})")
                params.extend(monate)
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
        # Erfassungs-Achse: filtert nach Jahr des ``erstellt_am``-Stempels (wann
        # in die DB aufgenommen). Spiegelt funddatum_jahr_min/_max (Fund-Achse)
        # und ergaenzt das by_erstellt_am_jahr-Aggregat in der Statistik um den
        # Listen-Drill-down ("welche Stuecke habe ich 2024 erfasst?"). Substring
        # 1..4 ist analog zu funddatum_jahr und zu _count_erstellt_am_jahr; nur
        # vierstellige Jahres-Praefixe matchen, damit kaputte Stempel
        # historischer Imports nicht das Ergebnis verzerren.
        if erstellt_am_jahr_min is not None or erstellt_am_jahr_max is not None:
            where.append("substr(o.erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
            if erstellt_am_jahr_min is not None:
                where.append("CAST(substr(o.erstellt_am, 1, 4) AS INTEGER) >= ?")
                params.append(int(erstellt_am_jahr_min))
            if erstellt_am_jahr_max is not None:
                where.append("CAST(substr(o.erstellt_am, 1, 4) AS INTEGER) <= ?")
                params.append(int(erstellt_am_jahr_max))
        # erstellt_am_jahr_in: diskrete Erfassungs-Jahres-Menge ("erfasst in
        # 2023 ODER 2024" - z.B. zwei Migrations-Wellen). Spiegelt
        # funddatum_jahr_in auf die Erfassungs-Achse; Validierung 1800..2999
        # identisch, damit Tippfehler einen klaren Fehler statt eines stillen
        # Leerergebnisses erzeugen.
        if erstellt_am_jahr_in:
            jahre = [int(j) for j in erstellt_am_jahr_in]
            invalid = [j for j in jahre if not 1800 <= j <= 2999]
            if invalid:
                raise ValueError(
                    f"Unbekannte Erstellt-am-Jahre: {invalid} "
                    f"(erwartet 1800..2999)")
            if jahre:
                placeholders = ", ".join("?" * len(jahre))
                where.append(
                    f"substr(o.erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    f"AND CAST(substr(o.erstellt_am, 1, 4) AS INTEGER) IN "
                    f"({placeholders})")
                params.extend(jahre)
        # erstellt_am_jahrzehnt_in: diskrete Erfassungs-Dekaden-Menge
        # ("2010er ODER 2020er" - z.B. handgepflegte 2010er-Phase vs. Excel-
        # Migrations-Welle 2020+). Spiegelt funddatum_jahrzehnt_in auf die
        # Erfassungs-Achse und ergaenzt das by_erstellt_am_jahrzehnt-Aggregat
        # um den Listen-Drill-down. Validierung identisch (1800..2990, durch
        # 10 teilbar), damit Tippfehler einen klaren Fehler statt eines
        # stillen Leerergebnisses erzeugen.
        if erstellt_am_jahrzehnt_in:
            dekaden = [int(d) for d in erstellt_am_jahrzehnt_in]
            invalid = [d for d in dekaden
                       if not (1800 <= d <= 2990 and d % 10 == 0)]
            if invalid:
                raise ValueError(
                    f"Unbekannte Erstellt-am-Jahrzehnte: {invalid} "
                    f"(erwartet 1800..2990, durch 10 teilbar)")
            if dekaden:
                placeholders = ", ".join("?" * len(dekaden))
                where.append(
                    f"substr(o.erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    f"AND (CAST(substr(o.erstellt_am, 1, 4) AS INTEGER) / 10) * 10 "
                    f"IN ({placeholders})")
                params.extend(dekaden)
        # erstellt_am_monat: Saison-Filter ueber alle Jahre auf der Erfassungs-
        # Achse ("alle im Januar erfassten Stuecke"). Spiegelt funddatum_monat
        # und ergaenzt das by_erstellt_am_monat-Aggregat in der Statistik um
        # den Listen-Drill-down (typische Indoor-Erfassungs-Spitzen Winter/
        # Boersen-Vorbereitung Januar-Maerz). Substring 6..7 ist analog zu
        # funddatum_monat und zu _count_erstellt_am_monat; nur vierstellige
        # Jahres-Praefixe und gueltige Monatsteile 01..12 matchen.
        if erstellt_am_monat is not None:
            m = int(erstellt_am_monat)
            if not 1 <= m <= 12:
                raise ValueError(
                    f"erstellt_am_monat muss zwischen 1 und 12 liegen (war: {m})")
            where.append(
                "o.erstellt_am IS NOT NULL AND TRIM(o.erstellt_am) != '' "
                "AND substr(o.erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                "AND substr(o.erstellt_am, 6, 2) GLOB '[0-1][0-9]' "
                "AND CAST(substr(o.erstellt_am, 6, 2) AS INTEGER) = ?")
            params.append(m)
        # erstellt_am_monat_in: Mengen-Saison-Filter auf der Erfassungs-Achse
        # ("Indoor-Phase November ODER Dezember ODER Januar"). Spiegelt
        # funddatum_monat_in; Validierung 1..12 identisch (Tippfehler 0/13
        # erzeugen klaren Fehler statt stillen Leerergebnisses).
        if erstellt_am_monat_in:
            monate = [int(m) for m in erstellt_am_monat_in]
            invalid = [m for m in monate if not 1 <= m <= 12]
            if invalid:
                raise ValueError(
                    f"Unbekannte Erstellt-am-Monate: {invalid} "
                    f"(erwartet 1..12)")
            if monate:
                placeholders = ", ".join("?" * len(monate))
                where.append(
                    "o.erstellt_am IS NOT NULL AND TRIM(o.erstellt_am) != '' "
                    "AND substr(o.erstellt_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    "AND substr(o.erstellt_am, 6, 2) GLOB '[0-1][0-9]' "
                    f"AND CAST(substr(o.erstellt_am, 6, 2) AS INTEGER) IN "
                    f"({placeholders})")
                params.extend(monate)
        # erstellt_am-Bereich auf Tagesgenauigkeit/Sekundengenauigkeit: ISO
        # YYYY-MM-DD[ HH:MM:SS] ist lexikographisch vergleichbar, daher reicht
        # ein direkter String-Vergleich ohne Datums-Parsing. Spiegelt funddatum_
        # min/_max auf die Erfassungs-Achse und ergaenzt die diskreten Jahr/
        # Jahrzehnt/Monat-Filter um einen tagesgenauen Stichtag-Filter (z.B.
        # "alle ab dem KI-Welle-Start 2024-03-15 erfassten Stuecke"). Akzeptiert
        # auch YYYY-MM oder YYYY allein, weil ISO-Praefixe lexikographisch
        # mit dem voll qualifizierten Stempel kompatibel sind. NULL/leere
        # Stempel werden konsistent zur funddatum_min/_max-Konvention
        # ausgeschlossen.
        if erstellt_am_min is not None:
            where.append("o.erstellt_am IS NOT NULL AND TRIM(o.erstellt_am) != '' "
                         "AND o.erstellt_am >= ?")
            params.append(str(erstellt_am_min))
        if erstellt_am_max is not None:
            where.append("o.erstellt_am IS NOT NULL AND TRIM(o.erstellt_am) != '' "
                         "AND o.erstellt_am <= ?")
            params.append(str(erstellt_am_max))
        # Aenderungs-Achse: filtert nach Jahr des ``geaendert_am``-Stempels (wann
        # zuletzt redaktionell angefasst). Spiegelt erstellt_am_jahr_min/_max auf
        # die zweite Zeitstempel-Spalte und beantwortet die typische Pflege-Frage
        # "welche Stuecke habe ich dieses Jahr noch beruehrt - und welche
        # schlummern seit Jahren unveraendert in der Vitrine?" (Default-Verhalten
        # beim Erstellen: erstellt_am == geaendert_am; die Achsen divergieren erst,
        # sobald nach dem Anlegen mindestens ein Datenblatt-Update lief). Substring
        # 1..4 ist analog zu erstellt_am_jahr und zum geaendert_am-Spanne-Aggregat
        # in stats.py; nur vierstellige Jahres-Praefixe matchen, damit kaputte
        # Stempel historischer Imports (leerer / non-ISO-Wert) nicht das Ergebnis
        # verzerren. Implementations-Konvention identisch zu erstellt_am_jahr_min/
        # _max: erst die Praefix-Pruefung als Guard, dann die zwei optionalen
        # Schranken, damit None=ohne-Schranke und Range-Filter ohne untere oder
        # obere Grenze beide korrekt arbeiten.
        if geaendert_am_jahr_min is not None or geaendert_am_jahr_max is not None:
            where.append("substr(o.geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
            if geaendert_am_jahr_min is not None:
                where.append("CAST(substr(o.geaendert_am, 1, 4) AS INTEGER) >= ?")
                params.append(int(geaendert_am_jahr_min))
            if geaendert_am_jahr_max is not None:
                where.append("CAST(substr(o.geaendert_am, 1, 4) AS INTEGER) <= ?")
                params.append(int(geaendert_am_jahr_max))
        # geaendert_am_jahr_in: diskrete Aenderungs-Jahres-Menge ("zuletzt 2022
        # ODER 2024 angefasst") - komplementaer zum Bereichsfilter
        # geaendert_am_jahr_min/_max. Spiegelt erstellt_am_jahr_in / funddatum_jahr_in
        # auf die zweite Zeitstempel-Spalte: ein Stueck zaehlt fuer das Jahr, in dem
        # die letzte redaktionelle Beruehrung stattfand, unabhaengig vom Erfassungs-
        # Jahr und vom Funddatum. Beantwortet die Listen-Drill-Down-Variante der
        # typischen Pflege-Frage "welche Stuecke habe ich in diesen Pflege-Wellen
        # zuletzt redaktionell beruehrt?" - z.B. zwei Pflege-Schuebe nach Boersen-
        # Besuchen (2022 Tucson-Nachbearbeitung ODER 2024 Muenchen-Nachbearbeitung).
        # Validierung 1800..2999 identisch zu erstellt_am_jahr_in / funddatum_jahr_in,
        # damit Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses
        # erzeugen.
        if geaendert_am_jahr_in:
            jahre = [int(j) for j in geaendert_am_jahr_in]
            invalid = [j for j in jahre if not 1800 <= j <= 2999]
            if invalid:
                raise ValueError(
                    f"Unbekannte Geaendert-am-Jahre: {invalid} "
                    f"(erwartet 1800..2999)")
            if jahre:
                placeholders = ", ".join("?" * len(jahre))
                where.append(
                    f"substr(o.geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    f"AND CAST(substr(o.geaendert_am, 1, 4) AS INTEGER) IN "
                    f"({placeholders})")
                params.extend(jahre)
        # geaendert_am_jahrzehnt_in: diskrete Aenderungs-Dekaden-Menge ("Pflege-
        # Welle in den 2010ern ODER 2020ern") - komplementaer zu
        # geaendert_am_jahr_in (Einzeljahre) und zum Bereichsfilter
        # geaendert_am_jahr_min/_max. Spiegelt erstellt_am_jahrzehnt_in /
        # funddatum_jahrzehnt_in auf die zweite Zeitstempel-Spalte: gruppiert
        # das Jahr per Integer-Div durch 10 und vergleicht mit der angegebenen
        # Dekaden-Startzahl (``2010`` selektiert 2010..2019, nicht "2010er"-String).
        # Aenderungs-Dekaden trennen i.d.R. ganze Pflege-Generationen: 2010er
        # haendisch gepflegte Stuecke (vor dem Datenblatt-Schema-Wechsel) vs.
        # 2020er Migrations-/KI-Welle (nach dem Datenblatt-Schema-Wechsel).
        # Validierung 1800..2990 (durch 10 teilbar) identisch zu
        # erstellt_am_jahrzehnt_in / funddatum_jahrzehnt_in, damit
        # Tippfehler (2015 als Mitten-Jahr / 1700 ausserhalb / 3000 ausserhalb)
        # einen klaren Fehler statt eines stillen Leerergebnisses erzeugen.
        if geaendert_am_jahrzehnt_in:
            dekaden = [int(d) for d in geaendert_am_jahrzehnt_in]
            invalid = [d for d in dekaden
                       if not (1800 <= d <= 2990 and d % 10 == 0)]
            if invalid:
                raise ValueError(
                    f"Unbekannte Geaendert-am-Jahrzehnte: {invalid} "
                    f"(erwartet 1800..2990, durch 10 teilbar)")
            if dekaden:
                placeholders = ", ".join("?" * len(dekaden))
                where.append(
                    f"substr(o.geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    f"AND (CAST(substr(o.geaendert_am, 1, 4) AS INTEGER) / 10) * 10 "
                    f"IN ({placeholders})")
                params.extend(dekaden)
        # geaendert_am_monat: Saison-Filter ueber alle Jahre auf der Aenderungs-
        # Achse ("alle im Januar nachbearbeiteten Stuecke") - spiegelt
        # erstellt_am_monat / funddatum_monat auf die zweite Zeitstempel-Spalte
        # und beantwortet die typische Pflege-Frage "in welchen Monaten habe ich
        # zuletzt am Bestand redaktionell gearbeitet?". Aussenkontext-bedingt
        # treten typische Pflege-Spitzen analog zur Erfassungs-Achse im Winter
        # auf (Indoor-Phase November-Januar, Boersen-Nachbearbeitung Februar/
        # Maerz nach Tucson), aber als zweite Achse: ein Stueck kann im Juli
        # erfasst (Sommer-Tour) und im Januar redaktionell ueberarbeitet worden
        # sein (Winter-Pflege). Substring 6..7 ist analog zu erstellt_am_monat;
        # nur vierstellige Jahres-Praefixe und gueltige Monatsteile 01..12 matchen,
        # damit reine Jahresangaben ohne Monat automatisch herausfallen.
        if geaendert_am_monat is not None:
            m = int(geaendert_am_monat)
            if not 1 <= m <= 12:
                raise ValueError(
                    f"geaendert_am_monat muss zwischen 1 und 12 liegen (war: {m})")
            where.append(
                "o.geaendert_am IS NOT NULL AND TRIM(o.geaendert_am) != '' "
                "AND substr(o.geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                "AND substr(o.geaendert_am, 6, 2) GLOB '[0-1][0-9]' "
                "AND CAST(substr(o.geaendert_am, 6, 2) AS INTEGER) = ?")
            params.append(m)
        # geaendert_am_monat_in: Mengen-Saison-Filter auf der Aenderungs-Achse
        # ("Indoor-Pflege-Phase November ODER Dezember ODER Januar"). Komplementaer
        # zum einzelnen geaendert_am_monat-Filter; spiegelt erstellt_am_monat_in /
        # funddatum_monat_in in der diskreten Mengen-Notation. Beantwortet die
        # typische "Mehrere Pflege-Spitzen kombinieren"-Frage: Indoor-Phase
        # November/Dezember/Januar als zusammenhaengender Pflege-Block, oder
        # Boersen-Nachbearbeitung Februar (Tucson) + Oktober (Muenchen, Sainte-
        # Marie-aux-Mines). Erwartet jeden Eintrag in 1..12 (Tippfehler 0/13
        # erzeugen einen klaren Fehler statt eines stillen Leerergebnisses).
        if geaendert_am_monat_in:
            monate = [int(m) for m in geaendert_am_monat_in]
            invalid = [m for m in monate if not 1 <= m <= 12]
            if invalid:
                raise ValueError(
                    f"Unbekannte Geaendert-am-Monate: {invalid} "
                    f"(erwartet 1..12)")
            if monate:
                placeholders = ", ".join("?" * len(monate))
                where.append(
                    "o.geaendert_am IS NOT NULL AND TRIM(o.geaendert_am) != '' "
                    "AND substr(o.geaendert_am, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                    "AND substr(o.geaendert_am, 6, 2) GLOB '[0-1][0-9]' "
                    f"AND CAST(substr(o.geaendert_am, 6, 2) AS INTEGER) IN "
                    f"({placeholders})")
                params.extend(monate)
        # geaendert_am-Bereich auf Tagesgenauigkeit/Sekundengenauigkeit:
        # spiegelt erstellt_am_min/_max auf die Aenderungs-Achse und
        # funddatum_min/_max auf die Fund-Achse - schliesst die Tagesgenau-
        # Stichtag-Trias der drei Zeitstempel-Spalten ab. ISO YYYY-MM-DD
        # [ HH:MM:SS] ist lexikographisch vergleichbar, daher reicht ein
        # direkter String-Vergleich ohne Datums-Parsing. Beantwortet die
        # typische Pflege-Stichtag-Frage "welche Stuecke wurden seit dem
        # letzten Boersen-Besuch redaktionell beruehrt?" tagesgenau (oder
        # sekundengenau auf dem voll qualifizierten Stempel), waehrend die
        # existierenden Jahr/Jahrzehnt/Monat-Filter nur grobe Diskreti-
        # sierungen ueber die Aenderungs-Achse boten. NULL/leere geaendert_am-
        # Stempel werden konsistent zu erstellt_am_min/_max und funddatum_min/
        # _max ausgeschlossen.
        if geaendert_am_min is not None:
            where.append("o.geaendert_am IS NOT NULL AND TRIM(o.geaendert_am) != '' "
                         "AND o.geaendert_am >= ?")
            params.append(str(geaendert_am_min))
        if geaendert_am_max is not None:
            where.append("o.geaendert_am IS NOT NULL AND TRIM(o.geaendert_am) != '' "
                         "AND o.geaendert_am <= ?")
            params.append(str(geaendert_am_max))
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
        # Wert_pro_Gewicht-Filter als Filter-Ebenen-Pendant zur Wert_pro_Gewicht_chf_g-
        # Sortier-Achse: spezifische Marktwert-Dichte (CHF/g) als Bereichs-Grenze.
        # Sammler-/Verkaeufer-Frage: "welche Stuecke rentieren sich pro Gramm
        # ueberhaupt fuer den Boersen-Transport (>= 1 CHF/g, sonst frisst die
        # Wegzeit den Ertrag)?" -> wert_pro_gewicht_min=1.0; oder "welche sind
        # potentielle Schmuck-/Karat-Kandidaten (>= 10 CHF/g, typisch fuer
        # Rubin-/Smaragd-/Diamant-Splitter)?" -> wert_pro_gewicht_min=10.0.
        # Spiegelt volumen_min/max und wert_min/max: derselbe SQL-Ausdruck wie
        # in der SELECT-Liste (der Zaehler {wert_sql}, der Nenner Gewicht_g mit
        # Null-Guard), damit der Filter exakt mit der Sortier-Spalte
        # uebereinstimmt (Sortier-nach-Wert_pro_Gewicht_chf_g + Filter
        # wert_pro_gewicht_min=10 selektieren dieselbe Zahlen-Domain, kein
        # Drift zwischen Filter- und Sortier-Definition). NULL-Semantik der
        # Sortier-Achse spiegelt sich auch hier: fehlende oder Null-Masse
        # (Gewicht_g IS NULL OR = 0) laesst die CASE-Expression NULL werden,
        # und NULL >= X / NULL <= X sind beide NULL == FALSE - solche Objekte
        # fallen implizit aus dem Filter, spiegelt die volumen_-/mohs_-/dichte_-
        # Konvention.
        if wert_pro_gewicht_min is not None:
            where.append(
                f"(CASE WHEN o.Gewicht_g IS NULL OR o.Gewicht_g = 0 THEN NULL "
                f"ELSE {wert_sql} * 1.0 / o.Gewicht_g END) >= ?")
            params.append(float(wert_pro_gewicht_min))
        if wert_pro_gewicht_max is not None:
            where.append(
                f"(CASE WHEN o.Gewicht_g IS NULL OR o.Gewicht_g = 0 THEN NULL "
                f"ELSE {wert_sql} * 1.0 / o.Gewicht_g END) <= ?")
            params.append(float(wert_pro_gewicht_max))
        # Wert_pro_Volumen-Filter als Filter-Ebenen-Pendant zur Wert_pro_Volumen_chf_mm3-
        # Sortier-Achse: spezifische Marktwert-Dichte (CHF/mm3) als Bereichs-Grenze.
        # Sammler-Frage: "welche Stuecke rentieren sich pro Vitrinen-mm3 ueberhaupt
        # (>= 0.01 CHF/mm3, sonst frisst der Aufbewahrungs-Platz den Ertrag)?"
        # oder "welche sind potentielle Karat-Kandidaten (>= 1 CHF/mm3, typisch
        # fuer Rubin-/Smaragd-/Diamant-Splitter)?". Spiegelt wert_pro_gewicht_min/
        # max auf die Volumen-Achse: derselbe CASE-WHEN-Ausdruck wie in der
        # SELECT-Liste (der Zaehler {wert_sql}, der Nenner Laenge*Breite*Hoehe mit
        # NULL-/Null-Guard fuer alle drei Achsen), damit der Filter exakt mit der
        # Sortier-Spalte uebereinstimmt (Sortier-nach-Wert_pro_Volumen_chf_mm3 +
        # Filter wert_pro_volumen_min=1.0 selektieren dieselbe Zahlen-Domain,
        # kein Drift zwischen Filter- und Sortier-Definition). NULL-Semantik der
        # Sortier-Achse spiegelt sich auch hier: mindestens eine fehlende Dimension
        # oder Null-Produkt laesst die CASE-Expression NULL werden, und NULL >= X
        # / NULL <= X sind beide NULL == FALSE - solche Objekte fallen implizit
        # aus dem Filter, spiegelt die volumen_-/wert_pro_gewicht_-/mohs_-/dichte_-
        # Konvention.
        if wert_pro_volumen_min is not None:
            where.append(
                f"(CASE WHEN o.Laenge_mm IS NULL OR o.Breite_mm IS NULL "
                f"OR o.Hoehe_mm IS NULL "
                f"OR (o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) = 0 THEN NULL "
                f"ELSE {wert_sql} * 1.0 "
                f"/ (o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) END) >= ?")
            params.append(float(wert_pro_volumen_min))
        if wert_pro_volumen_max is not None:
            where.append(
                f"(CASE WHEN o.Laenge_mm IS NULL OR o.Breite_mm IS NULL "
                f"OR o.Hoehe_mm IS NULL "
                f"OR (o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) = 0 THEN NULL "
                f"ELSE {wert_sql} * 1.0 "
                f"/ (o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) END) <= ?")
            params.append(float(wert_pro_volumen_max))
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
        # Volumen_mm3-Filter als kombinierte Groessen-Achse (Produkt L*B*H):
        # ergaenzt die drei Einzel-Achsen laenge_/breite_/hoehe_min/max um die
        # Vitrinen-Gesamtgroesse - "welche Stuecke sind ueberhaupt sammelwuerdig
        # (>= 10 cm3)?" -> volumen_min=10000. Spiegelt die Volumen_mm3-Sortier-
        # Achse aus SORTABLE_COLUMNS auf die Filter-Ebene. NULL-Eintraege
        # (mindestens eine Dimension nicht vermessen) fallen durch die
        # ?-Vergleiche raus, spiegelt die laenge_/breite_/hoehe_-Konvention und
        # die Produkt-NULL-Semantik der Volumen_mm3-Sortierung.
        if volumen_min is not None:
            where.append(
                "(o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) >= ?")
            params.append(float(volumen_min))
        if volumen_max is not None:
            where.append(
                "(o.Laenge_mm * o.Breite_mm * o.Hoehe_mm) <= ?")
            params.append(float(volumen_max))
        # Mohs-Haerte-Filter ueber das min/max-Spaltenpaar: Sammler-Frage
        # "welche Stuecke sind hart genug fuer Schmuck (>=7)?" -> mohs_min=7,
        # filtert auf Mohs_Haerte_min (das Mineral faellt nirgends unter 7).
        # Spiegelbild ``mohs_max`` auf Mohs_Haerte_max (das Mineral ueberschreitet
        # den Wert nirgends) - schliesst weiche Stuecke fuer Strichtest aus
        # ("welche sind nicht haerter als 3?"). Kombiniert liefert es Stuecke,
        # deren ganzer Haertebereich in [mohs_min..mohs_max] liegt - analog zur
        # laenge_/breite_/hoehe_-Vitrinen-Auswahl, hier auf zwei Spalten verteilt.
        # NULL-Eintraege (nicht bestimmte Haerte) fallen durch ?-Vergleich raus.
        if mohs_min is not None:
            where.append("o.Mohs_Haerte_min >= ?")
            params.append(float(mohs_min))
        if mohs_max is not None:
            where.append("o.Mohs_Haerte_max <= ?")
            params.append(float(mohs_max))
        # Dichte-Filter analog zur Mohs-Haerte ueber das min/max-Spaltenpaar.
        # Sammler-Frage: "welche Stuecke sind dicht genug fuer Erz-Vermutung
        # (>=5 g/cm3, Magnetit/Haematit/Galenit)?" -> dichte_min=5.0; oder
        # "welche koennten Bims/Aerogel/Aussen-Rohstoffe sein (<=2)?" ->
        # dichte_max=2.0. NULL-Eintraege fallen durch ?-Vergleich aussen vor.
        if dichte_min is not None:
            where.append("o.Dichte_min_gcm3 >= ?")
            params.append(float(dichte_min))
        if dichte_max is not None:
            where.append("o.Dichte_max_gcm3 <= ?")
            params.append(float(dichte_max))
        # Globale Seltenheit (1=haeufig .. 10=sehr selten) als Bereichsfilter.
        # Sammler-Frage: "welche Stuecke sind global Top-Rare (>=8)?" liefert
        # die Vitrinen-Schaustuecke; ``seltenheit_global_max=3`` selektiert
        # Tauschmaterial (haeufige Stuecke). Validierung 1..10 via Helper
        # (Tippfehler 0/11 -> ValueError); NULL-Eintraege fallen aus dem
        # Vergleich raus.
        _append_scale_1_10_filter(
            where, params, "seltenheit_global", "Seltenheit_global_1_10",
            seltenheit_global_min, seltenheit_global_max)
        # Standort-Seltenheit (1=am Fundort haeufig .. 10=am Fundort sehr selten):
        # komplementaer zur globalen Rarity: ein global haeufiger Quarz kann am
        # Fundort selten sein, wenn der Aufschluss kaum Quarz fuehrt (oder
        # umgekehrt: lokale Massenware, global trotzdem rar). Filtert lokal
        # interessante Stuecke (>=8) vs. Fundort-Standardware (<=3).
        _append_scale_1_10_filter(
            where, params, "seltenheit_fundort", "Seltenheit_Fundort_1_10",
            seltenheit_fundort_min, seltenheit_fundort_max)
        # Marktnachfrage (1=geringe Nachfrage .. 10=stark gefragt): ``nachfrage_min=7``
        # selektiert Verkaufs-Kandidaten, ``nachfrage_max=3`` Lager-/Tausch-
        # material ohne akute Marktattraktivitaet.
        _append_scale_1_10_filter(
            where, params, "nachfrage", "Nachfrage_1_10",
            nachfrage_min, nachfrage_max)
        if kristallsystem:
            where.append("o.Kristallsystem = ?")
            params.append(kristallsystem)
        # kristallsystem_in: Mengen-Filter ("trigonal ODER hexagonal" fuer Quarz-Familie).
        # Spiegelt status_in: validiert gegen VALID_KRISTALLSYSTEME aus dem Feldwoerterbuch,
        # damit Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses erzeugen.
        # Kombinierbar mit dem exakten ``kristallsystem``-Filter (Schnittmenge).
        _append_enum_in_filter(where, params, kristallsystem_in, "Kristallsystem",
                               "Kristallsystem", VALID_KRISTALLSYSTEME)
        if beste_verwendung:
            where.append("o.Beste_Verwendung = ?")
            params.append(beste_verwendung)
        # beste_verwendung_in: Mengen-Filter ("Schmuck ODER Sammlung", aber nicht
        # Industrie/Talisman). Spiegelt status_in / kristallsystem_in: validiert
        # gegen VALID_BESTE_VERWENDUNG, damit Tippfehler einen klaren Fehler
        # statt eines stillen Leerergebnisses erzeugen.
        _append_enum_in_filter(where, params, beste_verwendung_in, "Beste_Verwendung",
                               "Beste_Verwendung", VALID_BESTE_VERWENDUNG)
        if glanz:
            where.append("o.Glanz = ?")
            params.append(glanz)
        # glanz_in: Mengen-Filter ("glasig ODER metallisch ODER seidig") fuer die
        # optische Auswahl. Spiegelt kristallsystem_in / beste_verwendung_in:
        # validiert gegen VALID_GLANZ aus dem Feldwoerterbuch, damit Tippfehler
        # einen klaren Fehler statt eines stillen Leerergebnisses erzeugen.
        # Kombinierbar mit dem exakten ``glanz``-Filter (Schnittmenge).
        _append_enum_in_filter(where, params, glanz_in, "Glanz", "Glanz",
                               VALID_GLANZ)
        if transparenz:
            where.append("o.Transparenz = ?")
            params.append(transparenz)
        # transparenz_in: Mengen-Filter ("durchsichtig ODER durchscheinend")
        # fuer Foto-Setup-Auswahl: lichtdurchlaessige Stuecke brauchen Back-
        # light, opake nicht. Spiegelt glanz_in / kristallsystem_in: validiert
        # gegen VALID_TRANSPARENZ (durchsichtig/durchscheinend/opak), damit
        # Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses
        # erzeugen. Kombinierbar mit dem exakten ``transparenz``-Filter.
        _append_enum_in_filter(where, params, transparenz_in, "Transparenz",
                               "Transparenz", VALID_TRANSPARENZ)
        # magnetismus_in: Mengen-Filter ("ja ODER schwach") als Eisen-Auswahl -
        # alle magnetisch reagierenden Stuecke (Magnetit/Pyrrhotin/Haematit/
        # Ilmenit) in einer Sicht, ohne dass die inerten Quarz-/Calcit-Stuecke
        # mitkommen. Spiegelt glanz_in/transparenz_in: validiert gegen
        # VALID_MAGNETISMUS (ja/schwach/nein), damit Tippfehler einen klaren
        # Fehler statt eines stillen Leerergebnisses erzeugen.
        _append_enum_in_filter(where, params, magnetismus_in, "Magnetismus",
                               "Magnetismus", VALID_MAGNETISMUS)
        # spaltbarkeit_in: Mengen-Filter ("vollkommen ODER gut") als Praeparier-
        # Auswahl - alle sauber spaltbaren Stuecke (Calcit/Fluorit/Glimmer) in
        # einer Sicht, ohne dass die zaehen Quarz-Brocken (keine) mitkommen.
        # Spiegelt magnetismus_in/transparenz_in: validiert gegen
        # VALID_SPALTBARKEIT (vollkommen/gut/deutlich/undeutlich/keine), damit
        # Tippfehler einen klaren Fehler statt eines stillen Leerergebnisses
        # erzeugen.
        _append_enum_in_filter(where, params, spaltbarkeit_in, "Spaltbarkeit",
                               "Spaltbarkeit", VALID_SPALTBARKEIT)
        # bruch_in: Mengen-Filter ("muschelig ODER splittrig") als Schaerfe-
        # kanten-Auswahl - Stuecke, die ohne Spaltflaechen scharfe Kanten
        # erzeugen (Obsidian/Quarz/Feuerstein), in einer Sicht ohne fasrige
        # Aktinolith-/erdige Limonit-Stuecke. Spiegelt spaltbarkeit_in/
        # magnetismus_in: validiert gegen VALID_BRUCH (muschelig/uneben/
        # splittrig/faserig/erdig/glatt), damit Tippfehler einen klaren
        # Fehler statt eines stillen Leerergebnisses erzeugen.
        _append_enum_in_filter(where, params, bruch_in, "Bruch", "Bruch",
                               VALID_BRUCH)
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

    def list_objects_in_bbox(self, lat_min: float, lat_max: float,
                             lon_min: float, lon_max: float
                             ) -> list[tuple[str, float, float]]:
        """Listet Objekte mit Fundort-Koordinaten innerhalb einer Bounding-Box.

        Scant alle Objekte mit nicht-leerem Fundort, parst die enthaltenen
        Koordinaten via :func:`stonebook.migration.validators.parse_coordinates`
        und liefert nur die Objekte, deren Koordinaten in der Box liegen.
        Fundort-Eintraege ohne erkennbare Koordinaten (z.B. reine Ortsnamen
        wie ``"Berner Oberland"``) werden uebergangen.

        Reine Python-Schicht ueber die DB-Sicht: Fundort ist eine freie
        str-Spalte ohne strukturierte Koordinaten-Achse, daher gibt es kein
        SQL-Aequivalent. Verglichen mit den SQL-basierten ``list_objects``-
        Filtern ist der Pfad langsamer (O(n) Python pro Aufruf), bleibt aber
        bei einer Sammler-DB mit O(10^3) Eintraegen unter Sekundenzeit; fuer
        groessere Datasets sollte eine extrahierte Koordinaten-Spalte mit
        SQL-Range-Filter angedacht werden. Reihenfolge: aufsteigend nach
        ``obj_id``, damit der Filter deterministisch ist.

        Box-Konvention: lat in [lat_min, lat_max] und lon in [lon_min, lon_max],
        beide Grenzen inklusiv (spiegelt die ``BETWEEN``-Konvention der
        SQL-Range-Filter). Bei lat_min > lat_max bzw. lon_min > lon_max ist
        die Schnittmenge leer; die Datums-Grenze (lon ueber +/-180 hinweg)
        wird nicht behandelt - der Caller muss zwei Boxen abfragen, wenn
        sein Suchgebiet ueber die +/-180-Linie laeuft (in der Praxis fuer
        Sammler-Daten irrelevant).
        """
        from stonebook.migration.validators import parse_coordinates

        rows = self.conn.execute(
            "SELECT obj_id, Fundort FROM objects "
            "WHERE Fundort IS NOT NULL AND TRIM(Fundort) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        result: list[tuple[str, float, float]] = []
        for row in rows:
            coords = parse_coordinates(row["Fundort"])
            if coords is None:
                continue
            lat, lon = coords
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                result.append((row["obj_id"], lat, lon))
        return result

    def list_objects_ohne_koordinaten(self) -> list[tuple[str, str]]:
        """Listet Objekte mit dokumentiertem Fundort, aber ohne parsebare Lat/Lon.

        Pflege-Sicht zur quote_mit_koordinaten_prozent-Coverage: waehrend die
        Coverage-Quote den Anteil beziffert ("welcher Anteil meiner Sammlung
        ist geocoded?"), liefert dieser Helper die konkrete Arbeitsliste der
        noch nicht geocodeden Stuecke ("welche Stuecke fehlen mir konkret?")
        - typischer naechster Schritt im Sammlungs-Pflege-Workflow nach dem
        Statistik-Block. Komplementaer zu ``list_objects_in_bbox`` auf der
        gleichen Python-Achse: dort die punktuelle Suche im Box-Gebiet, hier
        die Pflege-Restmenge ausserhalb jeder geografischen Erreichbarkeit.

        Reuse-Pfad: SELECT Fundort fuer alle Objekte mit nicht-leerem Fundort,
        ``parse_coordinates`` auf jeden Wert, Treffer mit ``None``-Ergebnis
        zurueck. Rueckgabe als (obj_id, Fundort)-Tuple, damit der Caller den
        rohen Freitext-Eintrag ohne erneutes Lookup hat (typisch: anzeigen in
        einer Pflege-Liste mit Klick-zu-bearbeiten oder Geocoder-Vorschlag).
        Objekte ohne Fundort werden uebergangen (sie tauchen in
        ``has_fundort=False`` auf, das ist eine eigene Pflege-Achse:
        Fundort-Akquise vs. Geocoding-Ergaenzung). Reihenfolge aufsteigend
        nach ``obj_id``, damit die Pflege-Liste deterministisch ist.
        """
        from stonebook.migration.validators import parse_coordinates

        rows = self.conn.execute(
            "SELECT obj_id, Fundort FROM objects "
            "WHERE Fundort IS NOT NULL AND TRIM(Fundort) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        return [(row["obj_id"], row["Fundort"]) for row in rows
                if parse_coordinates(row["Fundort"]) is None]

    def list_objects_mit_ungueltigem_funddatum(self) -> list[tuple[str, str]]:
        """Listet Objekte mit dokumentiertem Funddatum, aber ohne strikte ISO-Form.

        Pflege-Sicht auf die Funddatum-Achse als Spiegel von
        ``list_objects_ohne_koordinaten`` auf der Fundort-Achse: waehrend die
        Koordinaten-Pflege den Fundort-Freitext auf parsebare Lat/Lon-Paare
        prueft, prueft dieser Helper den Funddatum-Freitext auf die strikte
        YYYY-MM-DD-Form, die die Standard-Schreibweise laut Feldwoerterbuch
        (``fields.py`` ``FieldDef(..., "date", ...)`` mit Description
        ``"YYYY-MM-DD"``) und die Konvention der CSV-Migration
        (``load_v2``/``load_standard`` schreiben nur ``parse_iso_date``-
        normalisierte Werte oder ueberspringen den Eintrag) darstellt.
        Nicht-strikte Werte wie ``"13.06.2024"``, ``"2024"``, ``"unbekannt"``
        oder ``"2024-13-01"`` (ungueltiger Monat) und ``"2024-02-30"``
        (ungueltiger Tag im Feb) tauchen typischerweise nach manueller
        DB-Edition, JSON-Restore aus externer Quelle oder alten
        Vor-Migrations-Datensaetzen auf - fuer diese Faelle liefert der
        Helper eine deterministische Arbeitsliste zur Nachpflege.

        Sowohl Struktur (10-Zeichen-YYYY-MM-DD-Regex) als auch semantische
        Gueltigkeit (``datetime.date``-Konstruktion, damit Monat 13 oder
        Tag 30 im Feb aussortiert werden) muessen bestanden werden. Nur
        das strikte Format zaehlt als valide - die permissive
        ``parse_iso_date``-Umformung ist Migrations-/Import-Logik und
        nicht die DB-Ziel-Form. Objekte ohne Funddatum werden uebergangen
        (sie tauchen in ``has_funddatum=False`` auf, das ist eine eigene
        Pflege-Achse: Datums-Akquise vs. Formatnorm). Reihenfolge
        aufsteigend nach ``obj_id``, damit die Pflege-Liste
        deterministisch ist.

        Rueckgabe als ``(obj_id, Funddatum)``-Tupel, damit der Caller den
        rohen Freitext-Eintrag ohne erneutes Lookup hat (typisch: in einer
        Pflege-Liste anzeigen mit Klick-zu-bearbeiten oder als
        ``parse_iso_date``-Vorschlag).
        """
        rows = self.conn.execute(
            "SELECT obj_id, Funddatum FROM objects "
            "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        result: list[tuple[str, str]] = []
        for row in rows:
            raw = row["Funddatum"]
            if _STRICT_ISO_DATE_RE.match(raw):
                y, m, d = int(raw[0:4]), int(raw[5:7]), int(raw[8:10])
                try:
                    datetime.date(y, m, d)
                    continue
                except ValueError:
                    pass
            result.append((row["obj_id"], raw))
        return result

    def list_objects_in_radius(self, lat_center: float, lon_center: float,
                               radius_km: float
                               ) -> list[tuple[str, float, float, float]]:
        """Listet Objekte mit Fundort-Koordinaten im Umkreis um einen Mittelpunkt.

        Geografisches Disk-Pendant zu ``list_objects_in_bbox``: waehrend die
        Bounding-Box ein rechteckiges Lat/Lon-Gebiet beschreibt (typografisch
        einfach, aber nahe den Polen stark verzerrt), ist der Umkreis die
        natuerliche Form fuer die Sammler-Frage 'welche Stuecke liegen in X km
        Umgebung um meinen aktuellen Standort?'. Der Bounding-Box-Filter ist
        eine grobe Annaeherung, der Umkreis-Filter die exakte Disk - beide
        bedienen verschiedene Auspraegungen derselben geografischen
        Such-Achse.

        Distanz wird via Haversine-Formel auf einer Erd-Sphaere mit Radius
        6371.0 km berechnet (mittlerer Erdradius; geodaetisch genau genug fuer
        Sammler-Distanzen unter 1000 km, wo der Sphaeren-vs-Ellipsoid-Fehler
        unter 0.5 % bleibt). Reuse-Pfad zu ``list_objects_in_bbox``: SELECT
        Fundort fuer alle Objekte mit nicht-leerem Fundort,
        ``parse_coordinates`` auf jeden Wert, Distanz-Test gegen den Umkreis.
        Fundort-Eintraege ohne erkennbare Koordinaten (reine Ortsnamen wie
        ``"Berner Oberland"``) werden uebergangen - sie laufen ueber
        ``list_objects_ohne_koordinaten`` auf der Pflege-Achse.

        Rueckgabe als ``(obj_id, lat, lon, distance_km)``-Tupel - die
        Distanz wird durchgereicht, damit der Caller eine Trefferliste nach
        Naehe sortieren oder gruppieren kann ohne erneuten Haversine-
        Aufruf. Reihenfolge: aufsteigend nach Distanz, sekundaer nach
        ``obj_id`` fuer deterministische Ausgabe (zwei Stuecke aus exakt
        derselben Lokalitaet haben identische Distanz - die obj_id-
        Sortierung verhindert nicht-deterministische Reihenfolge).

        ``radius_km`` < 0 liefert eine leere Trefferliste (negative Radien
        sind semantisch leer); ``radius_km`` == 0 trifft nur Stuecke exakt
        am Mittelpunkt (selten relevant, aber konsistent zur Disk-Definition).
        """
        if radius_km < 0:
            return []
        result = [r for r in self._list_objects_haversine(lat_center, lon_center)
                  if r[3] <= radius_km]
        result.sort(key=lambda r: (r[3], r[0]))
        return result

    def _list_objects_haversine(
        self, lat_center: float, lon_center: float,
    ) -> list[tuple[str, float, float, float]]:
        """Interner Helper: liefert (obj_id, lat, lon, distance_km) fuer
        alle Objekte mit per :func:`parse_coordinates` erkennbaren
        Fundort-Koordinaten, unsortiert.

        Gemeinsame Reuse-Basis fuer ``list_objects_nearest``
        (aufsteigende K-NN-Auswahl) und ``list_objects_farthest``
        (absteigende K-FN-Auswahl) - beide K-Extrema-Suchen teilen
        exakt dieselbe Distanzberechnung (Haversine auf Erd-Sphaere
        mit Radius 6371.0 km) und unterscheiden sich nur in der
        Sortier-Richtung. Ohne diesen Helper wuerde jede Aenderung an
        der Distanz-Konvention (Erdradius, Ausnahmen fuer Antipode-
        Punkte, DMS-Toleranz) in zwei parallelen Copy-Paste-Kopien
        gepflegt und koennte silent divergieren; die geteilte Basis
        haelt beide Achsen strukturell konsistent.

        Reihenfolge der Rueckgabe = ``obj_id`` (spiegelt die SELECT-
        Reihenfolge); die Sortierung nach Distanz erfolgt im Caller.
        """
        import math
        from stonebook.migration.validators import parse_coordinates

        rows = self.conn.execute(
            "SELECT obj_id, Fundort FROM objects "
            "WHERE Fundort IS NOT NULL AND TRIM(Fundort) != '' "
            "ORDER BY obj_id"
        ).fetchall()
        earth_radius_km = 6371.0
        lat_c_rad = math.radians(lat_center)
        lon_c_rad = math.radians(lon_center)
        result: list[tuple[str, float, float, float]] = []
        for row in rows:
            coords = parse_coordinates(row["Fundort"])
            if coords is None:
                continue
            lat, lon = coords
            lat_rad = math.radians(lat)
            lon_rad = math.radians(lon)
            dlat = lat_rad - lat_c_rad
            dlon = lon_rad - lon_c_rad
            a = (math.sin(dlat / 2) ** 2
                 + math.cos(lat_c_rad) * math.cos(lat_rad) * math.sin(dlon / 2) ** 2)
            distance_km = 2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a)))
            result.append((row["obj_id"], lat, lon, distance_km))
        return result

    def list_objects_nearest(self, lat_center: float, lon_center: float,
                             limit: int
                             ) -> list[tuple[str, float, float, float]]:
        """Listet die ``limit`` Objekte mit Fundort-Koordinaten am naechsten zum Mittelpunkt.

        K-Nearest-Neighbors-Pendant zu ``list_objects_in_radius``:
        waehrend die Disk-Suche eine Distanz-Grenze setzt (alle Stuecke
        innerhalb X km, ohne Mengen-Schranke), beantwortet die K-NN-
        Variante die spiegelbildliche Frage 'welche sind die N nahesten
        Stuecke zu meinem Standort?' (Mengen-Grenze, ohne Distanz-
        Schranke). Beide bedienen verschiedene Auspraegungen derselben
        geografischen Such-Achse - die Disk antwortet auf 'wer ist nah
        genug?', die K-NN-Variante auf 'wer sind die nahesten N?'.

        Typische Anwendung: der Sammler steht an einer Lokalitaet und
        will die N nahesten Stuecke aus seinem Bestand zum Vergleich
        bestimmen, ohne im Voraus zu wissen, welcher Radius die richtige
        Trefferzahl liefert (Disk-Suche erfordert vorab eine Distanz-
        Schaetzung, K-NN nicht).

        Reuse-Pfad zu ``list_objects_in_radius``: SELECT Fundort fuer
        alle Objekte mit nicht-leerem Fundort, ``parse_coordinates`` auf
        jeden Wert, Haversine-Distanz auf einer Erd-Sphaere mit Radius
        6371.0 km. Anschliessend Sortierung aufsteigend nach Distanz
        und Slice auf ``limit``. Fundort-Eintraege ohne erkennbare
        Koordinaten (reine Ortsnamen) werden uebergangen - sie laufen
        ueber ``list_objects_ohne_koordinaten`` auf der Pflege-Achse.

        Rueckgabe als ``(obj_id, lat, lon, distance_km)``-Tupel - die
        Distanz wird durchgereicht, damit der Caller die Trefferliste
        sortieren oder anzeigen kann ohne erneuten Haversine-Aufruf.
        Sekundaersortierung nach ``obj_id`` fuer deterministische
        Ausgabe bei Distanz-Bindungen (zwei Stuecke aus exakt derselben
        Lokalitaet haben identische Distanz).

        ``limit`` <= 0 liefert eine leere Trefferliste (semantisch
        leere K-NN-Anfrage); ``limit`` > Anzahl geocoded-er Stuecke
        liefert alle verfuegbaren Stuecke (keine Polsterung mit
        Platzhaltern, keine Ausnahme).
        """
        if limit <= 0:
            return []
        candidates = self._list_objects_haversine(lat_center, lon_center)
        candidates.sort(key=lambda r: (r[3], r[0]))
        return candidates[:limit]

    def list_objects_farthest(self, lat_center: float, lon_center: float,
                              limit: int
                              ) -> list[tuple[str, float, float, float]]:
        """Listet die ``limit`` Objekte mit Fundort-Koordinaten am weitesten weg vom Mittelpunkt.

        K-Farthest-Neighbors-Pendant zu ``list_objects_nearest``:
        waehrend die K-NN-Variante die spiegelbildliche Frage 'welche
        sind die N nahesten Stuecke zu meinem Standort?' beantwortet
        (Naehe-Achse), beantwortet die K-FN-Variante die Extrem-Achse
        'welche sind die N weitesten Stuecke?' - typischerweise die
        Ausreisser der Sammlung (das eine Souvenir-Stueck aus Namibia
        in einer sonst Schweizer Sammlung, die Fern-Reise-Beute in
        einer sonst regional gepflegten Sammlung). Beide K-Extrema-
        Suchen bedienen verschiedene Auspraegungen derselben
        geografischen Such-Achse - Naehe und Ferne sind die beiden
        Rand-Extreme derselben Distanz-Verteilung.

        Typische Anwendung: der Sammler will die N weitesten Stuecke
        aus seinem Bestand identifizieren, ohne im Voraus zu wissen,
        welcher Radius die richtige Trefferzahl liefert (Disk-Suche
        erfordert vorab eine Distanz-Schaetzung, K-FN nicht). Auch
        als Ausreisser-Detektor: die Distanz des N-t weitesten
        Stuecks im Vergleich zu ``koordinaten_radius_durchschnitt_km``
        beziffert, wie stark die Sammlungs-Streuung von diesen
        Extrem-Punkten getrieben wird.

        Reuse-Pfad: teilt ``_list_objects_haversine`` mit
        ``list_objects_nearest`` (dieselbe Haversine-Distanz-Runde,
        derselbe Erdradius 6371.0 km, dasselbe parse_coordinates-
        Filter fuer Ortsname/leere-Fundort-Eintraege), unterscheidet
        sich nur in der Sortier-Richtung (absteigend statt aufsteigend
        nach Distanz). Fundort-Eintraege ohne erkennbare Koordinaten
        (reine Ortsnamen) werden uebergangen - sie laufen ueber
        ``list_objects_ohne_koordinaten`` auf der Pflege-Achse.

        Rueckgabe als ``(obj_id, lat, lon, distance_km)``-Tupel - die
        Distanz wird durchgereicht, damit der Caller die Trefferliste
        sortieren oder anzeigen kann ohne erneuten Haversine-Aufruf.
        Sekundaersortierung nach ``obj_id`` (aufsteigend) fuer
        deterministische Ausgabe bei Distanz-Bindungen (zwei Stuecke
        aus exakt derselben fernen Lokalitaet haben identische
        Distanz - spiegelt die K-NN-Konvention).

        ``limit`` <= 0 liefert eine leere Trefferliste (semantisch
        leere K-FN-Anfrage, spiegelt K-NN); ``limit`` > Anzahl
        geocoded-er Stuecke liefert alle verfuegbaren Stuecke (keine
        Polsterung, keine Ausnahme).
        """
        if limit <= 0:
            return []
        candidates = self._list_objects_haversine(lat_center, lon_center)
        candidates.sort(key=lambda r: (-r[3], r[0]))
        return candidates[:limit]

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

    def merge_nonempty(self, obj_id: str, fields: dict,
                       *, dry_run: bool = False) -> list[str]:
        """Setzt nur nicht-leere Werte; gibt Liste der Konfliktfelder zurück (vorhandener Wert != neuer Wert).

        ``dry_run=True`` unterdrueckt das ``update_fields``-Schreiben; die
        Konflikt-Erkennung laeuft unveraendert, sodass ein Aufrufer die
        Merge-Wirkung ohne Datenaenderung inspizieren kann (siehe
        :func:`stonebook.export.csv_export.import_csv` mit ``dry_run=True``).
        """
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
        if updates and not dry_run:
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

    def get(self, image_id: int) -> sqlite3.Row | None:
        """Liest einen Bild-Eintrag per Primaerschluessel.

        Spiegelt :meth:`AnalysisRepo.get` auf die Bild-Tabelle - Gallery-Editor
        und :meth:`delete` brauchen die Roh-Zeile (kategorie, rel_path,
        herkunft_obj_id), bevor sie auf einzelne Bilder zugreifen koennen.
        """
        return self.conn.execute(
            "SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()

    def delete(self, image_id: int) -> bool:
        """Loescht einen einzelnen Bild-Eintrag; gibt True bei Erfolg zurueck.

        Spiegelt :meth:`AnalysisRepo.delete` exakt auf die Bild-Tabelle: der
        Galerie-Editor entfernt damit verstreute Fehl-Uploads (falsche Kategorie,
        falsches Objekt) auf der Index-Ebene, ohne die Datei auf der Platte
        anzufassen - das bleibt callerseitig (der Index ist primaer, die
        Datei sekundaer; Re-Index baut den Eintrag bei Bedarf neu auf).
        Idempotent: zweiter Aufruf mit derselben ID liefert False.
        """
        cur = self.conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        self.conn.commit()
        return cur.rowcount > 0

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

    def delete(self, alias_id: str) -> bool:
        """Entfernt einen Alias-Eintrag; gibt True bei Erfolg zurueck.

        Spiegelt :meth:`ImageRepo.delete` / :meth:`AnalysisRepo.delete` auf die
        Alias-Tabelle: noetig fuer Korrekturen einer Fehl-Merge-Operation
        (versehentlich eingetragene historische ID, falsche Duplikat-Gruppe).
        Die Funktion entfernt nur den Mapping-Eintrag selbst; weder das Kanon-
        Objekt noch die schon umgehaengten Bilder/KI-Analysen werden zurueck-
        gerollt - der Restore eines geloeschten Member-Objekts ist nur ueber
        Backup moeglich (siehe :func:`stonebook.export.json_export.import_json`).
        Idempotent: zweiter Aufruf mit derselben ID liefert False.
        """
        cur = self.conn.execute("DELETE FROM aliases WHERE alias_id = ?", (alias_id,))
        self.conn.commit()
        return cur.rowcount > 0

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

    def reassign(self, from_obj: str, to_obj: str) -> int:
        """Haengt alle KI-Analysen von ``from_obj`` auf ``to_obj`` um.

        Wird beim Merge zweier Objekte in :func:`stonebook.db.merge.
        merge_into_canonical` gerufen, damit die Analyse-Historie des Members
        nicht via ON DELETE CASCADE verloren geht (Member wird nach dem Merge
        geloescht). Spiegelt :meth:`ImageRepo.reassign` exakt auf die parallele
        FK-Tabelle. Gibt die Zahl umgehaengter Zeilen zurueck (0 wenn ``from_obj``
        keine Analysen hatte).
        """
        cur = self.conn.execute(
            "UPDATE ki_analysen SET obj_id = ? WHERE obj_id = ?",
            (to_obj, from_obj))
        self.conn.commit()
        return cur.rowcount

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

    def count(self) -> int:
        """Gesamtzahl aller KI-Analysen ueber alle Objekte.

        Spiegelt :meth:`ImageRepo.count` / :meth:`AliasRepo.count` auf die
        KI-Analyse-Tabelle - die drei abhaengigen Tabellen haben damit eine
        einheitliche Gesamtzaehler-API (ki_analysen_total in der Statistik
        verwendet dieselbe Aggregation). Komplementaer zu :meth:`count_for`
        (pro Objekt) als batch-Gegenstueck zur per-Objekt-Sicht.
        """
        return self.conn.execute("SELECT COUNT(*) FROM ki_analysen").fetchone()[0]

    def prune_all(self, keep: int) -> int:
        """Behaelt nur die ``keep`` neuesten Analysen je Objekt ueber alle Objekte.

        Spiegelt :meth:`prune` auf den Gesamtbestand: statt fuer ein einzelnes
        ``obj_id`` aufzuraeumen, laeuft die gleiche Vorhalte-Regel ueber alle
        Objekte mit KI-Analysen. Gibt die Gesamtzahl tatsaechlich geloeschter
        Zeilen zurueck. Typische Wartung nach Massen-Re-Analyse oder vor einem
        Voll-Backup, wenn die Analyse-Historie pro Objekt auf eine handhabbare
        Tiefe begrenzt werden soll. ``keep < 0`` wirft ``ValueError`` (spiegelt
        :meth:`prune`); ``keep == 0`` loescht alle Analysen ueber alle Objekte.
        """
        if keep < 0:
            raise ValueError("keep muss >= 0 sein")
        cur = self.conn.execute(
            "DELETE FROM ki_analysen WHERE id IN ("
            " SELECT id FROM ("
            "  SELECT id, ROW_NUMBER() OVER ("
            "   PARTITION BY obj_id ORDER BY zeitpunkt DESC, id DESC) AS rn"
            "  FROM ki_analysen) WHERE rn > ?)",
            (keep,))
        self.conn.commit()
        return cur.rowcount
