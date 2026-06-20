from stonebook.ai.providers import coerce_result, extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fence():
    text = 'Hier das Ergebnis:\n```json\n{"Mineral_Primaer": {"wert": "Quarz"}}\n```\nFertig.'
    assert extract_json(text) == {"Mineral_Primaer": {"wert": "Quarz"}}


def test_extract_json_with_prefix_text():
    text = 'Antwort: {"x": {"y": "{nicht ende}"}} und noch text'
    assert extract_json(text) == {"x": {"y": "{nicht ende}"}}


def test_extract_json_nested_braces_in_strings():
    text = '{"zusammenfassung": "a {b} c", "gesamt_confidence": 50}'
    assert extract_json(text)["zusammenfassung"] == "a {b} c"


def test_coerce_result_numeric_coercion():
    raw = {
        "Mohs_Haerte_min": {"wert": "6,5", "confidence_prozent": 90},
        "Gewicht_g": {"wert": "41.0 g", "confidence_prozent": "80"},
        "Confidence_Prozent": {"wert": "75", "confidence_prozent": 60},
        "gesamt_confidence": 85,
        "zusammenfassung": "Test",
    }
    out = coerce_result(raw)
    assert out["Mohs_Haerte_min"]["wert"] == 6.5
    assert out["Gewicht_g"]["wert"] == 41.0
    assert out["Confidence_Prozent"]["wert"] == 75
    assert out["Gewicht_g"]["confidence_prozent"] == 80
    assert out["gesamt_confidence"] == 85
    assert out["zusammenfassung"] == "Test"


def test_coerce_result_clamps_and_filters():
    raw = {
        "Mineral_Primaer": {"wert": "Quarz", "confidence_prozent": 150},
        "Foto_Uebersicht": {"wert": "x", "confidence_prozent": 50},  # nicht erlaubt
        "Unbekannt": {"wert": "y"},                                   # nicht erlaubt
        "Farbe_beobachtet": {"wert": "  ", "confidence_prozent": 30},  # leer → null
    }
    out = coerce_result(raw)
    assert out["Mineral_Primaer"]["confidence_prozent"] == 100
    assert "Foto_Uebersicht" not in out
    assert "Unbekannt" not in out
    assert out["Farbe_beobachtet"]["wert"] is None


def test_coerce_result_bare_value():
    out = coerce_result({"Mineral_Primaer": "Quarz", "gesamt_confidence": 0})
    assert out["Mineral_Primaer"]["wert"] == "Quarz"
    assert out["Mineral_Primaer"]["confidence_prozent"] == 0


def test_coerce_result_zahl_mit_einheit_ohne_leerzeichen():
    """Modelle schreiben oft 'Wert+Einheit' ohne Trennzeichen ('41.0g', '2,65g/cm³')."""
    raw = {
        "Gewicht_g": {"wert": "41.0g", "confidence_prozent": 80},
        "Dichte_min_gcm3": {"wert": "2,65g/cm³", "confidence_prozent": 70},
        "Mohs_Haerte_min": {"wert": "ca. 6.5", "confidence_prozent": 70},
        "Seltenheit_global_1_10": {"wert": "etwa 7 von 10", "confidence_prozent": 60},
        # Vorzeichen am Anfang darf nicht verloren gehen
        "Wert_CHF_roh": {"wert": "+1500", "confidence_prozent": 50},
    }
    out = coerce_result(raw)
    assert out["Gewicht_g"]["wert"] == 41.0
    assert out["Dichte_min_gcm3"]["wert"] == 2.65
    assert out["Mohs_Haerte_min"]["wert"] == 6.5
    assert out["Seltenheit_global_1_10"]["wert"] == 7
    assert out["Wert_CHF_roh"]["wert"] == 1500.0


def test_coerce_result_kein_numerischer_anteil_bleibt_none():
    raw = {
        "Gewicht_g": {"wert": "unbekannt", "confidence_prozent": 0},
        "Mohs_Haerte_min": {"wert": "n/a", "confidence_prozent": 0},
    }
    out = coerce_result(raw)
    assert out["Gewicht_g"]["wert"] is None
    assert out["Mohs_Haerte_min"]["wert"] is None


def test_coerce_result_locale_tausender_in_preisen():
    """KI-Modelle geben Preise lokal formatiert zurueck (DE/EN/CH/FR-Tausender).

    Vor dem Fix lieferte ``coerce_result('1.500,00 CHF')`` 1.5 statt 1500.0,
    weil ``_LEADING_NUMBER`` die DE-Notation an der Hunderter-Punkt-Stelle
    abschnitt. ``normalize_numeric_locale`` strippt vorher die Tausender,
    sodass die Zahl als Ganzes erkannt wird.
    """
    raw = {
        # DE-Format ("Tausenderpunkt + Dezimalkomma") - haeufig in DE-System-Prompts
        "Wert_CHF_roh": {"wert": "1.500,00 CHF", "confidence_prozent": 70},
        # EN-Format ("Tausenderkomma + Dezimalpunkt") - haeufig in EN-Antworten
        "Wert_CHF_poliert": {"wert": "1,500.00 CHF", "confidence_prozent": 70},
        # CH-Format mit Apostroph als Tausender (Buchhaltungs-Convention)
        "Marktwert_Industrie": {"wert": "1'500.00 CHF", "confidence_prozent": 70},
        # FR-/SI-Format mit Whitespace als Tausender
        "Wert_CHF_Schmuck": {"wert": "1 500.00 CHF", "confidence_prozent": 70},
        # Millionen-Wert mit reinen Tausendergruppen (kein Dezimal)
        "Wissenschaftlicher_Wert_CHF": {"wert": "1,500,000 CHF",
                                        "confidence_prozent": 70},
        # NBSP-Tausender (franzoesische Excel-/LibreOffice-Konvention)
        "Wert_USD_Talisman": {"wert": "1\xa0500.00 USD", "confidence_prozent": 70},
    }
    out = coerce_result(raw)
    assert out["Wert_CHF_roh"]["wert"] == 1500.0
    assert out["Wert_CHF_poliert"]["wert"] == 1500.0
    assert out["Marktwert_Industrie"]["wert"] == 1500.0
    assert out["Wert_CHF_Schmuck"]["wert"] == 1500.0
    assert out["Wissenschaftlicher_Wert_CHF"]["wert"] == 1500000.0
    assert out["Wert_USD_Talisman"]["wert"] == 1500.0


def test_coerce_result_ambivalente_einzeltrenner_bleiben_dezimal():
    """``'2,65'`` / ``'1.5'`` (Einzeltrenner) bleiben Dezimal, kein Tausender-Trip.

    Spiegelt die parse_range-Konvention: nur eindeutig erkennbare Tausender
    werden gestrippt. Ohne diese Garantie waere die bestehende Test-Erwartung
    fuer ``'2,65g/cm³'`` -> 2.65 nicht mehr stabil.
    """
    raw = {
        "Dichte_min_gcm3": {"wert": "2,65 g/cm³", "confidence_prozent": 70},
        "Mohs_Haerte_min": {"wert": "6.5", "confidence_prozent": 70},
        # Einzelner Komma-Trenner ohne Dezimal: ambivalent, bleibt 1.0
        "Gewicht_g": {"wert": "1,5g", "confidence_prozent": 70},
    }
    out = coerce_result(raw)
    assert out["Dichte_min_gcm3"]["wert"] == 2.65
    assert out["Mohs_Haerte_min"]["wert"] == 6.5
    assert out["Gewicht_g"]["wert"] == 1.5
