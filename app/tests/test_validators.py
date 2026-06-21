from stonebook.migration.validators import parse_coordinates, parse_iso_date


def test_parse_iso_date_iso_unchanged():
    assert parse_iso_date("2024-06-13") == "2024-06-13"


def test_parse_iso_date_german():
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("1.1.2020") == "2020-01-01"


def test_parse_iso_date_slash_dot():
    assert parse_iso_date("2024/06/13") == "2024-06-13"
    assert parse_iso_date("2024.06.13") == "2024-06-13"


def test_parse_iso_date_year_only():
    assert parse_iso_date("2024") == "2024-01-01"
    assert parse_iso_date("1999") == "1999-01-01"


def test_parse_iso_date_year_month():
    assert parse_iso_date("2024-06") == "2024-06-01"
    assert parse_iso_date("2024/6") == "2024-06-01"


def test_parse_iso_date_deutsche_monatsnamen():
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("1. Januar 2020") == "2020-01-01"
    assert parse_iso_date("3 Mai 2019") == "2019-05-03"
    assert parse_iso_date("31. Dezember 1999") == "1999-12-31"
    # Kurzformen
    assert parse_iso_date("13. Jun 2024") == "2024-06-13"
    assert parse_iso_date("13. Sept 2024") == "2024-09-13"
    # Mit Umlaut: März → maerz
    assert parse_iso_date("5. März 2022") == "2022-03-05"


def test_parse_iso_date_monat_jahr():
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("Mai, 2024") == "2024-05-01"
    assert parse_iso_date("Dezember 1999") == "1999-12-01"
    assert parse_iso_date("März 2022") == "2022-03-01"


def test_parse_iso_date_englische_monatsnamen():
    """Englische Monatsnamen (EXIF, Foto-Bibliotheks-Exporte): 'Month DD, YYYY'."""
    # Kurz + lang
    assert parse_iso_date("Jun 13, 2024") == "2024-06-13"
    assert parse_iso_date("June 13, 2024") == "2024-06-13"
    # Ohne Komma
    assert parse_iso_date("June 13 2024") == "2024-06-13"
    assert parse_iso_date("Dec 1 1999") == "1999-12-01"
    # Englisch-spezifische Kuerzel/Formen, die im DE-Schema fehlen
    assert parse_iso_date("May 5, 2020") == "2020-05-05"
    assert parse_iso_date("Oct 31, 2024") == "2024-10-31"
    assert parse_iso_date("December 24, 2023") == "2023-12-24"
    assert parse_iso_date("March 7, 2020") == "2020-03-07"
    assert parse_iso_date("July 15 2024") == "2024-07-15"
    # Mit Punkt nach Kurzform (z.B. "Jun. 13, 2024")
    assert parse_iso_date("Jun. 13, 2024") == "2024-06-13"


def test_parse_iso_date_tag_ordinal_suffix():
    """Englisches Ordinal-Suffix (st/nd/rd/th) am Tag wird akzeptiert."""
    # Tag-vor-Monat
    assert parse_iso_date("1st March 2024") == "2024-03-01"
    assert parse_iso_date("2nd June 2024") == "2024-06-02"
    assert parse_iso_date("3rd July 2024") == "2024-07-03"
    assert parse_iso_date("4th August 2024") == "2024-08-04"
    assert parse_iso_date("21st December 2024") == "2024-12-21"
    assert parse_iso_date("22nd February 2024") == "2024-02-22"
    assert parse_iso_date("23rd December 1999") == "1999-12-23"
    assert parse_iso_date("31st May 2024") == "2024-05-31"
    # Monat-vor-Tag
    assert parse_iso_date("March 1st, 2024") == "2024-03-01"
    assert parse_iso_date("June 2nd 2024") == "2024-06-02"
    assert parse_iso_date("May 31st, 2024") == "2024-05-31"
    assert parse_iso_date("Dec 23rd, 1999") == "1999-12-23"
    # Case-insensitive
    assert parse_iso_date("1ST March 2024") == "2024-03-01"
    assert parse_iso_date("March 1ST, 2024") == "2024-03-01"
    # Mit trailing Satzzeichen
    assert parse_iso_date("March 1st, 2024.") == "2024-03-01"
    # Mit Annaeherungspraefix
    assert parse_iso_date("ca. 1st March 2024") == "2024-03-01"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("Jun 13, 2024") == "2024-06-13"


def test_parse_iso_date_englische_monatsnamen_ungueltig():
    assert parse_iso_date("Feb 30, 2024") is None  # 30. Februar
    assert parse_iso_date("Foo 13, 2024") is None  # Unbekannter Monat
    assert parse_iso_date("Jun 13, 1700") is None  # vor 1800


def test_parse_iso_date_compact_iso():
    """ISO 8601 compact YYYYMMDD (kommt in Dateinamen/Log-Stempeln vor)."""
    assert parse_iso_date("20240613") == "2024-06-13"
    assert parse_iso_date("19990101") == "1999-01-01"
    assert parse_iso_date("20240230") is None    # Februar 30 → ungueltig
    assert parse_iso_date("17000101") is None    # vor 1800 → ausserhalb


def test_parse_iso_date_iso_datetime():
    """ISO 8601 mit Zeitanteil (T oder Space) wird auf das Datum reduziert."""
    assert parse_iso_date("2024-06-13T10:00:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13 10:00:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00Z") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00.123") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00+02:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00-0500") == "2024-06-13"


def test_parse_iso_date_iso_datetime_komma_dezimal():
    """ISO 8601 schreibt Komma als bevorzugten Dezimal-Separator im Zeitanteil vor."""
    # Reines ISO mit Komma-Decimal in Sekundenbruch
    assert parse_iso_date("2024-06-13T10:00:00,123") == "2024-06-13"
    assert parse_iso_date("2024-06-13 10:00:00,123") == "2024-06-13"
    # Mit Zeitzonen-Suffix (UTC und Offset)
    assert parse_iso_date("2024-06-13T10:00:00,123Z") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00,123+02:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00,5-0500") == "2024-06-13"
    # DE-Datum + Zeit mit Komma-Decimal (Logbuch-/Excel-Eintrag DE-Locale)
    assert parse_iso_date("13.06.2024 14:30:00,123") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30:00,5") == "2024-06-13"
    # EXIF mit Komma-Decimal (sehr selten, aber spec-compliant)
    assert parse_iso_date("2024:06:13 10:00:00,123") == "2024-06-13"
    # Mit deutschem Monatsnamen + Komma-Decimal
    assert parse_iso_date("13. Juni 2024 14:30:00,123") == "2024-06-13"
    # Bestehende Punkt-Dezimal-Form unveraendert (kein Regress)
    assert parse_iso_date("2024-06-13T10:00:00.123") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00.123Z") == "2024-06-13"


def test_parse_iso_date_named_timezones():
    """Benannte Zeitzonen-Suffixe (UTC/GMT/CET/CEST/MEZ/MESZ/EST/PST/...).

    Symmetrisch zur numerischen Form (``+02:00``/``Z``) - System-Logs, Foto-
    Captions und EXIF-Tools schreiben die TZ oft als 2-5-Buchstaben-
    Abkuerzung statt als Offset. Der Datumsanteil ist eindeutig, der
    Zeitanteil (inkl. TZ) wird ohnehin verworfen.
    """
    # UTC/GMT (Coordinated Universal Time)
    assert parse_iso_date("2024-06-13T10:00:00 UTC") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 GMT") == "2024-06-13"
    # Mitteleuropa (Sommer/Winter)
    assert parse_iso_date("2024-06-13T10:00:00 CET") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 CEST") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 MEZ") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 MESZ") == "2024-06-13"
    # USA-Zeitzonen
    assert parse_iso_date("2024-06-13T10:00:00 EST") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 EDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 PST") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 PDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 CST") == "2024-06-13"
    # Weitere (Asia/Australia)
    assert parse_iso_date("2024-06-13T10:00:00 JST") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00 IST") == "2024-06-13"
    # Mit Space-statt-T-Separator
    assert parse_iso_date("2024-06-13 14:30 UTC") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:30:00 CEST") == "2024-06-13"
    # DE-Datum + Zeit + named TZ (Excel/Logbuch DE-Locale)
    assert parse_iso_date("13.06.2024 14:30 CEST") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30:00 UTC") == "2024-06-13"
    # Monatsname + Zeit + named TZ
    assert parse_iso_date("13. Juni 2024 14:30 GMT") == "2024-06-13"
    assert parse_iso_date("Jun 13 2024 14:30 EST") == "2024-06-13"
    # Bestehende Formen bleiben unveraendert (kein Regress)
    assert parse_iso_date("2024-06-13T10:00:00Z") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00+02:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13T10:00:00") == "2024-06-13"
    # Kleinbuchstaben-Suffixe matchen nicht (nicht-TZ wie ``Uhr``, ``abc``):
    assert parse_iso_date("2024-06-13T10:00:00 abc") is None
    assert parse_iso_date("2024-06-13T10:00:00 Uhr") is None
    # Gemischter Case (UTc) ebenfalls nicht - bewusste Konvention,
    # weil TZ-Standardschreibung Grossbuchstaben sind.
    assert parse_iso_date("2024-06-13T10:00:00 UTc") is None
    # Sechs Buchstaben (zu lang) matched nicht
    assert parse_iso_date("2024-06-13T10:00:00 TOOLONG") is None
    # Einzelner Grossbuchstabe matched nicht (Z wird separat als Zulu erkannt,
    # aber 'X' o.ae. nicht - Mindestlaenge 2 verhindert Kollision)
    assert parse_iso_date("2024-06-13T10:00:00 X") is None


def test_parse_iso_date_deutsche_zeitangaben():
    """DE-Datum mit Zeit (Excel/Logbuch) - Zeitanteil wird ignoriert."""
    assert parse_iso_date("13.06.2024 14:30") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30:00") == "2024-06-13"
    assert parse_iso_date("1.1.2020 0:00") == "2020-01-01"
    # Auch mit deutschem Monatsnamen
    assert parse_iso_date("13. Juni 2024 14:30") == "2024-06-13"
    # ungueltiger Datumsteil bleibt None, auch wenn Zeit korrekt aussieht
    assert parse_iso_date("32.13.2024 14:30") is None


def test_parse_iso_date_exif_datetime():
    """EXIF DateTimeOriginal nutzt Doppelpunkte im Datumsteil (Foto-Metadaten)."""
    assert parse_iso_date("2024:06:13 10:00:00") == "2024-06-13"
    assert parse_iso_date("1999:12:31 23:59:59") == "1999-12-31"
    # Ungueltiges EXIF-Datum (Monat 13) → None
    assert parse_iso_date("2024:13:01 10:00:00") is None


def test_parse_iso_date_exif_date_ohne_zeit():
    """EXIF DateTime ohne Zeit-Suffix (stripped Camera-Stempel) - tritt nach Datenextraktion auf."""
    assert parse_iso_date("2024:06:13") == "2024-06-13"
    assert parse_iso_date("1999:12:31") == "1999-12-31"
    assert parse_iso_date("2020:01:01") == "2020-01-01"
    # Ungueltige Werte bleiben None
    assert parse_iso_date("2024:13:01") is None    # Monat 13
    assert parse_iso_date("2024:02:30") is None    # Februar 30
    assert parse_iso_date("1700:01:01") is None    # vor 1800
    # Mit trailing Satzzeichen / Klammern / Annaeherungspraefix
    assert parse_iso_date("2024:06:13.") == "2024-06-13"
    assert parse_iso_date("(2024:06:13)") == "2024-06-13"
    assert parse_iso_date("ca. 2024:06:13") == "2024-06-13"
    # Bestehende EXIF-Form mit Zeit bleibt unveraendert (kein Regress)
    assert parse_iso_date("2024:06:13 10:00:00") == "2024-06-13"


def test_parse_iso_date_annaeherungs_praefix():
    """Sammlungs-Notizen wie 'ca. 1985' / 'um 1980' / 'circa Juni 2024' ergeben das Datum."""
    # Jahres-Naeherung (typisch fuer geerbte Sammlung)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("ca 1985") == "1985-01-01"
    assert parse_iso_date("circa 2020") == "2020-01-01"
    assert parse_iso_date("um 1980") == "1980-01-01"
    assert parse_iso_date("gegen 1999") == "1999-01-01"
    # Englische Varianten
    assert parse_iso_date("approx. 2024") == "2024-01-01"
    assert parse_iso_date("approx 2024") == "2024-01-01"
    assert parse_iso_date("approximately 1995") == "1995-01-01"
    assert parse_iso_date("around 1995") == "1995-01-01"
    assert parse_iso_date("about 2010") == "2010-01-01"
    # Case-insensitive
    assert parse_iso_date("CA. 2020") == "2020-01-01"
    assert parse_iso_date("Circa 2020") == "2020-01-01"
    # Auf vollstaendigem Datum
    assert parse_iso_date("ca. 13.06.2024") == "2024-06-13"
    assert parse_iso_date("circa 2024-06-13") == "2024-06-13"
    # Auf Monatsnamen
    assert parse_iso_date("ca. Juni 2024") == "2024-06-01"
    assert parse_iso_date("circa June 2024") == "2024-06-01"
    # Verkettete Praefixe ("ca. circa 2020") sind semantisch redundant, aber unschaedlich:
    # die Rekursion strippt einen nach dem anderen und liefert am Ende das Datum.
    assert parse_iso_date("ca. circa 2020") == "2020-01-01"
    # Praefix ohne Inhalt / mit ungueltigem Rest → None
    assert parse_iso_date("ca.") is None
    assert parse_iso_date("circa") is None
    assert parse_iso_date("ca. abc") is None
    assert parse_iso_date("ca. 1700") is None  # ausserhalb 1800-2999


def test_parse_iso_date_annaeherungs_praefix_erweitert():
    """DE-Sammler-Vokabular (etwa/vermutlich/schaetzungsweise) und EN (estimated/roughly) als Praefix."""
    # Deutsch
    assert parse_iso_date("etwa 1985") == "1985-01-01"
    assert parse_iso_date("vermutlich 1985") == "1985-01-01"
    assert parse_iso_date("schaetzungsweise 1985") == "1985-01-01"
    assert parse_iso_date("schätzungsweise 1985") == "1985-01-01"
    # Englisch
    assert parse_iso_date("estimated 1985") == "1985-01-01"
    assert parse_iso_date("est. 1985") == "1985-01-01"
    assert parse_iso_date("roughly 1985") == "1985-01-01"
    # Case-insensitive
    assert parse_iso_date("ETWA 2020") == "2020-01-01"
    assert parse_iso_date("Vermutlich 2020") == "2020-01-01"
    assert parse_iso_date("SCHAETZUNGSWEISE 1985") == "1985-01-01"
    # Praefix + vollstaendiges Datum (Rekursion)
    assert parse_iso_date("etwa Juni 2024") == "2024-06-01"
    assert parse_iso_date("vermutlich 13.06.2024") == "2024-06-13"
    assert parse_iso_date("estimated 2024-06-13") == "2024-06-13"
    # Verkettet mit bestehenden Praefixen (rekursive Strippung)
    assert parse_iso_date("etwa ca. 1985") == "1985-01-01"
    # Ohne Datum-Rest → None
    assert parse_iso_date("etwa") is None
    assert parse_iso_date("vermutlich") is None
    # Datum aus dem zulaessigen Bereich → None
    assert parse_iso_date("etwa 1700") is None
    # Bestehende Praefixe unveraendert (kein Regress)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("circa 2020") == "2020-01-01"
    assert parse_iso_date("um 1980") == "1980-01-01"
    assert parse_iso_date("approx 2024") == "2024-01-01"


def test_parse_iso_date_annaeherungs_symbol():
    """Tilde (``~``) und Almost-Equal (``≈``) als Annaeherungs-Symbol vor dem Datum."""
    # Tilde - typografisch knappe Notation aus Tabellen-Captions / Foto-EXIF
    assert parse_iso_date("~1985") == "1985-01-01"
    assert parse_iso_date("~ 1985") == "1985-01-01"
    assert parse_iso_date("~Juni 2024") == "2024-06-01"
    assert parse_iso_date("~ Juni 2024") == "2024-06-01"
    assert parse_iso_date("~13.06.2024") == "2024-06-13"
    assert parse_iso_date("~2024-06") == "2024-06-01"
    # Almost-Equal (U+2248) - LaTeX-Exports (``\approx``), Print-Kataloge
    assert parse_iso_date("≈1985") == "1985-01-01"
    assert parse_iso_date("≈ 1985") == "1985-01-01"
    assert parse_iso_date("≈Juni 2024") == "2024-06-01"
    assert parse_iso_date("≈13.06.2024") == "2024-06-13"
    # Verkettet mit Wort-Praefix (rekursive Strippung): semantisch redundant,
    # aber unschaedlich - jeder Praefix wird einmal pro Rekursionsebene gestrippt.
    assert parse_iso_date("~ca. 1985") == "1985-01-01"
    assert parse_iso_date("≈ circa 2020") == "2020-01-01"
    assert parse_iso_date("~~1985") == "1985-01-01"
    # Ohne Datum-Rest oder mit ungueltigem Rest → None
    assert parse_iso_date("~") is None
    assert parse_iso_date("≈") is None
    assert parse_iso_date("~abc") is None
    assert parse_iso_date("~1700") is None  # ausserhalb 1800-2999
    # Tilde nur als Praefix (am Anfang) gestrippt - mittendrin/am Ende bleibt
    # die Eingabe wie sie ist und matcht keinen Datums-Parser.
    assert parse_iso_date("1985~") is None
    assert parse_iso_date("X ~ 1985") is None
    # Bestehende Praefixe unveraendert (kein Regress)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("circa 2020") == "2020-01-01"
    assert parse_iso_date("etwa 1985") == "1985-01-01"


def test_parse_iso_date_jahreszeiten():
    """Sammlungs-Notizen mit Jahreszeit + Jahr ergeben den meteorologischen Saison-Start."""
    # Deutsch
    assert parse_iso_date("Frühling 2024") == "2024-03-01"
    assert parse_iso_date("Frühjahr 2024") == "2024-03-01"
    assert parse_iso_date("Sommer 1985") == "1985-06-01"
    assert parse_iso_date("Herbst 1999") == "1999-09-01"
    assert parse_iso_date("Winter 1985") == "1985-12-01"
    # Englisch
    assert parse_iso_date("Spring 2024") == "2024-03-01"
    assert parse_iso_date("Summer 1985") == "1985-06-01"
    assert parse_iso_date("Autumn 2020") == "2020-09-01"
    assert parse_iso_date("Fall 1999") == "1999-09-01"
    # Case-insensitive
    assert parse_iso_date("sommer 2020") == "2020-06-01"
    assert parse_iso_date("SUMMER 2020") == "2020-06-01"
    # Mit Komma
    assert parse_iso_date("Sommer, 1985") == "1985-06-01"
    # Naeherung + Saison ("ca. Sommer 1985")
    assert parse_iso_date("ca. Sommer 1985") == "1985-06-01"
    assert parse_iso_date("circa Summer 1985") == "1985-06-01"
    # Monatsnamen behalten Vorrang vor Saisons (kein versehentliches Re-Mapping)
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("June 2024") == "2024-06-01"


def test_parse_iso_date_relative_jahresposition():
    """Anfang/Mitte/Ende + Jahr (analog Saison): Jan / Jul / Dez im genannten Jahr."""
    # Deutsch
    assert parse_iso_date("Anfang 2024") == "2024-01-01"
    assert parse_iso_date("Mitte 2024") == "2024-07-01"
    assert parse_iso_date("Ende 2024") == "2024-12-01"
    assert parse_iso_date("Anfang 1985") == "1985-01-01"
    assert parse_iso_date("Mitte 1985") == "1985-07-01"
    assert parse_iso_date("Ende 1999") == "1999-12-01"
    # Englisch
    assert parse_iso_date("early 2024") == "2024-01-01"
    assert parse_iso_date("mid 2024") == "2024-07-01"
    assert parse_iso_date("late 2024") == "2024-12-01"
    # Bindestrich-Variante (verbreitet bei "mid-2024")
    assert parse_iso_date("mid-2024") == "2024-07-01"
    assert parse_iso_date("early-2024") == "2024-01-01"
    assert parse_iso_date("late-2024") == "2024-12-01"
    # Case-insensitive
    assert parse_iso_date("ANFANG 2024") == "2024-01-01"
    assert parse_iso_date("Mid 2024") == "2024-07-01"
    # Kombiniert mit Annaeherungspraefix
    assert parse_iso_date("ca. Anfang 1985") == "1985-01-01"
    assert parse_iso_date("circa mid 1985") == "1985-07-01"
    # Kombiniert mit trailing Satzzeichen
    assert parse_iso_date("Ende 2024.") == "2024-12-01"
    # Kombiniert in Klammern
    assert parse_iso_date("[Mitte 1985]") == "1985-07-01"


def test_parse_iso_date_relative_jahresposition_ungueltig():
    """Schluesselwort ohne Jahr / Jahr ausserhalb / mehrdeutige Decade-Spanne → None."""
    # Schluesselwort allein
    assert parse_iso_date("Anfang") is None
    assert parse_iso_date("Mitte") is None
    assert parse_iso_date("Ende") is None
    assert parse_iso_date("early") is None
    # Jahr ausserhalb 1800-2999
    assert parse_iso_date("Anfang 1700") is None
    assert parse_iso_date("Ende 3000") is None
    # Mit zusaetzlichem Wort (z.B. "Anfang Maerz 2024") → None
    # (semantisch sinnvoll waere 2024-03-01, aber das Format ist nicht eindeutig
    # genug zur stillschweigenden Konvertierung)
    assert parse_iso_date("Anfang März 2024") is None
    # Bestehende Saison-Notation bleibt unveraendert (kein Regress)
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    # Dekaden-Position ("late 1980s", "Anfang 1980er") wird ueber das eigene
    # _RELATIVE_DECADE-Pattern auf das jeweilige Jahr in der Dekade gemappt
    # (Anfang=Jahr 0, Mitte=Jahr 5, Ende=Jahr 9) - siehe
    # ``test_parse_iso_date_relative_dekade``. Frueher fielen beide auf None
    # (mit Begruendung "mehrdeutig"), inzwischen sind sie eindeutig verortet.
    assert parse_iso_date("late 1980s") == "1989-01-01"
    assert parse_iso_date("Anfang 1980er") == "1980-01-01"
    # "Anfang der 1980er" mit Artikel-Fueller bleibt None (nicht im Vokabular,
    # eindeutiges Stripping waere willkuerlich) - die Form ist in praktischen
    # Sammler-Notizen extrem selten ("Anfang 1980er" ist die uebliche Form).
    assert parse_iso_date("Anfang der 1980er") is None


def test_parse_iso_date_jahrzehnt():
    """Jahrzehnt-Notation ergibt das Dekaden-Startjahr (1980er → 1980-01-01)."""
    # Deutsch
    assert parse_iso_date("1980er") == "1980-01-01"
    assert parse_iso_date("1990er") == "1990-01-01"
    assert parse_iso_date("1980er Jahre") == "1980-01-01"
    assert parse_iso_date("1980 er") == "1980-01-01"
    assert parse_iso_date("1980-er") == "1980-01-01"
    # Englisch
    assert parse_iso_date("1980s") == "1980-01-01"
    assert parse_iso_date("1990s") == "1990-01-01"
    assert parse_iso_date("1980 s") == "1980-01-01"
    # Case-insensitive
    assert parse_iso_date("1980ER") == "1980-01-01"
    assert parse_iso_date("1980S") == "1980-01-01"
    # Mit Annaeherungspraefix
    assert parse_iso_date("ca. 1980er") == "1980-01-01"
    assert parse_iso_date("circa 1980s") == "1980-01-01"
    # Mit trailing Satzzeichen
    assert parse_iso_date("1980er.") == "1980-01-01"
    assert parse_iso_date("1980s,") == "1980-01-01"
    # Bestehende Jahresangaben unveraendert (kein Regress)
    assert parse_iso_date("1980") == "1980-01-01"


def test_parse_iso_date_jahrzehnt_ungueltig():
    # Zweistellige Kurzform ist mehrdeutig (1880er vs 1980er) → None
    assert parse_iso_date("80er") is None
    assert parse_iso_date("80s") is None
    # Jahrzehnt vor 1800 oder nach 2999 → None
    assert parse_iso_date("1700er") is None
    assert parse_iso_date("3000er") is None
    # Kein Jahrzehnt ohne Suffix
    assert parse_iso_date("1980 j") is None


def test_parse_iso_date_relative_dekade():
    """Relative Position innerhalb einer Dekade ('Mitte 1980er', 'mid-1990s',
    'Late 2000s') spiegelt _RELATIVE_YEAR auf die Dekaden-Achse.

    Konvention: Anfang/early=Jahr 0, Mitte/mid=Jahr 5, Ende/late=Jahr 9.
    """
    # Deutsche Varianten
    assert parse_iso_date("Anfang 1980er") == "1980-01-01"
    assert parse_iso_date("Mitte 1980er") == "1985-01-01"
    assert parse_iso_date("Ende 1980er") == "1989-01-01"
    assert parse_iso_date("Anfang 1990er") == "1990-01-01"
    assert parse_iso_date("Mitte 2000er") == "2005-01-01"
    assert parse_iso_date("Ende 1990er") == "1999-01-01"
    # Mit "Jahre"-Trailer (wie _DECADE)
    assert parse_iso_date("Anfang 1990er Jahre") == "1990-01-01"
    assert parse_iso_date("Mitte 1980er Jahre") == "1985-01-01"
    # Englische Varianten
    assert parse_iso_date("early 1980s") == "1980-01-01"
    assert parse_iso_date("mid 1980s") == "1985-01-01"
    assert parse_iso_date("late 1990s") == "1999-01-01"
    # Englisch mit Bindestrich (sehr verbreitet: "mid-1990s")
    assert parse_iso_date("Mid-1980s") == "1985-01-01"
    assert parse_iso_date("Late-1990s") == "1999-01-01"
    assert parse_iso_date("Early-2000s") == "2000-01-01"
    # Case-insensitive
    assert parse_iso_date("MITTE 1980er") == "1985-01-01"
    assert parse_iso_date("MID 1980s") == "1985-01-01"
    # Kombination mit bestehenden Modifikatoren
    assert parse_iso_date("ca. Mitte 1980er") == "1985-01-01"
    assert parse_iso_date("(Late 1990s)") == "1999-01-01"
    assert parse_iso_date("Mitte 1980er.") == "1985-01-01"


def test_parse_iso_date_relative_dekade_ungueltig_und_disjunkt():
    """Out-of-Range, fehlende Suffixe, unbekannte Schluesselwoerter → None.
    Disjunkt zu _RELATIVE_YEAR und _DECADE (kein Regress)."""
    # 2-stellige Dekade (mehrdeutig, spiegelt _DECADE-Ablehnung)
    assert parse_iso_date("Anfang 80er") is None
    assert parse_iso_date("Mid 90s") is None
    # Jahr ausserhalb [1800, 2999]
    assert parse_iso_date("Mitte 1700er") is None
    assert parse_iso_date("Anfang 3000er") is None
    # Unbekanntes Position-Wort
    assert parse_iso_date("Foo 1980er") is None
    assert parse_iso_date("herum 1980er") is None
    # Disjunkt zu _RELATIVE_YEAR: "Mitte 1980" (ohne er/s) bleibt Juli 1980
    assert parse_iso_date("Mitte 1980") == "1980-07-01"
    assert parse_iso_date("Mid-2024") == "2024-07-01"
    # Disjunkt zu _DECADE: "1980er" ohne Position bleibt Dekaden-Start
    assert parse_iso_date("1980er") == "1980-01-01"
    assert parse_iso_date("1990s") == "1990-01-01"


def test_parse_iso_date_mehrjahres_spanne():
    """Mehrjahres-Spanne ('1950-1960') ergibt das Startjahr (analog Dekaden)."""
    # ASCII-Bindestrich (gaengigste Form in Sammlungs-Notizen)
    assert parse_iso_date("1950-1960") == "1950-01-01"
    assert parse_iso_date("1985-1990") == "1985-01-01"
    assert parse_iso_date("1900-2000") == "1900-01-01"
    # En-Dash (U+2013, typografische Spanne-Notation)
    assert parse_iso_date("1950–1960") == "1950-01-01"
    # Em-Dash (U+2014, Word-Autoformat in deutschen Texten fuer Spannen)
    assert parse_iso_date("1950—1960") == "1950-01-01"
    # Minus-Zeichen (U+2212, typografisch sauberes Print-/LaTeX-Minus)
    assert parse_iso_date("1950−1960") == "1950-01-01"
    # Slash-Separator (Tagebuecher mit Schraegstrich-Trenner)
    assert parse_iso_date("1950/1960") == "1950-01-01"
    # Mit Whitespace um den Separator
    assert parse_iso_date("1950 - 1960") == "1950-01-01"
    assert parse_iso_date("1950 – 1960") == "1950-01-01"
    assert parse_iso_date("1950 — 1960") == "1950-01-01"
    assert parse_iso_date("1950 − 1960") == "1950-01-01"
    assert parse_iso_date("1950 / 1960") == "1950-01-01"
    # Inverted Spanne (Tippfehler) → erstes Jahr, spiegelt parse_range
    assert parse_iso_date("1985-1980") == "1985-01-01"
    # Kombinationen mit bestehenden Modifikatoren
    assert parse_iso_date("ca. 1950-1960") == "1950-01-01"
    assert parse_iso_date("circa 1950–1960") == "1950-01-01"
    assert parse_iso_date("(1950-1960)") == "1950-01-01"
    assert parse_iso_date("[1950-1960]") == "1950-01-01"
    assert parse_iso_date("1950-1960.") == "1950-01-01"
    assert parse_iso_date("1950-1960,") == "1950-01-01"


def test_parse_iso_date_mehrjahres_spanne_ungueltig():
    """Jahr ausserhalb [1800, 2999] in einem der zwei Teile → None."""
    assert parse_iso_date("1700-1960") is None
    assert parse_iso_date("1950-3000") is None
    assert parse_iso_date("1700-1750") is None
    # Bestehende YYYY-MM-/MM-YYYY-/Decade-Formen bleiben unveraendert (kein Regress)
    assert parse_iso_date("1950-12") == "1950-12-01"  # YYYY-MM (Monat 1-12)
    assert parse_iso_date("06-2024") == "2024-06-01"  # MM-YYYY
    assert parse_iso_date("1980er") == "1980-01-01"   # Dekade
    assert parse_iso_date("1950") == "1950-01-01"     # Einzeljahr


def test_parse_iso_date_mehrjahres_spanne_wortform():
    """Wort-Form der Mehrjahres-Spanne ('1950 bis 1960' / '1950 to 1960')
    spiegelt die symbolische Form (Startjahr als ISO-Datum)."""
    # Deutsche Wort-Form (typisch in geerbten Sammlungs-Tagebuechern)
    assert parse_iso_date("1950 bis 1960") == "1950-01-01"
    assert parse_iso_date("1985 bis 1990") == "1985-01-01"
    assert parse_iso_date("2000 bis 2024") == "2000-01-01"
    # Englische Varianten (auktionskataloge mit EN-Notation, mining-Logs)
    assert parse_iso_date("1950 to 1960") == "1950-01-01"
    assert parse_iso_date("1950 till 1960") == "1950-01-01"
    assert parse_iso_date("1950 until 1960") == "1950-01-01"
    # Case-insensitiv (BIS/TO/Till/Until aus Caps-Lock-Notizen)
    assert parse_iso_date("1950 BIS 1960") == "1950-01-01"
    assert parse_iso_date("1950 To 1960") == "1950-01-01"
    # Inverted Spanne (Tippfehler) liefert das erste Jahr, spiegelt _YEAR_RANGE
    assert parse_iso_date("1985 bis 1980") == "1985-01-01"
    # Kombinationen mit bestehenden Modifikatoren (ca./Klammern/Trailing-Punkt)
    assert parse_iso_date("ca. 1950 bis 1960") == "1950-01-01"
    assert parse_iso_date("(1950 to 1960)") == "1950-01-01"
    assert parse_iso_date("1950 bis 1960.") == "1950-01-01"


def test_parse_iso_date_mehrjahres_spanne_wortform_ungueltig():
    """Jahr ausserhalb [1800, 2999] oder fehlender Whitespace → None."""
    assert parse_iso_date("1700 bis 1960") is None
    assert parse_iso_date("1950 to 3000") is None
    # Ohne Whitespace um das Schluesselwort kein Match (lebt von der Satzform)
    assert parse_iso_date("1950bis1960") is None
    assert parse_iso_date("1950to1960") is None
    # Unbekanntes Schluesselwort
    assert parse_iso_date("1950 oder 1960") is None
    # 'zwischen 1950 und 1960' braucht eine andere Pattern-Struktur und ist
    # bewusst nicht abgedeckt (das Wort 'zwischen' allein ist kein Range-
    # Separator zwischen zwei Jahren, sondern ein Praefix vor dem ersten).
    assert parse_iso_date("zwischen 1950 und 1960") is None


def test_parse_iso_date_quartale():
    """Quartal + Jahr ergeben den Quartals-Startmonat (Jan/Apr/Jul/Okt)."""
    # Kurzform "Q1 2024" mit verschiedenen Separatoren
    assert parse_iso_date("Q1 2024") == "2024-01-01"
    assert parse_iso_date("Q2 2024") == "2024-04-01"
    assert parse_iso_date("Q3 2024") == "2024-07-01"
    assert parse_iso_date("Q4 2024") == "2024-10-01"
    assert parse_iso_date("Q1/2024") == "2024-01-01"
    assert parse_iso_date("Q3-1985") == "1985-07-01"
    assert parse_iso_date("Q3.1985") == "1985-07-01"
    # Quartal nachgestellt ("1Q 2024")
    assert parse_iso_date("1Q 2024") == "2024-01-01"
    assert parse_iso_date("3Q/1985") == "1985-07-01"
    # Langform DE
    assert parse_iso_date("1. Quartal 2024") == "2024-01-01"
    assert parse_iso_date("3. Quartal 1985") == "1985-07-01"
    assert parse_iso_date("Quartal 1 2024") == "2024-01-01"
    assert parse_iso_date("Quartal 4 1999") == "1999-10-01"
    # Langform EN
    assert parse_iso_date("3. Quarter 1985") == "1985-07-01"
    assert parse_iso_date("Quarter 2 2020") == "2020-04-01"
    # Case-insensitive
    assert parse_iso_date("q1 2024") == "2024-01-01"
    assert parse_iso_date("QUARTAL 1 2024") == "2024-01-01"
    # Mit Annaeherungspraefix
    assert parse_iso_date("ca. Q1 2024") == "2024-01-01"
    assert parse_iso_date("circa 3. Quartal 1985") == "1985-07-01"
    # Mit trailing Satzzeichen
    assert parse_iso_date("Q1 2024.") == "2024-01-01"


def test_parse_iso_date_quartale_ungueltig():
    assert parse_iso_date("Q5 2024") is None      # nur Q1-Q4
    assert parse_iso_date("Q0 2024") is None
    assert parse_iso_date("Q1 1700") is None      # Jahr ausserhalb 1800-2999
    assert parse_iso_date("Q1") is None           # Jahr fehlt
    assert parse_iso_date("Quartal 2024") is None  # Quartalzahl fehlt


def test_parse_iso_date_quartale_langform_year_first():
    """Year-first Langform-Quartal ('2024 Quartal 1', '2024-1. Quartal')."""
    # Verschiedene Separatoren zwischen Jahr und Langform
    assert parse_iso_date("2024 Quartal 1") == "2024-01-01"
    assert parse_iso_date("2024 Quartal 2") == "2024-04-01"
    assert parse_iso_date("2024 Quartal 3") == "2024-07-01"
    assert parse_iso_date("2024 Quartal 4") == "2024-10-01"
    # Zahl-vor-Wort Reihenfolge ("1. Quartal")
    assert parse_iso_date("2024 1. Quartal") == "2024-01-01"
    assert parse_iso_date("2024 3. Quartal") == "2024-07-01"
    assert parse_iso_date("1985 4. Quartal") == "1985-10-01"
    # Bindestrich / Komma / Punkt als Separator zwischen Jahr und Langform
    assert parse_iso_date("2024-1. Quartal") == "2024-01-01"
    assert parse_iso_date("2024-Quartal 1") == "2024-01-01"
    assert parse_iso_date("2024,Quartal 1") == "2024-01-01"
    assert parse_iso_date("2024.Quartal 1") == "2024-01-01"
    # Englische Langform Quarter
    assert parse_iso_date("2024 Quarter 1") == "2024-01-01"
    assert parse_iso_date("1985 3. Quarter") == "1985-07-01"
    assert parse_iso_date("1985-Quarter 2") == "1985-04-01"
    # Case-insensitive
    assert parse_iso_date("2024 quartal 1") == "2024-01-01"
    assert parse_iso_date("2024 QUARTAL 1") == "2024-01-01"
    # Kombiniert mit Annaeherungspraefix / Klammern / trailing Satzzeichen
    assert parse_iso_date("ca. 2024 Quartal 1") == "2024-01-01"
    assert parse_iso_date("(2024 Quartal 1)") == "2024-01-01"
    assert parse_iso_date("2024 Quartal 1.") == "2024-01-01"
    # Bestehende Year-Last-Langform unveraendert (kein Regress)
    assert parse_iso_date("1. Quartal 2024") == "2024-01-01"
    assert parse_iso_date("Quartal 1 2024") == "2024-01-01"
    # Ungueltig: Q0/Q5, Jahr ausserhalb Spanne
    assert parse_iso_date("2024 Quartal 5") is None
    assert parse_iso_date("2024 Quartal 0") is None
    assert parse_iso_date("1700 Quartal 1") is None
    assert parse_iso_date("3000 Quartal 1") is None


def test_parse_iso_date_quartale_year_first():
    """Year-first Quartals-Notation ('2024-Q1', '2024Q1') - Excel/Finanzreports."""
    # Verschiedene Separatoren zwischen Jahr und Q
    assert parse_iso_date("2024-Q1") == "2024-01-01"
    assert parse_iso_date("2024-Q2") == "2024-04-01"
    assert parse_iso_date("2024-Q3") == "2024-07-01"
    assert parse_iso_date("2024-Q4") == "2024-10-01"
    assert parse_iso_date("2024/Q1") == "2024-01-01"
    assert parse_iso_date("2024 Q1") == "2024-01-01"
    assert parse_iso_date("2024.Q1") == "2024-01-01"
    assert parse_iso_date("2024,Q1") == "2024-01-01"
    # Compact-Form ohne Separator (Excel-Auto-Format)
    assert parse_iso_date("2024Q1") == "2024-01-01"
    assert parse_iso_date("1985Q3") == "1985-07-01"
    assert parse_iso_date("1999Q4") == "1999-10-01"
    # Year-first mit Q nachgestellt: "2024-1Q"
    assert parse_iso_date("2024-1Q") == "2024-01-01"
    assert parse_iso_date("2024 3Q") == "2024-07-01"
    # Case-insensitive (Excel-Default ist GROSS, manche Tools klein)
    assert parse_iso_date("2024-q1") == "2024-01-01"
    assert parse_iso_date("2024q1") == "2024-01-01"
    # Kombiniert mit Annaeherungspraefix / Klammern / trailing Satzzeichen
    assert parse_iso_date("ca. 2024-Q1") == "2024-01-01"
    assert parse_iso_date("(2024-Q1)") == "2024-01-01"
    assert parse_iso_date("2024-Q1.") == "2024-01-01"
    # Bestehende Year-Last-Form unveraendert (kein Regress)
    assert parse_iso_date("Q1 2024") == "2024-01-01"
    assert parse_iso_date("1Q 2024") == "2024-01-01"
    # Ungueltig: Q5/Q0, Jahr ausserhalb Spanne
    assert parse_iso_date("2024-Q5") is None
    assert parse_iso_date("2024-Q0") is None
    assert parse_iso_date("1700-Q1") is None
    assert parse_iso_date("3000-Q1") is None


def test_parse_iso_date_halbjahr():
    """Halbjahres-Notation (Kurz-/Lang-/Year-First, DE/EN) spiegelt das
    Quartals-Vokabular auf die 6-Monats-Achse. H1 → Januar, H2 → Juli."""
    # Kurzform Q-Stil: "H1 2024", verschiedene Separatoren
    assert parse_iso_date("H1 2024") == "2024-01-01"
    assert parse_iso_date("H2 2024") == "2024-07-01"
    assert parse_iso_date("H1/2024") == "2024-01-01"
    assert parse_iso_date("H2-2024") == "2024-07-01"
    assert parse_iso_date("H1.2024") == "2024-01-01"
    assert parse_iso_date("H2,1985") == "1985-07-01"
    # Kurzform Postfix: "1H 2024"
    assert parse_iso_date("1H 2024") == "2024-01-01"
    assert parse_iso_date("2H/1985") == "1985-07-01"
    # Langform DE
    assert parse_iso_date("1. Halbjahr 2024") == "2024-01-01"
    assert parse_iso_date("2. Halbjahr 1985") == "1985-07-01"
    assert parse_iso_date("Halbjahr 1 2024") == "2024-01-01"
    assert parse_iso_date("Halbjahr 2 1999") == "1999-07-01"
    # Langform EN (Compound mit/ohne Bindestrich)
    assert parse_iso_date("1. Halfyear 2024") == "2024-01-01"
    assert parse_iso_date("2. Half-year 1985") == "1985-07-01"
    assert parse_iso_date("Halfyear 2 2020") == "2020-07-01"
    assert parse_iso_date("Half-year 1 2020") == "2020-01-01"
    # Case-insensitive
    assert parse_iso_date("h1 2024") == "2024-01-01"
    assert parse_iso_date("HALBJAHR 1 2024") == "2024-01-01"
    # Year-first Kurzform: "2024-H1", "2024H1"
    assert parse_iso_date("2024-H1") == "2024-01-01"
    assert parse_iso_date("2024-H2") == "2024-07-01"
    assert parse_iso_date("2024 H1") == "2024-01-01"
    assert parse_iso_date("2024H1") == "2024-01-01"
    assert parse_iso_date("2024-1H") == "2024-01-01"
    assert parse_iso_date("2024 2H") == "2024-07-01"
    # Year-first Langform
    assert parse_iso_date("2024 1. Halbjahr") == "2024-01-01"
    assert parse_iso_date("2024 Halbjahr 2") == "2024-07-01"
    assert parse_iso_date("2024-1. Halbjahr") == "2024-01-01"
    assert parse_iso_date("2024,Halbjahr 1") == "2024-01-01"
    # Kombiniert mit Annaeherungspraefix / Klammern / trailing Satzzeichen
    assert parse_iso_date("ca. H1 2024") == "2024-01-01"
    assert parse_iso_date("(H1 2024)") == "2024-01-01"
    assert parse_iso_date("H1 2024.") == "2024-01-01"


def test_parse_iso_date_halbjahr_ungueltig():
    """H0/H3, Jahr ausserhalb Spanne → None; bestehende Pattern bleiben."""
    assert parse_iso_date("H0 2024") is None
    assert parse_iso_date("H3 2024") is None
    assert parse_iso_date("H1 1700") is None
    assert parse_iso_date("H1 3000") is None
    assert parse_iso_date("H1") is None              # Jahr fehlt
    assert parse_iso_date("Halbjahr 2024") is None    # H-Zahl fehlt
    assert parse_iso_date("2024-H3") is None
    assert parse_iso_date("3000-H1") is None
    # Bestehende Q-/Seasons-/YYYY-MM-Patterns unveraendert (kein Regress)
    assert parse_iso_date("Q1 2024") == "2024-01-01"
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("2024-06") == "2024-06-01"
    assert parse_iso_date("1985 bis 1990") == "1985-01-01"


def test_parse_iso_date_jahreszeiten_ungueltig():
    assert parse_iso_date("Sommer 1700") is None    # ausserhalb 1800-2999
    assert parse_iso_date("Foosaison 2020") is None  # kein bekannter Saison-Name
    assert parse_iso_date("Spring") is None          # Jahreszeit ohne Jahr
    # "Winter 1999/2000" ist mehrdeutig (Jahreswechsel) → bewusst nicht parsen
    assert parse_iso_date("Winter 1999/2000") is None


def test_parse_iso_date_numerisches_monat_jahr():
    """Numerisches MM/YYYY (06/2024, 6-2024, 06.2024) ist eine Monatsangabe → -01."""
    assert parse_iso_date("06/2024") == "2024-06-01"
    assert parse_iso_date("6/2024") == "2024-06-01"
    assert parse_iso_date("1/2024") == "2024-01-01"
    assert parse_iso_date("12/2024") == "2024-12-01"
    # Andere Separatoren
    assert parse_iso_date("06-2024") == "2024-06-01"
    assert parse_iso_date("06.2024") == "2024-06-01"
    # Ungueltige Monatswerte → None
    assert parse_iso_date("13/2024") is None
    assert parse_iso_date("0/2024") is None
    assert parse_iso_date("00/2024") is None
    # Jahr ausserhalb [1800, 2999]
    assert parse_iso_date("06/1700") is None
    # 2-stelliges Jahr ist nicht erfasst (zu mehrdeutig)
    assert parse_iso_date("06/24") is None
    # YYYY-MM bleibt unveraendert (kein Regress)
    assert parse_iso_date("2024-06") == "2024-06-01"
    assert parse_iso_date("2024/06") == "2024-06-01"


def test_parse_iso_date_wochentag_praefix():
    """Wochentag-Praefixe (DE/EN, lang/kurz) werden gestrippt, Rest re-parst."""
    # DE Vollform + Komma
    assert parse_iso_date("Donnerstag, 13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("Montag, 1.1.2020") == "2020-01-01"
    # DE Kurzform mit/ohne Punkt
    assert parse_iso_date("Mo 13.06.2024") == "2024-06-13"
    assert parse_iso_date("Mo. 13.06.2024") == "2024-06-13"
    assert parse_iso_date("Di 13.6.2024") == "2024-06-13"
    assert parse_iso_date("Fr 1. Januar 2024") == "2024-01-01"
    # EN Vollform + Komma
    assert parse_iso_date("Thursday, June 13, 2024") == "2024-06-13"
    assert parse_iso_date("Sunday, May 5, 2020") == "2020-05-05"
    # EN Kurzform
    assert parse_iso_date("Mon, 13.06.2024") == "2024-06-13"
    assert parse_iso_date("Thu Jun 13 2024") == "2024-06-13"
    assert parse_iso_date("Thu 2024-06-13") == "2024-06-13"
    # Case-insensitive
    assert parse_iso_date("DONNERSTAG, 13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("mo 13.06.2024") == "2024-06-13"
    # Wochentag allein → None (kein Datum-Rest)
    assert parse_iso_date("Donnerstag") is None
    assert parse_iso_date("Mon") is None
    # Wochentag + Unsinn → None
    assert parse_iso_date("Mon 99") is None
    # Bestehende Datumsangaben ohne Wochentag bleiben gleich (kein Regress)
    assert parse_iso_date("May 2024") == "2024-05-01"
    assert parse_iso_date("May 5, 2020") == "2020-05-05"


def test_parse_iso_date_temporale_praeposition():
    """Temporale Praeposition (im/in/vom/am/von/on) vor dem Datum wird gestrippt.

    Spiegelt das _APPROX_PREFIX-Konzept (Praefix wird gestrippt, Datum bleibt
    unveraendert) auf temporale Satz-Praepositionen, wie sie in Sammlungs-Notizen
    in vollstaendigen Saetzen auftauchen.
    """
    # DE "im" + Jahr
    assert parse_iso_date("im 2024") == "2024-01-01"
    # DE "im" + Monat + Jahr
    assert parse_iso_date("im Juni 2024") == "2024-06-01"
    assert parse_iso_date("Im Juni 2024") == "2024-06-01"
    # DE "im" + Saison + Jahr
    assert parse_iso_date("im Sommer 1985") == "1985-06-01"
    assert parse_iso_date("Im Sommer 1985") == "1985-06-01"
    assert parse_iso_date("im Frühling 2020") == "2020-03-01"
    # DE "im" + Jahrzehnt
    assert parse_iso_date("im 1980er") == "1980-01-01"
    # DE "im Jahr"
    assert parse_iso_date("im Jahr 1985") == "1985-01-01"
    assert parse_iso_date("Im Jahr 2024") == "2024-01-01"
    assert parse_iso_date("im Jahre 1985") == "1985-01-01"
    # DE "in dem Jahr" / "in den Jahren" (Vollform mit Artikel)
    assert parse_iso_date("in dem Jahr 1985") == "1985-01-01"
    assert parse_iso_date("in den Jahren 1985-1990") == "1985-01-01"
    # DE "vom" - typisch fuer Foto-/Brief-Captions
    assert parse_iso_date("vom 13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("vom 13.06.2024") == "2024-06-13"
    assert parse_iso_date("vom 2024-06-13") == "2024-06-13"
    # DE "von" + Jahr
    assert parse_iso_date("von 1985") == "1985-01-01"
    # DE "am" - typisch fuer "aufgenommen am"-Captions
    assert parse_iso_date("am 13.06.2024") == "2024-06-13"
    assert parse_iso_date("am 13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("Am 1. Januar 2020") == "2020-01-01"
    # EN "in" + Monat/Jahr
    assert parse_iso_date("in 2024") == "2024-01-01"
    assert parse_iso_date("in June 2024") == "2024-06-01"
    assert parse_iso_date("in the year 1985") == "1985-01-01"
    assert parse_iso_date("in the year 2024") == "2024-01-01"
    assert parse_iso_date("in the 1980s") == "1980-01-01"
    # EN "on" + voller Datums-Form
    assert parse_iso_date("on June 13, 2024") == "2024-06-13"
    assert parse_iso_date("on 2024-06-13") == "2024-06-13"
    # "Jahr"/"year" als Listen-Stichwort ohne Praeposition
    assert parse_iso_date("Jahr 1985") == "1985-01-01"
    assert parse_iso_date("Jahre 1985") == "1985-01-01"
    assert parse_iso_date("year 2024") == "2024-01-01"
    assert parse_iso_date("Year 2024") == "2024-01-01"
    # Case-insensitive (DE/EN gemischt)
    assert parse_iso_date("IM JUNI 2024") == "2024-06-01"
    assert parse_iso_date("VOM 13.06.2024") == "2024-06-13"
    assert parse_iso_date("ON JUNE 13, 2024") == "2024-06-13"
    # Praeposition + Quartal/Halbjahr
    assert parse_iso_date("im Q1 2024") == "2024-01-01"
    assert parse_iso_date("im H1 2024") == "2024-01-01"
    assert parse_iso_date("im 1. Quartal 2024") == "2024-01-01"
    # Verkettete Praefixe (rekursive Strippung): semantisch redundant, aber
    # unschaedlich - die Rekursion strippt einen nach dem anderen.
    assert parse_iso_date("im ca. 1985") == "1985-01-01"
    assert parse_iso_date("ca. im Juni 2024") == "2024-06-01"
    # Praefix ohne Inhalt / mit ungueltigem Rest → None
    assert parse_iso_date("im") is None
    assert parse_iso_date("vom") is None
    assert parse_iso_date("Jahr") is None
    assert parse_iso_date("im abc") is None
    assert parse_iso_date("im garten") is None
    # Praefix vor Jahr ausserhalb 1800-2999 → None
    assert parse_iso_date("im 1700") is None
    assert parse_iso_date("im Jahr 1700") is None
    # Wortanfang muss exakt sein - kein Anschneiden laengerer Worte
    assert parse_iso_date("important 2024") is None
    assert parse_iso_date("immer 1985") is None
    # Bestehende Datumsangaben ohne Praeposition bleiben gleich (kein Regress)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("Sommer 1985") == "1985-06-01"
    assert parse_iso_date("13.06.2024") == "2024-06-13"


def test_parse_iso_date_bindestrich_separator_mit_monatsname():
    """Bindestrich als Separator zwischen Tag/Monatsname/Jahr (Oracle/Log-Exporte)."""
    # DD-MMM-YYYY (Oracle-Default-Format)
    assert parse_iso_date("01-Jun-2024") == "2024-06-01"
    assert parse_iso_date("13-Jun-2024") == "2024-06-13"
    assert parse_iso_date("31-Dez-1999") == "1999-12-31"
    # Deutsche Vollform
    assert parse_iso_date("13-Juni-2024") == "2024-06-13"
    # GROSSGESCHRIEBEN (Oracle TO_CHAR-Default)
    assert parse_iso_date("01-JAN-2024") == "2024-01-01"
    assert parse_iso_date("31-DEC-2024") == "2024-12-31"
    # Englische Reihenfolge MMM-DD-YYYY
    assert parse_iso_date("Jun-13-2024") == "2024-06-13"
    assert parse_iso_date("June-13-2024") == "2024-06-13"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("13/Jun/2024") == "2024-06-13"
    # 2-stellige Jahresangaben weiterhin nicht akzeptiert (zu mehrdeutig)
    assert parse_iso_date("01-Jun-99") is None
    # Unbekannter Monat / Jahr ausserhalb 1800-2999
    assert parse_iso_date("01-Foo-2024") is None
    assert parse_iso_date("01-Jun-1700") is None


def test_parse_iso_date_slash_separator_mit_monatsname():
    """Slash als Separator zwischen Tag/Monatsname/Jahr (gaengig in Exports)."""
    # DD/Mon/YYYY
    assert parse_iso_date("13/Jun/2024") == "2024-06-13"
    assert parse_iso_date("13/Juni/2024") == "2024-06-13"
    # Mon/YYYY
    assert parse_iso_date("Mai/2024") == "2024-05-01"
    assert parse_iso_date("Juni/2024") == "2024-06-01"
    assert parse_iso_date("Jun/2024") == "2024-06-01"
    # Englisch mit Slash
    assert parse_iso_date("Jun/13/2024") == "2024-06-13"
    assert parse_iso_date("June/13/2024") == "2024-06-13"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("13 Juni 2024") == "2024-06-13"
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    # Unbekannter Separator → None
    assert parse_iso_date("Juni\\2024") is None


def test_parse_iso_date_kurzform_mit_punkt_und_slash():
    """Punkt nach Monatsname-Kurzform mit Slash-Separator: '5/Jun./2024'."""
    assert parse_iso_date("5/Jun./2024") == "2024-06-05"
    assert parse_iso_date("13/Jun./2024") == "2024-06-13"
    assert parse_iso_date("31/Dec./2024") == "2024-12-31"
    # Mit DE-Vollform plus Punkt (eher selten, aber unschaedlich)
    assert parse_iso_date("13/Juni./2024") == "2024-06-13"
    # Mit Bindestrich-Separator
    assert parse_iso_date("13-Jun.-2024") == "2024-06-13"
    # Mit Punkt-Separator zwischen Tag und Monat plus Trail-Punkt am Monat
    assert parse_iso_date("13.Jun.2024") == "2024-06-13"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("13/Jun/2024") == "2024-06-13"
    assert parse_iso_date("13-Jun-2024") == "2024-06-13"
    assert parse_iso_date("Jun. 13, 2024") == "2024-06-13"


def test_parse_iso_date_komma_vor_jahr_de():
    """DE-Format mit Komma vor dem Jahr: '13. März, 2024'."""
    assert parse_iso_date("13. März, 2024") == "2024-03-13"
    assert parse_iso_date("13. Juni, 2024") == "2024-06-13"
    assert parse_iso_date("1. Januar, 2020") == "2020-01-01"
    # Kurzform mit Komma
    assert parse_iso_date("13. Jun, 2024") == "2024-06-13"
    # Komma direkt nach Monatsname ohne Space (Excel-CSV-Eigenheit)
    assert parse_iso_date("13.Juni,2024") == "2024-06-13"
    # Mit Annaeherungspraefix
    assert parse_iso_date("ca. 13. März, 2024") == "2024-03-13"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("13. März 2024") == "2024-03-13"
    # Ungueltiger Tag bleibt None
    assert parse_iso_date("32. Juni, 2024") is None


def test_parse_iso_date_monat_jahr_bindestrich():
    """Bindestrich zwischen Monatsname und Jahr ('Jun-2024', 'Juni-2024')."""
    # Deutsche Kurz-/Vollformen
    assert parse_iso_date("Juni-2024") == "2024-06-01"
    assert parse_iso_date("Jun-2024") == "2024-06-01"
    assert parse_iso_date("Mai-2024") == "2024-05-01"
    assert parse_iso_date("Dezember-1999") == "1999-12-01"
    # Englisch
    assert parse_iso_date("Dec-1999") == "1999-12-01"
    assert parse_iso_date("March-2024") == "2024-03-01"
    assert parse_iso_date("May-2020") == "2020-05-01"
    # Mit Punkt nach Kurzform ("Jun.-2024" - selten, aber unschaedlich)
    assert parse_iso_date("Jun.-2024") == "2024-06-01"
    # Case-insensitive (via Normalisierung)
    assert parse_iso_date("JUN-2024") == "2024-06-01"
    # Umlaut wird normalisiert
    assert parse_iso_date("März-2022") == "2022-03-01"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("Juni/2024") == "2024-06-01"
    assert parse_iso_date("Juni, 2024") == "2024-06-01"
    # Voll qualifizierte DD-Mon-YYYY-Notation bleibt erhalten
    assert parse_iso_date("13-Jun-2024") == "2024-06-13"
    assert parse_iso_date("Jun-13-2024") == "2024-06-13"
    # Unbekannter Monat → None
    assert parse_iso_date("Foo-2024") is None
    # Jahr ausserhalb 1800-2999
    assert parse_iso_date("Jun-1700") is None


def test_parse_iso_date_umschliessende_klammern():
    """Zitierte Datumsangaben in Klammern/Anfuehrungszeichen werden gestrippt."""
    # ASCII-Klammern / Anfuehrungszeichen
    assert parse_iso_date("(2024)") == "2024-01-01"
    assert parse_iso_date("[2024]") == "2024-01-01"
    assert parse_iso_date("{2024}") == "2024-01-01"
    assert parse_iso_date("(2024-06-13)") == "2024-06-13"
    assert parse_iso_date("(13.06.2024)") == "2024-06-13"
    assert parse_iso_date('"2024-06-13"') == "2024-06-13"
    assert parse_iso_date("'2024-06-13'") == "2024-06-13"
    # Typografische Varianten (Schweizer/Deutsche Texte)
    assert parse_iso_date("«2024-06-13»") == "2024-06-13"
    assert parse_iso_date("‹2024-06-13›") == "2024-06-13"
    assert parse_iso_date('„2024-06-13"') == "2024-06-13"
    assert parse_iso_date("„2024-06-13“") == "2024-06-13"
    # Geschachtelt mit Praefixen/Suffixen
    assert parse_iso_date("[ca. 1985]") == "1985-01-01"
    assert parse_iso_date("«Sommer 1985»") == "1985-06-01"
    assert parse_iso_date("(2024-06-13.)") == "2024-06-13"
    # Leeres Innenleben → None
    assert parse_iso_date("()") is None
    assert parse_iso_date('""') is None
    # Klammer mitten im Text wird NICHT angetastet (keine falschen Treffer)
    assert parse_iso_date("abc(def)") is None


def test_parse_iso_date_trailing_satzzeichen():
    """Sammlungs-Notizen mit Datum am Satzende: trailing .!?,;: gehoert nicht zum Datum."""
    # Punkt nach ISO-Datum / DE-Datum / Jahr / Monat+Jahr
    assert parse_iso_date("2024-06-13.") == "2024-06-13"
    assert parse_iso_date("13.06.2024.") == "2024-06-13"
    assert parse_iso_date("1985.") == "1985-01-01"
    assert parse_iso_date("Juni 2024.") == "2024-06-01"
    assert parse_iso_date("13. Juni 2024.") == "2024-06-13"
    assert parse_iso_date("Jun 13, 2024.") == "2024-06-13"
    # Andere Satzzeichen
    assert parse_iso_date("1985!") == "1985-01-01"
    assert parse_iso_date("1985?") == "1985-01-01"
    assert parse_iso_date("2024;") == "2024-01-01"
    assert parse_iso_date("2024:") == "2024-01-01"
    # Mehrere Satzzeichen am Ende
    assert parse_iso_date("2024-06-13!?") == "2024-06-13"
    assert parse_iso_date("13.06.2024.,;") == "2024-06-13"
    # Kombiniert mit Annaeherungspraefix
    assert parse_iso_date("ca. 1985.") == "1985-01-01"
    assert parse_iso_date("circa 2024-06-13.") == "2024-06-13"
    # Kombiniert mit Jahreszeit
    assert parse_iso_date("Sommer 1985.") == "1985-06-01"
    # Wenn der Rest ungueltig bleibt → None (nicht versehentlich was retten)
    assert parse_iso_date("abc.") is None
    assert parse_iso_date("unbekannt.") is None


def test_parse_iso_date_trailing_paren_annotation():
    """Trailing parenthesized Annotation ("13.06.2024 (Foto)") wird gestrippt.

    Sammlungs-Notizen haengen oft eine Kontext-/Provenienz-Annotation in
    runden/eckigen/geschwungenen Klammern an das Datum an; das Datum selbst
    bleibt parsbar. Strip + Rekursion analog _TRAILING_TIME/_TRAILING_PUNCT.
    """
    # Runde Klammern (haeufigste Form)
    assert parse_iso_date("13.06.2024 (Foto)") == "2024-06-13"
    assert parse_iso_date("2024-06-13 (verifiziert)") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024 (gefunden)") == "2024-06-13"
    # Eckige Klammern (technische/maschinen-lesbare Annotation)
    assert parse_iso_date("2024-06-13 [Foto]") == "2024-06-13"
    assert parse_iso_date("13.06.2024 [verifiziert]") == "2024-06-13"
    # Geschwungene Klammern (selten, aber spec-konform)
    assert parse_iso_date("1985 {geerbt}") == "1985-01-01"
    # Mit Annaeherungspraefix kombiniert
    assert parse_iso_date("ca. 1985 (Schaetzung)") == "1985-01-01"
    assert parse_iso_date("circa 2024-06-13 (verifiziert)") == "2024-06-13"
    # Mit Jahreszeit kombiniert
    assert parse_iso_date("Sommer 1985 (geerbt)") == "1985-06-01"
    assert parse_iso_date("Mitte 1985 (Schaetzung)") == "1985-07-01"
    # Mit Dekaden-Form kombiniert
    assert parse_iso_date("1980er (Sammler-Notiz)") == "1980-01-01"
    # Mehrere sequentielle Annotationen (Rekursion strippt eine nach der anderen)
    assert parse_iso_date("13.06.2024 (Foto) (gefunden)") == "2024-06-13"
    assert parse_iso_date("2024-06-13 [Foto] (gefunden)") == "2024-06-13"
    assert parse_iso_date("ca. 1985 (Schaetzung) (geerbt)") == "1985-01-01"
    # Annotation + trailing Satzzeichen (beide Strips greifen via Rekursion)
    assert parse_iso_date("2024-06-13 (Foto).") == "2024-06-13"
    assert parse_iso_date("1985 (geerbt)!") == "1985-01-01"
    # Whitespace-Variationen zwischen Datum und Klammer
    assert parse_iso_date("2024-06-13(Foto)") == "2024-06-13"
    assert parse_iso_date("2024-06-13  (Foto)") == "2024-06-13"
    # Mit Inhalt-Inhalt mit Sonderzeichen (Klammern bleiben Single-Level)
    assert parse_iso_date("2024-06-13 (Foto: gut.)") == "2024-06-13"
    assert parse_iso_date("1985 (Schaetzung +/- 2 Jahre)") == "1985-01-01"
    # Leere Klammern werden gestrippt (Annotation ohne Inhalt)
    assert parse_iso_date("2024-06-13 ()") == "2024-06-13"
    # Nur Klammer-Inhalt ohne Datum → None
    assert parse_iso_date("(Foto)") is None
    assert parse_iso_date("[verifiziert]") is None
    # Klammern ohne gueltiges Datum davor → None (Rekursion strippt, Rest ungueltig)
    assert parse_iso_date("abc (Foto)") is None
    # Nur ein offener/schliessender Bracket (unbalanciert) → kein Strip, kein Match
    assert parse_iso_date("2024-06-13 (Foto") is None
    assert parse_iso_date("2024-06-13 Foto)") is None
    # Bestehende Datumsformen ohne Annotation bleiben gleich (kein Regress)
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("Sommer 1985") == "1985-06-01"
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    # Whole-string Klammer-Wrap bleibt von bracket-strip am Anfang behandelt
    # (kein Regress in der bestehenden Wrap-Logik)
    assert parse_iso_date("(2024)") == "2024-01-01"
    assert parse_iso_date("[2024-06-13]") == "2024-06-13"


def test_parse_iso_date_iso_ordinaldatum():
    """ISO 8601 Ordinal-Datum (Tag des Jahres) wird auf das Kalenderdatum projeziert."""
    # ISO-Standard mit Bindestrich
    assert parse_iso_date("2024-165") == "2024-06-13"
    assert parse_iso_date("2024-001") == "2024-01-01"
    assert parse_iso_date("2024-100") == "2024-04-09"
    # Compact-Form (ohne Bindestrich, 7 Ziffern)
    assert parse_iso_date("2024165") == "2024-06-13"
    assert parse_iso_date("2024001") == "2024-01-01"
    # Schaltjahr: Tag 366 ist gueltig in 2024 (Schalt), aber nicht in 2023
    assert parse_iso_date("2024-366") == "2024-12-31"
    assert parse_iso_date("2020-366") == "2020-12-31"
    # 1999 = letzter Tag fuer "365" (nicht Schaltjahr)
    assert parse_iso_date("1999-365") == "1999-12-31"
    # Mit Annaeherungs-/Klammer-Praefix kombinierbar (Rekursion)
    assert parse_iso_date("ca. 2024-165") == "2024-06-13"
    assert parse_iso_date("(2024-165)") == "2024-06-13"
    assert parse_iso_date("2024-165.") == "2024-06-13"
    # YYYY-MM (8-digit YYYYMMDD) bleibt unveraendert (kein Regress)
    assert parse_iso_date("2024-12") == "2024-12-01"
    assert parse_iso_date("20240613") == "2024-06-13"


def test_parse_iso_date_iso_ordinaldatum_ungueltig():
    # Tag 0 / Tag 367 ausserhalb 1..366
    assert parse_iso_date("2024-000") is None
    assert parse_iso_date("2024-367") is None
    # Tag 366 in Nicht-Schaltjahr → None (kein Ueberlauf ins Folgejahr)
    assert parse_iso_date("2023-366") is None
    assert parse_iso_date("1999-366") is None
    # Jahr ausserhalb 1800..2999
    assert parse_iso_date("1700-100") is None
    assert parse_iso_date("3000-100") is None


def test_parse_iso_date_iso_wochendatum():
    """ISO 8601 Wochendatum ergibt den Montag (ohne Tag) bzw. den gewuenschten Tag."""
    # ISO-Standard mit Bindestrich, ohne Tag → Montag der Woche
    assert parse_iso_date("2024-W25") == "2024-06-17"
    assert parse_iso_date("2024-W01") == "2024-01-01"
    assert parse_iso_date("2024-W52") == "2024-12-23"
    # Compact-Form (ohne Bindestrich), wie sie in Logs auftaucht
    assert parse_iso_date("2024W25") == "2024-06-17"
    assert parse_iso_date("2020W01") == "2019-12-30"  # ISO-Wochenjahr ueberlappt!
    # Mit explizitem Wochentag (1=Mo .. 7=So)
    assert parse_iso_date("2024-W25-1") == "2024-06-17"
    assert parse_iso_date("2024-W25-3") == "2024-06-19"
    assert parse_iso_date("2024-W25-7") == "2024-06-23"
    assert parse_iso_date("2024W253") == "2024-06-19"  # Compact mit Tag
    # Case-insensitive (w klein)
    assert parse_iso_date("2024-w25") == "2024-06-17"
    # Kombiniert mit trailing Satzzeichen / Klammer / Praefix
    assert parse_iso_date("2024-W25.") == "2024-06-17"
    assert parse_iso_date("(2024-W25)") == "2024-06-17"
    assert parse_iso_date("ca. 2024-W25") == "2024-06-17"


def test_parse_iso_date_iso_wochendatum_ungueltig():
    # Woche ausserhalb 1..53
    assert parse_iso_date("2024-W00") is None
    assert parse_iso_date("2024-W54") is None
    # Tag ausserhalb 1..7 → matcht das Pattern nicht (faellt auf andere zurueck → None)
    assert parse_iso_date("2024-W25-0") is None
    assert parse_iso_date("2024-W25-8") is None
    # Jahr ausserhalb 1800..2999
    assert parse_iso_date("1700-W01") is None
    # 2024 hat nur 52 Wochen → W53 ist ungueltig
    assert parse_iso_date("2024-W53") is None
    # Aber 2020 hat 53 Wochen → W53 ist gueltig
    assert parse_iso_date("2020-W53") == "2020-12-28"


def test_parse_iso_date_kw_notation():
    """Deutsche KW-Notation ergibt den Montag der genannten Woche."""
    # Verschiedene Separatoren
    assert parse_iso_date("KW 25 2024") == "2024-06-17"
    assert parse_iso_date("KW25/2024") == "2024-06-17"
    assert parse_iso_date("KW 25, 2024") == "2024-06-17"
    assert parse_iso_date("KW25-2024") == "2024-06-17"
    assert parse_iso_date("KW 1 2024") == "2024-01-01"
    # Case-insensitive
    assert parse_iso_date("kw 25 2024") == "2024-06-17"
    assert parse_iso_date("Kw25/2024") == "2024-06-17"
    # Kombiniert mit Annaeherungspraefix / Klammer
    assert parse_iso_date("ca. KW 25 2024") == "2024-06-17"
    assert parse_iso_date("[KW 25 2024]") == "2024-06-17"
    # Ungueltig
    assert parse_iso_date("KW 0 2024") is None
    assert parse_iso_date("KW 54 2024") is None
    assert parse_iso_date("KW 25 1700") is None
    assert parse_iso_date("KW 53 2024") is None  # 2024 hat nur 52 Wochen
    # Ohne Jahr → kein Match (mehrdeutig)
    assert parse_iso_date("KW 25") is None


def test_parse_iso_date_monat_jahr_punkt_separator():
    """Punkt als Separator zwischen Monatsname und Jahr ('Juni.2024', Excel-CSV-Form)."""
    # Deutsche Voll-/Kurzformen
    assert parse_iso_date("Juni.2024") == "2024-06-01"
    assert parse_iso_date("Jun.2024") == "2024-06-01"
    assert parse_iso_date("Mai.2024") == "2024-05-01"
    assert parse_iso_date("Dezember.1999") == "1999-12-01"
    assert parse_iso_date("März.2022") == "2022-03-01"
    # Englisch
    assert parse_iso_date("Dec.1999") == "1999-12-01"
    assert parse_iso_date("March.2024") == "2024-03-01"
    assert parse_iso_date("May.2020") == "2020-05-01"
    # Case-insensitive (via Normalisierung)
    assert parse_iso_date("JUN.2024") == "2024-06-01"
    assert parse_iso_date("dec.2024") == "2024-12-01"
    # Roemische Monatsziffern mit Punkt-Separator
    assert parse_iso_date("VI.2024") == "2024-06-01"
    assert parse_iso_date("XII.1999") == "1999-12-01"
    # Kombiniert mit Annaeherungspraefix / Klammern / trailing Satzzeichen
    assert parse_iso_date("ca. Juni.2024") == "2024-06-01"
    assert parse_iso_date("(Juni.2024)") == "2024-06-01"
    assert parse_iso_date("Juni.2024.") == "2024-06-01"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("Juni, 2024") == "2024-06-01"
    assert parse_iso_date("Juni/2024") == "2024-06-01"
    assert parse_iso_date("Juni-2024") == "2024-06-01"
    assert parse_iso_date("Jun. 2024") == "2024-06-01"
    # Voll qualifizierte DD.Mon.YYYY-Notation bleibt erhalten
    assert parse_iso_date("13.Juni.2024") == "2024-06-13"
    assert parse_iso_date("13.Jun.2024") == "2024-06-13"
    # Unbekannter Monat → None (nicht jeder Punkt-Token ist ein Monat)
    assert parse_iso_date("Foo.2024") is None
    assert parse_iso_date("abc.2024") is None
    # Jahr ausserhalb 1800-2999
    assert parse_iso_date("Jun.1700") is None


def test_parse_iso_date_roemische_monate():
    """Roemische Monatsziffern (I..XII) auf aelteren Etiketten / Eingangsbuechern."""
    # DD.MM.YYYY mit Punkt-Separator (klassische Etiketten-Form)
    assert parse_iso_date("13.VI.1985") == "1985-06-13"
    assert parse_iso_date("1.I.2020") == "2020-01-01"
    assert parse_iso_date("31.XII.1999") == "1999-12-31"
    assert parse_iso_date("15.IV.2024") == "2024-04-15"
    assert parse_iso_date("28.II.2024") == "2024-02-28"
    assert parse_iso_date("30.IX.2020") == "2020-09-30"
    # Mit Whitespace zwischen den Teilen ("13. VI. 1985")
    assert parse_iso_date("13. VI. 1985") == "1985-06-13"
    assert parse_iso_date("13 VI 2024") == "2024-06-13"
    # Bindestrich-Separator ("13-VI-2024")
    assert parse_iso_date("13-VI-2024") == "2024-06-13"
    # Nur Monat + Jahr ("VI 2024" / "VI/2024")
    assert parse_iso_date("VI 2024") == "2024-06-01"
    assert parse_iso_date("XII 1999") == "1999-12-01"
    assert parse_iso_date("VI/2024") == "2024-06-01"
    assert parse_iso_date("XII-1999") == "1999-12-01"
    # Englische Reihenfolge ("VI 13 2024")
    assert parse_iso_date("VI 13 2024") == "2024-06-13"
    # Case-insensitive (Etiketten teilweise klein geschrieben)
    assert parse_iso_date("13.vi.2024") == "2024-06-13"
    assert parse_iso_date("vi 2024") == "2024-06-01"
    # Kombiniert mit Annaeherungspraefix / Klammern / trailing Satzzeichen
    assert parse_iso_date("ca. 13.VI.1985") == "1985-06-13"
    assert parse_iso_date("(13.VI.1985)") == "1985-06-13"
    assert parse_iso_date("13.VI.1985.") == "1985-06-13"
    # Mit Zeit-Suffix (kommt z.B. in Logbuch-Eintraegen vor)
    assert parse_iso_date("13.VI.1985 14:30") == "1985-06-13"
    # Einzelbuchstaben-Mai ("13.V.2024" = 13. Mai 2024)
    assert parse_iso_date("13.V.2024") == "2024-05-13"
    assert parse_iso_date("13.X.2024") == "2024-10-13"
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_iso_date("13. Juni 1985") == "1985-06-13"
    assert parse_iso_date("13.06.1985") == "1985-06-13"


def test_parse_iso_date_roemische_monate_ungueltig():
    # XIII / XIV / hoeher gibt keinen gueltigen Monat
    assert parse_iso_date("13.XIII.2024") is None
    assert parse_iso_date("13.XIV.2024") is None
    # Ungueltiger Tag bleibt None
    assert parse_iso_date("32.VI.2024") is None
    assert parse_iso_date("30.II.2024") is None  # Februar 30
    # Jahr ausserhalb 1800..2999
    assert parse_iso_date("13.VI.1700") is None


def test_parse_iso_date_invalid():
    assert parse_iso_date("") is None
    assert parse_iso_date(None) is None
    assert parse_iso_date("   ") is None
    assert parse_iso_date("k. A.") is None
    assert parse_iso_date("unbekannt") is None
    assert parse_iso_date("32.13.2024") is None  # ungueltiger Tag
    assert parse_iso_date("2024-13-01") is None  # ungueltiger Monat
    assert parse_iso_date("1700") is None        # vor 1800
    assert parse_iso_date("foo") is None
    assert parse_iso_date("32. Juni 2024") is None    # ungueltiger Tag
    assert parse_iso_date("13. Foomonat 2024") is None  # unbekannter Monat


def test_parse_coordinates_decimal():
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5;7.5") == (46.5, 7.5)
    assert parse_coordinates("46,5 7,5") == (46.5, 7.5)


def test_parse_coordinates_with_direction():
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° O") == (46.5, 7.5)
    assert parse_coordinates("46.5° S, 7.5° W") == (-46.5, -7.5)
    # Reihenfolge lon, lat mit Hinweis → korrekt sortiert
    assert parse_coordinates("7.5° E, 46.5° N") == (46.5, 7.5)


def test_parse_coordinates_prefix():
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("S46.5 W7.5") == (-46.5, -7.5)


def test_parse_coordinates_dms():
    lat, lon = parse_coordinates('46°30\'15"N 7°30\'0"E')
    assert round(lat, 4) == 46.5042
    assert round(lon, 4) == 7.5
    lat, lon = parse_coordinates("46°30' S 7°30' W")
    assert round(lat, 4) == -46.5
    assert round(lon, 4) == -7.5


def test_parse_coordinates_plus_prefix():
    """Explizit positives Vorzeichen (z.B. aus GPS-Exporten) wird akzeptiert."""
    assert parse_coordinates("+46.5, +7.5") == (46.5, 7.5)
    assert parse_coordinates("+46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("+46.5, -7.5") == (46.5, -7.5)
    assert parse_coordinates("-46.5, +7.5") == (-46.5, 7.5)
    # Auch in der Praefix-Variante (N/S/E/W vorne, Plus an der Zahl)
    assert parse_coordinates("N+46.5 E+7.5") == (46.5, 7.5)


def test_parse_coordinates_typografisches_minus():
    """U+2212 (Minus-Zeichen) wird wie ASCII-Hyphen als Negativ-Vorzeichen behandelt."""
    # Negative Latitude (Suedhalbkugel)
    assert parse_coordinates("−46.5, 7.5") == (-46.5, 7.5)
    # Negative Longitude (Westhalbkugel)
    assert parse_coordinates("46.5, −7.5") == (46.5, -7.5)
    # Beide Werte negativ
    assert parse_coordinates("−46.5, −7.5") == (-46.5, -7.5)
    # Gemischt ASCII-Hyphen + Minus-Zeichen
    assert parse_coordinates("-46.5, −7.5") == (-46.5, -7.5)
    assert parse_coordinates("−46.5, -7.5") == (-46.5, -7.5)
    # Mit DMS-aehnlicher Notation (Grad-Symbol bleibt unangetastet)
    assert parse_coordinates("−46.5° −7.5°") == (-46.5, -7.5)
    # Mit Labels (Strip greift vor Pattern-Matching)
    assert parse_coordinates("Lat: −46.5, Lon: −7.5") == (-46.5, -7.5)
    # Out-of-Range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("−95.0, 7.5") is None
    assert parse_coordinates("46.5, −200.0") is None
    # Bestehender ASCII-Hyphen-Pfad bleibt unveraendert (Regress)
    assert parse_coordinates("-46.5, -7.5") == (-46.5, -7.5)


def test_parse_coordinates_mit_labels():
    """Geo-Notation mit Lat/Lon/Breite/Längen-Labels (Excel, GIS-Exports)."""
    # Englische Labels mit/ohne Doppelpunkt/Gleichheit
    assert parse_coordinates("Lat: 46.5, Lon: 7.5") == (46.5, 7.5)
    assert parse_coordinates("lat:46.5, lon:7.5") == (46.5, 7.5)
    assert parse_coordinates("latitude=46.5, longitude=7.5") == (46.5, 7.5)
    assert parse_coordinates("LAT 46.5 LON 7.5") == (46.5, 7.5)
    # Long/Long. als gaengige Abkuerzung
    assert parse_coordinates("Lat 46.5 Long 7.5") == (46.5, 7.5)
    assert parse_coordinates("Lat 46.5 Long. 7.5") == (46.5, 7.5)
    # Deutsche Labels
    assert parse_coordinates("Breite 46.5 Länge 7.5") == (46.5, 7.5)
    assert parse_coordinates("breitengrad: 46.5 längengrad: 7.5") == (46.5, 7.5)
    # Label + explizite Richtung (Label wird gestrippt, Richtung bleibt aktiv)
    assert parse_coordinates("Lat 46.5° N, Lon 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("Lat 46.5° S, Lon 7.5° W") == (-46.5, -7.5)
    # Ohne Labels weiterhin unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)


def test_parse_coordinates_himmelsrichtung_vollnamen():
    """Vollnamen der Himmelsrichtungen (DE/EN) werden auf N/S/E/W/O reduziert."""
    # Deutsch (Praefix-Form)
    assert parse_coordinates("Nord 46.5, Ost 7.5") == (46.5, 7.5)
    assert parse_coordinates("Norden 46.5, Osten 7.5") == (46.5, 7.5)
    assert parse_coordinates("Sued 46.5, West 7.5") == (-46.5, -7.5)
    assert parse_coordinates("Sueden 46.5, Westen 7.5") == (-46.5, -7.5)
    # Umlaute (Süd/Süden)
    assert parse_coordinates("Süd 46.5, West 7.5") == (-46.5, -7.5)
    assert parse_coordinates("Süden 46.5, Westen 7.5") == (-46.5, -7.5)
    # Englisch (Praefix-Form)
    assert parse_coordinates("North 46.5, East 7.5") == (46.5, 7.5)
    assert parse_coordinates("South 46.5, West 7.5") == (-46.5, -7.5)
    # Mixed-Sprache (kommt in geerbten Sammlungs-Notizen vor)
    assert parse_coordinates("North 46.5, Ost 7.5") == (46.5, 7.5)
    # Decimal-Suffix-Form ("46.5° North, 7.5° East")
    assert parse_coordinates("46.5° North, 7.5° East") == (46.5, 7.5)
    assert parse_coordinates("46.5° Nord, 7.5° Ost") == (46.5, 7.5)
    # Case-insensitive
    assert parse_coordinates("NORTH 46.5, EAST 7.5") == (46.5, 7.5)
    assert parse_coordinates("nord 46.5, ost 7.5") == (46.5, 7.5)
    # Mit trailing Punkt nach Kurzform
    assert parse_coordinates("Nord. 46.5, Ost. 7.5") == (46.5, 7.5)
    # Mit Labels kombiniert (Reihenfolge: erst Labels strippen, dann Richtung normalisieren)
    assert parse_coordinates("Lat: North 46.5, Lon: East 7.5") == (46.5, 7.5)
    # Einzelbuchstaben weiter funktionierend (kein Regress)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)


def test_parse_coordinates_compact_suffix_ohne_separator():
    """Compact-Form ohne Separator: '46.5N7.5E' (GPS-Online-Tools, Hand-Notizen)."""
    # Reine Suffix-Form ohne Whitespace
    assert parse_coordinates("46.5N7.5E") == (46.5, 7.5)
    assert parse_coordinates("46.5S7.5W") == (-46.5, -7.5)
    assert parse_coordinates("46.5N7.5O") == (46.5, 7.5)
    # Mit Grad-Symbol
    assert parse_coordinates("46.5°N7.5°E") == (46.5, 7.5)
    # Case-insensitive
    assert parse_coordinates("46.5n7.5e") == (46.5, 7.5)
    # Mit teilweisem Whitespace (kein Komma/Slash-Separator)
    assert parse_coordinates("46.5N 7.5E") == (46.5, 7.5)
    # Reihenfolge lon, lat (Suffix-Direction reorientiert korrekt)
    assert parse_coordinates("7.5E46.5N") == (46.5, 7.5)
    # Out-of-range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("100N50E") is None
    # Bestehende Formate weiterhin gueltig (kein Regress)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)


def test_parse_coordinates_tab_separator():
    """Tab als Separator (TSV-Exporte, Tab-getrennte GPS-/Excel-Spalten)."""
    # Reines Tab-Separator-Paar
    assert parse_coordinates("46.5\t7.5") == (46.5, 7.5)
    assert parse_coordinates("46,5\t7,5") == (46.5, 7.5)
    # Tab + Whitespace-Padding (Spalten in Tab-Tabellen mit zusaetzlichem Padding)
    assert parse_coordinates("46.5 \t 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5\t\t7.5") == (46.5, 7.5)
    # Mit Vorzeichen / Grad-Symbol / Richtung
    assert parse_coordinates("-46.5\t-7.5") == (-46.5, -7.5)
    assert parse_coordinates("+46.5\t+7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5°N\t7.5°E") == (46.5, 7.5)
    assert parse_coordinates("46.5° S\t7.5° W") == (-46.5, -7.5)
    # Out-of-range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("100\t50") is None
    # Bestehende Separatoren weiterhin gueltig (kein Regress)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5;7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5 7.5") == (46.5, 7.5)


def test_parse_coordinates_colon_dms():
    """Colon-separierte DMS-Notation: '46:30:15 N' (GPS-Logs, NMEA-Konvertierungen).

    Spiegelt die _DMS-Logik auf die ° / ' / " - lose Variante; obligatorische
    Himmelsrichtung verhindert Kollision mit Zeit-Notation (``14:30:00``).
    """
    # Standard mit Whitespace zwischen Sekunden und Richtung
    assert parse_coordinates("46:30:15 N, 7:30:0 E") == (46.5 + 15/3600, 7.5)
    # Ohne Whitespace zwischen Sekunden und Richtung
    assert parse_coordinates("46:30:15N, 7:30:0E") == (46.5 + 15/3600, 7.5)
    # Dezimal-Sekunden (Komma oder Punkt)
    lat, lon = parse_coordinates("46:30:15.5 N, 7:30:0 E")
    assert abs(lat - (46.5 + 15.5/3600)) < 1e-9
    assert lon == 7.5
    lat, lon = parse_coordinates("46:30:15,5 N, 7:30:0 E")
    assert abs(lat - (46.5 + 15.5/3600)) < 1e-9
    # Suedhalbkugel / Westhalbkugel
    lat, lon = parse_coordinates("46:30:15 S, 7:30:0 W")
    assert abs(lat - -(46.5 + 15/3600)) < 1e-9
    assert lon == -7.5
    # O = Ost (deutsche Notation)
    assert parse_coordinates("46:30:0 N, 7:30:0 O") == (46.5, 7.5)
    # Null-gepolsterte Sekunden
    assert parse_coordinates("46:00:00 N, 7:00:00 E") == (46.0, 7.0)
    # Verschiedene Pair-Separatoren (Komma/Semikolon/Slash/Tab/Whitespace)
    assert parse_coordinates("46:30:0 N 7:30:0 E") == (46.5, 7.5)
    assert parse_coordinates("46:30:0 N; 7:30:0 E") == (46.5, 7.5)
    assert parse_coordinates("46:30:0 N / 7:30:0 E") == (46.5, 7.5)
    # Case-insensitive Richtung
    assert parse_coordinates("46:30:0 n, 7:30:0 e") == (46.5, 7.5)
    # Mit umschliessenden Klammern (wird aktuell nicht extra gestrippt;
    # die _DMS_COLON-findall greift trotzdem auf den inhalt)
    assert parse_coordinates("(46:30:0 N, 7:30:0 E)") == (46.5, 7.5)
    # Reine Zeit-Notation ohne Richtung → kein colon-DMS-Match (Schutz vor
    # Kollision mit der Drei-Doppelpunkt-Form). Ohne Himmelsrichtung greift
    # _DMS_COLON nicht; das eindeutige "Zeit"-Stueck ``14:30:00`` ohne
    # zweite Zahl fallt durch alle Pattern auf None.
    assert parse_coordinates("14:30:00") is None
    # Out-of-Range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("100:00:00 N, 7:30:0 E") is None
    assert parse_coordinates("46:30:0 N, 200:00:00 E") is None
    # Bestehende DMS-Form mit ° / ' / " bleibt unveraendert (kein Regress)
    assert parse_coordinates("46° 30' 15\" N, 7° 30' 0\" E") == (
        46.5 + 15/3600, 7.5,
    )
    # Bestehende dezimale Form bleibt unveraendert (kein Regress)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)


def test_parse_coordinates_invalid():
    assert parse_coordinates("") is None
    assert parse_coordinates(None) is None
    assert parse_coordinates("foo") is None
    assert parse_coordinates("95.0, 7.5") is None     # lat out of range
    assert parse_coordinates("46.5, 200.0") is None   # lon out of range
    assert parse_coordinates("46.5") is None          # nur eine Zahl
