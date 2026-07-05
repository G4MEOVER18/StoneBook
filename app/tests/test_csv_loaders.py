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
    # Freitext-Anhang bricht das $-Anker-Pattern; Fallback liefert nur Center.
    assert csv_loaders.parse_range("5.5(3) (Literatur)") == (5.5, 5.5)
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
    # Freitext-Anhang bricht das Pattern; Fallback auf Zahl-Extraktion liefert
    # nur den Center (Toleranz wird ohne strikten Pattern-Match nicht gesondert
    # ausgewertet).
    assert csv_loaders.parse_range("5.5 ± 0.3 (Literatur)") == (5.5, 5.5)
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
    # Freitext-Anhang: Fallback greift, spiegelt die ±-Konvention
    assert csv_loaders.parse_range("5.5 +/- 0.3 (Literatur)") == (5.5, 5.5)


def test_parse_range_schweizer_apostroph_tausender():
    """Schweizer Tausendertrenner ''' wird ignoriert (CHF-Betraege aus Excel)."""
    # Ohne Fix waere "1'000.00" als (1, 0) gelesen worden.
    assert csv_loaders.parse_range("1'000.00") == (1000.0, 1000.0)
    assert csv_loaders.parse_range("1'500'000.50") == (1500000.5, 1500000.5)
    # Range mit Apostroph auf beiden Seiten
    assert csv_loaders.parse_range("1'000-2'000") == (1000.0, 2000.0)
    # Typografischer Apostroph (U+2019) wird ebenso entfernt
    assert csv_loaders.parse_range("1’000") == (1000.0, 1000.0)


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
