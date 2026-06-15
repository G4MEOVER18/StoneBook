from pathlib import Path

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
    """Unsicherheitsnotation '5.5(3)' oder umgedrehte Eingabe '7-5' sind keine Ranges."""
    # "5.5(3)" - Unsicherheit, nicht 5.5..3
    assert csv_loaders.parse_range("5.5(3)") == (5.5, 5.5)
    # Tippfehler "7-5" → soll nicht (7, 5) liefern
    assert csv_loaders.parse_range("7-5") == (7.0, 7.0)
    # Echter Range bleibt korrekt
    assert csv_loaders.parse_range("5-7") == (5.0, 7.0)


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
