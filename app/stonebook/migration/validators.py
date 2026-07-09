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
    {"k.a.", "k. a.", "n/a", "na", "?", "-", "—", "unbekannt"}
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
    r"^\s*(\d{4})\s+(?:bis|to|till|until)\s+(\d{4})\s*$",
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
    # Wahrscheinlichkeits-/Vermutungs-Marker (EN)
    r"|perhaps|possibly|maybe"
    r")\s+"
    r"|[~≈]\s*"
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
    r"(?:im|in|am|vom|von|on|aus|w[äa]hrend|waehrend|during)\s+"
    r"(?:(?:dem|den|der|des|the)\s+)?"
    r"(?:(?:jahr|jahre|jahres|jahren|year)\s+)?"
    r"|"
    # Nur "Jahr"-Wort ohne Praeposition (Listen-/Tabellen-Stil)
    r"(?:jahr|jahre|jahres|jahren|year)\s+"
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
_TRAILING_TIME = re.compile(
    r"[Tt ]\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?"
    r"(?:\s*[Zz]|\s*[+-]\d{2}:?\d{2}|\s+[A-Z]{2,5})?\s*$"
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
    r"|\s+(?:UTC|GMT|UT"
    r"|CET|CEST|MEZ|MESZ|WET|WEST|EET|EEST|BST"
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
_TRAILING_ERA_MARKER = re.compile(
    r"\s+(?:"
    r"n\.?\s*chr\.?"           # n. Chr. / n.Chr. / n Chr. / nChr.
    r"|nach\s+christus"        # nach Christus (Vollform)
    r"|v\.?\s*chr\.?"          # v. Chr. / v.Chr. / v Chr. / vChr.
    r"|vor\s+christus"         # vor Christus (Vollform)
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
    r"|perhaps|possibly|maybe"
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
    r"^\s*(\d{4})\s*[,./ \-]\s*([A-Za-zÄÖÜäöü]+)\.?\s*$",
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
    r"^\s*(\d{4})\s*[,./ \-]\s*([A-Za-zÄÖÜäöü]+)\.?\s*"
    r"[,./ \-]\s*(\d{1,2})(?:st|nd|rd|th)?\s*$",
)

# Jahreszeit + Jahr ("Sommer 1985", "Spring 2024", "Frühjahr 2020").
# Konvention: meteorologischer Saison-Start im genannten Jahr (Maerz/Juni/Sep/Dez).
# Winter wird auf Dezember desselben Jahres gelegt.
_SEASON_MONTHS: dict[str, int] = {
    "fruehling": 3, "fruehjahr": 3, "spring": 3,
    "sommer": 6, "summer": 6,
    "herbst": 9, "autumn": 9, "fall": 9,
    "winter": 12,
}
_SEASON_YEAR = re.compile(
    r"^\s*([A-Za-zÄÖÜäöü]+)\.?\s*[, ]?\s*(\d{4})\s*$",
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
    r"^\s*(\d{4})\s*[/.\-, ]\s*([A-Za-zÄÖÜäöü]+)\.?\s*$",
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
_HALFYEAR_SHORT = re.compile(
    r"^\s*(?:H\s*([1-2])|([1-2])\s*H)\s*[/.\-,]?\s*(\d{4})\s*$",
    re.IGNORECASE,
)
# "1. Halbjahr 2024" / "Halbjahr 1 2024" / "2. Halfyear 1985" / "1. Half-Year 2024"
# - Langform symmetrisch zu _QUARTER_LONG. Beide Reihenfolgen (Zahl-vor-Wort
# und Wort-vor-Zahl) werden akzeptiert. Englisch "half year" (zwei Worte) wird
# bewusst nicht erfasst, weil es zu mehrdeutig mit normalen Saetzen waere
# ("the half year ended..."); EN-Form lebt von der Bindestrich-/Compound-
# Variante ("half-year"/"halfyear"), die in Reports der ueblichen Praxis
# entspricht.
_HALFYEAR_LONG = re.compile(
    r"^\s*(?:([1-2])\s*\.?\s*(?:halbjahr|half-?year)"
    r"|(?:halbjahr|half-?year)\s+([1-2]))"
    r"\s*[/.\-, ]?\s*(\d{4})\s*$",
    re.IGNORECASE,
)
# Year-first Halbjahres-Notation ("2024-H1", "2024 H1", "2024H1", "2024-1H")
# - spiegelt _QUARTER_YEAR_FIRST auf die Halbjahres-Achse. Geschaeftsperioden-
# Reports und Excel-Auto-Format sortieren oft Year-First-formatiert
# ("2024-H1" sortiert lexikographisch korrekt vor "2024-H2").
_HALFYEAR_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, ]?\s*(?:H\s*([1-2])|([1-2])\s*H)\s*$",
    re.IGNORECASE,
)
# Year-first Langform-Halbjahr ("2024 1. Halbjahr", "2024 Halbjahr 1",
# "2024-2. Halfyear") - spiegelt _QUARTER_LONG_YEAR_FIRST. Wie bei der
# Quartals-Langform-Year-First werden beide Reihenfolgen innerhalb der
# Langform akzeptiert.
_HALFYEAR_LONG_YEAR_FIRST = re.compile(
    r"^\s*(\d{4})\s*[/.\-, ]?\s*"
    r"(?:([1-2])\s*\.?\s*(?:halbjahr|half-?year)"
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
# DE-Sammler-Vokabular: "Jahrhundert" (Vollform), "Jahrhdt", "Jhrdt", "Jhdt",
# "Jhrd", "Jh"; alle mit optionalem Trailing-Punkt. Ordinaler Punkt nach der
# Jahrhundert-Zahl ("19.") ist im Deutschen ueblich, aber auch die punktlose
# Form ("19 Jahrhundert") kommt in Notizen vor.
_CENTURY_DE = re.compile(
    r"^\s*(\d{1,2})\s*\.?\s*(?:jahrhundert|jahrhdt|jhrdt|jhdt|jhrd|jh)\.?\s*$",
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
    r"^\s*([IVXLCM]+)\s*\.?\s*(?:jahrhundert|jahrhdt|jhrdt|jhdt|jhrd|jh)\.?\s*$",
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
    r"(\d{1,2})\s*\.?\s*(?:jahrhundert|jahrhdt|jhrdt|jhdt|jhrd|jh)\.?\s*$",
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
    r"([IVXLCM]+)\s*\.?\s*(?:jahrhundert|jahrhdt|jhrdt|jhdt|jhrd|jh)\.?\s*$",
    re.IGNORECASE,
)
_RELATIVE_CENTURY_ROMAN_EN = re.compile(
    r"^\s*(Anfang|Mitte|Ende|early|mid|late)[-\s]+"
    r"([IVXLCM]+)\.?\s+(?:century|cent\.?|c\.)\s*$",
    re.IGNORECASE,
)


def _normalize_month_name(name: str) -> int | None:
    key = name.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return _MONTH_NAMES.get(key)


def _normalize_season_name(name: str) -> int | None:
    key = name.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return _SEASON_MONTHS.get(key)
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
_DMS_PREFIX = re.compile(
    r"""([NSEWOnsewo])                          # Himmelsrichtung (obligatorisch, vorne)
        \s*(\d+(?:[.,]\d+)?)\s*°                # Grad + obligatorisches °
        (?:\s*(\d+(?:[.,]\d+)?)\s*['′])?        # optional Minuten
        (?:\s*(\d+(?:[.,]\d+)?)\s*(?:["″]|''))? # optional Sekunden
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
    r"""([-+]?\d+(?:[.,]\d+)?)\s*°?\s*([NSEWOnsewo])?  # erste Zahl + opt. Richtung
        \s*[ \t,;/&]\s*
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
# Gelaeufige Bezeichner vor den eigentlichen Koordinaten: "Lat: 46.5, Lon: 7.5",
# "Breite 46.5 Länge 7.5", "latitude=46.5 longitude=7.5". Werden vor dem
# Pattern-Matching entfernt; die Himmelsrichtung im Label (N/E/S/W als Buchstabe
# in "Lon") ist nicht gemeint und wuerde sonst _PREFIX_PAIR irrefuehren.
_COORD_LABEL = re.compile(
    r"""\b(?:
            latitude | lat | breitengrad | breite
          | longitude | longitudinal | long | lon | laengengrad | laenge
          | längengrad | länge
          | mlat | mlon                # OpenStreetMap-Share-URL-Query-Parameter
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
    if not s or s.lower() in DATE_NO_DATA_MARKERS:
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
    # ist (dir, deg, min, sec) - umsortieren zu (deg, min, sec, dir) fuer den
    # _dms_to_decimal-Aufruf.
    dms_prefix_hits = _DMS_PREFIX.findall(s)
    if len(dms_prefix_hits) >= 2:
        d1, deg1, min1, sec1 = dms_prefix_hits[0]
        d2, deg2, min2, sec2 = dms_prefix_hits[1]
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
