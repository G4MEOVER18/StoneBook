import pytest

from stonebook.migration.validators import parse_coordinates, parse_iso_date


def test_parse_iso_date_iso_unchanged():
    assert parse_iso_date("2024-06-13") == "2024-06-13"


def test_parse_iso_date_german():
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("1.1.2020") == "2020-01-01"


def test_parse_iso_date_slash_dot():
    assert parse_iso_date("2024/06/13") == "2024-06-13"
    assert parse_iso_date("2024.06.13") == "2024-06-13"


def test_parse_iso_date_us_format_fallback():
    """US-Datumsformat MM/DD/YYYY greift als Fallback, wenn DE als DD/MM/YYYY scheitert.

    Sehr verbreitet in Sammlungs-Notizen aus englischsprachigen Quellen
    (Auktions-Kataloge, US-Boersen, EN-Excel-Exporte mit Locale-abhaengiger
    Datumsspalte). Vor dem Fix fielen alle US-Formen mit Tag>12 stille auf
    None, weil das Feld dann in DE-Interpretation "Monat 13" hatte. Nach dem
    Fix greift der US-Zweig, ohne die DE-Interpretation mehrdeutiger Eingaben
    zu beeintraechtigen - der Loop stoppt beim ersten erfolgreichen Parse, so
    dass "01/02/2024" weiter als "2024-02-01" (DE: Tag 1, Monat 2) gelesen wird.
    """
    # Eindeutig US (Tag 13 > 12 -> DE-Interpretation als Monat 13 scheitert)
    assert parse_iso_date("06/13/2024") == "2024-06-13"
    assert parse_iso_date("06/13/1985") == "1985-06-13"
    # Bindestrich- und Punkt-Variante symmetrisch zu den DE-Formen
    assert parse_iso_date("06-13-2024") == "2024-06-13"
    assert parse_iso_date("06.13.2024") == "2024-06-13"
    # DE-Vorrang: mehrdeutige Eingaben (Tag <= 12 UND Monat <= 12) bleiben DE
    assert parse_iso_date("01/02/2024") == "2024-02-01"
    assert parse_iso_date("13/06/2024") == "2024-06-13"
    # Ungueltig in beiden Interpretationen -> None
    assert parse_iso_date("13/13/2024") is None
    # US mit Jahr ausserhalb [1800, 2999] -> None (Bereichs-Konvention greift)
    assert parse_iso_date("06/13/1500") is None


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


def test_parse_iso_date_standalone_trailing_tz():
    """Standalone-Trailing-Zeitzone ohne Zeitanteil ("2024-06-13 UTC",
    "13.06.2024 CET", "Juni 2020 MEZ", "2024-06-13Z") wird vom Ende
    abgestrippt, damit der reine Datumsanteil fuer die Parser-Kaskade
    zurueckbleibt.

    Spiegelt :func:`test_parse_iso_date_named_timezones` (Date+Time+TZ)
    auf die Date-Only-Achse: wenn keine Zeit angehaengt ist, greift
    :data:`stonebook.migration.validators._TRAILING_TIME` nicht
    (das Time-Muster verlangt ``T14:30``), und die reine TZ-Abkuerzung
    fiel bisher stille auf None. Typische Datenquellen mit Date-Only-TZ-
    Suffix sind System-Logs mit Datum-Rotation, Foto-Metadaten-Exporte
    in denen der TZ-Marker aus einer Datetime-Zelle in ein reines Datum-
    Feld ueberlaeuft, und Sammler-Notizen mit TZ als Kontext-Anmerkung
    neben dem Fund-Datum ("13.06.2024 MEZ").

    Konzept identisch zur Time+TZ-Form:  die TZ-Angabe ist semantische
    Wert-Anmerkung ("in welcher Zeitzone wurde das Datum notiert"),
    keine Datums-Modifikation - Strip + Rekursion, das ISO-Datum-Output
    ist identisch zur reinen Form.
    """
    # Universelle Zeit (Z-Compact ohne Trenner, spiegelt ISO 8601 Zulu-
    # Konvention fuer Datetime; UTC/GMT/UT verlangen Whitespace-Trenner
    # als Sammler-Notations-Konvention).
    assert parse_iso_date("2024-06-13Z") == "2024-06-13"
    assert parse_iso_date("2024-06-13 Z") == "2024-06-13"
    assert parse_iso_date("2024-06-13 UTC") == "2024-06-13"
    assert parse_iso_date("2024-06-13 GMT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 UT") == "2024-06-13"
    # Europa (CET, MEZ, MESZ, CEST + westeuropaeisch WET/WEST + osteuropaeisch
    # EET/EEST + britische Sommerzeit BST)
    assert parse_iso_date("2024-06-13 CET") == "2024-06-13"
    assert parse_iso_date("2024-06-13 CEST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 MEZ") == "2024-06-13"
    assert parse_iso_date("2024-06-13 MESZ") == "2024-06-13"
    assert parse_iso_date("2024-06-13 WET") == "2024-06-13"
    assert parse_iso_date("2024-06-13 WEST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 EET") == "2024-06-13"
    assert parse_iso_date("2024-06-13 EEST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 BST") == "2024-06-13"
    # Nordamerika (EST/EDT, CST/CDT, MST/MDT, PST/PDT + Alaska + Hawaii)
    assert parse_iso_date("2024-06-13 EST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 EDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 CST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 CDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 MST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 MDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 PST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 PDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 AKST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 AKDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 HST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 HDT") == "2024-06-13"
    # Asien-Pazifik
    assert parse_iso_date("2024-06-13 JST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 KST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 IST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 HKT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 SGT") == "2024-06-13"
    # Ozeanien
    assert parse_iso_date("2024-06-13 AEST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 AEDT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 NZST") == "2024-06-13"
    assert parse_iso_date("2024-06-13 NZDT") == "2024-06-13"
    # Suedamerika/Afrika
    assert parse_iso_date("2024-06-13 BRT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 SAST") == "2024-06-13"
    # DE-Format + Date-Only-TZ (Sammler-Notiz mit MEZ als Kontext-Anmerkung)
    assert parse_iso_date("13.06.2024 UTC") == "2024-06-13"
    assert parse_iso_date("13.06.2024 CET") == "2024-06-13"
    assert parse_iso_date("13.06.2024 MEZ") == "2024-06-13"
    # Monatsname + Jahr + TZ (Log-Rotation-Datum ohne genauen Tag)
    assert parse_iso_date("Juni 2020 MEZ") == "2020-06-01"
    assert parse_iso_date("June 2020 UTC") == "2020-06-01"
    # Jahr allein + TZ (grobstes Log-Rotations-Datum)
    assert parse_iso_date("1985 UTC") == "1985-01-01"
    assert parse_iso_date("2024 CET") == "2024-01-01"
    # Kombiniert mit trailing Klammer-Annotation ("(Foto)"): erst wird die
    # Klammer via _TRAILING_PAREN_REMARK gestrippt, dann in der Rekursion
    # die TZ - beide Marker sind unabhaengige Kontext-Anmerkungen.
    assert parse_iso_date("2024-06-13 UTC (Foto)") == "2024-06-13"
    assert parse_iso_date("13.06.2024 CET [verified]") == "2024-06-13"
    # Kombiniert mit trailing Aera-Marker (Museums-Etikett mit Zeitrechnungs-
    # Anker und TZ-Kontext)
    assert parse_iso_date("1985 AD UTC") == "1985-01-01"
    assert parse_iso_date("1985 n. Chr. CET") == "1985-01-01"
    # Kombiniert mit trailing Annaeherungs-Suffix
    assert parse_iso_date("1985 ca. UTC") == "1985-01-01"
    assert parse_iso_date("2020 vermutlich MEZ") == "2020-01-01"
    # Kein Regress: Date+Time+TZ-Formen fallen weiterhin durch die
    # :data:`_TRAILING_TIME`-Kaskade und liefern das reine Datum.
    assert parse_iso_date("2024-06-13T14:30 UTC") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:30 CEST") == "2024-06-13"
    assert parse_iso_date("2024-06-13T00:00:00Z") == "2024-06-13"
    assert parse_iso_date("2024-06-13T00:00:00+02:00") == "2024-06-13"
    # Kein Regress: Datum ohne TZ bleibt unveraendert
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("1985") == "1985-01-01"
    # Kleinbuchstaben-Suffix darf NICHT als TZ interpretiert werden
    # (Grossbuchstaben-Konvention der IANA-/CLDR-Abkuerzungen).
    assert parse_iso_date("2024-06-13 utc") is None
    assert parse_iso_date("2024-06-13 cet") is None
    assert parse_iso_date("2024-06-13 z") is None
    # Mixed-Case-Suffix ebenfalls nicht
    assert parse_iso_date("2024-06-13 UTc") is None
    assert parse_iso_date("2024-06-13 Cet") is None
    # Nicht-TZ-Suffix (aus Sammler-Notation) darf NICHT als TZ interpretiert
    # werden - Whitelist-Ansatz verhindert False-Positives auf legitime
    # 2-5-Buchstaben-Suffixe ohne TZ-Semantik.
    assert parse_iso_date("2024-06-13 REF") is None
    assert parse_iso_date("2024-06-13 EOD") is None
    assert parse_iso_date("2024-06-13 CH") is None
    assert parse_iso_date("2024-06-13 FOTO") is None
    # Suffix ohne Whitespace-Trenner fuer nicht-Z-Marker matcht nicht (nur
    # ``Z`` darf compact ans Datum haengen als ISO 8601 Zulu-Konvention)
    assert parse_iso_date("2024-06-13UTC") is None
    assert parse_iso_date("2024-06-13CET") is None
    # Reine TZ ohne Datum bleibt None (kein Freitext-Ratespiel)
    assert parse_iso_date("UTC") is None
    assert parse_iso_date("Z") is None
    assert parse_iso_date("CET") is None


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


def test_parse_iso_date_wahrscheinlichkeits_praefix():
    """Wahrscheinlichkeits-/Vermutungs-Marker (DE/EN) als Praefix vor dem Datum.

    Sehr verbreitet in geerbten Sammlungs-Notizen, wenn der Vorbesitzer das
    Datum nicht genau kannte ("wahrscheinlich 1985 gekauft",
    "möglicherweise 1980er", "evtl. Juni 2024", "perhaps 1995"). Semantisch
    identisch zu ``ca.``/``circa`` (Naeherungswert mit dokumentierter
    Unsicherheit), aber auf einer eigenen Praefix-Achse (Wahrscheinlichkeit
    statt Praezision) - vor dem Fix fielen alle Formen still auf None.
    """
    # Deutsche Marker
    assert parse_iso_date("wahrscheinlich 1985") == "1985-01-01"
    assert parse_iso_date("moeglicherweise 1985") == "1985-01-01"
    assert parse_iso_date("möglicherweise 1985") == "1985-01-01"
    assert parse_iso_date("möglicherweise Juni 2024") == "2024-06-01"
    assert parse_iso_date("evtl. 1985") == "1985-01-01"
    assert parse_iso_date("evtl 1985") == "1985-01-01"
    assert parse_iso_date("eventuell 1985") == "1985-01-01"
    assert parse_iso_date("eventuell 13.06.2024") == "2024-06-13"
    # Englische Marker
    assert parse_iso_date("perhaps 1985") == "1985-01-01"
    assert parse_iso_date("possibly 1985") == "1985-01-01"
    assert parse_iso_date("maybe 1985") == "1985-01-01"
    assert parse_iso_date("perhaps Juni 2024") == "2024-06-01"
    # Case-insensitive (Etiketten in Grossbuchstaben/Kleinbuchstaben/Mischform)
    assert parse_iso_date("Wahrscheinlich 1985") == "1985-01-01"
    assert parse_iso_date("MÖGLICHERWEISE 1985") == "1985-01-01"
    assert parse_iso_date("Perhaps 1985") == "1985-01-01"
    # Verkettet mit anderen Praefixen (Rekursion loest sie sequentiell auf)
    assert parse_iso_date("wahrscheinlich ca. 1985") == "1985-01-01"
    assert parse_iso_date("evtl. Sommer 1985") == "1985-06-01"
    assert parse_iso_date("perhaps 1980er") == "1980-01-01"
    assert parse_iso_date("möglicherweise Mitte 19. Jahrhundert") == "1850-01-01"
    # Ohne Datum-Rest oder mit ungueltigem Rest → None
    assert parse_iso_date("wahrscheinlich") is None
    assert parse_iso_date("perhaps abc") is None
    assert parse_iso_date("evtl. 1700") is None  # ausserhalb 1800-2999
    # Trailing-Form ("1985 wahrscheinlich") wird durch das symmetrische
    # :data:`_TRAILING_APPROX_SUFFIX` erfasst - siehe
    # :func:`test_parse_iso_date_trailing_annaeherungs_suffix` fuer die
    # volle Trailing-Wortliste und Notations-Palette.
    assert parse_iso_date("1985 wahrscheinlich") == "1985-01-01"
    # Bestehende Praefixe unveraendert (kein Regress)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("vermutlich 1985") == "1985-01-01"
    assert parse_iso_date("estimated 1985") == "1985-01-01"


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
    # "Anfang der 1980er" mit DE-Genitiv-Artikel-Fueller wird jetzt semantisch
    # identisch zur artikellosen Form auf den Dekaden-Anker gemappt - siehe
    # ``test_parse_iso_date_relative_dekade_genitiv_artikel``.
    assert parse_iso_date("Anfang der 1980er") == "1980-01-01"


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


def test_parse_iso_date_jahrhundert():
    """Jahrhundert-Notation (DE/EN) ergibt das Jahrhundert-Startjahr.

    Konvention analog Dekaden-Notation (1980er → 1980-01-01): das Label zeigt
    umgangssprachlich auf die "18xx"-Jahre, also 19. Jahrhundert → 1800-01-01.
    Museums-Etiketten, Provenienz-Vermerke und Auktions-Beschreibungen aus
    geerbten Sammlungen verwenden diese Grobdatierung typisch, wenn der
    Vorbesitzer den Fund nicht exakt jahrweise datieren konnte.
    """
    # Deutsche Vollform
    assert parse_iso_date("19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("20. Jahrhundert") == "1900-01-01"
    assert parse_iso_date("21. Jahrhundert") == "2000-01-01"
    # Ohne Punkt/Whitespace-Variationen (ordinaler Punkt ist optional, kommt in
    # Notizen ohne strenge DE-Grammatik vor: "19 Jahrhundert")
    assert parse_iso_date("19.Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19 Jahrhundert") == "1800-01-01"
    # DE-Kurzformen
    assert parse_iso_date("19. Jh.") == "1800-01-01"
    assert parse_iso_date("19. Jh") == "1800-01-01"
    assert parse_iso_date("19. Jhdt.") == "1800-01-01"
    assert parse_iso_date("19. Jhrdt.") == "1800-01-01"
    assert parse_iso_date("20. Jhdt") == "1900-01-01"
    # Englische Form
    assert parse_iso_date("19th century") == "1800-01-01"
    assert parse_iso_date("20th century") == "1900-01-01"
    assert parse_iso_date("21st century") == "2000-01-01"
    # EN ohne Ordinalsuffix (Museums-Etikett-Kurzform)
    assert parse_iso_date("20 century") == "1900-01-01"
    # EN Kurzform mit Punkt
    assert parse_iso_date("20th c.") == "1900-01-01"
    assert parse_iso_date("19th cent.") == "1800-01-01"
    # Case-insensitive (Etiketten in Grossbuchstaben, Kaufmanns-Notation)
    assert parse_iso_date("19. JAHRHUNDERT") == "1800-01-01"
    assert parse_iso_date("20TH CENTURY") == "1900-01-01"
    # Trailing Satzzeichen (Fliesstext-Notation "Fund aus dem 19. Jahrhundert.")
    assert parse_iso_date("19. Jahrhundert.") == "1800-01-01"
    assert parse_iso_date("19. Jh.,") == "1800-01-01"
    # Umschliessende Klammern (zitierte Datierung)
    assert parse_iso_date("(19. Jahrhundert)") == "1800-01-01"


def test_parse_iso_date_jahrhundert_ungueltig():
    """Ausserhalb des 1800-2999-Bandes, kein Wort-Suffix oder Kollisionen -> None."""
    # 18. Jahrhundert = 1700-1799, unter der 1800-Untergrenze
    assert parse_iso_date("18. Jahrhundert") is None
    # 1. Jahrhundert = 0-99, deutlich ausserhalb
    assert parse_iso_date("1. Jahrhundert") is None
    # 31. Jahrhundert = 3000, ueber die 2999-Obergrenze
    assert parse_iso_date("31. Jahrhundert") is None
    assert parse_iso_date("40. Jahrhundert") is None
    # Ohne Wort-Suffix bleibt es eine reine Zahl (die durch _YEAR_ONLY laeuft)
    assert parse_iso_date("19") is None       # 19 < 1800
    # Wort ohne Zahl
    assert parse_iso_date("Jahrhundert") is None
    assert parse_iso_date("century") is None
    # Wort-vor-Zahl-Reihenfolge (im DE/EN unueblich) bleibt None
    assert parse_iso_date("Jahrhundert 19") is None
    assert parse_iso_date("century 19th") is None
    # Bestehende Jahrzehnt-/Jahresangaben bleiben unangetastet (kein Regress)
    assert parse_iso_date("1980er") == "1980-01-01"
    assert parse_iso_date("1985") == "1985-01-01"


def test_parse_iso_date_roemisches_jahrhundert():
    """Roemische Jahrhundert-Notation (XIX. Jahrhundert, XX. Jhdt., XXI century)
    ergibt das Jahrhundert-Startjahr - Konvention identisch zur Arabisch-Notation.

    Traditionelle Museums-Etiketten-Schreibweise, besonders in geerbten Sammlungen
    mit europaeischer Provenienz (Italien, Osteuropa, Frankreich) und in aelteren
    deutschen wissenschaftlichen Referenzen. Vor dem Fix fielen alle diese Formen
    stille auf None. Spiegelt die bereits vorhandene Roemisch-Unterstuetzung fuer
    Monate (I..XII in _MONTH_NAMES) auf die Jahrhundert-Achse.
    """
    # Deutsche Vollform Roemisch
    assert parse_iso_date("XIX. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("XX. Jahrhundert") == "1900-01-01"
    assert parse_iso_date("XXI. Jahrhundert") == "2000-01-01"
    # Ohne Punkt oder Whitespace (Etiketten ohne strenge Grammatik)
    assert parse_iso_date("XIX.Jahrhundert") == "1800-01-01"
    assert parse_iso_date("XIX Jahrhundert") == "1800-01-01"
    # Deutsche Kurzformen (Jh., Jhdt., Jhrdt.) - identisch zur Arabisch-Notation
    assert parse_iso_date("XIX. Jh.") == "1800-01-01"
    assert parse_iso_date("XIX. Jh") == "1800-01-01"
    assert parse_iso_date("XIX. Jhdt.") == "1800-01-01"
    assert parse_iso_date("XIX. Jhrdt.") == "1800-01-01"
    assert parse_iso_date("XX. Jhdt") == "1900-01-01"
    # Englische Vollform Roemisch
    assert parse_iso_date("XIX century") == "1800-01-01"
    assert parse_iso_date("XX century") == "1900-01-01"
    assert parse_iso_date("XXI century") == "2000-01-01"
    # Englisch mit trailing-Punkt nach Roemisch-Zahl (Etiketten-Praxis)
    assert parse_iso_date("XX. century") == "1900-01-01"
    # Englische Kurzformen c./cent.
    assert parse_iso_date("XX c.") == "1900-01-01"
    assert parse_iso_date("XIX cent.") == "1800-01-01"
    assert parse_iso_date("XXI c.") == "2000-01-01"
    # Case-insensitive (Etiketten in Kleinbuchstaben und in Mischform)
    assert parse_iso_date("xix. jahrhundert") == "1800-01-01"
    assert parse_iso_date("xx. jhdt.") == "1900-01-01"
    assert parse_iso_date("xix century") == "1800-01-01"
    assert parse_iso_date("XIX. JAHRHUNDERT") == "1800-01-01"
    # Trailing Satzzeichen (Fliesstext-Notation "Fund aus dem XIX. Jahrhundert.")
    assert parse_iso_date("XIX. Jahrhundert.") == "1800-01-01"
    assert parse_iso_date("XIX. Jh.,") == "1800-01-01"
    # Umschliessende Klammern (zitierte Datierung)
    assert parse_iso_date("(XIX. Jahrhundert)") == "1800-01-01"
    # Rand-Grenzfall: XXX. Jahrhundert = 2900-01-01 (Obergrenze)
    assert parse_iso_date("XXX. Jahrhundert") == "2900-01-01"


def test_parse_iso_date_roemisches_jahrhundert_ungueltig():
    """Ausserhalb 1800-2999-Band, non-kanonische Roemisch-Tokens oder
    Kollisionen -> None. Spiegelt die Ungueltig-Semantik von
    _CENTURY_DE/_EN auf die Roemisch-Achse.
    """
    # XVIII. Jahrhundert = 1700-1799, unter der 1800-Untergrenze
    assert parse_iso_date("XVIII. Jahrhundert") is None
    # I. bis IX. Jahrhundert = 0-899, weit unter Untergrenze
    assert parse_iso_date("I. Jahrhundert") is None
    assert parse_iso_date("IX. Jahrhundert") is None
    # XXXI. + gaebe > 2999, aber XXXI ist nicht im Map (nur bis XXX)
    assert parse_iso_date("XXXI. Jahrhundert") is None
    # Non-kanonische Roemisch-Tokens (im Map nicht enthalten)
    assert parse_iso_date("IIII. Jahrhundert") is None
    assert parse_iso_date("VXV. Jahrhundert") is None
    # Roemisch-Jahr-Form ohne Century-Suffix (MMXX = 2020) - keine Century
    assert parse_iso_date("MMXX Jahrhundert") is None
    # Ohne Wort-Suffix (reine Roemisch-Zahl mit / ohne Punkt)
    assert parse_iso_date("XIX") is None
    assert parse_iso_date("XIX.") is None
    # Bestehende Arabisch-Century bleibt unangetastet (kein Regress)
    assert parse_iso_date("19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19th century") == "1800-01-01"
    # Bestehende Roemisch-Monate bleiben unangetastet (kein Regress)
    assert parse_iso_date("13.VI.1985") == "1985-06-13"
    assert parse_iso_date("VI 2024") == "2024-06-01"


def test_parse_iso_date_roemisches_jahrhundert_relativ():
    """Relative Position innerhalb eines Roemisch-adressierten Jahrhunderts
    ('Mitte XIX. Jahrhundert', 'late XX century', 'Anfang XXI. Jhdt.').

    Spiegelt _RELATIVE_CENTURY_DE/_EN auf die Roemisch-Achse - dieselben
    Offset-Konventionen: Anfang/early=0, Mitte/mid=50, Ende/late=99.
    """
    # Deutsche Vollform
    assert parse_iso_date("Anfang XIX. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("Mitte XIX. Jahrhundert") == "1850-01-01"
    assert parse_iso_date("Ende XIX. Jahrhundert") == "1899-01-01"
    assert parse_iso_date("Anfang XX. Jahrhundert") == "1900-01-01"
    assert parse_iso_date("Mitte XX. Jahrhundert") == "1950-01-01"
    assert parse_iso_date("Ende XX. Jahrhundert") == "1999-01-01"
    assert parse_iso_date("Anfang XXI. Jahrhundert") == "2000-01-01"
    # Deutsche Kurzformen (Jhdt./Jh./Jhrdt.)
    assert parse_iso_date("Mitte XX. Jhdt.") == "1950-01-01"
    assert parse_iso_date("Ende XIX. Jh.") == "1899-01-01"
    assert parse_iso_date("Anfang XX. Jhrdt.") == "1900-01-01"
    # Englische Vollform
    assert parse_iso_date("early XIX century") == "1800-01-01"
    assert parse_iso_date("mid XIX century") == "1850-01-01"
    assert parse_iso_date("late XIX century") == "1899-01-01"
    assert parse_iso_date("early XX century") == "1900-01-01"
    assert parse_iso_date("mid XX century") == "1950-01-01"
    assert parse_iso_date("late XX century") == "1999-01-01"
    # Englische Kurzformen c./cent.
    assert parse_iso_date("early XX c.") == "1900-01-01"
    assert parse_iso_date("mid XX c.") == "1950-01-01"
    assert parse_iso_date("late XX cent.") == "1999-01-01"
    # Englische Bindestrich-Kompositum ("mid-XIX century" typische EN-Form)
    assert parse_iso_date("mid-XIX century") == "1850-01-01"
    assert parse_iso_date("late-XIX century") == "1899-01-01"
    assert parse_iso_date("early-XX century") == "1900-01-01"
    # Case-insensitive
    assert parse_iso_date("ENDE XIX. JAHRHUNDERT") == "1899-01-01"
    assert parse_iso_date("EARLY XX CENTURY") == "1900-01-01"
    # Rand-Grenzfall: Ende XXX. Jahrhundert = 2999 (Obergrenze) muss noch matchen
    assert parse_iso_date("Ende XXX. Jahrhundert") == "2999-01-01"
    # Ungueltig-Faelle
    # XVIII (1700er) mit Anfang/Mitte/Ende bleibt unter Untergrenze
    assert parse_iso_date("Anfang XVIII. Jahrhundert") is None
    assert parse_iso_date("Ende XVIII. Jahrhundert") is None
    # Non-kanonisches Roemisch-Token
    assert parse_iso_date("Mitte IIII. Jahrhundert") is None
    # Reines Praefix ohne Century-Suffix
    assert parse_iso_date("Anfang XIX") is None
    assert parse_iso_date("Mitte XX") is None


def test_parse_iso_date_relative_jahrhundert():
    """Relative Position innerhalb eines Jahrhunderts ('Mitte 19. Jahrhundert',
    'late 20th century', 'mid-19th c.') spiegelt _RELATIVE_DECADE auf die
    Jahrhundert-Achse.

    Konvention: Anfang/early=0 (Jahrhundert-Startjahr), Mitte/mid=50
    (Jahrhundert-Mitte), Ende/late=99 (Jahrhundert-Endjahr). Beispiele:
    - "Anfang 19. Jahrhundert" → 1800-01-01
    - "Mitte 19. Jahrhundert" → 1850-01-01
    - "Ende 19. Jahrhundert" → 1899-01-01
    """
    # Deutsche Varianten - Vollform
    assert parse_iso_date("Anfang 19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("Mitte 19. Jahrhundert") == "1850-01-01"
    assert parse_iso_date("Ende 19. Jahrhundert") == "1899-01-01"
    assert parse_iso_date("Anfang 20. Jahrhundert") == "1900-01-01"
    assert parse_iso_date("Mitte 20. Jahrhundert") == "1950-01-01"
    assert parse_iso_date("Ende 20. Jahrhundert") == "1999-01-01"
    assert parse_iso_date("Anfang 21. Jahrhundert") == "2000-01-01"
    # Deutsche Kurzformen
    assert parse_iso_date("Mitte 20. Jhdt.") == "1950-01-01"
    assert parse_iso_date("Ende 19. Jh.") == "1899-01-01"
    assert parse_iso_date("Anfang 20. Jhrdt.") == "1900-01-01"
    # Englische Varianten
    assert parse_iso_date("early 19th century") == "1800-01-01"
    assert parse_iso_date("mid 19th century") == "1850-01-01"
    assert parse_iso_date("late 19th century") == "1899-01-01"
    assert parse_iso_date("early 20th century") == "1900-01-01"
    assert parse_iso_date("mid 20th century") == "1950-01-01"
    assert parse_iso_date("late 20th century") == "1999-01-01"
    # Englische Kurzformen (c./cent.)
    assert parse_iso_date("early 20th c.") == "1900-01-01"
    assert parse_iso_date("mid 20th c.") == "1950-01-01"
    assert parse_iso_date("late 20th cent.") == "1999-01-01"
    # Englische Bindestrich-Kompositum ("mid-19th century" typische EN-Form)
    assert parse_iso_date("mid-19th century") == "1850-01-01"
    assert parse_iso_date("late-19th century") == "1899-01-01"
    assert parse_iso_date("early-20th century") == "1900-01-01"
    # EN ohne Ordinalsuffix
    assert parse_iso_date("mid 20 century") == "1950-01-01"
    # Case-insensitive (Etiketten in Grossbuchstaben)
    assert parse_iso_date("ENDE 19. JAHRHUNDERT") == "1899-01-01"
    assert parse_iso_date("EARLY 20TH CENTURY") == "1900-01-01"
    assert parse_iso_date("Mitte 20. Jh.") == "1950-01-01"
    # Rand-Grenzfall: 30. Jhdt. + Ende = 2999 (Obergrenze) muss noch matchen
    assert parse_iso_date("Ende 30. Jahrhundert") == "2999-01-01"


def test_parse_iso_date_relative_jahrhundert_ungueltig():
    """Ausserhalb des 1800-2999-Bandes, ohne Wort-Suffix, oder Kollisionen -> None."""
    # 18. Jahrhundert = 1700-1799, komplett unter der 1800-Untergrenze
    assert parse_iso_date("Anfang 18. Jahrhundert") is None
    assert parse_iso_date("Mitte 18. Jahrhundert") is None
    assert parse_iso_date("Ende 18. Jahrhundert") is None
    # 31. Jahrhundert = 3000-3099, ueber der 2999-Obergrenze
    assert parse_iso_date("Anfang 31. Jahrhundert") is None
    assert parse_iso_date("Mitte 31. Jahrhundert") is None
    assert parse_iso_date("Ende 31. Jahrhundert") is None
    # 1. Jahrhundert = 0-99, weit ausserhalb
    assert parse_iso_date("Anfang 1. Jahrhundert") is None
    # Praefix ohne Century-Suffix bleibt None (nicht als reines Jahr interpretiert)
    assert parse_iso_date("Anfang 19") is None
    assert parse_iso_date("Mitte 20") is None
    # Ohne Praefix bleibt die base Century-Notation aktiv (kein Regress)
    assert parse_iso_date("19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("20th century") == "1900-01-01"
    # Relative-Dekade bleibt unangetastet (kein Regress durch Pattern-Kollision)
    assert parse_iso_date("Mitte 1980er") == "1985-01-01"
    assert parse_iso_date("Ende 1990s") == "1999-01-01"
    assert parse_iso_date("Anfang 2000s") == "2000-01-01"


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


def test_parse_iso_date_relative_dekade_genitiv_artikel():
    """DE-Genitiv-Artikel-Fueller vor Dekaden-Anker ('Anfang der 1980er',
    'Ende der 1990er Jahre', 'Mitte der 2000er') wird semantisch identisch
    zur artikellosen Form auf den Dekaden-Anker gemappt.

    In geerbten Sammlungs-Notizen die haeufigste DE-Print-/Buch-Form fuer
    Dekaden-Positionen ("Sammlung Anfang der 1980er Jahre begonnen", "Fund
    Ende der 1990er Jahre"). Bisher fielen alle Formen mit ``der``-Artikel
    still auf None, obwohl semantisch identisch zur artikellosen ``Anfang
    1980er``-Form (Konvention: Anfang → Jahr 0 der Dekade, Mitte → Jahr 5,
    Ende → Jahr 9).
    """
    # DE-Genitiv-Artikel ohne "Jahre"-Trailer
    assert parse_iso_date("Anfang der 1980er") == "1980-01-01"
    assert parse_iso_date("Mitte der 1990er") == "1995-01-01"
    assert parse_iso_date("Ende der 2000er") == "2009-01-01"
    # Mit "Jahre"-Trailer (Standard-Print-Form)
    assert parse_iso_date("Anfang der 1980er Jahre") == "1980-01-01"
    assert parse_iso_date("Mitte der 1990er Jahre") == "1995-01-01"
    assert parse_iso_date("Ende der 2000er Jahre") == "2009-01-01"
    # Mit "Jahren"-Dativ-Plural-Trailer (in praepositionalen Wendungen)
    assert parse_iso_date("Anfang der 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("Ende der 1990er Jahren") == "1999-01-01"
    # Case-insensitive (Genitiv-Artikel darf auch grossgeschrieben sein)
    assert parse_iso_date("Anfang Der 1980er") == "1980-01-01"
    assert parse_iso_date("ANFANG DER 1980ER") == "1980-01-01"
    # Kombination mit Annaeherungspraefix (Verkettung ueber Rekursion)
    assert parse_iso_date("ca. Mitte der 1990er") == "1995-01-01"
    assert parse_iso_date("circa Anfang der 1980er Jahre") == "1980-01-01"
    # Kombination mit trailing Satzzeichen
    assert parse_iso_date("Anfang der 1980er.") == "1980-01-01"
    assert parse_iso_date("Ende der 1990er Jahre.") == "1999-01-01"
    # Kombination mit umschliessenden Klammern
    assert parse_iso_date("(Anfang der 1980er Jahre)") == "1980-01-01"
    # Regression-Anker: artikellose Form bleibt unveraendert
    assert parse_iso_date("Anfang 1980er") == "1980-01-01"
    assert parse_iso_date("Mitte 1990er Jahre") == "1995-01-01"


def test_parse_iso_date_jahrzehnt_dativ_plural():
    """Dativ-Plural-Form 'Jahren' der Dekaden-Notation ('1980er Jahren',
    'in den 1990er Jahren') wird semantisch identisch zur Nominativ-Form
    ('1980er Jahre') auf den Dekaden-Anker gemappt.

    In praepositionalen Wendungen ist ``Jahren`` (Dativ-Plural) der Standard,
    nicht ``Jahre`` (Nominativ/Akkusativ): "in den 1980er Jahren", "aus
    den 1990er Jahren", "waehrend der 2000er Jahren". Vorher fiel die
    Dativ-Form auf None, obwohl semantisch identisch zur Nominativ-Form.
    """
    # Direkte Dativ-Plural-Form
    assert parse_iso_date("1980er Jahren") == "1980-01-01"
    assert parse_iso_date("1990er Jahren") == "1990-01-01"
    assert parse_iso_date("2000er Jahren") == "2000-01-01"
    # Case-insensitive
    assert parse_iso_date("1980er JAHREN") == "1980-01-01"
    assert parse_iso_date("1980ER Jahren") == "1980-01-01"
    # In Kombination mit _TEMPORAL_PREFIX (praepositionale Standard-Wendung
    # "in den 1980er Jahren" = Praeposition "in" + Artikel "den" + Dekade)
    assert parse_iso_date("in den 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("von den 1990er Jahren") == "1990-01-01"
    # Regression-Anker: Nominativ-Form bleibt unveraendert
    assert parse_iso_date("1980er Jahre") == "1980-01-01"
    assert parse_iso_date("in den 1980er Jahre") == "1980-01-01"


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


def test_parse_iso_date_mehrjahres_spanne_zwischen():
    """Umschliessende Range-Form 'zwischen X und Y' / 'between X and Y'
    spiegelt _YEAR_RANGE_WORD auf die bilaterale Konjunktions-Notation
    (Startjahr als ISO-Datum)."""
    # Deutsche Form (typisch in geerbten Sammlungs-Tagebuechern, wenn der
    # Vorbesitzer die Spanne nicht praezise datieren konnte)
    assert parse_iso_date("zwischen 1950 und 1960") == "1950-01-01"
    assert parse_iso_date("zwischen 1985 und 1990") == "1985-01-01"
    assert parse_iso_date("zwischen 2000 und 2024") == "2000-01-01"
    # Englische Form (Auktionskataloge, Provenienz-Notizen aus EN-Quellen)
    assert parse_iso_date("between 1950 and 1960") == "1950-01-01"
    assert parse_iso_date("between 1985 and 1990") == "1985-01-01"
    # Case-insensitiv (Caps-Lock-Notizen, Titel-Case aus Word-Autoformat)
    assert parse_iso_date("ZWISCHEN 1985 UND 1990") == "1985-01-01"
    assert parse_iso_date("Between 1985 And 1990") == "1985-01-01"
    # Inverted Spanne (Tippfehler) liefert das erste Jahr, spiegelt
    # _YEAR_RANGE / _YEAR_RANGE_WORD
    assert parse_iso_date("zwischen 1990 und 1985") == "1990-01-01"
    # Whitespace-Toleranz (mehrfache Leerzeichen, Trim)
    assert parse_iso_date("  zwischen  1985  und  1990  ") == "1985-01-01"
    # Kombination mit bestehenden Praefixen ueber Rekursion
    assert parse_iso_date("ca. zwischen 1985 und 1990") == "1985-01-01"
    assert parse_iso_date("(zwischen 1985 und 1990)") == "1985-01-01"
    assert parse_iso_date("zwischen 1985 und 1990.") == "1985-01-01"


def test_parse_iso_date_mehrjahres_spanne_zwischen_ungueltig():
    """Jahr ausserhalb [1800, 2999], fehlende Konjunktion oder fehlender
    Whitespace → None."""
    # Ohne Whitespace zwischen Schluesselwoertern kein Match
    assert parse_iso_date("zwischen1985und1990") is None
    # Nur ein Jahr (fehlende Konjunktion/rechtes Jahr)
    assert parse_iso_date("zwischen 1985") is None
    # Nur die Konjunktion ohne 'zwischen'/'between' (nicht die Wort-Form
    # von _YEAR_RANGE_WORD, das nur bis/to/till/until kennt)
    assert parse_iso_date("1985 und 1990") is None
    assert parse_iso_date("1985 and 1990") is None
    # Jahr ausserhalb [1800, 2999]
    assert parse_iso_date("zwischen 1500 und 1600") is None
    assert parse_iso_date("between 1800 and 3000") is None


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


def test_parse_iso_date_winter_cross_year():
    """Winter-Cross-Year-Notation ("Winter YYYY/YYYY+1", "Winter YYYY/YY",
    "Winter YYYY-YYYY+1"): sehr verbreitet in Sammlungs-Notizen und Foto-
    Captions, wenn Fund/Aktivitaet in die Winter-Saison faellt, die per
    Konvention zwei Kalenderjahre umschliesst (Dezember-Februar). Ohne diese
    Notation fiel jede Form mit Doppel-Jahr auf None, obwohl "Winter
    YYYY/YYYY+1" die de-facto Konvention in Wetter-/Klima-Kontexten und
    Sammler-Etiketten ist. Konvention: Dezember des ersten Jahres (spiegelt
    _SEASON_MONTHS["winter"] = 12 und die bereits gelieferte YYYY-12-01-
    Semantik fuer "Winter YYYY" ohne Cross-Year-Notation).
    """
    # Vollstaendige 4/4-Ziffer-Form mit Slash-Trenner
    assert parse_iso_date("Winter 2023/2024") == "2023-12-01"
    assert parse_iso_date("Winter 1999/2000") == "1999-12-01"
    assert parse_iso_date("Winter 2098/2099") == "2098-12-01"
    # Kurzform mit 2-Ziffer-Ende (2023/24) - haeufigste Notation in
    # Sammlungs-Notizen und Wettersaison-Berichten
    assert parse_iso_date("Winter 2023/24") == "2023-12-01"
    assert parse_iso_date("Winter 2000/01") == "2000-12-01"
    # Jahrhundert-Boundary-Form 2099/00 (Kurzform) - der (year_start // 100)
    # * 100 + int(year_end_raw)-Fall mit year_end_raw = 00 muss +100 kompen-
    # sieren, damit 2099/00 -> 2100 (nicht 2000) als semantische Nachfolge
    # gelesen wird
    assert parse_iso_date("Winter 2099/00") == "2099-12-01"
    # Bindestrich-Trenner symmetrisch zu Slash (analog _YEAR_RANGE-Konvention)
    assert parse_iso_date("Winter 1999-2000") == "1999-12-01"
    assert parse_iso_date("Winter 2023-24") == "2023-12-01"
    # En-Dash/Em-Dash (typografische Print-Notation aus Word-Autoformat und
    # LaTeX-Exporten)
    assert parse_iso_date("Winter 2023–2024") == "2023-12-01"
    assert parse_iso_date("Winter 2023—2024") == "2023-12-01"
    # Whitespace um den Trenner (Word-Autoformat setzt oft Leerzeichen um
    # den Bindestrich in Range-Notationen)
    assert parse_iso_date("Winter 2023 / 2024") == "2023-12-01"
    assert parse_iso_date("Winter 2023 - 2024") == "2023-12-01"
    # Case-Insensitivitaet
    assert parse_iso_date("winter 2023/24") == "2023-12-01"
    assert parse_iso_date("WINTER 2023/2024") == "2023-12-01"
    # Regression: "Winter YYYY" (Single-Year, ohne Cross-Year-Notation)
    # bleibt unveraendert - dieselbe YYYY-12-01-Semantik
    assert parse_iso_date("Winter 2023") == "2023-12-01"
    assert parse_iso_date("winter 2023") == "2023-12-01"
    # Regression: andere Saisons ohne Cross-Year bleiben unveraendert
    assert parse_iso_date("Sommer 2023") == "2023-06-01"
    assert parse_iso_date("Fruehling 2024") == "2024-03-01"


def test_parse_iso_date_winter_cross_year_ungueltig():
    """Winter-Cross-Year-Notation: semantische Konsistenz-Pruefung und
    Whitelist auf 'winter'. Nicht-konsekutive Jahres-Paare, nicht-Winter-
    Saisons und Werte ausserhalb des 1800..2999-Bandes werden zurueckgewiesen.
    """
    # Nicht-konsekutive Jahres-Paare (semantische Winter-Saison verlangt
    # exakt year_end == year_start + 1)
    assert parse_iso_date("Winter 2023/2025") is None
    assert parse_iso_date("Winter 2023/22") is None
    assert parse_iso_date("Winter 2023-2030") is None
    # Nur "winter" akzeptiert Cross-Year - die uebrigen Saisons enden
    # natuerlicherweise innerhalb eines Kalenderjahres
    assert parse_iso_date("Sommer 2023/2024") is None
    assert parse_iso_date("Summer 2023/2024") is None
    assert parse_iso_date("Fruehling 2023/2024") is None
    assert parse_iso_date("Spring 2023/2024") is None
    assert parse_iso_date("Herbst 2023/2024") is None
    assert parse_iso_date("Autumn 2023/2024") is None
    # Jahr ausserhalb [1800, 2999]
    assert parse_iso_date("Winter 1799/1800") is None


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


def test_parse_iso_date_boundary_praefix():
    """Boundary-/Richtungs-Praefix (vor/nach/before/after/pre-/post-) wird gestrippt.

    Spiegelt das _APPROX_PREFIX-Konzept (Praefix wird gestrippt, Datum bleibt
    unveraendert) auf Richtungs-Marker, wie sie in geerbten Sammlungs-Notizen
    fuer grob datierte Funde auftauchen ("vor 1985 gefunden, genaues Jahr
    unbekannt"). Das ISO-Datum nimmt den Grenzwert als bekannten Anker; die
    Richtungs-Information (vor/nach) bleibt im Freitext (notizen).
    """
    # DE Wort-Formen
    assert parse_iso_date("vor 1985") == "1985-01-01"
    assert parse_iso_date("nach 1985") == "1985-01-01"
    assert parse_iso_date("Vor 1985") == "1985-01-01"
    assert parse_iso_date("Nach 2024") == "2024-01-01"
    # EN Wort-Formen
    assert parse_iso_date("before 1985") == "1985-01-01"
    assert parse_iso_date("after 1985") == "1985-01-01"
    assert parse_iso_date("Before 2024") == "2024-01-01"
    assert parse_iso_date("After 1985") == "1985-01-01"
    # EN Bindestrich-Kompositum (pre-/post-)
    assert parse_iso_date("pre-1985") == "1985-01-01"
    assert parse_iso_date("post-1985") == "1985-01-01"
    assert parse_iso_date("Pre-1985") == "1985-01-01"
    assert parse_iso_date("Post-2024") == "2024-01-01"
    # Mit Whitespace statt Bindestrich (EN-Pre/Post-Form mit Leerzeichen)
    assert parse_iso_date("pre 1985") == "1985-01-01"
    assert parse_iso_date("post 1985") == "1985-01-01"
    # Boundary + Monat/Jahr (alle Datums-Untertypen, rekursiv)
    assert parse_iso_date("vor Juni 2024") == "2024-06-01"
    assert parse_iso_date("nach 13.06.2024") == "2024-06-13"
    assert parse_iso_date("nach 13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("before June 2024") == "2024-06-01"
    assert parse_iso_date("after 2024-06-13") == "2024-06-13"
    # Boundary + Jahrzehnt / Saison / Range
    assert parse_iso_date("vor 1980er") == "1980-01-01"
    assert parse_iso_date("nach Sommer 1985") == "1985-06-01"
    assert parse_iso_date("vor 1950-1960") == "1950-01-01"
    assert parse_iso_date("nach 1950 bis 1960") == "1950-01-01"
    # Case-insensitive (DE/EN gemischt)
    assert parse_iso_date("VOR 1985") == "1985-01-01"
    assert parse_iso_date("NACH JUNI 2024") == "2024-06-01"
    assert parse_iso_date("BEFORE 1985") == "1985-01-01"
    # Verkettete Praefixe (rekursive Strippung)
    assert parse_iso_date("vor ca. 1985") == "1985-01-01"
    assert parse_iso_date("ca. vor 1985") == "1985-01-01"
    assert parse_iso_date("nach circa Juni 2024") == "2024-06-01"
    # Boundary + temporale Praeposition (semantisch redundant, unschaedlich)
    assert parse_iso_date("vor im Jahr 1985") == "1985-01-01"
    # Praefix ohne Inhalt / mit ungueltigem Rest → None
    assert parse_iso_date("vor") is None
    assert parse_iso_date("nach") is None
    assert parse_iso_date("before") is None
    assert parse_iso_date("after") is None
    assert parse_iso_date("vor abc") is None
    assert parse_iso_date("nach garten") is None
    assert parse_iso_date("pre-abc") is None
    # Praefix vor Jahr ausserhalb 1800-2999 → None
    assert parse_iso_date("vor 1700") is None
    assert parse_iso_date("nach 3000") is None
    # Wortanfang muss exakt sein - kein Anschneiden laengerer Worte
    # ("vorhin", "vormittags", "preset", "posten" duerfen NICHT matchen)
    assert parse_iso_date("vorhin 1985") is None
    assert parse_iso_date("vormittags 1985") is None
    assert parse_iso_date("preset 1985") is None
    assert parse_iso_date("president 1985") is None
    assert parse_iso_date("posten 1985") is None
    assert parse_iso_date("nachher 1985") is None
    assert parse_iso_date("Nachfrage 1985") is None
    # Bestehende Datumsangaben ohne Boundary-Praefix bleiben gleich (kein Regress)
    assert parse_iso_date("1985") == "1985-01-01"
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("im Juni 2024") == "2024-06-01"


def test_parse_iso_date_range_praefix():
    """Unidirektionaler Range-Praefix (ab/seit/bis/from/since/until/till) wird gestrippt.

    Spiegelt das _BOUNDARY_PREFIX-Konzept (Praefix wird gestrippt, Datum bleibt
    unveraendert) auf unidirektionale Spanne-Marker, wie sie in geerbten
    Sammlungs-Notizen fuer den Start-/Endpunkt einer Erfassungs-/Fund-Periode
    auftauchen ("Sammlung ab 1985", "Fundort seit 1990 zugaenglich",
    "Fundort bis 1995 aktiv"). Das ISO-Datum nimmt das Jahr als bekannten
    Anker; die Richtungs-/Spannenform bleibt im Freitext (notizen).
    """
    # DE Wort-Formen
    assert parse_iso_date("ab 1985") == "1985-01-01"
    assert parse_iso_date("seit 1985") == "1985-01-01"
    assert parse_iso_date("bis 1985") == "1985-01-01"
    assert parse_iso_date("Ab 2024") == "2024-01-01"
    assert parse_iso_date("Seit 2024") == "2024-01-01"
    assert parse_iso_date("Bis 2024") == "2024-01-01"
    # EN Wort-Formen
    assert parse_iso_date("from 1985") == "1985-01-01"
    assert parse_iso_date("since 1985") == "1985-01-01"
    assert parse_iso_date("until 1985") == "1985-01-01"
    assert parse_iso_date("till 1985") == "1985-01-01"
    assert parse_iso_date("From 2024") == "2024-01-01"
    assert parse_iso_date("Since 2024") == "2024-01-01"
    assert parse_iso_date("Until 2024") == "2024-01-01"
    # Range-Praefix + alle Datums-Untertypen (rekursiv)
    assert parse_iso_date("ab Juni 2024") == "2024-06-01"
    assert parse_iso_date("seit Sommer 1985") == "1985-06-01"
    assert parse_iso_date("bis 13.06.2024") == "2024-06-13"
    assert parse_iso_date("from 1980er") == "1980-01-01"
    assert parse_iso_date("since June 2024") == "2024-06-01"
    assert parse_iso_date("until 2024-06-13") == "2024-06-13"
    assert parse_iso_date("ab 1950-1960") == "1950-01-01"
    # Case-insensitive
    assert parse_iso_date("AB 1985") == "1985-01-01"
    assert parse_iso_date("SEIT JUNI 2024") == "2024-06-01"
    assert parse_iso_date("FROM 1985") == "1985-01-01"
    # Verkettete Praefixe (rekursive Strippung)
    assert parse_iso_date("ab ca. 1985") == "1985-01-01"
    assert parse_iso_date("ca. ab 1985") == "1985-01-01"
    assert parse_iso_date("seit circa Juni 2024") == "2024-06-01"
    # Range-Praefix + temporale Praeposition (semantisch redundant, unschaedlich)
    assert parse_iso_date("ab im Jahr 1985") == "1985-01-01"
    # WICHTIG: "bis" als Range-Separator in der Mitte bleibt erhalten - der
    # ^-Anker schliesst Kollision mit _YEAR_RANGE_WORD aus. Regression-Test:
    assert parse_iso_date("1985 bis 1990") == "1985-01-01"
    assert parse_iso_date("1985-1990") == "1985-01-01"
    # Praefix ohne Inhalt / mit ungueltigem Rest → None
    assert parse_iso_date("ab") is None
    assert parse_iso_date("seit") is None
    assert parse_iso_date("bis") is None
    assert parse_iso_date("from") is None
    assert parse_iso_date("since") is None
    assert parse_iso_date("until") is None
    assert parse_iso_date("till") is None
    assert parse_iso_date("ab abc") is None
    assert parse_iso_date("seit garten") is None
    # Praefix vor Jahr ausserhalb 1800-2999 → None
    assert parse_iso_date("ab 1700") is None
    assert parse_iso_date("bis 3000") is None
    # Wortanfang muss exakt sein - kein Anschneiden laengerer Worte
    # ("Ablagerung", "Abschnitt", "seitlich", "seitens", "bissel", "fromage",
    # "sincerely", "tilltrigger", "untilst" duerfen NICHT matchen)
    assert parse_iso_date("Ablagerung 1985") is None
    assert parse_iso_date("Abschnitt 1985") is None
    assert parse_iso_date("abgesehen 1985") is None
    assert parse_iso_date("seitlich 1985") is None
    assert parse_iso_date("seitens 1985") is None
    assert parse_iso_date("bissel 1985") is None
    assert parse_iso_date("fromage 1985") is None
    assert parse_iso_date("sincerely 1985") is None
    # Bestehende Datumsangaben ohne Range-Praefix bleiben gleich (kein Regress)
    assert parse_iso_date("1985") == "1985-01-01"
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("vor 1985") == "1985-01-01"
    assert parse_iso_date("im Juni 2024") == "2024-06-01"


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
    # Englisch-typografische Quote-Paare (Word-/Office-Autoformat):
    # U+201C..U+201D (doppelt) und U+2018..U+2019 (einzeln).
    assert parse_iso_date("“2024-06-13”") == "2024-06-13"
    assert parse_iso_date("‘2024-06-13’") == "2024-06-13"
    assert parse_iso_date("“13. Juni 2024”") == "2024-06-13"
    assert parse_iso_date("‘ca. 1985’") == "1985-01-01"
    assert parse_iso_date("“Sommer 1985”") == "1985-06-01"
    # Leere englisch-typografische Paare → None (spiegelt ASCII-/„..."-Form)
    assert parse_iso_date("“”") is None
    assert parse_iso_date("‘’") is None
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


def test_parse_iso_date_trailing_paren_geschachtelt():
    """Verschachtelte trailing Klammer-Annotationen ("(Foto (gut))",
    "[Sammlung (Muster (jun.))]") werden vom Balanced-Bracket-Helper
    :func:`_strip_trailing_balanced_bracket` in einem Zug gestrippt.

    Die bestehende :data:`_TRAILING_PAREN_REMARK`-Regex schliesst Nest-Inhalt
    strukturell aus (Nicht-Klammer-Zeichenklasse ``[^\\(\\)\\[\\]\\{\\}]*``)
    und der ``$``-Anker verhindert einen iterativen Innen-nach-aussen-Strip,
    sodass geschachtelte Annotationen bisher stille auf None fielen. In
    Sammlungs-Notizen sind sie aber verbreitet: Provenienz-Anmerkungen mit
    eingebetteter Klammer-Sub-Info (``"(Foto (2020))"``, ``"(Provenienz
    (Auktion 2024))"``) oder mehrfach verschachtelte Museums-Etiketten
    (``"[Sammlung (Muster (jun.))]"``). Der Balanced-Helper zaehlt Klammer-
    Tiefe rueckwaerts und strippt die gesamte Gruppe, wenn ein passender
    Opener mit Tiefe 0 gefunden wird.
    """
    # Runde Klammern mit Nest
    assert parse_iso_date("13.06.2024 (Foto (gut))") == "2024-06-13"
    assert parse_iso_date("2024-06-13 (Provenienz (Auktion 2024))") == "2024-06-13"
    assert parse_iso_date("ca. 1985 (Sammlung (geerbt))") == "1985-01-01"
    # Eckige Klammern mit Nest
    assert parse_iso_date("1985 [Sammlung (Muster (jun.))]") == "1985-01-01"
    assert parse_iso_date("1985 [Foto (2020)]") == "1985-01-01"
    # Dreifache Schachtelung
    assert parse_iso_date("2024-06-13 [Foto [Auktion (2020)]]") == "2024-06-13"
    # Gemischte Klammer-Arten innerhalb des Nests (Fremd-Klammer als Content)
    assert parse_iso_date("2024-06-13 (Foto {gut})") == "2024-06-13"
    assert parse_iso_date("1985 [Foto {gut} (2020)]") == "1985-01-01"
    # Mit trailing Satzzeichen: erst Satzzeichen strippen, dann geschachtelt
    assert parse_iso_date("2024-06-13 (Foto (gut)).") == "2024-06-13"
    # Nur Klammer-Inhalt ohne Datum → None (Rekursion strippt, Rest ungueltig)
    assert parse_iso_date("(Foto (gut))") is None
    # Unbalanciert (mehr Openers als Closer) → kein Strip, kein Match
    assert parse_iso_date("2024-06-13 (Foto (gut)") is None
    # Unbalanciert (mehr Closer als Opener) → kein Strip, kein Match
    assert parse_iso_date("2024-06-13 Foto (gut))") is None
    # Bestehende Single-Level-Faelle bleiben unveraendert (kein Regress)
    assert parse_iso_date("13.06.2024 (Foto)") == "2024-06-13"
    assert parse_iso_date("2024-06-13 [Foto]") == "2024-06-13"
    assert parse_iso_date("2024-06-13 ()") == "2024-06-13"


def test_parse_iso_date_trailing_aera_marker():
    """Trailing Aera-Marker (DE/EN/Latein) - n. Chr., v. Chr., AD, BC, CE, BCE -
    werden abgestrippt, damit das Jahr fuer die Parser-Kaskade zurueck bleibt.

    Traditionelle Museums-Etiketten- und Auktions-Kataloge-Praxis in Sammlungen
    mit kulturhistorischer/archaeologischer Provenienz. Vor dem Fix fielen alle
    Formen mit Aera-Suffix stille auf None, obwohl das Jahr eindeutig ist. Die
    Aera-Angabe ist semantische Wert-Anmerkung ("welche Zeitrechnungs-Konven-
    tion"), keine Datums-Modifikation - Strip + Rekursion spiegelt das Konzept
    von _APPROX_PREFIX/_BOUNDARY_PREFIX (Praefix wird gestrippt, Datum bleibt
    unveraendert) auf die Suffix-Achse.
    """
    # Deutsche Marker (n. Chr. / v. Chr.)
    assert parse_iso_date("1985 n. Chr.") == "1985-01-01"
    assert parse_iso_date("1985 n.Chr.") == "1985-01-01"
    assert parse_iso_date("1985 nChr.") == "1985-01-01"
    assert parse_iso_date("1985 n Chr.") == "1985-01-01"
    assert parse_iso_date("1985 nach Christus") == "1985-01-01"
    # Englische/Latein Marker (AD / A.D. / A D)
    assert parse_iso_date("1985 AD") == "1985-01-01"
    assert parse_iso_date("1985 A.D.") == "1985-01-01"
    assert parse_iso_date("1985 A. D.") == "1985-01-01"
    assert parse_iso_date("1985 A D") == "1985-01-01"
    # Moderne akademische Konvention (CE / C.E. / Common Era)
    assert parse_iso_date("1985 CE") == "1985-01-01"
    assert parse_iso_date("1985 C.E.") == "1985-01-01"
    assert parse_iso_date("1985 C. E.") == "1985-01-01"
    # v.-Chr.-/BC-/BCE-Marker: Jahr bleibt der Anker; Range-Pruefung ent-
    # scheidet ueber Gueltigkeit. 1985 v.Chr. wird wie 1985 n.Chr. gelesen
    # (die Aera-Info geht in Freitext-Notizen, das ISO-Datum-Output ist die
    # 4-Ziffer-Zahl-Deutung). 500 v.Chr. faellt auf None wegen < 1800.
    assert parse_iso_date("1985 v. Chr.") == "1985-01-01"
    assert parse_iso_date("1985 v.Chr.") == "1985-01-01"
    assert parse_iso_date("1985 vor Christus") == "1985-01-01"
    assert parse_iso_date("1985 BC") == "1985-01-01"
    assert parse_iso_date("1985 B.C.") == "1985-01-01"
    assert parse_iso_date("1985 BCE") == "1985-01-01"
    assert parse_iso_date("1985 B.C.E.") == "1985-01-01"
    # BC-Marker mit ausserhalb-1800-Jahr faellt auf None (Jahres-Range-Pruefung
    # nach Aera-Strip), spiegelt "500" ohne Marker -> None.
    assert parse_iso_date("500 v. Chr.") is None
    assert parse_iso_date("500 vor Christus") is None
    assert parse_iso_date("500 BC") is None
    assert parse_iso_date("500 B.C.") is None
    assert parse_iso_date("500 BCE") is None
    assert parse_iso_date("500 B.C.E.") is None
    # Kombiniert mit vollstaendigem Datum (Tag + Monat + Jahr + Marker)
    assert parse_iso_date("13.06.2024 AD") == "2024-06-13"
    assert parse_iso_date("13.06.2024 n. Chr.") == "2024-06-13"
    assert parse_iso_date("2024-06-13 CE") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024 n. Chr.") == "2024-06-13"
    assert parse_iso_date("13 June 2024 AD") == "2024-06-13"
    # Kombiniert mit Jahrhundert-Notation (Arabisch und Roemisch)
    assert parse_iso_date("19. Jahrhundert n. Chr.") == "1800-01-01"
    assert parse_iso_date("19th century AD") == "1800-01-01"
    assert parse_iso_date("XIX. Jahrhundert n. Chr.") == "1800-01-01"
    assert parse_iso_date("XIX century AD") == "1800-01-01"
    # Case-insensitive (Etiketten in verschiedenen Schreibungen)
    assert parse_iso_date("1985 ad") == "1985-01-01"
    assert parse_iso_date("1985 AD") == "1985-01-01"
    assert parse_iso_date("1985 Ad") == "1985-01-01"
    assert parse_iso_date("1985 N. CHR.") == "1985-01-01"
    assert parse_iso_date("1985 Ce") == "1985-01-01"
    # Bestehende Formen ohne Aera-Marker bleiben unveraendert (kein Regress)
    assert parse_iso_date("1985") == "1985-01-01"
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("Sommer 1985") == "1985-06-01"
    # Nicht-Aera-Suffix darf NICHT als Aera-Marker gedeutet werden
    assert parse_iso_date("1985 Museum") is None
    assert parse_iso_date("1985 gefunden") is None
    assert parse_iso_date("2024-06-13 Foto") is None
    # Reine Aera-Markierung ohne Datum bleibt None (kein Freitext-Ratephiel)
    assert parse_iso_date("n. Chr.") is None
    assert parse_iso_date("AD") is None
    assert parse_iso_date("CE") is None
    # Leading Aera-Form ("AD 1985") wird NICHT durch trailing-Strip erfasst -
    # der Regex verlangt \s+ vor der Aera-Angabe, damit "AD 1985" (leading)
    # nicht als "AD" + " 1985" (mit Ende-Anker) fehlgeleitet interpretiert wird.
    # Sie wird stattdessen vom symmetrischen _LEADING_ERA_MARKER-Strip
    # erfasst (siehe test_parse_iso_date_leading_aera_marker).
    assert parse_iso_date("AD 1985") == "1985-01-01"
    # Underscore-Trenner in Filename-Artefakten ("Fund_AD_2024") bleibt None -
    # der Regex verlangt Whitespace vor der Aera-Angabe, damit Filesystem-
    # Segmente nicht versehentlich als Aera-Suffix gelesen werden.
    assert parse_iso_date("Fund_AD_2024") is None


def test_parse_iso_date_leading_aera_marker():
    """Leading Aera-Marker (DE/EN/Latein) - AD, A.D., CE, C.E., n. Chr., nach
    Christus, BC, BCE, v. Chr., vor Christus - werden vom Anfang der Eingabe
    abgestrippt, damit das Datum fuer die Parser-Kaskade zurueck bleibt.

    Spiegelt :func:`test_parse_iso_date_trailing_aera_marker` auf die
    Praefix-Achse: waehrend die Trailing-Form ("1985 AD") die im
    wissenschaftlichen Diskurs typische Postfix-Setzung abdeckt, kommt die
    Leading-Form ("AD 1985") in aelteren Museums-Etiketten mit lateinischer
    Datierungs-Grammatik ("Anno Domini 1985" -> "AD 1985"), in englisch-
    sprachigen Auktions-Katalogen und in akademischen Referenzen aus dem
    19./20. Jhdt. vor. Vor dem Fix fielen alle Leading-Formen stille auf
    None. Konzept identisch zur Trailing-Form: Strip + Rekursion, das
    ISO-Datum-Output ist identisch zur reinen Form.
    """
    # Latein-/Englisch-Marker (AD / A.D. / A. D. / A D)
    assert parse_iso_date("AD 1985") == "1985-01-01"
    assert parse_iso_date("A.D. 1985") == "1985-01-01"
    assert parse_iso_date("A. D. 1985") == "1985-01-01"
    assert parse_iso_date("A D 1985") == "1985-01-01"
    # Moderne akademische Konvention (CE / C.E. / Common Era)
    assert parse_iso_date("CE 1985") == "1985-01-01"
    assert parse_iso_date("C.E. 1985") == "1985-01-01"
    assert parse_iso_date("C. E. 1985") == "1985-01-01"
    # Deutsche Marker (n. Chr. / n.Chr. / n Chr. / nChr.)
    assert parse_iso_date("n. Chr. 1985") == "1985-01-01"
    assert parse_iso_date("n.Chr. 1985") == "1985-01-01"
    assert parse_iso_date("n Chr. 1985") == "1985-01-01"
    assert parse_iso_date("nChr. 1985") == "1985-01-01"
    # Deutsche Vollform (nach Christus)
    assert parse_iso_date("nach Christus 1985") == "1985-01-01"
    # v. Chr. / vor Christus - Jahr bleibt der Anker; Range-Pruefung ent-
    # scheidet ueber Gueltigkeit (1985 im Band -> "1985-01-01"; 500 aussen
    # -> None). Spiegelt die Trailing-Form-Semantik.
    assert parse_iso_date("v. Chr. 1985") == "1985-01-01"
    assert parse_iso_date("v.Chr. 1985") == "1985-01-01"
    assert parse_iso_date("vor Christus 1985") == "1985-01-01"
    # BC / BCE / B.C. / B.C.E. - Latein-Aequivalent zu v. Chr.
    assert parse_iso_date("BC 1985") == "1985-01-01"
    assert parse_iso_date("B.C. 1985") == "1985-01-01"
    assert parse_iso_date("BCE 1985") == "1985-01-01"
    assert parse_iso_date("B.C.E. 1985") == "1985-01-01"
    # BC/BCE/v. Chr. mit Jahr < 1800: Jahres-Range-Pruefung filtert
    # transparent auf None (spiegelt "500" ohne Aera-Marker -> None und
    # die Trailing-Form-Behandlung "500 BC" -> None).
    assert parse_iso_date("BC 500") is None
    assert parse_iso_date("BCE 500") is None
    assert parse_iso_date("v. Chr. 500") is None
    assert parse_iso_date("vor Christus 500") is None
    # Kombiniert mit vollstaendigem Datum (Aera + Tag + Monat + Jahr)
    assert parse_iso_date("AD 13.06.2024") == "2024-06-13"
    assert parse_iso_date("n. Chr. 13.06.2024") == "2024-06-13"
    assert parse_iso_date("CE 2024-06-13") == "2024-06-13"
    assert parse_iso_date("n. Chr. 13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("AD 13 June 2024") == "2024-06-13"
    # Kombiniert mit Jahrhundert-Notation (Arabisch und Roemisch)
    assert parse_iso_date("AD 19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("n. Chr. 19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("AD 19th century") == "1800-01-01"
    assert parse_iso_date("AD XIX. Jahrhundert") == "1800-01-01"
    # Kombiniert mit Trailing-Aera-Marker (Strip erfolgt zweischichtig:
    # erst Leading, dann Trailing im Rekursions-Aufruf). Semantisch redundant
    # aber in geerbten Notizen mit doppelter Sicherheits-Aera-Setzung
    # gelegentlich zu finden.
    assert parse_iso_date("AD 1985 AD") == "1985-01-01"
    assert parse_iso_date("n. Chr. 1985 n. Chr.") == "1985-01-01"
    # Case-insensitive (Etiketten in verschiedenen Schreibungen)
    assert parse_iso_date("ad 1985") == "1985-01-01"
    assert parse_iso_date("Ad 1985") == "1985-01-01"
    assert parse_iso_date("Ce 1985") == "1985-01-01"
    assert parse_iso_date("N. CHR. 1985") == "1985-01-01"
    assert parse_iso_date("bce 500") is None
    # Bestehende Formen ohne Aera-Marker bleiben unveraendert (kein Regress)
    assert parse_iso_date("1985") == "1985-01-01"
    assert parse_iso_date("1985 AD") == "1985-01-01"
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("Sommer 1985") == "1985-06-01"
    # Non-Aera-Praefix darf NICHT als Aera-Marker gedeutet werden
    assert parse_iso_date("Alpha 1985") is None
    assert parse_iso_date("Adventure 1985") is None
    assert parse_iso_date("Certain 1985") is None
    assert parse_iso_date("Adapter 1985") is None
    # November beginnt mit "N" - darf nicht als n.Chr.-Kurzform gedeutet
    # werden (der Regex verlangt "chr" nach "n", nicht "ovember").
    assert parse_iso_date("November 1985") == "1985-11-01"
    # Reine Aera-Markierung ohne Datum bleibt None (kein Freitext-Ratespiel;
    # \s+ nach Marker verlangt ein Datum-Wort).
    assert parse_iso_date("AD") is None
    assert parse_iso_date("A.D.") is None
    assert parse_iso_date("CE") is None
    assert parse_iso_date("n. Chr.") is None
    assert parse_iso_date("BCE") is None
    # Aera-Marker OHNE Whitespace zu einem Datum ("AD1985") wird NICHT als
    # Aera gedeutet - der Regex verlangt \s+ nach dem Marker, damit die
    # Compact-Form nicht als Aera-Praefix fehlgeleitet wird.
    assert parse_iso_date("AD1985") is None
    # Boundary-Praefix ohne Christus-Marker ("vor 1985"/"nach 1985") bleibt
    # unveraendert - _LEADING_ERA_MARKER verlangt obligatorisches "christus"/
    # "chr" nach "vor"/"nach", damit reines "vor 1985" durch _BOUNDARY_PREFIX
    # als Boundary erkannt wird (kein Konflikt zwischen den beiden Achsen).
    assert parse_iso_date("vor 1985") == "1985-01-01"
    assert parse_iso_date("nach 1985") == "1985-01-01"
    # Underscore-Trenner in Filename-Artefakten ("AD_1985") bleibt None -
    # der Regex verlangt Whitespace nach der Aera-Angabe, damit Filesystem-
    # Segmente nicht versehentlich als Aera-Praefix gelesen werden.
    assert parse_iso_date("AD_1985") is None
    # Kombiniert mit Annaeherungs-/Klammer-Praefix (mehrschichtige Rekursion)
    assert parse_iso_date("ca. AD 1985") == "1985-01-01"
    assert parse_iso_date("(AD 1985)") == "1985-01-01"


def test_parse_iso_date_trailing_annaeherungs_suffix():
    """Trailing Annaeherungs-Suffix (DE/EN) - ca./circa/approx./approximately/
    estimated/est./around/about/roughly/etwa/vermutlich/schaetzungsweise/
    ungefaehr/wahrscheinlich/moeglicherweise/evtl./eventuell/perhaps/possibly/
    maybe - wird vom Ende der Eingabe abgestrippt, damit das Datum fuer die
    Parser-Kaskade zurueck bleibt.

    Spiegelt :func:`test_parse_iso_date_annaeherungs_praefix` /
    :func:`test_parse_iso_date_annaeherungs_praefix_erweitert` /
    :func:`test_parse_iso_date_wahrscheinlichkeits_praefix` auf die Suffix-
    Achse: waehrend die Leading-Form ("ca. 1985", "vermutlich 2020") die im
    wissenschaftlichen Diskurs typische Praefix-Setzung abdeckt, kommt die
    Trailing-Form ("1985 ca.", "2020 vermutlich", "Juni 2020 ungefaehr") in
    geerbten Sammlungs-Notizen und Etiketten verbreitet vor, in denen der
    Vorbesitzer das Datum voranstellt und den Praezisions-Marker nachtraeglich
    anfuegt. Vor dem Fix fielen alle Trailing-Formen stille auf None (das
    Datum-Feld verlor den Bezug, obwohl das Jahr eindeutig lesbar ist).
    Konzept identisch zur Leading-Form: Strip + Rekursion, das ISO-Datum-
    Output ist identisch zur reinen Form; die Praezisions-Angabe ist
    semantische Wert-Anmerkung und bleibt im Freitext (notizen).
    """
    # Kurzform-DE/EN-Marker mit Punkt (haeufigste Etikett-Praxis)
    assert parse_iso_date("1985 ca.") == "1985-01-01"
    assert parse_iso_date("1985 ca") == "1985-01-01"
    assert parse_iso_date("2020 circa") == "2020-01-01"
    assert parse_iso_date("2024 approx.") == "2024-01-01"
    assert parse_iso_date("2024 approx") == "2024-01-01"
    assert parse_iso_date("1995 approximately") == "1995-01-01"
    assert parse_iso_date("1995 around") == "1995-01-01"
    assert parse_iso_date("2010 about") == "2010-01-01"
    assert parse_iso_date("1985 roughly") == "1985-01-01"
    assert parse_iso_date("1985 estimated") == "1985-01-01"
    assert parse_iso_date("1985 est.") == "1985-01-01"
    # Deutsche Wortformen (Praezision und Wahrscheinlichkeit)
    assert parse_iso_date("2020 etwa") == "2020-01-01"
    assert parse_iso_date("1985 vermutlich") == "1985-01-01"
    assert parse_iso_date("1985 schaetzungsweise") == "1985-01-01"
    assert parse_iso_date("1985 schätzungsweise") == "1985-01-01"
    assert parse_iso_date("1985 ungefaehr") == "1985-01-01"
    assert parse_iso_date("1985 ungefähr") == "1985-01-01"
    assert parse_iso_date("1985 wahrscheinlich") == "1985-01-01"
    assert parse_iso_date("1985 moeglicherweise") == "1985-01-01"
    assert parse_iso_date("1985 möglicherweise") == "1985-01-01"
    assert parse_iso_date("1985 evtl.") == "1985-01-01"
    assert parse_iso_date("1985 evtl") == "1985-01-01"
    assert parse_iso_date("1985 eventuell") == "1985-01-01"
    # Englische Wahrscheinlichkeits-Wortformen
    assert parse_iso_date("1985 perhaps") == "1985-01-01"
    assert parse_iso_date("1985 possibly") == "1985-01-01"
    assert parse_iso_date("1985 maybe") == "1985-01-01"
    # Kombiniert mit vollstaendigem Datum (Tag + Monat + Jahr + Suffix)
    assert parse_iso_date("13.06.2024 ca.") == "2024-06-13"
    assert parse_iso_date("13.06.2024 vermutlich") == "2024-06-13"
    assert parse_iso_date("2024-06-13 approx") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024 ca.") == "2024-06-13"
    assert parse_iso_date("13 June 2024 estimated") == "2024-06-13"
    # Kombiniert mit Monatsname (Praezisions-Marker nach "Monat Jahr")
    assert parse_iso_date("Juni 2020 ca.") == "2020-06-01"
    assert parse_iso_date("June 2020 approx") == "2020-06-01"
    assert parse_iso_date("Juni 2020 ungefaehr") == "2020-06-01"
    # Kombiniert mit Jahreszeit + Jahr
    assert parse_iso_date("Sommer 1985 ca.") == "1985-06-01"
    assert parse_iso_date("Winter 2023 vermutlich") == "2023-12-01"
    # Case-insensitive (Etiketten in Grossbuchstaben/Mixed-Case)
    assert parse_iso_date("1985 CA.") == "1985-01-01"
    assert parse_iso_date("1985 Circa") == "1985-01-01"
    assert parse_iso_date("2020 VERMUTLICH") == "2020-01-01"
    assert parse_iso_date("1985 Estimated") == "1985-01-01"
    # Kombiniert mit Trailing-Aera-Marker (Strip erfolgt zweischichtig:
    # erst Aera, dann Praezisions-Marker im Rekursions-Aufruf). In der Praxis
    # eine Ueber-Sicherheits-Notation ("Jahr AD, aber Genauigkeit unsicher").
    assert parse_iso_date("1985 AD ca.") == "1985-01-01"
    assert parse_iso_date("1985 n. Chr. vermutlich") == "1985-01-01"
    # Kombiniert mit Trailing-Satzzeichen (Praezisions-Marker vor dem
    # Satzzeichen faellt via Rekursion nach dem Punkt-Strip): "1985 ca.!" ->
    # "1985 ca." -> "1985" -> "1985-01-01". Auch "1985 estimated!" -> "1985".
    assert parse_iso_date("1985 estimated!") == "1985-01-01"
    # Kombiniert mit Leading-Praefix (mehrschichtige Rekursion): sinnfrei
    # aber unschaedlich - jede Rekursions-Ebene strippt einen Marker.
    assert parse_iso_date("ca. 1985 ca.") == "1985-01-01"
    assert parse_iso_date("vermutlich 1985 vermutlich") == "1985-01-01"
    # Bestehende Formen ohne Suffix bleiben unveraendert (kein Regress)
    assert parse_iso_date("1985") == "1985-01-01"
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("vermutlich 1985") == "1985-01-01"
    assert parse_iso_date("Juni 2020") == "2020-06-01"
    # Non-Marker-Suffix darf NICHT als Praezisions-Marker gedeutet werden
    assert parse_iso_date("1985 Museum") is None
    assert parse_iso_date("1985 gefunden") is None
    assert parse_iso_date("2024-06-13 Foto") is None
    # Reiner Marker ohne Datum bleibt None (kein Freitext-Ratespiel)
    assert parse_iso_date("ca.") is None
    assert parse_iso_date("circa") is None
    assert parse_iso_date("vermutlich") is None
    # "um"/"gegen" NICHT als Trailing-Marker (nur Leading gelistet, siehe
    # _TRAILING_APPROX_SUFFIX-Kommentar): am Zeilenende in Sammler-Notizen
    # tragen sie ueberwiegend Praeposition-Bedeutung ("Foto 1985 um 14 Uhr",
    # "Foto 1985 gegen Norden"), nicht Praezisions-Bedeutung. Wenn der Rest-
    # String durch das Strippen nicht matcht, faellt die Eingabe auf None.
    assert parse_iso_date("1985 um") is None
    assert parse_iso_date("1985 gegen") is None
    # Suffix ohne Whitespace davor ("1985ca.") wird NICHT gestrippt - der
    # Regex verlangt \s+ vor dem Suffix, damit Compact-Formen wie "1985ca"
    # nicht versehentlich als Marker-Suffix gelesen werden (waere in
    # Sammler-Etiketten ohnehin extrem unkonventionell, weil Whitespace vor
    # dem Marker die Standard-Notations-Konvention ist).
    assert parse_iso_date("1985ca.") is None
    # Underscore-Trenner in Filename-Artefakten ("1985_ca") bleibt None
    assert parse_iso_date("1985_ca") is None


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


def test_parse_iso_date_year_first_monatsname():
    """Year-first Notation mit ausgeschriebenem Monatsnamen ('2024-Juni', '2024 June')."""
    # 2-Teil-Form (Monatsstart): verschiedene Separatoren
    assert parse_iso_date("2024-Juni") == "2024-06-01"
    assert parse_iso_date("2024 Juni") == "2024-06-01"
    assert parse_iso_date("2024.Juni") == "2024-06-01"
    assert parse_iso_date("2024/Juni") == "2024-06-01"
    assert parse_iso_date("2024, Juni") == "2024-06-01"
    # EN-Voll-/Kurzformen
    assert parse_iso_date("2024-June") == "2024-06-01"
    assert parse_iso_date("2024-Jun") == "2024-06-01"
    assert parse_iso_date("2024 June") == "2024-06-01"
    assert parse_iso_date("1999-Dezember") == "1999-12-01"
    assert parse_iso_date("1999-Dec") == "1999-12-01"
    # DE-Kurzformen und Umlaut
    assert parse_iso_date("2024-Mrz") == "2024-03-01"
    assert parse_iso_date("2024-Mar") == "2024-03-01"
    assert parse_iso_date("2024-Maerz") == "2024-03-01"
    assert parse_iso_date("2024-März") == "2024-03-01"
    # Case-insensitive (Normalisierung)
    assert parse_iso_date("2024-JUNI") == "2024-06-01"
    assert parse_iso_date("2024-juni") == "2024-06-01"
    # Optionales Punkt-Suffix am Monatsnamen ("2024-Jun.")
    assert parse_iso_date("2024-Jun.") == "2024-06-01"
    assert parse_iso_date("2024 Jun.") == "2024-06-01"
    # Roemische Monatsziffern: 2024-VI / 2024 XII
    assert parse_iso_date("2024-VI") == "2024-06-01"
    assert parse_iso_date("2024 XII") == "2024-12-01"
    # Kombiniert mit Annaeherungspraefix / Klammern / trailing Satzzeichen
    assert parse_iso_date("ca. 2024-Juni") == "2024-06-01"
    assert parse_iso_date("(2024-Juni)") == "2024-06-01"
    assert parse_iso_date("2024-Juni.") == "2024-06-01"


def test_parse_iso_date_year_first_monatsname_mit_tag():
    """Year-first DD-Monatsname-YYYY ('2024-Juni-13', voll qualifiziert)."""
    # 3-Teil-Form mit verschiedenen Separatoren
    assert parse_iso_date("2024-Juni-13") == "2024-06-13"
    assert parse_iso_date("2024 Juni 13") == "2024-06-13"
    assert parse_iso_date("2024.Juni.13") == "2024-06-13"
    assert parse_iso_date("2024/Juni/13") == "2024-06-13"
    # EN + DE Voll-/Kurzformen
    assert parse_iso_date("2024 June 13") == "2024-06-13"
    assert parse_iso_date("2024-Jun-13") == "2024-06-13"
    assert parse_iso_date("2024 Jan 1") == "2024-01-01"
    assert parse_iso_date("1985-Dezember-31") == "1985-12-31"
    # Englisches Tag-Ordinal-Suffix
    assert parse_iso_date("2024-June-1st") == "2024-06-01"
    assert parse_iso_date("2024 June 13th") == "2024-06-13"
    assert parse_iso_date("2024-Mar-3rd") == "2024-03-03"
    # Gemischte Separatoren (verschiedene zwischen Year/Month und Month/Day)
    assert parse_iso_date("2024 Juni-13") == "2024-06-13"
    assert parse_iso_date("2024-Juni 13") == "2024-06-13"
    # Roemische Monatsziffern
    assert parse_iso_date("2024-VI-13") == "2024-06-13"
    assert parse_iso_date("1985 XII 31") == "1985-12-31"
    # Kombiniert mit Annaeherungspraefix / Klammern / Anfuehrungszeichen
    assert parse_iso_date("ca. 2024-Juni-13") == "2024-06-13"
    assert parse_iso_date("(2024-Juni-13)") == "2024-06-13"
    assert parse_iso_date('"2024-Juni-13"') == "2024-06-13"


def test_parse_iso_date_year_first_monatsname_ungueltig():
    """Year-first Monatsname mit ungueltigen Werten faellt auf None."""
    # Unbekannter Monatsname (kein Wort aus _MONTH_NAMES)
    assert parse_iso_date("2024-Foo") is None
    assert parse_iso_date("2024-Foo-13") is None
    assert parse_iso_date("2024 abc") is None
    # Jahr ausserhalb 1800..2999
    assert parse_iso_date("0000-Juni") is None
    assert parse_iso_date("3000-Juni") is None
    assert parse_iso_date("1700-Juni-13") is None
    # Ungueltiger Tag
    assert parse_iso_date("2024-Juni-32") is None
    assert parse_iso_date("2024-Februar-30") is None  # Februar 30
    assert parse_iso_date("2024-Juni-00") is None
    # Roemische Monatsziffer ausser Range (XIII)
    assert parse_iso_date("2024-XIII") is None
    assert parse_iso_date("2024-XIII-13") is None


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


def test_parse_coordinates_dms_typografische_quotes():
    """DMS mit typografischen Curly-Quotes (Word/Outlook-Autoformat).

    Wenn ein Sammler die Koordinate in Word/LibreOffice-Writer/Outlook
    eingibt, wandelt Autoformat automatisch ``'`` -> ``’`` (U+2019) und
    ``"`` -> ``”`` (U+201D); dieselben Zeichen entstehen beim Kopieren
    aus einer PDF/DOCX/HTML-Quelle mit Smart-Punctuation. Vor dieser
    Erweiterung kannte das _DMS-Pattern nur ASCII-Apostroph und echtes
    Prime (U+2032/U+2033), sodass jede Word-basierte Dokumentationskette
    silenten Koordinaten-Datenverlust bei der Migration erzeugte.
    """
    # Right curly (Word-Standard-Autoformat: ' -> ’, " -> ”)
    lat, lon = parse_coordinates("46°30’15” N, 7°30’0” E")
    assert round(lat, 4) == 46.5042
    assert round(lon, 4) == 7.5
    # Left curly (kommt in aeltere DOCX/DTP-Quellen mit umgekehrter Curly-
    # Konvention und in Zwischenablage-Kopien aus manchen PDFs vor)
    lat, lon = parse_coordinates("46°30‘15“ N, 7°30‘0“ E")
    assert round(lat, 4) == 46.5042
    assert round(lon, 4) == 7.5
    # Gemischt: Curly-Minuten + ASCII-Sekunden (haeufig, wenn nur die
    # Einfach-Quote autoformatiert wurde und der Sammler die Sekunden
    # mit Umschalt-2 nachtippte)
    lat, lon = parse_coordinates("46°30’15\" N, 7°30’0\" E")
    assert round(lat, 4) == 46.5042
    assert round(lon, 4) == 7.5
    # Zwei aufeinander folgende Curly-Prime-Zeichen als Sekunden-Ersatz
    # (mirror der bestehenden ``''``-Konvention auf Curly-Achse)
    lat, lon = parse_coordinates("46°30’15’’ N, 7°30’0’’ E")
    assert round(lat, 4) == 46.5042
    assert round(lon, 4) == 7.5
    # Ohne Sekunden, nur Minuten mit Curly-Prime
    lat, lon = parse_coordinates("46°30’ S, 7°30’ W")
    assert round(lat, 4) == -46.5
    assert round(lon, 4) == -7.5
    # Bestehende ASCII- und U+2032/U+2033-Formen bleiben (kein Regress)
    lat, lon = parse_coordinates('46°30\'15" N, 7°30\'0" E')
    assert round(lat, 4) == 46.5042
    assert round(lon, 4) == 7.5
    lat, lon = parse_coordinates("46°30′15″ N, 7°30′0″ E")
    assert round(lat, 4) == 46.5042
    assert round(lon, 4) == 7.5


def test_parse_coordinates_plus_prefix():
    """Explizit positives Vorzeichen (z.B. aus GPS-Exporten) wird akzeptiert."""
    assert parse_coordinates("+46.5, +7.5") == (46.5, 7.5)
    assert parse_coordinates("+46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("+46.5, -7.5") == (46.5, -7.5)
    assert parse_coordinates("-46.5, +7.5") == (-46.5, 7.5)
    # Auch in der Praefix-Variante (N/S/E/W vorne, Plus an der Zahl)
    assert parse_coordinates("N+46.5 E+7.5") == (46.5, 7.5)


def test_parse_coordinates_iso6709_compact_decimal():
    """ISO 6709 Compact-Decimal-Form: ``+46.5+007.5/`` / ``+46.5+7.5`` / ``-46.5-7.5``.

    Internationaler Standard fuer Punkt-Koordinaten ohne Separator zwischen
    Lat und Lon - die beiden Vorzeichen dienen als impliziter Separator.
    Verbreitet in KML-Captions, HTML5-Microformats (Wikipedia-Geo-Microformat),
    GeoRSS-Feeds, exiftool-GPS-Output und maschinen-lesbaren GIS-Tool-Exporten.
    Vor dieser Erweiterung fielen alle Compact-Formen still auf None
    (_DECIMAL_PAIR verlangt expliziten Separator, _PREFIX_PAIR/_SUFFIX_PAIR_NO_SEP
    verlangen Richtungs-Buchstaben).
    """
    # Standard-Form mit fuehrender Null in Lon (spec-konform) und Trenner
    assert parse_coordinates("+46.5+007.5/") == (46.5, 7.5)
    # Ohne fuehrende Null in Lon (verbreitet in minimal formatierenden Tools)
    assert parse_coordinates("+46.5+7.5") == (46.5, 7.5)
    # Ohne trailing-Slash (einzelne Koordinate ohne Format-Trenner)
    assert parse_coordinates("+46.5+007.5") == (46.5, 7.5)
    # Negative Lat (Suedhalbkugel) + negative Lon (Westhalbkugel)
    assert parse_coordinates("-46.5-7.5") == (-46.5, -7.5)
    assert parse_coordinates("-46.5-007.5") == (-46.5, -7.5)
    # Gemischte Vorzeichen
    assert parse_coordinates("-46.5+7.5") == (-46.5, 7.5)
    assert parse_coordinates("+46.5-7.5") == (46.5, -7.5)
    # Null-Koordinaten (Aequator/Greenwich)
    assert parse_coordinates("+0+0") == (0.0, 0.0)
    assert parse_coordinates("-0-0") == (0.0, 0.0)
    # Ganzzahl ohne Dezimal
    assert parse_coordinates("+46+7") == (46.0, 7.0)
    # Whitespace um den ganzen Ausdruck ist toleriert
    assert parse_coordinates("  +46.5+7.5/  ") == (46.5, 7.5)
    # Out-of-Range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("+95.0+7.5") is None       # Lat ausserhalb [-90, 90]
    assert parse_coordinates("+46.5+185.0") is None     # Lon ausserhalb [-180, 180]
    # Regression: bestehende Decimal-Pair-Form mit Plus-Vorzeichen UND Separator
    # bleibt unveraendert (faellt durch das _DECIMAL_PAIR-Pattern, nicht durch
    # das neue ISO-6709-Pattern, weil dort der Separator zwischen den Zahlen
    # nicht akzeptiert wird - der ^...$-Anker macht das Pattern restriktiv).
    assert parse_coordinates("+46.5, +7.5") == (46.5, 7.5)
    # Decimal mit Vorzeichen UND DMS-Markern wird NICHT als ISO 6709 interpretiert
    # (das ^...$-Anker laesst zusaetzliche Tokens nicht zu) - faellt zurueck
    # auf das _DECIMAL_PAIR/_PREFIX_PAIR-Verhalten ohne stille Doppeldeutung.


def test_parse_coordinates_iso6709_compact_dm():
    """ISO 6709 Compact-DM-Form: ``+DDMM+DDDMM/`` (Grad + Minuten, ohne Trenner).

    Der ISO-6709-Standard fixiert die Ziffernbreite je Position: Lat = 2
    Grad-Ziffern + 2 Minuten-Ziffern (Gesamt 4 Ganzzahl-Ziffern), Lon = 3
    Grad-Ziffern + 2 Minuten-Ziffern (Gesamt 5 Ganzzahl-Ziffern); die zwei
    Vorzeichen zwischen den Zahlen dienen als impliziter Separator, die feste
    Ziffernbreite disambiguiert vom Compact-Decimal-Fall (1-2/1-3 Ganzzahl-
    Ziffern). Vor dieser Erweiterung fielen alle DM-Compact-Formen still auf
    None (weder _DECIMAL_PAIR noch _ISO6709_COMPACT_DECIMAL noch _PREFIX_PAIR/
    _SUFFIX_PAIR_NO_SEP passen).
    """
    # Standard-Form mit Trailing-Slash (spec-konform): 46°30' N,  7°45' E
    assert parse_coordinates("+4630+00745/") == (46.5, 7.75)
    # Ohne Trailing-Slash (einzelne Koordinate)
    assert parse_coordinates("+4630+00745") == (46.5, 7.75)
    # Negative Lat (Suedhalbkugel) + negative Lon (Westhalbkugel)
    assert parse_coordinates("-4630-00745/") == (-46.5, -7.75)
    assert parse_coordinates("-4630-00745") == (-46.5, -7.75)
    # Gemischte Vorzeichen
    assert parse_coordinates("-4630+00745") == (-46.5, 7.75)
    assert parse_coordinates("+4630-00745") == (46.5, -7.75)
    # Dezimal-Minuten: 46°30.5' N -> 46 + 30.5/60 = 46.5083...
    lat, lon = parse_coordinates("+4630.5+00745.5/")
    assert lat == pytest.approx(46.5083333, abs=1e-6)
    assert lon == pytest.approx(7.7583333, abs=1e-6)
    # ISO 6709 fixiert '.' als Dezimaltrenner - Komma-Notation kollidiert mit dem
    # _DECIMAL_PAIR-Separator und wird bewusst nicht als Compact-DM interpretiert.
    # Null-Koordinaten (Aequator/Greenwich)
    assert parse_coordinates("+0000+00000") == (0.0, 0.0)
    assert parse_coordinates("-0000-00000") == (0.0, 0.0)
    # Ganzzahl-Minuten am Rand: 89°59' N, 179°59' E ist noch gueltig
    lat, lon = parse_coordinates("+8959+17959/")
    assert lat == pytest.approx(89.9833333, abs=1e-6)
    assert lon == pytest.approx(179.9833333, abs=1e-6)
    # Whitespace um den ganzen Ausdruck ist toleriert
    assert parse_coordinates("  +4630+00745/  ") == (46.5, 7.75)
    # Out-of-Range durch ueberlaufende Minuten (Minuten > 60 machen Wert > Grad+1)
    # +9199+18099: Lat = 91 + 99/60 = 92.65 (>90), Lon = 180 + 99/60 = 181.65 (>180)
    assert parse_coordinates("+9199+18099/") is None
    # Regression: bestehende Compact-Decimal-Form bleibt unveraendert
    assert parse_coordinates("+46.5+7.5") == (46.5, 7.5)
    assert parse_coordinates("+46.5+007.5/") == (46.5, 7.5)


def test_parse_coordinates_iso6709_compact_dms():
    """ISO 6709 Compact-DMS-Form: ``+DDMMSS+DDDMMSS/`` (Grad + Min + Sek, ohne Trenner).

    Erweiterung des Compact-DM auf die Sekunden-Achse: Lat = 2+2+2 = 6 Ganzzahl-
    Ziffern, Lon = 3+2+2 = 7 Ganzzahl-Ziffern. Dezimalstellen (optional) haengen
    an den Sekunden. Verbreitet in exiftool-XMP-GPS-Exporten, Wikipedia-Geo-
    Microformat und GML-/KML-Formaten mit hoher Genauigkeit.
    """
    # Standard-Form: 46°30'15" N, 7°45'0" E
    lat, lon = parse_coordinates("+463015+0074500/")
    assert lat == pytest.approx(46.504166667, abs=1e-6)
    assert lon == pytest.approx(7.75, abs=1e-6)
    # Ohne Trailing-Slash
    lat, lon = parse_coordinates("+463015+0074500")
    assert lat == pytest.approx(46.504166667, abs=1e-6)
    assert lon == pytest.approx(7.75, abs=1e-6)
    # Negative Vorzeichen (Sued/West)
    lat, lon = parse_coordinates("-463015-0074500/")
    assert lat == pytest.approx(-46.504166667, abs=1e-6)
    assert lon == pytest.approx(-7.75, abs=1e-6)
    # Dezimal-Sekunden (hohe Genauigkeit): 15.5 Sek -> +0.5/3600
    lat, lon = parse_coordinates("+463015.5+0074500.5/")
    assert lat == pytest.approx(46.504305556, abs=1e-6)
    assert lon == pytest.approx(7.750138889, abs=1e-6)
    # ISO 6709 fixiert '.' als Dezimaltrenner (Komma-Notation kollidiert mit
    # dem _DECIMAL_PAIR-Separator und wird nicht als Compact-DMS interpretiert).
    # Null-Koordinaten (Aequator/Greenwich)
    assert parse_coordinates("+000000+0000000") == (0.0, 0.0)
    assert parse_coordinates("-000000-0000000") == (0.0, 0.0)
    # Whitespace um den ganzen Ausdruck ist toleriert
    lat, lon = parse_coordinates("  +463015+0074500/  ")
    assert lat == pytest.approx(46.504166667, abs=1e-6)
    # Out-of-Range: ueberlaufende Sekunden
    # +919999+1809999: Lat = 91 + 99/60 + 99/3600 = 92.6775 (>90)
    assert parse_coordinates("+919999+1809999/") is None
    # Regression: Compact-Decimal-Form bleibt unveraendert
    assert parse_coordinates("+46.5+7.5") == (46.5, 7.5)
    # Regression: Compact-DM-Form bleibt unveraendert
    assert parse_coordinates("+4630+00745/") == (46.5, 7.75)


def test_parse_coordinates_iso6709_compact_ambiguity():
    """Ziffernbreite disambiguiert die drei Compact-Formen (Decimal/DM/DMS).

    Die drei ISO-6709-Compact-Formen sind ueber die Ganzzahl-Ziffernbreite
    strukturell disjunkt:
      - 1-2 Ziffern Lat / 1-3 Ziffern Lon = Compact-Decimal (``+46+7``, ``+46.5+7.5``)
      - 4 Ziffern Lat  / 5 Ziffern Lon    = Compact-DM (``+4630+00745``)
      - 6 Ziffern Lat  / 7 Ziffern Lon    = Compact-DMS (``+463015+0074500``)

    Zwischenformen (3+4, 5+6, 7+8) matchen bewusst *keine* der Klassen und
    fallen auf None - jeder Compact-Match muss die Positions-Konvention exakt
    respektieren.
    """
    # 3-digit Lat ist keine der drei Formen -> None
    assert parse_coordinates("+463+0074") is None
    # 5-digit Lat / 6-digit Lon (zwischen DM und DMS) -> None
    assert parse_coordinates("+46301+007450") is None
    # 7-digit Lat / 8-digit Lon (jenseits DMS) -> None
    assert parse_coordinates("+4630150+00745000") is None
    # Regression: normale Formen alle drei greifen
    assert parse_coordinates("+46+7") == (46.0, 7.0)         # Compact-Decimal
    assert parse_coordinates("+4630+00745") == (46.5, 7.75)  # Compact-DM
    lat, lon = parse_coordinates("+463015+0074500")           # Compact-DMS
    assert lat == pytest.approx(46.504166667, abs=1e-6)


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


def test_parse_coordinates_dms_letter_markers():
    """DMS-Notation mit ASCII-Buchstaben-Markern ("46d30m15sN", "46deg30min15secN").

    Sehr verbreitet in Consumer-GPS-Geraete-Ausgaben (Garmin, TomTom),
    NMEA-/exiftool-ASCII-Dumps und Typewriter-Notation, die ° / ' / " nicht
    auf Standard-Tastaturen erzeugen koennen. Auch in handgeschriebenen
    Sammler-Notizen aus dem GPS-Boersen-Jahrzehnt (~2000-2015), wo der
    Sammler den Display-Text 1:1 abgeschrieben hat.
    """
    # Kompakt-Form ohne Whitespace (klassischer GPS-Display-Text)
    assert parse_coordinates("46d30m15sN 7d30m0sE") == (46.5 + 15/3600, 7.5)
    # Mit Whitespace zwischen den Komponenten
    assert parse_coordinates("46d 30m 15s N, 7d 30m 0s E") == (
        46.5 + 15/3600, 7.5,
    )
    # Vollform deg/min/sec
    assert parse_coordinates("46deg30min15secN 7deg30min0secE") == (
        46.5 + 15/3600, 7.5,
    )
    assert parse_coordinates("46deg 30min 15sec N, 7deg 30min 0sec E") == (
        46.5 + 15/3600, 7.5,
    )
    # Uppercase-Marker
    assert parse_coordinates("46D30M15SN 7D30M0SE") == (46.5 + 15/3600, 7.5)
    # Reine Grad-Form (kein M/S)
    assert parse_coordinates("46d N, 7d E") == (46.0, 7.0)
    # Dezimale Grad
    assert parse_coordinates("46.5d N 7.5d E") == (46.5, 7.5)
    # Grad + Minuten ohne Sekunden
    assert parse_coordinates("46d 30m N, 7d 30m E") == (46.5, 7.5)
    # Dezimale Minuten
    lat, lon = parse_coordinates("46d 30.5m N, 7d 30.5m E")
    assert abs(lat - (46 + 30.5/60)) < 1e-9
    assert abs(lon - (7 + 30.5/60)) < 1e-9
    # DE-Komma-Dezimal in Grad
    assert parse_coordinates("46,5d N 7,5d E") == (46.5, 7.5)
    # DE-Komma-Dezimal in Sekunden
    lat, lon = parse_coordinates("46d 30m 15,5s N, 7d 30m 0s E")
    assert abs(lat - (46.5 + 15.5/3600)) < 1e-9
    # Suedhalbkugel / Westhalbkugel (S auch als Sekunden-Marker moeglich,
    # aber die trailing-Direction-Grammatik greift trotzdem sauber)
    lat, lon = parse_coordinates("46d 30m 15s S, 7d 30m 0s W")
    assert abs(lat - -(46.5 + 15/3600)) < 1e-9
    assert lon == -7.5
    # Deutsche O = Ost
    assert parse_coordinates("46d 30m 0s N, 7d 30m 0s O") == (46.5, 7.5)
    # Punkt nach Marker ("46d.30m.15s.N" aus Notationen mit Punkt-Trenner)
    assert parse_coordinates("46d.30m.15s.N 7d.30m.0s.E") == (
        46.5 + 15/3600, 7.5,
    )
    # Verschiedene Pair-Separatoren
    assert parse_coordinates("46d 30m 15s N; 7d 30m 0s E") == (
        46.5 + 15/3600, 7.5,
    )
    assert parse_coordinates("46d 30m 15s N / 7d 30m 0s E") == (
        46.5 + 15/3600, 7.5,
    )
    # Mit umschliessenden Klammern
    assert parse_coordinates("(46d 30m 15s N, 7d 30m 0s E)") == (
        46.5 + 15/3600, 7.5,
    )
    # Mit Coord-Labels
    assert parse_coordinates(
        "Lat: 46d 30m 15s N, Lon: 7d 30m 0s E") == (46.5 + 15/3600, 7.5)
    # Nur ein Koordinaten-Hit -> None (halbe Koordinate ist nichts wert)
    assert parse_coordinates("46d 30m 15s N") is None
    # Out-of-Range bleibt None
    assert parse_coordinates("95d N, 7d E") is None
    assert parse_coordinates("46d N, 200d E") is None
    # Bestehende DMS-Form mit ° / ' / " bleibt unveraendert (kein Regress)
    assert parse_coordinates("46° 30' 15\" N, 7° 30' 0\" E") == (
        46.5 + 15/3600, 7.5,
    )
    # Bestehende Colon-DMS bleibt unveraendert (kein Regress)
    assert parse_coordinates("46:30:15 N, 7:30:0 E") == (46.5 + 15/3600, 7.5)
    # Bestehende dezimale Form bleibt unveraendert (kein Regress)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)


def test_parse_coordinates_invalid():
    assert parse_coordinates("") is None
    assert parse_coordinates(None) is None
    assert parse_coordinates("foo") is None
    assert parse_coordinates("95.0, 7.5") is None     # lat out of range
    assert parse_coordinates("46.5, 200.0") is None   # lon out of range
    assert parse_coordinates("46.5") is None          # nur eine Zahl


def test_parse_coordinates_url_encoded_komma():
    """URL-encoded Komma (%2C) - aus dem Browser kopierte Geo-URLs.

    Sammler kopieren die Google-Maps- oder generische Share-URL direkt aus dem
    Browser-Adress-Feld ins Fundort-Feld. Das Komma zwischen lat/lon wird beim
    RFC-3986-Percent-Encoding als ``%2C`` (Grossbuchstabe, Standard-Konvention)
    oder ``%2c`` (Kleinbuchstabe, tolerante Encoder-Variante) kodiert. Ohne
    Normalisierung faellt das Muster durch die _DECIMAL_PAIR-Separator-Klasse
    (``%`` gehoert nicht dazu) und liefert None.
    """
    # Standard Google Maps mit URL-encoded Komma
    assert parse_coordinates(
        "https://www.google.com/maps?q=46.5%2C7.5") == (46.5, 7.5)
    # Kleinbuchstabe-Varianten (tolerante Encoder-Praxis)
    assert parse_coordinates(
        "https://www.google.com/maps?q=46.5%2c7.5") == (46.5, 7.5)
    # Reines Zahlenpaar mit %2C ohne URL-Kontext
    assert parse_coordinates("46.5%2C7.5") == (46.5, 7.5)
    # Mit Vorzeichen (Suedhalbkugel)
    assert parse_coordinates("-46.5%2C-7.5") == (-46.5, -7.5)
    # Out-of-range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("100%2C50") is None
    # Regression: normales Komma weiterhin gueltig
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)


def test_parse_coordinates_url_query_params():
    """URL-Query-Parameter-Formen (lat=/lon=/mlat=/mlon=/latitude=/longitude=).

    OpenStreetMap-Share-Links und generische Geo-URL-Formate uebermitteln
    Koordinaten als zwei separate Query-Parameter mit ``&``-Separator dazwischen
    (``?mlat=46.5&mlon=7.5``, ``?lat=46.5&lon=7.5``). Ohne die Erweiterung um
    ``mlat``/``mlon`` in _COORD_LABEL und ``&`` in der _DECIMAL_PAIR-Separator-
    Klasse fielen alle Share-URL-Formen stille auf None.
    """
    # OSM Share-Link ("mark lat/lon" fuer Marker-Position)
    assert parse_coordinates(
        "https://www.openstreetmap.org/?mlat=46.5&mlon=7.5") == (46.5, 7.5)
    # Reine Query-Params ohne URL-Kontext
    assert parse_coordinates("?mlat=46.5&mlon=7.5") == (46.5, 7.5)
    # Generische lat/lon-Parameter
    assert parse_coordinates("?lat=46.5&lon=7.5") == (46.5, 7.5)
    assert parse_coordinates(
        "https://example.com/geo?lat=46.5&lon=7.5") == (46.5, 7.5)
    # Verbose latitude/longitude
    assert parse_coordinates("?latitude=46.5&longitude=7.5") == (46.5, 7.5)
    # Case-insensitive
    assert parse_coordinates("?MLAT=46.5&MLON=7.5") == (46.5, 7.5)
    # Mit Vorzeichen (Suedhalbkugel)
    assert parse_coordinates("?lat=-46.5&lon=-7.5") == (-46.5, -7.5)
    # Mit trailing Fragment (OSM hat oft ein #map=... Suffix nach den Query-Params)
    assert parse_coordinates(
        "?mlat=46.5&mlon=7.5#map=15/46.5/7.5") == (46.5, 7.5)
    # Out-of-range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("?lat=100&lon=50") is None
    # Fehlender zweiter Parameter -> None (keine halben Koordinaten)
    assert parse_coordinates("?lat=46.5") is None
    # Regression: bestehende URL-Formen weiterhin gueltig
    assert parse_coordinates(
        "https://www.google.com/maps/@46.5,7.5,15z") == (46.5, 7.5)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)


def test_parse_coordinates_ampersand_separator():
    """Ampersand als natuerlicher AND-Separator zwischen zwei Zahlen.

    Konsistent zur URL-Query-Anwendung: ``&`` als Separator im _DECIMAL_PAIR
    laesst auch natuerlich-sprachliche Zahlen-Paare mit ``&`` als Trenner
    durch (``46.5 & 7.5`` als "46.5 UND 7.5"), was in geerbten Sammlungs-
    Notizen gelegentlich vorkommt (Excel-Copy-Paste, Hand-Notizen).
    """
    assert parse_coordinates("46.5 & 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5&7.5") == (46.5, 7.5)
    # Regression: bestehende Separatoren weiterhin gueltig
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5; 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5 7.5") == (46.5, 7.5)
