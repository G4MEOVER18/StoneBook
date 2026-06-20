"""Eingabe-Validatoren für Felder mit freiem Textformat (Funddatum, Koordinaten)."""
from __future__ import annotations

import datetime
import re

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y%m%d",   # ISO 8601 compact YYYYMMDD (Dateinamen, Logs)
    "%Y:%m:%d",  # EXIF DateTime ohne Zeit-Suffix (stripped Camera-Stempel)
)

_YEAR_ONLY = re.compile(r"^\s*(\d{4})\s*$")
# Jahrzehnt-Notation ("1980er", "1980s", "1980er Jahre", "1980-er").
# Konvention: Dekaden-Start = Jahr selbst (1980er → 1980-01-01). Reichweite-Annotation
# bleibt im Freitext (notizen). Zweistellige Kurzform "80er" ist mehrdeutig
# (1880er vs 1980er) und wird bewusst nicht aufgeloest -- liefert None.
_DECADE = re.compile(
    r"^\s*(\d{4})(?:[\- ]?(?:er|s))(?:\s+jahre)?\s*$",
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
_APPROX_PREFIX = re.compile(
    r"^(?:ca\.?|circa|approx\.?|approximately"
    r"|around|about|roughly|estimated|est\."
    r"|um|gegen|etwa|vermutlich"
    # Umlaut-Variante und Transliteration ae (gemischte Sammlungs-Notizen)
    r"|sch[äa]tzungsweise|schaetzungsweise"
    r")\s+",
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
_TRAILING_TIME = re.compile(
    r"[Tt ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
    r"(?:\s*[Zz]|\s*[+-]\d{2}:?\d{2})?\s*$"
)
# Trailing-Satzzeichen ("2024-06-13.", "1985!", "13. Juni 2024;").
# Geerbte Sammlungs-Notizen sind oft ganze Saetze mit Datum am Ende; das Punkt-
# /Doppelpunkt-Suffix gehoert nicht zum Datum selbst und wird vor dem Re-Parsing
# entfernt. ISO-Datumformate enden auf Ziffern, kollidieren also nicht.
_TRAILING_PUNCT = re.compile(r"[.,;:!?]+\s*$")
# Umschliessende Klammern/Anfuehrungszeichen aus zitierten Datumsangaben:
# "(2024)", "[2024-06-13]", '"13. Juni 2024"', '„Sommer 1985"'.
# Genau ein Paar wird gestrippt; danach Re-Parsing per Rekursion.
_BRACKET_PAIRS: tuple[tuple[str, str], ...] = (
    ("(", ")"), ("[", "]"), ("{", "}"),
    ('"', '"'), ("'", "'"), ("`", "`"),
    ("«", "»"), ("‹", "›"),
    ("„", "\""), ("„", "“"), ("‚", "‘"),
)
# ISO 8601 mit Zeitanteil: "2024-06-13T10:00:00", "2024-06-13 10:00:00Z",
# auch EXIF-Stil "2024:06:13 10:00:00" → Zeit wird verworfen, nur Datum bleibt.
_ISO_DATETIME = re.compile(
    r"^\s*(\d{4})[-:/.](\d{1,2})[-:/.](\d{1,2})"
    r"[Tt ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
    r"(?:\s*[Zz]|\s*[+-]\d{2}:?\d{2})?\s*$"
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
    r"^\s*(\d{1,2})(?:st|nd|rd|th)?\s*[./\-]?\s*([A-Za-zÄÖÜäöü]+)\.?"
    r"\s*[,./\-]?\s*(\d{4})\s*$",
    re.IGNORECASE,
)
# Englische Reihenfolge "Jun 13, 2024" / "June 13 2024" / "Jun. 13, 2024" / "Jun/13/2024"
# / "Jun-13-2024". Tag-Ordinal "March 1st, 2024" wird ebenfalls akzeptiert.
_ENGLISH_MONTH_DAY_YEAR = re.compile(
    r"^\s*([A-Za-z]+)\s*[./\-]?\s*(\d{1,2})(?:st|nd|rd|th)?\s*[,./\-]?\s*(\d{4})\s*$",
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
_MONTH_YEAR = re.compile(
    r"^\s*([A-Za-zÄÖÜäöü]+)\.?\s*[,./ \-]\s*(\d{4})\s*$",
)

# Jahreszeit + Jahr ("Sommer 1985", "Spring 2024", "Frühjahr 2020").
# Konvention: meteorologischer Saison-Start im genannten Jahr (Maerz/Juni/Sep/Dez).
# Winter wird auf Dezember desselben Jahres gelegt; "Winter 1999/2000" o.ae. werden
# bewusst nicht aufgeloest (Mehrdeutigkeit) und fallen auf None.
_SEASON_MONTHS: dict[str, int] = {
    "fruehling": 3, "fruehjahr": 3, "spring": 3,
    "sommer": 6, "summer": 6,
    "herbst": 9, "autumn": 9, "fall": 9,
    "winter": 12,
}
_SEASON_YEAR = re.compile(
    r"^\s*([A-Za-zÄÖÜäöü]+)\.?\s*[, ]?\s*(\d{4})\s*$",
)

# Quartal + Jahr ("Q1 2024", "Q3/1985", "1. Quartal 2024", "3. Quarter 1985",
# "1Q2024", "Quartal 1 2024"). Konvention: Quartals-Startmonat (Jan/Apr/Jul/Okt).
# Akzeptiert sowohl deutsche ("Quartal") als auch englische ("Quarter") Schreibweise.
_QUARTER_MONTHS: dict[int, int] = {1: 1, 2: 4, 3: 7, 4: 10}
# "Q1 2024" / "Q1/2024" / "Q1-2024" / "1Q 2024"
_QUARTER_SHORT = re.compile(
    r"^\s*(?:Q\s*([1-4])|([1-4])\s*Q)\s*[/.\-,]?\s*(\d{4})\s*$",
    re.IGNORECASE,
)
# "1. Quartal 2024" / "Quartal 1 2024" / "3. Quarter 1985"
_QUARTER_LONG = re.compile(
    r"^\s*(?:([1-4])\s*\.?\s*(?:quartal|quarter)|(?:quartal|quarter)\s+([1-4]))"
    r"\s*[/.\-, ]?\s*(\d{4})\s*$",
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
    r"^\s*(\d{4})\s*[/.\-, ]?\s*(?:Q\s*([1-4])|([1-4])\s*Q)\s*$",
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
    r"(?:([1-4])\s*\.?\s*(?:quartal|quarter)|(?:quartal|quarter)\s+([1-4]))\s*$",
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

# ISO 8601 Wochendatum: "2024-W25", "2024W25" (compact), "2024-W25-3" (mit Tag).
# Konvention: ohne expliziten Wochentag → Montag der Woche (ISO-Wochenstart).
# Verbreitet in Log-/Build-Stempeln und manchen Sammlungs-Notizen ("KW25 2024").
# Zwei Schreibweisen werden akzeptiert: ISO-Standard (Bindestrich) und compact
# (ohne Bindestrich); Wochentag optional, immer 1-7 (Mo-So per ISO-Definition).
_ISO_WEEK_DATE = re.compile(
    r"^\s*(\d{4})-?W(\d{1,2})(?:-?([1-7]))?\s*$",
    re.IGNORECASE,
)
# Deutsche KW-Notation: "KW 25 2024", "KW25/2024", "KW 25, 2024".
# Verbreitet in Sammlungs-Tagebuechern (Wochenangaben statt Tagen). Mapping
# identisch zu _ISO_WEEK_DATE (Montag der genannten Woche).
_KW_YEAR = re.compile(
    r"^\s*KW\s*(\d{1,2})\s*[/.\-, ]\s*(\d{4})\s*$",
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
_RELATIVE_YEAR = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)[-\s]+(\d{4})\s*$",
    re.IGNORECASE,
)


def _normalize_month_name(name: str) -> int | None:
    key = name.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return _MONTH_NAMES.get(key)


def _normalize_season_name(name: str) -> int | None:
    key = name.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return _SEASON_MONTHS.get(key)
# DMS: 46°30'15" N  /  7° 30' 0'' O  /  46°30'15.5"S
_DMS = re.compile(
    r"""(\d+(?:[.,]\d+)?)\s*°               # Grad
        (?:\s*(\d+(?:[.,]\d+)?)\s*['′])?    # optional Minuten
        (?:\s*(\d+(?:[.,]\d+)?)\s*(?:["″]|''))?  # optional Sekunden
        \s*([NSEWOnsewo])                   # Himmelsrichtung
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
    r"""([-+]?\d+(?:[.,]\d+)?)\s*°?\s*([NSEWOnsewo])?  # erste Zahl + opt. Richtung
        \s*[ \t,;/]\s*
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
# Gelaeufige Bezeichner vor den eigentlichen Koordinaten: "Lat: 46.5, Lon: 7.5",
# "Breite 46.5 Länge 7.5", "latitude=46.5 longitude=7.5". Werden vor dem
# Pattern-Matching entfernt; die Himmelsrichtung im Label (N/E/S/W als Buchstabe
# in "Lon") ist nicht gemeint und wuerde sonst _PREFIX_PAIR irrefuehren.
_COORD_LABEL = re.compile(
    r"""\b(?:
            latitude | lat | breitengrad | breite
          | longitude | longitudinal | long | lon | laengengrad | laenge
          | längengrad | länge
        )
        (?![A-Za-zÄÖÜäöü])     # kein Anschnitt eines laengeren Wortes ("latex")
        \.?\s*[:=]?\s*         # optionaler Punkt + : / = + Whitespace
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Vollnamen der Himmelsrichtungen (DE/EN) werden vor dem Pattern-Matching auf
# die Ein-Buchstaben-Form reduziert, mit der _DMS/_DECIMAL_PAIR/_PREFIX_PAIR
# arbeitet. Verbreitet in GPS-Logs/Foto-Captions: ``"North 46.5, East 7.5"``,
# ``"Nord 46.5°, Ost 7.5°"``, ``"Norden 46.5 Osten 7.5"``.
# DE-Vollformen mit -en-Suffix (``Norden``/``Sueden``/``Osten``/``Westen``)
# sind im Sammler-Sprachgebrauch ueblich; ``Sued`` bleibt mit Umlaut-Normalisierung.
_DIRECTION_WORD = re.compile(
    r"\b(?:"
    r"north|south|east|west"
    r"|nord(?:en)?|sued(?:en)?|s[uü]d(?:en)?|ost(?:en)?|west(?:en)?"
    r")\b\.?",
    re.IGNORECASE,
)
_DIRECTION_LETTER: dict[str, str] = {
    "n": "N", "north": "N", "nord": "N", "norden": "N",
    "s": "S", "south": "S",
    "sued": "S", "sueden": "S", "süd": "S", "süden": "S",
    "e": "E", "east": "E",
    "o": "O", "ost": "O", "osten": "O",
    "w": "W", "west": "W", "westen": "W",
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


def parse_iso_date(text) -> str | None:
    """Konvertiert verschiedene Datumsschreibweisen in ISO YYYY-MM-DD.

    Unterstützt: YYYY-MM-DD, DD.MM.YYYY, YYYY/MM/DD, YYYY-MM (→ -01),
    reine Jahresangaben YYYY (→ -01-01). Gibt None für leere/ungueltige Werte.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s or s.lower() in {"k.a.", "k. a.", "n/a", "na", "?", "-", "—", "unbekannt"}:
        return None
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
    m = _YEAR_ONLY.match(s)
    if m:
        year = int(m.group(1))
        if 1800 <= year <= 2999:
            return f"{year:04d}-01-01"
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
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if 1800 <= d.year <= 2999:
            return d.isoformat()
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
    m = _MONTH_YEAR.match(s)
    if m:
        month = _normalize_month_name(m.group(1))
        year = int(m.group(2))
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
    # Deutsche KW-Notation ("KW 25 2024", "KW25/2024"). Mapping wie _ISO_WEEK_DATE.
    m = _KW_YEAR.match(s)
    if m:
        week, year = int(m.group(1)), int(m.group(2))
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
    # Relative Jahresposition ("Anfang/Mitte/Ende 2024", "early/mid/late 2024",
    # "mid-2024"). Vor _SEASON_YEAR geprueft, damit die Schluesselwoerter nicht
    # erst als unbekannter Saison-Name auf None fallen.
    m = _RELATIVE_YEAR.match(s)
    if m:
        month = _RELATIVE_MONTHS[m.group(1).lower()]
        year = int(m.group(2))
        if 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Jahreszeit + Jahr ("Sommer 1985", "Spring 2024"): meteorologischer
    # Saison-Start im genannten Jahr. Ueber denselben _MONTH_YEAR-Regex
    # gepatched, damit "Juni 2024" (Monat) Vorrang vor Seasons hat.
    m = _SEASON_YEAR.match(s)
    if m:
        month = _normalize_season_name(m.group(1))
        year = int(m.group(2))
        if month and 1800 <= year <= 2999:
            return f"{year:04d}-{month:02d}-01"
    # Letzter Versuch: trailing Time-Suffix abschneiden und Datum allein parsen.
    # Faengt nicht-ISO-Eingaben wie "13.06.2024 14:30" oder "13. Juni 2024 10:00" ab.
    stripped = _TRAILING_TIME.sub("", s).strip()
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

    m = _PREFIX_PAIR.search(s)
    if m:
        d1, n1, d2, n2 = m.groups()
        a = _to_float(n1) * _sign(d1)
        b = _to_float(n2) * _sign(d2)
        lat, lon = _orient(a, d1, b, d2)
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
