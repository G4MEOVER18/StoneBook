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


def test_parse_iso_date_de_zweistelliges_jahr():
    """DE-Kompakt-Datum mit zweistelligem Jahr ("13.06.24", "1.6.24", "13/06/24",
    "13-06-24") mit Sammler-typischem Pivot 30 (00-30 -> 20YY, 31-99 -> 19YY).

    Verbreitet in handschriftlichen Sammler-Notizen, aus Kassen-/Auktions-
    Beleg-Scans, aus alten Excel-Tabellen mit Default-2-Ziffer-Jahr-Anzeige
    und aus DE-/CH-typischen Beschriftungs-Etiketten, wo die verkuerzte
    Notation Platz spart. Vor dem Fix fielen alle Formen still auf None,
    weil das Feld dann in strptime auf keinem der 4-Ziffer-Formate matchte
    und ``%y`` bewusst nicht in :data:`_DATE_FORMATS` steht (Python-strptime
    nutzt Pivot 68/69, der ``13.06.68`` als 2068-06-13 lesen wuerde - 42
    Jahre in der Zukunft, sicher nicht der Sammler-Intent). Nach dem Fix
    greift eine dedizierte Regex-Vorpruefung vor dem strptime-Loop.
    """
    # Basisform: DD.MM.YY mit Punkt-Separator (DE-Standard)
    assert parse_iso_date("13.06.24") == "2024-06-13"
    assert parse_iso_date("1.6.24") == "2024-06-01"
    # Ein- und zweistelliger Tag/Monat
    assert parse_iso_date("1.1.24") == "2024-01-01"
    assert parse_iso_date("31.12.24") == "2024-12-31"
    # Slash- und Bindestrich-Separator (symmetrisch zu den 4-Ziffer-Formen)
    assert parse_iso_date("13/06/24") == "2024-06-13"
    assert parse_iso_date("13-06-24") == "2024-06-13"
    # Pivot-Konvention: YY <= 30 -> 20YY, YY >= 31 -> 19YY
    assert parse_iso_date("13.06.00") == "2000-06-13"
    assert parse_iso_date("13.06.30") == "2030-06-13"
    assert parse_iso_date("13.06.31") == "1931-06-13"
    assert parse_iso_date("13.06.85") == "1985-06-13"
    assert parse_iso_date("13.06.99") == "1999-06-13"
    # Whitespace-Toleranz aussen
    assert parse_iso_date("  13.06.24  ") == "2024-06-13"


def test_parse_iso_date_de_zweistelliges_jahr_ungueltig():
    """Ungueltige DD.MM.YY-Formen fallen auf None.

    Semantisch ungueltige Kombinationen (Tag > 31, Monat > 12, nicht existente
    Kalender-Tage wie 30. Februar) und strukturell nicht passende Formen
    (Whitespace zwischen Zahl-Trennern, gemischte Separatoren, 1- oder
    3-Ziffer-Jahr) werden abgewiesen.
    """
    # Tag > 31 / Monat > 12
    assert parse_iso_date("32.13.24") is None
    assert parse_iso_date("32.06.24") is None
    assert parse_iso_date("13.13.24") is None
    # Nicht existenter Kalendertag (Feb 30)
    assert parse_iso_date("30.02.24") is None
    # Whitespace zwischen Zahl-Trennern
    assert parse_iso_date("13. 06. 24") is None
    # Gemischte Separatoren (Back-Reference \2 verlangt Symmetrie)
    assert parse_iso_date("13.06/24") is None
    assert parse_iso_date("13/06.24") is None
    assert parse_iso_date("13-06/24") is None
    # Nur ein-Ziffer-Jahr (kein Match; strptime %y verlangt exakt zwei Ziffern)
    assert parse_iso_date("13.06.2") is None
    # 4-Ziffer-Jahr faellt weiter durch die etablierten Formate, nicht durch
    # den neuen 2-Ziffer-Zweig (Regress-Anker)
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("1.1.2020") == "2020-01-01"


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


def test_parse_iso_date_monat_range_jahr():
    """Month-Range innerhalb eines Jahres ('Juni/Juli 2024', 'Mai-Juni 1985',
    'Juni bis Juli 2024') spiegelt _YEAR_RANGE/_YEAR_RANGE_WORD auf die
    Monats-Achse (Start-Monat als ISO-Datum, End-Monat als semantische
    Anmerkung im Freitext)."""
    # Symbol-Trenner (Slash/Bindestrich, DE-Standard-Notation)
    assert parse_iso_date("Juni/Juli 2024") == "2024-06-01"
    assert parse_iso_date("Juni-Juli 2024") == "2024-06-01"
    assert parse_iso_date("Mai-Juni 1985") == "1985-05-01"
    assert parse_iso_date("August/September 2000") == "2000-08-01"
    # Kurzformen (Jun/Jul, DE-/EN-Kompakt)
    assert parse_iso_date("Jun/Jul 2024") == "2024-06-01"
    assert parse_iso_date("Jun-Jul 2024") == "2024-06-01"
    # En-/Em-Dash (typografische Print-/Word-Autoformat-Trenner)
    assert parse_iso_date("Juni – Juli 2024") == "2024-06-01"
    assert parse_iso_date("Juni — Juli 2024") == "2024-06-01"
    # Umlaut im Monatsnamen
    assert parse_iso_date("März/April 2020") == "2020-03-01"
    # Kurzform mit Punkt (DE-Etiketten-Praxis)
    assert parse_iso_date("Nov./Dez. 2023") == "2023-11-01"
    # Wort-Trenner (DE bis / EN to/till/until) - spiegelt _YEAR_RANGE_WORD
    assert parse_iso_date("Juni bis Juli 2024") == "2024-06-01"
    assert parse_iso_date("June to July 2024") == "2024-06-01"
    assert parse_iso_date("June till July 2024") == "2024-06-01"
    assert parse_iso_date("June until July 2024") == "2024-06-01"
    # Case-insensitiv (Caps-Lock-Notizen aus geerbten Sammler-Etiketten)
    assert parse_iso_date("JUNI/JULI 2024") == "2024-06-01"
    assert parse_iso_date("Juni BIS Juli 2024") == "2024-06-01"
    # Englische Monatsnamen (EXIF, Foto-Bibliotheks-Exporte)
    assert parse_iso_date("June/July 2024") == "2024-06-01"
    assert parse_iso_date("May-June 1985") == "1985-05-01"
    # Inverted Range (Tippfehler oder Cross-Year-Semantik wie
    # "November-Februar 2024" = Nov 2023 - Feb 2024) - liefert Start-Monat,
    # spiegelt _YEAR_RANGE ("1985-1980" -> "1985-01-01")
    assert parse_iso_date("November-Februar 2024") == "2024-11-01"
    # Kombinationen mit bestehenden Modifikatoren (Rekursion)
    assert parse_iso_date("ca. Juni/Juli 2024") == "2024-06-01"
    assert parse_iso_date("circa Juni-Juli 2024") == "2024-06-01"
    assert parse_iso_date("~Juni/Juli 2024") == "2024-06-01"
    assert parse_iso_date("(Juni/Juli 2024)") == "2024-06-01"
    assert parse_iso_date("[Mai-Juni 1985]") == "1985-05-01"
    assert parse_iso_date("Juni/Juli 2024.") == "2024-06-01"
    assert parse_iso_date("Juni/Juli 2024,") == "2024-06-01"
    assert parse_iso_date("im Juni/Juli 2024") == "2024-06-01"


def test_parse_iso_date_monat_range_jahr_ungueltig():
    """Jahr ausserhalb [1800, 2999] oder unbekannter Monatsname in einem der
    zwei Teile -> None; bestehende 2-Teil-Form (_MONTH_YEAR) bleibt
    unveraendert (kein Regress)."""
    # Jahr ausserhalb des gueltigen Bandes
    assert parse_iso_date("Juni/Juli 1700") is None
    assert parse_iso_date("Juni/Juli 3000") is None
    # Unbekannter Monatsname in einem der Teile - Match faellt durch, kein
    # Fallback auf "Juni 2024"
    assert parse_iso_date("Juni/xxx 2024") is None
    assert parse_iso_date("xxx/Juli 2024") is None
    # Bestehende 2-Teil-Form _MONTH_YEAR bleibt unveraendert (Disjunktheit)
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("Juni-2024") == "2024-06-01"
    assert parse_iso_date("Juni/2024") == "2024-06-01"
    assert parse_iso_date("Juni.2024") == "2024-06-01"
    # Bestehende Jahres-Range (_YEAR_RANGE) bleibt unveraendert (kein Regress)
    assert parse_iso_date("1985-1990") == "1985-01-01"
    assert parse_iso_date("1985 bis 1990") == "1985-01-01"


def test_parse_iso_date_tages_range_monat_jahr():
    """Tages-Range innerhalb eines Monats mit Monatsname ('5.-7. Juni 2024',
    '5-7 June 2024', '5 bis 7 Juni 2024') spiegelt _YEAR_RANGE / _MONTH_RANGE_YEAR
    auf die Tages-Achse (Start-Tag als ISO-Datum, End-Tag als semantische
    Anmerkung im Freitext)."""
    # DE-Standardnotation "TAG.-TAG. Monat YYYY" (Etiketten, Sammlungs-Notizen)
    assert parse_iso_date("5.-7. Juni 2024") == "2024-06-05"
    assert parse_iso_date("12.-14. August 2020") == "2020-08-12"
    assert parse_iso_date("1.-3. März 2020") == "2020-03-01"
    # DE-Kurzform ohne Punkte "TAG-TAG Monat YYYY"
    assert parse_iso_date("5-7 Juni 2024") == "2024-06-05"
    assert parse_iso_date("12-14 August 2020") == "2020-08-12"
    # Mit Whitespace um den Bindestrich (Freitext-Praxis)
    assert parse_iso_date("5. - 7. Juni 2024") == "2024-06-05"
    assert parse_iso_date("5 - 7 Juni 2024") == "2024-06-05"
    # En-/Em-Dash (typografische Print-/Word-Autoformat-Trenner)
    assert parse_iso_date("5–7 Juni 2024") == "2024-06-05"
    assert parse_iso_date("5—7 Juni 2024") == "2024-06-05"
    assert parse_iso_date("5.–7. Juni 2024") == "2024-06-05"
    # Wort-Trenner DE (bis) - spiegelt _YEAR_RANGE_WORD / _MONTH_RANGE_YEAR
    assert parse_iso_date("5 bis 7 Juni 2024") == "2024-06-05"
    assert parse_iso_date("5. bis 7. Juni 2024") == "2024-06-05"
    # Wort-Trenner EN (to/till/until)
    assert parse_iso_date("5 to 7 June 2024") == "2024-06-05"
    assert parse_iso_date("5 till 7 June 2024") == "2024-06-05"
    assert parse_iso_date("5 until 7 June 2024") == "2024-06-05"
    # Englische Monatsnamen (EXIF, Boersen-Zitate, Foto-Captions)
    assert parse_iso_date("5-7 June 2024") == "2024-06-05"
    assert parse_iso_date("12-14 August 2020") == "2020-08-12"
    assert parse_iso_date("1-3 May 1985") == "1985-05-01"
    # Kurzformen (Jun/Aug, DE/EN-Kompakt)
    assert parse_iso_date("5-7 Jun 2024") == "2024-06-05"
    assert parse_iso_date("12-14 Aug 2020") == "2020-08-12"
    # Mit Punkt nach Monats-Kurzform (DE-Etiketten-Praxis)
    assert parse_iso_date("5.-7. Jun. 2024") == "2024-06-05"
    # EN-Ordinal-Suffix am Tag (spiegelt _DAY_MONTH_YEAR)
    assert parse_iso_date("5th-7th June 2024") == "2024-06-05"
    assert parse_iso_date("1st to 3rd March 2024") == "2024-03-01"
    assert parse_iso_date("21st to 23rd December 2024") == "2024-12-21"
    # Umlaut im Monatsnamen
    assert parse_iso_date("5.-7. März 2024") == "2024-03-05"
    assert parse_iso_date("5-7 März 2024") == "2024-03-05"
    # Case-insensitiv (Caps-Lock-Notizen aus geerbten Sammler-Etiketten)
    assert parse_iso_date("5.-7. JUNI 2024") == "2024-06-05"
    assert parse_iso_date("5 BIS 7 Juni 2024") == "2024-06-05"
    # Inverted Range (Tippfehler) - Start-Tag, spiegelt _MONTH_RANGE_YEAR
    # ("November-Februar 2024" -> "2024-11-01")
    assert parse_iso_date("7.-5. Juni 2024") == "2024-06-07"
    # Kombinationen mit bestehenden Modifikatoren (Rekursion)
    assert parse_iso_date("ca. 5.-7. Juni 2024") == "2024-06-05"
    assert parse_iso_date("circa 5-7 June 2024") == "2024-06-05"
    assert parse_iso_date("~5.-7. Juni 2024") == "2024-06-05"
    assert parse_iso_date("(5.-7. Juni 2024)") == "2024-06-05"
    assert parse_iso_date("[12-14 August 2020]") == "2020-08-12"
    assert parse_iso_date("5.-7. Juni 2024.") == "2024-06-05"
    assert parse_iso_date("5.-7. Juni 2024,") == "2024-06-05"
    assert parse_iso_date("vom 5.-7. Juni 2024") == "2024-06-05"


def test_parse_iso_date_tages_range_monat_jahr_ungueltig():
    """Jahr ausserhalb [1800, 2999], unbekannter Monatsname oder ungueltiger
    Start-Tag -> None; bestehende Formen (_DAY_MONTH_YEAR, _MONTH_RANGE_YEAR)
    bleiben unveraendert (kein Regress)."""
    # Jahr ausserhalb des gueltigen Bandes
    assert parse_iso_date("5.-7. Juni 1700") is None
    assert parse_iso_date("5-7 June 3000") is None
    # Unbekannter Monatsname - Match faellt durch, kein Fallback auf einen Tag
    assert parse_iso_date("5.-7. xxx 2024") is None
    assert parse_iso_date("5-7 foo 2024") is None
    # Ungueltiger Start-Tag (32/33) - Match faellt durch
    assert parse_iso_date("32.-33. Juni 2024") is None
    assert parse_iso_date("0-3 Juni 2024") is None
    # Ungueltiger Start-Tag im Monat (31. Februar) - datetime.date wirft ValueError
    assert parse_iso_date("31.-32. Feb 2024") is None
    # Slash als Trenner NICHT erlaubt (mehrdeutig mit US-Datumsformat M/D)
    assert parse_iso_date("5/7 Juni 2024") is None
    # Bestehende Einzel-Tag-Form _DAY_MONTH_YEAR bleibt unveraendert (Disjunktheit)
    assert parse_iso_date("5. Juni 2024") == "2024-06-05"
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("June 5, 2024") == "2024-06-05"
    # Bestehende Month-Range-Form _MONTH_RANGE_YEAR bleibt unveraendert
    assert parse_iso_date("Juni/Juli 2024") == "2024-06-01"
    assert parse_iso_date("Mai-Juni 1985") == "1985-05-01"


def test_parse_iso_date_tages_range_numerischer_monat():
    """Tages-Range mit numerischem Monat wird auf den Start-Tag aufgeloest.

    ``13.-15.06.2024`` / ``13. bis 15.06.2024`` / ``13-15.06.2024`` sind in
    Sammlungs-Tagebuechern, Fund-Etiketten und Excel-Zeilen die uebliche
    Kompaktform fuer einen mehrtaegigen Fund-Zeitraum innerhalb eines Monats
    (Ex-Kursions-Zeitraum am Gotthard, Bergtour im Val Bedretto). Vor dem Fix
    fielen alle Formen still auf None, weil :data:`_DAY_MONTH_YEAR` nur
    Einzel-Tage akzeptierte und der Range-Bindestrich zwischen den beiden
    Tagen den ``$``-Anker-Match blockte. Spiegelt die semantische Konvention
    aus :data:`_DAY_RANGE_MONTH_YEAR` (Named-Month-Variante): der erste Tag
    liefert das ISO-Datum, der zweite Tag wird als Fund-Zeitraum-Ende
    dokumentiert aber nicht in die Datums-Rueckgabe eingerechnet.
    """
    # Kompaktform mit Punkt-Trenner
    assert parse_iso_date("13.-15.06.2024") == "2024-06-13"
    assert parse_iso_date("13. - 15.06.2024") == "2024-06-13"
    assert parse_iso_date("13-15.06.2024") == "2024-06-13"
    assert parse_iso_date("13 - 15.06.2024") == "2024-06-13"
    # DE-Wort-Trenner
    assert parse_iso_date("13. bis 15.06.2024") == "2024-06-13"
    assert parse_iso_date("13 bis 15.06.2024") == "2024-06-13"
    # EN-Wort-Trenner
    assert parse_iso_date("13 to 15.06.2024") == "2024-06-13"
    assert parse_iso_date("13 through 15.06.2024") == "2024-06-13"
    assert parse_iso_date("13 until 15.06.2024") == "2024-06-13"
    # Einstellige Tage/Monate
    assert parse_iso_date("3-5.10.2023") == "2023-10-03"
    assert parse_iso_date("3.-5.10.2023") == "2023-10-03"
    assert parse_iso_date("1-3.1.2020") == "2020-01-01"
    # Whitespace um Punkte
    assert parse_iso_date("13. bis 15. 06. 2024") == "2024-06-13"
    # En-/Em-Dash als Trenner
    assert parse_iso_date("13.–15.06.2024") == "2024-06-13"
    assert parse_iso_date("13.—15.06.2024") == "2024-06-13"
    # Case-Insensitivitaet auf dem Wort-Trenner
    assert parse_iso_date("13 BIS 15.06.2024") == "2024-06-13"
    assert parse_iso_date("13 TO 15.06.2024") == "2024-06-13"
    # Ungueltiger Start-Tag / Monat / Jahr -> None
    assert parse_iso_date("32.-33.06.2024") is None
    assert parse_iso_date("13.-15.13.2024") is None
    assert parse_iso_date("13.-15.06.1500") is None
    assert parse_iso_date("13.-15.06.3000") is None
    # Regress: Einzel-Tag ohne Range bleibt unveraendert
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    # Regress: Named-Month-Range bleibt unveraendert
    assert parse_iso_date("13.-15. Juni 2024") == "2024-06-13"
    # Regress: ISO bleibt unveraendert
    assert parse_iso_date("2024-06-13") == "2024-06-13"


def test_parse_iso_date_englische_month_first_tages_range():
    """EN Month-First-Tages-Range wird auf den Start-Tag im ersten Monat aufgeloest.

    ``Feb 3 - Feb 8, 2024`` (wiederholter Monat), ``Feb 3-8, 2024`` (Monat
    einmal), ``March 3 - April 5, 2024`` (Cross-Month) und ``Feb 3 to Feb 8,
    2024`` (Wort-Trenner) sind in EN-Auktions-Katalog-Beschreibungen,
    Foto-Captions und Boersen-Zitaten die uebliche Kompaktform fuer einen
    mehrtaegigen Fund-/Boersen-/Exkursions-Zeitraum. Vor dem Fix fielen alle
    Formen still auf None, weil :data:`_ENGLISH_MONTH_DAY_YEAR` nur einen
    Einzel-Tag akzeptierte und der Range-Trenner den ``$``-Anker-Match
    blockte, und :data:`_DAY_RANGE_MONTH_YEAR` (Day-First-Konvention) mit
    einer Zahl beginnt statt mit einem Monatsnamen. Spiegelt die semantische
    Konvention aus :data:`_DAY_RANGE_MONTH_YEAR`: der erste Tag im ersten
    (oder einzigen) Monat liefert das ISO-Datum, End-Tag/End-Monat werden
    als Range-Ende dokumentiert aber nicht in die Datums-Rueckgabe
    eingerechnet.
    """
    # Repeated month (same month both sides)
    assert parse_iso_date("Feb 3 - Feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3-Feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3 -Feb 8, 2024") == "2024-02-03"
    # Same month, single month appearance
    assert parse_iso_date("Feb 3-8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3 - 8, 2024") == "2024-02-03"
    # Cross-month range
    assert parse_iso_date("March 3 - April 5, 2024") == "2024-03-03"
    assert parse_iso_date("June 15 - July 20, 2023") == "2023-06-15"
    assert parse_iso_date("December 28 - January 5, 2024") == "2024-12-28"
    # Wort-Trenner EN (to/till/until/through/thru)
    assert parse_iso_date("Feb 3 to Feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3 to 8, 2024") == "2024-02-03"
    assert parse_iso_date("June 15 to July 20, 2023") == "2023-06-15"
    assert parse_iso_date("Feb 3 through Feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3 until 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3 till 8, 2024") == "2024-02-03"
    # Wort-Trenner DE (bis) - EN-Monatsname aber DE-Trenner (Mischform aus
    # zweisprachigen Sammlungs-Notizen)
    assert parse_iso_date("Feb 3 bis Feb 8, 2024") == "2024-02-03"
    # Ordinal-Suffixe (st|nd|rd|th)
    assert parse_iso_date("February 3rd - March 5th, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 1st - Feb 3rd, 2024") == "2024-02-01"
    assert parse_iso_date("Jan 1st - 31st, 2024") == "2024-01-01"
    # Monatsname-Abkuerzung mit trailing Punkt
    assert parse_iso_date("Feb. 3 - Feb. 8, 2024") == "2024-02-03"
    assert parse_iso_date("Jan. 1 - Feb. 5, 2024") == "2024-01-01"
    # En-/Em-Dash als Trenner
    assert parse_iso_date("Feb 3 – Feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3—Feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3–8, 2024") == "2024-02-03"
    # Ohne Komma vor dem Jahr
    assert parse_iso_date("Feb 3-8 2024") == "2024-02-03"
    assert parse_iso_date("March 3 - April 5 2024") == "2024-03-03"
    # Case-Insensitivitaet (Caps-Lock aus geerbten Etiketten, gemischte
    # Schreibung)
    assert parse_iso_date("FEB 3 - FEB 8, 2024") == "2024-02-03"
    assert parse_iso_date("feb 3 - feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("Feb 3 - MAR 5, 2024") == "2024-02-03"  # cross with mixed case
    # Kombination mit Annaeherungspraefix (via Rekursion)
    assert parse_iso_date("ca. Feb 3 - Feb 8, 2024") == "2024-02-03"
    assert parse_iso_date("circa March 3 - April 5, 2024") == "2024-03-03"
    # Klammer-Wrap via Bracket-Strip-Rekursion
    assert parse_iso_date("(Feb 3-8, 2024)") == "2024-02-03"
    assert parse_iso_date("[March 3 - April 5, 2024]") == "2024-03-03"
    # Inverted Range (Tippfehler) - Start-Tag bleibt Anker (spiegelt _MONTH_RANGE_YEAR)
    assert parse_iso_date("Feb 8-3, 2024") == "2024-02-08"
    assert parse_iso_date("Feb 8 - Feb 3, 2024") == "2024-02-08"
    assert parse_iso_date("April 5 - March 3, 2024") == "2024-04-05"
    # Ungueltiger Tag / Monat / Jahr -> None
    assert parse_iso_date("Feb 31-8, 2024") is None  # 31. Feb existiert nicht
    assert parse_iso_date("Feb 3-32, 2024") is None  # Tag 32 out of range
    assert parse_iso_date("Feb 0-8, 2024") is None  # Tag 0 out of range
    assert parse_iso_date("Feb 3 - Junk 5, 2024") is None  # invalid month2
    assert parse_iso_date("Junk 3 - Feb 5, 2024") is None  # invalid month1
    assert parse_iso_date("Junk 3-8, 2024") is None  # invalid month, single
    assert parse_iso_date("Feb 3 - Feb 8, 3999") is None  # year out of range
    assert parse_iso_date("Feb 3 - Feb 8, 1700") is None  # year out of range
    # Regress: Single-Date-Formen bleiben unveraendert
    assert parse_iso_date("Jun 13, 2024") == "2024-06-13"
    assert parse_iso_date("June 13, 2024") == "2024-06-13"
    assert parse_iso_date("March 3rd, 2020") == "2020-03-03"
    assert parse_iso_date("Feb. 3, 2024") == "2024-02-03"
    # Regress: Day-First-Range bleibt unveraendert (5-7 June 2024)
    assert parse_iso_date("5-7 June 2024") == "2024-06-05"
    assert parse_iso_date("13.-15. Juni 2024") == "2024-06-13"
    assert parse_iso_date("5. bis 7. Juni 2024") == "2024-06-05"
    # Regress: ISO / DE bleibt unveraendert
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"


def test_parse_iso_date_voll_datum_range_de():
    """Voll-Datum-Range im DE-Format wird auf das Start-Datum aufgeloest.

    Der Sammler notiert Fund-Zeitraeume ueber mehrere Tage / einen Monatswechsel
    oft als "13.06.-15.06.2024" (Kurzform mit fehlendem ersten Jahr, gleiches
    Jahr fuer beide Datums-Grenzen) oder "13.06.2024-15.07.2024" (Voll-Form
    ueber Monats-/Jahresgrenze). Vor dem Fix fielen alle Voll-Datum-Range-Formen
    still auf None, weil :data:`_DATE_FORMATS` strptime-anchored ist und der
    Range-Separator zwischen den beiden Datums-Feldern keinen Match zulaesst.

    Konvention: der Range-Start liefert das ISO-Datum, das End-Datum wird
    nicht in die Rueckgabe eingerechnet (Fund-Datum ist Einzel-Punkt, kein
    Range). Wenn das erste Datum kein Jahr traegt, wird das Jahr aus dem
    zweiten Datum uebernommen.
    """
    # Voll-Form mit Bindestrich
    assert parse_iso_date("13.06.2024-15.06.2024") == "2024-06-13"
    assert parse_iso_date("13.06.2024 - 15.06.2024") == "2024-06-13"
    assert parse_iso_date("13.06.2024-15.07.2024") == "2024-06-13"
    # Kurzform (fehlendes erstes Jahr, gleiches Jahr wie End-Datum)
    assert parse_iso_date("13.06.-15.06.2024") == "2024-06-13"
    assert parse_iso_date("13.06.-15.07.2024") == "2024-06-13"
    assert parse_iso_date("28.09.-05.10.2024") == "2024-09-28"
    # DE-Wort-Trenner
    assert parse_iso_date("13.06.2024 bis 15.07.2024") == "2024-06-13"
    assert parse_iso_date("30.01.2024 bis 04.02.2024") == "2024-01-30"
    # EN-Wort-Trenner
    assert parse_iso_date("13.06.2024 to 15.07.2024") == "2024-06-13"
    assert parse_iso_date("13.06.2024 through 15.07.2024") == "2024-06-13"
    # Slash als Trenner (Datenbank-Export-Konvention)
    assert parse_iso_date("13.06.2024/15.07.2024") == "2024-06-13"
    assert parse_iso_date("13.06.2024 / 15.07.2024") == "2024-06-13"
    # En-/Em-Dash
    assert parse_iso_date("13.06.2024–15.06.2024") == "2024-06-13"
    assert parse_iso_date("13.06.2024—15.06.2024") == "2024-06-13"
    # Einstellige Tage/Monate
    assert parse_iso_date("3.6.2024-5.7.2024") == "2024-06-03"
    assert parse_iso_date("1.1.2020-31.12.2020") == "2020-01-01"
    # Case-Insensitivitaet auf Wort-Trennern
    assert parse_iso_date("13.06.2024 BIS 15.07.2024") == "2024-06-13"
    # Ungueltige Grenzwerte -> None
    assert parse_iso_date("32.06.2024-15.06.2024") is None
    assert parse_iso_date("13.13.2024-15.06.2024") is None
    assert parse_iso_date("13.06.1500-15.06.1500") is None
    assert parse_iso_date("13.06.3000-15.06.3000") is None
    # Regress: Einzel-Datum bleibt unveraendert
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    # Regress: Numerischer Tag-Range mit gemeinsamem Monat.Jahr
    assert parse_iso_date("13.-15.06.2024") == "2024-06-13"
    # Regress: Named-Month-Range
    assert parse_iso_date("13.-15. Juni 2024") == "2024-06-13"
    # Regress: ISO
    assert parse_iso_date("2024-06-13") == "2024-06-13"


def test_parse_iso_date_iso_datum_range():
    """ISO-Datum-Range wird auf das Start-Datum aufgeloest.

    ``2024-06-13/2024-06-15`` (ISO-8601-Slash-Trenner), ``2024-06-13 - 2024-06-15``
    (Bindestrich-Trenner mit Whitespace), ``2024-06-13 bis 2024-06-15``
    (DE-Wort-Trenner), ``2024-06-13–2024-06-15`` (En-/Em-Dash) sind die
    verbreiteten Notationen fuer Datums-Ranges aus Datenbank-Exporten,
    wissenschaftlichen Publikationen, GIS-/CSV-Interchange-Formaten und
    modernen Sammler-Notizen mit ISO-Datum-Standard.

    Vor dem Fix fielen alle Formen still auf None, weil :data:`_DATE_FORMATS`
    strptime-anchored ist und der Range-Separator zwischen den beiden Datums-
    Feldern keinen Match zulaesst - silenter Funddatum-Datenverlust bei der
    Migration aus Zeitraum-Notationen mit ISO-Datum.

    Konvention identisch zu den uebrigen Range-Patterns: der Range-Start
    liefert das ISO-Datum, das End-Datum wird nicht in die Rueckgabe
    eingerechnet (Fund-Datum in der Sammlungs-DB ist Einzel-Punkt).
    """
    # ISO-Slash-Trenner (offizieller ISO-8601-Range-Separator)
    assert parse_iso_date("2024-06-13/2024-06-15") == "2024-06-13"
    assert parse_iso_date("2020-01-01/2020-12-31") == "2020-01-01"
    assert parse_iso_date("2024-06-13 / 2024-06-15") == "2024-06-13"
    # ASCII-Bindestrich mit Whitespace
    assert parse_iso_date("2024-06-13 - 2024-06-15") == "2024-06-13"
    # ASCII-Bindestrich ohne Whitespace (durch _TYPOGRAPHIC_DASH-Normalisierung
    # nachgelagert entstehende Form aus En-/Em-Dash-Eingaben)
    assert parse_iso_date("2024-06-13-2024-06-15") == "2024-06-13"
    # En-/Em-Dash ohne Whitespace
    assert parse_iso_date("2024-06-13–2024-06-15") == "2024-06-13"
    assert parse_iso_date("2024-06-13—2024-06-15") == "2024-06-13"
    # DE-Wort-Trenner
    assert parse_iso_date("2024-06-13 bis 2024-06-15") == "2024-06-13"
    assert parse_iso_date("1985-05-30 bis 1985-06-05") == "1985-05-30"
    # EN-Wort-Trenner
    assert parse_iso_date("2024-06-13 to 2024-06-15") == "2024-06-13"
    assert parse_iso_date("2024-06-13 through 2024-06-15") == "2024-06-13"
    assert parse_iso_date("2024-06-13 until 2024-06-15") == "2024-06-13"
    # Case-Insensitivitaet auf Wort-Trenner
    assert parse_iso_date("2024-06-13 BIS 2024-06-15") == "2024-06-13"
    # Einstellige Monate/Tage
    assert parse_iso_date("2024-6-1/2024-6-15") == "2024-06-01"
    # Ungueltige Start-Grenze -> None (End-Grenze wird nicht validiert, weil
    # sie nicht in die Rueckgabe eingerechnet wird - konsistent zur Semantik
    # der uebrigen Range-Patterns).
    assert parse_iso_date("2024-13-13/2024-06-15") is None
    assert parse_iso_date("2024-06-32/2024-06-15") is None
    assert parse_iso_date("1500-06-13/2024-06-15") is None
    # Regress: Einzel-ISO-Datum bleibt unveraendert
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    # Regress: Mehrjahres-Spanne (YYYY-YYYY) bleibt unveraendert
    assert parse_iso_date("2020-2024") == "2020-01-01"
    # Regress: DE-Voll-Datum-Range bleibt unveraendert
    assert parse_iso_date("13.06.2024-15.07.2024") == "2024-06-13"


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


def test_parse_iso_date_englische_of_konstruktion():
    """Englische "day of month" Ordinal-Konstruktion mit "of"-Praeposition
    ("the 4th of July 2019", "15th of June 2020"). Idiomatische EN-Form der
    Tages-vor-Monat-Reihenfolge; in geerbten Sammlungs-Notizen, Auktions-
    Katalogen und englischen Foto-Captions verbreitet."""
    # Standard-Ordinal-Formen
    assert parse_iso_date("the 4th of July 2019") == "2019-07-04"
    assert parse_iso_date("4th of July 2019") == "2019-07-04"
    assert parse_iso_date("the 15th of June 2020") == "2020-06-15"
    assert parse_iso_date("15th of June 2020") == "2020-06-15"
    assert parse_iso_date("1st of January 2020") == "2020-01-01"
    assert parse_iso_date("2nd of February 2019") == "2019-02-02"
    assert parse_iso_date("3rd of March 1985") == "1985-03-03"
    assert parse_iso_date("22nd of December 2020") == "2020-12-22"
    assert parse_iso_date("31st of May 2024") == "2024-05-31"
    # Kurzform-Monatsnamen
    assert parse_iso_date("2nd of Feb 2019") == "2019-02-02"
    assert parse_iso_date("1st of Jan 2020") == "2020-01-01"
    assert parse_iso_date("15th of Jun 2020") == "2020-06-15"
    assert parse_iso_date("22nd of Dec 2020") == "2020-12-22"
    # Kurzform mit Punkt
    assert parse_iso_date("2nd of Feb. 2019") == "2019-02-02"
    # Komma vor Jahr (Zeitungs-/Journal-Stil)
    assert parse_iso_date("the 4th of July, 2019") == "2019-07-04"
    assert parse_iso_date("15th of June, 2020") == "2020-06-15"
    # Case-Insensitivitaet (Caps, Titel-Case, Mixed)
    assert parse_iso_date("THE 4TH OF JULY 2019") == "2019-07-04"
    assert parse_iso_date("The 4th Of July 2019") == "2019-07-04"
    assert parse_iso_date("the 4TH of JULY 2019") == "2019-07-04"
    # Ohne Ordinal-Suffix (Kompakt-Notiz-Form, grammatisch lax)
    assert parse_iso_date("15 of June 2020") == "2020-06-15"
    assert parse_iso_date("4 of July 2019") == "2019-07-04"
    # Trailing Satzzeichen
    assert parse_iso_date("4th of July 2019.") == "2019-07-04"
    assert parse_iso_date("the 15th of June 2020,") == "2020-06-15"
    # Mit Annaeherungspraefix
    assert parse_iso_date("ca. 4th of July 2019") == "2019-07-04"
    assert parse_iso_date("approx. the 15th of June 2020") == "2020-06-15"
    # Klammer-Strip
    assert parse_iso_date("[4th of July 2019]") == "2019-07-04"
    assert parse_iso_date("(the 15th of June 2020)") == "2020-06-15"
    # Grenzfaelle: ungueltige Tage/Monate/Jahre -> None
    assert parse_iso_date("the 32nd of June 2020") is None  # Tag > 31
    assert parse_iso_date("the 30th of February 2020") is None  # 30. Feb existiert nicht
    assert parse_iso_date("the 31st of April 2020") is None  # 31. April existiert nicht
    assert parse_iso_date("the 4th of Foo 2019") is None  # Unbekannter Monat
    assert parse_iso_date("the 4th of July 1700") is None  # Jahr vor 1800
    assert parse_iso_date("the 4th of July 3000") is None  # Jahr nach 2999
    # Regress-Anker: bestehende Formen bleiben gueltig
    assert parse_iso_date("15th June 2020") == "2020-06-15"
    assert parse_iso_date("June 15th, 2020") == "2020-06-15"
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    # Disjunktheit: Ohne "of" faellt der Match durch auf _DAY_MONTH_YEAR /
    # _ENGLISH_MONTH_DAY_YEAR (die "of" nicht kennen)
    assert parse_iso_date("15th June 2020") == "2020-06-15"  # ohne of -> _DAY_MONTH_YEAR


def test_parse_iso_date_typografische_dash_zwischen_ziffern():
    """En-Dash (U+2013) und Em-Dash (U+2014) als Trenner INNERHALB eines
    Datums werden auf ASCII-Hyphen normalisiert. Word/Outlook/LibreOffice-
    AutoFormat, PDF-Text-Extraktion und Office-Autokorrektur-Ketten wandeln
    ASCII-Hyphen in Zahl-Kombinationen automatisch in typografische Dashes
    um (Excel-Autoformat, Word-Standard-Autoformat, LaTeX-Textrender
    ``--`` -> ``–``, PDF-Copy-Extraktion aus formatierten Vorlagen).

    Bisher fielen alle Formen still auf None, weil die strptime-Loops in
    :data:`_DATE_FORMATS` ASCII-Hyphen verlangen (``%d-%m-%Y`` matcht nur
    ``13-06-2024``, nicht ``13–06–2024``) und die uebrigen Named-Pattern-
    Regexes ohne Range-Semantik akzeptieren typografische Dashes nur in
    ihren dedizierten Range-Klassen. Aus dem typischen Sammler-Workflow
    "Fund-Datum in Word/Outlook-Notiz getippt (13-06-2024) wird Autoformat-
    konvertiert zu 13–06–2024, dann in die Sammlung kopiert" entstand
    damit silenter Funddatum-Datenverlust bei der Migration.
    """
    # En-Dash zwischen Ziffern (Word-Autoformat-typisch)
    assert parse_iso_date("13–06–2024") == "2024-06-13"
    assert parse_iso_date("2024–06–13") == "2024-06-13"
    assert parse_iso_date("06–13–2024") == "2024-06-13"  # US-Format
    # Em-Dash zwischen Ziffern
    assert parse_iso_date("13—06—2024") == "2024-06-13"
    assert parse_iso_date("2024—06—13") == "2024-06-13"
    # Gemischt En- und Em-Dash
    assert parse_iso_date("13–06—2024") == "2024-06-13"
    assert parse_iso_date("2024—06–13") == "2024-06-13"
    # Zwischen Ziffer und Monatsname (Oracle-Log-Konvention "01-JAN-2024")
    assert parse_iso_date("13–June–2024") == "2024-06-13"
    assert parse_iso_date("13–Juni–2024") == "2024-06-13"
    assert parse_iso_date("01–JAN–2024") == "2024-01-01"
    assert parse_iso_date("June–2024") == "2024-06-01"
    # Case-Insensitivitaet auf dem Monatsnamen
    assert parse_iso_date("13–JUNI–2024") == "2024-06-13"
    assert parse_iso_date("13–june–2024") == "2024-06-13"
    # Kombination mit Approx-Praefix
    assert parse_iso_date("ca. 13–06–2024") == "2024-06-13"
    # Regress-Anker: bestehende ASCII-Hyphen-Formen bleiben unveraendert
    assert parse_iso_date("13-06-2024") == "2024-06-13"
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13-Jun-2024") == "2024-06-13"
    # Regress: Whitespace-getrennte typografische Dashes bleiben Range-Trenner
    # ("2020 – 2024" ist Jahr-Range, nicht Datum) - hier wird der Dash NICHT
    # als Datums-Separator normalisiert, weil Whitespace zwischen ihm und
    # den Ziffern steht (Lookbehind/Lookahead verlangen direkte Adjazenz).
    assert parse_iso_date("2020 – 2024") == "2020-01-01"  # Range-Start-Jahr
    # Regress: Kein-Whitespace-Jahr-Range "2020–2024" wird auf "2020-2024"
    # normalisiert und matcht dann die :data:`_YEAR_RANGE`-Klasse mit ASCII-
    # Hyphen - identisches Ergebnis via unveraendertem Pfad.
    assert parse_iso_date("2020–2024") == "2020-01-01"
    # Regress: Monatsnamen-Range ("Juni–Juli 2024") bleibt intakt, weil
    # Lookbehind/Lookahead fuer Buchstaben-zu-Buchstaben-Dashes nicht triggern.
    assert parse_iso_date("Juni–Juli 2024") == "2024-06-01"
    # Ungueltige Fall: Jahr < 1800 bleibt None
    assert parse_iso_date("13–06–1700") is None


def test_parse_iso_date_italienische_monatsnamen():
    """Italienische Monatsnamen (Ticino / italienische Schweiz sowie geerbte
    Sammler-Notizen aus italienischen Alpen-/Dolomiten-Fundorten) - alle ASCII,
    keine Akzente in italienischen Monatsnamen, daher keine Regex-Aenderung."""
    # Voll ausgeschriebene Formen (alle 12 Monate, spiegelt DE/EN-Testblock)
    assert parse_iso_date("gennaio 2024") == "2024-01-01"
    assert parse_iso_date("febbraio 2024") == "2024-02-01"
    assert parse_iso_date("marzo 2024") == "2024-03-01"
    assert parse_iso_date("aprile 2024") == "2024-04-01"
    assert parse_iso_date("maggio 2024") == "2024-05-01"
    assert parse_iso_date("giugno 2024") == "2024-06-01"
    assert parse_iso_date("luglio 2024") == "2024-07-01"
    assert parse_iso_date("agosto 2024") == "2024-08-01"
    assert parse_iso_date("settembre 2024") == "2024-09-01"
    assert parse_iso_date("ottobre 2024") == "2024-10-01"
    assert parse_iso_date("novembre 2024") == "2024-11-01"
    assert parse_iso_date("dicembre 2024") == "2024-12-01"
    # Tag + Monat + Jahr (typische Etiketten-Notation aus Ticino-Fundstellen)
    assert parse_iso_date("13 gennaio 2024") == "2024-01-13"
    assert parse_iso_date("13. gennaio 2024") == "2024-01-13"
    assert parse_iso_date("28 febbraio 2024") == "2024-02-28"
    assert parse_iso_date("3 marzo 2020") == "2020-03-03"
    assert parse_iso_date("13 giugno 2024") == "2024-06-13"
    assert parse_iso_date("31 dicembre 1999") == "1999-12-31"
    # Separator-Varianten (Punkt/Slash/Bindestrich, spiegelt DE/EN-Konventionen)
    assert parse_iso_date("13.giugno.2024") == "2024-06-13"
    assert parse_iso_date("13/giugno/2024") == "2024-06-13"
    assert parse_iso_date("13-giugno-2024") == "2024-06-13"
    # IT-Kurzformen (gen/mag/giu/lug/ago/sett/ott/dic), spiegelt DE/EN-Kurzformen.
    # gen/mag/giu/lug/ago/sett/ott/dic sind IT-spezifisch, spiegeln semantisch
    # die DE/EN-Alternativen auf dieselben Monatswerte.
    assert parse_iso_date("gen 2024") == "2024-01-01"
    assert parse_iso_date("mag 2024") == "2024-05-01"
    assert parse_iso_date("giu 2024") == "2024-06-01"
    assert parse_iso_date("lug 2024") == "2024-07-01"
    assert parse_iso_date("ago 2024") == "2024-08-01"
    assert parse_iso_date("sett 2024") == "2024-09-01"
    assert parse_iso_date("ott 2024") == "2024-10-01"
    assert parse_iso_date("dic 2024") == "2024-12-01"
    # Kurzform + Tag + Jahr
    assert parse_iso_date("13 giu 2024") == "2024-06-13"
    assert parse_iso_date("13 dic 1999") == "1999-12-13"
    # Year-first Notation ("2024 gennaio", "2024/gennaio")
    assert parse_iso_date("2024 gennaio") == "2024-01-01"
    assert parse_iso_date("2024/gennaio") == "2024-01-01"
    assert parse_iso_date("2024-giugno") == "2024-06-01"
    # Case-Insensitivitaet (Caps-Lock-Notizen aus geerbten Sammler-Etiketten)
    assert parse_iso_date("GENNAIO 2024") == "2024-01-01"
    assert parse_iso_date("Giugno 2024") == "2024-06-01"
    assert parse_iso_date("13 GIUGNO 2024") == "2024-06-13"
    # Kombination mit Approx-Praefix (rekursiv via bestehende Modifikatoren)
    assert parse_iso_date("ca. giugno 2024") == "2024-06-01"
    assert parse_iso_date("circa 13 giugno 2024") == "2024-06-13"
    # Ungueltige Tag-Werte in IT-Notation (spiegelt DE/EN-Konvention)
    assert parse_iso_date("30 febbraio 2024") is None
    assert parse_iso_date("31 aprile 2024") is None
    # Jahr ausserhalb [1800, 2999]
    assert parse_iso_date("gennaio 1700") is None
    assert parse_iso_date("13 giugno 3000") is None
    # Regression: bestehende DE/EN-Formen bleiben unveraendert
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("June 13, 2024") == "2024-06-13"
    assert parse_iso_date("Jun 13, 2024") == "2024-06-13"


def test_parse_iso_date_franzoesische_monatsnamen():
    """Franzoesische Monatsnamen (Suisse romande - Wallis/Waadt/Genf/Neuenburg/
    Freiburg sowie geerbte Sammler-Notizen aus franzoesisch-sprachigen Alpen-
    Fundorten). FR-Monatsnamen enthalten Diakritika (février/août/décembre),
    die :func:`_normalize_month_name` via NFKD-Dekomposition auf die ASCII-
    Aequivalente strippt; die Regex-Character-Klassen wurden auf Latin-1-Buchstaben
    erweitert, sodass sowohl akzent- als auch ASCII-Schreibweise transparent
    matchen."""
    # Voll ausgeschriebene Formen (alle 12 Monate, spiegelt DE/EN/IT-Testblock).
    # Akzent-freie ASCII-Notation aus DB-Feldern mit nur-ASCII-Konvention.
    assert parse_iso_date("janvier 2024") == "2024-01-01"
    assert parse_iso_date("fevrier 2024") == "2024-02-01"
    assert parse_iso_date("mars 2024") == "2024-03-01"
    assert parse_iso_date("avril 2024") == "2024-04-01"
    assert parse_iso_date("mai 2024") == "2024-05-01"
    assert parse_iso_date("juin 2024") == "2024-06-01"
    assert parse_iso_date("juillet 2024") == "2024-07-01"
    assert parse_iso_date("aout 2024") == "2024-08-01"
    assert parse_iso_date("septembre 2024") == "2024-09-01"
    assert parse_iso_date("octobre 2024") == "2024-10-01"
    assert parse_iso_date("novembre 2024") == "2024-11-01"
    assert parse_iso_date("decembre 2024") == "2024-12-01"
    # Standard-FR-Schreibweise mit Diakritika (février/août/décembre) - via
    # NFKD-Dekomposition in _normalize_month_name auf fevrier/aout/decembre
    # normalisiert.
    assert parse_iso_date("février 2024") == "2024-02-01"
    assert parse_iso_date("août 2024") == "2024-08-01"
    assert parse_iso_date("décembre 2024") == "2024-12-01"
    # Tag + Monat + Jahr (typische FR-Etiketten-Notation aus Wallis/Chamonix)
    assert parse_iso_date("13 janvier 2024") == "2024-01-13"
    assert parse_iso_date("13. fevrier 2024") == "2024-02-13"
    assert parse_iso_date("13 février 2024") == "2024-02-13"
    assert parse_iso_date("13 mars 2024") == "2024-03-13"
    assert parse_iso_date("13 août 2024") == "2024-08-13"
    assert parse_iso_date("31 décembre 1999") == "1999-12-31"
    # Separator-Varianten (Punkt/Slash/Bindestrich, spiegelt DE/EN/IT-Konventionen)
    assert parse_iso_date("13.juin.2024") == "2024-06-13"
    assert parse_iso_date("13/juin/2024") == "2024-06-13"
    assert parse_iso_date("13-juin-2024") == "2024-06-13"
    # FR-Kurzformen (janv/fev/fevr/avr/juil/juill), spiegelt DE/EN/IT-Kurzformen.
    assert parse_iso_date("janv 2024") == "2024-01-01"
    assert parse_iso_date("fev 2024") == "2024-02-01"
    assert parse_iso_date("fevr 2024") == "2024-02-01"
    assert parse_iso_date("févr 2024") == "2024-02-01"
    assert parse_iso_date("avr 2024") == "2024-04-01"
    assert parse_iso_date("juil 2024") == "2024-07-01"
    assert parse_iso_date("juill 2024") == "2024-07-01"
    # Kurzform + Tag + Jahr
    assert parse_iso_date("13 janv 2024") == "2024-01-13"
    assert parse_iso_date("13 avr 2024") == "2024-04-13"
    # Year-first Notation
    assert parse_iso_date("2024 janvier") == "2024-01-01"
    assert parse_iso_date("2024/juin") == "2024-06-01"
    assert parse_iso_date("2024-décembre") == "2024-12-01"
    # Case-Insensitivitaet (Caps-Lock-Notizen aus geerbten Sammler-Etiketten)
    assert parse_iso_date("JANVIER 2024") == "2024-01-01"
    assert parse_iso_date("Juin 2024") == "2024-06-01"
    assert parse_iso_date("13 JUIN 2024") == "2024-06-13"
    assert parse_iso_date("FÉVRIER 2024") == "2024-02-01"
    # Kombination mit Approx-Praefix (rekursiv via bestehende Modifikatoren)
    assert parse_iso_date("ca. juin 2024") == "2024-06-01"
    assert parse_iso_date("circa 13 juin 2024") == "2024-06-13"
    # Ungueltige Tag-Werte in FR-Notation (spiegelt DE/EN/IT-Konvention)
    assert parse_iso_date("30 fevrier 2024") is None
    assert parse_iso_date("31 avril 2024") is None
    # Jahr ausserhalb [1800, 2999]
    assert parse_iso_date("janvier 1700") is None
    assert parse_iso_date("13 juin 3000") is None
    # Regression: bestehende DE/EN/IT-Formen bleiben unveraendert
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    assert parse_iso_date("June 13, 2024") == "2024-06-13"
    assert parse_iso_date("Jun 13, 2024") == "2024-06-13"
    assert parse_iso_date("13 giugno 2024") == "2024-06-13"
    assert parse_iso_date("13.VI.2024") == "2024-06-13"
    assert parse_iso_date("März 2024") == "2024-03-01"


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


def test_parse_iso_date_iso_datetime_compact_basic():
    """ISO 8601 Basic-Form ohne Trenner: ``20240613T143200`` / ``20240613T1432``.

    Standard-Serialisierungs-Form fuer datei-basierte Zeitstempel (Backup-/
    Log-Rotations-Skripte schreiben typisch ``stone_20240613T143200.sqlite3``,
    ``export_20240613T143200.tar.gz``), Git-Branch-/Tag-Namen (``release/
    20240613T143200``), RFC-3339-nahe Log-Formate und manche EXIF-DateTime-
    Original-Feldwerte in JPEG-/RAW-Kameras. Bisher fielen alle basic-Form-
    Datetime-Notationen still auf None, obwohl das Datum vor dem T-Separator
    eindeutig kompakt-lesbar war (``20240613`` -> 2024-06-13 via
    _DATE_FORMATS-``%Y%m%d``): der T-Time-Suffix in der kompakten Form
    ``T143200`` blockierte das nachfolgende ``%Y%m%d``-Matching und der
    Trailing-Time-Strip verlangte in der ersten Alternante zwingend Colons
    im Zeit-Anteil (``\\d{1,2}:\\d{2}``). Die zweite Alternante
    ``(?<=\\d)[Tt]\\d{4}(?:\\d{2})?(?:[.,]\\d+)?`` deckt die kompakte
    Time-Form ab; Lookbehind ``(?<=\\d)`` schuetzt vor Katalog-/Namens-
    Kontext (``Bezirk T2024``, ``Text T2024``), wo das T semantisch ein
    Namens-Suffix ist.
    """
    # HHMMSS-Vollform (Sekunden-genau) - die kanonische ISO 8601 basic-Form.
    assert parse_iso_date("20240613T143200") == "2024-06-13"
    # HHMM-Kurzform (Minuten-genau) - in kompakten Log-Stempeln und Datei-
    # Rotations-Skripten die minimalste zeitliche Rasterung.
    assert parse_iso_date("20240613T1432") == "2024-06-13"
    # Zulu-Suffix ``Z``: UTC ohne Offset, spiegelt die Colon-Form-Konvention
    # (``2024-06-13T14:32:00Z``) auf die basic-Form.
    assert parse_iso_date("20240613T143200Z") == "2024-06-13"
    # Numerischer Offset (``+0200`` / ``-0500``): spiegelt die Colon-Form.
    assert parse_iso_date("20240613T143200+0200") == "2024-06-13"
    assert parse_iso_date("20240613T143200-0500") == "2024-06-13"
    # Sekundenbruchteil mit Punkt- und Komma-Dezimal (ISO 8601 laesst beide
    # zu, empfiehlt Komma; Systeme in EU-Locales schreiben oft Komma).
    assert parse_iso_date("20240613T143200.123") == "2024-06-13"
    assert parse_iso_date("20240613T143200,5") == "2024-06-13"
    # Benannter TZ-Suffix (``UTC``/``CET``/``MEZ``): spiegelt die Colon-Form-
    # Konvention der Whitelist-Suffixe.
    assert parse_iso_date("20240613T143200 UTC") == "2024-06-13"
    # Case-insensitive ``T`` (kleines ``t``): manche Log-Formate schreiben
    # ``t`` als Trenner (RFC 3339 laesst beide zu).
    assert parse_iso_date("20240613t143200") == "2024-06-13"
    # Lookbehind-Schutz: ``T`` nach Nicht-Ziffer wird NICHT als Zeit-Trenner
    # interpretiert - schuetzt vor falsch-positiven Strips in Katalog-/
    # Namens-Kontext.
    assert parse_iso_date("Bezirk T143200") is None
    assert parse_iso_date("2024 T2024") is None
    # Ambivalente Ziffern-Zahl (1/2/3/5 Ziffern nach ``T``) - nur 4 und 6
    # sind spec-konforme basic time-Formen.
    assert parse_iso_date("20240613T1") is None
    assert parse_iso_date("20240613T12") is None
    assert parse_iso_date("20240613T123") is None
    # Regression-Anker: die Colon-Form bleibt unveraendert.
    assert parse_iso_date("2024-06-13T14:32:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:32:00") == "2024-06-13"


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


def test_parse_iso_date_utc_gmt_mit_numerischem_offset():
    """UTC/GMT/UT-Zeitzone mit angehaengtem numerischen Offset (``UTC+2``,
    ``GMT-05:30``, ``UT+01:00``) wird sowohl in der Date-Only- als auch in
    der Date+Time-Form vollstaendig abgestrippt, sodass der reine Datumsteil
    in der Parser-Kaskade greift.

    Bisher fielen alle Kombinationen ``<datum> [uhrzeit] (UTC|GMT|UT)[+-]N[:MM]``
    still auf None, weil weder :data:`_TRAILING_TIME` noch
    :data:`_TRAILING_TZ_STANDALONE` den numerischen Offset-Suffix nach dem
    Named-TZ akzeptierten: die :data:`_TRAILING_TIME`-Regex kannte nur den
    reinen numerischen Offset ``+0200``/``+02:00`` (ohne vorangehendes
    ``UTC``/``GMT``) oder die reine Named-TZ-Form (ohne Offset-Ziffern
    dahinter); die :data:`_TRAILING_TZ_STANDALONE`-Whitelist listete UTC/
    GMT/UT als reine Marker ohne Offset-Alternante. Die kombinierte Form
    (Named-TZ als Anker + Offset als Delta zur Zulu-Zeit) ist aber die
    natuerliche Notation fuer Cross-Locale-Kontext in EXIF-Foto-Metadaten
    aus GPS-Kameras (Datum-Feld ohne Zeit-Feld, TZ-Delta als Kontext-Marker
    fuer die Erstellungs-Lokalisierung), in Log-Zeilen internationaler
    Backup-Rotations-Skripte (Datum-Rotation ohne feste Uhrzeit-Konvention,
    UTC-Offset als Doku fuer den Host-TZ-Kontext) und in Sammler-Notizen
    aus Foto-/Fund-Reise-Berichten mit non-DACH-Provenienz. Silenter
    Funddatum-Datenverlust bei der Migration; besonders gefaehrlich, weil
    die reine UTC-/GMT-Form ohne Offset schon lange gestrippt wurde und
    der User keinen Grund hatte anzunehmen, dass die Variante mit Offset
    anders behandelt wird.

    Fix erweitert beide Regex-Zweige: die _TRAILING_TIME-TZ-Suffix-Klausel
    bekommt eine spezifische ``\\s+(?:UTC|GMT|UT)(?:[+-]\\d{1,2}(?::?\\d{2})?)?``-
    Alternante vor dem generischen ``\\s+[A-Z]{2,5}``-Zweig; die
    _TRAILING_TZ_STANDALONE-Whitelist teilt UTC/GMT/UT von den uebrigen
    Named-TZs ab und ergaenzt an dieser Position die identische Offset-
    Alternante. Reihenfolge spezifisch-vor-generisch ist notwendig, weil
    beide Klassen auf ``UTC``/``GMT``/``UT`` matchen und die generische
    Form die Offset-Ziffern sonst uebriglassen wuerde (``GMT`` matcht via
    generischer Alternante, ``+2`` bleibt zurueck, ``\\s*$`` scheitert -
    ganzer Strip scheitert). Optionaler Minuten-Anteil ``:?\\d{2}`` deckt
    die Half-Hour-/Quarter-Hour-Zeitzonen ab (Indien UTC+5:30, Neufundland
    UTC-3:30, Nepal UTC+5:45), die in Sammler-Notizen aus internationaler
    Reise-/Sammlungs-Provenienz vorkommen.
    """
    # Date-Only + UTC/GMT/UT mit einstelligem Offset
    assert parse_iso_date("2024-06-13 UTC+2") == "2024-06-13"
    assert parse_iso_date("2024-06-13 UTC-5") == "2024-06-13"
    assert parse_iso_date("2024-06-13 GMT+2") == "2024-06-13"
    assert parse_iso_date("2024-06-13 GMT-5") == "2024-06-13"
    assert parse_iso_date("2024-06-13 UT+1") == "2024-06-13"
    # Zweistelliger Stunden-Offset
    assert parse_iso_date("2024-06-13 UTC+02") == "2024-06-13"
    assert parse_iso_date("2024-06-13 GMT-05") == "2024-06-13"
    # Half-Hour-/Quarter-Hour-Zeitzonen (Indien +5:30, Neufundland -3:30,
    # Nepal +5:45) - Half-Hour-Offset mit Colon-Trenner
    assert parse_iso_date("2024-06-13 UTC+05:30") == "2024-06-13"
    assert parse_iso_date("2024-06-13 UTC-05:30") == "2024-06-13"
    assert parse_iso_date("2024-06-13 GMT+03:30") == "2024-06-13"
    assert parse_iso_date("2024-06-13 UTC+05:45") == "2024-06-13"
    # Half-Hour-Offset ohne Colon-Trenner (kompakte ISO 8601 basic profile)
    assert parse_iso_date("2024-06-13 UTC+0530") == "2024-06-13"
    assert parse_iso_date("2024-06-13 GMT-0330") == "2024-06-13"
    # Date+Time + UTC/GMT/UT + Offset (EXIF-Datetime aus GPS-Kameras)
    assert parse_iso_date("2024-06-13 14:30:00 GMT+2") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:30:00 UTC-5") == "2024-06-13"
    assert parse_iso_date("2024-06-13T14:30 GMT+02:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13T14:30:00 UTC-05:30") == "2024-06-13"
    # DE-Format + Offset (Sammler-Etikett mit non-DACH-Reise-TZ-Kontext)
    assert parse_iso_date("13.06.2024 GMT+2") == "2024-06-13"
    assert parse_iso_date("13.06.2024 UTC-5") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024 GMT+02:00") == "2024-06-13"
    # Monatsname + Jahr + Offset (grobes Log-Rotations-Datum)
    assert parse_iso_date("Juni 2024 GMT+1") == "2024-06-01"
    assert parse_iso_date("June 2024 UTC-5") == "2024-06-01"
    # Jahr allein + Offset (Jahres-Rotation mit Host-TZ-Doku)
    assert parse_iso_date("2024 UTC+2") == "2024-01-01"
    assert parse_iso_date("1985 GMT-5") == "1985-01-01"
    # Kein Regress: reines UTC/GMT ohne Offset weiterhin gestrippt
    assert parse_iso_date("2024-06-13 UTC") == "2024-06-13"
    assert parse_iso_date("2024-06-13 GMT") == "2024-06-13"
    assert parse_iso_date("2024-06-13 UT") == "2024-06-13"
    # Kein Regress: reiner numerischer Offset (ohne UTC/GMT-Wort) an Time-Suffix
    assert parse_iso_date("2024-06-13T14:30+02:00") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:30 +0200") == "2024-06-13"
    # Kein Regress: andere Named-TZs (CET/EST/MEZ) matchen weiterhin - der
    # generische Named-TZ-Zweig steht nach der spezifischen UTC/GMT/UT-Klasse.
    assert parse_iso_date("2024-06-13 CET") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:30 EST") == "2024-06-13"
    # Kein Regress: CET+2 (nonsense, aber semantisch harmlos) - CET wird via
    # generischem ``\\s+[A-Z]{2,5}``-Zweig gestrippt, das ``+2`` blockt danach
    # den ``\\s*$``-Anker; ganzer Strip scheitert, das Datum vor dem CET-Suffix
    # wird nicht mehr erkannt. Bewusster Trade-off: die spezifische Offset-
    # Alternante ist auf UTC/GMT/UT beschraenkt, weil nur diese Marker
    # semantisch Delta-Notation zur Zulu-Zeit tragen - CET+2 waere ein
    # doppelt-modifizierter Marker ohne Praezedenz in Sammler-Notation.
    assert parse_iso_date("2024-06-13 CET+2") is None
    # Kein Regress: positiver Offset ohne Named-TZ-Anker matcht weiterhin
    # nicht als reines Suffix (der numerische Offset in _TRAILING_TIME ist
    # an einen vorangehenden Zeit-Block gebunden). "2024-06-13 +2" bleibt
    # None - der Whitespace + Ziffer + Vorzeichen ist ohne Zeit-Anker
    # semantisch mehrdeutig (koennte Fortsetzungs-Wert oder Katalog-Delta
    # sein).
    assert parse_iso_date("2024-06-13 +2") is None
    assert parse_iso_date("2024-06-13 +02:00") is None
    # Kein Regress: Datum ausserhalb Jahr-Range mit TZ+Offset bleibt None
    assert parse_iso_date("1700-06-15 GMT+2") is None
    # Kein Regress: Kleinbuchstaben-TZ-Suffix matcht nicht (Konvention
    # der Grossbuchstaben-Whitelist), auch mit Offset nicht
    assert parse_iso_date("2024-06-13 utc+2") is None
    assert parse_iso_date("2024-06-13 gmt-5") is None


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


def test_parse_iso_date_annaeherungs_praefix_ungefaehr():
    """``ungefähr``/``ungefaehr`` als Praefix - Symmetrie zum Trailing-Suffix.

    Vor dem Fix war die Wortmarke ``ungefähr``/``ungefaehr`` nur als
    Trailing-Suffix (``1985 ungefähr``) erkannt, waehrend die identische
    Praefix-Form (``ungefähr 1985``) still auf None fiel. Das war eine
    Asymmetrie zwischen ``_APPROX_PREFIX`` und ``_TRAILING_APPROX_SUFFIX``,
    die die haeufigere DE-Satz-Reihenfolge (Praezisions-Marker vor Datum:
    ``ungefähr <Datum> in den Alpen gefunden``) benachteiligt hat.
    Semantisch identisch zu ``ca.``/``etwa``/``schaetzungsweise`` und den
    uebrigen Praezisions-Praefixen.
    """
    # DE-Umlaut-Form (Standard-Schreibweise auf sauber gesetzten Etiketten)
    assert parse_iso_date("ungefähr 1985") == "1985-01-01"
    assert parse_iso_date("ungefähr 2020") == "2020-01-01"
    # ae-Transliteration (Sammlungs-Notizen ohne Umlaut-Fähigkeit -
    # Legacy-CSV-Exporte, ASCII-only-Tools, gemischte Encodings)
    assert parse_iso_date("ungefaehr 1985") == "1985-01-01"
    assert parse_iso_date("ungefaehr 2020") == "2020-01-01"
    # Case-insensitive (Museums-Etiketten in Grossbuchstaben/Mischform)
    assert parse_iso_date("UNGEFÄHR 1985") == "1985-01-01"
    assert parse_iso_date("Ungefähr 1985") == "1985-01-01"
    assert parse_iso_date("UNGEFAEHR 1985") == "1985-01-01"
    # Praefix + vollstaendiges Datum (Rekursion greift durch)
    assert parse_iso_date("ungefähr 13.06.2024") == "2024-06-13"
    assert parse_iso_date("ungefähr Juni 2024") == "2024-06-01"
    assert parse_iso_date("ungefaehr 2024-06-13") == "2024-06-13"
    # Praefix + Dekaden/Saison/Jahrhundert (rekursive Aufloesung)
    assert parse_iso_date("ungefähr 1980er") == "1980-01-01"
    assert parse_iso_date("ungefähr Sommer 1985") == "1985-06-01"
    # Verkettet mit anderen Praefixen (Rekursion loest sie sequentiell auf)
    assert parse_iso_date("ungefähr ca. 1985") == "1985-01-01"
    assert parse_iso_date("ca. ungefähr 1985") == "1985-01-01"
    # Ohne Datum-Rest oder mit ungueltigem Rest → None
    assert parse_iso_date("ungefähr") is None
    assert parse_iso_date("ungefaehr") is None
    assert parse_iso_date("ungefähr abc") is None
    assert parse_iso_date("ungefähr 1700") is None  # ausserhalb 1800-2999
    # Kein False-Positive fuer aehnlich beginnende Woerter (``ungeeignet``,
    # ``ungenau``, ``unger[ae]cht``) - der Praefix muss durch \s+ vom Rest
    # getrennt sein und exakt eines der Alternate-Woerter matchen.
    assert parse_iso_date("ungeeignet 1985") is None
    assert parse_iso_date("ungenau 1985") is None
    # Trailing-Form bleibt unveraendert erkannt (kein Regress)
    assert parse_iso_date("1985 ungefähr") == "1985-01-01"
    assert parse_iso_date("2024-06-13 ungefaehr") == "2024-06-13"
    # Bestehende Praefixe unveraendert (kein Regress)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("circa 2020") == "2020-01-01"
    assert parse_iso_date("etwa 1985") == "1985-01-01"
    assert parse_iso_date("vermutlich 1985") == "1985-01-01"
    assert parse_iso_date("schaetzungsweise 1985") == "1985-01-01"


def test_parse_iso_date_annaeherungs_praefix_geschaetzt():
    """``geschätzt``/``geschaetzt`` als Praefix (Past-Partizip-Form).

    Erweitert :data:`_APPROX_PREFIX` um die DE-Past-Partizip-Form der
    Schaetzung, die semantisch identisch zum bereits gelisteten adverbialen
    ``sch[äa]tzungsweise`` ist, aber in Sammler-Notizen oft die verkuerzte
    Alternative bildet ("Erwerb geschätzt 1985", "Fundzeitpunkt geschaetzt
    Juni 2024"). Vor dem Fix fielen alle Praefix-Formen mit dieser Marke
    still auf None, obwohl die identische EN-Past-Partizip-Form
    ``estimated`` (spiegelt exakt dieselbe Grammatik) bereits erkannt wurde
    - eine DE/EN-Asymmetrie im Past-Partizip-Register. Umlaut- und ae-
    Transliterations-Variante parallel wie bei ``ungef[äa]hr`` /
    ``sch[äa]tzungsweise``.
    """
    # DE-Umlaut-Form (Standard-Schreibweise auf sauber gesetzten Etiketten)
    assert parse_iso_date("geschätzt 1985") == "1985-01-01"
    assert parse_iso_date("geschätzt 2020") == "2020-01-01"
    # ae-Transliteration (Legacy-CSV-Exporte, ASCII-only-Tools)
    assert parse_iso_date("geschaetzt 1985") == "1985-01-01"
    assert parse_iso_date("geschaetzt 2020") == "2020-01-01"
    # Case-insensitive (Museums-Etiketten in Grossbuchstaben/Mischform)
    assert parse_iso_date("GESCHÄTZT 1985") == "1985-01-01"
    assert parse_iso_date("Geschätzt 1985") == "1985-01-01"
    assert parse_iso_date("GESCHAETZT 1985") == "1985-01-01"
    # Praefix + vollstaendiges Datum (Rekursion greift durch)
    assert parse_iso_date("geschätzt 13.06.2024") == "2024-06-13"
    assert parse_iso_date("geschätzt Juni 2024") == "2024-06-01"
    assert parse_iso_date("geschaetzt 2024-06-13") == "2024-06-13"
    # Praefix + Dekaden/Saison/Jahrhundert (rekursive Aufloesung)
    assert parse_iso_date("geschätzt 1980er") == "1980-01-01"
    assert parse_iso_date("geschätzt Sommer 1985") == "1985-06-01"
    # Verkettet mit anderen Praefixen (Rekursion loest sie sequentiell auf)
    assert parse_iso_date("geschätzt ca. 1985") == "1985-01-01"
    assert parse_iso_date("ca. geschätzt 1985") == "1985-01-01"
    # Ohne Datum-Rest oder mit ungueltigem Rest → None
    assert parse_iso_date("geschätzt") is None
    assert parse_iso_date("geschaetzt") is None
    assert parse_iso_date("geschätzt abc") is None
    assert parse_iso_date("geschätzt 1700") is None  # ausserhalb 1800-2999
    # Kein False-Positive fuer aehnlich beginnende Woerter - der Praefix muss
    # durch \s+ vom Rest getrennt sein und exakt eines der Alternate-Woerter
    # matchen.
    assert parse_iso_date("geschätzterweise 1985") is None
    assert parse_iso_date("geschätzten 1985") is None
    # Bestehende Praefixe unveraendert (kein Regress)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("circa 2020") == "2020-01-01"
    assert parse_iso_date("schaetzungsweise 1985") == "1985-01-01"
    assert parse_iso_date("ungefähr 1985") == "1985-01-01"
    assert parse_iso_date("estimated 1985") == "1985-01-01"


def test_parse_iso_date_annaeherungs_suffix_geschaetzt():
    """``geschätzt``/``geschaetzt`` als Trailing-Suffix (Past-Partizip-Form).

    Spiegelt :func:`test_parse_iso_date_annaeherungs_praefix_geschaetzt` auf
    die Suffix-Achse: ``_TRAILING_APPROX_SUFFIX`` bekommt denselben Past-
    Partizip-Eintrag als DE-Standardform der Schaetzung. In Sammler-Etiketten
    tritt die Trailing-Form ("1985 geschätzt", "Fund Juni 2024 geschaetzt")
    ebenso oft auf wie die Praefix-Form; die DE/EN-Symmetrie zu ``estimated``
    (bereits gelistet) wird damit auf beiden Achsen konsistent.
    """
    # DE-Umlaut- und ae-Transliteration
    assert parse_iso_date("1985 geschätzt") == "1985-01-01"
    assert parse_iso_date("1985 geschaetzt") == "1985-01-01"
    assert parse_iso_date("2020 geschätzt") == "2020-01-01"
    # Case-insensitive
    assert parse_iso_date("1985 GESCHÄTZT") == "1985-01-01"
    assert parse_iso_date("1985 Geschätzt") == "1985-01-01"
    assert parse_iso_date("1985 GESCHAETZT") == "1985-01-01"
    # Kombiniert mit vollstaendigem Datum
    assert parse_iso_date("13.06.2024 geschätzt") == "2024-06-13"
    assert parse_iso_date("2024-06-13 geschaetzt") == "2024-06-13"
    assert parse_iso_date("Juni 2020 geschätzt") == "2020-06-01"
    assert parse_iso_date("Juni 2020 geschaetzt") == "2020-06-01"
    # Kombiniert mit Saison + Jahr
    assert parse_iso_date("Sommer 1985 geschätzt") == "1985-06-01"
    assert parse_iso_date("Winter 2023 geschaetzt") == "2023-12-01"
    # Mehrschichtige Rekursion (sinnfrei, aber unschaedlich)
    assert parse_iso_date("ca. 1985 geschätzt") == "1985-01-01"
    assert parse_iso_date("geschätzt 1985 geschätzt") == "1985-01-01"
    # Reiner Marker ohne Datum bleibt None
    assert parse_iso_date("geschätzt") is None
    assert parse_iso_date("geschaetzt") is None
    # Suffix ohne Whitespace davor wird NICHT gestrippt (spiegelt die
    # \s+-Grenze aller Suffix-Eintraege)
    assert parse_iso_date("1985geschätzt") is None
    # Bestehende Suffixe unveraendert (kein Regress)
    assert parse_iso_date("1985 ca.") == "1985-01-01"
    assert parse_iso_date("1985 schaetzungsweise") == "1985-01-01"
    assert parse_iso_date("1985 ungefähr") == "1985-01-01"
    assert parse_iso_date("1985 estimated") == "1985-01-01"


def test_parse_iso_date_folgende_jahre_suffix():
    """Trailing "und folgende Jahre"-Suffix (DE-Bibliografie-/Zitat-Standard).

    ``1985 ff.`` = "1985 und zwei oder mehr folgende Jahre"; ``1985 f.`` =
    "1985 und ein folgendes Jahr". Herkunft aus der klassischen Zitier-Praxis
    (Duden K104, DIN 1505, Bibliografie-Guides der Universitaets-Bibliotheken)
    und in Museums-Etiketten fuer Erwerbs-/Bearbeitungs-Zeitraeume ohne festes
    End-Datum ("Sammlung Meier, 1985ff." = ab 1985 laufend erweitert).
    Konvention identisch zu :data:`_YEAR_RANGE` / :data:`_YEAR_RANGE_WORD` /
    :data:`_YEAR_RANGE_BETWEEN` - Startjahr als ISO-Datum, "und folgende"
    bleibt semantische Wert-Anmerkung im Freitext.
    """
    # ff.-Form mit Whitespace + Punkt (Duden/DIN 5008-Standard)
    assert parse_iso_date("1985 ff.") == "1985-01-01"
    assert parse_iso_date("2020 ff.") == "2020-01-01"
    # ff-Form ohne Punkt (Kurzsatz-Notizen)
    assert parse_iso_date("1985 ff") == "1985-01-01"
    # Kompakt-Form ohne Whitespace (Karteikarten-/Tabellen-Cell-Notation)
    assert parse_iso_date("1985ff") == "1985-01-01"
    assert parse_iso_date("1985ff.") == "1985-01-01"
    # f.-Form: "und ein folgendes Jahr" - semantisch aequivalent fuer die
    # ISO-Auswertung (Start-Jahr)
    assert parse_iso_date("1985 f.") == "1985-01-01"
    assert parse_iso_date("1985 f") == "1985-01-01"
    assert parse_iso_date("1985f.") == "1985-01-01"
    assert parse_iso_date("1985f") == "1985-01-01"
    # Case-insensitive (Museums-Etiketten in Grossbuchstaben/Mischform)
    assert parse_iso_date("1985 FF.") == "1985-01-01"
    assert parse_iso_date("1985FF") == "1985-01-01"
    assert parse_iso_date("1985 F.") == "1985-01-01"
    # Kombiniert mit vollstaendigem Datum (Monat/Tag bleibt erhalten -
    # "Sammlung Meier ab Juni 2024 laufend erweitert")
    assert parse_iso_date("Juni 2024 ff.") == "2024-06-01"
    assert parse_iso_date("13.06.2024 ff.") == "2024-06-13"
    assert parse_iso_date("2024-06-13 ff.") == "2024-06-13"
    assert parse_iso_date("2024-06 ff.") == "2024-06-01"
    # Kombiniert mit Saison/Dekade/Jahrhundert (rekursive Aufloesung nach Strip)
    assert parse_iso_date("Sommer 1985 ff.") == "1985-06-01"
    assert parse_iso_date("1980er ff.") == "1980-01-01"
    # Verkettet mit anderen Suffix-/Praefix-Formen (Rekursion loest sie
    # sequentiell auf)
    assert parse_iso_date("ca. 1985 ff.") == "1985-01-01"
    assert parse_iso_date("1985 ff. ca.") == "1985-01-01"
    assert parse_iso_date("1985 ff, geschätzt") == "1985-01-01"
    assert parse_iso_date("ungefähr 1985 ff.") == "1985-01-01"
    # Ohne Datum-Rest oder mit ungueltigem Rest → None
    assert parse_iso_date("ff") is None
    assert parse_iso_date("ff.") is None
    assert parse_iso_date("f.") is None
    assert parse_iso_date("1700 ff.") is None  # ausserhalb 1800-2999
    assert parse_iso_date("abc ff.") is None
    # Kein False-Positive fuer Woerter, die mit "f"/"ff" enden aber keinen
    # Zitat-Marker meinen. Das Lookbehind (?<=\d) und der \s+-Zweig blocken
    # Wort-Bestandteil-Positionen: "Auffall" endet auf "l" (kein Match);
    # "fest", "auf" haben zwar "f" am Ende bzw. Anfang, aber keiner Ziffer
    # davor - Match auf "1985 fest" wuerde das f am Wort-Ende erwarten,
    # die Datei-Struktur endet aber mit "t", kein Match.
    assert parse_iso_date("1985 fest") is None
    assert parse_iso_date("1985 auf") is None
    assert parse_iso_date("1985 Auffall") is None
    # Kein Ziffer-vor-Marker beim Kompakt-Zweig ohne Ziffer davor
    assert parse_iso_date("Sample f.") is None
    # Datums-Fund mit Wort das auf f endet, aber ohne Ziffer davor:
    # weder \s+ff?$ noch (?<=\d)ff?$ matcht - kein False-Strip
    assert parse_iso_date("Auf 1985") is None
    # Bestehende Suffixe unveraendert (kein Regress)
    assert parse_iso_date("1985 ca.") == "1985-01-01"
    assert parse_iso_date("1985 schaetzungsweise") == "1985-01-01"
    assert parse_iso_date("1985 ungefähr") == "1985-01-01"
    assert parse_iso_date("1985 estimated") == "1985-01-01"
    assert parse_iso_date("1985 geschätzt") == "1985-01-01"
    # Bestehende Praefixe unveraendert (kein Regress)
    assert parse_iso_date("ca. 1985") == "1985-01-01"
    assert parse_iso_date("circa 2020") == "2020-01-01"
    # Bestehende Range-Formen unveraendert (kein Regress) - "und folgende"
    # ist der offene End-Datum-Pendant zur festen Range-Form
    assert parse_iso_date("1985-1990") == "1985-01-01"
    assert parse_iso_date("1985 bis 1990") == "1985-01-01"
    assert parse_iso_date("zwischen 1985 und 1990") == "1985-01-01"


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


def test_parse_iso_date_franzoesische_saison_namen():
    """Franzoesische Saison-Namen (Suisse romande - Wallis/Waadt/Genf,
    Sammler-Notizen aus Chamonix-Argentiere/Val d'Anniviers). printemps=
    Fruehling (Monat 3), ete=Sommer (Monat 6, Standard-FR-Schreibweise
    "été" mit e-acute, via NFKD-Strip auf ete normalisiert), automne=
    Herbst (Monat 9), hiver=Winter (Monat 12)."""
    # Voll-Formen Season + Jahr (spiegelt DE/EN-Testblock)
    assert parse_iso_date("printemps 2024") == "2024-03-01"
    assert parse_iso_date("ete 2024") == "2024-06-01"
    assert parse_iso_date("été 2024") == "2024-06-01"
    assert parse_iso_date("automne 2024") == "2024-09-01"
    assert parse_iso_date("hiver 2024") == "2024-12-01"
    # Case-Insensitivitaet (Caps-Lock-Etiketten, Titel-Case)
    assert parse_iso_date("Printemps 2024") == "2024-03-01"
    assert parse_iso_date("ETE 2024") == "2024-06-01"
    assert parse_iso_date("ÉTÉ 2024") == "2024-06-01"
    assert parse_iso_date("Automne 2024") == "2024-09-01"
    assert parse_iso_date("HIVER 2024") == "2024-12-01"
    # Year-first Notation (Ordner-Struktur, Excel-Auto-Fill)
    assert parse_iso_date("2024 printemps") == "2024-03-01"
    assert parse_iso_date("2024/ete") == "2024-06-01"
    assert parse_iso_date("2024-automne") == "2024-09-01"
    # Praepositions-Alternante von/of (DE/EN-Prosa spiegelt auf FR-Season)
    assert parse_iso_date("printemps von 2024") == "2024-03-01"
    assert parse_iso_date("automne of 2019") == "2019-09-01"
    # Kombination mit Approx-Praefix
    assert parse_iso_date("ca. printemps 2024") == "2024-03-01"
    # Ungueltiges Jahr (ausserhalb [1800, 2999])
    assert parse_iso_date("printemps 1700") is None
    assert parse_iso_date("hiver 3000") is None
    # Regress: bestehende DE/EN-Saisonen bleiben unveraendert
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("summer 2024") == "2024-06-01"
    assert parse_iso_date("Winter 2024") == "2024-12-01"
    assert parse_iso_date("Frühsommer 2024") == "2024-06-01"


def test_parse_iso_date_italienische_saison_namen():
    """Italienische Saison-Namen (Ticino / italienische Schweiz sowie
    geerbte Sammler-Notizen aus italienischen Alpen-/Dolomiten-Fundorten).

    primavera=Fruehling (Monat 3), estate=Sommer (Monat 6, alle ASCII
    ohne Akzente auf IT-Season-Namen), autunno=Herbst (Monat 9),
    inverno=Winter (Monat 12). Symmetrie-Vervollstaendigung zum bereits
    gepflegten IT-Monat-Block (gennaio..dicembre) in :data:`_MONTH_NAMES`:
    dort ist Ticino als IT-Sprachraum begruendet, hier fehlten die
    passenden Saison-Namen.
    """
    # Voll-Formen Season + Jahr (spiegelt DE/EN/FR-Testblock)
    assert parse_iso_date("primavera 2024") == "2024-03-01"
    assert parse_iso_date("estate 2024") == "2024-06-01"
    assert parse_iso_date("autunno 2024") == "2024-09-01"
    assert parse_iso_date("inverno 2024") == "2024-12-01"
    # Case-Insensitivitaet (Caps-Lock-Etiketten, Titel-Case)
    assert parse_iso_date("Primavera 2024") == "2024-03-01"
    assert parse_iso_date("ESTATE 2024") == "2024-06-01"
    assert parse_iso_date("Autunno 2024") == "2024-09-01"
    assert parse_iso_date("INVERNO 2024") == "2024-12-01"
    # Year-first Notation (Ordner-Struktur, Excel-Auto-Fill)
    assert parse_iso_date("2024 primavera") == "2024-03-01"
    assert parse_iso_date("2024/estate") == "2024-06-01"
    assert parse_iso_date("2024-autunno") == "2024-09-01"
    # Praepositions-Alternante von/of (DE/EN-Prosa spiegelt auf IT-Season)
    assert parse_iso_date("primavera von 2024") == "2024-03-01"
    assert parse_iso_date("estate of 2019") == "2019-06-01"
    # Kombination mit Approx-Praefix
    assert parse_iso_date("ca. primavera 2024") == "2024-03-01"
    # Ungueltiges Jahr (ausserhalb [1800, 2999])
    assert parse_iso_date("primavera 1700") is None
    assert parse_iso_date("inverno 3000") is None
    # Regress: bestehende DE/EN/FR-Saisonen bleiben unveraendert
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("summer 2024") == "2024-06-01"
    assert parse_iso_date("Winter 2024") == "2024-12-01"
    assert parse_iso_date("printemps 2024") == "2024-03-01"
    assert parse_iso_date("ete 2024") == "2024-06-01"
    # Regress: IT-Monat-Namen bleiben unveraendert (Kollisions-Schutz zwischen
    # IT-Monat und IT-Saison, keine Ueberschneidungen).
    assert parse_iso_date("13 giugno 2024") == "2024-06-13"
    assert parse_iso_date("13 gennaio 2024") == "2024-01-13"


def test_parse_iso_date_kompositum_saison():
    """DE-Kompositum-Formen ``Frueh<Saison>``/``Spaet<Saison>`` fuer die drei
    innerhalb eines Kalenderjahres liegenden Saisons.

    ``Frueh<X>`` -> erster Monat der Saison, ``Spaet<X>`` -> dritter Monat.
    Deckt Fruehjahr/Fruehling, Sommer, Herbst ab; Winter-Kompositum ist
    bewusst nicht aufgeloest (mehrdeutig zwischen Jahr-des-Anfangs und
    Jahr-des-Endes).
    """
    # Sommer-Kompositum
    assert parse_iso_date("Frühsommer 2024") == "2024-06-01"
    assert parse_iso_date("Spätsommer 2024") == "2024-08-01"
    # Herbst-Kompositum
    assert parse_iso_date("Frühherbst 2024") == "2024-09-01"
    assert parse_iso_date("Spätherbst 2024") == "2024-11-01"
    # Fruehjahr-/Fruehling-Kompositum
    assert parse_iso_date("Frühfrühling 2024") == "2024-03-01"
    assert parse_iso_date("Spätfrühling 2024") == "2024-05-01"
    assert parse_iso_date("Frühfrühjahr 2024") == "2024-03-01"
    assert parse_iso_date("Spätfrühjahr 2024") == "2024-05-01"
    # ASCII-transliterierte Umlaut-Formen (ae/oe/ue statt ä/ö/ü)
    assert parse_iso_date("Fruehsommer 2024") == "2024-06-01"
    assert parse_iso_date("Spaetsommer 2024") == "2024-08-01"
    assert parse_iso_date("Fruehherbst 2024") == "2024-09-01"
    assert parse_iso_date("Spaetherbst 2024") == "2024-11-01"
    assert parse_iso_date("Fruehfruehjahr 2024") == "2024-03-01"
    assert parse_iso_date("Spaetfruehjahr 2024") == "2024-05-01"
    # Case-Insensitivitaet (Museums-Etiketten in Caps-Lock, gemischte Schreibung)
    assert parse_iso_date("FRUEHSOMMER 2024") == "2024-06-01"
    assert parse_iso_date("SPÄTHERBST 2024") == "2024-11-01"
    assert parse_iso_date("spätsommer 1985") == "1985-08-01"
    assert parse_iso_date("SpätSommer 1985") == "1985-08-01"
    # EN-Kompositum-Formen "earlyspring"/"latespring" etc. (compact)
    assert parse_iso_date("earlysummer 2024") == "2024-06-01"
    assert parse_iso_date("latesummer 2024") == "2024-08-01"
    assert parse_iso_date("earlyautumn 2024") == "2024-09-01"
    assert parse_iso_date("lateautumn 2024") == "2024-11-01"
    assert parse_iso_date("earlyfall 2024") == "2024-09-01"
    assert parse_iso_date("latefall 2024") == "2024-11-01"
    assert parse_iso_date("earlyspring 2024") == "2024-03-01"
    assert parse_iso_date("latespring 2024") == "2024-05-01"
    # Komma-Separator zwischen Saison und Jahr (spiegelt _SEASON_YEAR)
    assert parse_iso_date("Spätsommer, 1985") == "1985-08-01"
    assert parse_iso_date("Frühherbst, 1985") == "1985-09-01"
    # Annaeherungspraefix (ca./circa) + Kompositum-Saison
    assert parse_iso_date("ca. Spätsommer 1985") == "1985-08-01"
    assert parse_iso_date("circa Frühherbst 1985") == "1985-09-01"
    assert parse_iso_date("~ Spätfrühling 2024") == "2024-05-01"
    # Temporale Praeposition (im/vom) + Kompositum-Saison
    assert parse_iso_date("im Frühsommer 2024") == "2024-06-01"
    assert parse_iso_date("im Spätherbst 1985") == "1985-11-01"
    # Year-first-Reihenfolge (_SEASON_YEAR_FIRST)
    assert parse_iso_date("2024 Spätherbst") == "2024-11-01"
    assert parse_iso_date("2024-Spätsommer") == "2024-08-01"
    assert parse_iso_date("2024/Frühsommer") == "2024-06-01"
    # Klammern-/Anfuehrungszeichen-Strip vor der Kompositum-Aufloesung
    assert parse_iso_date("(Spätsommer 2024)") == "2024-08-01"
    assert parse_iso_date('"Frühherbst 2024"') == "2024-09-01"
    # Trailing-Satzzeichen-Strip vor der Kompositum-Aufloesung
    assert parse_iso_date("Spaetsommer 2024.") == "2024-08-01"
    assert parse_iso_date("Frühherbst 1985!") == "1985-09-01"
    # Winter-Kompositum bewusst nicht aufgeloest (Semantik mehrdeutig)
    assert parse_iso_date("Frühwinter 2024") is None
    assert parse_iso_date("Spätwinter 2024") is None
    # Unbekannte Kompositum-Praefixe fallen weiter auf None
    assert parse_iso_date("Vorsommer 2024") is None
    assert parse_iso_date("Nachsommer 2024") is None
    assert parse_iso_date("Hochsommer 2024") is None
    assert parse_iso_date("Mittsommer 2024") is None
    # Jahr ausserhalb 1800-2999 -> None (Bereichs-Konvention greift)
    assert parse_iso_date("Frühsommer 1700") is None
    assert parse_iso_date("Spätherbst 3000") is None
    # Regress-Anker: Basis-Saisons unveraendert
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("Herbst 2024") == "2024-09-01"
    assert parse_iso_date("Frühling 2024") == "2024-03-01"
    assert parse_iso_date("Frühjahr 2024") == "2024-03-01"
    assert parse_iso_date("Winter 2024") == "2024-12-01"
    # Regress-Anker: Winter-Cross-Year weiterhin auf reines Winter beschraenkt
    assert parse_iso_date("Winter 2023/2024") == "2023-12-01"
    # Regress-Anker: Range-Spanne fuer Kompositum-Saison bleibt None (kein
    # kruemliger Fallback-Match auf das erste Jahr)
    assert parse_iso_date("Frühsommer 2023/2024") is None
    assert parse_iso_date("Spätherbst 2023-2024") is None


def test_parse_iso_date_fixed_date_feiertage():
    """Fixed-Date-Feiertag + Jahr (Weihnachten, Silvester, Neujahr,
    Halloween, Nikolaus, Heiligabend, Bundesfeier, Tag der Arbeit, Tag der
    deutschen Einheit, Heilige Drei Koenige, Valentinstag, Allerheiligen,
    Stephans-/Stefanstag).

    Whitelist (DACH + Standard-EN-Termine); variable Feiertage (Ostern,
    Karfreitag, Pfingsten, Muttertag, Vatertag) fallen weiter auf None.
    """
    # Basis-Formen DE
    assert parse_iso_date("Neujahr 2024") == "2024-01-01"
    assert parse_iso_date("Neujahrstag 2024") == "2024-01-01"
    assert parse_iso_date("Valentinstag 2024") == "2024-02-14"
    assert parse_iso_date("Tag der Arbeit 2024") == "2024-05-01"
    assert parse_iso_date("Arbeiterfeiertag 2024") == "2024-05-01"
    assert parse_iso_date("Arbeiterkampftag 2024") == "2024-05-01"
    assert parse_iso_date("Bundesfeier 2023") == "2023-08-01"
    assert parse_iso_date("Schweizer Nationalfeiertag 2023") == "2023-08-01"
    assert parse_iso_date("Tag der deutschen Einheit 2023") == "2023-10-03"
    assert parse_iso_date("Halloween 2019") == "2019-10-31"
    assert parse_iso_date("Allerheiligen 2020") == "2020-11-01"
    assert parse_iso_date("Nikolaus 2022") == "2022-12-06"
    assert parse_iso_date("Nikolaustag 2022") == "2022-12-06"
    assert parse_iso_date("Heiligabend 2023") == "2023-12-24"
    assert parse_iso_date("Weihnachten 2023") == "2023-12-25"
    assert parse_iso_date("Weihnachtstag 2023") == "2023-12-25"
    assert parse_iso_date("Stefanstag 2023") == "2023-12-26"
    assert parse_iso_date("Stephanstag 2023") == "2023-12-26"
    assert parse_iso_date("Silvester 2020") == "2020-12-31"
    assert parse_iso_date("Silvesterabend 2020") == "2020-12-31"
    assert parse_iso_date("Heilige Drei Koenige 2024") == "2024-01-06"
    assert parse_iso_date("Heilige Drei Könige 2024") == "2024-01-06"
    assert parse_iso_date("Dreikoenigstag 2024") == "2024-01-06"
    # Basis-Formen EN
    assert parse_iso_date("New Year 2024") == "2024-01-01"
    assert parse_iso_date("New Year's Day 2024") == "2024-01-01"
    assert parse_iso_date("New Year’s Day 2024") == "2024-01-01"  # Curly-Apostroph
    assert parse_iso_date("Epiphany 2024") == "2024-01-06"
    assert parse_iso_date("Valentine's Day 2024") == "2024-02-14"
    assert parse_iso_date("Labour Day 2024") == "2024-05-01"
    assert parse_iso_date("Labor Day 2024") == "2024-05-01"
    assert parse_iso_date("May Day 2024") == "2024-05-01"
    assert parse_iso_date("Swiss National Day 2023") == "2023-08-01"
    assert parse_iso_date("German Unity Day 2023") == "2023-10-03"
    assert parse_iso_date("All Saints Day 2020") == "2020-11-01"
    assert parse_iso_date("St. Nicholas Day 2022") == "2022-12-06"
    assert parse_iso_date("St Nicholas Day 2022") == "2022-12-06"
    assert parse_iso_date("Christmas Eve 2023") == "2023-12-24"
    assert parse_iso_date("Christmas 2023") == "2023-12-25"
    assert parse_iso_date("Christmas Day 2023") == "2023-12-25"
    assert parse_iso_date("Boxing Day 2023") == "2023-12-26"
    assert parse_iso_date("New Year's Eve 2020") == "2020-12-31"
    assert parse_iso_date("New Year’s Eve 2020") == "2020-12-31"
    # Case-Insensitivitaet
    assert parse_iso_date("weihnachten 2023") == "2023-12-25"
    assert parse_iso_date("WEIHNACHTEN 2023") == "2023-12-25"
    assert parse_iso_date("CHRISTMAS 2023") == "2023-12-25"
    assert parse_iso_date("silvester 2020") == "2020-12-31"
    # Trenner-Varianten (Komma / Slash / Kombination)
    assert parse_iso_date("Weihnachten, 2023") == "2023-12-25"
    assert parse_iso_date("Weihnachten/2023") == "2023-12-25"
    assert parse_iso_date("Silvester 2020") == "2020-12-31"
    # Praepositions-Trenner (von / of), spiegelt _SEASON_YEAR / _MONTH_YEAR
    assert parse_iso_date("Weihnachten von 2023") == "2023-12-25"
    assert parse_iso_date("Silvester von 2020") == "2020-12-31"
    assert parse_iso_date("Christmas of 2023") == "2023-12-25"
    assert parse_iso_date("New Year of 2024") == "2024-01-01"
    # Year-first Reihenfolge (spiegelt _SEASON_YEAR_FIRST)
    assert parse_iso_date("2023 Weihnachten") == "2023-12-25"
    assert parse_iso_date("2020-Silvester") == "2020-12-31"
    assert parse_iso_date("2024/Halloween") == "2024-10-31"
    assert parse_iso_date("2019 Nikolaustag") == "2019-12-06"
    assert parse_iso_date("2023 Christmas") == "2023-12-25"
    # Umlaut- vs ASCII-Transliteration (Umlaut- und ae/oe/ue-Form aequivalent)
    assert parse_iso_date("Heilige Drei Könige 2024") == "2024-01-06"
    assert parse_iso_date("Heilige Drei Koenige 2024") == "2024-01-06"
    # Annaeherungspraefix (ca./circa) + Feiertag
    assert parse_iso_date("ca. Weihnachten 2023") == "2023-12-25"
    assert parse_iso_date("circa Silvester 2020") == "2020-12-31"
    assert parse_iso_date("~ Halloween 2019") == "2019-10-31"
    # Temporale Praeposition + Feiertag
    assert parse_iso_date("an Weihnachten 2023") is None  # "an" nicht in _TEMPORAL_PREFIX
    assert parse_iso_date("zu Weihnachten 2023") is None  # "zu" nicht in _TEMPORAL_PREFIX
    # Klammern-/Anfuehrungszeichen-Strip vor der Feiertag-Aufloesung
    assert parse_iso_date("(Weihnachten 2023)") == "2023-12-25"
    assert parse_iso_date('"Silvester 2020"') == "2020-12-31"
    # Trailing-Satzzeichen-Strip vor der Feiertag-Aufloesung
    assert parse_iso_date("Weihnachten 2023.") == "2023-12-25"
    assert parse_iso_date("Silvester 2020!") == "2020-12-31"
    # Trailing-Klammer-Annotation-Strip vor der Feiertag-Aufloesung
    assert parse_iso_date("Weihnachten 2023 (Foto)") == "2023-12-25"
    assert parse_iso_date("Silvester 2020 [Auktion]") == "2020-12-31"
    # Variable Feiertage werden ueber den Osterzyklus aufgeloest (siehe
    # test_parse_iso_date_variable_easter_feiertage). Muttertag/Vatertag
    # bleiben None (Locale-Ambiguitaet, siehe Docstring bei
    # :data:`_HOLIDAY_EASTER_OFFSET`).
    assert parse_iso_date("Muttertag 2024") is None
    assert parse_iso_date("Vatertag 2024") is None
    assert parse_iso_date("Mother's Day 2024") is None
    assert parse_iso_date("Father's Day 2024") is None
    # Unbekannte Namen fallen auf None
    assert parse_iso_date("Notaholiday 2024") is None
    assert parse_iso_date("Foobar 2024") is None
    assert parse_iso_date("2024 Notaholiday") is None
    # Jahr ausserhalb 1800-2999 -> None
    assert parse_iso_date("Weihnachten 1799") is None
    assert parse_iso_date("Weihnachten 3000") is None
    assert parse_iso_date("Silvester 1500") is None
    # Regress-Anker: Basis-Saisons und Monatsnamen unveraendert
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("Herbst 2024") == "2024-09-01"
    assert parse_iso_date("Winter 2024") == "2024-12-01"
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("June 2024") == "2024-06-01"
    assert parse_iso_date("March 2024") == "2024-03-01"
    # Regress-Anker: Standard-ISO/DE-Formate unveraendert
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    # Regress-Anker: Quartal / Halbjahr / KW unveraendert (kein
    # kruemliger Match auf die Feiertag-Fallback-Kaskade)
    assert parse_iso_date("Q1 2024") == "2024-01-01"
    assert parse_iso_date("H2 2024") == "2024-07-01"
    assert parse_iso_date("KW 12 2024") == "2024-03-18"
    # Regress-Anker: Approximations-Marker allein (ohne Feiertag) bleibt None
    assert parse_iso_date("ca.") is None
    assert parse_iso_date("Weihnachten") is None  # Feiertag ohne Jahr -> None
    assert parse_iso_date("Silvester") is None


def test_parse_iso_date_dach_konfessionelle_fixed_date_feiertage():
    """Fixed-Date DACH-katholische/-protestantische Zusatz-Feiertage: Josefstag
    (19.03.), Peter und Paul (29.06.), Mariae Himmelfahrt (15.08.),
    Reformationstag (31.10.), Allerseelen (02.11.), Mariae Empfaengnis (08.12.).

    Ergaenzt die konfessionellen Fixed-Date-Marker aus DACH-Sammler-Notizen
    ueber die bereits vorhandenen weltlichen (Neujahr, Tag der Arbeit,
    Bundesfeier, Tag der deutschen Einheit) und uebergreifend-christlichen
    (Heilige Drei Koenige, Allerheiligen, Nikolaus, Heiligabend, Weihnachten,
    Stephanstag, Silvester) hinaus. Alle sechs Tage sind in mindestens einem
    DACH-Teilraum gesetzlicher Feiertag (Reformationstag in den evangelischen
    Nord-/Ost-DE-Bundeslaendern; Mariae Himmelfahrt in AT/BY/SL und
    Innerschweiz; Mariae Empfaengnis in AT und den katholischen CH-Kantonen;
    Josefstag / Peter und Paul in TI/GR/UR/NW/SZ/VS/LU/ZG). Variable
    Feiertage (Volkstrauertag, Totensonntag, Advent, Bettag) fallen weiter
    auf None.
    """
    # Reformationstag (31.10.) - kollidiert kalendarisch mit Halloween, beide
    # Namen liefern semantisch dasselbe (10, 31)-Datum aus dem Dict.
    assert parse_iso_date("Reformationstag 2017") == "2017-10-31"
    assert parse_iso_date("Reformationsfest 2020") == "2020-10-31"
    assert parse_iso_date("Reformation Day 2023") == "2023-10-31"
    # Regress: Halloween 2019 wirkt unveraendert weiter
    assert parse_iso_date("Halloween 2019") == "2019-10-31"
    # Mariae Himmelfahrt (15.08.) - Umlaut- und ASCII-Transliteration
    assert parse_iso_date("Mariä Himmelfahrt 2024") == "2024-08-15"
    assert parse_iso_date("Mariae Himmelfahrt 2024") == "2024-08-15"
    assert parse_iso_date("Maria Himmelfahrt 2024") == "2024-08-15"
    assert parse_iso_date("Hohe Unsere Frau 2024") == "2024-08-15"
    assert parse_iso_date("Assumption 2024") == "2024-08-15"
    assert parse_iso_date("Assumption of Mary 2024") == "2024-08-15"
    assert parse_iso_date("Assumption of the Virgin Mary 2024") == "2024-08-15"
    assert parse_iso_date("Assumption of Our Lady 2024") == "2024-08-15"
    # Mariae Empfaengnis (08.12.) - Umlaut- und ASCII-Transliteration
    assert parse_iso_date("Mariä Empfängnis 2023") == "2023-12-08"
    assert parse_iso_date("Mariae Empfaengnis 2023") == "2023-12-08"
    assert parse_iso_date("Maria Empfängnis 2023") == "2023-12-08"
    assert parse_iso_date("Empfängnis Mariä 2023") == "2023-12-08"
    assert parse_iso_date("Immaculate Conception 2023") == "2023-12-08"
    assert parse_iso_date("Feast of the Immaculate Conception 2023") == "2023-12-08"
    # Allerseelen (02.11.) - direkt nach Allerheiligen (bereits vorhanden)
    assert parse_iso_date("Allerseelen 2020") == "2020-11-02"
    assert parse_iso_date("All Souls 2020") == "2020-11-02"
    assert parse_iso_date("All Souls' Day 2020") == "2020-11-02"
    assert parse_iso_date("All Souls’ Day 2020") == "2020-11-02"  # Curly-Apostroph
    # Regress: Allerheiligen 2020 bleibt (11, 1)
    assert parse_iso_date("Allerheiligen 2020") == "2020-11-01"
    # Josefstag (19.03.) - DE- und CH-Innerschweiz-Formen plus EN
    assert parse_iso_date("Josefstag 2024") == "2024-03-19"
    assert parse_iso_date("Josefitag 2024") == "2024-03-19"
    assert parse_iso_date("Josephstag 2024") == "2024-03-19"
    assert parse_iso_date("St. Joseph's Day 2024") == "2024-03-19"
    assert parse_iso_date("St Joseph's Day 2024") == "2024-03-19"
    assert parse_iso_date("Saint Joseph's Day 2024") == "2024-03-19"
    # Peter und Paul (29.06.) - DE-/DE-Genitiv-Form plus EN
    assert parse_iso_date("Peter und Paul 2024") == "2024-06-29"
    assert parse_iso_date("Petri und Pauli 2024") == "2024-06-29"
    assert parse_iso_date("Petrus und Paulus 2024") == "2024-06-29"
    assert parse_iso_date("Peter and Paul 2024") == "2024-06-29"
    assert parse_iso_date("Sts. Peter and Paul 2024") == "2024-06-29"
    assert parse_iso_date("Saints Peter and Paul 2024") == "2024-06-29"
    assert parse_iso_date("Feast of Sts. Peter and Paul 2024") == "2024-06-29"
    # Case-Insensitivitaet (kleiner Auszug, spiegelt bestehende Feiertag-Test-Konvention)
    assert parse_iso_date("reformationstag 2023") == "2023-10-31"
    assert parse_iso_date("REFORMATIONSTAG 2023") == "2023-10-31"
    assert parse_iso_date("mariä himmelfahrt 2024") == "2024-08-15"
    # Trenner-Varianten (Komma / Slash / Praeposition), spiegelt Basis-Feiertag-Test
    assert parse_iso_date("Reformationstag, 2023") == "2023-10-31"
    assert parse_iso_date("Reformationstag/2023") == "2023-10-31"
    assert parse_iso_date("Mariä Himmelfahrt von 2024") == "2024-08-15"
    assert parse_iso_date("Assumption of Mary of 2024") == "2024-08-15"
    # Year-first Reihenfolge
    assert parse_iso_date("2023 Reformationstag") == "2023-10-31"
    assert parse_iso_date("2024-Mariä Himmelfahrt") == "2024-08-15"
    assert parse_iso_date("2023/Immaculate Conception") == "2023-12-08"
    # Approximations-Praefix (ca./circa/~) + Feiertag
    assert parse_iso_date("ca. Reformationstag 2023") == "2023-10-31"
    assert parse_iso_date("circa Josefstag 2024") == "2024-03-19"
    assert parse_iso_date("~ Peter und Paul 2024") == "2024-06-29"
    # Klammern-/Anfuehrungszeichen-Strip und Trailing-Satzzeichen
    assert parse_iso_date("(Reformationstag 2023)") == "2023-10-31"
    assert parse_iso_date('"Mariä Himmelfahrt 2024"') == "2024-08-15"
    assert parse_iso_date("Josefstag 2024.") == "2024-03-19"
    assert parse_iso_date("Peter und Paul 2024!") == "2024-06-29"
    # Trailing-Klammer-Annotation-Strip
    assert parse_iso_date("Reformationstag 2023 (Foto)") == "2023-10-31"
    assert parse_iso_date("Mariä Himmelfahrt 2024 [Auktion]") == "2024-08-15"
    # Jahr ausserhalb 1800-2999 -> None
    assert parse_iso_date("Reformationstag 1799") is None
    assert parse_iso_date("Mariä Himmelfahrt 3000") is None
    assert parse_iso_date("Josefstag 1500") is None
    # Feiertag ohne Jahr -> None
    assert parse_iso_date("Reformationstag") is None
    assert parse_iso_date("Mariä Himmelfahrt") is None
    assert parse_iso_date("Josefstag") is None
    # Variable konfessionelle Feiertage (Volkstrauertag = zweitletzter Sonntag
    # vor 1. Advent, Totensonntag = letzter Sonntag vor 1. Advent, Advent 1-4,
    # Buss- und Bettag = Mittwoch vor Totensonntag) fallen weiter auf None -
    # sie erfordern jaehrlich unterschiedliche Datums-Berechnung (relativ zum
    # ersten Advent, der jaehrlich zwischen 27.11. und 03.12. springt) und sind
    # aus Konservativitaets-Gruenden nicht in diesem konfessionellen Fixed-Date-
    # Fix behandelt.
    assert parse_iso_date("Volkstrauertag 2024") is None
    assert parse_iso_date("Totensonntag 2024") is None
    assert parse_iso_date("1. Advent 2024") is None
    assert parse_iso_date("Bettag 2024") is None
    # Regress-Anker: bestehende Fixed-Date-Feiertage und Standard-Formate
    assert parse_iso_date("Weihnachten 2023") == "2023-12-25"
    assert parse_iso_date("Neujahr 2024") == "2024-01-01"
    assert parse_iso_date("Tag der deutschen Einheit 2023") == "2023-10-03"
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"


def test_parse_iso_date_variable_easter_feiertage():
    """Variable Feiertage im Osterzyklus (DE/EN): Datum wird jahresspezifisch
    aus Ostersonntag (Computus/Butcher-Meeus) plus Offset in Tagen berechnet.

    Ostersonntag als Anker fuer Karfreitag (-2), Karsamstag (-1), Ostermontag
    (+1), Palmsonntag (-7), Gruendonnerstag (-3), Aschermittwoch (-46),
    Rosenmontag (-48), Fastnachtsdienstag (-47), Christi Himmelfahrt (+39),
    Pfingsten (+49), Pfingstmontag (+50), Fronleichnam (+60).
    """
    # Kanonische Ostersonntag-Referenzdaten (unabhaengig verifiziert):
    # 2024 -> 31.03., 2023 -> 09.04., 2022 -> 17.04., 2020 -> 12.04.,
    # 2000 -> 23.04., 1900 -> 15.04., 1954 -> 18.04.
    assert parse_iso_date("Ostern 2024") == "2024-03-31"
    assert parse_iso_date("Ostersonntag 2024") == "2024-03-31"
    assert parse_iso_date("Easter 2024") == "2024-03-31"
    assert parse_iso_date("Easter Sunday 2024") == "2024-03-31"
    assert parse_iso_date("Ostern 2023") == "2023-04-09"
    assert parse_iso_date("Ostern 2022") == "2022-04-17"
    assert parse_iso_date("Ostern 2020") == "2020-04-12"
    assert parse_iso_date("Ostern 2000") == "2000-04-23"
    assert parse_iso_date("Ostern 1900") == "1900-04-15"
    assert parse_iso_date("Ostern 1954") == "1954-04-18"
    # Karwoche (Offset relativ zu Ostersonntag)
    assert parse_iso_date("Karfreitag 2024") == "2024-03-29"
    assert parse_iso_date("Good Friday 2024") == "2024-03-29"
    assert parse_iso_date("Karsamstag 2024") == "2024-03-30"
    assert parse_iso_date("Holy Saturday 2024") == "2024-03-30"
    assert parse_iso_date("Ostermontag 2024") == "2024-04-01"
    assert parse_iso_date("Easter Monday 2024") == "2024-04-01"
    assert parse_iso_date("Palmsonntag 2024") == "2024-03-24"
    assert parse_iso_date("Palm Sunday 2024") == "2024-03-24"
    assert parse_iso_date("Gründonnerstag 2024") == "2024-03-28"
    assert parse_iso_date("Gruendonnerstag 2024") == "2024-03-28"
    assert parse_iso_date("Maundy Thursday 2024") == "2024-03-28"
    # Fastnachtszeit
    assert parse_iso_date("Aschermittwoch 2024") == "2024-02-14"
    assert parse_iso_date("Ash Wednesday 2024") == "2024-02-14"
    assert parse_iso_date("Rosenmontag 2024") == "2024-02-12"
    assert parse_iso_date("Fastnachtsdienstag 2024") == "2024-02-13"
    assert parse_iso_date("Faschingsdienstag 2024") == "2024-02-13"
    assert parse_iso_date("Shrove Tuesday 2024") == "2024-02-13"
    assert parse_iso_date("Mardi Gras 2024") == "2024-02-13"
    assert parse_iso_date("Pancake Day 2024") == "2024-02-13"
    # Nach Ostern
    assert parse_iso_date("Christi Himmelfahrt 2024") == "2024-05-09"
    assert parse_iso_date("Himmelfahrt 2024") == "2024-05-09"
    assert parse_iso_date("Ascension Day 2024") == "2024-05-09"
    assert parse_iso_date("Pfingsten 2024") == "2024-05-19"
    assert parse_iso_date("Pfingstsonntag 2024") == "2024-05-19"
    assert parse_iso_date("Pentecost 2024") == "2024-05-19"
    assert parse_iso_date("Whitsun 2024") == "2024-05-19"
    assert parse_iso_date("Whit Sunday 2024") == "2024-05-19"
    assert parse_iso_date("Pfingstmontag 2024") == "2024-05-20"
    assert parse_iso_date("Whit Monday 2024") == "2024-05-20"
    assert parse_iso_date("Fronleichnam 2024") == "2024-05-30"
    assert parse_iso_date("Corpus Christi 2024") == "2024-05-30"
    assert parse_iso_date("Trinitatis 2024") == "2024-05-26"
    assert parse_iso_date("Trinity Sunday 2024") == "2024-05-26"
    # Year-first Reihenfolge (spiegelt _HOLIDAY_YEAR_FIRST)
    assert parse_iso_date("2024 Ostern") == "2024-03-31"
    assert parse_iso_date("2024-Karfreitag") == "2024-03-29"
    assert parse_iso_date("2024/Pfingsten") == "2024-05-19"
    assert parse_iso_date("2024 Christi Himmelfahrt") == "2024-05-09"
    # Case-Insensitivitaet + Praepositions-Trenner
    assert parse_iso_date("ostern 2024") == "2024-03-31"
    assert parse_iso_date("OSTERN 2024") == "2024-03-31"
    assert parse_iso_date("EASTER 2024") == "2024-03-31"
    assert parse_iso_date("Ostern von 2024") == "2024-03-31"
    assert parse_iso_date("Easter of 2024") == "2024-03-31"
    # Praeposition + Feiertag-Praefix (spiegelt Fixed-Date-Verhalten)
    assert parse_iso_date("ca. Ostern 2024") == "2024-03-31"
    assert parse_iso_date("circa Karfreitag 2024") == "2024-03-29"
    # Klammern-/Anfuehrungszeichen-/Trailing-Punct-Strip
    assert parse_iso_date("(Ostern 2024)") == "2024-03-31"
    assert parse_iso_date('"Karfreitag 2024"') == "2024-03-29"
    assert parse_iso_date("Ostern 2024.") == "2024-03-31"
    assert parse_iso_date("Pfingsten 2024 (Foto)") == "2024-05-19"
    # Monat-Uebergang: Aschermittwoch 2016 (Ostersonntag 27.03.2016 - 46 Tage
    # = 10.02.2016) faellt von April- in Februar-Datum via datetime.timedelta.
    assert parse_iso_date("Ostern 2016") == "2016-03-27"
    assert parse_iso_date("Aschermittwoch 2016") == "2016-02-10"
    # Jahr ausserhalb 1800-2999 -> None
    assert parse_iso_date("Ostern 1799") is None
    assert parse_iso_date("Karfreitag 3000") is None
    # Unbekannte variable Feiertage bleiben None (Locale-Ambiguitaet)
    assert parse_iso_date("Muttertag 2024") is None
    assert parse_iso_date("Vatertag 2024") is None
    # Regress-Anker: Fixed-Date-Feiertage weiterhin ueber die eigene Whitelist
    assert parse_iso_date("Weihnachten 2024") == "2024-12-25"
    assert parse_iso_date("Silvester 2024") == "2024-12-31"
    assert parse_iso_date("Neujahr 2024") == "2024-01-01"


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
    # "Anfang <Monatsname> <Jahr>" wird jetzt ueber das eigene
    # _RELATIVE_MONTH_YEAR-Pattern auf den ersten Tag des jeweiligen Monats
    # gemappt (semantisch: "Monatsanfang" = 1. Tag) - siehe
    # ``test_parse_iso_date_relative_monat_jahresposition``. Frueher fiel diese
    # Form auf None (mit Begruendung "nicht eindeutig genug"), inzwischen ist
    # die Sammler-Semantik eindeutig verortet.
    assert parse_iso_date("Anfang März 2024") == "2024-03-01"
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


def test_parse_iso_date_year_compound_position():
    """Deutsche Kompositum-Form Jahres<anfang/mitte/ende> + Jahr → Jan/Jul/Dez.

    Substantivierte DE-Prosa-Form neben der artikellosen Kurzform ("Jahresende
    1985" = "Ende 1985"). In geerbten Fund-Tagebuechern und Prosa-Etiketten
    haeufiger als die journalistische Kurzform. Semantik spiegelt
    :data:`_RELATIVE_MONTHS` auf die Kompositum-Achse:
    Jahresanfang/Jahresbeginn -> Jan, Jahresmitte -> Jul, Jahresende/
    Jahresschluss -> Dez.
    """
    # Deutsch: Jahresanfang/Jahresbeginn = Januar
    assert parse_iso_date("Jahresanfang 2024") == "2024-01-01"
    assert parse_iso_date("Jahresbeginn 2024") == "2024-01-01"
    assert parse_iso_date("Jahresstart 2024") == "2024-01-01"
    # Jahresmitte = Juli
    assert parse_iso_date("Jahresmitte 2024") == "2024-07-01"
    # Jahresende/Jahresschluss/Jahresausklang = Dezember
    assert parse_iso_date("Jahresende 2024") == "2024-12-01"
    assert parse_iso_date("Jahresschluss 2024") == "2024-12-01"
    assert parse_iso_date("Jahresausklang 2024") == "2024-12-01"
    # Verschiedene Jahre
    assert parse_iso_date("Jahresanfang 1985") == "1985-01-01"
    assert parse_iso_date("Jahresmitte 1999") == "1999-07-01"
    assert parse_iso_date("Jahresende 1985") == "1985-12-01"
    # Case-insensitive
    assert parse_iso_date("JAHRESANFANG 2024") == "2024-01-01"
    assert parse_iso_date("jahresende 2024") == "2024-12-01"
    assert parse_iso_date("JahresMitte 2024") == "2024-07-01"
    # Bindestrich-Trenner (typografisch selten aber spec-konform)
    assert parse_iso_date("Jahresende-2024") == "2024-12-01"
    assert parse_iso_date("Jahresanfang-2024") == "2024-01-01"
    # Trailing Satzzeichen (via _TRAILING_PUNCT-Strip)
    assert parse_iso_date("Jahresmitte 2024.") == "2024-07-01"
    assert parse_iso_date("Jahresende 2024,") == "2024-12-01"
    # In Klammern (via _BRACKET_PAIRS-Strip)
    assert parse_iso_date("[Jahresende 1985]") == "1985-12-01"
    assert parse_iso_date("(Jahresmitte 2020)") == "2020-07-01"
    # Kombiniert mit Annaeherungspraefix
    assert parse_iso_date("ca. Jahresende 1990") == "1990-12-01"
    assert parse_iso_date("circa Jahresanfang 2020") == "2020-01-01"


def test_parse_iso_date_year_compound_position_ungueltig():
    """Kompositum ohne Jahr / Jahr ausserhalb 1800-2999 / unbekanntes Suffix → None."""
    # Nur Kompositum-Prefix ohne Jahr
    assert parse_iso_date("Jahresanfang") is None
    assert parse_iso_date("Jahresende") is None
    assert parse_iso_date("Jahresmitte") is None
    # Jahr ausserhalb 1800-2999
    assert parse_iso_date("Jahresende 1700") is None
    assert parse_iso_date("Jahresanfang 3000") is None
    # Unbekanntes Positions-Suffix
    assert parse_iso_date("Jahreskern 2024") is None
    assert parse_iso_date("Jahresrand 2024") is None
    # Ohne Jahres-Praefix -> _RELATIVE_YEAR-Kurzform (kein Regress)
    assert parse_iso_date("Anfang 2024") == "2024-01-01"
    assert parse_iso_date("Mitte 2024") == "2024-07-01"
    assert parse_iso_date("Ende 2024") == "2024-12-01"


def test_parse_iso_date_relative_monat_jahresposition():
    """Anfang/Mitte/Ende + Monatsname + Jahr → Monatsanfang/Mitte/Ende.

    Sehr verbreitet in DE-Sammler-Notizen und Fund-Etiketten, wenn der Fund
    zwar auf einen Monat, aber nicht auf ein Einzeldatum eingegrenzt werden kann
    ("Fund Anfang Juni 2024", "Bergtour Mitte August 2020", "Erwerb Ende
    Dezember 2019", "found mid-March 1995"). Konvention: Anfang/early -> Tag 1,
    Mitte/mid -> Tag 15, Ende/late -> letzter Tag des Monats (28-31, Schaltjahr-
    korrekt via datetime-Arithmetik).
    """
    # Deutsch: Anfang / Mitte / Ende auf 1 / 15 / letzter Tag
    assert parse_iso_date("Anfang Juni 2024") == "2024-06-01"
    assert parse_iso_date("Mitte Juni 2024") == "2024-06-15"
    assert parse_iso_date("Ende Juni 2024") == "2024-06-30"
    # Ende der Monate mit 31 Tagen
    assert parse_iso_date("Ende Januar 2024") == "2024-01-31"
    assert parse_iso_date("Ende Dezember 2024") == "2024-12-31"
    assert parse_iso_date("Ende August 2020") == "2020-08-31"
    # Ende der Monate mit 30 Tagen
    assert parse_iso_date("Ende April 2024") == "2024-04-30"
    assert parse_iso_date("Ende November 2024") == "2024-11-30"
    # Februar-Schaltjahr-Behandlung
    assert parse_iso_date("Ende Februar 2024") == "2024-02-29"  # Schaltjahr
    assert parse_iso_date("Ende Februar 2023") == "2023-02-28"  # kein Schaltjahr
    assert parse_iso_date("Ende Februar 2000") == "2000-02-29"  # Schaltjahr (durch 400)
    assert parse_iso_date("Ende Februar 1900") == "1900-02-28"  # kein Schaltjahr (durch 100, nicht 400)
    # Alle DE-Positionen fuer weitere Monate
    assert parse_iso_date("Anfang Januar 2024") == "2024-01-01"
    assert parse_iso_date("Mitte März 2020") == "2020-03-15"
    assert parse_iso_date("Ende Juli 1985") == "1985-07-31"
    # DE-Umlaut-Monatsnamen (Maerz)
    assert parse_iso_date("Mitte Maerz 2024") == "2024-03-15"
    assert parse_iso_date("Ende März 2024") == "2024-03-31"
    # Englisch: early / mid / late auf 1 / 15 / letzter Tag
    assert parse_iso_date("early June 2024") == "2024-06-01"
    assert parse_iso_date("mid June 2024") == "2024-06-15"
    assert parse_iso_date("late June 2024") == "2024-06-30"
    assert parse_iso_date("late February 2024") == "2024-02-29"
    assert parse_iso_date("early January 1985") == "1985-01-01"
    # Bindestrich-Compound (typische EN-Notation "mid-June", "late-March")
    assert parse_iso_date("mid-June 2024") == "2024-06-15"
    assert parse_iso_date("early-June 2024") == "2024-06-01"
    assert parse_iso_date("late-March 2024") == "2024-03-31"
    # Case-insensitive
    assert parse_iso_date("ANFANG JUNI 2024") == "2024-06-01"
    assert parse_iso_date("Mid June 2024") == "2024-06-15"
    assert parse_iso_date("LATE JUNE 2024") == "2024-06-30"
    # Monatsname als Kurzform mit Punkt (spiegelt _DAY_MONTH_YEAR / _MONTH_YEAR)
    assert parse_iso_date("Anfang Jan. 2024") == "2024-01-01"
    assert parse_iso_date("Ende Dez. 2024") == "2024-12-31"
    assert parse_iso_date("mid Jan. 2024") == "2024-01-15"
    # Kombiniert mit Annaeherungspraefix (Rekursion durch _APPROX_PREFIX-Strip)
    assert parse_iso_date("ca. Anfang Juni 2024") == "2024-06-01"
    assert parse_iso_date("circa mid June 2024") == "2024-06-15"
    # Kombiniert mit trailing Satzzeichen (durch _TRAILING_PUNCT gestrippt)
    assert parse_iso_date("Ende Juni 2024.") == "2024-06-30"
    # Kombiniert in Klammern (durch Bracket-Strip in parse_iso_date rekursiv)
    assert parse_iso_date("[Mitte Juni 2024]") == "2024-06-15"


def test_parse_iso_date_relative_monat_jahresposition_ungueltig():
    """Ungueltige Monatsnamen / Jahre ausserhalb Bereich / fehlende Komponenten -> None."""
    # Ungueltige Monatsnamen fallen auf None (kein stiller Fallback auf
    # Standard-Monat, damit "Anfang Xyz 2024" nicht als "Anfang 2024" gelesen wird)
    assert parse_iso_date("Anfang Xyz 2024") is None
    assert parse_iso_date("Ende Foo 1985") is None
    # Jahr ausserhalb 1800-2999
    assert parse_iso_date("Anfang Juni 1700") is None
    assert parse_iso_date("Ende Juni 3000") is None
    # Fehlendes Jahr faellt zurueck auf uebrige Patterns (typischerweise None)
    assert parse_iso_date("Anfang Juni") is None
    # Nur Positions-Wort ohne Monat + Jahr -> None (spiegelt _RELATIVE_YEAR)
    assert parse_iso_date("Anfang") is None
    # Regression: bestehende _RELATIVE_YEAR-Form (Position + Jahr ohne Monat)
    # bleibt unveraendert
    assert parse_iso_date("Anfang 2024") == "2024-01-01"
    assert parse_iso_date("Ende 2024") == "2024-12-01"
    # Regression: bestehende _MONTH_YEAR-Form (Monatsname + Jahr ohne Position)
    # bleibt unveraendert
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    # Regression: bestehende _DAY_MONTH_YEAR-Form (Ziffer + Monatsname + Jahr)
    # bleibt unveraendert
    assert parse_iso_date("13. Juni 2024") == "2024-06-13"
    # Regression: Dekaden-Position "Anfang 1980er" ueber _RELATIVE_DECADE
    assert parse_iso_date("Anfang 1980er") == "1980-01-01"


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


def test_parse_iso_date_jahrzehnt_dativ_plural_substantiviert():
    """Dativ-Plural-Form der substantivierten Dekaden-Notation ('1980ern',
    'in den 1990ern') wird semantisch identisch zur Nominativ-Form ('1980er')
    auf den Dekaden-Anker gemappt.

    In praepositionalen Wendungen ist ``1980ern`` (Dativ-Plural des
    substantivierten Adjektivs ``die 1980er``) die uebliche DE-Kurzform
    ohne expliziten ``Jahre``-Trailer: ``in den 1980ern``, ``aus den
    1990ern``, ``seit den 2000ern``. Bisher fiel diese sehr verbreitete
    DE-Umgangs-/Print-Form still auf None, obwohl semantisch identisch
    zur langen Form ``1980er Jahren`` (die bereits ueber die ``jahre(?:n)?``-
    Klausel gemapped wird) und zur Nominativ-Form ``1980er``.

    Konvention: Dekaden-Start (spiegelt die uebrigen Formen). Grammatika-
    lisch ist ``1980ern`` die Dativ-Plural-Form des substantivierten Ad-
    jektivs mit dem Standard-Dativ-Plural-Suffix -n (Nominativ Plural
    -e -> Dativ Plural -en).
    """
    # Direkte substantivierte Dativ-Plural-Form
    assert parse_iso_date("1980ern") == "1980-01-01"
    assert parse_iso_date("1990ern") == "1990-01-01"
    assert parse_iso_date("2000ern") == "2000-01-01"
    # Case-insensitive
    assert parse_iso_date("1980ERN") == "1980-01-01"
    # Trenner-Varianten (symmetrisch zu 1980er / 1980-er / 1980 er)
    assert parse_iso_date("1980-ern") == "1980-01-01"
    assert parse_iso_date("1980 ern") == "1980-01-01"
    # In Kombination mit _TEMPORAL_PREFIX (Standard-praepositionale Wendung
    # "in den 1980ern" = Praeposition "in" + Artikel "den" + Dekade)
    assert parse_iso_date("in den 1980ern") == "1980-01-01"
    assert parse_iso_date("in den 1990ern") == "1990-01-01"
    # In Kombination mit DE-Adjektiv-Form (die spaeten 1990ern = die + Adjektiv
    # + Dativ-Plural-Substantiviert)
    assert parse_iso_date("die spaeten 1990ern") == "1999-01-01"
    assert parse_iso_date("die frühen 1980ern") == "1980-01-01"
    assert parse_iso_date("in den fruehen 1980ern") == "1980-01-01"
    # Mit Annaeherungspraefix (Verkettung ueber Rekursion)
    assert parse_iso_date("ca. 1980ern") == "1980-01-01"
    # Mit trailing Satzzeichen
    assert parse_iso_date("1980ern.") == "1980-01-01"
    # Ungueltige Formen: 2-stellige Kurzform bleibt mehrdeutig
    assert parse_iso_date("80ern") is None
    # Out-of-Range bleibt ausgeschlossen
    assert parse_iso_date("1700ern") is None
    assert parse_iso_date("3000ern") is None
    # Regression-Anker: Nominativ-Form ("1980er") und lange Form ("1980er
    # Jahren") bleiben unveraendert
    assert parse_iso_date("1980er") == "1980-01-01"
    assert parse_iso_date("1980er Jahren") == "1980-01-01"
    assert parse_iso_date("1980er Jahre") == "1980-01-01"


def test_parse_iso_date_jahrzehnt_hyphen_kompositum():
    """Hyphenierte Kompositum-Form der Dekaden-Notation ('1980er-Jahre',
    '1990er-Jahren') wird semantisch identisch zur getrennten Schreibweise
    ('1980er Jahre') auf den Dekaden-Anker gemappt.

    Duden erkennt neben der getrennten Standard-Form ``die 1980er Jahre``
    auch die Zusammenschreibung ``die 1980er-Jahre`` als offizielle
    alternative Notation an. In DE-Publikationen, Print-Katalogen und
    Sammler-Notizen sehr verbreitet (Wikipedia-Artikel typischer Musik-/
    Kultur-Themen der Dekade nutzen die Bindestrich-Form, ebenso viele
    Buch-Titel wie "Musik der 1980er-Jahre"). Bisher fiel diese
    orthografisch korrekte Kompositum-Form still auf None, obwohl
    semantisch identisch zur getrennten Form.

    Konvention: Dekaden-Start (spiegelt die uebrigen Formen). Beide
    Dekaden-Suffix-Varianten (DE ``er``/``ern`` und EN ``s``) und alle
    Trailer-Kasus-Varianten (Nominativ ``Jahre``, Dativ ``Jahren``)
    werden akzeptiert.
    """
    # Direkt hyphenierte Kompositum-Form (Duden-alternative Zusammenschreibung)
    assert parse_iso_date("1980er-Jahre") == "1980-01-01"
    assert parse_iso_date("1990er-Jahre") == "1990-01-01"
    assert parse_iso_date("2000er-Jahre") == "2000-01-01"
    # Dativ-Plural mit hyphenierter Kompositum-Form
    assert parse_iso_date("1980er-Jahren") == "1980-01-01"
    assert parse_iso_date("1990er-Jahren") == "1990-01-01"
    # Doppel-Bindestrich (Bindestrich vor er-Suffix UND vor Jahre-Trailer)
    assert parse_iso_date("1980-er-Jahre") == "1980-01-01"
    assert parse_iso_date("1990-er-Jahren") == "1990-01-01"
    # Case-insensitive
    assert parse_iso_date("1980ER-JAHRE") == "1980-01-01"
    assert parse_iso_date("1980er-jahre") == "1980-01-01"
    # In Kombination mit _TEMPORAL_PREFIX (Standard-praepositionale Wendung
    # "in den 1980er-Jahren" = Praeposition "in" + Artikel "den" + hyphenierte Dekade)
    assert parse_iso_date("in den 1980er-Jahren") == "1980-01-01"
    assert parse_iso_date("in den 1990er-Jahren") == "1990-01-01"
    assert parse_iso_date("aus den 2000er-Jahren") == "2000-01-01"
    # Mit Annaeherungspraefix (Verkettung ueber Rekursion)
    assert parse_iso_date("ca. 1980er-Jahre") == "1980-01-01"
    assert parse_iso_date("circa 1990er-Jahren") == "1990-01-01"
    # Mit trailing Satzzeichen
    assert parse_iso_date("1980er-Jahre.") == "1980-01-01"
    # Kombiniert mit DE-Adjektiv-Relativposition (frueh/spaet + hyphenierte Kompositum-Form)
    assert parse_iso_date("die fruehen 1980er-Jahre") == "1980-01-01"
    assert parse_iso_date("die spaeten 1990er-Jahren") == "1999-01-01"
    assert parse_iso_date("frueh 1980er-Jahre") is None  # Adjektiv-Endung obligatorisch
    # Kombiniert mit Anfang/Mitte/Ende + hyphenierte Kompositum-Form
    assert parse_iso_date("Anfang der 1980er-Jahre") == "1980-01-01"
    assert parse_iso_date("Mitte der 1990er-Jahre") == "1995-01-01"
    assert parse_iso_date("Ende der 2000er-Jahre") == "2009-01-01"
    # Kombiniert mit EN-Relativposition + hyphenierte Kompositum-Form (Mischform,
    # in bilingualen Sammlungs-Notizen vorkommend)
    assert parse_iso_date("mid-1990er-Jahre") == "1995-01-01"
    assert parse_iso_date("late 2000er-Jahren") == "2009-01-01"
    # Regression-Anker: getrennte Standard-Form und artikellose Nominativ-Form
    # bleiben unveraendert
    assert parse_iso_date("1980er Jahre") == "1980-01-01"
    assert parse_iso_date("1980er Jahren") == "1980-01-01"
    assert parse_iso_date("1980er") == "1980-01-01"
    assert parse_iso_date("1980-er") == "1980-01-01"
    # Out-of-Range bleibt ausgeschlossen
    assert parse_iso_date("1700er-Jahre") is None
    assert parse_iso_date("3000er-Jahre") is None


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


def test_parse_iso_date_jahrhundert_duden_abkuerzungen():
    """Duden-konforme Kurzformen ``Jhd.`` (ohne ``t``) und ``Jahrh.`` werden erkannt.

    Bisher fielen ``20. Jhd.`` und ``20. Jahrh.`` still auf None, weil die
    Alternierungs-Liste in :data:`_CENTURY_DE` nur die ``t``-Endungen
    (``jhdt``/``jhrdt``) und die reine Kurzform ``jh`` enthielt. ``Jhd.``
    und ``Jahrh.`` sind laut Duden gaengige Abkuerzungen von ``Jahrhundert``
    und finden sich in aelteren Museums-Etiketten, Auktionskatalogen und
    Provenienz-Vermerken; ohne Erkennung entstand silenter Funddatum-
    Datenverlust bei der Migration.
    """
    # Neue Kurzformen (Duden-konform)
    assert parse_iso_date("20. Jhd.") == "1900-01-01"
    assert parse_iso_date("20. Jhd") == "1900-01-01"
    assert parse_iso_date("19. Jhd.") == "1800-01-01"
    assert parse_iso_date("21. Jhd.") == "2000-01-01"
    assert parse_iso_date("20. Jahrh.") == "1900-01-01"
    assert parse_iso_date("19. Jahrh.") == "1800-01-01"
    assert parse_iso_date("21. Jahrh") == "2000-01-01"
    # Case-Insensitivitaet
    assert parse_iso_date("20. JHD.") == "1900-01-01"
    assert parse_iso_date("20. jhd.") == "1900-01-01"
    assert parse_iso_date("20. JAHRH.") == "1900-01-01"
    # Ohne Punkt vor der Zahl
    assert parse_iso_date("19Jhd.") == "1800-01-01"
    assert parse_iso_date("19Jahrh") == "1800-01-01"
    # Roemische Zahlen mit den neuen Kurzformen
    assert parse_iso_date("XIX. Jhd.") == "1800-01-01"
    assert parse_iso_date("XX. Jhd.") == "1900-01-01"
    assert parse_iso_date("XX. Jahrh.") == "1900-01-01"
    # Relative Position kombiniert mit neuen Kurzformen
    assert parse_iso_date("Anfang 20. Jhd.") == "1900-01-01"
    assert parse_iso_date("Mitte 19. Jhd.") == "1850-01-01"
    assert parse_iso_date("Ende 20. Jhd.") == "1999-01-01"
    assert parse_iso_date("Anfang 20. Jahrh.") == "1900-01-01"
    # Regress-Anker: bestehende Kurzformen bleiben unveraendert
    assert parse_iso_date("20. Jahrhundert") == "1900-01-01"
    assert parse_iso_date("20. Jhdt.") == "1900-01-01"
    assert parse_iso_date("20. Jh.") == "1900-01-01"
    assert parse_iso_date("20. Jhrd.") == "1900-01-01"
    assert parse_iso_date("20. Jhrdt.") == "1900-01-01"
    assert parse_iso_date("20. Jh") == "1900-01-01"


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


def test_parse_iso_date_jahrhundert_spanne():
    """Jahrhundert-Spanne ('19.-20. Jahrhundert', '19th to 20th century',
    'XIX.-XX. Jahrhundert') spiegelt _YEAR_RANGE / _DECADE_RANGE auf die
    Jahrhundert-Achse: Startjahr des linken Jahrhunderts als ISO-Datum,
    spiegelt die _CENTURY_*-Konvention ('19. Jahrhundert' -> '1800-01-01').

    In Museums-Etiketten und geerbten Sammlungs-Notizen sehr verbreitet, wenn
    der Vorbesitzer die Provenienz nur ungefaehr auf zwei aufeinanderfolgende
    Jahrhunderte einordnen konnte. Vor der Erweiterung fielen alle Formen
    still auf None (stiller Datenverlust auf typischer Provenienz-Notation).
    """
    # DE-Arabisch symbolischer Separator
    assert parse_iso_date("19.-20. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19. - 20. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19-20 Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19./20. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19.–20. Jahrhundert") == "1800-01-01"  # En-Dash
    assert parse_iso_date("19.—20. Jahrhundert") == "1800-01-01"  # Em-Dash
    assert parse_iso_date("19.−20. Jahrhundert") == "1800-01-01"  # U+2212 Minus
    # DE-Arabisch mit Duden-Kurzformen (jhdt/jh/jhrd)
    assert parse_iso_date("19.-20. Jhdt.") == "1800-01-01"
    assert parse_iso_date("19.-20. Jh.") == "1800-01-01"
    assert parse_iso_date("19.-20.Jhdt.") == "1800-01-01"
    # DE-Arabisch Wort-Separator (bis/to/till/until)
    assert parse_iso_date("19. bis 20. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19 bis 20 Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19 to 20 Jahrhundert") == "1800-01-01"
    # EN-Arabisch symbolischer Separator
    assert parse_iso_date("19th-20th century") == "1800-01-01"
    assert parse_iso_date("19-20 century") == "1800-01-01"
    assert parse_iso_date("19-20 c.") == "1800-01-01"
    assert parse_iso_date("19th - 20th century") == "1800-01-01"
    assert parse_iso_date("19th/20th century") == "1800-01-01"
    assert parse_iso_date("19th–20th century") == "1800-01-01"
    # EN-Arabisch Wort-Separator
    assert parse_iso_date("19th to 20th century") == "1800-01-01"
    assert parse_iso_date("19th till 20th century") == "1800-01-01"
    assert parse_iso_date("19th until 20th century") == "1800-01-01"
    # DE-Roemisch symbolisch und Wort
    assert parse_iso_date("XIX.-XX. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("XIX-XX Jhdt.") == "1800-01-01"
    assert parse_iso_date("XIX–XX Jahrhundert") == "1800-01-01"
    assert parse_iso_date("XIX. bis XX. Jhdt.") == "1800-01-01"
    # EN-Roemisch
    assert parse_iso_date("XIX-XX century") == "1800-01-01"
    assert parse_iso_date("XIX to XX century") == "1800-01-01"
    assert parse_iso_date("XIX.-XX. c.") == "1800-01-01"
    # Case-insensitiv (BIS/TO aus Caps-Lock-Notizen)
    assert parse_iso_date("19. BIS 20. JAHRHUNDERT") == "1800-01-01"
    assert parse_iso_date("19TH TO 20TH CENTURY") == "1800-01-01"
    # Inverted Spanne (Tippfehler) liefert linkes Jahrhundert
    assert parse_iso_date("20.-19. Jahrhundert") == "1900-01-01"
    assert parse_iso_date("XX.-XIX. Jhdt.") == "1900-01-01"
    # Kombinationen mit bestehenden Modifikatoren
    assert parse_iso_date("ca. 19.-20. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("(19.-20. Jahrhundert)") == "1800-01-01"
    assert parse_iso_date("[19.-20. Jahrhundert]") == "1800-01-01"
    assert parse_iso_date("19.-20. Jahrhundert.") == "1800-01-01"
    # Kombination mit _TEMPORAL_PREFIX ("aus dem 19.-20. Jahrhundert")
    assert parse_iso_date("aus dem 19.-20. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("im 19.-20. Jhdt.") == "1800-01-01"
    # Whitespace-Toleranz
    assert parse_iso_date("  19.  -  20.  Jahrhundert  ") == "1800-01-01"


def test_parse_iso_date_jahrhundert_spanne_ungueltig():
    """Jahrhundert-Zahlen ausserhalb des 1800-2999-Bandes, non-kanonische
    Roemisch-Tokens, fehlender Wort-Separator-Whitespace, oder fehlender
    Suffix -> None."""
    # 18. Jahrhundert (1700-1799) < 1800 - beide Enden unter Untergrenze
    assert parse_iso_date("17.-18. Jahrhundert") is None
    assert parse_iso_date("18.-19. Jahrhundert") is None
    assert parse_iso_date("XVII.-XVIII. Jhdt.") is None
    # 31. Jahrhundert (3000+) > 2999 - beide Enden ueber Obergrenze
    assert parse_iso_date("30.-31. Jahrhundert") is None
    assert parse_iso_date("19.-31. Jahrhundert") is None
    # Non-kanonische Roemisch-Tokens (nicht in _ROMAN_CENTURY_VALUES)
    assert parse_iso_date("IIII-XX Jahrhundert") is None
    assert parse_iso_date("XIX-XXXV Jahrhundert") is None
    # Ohne Whitespace um das Wort-Schluesselwort kein Match
    assert parse_iso_date("19bis20 Jahrhundert") is None
    assert parse_iso_date("19thto20th century") is None
    # Ohne Century-Suffix keine Range (waere sonst reines Jahres-Range)
    assert parse_iso_date("19.-20.") is None
    assert parse_iso_date("XIX.-XX.") is None
    # Bestehende Formen bleiben unveraendert (kein Regress)
    assert parse_iso_date("19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("20th century") == "1900-01-01"
    assert parse_iso_date("XIX. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("XX century") == "1900-01-01"
    # Relative Formen bleiben unveraendert
    assert parse_iso_date("Anfang 19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("Mitte XIX. Jhdt.") == "1850-01-01"
    # Dekaden-Spanne und Jahres-Spanne bleiben unveraendert
    assert parse_iso_date("1980er-1990er") == "1980-01-01"
    assert parse_iso_date("1950-1960") == "1950-01-01"


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


def test_parse_iso_date_relative_dekade_de_adjektiv_form():
    """DE-Adjektiv-Form der Dekaden-Position ('fruehe(n) 1980er',
    'spaete(n) 1990er Jahren') wird semantisch identisch zur Substantiv-Form
    ('Anfang 1980er', 'Ende 1990er') und zur EN-Form ('early 1980s',
    'late 1990s') auf den Dekaden-Anker gemappt.

    Sehr verbreitet in geerbten DE-Sammler-/Museums-Notizen, weil die
    Adjektiv-Form die grammatikalisch flektierte Standard-Notation innerhalb
    eines Satzes ist ("Fund aus den fruehen 1980er Jahren", "Nachlass aus
    spaeten 1990ern", "die spaete 2000er Sammlung"). Vor der Erweiterung
    fielen alle DE-Adjektiv-Formen still auf None, obwohl EN-Aequivalent
    (early/mid/late) und DE-Substantiv-Aequivalent (Anfang/Mitte/Ende)
    beide bereits auf denselben Dekaden-Anker abgebildet wurden.

    Konvention symmetrisch zur Substantiv-Form: fruehe → Jahr 0 der Dekade
    (spiegelt Anfang), spaete → Jahr 9 (spiegelt Ende). Alle 5 Kasus-
    Endungen der DE-Adjektiv-Deklination (-e/-em/-en/-er/-es) werden
    akzeptiert, damit Nominativ/Genitiv/Dativ/Akkusativ in beiden
    Deklinationsklassen (schwach mit Artikel, stark ohne Artikel) matchen.
    Umlaut-Form (früh/spät) und ASCII-transliterierte Form (frueh/spaet)
    beide praxisrelevant und symmetrisch akzeptiert.
    """
    # Umlaut-Form (früh/spät): Standard-DE-Print-/Excel-Notation
    assert parse_iso_date("frühe 1980er") == "1980-01-01"
    assert parse_iso_date("frühen 1980er") == "1980-01-01"
    assert parse_iso_date("frühes 1980er") == "1980-01-01"
    assert parse_iso_date("späte 1990er") == "1999-01-01"
    assert parse_iso_date("späten 1990er") == "1999-01-01"
    # ASCII-transliterierte Form (frueh/spaet): geerbte 7-bit-Notizen /
    # Terminal-Tools ohne Umlaut-Support
    assert parse_iso_date("fruehe 1980er") == "1980-01-01"
    assert parse_iso_date("fruehen 1980er") == "1980-01-01"
    assert parse_iso_date("spaete 1990er") == "1999-01-01"
    assert parse_iso_date("spaeten 1990er") == "1999-01-01"
    # Mit "Jahre"/"Jahren"-Trailer (Standard-Print-Form in vollstaendigen Saetzen)
    assert parse_iso_date("frühe 1980er Jahre") == "1980-01-01"
    assert parse_iso_date("frühen 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("spaeten 1990er Jahren") == "1999-01-01"
    assert parse_iso_date("fruehen 2000er Jahre") == "2000-01-01"
    # Mit Leading-Artikel (Nominativ/Akkusativ Plural: "die spaeten 1990er",
    # Genitiv Plural: "der fruehen 1980er Jahre", Dativ Plural: "den fruehen
    # 1980er Jahren"). Der Artikel steht direkt am Anfang ohne Praeposition.
    assert parse_iso_date("die frühen 1980er") == "1980-01-01"
    assert parse_iso_date("die spaeten 1990er") == "1999-01-01"
    assert parse_iso_date("der frühen 1980er Jahre") == "1980-01-01"
    assert parse_iso_date("die fruehen 2000er Jahre") == "2000-01-01"
    # In Kombination mit _TEMPORAL_PREFIX ("in den", "von den") wird die
    # Praeposition + Artikel zuerst gestrippt, bevor die Adjektiv-Form
    # gematcht wird.
    assert parse_iso_date("in den frühen 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("von den fruehen 2000er Jahren") == "2000-01-01"
    # Case-insensitive (Titel-Case, Grosschreibung als Satz-Anfang)
    assert parse_iso_date("Frühe 1980er") == "1980-01-01"
    assert parse_iso_date("FRÜHE 1980ER") == "1980-01-01"
    assert parse_iso_date("SPAETE 1990ER") == "1999-01-01"
    # Kombination mit Annaeherungspraefix (Verkettung ueber Rekursion)
    assert parse_iso_date("ca. frühe 1980er") == "1980-01-01"
    assert parse_iso_date("circa spaete 1990er Jahre") == "1999-01-01"
    # Kombination mit umschliessenden Klammern
    assert parse_iso_date("(frühe 1980er)") == "1980-01-01"
    assert parse_iso_date("(die spaeten 1990er Jahre)") == "1999-01-01"


def test_parse_iso_date_relative_dekade_de_adjektiv_form_ungueltig():
    """DE-Adjektiv-Form ohne Kasus-Endung (nur Wurzel ``frueh``/``spaet``)
    oder mit unbekanntem Adjektiv (``mittel``, ``jung``, ``alt``) faellt auf None.

    Sicherheits-Anker gegen ueberdehnbaren Match: nur die grammatikalisch
    korrekte Adjektiv-Form (Wurzel + Kasus-Endung) matcht, damit die Wurzel
    allein (``frueh 1980er``) und semantisch aehnliche, aber nicht in den
    Position-Offset-Kanon einsortierbare Adjektive (``mittel``, ``jung``,
    ``alt``) nicht kuenstlich auf einen Dekaden-Anker abgebildet werden.
    """
    # Reine Wurzel ohne Adjektiv-Endung (grammatikalisch inkorrekt)
    assert parse_iso_date("frueh 1980er") is None
    assert parse_iso_date("spaet 1990er") is None
    assert parse_iso_date("früh 1980er") is None
    assert parse_iso_date("spät 1990er") is None
    # Unbekannte Adjektive (kein Offset-Mapping in der Position-Achse)
    assert parse_iso_date("mittlere 1980er") is None
    assert parse_iso_date("junge 1990er") is None
    assert parse_iso_date("alte 1980er") is None
    # Kombination mit ungueltiger Dekade (out-of-range) faellt weiterhin auf None
    assert parse_iso_date("frühe 1700er") is None
    assert parse_iso_date("spaete 3000er") is None
    # Regression-Anker: Substantiv-Form (Anfang/Ende) bleibt unveraendert
    assert parse_iso_date("Anfang 1980er") == "1980-01-01"
    assert parse_iso_date("Ende 1990er") == "1999-01-01"
    # Regression-Anker: EN-Form (early/late) bleibt unveraendert
    assert parse_iso_date("early 1980s") == "1980-01-01"
    assert parse_iso_date("late 1990s") == "1999-01-01"


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


def test_parse_iso_date_range_word_through_thru():
    """Englische Range-Trenner "through" (formal) und "thru" (colloquial) auf
    allen drei Range-Achsen (Mehrjahres-Spanne, Monat-Range, Tages-Range).

    "Through" ist der US-Standard-Range-Ausdruck ("Monday through Friday",
    "1950 through 1960", "June through July") und in amerikanischen
    Auktions-Katalogen, Mineral-Society-Publikationen und Sammler-Notizen
    aus US-Quellen verbreitet. "Thru" ist die alltagssprachliche Kurzform,
    typisch in Foto-Captions, Social-Media-Postings und informellen Feld-
    Tagebuechern. Bisher fielen alle Formen still auf None, weil die
    :data:`_YEAR_RANGE_WORD`-, :data:`_MONTH_RANGE_YEAR`- und
    :data:`_DAY_RANGE_MONTH_YEAR`-Alternanten nur ``bis|to|till|until``
    enthielten - aus einer typischen US-Sammler-Notiz "collected June
    through July 2020 in Arizona" wurde silenter Funddatum-Datenverlust
    bei der Migration."""
    # Mehrjahres-Spanne mit through
    assert parse_iso_date("1950 through 1960") == "1950-01-01"
    assert parse_iso_date("1985 through 1990") == "1985-01-01"
    assert parse_iso_date("2000 through 2024") == "2000-01-01"
    # Mehrjahres-Spanne mit thru (colloquial)
    assert parse_iso_date("1950 thru 1960") == "1950-01-01"
    assert parse_iso_date("1985 thru 1990") == "1985-01-01"
    # Monat-Range mit through
    assert parse_iso_date("June through July 2024") == "2024-06-01"
    assert parse_iso_date("Juni through Juli 2024") == "2024-06-01"
    assert parse_iso_date("March through April 2020") == "2020-03-01"
    # Monat-Range mit thru
    assert parse_iso_date("June thru July 2024") == "2024-06-01"
    assert parse_iso_date("Mar thru Apr 2020") == "2020-03-01"
    # Tages-Range innerhalb Monat mit through
    assert parse_iso_date("5 through 7 June 2024") == "2024-06-05"
    assert parse_iso_date("5th through 7th June 2024") == "2024-06-05"
    assert parse_iso_date("1 through 15 March 2020") == "2020-03-01"
    # Tages-Range mit thru
    assert parse_iso_date("5 thru 7 June 2024") == "2024-06-05"
    assert parse_iso_date("5th thru 7th June 2024") == "2024-06-05"
    # Case-Insensitivitaet (Caps-Lock aus Excel-Auto-Fill / Header-Notation)
    assert parse_iso_date("1950 THROUGH 1960") == "1950-01-01"
    assert parse_iso_date("June THROUGH July 2024") == "2024-06-01"
    assert parse_iso_date("June Through July 2024") == "2024-06-01"
    assert parse_iso_date("June THRU July 2024") == "2024-06-01"
    # Kombination mit Annaeherungspraefix
    assert parse_iso_date("ca. 1950 through 1960") == "1950-01-01"
    assert parse_iso_date("approx. June through July 2024") == "2024-06-01"
    # Regress-Anker: bestehende Range-Trenner bleiben unveraendert
    assert parse_iso_date("1950 bis 1960") == "1950-01-01"
    assert parse_iso_date("1950 to 1960") == "1950-01-01"
    assert parse_iso_date("1950 till 1960") == "1950-01-01"
    assert parse_iso_date("1950 until 1960") == "1950-01-01"
    assert parse_iso_date("June to July 2024") == "2024-06-01"
    assert parse_iso_date("5th to 7th June 2024") == "2024-06-05"
    # Regress: symbolische Trenner (Bindestrich/en-dash) bleiben
    assert parse_iso_date("1950-1960") == "1950-01-01"
    assert parse_iso_date("Juni-Juli 2024") == "2024-06-01"
    # Grenzfaelle: Jahr ausserhalb Range
    assert parse_iso_date("1700 through 1960") is None
    # Ohne Whitespace um das Schluesselwort kein Match (Satzform-Prinzip)
    assert parse_iso_date("1950through1960") is None


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


def test_parse_iso_date_zwischen_wrapper_generisch():
    """'zwischen X und Y' / 'between X and Y' als generischer Range-Wrapper.

    Vor dem Fix erkannte :data:`_YEAR_RANGE_BETWEEN` nur die reine Jahres-
    Spanne (``zwischen 1985 und 1990``). Alle uebrigen Range-Inhalte fielen
    still auf None:

    - ``zwischen Juni und Juli 2024`` (Monat-Spanne, aufgeloest via
      :data:`_MONTH_RANGE_YEAR`)
    - ``zwischen 13. und 15. Juni 2024`` (Tages-Spanne in einem Monat,
      aufgeloest via :data:`_DAY_RANGE_MONTH_YEAR`)
    - ``between June and July 2024`` (EN-Variante, Monat-Spanne)
    - ``zwischen 1980er und 1990er`` (Dekaden-Spanne, aufgeloest via
      :data:`_DECADE_RANGE`)
    - ``zwischen Sommer und Herbst 2024`` (Saison-Spanne, aufgeloest via
      :data:`_SEASON_RANGE`)
    - ``zwischen 19. und 20. Jahrhundert`` (Jahrhundert-Spanne, aufgeloest
      via :data:`_CENTURY_RANGE_DE`)

    Der :data:`_BETWEEN_AND_WRAPPER`-Preprocessor normalisiert die Wrapper-
    Form auf ``X - Y`` und ruft :func:`parse_iso_date` rekursiv auf, sodass
    alle bestehenden Range-Patterns transparent greifen. Startjahr/Start-
    Monat/Start-Tag der linken Range-Seite als ISO-Datum (Konvention aus
    :data:`_YEAR_RANGE` / :data:`_MONTH_RANGE_YEAR` / etc.).
    """
    # Monat-Spanne im gleichen Jahr (via _MONTH_RANGE_YEAR)
    assert parse_iso_date("zwischen Juni und Juli 2024") == "2024-06-01"
    assert parse_iso_date("zwischen Mai und August 1985") == "1985-05-01"
    assert parse_iso_date("between June and July 2024") == "2024-06-01"
    assert parse_iso_date("between May and August 1985") == "1985-05-01"
    # Tages-Spanne innerhalb eines Monats (via _DAY_RANGE_MONTH_YEAR)
    assert parse_iso_date("zwischen 13. und 15. Juni 2024") == "2024-06-13"
    assert parse_iso_date("zwischen 5. und 7. Oktober 2023") == "2023-10-05"
    assert parse_iso_date("between 5 and 7 June 2024") == "2024-06-05"
    # Dekaden-Spanne (via _DECADE_RANGE)
    assert parse_iso_date("zwischen 1980er und 1990er") == "1980-01-01"
    assert parse_iso_date("between 1950s and 1970s") == "1950-01-01"
    # Saison-Spanne (via _SEASON_RANGE)
    assert parse_iso_date("zwischen Sommer und Herbst 2024") == "2024-06-01"
    assert parse_iso_date("between spring and summer 2020") == "2020-03-01"
    # Jahrhundert-Spanne (via _CENTURY_RANGE_DE / _CENTURY_RANGE_EN)
    assert parse_iso_date("zwischen 19. und 20. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("between 19th and 20th century") == "1800-01-01"
    # Kombination mit Praefixen ueber Rekursion
    assert parse_iso_date("ca. zwischen Juni und Juli 2024") == "2024-06-01"
    assert parse_iso_date("circa between June and July 2024") == "2024-06-01"
    assert parse_iso_date("(zwischen Juni und Juli 2024)") == "2024-06-01"
    # Case-Insensitivitaet
    assert parse_iso_date("ZWISCHEN JUNI UND JULI 2024") == "2024-06-01"
    assert parse_iso_date("BETWEEN JUNE AND JULY 2024") == "2024-06-01"
    # Whitespace-Toleranz
    assert parse_iso_date("  zwischen  Juni  und  Juli  2024  ") == "2024-06-01"
    # Regress: reine Jahres-Spanne bleibt unveraendert (redundant zu
    # _YEAR_RANGE_BETWEEN, das nachgelagert dieselbe Semantik liefert)
    assert parse_iso_date("zwischen 1985 und 1990") == "1985-01-01"
    assert parse_iso_date("between 1950 and 1960") == "1950-01-01"
    # Regress: Nicht-Range-Formen mit 'und' irgendwo im Text (nicht als
    # Wrapper) fallen weiterhin auf None
    assert parse_iso_date("zwischen den 1980er Jahren und heute") is None
    assert parse_iso_date("Foobar und Baz 2024") is None
    # Kein Match: fehlender Range-Inhalt links oder rechts der Konjunktion
    assert parse_iso_date("zwischen  und Juli 2024") is None
    # Kein Match: unbekannter Monat/Saison/Jahrhundert auf einer/beiden Seiten
    assert parse_iso_date("zwischen Junk und Juli 2024") is None
    assert parse_iso_date("zwischen Juni und Junk 2024") is None
    assert parse_iso_date("zwischen Sonner und Herbst 2024") is None


def test_parse_iso_date_dekaden_spanne():
    """Dekaden-Spanne ('1980er-1990er', '1980s to 1990s') spiegelt _YEAR_RANGE /
    _YEAR_RANGE_WORD auf die Dekaden-Achse: Startjahr der linken Dekade als
    ISO-Datum, spiegelt die _DECADE-Konvention ('1980er' -> '1980-01-01').

    In geerbten Sammler-/Museums-Notizen sehr verbreitet, wenn der Vorbesitzer
    den Erwerbs-/Fund-Zeitraum nur ungefaehr auf zwei aufeinanderfolgende
    Dekaden datieren konnte ('Erwerb 1980er-1990er', 'Sammlungsaufbau 1980s
    to 2000s'). Vor der Erweiterung fielen alle Formen still auf None (kein
    stiller Datenverlust auf typischer Erbschafts-/Import-Notation).
    """
    # Symbolischer Separator (ASCII-Bindestrich als Basisform)
    assert parse_iso_date("1980er-1990er") == "1980-01-01"
    assert parse_iso_date("1980s-1990s") == "1980-01-01"
    # Symbolische Separator-Varianten spiegeln _YEAR_RANGE-Klasse
    assert parse_iso_date("1980er - 1990er") == "1980-01-01"
    assert parse_iso_date("1980er–1990er") == "1980-01-01"   # En-Dash
    assert parse_iso_date("1980er—1990er") == "1980-01-01"   # Em-Dash
    assert parse_iso_date("1980er−1990er") == "1980-01-01"   # U+2212 Minus
    assert parse_iso_date("1980er/1990er") == "1980-01-01"
    assert parse_iso_date("1980er / 1990er") == "1980-01-01"
    # Wort-Separator (DE bis / EN to/till/until) spiegelt _YEAR_RANGE_WORD
    assert parse_iso_date("1980er bis 1990er") == "1980-01-01"
    assert parse_iso_date("1980s to 1990s") == "1980-01-01"
    assert parse_iso_date("1980s till 1990s") == "1980-01-01"
    assert parse_iso_date("1980s until 1990s") == "1980-01-01"
    # Case-insensitiv (BIS/TO aus Caps-Lock-Notizen)
    assert parse_iso_date("1980ER-1990ER") == "1980-01-01"
    assert parse_iso_date("1980S TO 1990S") == "1980-01-01"
    # Gemischte DE-/EN-Suffixe (in Sammler-Notizen kommen DE/EN vor)
    assert parse_iso_date("1980er-1990s") == "1980-01-01"
    assert parse_iso_date("1980s bis 1990er") == "1980-01-01"
    # Dativ-Plural-Substantiviert (spiegelt _DECADE-Alternante 'ern')
    assert parse_iso_date("1980ern-1990ern") == "1980-01-01"
    assert parse_iso_date("1980ern bis 1990ern") == "1980-01-01"
    # Mit Jahre-Trailer (Nominativ und Dativ-Plural)
    assert parse_iso_date("1980er Jahre - 1990er Jahre") == "1980-01-01"
    assert parse_iso_date("1980er Jahren bis 1990er Jahren") == "1980-01-01"
    # Duden-Kompositum (hyphenierter Trailer)
    assert parse_iso_date("1980er-Jahre - 1990er-Jahre") == "1980-01-01"
    # Inverted Spanne (Tippfehler) liefert die linke Dekade, spiegelt _YEAR_RANGE
    assert parse_iso_date("1990er-1980er") == "1990-01-01"
    # Kombinationen mit bestehenden Modifikatoren (ca./Klammern/Trailing-Punkt)
    assert parse_iso_date("ca. 1980er-1990er") == "1980-01-01"
    assert parse_iso_date("circa 1980s to 1990s") == "1980-01-01"
    assert parse_iso_date("(1980er-1990er)") == "1980-01-01"
    assert parse_iso_date("[1980er-1990er]") == "1980-01-01"
    assert parse_iso_date("1980er-1990er.") == "1980-01-01"
    # Kombination mit _TEMPORAL_PREFIX (Standard-praepositionale Wendung
    # "in den 1980er-1990er Jahren" = Praeposition "in" + Artikel "den" +
    # Dekaden-Spanne + Trailer)
    assert parse_iso_date("in den 1980er-1990er Jahren") == "1980-01-01"
    # Whitespace-Toleranz
    assert parse_iso_date("  1980er - 1990er  ") == "1980-01-01"


def test_parse_iso_date_dekaden_spanne_ungueltig():
    """Jahr ausserhalb [1800, 2999] oder fehlender Wort-Separator-Whitespace → None."""
    # Beide Dekaden muessen im gueltigen Bereich sein
    assert parse_iso_date("1700er-1900er") is None
    assert parse_iso_date("1980er-3000er") is None
    assert parse_iso_date("1500er-1600er") is None
    # Zweistellige Kurzform bleibt mehrdeutig (spiegelt _DECADE)
    assert parse_iso_date("80er-90er") is None
    assert parse_iso_date("80s-90s") is None
    # Fehlender Suffix auf einer Seite kein Match (waere sonst _YEAR_RANGE)
    assert parse_iso_date("1980-1990er") is None
    assert parse_iso_date("1980er-1990") is None
    # Ohne Whitespace um das Wort-Schluesselwort kein Match (lebt von Satzform)
    assert parse_iso_date("1980erbis1990er") is None
    assert parse_iso_date("1980sto1990s") is None
    # Unbekanntes Schluesselwort
    assert parse_iso_date("1980er oder 1990er") is None
    # Bestehende Formen bleiben unveraendert (kein Regress)
    assert parse_iso_date("1980er") == "1980-01-01"        # Dekade
    assert parse_iso_date("1980er-Jahre") == "1980-01-01"  # Kompositum
    assert parse_iso_date("1950-1960") == "1950-01-01"     # Jahres-Spanne
    assert parse_iso_date("1950 bis 1960") == "1950-01-01" # Jahres-Wort-Spanne
    assert parse_iso_date("1980") == "1980-01-01"          # Einzeljahr


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


def test_parse_iso_date_quartal_halbjahr_englische_ordinal_suffixe():
    """Englische Ordinal-Suffix-Form ('1st|2nd|3rd|4th quarter YYYY',
    '1st|2nd half-year YYYY') als symmetrische Ergaenzung zur deutschen
    Digit-Punkt-Form ('1. Quartal YYYY'). Die EN-Form ist die Standard-
    Notation in EN-sprachigen Auktions-Katalogen, Mineral-Boersen-Berichten
    und Sammler-Blogs; sie fiel zuvor still auf None und wurde damit in
    der Sammler-Statistik nicht zeitlich verortet."""
    # Year-Last Quartal-Langform mit EN-Ordinal-Suffix
    assert parse_iso_date("1st quarter 2024") == "2024-01-01"
    assert parse_iso_date("2nd quarter 2024") == "2024-04-01"
    assert parse_iso_date("3rd quarter 1985") == "1985-07-01"
    assert parse_iso_date("4th quarter 1999") == "1999-10-01"
    # Case-insensitiv (mixed-case ist in Katalog-Titeln typisch)
    assert parse_iso_date("1st Quarter 2024") == "2024-01-01"
    assert parse_iso_date("4TH QUARTER 2024") == "2024-10-01"
    # Year-First Quartal-Langform mit EN-Ordinal-Suffix
    assert parse_iso_date("2024 1st quarter") == "2024-01-01"
    assert parse_iso_date("2024-3rd Quarter") == "2024-07-01"
    assert parse_iso_date("2024,4th Quarter") == "2024-10-01"
    assert parse_iso_date("1985.2nd Quarter") == "1985-04-01"
    # Year-Last Halbjahr-Langform mit EN-Ordinal-Suffix (Compound half-year)
    assert parse_iso_date("1st half-year 2024") == "2024-01-01"
    assert parse_iso_date("2nd half-year 2024") == "2024-07-01"
    assert parse_iso_date("1st halfyear 2024") == "2024-01-01"
    assert parse_iso_date("2nd halfyear 1985") == "1985-07-01"
    # Year-First Halbjahr-Langform mit EN-Ordinal-Suffix
    assert parse_iso_date("2024 1st half-year") == "2024-01-01"
    assert parse_iso_date("2024-2nd Halfyear") == "2024-07-01"
    # Mit Annaeherungspraefix / trailing Satzzeichen
    assert parse_iso_date("ca. 1st Quarter 2024") == "2024-01-01"
    assert parse_iso_date("(2nd Quarter 2024)") == "2024-04-01"
    assert parse_iso_date("3rd Quarter 2024.") == "2024-07-01"
    # Kombination mit Praepositions-Alternante (von/of) - EN-Ordinal-Suffix
    # in Prosa mit "of"-Verbindung wie in Katalog-Fliesstext ("1st Quarter
    # of 2020 Zermatt-Bergtour")
    assert parse_iso_date("1st Quarter of 2020") == "2020-01-01"
    assert parse_iso_date("3rd Quarter of 2019") == "2019-07-01"
    assert parse_iso_date("2nd half-year of 2024") == "2024-07-01"
    # Kombination Ziffer + Punkt bleibt erlaubt (der bestehende DE-Marker)
    assert parse_iso_date("1. Quartal 2024") == "2024-01-01"
    assert parse_iso_date("2024 1. Quartal") == "2024-01-01"
    # Semantisch-schiefe Kombinationen bleiben tolerant (kein Positions-Zwang
    # [1-4]->{st,nd,rd,th}) - konsistent zur ohnehin lenient formulierten
    # Klasse; OCR-/Autocorrect-Artefakte werden nicht verworfen.
    assert parse_iso_date("1th quarter 2024") == "2024-01-01"
    assert parse_iso_date("2st quarter 2024") == "2024-04-01"
    # Q-Kurzform + H-Kurzform unveraendert (kein Regress in Nachbar-Patterns)
    assert parse_iso_date("Q1 2024") == "2024-01-01"
    assert parse_iso_date("Q4 2024") == "2024-10-01"
    assert parse_iso_date("H1 2024") == "2024-01-01"
    assert parse_iso_date("H2 2024") == "2024-07-01"
    # DE-Langform (Digit-Punkt und Wort-vor-Zahl) bleibt unveraendert
    assert parse_iso_date("3. Quartal 1985") == "1985-07-01"
    assert parse_iso_date("Quartal 4 1999") == "1999-10-01"
    assert parse_iso_date("Halbjahr 2 1999") == "1999-07-01"
    # Jahr ausserhalb Spanne / ungueltige Zahl → None
    assert parse_iso_date("5th quarter 2024") is None
    assert parse_iso_date("3rd half-year 2024") is None
    assert parse_iso_date("1st quarter 1700") is None
    assert parse_iso_date("1st quarter 3000") is None
    # EN-Ordinal-Suffix ohne Quartal-/Halbjahr-Keyword darf nicht fangen
    assert parse_iso_date("1st 2024") is None


def test_parse_iso_date_jahreszeiten_ungueltig():
    assert parse_iso_date("Sommer 1700") is None    # ausserhalb 1800-2999
    assert parse_iso_date("Foosaison 2020") is None  # kein bekannter Saison-Name
    assert parse_iso_date("Spring") is None          # Jahreszeit ohne Jahr


def test_parse_iso_date_saison_spanne():
    """Saison-Spanne ('Sommer bis Herbst 2024', 'summer to fall 2024',
    'Fruehjahr-Sommer 2024') spiegelt _YEAR_RANGE / _DECADE_RANGE /
    _CENTURY_RANGE_* auf die Saison-Achse: linke Saison als Anker, ihr
    meteorologischer Startmonat plus Jahres-Zahl auf den 1. gesetzt.

    In Sammler-Notizen, Feld-Tagebuechern und Foto-Captions verbreitet, wenn
    der Fund oder die Sammel-Aktivitaet ueber mehrere Saisons desselben
    Jahres lief. Vor der Erweiterung fielen alle Formen still auf None.
    """
    # DE symbolischer Separator
    assert parse_iso_date("Sommer-Herbst 2024") == "2024-06-01"
    assert parse_iso_date("Sommer - Herbst 2024") == "2024-06-01"
    assert parse_iso_date("Sommer/Herbst 2024") == "2024-06-01"
    assert parse_iso_date("Sommer–Herbst 2024") == "2024-06-01"  # En-Dash
    assert parse_iso_date("Sommer—Herbst 2024") == "2024-06-01"  # Em-Dash
    assert parse_iso_date("Sommer−Herbst 2024") == "2024-06-01"  # U+2212 Minus
    # DE Wort-Separator
    assert parse_iso_date("Sommer bis Herbst 2024") == "2024-06-01"
    assert parse_iso_date("Fruehjahr bis Sommer 2024") == "2024-03-01"
    assert parse_iso_date("Frühjahr bis Herbst 2024") == "2024-03-01"
    assert parse_iso_date("Frühling bis Herbst 2024") == "2024-03-01"
    # EN symbolisch und Wort
    assert parse_iso_date("summer-fall 2024") == "2024-06-01"
    assert parse_iso_date("summer-autumn 2024") == "2024-06-01"
    assert parse_iso_date("spring/summer 2024") == "2024-03-01"
    assert parse_iso_date("summer to fall 2024") == "2024-06-01"
    assert parse_iso_date("spring to summer 2024") == "2024-03-01"
    assert parse_iso_date("summer till autumn 2024") == "2024-06-01"
    assert parse_iso_date("spring until autumn 2024") == "2024-03-01"
    # Case-insensitiv (Caps-Lock-Notizen, Excel-Auto-Fill)
    assert parse_iso_date("SOMMER BIS HERBST 2024") == "2024-06-01"
    assert parse_iso_date("Summer To Fall 2024") == "2024-06-01"
    # ASCII-transliterierte Umlaute (ae/oe/ue)
    assert parse_iso_date("Fruehjahr bis Sommer 2024") == "2024-03-01"
    assert parse_iso_date("Fruehling-Herbst 2024") == "2024-03-01"
    # Kompositum-Formen (Frueh<X>/Spaet<X> / early<X>/late<X>)
    assert parse_iso_date("Fruehsommer-Spaetherbst 2024") == "2024-06-01"
    assert parse_iso_date("Spaetfruehjahr bis Fruehherbst 2024") == "2024-05-01"
    assert parse_iso_date("earlysummer to lateautumn 2024") == "2024-06-01"
    # Winter als linke Saison bleibt am Dezember haengen (dokumentiert)
    assert parse_iso_date("Winter-Fruehling 2024") == "2024-12-01"
    assert parse_iso_date("winter to spring 2024") == "2024-12-01"
    # Inverted Spanne (Tippfehler) liefert die linke Saison
    assert parse_iso_date("Herbst bis Sommer 2024") == "2024-09-01"
    assert parse_iso_date("autumn to summer 2024") == "2024-09-01"
    # Kombinationen mit bestehenden Modifikatoren
    assert parse_iso_date("ca. Sommer-Herbst 2024") == "2024-06-01"
    assert parse_iso_date("(Sommer-Herbst 2024)") == "2024-06-01"
    assert parse_iso_date("[Sommer-Herbst 2024]") == "2024-06-01"
    assert parse_iso_date("Sommer-Herbst 2024.") == "2024-06-01"
    # Kombination mit _TEMPORAL_PREFIX ('im Sommer-Herbst 2024')
    assert parse_iso_date("im Sommer-Herbst 2024") == "2024-06-01"
    assert parse_iso_date("aus dem Sommer-Herbst 2024") == "2024-06-01"
    # Whitespace-Toleranz
    assert parse_iso_date("  Sommer - Herbst  2024  ") == "2024-06-01"


def test_parse_iso_date_saison_spanne_ungueltig():
    """Unbekannte Saison-Namen, fehlender Jahres-Anker, Out-of-Range Jahr,
    fehlender Wort-Separator-Whitespace -> None."""
    # Kein Saison-Name (Freitext auf einer Seite)
    assert parse_iso_date("Foo bis Bar 2024") is None
    assert parse_iso_date("Sommer bis Foo 2024") is None
    assert parse_iso_date("Foo bis Sommer 2024") is None
    # Nur ein Wort (fehlende rechte Saison)
    assert parse_iso_date("Sommer bis 2024") is None
    # Jahr ausserhalb [1800, 2999]
    assert parse_iso_date("Sommer bis Herbst 1500") is None
    assert parse_iso_date("Sommer bis Herbst 3000") is None
    # Ohne Whitespace um das Wort-Schluesselwort kein Match
    assert parse_iso_date("Sommerbis Herbst 2024") is None
    assert parse_iso_date("summerto fall 2024") is None
    # Fehlendes Jahr
    assert parse_iso_date("Sommer bis Herbst") is None
    # Bestehende Saison-Formen bleiben unveraendert (kein Regress)
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("Winter 2023/24") == "2023-12-01"
    assert parse_iso_date("Winter 2023") == "2023-12-01"
    assert parse_iso_date("2024 Sommer") == "2024-06-01"
    # Monat-Range bleibt unveraendert (Fall-Through nutzt Monatsnamen-Zweig)
    assert parse_iso_date("Juni-Juli 2024") == "2024-06-01"
    # Einzelmonat / Feiertag unveraendert
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("Weihnachten 2023") == "2023-12-25"


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


def test_parse_iso_date_temporale_praeposition_herkunft_und_zeitspanne():
    """Herkunfts-Praeposition ``aus`` (DE) und Zeitspannen-Praeposition
    ``waehrend``/``während`` (DE) / ``during`` (EN) vor dem Datum werden
    gestrippt.

    Spiegelt das ``im/in/am/vom/von/on``-Konzept auf die Herkunfts- und
    Zeitspannen-Achse; die Praeposition ist Satz-Gluekel, keine Datums-
    Modifikation - das ISO-Datum-Output ist identisch zur reinen Form.
    In geerbten Sammler-/Museums-Notizen die haeufigste DE-Provenienz-
    /Zeitspannen-Formulierung ("Stueck aus dem Jahr 1985", "aus den 1980ern",
    "aus dem 19. Jahrhundert", "waehrend des Jahres 1985 gefunden",
    "during the 1985 expedition"). Bisher fielen alle Formen mit diesen
    Praepositionen still auf None, obwohl die Datums-Bedeutung selbst
    identisch zur reinen Form ist.
    """
    # DE "aus" + Jahr
    assert parse_iso_date("aus 1985") == "1985-01-01"
    assert parse_iso_date("Aus 1985") == "1985-01-01"
    # DE "aus dem Jahr" - klassische Provenienz-Formulierung
    assert parse_iso_date("aus dem Jahr 1985") == "1985-01-01"
    assert parse_iso_date("Aus dem Jahr 1985") == "1985-01-01"
    assert parse_iso_date("aus dem Jahre 1985") == "1985-01-01"
    # DE "aus des Jahres" (Genitiv, formeller Museums-Katalog-Stil)
    assert parse_iso_date("aus des Jahres 1985") == "1985-01-01"
    # DE "aus den Jahren" (Plural fuer Range-Notation)
    assert parse_iso_date("aus den Jahren 1985-1990") == "1985-01-01"
    # DE "aus" + Dekaden-Notation (Standard-praepositionale Wendung)
    assert parse_iso_date("aus den 1980ern") == "1980-01-01"
    assert parse_iso_date("aus den 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("aus den 1990er Jahren") == "1990-01-01"
    # DE "aus" + Jahrhundert
    assert parse_iso_date("aus dem 19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("aus dem 20. Jhdt.") == "1900-01-01"
    # DE "aus" + DE-Adjektiv-Form der Dekaden-Position (Verkettung)
    assert parse_iso_date("aus den fruehen 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("aus der spaeten 1990er") == "1999-01-01"
    # DE "aus" + Monat + Jahr
    assert parse_iso_date("aus dem Juni 2024") == "2024-06-01"
    # DE "waehrend" (ASCII-transliteriert) + Jahr
    assert parse_iso_date("waehrend 1985") == "1985-01-01"
    assert parse_iso_date("Waehrend 1985") == "1985-01-01"
    # DE "während" (Umlaut) + Jahr
    assert parse_iso_date("während 1985") == "1985-01-01"
    assert parse_iso_date("Während 1985") == "1985-01-01"
    # DE "waehrend des Jahres" - klassische Zeitspannen-Formulierung
    assert parse_iso_date("waehrend des Jahres 1985") == "1985-01-01"
    assert parse_iso_date("während des Jahres 1985") == "1985-01-01"
    # DE "waehrend der 1980er Jahre" (Genitiv-Rektion)
    assert parse_iso_date("waehrend der 1980er Jahre") == "1980-01-01"
    assert parse_iso_date("während der 1990er Jahre") == "1990-01-01"
    # EN "during" + Jahr
    assert parse_iso_date("during 1985") == "1985-01-01"
    assert parse_iso_date("During 1985") == "1985-01-01"
    # EN "during the" + Jahrzehnt
    assert parse_iso_date("during the 1980s") == "1980-01-01"
    assert parse_iso_date("during the 1990s") == "1990-01-01"
    # EN "during the year"
    assert parse_iso_date("during the year 1985") == "1985-01-01"
    # Case-insensitive (DE/EN gemischt)
    assert parse_iso_date("AUS DEM JAHR 1985") == "1985-01-01"
    assert parse_iso_date("WAEHREND 1985") == "1985-01-01"
    assert parse_iso_date("DURING 1985") == "1985-01-01"
    # Verkettete Praefixe (rekursive Strippung)
    assert parse_iso_date("aus ca. 1985") == "1985-01-01"
    assert parse_iso_date("waehrend ca. 1985") == "1985-01-01"
    # Wortanfang muss exakt sein - kein Anschneiden laengerer Worte
    # ("ausgehend", "ausbruch", "auslaufend" beginnen mit "aus", aber ohne
    # Whitespace-Trenner zum naechsten Wort matcht das Pattern nicht)
    assert parse_iso_date("ausgehend von 1985") is None
    assert parse_iso_date("auslaufend 1985") is None
    assert parse_iso_date("ausbruchsjahr 1985") is None
    # ("waehrenddessen", "duringtime" wuerden analog nicht matchen; aber
    # da diese Woerter unueblich sind, hier nur die realistischen)
    # Praefix ohne Inhalt / mit ungueltigem Rest → None
    assert parse_iso_date("aus") is None
    assert parse_iso_date("waehrend") is None
    assert parse_iso_date("during") is None
    assert parse_iso_date("aus abc") is None
    # Praefix vor Jahr ausserhalb 1800-2999 → None
    assert parse_iso_date("aus 1700") is None
    assert parse_iso_date("aus dem Jahr 1700") is None
    assert parse_iso_date("during 1700") is None
    # Bestehende Praepositionen ohne aus/waehrend/during bleiben unveraendert
    # (Regression-Anker)
    assert parse_iso_date("im Sommer 1985") == "1985-06-01"
    assert parse_iso_date("vom 13.06.2024") == "2024-06-13"
    assert parse_iso_date("on June 13, 2024") == "2024-06-13"
    assert parse_iso_date("von 1985") == "1985-01-01"
    assert parse_iso_date("Jahr 1985") == "1985-01-01"


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


def test_parse_iso_date_boundary_praefix_spaetestens_fruehestens():
    """DE-Adverb-Formen ``spaetestens``/``spätestens`` und ``fruehestens``/``frühestens``.

    Spiegelt das ``vor``/``nach``-Verhalten auf die semantisch identischen DE-
    Adverb-Formen: ``spätestens 1985`` ist die weiche Obergrenze ("das Jahr
    ist das spaeteste Datum", semantisch == ``vor 1985``), ``frühestens 1985``
    die weiche Untergrenze (semantisch == ``nach 1985``). Verbreitet in
    Sammler-Notizen zu Grenz-Datierungen. Deckt Umlaut- und ae/ue-Trans-
    literation ab (Encoding-Robustheit fuer ASCII-only-Tools und Legacy-CSV).
    """
    # DE Umlaut-Standardform
    assert parse_iso_date("spätestens 1985") == "1985-01-01"
    assert parse_iso_date("frühestens 1985") == "1985-01-01"
    # ae/ue-Transliteration (ASCII-only-Fallback)
    assert parse_iso_date("spaetestens 1985") == "1985-01-01"
    assert parse_iso_date("fruehestens 1985") == "1985-01-01"
    # Case-insensitive (Etiketten in Grossbuchstaben, Satzanfang mit Grossbuchstabe)
    assert parse_iso_date("Spätestens 1985") == "1985-01-01"
    assert parse_iso_date("FRÜHESTENS 1985") == "1985-01-01"
    assert parse_iso_date("SPAETESTENS 2024") == "2024-01-01"
    assert parse_iso_date("Fruehestens 2024") == "2024-01-01"
    # Adverb-Praefix + alle Datums-Untertypen (rekursiv, spiegelt vor/nach)
    assert parse_iso_date("spätestens Juni 2024") == "2024-06-01"
    assert parse_iso_date("frühestens 13.06.2024") == "2024-06-13"
    assert parse_iso_date("spätestens 1980er") == "1980-01-01"
    assert parse_iso_date("frühestens Sommer 1985") == "1985-06-01"
    assert parse_iso_date("spaetestens 2024-06-13") == "2024-06-13"
    # Bindestrich-Variante symmetrisch zu pre-/post-Formen
    assert parse_iso_date("spätestens-1985") == "1985-01-01"
    assert parse_iso_date("frühestens-2024") == "2024-01-01"
    # Verkettung mit anderen Praefixen (rekursive Strippung)
    assert parse_iso_date("spätestens ca. 1985") == "1985-01-01"
    assert parse_iso_date("ca. spätestens 1985") == "1985-01-01"
    assert parse_iso_date("frühestens circa Juni 2024") == "2024-06-01"
    # Adverb + temporale Praeposition (semantisch redundant, unschaedlich)
    assert parse_iso_date("spätestens im Juni 2024") == "2024-06-01"
    assert parse_iso_date("frühestens im Jahr 1985") == "1985-01-01"
    # Praefix ohne Inhalt / mit ungueltigem Rest → None
    assert parse_iso_date("spätestens") is None
    assert parse_iso_date("frühestens") is None
    assert parse_iso_date("spätestens abc") is None
    # Praefix vor Jahr ausserhalb 1800-2999 → None
    assert parse_iso_date("spätestens 1700") is None
    assert parse_iso_date("frühestens 3000") is None
    # Wortende-Zwang: kein Anschneiden laengerer Worte, kein direktes Anhaengen
    assert parse_iso_date("spätestenswolke 1985") is None
    assert parse_iso_date("spätestensvor 1985") is None
    assert parse_iso_date("fruehestensx 1985") is None
    # Regression-Anker: bestehende Boundary-Praefixe bleiben unveraendert
    assert parse_iso_date("vor 1985") == "1985-01-01"
    assert parse_iso_date("nach 1985") == "1985-01-01"
    assert parse_iso_date("before 1985") == "1985-01-01"
    assert parse_iso_date("pre-1985") == "1985-01-01"


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


def test_parse_iso_date_range_praefix_mit_artikel_und_jahr_wort():
    """Range-Praefix (ab/seit/bis/from/since/until/till) + optionaler Artikel
    + optionales Jahr-Wort werden gestrippt.

    Spiegelt das _TEMPORAL_PREFIX-Konzept (Praeposition + Artikel + Jahr-Wort
    als reines Satz-Gluekel) auf die unidirektionalen Spannen-Marker. Sehr
    verbreitet in geerbten Sammler-/Museums-Notizen mit vollstaendigem
    Satzbau ("Sammlung seit dem Jahr 1985", "Fundort ab dem 1980er Jahren",
    "Sammlung since the year 1985", "from the 1980s"). Bisher fielen alle
    Formen mit Artikel-Zwischenwort still auf None, obwohl semantisch
    identisch zur artikellosen Form ("seit 1985") - das Jahr ist der
    bekannte Anker, der Artikel-Zwischen-Teil ist reines grammatikalisches
    Gluekel.
    """
    # DE "seit/ab/bis" + Artikel + Jahr-Wort + Jahr (klassische Genitiv-/
    # Dativ-Rektion in Museums-Katalog-Vermerken)
    assert parse_iso_date("seit dem Jahr 1985") == "1985-01-01"
    assert parse_iso_date("ab dem Jahr 1985") == "1985-01-01"
    assert parse_iso_date("bis dem Jahr 1985") == "1985-01-01"
    # DE "seit/ab" + Artikel + Dekaden-Notation (mit Adjektiv-/Substantiv-Form)
    assert parse_iso_date("seit den 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("seit den 1980ern") == "1980-01-01"
    assert parse_iso_date("ab den 1980ern") == "1980-01-01"
    assert parse_iso_date("bis den 1990ern") == "1990-01-01"
    # DE "seit" + Genitiv-Artikel (formeller Museums-Katalog-Stil)
    assert parse_iso_date("seit des Jahres 1985") == "1985-01-01"
    # DE Kombination mit Adjektiv-Form der Dekaden-Position (Verkettung)
    assert parse_iso_date("seit den fruehen 1980er Jahren") == "1980-01-01"
    assert parse_iso_date("ab den spaeten 1990ern") == "1999-01-01"
    # EN "since/from/until/till" + Artikel + Jahr-Wort + Jahr
    assert parse_iso_date("since the year 1985") == "1985-01-01"
    assert parse_iso_date("from the year 1985") == "1985-01-01"
    assert parse_iso_date("until the year 1985") == "1985-01-01"
    # EN "since/from/until" + Artikel + Jahrzehnt
    assert parse_iso_date("since the 1980s") == "1980-01-01"
    assert parse_iso_date("from the 1980s") == "1980-01-01"
    assert parse_iso_date("until the 1990s") == "1990-01-01"
    assert parse_iso_date("till the 1990s") == "1990-01-01"
    # Case-insensitive
    assert parse_iso_date("SEIT DEM JAHR 1985") == "1985-01-01"
    assert parse_iso_date("SINCE THE YEAR 1985") == "1985-01-01"
    # Praefix + Artikel ohne gueltigen Datums-Rest → None (Wort statt Jahr)
    assert parse_iso_date("seit dem Fund 1985") is None
    assert parse_iso_date("ab dem Katalog 1985") is None
    # Regression-Anker: artikellose Formen bleiben unveraendert
    assert parse_iso_date("seit 1985") == "1985-01-01"
    assert parse_iso_date("ab 1985") == "1985-01-01"
    assert parse_iso_date("bis 1985") == "1985-01-01"
    assert parse_iso_date("from 1985") == "1985-01-01"
    assert parse_iso_date("since 1985") == "1985-01-01"
    assert parse_iso_date("until 1985") == "1985-01-01"
    # Regression-Anker: "1985 bis 1990" (bis als Range-Trenner) bleibt
    # unveraendert - der ^-Anker in _RANGE_PREFIX schliesst Kollision mit
    # _YEAR_RANGE_WORD aus
    assert parse_iso_date("1985 bis 1990") == "1985-01-01"


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


def test_parse_iso_date_trailing_aera_marker_uz_vuz():
    """DDR-/moderne konfessionsneutrale Aera-Notation "u. Z." / "v. u. Z."
    wird als trailing Aera-Marker abgestrippt, spiegelt CE/BCE-Semantik.

    Standard-Konvention der DDR-Fachliteratur (Akademie-Publikationen bis
    1990) und in der modernen sekulaeren DE-Wissenschaftssprache verbreitet,
    wo die christlich-konfessionelle n. Chr./v. Chr.-Notation durch die
    neutrale Aera-Angabe ersetzt wird. Vor dem Fix fielen alle Formen stille
    auf None, obwohl semantisch identisch zur bereits unterstuetzten
    CE/BCE- und n. Chr./v. Chr.-Notation.
    """
    # u. Z. Kurzform (unserer Zeitrechnung, CE-Aequivalent)
    assert parse_iso_date("1985 u. Z.") == "1985-01-01"
    assert parse_iso_date("1985 u.Z.") == "1985-01-01"
    assert parse_iso_date("1985 u Z") == "1985-01-01"
    assert parse_iso_date("1985 uZ") == "1985-01-01"
    assert parse_iso_date("1985 u. z.") == "1985-01-01"
    # u. Z. Vollform (unserer Zeitrechnung)
    assert parse_iso_date("1985 unserer Zeitrechnung") == "1985-01-01"
    # v. u. Z. Kurzform (vor unserer Zeitrechnung, BCE-Aequivalent).
    # Wird wie CE-Aequivalent gelesen; Range-Pruefung filtert Werte < 1800
    # transparent auf None (spiegelt "500 BCE" -> None ohne Aera-Marker).
    assert parse_iso_date("1985 v. u. Z.") == "1985-01-01"
    assert parse_iso_date("1985 v.u.Z.") == "1985-01-01"
    assert parse_iso_date("1985 v u Z") == "1985-01-01"
    assert parse_iso_date("1985 vuZ") == "1985-01-01"
    # v. u. Z. Vollform (vor unserer Zeitrechnung)
    assert parse_iso_date("1985 vor unserer Zeitrechnung") == "1985-01-01"
    # BCE-Aequivalent-Verhalten: Jahre < 1800 fallen auf None (Range-Pruefung)
    assert parse_iso_date("500 v. u. Z.") is None
    assert parse_iso_date("500 v.u.Z.") is None
    assert parse_iso_date("500 vor unserer Zeitrechnung") is None
    # Case-insensitive (Etiketten in verschiedenen Schreibungen)
    assert parse_iso_date("1985 U. Z.") == "1985-01-01"
    assert parse_iso_date("1985 V. U. Z.") == "1985-01-01"
    assert parse_iso_date("1985 U.Z.") == "1985-01-01"
    # Kombiniert mit vollstaendigem Datum (Tag + Monat + Jahr + Marker)
    assert parse_iso_date("13.06.2024 u. Z.") == "2024-06-13"
    assert parse_iso_date("2024-06-13 u.Z.") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024 unserer Zeitrechnung") == "2024-06-13"
    # Kombiniert mit Jahrhundert-Notation (Arabisch und Roemisch)
    assert parse_iso_date("19. Jahrhundert u. Z.") == "1800-01-01"
    assert parse_iso_date("XIX. Jahrhundert u. Z.") == "1800-01-01"
    # Reihenfolge-Anker: v. u. Z. muss VOR u. Z. alterniert werden. Sonst
    # wuerde u. Z. nur den "u. Z."-Anteil konsumieren und "v." als trailing
    # zurueck lassen, was nach _TRAILING_PUNCT-Strip zu "1985 v" fuehrt.
    assert parse_iso_date("1985 v. u. Z.") == "1985-01-01"
    # Reine Aera-Markierung ohne Datum bleibt None
    assert parse_iso_date("u. Z.") is None
    assert parse_iso_date("v. u. Z.") is None
    assert parse_iso_date("unserer Zeitrechnung") is None
    # Nicht-Aera-Suffix darf NICHT als u. Z.-Marker gedeutet werden (kein
    # Regress: das u/z-Pattern darf nur mit Punkt-/Whitespace-Trennung
    # matchen, nicht als Teil eines Wortes)
    assert parse_iso_date("1985 uZahn") is None
    assert parse_iso_date("1985 zeitrechnung") is None
    # Bestehende Aera-Marker bleiben unveraendert (kein Regress zu n. Chr./AD/CE)
    assert parse_iso_date("1985 n. Chr.") == "1985-01-01"
    assert parse_iso_date("1985 AD") == "1985-01-01"
    assert parse_iso_date("1985 CE") == "1985-01-01"
    assert parse_iso_date("500 v. Chr.") is None
    assert parse_iso_date("500 BCE") is None


def test_parse_iso_date_anno_domini():
    """Lateinische Vollform ``Anno Domini`` wird als Aera-Marker abgestrippt,
    spiegelt die AD/A.D.-Semantik auf die museal-latinisierte Vollform.

    Anno Domini (deutsch: "im Jahr des Herrn") ist die ursprungliche
    kirchen-lateinische Notation, aus der die verbreitete Kurzform
    ``AD``/``A.D.`` hervorgegangen ist. In geerbten Sammlungen mit
    museal-ecclesialer Provenienz (Reliquiare, Kloster-Bestaende,
    Grabinschriften-Fotografie-Sammlungen, historisch-archaeologische
    Publikationen aus dem 18./19. Jhdt. mit puristischer Latein-
    Konvention) sowie in modernen kalligrafisch-formalen Etiketten
    (Sonderausstellungen, "In Memoriam"-Karten mit Fund-/Erwerbsdatum)
    taucht die Vollform statt der Kurzform auf. Vor dem Fix fielen alle
    Vollform-Etiketten stille auf None, obwohl semantisch identisch zur
    bereits unterstuetzten Kurzform "AD 1985" / "1985 AD". Konzept
    identisch zu :func:`test_parse_iso_date_leading_aera_marker` /
    :func:`test_parse_iso_date_trailing_aera_marker`: Strip + Rekursion,
    das ISO-Datum-Output ist identisch zur reinen Form.
    """
    # Leading-Form (Anno Domini vor dem Datum)
    assert parse_iso_date("Anno Domini 1985") == "1985-01-01"
    assert parse_iso_date("Anno Domini 2024") == "2024-01-01"
    assert parse_iso_date("Anno Domini 13.06.2024") == "2024-06-13"
    assert parse_iso_date("Anno Domini 2024-06-13") == "2024-06-13"
    assert parse_iso_date("Anno Domini 13. Juni 2024") == "2024-06-13"
    # Trailing-Form (Anno Domini nach dem Datum)
    assert parse_iso_date("1985 Anno Domini") == "1985-01-01"
    assert parse_iso_date("2024 Anno Domini") == "2024-01-01"
    assert parse_iso_date("13.06.2024 Anno Domini") == "2024-06-13"
    assert parse_iso_date("2024-06-13 Anno Domini") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024 Anno Domini") == "2024-06-13"
    # Case-Insensitivitaet (Etiketten in klein/GROSS/Mixed)
    assert parse_iso_date("anno domini 1985") == "1985-01-01"
    assert parse_iso_date("ANNO DOMINI 1985") == "1985-01-01"
    assert parse_iso_date("Anno domini 1985") == "1985-01-01"
    assert parse_iso_date("aNnO dOmInI 1985") == "1985-01-01"
    assert parse_iso_date("1985 anno domini") == "1985-01-01"
    assert parse_iso_date("1985 ANNO DOMINI") == "1985-01-01"
    # Whitespace-Toleranz zwischen anno und domini (Doppel-Space aus Excel-
    # Auto-Fill, Tab-Trenner aus TSV-Export)
    assert parse_iso_date("Anno  Domini 1985") == "1985-01-01"
    assert parse_iso_date("Anno\tDomini 1985") == "1985-01-01"
    assert parse_iso_date("1985 Anno  Domini") == "1985-01-01"
    # Kombiniert mit Jahrhundert-Notation (Arabisch und Roemisch)
    assert parse_iso_date("Anno Domini 19. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("Anno Domini 19th century") == "1800-01-01"
    assert parse_iso_date("Anno Domini XIX. Jahrhundert") == "1800-01-01"
    assert parse_iso_date("19. Jahrhundert Anno Domini") == "1800-01-01"
    # Kombiniert mit Annaeherungs-Praefix ("ca. Anno Domini 1985"), Rekursion
    # loest zuerst ca. auf, dann Anno Domini
    assert parse_iso_date("ca. Anno Domini 1985") == "1985-01-01"
    assert parse_iso_date("circa Anno Domini 1985") == "1985-01-01"
    # Redundante Kombination Leading + Trailing (semantisch doppelt, aber
    # praktisch in ueberformatierten Etiketten moeglich): Rekursion loest
    # beide Achsen auf.
    assert parse_iso_date("Anno Domini 1985 AD") == "1985-01-01"
    assert parse_iso_date("AD 1985 Anno Domini") == "1985-01-01"
    # Bestehende Kurzform-Marker bleiben unveraendert (kein Regress zu AD/A.D.)
    assert parse_iso_date("1985 AD") == "1985-01-01"
    assert parse_iso_date("AD 1985") == "1985-01-01"
    assert parse_iso_date("1985 A.D.") == "1985-01-01"
    assert parse_iso_date("A.D. 1985") == "1985-01-01"
    # Bestehende Formen ohne Aera-Marker bleiben unveraendert
    assert parse_iso_date("1985") == "1985-01-01"
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    # Reine Aera-Markierung ohne Datum bleibt None (kein Freitext-Ratespiel)
    assert parse_iso_date("Anno Domini") is None
    assert parse_iso_date("anno domini") is None
    # Bare Anno ohne Domini ist KEIN Aera-Marker (semantisch reines "im Jahr");
    # bleibt derzeit None, weil weder :data:`_TEMPORAL_PREFIX` noch
    # :data:`_LEADING_ERA_MARKER` das Wort einzeln kennt. Kein Regress zu
    # den vorhandenen Aera-Markern.
    assert parse_iso_date("Anno 1985") is None
    assert parse_iso_date("1985 Anno") is None
    # Domini allein ohne Anno ist KEIN Aera-Marker
    assert parse_iso_date("Domini 1985") is None
    assert parse_iso_date("1985 Domini") is None
    # Non-Marker-Suffix darf NICHT als Anno-Domini gedeutet werden
    assert parse_iso_date("1985 Anno Museum") is None
    assert parse_iso_date("1985 Anno-Fund") is None


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


def test_parse_iso_date_kw_langform_und_englisch():
    """Langform-KW-Notation (Kalenderwoche/Woche) und englisches CW/calendar week.

    Erweitert die reine KW-Kurzform um die drei praxisrelevanten Langform-
    Alternativen: DE-Langform ``Kalenderwoche``, DE-Kurzform ohne Kalender-
    Praefix ``Woche``, und EN-Kurzform ``CW`` (calendar week) samt EN-
    Langform ``calendar week`` (mit/ohne Whitespace). Mapping identisch zur
    Kurzform (Montag der genannten Woche).
    """
    # DE-Langform "Kalenderwoche"
    assert parse_iso_date("Kalenderwoche 25 2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 25/2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 25, 2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche25/2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 1 2024") == "2024-01-01"
    # DE-Kurzform "Woche"
    assert parse_iso_date("Woche 25 2024") == "2024-06-17"
    assert parse_iso_date("Woche 25/2024") == "2024-06-17"
    assert parse_iso_date("Woche25 2024") == "2024-06-17"
    # EN-Kurzform "CW"
    assert parse_iso_date("CW 25 2024") == "2024-06-17"
    assert parse_iso_date("CW25/2024") == "2024-06-17"
    assert parse_iso_date("CW 25, 2024") == "2024-06-17"
    # EN-Langform "calendar week" mit/ohne Whitespace
    assert parse_iso_date("calendar week 25 2024") == "2024-06-17"
    assert parse_iso_date("calendarweek 25 2024") == "2024-06-17"
    assert parse_iso_date("calendar week 1 2024") == "2024-01-01"
    # Case-Insensitivitaet
    assert parse_iso_date("KALENDERWOCHE 25 2024") == "2024-06-17"
    assert parse_iso_date("kalenderwoche 25 2024") == "2024-06-17"
    assert parse_iso_date("cw 25 2024") == "2024-06-17"
    assert parse_iso_date("CALENDAR WEEK 25 2024") == "2024-06-17"
    # Kombiniert mit Annaeherungspraefix / Klammern
    assert parse_iso_date("ca. Kalenderwoche 25 2024") == "2024-06-17"
    assert parse_iso_date("[Woche 25 2024]") == "2024-06-17"
    assert parse_iso_date("(CW 25 2024)") == "2024-06-17"
    # Ungueltig (nicht-existente Woche / Jahr ausserhalb / Woche ohne Jahr)
    assert parse_iso_date("Kalenderwoche 0 2024") is None
    assert parse_iso_date("Woche 54 2024") is None
    assert parse_iso_date("CW 25 1700") is None
    assert parse_iso_date("Kalenderwoche 53 2024") is None
    assert parse_iso_date("Kalenderwoche 25") is None
    assert parse_iso_date("Woche 25") is None
    assert parse_iso_date("CW 25") is None
    # Kein Match: kein Whitespace/Trenner zwischen Wort und Jahr
    assert parse_iso_date("Kalenderwoche2024") is None
    # Regress-Anker: Basis-KW und ISO-Woche unveraendert
    assert parse_iso_date("KW 25 2024") == "2024-06-17"
    assert parse_iso_date("2024-W25") == "2024-06-17"


def test_parse_iso_date_kw_year_first():
    """Year-first KW-Notation ('2024 KW 25', '2024/KW25', '2024-Kalenderwoche 25').

    Symmetrisch zur Year-Last-Form _KW_YEAR - in Sammlungs-Tagebuechern und
    Excel-Auto-Fill mit dem Jahr als sortierendem Praefix ueblich. Mapping
    identisch (Montag der genannten Woche).
    """
    # Alle KW-Marker in Year-First-Reihenfolge
    assert parse_iso_date("2024 KW 25") == "2024-06-17"
    assert parse_iso_date("2024/KW25") == "2024-06-17"
    assert parse_iso_date("2024-KW25") == "2024-06-17"
    assert parse_iso_date("2024, KW 25") == "2024-06-17"
    assert parse_iso_date("2024 Kalenderwoche 25") == "2024-06-17"
    assert parse_iso_date("2024/Kalenderwoche 25") == "2024-06-17"
    assert parse_iso_date("2024 Woche 25") == "2024-06-17"
    assert parse_iso_date("2024 CW 25") == "2024-06-17"
    assert parse_iso_date("2024/CW25") == "2024-06-17"
    assert parse_iso_date("2024 calendar week 25") == "2024-06-17"
    assert parse_iso_date("2024 calendarweek 25") == "2024-06-17"
    # Case-Insensitivitaet
    assert parse_iso_date("2024 kw 25") == "2024-06-17"
    assert parse_iso_date("2024 KALENDERWOCHE 25") == "2024-06-17"
    # Erste Woche (Grenzfall)
    assert parse_iso_date("2024 KW 1") == "2024-01-01"
    assert parse_iso_date("2024 Woche 1") == "2024-01-01"
    # Kombiniert mit Annaeherungspraefix / Klammern
    assert parse_iso_date("ca. 2024 KW 25") == "2024-06-17"
    assert parse_iso_date("[2024 Kalenderwoche 25]") == "2024-06-17"
    # Ungueltig (Woche ausser Bereich / Jahr ausserhalb)
    assert parse_iso_date("2024 KW 0") is None
    assert parse_iso_date("2024 KW 54") is None
    assert parse_iso_date("1700 KW 25") is None
    assert parse_iso_date("2024 KW 53") is None  # 2024 hat nur 52 Wochen
    # Regress-Anker: Basis-Year-Last-Formen unveraendert
    assert parse_iso_date("KW 25 2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 25 2024") == "2024-06-17"


def test_parse_iso_date_kw_praeposition_von_of():
    """KW-Notation mit Wort-Praeposition ``von`` (DE) / ``of`` (EN) zwischen
    Wochen-Zahl und Jahr: ``KW 25 von 2024`` / ``week 25 of 2024``.

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[/.\\-, ]`` von :data:`_KW_YEAR`
    um die Wort-Praepositions-Trenner ``von`` (DE) und ``of`` (EN). In
    Prosa-Etiketten und Sammler-Notizen die uebliche natuerlichsprachige
    Verbindungs-Form zwischen Wochen-Nummer und Jahr ("Fund KW 25 von 2024
    im Aaregebiet", "Bergtour week 40 of 2019 Tucson-Boerse"). Mapping
    identisch zur Ein-Zeichen-Separator-Form (Montag der genannten Woche).
    Beide Praepositionen verlangen Whitespace auf beiden Seiten, sodass
    Kompositum-Formen (``vondel``, ``vonof``, ``von2024``) und angehaengte
    Formen (``KW 25von 2024``) unangetastet auf None fallen.
    """
    # DE-Praeposition ``von`` mit allen KW-Marker-Alternativen
    assert parse_iso_date("KW 25 von 2024") == "2024-06-17"
    assert parse_iso_date("KW25 von 2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 25 von 2024") == "2024-06-17"
    assert parse_iso_date("Woche 25 von 2024") == "2024-06-17"
    assert parse_iso_date("W25 von 2024") == "2024-06-17"
    assert parse_iso_date("W 25 von 2024") == "2024-06-17"
    # EN-Praeposition ``of`` mit allen KW-Marker-Alternativen
    assert parse_iso_date("KW 25 of 2024") == "2024-06-17"
    assert parse_iso_date("CW 25 of 2024") == "2024-06-17"
    assert parse_iso_date("CW25 of 2024") == "2024-06-17"
    assert parse_iso_date("calendar week 25 of 2024") == "2024-06-17"
    assert parse_iso_date("calendarweek 25 of 2024") == "2024-06-17"
    assert parse_iso_date("W25 of 2024") == "2024-06-17"
    # Case-Insensitivitaet (spiegelt die uebrigen Marker-Alternativen)
    assert parse_iso_date("KW 25 VON 2024") == "2024-06-17"
    assert parse_iso_date("kw 25 of 2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 25 VON 2024") == "2024-06-17"
    assert parse_iso_date("CW 25 OF 2024") == "2024-06-17"
    # Erste Woche (Grenzfall)
    assert parse_iso_date("KW 1 von 2024") == "2024-01-01"
    assert parse_iso_date("week 1 of 2024") is None  # kein reines 'week' als Marker
    assert parse_iso_date("CW 1 of 2024") == "2024-01-01"
    # Kombiniert mit Annaeherungspraefix / Klammern
    assert parse_iso_date("ca. KW 25 von 2024") == "2024-06-17"
    assert parse_iso_date("[Kalenderwoche 25 of 2024]") == "2024-06-17"
    # Kein Match: Whitespace auf beiden Seiten der Praeposition obligatorisch
    assert parse_iso_date("KW 25von 2024") is None
    assert parse_iso_date("KW 25 von2024") is None
    assert parse_iso_date("KW25vonof2024") is None
    # Kein Match: Kompositum-Formen (vondel/vonof) mit Praeposition-Praefix
    assert parse_iso_date("KW 25 vondel 2024") is None
    assert parse_iso_date("KW 25 vonof 2024") is None
    # Kein Match: andere DE-Praepositionen bleiben unangetastet (bewusst
    # eng gefasste Alternante, nur ``von``/``of`` supported).
    assert parse_iso_date("KW 25 vor 2024") is None
    assert parse_iso_date("KW 25 nach 2024") is None
    assert parse_iso_date("KW 25 im 2024") is None
    # Kein Match: EN-``of`` mit falscher Fortsetzung (kein 4-Ziffer-Jahr)
    assert parse_iso_date("KW 25 of course 2024") is None
    # Ungueltig (Jahr / Woche ausserhalb)
    assert parse_iso_date("KW 0 von 2024") is None
    assert parse_iso_date("KW 54 von 2024") is None
    assert parse_iso_date("KW 25 von 1700") is None
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert.
    assert parse_iso_date("KW 25 2024") == "2024-06-17"
    assert parse_iso_date("KW25/2024") == "2024-06-17"
    assert parse_iso_date("KW 25, 2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 25/2024") == "2024-06-17"


def test_parse_iso_date_monat_praeposition_von_of():
    """Monatsname-Notation mit Wort-Praeposition ``von`` (DE) / ``of`` (EN)
    zwischen Monatsname und Jahr: ``Juli von 2024`` / ``January of 2024``.

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[,./ \\-]`` von :data:`_MONTH_YEAR`
    um die Wort-Praepositions-Alternante ``\\s+(?:von|of)\\s+``. Spiegelt die
    identische Erweiterung in :data:`_KW_YEAR` (Wochen-Achse, Commit
    bc67cc7) auf die Monatsname-Achse: in Prosa-Etiketten und Sammler-Fund-
    Tagebuechern ist die Praepositions-Form die uebliche natuerlichsprachige
    Verbindung zwischen Monat und Jahr ("Fund Juli von 2024 im Aaregebiet",
    "Bergtour January of 2020 Zermatt"). Mapping identisch zur Ein-Zeichen-
    Separator-Form (erster Tag des Monats).
    """
    # DE-Praeposition ``von`` mit voller / abgekuerzter DE-Monatsform
    assert parse_iso_date("Januar von 2024") == "2024-01-01"
    assert parse_iso_date("Juli von 2024") == "2024-07-01"
    assert parse_iso_date("Dezember von 1985") == "1985-12-01"
    assert parse_iso_date("Jun von 2024") == "2024-06-01"
    assert parse_iso_date("Jun. von 2024") == "2024-06-01"
    # EN-Praeposition ``of`` mit voller / abgekuerzter EN-Monatsform
    assert parse_iso_date("January of 2024") == "2024-01-01"
    assert parse_iso_date("July of 2024") == "2024-07-01"
    assert parse_iso_date("December of 1985") == "1985-12-01"
    assert parse_iso_date("June of 2024") == "2024-06-01"
    assert parse_iso_date("Jun of 2024") == "2024-06-01"
    assert parse_iso_date("Jun. of 2024") == "2024-06-01"
    # Case-Insensitivitaet (Excel-Auto-Fill / Uppercase-Titel)
    assert parse_iso_date("JULI VON 2024") == "2024-07-01"
    assert parse_iso_date("january of 2024") == "2024-01-01"
    assert parse_iso_date("JULY OF 2024") == "2024-07-01"
    # Kombiniert mit Annaeherungspraefix / Klammern
    assert parse_iso_date("ca. Juli von 2024") == "2024-07-01"
    assert parse_iso_date("[January of 2024]") == "2024-01-01"
    # Kein Match: Whitespace auf beiden Seiten der Praeposition obligatorisch
    assert parse_iso_date("Julivon 2024") is None
    assert parse_iso_date("Juli von2024") is None
    # Kein Match: Kompositum-Formen
    assert parse_iso_date("Juli vondel 2024") is None
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert.
    assert parse_iso_date("Januar 2024") == "2024-01-01"
    assert parse_iso_date("Juli, 2024") == "2024-07-01"
    assert parse_iso_date("July 2024") == "2024-07-01"
    assert parse_iso_date("Jun.2024") == "2024-06-01"
    assert parse_iso_date("Juni/2024") == "2024-06-01"
    assert parse_iso_date("Juni-2024") == "2024-06-01"


def test_parse_iso_date_saison_praeposition_von_of():
    """Jahreszeit-Notation mit Wort-Praeposition ``von`` (DE) / ``of`` (EN)
    zwischen Saison-Wort und Jahr: ``Sommer von 2024`` / ``summer of 2024``.

    Spiegelt die identische Erweiterung in :data:`_KW_YEAR` (Wochen-Achse)
    und :data:`_MONTH_YEAR` (Monatsname-Achse) auf die Saison-Achse.
    Mapping identisch zur Ein-Zeichen-Separator-Form (meteorologischer
    Saison-Startmonat gemaess :data:`_SEASON_MONTHS`).
    """
    # DE-Saisons mit ``von``-Praeposition
    assert parse_iso_date("Frühling von 2024") == "2024-03-01"
    assert parse_iso_date("Frühjahr von 2024") == "2024-03-01"
    assert parse_iso_date("Sommer von 2024") == "2024-06-01"
    assert parse_iso_date("Herbst von 1999") == "1999-09-01"
    assert parse_iso_date("Winter von 1985") == "1985-12-01"
    # EN-Saisons mit ``of``-Praeposition
    assert parse_iso_date("spring of 2024") == "2024-03-01"
    assert parse_iso_date("summer of 2024") == "2024-06-01"
    assert parse_iso_date("autumn of 2020") == "2020-09-01"
    assert parse_iso_date("fall of 1999") == "1999-09-01"
    assert parse_iso_date("winter of 1985") == "1985-12-01"
    # Case-Insensitivitaet
    assert parse_iso_date("SOMMER VON 2024") == "2024-06-01"
    assert parse_iso_date("SUMMER OF 2024") == "2024-06-01"
    assert parse_iso_date("sommer von 2020") == "2020-06-01"
    # Kombiniert mit Annaeherungspraefix
    assert parse_iso_date("ca. Sommer von 1985") == "1985-06-01"
    assert parse_iso_date("circa summer of 1985") == "1985-06-01"
    # Kein Match: Whitespace-Zwang beidseitig
    assert parse_iso_date("Sommervon 2024") is None
    assert parse_iso_date("Sommer von2024") is None
    # Regress-Anker: die bisherigen Formen bleiben unveraendert
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("Sommer, 1985") == "1985-06-01"
    assert parse_iso_date("Summer 1985") == "1985-06-01"


def test_parse_iso_date_quartal_praeposition_von_of():
    """Quartals-Notation mit Wort-Praeposition ``von`` (DE) / ``of`` (EN)
    zwischen Q-/Quartal-Marker und Jahr: ``Q1 von 2024`` / ``1. Quartal of
    2024`` / ``Quarter 3 of 1985``.

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[/.\\-,]`` von
    :data:`_QUARTER_SHORT` und ``[/.\\-, ]`` von :data:`_QUARTER_LONG` um die
    Wort-Praepositions-Alternante ``\\s+(?:von|of)\\s+``. Spiegelt die
    identische Erweiterung in :data:`_KW_YEAR` (Wochen-Achse) und
    :data:`_MONTH_YEAR` (Monatsname-Achse) auf die Quartals-Achse: in
    Prosa-Etiketten und Sammler-Fund-Tagebuechern ist die Praepositions-
    Form die uebliche natuerlichsprachige Verbindung zwischen Quartals-
    Marker und Jahr ("Fund Q1 von 2024 im Aaregebiet", "Erwerb 1. Quartal
    von 2020 Zermatt-Bergtour", "Fund 3. Quarter of 2019 Tucson-Boerse").
    Mapping identisch zur Ein-Zeichen-Separator-Form (Quartals-Startmonat
    Jan/Apr/Jul/Okt, Tag 1). Beide Praepositionen verlangen Whitespace auf
    beiden Seiten, sodass Kompositum- und angehaengte Formen unangetastet
    auf None fallen.
    """
    # Kurzform Q1..Q4 + von/of (DE/EN)
    assert parse_iso_date("Q1 von 2024") == "2024-01-01"
    assert parse_iso_date("Q2 von 2024") == "2024-04-01"
    assert parse_iso_date("Q3 von 2024") == "2024-07-01"
    assert parse_iso_date("Q4 von 2024") == "2024-10-01"
    assert parse_iso_date("Q1 of 2024") == "2024-01-01"
    assert parse_iso_date("Q2 of 1985") == "1985-04-01"
    assert parse_iso_date("Q3 of 2019") == "2019-07-01"
    assert parse_iso_date("Q4 of 1999") == "1999-10-01"
    # Postfix-Form (1Q/2Q/3Q/4Q) + von/of
    assert parse_iso_date("1Q von 2024") == "2024-01-01"
    assert parse_iso_date("3Q of 2019") == "2019-07-01"
    # Langform Zahl-vor-Wort (1. Quartal / 3. Quarter) + von/of
    assert parse_iso_date("1. Quartal von 2024") == "2024-01-01"
    assert parse_iso_date("2. Quartal von 2024") == "2024-04-01"
    assert parse_iso_date("3. Quartal von 1985") == "1985-07-01"
    assert parse_iso_date("4. Quartal von 1999") == "1999-10-01"
    assert parse_iso_date("1. Quarter of 2024") == "2024-01-01"
    assert parse_iso_date("3. Quarter of 1985") == "1985-07-01"
    # Langform Wort-vor-Zahl (Quartal 1 / Quarter 3) + von/of
    assert parse_iso_date("Quartal 1 von 2024") == "2024-01-01"
    assert parse_iso_date("Quartal 2 of 2024") == "2024-04-01"
    assert parse_iso_date("Quarter 4 von 2024") == "2024-10-01"
    assert parse_iso_date("Quarter 3 of 1985") == "1985-07-01"
    # Case-Insensitivitaet (Excel-Auto-Fill / Uppercase-Titel)
    assert parse_iso_date("q1 VON 2024") == "2024-01-01"
    assert parse_iso_date("Q1 OF 2024") == "2024-01-01"
    assert parse_iso_date("QUARTAL 2 VON 2024") == "2024-04-01"
    assert parse_iso_date("quarter 3 of 1985") == "1985-07-01"
    # Kombiniert mit Annaeherungspraefix / Klammern
    assert parse_iso_date("ca. Q1 von 2024") == "2024-01-01"
    assert parse_iso_date("[Q3 of 1985]") == "1985-07-01"
    assert parse_iso_date("ca. 1. Quartal von 2020") == "2020-01-01"
    # Kein Match: Whitespace auf beiden Seiten der Praeposition obligatorisch
    assert parse_iso_date("Q1von2024") is None
    assert parse_iso_date("Q1von 2024") is None
    assert parse_iso_date("Q1 von2024") is None
    assert parse_iso_date("Quartal 1von 2024") is None
    assert parse_iso_date("Quartal 1 von2024") is None
    # Kein Match: Kompositum-Formen (vondel/vonof)
    assert parse_iso_date("Q1 vondel 2024") is None
    assert parse_iso_date("Q1 vonof 2024") is None
    # Kein Match: andere DE-Praepositionen bleiben unangetastet
    assert parse_iso_date("Q1 vor 2024") is None
    assert parse_iso_date("Q1 nach 2024") is None
    assert parse_iso_date("Q1 im 2024") is None
    assert parse_iso_date("Quartal 1 vor 2024") is None
    # Kein Match: EN-``of`` mit falscher Fortsetzung (kein 4-Ziffer-Jahr)
    assert parse_iso_date("Q1 of course 2024") is None
    # Ungueltige Q-Nummer
    assert parse_iso_date("Q0 von 2024") is None
    assert parse_iso_date("Q5 von 2024") is None
    assert parse_iso_date("5. Quartal von 2024") is None
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert.
    assert parse_iso_date("Q1 2024") == "2024-01-01"
    assert parse_iso_date("Q1/2024") == "2024-01-01"
    assert parse_iso_date("Q1-2024") == "2024-01-01"
    assert parse_iso_date("Q1,2024") == "2024-01-01"
    assert parse_iso_date("Q1.2024") == "2024-01-01"
    assert parse_iso_date("1Q2024") == "2024-01-01"
    assert parse_iso_date("1. Quartal 2024") == "2024-01-01"
    assert parse_iso_date("Quartal 1 2024") == "2024-01-01"
    assert parse_iso_date("3. Quarter 1985") == "1985-07-01"
    # Regress-Anker: Year-First-Formen bleiben unveraendert (dort ist die
    # Praepositions-Semantik nicht idiomatisch, keine Aenderung).
    assert parse_iso_date("2024-Q1") == "2024-01-01"
    assert parse_iso_date("2024 Q3") == "2024-07-01"
    assert parse_iso_date("2024Q4") == "2024-10-01"
    assert parse_iso_date("2024 1. Quartal") == "2024-01-01"


def test_parse_iso_date_halbjahr_praeposition_von_of():
    """Halbjahres-Notation mit Wort-Praeposition ``von`` (DE) / ``of`` (EN)
    zwischen H-/Halbjahr-Marker und Jahr: ``H1 von 2024`` / ``1. Halbjahr of
    2024`` / ``2. Halfyear of 1985``.

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[/.\\-,]`` von
    :data:`_HALFYEAR_SHORT` und ``[/.\\-, ]`` von :data:`_HALFYEAR_LONG` um die
    Wort-Praepositions-Alternante ``\\s+(?:von|of)\\s+``. Spiegelt die
    identische Erweiterung in :data:`_QUARTER_SHORT` / :data:`_QUARTER_LONG`
    (Quartals-Achse), :data:`_KW_YEAR` (Wochen-Achse) und :data:`_MONTH_YEAR`
    (Monatsname-Achse) auf die Halbjahres-Achse: in Prosa-Etiketten und
    Sammler-Fund-Tagebuechern ist die Praepositions-Form die uebliche
    natuerlichsprachige Verbindung zwischen Halbjahres-Marker und Jahr
    ("Fund H1 von 2024 im Aaregebiet", "Erwerb 1. Halbjahr von 2020 Zermatt-
    Bergtour", "Fund 2. Halfyear of 2019 Tucson-Boerse"). Mapping identisch
    zur Ein-Zeichen-Separator-Form (Halbjahres-Startmonat Jan/Jul, Tag 1).
    Beide Praepositionen verlangen Whitespace auf beiden Seiten, sodass
    Kompositum- und angehaengte Formen unangetastet auf None fallen.
    """
    # Kurzform H1/H2 + von/of (DE/EN)
    assert parse_iso_date("H1 von 2024") == "2024-01-01"
    assert parse_iso_date("H2 von 2024") == "2024-07-01"
    assert parse_iso_date("H1 of 2024") == "2024-01-01"
    assert parse_iso_date("H2 of 1985") == "1985-07-01"
    assert parse_iso_date("H1 of 2019") == "2019-01-01"
    assert parse_iso_date("H2 of 1999") == "1999-07-01"
    # Postfix-Form (1H/2H) + von/of
    assert parse_iso_date("1H von 2024") == "2024-01-01"
    assert parse_iso_date("2H von 2024") == "2024-07-01"
    assert parse_iso_date("2H of 2019") == "2019-07-01"
    # Langform Zahl-vor-Wort (1. Halbjahr / 2. Halbjahr) + von/of
    assert parse_iso_date("1. Halbjahr von 2024") == "2024-01-01"
    assert parse_iso_date("2. Halbjahr von 2024") == "2024-07-01"
    assert parse_iso_date("1. Halbjahr of 2024") == "2024-01-01"
    assert parse_iso_date("2. Halbjahr of 1985") == "1985-07-01"
    # Langform EN (halfyear / half-year) Zahl-vor-Wort + von/of
    assert parse_iso_date("1. Halfyear of 2024") == "2024-01-01"
    assert parse_iso_date("2. Halfyear of 1985") == "1985-07-01"
    assert parse_iso_date("1. Half-Year von 2020") == "2020-01-01"
    assert parse_iso_date("2. Half-Year of 2019") == "2019-07-01"
    # Langform Wort-vor-Zahl (Halbjahr 1 / Halfyear 2) + von/of
    assert parse_iso_date("Halbjahr 1 von 2024") == "2024-01-01"
    assert parse_iso_date("Halbjahr 2 of 2024") == "2024-07-01"
    assert parse_iso_date("Halfyear 1 of 2024") == "2024-01-01"
    assert parse_iso_date("Half-Year 2 von 1985") == "1985-07-01"
    # Case-Insensitivitaet (Excel-Auto-Fill / Uppercase-Titel)
    assert parse_iso_date("h1 VON 2024") == "2024-01-01"
    assert parse_iso_date("H1 OF 2024") == "2024-01-01"
    assert parse_iso_date("HALBJAHR 2 VON 2024") == "2024-07-01"
    assert parse_iso_date("halfyear 1 of 2024") == "2024-01-01"
    # Kombiniert mit Annaeherungspraefix / Klammern
    assert parse_iso_date("ca. H1 von 2024") == "2024-01-01"
    assert parse_iso_date("[H2 of 1985]") == "1985-07-01"
    assert parse_iso_date("ca. 1. Halbjahr von 2020") == "2020-01-01"
    # Kein Match: Whitespace auf beiden Seiten der Praeposition obligatorisch
    assert parse_iso_date("H1von2024") is None
    assert parse_iso_date("H1von 2024") is None
    assert parse_iso_date("H1 von2024") is None
    assert parse_iso_date("Halbjahr 1von 2024") is None
    assert parse_iso_date("Halbjahr 1 von2024") is None
    # Kein Match: Kompositum-Formen (vondel/vonof)
    assert parse_iso_date("H1 vondel 2024") is None
    assert parse_iso_date("H1 vonof 2024") is None
    # Kein Match: andere DE-Praepositionen bleiben unangetastet
    assert parse_iso_date("H1 vor 2024") is None
    assert parse_iso_date("H1 nach 2024") is None
    assert parse_iso_date("H1 im 2024") is None
    assert parse_iso_date("Halbjahr 1 vor 2024") is None
    # Ungueltige H-Nummer (nur H1/H2)
    assert parse_iso_date("H0 von 2024") is None
    assert parse_iso_date("H3 von 2024") is None
    assert parse_iso_date("3. Halbjahr von 2024") is None
    assert parse_iso_date("Halbjahr 3 von 2024") is None
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert.
    assert parse_iso_date("H1 2024") == "2024-01-01"
    assert parse_iso_date("H1/2024") == "2024-01-01"
    assert parse_iso_date("H1-2024") == "2024-01-01"
    assert parse_iso_date("H1,2024") == "2024-01-01"
    assert parse_iso_date("H1.2024") == "2024-01-01"
    assert parse_iso_date("1H2024") == "2024-01-01"
    assert parse_iso_date("1. Halbjahr 2024") == "2024-01-01"
    assert parse_iso_date("Halbjahr 1 2024") == "2024-01-01"
    assert parse_iso_date("2. Halfyear 1985") == "1985-07-01"
    # Regress-Anker: Year-First-Formen bleiben unveraendert (dort ist die
    # Praepositions-Semantik nicht idiomatisch, keine Aenderung).
    assert parse_iso_date("2024-H1") == "2024-01-01"
    assert parse_iso_date("2024 H2") == "2024-07-01"
    assert parse_iso_date("2024H2") == "2024-07-01"
    assert parse_iso_date("2024 1. Halbjahr") == "2024-01-01"


def test_parse_iso_date_relative_year_praeposition_von_of():
    """Relative Jahresposition mit Wort-Praeposition ``von`` (DE) / ``of``
    (EN) zwischen Positions-Wort und Jahr: ``Anfang von 2024`` / ``Mitte von
    1985`` / ``Ende von 1999`` / ``Jahresanfang von 2020`` / ``Jahresende
    of 2019``.

    Ergaenzt die Trenner-Klasse ``[-\\s]+`` von :data:`_RELATIVE_YEAR` und
    :data:`_YEAR_COMPOUND_POSITION` um die Wort-Praepositions-Alternante
    ``\\s+(?:von|of)\\s+``. Spiegelt die identische Erweiterung in
    :data:`_KW_YEAR` (Wochen-Achse), :data:`_MONTH_YEAR` (Monatsname-Achse),
    :data:`_QUARTER_SHORT`/:data:`_QUARTER_LONG` (Quartals-Achse) und
    :data:`_HALFYEAR_SHORT`/:data:`_HALFYEAR_LONG` (Halbjahres-Achse) auf die
    relative-Jahresposition-Achse. In DE-Sammler-Notizen ist ``Anfang von
    2024`` (bzw. das umgangssprachlich haeufigere Substantiv-Kompositum
    ``Jahresanfang von 2024``) die etablierte Verbindungs-Form zwischen
    Positions-Wort und Jahr. Mapping identisch zur Ein-Zeichen-Trenner-Form
    (Anfang/early -> Jan, Mitte -> Jul, Ende/late -> Dez). Beide
    Praepositionen verlangen Whitespace auf beiden Seiten, sodass
    Kompositum- und angehaengte Formen unangetastet auf None fallen.
    """
    # DE artikellose Kurzform + von/of
    assert parse_iso_date("Anfang von 2024") == "2024-01-01"
    assert parse_iso_date("Mitte von 2024") == "2024-07-01"
    assert parse_iso_date("Ende von 2024") == "2024-12-01"
    assert parse_iso_date("Anfang of 2024") == "2024-01-01"
    assert parse_iso_date("Mitte of 1985") == "1985-07-01"
    assert parse_iso_date("Ende of 1999") == "1999-12-01"
    # EN Kurzform + von/of (of-Praeposition idiomatisch fuer EN)
    assert parse_iso_date("early of 2024") == "2024-01-01"
    assert parse_iso_date("mid of 2024") == "2024-07-01"
    assert parse_iso_date("late of 2024") == "2024-12-01"
    assert parse_iso_date("early von 2024") == "2024-01-01"
    # DE Substantiv-Kompositum + von/of (haeufigste DE-Prosa-Form)
    assert parse_iso_date("Jahresanfang von 2024") == "2024-01-01"
    assert parse_iso_date("Jahresbeginn von 2024") == "2024-01-01"
    assert parse_iso_date("Jahresstart von 2024") == "2024-01-01"
    assert parse_iso_date("Jahresmitte von 2024") == "2024-07-01"
    assert parse_iso_date("Jahresende von 2024") == "2024-12-01"
    assert parse_iso_date("Jahresschluss von 1985") == "1985-12-01"
    assert parse_iso_date("Jahresausklang von 1999") == "1999-12-01"
    # Substantiv-Kompositum mit of (Symmetrie zur uebrigen Praxis)
    assert parse_iso_date("Jahresanfang of 2024") == "2024-01-01"
    assert parse_iso_date("Jahresende of 1985") == "1985-12-01"
    assert parse_iso_date("Jahresschluss of 2019") == "2019-12-01"
    # Case-Insensitivitaet (Excel-Auto-Fill / Uppercase-Titel)
    assert parse_iso_date("ANFANG VON 2024") == "2024-01-01"
    assert parse_iso_date("mitte OF 2024") == "2024-07-01"
    assert parse_iso_date("ENDE OF 1985") == "1985-12-01"
    assert parse_iso_date("JAHRESANFANG VON 2024") == "2024-01-01"
    assert parse_iso_date("jahresmitte of 2024") == "2024-07-01"
    # Kombiniert mit Annaeherungspraefix / Klammern
    assert parse_iso_date("ca. Anfang von 2024") == "2024-01-01"
    assert parse_iso_date("[Jahresende von 1985]") == "1985-12-01"
    assert parse_iso_date("circa Mitte von 1990") == "1990-07-01"
    # Kein Match: Whitespace auf beiden Seiten der Praeposition obligatorisch
    assert parse_iso_date("Anfangvon2024") is None
    assert parse_iso_date("Anfangvon 2024") is None
    assert parse_iso_date("Anfang von2024") is None
    assert parse_iso_date("Jahresanfangvon 2024") is None
    assert parse_iso_date("Jahresanfang von2024") is None
    # Kein Match: Kompositum-Formen (vondel/vonof)
    assert parse_iso_date("Anfang vondel 2024") is None
    assert parse_iso_date("Anfang vonof 2024") is None
    assert parse_iso_date("Jahresanfang vondel 2024") is None
    # Kein Match: andere DE-Praepositionen bleiben unangetastet
    assert parse_iso_date("Anfang vor 2024") is None
    assert parse_iso_date("Anfang nach 2024") is None
    assert parse_iso_date("Anfang im 2024") is None
    assert parse_iso_date("Jahresende vor 2024") is None
    assert parse_iso_date("Jahresende nach 2024") is None
    # Kein Match: EN-``of`` mit falscher Fortsetzung (kein 4-Ziffer-Jahr)
    assert parse_iso_date("Anfang of course 2024") is None
    # Regress-Anker: die bisherigen Trenner-Formen bleiben unveraendert.
    assert parse_iso_date("Anfang 2024") == "2024-01-01"
    assert parse_iso_date("Mitte 2024") == "2024-07-01"
    assert parse_iso_date("Ende 2024") == "2024-12-01"
    assert parse_iso_date("early 2024") == "2024-01-01"
    assert parse_iso_date("mid 2024") == "2024-07-01"
    assert parse_iso_date("late 2024") == "2024-12-01"
    assert parse_iso_date("mid-2024") == "2024-07-01"
    assert parse_iso_date("early-2024") == "2024-01-01"
    assert parse_iso_date("Jahresanfang 2024") == "2024-01-01"
    assert parse_iso_date("Jahresmitte 2024") == "2024-07-01"
    assert parse_iso_date("Jahresende 2024") == "2024-12-01"
    assert parse_iso_date("Jahresbeginn 2024") == "2024-01-01"
    assert parse_iso_date("Jahresschluss 2024") == "2024-12-01"
    assert parse_iso_date("Jahresausklang 1999") == "1999-12-01"


def test_parse_iso_date_w_marker_kurzform():
    """Einzelbuchstabe-Kurzform ``W`` als Wochen-Marker (``W25 2024`` / ``2024 W25``).

    Symmetrisch zu :data:`_KW_YEAR` / :data:`_KW_YEAR_FIRST` fuer den ISO
    8601-Wochen-Marker ``W`` ohne volles Kalenderwoche-Wort. Spiegelt die
    ISO-Compact-Form ``2024W25`` (:data:`_ISO_WEEK_DATE`, kein Whitespace-
    Trenner) auf die Formen mit Whitespace-/Separator-Trenner: die
    Year-Last-Reihenfolge ``W25 2024`` (Wochen-Zahl vor Jahr) und die
    Space-getrennte Year-First-Form ``2024 W25`` sind in Log-Stempeln,
    Kalender-Exporten und internationalen Sammler-Notizen die de-facto
    Kompakt-Schreibweisen ohne KW-/CW-Praefix. Mapping identisch (Montag
    der genannten Woche).
    """
    # Year-Last-Reihenfolge (Wochen-Marker vor Jahr): die klassische
    # Log-Stempel-/Kalender-Export-Notation.
    assert parse_iso_date("W25 2024") == "2024-06-17"
    assert parse_iso_date("W25/2024") == "2024-06-17"
    assert parse_iso_date("W25.2024") == "2024-06-17"
    assert parse_iso_date("W25, 2024") == "2024-06-17"
    assert parse_iso_date("W25-2024") == "2024-06-17"
    # Optionaler Whitespace zwischen W-Marker und Wochen-Zahl (spiegelt die
    # KW/CW-Konvention aus _KW_YEAR: ``KW 25 2024`` / ``KW25 2024``).
    assert parse_iso_date("W 25 2024") == "2024-06-17"
    # Optionaler Punkt-Trenner nach W-Kurzform (``W. 25 2024``) - spiegelt
    # die Punkt-Abkuerzungs-Konvention aus _KW_YEAR (``KW. 25 2024``).
    assert parse_iso_date("W. 25 2024") == "2024-06-17"
    # Year-First-Reihenfolge (Jahr vor Wochen-Marker): symmetrisch zu
    # _KW_YEAR_FIRST fuer ``KW`` etc. Deckt die Space-getrennte Form
    # ``2024 W25`` ab (die Non-Space-Form ``2024W25`` bleibt bei
    # _ISO_WEEK_DATE).
    assert parse_iso_date("2024 W25") == "2024-06-17"
    assert parse_iso_date("2024/W25") == "2024-06-17"
    assert parse_iso_date("2024 W 25") == "2024-06-17"
    assert parse_iso_date("2024, W25") == "2024-06-17"
    # Case-insensitive (Standard-KW-Alternante hat re.IGNORECASE-Flag).
    assert parse_iso_date("w25 2024") == "2024-06-17"
    # Erste Woche und letzte Woche als Grenzfaelle (2024 hat 52 Wochen).
    assert parse_iso_date("W1 2024") == "2024-01-01"
    assert parse_iso_date("W52 2024") == "2024-12-23"
    # Kombiniert mit Annaeherungspraefix / Klammern (die Prefix-Strip-
    # Kaskade in parse_iso_date arbeitet transparent).
    assert parse_iso_date("ca. W25 2024") == "2024-06-17"
    assert parse_iso_date("[W25 2024]") == "2024-06-17"
    # Ungueltig: Wochen-Zahl ausser Bereich (Woche 0, Woche 54, Woche 53
    # in 2024 gibt es nicht) und Jahr ausserhalb der Kollektions-Domaene.
    assert parse_iso_date("W0 2024") is None
    assert parse_iso_date("W54 2024") is None
    assert parse_iso_date("W53 2024") is None  # 2024 hat nur 52 Wochen
    assert parse_iso_date("W25 1700") is None
    # Standalone-W-Token ohne 4-Ziffer-Jahr matcht NICHT: schuetzt vor
    # False-Positives bei Messwert-Notationen (``W3.5``), Sortier-Codes
    # (``W-4``), Standalone-Wochen-Referenzen (``W25`` allein). Der
    # obligatorische Separator + 4-Ziffer-Jahr im Regex-Anker sorgt
    # dafuer, dass die W-Alternante nur bei vollstaendiger Wochen-plus-
    # Jahr-Struktur greift.
    assert parse_iso_date("W25") is None
    assert parse_iso_date("W3.5") is None
    assert parse_iso_date("W-4") is None
    # Regress-Anker: die bestehenden KW/CW/Kalenderwoche/Woche-Formen
    # bleiben unveraendert (die W-Alternante steht am Ende der Regex-
    # Alternativen, sodass laengere Marker Vorrang haben - regex-
    # alternative-Ordering ist links-nach-rechts).
    assert parse_iso_date("KW 25 2024") == "2024-06-17"
    assert parse_iso_date("Kalenderwoche 25 2024") == "2024-06-17"
    assert parse_iso_date("Woche 25 2024") == "2024-06-17"
    assert parse_iso_date("2024 KW 25") == "2024-06-17"
    # Regress-Anker: die ISO-Compact-Form ``2024W25`` bleibt bei
    # _ISO_WEEK_DATE und liefert unveraendert das Datum (keine
    # Doppel-Interpretation durch die neue W-Alternante).
    assert parse_iso_date("2024W25") == "2024-06-17"
    assert parse_iso_date("2024-W25") == "2024-06-17"
    assert parse_iso_date("2024-W25-3") == "2024-06-19"


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


def test_parse_iso_date_year_first_saison():
    """Year-first Jahreszeit-Notation ('2024 Sommer', '1985-Winter', '2024/Herbst')
    liefert den meteorologischen Saison-Start; symmetrisch zur Year-Last-Form
    'Sommer 1985'."""
    # DE-Saisons mit verschiedenen Separatoren (Whitespace/Bindestrich/Slash/Punkt/Komma)
    assert parse_iso_date("2024 Sommer") == "2024-06-01"
    assert parse_iso_date("2024-Sommer") == "2024-06-01"
    assert parse_iso_date("2024/Sommer") == "2024-06-01"
    assert parse_iso_date("2024.Sommer") == "2024-06-01"
    assert parse_iso_date("2024, Sommer") == "2024-06-01"
    # Alle vier DE-Saisons (Startmonate 3/6/9/12)
    assert parse_iso_date("1985 Fruehling") == "1985-03-01"
    assert parse_iso_date("1985 Fruehjahr") == "1985-03-01"
    assert parse_iso_date("1985 Frühjahr") == "1985-03-01"
    assert parse_iso_date("1985 Sommer") == "1985-06-01"
    assert parse_iso_date("1985 Herbst") == "1985-09-01"
    assert parse_iso_date("1985 Winter") == "1985-12-01"
    # EN-Saisons symmetrisch zur Year-Last-Form
    assert parse_iso_date("2024 spring") == "2024-03-01"
    assert parse_iso_date("2024 summer") == "2024-06-01"
    assert parse_iso_date("2024 autumn") == "2024-09-01"
    assert parse_iso_date("2024 fall") == "2024-09-01"
    assert parse_iso_date("2024 winter") == "2024-12-01"
    # Case-insensitive (Normalisierung)
    assert parse_iso_date("2024 SOMMER") == "2024-06-01"
    assert parse_iso_date("2024 sommer") == "2024-06-01"
    assert parse_iso_date("2024-HERBST") == "2024-09-01"
    # Optionaler trailing Punkt am Saison-Wort
    assert parse_iso_date("2024 Sommer.") == "2024-06-01"
    # Kombiniert mit Annaeherungspraefix / Klammern / Anfuehrungszeichen
    assert parse_iso_date("ca. 2024 Sommer") == "2024-06-01"
    assert parse_iso_date("(2024 Sommer)") == "2024-06-01"
    assert parse_iso_date('"2024 Sommer"') == "2024-06-01"
    assert parse_iso_date("ungefähr 2024 Herbst") == "2024-09-01"
    # Regression: Year-Last-Form bleibt unveraendert erkannt
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("Winter 2023/2024") == "2023-12-01"


def test_parse_iso_date_year_first_saison_ungueltig():
    """Year-first Saison mit ungueltigen Werten faellt auf None."""
    # Unbekanntes Wort (weder Monat noch Saison)
    assert parse_iso_date("2024 Foo") is None
    assert parse_iso_date("2024-Bar") is None
    # Jahr ausserhalb 1800..2999
    assert parse_iso_date("0000 Sommer") is None
    assert parse_iso_date("3000 Sommer") is None
    assert parse_iso_date("1700 Winter") is None
    # Regression: Year-first Monatsname ("2024 Juni") bleibt Monat, nicht Saison
    assert parse_iso_date("2024 Juni") == "2024-06-01"
    assert parse_iso_date("2024-Dezember") == "2024-12-01"


def test_parse_iso_date_compact_yyyymm():
    """Compact YYYYMM-Form ohne Trenner: '202406' -> 2024-06-01.

    Deckt Datei-/Ordner-Namen aus Foto-/Sammlungs-Archiven ('photos_202406/',
    'log_202406.txt', 'backup_202406.tar.gz'), Buchhaltungs-Perioden-Stempel,
    monatliche Batch-/Backup-Rotation-Skripten und Foto-EXIF-Auto-Renamer
    (Sony/Canon Kamera-Software YYYYMM-Ordner-Praefix) ab. Vorher fielen
    diese Formen entweder auf ein semantisch falsches Datum (das
    ``%Y%m%d``-Format matcht per Python-strptime-Greedy-Verhalten auch
    6-Ziffer-Inputs: '202412' wurde zu '2024-01-02' statt '2024-12-01')
    oder auf None (bei ungueltiger 5. Ziffer als Tag)."""
    # Alle Monate 01..12
    assert parse_iso_date("202401") == "2024-01-01"
    assert parse_iso_date("202402") == "2024-02-01"
    assert parse_iso_date("202403") == "2024-03-01"
    assert parse_iso_date("202404") == "2024-04-01"
    assert parse_iso_date("202405") == "2024-05-01"
    assert parse_iso_date("202406") == "2024-06-01"
    assert parse_iso_date("202407") == "2024-07-01"
    assert parse_iso_date("202408") == "2024-08-01"
    assert parse_iso_date("202409") == "2024-09-01"
    assert parse_iso_date("202410") == "2024-10-01"
    assert parse_iso_date("202411") == "2024-11-01"
    assert parse_iso_date("202412") == "2024-12-01"
    # Verschiedene Jahre am Rand des zulaessigen Bereichs
    assert parse_iso_date("180001") == "1800-01-01"
    assert parse_iso_date("299912") == "2999-12-01"
    assert parse_iso_date("199912") == "1999-12-01"
    assert parse_iso_date("198506") == "1985-06-01"
    # Leading/Trailing Whitespace
    assert parse_iso_date("  202406  ") == "2024-06-01"
    assert parse_iso_date("\t202406\n") == "2024-06-01"


def test_parse_iso_date_compact_yyyymm_ungueltig():
    """Compact YYYYMM mit ungueltigen Werten faellt auf None (blockiert
    die %Y%m%d-Greedy-Interpretation im nachfolgenden strptime-Loop)."""
    # Ungueltiger Monat (00, 13, 99)
    assert parse_iso_date("202400") is None
    assert parse_iso_date("202413") is None
    assert parse_iso_date("202499") is None
    # Jahr ausserhalb 1800..2999
    assert parse_iso_date("170006") is None
    assert parse_iso_date("179906") is None  # 1799 knapp ausserhalb
    assert parse_iso_date("300006") is None  # 3000 knapp ausserhalb
    assert parse_iso_date("999999") is None
    # Falsche Laenge (5 oder 7 Ziffern - kein YYYYMM)
    assert parse_iso_date("20240") is None
    assert parse_iso_date("2024") == "2024-01-01"  # 4 Ziffern = _YEAR_ONLY
    # Regression: 8-Ziffer-YYYYMMDD bleibt korrekt
    assert parse_iso_date("20240613") == "2024-06-13"
    # Regression: 7-Ziffer-YYYYDDD (ISO-Ordinal) bleibt korrekt
    assert parse_iso_date("2024165") == "2024-06-13"
    # Regression: hyphenierte Form bleibt korrekt
    assert parse_iso_date("2024-06") == "2024-06-01"
    assert parse_iso_date("2024-06-01") == "2024-06-01"


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


def test_parse_iso_date_erweiterte_no_data_marker():
    """Erweiterte "keine Angabe"-Marker liefern None (nicht als silent-data-loss
    Fund gemeldet werden).

    Ergaenzt die Basis-Menge (``k.a.``/``k. a.``/``n/a``/``na``/``?``/``-``/
    ``—``/``unbekannt``) um symmetrische Varianten (``n.a.``/``n. a.`` zu
    ``k.a.``/``k. a.``, En-Dash ``–`` zu ASCII-``-`` und Em-Dash ``—``),
    Mehrfach-Fragezeichen (``??``/``???``), englische Aequivalente
    (``unknown``/``no data``/``no date``/``none``) und ausgeschriebene
    DE-Formen (``keine angabe``/``keine daten``/``kein datum``). Alle Varianten
    liefern None statt einer Fehl-Interpretation, und der Marker-Check ist
    case-insensitive (parse_iso_date .lower()t den Input vor dem Check).
    """
    # n.a. / n. a. symmetrisch zu k.a. / k. a.
    assert parse_iso_date("n.a.") is None
    assert parse_iso_date("N.A.") is None
    assert parse_iso_date("n. a.") is None
    assert parse_iso_date("N. A.") is None
    # En-Dash (U+2013) symmetrisch zu ASCII-Hyphen und Em-Dash
    assert parse_iso_date("–") is None
    # Mehrfach-Fragezeichen
    assert parse_iso_date("??") is None
    assert parse_iso_date("???") is None
    # Englische Aequivalente
    assert parse_iso_date("unknown") is None
    assert parse_iso_date("UNKNOWN") is None
    assert parse_iso_date("Unknown") is None
    assert parse_iso_date("no data") is None
    assert parse_iso_date("No Data") is None
    assert parse_iso_date("no date") is None
    assert parse_iso_date("none") is None
    assert parse_iso_date("None") is None
    # Ausgeschriebene DE-Formen
    assert parse_iso_date("keine angabe") is None
    assert parse_iso_date("Keine Angabe") is None
    assert parse_iso_date("KEINE ANGABE") is None
    assert parse_iso_date("keine daten") is None
    assert parse_iso_date("kein datum") is None
    # Whitespace-Toleranz (parse_iso_date strippt vor dem Marker-Check)
    assert parse_iso_date("  n.a.  ") is None
    assert parse_iso_date("  keine angabe  ") is None
    # Regress-Anker: bereits vorhandene Marker bleiben None
    assert parse_iso_date("k.a.") is None
    assert parse_iso_date("n/a") is None
    assert parse_iso_date("unbekannt") is None
    # Regress-Anker: gueltige Datums-Formen bleiben unveraendert
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    # Regress-Anker: echte Fehl-Eingaben bleiben None (nicht in der Marker-Menge)
    assert parse_iso_date("Sommer 84") is None
    assert parse_iso_date("32.13.2024") is None


def test_date_no_data_markers_import_und_konsistenz():
    """DATE_NO_DATA_MARKERS ist importierbar und enthaelt die erwarteten Kern-Marker.

    csv_loaders.find_rows_with_invalid_funddatum importiert die Menge direkt
    (als single source of truth) - der Anker garantiert, dass die neuen
    Marker fuer alle Consumer sichtbar sind, nicht nur fuer parse_iso_date.
    """
    from stonebook.migration.validators import DATE_NO_DATA_MARKERS
    # Bereits vorhandene Marker
    assert "k.a." in DATE_NO_DATA_MARKERS
    assert "unbekannt" in DATE_NO_DATA_MARKERS
    # Neu hinzugefuegte Marker
    assert "n.a." in DATE_NO_DATA_MARKERS
    assert "n. a." in DATE_NO_DATA_MARKERS
    assert "–" in DATE_NO_DATA_MARKERS  # U+2013 en-dash
    assert "??" in DATE_NO_DATA_MARKERS
    assert "unknown" in DATE_NO_DATA_MARKERS
    assert "no data" in DATE_NO_DATA_MARKERS
    assert "keine angabe" in DATE_NO_DATA_MARKERS
    # Alle Marker sind lowercase (parse_iso_date .lower()t den Input vor dem Check)
    for marker in DATE_NO_DATA_MARKERS:
        assert marker == marker.lower(), (
            f"Marker {marker!r} ist nicht lowercase - parse_iso_date wuerde "
            "ihn beim .lower()-Vergleich niemals matchen.")


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


def test_parse_coordinates_nmea_0183_sentence():
    """NMEA-0183 Sentence-Form: ``DDMM.mmmm,N,DDDMM.mmmm,E`` mit N/S/E/W-
    Direction-Buchstaben statt Vorzeichen und Komma als Field-Separator.

    Standard-Ausgabe des NMEA-0183-Protokolls, das jedes GPS-Geraet als
    Rohdaten-Ausgabe unterstuetzt (Serial-Port, USB-Debug, gpsd-Ausgabe,
    viele Handheld-GPS-Empfaenger im "NMEA-Dump"-Modus) und jede GPX-/KML-
    Konverter-Kette als Zwischenformat verwendet. Verbreitet in Rohdaten-
    Logs aus Fahrzeug-/Boots-Navigationsgeraeten, in exiftool-XMP-GPS-
    Exporten und in gpsbabel-Ausgabe im "$GPGGA"-/"$GPRMC"-Sentence-Format.

    Bisher fielen alle NMEA-Notationen still auf None: _ISO6709_COMPACT_DM
    verlangt ±-Vorzeichen, _DECIMAL_PAIR liest "4630.500" als 4630.5 (out-of-
    range, _validate liefert None), _PREFIX_PAIR/_SUFFIX_PAIR_NO_SEP gehen
    von Dezimal-Grad-Notation aus.
    """
    expected_lat = 46.0 + 30.5 / 60  # 46.508333...
    expected_lon = 7.0 + 45.3 / 60   # 7.755

    # NMEA-Standard mit Komma-Trenner
    lat, lon = parse_coordinates("4630.500,N,00745.300,E")
    assert abs(lat - expected_lat) < 1e-6
    assert abs(lon - expected_lon) < 1e-6

    # Copy-Paste-Variante mit Whitespace statt Komma
    lat, lon = parse_coordinates("4630.500 N 00745.300 E")
    assert abs(lat - expected_lat) < 1e-6
    assert abs(lon - expected_lon) < 1e-6

    # Compact ohne Trenner um die Direction-Buchstaben
    lat, lon = parse_coordinates("4630.500N 00745.300E")
    assert abs(lat - expected_lat) < 1e-6
    assert abs(lon - expected_lon) < 1e-6

    # Mixed: Komma zwischen Zahl und Direction, Whitespace zwischen Feld-Paaren
    lat, lon = parse_coordinates("4630.500,N 00745.300,E")
    assert abs(lat - expected_lat) < 1e-6
    assert abs(lon - expected_lon) < 1e-6

    # Suedhalbkugel/Westhalbkugel
    lat, lon = parse_coordinates("4630.500,S,00745.300,W")
    assert abs(lat - -expected_lat) < 1e-6
    assert abs(lon - -expected_lon) < 1e-6

    # Case-insensitive
    lat, lon = parse_coordinates("4630.500,n,00745.300,e")
    assert abs(lat - expected_lat) < 1e-6

    # DE ``O`` als Ost (Sammler-typische DE-Notation)
    lat, lon = parse_coordinates("4630.500,N,00745.300,O")
    assert abs(lon - expected_lon) < 1e-6

    # Vollstaendige GPGGA-NMEA-Sentence (aus Roh-GPS-Log)
    lat, lon = parse_coordinates(
        "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    )
    assert abs(lat - (48.0 + 7.038 / 60)) < 1e-6
    assert abs(lon - (11.0 + 31.000 / 60)) < 1e-6

    # Integer-only NMEA (Minuten ohne Dezimal, spec-erlaubt)
    lat, lon = parse_coordinates("4630N 00745E")
    assert abs(lat - 46.5) < 1e-6
    assert abs(lon - 7.75) < 1e-6

    # Grenzfaelle Aequator/Greenwich (00 00.000 in beiden Achsen)
    assert parse_coordinates("0000.000,N,00000.000,E") == (0.0, 0.0)

    # Extremer Rand ±90 Lat / ±180 Lon (Nordpol / 180° Meridian)
    lat, lon = parse_coordinates("8959.9,N,17959.9,E")
    assert lat == pytest.approx(89.99833, abs=1e-4)
    assert lon == pytest.approx(179.99833, abs=1e-4)

    # Out-of-Range: Latitude > 90 (95° geht nicht)
    assert parse_coordinates("9530.5,N,00745.3,E") is None
    # Out-of-Range: Longitude > 180 (185° geht nicht)
    assert parse_coordinates("4630.5,N,18530.3,E") is None

    # Regress-Anker: bestehende Formen bleiben unveraendert
    # Reine Dezimal-Grad (kein NMEA)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    # Suffix mit Direction ohne NMEA-Struktur
    assert parse_coordinates("46.5N 7.5E") == (46.5, 7.5)
    # ISO-6709-Compact-DM mit ±-Vorzeichen bleibt
    assert parse_coordinates("+4630+00745") == (46.5, 7.75)
    lat, lon = parse_coordinates("+4630.500+00745.300")
    assert abs(lat - expected_lat) < 1e-6
    # DMS Suffix-Form bleibt (Grad-Symbol vorhanden)
    lat, lon = parse_coordinates("46°30'15\" N, 7°45'30\" E")
    assert abs(lat - (46.5 + 15/3600)) < 1e-6


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


def test_parse_coordinates_masculine_ordinal_als_grad_symbol():
    """U+00BA (maskuline Ordinal ``º``) wird wie U+00B0 (Grad ``°``) behandelt.

    ``º`` liegt auf spanischen/portugiesischen/italienischen Tastaturen als
    eigene Taste (``°`` erfordert dort AltGr) und ist die von iOS-Long-Press
    auf ``O`` angebotene Standard-Alternative. OCR-Engines geben bei
    niedrig-aufgeloesten Print-Katalogen haeufig ``º`` statt ``°`` aus, weil
    die beiden Glyphen visuell nicht unterscheidbar sind. Vor dem Fix fielen
    alle DMS-/Decimal-Degree-Formen mit ``º`` still auf None, weil die 40+
    Regex-Vorkommen des Grad-Literals strikt U+00B0 verlangen.
    """
    # Decimal-Degree mit Label und Kardinalrichtung
    assert parse_coordinates("Lat: 46.5º N, Lon: 7.5º E") == (46.5, 7.5)
    assert parse_coordinates("46.5º N, 7.5º E") == (46.5, 7.5)
    assert parse_coordinates("46.5º S, 7.5º W") == (-46.5, -7.5)
    # Vollstaendige DMS-Notation (Grad, Minuten, Sekunden)
    lat, lon = parse_coordinates("46º30'15\"N 7º30'0\"E")
    assert abs(lat - (46 + 30/60 + 15/3600)) < 1e-9
    assert abs(lon - 7.5) < 1e-9
    # DMS mit Whitespace zwischen den Komponenten
    lat, lon = parse_coordinates("46º 30' 15\" N, 7º 30' 0\" E")
    assert abs(lat - (46 + 30/60 + 15/3600)) < 1e-9
    assert abs(lon - 7.5) < 1e-9
    # Prefix-Form (Richtung vor dem Wert)
    assert parse_coordinates("N46.5º E7.5º") == (46.5, 7.5)
    assert parse_coordinates("N 46º 30' 15\" E 7º 30' 0\"") == (
        parse_coordinates("N 46° 30' 15\" E 7° 30' 0\"")
    )
    # Degree-Decimal-Minute-Form (DDM: Grad + Dezimal-Minuten)
    lat, lon = parse_coordinates("46º30.5'N 7º45.5'E")
    assert abs(lat - (46 + 30.5/60)) < 1e-9
    assert abs(lon - (7 + 45.5/60)) < 1e-9
    # ASCII-Hyphen-Vorzeichen + Ordinal-Grad-Marker (ohne Kardinalrichtung)
    assert parse_coordinates("-46.5º -7.5º") == (-46.5, -7.5)
    # U+2212-Minus + Ordinal-Grad-Marker (beide Fixes greifen unabhaengig)
    assert parse_coordinates("−46.5º −7.5º") == (-46.5, -7.5)
    # Gemischt ``º`` und ``°`` im selben Eingabestring
    assert parse_coordinates("46.5º N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5º E") == (46.5, 7.5)
    # Out-of-Range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("95.0º N, 7.5º E") is None
    assert parse_coordinates("46.5º N, 200.0º E") is None
    # Bestehender U+00B0-Pfad bleibt unveraendert (Regress)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("46°30'15\"N 7°30'0\"E") == (
        parse_coordinates("46º30'15\"N 7º30'0\"E")
    )
    # ``º`` alleine ohne Zahl-Kontext liefert None (keine Koordinate)
    assert parse_coordinates("ºº") is None
    assert parse_coordinates("º") is None


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


def test_parse_coordinates_lng_web_api_kurzform():
    """Google-Maps-/Leaflet-/Mapbox-Kurzform ``lng`` als Longitude-Label.

    ``lng`` ist die de-facto Standard-Kurzform der Longitude in den verbreitetsten
    Web-Mapping-APIs (Google Maps JavaScript API mit ``google.maps.LatLng``,
    Leaflet ``L.latLng(lat, lng)``, Mapbox GL ``[lng, lat]``, MapKit JS, HERE
    Maps, Bing Maps V8), neben ``lon`` die zweite etablierte Konvention. In
    Sammler-Notizen aus modernen Foto-Apps mit eingebetteter Karte (Google
    Photos "gps info", iPhone "Places", Bergtouren-Apps wie Komoot/AllTrails,
    ExifTool-JSON-Formatierung) die haeufigere Notation als ``lon``. Bisher
    fiel jede ``lat/lng``-Notation still auf None: ``_COORD_LABEL`` erkannte
    ``lat`` und strippte es, ``lng`` blieb aber unbekannt und verhinderte via
    _PREFIX_PAIR / _DECIMAL_PAIR die Struktur-Erkennung.
    """
    # Grundfall: lat + lng mit Komma/Doppelpunkt/Gleichheit/Whitespace/Ampersand
    assert parse_coordinates("lat 46.5, lng 7.5") == (46.5, 7.5)
    assert parse_coordinates("lat: 46.5, lng: 7.5") == (46.5, 7.5)
    assert parse_coordinates("lat=46.5, lng=7.5") == (46.5, 7.5)
    assert parse_coordinates("lat=46.5&lng=7.5") == (46.5, 7.5)
    assert parse_coordinates("lat 46.5 lng 7.5") == (46.5, 7.5)
    # Case-insensitive (spiegelt die uebrigen Labels)
    assert parse_coordinates("LAT 46.5, LNG 7.5") == (46.5, 7.5)
    assert parse_coordinates("Lat 46.5, Lng 7.5") == (46.5, 7.5)
    # Negative Werte (Suedhalbkugel/Westhalbkugel)
    assert parse_coordinates("lat: -46.5, lng: -7.5") == (-46.5, -7.5)
    # Grad-Symbol als typografischer Zusatz
    assert parse_coordinates("lat: 46.5°, lng: 7.5°") == (46.5, 7.5)
    # Mit expliziter Richtung (Label wird gestrippt, Richtung bleibt aktiv)
    assert parse_coordinates("lat: 46.5N, lng: 7.5E") == (46.5, 7.5)
    assert parse_coordinates("lat: 46.5S, lng: 7.5W") == (-46.5, -7.5)
    # Wort-Boundary: laengere Woerter mit ``lng`` als Substring nicht matchen
    assert parse_coordinates("lngs=1") is None
    assert parse_coordinates("foolng=1") is None
    # Regress-Anker: bereits vorhandene Labels (lon/long/longitude) bleiben
    assert parse_coordinates("Lat: 46.5, Lon: 7.5") == (46.5, 7.5)
    assert parse_coordinates("Lat 46.5 Long 7.5") == (46.5, 7.5)
    assert parse_coordinates("latitude=46.5, longitude=7.5") == (46.5, 7.5)


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


def test_parse_coordinates_himmelsrichtung_fr_it_vollnamen():
    """FR/IT-Vollnamen der Himmelsrichtungen (Suisse romande, Ticino, Val d'Aosta).

    ``nord`` und ``sud`` sind bereits durch die DE-Alternativen abgedeckt (die
    ``-en``-Suffixe sind optional). Neu sind nur die Ost-/West-Wortstaemme mit
    FR-/IT-eigenstaendiger Schreibweise: FR ``est``/``ouest``, IT ``est``/
    ``ovest``.
    """
    # FR (Prefix-Form): Chamonix/Wallis/Val d'Anniviers-Sammlungs-Notizen
    assert parse_coordinates("Nord 46.5, Est 7.5") == (46.5, 7.5)
    assert parse_coordinates("Sud 46.5, Ouest 7.5") == (-46.5, -7.5)
    assert parse_coordinates("Nord 46.5, Ouest 7.5") == (46.5, -7.5)
    # IT (Prefix-Form): Ticino/Val Bavona/Val d'Aosta-Etiketten
    assert parse_coordinates("Nord 46.5, Ovest 7.5") == (46.5, -7.5)
    assert parse_coordinates("Sud 46.5, Est 7.5") == (-46.5, 7.5)
    # Decimal-Suffix-Form ("46.5° Est, 7.5° Ouest")
    assert parse_coordinates("46.5° Nord, 7.5° Est") == (46.5, 7.5)
    assert parse_coordinates("46.5° Nord, 7.5° Ovest") == (46.5, -7.5)
    # Case-insensitive
    assert parse_coordinates("NORD 46.5, EST 7.5") == (46.5, 7.5)
    assert parse_coordinates("sud 46.5, ovest 7.5") == (-46.5, -7.5)
    # Mit trailing Punkt nach Kurzform ("Est." aus Katalog-Abkuerzung)
    assert parse_coordinates("Nord. 46.5, Est. 7.5") == (46.5, 7.5)
    # Mit Labels kombiniert (Reihenfolge: erst Labels strippen, dann Richtung normalisieren)
    assert parse_coordinates("Lat: Nord 46.5, Lon: Est 7.5") == (46.5, 7.5)
    # Wort-Grenzen: "est" darf nicht in "test"/"best"/"estimated"/"established"
    # matchen, "ovest" darf nicht in "ovestern" matchen, "ouest" nicht in "ouesten"
    # matchen. Fundort-Feld mit Freitext, der ein solches Wort enthaelt und
    # zufaellig Koordinaten-aehnlich aussieht, darf nicht als Direction fehl-
    # normalisiert werden - hier keine Koordinaten-Erkennung erwartet.
    assert parse_coordinates("test 46.5, best 7.5") is None
    assert parse_coordinates("estimated 46.5, established 7.5") is None


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


def test_parse_coordinates_pipe_separator():
    """Pipe ``|`` als Separator (PSV-Files, MapInfo/QGIS-Pipe-Delimiter, GIS-Alternativ-Export).

    Pipe-Separator ist die de-facto Standard-Alternative fuer Locale-
    agnostische Datenbank-/GIS-Exporte in europaeischen Setups mit
    Komma-Dezimal-Locale (DE/FR/IT), wo Kommas als Feld-Separator
    mehrdeutig waeren. Typische Quellen: Plain-Text-Datenbank-Exporte
    (PSV-Files), SQLite-CLI-Text-Exporte mit Pipe-Delimiter, MapInfo-/
    QGIS-Attributtabellen-Exporte, GDAL/OGR-Text-Formate, sowie manche
    Bookmarking-Tools und Foto-Metadaten-Export-Werkzeuge mit Locale-
    unabhaengiger Feld-Trennung. Bisher fielen alle Pipe-getrennten
    Koordinaten still auf None, obwohl die beiden Zahl-Anteile eindeutig
    lesbar waren; symmetrisch zum Tab-/Ampersand-/Tilde-Separator-Precedent
    wird Pipe in die :data:`_DECIMAL_PAIR`-Separator-Klasse aufgenommen.
    """
    # Reines Pipe-Separator-Paar (PSV-File-Standard).
    assert parse_coordinates("46.5|7.5") == (46.5, 7.5)
    # Pipe + Whitespace-Padding (Formatierte GIS-Attribut-Exporte).
    assert parse_coordinates("46.5 | 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5| 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5 |7.5") == (46.5, 7.5)
    # DE-Komma-Dezimal + Pipe (Locale-agnostischer Export aus DE-Excel-
    # CSV nach PSV-Konvertierung).
    assert parse_coordinates("46,5|7,5") == (46.5, 7.5)
    # Mit Vorzeichen (negative Koordinaten aus GIS-Attribute).
    assert parse_coordinates("-46.5|-7.5") == (-46.5, -7.5)
    assert parse_coordinates("+46.5|+7.5") == (46.5, 7.5)
    # Mit Grad-Symbol und Himmelsrichtung (Suffix-Form aus GIS-Text-Export).
    assert parse_coordinates("46.5°|7.5°") == (46.5, 7.5)
    assert parse_coordinates("46.5°N|7.5°E") == (46.5, 7.5)
    assert parse_coordinates("46.5° S|7.5° W") == (-46.5, -7.5)
    # Out-of-range bleibt None (Validierung greift wie sonst).
    assert parse_coordinates("100|50") is None
    # Bestehende Separatoren weiterhin gueltig (kein Regress).
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5;7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5\t7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5~7.5") == (46.5, 7.5)


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


def test_parse_coordinates_colon_dm_ohne_sekunden():
    """Colon-Grad-Minuten-Form ohne Sekunden: '46:30 N, 7:45 E' (Consumer-
    GPS-Display bei zoom-out, maritime Log-Zeilen mit Sekunden = 0).

    Spiegelt die _DMS-Konvention (Minuten und Sekunden beide optional) auf
    die colon-lose Variante: sekunden-lose Form ``46:30 N`` mappt auf
    46 + 30/60 = 46.5 (Grad + Minutenanteil). Bisher fiel diese Form auf
    einen falschen Wert durch: das _DMS_COLON-Pattern verlangte drei Zahlen
    mit zwei Doppelpunkten (deg:min:sec), sodass die zwei-Zahlen-Form ``46:30
    N, 7:45 E`` durch fiel und die _DECIMAL_PAIR-Fallback-Extraktion nur die
    letzten zwei Zahlen (30 und 7) als Koordinaten-Paar erkannte - die Grad-
    Anteile 46 und 45 wurden ignoriert und der Sammler sah ``(30.0, 7.0)``
    statt der intendierten ``(46.5, 7.75)``. Aus Consumer-GPS-Displays und
    maritimen Log-Zeilen mit sekunden-frei angezeigten Positionen entstand
    damit silenter Koordinaten-Datenverlust.
    """
    # Standard mit Whitespace zwischen Minuten und Richtung
    assert parse_coordinates("46:30 N, 7:45 E") == (46.5, 7.75)
    # Ohne Whitespace zwischen Minuten und Richtung
    assert parse_coordinates("46:30N,7:45E") == (46.5, 7.75)
    # Verschiedene Pair-Separatoren
    assert parse_coordinates("46:30 N 7:45 E") == (46.5, 7.75)
    assert parse_coordinates("46:30 N; 7:45 E") == (46.5, 7.75)
    assert parse_coordinates("46:30 N / 7:45 E") == (46.5, 7.75)
    # Dezimal-Minuten (Punkt oder Komma)
    lat, lon = parse_coordinates("46:30.5 N, 7:45.5 E")
    assert abs(lat - (46 + 30.5/60)) < 1e-9
    assert abs(lon - (7 + 45.5/60)) < 1e-9
    lat, lon = parse_coordinates("46:30,5 N, 7:45,5 E")
    assert abs(lat - (46 + 30.5/60)) < 1e-9
    assert abs(lon - (7 + 45.5/60)) < 1e-9
    # Suedhalbkugel / Westhalbkugel
    assert parse_coordinates("46:30 S, 7:45 W") == (-46.5, -7.75)
    # O = Ost (deutsche Notation)
    assert parse_coordinates("46:30 N, 7:45 O") == (46.5, 7.75)
    # Case-insensitive Richtung
    assert parse_coordinates("46:30 n, 7:45 e") == (46.5, 7.75)
    # Null-gepolsterte Minuten (semantisch die reine Grad-Form)
    assert parse_coordinates("46:00 N, 7:00 E") == (46.0, 7.0)
    # Out-of-Range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("100:30 N, 7:45 E") is None
    assert parse_coordinates("46:30 N, 200:45 E") is None
    # Reine Zeit-Notation ohne Richtung bleibt None (Kollisions-Schutz gilt
    # weiterhin: die Himmelsrichtung ist obligatorisch)
    assert parse_coordinates("14:30") is None
    # Regression-Anker: DMS mit Sekunden (drei Zahlen) bleibt unveraendert
    assert parse_coordinates("46:30:15 N, 7:30:0 E") == (46.5 + 15/3600, 7.5)
    assert parse_coordinates("46:30:15.5 N, 7:30:0 E") == (
        46.5 + 15.5/3600, 7.5,
    )
    # Regression-Anker: DMS mit ° / ' / " bleibt unveraendert
    assert parse_coordinates("46° 30' 15\" N, 7° 30' 0\" E") == (
        46.5 + 15/3600, 7.5,
    )
    # Regression-Anker: dezimale Form bleibt unveraendert
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


def test_parse_coordinates_fullwidth_cjk_interpunktion():
    """Fullwidth-CJK-Interpunktion (U+FF0C ``，``, U+FF0E ``．``, U+FF0F ``／``)
    wird transparent auf ASCII normalisiert.

    Japanese/Chinese-IME liefern ``，``/``．``/``／`` als Default-Interpunktion
    (statt der ASCII-Aequivalente ``,``/``.``/``/``). Sammler mit CJK-Locale
    oder aus einem CJK-IME-Kontext kopiertem Text tippen die Koordinaten mit
    der Fullwidth-Form, ohne den Unterschied zu bemerken - die Zeichen sind
    monospace-visuell nur an der Breite unterscheidbar. Vor dem Fix fielen
    alle Fullwidth-Interpunktions-Formen still auf None, weil die _DECIMAL_PAIR-
    Separator-Klasse ``[ \\t,;/&]`` und der Decimal-Punkt der _NUM_RE-Zahl-
    Extraktion strikt ASCII-Zeichen verlangen. Fullwidth-Ziffern (U+FF10..
    U+FF19) sind bereits transparent behandelt, weil Python ``\\d`` per Default
    Unicode-Decimal matcht - nur die Interpunktion braucht den expliziten Strip.
    """
    # Fullwidth-Komma als Separator
    assert parse_coordinates("46.5，7.5") == (46.5, 7.5)
    # Fullwidth-Komma mit trailing Whitespace (typisch fuer copy-paste aus CJK)
    assert parse_coordinates("46.5， 7.5") == (46.5, 7.5)
    # Fullwidth-Full-Stop als Decimal-Punkt (Standard-IME-Output)
    assert parse_coordinates("46．5，7．5") == (46.5, 7.5)
    # Fullwidth-Solidus als Separator (spiegelt den ASCII-Slash-Zweig)
    assert parse_coordinates("46.5／7.5") == (46.5, 7.5)
    # Fullwidth-Komma mit ASCII-Vorzeichen
    assert parse_coordinates("-46.5，-7.5") == (-46.5, -7.5)
    # Fullwidth-Komma mit U+2212-Minus (beide Fixes greifen unabhaengig)
    assert parse_coordinates("−46.5，−7.5") == (-46.5, -7.5)
    # Fullwidth-Komma in DMS-/Prefix-Notation
    assert parse_coordinates("N46.5°，E7.5°") == (46.5, 7.5)
    # Fullwidth-Ziffern (U+FF10..U+FF19) sind schon vorher transparent
    # (Regression-Anker fuer Python-\\d-Unicode-Decimal-Semantik).
    assert parse_coordinates("４６.５，７.５") == (46.5, 7.5)
    # Out-of-range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("46.5，200.0") is None
    assert parse_coordinates("100.0，7.5") is None
    # Regression: ASCII-Interpunktion weiter gueltig
    assert parse_coordinates("46.5,7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5/7.5") == (46.5, 7.5)


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


def test_parse_coordinates_labeled_reversed_order():
    """Reversed-Order (Lon vor Lat) mit Labels: die Label-Semantik gewinnt gegenueber
    der Positions-Reihenfolge.

    OSM-Share-URLs, JavaScript-Mapping-API-JSON, GIS-Reports und Freitext-Notizen
    liefern Longitude und Latitude haeufig in umgekehrter Reihenfolge
    (``?mlon=X&mlat=Y``, ``?lng=X&lat=Y``, ``"Lon: 7.5, Lat: 46.5"``); das ist die
    geographisch uebliche (X, Y) = (Lon, Lat)-Konvention aus der Karten-Toolchain
    (WKT-POINT, GeoJSON, KML, Mapbox-Array-Encoding). Bisher wurde die publizierte
    Achsen-Zuordnung silente verworfen: :data:`_COORD_LABEL` strippte die Label-
    Woerter zu Whitespace, und :data:`_DECIMAL_PAIR` interpretierte die Auftritts-
    Reihenfolge als (lat, lon). Ergebnis: ``"Lon: 7.5, Lat: 46.5"`` -> (7.5, 46.5)
    statt (46.5, 7.5) - jede OSM-mlon-zuerst-URL, jedes Mapbox-lng-zuerst-JSON,
    jedes Excel-Kopiat mit Lon-vor-Lat-Spaltenreihenfolge und jede GIS-Datenbank
    mit (X, Y)-Achsen-Konvention produzierte silente Achsen-Vertauschung bei der
    Migration; besonders schwer erkennbar bei Schweizer/Alpen-Fundorten, weil
    (lat=7.5, lon=46.5) formal ein gueltiges Paar (Golf von Guinea nahe Sao Tome)
    ergibt und die _validate-Range-Pruefung erfolgreich durchlaeuft.
    """
    # OSM-Share-URLs mit reversed mlon/mlat (die Frontend-Spec ist tolerant gegen
    # Reihenfolge; verschiedene Client-Bibliotheken generieren die eine oder
    # die andere Reihenfolge)
    assert parse_coordinates(
        "https://www.openstreetmap.org/?mlon=7.5&mlat=46.5") == (46.5, 7.5)
    assert parse_coordinates("?mlon=7.5&mlat=46.5") == (46.5, 7.5)
    # Generische lat/lon-Params reversed
    assert parse_coordinates("?lon=7.5&lat=46.5") == (46.5, 7.5)
    assert parse_coordinates(
        "https://example.com/geo?lon=7.5&lat=46.5") == (46.5, 7.5)
    # Web-Mapping-API-lng-zuerst (Google Maps JS API, Leaflet, Mapbox GL) reversed
    assert parse_coordinates("?lng=7.5&lat=46.5") == (46.5, 7.5)
    assert parse_coordinates("lng=7.5&lat=46.5") == (46.5, 7.5)
    # Verbose latitude/longitude reversed
    assert parse_coordinates("?longitude=7.5&latitude=46.5") == (46.5, 7.5)
    # Case-insensitive reversed
    assert parse_coordinates("?MLON=7.5&MLAT=46.5") == (46.5, 7.5)
    assert parse_coordinates("?LNG=7.5&LAT=46.5") == (46.5, 7.5)
    # Reversed mit Vorzeichen (Suedhalbkugel/Westhalbkugel)
    assert parse_coordinates("?lon=-7.5&lat=-46.5") == (-46.5, -7.5)
    assert parse_coordinates("mlon=-7.5&mlat=-46.5") == (-46.5, -7.5)
    assert parse_coordinates("lng=-7.5&lat=-46.5") == (-46.5, -7.5)
    # Reversed mit DE-Komma-Dezimal (Excel-CSV DE-Locale)
    assert parse_coordinates("mlon=7,5&mlat=46,5") == (46.5, 7.5)
    # Freitext reversed mit Doppelpunkt
    assert parse_coordinates("Lon: 7.5, Lat: 46.5") == (46.5, 7.5)
    assert parse_coordinates("Longitude: 7.5, Latitude: 46.5") == (46.5, 7.5)
    assert parse_coordinates("longitudinal=7.5, lat=46.5") == (46.5, 7.5)
    # Freitext reversed mit Gleichheit
    assert parse_coordinates("lon=7.5 lat=46.5") == (46.5, 7.5)
    # Freitext reversed mit Long-Kurzform
    assert parse_coordinates("Lat 46.5 Long 7.5") == (46.5, 7.5)  # standard
    assert parse_coordinates("Long 7.5 Lat 46.5") == (46.5, 7.5)  # reversed
    # Deutsche Labels reversed
    assert parse_coordinates("Länge 7.5 Breite 46.5") == (46.5, 7.5)
    assert parse_coordinates("Länge: 7.5, Breite: 46.5") == (46.5, 7.5)
    assert parse_coordinates("laenge=7.5&breite=46.5") == (46.5, 7.5)
    assert parse_coordinates("längengrad: 7.5, breitengrad: 46.5") == (46.5, 7.5)
    # Direction-Buchstaben gewinnen gegen die Label-Semantik: wenn ein Sammler
    # die Labels vertauscht (``Lat: E7.5, Lon: N46.5``), aber die Direction
    # korrekt vergibt, soll das Ergebnis dennoch korrekt sein - _orient reagiert
    # auf N/S vs. E/W und sortiert um.
    assert parse_coordinates("Lat: E7.5, Lon: N46.5") == (46.5, 7.5)
    assert parse_coordinates("Lat: N46.5, Lon: E7.5") == (46.5, 7.5)
    # Direction-Suffix nach dem Wert (Standard-Sammler-Notation)
    assert parse_coordinates("Lat: 46.5° N, Lon: 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("Lat: 46.5° S, Lon: 7.5° W") == (-46.5, -7.5)
    assert parse_coordinates("Lon: 7.5° E, Lat: 46.5° N") == (46.5, 7.5)
    assert parse_coordinates("Lon: 7.5° W, Lat: 46.5° S") == (-46.5, -7.5)
    # Reversed mit trailing OSM-Fragment (haeufige Kombination in Share-URLs)
    assert parse_coordinates(
        "?mlon=7.5&mlat=46.5#map=15/46.5/7.5") == (46.5, 7.5)
    # Out-of-range greift auch in der Label-Route (definitiver Reject, kein
    # Fall-Through auf _DECIMAL_PAIR - die publizierte Label-Zuordnung ist
    # eindeutig, und ein Fallback auf die label-lose Route wuerde die
    # Achsen-Semantik verwerfen)
    assert parse_coordinates("lon=50&lat=100") is None
    assert parse_coordinates("mlon=200&mlat=46.5") is None
    # Nur eine Achse markiert -> Fall-Through auf bestehende Logik (Label-
    # Position ist mehrdeutig; das existierende Verhalten bleibt)
    assert parse_coordinates("Lat 46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("Lon 7.5, 46.5") == (7.5, 46.5)  # dokumentiertes Fallback
    # Regression: Standard-Reihenfolge (Lat vor Lon) bleibt unveraendert
    assert parse_coordinates("Lat: 46.5, Lon: 7.5") == (46.5, 7.5)
    assert parse_coordinates("mlat=46.5&mlon=7.5") == (46.5, 7.5)
    assert parse_coordinates("?lat=46.5&lon=7.5") == (46.5, 7.5)
    assert parse_coordinates("?lat=46.5&lng=7.5") == (46.5, 7.5)
    # Regression: DMS-Werte mit Labels fallen NICHT in die Plain-Decimal-Route
    # (End-Anker ``(?=$|[\s,;&?#/])`` verhindert DMS-Fortsetzung)
    assert parse_coordinates(
        "Lat: 46d 30m 15s N, Lon: 7d 30m 0s E") == (46.5 + 15/3600, 7.5)
    assert parse_coordinates(
        "Lat: 46°30'15\"N, Lon: 7°30'0\"E") == (46.5 + 15/3600, 7.5)
    # Regression: Formen ohne Label bleiben unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates(
        "https://www.google.com/maps/@46.5,7.5,15z") == (46.5, 7.5)


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


def test_parse_coordinates_prefix_dms():
    """Prefix-DMS-Notation: Himmelsrichtung VOR den Grad-/Minuten-/Sekunden-Zahlen.

    Standard-Notation in aelteren Marine-/Luftfahrt-Formaten, in einigen
    GPS-Tool-Exporten (NMEA-Konvertierungen, exiftool-GPS-Output mit
    Direction-First) und in Wikipedia-Koordinaten-Vorlagen der englischen
    Sprachversion ("N 46°30′15″ E 7°30′0″"). Vor dem Fix fielen alle Prefix-
    DMS-Formen still auf falsche Werte: _DMS.findall verlangte die Richtung
    am Ende und lieferte 0 Hits, und _PREFIX_PAIR akzeptierte das ° optional
    und griff nur mit den ersten beiden Zahlen (``N 46° 30' 15"`` wurde als
    (46.0, 30.0) gelesen - Minuten und Sekunden gingen verloren).
    """
    expected_lat = 46.5 + 15 / 3600
    # Standard-Form mit Whitespace zwischen Richtung, Grad, Minuten, Sekunden
    lat, lon = parse_coordinates("N 46° 30' 15\" E 7° 30' 0\"")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # Compact-Form ohne Whitespace zwischen Richtung und Zahlen
    lat, lon = parse_coordinates("N46°30'15\"E7°30'0\"")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # Dezimal-Minuten-Variante (Grad + Dezimal-Minuten, keine Sekunden)
    lat, lon = parse_coordinates("N 46° 30.25' E 7° 30.0'")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # Suedhalbkugel / Westhalbkugel
    lat, lon = parse_coordinates("S 46° 30' 15\" W 7° 30' 0\"")
    assert abs(lat - -expected_lat) < 1e-9
    assert lon == -7.5
    # Reihenfolge lon, lat (Prefix-Direction reorientiert korrekt via _orient)
    lat, lon = parse_coordinates("E 7° 30' 0\" N 46° 30' 15\"")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # O = Ost (deutsche Notation)
    lat, lon = parse_coordinates("N 46° 30' 15\" O 7° 30' 0\"")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # Case-insensitive
    lat, lon = parse_coordinates("n 46° 30' 15\" e 7° 30' 0\"")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # Vollnamen der Himmelsrichtungen werden vorher auf N/O normalisiert
    lat, lon = parse_coordinates("Nord 46° 30' 15\" Ost 7° 30' 0\"")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # Typografische Minuten-/Sekunden-Zeichen (′ U+2032, ″ U+2033) - Wikipedia-
    # Konvention in Koordinaten-Vorlagen.
    lat, lon = parse_coordinates("N 46°30′15″ E 7°30′0″")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.5
    # DE-Komma-Dezimal in den Sekunden
    lat, lon = parse_coordinates("N 46° 30' 15,5\" E 7° 30' 0\"")
    assert abs(lat - (46.5 + 15.5 / 3600)) < 1e-9
    assert lon == 7.5
    # Nur Grad + Richtung ohne Minuten/Sekunden (degenerierter Fall, gleicher
    # Wert wie via _PREFIX_PAIR)
    assert parse_coordinates("N 46.5° E 7.5°") == (46.5, 7.5)
    # Out-of-Range bleibt None (Validierung greift wie sonst)
    assert parse_coordinates("N 100° 30' 15\" E 7° 30' 0\"") is None
    assert parse_coordinates("N 46° 30' 15\" E 200° 30' 0\"") is None
    # Regress: bestehende Suffix-DMS-Form bleibt unveraendert
    assert parse_coordinates("46° 30' 15\" N, 7° 30' 0\" E") == (
        46.5 + 15 / 3600, 7.5,
    )
    # Regress: Prefix-Decimal ohne ° weiter via _PREFIX_PAIR
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("N 46.5 E 7.5") == (46.5, 7.5)
    # Regress: dezimale Form weiter unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)


def test_parse_coordinates_prefix_ddm_ohne_prime_marker():
    """Prefix-DDM-Notation ohne Prime-Marker: ``N 46°30.5 E 7°45.3`` /
    ``N 46° 30.5 E 7° 45.3``. Standard-Ausgabe-Modus fuer alle Consumer-GPS-
    Geraete-Anzeigen (Garmin/Magellan/TomTom im "hddd° mm.mmm'"-Modus),
    marine/Luftfahrt-Kartensysteme (BSH-Karten, IHO-S-57), Wikipedia-Coord-
    Template-Ausgabe (``{{Coord|46|30.5|N|7|45.3|E}}``) sowie GPS-Log-Textfelder
    ohne typografische Prime-Zeichen.

    Bisher fiel die DDM-Notation ohne Prime-Marker still auf einen partiellen
    Match des _DMS_PREFIX-Zweigs: die Minuten-Gruppe scheiterte am fehlenden
    ``'``, das Pattern-Match brach nach dem Grad-Teil ab, und die naechste
    findall-Iteration griff den Rest als eigenen (Dir, Deg)-Match - die
    Dezimalminuten ``.5``/``.3`` gingen dabei silent verloren
    (``N 46°30.5 E 7°45.3`` -> (46.0, 7.0) statt (46.508..., 7.755)).

    Der Dezimalpunkt-Zwang der prime-losen Alternante ``\\d+[.,]\\d+`` schuetzt
    vor Kollision mit Integer-Anhaeufungen ohne Marker (``N 46° 30 E`` bleibt
    (46.0, ...), weil ``30`` keine Dezimalstellen hat und die Prime-lose
    Alternante nicht matcht - die Ambiguitaet zu Katalog-Nummer/Sample-ID/
    Anzahl-Vermerk ueberwiegt den Erkennungs-Gewinn).
    """
    expected_lat = 46.0 + 30.5 / 60  # 46.508333...
    expected_lon = 7.0 + 45.3 / 60   # 7.755
    # Basisform ohne Whitespace zwischen Grad und Minuten
    lat, lon = parse_coordinates("N 46°30.5 E 7°45.3")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # Mit Whitespace zwischen Grad und Minuten
    lat, lon = parse_coordinates("N 46° 30.5 E 7° 45.3")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # DE-Komma-Dezimal (Excel-DE-Export)
    lat, lon = parse_coordinates("N 46°30,5 E 7°45,3")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # Compact ohne Whitespace um Richtung
    lat, lon = parse_coordinates("N46°30.5E7°45.3")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # Suedhalbkugel / Westhalbkugel
    lat, lon = parse_coordinates("S 46°30.5 W 7°45.3")
    assert abs(lat - -expected_lat) < 1e-9
    assert abs(lon - -expected_lon) < 1e-9
    # Case-insensitive
    lat, lon = parse_coordinates("n 46°30.5 e 7°45.3")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # Vollnamen der Himmelsrichtungen werden vorher auf N/O normalisiert
    lat, lon = parse_coordinates("Nord 46°30.5 Ost 7°45.3")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # O = Ost (DE-Notation)
    lat, lon = parse_coordinates("N 46°30.5 O 7°45.3")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # Reihenfolge lon, lat (Prefix-Direction reorientiert korrekt via _orient)
    lat, lon = parse_coordinates("E 7°45.3 N 46°30.5")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # Nur einer der beiden hat Dezimalstellen (die Integer-Seite bleibt reine
    # Grad-Form, die Decimal-Seite wird als DDM erkannt)
    lat, lon = parse_coordinates("N 46°30.5 E 7°")
    assert abs(lat - expected_lat) < 1e-9
    assert lon == 7.0
    # Umgekehrt: Grad ohne Minuten auf Lat, DDM auf Lon
    lat, lon = parse_coordinates("N 46° E 7°45.3")
    assert lat == 46.0
    assert abs(lon - expected_lon) < 1e-9
    # Grenzfaelle Aequator/Null-Meridian
    assert parse_coordinates("N 0°0.0 E 0°0.0") == (0.0, 0.0)
    # +/-90/+/-180-Extreme
    lat, lon = parse_coordinates("N 89°59.9 E 179°59.9")
    assert abs(lat - (89.0 + 59.9 / 60)) < 1e-9
    assert abs(lon - (179.0 + 59.9 / 60)) < 1e-9
    # Out-of-Range Lat/Lon bleibt None
    assert parse_coordinates("N 100°30.5 E 7°45.3") is None
    assert parse_coordinates("N 46°30.5 E 200°45.3") is None
    # Regress-Anker: bestehende Formen bleiben unveraendert
    # Prime-Form mit Dezimal-Minuten (DDM mit Prime)
    lat, lon = parse_coordinates("N 46°30.5' E 7°45.3'")
    assert abs(lat - expected_lat) < 1e-9
    assert abs(lon - expected_lon) < 1e-9
    # Ganzzahl-Minuten mit Prime (DMS klassisch)
    lat, lon = parse_coordinates("N 46°30' E 7°45'")
    assert abs(lat - 46.5) < 1e-9
    assert abs(lon - (7.0 + 45.0 / 60)) < 1e-9
    # Vollstaendige DMS mit Sekunden (Prime obligatorisch)
    lat, lon = parse_coordinates("N 46°30'15\" E 7°45'30\"")
    assert abs(lat - (46.5 + 15 / 3600)) < 1e-9
    assert abs(lon - (7.0 + 45.0 / 60 + 30 / 3600)) < 1e-9
    # Ganzzahl-Minuten OHNE Prime bleibt ambig: nur Grad-Anteil wird gelesen
    # (Kollisions-Schutz gegen Katalog-Nummer/Sample-ID/Anzahl-Vermerk)
    assert parse_coordinates("N 46° 30 E 7°") == (46.0, 7.0)
    # Reine Prefix-Decimal (kein Grad-Marker) weiter via _PREFIX_PAIR
    assert parse_coordinates("N 46.5 E 7.5") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    # Suffix-DMS-Form (Direction NACH Zahl) weiter via _DMS
    assert parse_coordinates("46°30'15\" N, 7°45'30\" E") == (
        46.5 + 15 / 3600, 7.0 + 45 / 60 + 30 / 3600,
    )


def test_parse_coordinates_osm_hash_map_fragment():
    """OSM-URL-Hash-Fragment "#map=<zoom>/<lat>/<lon>" korrekt entpacken.

    Standard-Share-Format der OpenStreetMap-JavaScript-Karte und uebernommen
    von zahlreichen OSM-Derivaten (openstreetmap.de, waymarkedtrails.org,
    uMap, OpenTopoMap): das erste Slash-getrennte Feld ist der Zoom-Level
    (0-19 typisch), die naechsten zwei sind Lat/Lon. Vor dem Fix fiel jeder
    OSM-Share-Link auf ein semantisch falsches Paar - ``"#map=15/46.5/7.5"``
    wurde von _DECIMAL_PAIR als (15.0, 46.5) gelesen, weil das Pattern die
    ersten beiden Slash-getrennten Zahlen greift und Zoom-Level als Latitude
    interpretiert. Aus einem typischen Sammler-Workflow "Fundort in OSM
    anzeigen -> Share-URL kopieren -> ins Fundort-Feld einfuegen" entstand
    silenter Koordinaten-Datenverlust bei der Migration.
    """
    # Vollstaendige OSM-URL mit Hash-Fragment
    assert parse_coordinates(
        "https://www.openstreetmap.org/#map=15/46.5/7.5") == (46.5, 7.5)
    # Nur Fragment ohne URL-Kontext (Sammler kopiert nur den Hash-Teil)
    assert parse_coordinates("#map=15/46.5/7.5") == (46.5, 7.5)
    # Zusaetzliche Layer-Parameter nach den Koordinaten
    assert parse_coordinates(
        "https://www.openstreetmap.org/#map=15/46.5/7.5&layers=N") == (46.5, 7.5)
    # Fraktionaler Zoom (neuere OSM-Versionen erlauben Nicht-Ganzzahl-Zoom)
    assert parse_coordinates("#map=15.5/46.5/7.5") == (46.5, 7.5)
    # Case-Insensitivitaet (OSM-Frontends akzeptieren Uppercase-Variante)
    assert parse_coordinates("#MAP=15/46.5/7.5") == (46.5, 7.5)
    # Suedhalbkugel / Westhalbkugel (Vorzeichen an Lat/Lon)
    assert parse_coordinates("#map=15/-33.85/151.2") == (-33.85, 151.2)
    assert parse_coordinates("#map=10/-46.5/-7.5") == (-46.5, -7.5)
    # DE-Komma-Dezimal (aus DE-Locale-Kontext, wenn der Browser die
    # dezimalen Trenner beim Copy-Paste in die DE-Locale umformt)
    assert parse_coordinates("#map=15/46,5/7,5") == (46.5, 7.5)
    # OSM-Derivat mit gleichem Fragment-Format
    assert parse_coordinates(
        "https://openstreetmap.de/karte.html?zoom=15#map=15/46.5/7.5") == (
        46.5, 7.5)
    assert parse_coordinates(
        "https://opentopomap.org/#map=15/46.5/7.5") == (46.5, 7.5)
    # Fragment eingebettet in Freitext (Sammler-Notizen wie "siehe X")
    assert parse_coordinates(
        "siehe https://www.openstreetmap.org/#map=15/46.5/7.5") == (46.5, 7.5)
    # Out-of-range Lat/Lon -> None (Validierung greift, kein Fallback auf
    # _DECIMAL_PAIR das sonst die Zoom-Lat-Reihenfolge zurueckdrehen wuerde)
    assert parse_coordinates("#map=15/91.0/181.0") is None
    assert parse_coordinates("#map=15/-91.0/7.5") is None
    assert parse_coordinates("#map=15/46.5/181.0") is None
    # Kombination mit bereits vorhandenen mlat/mlon-Params (Regression:
    # der bestehende Test test_parse_coordinates_url_query_params deckt
    # das Kombinationsverhalten mit denselben Koordinaten ab)
    assert parse_coordinates(
        "?mlat=46.5&mlon=7.5#map=15/46.5/7.5") == (46.5, 7.5)
    # Regress: Formen ohne #map-Fragment bleiben unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates(
        "https://www.google.com/maps/@46.5,7.5,15z") == (46.5, 7.5)
    assert parse_coordinates(
        "https://www.openstreetmap.org/?mlat=46.5&mlon=7.5") == (46.5, 7.5)


def test_parse_coordinates_bing_maps_tilde_separator():
    """Tilde ``~`` als Separator - Bing-Maps-URL-Center-Point-Form (``cp=lat~lon``).

    Bing Maps verwendet in seiner Share-URL-Spec den Query-Parameter
    ``cp`` (Center Point) mit ``~`` als Lat-Lon-Trenner: ``bing.com/maps?
    cp=46.5~7.5&lvl=15``. Diese Form ist die von Bing-Frontends selbst
    generierte Copy-URL, wenn der Sammler auf "Share" klickt oder die URL
    aus dem Browser-Adress-Feld kopiert. Auch aeltere Bing-Derivate (ehem.
    maps.live.com, bing.com/mapspreview) und in Bing-basierte Karten-Widgets
    eingebundene iframe-URLs verwenden dieselbe ``~``-Konvention. Ohne
    ``~`` in der _DECIMAL_PAIR-Separator-Klasse fielen alle Bing-Share-URLs
    stille auf None: _PREFIX_PAIR verlangt Richtungs-Buchstaben (N/S/E/W/O),
    _SUFFIX_PAIR_NO_SEP ebenso, und _ISO6709_COMPACT_DECIMAL ist auf
    ``^...$`` verankert und toleriert kein URL-Praefix.
    """
    # Standard Bing-Share-URL mit cp-Query-Parameter
    assert parse_coordinates(
        "https://www.bing.com/maps?cp=46.5~7.5&lvl=15") == (46.5, 7.5)
    # Ohne trailing Query-Parameter
    assert parse_coordinates(
        "https://www.bing.com/maps?cp=46.5~7.5") == (46.5, 7.5)
    # Ohne www-Subdomain (Bing akzeptiert beide Formen)
    assert parse_coordinates(
        "https://bing.com/maps?cp=46.5~7.5&lvl=15") == (46.5, 7.5)
    # Reines cp-Query-Fragment ohne URL-Kontext
    assert parse_coordinates("cp=46.5~7.5") == (46.5, 7.5)
    # Reines Zahlen-Paar mit Tilde-Separator (Bing-cp-Form ohne Label)
    assert parse_coordinates("46.5~7.5") == (46.5, 7.5)
    # Mit Whitespace um die Tilde (tolerante Copy-Paste-Form)
    assert parse_coordinates("46.5 ~ 7.5") == (46.5, 7.5)
    # Mit Vorzeichen (Suedhalbkugel/Westhalbkugel)
    assert parse_coordinates(
        "https://bing.com/maps?cp=-46.5~-7.5&lvl=15") == (-46.5, -7.5)
    assert parse_coordinates("-46.5~-7.5") == (-46.5, -7.5)
    # Negatives Vorzeichen nur auf einer Achse (Nord/West-Kombination)
    assert parse_coordinates("46.5~-7.5") == (46.5, -7.5)
    # DE-Komma-Dezimal in Lat/Lon (Bing-DE-Locale-Frontends schreiben so)
    assert parse_coordinates(
        "https://www.bing.com/maps?cp=46,5~7,5&lvl=15") == (46.5, 7.5)
    # Mit vorherigen Query-Parametern (rp/where davor ist Bing-typisch)
    assert parse_coordinates(
        "https://www.bing.com/maps?rp=~&cp=46.5~7.5&lvl=15") == (46.5, 7.5)
    # Out-of-Range Lat -> None (Validierung greift wie sonst)
    assert parse_coordinates("cp=100~50") is None
    # Out-of-Range Lon -> None
    assert parse_coordinates("cp=46.5~200") is None
    # Regression: leading Tilde als Approximations-Praefix (aus dem Datum-
    # Parser bekannt) blockiert die Zahl-Paar-Erkennung nicht - das .search()
    # skippt vor den Tilden bis zur ersten Ziffer.
    assert parse_coordinates("~46.5, 7.5") == (46.5, 7.5)
    # Regression: bestehende Separatoren weiterhin gueltig
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5\t7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5&7.5") == (46.5, 7.5)
    # Regression: Google-Maps-@-URL bleibt Komma-getrennt
    assert parse_coordinates(
        "https://www.google.com/maps/@46.5,7.5,15z") == (46.5, 7.5)
    # Regression: einzelne Zahl ohne Trenner (auch mit ~) bleibt None
    assert parse_coordinates("46.5") is None
    assert parse_coordinates("~46.5") is None


def test_parse_coordinates_wkt_point():
    """WKT-POINT-Notation (OGC Simple Features / ISO 19125) - Standard-
    Serialisierungs-Form fuer Punkt-Geometrien aus GIS-Werkzeugketten.

    PostGIS ST_AsText, GeoPandas .to_wkt, QGIS "Copy as WKT", ogr2ogr,
    ArcGIS Feature-to-Text und jeder Shapefile-Export-Pfad ueber GEOS/GDAL
    liefern die WKT-Form. Die OGC-Achsen-Konvention ist fix (X Y) mit
    X=Longitude, Y=Latitude - unabhaengig von der EPSG-Konvention (Lat
    zuerst). Ohne diesen Zweig fiele jeder WKT-POINT-Text durch das
    Whitespace-Separator-Muster von :data:`_DECIMAL_PAIR` und lieferte
    silente Achsen-Vertauschung ((7.5, 46.5) statt (46.5, 7.5)).
    """
    # Basisform ohne Whitespace nach POINT
    assert parse_coordinates("POINT(7.5 46.5)") == (46.5, 7.5)
    # Mit Whitespace nach POINT (auch OGC-Standard-Variante)
    assert parse_coordinates("POINT (7.5 46.5)") == (46.5, 7.5)
    # Case-Insensitivitaet (verschiedene WKT-Ausgabepfade)
    assert parse_coordinates("point (7.5 46.5)") == (46.5, 7.5)
    assert parse_coordinates("Point(7.5 46.5)") == (46.5, 7.5)
    assert parse_coordinates("PoInT(7.5 46.5)") == (46.5, 7.5)
    # 3D-Form (Z-Achse fuer Elevation) - Z wird ignoriert
    assert parse_coordinates("POINT Z (7.5 46.5 800)") == (46.5, 7.5)
    assert parse_coordinates("POINTZ(7.5 46.5 800)") == (46.5, 7.5)
    # Measure-Form (M-Achse fuer linear-referenced measure)
    assert parse_coordinates("POINT M (7.5 46.5 42)") == (46.5, 7.5)
    assert parse_coordinates("POINTM(7.5 46.5 42)") == (46.5, 7.5)
    # 3D + Measure (ZM-Form)
    assert parse_coordinates("POINT ZM (7.5 46.5 800 42)") == (46.5, 7.5)
    assert parse_coordinates("POINTZM(7.5 46.5 800 42)") == (46.5, 7.5)
    # Vorzeichen auf Lon
    assert parse_coordinates("POINT(-7.5 46.5)") == (46.5, -7.5)
    assert parse_coordinates("POINT(+7.5 46.5)") == (46.5, 7.5)
    # Vorzeichen auf Lat
    assert parse_coordinates("POINT(7.5 -46.5)") == (-46.5, 7.5)
    # Beide negativ (Sued-West-Kombination)
    assert parse_coordinates("POINT(-7.5 -46.5)") == (-46.5, -7.5)
    # EWKT-Prefix mit SRID (PostGIS-Erweiterung)
    assert parse_coordinates("SRID=4326;POINT(7.5 46.5)") == (46.5, 7.5)
    assert parse_coordinates(
        "SRID=4326 ; POINT (7.5 46.5)") == (46.5, 7.5)
    # DE-Komma-Dezimal (Sammler-typisch bei Excel-Export mit DE-Locale)
    assert parse_coordinates("POINT(7,5 46,5)") == (46.5, 7.5)
    # Scientific-Notation in den Koordinaten
    assert parse_coordinates("POINT(7.5e0 4.65e1)") == (46.5, 7.5)
    # Fuehrende/Trailing Whitespace
    assert parse_coordinates("  POINT(7.5 46.5)  ") == (46.5, 7.5)
    # Out-of-Range Lon -> None (Validierung greift wie sonst)
    assert parse_coordinates("POINT(200 46.5)") is None
    # Out-of-Range Lat -> None
    assert parse_coordinates("POINT(7.5 91.0)") is None
    # Aequator/Null-Meridian (Grenzfaelle)
    assert parse_coordinates("POINT(0 0)") == (0.0, 0.0)
    assert parse_coordinates("POINT(180 90)") == (90.0, 180.0)
    assert parse_coordinates("POINT(-180 -90)") == (-90.0, -180.0)
    # Regression: alle bestehenden Zahl-Paar-Formen bleiben (kein Regress)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("#map=15/46.5/7.5") == (46.5, 7.5)
    # Regression: MULTIPOINT/LINESTRING sind nicht abgedeckt und faellen
    # (semantisch korrekt) zurueck auf das Fallback-Verhalten - kein Datum-
    # Umsprung, sondern Sammler soll manuell Einzel-Punkt extrahieren.
    # (Die alte _DECIMAL_PAIR-Extraktion greift dann, was hier semantisch
    # falsch waere - aber der WKT-Zweig blockt MULTIPOINT bewusst nicht,
    # weil eine Point-Menge nicht eindeutig auf einen Fundort abbildbar
    # ist.)
    # Freitext-Praefix vor POINT (kein WKT, matcht nicht mehr)
    assert parse_coordinates("Location: POINT(7.5 46.5)") != (46.5, 7.5)
    # Fehlender zweiter Wert -> None (kein halbes POINT)
    assert parse_coordinates("POINT(7.5)") is None
    # Fehlende Klammern -> kein WKT-Match, fallback auf _DECIMAL_PAIR
    # (das dann silente Vertauschung liefert - erwartet und dokumentiert)
    assert parse_coordinates("POINT 7.5 46.5") == (7.5, 46.5)


def test_parse_iso_date_monat_underscore_separator():
    """Monatsname-Notation mit Underscore ``_`` als Filename-sicherem Separator
    zwischen Monatsname und Jahr: ``Juni_2024`` / ``July_2020`` / ``Sep_1985``.

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[,./ \\-]`` von
    :data:`_MONTH_YEAR` um den Underscore. In Foto-/Sammlungs-Archiven ist der
    Underscore der zuverlaessigste Cross-Plattform-Filename-Trenner (kein
    Reserved-Char in Windows/POSIX, keine locale-abhaengige Interpretation);
    Foto-Software-Auto-Rename und massenhafte Datei-Umbenennung normalisieren
    Leerzeichen typischerweise auf ``_``. Bisher fielen alle Filename-
    abgeleiteten Monatsname-Jahr-Formen mit Underscore auf None (silenter
    Funddatum-Datenverlust). Mapping identisch zur Ein-Zeichen-Separator-Form
    (erster Tag des Monats).
    """
    # Voll ausgeschriebene DE-Monatsnamen mit Underscore
    assert parse_iso_date("Januar_2024") == "2024-01-01"
    assert parse_iso_date("Juni_2024") == "2024-06-01"
    assert parse_iso_date("Juli_2020") == "2020-07-01"
    assert parse_iso_date("Dezember_1985") == "1985-12-01"
    assert parse_iso_date("August_2020") == "2020-08-01"
    # Voll ausgeschriebene EN-Monatsnamen mit Underscore
    assert parse_iso_date("January_2024") == "2024-01-01"
    assert parse_iso_date("July_2020") == "2020-07-01"
    assert parse_iso_date("December_1985") == "1985-12-01"
    assert parse_iso_date("August_2020") == "2020-08-01"
    # Abgekuerzte Monatsnamen (DE/EN) mit Underscore
    assert parse_iso_date("Jan_2024") == "2024-01-01"
    assert parse_iso_date("Jun_2024") == "2024-06-01"
    assert parse_iso_date("Sep_1985") == "1985-09-01"
    assert parse_iso_date("Dec_1985") == "1985-12-01"
    # Abgekuerzte Monatsnamen mit Punkt-Suffix und Underscore ("Jun._2024",
    # "Sep._1985") - Kombination der ``\\.?``-Punkt-Toleranz mit dem neuen
    # Underscore-Separator; kommt in Foto-Software-Auto-Rename-Regeln vor,
    # die den Punkt der Abkuerzung nicht strippen und nur Whitespace auf
    # Underscore mappen.
    assert parse_iso_date("Jun._2024") == "2024-06-01"
    assert parse_iso_date("Sep._1985") == "1985-09-01"
    # Case-Insensitivitaet (Foto-Software mit uppercase-Auto-Rename)
    assert parse_iso_date("JUNI_2024") == "2024-06-01"
    assert parse_iso_date("juli_2020") == "2020-07-01"
    assert parse_iso_date("SEP_1985") == "1985-09-01"
    # Kombiniert mit Annaeherungspraefix / Klammer-Strip
    assert parse_iso_date("ca. Juni_2024") == "2024-06-01"
    assert parse_iso_date("[Juli_2020]") == "2020-07-01"
    # Kollisionsschutz: unbekannte Nicht-Monatsname-Woerter mit Underscore-
    # Jahr-Struktur fallen weiterhin auf None (nur eindeutige Monatsnamen
    # sollen matchen)
    assert parse_iso_date("Foo_2024") is None
    assert parse_iso_date("Sample_2024") is None
    assert parse_iso_date("Bar_1985") is None
    # Kollisionsschutz: mehrere Underscores in Folge (fehlerhafte Filename-
    # Auto-Rename-Regel) mangeln die Struktur und liefern None statt einer
    # silenten Fehl-Interpretation ("Juni__2024" hat 2 Underscores und
    # matcht die Separator-Klasse nicht als Einzel-Zeichen).
    assert parse_iso_date("Juni__2024") is None
    # Kollisionsschutz: Underscore-Kompositum ohne Monatsname faellt auf
    # None (nur der Monatsname-Slot ist ausgeschriebener Wort-Slot).
    assert parse_iso_date("_Juni_2024") is None
    assert parse_iso_date("Juni_2024_") is None
    # Kollisionsschutz: Underscore mit Praeposition-Kombination faellt auf
    # den bereits vorhandenen Praepositions-Zweig durch - "Juli_von_2024"
    # ist keine natuerlichsprachige Notation und liefert None.
    assert parse_iso_date("Juli_von_2024") is None
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert und die Praepositions-Alternante bleibt aktiv.
    assert parse_iso_date("Juni 2024") == "2024-06-01"
    assert parse_iso_date("Juni-2024") == "2024-06-01"
    assert parse_iso_date("Juni/2024") == "2024-06-01"
    assert parse_iso_date("Juni.2024") == "2024-06-01"
    assert parse_iso_date("Juni, 2024") == "2024-06-01"
    assert parse_iso_date("Juli von 2024") == "2024-07-01"
    assert parse_iso_date("July of 2024") == "2024-07-01"


def test_parse_iso_date_saison_underscore_separator():
    """Jahreszeit-Notation mit Underscore ``_`` als Filename-sicherem Separator
    zwischen Saison-Wort und Jahr: ``Sommer_2024`` / ``Winter_1985`` /
    ``summer_2020`` / ``Fruehjahr_2020``.

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[, ]?`` von
    :data:`_SEASON_YEAR` um den Underscore, symmetrisch zur
    ``_MONTH_YEAR``-Underscore-Erweiterung. In Foto-/Sammlungs-Archiven
    ordnen Sammler ihre Sammelaktionen und Ausflug-Fotos oft nach Saison
    ein ("Aare_Sommer_2024.jpg", "Bergtour_Winter_1985/",
    "Fund_Herbst_2020.pdf") - der Underscore ist der Filename-sichere
    Trenner, den Foto-Software-Auto-Rename und massenhafte Datei-
    Umbenennung typischerweise setzen. Mapping identisch zur Ein-Zeichen-
    Separator-Form (Saison-Startmonat).
    """
    # DE-Saisons mit Underscore
    assert parse_iso_date("Sommer_2024") == "2024-06-01"
    assert parse_iso_date("Winter_1985") == "1985-12-01"
    assert parse_iso_date("Herbst_2020") == "2020-09-01"
    assert parse_iso_date("Fruehjahr_2020") == "2020-03-01"
    assert parse_iso_date("Fruehling_2024") == "2024-03-01"
    # EN-Saisons mit Underscore
    assert parse_iso_date("summer_2020") == "2020-06-01"
    assert parse_iso_date("spring_2024") == "2024-03-01"
    assert parse_iso_date("autumn_2020") == "2020-09-01"
    assert parse_iso_date("fall_2020") == "2020-09-01"
    assert parse_iso_date("winter_1985") == "1985-12-01"
    # DE-Kompositum-Formen (Fruehsommer/Spaetsommer/Fruehherbst/Spaetherbst)
    # mit Underscore - die Modifikator-Praefixe schieben den Saison-Startmonat
    # jeweils an den Rand der Saison; symmetrisch zur Space-Separator-Form.
    assert parse_iso_date("Spaetsommer_2024") == "2024-08-01"
    assert parse_iso_date("Fruehsommer_2024") == "2024-06-01"
    assert parse_iso_date("Spaetherbst_2020") == "2020-11-01"
    # Case-Insensitivitaet (Foto-Software mit uppercase-Auto-Rename)
    assert parse_iso_date("SOMMER_2024") == "2024-06-01"
    assert parse_iso_date("winter_1985") == "1985-12-01"
    assert parse_iso_date("WINTER_1985") == "1985-12-01"
    # Kombiniert mit Annaeherungspraefix / Klammer-Strip
    assert parse_iso_date("ca. Sommer_2024") == "2024-06-01"
    assert parse_iso_date("[Winter_1985]") == "1985-12-01"
    # Kollisionsschutz: unbekannte Nicht-Saison-Woerter mit Underscore-Jahr-
    # Struktur fallen weiterhin auf None (nur eindeutige Saison-Wortstammes
    # sollen matchen)
    assert parse_iso_date("Foo_2024") is None
    assert parse_iso_date("Sample_2024") is None
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert und die Praepositions-Alternante bleibt aktiv.
    assert parse_iso_date("Sommer 2024") == "2024-06-01"
    assert parse_iso_date("Sommer, 2024") == "2024-06-01"
    assert parse_iso_date("Sommer2024") == "2024-06-01"
    assert parse_iso_date("summer of 2024") == "2024-06-01"
    assert parse_iso_date("Sommer von 2024") == "2024-06-01"


def test_parse_iso_date_year_month_name_underscore_separator():
    """Year-first Monatsname-Notation mit Underscore ``_`` als Filename-sicherem
    Separator zwischen Jahr und Monatsname (``2024_Juli`` / ``1985_June`` /
    ``2020_Sep``) und optional zwischen Monatsname und Tag (``2024_Juli_15``
    / ``2024_June_15`` / ``2024_July_1st``).

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[,./ \\-]`` von
    :data:`_YEAR_MONTH_NAME` und :data:`_YEAR_MONTH_NAME_DAY` um den
    Underscore, symmetrisch zur ``_MONTH_YEAR``- und
    ``_SEASON_YEAR``-Underscore-Erweiterung. Year-first-Filename-Konvention
    (Jahr als sortierender Praefix) ist der de-facto Standard in Foto-
    Library-Sortierungen und Backup-Rotation-Ordnern (``2024_Juli_Aare.jpg``,
    ``2024_June_Tucson-Boerse/``, ``2020_Sep_Bergtour_15.pdf``); der
    Underscore ist der zuverlaessigste Cross-Plattform-Filename-Trenner.
    Mapping identisch zur Ein-Zeichen-Separator-Form (erster Tag des
    Monats bei nur Jahr+Monat, expliziter Tag bei Jahr+Monat+Tag).
    """
    # Year-first Jahr + Monatsname mit Underscore (voll ausgeschrieben DE/EN)
    assert parse_iso_date("2024_Juli") == "2024-07-01"
    assert parse_iso_date("2024_January") == "2024-01-01"
    assert parse_iso_date("1985_June") == "1985-06-01"
    assert parse_iso_date("2020_December") == "2020-12-01"
    # Year-first mit abgekuerztem Monatsnamen und Underscore
    assert parse_iso_date("2020_Sep") == "2020-09-01"
    assert parse_iso_date("2024_Jun") == "2024-06-01"
    assert parse_iso_date("1985_Dec") == "1985-12-01"
    # Year-first Jahr + Monatsname + Tag mit Underscore-Separator auf beiden
    # Positionen (Konvention _YEAR_MONTH_NAME_DAY)
    assert parse_iso_date("2024_Juli_15") == "2024-07-15"
    assert parse_iso_date("2024_June_15") == "2024-06-15"
    assert parse_iso_date("2024_January_15") == "2024-01-15"
    # Year-first mit englischem Tag-Ordinal-Suffix und Underscore
    assert parse_iso_date("2024_July_1st") == "2024-07-01"
    assert parse_iso_date("2024_June_15th") == "2024-06-15"
    # Case-Insensitivitaet (Foto-Software mit uppercase-Auto-Rename)
    assert parse_iso_date("2024_JUNI") == "2024-06-01"
    assert parse_iso_date("2024_JULI_15") == "2024-07-15"
    # Mixed-Separator-Kombination (typisch bei Copy-paste aus einem
    # gemischten Fluss-Etikett - Jahr-Space-Monat gefolgt von Underscore-Tag):
    assert parse_iso_date("2024 Juni_15") == "2024-06-15"
    assert parse_iso_date("2024-Juni_15") == "2024-06-15"
    assert parse_iso_date("2024_Juni-15") == "2024-06-15"
    # Kollisionsschutz: unbekannte Nicht-Monatsname-Woerter mit Underscore-
    # Struktur fallen weiterhin auf None
    assert parse_iso_date("2024_Sample") is None
    assert parse_iso_date("2024_Foo") is None
    assert parse_iso_date("2024_Sample_15") is None
    assert parse_iso_date("2024_Foo_15") is None
    # Kombiniert mit Annaeherungspraefix / Klammer-Strip
    assert parse_iso_date("ca. 2024_Juli") == "2024-07-01"
    assert parse_iso_date("[2024_June_15]") == "2024-06-15"
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert.
    assert parse_iso_date("2024 Juli") == "2024-07-01"
    assert parse_iso_date("2024-Juli") == "2024-07-01"
    assert parse_iso_date("2024/Juli") == "2024-07-01"
    assert parse_iso_date("2024.Juli") == "2024-07-01"
    assert parse_iso_date("2024,Juli") == "2024-07-01"
    assert parse_iso_date("2024-Juli-15") == "2024-07-15"
    assert parse_iso_date("2024/July/15") == "2024-07-15"


def test_parse_iso_date_year_first_saison_underscore_separator():
    """Year-first Jahreszeit-Notation mit Underscore ``_`` als Filename-sicherem
    Separator zwischen Jahr und Saison-Wort (``2024_Sommer`` / ``1985_Winter``
    / ``2020_summer`` / ``2024_Fruehjahr``).

    Ergaenzt die Ein-Zeichen-Separator-Klasse ``[/.\\-, ]`` von
    :data:`_SEASON_YEAR_FIRST` um den Underscore, symmetrisch zur
    ``_SEASON_YEAR``-Underscore-Erweiterung (Commit f8e2bea) und zur
    ``_YEAR_MONTH_NAME``-Underscore-Erweiterung (Commit 530b589). In
    Foto-Library-Sortierungen und Backup-Rotation-Ordnern (``2024_Sommer_Aare/``,
    ``2024_Winter_Alpen-Fund.jpg``, ``2020_Herbst_Bergtour.pdf``) ordnet das
    Jahr als sortierender Praefix die Datei-Explorer-Ansicht chronologisch,
    und der Underscore ist der zuverlaessigste Cross-Plattform-Filename-
    Trenner. Mapping identisch zur Ein-Zeichen-Separator-Form (Saison-
    Startmonat aus _SEASON_MONTHS).
    """
    # Year-first Jahr + DE-Saison mit Underscore
    assert parse_iso_date("2024_Sommer") == "2024-06-01"
    assert parse_iso_date("1985_Winter") == "1985-12-01"
    assert parse_iso_date("2020_Herbst") == "2020-09-01"
    assert parse_iso_date("2024_Fruehjahr") == "2024-03-01"
    assert parse_iso_date("2024_Fruehling") == "2024-03-01"
    # Year-first Jahr + EN-Saison mit Underscore
    assert parse_iso_date("2020_summer") == "2020-06-01"
    assert parse_iso_date("2024_spring") == "2024-03-01"
    assert parse_iso_date("2020_autumn") == "2020-09-01"
    assert parse_iso_date("2020_fall") == "2020-09-01"
    assert parse_iso_date("1985_winter") == "1985-12-01"
    # DE-Kompositum-Formen (Fruehsommer/Spaetsommer/Fruehherbst/Spaetherbst)
    # mit Underscore - Randmonat-Anker der Saison
    assert parse_iso_date("2024_Spaetsommer") == "2024-08-01"
    assert parse_iso_date("2024_Fruehsommer") == "2024-06-01"
    assert parse_iso_date("2020_Spaetherbst") == "2020-11-01"
    # Case-Insensitivitaet (Foto-Software mit uppercase-Auto-Rename)
    assert parse_iso_date("2024_SOMMER") == "2024-06-01"
    assert parse_iso_date("1985_WINTER") == "1985-12-01"
    # Kombiniert mit Annaeherungspraefix / Klammer-Strip
    assert parse_iso_date("ca. 2024_Sommer") == "2024-06-01"
    assert parse_iso_date("[1985_Winter]") == "1985-12-01"
    # Kollisionsschutz: unbekannte Nicht-Saison-Woerter mit Underscore-Jahr-
    # Struktur fallen weiterhin auf None
    assert parse_iso_date("2024_Sample") is None
    assert parse_iso_date("2024_Foo") is None
    # Regress-Anker: die bisherigen Ein-Zeichen-Separator-Formen bleiben
    # unveraendert.
    assert parse_iso_date("2024 Sommer") == "2024-06-01"
    assert parse_iso_date("2024-Winter") == "2024-12-01"
    assert parse_iso_date("2024/Herbst") == "2024-09-01"
    assert parse_iso_date("2024.Fruehjahr") == "2024-03-01"
    assert parse_iso_date("2024,Sommer") == "2024-06-01"


def test_parse_iso_date_periodenmarker_underscore_separator():
    """Perioden-Marker-Kurzformen (Q/H/KW/CW/W) mit Underscore ``_`` als
    Filename-sicherem Separator zwischen Marker und Jahr (``Q1_2024`` /
    ``H1_2024`` / ``KW25_2024`` / ``W25_2024``) sowie Year-First-Formen
    (``2024_Q1`` / ``2024_H1`` / ``2024_KW25``).

    Ergaenzt die Ein-Zeichen-Separator-Klassen von :data:`_QUARTER_SHORT`,
    :data:`_QUARTER_YEAR_FIRST`, :data:`_HALFYEAR_SHORT`,
    :data:`_HALFYEAR_YEAR_FIRST`, :data:`_KW_YEAR` und
    :data:`_KW_YEAR_FIRST` um den Underscore. In Geschaefts-Perioden-
    Reports (Excel-Auto-Fill, Buchhaltungs-Perioden-Stempel) und Foto-
    Library-Sortierungen (``Q1_2024_Bericht.pdf``, ``H1_2024_Umsatz/``,
    ``KW25_2024_Aare-Bergtour.jpg``) ist der Underscore der zuverlaessigste
    Cross-Plattform-Filename-Trenner. Mapping identisch zu den bestehenden
    Ein-Zeichen-Separator-Formen: Q1->Jan, Q2->Apr, Q3->Jul, Q4->Okt;
    H1->Jan, H2->Jul; KW/CW/W->Montag der Woche.
    """
    # Quartal Kurzform Year-Last mit Underscore
    assert parse_iso_date("Q1_2024") == "2024-01-01"
    assert parse_iso_date("Q2_2024") == "2024-04-01"
    assert parse_iso_date("Q3_1985") == "1985-07-01"
    assert parse_iso_date("Q4_2020") == "2020-10-01"
    assert parse_iso_date("1Q_2024") == "2024-01-01"
    assert parse_iso_date("3Q_1985") == "1985-07-01"
    # Quartal Kurzform Year-First mit Underscore
    assert parse_iso_date("2024_Q1") == "2024-01-01"
    assert parse_iso_date("2024_Q3") == "2024-07-01"
    assert parse_iso_date("1985_Q4") == "1985-10-01"
    # Halbjahr Kurzform Year-Last mit Underscore
    assert parse_iso_date("H1_2024") == "2024-01-01"
    assert parse_iso_date("H2_1985") == "1985-07-01"
    assert parse_iso_date("1H_2024") == "2024-01-01"
    assert parse_iso_date("2H_1985") == "1985-07-01"
    # Halbjahr Kurzform Year-First mit Underscore
    assert parse_iso_date("2024_H1") == "2024-01-01"
    assert parse_iso_date("2024_H2") == "2024-07-01"
    # KW Year-Last mit Underscore
    assert parse_iso_date("KW25_2024") == "2024-06-17"
    assert parse_iso_date("KW1_2024") == "2024-01-01"
    assert parse_iso_date("CW25_2024") == "2024-06-17"
    assert parse_iso_date("W25_2024") == "2024-06-17"
    # KW Year-First mit Underscore
    assert parse_iso_date("2024_KW25") == "2024-06-17"
    assert parse_iso_date("2024_W25") == "2024-06-17"
    assert parse_iso_date("2024_CW25") == "2024-06-17"
    # Case-Insensitivitaet
    assert parse_iso_date("q1_2024") == "2024-01-01"
    assert parse_iso_date("h1_2024") == "2024-01-01"
    assert parse_iso_date("kw25_2024") == "2024-06-17"
    # Kombiniert mit Annaeherungspraefix / Klammer-Strip
    assert parse_iso_date("ca. Q1_2024") == "2024-01-01"
    assert parse_iso_date("[H1_2024]") == "2024-01-01"
    # Kollisionsschutz: Nicht-Q-/H-/KW-/W-Prefixe fallen weiterhin auf None
    assert parse_iso_date("K1_2024") is None
    assert parse_iso_date("J1_2024") is None
    assert parse_iso_date("Q5_2024") is None  # Q5 kein gueltiges Quartal
    assert parse_iso_date("H3_2024") is None  # H3 kein gueltiges Halbjahr
    # Regress-Anker: bisherige Ein-Zeichen-Separator-Formen unveraendert
    assert parse_iso_date("Q1 2024") == "2024-01-01"
    assert parse_iso_date("Q1/2024") == "2024-01-01"
    assert parse_iso_date("Q1-2024") == "2024-01-01"
    assert parse_iso_date("Q1.2024") == "2024-01-01"
    assert parse_iso_date("Q1,2024") == "2024-01-01"
    assert parse_iso_date("H1 2024") == "2024-01-01"
    assert parse_iso_date("H1/2024") == "2024-01-01"
    assert parse_iso_date("KW25 2024") == "2024-06-17"
    assert parse_iso_date("2024 Q1") == "2024-01-01"
    assert parse_iso_date("2024/Q1") == "2024-01-01"
    assert parse_iso_date("2024-Q1") == "2024-01-01"
    assert parse_iso_date("2024Q1") == "2024-01-01"
    assert parse_iso_date("2024 KW 25") == "2024-06-17"
    # Praepositions-Alternante bleibt aktiv
    assert parse_iso_date("Q1 von 2024") == "2024-01-01"
    assert parse_iso_date("H1 of 2024") == "2024-01-01"
    assert parse_iso_date("KW 25 von 2024") == "2024-06-17"


def test_parse_coordinates_geojson_point():
    """GeoJSON-Point-Notation (RFC 7946) - Achsen-Reihenfolge (Lon, Lat).

    Aus JSON-basierten GIS-Werkzeugketten (geojson.io, Mapbox, Leaflet,
    Folium, geopandas .to_json(), QGIS "Save As... GeoJSON", ogr2ogr -f
    GeoJSON, Overpass-Turbo, Nominatim ``format=geojson``) und API-Response-
    Snippets. RFC 7946 §3.1.1 fixiert die Reihenfolge (Longitude, Latitude)
    im Coordinates-Array; ohne diesen Zweig fielen alle GeoJSON-Point-Texte
    durch :data:`_DECIMAL_PAIR` (Komma-Separator im ``[X, Y]``-Array) und
    lieferten silente Achsen-Vertauschung ((7.5, 46.5) statt (46.5, 7.5)).
    """
    # Basisform (voller GeoJSON-Point mit Type und Coordinates)
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [7.5, 46.5]}') == (46.5, 7.5)
    # Coordinates VOR Type (JSON-Member-Reihenfolge ist per spec unerheblich)
    assert parse_coordinates(
        '{"coordinates": [7.5, 46.5], "type": "Point"}') == (46.5, 7.5)
    # Kompakte Form ohne Whitespace um den Doppelpunkt / im Array
    assert parse_coordinates(
        '{"type":"Point","coordinates":[7.5,46.5]}') == (46.5, 7.5)
    # Formatiert mit Zeilenumbruechen (pretty-print aus geojson.io)
    assert parse_coordinates(
        '{\n  "type": "Point",\n  "coordinates": [7.5, 46.5]\n}') == (46.5, 7.5)
    # Case-Insensitivitaet auf Type=Point (nicht-kanonische Casing aus JS-Codegen)
    assert parse_coordinates(
        '{"type": "point", "coordinates": [7.5, 46.5]}') == (46.5, 7.5)
    assert parse_coordinates(
        '{"type": "POINT", "coordinates": [7.5, 46.5]}') == (46.5, 7.5)
    # Single-Quotes statt Double-Quotes (Python-Repr-Form)
    assert parse_coordinates(
        "{'type': 'Point', 'coordinates': [7.5, 46.5]}") == (46.5, 7.5)
    # Elevation als drittes Element (RFC 7946 §3.1.1 SHOULD-Klausel)
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [7.5, 46.5, 800]}') == (46.5, 7.5)
    # Vorzeichen auf Lon / Lat
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [-7.5, 46.5]}') == (46.5, -7.5)
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [7.5, -46.5]}') == (-46.5, 7.5)
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [-7.5, -46.5]}') == (-46.5, -7.5)
    # Wissenschaftliche Notation (JSON-Spec erlaubt E±N)
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [7.5e0, 4.65e1]}') == (46.5, 7.5)
    # Feature-Wrapper (der Type-Marker der Geometry gewinnt, weil er direkt
    # neben dem Coordinates-Feld steht - Sammler kopiert ganze Feature-JSON
    # aus geojson.io oder Overpass-Turbo)
    assert parse_coordinates(
        '{"type": "Feature", "geometry": {"type": "Point", '
        '"coordinates": [7.5, 46.5]}, "properties": {}}') == (46.5, 7.5)
    # Grenzfaelle: Aequator/Null-Meridian, Pol-Nord-Ost-Ecke
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [0, 0]}') == (0.0, 0.0)
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [180, 90]}') == (90.0, 180.0)
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [-180, -90]}') == (-90.0, -180.0)
    # Out-of-Range Lon -> None
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [200, 46.5]}') is None
    # Out-of-Range Lat -> None
    assert parse_coordinates(
        '{"type": "Point", "coordinates": [7.5, 91.0]}') is None
    # Fehlender Type-Marker -> Fallback auf _DECIMAL_PAIR (silente Vertauschung,
    # weil kein GeoJSON-Achsen-Signal vorliegt - dokumentiert). Sammler soll
    # den vollen GeoJSON-Snippet mit Type-Feld kopieren, nicht nur den Array.
    assert parse_coordinates('"coordinates": [7.5, 46.5]') == (7.5, 46.5)
    # Fehlendes Coordinates-Feld -> None (kein GeoJSON-Match, kein Zahl-Paar
    # im Rest der Type-Deklaration)
    assert parse_coordinates('{"type": "Point"}') is None
    # Type=MultiPoint/LineString/Polygon -> kein Match (semantisch nicht als
    # Einzelpunkt-Fundort abbildbar, faellt auf Fallback zurueck)
    assert parse_coordinates(
        '{"type": "MultiPoint", "coordinates": [[7.5, 46.5], [8.0, 47.0]]}'
    ) != (46.5, 7.5)
    assert parse_coordinates(
        '{"type": "LineString", "coordinates": [[7.5, 46.5], [8.0, 47.0]]}'
    ) != (46.5, 7.5)
    # Fuehrende/Trailing Whitespace um den ganzen JSON-Blob
    assert parse_coordinates(
        '  {"type": "Point", "coordinates": [7.5, 46.5]}  ') == (46.5, 7.5)
    # Regression: alle bestehenden Formen bleiben unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("#map=15/46.5/7.5") == (46.5, 7.5)
    assert parse_coordinates("POINT(7.5 46.5)") == (46.5, 7.5)


def test_parse_coordinates_geo_uri_rfc5870():
    """GeoURI-Notation (RFC 5870) - Standard-URI-Schema fuer Geo-Koordinaten.

    Verbreitet in Android-Maps-Intents (``geo:`` aus der Android-Developer-Doc:
    jeder "In Karten oeffnen"-Link aus Nachrichten-/Kalender-Apps), vCard v4
    (RFC 6350 §6.5.2 GEO-Property), iCalendar RFC 7986 (VEVENT GEO-Property,
    Sammler-Kalender-Export mit Fundort-Termin), QR-Code-Standard-Encoding
    fuer Standort-QR-Codes (Feld-/Museums-Schilder) und div. Karten-Apps.
    RFC 5870 §3.3 fixiert die Reihenfolge (Latitude, Longitude, [Altitude]) -
    im Gegensatz zur GeoJSON-/WKT-Konvention (Lon, Lat); Altitude und
    Parameter (``;crs=``, ``;u=``) werden semantisch ignoriert. Standardform
    (RFC 5870 §3.1): ``geo:<lat>,<lon>[,<alt>][;param=value...]``.
    """
    # Basisform (RFC 5870 §3.1 kanonisches Beispiel)
    assert parse_coordinates("geo:46.5,7.5") == (46.5, 7.5)
    # Mit Altitude (drittes Element, RFC 5870 §3.4)
    assert parse_coordinates("geo:46.5,7.5,100") == (46.5, 7.5)
    # Mit Uncertainty-Parameter (RFC 5870 §3.4.3, ``u=`` in Metern)
    assert parse_coordinates("geo:46.5,7.5;u=65") == (46.5, 7.5)
    # Mit CRS-Parameter (RFC 5870 §3.4.2, WGS84 als Default und einziger
    # obligatorisch unterstuetzter Wert)
    assert parse_coordinates("geo:46.5,7.5;crs=wgs84") == (46.5, 7.5)
    # Mit Altitude, CRS und Uncertainty kombiniert (voller Parameter-Satz)
    assert parse_coordinates(
        "geo:46.5,7.5,100;crs=wgs84;u=10") == (46.5, 7.5)
    # Uppercase-Scheme (RFC 3986 spec: URI-Schemes sind Case-Insensitive)
    assert parse_coordinates("GEO:46.5,7.5") == (46.5, 7.5)
    # Mixed-Case-Scheme
    assert parse_coordinates("Geo:46.5,7.5") == (46.5, 7.5)
    # Vorzeichen auf Lat/Lon (Suedhalbkugel / Westhalbkugel)
    assert parse_coordinates("geo:-33.85,151.2") == (-33.85, 151.2)
    assert parse_coordinates("geo:46.5,-7.5") == (46.5, -7.5)
    assert parse_coordinates("geo:-46.5,-7.5") == (-46.5, -7.5)
    # Explizites Plus-Vorzeichen (RFC 5870 laesst optionales ``+`` zu)
    assert parse_coordinates("geo:+46.5,+7.5") == (46.5, 7.5)
    # Ganzzahl-Werte (kein Dezimalpunkt)
    assert parse_coordinates("geo:46,7") == (46.0, 7.0)
    # Aequator/Null-Meridian (Null Island - formal gueltig)
    assert parse_coordinates("geo:0,0") == (0.0, 0.0)
    # Pol-Nord-Ost-Ecke (Grenzfall der Range-Pruefung)
    assert parse_coordinates("geo:90,180") == (90.0, 180.0)
    assert parse_coordinates("geo:-90,-180") == (-90.0, -180.0)
    # Whitespace um den Doppelpunkt (tolerante Copy-Paste-Form)
    assert parse_coordinates("geo: 46.5,7.5") == (46.5, 7.5)
    # Fuehrende/Trailing Whitespace um den ganzen URI
    assert parse_coordinates("  geo:46.5,7.5  ") == (46.5, 7.5)
    # Zoom-Query (Google Maps Android-Extension, spec-konform als Query)
    assert parse_coordinates("geo:46.5,7.5?z=15") == (46.5, 7.5)
    # Zusaetzliche Query-Parameter (spec-konform als generisches URI-Query)
    assert parse_coordinates("geo:46.5,7.5?z=15&label=Zermatt") == (46.5, 7.5)
    # Out-of-Range Lat -> None (Validierung greift wie sonst)
    assert parse_coordinates("geo:91,7.5") is None
    assert parse_coordinates("geo:-91,7.5") is None
    # Out-of-Range Lon -> None
    assert parse_coordinates("geo:46.5,200") is None
    assert parse_coordinates("geo:46.5,-200") is None
    # Regression: alle bestehenden Formen bleiben unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("#map=15/46.5/7.5") == (46.5, 7.5)
    assert parse_coordinates("POINT(7.5 46.5)") == (46.5, 7.5)


def test_parse_coordinates_geo_uri_android_intent():
    """Google-Maps-Android-Intent-Form ``geo:0,0?q=<lat>,<lon>[(<label>)]``.

    Offizielle Android-Developer-Doc-Konvention (siehe
    ``developer.android.com/guide/components/intents-common#Maps``) fuer
    "Zeige Standort mit Label" und "Zeige Suchergebnis an Position":
    der ``geo:``-Pfad enthaelt die Platzhalter-Koordinaten ``0,0``
    (Null Island), die *echten* Koordinaten stehen im ``?q=<lat>,<lon>``-
    Query mit optionalem Label in Klammern. Diese Form entsteht typischerweise,
    wenn der Sammler den "Teilen"-Button in Google Maps drueckt und den
    generierten Intent-URI aus dem Share-Sheet kopiert (in eine Notiz-App,
    einen Chat, in eine E-Mail). Ohne diesen expliziten Zweig gewinnt der
    ``0,0``-Match aus dem geo-Pfad und der Sammler bekommt silente Null-
    Island-Koordinaten statt seiner tatsaechlichen Position - besonders
    schwer erkennbar, weil (0,0) formal ein gueltiges Lat/Lon-Paar ist und
    die _validate-Range-Pruefung erfolgreich durchlaeuft.
    """
    # Standardform (Placeholder-Path + q mit Koordinaten)
    assert parse_coordinates("geo:0,0?q=46.5,7.5") == (46.5, 7.5)
    # Mit Label in Klammern (RFC-3986-sub-delims-kompatibel)
    assert parse_coordinates("geo:0,0?q=46.5,7.5(Zermatt)") == (46.5, 7.5)
    # Label mit Whitespace und mehreren Woertern
    assert parse_coordinates(
        "geo:0,0?q=47.037,7.749(Some Long Label With Spaces)"
    ) == (47.037, 7.749)
    # Case-Insensitivitaet auf Scheme (Android-Codegen produziert lowercase,
    # aber Copy-Paste aus Terminal/Log-Output kann Uppercase liefern)
    assert parse_coordinates("GEO:0,0?q=46.5,7.5") == (46.5, 7.5)
    # Vorzeichen auf Query-Koordinaten (Suedhalbkugel-Fundorte)
    assert parse_coordinates("geo:0,0?q=-33.85,151.2") == (-33.85, 151.2)
    assert parse_coordinates("geo:0,0?q=-46.5,-7.5") == (-46.5, -7.5)
    # Placeholder-Path mit .0-Dezimal-Notation (Android-Codegen-Variante)
    assert parse_coordinates("geo:0.0,0.0?q=46.5,7.5") == (46.5, 7.5)
    # Whitespace um den Doppelpunkt / q-Wert (tolerante Form)
    assert parse_coordinates("geo:0,0?q= 46.5, 7.5") == (46.5, 7.5)
    # Query-Koordinaten Out-of-Range -> None (Validierung greift)
    assert parse_coordinates("geo:0,0?q=91,7.5") is None
    assert parse_coordinates("geo:0,0?q=46.5,200") is None
    # Regression: q mit Textadresse (kein Zahl-Paar) faellt auf die generische
    # GeoURI-Form zurueck und liefert die Placeholder-Koordinaten (0,0). Der
    # Sammler soll in diesem Fall die tatsaechliche Adresse manuell aufloesen
    # und nachtragen; die (0,0)-Rueckgabe ist der eindeutig identifizierbare
    # "keine echten Koordinaten"-Marker.
    assert parse_coordinates("geo:0,0?q=Zermatt") == (0.0, 0.0)
    assert parse_coordinates(
        "geo:0,0?q=my+street+address") == (0.0, 0.0)
    # Regression: geo: mit echten Koordinaten im Pfad UND q-Text-Label
    # (spec-konform, siehe Android-Doc "Show given location with matching
    # address as the label") - die Pfad-Koordinaten gewinnen
    assert parse_coordinates("geo:46.5,7.5?q=Zermatt") == (46.5, 7.5)
    # RFC-5870-Parameter-Segment (``;u=<meters>`` fuer Uncertainty in
    # Metern, ``;crs=<name>`` fuer Coordinate-Reference-System) zwischen
    # Basis-Koordinaten und Query-String - RFC-konform und von einigen
    # nicht-Android-Karten-Apps sowie von RFC-5870-strikten Geocoder-
    # Bibliotheken (pygeouri, geopy) erzeugt. Vor diesem Zweig fielen
    # solche Formen still auf die Placeholder-Koordinaten (0,0) durch,
    # weil das Android-Query-Pattern nur ``\s*\?`` zwischen Basis-Koord
    # und Query-Marker akzeptierte und der ``;``-Parameter-Block dazwischen
    # das Anker-Matching blockte.
    assert parse_coordinates(
        "geo:0,0;u=25?q=46.5,7.5") == (46.5, 7.5)
    assert parse_coordinates(
        "geo:0,0;crs=wgs84?q=46.5,7.5") == (46.5, 7.5)
    assert parse_coordinates(
        "geo:0,0;crs=wgs84;u=25?q=46.5,7.5(Fundstelle)") == (46.5, 7.5)
    # RFC-5870-Parameter kombiniert mit optionaler Altitude im
    # Placeholder-Koord (drittes Komma-Feld)
    assert parse_coordinates(
        "geo:0,0,100;u=25?q=46.5,7.5(Fund)") == (46.5, 7.5)
    # Regression: alle bestehenden Formen bleiben unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("geo:46.5,7.5") == (46.5, 7.5)
    # Regression: RFC-5870-Parameter OHNE q= liefert weiterhin die reinen
    # Basis-Koord ueber :data:`_GEO_URI` (dokumentiertes Fallback)
    assert parse_coordinates("geo:0,0;u=25") == (0.0, 0.0)
    assert parse_coordinates("geo:46.5,7.5;u=25") == (46.5, 7.5)


def test_parse_coordinates_google_place_3d_4d_fragment():
    """Google-Maps-Place-URL-Protobuf-Fragment ``!3d<lat>!4d<lon>``.

    Diese Form entsteht, wenn der Sammler in Google Maps einen Ort
    antippt (statt nur die Karte zu scrollen) und den Share-Link kopiert.
    Die URL enthaelt dann zwei semantisch unterschiedliche Koordinaten-
    Paare: ``@<lat>,<lon>,<zoom>z`` fuer den View-Center (Kamera-Position)
    und ``!3d<lat>!4d<lon>`` im ``/data=``-Segment fuer die tatsaechliche
    Pin-Position des angeklickten Ortes. Die Pin-Position ist der
    semantisch publizierte Wert und muss den View-Center-Match ueberholen -
    sonst bekaeme der Sammler bei "heraus-gezoomt teilen" die zufaellige
    Zoom-abhaengige Kamera-Position statt seiner Fundort-Koordinaten.
    """
    # Full place URL: !3d!4d identisch mit @-URL (zoom-in-Sonderfall)
    assert parse_coordinates(
        "https://www.google.com/maps/place/Zermatt/@46.0207,7.7491,15z"
        "/data=!4m5!3m4!1s0x0:0x0!8m2!3d46.0207!4d7.7491"
    ) == (46.0207, 7.7491)
    # Full place URL: !3d!4d weichen ab vom @-URL-View-Center (heraus-
    # gezoomt teilen) - der Pin gewinnt, nicht der Kamera-Standort
    assert parse_coordinates(
        "https://www.google.com/maps/place/Zermatt/@46.5,7.5,6z"
        "/data=!4m5!3m4!1s0x0:0x0!8m2!3d46.0207!4d7.7491"
    ) == (46.0207, 7.7491)
    # Nur das Fragment ohne URL-Kontext (Sammler kopiert nur das
    # /data=-Segment aus der Adress-Leiste)
    assert parse_coordinates("!3d46.0207!4d7.7491") == (46.0207, 7.7491)
    assert parse_coordinates("data=!3d46.0207!4d7.7491") == (46.0207, 7.7491)
    # Mit vorherigen Protobuf-Markern (typisch fuer echte Google-URLs)
    assert parse_coordinates("!4m5!3m4!1s0x0:0x0!8m2!3d46.5!4d7.5") == (46.5, 7.5)
    # Mit trailing Marker (!16z fuer Feature-ID) nach dem Pin-Paar
    assert parse_coordinates(
        "!3d46.5!4d7.5!16zL20vMDNqamY") == (46.5, 7.5)
    # Vorzeichen auf beiden Achsen (Suedhalbkugel/Westhalbkugel)
    assert parse_coordinates("!3d-33.85!4d151.2") == (-33.85, 151.2)
    assert parse_coordinates("!3d-46.5!4d-7.5") == (-46.5, -7.5)
    # Vorzeichen nur auf einer Achse (Nord/West-Kombination)
    assert parse_coordinates("!3d46.5!4d-7.5") == (46.5, -7.5)
    # Explizites +-Vorzeichen (unueblich, aber spec-konform)
    assert parse_coordinates("!3d+46.5!4d+7.5") == (46.5, 7.5)
    # Case-Insensitivitaet (!3D/!4D aus manuell nachbearbeiteten URLs)
    assert parse_coordinates("!3D46.5!4D7.5") == (46.5, 7.5)
    # DE-Komma-Dezimal (Excel-Zwischenkopie mit DE-Locale)
    assert parse_coordinates("!3d46,5!4d7,5") == (46.5, 7.5)
    # Ganzzahlige Koordinaten (Grenzfall)
    assert parse_coordinates("!3d46!4d7") == (46.0, 7.0)
    # Null-Island (Grenzfall, aber gueltig)
    assert parse_coordinates("!3d0!4d0") == (0.0, 0.0)
    # Grenzwerte
    assert parse_coordinates("!3d90.0!4d180.0") == (90.0, 180.0)
    assert parse_coordinates("!3d-90.0!4d-180.0") == (-90.0, -180.0)
    # Out-of-Range Lat -> None
    assert parse_coordinates("!3d91.0!4d7.5") is None
    # Out-of-Range Lon -> None
    assert parse_coordinates("!3d46.5!4d200.0") is None
    # Fehlender !4d-Marker -> Fallback auf None (kein anderes Zahl-Paar
    # in der Eingabe)
    assert parse_coordinates("!3d46.5") is None
    # !5d anstelle von !4d -> nicht die Pin-Position (Feld-Index-Konvention
    # verletzt) -> Fallback greift, keine Koordinaten in Eingabe -> None
    assert parse_coordinates("!3d46.5!5d100") is None
    # Freitext-Ausrufezeichen mit "3d"-/"4d"-Substrings (Fotoshooting,
    # 3D-Modell-Notation) - kein Match, weil die Marker eine unmittelbar
    # folgende Zahl verlangen und die Freitext-Semantik davon abweicht.
    assert parse_coordinates("Wow! 3d-Fotoshooting!") is None
    # Regression: URL ohne !3d!4d-Fragment faellt auf @-URL-Center
    # (bestehendes Verhalten)
    assert parse_coordinates(
        "https://www.google.com/maps/@46.5,7.5,15z") == (46.5, 7.5)
    # Regression: Standard-Dezimal-Paar bleibt unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    # Regression: OSM-Query-Param-Form bleibt unveraendert
    assert parse_coordinates(
        "https://www.openstreetmap.org/?mlat=46.5&mlon=7.5") == (46.5, 7.5)
    # Regression: GeoURI-Form bleibt unveraendert
    assert parse_coordinates("geo:46.5,7.5") == (46.5, 7.5)


def test_parse_coordinates_yandex_maps_ll_lon_lat_order():
    """Yandex-Maps-URL-Konvention: ``ll=`` und ``pt=`` sind (Longitude, Latitude).

    Yandex Maps ist der einzige verbreitete Karten-Anbieter, dessen Share-URL-
    Konvention der Google/Apple/Bing/OSM-Standard-Reihenfolge (Latitude, Longitude)
    widerspricht - die offizielle Yandex-Maps-API-Doku gibt ``ll=<longitude>,
    <latitude>`` fix vor, und der Placemark-Parameter ``pt=<lon>,<lat>[,<marker>]``
    folgt derselben Konvention. Vor dem Fix wurde jede Yandex-Share-URL vom
    generischen :data:`_DECIMAL_PAIR`-Zweig als (Lat, Lon) fehlinterpretiert und
    lieferte silente Achsen-Vertauschung: aus ``ll=7.5,46.5`` (Longitude 7.5,
    Latitude 46.5) wurde ``(7.5, 46.5)`` (Latitude 7.5, Longitude 46.5). Der
    Fix spiegelt strukturell den WKT-POINT-, den GeoJSON-Point- und den
    OSM-Hash-Map-Zweig auf die Yandex-URL-Achse.
    """
    # Basis-URL mit ll= (Longitude 7.5, Latitude 46.5)
    assert parse_coordinates("https://yandex.com/maps/?ll=7.5,46.5") == (46.5, 7.5)
    # Regionale TLDs (Yandex laeuft in mehreren Laenderdomains)
    assert parse_coordinates("https://yandex.ru/maps/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("yandex.by/maps/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("yandex.kz/maps/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("yandex.com.tr/maps/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("yandex.ua/maps/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("yandex.uz/maps/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("yandex.fr/maps/?ll=7.5,46.5") == (46.5, 7.5)
    # ymaps.ru URL-Shortener
    assert parse_coordinates("ymaps.ru/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("https://ymaps.ru/?ll=7.5,46.5") == (46.5, 7.5)
    # Historischer maps.yandex.<tld>-Subdomain-Pfad
    assert parse_coordinates("https://maps.yandex.ru/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("maps.yandex.com/?ll=7.5,46.5") == (46.5, 7.5)
    # Trailing Zoom-Parameter
    assert parse_coordinates(
        "https://yandex.com/maps/?ll=7.5,46.5&z=15") == (46.5, 7.5)
    # Mehrere Query-Params vor ll=
    assert parse_coordinates(
        "https://yandex.com/maps/?text=Zermatt&ll=7.5,46.5&z=10") == (46.5, 7.5)
    assert parse_coordinates(
        "https://yandex.com/maps/?mode=search&text=quartz&ll=7.5,46.5"
    ) == (46.5, 7.5)
    # pt= Placemark-Parameter (identische Lon-Lat-Konvention)
    assert parse_coordinates("https://yandex.com/maps/?pt=7.5,46.5") == (46.5, 7.5)
    # pt= mit Marker-Style-Suffix (dritter Wert, wird ignoriert)
    assert parse_coordinates(
        "https://yandex.com/maps/?pt=7.5,46.5,pm2rdm") == (46.5, 7.5)
    assert parse_coordinates(
        "https://yandex.com/maps/?pt=7.5,46.5,flag") == (46.5, 7.5)
    # URL-encoded Komma (%2C) - vom generischen Preprocess-Strip normalisiert
    assert parse_coordinates(
        "https://yandex.com/maps/?ll=7.5%2C46.5") == (46.5, 7.5)
    assert parse_coordinates(
        "https://yandex.com/maps/?ll=7.5%2c46.5") == (46.5, 7.5)
    # Suedhalbkugel (negativer Lat)
    assert parse_coordinates(
        "https://yandex.com/maps/?ll=7.5,-46.5") == (-46.5, 7.5)
    # Westhalbkugel (negativer Lon)
    assert parse_coordinates(
        "https://yandex.com/maps/?ll=-7.5,46.5") == (46.5, -7.5)
    # Beide negativ
    assert parse_coordinates(
        "https://yandex.com/maps/?ll=-7.5,-46.5") == (-46.5, -7.5)
    # Case-Insensitivitaet auf Domain (Browser-Kopier-Puffer schreibt oft Caps)
    assert parse_coordinates("HTTPS://YANDEX.COM/MAPS/?ll=7.5,46.5") == (46.5, 7.5)
    assert parse_coordinates("YANDEX.RU/maps/?LL=7.5,46.5") == (46.5, 7.5)
    # Out-of-Range Lon (>180) -> None (Validierung greift auf Yandex-Reihenfolge)
    assert parse_coordinates("https://yandex.com/maps/?ll=181,46.5") is None
    assert parse_coordinates("https://yandex.com/maps/?ll=-181,46.5") is None
    # Out-of-Range Lat (>90 oder <-90) -> None
    assert parse_coordinates("https://yandex.com/maps/?ll=7.5,91.0") is None
    assert parse_coordinates("https://yandex.com/maps/?ll=7.5,-91.0") is None
    # Grenzfaelle (Aequator/Null-Meridian)
    assert parse_coordinates("https://yandex.com/maps/?ll=0,0") == (0.0, 0.0)
    assert parse_coordinates("https://yandex.com/maps/?ll=180,90") == (90.0, 180.0)
    assert parse_coordinates(
        "https://yandex.com/maps/?ll=-180,-90") == (-90.0, -180.0)
    # Integer-only (keine Dezimalstellen)
    assert parse_coordinates("https://yandex.com/maps/?ll=7,46") == (46.0, 7.0)
    # Regression: Non-Yandex-Domain mit demselben ll=-Parameter
    # (Google/Apple/Bing verwenden weiterhin Lat,Lon-Reihenfolge)
    assert parse_coordinates(
        "https://www.google.com/maps/?ll=46.5,7.5") == (46.5, 7.5)
    assert parse_coordinates(
        "https://maps.google.com/?ll=46.5,7.5") == (46.5, 7.5)
    assert parse_coordinates(
        "https://maps.apple.com/?ll=46.5,7.5") == (46.5, 7.5)
    # Regression: Freitext mit "yandex" ohne Maps-URL matcht nicht mehr
    assert parse_coordinates("Yandex says location is 46.5, 7.5") == (46.5, 7.5)
    # Regression: bestehende Formen bleiben (kein Regress durch neue Domain-Prue)
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("#map=15/46.5/7.5") == (46.5, 7.5)
    assert parse_coordinates("POINT(7.5 46.5)") == (46.5, 7.5)
    assert parse_coordinates("geo:46.5,7.5") == (46.5, 7.5)


def test_parse_coordinates_kml_point():
    """KML-Point-Notation (OGC KML 2.2): ``<Point><coordinates>lon,lat[,alt]``.

    Google Earth, .kml/.kmz-Dateien, QGIS-KML-Export, ogr2ogr -f KML und alle
    KML-basierten Karten-Ketten serialisieren Punkt-Geometrien als ``<Point>``-
    Element mit ``<coordinates>lon,lat[,alt]</coordinates>``. Die KML-Spec gibt
    die Reihenfolge fix (Lon, Lat, [Alt]) - spiegelt die WKT-/GeoJSON-Konvention
    aus OGC Simple Features und RFC 7946. Ohne diesen Zweig fiel jeder KML-
    Point-Text durch :data:`_DECIMAL_PAIR` und lieferte silente Achsen-
    Vertauschung (7.5, 46.5) statt (46.5, 7.5). Match ist definitiv nur bei
    Point-Marker + Coordinates-Marker (analog zur konservativen GeoJSON-
    Marker-Kombination).
    """
    # Basis-Form mit Point-Wrapper
    assert parse_coordinates(
        "<Point><coordinates>7.5,46.5</coordinates></Point>") == (46.5, 7.5)
    # Mit Altitude (drittes Element, wird ignoriert)
    assert parse_coordinates(
        "<Point><coordinates>7.5,46.5,800</coordinates></Point>") == (46.5, 7.5)
    assert parse_coordinates(
        "<Point><coordinates>7.5,46.5,0</coordinates></Point>") == (46.5, 7.5)
    # Whitespace/Newlines innerhalb der Coordinates (Google-Earth-Pretty-Print)
    assert parse_coordinates(
        "<Point>  <coordinates>  7.5,46.5  </coordinates>  </Point>"
    ) == (46.5, 7.5)
    assert parse_coordinates(
        "<Point>\n  <coordinates>\n    7.5,46.5,0\n  </coordinates>\n</Point>"
    ) == (46.5, 7.5)
    # KML-Namespace-Prefix ``<kml:Point>``/``<kml:coordinates>``
    assert parse_coordinates(
        "<kml:Point><kml:coordinates>7.5,46.5</kml:coordinates></kml:Point>"
    ) == (46.5, 7.5)
    # gx:-Namespace (Google-Earth-Extensions)
    assert parse_coordinates(
        "<gx:Point><gx:coordinates>7.5,46.5</gx:coordinates></gx:Point>"
    ) == (46.5, 7.5)
    # Vollstaendige Placemark-Notation (typische Google-Earth-Copy-KML-Ausgabe)
    kml_placemark = (
        "<Placemark>\n"
        "  <name>Fundort</name>\n"
        "  <Point>\n"
        "    <coordinates>7.5,46.5,0</coordinates>\n"
        "  </Point>\n"
        "</Placemark>"
    )
    assert parse_coordinates(kml_placemark) == (46.5, 7.5)
    # Beide negativ (Sued-West)
    assert parse_coordinates(
        "<Point><coordinates>-7.5,-46.5</coordinates></Point>"
    ) == (-46.5, -7.5)
    # Nur ein Vorzeichen (Nord-West-/Sued-Ost-Kombination)
    assert parse_coordinates(
        "<Point><coordinates>-7.5,46.5,800</coordinates></Point>") == (46.5, -7.5)
    assert parse_coordinates(
        "<Point><coordinates>7.5,-46.5</coordinates></Point>") == (-46.5, 7.5)
    # Case-Insensitivitaet (unterschiedliche KML-Ausgabepfade)
    assert parse_coordinates(
        "<POINT><COORDINATES>7.5,46.5</COORDINATES></POINT>") == (46.5, 7.5)
    assert parse_coordinates(
        "<point><coordinates>7.5,46.5</coordinates></point>") == (46.5, 7.5)
    # Point-Tag mit Attributen (id="", gx:altitudeMode="clampToGround" etc.)
    assert parse_coordinates(
        '<Point id="p1"><coordinates>7.5,46.5</coordinates></Point>'
    ) == (46.5, 7.5)
    assert parse_coordinates(
        '<Point><altitudeMode>relativeToGround</altitudeMode>'
        '<coordinates>7.5,46.5,100</coordinates></Point>'
    ) == (46.5, 7.5)
    # Scientific Notation in Koordinaten (KML-Spec erlaubt sie)
    assert parse_coordinates(
        "<Point><coordinates>7.5e0,4.65e1</coordinates></Point>") == (46.5, 7.5)
    # Grenzfaelle Aequator/Null-Meridian
    assert parse_coordinates(
        "<Point><coordinates>0,0</coordinates></Point>") == (0.0, 0.0)
    assert parse_coordinates(
        "<Point><coordinates>180,90</coordinates></Point>") == (90.0, 180.0)
    assert parse_coordinates(
        "<Point><coordinates>-180,-90</coordinates></Point>") == (-90.0, -180.0)
    # Ganzzahlige Koordinaten
    assert parse_coordinates(
        "<Point><coordinates>7,46</coordinates></Point>") == (46.0, 7.0)
    # Out-of-Range Lon (>180) -> None
    assert parse_coordinates(
        "<Point><coordinates>181,7.5</coordinates></Point>") is None
    # Out-of-Range Lat (>90) -> None
    assert parse_coordinates(
        "<Point><coordinates>7.5,91</coordinates></Point>") is None
    # LineString ohne Point-Marker: kein KML-Point-Match, faellt auf
    # bestehendes _DECIMAL_PAIR-Verhalten zurueck (dokumentierte
    # silente Vertauschung fuer semantisch nicht-Point-Daten, analog zur
    # MULTIPOINT-Regression im WKT-Test).
    assert parse_coordinates(
        "<LineString><coordinates>7.5,46.5 7.6,46.6</coordinates></LineString>"
    ) == (7.5, 46.5)
    # LinearRing ohne Point-Marker: gleicher Fallback
    assert parse_coordinates(
        "<LinearRing><coordinates>7.5,46.5 7.6,46.6 7.7,46.7 7.5,46.5"
        "</coordinates></LinearRing>"
    ) == (7.5, 46.5)
    # Bare-<coordinates> ohne Point-Wrapper: kein KML-Point-Match,
    # bewusster Fallback (User haette den Point-Wrapper mitkopieren muessen).
    assert parse_coordinates(
        "<coordinates>7.5,46.5</coordinates>") == (7.5, 46.5)
    # Point-Marker ohne Coordinates-Tag: kein KML-Point-Match
    assert parse_coordinates(
        "<Point><name>ohne Koordinaten</name></Point>") is None
    # Regression: bestehende Formen bleiben unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("POINT(7.5 46.5)") == (46.5, 7.5)
    assert parse_coordinates("#map=15/46.5/7.5") == (46.5, 7.5)
    assert parse_coordinates("geo:46.5,7.5") == (46.5, 7.5)
    # Regression: GeoJSON-Form bleibt unveraendert
    assert parse_coordinates(
        '{"type":"Point","coordinates":[7.5,46.5]}') == (46.5, 7.5)


def test_parse_iso_date_trailing_uhr_marker():
    """DE-Uhrzeit-Trailing-Suffix "Uhr" wird abgestrippt und das Datum korrekt geparst.

    Sammler-Notizen mit erhaltener Uhrzeit ("Fund am 13.06.2024 um 14:30 Uhr",
    "Foto 13. Juni 2024, 14 Uhr", "2024-06-13 14:30:00 Uhr.") wurden bisher
    still auf None geworfen: der Colon-Zweig von :data:`_TRAILING_TIME`
    strippt zwar ``14:30``, laesst aber ``13.06.2024 Uhr`` uebrig - das
    Uhr-Wort matcht die case-sensitive [A-Z]{2,5}-Whitelist nur als "UHR"
    (unueblich). Die Hour-only-Form ("14 Uhr") wird vom Colon-Zweig sowieso
    nicht gefangen. :data:`_TRAILING_UHR_TIME` deckt beide Formen ab.
    """
    # Colon-Zeit + Uhr
    assert parse_iso_date("13.06.2024 14:30 Uhr") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30:00 Uhr") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30 Uhr.") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:30 Uhr") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14:30:00 Uhr") == "2024-06-13"
    # Hour-only + Uhr
    assert parse_iso_date("13.06.2024 14 Uhr") == "2024-06-13"
    assert parse_iso_date("13.06.2024 8 Uhr") == "2024-06-13"
    assert parse_iso_date("2024-06-13 14 Uhr") == "2024-06-13"
    # Komma-Trenner (typische DE-Prosa-Notation "13. Juni 2024, 14 Uhr")
    assert parse_iso_date("13.06.2024, 14:30 Uhr") == "2024-06-13"
    assert parse_iso_date("13.06.2024, 14 Uhr") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024, 14:30 Uhr") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024, 14 Uhr") == "2024-06-13"
    # Monatsname-Form + Zeit ohne Komma
    assert parse_iso_date("13. Juni 2024 14:30 Uhr") == "2024-06-13"
    # Case-Insensitivitaet (Kleinbuchstaben, GROSSBUCHSTABEN, Mixed)
    assert parse_iso_date("13.06.2024 14:30 uhr") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30 UHR") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30 UhR") == "2024-06-13"
    # Uhr mit trailing Punkt (Prosa-Abkuerzungs-Schlussform)
    assert parse_iso_date("13.06.2024 14 Uhr.") == "2024-06-13"
    assert parse_iso_date("13.06.2024, 14:30 uhr.") == "2024-06-13"
    # Kollision mit temporaler Praeposition + Uhr: der Praefix-Strip
    # ("Fund am ...") passiert an anderer Stelle; hier nur die reine
    # Datum+Uhrzeit-Form testen.
    # Kombination mit Klammer-Annotation (Uhr zuerst, dann Klammer)
    assert parse_iso_date("13.06.2024 14:30 Uhr (Foto)") == "2024-06-13"
    # Kombination mit Annaeherungs-Praefix
    assert parse_iso_date("ca. 13.06.2024 14:30 Uhr") == "2024-06-13"

    # Bare-Time ohne Datum -> None (keine False-Positive-Auswertung)
    assert parse_iso_date("14:30 Uhr") is None
    assert parse_iso_date("14 Uhr") is None
    assert parse_iso_date("Uhr") is None
    # Nur die Uhrzeit ohne umgebende Datum-Ziffer -> None
    assert parse_iso_date("um 14 Uhr") is None

    # Regress-Anker: bestehende Trailing-Time-Formen ohne Uhr bleiben unveraendert
    assert parse_iso_date("13.06.2024 14:30") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30 UTC") == "2024-06-13"
    assert parse_iso_date("13.06.2024T14:30") == "2024-06-13"
    assert parse_iso_date("20240613T143200") == "2024-06-13"
    # Regress-Anker: das reine Datum ohne Zeit-Anteil bleibt unveraendert
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("2024-06-13") == "2024-06-13"
    # Regress-Anker: die bestehende false-positive-freie Behandlung von
    # "T-Separator + Uhr" (kein Whitespace zwischen Datum und Zeit-Ziffer)
    # bleibt bestehen - _TRAILING_UHR_TIME verlangt einen [,\s]+-Trenner
    # vor der Stunde-Ziffer, sodass "T10:00:00 Uhr" nicht matcht und die
    # Formal-Kombination "ISO-T + DE-Uhr" (semantisch unueblich, weil
    # ISO-T-Notation die 24h-Zeit ohne Uhr-Suffix erwartet) unangetastet
    # auf None faellt.
    assert parse_iso_date("2024-06-13T10:00:00 Uhr") is None


def test_parse_iso_date_trailing_tageszeit_marker():
    """DE-/EN-Tageszeit-Trailing-Marker OHNE Uhrzeit-Ziffer wird abgestrippt.

    Sammler-Notizen mit grober Tageszeit-Angabe zusaetzlich zum Fund-/Foto-
    Datum ("13.06.2024 morgens", "13. Juni 2024 nachmittags",
    "2024-06-13 abends", "13.06.2024, vormittags.") wurden bisher still
    auf None geworfen: weder :data:`_TRAILING_TIME` (verlangt Ziffer im
    Suffix) noch :data:`_TRAILING_UHR_TIME` (verlangt Ziffer + "Uhr")
    noch :data:`_TRAILING_TZ_STANDALONE` (Whitelist auf IANA-/CLDR-TZ-
    Abkuerzungen begrenzt) fangen die reine Adverb-Form ohne Uhrzeit-
    Ziffer. :data:`_TRAILING_TAGESZEIT` deckt die DE-Adverb-Formen
    (morgens, vormittags, mittags, nachmittags, abends, nachts) plus
    EN-Aequivalente (morning, afternoon, evening, night) ab.
    """
    # DE-Adverb-Formen (Standard-Fall)
    assert parse_iso_date("13.06.2024 morgens") == "2024-06-13"
    assert parse_iso_date("13.06.2024 vormittags") == "2024-06-13"
    assert parse_iso_date("13.06.2024 mittags") == "2024-06-13"
    assert parse_iso_date("13.06.2024 nachmittags") == "2024-06-13"
    assert parse_iso_date("13.06.2024 abends") == "2024-06-13"
    assert parse_iso_date("13.06.2024 nachts") == "2024-06-13"
    # EN-Aequivalente
    assert parse_iso_date("2024-06-13 morning") == "2024-06-13"
    assert parse_iso_date("2024-06-13 afternoon") == "2024-06-13"
    assert parse_iso_date("2024-06-13 evening") == "2024-06-13"
    assert parse_iso_date("2024-06-13 night") == "2024-06-13"
    # Komma-Trenner (typische DE-Prosa-Notation "13. Juni 2024, nachmittags")
    assert parse_iso_date("13.06.2024, nachmittags") == "2024-06-13"
    assert parse_iso_date("13.06.2024, morgens") == "2024-06-13"
    assert parse_iso_date("13. Juni 2024, abends") == "2024-06-13"
    # Monatsname-Form + Tageszeit ohne Komma
    assert parse_iso_date("13. Juni 2024 nachmittags") == "2024-06-13"
    assert parse_iso_date("Juni 2024 morgens") == "2024-06-01"
    # Case-Insensitivitaet (Kleinbuchstaben, GROSSBUCHSTABEN, Mixed)
    assert parse_iso_date("13.06.2024 MORGENS") == "2024-06-13"
    assert parse_iso_date("13.06.2024 Nachmittags") == "2024-06-13"
    assert parse_iso_date("13.06.2024 AbEnDs") == "2024-06-13"
    # Trailing Punkt/Komma (Prosa-Abkuerzungs-Schlussform, Aufzaehlungs-Komma)
    assert parse_iso_date("13.06.2024 morgens.") == "2024-06-13"
    assert parse_iso_date("13.06.2024 nachmittags,") == "2024-06-13"
    assert parse_iso_date("13.06.2024, morgens.") == "2024-06-13"
    # Kombination mit Klammer-Annotation (Klammer zuerst gestrippt, dann Tageszeit)
    assert parse_iso_date("13.06.2024 morgens (Foto)") == "2024-06-13"
    assert parse_iso_date("13.06.2024 nachmittags [Sammlung]") == "2024-06-13"
    # Kombination mit Annaeherungs-Praefix
    assert parse_iso_date("ca. 13.06.2024 morgens") == "2024-06-13"
    assert parse_iso_date("circa 13.06.2024 nachmittags") == "2024-06-13"
    # Kombination mit ISO-Datum + T-Trennung (keine Uhrzeit, nur Tageszeit)
    assert parse_iso_date("2024-06-13 nachmittags") == "2024-06-13"

    # Bare-Tageszeit ohne Datum -> None (keine False-Positive-Auswertung).
    # Der [,\s]+-Trenner-Zwang der Regex verhindert einen Match ohne
    # vorangehendes Datum-Wort.
    assert parse_iso_date("morgens") is None
    assert parse_iso_date("abends") is None
    assert parse_iso_date("nachmittags") is None
    assert parse_iso_date("morning") is None
    assert parse_iso_date("night") is None
    # Nur die Tageszeit ohne umgebende Datum-Ziffer -> None
    assert parse_iso_date("am morgens") is None
    assert parse_iso_date("gegen abends") is None

    # Regress-Anker: der bestehende Boundary-Prefix-Reject-Fall
    # "vormittags 1985" (Tageszeit als *Praefix* vor der Jahreszahl,
    # Test aus test_parse_iso_date_boundary_praefix_wortanfang) bleibt
    # unveraendert None - die Trailing-Regex ankert am Zeilenende, sodass
    # der Praefix-Fall inaktiv bleibt.
    assert parse_iso_date("vormittags 1985") is None
    assert parse_iso_date("morgens 2024") is None

    # Regress-Anker: bestehende Trailing-Time-Formen bleiben unveraendert
    assert parse_iso_date("13.06.2024 14:30") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30 Uhr") == "2024-06-13"
    assert parse_iso_date("13.06.2024 14:30 UTC") == "2024-06-13"
    assert parse_iso_date("13.06.2024T14:30") == "2024-06-13"
    # Regress-Anker: das reine Datum ohne Tageszeit-Anteil bleibt unveraendert
    assert parse_iso_date("13.06.2024") == "2024-06-13"
    assert parse_iso_date("2024-06-13") == "2024-06-13"


def test_parse_iso_date_hearsay_marker():
    """Hearsay-/Zuschreibungs-Marker (DE ``angeblich``, EN ``allegedly`` /
    ``supposedly`` / ``reportedly`` / ``purportedly`` / ``presumably``) als
    Praefix und Suffix vor/nach dem Datum.

    Geerbte Sammlungs-Notizen und Museums-Etiketten mit Datum aus zweiter
    Hand (Verkaeufer-Angabe, Vorbesitzer-Erzaehlung, Katalog-Referenz) sind
    in Provenienz-Ketten sehr verbreitet, wenn der aktuelle Kurator die
    Datums-Zuverlaessigkeit relativieren will ("angeblich 1985 vom Aare-
    Gebiet gefunden", "1985 allegedly Tucson-Fund", "supposedly Juni 2024
    vom Vorbesitzer erworben"). Semantisch identisch zu ``vermutlich`` /
    ``wahrscheinlich`` (Unsicherheits-Marker mit dokumentierter Herkunfts-
    Fragezeichen), aber auf der Hearsay-Achse (Datum stammt aus Erzaehlung,
    nicht Beobachtung). Vor dem Fix fielen alle Formen still auf None:
    :data:`_APPROX_PREFIX` listete keinen Hearsay-Marker, :data:`_TRAILING_APPROX_SUFFIX`
    spiegelbildlich auch nicht.
    """
    # Deutsche Marker als Praefix
    assert parse_iso_date("angeblich 1985") == "1985-01-01"
    assert parse_iso_date("angeblich Juni 2024") == "2024-06-01"
    assert parse_iso_date("angeblich 13.06.2024") == "2024-06-13"
    assert parse_iso_date("angeblich Sommer 1985") == "1985-06-01"
    # Englische Marker als Praefix
    assert parse_iso_date("allegedly 1985") == "1985-01-01"
    assert parse_iso_date("supposedly 1985") == "1985-01-01"
    assert parse_iso_date("reportedly 1985") == "1985-01-01"
    assert parse_iso_date("purportedly 1985") == "1985-01-01"
    assert parse_iso_date("presumably 1985") == "1985-01-01"
    assert parse_iso_date("allegedly Juni 2024") == "2024-06-01"
    assert parse_iso_date("supposedly 13.06.2024") == "2024-06-13"
    assert parse_iso_date("presumably Sommer 1985") == "1985-06-01"
    # Case-Insensitivitaet (Etiketten in GROSS/klein/Mixed)
    assert parse_iso_date("Angeblich 1985") == "1985-01-01"
    assert parse_iso_date("ANGEBLICH 1985") == "1985-01-01"
    assert parse_iso_date("Allegedly 1985") == "1985-01-01"
    assert parse_iso_date("SUPPOSEDLY 1985") == "1985-01-01"
    assert parse_iso_date("Presumably 1985") == "1985-01-01"
    # Verkettet mit anderen Praefixen (Rekursion loest sequentiell auf)
    assert parse_iso_date("angeblich ca. 1985") == "1985-01-01"
    assert parse_iso_date("allegedly circa 1985") == "1985-01-01"
    assert parse_iso_date("supposedly around 1985") == "1985-01-01"
    assert parse_iso_date("angeblich Mitte 19. Jahrhundert") == "1850-01-01"
    # Deutsche Marker als Suffix
    assert parse_iso_date("1985 angeblich") == "1985-01-01"
    assert parse_iso_date("Juni 2024 angeblich") == "2024-06-01"
    assert parse_iso_date("13.06.2024 angeblich") == "2024-06-13"
    # Englische Marker als Suffix
    assert parse_iso_date("1985 allegedly") == "1985-01-01"
    assert parse_iso_date("1985 supposedly") == "1985-01-01"
    assert parse_iso_date("1985 reportedly") == "1985-01-01"
    assert parse_iso_date("1985 purportedly") == "1985-01-01"
    assert parse_iso_date("1985 presumably") == "1985-01-01"
    assert parse_iso_date("Juni 2024 supposedly") == "2024-06-01"
    # Case-Insensitivitaet der Trailing-Form
    assert parse_iso_date("1985 ANGEBLICH") == "1985-01-01"
    assert parse_iso_date("1985 Allegedly") == "1985-01-01"
    assert parse_iso_date("1985 REPORTEDLY") == "1985-01-01"
    # Kombination mit Klammer-Annotation (Klammer zuerst gestrippt)
    assert parse_iso_date("angeblich 1985 (Etikett-Notiz)") == "1985-01-01"
    assert parse_iso_date("allegedly 1985 [Provenienz]") == "1985-01-01"
    # Ohne Datum-Rest oder mit ungueltigem Rest -> None
    assert parse_iso_date("angeblich") is None
    assert parse_iso_date("allegedly") is None
    assert parse_iso_date("supposedly abc") is None
    assert parse_iso_date("reportedly 1700") is None  # ausserhalb 1800-2999
    # Regress-Anker: bestehende Wahrscheinlichkeits-Marker bleiben unveraendert
    assert parse_iso_date("wahrscheinlich 1985") == "1985-01-01"
    assert parse_iso_date("vermutlich 1985") == "1985-01-01"
    assert parse_iso_date("perhaps 1985") == "1985-01-01"
    assert parse_iso_date("possibly 1985") == "1985-01-01"
    assert parse_iso_date("maybe 1985") == "1985-01-01"
    assert parse_iso_date("1985 wahrscheinlich") == "1985-01-01"
    assert parse_iso_date("1985 vermutlich") == "1985-01-01"


def test_parse_coordinates_wikipedia_geohack_url():
    """Wikipedia-GeoHack-URL-Query-Parameter ``params=<lat>_<dir>_<lon>_<dir>``
    (Decimal-mit-Direction, DM, DMS) wird als Koordinaten-Quelle erkannt.

    Wikipedia rendert jede Koordinaten-Box (Template ``{{Coord}}`` oder
    ``{{Location}}``) als Hyperlink auf
    ``https://geohack.toolforge.org/geohack.php?pagename=<Artikel>&params=<coord>[&type=...&region=...&scale=...]``.
    Der ``params=``-Wert kodiert die Koordinaten Underscore-getrennt in
    einer der drei Formen:

    - Decimal + Direction: ``46.5_N_7.5_E``
    - DM (Grad + Minuten): ``46_30_N_7_30_E``
    - DMS (Grad + Minuten + Sekunden): ``46_30_15_N_7_30_15_E``

    Bisher fiel jede GeoHack-URL still auf None, weil Underscore (``_``)
    weder in :data:`_DECIMAL_PAIR`s Separator-Klasse ``[ \t,;/&~]`` steht
    noch die DMS-Patterns (:data:`_DMS`, :data:`_DMS_COLON`,
    :data:`_DMS_LETTERS`, :data:`_DMS_PREFIX`) den Underscore als Zahl-
    Trenner kennen - aus einem typischen Sammler-Workflow "Fundort in
    Wikipedia nachschlagen -> Coord-Link kopieren -> ins Fundort-Feld
    einfuegen" entstand damit silenter Koordinaten-Datenverlust bei der
    Migration. Neuer :data:`_GEOHACK_PARAMS`-Zweig extrahiert vor allen
    Zahl-Paar-Patterns die Underscore-Kette, konvertiert DM/DMS via
    ``deg + min/60 + sec/3600`` und wendet das Direction-Vorzeichen an
    (N/E/O positiv, S/W negativ).
    """
    # Volle URL, Decimal-Form
    assert parse_coordinates(
        "https://geohack.toolforge.org/geohack.php?params=46.5_N_7.5_E"
    ) == (46.5, 7.5)
    # Volle URL mit Pagename-Prefix (der bei GeoHack ueblich ist)
    assert parse_coordinates(
        "https://geohack.toolforge.org/geohack.php"
        "?pagename=Mont_Blanc&params=45.833333_N_6.866667_E"
    ) == (45.833333, 6.866667)
    # DM-Form (Grad + Minuten)
    assert parse_coordinates(
        "https://geohack.toolforge.org/geohack.php?params=46_30_N_7_30_E"
    ) == (46.5, 7.5)
    # DMS-Form (Grad + Minuten + Sekunden)
    lat, lon = parse_coordinates(
        "https://geohack.toolforge.org/geohack.php?params=46_30_15_N_7_30_15_E")
    assert abs(lat - (46 + 30/60 + 15/3600)) < 1e-9
    assert abs(lon - (7 + 30/60 + 15/3600)) < 1e-9
    # Suedhalbkugel-/Westhalbkugel-Direction (Vorzeichen negativ)
    assert parse_coordinates(
        "https://geohack.toolforge.org/geohack.php?params=46.5_S_7.5_W"
    ) == (-46.5, -7.5)
    # DE-Alternante O fuer Ost (Sammler-typisch in DE-lokalisierten URLs)
    assert parse_coordinates("params=46.5_N_7.5_O") == (46.5, 7.5)
    # URL mit trailing type/region/scale-Parametern (Standard-Rendering)
    assert parse_coordinates(
        "https://geohack.toolforge.org/geohack.php"
        "?params=46.5_N_7.5_E&type=mountain&region=CH&scale=50000"
    ) == (46.5, 7.5)
    # DMS-Form + trailing type-Parameter (kombiniert)
    lat, lon = parse_coordinates(
        "https://geohack.toolforge.org/geohack.php"
        "?params=46_30_15_N_7_30_15_E&type=mountain")
    assert abs(lat - (46 + 30/60 + 15/3600)) < 1e-9
    assert abs(lon - (7 + 30/60 + 15/3600)) < 1e-9
    # Reines params=-Fragment (der Sammler kopiert nur den Query-Teil)
    assert parse_coordinates("params=46.5_N_7.5_E") == (46.5, 7.5)
    # Case-Insensitivitaet auf params= und Direction (Caps-Lock aus
    # geerbten URLs)
    assert parse_coordinates("PARAMS=46.5_N_7.5_E") == (46.5, 7.5)
    assert parse_coordinates("params=46.5_n_7.5_e") == (46.5, 7.5)
    # Nord/Sued-Aequator- und Ost/West-Nullmeridian-Grenzfaelle
    assert parse_coordinates("params=0_N_0_E") == (0.0, 0.0)
    assert parse_coordinates("params=90_N_180_E") == (90.0, 180.0)
    assert parse_coordinates("params=90_S_180_W") == (-90.0, -180.0)
    # Out-of-Range: Validierung greift wie sonst
    assert parse_coordinates("params=91.0_N_7.5_E") is None
    assert parse_coordinates("params=46.5_N_200.0_E") is None
    # Ungueltige Form ohne Direction (kein GeoHack-Match, Underscore
    # ist in keinem anderen Pattern als Separator anerkannt -> None)
    assert parse_coordinates("params=46.5_7.5") is None
    # Ungueltige Form mit nur einer Direction (kein Match)
    assert parse_coordinates("params=46.5_N_7.5") is None
    # Regress-Anker: alle bestehenden Formen bleiben unveraendert
    assert parse_coordinates("46.5, 7.5") == (46.5, 7.5)
    assert parse_coordinates("46.5° N, 7.5° E") == (46.5, 7.5)
    assert parse_coordinates("N46.5 E7.5") == (46.5, 7.5)
    assert parse_coordinates("#map=15/46.5/7.5") == (46.5, 7.5)
    assert parse_coordinates("POINT(7.5 46.5)") == (46.5, 7.5)

