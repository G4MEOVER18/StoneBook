from pathlib import Path

import pytest

from stonebook.fields import is_empty
from stonebook.migration import csv_loaders
from stonebook.migration.id_utils import normalize_id, display_name

REPO = Path(__file__).resolve().parents[2]
CSV_DIR = REPO / "data" / "csv"


def test_is_empty():
    assert is_empty(None)
    assert is_empty("")
    assert is_empty("   ")
    assert not is_empty("x")
    assert not is_empty(0)        # 0 ist ein gültiger Wert
    assert not is_empty(0.0)
    assert not is_empty(False)


def test_normalize_id():
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("OBJ_0043") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    assert normalize_id(43) == "OBJ_0043"
    assert normalize_id("") is None
    assert normalize_id("Quatsch") is None
    assert display_name("OBJ_0043") == "Objekt 43"


def test_normalize_id_kompaktform_und_alternative_praefixe():
    """OBJ ohne Separator, EN-Langform, Nummer-/Hash-Praefix - in Dateinamen/Captions verbreitet."""
    # Kompaktform OBJ + Ziffern ohne Separator (Datei-/Ordnernamen)
    assert normalize_id("OBJ43") == "OBJ_0043"
    assert normalize_id("OBJ001") == "OBJ_0001"
    assert normalize_id("obj43") == "OBJ_0043"
    # Englische Langform (Foto-Captions / EN-Notizen)
    assert normalize_id("Object 43") == "OBJ_0043"
    assert normalize_id("object 7") == "OBJ_0007"
    # DE Nummerierungs-Praefix
    assert normalize_id("Nr. 43") == "OBJ_0043"
    assert normalize_id("Nr 43") == "OBJ_0043"
    assert normalize_id("Nr.43") == "OBJ_0043"
    assert normalize_id("nr. 7") == "OBJ_0007"
    # Hash-Praefix (Tagebuch-/Foto-Notation)
    assert normalize_id("#43") == "OBJ_0043"
    assert normalize_id("# 43") == "OBJ_0043"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert normalize_id("OBJ-001") == "OBJ_0001"
    assert normalize_id("OBJ_0043") == "OBJ_0043"
    assert normalize_id("Objekt 7") == "OBJ_0007"
    # Ungueltige Formen bleiben None
    assert normalize_id("OBJ X43") is None
    assert normalize_id("OBJ-43X") is None
    assert normalize_id("Objekt001") is None  # DE-Langform braucht Whitespace
    assert normalize_id("Object43") is None   # EN-Langform braucht Whitespace
    assert normalize_id("OBJEKT43") is None   # 'EKT' zwischen Buchstaben und Zahl


def test_parse_range():
    assert csv_loaders.parse_range("6.5–7") == (6.5, 7.0)
    assert csv_loaders.parse_range("6.5-7.0") == (6.5, 7.0)
    assert csv_loaders.parse_range("ca. 2.65") == (2.65, 2.65)
    assert csv_loaders.parse_range("7") == (7.0, 7.0)
    assert csv_loaders.parse_range("2,55") == (2.55, 2.55)
    assert csv_loaders.parse_range("") == (None, None)
    assert csv_loaders.parse_range(None) == (None, None)


def test_parse_range_keine_invertierten_paare():
    """Umgedrehte Range-Eingabe '7-5' (Tippfehler) darf keinen inverted Range liefern.

    (Die IUCr-Kompaktform ``'5.5(3)'`` wird jetzt als publizierte Toleranz
    ausgelesen und lebt in :func:`test_parse_range_klammer_unsicherheit`.)
    """
    # Tippfehler "7-5" → soll nicht (7, 5) liefern
    assert csv_loaders.parse_range("7-5") == (7.0, 7.0)
    # Echter Range bleibt korrekt
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)


def test_parse_range_klammer_unsicherheit():
    """IUCr-Kompaktform ``N(M)`` liefert die publizierten Toleranz-Grenzen.

    Standard-Konvention der International Union of Crystallography und
    verbreitet in mineralogischen Referenz-Tabellen, Roentgen-Beugungs-
    Reports und NIST-CODATA-Konstanten-Tabellen. Vor dem Fix fielen alle
    Kompaktformen entweder auf inverted-Range-Kollaps ``(5.5, 5.5)``
    (Klammer-Zahl < Center) oder auf einen falsch interpretierten Range
    ``(2.65, 5.0)`` (Klammer-Zahl > Center) - beide Faelle verwarfen die
    publizierte Standard-Unsicherheit stille.
    """
    # 5.5(3) = 5.5 ± 0.3 -> Toleranz auf 1. Nachkommastelle
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    # 2.65(5) = 2.65 ± 0.05 -> Toleranz auf 2. Nachkommastelle
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))
    # 100(2) = 100 ± 2 -> Toleranz auf letzte ganze Ziffer (n_decimals = 0)
    assert csv_loaders.parse_range("100(2)") == pytest.approx((98.0, 102.0))
    # Mehrstellige Toleranz: 7.4(15) = 7.4 ± 1.5 (nicht 0.15, weil 15 ist
    # die Standardabweichung in Einheiten der letzten Ziffer und die letzte
    # Ziffer des Zentrums liegt auf 10^-1).
    assert csv_loaders.parse_range("7.4(15)") == pytest.approx((5.9, 8.9))
    # 12.345(67) = 12.345 ± 0.067 -> Toleranz auf 3. Nachkommastelle
    assert csv_loaders.parse_range("12.345(67)") == pytest.approx((12.278, 12.412))
    # Negativer Center (thermische/isotopische Werte, spiegelt die
    # ±-Langform-Konvention).
    assert csv_loaders.parse_range("-1.5(3)") == pytest.approx((-1.8, -1.2))
    # DE-Komma-Dezimal (deutschsprachige Publikationen, Excel-DE).
    assert csv_loaders.parse_range("2,65(5)") == pytest.approx((2.60, 2.70))
    # Whitespace zwischen Wert und Klammer bricht das strikte IUCr-Pattern
    # (echte Annotations-Klammern wie "1.5 (Literatur)" duerfen nicht als
    # Unsicherheit interpretiert werden); Fallback auf Zahl-Extraktion.
    assert csv_loaders.parse_range("5.5 (3)") == (5.5, 5.5)
    # Freitext-Klammer-Annotation NACH IUCr-Kompaktform (durch Whitespace
    # getrennt) wird jetzt toleriert - die Trailing-Klammer-Erweiterung des
    # Uncertainty-Patterns matcht die publizierte Wert-mit-Toleranz-mit-
    # Referenz-Notation als kanonische Publikations-Zeilenform.
    assert csv_loaders.parse_range("5.5(3) (Literatur)") == pytest.approx((5.2, 5.8))
    # Ganzzahliger Wert mit einstelliger Toleranz (haeufig in NIST-Tabellen).
    assert csv_loaders.parse_range("50(1)") == pytest.approx((49.0, 51.0))
    # Toleranz-Klammer allein (ohne Center) bleibt Standard-Fallback.
    assert csv_loaders.parse_range("(3)") == (3.0, 3.0)


def test_parse_range_en_tausendertrenner_mit_dezimal():
    """Englische Excel-Exporte: '1,000.50' (Komma=Tausender, Punkt=Dezimal)."""
    assert csv_loaders.parse_range("1,000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1,000,000.50") == (1000000.5, 1000000.5)
    assert csv_loaders.parse_range("1,000.00-2,000.00") == (1000.0, 2000.0)


def test_parse_range_de_tausendertrenner_mit_dezimal():
    """Deutsche Excel-Exporte: '1.000,50' (Punkt=Tausender, Komma=Dezimal)."""
    assert csv_loaders.parse_range("1.000,50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1.000.000,75") == (1000000.75, 1000000.75)


def test_parse_range_reine_tausendergruppen():
    """Mehrere gleichartige Trenner sind eindeutig Tausender (kein Dezimal)."""
    assert csv_loaders.parse_range("1.000.000") == (1000000.0, 1000000.0)
    assert csv_loaders.parse_range("1,000,000") == (1000000.0, 1000000.0)
    # 3 Gruppen
    assert csv_loaders.parse_range("1.000.000.000") == (1000000000.0, 1000000000.0)


def test_parse_range_ambivalente_einzeltrenner_bleiben_dezimal():
    """'1,000' und '1.000' sind ambivalent - bestehende Dezimal-Lesart beibehalten."""
    # Diese Faelle bleiben Dezimal (Regression-Test fuer bestehende Tests).
    assert csv_loaders.parse_range("1,000") == (1.0, 1.0)
    assert csv_loaders.parse_range("1.000") == (1.0, 1.0)
    # Range-Tokens mit Komma als DE-Dezimal duerfen nicht zu Tausendern werden
    assert csv_loaders.parse_range("6,5-7,0") == (6.5, 7.0)
    assert csv_loaders.parse_range("2,55") == (2.55, 2.55)


def test_parse_range_whitespace_tausender_mit_dezimal():
    """FR/SI-Konvention: Whitespace als Tausendertrenner mit Dezimalanteil.

    Franzoesische Excel-/LibreOffice-Exporte und ISO 31-0-konforme Tools
    schreiben Tausender als NBSP/schmales NBSP/ASCII-Leerzeichen. Vor dem
    Fix lieferte ``'1 000.50'`` (1.0, 0.5) statt (1000.5, 1000.5).
    """
    # ASCII-Leerzeichen (Hand-Eingabe, einige Tools)
    assert csv_loaders.parse_range("1 000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1 234 567.89") == (1234567.89, 1234567.89)
    # FR-Konvention: Whitespace-Tausender + Komma-Dezimal
    assert csv_loaders.parse_range("1 000,50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("12 345 678,90") == (12345678.9, 12345678.9)
    # NBSP (U+00A0) - Default in franzoesischen Office-Suites
    assert csv_loaders.parse_range("1\xa0000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1\xa0234\xa0567,89") == (1234567.89, 1234567.89)
    # Schmales NBSP (U+202F) - ISO 31-0 / SI-Empfehlung
    assert csv_loaders.parse_range("1 000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1 234 567,89") == (1234567.89, 1234567.89)
    # THIN SPACE (U+2009) - das eigentlich BIPM-SI-Brochure / NIST-konforme
    # Tausender-Zeichen (NBSP ist Excel-Praxis, U+2009 ist die SI-Empfehlung
    # im SI-Brochure 8th edition, section 5.3.4). Verbreitet in wissenschaft-
    # lichen Publikationen, LaTeX-Output mit ``\,`` und ISO-31-0-konformen
    # Datensaetzen. Vor dem Fix lieferte ``"1 000.50"`` (1.0, 1.0)
    # statt (1000.5, 1000.5) - silenter Wert-Datenverlust bei der Migration
    # aus typografisch sauber gesetzten Mineralogie-Publikationen.
    assert csv_loaders.parse_range("1 000.50") == (1000.5, 1000.5)
    assert csv_loaders.parse_range("1 234 567,89") == (1234567.89, 1234567.89)
    # Kombiniert mit Punkt-Dezimal (EN-Konvention): THIN SPACE Tausender +
    # ASCII-Punkt-Dezimal aus internationalen Print-Quellen.
    assert csv_loaders.parse_range("12 345.67") == (12345.67, 12345.67)


def test_parse_range_whitespace_tausender_reine_gruppen():
    """Zwei oder mehr Whitespace-Trennergruppen sind eindeutig Tausender."""
    assert csv_loaders.parse_range("1 000 000") == (1000000.0, 1000000.0)
    assert csv_loaders.parse_range("1 234 567") == (1234567.0, 1234567.0)
    assert csv_loaders.parse_range("1 000 000 000") == (1000000000.0, 1000000000.0)
    # NBSP-Variante
    assert csv_loaders.parse_range("1\xa0000\xa0000") == (1000000.0, 1000000.0)
    # THIN SPACE (U+2009) - reine Tausendergruppen ohne Dezimalanteil,
    # spiegelt die NBSP-Variante auf das SI-spezifizierte Trennzeichen.
    assert csv_loaders.parse_range("1 000 000") == (1000000.0, 1000000.0)
    assert csv_loaders.parse_range("1 234 567") == (1234567.0, 1234567.0)
    # Range mit Whitespace-Tausendern auf beiden Seiten
    assert csv_loaders.parse_range("1 000 000-2 000 000") == (1000000.0, 2000000.0)


def test_parse_range_einzelne_whitespace_gruppe_bleibt_ambivalent():
    """``'1 234'`` (eine Gruppe, kein Dezimal) bleibt mehrdeutig wie ``'1,000'``.

    Spiegelt das EN/DE-Verhalten: ohne Dezimal und ohne zweite Trennergruppe
    ist die Whitespace-Form nicht eindeutig (koennte Range-Tippfehler "1 bis
    234" sein). Der Fall bleibt unangetastet - der bestehende Range-Parser
    liefert weiter zwei separate Zahlen.
    """
    # Wuerde sonst als 1234 missinterpretiert; existierender Range-Parser
    # zerlegt in zwei Zahlen (kein Regress fuer "5 7" o.ae.).
    assert csv_loaders.parse_range("1 234") == (1.0, 234.0)
    # Bestaetigung: gleicher Mechanismus wie "5 7"
    assert csv_loaders.parse_range("5 7") == (5.0, 7.0)


def test_parse_range_plus_minus_unsicherheit():
    """Wissenschaftliche Unsicherheits-Notation ``N ± M`` liefert (N-M, N+M).

    In Mineralogie-Publikationen und -Tabellen der Standard-Weg, Messgenauigkeit
    zu notieren. Vor dem Fix lieferte ``5.5 ± 0.3`` den Center-Wert doppelt
    (Toleranz ging verloren); nach dem Fix werden die publizierten Bereichs-
    grenzen sichtbar. Komma-Dezimal (DE) und negativer Center werden unterstuetzt.
    """
    # Standard-Notation mit Whitespace um das ±-Zeichen (Publikations-Praxis).
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    # Ohne Whitespace (Hand-Notation, Excel-Auto-Format).
    assert csv_loaders.parse_range("5.5±0.3") == pytest.approx((5.2, 5.8))
    # DE-Komma-Dezimal (deutschsprachige Publikationen, Excel-DE).
    assert csv_loaders.parse_range("2,65 ± 0,05") == pytest.approx((2.60, 2.70))
    # Negativer Center (thermische/isotopische Werte, seltener in Sammler-DB).
    assert csv_loaders.parse_range("-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    # Toleranz = 0 kollabiert auf Punkt-Wert (Publikationen ohne dokumentierte
    # Unsicherheit notieren manchmal explizit ± 0 als "exakt gemessen").
    assert csv_loaders.parse_range("5.5 ± 0") == (5.5, 5.5)
    # Freitext-Klammer-Annotation nach Uncertainty wird jetzt toleriert - die
    # Trailing-Klammer-Erweiterung des Patterns matcht die publizierte
    # Wert-mit-Toleranz-mit-Referenz-Notation ("5.5 ± 0.3 (Literatur)",
    # "5.5 ± 0.3 [Ref]", "5.5 ± 0.3 {IUCr}") als kanonische Publikations-
    # Zeilenform. Vor der Erweiterung fielen alle diese Formen auf den
    # Fallback-Zahl-Extraktions-Kollaps (5.5, 5.5), obwohl die publizierte
    # Toleranz die intendierten Grenzen (5.2, 5.8) explizit setzt.
    assert csv_loaders.parse_range("5.5 ± 0.3 (Literatur)") == pytest.approx((5.2, 5.8))
    # Ohne Center (nur Toleranz) bleibt das alte Verhalten: eine Zahl.
    assert csv_loaders.parse_range("± 0.5") == (0.5, 0.5)


def test_parse_range_plus_minus_ascii_ersatzform():
    """ASCII-Ersatzformen ``+/-`` und ``+-`` loesen zu identischen Bereichs-
    grenzen auf wie die Unicode-Langform ``±``.

    In E-Mails, Terminal-Ausgaben, LaTeX-Roh-Exporten und geerbten Excel-
    Kopien mit Character-Set-Verlust ist die ASCII-Schreibweise Standard,
    weil der Autor kein Unicode ± zur Verfuegung hatte oder das Zeichen
    beim Kopieren verloren ging (z.B. beim Durchlaufen alter Sammlungs-DB-
    Formate, Foto-EXIF-Kommentaren oder 7-bit-Mail-Transports). Ohne die
    Ersatzform-Erkennung fielen alle diese Notationen weiter auf den
    inverted-Range-Kollaps ``(5.5, 5.5)`` - die Toleranz ging genauso
    verloren, wie beim reinen ``±``-Ausfall vor dem Original-Fix, obwohl
    das rohe Muster ``+/-`` semantisch identisch ist.
    """
    # +/- Standard-Notation (verbreitetste ASCII-Ersatzform)
    assert csv_loaders.parse_range("5.5 +/- 0.3") == pytest.approx((5.2, 5.8))
    # +- (kompakter, ohne Slash)
    assert csv_loaders.parse_range("5.5 +- 0.3") == pytest.approx((5.2, 5.8))
    # Ohne Whitespace um das ASCII-Symbol (Hand-Notation)
    assert csv_loaders.parse_range("5.5+/-0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5+-0.3") == pytest.approx((5.2, 5.8))
    # Ganzzahl-Zentrum mit ganzzahliger Toleranz (100 +/- 2)
    assert csv_loaders.parse_range("100 +/- 2") == (98.0, 102.0)
    # DE-Komma-Dezimal mit ASCII-Ersatzform (DE-Excel-Roh-Exporte)
    assert csv_loaders.parse_range("2,65 +/- 0,05") == pytest.approx((2.60, 2.70))
    # Negativer Center - spiegelt die ±-Konvention
    assert csv_loaders.parse_range("-1.5 +/- 0.3") == pytest.approx((-1.8, -1.2))
    # Freitext-Klammer-Annotation nach Uncertainty wird jetzt toleriert -
    # spiegelt die ±-Erweiterung auf die ASCII-Ersatzformen (+/- und +-).
    assert csv_loaders.parse_range("5.5 +/- 0.3 (Literatur)") == pytest.approx((5.2, 5.8))


def test_parse_range_uncertainty_mit_trailing_einheit():
    """Unsicherheits-Notation mit nachgestellter Einheit behaelt die publizierte Toleranz.

    In mineralogischen Referenz-Tabellen ist die Kompakt- oder Langform *mit*
    Einheit die uebliche Praxis: ``2.65 ± 0.05 g/cm³`` (Dichte-Feld mit SI-
    Einheit inkl. Superscript-3), ``5.5 ± 0.3 Mohs`` (Haerte-Feld mit Skalen-
    Name), ``100 ± 2 HV`` (Vickers-Haerte), ``-1.5 ± 0.3 °C`` (Temperatur).
    Vor dem Fix brach die trailing Einheit den ``$``-Anker der Uncertainty-
    Patterns und liess die Notation auf die generische Zahl-Extraktion
    fallen: ``2.65 ± 0.05 g/cm³`` wurde als ``[2.65, 0.05]`` gelesen und
    lieferte via ``if hi < lo``-Kollaps ``(2.65, 2.65)`` (Toleranz verloren);
    ``2.65(5) g/cm³`` wurde als ``[2.65, 5]`` gelesen und lieferte semantisch
    falsche ``(2.65, 5.0)`` (mineralogisch unsinniger Dichte-Range 2.65 bis
    5.0 g/cm³ statt Toleranz 2.60 bis 2.70); ``5.5(3) Mohs`` fiel via
    inverted-Range auf ``(5.5, 5.5)`` (Toleranz verloren). Fix relaxt das
    ``$``-Ende beider Patterns auf einen Whitespace-getrennten Wort-Token-
    Rest, plus optionale Trailing-Klammer-Annotationen (rund/eckig/geschweift,
    single-level), damit die publizierte Kombination "Wert + Toleranz +
    Einheit + Literatur-/Katalog-Referenz" als kanonische Publikations-
    Zeilenform erhalten bleibt. Komma/Semikolon-Trenner ausserhalb der
    Klammer-Annotationen sind weiter ausgeschlossen (schliesst ``, siehe
    Nr. 42``-Listen aus, damit dortige Nummern nicht als Range-Grenze
    fehlgelesen werden). Der erste Token-Buchstabe im Einheiten-Wort muss
    kein ASCII-Digit sein - damit fallen zufaellige nachgestellte Zahlen
    (``5.5 ± 0.3 42``) auf die Zahl-Extraktion durch und werden nicht in
    die Toleranz eingemischt.
    """
    # ± Langform mit SI-Einheit (Dichte-Feld). Vorher: (2.65, 2.65) via Kollaps.
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    # ± Langform mit Skalen-Name (Haerte-Feld). Vorher: (5.5, 5.5) via Kollaps.
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs") == pytest.approx((5.2, 5.8))
    # ± Langform mit Vickers-Haerte-Kuerzel (Zwei-Buchstaben-Unit).
    assert csv_loaders.parse_range("100 ± 2 HV") == pytest.approx((98.0, 102.0))
    # ± Langform mit Temperatur-Einheit (° als Superscript).
    assert csv_loaders.parse_range("-1.5 ± 0.3 °C") == pytest.approx((-1.8, -1.2))
    # ± Langform mit Prozent-Zeichen (Anteil-Feld, seltene Wahl).
    assert csv_loaders.parse_range("50 ± 2 %") == pytest.approx((48.0, 52.0))
    # ASCII-Ersatzform mit trailing Einheit (7-bit-Mail-Transport, LaTeX-Roh).
    assert csv_loaders.parse_range("2.65 +/- 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 +- 0.3 Mohs") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit SI-Einheit (Dichte-Feld). Vorher: (2.65, 5.0) semantisch falsch.
    assert csv_loaders.parse_range("2.65(5) g/cm³") == pytest.approx((2.60, 2.70))
    # IUCr-Kompaktform mit Skalen-Name (Haerte-Feld). Vorher: (5.5, 5.5) via Kollaps.
    assert csv_loaders.parse_range("5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit Vickers-Kuerzel.
    assert csv_loaders.parse_range("100(2) HV") == pytest.approx((98.0, 102.0))
    # IUCr-Kompaktform mit Kristall-Achsen-Einheit (Angstroem in Roentgenstruktur-Reports).
    assert csv_loaders.parse_range("12.345(67) Å") == pytest.approx((12.278, 12.412))
    # DE-Komma-Dezimal mit trailing Einheit (deutschsprachige Publikationen).
    assert csv_loaders.parse_range("2,65 ± 0,05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2,65(5) g/cm³") == pytest.approx((2.60, 2.70))
    # Mehrere trailing Wort-Tokens (Einheit + Skalen-Zusatz).
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs Haerte") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) Mohs Haerte") == pytest.approx((5.2, 5.8))
    # Klammer-Freitext-Anhang nach Uncertainty (mit oder ohne Einheit dazwischen)
    # wird jetzt toleriert - die Trailing-Klammer-Erweiterung des Patterns
    # matcht die publizierte Wert-mit-Toleranz-mit-Einheit-mit-Referenz-Notation
    # als kanonische Publikations-Zeilenform. Die publizierte Toleranz bleibt
    # erhalten, spiegelt die _PLUS_MINUS_UNCERTAINTY-/_PARENTHESIS_UNCERTAINTY-
    # Grundsemantik auf die reale IUCr-/NIST-Publikations-Praxis, in der Wert
    # + Toleranz + Einheit + Literatur-Verweis eine einzige Tabellen-Zeile
    # bilden.
    assert csv_loaders.parse_range("5.5 ± 0.3 (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³ (Literatur)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5) g/cm³ (Literatur)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 ± 0.3 Mohs [Ref]") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) Mohs [Ref]") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("12.345(67) K [NIST-CODATA-2018]") == pytest.approx((12.278, 12.412))
    # Regression-Anker: Komma-Anhang bricht das Trailing-Pattern (schliesst
    # ``, siehe Nr. 42``-Listen aus). Ohne diesen Ausschluss wuerde eine
    # nachgestellte Referenz-Nummer als Range-Grenze fehlgelesen.
    assert csv_loaders.parse_range("2.65 ± 0.05, siehe") == (2.65, 2.65)
    # Regression-Anker: Trailing-Digit-Token faellt auf Zahl-Extraktion, damit
    # zufaellige Zahlen nicht die Toleranz ueberschreiben.
    assert csv_loaders.parse_range("5.5 ± 0.3 42") == (5.5, 42.0)


def test_parse_range_uncertainty_mit_prozent_und_promille():
    """Unsicherheits-Notation mit ``%``/``‰`` direkt am Wert behaelt die Toleranz.

    In mineralogischen und geochemischen Publikationen sind Prozent-Zeichen
    (``%``, U+0025) und Promille-Zeichen (``‰``, U+2030) haeufige Wert-Suffixe,
    die konventionell OHNE Whitespace zwischen Zahl und Symbol notiert werden
    (``45.2 ± 0.3%`` in oxydischen Chemie-Analysen, ``-15.5 ± 0.5‰`` in
    Isotopen-Fraktionierungs-Werten wie δ¹³C/δ¹⁸O/δ³⁴S, ``100(2)%`` in Erz-
    Gehaltsangaben, ``2.65(5)%`` in Reinheits-/Ausbeute-Tabellen). Vor dem
    Fix brach das direkt angehaengte ``%``/``‰`` den ``$``-Anker beider
    Uncertainty-Patterns: der Trailing-Unit-Zweig verlangte obligatorisches
    ``\\s+`` VOR dem ersten Einheiten-Token, sodass ``5.5 ± 0.3%`` durch das
    fehlende Whitespace zwischen ``0.3`` und ``%`` auf die Fallback-Zahl-
    Extraktion durchfiel und via ``[5.5, 0.3]``-inverted-range auf ``(5.5,
    5.5)`` kollabierte (Toleranz verloren); ``100(2)%`` fiel via ``[100, 2]``
    -> Kollaps auf ``(100, 100)`` (Toleranz verloren); ``-15.5(5)‰`` (Standard-
    Notation der Isotopen-Referenz-Werte in Geochemie-/Kosmochemie-Publikationen)
    fiel via inverted-Range-Kollaps auf ``(-15.5, -15.5)``. In den Fachdomaenen
    (Isotopen-Geochemie: ‰ ist die einzige uebliche Einheit fuer delta-Werte
    stabiler Isotope; Oxid-Gehaltsangaben: wt% / mol% / at% ist die Standard-
    Konvention der Elektronenmikrosonden- und ICP-MS-Analysen; Erz-/Reinheits-
    Angaben: % ohne Whitespace ist die Print-/Excel-Konvention) entsteht damit
    silenter Verlust der publizierten Standard-Unsicherheit auf jeder Analyse-
    /Isotopen-Achse. Fix ergaenzt in beiden Uncertainty-Patterns eine optionale
    ``(?:\\s*[%‰])?``-Alternante hinter der Toleranz-Zahl (und, symmetrisch,
    hinter der Center-Zahl der ±-Langform), sodass das Symbol mit oder ohne
    Whitespace direkt an die Zahl gebunden werden kann, ohne den Trailing-
    Unit-Zweig oder die Trailing-Bracket-Annotations-Zweig zu blockieren.
    Center-``%``/``‰`` fuer die IUCr-Kompaktform ist bewusst NICHT ergaenzt,
    weil die IUCr-Konvention das Einheiten-Symbol strikt hinter die
    Klammer setzt (``5.5%(3)`` waere nicht IUCr-konform).
    """
    # ±-Langform mit ``%`` direkt an der Toleranz (Oxid-Gehaltsangabe).
    # Vorher: (5.5, 5.5) via ``[5.5, 0.3]``-inverted-range-Kollaps.
    assert csv_loaders.parse_range("5.5 ± 0.3%") == pytest.approx((5.2, 5.8))
    # ±-Langform mit ``%`` an Center UND Toleranz (redundante aber verbreitete
    # Publikations-Notation, "Wert-Einheit ± Toleranz-Einheit").
    assert csv_loaders.parse_range("5.5% ± 0.3%") == pytest.approx((5.2, 5.8))
    # ±-Langform ohne Whitespace zwischen ± und Zahlen, ``%`` direkt angehaengt
    # (kompakte Tabellen-Schreibweise ohne Spacing-Overhead).
    assert csv_loaders.parse_range("5.5%±0.3%") == pytest.approx((5.2, 5.8))
    # ±-Langform mit ``‰`` (Promille) fuer Isotopen-delta-Werte. Center darf
    # negativ sein - die klassische Konvention der Isotopen-Fraktionierung
    # (δ¹³C ~ -25‰ in organischer Materie, δ¹⁸O ~ -8‰ in Suesswasser).
    assert csv_loaders.parse_range("-15.5 ± 0.5‰") == pytest.approx((-16.0, -15.0))
    # ±-ASCII-Ersatzform mit ``%`` (7-bit-Mail-Transport, LaTeX-Roh).
    assert csv_loaders.parse_range("5.5 +/- 0.3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +- 0.3%") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit ``%`` (Reinheits-/Ausbeute-Tabellen).
    # Vorher: (5.5, 5.5) via inverted-Range-Kollaps.
    assert csv_loaders.parse_range("5.5(3)%") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit ``%`` (Erz-Gehaltsangabe, ganzzahliges Center).
    # Vorher: (100.0, 100.0) via inverted-Range-Kollaps.
    assert csv_loaders.parse_range("100(2)%") == pytest.approx((98.0, 102.0))
    # IUCr-Kompaktform mit ``‰`` fuer Isotopen-Referenz-Werte.
    assert csv_loaders.parse_range("-15.5(5)‰") == pytest.approx((-16.0, -15.0))
    # DE-Komma-Dezimal mit ``%``/``‰`` direkt angehaengt (deutschsprachige
    # Publikationen mit Komma-Dezimal-Konvention).
    assert csv_loaders.parse_range("5,5 ± 0,3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5,5(3)%") == pytest.approx((5.2, 5.8))
    # ``%``/``‰`` mit optionalem Whitespace davor (Space-getrennte Publikations-
    # Konvention) - bereits vor dem Fix ueber den Trailing-Unit-Zweig
    # unterstuetzt, hier als Regression-Anker gegen die neue Alternante.
    assert csv_loaders.parse_range("5.5 ± 0.3 %") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) %") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("-15.5 ± 0.5 ‰") == pytest.approx((-16.0, -15.0))
    # Kombination ``%`` + Trailing-Klammer-Annotation (publizierte Notation
    # "Wert%-Einheit + Referenz-Klammer").
    assert csv_loaders.parse_range("5.5 ± 0.3% (Literatur)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)% [Ref]") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty OHNE ``%``/``‰`` funktioniert unveraendert.
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty mit Whitespace-getrennter Einheit
    # unveraendert (der neue ``%``/``‰``-Optional-Zweig blockiert die
    # Trailing-Unit-Sequenz nicht).
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty mit Prozent-in-Einheit (``mol%``, ``wt%``,
    # ``at%``) unveraendert - das ``%`` ist Bestandteil eines mehrbuchstabigen
    # Einheiten-Tokens und wird via Trailing-Unit-Zweig gemischt, nicht via
    # der neuen Optional-Alternante.
    assert csv_loaders.parse_range("5.5 ± 0.3 mol%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5) wt%") == pytest.approx((2.60, 2.70))


def test_parse_range_uncertainty_mit_direkt_anhaengender_einheit():
    """Unsicherheits-Notation mit direkt (ohne Whitespace) anhaengender Einheit
    behaelt die publizierte Toleranz.

    In Mineralogie-/Physik-Publikationen, in Excel-CSV-Exporten aus geerbten
    Sammler-Etiketten und in Foto-EXIF-Kommentaren ist die Space-lose Notation
    zwischen Zahl und Einheit sehr verbreitet: ``5.5mm`` (Kristall-Groesse),
    ``2.65g/cm³`` (Dichte), ``100HV`` (Vickers-Haerte), ``12.345K`` (Temperatur).
    Vor dem Fix brach die direkt anhaengende SI-Einheit den ``$``-Anker beider
    Uncertainty-Patterns: der Trailing-Unit-Zweig verlangte obligatorisches
    ``\\s+`` VOR dem ersten Einheiten-Token, sodass ``5.5 ± 0.3mm`` durch das
    fehlende Whitespace zwischen ``0.3`` und ``mm`` auf die Fallback-Zahl-
    Extraktion durchfiel und via ``[5.5, 0.3]``-inverted-range auf ``(5.5,
    5.5)`` kollabierte (Toleranz verloren); ``5.5mm ± 0.3mm`` fiel auf
    ``[5.5, 0.3]``-Kollaps ``(5.5, 5.5)``; ``2.65(5)g/cm³`` fiel auf
    ``[2.65, 5]`` → ``(2.65, 5.0)`` semantisch falsch. Fix ergaenzt in beiden
    Uncertainty-Patterns eine optionale direkt-anhaengende Einheiten-Token-
    Alternante ``(?:[A-Za-zÅΩµ°][A-Za-z0-9ÅΩµ°/^³²]*)?`` hinter Center und
    Toleranz-Zahl. Die Alternante muss mit einem Buchstaben (ASCII a-z / A-Z
    plus SI-Standard-Zeichen Å/Ω/µ/°) STARTEN - damit blockt sie nicht die
    ±-Alternante, die mit ``±``/``+/-``/``+-`` beginnt, und kollidiert nicht
    mit den Bracket-Klammern ``(``/``[``/``{``.
    """
    # ±-Langform mit direkt anhaengender Einheit an Toleranz.
    # Vorher: (5.5, 5.5) via ``[5.5, 0.3]``-inverted-range-Kollaps.
    assert csv_loaders.parse_range("5.5 ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3g") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm3") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm^3") == pytest.approx((2.60, 2.70))
    # ±-Langform mit direkt anhaengender Einheit an Center (Wert-Einheit + Toleranz).
    assert csv_loaders.parse_range("5.5mm ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5g ± 0.3") == pytest.approx((5.2, 5.8))
    # ±-Langform mit direkt anhaengender Einheit an Center UND Toleranz
    # (redundante aber verbreitete Publikations-Notation).
    assert csv_loaders.parse_range("5.5mm ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5g ± 0.3g") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65g/cm3 ± 0.05g/cm3") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65g/cm³ ± 0.05g/cm³") == pytest.approx((2.60, 2.70))
    # ±-ASCII-Ersatzform mit direkt anhaengender Einheit.
    assert csv_loaders.parse_range("5.5 +/- 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +- 0.3mm") == pytest.approx((5.2, 5.8))
    # ±-Langform mit SI-Standard-Sonder-Zeichen (Å, Ω, µ, °).
    assert csv_loaders.parse_range("12.345 ± 0.067K") == pytest.approx((12.278, 12.412))
    assert csv_loaders.parse_range("12.345Å ± 0.067Å") == pytest.approx((12.278, 12.412))
    # IUCr-Kompaktform mit direkt anhaengender Einheit.
    # Vorher: (5.5, 5.5) via inverted-Range-Kollaps.
    assert csv_loaders.parse_range("5.5(3)mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)g") == pytest.approx((2.60, 2.70))
    # IUCr-Kompaktform mit direkt anhaengender SI-Einheit.
    # Vorher: (2.65, 5.0) semantisch falsch.
    assert csv_loaders.parse_range("2.65(5)g/cm3") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm^3") == pytest.approx((2.60, 2.70))
    # IUCr-Kompaktform mit Vickers-Kuerzel direkt anhaengend.
    assert csv_loaders.parse_range("100(2)HV") == pytest.approx((98.0, 102.0))
    # IUCr-Kompaktform mit Angstroem direkt anhaengend.
    assert csv_loaders.parse_range("12.345(67)Å") == pytest.approx((12.278, 12.412))
    # DE-Komma-Dezimal mit direkt anhaengender Einheit.
    assert csv_loaders.parse_range("5,5 ± 0,3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2,65 ± 0,05g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2,65(5)g/cm³") == pytest.approx((2.60, 2.70))
    # Kombination direkt-anhaengende Einheit + Trailing-Klammer-Annotation.
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm³ (Literatur)") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm³ [Ref]") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3)mm (Foto)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Uncertainty mit Whitespace-getrennter Einheit
    # unveraendert (der neue direkt-anhaengende Alternate blockiert die
    # Trailing-Unit-Sequenz nicht).
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3) Mohs") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("12.345(67) Å") == pytest.approx((12.278, 12.412))
    # Regression-Anker: Uncertainty OHNE Einheit funktioniert unveraendert.
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: ``%``/``‰`` direkt anhaengend bleibt via
    # ``(?:\\s*[%‰])?``-Alternante erkannt (nicht via der neuen Buchstaben-
    # basierten Direct-Attach-Alternante).
    assert csv_loaders.parse_range("5.5 ± 0.3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("-15.5 ± 0.5‰") == pytest.approx((-16.0, -15.0))
    # Regression-Anker: Komma-Anhang und Trailing-Digit-Token bleiben Range-
    # Grenze (nicht in die Toleranz eingemischt).
    assert csv_loaders.parse_range("5.5 ± 0.3, siehe") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3 42") == (5.5, 42.0)


def test_parse_range_uncertainty_mit_center_einheit_whitespace_getrennt():
    """Unsicherheits-Notation mit whitespace-getrennter Einheit VOR dem ± behaelt
    die publizierte Toleranz.

    In publizierten Referenz-Tabellen und Excel-CSV-Exporten aus Print-Quellen
    ist die redundante "Center-mit-Einheit ± Toleranz-mit-Einheit"-Notation
    eine sehr verbreitete Standard-Praxis (Sammler kopieren komplette Dichte-
    /Haerte-/Temperatur-Zeilen aus IUCr-/NIST-Publikationen und Print-
    Nachschlagewerken, wo die Einheit auf beiden Seiten des ±-Symbols
    redundant notiert wird). Vor dem Fix fiel jede Notation mit whitespace-
    getrennter Einheit VOR dem ±-Symbol still auf die Fallback-Zahl-
    Extraktion durch: ``2.65 g/cm³ ± 0.05 g/cm³`` wurde als ``[2.65, 0.05]``
    gelesen und via ``if hi < lo``-Kollaps auf ``(2.65, 2.65)`` reduziert
    (Toleranz verloren); ``-1.5 °C ± 0.3`` sogar semantisch falsch als
    ``[-1.5, 0.3]``-Range interpretiert und zu ``(-1.5, 0.3)`` (thermisch
    unsinnige Range-Grenzen, publizierte Standard-Unsicherheit als Range-
    Grenze fehlgedeutet). Fix ergaenzt in :data:`_PLUS_MINUS_UNCERTAINTY`
    einen ``(?:\\s+…[A-Za-z…][A-Za-z0-9…]*)*``-Zweig ZWISCHEN Center und
    ± symmetrisch zur bereits vorhandenen Trailing-Einheit-nach-Toleranz-
    Klausel.

    Der Zweig backtrackt sauber bei ± direkt hinter Center (``5.5 ± 0.3``):
    das erste-Zeichen-muss-Buchstabe-Kriterium (``[A-Za-zÅΩµ°]``) blockt die
    ±-Zeichen-Position, und das ``*``-Quantifier erlaubt Zero-Match. Regression-
    Anker gegen die vorhandenen Uncertainty-Tests: ``5.5 ± 0.3`` (kein Middle-
    Token) bleibt unveraendert, ``5.5 ± 0.3 mm`` (Trailing-Token, nicht Middle)
    bleibt unveraendert.
    """
    # SI-Einheit auf Center UND Toleranz, whitespace-getrennt (Publikations-Standard
    # aus mineralogischen Dichte-Tabellen). Vorher: (2.65, 2.65) via Kollaps.
    assert csv_loaders.parse_range(
        "2.65 g/cm³ ± 0.05 g/cm³"
    ) == pytest.approx((2.60, 2.70))
    # SI-Einheit nur auf Center-Seite, Toleranz ohne Einheit (kompaktere
    # Publikations-Notation). Vorher: (5.5, 5.5) via Kollaps.
    assert csv_loaders.parse_range("5.5 mm ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 g ± 0.3") == pytest.approx((5.2, 5.8))
    # Zwei-Buchstaben-Einheit (Vickers-Haerte-Kuerzel) auf Center UND Toleranz.
    # Vorher: (100.0, 100.0) via Kollaps.
    assert csv_loaders.parse_range("100 HV ± 2") == (98.0, 102.0)
    assert csv_loaders.parse_range("100 HV ± 2 HV") == (98.0, 102.0)
    # Skalen-Name (Mohs-Haerte, kein SI-Symbol) auf Center-Seite.
    assert csv_loaders.parse_range("5.5 Mohs ± 0.3") == pytest.approx((5.2, 5.8))
    # Temperatur-Einheit mit SI-Standard-Sonderzeichen (° = U+00B0) auf Center
    # UND Toleranz. Negativer Center - spiegelt die _PLUS_MINUS-Konvention.
    # Vorher besonders schlimm: (-1.5, 0.3) als vermeintlicher Range across-zero.
    assert csv_loaders.parse_range("-1.5 °C ± 0.3") == pytest.approx((-1.8, -1.2))
    assert csv_loaders.parse_range(
        "-1.5 °C ± 0.3 °C"
    ) == pytest.approx((-1.8, -1.2))
    # Angstroem-Einheit (Kristall-Achsen-Laengen in Roentgen-Struktur-Reports).
    assert csv_loaders.parse_range(
        "12.345 Å ± 0.067 Å"
    ) == pytest.approx((12.278, 12.412))
    # SI-Standard-Sonderzeichen Å auf Center-Seite, ohne Einheit auf Toleranz.
    assert csv_loaders.parse_range(
        "12.345 Å ± 0.067"
    ) == pytest.approx((12.278, 12.412))
    # Ohm (Ω = U+03A9) - elektrische Leitfaehigkeit in erz-mineralogischen
    # Kontexten (Halbleiter-Mineralien, Cu-/Ag-Analytik).
    assert csv_loaders.parse_range("100 Ω ± 5") == (95.0, 105.0)
    # ASCII-Ersatzform ``+/-`` mit Center-Einheit (LaTeX-Roh-Export, 7-bit-Mail).
    assert csv_loaders.parse_range(
        "2.65 g/cm³ +/- 0.05 g/cm³"
    ) == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5 mm +/- 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 mm +- 0.3") == pytest.approx((5.2, 5.8))
    # DE-Komma-Dezimal auf Center und Toleranz mit whitespace-getrennter Einheit
    # (deutschsprachige mineralogische Publikationen und DE-Excel-Exporte).
    assert csv_loaders.parse_range(
        "2,65 g/cm³ ± 0,05 g/cm³"
    ) == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5,5 mm ± 0,3") == pytest.approx((5.2, 5.8))
    # Mehrere whitespace-getrennte Einheiten-Tokens auf Center-Seite (Skalen-
    # Name + Zusatz-Marker, publizierte Praxis in mineralogischen Referenz-
    # Tabellen).
    assert csv_loaders.parse_range(
        "5.5 Mohs Haerte ± 0.3"
    ) == pytest.approx((5.2, 5.8))
    # Kombination Center-Einheit + Trailing-Klammer-Annotation (kanonische
    # Publikations-Zeilenform "Wert-Einheit + Toleranz + Referenz-Klammer").
    assert csv_loaders.parse_range(
        "2.65 g/cm³ ± 0.05 g/cm³ (Literatur)"
    ) == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range(
        "100 HV ± 2 HV [NIST-2018]"
    ) == (98.0, 102.0)
    # Kombination Center-Einheit + Trailing-Satzzeichen (aus Satz-Fluss
    # uebernommener Wert).
    assert csv_loaders.parse_range("5.5 mm ± 0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("100 HV ± 2 HV;") == (98.0, 102.0)
    # Regression-Anker: Uncertainty OHNE Center-Einheit bleibt via Zero-Match
    # der neuen ``*``-Alternante unveraendert.
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³") == pytest.approx((2.60, 2.70))
    # Regression-Anker: direkt anhaengende Einheit (ohne Whitespace) auf Center
    # bleibt via bestehende Direct-Attach-Alternante erkannt, nicht via der
    # neuen Whitespace-Middle-Unit-Alternante.
    assert csv_loaders.parse_range("5.5mm ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5mm ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range(
        "2.65g/cm³ ± 0.05g/cm³"
    ) == pytest.approx((2.60, 2.70))
    # Regression-Anker: gemischte Notation (Whitespace-Center, Attached-Toleranz)
    # bleibt korrekt aufgeloest.
    assert csv_loaders.parse_range("5.5 mm ± 0.3mm") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5mm ± 0.3 mm") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Range mit "N to M"-Syntax bleibt Fallback (kein
    # Uncertainty), weil ``to`` zwar durch die Middle-Unit-Alternante
    # konsumiert wird, aber die Toleranz-Zahl nach dem naechsten Whitespace
    # kein Buchstabe ist und das Uncertainty-Pattern insgesamt nicht matcht;
    # die Fallback-Zahl-Extraktion liefert [5, 10, 0.3], via ``hi < lo``-
    # Anti-Kollaps auf (5.0, 5.0) - die publizierte Range-Grenze wird
    # verworfen, weil die Notation ohnehin mehrdeutig ist (Range oder
    # Range-mit-Toleranz?), das Center-only-Fallback ist die konservative Wahl.
    assert csv_loaders.parse_range("5 to 10 ± 0.3") == (5.0, 5.0)


def test_parse_range_prozent_promille_range_ohne_whitespace_um_bindestrich():
    """Range-Notation ``N%-M%`` / ``N‰-M‰`` ohne Whitespace um den Bindestrich
    liefert beide Bereichsgrenzen (keine Sign-Bindung an die obere Grenze).

    In Sammler-Notizen sind Prozent-/Promille-Bereichs-Angaben ohne
    Whitespace um den Bindestrich der praxis-verbreitetste Kompakt-Stil
    ("Cu-Gehalt 5%-10% (XRF)", "Fluid-Einschluss-Salinitaet 3%-8%",
    "Isotopen-Fraktionierung δ13C 0.5‰-2.5‰"). Vor dem Fix fiel der
    zu enge Sign-Lookbehind auf ``[5, -10]``, was via ``if hi < lo``-
    Kollaps stille auf ``(5.0, 5.0)`` reduzierte und die obere Grenze
    verwarf - silenter Datenverlust auf ppm-nahen Konzentrations- und
    Isotopen-Feldern. Fix erweitert die Sign-Blockierung ``(?<![\\d.])-``
    auf ``(?<![\\d.%‰])-`` und beruecksichtigt die Wert-Terminatoren
    ``%``/``‰`` als sign-blockierende Vorgaenger.
    """
    # Prozent-Range ohne Whitespace um den Bindestrich
    assert csv_loaders.parse_range("5%-10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5%-10") == (5.0, 10.0)
    assert csv_loaders.parse_range("5.5%-10.5%") == pytest.approx((5.5, 10.5))
    assert csv_loaders.parse_range("0%-100%") == (0.0, 100.0)
    # Promille-Range (Isotopen-Fraktionierung, Wasser-Chemie)
    assert csv_loaders.parse_range("0.5‰-2.5‰") == pytest.approx((0.5, 2.5))
    assert csv_loaders.parse_range("1‰-3‰") == (1.0, 3.0)
    # Whitespace-Kombinationen: bereits vor dem Fix korrekt, hier als
    # Regress-Anker (das Fix darf keine dieser Formen brechen)
    assert csv_loaders.parse_range("5% - 10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5 % - 10 %") == (5.0, 10.0)
    assert csv_loaders.parse_range("5 %-10 %") == (5.0, 10.0)
    assert csv_loaders.parse_range("5%- 10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5-10%") == (5.0, 10.0)
    # DE-Komma-Dezimal im Prozent-Range
    assert csv_loaders.parse_range("5,5%-10,5%") == pytest.approx((5.5, 10.5))
    # Range mit "bis"/"to"-Wort-Trenner (kein Sign-Konflikt, aber
    # Konsistenz-Anker fuer Prozent-Notation)
    assert csv_loaders.parse_range("5% bis 10%") == (5.0, 10.0)
    assert csv_loaders.parse_range("5% to 10%") == (5.0, 10.0)
    # Regress-Anker: Negativ-Vorzeichen bleibt aktiv an legitimen
    # Start-Positionen (String-Anfang, Whitespace, Komma, Semikolon,
    # Klammer, andere Nicht-Wert-Terminatoren) - der Fix darf die
    # Negativ-Semantik nur an %/‰-Positionen blockieren
    assert csv_loaders.parse_range("-5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-5-10") == (-5.0, 10.0)
    assert csv_loaders.parse_range("-10 - -5") == (-10.0, -5.0)
    assert csv_loaders.parse_range("5, -10") == (5.0, 5.0)   # inverted collapse
    assert csv_loaders.parse_range("-15.5 ± 0.5‰") == pytest.approx((-16.0, -15.0))
    # Regress-Anker: reine Prozent-/Promille-Einzelwerte unveraendert
    assert csv_loaders.parse_range("5%") == (5.0, 5.0)
    assert csv_loaders.parse_range("5‰") == (5.0, 5.0)
    assert csv_loaders.parse_range("100%") == (100.0, 100.0)
    # Regress-Anker: Uncertainty mit Prozent-Suffix unveraendert (der
    # dedizierte ±-Zweig matcht vor der Range-Zahl-Extraktion)
    assert csv_loaders.parse_range("5.5% ± 0.3%") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)%") == pytest.approx((5.2, 5.8))
    # Regress-Anker: Basis-Range ohne Prozent unveraendert
    assert csv_loaders.parse_range("5-10") == (5.0, 10.0)
    assert csv_loaders.parse_range("5.5-10.5") == pytest.approx((5.5, 10.5))
    # Regress-Anker: mol%/wt%/at% (Prozent als Teil eines mehrbuchstabigen
    # Einheit-Tokens) bleibt Range-Grenze, nicht sign-blockierender Terminator
    assert csv_loaders.parse_range("5.5 mol% - 10.5 mol%") == pytest.approx((5.5, 10.5))
    assert csv_loaders.parse_range("5 wt% - 10 wt%") == (5.0, 10.0)


def test_parse_range_uncertainty_mit_trailing_satzzeichen():
    """Uncertainty-Notation mit Trailing-Satzzeichen (``.``, ``,``, ``;``,
    ``:``, ``!``, ``?``) behaelt die publizierte Toleranz.

    In Sammler-Notizen und Excel-CSV-Zeilen ist es sehr verbreitet, den Wert
    mit Toleranz am Ende eines Satzes oder einer Zeilen-Zelle mit einem
    Punkt/Komma/Semikolon abzuschliessen ("Dichte 2.65 ± 0.05.",
    "Haerte 5.5 ± 0.3, siehe Literatur X", "5.5(3);"). Vor dem Fix
    ankerten beide Uncertainty-Patterns strikt auf ``\\s*$`` - jedes
    Trailing-Satzzeichen blockte den End-Anker-Match und die Formen fielen
    still auf die Fallback-Zahl-Extraktion via ``[center, tol]``-inverted-
    range-Kollaps auf ``(center, center)`` durch (Toleranz verloren). Fix
    ergaenzt beide Patterns um eine optionale Trailing-Satzzeichen-Klasse
    ``[.,;:!?]?`` vor dem End-Anker.
    """
    # ±-Langform mit einzelnem Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3;") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3:") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3!") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3?") == pytest.approx((5.2, 5.8))
    # Ohne Whitespace um ±
    assert csv_loaders.parse_range("5.5±0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5±0.3,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5±0.3;") == pytest.approx((5.2, 5.8))
    # ASCII-Ersatzform (+/-, +-) mit Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 +/- 0.3.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +/- 0.3,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 +- 0.3;") == pytest.approx((5.2, 5.8))
    # IUCr-Kompaktform mit Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5(3).") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3),") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3);") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3):") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5),") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("100(2).") == (98.0, 102.0)
    # Mit direkt anhaengender Einheit + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3mm,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3mm.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05g/cm³,") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("2.65(5)g/cm³.") == pytest.approx((2.60, 2.70))
    # Mit Whitespace-getrennter Einheit + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3 mm,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65 ± 0.05 g/cm³.") == pytest.approx((2.60, 2.70))
    assert csv_loaders.parse_range("5.5(3) Mohs;") == pytest.approx((5.2, 5.8))
    # Mit Trailing-Klammer-Annotation + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5 ± 0.3 (Literatur).") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3 (Ref),") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) [NIST-2018].") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("100(2) {IUCr};") == (98.0, 102.0)
    # Mit Prozent-/Promille-Suffix + Trailing-Satzzeichen
    assert csv_loaders.parse_range("5.5% ± 0.3%.") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)%,") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("-15.5 ± 0.5‰.") == pytest.approx((-16.0, -15.0))
    # Trailing-Whitespace nach Satzzeichen toleriert
    assert csv_loaders.parse_range("5.5 ± 0.3, ") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3.  ") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3);  ") == pytest.approx((5.2, 5.8))
    # Regress-Anker: ohne Trailing-Satzzeichen unveraendert
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3 mm") == pytest.approx((5.2, 5.8))
    # Regress-Anker: Trailing-Freitext nach Satzzeichen fuehrt weiter zum
    # Fallback (kein Match des Uncertainty-Zweigs, kein Ausschnitt-Match durch
    # die neue optionale Satzzeichen-Klasse). Der Fallback liefert
    # ``[center, tol]`` und kollabiert via ``if hi < lo`` auf ``(center, center)``
    # - identisch zum Verhalten vor dem Fix, das Fix ist strikt additiv fuer
    # die reine Satzzeichen-Terminator-Position.
    assert csv_loaders.parse_range("5.5 ± 0.3, more text") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 ± 0.3!!more") == (5.5, 5.5)
    # Freitext ohne Satzzeichen wird bereits vor dem Fix vom Trailing-Unit-
    # Wort-Zweig aufgesaugt (jedes Wort wird als Einheit interpretiert), so
    # dass ``"5.5(3) with note"`` als valide IUCr-Kompaktform + zwei Einheiten-
    # Tokens erkannt wird und die Toleranz behaelt - Regress-Anker fuer die
    # (ueberraschende, aber semantisch verlust-freie) alte Semantik.
    assert csv_loaders.parse_range("5.5(3) with note") == pytest.approx((5.2, 5.8))


def test_parse_range_klammer_annotation_wird_nicht_als_range_gelesen():
    """Klammer-umschlossene Freitext-Anhaenge sind Annotation, nicht Range-Grenze.

    In Sammler-Notizen sind Foto-/Katalog-/Referenz-Marker in Klammern
    strukturell separat vom Wert-Bereich: ``"5.5 (2020)"`` bedeutet "Wert 5.5,
    Referenz-Jahr 2020" - nicht "Wert-Bereich 5.5 bis 2020". Vor dem Fix
    lieferte die generische Fallback-Zahl-Extraktion alle Zahlen inkl. der
    Annotation als vermeintliche Range-Grenzen und produzierte mineralogisch/
    sammlungslogisch unsinnige Bereiche:

    * ``"5.5 (2020)"``        -> (5.5, 2020.0)   (Jahr als hi statt Annotation)
    * ``"5-7 Mohs (Nr. 42)"`` -> (5.0, 42.0)     (Katalog-Nr. als hi)
    * ``"2.65 (Ref 42)"``     -> (2.65, 42.0)    (Ref-Nr. als hi)
    * ``"5.5 [2024]"``        -> (5.5, 2024.0)   (Jahr in eckigen Klammern)

    Bei allen inverted-Range-Faellen (Annotation-Zahl < Zentrum-Zahl) griff
    der ``if hi < lo``-Fallback und kollabierte auf ``(lo, lo)`` - aber
    sobald die Annotation *groesser* als das Zentrum war (Jahres-Marker,
    hohe Katalog-Nummern), wurde die Annotation stille als hoher Range-Wert
    gelesen.

    Der Fix strippt runde/eckige/geschweifte Klammer-Annotationen inkl.
    Verschachtelung vor der Zahl-Extraktion. Kritischer Rueckfall-Schutz:
    wenn der Wert *selbst* in Klammern steht (``"(5-7)"``, ``"(2.65)"``,
    ``"[5,7]"`` als mathematisches Intervall), wird der Original-String
    beibehalten - die Klammer-Umhuellung wird dann als Wert-Traeger
    interpretiert, nicht als Annotation.
    """
    # Jahres-Annotation nach Wert (Foto-Referenz / Kauf-Jahr). Vorher: (5.5, 2020.0).
    assert csv_loaders.parse_range("5.5 (2020)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 [2024]") == (5.5, 5.5)
    # Katalog-/Referenz-Nummer nach Wert. Vorher: (2.65, 42.0).
    assert csv_loaders.parse_range("2.65 (Ref 42)") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 (Nr. 42)") == (2.65, 2.65)
    # Katalog-Nummer nach Range. Vorher: (5.0, 42.0).
    assert csv_loaders.parse_range("5-7 (Nr. 42)") == (5.0, 7.0)
    assert csv_loaders.parse_range("5-7 Mohs (siehe Ref. 42)") == (5.0, 7.0)
    # Jahres-Annotation nach Range in eckigen Klammern. Vorher: (5.5, 2024.0).
    assert csv_loaders.parse_range("5.5-7.0 [Verified 2024]") == (5.5, 7.0)
    # Freitext-Annotation ohne Zahl (bleibt aus Symmetrie-Gruenden ebenfalls
    # gestrippt, damit trailing-Freitext in Klammern kein Rest-Whitespace
    # als Wert-Erweiterung anschleppt).
    assert csv_loaders.parse_range("5.5 (Foto)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 [verified]") == (5.5, 5.5)
    assert csv_loaders.parse_range("5.5 {geerbt}") == (5.5, 5.5)
    # Verschachtelte Klammern werden vom Innen-nach-Aussen aufgeloest.
    assert csv_loaders.parse_range("5.5 (Foto (gut))") == (5.5, 5.5)
    assert csv_loaders.parse_range("5-7 [Range (Mohs) verified]") == (5.0, 7.0)
    # Klammer-Freitext-Anhang nach Uncertainty wird jetzt vom erweiterten
    # Uncertainty-Pattern direkt matched (Trailing-Klammer-Erweiterung), sodass
    # die publizierte Toleranz erhalten bleibt. Vorher: die Klammer blockte
    # das End-Anker-Matching, und der Fallback lieferte via Strip nur den
    # Center ("5.5 ± 0.3 (Ref 42)" -> (5.5, 5.5)); mit der Erweiterung matcht
    # die Klammer-Annotation als Trailing-Zweig und die Toleranz-Grenzen
    # bleiben erhalten ((5.2, 5.8) fuer die ±-Form, (5.2, 5.8) fuer die
    # IUCr-Kompaktform).
    assert csv_loaders.parse_range("5.5 ± 0.3 (Ref 42)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5(3) (Ref 42)") == pytest.approx((5.2, 5.8))
    # Regression-Anker: Wert *selbst* in Klammern bleibt unangetastet.
    # Rueckfall-Schutz greift, weil nach dem Strip keine Ziffern mehr uebrig
    # waeren - die Klammer wird als Wert-Traeger interpretiert.
    assert csv_loaders.parse_range("(5-7)") == (5.0, 7.0)
    assert csv_loaders.parse_range("(2.65)") == (2.65, 2.65)
    # ``[5-7]`` als mathematisches Intervall mit ASCII-Bindestrich - der
    # Komma-Trenner ``[5,7]`` bleibt bewusst ausgespart, weil er mit dem
    # DE-Dezimal-Komma kollidiert (``5,7`` waere gleichzeitig "5 komma 7"
    # als 5.7 und Zweier-Liste "5 und 7"); die Klammer-Umhuellung mit
    # Bindestrich ist eindeutig.
    assert csv_loaders.parse_range("[5-7]") == (5.0, 7.0)
    assert csv_loaders.parse_range("{5-7}") == (5.0, 7.0)
    # Regression-Anker: bereits vorhandene Grenzform-Tests bleiben unveraendert.
    assert csv_loaders.parse_range("5.5 (3.0)") == (5.5, 5.5)   # inverted-Kollaps


def test_parse_range_wissenschaftliche_notation():
    """Zahl-Token mit Exponent ``E±N`` wird als scientific-notation gelesen.

    In Mineralogie-/Physik-Publikationen die Standardform fuer Werte, die
    viele Groessenordnungen ueberspannen: Absorptions-Querschnitte in cm²
    (``2.5e-19``), Halbwertszeiten von Isotopen in Jahren (``4.5e9``),
    Kalibrier-Konstanten aus spektroskopischen Messungen (``1.5e-3``),
    Fluoreszenz-Lebensdauern in Sekunden (``3e-6``). Vor dem Fix wurde
    ``1e3`` als zwei Tokens ``1`` und ``3`` gelesen (inverted range,
    Fallback (1.0, 1.0)); ``1.5e-3`` lieferte ``(1.5, 3.0)`` als
    vermeintlicher Range ``1.5 bis 3`` - beide Faelle verwerfen die
    Groessenordnung stille.

    Kollisionsfreiheit zu den Uncertainty-Patterns (Langform ``N ± M``
    und IUCr-Kompaktform ``N(M)``): der Exponent-Match greift nur, wenn
    weder die ± noch die Klammer-Struktur den Freitext strukturell
    umschliesst - beide Uncertainty-Zweige fangen ihren Fall via
    ^...$-Anker vor der generischen Zahlen-Extraktion ab, sodass
    ``5.5(3)`` und ``5.5 ± 0.3`` weiterhin die publizierte Toleranz
    liefern und nicht als scientific-notation-Kollision fehlinterpretiert
    werden.
    """
    # Ganzzahl-Mantisse mit positivem Exponent: klassische Compact-Form fuer
    # Werte in wissenschaftlichen Notizen.
    assert csv_loaders.parse_range("1e3") == (1000.0, 1000.0)
    # Explizites Plus-Vorzeichen (Excel-DE-Auto-Format schreibt haeufig
    # ``1,5E+03``; NIST-CODATA-Tabellen ``1.5E+3`` mit sichtbarem Plus).
    assert csv_loaders.parse_range("1.5E+3") == (1500.0, 1500.0)
    # Negativer Exponent: der Standard-Fall fuer sub-Einheiten-Groessen
    # (Kalibrier-Konstanten, Absorptions-Querschnitte, HWZ-Bruchteile).
    assert csv_loaders.parse_range("1.5e-3") == (0.0015, 0.0015)
    # Case-insensitive: ``e`` und ``E`` beide gueltig (LaTeX-Rendering
    # schreibt ``e``, Excel-Auto-Format ``E``).
    assert csv_loaders.parse_range("2.65e0") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65E0") == (2.65, 2.65)
    # DE-Komma-Dezimal in der Mantisse (deutsche Publikationen, Excel-DE
    # schreibt ``1,5E-03`` mit Komma-Dezimal); der Exponent selbst ist
    # immer ganzzahlig ohne Locale-Problem.
    assert csv_loaders.parse_range("1,5e-3") == (0.0015, 0.0015)
    # Astronomische Groessenordnungen (Halbwertszeit U-238 in Jahren,
    # Absorptions-Querschnitt in cm²) - decken den float-Wertebereich ab.
    assert csv_loaders.parse_range("4.5e9") == (4.5e9, 4.5e9)
    assert csv_loaders.parse_range("2.5e-19") == (2.5e-19, 2.5e-19)
    # Echter Range mit scientific notation auf beiden Seiten (Kalibrier-
    # Bereich, Absorptions-Spektrum): der Range-Trenner ist der Bindestrich
    # zwischen den beiden Exponent-Zahlen, nicht der Minus-Anker des
    # rechten Exponents.
    assert csv_loaders.parse_range("1e3 - 5e3") == (1000.0, 5000.0)
    # Range mit negativem Exponent auf beiden Seiten: sicherstellen, dass
    # die Zahl-Zerlegung greedy den ganzen Exponent-Token nimmt und nicht
    # vorzeitig beim Bindestrich abbricht.
    assert csv_loaders.parse_range("1e-3 - 5e-3") == (0.001, 0.005)
    # Einzelner Exponent ohne Mantisse-Dezimalstelle (``1e0`` = 1) - lieferte
    # frueher ueber die Zwei-Zahl-Zerlegung (1.0, 0.0) → collapsed (1.0, 1.0).
    # Neues Verhalten: exponent wird ausgewertet, liefert dasselbe (1.0, 1.0)
    # aber ueber den semantisch korrekten Pfad.
    assert csv_loaders.parse_range("1e0") == (1.0, 1.0)
    # Kollisionsfreiheit mit den Uncertainty-Zweigen: die publizierte
    # Toleranz-Semantik bleibt Vorrang; ``5.5(3)`` liefert weiterhin die
    # Klammer-Unsicherheit, kein scientific-notation-Fallback, und
    # ``5.5 ± 0.3`` bleibt Langform-Uncertainty. Regression-Anker fuer
    # den Fall, dass jemand die Zweige umsortiert.
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))


def test_parse_range_scientific_notation_overflow():
    """Overflow der Exponent-Notation (``1e400`` -> ``inf``) faellt auf ``(None, None)``.

    ``float()`` konvertiert Mantissen jenseits des IEEE-754-Bereichs
    (rund ``1.7976931348623157e+308``) stille zu ``+inf``/``-inf`` und
    ``inf ± inf`` bzw. ``inf - inf`` zu ``NaN``. Ohne Filter wanderten
    diese Werte transparent als vermeintlich gueltige Bereichsgrenzen in
    die Numeric-Felder (Wert_CHF, Gewicht_g, Dichte, Haerte) und
    korrumpierten stille alle nachgelagerten Operationen: SUM/AVG in der
    Statistik lieferten ``inf``, Sortierung nach Wert setzt den
    Overflow-Datensatz endlos an die Spitze, JSON-Export via
    ``json.dumps`` mit ``allow_nan=False`` verweigert die Serialisierung
    (Backup-CLI wuerde brechen) und ``allow_nan=True`` schreibt das
    JSON-spec-widrige Literal ``Infinity``. Vor dem Fix lieferte
    ``'1e400'`` -> ``(inf, inf)``, ``'1e400 ± 0.1'`` -> ``(inf, inf)`` und
    ``'5.5 - 1e400'`` -> ``(5.5, inf)``.

    Semantisch ist ein Token, das float nicht darstellen kann, aequivalent
    zu "kein gueltiger Wert" - konsistent mit der bestehenden ``(None,
    None)``-Rueckgabe fuer leere/nicht-parsbare Eingaben. Bei gemischten
    Ranges (endlich + overflow) bleibt der endliche Teil als (n, n)
    erhalten, damit die endliche Halb-Information nicht mit-verworfen
    wird.
    """
    # Reiner Overflow: das einzige Token ueberlaeuft, keine Zahl uebrig.
    assert csv_loaders.parse_range("1e400") == (None, None)
    assert csv_loaders.parse_range("1E400") == (None, None)
    assert csv_loaders.parse_range("2.5e999") == (None, None)
    # Explizit negativer Overflow (typografisch selten, aber float()-symmetrisch).
    assert csv_loaders.parse_range("-1e400") == (None, None)
    # Beide Range-Seiten ueberlaufen -> keine endliche Grenze uebrig.
    assert csv_loaders.parse_range("1e400 - 5e400") == (None, None)
    # Gemischt: nur eine Seite ueberlaeuft; die endliche Halb-Info bleibt
    # als Punkt-Wert erhalten (via inverted-range-Fallback nach der
    # finite-Filter-Reduktion).
    assert csv_loaders.parse_range("5.5 - 1e400") == (5.5, 5.5)
    assert csv_loaders.parse_range("1e400 - 5.5") == (5.5, 5.5)
    # Uncertainty-Zweige mit Overflow-Center: arithmetische Verkettung
    # (``inf ± tol`` bzw. ``inf(2)``) liefert ``inf``/``NaN``, wird
    # via ``_finite_pair`` auf ``(None, None)`` gemappt.
    assert csv_loaders.parse_range("1e400 ± 1e400") == (None, None)
    # Regression-Anker: normale scientific notation innerhalb des
    # float-Bereichs bleibt unveraendert (die Filter greift nur bei
    # Overflow, nicht bei allen Werten mit Exponent).
    assert csv_loaders.parse_range("4.5e9") == (4.5e9, 4.5e9)
    assert csv_loaders.parse_range("2.5e-19") == (2.5e-19, 2.5e-19)
    # Underflow zu subnormal/0.0 bleibt endlich und wird NICHT gefiltert -
    # 0 ist ein legitimer Zahl-Wert (Nullpunkt), im Gegensatz zu inf.
    assert csv_loaders.parse_range("1e-400") == (0.0, 0.0)


def test_parse_range_leading_dot_dezimal():
    """Leading-Dot-Dezimals ``.5`` / ``.05`` / ``.5e-3`` werden als Wert < 1 gelesen.

    US-typografische Konvention "no leading zero" und wissenschaftliche
    Publikationen ohne fuehrende Null (LaTeX/PDF-Roh-Export, Print-Kataloge,
    NIST-CODATA-Auszuege). Vor dem Fix fiel der Punkt aus dem Match des
    generischen Zahl-Token-Regex und die Ziffernfolge dahinter wurde als eigene
    Ganzzahl gelesen: ``.5`` lieferte (5.0, 5.0) statt (0.5, 0.5) (Faktor 10
    zu gross), ``.5-.7`` lieferte (5.0, 7.0) statt (0.5, 0.7), ``.5e-3`` (kleiner
    Absorptions-/Kalibrier-Wert in Publikationen ohne fuehrende Null) lieferte
    ueber Zwei-Zahl-Zerlegung ``[5, 3]`` und hi<lo-Fallback (5.0, 5.0) statt
    (0.0005, 0.0005) - Faktor 10.000 zu gross. Bei der Migration aus US-/
    englischsprachigen Sammlungs-Notizen und aus LaTeX-Publikationen ohne
    fuehrende Null entstand damit silenter Groessenordnungs-Verlust bei
    kleinen Werten (Mikroskopie-Messwerte, Foliendicken, Feinkorn-Groessen).
    """
    # Punktwert ohne fuehrende Null (typisch US/Print).
    assert csv_loaders.parse_range(".5") == (0.5, 0.5)
    assert csv_loaders.parse_range(".05") == (0.05, 0.05)
    assert csv_loaders.parse_range(".005") == (0.005, 0.005)
    # Range ohne fuehrende Nullen auf beiden Seiten.
    assert csv_loaders.parse_range(".5-.7") == (0.5, 0.7)
    assert csv_loaders.parse_range(".5 - .7") == (0.5, 0.7)
    # Gemischt: leading-dot links, normale Zahl rechts (und umgekehrt).
    assert csv_loaders.parse_range(".5-7") == (0.5, 7.0)
    # Scientific notation ohne fuehrende Null - Absorptions-/Kalibrier-Werte
    # in Publikationen (``.5e-3`` = 5e-4 = 0.0005).
    assert csv_loaders.parse_range(".5e-3") == (0.0005, 0.0005)
    assert csv_loaders.parse_range(".5E+3") == (500.0, 500.0)
    # Freitext-Praefix (z.B. Annaeherungs-Marker) vor leading-dot.
    assert csv_loaders.parse_range("ca. .5") == (0.5, 0.5)
    # Freitext-Suffix (Einheit) nach leading-dot - Einheit hat keine
    # Zahlen, damit die Groessenordnung erhalten bleibt.
    assert csv_loaders.parse_range(".5 mm") == (0.5, 0.5)
    assert csv_loaders.parse_range(".05 g") == (0.05, 0.05)
    # Regression-Anker: normale Werte (mit fuehrender Null) bleiben
    # unveraendert, damit die neue Alternante die bestehende Konvention
    # nicht umschreibt.
    assert csv_loaders.parse_range("0.5") == (0.5, 0.5)
    assert csv_loaders.parse_range("0.5-0.7") == (0.5, 0.7)
    # Regression-Anker: leading-Komma (``,5`` alleinstehend) wird NICHT
    # als Dezimal interpretiert - waere in DE-Locale mehrdeutig; US-
    # Konvention kennt kein leading-Komma-Dezimal, und Excel-DE schreibt
    # ``0,5`` mit fuehrender Null. Der String faellt auf die generische
    # Zahl-Suche zurueck, findet die ``5`` als eigenstaendige Ganzzahl.
    assert csv_loaders.parse_range(",5") == (5.0, 5.0)


def test_parse_range_schweizer_apostroph_tausender():
    """Schweizer Tausendertrenner ''' wird ignoriert (CHF-Betraege aus Excel)."""
    # Ohne Fix waere "1'000.00" als (1, 0) gelesen worden.
    assert csv_loaders.parse_range("1'000.00") == (1000.0, 1000.0)
    assert csv_loaders.parse_range("1'500'000.50") == (1500000.5, 1500000.5)
    # Range mit Apostroph auf beiden Seiten
    assert csv_loaders.parse_range("1'000-2'000") == (1000.0, 2000.0)
    # Typografischer Apostroph (U+2019) wird ebenso entfernt
    assert csv_loaders.parse_range("1’000") == (1000.0, 1000.0)


def test_parse_range_einheit_mit_hochgestellter_ascii_ziffer():
    """SI-Einheiten mit ASCII-Superskript-Ersatz (``cm3``/``m2``/``s2``/``cm^3``)
    duerfen die Ziffer im Einheiten-Suffix nicht als Range-Grenze anschleppen.

    In geerbten Sammlungs-Notizen sehr verbreitet, wenn Autor/Tool kein
    Unicode-Superskript zur Verfuegung hatte: Excel-CSV-Exporte ohne
    Unicode-Codepage, Terminal-/Log-Ausgaben (ASCII-only), LaTeX-Roh-Exporte
    ohne ``\\textsuperscript``, alte Sammlungs-DB-Formate mit 7-bit-ASCII
    und Foto-EXIF-Kommentare aus Kameras ohne Unicode-Support schreiben
    ``g/cm³`` als ``g/cm3`` (Ziffer statt ³ U+00B3) bzw. als ``g/cm^3`` mit
    Caret als Superskript-Marker (LaTeX-/Math-Konvention). Bisher fiel die
    Einheits-Ziffer als eigenstaendiger Zahl-Token in nums auf und produzierte
    mineralogisch unsinnige Bereiche:

    * ``"2.65 g/cm3"``  -> (2.65, 3.0)  (3 aus ``cm3`` als Range-hi statt Einheit)
    * ``"2.65 kg/m3"``  -> (2.65, 3.0)  (3 aus ``m3`` als Range-hi)
    * ``"2.65 g/cm^3"`` -> (2.65, 3.0)  (Caret-Superskript-Form, gleiche Fehl-Lese)
    * ``"5-7 g/cm3"``   -> (5.0, 5.0)   (nums=[5,7,3], hi=3<lo=5 -> Kollaps, Range verloren)
    * ``"9.81 m/s2"``   -> (9.81, 9.81) (zufaellig richtig, weil hi<lo-Kollaps)

    Bei der Migration aus ASCII-only-Mineralogie-Notizen entstand damit
    silenter Wert-/Range-Datenverlust: kleine Bereiche mit hi=Ziffer-aus-
    Einheit wurden auf den Center kollabiert (Range verloren), grosse
    Werte mit ni-Ziffer-aus-Einheit > Center wurden als semantisch falscher
    Range gelesen (unsinnige mineralogische Interpretation).

    Der Fix ergaenzt ``_NUM_RE`` um ein negatives Lookbehind ``(?<![A-Za-z^])``,
    das die generische Zahl-Extraktion an Positionen blockiert, an denen die
    Zahl direkt nach einem Buchstaben oder Caret steht - die typische
    Einheiten-Suffix-Signatur. Kollisionsfrei zu scientific notation
    (``1e3``/``1.5e-3`` matchen als Ganz-Token, das Lookbehind pruefft nur
    das fuehrende Digit, nicht das ``e`` innerhalb des Tokens) und zu
    Leading-Dot-Dezimals (``.5`` matcht ueber die ``\\.\\d+``-Alternante,
    Lookbehind gilt vor dem ``.``).

    Bezeichner-Positionen (``Sample3``/``Mineral2``/``B12``) sind eine
    natuerliche Nebenwirkung: dort ist die Zahl Teil des Namens (Sample-
    Nummer, Chargen-Marker, Katalog-Bezeichner), nicht eine Messgroesse -
    dropen ist semantisch korrekt, spiegelt die Strip-Konvention von
    :func:`_strip_bracketed_annotations` auf die Bezeichner-Achse.
    """
    # Dichte-Einheit mit ASCII-Superskript-Ersatz (die haeufigste Notation
    # in ASCII-only-Mineralogie-Kontexten). Vorher: (2.65, 3.0).
    assert csv_loaders.parse_range("2.65 g/cm3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 kg/m3") == (2.65, 2.65)
    # Caret-Superskript-Form (LaTeX-/Math-Konvention). Vorher: (2.65, 3.0).
    assert csv_loaders.parse_range("2.65 g/cm^3") == (2.65, 2.65)
    assert csv_loaders.parse_range("2.65 kg/m^3") == (2.65, 2.65)
    # Range mit Einheit am Ende: die Einheits-Ziffer darf den echten Range
    # weder als hi ueberschreiben noch via hi<lo-Kollaps auf den Center
    # zusammenziehen. Vorher: (5.0, 5.0) via nums=[5,7,3] und hi=3<lo=5.
    assert csv_loaders.parse_range("5-7 g/cm3") == (5.0, 7.0)
    assert csv_loaders.parse_range("5-7 g/cm^3") == (5.0, 7.0)
    # Andere physikalische Einheiten mit ASCII-Superskript (Flaeche, Zeit,
    # Beschleunigung, Volumen). Vorher: alle Faelle brachten via hi<lo-Kollaps
    # zufaellig den Center-Wert doppelt zurueck (aber semantisch: Ziffer
    # aus Einheit war als Range-Grenze gemeint - Silent-Drop der Semantik).
    assert csv_loaders.parse_range("9.81 m/s2") == (9.81, 9.81)
    assert csv_loaders.parse_range("100 mm2") == (100.0, 100.0)
    assert csv_loaders.parse_range("50 cm3") == (50.0, 50.0)
    # Bezeichner-Zahlen (Sample/Chargen-Marker vor dem Wert): die Zahl im
    # Bezeichner-Praefix wird nicht als Range-Grenze fehlgelesen. Vorher:
    # ``"Sample3 test 2.65"`` -> (3.0, 3.0) via hi<lo-Kollaps, Wert 2.65
    # ging verloren. ``"Mineral2 test 5.5"`` -> (2.0, 5.5) semantisch falscher
    # Range 2 bis 5.5.
    assert csv_loaders.parse_range("Sample3 test 2.65") == (2.65, 2.65)
    assert csv_loaders.parse_range("Mineral2 5.5") == (5.5, 5.5)
    # Unicode-Superskript-Form (bereits richtig, Regression-Anker): ``g/cm³``
    # (U+00B3) enthaelt kein ASCII-Digit und war schon vor dem Fix korrekt.
    assert csv_loaders.parse_range("2.65 g/cm³") == (2.65, 2.65)
    assert csv_loaders.parse_range("5-7 g/cm³") == (5.0, 7.0)
    # Regression-Anker: scientific notation bleibt Ganz-Token, weil das
    # Lookbehind nur die erste Ziffer prueft und ``1e3`` als eine Zahl mit
    # ``1`` am Anfang (nach ``\\s``/Start, nicht nach Buchstabe) matcht.
    assert csv_loaders.parse_range("1e3") == (1000.0, 1000.0)
    assert csv_loaders.parse_range("1.5e-3") == (0.0015, 0.0015)
    assert csv_loaders.parse_range(".5e-3") == (0.0005, 0.0005)
    # Regression-Anker: Leading-Dot-Dezimals matchen ueber die ``\\.\\d+``-
    # Alternante, das Lookbehind gilt vor dem ``.`` und laesst den Match zu.
    assert csv_loaders.parse_range(".5") == (0.5, 0.5)
    assert csv_loaders.parse_range(".5 mm") == (0.5, 0.5)
    # Regression-Anker: alle bereits geprueften Notations-Klassen bleiben
    # unveraendert - der Fix beruehrt nur die generische Fallback-Extraktion.
    assert csv_loaders.parse_range("5.5(3)") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("6.5-7.0") == (6.5, 7.0)
    assert csv_loaders.parse_range("1'000.00") == (1000.0, 1000.0)


def test_parse_range_unicode_vulgar_fraktionen():
    """Unicode-Vulgar-Fraktionen (¼/½/¾ und U+2150-U+215E) werden als Wert
    aufgeloest statt still verworfen.

    In mineralogischen Referenz-Tabellen ist die Mohs-Halbschritt-Notation
    ``5½`` der klassische Weg, die Haerte zwischen zwei Ganzzahl-
    Referenzmineralen zu notieren (5½ = zwischen Apatit und Orthoklas,
    6½ = zwischen Orthoklas und Quarz), und ¼/¾/⅛-Notation kommt in
    Groessen-/Gewichts-Fraktionen aeltere Sammler-Karten und in
    imperialen Einheiten (``3¼ inch``) vor. Vor dieser Erweiterung fiel
    ``5½`` auf ``[5]`` und lieferte (5.0, 5.0) statt (5.5, 5.5) - der
    publizierte Halbschritt der Mohs-Skala ging silent verloren und die
    Sortier-/Vergleichs-Reihenfolge stimmte nicht mehr mit der Referenz-
    Tabelle ueberein; standalone ``¼`` lieferte (None, None) - Wert-
    Datenverlust bei jeder Migration aus Word/LibreOffice/PDF-Quellen mit
    typografisch sauber gesetzten Unicode-Fraktionen.
    """
    # Mixed-Form Mohs-Halbschritt (die haeufigste Notation in Referenz-
    # Tabellen; vor dem Fix: (5.0, 5.0), Halbschritt still verloren).
    assert csv_loaders.parse_range("5½") == (5.5, 5.5)
    assert csv_loaders.parse_range("6½") == (6.5, 6.5)
    # Mixed-Form mit Whitespace-Trenner (Print-/Katalog-Form mit typo-
    # grafisch sauberem Halbschritt-Space; auch NBSP und schmales NBSP).
    assert csv_loaders.parse_range("5 ½") == (5.5, 5.5)
    assert csv_loaders.parse_range("5\xa0½") == (5.5, 5.5)
    assert csv_loaders.parse_range("5 ½") == (5.5, 5.5)
    # Mixed-Form mit Viertel- und Dreiviertel-Fraktion (imperiale Einheiten,
    # aeltere Groessen-Notation in Sammler-Karten).
    assert csv_loaders.parse_range("3¼") == (3.25, 3.25)
    assert csv_loaders.parse_range("6¾") == (6.75, 6.75)
    # Mixed-Form mit Achtel-Fraktion (Sieb-Rueckstands-Rasterung, feinere
    # imperiale Notation).
    assert csv_loaders.parse_range("2⅛") == (2.125, 2.125)
    assert csv_loaders.parse_range("1⅜") == (1.375, 1.375)
    assert csv_loaders.parse_range("4⅝") == (4.625, 4.625)
    assert csv_loaders.parse_range("3⅞") == (3.875, 3.875)
    # Standalone-Form (Wert < 1 ohne Ganzzahl-Vorstand); vor dem Fix:
    # (None, None), Wert komplett verloren.
    assert csv_loaders.parse_range("¼") == (0.25, 0.25)
    assert csv_loaders.parse_range("½") == (0.5, 0.5)
    assert csv_loaders.parse_range("¾") == (0.75, 0.75)
    assert csv_loaders.parse_range("⅕") == (0.2, 0.2)
    assert csv_loaders.parse_range("⅖") == (0.4, 0.4)
    assert csv_loaders.parse_range("⅗") == (0.6, 0.6)
    assert csv_loaders.parse_range("⅘") == (0.8, 0.8)
    assert csv_loaders.parse_range("⅛") == (0.125, 0.125)
    assert csv_loaders.parse_range("⅜") == (0.375, 0.375)
    assert csv_loaders.parse_range("⅝") == (0.625, 0.625)
    assert csv_loaders.parse_range("⅞") == (0.875, 0.875)
    assert csv_loaders.parse_range("⅒") == (0.1, 0.1)
    # Periodische Fraktionen (⅓/⅔/⅙/⅚/⅐/⅑) - 12 signifikante Nachkomma-
    # Stellen decken den IEEE-754-double-Praezisionsbereich sauber ab.
    assert csv_loaders.parse_range("⅓") == pytest.approx((1 / 3, 1 / 3), rel=1e-11)
    assert csv_loaders.parse_range("⅔") == pytest.approx((2 / 3, 2 / 3), rel=1e-11)
    assert csv_loaders.parse_range("⅙") == pytest.approx((1 / 6, 1 / 6), rel=1e-11)
    assert csv_loaders.parse_range("⅚") == pytest.approx((5 / 6, 5 / 6), rel=1e-11)
    assert csv_loaders.parse_range("⅐") == pytest.approx((1 / 7, 1 / 7), rel=1e-11)
    assert csv_loaders.parse_range("⅑") == pytest.approx((1 / 9, 1 / 9), rel=1e-11)
    # Range-Formen mit Mixed-Fraktion auf beiden Seiten (Mohs-Bereich
    # zwischen zwei Halbschritt-Werten) - die haeufigste Referenz-Tabellen-
    # Notation fuer variabel-haertige Minerale.
    assert csv_loaders.parse_range("5½-6½") == (5.5, 6.5)
    assert csv_loaders.parse_range("5½ - 6½") == (5.5, 6.5)
    assert csv_loaders.parse_range("5 ½ – 6 ½") == (5.5, 6.5)  # En-Dash Print-Form
    # Range mit Mixed-Fraktion und Ganzzahl gemischt.
    assert csv_loaders.parse_range("5½-7") == (5.5, 7.0)
    assert csv_loaders.parse_range("5-6½") == (5.0, 6.5)
    # Kombination mit Uncertainty-Zweig: die Fraktions-Normalisierung
    # greift *vor* der Uncertainty-Erkennung, damit ``5½ ± 0.3`` als
    # ``5.5 ± 0.3`` korrekt als publizierte Toleranz auf den Halbschritt-
    # Wert auswertet (statt Center 5.0 zu (4.7, 5.3)).
    assert csv_loaders.parse_range("5½ ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5½(3)") == pytest.approx((5.2, 5.8))
    # Kombination mit Trailing-Einheit: die Fraktion wird zum Wert-
    # Vorstand normalisiert, die nachfolgende Einheit bleibt Whitespace-
    # getrennter Wort-Token (kein Match im Zahl-Extraktor).
    assert csv_loaders.parse_range("5½ Mohs") == (5.5, 5.5)
    assert csv_loaders.parse_range("2¾ g/cm³") == (2.75, 2.75)
    assert csv_loaders.parse_range("3¼ inch") == (3.25, 3.25)
    # Kombination mit Klammer-Annotation: die Fraktion wird normalisiert,
    # dann strippt der Klammer-Strip die Annotation vor der Zahl-
    # Extraktion (spiegelt _strip_bracketed_annotations auf die Fraktions-
    # Achse).
    assert csv_loaders.parse_range("5½ (Ref)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5½ [Foto]") == (5.5, 5.5)
    # Kollisions-Schutz gegen SI-Einheiten-Position: ``cm3½`` bleibt
    # unangetastet, weil die 3 durch das _NUM_RE-Lookbehind als Teil der
    # Einheit erkannt wird und das Mixed-Fraktion-Lookbehind zusaetzlich
    # den Letter-Kontext blockiert (die Fraktion darf nicht mit einer
    # Einheiten-Ziffer als vermeintlichem Ganzzahl-Vorstand kombiniert
    # werden). Ohne diesen Schutz wuerde ``cm3½`` zu ``cm3.5`` und der
    # (unerwuenschte) Match wuerde 3.5 als Wert liefern.
    assert csv_loaders.parse_range("cm3½") == (None, None)
    assert csv_loaders.parse_range("m^3½") == (None, None)
    # Kollisions-Schutz gegen Bezeichner-Position: ``Sample½`` bleibt
    # unangetastet (kein Wert, sondern Katalog-Bezeichner mit typografischer
    # Fraktion) - spiegelt die _NUM_RE-Bezeichner-Konvention.
    assert csv_loaders.parse_range("Sample½") == (None, None)
    # Defekte Dezimal-Fraktions-Verkettung: ``5.5½`` ist semantisch
    # unklar (soll das 5.5+0.5=6.0 oder ein Tippfehler sein?), besser
    # unangetastet lassen als kuenstlich zu ``5.5.5`` zu erweitern. Das
    # Fraktions-Lookbehind blockiert nach ``.`` und ``,``, sodass nur die
    # ``5.5`` als Wert-Token extrahiert wird.
    assert csv_loaders.parse_range("5.5½") == (5.5, 5.5)
    # Locale-Konsistenz: DE-Komma-Dezimal am Vorstand ist keine gueltige
    # Mixed-Form; die Fraktion faellt auf Standalone zurueck. ``5,5½``
    # wird zu ``5,50.5`` erweitert - der Zahl-Extraktor liest ``5,5`` als
    # DE-Dezimal und ``0.5`` als zweiten Wert. Range zaehlt nach
    # Zahl-Reihenfolge; Ergebnis (5.5, 5.5) via hi<lo-Kollaps, konsistent
    # mit der Standard-DE-Konvention.
    assert csv_loaders.parse_range("5,5½") == (5.5, 5.5)


def test_parse_range_ascii_mixed_fraktionen():
    """ASCII-Mixed-Fraktion ``\\d+\\s+\\d+/\\d+`` wird als Wert aufgeloest statt still
    als Range-/Ratio-Fragmentliste zerlegt.

    Spiegelt die Unicode-Vulgar-Fraktions-Normalisierung
    (:func:`_normalize_vulgar_fractions`) auf die Plain-ASCII-Achse - typische
    Notation aus Typewriter-/Terminal-Notizen, aus geerbten Textdatei-
    Sammlungen (RTF/TXT ohne Autoformat-Konvertierung zu ½/¼) und aus
    handschriftlich abgeschriebenen Mohs-Haerte-Werten, bei denen der Autor
    den Halbschritt als ``5 1/2`` statt ``5½`` notiert. Vor dieser
    Erweiterung fiel ``5 1/2`` auf ``[5, 1, 2]`` und lieferte via inverted-
    Range-Kollaps ``(5.0, 5.0)`` - der Mohs-Halbschritt ging silent
    verloren; ``5 1/2 - 6 1/2`` lieferte via [5, 1, 2, 6, 1, 2] den
    semantisch falschen Range ``(5.0, 6.0)`` (beide Halbschritte verloren);
    ``5 3/4 Mohs`` lieferte ``(3.0, 4.0)`` (Ganzzahl-Vorstand verworfen).
    """
    # Mohs-Halbschritt (der klassische Anwendungsfall - haeufigste ASCII-
    # Notation in Typewriter-/Plain-Text-Sammler-Notizen; vor dem Fix
    # (5.0, 5.0), Halbschritt still verloren).
    assert csv_loaders.parse_range("5 1/2") == (5.5, 5.5)
    assert csv_loaders.parse_range("6 1/2") == (6.5, 6.5)
    # Viertel-/Dreiviertel-Fraktion (imperiale Groessen-/Gewicht-Angaben,
    # aeltere Sammler-Karten).
    assert csv_loaders.parse_range("3 1/4") == (3.25, 3.25)
    assert csv_loaders.parse_range("6 3/4") == (6.75, 6.75)
    # Achtel-Fraktion (Sieb-Rueckstands-Rasterung, feinere imperiale
    # Notation).
    assert csv_loaders.parse_range("2 1/8") == (2.125, 2.125)
    assert csv_loaders.parse_range("1 3/8") == (1.375, 1.375)
    assert csv_loaders.parse_range("4 5/8") == (4.625, 4.625)
    assert csv_loaders.parse_range("3 7/8") == (3.875, 3.875)
    # Sechzehntel-Fraktion (Bohrdurchmesser-Notation, feine imperiale
    # Rasterung).
    assert csv_loaders.parse_range("5 1/16") == pytest.approx((5.0625, 5.0625))
    assert csv_loaders.parse_range("5 15/16") == (5.9375, 5.9375)
    # Metrische Tenth-Fraktion.
    assert csv_loaders.parse_range("5 3/10") == (5.3, 5.3)
    # Periodische Fraktionen (⅓/⅔/⅙/⅚) - 12 signifikante Nachkomma-Stellen
    # decken den IEEE-754-double-Praezisionsbereich sauber ab (spiegelt die
    # Konvention der Unicode-Vulgar-Fraktions-Normalisierung).
    assert csv_loaders.parse_range("5 1/3") == pytest.approx(
        (5 + 1 / 3, 5 + 1 / 3), rel=1e-11
    )
    assert csv_loaders.parse_range("5 2/3") == pytest.approx(
        (5 + 2 / 3, 5 + 2 / 3), rel=1e-11
    )
    assert csv_loaders.parse_range("5 1/6") == pytest.approx(
        (5 + 1 / 6, 5 + 1 / 6), rel=1e-11
    )
    # Whitespace-Varianten: einfaches Leerzeichen, NBSP (U+00A0), schmales
    # NBSP (U+202F) - typografische Print-Formen mit sauberem Halbschritt-
    # Space.
    assert csv_loaders.parse_range("5\xa01/2") == (5.5, 5.5)
    assert csv_loaders.parse_range("5 1/2") == (5.5, 5.5)
    # Range-Formen mit Mixed-Fraktion auf beiden Seiten (Mohs-Bereich
    # zwischen zwei Halbschritt-Werten) - die haeufigste Referenz-Tabellen-
    # Notation fuer variabel-haertige Minerale in Plain-Text-Quellen.
    assert csv_loaders.parse_range("5 1/2 - 6 1/2") == (5.5, 6.5)
    assert csv_loaders.parse_range("5 1/2-6 1/2") == (5.5, 6.5)
    assert csv_loaders.parse_range("5 1/2 – 6 1/2") == (5.5, 6.5)  # En-Dash
    # Range mit Mixed-Fraktion und Ganzzahl gemischt.
    assert csv_loaders.parse_range("5 1/2 - 7") == (5.5, 7.0)
    assert csv_loaders.parse_range("5 - 6 1/2") == (5.0, 6.5)
    # Kombination mit Uncertainty-Zweig: die Fraktions-Normalisierung
    # greift *vor* der Uncertainty-Erkennung, damit ``5 1/2 ± 0.3`` als
    # ``5.5 ± 0.3`` korrekt als publizierte Toleranz auf den Halbschritt-
    # Wert auswertet (statt Center 5.0 zu (4.7, 5.3)).
    assert csv_loaders.parse_range("5 1/2 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("5 1/2(3)") == pytest.approx((5.2, 5.8))
    # Kombination mit Trailing-Einheit: die Fraktion wird zum Wert-
    # Vorstand normalisiert, die nachfolgende Einheit bleibt Whitespace-
    # getrennter Wort-Token (kein Match im Zahl-Extraktor).
    assert csv_loaders.parse_range("5 1/2 Mohs") == (5.5, 5.5)
    assert csv_loaders.parse_range("2 3/4 g/cm³") == (2.75, 2.75)
    assert csv_loaders.parse_range("3 1/4 inch") == (3.25, 3.25)
    # Kombination mit Klammer-Annotation: die Fraktion wird normalisiert,
    # dann strippt der Klammer-Strip die Annotation vor der Zahl-
    # Extraktion.
    assert csv_loaders.parse_range("5 1/2 (Ref)") == (5.5, 5.5)
    assert csv_loaders.parse_range("5 1/2 [Foto]") == (5.5, 5.5)


def test_parse_range_ascii_mixed_fraktionen_ungueltig():
    """Sicherheitsschranken der ASCII-Mixed-Fraktions-Normalisierung:
    Denominator-Whitelist, Proper-Fraktion-Check, Lookbehind/Lookahead-Schutz.

    ASCII-Mixed-Fraktion ist strukturell mehrdeutig - im Gegensatz zur
    Unicode-Vulgar-Fraktion ``½`` (eindeutiges Wert-Zeichen) kann
    ``1/2`` als Ratio, Datums-Fragment (6/2024) oder Katalog-Nummer
    (Nr. 3 von 42) auftreten. Die Whitelist auf mineralogische/imperiale
    Standard-Nenner {2,3,4,5,6,8,10,16,32} und der Proper-Fraktion-Check
    (Zaehler < Nenner) filtern die semantisch mehrdeutigen Kombinationen.
    """
    # Denominator ausserhalb der Whitelist: Datums-Fragment mit Nenner
    # 1985/2020/2024 (Jahr) faellt auf keine Substitution zurueck -
    # die generische Zahl-Extraktion greift und liefert die einzelnen
    # Tokens. ``5 6/2024`` (Tag/Monat/Jahr-Fragment) -> [5, 6, 2024].
    assert csv_loaders.parse_range("5 1/1985") == (5.0, 1985.0)
    assert csv_loaders.parse_range("5 6/2024") == (5.0, 2024.0)
    # Nenner 12 (Monatszahl) ist bewusst ausserhalb der Whitelist - eine
    # 12tel-Fraktion ist mineralogisch unueblich und die Kollision mit
    # Monats-Notation zu wichtig. ``5 3/12`` bleibt Range-/Fragment-
    # Interpretation [5, 3, 12].
    assert csv_loaders.parse_range("5 1/12") == (5.0, 12.0)
    assert csv_loaders.parse_range("5 3/12") == (5.0, 12.0)
    # Nenner 100 (Katalog-Nummer ``N von 100``) ist bewusst ausserhalb -
    # ``5 42/100`` bleibt Range-/Fragment-Interpretation [5, 42, 100].
    assert csv_loaders.parse_range("5 42/100") == (5.0, 100.0)
    # Improper Fraktion (Zaehler >= Nenner) faellt auf keine Substitution
    # zurueck - ``5 5/2`` waere semantisch mehrdeutig (Ratio 5:2, verkuerzte
    # Range-Notation), besser unangetastet.
    assert csv_loaders.parse_range("5 5/2") == (5.0, 5.0)
    assert csv_loaders.parse_range("5 3/3") == (5.0, 5.0)
    # Kollisions-Schutz gegen Einheiten-Position: der Ganzzahl-Vorstand
    # darf nicht mit einer Einheiten-Ziffer als vermeintlichem Wert-Anker
    # kombiniert werden. ``cm3 1/2`` (SI-Einheit ``cm³`` als ``cm3``-ASCII)
    # bleibt in der Einheiten-Semantik - der Wert-Anker ist die Einheit,
    # nicht der 3-Suffix.
    assert csv_loaders.parse_range("m^3 1/2") == (1.0, 2.0)
    # Kollisions-Schutz gegen greedy-Uebergreifen: eine anschliessende
    # ``/\d``-Sequenz (Datum-Kette ``5 3/4/2020``) blockiert den Match via
    # Lookahead - die Fraktion ist strukturell nicht abgeschlossen und
    # koennte Teil eines Datums-Fragments sein.
    assert csv_loaders.parse_range("5 3/4/2020") == (5.0, 2020.0)
    # Standalone-Fraktion ohne Ganzzahl-Vorstand (``1/2``, ``3/4``) faellt
    # bewusst *nicht* auf 0.5/0.75, sondern bleibt Range-Interpretation
    # [1, 2] / [3, 4] - die Mehrdeutigkeit zwischen Fraktion, Ratio,
    # Einheiten-Nenner und Range ist ohne Ganzzahl-Vorstand zu gross;
    # die Unicode-Standalone-Form ``½``/``¾`` bleibt hier die stabile
    # Alternative, wenn der Autor die Fraktion eindeutig meint.
    assert csv_loaders.parse_range("1/2") == (1.0, 2.0)
    assert csv_loaders.parse_range("3/4") == (3.0, 4.0)
    # Regression-Anker: die bestehende Uncertainty-/Range-Semantik ohne
    # Mixed-Fraktion bleibt unangetastet.
    assert csv_loaders.parse_range("5") == (5.0, 5.0)
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("5.5 ± 0.3") == pytest.approx((5.2, 5.8))
    assert csv_loaders.parse_range("2.65(5)") == pytest.approx((2.60, 2.70))


def test_parse_range_negatives_vorzeichen():
    """Fuehrendes Minus-Vorzeichen wird als negatives Signum an die folgende Zahl
    gebunden, ohne die bestehende Range-Separator-Semantik zu beruehren.

    Vor dem Fix verwarf die generische Zahl-Extraktion (siehe :data:`_NUM_RE`)
    still jedes fuehrende ASCII-Minus-Vorzeichen, weil das Regex nur den
    Ziffernteil einfing:

    * ``"-5.5"``      -> ``[5.5]``       -> (5.5, 5.5)    (Vorzeichen verloren)
    * ``"-10 - -5"``  -> ``[10, 5]``     -> (10.0, 10.0)  (beide Vorzeichen verloren + inverted-Kollaps)
    * ``"-10 - 5"``   -> ``[10, 5]``     -> (10.0, 10.0)  (linkes Vorzeichen verloren + inverted-Kollaps)
    * ``"ca. -5.5"``  -> ``[5.5]``       -> (5.5, 5.5)    (Vorzeichen verloren nach Freitext-Praefix)
    * ``"-10,5–-5,5"``-> ``[10.5, 5.5]`` -> (10.5, 10.5)  (DE-Komma + en-dash, beide Vorzeichen verloren)

    Bei der Migration aus Cryo-Mineralogie-Notizen (Frost-/Eis-Kristall-
    Sammlungen mit Temperatur-Bereichen unter 0 °C), Bergbau-/Tektonik-
    Tiefen-Berichten (negative Meereshoehe als Kristall-Fundort), Isotopen-
    Fraktionierungs-Daten (δ¹³C, δ¹⁸O in ‰ - typisch negativ fuer viele
    Karbonate/Silikate), thermischen Ausdehnungs-Koeffizienten (β < 0 bei
    einigen Kristall-Klassen wie Quarz alpha-beta-Uebergang) oder aus
    Vergleichs-Deltas (``Δn`` in Doppelbrechungs-Tabellen) entstand damit
    silenter Vorzeichen-Datenverlust auf jedem Numeric-Feld, das Nullpunkt-
    negative Werte tragen kann. Im schlimmsten Fall (symmetrischer negativer
    Range) wurden die absoluten Werte gespiegelt (10.0 statt -10.0) - eine
    Vorzeichen-Inversion, die mineralogisch/physikalisch nicht auffaellt,
    aber die publizierte Temperatur- oder Isotopen-Achse komplett verwirft.

    Der Fix erweitert ``_NUM_RE`` um eine optionale Sign-Alternante
    ``(?:(?<![\\d.])-)?`` vor dem Digit-Teil - das Minus wird nur an
    Positionen als Vorzeichen gebunden, an denen das VOR dem Minus stehende
    Zeichen weder Digit noch Dezimalpunkt ist. Dadurch bleibt die bestehende
    Range-Separator-Semantik unangetastet: in ``"5-7"`` und ``"5.5-7.0"``
    steht ein Digit unmittelbar vor dem Minus, der Sign-Match blockt via
    ``(?<![\\d.])`` und der Hyphen bleibt Range-Trenner. Nur wenn das
    Zeichen vor dem Minus ein Whitespace, Start-of-String, Klammer-Rand,
    anderer Dash-Typ (en-/em-dash) oder anderes Non-Digit-Separator-Zeichen
    (``=``, ``:``, ``/``, ``&``, ``,``) ist, wird der Minus als Vorzeichen
    interpretiert - genau die Positionen, an denen ein Minus semantisch
    kein Range-Separator sein kann.
    """
    # Einzelwert negativ - klassischer Cryo-Temperatur-Wert oder Isotopen-
    # Fraktionierung.
    assert csv_loaders.parse_range("-5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-10") == (-10.0, -10.0)
    assert csv_loaders.parse_range("-0.5") == (-0.5, -0.5)
    # Symmetrischer negativer Range mit ASCII-Hyphen als Range-Separator
    # zwischen zwei negativen Bounds - typisch fuer Cryo-Temperatur-Fenster
    # ("-10 - -5 °C") oder Isotopen-Delta-Bereiche.
    assert csv_loaders.parse_range("-10 - -5") == (-10.0, -5.0)
    assert csv_loaders.parse_range("-10--5") == (-10.0, -5.0)
    # En-dash (U+2013) und em-dash (U+2014) als Range-Separator zwischen zwei
    # negativen Bounds - typografisch sauber gesetzte Print-/PDF-Publikationen
    # verwenden en-dash statt ASCII-Hyphen fuer Bereichs-Notation.
    assert csv_loaders.parse_range("-10 – -5") == (-10.0, -5.0)
    assert csv_loaders.parse_range("-10 — -5") == (-10.0, -5.0)
    # Vorzeichen-gemischter Range (negativ zu positiv) - typisch fuer
    # Temperatur-Fenster ueber den Nullpunkt hinweg ("-10 bis +5 °C").
    assert csv_loaders.parse_range("-10 - 5") == (-10.0, 5.0)
    assert csv_loaders.parse_range("-10–5") == (-10.0, 5.0)
    # Freitext-Praefix (Annaeherungs-Marker) vor negativem Wert - der Wert
    # muss trotz Praefix sein Vorzeichen behalten.
    assert csv_loaders.parse_range("ca. -5.5") == (-5.5, -5.5)
    assert csv_loaders.parse_range("circa -5.5") == (-5.5, -5.5)
    # DE-Komma-Dezimal mit negativem Vorzeichen - deutsche Publikationen und
    # Excel-DE-Auto-Format schreiben ``-2,65`` mit Komma-Dezimal.
    assert csv_loaders.parse_range("-2,65") == (-2.65, -2.65)
    assert csv_loaders.parse_range("-10,5 - -5,5") == (-10.5, -5.5)
    assert csv_loaders.parse_range("-10,5–-5,5") == (-10.5, -5.5)
    # Trailing-Einheit nach negativem Wert - die Einheit hat keine Zahlen,
    # damit die Groessenordnung erhalten bleibt.
    assert csv_loaders.parse_range("-5.5 °C") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-10 - -5 °C") == (-10.0, -5.0)
    # Scientific notation mit negativem Vorzeichen an der Mantisse - typisch
    # fuer sub-Einheiten-Groessen im negativen Bereich (thermische
    # Ausdehnungs-Koeffizienten, Absorptions-Deltas).
    assert csv_loaders.parse_range("-1.5e-3") == (-0.0015, -0.0015)
    assert csv_loaders.parse_range("-1e3") == (-1000.0, -1000.0)
    # Leading-Dot-Dezimal mit negativem Vorzeichen (``-.5`` = -0.5, US-
    # Konvention "no leading zero" mit Minus-Praefix).
    assert csv_loaders.parse_range("-.5") == (-0.5, -0.5)
    assert csv_loaders.parse_range("-.5-.7") == (-0.5, 0.7)
    # Negativer Wert mit Uncertainty-Langform (``-1.5 ± 0.3``) - der
    # bestehende _PLUS_MINUS_UNCERTAINTY-Zweig faengt den Fall bereits, hier
    # als Regression-Anker fuer die Prioritaets-Reihenfolge (Uncertainty vor
    # generischer Zahl-Extraktion).
    assert csv_loaders.parse_range("-1.5 ± 0.3") == pytest.approx((-1.8, -1.2))
    # Regression-Anker: die bestehende Range-Separator-Semantik bleibt
    # unveraendert - in ``"5-7"`` steht Digit vor Minus, der Sign-Match
    # blockt und der Hyphen bleibt Range-Trenner.
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)
    assert csv_loaders.parse_range("5.5-7.0") == (5.5, 7.0)
    assert csv_loaders.parse_range("5") == (5.0, 5.0)
    assert csv_loaders.parse_range("5.5") == (5.5, 5.5)
    # Regression-Anker: Leading-Dot-Dezimal ohne Vorzeichen bleibt
    # unveraendert.
    assert csv_loaders.parse_range(".5") == (0.5, 0.5)
    assert csv_loaders.parse_range(".5-.7") == (0.5, 0.7)
    # Regression-Anker: Freitext-Praefix ohne Vorzeichen bleibt unveraendert
    # (der optional-sign-Zweig blockt korrekt bei Nicht-Minus-Praefix).
    assert csv_loaders.parse_range("ca. 5.5") == (5.5, 5.5)
    assert csv_loaders.parse_range("ca. 2.65") == (2.65, 2.65)
    # Regression-Anker: scientific notation ohne Vorzeichen bleibt
    # unveraendert (der Exponent-``-`` bleibt Teil des Ganz-Tokens).
    assert csv_loaders.parse_range("1e-3") == (0.001, 0.001)
    assert csv_loaders.parse_range("1.5e-3") == (0.0015, 0.0015)
    # Regression-Anker: SI-Einheit-Suffix mit ASCII-Superskript (``cm3``,
    # ``m^3``) blockt die Ziffer im Suffix - Buchstabe/Caret vor Digit
    # trifft den bestehenden ``(?<![A-Za-z^])``-Lookbehind, das neue
    # Sign-Lookbehind ist eine unabhaengige Schicht.
    assert csv_loaders.parse_range("2.65 g/cm3") == (2.65, 2.65)
    assert csv_loaders.parse_range("-2.65 g/cm3") == (-2.65, -2.65)
    # Regression-Anker: inverted-Range-Kollaps bleibt aktiv, wenn der
    # negative hi arithmetisch kleiner als der negative lo ist
    # (Tippfehler-Robustheit spiegelt die positive Konvention).
    assert csv_loaders.parse_range("-5 - -10") == (-5.0, -5.0)
    # Regression-Anker: Klammer-Annotation nach negativem Wert wird
    # gestrippt und die Annotations-Zahl darf nicht als Range-Grenze
    # fehlgelesen werden.
    assert csv_loaders.parse_range("-5.5 (Ref 42)") == (-5.5, -5.5)
    assert csv_loaders.parse_range("-10 - -5 [Nr. 42]") == (-10.0, -5.0)


def test_load_v1():
    data = csv_loaders.load_v1(CSV_DIR / "Stonebock__stoneboock_daten_objekte_1-42.csv")
    assert "OBJ_0001" in data
    o1 = data["OBJ_0001"]
    assert "Jaspis" in o1["Mineral_Primaer"]
    assert "Rötlich" in o1["notizen"]


def test_load_v2():
    data = csv_loaders.load_v2(CSV_DIR / "Stonebock__stoneboock_daten_v2_objekte_1-42.csv")
    o1 = data["OBJ_0001"]
    assert o1["Mohs_Haerte_min"] == 6.5
    assert o1["Mohs_Haerte_max"] == 7.0
    assert o1["Confidence_Prozent"] == 80
    assert o1["Varietaet"] == "Jaspis"


def test_load_standard_roundtrip(tmp_path):
    """export_csv → load_standard ergibt identische Werte für nichtleere Zellen."""
    from stonebook.db.database import connect
    from stonebook.export.csv_export import export_csv
    from stonebook.migration.csv_loaders import load_standard
    from stonebook.migration.migrate import migrate

    db_file = tmp_path / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    csv_path = tmp_path / "export.csv"
    export_csv(connect(db_file), csv_path)
    data = load_standard(csv_path)
    assert "OBJ_0043" in data
    o43 = data["OBJ_0043"]
    assert "Quarz" in o43["Mineral_Primaer"]
    assert o43["Gewicht_g"] == 41.0
    assert o43["Mohs_Haerte_min"] == 7.0
    assert o43.get("status") == "aktiv"


def test_load_standard_ignoriert_ungueltige_datumswerte(tmp_path):
    csv_path = tmp_path / "x.csv"
    csv_path.write_text(
        "ID,Funddatum,Mineral_Primaer\nOBJ_0001,32.13.2024,Quarz\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    o1 = data["OBJ_0001"]
    assert o1["Mineral_Primaer"] == "Quarz"
    assert "Funddatum" not in o1  # ungueltiges Datum wird verworfen


def test_load_standard_semicolon_delimiter(tmp_path):
    """Excel-DE-Export mit ; als Trennzeichen wird automatisch erkannt."""
    csv_path = tmp_path / "semi.csv"
    csv_path.write_text(
        "ID;Mineral_Primaer;Gewicht_g\nOBJ_0001;Quarz;12.5\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Gewicht_g"] == 12.5


def test_load_standard_tab_delimiter(tmp_path):
    csv_path = tmp_path / "tab.tsv"
    csv_path.write_text(
        "ID\tMineral_Primaer\tGewicht_g\nOBJ_0001\tCalcit\t7\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Calcit"
    assert data["OBJ_0001"]["Gewicht_g"] == 7.0


def test_load_standard_header_whitespace(tmp_path):
    """Spaltennamen mit fuehrenden/abschliessenden Leerzeichen werden getrimmt."""
    csv_path = tmp_path / "ws.csv"
    csv_path.write_text(
        " ID , Mineral_Primaer ,Gewicht_g \nOBJ_0001,Quarz,5\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Gewicht_g"] == 5.0


def test_load_standard_multiline_quoted_zelle(tmp_path):
    """Eingebettete Newlines in quoted Feldern (lange notizen) bleiben erhalten."""
    csv_path = tmp_path / "ml.csv"
    # notizen mit eingebettetem \n in Anfuehrungszeichen (z.B. Excel-Export
    # langer Freitext-Notizen mit Zeilenumbruechen)
    csv_path.write_text(
        'ID,Mineral_Primaer,notizen\n'
        'OBJ_0001,Quarz,"Erste Zeile\nZweite Zeile\nDritte Zeile"\n'
        'OBJ_0002,Calcit,"Einzelnotiz"\n',
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    # Newlines im Freitext bleiben erhalten (sonst waere die Notiz zerfallen)
    assert data["OBJ_0001"]["notizen"] == "Erste Zeile\nZweite Zeile\nDritte Zeile"
    assert data["OBJ_0002"]["notizen"] == "Einzelnotiz"


def test_load_standard_multiline_mit_semicolon_delimiter(tmp_path):
    """Multiline-Zellen bleiben auch bei ;-Delimiter (Excel-DE) erhalten."""
    csv_path = tmp_path / "ml_de.csv"
    csv_path.write_text(
        'ID;Mineral_Primaer;notizen\n'
        'OBJ_0001;Quarz;"Zeile A\nZeile B"\n',
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["notizen"] == "Zeile A\nZeile B"


def test_load_standard_skip_blank_rows(tmp_path):
    csv_path = tmp_path / "blank.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer\n"
        "OBJ_0001,Quarz\n"
        ",\n"
        "\n"
        "OBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}


def test_load_standard_empty_file(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")
    from stonebook.migration.csv_loaders import load_standard
    assert load_standard(csv_path) == {}


def test_load_standard_bom_und_crlf(tmp_path):
    """BOM + Windows-Zeilenenden werden korrekt verarbeitet."""
    csv_path = tmp_path / "bom.csv"
    csv_path.write_bytes(
        b"\xef\xbb\xbfID,Mineral_Primaer\r\nOBJ_0001,Quarz\r\n"
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"


def test_load_standard_cp1252_fallback(tmp_path):
    """Excel-Export auf alten Windows-Systemen ist oft cp1252; muss lesbar bleiben."""
    csv_path = tmp_path / "win.csv"
    # Umlaute in Daten + Header werden als cp1252 geschrieben (kein BOM, kein UTF-8)
    csv_path.write_bytes(
        "ID,Mineral_Primaer,Fundort\nOBJ_0001,Quarz,Zürich\n".encode("cp1252")
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Fundort"] == "Zürich"


def test_load_standard_latin1_fallback(tmp_path):
    csv_path = tmp_path / "latin.csv"
    csv_path.write_bytes(
        "ID,Mineral_Primaer\nOBJ_0001,Calcít\n".encode("latin-1")
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Calcít"


def test_load_standard_utf16_le_bom(tmp_path):
    """Excel 'Unicode Text'-Export ist UTF-16-LE mit BOM und Tab-Separator.

    Ohne BOM-Erkennung fiele die Datei aktuell durch utf-8-sig/utf-8 (beide
    scheitern an ``\\xff`` als ungueltigem Startbyte) auf cp1252 zurueck und
    wuerde als Doppelbyte-Muell dekodiert (jeder ASCII-Buchstabe als
    ``X\\x00``, ID-Header zerfaellt). Mit BOM-Pruefung wird der korrekte
    UTF-16-Decoder benutzt; Umlaute bleiben intakt.
    """
    csv_path = tmp_path / "u16le.csv"
    csv_path.write_bytes(
        ("ID\tMineral_Primaer\tFundort\n"
         "OBJ_0001\tQuarz\tZürich\n"
         "OBJ_0002\tCalcit\tDavos\n").encode("utf-16")  # encode() addiert BOM \xff\xfe
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Fundort"] == "Zürich"
    assert data["OBJ_0002"]["Mineral_Primaer"] == "Calcit"


def test_load_standard_utf16_be_bom(tmp_path):
    """UTF-16-BE mit BOM (selten, aber spec-konform) wird ebenfalls erkannt."""
    csv_path = tmp_path / "u16be.csv"
    # encode('utf-16-be') addiert KEIN BOM; BOM \xfe\xff manuell voranstellen,
    # damit die BOM-Pruefung in _read_text_any_encoding greift
    csv_path.write_bytes(
        b"\xfe\xff" + (
            "ID,Mineral_Primaer\nOBJ_0001,Quarz\n"
        ).encode("utf-16-be")
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"


def test_load_standard_utf16_ohne_bom_faellt_auf_cp1252_zurueck(tmp_path):
    """Ohne BOM keine stille UTF-16-Annahme: BOM-loses UTF-16 ist von ASCII-
    Daten in cp1252 nicht eindeutig unterscheidbar; bestehende Fallback-Logik
    bleibt unveraendert. Eine reine ASCII-CSV ohne BOM funktioniert weiter.
    """
    csv_path = tmp_path / "ascii.csv"
    csv_path.write_bytes(b"ID,Mineral_Primaer\nOBJ_0001,Quarz\n")
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"


def test_load_standard_quoted_multiline(tmp_path):
    """Zellen mit eingebetteten Zeilenumbruechen (quoted) werden korrekt geparst."""
    csv_path = tmp_path / "multi.csv"
    csv_path.write_text(
        'ID,Mineral_Primaer,notizen\n'
        'OBJ_0001,Quarz,"Zeile 1\nZeile 2"\n'
        'OBJ_0002,Calcit,einzeilig\n',
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002"}
    assert "Zeile 1" in data["OBJ_0001"]["notizen"]
    assert "Zeile 2" in data["OBJ_0001"]["notizen"]
    assert data["OBJ_0002"]["notizen"] == "einzeilig"


def test_load_standard_obj_id_alias(tmp_path):
    """JSON-/DB-Konvention 'obj_id' wird als ID-Spalte akzeptiert."""
    csv_path = tmp_path / "json_like.csv"
    csv_path.write_text(
        "obj_id,Mineral_Primaer,Gewicht_g\nOBJ_0001,Quarz,12.5\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Mineral_Primaer"] == "Quarz"
    assert data["OBJ_0001"]["Gewicht_g"] == 12.5


def test_find_duplicate_ids_standard(tmp_path):
    """Doppelte IDs in derselben CSV werden erkannt (spiegelt load_standard-Dict-Overwrite).

    load_standard(dict[str, dict]) ueberschreibt fruehere Zeilen kommentarlos,
    wenn dieselbe ID mehrfach als Zeile vorkommt (typischer Datenverlust-Fall
    bei nutzer-editierten CSVs). find_duplicate_ids liefert die betroffenen
    IDs zurueck, ohne die Loesch-Semantik selbst zu aendern.
    """
    from stonebook.migration.csv_loaders import find_duplicate_ids, load_standard
    csv_path = tmp_path / "duplikate.csv"
    csv_path.write_text(
        "ID,Name\n"
        "OBJ_0001,Erste Zeile\n"
        "OBJ_0002,Zwischen\n"
        "OBJ_0001,Zweite Zeile\n"
        "OBJ_0003,Andere\n"
        "OBJ_0001,Dritte Zeile\n",
        encoding="utf-8",
    )
    # find_duplicate_ids meldet OBJ_0001 genau einmal, in der Reihenfolge des
    # zweiten Vorkommens (deterministisch fuer Reporter/Log-Ausgabe).
    assert find_duplicate_ids(csv_path) == ["OBJ_0001"]
    # load_standard behaelt die letzte Zeile (dict-Overwrite-Semantik).
    data = load_standard(csv_path)
    assert data["OBJ_0001"]["Name"] == "Dritte Zeile"
    assert data["OBJ_0002"]["Name"] == "Zwischen"
    assert data["OBJ_0003"]["Name"] == "Andere"


def test_find_duplicate_ids_normalisiert_alternativ_formen(tmp_path):
    """obj_1 und OBJ_0001 werden als dieselbe ID erkannt (normalize_id-Semantik).

    Spiegelt load_standard, das ueber normalize_id gleichermassen kompaktes
    ``obj_1`` und ``OBJ_0001`` auf denselben Schluessel abbildet - ohne
    Normalisierung wuerde ein user-editierter Mix beider Formen fuer dasselbe
    Stueck nicht als Duplikat auffallen.
    """
    from stonebook.migration.csv_loaders import find_duplicate_ids
    csv_path = tmp_path / "mixid.csv"
    csv_path.write_text(
        "ID,Name\nOBJ_0001,Erste\nobj_1,Zweite\n",
        encoding="utf-8",
    )
    assert find_duplicate_ids(csv_path) == ["OBJ_0001"]


def test_find_duplicate_ids_leer_und_ohne_duplikate(tmp_path):
    """Leere CSV und CSV ohne Duplikate liefern eine leere Liste."""
    from stonebook.migration.csv_loaders import find_duplicate_ids
    leer = tmp_path / "leer.csv"
    leer.write_text("ID,Name\n", encoding="utf-8")
    assert find_duplicate_ids(leer) == []
    ohne = tmp_path / "ohne.csv"
    ohne.write_text(
        "ID,Name\nOBJ_0001,A\nOBJ_0002,B\nOBJ_0003,C\n",
        encoding="utf-8",
    )
    assert find_duplicate_ids(ohne) == []


def test_find_duplicate_ids_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError (spiegelt load_standard).

    Ohne diesen Fehler wuerde ein falsch adressierter Dateipfad (z.B. v1-CSV
    mit Header Name,Mineralart) hier stille als "keine Duplikate" durchgehen,
    obwohl load_standard denselben Input mit ValueError abbricht - beide
    Funktionen sollen zur gleichen Format-Regel stehen.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_duplicate_ids
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text("Name,Mineralart\nFoo,Quarz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_duplicate_ids(csv_path)


def test_find_duplicate_ids_leere_datei_ohne_id_spalte_ist_ok(tmp_path):
    """Leere CSV (nur Header) ohne ID-Spalte loest keinen Fehler aus (spiegelt load_standard)."""
    from stonebook.migration.csv_loaders import find_duplicate_ids
    csv_path = tmp_path / "leerohne.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    assert find_duplicate_ids(csv_path) == []


def test_find_rows_without_id_standard(tmp_path):
    """Zeilen mit leerer oder unlesbarer ID-Spalte werden gemeldet.

    load_standard verwirft Zeilen ohne normalisierbare ID kommentarlos - ein
    user-editierter Tippfehler (leer, ``??``, ``TODO``) laesst die Zeile silent
    verschwinden, obwohl uebrige Spalten voll gepflegt sein koennen. Der Report
    liefert 1-basierte Zeilennummern ueber die Datenzeilen (Header zaehlt nicht),
    komplett leere Zeilen zaehlen nicht (die filtert der Reader).
    """
    from stonebook.migration.csv_loaders import find_rows_without_id, load_standard
    csv_path = tmp_path / "ohne_id.csv"
    csv_path.write_text(
        "ID,Name\n"
        "OBJ_0001,Erste\n"
        ",Zeile ohne ID\n"
        "OBJ_0002,Zweite\n"
        "??,Kaputte ID\n"
        "OBJ_0003,Dritte\n",
        encoding="utf-8",
    )
    assert find_rows_without_id(csv_path) == [2, 4]
    # load_standard behaelt nur die drei gueltigen IDs (dict-Semantik).
    data = load_standard(csv_path)
    assert set(data.keys()) == {"OBJ_0001", "OBJ_0002", "OBJ_0003"}


def test_find_rows_without_id_leer_und_alles_ok(tmp_path):
    """Leere CSV und CSV ohne unlesbare IDs liefern eine leere Liste."""
    from stonebook.migration.csv_loaders import find_rows_without_id
    leer = tmp_path / "leer.csv"
    leer.write_text("ID,Name\n", encoding="utf-8")
    assert find_rows_without_id(leer) == []
    ok = tmp_path / "ok.csv"
    ok.write_text(
        "ID,Name\nOBJ_0001,A\nOBJ_0002,B\n",
        encoding="utf-8",
    )
    assert find_rows_without_id(ok) == []


def test_find_rows_without_id_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError (spiegelt load_standard)."""
    import pytest
    from stonebook.migration.csv_loaders import find_rows_without_id
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text("Name,Mineralart\nFoo,Quarz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_without_id(csv_path)


def test_find_rows_without_id_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID`` - beide werden erkannt."""
    from stonebook.migration.csv_loaders import find_rows_without_id
    csv_path = tmp_path / "objid.csv"
    csv_path.write_text(
        "obj_id,Name\nOBJ_0001,Erste\n,Zeile ohne ID\n",
        encoding="utf-8",
    )
    assert find_rows_without_id(csv_path) == [2]


def test_find_rows_with_invalid_funddatum_standard(tmp_path):
    """Zeilen mit einem nicht parsbaren Funddatum werden gemeldet (Feld-Level-Silent-Drop).

    _convert_standard uebernimmt Funddatum nur, wenn parse_iso_date den Wert
    erfolgreich mappen kann - Tippfehler (32.13.2024, Monat 13) oder unstruk-
    turierter Freitext ("Sommer 84" ohne Vollzahl-Jahr) werden kommentarlos
    verworfen, die Zeile bleibt aber sonst intakt. Der Report liefert
    (Zeilennummer, Roh-Wert)-Paare, damit der User den konkreten Tippfehler
    ohne Zusatz-Recherche findet.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_funddatum,
        load_standard,
    )
    csv_path = tmp_path / "funddatum.csv"
    csv_path.write_text(
        "ID,Funddatum,Mineral_Primaer\n"
        "OBJ_0001,2024-06-13,Quarz\n"
        "OBJ_0002,32.13.2024,Calcit\n"
        "OBJ_0003,1985,Amethyst\n"
        "OBJ_0004,Sommer 84,Turmalin\n"
        "OBJ_0005,,Ohne\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == [
        (2, "32.13.2024"),
        (4, "Sommer 84"),
    ]
    # load_standard behaelt die Zeilen, aber ohne das kaputte Funddatum-Feld.
    data = load_standard(csv_path)
    assert data["OBJ_0002"]["Mineral_Primaer"] == "Calcit"
    assert "Funddatum" not in data["OBJ_0002"]
    assert "Funddatum" not in data["OBJ_0004"]
    # Gueltige Datums-Werte bleiben unangetastet.
    assert data["OBJ_0001"]["Funddatum"] == "2024-06-13"
    assert data["OBJ_0003"]["Funddatum"] == "1985-01-01"


def test_find_rows_with_invalid_funddatum_ignoriert_leer_und_no_data_marker(tmp_path):
    """Leere Werte und "keine Angabe"-Marker (k.a./n/a/unbekannt/? etc.) zaehlen
    NICHT als invalid.

    parse_iso_date behandelt die Marker semantisch als "User sagt: kein Datum"
    (siehe DATE_NO_DATA_MARKERS). Da ist nichts verloren gegangen; die Zeile
    darf nicht als silent-data-loss-Fund gemeldet werden, sonst wuerde der
    Report bei ausdruecklich "no data"-Eingaben Rauschen erzeugen.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "marker.csv"
    csv_path.write_text(
        "ID,Funddatum,Mineral_Primaer\n"
        "OBJ_0001,,Leer\n"
        "OBJ_0002,   ,Whitespace\n"
        "OBJ_0003,k.a.,Marker DE\n"
        "OBJ_0004,n/a,Marker EN\n"
        "OBJ_0005,unbekannt,Wort-Marker\n"
        "OBJ_0006,?,Fragezeichen\n"
        "OBJ_0007,-,Bindestrich\n"
        "OBJ_0008,K.A.,Marker mit Grossschreibung\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == []


def test_find_rows_with_invalid_funddatum_ohne_spalte_ist_leer(tmp_path):
    """Fehlt die Funddatum-Spalte komplett, wird [] zurueckgegeben.

    Kein Datenverlust moeglich, wenn das Feld gar nicht Teil der CSV ist -
    der Report darf nicht faelschlich "0 Zeilen" statt "gar nicht anwendbar"
    signalisieren, sondern liefert schlicht leere Liste.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "kein_funddatum.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\nOBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == []


def test_find_rows_with_invalid_funddatum_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID`` - beide werden erkannt.

    Spiegelt find_rows_without_id/find_duplicate_ids: das ID-Spalten-Aliasing
    ist eine Symmetrie-Regel ueber alle Pre-Scanner, kein Extra-Feature dieses
    einen Checks.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "objid_datum.csv"
    csv_path.write_text(
        "obj_id,Funddatum\nOBJ_0001,2024-06-13\nOBJ_0002,kaputt\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_funddatum(csv_path) == [(2, "kaputt")]


def test_find_rows_with_invalid_funddatum_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError.

    Spiegelt find_duplicate_ids/find_rows_without_id/load_standard: alle vier
    stehen zur gleichen Format-Regel und lehnen v1/v2-Historik-CSVs sichtbar
    ab, statt stille "0 Funde" zu melden.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_with_invalid_funddatum(csv_path)


def test_find_rows_with_invalid_funddatum_leere_datei_ohne_id_spalte_ist_ok(tmp_path):
    """Leere CSV (nur Header) ohne ID-Spalte loest keinen Fehler aus.

    Spiegelt find_duplicate_ids/find_rows_without_id: ohne Zeilen kann es
    keinen Datenverlust geben, unabhaengig vom Header-Format.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_funddatum
    csv_path = tmp_path / "leerohne.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    assert find_rows_with_invalid_funddatum(csv_path) == []


def test_find_rows_with_invalid_numeric_field_standard(tmp_path):
    """Feld-Level-Silent-Drop-Pendant auf der numerischen Achse.

    ``_num("sehr schwer")`` liefert None, ``_convert_standard`` uebergibt
    ``(True, None)``, ``import_csv`` filtert das Feld via ``is_empty(None)``
    aus dem Update-Dict - der Roh-Text ist verloren, ohne dass der Report
    ihn sichtbar macht. Diese Funktion pre-scannt die CSV und liefert die
    (Zeile, Roh-Wert)-Paare zur sichtbaren Meldung, damit der User den
    konkreten Tippfehler direkt findet. Spiegelt den Standard-Pfad von
    find_rows_with_invalid_funddatum auf die Gewicht-Achse.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_field,
        load_standard,
    )
    csv_path = tmp_path / "gewicht.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Mineral_Primaer\n"
        "OBJ_0001,42.5,Quarz\n"
        "OBJ_0002,sehr schwer,Calcit\n"
        "OBJ_0003,150,Amethyst\n"
        "OBJ_0004,teuer,Turmalin\n"
        "OBJ_0005,,Ohne\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g") == [
        (2, "sehr schwer"),
        (4, "teuer"),
    ]
    # load_standard behaelt die Zeilen, aber ohne das kaputte Gewicht_g-Feld
    # (_num->None, is_empty(None)->True, das Feld verschwindet aus fields dict).
    data = load_standard(csv_path)
    assert data["OBJ_0002"]["Mineral_Primaer"] == "Calcit"
    assert data["OBJ_0002"].get("Gewicht_g") is None
    assert data["OBJ_0004"].get("Gewicht_g") is None
    # Gueltige numerische Werte bleiben unangetastet.
    assert data["OBJ_0001"]["Gewicht_g"] == 42.5
    assert data["OBJ_0003"]["Gewicht_g"] == 150.0


def test_find_rows_with_invalid_numeric_field_akzeptiert_einheiten(tmp_path):
    """Werte mit Einheit (``42 g``, ``ca. 500 CHF``) sind NICHT invalid.

    ``_num`` extrahiert das Zahl-Token, ``_convert_standard`` uebernimmt den
    Wert - die Einheiten-Annotation geht verloren, ist aber semantisch
    redundant (die Spalte kodiert die Einheit im Namen: ``Gewicht_g`` ist
    immer g). Erst wenn kein Zahl-Token gefunden wird (``sehr schwer``),
    ist der Wert-Anteil verloren und die Zeile wird gemeldet. Ohne diesen
    Test wuerde eine spaetere Regex-Verschaerfung von ``_num`` (z.B. Einheit
    zwingend abschneiden vor der Zahl-Extraktion) den Report mit Rauschen
    fuellen.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "einheiten.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Wert_CHF_roh\n"
        "OBJ_0001,42 g,ca. 500 CHF\n"
        "OBJ_0002,150 gram,750.00 CHF\n"
        "OBJ_0003,ca. 42.5,1'500.00\n",  # Schweizer Tausender
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Gewicht_g") == []
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Wert_CHF_roh") == []


def test_find_rows_with_invalid_numeric_field_ignoriert_leer_und_no_data_marker(tmp_path):
    """Leere Werte und "keine Angabe"-Marker zaehlen NICHT als invalid.

    Spiegelt die Marker-Ignoranz von find_rows_with_invalid_funddatum: die
    :data:`DATE_NO_DATA_MARKERS`-Menge ist single source of truth ueber alle
    Feld-Achsen (Datum, numerisch). Wenn der User explizit ``k.a.`` in eine
    Gewicht-Zelle schreibt, ist das "kein Wert verfuegbar" - da ist nichts
    verloren gegangen, und der Report darf keine Rauschmeldung erzeugen.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "marker_num.csv"
    csv_path.write_text(
        "ID,Gewicht_g\n"
        "OBJ_0001,\n"
        "OBJ_0002,   \n"
        "OBJ_0003,k.a.\n"
        "OBJ_0004,n/a\n"
        "OBJ_0005,unbekannt\n"
        "OBJ_0006,?\n"
        "OBJ_0007,-\n"
        "OBJ_0008,K.A.\n",  # Grossschreibung
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g") == []


def test_find_rows_with_invalid_numeric_field_ohne_spalte_ist_leer(tmp_path):
    """Fehlt die genannte Spalte komplett im File, wird ``[]`` zurueckgegeben.

    Spiegelt find_rows_with_invalid_funddatum: kein Datenverlust moeglich,
    wenn das Feld gar nicht Teil der CSV ist - der Report darf nicht
    faelschlich "0 Zeilen" statt "gar nicht anwendbar" signalisieren.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "kein_gewicht.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer\nOBJ_0001,Quarz\nOBJ_0002,Calcit\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g") == []


def test_find_rows_with_invalid_numeric_field_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID`` - beide werden erkannt.

    Spiegelt die ID-Spalten-Aliasing-Regel der uebrigen Pre-Scanner:
    das Alias gilt fuer alle Silent-Drop-Detektoren einheitlich.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "objid_num.csv"
    csv_path.write_text(
        "obj_id,Wert_CHF_roh\nOBJ_0001,42.5\nOBJ_0002,teuer\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Wert_CHF_roh") == [(2, "teuer")]


def test_find_rows_with_invalid_numeric_field_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError.

    Spiegelt find_duplicate_ids/find_rows_without_id/find_rows_with_invalid_funddatum/
    load_standard: alle stehen zur gleichen Format-Regel und lehnen v1/v2-
    Historik-CSVs sichtbar ab, statt stille "0 Funde" zu melden.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "fremd_num.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_with_invalid_numeric_field(csv_path, "Gewicht_g")


def test_find_rows_with_invalid_numeric_field_raises_bei_nicht_numerischem_feld(tmp_path):
    """Nicht-numerische Felder werfen ValueError.

    ``Fundort`` (str), ``Notizen`` (text), ``Kategorie`` (enum), ``Funddatum``
    (date), ``Foto_Uebersicht`` (path) sind keine Silent-Drop-Kandidaten auf
    der Zahl-Achse und wuerden vom Detektor irrefuehrende Ergebnisse liefern
    ("jeder freitext-Wert waere invalid"). Fuer ``date`` gibt es
    :func:`find_rows_with_invalid_funddatum` als spezialisierten Pfad; fuer
    Text-Felder gilt jeder nicht-leere Wert als gueltig (kein Silent-Drop
    moeglich). Ein Aufruf mit "Fundort" waere fast sicher ein Programmier-
    Fehler und darf nicht stillschweigend leere Liste liefern.
    """
    import pytest
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "irrelevant.csv"
    csv_path.write_text("ID,Fundort\nOBJ_0001,Davos\n", encoding="utf-8")
    for col in ("Fundort", "Funddatum", "Mineral_Primaer", "Kategorie",
                "Foto_Uebersicht"):
        with pytest.raises(ValueError, match="Kein numerisches Standard-Feld"):
            find_rows_with_invalid_numeric_field(csv_path, col)
    # Erfundenes Feld wird ebenfalls abgewiesen (kein Regress zu einem
    # "unbekanntes Feld wird toleriert"-Verhalten).
    with pytest.raises(ValueError, match="Kein numerisches Standard-Feld"):
        find_rows_with_invalid_numeric_field(csv_path, "Halluzination")


def test_find_rows_with_invalid_numeric_field_scale_und_int_felder(tmp_path):
    """Detektor deckt alle NUMERIC_TYPES ab (float, int, scale).

    ``Confidence_Prozent`` (int) und ``Seltenheit_global_1_10`` (scale) sind
    numerisch konvertiert und teilen die Silent-Drop-Semantik: ein Freitext
    wie "hoch" oder "mittel" faellt via ``_int -> _num -> None`` durch, das
    Feld wird nicht uebernommen. Ohne diesen Test koennte eine spaetere
    Verschaerfung des Domain-Filters (z.B. nur ``float`` akzeptieren) die
    Scale-/Int-Coverage still abschneiden.
    """
    from stonebook.migration.csv_loaders import find_rows_with_invalid_numeric_field
    csv_path = tmp_path / "scale_int.csv"
    csv_path.write_text(
        "ID,Confidence_Prozent,Seltenheit_global_1_10\n"
        "OBJ_0001,85,7\n"
        "OBJ_0002,hoch,mittel\n"
        "OBJ_0003,42,-\n"   # "-" ist no-data-marker, nicht invalid
        "OBJ_0004,keine Angabe verfuegbar,unbekannt\n",  # nur Text ohne Zahl
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Confidence_Prozent") == [
        (2, "hoch"),
        (4, "keine Angabe verfuegbar"),
    ]
    assert find_rows_with_invalid_numeric_field(
        csv_path, "Seltenheit_global_1_10") == [
        (2, "mittel"),
    ]


def test_find_rows_with_invalid_numeric_fields_bulk_standard(tmp_path):
    """Bulk-Scanner buendelt alle numerischen Spalten in einem Aufruf.

    Symmetrie-Vervollstaendigung zur singularen Variante: waehrend die
    Einzel-Spalte-Version einen konkreten Feldnamen erwartet, laeuft die
    Plural-Version selbstaendig ueber alle im File vorhandenen numerischen
    Spalten und emittiert (Zeile, Spalte, Roh-Wert)-Tripel. Vorbedingung
    fuer die ImportReport-Wiring, die ohne feste Spalten-Liste auskommen
    muss. Reihenfolge = Zeile-primaer, Spalte-sekundaer in Header-Reihenfolge.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "bulk.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Wert_CHF_roh,Mineral_Primaer\n"
        "OBJ_0001,42.5,500,Quarz\n"
        "OBJ_0002,sehr schwer,teuer,Calcit\n"     # zwei Silent-Drops in Zeile 2
        "OBJ_0003,150,ca. 750,Amethyst\n"          # Zeile 3 sauber
        "OBJ_0004,,unbekannt,Turmalin\n"           # leer/Marker - kein Report
        "OBJ_0005,mittel,,Diopsid\n",              # nur Gewicht kaputt
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == [
        (2, "Gewicht_g", "sehr schwer"),
        (2, "Wert_CHF_roh", "teuer"),
        (5, "Gewicht_g", "mittel"),
    ]


def test_find_rows_with_invalid_numeric_fields_ohne_numerische_spalten(tmp_path):
    """Fehlen numerische Spalten komplett -> [] statt ValueError.

    Spiegelt die Kein-Datenverlust-Regel der Einzel-Version: wenn das File
    keine numerischen Felder enthaelt, kann es dort auch keinen Silent-Drop
    geben - der Report darf nicht kuenstlich ValueError werfen.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "kein_num.csv"
    csv_path.write_text(
        "ID,Mineral_Primaer,Fundort\nOBJ_0001,Quarz,Davos\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == []


def test_find_rows_with_invalid_numeric_fields_ignoriert_no_data_marker(tmp_path):
    """Explizite "keine Angabe"-Marker werden auch im Bulk-Scan uebersprungen.

    Marker-Menge muss zwischen singular und plural konsistent sein - Wenn
    der User in einer Spalte ``k.a.`` schreibt, ist das explizite
    ``kein Wert verfuegbar``, kein Silent-Drop. Ein Regress hier wuerde die
    Report-Ausgabe mit Rauschmeldungen fluten.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "marker_bulk.csv"
    csv_path.write_text(
        "ID,Gewicht_g,Wert_CHF_roh,Confidence_Prozent\n"
        "OBJ_0001,k.a.,n/a,unbekannt\n"
        "OBJ_0002,?,-,K.A.\n"
        "OBJ_0003,,   ,\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == []


def test_find_rows_with_invalid_numeric_fields_scale_und_int_felder(tmp_path):
    """Bulk-Scan deckt alle NUMERIC_TYPES ab (float / int / scale).

    Analog zur singularen Variante: Confidence_Prozent (int),
    Seltenheit_global_1_10 (scale), Gewicht_g (float) sind alle numerisch
    konvertiert und teilen die Silent-Drop-Semantik. Ohne diesen Test
    koennte eine spaetere Domain-Verengung des Bulk-Scanners (nur float)
    die Scale-/Int-Coverage still abschneiden.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "types.csv"
    csv_path.write_text(
        "ID,Confidence_Prozent,Seltenheit_global_1_10,Gewicht_g\n"
        "OBJ_0001,hoch,mittel,leicht\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == [
        (1, "Confidence_Prozent", "hoch"),
        (1, "Seltenheit_global_1_10", "mittel"),
        (1, "Gewicht_g", "leicht"),
    ]


def test_find_rows_with_invalid_numeric_fields_akzeptiert_obj_id_spalte(tmp_path):
    """JSON-/DB-Format nutzt ``obj_id`` statt ``ID``.

    Bulk-Scan-Konsistenz mit der ID-Alias-Regel der uebrigen Silent-Drop-
    Detektoren: ein Reexport aus dem DB-Backup-JSON (Header ``obj_id``) muss
    genauso verarbeitet werden wie ein CSV-Export (Header ``ID``).
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "objid_bulk.csv"
    csv_path.write_text(
        "obj_id,Wert_CHF_roh\nOBJ_0001,42.5\nOBJ_0002,teuer\n",
        encoding="utf-8",
    )
    assert find_rows_with_invalid_numeric_fields(csv_path) == [
        (2, "Wert_CHF_roh", "teuer"),
    ]


def test_find_rows_with_invalid_numeric_fields_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV mit Zeilen aber ohne ID/obj_id-Header wirft ValueError.

    Format-Regel-Konsistenz: alle Pre-Scanner
    (find_duplicate_ids/find_rows_without_id/find_rows_with_invalid_funddatum/
    find_rows_with_invalid_numeric_field und jetzt auch die Bulk-Variante)
    lehnen v1/v2-Historik-CSVs sichtbar ab, statt stille "0 Funde" zu melden.
    """
    import pytest
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "fremd_bulk.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ID-Spalte"):
        find_rows_with_invalid_numeric_fields(csv_path)


def test_find_rows_with_invalid_numeric_fields_leere_csv(tmp_path):
    """Leere CSV (nur Header) -> [] ohne Fehler.

    Spiegelt find_rows_with_invalid_funddatum_leere_csv: ohne Zeilen kann
    es keinen Datenverlust geben, unabhaengig vom Header-Format. Auch dann
    keine ValueError, wenn der Header keine ID-Spalte hat - konsistent mit
    dem "Zeilen == 0"-Kurzschluss der uebrigen Silent-Drop-Detektoren.
    """
    from stonebook.migration.csv_loaders import (
        find_rows_with_invalid_numeric_fields,
    )
    csv_path = tmp_path / "leer_bulk.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    assert find_rows_with_invalid_numeric_fields(csv_path) == []


def test_load_standard_raises_bei_fehlender_id_spalte(tmp_path):
    """CSV ohne ID/obj_id-Spalte ist kein gueltiger Standard-Import - klarer Fehler."""
    import pytest
    csv_path = tmp_path / "fremd.csv"
    csv_path.write_text(
        "Name,Mineralart,Fundort\nFoo,Quarz,Davos\n",
        encoding="utf-8",
    )
    from stonebook.migration.csv_loaders import load_standard
    with pytest.raises(ValueError, match="ID-Spalte"):
        load_standard(csv_path)


def test_load_standard_leere_csv_ohne_id_spalte_ist_ok(tmp_path):
    """Leere CSV (nur Header) loest keinen Fehler aus - return {} ist sinnvoll."""
    csv_path = tmp_path / "leer.csv"
    csv_path.write_text("Name,Mineralart\n", encoding="utf-8")
    from stonebook.migration.csv_loaders import load_standard
    assert load_standard(csv_path) == {}


def test_load_obj043():
    data = csv_loaders.load_obj043(
        CSV_DIR / "Stonebock__StoneBoock_Objekt_043_FULL__StoneBoock_Objekt_043.csv")
    o43 = data["OBJ_0043"]
    assert o43["Gewicht_g"] == 41.0
    assert "Quarz" in o43["Mineral_Primaer"]
    assert o43["Dichte_min_gcm3"] == 2.65
    assert o43["Dichte_max_gcm3"] == 2.65
    assert o43["Mohs_Haerte_min"] == 7.0


def test_load_v1_cp1252_fallback(tmp_path):
    """v1-Loader greift jetzt auf den gleichen tolerant-Reader wie load_standard zu.

    Re-editierte Historik-CSVs aus Excel/Notepad mit cp1252-Encoding (typisch beim
    "Speichern unter..."-Dialog auf aelteren Windows-Versionen) wurden bisher von
    ``_read_csv`` mit utf-8-sig-only stillschweigend zur ``UnicodeDecodeError``-
    Exception eskaliert. Nach der Konsolidierung auf ``_read_csv_robust`` greift
    der Encoding-Fallback (utf-8-sig -> utf-8 -> cp1252 -> latin-1) auch fuer die
    historischen Loader.
    """
    p = tmp_path / "v1_cp1252.csv"
    # Volle v1-Spaltenliste mit Härte/Dichte/Wert-Spalten; nur die kritischen
    # Umlaute (Härte, Rötlich) testen den Encoding-Fallback.
    header = ("ID,Name,Beschreibung,Mineralart,Fundort,UV-Reaktion,Härte,Dichte,"
              "Transparenz,Farbe,Wert_CHF_roh,Wert_CHF_poliert,Wert_CHF_Schmuck,"
              "Wert_USD_Talisman,Marktwert,Wissenschaftlicher_Wert,"
              "Seltenheit_global,Seltenheit_Fundort,Nachfrage,Inhaltsstoffe,"
              "Beste_Verwendung\n")
    row = ("OBJ_0001,Jaspis,Rötlicher Stein,Jaspis,Schweiz,keine,6.5-7,2.65,"
           "opak,rot,100,200,300,50,150,80,7,5,6,SiO2,Sammlung\n")
    p.write_bytes((header + row).encode("cp1252"))
    data = csv_loaders.load_v1(p)
    assert "OBJ_0001" in data
    o = data["OBJ_0001"]
    assert o["Mineral_Primaer"] == "Jaspis"
    assert o["Mohs_Haerte_min"] == 6.5
    assert o["Mohs_Haerte_max"] == 7.0
    assert "Rötlich" in o["notizen"]


def test_load_v2_semicolon_delimiter(tmp_path):
    """v2-Loader erkennt jetzt ``;`` als Delimiter (DE-Excel-Default).

    DE-/CH-Excel speichert beim CSV-Export per Default mit Semikolon, weil das
    Komma als Dezimal-Trenner reserviert ist. Vor der Konsolidierung scheiterte
    ``load_v2`` auf solchen Re-Exports stille mit leerem Dict (Header als
    Einzelspalte ``ID;Name;...`` interpretiert, keine ID-Spalte gefunden).
    Der tolerant-Reader detektiert jetzt den haeufigsten Trenner aus der
    Header-Zeile.
    """
    p = tmp_path / "v2_semicolon.csv"
    header = "ID;Name;Mineral_Primaer;Mohs_Haerte_min;Mohs_Haerte_max\n"
    row = "OBJ_0007;Bergkristall;Quarz;7;7\n"
    p.write_text(header + row, encoding="utf-8")
    data = csv_loaders.load_v2(p)
    assert "OBJ_0007" in data
    o = data["OBJ_0007"]
    assert o["Mineral_Primaer"] == "Quarz"
    assert o["Mohs_Haerte_min"] == 7.0
    assert o["Mohs_Haerte_max"] == 7.0
