"""Loader für die drei historischen CSV-Formate → Standard-Felddicts."""
import csv
import io
import math
import re
from pathlib import Path

from stonebook.fields import DATA_FIELDS, NUMERIC_TYPES, FIELD_BY_NAME
from stonebook.migration.id_utils import normalize_id
from stonebook.migration.validators import DATE_NO_DATA_MARKERS, parse_iso_date

# Zahl-Token-Regex mit optionaler wissenschaftlicher Notation ``E±N`` (Exponent
# zur Basis 10). In Mineralogie-/Physik-Tabellen und Referenz-Publikationen die
# Standardform fuer Werte, die viele Groessenordnungen ueberspannen: Absorptions-
# Querschnitte in cm² (``2.5e-19``), Halbwertszeiten von Isotopen in Jahren
# (``4.5e9``), Kalibrier-Konstanten aus spektroskopischen Messungen (``1.5e-3``),
# Fluoreszenz-Lebensdauern in Sekunden (``3e-6``). Ohne die Exponent-Alternation
# fielen alle diese Formen auf eine Mehrfach-Zahl-Zerlegung: ``1.5e-3`` wurde
# als zwei Tokens ``1.5`` und ``3`` gelesen und lieferte ``(1.5, 3.0)`` als
# vermeintlicher Range ``1.5 bis 3``; ``1e3`` wurde ``[1.0, 3.0]`` und fiel via
# ``hi < lo``-Fallback auf ``(1.0, 1.0)`` zurueck; ``1.5E+3`` denselben Kollaps
# ueber das ignorierte Vorzeichen des Exponenten. Bei der Migration aus
# wissenschaftlichen Quellen (Sammler kopieren Kalibrier-/Absorptions-Werte
# direkt aus Publikationen oder NIST-CODATA-Tabellen) entstand damit silenter
# Verlust der Groessenordnung - der Wert wurde als Punktwert der Mantisse
# gelesen, die eigentliche Zehnerpotenz fiel weg.
#
# Exponent-Zeichen ``e``/``E`` (case-insensitive per Zeichen-Klasse), optionales
# Vorzeichen ``+``/``-`` und mindestens eine Ziffer. Wird von ``float()``
# automatisch als IEEE-754-Basis-10-Exponent interpretiert (``float("1.5e-3")
# == 0.0015``), sodass die bereits vorhandene ``float(n.replace(",", "."))``-
# Konvertierung in :func:`parse_range` die scientific-notation-Form transparent
# akzeptiert - keine separate Postprocessing-Logik noetig. Locale-Toleranz
# symmetrisch zur bereits vorhandenen Komma-Dezimal-Konvention des Basis-
# Teils: Komma-Dezimal in der Mantisse (``1,5e-3``) wird durch das
# ``.replace(",", ".")`` vor dem ``float()``-Aufruf normalisiert (DE/EU-
# Publikationen und Excel-DE schreiben ``1,5E-03`` mit Komma-Dezimal); der
# Exponent selbst ist ganzzahlig ohne Locale-Problem.
#
# Kollisionsfreiheit zu den bereits vorhandenen Uncertainty-Patterns
# (_PLUS_MINUS_UNCERTAINTY / _PARENTHESIS_UNCERTAINTY): beide fangen vor der
# generischen Zahlen-Extraktion via ^...$-Anker die Publikations-Notation ab
# und lassen den Exponent-Match hier nur bei Freitext-Werten ohne
# Uncertainty-Struktur greifen; die Uncertainty-Basis- und -Toleranz-Zahlen
# bleiben absichtlich ohne Exponent-Alternation, weil die IUCr-/DIN-Uncertainty-
# Konventionen den Exponent nicht innerhalb der ± -/Klammer-Struktur setzen,
# sondern die gesamte Notation getrennt vom Exponent notieren (etwa
# ``2.65e0 ± 5e-2`` wuerde in einer Publikation als ``2.65(5)e0`` geschrieben,
# nicht als Kombination beider Notationen im gleichen Token).
#
# Erste Alternante ``\.\d+`` fängt Leading-Dot-Dezimals wie ``.5`` / ``.05`` /
# ``.5e-3`` (US-typografische Konvention "no leading zero" und wissenschaftliche
# Publikationen mit Punkt-Dezimal ohne fuehrende Null). Ohne diese Alternante
# fiele der Punkt aus dem Match und die Ziffernfolge dahinter wurde als eigene
# Ganzzahl gelesen: ``.5`` lieferte ``[5]`` -> (5.0, 5.0) statt (0.5, 0.5),
# ``.5-.7`` lieferte ``[5, 7]`` -> (5.0, 7.0) statt (0.5, 0.7), und
# ``.5e-3`` (Absorptions-/Kalibrier-Wert in Publikationen ohne fuehrende Null)
# lieferte ``[5, 3]`` -> ueber hi<lo-Fallback (5.0, 5.0) statt (0.0005, 0.0005).
# Bei der Migration aus US-/englischsprachigen Sammlungs-Notizen und aus
# LaTeX-/PDF-Publikationen ohne fuehrende Null entstand damit stille
# Groessenordnungs-Verluste bei allen kleinen Werten (Mikroskopie-Messwerte,
# Foliendicken, Feinkorn-Groessen). Nur Punkt als Leading-Dezimal, nicht Komma:
# leading ``,5`` waere in DE-Locale mehrdeutig (koennte Range-Separator eines
# leeren Werts vor dem Komma sein wie in ``,5`` = zweiter Teil von ``5,5``);
# US-Konvention kennt kein leading-Komma-Dezimal, und Excel-DE schreibt ``0,5``
# statt ``,5``.
#
# Negatives Lookbehind ``(?<![A-Za-z^])`` schuetzt vor der Fehl-Lese der
# hochgestellt-Ersatz-Ziffer in SI-Einheiten: ``cm3``/``m2``/``s2`` sowie die
# ASCII-Caret-Variante ``cm^3``/``m^2``/``s^2`` sind der uebliche Weg, hoch-
# gestellte Ziffern in reinem ASCII zu notieren (Excel-CSV-Exporte, Terminal-
# /Log-Ausgaben, geerbte Sammlungs-Notizen mit 7-bit-ASCII-Codepage, LaTeX-
# Roh-Exporte ohne ``\textsuperscript`` und Foto-EXIF-Kommentare aus Kameras
# ohne Unicode-Support). Ohne dieses Lookbehind fiel die Einheits-Ziffer als
# eigenstaendiger Zahl-Token in nums auf und produzierte mineralogisch
# unsinnige Bereiche: ``"2.65 g/cm3"`` lieferte (2.65, 3.0) statt (2.65, 2.65)
# (die 3 aus ``cm3`` als Range-hi fehlgelesen), ``"5-7 g/cm3"`` lieferte
# (5.0, 5.0) via ``if hi < lo``-Kollaps (nums = [5, 7, 3], hi=3, lo=5 → (5,5),
# Range verloren), ``"2.65 kg/m3"`` lieferte (2.65, 3.0). Bei der Migration
# aus Mineralogie-Publikationen ohne Unicode-Superskript (die aeltere Print-
# Katalog-Praxis oder ASCII-only-Sammlungs-DB-Formate) entstand damit silen-
# ter Range-/Punkt-Wert-Datenverlust. Die Unicode-Superskript-Variante
# ``g/cm³`` (U+00B3) ist bereits korrekt, weil ``³`` kein ASCII-Digit ist
# und daher gar nicht in ``_NUM_RE`` matcht - der Fix schliesst nur die
# ASCII-Fallback-Lücke.
#
# Semantische Reichweite spiegelt die _strip_bracketed_annotations-Konvention:
# Zahlen, die semantisch an Metadaten (Einheit, Bezeichner) gebunden sind,
# duerfen nicht als Wert-Bereichsgrenze gelesen werden. Der Lookbehind blockiert
# ausserdem in Bezeichner-Positionen wie ``Sample3``/``Mineral2``/``B12``, wo
# die Zahl Teil des Namens ist und keine Messgroesse - typisch fuer Katalog-/
# Chargen-Bezeichner in geerbten Excel-Kopien mit einer Wert-Spalte, in der
# Sammler zusaetzlich zum Wert einen Sample-Namen notiert haben ("Sample3
# 2.65 g/cm³" → nur 2.65 ist die Dichte, die 3 in Sample3 ist Sample-Nummer).
# Reines ``e5`` (kein Vorzeichen, kein Mantisse-Teil) verliert das Match, was
# konsistent mit der scientific-notation-Semantik ist: ``e5`` allein ist keine
# gueltige Zahl, sondern ein defekter Exponent-Token; ``5e3`` bleibt korrekt
# ein Ganz-Token (das ``e`` sitzt zwischen zwei Ziffern, nicht am Anfang).
#
# Kollisionsfrei zu scientific notation: ``1e3`` / ``1.5e-3`` matcht als
# Ganz-Token ueber die Alternante ``\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?`` und der
# Lookbehind checkt vor dem fuehrenden Digit, nicht vor dem ``e`` - Publikations-
# Notation aus wissenschaftlichen Quellen bleibt unangetastet. Kollisionsfrei
# zur DMS-Koordinaten-Extraktion in :mod:`stonebook.migration.validators`, weil
# dort ein eigener Parser mit expliziten ``°``/``'``/``"``-Ankern zum Einsatz
# kommt - die Fallback-Zahl-Extraktion via ``_NUM_RE`` gilt hier nicht.
#
# Optionales fuehrendes Minus-Vorzeichen ``(?:(?<![\d.])-)?`` bindet den ASCII-
# Hyphen als Vorzeichen an die folgende Zahl, aber nur wenn das Zeichen VOR
# dem Hyphen kein Digit und kein Dezimalpunkt ist - also nur an Positionen,
# an denen ein ``-`` semantisch ein Vorzeichen sein kann (String-Anfang,
# Whitespace, andere Nicht-Zahl-Separatoren wie ``=``, ``:``, Klammer-
# Rand, andere Dash-Varianten). Bei Digit-vor-Hyphen wie in ``5.5-7.0`` oder
# ``5-7`` (Range-Notation) blockt der Lookbehind das Sign-Match und der
# Hyphen bleibt Range-Separator - die bestehende Range-Semantik bleibt
# unveraendert. Vor dem Fix verwarf die Zahl-Extraktion still jedes fuehrende
# Minus-Zeichen und lieferte ``"-5.5"`` als ``(5.5, 5.5)`` (Vorzeichen
# verloren), ``"-10 - -5"`` (typische Temperatur- oder Tiefen-Range in
# Cryo-/Bergbau-Kontext) als ``[10, 5]`` mit inverted-Range-Kollaps
# ``(10.0, 10.0)`` (beide Vorzeichen verloren, semantisch komplett falsch:
# Kryo-Temperatur -10 bis -5 °C wurde als Werte 10 zu 10 gelesen), ``"-10 -
# 5"`` (Vorzeichen-gemischter Range) analog. Beim Import aus Cryo-
# Mineralogie-Notizen (Frost-/Eis-Kristall-Sammlungen), Bergbau-/Tektonik-
# Tiefen-Berichten (negative Meereshoehe), Isotopen-Fraktionierungs-Werten
# (δ¹³C, δ¹⁸O in ‰ - typisch negativ) oder thermischen Ausdehnungs-
# Koeffizienten (β < 0 bei einigen Kristall-Klassen) entstand damit silen-
# ter Vorzeichen-Datenverlust auf jedem Numeric-Feld, das Nullpunkt-negative
# Werte tragen kann. Der Lookbehind ``(?<![\d.])`` erfasst genau die Positionen,
# an denen ``-`` unzweideutig Vorzeichen ist; die typografischen Minus-Varianten
# (en-dash U+2013, em-dash U+2014, minus U+2212) bleiben Range-Separatoren
# (das Sign-Match ist ASCII-only) - die spezifische Minus-Zeichen-
# Vorzeichen-Rolle des U+2212 aus Print-Katalogen wird in
# :func:`normalize_numeric_locale` per Single-Pass-Strip auf ASCII-Hyphen
# normalisiert (spiegelt den ``parse_coordinates``-Preprocess-Ansatz), damit
# ``"−5.5"`` als ``"-5.5"`` in die Sign-Bindung faellt; en-dash/em-dash
# bleiben unangetastet, weil beide semantisch immer Range-Separatoren sind.
# Der Sign-Lookbehind ``(?<![\d.%‰])-`` schliesst zusaetzlich zum Digit/
# Punkt-Kontext die Prozent-/Promille-Suffixe (``%`` U+0025, ``‰`` U+2030)
# als Vorzeichen-blockierende Vorgaenger aus - beide sind Wert-Terminatoren
# (kein Bestandteil der Zahl, kein Separator innerhalb einer Zahl), sodass
# der ``-`` unmittelbar dahinter unzweideutig Range-Trenner ist. Bisher
# fiel ``"5%-10%"`` durch den zu engen Lookbehind auf ``[5, -10]``, was
# via ``if hi < lo``-Kollaps stille auf ``(5.0, 5.0)`` reduzierte und die
# obere Range-Grenze (10%) verwarf - typische Sammler-Notiz fuer
# Reinheits-/Beimengungs-/Anteil-Angaben in ppm-nahen Konzentrationen
# ("Cu-Gehalt 5%-10%", "Fluid-Einschluss-Salinitaet 3%-8%") mit silenter
# Datenverlust bei der Migration. Der ‰-Zweig spiegelt die Regelung auf
# die Promille-Achse (Isotopen-Fraktionierung δ¹³C, δ¹⁸O sowie Wasser-
# Chemie-Konzentrationen "0.5‰-2.5‰"). Kollisionsfrei zu ``"5% - 10%"``
# (Whitespace um den Bindestrich) - dort blockt die separate Whitespace-
# Sequenz die Sign-Bindung ohnehin, das Fix ist strikt additiv fuer die
# whitespace-lose Notation. Kollisionsfrei zu Negativ-Vorzeichen-Rollen an
# String-Anfang, nach Whitespace oder anderen echten Separatoren (Komma,
# Semikolon, Klammern, Gleichheitszeichen) - dort ist der Vorgaenger
# nicht ``%``/``‰``, und das Sign-Match bleibt aktiv.
# Zweites Lookbehind ``(?<![A-Za-z^]-)`` schuetzt vor Fehl-Lese des SI-Kompakt-
# Exponenten in Einheiten mit negativer Zehnerpotenz: ``g cm-3``, ``kg m-3``
# (Dichte in coherent-SI-Notation), ``m s-1`` (Geschwindigkeit), ``s-1`` (Frequenz-
# Reziprok), ``mol-1`` (Loschmidt-Reziprok), ``A-1``/``Å-1`` (reziproke Basis-
# Vektoren in Roentgen-Beugung), ``cm-3`` (Konzentration/Zerfallsdichte) sowie
# die ASCII-Caret-Variante ``g cm^-3``/``m s^-1``. Diese SI-Kompakt-Form ohne
# Divisions-Slash ist der internationale Publikations-Standard fuer coherent-
# SI-Notation (ISO 80000, IUPAC-Gruen-Buch, IUCr-Style-Guide) und in Mineralogie-/
# Physik-Referenz-Tabellen die kanonische Weise, zusammengesetzte Einheiten mit
# negativer Zehnerpotenz zu setzen ("Dichte 2.65 g cm-3", "Loeslichkeitsprodukt
# 1.5e-9 mol2 kg-2", "Frequenz 100 s-1", "Bragg-Winkel 5.5 A-1"). Bisher
# fielen alle diese Formen still auf Range-Fehl-Interpretation durch: die
# generische ``_NUM_RE``-Extraktion erkannte den ``-``-Trenner zwar als
# Sign-Blocker (durch die Buchstaben-Lookbehind), aber die trailing Ziffer nach
# dem ``-`` fiel als eigenstaendige Zahl in ``nums`` und lieferte via
# ``if hi < lo``-Fallback entweder einen semantisch falschen Range oder einen
# stille (n, n)-Kollaps. Konkret: ``"2.65 g cm-3"`` lieferte ``[2.65, 3.0]`` und
# via ``hi > lo`` den unsinnigen Dichte-Range ``(2.65, 3.0)`` statt ``(2.65,
# 2.65)`` (die 3 aus ``cm-3`` als Range-hi fehlgelesen); ``"2.65 kg m-3"``
# analog auf ``(2.65, 3.0)``; ``"1.5 mol-1"`` auf ``(1.0, 1.5)`` (die 1 aus
# ``mol-1`` als Range-lo). ``"5.5 cm-3"`` fiel via inverted-Range-Fallback auf
# ``(5.5, 5.5)`` (die 3 wurde extrahiert, aber weil 3 < 5.5, kollabierte hi<lo
# auf lo) - der stille Kollaps sah zwar richtig aus, war aber zufaellig, denn
# jede Wert-Notation mit Wert < SI-Exponent produziert weiterhin die falsche
# Range-Interpretation. Bei der Migration aus Mineralogie-/Physik-Publikationen
# mit coherent-SI-Notation (Dichte 1-4 g cm-3, Konzentrationen um 1 mol-1,
# spektroskopische Bragg-Winkel 1-10 A-1) entstand damit silenter Range-
# Fehl-Interpretations-Fehler auf jeder Wert-Achse mit SI-Kompakt-Einheit.
#
# Neues Lookbehind ``(?<![A-Za-z^]-)`` prueft die zwei Zeichen vor dem Match-
# Start und blockiert, wenn ``[Buchstabe|Caret][Hyphen]`` als 2-Zeichen-Sequenz
# unmittelbar vorausgeht - genau die SI-Kompakt-Exponenten-Signatur. Die
# einzelne Zahl-Position wird durchgelassen, wenn das 2-Zeichen-Fenster ANDERS
# aussieht: ``"5 -3"`` (Whitespace-Hyphen, kein Buchstabe im Fenster) bleibt
# echte Range, ``"x=-3.5"`` / ``"value:-3.5"`` (Punkt/Doppelpunkt/Gleich vor
# Hyphen) bleibt Sign-Bindung, ``"(-3.5, 4.5)"`` (Klammer vor Hyphen) bleibt
# Sign-Bindung. Der Existenz-basierte Sign-Zweig oben (``(?<![\d.%‰])-``) und
# das neue Lookbehind sind strukturell disjunkt: der Sign-Zweig operiert
# innerhalb des Match-Bodies (optionale Vorzeichen-Anbindung an eine
# nachfolgende Ziffer), das neue Lookbehind operiert an der Match-Start-
# Position (blockiert ganze Position). Beide zusammen ergeben die vollstaen-
# dige SI-Kompakt-Einheit-Absicherung: der ``-`` wird nie als Sign gebunden
# (Sign-Zweig blockt durch Buchstaben-Lookbehind auf der ``-``-Position, siehe
# oben) UND die Ziffer nach ``-`` wird nicht als eigenstaendige Zahl extrahiert
# (neues Lookbehind blockt auf der Ziffer-Position).
#
# Kollisionsfreiheit zu Sign-Rollen: der Zweig blockiert NUR das 2-Zeichen-
# Fenster ``[Buchstabe|Caret][Hyphen]``. Alle uebrigen Kontexte, in denen ein
# Hyphen als echter Sign fungiert, bleiben unberuehrt - Zeilenanfang (``"-3"``),
# nach Whitespace (``"5 -3"``), nach Komma/Semikolon/Klammer/Gleichheitszeichen
# (``"(-3.5, 4.5)"``, ``"x=-3.5"``, ``"value:-3.5"``), nach anderen Nicht-
# Buchstaben-Separatoren (`.replace(",", ".")`-Nachbereitung). Kollisionsfrei
# zu Range-Semantik: die Range-Trenner-Rolle des Hyphens zwischen zwei Zahlen
# (``"5-7"``, ``"5.5-3.2"``) hat auf der ersten Ziffer der zweiten Zahl das
# 2-Zeichen-Fenster ``[Ziffer][Hyphen]`` - ``[Ziffer]`` ist nicht ``[A-Za-z^]``,
# das Lookbehind passiert, die Range-Extraktion bleibt intakt.
_NUM_RE = re.compile(
    r"(?<![A-Za-z^])(?<![A-Za-z^]-)"
    r"("
    r"(?:(?<![\d.%‰])-)?"
    r"(?:\.\d+(?:[eE][+-]?\d+)?|\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)"
    r")"
)

# Annaeherungs-Praefix am String-Anfang ("ca.", "circa", "about", "approx.",
# "estimated", "um", "etwa", "vermutlich", "geschaetzt", "~", "≈" ...).
# Spiegelt :data:`stonebook.migration.validators._APPROX_PREFIX` auf die
# Wert-Achse: identische Vokabel-Liste, identisches Zweig-Layout, identische
# Case-Insensitivitaet und identisches Symbol-Set (Tilde ``~`` U+007E,
# Almost-Equal ``≈`` U+2248). In Publikationen, Auktions-Katalogen und
# Sammler-Notizen wird die Approximations-Vokabel oft mit publizierter
# Standard-Unsicherheit kombiniert ("ca. 2.65 ± 0.05 g/cm³", "approx 5.5 ±
# 0.3 Mohs", "~7.4(15) HV", "circa 5.5(3) mm"). Bisher fielen alle
# Kombinationen "Praefix + Uncertainty-Notation" still auf die Fallback-
# Zahl-Extraktion durch, weil sowohl :data:`_PLUS_MINUS_UNCERTAINTY` als auch
# :data:`_PARENTHESIS_UNCERTAINTY` per ``^...$``-Anker eine reine Zahl am
# String-Anfang verlangen; der Approximations-Praefix stand vor der Center-
# Zahl und verhinderte den Uncertainty-Match. Ohne diesen Fix lieferte
# ``"ca. 5.5 ± 0.3"`` (5.5, 5.5) statt (5.2, 5.8), ``"approx 2.65(5)"``
# ueber inverted-Range-Kollaps ebenfalls (2.65, 2.65) statt (2.60, 2.70) -
# die publizierte Standard-Unsicherheit ging bei jeder mit Approximations-
# Marker versehenen Wert-Zelle stille verloren, obwohl die Marker semantisch
# nur die Praezision des Zentrums modifizieren, nicht die Toleranz-Struktur.
# Bei der Migration aus wissenschaftlichen Publikationen (Sammler kopieren
# Dichte-/Haerte-Werte samt Approximations-Marker aus IUCr-/NIST-Tabellen)
# und aus Auktions-Katalogen (Preis-Schaetzungen mit publizierter Streuung)
# entstand damit silenter Praezisions-Datenverlust auf jeder Wert-Achse mit
# Approximations-Marker.
#
# Wird in :func:`parse_range` nach den Fraktions-Normalisierungen und vor
# den Uncertainty-Patterns via ``.match`` erkannt und einmalig gestrippt
# (analog zum :func:`stonebook.migration.validators.parse_iso_date`-Muster
# mit :data:`_APPROX_PREFIX`); die verbleibende Wert-Struktur laeuft dann
# in die normale Pipeline (Uncertainty-Match oder Fallback-Zahl-Suche) und
# liefert die publizierte Toleranz korrekt als Bereichsgrenzen. Idempotent
# bei mehrfacher Anwendung, weil die Fallback-Zahl-Suche bereits ohne Anker
# arbeitet und daher jeden Wert korrekt findet - der Praefix-Strip fixt nur
# die Uncertainty-Anker-Kollision.
#
# Wort-Vokabeln verlangen mindestens ein Leerzeichen zur Trennung von der
# Wert-Zahl (``ca. 5.5`` OK, ``ca5.5`` blockt), damit "ca" nicht
# irrtuemlich in Bezeichner-Namen (Sample-IDs "ca17", Mineral-Katalog-
# Nummern "ca42") oder in Einheiten-Kompositionen (z.B. Compound-Namen)
# als Approximations-Marker fehlgelesen wird. Die symbolischen Marker
# ``~``/``≈`` erlauben auch null Leerzeichen (``~5.5`` und ``~ 5.5`` sind
# beide semantisch gleich), spiegelt die Symbolic-Marker-Konvention aus
# :data:`stonebook.migration.validators._APPROX_PREFIX`. Umlaut- und
# Transliterations-Varianten (``ungef[äa]hr``/``ungefaehr``, ``sch[äa]tzungs-
# weise``/``schaetzungsweise``, ``gesch[äa]tzt``/``geschaetzt``, ``m[öo]glicher-
# weise``/``moeglicherweise``) parallel wie im Datums-Praefix - Windows-CP1252/
# Excel-DE nativ vs. 7-bit-ASCII-Notizen aus Terminal-/E-Mail-/LaTeX-Quellen.
# FR-/IT-Annaeherungs-Marker (Suisse romande / Ticino / Val d'Aosta): ``vers`` (FR)
# = "gegen"/"um", ``environ`` (FR) = "ungefaehr", ``verso`` (IT) = "gegen"/"um",
# ``attorno`` (IT, bare Praefix-Form ohne Artikel-Kontraktion). ``circa`` ist zwar
# IT-Vokabular, aber via Latin-Wurzel bereits im DE-/EN-Block oben abgedeckt.
# Spiegelt strukturell den identischen FR/IT-Block aus
# :data:`stonebook.migration.validators._APPROX_PREFIX` auf die Wert-Achse. Sammler-
# Notizen aus franzoesisch-sprachigen Alpen-Fundorten (Wallis/Val d'Anniviers,
# Chamonix, Mont-Blanc) und aus italienisch-sprachigen Ticino-/Val-d'Aosta-
# Sammlungen (Museo cantonale di storia naturale, "Rivista Mineralogica Ticinese"-
# Etiketten) nutzen diese Vokabeln fuer approximierte Wert-Angaben ebenso wie fuer
# approximierte Datums-Angaben - "vers 500 CHF" fuer eine Preis-Schaetzung ohne
# publizierte Streuung, "verso 5.5 Mohs" fuer eine Haerte-Naeherung ohne exakte
# Messung, "environ 2.65 ± 0.05 g/cm³" fuer eine Dichte-Schaetzung mit publizierter
# Standard-Unsicherheit aus einer FR-sprachigen Referenz-Tabelle. Bisher fielen
# alle FR/IT-Praefix-Formen still auf die Fallback-Zahl-Extraktion durch, obwohl
# semantisch identisch zu ``ca.``/``circa``/``etwa`` - Analog zum DE/EN-Block ist
# der Effekt bei Uncertainty-Kombinationen ("environ 2.65 ± 0.05") ein Praezisions-
# Verlust: die publizierte Toleranz kollabiert via ``[center, tol]``-inverted-Range
# auf ``(center, center)``. Kollisions-Schutz durch das gemeinsame ``\s+``-Suffix:
# ``vers`` matcht nicht in ``versichert``/``verse``/``versa``; ``environ`` nicht in
# ``environment``/``environments``; ``verso`` nicht in ``versoehnung``/``version``;
# ``attorno`` hat keinen DE/EN-Wortstamm-Konflikt.
#
# Die Symbolic-Marker-Klasse ``[~≈≅≃]`` deckt neben ASCII-Tilde (U+007E) und
# Almost-Equal (``≈`` U+2248) auch die beiden weiteren, in Physik-/Engineering-/
# Mineralogie-Publikationen gebraeuchlichen Unicode-Naeherungs-Symbole ab:
# ``≅`` (U+2245, "APPROXIMATELY EQUAL TO", der LaTeX-Befehl ``\cong`` rendert
# genau dieses Zeichen) und ``≃`` (U+2243, "ASYMPTOTICALLY EQUAL TO", LaTeX
# ``\simeq``). Beide sind in Print-Publikationen und in aus LaTeX exportierten
# Datenbank-CSVs verbreitete Naeherungs-Marker mit semantisch identischer
# Bedeutung zu ``≈``/``~`` - "der Wert ist ungefaehr X". Bisher fielen alle
# Formen mit diesen zwei Marker-Varianten still auf die Fallback-Zahl-
# Extraktion durch, weil die Zeichenklasse nur ``~`` und ``≈`` enthielt; bei
# Kombination mit Uncertainty ("≅ 5.5 ± 0.3", "≃ 2.65(5)") fiel ausserdem die
# publizierte Toleranz ueber den ``[center, tol]``-inverted-Range-Kollaps auf
# ``(center, center)`` still verloren - identischer Bug-Effekt wie bei
# ``~``/``≈`` vor Einfuehrung dieser Klasse. Sammler-Notizen aus wissenschaft-
# lichen Publikationen (IUCr-/NIST-/RRUFF-Tabellen mit ``≅``-annotierten
# Referenz-Werten) und aus LaTeX-Autoformat-Quellen (``\cong``/``\simeq``
# rendert Print zu ``≅``/``≃``) entstand damit silenter Praezisions-Datenverlust
# auf jeder Wert-Achse mit diesen zwei Symbolen. Der Fix ist strukturell strikt
# additiv - keine bestehende Match-Semantik veraendert sich. Case-Neutralitaet
# ist bei Symbolen ohne Case-Distinktion nicht wirksam, aber re.IGNORECASE
# bleibt fuer die Wort-Vokabeln in der Alternate-Kette weiterhin aktiv.
_APPROX_VALUE_PREFIX = re.compile(
    r"^\s*(?:"
    r"(?:ca\.?|circa|approx\.?|approximately"
    r"|around|about|roughly|estimated|est\."
    r"|um|gegen|etwa|vermutlich"
    r"|sch[äa]tzungsweise|schaetzungsweise"
    r"|ungef[äa]hr|ungefaehr"
    r"|gesch[äa]tzt|geschaetzt"
    r"|wahrscheinlich|m[öo]glicherweise|moeglicherweise"
    r"|evtl\.?|eventuell"
    r"|perhaps|possibly|maybe|presumably"
    # Hearsay-/Zuschreibungs-Marker (DE ``angeblich`` sowie EN ``allegedly``/
    # ``supposedly``/``reportedly``/``purportedly``) - spiegelt strukturell die
    # bereits in :data:`stonebook.migration.validators._APPROX_PREFIX` gepflegte
    # Hearsay-Marker-Menge auf die Wert-Achse. In geerbten Sammlungs-Notizen,
    # Museums-Etiketten und Auktions-Katalog-Provenienz-Eintraegen setzt der
    # Vorbesitzer/Kurator/Auktionator den Hearsay-Marker vor die Wert-Angabe,
    # wenn die Preis-/Gewichts-/Dichte-/Haerte-Aussage aus zweiter Hand kommt
    # (Verkaeufer-Angabe, Vorbesitzer-Erzaehlung, Katalog-Referenz statt eigener
    # Messung/Bewertung): "angeblich 500 CHF Marktwert laut Vorbesitzer",
    # "angeblich 2.65 g/cm3 Dichte aus altem Etikett", "allegedly 500 CHF from
    # the seller's estimate", "supposedly Mohs 7 per the old label", "reportedly
    # 5.5 g weight from an unverified source", "purportedly a Mohs 8 hardness
    # per the auction catalogue". Semantisch identisch zu ``vermutlich``/
    # ``wahrscheinlich``/``perhaps``/``possibly`` (Unsicherheits-Marker mit
    # dokumentierter Herkunfts-Fragezeichen), aber auf der Hearsay-Achse (Wert
    # stammt aus Erzaehlung/Zuschreibung, nicht aus eigener Messung) - Strip +
    # Rekursion wie bei den uebrigen Wahrscheinlichkeits-Marken, das Range-
    # Tupel-Output ist identisch zur reinen Form (der Hearsay-Marker gehoert
    # konzeptionell in die notizen-Spalte, nicht in die numerische Bereichs-
    # Grenze). ``presumably`` (EN-Wahrscheinlichkeits-/Vermutungs-Marker,
    # bereits in :data:`stonebook.migration.validators._APPROX_PREFIX` gepflegt)
    # wird symmetrisch zu ``vermutlich`` in derselben Alternation aufgenommen -
    # spiegelt die EN-Standard-Vermutungs-Notation aus akademischen
    # Publikationen und aus englisch-sprachigen Sammler-Notizen.
    #
    # Bisher fielen alle Hearsay-Praefix-Formen still auf die Fallback-Zahl-
    # Extraktion durch: die Uncertainty-Patterns :data:`_PLUS_MINUS_UNCERTAINTY`
    # / :data:`_PARENTHESIS_UNCERTAINTY` sind per ``^\s*(-?\d ...)``-Anker
    # gebunden und matchen nicht, wenn der String mit einem Nicht-Ziffer-Marker
    # beginnt, der nicht in der Approx-Praefix-Whitelist steht. Die publizierte
    # Standard-Unsicherheit ging via ``[center, tol]``-inverted-Range-Kollaps
    # ``(center, center)`` still verloren - identischer Bug-Effekt wie bei
    # ``"ca. 5.5 ± 0.3"`` vor Einfuehrung der uebrigen Approx-Marker in
    # :data:`_APPROX_VALUE_PREFIX`: aus ``"angeblich 500 ± 50 CHF"``
    # entstand silenter Toleranz-Datenverlust (Range (450, 550) kollabierte
    # auf (500, 500)); analog fuer ``"allegedly 5.5 ± 0.3"`` /
    # ``"reportedly 2.65(5)"`` / ``"purportedly 500 ± 50 EUR"`` /
    # ``"supposedly 5.5 +/- 0.3"`` und alle Verkettungen mit Leading-Waehrungs-
    # Marker (``"angeblich CHF 500 ± 50"`` via zweifacher Rekursion) oder mit
    # Trailing-Approx-Marker (``"angeblich 500 ± 50, ca."`` via Leading-Strip
    # gefolgt vom Trailing-Strip). Kollisionsfrei zu den bestehenden Wahr-
    # scheinlichkeits-/Approx-Markern (lexikalisch disjunkt); Kollisions-Schutz
    # gegen Fremdwoerter durch das obligatorische ``\s+``-Suffix in der
    # Praefix-Regex (``angeblich`` matcht nicht in ``angeblichkeit``/anderen
    # nicht-Standard-Ableitungen, weil dort kein Whitespace folgt; ``allegedly``/
    # ``supposedly``/``reportedly``/``purportedly``/``presumably`` sind
    # lexikalisch eindeutige Adverb-Formen ohne DE-/FR-/IT-Wortstamm-Konflikt).
    # Case-insensitive spiegelt die uebrige Marker-Menge.
    r"|angeblich|allegedly|supposedly|reportedly|purportedly"
    r"|vers|environ|verso|attorno"
    r")\s+"
    r"|[~≈≅≃]\s*"
    r")",
    re.IGNORECASE,
)

# Leading-Waehrungs-Prefix am String-Anfang ("CHF 500 ± 50", "$500 ± 50",
# "EUR 5.5(3) g/cm³", "€500 ± 50"). Spiegelt strukturell die
# :data:`_APPROX_VALUE_PREFIX`-Strip-Logik auf die Waehrungs-Achse: ohne
# Strip fielen alle Formen mit Leading-Waehrungs-Marker UND Uncertainty-
# Struktur still auf die Fallback-Zahl-Extraktion durch, weil sowohl
# :data:`_PLUS_MINUS_UNCERTAINTY` als auch :data:`_PARENTHESIS_UNCERTAINTY`
# per ``^\s*(-?\d ...)``-Anker eine Zahl (oder Vorzeichen) am String-Anfang
# verlangen. Die publizierte Standard-Unsicherheit ging via
# ``[center, tol]``-inverted-Range-Kollaps ``(center, center)`` still
# verloren - identischer Bug-Effekt wie bei ``"ca. 5.5 ± 0.3"`` vor
# Einfuehrung von :data:`_APPROX_VALUE_PREFIX`.
#
# In Auktions-Katalogen (Christie's, Bonhams, Sotheby's Fine Mineral,
# "Rocks & Minerals"-Zeitschrift) und in Erbschafts-/Boersen-Schaetzungen
# ist die Leading-Waehrungs-Konvention Standard (``CHF 500 ± 50``, ``$500
# ± 50``, ``EUR 500 ± 50``, ``€500 ± 50``); die Trailing-Form (``500 CHF
# ± 50``, ``500 ± 50 CHF``) ist bereits ueber die Trailing-Einheit-
# Alternate in :data:`_PLUS_MINUS_UNCERTAINTY` abgedeckt. Der Praefix-
# Strip macht die Symmetrie zwischen Leading- und Trailing-Waehrungs-
# Marker vollstaendig und macht die Auktions-/Publikations-Migration
# verlustfrei fuer Wert-Zellen mit Standard-Unsicherheit.
#
# ISO-4217-Code-Whitelist deckt die G10-Waehrungen (CHF, EUR, USD, GBP,
# JPY, CAD, AUD, NZD, SEK, NOK, DKK) plus die in internationalen Mineral-
# Auktionen gebraeuchlichen Zusatz-Waehrungen (PLN, CZK, HUF, RUB, CNY,
# HKD, SGD, INR, AED, ILS, ZAR, BRL, MXN, TRY, THB, KRW) ab. ``\b``
# (Wortgrenze) hinter dem Code verhindert Kollision mit Fremdwoertern,
# die zufaellig mit den gleichen Buchstaben beginnen (``USDA 500`` -
# US-Landwirtschafts-Ministerium; ``SEKtoren 500``; ``AUDio 500``;
# ``NOKia 500``; ``PLNe 500``; ``CNYanide 500``): zwischen Code-Endung
# und Fremdwort-Fortsetzung liegt keine Wortgrenze, weil beide Zeichen
# Wortzeichen sind. Case-Insensitiv, weil Sammler-Notizen in Excel-
# Autocorrect-Kontexten sowohl uppercase (Standard-ISO-Form) als auch
# lowercase (``chf 500``, ``usd 500``, verbreitet in geerbten Notizen
# aus Konsolen-Tools ohne Caps-Lock) verwenden.
#
# Waehrungs-Symbole (Ein-Zeichen-Marker am String-Anfang): $ (USD), €
# (EUR), £ (GBP), ¥ (JPY/CNY), ¢ (Cent), ₹ (INR), ₩ (KRW), ₽ (RUB), ₺
# (TRY), ₪ (ILS), ₣ (French Franc, historisch), ₦ (NGN), ₫ (VND), ₴
# (UAH), ₵ (GHS). Optionale Compound-$-Prefixes (HK$, US$, NZ$, AU$,
# CA$, SG$, NT$) erfassen die verbreiteten Nicht-USD-$-Waehrungen aus
# internationalen Auktions-Katalogen; der 2-Buchstaben-Prefix ist
# uppercase-only, weil lowercase (``hk$500``) in der Praxis nicht
# auftaucht und die Case-Sensitivitaet der Compound-Prefixe die
# Kollisions-Sicherheit gegen zufaellig-2-Buchstaben-plus-$-Sequenzen
# in freien Notizen erhoeht.
#
# Wird in :func:`parse_range` nach dem :data:`_APPROX_VALUE_PREFIX`-Strip
# und vor dem :data:`_APPROX_VALUE_SUFFIX`-Strip einsortiert (via
# Rekursion), damit die Verkettung "Approx-Marker + Waehrungs-Marker" in
# beiden Reihenfolgen transparent aufloest: "ca. CHF 500 ± 50" -> Approx-
# Strip -> "CHF 500 ± 50" -> Waehrungs-Strip -> "500 ± 50" -> Uncertainty-
# Match; "CHF ca. 500 ± 50" -> Approx-Strip blockt (Anker), Waehrungs-
# Strip -> "ca. 500 ± 50" -> Rekursion -> Approx-Strip -> "500 ± 50" ->
# Uncertainty-Match.
_LEADING_CURRENCY_PREFIX = re.compile(
    r"^\s*(?:"
    r"(?:CHF|EUR|USD|GBP|JPY|CAD|AUD|NZD|SEK|NOK|DKK"
    r"|PLN|CZK|HUF|RUB|CNY|HKD|SGD|INR|AED|ILS|ZAR"
    r"|BRL|MXN|TRY|THB|KRW)\b"
    r"|(?:HK|US|NZ|AU|CA|SG|NT)\$"
    r"|[$€£¥¢₹₩₽₺₪₣₦₫₴₵]"
    r")\s*",
    re.IGNORECASE,
)

# Trailing Annaeherungs-Suffix am String-Ende: spiegelt :data:`_APPROX_VALUE_PREFIX`
# auf die Suffix-Achse, strukturell identisch zu :data:`stonebook.migration.validators.
# _TRAILING_APPROX_SUFFIX` fuer die Wert-Achse. Sammler-Notizen aus geerbten
# Etiketten/Katalogen setzen den Praezisions-Marker regelmaessig NACH dem Wert
# ("5.5 ca.", "2.65 g/cm³ circa", "500 CHF geschaetzt", "Dichte 2.65 ± 0.05,
# ca.") - typische Reihenfolge in handschriftlichen Etiketten und in
# Excel-CSV-Zeilen, wo der Nutzer den Wert eingibt und den Praezisions-Marker
# nachtraeglich anfuegt.
#
# Bei reinen Wert-Zellen ohne Uncertainty-Struktur ("5.5 ca.", "500 vermutlich")
# ist der Effekt der Trailing-Form verlustfrei via Fallback-Zahl-Extraktion
# ((5.5, 5.5) bleibt (5.5, 5.5), die Approximations-Semantik geht in die
# notizen-Spalte). Kritisch ist die Kombination mit Uncertainty-Notation, in
# der eine Trennung des Wert-Ausdrucks vom Marker via Komma steht - genau die
# in Sammler-Notizen verbreitete Notation "5.5 ± 0.3, ca.", "2.65(5), circa",
# "2.65 g/cm³ ± 0.05, ungefaehr". Die Uncertainty-Patterns
# :data:`_PLUS_MINUS_UNCERTAINTY` / :data:`_PARENTHESIS_UNCERTAINTY` absorbieren
# Trailing-Tokens ohne Komma (der Trailing-Token-Loop in beiden Patterns
# akzeptiert ``ca.``/``circa``/``geschaetzt`` als Einheit-aehnliche Tokens),
# aber eine ``,`` bricht die Token-Kette und das End-Anker-Matching schlaegt fehl.
# Ohne Suffix-Strip fielen alle Komma-getrennten Formen still auf die Fallback-
# Zahl-Extraktion durch und lieferten via ``[center, tol]``-inverted-range-
# Kollaps ``(center, center)`` (Toleranz verloren) - identischer Bug-Effekt
# wie in der Leading-Form vor Einfuehrung von :data:`_APPROX_VALUE_PREFIX`.
#
# Marker-Menge spiegelt :data:`_APPROX_VALUE_PREFIX` MINUS die als Trailing-Form
# nicht praxisrelevanten Vokabeln: ``um``/``gegen`` (starke Praepositions-
# Ambivalenz - "5 um Grenze zu setzen" waere fehlinterpretiert), ``~``/``≈``
# (typografische Marker konventionell nur als Praefix, spiegelt die
# _TRAILING_APPROX_SUFFIX-Konvention in validators.py), ``vers``/``environ``/
# ``verso``/``attorno`` (FR/IT-Praepositionen, in typischer FR/IT-Sammler-Notation
# nur als Praefix vor dem Wert - "vers 500 CHF" ja, "500 CHF vers" nein, spiegelt
# die Praeposition-nur-links-Konvention der Sprach-Konvention selbst).
#
# ``[\s,]+`` als Trenner vor dem Marker (statt reinem ``\s+``): akzeptiert
# sowohl reine Whitespace-Trennung ("5.5 ± 0.3 ca.", die typographisch saubere
# Form ohne Interpunktion zwischen Wert-Ausdruck und Marker) als auch die
# Komma-getrennte Sammler-Notation ("5.5 ± 0.3, ca.", die in geerbten Notizen
# haeufigere Form mit Komma-Trenner). Erweitert damit die von
# :data:`stonebook.migration.validators._TRAILING_APPROX_SUFFIX` verwendete
# reine ``\s+``-Trennung auf die Wert-Achse-spezifische Notation - Datums-
# Zellen enthalten praktisch nie ein Komma vor dem Praezisions-Marker
# ("13.06.2024, ca." ist sehr unueblich), Wert-Zellen mit Uncertainty-Struktur
# ("5.5 ± 0.3, ca.") aber sehr wohl.
#
# ``\s*[.,;:!?]?\s*$`` erlaubt ein einzelnes Trailing-Satzzeichen nach dem
# Marker: ``ca.`` (der Marker selbst enthaelt Punkt, ``ca\.?`` matcht ihn) ohne
# weiteren Punkt, ``circa.`` (Marker ohne Punkt + Zeilen-End-Punkt aus Excel-
# Autocomplete), ``geschaetzt,`` (Marker + Freitext-Fortsetzung wurde bereits
# als "..., ca." bzw. anderer Punkt-Setz-Konvention abgetrennt und liegt vor
# dem letzten Marker). Case-insensitiv (Excel-Autocorrect "Ca."/"Circa"/
# "GESCHAETZT"). Wird in :func:`parse_range` NACH dem :data:`_APPROX_VALUE_PREFIX`-
# Strip einsortiert, damit Leading- und Trailing-Strip in einer Rekursion
# verkettet werden koennen ("ca. 5.5 ± 0.3, ca." -> Leading-Strip auf
# "5.5 ± 0.3, ca." -> Rekursion greift den Trailing-Strip).
_APPROX_VALUE_SUFFIX = re.compile(
    r"[\s,]+(?:"
    r"ca\.?|circa|approx\.?|approximately"
    r"|around|about|roughly|estimated|est\."
    r"|etwa|vermutlich"
    r"|sch[äa]tzungsweise|schaetzungsweise"
    r"|ungef[äa]hr|ungefaehr"
    r"|gesch[äa]tzt|geschaetzt"
    r"|wahrscheinlich|m[öo]glicherweise|moeglicherweise"
    r"|evtl\.?|eventuell"
    # ``presumably`` als EN-Wahrscheinlichkeits-/Vermutungs-Marker in der
    # Trailing-Achse - spiegelt den bereits in :data:`_APPROX_VALUE_PREFIX`
    # (Leading), :data:`stonebook.migration.validators._APPROX_PREFIX`
    # (Datums-Leading) und :data:`stonebook.migration.validators._TRAILING_APPROX_SUFFIX`
    # (Datums-Trailing) gefuehrten Eintrag auf die letzte fehlende Achse.
    # Semantisch identisch zu ``vermutlich``/``wahrscheinlich``/``perhaps``/
    # ``possibly``/``maybe`` (Unsicherheits-Marker), die alle in der Trailing-
    # Menge stehen; die bisherige Auslassung war eine reine Symmetrie-Luecke.
    # Bisher fielen alle Trailing-Formen mit ``presumably`` nach Komma-Trenner
    # still auf die Fallback-Zahl-Extraktion durch: ``_PLUS_MINUS_UNCERTAINTY``
    # / ``_PARENTHESIS_UNCERTAINTY`` ankern per ``^...$``, und ``,\s*presumably``
    # nach dem Uncertainty-Ausdruck bricht das End-Anker-Matching, sodass
    # ``"5.5 ± 0.3, presumably"`` via inverted-range-Kollaps ``(5.5, 5.5)``
    # lieferte (Toleranz verloren); analog fuer ``"2.65(5), presumably"``,
    # ``"500 ± 50 CHF, presumably"``, ``"2.65 ± 0.05 g/cm³, presumably"`` und
    # die Verkettung mit Leading-Approx-Marker (``"ca. 5.5 ± 0.3, presumably"``
    # via Leading-Strip + Rekursion). Der Suffix-Strip liefert die identische
    # ``(5.2, 5.8)`` bzw. ``(2.6, 2.7)`` bzw. ``(450, 550)`` wie die etablierten
    # Marker der Menge (``possibly``, ``vermutlich``, ``wahrscheinlich``).
    r"|perhaps|possibly|maybe|presumably"
    r")\s*[.,;:!?]?\s*$",
    re.IGNORECASE,
)

# ASCII-Ersatzformen des Unicode-±-Praefix am String-Anfang: ``+/-`` (Standard-
# ASCII-Ersatz aus 7-bit-Mail-Transports, Terminal-Ausgaben, LaTeX-Roh-Exporten)
# und ``+-`` (kompakte ASCII-Form, verbreitet in Excel-CSV-Kopien mit Character-
# Set-Verlust und in geerbten Text-Notizen). Spiegelt strukturell die transparente
# Naturalisierung des Unicode-``±``-Praefix durch :data:`_NUM_RE`: das Symbol
# ist non-digit und wird als Vorzeichen-blockierendes Zeichen von der
# Sign-Alternante durchgelassen, sodass die folgende Ziffer als positiver
# Center-Wert extrahiert wird - ``±5.5`` -> (5.5, 5.5), semantisch "5.5 mit
# implizite Unsicherheit". Die Trailing-Uncertainty-Form ``5.5 +/- 0.3`` /
# ``5.5 +- 0.3`` ist bereits ueber :data:`_PLUS_MINUS_UNCERTAINTY` abgedeckt
# (dort matcht der ``\+/-|\+-``-Zweig zwischen Center und Toleranz-Zahl); der
# Leading-Praefix-Strip macht die Symmetrie zwischen Trailing- und Leading-
# ASCII-Marker vollstaendig und schliesst die letzte Kollision zwischen den
# Unicode- und ASCII-Formen der Uncertainty-Notation.
#
# Ohne diesen Strip ergibt sich eine silente Vorzeichen-Inversion bei ASCII-
# Formen OHNE Whitespace zwischen Marker und Wert - eine typische Notation
# aus Hand-Notation und aus Terminal-/Mail-Copy-Paste ohne Whitespace-Pflege:
#
#   ``"± 5.5"``    -> (5.5, 5.5)    (Unicode-±: naturally works via _NUM_RE-Skip)
#   ``"± 5.5"``    -> (5.5, 5.5)    (Unicode-± ohne Whitespace: naturally works)
#   ``"+/- 5.5"``  -> (5.5, 5.5)    (ASCII mit Whitespace: naturally works)
#   ``"+/-5.5"``   -> (-5.5, -5.5)  (ASCII OHNE Whitespace: silente Sign-Inversion)
#   ``"+-5.5"``    -> (-5.5, -5.5)  (ASCII kompakt ohne Whitespace: silente Sign-Inversion)
#
# Ohne Whitespace faellt der Trailing-``-`` des ASCII-Markers in _NUM_RE
# unmittelbar vor die Ziffer, wird von der ``(?:(?<![\d.])-)?``-Sign-Alternante
# als Vorzeichen an die folgende Zahl gebunden und das Ergebnis ist ein
# negativer Center-Wert - wo semantisch ein positiver Center mit implizite
# Unsicherheit gemeint war. Bei der Migration aus Text-Notizen, Terminal-
# Ausgaben (Diagnose-Reports mit ``+/-``-Toleranz-Notation, oft ohne
# Whitespace geschrieben) und Excel-CSV-Zeilen mit Character-Set-Verlust
# (``±`` -> ``+/-``-ASCII-Fallback) entsteht damit silenter Vorzeichen-
# Datenverlust auf jeder Wert-Zelle mit Leading-ASCII-±-Marker - der Wert
# wird bei jeder Auswertung (Statistik-Report, Sortierung, JSON-Export) mit
# invertiertem Vorzeichen gefuehrt.
#
# ``\+/?-`` matcht beide ASCII-Formen: ``+/-`` (mit Slash-Trenner, die
# verbreitete ASCII-Konvention) und ``+-`` (ohne Slash, die kompakte Form).
# ``\s*`` erlaubt optionale Whitespace-Trennung zwischen Marker und Wert
# (idempotent zum naturally-working Whitespace-Fall - der Strip wirkt sich
# dort semantisch nicht aus, weil _NUM_RE die positive Zahl ohnehin
# extrahiert hat). Das Lookahead ``(?=[.\d])`` fordert eine Ziffer oder
# leading-dot-Dezimal (``.5`` = 0.5) unmittelbar nach dem Marker (ggf. mit
# Whitespace dazwischen), damit der Strip *nicht* auf pathologische
# Sequenzen wie ``+/-abc`` oder ``+/-`` allein greift (dort faellt der
# Strip ohnehin sinnvoll auf die Fallback-Zahl-Suche durch, aber der
# Lookahead macht den Guard explizit und schuetzt vor kuenstlichen
# Konflikten mit spaeter eingefuehrten Marker-Patterns).
#
# Wird in :func:`parse_range` nach :data:`_APPROX_VALUE_PREFIX` und
# :data:`_LEADING_CURRENCY_PREFIX` einsortiert, damit die Verkettung
# ``"ca. +/-5.5"`` / ``"CHF +/-500"`` transparent ueber die bereits
# etablierte Praefix-Rekursions-Semantik aufloest: Approx-Strip ->
# ``"+/-5.5"`` -> ASCII-PM-Strip -> ``"5.5"`` -> Fallback (5.5, 5.5). Vor
# den Uncertainty-Zweigen einsortiert, damit ``"+/-5.5 ± 0.3"`` (Leading-
# ASCII-± Marker + Trailing-Uncertainty) via Rekursion die Toleranz behaelt:
# ASCII-PM-Strip -> ``"5.5 ± 0.3"`` -> Uncertainty-Match (5.2, 5.8). Vor
# dem Vergleichs-Zweig einsortiert, damit ``"< +/-5.5"`` transparent auf
# ``"< 5.5"`` reduziert und die obere-Grenze-Semantik (None, 5.5) liefert
# (nicht praxisrelevant, aber verlustfrei via Rekursion).
#
# Kollisionsfrei zur negativen Sign-Bindung in _NUM_RE: der Strip laeuft
# VOR der Zahl-Extraktion und entfernt genau die ASCII-±-Marker-Sequenz -
# die Sign-Alternante von _NUM_RE sieht danach eine reine Ziffer ohne
# Vorzeichen und liefert den positiven Center-Wert. Kollisionsfrei zu
# tatsaechlichen negativen Werten wie ``"-5.5"`` (kein ``+`` am Anfang,
# Strip blockt an ``^\s*\+``) und zu positiven Vorzeichen ``"+5.5"``
# (kein ``-`` nach ``+``, Strip blockt an ``\+/?-`` - die Sequenz ``+5``
# hat weder ``/`` noch ``-`` an der Position). Kollisionsfrei zu ASCII-±-
# Notation OHNE Whitespace VOR Range-Grenzen wie ``"+/-5-10"`` (unklare
# Semantik: gemeint entweder ``"+/-5 bis 10"`` oder ``"+/-5 bis -10"``);
# der Strip liest den Marker als Praezisions-Modifier des ersten Werts
# und rekursiert auf ``"5-10"`` -> (5.0, 10.0), was der wahrscheinlicheren
# Interpretation entspricht.
_LEADING_ASCII_PM_MARKER = re.compile(r"^\s*\+/?-\s*(?=[.\d])")

# Einseitige Vergleichs-Grenze am String-Anfang: ``< 5``, ``> 5``, ``<= 5``,
# ``>= 5``, ``≤ 5``, ``≥ 5``. Semantisch eine offene Range-Grenze (untere ODER
# obere), keine Punkt-Angabe: ``< 5`` heisst "kleiner als 5" -> Range (-inf, 5),
# ``≥ 500`` heisst "mindestens 500" -> Range [500, +inf). In Sammler-Notizen und
# publizierten Referenz-Tabellen die uebliche Kurzform fuer eine unsichere
# Bereichsgrenze ("Mohs > 7" bei einem Stueck, das Quarz ritzt, ohne dass die
# genaue Haerte bestimmt wurde; "Dichte < 3" fuer ein zweifelsfrei leichteres
# Mineral, dessen exakte Massendichte nicht vermessen wurde; "Wert >= 500 CHF"
# fuer eine Mindest-Schaetzung ohne feste Obergrenze). Ohne Behandlung fiel jede
# solche Notation still auf die Fallback-Zahl-Extraktion durch, die den
# Vergleichs-Marker ignorierte und den nackten Wert als Punkt-Range (5.0, 5.0)
# lieferte - die publizierte Ein-Seiten-Semantik ging stille verloren und die
# Migration schrieb Mohs_Haerte_min=5 UND Mohs_Haerte_max=5 statt Mohs_Haerte_max=5
# mit Mohs_Haerte_min=NULL (bzw. spiegelbildlich fuer den ``>``/``≥``-Fall).
#
# Der Marker wird als Gruppe extrahiert: ``<``/``<=``/``≤`` mappt auf obere
# Grenze (lo=None, hi=Wert), ``>``/``>=``/``≥`` auf untere Grenze (lo=Wert,
# hi=None). Die Gleich-Varianten (``<=``/``≤``/``>=``/``≥``) liefern semantisch
# denselben Range wie ``<``/``>`` (die Bereichs-Grenzen sind in dieser Anwendung
# ohnehin inklusiv gemeint, weil DB-Filter ``Mohs_Haerte_max >= X`` und
# ``Mohs_Haerte_max <= X`` als geschlossene Intervalle geschrieben sind).
#
# Wird in :func:`parse_range` NACH dem :data:`_APPROX_VALUE_PREFIX`-Strip
# geprueft, damit ``< ca. 5`` (Approximations-Marker im Vergleichs-Kontext) die
# Approximation zunaechst konsumiert und danach die Vergleichs-Semantik ausliest.
# Kollisionsfrei zu den Uncertainty-Zweigen (``5.5 ± 0.3``, ``5.5(3)``): diese
# verlangen eine reine Zahl am Anfang; ``< 5.5 ± 0.3`` liesse man semantisch als
# "obere Grenze mit publizierter Toleranz um 5.5" lesen, aber diese Kombination
# ist in Sammler-Notizen extrem selten (Vergleichs-Marker impliziert bereits
# Unsicherheit) - falls sie auftritt, konsumiert der Vergleichs-Zweig den Marker
# und rekursiert; der Rest ``5.5 ± 0.3`` laeuft transparent in den Uncertainty-
# Zweig und die publizierte Toleranz wird als Bereich (5.2, 5.8) zurueckgegeben,
# der Vergleichs-Marker geht dann semantisch in die Approximations-Interpretation
# der Toleranz-Grenzen ueber (nicht ideal, aber verlustfrei).
#
# Kollisionsfrei zu negativen Vorzeichen: das Regex verlangt ``<``/``>`` als
# Praefix VOR jeder Zahl-Struktur; ``- 5`` (negative Zahl mit Leerzeichen)
# blockt bereits an der Vorzeichen-Klasse. ``> -5`` (Vergleichs-Marker vor
# negativer Zahl) wird korrekt geparst: der Marker konsumiert den ``>``, die
# Rekursion parst ``-5`` als (-5.0, -5.0), und die Vergleichs-Interpretation
# liefert (-5.0, None) = "groesser als -5". Die Vergleichs-Marker sind
# ausschliesslich als Bereichs-Grenzen-Anzeiger etabliert; sie treten in
# CSV-Wert-Feldern nirgends als Teil einer Zahl-Struktur auf (kein Vorzeichen,
# kein Exponent-Zeichen, kein Dezimal-/Tausender-Trenner).
_COMPARISON_PREFIX = re.compile(r"^\s*(<=|>=|<|>|≤|≥)\s*")

# Wort-basierte einseitige Vergleichs-Grenze am String-Anfang: die natur-
# sprachige Kurzform der ``<``/``>``/``<=``/``>=``-Marker, die in Sammler-
# Notizen und deutsch-/englisch-sprachigen Publikationen ebenso verbreitet
# ist wie die mathematische Notation. ``mindestens 5`` = ``>= 5`` ->
# (5, None); ``hoechstens 5`` = ``<= 5`` -> (None, 5); ``bis 500`` = ``<=
# 500`` fuer Wert-Obergrenzen ("Wert bis 500 CHF") oder Grenzwerte im Feld-
# text ("Haerte bis 6.5" = "hoechstens 6.5" auf der Mohs-Achse). Spiegelt
# strukturell :data:`_COMPARISON_PREFIX` auf die Wort-Achse: der Marker
# wird konsumiert, der Rest rekursiv geparst und das Ergebnis auf eine
# offene Range-Grenze abgebildet.
#
# Ohne Behandlung fielen alle diese Formen still auf die Fallback-Zahl-
# Extraktion durch: der Wort-Marker wurde als Freitext gelesen und der
# nackte Wert als Punkt-Range (5.0, 5.0) geliefert - die publizierte
# Ein-Seiten-Semantik ging stille verloren und die Migration schrieb
# Mohs_Haerte_min=5 UND Mohs_Haerte_max=5 statt der korrekten
# Ein-Seiten-Setzung mit NULL an der gegenueberliegenden Grenze.
#
# Marker-Menge (Anspruch: die in Sammler-Notizen und Auktions-/Katalog-
# Texten praxisrelevanten Formen, keine kreativen Freitext-Varianten):
#
# Untere Grenze (>=, ``lo=Wert, hi=None``):
#   * DE: ``mindestens``, ``mind.``, ``min.``, ``wenigstens``,
#     ``zumindest``, ``ab``, ``ueber``/``über``, ``oberhalb``,
#     ``mehr als``
#   * EN: ``at least``, ``from``, ``over``, ``above``, ``more than``,
#     ``greater than``
#
# Obere Grenze (<=, ``lo=None, hi=Wert``):
#   * DE: ``hoechstens``, ``höchstens``, ``maximal``, ``max.``,
#     ``bis zu``, ``bis``, ``unter``, ``unterhalb``, ``weniger als``
#   * EN: ``at most``, ``up to``, ``under``, ``below``, ``less than``
#
# Die strikte (>) vs. nicht-strikte (>=) Semantik wird nicht unterschieden -
# der interne Range-Container kennt nur offene/geschlossene Grenzen, und die
# fuer Sammler-CSVs relevante Frage ist "welche Seite ist unbekannt?", nicht
# "ist der Grenzwert selbst enthalten?". Spiegelt die Konvention aus
# :data:`_COMPARISON_PREFIX`, wo ``<`` und ``<=`` bereits identisch auf die
# obere-Grenze-offen abgebildet werden.
#
# Praefix-Position auf ``^\s*`` anker-gebunden und mit Whitespace nach dem
# Marker separiert (``\s+``): kollisionsfrei zu Fortsetzungen der Wort-
# stamme (``abmessungen``, ``abbau``, ``maximal-wert``, ``bislang``,
# ``ueberall``, ``ueberpruefung``, ``overall``, ``override``, ``underneath``,
# ``understanding``, ``unterschiedlich``, ``oberflaeche``), weil die Marker-
# Fortsetzung nicht mit Whitespace beginnen kann. ``bis`` zwischen zwei
# Zahlen (``3 bis 5``) bleibt als Range-Separator erhalten, weil der
# Praefix-Anker den Wort-Marker nur am String-Anfang akzeptiert -
# ``3 bis 5`` matcht NICHT (die ``3`` steht vorne). ``min``/``max`` ohne
# Punkt sind absichtlich AUSGESCHLOSSEN: ``min`` ist SI-Einheit fuer
# Minute, ``max`` ist ein verbreiteter Vorname und Feldpraefix - beide
# treten in Sammler-Notizen und Wert-Feldern auf und wuerden ohne
# Punkt-Guard fehl-matchen. Die abgekuerzten Formen mit Punkt
# (``min.``/``max.``/``mind.``) sind eindeutig als Marker markiert und
# werden akzeptiert.
_COMPARISON_WORD_LOWER = re.compile(
    r"^\s*(?:"
    r"mindestens|mind\.|min\.|"
    r"wenigstens|zumindest|"
    r"oberhalb|"
    r"mehr\s+als|"
    r"ab|über|ueber|"
    r"at\s+least|"
    r"greater\s+than|more\s+than|"
    r"above|over|from"
    r")\s+",
    re.IGNORECASE,
)
_COMPARISON_WORD_UPPER = re.compile(
    r"^\s*(?:"
    r"höchstens|hoechstens|"
    r"maximal|max\.|"
    r"unterhalb|"
    r"weniger\s+als|"
    r"bis\s+zu|bis|unter|"
    r"at\s+most|up\s+to|"
    r"less\s+than|"
    r"below|under"
    r")\s+",
    re.IGNORECASE,
)

# Marker-Menge fuer :data:`_COMPARISON_WORD_LOWER`, die in natuerlicher
# Sprache DUAL-USE sind: sie fungieren *entweder* als "at least"-
# Ein-Seiten-Marker (``from 5``, ``ab 500 CHF``) *oder* als Range-Start-
# Marker in Kombination mit ``to``/``bis`` oder einem Ziffern-Bindestrich
# (``from 5 to 7``, ``ab 5 bis 7``, ``ab 5-7``, ``from 500 to 700 CHF``).
# Die Unterscheidung ist rein syntaktisch: bei folgendem Range-Separator
# ist der Marker der Range-Start-Wort ("von X bis Y"-Konvention),
# bei fehlendem Separator die etablierte Ein-Seiten-Semantik ("at
# least X"). Alle anderen Marker (``mindestens``/``at least``/``ueber``/
# ``mehr als``/``greater than``/``over``/``above``/``oberhalb``/
# ``wenigstens``/``zumindest``/``min.``/``mind.``) sind ausschliesslich
# Ein-Seiten-Marker und teilen die Range-Starter-Semantik nicht - sie
# bleiben von der Dual-Use-Auswertung ausgenommen und wenden immer die
# Ein-Seiten-Bounds-Setzung an, auch bei folgendem Range-Ausdruck
# (``at least 5-7`` -> (5, None), spiegelt die Sammler-Semantik "der
# Wert liegt mindestens im Range 5-7, also mindestens 5").
_RANGE_STARTER_WORDS: frozenset[str] = frozenset({"from", "ab"})

# Detektor fuer einen Range-Separator NACH der ersten Zahl im ``rest``-
# Segment: entweder ein Wort-Separator (``to``/``bis`` mit obligatorischem
# Whitespace links und rechts, damit ``bislang``/``together``/``tomorrow``
# nicht mit-matcht) oder ein Ziffern-Bindestrich (ASCII-``-`` bzw. Unicode-
# Dashes ``–``/``—``/``−`` zwischen zwei Zahlen; ASCII-Vorzeichen-Bindung
# an eine folgende Zahl OHNE fuehrende Ziffer wird durch den Lookbehind
# ``(?<=\d)`` ausgeschlossen, damit ``ab -5`` als "at least -5" statt als
# Range ``ab -5`` gelesen wird). Wird ausschliesslich fuer die
# :data:`_RANGE_STARTER_WORDS`-Dual-Use-Auswertung genutzt.
_HAS_RANGE_TAIL = re.compile(
    r"\s+(?:to|bis)\s+|(?<=\d)\s*[-–—−]\s*(?=[.\d])",
    re.IGNORECASE,
)

# Wissenschaftliche Unsicherheits-Notation "N ± M" (Mittelwert plus/minus Toleranz).
# In Mineralogie-Tabellen und -Publikationen der Standard-Weg, Messgenauigkeit zu
# notieren: ``Dichte 2.65 ± 0.05`` = "Wert 2.65, Toleranz 0.05, Range [2.60, 2.70]".
# ``5.5 ± 0.3`` liefert damit (5.2, 5.8) statt (5.5, 5.5) und macht die publizierte
# Toleranz explizit als Bereichsgrenzen sichtbar - sinnvoll fuer Sammler-Notizen,
# die Dichte-/Haerte-Werte direkt aus Referenz-Tabellen uebernehmen. Center darf
# negativ sein (fuer thermische/isotopische Werte ausserhalb der klassischen
# Mineralogie); Toleranz ist nicht-negativ per Definition. Komma als Dezimaltrenner
# akzeptiert (DE-Publikationen). Muss auf den gesamten String matchen (^...$),
# damit Freitext-Anhaenge wie ``5.5 ± 0.3 (Literatur)`` nicht versehentlich
# einbezogen werden - fuer die kommt die Fallback-Zahl-Suche zum Zug.
#
# Neben dem Unicode-Zeichen ± (U+00B1, DE/Excel/Print-Standard) werden auch die
# ASCII-Ersatzformen ``+/-`` und ``+-`` akzeptiert - beide sind in E-Mails,
# Terminal-Ausgaben und LaTeX-Roh-Exporten die uebliche Notation, wenn der
# Autor kein Unicode zur Verfuegung hat oder die Notiz von einem 7-bit ASCII-
# Tool stammt (alte Sammlungs-Datenbanken, Foto-EXIF-Kommentare, geerbte
# Excel-Kopien mit Character-Set-Verlust). Ohne die ASCII-Fallbacks fielen
# diese Formen weiter auf den inverted-Range-Kollaps (5.5, 5.5) und die
# publizierte Toleranz ging stille verloren - unabhaengig davon, ob der
# Sammler das ±-Zeichen zum Zeitpunkt der Notiz uebersetzen konnte oder
# nicht. Alle drei Varianten loesen zu identischen Bereichs-Grenzen auf.
#
# Trailing-Einheits-Annotation (``2.65 ± 0.05 g/cm³``, ``5.5 ± 0.3 Mohs``,
# ``100 ± 2 HV``, ``-1.5 ± 0.3 °C``) wird ueber :data:`_TRAILING_UNIT_TOKENS`
# als Whitespace-getrennte Wort-Tokens toleriert, ohne die publizierte
# Toleranz zu verwerfen. Ohne diese Toleranz fiel jede Notation mit
# nachgestellter Einheit stille auf die Fallback-Zahl-Suche zurueck:
# ``2.65 ± 0.05 g/cm³`` lieferte via ``if hi < lo``-Kollaps ``(2.65, 2.65)``
# (Toleranz verloren), ``5.5 ± 0.3 Mohs`` lieferte ``(5.5, 5.5)`` (Toleranz
# verloren) - trotz mineralogischer Praxis, den Wert samt Toleranz *und*
# Einheit in einem Token zu notieren (Dichte-Feld: ``g/cm³``; Haerte-Feld:
# ``Mohs`` / ``HV`` / ``HB``; thermische Felder: ``°C``, ``°F``). Klammer-
# Anhaenge (``(Literatur)``, ``(Ref)``) bleiben ausgeschlossen und fallen
# weiterhin auf die Zahl-Extraktion durch - die Einheits-Klasse
# :data:`_TRAILING_UNIT_TOKENS` verlangt beim ersten Token einen Nicht-
# Klammer-Nicht-Ziffer-Buchstaben und schliesst so runde/eckige/geschweifte
# Klammern strukturell aus.
# Trailing-Bracket-Annotations-Zweig ``(?:\s*[(\[{][^()\[\]{}]*[)\]}])*``
# nach der Einheit-Wort-Sequenz - deckt die typische Kombination "Wert +
# Toleranz + Einheit + Freitext-Klammer-Annotation" ab, die in publizierten
# mineralogischen Referenz-Tabellen der Standard ist ("2.65 ± 0.05 g/cm³
# (Literatur)", "5.5 ± 0.3 Mohs [Ref 42]", "100 ± 2 HV {IUCr}"). Bisher
# fiel diese verbreitete Notation still auf einen Toleranz-Verlust durch:
# das Regex ankert auf ``\s*$``, aber die Trailing-Klammer-Annotation blockte
# das End-Anker-Matching (die Einheits-Wort-Sequenz stoppt vor der Klammer,
# weil das erste Klammer-Zeichen in der [^\s\d(){}\[\],;]-Ausschluss-Klasse
# liegt), sodass "2.65 ± 0.05 g/cm³ (Literatur)" auf die Fallback-Zahl-
# Extraktion durchfiel und die publizierte Toleranz stille auf (2.65, 2.65)
# kollabierte. Bei der Migration aus wissenschaftlichen Publikationen und
# Datenbank-Exporten, die Wert-mit-Toleranz-mit-Einheit-mit-Referenz-
# Annotation als kanonische Zeile schreiben, entstand damit silenter
# Praezisions-Datenverlust auf jeder Dichte-/Haerte-/Wert-Achse mit Literatur-
# Verweis.
#
# Der neue Zweig matcht null oder mehr Klammer-Gruppen (rund/eckig/geschweift),
# jede mit optionalem Whitespace davor und beliebigem Inner-Content (ausser
# den drei Klammer-Zeichen selbst) - single-level, keine Verschachtelung.
# Nested Klammern (``(Foto (gut))``) sind in Wert-Feld-Annotationen sehr
# selten; falls sie auftreten, faellt die Klammer auf die Zahl-Extraktion
# durch, was Rueckwaerts-kompatibel mit dem alten Verhalten ist. Die drei
# Klammer-Typen sind symmetrisch behandelt, spiegelt die Konvention der
# :func:`_strip_bracketed_annotations`-Helper.
#
# Direkt-anhaengende Einheiten-Alternante
# ``(?:(?![eE][+-]?\d)[A-Za-zÅΩµ°][A-Za-z0-9ÅΩµ°/^³²]*)?`` nach Center und
# Toleranz-Zahl - deckt die publizierte Notation ohne Whitespace zwischen
# Zahl und Einheit ab, die in Mineralogie-/Physik-Publikationen und Excel-
# CSV-Exporten aus geerbten Sammler-Etiketten sehr verbreitet ist:
# ``5.5mm`` (Kristall-Groesse), ``2.65g/cm³`` (Dichte), ``100HV`` (Vickers-
# Haerte), ``12.345K`` (Temperatur). Vor dem Fix verlangte der Trailing-Unit-
# Zweig obligatorisches ``\s+`` VOR dem ersten Einheiten-Token, sodass
# ``5.5 ± 0.3mm`` durch das fehlende Whitespace zwischen ``0.3`` und ``mm``
# auf die Fallback-Zahl-Extraktion durchfiel und via ``[5.5, 0.3]``-inverted-
# range auf ``(5.5, 5.5)`` kollabierte (Toleranz verloren); analog fielen
# ``5.5mm ± 0.3``, ``5.5mm ± 0.3mm``, ``2.65 ± 0.05g/cm³`` und ``2.65(5)g``
# auf Kollaps oder semantisch falsche Range-Werte. Bei der Migration aus
# solchen Quellen entstand silenter Praezisions-Datenverlust auf jeder Wert-
# Achse mit direkt anhaengender Einheit.
#
# Das Alternate startet mit einem Buchstaben (ASCII a-z/A-Z plus SI-Standard-
# Zeichen Å/Ω/µ/°) und fuehrt fort mit Buchstaben, Ziffern und den SI-
# typischen Sonderzeichen ``/``, ``^``, ``³``, ``²`` (fuer zusammengesetzte
# Einheiten wie ``g/cm³``, ``m/s²``, ``cm^3``). Das Start-Muss-Sein-Buchstabe
# blockt die Alternante an Positionen, an denen ± oder Ziffer folgt - keine
# Kollision mit der ±/Klammer-Alternate der Uncertainty-Struktur. Das
# negative Lookahead ``(?![eE][+-]?\d)`` schuetzt vor Kollision mit
# wissenschaftlicher Notation: ``1e400 ± 1e400`` (Overflow-Range) darf NICHT
# als "Center=1 mit Einheit ``e400`` plus/minus 1 mit Einheit ``e400``"
# gelesen werden - das ``e`` gefolgt von Ziffern ist Exponent-Marker, keine
# SI-Einheit. Ohne den Lookahead wuerden alle scientific-notation-Overflow-
# Tokens faelschlich in die Uncertainty-Struktur eingemischt und die
# nachgelagerte ``_finite_pair``-Overflow-Behandlung ueberschrieben.
_PLUS_MINUS_UNCERTAINTY = re.compile(
    r"^\s*(-?\d+(?:[.,]\d+)?)(?:\s*[%‰])?"
    r"(?:(?![eE][+-]?\d)[A-Za-zÅΩµ°][A-Za-z0-9ÅΩµ°/^³²]*)?"
    # Whitespace-getrennte Einheiten-Tokens ZWISCHEN Center und ± -
    # deckt die in Publikationen verbreitete Redundanz-Notation
    # "Center-mit-Einheit ± Toleranz-mit-Einheit" ab (``2.65 g/cm³ ±
    # 0.05 g/cm³``, ``5.5 mm ± 0.3 mm``, ``100 HV ± 2 HV``, ``-1.5 °C
    # ± 0.3 °C``). Ohne diesen Zweig fiel jede Notation mit whitespace-
    # getrennter Einheit VOR dem ±-Symbol still auf die Fallback-Zahl-
    # Extraktion durch: ``2.65 g/cm³ ± 0.05 g/cm³`` wurde als
    # ``[2.65, 0.05]``-Range gelesen und via ``if hi < lo``-Kollaps auf
    # ``(2.65, 2.65)`` reduziert (Toleranz verloren); ``-1.5 °C ± 0.3``
    # noch bunter: als ``[-1.5, 0.3]``-Range gelesen und zu
    # ``(-1.5, 0.3)`` interpretiert (mineralogisch/thermisch unsinnige
    # Range-Grenzen, die publizierte Standard-Unsicherheit als
    # Range-Grenze fehlgedeutet). In publizierten Referenz-Tabellen,
    # Excel-CSV-Exporten und Sammler-Notizen ist die redundante
    # Einheit-auf-beiden-Seiten-Notation eine Standard-Praxis
    # (Copy&Paste von Dichte-Zeilen aus Print-Publikationen,
    # Feld-Uebernahmen aus Etiketten-Beschreibungen); der Zweig macht
    # sie symmetrisch zur bereits vorhandenen Trailing-Einheit-nach-
    # Toleranz-Klausel akzeptierbar. Das erste-Zeichen-muss-Buchstabe-
    # Kriterium (``[A-Za-zÅΩµ°]``) schuetzt vor Kollision mit dem
    # ±-Symbol (nicht in der Zeichen-Klasse) und mit der Toleranz-
    # Zahl (Ziffer nicht in der Zeichen-Klasse) - der Zweig backtrackt
    # sauber, wenn die naechste Position ± oder Ziffer statt Einheit
    # zeigt.
    r"(?:\s+(?![eE][+-]?\d)[A-Za-zÅΩµ°][A-Za-z0-9ÅΩµ°/^³²]*)*"
    r"\s*(?:±|\+/-|\+-)\s*(\d+(?:[.,]\d+)?)(?:\s*[%‰])?"
    r"(?:(?![eE][+-]?\d)[A-Za-zÅΩµ°][A-Za-z0-9ÅΩµ°/^³²]*)?"
    r"(?:\s+[^\s\d(){}\[\],;][^\s(){}\[\],;]*)*"
    # Trailing-Klammer-Annotation ((\[{Ref\]}), (Literatur), [NIST-2018])
    # single-level, symmetrisch fuer runde/eckige/geschweifte Klammern.
    r"(?:\s*[(\[{][^()\[\]{}]*[)\]}])*"
    # Trailing-Satzzeichen ``[.,;:!?]`` als Endpunkt der Wert-Zelle
    # tolerieren, damit die publizierte Toleranz nicht durch das
    # ``$``-Anker-Match verworfen wird, wenn Sammler-Notizen die
    # Uncertainty-Notation innerhalb eines Satzes oder mit typischem
    # Excel-CSV-Zeilen-Ende-Punkt/Komma schreiben ("Dichte 2.65 ± 0.05.",
    # "Haerte 5.5 ± 0.3, Referenz X", "5.5(3);"). Bisher fielen alle
    # Formen mit Trailing-Satzzeichen still auf die Fallback-Zahl-
    # Extraktion durch und lieferten via ``[center, tol]``-inverted-
    # range-Kollaps ``(center, center)`` (Toleranz verloren) - typische
    # Praxis in Sammler-Notizen ("Dichte 2.65 ± 0.05.") und Excel-CSV-
    # Zeilen mit vom Editor angehaengten Punkten/Kommas. Ein einzelnes
    # Trailing-Zeichen ist ausreichend (Doppel-Punkt-Anhaenge sind in
    # Wert-Feldern nicht praxisrelevant); Punkt/Komma/Semikolon sind die
    # verbreitetsten Formen aus Editor-Autocomplete und Freitext-
    # Satz-Kontext, Doppelpunkt und Ausrufezeichen/Fragezeichen sind
    # seltener aber semantisch aequivalent (Wert-Terminator). Ohne
    # Wechselwirkung mit der Trailing-Klammer-Annotation - die Klammer-
    # Annotation ist optional und der neue Satzzeichen-Zweig kommt
    # entweder nach der letzten Klammer-Gruppe (``"5.5 ± 0.3 (Ref),"``)
    # oder nach dem letzten Einheiten-Token (``"5.5 ± 0.3 mm,"``) oder
    # direkt hinter der Toleranz-Zahl (``"5.5 ± 0.3,"``).
    r"\s*[.,;:!?]?\s*$"
)

# IUCr / kristallographische Kompakt-Unsicherheits-Notation ``N(M)`` - der
# Klammer-Term beziffert die Standard-Unsicherheit auf die letzten Ziffern
# des Zentrums, ohne dass Toleranz und Dezimalstelle separat notiert werden
# muessen. Standard-Konvention der International Union of Crystallography
# (IUCr Style Guide "Notes for authors", Abschnitt "Estimated standard
# uncertainties") und in mineralogischen Referenz-Tabellen, Roentgen-
# Beugungs-Reports (Rietveld-Verfeinerung, Einkristall-Strukturaufloesung)
# sowie NIST-CODATA-Konstanten-Tabellen die etablierte platzsparende
# Alternative zur ``N ± M``-Langform:
#
# * ``5.5(3)``     = 5.5 ± 0.3       -> (5.2, 5.8)     (Toleranz auf 1. Nachkomma)
# * ``2.65(5)``    = 2.65 ± 0.05     -> (2.60, 2.70)   (Toleranz auf 2. Nachkomma)
# * ``100(2)``     = 100 ± 2         -> (98, 102)      (Toleranz auf letzte ganze Ziffer)
# * ``12.345(67)`` = 12.345 ± 0.067  -> (12.278, 12.412) (Toleranz auf 3. Nachkomma)
# * ``7.4(15)``    = 7.4 ± 1.5       -> (5.9, 8.9)     (mehrstellige Toleranz)
#
# Bisher fielen alle diese Formen entweder auf inverted-Range-Kollaps
# ``(5.5, 5.5)`` (wenn Klammer-Zahl < Center, z.B. ``5.5(3)``) oder auf
# einen falsch interpretierten Range ``(2.65, 5.0)`` (wenn Klammer-Zahl >
# Center, z.B. ``2.65(5)``) - beide Faelle verwerfen die publizierte
# Standard-Unsicherheit und beziffern statt der Bereichs-Grenzen einen
# Punkt-Wert bzw. einen semantisch falschen Range. Bei der Migration aus
# wissenschaftlichen Quellen (Sammler kopieren Dichte-/Haerte-Werte direkt
# aus IUCr-Publikationen oder mineralogischen Nachschlagewerken) entsteht
# damit silenter Verlust der Messgenauigkeit.
#
# Muss auf den gesamten String matchen ($-Anker), damit Freitext-Anhaenge
# wie ``5.5(3) (Literatur)`` nicht versehentlich als Unsicherheit gelesen
# werden - fuer die faellt der Match und die Fallback-Zahl-Suche greift.
# Kein Whitespace zwischen Wert und Klammer erlaubt (``5.5 (3)``), damit
# echte Annotations-Klammern (``1.5 (Literatur)``, ``2.65 (aus Katalog)``)
# nicht als Unsicherheit interpretiert werden - die IUCr-Konvention setzt
# die Klammer strikt ohne Trenner direkt hinter den Wert. Center darf
# negativ sein (thermische/isotopische Werte ausserhalb der klassischen
# Mineralogie, spiegelt die _PLUS_MINUS_UNCERTAINTY-Konvention); Klammer-
# Ziffer-Gruppe muss aus reinen Dezimalziffern bestehen (keine Trenner
# innerhalb, sonst wuerde ``5.5(1,2)`` als "1 bis 2 Toleranz" mehrdeutig).
#
# Trailing-Einheits-Annotation (``2.65(5) g/cm³``, ``5.5(3) Mohs``,
# ``100(2) HV``) wird symmetrisch zur ±-Langform ueber Whitespace-getrennte
# Wort-Tokens toleriert. Ohne diese Toleranz kollabierte die Kompaktform
# bei nachgestellter Einheit auf die Fallback-Zahl-Suche und lieferte semantisch
# falsche Ergebnisse: ``2.65(5) g/cm³`` wurde als ``[2.65, 5.0]`` erkannt und
# lieferte ``(2.65, 5.0)`` (mineralogisch unsinniger Dichte-Range 2.65 bis 5.0
# g/cm³ statt Toleranz 2.60 bis 2.70); ``5.5(3) Mohs`` fiel via inverted-Range-
# Kollaps auf ``(5.5, 5.5)`` (Toleranz verloren). In mineralogischen Referenz-
# Tabellen ist die Kompaktform *mit* Einheit die uebliche Praxis (Dichte:
# ``g/cm³``; Haerte: ``Mohs``/``HV``/``HB``; Kristall-Achsen: ``Å``), daher
# ist die Einheits-Toleranz genauso wichtig wie bei der ±-Langform.
# Trailing-Bracket-Annotations-Zweig symmetrisch zur _PLUS_MINUS_UNCERTAINTY-
# Erweiterung (siehe Kommentar dort fuer Details zur Motivation, zur single-
# level-Konvention und zur symmetrischen Klammer-Typen-Behandlung). Deckt
# hier die IUCr-Kompaktform-plus-Referenz-Annotation ab ("2.65(5) g/cm³
# (Literatur)", "5.5(3) Mohs [Ref 42]", "12.345(67) K [NIST-CODATA-2018]") -
# in publizierten Kristallographie-/Mineralogie-Tabellen die kanonische
# Zeilenform (Wert-mit-Kompakt-Toleranz + Einheit + Literatur-Referenz).
# Bisher fiel diese Kombination still auf einen Praezisions-Verlust durch
# (analog _PLUS_MINUS_UNCERTAINTY): die Trailing-Klammer-Annotation blockte
# das End-Anker-Matching, "2.65(5) g/cm³ (Literatur)" fiel auf die Fallback-
# Zahl-Extraktion mit (2.65, 2.65)-Kollaps (Toleranz verloren) oder auf
# einen semantisch falschen Range durch, wenn die Annotation eine hoehere
# Zahl enthielt (2.65, ..., > 2.65).
_PARENTHESIS_UNCERTAINTY = re.compile(
    r"^\s*(-?\d+(?:[.,]\d+)?)\((\d+)\)(?:\s*[%‰])?"
    r"(?:(?![eE][+-]?\d)[A-Za-zÅΩµ°][A-Za-z0-9ÅΩµ°/^³²]*)?"
    r"(?:\s+[^\s\d(){}\[\],;][^\s(){}\[\],;]*)*"
    r"(?:\s*[(\[{][^()\[\]{}]*[)\]}])*"
    # Trailing-Satzzeichen tolerieren - spiegelt die Erweiterung von
    # :data:`_PLUS_MINUS_UNCERTAINTY` auf die IUCr-Kompaktform, damit
    # ``"5.5(3),"`` / ``"2.65(5)."`` / ``"100(2);"`` die publizierte
    # Toleranz behalten statt via ``[center, tol]``-inverted-range-
    # Kollaps auf ``(center, center)`` zu fallen.
    r"\s*[.,;:!?]?\s*$"
)

# Eindeutig erkennbare Tausender-Strukturen (Komma+Punkt oder Punkt+Komma in einer Zahl,
# oder mehrere Trenner desselben Typs in Folge). ``(?<!\d)``/``(?!\d)`` stellen sicher,
# dass die Zahl als Ganzes erkannt wird (kein Anschnitt einer laengeren Ziffernfolge).
_EN_THOUSANDS_WITH_DECIMAL = re.compile(
    r"(?<!\d)(\d{1,3}(?:,\d{3})+\.\d+)(?!\d)"
)
_DE_THOUSANDS_WITH_DECIMAL = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d{3})+,\d+)(?!\d)"
)
_EN_THOUSANDS_PURE = re.compile(
    r"(?<!\d)(\d{1,3}(?:,\d{3}){2,})(?!\d)"
)
_DE_THOUSANDS_PURE = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d{3}){2,})(?!\d)"
)
# Whitespace als Tausender-Trenner (FR/Swiss-French/SI-Konvention). Im
# Gegensatz zum ASCII-Komma/Punkt werden die typografischen Whitespace-
# Varianten (NBSP U+00A0, schmales NBSP U+202F, THIN SPACE U+2009)
# genauso wie das ASCII-Leerzeichen unterstuetzt - franzoesische Excel-/
# LibreOffice-Exporte schreiben Tausender meist als NBSP (``1\xa0234,56``),
# Hand-Eingaben dagegen oft mit gewoehnlichem Leerzeichen
# (``1 234,56``), und das BIPM-SI-Brochure / NIST-konforme Typografie
# (wissenschaftliche Publikationen, LaTeX-Output mit ``\,``) verwendet
# THIN SPACE U+2009 als das eigentliche spec-empfohlene Tausender-
# Zeichen (NBSP ist Excel-Praxis, aber das SI-Brochure 8th edition,
# section 5.3.4 schreibt explizit "thin space"). Bisher fielen alle
# THIN-SPACE-Formen stille auf eine Mehrfach-Zahl-Zerlegung
# (``"1 000.50"`` lieferte ``(1.0, 1.0)`` statt ``(1000.5, 1000.5)``,
# weil die Whitespace-Klasse THIN SPACE nicht enthielt und das
# Re-Pattern statt einer Zahl ``1000.5`` zwei Token ``1`` und ``000.5``
# fand), was bei der Migration aus typografisch sauber gesetzten
# Mineralogie-Publikationen, LaTeX-/TeX-Exporten oder ISO-31-0-
# konformen Datensaetzen silenten Wert-Datenverlust erzeugte.
# Symmetrisch zu den EN/DE-Patterns: bei vorhandener Dezimal-Trennung
# reicht eine Gruppe, ohne Dezimal sind mindestens zwei Gruppen noetig -
# die einzelne Gruppe ``1 234`` bleibt ambivalent (koennte Range-
# Tippfehler "Wert 1 bis 234" oder Tausender sein) und wird wie bei
# den EN/DE-Patterns nicht angetastet.
_SP_THOUSAND_CHARS = r"[ \xa0  ]"
_SPACE_THOUSANDS_WITH_DECIMAL = re.compile(
    rf"(?<!\d)(\d{{1,3}}(?:{_SP_THOUSAND_CHARS}\d{{3}})+[.,]\d+)(?!\d)"
)
_SPACE_THOUSANDS_PURE = re.compile(
    rf"(?<!\d)(\d{{1,3}}(?:{_SP_THOUSAND_CHARS}\d{{3}}){{2,}})(?!\d)"
)
_SPACE_THOUSAND_CHAR_RE = re.compile(_SP_THOUSAND_CHARS)

# Underscore-Digit-Grouping (PEP 515, Java 7+, JavaScript ES2021, Rust, Swift,
# Kotlin, C++14, C# 7+) - der programmiersprachen-verbreitetste Ziffer-
# Gruppierungs-Trenner fuer numerische Literale. In Python 3.6+, Java, JS,
# Rust und den uebrigen modernen Sprachen ist ``1_000_000`` die kanonische
# Notation fuer grosse ganze Zahlen, und die Trenner-Notation faellt bei
# jedem Copy&Paste aus dem Editor (Interactive Python REPL, Jupyter-Notebook,
# Java-Datei-Ausriss, Rust-Playground, JSON5 mit numeric-separator-Erweiterung,
# Vim-yank, VSCode-copy-paste einer Code-Zeile ins Notiz-Feld) in die
# Sammler-Notiz-Feld-Werte. Aus dem typischen Sammler-Workflow "Preis-/
# Groessen-/Menge-Angabe aus einem Python/Java/JavaScript-Snippet in das
# Wert-CHF-/Gewicht-g-/Anzahl-Feld einfuegen" entstand damit silenter
# Groessenordnungs-Datenverlust bei der Migration: ``"1_000_000"`` (1 Million
# CHF, Preis-Angabe aus einer Sammler-Datenbank mit Python-numeric-literal-
# Format) fiel via :data:`_NUM_RE`-Fallback auf ``(1.0, 1.0)`` (Groessenordnung
# komplett verloren, 999999 CHF Wert-Diskrepanz), ``"1_500 g"`` (Gewicht-
# Angabe aus einem Java-Datenblatt) auf ``(1.0, 500.0)`` (Range-Grenzen
# vertauscht und um Faktor 3 geschrumpft), ``"10_000-20_000"`` (Range aus
# einem Rust-Playground-Code) auf ``(10.0, 10.0)`` (obere Grenze verloren,
# untere Grenze um Faktor 1000 geschrumpft), ``"1_234.567_89"`` (Rust-float-
# literal mit Ganzzahl- und Fraktions-Gruppierung) auf ``(1.0, 234.567)``
# (Ganzzahl-Groessenordnung verloren, Fraktion um zwei signifikante Stellen
# gekappt).
#
# Der Unicode-Underscore ``_`` (U+005F LOW LINE) hat in numerischen Kontexten
# ausserhalb dieser Ziffer-Gruppierungs-Rolle keine andere Bedeutung: kein
# Dezimal-Trenner (weder EN noch DE noch FR), kein Range-Trenner (typische
# Trenner sind Bindestrich/en-dash/em-dash/Slash/bis-Wort), kein Uncertainty-
# Marker (``±``/Klammer-Kompaktform) und kein Einheiten-Zeichen. Damit ist
# die Underscore-Position zwischen Ziffern eindeutig als "Ziffer-Gruppierungs-
# Trenner" interpretierbar und die Normalisierung ist verlustfrei fuer
# beliebige Gruppierungs-Groessen, sofern sie der Standard-3-Ziffer-
# Gruppierungs-Konvention folgen. Nicht-Standard-Gruppierungen (``1_23``,
# ``1_0000``) bleiben unangetastet - Python erlaubt sie zwar syntaktisch,
# aber in menschlich gepflegten Sammler-Notizen sind sie extrem selten und
# das Risiko einer Fehl-Interpretation als Bezeichner-Fragment ist hoeher
# als der Nutzen einer erzwungenen Normalisierung.
#
# Die Lookbehind-Klasse ``(?<![A-Za-z_\d])`` schuetzt vor Bezeichner-
# Kontexten (``Sample_1_000``, ``id_1_000``, ``_1_000`` als Kotlin-Backing-
# Field-Konvention, ``AB1_000``) - in allen diesen Faellen ist der Unterstrich
# Teil des Bezeichners und nicht Wert-Ziffer-Trenner. Die Lookahead-Klasse
# ``(?![\d_])`` schuetzt vor unvollstaendigen Gruppen (``1_000_a`` mit
# trailing Nicht-Standard-Suffix, ``1_000_`` mit trailing Underscore ohne
# folgende Ziffern) - dort ist der Underscore-Fluss unterbrochen und die
# Interpretation als Wert-Gruppierung unsicher. Die 3-Ziffer-Gruppen-
# Anforderung ``(?:_\d{3})+`` deckt die konventionelle Praxis in allen
# Programmiersprachen ab (Python-PEP-515-Empfehlung, Java-Style-Guide,
# JavaScript-Community-Praxis, Rust-Style-Guide) und vermeidet
# Kollisionen mit atypischen Ziffer-Sequenzen wie ``1_23`` (Python
# akzeptiert, aber sehr selten in menschlichen Notizen). Die Fuehrungs-
# Gruppen-Groesse ``\d{1,3}`` spiegelt die Standard-Konvention (leading
# 1-3 Ziffern vor der ersten 3er-Gruppe: ``1_000``, ``12_000``, ``123_000``).
#
# Kollisionsfreiheit zu den bestehenden Trennern:
#   * :data:`_SP_THOUSAND_CHARS` (Leerzeichen/NBSP/thin-space) - kein
#     Konflikt, Underscore ist kein Whitespace.
#   * :data:`_NUM_RE`-Sign-Lookbehind ``(?<![\d.%‰])-`` - kein Konflikt,
#     Underscore ist nicht in der Klasse.
#   * :data:`_APPROX_PREFIX` / temporale Praepositionen - werden VOR
#     dem numerischen Parsing gestrippt, kein Konflikt.
#   * :data:`_PLUS_MINUS_UNCERTAINTY` / :data:`_PARENTHESIS_UNCERTAINTY` -
#     matcht auf ``^...$`` und muss auf den gesamten String matchen; ein
#     Wert ``"1_000 ± 5"`` wuerde die Center-Zahl ``\d+(?:[.,]\d+)?``
#     verletzen (Underscore ist nicht in der Zahl-Klasse). Der Strip
#     VOR dem Uncertainty-Match loest genau diese Kollision: nach dem
#     Strip wird ``"1000 ± 5"`` transparent zur Uncertainty-Range
#     ``(995.0, 1005.0)`` (statt (1.0, 5.0) vorher).
#   * Range-Trenner-Bindestrich - der Strip normalisiert Underscore-
#     Gruppierungen VOR der Zahl-Extraktion; ``"1_000-2_000"`` wird zu
#     ``"1000-2000"`` und die Range-Semantik bleibt erhalten.
_UNDERSCORE_DIGIT_GROUPING = re.compile(
    r"(?<![A-Za-z_\d])(\d{1,3}(?:_\d{3})+)(?![\d_])"
)

# Bracket-Annotation-Strip fuer die Fallback-Zahl-Extraktion. Klammer-
# umschlossene Freitext-Anhaenge in Sammler-Notizen ("(Foto)", "(Nr. 42)",
# "(Ref 2020)", "(siehe Katalog)", "[verified 2024]", "{geerbt}") enthalten
# oft Zahlen (Katalog-Nummern, Foto-Referenzen, Jahres-Marker, ID-Verweise),
# die *nicht* Teil des zu parsenden Wert-Bereichs sind - sie sind Metadaten
# zum Wert. Ohne Strip lieferte die generische :data:`_NUM_RE`-Extraktion
# alle Zahlen inkl. der Annotation als vermeintliche Range-Grenzen:
#
# * ``"5.5 (2020)"``       -> nums = [5.5, 2020] -> (5.5, 2020.0)      (Jahr als hi)
# * ``"5-7 Mohs (Nr. 42)"`` -> nums = [5, 7, 42] -> (5.0, 42.0)         (Katalog-Nr. als hi)
# * ``"2.65 (Ref 42)"``    -> nums = [2.65, 42] -> (2.65, 42.0)         (Ref-Nr. als hi)
# * ``"5.5-7.0 [2024]"``   -> nums = [5.5, 7, 2024] -> (5.5, 2024.0)    (Jahr ueberschreibt Range-hi)
#
# Bei allen inverted-Range-Faellen (Annotation-Zahl < Zentrum-Zahl) griff
# der ``if hi < lo``-Fallback und kollabierte auf ``(lo, lo)`` (Toleranz-
# aehnlicher Schutz). Sobald die Annotation-Zahl aber *groesser* als das
# Zentrum ist - typisch bei Jahres-Marker (2020, 2024) oder Katalog-Nummern
# (Nr. 42, Nr. 1234) - wurde die Annotation stille als hoher Range-Wert
# gelesen und produzierte mineralogisch/sammlungslogisch unsinnige Bereiche
# ("Wert 2.65 bis 2020 g/cm³" statt "Wert 2.65 g/cm³, Referenz-Jahr 2020").
#
# Iterative Regex-Substitution loest verschachtelte Klammern von innen
# nach aussen: bei ``"5.5 (Foto (gut))"`` matcht der Innen-Pass zuerst
# ``(gut)`` (kein weiterer Nest-Inhalt), dann der Aussen-Pass ``(Foto  )``.
# Fixpunkt-Loop stoppt, wenn keine Klammer mehr matcht. Runde/eckige/
# geschweifte Klammern werden symmetrisch behandelt - die drei Klammer-
# Varianten sind in Sammler-Notizen austauschbar (rund am haeufigsten,
# eckig fuer technische/maschinen-lesbare Marker, geschweift selten aber
# spec-konform).
#
# Kritischer Rueckfall-Schutz: wenn der Strip den gesamten Zahl-Inhalt
# entfernt (weil der Wert *selbst* in Klammern steht, z.B. ``"(5-7)"``,
# ``"(2.65)"`` oder ``"[5,7]"`` als mathematisches Intervall), wird der
# Original-String beibehalten. Die Heuristik ``_HAS_DIGIT.search(stripped)``
# entscheidet: nur wenn nach dem Strip noch Ziffern uebrig sind, ist die
# Klammer wirklich Annotation und nicht der Wert-Traeger; sonst wird die
# Klammer als Wert-Umhuellung interpretiert (spiegelt die Standard-
# Konvention, dass ``"(5-7)"`` = "5 bis 7" und ``"(2.65)"`` = "2.65"
# einwertig sind, wie sie in Buchhaltungs-/Formular-Auszuegen mit
# Trenner-Klammern und in mathematischen Intervall-Notationen ueblich
# sind). Damit bleibt die Grenzform-Semantik erhalten und der Strip
# greift nur, wenn die Klammer eindeutig Annotation zum Wert-Traeger ist.
_BRACKETED_ROUND = re.compile(r"\([^()]*\)")
_BRACKETED_SQUARE = re.compile(r"\[[^\[\]]*\]")
_BRACKETED_CURLY = re.compile(r"\{[^{}]*\}")
_HAS_DIGIT = re.compile(r"\d")

# ASCII-Doppel-/Dreifach-Dot-Range-Separator zwischen zwei Zahl-Tokens
# (Fortran-/Pascal-/Ruby-Range-Notation ``3.5..5.5``, ``1..10``, Publikations-
# Range-Notation ``3.5...5.5``, ``1e5..2e5``, ``0.5..1.5 mm``). Ohne diese
# Vorverarbeitung fallen alle Formen still auf einen Range-Kollaps zurueck: das
# generische :data:`_NUM_RE` liest den zweiten Dot als "leading-dot decimal"
# (``.5`` in ``3.5..5.5``) und extrahiert ``[3.5, 0.5, 0.5]``; via
# ``hi < lo``-Kollaps auf ``(3.5, 3.5)`` geht die obere Range-Grenze verloren.
# Bei Ganzzahl-Bereichen (``3..5``) blockt die zwei Dots die naechste Match-
# Position und liefert nur ``[3]``, ebenfalls Kollaps auf (3.0, 3.0). Bei
# Scientific-Notation-Bereichen (``1e5..2e5`` -> ``[1e5, 0.2e5]``) ebenfalls
# stille Kollaps auf die Mantisse.
#
# Silenter Datenverlust auf der oberen Range-Grenze bei der Migration aus:
# (1) Publikationen mit Publikations-Range-Notation, in denen ``..``/``...``
#     als Range-Trenner statt ``-``/``–`` verwendet wird (verbreitet in
#     wissenschaftlichen Tabellen, in denen der Bindestrich als Sub-/Vorzeichen
#     reserviert ist und ``..`` als visuell klareres Trenner-Zeichen dient);
# (2) Sammler-Notizen aus Textdatei-Sammlungen (RTF/TXT ohne Autoformat-
#     Konvertierung zu ``–``/``…``), in denen der Sammler die ASCII-Form
#     verwendet;
# (3) Datenbank-Exporten aus Fortran-/Ruby-basierten GIS-/Kristall-Tools,
#     die Range-Werte als ``a..b``-Literale serialisieren.
#
# Fix: Preprocessing-Regex ersetzt ``\d{...}..\d``/``\d{...}...\d``-Sequenzen
# durch ``\d-\d``-Sequenzen (ohne Whitespace, damit der Bindestrich unmittelbar
# zwischen Ziffern steht und die Sign-Lookbehind-Klausel ``(?<![\d.%‰])-`` in
# :data:`_NUM_RE` das ``-`` als Separator statt Sign erkennt). Bewusst
# konservativ: nur zwei oder drei Dots werden akzeptiert (Ruby-Style ``..``
# und Publikations-Style ``...``); vier oder mehr Dots (typografischer Muell
# oder OCR-Fehler) bleiben unangetastet. Guards ``(?<=\d)`` links und
# ``(?=\d)`` rechts stellen sicher, dass der Dot-Cluster tatsaechlich zwischen
# Ziffern steht - reine trailing/leading Dot-Cluster (``3..``, ``..5``) sowie
# Dot-Cluster in Fliesstext (``Cluster ... aber``) bleiben unangetastet.
# Kollisionsfrei zu:
#   - IUCr-Uncertainty ``5.5(3)`` (nutzt Klammer, keine Dots)
#   - ±-Uncertainty ``5.5 ± 0.3`` (nutzt ``±``/``+-``/``+/-``, keine Dots)
#   - Standard-Range ``3.5-5.5``/``3.5 - 5.5``/``3.5–5.5`` (nutzt Bindestrich/En-Dash)
#   - Unicode-Ellipsis ``3.5 … 5.5`` (funktioniert bereits ueber Whitespace-
#     Trennung, wird von diesem Fix nicht beruehrt)
#   - Einzelwerte mit Trailing-Ellipsis ``5.5...`` (kein digit rechts, kein Match)
#   - Nummerierungen ``1.2.3.4`` (nur einzelne Dots, kein 2+-Cluster)
_DOTTED_RANGE_SEPARATOR = re.compile(r"(?<=\d)\.{2,3}(?=\d)")

# Explizit-Multiplikations-Form der wissenschaftlichen Zehnerpotenz auf die
# Standard-Scientific-Notation ``NeM`` normalisieren, damit :data:`_NUM_RE`
# den Wert als *eine* Zahl liest statt Mantisse und Exponent-Basis (10) als
# zwei Range-Grenzen zu extrahieren. In Publikationen und Sammler-Notizen
# aus wissenschaftlichen Quellen kommt die explizite Form (``2.5 · 10^3``,
# ``2.5 × 10^-3``, ``2.5*10^3``, ``2.5x10^3``) haeufig statt der kompakten
# E-Notation vor - Word/LaTeX/PDF-Autoformat setzt das Multiplikations-
# Zeichen typografisch (``·`` U+00B7 MIDDLE DOT, ``⋅`` U+22C5 DOT OPERATOR,
# ``×`` U+00D7 MULTIPLICATION SIGN) und den Exponenten oft als Unicode-
# Superscript (``2.5·10³``, ``2.5×10⁻³``). Ohne Normalisierung liest
# :data:`_NUM_RE` z.B. ``2.5·10^3`` als ``[2.5, 10, 3]`` (Middle-Dot ist kein
# Zahl-Teil, ``^3`` faellt aus dem Zahl-Match); der ``if hi < lo``-Kollaps oder
# die letzte Zahl gewinnen als vermeintliche Range-Grenze - der publizierte
# Faktor 10^3 geht stille verloren. Beide Zweige (Caret + ASCII-Exp / Unicode-
# Superscript-Exp) werden vor allen weiteren Zahl-Patterns via
# :func:`_normalize_explicit_mult_power10` auf ``NeM`` umgeschrieben.
#
# Sowohl ``·`` (U+00B7 MIDDLE DOT) als auch ``⋅`` (U+22C5 DOT OPERATOR) werden
# akzeptiert: die beiden Codepunkte sehen visuell nahezu identisch aus, sind
# aber unicode-kategorisch getrennt. MIDDLE DOT ist der typografische General-
# Punkt, der in DE-Print-Publikationen (Hollemann-Wiberg, Ternes) fuer die
# Multiplikation gesetzt wird; DOT OPERATOR ist das mathematische Operator-
# Symbol, das LaTeX ``\cdot`` und MathJax beim Rendern erzeugen - Wikipedia-
# Artikel zu Mineralen (``Fluoreszenz-Ausbeute 2.5·10⁻³`` in einer Physik-
# Info-Box), aus MathJax-gerenderten PDFs kopierte Publikations-Snippets und
# aus LaTeX-Quellen exportierte Referenz-Tabellen enthalten haeufig U+22C5.
# Ohne die zusaetzliche Alternante fielen genau diese Copy-Paste-Faelle auf
# den ``(mantisse, 10.0)``-Fehlpfad und die Groessenordnung ging in der
# Migration silent verloren.
_SUPERSCRIPT_TO_ASCII: dict[str, str] = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁻": "-", "⁺": "+",
}
_EXPLICIT_MULT_POWER10_CARET = re.compile(
    r"(?<![A-Za-z0-9])"
    r"((?:(?<![\d.%‰])-)?(?:\.\d+|\d+(?:[.,]\d+)?))"
    r"\s*[·⋅×*xX]\s*"
    r"10\s*\^\s*"
    r"([-+]?\d+)"
    r"(?![.,]?\d)"
)
_EXPLICIT_MULT_POWER10_SUPER = re.compile(
    r"(?<![A-Za-z0-9])"
    r"((?:(?<![\d.%‰])-)?(?:\.\d+|\d+(?:[.,]\d+)?))"
    r"\s*[·⋅×*xX]\s*"
    r"10"
    r"([⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)"
)


def _normalize_explicit_mult_power10(s: str) -> str:
    """``N · 10^M`` / ``N × 10³`` → ``NeM`` (Standard-Scientific-Notation)."""
    def _caret(m: re.Match) -> str:
        return f"{m.group(1)}e{m.group(2)}"

    def _super(m: re.Match) -> str:
        exp = "".join(_SUPERSCRIPT_TO_ASCII[c] for c in m.group(2))
        return f"{m.group(1)}e{exp}"

    s = _EXPLICIT_MULT_POWER10_CARET.sub(_caret, s)
    s = _EXPLICIT_MULT_POWER10_SUPER.sub(_super, s)
    return s

# Unicode-Vulgar-Fraktionen (U+00BC/U+00BD/U+00BE und U+2150-U+215E) auf ihre
# Dezimal-Aequivalente abbilden. In der Mineralogie ist die Halbschritt-
# Notation ``5½`` bei Mohs-Haerte-Angaben die klassische Referenz-Tabellen-
# Form (Mohs-Skala misst in Halbschritten zwischen Ganzzahl-Referenzmineralen:
# 5½ = zwischen Apatit und Orthoklas, 6½ = zwischen Orthoklas und Quarz),
# und ¼/¾-Notation kommt in Groessen-/Gewichts-Angaben aeltere Sammlungs-
# Karten und in imperialen Einheiten-Notationen vor. ⅛/⅜/⅝/⅞-Notation ist
# typisch fuer feinere Groessen-Rasterungen (Sieb-Rueckstands-Tabellen,
# Kristall-Achsen-Zerlegungen). Die 1/3-/1/5-/1/6-/1/7-/1/9-/1/10-Reihen
# sind seltener, aber in ISO-31-0 und wissenschaftlichen Publikationen
# spec-konform enthalten und werden symmetrisch zur Standard-Achse
# unterstuetzt.
#
# Bisher fielen alle Formen mit Unicode-Vulgar-Fraktion auf einen stille
# Fraktions-Datenverlust: ``5½`` wurde als ``[5]`` gelesen (die ½-Char
# faellt nicht in ``_NUM_RE``) und lieferte (5.0, 5.0) statt (5.5, 5.5);
# der publizierte Halbschritt der Mohs-Skala ging verloren und die
# Sortier-/Vergleichs-Reihenfolge stimmte nicht mehr mit der Referenz-
# Tabelle ueberein. Standalone ``¼`` lieferte ``(None, None)`` (keine
# Zahl gefunden), obwohl der Wert eindeutig 0.25 ist. Bei der Migration
# aus mineralogischen Referenz-Tabellen und aus Sammler-Notizen, die
# aus Word/LibreOffice-Writer/PDF-/HTML-Quellen mit typografisch sauber
# gesetzten Unicode-Fraktionen stammen (Word-Autoformat wandelt ``1/2``
# und ``1/4`` beim Eintippen automatisch zu ½/¼; DOCX-/PDF-Exporte und
# LaTeX-Ausgaben nutzen die Unicode-Formen als Standard), entstand
# damit silent Wert-Datenverlust.
#
# Die Fraktions-Dezimalen sind die Nachkomma-Ziffern *ohne* fuehrende
# ``0.`` - werden je nach Kontext an Ganzzahl-Vorstand (Mixed-Form
# ``5½`` -> ``5.5``) oder an ``"0"`` (Standalone-Form ``½`` -> ``0.5``)
# konkateniert. Fuer die periodischen Bruchteile (⅓ = 0.333..., ⅔ = 0.667...,
# ⅐ = 0.142..., ⅑ = 0.111..., ⅙ = 0.167..., ⅚ = 0.833...) werden 12
# signifikante Nachkomma-Stellen verwendet - genug, um den IEEE-754-double-
# Praezisionsbereich sauber abzubilden (mantisse ~15-17 Stellen), ohne
# runde Zahlen kuenstlich zu verlaengern. ⅔ wird auf ``0.666666666667``
# gerundet (letzte Ziffer nach oben, um den Rundungs-Fehler zur
# mathematischen 2/3 zu minimieren).
_VULGAR_FRACTION_DECIMALS: dict[str, str] = {
    "¼": "25",              # ¼ = 1/4
    "½": "5",               # ½ = 1/2
    "¾": "75",              # ¾ = 3/4
    "⅐": "142857142857",    # ⅐ = 1/7
    "⅑": "111111111111",    # ⅑ = 1/9
    "⅒": "1",               # ⅒ = 1/10
    "⅓": "333333333333",    # ⅓ = 1/3
    "⅔": "666666666667",    # ⅔ = 2/3
    "⅕": "2",               # ⅕ = 1/5
    "⅖": "4",               # ⅖ = 2/5
    "⅗": "6",               # ⅗ = 3/5
    "⅘": "8",               # ⅘ = 4/5
    "⅙": "166666666667",    # ⅙ = 1/6
    "⅚": "833333333333",    # ⅚ = 5/6
    "⅛": "125",             # ⅛ = 1/8
    "⅜": "375",             # ⅜ = 3/8
    "⅝": "625",             # ⅝ = 5/8
    "⅞": "875",             # ⅞ = 7/8
}
_VULGAR_FRACTION_CLASS = "[" + "".join(_VULGAR_FRACTION_DECIMALS) + "]"

# Mixed-Form-Regex ``(Ganzzahl)(optional Whitespace)(Fraktion)`` -> ``Ganzzahl.Dez``.
# Lookbehind spiegelt die _NUM_RE-Konvention: keine Substitution nach Buchstaben
# (``cm3½`` bleibt unangetastet, weil die 3 Teil der SI-Einheit ist, nicht Teil
# der Wert-Zahl), nach Caret (``m^3½`` genauso), nach Punkt/Komma (``5.5½``
# waere ein defekter Dezimal-Mixed-Form-Anhang, unklare Semantik - besser
# unangetastet lassen als kuenstlich zu ``5.5.5`` zu erweitern) und nach einer
# anderen Ziffer (``123½`` matcht als komplette Zahl "123", nicht nur "23";
# ``\d+`` ist greedy, aber der Lookbehind auf die *erste* Ziffer schuetzt vor
# Mitte-der-Zahl-Positionen). Whitespace-Trennung zwischen Ganzzahl und
# Fraktion (``5 ½``, ``5\xa0½``) erlaubt, weil in Print-/Katalog-Formen mit
# typografisch sauberem Halbschritt-Space (NBSP, thin space) die Konvention
# gaengig ist. Kollisionsfreiheit zur wissenschaftlichen Notation ``5e½``:
# nach der Ganzzahl-Extraktion ``\d+`` sitzt der Cursor auf dem ``e``, dann
# ``\s*`` matcht 0 Zeichen, dann Fraktion - aber next char ist ``e``, keine
# Fraktion; kein Match. ``5e½`` bleibt unveraendert.
_MIXED_FRACTION_RE = re.compile(
    rf"(?<![A-Za-z^.,\d])(\d+)\s*({_VULGAR_FRACTION_CLASS})"
)
# Standalone-Form-Regex einzelne Fraktion ohne vorangehende Ganzzahl -> ``0.Dez``.
# Lookbehind ``(?<![A-Za-z\d])`` schuetzt vor Bezeichner-Kontexten (``Sample½``
# bleibt Bezeichner, keine kuenstliche 0.5-Interpretation) und vor der Nach-
# Mixed-Form-Position (der ``5`` in ``5½`` wurde in sub1 bereits konsumiert -
# aber Sicherheitsnetz fuer den ``0.5`` nach ``5½``-Substitution: nach sub1 ist
# der String ``5.5``, die ``.5`` steht nach der ``5.`` und der Lookbehind
# blockiert die Fraktion, waere sie noch da). Auch nach einem Ziffer-nach-Fraktion-
# Kontext wie ``½5`` blockiert der nicht-Standalone-Kontext nicht (die Fraktion
# ist am Anfang, kein Digit davor), sub2 wuerde matchen: ``½5`` -> ``0.55``. Das
# ist eine seltene Grenzform (typografisch ungewoehnliche Wert-Notation),
# semantisch tolerabel als Verwechslung mit einer verdrehten Mixed-Form.
_STANDALONE_FRACTION_RE = re.compile(
    rf"(?<![A-Za-z\d])({_VULGAR_FRACTION_CLASS})"
)


def _normalize_vulgar_fractions(s: str) -> str:
    """Ersetzt Unicode-Vulgar-Fraktionen durch ihre Dezimal-Aequivalente.

    Mixed-Form ``5½``/``5\xa0½`` wird zu ``5.5``; standalone ``½`` wird
    zu ``0.5``. Wird in :func:`parse_range` *vor* der generischen Zahl-
    Extraktion aufgerufen, damit die publizierten Halbschritt-/Viertel-/
    Achtel-Werte aus mineralogischen Referenz-Tabellen (Mohs-Haerte,
    Groessen-/Gewichts-Fraktionen, Sieb-Rueckstaende) nicht stille
    verloren gehen. Siehe :data:`_VULGAR_FRACTION_DECIMALS` fuer die
    vollstaendige Zeichen-Tabelle und die Rundungs-Konvention der
    periodischen Bruchteile.
    """
    s = _MIXED_FRACTION_RE.sub(
        lambda m: f"{m.group(1)}.{_VULGAR_FRACTION_DECIMALS[m.group(2)]}", s
    )
    s = _STANDALONE_FRACTION_RE.sub(
        lambda m: f"0.{_VULGAR_FRACTION_DECIMALS[m.group(1)]}", s
    )
    return s


# ASCII-Mixed-Fraktion (Ganzzahl + Whitespace + Zaehler/Nenner) auf Dezimal-
# Aequivalent abbilden. Spiegelt die Unicode-Vulgar-Fraktions-Normalisierung
# (:func:`_normalize_vulgar_fractions`) auf die Plain-ASCII-Achse - typische
# Notation aus Typewriter-/Terminal-Notizen, aus geerbten Textdatei-
# Sammlungen (RTF/TXT ohne Autoformat-Konvertierung zu ½/¼) und aus
# handschriftlich abgeschriebenen Mohs-Haerte-Werten, bei denen der Autor
# den Halbschritt als ``5 1/2`` statt ``5½`` notiert. In der Mineralogie
# ist die Halbschritt-Notation die Referenz-Tabellen-Konvention (Mohs misst
# zwischen Ganzzahl-Referenzmineralen); in imperialen Groessen-/Gewicht-
# Angaben ist ``5 3/4 inch``/``2 1/8 g`` die uebliche Feiner-Rasterung.
#
# Bisher fielen alle Mixed-Formen still auf einen Fraktions-Datenverlust
# via generischer Zahl-Extraktion: ``5 1/2`` wurde als ``[5, 1, 2]`` gelesen
# und lieferte via ``if hi < lo``-Fallback ``(5.0, 5.0)`` (der Halbschritt
# ging verloren, die Mohs-Referenz-Reihenfolge stimmte nicht mit der
# Tabelle ueberein); ``5 3/4 - 7 1/2`` lieferte via [5, 3, 4, 7, 1, 2] den
# semantisch falschen Range ``(5.0, 7.0)`` (beide Halbschritte verloren);
# ``5 3/4 Mohs`` lieferte ``(3.0, 4.0)`` als Range der Fraktion (Wert der
# Ganzzahl verworfen). Bei der Migration aus geerbten Textdatei-Sammlungen
# entstand damit silent Wert-Datenverlust in der Haerte-/Dichte-/Groessen-
# Achse.
#
# Sicherheitsschranken:
#
# * Nur Whitespace-getrennte Mixed-Form ``\d+\s+\d+/\d+`` - ohne Whitespace-
#   Trenner (``5/2``) ist die Notation semantisch mehrdeutig (Range 5-2,
#   Ratio 5:2, Fraktion 2.5, Einheit ``g/cm2``) und faellt unangetastet
#   auf die generische Zahl-Extraktion zurueck. Der Whitespace zwischen
#   Ganzzahl-Vorstand und Fraktion ist die stabile Abgrenzung zur Ratio-/
#   Einheiten-Notation.
# * Nur *proper* Fraktionen (Zaehler < Nenner) - improper Formen wie
#   ``5/2`` als Fraktion (2.5) sind in Sammler-Notizen semantisch mehr-
#   deutig und bleiben unangetastet.
# * Erlaubte Nenner :data:`_ASCII_FRACTION_ALLOWED_DENOMINATORS` -
#   {2, 3, 4, 5, 6, 8, 10, 16, 32} deckt die typischen mineralogischen
#   und imperialen Fraktions-Klassen ab (Halbschritt-Mohs, Viertel-/
#   Achtel-/Sechzehntel-/Zweiundreissigstel-Imperial, Tenth-Metrik,
#   Drittel/Sechstel-ISO). Denominatoren ausserhalb dieser Menge fallen
#   auf keine Substitution zurueck und schuetzen vor Kollisionen mit
#   Datums-Fragmenten (Tag/Monat-Notation ``6/1985`` mit Nenner 1985,
#   Kalender-Notation ``6 6/2024`` mit Nenner 2024), Katalog-/Referenz-
#   Nummern (``5 42/100`` mit Nenner 100 als "42 von 100") und mit
#   ratio-Konvention (``5 3/12`` als "3 zu 12" ohne Fraktion-Semantik).
# * Lookbehind ``(?<![A-Za-z^.,\d])`` blockiert nach Buchstaben (``cm2 1/2``
#   bleibt Einheiten-Kontext), nach Caret (``m^3 1/2``), nach Punkt/
#   Komma (``5.5 1/2`` ist semantisch unklar) und nach anderer Ziffer
#   (Sicherheitsnetz gegen greedy-Match-Ueberreichweite). Spiegelt die
#   :data:`_MIXED_FRACTION_RE`-Konvention der Unicode-Achse.
# * Lookahead ``(?!/\d)`` blockiert vor einer weiteren ``/\d``-Gruppe
#   (Datum-Fragment ``5 6/1985/2000`` matcht sonst ``5 6/1985`` und
#   liefert ``5.<invalid>`` - wenn 1985 nicht im Allow-Set ist, wird der
#   Match verworfen; aber die Lookahead-Bedingung stoppt den Match schon
#   in der Vorabpruefung). Auch fuer Ratio-Ketten wie ``5 1/2/3``
#   praktisch (unklare Semantik, besser unangetastet).
#
# Ergebnis: ``5 1/2`` -> ``5.5`` (Mohs-Halbschritt), ``5 3/4`` -> ``5.75``
# (imperialer Dreiviertel-Wert), ``5 1/3`` -> ``5.333333333333`` (periodische
# Fraktion mit 12 signifikanten Nachkomma-Stellen), ``5 15/16`` -> ``5.9375``
# (imperialer Sechzehntel-Wert), Range ``5 1/2 - 6 1/2`` -> ``5.5 - 6.5``
# und (5.5, 6.5), Uncertainty ``5 1/2 ± 0.3`` -> ``5.5 ± 0.3`` und
# (5.2, 5.8), Trailing-Einheit ``5 3/4 Mohs`` -> ``5.75 Mohs`` und
# (5.75, 5.75).
_ASCII_FRACTION_ALLOWED_DENOMINATORS: frozenset[int] = frozenset(
    {2, 3, 4, 5, 6, 8, 10, 16, 32}
)
_ASCII_MIXED_FRACTION_RE = re.compile(
    r"(?<![A-Za-z^.,\d])(\d+)\s+(\d+)/(\d+)(?!/?\d)"
)

# ASCII ``x``/``X`` zwischen zwei Ziffern als Dimensions-Separator: ``5x10mm`` /
# ``2.5x3.0x4.0mm`` / ``LxWxH``-Kompaktnotation aus Sammler-/Katalog-Notizen
# (Matrix-Groesse eines Kristalls, Ausdehnung eines Handstuecks, Foto-Massband-
# Ablesung im Freitext-Feld). In der Mineralogie ist die Notation ``5x10mm``
# der klassische Weg, "5 mm mal 10 mm" ohne separates Breite-Feld zu notieren -
# haeufig aus geerbten Excel-Kopien mit nur einer Groessen-Spalte, aus
# Foto-Katalog-Software mit Freitext-Groessen-Feld und aus handschriftlichen
# Sammler-Karten, in denen der Autor Platz spart.
#
# Bisher fiel die ASCII-x-Form still auf silenten Datenverlust der zweiten
# (und dritten) Dimension: ``_NUM_RE`` hat den negativen Lookbehind
# ``(?<![A-Za-z^])``, der eine Ziffer direkt nach einem Buchstaben blockiert
# (Schutz gegen Bezeichner-Nummerierung wie ``Sample3`` und gegen ASCII-
# Hochzahl-Einheiten wie ``cm3``/``m^2``). Damit blockte ``5x10`` das zweite
# Zahl-Token: ``5`` matcht (kein Letter davor), ``10`` blockiert (``x`` davor
# ist Letter). Ergebnis (5.0, 5.0) - die zweite Dimension ging still verloren;
# ``5x10x15`` analog (5.0, 5.0), obwohl die maximale Ausdehnung 15 die
# eigentliche Sortier-/Vergleichs-Groesse in einer Groessen-Spalte ist;
# ``2.5x3.0mm`` lieferte (2.5, 2.5). Bei der Migration aus Katalog-Software
# mit Freitext-Groesse und aus geerbten Excel-Kopien entstand damit silenter
# Range-Datenverlust in der Groessen-Achse.
#
# Unicode-Multiplikations-Zeichen ``×`` (U+00D7) matchte hingegen schon
# bisher als Range-Separator (kein Letter in ``_NUM_RE``-Lookbehind, kein
# Zahl-Bestandteil): ``5×10`` lieferte (5.0, 10.0) korrekt. Die neue
# Normalisierung schliesst die ASCII-Fallback-Luecke und macht ``5x10``
# / ``5X10`` semantisch aequivalent zur Unicode-Variante - konsistent mit
# der ``_normalize_vulgar_fractions``-/``_normalize_ascii_mixed_fractions``-
# Konvention, ASCII-Ersatzformen typografisch sauberer Notation auf die
# gleiche Behandlung zu heben.
#
# Regex ``(\d)[xX](\d)`` verlangt Ziffern direkt vor und nach ``x``/``X``,
# ohne Whitespace-Toleranz - die Whitespace-Form ``5 x 10`` funktioniert
# bereits ohne Sub, weil der Whitespace selbst der Separator ist und ``_NUM_RE``
# beide Zahlen findet. Nur die Whitespace-lose Compact-Form braucht die
# Substitution zur Trennung. Substitution durch Leerzeichen (nicht durch
# ``×``) hat den Vorteil, dass ``_NUM_RE`` das Ergebnis ohne weitere
# Normalisierung findet - der Lookbehind sieht das Leerzeichen und laesst
# die zweite Ziffer als eigenstaendiges Token durch.
#
# Kollisions-Schutz durch die Digit-Anker: Bezeichner mit ``x`` (``Excel``,
# ``Textur``) haben keinen digit-x-digit-Match und bleiben unangetastet.
# Der Fall ``Sample5x10`` (Katalog-Bezeichner mit angehaengter Dimensions-
# Notation) wird zu ``Sample5 10`` - ``5`` bleibt via ``_NUM_RE``-Lookbehind
# (Letter davor) blockiert, ``10`` matcht nach Leerzeichen als (10, 10);
# das ist gegenueber dem alten Verhalten (None, None) ein Info-Gewinn (der
# einzige gefundene Zahl-Wert wird nicht mehr komplett verworfen). Der Fall
# ``3x10^-3`` (scientific-notation-artige Konstrukte) wird zu ``3 10^-3``:
# ``3`` matcht als (3, 3), ``10`` wird durch ``^`` blockiert (``_NUM_RE``-
# Lookbehind schliesst ``^`` ein) - konsistent mit dem bisherigen
# ASCII-Hochzahl-Schutz. Fuer echte scientific notation ``3e-3`` /
# ``3E-3`` gibt es keinen ``x`` und der Zweig greift nicht.
#
# Digit-Lookahead ``(?=\d)`` statt konsumierender zweiter Digit-Gruppe: die
# rechte Digit-Kante bleibt im Reststring stehen und ist beim naechsten
# re.sub-Scan-Schritt selbst wieder LINKE Kante eines potenziellen Digit-x-
# Digit-Matches. Ohne diesen Lookahead-Modus (also bei der konsumierenden
# Form ``(\d)[xX](\d)``) fielen alle chainings mit ungerader Segment-Laenge
# still auf silenten Datenverlust der mittleren/hinteren Dimensionen: bei
# ``1x2x3`` (all-single-digit-chain) matcht der erste Pass ``1x2`` und
# konsumiert die Ziffern auf beiden Seiten des ersten ``x``; der naechste
# Scan-Schritt beginnt an Position 3 (dem zweiten ``x``) und findet dort
# keine Digit-Kante mehr (die ``3`` steht isoliert am Ende ohne rechten
# Digit-Partner), das Ergebnis nach der Substitution ist ``1 2x3`` - die
# ``3`` bleibt via ``_NUM_RE``-Letter-Lookbehind hinter dem ``x`` weiter
# blockiert und fliesst als silenter Datenverlust nicht in die Zahl-Menge
# ein: ``nums=[1, 2]`` -> ``(1, 2)`` statt der publizierten ``(1, 3)``.
# Bei ``5x1x2`` (start-multidigit, mittlere-single) noch schlimmer: der
# erste Pass matcht ``5x1``, das zweite ``x`` bleibt ohne konsumiertes
# Zeichen zurueck, ``2`` blockiert weiter via Letter-Lookbehind, nums=[5, 1]
# via inverted-Range-Kollaps auf ``(5, 5)`` - die dritte Dimension
# komplett verloren. Der Lookahead ``(?=\d)`` fixt beide Faelle: die
# rechte Ziffer bleibt stehen und wird beim naechsten Scan-Schritt selbst
# zur linken Kante der naechsten Digit-x-Digit-Sequenz - ``1x2x3`` ->
# ``1 2 3`` -> ``(1, 3)``, ``5x1x2`` -> ``5 1 2`` -> ``(5, 5)`` via
# inverted-Range-Kollaps (Autor hat groesste Dimension zuerst - konsistent
# mit der bestehenden Semantik). Ersetzung wird ``\1 `` (nur die vorherige
# Ziffer plus Leerzeichen anstelle des ``x``; die rechte Ziffer bleibt
# unangetastet fuer den naechsten Scan). Semantisch identisch zur
# Unicode-``×``-Behandlung (die ``×`` ist kein Letter und blockiert den
# Lookbehind ohnehin nicht, alle konsekutiven ``×``-Sequenzen werden
# transparent gelesen: ``1×2×3`` -> nums=[1, 2, 3] -> ``(1, 3)``,
# ``5×1×2`` -> ``(5, 5)`` via Kollaps).
_DIMENSION_X = re.compile(r"(\d)[xX](?=\d)")


def _ascii_mixed_fraction_replace(m: re.Match) -> str:
    """Callback fuer :data:`_ASCII_MIXED_FRACTION_RE`: Mixed-Form -> Dezimal.

    Denominator-Whitelist :data:`_ASCII_FRACTION_ALLOWED_DENOMINATORS` und
    Proper-Fraktions-Check (Zaehler < Nenner) filtern semantisch mehr-
    deutige Kombinationen (Datum-/Katalog-/Ratio-Fragmente). Bei Filter-
    Miss wird der Original-Match unveraendert zurueckgegeben - die
    generische Zahl-Extraktion nimmt dann die einzelnen Tokens.

    12 signifikante Nachkomma-Stellen fuer periodische Fraktionen (1/3,
    2/3, 1/6, 5/6) decken den IEEE-754-double-Praezisionsbereich sauber
    ab und terminieren die Dezimal-Repraesentation bei Bruchteilen mit
    endlicher Basis-10-Entwicklung (1/2, 1/4, 3/4, 1/8, 3/8, ...) via
    Trailing-Zero-Strip.
    """
    integer, num, denom = m.group(1), int(m.group(2)), int(m.group(3))
    if denom not in _ASCII_FRACTION_ALLOWED_DENOMINATORS or num >= denom:
        return m.group(0)
    frac = num / denom
    frac_str = f"{frac:.12f}".rstrip("0").rstrip(".")
    if frac_str.startswith("0."):
        frac_str = frac_str[2:]
    elif frac_str == "0":
        return m.group(0)
    return f"{integer}.{frac_str}"


def _normalize_ascii_mixed_fractions(s: str) -> str:
    """Ersetzt ASCII-Mixed-Fraktionen ``\\d+\\s+\\d+/\\d+`` durch Dezimal-Aequivalente.

    ``5 1/2`` -> ``5.5``, ``5 3/4`` -> ``5.75``, ``2 1/8`` -> ``2.125``.
    Wird in :func:`parse_range` *nach* der Unicode-Fraktions-Normalisierung
    und *vor* der Uncertainty-Erkennung aufgerufen, damit die publizierten
    Halbschritt-/Viertel-/Achtel-Werte aus Plain-Text-Referenz-Tabellen
    (Typewriter-Notizen, TXT-Sammler-Karten, ASCII-Mail-Exporte) nicht
    stille verloren gehen. Siehe :data:`_ASCII_MIXED_FRACTION_RE` und
    :func:`_ascii_mixed_fraction_replace` fuer die Sicherheitsschranken
    (Denominator-Whitelist, Proper-Fraktion, Lookbehind/Lookahead-Schutz).
    """
    return _ASCII_MIXED_FRACTION_RE.sub(_ascii_mixed_fraction_replace, s)


# Explizit-Multiplikations-Notation der wissenschaftlichen Zehnerpotenz
# (``N × 10^M``, ``N · 10^M``, ``N * 10^M``, ``N x 10^M``, sowie die Unicode-
# Superskript-Form ``N × 10ᴹ``) auf die kompakte E-Notation ``NeM`` abbilden.
# In Mineralogie-/Physik-/Chemie-Publikationen der klassische typografische
# Standard fuer Werte, die viele Groessenordnungen ueberspannen: Absorptions-
# Querschnitte in cm² (``2.5 × 10⁻¹⁹``), Loeslichkeitsprodukte (``1.5 × 10⁻⁹
# mol²/kg²``), Aktivitaeten radioaktiver Isotope (``4.5 · 10⁹ a``), Kalibrier-
# Konstanten (``1.5 × 10⁻³``), Fluoreszenz-Lebensdauern (``3 · 10⁻⁶ s``), Bragg-
# Winkel-Beugungs-Faktoren (``5.5 · 10⁻² Å``) sowie thermische Ausdehnungs-
# Koeffizienten (``β = 5.5 × 10⁻⁶ K⁻¹``). Waehrend die kompakte E-Notation
# ``2.5e-19`` in Computer-Ausgaben und Excel-Auto-Format dominiert, ist die
# explizit-multiplikative Form ``2.5 × 10⁻¹⁹`` die kanonische Setz-Weise in
# gedruckten Referenz-Tabellen, in LaTeX-/PDF-Publikationen und in Sammler-
# Notizen, die aus Print-Quellen (Mineralogie-Handbuecher, Hollemann-Wiberg,
# CRC Handbook) uebernommen wurden. Bisher fielen alle diese Formen still auf
# eine strukturell falsche Range-Interpretation: die generische ``_NUM_RE``-
# Extraktion las Mantisse und ``10`` als zwei separate Zahl-Tokens und lieferte
# via ``(lo, hi)``-Aufbau den unsinnigen Range ``(<mantisse>, 10.0)``:
# ``5.5 × 10^-3`` lieferte ``(5.5, 10.0)`` statt ``(0.0055, 0.0055)`` -
# Groessenordnung komplett verloren, Wert mit dem Basis-Radix vertauscht;
# ``2.5 · 10⁻¹⁹`` (Superskript-Form) analog auf ``(2.5, 10.0)`` (der Superskript-
# Exponent faellt aus ``_NUM_RE`` heraus, weil ``⁻¹⁹`` nicht in der ASCII-
# Zahl-Klasse liegt); ``1.5 * 10^3`` auf ``(1.5, 10.0)``. Bei der Migration aus
# Mineralogie-/Physik-Publikationen mit typografischer Explizit-Multiplikations-
# Notation entstand damit silenter Groessenordnungs-Datenverlust auf jeder Wert-
# Achse (Dichte, Aktivitaet, Loeslichkeit, spektroskopische Konstante, thermischer
# Koeffizient), oft ueber viele Groessenordnungen hinweg (``e-19`` -> 10 macht
# Sammlungs-Statistik und JSON-Export unbrauchbar).
#
# Normalisierung als Preprocessing-Schritt vor allen Zahl-Extraktions-Zweigen:
# Die explizit-multiplikative Form wird zur E-Notation gemappt, sodass die
# nachgelagerten Zweige (Uncertainty-Match, Zahl-Extraktion mit ``_NUM_RE``)
# transparent die bereits existierende E-Notations-Semantik nutzen. Der Schritt
# ist idempotent (bei erneuter Anwendung matcht nichts) und lokal-beschraenkt
# (matcht nur die vollstaendige Sequenz ``<mantisse> <mult-sign> 10 <exponent>``,
# nicht Teil-Muster).
#
# Multiplikations-Signaturen:
# - ``·`` (U+00B7, Middle Dot): typografischer Standard fuer Multiplikation in
#   DE-Print-Publikationen (Hollemann-Wiberg, Ternes Bio-Chemie, Straus/Sailer).
# - ``⋅`` (U+22C5, Dot Operator): mathematisches Operator-Symbol, das LaTeX
#   ``\cdot`` und MathJax beim Rendern erzeugen. Visuell nahezu identisch zu
#   U+00B7, aber unicode-kategorisch getrennt (Sm statt Po). Aus MathJax-
#   gerenderten Wikipedia-Info-Boxen, aus LaTeX-Quellen exportierten Referenz-
#   Tabellen und aus Publikations-Snippets kopierte Werte enthalten den
#   Codepunkt bevorzugt statt des Middle-Dot; beide Formen kommen in Sammler-
#   Notizen austauschbar vor, weil die Copy-Paste-Quelle den Codepunkt bestimmt.
# - ``×`` (U+00D7, Multiplication Sign): typografischer Standard fuer
#   Multiplikation in EN-Print-Publikationen (CRC Handbook, IUPAC Green Book,
#   Kluwer Handbook of Minerals).
# - ``*`` (U+002A, Asterisk): ASCII-Ersatz fuer Multiplikation in Terminal-/
#   Log-/E-Mail-Notizen und LaTeX-Roh-Exporten ohne Unicode.
# - ``x``/``X`` (U+0078/U+0058, letter): ASCII-Ersatz fuer Multiplikation in
#   Typewriter-/Terminal-Notizen; identisch behandelt zu ``×``, weil beide in
#   handschriftlichen und Terminal-Kontexten austauschbar sind. Das Lookbehind
#   ``(?<![A-Za-z0-9])`` an der Match-Start-Position schuetzt vor Namens-
#   Fragmenten wie ``Sample5x10^-3`` (der ``5`` in ``Sample5`` ist Teil des
#   Namens, kein Wert-Token) und Katalog-Nummern.
#
# Exponent-Signaturen:
# - ``^<sign?><digits>``: ASCII-Caret-Notation, verbreitet in Terminal-/Plain-
#   Text-/LaTeX-Roh-Quellen.
# - ``<superscript-digits>``: Unicode-Superskript (U+2070-U+2079 fuer Ziffern,
#   U+207B/U+207A fuer Vorzeichen), typografischer Standard in gedruckten
#   Publikationen und modernem Word-/PDF-Autoformat.
#
# Kollisionsfreiheit:
# - Zur bestehenden E-Notation ``1e-3``: die E-Notation hat keinen ``10``-
#   Basis-Radix in ihrer Struktur; das Match-Pattern fordert die explizite
#   ``10``-Sequenz, die in ``1e-3`` nicht existiert.
# - Zur Range-Notation ``5-10``: das Match-Pattern fordert eine Multiplikations-
#   Signatur ZWISCHEN Mantisse und ``10``; ein Range hat statt dessen einen
#   Hyphen und trifft das Pattern nicht.
# - Zur Uncertainty-Notation ``5 ± 3``: das Match-Pattern fordert die
#   Multiplikations-Signatur; ``±`` matcht nicht.
# - Zur SI-Kompakt-Einheit ``g cm^-3``: das Match-Pattern fordert eine Mantisse
#   VOR der Multiplikations-Signatur; ``cm^-3`` beginnt mit Buchstaben, keine
#   Mantisse davor, kein Match.
# - Zur Dimensions-/Groessen-Notation ``5x10 cm``: das Match-Pattern fordert
#   nach ``10`` einen Exponenten (``^<int>`` oder Superskript); ``5x10 cm``
#   hat weder das eine noch das andere, wird nicht angetastet und faellt
#   weiterhin auf die bestehende Range-Interpretation ``(5, 10)`` zurueck.
_UNICODE_SUPERSCRIPT_MAP = str.maketrans({
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁻": "-", "⁺": "+",
})

_EXPLICIT_EXPONENT_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<mantissa>\d+(?:[.,]\d+)?|\.\d+)"
    r"\s*(?:[·⋅×*]|[xX])\s*"
    r"10"
    r"(?:"
    r"\s*\^\s*(?P<caret>[+-]?\d+)"
    r"|"
    r"(?P<superscript>[⁰¹²³⁴⁵⁶⁷⁸⁹][⁰¹²³⁴⁵⁶⁷⁸⁹]*|[⁻⁺][⁰¹²³⁴⁵⁶⁷⁸⁹]+)"
    r")"
    r"(?![.,\d])"
)


def _normalize_explicit_multiplication_exponent(s: str) -> str:
    """Ersetzt ``N × 10^M`` / ``N · 10^M`` / ``N × 10ᴹ`` durch ``NeM``.

    Explizit-multiplikative Form der wissenschaftlichen Zehnerpotenz ist der
    typografische Standard in Print-Publikationen (Mineralogie-Handbuecher,
    Hollemann-Wiberg, CRC Handbook, IUPAC Green Book) und in LaTeX-/PDF-
    Quellen; die kompakte E-Notation ``1.5e-3`` dominiert in Computer-
    Ausgaben. Ohne diese Normalisierung wuerden alle Explizit-Formen als
    Range ``(mantisse, 10.0)`` fehlgelesen und die Groessenordnung ginge
    stille verloren - typisch fuer Absorptions-Querschnitte, Loeslichkeits-
    produkte, Isotopen-Aktivitaeten, Kalibrier-Konstanten. Siehe
    :data:`_EXPLICIT_EXPONENT_RE` fuer die Multiplikations- und Exponent-
    Signaturen sowie die Kollisions-Schutz-Zonen.
    """
    def _replace(m: re.Match) -> str:
        mantissa = m.group("mantissa")
        caret = m.group("caret")
        if caret is not None:
            exponent = caret
        else:
            exponent = m.group("superscript").translate(_UNICODE_SUPERSCRIPT_MAP)
        return f"{mantissa}e{exponent}"
    return _EXPLICIT_EXPONENT_RE.sub(_replace, s)


def _normalize_dotted_range_separator(s: str) -> str:
    """Ersetzt ``\\d..\\d``/``\\d...\\d``-Range-Separatoren durch einen einfachen Bindestrich.

    Siehe :data:`_DOTTED_RANGE_SEPARATOR` fuer Details zur Motivation
    (Fortran-/Pascal-/Ruby-Range-Notation und Publikations-Style-``...``).
    """
    return _DOTTED_RANGE_SEPARATOR.sub("-", s)


def _strip_bracketed_annotations(s: str) -> str:
    """Entfernt runde/eckige/geschweifte Klammer-Annotationen inklusive Nest.

    Iterativ von innen nach aussen, damit ``"(Foto (gut))"`` in zwei
    Passes verschwindet. Wenn der Strip alle Ziffern entfernt (Wert *selbst*
    in Klammern), wird der Original-String zurueckgegeben - die Klammer-
    Umhuellung wird dann als Wert-Traeger interpretiert, nicht als Annotation.
    """
    prev = None
    stripped = s
    while prev != stripped:
        prev = stripped
        stripped = _BRACKETED_ROUND.sub("", stripped)
        stripped = _BRACKETED_SQUARE.sub("", stripped)
        stripped = _BRACKETED_CURLY.sub("", stripped)
    if _HAS_DIGIT.search(stripped):
        return stripped
    return s


# Range-Notation ``<Wert><Einheit>-<Wert><Einheit>`` mit identischer Einheit auf
# beiden Seiten des Bindestrichs (``3mm-5mm``, ``1.5g-2.5g``, ``5cm-10cm``,
# ``10kg-15kg``). In Sammler-Notizen und Fund-Etiketten die kompakte Schreibweise,
# wenn der Sammler die Einheit an beiden Bereichs-Grenzen wiederholt (statt der
# etablierten Trailing-Einheit-Form ``3-5 mm`` mit Einheit nur nach der oberen
# Grenze). Praxis-Beispiele: Kristall-Groessen-Ranges auf Etiketten aus Mineralien-
# Boersen ("Rauchquarz-Cluster, Einzelkristalle 3mm-5mm"), Gewichts-Ranges bei
# Sammlungs-Ueberblick ("Chalkopyrit-Stufen 10g-50g"), Groessen-Klassen in
# Auktions-Katalogen ("Amethyst-Druse 5cm-10cm").
#
# Bisher fielen alle Formen still auf den ersten Wert (``3mm-5mm`` -> ``(3.0,
# 3.0)``, ``1.5g-2.5g`` -> ``(1.5, 1.5)``, ``10kg-15kg`` -> ``(10.0, 10.0)``),
# weil die Sign-Blockierung ``(?<![A-Za-z^]-)`` in :data:`_NUM_RE` den ``m-``->
# ``2`` Uebergang als Sign-Bindung interpretiert und die obere Bereichs-Grenze
# unmatched laesst. Der ``\d+``-Fallback matcht dann nur den Ziffern-Rest hinter
# der ersten Ziffer der oberen Grenze (``20`` -> ``0``, ``15`` -> ``5``, ``2.5``
# -> ``.5``) - die Zahl-Menge wird ``[lo, teil-von-hi]`` und faellt via
# ``hi < lo``-Kollaps auf ``(lo, lo)``. Silenter Datenverlust auf der oberen
# Bereichs-Grenze, ohne dass der User einen Hinweis auf den Fehler bekommt.
#
# Transformation strippt die erste Einheit (``3mm-5mm`` -> ``3-5 mm``, ``1.5g-
# 2.5g`` -> ``1.5-2.5 g``), damit die generische Range-Zahl-Extraktion die
# beiden Werte findet. Semantisch aequivalent: die Trailing-Einheit-Form ist
# der etablierte Kanon in wissenschaftlichen Publikationen und in der
# bestehenden Test-Suite (``5-10 mm``, ``10-20 g``, ``5.5-10.5 mm``); die
# hier gestrippte Repetition ist reine Notations-Redundanz ohne semantische
# Differenz. Nach der Transformation greift die vorhandene Trailing-Einheit-
# Semantik unveraendert.
#
# Sicherheits-Guards:
# * Leading-Guard ``(?:^|(?<=[\s(\[{,;:]))`` verhindert False-Positives an
#   eingebetteten Positionen wie ``field-1abc-2abc`` (dort ist ``1abc-2abc``
#   von ``-`` und Buchstabe umgeben, nicht von Whitespace/Anfang/Klammer/
#   Komma/Semikolon/Colon) - der Match beginnt nur an einer strukturell
#   erwarteten Wert-Start-Position.
# * Trailing-Guard ``(?![A-Za-z0-9])`` nach dem zweiten Einheit-Token
#   verhindert, dass eine dritte laengere Einheit den Match teilt
#   (``3mm-5mm2`` waere kein Match; ``3mm-5mmol`` waere kein Match, weil
#   die tatsaechliche Einheit ``mmol`` ist und ``mm`` nur ein Teil davon).
# * Einheiten-Zeichenklasse ``[A-Za-zµ°]{1,4}`` beschraenkt die Einheit auf
#   1-4 Buchstaben (deckt praktisch alle SI-/Nicht-SI-Basis-Einheiten ab:
#   mm/cm/dm/m/km/nm/µm/g/kg/mg/µg/ng/l/ml/dl/cl/s/min/h/°C/°F/°K/pt/oz/lb/
#   in/ft/yd) und laesst zusammengesetzte Einheiten mit ``/``/``^``/``³``/
#   ``²`` (``g/cm³``, ``mol/l``, ``m/s``) unbetroffen - dort wuerde die
#   Trailing-Einheit-Form ``2.65 g/cm³ - 5.5 g/cm³`` schon vor dem Fix per
#   Whitespace-um-Bindestrich-Trenner korrekt in ``_NUM_RE`` fallen.
# * Kollisionsfrei zum ``%``/``‰``-Sign-Blocker aus dem Prozent-/Promille-
#   Range-Fix (``5%-10%``, ``0.5‰-2.5‰``): ``%`` und ``‰`` sind nicht in
#   der Einheiten-Zeichenklasse enthalten, der bestehende Zweig greift
#   unveraendert.
# * Kollisionsfrei zur wissenschaftlichen ``E``-Notation (``1e3-2e3``): der
#   Regex-Trailing-Guard ``\2`` verlangt exakte Einheit auf beiden Seiten;
#   die e-Notation-Ziffern hinter dem ersten ``e`` verhindern, dass eine
#   symmetrische Einheit gefunden wird (``1e3-2e3`` matcht nicht, weil
#   nach ``1`` als Zahl der Rest ``e3-2e3`` fuer die Einheit-Position ``e``
#   und dann ``\s*[-–—]\s*`` erwartet, aber ``3`` folgt).
_REPEATED_UNIT_RANGE = re.compile(
    r"(?:^|(?<=[\s(\[{,;:]))"
    r"(\d+(?:[.,]\d+)?)"
    r"\s*"
    r"([A-Za-zµ°]{1,4})"
    r"(\s*[-–—]\s*)"
    r"(\d+(?:[.,]\d+)?)"
    r"\s*"
    r"\2"
    r"(?![A-Za-z0-9])"
)


def _strip_repeated_unit(s: str) -> str:
    """Strippt die erste Einheit in ``<num><unit>-<num><unit>``-Notation.

    Transformation: ``3mm-5mm`` -> ``3-5 mm``, ``1.5g-2.5g`` -> ``1.5-2.5 g``,
    ``5cm-10cm`` -> ``5-10 cm``. Nur bei identischer Einheit auf beiden
    Seiten (per Backreference); mixed-unit-Formen (``3mm-5cm``) und Formen
    mit Einheit nur auf einer Seite (``3-5mm``, ``3mm-5``) bleiben
    unangetastet. Der Strip macht die Bereichs-Grenze fuer die
    generische ``_NUM_RE``-Zahl-Extraktion sichtbar, die sonst durch den
    Sign-Blocker ``(?<![A-Za-z^]-)`` an der zweiten Grenze scheitert.
    Siehe :data:`_REPEATED_UNIT_RANGE` fuer Details zu Guards und
    Kollisions-Schutz.
    """
    return _REPEATED_UNIT_RANGE.sub(r"\1\3\4 \2", s)


def _strip_locale_thousands(s: str) -> str:
    """Entfernt eindeutig erkennbare Tausender-Trenner aus EN/DE/FR-Excel-Exporten.

    Beruehrt nur Zahl-Token, deren Struktur unmissverstaendlich ist:
    ``1,000.50``/``1.000,50`` (gemischte Trenner ⇒ rechter ist Dezimal),
    ``1,000,000``/``1.000.000`` (≥2 gleichartige Trennergruppen ⇒ Tausender)
    sowie die SI-/FR-Whitespace-Form ``1 234,56``/``1\xa0234.56``/
    ``1 234 567`` (Leerzeichen, NBSP, schmales NBSP). Zusaetzlich die
    programmiersprachen-verbreitete Underscore-Ziffer-Gruppierungs-Form
    ``1_000``/``1_000_000``/``1_234.567`` (PEP 515, Java 7+, JS ES2021,
    Rust) - siehe :data:`_UNDERSCORE_DIGIT_GROUPING`. Mehrdeutige Faelle
    wie ``1,000`` / ``1.000`` / ``1 234`` (eine Trennergruppe) werden
    nicht angetastet, damit ``2,55`` weiterhin als Dezimal-2.55 gelesen wird.
    """
    s = _EN_THOUSANDS_WITH_DECIMAL.sub(lambda m: m.group(1).replace(",", ""), s)
    s = _DE_THOUSANDS_WITH_DECIMAL.sub(
        lambda m: m.group(1).replace(".", "").replace(",", "."), s)
    s = _EN_THOUSANDS_PURE.sub(lambda m: m.group(1).replace(",", ""), s)
    s = _DE_THOUSANDS_PURE.sub(lambda m: m.group(1).replace(".", ""), s)
    s = _SPACE_THOUSANDS_WITH_DECIMAL.sub(
        lambda m: _SPACE_THOUSAND_CHAR_RE.sub("", m.group(1)), s)
    s = _SPACE_THOUSANDS_PURE.sub(
        lambda m: _SPACE_THOUSAND_CHAR_RE.sub("", m.group(1)), s)
    s = _UNDERSCORE_DIGIT_GROUPING.sub(lambda m: m.group(1).replace("_", ""), s)
    return s


def normalize_numeric_locale(text: str) -> str:
    """Bereitet einen Freitext fuers Zahl-Token-Parsing vor.

    Spiegelt die Vorverarbeitung, die :func:`parse_range` intern macht, in
    eine eigene Funktion fuer andere Module mit lokaler Zahl-Extraktion
    (z.B. die KI-Antwort-Koerzitierung in :mod:`stonebook.ai.providers`).
    Strippt den Schweizer Apostroph-Tausender (``1'500.00`` → ``1500.00``)
    und die eindeutig erkennbaren EN/DE/FR-Tausender-Strukturen via
    :func:`_strip_locale_thousands`; mehrdeutige Einzel-Trenner
    (``1,000`` / ``1.000`` / ``1 234``) bleiben unangetastet, damit
    ``2,55`` weiterhin als Dezimal-2,55 lesbar bleibt.

    Das typografische Minus-Zeichen U+2212 (MINUS SIGN) wird auf den ASCII-
    Hyphen ``-`` normalisiert, damit die Sign-Bindung in :data:`_NUM_RE`
    (``(?<![\\d.%‰])-``) greift und negative Werte aus typeset-Quellen
    nicht stille auf ihren Absolut-Betrag kollabieren. Der ``_NUM_RE``-
    Kommentar dokumentiert die ASCII-only-Konvention der Sign-Alternante
    (typografische Minus-Varianten en-dash/em-dash/U+2212 bleiben Range-
    Separatoren, das Vorzeichen ist ASCII-only) und verweist explizit auf
    diese Vorverarbeitungs-Stufe als Ergaenzung fuer die U+2212-Vorzeichen-
    Rolle aus Print-/PDF-/LaTeX-Autoformat-Quellen. Bisher fielen alle
    U+2212-vorangestellten Werte silente auf den positiven Betrag:
    ``"−5.5"`` lieferte ``(5.5, 5.5)`` statt ``(-5.5, -5.5)``, ``"−5.5 ±
    0.3"`` fiel via ``$``-Anker-Miss auf die Fallback-Zahl-Suche und
    lieferte ``(5.5, 5.5)`` statt ``(-5.8, -5.2)`` (Vorzeichen UND
    publizierte Toleranz verloren), ``"−15.5 ± 0.5 ‰"`` (Isotopen-
    Fraktionierungs-Wert δ¹³C/δ¹⁸O typisch negativ mit Toleranz und
    Promille-Einheit) analog auf ``(15.5, 15.5)``. Bei der Migration aus
    Print-Katalogen (Word-/Office-Autoformat wandelt ``-`` beim Zahl-
    Kontext automatisch zu U+2212), PDF-/LaTeX-Publikationen (der
    kanonische mathematische Minus-Setz) und GPS-/Editor-Tools mit "smart
    punctuation" entstand damit silenter Vorzeichen-Datenverlust auf jeder
    Numeric-Achse mit Nullpunkt-negativen Werten (Kryo-Temperaturen,
    Isotopen-Delta-Notationen δ¹³C/δ¹⁸O in ‰, thermische Ausdehnungs-
    Koeffizienten β < 0, Meereshoehe-negative Fundort-Tiefen). Single-
    Pass-Strip vor allen weiteren Zahl-Patterns ist einfacher und sicherer
    als alle Zahl-/Uncertainty-Patterns parallel um U+2212-Alternation zu
    erweitern (Sign-Lookbehind, Center-Match, Trailing-Einheit-Alternate,
    Klammer-Kompakt-Notation) - U+2212 hat im Wert-Kontext keine andere
    Bedeutung als "negativ". Spiegelt den U+2212-Normalisierungs-Ansatz
    aus :func:`stonebook.migration.validators.parse_coordinates`.

    Kollisionsfreiheit zur Range-Separator-Rolle: U+2212 zwischen zwei
    Zahlen (``"5.5 − 7.5"`` / ``"5.5−7.5"``) blieb schon bisher ein
    Range-Trenner (U+2212 matcht nicht in ``_NUM_RE``, die Zahlen wurden
    getrennt gefunden). Nach der Normalisierung wird die U+2212-Sequenz
    zum ASCII-Hyphen ``-`` und faellt in die bereits vorhandene Range-
    Separator-Logik: der Sign-Lookbehind ``(?<![\\d.%‰])-`` blockiert die
    Sign-Bindung nach der ersten Digit (``5.5-7.5`` bleibt Range, das
    ``-`` nach ``5.5`` wird nicht als Vorzeichen an ``7.5`` gebunden) -
    die Range-Semantik bleibt unveraendert.

    Der Caller entscheidet selbst, ob er das Ergebnis als Range parst
    (``parse_range``) oder per ``_LEADING_NUMBER.search`` nur die erste
    Zahl extrahiert (Providers): die Kommazahl-zu-Punktzahl-Umsetzung
    macht jeder fuer sich, weil sie auf den jeweiligen Match-String
    geht und nicht auf den ganzen Freitext (sonst wuerden Tausenderpunkte
    in DE-Notation unbeabsichtigt zu Dezimalpunkten).
    """
    s = text.replace("'", "").replace("’", "").replace("−", "-")
    s = _normalize_explicit_mult_power10(s)
    return _strip_locale_thousands(s)


def parse_range(text) -> tuple[float | None, float | None]:
    """'6.5–7' → (6.5, 7.0); 'ca. 2.65' → (2.65, 2.65); '' → (None, None).

    Wissenschaftliche Unsicherheits-Notation wird als Bereich aufgeloest:
    ``'5.5 ± 0.3'`` → (5.2, 5.8) (Langform, siehe :data:`_PLUS_MINUS_UNCERTAINTY`);
    ``'5.5(3)'`` → (5.2, 5.8), ``'2.65(5)'`` → (2.60, 2.70), ``'100(2)'`` → (98, 102)
    (IUCr-Kompaktform, siehe :data:`_PARENTHESIS_UNCERTAINTY`).

    Ansonsten: wenn die letzte gefundene Zahl kleiner als die erste ist
    (z.B. Tippfehler ``'7-5'``), wird ein inverted Range vermieden: es
    zaehlt nur der erste Wert als (n, n).

    Schweizer Tausendertrenner ``'`` (z.B. ``1'500.00``) werden entfernt, damit
    Excel-/Buchhaltungsexporte mit CHF-Betraegen nicht in Einzelziffern zerfallen.
    Eindeutige EN/DE-Tausender (``1,000.50`` / ``1.000,50`` / ``1,000,000``) werden
    ebenfalls normalisiert; ambivalente Faelle wie ``2,55`` bleiben Dezimalwerte.

    Wissenschaftliche Notation ``E±N`` wird als Zehnerpotenz gelesen
    (``'1.5e-3'`` → (0.0015, 0.0015), ``'1e3'`` → (1000.0, 1000.0)); ohne
    Exponent-Auswertung wuerden Absorptions-/Kalibrier-Werte aus
    Publikationen auf ihre Mantisse kollabieren (siehe :data:`_NUM_RE`).

    Leading-Dot-Dezimals ohne fuehrende Null werden als Wert < 1 gelesen
    (``'.5'`` → (0.5, 0.5), ``'.5-.7'`` → (0.5, 0.7), ``'.5e-3'`` →
    (0.0005, 0.0005)) - US-Konvention und wissenschaftliche Publikationen
    ohne leading zero (siehe :data:`_NUM_RE`).

    Unicode-Vulgar-Fraktionen (¼/½/¾ und U+2150-U+215E) werden vor der
    Zahl-Extraktion in Dezimal-Aequivalente umgesetzt: Mixed-Form
    ``'5½'`` → (5.5, 5.5) (Mohs-Halbschritt der Referenz-Tabelle),
    Standalone ``'¼'`` → (0.25, 0.25), Range ``'5½-7'`` → (5.5, 7.0).
    Siehe :func:`_normalize_vulgar_fractions` fuer Details.

    Nicht-endliche Werte (Overflow der scientific-notation zu ``+inf`` /
    ``-inf`` sowie ``NaN`` aus arithmetischer Verkettung wie ``inf - inf``
    in Uncertainty-Zweigen) fallen auf ``(None, None)`` zurueck. Ein
    Token wie ``'1e400'`` wuerde sonst via ``float()`` transparent zu
    ``inf`` konvertiert und als vermeintlich gueltige Bereichsgrenze in
    Numeric-Felder wandern; ``inf`` in einem CHF-/Gewicht-/Dichte-Feld
    korrumpiert stille jede nachgelagerte SUM/AVG-Aggregation (Statistik-
    Report), verletzt die JSON-Spec (``json.dumps`` mit
    ``allow_nan=False`` verweigert ``inf``, der Standard-Export
    schreibt das nicht-standardkonforme Literal ``Infinity``) und
    verzerrt Vergleichs-/Sortier-Reihenfolgen ("groesste 10 Objekte"
    zeigt endlos den einen ueberlaufenen Wert). Semantisch ist ein
    Token, das float nicht darstellen kann, aequivalent zu "kein
    gueltiger Wert" - konsistent mit der bestehenden None-Rueckgabe fuer
    leere/nicht-parsbare Eingaben.
    """
    if text is None:
        return None, None
    s = normalize_numeric_locale(str(text))
    # Explizit-multiplikative Form der wissenschaftlichen Zehnerpotenz
    # (``5.5 × 10^-3``, ``5.5 · 10⁻³``, ``5.5 * 10^-3``, ``5.5 x 10^-3``)
    # auf die kompakte E-Notation ``5.5e-3`` abbilden, damit die publizierte
    # Groessenordnung von der bereits existierenden E-Notations-Semantik in
    # ``_NUM_RE`` transparent gelesen wird. Ohne diese Normalisierung wuerden
    # Print-Publikations-Werte als Range ``(5.5, 10.0)`` fehlgelesen (der
    # Basis-Radix ``10`` als vermeintliche Range-Grenze extrahiert) und die
    # eigentliche Groessenordnung ginge stille verloren. Siehe
    # :func:`_normalize_explicit_multiplication_exponent` fuer Details zu
    # Multiplikations-/Exponent-Signaturen und Kollisions-Schutz.
    s = _normalize_explicit_multiplication_exponent(s)
    # Unicode-Vulgar-Fraktionen (¼/½/¾ und U+2150-U+215E) vor allen weiteren
    # Zweigen normalisieren: die Fraktion ist ein Wert-Bestandteil, kein
    # Separator - Mixed-Form ``5½`` -> ``5.5``, Standalone ``½`` -> ``0.5``.
    # Vor den Uncertainty-Zweigen platziert, damit ``5½ ± 0.3`` als
    # ``5.5 ± 0.3`` in den ±-Zweig faellt und die publizierte Toleranz auf
    # den vollen Halbschritt-Wert (5.2, 5.8) auswertet (statt (5.2, 5.8)
    # mit fehlgelesenem Center 5.0 zu (4.7, 5.3)). Vor der Klammer-
    # Annotations-Strip platziert, damit ein Halbschritt-Wert vor der
    # Annotations-Klammer wie ``5½ (Ref)`` als ``5.5 (Ref)`` weiter geht
    # und der Klammer-Strip auf das Standard-Pattern greifen kann. Siehe
    # :func:`_normalize_vulgar_fractions` fuer Details zu Mixed-/Standalone-
    # Regex und den Kollisions-Schutz gegen SI-Einheiten-Position (``cm3½``
    # bleibt unangetastet, weil die 3 Teil der Einheit ist, nicht der Wert).
    s = _normalize_vulgar_fractions(s)
    # ASCII-Mixed-Fraktion ``\d+\s+\d+/\d+`` (Ganzzahl + Whitespace + Zaehler/
    # Nenner) auf Dezimal-Aequivalent abbilden: ``5 1/2`` -> ``5.5``, ``5 3/4``
    # -> ``5.75``, ``2 1/8`` -> ``2.125``. Spiegelt die Unicode-Vulgar-Fraktions-
    # Normalisierung auf die Plain-ASCII-Achse fuer typische Notation aus
    # Typewriter-/Terminal-Notizen, aus geerbten Textdatei-Sammlungen (RTF/TXT
    # ohne Autoformat-Konvertierung zu ½/¼) und aus handschriftlich
    # abgeschriebenen Mohs-Haerte-Werten. Nach _normalize_vulgar_fractions
    # einsortiert (Unicode-Formen zuerst - eindeutigere Semantik), vor den
    # Uncertainty-Zweigen einsortiert (damit ``5 1/2 ± 0.3`` als ``5.5 ± 0.3``
    # in den ±-Zweig faellt). Denominator-Whitelist und Proper-Fraktion-Check
    # schuetzen vor Datums-/Katalog-/Ratio-Fragmenten - siehe
    # :func:`_normalize_ascii_mixed_fractions` fuer Details.
    s = _normalize_ascii_mixed_fractions(s)
    # ASCII-Doppel-/Dreifach-Dot-Range-Separator (``3.5..5.5`` -> ``3.5-5.5``,
    # ``3.5...5.5`` -> ``3.5-5.5``) vor der Uncertainty- und der generischen
    # Zahl-Extraktions-Stufe normalisieren, damit die Fortran-/Ruby-/Publikations-
    # Range-Notation nicht stille auf den ersten Wert kollabiert. Reine Preprocessing-
    # Substitution, kollisionsfrei zu den Uncertainty-Zweigen (die nutzen ± bzw. (M)
    # als Toleranz-Signal, nicht ..). Siehe :data:`_DOTTED_RANGE_SEPARATOR`
    # fuer Details zu Motivation, Kollisionsanalyse und Guard-Semantik.
    s = _normalize_dotted_range_separator(s)
    # Annaeherungs-Praefix am String-Anfang strippen ("ca. 5.5 ± 0.3" ->
    # "5.5 ± 0.3", "~2.65(5)" -> "2.65(5)"). Siehe :data:`_APPROX_VALUE_PREFIX`
    # fuer Details: die Uncertainty-Patterns sind per ``^...$`` anker-gebunden
    # und wuerden sonst still auf die Fallback-Zahl-Extraktion durchfallen und
    # via ``[center, tol]``-inverted-Range-Kollaps ``(center, center)``
    # liefern (Toleranz verloren). Der Praefix modifiziert nur die
    # Praezisions-Angabe des Zentrums, nicht die Toleranz-Struktur - Strip
    # + Rekursion analog zum :func:`stonebook.migration.validators.parse_iso_date`-
    # Muster mit :data:`stonebook.migration.validators._APPROX_PREFIX`.
    if _APPROX_VALUE_PREFIX.match(s):
        rest = _APPROX_VALUE_PREFIX.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_range(rest)
    # Leading-Waehrungs-Prefix am String-Anfang strippen ("CHF 500 ± 50" ->
    # "500 ± 50", "$500 ± 50" -> "500 ± 50", "€5.5(3)" -> "5.5(3)"). Siehe
    # :data:`_LEADING_CURRENCY_PREFIX` fuer Details: die Uncertainty-Patterns
    # sind per ``^\s*(-?\d ...)``-Anker gebunden und wuerden sonst still
    # auf die Fallback-Zahl-Extraktion durchfallen und via ``[center, tol]``-
    # inverted-Range-Kollaps ``(center, center)`` liefern (Toleranz
    # verloren). Der Praefix ist rein syntaktische Waehrungs-Kennzeichnung
    # ohne Einfluss auf den numerischen Wert - Strip + Rekursion analog zur
    # :data:`_APPROX_VALUE_PREFIX`-Kette, sodass beide Reihenfolgen
    # ("ca. CHF 500 ± 50", "CHF ca. 500 ± 50") transparent aufloesen. Vor
    # dem Trailing-Suffix-Strip einsortiert, damit "CHF 500 ± 50, ca."
    # (Leading-Waehrung + Trailing-Approx-Marker + Uncertainty) via
    # zweifacher Rekursion die Toleranz behaelt.
    if _LEADING_CURRENCY_PREFIX.match(s):
        rest = _LEADING_CURRENCY_PREFIX.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_range(rest)
    # Trailing Annaeherungs-Suffix am String-Ende strippen ("5.5 ± 0.3, ca." ->
    # "5.5 ± 0.3", "2.65(5) circa" -> "2.65(5)", "500 CHF geschaetzt" -> "500 CHF").
    # Siehe :data:`_APPROX_VALUE_SUFFIX` fuer Details: die Uncertainty-Patterns
    # akzeptieren zwar Trailing-Tokens ohne Komma als Einheit-Alternative, aber
    # eine ``,`` bricht die Token-Kette und das End-Anker-Matching schlaegt fehl -
    # der Fallback via ``[center, tol]``-inverted-Range-Kollaps liefert ``(center,
    # center)`` (Toleranz verloren). Der Suffix modifiziert nur die Praezisions-
    # Angabe des Wert-Ausdrucks, nicht die Toleranz-Struktur - Strip + Rekursion
    # analog zum :data:`_APPROX_VALUE_PREFIX`-Muster. Nach dem Leading-Strip
    # einsortiert, damit "ca. 5.5 ± 0.3, ca." (beidseitige Marker-Kombination)
    # in einer Rekursion aufgeloest wird.
    suffix_stripped = _APPROX_VALUE_SUFFIX.sub("", s, count=1).strip()
    if suffix_stripped and suffix_stripped != s:
        return parse_range(suffix_stripped)
    # ASCII-Ersatzformen des Unicode-±-Praefix am String-Anfang strippen
    # ("+/-5.5" -> "5.5", "+-5.5" -> "5.5"). Siehe :data:`_LEADING_ASCII_PM_MARKER`
    # fuer Details: das Unicode-``±`` wird transparent via _NUM_RE-Skip als
    # Vorzeichen-blockierendes Non-Digit-Zeichen behandelt und liefert die
    # folgende Ziffer als positiven Center-Wert; die ASCII-Ersatzformen ``+/-``
    # und ``+-`` enden aber auf ``-`` und werden ohne Whitespace vor dem Wert
    # von der Sign-Alternante als Vorzeichen an die Zahl gebunden - Ergebnis
    # ist ein silenter negativer Center-Wert, wo semantisch ein positiver
    # gemeint war. Strip + Rekursion analog zur :data:`_APPROX_VALUE_PREFIX`-
    # Kette, sodass die Verkettung mit anderen Praefixen (``"ca. +/-5.5"``,
    # ``"CHF +/-500"``, ``"< +/-5.5"``) transparent aufloest und die
    # Uncertainty-Kombination ``"+/-5.5 ± 0.3"`` die publizierte Toleranz
    # behaelt.
    if _LEADING_ASCII_PM_MARKER.match(s):
        rest = _LEADING_ASCII_PM_MARKER.sub("", s, count=1).strip()
        if rest and rest != s:
            return parse_range(rest)
    # Einseitige Vergleichs-Grenze (``<``/``>``/``<=``/``>=``/``≤``/``≥``) am
    # String-Anfang: der Marker wird konsumiert, der Rest via parse_range
    # rekursiv geparst und das Ergebnis auf eine offene Bereichs-Grenze
    # abgebildet. ``<``/``<=``/``≤`` -> obere Grenze (lo=None, hi=Wert);
    # ``>``/``>=``/``≥`` -> untere Grenze (lo=Wert, hi=None). Der Wert wird
    # aus lo bzw. hi des rekursiven Ergebnisses gezogen (Kompatibilitaet mit
    # Uncertainty-/Bracket-/Einheiten-Zweigen: ``< 5.5 ± 0.3`` liefert nach
    # Rekursion (5.2, 5.8), und die Vergleichs-Interpretation nimmt die
    # obere Toleranz-Grenze als konservativen Obergrenzen-Wert). Nach
    # _APPROX_VALUE_PREFIX-Strip einsortiert, damit ``< ca. 5`` transparent
    # als "obere Grenze 5, ungefaehr" gelesen wird. Siehe :data:`_COMPARISON_PREFIX`
    # fuer Details zur Motivation, Marker-Menge und Kollisionsschutz.
    cmp_match = _COMPARISON_PREFIX.match(s)
    if cmp_match:
        rest = s[cmp_match.end():].strip()
        if rest:
            inner_lo, inner_hi = parse_range(rest)
            marker = cmp_match.group(1)
            if marker in ("<", "<=", "≤"):
                return None, inner_hi
            return inner_lo, None
    # Wort-basierte einseitige Vergleichs-Grenze am String-Anfang: die natur-
    # sprachige Kurzform der ``<``/``>``/``<=``/``>=``-Marker. ``mindestens 5``
    # / ``ab 5`` / ``at least 5`` -> untere Grenze (lo=5, hi=None);
    # ``hoechstens 5`` / ``bis 5`` / ``max. 5`` / ``at most 5`` / ``up to 5``
    # -> obere Grenze (lo=None, hi=5). Nach _COMPARISON_PREFIX einsortiert,
    # damit ``mindestens > 5`` die Wort-Form konsumiert und der Rest ``> 5``
    # transparent den Zeichen-Marker greift (redundante Notation, verlustfrei).
    # Siehe :data:`_COMPARISON_WORD_LOWER` / :data:`_COMPARISON_WORD_UPPER`
    # fuer Details zur Marker-Menge, Kollisions-Schutz und Punkt-Guard-
    # Konvention der abgekuerzten Formen.
    word_lo = _COMPARISON_WORD_LOWER.match(s)
    if word_lo:
        rest = s[word_lo.end():].strip()
        if rest:
            # Range-Starter-Wort-Dual-Use: ``from``/``ab`` sind in
            # natuerlicher Sprache doppel-genutzt - entweder als "at
            # least"-Ein-Seiten-Marker (``from 5`` / ``ab 500 CHF``)
            # oder als Range-Start-Wort in Kombination mit einem
            # folgenden Range-Separator (``from 5 to 7`` / ``ab 5 bis
            # 7`` / ``ab 5-7`` / ``from 500 to 700 CHF``). Bisher
            # kollabierten alle Range-Formen still auf die Ein-Seiten-
            # Interpretation (``from 5 to 7`` -> (5, None) statt der
            # publizierten Range (5, 7)) und die obere Bereichsgrenze
            # ging verloren; die neue Dual-Use-Auswertung erkennt einen
            # Range-Separator (:data:`_HAS_RANGE_TAIL`: Wort-Separator
            # ``to``/``bis`` oder Ziffern-Bindestrich) und leitet in
            # diesem Fall die Rekursion auf ``rest`` durch, sodass die
            # etablierte Range-Extraktion die publizierte Bereichs-
            # Zuordnung uebernimmt. Ohne Range-Separator bleibt die
            # etablierte "at least"-Semantik ohne Verhaltens-Aenderung
            # erhalten (``from 5`` -> (5, None), ``ab 500 CHF`` ->
            # (500, None)). Die Auswertung ist auf :data:`_RANGE_
            # STARTER_WORDS` beschraenkt und laesst alle uebrigen
            # Marker (mindestens/at least/ueber/mehr als/greater than/
            # over/above/oberhalb/wenigstens/zumindest/min./mind.)
            # bei ihrer strikten Ein-Seiten-Semantik.
            marker_lower = word_lo.group(0).strip().lower()
            if marker_lower in _RANGE_STARTER_WORDS and _HAS_RANGE_TAIL.search(rest):
                return parse_range(rest)
            inner_lo, _inner_hi = parse_range(rest)
            return inner_lo, None
    word_hi = _COMPARISON_WORD_UPPER.match(s)
    if word_hi:
        rest = s[word_hi.end():].strip()
        if rest:
            _inner_lo, inner_hi = parse_range(rest)
            return None, inner_hi
    # ``N ± M``-Notation vor der generischen Zahlen-Extraktion pruefen: die
    # Toleranz ist strukturell an das Zentrum gebunden, nicht ein zweiter
    # unabhaengiger Wert. Ohne diesen Zweig wuerde ``5.5 ± 0.3`` als
    # ``[5.5, 0.3]`` erkannt und via ``if hi < lo`` auf ``(5.5, 5.5)`` fallen -
    # die publizierte Toleranz ginge stille verloren.
    m = _PLUS_MINUS_UNCERTAINTY.match(s)
    if m:
        center = float(m.group(1).replace(",", "."))
        tol = float(m.group(2).replace(",", "."))
        return _finite_pair(center - tol, center + tol)
    # Kompakt-Unsicherheits-Notation ``N(M)`` (IUCr-Standard) vor der
    # generischen Zahlen-Extraktion pruefen: ohne diesen Zweig wuerde
    # ``5.5(3)`` als ``[5.5, 3.0]`` erkannt und via ``if hi < lo`` auf
    # ``(5.5, 5.5)`` fallen (Toleranz verloren), waehrend ``2.65(5)`` als
    # ``[2.65, 5.0]`` als semantisch falscher Range ``(2.65, 5.0)``
    # interpretiert wuerde. Die Toleranz ist strukturell an das Zentrum
    # gebunden (angewandt auf die letzten Ziffern), nicht ein zweiter
    # unabhaengiger Wert. Der Divisor 10**n_decimals bezieht die Klammer-
    # Zahl auf die Position der letzten signifikanten Stelle des Zentrums:
    # bei ``5.5(3)`` liegt die 3 auf der ersten Nachkommastelle -> 0.3;
    # bei ``100(2)`` liegt die 2 auf der letzten Ganzzahl-Stelle -> 2.
    m = _PARENTHESIS_UNCERTAINTY.match(s)
    if m:
        center_str = m.group(1).replace(",", ".")
        center = float(center_str)
        n_decimals = len(center_str.split(".", 1)[1]) if "." in center_str else 0
        tol = int(m.group(2)) / (10 ** n_decimals)
        return _finite_pair(center - tol, center + tol)
    # Klammer-Annotation vor der generischen Zahl-Extraktion strippen: Sammler-
    # Notizen setzen Foto-/Katalog-/Referenz-Marker (``(Nr. 42)``, ``(2020)``,
    # ``[verified]``, ``{geerbt}``) rein zusaetzlich zum Wert, oft mit einer
    # Zahl im Annotations-Inhalt. Ohne Strip wuerden Katalog-/Jahres-Nummern
    # als Range-Grenzen fehlgelesen (``"5.5 (2020)"`` -> (5.5, 2020.0) statt
    # (5.5, 5.5)). Siehe :func:`_strip_bracketed_annotations` fuer Details
    # zur Nest-Aufloesung und dem Rueckfall-Schutz bei Wert-in-Klammern.
    s = _strip_bracketed_annotations(s)
    # Repetierte Einheit ``<Wert><Einheit>-<Wert><Einheit>`` (``3mm-5mm``,
    # ``1.5g-2.5g``, ``5cm-10cm``) auf die etablierte Trailing-Einheit-Form
    # (``3-5 mm``, ``1.5-2.5 g``, ``5-10 cm``) reduzieren. Ohne diesen Strip
    # blockiert der Sign-Lookbehind ``(?<![A-Za-z^]-)`` in :data:`_NUM_RE`
    # die obere Bereichs-Grenze (``m-`` verhindert den ``2``-Match, ``\d+``
    # matcht nur den Ziffern-Rest ``0``) und der Range-Zahl-Extract kollabiert
    # via ``hi < lo``-Fallback auf ``(lo, lo)`` (obere Bereichs-Grenze verloren).
    # Nach _strip_bracketed_annotations, damit ``(3mm-5mm)`` (Wert-in-Klammern-
    # Ruecksetzung durch die Klammer-Strip-Logik) trotzdem als Range gelesen
    # wird. Siehe :func:`_strip_repeated_unit` fuer Details zu Guards und
    # Kollisions-Schutz.
    s = _strip_repeated_unit(s)
    # ASCII ``x``/``X`` zwischen zwei Ziffern als Dimensions-Separator auf
    # Leerzeichen normalisieren: ``5x10mm`` -> ``5 10mm``, ``2.5x3.0x4.0mm`` ->
    # ``2.5 3.0 4.0mm``. Spiegelt die Unicode-``×``-(U+00D7-)Range-Semantik
    # auf die ASCII-Achse und macht die haeufige Compact-Dimensions-Notation
    # aus Katalog-Software / Foto-Massband-Notizen als Range der Ausdehnungen
    # verfuegbar (min-Dimension als lo, max-Dimension als hi). Nach
    # _strip_repeated_unit einsortiert, weil der Unit-Strip strukturell
    # unabhaengig ist (matcht nur ``[-–—]``-Separator, nie ``x``/``X``) und
    # die Reihenfolge semantisch keine Rolle spielt. Siehe
    # :data:`_DIMENSION_X` fuer die Kollisions-Schutz-Details.
    s = _DIMENSION_X.sub(r"\1 ", s)
    # Nicht-endliche Tokens (``1e400`` -> ``inf`` via ``float()``-Overflow)
    # aus der Zahl-Menge vor der lo/hi-Auswahl filtern: sonst wuerde
    # ``'1e400'`` als ``(inf, inf)`` und ``'5.5 - 1e400'`` als ``(5.5, inf)``
    # in Numeric-Felder wandern und alle nachgelagerten Aggregationen /
    # Sortierungen / JSON-Exporte korrumpieren. Der Filter greift *nach* der
    # bracketed-annotation-Strip (damit ein overflow-Token in einer
    # Annotation - selten, aber theoretisch moeglich - dieselbe Behandlung
    # wie eine Katalog-Nummer erhaelt: raus aus der Wert-Menge). Fallback
    # auf ``(None, None)`` wenn *alle* Tokens ueberlaufen sind, spiegelt die
    # "keine Zahl gefunden"-Semantik von leerem Eingabe-Text.
    nums = [
        f for f in (float(n.replace(",", ".")) for n in _NUM_RE.findall(s))
        if math.isfinite(f)
    ]
    if not nums:
        return None, None
    lo, hi = nums[0], nums[-1]
    if hi < lo:
        return lo, lo
    return lo, hi


def _finite_pair(lo: float, hi: float) -> tuple[float | None, float | None]:
    """Gibt ``(lo, hi)`` nur zurueck, wenn beide Werte endlich sind, sonst ``(None, None)``.

    Schutzt die Uncertainty-Zweige (``_PLUS_MINUS_UNCERTAINTY``,
    ``_PARENTHESIS_UNCERTAINTY``) vor arithmetischer Overflow-/NaN-
    Verkettung: ``float("1e400") ± 0.1`` liefert ``(inf, inf)``, und
    ``float("1e400") ± float("1e400")`` liefert ``(nan, nan)`` (via
    ``inf - inf``) - beide Formen sind semantisch "kein gueltiger
    Wert" und werden konsistent zur restlichen Filter-Kette (siehe
    :func:`parse_range`) auf ``(None, None)`` gemappt.
    """
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return None, None
    return lo, hi


def _num(text) -> float | None:
    lo, _ = parse_range(text)
    return lo


def _int(text) -> int | None:
    v = _num(text)
    return int(v) if v is not None else None


def _join_notes(*parts) -> str:
    return "\n".join(p.strip() for p in parts if p and str(p).strip())


_COMMON_DELIMS = (",", ";", "\t", "|")
_ENCODING_FALLBACKS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
# UTF-16-Byte-Order-Marks: \xff\xfe = LE, \xfe\xff = BE. Excel speichert beim
# Export-Typ "Unicode Text (*.txt)" UTF-16-LE mit BOM und Tab-Separator; in
# einigen DE-/CH-Office-Installationen ist das der Default fuer "CSV mit
# Sonderzeichen". Ohne BOM-Erkennung fiele die Datei aktuell durch utf-8-sig/
# utf-8 (beide scheitern an \xff bzw. \xfe als ungueltigem Startbyte) auf
# cp1252 zurueck und wuerde dort als Doppel-Byte-Muell dekodiert (jeder ASCII-
# Buchstabe als ``X\x00``, dann auch der ID-Header zerfaellt). Die explizite
# BOM-Pruefung vor dem Fallback-Loop liefert sauberen Unicode-Text fuer beide
# UTF-16-Varianten; ohne BOM bleiben wir bei der bestehenden Heuristik (keine
# stille UTF-16-Annahme, weil reine ASCII-Daten als BOM-loses UTF-16-LE
# fast immer Unsinn waeren).
_UTF16_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe", "utf-16"),  # LE - Excel "Unicode Text" Default
    (b"\xfe\xff", "utf-16"),  # BE - selten, aber spec-konform
)


def _read_text_any_encoding(path: Path) -> str:
    """Liest Text mit UTF-8/BOM-bevorzugt; faellt auf cp1252/latin-1 zurueck.

    Excel-Exporte aus aelteren Windows-Versionen sind oft cp1252-kodiert.
    Latin-1 als letzter Schritt ist verlustfrei fuer Single-Byte-Streams.
    UTF-16-mit-BOM (Excel "Unicode Text"-Export) wird via BOM-Pruefung erkannt,
    damit ``\\xff\\xfe...``-Bytes nicht durch cp1252 als Doppelbyte-Muell
    dekodiert werden.
    """
    raw = path.read_bytes()
    for bom, enc in _UTF16_BOMS:
        if raw.startswith(bom):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                break
    for enc in _ENCODING_FALLBACKS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _strip_quoted_spans(line: str) -> str:
    """Entfernt Inhalt von RFC-4180-quoted Feldern aus der Zeile.

    Zaehl-Grundlage fuer die Delimiter-Erkennung: nur Zeichen ausserhalb
    ``"``-quoted Spans zaehlen, weil eingebettete Delimiter innerhalb eines
    Feldnamens (``"Feld mit, Komma"``) semantisch nicht als Trenner wirken.
    Verdoppelte Anfuehrungszeichen (``""``) sind der RFC-4180-Escape fuer ein
    literales ``"`` und werden als Innen-Zeichen ueberschritten. Zeilen mit
    unbalancierten Anfuehrungszeichen fallen auf den Original-String zurueck.

    Nur fuer die Erst-Zeilen-Heuristik gedacht - der eigentliche CSV-Reader
    (``csv.DictReader``) macht seine eigene, vollstaendige Quoting-Auswertung.
    """
    out: list[str] = []
    in_quote = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            if in_quote and i + 1 < len(line) and line[i + 1] == '"':
                # Escape-Sequenz "" innerhalb eines quoted Feldes: verbleibt
                # innen, ueberspringt beide Zeichen.
                i += 2
                continue
            in_quote = not in_quote
        elif not in_quote:
            out.append(ch)
        i += 1
    if in_quote:
        # Unbalanciertes Anfuehrungszeichen: konservativ auf Original zurueckfallen,
        # damit ein einzelnes ``"`` in einem exotischen Header nicht die halbe
        # Zeile ausblendet.
        return line
    return "".join(out)


def _detect_delimiter(header_line: str) -> str:
    """Wählt das Trennzeichen mit den meisten Treffern in der Headerzeile.

    Zeichen innerhalb RFC-4180-quoted Feldnamen (``"Feld mit, Komma"``) werden
    per :func:`_strip_quoted_spans` ausgeblendet, damit ein Semikolon-CSV mit
    komma-haltigen Header-Feldnamen nicht faelschlich als Komma-CSV erkannt
    wird (Excel-DE-Export typisch: Semikolon-Delimiter, aber mehrere Kommas
    im quoted Feldnamen wie ``"Wert, geschaetzt"`` wuerden bei nackter Count-
    Heuristik den echten ``;``-Trenner ueberstimmen und die ganze Zeile zu
    einer einzigen Zelle zerfallen lassen).

    Fällt auf Komma zurück, wenn keines der gängigen Zeichen vorkommt.
    """
    unquoted = _strip_quoted_spans(header_line)
    best, best_n = ",", 0
    for d in _COMMON_DELIMS:
        n = unquoted.count(d)
        if n > best_n:
            best, best_n = d, n
    return best


def _read_csv_robust(path: Path) -> list[dict]:
    """Toleranter CSV-Reader für nutzer-editierte/externe Quellen.

    Erkennt Delimiter (``,`` / ``;`` / Tab / ``|``), strippt Whitespace aus den
    Spaltennamen und überspringt komplett leere Zeilen. Für die historischen
    Repo-CSVs nicht nötig; gedacht für ``load_standard``.

    Multi-Line-Zellen (eingebettete Newlines in quoted Felder wie ``notizen``)
    bleiben erhalten: der Reader bekommt einen ``StringIO``-Stream (nicht eine
    ``splitlines``-Liste), damit ``csv.DictReader`` seine eigene Zeilenlogik
    anwenden kann. Sonst wuerde ein langes Notiz-Feld mit ``\\n`` in nutzlose
    Halbzeilen zerfallen.
    """
    text = _read_text_any_encoding(path)
    if not text.strip():
        return []
    # Erste nicht-leere Zeile als Header fuer die Delimiter-Erkennung. Hier ist
    # splitlines unschaedlich, weil der Header nie quoted Newlines enthaelt.
    header_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    delim = _detect_delimiter(header_line)
    # StringIO statt splitlines(): erhaelt Multi-Line-Zellen wie "Zeile1\nZeile2"
    # in quoted Spalten. csv.DictReader nutzt seine eigene Newline-Erkennung,
    # die quoted Newlines beruecksichtigt.
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if reader.fieldnames:
        reader.fieldnames = [(h or "").strip() for h in reader.fieldnames]
    rows: list[dict] = []
    for row in reader:
        # Leere Zeilen / "alle Zellen leer" überspringen
        if not any((v or "").strip() for v in row.values() if v is not None):
            continue
        rows.append(row)
    return rows


def load_v1(path: Path) -> dict[str, dict]:
    """21 Spalten, Objekte 1-42."""
    result = {}
    for row in _read_csv_robust(path):
        obj_id = normalize_id(row.get("ID"))
        if not obj_id:
            continue
        h_min, h_max = parse_range(row.get("Härte"))
        d_min, d_max = parse_range(row.get("Dichte"))
        result[obj_id] = {
            "Name": row.get("Name", "").strip(),
            "Mineral_Primaer": row.get("Mineralart", "").strip(),
            "Fundort": row.get("Fundort", "").strip(),
            "UV_365nm": row.get("UV-Reaktion", "").strip(),
            "Mohs_Haerte_min": h_min, "Mohs_Haerte_max": h_max,
            "Dichte_min_gcm3": d_min, "Dichte_max_gcm3": d_max,
            "Transparenz": row.get("Transparenz", "").strip(),
            "Farbe_beobachtet": row.get("Farbe", "").strip(),
            "Wert_CHF_roh": _num(row.get("Wert_CHF_roh")),
            "Wert_CHF_poliert": _num(row.get("Wert_CHF_poliert")),
            "Wert_CHF_Schmuck": _num(row.get("Wert_CHF_Schmuck")),
            "Wert_USD_Talisman": _num(row.get("Wert_USD_Talisman")),
            "Marktwert_Industrie": _num(row.get("Marktwert")),
            "Wissenschaftlicher_Wert_CHF": _num(row.get("Wissenschaftlicher_Wert")),
            "Seltenheit_global_1_10": _int(row.get("Seltenheit_global")),
            "Seltenheit_Fundort_1_10": _int(row.get("Seltenheit_Fundort")),
            "Nachfrage_1_10": _int(row.get("Nachfrage")),
            "Beste_Verwendung": row.get("Beste_Verwendung", "").strip(),
            "notizen": _join_notes(row.get("Beschreibung"), row.get("Inhaltsstoffe")),
        }
    return result


_STANDARD_COLS = frozenset(f.name for f in DATA_FIELDS)


def _convert_standard(col: str, raw) -> tuple[bool, object]:
    """Konvertiert eine Rohzelle gemaess Feldwörterbuch-Typ.

    Gibt (übernehmen?, wert) zurück; übernehmen=False für ungueltige Datumsangaben.
    """
    fdef = FIELD_BY_NAME[col]
    if fdef.ftype in NUMERIC_TYPES:
        return True, _int(raw) if fdef.ftype in ("int", "scale") else _num(raw)
    if fdef.ftype == "date":
        iso = parse_iso_date(raw)
        return (iso is not None), iso
    return True, str(raw).strip()


def load_v2(path: Path) -> dict[str, dict]:
    """41 Spalten ≈ Feldwörterbuch-Standard, 1:1-Übernahme mit Typkonvertierung."""
    result = {}
    for row in _read_csv_robust(path):
        obj_id = normalize_id(row.get("ID"))
        if not obj_id:
            continue
        fields: dict = {}
        for col, raw in row.items():
            if col not in _STANDARD_COLS or raw is None:
                continue
            take, val = _convert_standard(col, raw)
            if take:
                fields[col] = val
        result[obj_id] = fields
    return result


_ID_COLUMNS = ("ID", "obj_id")


def find_duplicate_ids(path: Path) -> list[str]:
    """Findet obj_ids, die in derselben Standard-CSV mehrfach als Zeile vorkommen.

    :func:`load_standard` (und damit :func:`stonebook.export.csv_export.import_csv`)
    baut das Ergebnis als ``dict[str, dict]`` auf, sodass eine zweite Zeile mit
    derselben ID die erste kommentarlos ueberschreibt - typischer Datenverlust-
    Fall bei nutzer-editierten CSVs, wo dieselbe ID doppelt eingetragen wurde
    (z.B. beim Merge mehrerer Auszuege in Excel) und die spaetere Zeile alle
    Werte der frueheren Zeile verdraengt, obwohl beide Zeilen nur teilweise
    gefuellt sind. Diese Funktion pre-scannt die Datei und liefert die Liste
    der doppelten IDs zurueck, ohne die Loesch-Semantik selbst zu aendern.

    Normalisiert IDs ueber :func:`normalize_id` (spiegelt :func:`load_standard`),
    sodass ``obj_1`` und ``OBJ_0001`` als dieselbe ID erkannt werden. Leere/
    ungueltige IDs (die von :func:`load_standard` sowieso uebersprungen werden)
    zaehlen hier nicht als Duplikat. Reihenfolge der Rueckgabe = Reihenfolge
    der zweiten Vorkommen im File (deterministisch fuer Reporter/Log-Ausgabe).
    Rueckgabe enthaelt jede ID hoechstens einmal, unabhaengig davon, wie oft
    sie ueber die erste hinaus vorkommt.

    Akzeptiert dieselben ID-Spalten wie :func:`load_standard` (``ID`` oder
    ``obj_id``). Wirft ``ValueError`` (analog :func:`load_standard`), wenn
    die CSV Zeilen enthaelt, aber weder ``ID`` noch ``obj_id`` als Header.
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    seen: set[str] = set()
    duplikate: list[str] = []
    duplikat_set: set[str] = set()
    for row in rows:
        obj_id = normalize_id(row.get("ID") or row.get("obj_id"))
        if not obj_id:
            continue
        if obj_id in seen:
            if obj_id not in duplikat_set:
                duplikate.append(obj_id)
                duplikat_set.add(obj_id)
        else:
            seen.add(obj_id)
    return duplikate


def find_rows_without_id(path: Path) -> list[int]:
    """Findet Zeilennummern (1-basiert ueber die Datenzeilen), in denen die ID-Spalte
    leer ist oder :func:`normalize_id` sie nicht auf eine gueltige obj_id abbilden kann.

    :func:`load_standard` (und damit :func:`stonebook.export.csv_export.import_csv`)
    verwirft solche Zeilen kommentarlos - ein user-editierter Tippfehler in der
    ID-Zelle (leer, ``??`` oder ``TODO``) laesst die Zeile silent verschwinden,
    obwohl die uebrigen Spalten voll gepflegt sein koennen. Symmetrisches
    Blindfleck-Pendant zu :func:`find_duplicate_ids` (Doppel-Zeile-Silent-
    Ueberschreibung): beide melden zeilen-basierte silent data loss, ohne die
    Semantik von :func:`load_standard` selbst zu aendern.

    Reihenfolge = Reihenfolge im File. Vollstaendig leere Zeilen zaehlen nicht
    (die filtert bereits :func:`_read_csv_robust`); gemeldet werden nur Zeilen
    mit Inhalt, aber ohne verwertbare ID. Wirft ``ValueError`` analog zu
    :func:`find_duplicate_ids` / :func:`load_standard`, wenn die CSV Zeilen
    enthaelt, aber weder ``ID`` noch ``obj_id`` als Header hat.
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    ohne_id: list[int] = []
    for idx, row in enumerate(rows, start=1):
        obj_id = normalize_id(row.get("ID") or row.get("obj_id"))
        if not obj_id:
            ohne_id.append(idx)
    return ohne_id


def _find_rows_with_unparsable_value(
    path: Path, column: str, parser
) -> list[tuple[int, str]]:
    """Interner Helper fuer Feld-Level-Silent-Drop-Erkennung.

    Iteriert die Datenzeilen der CSV, ueberspringt leere Werte und die
    :data:`DATE_NO_DATA_MARKERS`, und liefert ``(Zeilennummer, Roh-Wert)``
    fuer jede Zelle in ``column``, in der ``parser(stripped)`` None
    zurueckgibt - der Feld-Level-Silent-Drop-Fund. Wird von
    :func:`find_rows_with_invalid_funddatum` (Parser
    :func:`parse_iso_date`) und :func:`find_rows_with_invalid_numeric_field`
    (Parser :func:`_num`) geteilt, damit beide dieselbe Marker-Semantik,
    Zeilennummerierung und ID-Spalten-Validierung nutzen und die
    Blindfleck-Regel "keine Meldung fuer 'no data'-Marker" nicht in zwei
    parallelen Implementierungen driften kann. Erwartet, dass der Caller
    ``column`` bereits validiert hat (spezifische Fehlermeldung je Achse:
    numerische vs. Datum-Achse haben unterschiedliche Erwartungswerte).
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    invalid: list[tuple[int, str]] = []
    for idx, row in enumerate(rows, start=1):
        raw = row.get(column)
        if raw is None:
            continue
        stripped = str(raw).strip()
        if not stripped or stripped.lower() in DATE_NO_DATA_MARKERS:
            continue
        if parser(stripped) is None:
            invalid.append((idx, stripped))
    return invalid


def find_rows_with_invalid_funddatum(path: Path) -> list[tuple[int, str]]:
    """Findet Zeilen mit einem nicht-leeren Funddatum-Wert, der nicht als
    ISO-Datum geparst werden konnte (silent drop in :func:`load_standard`).

    :func:`_convert_standard` uebernimmt Funddatum nur, wenn
    :func:`parse_iso_date` den Wert erfolgreich in YYYY-MM-DD normalisieren
    kann - andernfalls wird das Feld kommentarlos verworfen (der Rest der
    Zeile bleibt erhalten, die Funddatum-Spalte fehlt im Objekt-Dict). Ein
    typischer Datenverlust-Fall bei nutzer-editierten CSVs, wenn der User
    einen Tippfehler eingibt (``32.13.2024``) oder ein vom Parser nicht
    unterstuetztes Freitext-Format ("Sommer 84" ohne Jahres-Vollzahl,
    "letzten Herbst"). Symmetrisches Blindfleck-Pendant zu
    :func:`find_duplicate_ids` und :func:`find_rows_without_id`: alle drei
    melden zeilen-basierte silent data loss, ohne die Semantik von
    :func:`load_standard` selbst zu aendern.

    Rueckgabe: Liste von ``(Zeilennummer, Roh-Wert)``, 1-basiert ueber die
    Datenzeilen (Header zaehlt nicht, komplett leere Zeilen zaehlen nicht -
    die filtert bereits :func:`_read_csv_robust`). Der Roh-Wert ist der
    gestrippte Zellen-Inhalt, sodass CLI-Reporter und Logs die konkret
    kaputte Eingabe direkt anzeigen koennen ("Zeile 5: 'Sommer 84' konnte
    nicht geparst werden"). Reihenfolge = Reihenfolge im File.

    Explizite "keine Angabe"-Marker (``k.a.``, ``n/a``, ``unbekannt``, ``?``
    etc., siehe :data:`stonebook.migration.validators.DATE_NO_DATA_MARKERS`)
    zaehlen nicht als "invalid" - der User hat explizit gesagt "kein Datum
    verfuegbar", da ist nichts verloren gegangen. Fehlt die Funddatum-Spalte
    komplett im File, wird ``[]`` zurueckgegeben (kein Datenverlust moeglich).
    Whitespace-only-Werte zaehlen ebenfalls als leer und nicht als invalid.

    Wirft ``ValueError`` analog zu :func:`find_duplicate_ids` /
    :func:`find_rows_without_id` / :func:`load_standard`, wenn die CSV Zeilen
    enthaelt, aber weder ``ID`` noch ``obj_id`` als Header - so faellt eine
    falsch zugeordnete Datei (v1/v2-CSV) nicht stillschweigend leer durch.
    """
    return _find_rows_with_unparsable_value(path, "Funddatum", parse_iso_date)


_NUMERIC_STANDARD_COLS = frozenset(
    f.name for f in DATA_FIELDS if f.ftype in NUMERIC_TYPES
)


def find_rows_with_invalid_numeric_field(
    path: Path, column: str,
) -> list[tuple[int, str]]:
    """Findet Zeilen mit einem nicht-leeren Wert in einem numerischen
    Standardfeld, den :func:`_num` nicht als Zahl parsen konnte (silent
    drop in :func:`load_standard`).

    Feld-Level-Silent-Drop-Pendant zu :func:`find_rows_with_invalid_funddatum`
    auf der numerischen Achse. Waehrend die Datum-Variante Tippfehler in
    ``Funddatum`` (``32.13.2024``, ``Sommer 84``) erkennt, deckt diese
    Variante Tippfehler in numerischen Feldern (``Gewicht_g``, ``Wert_CHF_roh``,
    ``Mohs_Haerte_min``, ``Confidence_Prozent``, ...) ab: ein User-Freitext
    wie ``sehr schwer`` in der Gewicht_g-Spalte laesst :func:`_num` auf
    None fallen, ``_convert_standard`` uebergibt ``(True, None)``, in
    :func:`stonebook.export.csv_export.import_csv` filtert ``is_empty(None)``
    das Feld aus dem Update-Dict - die Zeile bleibt erhalten, aber der
    Roh-Text ist verloren, ohne dass der Report ihn sichtbar macht.

    Rueckgabe: Liste von ``(Zeilennummer, Roh-Wert)``, 1-basiert ueber die
    Datenzeilen. Der Roh-Wert ist der gestrippte Zellen-Inhalt, sodass
    CLI-Reporter die kaputte Eingabe direkt anzeigen koennen
    ("Zeile 5: 'sehr schwer' im Feld Gewicht_g konnte nicht geparst werden").
    Reihenfolge = Reihenfolge im File.

    ``column`` muss ein numerisches Standardfeld sein (``float`` / ``int`` /
    ``scale``, siehe :data:`stonebook.fields.NUMERIC_TYPES`); andere Felder
    (``str`` / ``text`` / ``enum`` / ``date`` / ``path``) werfen
    ``ValueError``, damit ein Aufruf mit ``"Funddatum"`` oder ``"Fundort"``
    nicht stillschweigend "0 Funde" liefert (fuer ``date`` gibt es
    :func:`find_rows_with_invalid_funddatum`; fuer Text-Felder gilt jeder
    nicht-leere Wert als gueltig, dort gibt es keinen Silent-Drop).

    Explizite "keine Angabe"-Marker (``k.a.``, ``n/a``, ``unbekannt``, ``?``,
    ``-``, ``—``, siehe :data:`stonebook.migration.validators.DATE_NO_DATA_MARKERS`)
    zaehlen NICHT als "invalid" - der User hat explizit gesagt "kein Wert
    verfuegbar", da ist nichts verloren gegangen. Die Marker-Menge wird mit
    :func:`find_rows_with_invalid_funddatum` geteilt (single source of truth
    fuer "was ist ein leerer Marker?" ueber alle Feld-Achsen). Whitespace-
    only-Werte zaehlen ebenfalls als leer und nicht als invalid.

    Fehlt die genannte Spalte komplett im File, wird ``[]`` zurueckgegeben
    (kein Datenverlust moeglich, spiegelt
    :func:`find_rows_with_invalid_funddatum`). Wirft ``ValueError`` analog,
    wenn die CSV Zeilen enthaelt, aber weder ``ID`` noch ``obj_id`` als
    Header - so faellt eine falsch zugeordnete Datei sichtbar durch.

    Werte, die eine Einheit enthalten (``42 g``, ``ca. 500 CHF``), gelten
    NICHT als invalid - :func:`_num` extrahiert das Zahl-Token via
    :func:`parse_range` und ``_convert_standard`` uebernimmt den Wert. Die
    Einheiten-Annotation geht dabei verloren, ist aber semantisch redundant
    (die Spalte kodiert die Einheit im Namen: ``Gewicht_g`` ist immer g,
    ``Wert_CHF_roh`` ist immer CHF). Erst wenn kein Zahl-Token gefunden wird
    (``sehr schwer``, ``teuer``, ``fast nichts``), ist der Wert-Anteil
    verloren und die Zeile wird gemeldet.
    """
    if column not in _NUMERIC_STANDARD_COLS:
        raise ValueError(
            f"Kein numerisches Standard-Feld: {column!r} "
            f"(erwartet: eines von {sorted(_NUMERIC_STANDARD_COLS)!r})")
    return _find_rows_with_unparsable_value(path, column, _num)


def find_rows_with_invalid_numeric_fields(
    path: Path,
) -> list[tuple[int, str, str]]:
    """Bulk-Scanner ueber ALLE im File vorhandenen numerischen Standardfelder.

    Buendelt :func:`find_rows_with_invalid_numeric_field` (pro Spalte) auf
    die gesamte numerische Achse, damit :func:`stonebook.export.csv_export.import_csv`
    ohne Kenntnis der konkreten Spaltenliste eine Gesamt-Silent-Drop-Bilanz
    fuer :class:`~stonebook.export.csv_export.ImportReport` liefern kann.
    Spiegelt :func:`find_rows_with_invalid_funddatum` (fixe Spalte, zeilen-
    orientiertes Ergebnis) auf die Achse "beliebig viele numerische Spalten"
    und schliesst damit die Symmetrie-Luecke im Silent-Drop-Report: Datum
    ist bereits im Report wired, Numerik bisher nur per Einzel-Aufruf.

    Rueckgabe: Liste von ``(Zeilennummer, Spaltenname, Roh-Wert)``. Sortier-
    ordnung ist Zeile-primaer, Spalte-sekundaer in der Header-Reihenfolge des
    Files - so bleibt die Reihenfolge deterministisch und ein CLI-Reporter
    kann pro Zeile alle Silent-Drops zusammenhaengend anzeigen. Eine Zeile
    kann mehrere Eintraege beitragen, wenn mehrere numerische Zellen
    unparsbar sind (z.B. ``sehr schwer`` in ``Gewicht_g`` UND ``teuer`` in
    ``Wert_CHF_roh`` in derselben Zeile - beide Silent-Drops werden separat
    gemeldet, damit der Roh-Wert-Kontext pro Feld erhalten bleibt).

    Nicht-numerische Spalten werden ignoriert (kein Silent-Drop moeglich:
    ``str``/``text``/``enum``/``path`` akzeptieren jeden Freitext,
    ``date`` hat :func:`find_rows_with_invalid_funddatum` als spezialisierten
    Pfad). Explizite "keine Angabe"-Marker (``k.a.``, ``n/a``, ``unbekannt``,
    ``?``, ``-``, ``—``, siehe
    :data:`stonebook.migration.validators.DATE_NO_DATA_MARKERS`) zaehlen NICHT
    als invalid - single source of truth mit
    :func:`find_rows_with_invalid_funddatum`/:func:`find_rows_with_invalid_numeric_field`.
    Whitespace-only-Werte zaehlen als leer und nicht als invalid.

    Fehlen numerische Spalten komplett im File, wird ``[]`` zurueckgegeben.
    Wirft ``ValueError`` wenn die CSV Zeilen enthaelt, aber weder ``ID`` noch
    ``obj_id`` als Header - konsistent mit
    :func:`find_duplicate_ids`/:func:`find_rows_without_id`/
    :func:`find_rows_with_invalid_funddatum`/:func:`find_rows_with_invalid_numeric_field`.
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    if not rows:
        return []
    numeric_cols = [c for c in rows[0].keys() if c in _NUMERIC_STANDARD_COLS]
    if not numeric_cols:
        return []
    invalid: list[tuple[int, str, str]] = []
    for idx, row in enumerate(rows, start=1):
        for col in numeric_cols:
            raw = row.get(col)
            if raw is None:
                continue
            stripped = str(raw).strip()
            if not stripped or stripped.lower() in DATE_NO_DATA_MARKERS:
                continue
            if _num(stripped) is None:
                invalid.append((idx, col, stripped))
    return invalid


def load_standard(path: Path) -> dict[str, dict]:
    """Liest eine CSV im aktuellen Export-Schema (ID + 43 Standardfelder + status + notizen).

    Gegenstück zu :func:`stonebook.export.csv_export.export_csv` und für externes
    Re-Import gedacht. Im Gegensatz zu load_v2 werden auch ``status`` und
    ``notizen`` übernommen, sofern in der Quelle vorhanden. Als ID-Spalte werden
    sowohl ``ID`` (CSV-Standard) als auch ``obj_id`` (DB-/JSON-Format)
    akzeptiert, damit JSON-Exporte ohne Spaltenumbenennung re-importierbar sind.

    Wirft ``ValueError`` wenn die CSV Zeilen enthaelt, aber weder eine Spalte
    ``ID`` noch ``obj_id`` -- so faellt eine falsch zugeordnete Datei (z.B.
    ``load_standard`` auf einer v1/v2-CSV mit Header ``Name,Mineralart,...``)
    nicht stillschweigend leer durch.
    """
    rows = _read_csv_robust(path)
    if rows and not any(c in rows[0] for c in _ID_COLUMNS):
        raise ValueError(
            f"CSV ohne ID-Spalte ({' oder '.join(_ID_COLUMNS)}): {path}")
    result = {}
    extra_cols = {"status", "notizen"}
    for row in rows:
        obj_id = normalize_id(row.get("ID") or row.get("obj_id"))
        if not obj_id:
            continue
        fields: dict = {}
        for col, raw in row.items():
            if raw is None:
                continue
            if col in _STANDARD_COLS:
                take, val = _convert_standard(col, raw)
                if take:
                    fields[col] = val
            elif col in extra_cols:
                fields[col] = str(raw).strip()
        result[obj_id] = fields
    return result


def load_obj043(path: Path) -> dict[str, dict]:
    """10-Spalten-Einzelobjektformat (voll verifiziert, höchste Priorität)."""
    result = {}
    for row in _read_csv_robust(path):
        obj_id = normalize_id(row.get("ID"))
        if not obj_id:
            continue
        h_min, h_max = parse_range(row.get("Härte"))
        d_min, d_max = parse_range(row.get("Dichte"))
        result[obj_id] = {
            "Fundort": row.get("Fundort", "").strip(),
            "Mineral_Primaer": row.get("Mineralart", "").strip(),
            "Farbe_beobachtet": row.get("Farbe", "").strip(),
            "Mohs_Haerte_min": h_min, "Mohs_Haerte_max": h_max,
            "Dichte_min_gcm3": d_min, "Dichte_max_gcm3": d_max,
            "UV_365nm": row.get("UV-Reaktion", "").strip(),
            "Gewicht_g": _num(row.get("Gewicht (g)")),
            "notizen": _join_notes(row.get("Struktur"), row.get("Besonderheiten")),
        }
    return result
