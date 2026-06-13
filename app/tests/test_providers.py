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
