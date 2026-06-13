from stonebook.ai.analysis_schema import AI_FIELDS, build_tool, field_definitions_text
from stonebook.ai.image_prep import default_selection


def test_tool_schema_struktur():
    tool = build_tool()
    assert tool["name"] == "analyse_ergebnis"
    props = tool["input_schema"]["properties"]
    assert "gesamt_confidence" in props
    assert "zusammenfassung" in props
    assert "Mineral_Primaer" in props
    # Pfad-/Funddatum-Felder ausgeschlossen
    assert "Foto_Uebersicht" not in props
    assert "Funddatum" not in props
    feld = props["Mineral_Primaer"]
    assert "wert" in feld["properties"]
    assert "confidence_prozent" in feld["properties"]


def test_field_definitions_text():
    text = field_definitions_text()
    assert "Mineral_Primaer" in text
    assert "Mohs_Haerte_min" in text
    assert len(AI_FIELDS) > 30


def test_default_selection_je_kategorie():
    rows = [
        {"kategorie": "Uebersicht", "rel_path": "a"},
        {"kategorie": "Kamera", "rel_path": "b"},
        {"kategorie": "Kamera", "rel_path": "c"},
        {"kategorie": "Mikroskop", "rel_path": "d"},
        {"kategorie": "UV365", "rel_path": "e"},
    ]
    sel = default_selection(rows, 6)
    paths = [r["rel_path"] for r in sel]
    # je Kategorie eins zuerst (a,b,d,e), dann auffüllen mit c
    assert paths[:4] == ["a", "b", "d", "e"]
    assert "c" in paths
    assert len(sel) == 5

    sel2 = default_selection(rows, 3)
    assert len(sel2) == 3
