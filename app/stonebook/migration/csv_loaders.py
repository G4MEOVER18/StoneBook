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
# (das Sign-Match ist ASCII-only) - fuer die spezifische Minus-Zeichen-
# Vorzeichen-Rolle (U+2212 aus Print-Katalogen) waere eine eigene Norma-
# lisierung noetig (spiegelt den ``parse_coordinates``-Preprocess-Ansatz),
# ist hier aber ausserhalb des ASCII-Fallback-Umfangs.
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
_NUM_RE = re.compile(
    r"(?<![A-Za-z^])"
    r"("
    r"(?:(?<![\d.%‰])-)?"
    r"(?:\.\d+(?:[eE][+-]?\d+)?|\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)"
    r")"
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


def _strip_locale_thousands(s: str) -> str:
    """Entfernt eindeutig erkennbare Tausender-Trenner aus EN/DE/FR-Excel-Exporten.

    Beruehrt nur Zahl-Token, deren Struktur unmissverstaendlich ist:
    ``1,000.50``/``1.000,50`` (gemischte Trenner ⇒ rechter ist Dezimal),
    ``1,000,000``/``1.000.000`` (≥2 gleichartige Trennergruppen ⇒ Tausender)
    sowie die SI-/FR-Whitespace-Form ``1 234,56``/``1\xa0234.56``/
    ``1 234 567`` (Leerzeichen, NBSP, schmales NBSP). Mehrdeutige Faelle
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

    Der Caller entscheidet selbst, ob er das Ergebnis als Range parst
    (``parse_range``) oder per ``_LEADING_NUMBER.search`` nur die erste
    Zahl extrahiert (Providers): die Kommazahl-zu-Punktzahl-Umsetzung
    macht jeder fuer sich, weil sie auf den jeweiligen Match-String
    geht und nicht auf den ganzen Freitext (sonst wuerden Tausenderpunkte
    in DE-Notation unbeabsichtigt zu Dezimalpunkten).
    """
    s = text.replace("'", "").replace("’", "")
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


def _detect_delimiter(header_line: str) -> str:
    """Wählt das Trennzeichen mit den meisten Treffern in der Headerzeile.

    Fällt auf Komma zurück, wenn keines der gängigen Zeichen vorkommt.
    """
    best, best_n = ",", 0
    for d in _COMMON_DELIMS:
        n = header_line.count(d)
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
