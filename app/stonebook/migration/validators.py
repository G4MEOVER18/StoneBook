"""Eingabe-Validatoren für Felder mit freiem Textformat (Funddatum, Koordinaten)."""
from __future__ import annotations

import datetime
import re
import unicodedata

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y%m%d",   # ISO 8601 compact YYYYMMDD (Dateinamen, Logs)
    "%Y:%m:%d",  # EXIF DateTime ohne Zeit-Suffix (stripped Camera-Stempel)
    # US-Datumsformat "MM/DD/YYYY" / "MM-DD-YYYY" / "MM.DD.YYYY" als Fallback
    # NACH den DE/EU-Varianten - dadurch behalten mehrdeutige Eingaben wie
    # "01/02/2024" ihre bestehende DE-Interpretation (2024-02-01, Tag 1 im
    # Februar), waehrend eindeutige US-Formen "06/13/2024" (Tag 13 waere in
    # DE-Interpretation ungueltiger Monat 13) den Fallback treffen und
    # korrekt als 2024-06-13 (Juni 13) aufgeloest werden. Bisher fielen alle
    # US-Formen mit Tag > 12 stille auf None - typisch in Sammlungs-Notizen
    # aus englischsprachigen Quellen (Auktions-Kataloge, US-Mineral-Boersen,
    # Foto-Captions mit MDN-Datetime aus amerikanischen Kameras), die den
    # DE-Fallback nicht durchlaufen. EN/US-Ausgangs-CSVs aus Excel schreiben
    # per Default MM/DD/YYYY (locale-abhaengig) - der Fallback macht diese
    # Datensaetze re-importierbar, ohne die deutschen Bestands-Daten zu
    # veraendern (der Loop stoppt beim ersten erfolgreichen Match, sodass
    # DE/EU eindeutig Vorrang behaelt). Bindestrich- und Punkt-Variante
    # symmetrisch zu den DE-Formen, damit "06-13-2024" und "06.13.2024"
    # gleich behandelt werden wie "06/13/2024".
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m.%d.%Y",
)

# Explizite "keine Angabe"-Marker, die parse_iso_date wie Leer behandelt (None).
# Ausgelagert als Modul-Konstante, damit ein Consumer (:mod:`csv_loaders`,
# :func:`find_rows_with_invalid_funddatum`) einen semantisch leeren Marker
# ("k.a.", "n/a", "unbekannt") von einer echten Fehl-Eingabe ("Sommer 84",
# "32.13.2024") unterscheiden kann, ohne die Marker-Menge zu duplizieren -
# beide Faelle liefern parse_iso_date == None, aber nur die zweite ist ein
# silent-data-loss-Fund, den der Import-Report sichtbar machen soll (der
# User hat einen Wert getippt, der Parser konnte ihn nicht mappen). Die
# Marker-Semantik ist "User sagt explizit: kein Datum", da ist nichts
# verloren gegangen.
DATE_NO_DATA_MARKERS: frozenset[str] = frozenset(
    {
        "k.a.", "k. a.", "n/a", "na", "?", "-", "—", "unbekannt",
        # ``n.a.`` / ``n. a.`` symmetrisch zu ``k.a.`` / ``k. a.``: dieselbe
        # DE-Abkuerzungs-Konvention (Punkt statt Slash), die in Sammler-Notizen
        # und Auktions-Etiketten neben der Slash-Variante ``n/a`` auftaucht,
        # ohne dass parse_iso_date bisher den Marker-Status erkannt haette.
        "n.a.", "n. a.",
        # En-Dash (U+2013) sitzt zwischen ASCII-Hyphen ``-`` und Em-Dash (U+2014,
        # ``—``, bereits in der Menge). Word/Outlook/LibreOffice-AutoFormat
        # ersetzen ``-`` in isolierten Zell-Positionen typischerweise durch
        # U+2013, nicht U+2014 - ohne den En-Dash-Marker fiel diese Auto-Format-
        # Variante als "invalid" statt "no data" in den silent-data-loss-Report.
        "–",
        # Mehrfach-Fragezeichen: verstaerkte Unsicherheits-Marker ("wirklich
        # keine Ahnung"), semantisch identisch zum bereits enthaltenen ``?``.
        "??", "???",
        # Englische Aequivalente zu ``unbekannt`` und ``keine Angabe``:
        # US-/UK-Auktions-Kataloge und englischsprachige Sammler-Notizen
        # verwenden ``unknown`` / ``no data`` / ``no date`` / ``none`` als
        # Standard-Marker fuer "kein Datum verfuegbar".
        "unknown", "no data", "no date", "none",
        # Ausgeschriebene DE-Formen: der User tippt statt der Abkuerzung den
        # vollen Satz. ``keine angabe`` ist die kanonische Langform von ``k.a.``,
        # ``keine daten`` / ``kein datum`` sind natuerlich-sprachliche
        # Varianten, die dieselbe Semantik tragen.
        "keine angabe", "keine daten", "kein datum",
        # Weitere DE-Datum-spezifische Marker, die in Museums-Etiketten und
        # geerbten Sammler-Katalogen als Standard-Konvention fuer "Fund-Datum
        # nicht ermittelbar" auftreten. Spiegelt die etablierten Datum-spezifi-
        # schen Prosa- und Katalog-Formen der uebrigen Sprachen auf die DE-
        # Achse: ``undatiert`` (kompakte Adjektiv-Form, DE-Katalog-Standard fuer
        # "ohne Datum-Angabe", verbreitet in Naturhistorischen Museen und
        # Mineralien-Sammlungs-Etiketten), ``nicht datiert`` (natuerlich-
        # sprachliche Prosa-Form, parallel zu ``kein datum``), ``ohne datum``
        # (DE-Katalog-Konvention symmetrisch zur FR ``sans date`` / IT ``senza
        # data`` / ES ``sin fecha`` / PT ``sem data``) und ``datum unbekannt``
        # (invertierte DE-Prosa-Form, parallel zur FR ``date inconnue`` / ES
        # ``fecha desconocida`` / PT ``data desconhecida``). Bisher fielen
        # DE-Bestaende mit diesen expliziten Markern in den silent-data-loss-
        # Report als "invalid Datum, bitte pruefen", obwohl der User semantisch
        # bewusst "kein Datum verfuegbar" markiert hatte. Kollisionsfreiheit
        # zu gueltigen Datums-Formen: keine der Marker enthaelt Ziffern oder
        # Datums-Trenner, sodass gueltige DE-Eingaben ("13. Juni 2024",
        # "Juni undatiert" - solche Mischformen kommen nicht vor) unveraendert
        # durchlaufen. Alle Marker sind lowercase (Consumer .lower()t den
        # Input vor dem Check, wie im Bestand konventionalisiert).
        "undatiert", "nicht datiert", "ohne datum", "datum unbekannt",
        # Franzoesische Aequivalente (Suisse romande - Wallis/Waadt/Genf/
        # Neuenburg/Freiburg, ~23% Bevoelkerungsanteil laut BFS) sowie geerbte
        # Sammler-Notizen und Auktions-Etiketten aus franzoesisch-sprachigen
        # Alpen-Fundorten (Val d'Anniviers, Chamonix, Mont-Blanc-Massiv) und
        # aus Museum-Etiketten mit FR-Provenienz. ``inconnu``/``inconnue``
        # (mask./fem. Form von "unbekannt"), ``sans date`` (Standard-Katalog-
        # Konvention fuer "ohne Datum", identisch zur ISBD/AACR2-Bibliothekars-
        # Notation), ``date inconnue`` (invertierte Standard-Prosa-Form),
        # ``pas de date`` (natuerlichsprachige "kein Datum"-Form). Spiegelt
        # die FR-Erweiterungen in :data:`_MONTH_NAMES` (janvier..decembre),
        # :data:`_SEASON_MONTHS` (printemps/ete/automne/hiver),
        # :data:`_DIRECTION_WORD` (est/ouest), :data:`_APPROX_PREFIX`
        # (vers/environ) und :data:`_TEMPORAL_PREFIX` (en/an/annee) auf die
        # No-Data-Marker-Achse.
        "inconnu", "inconnue", "sans date", "date inconnue", "pas de date",
        # Italienische Aequivalente (Ticino / italienische Schweiz sowie
        # geerbte Sammler-Notizen aus italienisch-sprachigen Alpen-/Dolomiten-
        # Fundorten, Val d'Aosta und Museo cantonale di storia naturale in
        # Lugano). ``sconosciuto``/``sconosciuta`` (mask./fem. Form von
        # "unbekannt"), ``ignoto``/``ignota`` (mask./fem. Form von "unbekannt/
        # nicht identifiziert", in wissenschaftlichen IT-Publikationen die
        # praeferierte Form), ``senza data`` (Standard-Katalog-Konvention fuer
        # "ohne Datum"). Spiegelt die IT-Erweiterungen in :data:`_MONTH_NAMES`
        # (gennaio..dicembre), :data:`_SEASON_MONTHS` (primavera/estate/
        # autunno/inverno), :data:`_DIRECTION_WORD` (est/ovest) und
        # :data:`_APPROX_PREFIX` (verso/attorno) auf die No-Data-Marker-Achse.
        "sconosciuto", "sconosciuta", "ignoto", "ignota", "senza data",
        # Spanische Aequivalente (Sammler-Region Andalusien mit Almeria/
        # Sierra Almagrera/Rodalquilar/Riotinto sowie La Union Murcia,
        # lateinamerikanische Fundstellen Cerro Rico Potosi/Chuquicamata/
        # La Rinconada) sowie geerbte Etiketten von ES-sprachigen
        # Auktions-/Museums-Anbietern (Fabre Minerals Barcelona, Museo
        # Nacional de Ciencias Naturales Madrid). ``desconocido``/
        # ``desconocida`` (mask./fem. Form von "unbekannt"), ``sin fecha``
        # (Standard-Katalog-Konvention "ohne Datum"), ``fecha desconocida``
        # (invertierte Prosa-Form). Spiegelt die ES-Erweiterungen in
        # :data:`_MONTH_NAMES` (enero..diciembre, commit 652ac1a),
        # :data:`_SEASON_MONTHS` (primavera/verano/otono/invierno, commit
        # 69e71b6) und :data:`_DIRECTION_WORD` (norte/sur/este/oeste,
        # commit f9804bd) auf die No-Data-Marker-Achse und schliesst damit
        # die ES-Achse aller vier parse-relevanten Vollnamen-Kategorien.
        "desconocido", "desconocida", "sin fecha", "fecha desconocida",
        # Portugiesische Aequivalente (Panasqueira/Beira Baixa fuer
        # Wolframit-/Quarz-Adern, brasilianische Pegmatit-Region Minas
        # Gerais/Bahia mit Turmalin/Topas/Aquamarin/Beryll) sowie geerbte
        # PT-BR-Sammler-/Auktions-/Museums-Notizen (Museu Nacional de
        # Historia Natural Lissabon). ``desconhecido``/``desconhecida``
        # (mask./fem. Form von "unbekannt"), ``sem data`` (Standard-
        # Katalog-Konvention "ohne Datum"), ``data desconhecida``
        # (invertierte Prosa-Form). Spiegelt die PT-Erweiterungen in
        # :data:`_MONTH_NAMES` (janeiro..dezembro, commit 87eb2cd) und
        # :data:`_SEASON_MONTHS` (verao/outono/primavera/inverno, commit
        # 4c3ce4f) auf die No-Data-Marker-Achse.
        "desconhecido", "desconhecida", "sem data", "data desconhecida",
        # Wissenschaftliche Bibliografie-/Katalogisierungs-Konventionen:
        # ``n.d.`` (englisch "no date" / lateinisch "non datum") ist die
        # ISBD/AACR2/RDA-Bibliothekars-Standard-Abkuerzung fuer "kein Datum
        # ermittelbar" und in Auktions-Katalogen, Museumskatalogen, wissen-
        # schaftlichen Publikationen und Reference-Listen die kanonische
        # No-Date-Notation. ``s.d.`` (lateinisch "sine die" / italienisch
        # "senza data" / franzoesisch "sans date") ist das kontinental-
        # europaeische Gegenstueck, das in FR-/IT-/DE-katalogisiertem Bestand
        # (Museum-Etiketten, Mineralien-Auktions-Kataloge Christie's/Bonhams
        # /Sotheby's) neben ``n.d.`` gebraeuchlich ist. Beide sind in Sammler-
        # Notizen aus geerbten Bestaenden mit publiziertem Provenienz-Weg
        # (ehemals Museum, ehemals Auktion) haeufig - der Sammler uebernimmt
        # die katalogisierte Notation unveraendert. Punkt-Form (``n.d.``) und
        # Punkt-Whitespace-Form (``n. d.``) parallel zu ``k.a.``/``k. a.`` /
        # ``n.a.``/``n. a.``.
        "n.d.", "n. d.", "s.d.", "s. d.",
    }
)

_YEAR_ONLY = re.compile(r"^\s*(\d{4})\s*$")
# Jahrzehnt-Notation ("1980er", "1980s", "1980er Jahre", "1980-er").
# Konvention: Dekaden-Start = Jahr selbst (1980er → 1980-01-01). Reichweite-Annotation
# bleibt im Freitext (notizen). Zweistellige Kurzform "80er" ist mehrdeutig
# (1880er vs 1980er) und wird bewusst nicht aufgeloest -- liefert None.
# ``jahre(?:n)?`` deckt zusaetzlich zur Nominativ-/Akkusativ-Form ``Jahre``
# auch die Dativ-Plural-Form ``Jahren`` ab, die in praepositionalen Wendungen
# der Standard-Form entspricht: ``in den 1980er Jahren``, ``aus den 1990er
# Jahren``, ``waehrend der 2000er Jahren``. Ohne das ``n``-Suffix fiel diese
# haeufigste DE-Print-/Buch-Form still auf None, obwohl semantisch identisch
# zur Nominativ-Variante ``1980er Jahre`` (Konvention: Dekaden-Start). Wird
# nach _TEMPORAL_PREFIX geparst - ``in den 1980er Jahren`` strippt zuerst
# ``in den `` via _TEMPORAL_PREFIX-Praeposition-plus-Artikel und uebergibt
# ``1980er Jahren`` an _DECADE zur Auswertung.
#
# Suffix-Alternante ``(?:ern|er|s)`` deckt zusaetzlich die substantivierte
# Dativ-Plural-Form ``1980ern`` ab, die in praepositionalen Wendungen ohne
# expliziten ``Jahre``-Trailer die uebliche DE-Kurzform ist ("in den 1980ern",
# "aus den 1990ern", "seit den 2000ern"). Ohne den ``ern``-Zweig fielen diese
# haeufigen DE-Formen still auf None, obwohl semantisch identisch zur langen
# Form ``1980er Jahren`` und zur artikellosen Nominativ-Form ``1980er``.
# Konvention: Dekaden-Start (spiegelt die uebrigen Formen). Die ``ern``-Endung
# ist mehr als "er + n" - grammatikalisch ist ``1980ern`` die Dativ-Plural-
# Form des substantivierten Adjektivs ``die 1980er`` mit dem Dativ-Plural-
# Suffix -n (Standard-DE-Deklination: Nominativ Plural -e -> Dativ Plural
# -en; hier auf die substantivierte Form der Dekaden-Notation appliziert).
# In der Regex-Alternante muss ``ern`` VOR ``er`` stehen, damit fuer den
# String ``1980ern`` zuerst die spezifische Dativ-Plural-Form getroffen wird
# statt der kuerzeren ``er`` mit uebrig gelassenem ``n`` (das dann via
# ``\s*$`` fehl-matcht und die Dativ-Form still auf None fallen laesst).
# ``[\- ]?`` vor der Alternante bleibt symmetrisch zu den anderen Suffixen
# (``1980-ern``, ``1980 ern`` sind selten aber spec-konform); nach dem
# Suffix darf optional ``jahre(?:n)?`` folgen (redundant zur substantivierten
# Form aber unschaedlich, spiegelt die uebrigen Suffix-Zweige).
#
# Trenner zwischen ``er``/``ern``/``s`` und dem optionalen ``jahre(?:n)?``-
# Trailer als ``[-\s]+`` deckt auch die hyphenierte Kompositum-Form
# ``1980er-Jahre`` / ``1980er-Jahren`` ab, die neben der artikellosen
# Standard-Form ``1980er Jahre`` als offizielle Duden-alternative Schreibweise
# gilt (Zusammenschreibung der aus Ziffer + er-Suffix + Substantiv
# gebildeten Zeit-Bezeichnung). In DE-Publikationen und Sammler-Notizen
# sehr verbreitet ("die 1980er-Jahre", "in den 1990er-Jahren", "spaete
# 2000er-Jahre") - vor der Erweiterung fielen alle Bindestrich-Kompositum-
# Formen still auf None, weil der Trenner obligatorisches Whitespace
# verlangte. Semantisch identisch zur getrennten Schreibweise (Konvention:
# Dekaden-Start). Der Zeichenklasse ``[-\s]+`` erlaubt beliebige Kombina-
# tionen aus Bindestrich(en) und Whitespace, sodass auch die zusammen-
# gesetzte Form ``1980-er-Jahre`` (Bindestrich sowohl vor dem er-Suffix
# als auch vor dem Jahre-Trailer, seltene aber vorkommende typografische
# Praxis in Print-Katalogen) aufgeloest wird.
_DECADE = re.compile(
    r"^\s*(\d{4})(?:[\- ]?(?:ern|er|s))(?:[-\s]+jahren?)?\s*$",
    re.IGNORECASE,
)
# Dekaden-Spanne ("1980er-1990er", "1980s-1990s", "1980er - 1990er",
# "1980er/1990er", "1980er–1990er", "1980er bis 1990er", "1980s to 1990s",
# "1980er-Jahre - 1990er-Jahre") - spiegelt _YEAR_RANGE / _YEAR_RANGE_WORD auf
# die Dekaden-Achse. In geerbten Sammler-/Museums-Notizen sehr verbreitet,
# wenn der Vorbesitzer den Erwerbs-/Fund-Zeitraum nur ungefaehr auf zwei
# aufeinanderfolgende Dekaden datieren konnte ("Erwerb 1980er-1990er",
# "Sammlungsaufbau 1980s to 2000s"). Ohne dedizierte Spanne-Erkennung fielen
# alle Formen stille auf None, weil _DECADE ein einzelnes Jahrzehnt verlangt
# und _YEAR_RANGE zwei reine 4-Ziffer-Anker ohne er/s-Suffix erwartet - ein
# stiller Datenverlust auf einer sehr typischen Erbschafts-/Import-Notation.
#
# Konvention identisch zu _YEAR_RANGE / _YEAR_RANGE_WORD / _DECADE: Startjahr
# der linken Dekade als ISO-Datum (1980er-1990er -> 1980-01-01), die Range-
# Annotation bleibt im Freitext (notizen). Inverted Spanne ("1990er-1980er",
# Tippfehler) liefert die linke Dekade, spiegelt _YEAR_RANGE-Konvention.
#
# Beide Enden erlauben die vollen Dekaden-Suffix-Alternanten aus _DECADE
# (ern/er/s) samt optionalem [\-\s]?-Trenner vor dem Suffix ("1980-er"-Form)
# und dem optionalen [-\s]+jahren?-Trailer ("1980er Jahre", "1980er-Jahre",
# "1980er Jahren") - Mischformen wie "1980er-1990s" oder "1980s bis 1990er"
# werden toleriert (in Sammler-Notizen kommen DE-/EN-Suffixe gemischt vor).
#
# Symbolischer Separator [-–—−/] deckt ASCII-Bindestrich, En-Dash (U+2013),
# Em-Dash (U+2014), Minus-Zeichen (U+2212) und Slash (Tagebuch-Notation) ab -
# identisch zur _YEAR_RANGE-Separator-Klasse. Wort-Separator (bis/to/till/
# until) verlangt Whitespace links und rechts, spiegelt _YEAR_RANGE_WORD;
# ohne Whitespace ("1980erbis1990er") kein Match, weil die Wort-Form von der
# natuerlichen Satzform lebt.
#
# Vor _DECADE geprueft, damit die Spanne-Form (die ein einzelnes Dekaden-
# Pattern strukturell enthaelt) nicht vom base _DECADE geblockt wird.
# Kollisionsfrei zu _YEAR_RANGE (dort keine er/s-Suffixe) und zu _RELATIVE_
# DECADE (dort obligatorischer Anfang/Mitte/Ende-Praefix).
_DECADE_RANGE = re.compile(
    r"^\s*(\d{4})(?:[\- ]?(?:ern|er|s))(?:[-\s]+jahren?)?"
    r"(?:\s*[-–—−/]\s*|\s+(?:bis|to|till|until)\s+)"
    r"(\d{4})(?:[\- ]?(?:ern|er|s))(?:[-\s]+jahren?)?\s*$",
    re.IGNORECASE,
)
# Mehrjahres-Spanne ("1950-1960", "1950–1960", "1950/1960", "1950 - 1960") -
# verbreitet in geerbten Sammlungs-Notizen mit unsicherem Funddatum, wenn der
# vorherige Besitzer den Fund nicht genauer datieren konnte ("zwischen 1950
# und 1960" als Range-Notation). Konvention: Startjahr als ISO-Datum (Spanne-
# Start), spiegelt die Dekaden-Konvention (1980er → 1980-01-01 = Dekaden-
# Start) - die Range-Annotation bleibt im Freitext (notizen). Sowohl ASCII-
# Bindestrich als auch En-Dash (U+2013), Em-Dash (U+2014) und Minus-Zeichen
# (U+2212) als typografische Spanne-Notation werden akzeptiert; Slash als
# Alternativ-Separator deckt "1950/1960"-Varianten ab (kommt in Tagebuechern
# mit Schraegstrich-Trenner vor). Em-Dash setzt Word-Autoformat in deutschen
# Texten oft fuer "von-bis"-Spannen ("1950—1960"), das Minus-Zeichen kommt in
# typografisch sauber gesetzten Print-Katalogen und LaTeX-Exporten vor, wo
# der Setzer das mathematische Minus (statt ASCII-Hyphen) verwendet.
# Beide Jahre muessen in [1800, 2999] liegen; inverted Spanne ("1985-1980",
# Tippfehler) liefert das erste Jahr, spiegelt das parse_range-Verhalten auf
# die Jahres-Achse.
# Vor _YEAR_MONTH geprueft, damit "1950-12" weiterhin als YYYY-MM gilt (zwei
# 4-Ziffer-Anker schliessen das aus: Monat-Form hat 1-2 Ziffern im zweiten
# Teil); kollisionsfrei zu _MONTH_NUMERIC_YEAR (1-2 + 4 Ziffern).
_YEAR_RANGE = re.compile(r"^\s*(\d{4})\s*[-–—−/]\s*(\d{4})\s*$")
# Wort-Form der Mehrjahres-Spanne ("1950 bis 1960", "1950 to 1960",
# "1950 till 1960", "1950 until 1960") - spiegelt _YEAR_RANGE auf die
# Wort-Variante des Range-Separators. In geerbten Sammlungs-Notizen oft
# in vollstaendigen Saetzen geschrieben ("Fund 1950 bis 1960 im Aaregebiet")
# statt mit Bindestrich/Slash; ohne Wort-Form fiele die Eingabe stille auf
# None. Konvention identisch zum symbolischen _YEAR_RANGE: Startjahr als
# ISO-Datum (Spanne-Start), inverted Spanne ("1985 bis 1980", Tippfehler)
# liefert das erste Jahr. Mindestens ein Whitespace links und rechts vom
# Schluesselwort, damit "1950bis1960" (extrem unkonventionell, keine
# Lese-Tradition in Sammler-Notizen) kein Match wird; die Wort-Form lebt
# von der natuerlichen Satzform. Wird vor _MONTH_NUMERIC_YEAR geprueft (das
# auf "(1-2 Ziffern) Separator (4 Ziffern)" matched) und vor _YEAR_MONTH
# (das auf "(4 Ziffern) Separator (1-2 Ziffern)" matched) - kollisionsfrei,
# weil beide Jahre hier 4 Ziffern haben.
_YEAR_RANGE_WORD = re.compile(
    r"^\s*(\d{4})\s+(?:bis|to|till|until|through|thru)\s+(\d{4})\s*$",
    re.IGNORECASE,
)
# Umschliessende Range-Form "zwischen X und Y" / "between X and Y" - spiegelt
# _YEAR_RANGE_WORD auf die bilaterale Konjunktions-Notation. In geerbten
# Sammlungs-Notizen die haeufigste Form, wenn der Vorbesitzer den Fund-Zeitraum
# nicht praezise datieren konnte, aber die grobe Spanne angeben wollte
# ("zwischen 1985 und 1990 im Aaregebiet gefunden", "between 1950 and 1960
# purchased from a Swiss dealer") - ohne Match fielen alle Formen still auf
# None, obwohl beide Jahre eindeutig lesbar sind. Konvention identisch zu
# _YEAR_RANGE / _YEAR_RANGE_WORD: Startjahr als ISO-Datum (Spanne-Start),
# inverted Spanne ("zwischen 1990 und 1985", Tippfehler) liefert das erste
# Jahr. Mindestens ein Whitespace jeweils rund um "zwischen"/"between" und
# um "und"/"and", damit "zwischen1985und1990" (extrem unkonventionell) kein
# Match wird; die Wort-Form lebt von der natuerlichen Satzform. Kollisionsfrei
# zu _YEAR_RANGE_WORD (der beginnt mit vier Ziffern, hier beginnt der Match
# mit "zwischen"/"between") und zu allen anderen Datumsformen (keine andere
# Form beginnt mit "zwischen"/"between").
_YEAR_RANGE_BETWEEN = re.compile(
    r"^\s*(?:zwischen|between)\s+(\d{4})\s+(?:und|and)\s+(\d{4})\s*$",
    re.IGNORECASE,
)
# Generischer "zwischen X und Y" / "between X and Y"-Wrapper fuer beliebige
# Range-Inhalte (nicht nur reine Jahre wie :data:`_YEAR_RANGE_BETWEEN`). In
# geerbten Sammlungs-Notizen und Museums-Etiketten fuegt der Vorbesitzer die
# ``zwischen ... und ...``-Konstruktion vor beliebige Datums-Spannen ein:
# ``zwischen Juni und Juli 2024`` (Monat-Spanne), ``zwischen 13. und 15. Juni
# 2024`` (Tages-Spanne innerhalb eines Monats), ``zwischen 13. Juni und
# 15. Juli 2024`` (Cross-Month-Tages-Spanne), ``zwischen Sommer und Herbst
# 2024`` (Saison-Spanne), ``zwischen 1980er und 1990er`` (Dekaden-Spanne).
# Bisher fielen alle diese Formen still auf None, weil :data:`_YEAR_RANGE_
# BETWEEN` nur reine 4-Ziffer-Jahres-Spannen matcht und keiner der uebrigen
# Range-Patterns (:data:`_MONTH_RANGE_YEAR`, :data:`_DAY_RANGE_MONTH_YEAR`,
# :data:`_SEASON_RANGE`, :data:`_DECADE_RANGE`, :data:`_CENTURY_RANGE_*`) die
# ``zwischen ... und ...``-Umschliessung kennt - aus einem typischen Etikett
# wie "zwischen Juni und Juli 2024 gefunden" oder "zwischen 13. und 15. Juni
# 2024 am Aaregebiet" entstand damit silenter Funddatum-Datenverlust bei der
# Migration.
#
# Fix normalisiert die Wrapper-Form auf die generische ``X - Y``-Range-
# Notation, sodass alle bestehenden Range-Patterns transparent greifen:
# ``zwischen Juni und Juli 2024`` -> ``Juni - Juli 2024`` -> :data:`_MONTH_
# RANGE_YEAR` -> ``2024-06-01``. Der Preprocessor wird nach allen anderen
# Praefix-Strippern (:data:`_APPROX_PREFIX`, :data:`_WEEKDAY_PREFIX`,
# :data:`_TEMPORAL_PREFIX`, :data:`_BOUNDARY_PREFIX`, :data:`_RANGE_PREFIX`)
# und *vor* allen Pattern-Match-Zweigen eingesetzt, sodass die Kombination
# mit Praefixen ("ca. zwischen Juni und Juli 2024" -> "zwischen Juni und
# Juli 2024" -> "Juni - Juli 2024" -> "2024-06-01") transparent via Rekursion
# aufloest.
#
# Lazy-Match ``.+?`` auf beiden Seiten mit End-Anker ``\s*$`` erzwingt die
# minimale Left-Aufteilung: bei mehreren ``und``/``and``-Vorkommen fasst die
# Regex die rechte Seite maximal (Whitespace + und/and + Whitespace ist der
# Split-Punkt, alles danach ist die rechte Seite). Fuer "zwischen 3. und
# 5. April und 15. Mai 2024" (semantisch unklarer Kompositum-Wrapper) wird
# left="3." und right="5. April und 15. Mai 2024" - der resultierende "3.
# - 5. April und 15. Mai 2024" matcht kein Range-Pattern und liefert None
# (kein Regress, weil das Original auch None geliefert haette). Kein Match-
# Konflikt mit :data:`_YEAR_RANGE_BETWEEN` (das laeuft ohnehin nach dem
# Preprocessor und wuerde denselben Wert liefern, weil ``1985 - 1990`` via
# :data:`_YEAR_RANGE` denselben Anker-Wert liefert wie ``zwischen 1985 und
# 1990`` via _YEAR_RANGE_BETWEEN direkt) und keine anderen Datumsformen
# beginnen mit "zwischen"/"between".
_BETWEEN_AND_WRAPPER = re.compile(
    r"^\s*(?:zwischen|between)\s+(.+?)\s+(?:und|and)\s+(.+?)\s*$",
    re.IGNORECASE,
)
_YEAR_MONTH = re.compile(r"^\s*(\d{4})[-/.](\d{1,2})\s*$")
# Numerisches Monat-Jahr "06/2024", "6-2024", "06.2024" - in Exports oft fuer
# Monatsangaben verwendet. Tag wird auf den 1. gesetzt; Monate ausserhalb 1-12
# fallen auf None (sind dann i.d.R. ein anderes Format, das nicht hierher gehoert).
_MONTH_NUMERIC_YEAR = re.compile(r"^\s*(\d{1,2})[/.\-](\d{4})\s*$")
# Annaeherungspraefixe (DE/EN), wie sie in geerbten Sammlungs-Notizen typisch sind:
# "ca. 1985", "circa 2020", "um 1980", "approx. 2024", "around 1995".
# Werden gestrippt, dann wird der Rest re-parst - die Datumsbedeutung selbst bleibt
# gleich (Vermerk "Naeherungswert" liegt in der Freitext-Spalte, nicht im ISO-Datum).
# DE-Sammler-Vokabular umfasst zusaetzlich ``etwa``, ``vermutlich``,
# ``schaetzungsweise``/``schätzungsweise`` (alle "geschaetzter Wert", semantisch
# identisch mit ``ca.``); EN ergaenzt ``estimated``/``est.``/``roughly``.
#
# Wahrscheinlichkeits-/Vermutungs-Marker (DE: ``wahrscheinlich``, ``moeglicher-
# weise``/``möglicherweise``, ``evtl.``/``evtl``/``eventuell``; EN: ``perhaps``,
# ``possibly``, ``maybe``) spiegeln semantisch die Konservativ-Annaeherung
# (``vermutlich``/``ca.``) auf die Unsicherheits-Achse. In geerbten Sammlungs-
# Notizen sehr verbreitet, wenn der Vorbesitzer das Datum nicht genau kannte
# ("wahrscheinlich 1985 gekauft", "möglicherweise 1980er", "evtl. Juni 2024",
# "perhaps 1995"). Bisher fielen alle diese Praefix-Formen still auf None -
# aus typischen Etikett-/Tagebuch-Eintraegen mit Unsicherheits-Markierung
# wurde silenter Funddatum-Datenverlust. Der Praefix ist semantische Wert-
# Anmerkung ("welche Verlaesslichkeit"), keine Datums-Modifikation; das
# ISO-Datum-Output bleibt identisch zur reinen Form, die Vermutungs-Angabe
# bleibt im Freitext (notizen).
#
# Symbolische Annaeherungs-Marker (Tilde ``~`` und Almost-Equal ``≈`` U+2248)
# decken die typografisch-knappe Notation aus Print-Katalogen, Auktions-PDFs und
# LaTeX-Exporten ab (``\approx`` rendert als ``≈``); auch verbreitet in Tabellen-
# Captions/Foto-EXIF-Notizen, wo der Schreiber Platz spart (``~1985``, ``≈
# Juni 2024``). Bisher fielen beide Formen stille auf None, obwohl semantisch
# identisch zu ``ca.``. Wird via Alternation zur Wort-Variante eingefuegt: die
# symbolische Form akzeptiert auch null Leerzeichen (``~1985``), waehrend die
# Wort-Variante weiter mindestens eines verlangt (sonst wuerde ``ca1985`` als
# ``ca`` + ``1985`` zerlegt).
#
# Die Symbolic-Marker-Klasse ``[~≈≅≃]`` deckt neben ASCII-Tilde und Almost-
# Equal (``≈``) auch die beiden weiteren, in wissenschaftlichen Publikationen
# und LaTeX-Autoformat-Quellen gebraeuchlichen Naeherungs-Symbole ab: ``≅``
# (U+2245, "APPROXIMATELY EQUAL TO", LaTeX ``\cong``) und ``≃`` (U+2243,
# "ASYMPTOTICALLY EQUAL TO", LaTeX ``\simeq``). Beide sind in Print-Katalogen,
# Auktions-PDFs mit LaTeX-Setz und in aus wissenschaftlichen Datenbanken
# (IUCr, NIST, RRUFF, Mindat.org mit LaTeX-Rendering) exportierten Textfeldern
# verbreitet und semantisch identisch zu ``≈``/``~`` als Naeherungs-Marker vor
# einem Datum ("≅ 1985", "≃ Juni 2024"). Spiegelt die identische Klassen-
# Erweiterung in :data:`stonebook.migration.csv_loaders._APPROX_VALUE_PREFIX`
# auf die Datums-Achse - dieselbe LaTeX-Konvention aus wissenschaftlichen
# Publikationen erzeugt bei Datums-Feldern (Fund-/Erwerbs-Jahr aus einer
# Referenz-Publikation) denselben Marker vor der Datums-Angabe wie bei Wert-
# Feldern (Dichte/Haerte/Mohs-Wert aus einer Referenz-Tabelle). Bisher fielen
# alle DE/EN/FR/IT-Formen mit diesen zwei Symbolen still auf None, obwohl
# semantisch identisch zu ``ca.``/``circa``/``etwa``.
_APPROX_PREFIX = re.compile(
    r"^(?:"
    r"(?:ca\.?|circa|approx\.?|approximately"
    r"|around|about|roughly|estimated|est\."
    r"|um|gegen|etwa|vermutlich"
    # Umlaut-Variante und Transliteration ae (gemischte Sammlungs-Notizen)
    r"|sch[äa]tzungsweise|schaetzungsweise"
    # ``ungef[äa]hr``/``ungefaehr`` spiegelt die bereits im
    # :data:`_TRAILING_APPROX_SUFFIX` gelistete Wortmarke auf die Praefix-
    # Achse: DE-Standardvokabular fuer "geschaetzter Wert" (semantisch
    # identisch zu ``ca.``/``etwa``), sehr verbreitet in Sammlungs-Notizen
    # ("ungefähr 1985 in den Alpen gefunden", "ungefaehr Juni 2024
    # gekauft"). Vor dem Fix fielen alle Praefix-Formen mit dieser Marke
    # stille auf None, waehrend die identische Trailing-Form ("1985
    # ungefähr") erkannt wurde - eine Asymmetrie, die typische DE-Satz-
    # Reihenfolge ("ungefähr <Datum> <Kontext>") gegen die Anhang-Form
    # ("<Datum> ungefähr <Kontext>") bevorzugte. Umlaut- und Transliterations-
    # Variante spiegelt die schaetzungsweise-Konvention.
    r"|ungef[äa]hr|ungefaehr"
    # Past-Partizip ``geschätzt``/``geschaetzt`` als adverbiale Praezisions-
    # Marke ("geschätzt 1985", "geschaetzt Juni 2024"). Spiegelt die
    # adverbiale Form ``sch[äa]tzungsweise``/``schaetzungsweise`` bereits im
    # Pattern und ist in DE-Sammler-/Museums-Notizen oft die verkuerzte
    # Alternative ("Erwerb geschätzt 1985", "Fundzeitpunkt geschaetzt Juni
    # 2024"). Vor dem Fix fielen alle Praefix-Formen mit dieser Marke
    # stille auf None, obwohl die identische EN-Form ``estimated`` (Past-
    # Partizip, identische Grammatik) bereits erkannt wurde - eine DE/EN-
    # Asymmetrie im Past-Partizip-Register. Umlaut- und ASCII-Trans-
    # literations-Variante parallel wie bei den uebrigen Vokabeln (Windows-
    # CP1252/Excel-DE nativ vs. 7-bit-ASCII-Notizen).
    r"|gesch[äa]tzt|geschaetzt"
    # Wahrscheinlichkeits-/Vermutungs-Marker (DE)
    r"|wahrscheinlich|m[öo]glicherweise|moeglicherweise"
    r"|evtl\.?|eventuell"
    # Hearsay-/Zuschreibungs-Marker (DE): der Vorbesitzer notierte das Datum
    # nicht aus eigener Beobachtung, sondern aufgrund einer Zuschreibung
    # (Verkaeufer-Angabe, Vorbesitzer-Erzaehlung, Katalog-Referenz). In
    # geerbten Sammlungs-Notizen und Museums-Etiketten sehr verbreitet,
    # wenn die Provenienz aus zweiter Hand kommt und der aktuelle Kurator
    # die Datums-Zuverlaessigkeit relativieren will ("angeblich 1985 im
    # Aare-Gebiet gefunden", "angeblich Juni 2024 vom Vorbesitzer erworben").
    # Semantisch identisch zu "vermutlich"/"wahrscheinlich" (Unsicherheits-
    # Marker mit dokumentierter Herkunfts-Fragezeichen), aber auf der Hearsay-
    # Achse (Datum stammt aus Erzaehlung, nicht Beobachtung) - Strip + Rekursion
    # wie bei den uebrigen Wahrscheinlichkeits-Marken, das ISO-Datum-Output
    # ist identisch zur reinen Form (der Hearsay-Marker gehoert konzeptionell
    # in die notizen-Spalte).
    r"|angeblich"
    # Wahrscheinlichkeits-/Vermutungs-Marker (EN)
    r"|perhaps|possibly|maybe|presumably"
    # Hearsay-/Zuschreibungs-Marker (EN): spiegelt DE ``angeblich`` auf die
    # englische Achse. In EN-Sammler-Notizen aus Auktions-Katalogen und
    # US-/UK-Mineral-Boersen sehr verbreitet, wenn die Provenienz-Angabe
    # aus zweiter Hand kommt ("allegedly 1985 from an Aar valley find",
    # "supposedly June 2024 acquired from the previous owner", "reportedly
    # collected 1995 in Tucson"). ``purportedly`` ist die
    # akademisch-formellere Variante, verbreitet in Museums-Katalogen und
    # wissenschaftlichen Publikationen.
    r"|allegedly|supposedly|reportedly|purportedly"
    # FR-/IT-Annaeherungs-Marker (Suisse romande / Ticino / Val d'Aosta).
    # ``vers`` (FR) = "gegen"/"um", ``environ`` (FR) = "ungefaehr", ``verso``
    # (IT) = "gegen"/"um", ``attorno`` (IT, meist in "attorno al 1985" mit
    # Artikel-Kontraktion, hier ohne Artikel als bare Praefix-Form). ``circa``
    # ist zwar IT-Vokabular, aber via Latin-Wurzel bereits im DE-/EN-Block
    # oben abgedeckt. Sammler-Notizen aus franzoesisch-sprachigen Alpen-
    # Fundorten (Wallis/Val d'Anniviers, Chamonix, Mont-Blanc) und aus
    # italienisch-sprachigen Ticino-/Val-d'Aosta-Sammlungen und Museo-
    # cantonale-di-storia-naturale-Etiketten nutzen die FR/IT-Vokabeln,
    # wenn der Vorbesitzer den Fund-/Erwerbs-Zeitraum nur ungefaehr kannte
    # ("vers 1985 acquis au marche", "environ juin 2024 trouve au Chamonix",
    # "verso 1985 acquistato in Ticino", "attorno 1985 raccolto in Val
    # Bavona"). Bisher fielen alle FR/IT-Praefix-Formen still auf None,
    # obwohl semantisch identisch zu ``ca.``/``circa``. Spiegelt die
    # FR/IT-Erweiterungen in :data:`_MONTH_NAMES` / :data:`_SEASON_MONTHS`
    # / :data:`_DIRECTION_WORD` / :data:`_COORD_LABEL` auf die Approx-
    # Praefix-Achse. Kollisions-Schutz durch das ``\s+``-Suffix in der
    # Praefix-Regex: ``vers`` matcht nicht in ``versichert``/``verse``/
    # ``versa`` (nach ``vers`` folgt hier ein Buchstabe, kein Whitespace);
    # ``environ`` matcht nicht in ``environment``/``environments`` (analog);
    # ``verso`` matcht nicht in ``versoehnung``/``version`` (analog);
    # ``attorno`` hat keinen DE/EN-Wortstamm-Konflikt.
    r"|vers|environ|verso|attorno"
    # ES-/PT-Annaeherungs-Marker (Sammler-Region Andalusien mit Almeria/
    # Sierra Almagrera/Rodalquilar/Riotinto sowie La Union Murcia, latein-
    # amerikanische Fundstellen Cerro Rico Potosi/Chuquicamata/La Rinconada;
    # Panasqueira/Beira Baixa fuer Wolframit-/Quarz-Adern, brasilianische
    # Pegmatit-Region Minas Gerais/Bahia mit Turmalin/Topas/Aquamarin/Beryll).
    # ``hacia`` (ES) = "gegen"/"um" - der ES-Aequivalent zu DE ``gegen``/FR
    # ``vers``/IT ``verso``, Standard-Vokabel fuer "ungefaehr um ein Datum
    # herum" in Fund-Etiketten und Katalog-Eintraegen ("hacia 1985",
    # "hacia junio 2024", "hacia el verano 2024"). ``aproximadamente`` (ES/PT
    # geteilt) = "ungefaehr"/"circa" - der direkte Aequivalent zu DE
    # ``ungefaehr``/``ca.``/EN ``approximately``, verbreitet in wissen-
    # schaftlichen ES-/PT-Publikationen und formalisierten Katalog-
    # Eintraegen ("aproximadamente 1985", "aproximadamente junio 2024"),
    # semantisch identisch aber sprachliche Katalog-Konvention. ``talvez``
    # (PT) = "vielleicht"/"eventuell" - der PT-Aequivalent zu DE ``evtl.``/
    # ``eventuell``/EN ``perhaps``/``maybe``, verbreitet in PT-BR-Sammler-
    # Notizen mit Unsicherheits-Marker ("talvez 1985 em Minas Gerais",
    # "talvez junho 2024"). ``provavelmente`` (PT) = "wahrscheinlich" -
    # der PT-Aequivalent zu DE ``wahrscheinlich``/EN ``probably``/
    # ``presumably``, verbreitet in narrativen PT-BR-Sammler-Notizen und
    # Museums-Etiketten ("provavelmente 1985 em Panasqueira"). Bisher fielen
    # alle ES-/PT-Praefix-Formen still auf None, obwohl semantisch identisch
    # zu ``ca.``/``circa``/DE ``ungefaehr``/FR ``vers``/IT ``verso``.
    # Spiegelt die ES-/PT-Erweiterungen in :data:`_MONTH_NAMES` (enero..
    # diciembre / janeiro..dezembro, commits 652ac1a und 87eb2cd),
    # :data:`_SEASON_MONTHS` (primavera/verano/otono/invierno und verao/
    # outono/primavera/inverno, commits 69e71b6 und 4c3ce4f),
    # :data:`_DIRECTION_WORD` (norte/sur/este/oeste ES, commit f9804bd) und
    # :data:`DATE_NO_DATA_MARKERS` (desconocido/sin fecha/desconhecido/sem
    # data, commit bebce89) auf die Approx-Praefix-Achse und schliesst
    # damit die ES-/PT-Achse aller parse-relevanten Vollnamen-Kategorien
    # inklusive der Approx-Semantik. Kollisions-Schutz durch das
    # ``\s+``-Suffix: ``hacia`` matcht nicht in ``haciendo``/``hacia`` als
    # Verb-Form ohne Whitespace (nach ``hacia`` folgt hier meist Text ohne
    # Whitespace), ``aproximadamente`` und ``provavelmente`` haben durch
    # ihre Wort-Laenge (14/12 Zeichen) keinen ueberlappenden Wortstamm zu
    # anderen Sprachen, ``talvez`` (PT-spezifisch, im ES ist die zwei-Wort-
    # Form ``tal vez`` Standard und faellt nicht in das single-Wort-Pattern).
    r"|hacia|aproximadamente|provavelmente|talvez"
    r")\s+"
    # ``∼`` (U+223C, TILDE OPERATOR, LaTeX ``\sim``) als weiterer Symbolic-
    # Marker in der Symbolic-Marker-Klasse. Semantisch identisch zu ``~``
    # (ASCII TILDE, U+007E), aber typografisch getrennt: ``∼`` ist der
    # mathematische Naeherungs-Operator, den LaTeX im Math-Mode fuer
    # ``\sim`` rendert (waehrend ``~`` in LaTeX ``\textasciitilde`` ist,
    # ein Text-Mode-Symbol). PDF-Text-Extraktion aus LaTeX-gesetzten
    # Publikationen (IUCr, NIST, RRUFF, Mindat.org, Handbook of Mineralogy)
    # exportiert den Math-Mode-Tilde als U+223C, nicht als ASCII-``~`` -
    # spiegelt strukturell die identische Konvention der uebrigen Symbolic-
    # Marker der Klasse: ``≈``/``≅``/``≃`` sind alle die Unicode-Punkte der
    # LaTeX-Math-Mode-Naeherungs-Symbole (``\approx``/``\cong``/``\simeq``),
    # der ASCII-``~`` ist die Text-Mode-Variante, und ``∼`` schliesst die
    # letzte Luecke der Math-Mode-Symbol-Achse. Bisher fielen alle Datums-
    # Formen mit ``∼``-Praefix still auf None, obwohl semantisch identisch
    # zu ``~``/``≈``/``≅``/``≃`` - identischer Bug-Effekt wie bei ``≅1985``
    # vor Einfuehrung von ``≅`` in c6ce6ac. Spiegelt die identische Klassen-
    # Erweiterung in :data:`stonebook.migration.csv_loaders._APPROX_VALUE_PREFIX`.
    r"|[~≈≅≃∼]\s*"
    r")",
    re.IGNORECASE,
)
# Temporale Praeposition (DE/EN) vor dem Datum: "im Sommer 1985", "im Juni 2024",
# "im Jahr 1985", "in den Jahren 1985-1990", "vom 13. Juni 2024", "am 13.06.2024",
# "in 2024", "on June 13, 2024", "year 2024", "Jahr 1985". Sehr verbreitet in
# geerbten Sammlungs-Notizen, die das Datum in einen vollstaendigen Satz einbetten
# ("Im Sommer 1985 in den Schweizer Alpen gefunden", "Foto vom 13. Juni 2024",
# "Aufgenommen am 13.06.2024"); bisher fielen alle Formen mit Praeposition stille
# auf None, obwohl semantisch eindeutig - die Datums-Bedeutung selbst bleibt
# identisch (die Praeposition ist Satz-Gluekel, keine Datums-Modifikation),
# spiegelt damit das Konzept von _APPROX_PREFIX (Praefix wird gestrippt, Datum
# bleibt unveraendert) auf die temporale-Satz-Achse.
# DE: "im" (=in dem), "in", "vom" (=von dem), "von", "am" (=an dem) sind die
# ueblichen temporalen Praepositionen vor Tag/Monat/Saison/Jahr.
# EN: "in" (Praeposition vor Monat/Jahr), "on" (vor Tag mit Jahr) sind verbreitet.
# Optional zwischen Praeposition und Datum ein Artikel (DE: "dem"/"den"/"der";
# EN: "the") und ein Fueller-Wort ("Jahr"/"Jahre"/"Jahren"/"year"), das in
# Saetzen wie "im Jahr 1985" / "in den Jahren 1985-1990" / "in dem Jahre 1985"
# / "in the year 1985" / "in the 1980s" oft auftaucht.
# "Jahr 1985" ohne Praeposition kommt ebenfalls vor (Listen-/Tabellen-Stichwort,
# "Jahr 1985: Erste Sammlung"). Wird via Rekursion identisch zu _APPROX_PREFIX/
# _WEEKDAY_PREFIX behandelt: einmal gestrippt, dann uebernimmt parse_iso_date
# das eigentliche Parsen vom Rest. Verkettung mit anderen Praefixen funktioniert
# durch wiederholte Rekursion ("im ca. Sommer 1985" → "ca. Sommer 1985" → "Sommer
# 1985" → "1985-06-01"). Nach _WEEKDAY_PREFIX einsortiert, damit "Donnerstag, im
# Juni 2024" zuerst den Wochentag und dann die Praeposition strippt.
# Praeposition ``aus`` (DE-Herkunft/Provenienz-Standard: "aus dem Jahr 1985",
# "aus den 1980er Jahren", "aus dem 19. Jahrhundert") deckt die haeufigste
# DE-Herkunfts-Formulierung in Sammler-/Museums-Notizen ab. In der ererbten
# Katalog-Praxis notieren Vorbesitzer die Provenienz eines Stuecks fast immer
# mit ``aus`` + Zeitangabe ("Stueck aus der Nachkriegs-Sammlung, aus dem
# Jahr 1962", "Fund aus den 1980ern Alpen-Exkursionen"). Bisher fielen alle
# Formen mit ``aus``-Praefix still auf None, obwohl die Datums-Bedeutung
# selbst identisch zur reinen Form ist - die Praeposition ist reines Satz-
# Gluekel, keine Datums-Modifikation. Spiegelt das ``im/in/am/vom/von/on``-
# Konzept auf die Herkunfts-Achse; die Rekursions-Kette in parse_iso_date
# erledigt die eigentliche Datums-Auswertung nach dem Strip.
#
# Praeposition ``waehrend`` / ``während`` (DE-Genitiv/Dativ-Zeitspanne:
# "waehrend des Jahres 1985", "waehrend 1985", "waehrend der 1980er Jahre")
# und EN ``during`` decken die zeitspannen-Herkunfts-Formulierung ab - typisch
# in narrativen Tagebuch-/Reise-Notizen ("waehrend meines Aufenthaltes in
# 1985 gefunden", "during the 1985 summer expedition"). Symmetrisch zu ``aus``
# behandelt: reines Satz-Gluekel, Datums-Bedeutung identisch zur reinen Form.
# Umlaut- (``während``) und ASCII-transliterierte Form (``waehrend``) beide
# praxisrelevant (Windows-CP1252/Excel-DE nativ, 7-bit-ASCII-Notizen
# transliterieren).
_TEMPORAL_PREFIX = re.compile(
    r"^(?:"
    # Praeposition + optional Artikel + optional "Jahr"-Wort + Whitespace
    # FR-/IT-Zusatz (Suisse romande / Ticino / Val d'Aosta): ``en`` (FR)
    # deckt die haeufigste FR-Temporal-Praeposition vor Jahr/Monat/Saison ab
    # ("en 1985", "en juin 2024", "en été 2024" - identisch zu DE ``im``).
    # ``nel``/``nella``/``nello``/``nei``/``negli``/``nelle`` (IT) deckt die
    # kontraktierten Artikel-Praeposition-Formen ab: ``nel`` = "in dem" (mask.
    # sing.), ``nella`` = "in der" (fem. sing.), ``nello`` = "in dem" (mask.
    # sing. vor s+Konsonant/z), ``nei`` = "in den" (mask. pl.), ``negli`` = "in
    # den" (mask. pl. vor s+Konsonant/z), ``nelle`` = "in den" (fem. pl.).
    # Sehr verbreitet in Ticino-Sammler-Notizen und in Museo-cantonale-di-
    # storia-naturale-Etiketten ("nel 1985 raccolto in Val Bavona", "nella
    # primavera 2020 acquistato al mercato di Locarno", "negli anni 1980
    # esplorato il Val Verzasca"). Bisher fielen alle FR/IT-Praeposition-
    # Formen still auf None, weil die Liste nur DE-/EN-Wortstaemme abdeckte -
    # obwohl semantisch identisch zur DE ``im``/EN ``in``-Praeposition und
    # das ISO-Datum-Output unveraendert bleibt. Spiegelt die FR/IT-
    # Erweiterungen in :data:`_MONTH_NAMES` / :data:`_SEASON_MONTHS` /
    # :data:`_DIRECTION_WORD` / :data:`_COORD_LABEL` / :data:`_APPROX_PREFIX`
    # auf die Temporal-Praeposition-Achse. Kollisions-Schutz: alle FR/IT-
    # Wortstaemme haben eine eindeutige, kurze Form ohne Kollisions-Konflikt
    # mit DE-/EN-Wortstaemmen (``en`` ist als Standalone-Wort weder in DE
    # noch in EN gebraeuchlich; ``nel``/``nello``/``nei``/``negli``/``nelle``/
    # ``nella`` haben keine Praefix-Kollision mit DE/EN-Woertern).
    r"(?:im|in|am|vom|von|on|aus|w[äa]hrend|waehrend|during"
    r"|en|nel|nello|nella|nei|negli|nelle"
    r")\s+"
    r"(?:(?:dem|den|der|des|the)\s+)?"
    # FR-/IT-Filler-Woerter (Jahr-Aequivalent): FR ``an``/``annee``/``annees``
    # (mit oder ohne Akzent auf ``année``/``années`` - :func:`_normalize_month_
    # name`-Diakritika-Strip greift hier nicht, weil das Filler-Wort direkt in
    # der Regex-Alternante steht - beide Formen explizit auflisten), IT ``anno``/
    # ``anni`` (mask. sing./pl., ``anno`` = "Jahr", ``anni`` = "Jahre"). Symmetrie
    # zur DE ``jahr``/``jahre``/``jahres``/``jahren``-Alternante und EN ``year``-
    # Alternante, damit "en l'annee 1985" (FR) / "nell anno 1985" (IT) / "negli
    # anni 1980" (IT) transparent gestrippt werden. Elidierte FR-Artikel-Formen
    # (``l'``/``d'``) bleiben ausserhalb dieses Patterns (die Apostroph-Behandlung
    # verlangt eine Sonder-Regex und ist selten in Sammler-Notizen ohne strenge
    # Grammatik). ``anno(?!\s+domini)`` negativer Lookahead schuetzt die Latin-
    # Aera-Vollform ``Anno Domini`` (Church-Latin "im Jahr des Herrn", historische
    # Etiketten mit ecclesialer Provenienz) vor dem vorzeitigen Filler-Strip -
    # ohne Lookahead wuerde ``anno\s+`` in ``Anno Domini 1985`` matchen und den
    # Rest ``Domini 1985`` unparseable an :func:`parse_iso_date`-Rekursion
    # uebergeben. :data:`_LEADING_ERA_MARKER` (spaeter im Kaskade-Aufruf) hat den
    # dedizierten ``anno\s+domini``-Alternate, der die Vollform als 2-Token-Aera-
    # Marker strippt; der negative Lookahead sorgt dafuer, dass die Filler-Regel
    # hier den 1-Token-``anno``-Fall an die spezifischere Aera-Regel abgibt.
    r"(?:(?:jahr|jahre|jahres|jahren|year|an|ann[eé]e|ann[eé]es|anno(?!\s+domini)|anni)\s+)?"
    r"|"
    # Nur "Jahr"-Wort ohne Praeposition (Listen-/Tabellen-Stil)
    r"(?:jahr|jahre|jahres|jahren|year|anno(?!\s+domini)|anni|ann[eé]e|ann[eé]es)\s+"
    r")",
    re.IGNORECASE,
)
# Boundary-/Richtungs-Praefix (DE/EN) vor dem Datum: "vor 1985", "nach 1985",
# "before 1985", "after 1985", "pre-1985", "post-1985". Sehr verbreitet in
# geerbten Sammlungs-Notizen, wenn der vorherige Besitzer den Fund nur grob
# in Bezug auf ein Jahr datieren konnte ("vor 1985 gefunden, genaues Jahr
# unbekannt"). Bisher fielen alle Boundary-Formen stille auf None, obwohl
# das Jahr selbst eindeutig ist - die Richtungsinformation (vor/nach) bleibt
# im Freitext (notizen) erhalten, das ISO-Datum nimmt den Grenzwert als
# bekannten Anker. Spiegelt das Konzept von _APPROX_PREFIX (Praefix wird
# gestrippt, Datum bleibt unveraendert): die Richtungsangabe ist semantisch
# "Wert-Anmerkung", keine Datums-Modifikation - das ISO-Output ist identisch
# zur reinen Form. Konvention spiegelt _APPROX_PREFIX und _YEAR_RANGE (Start-
# /Boundary-Jahr als ISO-Datum), sodass "vor 1985" und "1985-1990" beide auf
# 1985-01-01 abbilden und die Range-/Boundary-Annotation im Freitext bleibt.
# DE-Sammler-Vokabular: "vor"/"nach" sind die Standard-Richtungsangaben,
# "pre"/"post" decken hyphen-typische Kompositformen aus englischen Quellen
# ab (Auktions-Beschreibungen, Mineralogie-Reviews). EN: "before"/"after"
# sind die ueblichen Wort-Formen. Trenner ``[-\s]+`` deckt sowohl Bindestrich-
# Kompositum ("pre-1985", "post-1985" - typische EN-Compound-Form) als auch
# Wort-Trennung ("vor 1985", "before 1985") ab; verbleibender Whitespace
# wird durch das strip() vor der Rekursion abgefangen. Wird via Rekursion
# identisch zu _APPROX_PREFIX/_WEEKDAY_PREFIX/_TEMPORAL_PREFIX behandelt:
# einmal gestrippt, dann uebernimmt parse_iso_date das eigentliche Parsen
# vom Rest. Verkettung mit anderen Praefixen funktioniert durch wiederholte
# Rekursion ("vor ca. 1985" → "ca. 1985" → "1985" → "1985-01-01";
# "ca. vor 1985" → "vor 1985" → "1985"). Nach _TEMPORAL_PREFIX einsortiert,
# damit "im vor 1985" (semantisch redundant, aber unschaedlich) erst die
# Praeposition und dann die Richtungsangabe strippt. Kollision mit Praefixen
# wie "vorheriger", "Nachmittag", "preset", "posten": ausgeschlossen, weil
# der trailing ``[-\s]+`` ein echtes Wort-Ende verlangt - "vorhin 1985"
# matchet nicht, weil nach "vor" kein Whitespace/Bindestrich kommt.
#
# Erweiterte DE-Adverb-Formen ``spaetestens``/``spätestens`` (spiegelt ``vor``
# als semantische Obergrenze, "das Jahr ist das spaeteste Datum") und
# ``fruehestens``/``frühestens`` (spiegelt ``nach`` als semantische Unter-
# grenze, "das Jahr ist das frueheste Datum") decken die haeufigste DE-
# Sammler-/Museums-Notiz-Praxis fuer weiche Grenz-Datierungen ab: "Fund
# spaetestens 1985 in die Sammlung aufgenommen", "Provenienz frühestens
# 1990". Semantisch identisch zu vor/nach - der Grenzwert ist der bekannte
# Anker, die Richtung bleibt im Freitext (notizen). Umlaut- und ae-Trans-
# literation parallel wie bei den uebrigen Vokabeln (siehe :data:`_APPROX_PREFIX`
# ``ungef[äa]hr|ungefaehr``, :data:`_RELATIVE_DECADE_ADJECTIVE_OFFSETS``
# ``spaet``/``spät``/``frueh``/``früh``). Wortende-Zwang ``[-\s]+`` erhaelt
# sich - "spätestensvor 1985" (ohne Whitespace) matchet nicht, "spätestens-
# 1985" (Bindestrich statt Whitespace) matchet symmetrisch zu ``pre-1985``.
_BOUNDARY_PREFIX = re.compile(
    r"^(?:vor|nach|sp[äa]testens|spaetestens|fr[üu]hestens|fruehestens|before|after|pre|post)[-\s]+",
    re.IGNORECASE,
)
# Unidirektionale Range-Praefix (DE/EN) vor dem Datum: "ab 1985", "seit 1985",
# "bis 1985", "from 1985", "since 1985", "until 1985", "till 1985". Sehr
# verbreitet in geerbten Sammlungs-Notizen, wenn der Sammler den Startpunkt
# einer Erfassungs-/Fund-Periode notiert ("Sammlung ab 1985", "Fundort seit
# 1990 zugaenglich") oder ihr Ende ("Fundort bis 1995 aktiv", "until 2000
# accessible"). Semantisch komplementaer zu _BOUNDARY_PREFIX (vor/nach als
# bilaterale Grenze, ab/seit/bis als unidirektionale Spanne-Start-/Ende-
# Marker); aus parser-Sicht identisch (das Jahr ist der bekannte Anker,
# die Richtung bleibt im Freitext). Bisher fielen alle Formen mit
# unidirektionalem Praefix stille auf None, obwohl das Jahr/Datum selbst
# eindeutig ist - aus typischen Tagebuch-/Etikett-Eintraegen wie "seit
# 1985" wurde silenter Funddatum-Datenverlust. Spiegelt das Konzept von
# _BOUNDARY_PREFIX (Strip + Rekursion, Boundary-Jahr als ISO-Datum). DE-
# Sammler-Vokabular: "ab" (von da an), "seit" (von da an, dauerhaft),
# "bis" (bis zu da); EN: "from" (von da an), "since" (von da an, dauer-
# haft), "until"/"till" (bis zu da). Hinweis zur Kollision mit
# _YEAR_RANGE_WORD: dort ist "bis"/"to"/"till"/"until" als Range-Trenner
# in der Mitte gelistet ("1950 bis 1960"); hier am Anfang strippt es als
# unidirektionaler Marker ("bis 1985"). Beide funktionieren ohne Konflikt,
# weil _RANGE_PREFIX mit ``^`` ankerkt - "1985 bis 1990" beginnt mit
# einer Ziffer, nicht mit "bis", und faellt damit nicht in den Prefix-
# Strip-Pfad. "von" ist bereits in _TEMPORAL_PREFIX gelistet und wird
# dort gestrippt; hier nicht doppelt aufgenommen. Trenner ``\s+`` deckt
# alle Wort-Formen ab (keine Bindestrich-Kompositum-Form ueblich bei
# DE/EN-Unidirektionalen). Nach _BOUNDARY_PREFIX einsortiert, weil
# semantisch verwandt aber konzeptionell unterschiedlich (bilateral vs.
# unidirektional) und damit beide Praefix-Klassen lesbar getrennt
# bleiben. Kollision mit Praefixen wie "Ablagerung", "Abschnitt",
# "abgesehen", "seitlich", "seitens", "bissel", "fromage", "sincerely",
# "tilltrigger": ausgeschlossen durch das trailing ``\s+`` (Wort-Ende-
# Pruefung).
# Optionaler Artikel + optional Jahr-Wort nach der Praeposition, symmetrisch
# zu _TEMPORAL_PREFIX. Deckt Formen mit Artikel-Rektion ab: "seit dem Jahr
# 1985" (Dativ), "ab dem Jahr 1985" (Dativ), "bis zum Jahr 1985" (nicht
# gedeckt, Kontraktion "zum" waere separate Alternante), "seit den 1980er
# Jahren" (Dativ Plural, sehr verbreitet in Kollektions-/Museums-Provenienz-
# Vermerken), "seit den 1980ern" (substantivierte Dativ Plural-Kurzform),
# "since the year 1985" (EN Standard-Form), "from the 1980s", "until the
# 1990s". Bisher fielen alle Formen mit Artikel-Zwischenwort still auf None,
# obwohl semantisch identisch zur artikellosen Form ("seit 1985"): das Jahr
# ist der bekannte Anker, der Artikel-Zwischen-Teil ist reines grammatika-
# lisches Gluekel und wird beim Strippen wie in _TEMPORAL_PREFIX identisch
# behandelt. Aus geerbten Sammler-/Museums-Notizen mit vollstaendigem
# Satzbau entstand damit silenter Funddatum-Datenverlust, obwohl das
# Datum selbst eindeutig ist.
_RANGE_PREFIX = re.compile(
    r"^(?:ab|seit|bis|from|since|until|till)\s+"
    r"(?:(?:dem|den|der|des|the)\s+)?"
    r"(?:(?:jahr|jahre|jahres|jahren|year)\s+)?",
    re.IGNORECASE,
)
# Wochentag-Praefix wie in Foto-Captions / EXIF-Datetimes / Tagebucheintraegen
# ("Mo 13.06.2024", "Donnerstag, 13. Juni 2024", "Thu Jun 13 2024").
# Voll- und Kurzformen (DE: Mo/Di/Mi/Do/Fr/Sa/So; EN: Mon-Sun) werden gestrippt,
# samt optionalem trailing ``.`` und Komma. Danach uebernimmt die Rekursion.
# Zweistellige Kurzform mit Punkt ("Mo.") oder ohne — beides verbreitet.
_WEEKDAY_PREFIX = re.compile(
    r"^(?:"
    r"montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun"
    r"|mo|di|mi|do|fr|sa|so"
    r")\.?\s*,?\s+",
    re.IGNORECASE,
)
# Trailing time component (T/space getrennt) inkl. optionaler Zonenangabe.
# Wird vor dem Re-Parsing gestrichen, damit auch "13.06.2024 14:30" funktioniert.
# Sekunden-Dezimalbruch akzeptiert sowohl Punkt als auch Komma als Trennzeichen;
# ISO 8601 schreibt explizit Komma als bevorzugten Dezimal-Separator vor und
# erlaubt Punkt als Alternative ("preferring comma is permitted"), in
# europaeischen Locales (DE/FR/IT) ist Komma der Default.
# Benannte Zeitzonen-Suffixe (``UTC``, ``GMT``, ``CET``, ``CEST``, ``EST``,
# ``PST``, ``MEZ``, ``MESZ`` etc.) werden symmetrisch zur numerischen Form
# (``+02:00``/``Z``) erkannt - System-Logs, Foto-Captions und EXIF-Tools
# schreiben die TZ oft als 2-5-Buchstaben-Abkuerzung statt als Offset. Nur
# Grossbuchstaben matchen, damit zufaellige Kleinbuchstaben-Suffixe (``Uhr``,
# ``abc``) nicht als TZ interpretiert werden; einzelnes ``Z`` ist Zulu und
# wird durch den vorhandenen ``[Zz]``-Branch abgedeckt (deshalb hier
# Mindestlaenge 2, um Kollision zu vermeiden).
#
# Zweite Alternante ``(?<=\d)[Tt]\d{4}(?:\d{2})?(?:[.,]\d+)?`` deckt die
# kompakte ISO 8601 Basic-Form ohne Trenner ab: ``T143200`` (HHMMSS),
# ``T1432`` (HHMM), ``T143200.123`` (HHMMSS mit Sekundenbruchteil), symmetrisch
# zur kollektionerweiterten Form mit Sekundenbruch aus der ersten Alternante.
# Standard-Serialisierungs-Form fuer datei-basierte Zeitstempel (Backup-/
# Log-Rotations-Skripte schreiben typisch ``stone_20240613T143200.sqlite3``,
# ``export_20240613T143200.tar.gz``), fuer Git-Branch-/Tag-Namen (``release/
# 20240613T143200``), fuer ISO 8601 basic profile in RFC-2822/RFC-3339-nahen
# Log-Formaten und fuer manche EXIF-DateTimeOriginal-Feldwerte in JPEG-/RAW-
# Kameras (Sony/Canon-Auto-Rename kombiniert manchmal die basic-Form mit dem
# Ordner-Namen zu Datei-Stempeln). Bisher fielen alle basic-Form-Datetime-
# Notationen still auf None, obwohl das Datum vor dem T-Separator eindeutig
# kompakt-lesbar war (``20240613`` -> 2024-06-13 via _DATE_FORMATS-``%Y%m%d``):
# ``20240613T143200`` -> None statt 2024-06-13 (Datum-Kompakt-Form wird durch
# das T-Time-Suffix blockiert), ``20240613T143200Z`` und
# ``20240613T143200+0200`` analog (TZ-Suffix schon in der ersten Alternante
# abgedeckt, aber die kompakte Zeit selbst faellt aus dem Colon-Muster
# heraus).
#
# Lookbehind ``(?<=\d)`` blockiert die Substitution, wenn dem ``T`` kein
# Ziffer vorangeht - schuetzt vor falsch-positiven Strips wie ``Bezirk T2024``
# oder ``Text T2024``, wo ``T2024`` semantisch ein Katalog-Marker oder
# Namens-Suffix ist, kein Zeit-Fragment. Fuer die legitime Basic-Form
# ``20240613T143200`` steht die Kompakt-Datum-Ziffer vor dem T; fuer
# Katalog-/Namens-Kontext steht ein Buchstabe oder Whitespace davor.
#
# Nur ``[Tt]`` (kein Whitespace-Trenner) fuer die Kompakt-Form: die
# Whitespace-Form ``20240613 143200`` ist nicht ISO 8601 basic profile und
# koennte in Sammler-Notizen mit Katalog-/Referenz-Nummern (``1985 12345``)
# kollidieren; die Basic-Form-Konvention setzt zwingend ``T`` als Datum-Zeit-
# Trenner. Die 4-oder-6-Ziffern-Alternante (HHMM oder HHMMSS) ist die
# vollstaendige ISO 8601 basic time-Form; 5-Ziffer- oder andere Zwischen-
# Formen sind semantisch undefiniert und bleiben unangetastet.
_TRAILING_TIME = re.compile(
    r"(?:"
    r"[Tt ]\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?"
    r"|(?<=\d)[Tt]\d{4}(?:\d{2})?(?:[.,]\d+)?"
    r")"
    # TZ-Suffix nach dem Zeit-Block: Zulu (``Z``/``z``), numerischer Offset
    # (``+0200``/``+02:00``), spezifisch-mit-Offset (``UTC+2``/``GMT-05:30``/
    # ``UT+01``) oder generischer Named-TZ (``CET``/``EST``/``MEZ``).
    # ``UTC``/``GMT``/``UT`` sind die einzigen TZ-Abkuerzungen, die semantisch
    # sinnvoll einen Offset tragen (Delta-Notation zur Zulu-Zeit; ``CET+2``
    # oder ``EST-1`` waeren doppelt-modifiziert und in der Praxis unueblich).
    # Die spezifische UTC/GMT/UT-Alternante steht vor dem generischen
    # ``[A-Z]{2,5}``, weil beide auf denselben Positionen matchen und die
    # generische Form die Offset-Ziffern sonst uebriglassen wuerde (``GMT``
    # matcht via generischer Alternante, ``+2`` bleibt zurueck, ``\s*$`` schlaegt
    # fehl - der ganze Strip scheitert und das Datum vor dem GMT-Suffix wird
    # nicht mehr erkannt). Optionaler Minuten-Anteil ``:?\d{2}`` deckt die
    # Half-Hour-/Quarter-Hour-Zeitzonen ab (Indien UTC+5:30, Neufundland
    # UTC-3:30, Nepal UTC+5:45), die in Sammler-Notizen aus internationaler
    # Foto-/Fund-Reise oder aus geerbten Etiketten mit non-DACH-Provenienz
    # vorkommen. Bisher fielen alle Formen ``T14:30 GMT+2``/``T14:30:00 UTC-5``/
    # ``T14:30 UTC+05:30`` still auf None, weil weder der numerische Offset-
    # Zweig (``+02:00`` verlangt zwei-stelligen Stunden-Anteil ohne
    # vorangehendes UTC-Wort) noch die generische ``[A-Z]{2,5}``-Alternante
    # (blockt an ``+2``-Suffix nach dem TZ-Namen) matchte - typischer Silent-
    # Datenverlust bei EXIF-Datetimestrings aus GPS-fotografischen Kameras
    # und aus Log-Zeilen internationaler Backup-Rotations-Skripte.
    r"(?:"
    r"\s*[Zz]"
    r"|\s*[+-]\d{2}:?\d{2}"
    r"|\s+(?:UTC|GMT|UT)(?:[+-]\d{1,2}(?::?\d{2})?)?"
    r"|\s+[A-Z]{2,5}"
    r")?\s*$"
)
# DE-Uhrzeit-Trailing-Suffix mit dem "Uhr"-Wortmarker: "13.06.2024 14:30 Uhr",
# "13. Juni 2024, 14 Uhr", "2024-06-13 14:30:00 Uhr.", auch case-insensitive
# ("uhr", "UHR"). In DE-Sammler-Notizen und geerbten Etiketten die uebliche
# Notation, wenn zusaetzlich zum Fund-/Foto-Datum die Uhrzeit erhalten geblieben
# ist ("Fund am 13.06.2024 um 14:30 Uhr", "Foto 13. Juni 2024, 14 Uhr"). Ohne
# expliziten Uhr-Strip fielen alle diese Formen still auf None: der Colon-
# Zweig von :data:`_TRAILING_TIME` strippt zwar den ``14:30``-Teil, laesst
# aber ``13.06.2024 Uhr`` zurueck (der Suffix-Whitelist [A-Z]{2,5} matcht
# das gemischt-case "Uhr" nicht - "UHR" wuerde matchen, ist aber unueblich).
# Die Hour-only-Form "14 Uhr" (Stunde ohne Minuten, DE-Sprech-Alltag: "um
# 14 Uhr") wird vom Colon-Zweig sowieso nicht gefangen, weil dort ``:MM``
# zwingend ist.
#
# Diese Regex fangt beide Formen (Colon-Zeit + Uhr, Hour-only + Uhr) in einem
# Schritt: ``[,\s]+`` als Trenner (Whitespace oder Komma-Praefix wie ``",
# 14:30 Uhr"``), dann 1-2 Stunden-Ziffern, dann optional ``:MM`` und
# ``:SS``, dann optional Whitespace, dann das ``uhr``-Wort (case-insensitive)
# mit optionalem trailing Punkt (``Uhr.`` als abgekuerzte Schlussform in
# Prosa-Notizen). Der abschliessende ``\s*$``-Anker macht die Match-Position
# eindeutig am Zeilenende.
#
# Vor :data:`_TRAILING_TIME` gestrippt in :func:`parse_iso_date`, damit die
# Uhr-Variante nicht durch den Colon-Zweig ohne Uhr-Suffix-Konsum zerfallt
# (der wuerde ``14:30`` strippen und ``13.06.2024 Uhr`` uebriglassen, was
# als kein bekanntes Datum-Muster still auf None faellt). Kein Konflikt mit
# reinen TZ-Suffixen (``UTC``/``CET`` etc.): die brauchen keine vorangehende
# Zeit-Ziffer und werden weiter unten via :data:`_TRAILING_TZ_STANDALONE`
# behandelt.
#
# Bare-Time-Kollisions-Schutz: die Regex verlangt vor der Ziffer einen
# Trenner ``[,\s]+``, sodass ``"14:30 Uhr"`` (keine vorangehende Datum-Zahl)
# nicht matcht - das erste Zeichen ``1`` ist weder Whitespace noch Komma,
# und ohne linken Kontext-Anker faellt der Match nicht rein. Analog fuer
# ``"14 Uhr"`` allein (ohne Datum).
_TRAILING_UHR_TIME = re.compile(
    r"[,\s]+\d{1,2}(?::\d{2}(?::\d{2})?)?\s*uhr\.?\s*$",
    re.IGNORECASE,
)
# DE-/EN-Tageszeit-Trailing-Marker OHNE konkrete Uhrzeit-Ziffer
# ("13.06.2024 morgens", "13. Juni 2024 nachmittags", "2024-06-13 abends",
# "13.06.2024, vormittags."). In Sammler-Notizen weit verbreitet als grobe
# Tageszeit-Angabe zusaetzlich zum Fund-/Foto-Datum ("Fund am 13.06.2024
# nachmittags", "Foto 13. Juni 2024 morgens", "Erwerb 2024-06-13 abends"),
# wenn der genaue Uhrzeit-Zeitpunkt nicht mehr vorlag, aber die Tageszeit
# als Erinnerungs-Anker im Etikett festgehalten wurde. Bisher fielen alle
# diese Formen still auf None: weder :data:`_TRAILING_TIME` (verlangt eine
# Ziffer im Suffix, z.B. ``14:30``) noch :data:`_TRAILING_UHR_TIME`
# (verlangt Ziffer + "Uhr") noch :data:`_TRAILING_TZ_STANDALONE`
# (Whitelist explizit auf IANA-/CLDR-TZ-Abkuerzungen begrenzt) fangen
# die reine Adverb-Form ohne Uhrzeit-Ziffer - aus dem typischen
# Sammler-Etikett "13.06.2024 nachmittags" wurde silenter Funddatum-
# Datenverlust bei der Migration, obwohl das Datum vor dem Tageszeit-
# Suffix eindeutig lesbar ist.
#
# Wortliste: strikte DE-Adverb-Formen der Tageszeit (``morgens``,
# ``vormittags``, ``mittags``, ``nachmittags``, ``abends``, ``nachts``)
# plus EN-Aequivalente (``morning``, ``afternoon``, ``evening``,
# ``night``). Case-insensitive per re.IGNORECASE (Etiketten in
# Grossbuchstaben, Satzanfang mit Grossbuchstabe). Die Alternation ist
# von der laengsten zur kuerzesten Form sortiert, damit Python-re bei
# gleichem Praefix zuerst die spezifischere Form probiert (irrelevant
# hier, weil kein Prefix-Konflikt besteht - ``nachmittags`` und
# ``nachts`` teilen nur ``nach``, dann divergieren sie in Position 4 -
# aber Konvention).
#
# Der linke Trenner ``[,\s]+`` verlangt einen Whitespace-/Komma-Anker
# vor der Adverb-Form, sodass eine reine Wort-Form ohne Datum-Kontext
# (``"morgens"``, ``"abends"``) nicht matcht - das erste Zeichen ``m``
# bzw. ``a`` ist weder Whitespace noch Komma, und ohne linken Kontext-
# Anker faellt der Match nicht rein. Analog schuetzt das Anker-Paar
# ``[,\s]+ ... \s*$`` vor Kollision mit dem Praefix-Fall ``vormittags
# 1985``: dort steht die Tageszeit als *Praefix* vor der Jahreszahl,
# die Regex ankert aber am Zeilenende (nach der Jahreszahl gibt es
# keinen Tageszeit-Suffix), sodass der Trailing-Strip inaktiv bleibt
# und der bestehende Boundary-Prefix-Reject-Test ``vormittags 1985 ->
# None`` unangetastet bleibt.
#
# Der optionale ``[.,]?`` faengt Prosa-Abkuerzungs-Schlussformen
# (``nachmittags.`` als Satz-Ende, ``morgens,`` als Aufzaehlungs-
# Komma) - der abschliessende ``\s*$``-Anker macht die Match-Position
# eindeutig am Zeilenende.
#
# Vor :data:`_TRAILING_TIME` einsortiert in :func:`parse_iso_date`,
# analog zu :data:`_TRAILING_UHR_TIME`: _TRAILING_TIME wuerde an dieser
# Position sowieso nicht matchen (keine Ziffer im Suffix), aber die
# Reihenfolge-Konvention haelt die zwei komplementaeren "Uhrzeit-
# Anmerkungen"-Zweige (Uhr / Tageszeit) direkt nebeneinander und macht
# die Semantik lesbar. Strip + Rekursion analog _TRAILING_UHR_TIME: die
# Tageszeit ist semantische Wert-Anmerkung, keine Datums-Modifikation -
# das ISO-Datum-Output ist identisch zur reinen Datums-Form.
_TRAILING_TAGESZEIT = re.compile(
    r"[,\s]+"
    r"(?:nachmittags|vormittags|morgens|mittags|abends|nachts"
    r"|afternoon|evening|morning|night)"
    r"[.,]?\s*$",
    re.IGNORECASE,
)
# Standalone-Trailing-Zeitzone ohne Zeitanteil ("2024-06-13 UTC", "1985 GMT",
# "13.06.2024 CET", "Juni 2020 MEZ", "2024-06-13Z"). Spiegelt die TZ-Suffix-
# Konvention von :data:`_TRAILING_TIME` auf die Date-Only-Achse: wenn keine
# Zeit angehaengt ist, greift _TRAILING_TIME nicht (das Time-Muster verlangt
# ``T14:30``), und die reine TZ-Abkuerzung faellt bisher stille auf None,
# obwohl das Datum eindeutig lesbar ist. Typische Datenquellen mit
# Date-Only-TZ-Suffix sind System-Logs mit Datum-Rotation ("stone.2024-06-13.UTC.log"),
# Foto-Metadaten-Exporte, in denen der TZ-Marker aus einer Datetime-Zelle in
# ein reines Datum-Feld ueberlaeuft ("photo taken 2024-06-13 UTC"), und
# Sammler-Notizen, in denen die TZ als Kontext-Anmerkung neben dem Fund-Datum
# steht ("13.06.2024 MEZ, Kohler-Aar-Fund"). Bisher war das reiner Silent-
# Funddatum-Datenverlust bei der Migration.
#
# Konzept identisch zu :data:`_TRAILING_ERA_MARKER` / :data:`_TRAILING_APPROX_SUFFIX`:
# die TZ-Angabe ist semantische Wert-Anmerkung ("in welcher Zeitzone wurde
# das Datum notiert"), keine Datums-Modifikation - Strip + Rekursion, das
# ISO-Datum-Output ist identisch zur reinen Form. Der TZ-Marker gehoert
# konzeptionell in die notizen-Spalte, nicht in das ISO-Datum selbst.
#
# Wortliste: explizite Whitelist der gaengigsten IANA-/CLDR-Abkuerzungen
# statt der ``[A-Z]{2,5}``-Klasse aus :data:`_TRAILING_TIME` - fuer Date-Only
# ist die False-Positive-Gefahr hoeher, weil kein Zeit-Anker die TZ-Bedeutung
# stuetzt. Der Whitelist-Ansatz vermeidet Kollisionen mit legitimen 2-5-
# Buchstaben-Suffixen aus Sammlungs-Notizen ("2024 REF", "2024 EOD", "1985 CH"),
# die keine TZ-Semantik tragen. Umfasst:
# - Universelle Zeit: Z (Zulu, ISO 8601-Standard-Suffix fuer UTC), UTC, GMT, UT
# - Europa: CET, CEST, MEZ, MESZ, WET, WEST, EET, EEST, BST (British Summer)
# - Nordamerika: EST, EDT, CST, CDT, MST, MDT, PST, PDT, AKST, AKDT, HST, HDT
# - Asien-Pazifik: JST, KST, IST, HKT, SGT, PHT, ICT, MYT, WIB, WIT, WITA
# - Ozeanien: AEST, AEDT, ACST, ACDT, AWST, AWDT, NZST, NZDT
# - Suedamerika/Afrika: BRT, ART, CLT, ARS, EAT, SAST, WAT, CAT
#
# ``Z`` (Zulu) darf direkt an der Zahl haengen (``2024-06-13Z``, ISO 8601-
# Konvention fuer Zulu-Suffix ohne Zeit), alle anderen Marker verlangen einen
# Whitespace-Trenner (Sammler-Notation-Konvention: ``2024-06-13 UTC``, nicht
# ``2024-06-13UTC``). Case-sensitive: nur Grossbuchstaben, damit zufaellige
# Kleinbuchstaben-Suffixe ("2024 utc", "13.06.2024 cet") als Freitext-Notiz
# gewertet werden und nicht als TZ-Marker (Grossbuchstaben-Konvention der
# IANA-/CLDR-Abkuerzungen).
#
# Vor :data:`_TRAILING_PAREN_REMARK` einsortiert, damit
# ``2024-06-13 UTC (Foto)`` erst die Klammer verliert und dann in der
# Rekursion die TZ - beide Marker sind unabhaengige Kontext-Anmerkungen.
# Nach :data:`_TRAILING_TIME` einsortiert, damit
# ``2024-06-13T14:30 UTC`` (Date+Time+TZ) den kompletten Zeit+TZ-Block via
# _TRAILING_TIME strippt und die Date-Only-Variante nur den Rest-Fall
# behandelt.
_TRAILING_TZ_STANDALONE = re.compile(
    r"(?:"
    r"Z"
    # UTC/GMT/UT tragen semantisch sinnvoll einen optionalen numerischen Offset
    # (``UTC+2``/``GMT-05:30``/``UT+01:00``) - Delta-Notation zur Zulu-Zeit.
    # Vor der generischen Named-TZ-Alternante einsortiert, damit die spezifische
    # Form mit Offset gemeinsam gestrippt wird und nicht ``+2`` nach dem
    # generischen ``GMT``-Strip zurueckbleibt (was den ``\s*$``-Anker
    # scheitern liesse und das Datum vor dem TZ-Suffix verlieren wuerde).
    # Optionaler Minuten-Anteil ``:?\d{2}`` deckt Half-Hour-Zeitzonen ab
    # (Indien UTC+5:30, Neufundland UTC-3:30, Nepal UTC+5:45), die in
    # Sammler-Notizen aus internationaler Foto-/Fund-Reise-Provenienz oder
    # aus geerbten Etiketten mit non-DACH-Herkunft vorkommen. Bisher fielen
    # alle Date-Only-Formen ``2024-06-13 GMT+2``/``13.06.2024 UTC-05:30``/
    # ``Juni 2024 GMT+1`` still auf None, weil weder die spezifische Whitelist
    # den Offset-Suffix akzeptierte noch der ``\s*$``-Anker nach reinem
    # ``GMT``-Match die verbleibenden ``+2``-Ziffern konsumieren konnte -
    # typischer Silent-Datenverlust bei EXIF-Foto-Metadaten aus GPS-Kameras
    # ohne Zeit-Komponente im Sichtfeld und bei Log-Zeilen aus internationalen
    # System-Rotations-Skripten mit reinem Datum-plus-TZ-Marker.
    r"|\s+(?:UTC|GMT|UT)(?:[+-]\d{1,2}(?::?\d{2})?)?"
    r"|\s+(?:"
    r"CET|CEST|MEZ|MESZ|WET|WEST|EET|EEST|BST"
    r"|EST|EDT|CST|CDT|MST|MDT|PST|PDT|AKST|AKDT|HST|HDT"
    r"|JST|KST|IST|HKT|SGT|PHT|ICT|MYT|WIB|WIT|WITA"
    r"|AEST|AEDT|ACST|ACDT|AWST|AWDT|NZST|NZDT"
    r"|BRT|ART|CLT|ARS|EAT|SAST|WAT|CAT"
    r")"
    r")\s*$"
)
# Trailing-Satzzeichen ("2024-06-13.", "1985!", "13. Juni 2024;").
# Geerbte Sammlungs-Notizen sind oft ganze Saetze mit Datum am Ende; das Punkt-
# /Doppelpunkt-Suffix gehoert nicht zum Datum selbst und wird vor dem Re-Parsing
# entfernt. ISO-Datumformate enden auf Ziffern, kollidieren also nicht.
_TRAILING_PUNCT = re.compile(r"[.,;:!?]+\s*$")
# Trailing parenthesized remark ("13.06.2024 (Foto)", "ca. 1985 [Schaetzung]",
# "Sommer 1985 {geerbt}", "Juni 2024 (verifiziert)"). In Sammlungs-Notizen sehr
# verbreitet als Kontext-/Annotations-Suffix nach dem Datum: Foto-/Pflege-
# Vermerke ("(Foto)"), Provenienz ("(geerbt von Onkel)"), Verlaesslichkeits-
# Hinweise ("(verifiziert)", "(Schaetzung)"), Quelle ("(Auktion 2024)"). Drei
# Klammer-Varianten: runde Klammern (haeufigste Form), eckige Klammern
# (technische/maschinen-lesbare Annotation), geschwungene Klammern (selten,
# aber spec-konform). Bisher fielen alle drei Klammer-Annotationen am
# Ende auf None, weil die strukturellen Pattern den Klammer-Suffix als
# Format-Bruch sehen und _TRAILING_PUNCT nur Satzzeichen [.,;:!?] abdeckt,
# nicht die strukturelle Klammer-Form - aus einem typischen Sammler-
# Etikett wie "13.06.2024 (Foto)" wurde silenter Funddatum-Datenverlust.
# Single-Level (keine geschachtelten Klammern im Annotations-Inhalt); fuer
# verschachtelte Annotationen ("(Foto (gut))") ergaenzt der Balanced-Bracket-
# Helper :func:`_strip_trailing_balanced_bracket` diese Regex: er verfolgt
# Klammer-Tiefe rueckwaerts vom Zeilenende und strippt eine trailing Klammer-
# Gruppe erst dann, wenn ein passender Oeffner mit Tiefe 0 gefunden wurde -
# sodass ``"(Foto (gut))"`` in einem Schritt aufgeloest wird, ohne dass die
# reine Regex-Kaskade rekursiv scheitert (die Regex verlangt ``$``-Anker und
# schliesst geschachtelte Klammern ueber die Nicht-Klammer-Zeichenklasse aus).
# Vor _TRAILING_PUNCT einsortiert, weil parenthesierte Annotation eine
# eigenstaendige strukturelle Form ist und nicht erst durch Satzzeichen-
# Vorstufe gefiltert werden muss.
# Strip + Rekursion analog _TRAILING_TIME/_TRAILING_PUNCT.
_TRAILING_PAREN_REMARK = re.compile(
    r"\s*[\(\[\{][^\(\)\[\]\{\}]*[\)\]\}]\s*$"
)
# Zuordnung Closer -> Opener fuer den Balanced-Bracket-Strip. Nur die drei
# Standard-Klammer-Paare (runde/eckige/geschwungene) werden erkannt; wenn
# der Input eine gemischte Kombination enthaelt (``[Foto)``, ``(Foto]``),
# faellt der Strip transparent aus und die einfachere :data:`_TRAILING_PAREN_REMARK`-
# Regex uebernimmt (die auch nicht-passende Paare stripped, aber nur ohne
# Nest-Inhalt).
_TRAILING_BRACKET_PAIRS: dict[str, str] = {")": "(", "]": "[", "}": "{"}


def _strip_trailing_balanced_bracket(s: str) -> str | None:
    """Strippt am Ende von ``s`` eine balancierte Klammer-Gruppe inkl. Nest.

    Traeger-Semantik: das letzte nicht-Whitespace-Zeichen muss ein Closer sein
    (``)``/``]``/``}``); rueckwaerts wird die Klammer-Tiefe verfolgt, bis der
    passende Opener mit Tiefe 0 gefunden wird. Der Rueckgabe-String ist ``s``
    ohne die trailing Klammer-Gruppe (und ohne den nachgelaufenen Whitespace);
    ohne passenden Opener (unbalanciert, oder gemischtes Paar) wird ``None``
    zurueckgegeben - der Caller faellt dann auf die einfachere Regex-Strip-
    Kaskade oder auf Rueckgabe ``None`` zurueck.

    Ergaenzt :data:`_TRAILING_PAREN_REMARK` fuer geschachtelte Annotationen
    (``"(Foto (gut))"``, ``"[Sammlung (Muster (jun.))]"``), die durch die
    reine Regex nicht abgedeckt sind (die Nicht-Klammer-Zeichenklasse
    schliesst den inneren Nest-Inhalt strukturell aus, und der ``$``-Anker
    verhindert einen iterativen Innen-nach-aussen-Strip).
    Nur andere Klammer-Zeichen desselben Typs werden bei der Tiefen-
    Zaehlung beruecksichtigt - Fremd-Klammern (``[`` innerhalb einer
    ``()``-Gruppe) sind Content und stoeren die Balanced-Erkennung nicht.
    """
    stripped = s.rstrip()
    if not stripped:
        return None
    closer = stripped[-1]
    opener = _TRAILING_BRACKET_PAIRS.get(closer)
    if opener is None:
        return None
    depth = 0
    for i in range(len(stripped) - 1, -1, -1):
        c = stripped[i]
        if c == closer:
            depth += 1
        elif c == opener:
            depth -= 1
            if depth == 0:
                return stripped[:i].rstrip()
    return None
# Trailing Aera-Marker (DE/EN/Latein) nach dem Datum: "1985 n. Chr.",
# "1985 nach Christus", "500 v. Chr.", "500 vor Christus", "1985 AD",
# "1985 A.D.", "1985 CE", "1985 C.E.", "500 BC", "500 B.C.", "500 BCE",
# "500 B.C.E.". Traditionelle Museums-Etiketten- und Auktions-Kataloge-
# Praxis in Sammlungen mit kulturhistorischer/archaeologischer Provenienz,
# wo das Datum um die Zeitrechnungs-Aera explizit qualifiziert wird -
# besonders in geerbten Sammlungen aus akademischen Kontexten und in
# aelteren Referenzen aus dem 19./20. Jhdt., wo AD/BC im wissenschaftlichen
# Diskurs Standard war. Bisher fielen alle diese Formen stille auf None,
# weil die strukturellen Datums-Patterns den Aera-Suffix als Format-Bruch
# sehen und weder _TRAILING_TIME (Zeit-Suffix) noch _TRAILING_PAREN_REMARK
# (Klammer-Annotation) noch _TRAILING_PUNCT (nur die letzten Satzzeichen)
# die mehr-Token-Wort-Marker-Form abdecken - aus einem typischen Sammler-
# Etikett wie "1985 n. Chr." wurde silenter Funddatum-Datenverlust.
#
# Spiegelt das Konzept von _APPROX_PREFIX/_BOUNDARY_PREFIX (Praefix wird
# gestrippt, Datum bleibt unveraendert) auf die Suffix-Achse: die Aera-
# Angabe ist semantische Wert-Anmerkung ("welche Zeitrechnungs-Konvention"),
# keine Datums-Modifikation - das ISO-Datum-Output ist identisch zur reinen
# Form. AD/n. Chr./CE/u. Z. liegen im gueltigen 1800..2999-Band; BC/v. Chr./
# BCE/v. u. Z. liegen ausserhalb (Jahres-Range-Pruefung filtert sie
# transparent auf None, konsistent mit "500" -> None ohne Aera-Marker).
# Strip + Rekursion analog _TRAILING_TIME/_TRAILING_PAREN_REMARK/
# _TRAILING_PUNCT.
#
# BCE-Muster (b\.?\s*c\.?\s*e\.?) vor dem BC-Muster (b\.?\s*c\.?), damit
# die spezifischere 3-Buchstaben-Form nicht durch das kuerzere BC-Pattern
# vorzeitig konsumiert wird. AD/BC/CE nur mit obligatorischer Anwesenheit
# eines Wortes vor der Aera-Angabe (dass \s+ mit mindestens einem Whitespace
# vorangeht), damit z.B. "AD 1985" (leading-Form) nicht versehentlich als
# alles-Aera gelesen wird - die leading-Form wird durch das symmetrische
# :data:`_LEADING_ERA_MARKER` mit ``^`` und ``\s+`` am Ende erfasst.
# Interne Whitespaces innerhalb der Aera-Angabe optional ("A.D.", "A D",
# "A. D.") mit \s* zwischen den Buchstaben. Case-insensitive akzeptiert
# (Etiketten in Grossbuchstaben/Kleinbuchstaben/Mischform sind alle in
# geerbten Sammlungs-Notizen zu finden).
#
# DDR-/moderne konfessionsneutrale DE-Aera-Notation "u. Z." (unserer
# Zeitrechnung, CE-Aequivalent) und "v. u. Z." (vor unserer Zeitrechnung,
# BCE-Aequivalent). Standard-Konvention der DDR-Fachliteratur (Deutsche
# Akademie der Wissenschaften Berlin, ost-deutsche archaeologische und
# mineralogische Publikationen bis 1990) und in der modernen sekulaeren
# DE-Wissenschaftssprache verbreitet, wo Autoren die christlich-konfessio-
# nelle "n. Chr."-Notation durch die neutrale Aera-Angabe ersetzen (analog
# zur englischsprachigen CE/BCE-Konvention, die "AD/BC" ablost). Kommt in
# geerbten Sammlungen mit ost-deutscher Provenienz und in aelteren
# Referenzen aus DDR-Museums-Eingangsbuechern vor; auch in modernen
# westdeutschen Publikationen mit dezidiert neutraler Datumsangabe. Ohne
# diese Alternation fielen typische Etiketten wie "500 v. u. Z." oder
# "1985 u. Z." stille auf None, obwohl semantisch identisch zur bereits
# unterstuetzten CE/BCE- und n. Chr./v. Chr.-Notation. Die v. u. Z.-Form
# (drei Token) muss VOR der u. Z.-Form (zwei Token) alterniert werden -
# spiegelt die BCE-vor-BC-Reihenfolge, sonst konsumiert die u. Z.-Alter-
# nation nur den "u. Z."-Anteil und laesst "v." als trailing zurueck, was
# nach dem _TRAILING_PUNCT-Strip zu "1985 v" fuehrt (nicht parsierbar).
# Lateinische Vollform ``Anno Domini`` (deutsch: "im Jahr des Herrn") ist die
# ursprungliche kirchen-lateinische Notation, aus der die verbreitete Kurzform
# ``A.D.``/``AD`` hervorgegangen ist. In geerbten Sammlungen mit museal-
# ecclesialer Provenienz (Reliquiare, kirchliche Reliquien-/Mineralien-
# Sammlungen aus Kloster-Bestaenden, aeltere Auktions-Kataloge mit
# Papst-Aera-Bezug, Grabinschriften-Fotografie-Sammlungen, historisch-
# archaeologische Publikationen aus dem 18./19. Jhdt. mit puristischer
# Latein-Konvention) sowie in modernen kalligrafisch-formalen Etiketten
# (Sonderausstellungen, festliche Gedenktafeln, "In Memoriam"-Karten mit
# Fund-/Erwerbsdatum) taucht die Vollform statt der Kurzform auf. Bisher
# fielen alle Etiketten mit ``Anno Domini``-Marke stille auf None: die
# vorhandene ``a\.?\s*d\.?``-Alternante deckt nur die Kurzform ab, und die
# Vollform ``Anno Domini`` matcht nicht (``anno`` steht vor dem ``d``, das
# Pattern verlangt aber ``a`` unmittelbar vor optionalem ``.`` und dann
# ``d``). Aus einem typischen Museums-Etikett "1985 Anno Domini" wurde
# damit silenter Funddatum-Datenverlust; die Kurzform "1985 AD" liefert
# das gleiche Ergebnis "1985-01-01", aber die Vollform-Etiketten (die
# gerade in kunsthistorischen/kirchenhistorischen Sammlungen die
# formell-korrekte Notation sind) blieben in der Migration unerkannt.
# Semantisch identisch zur Kurzform ``AD``/``A.D.`` (Christlich-Positive-
# Aera): der Strip laesst den Jahres-Anker unveraendert, die Aera-Info
# gehoert in Freitext (notizen). Trennwhitespace ``\s+`` zwischen ``anno``
# und ``domini`` deckt sowohl die typografisch-saubere ``Anno Domini``-
# Form ab als auch die Kompakt-Notation ``Anno  Domini`` (Doppel-Space
# aus Excel-Auto-Fill) und ``Anno\tDomini`` (Tab-Trenner aus TSV-Exports).
# Case-Insensitivitaet spiegelt die uebrigen Aera-Marker-Alternanten
# (``AD``/``ad``/``Ad`` transparent identisch). Kollisionsfrei zu bereits
# vorhandenen Marker-Alternanten: ``anno`` ist kein Praefix von ``n.
# chr.``/``v. chr.``/``a. d.``/``b. c.``/``c. e.``/``u. z.``, und ``domini``
# ist kein Wort in irgendeiner der uebrigen Marker-Klassen. Kollisionsfrei
# zu :data:`_APPROX_PREFIX` (``anno`` ist kein Praezisions-Marker),
# :data:`_TRAILING_APPROX_SUFFIX` (spiegelbildlich), :data:`_TEMPORAL_PREFIX`
# (dort sind ``jahr``/``jahre``/``year`` gelistet, nicht ``anno``).
# Position VOR ``a\.?\s*d\.?``: die Kurzform-Alternante wuerde bei
# case-insensitiven Match den ``a``-Praefix von ``anno`` verschlingen (weil
# ``\.?\s*`` optional ist und der ``d`` gefolgt von whitespace matchen
# koennte), daher muss die spezifischere Vollform links stehen. Analog
# zur BCE-vor-BC-Reihenfolge (spezifischer zuerst) und zur v.u.Z.-vor-
# u.Z.-Reihenfolge (Praefix-Vermeidung).
_TRAILING_ERA_MARKER = re.compile(
    r"\s+(?:"
    r"n\.?\s*chr\.?"           # n. Chr. / n.Chr. / n Chr. / nChr.
    r"|nach\s+christus"        # nach Christus (Vollform)
    r"|v\.?\s*chr\.?"          # v. Chr. / v.Chr. / v Chr. / vChr.
    r"|vor\s+christus"         # vor Christus (Vollform)
    r"|anno\s+domini"          # Anno Domini (Latein-Vollform von A.D.)
    r"|a\.?\s*d\.?"            # AD / A.D. / A. D. / A D
    r"|b\.?\s*c\.?\s*e\.?"     # BCE / B.C.E. / B. C. E. (vor BC-Muster!)
    r"|b\.?\s*c\.?"            # BC / B.C. / B. C. / B C
    r"|c\.?\s*e\.?"            # CE / C.E. / C. E. / C E
    r"|v\.?\s*u\.?\s*z\.?"     # v. u. Z. / v.u.Z. / vuZ (vor u.Z.-Muster!)
    r"|vor\s+unserer\s+zeitrechnung"  # vor unserer Zeitrechnung (Vollform)
    r"|u\.?\s*z\.?"            # u. Z. / u.Z. / u Z / uZ
    r"|unserer\s+zeitrechnung"  # unserer Zeitrechnung (Vollform)
    r")\s*$",
    re.IGNORECASE
)
# Leading Aera-Marker (DE/EN/Latein) vor dem Datum: "AD 1985", "A.D. 1985",
# "CE 1985", "n. Chr. 1985", "nach Christus 1985", "v. Chr. 500", "BCE 500".
# Spiegelt :data:`_TRAILING_ERA_MARKER` auf die Praefix-Achse: waehrend die
# Trailing-Form ("1985 AD") die im wissenschaftlichen Diskurs typische
# Postfix-Setzung abdeckt, kommt die Leading-Form ("AD 1985") in aelteren
# Museums-Etiketten mit lateinischer Datierungs-Grammatik ("Anno Domini
# 1985" -> "AD 1985"), in englischsprachigen Auktions-Katalogen und in
# akademischen Referenzen aus dem 19./20. Jhdt. vor, wo die Aera-Praefix-
# Konvention ueblich war. Bisher fielen alle Leading-Formen stille auf None,
# weil _TRAILING_ERA_MARKER strikt mit ``\s*$`` am Ende ankert (die
# Position-Semantik der Trailing-Form) - aus einem typischen Etikett wie
# "AD 1985" wurde silenter Funddatum-Datenverlust bei der Migration.
#
# Konzept identisch zu _TRAILING_ERA_MARKER: die Aera-Angabe ist semantische
# Wert-Anmerkung ("welche Zeitrechnungs-Konvention"), keine Datums-
# Modifikation - Strip + Rekursion, das ISO-Datum-Output ist identisch zur
# reinen Form. AD/n. Chr./CE liegen im gueltigen 1800..2999-Band; BC/v. Chr./
# BCE liegen ausserhalb (Jahres-Range-Pruefung filtert sie transparent auf
# None, konsistent mit "500" -> None ohne Aera-Marker).
#
# Vor _BOUNDARY_PREFIX in parse_iso_date einsortiert (siehe dortigen Aufruf),
# weil die Formen "vor Christus 1985" und "nach Christus 1985" mit "vor"/
# "nach" beginnen - _BOUNDARY_PREFIX wuerde sonst nur "vor "/"nach "
# strippen und "Christus 1985" als Rest liefern, der keine der Struktur-
# Patterns matcht. Die Leading-Era-Pruefung braucht das obligatorische
# "christus"/"chr" nach "vor"/"nach", sodass reines "vor 1985" ohne
# Christus-Marker weiterhin durch _BOUNDARY_PREFIX (auch weiter unten in
# der Kaskade) als Boundary-Praefix erkannt wird - kein Konflikt.
#
# ``\s+`` am Ende (statt ``$``-Anker) verlangt ein Datum-Wort nach der Aera-
# Angabe, damit reines "AD" (ohne Datum) NICHT strippt und ueber die
# Struktur-Patterns transparent auf None faellt (kein Freitext-Ratespiel).
# BCE/B.C.E. wieder vor BC/B.C. wegen der Praefix-Praeferenz der Regex-
# Alternation (spezifischer zuerst).
_LEADING_ERA_MARKER = re.compile(
    r"^(?:"
    r"n\.?\s*chr\.?"           # n. Chr. / n.Chr. / n Chr. / nChr.
    r"|nach\s+christus"        # nach Christus (Vollform)
    r"|v\.?\s*chr\.?"          # v. Chr. / v.Chr. / v Chr. / vChr.
    r"|vor\s+christus"         # vor Christus (Vollform)
    r"|anno\s+domini"          # Anno Domini (Latein-Vollform von A.D.)
    r"|a\.?\s*d\.?"            # AD / A.D. / A. D. / A D
    r"|b\.?\s*c\.?\s*e\.?"     # BCE / B.C.E. / B. C. E. (vor BC-Muster!)
    r"|b\.?\s*c\.?"            # BC / B.C. / B. C. / B C
    r"|c\.?\s*e\.?"            # CE / C.E. / C. E. / C E
    r")\s+",
    re.IGNORECASE
)
# Trailing Annaeherungs-Suffix (DE/EN) - spiegelt :data:`_APPROX_PREFIX` auf die
# Suffix-Achse: waehrend die Leading-Form ("ca. 1985", "circa 2020") die im
# wissenschaftlichen Diskurs typische Praefix-Setzung abdeckt, kommt die
# Trailing-Form ("1985 ca.", "2020 circa", "13.06.2024 vermutlich", "Juni 2020
# ungefaehr", "1985 wahrscheinlich") in geerbten Sammlungs-Notizen sehr
# verbreitet vor: Etiketten und Tagebuch-Eintraege, in denen der Vorbesitzer
# das Datum voranstellt und den Praezisions-Marker nachtraeglich anfuegt,
# oft nach spaeterer Nachpruefung ("Fund 1985 ca. - Katalog-Recherche 2010
# ergab kein exaktes Datum"). Bisher fielen alle Trailing-Formen stille auf
# None, weil _APPROX_PREFIX strikt mit ``^`` ankerkt (die Position-Semantik
# der Leading-Form) - aus einem typischen Etikett wie "1985 ca." wurde
# silenter Funddatum-Datenverlust bei der Migration.
#
# Konzept identisch zu _APPROX_PREFIX / _TRAILING_ERA_MARKER: die Praezisions-
# Angabe ist semantische Wert-Anmerkung ("welche Verlaesslichkeit"), keine
# Datums-Modifikation - Strip + Rekursion, das ISO-Datum-Output ist identisch
# zur reinen Form. Wortliste spiegelt _APPROX_PREFIX ohne die stark
# ambivalenten Kurzformen "um"/"gegen" (die sowohl als Praeposition wie als
# temporaler Konnektor auftauchen und am Zeilenende in Sammler-Notizen fast
# nur die Praepositions-Bedeutung tragen ("Foto 1985 um 14 Uhr" - hier ist
# "um" eine Uhrzeit-Praeposition, kein Naeherungsmarker) und die typografischen
# Approximations-Symbole ``~``/``≈`` (die als Trailing-Marker in Sammler-
# Notizen nicht ueblich sind - sie stehen konventionell nur vor dem Wert
# als Approximations-Marker, spiegelt die Konvention der mathematischen und
# LaTeX-Notation).
#
# ``\s+`` am Anfang (statt ``$``-Anker allein) verlangt einen Whitespace vor
# dem Suffix, damit "ca. 1985" (leading) NICHT versehentlich als "ca. 1985"
# ohne Whitespace-Trenner am Ende passt und "ca." als Suffix konsumiert wird
# (waere im gestrippten Rest "ca." isoliert, matcht ohnehin keine Datums-
# Struktur, ist aber sauberer via Whitespace-Grenze). Case-insensitive spiegelt
# _APPROX_PREFIX. Vor _TRAILING_TIME einsortiert, damit "1985 ca." vor der
# Zeit-Strip-Kaskade den Praezisions-Marker sauber verliert (die Punkt-am-Ende
# aus "ca." wuerde sonst durch _TRAILING_PUNCT gestrippt und "1985 ca" bliebe
# als Rest, der keine Struktur matcht).
_TRAILING_APPROX_SUFFIX = re.compile(
    r"\s+(?:"
    r"ca\.?|circa|approx\.?|approximately"
    r"|around|about|roughly|estimated|est\."
    r"|etwa|vermutlich"
    r"|sch[äa]tzungsweise|schaetzungsweise"
    r"|ungef[äa]hr|ungefaehr"
    # Past-Partizip ``geschätzt``/``geschaetzt`` als Trailing-Praezisions-
    # Marke ("1985 geschätzt", "Juni 2024 geschaetzt"). Spiegelt den
    # gleichnamigen Eintrag in :data:`_APPROX_PREFIX` auf die Suffix-Achse;
    # DE/EN-Symmetrie zu ``estimated`` (Past-Partizip, bereits gelistet)
    # und Halbdopplung zur adverbialen Form ``sch[äa]tzungsweise`` als
    # verkuerzte Sammler-Notiz-Variante.
    r"|gesch[äa]tzt|geschaetzt"
    r"|wahrscheinlich|m[öo]glicherweise|moeglicherweise"
    r"|evtl\.?|eventuell"
    # Hearsay-/Zuschreibungs-Marker (DE ``angeblich``, EN ``allegedly`` /
    # ``supposedly`` / ``reportedly`` / ``purportedly`` / ``presumably``) -
    # spiegelt den gleichnamigen Block in :data:`_APPROX_PREFIX` auf die
    # Trailing-Achse. Sammler-Notizen mit Datum-voran + Provenienz-Marker
    # nachgeschoben ("1985 angeblich vom Aare-Gebiet", "Juni 2024 supposedly
    # von Zermatt-Boerse", "1995 reportedly Tucson-Fund"). Konvention
    # identisch zu den uebrigen Wahrscheinlichkeits-Marken: Strip + Rekursion,
    # das ISO-Datum-Output bleibt zur reinen Form identisch, der Hearsay-
    # Marker gehoert konzeptionell in die notizen-Spalte.
    r"|angeblich"
    r"|perhaps|possibly|maybe|presumably"
    r"|allegedly|supposedly|reportedly|purportedly"
    r")\s*$",
    re.IGNORECASE,
)
# Trailing "und folgende Jahre"-Suffix (DE-Bibliografie-/Zitat-Standard "ff."
# und "f."). In geerbten Sammlungs-/Museums-Notizen und in akademischen
# Referenzen sehr verbreitet, um eine offene Jahres-Spanne knapp zu markieren:
# ``1985 ff.`` (= 1985 und 2+ folgende Jahre), ``1985 f.`` (= 1985 und 1
# folgendes Jahr). Herkunft aus der klassischen Zitier-Praxis (Duden K104,
# DIN 1505, Bibliografie-Guides der grossen Universitaets-Bibliotheken) und
# in Museums-Etiketten fuer Erwerbs-/Bearbeitungs-Zeitraeume ohne festes
# End-Datum ("Sammlung Meier, 1985ff." = ab 1985 laufend erweitert). Bisher
# fielen alle Formen still auf None: die Marker ``f``/``ff`` sind kein
# Datums-Bestandteil und fielen nicht in eine der Struktur-Patterns; Rest
# nach der 4-Ziffer-Zahl blockte das ``$``-Anker-Matching von :data:`_YEAR_ONLY`.
# Semantik analog zu :data:`_YEAR_RANGE` / :data:`_YEAR_RANGE_WORD` /
# :data:`_YEAR_RANGE_BETWEEN`: das Startjahr wird als ISO-Datum ausgegeben
# (Spanne-Start, Konvention identisch zu ``1985-1990`` -> ``1985-01-01``).
# Die Info "und folgende" ist semantische Wert-Anmerkung ("offenes End-Datum")
# und keine Datums-Modifikation - der bekannte Anker ist das Start-Jahr, das
# nachgelagerte "und folgende" bleibt im Freitext (notizen).
#
# Konzept identisch zu :data:`_TRAILING_APPROX_SUFFIX` / :data:`_TRAILING_ERA_MARKER`:
# Strip + Rekursion, das eigentliche Parsen des Rest-Datums erledigt
# parse_iso_date via Rekursion. Verkettung mit anderen Suffix-/Praefix-
# Formen funktioniert transparent ("1985 ff., geschaetzt" wird via
# _TRAILING_APPROX_SUFFIX auf "1985 ff., " reduziert, via _TRAILING_PUNCT
# auf "1985 ff", via _TRAILING_FOLLOWING_SUFFIX auf "1985" und final via
# _YEAR_ONLY auf "1985-01-01").
#
# Zwei Positions-Klassen fuer den Trenner vor dem Marker:
#   * ``\s+`` deckt die Standard-Notation mit Leerzeichen ab ("1985 ff.",
#     "1985 f.", "Juni 2024 ff.") - typisch fuer typografisch sauber
#     gesetzte Museums-Etiketten und akademische Referenzen mit Punkt-
#     nach-Abkuerzung-Konvention.
#   * ``(?<=\d)`` deckt die Kompakt-Notation ohne Leerzeichen ab
#     ("1985ff", "1985ff.", "1985f", "1985f.") - typisch fuer knappe
#     Sammler-Karteikarten-Notizen und Tabellen-Cell-Eintraege mit
#     Platz-Ersparnis, wo der Sammler den Trenner weglaesst und den
#     Marker direkt an das Jahr klebt. Das Lookbehind auf eine Ziffer
#     schuetzt vor Match-Positionen mitten in Woertern ("Auffall" endet
#     mit "l", nicht "f", also kein Match; "1985f" endet mit "f" nach
#     einer Ziffer, also Match).
#
# ``ff?`` matcht sowohl die Einfachform (``f`` = "und 1 folgendes Jahr")
# als auch die Doppelform (``ff`` = "und 2+ folgende Jahre"); beide sind
# semantisch aequivalent fuer die ISO-Datums-Auswertung (Start-Jahr).
# ``\.?`` deckt die Abkuerzungs-Punkt-Konvention der DIN 5008-/DUDEN-
# Praxis ab (``ff.`` mit Punkt ist der Standard, ``ff`` ohne Punkt ist
# in Kurzsatz-Notizen ueblich). ``\s*$`` blockt False-Positives im Wort-
# Inneren: der Marker muss am Zeilenende stehen, sonst waere die Marke
# semantisch nicht als "und folgende" lesbar.
#
# Case-insensitive spiegelt die Konvention der uebrigen Trailing-Suffixes
# (Museums-Etiketten in Grossbuchstaben, Mischform-Notationen aus
# handschriftlichen Vorbesitzer-Notizen).
#
# Kollisionsfreiheit zu bestehenden Patterns:
# * :data:`_TRAILING_APPROX_SUFFIX`: alle dortigen Marker sind Voll-Woerter
#   ohne Kollision mit ``f``/``ff`` (das kuerzeste Wort ist ``ca``, 2 Zeichen,
#   aber nicht "f").
# * :data:`_TRAILING_ERA_MARKER`: die Aera-Markiernug ("n. Chr.", "AD", "BC",
#   "BCE", "CE") kollidiert nicht mit "f"/"ff".
# * Monatsnamen und ihre Kurzformen: Kein Monatsname endet auf einem
#   einzelnen "f" oder "ff" (Feb/Sep/Jan/Jun etc. enden auf andere
#   Buchstaben). Die Roemische Notation (I..XII) enthaelt kein "f".
# * :data:`_YEAR_ONLY`, :data:`_YEAR_RANGE`, :data:`_DECADE`, etc.: alle
#   Patterns matchen strikt Ziffern-basierte Strukturen ohne Buchstaben-
#   Suffix. Ein wortbestandhaltiger Rest wird durch das Strip
#   transparenter gemacht, nicht verdeckt.
# * Datums-Tokens mit direkter Ziffer-Buchstaben-Nachbarschaft (etwa
#   Kompakt-Formen wie "202412"): das Lookbehind matcht auf die letzte
#   Ziffer - aber die letzte Ziffer wird nicht konsumiert, sodass die
#   Struktur-Patterns (_COMPACT_YEAR_MONTH, %Y%m%d, ISO_ORDINAL) weiter
#   greifen koennen. Der Strip greift nur, wenn nach der Ziffer wirklich
#   ein ``f``/``ff`` steht.
_TRAILING_FOLLOWING_SUFFIX = re.compile(
    r"(?:\s+|(?<=\d))ff?\.?\s*$",
    re.IGNORECASE,
)
# Umschliessende Klammern/Anfuehrungszeichen aus zitierten Datumsangaben:
# "(2024)", "[2024-06-13]", '"13. Juni 2024"', '„Sommer 1985"'.
# Genau ein Paar wird gestrippt; danach Re-Parsing per Rekursion.
# Englische typografische Anfuehrungszeichen (U+201C / U+201D Doppel; U+2018 /
# U+2019 Einzel) sind Standard-Output von Word-/Office-Autoformat in englischen
# Texten und sehr verbreitet in Foto-Captions, Auktions-Beschreibungen und
# Sammlungs-Notizen, wo der Schreiber Datumsangaben mit "smart quotes" zitiert.
# Bisher fielen Eingaben wie ``"2024-06-13"`` (U+201C..U+201D) auf None, obwohl
# semantisch identisch zur ASCII-Quote-Form - die Single-Source-of-Truth
# (Datum) ging stillschweigend verloren. Komplementaer zu den bereits gelisteten
# Single-Char-Identicals (ASCII '/' /'`'), die nur eine Doppelung als oeffnend+
# schliessend sind, und zur German-Form (U+201E + U+201C als „...“).
_BRACKET_PAIRS: tuple[tuple[str, str], ...] = (
    ("(", ")"), ("[", "]"), ("{", "}"),
    ('"', '"'), ("'", "'"), ("`", "`"),
    ("«", "»"), ("‹", "›"),
    ("„", "\""), ("„", "“"), ("‚", "‘"),
    # Englisch typografisch ("..."): U+201C "left double" + U+201D "right double"
    ("“", "”"),
    # Englisch typografisch einzel ('...'): U+2018 "left single" + U+2019 "right single"
    ("‘", "’"),
)
# ISO 8601 mit Zeitanteil: "2024-06-13T10:00:00", "2024-06-13 10:00:00Z",
# auch EXIF-Stil "2024:06:13 10:00:00" → Zeit wird verworfen, nur Datum bleibt.
# Sekunden-Dezimalbruch akzeptiert sowohl Punkt als auch Komma als Trennzeichen
# (ISO 8601 schreibt Komma als bevorzugten Dezimal-Separator vor; EU-Locales
# nutzen Komma als Default - der Zeitanteil wird ohnehin verworfen, daher
# spielt das fuer das ISO-Datum-Output keine Rolle, aber das Pattern muss
# matchen, sonst faellt die Eingabe auf None).
_ISO_DATETIME = re.compile(
    r"^\s*(\d{4})[-:/.](\d{1,2})[-:/.](\d{1,2})"
    r"[Tt ]\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?"
    r"(?:\s*[Zz]|\s*[+-]\d{2}:?\d{2}|\s+[A-Z]{2,5})?\s*$"
)

# Monatsnamen (Deutsch + Englisch, lang/kurz, ohne Punkt; Umlaute via Normalisierung).
# Identische Kuerzel (Jan/Feb/Mar/Apr/Jun/Jul/Aug/Sep/Nov) decken beide Sprachen ab;
# die englisch-spezifischen Eintraege sind May/Oct/Dec sowie die vollen Formen.
_MONTH_NAMES: dict[str, int] = {
    "januar": 1, "january": 1, "jan": 1,
    "februar": 2, "february": 2, "feb": 2,
    "maerz": 3, "marz": 3, "march": 3, "mar": 3, "mrz": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "december": 12, "dez": 12, "dec": 12,
    # Italienische Monatsnamen (Ticino / italienische Schweiz sowie geerbte
    # Sammler-Notizen aus italienischen Alpen-/Dolomiten-Fundorten) - alle
    # ASCII, keine Akzente in italienischen Monatsnamen (im Gegensatz zu
    # franzoesisch fev/aout/dec), daher keine Regex-/Character-Class-Aenderung
    # noetig. Kollisionsfrei zum DE/EN-Bestand, weil identische Kuerzel
    # (mar/apr/nov) und Zwischenpaare (mag=mai, giu=juni, lug=juli, ago=aug,
    # sett=sept, ott=okt, dic=dez) alle auf denselben Monat abbilden -
    # semantisch identisch mit den DE/EN-Alternativen. Die dritte Amtssprache
    # Rumantsch (Bundesamts-Statistik: ~0.5% Bevoelkerungsanteil, deutlich
    # kleiner als IT) wird nicht abgedeckt, weil Sammler-Notizen aus dem
    # Buendner Oberland fast durchgaengig DE-Sprachig gepflegt sind.
    "gennaio": 1, "gen": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5, "mag": 5,
    "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7,
    "agosto": 8, "ago": 8,
    "settembre": 9, "sett": 9,
    "ottobre": 10, "ott": 10,
    "novembre": 11,
    "dicembre": 12, "dic": 12,
    # Franzoesische Monatsnamen (Suisse romande - Wallis/Waadt/Genf/Neuenburg/
    # Freiburg, ~23% Bevoelkerungsanteil laut BFS und damit deutlich groesser
    # als die italienischsprachige Sparte) sowie geerbte Sammler-Notizen aus
    # franzoesisch-sprachigen Alpen-Fundorten (Wallis/Val d'Anniviers, Grimsel,
    # Binntal-Region, Mont-Blanc-Massiv/Chamonix-Argentiere, Aiguilles Rouges).
    # ASCII-Form eingetragen; :func:`_normalize_month_name` strippt FR-Diakritika
    # (é/è/ê/à/â/î/ô/û/ç) via NFKD-Dekomposition, sodass sowohl "13. fevrier 2024"
    # (ASCII-Sammler-Notation aus DBs mit nur-ASCII-Feldern) als auch "13. février
    # 2024" (Standard-FR-Schreibweise) auf denselben Dict-Key mappen. Kollisions-
    # frei zum DE/EN/IT-Bestand: identische Schreibweisen (mai/novembre) mappen
    # auf denselben Monat wie DE/IT; abweichende Formen sind FR-eigenstaendig
    # (janvier/fevrier/mars/avril/juin/juillet/aout/septembre/octobre/decembre).
    "janvier": 1, "janv": 1,
    "fevrier": 2, "fevr": 2, "fev": 2,
    "mars": 3,
    "avril": 4, "avr": 4,
    # "mai" bereits im DE-Block eingetragen (identische FR/DE-Schreibweise).
    "juin": 6,
    "juillet": 7, "juil": 7, "juill": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    # "novembre" bereits im IT-Block eingetragen (identische FR/IT-Schreibweise).
    "decembre": 12,
    # Spanische Monatsnamen (Sammler-Region Andalusien mit den historisch
    # bedeutenden Fundstellen Almeria/Sierra Almagrera/Rodalquilar, Riotinto-
    # Grube in Huelva, Panasqueira-Grenzgebiet zwischen Spanien und Portugal
    # sowie La Union in Cartagena; geerbte Sammler-Notizen aus spanisch-
    # sprachigen Katalogen von Museo Nacional de Ciencias Naturales in Madrid
    # und ES-Auktionsanbietern wie Fabre Minerals/Iberian Minerals). ES-Monatsnamen
    # sind alle ASCII (keine Diakritika), daher keine Regex-/Character-Class-
    # Aenderung noetig. Kollisionsfrei zum DE/EN/IT/FR-Bestand: marzo/agosto sind
    # bereits im IT-Block eingetragen (identische ES/IT-Schreibweise, identische
    # Monatswerte); mar/apr/may/jun/jul/sep/oct/nov/dic ueberschneiden sich mit
    # bestehenden DE/EN/IT-Kurzformen auf dieselben Monatswerte - semantisch
    # identisch, keine neuen Kollisionen. Die Latin-America-Variante ``setiembre``
    # (ohne p) ist in Kolumbien/Argentinien/Peru die gaengigere Schreibweise
    # (RAE-akzeptiert seit 1985) und tritt in geerbten Sammler-Notizen aus
    # suedamerikanischen Fundstellen (Cerro Rico Potosi Bolivien, Chuquicamata
    # Chile, La Rinconada Peru) verbreitet auf.
    "enero": 1, "ene": 1,
    "febrero": 2,
    # "marzo" bereits im IT-Block eingetragen (identische ES/IT-Schreibweise).
    "abril": 4, "abr": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    # "agosto"/"ago" bereits im IT-Block eingetragen (identische ES/IT-Schreibweise).
    "septiembre": 9, "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
    # Portugiesische Monatsnamen (Sammler-Region Portugal mit den historisch
    # bedeutenden Wolframit-/Quarz-Fundstellen Panasqueira und Beira Baixa sowie
    # aus geerbten Sammler-Notizen aus lusophonen Fundstellen: Brasilien mit
    # Ouro Preto/Minas Gerais fuer Turmalin/Topas/Aquamarin, Serra Pelada fuer
    # Gold, Mozambique fuer Rubin und Turmalin). Die Portugal-Sparte teilt sich
    # den Wolframit-Guertel mit der spanischen Panasqueira-Grenze (bereits im
    # ES-Block als "Panasqueira-Grenzgebiet zu Portugal" erwaehnt) und
    # brasilianische Pegmatite (Minas Gerais/Bahia) sind eine der weltweit
    # groessten Quellen fuer Turmalin-/Beryll-/Topas-Sammlungen; PT-BR-
    # Auktionsanbieter und Museu de Historia Natural de Lisboa pflegen ihre
    # Kataloge in PT-Sprache. PT-Monatsnamen enthalten Diakritika nur in
    # ``março`` (c-cedille), die :func:`_normalize_month_name` via NFKD-
    # Dekomposition und Combining-Mark-Filter auf ``marco`` strippt - identisch
    # zur Behandlung von FR ``février``/``août``/``décembre`` und ES ``otoño``.
    # Damit mappen sowohl ``março`` (Standard-PT-Schreibweise) als auch
    # ``marco`` (ASCII-Notation aus DBs mit nur-ASCII-Feldern) auf denselben
    # Dict-Key. Der ASCII-Key kollidiert NICHT mit IT/ES ``marzo`` (der
    # bereits eingetragen ist), weil PT ``marco`` mit ``c`` geschrieben wird,
    # nicht mit ``z`` - beide Formen koexistieren als separate Dict-Keys auf
    # denselben Monatswert 03. Kollisionsfrei zum DE/EN/IT/FR/ES-Bestand:
    # abril (bereits im ES-Block), agosto (bereits im IT-Block), novembre
    # (bereits im IT-/FR-Block), dezembro (bereits im DE-Block) sind
    # identische Schreibweisen auf denselben Monatswert; alle anderen PT-
    # Vollnamen (janeiro/fevereiro/marco/maio/junho/julho/setembro/outubro)
    # sind PT-spezifisch und schneidungsfrei. PT-Kurzformen ``set`` (September)
    # und ``out`` (Oktober) sind PT-spezifisch und ergaenzen die bereits vom
    # IT-Block bekannten ``sett``/``ott``-Kurzformen sowie EN ``sep``/``oct``.
    # Die uebrigen PT-Kurzformen (jan/fev/mar/abr/mai/jun/jul/ago/nov/dez)
    # ueberschneiden sich mit DE/EN/FR/IT/ES-Kurzformen auf dieselben Monats-
    # werte - semantisch identisch, keine neuen Kollisionen.
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    # "abril" bereits im ES-Block eingetragen (identische PT/ES-Schreibweise).
    "maio": 5,
    "junho": 6,
    "julho": 7,
    # "agosto" bereits im IT-Block eingetragen (identische PT/IT/ES-Schreibweise).
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    # "novembre" bereits im IT-Block eingetragen; PT schreibt "novembro"
    # (ohne trailing -e). Beide sind separate Dict-Keys auf denselben Monat.
    "novembro": 11,
    # DE ist "dezember" (mit -r), PT ist "dezembro" (mit -o) - separate
    # Dict-Keys auf denselben Monatswert 12.
    "dezembro": 12,
    # Roemische Monatsziffern (I..XII) - traditionelle Schreibweise auf aelteren
    # mineralogischen Etiketten, Museums-Eingangsbuechern und in osteuropaeischen
    # Sammlungs-Notizen ("13.VI.1985" = 13. Juni 1985). Wird durch
    # _normalize_month_name via lower() angesprochen; die Patterns
    # _DAY_MONTH_YEAR / _ENGLISH_MONTH_DAY_YEAR / _MONTH_YEAR akzeptieren
    # Buchstaben-Tokens beliebiger Laenge, daher kein separates Regex noetig.
    # Einbuchstabige Eintraege (i/v/x) sind formal mehrdeutig (Pronomen "I",
    # Tippfehler), greifen aber nur in Datum-Strukturen mit Tag + 4-Ziffer-Jahr
    # bzw. Monat + 4-Ziffer-Jahr - dort ist Datums-Semantik eindeutig.
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
    "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
}
# "13. Juni 2024" / "13 Juni 2024" / "13.Juni.2024" / "13/Jun/2024" / "13-Jun-2024"
# Separator zwischen den Teilen: Punkt, Slash, Bindestrich, Komma oder reines Whitespace.
# Bindestrich-Form "DD-MMM-YYYY" ist verbreitet in Oracle-/Log-/Datenbank-Exporten
# ("01-JAN-2024"). Optionales englisches Tag-Ordinal-Suffix ``st|nd|rd|th`` nach
# der Tagzahl ("1st June 2024", "31st May 2024") - in englischen Foto-Captions
# verbreitet.
# Nach dem Monatsnamen darf ein optionaler Punkt (DE-Kurzform "Jun.") direkt vor
# dem Separator stehen, und vor dem Jahr darf zusaetzlich ein Komma stehen
# ("13. März, 2024", "13/Jun./2024" aus Datenbank-Exporten/Foto-Bibliotheks-Exports).
_DAY_MONTH_YEAR = re.compile(
    r"^\s*(\d{1,2})(?:st|nd|rd|th)?\s*[./\-]?\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?"
    r"\s*[,./\-]?\s*(\d{4})\s*$",
    re.IGNORECASE,
)
# Englische Reihenfolge "Jun 13, 2024" / "June 13 2024" / "Jun. 13, 2024" / "Jun/13/2024"
# / "Jun-13-2024". Tag-Ordinal "March 1st, 2024" wird ebenfalls akzeptiert.
_ENGLISH_MONTH_DAY_YEAR = re.compile(
    r"^\s*([A-Za-z]+)\s*[./\-]?\s*(\d{1,2})(?:st|nd|rd|th)?\s*[,./\-]?\s*(\d{4})\s*$",
    re.IGNORECASE,
)
# Englische "day of month" Ordinal-Konstruktion mit "of"-Praeposition:
# "the 4th of July 2019", "15th of June 2020", "1st of January 2020",
# "22nd of December, 2020", "the 3rd of March 1985". In englischen Sammler-
# Notizen, Foto-Captions und Auktions-Beschreibungen die idiomatische Form
# der Tages-vor-Monat-Reihenfolge ("the 4th of July" ist die Standard-
# Feiertag-Notation, "the 15th of June" die typische Prosa-Datums-Angabe in
# englischer Sprache aus geerbten Sammlungen mit US-/UK-Vorbesitzer,
# Auktions-Katalog-Eintragen "Purchased on the 15th of June 2019" und aus
# englisch verfassten Fund-Berichten). Bisher fielen alle "of"-Konstruktionen
# stille auf None, weil :data:`_DAY_MONTH_YEAR` nur den direkten Whitespace-
# oder Punkt-/Slash-/Bindestrich-Separator zwischen Tag und Monatsname
# akzeptierte und das Wort "of" den strukturellen ``$``-Anker-Match blockte -
# aus einem typischen Auktions-Eintrag "Acquired the 4th of July 1985 in
# Tucson" wurde silenter Funddatum-Datenverlust bei der Migration.
#
# Optionaler ``the``-Artikel-Praefix ("the 4th of July" / "4th of July" sind
# beide idiomatisch, "the" wird oft in Prosa gesetzt und in Kompakt-Notizen
# weggelassen). Optionales Tag-Ordinal-Suffix ``st|nd|rd|th`` spiegelt
# :data:`_DAY_MONTH_YEAR` - grammatisch korrekt ist die Ordinal-Form
# ("the 15th of June"), aber Sammler-Kompakt-Notizen lassen den Ordinal-
# Suffix manchmal weg ("15 of June 2020"). Monatsname muss valide sein
# (via :func:`_normalize_month_name`), sonst faellt der Match durch.
# Vor dem Jahr optionales Komma ("the 15th of June, 2020" - EN-Print-
# Konvention aus Zeitungs-/Journal-Stil).
#
# Disjunktheit zu :data:`_DAY_MONTH_YEAR` (verlangt Whitespace/Punkt/Slash/
# Bindestrich zwischen Tag und Monatsname, kein Wort dazwischen) und zu
# :data:`_ENGLISH_MONTH_DAY_YEAR` (verlangt Monatsname als erstes Feld). Die
# "of"-Praeposition als Pflicht-Trenner macht die Struktur eindeutig
# (kein anderes Datums-Pattern kennt "of" als semantisches Zeichen).
_DAY_OF_MONTH_YEAR = re.compile(
    r"^\s*(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+of\s+"
    r"([A-Za-z]+)\.?\s*,?\s*(\d{4})\s*$",
    re.IGNORECASE,
)
# "Juni 2024" / "Juni, 2024" / "Juni/2024" / "Juni-2024" / "Jun-2024" / "Juni.2024".
# Bindestrich-Form ist symmetrisch zur DD-Mon-YYYY-Notation (Oracle/Log-Exporte):
# Reports lassen den Tag oft weg, wenn nur eine Monatsangabe vorliegt
# ("Jun-2024" = ganzer Juni). Die voll qualifizierte DD-Mon-YYYY-Form bleibt
# weiterhin von _DAY_MONTH_YEAR erfasst (die Pattern kollidieren nicht, weil
# diese hier nur exakt zwei Teile zulaesst).
# Punkt als Separator ("Juni.2024", "Dec.2024") symmetrisch zur DD.Mon.YYYY-Form
# ("13.Juni.2024" / "13.Jun.2024"); kommt in deutschen Excel-CSV-Exporten und
# Tabellenkalkulations-Auto-Formatierung vor, wenn der Tag-Anteil weggelassen
# wird. Das optionale ``\.?`` vor dem Separator deckt zusaetzlich ``Jun..2024``
# / ``Jun. 2024``-Mischformen ab, ohne die bestehenden Whitespace-/Komma-/
# Slash-/Bindestrich-Varianten zu beeintraechtigen.
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Monatsname und Jahr
# deckt die natuerlichsprachige DE-/EN-Prosa-Form ab: ``Juli von 2024`` /
# ``Januar von 2024`` (DE), ``July of 2024`` / ``January of 2024`` (EN).
# In geerbten Sammlungs-Etiketten und Fund-Tagebuechern mit Fliesstext-
# Notation ("Fund Juli von 2024 im Aaregebiet", "Bergtour January of 2020
# Zermatt") ist die Praeposition die natuerlichsprachige Verbindung
# zwischen Monat und Jahr - viel natuerlicher als die knappe ``Juli 2024``-
# Form, aber genauso semantisch eindeutig. Bisher fielen alle
# Praepositions-Formen still auf None, weil die Separator-Klasse
# ``[,./ \-]`` nur Ein-Zeichen-Trenner (Komma, Punkt, Slash, Leerzeichen,
# Bindestrich) kennt und keinen Wort-Trenner - typische DE-/EN-Prosa-
# Notizen aus Fund-Tagebuechern gingen als silenter Funddatum-Datenverlust
# in die Migration, obwohl Monat und Jahr eindeutig lesbar sind.
#
# Spiegelt die "of"/"von"-Praepositions-Erweiterung aus
# :data:`_KW_YEAR` (Wochen-Achse) und :data:`_DAY_OF_MONTH_YEAR`
# (englische Ordinal-Konstruktion "4th of July 2019") auf die
# Monatsname-Achse. Beide Praepositionen verlangen Whitespace auf beiden
# Seiten (``\s+...\s+``), sodass Kompositum-Formen (``Julivon``,
# ``Juli-von``) und angehaengte Formen (``Juli von2024``) still fehl-
# matchen. Case-Insensitivitaet ist nicht noetig (die Regex ist ohne
# ``re.IGNORECASE``); der :func:`_normalize_month_name`-Handler behandelt
# Case-Insensitivitaet der Monats-Alternativen und die Praeposition
# ``von``/``of`` ist bereits in ihrer natuerlichen Kleinbuchstaben-Form
# (Grossbuchstaben-Varianten aus Uppercase-Titeln sind semantisch
# identisch, aber praktisch selten im Prosa-Kontext).
#
# Underscore ``_`` als Separator zwischen Monatsname und Jahr - der de-facto
# Filename-sichere Trenner in Foto-/Sammlungs-Archiven und Ordner-Struktur-
# Namen ("Fund_Juni_2024.jpg", "Ausflug_July_2020.pdf", "Sammlung_Sep_1985/",
# "Aare_Mai_2024_UV.png"). In der Praxis das zentrale Muster, wenn ein
# Sammler den Fund/Auftritt/Foto-Ordner nach Monat und Jahr benennt und den
# Ordner-/Datei-Namen dann als Datums-Feld in die App uebernimmt (Copy-paste
# aus Datei-Explorer, Massen-Umbenennen mit Sammlungs-Tag). Auf Datei-Achse
# stehen ``[space]``, ``[.]``, ``[-]``, ``[/]`` haeufig unter Ausschluss der
# Windows-/POSIX-Reserved-Char-Konvention (Slash) oder sind in Foto-Software
# durch Auto-Rename-Regeln zu ``_`` normalisiert - der Underscore ist damit
# der zuverlaessigste Cross-Plattform-Filename-Trenner. Bisher fielen alle
# Filename-abgeleiteten Monatsname-Jahr-Formen mit Underscore-Separator
# ("Juni_2024" -> None, "Sep_1985" -> None, "August_2020" -> None) still auf
# None, weil die Separator-Klasse ``[,./ \-]`` den Filename-Trenner nicht
# kannte - typische Foto-Ordner-Namen und massenkonvertierte Datei-Batches
# gingen als silenter Funddatum-Datenverlust in die Migration. Der Unicode-
# Underscore hat im Datums-Kontext keine andere Bedeutung (kein Trenner in
# einer publizierten Datums-Notation), damit ist die Erweiterung verlustfrei
# und kollisionsfrei zu allen bestehenden Datums-Notationen. Symmetrisch zur
# etablierten Underscore-Behandlung in :func:`_strip_locale_thousands`
# (Zahl-Achse, Python/Java/JS-Digit-Grouping), die den Underscore als
# domaenen-neutralen Sekundaer-Separator behandelt.
_MONTH_YEAR = re.compile(
    r"^\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?(?:\s*[,./ _\-]\s*|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)

# Month-Range innerhalb eines Jahres ("Juni/Juli 2024", "Mai-Juni 1985",
# "August/September 2000", "Juni bis Juli 2024", "June to July 2024"). Sehr
# verbreitet in geerbten Sammlungs-Notizen und Foto-Captions, wenn der Sammler
# den Fund/das Foto nicht auf einen einzigen Monat, aber auf einen zusammen-
# haengenden Monatsbereich innerhalb desselben Jahres eingrenzen kann ("Aare-
# gebiet, Juni/Juli 2024" = "im Juni oder Juli 2024 gefunden", "Fund Mai-Juni
# 1985" = "irgendwann im Mai oder Juni 1985"). Bisher fielen alle Formen still
# auf None, weil _MONTH_YEAR nur einen Monat + Jahr akzeptiert und der Range-
# Trenner (Slash/Bindestrich/"bis"/"to") den strukturellen ``$``-Anker-Match
# blockte - aus einem typischen Etikett wie "Juni/Juli 2024" wurde silenter
# Funddatum-Datenverlust bei der Migration.
#
# Konvention identisch zu :data:`_YEAR_RANGE` / :data:`_YEAR_RANGE_WORD`: der
# Start-Monat als ISO-Datum (Range-Start-Anker, "Juni/Juli 2024" -> "2024-06-01"
# analog "1985-1990" -> "1985-01-01"), der End-Monat bleibt semantische Wert-
# Anmerkung im Freitext (notizen). Inverted Range (Tippfehler oder Cross-Year-
# Semantik wie "November-Februar 2024") liefert weiterhin den Start-Monat -
# konsistent mit _YEAR_RANGE ("1985-1980" -> "1985-01-01").
#
# Trenner-Alternativen spiegeln die _YEAR_RANGE-/_YEAR_RANGE_WORD-Konvention:
# - Symbol-Trenner ``[-–—/]``: "Juni/Juli 2024", "Mai-Juni 1985",
#   "Juni–Juli 2024" (en dash typografisch), "Juni—Juli 2024" (em dash).
# - Wort-Trenner (bis/to/till/until): "Juni bis Juli 2024",
#   "June to July 2024" - spiegelt :data:`_YEAR_RANGE_WORD` auf die Monats-Achse.
#
# Beide Monats-Tokens muessen valide Monatsnamen sein (Pruefung im Handler via
# :func:`_normalize_month_name`), sonst waere die Struktur mehrdeutig
# ("Juni/xxx 2024" darf nicht als "Juni 2024" gelesen werden).
#
# Disjunktheit zu _MONTH_YEAR: die 2-Teil-Form ("Juni 2024") verlangt einen
# einzelnen Separator ``[,./ \-]`` gefolgt von 4 Ziffern; die 3-Teil-Form hier
# verlangt vor dem Jahr einen zweiten Monatsnamen. "Juni/Juli 2024" faellt bei
# _MONTH_YEAR (nach dem "/"-Separator kommt "Juli", keine 4 Ziffern) und wird
# hier korrekt aufgeloest. "Juni/2024" faellt hier (nach dem "/" kommt eine
# Zahl, kein Monatsname) und wird von _MONTH_YEAR aufgeloest.
_MONTH_RANGE_YEAR = re.compile(
    r"^\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?"
    r"\s*(?:[-–—/]\s*|\s+(?:bis|to|till|until|through|thru)\s+)"
    r"([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?"
    r"\s+(\d{4})\s*$",
    re.IGNORECASE,
)

# Tages-Range innerhalb eines Monats mit Monatsname ("5.-7. Juni 2024",
# "5-7 June 2024", "5. bis 7. Juni 2024", "5 to 7 June 2024"). Sehr verbreitet in
# Sammlungs-Notizen, Foto-Captions und Fund-Etiketten, wenn der Sammler den Fund
# oder die Exkursion auf einen zusammenhaengenden Tages-Bereich innerhalb eines
# einzelnen Monats eingrenzt ("Fund vom 5.-7. Juni 2024 am Aaregebiet", "Tucson
# Boerse 5-7 February 2024", "Alpen-Tour 12.-14. August 2020"). Bisher fielen
# alle Formen still auf None, weil :data:`_DAY_MONTH_YEAR` nur einen Einzel-Tag
# akzeptiert und der Range-Trenner (Bindestrich/en-dash/em-dash/"bis"/"to"/
# "till"/"until") den strukturellen ``$``-Anker-Match blockte - aus einem
# typischen Etikett wie "5.-7. Juni 2024" (= vom 5. bis 7. Juni 2024) oder
# einem Boersen-Zitat "Tucson Boerse 5-7 February 2024" wurde silenter
# Funddatum-Datenverlust bei der Migration.
#
# Konvention identisch zu :data:`_YEAR_RANGE` / :data:`_YEAR_RANGE_WORD` /
# :data:`_MONTH_RANGE_YEAR`: der Start-Tag als ISO-Datum (Range-Start-Anker,
# "5.-7. Juni 2024" -> "2024-06-05" analog "Mai-Juni 1985" -> "1985-05-01"),
# der End-Tag bleibt semantische Wert-Anmerkung im Freitext (notizen). Inverted
# Range (Tippfehler wie "7.-5. Juni 2024") liefert weiterhin den Start-Tag -
# konsistent mit _MONTH_RANGE_YEAR ("November-Februar 2024" -> "2024-11-01").
#
# Trenner-Alternativen spiegeln die _MONTH_RANGE_YEAR-Konvention:
# - Symbol-Trenner ``[-–—]``: "5-7 Juni 2024", "5–7 Juni 2024" (en dash),
#   "5—7 Juni 2024" (em dash). Slash ``/`` bewusst NICHT als Trenner erlaubt,
#   weil "5/7 Juni 2024" in EN/US-Kontexten als "May 7" (M/D) oder "July 5"
#   (D/M) mehrdeutig gelesen werden koennte - Tages-Ranges verwenden idiomatisch
#   Bindestrich, nicht Slash.
# - Wort-Trenner (bis/to/till/until): "5 bis 7 Juni 2024", "5 to 7 June 2024"
#   - spiegelt :data:`_YEAR_RANGE_WORD` / :data:`_MONTH_RANGE_YEAR` auf die
#   Tages-Achse.
#
# Optionaler Punkt nach jedem Tag (``\.?``) deckt die DE-Ordinal-Notation ab
# ("5. Juni" statt "5 Juni"); optionales EN-Ordinal-Suffix ``(?:st|nd|rd|th)?``
# spiegelt :data:`_DAY_MONTH_YEAR` fuer EN-Formen ("5th-7th June 2024", "1st
# to 3rd March 2024"). Beide Tages-Tokens werden im Handler auf 1..31 geprueft,
# der Monatsname via :func:`_normalize_month_name` auf einen gueltigen Monat.
#
# Disjunktheit zu :data:`_DAY_MONTH_YEAR`: die Einzel-Tag-Form verlangt genau
# einen Tag + Monatsname + Jahr; die Tages-Range-Form hier verlangt zwei Tage
# + Range-Trenner + Monatsname + Jahr. "5.-7. Juni 2024" faellt bei
# _DAY_MONTH_YEAR (nach "5" + optionalem "."-Trenner folgt "-7." statt Monats-
# name) und wird hier korrekt aufgeloest. "5 Juni 2024" faellt hier (kein
# Range-Trenner) und wird von _DAY_MONTH_YEAR aufgeloest.
_DAY_RANGE_MONTH_YEAR = re.compile(
    r"""^\s*
        (\d{1,2})(?:st|nd|rd|th)?\.?
        (?:\s*[-–—]\s*|\s+(?:bis|to|till|until|through|thru)\s+)
        (\d{1,2})(?:st|nd|rd|th)?\.?
        \s+
        ([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?
        \s+
        (\d{4})
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Englische Month-First-Tages-Range: "Feb 3 - Feb 8, 2024" (Monat auf beiden
# Seiten wiederholt, gleicher Monat), "Feb 3-8, 2024" (Monat nur einmal, Tages-
# Range im selben Monat), "March 3 - April 5, 2024" (Monat auf beiden Seiten,
# Cross-Month-Range), "Feb 3 to Feb 8, 2024" (Wort-Trenner), "February 3rd -
# March 5th, 2024" (Ordinal-Suffixe), "Feb. 3 - Feb. 8, 2024" (Abbrev.-Punkt).
# Sehr verbreitet in EN-Sammlungs-Notizen, Auktions-Katalog-Beschreibungen,
# Museums-Etiketten und Boersen-Zitaten, wenn der Sammler den Fund-Zeitraum,
# die Exkursion oder die Boersen-Periode auf einen Tages-Bereich innerhalb
# desselben oder ueber zwei aufeinanderfolgende Monate eingrenzt ("collected
# March 3 - April 5, 2024 at Val Bedretto", "Tucson Show Feb 3-8, 2024",
# "field season June 15 - July 20, 2023 in the Alps"). Bisher fielen alle
# Formen still auf None, weil :data:`_ENGLISH_MONTH_DAY_YEAR` nur einen
# Einzel-Tag akzeptiert und der Range-Trenner den strukturellen ``$``-Anker-
# Match blockte, und :data:`_DAY_RANGE_MONTH_YEAR` mit einer Zahl beginnt
# (Tag-First-Konvention) statt mit einem Monatsnamen - EN-Foto-Captions und
# EN-Katalog-Zeilen fielen auf den silenten Funddatum-Datenverlust der zwei
# Ausdehnungs-Tage bei der Migration.
#
# Konvention identisch zu :data:`_DAY_RANGE_MONTH_YEAR`: der Start-Tag im
# ersten (oder einzigen) Monat als ISO-Datum (Range-Start-Anker), End-Tag
# und End-Monat bleiben semantische Wert-Anmerkung im Freitext (notizen).
# Inverted Range (Tippfehler "Feb 8-3, 2024") liefert den ersten Tag wie
# _DAY_RANGE_MONTH_YEAR / _MONTH_RANGE_YEAR. Cross-Month-Range "March 3 -
# April 5, 2024" liefert "2024-03-03" (Start-Monat, Start-Tag). Trenner-
# Alternativen identisch zu :data:`_DAY_RANGE_MONTH_YEAR` (ASCII-Hyphen,
# En-/Em-Dash, DE-Wort "bis", EN-Woerter "to"/"till"/"until"/"through"/
# "thru").
#
# Zweiter Monatsname optional via ``(?:([A-Za-z]+)\.?\s+)?``: fehlt er
# ("Feb 3-8, 2024"), wird der erste Monat semantisch fuer beide Tage
# uebernommen. Ist er vorhanden ("Feb 3 - Feb 8, 2024" oder "March 3 -
# April 5, 2024"), muss er via :func:`_normalize_month_name` valide sein -
# sonst fall-through (kein Return) analog :data:`_MONTH_RANGE_YEAR`.
# Optionales Komma vor dem Jahr symmetrisch zu :data:`_ENGLISH_MONTH_DAY_YEAR`
# ("June 13, 2024"), optionales Ordinal-Suffix ``st|nd|rd|th`` symmetrisch
# zu :data:`_DAY_RANGE_MONTH_YEAR` ("5th-7th June 2024").
#
# Disjunktheit zu :data:`_ENGLISH_MONTH_DAY_YEAR` (Einzel-Tag ohne Range-
# Trenner): "Jun 13, 2024" faellt hier, weil zwischen "13" und "2024" nur
# Komma+Whitespace stehen, kein Dash und kein Range-Wort - matcht die
# Range-Trenner-Alternante nicht. Disjunktheit zu :data:`_DAY_RANGE_MONTH_YEAR`
# (Day-First-Konvention): "5-7 June 2024" beginnt mit einer Zahl, unser
# Pattern verlangt einen Monatsnamen als erstes Token.
_ENGLISH_MONTH_DAY_RANGE = re.compile(
    r"""^\s*
        ([A-Za-z]+)\.?
        \s+
        (\d{1,2})(?:st|nd|rd|th)?
        (?:\s*[-–—]\s*|\s+(?:bis|to|till|until|through|thru)\s+)
        (?:([A-Za-z]+)\.?\s+)?
        (\d{1,2})(?:st|nd|rd|th)?
        \s*,?\s*
        (\d{4})
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Tages-Range mit numerischem Monat: "13.-15.06.2024", "13. - 15.06.2024",
# "13. bis 15.06.2024", "13-15.06.2024". Spiegelt :data:`_DAY_RANGE_MONTH_YEAR`
# auf die numerische Monat-Achse - der Sammler notiert einen Fund-Zeitraum
# innerhalb eines Kalendermonats haeufig in dieser Kompakt-Form ("Fund
# 13.-15.06.2024 am Gotthard", "Sammlungs-Excursion 3.-5.10.2023 Val Bedretto"),
# weil sie kuerzer als "13. bis 15. Juni 2024" ist und in Excel-Zellen /
# Foto-Captions / Etiketten besser passt. Bisher fielen alle Formen still auf
# None, weil :data:`_DAY_MONTH_YEAR` nur einen Einzel-Tag akzeptiert und der
# Range-Bindestrich zwischen den Tagen den strukturellen ``$``-Anker-Match
# blockte - silenter Funddatum-Datenverlust bei der Migration aus Sammlungs-
# Tagebuechern und Fund-Etiketten mit numerischem Monat.
#
# Konvention identisch zu :data:`_DAY_RANGE_MONTH_YEAR`: der erste Tag zaehlt
# als Range-Start und liefert ``YYYY-MM-DD1`` (Fund-Zeitraum-Start ist der
# semantisch relevante Anker, weil das Fund-Datum in der Sammlungs-DB als
# Einzel-Punkt gespeichert wird, nicht als Range). Range-Trenner-Menge
# identisch zu :data:`_DAY_RANGE_MONTH_YEAR` (ASCII-Hyphen, En-/Em-Dash,
# DE-Wort "bis", EN-Woerter "to"/"till"/"until"/"through"/"thru") -
# konsistent zur Range-Trenner-Konvention der uebrigen Range-Patterns.
#
# Disjunktheit zu :data:`_DAY_MONTH_YEAR` (Einzel-Tag ohne Range-Trenner)
# und zu :data:`_ISO_YEAR_MONTH_DAY` (YYYY zuerst statt DD zuerst). Full-
# Date-Range-Formen (``13.06.-15.06.2024``, ``13.06.2024-15.06.2024``)
# bleiben bewusst ausserhalb dieses Patterns - die Semantik ist dort
# nicht "gleicher Monat" sondern "beliebiger Range" und braucht separate
# Behandlung; hier nur die Ein-Monat-Kompaktform, in der beide Tage
# strukturell vor der gemeinsamen Monat.Jahr-Angabe stehen.
_DAY_RANGE_NUMERIC_MONTH_YEAR = re.compile(
    r"""^\s*
        (\d{1,2})\.?
        (?:\s*[-–—]\s*|\s+(?:bis|to|till|until|through|thru)\s+)
        (\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Voll-Datum-Range im DE-Format: "13.06.-15.06.2024" (Kurzform mit fehlendem
# ersten Jahr, semantisch beide Daten im selben Jahr), "13.06.2024-15.07.2024"
# (Voll-Form, beliebige Monate/Jahre), "13.06.2024 bis 15.07.2024",
# "13.06.2024 / 15.07.2024". Sehr verbreitet in Sammlungs-Tagebuechern und
# Fund-Etiketten, wenn der Sammler einen Fund-Zeitraum ueber mehrere Tage /
# einen Monatswechsel dokumentiert ("Herbst-Excursion Gotthard 28.09.-05.10.2024",
# "Tucson-Boerse 30.01.2024 bis 04.02.2024", "Sommer-Sammelphase
# 15.06.2024-31.08.2024"). Bisher fielen alle Formen still auf None, weil
# :data:`_DATE_FORMATS` strptime-anchored ist und der Range-Separator zwischen
# den beiden Datums-Feldern keinen Match zulaesst - silenter Funddatum-
# Datenverlust bei der Migration aus Zeitraum-Notationen.
#
# Konvention identisch zu :data:`_DAY_RANGE_MONTH_YEAR` / :data:`_DAY_RANGE_
# NUMERIC_MONTH_YEAR`: der Range-Start liefert das ISO-Datum, das End-Datum
# wird nicht in die Datums-Rueckgabe eingerechnet, weil das Fund-Datum in
# der Sammlungs-DB als Einzel-Punkt gespeichert wird. Wenn das erste Datum
# kein Jahr traegt (Kurzform ``13.06.-15.06.2024``), wird das Jahr aus dem
# zweiten Datum uebernommen - das entspricht der Sammler-Konvention "gleiches
# Jahr, End-Datum vollstaendig".
#
# Range-Trenner-Menge (ASCII-Hyphen, En-/Em-Dash, Slash, DE-Wort ``bis``,
# EN-Woerter ``to``/``till``/``until``/``through``/``thru``) spiegelt die
# uebrigen Range-Patterns. Der Slash ist hier bewusst inkludiert, weil er
# in Voll-Datum-Range-Notation zwar seltener aber verbreitet ist
# ("13.06.2024/15.07.2024" aus Datenbank-Exporten mit Datei-Namen-Konvention).
_FULL_DATE_RANGE_DE = re.compile(
    r"""^\s*
        (\d{1,2})\.(\d{1,2})\.(?:(\d{4}))?\s*
        (?:\s*[-–—/]\s*|\s+(?:bis|to|till|until|through|thru)\s+)
        (\d{1,2})\.(\d{1,2})\.(\d{4})
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ISO-Datum-Range: "2024-06-13/2024-06-15" (Slash-Trenner, ISO-8601-konform),
# "2024-06-13 - 2024-06-15" (Bindestrich-Trenner mit Whitespace), "2024-06-13
# bis 2024-06-15", "2024-06-13–2024-06-15" (En-/Em-Dash). Verbreitet in
# Datenbank-Exporten, wissenschaftlichen Publikationen, GIS-/CSV-Interchange-
# Formaten und modernen Sammler-Notizen, die ISO-Datum als Standard-Form
# verwenden. Bisher fielen alle Formen still auf None, weil :data:`_DATE_
# FORMATS` strptime-anchored ist und den Range-Separator nicht toleriert.
#
# Konvention identisch zu den uebrigen Range-Patterns: der Range-Start
# liefert das ISO-Datum, das End-Datum wird nicht in die Rueckgabe
# eingerechnet. Trenner-Klasse akzeptiert ASCII-Hyphen ohne obligatorisches
# Whitespace: die Voll-ISO-Struktur ``\d{4}-\d{1,2}-\d{1,2}`` auf beiden
# Seiten schuetzt vor Ambiguitaet mit der internen Hyphen-Struktur des
# ISO-Datums (kein False-Positive auf einzelne ISO-Daten wie ``2024-06-13``
# oder Range-Fragmente wie ``2024-06-13-14``, weil die Zweit-Seite nicht
# nur eine Tag-Zahl sondern ein volles YYYY-MM-DD-Tripel matchen muss).
# Die Toleranz auf bare-Bindestrich ist wichtig, weil
# :data:`_TYPOGRAPHIC_DASH_BETWEEN_DIGITS` vor diesem Match Unicode-Dashes
# zwischen Ziffern auf ASCII-Hyphens normalisiert und die whitespace-lose
# En-Dash-Range ``2024-06-13–2024-06-15`` bei diesem Handler bereits als
# ``2024-06-13-2024-06-15`` ankommt.
_ISO_DATE_RANGE = re.compile(
    r"""^\s*
        (\d{4})-(\d{1,2})-(\d{1,2})
        (?:\s*/\s*|\s*[–—]\s*|\s*-\s*|\s+(?:bis|to|till|until|through|thru)\s+)
        (\d{4})-(\d{1,2})-(\d{1,2})
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Year-first Notation mit Monatsnamen: "2024-Juni" / "2024 June" / "2024-Jun" /
# "2024.Juni" / "2024/Juni" / "2024, June". Spiegelt _MONTH_YEAR ("Juni 2024")
# auf die Year-First-Reihenfolge - die ISO-/sortierbare Form mit ausgeschriebenem
# Monatsnamen kommt in Excel-Auto-Fill-Spalten ("2024-Jan", "2024-Feb"
# als sortierbare Monatsgruppen), Listen-Headern in Sammlungs-Tagebuechern
# ("2024 Juni: 5 neue Stuecke vom Aaregebiet"), LaTeX-/Markdown-Dokumenten
# mit chronologisch gruppierten Eintraegen und in Excel-Pivot-Auto-Format
# vor, wenn der Sammler die Jahre als ordnenden Schluessel vor dem Monatsnamen
# stellt. Bisher fielen alle Formen stille auf None, obwohl semantisch
# identisch zur Month-First-Variante. Konvention: Tag wird auf den 1. gesetzt
# (Monatsstart), spiegelt _MONTH_YEAR. Wird nach _MONTH_YEAR geprueft, weil
# beide disjunkt sind (Month-First beginnt mit Buchstaben, Year-First mit
# 4 Ziffern - kollisionsfrei) und die Reihenfolge die ueblichere Month-First-
# Variante zuerst behandelt.
_YEAR_MONTH_NAME = re.compile(
    r"^\s*(\d{4})\s*[,./ _\-]\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?\s*$",
)
# Year-first DD-Monatsname-YYYY-Notation: "2024-Juni-13" / "2024 June 13" /
# "2024.Juni.13" / "2024-Jun-13" / "2024/Juni/13". Spiegelt _DAY_MONTH_YEAR
# ("13. Juni 2024") und _ENGLISH_MONTH_DAY_YEAR ("Juni 13, 2024") auf die
# Year-First-Reihenfolge - die voll qualifizierte sortierbare ISO-aehnliche
# Form mit ausgeschriebenem Monatsnamen kommt in den gleichen Quellen wie
# _YEAR_MONTH_NAME vor (Excel-Auto-Fill, Listen-Header, LaTeX). Optionales
# englisches Tag-Ordinal-Suffix ``st|nd|rd|th`` symmetrisch zu den anderen
# named-month Patterns. Konvention identisch zu _DAY_MONTH_YEAR/
# _ENGLISH_MONTH_DAY_YEAR: voll qualifiziertes Datum (Y/M/D). Wird vor
# _YEAR_MONTH_NAME geprueft, weil die 3-Teil-Form spezifischer ist; beide
# Patterns sind durch das ``$``-Anker disjunkt (3 Teile vs. 2 Teile).
_YEAR_MONTH_NAME_DAY = re.compile(
    r"^\s*(\d{4})\s*[,./ _\-]\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?\s*"
    r"[,./ _\-]\s*(\d{1,2})(?:st|nd|rd|th)?\s*$",
)

# Jahreszeit + Jahr ("Sommer 1985", "Spring 2024", "Frühjahr 2020").
# Konvention: meteorologischer Saison-Start im genannten Jahr (Maerz/Juni/Sep/Dez).
# Winter wird auf Dezember desselben Jahres gelegt.
_SEASON_MONTHS: dict[str, int] = {
    "fruehling": 3, "fruehjahr": 3, "spring": 3,
    "sommer": 6, "summer": 6,
    "herbst": 9, "autumn": 9, "fall": 9,
    "winter": 12,
    # DE-Kompositum-Formen "Frueh<Saison>"/"Spaet<Saison>" der drei innerhalb
    # eines Kalenderjahres liegenden Saisons (Fruehling/Fruehjahr, Sommer,
    # Herbst) mappen auf die Saison-Startmonat +/- Randabstand: "Frueh<X>"
    # zeigt auf den ersten Monat der Saison (identisch zur nackten Saison,
    # weil die Saison drei Monate abdeckt und "Frueh<X>" ihren Anfang meint),
    # "Spaet<X>" auf den dritten Monat der Saison. Sehr verbreitet in DE-
    # Sammlungs-Notizen, Foto-Captions und Fundort-Etiketten ("Fund
    # Spaetsommer 2024", "Spaetherbst-Exkursion 2023 Aare", "Fruehsommer-
    # Bergtour 1985"), weil Sammler die Fund-/Foto-Zeit oft innerhalb der
    # Saison eingrenzen koennen, aber nicht auf den exakten Monat. Bisher
    # fielen alle Kompositum-Formen still auf None, obwohl semantisch klar
    # in einen Kalendermonat abbildbar - der reine Saison-Wortstamm ist im
    # Kompositum durch das Modifikator-Praefix "Frueh"/"Spaet" ergaenzt und
    # damit fuer _normalize_season_name unbekannt. Konvention: Fruehjahr
    # (Maerz-Mai) -> Fruehfruehjahr=3, Spaetfruehjahr=5; Sommer (Juni-Aug)
    # -> Fruehsommer=6, Spaetsommer=8; Herbst (Sep-Nov) -> Fruehherbst=9,
    # Spaetherbst=11. ASCII-transliterierte Formen (frueh statt frueh) und
    # Umlaut-Formen (frueh/spaet) werden durch _normalize_season_name via
    # ae/oe/ue-Ersatz auf denselben Key normalisiert. Winter-Kompositum-
    # Formen (Fruehwinter/Spaetwinter) bewusst NICHT enthalten, weil der
    # meteorologische Winter Dezember-Februar zwei Kalenderjahre umschliesst
    # und die Modifikator-Semantik dort mehrdeutig zwischen dem Jahr des
    # Winter-Anfangs und dem Jahr des Winter-Endes waere - "Spaetwinter
    # 2024" koennte Februar 2024 (Ende Winter 2023/24) oder Februar 2025
    # (Ende Winter 2024/25) meinen. Fuer die drei Ganzjahres-internen
    # Saisons ist die Zuordnung eindeutig.
    "fruehfruehling": 3, "fruehfruehjahr": 3, "earlyspring": 3,
    "spaetfruehling": 5, "spaetfruehjahr": 5, "latespring": 5,
    "fruehsommer": 6, "earlysummer": 6,
    "spaetsommer": 8, "latesummer": 8,
    "fruehherbst": 9, "earlyautumn": 9, "earlyfall": 9,
    "spaetherbst": 11, "lateautumn": 11, "latefall": 11,
    # Franzoesische Saison-Namen (Suisse romande, Chamonix/Wallis/Val
    # d'Anniviers-Sammlungen) - printemps=Fruehling, ete=Sommer (mit e-acute
    # in Standard-FR-Schreibweise "été"), automne=Herbst, hiver=Winter. Die
    # ASCII-Form "ete" ist der Post-NFKD-Strip-Key von "été" (via
    # :func:`_normalize_season_name`), der die e-acute-Diakritika strippt und
    # damit sowohl "été 2024" als auch "ete 2024" auf denselben Key mappt.
    # Konvention identisch zu DE/EN: meteorologischer Saison-Startmonat des
    # genannten Jahres (Maerz/Juni/Sep/Dez). Kompositum-Formen "debut<X>"/
    # "fin<X>" (FR-Aequivalent zu Frueh/Spaet) sind seltener und werden nicht
    # separat gefuehrt - Sammler-Notizen aus der Romandie verwenden ueberwiegend
    # die nackte Saison-Notation.
    "printemps": 3, "ete": 6, "automne": 9, "hiver": 12,
    # Italienische Saison-Namen (Ticino / italienische Schweiz sowie geerbte
    # Sammler-Notizen aus italienischen Alpen-/Dolomiten-Fundorten) -
    # primavera=Fruehling, estate=Sommer, autunno=Herbst, inverno=Winter.
    # Alle ASCII, keine Akzente auf den italienischen Saison-Namen (im
    # Gegensatz zu franzoesisch ete/été), daher keine Regex-/Character-
    # Class-Aenderung noetig; die identische NFKD-Diakritika-Behandlung
    # in :func:`_normalize_season_name` bleibt Ruhe-Semantik. Konvention
    # identisch zu DE/EN/FR: meteorologischer Saison-Startmonat des
    # genannten Jahres (Maerz/Juni/September/Dezember). Symmetrie-
    # Vervollstaendigung zum bereits gepflegten IT-Monat-Block in
    # :data:`_MONTH_NAMES` (gennaio..dicembre): dort ist Ticino als IT-
    # Sprachraum begruendet, hier fehlten die passenden Saison-Namen -
    # Sammler-Notizen aus Val Bavona/Val Verzasca/Val Malvaglia oder
    # Dolomiten-Fund-Etiketten der Bergamasker Alpen konnten "estate
    # 1985" bisher nicht als "1985-06-01" auflosen, obwohl der IT-
    # Wortstamm im Sammlungs-Feld eindeutig als Saison-Angabe lesbar
    # ist. Kollisions-Schutz: keiner der vier Namen kollidiert mit dem
    # bestehenden IT-Monat-Bestand (gennaio/febbraio/marzo/aprile/maggio/
    # giugno/luglio/agosto/settembre/ottobre/novembre/dicembre) oder mit
    # DE/EN/FR-Season-/Monat-Namen; "estate" ist zwar auch ein englischer
    # Substantiv (Nachlass), spiegelt aber die identische Kontext-
    # Ambiguitaet der bereits akzeptierten "spring"/"fall"-Notationen (die
    # ebenfalls Nicht-Season-Bedeutungen tragen koennen) und wird in
    # Sammler-Notizen fast durchgaengig als Saison verstanden.
    "primavera": 3, "estate": 6, "autunno": 9, "inverno": 12,
    # Spanische Saison-Namen (Sammler-Region Andalusien/Almeria/La Union sowie
    # geerbte Sammler-Notizen aus lateinamerikanischen Fundstellen: Cerro Rico
    # Potosi Bolivien, Chuquicamata Chile, La Rinconada Peru) - symmetrische
    # Ergaenzung zum ES-Monat-Block in :data:`_MONTH_NAMES` (enero..diciembre,
    # 652ac1a). Konvention identisch zu DE/EN/FR/IT: meteorologischer Saison-
    # Startmonat des genannten Jahres (Maerz/Juni/September/Dezember).
    # "primavera" bereits im IT-Block eingetragen (identische ES/IT-Schreibweise
    # auf denselben Monatswert 03). verano=Sommer und invierno=Winter sind
    # rein ASCII und ES-spezifisch (keine Kollision mit DE/EN/FR/IT-Bestand).
    # Der Herbst-Name enthaelt Diakritika (``otoño`` mit Tilde-N), der bestehende
    # NFKD-Post-Strip in :func:`_normalize_season_name` (spiegelt
    # :func:`_normalize_month_name`) dekomponiert U+00F1 zu ``n`` + Combining-
    # Tilde und strippt letzteres, sodass sowohl "otoño 2024" als auch die
    # ASCII-Notation "otono 2024" (aus DBs mit nur-ASCII-Feldern) auf denselben
    # Dict-Key ``otono`` mappen - spiegelt die identische Behandlung von FR
    # ``été``->``ete`` und ES-Monatsnamen mit Diakritika im gleichen NFKD-Pfad.
    "verano": 6, "otono": 9, "invierno": 12,
    # Portugiesische Saison-Namen (Sammler-Region Portugal mit den Wolframit-/
    # Quarz-Fundstellen Panasqueira/Beira Baixa sowie brasilianische Pegmatit-
    # Region Minas Gerais/Bahia/Espirito Santo, aus der Sammler-Notizen und
    # Foto-Captions haeufig in PT-Sprache gepflegt sind: "verão de 2019 em
    # Minas Gerais", "outono de 2020 em Panasqueira", "inverno de 1985 em
    # Ouro Preto") - symmetrische Ergaenzung zum PT-Monat-Block in
    # :data:`_MONTH_NAMES` (janeiro..dezembro, Vorgaenger-Commit). Konvention
    # identisch zu DE/EN/FR/IT/ES: meteorologischer Saison-Startmonat des
    # genannten Jahres (Maerz/Juni/September/Dezember). "primavera" und
    # "inverno" bereits ueber den IT-/ES-Block eingetragen (identische PT/IT/
    # ES-Schreibweise, identische Monatswerte).
    #
    # Der Sommer-Name "verão" enthaelt Diakritika (a-tilde U+00E3), der
    # bestehende NFKD-Post-Strip in :func:`_normalize_season_name`
    # dekomponiert U+00E3 zu ``a`` + Combining-Tilde und strippt letzteres,
    # sodass sowohl "verão 2024" als auch die ASCII-Notation "verao 2024"
    # (aus DBs mit nur-ASCII-Feldern) auf denselben Dict-Key "verao" mappen -
    # spiegelt die identische Behandlung von ES "otoño"->"otono" und FR
    # "été"->"ete" im gleichen NFKD-Pfad. Der ASCII-Key "verao" kollidiert
    # NICHT mit dem bereits eingetragenen ES "verano", weil PT mit -ao
    # (nasalisierter Vokal, ohne trailing -n) geschrieben wird, ES mit -ano
    # (klassisch lateinische Endung mit -n) - beide Formen koexistieren als
    # separate Dict-Keys auf denselben Monatswert 06 (Regression-Assert im
    # Testblock sichert die Koexistenz).
    #
    # Der Herbst-Name "outono" ist rein ASCII (keine Diakritika) und PT-
    # spezifisch (differenziert vom ES-Post-Strip-Key "otono" mit ES-
    # Anfangsvokal o, PT hat den Diphthong-Anfang ou-) - separate Dict-Keys
    # auf denselben Monatswert 09.
    "verao": 6, "outono": 9,
}
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Saison-Wort und Jahr
# deckt die natuerlichsprachige DE-/EN-Prosa-Form ab: ``Sommer von 2024`` /
# ``Winter von 1985`` (DE), ``summer of 2024`` / ``autumn of 2019`` (EN).
# Spiegelt die identische Erweiterung in :data:`_MONTH_YEAR` (Monatsname-
# Achse) und :data:`_KW_YEAR` (Wochen-Achse) auf die Saison-Achse. Beide
# Praepositionen verlangen Whitespace auf beiden Seiten (``\s+...\s+``),
# sodass Kompositum-Formen (``Sommervon``, ``Sommer-von``) still fehl-
# matchen. Case-Insensitivitaet nach oben aufgenommen (spiegelt
# :data:`_MONTH_YEAR`) damit Excel-Auto-Fill-/Uppercase-Titel-Varianten
# (``SOMMER VON 2024``, ``SUMMER OF 2024``) ohne Regel-Doppel-Pflege
# matchen; die reine :func:`_normalize_season_name`-Aufloesung war schon
# case-insensitive (via ``.lower()``-Normierung), diese Erweiterung setzt
# nur die Regex-Level-Konvention nach.
_SEASON_YEAR = re.compile(
    r"^\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?(?:\s*[,_ ]?\s*|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)
# Winter-Cross-Year-Notation ("Winter 2023/2024", "Winter 2023/24", "Winter
# 1999-2000", "Winter 2023-24") - sehr verbreitet in Sammlungs-Notizen und
# Foto-Captions, wenn der Fund oder die Aktivitaet in die Winter-Saison faellt,
# die per Konvention zwei Kalenderjahre umschliesst (Dezember - Februar).
# Ohne diese Notation fielen alle Formen mit Doppel-Jahr-Notation stille auf
# None, obwohl "Winter YYYY/YYYY+1" die de-facto Konvention fuer den Winter-
# Zeitraum in Wetter-/Klima-Kontexten und Sammler-Etiketten ist ("Winter
# 2023/24 in den Schweizer Alpen gefunden", "Wintersaison 2023/2024",
# "collected winter 2023-24 from a Swiss dealer").
#
# Konvention: Winter-Startmonat ist Dezember des ersten Jahres (spiegelt
# _SEASON_MONTHS["winter"] = 12 und die bereits fuer "Winter YYYY" (ohne
# Cross-Year-Notation) gelieferte YYYY-12-01-Semantik). Zwei-Ziffer-Kurzform
# im zweiten Jahr ("2023/24" statt "2023/2024") wird auf das benachbarte
# Jahrhundert des ersten Jahres normalisiert: 2023 + 24 -> 2024 (nicht 1924).
# Semantische Konsistenz-Pruefung: das zweite Jahr muss exakt das erste Jahr
# plus 1 sein (typische Winter-Semantik); alle anderen Kombinationen fallen
# auf None (Tippfehler oder falsche Interpretation als Jahres-Range statt
# Winter-Range).
#
# Nur "winter"/"Winter" wird akzeptiert - die uebrigen Saisons (Fruehling,
# Sommer, Herbst) enden natuerlicherweise innerhalb eines Kalenderjahres und
# haben keine Cross-Year-Notation im gaengigen Sprachgebrauch. Slash und
# Bindestrich als Trenner symmetrisch zur bereits vorhandenen _YEAR_RANGE-
# Konvention ("1999/2000" und "1999-2000" beide erlaubt). Vor _SEASON_YEAR
# geprueft, weil das Basis-Pattern nur eine 4-Ziffer-Jahres-Zahl akzeptiert
# und die Doppel-Jahr-Form (4/4 oder 4/2 Ziffern) strukturell disjunkt ist.
_SEASON_CROSS_YEAR = re.compile(
    r"^\s*(winter)\.?\s*[, ]?\s*(\d{4})\s*[/\-–—]\s*(\d{4}|\d{2})\s*$",
    re.IGNORECASE,
)
# Saison-Spanne ("Sommer bis Herbst 2024", "Sommer-Herbst 2024", "summer to
# fall 2024", "spring-autumn 2024") - spiegelt _YEAR_RANGE / _YEAR_RANGE_WORD
# / _DECADE_RANGE / _CENTURY_RANGE_* auf die Saison-Achse. In Sammler-Notizen,
# Feld-Tagebuechern und Foto-Captions sehr verbreitet, wenn der Fund oder die
# Sammel-Aktivitaet ueber mehrere Saisons desselben Jahres lief ("Feldsaison
# Sommer bis Herbst 2024", "Alpen-Exkursion Fruehjahr-Sommer 1985", "collecting
# season spring to autumn 2020"). Bisher fielen alle Formen still auf None,
# weil _SEASON_YEAR / _SEASON_YEAR_FIRST eine einzelne Saison verlangen und
# _YEAR_RANGE / _YEAR_RANGE_WORD zwei 4-Ziffer-Jahres-Anker erwarten - stiller
# Datenverlust auf einer typischen Sammel-Zeitraum-Notation.
#
# Konvention identisch zu _YEAR_RANGE / _DECADE_RANGE / _CENTURY_RANGE_*: die
# LINKE Saison als Anker, ihr meteorologischer Saison-Startmonat plus Jahres-
# Zahl auf den 1. des Monats gesetzt ("Sommer bis Herbst 2024" -> Sommer-Start
# = Juni -> "2024-06-01"). Inverted Spanne ("Herbst bis Sommer 2024",
# Tippfehler) liefert die linke Saison ("2024-09-01"), spiegelt die
# _YEAR_RANGE-Konvention auf die Saison-Achse.
#
# Winter als linke Saison bleibt semantisch am Dezember des genannten Jahres
# haengen (spiegelt _SEASON_MONTHS["winter"] = 12); Notationen wie "Winter-
# Fruehling 2024" liefern damit "2024-12-01" (dokumentiert; die Cross-Year-
# Semantik zwischen Winter 2023/24 und Fruehling 2024 ist im Freitext nicht
# eindeutig aufloesbar - der Sammler soll die Cross-Year-Form "Winter 2023/24"
# explizit nutzen, wenn er die Zwei-Jahr-Semantik meint).
#
# Separator-Alternante vereinigt die Symbol-Klasse [-–—−/] (ASCII-Bindestrich,
# En-Dash U+2013, Em-Dash U+2014, Minus U+2212, Slash) und die Wort-Klasse
# (bis/to/till/until mit obligatorischem Whitespace) - spiegelt _YEAR_RANGE /
# _DECADE_RANGE / _CENTURY_RANGE_*. Der Wort-Zweig verlangt Whitespace, weil
# "Sommerbis Herbst" nie in natuerlicher Notation vorkommt.
#
# Saison-Namen aus _SEASON_MONTHS (Fruehling/Fruehjahr/spring, Sommer/summer,
# Herbst/autumn/fall, Winter, plus Frueh-/Spaet-Kompositum-Formen) werden ueber
# _normalize_season_name aufgeloest - dieselbe Umlaut-Transliteration und
# Case-Fold wie in _SEASON_YEAR. Unbekannte Wort-Kombinationen (Monatsnamen,
# Freitext, Tippfehler wie "Sonner statt Sommer") fallen still auf None,
# spiegelt die _SEASON_YEAR-Fall-Through-Semantik.
#
# Vor _SEASON_YEAR / _SEASON_YEAR_FIRST geprueft, damit die Spanne-Form (die
# strukturell zwei Saison-Woerter enthaelt) nicht vom base _SEASON_YEAR-
# Pattern (nur eines) geblockt wird. Kollisionsfrei zu _SEASON_CROSS_YEAR
# (dort obligatorisch "winter" plus Doppel-Jahr, hier zwei beliebige Saisons
# plus ein Jahr), zu _YEAR_RANGE (dort vier Ziffern, hier zwei Woerter plus
# Jahr) und zu _MONTH_RANGE_YEAR (dort Monatsnamen; die Fall-Through-Semantik
# ueber _normalize_season_name filtert Monatsnamen aus).
_SEASON_RANGE = re.compile(
    r"^\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?"
    r"(?:\s*[-–—−/]\s*|\s+(?:bis|to|till|until)\s+)"
    r"([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?"
    r"\s+(\d{4})\s*$",
    re.IGNORECASE,
)
# Year-first Jahreszeit-Notation ("2024 Sommer", "1985-Winter", "2024/Herbst",
# "2024 spring", "1999.Fruehjahr"). Spiegelt :data:`_SEASON_YEAR` auf die
# Year-First-Reihenfolge, analog zu :data:`_QUARTER_YEAR_FIRST` /
# :data:`_HALFYEAR_YEAR_FIRST` gegenueber ihren Year-Last-Basisformen. In
# Sammlungs-Notizen, Foto-Captions und Tagebuch-Eintraegen, die das Jahr als
# ordnenden Schluessel voranstellen ("Sammlung 2024 Sommer - Tucson-Boerse",
# "Fotos 1985 Winter") oder in denen das Datum-Feld aus einem sortierten
# Excel-Auto-Fill kommt, wird die Saison typischerweise NACH der Jahres-Zahl
# notiert - genauso wie die Quartal-/Halbjahr-Angabe in Business-Reports
# ("2024-Q1", "2024-H2"). Vor dem Fix fielen alle Formen still auf None,
# obwohl die identische Year-Last-Form (":data:`_SEASON_YEAR`") transparent
# das Datum lieferte - eine Asymmetrie zwischen den beiden Reihenfolgen, die
# die haeufigere DE-Excel-/Ordner-Struktur-Praxis (Jahr zuerst als sortierender
# Praefix) benachteiligt hat. Konvention identisch zu _SEASON_YEAR: der
# Saison-Startmonat aus :data:`_SEASON_MONTHS` (Fruehling/Fruehjahr/spring ->
# Maerz, Sommer/summer -> Juni, Herbst/autumn/fall -> September, Winter ->
# Dezember) auf den 1. des Monats gesetzt. Separatoren [/.\-, ] spiegeln die
# _QUARTER_YEAR_FIRST-/_HALFYEAR_YEAR_FIRST-/_YEAR_MONTH_NAME-Konvention
# (Bindestrich, Slash, Punkt, Komma, Leerzeichen).
#
# Kollisionsfreiheit zur bereits vorhandenen _YEAR_MONTH_NAME-Erkennung: das
# Basis-Pattern matcht dieselbe Struktur (Jahr + Separator + Wort), aber die
# Monatsnamen-Normalisierung liefert fuer Saison-Woerter None und die Funktion
# faellt weiter durch - dieser neue Pfad greift genau dann, wenn das Wort
# eine Saison und kein Monat ist. Kollisionsfreiheit zu _SEASON_CROSS_YEAR:
# die Cross-Year-Form beginnt mit einem Saison-Wort (nicht mit einer Jahres-
# Zahl) und ist strukturell disjunkt. Kollisionsfreiheit zu _RELATIVE_YEAR:
# das relative-Praefix-Pattern verlangt "Anfang"/"Mitte"/"Ende"/"early"/"mid"/
# "late" VOR der Jahreszahl - hier steht das Saison-Wort NACH der Jahreszahl,
# klar disjunkt. Nach _SEASON_CROSS_YEAR / _SEASON_YEAR einsortiert (im
# parse_iso_date-Body), damit die spezifischeren Formen (Cross-Year, Year-Last-
# Basis) zuerst gepruft werden - die Reihenfolge folgt der etablierten
# Spezifisch-vor-Allgemeinen-Konvention der uebrigen Patterns.
_SEASON_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, _]\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?\s*$",
)

# Fixed-Date-Feiertag + Jahr ("Weihnachten 2023", "Silvester 2020", "Neujahr
# 2024", "Halloween 2019", "Nikolaustag 2022", "Heiligabend 2023", "Tag der
# Arbeit 2024", "Tag der deutschen Einheit 2023", "Heilige Drei Koenige 2024",
# "Bundesfeier 2023"). Sehr verbreitet in Sammlungs-Notizen, Foto-Captions und
# Tagebuch-Eintraegen, wenn der Sammler das Fund-/Kauf-/Foto-Datum nicht exakt
# notierte, sondern sich an dem markanten Feiertag orientierte ("Am
# Weihnachten 2023 vom Vater geschenkt bekommen", "Silvester-Fund 2020 in
# Rhein-Kies", "Halloween-Auktion 2019 seltener Chalcedon"). Bisher fielen
# alle Feiertags-Formen still auf None, obwohl der Feiertag semantisch einen
# eindeutigen Kalendertag anmarkiert - :data:`_MONTH_YEAR` matcht das Pattern
# (ein Wort + Jahr), aber :func:`_normalize_month_name` liefert fuer den
# Feiertag-Namen None, dieselbe Fall-Through-Semantik gilt fuer
# :data:`_SEASON_YEAR` mit :func:`_normalize_season_name`.
#
# Whitelist der Fixed-Date-Feiertage (DACH + Standard-EN-Termine). Variable
# Feiertage (Ostern, Karfreitag, Ostermontag, Pfingsten, Christi Himmelfahrt,
# Fronleichnam, Muttertag, Vatertag) sind bewusst NICHT eingeschlossen -
# sie erfordern jaehrlich unterschiedliche Datums-Berechnung (Osterberechnung
# via Butcher/Meeus-Algorithmus, Muttertag = zweiter Mai-Sonntag, Vatertag
# = 40 Tage nach Ostern in DE) und werden aus Konservativitaets-Gruenden
# in einem separaten spaeteren Fix behandelt.
_HOLIDAY_MONTH_DAY: dict[str, tuple[int, int]] = {
    # Januar
    "neujahr": (1, 1),
    "neujahrstag": (1, 1),
    "newyear": (1, 1),
    "newyearsday": (1, 1),
    "dreikoenigstag": (1, 6),
    "heiligedreikoenige": (1, 6),
    "epiphany": (1, 6),
    # Februar
    "valentinstag": (2, 14),
    "valentinesday": (2, 14),
    # Maerz
    # Josefstag/Josefitag/Josephstag (19. Maerz): katholischer Hochfest-Termin,
    # gesetzlicher Feiertag in den katholischen Schweizer Kantonen Tessin,
    # Uri, Nidwalden, Wallis, Zug, Schwyz und Luzern; in Sammler-Notizen aus
    # Innerschweizer Mineralboersen und Tessiner Sammler-Vereinigungen als
    # Datums-Marker etabliert. Englische Form "St. Joseph's Day" / "Saint
    # Joseph's Day" spiegelt die St.-Nikolaus-/St.-Stephan-Konvention.
    "josefstag": (3, 19),
    "josefitag": (3, 19),
    "josephstag": (3, 19),
    "stjosefstag": (3, 19),
    "stjosephsday": (3, 19),
    "saintjosephsday": (3, 19),
    # Mai
    "tagderarbeit": (5, 1),
    "arbeiterfeiertag": (5, 1),
    "arbeiterkampftag": (5, 1),
    "labourday": (5, 1),
    "laborday": (5, 1),
    "mayday": (5, 1),
    # Juni
    # Peter und Paul (29. Juni): katholisches Hochfest der Apostelfuersten,
    # gesetzlicher Feiertag in den Schweizer Kantonen Tessin und Graubuenden;
    # in italienisch- und ruhetorontinisch-sprachigen Sammler-Notizen aus
    # dem Tessiner Alpenraum (mineralienreiche Provenienz Val Bedretto /
    # Cristallina) als Datums-Marker etabliert. Englische Form "Feast of Saints
    # Peter and Paul" wird auf die Norm-Schluessel "peterandpaul" /
    # "stspeterandpaul" gemappt (Norm-Schluessel strippt Whitespace/./',
    # sodass "Sts. Peter and Paul" == "stspeterandpaul" == "St. Peter and Paul").
    "peterundpaul": (6, 29),
    "petriundpauli": (6, 29),
    "petrusundpaulus": (6, 29),
    "peterandpaul": (6, 29),
    "stspeterandpaul": (6, 29),
    "saintspeterandpaul": (6, 29),
    "feastofstspeterandpaul": (6, 29),
    # August
    "bundesfeier": (8, 1),
    "schweizernationalfeiertag": (8, 1),
    "swissnationalday": (8, 1),
    # Mariae Himmelfahrt / Assumption of Mary (15. August): katholisches
    # Hochfest, gesetzlicher Feiertag in Oesterreich (national), in Bayern
    # (Gemeinden mit ueberwiegend katholischer Bevoelkerung) und im Saarland
    # sowie in vielen Schweizer Kantonen (LU, UR, SZ, OW, NW, ZG, FR, SO,
    # AI, JU, TI, VS). Sehr verbreitet als Datums-Marker in Sammler-Notizen
    # aus Bayerischen/Oesterreichischen Mineralboersen und Innerschweizer
    # Fundort-Etiketten (der Feiertag faellt in die Haupt-Sommer-Sammel-Saison
    # in den Alpen, ist entsprechend haeufig als Fund-Datum vermerkt).
    "mariaehimmelfahrt": (8, 15),
    "mariahimmelfahrt": (8, 15),
    "hoheunserefrau": (8, 15),
    "assumption": (8, 15),
    "assumptionofmary": (8, 15),
    "assumptionofthevirginmary": (8, 15),
    "assumptionofourlady": (8, 15),
    # Oktober
    "tagderdeutscheneinheit": (10, 3),
    "germanunityday": (10, 3),
    "halloween": (10, 31),
    # Reformationstag / Reformation Day (31. Oktober): evangelischer Gedenktag
    # an Luthers Thesenanschlag 1517, gesetzlicher Feiertag in den evangelisch
    # gepraegten deutschen Bundeslaendern Sachsen, Sachsen-Anhalt, Thueringen,
    # Brandenburg, Mecklenburg-Vorpommern (durchgaengig seit 1990) sowie
    # zusaetzlich in Bremen, Hamburg, Niedersachsen und Schleswig-Holstein
    # seit dem 500. Reformations-Jubilaeum 2018. Datum kollidiert mit
    # Halloween (bereits vorhanden, ebenfalls (10, 31)) - der Dict akzeptiert
    # beide Norm-Schluessel gleichberechtigt, weil der Ausgabe-Wert identisch
    # ist und die semantische Ambiguitaet ("wurde am Reformationstag oder
    # in der Halloween-Nacht gefunden") fuer die Fund-Datums-Semantik der
    # Sammlungs-DB irrelevant ist.
    "reformationstag": (10, 31),
    "reformationsfest": (10, 31),
    "reformationday": (10, 31),
    # November
    "allerheiligen": (11, 1),
    "allsaintsday": (11, 1),
    # Allerseelen / All Souls' Day (2. November): katholischer Gedenktag der
    # verstorbenen Glaeubigen, direkt nach Allerheiligen (bereits vorhanden,
    # (11, 1)). Kein gesetzlicher Feiertag in DACH, aber als kirchlicher
    # Gedenktag in katholisch gepraegten Sammler-Notizen als Datums-Marker
    # gefuehrt (Friedhofs-Gaenge/Familienfeiern rund um Allerheiligen +
    # Allerseelen sind der klassische Anlass fuer Fund-Doku-Sichtungen alter
    # Sammlungsbestaende). Englische Form "All Souls' Day" spiegelt die
    # "All Saints Day"-Konvention (Norm-Schluessel strippt Apostroph).
    "allerseelen": (11, 2),
    "allsouls": (11, 2),
    "allsoulsday": (11, 2),
    # Dezember
    "nikolaus": (12, 6),
    "nikolaustag": (12, 6),
    "stnicholasday": (12, 6),
    # Mariae Empfaengnis / Immaculate Conception (8. Dezember): katholisches
    # Hochfest, gesetzlicher Feiertag in Oesterreich (national) sowie in
    # den katholischen Schweizer Kantonen Luzern, Uri, Schwyz, Obwalden,
    # Nidwalden, Zug, Freiburg, Solothurn, Appenzell Innerrhoden, Tessin und
    # Wallis. In Sammler-Notizen aus katholisch gepraegten Regionen als
    # Vor-Weihnachts-Datums-Marker verbreitet. Englische Form "Immaculate
    # Conception" spiegelt die Assumption-of-Mary-Konvention.
    "mariaeempfaengnis": (12, 8),
    "mariaempfaengnis": (12, 8),
    "empfaengnismariae": (12, 8),
    "immaculateconception": (12, 8),
    "feastoftheimmaculateconception": (12, 8),
    "heiligabend": (12, 24),
    "christmaseve": (12, 24),
    "weihnachten": (12, 25),
    "weihnachtstag": (12, 25),
    "erstenweihnachtsfeiertag": (12, 25),
    "ersterweihnachtsfeiertag": (12, 25),
    "christmas": (12, 25),
    "christmasday": (12, 25),
    "stephanstag": (12, 26),
    "stefanstag": (12, 26),
    "zweitenweihnachtsfeiertag": (12, 26),
    "zweiterweihnachtsfeiertag": (12, 26),
    "boxingday": (12, 26),
    "silvester": (12, 31),
    "silvesterabend": (12, 31),
    "newyearseve": (12, 31),
}
# Variable Feiertage: Osterdatums-relative Offsets in Tagen (positive = nach
# Ostersonntag, negative = davor). Der konkrete Kalendertag jedes Feiertags
# haengt vom jahresspezifisch berechneten Ostersonntag ab (Computus /
# Butcher-Meeus Gregorian-Algorithmus in :func:`_easter_sunday`) und wird zur
# Migrationszeit fuer das gegebene Jahr aufgeloest. Der Osterzyklus liefert
# Fest-Termine, die kirchlicher und weltlicher Konvention nach in DACH und im
# angelsaechsischen Raum an einheitlichen Offset-Positionen liegen (Karfreitag
# = 2 Tage vor Ostern, Christi Himmelfahrt = 39 Tage nach Ostern, Pfingsten
# = 49 Tage nach Ostern, Fronleichnam = 60 Tage nach Ostern; alle vom Konzil
# von Nicaea 325 bzw. der Gregorianischen Kalender-Reform 1582 verbindlich
# festgelegt). Muttertag/Vatertag sind bewusst NICHT enthalten - deren
# Definitionen weichen zwischen den Kultur- und Rechtsraeumen ab (DE-Muttertag
# = zweiter Mai-Sonntag mit Sonderregel-Verschiebung bei Kollision mit
# Pfingstsonntag; US-Muttertag = zweiter Mai-Sonntag ohne Sonderregel;
# DE-Vatertag = Christi Himmelfahrt, US-Vatertag = dritter Juni-Sonntag). Ohne
# Locale-Marker im Datums-Feld ist die richtige Auswahl mehrdeutig, und ein
# stillschweigend gewaehlter Default wuerde in bis zu 50% der Faelle das
# falsche Datum vergeben. Norm-Schluessel spiegelt die Normalisierung in
# :func:`_normalize_holiday_name` (lowercase, Umlaut -> ae/oe/ue/ss,
# Whitespace/Punkt/Bindestrich/Apostroph gestrippt): "Christi Himmelfahrt" ->
# "christihimmelfahrt", "Palm Sunday" -> "palmsunday", "Gründonnerstag" ->
# "gruendonnerstag".
_HOLIDAY_EASTER_OFFSET: dict[str, int] = {
    # Karwoche vor Ostersonntag
    "palmsonntag": -7,
    "palmsunday": -7,
    "gruendonnerstag": -3,
    "maundythursday": -3,
    "holythursday": -3,
    "karfreitag": -2,
    "goodfriday": -2,
    "karsamstag": -1,
    "karsonnabend": -1,
    "holysaturday": -1,
    # Ostersonntag = Anker (0)
    "ostern": 0,
    "ostersonntag": 0,
    "easter": 0,
    "eastersunday": 0,
    # Osterwoche
    "ostermontag": 1,
    "eastermonday": 1,
    # Fastnachtszeit vor Ostern (relativ zu Aschermittwoch)
    "aschermittwoch": -46,
    "ashwednesday": -46,
    "fastnachtsdienstag": -47,
    "faschingsdienstag": -47,
    "fasnachtsdienstag": -47,
    "shrovetuesday": -47,
    "mardigras": -47,
    "fattuesday": -47,
    "pancakeday": -47,
    "rosenmontag": -48,
    "weiberfastnacht": -52,
    "weiberfasnacht": -52,
    "weiberfasnet": -52,
    "schmotzigerdonnerstag": -52,
    # Nach Ostern
    "christihimmelfahrt": 39,
    "himmelfahrt": 39,
    "ascensionday": 39,
    "ascension": 39,
    "ascensionofchrist": 39,
    "ascensionofourlord": 39,
    "pfingsten": 49,
    "pfingstsonntag": 49,
    "pentecost": 49,
    "whitsun": 49,
    "whitsunday": 49,
    "pfingstmontag": 50,
    "whitmonday": 50,
    "pentecostmonday": 50,
    "trinitatis": 56,
    "trinitysunday": 56,
    "fronleichnam": 60,
    "corpuschristi": 60,
}


def _easter_sunday(year: int) -> tuple[int, int]:
    """Osterdatum (Monat, Tag) via Butcher-Meeus Gregorian-Algorithmus.

    Anonymer Gregorianischer Osterrechen-Algorithmus (Butcher 1876, ueberliefert
    ueber Jean Meeus' "Astronomical Algorithms"). Deckt alle Jahre >= 1583 (also
    das gesamte Fenster des :func:`parse_iso_date`-1800..2999-Bandes) korrekt
    ab. Berechnet den ersten Sonntag nach dem ersten Vollmond nach der
    Fruehjahrs-Tag-und-Nacht-Gleiche gemaess der Gregorianischen Reform von 1582
    und dem Konzil von Nicaea 325 - Standarddefinition der Westkirche
    (Katholisch, Lutherisch, Anglikanisch, Reformiert); die orthodoxe Kirche
    verwendet den Julianischen Kalender fuer die Berechnung, aber deren
    Konvention ist im DACH-Sammler-Kontext irrelevant und der Feiertag "Ostern"
    ohne Konfessions-Marker bezeichnet dort ausschliesslich das westliche
    Datum. Rueckgabe (Monat, Tag) mit Monat in {3, 4} und Tag in [22..25]
    fuer Maerz bzw. [1..25] fuer April.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = ((h + ll - 7 * m + 114) % 31) + 1
    return month, day
# Feiertag-Name (ein oder mehrere Woerter, keine Ziffern) + Trenner + Jahr.
# Die Zeichenklasse deckt Multi-Wort-Formen ("Heilige Drei Koenige"), Apostrophe
# (ASCII ``'``, typografisch ``’``/``‘`` aus Word-Autoformat), Punkte
# ("St. Nicholas Day") und Bindestriche ("St-Stephens-Day") ab. Trenner-Klasse
# ``[\s,_/]+`` verlangt mindestens einen Trenner zwischen Name und Jahr, sodass
# angehaengte Formen ohne Whitespace (``Weihnachten2023``) mangels vollstaendiger
# Struktur unangetastet auf None fallen - konsistent zur natuerlichsprachigen
# Notation, die immer Trenner setzt. Bindestrich bewusst NICHT im Trenner, weil
# er in Multi-Wort-Namen (``St-Stephens-Day``) selbst Teil des Namens ist und
# die non-greedy Name-Auswahl nicht sicher zwischen Namens-Bindestrich und
# Trenner-Bindestrich unterscheidet. Praeposition ``von``/``of`` als Wort-
# Trenner symmetrisch zu :data:`_MONTH_YEAR` / :data:`_SEASON_YEAR`.
_HOLIDAY_YEAR = re.compile(
    r"^\s*([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœß.’‘' \-]+?)"
    r"(?:[\s,_/]+|\s+(?:von|of)\s+)"
    r"(\d{4})\s*$",
    re.IGNORECASE,
)
# Year-first Feiertag-Notation ("2023 Weihnachten", "2020-Silvester",
# "2024/Halloween", "2019 Nikolaustag"). Spiegelt :data:`_HOLIDAY_YEAR` auf
# die Year-First-Reihenfolge, analog zu :data:`_SEASON_YEAR_FIRST` gegenueber
# :data:`_SEASON_YEAR`. In Sammlungs-Notizen mit Excel-Auto-Fill oder Ordner-
# Struktur ("2023/Weihnachten/...") oder in narrativen Tagebuch-Eintraegen
# ("Sammlung 2024 Halloween-Auktion"), die das Jahr als sortierenden Praefix
# voranstellen. Konvention identisch zur Year-Last-Form: der Feiertag-Tag
# aus :data:`_HOLIDAY_MONTH_DAY`.
_HOLIDAY_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})"
    r"(?:[\s,_/\-]+|\s+(?:von|of)\s+)"
    r"([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœß.’‘' \-]+?)\s*$",
    re.IGNORECASE,
)

# Quartal + Jahr ("Q1 2024", "Q3/1985", "1. Quartal 2024", "3. Quarter 1985",
# "1Q2024", "Quartal 1 2024"). Konvention: Quartals-Startmonat (Jan/Apr/Jul/Okt).
# Akzeptiert sowohl deutsche ("Quartal") als auch englische ("Quarter") Schreibweise.
_QUARTER_MONTHS: dict[int, int] = {1: 1, 2: 4, 3: 7, 4: 10}
# "Q1 2024" / "Q1/2024" / "Q1-2024" / "1Q 2024"
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Q-Marker und Jahr deckt
# die natuerlichsprachige DE-/EN-Prosa-Form ``Q1 von 2024`` / ``Q3 of 1985`` /
# ``1Q von 2024`` ab, die in Sammler-Fund-Tagebuechern und Geschaefts-Perioden-
# Prosa die uebliche Verbindungs-Form zwischen Quartals-Marker und Jahr ist
# ("Fund Q1 von 2024 im Aaregebiet", "Bergtour 3Q of 2019 an der Tucson-Boerse",
# "Erwerb Q2 von 2020 Zermatt"). Bisher fielen alle Praepositions-Formen still
# auf None, weil die Separator-Klasse ``[/.\-,]?`` nur Ein-Zeichen-Trenner
# (Slash, Punkt, Bindestrich, Komma) plus umgebendes Whitespace kennt und keinen
# Wort-Trenner - typische DE-/EN-Prosa-Notizen aus Fund-Tagebuechern gingen als
# silenter Funddatum-Datenverlust in die Migration. Spiegelt die "of"-Praepositions-
# Erweiterung aus :data:`_DAY_OF_MONTH_YEAR` (englische Ordinal-Konstruktion "the
# 4th of July 2019") und :data:`_KW_YEAR` (Wochen-Achse ``KW 25 von 2024``) auf
# die Quartals-Achse. Beide Praepositionen verlangen Whitespace auf beiden Seiten
# (``\s+...\s+``), sodass Kompositum-Formen (``vondel``, ``vonof``) und angehaengte
# Formen (``Q1von 2024``, ``Q1 von2024``) mangels vollstaendiger Struktur
# unangetastet auf None fallen. Case-Insensitivitaet spiegelt die uebrigen
# Marker-Alternativen (``VON``/``OF`` in Grossbuchstaben aus Excel-Auto-Fill /
# Uppercase-Titeln matchen ohne Regel-Doppel-Pflege). Kollisionsfrei zu
# :data:`_QUARTER_YEAR_FIRST` (Year-First-Form mit anderer Separator-Position,
# dort ist die Praepositions-Semantik ``von``/``of`` nicht idiomatisch).
_QUARTER_SHORT = re.compile(
    r"^\s*(?:Q\s*([1-4])|([1-4])\s*Q)"
    r"(?:\s*[/.\-,_]?\s*|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)
# "1. Quartal 2024" / "Quartal 1 2024" / "3. Quarter 1985" / "1st Quarter 2024"
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Quartal-Wort/Zahl und
# Jahr symmetrisch zur Kurzform (``1. Quartal von 2024`` / ``Quartal 1 of 2024``
# / ``3. Quarter of 1985`` / ``2. Quartal von 1990``). In Prosa-Etiketten und
# Sammler-Notizen ist die Langform-Praepositions-Verbindung die haeufigere
# natuerlichsprachige DE-/EN-Form gegenueber der Kurzform-Q1-Notation, da die
# ausgeschriebene Quartal/Quarter-Bezeichnung typischer fuer Fliesstext ist
# ("Erwerb 1. Quartal von 2020 Zermatt-Bergtour", "Fund 3. Quarter of 2019
# Tucson-Boerse", "Aktivitaeten Quartal 2 von 2024 Aaregebiet-Sammlung").
# Ordinal-Marker ``(?:st|nd|rd|th|\.)?`` deckt symmetrisch die deutsche
# Digit-Punkt-Form ("1. Quartal") und die englische Ordinal-Suffix-Form
# ("1st|2nd|3rd|4th quarter") ab - letztere ist in EN-sprachigen Auktions-
# Katalogen, Mineral-Boersen-Berichten und Sammler-Blogs die Standard-
# Notation, fiel bisher aber still auf None (das reine ``\.?`` erlaubte nur
# den optionalen Punkt). Toleriert bewusst semantisch schiefe Kombinationen
# wie "1th"/"2th"/"3st" (keine Positions-Zwang [1-4]->{st,nd,rd,th}), weil
# die Regex-Klasse ohnehin lenient formuliert ist (Case-Insensitiv, freie
# Separatoren, Praepositions-Alternante) und OCR-/Autocorrect-Artefakte in
# Sammler-Katalog-Notizen gaengig sind; die Fehl-Kombinationen bleiben
# nachtraeglich sichtbar via :func:`find_rows_with_invalid_funddatum`.
# Kollisionsfrei zu bestehenden ``st|nd|rd|th``-Vorkommen in
# :data:`_CENTURY_YEAR` (Century-Pattern, eigener Zweig) und den Tag-
# Ordinal-Formen (nach der Ziffer, nicht nach dem Quartal-Keyword) - der
# Quartal-Zweig setzt es explizit VOR das Quartal-/Quarter-Keyword und
# teilt die semantische Position mit dem DE-Punkt-Marker.
_QUARTER_LONG = re.compile(
    r"^\s*(?:([1-4])\s*(?:st|nd|rd|th|\.)?\s*(?:quartal|quarter)|(?:quartal|quarter)\s+([1-4]))"
    r"(?:\s*[/.\-, ]?\s*|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)
# Year-first Quartals-Notation: "2024-Q1", "2024/Q1", "2024 Q1", "2024Q1",
# "2024-1Q". Spiegelt _QUARTER_SHORT auf die finanzielle/business-typische
# Jahr-zuerst-Reihenfolge (Quartalsreports, Excel-Auto-Format "2024-Q1",
# Buchhaltungsperioden). Konvention identisch zum Year-Last-Pattern:
# Quartals-Startmonat (Jan/Apr/Jul/Okt). Optionaler Separator [/.\- ,] zwischen
# Jahr und Q deckt sowohl ASCII-Bindestrich als auch Whitespace und kein-
# Separator-Compact-Form ("2024Q1") ab. Vor _QUARTER_SHORT geprueft waere
# unschaedlich (kollisionsfreie Reihenfolge: Jahr-zuerst beginnt mit 4 Ziffern,
# Q-zuerst beginnt mit Q oder Ziffer 1-4), wird aber konsistent mit den
# anderen Year-First-Patterns am gleichen Block-Ende einsortiert.
_QUARTER_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, _]?\s*(?:Q\s*([1-4])|([1-4])\s*Q)\s*$",
    re.IGNORECASE,
)
# Year-first Langform-Quartal: "2024 1. Quartal" / "2024 Quartal 1" /
# "2024-3. Quarter" / "1985, Quartal 4". Spiegelt _QUARTER_LONG auf die
# Jahr-zuerst-Reihenfolge - kommt in Geschaeftsperioden-Reports und einigen
# Sammlungs-Tagebuechern vor, wenn das Jahr als ordnender Schluessel
# vorangestellt wird ("Aktivitaeten 2024 - 1. Quartal: Foto-Session ..."). Wie
# bei _QUARTER_LONG werden beide Reihenfolgen innerhalb der Langform
# akzeptiert (Zahl-vor-Wort "1. Quartal" und Wort-vor-Zahl "Quartal 1"),
# sodass "2024 1. Quartal" und "2024 Quartal 1" identisch behandelt werden.
_QUARTER_LONG_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, ]?\s*"
    r"(?:([1-4])\s*(?:st|nd|rd|th|\.)?\s*(?:quartal|quarter)|(?:quartal|quarter)\s+([1-4]))\s*$",
    re.IGNORECASE,
)

# Halbjahres-Notation (Halfyear) + Jahr - spiegelt das Quartals-Vokabular auf
# die 6-Monats-Achse, die im finanziellen/business-Kontext (Geschaeftsberichte:
# "H1 2024 Umsatz", "Halbjahresbericht 2024") und in einigen Sammlungs-
# Tagebuechern ("1. Halbjahr 2024 - Tucson-Boerse + Schweizer Bergtour")
# verbreitet ist. Konvention: H1 → Januar (Halbjahres-Startmonat), H2 → Juli;
# spiegelt die Quartals-Konvention (Quartals-Startmonat) auf die 6-Monats-Achse.
# Akzeptiert sowohl deutsche ("Halbjahr") als auch englische ("Halfyear"/
# "Half-year") Schreibweise. Bisher fielen alle Formen stille auf None und
# wurden dadurch in der Sammler-Statistik nicht zeitlich verortet.
_HALFYEAR_MONTHS: dict[int, int] = {1: 1, 2: 7}
# "H1 2024" / "H1/2024" / "H1-2024" / "1H 2024" - Kurzform symmetrisch zu
# _QUARTER_SHORT. Akzeptiert Q-Stil ("H1") und Postfix-Stil ("1H"); optionaler
# Separator [/.\-,] zwischen H und Jahr (analog Quartal).
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen H-Marker und Jahr deckt
# die natuerlichsprachige DE-/EN-Prosa-Form ``H1 von 2024`` / ``H2 of 1985`` /
# ``1H von 2024`` ab, die in Sammler-Fund-Tagebuechern und Geschaefts-Halbjahres-
# Prosa die uebliche Verbindungs-Form zwischen Halbjahres-Marker und Jahr ist
# ("Fund H1 von 2024 im Aaregebiet", "Bergtour 2H of 2019 an der Tucson-Boerse",
# "Erwerb H2 von 2020 Zermatt-Bergtour"). Spiegelt die identische Erweiterung
# in :data:`_QUARTER_SHORT` (Commit ...) und :data:`_KW_YEAR` (Wochen-Achse)
# auf die Halbjahres-Achse. Beide Praepositionen verlangen Whitespace auf
# beiden Seiten, sodass Kompositum- und angehaengte Formen unangetastet auf
# None fallen. Kollisionsfrei zu :data:`_HALFYEAR_YEAR_FIRST` (Year-First-Form,
# dort ist die Praepositions-Semantik nicht idiomatisch).
_HALFYEAR_SHORT = re.compile(
    r"^\s*(?:H\s*([1-2])|([1-2])\s*H)"
    r"(?:\s*[/.\-,_]?\s*|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)
# "1. Halbjahr 2024" / "Halbjahr 1 2024" / "2. Halfyear 1985" / "1. Half-Year 2024"
# - Langform symmetrisch zu _QUARTER_LONG. Beide Reihenfolgen (Zahl-vor-Wort
# und Wort-vor-Zahl) werden akzeptiert. Englisch "half year" (zwei Worte) wird
# bewusst nicht erfasst, weil es zu mehrdeutig mit normalen Saetzen waere
# ("the half year ended..."); EN-Form lebt von der Bindestrich-/Compound-
# Variante ("half-year"/"halfyear"), die in Reports der ueblichen Praxis
# entspricht.
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Halbjahr-Wort/Zahl und
# Jahr symmetrisch zur Kurzform (``1. Halbjahr von 2024`` / ``Halbjahr 1 of
# 2024`` / ``2. Halfyear of 1985`` / ``1. Half-Year von 2020``). In Prosa-
# Etiketten und Sammler-Notizen ist die Langform-Praepositions-Verbindung die
# haeufigere natuerlichsprachige DE-/EN-Form gegenueber der Kurzform-H1-
# Notation, da die ausgeschriebene Halbjahr/Halfyear-Bezeichnung typischer
# fuer Fliesstext ist ("Erwerb 1. Halbjahr von 2020 Zermatt-Bergtour", "Fund
# 2. Halfyear of 2019 Tucson-Boerse", "Aktivitaeten Halbjahr 1 von 2024
# Aaregebiet-Sammlung").
_HALFYEAR_LONG = re.compile(
    r"^\s*(?:([1-2])\s*(?:st|nd|rd|th|\.)?\s*(?:halbjahr|half-?year)"
    r"|(?:halbjahr|half-?year)\s+([1-2]))"
    r"(?:\s*[/.\-, ]?\s*|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)
# Year-first Halbjahres-Notation ("2024-H1", "2024 H1", "2024H1", "2024-1H")
# - spiegelt _QUARTER_YEAR_FIRST auf die Halbjahres-Achse. Geschaeftsperioden-
# Reports und Excel-Auto-Format sortieren oft Year-First-formatiert
# ("2024-H1" sortiert lexikographisch korrekt vor "2024-H2").
_HALFYEAR_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, _]?\s*(?:H\s*([1-2])|([1-2])\s*H)\s*$",
    re.IGNORECASE,
)
# Year-first Langform-Halbjahr ("2024 1. Halbjahr", "2024 Halbjahr 1",
# "2024-2. Halfyear") - spiegelt _QUARTER_LONG_YEAR_FIRST. Wie bei der
# Quartals-Langform-Year-First werden beide Reihenfolgen innerhalb der
# Langform akzeptiert.
_HALFYEAR_LONG_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, ]?\s*"
    r"(?:([1-2])\s*(?:st|nd|rd|th|\.)?\s*(?:halbjahr|half-?year)"
    r"|(?:halbjahr|half-?year)\s+([1-2]))\s*$",
    re.IGNORECASE,
)

# ISO 8601 Ordinal-Datum (Tag des Jahres): "2024-165", "2024165" (compact, 7 Ziffern),
# "2024-001". Konvention: Tag 1..366 (366 nur in Schaltjahren). Verbreitet in
# NASA-/wissenschaftlichen Exporten und Astro-Sammler-Notizen ("Julianischer Tag");
# auch in einigen Log-Stempeln (Dateisysteme/Batch-Verarbeitung) als compact 7-Ziffer-Form.
# Vor _YEAR_MONTH geprueft, damit "2024-001" nicht als YYYY-MM mit Monat 001 versucht wird.
_ISO_ORDINAL_DATE = re.compile(
    r"^\s*(\d{4})-?(\d{3})\s*$"
)

# Compact YYYYMM-Form (6 Ziffern, keine Trenner): "202406" -> 2024-06-01,
# "199912" -> 1999-12-01. Sehr verbreitet in Datei-/Ordner-Namen aus Foto-/
# Sammlungs-Archiven ("photos_202406/", "log_202406.txt", "export_202406.csv"),
# in Buchhaltungs-Perioden-Stempeln (Excel-Auto-Format YYYYMM als Text-Spalte,
# um lexikographische Sortierung sicherzustellen), in monatlichen Batch-/
# Backup-Rotation-Skripten ("stone_202406.sqlite3", "backup_202406.tar.gz") und
# in Foto-EXIF-Auto-Renamern (Sony/Canon Kamera-Software schreibt oft YYYYMM
# als Ordner-Praefix). Bisher fiel jede reine 6-Ziffer-Notation ohne Trenner
# auf ein *semantisch falsches* Datum durch: das :data:`_DATE_FORMATS`-Format
# ``%Y%m%d`` (compact YYYYMMDD, 8 Ziffern) matcht per Python-strptime-Greedy-
# Verhalten auch 6-Ziffer-Inputs (das ``%Y``-Directive nimmt gierig die ersten
# 4 Ziffern, ``%m`` und ``%d`` teilen sich die restlichen 2 Ziffern als je
# 1-Ziffer-Fragment). Konkret: ``202412`` wurde zu ``2024-01-02`` (Monat 1,
# Tag 2 statt Monat 12 auf den 1.), ``202406`` fiel via ``ValueError`` (weil
# strptime keine gueltige 5. Ziffer als Tag findet und den ``%d``-Zweig
# blockiert - "202406" hat 6 Ziffern, %Y=2024, %m=0, %d=6 wuerde Monat 0 sein
# und scheitert), aber ``202412`` (%Y=2024, %m=1, %d=2, alle gueltig) fiel
# durch und lieferte ein semantisch komplett falsches ISO-Datum (2024-01-02
# statt 2024-12-01, Januar-Zweiter statt Dezember-Erster - eine 11-Monats-
# Verschiebung). Bei der Migration aus Foto-Ordner-Namen, aus Datei-basierten
# Sammlungs-Metadaten und aus Buchhaltungs-Perioden-Stempeln entstand damit
# silenter Funddatum-Datenverlust bzw. -Verzerrung auf jeder Achse, die den
# Fundzeitpunkt aus dem Datei-/Ordner-Namen ableitet.
#
# Der Fix legt eine spezifische 6-Ziffer-Regex VOR den strptime-Loop, sodass
# alle 6-Ziffer-Pure-Digit-Inputs zuerst als YYYYMM interpretiert werden -
# entweder erfolgreich (Monat 1..12, Jahr 1800..2999 -> ISO-Datum am 1. des
# Monats, analog zu _YEAR_MONTH und _MONTH_NUMERIC_YEAR) oder mit Rueckgabe
# None (blockiert die falsche %Y%m%d-Greedy-Interpretation im nachfolgenden
# strptime-Loop). Vor _ISO_ORDINAL_DATE (7 Ziffern) einsortiert waere
# unschaedlich (kollisionsfreie Reihenfolge: 6 vs 7 Ziffern), wird aber
# konsistent mit der etablierten Praxis der uebrigen Compact-Patterns direkt
# nach _ISO_ORDINAL_DATE einsortiert (aufsteigende Ziffern-Zahl-Konvention:
# _YEAR_ONLY 4 -> _COMPACT_YEAR_MONTH 6 -> _ISO_ORDINAL_DATE 7 -> %Y%m%d 8).
# Konvention identisch zu _YEAR_MONTH und _MONTH_NUMERIC_YEAR: Tag auf den 1.
# des Monats gesetzt (Monatsstart), Jahr im Bereich 1800..2999. Der 1800-
# Untergrenze-Check filtert False-Positives wie "179906" (Jahr 1799, ausserhalb
# der Kollektions-Domaene) und "170006" transparent auf None. Die 2999-
# Obergrenze filtert "300006" analog. Der Monats-Check 1..12 filtert
# "202400" (Monat 0), "202413" (Monat 13) und "202499" (Monat 99) auf None.
_COMPACT_YEAR_MONTH = re.compile(
    r"^\s*(\d{4})(\d{2})\s*$"
)

# DE-Kompakt-Datum mit zweistelligem Jahr: "13.06.24", "1.6.24", "13/06/24",
# "13-06-24". Verbreitet in handschriftlichen Sammler-Notizen, aus Kassen-/
# Auktions-Beleg-Scans, aus alten Excel-Tabellen mit Default-2-Ziffer-Jahr-
# Anzeige und aus DE-/CH-typischen Beschriftungs-Etiketten, wo die verkuerzte
# Notation Platz spart. Bisher fiel jede Form still auf None, weil die
# :data:`_DATE_FORMATS`-strptime-Kette nur 4-Ziffer-Jahre kennt (``%Y``) und
# ``%y`` bewusst nicht enthalten war (Python-strptime nutzt einen fixen
# POSIX-Pivot bei 68/69, der fuer eine Mineral-Sammlung ungeeignet ist:
# ``13.06.68`` wuerde als 2068 gelesen - 42 Jahre in der Zukunft, sicher
# nicht der Sammler-Intent). Aus dem typischen Migrations-Workflow "alte
# Excel-Datei mit DD.MM.YY-Spalte importieren" oder "Kassen-Beleg vom
# Mineral-Boersen-Kauf abschreiben" entstand damit silenter Funddatum-
# Datenverlust auf der zweistelligen Kurzform.
#
# Der Fix legt eine spezifische Regex-Vorpruefung VOR dem strptime-Loop,
# die die drei DE-Separatoren (``.`` / ``/`` / ``-``) mit obligatorischer
# Separator-Symmetrie via Back-Reference ``\2`` abdeckt (verhindert Mix-
# Formen wie ``13.06/24``, die semantisch inkonsistent sind) und das
# zweistellige Jahr mit einem sammler-typischen Pivot 30 aufloest:
# ``YY <= 30`` -> ``20YY`` (00-30 auf 2000-2030), ``YY >= 31`` -> ``19YY``
# (31-99 auf 1931-1999). Der Pivot 30 gibt einige Jahre Puffer fuer geplante
# Foto-Sessions und Ausstellungs-Termine bis 2030, mappt aber alle
# aelteren Sammler-Notizen mit YY >= 31 korrekt in das 20. Jhdt.
# (Boersen-Kaeufe der 80er/90er, geerbte Museums-Etiketten der 30er-70er).
# Kollisionsfrei zu :data:`_YEAR_ONLY` (vier Ziffern) und zu den strptime-
# Formaten mit ``%Y`` (auch vier Ziffern) - die 2-Ziffer-Form wird nur
# durch diese dedizierte Regex behandelt und faellt nicht in den strptime-
# Loop durch. Tag/Monat-Validierung ueber :class:`datetime.date`-
# Konstruktor (Feb 30 -> ValueError -> None). Kein Match bei Whitespace
# innerhalb der Zahl-Trenner (``13. 06. 24`` matcht nicht, weil ``\2``
# den identischen Separator ohne Whitespace verlangt) und keine
# US-Interpretation (MM.DD.YY, MM/DD/YY, MM-DD-YY werden weiter nicht
# unterstuetzt - die DE-Konvention ist im Schweizer Sammlungs-Kontext
# dominant, US-Kompakt-Formen ohne Trenner-Symmetrie waeren mehrdeutig).
_DAY_MONTH_2Y = re.compile(
    r"^\s*(\d{1,2})([./-])(\d{1,2})\2(\d{2})\s*$"
)

# ISO 8601 Wochendatum: "2024-W25", "2024W25" (compact), "2024-W25-3" (mit Tag).
# Konvention: ohne expliziten Wochentag → Montag der Woche (ISO-Wochenstart).
# Verbreitet in Log-/Build-Stempeln und manchen Sammlungs-Notizen ("KW25 2024").
# Zwei Schreibweisen werden akzeptiert: ISO-Standard (Bindestrich) und compact
# (ohne Bindestrich); Wochentag optional, immer 1-7 (Mo-So per ISO-Definition).
_ISO_WEEK_DATE = re.compile(
    r"^\s*(\d{4})-?W(\d{1,2})(?:-?([1-7]))?\s*$",
    re.IGNORECASE,
)
# Deutsche KW-Notation: "KW 25 2024", "KW25/2024", "KW 25, 2024",
# "Kalenderwoche 25 2024", "Woche 25 2024", plus englische Aequivalente
# "CW 25 2024" ("calendar week"). Verbreitet in Sammlungs-Tagebuechern
# (Wochenangaben statt Tagen) und in Geschaeftsperioden-Reports (die
# Wochen-Achse als sortierender Zeit-Anker fuer Tucson-/Mineralien-Boersen-
# Reisen, Foto-Sessions und Exkursions-Planung). Mapping identisch zu
# :data:`_ISO_WEEK_DATE` (Montag der genannten Woche). Die drei Kurzformen
# ``KW`` (DE), ``CW`` (EN, "calendar week") und die Langformen
# ``Kalenderwoche`` (DE) / ``Woche`` (DE-Kurzform ohne Kalender-Praefix)
# / ``calendar week`` (EN, mit optionalem Whitespace) decken alle
# praxisrelevanten Schreibweisen ab. Optionaler ``.``/``,``-Trenner nach
# der Kurzform (z.B. ``KW. 25 2024`` bei Punkt-Abkuerzungs-Konvention)
# durch die Alternante ``\.?`` toleriert. Kollisionsfrei zu
# :data:`_SEASON_YEAR` (kein Saison-Wort im _SEASON_MONTHS-Dict endet auf
# ``KW``/``CW``/``woche``/``week``) und zu :data:`_YEAR_MONTH_NAME`
# (keine Monatsname-Alternante enthaelt ``KW``/``CW``/``Kalenderwoche``/
# ``Woche``/``calendar``). Die Whitespace-erlaubende Form
# ``calendar\s*week`` deckt sowohl ``calendarweek 25 2024`` (compact) als
# auch ``calendar week 25 2024`` (Whitespace-getrennt) ab.
#
# Einzelbuchstabe-Kurzform ``W`` als letzte Alternante: ISO 8601 setzt ``W``
# als Wochen-Marker (``2024-W25`` / ``2024W25``); die Year-Last-Reihenfolge
# ``W25 2024`` (Wochen-Zahl vor Jahr) und die Space-getrennte Year-First-
# Form ``2024 W25`` sind in Log-Stempeln, Kalender-Exporten und
# internationalen Sammler-Notizen die de-facto Kompakt-Schreibweisen ohne
# volles Kalenderwoche-Wort. Bisher fielen alle Formen mit reinem
# W-Marker (statt KW/CW/Kalenderwoche/Woche/calendar week) still auf
# None, obwohl die ISO-Compact-Form ``2024W25`` (kein Whitespace zwischen
# Jahr und W) transparent das Datum lieferte - jede Notation mit
# Whitespace-Trenner (``W25 2024`` week-first, ``2024 W25`` year-first mit
# Space) oder mit Nicht-ISO-Separator (``W25/2024``, ``W25.2024``)
# konnte nicht gelesen werden, obwohl die Wochen-Semantik eindeutig
# ist. Die W-Alternante ist bewusst am Ende der Alternativen platziert,
# damit die laengeren Marker (``KW``, ``CW``, ``Kalenderwoche``, ``Woche``,
# ``calendar week``) zuerst versucht werden - regex-alternative-Ordering
# ist links-nach-rechts, und ``W`` als Praefix von ``Woche``/``week``
# haette die laengeren Formen sonst blockiert. Der obligatorische
# 4-Ziffer-Jahr-Anker und der obligatorische Wochen-Zahl-Anker mit
# Separator schuetzen vor False-Positives an Standalone-W-Tokens
# (``W25`` allein, ``W3.5`` Messwert, ``W-4`` Sortier-Code) - alle
# fallen mangels vollstaendiger Struktur unangetastet auf None.
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Wochen-Zahl und Jahr
# deckt die natuerlichsprachige DE-/EN-Form ``KW 25 von 2024`` /
# ``Kalenderwoche 25 von 2024`` / ``week 25 of 2024`` / ``CW 25 of 2024`` ab,
# die in Prosa-Etiketten und Sammler-Notizen die uebliche Verbindungs-Form
# zwischen Wochen-Nummer und Jahr ist ("Fund KW 25 von 2024 im Aaregebiet",
# "Bergtour week 40 of 2019 Tucson-Boerse"). Spiegelt die "of"-Praepositions-
# Erweiterung aus :data:`_DAY_OF_MONTH_YEAR` (englische Ordinal-Konstruktion
# "the 4th of July 2019") auf die Wochen-Achse und ergaenzt symmetrisch die
# DE-Preposition ``von``. Beide Praepositionen verlangen Whitespace auf
# beiden Seiten (``\s+...\s+``), sodass Kompositum-Formen wie ``vondel`` /
# ``vonof`` / ``von2024`` (ohne Trennwhitespace) still fehl-matchen und
# ``KW 25`` allein (ohne Jahr) unveraendert None liefert. Bisher fielen
# alle Praepositions-Formen still auf None, weil die Separator-Klasse
# ``[/.\-, ]`` nur Ein-Zeichen-Trenner kennt und die Wort-Praeposition
# nicht abdeckt - typische Prosa-Notizen aus Fund-Tagebuechern gingen als
# silenter Funddatum-Datenverlust in die Migration. Case-Insensitivitaet
# spiegelt die uebrigen Marker-Alternativen (KW/kw, Kalenderwoche/
# kalenderwoche); ``VON``/``OF`` in Grossbuchstaben aus Excel-Auto-Fill /
# Uppercase-Titeln matchen ohne Regel-Doppel-Pflege.
_KW_YEAR = re.compile(
    r"^\s*(?:KW|CW|Kalenderwoche|Woche|calendar\s*week|W)\.?\s*(\d{1,2})"
    r"(?:\s*[/.\-, _]\s*|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)
# Year-first KW-Notation: "2024 KW 25", "2024/KW25", "2024-Kalenderwoche 25",
# "2024, CW 25". Spiegelt :data:`_KW_YEAR` auf die Year-First-Reihenfolge -
# analog zu :data:`_QUARTER_YEAR_FIRST` / :data:`_HALFYEAR_YEAR_FIRST` /
# :data:`_SEASON_YEAR_FIRST` gegenueber ihren Year-Last-Basisformen. In
# Sammlungs-Tagebuechern, die das Jahr als sortierenden Praefix voranstellen
# ("2024 KW 25 - Tucson-Boerse", "Aktivitaeten 2024 CW 40 Bergtour Gotthard"),
# ist die Jahr-zuerst-Reihenfolge die uebliche Excel-/Ordner-Struktur-Konvention.
# Bisher fielen alle Year-First-Formen still auf None, obwohl die identische
# Year-Last-Form (":data:`_KW_YEAR`") transparent das Datum lieferte. Mapping
# identisch zu :data:`_ISO_WEEK_DATE` und :data:`_KW_YEAR` (Montag der
# genannten Woche). Separator [/.\-, ] zwischen Jahr und KW-Marker spiegelt die
# Year-First-Konvention der uebrigen Patterns (_QUARTER_YEAR_FIRST etc.).
# Einzelbuchstabe-Kurzform ``W`` als letzte Alternante spiegelt die
# entsprechende Erweiterung in :data:`_KW_YEAR`; deckt ``2024 W25`` /
# ``2024/W25`` / ``2024-W 25`` ab, die die Whitespace-Space-Form der
# ISO-Compact-Konvention ``2024W25`` sind (letztere per _ISO_WEEK_DATE
# bereits erfasst, aber ohne Whitespace-Trenner).
_KW_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, _]\s*"
    r"(?:KW|CW|Kalenderwoche|Woche|calendar\s*week|W)\.?\s*(\d{1,2})\s*$",
    re.IGNORECASE,
)

# Relative Jahresposition + Jahr ("Anfang 2024", "Mitte 1985", "Ende 1999",
# "early 2024", "mid 2024", "late 2024", "mid-2024"). Konvention analog Saison:
# Anfang/early → Januar (01), Mitte/mid → Juli (07), Ende/late → Dezember (12).
# Separator zwischen Schluesselwort und Jahr: Whitespace oder Bindestrich (englisch
# "mid-2024" ist verbreitet). Wird vor _SEASON_YEAR geprueft, damit die
# Schluesselwoerter nicht als unbekannter Saison-Name auf None fallen.
_RELATIVE_MONTHS: dict[str, int] = {
    "anfang": 1, "early": 1,
    "mitte": 7, "mid": 7,
    "ende": 12, "late": 12,
}
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Positions-Wort und
# Jahr deckt die natuerlichsprachige DE-/EN-Prosa-Form ``Anfang von 2024`` /
# ``Mitte von 1985`` / ``Ende von 1999`` / ``early of 2024`` ab, die in
# Sammler-Fund-Tagebuechern und Prosa-Etiketten die uebliche Verbindungs-
# Form zwischen Positions-Wort und Jahr ist ("Fund Anfang von 2024 im
# Aaregebiet", "Bergtour Mitte von 2020 Zermatt", "Erwerb Ende von 2019
# Tucson-Boerse"). Semantisch idiomatisch fuer DE ("Anfang von 2024" ist
# umgangssprachlich = "am Anfang des Jahres 2024"); die EN-``of``-Alternante
# wird zur DE-Symmetrie mit unterstuetzt (spiegelt die uebrigen Praepositions-
# Achsen aus :data:`_KW_YEAR`/`_MONTH_YEAR`/`_QUARTER_SHORT`/`_HALFYEAR_SHORT`).
# Beide Praepositionen verlangen Whitespace auf beiden Seiten, sodass
# Kompositum-Formen (``vondel``, ``vonof``) und angehaengte Formen (``Anfang
# von2024``) mangels vollstaendiger Struktur unangetastet auf None fallen.
# Kollisionsfrei zu :data:`_YEAR_COMPOUND_POSITION` (die ``Jahres``-Kompositum-
# Form hat das ``Jahres``-Praefix als obligatorisches Anker-Woertchen, ohne
# das die Kette hier greift). Bisher fielen alle Praepositions-Formen still
# auf None, weil die Trenner-Klasse ``[-\s]+`` nur Ein-Zeichen-Trenner kennt.
_RELATIVE_YEAR = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)"
    r"(?:[-\s]+|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)

# Deutsche Kompositum-Formen der Jahresposition ("Jahresanfang 2024",
# "Jahresbeginn 2024", "Jahresmitte 2024", "Jahresende 2024", "Jahresschluss
# 2024", "Jahresausklang 2024"). In DE-Sammler-Notizen und Prosa-Etiketten die
# haeufigere Wort-Form neben der artikellosen "Anfang 2024"/"Mitte 2024"/
# "Ende 2024"-Kurzform (letzteres ist journalistisch/Print, das Kompositum ist
# umgangssprachlich und wird in geerbten Fund-Tagebuechern der Sammler-Praxis
# durchgehend verwendet: "Aare-Herbstsammlung Jahresende 1985", "Erwerb
# Jahresanfang 2020", "Kauf Jahresmitte 2019 an der Tucson-Boerse"). Spiegelt
# das :data:`_RELATIVE_MONTHS`-Schema auf die substantivierte Kompositum-Achse:
#   Jahresanfang/Jahresbeginn/Jahresstart -> 1 (Januar, Jahres-Startanker)
#   Jahresmitte                            -> 7 (Juli, Jahres-Mitte)
#   Jahresende/Jahresschluss/Jahresausklang -> 12 (Dezember, Jahres-Endanker)
# Semantisch identisch zur artikellosen Kurzform (``Anfang 2024`` == ``Jahres-
# anfang 2024``, beide meinen den Jahres-Startanker). Bisher fielen alle
# Kompositum-Formen still auf None, weil :data:`_MONTH_YEAR` strukturell zwar
# matcht (ein Wort + Jahr), aber :func:`_normalize_month_name` fuer
# ``jahresanfang``/``jahresmitte``/``jahresende`` None liefert und die Kette
# durchfaellt - der Sammler-Freitext ging silent verloren, obwohl semantisch
# eindeutig zur Kurzform aequivalent.
#
# Separator zwischen Kompositum und Jahr: Whitespace oder Bindestrich, spiegelt
# die :data:`_RELATIVE_YEAR`-Trenner-Klasse ``[-\s]+`` (``Jahresende-2024``
# als hyphenierte Kompositum-Form ist typografisch selten aber spec-konform).
# Case-insensitive spiegelt die uebrigen Position-Patterns. Kollisionsfreiheit
# zu :data:`_RELATIVE_YEAR`: das ``Jahres``-Praefix ist obligatorisch, das
# Positions-Suffix (``anfang``/``beginn``/...) allein reicht nicht (``Anfang
# 2024`` faellt hier durch und wird von _RELATIVE_YEAR aufgeloest). Wird nach
# _RELATIVE_YEAR geprueft (die artikellose Kurzform hat als bereits etabliertes
# Pattern Vorrang), aber vor _SEASON_YEAR - sonst wuerde die kanonische Saison-
# Aufloesung greifen wollen und via unbekannten Saison-Namen auf None fallen.
_YEAR_COMPOUND_POSITION_MONTHS: dict[str, int] = {
    "anfang": 1, "beginn": 1, "start": 1,
    "mitte": 7,
    "ende": 12, "schluss": 12, "ausklang": 12,
}
# Praepositions-Alternante ``\s+(?:von|of)\s+`` zwischen Kompositum und Jahr
# deckt die natuerlichsprachige DE-Prosa-Form ``Jahresanfang von 2024`` /
# ``Jahresmitte von 1985`` / ``Jahresende von 1999`` / ``Jahresschluss of
# 2019`` ab - die in DE-Sammler-Notizen und Prosa-Etiketten uebliche und stark
# idiomatische Verbindungs-Form ("Fund Jahresanfang von 2020 im Aaregebiet",
# "Erwerb Jahresende von 1985 an der Tucson-Boerse", "Kauf Jahresmitte von
# 2019 Zermatt-Bergtour"). Spiegelt die Praepositions-Erweiterung aus
# :data:`_RELATIVE_YEAR` (artikellose Kurzform ``Anfang von 2024``) auf die
# substantivierte Kompositum-Achse; identische semantische Rolle und
# identisches Mapping (``Jahresanfang von 2024`` == ``Anfang von 2024``,
# beide meinen den Jahres-Startanker Januar). Beide Praepositionen verlangen
# Whitespace auf beiden Seiten, sodass Kompositum- und angehaengte Formen
# unangetastet auf None fallen. Bisher fielen alle Praepositions-Formen still
# auf None, weil die Trenner-Klasse ``[-\s]+`` nur Ein-Zeichen-Trenner kennt.
_YEAR_COMPOUND_POSITION = re.compile(
    r"^\s*Jahres(anfang|beginn|start|mitte|ende|schluss|ausklang)"
    r"(?:[-\s]+|\s+(?:von|of)\s+)(\d{4})\s*$",
    re.IGNORECASE,
)

# Relative Position innerhalb eines Monats mit Monatsname und Jahr:
# "Anfang Juni 2024", "Mitte Juni 2024", "Ende Juni 2024", "early June 2024",
# "mid-June 2024", "late June 2024". Sehr verbreitet in Sammler-Notizen und
# Fund-Etiketten, wenn der Sammler den Fund/das Foto zwar auf einen bestimmten
# Monat, aber innerhalb dieses Monats nicht auf ein Einzeldatum eingrenzen kann
# ("Fund Anfang Juni 2024 am Aaregebiet", "Bergtour Mitte August 2020",
# "Erwerb Ende Dezember 2019", "found mid-March 1995"). Bisher fielen alle Formen
# still auf None, weil _DAY_MONTH_YEAR eine numerische Tag-Angabe verlangt
# (``\d{1,2}`` als erstes Feld) und _MONTH_YEAR ohne den Positions-Praefix
# ausschliesslich Monatsname + Jahr als 2-Teil-Form ($-verankert) kennt - aus
# einer typischen Notiz wie "Ende Juni 2024" wurde silenter Funddatum-Datenverlust
# bei der Migration, obwohl Monat und Jahr eindeutig lesbar sind.
#
# Konvention: Positions-Wort mappt auf einen Tag innerhalb des Monats -
#   Anfang/early -> 1 (Monatsanfang)
#   Mitte/mid    -> 15 (Monatsmitte)
#   Ende/late    -> letzter Tag des Monats (28-31, abhaengig von Monat + Schaltjahr)
# Spiegelt das _RELATIVE_YEAR-Schema (Anfang/Mitte/Ende auf 1/7/12 als Monatszahl
# innerhalb eines Jahres) auf die Tag-innerhalb-eines-Monats-Achse und ist konsistent
# zur EN/US-Sammler-Praxis, den entsprechenden Monatspol zu treffen (fruehester,
# mittlerer, spaetester Tag). Fuer "Ende" wird der Monats-Endtag korrekt berechnet
# (Februar-Schaltjahr-Behandlung ueber datetime.date-Arithmetik: erster Tag des
# Folgemonats minus einen Tag), sodass "Ende Februar 2024" -> 2024-02-29 (Schaltjahr)
# und "Ende Februar 2023" -> 2023-02-28 (Nicht-Schaltjahr) semantisch korrekt sind.
#
# Separator zwischen Positions-Wort und Monatsname: Whitespace oder Bindestrich
# (spiegelt _RELATIVE_YEAR / _RELATIVE_DECADE - englisches "mid-June" ist eine
# sehr verbreitete Compound-Notation, deutsches "Anfang-Juni" (mit Bindestrich)
# selten aber spec-konform durch die identische Trenner-Klasse ``[-\s]+``).
# Monatsname als ``([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?`` deckt beide Sprachen und die Kurz-
# form-Punkt-Notation ab (Juni/June/Jun./Jan., spiegelt _DAY_MONTH_YEAR und
# _MONTH_YEAR).
#
# Disjunktheit zu _RELATIVE_YEAR: die 3-Teil-Form (Position + Monat + Jahr)
# verlangt einen Monats-Buchstaben-Token zwischen Position und Jahr, waehrend
# _RELATIVE_YEAR direkt die Jahres-Ziffern nach der Position erwartet - keine
# Kollision. Disjunktheit zu _DAY_MONTH_YEAR (verlangt Ziffer als erstes Feld)
# und _ENGLISH_MONTH_DAY_YEAR (verlangt Monatsname, dann Ziffer + Jahr):
# "Anfang Juni 2024" scheitert bei beiden strukturell. Disjunktheit zu
# _MONTH_YEAR (2-Teil-Form Monatsname + Jahr): der Positions-Praefix
# "Anfang"/"Mitte"/"Ende" wird zwar als [A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+-Token erkannt, aber
# _normalize_month_name liefert dann None, sodass der Match transparent
# durchfaellt.
_RELATIVE_MONTH_YEAR = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)"
    r"[-\s]+([A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ]+)\.?"
    r"\s+(\d{4})\s*$",
    re.IGNORECASE,
)

# Relative Position innerhalb einer Dekade ("Anfang 1980er", "Mitte 1980er",
# "Ende 1990s", "early 1980s", "mid-1990s", "late 2000s"). Spiegelt
# _RELATIVE_YEAR (relative Position innerhalb eines Jahres) auf die Dekaden-
# Achse - in geerbten Sammlungs-Notizen sehr verbreitet ("Funde aus den
# fruehen 80ern", "mid-1990s collection"), weil Sammler den Fundzeitpunkt
# oft nicht exakt jahrweise wissen, aber die Dekaden-Phase grob erinnern.
# Bisher fielen beide Sprach-Varianten und alle drei Positionen stille auf
# None, obwohl semantisch eindeutig in die Dekade verortbar.
#
# Konvention: Offset innerhalb der Dekade (0-9):
#   Anfang/early → 0  (Dekaden-Startjahr, z.B. 1980)
#   Mitte/mid    → 5  (Dekaden-Mitte, z.B. 1985)
#   Ende/late    → 9  (Dekaden-Endjahr, z.B. 1989)
# Spiegelt das _RELATIVE_MONTHS-Schema (Anfang=1/Mitte=7/Ende=12 als Mona-
# tszahlen) auf die 10er-Skala. "Ende 1980er" liefert 1989-01-01 (letztes
# Jahr der Dekade), "Mitte 1980er" liefert 1985-01-01 (5. Jahr der Dekade),
# "Anfang 1980er" liefert 1980-01-01 (deckungsgleich mit _DECADE "1980er",
# der ebenfalls den Dekaden-Start liefert - "early" und der reine
# Dekaden-Marker meinen praktisch dasselbe).
#
# Pattern verlangt vierstellige Dekaden-Anker (wie _DECADE) und akzeptiert
# beide Dekaden-Suffix-Varianten ("er" DE-Konvention, "s" EN-Konvention)
# samt optionalem "Jahre"-Trailer. Separator zwischen Schluesselwort und
# Decade-Anker: Whitespace oder Bindestrich (EN "mid-1990s" ist sehr
# verbreitet, DE "Anfang-1980er" eher selten aber spec-konform). Wird
# disjunkt zu _RELATIVE_YEAR gefuehrt (das Pattern verlangt das er/s-Suffix,
# _RELATIVE_YEAR verbietet es implizit durch $) und disjunkt zu _DECADE
# (das ohne Schluesselwort-Praefix matched).
_RELATIVE_DECADE_OFFSETS: dict[str, int] = {
    "anfang": 0, "early": 0,
    "mitte": 5, "mid": 5,
    "ende": 9, "late": 9,
}
# DE-Adjektiv-Praefix-Formen ("frueh(e|en|er|em|es)" / "spaet(e|en|er|em|es)"
# samt Umlaut-Varianten "frueh"/"spaet" und "früh"/"spät") auf die Dekaden-
# Offsets von "Anfang" (0) und "Ende" (9) mappen. Sehr verbreitet in DE-
# Sammler-/Museums-Notizen, weil "frueh(e|n) 1980er" bzw. "spaete(n) 1990er"
# die grammatikalisch flektierten Adjektiv-Formen des Positionsworts sind
# (weak/strong declension: "die fruehen 1980er Jahre" mit Artikel = weak
# Plural-Endung -en; "fruehe 1980er Jahre" ohne Artikel = strong Plural-
# Endung -e; die volle Kasus-Palette -e/-en/-er/-em/-es deckt Nom./Gen./
# Dat./Akk. inkl. Genitiv-Kombinationen wie "der fruehen 1980er Jahre"
# ab). Semantisch identisch zur bereits erfassten "Anfang/Mitte/Ende
# 1980er"-Form und zur EN-"early/mid/late 1980s"-Achse - vor der Erweiterung
# fielen die DE-Adjektiv-Formen still auf None, obwohl EN-Aequivalent und
# DE-Substantiv-Aequivalent aufgeloest wurden. Aus geerbten Sammlungs-
# Beschreibungen ("Fund aus den fruehen 1980er Jahren", "Nachlass aus
# spaeten 1990ern") entstand damit silenter Funddatum-Datenverlust.
# Umlaut- und ASCII-transliterierte Formen (früh/frueh, spät/spaet) sind
# beide praxisrelevant: Windows-CP1252/Excel-DE speichert Umlaute nativ,
# aeltere ASCII-only-Notizen und Import aus Terminal-Tools mit 7-bit-
# Codepage transliterieren zu ue/ae.
_RELATIVE_DECADE_ADJECTIVE_OFFSETS: tuple[tuple[str, int], ...] = (
    ("früh", 0), ("frueh", 0),
    ("spät", 9), ("spaet", 9),
)
# ``(?:der\s+)?`` deckt die DE-Genitiv-Artikel-Fueller-Form ab, die in
# ganzen Saetzen der Standard ist: ``Anfang der 1980er (Jahre)``, ``Ende der
# 1990er Jahren``, ``Mitte der 2000er``. Ohne den Artikel-Zweig fielen diese
# extrem verbreiteten Print-/Buch-Formen still auf None (Regex verlangte den
# Sprung direkt vom Positions-Wort auf den Dekaden-Anker: ``Anfang 1980er``),
# obwohl semantisch identisch zur artikellosen Form (Konvention: Anfang→Jahr
# 0 der Dekade, Mitte→Jahr 5, Ende→Jahr 9). Der Artikel-Zweig ist bewusst
# nur fuer die DE-Keywords semantisch gemeint (``der`` ist DE-Genitiv-Femininum
# Plural fuer ``die 1980er Jahre`` in der Genitiv-Rektion von ``Anfang/Mitte/
# Ende``), matcht via case-insensitive Regex zwar auch nach EN-Keywords
# (``early der 1980s``), das ist aber ein nicht-idiomatischer Fall, der in
# der Praxis nicht auftritt und - selbst wenn - semantisch identisch zur
# artikellosen Form auf den Dekaden-Anker abbildet (kein Datenverlust).
# ``jahre(?:n)?`` deckt zusaetzlich die Dativ-Plural-Form ``Jahren`` ab,
# spiegelt _DECADE auf die relative Positions-Achse (``Anfang der 1980er
# Jahren`` ist selten, aber ``Ende der 1990er Jahren`` als Fund-Kontext-
# Anmerkung kommt vor).
#
# ``(?:(?:die|der|den|dem|das)\s+)?`` als optionaler Leading-Artikel deckt
# die Nominativ-/Akkusativ-/Genitiv-/Dativ-Konstruktionen mit vor der Position
# stehendem definitem Artikel ab: ``die fruehen 1980er``, ``der fruehen
# 1980er Jahre``, ``den fruehen 1980ern``. Ohne diese Praefix-Klausel fielen
# die Formen still auf None, obwohl der Rest-String semantisch identisch zur
# artikellosen ``fruehe 1980er``-Form ist. Der ``_TEMPORAL_PREFIX`` strippt
# ``in/im/vom/von/am/on + optional Artikel`` schon vor diesem Pattern - der
# hier hinzugefuegte Artikel-Zweig deckt den Fall ab, dass der Artikel *ohne*
# Praeposition am Anfang steht (Nominativ als Satz-Subjekt: ``Die fruehen
# 1980er waren...``, oder direkt aus einer Tabellen-Zeile: ``die fruehen
# 1980er``).
#
# Die zwei DE-Adjektiv-Alternanten ``fr(?:üh|ueh)(?:e|em|en|er|es)`` und
# ``sp(?:ät|aet)(?:e|em|en|er|es)`` verlangen zwingend eine Adjektiv-Endung
# (mindestens einen Buchstaben aus e/em/en/er/es), damit die reine Root-Form
# ``frueh 1980er`` (grammatikalisch inkorrekt, Sammler-Praxis ohne Adjektiv-
# Deklination) nicht matcht und die Praezisions-Semantik erhalten bleibt.
# Die Endungs-Menge deckt die Standard-DE-Adjektiv-Deklinationsklassen ab
# (schwache Deklination mit Artikel: -en; starke Deklination ohne Artikel:
# -e/-es/-em/-er). Umlaut- und ASCII-transliterierte Formen (frueh/früh,
# spaet/spät) sind beide praxisrelevant und werden ueber die (?:üh|ueh)/
# (?:ät|aet)-Alternanten symmetrisch akzeptiert.
_RELATIVE_DECADE = re.compile(
    r"^\s*(?:(?:die|der|den|dem|das)\s+)?"
    r"(Anfang|Mitte|Ende|early|mid|late"
    r"|fr(?:üh|ueh)(?:e|em|en|er|es)"
    r"|sp(?:ät|aet)(?:e|em|en|er|es))"
    r"[-\s]+(?:der\s+)?(\d{4})(?:[\- ]?(?:ern|er|s))"
    # Trenner zwischen Dekaden-Suffix und optionalem ``jahre(?:n)?``-Trailer
    # als ``[-\s]+`` (analog zu _DECADE), damit die hyphenierte Kompositum-
    # Form ``Anfang der 1980er-Jahre`` / ``mid-1990er-Jahren`` / ``spaete
    # 2000er-Jahre`` erkannt wird (Duden-alternative Zusammenschreibung, in
    # DE-Publikationen sehr verbreitet). Ohne den Bindestrich-Zweig fielen
    # alle Relativ-Positions-Formen mit hyphenierten Trailer still auf
    # None, obwohl semantisch identisch zur getrennten Schreibweise.
    r"(?:[-\s]+jahren?)?\s*$",
    re.IGNORECASE,
)


def _relative_decade_offset(raw: str) -> int | None:
    """Ordnet ein Positions-Keyword (inkl. DE-Adjektiv-Endung) einem Dekaden-Offset zu.

    Nutzt die Basis-Map :data:`_RELATIVE_DECADE_OFFSETS` fuer die kanonischen
    Substantiv-Formen (``anfang``, ``mitte``, ``ende``, ``early``, ``mid``,
    ``late``) und die Praefix-Map :data:`_RELATIVE_DECADE_ADJECTIVE_OFFSETS`
    fuer die DE-Adjektiv-Deklinationen (``frueh(e|en|er|em|es)``,
    ``spaet(e|en|er|em|es)`` samt Umlaut-Varianten ``früh``/``spät``). Bei
    einem Match auf eine Adjektiv-Wurzel wird der zugeordnete Offset
    zurueckgegeben, unabhaengig von der konkreten Kasus-Endung.
    """
    key = raw.lower()
    if key in _RELATIVE_DECADE_OFFSETS:
        return _RELATIVE_DECADE_OFFSETS[key]
    for prefix, offset in _RELATIVE_DECADE_ADJECTIVE_OFFSETS:
        if key.startswith(prefix):
            return offset
    return None

# Jahrhundert-Notation (DE/EN) - in geerbten Sammlungs-Notizen die uebliche
# Grobdatierung fuer Museums-Eingaenge und Provenienz-Vermerke ("Fund aus dem
# 19. Jahrhundert", "acquired in the 20th century"). Bisher fielen alle Formen
# stille auf None, obwohl semantisch eindeutig in ein Jahrhundert-Startjahr
# verortbar - aus einem typischen Etikett wie "19. Jahrhundert" wurde silenter
# Funddatum-Datenverlust. Konvention: umgangssprachliche Ausrichtung, bei der
# das Label auf die "18xx"-Jahre zeigt (19. Jahrhundert = 1800er Jahre), analog
# zur Dekaden-Konvention (1980er → 1980-01-01 = Dekaden-Startjahr). Das ergibt
# fuer century N das Startjahr (N-1) * 100. Die pedantische Konvention
# (19. Jhdt. = 1801-1900) wird hier bewusst nicht gewaehlt, weil sie im
# Sammler-Sprachgebrauch mit dem Label ("18xx") nicht zusammenpasst.
# DE-Sammler-Vokabular: "Jahrhundert" (Vollform), "Jahrh", "Jahrhdt", "Jhrdt",
# "Jhdt", "Jhrd", "Jhd", "Jh"; alle mit optionalem Trailing-Punkt. Ordinaler
# Punkt nach der Jahrhundert-Zahl ("19.") ist im Deutschen ueblich, aber auch
# die punktlose Form ("19 Jahrhundert") kommt in Notizen vor. Die Kurzform
# "Jhd." (ohne trailing t) und "Jahrh." (nur Wortstamm bis zum ersten h) sind
# als Duden-konforme Abkuerzungen von "Jahrhundert" verbreitet in aelteren
# Museums-Etiketten und Provenienz-Vermerken.
_CENTURY_DE = re.compile(
    r"^\s*(\d{1,2})\s*\.?\s*(?:jahrhundert|jahrhdt|jahrh|jhrdt|jhdt|jhrd|jhd|jh)\.?\s*$",
    re.IGNORECASE,
)
# EN: "19th century", "20 century", "19th c." - die Kurzform "c." ist im
# Englischen der uebliche Century-Abbreviation aus Museums-Katalogen und
# Auktions-Beschreibungen. Ordinalsuffix (st/nd/rd/th) ist optional
# (Museums-Etiketten schreiben teils die reine Zahl "19 century").
_CENTURY_EN = re.compile(
    r"^\s*(\d{1,2})(?:st|nd|rd|th)?\s+(?:century|cent\.?|c\.)\s*$",
    re.IGNORECASE,
)
# Roemische Zahlen fuer Jahrhundert-Notation (I..XXX = 1..30). Die traditionelle
# Schreibweise auf alten Museums-Etiketten, Antiquariats-Katalogen, Provenienz-
# Vermerken der Museums-Eingangsbuecher und akademischen/historischen/geologi-
# schen Referenzen: "XIX. Jahrhundert" = 19. Jahrhundert = 1800er, "XX. Jhdt."
# = 20. Jhdt. = 1900er, "XXI. Jhdt." = 21. Jhdt. = 2000er. Besonders verbreitet
# in geerbten Sammlungen mit italienischer/osteuropaeischer/franzoesischer Pro-
# venienz und in aelteren deutschen Notizen aus der ersten Haelfte des 20. Jhdt.,
# wo die Roemisch-Notation im wissenschaftlichen Diskurs noch die Regel war.
# Bisher fielen alle diese Formen stille auf None (die _CENTURY_DE/_EN-Patterns
# akzeptieren nur ``\d{1,2}``), obwohl semantisch eindeutig - aus typischen
# Museums-Etiketten mit Roemisch-Notation wurde silenter Funddatum-Datenverlust
# bei der Migration.
#
# Spiegelt die bereits vorhandene Roemisch-Unterstuetzung fuer Monate (I..XII
# in :data:`_MONTH_NAMES`) auf die Jahrhundert-Achse. Range I..XXX deckt Jahre
# 100..3000 ab, was das gueltige 1800..2999-Band (Jahrhundert 19..30) mit
# reichlich Puffer einschliesst - kleinere Werte (XVIII. Jhdt. = 1700..1799)
# werden vom Pattern matched und dann durch die Jahres-Range-Pruefung
# zurueckgewiesen (spiegelt die Arabisch-Notation "18. Jahrhundert" -> None,
# konsistent mit der bestehenden Ungueltig-Semantik).
_ROMAN_CENTURY_VALUES: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
    "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13,
    "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19,
    "XX": 20, "XXI": 21, "XXII": 22, "XXIII": 23, "XXIV": 24, "XXV": 25,
    "XXVI": 26, "XXVII": 27, "XXVIII": 28, "XXIX": 29, "XXX": 30,
}
# DE-Vollform ("XIX. Jahrhundert") und alle bereits fuer _CENTURY_DE gelisteten
# Kurzformen (Jhdt./Jhrdt./Jh. etc.). Die Roemisch-Zeichen-Klasse ``[IVXLCM]``
# ist bewusst permissiv (deckt auch nicht-kanonische Kombinationen wie ``IIII``
# oder ``VXV`` ab): die Validierung erfolgt via :data:`_ROMAN_CENTURY_VALUES`-
# Lookup, sodass nicht-kanonische Tokens auf None fallen. Ordinaler Punkt nach
# der Roemisch-Zahl ("XIX.") ist im Deutschen ueblich (analog zu "19."), aber
# auch die punktlose Form ("XIX Jahrhundert") kommt in Notizen ohne strenge
# Grammatik vor. Kollisionsfrei zu _CENTURY_DE (\d{1,2} vs. [IVXLCM]+ sind
# disjunkt), kollisionsfrei zu den Monat-Patterns (die Roemisch-Monate leben
# in DAY_MONTH_YEAR/ENGLISH_MONTH_DAY_YEAR/MONTH_YEAR und verlangen dort
# Ziffer-Nachbarn, waehrend das Century-Pattern ``$``-anker mit "Jahrhundert"-
# Suffix verlangt).
_CENTURY_ROMAN_DE = re.compile(
    r"^\s*([IVXLCM]+)\s*\.?\s*(?:jahrhundert|jahrhdt|jahrh|jhrdt|jhdt|jhrd|jhd|jh)\.?\s*$",
    re.IGNORECASE,
)
# EN: "XIX century", "XIX. century", "XX c." - kein Ordinalsuffix (st/nd/rd/th)
# fuer Roemisch (die Ordinal-Suffixe gelten in EN nur fuer Arabisch: "19th",
# nicht "XIXth"). Optionaler trailing-Punkt nach der Roemisch-Zahl ("XIX.")
# deckt sowohl die DE-artige Etiketten-Praxis als auch die kompakte Form ab.
_CENTURY_ROMAN_EN = re.compile(
    r"^\s*([IVXLCM]+)\.?\s+(?:century|cent\.?|c\.)\s*$",
    re.IGNORECASE,
)

# Jahrhundert-Spanne ("19.-20. Jahrhundert", "19th to 20th century",
# "XIX.-XX. Jahrhundert") - spiegelt _YEAR_RANGE / _YEAR_RANGE_WORD /
# _DECADE_RANGE auf die Jahrhundert-Achse. In Museums-Etiketten und geerbten
# Sammlungs-Notizen sehr verbreitet, wenn der Vorbesitzer die Provenienz nur
# ungefaehr auf zwei aufeinanderfolgende Jahrhunderte einordnen konnte
# ("Erwerb aus dem 19.-20. Jahrhundert", "Sammlung aus dem XIX.-XX. Jhdt.").
# Bisher fielen alle Formen still auf None, weil _CENTURY_* eine einzelne
# Jahrhundert-Zahl verlangen (\$-Anker nach dem Wort-Suffix) - stiller Daten-
# verlust auf einer sehr typischen Provenienz-Datierungs-Notation, besonders
# bei generationsuebergreifenden Museums-Sammlungen mit vager Zeit-Achse.
#
# Konvention identisch zu _YEAR_RANGE / _YEAR_RANGE_WORD / _DECADE_RANGE /
# _CENTURY_*: Startjahr des linken Jahrhunderts als ISO-Datum
# ("19.-20. Jahrhundert" -> "1800-01-01"). Inverted Spanne ("20.-19. Jhdt.",
# Tippfehler) liefert das linke Jahrhundert (spiegelt _YEAR_RANGE-Konvention).
#
# Separator-Alternante vereinigt die Symbol-Klasse [-–—−/] (ASCII-Bindestrich,
# En-Dash U+2013, Em-Dash U+2014, Minus U+2212, Slash) und die Wort-Klasse
# (bis/to/till/until mit obligatorischem Whitespace) - spiegelt _YEAR_RANGE /
# _DECADE_RANGE. Der Wort-Zweig verlangt Whitespace, weil "19bis20" nie in
# natuerlicher Notation vorkommt.
#
# DE-Arabisch akzeptiert die volle _CENTURY_DE-Suffix-Menge (jahrhundert/
# jahrhdt/jahrh/jhrdt/jhdt/jhrd/jhd/jh) mit optionalem trailing Punkt sowie
# den optionalen Ordinal-Punkt nach jeder Jahrhundert-Zahl ("19.", "20.").
# EN-Arabisch spiegelt _CENTURY_EN mit optionalem Ordinalsuffix (st/nd/rd/th)
# an jeder Jahrhundert-Zahl und der EN-Suffix-Menge (century/cent./c.).
# DE-Roemisch spiegelt _CENTURY_ROMAN_DE mit der [IVXLCM]+ Zeichenklasse
# und Lookup ueber _ROMAN_CENTURY_VALUES. EN-Roemisch spiegelt
# _CENTURY_ROMAN_EN (keine Ordinal-Suffixe fuer Roemisch in EN).
#
# Vor _CENTURY_* geprueft, damit die Spanne-Form (die strukturell ein
# einzelnes Jahrhundert-Pattern enthaelt) nicht vom base _CENTURY_*-
# Pattern via \$-Anker geblockt wird. Kollisionsfrei zu _YEAR_RANGE (dort
# vier Ziffern, hier nur ein bis zwei Ziffern plus Wort-Suffix), zu
# _DECADE_RANGE (dort er/s-Suffix, hier Jahrhundert-Suffix), zu
# _RELATIVE_CENTURY_* (dort obligatorischer Anfang/Mitte/Ende-Praefix,
# hier keiner).
_CENTURY_RANGE_DE = re.compile(
    r"^\s*(\d{1,2})\s*\.?\s*"
    r"(?:\s*[-–—−/]\s*|\s+(?:bis|to|till|until)\s+)"
    r"(\d{1,2})\s*\.?\s*"
    r"(?:jahrhundert|jahrhdt|jahrh|jhrdt|jhdt|jhrd|jhd|jh)\.?\s*$",
    re.IGNORECASE,
)
_CENTURY_RANGE_EN = re.compile(
    r"^\s*(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*[-–—−/]\s*|\s+(?:bis|to|till|until)\s+)"
    r"(\d{1,2})(?:st|nd|rd|th)?"
    r"\s+(?:century|cent\.?|c\.)\s*$",
    re.IGNORECASE,
)
_CENTURY_RANGE_ROMAN_DE = re.compile(
    r"^\s*([IVXLCM]+)\s*\.?\s*"
    r"(?:\s*[-–—−/]\s*|\s+(?:bis|to|till|until)\s+)"
    r"([IVXLCM]+)\s*\.?\s*"
    r"(?:jahrhundert|jahrhdt|jahrh|jhrdt|jhdt|jhrd|jhd|jh)\.?\s*$",
    re.IGNORECASE,
)
_CENTURY_RANGE_ROMAN_EN = re.compile(
    r"^\s*([IVXLCM]+)\.?"
    r"(?:\s*[-–—−/]\s*|\s+(?:bis|to|till|until)\s+)"
    r"([IVXLCM]+)\.?"
    r"\s+(?:century|cent\.?|c\.)\s*$",
    re.IGNORECASE,
)

# Relative Position innerhalb eines Jahrhunderts ("Anfang 19. Jahrhundert",
# "Mitte 20. Jahrhundert", "Ende 19. Jhdt.", "early 19th century",
# "mid-19th century", "late 20th c."). Spiegelt _RELATIVE_DECADE (relative
# Position innerhalb einer Dekade) auf die Jahrhundert-Achse - in geerbten
# Sammlungs-Notizen sehr verbreitet fuer Museums-Provenienz-Vermerke ("Fund
# aus dem spaeten 19. Jahrhundert", "collected in the mid-20th century"),
# weil Vorbesitzer und Museums-Kuratoren die Erwerb-/Fund-Phase oft nur
# grob innerhalb eines Jahrhunderts einordnen konnten. Bisher fielen alle
# Sprach-Varianten und alle drei Positionen stille auf None, obwohl
# semantisch eindeutig in das Jahrhundert verortbar.
#
# Konvention: Offset innerhalb des Jahrhunderts (0-99):
#   Anfang/early → 0   (Jahrhundert-Startjahr, z.B. 1800)
#   Mitte/mid    → 50  (Jahrhundert-Mitte, z.B. 1850)
#   Ende/late    → 99  (Jahrhundert-Endjahr, z.B. 1899)
# Spiegelt das _RELATIVE_DECADE_OFFSETS-Schema (Anfang=0/Mitte=5/Ende=9)
# proportional auf die 100er-Skala. "Ende 19. Jahrhundert" liefert
# 1899-01-01 (letztes Jahr des Jahrhunderts), "Mitte 19. Jahrhundert"
# liefert 1850-01-01 (50. Jahr des Jahrhunderts), "Anfang 19. Jahrhundert"
# liefert 1800-01-01 (deckungsgleich mit _CENTURY "19. Jahrhundert").
#
# Pattern kombiniert die _RELATIVE_DECADE-Praefix-Struktur (dieselben sechs
# Schluesselwoerter, gleicher [-\s]+-Separator) mit der _CENTURY-Suffix-
# Struktur (DE-Wort-Suffix vs. EN-Ordinal-mit-Wort-Suffix). Zwei getrennte
# Regexe fuer DE/EN, weil das EN-Ordinalsuffix (st/nd/rd/th) in der DE-Form
# nicht vorkommt und die DE-Form eine reichere Kurzform-Menge (Jhdt./Jhrdt./
# Jh.) mitbringt.
_RELATIVE_CENTURY_OFFSETS: dict[str, int] = {
    "anfang": 0, "early": 0,
    "mitte": 50, "mid": 50,
    "ende": 99, "late": 99,
}
_RELATIVE_CENTURY_DE = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)[-\s]+"
    r"(\d{1,2})\s*\.?\s*(?:jahrhundert|jahrhdt|jahrh|jhrdt|jhdt|jhrd|jhd|jh)\.?\s*$",
    re.IGNORECASE,
)
_RELATIVE_CENTURY_EN = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)[-\s]+"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:century|cent\.?|c\.)\s*$",
    re.IGNORECASE,
)
# Roemisch-Notation innerhalb der Relativen-Position-Struktur ("Mitte XIX.
# Jahrhundert", "late XIX century", "Anfang XX. Jhdt."). Spiegelt
# _RELATIVE_CENTURY_DE/_EN auf die Roemisch-Achse - dieselben sechs Praefix-
# Schluesselwoerter, derselbe [-\s]+-Separator, aber Roemisch-Zahl statt
# Arabisch. Kommt in geerbten Sammlungs-Notizen mit gemischter Roemisch-/
# Arabisch-Datierungs-Praxis vor: der Vorbesitzer notierte etwa "Anfang XIX.
# Jhdt." fuer eine Museums-Erwerbung im ersten Jahrzehnt des 19. Jhdt. Ohne
# diese Notation fielen alle relativen Roemisch-Formen stille auf None,
# obwohl semantisch eindeutig verortbar (Anfang -> 0, Mitte -> 50,
# Ende -> 99 innerhalb des Roemisch-adressierten Jahrhunderts).
_RELATIVE_CENTURY_ROMAN_DE = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)[-\s]+"
    r"([IVXLCM]+)\s*\.?\s*(?:jahrhundert|jahrhdt|jahrh|jhrdt|jhdt|jhrd|jhd|jh)\.?\s*$",
    re.IGNORECASE,
)
_RELATIVE_CENTURY_ROMAN_EN = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)[-\s]+"
    r"([IVXLCM]+)\.?\s+(?:century|cent\.?|c\.)\s*$",
    re.IGNORECASE,
)


def _normalize_month_name(name: str) -> int | None:
    key = name.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    # NFKD-Dekomposition + Combining-Mark-Filter strippt uebrige lateinische
    # Diakritika (FR: é/è/ê/à/â/î/ô/û/ç/ï, IT: à/è/ì/ò/ù, ES: á/í/ó/ñ/ü), sodass
    # "février"/"août"/"décembre" auf ASCII-Aequivalente fevrier/aout/decembre
    # mappen. DE-Umlaute wurden vorher explizit auf ae/oe/ue transliteriert
    # (historische DE-Schreibweise), damit der Filter sie nicht auf a/o/u
    # zusammenfaltet - Reihenfolge ist wesentlich.
    key = "".join(
        c for c in unicodedata.normalize("NFKD", key)
        if not unicodedata.combining(c)
    )
    return _MONTH_NAMES.get(key)


def _normalize_season_name(name: str) -> int | None:
    key = name.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    key = "".join(
        c for c in unicodedata.normalize("NFKD", key)
        if not unicodedata.combining(c)
    )
    return _SEASON_MONTHS.get(key)


def _normalize_holiday_name(name: str) -> tuple[int, int] | None:
    """Normalisiert Feiertag-Namen (Umlaut-Ersatz, Whitespace-/Punkt-/
    Apostroph-/Bindestrich-Strip, Case-Fold) und liefert (Monat, Tag) oder
    None fuer unbekannte Namen.

    Die Normalisierung mappt alle typografischen Schreibvarianten auf denselben
    Dict-Key: ``"St. Nicholas Day"`` -> ``"stnicholasday"``,
    ``"New Year's Day"`` / ``"New Year’s Day"`` -> ``"newyearsday"``,
    ``"Heilige Drei Koenige"`` / ``"Heilige Drei Könige"`` -> ``"heiligedreikoenige"``,
    ``"Tag der Arbeit"`` -> ``"tagderarbeit"``. Damit sind die Multi-Wort-
    Feiertage in :data:`_HOLIDAY_MONTH_DAY` mit ihrer kanonischen
    Einzel-Token-Form gefuehrt und der Aufrufer muss keine Wort-Grenzen
    beruecksichtigen. Umlaut-Transliteration (ae/oe/ue/ss) spiegelt die
    identische Behandlung in :func:`_normalize_month_name` /
    :func:`_normalize_season_name`.
    """
    key = _holiday_key(name)
    return _HOLIDAY_MONTH_DAY.get(key)


def _holiday_key(name: str) -> str:
    """Kanonischer Einzel-Token-Schluessel fuer Feiertag-Namen.

    Aus :func:`_normalize_holiday_name` heraus faktorisiert, damit die
    identische Normalisierung von :func:`_normalize_variable_holiday`
    genutzt werden kann - beide Dicts (:data:`_HOLIDAY_MONTH_DAY` und
    :data:`_HOLIDAY_EASTER_OFFSET`) sind gegen denselben Norm-Schluessel
    indiziert, und ein aus dem :data:`_HOLIDAY_YEAR`-Regex gefallener Name
    wird pro Aufruf nur einmal normalisiert.
    """
    key = name.strip().lower()
    key = (
        key.replace("ä", "ae").replace("ö", "oe")
        .replace("ü", "ue").replace("ß", "ss")
    )
    return re.sub(r"[\s.\-'’‘`]+", "", key)


def _normalize_variable_holiday(name: str) -> int | None:
    """Osterdatums-relativer Offset fuer variable Feiertag-Namen; None fuer
    unbekannte Namen. Spiegelt :func:`_normalize_holiday_name` auf die
    Osterzyklus-Achse und nutzt denselben :func:`_holiday_key`-Norm-Schluessel.
    """
    return _HOLIDAY_EASTER_OFFSET.get(_holiday_key(name))


def _variable_holiday_iso(name: str, year: int) -> str | None:
    """ISO-Datum fuer einen variablen Feiertag im gegebenen Jahr, oder None
    wenn der Name unbekannt ist bzw. das Jahr ausserhalb des unterstuetzten
    1800..2999-Bandes liegt. Osterdatum via :func:`_easter_sunday`, dann
    Offset in Tagen aus :data:`_HOLIDAY_EASTER_OFFSET` mittels
    :class:`datetime.timedelta` addiert - die Datumsarithmetik traegt den
    Monat-/Jahres-Uebergang automatisch (z.B. Aschermittwoch 2016 = 10.02.
    faellt vom April-Ostern des Vorjahres in den Vorfebruar).
    """
    offset = _normalize_variable_holiday(name)
    if offset is None:
        return None
    if not 1800 <= year <= 2999:
        return None
    e_month, e_day = _easter_sunday(year)
    d = datetime.date(year, e_month, e_day) + datetime.timedelta(days=offset)
    return d.isoformat()
# DMS: 46°30'15" N  /  7° 30' 0'' O  /  46°30'15.5"S
#
# Prime-Zeichen fuer Minuten (Einfach-Prime): ASCII-Apostroph ``'`` (U+0027),
# echtes Prime ``′`` (U+2032, Unicode-Standard), und die typografischen Curly-
# Quotes ``’`` (U+2019 right single) und ``‘`` (U+2018 left single). Die
# Curly-Formen entstehen automatisch, wenn ein Sammler die Koordinate in
# Word/Outlook/LibreOffice-Writer eingibt (Autoformat wandelt ``'`` -> ``’``)
# oder aus einer PDF/DOCX-Quelle kopiert; bisher fielen alle typografisch
# gesetzten DMS-Koordinaten stille auf None (das _DMS-Pattern kannte nur
# ASCII-Apostroph und echtes Prime U+2032), obwohl die Curly-Form die de-facto
# Notation in Word-basierten Dokumentationsketten ist.
#
# Double-Prime fuer Sekunden: ASCII-Anfuehrungszeichen ``"`` (U+0022), echtes
# Double-Prime ``″`` (U+2033), Curly-Doubles ``”`` (U+201D right double) und
# ``“`` (U+201C left double); zusaetzlich zwei aufeinander folgende Prime-
# Zeichen (``''``, ``’’``, ``‘‘``, ``''`` u.a.), wie sie in Terminal-Ausgaben
# und ASCII-only-Quellen ohne echten Double-Prime ueblich sind. Der Compound-
# Fall wird durch ``[' ' ' ' ']{2}`` abgedeckt: irgend zwei aufeinanderfolgende
# Einfach-Primes werden als Double interpretiert. Kollisionsfrei zu echten
# Double-Primes durch die Alternation (``|``): die spezifische Doubles-Klasse
# wird zuerst versucht.
_DMS = re.compile(
    r"""(\d+(?:[.,]\d+)?)\s*°               # Grad
        (?:\s*(\d+(?:[.,]\d+)?)\s*['′’‘])?    # optional Minuten (ASCII + prime + curly)
        (?:\s*(\d+(?:[.,]\d+)?)\s*(?:["″”“]|['′’‘]{2}))?  # optional Sekunden (double-prime + zwei Primes)
        \s*([NSEWOnsewo])                   # Himmelsrichtung
    """,
    re.VERBOSE,
)
# Colon-separierte DMS-Notation ohne Grad-/Minuten-/Sekunden-Symbole:
# "46:30:15 N" / "46:30:15.5 S" / "7:30:0E". Verbreitet in GPS-Logs,
# Marine-/Luftfahrt-Notation und maschinen-lesbaren Exporten, wo das ° / ' / "
# weggelassen wird (typische CSV-Exports aus GPS-Tools, NMEA-Konvertierungen,
# Wikipedia-Koordinaten in der maschinen-lesbaren Form). Drei Doppelpunkt-
# getrennte Zahlen mit obligatorischer Himmelsrichtung am Ende decken Grad,
# Minuten und Sekunden ab; die Himmelsrichtung ist hier obligatorisch, um
# Kollision mit Zeit-Notation (``14:30:00`` Uhrzeit) zu vermeiden - ohne den
# N/S/E/W/O-Marker ist die Drei-Doppelpunkt-Folge nicht eindeutig als
# Koordinate erkennbar. Sekunden duerfen Dezimalpunkt/-Komma haben
# (``46:30:15.5 N``). Spiegelt die Struktur von _DMS (4 Capture-Gruppen:
# Grad, Minuten, Sekunden, Richtung), damit _dms_to_decimal ohne Anpassung
# funktioniert. Bisher fielen alle drei colon-DMS-Formen auf falsche Werte
# (das _DECIMAL_PAIR-Pattern greift mit den letzten beiden Zahlen statt mit
# den ersten Grad-Anteilen, sodass ``46:30:15 N, 7:30:0 E`` als ``(15.0, 7.0)``
# gelesen wurde - silenter Koordinaten-Datenverlust). Wird vor _DMS gepruft
# (kollisionsfrei: _DMS verlangt °, colon-DMS verbietet es), damit die Reihen-
# folge dem Spezifischen-vor-Allgemeinen-Prinzip folgt.
#
# Sekunden-Komponente ist optional gemacht ``(?:\s*:\s*(\d+(?:[.,]\d+)?))?``,
# damit die Grad+Minuten-only-Form ``46:30 N`` (ein Doppelpunkt statt zwei)
# auch matcht - sehr verbreitet in Consumer-GPS-Displays, die bei zoom-out
# nur die zwei signifikanten Positionen anzeigen, sowie in
# maritimen/Aviatik-Log-Zeilen mit Sekunden = 0 (die dann bewusst weggelassen
# werden). Bisher fiel diese Form still auf einen falschen Wert durch:
# ``46:30 N, 7:45 E`` trifft _DMS_COLON nicht (nur ein Doppelpunkt statt zwei),
# faellt auf _DECIMAL_PAIR-Fallback, der die letzten zwei Zahlen (30 und 7)
# als Koordinaten-Paar erkennt - die Grad-Anteile 46 und 45 werden ignoriert
# und der Sammler sieht ``(30.0, 7.0)`` statt der intendierten (46.5, 7.75).
# Die Kollisions-Grenze zu Zeit-Notation bleibt durch die obligatorische
# Himmelsrichtung am Ende gewahrt: ``14:30 Uhr`` ist keine Koordinate, ``14:30
# N`` ist ambig (praktisch aber unueblich als Uhrzeit - Uhrzeiten haben kein
# ``N`` als Suffix). Spiegelt die _DMS-Konvention, in der Minuten und Sekunden
# beide optional sind (dort deckt es die reine Grad-Form ``46° N`` und die
# Grad+Minuten-Form ``46°30' N`` ab).
_DMS_COLON = re.compile(
    r"""(\d+(?:[.,]\d+)?)\s*:               # Grad + Doppelpunkt
        \s*(\d+(?:[.,]\d+)?)                # Minuten
        (?:\s*:\s*(\d+(?:[.,]\d+)?))?       # optionale Sekunden (Doppelpunkt + Zahl)
        \s*([NSEWOnsewo])                   # obligatorische Himmelsrichtung
    """,
    re.VERBOSE,
)
# DMS-Notation mit ASCII-Buchstaben-Markern statt der typografischen Symbole
# ° / ' / ": ``46d30m15sN``, ``46d 30m 15s N``, ``46deg30min15secN``, ``46deg
# 30min 15sec N``, ``46.5d N`` (nur Grad), ``46d 30.5m N`` (Grad + dezimale
# Minuten). Sehr verbreitet in Consumer-GPS-Geraete-Ausgaben (Garmin, TomTom),
# NMEA-/exiftool-ASCII-Dumps und aelteren Typewriter-/Text-Notationen, die
# die ° / ' / " -Symbole nicht auf Standard-Tastaturen erzeugen koennen und
# darum auf die ASCII-Ersatz-Konvention d/m/s zurueckgreifen. Auch in
# handgeschriebenen Sammler-Notizen aus dem GPS-Boersen-Jahrzehnt (~2000-2015)
# taucht das Format regelmaessig auf, weil GPS-Empfaenger die Koordinaten in
# der d/m/s-Form auf dem Display anzeigten und der Sammler den Display-Text
# 1:1 abgeschrieben hat. Bisher fielen alle Formen mit Buchstaben-Markern
# still auf None (die _DMS-Regex verlangt strikt ° / ' / "-Symbole, die
# _DMS_COLON verlangt strikt Doppelpunkte); typische GPS-Log-Zeilen wie
# ``46d30m15sN 7d30m0sE`` wurden zum silenten Koordinaten-Datenverlust bei
# der Migration.
#
# Vollform ``deg``/``min``/``sec`` und Kurzform ``d``/``m``/``s`` beide
# erlaubt (case-insensitive), optional mit Trailing-Punkt (``46d.30m.15s.N``
# aus Notationen mit Punkt-Trenner). Sekunden und Minuten sind optional
# (analog _DMS): reine Grad-Form ``46d N`` und Grad+Minuten-Form
# ``46d 30m N`` bleiben gueltig. Die Himmelsrichtung am Ende ist obligatorisch,
# weil sie den letzten Buchstaben-Marker eindeutig als Direction abgrenzt
# (ohne Direction waere ``46d30m15s`` semantisch nicht eindeutig als
# Koordinate erkennbar, siehe _DMS_COLON-Kommentar). Grad/Minuten/Sekunden-
# Werte akzeptieren dezimale Nachkomma-Stellen mit Punkt oder Komma-Trenner
# (``46.5d N``, ``46d 30,5m N``) symmetrisch zu _DMS.
#
# Vor _DMS_COLON eingeordnet: kollisionsfrei (Colon-Form verlangt ``:``, hier
# ist ``d``/``m``/``s``), aber die Buchstaben-Form ist spezifischer im Sinne
# der zeichen-basierten Konvention und liest sich in der Reihenfolge d ->
# colon -> ° natuerlicher (zunehmende typografische Spezialisierung).
# Kollisionsfrei zu _DMS (° / ' / "), _COORD_LABEL (dort werden nur Vor-Datums-
# Bezeichner wie ``lat=`` gestrippt, keine In-Zahl-Marker), _DECIMAL_PAIR (das
# den ``d``-Marker nicht kennt und darum das Buchstaben-Format nicht als
# gueltiges Zahl-Paar erkennt) und _SUFFIX_PAIR_NO_SEP (das eine reine
# Zahl+Richtung-Form erwartet, keine Zwischen-Marker). Spiegelt die Struktur
# von _DMS/_DMS_COLON (4 Capture-Gruppen: Grad, Minuten, Sekunden, Richtung),
# damit _dms_to_decimal ohne Anpassung funktioniert.
_DMS_LETTERS = re.compile(
    r"""(\d+(?:[.,]\d+)?)\s*(?:deg|d)\.?              # Grad + d/deg
        (?:\s*(\d+(?:[.,]\d+)?)\s*(?:min|m)\.?)?      # optional Minuten + m/min
        (?:\s*(\d+(?:[.,]\d+)?)\s*(?:sec|s)\.?)?      # optional Sekunden + s/sec
        \s*([NSEWOnsewo])                             # obligatorische Himmelsrichtung
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Prefix-DMS-Notation: Himmelsrichtung VOR den Grad-/Minuten-/Sekunden-Zahlen
# ("N 46° 30' 15\" E 7° 30' 0\""). Spiegelt die _DMS-Struktur (deg°, opt min',
# opt sec") auf die Prefix-Reihenfolge - Standard in aeltere Marine-/Luftfahrt-
# und einigen GPS-Tool-Formaten (NMEA-Konvertierungen, exiftool GPS-Output
# mit Direction-First, Wikipedia-Koordinaten-Vorlagen in EN "N 46°30′15″
# E 7°30′0″"), sowie in geerbten Sammlungs-Etiketten mit englischer Notations-
# Konvention. Bisher fielen alle Prefix-DMS-Formen stille auf falsche Werte:
# _DMS.findall verlangt die Richtung am Ende und lieferte 0 Hits, _PREFIX_PAIR
# akzeptiert das ° optional und griff mit den ersten beiden Zahlen statt mit
# den vollen DMS-Anteilen (``N 46° 30' 15\" E 7° 30' 0\"`` wurde als
# (46.0, 30.0) gelesen - Minuten und Sekunden gingen verloren). Der Fix
# spiegelt _DMS mit der Direction-First-Reihenfolge: Direction obligatorisch,
# Grad+°obligatorisch (schuetzt vor Kollision mit reiner Prefix-Decimal-
# Notation ``N 46.5 E 7.5``, die weiterhin von _PREFIX_PAIR behandelt wird),
# Minuten und Sekunden optional. Wird vor _PREFIX_PAIR (und nach _DMS_COLON)
# geprueft, damit die spezifischere DMS-Struktur den zu-greedy-_PREFIX_PAIR-
# Match ueberholt. Capture-Reihenfolge (dir, deg, min, sec) muss beim Aufruf
# von _dms_to_decimal(deg, min, sec, dir) umsortiert werden.
#
# Minuten-Prime-Marker ist optional, WENN die Minuten-Zahl einen Dezimalpunkt
# enthaelt (Degrees-Decimal-Minutes-Notation, DDM). DDM ist der Standard-Ausgabe-
# Modus fuer alle Consumer-GPS-Geraete-Anzeigen (Garmin/Magellan/TomTom im
# "hddd° mm.mmm'"-Modus), marine/Luftfahrt-Kartensysteme (BSH-Karten, IHO-S-57-
# Karten, IALA-Aids-to-Navigation-Notation) und die Wikipedia-Coord-Template-
# Ausgabe ``{{Coord|46|30.5|N|7|45.3|E}}``. Bisher fiel die DDM-Notation ohne
# Prime-Marker (``N 46°30.5 E 7°45.3``) still auf einen partiellen Match des
# _DMS_PREFIX-Zweigs: die Minuten-Gruppe scheiterte am fehlenden ``'``, das
# Pattern-Match brach nach dem Grad-Teil ab, und die naechste findall-Iteration
# griff den Rest als eigenen (Dir, Deg)-Match - die Dezimalminuten ``.5``/``.3``
# gingen dabei silent verloren. Aus dem typischen Sammler-Workflow "Fund auf
# Garmin-Handheld-Display gelesen, Werte im Feld notiert und in Excel getippt"
# oder "Wikipedia-Coord-Template-Wert in die Sammlung uebernommen" wurde damit
# silenter Koordinaten-Datenverlust bei der Migration; besonders schwer erkennbar,
# weil (46.0, 7.0) formal ein gueltiges Lat/Lon-Paar ist (Nord-Atlantik) und
# die _validate-Range-Pruefung erfolgreich durchlaeuft. Der Dezimalpunkt-Zwang
# ``\d+[.,]\d+`` an der prime-losen Alternante schuetzt vor Kollision mit
# Integer-Anhaeufungen ohne Marker: ``N 46° 30 E`` (30 als potentieller Minuten-
# Wert) bleibt weiterhin (46.0, ...) - die Ambiguitaet von integer-Zahlen ohne
# Prime (Katalog-Nummer, Sample-ID, Anzahl-Vermerk) ueberwiegt den Erkennungs-
# Gewinn, und Consumer-GPS-Displays geben Minuten IMMER mit Dezimal aus (die
# Praezision der GPS-Position uebersteigt Ganzzahl-Minuten deutlich). Alternante
# mit Prime bleibt Ganzzahl-tolerant (Minute-15 ohne Dezimal weiter valide,
# wenn ``'`` folgt). Sekunden-Prime bleibt obligatorisch, weil DDM per Definition
# keine Sekunden-Komponente hat (das ist der Grad-Minuten-Standard, entweder
# DDM ODER DMS, nie beides).
_DMS_PREFIX = re.compile(
    r"""([NSEWOnsewo])                          # Himmelsrichtung (obligatorisch, vorne)
        \s*(\d+(?:[.,]\d+)?)\s*°                # Grad + obligatorisches °
        (?:\s*(?:(?:(\d+(?:[.,]\d+)?)\s*['′])   # Minuten: Ganzzahl/Dezimal MIT Prime
            |(\d+[.,]\d+))                      # ODER Dezimal-Minuten OHNE Prime (DDM)
        )?
        (?:\s*(\d+(?:[.,]\d+)?)\s*(?:["″]|''))? # optional Sekunden (Prime obligatorisch)
    """,
    re.VERBOSE,
)
_DECIMAL_PAIR = re.compile(
    # Tab in der Separator-Klasse deckt TSV-Exporte (Tab-getrennte Excel-/
    # GPS-Tools) ab: "46.5\t7.5" ist dort verbreitet, aber bisher fiel die
    # Eingabe auf None, weil nur Leerzeichen/Komma/Semikolon/Slash erkannt
    # wurden. Spiegelt das Komma/Semikolon-Verhalten auf den Tab-Separator,
    # ohne die bestehenden Separatoren zu beruehren - re.VERBOSE behandelt
    # \t als gewoehnliches Tab-Literal innerhalb der Zeichenklasse.
    # Ampersand ``&`` als Separator deckt URL-Query-Parameter-Paare ab
    # (``?lat=46.5&lon=7.5``, ``?mlat=46.5&mlon=7.5`` aus OpenStreetMap-
    # /GeoServer-Share-Links): das ``&`` ist der URL-Query-Trenner zwischen
    # den zwei Parametern und trennt gleichzeitig die Zahlen, sobald die
    # Label ``lat=``/``lon=``/``mlat=``/``mlon=`` vorher gestrippt sind.
    # Ohne diesen Zusatz fielen die typischen Share-Links auf None.
    # Tilde ``~`` als Separator deckt die Bing-Maps-URL-Center-Point-Form ab
    # (``cp=46.5~7.5``): die Bing-Maps-Frontend-Spec verwendet ``~`` als
    # Lat-Lon-Trenner im ``cp``-(Center-Point-)Query-Parameter und in vielen
    # Bing-basierten Share-Links (bing.com/maps, bing.com/mapspreview,
    # ehem. maps.live.com). Bisher fielen alle Bing-Share-URLs stille auf
    # None, weil ``~`` weder in der Separator-Klasse stand noch die anderen
    # Patterns (_PREFIX_PAIR verlangt Richtungs-Buchstaben, _SUFFIX_PAIR_NO_SEP
    # ebenso, _ISO6709_COMPACT_DECIMAL ist auf ^...$ verankert und toleriert
    # kein URL-Praefix). Aus dem typischen Sammler-Workflow "Fundort in Bing
    # Maps anzeigen -> Share-URL aus Browser-Adress-Feld kopieren -> ins
    # Fundort-Feld einfuegen" entstand damit silenter Koordinaten-Datenverlust
    # bei der Migration. Kollisionsfrei zur bereits vorhandenen Approximations-
    # Praefix-Rolle von ``~`` in :func:`parse_iso_date` (das ist ein anderer
    # Parser mit eigenem Kontext); in :func:`parse_coordinates` wird ``~``
    # nirgends als semantisches Zeichen ausser als Bing-Separator verwendet.
    # Ein-Wege-Tilde-Praefix (``~46.5, 7.5``, "ca. 46.5, 7.5") bleibt weiterhin
    # ueber die vorhandene .search()-Semantik verlustfrei, weil der Leading-
    # Tilde vor der Zahl-Extraktion still gescannt wird und der Match erst
    # bei der ersten Ziffer beginnt.
    # Pipe ``|`` als Separator deckt Plain-Text-Datenbank-/CSV-Alternativ-
    # Exporte ab (z.B. ``46.5|7.5`` in PSV-Files, Pipe-getrennte SQLite-CLI-
    # Text-Exporte, viele GIS-Tools wie MapInfo/QGIS mit Pipe-Delimiter-
    # Option, sowie manche Bookmarking-Tools und Foto-Metadaten-Export-
    # Werkzeuge). Der Pipe-Separator vermeidet Kollisionen mit Komma-
    # Dezimal-Locales (DE/FR/IT), wo Kommas als Feld-Separator mehrdeutig
    # waeren - deshalb ist Pipe die de-facto Standard-Alternative fuer
    # Locale-agnostische Datenbank-Exporte in europaeischen GIS-Setups.
    # Bisher fiel jede Pipe-getrennte Koordinate stille auf None, obwohl
    # die beiden Zahl-Anteile eindeutig lesbar waren; symmetrisch zum
    # Tab-/Ampersand-/Tilde-Separator-Precedent wird Pipe in die Klasse
    # aufgenommen, ohne die bestehende Semantik zu beruehren.
    r"""([-+]?\d+(?:[.,]\d+)?)\s*°?\s*([NSEWOnsewo])?  # erste Zahl + opt. Richtung
        \s*[ \t,;/&~|]\s*
        ([-+]?\d+(?:[.,]\d+)?)\s*°?\s*([NSEWOnsewo])?  # zweite Zahl + opt. Richtung
    """,
    re.VERBOSE,
)
_PREFIX_PAIR = re.compile(
    r"""([NSnsEWOew])\s*([-+]?\d+(?:[.,]\d+)?)\s*°?  # Richtung + Zahl
        \s*[ ,;/]?\s*
        ([NSnsEWOew])\s*([-+]?\d+(?:[.,]\d+)?)\s*°?  # Richtung + Zahl
    """,
    re.VERBOSE,
)
# Compact Suffix-Form ohne expliziten Separator: ``46.5N7.5E``, ``46.5°N7.5°E``,
# ``46.5N 7.5E`` (Whitespace optional). Tritt in komprimierten GPS-Strings
# (Online-Tools, GPX-Captions) und Hand-Notizen auf, wenn der Schreiber Platz
# spart. Spiegelt _PREFIX_PAIR (Richtung+Zahl) als Suffix-Variante (Zahl+Richtung);
# beide Richtungen sind hier obligatorisch, weil sie als impliziter Separator
# zwischen den zwei Zahlen dienen (ohne Richtung waere die Eingabe ``46.57.5``
# nicht eindeutig in zwei Zahlen zerlegbar). Wird nach _DECIMAL_PAIR geprueft,
# damit das bestehende Verhalten fuer ``46.5N 7.5E`` (mit Separator) erhalten
# bleibt; greift nur dort, wo der separator-basierte Fallback nichts findet.
_SUFFIX_PAIR_NO_SEP = re.compile(
    r"""(\d+(?:[.,]\d+)?)\s*°?\s*([NSEWOnsewo])  # Zahl + Richtung (obligatorisch)
        \s*
        (\d+(?:[.,]\d+)?)\s*°?\s*([NSEWOnsewo])  # Zahl + Richtung (obligatorisch)
    """,
    re.VERBOSE,
)
# ISO 6709 Compact-Decimal-Form: ``+46.5+007.5/`` / ``+46.5+7.5`` / ``-46.5-7.5``.
# Internationaler Standard fuer Punkt-Koordinaten ohne Separator zwischen Lat
# und Lon - die beiden Vorzeichen dienen als impliziter Separator. Verbreitet
# in KML-Captions, HTML5-Microformats (z.B. Wikipedia-Geo-Microformat),
# GeoRSS-Feeds, exiftool GPS-Output und maschinen-lesbaren Exporten aus
# GIS-Tools. Der abschliessende ``/`` ist im Standard die Format-Trenner-
# Konvention (kann bei einzeln stehenden Koordinaten weggelassen werden).
# Sowohl Lat als auch Lon haben obligatorisches Vorzeichen (+ oder -); dadurch
# kollisionsfrei zu _DECIMAL_PAIR, das Vorzeichen optional behandelt und einen
# expliziten Separator [ \t,;/] zwischen den zwei Zahlen verlangt - hier ist
# das zweite + / - selbst der Separator. Die Lat-Komponente hat 1-2 Ziffern
# vor dem optionalen Dezimal (range ±90), die Lon-Komponente 1-3 Ziffern
# (range ±180) - Spec-konform mit ISO 6709, aber die Validierung erfolgt
# in _validate, sodass das Pattern selbst weniger restriktiv bleibt und
# auch nicht-fuehrend-genullte Eingaben akzeptiert (``+46.5+7.5`` ohne
# fuehrende Null in der Lon-Komponente, wie aus Tools mit minimaler Formatierung).
# Bisher fielen alle ISO-6709-Compact-Formen stille auf None: _DECIMAL_PAIR
# verlangt einen Separator [ \t,;/] zwischen den zwei Zahlen, den die compact-
# Form nicht hat; _PREFIX_PAIR verlangt Richtungs-Buchstaben (NSEWO), die
# hier durch Vorzeichen ersetzt sind; _SUFFIX_PAIR_NO_SEP verlangt ebenfalls
# Richtungs-Buchstaben am Ende. Aus typischen KML-/GIS-Exporten und HTML5-
# Microformat-Captions wurde damit silenter Koordinaten-Datenverlust bei
# der Migration. Der trailing-Slash ist optional, weil viele Tools (besonders
# GPS-Logger und Photo-EXIF-Schreiber) ihn weglassen, sobald die Koordinate
# einzeln steht; ISO 6709 verlangt ihn nur zum Trennen, wenn mehrere Koordi-
# naten hintereinander folgen.
_ISO6709_COMPACT_DECIMAL = re.compile(
    r"""^\s*
        ([+-]\d{1,2}(?:[.,]\d+)?)    # Lat: Vorzeichen + 1-2 Ziffern + opt. Dezimal
        ([+-]\d{1,3}(?:[.,]\d+)?)    # Lon: Vorzeichen + 1-3 Ziffern + opt. Dezimal
        /?\s*$                       # optionaler ISO-6709-Format-Trenner
    """,
    re.VERBOSE,
)
# ISO 6709 Compact-DM-Form: ``+DDMM+DDDMM/`` bzw. ``+DDMM.MM+DDDMM.MM/`` -
# Grad + Minuten ohne Trenner, Dezimalstellen (optional) haengen an den Minuten.
# ISO 6709 fixes die Ziffernbreite je Position: Lat = 2 Ziffern Grad + 2 Ziffern
# Minuten (Gesamt 4 Ganzzahl-Ziffern), Lon = 3 Ziffern Grad + 2 Ziffern Minuten
# (Gesamt 5 Ganzzahl-Ziffern). Die zwei Vorzeichen dienen als impliziter Separator
# zwischen Lat und Lon (dieselbe Konvention wie _ISO6709_COMPACT_DECIMAL) - der
# einzige strukturelle Unterschied ist die Ziffernbreite der Ganzzahl-Vorstand-
# Gruppe (4/5 statt 1-2/1-3), die den Format-Modus eindeutig macht:
#
#   ``+4630+00745/``       -> 46°30' N,  7°45' E
#   ``+4630.5+00745.5/``   -> 46°30.5' N, 7°45.5' E   (Dezimal-Minuten)
#   ``-4630-00745``        -> 46°30' S,  7°45' W    (ohne Trailing-Slash)
#
# Verbreitet in KML-Placemark-Koordinaten (die KML-Coordinates-Notation zieht
# aus ISO 6709 die kompakte Form), in GeoRSS-Feeds mit ``georss:point`` und
# in Marine-/Luftfahrt-NMEA-Konvertierungen. Bisher fielen alle DM-Formen
# stille auf None: _DECIMAL_PAIR verlangt einen Separator [\ t,;/&] zwischen
# den zwei Zahlen (den die compact-Form nicht hat), _ISO6709_COMPACT_DECIMAL
# limitiert die Ganzzahl-Ziffernbreite via \d{1,2}/\d{1,3} (4/5 Ziffern
# matchen nicht), _PREFIX_PAIR/_SUFFIX_PAIR_NO_SEP verlangen Richtungs-
# Buchstaben statt Vorzeichen. Aus KML-/GeoRSS-Captions entstand damit
# silenter Koordinaten-Datenverlust bei der Migration.
#
# Vor _ISO6709_COMPACT_DMS eingeordnet und *nach* _ISO6709_COMPACT_DECIMAL
# (dessen 1-2/1-3-Ganzzahl-Klasse strukturell disjunkt zu den 4/5-Klassen
# hier ist - kein Konflikt). Der DMS-Pattern liegt danach mit 6/7 Ziffern
# und ist ebenfalls disjunkt, sodass die drei Compact-Formen in der Reihen-
# folge Dezimal(1-2/1-3) -> DM(4/5) -> DMS(6/7) kollisionsfrei greifen.
# Anker-basierter Match (^...$) macht das Pattern restriktiv: nur exakt die
# compact-Form ohne zusaetzliche Tokens davor/danach greift.
_ISO6709_COMPACT_DM = re.compile(
    r"""^\s*
        ([+-])(\d{2})(\d{2}(?:[.,]\d+)?)    # Lat: Vorzeichen, 2 Grad, 2 Min(.frac)
        ([+-])(\d{3})(\d{2}(?:[.,]\d+)?)    # Lon: Vorzeichen, 3 Grad, 2 Min(.frac)
        /?\s*$                              # optionaler ISO-6709-Format-Trenner
    """,
    re.VERBOSE,
)
# NMEA-0183 Sentence-Form: ``DDMM.mmmm,N,DDDMM.mmmm,E`` bzw. mit Whitespace-
# Trenner ``DDMM.mmmm N DDDMM.mmmm E``. Struktur identisch zu ISO 6709
# Compact-DM (2 Ziffern Grad + 2 Ziffern Minuten mit Dezimal fuer Lat,
# 3 Ziffern Grad + 2 Ziffern Minuten mit Dezimal fuer Lon), aber mit N/S/E/W-
# Richtungs-Buchstaben statt Vorzeichen und mit Komma statt Ohne-Trenner
# als Field-Separator. Standard-Ausgabe des NMEA-0183-Protokolls, das jedes
# GPS-Geraet als Rohdaten-Ausgabe unterstuetzt (Serial-Port, USB-Debug,
# gpsd-Ausgabe, viele Handheld-GPS-Empfaenger im "NMEA-Dump"-Modus) und
# jede GPX-/KML-Konverter-Kette als Zwischenformat verwendet. Verbreitet
# in Rohdaten-Logs aus Fahrzeug-/Boots-Navigationsgeraeten, in exiftool-XMP-
# GPS-Exporten (die die EXIF-GPSPosition in NMEA-Format serialisieren),
# in gpsbabel-Ausgabe im "$GPGGA"-/"$GPRMC"-Sentence-Format und in Marine-
# /Luftfahrt-Navigations-Log-Files. Die Achsen-Konvention ist fix vorgegeben
# durch das NMEA-Sentence-Layout: erst Latitude (mit N/S), dann Longitude
# (mit E/W); die Reihenfolge kann von der Freitextzeile abweichen, dann
# reorientiert :func:`_orient` via Direction-Buchstaben.
#
# Bisher fielen alle NMEA-Notationen still auf None:
#   - :data:`_ISO6709_COMPACT_DM` verlangt obligatorische ±-Vorzeichen (Anker
#     ``([+-])(\\d{2})...``) und hat keine Alternante fuer N/S/E/W-Buchstaben,
#     die NMEA-Sentences als Richtungs-Marker verwenden.
#   - :data:`_DECIMAL_PAIR` liest den NMEA-Latitude "4630.500" als reine
#     Dezimalzahl 4630.5 (ausserhalb ±90-Bereich), fiele bei _validate durch,
#     lieferte None.
#   - :data:`_SUFFIX_PAIR_NO_SEP` und :data:`_PREFIX_PAIR` gehen von Grad-
#     Dezimal-Notation aus und wuerden das Grad+Min-Zusammensetz-Format
#     (2-Ziffer-Grad + 2-Ziffer-Min ohne Trenner) falsch als reine Dezimal
#     lesen.
#
# Aus dem typischen Sammler-Workflow "GPS-Log aus dem Handheld exportiert
# und die Roh-NMEA-Zeile ins Fundort-Feld kopiert" oder "GPX-Datei mit exif-
# tool -x GPSPosition-Ausgabe (im NMEA-Format) uebernommen" entstand damit
# silenter Koordinaten-Datenverlust bei der Migration; besonders schwer
# erkennbar, weil die (46.508333, 7.755)-Werte ohne Fehler-Report einfach
# als None gespeichert wurden.
#
# Ziffernbreite-Zwang macht das Pattern eindeutig:
#   - Lat: exakt 2 Ziffern Grad + exakt 2 Ziffern Minuten (Ganzzahl-Anteil vor
#     Dezimal). Reine Dezimal-Grad wie "46.5" hat nur 2 Ziffern vor dem Punkt
#     und faellt nicht in den 4-Ziffer-Ganzzahl-Match.
#   - Lon: exakt 3 Ziffern Grad + exakt 2 Ziffern Minuten (Ganzzahl-Anteil).
#     Reine Dezimal-Grad wie "7.5" hat nur 1 Ziffer, "07.5" nur 2 - Ambiguitaet
#     zu 007° (Dreistellen-Grad mit fuehrenden Nullen) waere theoretisch
#     moeglich, aber NMEA-Konvention verlangt IMMER die fuehrende Null-Padding
#     bei Longitude (``007`` statt ``7``), also ``00745`` (5 Ziffern) - reine
#     Dezimal-Formen erreichen die 5-Ziffer-Klasse nur mit einer Ganzzahl >= 10000,
#     was ausserhalb des ±180-Bereichs liegt und via _validate ausgefiltert wird.
#
# Kollisionsfrei zu bestehenden Patterns:
#   - :data:`_DECIMAL_PAIR` (Separator [ \\t,;/&~|]): das ``4630.500,N,00745.300,E``-
#     Muster koennte auf ``4630.500,N`` das DECIMAL_PAIR-Pattern treffen (Zahl +
#     Komma + Direction), aber die Ganzzahl ``4630.500`` > 90 faellt in
#     _validate durch und liefert None; der NMEA-Zweig laeuft VOR _DECIMAL_PAIR.
#   - :data:`_ISO6709_COMPACT_DM` (verlangt ±-Vorzeichen): NMEA hat N/S/E/W-
#     Buchstaben stattdessen, keine Ambiguitaet.
#   - :data:`_PREFIX_PAIR`/:data:`_SUFFIX_PAIR_NO_SEP`: die 4/5-Ziffer-Kompakt-
#     Grad-Minuten-Struktur ist strukturell disjunkt zur ein-/zwei-Ziffer-Dezimal-
#     Grad-Form (46.5, 7.5) - der NMEA-Match verlangt zusammenhaengende 4-Ziffer-
#     Lat und 5-Ziffer-Lon vor der Dezimalstelle, was Dezimal-Grad-Formen nicht
#     erfuellen.
#
# Trenner zwischen den vier Feldern (Lat-Zahl, Lat-Dir, Lon-Zahl, Lon-Dir) ist
# entweder Komma (NMEA-Standard), Whitespace (informal Copy-Paste) oder beide -
# das Pattern akzeptiert Komma-Whitespace-Kombinationen via ``\\s*,?\\s*`` (analog
# zu :data:`_DECIMAL_PAIR`, wo die Kombination optionaler Whitespace um Komma
# etabliert ist). Die Direction-Buchstaben sind case-insensitive (Caps-Lock-
# Notizen aus geerbten Sammlungs-Etiketten). ``O`` als deutsche Ost-Notation
# spiegelt die :data:`_DMS`-/:data:`_PREFIX_PAIR`-Konvention (in NMEA selbst
# ist nur ``E`` Standard, aber der DE-Nutzer schreibt oft ``O``).
_NMEA_LATLON = re.compile(
    r"""(?:^|[\s,;/$])                    # Anker: String-Anfang oder Trenner
        (\d{2})(\d{2}(?:[.,]\d+)?)        # Lat: 2 Ziffern Grad + 2 Ziffern Min(.frac)
        \s*,?\s*                          # Komma und/oder Whitespace
        ([NSns])                          # Lat-Direction (case-insensitive)
        \s*,?\s*                          # Komma und/oder Whitespace
        (\d{3})(\d{2}(?:[.,]\d+)?)        # Lon: 3 Ziffern Grad + 2 Ziffern Min(.frac)
        \s*,?\s*                          # Komma und/oder Whitespace
        ([EWewOo])                        # Lon-Direction (case-insensitive)
    """,
    re.VERBOSE,
)
# ISO 6709 Compact-DMS-Form: ``+DDMMSS+DDDMMSS/`` bzw. ``+DDMMSS.SS+DDDMMSS.SS/``
# - Grad + Minuten + Sekunden ohne Trenner, Dezimalstellen (optional) haengen
# an den Sekunden. Ziffernbreite: Lat = 2+2+2 = 6 Ganzzahl-Ziffern, Lon =
# 3+2+2 = 7 Ganzzahl-Ziffern. Wie beim DM-Pattern dienen die zwei Vorzeichen
# als impliziter Separator; die Ziffernbreite disambiguiert Compact-DMS von
# Compact-DM und Compact-Decimal.
#
#   ``+463015+0074500/``          -> 46°30'15" N,  7°45'00" E
#   ``+463015.5+0074500.5/``      -> 46°30'15.5" N, 7°45'00.5" E (Dezimal-Sekunden)
#   ``-463015-0074500``           -> 46°30'15" S,  7°45'00" W  (ohne Trailing-Slash)
#
# Verbreitet in exiftool-XMP-GPS-Exporten (viele Kamera-Tools schreiben die
# EXIF-GPSPosition-Struktur als ISO-6709-Compact-DMS in den XMP-Sidecar-
# Metadaten), in Wikipedia-Geo-Microformat (HTML5 ``<span class="geo">``),
# und in GML-/KML-Formaten mit hoher Genauigkeit. Bisher fielen alle DMS-
# Formen stille auf None (dieselbe Kette wie beim DM-Kommentar).
#
# Reihenfolge: nach _ISO6709_COMPACT_DECIMAL/_ISO6709_COMPACT_DM eingeordnet,
# aber die drei Klassen sind ueber die Ganzzahl-Ziffernbreite (1-2/1-3 vs.
# 4/5 vs. 6/7) strukturell disjunkt - Reihenfolge ist semantisch egal,
# nur der Konvention "spezifischer zuerst" folgend.
_ISO6709_COMPACT_DMS = re.compile(
    r"""^\s*
        ([+-])(\d{2})(\d{2})(\d{2}(?:[.,]\d+)?) # Lat: Vorzeichen, 2 Grad, 2 Min, 2 Sek(.frac)
        ([+-])(\d{3})(\d{2})(\d{2}(?:[.,]\d+)?) # Lon: Vorzeichen, 3 Grad, 2 Min, 2 Sek(.frac)
        /?\s*$                                   # optionaler ISO-6709-Format-Trenner
    """,
    re.VERBOSE,
)
# OpenStreetMap-URL-Fragment mit map-Position: ``#map=<zoom>/<lat>/<lon>``.
# Konvention der OSM-JavaScript-Karte (leaflet-basiert) und uebernommen von
# zahlreichen OSM-Derivaten (openstreetmap.de, waymarkedtrails.org, uMap,
# OpenTopoMap), die den View-State ueber die URL-Hash-Fragment-Position
# teilen. Die Reihenfolge <zoom>/<lat>/<lon> ist fix in der OSM-Frontend-
# Spec: das erste Slash-getrennte Feld ist der Zoom-Level (0-19 typisch,
# ganzzahlig), die naechsten zwei sind Latitude und Longitude als Dezimal.
# Bisher fiel jeder OSM-Share-Link durch _DECIMAL_PAIR auf ein semantisch
# falsches Paar: ``"#map=15/46.5/7.5"`` liefert (15.0, 46.5), weil das
# _DECIMAL_PAIR-Pattern die ersten beiden Slash-getrennten Zahlen greift -
# der Zoom-Level (15) wird als Latitude gelesen, die eigentliche Latitude
# (46.5) rutscht in die Longitude-Position, und die tatsaechliche Longitude
# (7.5) faellt weg. Aus einem typischen Sammler-Workflow "Fundort in OSM
# anzeigen -> Share-URL kopieren -> ins Fundort-Feld einfuegen" entstand
# damit silenter Koordinaten-Datenverlust bei der Migration. Wird in
# :func:`parse_coordinates` vor allen Pattern-Versuchen extrahiert (via
# .search), sodass die zoom-vorangestellte Struktur die generischen Zahl-
# Paar-Patterns nicht mehr irrefuehrt. Zoom-Feld akzeptiert optional einen
# Dezimal-Teil (neuere OSM-Versionen bzw. ``&map=`` in eingebetteten
# Rendern erlauben fraktionalen Zoom); Lat/Lon akzeptieren Vorzeichen und
# DE-Komma-Dezimal, symmetrisch zu den uebrigen Coord-Patterns. Beide
# separator-Slashes zwischen Zoom-Lat und Lat-Lon sind fix in der OSM-Spec.
# Kollisionsfrei zu _DECIMAL_PAIR (das keinen ``#map=``-Prefix kennt) und
# zu _COORD_LABEL (das ``map`` nicht als Koordinaten-Label listet).
_OSM_HASH_MAP = re.compile(
    r"""\#map=\d+(?:[.,]\d+)?/                        # #map=<zoom>/
        ([-+]?\d+(?:[.,]\d+)?)/                       # <lat>/
        ([-+]?\d+(?:[.,]\d+)?)                        # <lon>
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Wikipedia-GeoHack-URL-Query-Parameter ``params=`` mit Underscore-getrennter
# Koordinaten-Kette (Decimal-mit-Direction, DM oder DMS) - die Standard-Form
# aller Wikipedia-Artikel-Koordinaten-Boxen: der Klick auf ``46° 30′ 15″ N,
# 7° 30′ 15″ E`` in einem Wikipedia-Artikel oeffnet
# ``https://geohack.toolforge.org/geohack.php?pagename=<Titel>&params=46_30_15_N_7_30_15_E&type=...``,
# und viele Sammler kopieren diese URL direkt aus dem Browser als Quellen-
# Beleg fuer den Fundort. Bisher fiel jede GeoHack-URL still auf None, weil
# Underscore (``_``) weder in :data:`_DECIMAL_PAIR`s Separator-Klasse
# ``[ \t,;/&~]`` steht noch die DMS-Patterns (:data:`_DMS`, :data:`_DMS_COLON`,
# :data:`_DMS_LETTERS`, :data:`_DMS_PREFIX`) den Underscore als Zahl-Trenner
# kennen - aus einem typischen Sammler-Workflow "Fundort in Wikipedia
# nachschlagen -> Coord-Link kopieren -> ins Fundort-Feld einfuegen"
# entstand damit silenter Koordinaten-Datenverlust bei der Migration. Die
# GeoHack-Grammatik ist strikt: ``params=<lat>_<direction>_<lon>_<direction>
# [_type:...|_scale:...|_region:...]`` mit ``<lat>``/``<lon>`` als 1, 2 oder
# 3 Underscore-getrennten Zahlen (Decimal-, DM- oder DMS-Form). Direction-
# Buchstaben N/S fuer Lat und E/W (auch DE-Alternante O fuer Ost) fuer Lon
# sind obligatorisch und dienen als impliziter Separator zwischen den zwei
# Achsen. Die drei Zahl-Optionalitaets-Klauseln erlauben alle drei Formen:
# ``46.5_N`` (Decimal), ``46_30_N`` (DM), ``46_30_15_N`` (DMS). Nach der
# zweiten Direction folgt entweder Query-Parameter-Separator (``&``, ``_type:``
# etc.) oder das String-Ende - die Alternante ``(?=_[A-Za-z]|&|$)`` verhindert
# das versehentliche Fressen des nachfolgenden ``type:``-Parameters. Kollisions-
# frei zu :data:`_OSM_HASH_MAP` (das verlangt ``#map=``-Praefix, nicht
# ``params=``), zu :data:`_GEO_URI` / :data:`_GEO_URI_ANDROID_QUERY` (die
# verlangen ``geo:``-Scheme), zu :data:`_GOOGLE_PLACE_3D_4D` (das verlangt
# ``!3d``/``!4d``-Fragment), und zu allen Decimal-/DMS-/Prefix-/Suffix-
# Patterns (die kennen Underscore nicht als Separator und fielen bisher
# still auf None). Case-Insensitiv, weil ``PARAMS=`` in geerbten URLs mit
# Caps-Lock-Encoding vorkommt.
_GEOHACK_PARAMS = re.compile(
    r"""(?:^|[?&])params=                              # Query-Parameter-Anker
        (\d+(?:\.\d+)?)                                # Lat-Grad
        (?:_(\d+(?:\.\d+)?))?                          # Lat-Minuten (optional)
        (?:_(\d+(?:\.\d+)?))?                          # Lat-Sekunden (optional)
        _([NS])                                        # Lat-Direction
        _
        (\d+(?:\.\d+)?)                                # Lon-Grad
        (?:_(\d+(?:\.\d+)?))?                          # Lon-Minuten (optional)
        (?:_(\d+(?:\.\d+)?))?                          # Lon-Sekunden (optional)
        _([EWO])                                       # Lon-Direction
        (?=_[A-Za-z]|&|$)                              # Ende: Type-Suffix, Ampersand oder String-Ende
    """,
    re.IGNORECASE | re.VERBOSE,
)
# WKT-POINT-Notation (OGC Simple Features / ISO 19125) - Standard-Serialisierungs-
# Form fuer Punkt-Geometrien aus GIS-Werkzeugketten: PostGIS ST_AsText,
# GeoPandas .to_wkt, QGIS "Copy as WKT", ogr2ogr, ArcGIS Feature-to-Text und
# jeder Shapefile-Export-Pfad, der ueber GEOS/GDAL laeuft. Die OGC-Achsen-
# Konvention ist fix vorgegeben: X ist Longitude (Ost-West), Y ist Latitude
# (Nord-Sued) - unabhaengig davon, dass EPSG-Konventionen fuer geografische
# Datenreferenz-Systeme oft die umgekehrte Reihenfolge (Lat, Lon) verwenden.
# In WKT ist der Standard IMMER (X Y), also (Lon Lat). Vor diesem Pattern
# fiel jeder WKT-POINT-Text durch _DECIMAL_PAIR (Whitespace-Separator, keine
# obligatorischen Direction-Buchstaben) und lieferte silente Achsen-
# Vertauschung: ``"POINT(7.5 46.5)"`` wurde als ``(lat=7.5, lon=46.5)``
# gelesen, obwohl der publizierte Wert lat=46.5, lon=7.5 meint. Aus einem
# typischen Sammler-Workflow "Fundort in QGIS anzeigen -> Copy as WKT ins
# Fundort-Feld einfuegen" oder aus einem SQL-Report ueber PostGIS-Tabellen
# (``SELECT ST_AsText(geom) FROM ...``) entstand damit silenter Achsen-
# Vertauschungs-Fehler bei der Migration; besonders schwer erkennbar, weil
# ``(7.5, 46.5)`` formal ein gueltiges Lat/Lon-Paar ist (Nord-Atlantik) und
# die _validate-Range-Pruefung erfolgreich durchlaeuft. Match ist definitiv:
# wenn das POINT-Keyword erkannt wird, ist die (Lon Lat)-Reihenfolge
# eindeutig, und ein Fallback auf _DECIMAL_PAIR wuerde exakt die Vertauschung
# reintroduzieren, die dieser Zweig fixt. Optional-Marker ``Z``/``M``/``ZM``
# nach dem POINT-Keyword sind OGC-Erweiterungen fuer 3D-/Measure-Dimensionen
# (Elevation, linear referenced measure) - die optionalen Werte werden nach
# Lat konsumiert, aber nicht in Rueckgabe eingerechnet (die App fuehrt keine
# Elevation-/Measure-Achse). Optionaler ``SRID=<n>;``-Praefix ist die
# PostGIS-EWKT-Erweiterung (Spatial Reference Identifier, meist 4326 fuer
# WGS84); wird toleriert aber semantisch ignoriert (die App speichert
# Koordinaten immer in dem CRS, das der Sammler eingegeben hat). Kollisionsfrei
# zu :data:`_COORD_LABEL` (weder ``point`` noch ``srid`` sind dort gelistet),
# zu :data:`_PREFIX_PAIR` / :data:`_SUFFIX_PAIR_NO_SEP` (die verlangen
# obligatorische Direction-Buchstaben), zu :data:`_DECIMAL_PAIR` (das per
# .search kaeme, aber der WKT-Match ist per .match anchored und laeuft
# davor). Case-Insensitiv, weil die verschiedenen WKT-Ausgabepfade
# unterschiedliche Case-Konventionen haben (PostGIS ``POINT``, GeoJSON-to-WKT
# oft ``Point``, ogr2ogr manchmal Lowercase). DE-Komma-Dezimal wird toleriert
# (kein Standard-WKT, aber Sammler-typisch bei Export aus DE-Locale-Excel).
_WKT_POINT = re.compile(
    r"""^\s*(?:SRID=\d+\s*;\s*)?             # optional EWKT SRID-Prefix
        POINT\s*(?:Z|M|ZM)?\s*               # POINT-Keyword + optionaler Z/M/ZM-Marker
        \(\s*
        ([-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)   # X = Longitude
        \s+
        ([-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)   # Y = Latitude
        (?:\s+[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?){0,2}  # optionale Z/M-Achsen
        \s*\)\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
# GeoJSON-Point-Notation (RFC 7946) - Standard-Serialisierungs-Form fuer Punkt-
# Geometrien aus JSON-basierten GIS-Werkzeugketten: geojson.io, Mapbox, Leaflet,
# Folium, geopandas .to_json(), QGIS "Save As... GeoJSON", ogr2ogr -f GeoJSON,
# Overpass-Turbo-Export und jeder Web-Karten-Frontend, der auf GeoJSON basiert.
# Die RFC-7946-Achsen-Konvention ist fix vorgegeben (§3.1.1): "A position is an
# array of numbers. There MUST be two or more elements. The first two elements
# are longitude and latitude, or easting and northing, precisely in that order
# and using decimal numbers." - also (Lon, Lat), spiegelt die WKT-Konvention
# aus OGC Simple Features. Vor diesem Pattern fiel jeder GeoJSON-Point-Text
# durch :data:`_DECIMAL_PAIR` (Komma-Separator zwischen den zwei Zahlen im
# ``[X, Y]``-Array) und lieferte silente Achsen-Vertauschung: ``{"type":
# "Point", "coordinates": [7.5, 46.5]}`` wurde als ``(lat=7.5, lon=46.5)``
# gelesen, obwohl der publizierte Wert lat=46.5, lon=7.5 meint. Aus einem
# typischen Sammler-Workflow "Fundort in geojson.io / QGIS anzeigen ->
# GeoJSON-Feature kopieren -> ins Fundort-Feld einfuegen" oder aus einem
# API-Response-Snippet (Overpass, Nominatim mit ``format=geojson``, Mapbox
# Directions API, ArcGIS REST) entstand damit silenter Achsen-Vertauschungs-
# Fehler bei der Migration; besonders schwer erkennbar, weil ``(7.5, 46.5)``
# formal ein gueltiges Lat/Lon-Paar ist (Nord-Atlantik) und die _validate-
# Range-Pruefung erfolgreich durchlaeuft. Match ist definitiv: wenn der
# GeoJSON-Point-Marker (Type-Feld mit Wert "Point" plus Coordinates-Feld
# mit Zwei-Element-Array) erkannt wird, ist die (Lon, Lat)-Reihenfolge
# eindeutig, und ein Fallback auf _DECIMAL_PAIR wuerde exakt die Vertauschung
# reintroduzieren, die dieser Zweig fixt. Nur Type=``Point`` wird als
# eindeutig behandelt: MultiPoint/LineString/Polygon haben verschachtelte
# Arrays (``[[X,Y], [X,Y], ...]``) und liefern semantisch einen Set/Pfad,
# der nicht auf einen Sammler-Fundort abbildbar ist - diese Formen fallen
# bewusst auf den bestehenden Fallback zurueck (analog zur MULTIPOINT-
# Regression im WKT-Test). Der Type-Match ist Case-Insensitive, weil einige
# Kette (besonders JavaScript/TypeScript-Codegen, kleingeschriebene JSON-
# APIs, Sammler-Hand-Notationen) die kanonische Titlecase-Form nicht
# einhalten. Der Coordinates-Array laesst optional ein drittes Element
# fuer die Elevation zu (RFC 7946 §3.1.1: "Implementations SHOULD NOT
# extend positions beyond three elements") - Elevation wird ignoriert
# (die App fuehrt keine Elevation-Achse), symmetrisch zur Z-Achse-Behandlung
# in _WKT_POINT. Reine JSON-Numeric-Notation (kein DE-Komma-Dezimal, kein
# ° / N/S/E/W): der JSON-Standard spezifiziert ``.`` als Dezimaltrenner
# und toleriert keine Locale-Varianten. Wissenschaftliche Notation E±N
# ist per JSON-Spec erlaubt und wird symmetrisch zu den uebrigen Coord-
# Patterns akzeptiert. Kollisionsfrei zu :data:`_COORD_LABEL` (weder
# ``type`` noch ``coordinates`` sind dort gelistet - die neuen Substrings
# stehen im JSON-Kontext mit Quote-Marker, sodass ``lon``-Substrings im
# JSON-Key-Namen keinen Label-Strip triggern) und zu allen Zahl-Paar-
# Patterns (die Suche nach den zwei Marker-Substrings ist strenger als
# jede generische Zahl-Extraktion). Zwei Reihenfolgen des Type/Coordinates-
# Members werden akzeptiert (JSON-Objekt-Member-Reihenfolge ist per
# spec unerheblich): der Type-Match und der Coordinates-Match laufen als
# zwei unabhaengige .search()-Aufrufe, die beide fuendig werden muessen.
_GEOJSON_POINT_TYPE = re.compile(
    r"""["']type["']\s*:\s*["']Point["']""",
    re.IGNORECASE,
)
_GEOJSON_POINT_COORDS = re.compile(
    r"""["']coordinates["']\s*:\s*\[\s*
        ([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)   # X = Longitude
        \s*,\s*
        ([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)   # Y = Latitude
        (?:\s*,\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)?   # optionale Elevation (Z)
        \s*\]
    """,
    re.IGNORECASE | re.VERBOSE,
)
# GeoURI-Notation (RFC 5870) - Standard-URI-Schema fuer geografische Koordinaten,
# verbreitet in: Android-Maps-Intents (``geo:``-Scheme aus der Android-Developer-
# Doc, jeder "In Karten oeffnen"-Link aus einer Nachrichten-/Kalender-App),
# vCard v4 (RFC 6350 §6.5.2, das GEO-Property speichert Kontakt-Standorte als
# GeoURI), iCalendar RFC 7986 (VEVENT/VLOCATION mit GEO-Property, Sammler-
# Kalender-Export mit Fundort-Termin), QR-Code-Standard "geo:"-Encoding fuer
# Standort-QR-Codes (Feld-/Museums-Schilder mit QR-Standort), OpenStreetMap-
# ``Share->geo:``-Format, ``osmand://`` und div. mobile Karten-Apps. RFC 5870
# §3.3 fixiert die Reihenfolge (Latitude, Longitude, [Altitude]) - im Gegensatz
# zur GeoJSON-/WKT-Konvention (Longitude, Latitude), also OHNE Achsen-Umsortierung.
# Der Altitude (drittes Element) wird ignoriert (die App fuehrt keine
# Elevation-Achse), symmetrisch zur Z-Achsen-Behandlung in :data:`_WKT_POINT`
# und :data:`_GEOJSON_POINT_COORDS`. Parameter (``;crs=<crs>``, ``;u=<uncertainty>``,
# beliebige Zusatzparameter) werden nach den Koordinaten toleriert aber
# semantisch ignoriert (die App speichert Koordinaten immer in dem CRS, das
# der Sammler eingegeben hat; RFC 5870 nennt WGS84 als Default und den einzigen
# obligatorisch unterstuetzten Wert). Scheme-Match ist Case-Insensitive (per
# RFC 3986 sind URI-Schemes Case-Insensitive; Android-Codegen produziert
# ``geo:``, aber Copy-Paste aus einer Terminal-/Log-Ausgabe kann ``GEO:``
# liefern). Match ist definitiv per anchored ``^`` - der GeoURI-Scheme-Marker
# ``geo:`` disambiguiert eindeutig vom RFC-6068 mailto-Scheme und allen
# anderen URI-Schemes; kein Fallback auf _DECIMAL_PAIR noetig (fuer die Standard-
# RFC-5870-Form wuerde _DECIMAL_PAIR zwar dieselben zwei Zahlen extrahieren,
# aber der Android-Query-Fall ``geo:0,0?q=<lat>,<lon>`` unten wuerde ohne
# expliziten GeoURI-Zweig auf ``0,0`` fallen).
_GEO_URI = re.compile(
    r"""^\s*geo:\s*
        ([-+]?\d+(?:\.\d+)?)                     # <lat>
        \s*,\s*
        ([-+]?\d+(?:\.\d+)?)                     # <lon>
        (?:\s*,\s*[-+]?\d+(?:\.\d+)?)?           # optional <alt>
        (?:\s*[;?].*)?                           # optional Parameter/Query-String
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
# Google-Maps-Android-Intent-Form ``geo:0,0?q=<lat>,<lon>[(<label>)]`` - die
# offizielle Android-Developer-Doc-Konvention fuer "Zeige Standort mit Label"
# und "Zeige Suchergebnis an Position": der ``geo:``-Pfad enthaelt die
# Platzhalter-Koordinaten ``0,0`` (Null Island), die *echten* Koordinaten
# stehen im ``?q=<lat>,<lon>``-Query mit optionalem Label in Klammern. Diese
# Form entsteht typischerweise, wenn der Sammler den "Teilen"-Button in
# Google Maps drueckt und den generierten Intent-URI aus dem Share-Sheet
# kopiert. Ohne diesen expliziten Zweig gewinnt der ``0,0``-Match aus dem
# geo-Pfad, weil er zuerst matcht - und der Sammler bekommt silente
# Null-Island-Koordinaten statt seiner Position. Muss VOR :data:`_GEO_URI`
# gepruft werden, weil sonst die generische GeoURI-Form auf ``0,0`` (den
# Platzhalter) matcht und der Query-Teil ignoriert wird. Label in Klammern
# ist RFC-3986-Query-kompatibel (Klammern sind ``sub-delims``); der Label-
# Text wird ignoriert (die App speichert Fundort-Bezeichnung im dedizierten
# Feld, nicht als Teil der Koordinaten).
_GEO_URI_ANDROID_QUERY = re.compile(
    r"""^\s*geo:\s*
        [-+]?\d+(?:\.\d+)?                        # placeholder <lat> (typisch 0)
        \s*,\s*
        [-+]?\d+(?:\.\d+)?                        # placeholder <lon> (typisch 0)
        (?:\s*,\s*[-+]?\d+(?:\.\d+)?)?            # optional placeholder <alt>
        (?:\s*;[^?]*)?                            # optional RFC-5870-Params
                                                  # (;u=25 Uncertainty in m,
                                                  # ;crs=wgs84 Coord-Ref-System)
        \s*\?[^#]*?\bq=\s*
        ([-+]?\d+(?:\.\d+)?)                      # echte <lat> im q-Parameter
        \s*,\s*
        ([-+]?\d+(?:\.\d+)?)                      # echte <lon> im q-Parameter
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
# Google-Maps-Place-URL-Fragment "!3d<lat>!4d<lon>" - die Protobuf-Feld-
# Serialisierung, mit der Google Maps im ``/data=``-Segment einer geteilten
# Place-URL die tatsaechliche Pin-Position kodiert. ``!3d`` markiert den
# double-Wert der Latitude an Feld-Index 3, ``!4d`` den double der Longitude
# an Feld-Index 4 - die beiden Marker stehen bei einer Single-Place-URL
# unmittelbar hintereinander. Diese Form entsteht typischerweise, wenn der
# Sammler in Google Maps auf einen Ort klickt (statt nur die Karte zu
# scrollen) und den Share-Link kopiert - die URL enthaelt dann zwei
# semantisch unterschiedliche Koordinaten-Paare: das ``@<lat>,<lon>,<zoom>z``-
# Segment fuer den View-Center (Kamera-Position) und das ``!3d<lat>!4d<lon>``-
# Fragment fuer die tatsaechliche Pin-Position des angeklickten Ortes. Beide
# Paare koennen unterschiedlich sein, wenn der Sammler heraus-/heraus-gezoomt
# ist und dann teilt: ``@46.5,7.5,6z`` (View auf Bern-Umgebung) mit
# ``!3d46.0207!4d7.7491`` (Pin auf Zermatt) - der publizierte Wert ist die
# Pin-Position, nicht der View-Center. Vor diesem Zweig fielen alle Google-
# Place-URLs still auf den View-Center-Wert, weil :data:`_DECIMAL_PAIR` das
# ``@``-Segment mit Komma-Separator zuerst greift und die Pin-Koordinaten
# im ``/data=``-Segment ignoriert (der ``!``-Delimiter des Protobuf-Encoding
# steht nicht in der Separator-Klasse ``[ \t,;/&~]``, sodass keiner der
# generischen Zahl-Paar-Zweige die ``!3d``/``!4d``-Zahlen zusammenbringt).
# Aus dem typischen Sammler-Workflow "Ort in Google Maps auf dem Smartphone
# suchen -> Pin antippen -> Teilen -> Link kopieren -> ins Fundort-Feld
# einfuegen" entstand damit silenter Fundort-Datenverlust: der Sammler bekam
# statt der tatsaechlichen Pin-Position die zufaellige Zoom-abhaengige
# Kamera-Position gespeichert; besonders schwer erkennbar, weil View-Center
# und Pin oft (aber nicht immer) uebereinstimmen und die _validate-Range-
# Pruefung in beiden Faellen erfolgreich durchlaeuft. Match ist definitiv:
# wenn die ``!3d...!4d...``-Signatur erkannt wird, sind die Werte die
# Pin-Koordinaten, und ein Fallback auf _DECIMAL_PAIR wuerde exakt den Bug
# reintroduzieren, den dieser Zweig fixt (View-Center statt Pin). Muss vor
# :data:`_DECIMAL_PAIR` gepruft werden, weil sonst der ``@``-URL-Center die
# Rueckgabe belegt. Case-Insensitivitaet (``!3D``/``!4D``) folgt der
# Toleranz-Konvention der uebrigen Coord-Muster (Google-Codegen produziert
# konsistent Lowercase, aber Copy-Paste aus manuell nachbearbeiteten URLs
# oder Screenshot-OCR kann Case brechen). DE-Komma-Dezimal wird toleriert
# (kein Standard von Google, aber Sammler-typisch bei Excel-Zwischenkopie
# mit DE-Locale). Kollisionsfreiheit zu :data:`_COORD_LABEL` (``!3d``/``!4d``
# sind keine Koordinaten-Label-Woerter), zu :data:`_PREFIX_PAIR` /
# :data:`_SUFFIX_PAIR_NO_SEP` (die verlangen obligatorische Direction-
# Buchstaben), zu :data:`_ISO6709_COMPACT_DECIMAL` (die per .match anchored
# sind und kein URL-Praefix erlauben). Kollisionsfreiheit zu Freitext-Zahlen
# nach einem Ausrufezeichen (``"Wow! 3d-Fotoshooting!"``): das Pattern
# verlangt die exakte Marker-Reihenfolge ``!3d...!4d`` mit unmittelbar
# folgender Zahl - ohne die zweite Marker-Zahl bleibt der Match aus und
# die Eingabe faellt auf den Fallback zurueck. Weitere Protobuf-Feld-Typen
# (``!3i`` fuer int32, ``!3s`` fuer string) sind fuer die Pin-Position
# nicht relevant und bleiben ausserhalb des Patterns.
_GOOGLE_PLACE_3D_4D = re.compile(
    r"""!3d([-+]?\d+(?:[.,]\d+)?)     # Pin-Latitude nach !3d-Marker
        !4d([-+]?\d+(?:[.,]\d+)?)     # Pin-Longitude nach !4d-Marker
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Yandex-Maps-URL-Konvention: die Query-Parameter ``ll=`` (map center) und
# ``pt=`` (placemark) verwenden Yandex-typische (Longitude, Latitude)-Reihenfolge,
# entgegen der von Google/Apple/Bing/OSM benutzten (Latitude, Longitude)-
# Konvention. Yandex Maps API-Dokumentation gibt die Reihenfolge fix vor:
# ``ll`` = "longitude and latitude of the map center, comma-separated";
# ``pt=<lon>,<lat>[,<marker_style>]`` fuer Placemarks (der optionale dritte
# Wert kodiert das Marker-Icon, keine Koordinaten-Semantik). Ohne diesen
# Zweig fiel jede Yandex-Share-URL durch das generische :data:`_DECIMAL_PAIR`
# und lieferte silente Achsen-Vertauschung: ``"https://yandex.com/maps/?ll=7.5,46.5"``
# wurde als ``(lat=7.5, lon=46.5)`` gelesen, obwohl der publizierte Wert
# lat=46.5, lon=7.5 meint. Aus dem typischen Sammler-Workflow "Fundort in
# Yandex Maps anzeigen -> Share-URL aus Browser-Adress-Feld kopieren -> ins
# Fundort-Feld einfuegen" entstand damit silenter Koordinaten-Datenverlust
# bei der Migration; besonders schwer erkennbar, weil ein Zahl-Paar mit
# vertauschten Achsen typisch immer noch innerhalb des :func:`_validate`-
# Range-Bandes liegen kann und keine None-Rueckgabe ausloest (die App
# landet einfach am falschen Ort in der Karte). Spiegelt strukturell den
# :data:`_WKT_POINT`-, :data:`_GEOJSON_POINT_COORDS`- und :data:`_OSM_HASH_MAP`-
# Zweig auf die Yandex-URL-Achse: alle Anbieter-spezifischen Konventionen,
# die dem generischen (Lat, Lon)-Standard widersprechen, gehoeren in eigene
# Zweige VOR der generischen Zahl-Paar-Extraktion. Domain-Alternative deckt
# die regionalen Yandex-TLDs ab (yandex.com/ru/by/kz/com.tr/ua/uz/fr/com.ge)
# sowie den Yandex-URL-Shortener ymaps.ru und den historischen
# maps.yandex.<tld>-Subdomain-Pfad. Case-Insensitiv, weil URLs aus
# Browser-Kopier-Puffern gelegentlich in Grossbuchstaben landen. DE-Komma-
# Dezimal in Yandex-URLs kommt in der Praxis nicht vor (URL-Parameter
# folgen Punkt-Dezimal-Konvention), wird aber vom Zahl-Pattern trotzdem
# akzeptiert (spiegelt die Toleranz der uebrigen URL-Zweige). Der %2C-
# URL-encoded Komma wird durch den generischen Pre-Processing-Strip
# (:func:`parse_coordinates`) auf ASCII-Komma normalisiert und braucht
# hier keine eigene Alternante.
_YANDEX_LL = re.compile(
    r"""(?:yandex\.(?:com|ru|by|kz|com\.tr|ua|uz|fr|com\.ge)/maps
          |ymaps\.ru
          |maps\.yandex\.(?:com|ru|by|kz|com\.tr|ua|uz|fr|com\.ge))
        [^#\s]*?
        [?&](?:ll|pt)=
        ([-+]?\d+(?:[.,]\d+)?)
        ,
        ([-+]?\d+(?:[.,]\d+)?)
    """,
    re.IGNORECASE | re.VERBOSE,
)
# KML-Point-Notation (OGC KML 2.2 / ISO 19153) - Standard-Serialisierungs-Form
# fuer Punkt-Geometrien aus Google-Earth-Exporten, .kml/.kmz-Dateien,
# QGIS-KML-Export, ogr2ogr -f KML, ArcGIS-KML-Konverter und jeder Karten-Kette,
# die auf dem KML-XML-Standard basiert. Die KML-Achsen-Konvention ist fix
# vorgegeben (KML Reference "coordinates"): "Tuple of comma-separated floating-
# point values (longitude, latitude, altitude) that specifies a coordinate.
# Longitude and latitude values are in decimal degrees ... Altitude values
# are optional." - also (Lon, Lat, [Alt]), spiegelt die WKT-/GeoJSON-Konvention
# aus OGC Simple Features und RFC 7946. Vor diesem Pattern fiel jeder KML-Point-
# Text durch :data:`_DECIMAL_PAIR` (Komma-Separator zwischen den zwei Zahlen
# im ``<coordinates>``-Element) und lieferte silente Achsen-Vertauschung:
# ``<coordinates>7.5,46.5,0</coordinates>`` wurde als ``(lat=7.5, lon=46.5)``
# gelesen, obwohl der publizierte Wert lat=46.5, lon=7.5 meint. Aus dem
# typischen Sammler-Workflow "Fundort in Google Earth setzen -> Placemark
# als KML exportieren / Copy-KML -> ins Fundort-Feld einfuegen" oder aus
# einem geerbten .kmz-Archiv mit Fund-Punkten aus einer alten Exkursion
# entstand damit silenter Achsen-Vertauschungs-Fehler bei der Migration;
# besonders schwer erkennbar, weil ``(7.5, 46.5)`` formal ein gueltiges
# Lat/Lon-Paar ist (Nord-Atlantik) und die _validate-Range-Pruefung
# erfolgreich durchlaeuft - keine None-Rueckgabe, kein Fehler-Report, der
# Datenpunkt landet einfach am falschen Ort in der Karte. Match ist definitiv
# nur, wenn BEIDE Marker (``<Point>``-Tag mit optionalem Namespace-Prefix
# UND ``<coordinates>``-Tag) vorhanden sind - dann ist die (Lon, Lat)-
# Reihenfolge per KML-Spec eindeutig, spiegelt die konservative
# GeoJSON-Marker-Kombination (Type=Point + Coordinates-Array). Fehlt der
# Point-Marker (``<LineString>``/``<LinearRing>``/``<Polygon>``), enthaelt
# das Coordinates-Element semantisch einen Pfad/Ring/Polygon mit mehreren
# Tupeln - die App fuehrt keine Pfad-Achse, daher fallen diese Formen
# bewusst auf den bestehenden Fallback zurueck (analog zur MULTIPOINT-
# Regression im WKT-Test und zur MultiPoint-Rejection in _GEOJSON_POINT).
# Namespace-Prefix ``<kml:Point>``/``<kml:coordinates>`` sowie andere
# XML-Namespaces (``<gx:Point>``, custom-prefix aus xmlns-Declarations)
# werden via ``(?:\w+:)?``-Optionaler-Prefix akzeptiert. Case-Insensitive,
# weil verschiedene KML-Ausgabepfade unterschiedliche Case-Konventionen
# haben (Google Earth ``Point``/``coordinates``, ogr2ogr manchmal
# lowercase, ArcGIS Titlecase). Der Coordinates-Elementinhalt darf durch
# Whitespace/Newlines eingeruegt sein (Google-Earth-Pretty-Print,
# XML-Formatter-Ausgabe), das Pattern strippt fuehrende Whitespace/Newline
# vor der Zahl-Extraktion via ``\s*`` nach dem oeffnenden Tag.
# Multi-Tupel-Coordinates (LineString/LinearRing/Polygon-Fall MIT
# ``<Point>``-Marker im selben String) waeren pathologisch (KML-Spec
# verbietet die Kombination) - der Zweig nimmt in diesem Fall das
# erste Tupel, symmetrisch zum WKT-Zweig, der auch nur den ersten
# POINT-Tupel greift. Reine JSON-Numeric-Notation (Punkt-Dezimal,
# scientific E±N) analog zu :data:`_GEOJSON_POINT_COORDS`; DE-Komma-
# Dezimal (``7,5,46,5``) waere in KML mehrdeutig (das Feld-Trennzeichen
# und der Dezimal-Trenner waeren identisch) und wird NICHT akzeptiert,
# spiegelt die KML-Spec (die ``.`` als Dezimal-Trenner fix vorgibt).
# Kollisionsfrei zu :data:`_COORD_LABEL` (weder ``point`` noch
# ``coordinates`` sind dort gelistet), zu :data:`_GEOJSON_POINT_COORDS`
# (das JSON-Bracket-Array-Syntax verlangt statt XML-Tag), zu
# :data:`_WKT_POINT` (das POINT-Keyword ohne Angle-Bracket verlangt) und
# zu :data:`_GEO_URI` / :data:`_GEO_URI_ANDROID_QUERY` (die den geo:-
# Scheme verlangen).
_KML_POINT_MARKER = re.compile(
    r"""<(?:\w+:)?Point\b[^>]*>""",
    re.IGNORECASE,
)
_KML_COORDINATES = re.compile(
    r"""<(?:\w+:)?coordinates\b[^>]*>\s*
        ([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)   # X = Longitude
        \s*,\s*
        ([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)   # Y = Latitude
        (?:\s*,\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)?   # optionale Altitude
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Gelaeufige Bezeichner vor den eigentlichen Koordinaten: "Lat: 46.5, Lon: 7.5",
# "Breite 46.5 Länge 7.5", "latitude=46.5 longitude=7.5". Werden vor dem
# Pattern-Matching entfernt; die Himmelsrichtung im Label (N/E/S/W als Buchstabe
# in "Lon") ist nicht gemeint und wuerde sonst _PREFIX_PAIR irrefuehren.
_COORD_LABEL = re.compile(
    r"""\b(?:
            latitude | lat | breitengrad | breite
          | longitude | longitudinal | long | lon | lng | laengengrad | laenge
          # ``lng`` ist die de-facto Standard-Kurzform der Longitude in den
          # verbreitetsten Web-Mapping-APIs (Google Maps JavaScript API mit
          # ``google.maps.LatLng``, Leaflet ``L.latLng(lat, lng)``, Mapbox GL
          # ``[lng, lat]``, MapKit JS, HERE Maps, Bing Maps V8) sowie im
          # geerbten Web-Framework-Ecosystem (Node.js geolocation Middleware,
          # React Native Maps, Flutter Maps, jeder Copy&Paste aus einer
          # DevTools-Konsole eines Web-Karten-Widgets). Neben ``lon`` die zweite
          # etablierte Konvention (Ein-Silben-Kurzform statt Drei-Buchstaben-
          # Prefix), zu unterscheiden von den GIS-/Wissenschafts-APIs (PostGIS,
          # GDAL, QGIS, ArcGIS), die ``lon`` bevorzugen. In Sammler-Notizen und
          # Fund-Etiketten aus modernen Foto-Apps mit eingebetteter Karte
          # (Google Photos "gps info", iPhone "Places", Bergtouren-Apps wie
          # Komoot/AllTrails, Foto-EXIF-Exporte via ExifTool JSON-Output mit
          # ``"GPSLongitude": ...`` als semantischer Schluessel, aber
          # ``"lng": ...`` in JavaScript-JSON-Formatierung) ist ``lng`` die
          # haeufigere Notation. Bisher fiel jede ``lat/lng``-Notation still
          # auf None: ``_COORD_LABEL`` erkannte ``lat`` und strippte es, ``lng``
          # blieb aber unbekannt und verhinderte via ``_PREFIX_PAIR`` /
          # ``_DECIMAL_PAIR`` die Struktur-Erkennung ("46.5 lng 7.5" hat keinen
          # zulaessigen Separator zwischen den Zahlen). Semantisch identisch
          # zu ``lon``/``long`` - nur eine Wort-Alternante, keine Struktur-
          # aenderung. Case-insensitive spiegelt die anderen Label-Woerter
          # (``LAT``, ``Lat``, ``lat`` gleich behandelt).
          | längengrad | länge
          | mlat | mlon                # OpenStreetMap-Share-URL-Query-Parameter
          # IT-Vollformen: Ticino/Val d'Aosta pflegen Sammler-Notizen in der
          # italienischen Amtssprache; explizite Achsen-Beschriftungen aus
          # GIS-/wissenschaftlichen Publikationen und aus Museo-cantonale-di-
          # storia-naturale-Etiketten ("Latitudine: 46.5, Longitudine: 7.5")
          # nutzen die IT-eigenstaendigen Vollformen. Bisher fielen alle
          # ``Latitudine``/``Longitudine``-Formen still durch: die Anschnitt-
          # Guard ``(?![A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ])`` blockte ``lat`` in
          # ``latitudine`` (die Zeichen ``i`` nach ``lat`` ist Wort-Zeichen),
          # sodass das Label nicht als Whitespace gestrippt wurde und
          # :data:`_DECIMAL_PAIR` an dem Wort-Rest scheiterte. Spiegelt die
          # FR-/IT-Erweiterungen in :data:`_MONTH_NAMES` / :data:`_SEASON_MONTHS`
          # / :data:`_DIRECTION_WORD` auf die Koordinaten-Label-Achse.
          # Kollisionsfrei zu allen bestehenden Alternativen (``latitudine``
          # startet mit ``lat`` und ``longitudine`` mit ``long``, aber die
          # bereits vorhandene Alternation-Reihenfolge Voll-vor-Kurz sorgt
          # dafuer, dass hier die Voll-Formen zuerst matchen).
          | latitudine | longitudine
        )
        (?![A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ])     # kein Anschnitt eines laengeren Wortes ("latex")
        \.?\s*[:=]?\s*         # optionaler Punkt + : / = + Whitespace
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Label-gesteuerte Extraktion, wenn *beide* Achsen (lat- und lon-Familie) explizit
# markiert sind. Deckt die verbreitete Query-Param-Form ``?mlon=7.5&mlat=46.5``
# (OSM-Share-URL mit reversed Order), ``?lng=7.5&lat=46.5`` (Web-Mapping-API mit
# Longitude-zuerst-Reihenfolge) sowie freitext-Notation ``"Lon: 7.5, Lat: 46.5"``
# / ``"longitude=7.5 latitude=46.5"`` ab, in denen der Longitude-Wert *vor* dem
# Latitude-Wert steht. Bisher fielen alle solchen Formen in :data:`_COORD_LABEL`,
# wurden dort still zu Whitespace gestrippt und danach von :data:`_DECIMAL_PAIR`
# in Auftritts-Reihenfolge (Lon, Lat) als (lat, lon) fehlinterpretiert - silente
# Achsen-Vertauschung bei jedem OSM-mlon-zuerst-URL, jedem lng-zuerst-JSON aus
# Web-Karten-Widget-DevTools-Exporten, jedem Freitext mit Lon-vor-Lat-Reihenfolge
# und jedem GIS-Report, der die geographisch uebliche (X, Y) = (Lon, Lat)-Achsen-
# Reihenfolge ausgibt. Besonders schwer erkennbar bei Fundorten in der Schweiz /
# Alpen-Region, wo lat=7.5 und lon=46.5 formal ein gueltiges Paar (Golf von
# Guinea nahe Sao Tome) ergeben und die _validate-Range-Pruefung erfolgreich
# durchlaeuft.
#
# Die neuen Patterns spiegeln die Label-Menge aus :data:`_COORD_LABEL` auf zwei
# disjunkte Achsen-Regexen (Lat-Familie vs. Lon-Familie), erfassen aber
# zusaetzlich den Wert selbst (mit optionaler Vorzeichen und optionaler
# N/S/E/W/O-Direction-Praefix/Suffix). Case-Insensitiv, weil OSM-Share-Links
# und JavaScript-API-JSON Kleinschreibung nutzen (mlat/mlon, lat/lng) und
# freitext-Notation oft Grossschreibung (Lat/Lon) hat. Alternation-Reihenfolge
# (Voll vor Kurz) plus :samp:`(?![A-Za-z...])`-Lookahead spiegelt
# :data:`_COORD_LABEL` fuer Anschnitt-Schutz ("latex" faengt nicht "lat").
#
# Zusaetzlicher End-Anker ``(?=$|[\s,;&?#/])`` nach der Wert-Extraktion stellt
# sicher, dass DMS-Fortsetzungen (``"Lat: 46d 30m 15s N"``, ``"Lat: 46°30'15\"N"``,
# ``"Lat: 46:30:15 N"``, ``"Lat: 46 30 15 N"``) NICHT als Plain-Decimal fehl-
# gelesen werden - die DMS-Formen bleiben Zustaendigkeit von _DMS/_DMS_LETTERS/
# _DMS_COLON/_DMS_PREFIX und dieser Fall faellt via Sentinel auf die generische
# Route zurueck. Vorzeichen (``-``) und DE-Komma-Dezimal (``46,5``) werden im
# Zahl-Capture toleriert.
_LAT_LABELED_VALUE = re.compile(
    r"""\b(?:latitudine|latitude|lat|breitengrad|breite|mlat)
        (?![A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ])
        \.?\s*[:=]?\s*
        (?:([NSEWOnsewo])\s*°?\s*)?    # optionale Prefix-Direction
        ([+-]?\d+(?:[.,]\d+)?)
        \s*°?\s*
        ([NSEWOnsewo])?                # optionale Suffix-Direction
        (?=$|[\s,;&?#/])               # gefolgt von Ende/Separator, nicht DMS-Fortsetzung
    """,
    re.IGNORECASE | re.VERBOSE,
)
_LON_LABELED_VALUE = re.compile(
    r"""\b(?:longitudine|longitude|longitudinal|long|lon|lng|laengengrad|laenge|längengrad|länge|mlon)
        (?![A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ])
        \.?\s*[:=]?\s*
        (?:([NSEWOnsewo])\s*°?\s*)?
        ([+-]?\d+(?:[.,]\d+)?)
        \s*°?\s*
        ([NSEWOnsewo])?
        (?=$|[\s,;&?#/])
    """,
    re.IGNORECASE | re.VERBOSE,
)
_LABELED_SENTINEL: tuple[float, float] = (float("nan"), float("nan"))
# Vollnamen der Himmelsrichtungen (DE/EN/FR/IT/ES) werden vor dem Pattern-Matching
# auf die Ein-Buchstaben-Form reduziert, mit der _DMS/_DECIMAL_PAIR/_PREFIX_PAIR
# arbeitet. Verbreitet in GPS-Logs/Foto-Captions: ``"North 46.5, East 7.5"``,
# ``"Nord 46.5°, Ost 7.5°"``, ``"Norden 46.5 Osten 7.5"``.
# DE-Vollformen mit -en-Suffix (``Norden``/``Sueden``/``Osten``/``Westen``)
# sind im Sammler-Sprachgebrauch ueblich; ``Sued`` bleibt mit Umlaut-Normalisierung.
#
# FR-/IT-Zusatz (Suisse romande / Ticino / Val d'Aosta) - ``nord`` und ``sud``
# sind bereits identisch zur DE-Schreibweise durch die bestehenden Alternativen
# ``nord(?:en)?`` / ``s[uü]d(?:en)?`` mit-abgedeckt (die DE ``-en``-Suffixe sind
# optional, sodass die nackten FR/IT-Formen ``nord``/``sud`` matchen); neu sind
# nur die Ost-/West-Achsen, die in FR/IT eigene Wortstaemme haben: FR ``est``/
# ``ouest``, IT ``est``/``ovest``. Bisher fielen alle Formen still auf die
# Fallback-Route (kein Direction-Marker erkannt, generische Zahl-Paar-Extraktion
# nimmt die Reihenfolge ohne Vorzeichen-Information), was aus einem typischen
# Val-d'Aosta-Etikett ``"Nord 46.5, Est 7.5"`` oder einer Chamonix-Foto-Caption
# ``"Sud 46.5, Ouest 7.5"`` silente Vorzeichen-/Achsen-Verluste erzeugte -
# spiegelt die IT-/FR-Monats-/Saison-Namen-Erweiterungen in :data:`_MONTH_NAMES`
# und :data:`_SEASON_MONTHS`. Kollisions-Schutz durch die ``\b``-Wortgrenzen:
# ``est`` matcht nicht in ``test``/``best``/``estimated``/``established`` (der
# vorangehende Buchstabe ist Wort-Zeichen, keine Wort-Grenze); ``ouest``/``ovest``
# haben keine gemeinsamen Praefixe mit DE/EN-Direction-Namen (``ost`` beginnt mit
# ``o``, aber die Alternation ``ost(?:en)?`` scheitert auf Position 1 an ``u``
# bzw. ``v`` bei ``ouest``/``ovest`` und die spezifischere Alternative gewinnt).
#
# ES-Zusatz (Andalusien / Sierra Almagrera / Rodalquilar / Riotinto / Cartagena
# und weitere spanischsprachige Fundregionen; ebenso lateinamerikanische Sammler-
# Notizen aus Mexiko/Chile/Peru/Bolivien). Neu sind alle vier Achsen mit ES-
# eigenstaendigen Wortstaemmen: ``norte`` (N), ``sur`` (S), ``este`` (E),
# ``oeste`` (W). Bisher fielen alle ES-Formen still auf die Fallback-Route,
# sodass ein Sammler-Fund bei ``"Sur 37.2, Oeste 2.4"`` (Suedhalbkugel, West-
# halbkugel) als ``(37.2, 2.4)`` (Nord-, Osthalbkugel) in die DB kam. Spiegelt
# die ES-Monats-/Saison-Namen-Erweiterungen in :data:`_MONTH_NAMES` (enero..
# diciembre) und :data:`_SEASON_MONTHS` (primavera/verano/otono/invierno) auf
# die Direction-Wort-Achse. Kollisions-Schutz durch die ``\b``-Wortgrenzen:
# ``norte`` matcht nicht in ``norteafricano``/``norteamericano`` (der folgende
# Buchstabe ist Wort-Zeichen, keine Wort-Grenze); ``este`` matcht nicht in
# ``esteban``/``estepa``/``esteem``/``ester`` (dito), ``sur`` matcht nicht in
# ``sursee``/``surface``/``sursaturation`` (dito), ``oeste`` matcht nicht in
# ``oesten``/``oestrogen`` (dito). Die ES-``este``-Alternative kollidiert nicht
# mit der FR-/IT-``est``-Alternative aus dem vorigen Block: bei Eingabe ``este``
# scheitert ``est`` an der Wort-Grenze nach dem ``t`` (nachfolgendes ``e`` ist
# Wort-Zeichen), sodass die ``este``-Alternative uebernimmt.
_DIRECTION_WORD = re.compile(
    r"\b(?:"
    r"north|south|east|west"
    r"|nord(?:en)?|sued(?:en)?|s[uü]d(?:en)?|ost(?:en)?|west(?:en)?"
    r"|ouest|ovest|est"
    r"|norte|sur|oeste|este"
    r")\b\.?",
    re.IGNORECASE,
)
_DIRECTION_LETTER: dict[str, str] = {
    "n": "N", "north": "N", "nord": "N", "norden": "N", "norte": "N",
    "s": "S", "south": "S",
    # ``sud`` (ohne ``e``/Umlaut) ist die nackte FR-/IT-Schreibweise (Suisse
    # romande, Ticino, Val d'Aosta) und die englisch-nahe Kompaktform, die auch
    # in gemischt-sprachigen Sammler-Notizen und in Excel-CSV-Exporten aus
    # rein-ASCII-Datenbanken (kein Umlaut, kein ``e``-Ersatz) auftaucht. Das
    # bestehende ``_DIRECTION_WORD``-Pattern ``s[uü]d(?:en)?`` matcht die bare
    # Form (``u``-Alternante der ``[uü]``-Klasse) - der Lookup-Schluessel fehlte
    # aber, sodass ``m.group(0).rstrip(".").lower()`` = ``"sud"`` auf die Default-
    # Rueckgabe (Original-Wort) fiel und der bare FR-/IT-``Sud``-Wortstamm nicht
    # zur ``S``-Direction-Letter reduziert wurde. Silenter Vorzeichen-Verlust
    # aller FR-/IT-Foto-Captions/GPS-Logs mit bare ``Sud``-Praefix.
    "sued": "S", "sueden": "S", "süd": "S", "süden": "S", "sud": "S",
    # ``sur`` ist die ES-Vollform fuer Sued (Andalusien/Lateinamerika-Sammler-
    # Notizen). Kein Konflikt mit anderen Sprachen: DE ``sued``, FR/IT ``sud``,
    # EN ``south`` haben abweichende Wortstaemme.
    "sur": "S",
    "e": "E", "east": "E", "est": "E",
    # ``este`` ist die ES-Vollform fuer Ost (spiegelt die ES-``sur``-Erweiterung
    # auf die Ost-Achse). Der Lookup-Schluessel ist noetig, weil das bestehende
    # ``est``-Pattern (FR/IT) an der Wort-Grenze nach dem ``t`` scheitert und
    # deshalb die ES-``este``-Alternative im Regex uebernimmt.
    "este": "E",
    "o": "O", "ost": "O", "osten": "O",
    "w": "W", "west": "W", "westen": "W", "ouest": "W", "ovest": "W",
    # ``oeste`` ist die ES-Vollform fuer West (spiegelt die ES-``norte``/
    # ``sur``/``este``-Erweiterungen auf die West-Achse).
    "oeste": "W",
}


def _normalize_direction_words(text: str) -> str:
    """Reduziert Vollnamen der Himmelsrichtungen auf die Ein-Buchstaben-Form (N/S/E/W/O).

    DMS/_DECIMAL_PAIR/_PREFIX_PAIR erwarten Einzelbuchstaben; volle Worte aus
    Foto-Captions oder GPS-Logs ("North 46.5", "Nord 46.5°", "Osten 7.5") wuerden
    sonst nicht matchen. Eingaben ohne Vollnamen bleiben unveraendert.
    """
    def _replace(m: re.Match) -> str:
        key = m.group(0).rstrip(".").lower()
        return _DIRECTION_LETTER.get(key, m.group(0))
    return _DIRECTION_WORD.sub(_replace, text)


def _extract_labeled_lat_lon(s: str) -> tuple[float, float] | None | tuple:
    """Extrahiert (lat, lon), wenn *beide* Achsen (lat- und lon-Familie) explizit
    im Freitext markiert sind. Deckt reversed-Order (Lon vor Lat) korrekt ab.

    Drei-Wege-Rueckgabe zur Abgrenzung "kein Label-Match" (Fall-Through) von
    "Label-Match aber Out-of-Range" (definitives None):

      - ``(lat, lon)`` bei erfolgreicher Extraktion beider Achsen (nach
        :func:`_validate`-Range-Pruefung),
      - ``None`` wenn *beide* Labels erkannt wurden, das Ergebnis aber die
        Range-Pruefung nicht besteht - definitiver Reject, kein Fall-Through
        auf die label-lose _DECIMAL_PAIR-Route (sonst wuerde ``lon=50&lat=100``
        die publizierte Achsen-Zuordnung verwerfen und ``(50, 100)`` via
        label-stripped _DECIMAL_PAIR liefern),
      - :data:`_LABELED_SENTINEL` (NaN-Marker) wenn *nicht* beide Achsen
        erkannt wurden - der Caller behandelt das als "kein Match" und faellt
        auf die generische _COORD_LABEL-Strip-Route durch.

    Direction-Buchstaben (falls vorhanden) werden ueber :func:`_orient`
    ausgewertet, damit ein Sammler-Tippfehler ``Lat: E7.5, Lon: N46.5`` (Labels
    vertauscht, Direction korrekt) korrekt aufgeloest wird - die Direction-
    Semantik gewinnt gegenueber der Label-Semantik, weil sie explizit die
    Achse benennt.
    """
    lat_m = _LAT_LABELED_VALUE.search(s)
    if lat_m is None:
        return _LABELED_SENTINEL
    lon_m = _LON_LABELED_VALUE.search(s)
    if lon_m is None:
        return _LABELED_SENTINEL
    lat_dir = lat_m.group(1) or lat_m.group(3)
    lon_dir = lon_m.group(1) or lon_m.group(3)
    lat_val = _to_float(lat_m.group(2)) * _sign(lat_dir)
    lon_val = _to_float(lon_m.group(2)) * _sign(lon_dir)
    lat, lon = _orient(lat_val, lat_dir, lon_val, lon_dir)
    return _validate(lat, lon)


_TYPOGRAPHIC_DASH_BETWEEN_DIGITS = re.compile(
    r"(?<=\d)[–—](?=\d)"                                  # 13–06 / 06–2024
    r"|(?<=\d)[–—](?=[A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ])"                     # 13–June, 13–Juni (Oracle-Log)
    r"|(?<=[A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœ])[–—](?=\d)"                     # June–2024, JAN–2024 (Oracle-Log)
)


def parse_iso_date(text) -> str | None:
    """Konvertiert verschiedene Datumsschreibweisen in ISO YYYY-MM-DD.

    Unterstützt: YYYY-MM-DD, DD.MM.YYYY, YYYY/MM/DD, YYYY-MM (→ -01),
    reine Jahresangaben YYYY (→ -01-01). Gibt None für leere/ungueltige Werte.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s or s.lower() in DATE_NO_DATA_MARKERS:
        return None
    # Typografischer En-Dash (U+2013) / Em-Dash (U+2014) ZWISCHEN Ziffern auf
    # ASCII-Hyphen normalisieren. Word/Outlook/LibreOffice-AutoFormat, PDF-
    # Text-Extraktion und viele Office-Autokorrektur-Ketten wandeln ASCII-
    # Hyphen in Zahl-Kombinationen automatisch in typografische Dashes um
    # (Excel-Autoformat, Word-Standard-Autoformat, LaTeX-Textrender ``--`` ->
    # ``–``, PDF-Copy-Extraktion aus formatierten Vorlagen). Aus dem typischen
    # Sammler-Workflow "Fund-Datum in Word/Outlook-Notiz getippt (13-06-2024)
    # wird Autoformat-konvertiert zu 13–06–2024, dann in die Sammlung kopiert"
    # entstand damit silenter Funddatum-Datenverlust bei der Migration - die
    # strptime-Loops in :data:`_DATE_FORMATS` verlangen ASCII-Hyphen (``%d-%m-%Y``
    # matcht nur ``13-06-2024``, nicht ``13–06–2024``), und die uebrigen
    # Named-Pattern-Regexes ohne Range-Semantik akzeptieren typografische Dashes
    # nur in ihren dedizierten Range-Klassen (:data:`_YEAR_RANGE` etc.).
    #
    # Sicherheitsschranke: nur den Bereich ZWISCHEN zwei Ziffern normalisieren
    # (via ``(?<=\\d)[–—](?=\\d)``). Whitespace-getrennte Dashes (``2020 – 2024``
    # als Jahr-Range mit Print-Konvention "Whitespace um en-dash") bleiben
    # unangetastet, weil die Range-Semantik in :data:`_YEAR_RANGE` /
    # :data:`_YEAR_RANGE_BETWEEN` etc. die Dashes bereits explizit als Trenner
    # akzeptiert - dort ist die Whitespace-Bindung Teil der Range-Konvention
    # ("Fund 2020–2024" = "Fund in einem Jahr zwischen 2020 und 2024", nicht
    # "Fund am 2020. Tag/Monat/Jahr im 2024"). Dashe an Wort-Grenzen bleiben
    # ebenfalls unangetastet (nur direkt zwischen Ziffern greift die Normalis-
    # ierung). Kein-Whitespace-Range wie ``2020–2024`` wird durch die Regel
    # zwar auf ``2020-2024`` normalisiert, matcht dann aber die identische
    # :data:`_YEAR_RANGE`-Alternante ``[-–—−/]`` und liefert dasselbe Ergebnis -
    # kollisionsfrei durch die Symmetrie der Range-Klasse.
    s = _TYPOGRAPHIC_DASH_BETWEEN_DIGITS.sub("-", s)
    # Umschliessende Klammern/Anfuehrungszeichen abstreifen ("(2024)", '"2024-06-13"').
    # Strip + Rekursion; tiefere Schachtelung loest sich automatisch auf.
    for op, cl in _BRACKET_PAIRS:
        if len(s) >= len(op) + len(cl) and s.startswith(op) and s.endswith(cl):
            inner = s[len(op):-len(cl)].strip()
            if inner and inner != s:
                return parse_iso_date(inner)
    # Annaeherungspraefix abstreifen ("ca. 1985" → "1985", "circa Juni 2024" → "Juni 2024").
    # Genau einmal anwenden; die Rekursion uebernimmt das eigentliche Parsing.
    if _APPROX_PREFIX.match(s):
        rest = _APPROX_PREFIX.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_iso_date(rest)
        return None
    # Wochentag-Praefix abstreifen ("Mo 13.06.2024" → "13.06.2024"). Wird vor den
    # uebrigen Patterns geprueft, damit "Donnerstag, 13. Juni 2024" nicht erst
    # als _DAY_MONTH_YEAR mit "Donnerstag" als Monat versucht wird.
    if _WEEKDAY_PREFIX.match(s):
        rest = _WEEKDAY_PREFIX.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_iso_date(rest)
        return None
    # Temporale Praeposition abstreifen ("im Juni 2024" → "Juni 2024", "vom
    # 13.06.2024" → "13.06.2024", "im Jahr 1985" → "1985", "Jahr 1985" → "1985").
    # Nach Wochentag-Strip, damit "Donnerstag, im Juni 2024" zuerst den Wochentag
    # und dann die Praeposition aufloest. Strip + Rekursion analog _APPROX_PREFIX:
    # die Praeposition ist Satz-Gluekel, keine Datums-Modifikation - das ISO-
    # Datum-Output bleibt identisch zur reinen Datums-Form.
    if _TEMPORAL_PREFIX.match(s):
        rest = _TEMPORAL_PREFIX.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_iso_date(rest)
        return None
    # Leading Aera-Marker abstreifen ("AD 1985" → "1985", "n. Chr. 1985"
    # → "1985", "nach Christus 1985" → "1985", "BCE 500" → "500", "vor
    # Christus 1985" → "1985"). Spiegelt _TRAILING_ERA_MARKER auf die
    # Praefix-Achse (Anno-Domini-Grammatik, englische Auktions-Kataloge,
    # akademische Referenzen). Vor _BOUNDARY_PREFIX einsortiert, weil die
    # Formen "vor Christus 1985" und "nach Christus 1985" mit "vor"/"nach"
    # beginnen und sonst nur die reine Praeposition strippen wuerden -
    # _LEADING_ERA_MARKER verlangt das obligatorische "christus"/"chr"
    # nach "vor"/"nach", sodass reines "vor 1985"/"nach 1985" ohne
    # Christus-Marker unveraendert von _BOUNDARY_PREFIX gefangen wird
    # (kein Konflikt, Reihenfolge ist Spezifisches-vor-Allgemeinem). Strip
    # + Rekursion analog _APPROX_PREFIX: die Aera-Angabe ist semantische
    # Wert-Anmerkung, keine Datums-Modifikation. BC/BCE/v. Chr. faellt
    # nach Strip transparent durch die 1800..2999-Range-Pruefung auf None,
    # konsistent mit der Trailing-Form.
    if _LEADING_ERA_MARKER.match(s):
        rest = _LEADING_ERA_MARKER.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_iso_date(rest)
        return None
    # Boundary-/Richtungs-Praefix abstreifen ("vor 1985" → "1985", "nach Juni
    # 2024" → "Juni 2024", "pre-1985" → "1985", "before 1985" → "1985"). Nach
    # Temporal-Praefix einsortiert, damit "im vor 1985" (semantisch redundant,
    # aber unschaedlich) erst die Praeposition und dann die Richtungsangabe
    # strippt. Strip + Rekursion analog _APPROX_PREFIX: die Richtungsangabe
    # ist semantische Wert-Anmerkung ("Grenzwert", "ungefaehre Ober-/Unter-
    # grenze"), keine Datums-Modifikation - das ISO-Datum-Output ist identisch
    # zur reinen Form, die Richtung bleibt im Freitext (notizen).
    if _BOUNDARY_PREFIX.match(s):
        rest = _BOUNDARY_PREFIX.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_iso_date(rest)
        return None
    # Unidirektionalen Range-Praefix abstreifen ("ab 1985" → "1985", "seit
    # Juni 2024" → "Juni 2024", "bis 1985" → "1985", "from 2024" → "2024").
    # Nach _BOUNDARY_PREFIX einsortiert, weil semantisch verwandt aber
    # konzeptionell unterschiedlich (bilateral vs. unidirektional). Strip +
    # Rekursion analog _APPROX_PREFIX/_BOUNDARY_PREFIX: das Jahr ist der
    # bekannte Anker, die Richtung (ab/seit/bis) bleibt im Freitext (notizen).
    if _RANGE_PREFIX.match(s):
        rest = _RANGE_PREFIX.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_iso_date(rest)
        return None
    # "zwischen X und Y" / "between X and Y"-Wrapper auf beliebige Range-
    # Inhalte generalisieren - normalisiere auf ``X - Y`` und rekursiv
    # parsen, sodass die bestehenden Range-Patterns (Monat/Tag/Saison/
    # Dekade/Jahrhundert) transparent greifen (siehe :data:`_BETWEEN_AND_
    # WRAPPER` fuer Details zur Konvention und zum Preprocessor-Reihenfolge-
    # Argument). Der spezialisierte :data:`_YEAR_RANGE_BETWEEN`-Zweig unten
    # bleibt als kurzer Direkt-Pfad fuer die reine Jahres-Spanne bestehen
    # und wird durch diesen Preprocessor nicht ueberholt (semantisch
    # identisches Ergebnis, bei "zwischen 1985 und 1990" landet man in
    # beiden Faellen auf 1985-01-01).
    m = _BETWEEN_AND_WRAPPER.match(s)
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        if left and right:
            return parse_iso_date(f"{left} - {right}")
        return None
    m = _YEAR_ONLY.match(s)
    if m:
        year = int(m.group(1))
        if 1800 <= year <= 2999:
            return f"{year:04d}-01-01"
        return None
    # Dekaden-Spanne ("1980er-1990er", "1980s to 1990s", "1980er - 1990er",
    # "1980er/1990er"). Vor _DECADE geprueft, damit die Spanne-Form (die
    # strukturell ein einzelnes Dekaden-Pattern enthaelt) nicht vom base
    # _DECADE-Pattern geblockt wird. Konvention identisch zu _YEAR_RANGE /
    # _YEAR_RANGE_WORD: Startjahr der linken Dekade als ISO-Datum (spiegelt
    # _DECADE 1980er -> 1980-01-01). Inverted Spanne ("1990er-1980er",
    # Tippfehler) liefert das erste Jahrzehnt.
    m = _DECADE_RANGE.match(s)
    if m:
        year_start, year_end = int(m.group(1)), int(m.group(2))
        if 1800 <= year_start <= 2999 and 1800 <= year_end <= 2999:
            return f"{year_start:04d}-01-01"
        return None
    # Jahrzehnt-Notation ("1980er", "1980s") → Dekaden-Startjahr. Vor _YEAR_MONTH
    # ist nicht noetig (das Match endet auf 'er'/'s'), aber vor allen anderen
    # Pattern-Versuchen, damit '1980er' nicht erst als Year-Month versucht wird.
    m = _DECADE.match(s)
    if m:
        year = int(m.group(1))
        if 1800 <= year <= 2999:
            return f"{year:04d}-01-01"
        return None
    # Relative Position innerhalb eines Jahrhunderts ("Anfang 19. Jahrhundert",
    # "Mitte 20. Jahrhundert", "Ende 19. Jhdt.", "early 19th century",
    # "mid-19th century", "late 20th c."). Vor dem base _CENTURY_* geprueft,
    # damit die Praefix-Form ("Anfang 19. Jahrhundert") nicht durch das base
    # Century-Pattern versucht wird (kein Match wegen "Anfang", aber die
    # explizite Reihenfolge macht das Verhalten lesbarer). Konvention analog
    # _RELATIVE_DECADE: Anfang/early → 0, Mitte/mid → 50, Ende/late → 99 als
    # Offset innerhalb des Jahrhunderts. "Ende 19. Jahrhundert" → 1899-01-01.
    m = _RELATIVE_CENTURY_DE.match(s) or _RELATIVE_CENTURY_EN.match(s)
    if m:
        offset = _RELATIVE_CENTURY_OFFSETS[m.group(1).lower()]
        century = int(m.group(2))
        year = (century - 1) * 100 + offset
        if 1800 <= year <= 2999:
            return f"{year:04d}-01-01"
        return None
    # Relative Roemisch-Jahrhundert-Notation ("Mitte XIX. Jahrhundert",
    # "late XIX century", "Anfang XX. Jhdt."). Spiegelt _RELATIVE_CENTURY_DE/_EN
    # auf die Roemisch-Achse - dieselben Offset-Konventionen (Anfang/early -> 0,
    # Mitte/mid -> 50, Ende/late -> 99) auf ein Roemisch-adressiertes Jahrhundert.
    # Vor der non-relative Roemisch-Century-Form geprueft, damit die Praefix-
    # Form nicht durch das base Roman-Century-Pattern versucht wird. Nicht-
    # kanonische Roemisch-Tokens (nicht im :data:`_ROMAN_CENTURY_VALUES`-Map)
    # fallen auf None.
    m = _RELATIVE_CENTURY_ROMAN_DE.match(s) or _RELATIVE_CENTURY_ROMAN_EN.match(s)
    if m:
        offset = _RELATIVE_CENTURY_OFFSETS[m.group(1).lower()]
        century = _ROMAN_CENTURY_VALUES.get(m.group(2).upper())
        if century is not None:
            year = (century - 1) * 100 + offset
            if 1800 <= year <= 2999:
                return f"{year:04d}-01-01"
        return None
    # Jahrhundert-Spanne ("19.-20. Jahrhundert", "19th to 20th century",
    # "XIX.-XX. Jahrhundert"). Vor _CENTURY_* geprueft, damit die Spanne-Form
    # (die strukturell ein einzelnes Jahrhundert-Pattern enthaelt) nicht vom
    # base _CENTURY_*-Pattern via \$-Anker geblockt wird. Konvention identisch
    # zu _YEAR_RANGE / _DECADE_RANGE / _CENTURY_*: Startjahr des linken
    # Jahrhunderts als ISO-Datum. Inverted Spanne ("20.-19. Jhdt.", Tippfehler)
    # liefert das linke Jahrhundert.
    m = _CENTURY_RANGE_DE.match(s) or _CENTURY_RANGE_EN.match(s)
    if m:
        century_start, century_end = int(m.group(1)), int(m.group(2))
        year_start = (century_start - 1) * 100
        year_end = (century_end - 1) * 100
        if 1800 <= year_start <= 2999 and 1800 <= year_end <= 2999:
            return f"{year_start:04d}-01-01"
        return None
    # Roemisch-Jahrhundert-Spanne ("XIX.-XX. Jahrhundert", "XIX to XX century").
    # Spiegelt _CENTURY_RANGE_DE/_EN auf die Roemisch-Achse - Museums-Etiketten
    # mit gemischter Roemisch-Notation aus geerbten europaeischen Sammlungen.
    # Non-kanonische Roemisch-Tokens (nicht im :data:`_ROMAN_CENTURY_VALUES`-
    # Map) fallen auf None.
    m = _CENTURY_RANGE_ROMAN_DE.match(s) or _CENTURY_RANGE_ROMAN_EN.match(s)
    if m:
        century_start = _ROMAN_CENTURY_VALUES.get(m.group(1).upper())
        century_end = _ROMAN_CENTURY_VALUES.get(m.group(2).upper())
        if century_start is not None and century_end is not None:
            year_start = (century_start - 1) * 100
            year_end = (century_end - 1) * 100
            if 1800 <= year_start <= 2999 and 1800 <= year_end <= 2999:
                return f"{year_start:04d}-01-01"
        return None
    # Jahrhundert-Notation ("19. Jahrhundert", "19th century", "20. Jh."). Auf
    # das Jahrhundert-Startjahr abgebildet (Konvention analog Dekaden-Notation:
    # 19. Jahrhundert → 1800-01-01, spiegelt die "1980er → 1980-01-01"-Kette,
    # bei der das Label auf die "18xx"-Jahre zeigt). Vor _YEAR_ONLY spielt die
    # Reihenfolge keine Rolle (Jahrhundert-Pattern verlangt den Wort-Suffix
    # "Jahrhundert"/"century" o.ae., YEAR_ONLY nur eine 4-Ziffer-Zahl), aber
    # der Block wird direkt nach _DECADE gefuehrt, weil beide Notationen
    # semantisch zur Grob-Datierungs-Familie gehoeren (Dekade → Jahrhundert).
    m = _CENTURY_DE.match(s) or _CENTURY_EN.match(s)
    if m:
        century = int(m.group(1))
        year = (century - 1) * 100
        if 1800 <= year <= 2999:
            return f"{year:04d}-01-01"
        return None
    # Roemisch-Jahrhundert-Notation ("XIX. Jahrhundert", "XX. Jhdt.",
    # "XXI century"). Spiegelt _CENTURY_DE/_EN auf die Roemisch-Achse - traditio-
    # nelle Museums-Etiketten-Praxis, besonders in geerbten Sammlungen mit
    # europaeischer Provenienz. Konvention identisch zur Arabisch-Notation:
    # Jahrhundert-Startjahr (XIX -> 1800-01-01). Non-kanonische Roemisch-Tokens
    # fallen auf None (via :data:`_ROMAN_CENTURY_VALUES`-Lookup). Werte
    # ausserhalb des 1800..2999-Bandes (XVIII. Jhdt. -> 1700 < 1800) werden wie
    # bei der Arabisch-Notation zurueckgewiesen.
    m = _CENTURY_ROMAN_DE.match(s) or _CENTURY_ROMAN_EN.match(s)
    if m:
        century = _ROMAN_CENTURY_VALUES.get(m.group(1).upper())
        if century is not None:
            year = (century - 1) * 100
            if 1800 <= year <= 2999:
                return f"{year:04d}-01-01"
        return None
    # ISO 8601 Ordinal-Datum (Tag-des-Jahres): "2024-165" / "2024165" (compact 7 Ziffern).
    # Vor _YEAR_MONTH geprueft, damit "2024-001" nicht versucht wird als YYYY-MM zu
    # parsen (Monat 001 wuerde sowieso scheitern, aber die Reihenfolge ist klarer).
    # Die compact 8-Ziffer-Form (YYYYMMDD) wird weiter unten in _DATE_FORMATS abgefangen
    # und kollidiert nicht (7 vs 8 Ziffern).
    m = _ISO_ORDINAL_DATE.match(s)
    if m:
        year, day_of_year = int(m.group(1)), int(m.group(2))
        if 1800 <= year <= 2999 and 1 <= day_of_year <= 366:
            try:
                d = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
            except (OverflowError, ValueError):
                return None
            # Schaltjahres-Pruefung: Tag 366 nur gueltig, wenn der Tag im selben
            # Kalenderjahr bleibt (sonst wuerde Tag 366 in 2023 auf 2024-01-01 rutschen).
            if d.year == year:
                return d.isoformat()
            return None
    # Compact YYYYMM-Form (6 Ziffern, keine Trenner): "202406" -> 2024-06-01.
    # Vor dem _DATE_FORMATS-strptime-Loop einsortiert, damit die 6-Ziffer-
    # Eingabe hier eindeutig als YYYYMM interpretiert wird und NICHT vom
    # nachfolgenden %Y%m%d-Format greedy als YYYY-M-D (z.B. "202412" ->
    # "2024-01-02" statt "2024-12-01") fehlinterpretiert wird. Return None
    # bei ungueltigem Monat/Jahr blockiert den strptime-Loop (der die 6-Ziffer-
    # Eingabe sonst mit gefaehrlichem Greedy-%Y-Verhalten aufloesen wuerde).
    m = _COMPACT_YEAR_MONTH.match(s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
        return None
    # Mehrjahres-Spanne ("1950-1960", "1950–1960", "1950/1960"). Vor _YEAR_MONTH
    # geprueft, damit klar wird: zwei 4-Ziffer-Anker, nicht YYYY-MM mit grossem
    # Monat. Konvention: Startjahr als ISO-Datum (analog zu Dekaden 1980er →
    # 1980-01-01). Inverted Spanne ("1985-1980", Tippfehler) liefert das erste
    # Jahr (spiegelt parse_range-Verhalten auf die Jahres-Achse).
    m = _YEAR_RANGE.match(s)
    if m:
        year_start, year_end = int(m.group(1)), int(m.group(2))
        if 1800 <= year_start <= 2999 and 1800 <= year_end <= 2999:
            return f"{year_start:04d}-01-01"
        return None
    # Wort-Form der Mehrjahres-Spanne ("1950 bis 1960", "1950 to 1960").
    # Spiegelt _YEAR_RANGE auf die natuerliche Satz-Notation und folgt
    # exakt derselben Konvention (Startjahr als ISO-Datum).
    m = _YEAR_RANGE_WORD.match(s)
    if m:
        year_start, year_end = int(m.group(1)), int(m.group(2))
        if 1800 <= year_start <= 2999 and 1800 <= year_end <= 2999:
            return f"{year_start:04d}-01-01"
        return None
    # Umschliessende Range-Form ("zwischen 1985 und 1990", "between 1950 and
    # 1960"). Spiegelt _YEAR_RANGE_WORD auf die bilaterale Konjunktions-
    # Notation und folgt exakt derselben Konvention (Startjahr als ISO-Datum).
    m = _YEAR_RANGE_BETWEEN.match(s)
    if m:
        year_start, year_end = int(m.group(1)), int(m.group(2))
        if 1800 <= year_start <= 2999 and 1800 <= year_end <= 2999:
            return f"{year_start:04d}-01-01"
        return None
    m = _YEAR_MONTH.match(s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1800 <= year <= 2999 and 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-01"
        return None
    m = _ISO_DATETIME.match(s)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1800 <= year <= 2999:
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                return None
    # Zweistelliges Jahr in DE-Kompakt-Notation ("13.06.24", "1.6.24",
    # "13/06/24", "13-06-24") vor dem strptime-Loop aufloesen: die
    # :data:`_DATE_FORMATS`-Kette fuehrt bewusst kein ``%y``-Format, weil
    # Python-strptime einen fixen POSIX-Pivot 68/69 nutzt (00-68 -> 20YY,
    # 69-99 -> 19YY), der fuer eine Mineral-Sammlung ungeeignet ist -
    # ``13.06.68`` wuerde als 2068-06-13 gelesen (42 Jahre in der Zukunft
    # zur aktuellen Sammlungs-Domaene). Der Pivot 30 (00-30 -> 20YY,
    # 31-99 -> 19YY) spiegelt den sammler-typischen Datums-Kontext:
    # aktuelle Boersen-Kaeufe und geplante Foto-Sessions bis 2030 bleiben
    # im 21. Jhdt., alle YY >= 31 werden ins 20. Jhdt. mit den Sammlungs-
    # klassischen Boersen-Kaufjahren 1931-1999 gemappt. Kollisionsfrei zu
    # :data:`_YEAR_MONTH` (vier Ziffern erforderlich), :data:`_MONTH_NUMERIC_YEAR`
    # (vier Ziffern als Jahr), :data:`_YEAR_RANGE` (zwei 4-Ziffer-Anker) und
    # zu den 4-Ziffer-strptime-Formaten (``%Y`` verlangt vier Ziffern). Siehe
    # :data:`_DAY_MONTH_2Y` fuer Details zu Struktur-Guards und Separator-
    # Symmetrie.
    m = _DAY_MONTH_2Y.match(s)
    if m:
        day = int(m.group(1))
        month = int(m.group(3))
        yy = int(m.group(4))
        year = 2000 + yy if yy <= 30 else 1900 + yy
        if 1 <= day <= 31 and 1 <= month <= 12:
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                return None
        return None
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if 1800 <= d.year <= 2999:
            return d.isoformat()
        return None
    # Tages-Range innerhalb eines Monats mit Monatsname ("5.-7. Juni 2024",
    # "5-7 June 2024", "5. bis 7. Juni 2024") - Start-Tag als ISO-Datum, End-Tag
    # als semantische Wert-Anmerkung im Freitext. Spiegelt _YEAR_RANGE /
    # _MONTH_RANGE_YEAR auf die Tages-Achse. Vor _DAY_MONTH_YEAR geprueft, weil
    # die Range-Form spezifischer ist als die Einzel-Tag-Form (Patterns sind
    # durch den Range-Trenner + Zweit-Tag disjunkt; Reihenfolge fuer Klarheit).
    # Monatsname muss valide sein - sonst faellt der Match durch auf die uebrigen
    # Pattern.
    m = _DAY_RANGE_MONTH_YEAR.match(s)
    if m:
        day1 = int(m.group(1))
        day2 = int(m.group(2))
        month = _normalize_month_name(m.group(3))
        year = int(m.group(4))
        if month and 1 <= day1 <= 31 and 1 <= day2 <= 31 and 1800 <= year <= 2999:
            try:
                return datetime.date(year, month, day1).isoformat()
            except ValueError:
                return None
    # Englische Month-First-Tages-Range ("Feb 3 - Feb 8, 2024", "Feb 3-8, 2024",
    # "March 3 - April 5, 2024") - Start-Tag im ersten (oder einzigen) Monat als
    # ISO-Datum, End-Tag/End-Monat als semantische Wert-Anmerkung im Freitext.
    # Spiegelt :data:`_DAY_RANGE_MONTH_YEAR` auf die EN-Month-First-Reihenfolge
    # (siehe :data:`_ENGLISH_MONTH_DAY_RANGE` fuer Details zur Konvention und
    # Kollisions-Analyse).
    m = _ENGLISH_MONTH_DAY_RANGE.match(s)
    if m:
        month1 = _normalize_month_name(m.group(1))
        day1 = int(m.group(2))
        month2_raw = m.group(3)
        month2 = _normalize_month_name(month2_raw) if month2_raw else month1
        day2 = int(m.group(4))
        year = int(m.group(5))
        if (month1 and month2 and 1 <= day1 <= 31 and 1 <= day2 <= 31
                and 1800 <= year <= 2999):
            try:
                return datetime.date(year, month1, day1).isoformat()
            except ValueError:
                return None
    # Tages-Range mit numerischem Monat ("13.-15.06.2024", "13. bis 15.06.2024",
    # "13-15.06.2024"). Spiegelt _DAY_RANGE_MONTH_YEAR auf die numerische Monat-
    # Achse - Start-Tag zaehlt als ISO-Datum. Vor der generischen _DATE_FORMATS-
    # Kette und vor _DAY_MONTH_YEAR-artigen Einzel-Tag-Formen bereits ausgefuehrt
    # (der Range-Bindestrich zwischen den beiden Tagen wuerde die _DATE_FORMATS-
    # strptime-Matches ohnehin blockieren, hier ist der Match aber sofort
    # aufloesbar). Range-Semantik: der End-Tag wird bewusst nicht in die ISO-
    # Rueckgabe eingerechnet, weil das Fund-Datum in der Sammlungs-DB als
    # Einzel-Punkt gespeichert wird.
    m = _DAY_RANGE_NUMERIC_MONTH_YEAR.match(s)
    if m:
        day1 = int(m.group(1))
        day2 = int(m.group(2))
        month = int(m.group(3))
        year = int(m.group(4))
        if (1 <= day1 <= 31 and 1 <= day2 <= 31
                and 1 <= month <= 12 and 1800 <= year <= 2999):
            try:
                return datetime.date(year, month, day1).isoformat()
            except ValueError:
                return None
    # Voll-Datum-Range im DE-Format ("13.06.-15.06.2024" mit fehlendem ersten
    # Jahr, "13.06.2024-15.07.2024" voll qualifiziert). Beide Datums-Felder
    # muessen strukturell aus der ``DD.MM.[YYYY]``-Vorlage stammen; wenn das
    # erste Datum kein Jahr traegt, wird das Jahr aus dem zweiten Datum
    # uebernommen (Sammler-Konvention "gleiches Jahr, End-Datum vollstaendig").
    # Range-Semantik: der Range-Start liefert das ISO-Datum, das End-Datum
    # wird nicht in die Rueckgabe eingerechnet.
    m = _FULL_DATE_RANGE_DE.match(s)
    if m:
        day1 = int(m.group(1))
        month1 = int(m.group(2))
        year1 = int(m.group(3)) if m.group(3) else int(m.group(6))
        if (1 <= day1 <= 31 and 1 <= month1 <= 12
                and 1800 <= year1 <= 2999):
            try:
                return datetime.date(year1, month1, day1).isoformat()
            except ValueError:
                return None
    # ISO-Datum-Range ("2024-06-13/2024-06-15", "2024-06-13 - 2024-06-15",
    # "2024-06-13 bis 2024-06-15", "2024-06-13–2024-06-15"). Der Range-Start
    # liefert das ISO-Datum, das End-Datum wird nicht in die Rueckgabe
    # eingerechnet.
    m = _ISO_DATE_RANGE.match(s)
    if m:
        year1 = int(m.group(1))
        month1 = int(m.group(2))
        day1 = int(m.group(3))
        if (1 <= day1 <= 31 and 1 <= month1 <= 12
                and 1800 <= year1 <= 2999):
            try:
                return datetime.date(year1, month1, day1).isoformat()
            except ValueError:
                return None
    # Relative Position innerhalb eines Monats mit Monatsname + Jahr
    # ("Anfang Juni 2024", "Mitte Juni 2024", "Ende Juni 2024", "early June 2024",
    # "mid-June 2024", "late June 2024"). Vor _DAY_MONTH_YEAR / _ENGLISH_MONTH_DAY_YEAR
    # / _MONTH_YEAR geprueft, weil die Positions-Praefix-Form strukturell disjunkt
    # zu allen dreien ist (Positions-Wort statt Ziffer/Monatsname-first) und die
    # explizite Reihenfolge das Verhalten lesbarer macht. Konvention: Anfang/early
    # -> Tag 1, Mitte/mid -> Tag 15, Ende/late -> letzter Tag des Monats (28-31,
    # Schaltjahr-korrekt via datetime-Arithmetik).
    m = _RELATIVE_MONTH_YEAR.match(s)
    if m:
        position = m.group(1).lower()
        month = _normalize_month_name(m.group(2))
        year = int(m.group(3))
        if month and 1800 <= year <= 2999:
            if position in ("anfang", "early"):
                day = 1
            elif position in ("mitte", "mid"):
                day = 15
            else:  # ende / late
                if month == 12:
                    day = 31
                else:
                    day = (datetime.date(year, month + 1, 1)
                           - datetime.timedelta(days=1)).day
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                return None
    # Englische "day of month" Ordinal-Form ("the 4th of July 2019",
    # "15th of June 2020"). Vor :data:`_DAY_MONTH_YEAR` geprueft, weil das
    # obligatorische Wort "of" die Struktur spezifischer macht (kein anderes
    # Datums-Pattern kennt "of" als Trenner). Ordinal-Suffix optional, Artikel-
    # Praefix "the" optional, Komma vor Jahr optional - deckt beide EN-Register
    # (Prosa-Feiertags-Notation "the 4th of July" und Kompakt-Notiz
    # "15 of June 2020") ab. Monatsname wird ueber :func:`_normalize_month_name`
    # validiert; ungueltiger Name (z.B. "the 4th of Foo 2019") faellt durch
    # auf die restlichen Pattern.
    m = _DAY_OF_MONTH_YEAR.match(s)
    if m:
        day = int(m.group(1))
        month = _normalize_month_name(m.group(2))
        year = int(m.group(3))
        if month and 1 <= day <= 31 and 1800 <= year <= 2999:
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                return None
    # Deutsche Monatsnamen ("13. Juni 2024", "Juni 2024")
    m = _DAY_MONTH_YEAR.match(s)
    if m:
        day = int(m.group(1))
        month = _normalize_month_name(m.group(2))
        year = int(m.group(3))
        if month and 1 <= day <= 31 and 1800 <= year <= 2999:
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                return None
    # Englische Reihenfolge "Jun 13, 2024" / "June 13 2024"
    m = _ENGLISH_MONTH_DAY_YEAR.match(s)
    if m:
        month = _normalize_month_name(m.group(1))
        day = int(m.group(2))
        year = int(m.group(3))
        if month and 1 <= day <= 31 and 1800 <= year <= 2999:
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                return None
    # Month-Range innerhalb eines Jahres ("Juni/Juli 2024", "Mai-Juni 1985",
    # "Juni bis Juli 2024") - Start-Monat als ISO-Datum, End-Monat als
    # semantische Wert-Anmerkung im Freitext. Spiegelt _YEAR_RANGE /
    # _YEAR_RANGE_WORD auf die Monats-Achse. Vor _MONTH_YEAR geprueft, weil die
    # 3-Teil-Form spezifischer ist als die 2-Teil-Form (Pattern sind durch den
    # Zweit-Monatsnamen und den $-Anker disjunkt; Reihenfolge nur fuer
    # Lesbarkeit). Beide Monats-Tokens muessen valide Monatsnamen sein - sonst
    # waere die Struktur mehrdeutig ("Juni/xxx 2024" darf nicht als "Juni 2024"
    # gelesen werden) und der Match faellt durch auf die restlichen Pattern.
    m = _MONTH_RANGE_YEAR.match(s)
    if m:
        month1 = _normalize_month_name(m.group(1))
        month2 = _normalize_month_name(m.group(2))
        year = int(m.group(3))
        if month1 and month2 and 1800 <= year <= 2999:
            return f"{year:04d}-{month1:02d}-01"
    m = _MONTH_YEAR.match(s)
    if m:
        month = _normalize_month_name(m.group(1))
        year = int(m.group(2))
        if month and 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Year-first DD-Monatsname-YYYY ("2024-Juni-13" / "2024 June 13"). Voll
    # qualifiziertes Datum mit ausgeschriebenem Monatsnamen in der ISO-aehnlichen
    # Year-First-Reihenfolge - spiegelt _DAY_MONTH_YEAR und
    # _ENGLISH_MONTH_DAY_YEAR. Vor _YEAR_MONTH_NAME geprueft, weil die 3-Teil-
    # Form spezifischer ist als die 2-Teil-Form (Pattern sind durch $-Anker
    # disjunkt, Reihenfolge nur fuer Lesbarkeit).
    m = _YEAR_MONTH_NAME_DAY.match(s)
    if m:
        year = int(m.group(1))
        month = _normalize_month_name(m.group(2))
        day = int(m.group(3))
        if month and 1 <= day <= 31 and 1800 <= year <= 2999:
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                return None
    # Year-first Monatsname + Jahr ("2024-Juni" / "2024 June" / "2024.Juni").
    # Spiegelt _MONTH_YEAR auf die Year-First-Reihenfolge - sortierbare Form mit
    # ausgeschriebenem Monat, wie sie in Excel-Auto-Fill und Listen-Headern
    # vorkommt. Konvention: Tag auf den 1. gesetzt (Monatsstart).
    m = _YEAR_MONTH_NAME.match(s)
    if m:
        year = int(m.group(1))
        month = _normalize_month_name(m.group(2))
        if month and 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # ISO 8601 Wochendatum ("2024-W25", "2024W25", "2024-W25-3"). Vor den
    # uebrigen YYYY-MM/YYYY-...-Mustern geprueft, damit das W eindeutig erkannt
    # wird und nicht erst gegen Monatsnamen versucht wird.
    m = _ISO_WEEK_DATE.match(s)
    if m:
        year, week = int(m.group(1)), int(m.group(2))
        day = int(m.group(3)) if m.group(3) else 1
        if 1800 <= year <= 2999 and 1 <= week <= 53:
            try:
                return datetime.date.fromisocalendar(year, week, day).isoformat()
            except ValueError:
                return None
    # Deutsche KW-Notation ("KW 25 2024", "KW25/2024", "Kalenderwoche 25 2024",
    # "Woche 25 2024", "CW 25 2024"). Mapping wie _ISO_WEEK_DATE.
    m = _KW_YEAR.match(s)
    if m:
        week, year = int(m.group(1)), int(m.group(2))
        if 1800 <= year <= 2999 and 1 <= week <= 53:
            try:
                return datetime.date.fromisocalendar(year, week, 1).isoformat()
            except ValueError:
                return None
    # Year-first KW-Notation ("2024 KW 25", "2024/KW25", "2024-Kalenderwoche 25",
    # "2024 CW 25"). Symmetrisch zur Year-Last-Form _KW_YEAR; kommt in
    # Sammlungs-Tagebuechern mit Jahr-zuerst-Sortierung ("2024 KW 25 -
    # Tucson-Boerse", Excel-Auto-Fill mit YYYY als sortierendem Praefix) vor.
    m = _KW_YEAR_FIRST.match(s)
    if m:
        year, week = int(m.group(1)), int(m.group(2))
        if 1800 <= year <= 2999 and 1 <= week <= 53:
            try:
                return datetime.date.fromisocalendar(year, week, 1).isoformat()
            except ValueError:
                return None
    # Numerisches Monat/Jahr ("06/2024", "6-2024"). Erst nach den DD.MM.YYYY-
    # Formaten geprueft, damit die nicht versehentlich auf MM/YYYY zurueckfallen.
    m = _MONTH_NUMERIC_YEAR.match(s)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Quartal + Jahr ("Q1 2024", "3. Quartal 1985"). Vor _SEASON_YEAR geprueft,
    # damit "Q1 2024" nicht versehentlich als Saison-Notation interpretiert wird.
    m = _QUARTER_SHORT.match(s)
    if m:
        q = int(m.group(1) or m.group(2))
        year = int(m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_QUARTER_MONTHS[q]:02d}-01"
    m = _QUARTER_LONG.match(s)
    if m:
        q = int(m.group(1) or m.group(2))
        year = int(m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_QUARTER_MONTHS[q]:02d}-01"
    # Year-first Quartals-Notation ("2024-Q1", "2024Q1", "2024 Q1"). Symmetrisch
    # zur Year-Last-Form _QUARTER_SHORT; kommt in Quartalsreports und
    # Excel-Auto-Format vor ("2024-Q1" sortiert lexikographisch korrekt).
    m = _QUARTER_YEAR_FIRST.match(s)
    if m:
        year = int(m.group(1))
        q = int(m.group(2) or m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_QUARTER_MONTHS[q]:02d}-01"
    # Year-first Langform-Quartal ("2024 1. Quartal", "2024 Quartal 1").
    # Symmetrisch zur Year-Last-Form _QUARTER_LONG; kommt in Geschaefts-
    # perioden-Reports und einigen Sammlungs-Tagebuechern vor.
    m = _QUARTER_LONG_YEAR_FIRST.match(s)
    if m:
        year = int(m.group(1))
        q = int(m.group(2) or m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_QUARTER_MONTHS[q]:02d}-01"
    # Halbjahres-Notation: spiegelt die Quartals-Block (Kurz-/Lang-/Year-First-
    # Varianten) auf die 6-Monats-Achse. Konvention: H1 → Januar (Halbjahres-
    # Startmonat), H2 → Juli. Verbreitet in Geschaeftsberichten ("H1 2024
    # Umsatz", "Halbjahresbericht 2024") und einigen Sammlungs-Tagebuechern
    # ("1. Halbjahr 2024 - Tucson-Boerse + Bergtour"). Vor _RELATIVE_YEAR
    # geprueft, weil dort u.a. "Anfang"/"Mitte"/"Ende" gepruefte werden und
    # "Halbjahr" lexikalisch zwar weit weg ist, aber zur konsistenten Block-
    # Reihenfolge passt.
    m = _HALFYEAR_SHORT.match(s)
    if m:
        h = int(m.group(1) or m.group(2))
        year = int(m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_HALFYEAR_MONTHS[h]:02d}-01"
    m = _HALFYEAR_LONG.match(s)
    if m:
        h = int(m.group(1) or m.group(2))
        year = int(m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_HALFYEAR_MONTHS[h]:02d}-01"
    m = _HALFYEAR_YEAR_FIRST.match(s)
    if m:
        year = int(m.group(1))
        h = int(m.group(2) or m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_HALFYEAR_MONTHS[h]:02d}-01"
    m = _HALFYEAR_LONG_YEAR_FIRST.match(s)
    if m:
        year = int(m.group(1))
        h = int(m.group(2) or m.group(3))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{_HALFYEAR_MONTHS[h]:02d}-01"
    # Relative Position innerhalb einer Dekade ("Anfang/Mitte/Ende 1980er",
    # "early/mid/late 1990s", "Mid-1980s"). Vor _RELATIVE_YEAR geprueft -
    # die Patterns sind disjunkt (Dekaden-Pattern verlangt er/s-Suffix), aber
    # die Reihenfolge bleibt vom Spezifischen zum Allgemeinen lesbarer.
    # Konvention: Anfang→Jahr 0 der Dekade, Mitte→Jahr 5, Ende→Jahr 9.
    m = _RELATIVE_DECADE.match(s)
    if m:
        offset = _relative_decade_offset(m.group(1))
        if offset is None:
            return None
        decade_anchor = int(m.group(2))
        if 1800 <= decade_anchor <= 2999:
            return f"{decade_anchor + offset:04d}-01-01"
        return None
    # Relative Jahresposition ("Anfang/Mitte/Ende 2024", "early/mid/late 2024",
    # "mid-2024"). Vor _SEASON_YEAR geprueft, damit die Schluesselwoerter nicht
    # erst als unbekannter Saison-Name auf None fallen.
    m = _RELATIVE_YEAR.match(s)
    if m:
        month = _RELATIVE_MONTHS[m.group(1).lower()]
        year = int(m.group(2))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Deutsche Kompositum-Form ("Jahresanfang 2024", "Jahresmitte 2024",
    # "Jahresende 2024", "Jahresbeginn 2020", "Jahresschluss 1985"). Semantisch
    # identisch zur artikellosen Kurzform "Anfang/Mitte/Ende <Jahr>", nach
    # _RELATIVE_YEAR geprueft (Kurzform hat als etabliertes Pattern Vorrang),
    # vor _SEASON_YEAR (sonst faellt die substantivierte Form ueber den
    # Fallback des unbekannten Saison-Namens auf None).
    m = _YEAR_COMPOUND_POSITION.match(s)
    if m:
        month = _YEAR_COMPOUND_POSITION_MONTHS[m.group(1).lower()]
        year = int(m.group(2))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Winter-Cross-Year-Notation ("Winter 2023/2024", "Winter 2023/24",
    # "Winter 1999-2000", "Winter 2023-24"). Vor _SEASON_YEAR geprueft, weil
    # die Doppel-Jahr-Form dem Basis-Pattern (nur eine 4-Ziffer-Zahl) strukturell
    # unbekannt ist und ohne Sonderpfad still auf None faellt. Konvention:
    # Dezember des ersten Jahres (spiegelt _SEASON_MONTHS["winter"] = 12);
    # semantische Konsistenz-Pruefung stellt sicher, dass das zweite Jahr
    # exakt das erste Jahr plus 1 ist (typische Winter-Saison-Semantik).
    m = _SEASON_CROSS_YEAR.match(s)
    if m:
        year_start = int(m.group(2))
        year_end_raw = m.group(3)
        if len(year_end_raw) == 2:
            year_end = (year_start // 100) * 100 + int(year_end_raw)
            if year_end <= year_start:
                year_end += 100
        else:
            year_end = int(year_end_raw)
        if 1800 <= year_start <= 2999 and year_end == year_start + 1:
            return f"{year_start:04d}-12-01"
        return None
    # Saison-Spanne ("Sommer bis Herbst 2024", "summer-fall 2024"). Vor
    # _SEASON_YEAR / _SEASON_YEAR_FIRST geprueft, damit die Spanne-Form (die
    # strukturell zwei Saison-Woerter enthaelt) nicht vom base _SEASON_YEAR-
    # Pattern geblockt wird. Konvention identisch zu _YEAR_RANGE /
    # _DECADE_RANGE / _CENTURY_RANGE_*: linke Saison als Anker (ihr Start-
    # monat plus Jahres-Zahl auf den 1. gesetzt). Unbekannte Wort-Paare (kein
    # Saison-Woerterbuch-Treffer) fallen still durch auf die naechsten Zweige.
    m = _SEASON_RANGE.match(s)
    if m:
        month_start = _normalize_season_name(m.group(1))
        month_end = _normalize_season_name(m.group(2))
        year = int(m.group(3))
        if month_start and month_end and 1800 <= year <= 2999:
            return f"{year:04d}-{month_start:02d}-01"
    # Jahreszeit + Jahr ("Sommer 1985", "Spring 2024"): meteorologischer
    # Saison-Start im genannten Jahr. Ueber denselben _MONTH_YEAR-Regex
    # gepatched, damit "Juni 2024" (Monat) Vorrang vor Seasons hat.
    m = _SEASON_YEAR.match(s)
    if m:
        month = _normalize_season_name(m.group(1))
        year = int(m.group(2))
        if month and 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Year-first Jahreszeit-Notation ("2024 Sommer", "1985-Winter", "2024/Herbst").
    # Symmetrisch zur Year-Last-Form _SEASON_YEAR; kommt in Sammlungs-Notizen,
    # Foto-Captions und Tagebuch-Eintraegen vor, die das Jahr als sortierenden
    # Praefix voranstellen (Excel-Auto-Fill, Ordner-Struktur "2024/Sommer/...").
    m = _SEASON_YEAR_FIRST.match(s)
    if m:
        year = int(m.group(1))
        month = _normalize_season_name(m.group(2))
        if month and 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Fixed-Date-Feiertag + Jahr ("Weihnachten 2023", "Silvester 2020",
    # "Neujahr 2024", "Halloween 2019"). Nach den Season-Zweigen einsortiert,
    # damit "Sommer 2024" / "Herbst 1985" zuerst als Saison behandelt werden
    # (der breitere Semantik-Anspruch), und der Feiertag-Zweig nur greift,
    # wenn der Name weder Monat noch Saison ist. Die Fall-Through-Semantik
    # der beiden vorherigen Zweige (Match ohne Return bei unbekanntem Namen)
    # macht die Reihenfolge korrektheits-unabhaengig, aber die "spezifisches-
    # vor-allgemeinerem"-Reihenfolge folgt der Konvention der uebrigen
    # Patterns. Multi-Wort-Namen ("Heilige Drei Koenige 2024", "Tag der
    # deutschen Einheit 2023") werden durch die Namen-Zeichenklasse
    # ``[A-Za-zÄÖÜäöüÀ-ÖØ-öø-ÿŒœß.’‘' \-]+?`` erfasst (non-greedy, keine Ziffern), die
    # Normalisierung in :func:`_normalize_holiday_name` mappt alle
    # Whitespace-/Umlaut-/Apostroph-Varianten auf denselben kanonischen
    # Einzel-Token-Key. Variable Feiertage (Ostern, Pfingsten, Muttertag,
    # Vatertag) sind bewusst NICHT in :data:`_HOLIDAY_MONTH_DAY` gelistet
    # und liefern hier weiterhin None (Fall-Through zum Rest der Kaskade).
    m = _HOLIDAY_YEAR.match(s)
    if m:
        name = m.group(1)
        year = int(m.group(2))
        if 1800 <= year <= 2999:
            hd = _normalize_holiday_name(name)
            if hd is not None:
                month, day = hd
                return f"{year:04d}-{month:02d}-{day:02d}"
            # Variable Feiertage (Osterzyklus): Ostersonntag jahresspezifisch
            # via Computus, dann Offset in Tagen aus :data:`_HOLIDAY_EASTER_OFFSET`.
            # Nach der Fixed-Date-Whitelist einsortiert, damit unbekannte Fixed-
            # Date-Namen weiterhin ohne Kollision auf None fallen; kein Feiertag
            # ist in beiden Dicts eingetragen (Karfreitag/Ostern/Pfingsten liegen
            # ausschliesslich in :data:`_HOLIDAY_EASTER_OFFSET`,
            # Weihnachten/Silvester/Halloween ausschliesslich in
            # :data:`_HOLIDAY_MONTH_DAY`), sodass die Reihenfolge korrektheits-
            # unabhaengig ist.
            iso = _variable_holiday_iso(name, year)
            if iso is not None:
                return iso
    # Year-first Feiertag-Notation ("2023 Weihnachten", "2020-Silvester").
    # Spiegelt _HOLIDAY_YEAR auf die Year-First-Reihenfolge, symmetrisch zu
    # :data:`_SEASON_YEAR_FIRST` / :data:`_QUARTER_YEAR_FIRST` gegenueber
    # ihren Year-Last-Basisformen. Nach _SEASON_YEAR_FIRST einsortiert
    # analog zur Year-Last-Reihenfolge.
    m = _HOLIDAY_YEAR_FIRST.match(s)
    if m:
        year = int(m.group(1))
        name = m.group(2)
        if 1800 <= year <= 2999:
            hd = _normalize_holiday_name(name)
            if hd is not None:
                month, day = hd
                return f"{year:04d}-{month:02d}-{day:02d}"
            iso = _variable_holiday_iso(name, year)
            if iso is not None:
                return iso
    # Trailing Aera-Marker abstreifen ("1985 n. Chr.", "500 v. Chr.", "1985 AD",
    # "1985 BCE"). Aera-Marker gehoert nicht zum Datum selbst; das Jahr bleibt
    # der bekannte Anker, die Zeitrechnungs-Konvention ist semantische Wert-
    # Anmerkung und keine Datums-Modifikation (analog _APPROX_PREFIX/
    # _BOUNDARY_PREFIX auf der Suffix-Achse). Vor _TRAILING_TIME einsortiert,
    # weil die Aera-Angabe eine mehr-Token-Wort-Marker-Form ist und nicht durch
    # die reine Zeit-/Klammer-/Punkt-Strip-Kaskade abgedeckt wird - ohne
    # explizite Aera-Behandlung fielen typische Museums-Etiketten mit
    # AD/BC/CE/n. Chr.-Suffix stille auf None (das trailing "." wuerde zwar
    # durch _TRAILING_PUNCT gestrippt, aber die verbliebene "1985 n Chr"
    # matcht keine der Struktur-Patterns). BC/v. Chr./BCE-Formen werden
    # akzeptiert und gestrippt, das resultierende Jahr wird dann durch die
    # 1800..2999-Range-Pruefung transparent auf None gefiltert (kein zusaetz-
    # licher BC-Sonderpfad noetig; spiegelt "500" -> None ohne Aera-Marker).
    stripped = _TRAILING_ERA_MARKER.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # Trailing Annaeherungs-Suffix abstreifen ("1985 ca.", "2020 circa",
    # "13.06.2024 vermutlich", "Juni 2020 ungefaehr", "1985 wahrscheinlich").
    # Spiegelt :data:`_APPROX_PREFIX` auf die Suffix-Achse (siehe dortiges
    # Kommentar-Block fuer die Wortliste). Nach _TRAILING_ERA_MARKER
    # einsortiert, weil "1985 AD ca." (Aera + Praezisions-Marker) zuerst
    # den Aera-Suffix aufloesen soll ("1985 ca." als Rest) und die Praezision
    # in der Rekursion faellt. Strip + Rekursion analog _TRAILING_ERA_MARKER:
    # der Praezisions-Marker ist semantische Wert-Anmerkung, keine Datums-
    # Modifikation.
    stripped = _TRAILING_APPROX_SUFFIX.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # Trailing "und folgende Jahre"-Suffix abstreifen ("1985 ff.", "1985 f.",
    # "1985ff", "Juni 2024 ff.", "13.06.2024 ff."). DE-Bibliografie-/Zitat-
    # Standard fuer offene Jahres-Spannen; semantisch aequivalent zu
    # :data:`_YEAR_RANGE` (Startjahr als ISO-Anker, "und folgende" bleibt im
    # Freitext). Nach :data:`_TRAILING_APPROX_SUFFIX` einsortiert, weil
    # kombinierte Formen wie "1985 ff. ca." zuerst den Praezisions-Marker
    # aufloesen sollen ("1985 ff." als Rest) und die "und folgende"-Marke
    # in der naechsten Rekursion faellt. Strip + Rekursion analog
    # :data:`_TRAILING_APPROX_SUFFIX`: der "und folgende"-Marker ist
    # semantische Wert-Anmerkung, keine Datums-Modifikation. Siehe
    # :data:`_TRAILING_FOLLOWING_SUFFIX` fuer die Kompakt-/Whitespace-
    # Positions-Klassen und die Kollisionsfreiheits-Analyse.
    stripped = _TRAILING_FOLLOWING_SUFFIX.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # DE-Uhrzeit-Trailing-Suffix "Uhr" abstreifen ("13.06.2024 14:30 Uhr",
    # "13. Juni 2024, 14 Uhr", "2024-06-13 14:30:00 Uhr."). Vor _TRAILING_TIME
    # einsortiert, weil der reine Colon-Zweig von _TRAILING_TIME zwar den
    # ``14:30``-Teil strippen wuerde, aber ``13.06.2024 Uhr`` uebrig liesse -
    # das Uhr-Wort matcht die case-sensitive [A-Z]{2,5}-Whitelist nur als
    # "UHR"-Grosschrift (unueblich), sodass die gemischt-case DE-Form still auf
    # None faellt. Diese Regex fangt beide Formen (Colon-Zeit + Uhr,
    # Hour-only + Uhr) in einem Schritt. Strip + Rekursion analog
    # :data:`_TRAILING_TIME`: die Uhrzeit ist semantische Wert-Anmerkung, keine
    # Datums-Modifikation - das ISO-Datum-Output ist identisch zur reinen
    # Datums-Form.
    stripped = _TRAILING_UHR_TIME.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # DE-/EN-Tageszeit-Trailing-Marker OHNE Uhrzeit-Ziffer abstreifen
    # ("13.06.2024 morgens", "13. Juni 2024 nachmittags", "2024-06-13 abends",
    # "13.06.2024, vormittags."). Vor _TRAILING_TIME einsortiert analog
    # _TRAILING_UHR_TIME: _TRAILING_TIME matcht hier sowieso nicht (keine
    # Ziffer im Suffix), aber die Reihenfolge haelt die beiden komplementaeren
    # "Uhrzeit-Anmerkungen"-Zweige (Uhr-Ziffer / Tageszeit-Adverb) direkt
    # nebeneinander. Strip + Rekursion analog _TRAILING_UHR_TIME: die
    # Tageszeit-Angabe ist semantische Wert-Anmerkung, keine Datums-
    # Modifikation - das ISO-Datum-Output ist identisch zur reinen Form.
    # Siehe :data:`_TRAILING_TAGESZEIT` fuer die Wortliste (DE-Adverb-
    # Formen + EN-Aequivalente), den [,\s]+-Trenner-Zwang (schuetzt vor
    # Bare-Adverb-Match) und die Reihenfolge-Analyse.
    stripped = _TRAILING_TAGESZEIT.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # Letzter Versuch: trailing Time-Suffix abschneiden und Datum allein parsen.
    # Faengt nicht-ISO-Eingaben wie "13.06.2024 14:30" oder "13. Juni 2024 10:00" ab.
    stripped = _TRAILING_TIME.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # Standalone-Trailing-Zeitzone ohne Zeitanteil ("2024-06-13 UTC",
    # "13.06.2024 CET", "Juni 2020 MEZ", "2024-06-13Z"). Nach
    # :data:`_TRAILING_TIME` einsortiert, damit Date+Time+TZ-Formen
    # ("2024-06-13T14:30 UTC") den kompletten Zeit+TZ-Block via
    # _TRAILING_TIME strippen und der Standalone-Strip nur die Date-Only-
    # Variante uebernimmt. Strip + Rekursion analog _TRAILING_ERA_MARKER /
    # _TRAILING_APPROX_SUFFIX: die TZ-Angabe ist semantische Wert-Anmerkung,
    # keine Datums-Modifikation. Siehe :data:`_TRAILING_TZ_STANDALONE` fuer
    # die Whitelist und den Whitespace-Trenner-Regel (nur ``Z`` darf compact
    # ans Datum haengen).
    stripped = _TRAILING_TZ_STANDALONE.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # Trailing parenthesized Annotation abstreifen ("13.06.2024 (Foto)",
    # "ca. 1985 [Schaetzung]"). In Sammlungs-Notizen verbreitet als Kontext-
    # Suffix nach dem Datum; gehoert nicht zum Datum selbst. Strip + Rekursion
    # vor _TRAILING_PUNCT, weil die Klammer-Form eine eigenstaendige strukturelle
    # Notation ist (die _TRAILING_PUNCT-Klasse deckt nur Satzzeichen ab).
    # Zuerst der Balanced-Bracket-Helper fuer geschachtelte Annotationen
    # ("(Foto (gut))", "[Sammlung (Muster (jun.))]"), die die _TRAILING_PAREN_REMARK-
    # Regex durch die Nicht-Klammer-Zeichenklasse strukturell ausschliesst;
    # anschliessend die einfachere Regex fuer Single-Level (auch mit gemischten
    # Paaren wie "(Foto]", die der Balanced-Helper nicht behandelt).
    stripped = _strip_trailing_balanced_bracket(s)
    if stripped is not None and stripped != s:
        return parse_iso_date(stripped) if stripped else None
    stripped = _TRAILING_PAREN_REMARK.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    # Trailing-Satzzeichen abstreifen ("Funddatum 2024-06-13.", "ca. 1985!").
    # Erst nach allen strukturellen Parsern, damit "1.6.2024" o.ae. nicht
    # vorzeitig ihren Punkt verlieren.
    stripped = _TRAILING_PUNCT.sub("", s).strip()
    if stripped and stripped != s:
        return parse_iso_date(stripped)
    return None


def _to_float(num: str) -> float:
    return float(num.replace(",", "."))


def _sign(direction: str | None) -> int:
    if not direction:
        return 1
    d = direction.upper()
    return -1 if d in ("S", "W") else 1


def _is_lat_direction(direction: str | None) -> bool | None:
    if not direction:
        return None
    d = direction.upper()
    if d in ("N", "S"):
        return True
    if d in ("E", "W", "O"):
        return False
    return None


def _dms_to_decimal(deg: str, minutes: str | None, seconds: str | None,
                    direction: str) -> float:
    val = _to_float(deg)
    if minutes:
        val += _to_float(minutes) / 60
    if seconds:
        val += _to_float(seconds) / 3600
    return val * _sign(direction)


def parse_coordinates(text) -> tuple[float, float] | None:
    """Parst Koordinaten in dezimal (lat, lon).

    Erkennt:
      - "46.5, 7.5"
      - "46.5° N, 7.5° E"  (auch O = Ost)
      - "N46.5 E7.5"
      - "46°30'15"N 7°30'0"E"
    Bei Mehrdeutigkeit (kein Hinweis auf Lat/Lon) wird (lat, lon) angenommen.
    Gibt None für leere/ungueltige Eingaben oder Werte ausserhalb [-90,90]/[-180,180].
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    # Typografisches Minus-Zeichen (U+2212) auf ASCII-Hyphen normalisieren, damit
    # negative Koordinaten aus typeset-Quellen (Print-Katalogen, PDFs aus LaTeX-
    # /Word-Autoformat, GPS-Tools mit "smart punctuation") nicht stille Lat/Lon-
    # Vorzeichen-Verluste erzeugen. Bisher fiel ``"−46.5, 7.5"`` durch die
    # _DECIMAL_PAIR-/_PREFIX_PAIR-Klassen [-+]? (ASCII-only) und lieferte
    # entweder den positiven Wert (Vorzeichen "geschluckt") oder None - beides
    # silentes Datenverlust-Risiko bei der Migration aus typografisch gesetzten
    # Sammlungs-Etiketten. Single-Pass-Strip vor allen Pattern-Versuchen ist
    # einfacher und sicherer als alle Zahl-Patterns parallel zu erweitern;
    # U+2212 hat im Koordinaten-Kontext keine andere Bedeutung als "negativ".
    s = s.replace("−", "-")
    # Maskuline Ordinal-Zeichen (U+00BA, ``º``) auf echtes Grad-Zeichen
    # (U+00B0, ``°``) normalisieren, damit DMS-/Decimal-Degree-Notationen aus
    # Spanisch-/Portugiesisch-/Italienisch-Tastaturen (dort liegt ``º`` als
    # eigene Taste, ``°`` erfordert AltGr-Kombination) und aus iOS-
    # Autokorrektur (Long-Press auf ``O`` bietet ``º`` an, nicht ``°``) sowie
    # aus OCR-Ergebnissen alter Print-Kataloge (die beiden Glyphen sind bei
    # niedriger Aufloesung visuell nicht unterscheidbar, viele OCR-Engines
    # geben stille ``º`` aus) nicht stille Koordinaten-Verluste erzeugen.
    # Bisher fielen alle Formen ``46.5º N``, ``46º30'15"N``, ``N46.5º E7.5º``
    # etc. still auf None, weil _DMS/_COORD_LABEL/_PREFIX_DMS und die weiteren
    # 40+ Vorkommen des ``°``-Literals im Regex-Vokabular strikt U+00B0
    # verlangen. Single-Pass-Strip vor allen Pattern-Versuchen ist einfacher
    # und sicherer als jedes einzelne Pattern mit einer ``[°º]``-Klasse zu
    # erweitern; ``º`` hat im Koordinaten-Kontext keine andere Bedeutung als
    # Grad-Marker (die Ordinal-Nutzung ``1º de junio`` = 1. Juni ist Datums-
    # Kontext, wird von :func:`parse_iso_date` behandelt, nicht hier).
    # Symmetrisch zum U+2212-Strip auf der Vorzeichen-Achse.
    s = s.replace("º", "°")
    # URL-encoded Komma (``%2C``/``%2c``) auf ASCII-Komma normalisieren, damit
    # aus dem Browser-Adress-Feld kopierte Geo-URLs (Google Maps ``?q=46.5%2C7.5``,
    # generische Query-Strings mit RFC-3986-Percent-Encoding des reservierten
    # ``,``-Zeichens) nicht stille Koordinaten-Verluste erzeugen. Ohne diese
    # Normalisierung faellt ``46.5%2C7.5`` durch die _DECIMAL_PAIR-Separator-
    # Klasse ``[ \t,;/&]`` (``%`` gehoert nicht dazu) und liefert None. Single-
    # Pass-Strip vor allen Pattern-Versuchen ist einfacher und sicherer als
    # alle Zahl-Patterns parallel um ``%2C``-Alternation zu erweitern; ``%2C``
    # hat im Koordinaten-Kontext keine andere Bedeutung als Komma. Symmetrisch
    # zum U+2212-Strip auf der Vorzeichen-Achse.
    s = s.replace("%2C", ",").replace("%2c", ",")
    # Fullwidth-CJK-Interpunktion auf ASCII normalisieren: Fullwidth-Komma
    # (U+FF0C ``，``), Fullwidth-Full-Stop (U+FF0E ``．``), Fullwidth-Solidus
    # (U+FF0F ``／``), Fullwidth-Semikolon (U+FF1B ``；``) und Ideographic-
    # Komma (U+3001 ``、``). Alle fuenf sind die Standard-Interpunktion aus
    # CJK-Text-Eingabe (Japanese/Chinese-IME liefert ``，`` statt ``,`` und
    # ``．`` statt ``.`` als Default; typisch auch fuer Copy-Paste aus CJK-
    # Publikationen, aus wechselnden IME-Kontexten und aus MS-Office-
    # Autoformat mit CJK-Locale). Ohne Normalisierung fallen alle CJK-
    # Interpunktions-Formen durch die _DECIMAL_PAIR-Separator-Klasse
    # ``[ \t,;/&]`` (kennt keine Fullwidth-Zeichen) und den Decimal-Punkt
    # der _NUM_RE-Zahl-Extraktion und liefern stille None - der Sammler-
    # Workflow "GPS-Koordinate aus CJK-Referenz kopieren, ins Fundort-Feld
    # einfuegen" scheitert unsichtbar. Fullwidth-Ziffern (U+FF10..U+FF19)
    # sind bereits transparent behandelt, weil Python ``\d`` Unicode-Decimal
    # per Default matcht (die CJK-Ziffern-Formen sind decimal-property-
    # Zeichen); nur die Interpunktion braucht den expliziten Strip. Single-
    # Pass-Replace vor allen Pattern-Versuchen ist symmetrisch zum U+2212-/
    # ``º``-/``%2C``-Strip auf ihren jeweiligen semantischen Achsen; die
    # fuenf Zeichen haben im Koordinaten-Kontext keine andere Bedeutung als
    # ihre ASCII-Aequivalente. Fullwidth-Semikolon (U+FF1B) spiegelt den
    # bereits im :data:`_DECIMAL_PAIR`-Separator akzeptierten ASCII-``;``
    # auf die CJK-Achse - CJK-GIS-Reports und Sammler-Notizen aus JP/ZH-
    # Locale nutzen ``；`` als Achsen-Trenner in derselben Weise, wie
    # DE-/EU-Excel-CSV-Exporte ``;`` als Feld-Trenner nutzen. Ideographic-
    # Komma (U+3001) ist die CJK-Enumeration-Interpunktion und wird in
    # Foto-Captions und Fundort-Beschreibungen aus JP-Sammler-Notizen
    # regelmaessig als Achsen-Trenner zwischen zwei Zahl-Feldern gesetzt
    # ("46.5、7.5" statt "46.5, 7.5"), spiegelt semantisch die ``、``=``,``-
    # Konvention der JIS-Interpunktions-Tabelle. Beide Zeichen sind
    # kollisionsfrei zu ihren ASCII-Aequivalenten, weil weder ``；`` noch
    # ``、`` im Koordinaten-Kontext eine andere Bedeutung als "Trenner"
    # tragen.
    s = (s.replace("，", ",")
          .replace("．", ".")
          .replace("／", "/")
          .replace("；", ";")
          .replace("、", ","))
    # OSM-URL-Hash-Fragment "#map=<zoom>/<lat>/<lon>" vor allen Zahl-Paar-Patterns
    # extrahieren: das erste Slash-getrennte Feld ist der Zoom-Level, nicht die
    # Latitude - _DECIMAL_PAIR wuerde sonst (zoom, lat) statt (lat, lon) greifen
    # und die tatsaechliche Longitude verwerfen. Match ist definitiv: wenn die
    # OSM-Fragment-Signatur erkannt wird, ist die Zoom-Lat-Lon-Reihenfolge
    # eindeutig, und ein Fallback auf _DECIMAL_PAIR wuerde exakt den Bug
    # reintroduzieren, den dieser Zweig fixt (Zoom-Level als Latitude gelesen).
    # Return des _validate-Ergebnisses (None bei Out-of-Range), analog zu den
    # ISO6709-Compact-Zweigen.
    m = _OSM_HASH_MAP.search(s)
    if m:
        return _validate(_to_float(m.group(1)), _to_float(m.group(2)))
    # Wikipedia-GeoHack-URL-Query-Parameter ``params=<lat>_<dir>_<lon>_<dir>``
    # mit Underscore-getrennter Decimal-/DM-/DMS-Zahlen-Kette. Vor allen
    # Zahl-Paar-Patterns extrahieren, weil Underscore als Separator in keinem
    # der weiteren Patterns anerkannt ist und die Formen sonst still auf None
    # fallen wuerden. Die drei Optionalitaets-Klauseln in :data:`_GEOHACK_PARAMS`
    # decken Decimal (nur Grad), DM (Grad+Minuten) und DMS (Grad+Minuten+
    # Sekunden) transparent ab; die Direction-Buchstaben liefern das Vorzeichen
    # (N/E/O positiv, S/W negativ) und disambiguieren die Achsen-Reihenfolge.
    m = _GEOHACK_PARAMS.search(s)
    if m:
        deg_lat = _to_float(m.group(1))
        min_lat = _to_float(m.group(2)) if m.group(2) else 0.0
        sec_lat = _to_float(m.group(3)) if m.group(3) else 0.0
        dir_lat = m.group(4)
        deg_lon = _to_float(m.group(5))
        min_lon = _to_float(m.group(6)) if m.group(6) else 0.0
        sec_lon = _to_float(m.group(7)) if m.group(7) else 0.0
        dir_lon = m.group(8)
        lat = (deg_lat + min_lat / 60 + sec_lat / 3600) * _sign(dir_lat)
        lon = (deg_lon + min_lon / 60 + sec_lon / 3600) * _sign(dir_lon)
        return _validate(lat, lon)
    # WKT-POINT-Notation (OGC Simple Features): "POINT(lon lat)". Vor allen
    # Zahl-Paar-Patterns extrahieren, weil das erste Zahl-Feld die
    # Longitude ist, nicht die Latitude - _DECIMAL_PAIR (Whitespace-Separator
    # ohne Direction-Buchstaben) wuerde sonst (lon, lat) als (lat, lon)
    # lesen und die publizierten Achsen silente vertauschen. Match ist
    # definitiv: das OGC-Standard-Format spezifiziert (X Y) mit X=Lon,
    # Y=Lat; ein Fallback auf _DECIMAL_PAIR wuerde exakt die Vertauschung
    # reintroduzieren, die dieser Zweig fixt. Return des _validate-Ergebnisses
    # mit umgesortierter Rueckgabe (Lat, Lon) analog zu den anderen Zweigen.
    m = _WKT_POINT.match(s)
    if m:
        lon = _to_float(m.group(1))
        lat = _to_float(m.group(2))
        return _validate(lat, lon)
    # GeoJSON-Point-Notation (RFC 7946): Type=``Point`` + Coordinates=``[lon, lat]``.
    # Vor allen Zahl-Paar-Patterns extrahieren, weil das erste Zahl-Feld die
    # Longitude ist, nicht die Latitude - _DECIMAL_PAIR (Komma-Separator ohne
    # Direction-Buchstaben) wuerde sonst (lon, lat) als (lat, lon) lesen und
    # die publizierten Achsen silente vertauschen (analog zum WKT-POINT-Fall).
    # Match ist definitiv nur, wenn BEIDE Marker (Type=Point, Coordinates-Array)
    # vorhanden sind - dann ist die (Lon, Lat)-Reihenfolge per RFC 7946 §3.1.1
    # eindeutig. Fallback auf _DECIMAL_PAIR wuerde exakt die Vertauschung
    # reintroduzieren, die dieser Zweig fixt. Fehlt der Type-Marker oder das
    # Coordinates-Feld, faellt die Eingabe auf das bestehende Verhalten zurueck
    # (kein GeoJSON, generische Zahl-Paar-Extraktion greift).
    if _GEOJSON_POINT_TYPE.search(s):
        m = _GEOJSON_POINT_COORDS.search(s)
        if m:
            lon = _to_float(m.group(1))
            lat = _to_float(m.group(2))
            return _validate(lat, lon)
    # GeoURI-Notation (RFC 5870): "geo:<lat>,<lon>[,<alt>][;param=value...]".
    # Android-Intent-Query-Form "geo:0,0?q=<lat>,<lon>(<label>)" muss VOR der
    # generischen GeoURI-Form geprueft werden, weil sonst der Platzhalter-Pfad
    # "0,0" matcht und die echten Koordinaten im ?q=-Query verworfen wuerden
    # (silente Achsen-/Wert-Vertauschung: Sammler kopiert einen Google-Maps-
    # Share-Intent aus der Android-App, bekommt (0.0, 0.0) statt seiner
    # tatsaechlichen Position). Beide Zweige verwenden RFC-5870-Achsen-
    # Reihenfolge (Lat, Lon) - kein _orient noetig (Reihenfolge ist im
    # URI-Schema fix vorgegeben). Der RFC-5870-Zweig konsumiert den Rest
    # der Eingabe (Parameter, Query) via anchored ".*"-Suffix, damit die
    # generischen Fallback-Patterns (_DECIMAL_PAIR, _PREFIX_PAIR) keine
    # sekundaeren Zahl-Paare aus Uncertainty/Altitude aufgreifen.
    m = _GEO_URI_ANDROID_QUERY.match(s)
    if m:
        return _validate(_to_float(m.group(1)), _to_float(m.group(2)))
    m = _GEO_URI.match(s)
    if m:
        return _validate(_to_float(m.group(1)), _to_float(m.group(2)))
    # Google-Maps-Place-URL-Fragment "!3d<lat>!4d<lon>" (Protobuf-Feld-Serialisierung
    # im /data=-Segment). Muss vor _DECIMAL_PAIR gepruft werden, weil sonst der
    # ``@<lat>,<lon>,<zoom>z``-View-Center gewinnt und die semantisch relevante
    # Pin-Position ignoriert wuerde (die beiden Paare koennen unterschiedlich sein,
    # wenn der Sammler heraus-gezoomt teilt). Match ist definitiv: der !3d/!4d-
    # Marker-Paar identifiziert eindeutig die Pin-Koordinaten - keine Achsen-
    # Vertauschung, keine _orient-Nachpruefung noetig (die Protobuf-Feld-Indizes
    # 3 und 4 sind fix Lat/Lon per Google-Encoding).
    m = _GOOGLE_PLACE_3D_4D.search(s)
    if m:
        return _validate(_to_float(m.group(1)), _to_float(m.group(2)))
    # Yandex-Maps-URL-Konvention: ``ll=<lon>,<lat>`` / ``pt=<lon>,<lat>[,...]``
    # verwendet (Longitude, Latitude)-Reihenfolge - entgegen der von Google/Apple/
    # Bing/OSM benutzten (Latitude, Longitude). Vor allen Zahl-Paar-Patterns
    # extrahieren, damit die generische :data:`_DECIMAL_PAIR`-Search die Yandex-
    # Zahl-Reihenfolge nicht als (Lat, Lon) fehlinterpretiert. Match ist definitiv:
    # wenn die Yandex-Domain-Signatur plus das ``ll=``/``pt=``-Parameter erkannt
    # wird, ist die Zahl-Reihenfolge eindeutig (Lon, Lat), und ein Fallback auf
    # :data:`_DECIMAL_PAIR` wuerde exakt die Vertauschung reintroduzieren, die
    # dieser Zweig fixt. Return des :func:`_validate`-Ergebnisses mit
    # umgesortierter Rueckgabe (Lat, Lon), analog zu :data:`_WKT_POINT` und
    # :data:`_GEOJSON_POINT_COORDS`.
    m = _YANDEX_LL.search(s)
    if m:
        lon = _to_float(m.group(1))
        lat = _to_float(m.group(2))
        return _validate(lat, lon)
    # KML-Point-Notation (OGC KML 2.2): ``<Point>...<coordinates>lon,lat[,alt]
    # </coordinates>...</Point>``. Match ist definitiv nur, wenn BEIDE Marker
    # (Point-Tag + Coordinates-Tag) vorhanden sind - dann ist die (Lon, Lat)-
    # Reihenfolge per KML-Spec eindeutig, analog zur konservativen GeoJSON-
    # Marker-Kombination (Type=Point + Coordinates-Array). Fehlt der
    # Point-Marker (LineString/LinearRing/Polygon), enthaelt das Coordinates-
    # Element semantisch einen Pfad/Ring mit mehreren Tupeln - die App
    # fuehrt keine Pfad-Achse, daher fallen diese Formen bewusst auf das
    # bestehende Verhalten zurueck (analog zur MultiPoint-Rejection im
    # WKT-/GeoJSON-Test). Fallback auf _DECIMAL_PAIR wuerde exakt die
    # Vertauschung reintroduzieren, die dieser Zweig fixt.
    if _KML_POINT_MARKER.search(s):
        m = _KML_COORDINATES.search(s)
        if m:
            lon = _to_float(m.group(1))
            lat = _to_float(m.group(2))
            return _validate(lat, lon)
    # Wenn *beide* Achsen explizit per Label markiert sind (``Lat:``/``Lon:``,
    # ``latitude=``/``longitude=``, ``mlat=``/``mlon=``, ``lat=``/``lng=``,
    # ``Breite``/``Länge`` etc.), per Label-Position extrahieren - sonst wuerde
    # die stumme _COORD_LABEL-Strip-Semantik ein Lon-vor-Lat-Input silente in
    # (lon, lat)-Reihenfolge an _DECIMAL_PAIR uebergeben und die publizierten
    # Achsen vertauschen. Match ist definitiv: wenn beide Labels erkannt werden,
    # ist die Achsen-Zuordnung eindeutig; ein Fallback auf die generische Strip-
    # Route wuerde exakt den Bug reintroduzieren, den dieser Zweig fixt
    # (OSM-``?mlon=X&mlat=Y``-URL, JavaScript-API-``?lng=X&lat=Y``, freitext-
    # ``"Lon: 7.5, Lat: 46.5"``, GIS-Reports mit (Lon, Lat)-Reihenfolge).
    # Rueckgabe ``_LABELED_SENTINEL`` markiert "keine beide Labels" und faellt
    # auf die generische _COORD_LABEL-Strip-Route durch; Rueckgabe ``None``
    # markiert "beide Labels erkannt, aber Out-of-Range" und ist ein definitiver
    # Reject (sonst wuerde ``lon=50&lat=100`` die publizierte Achsen-Zuordnung
    # verwerfen und via label-stripped _DECIMAL_PAIR ``(50, 100)`` liefern -
    # semantisch falsch, weil der Sammler explizit ``lat=100`` angegeben hat).
    labeled = _extract_labeled_lat_lon(s)
    if labeled is not _LABELED_SENTINEL:
        return labeled  # type: ignore[return-value]
    # Labels wie "Lat:"/"Lon:"/"Breite"/"Länge" stoeren _PREFIX_PAIR (das L in "Lon"
    # wird sonst als Richtung interpretiert). Vor dem Matching stillschweigend strippen.
    if _COORD_LABEL.search(s):
        s = _COORD_LABEL.sub(" ", s).strip()
        if not s:
            return None
    # Vollnamen der Himmelsrichtungen ("North"/"Nord"/"Osten" ...) auf die Ein-
    # Buchstaben-Form normalisieren, damit die Patterns weiter unten greifen.
    # Reine N/S/E/W/O-Eingaben bleiben unveraendert.
    s = _normalize_direction_words(s)

    dms_hits = _DMS.findall(s)
    if len(dms_hits) >= 2:
        a = _dms_to_decimal(*dms_hits[0])
        b = _dms_to_decimal(*dms_hits[1])
        lat, lon = _orient(a, dms_hits[0][3], b, dms_hits[1][3])
        return _validate(lat, lon)

    # DMS-Notation mit ASCII-Buchstaben-Markern ("46d30m15sN", "46deg30min15secN")
    # aus Consumer-GPS-Displays und Typewriter-Notation ohne ° / ' / ". Vor
    # _DMS_COLON und _PREFIX_PAIR/_DECIMAL_PAIR geprueft, damit die drei
    # Buchstaben-getrennten Zahlen nicht vorzeitig als (Grad, naechste Zahl)-
    # Paar interpretiert werden. Spiegelt die _DMS-Logik (findall,
    # _dms_to_decimal, _orient) auf die Buchstaben-Variante.
    dms_letters_hits = _DMS_LETTERS.findall(s)
    if len(dms_letters_hits) >= 2:
        a = _dms_to_decimal(*dms_letters_hits[0])
        b = _dms_to_decimal(*dms_letters_hits[1])
        lat, lon = _orient(a, dms_letters_hits[0][3], b, dms_letters_hits[1][3])
        return _validate(lat, lon)

    # Colon-separierte DMS-Notation ohne ° / ' / "-Symbole ("46:30:15 N").
    # Vor _PREFIX_PAIR/_DECIMAL_PAIR geprueft, damit die Drei-Zahlen-Folge nicht
    # vorzeitig als (Sekunden, naechste Zahl)-Paar interpretiert wird; spiegelt
    # die _DMS-Logik (findall, _dms_to_decimal, _orient) auf die colon-Variante.
    dms_colon_hits = _DMS_COLON.findall(s)
    if len(dms_colon_hits) >= 2:
        a = _dms_to_decimal(*dms_colon_hits[0])
        b = _dms_to_decimal(*dms_colon_hits[1])
        lat, lon = _orient(a, dms_colon_hits[0][3], b, dms_colon_hits[1][3])
        return _validate(lat, lon)

    # Prefix-DMS-Notation ("N 46° 30' 15\" E 7° 30' 0\""). Vor _PREFIX_PAIR
    # gepruft, damit die spezifischere DMS-Struktur den zu-greedy-Match des
    # decimal-Prefix-Patterns ueberholt (dieses wuerde nur (Direction+Deg)
    # matchen und Minuten/Sekunden ignorieren). Capture-Reihenfolge im Pattern
    # ist (dir, deg, min_with_prime, min_ddm_no_prime, sec) - Minuten-Alternanten
    # zusammenfuehren (nur eine der beiden kann bei einem Match belegt sein,
    # die jeweils andere ist ''), dann umsortieren zu (deg, min, sec, dir) fuer
    # den _dms_to_decimal-Aufruf.
    dms_prefix_hits = _DMS_PREFIX.findall(s)
    if len(dms_prefix_hits) >= 2:
        d1, deg1, min1a, min1b, sec1 = dms_prefix_hits[0]
        d2, deg2, min2a, min2b, sec2 = dms_prefix_hits[1]
        min1 = min1a or min1b
        min2 = min2a or min2b
        a = _dms_to_decimal(deg1, min1, sec1, d1)
        b = _dms_to_decimal(deg2, min2, sec2, d2)
        lat, lon = _orient(a, d1, b, d2)
        return _validate(lat, lon)

    m = _PREFIX_PAIR.search(s)
    if m:
        d1, n1, d2, n2 = m.groups()
        a = _to_float(n1) * _sign(d1)
        b = _to_float(n2) * _sign(d2)
        lat, lon = _orient(a, d1, b, d2)
        return _validate(lat, lon)

    # NMEA-0183 Sentence-Form: "4630.500,N,00745.300,E" - Grad+Minuten-Kompakt-
    # Struktur mit N/S/E/W-Direction-Buchstaben statt Vorzeichen (siehe
    # :data:`_NMEA_LATLON`-Kommentar). Vor :data:`_DECIMAL_PAIR` geprueft, weil
    # das generische Zahl-Paar-Pattern die 4-Ziffer-Latitude "4630.500" als reine
    # Dezimal 4630.5 lesen wuerde - via _validate faellt der Wert ausserhalb
    # ±90 durch und liefert None, was die NMEA-Erkennung blockt. Nach
    # :data:`_PREFIX_PAIR` einsortiert, weil die generischen Prefix-Direction-
    # Formen ("N 46 E 7") die typische Notation ohne Grad-Minuten-Kompakt-
    # Struktur behandeln - kollisionsfrei, weil NMEA obligatorische 4/5-Ziffer-
    # Ganzzahl-Vorstand-Struktur verlangt, die die einfache Dezimal-Form nicht
    # erfuellt.
    m = _NMEA_LATLON.search(s)
    if m:
        deg_a, min_a, dir_a, deg_b, min_b, dir_b = m.groups()
        a = _to_float(deg_a) + _to_float(min_a) / 60
        b = _to_float(deg_b) + _to_float(min_b) / 60
        a *= _sign(dir_a)
        b *= _sign(dir_b)
        lat, lon = _orient(a, dir_a, b, dir_b)
        return _validate(lat, lon)

    m = _DECIMAL_PAIR.search(s)
    if m:
        n1, d1, n2, d2 = m.groups()
        a = _to_float(n1) * _sign(d1)
        b = _to_float(n2) * _sign(d2)
        lat, lon = _orient(a, d1, b, d2)
        return _validate(lat, lon)

    # Compact-Suffix-Form ohne Separator: "46.5N7.5E" / "46.5°N7.5°E".
    # Letzter Versuch, weil die obligatorische Richtungs-Anwesenheit hier eindeutig
    # ist und keine der frueheren Patterns matcht (kein Separator zwischen Zahl
    # und naechster Richtung).
    m = _SUFFIX_PAIR_NO_SEP.search(s)
    if m:
        n1, d1, n2, d2 = m.groups()
        a = _to_float(n1) * _sign(d1)
        b = _to_float(n2) * _sign(d2)
        lat, lon = _orient(a, d1, b, d2)
        return _validate(lat, lon)

    # ISO 6709 Compact-Decimal-Form: "+46.5+007.5/" / "+46.5+7.5" / "-46.5-7.5".
    # Letzter Versuch (nach _SUFFIX_PAIR_NO_SEP), weil die obligatorischen Vorzeichen
    # die Form eindeutig machen, aber als Anker-basierter Match (^...$) restriktiver
    # ist als die uebrigen .search()-Patterns - er greift nur, wenn der gesamte
    # Input dem Compact-Format entspricht (keine zusaetzlichen Tokens davor/danach).
    # Dadurch bleibt sie kollisionsfrei zu allen Decimal-/DMS-/Prefix-/Suffix-Formen
    # mit Separator oder Richtungs-Buchstaben. Reihenfolge Lat→Lon ist im ISO-6709-
    # Standard fix vorgegeben - kein _orient noetig.
    m = _ISO6709_COMPACT_DECIMAL.match(s)
    if m:
        lat = _to_float(m.group(1))
        lon = _to_float(m.group(2))
        return _validate(lat, lon)

    # ISO 6709 Compact-DMS-Form: "+463015+0074500/", "+463015.5+0074500.5".
    # Grad+Minuten+Sekunden ohne Trenner - die feste Ziffernbreite (2+2+2 fuer
    # Lat, 3+2+2 fuer Lon) disambiguiert vom Compact-Decimal-Fall (1-2/1-3
    # Ganzzahl-Ziffern) und vom Compact-DM-Fall (2+2 / 3+2 = 4/5 Ziffern).
    # Vor _ISO6709_COMPACT_DM geprueft, weil die 6/7-Ziffer-Klasse spezifischer
    # ist (mehr Positions-Zwang) und den Standard-"spezifischer zuerst"-Ansatz
    # spiegelt - obwohl die drei Ziffernbreite-Klassen strukturell disjunkt
    # sind und die Reihenfolge semantisch keinen Unterschied macht.
    m = _ISO6709_COMPACT_DMS.match(s)
    if m:
        s_lat, deg_lat, min_lat, sec_lat = m.group(1), m.group(2), m.group(3), m.group(4)
        s_lon, deg_lon, min_lon, sec_lon = m.group(5), m.group(6), m.group(7), m.group(8)
        lat = (_to_float(deg_lat) + _to_float(min_lat) / 60
               + _to_float(sec_lat) / 3600) * (-1 if s_lat == "-" else 1)
        lon = (_to_float(deg_lon) + _to_float(min_lon) / 60
               + _to_float(sec_lon) / 3600) * (-1 if s_lon == "-" else 1)
        return _validate(lat, lon)

    # ISO 6709 Compact-DM-Form: "+4630+00745/", "+4630.5+00745.5".
    # Grad+Minuten ohne Trenner - 4 Ganzzahl-Ziffern Lat / 5 Ganzzahl-Ziffern
    # Lon (2+2 / 3+2). Disjunkt zu Compact-Decimal (1-2/1-3) und Compact-DMS
    # (6/7). Letzter Versuch der Compact-Kette; nur explizit fehlerfreier DM-
    # Match darf zu einem Ergebnis fuehren, sonst None.
    m = _ISO6709_COMPACT_DM.match(s)
    if m:
        s_lat, deg_lat, min_lat = m.group(1), m.group(2), m.group(3)
        s_lon, deg_lon, min_lon = m.group(4), m.group(5), m.group(6)
        lat = (_to_float(deg_lat) + _to_float(min_lat) / 60
               ) * (-1 if s_lat == "-" else 1)
        lon = (_to_float(deg_lon) + _to_float(min_lon) / 60
               ) * (-1 if s_lon == "-" else 1)
        return _validate(lat, lon)

    return None


def _orient(a: float, da: str | None, b: float, db: str | None) -> tuple[float, float]:
    """Ordnet die beiden Werte korrekt zu (lat, lon) basierend auf Richtungs-Hinweisen."""
    a_is_lat = _is_lat_direction(da)
    b_is_lat = _is_lat_direction(db)
    if a_is_lat is True or b_is_lat is False:
        return a, b
    if b_is_lat is True or a_is_lat is False:
        return b, a
    return a, b


def _validate(lat: float, lon: float) -> tuple[float, float] | None:
    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
        return lat, lon
    return None
