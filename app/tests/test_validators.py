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


def test_parse_coordinates_invalid():
    assert parse_coordinates("") is None
    assert parse_coordinates(None) is None
    assert parse_coordinates("foo") is None
    assert parse_coordinates("95.0, 7.5") is None     # lat out of range
    assert parse_coordinates("46.5, 200.0") is None   # lon out of range
    assert parse_coordinates("46.5") is None          # nur eine Zahl
