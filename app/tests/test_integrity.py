"""Konsistenzprüfungen über die DB."""
import datetime
from pathlib import Path

import pytest

from stonebook.db.database import connect, open_db
from stonebook.db.integrity import check_integrity
from stonebook.migration.migrate import migrate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_conn(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "stonebook.sqlite3"
    migrate(REPO, db_file, log=lambda *_: None)
    c = connect(db_file)
    yield c
    c.close()


def test_migrierte_db_ist_konsistent(migrated_conn):
    rep = check_integrity(migrated_conn)
    assert rep.is_clean
    assert rep.alias_to_missing == []
    assert rep.alias_id_collisions == []
    assert rep.invalid_funddatum == []


def test_check_files_findet_fehlendes_bild(migrated_conn, tmp_path):
    # Fake-Repo ohne Bilddateien → alle Bildreferenzen muessten als fehlend gelten
    rep = check_integrity(migrated_conn, root=tmp_path, check_files=True)
    assert len(rep.missing_image_files) == 63
    assert not rep.is_clean


def test_invalid_funddatum_wird_erkannt(tmp_path):
    db = tmp_path / "x.sqlite3"
    c = open_db(db)
    c.execute(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        ("OBJ_0001", "32.13.2024"),
    )
    c.execute(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        ("OBJ_0002", "2024-06-13"),
    )
    c.commit()
    rep = check_integrity(c)
    # (obj_id, roh-Wert)-Tupel: der konkrete Falschwert ist direkt im Report
    # sichtbar (spiegelt unknown_status / unknown_kategorie / future_funddatum).
    assert rep.invalid_funddatum == [("OBJ_0001", "32.13.2024")]
    c.close()


def test_alias_collision_wird_erkannt(tmp_path):
    db = tmp_path / "x.sqlite3"
    c = open_db(db)
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    c.execute(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES (?, ?)",
        ("OBJ_0002", "OBJ_0001"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.alias_id_collisions == ["OBJ_0002"]
    c.close()


def test_numeric_out_of_range_wird_erkannt(tmp_path):
    c = open_db(tmp_path / "x.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Confidence_Prozent, Gewicht_g, "
        "Seltenheit_global_1_10, Mohs_Haerte_min) VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", 150, 10.0, 5, 7.0),    # Confidence > 100
            ("OBJ_0002", 80, -2.5, 5, 7.0),     # negatives Gewicht
            ("OBJ_0003", 80, 10.0, 11, 7.0),    # Seltenheit > 10
            ("OBJ_0004", 80, 10.0, 5, 7.0),     # alles ok
        ],
    )
    c.commit()
    rep = check_integrity(c)
    fields = {(oid, f) for oid, f, _ in rep.numeric_out_of_range}
    assert ("OBJ_0001", "Confidence_Prozent") in fields
    assert ("OBJ_0002", "Gewicht_g") in fields
    assert ("OBJ_0003", "Seltenheit_global_1_10") in fields
    assert not any(oid == "OBJ_0004" for oid, _, _ in rep.numeric_out_of_range)
    assert not rep.is_clean
    c.close()


def test_range_inverted_wird_erkannt(tmp_path):
    c = open_db(tmp_path / "x.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Mohs_Haerte_min, Mohs_Haerte_max, "
        "Dichte_min_gcm3, Dichte_max_gcm3) VALUES (?, ?, ?, ?, ?)",
        [
            ("OBJ_0001", 7.0, 5.0, 2.6, 2.7),   # Mohs invertiert
            ("OBJ_0002", 5.0, 7.0, 3.0, 2.5),   # Dichte invertiert
            ("OBJ_0003", 5.0, 7.0, 2.6, 2.7),   # ok
            ("OBJ_0004", None, 7.0, 2.6, None), # halb leer → ueberspringen
        ],
    )
    c.commit()
    rep = check_integrity(c)
    # Vier-Tupel ``(obj_id, feldpaar, min_wert, max_wert)``: die konkreten
    # Werte stehen direkt im Report, sodass die Vertauschung ohne SQL-Roundtrip
    # zur Originaltabelle diagnostizierbar ist.
    inverted = {(oid, pair, lo, hi) for oid, pair, lo, hi in rep.range_inverted}
    assert ("OBJ_0001", "Mohs_Haerte_min>Mohs_Haerte_max", 7.0, 5.0) in inverted
    assert ("OBJ_0002", "Dichte_min_gcm3>Dichte_max_gcm3", 3.0, 2.5) in inverted
    assert not any(row[0] == "OBJ_0003" for row in rep.range_inverted)
    assert not any(row[0] == "OBJ_0004" for row in rep.range_inverted)
    c.close()


def test_dimension_order_inverted_wird_erkannt(tmp_path):
    """Konvention Laenge_mm >= Breite_mm >= Hoehe_mm laut Feldwoerterbuch.

    Verstoesse entstehen durch verwechselte Achsen beim Vermessen oder durch
    verdrehte Eingabe ins Datenblatt; symmetrisch zu ``range_inverted``
    (Mohs/Dichte min<=max), aber semantisch eine Achsen-Verwechslung statt
    einer logischen Unmoeglichkeit.
    """
    c = open_db(tmp_path / "x.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Laenge_mm, Breite_mm, Hoehe_mm) "
        "VALUES (?, ?, ?, ?)",
        [
            ("OBJ_0001", 10.0, 20.0, 5.0),   # Laenge < Breite verwechselt
            ("OBJ_0002", 30.0, 20.0, 25.0),  # Breite < Hoehe verwechselt
            ("OBJ_0003", 5.0, 10.0, 20.0),   # beide invertiert
            ("OBJ_0004", 30.0, 20.0, 10.0),  # konventionsgerecht
            ("OBJ_0005", 30.0, 30.0, 30.0),  # Wuerfel: Gleichheit zulaessig
            ("OBJ_0006", 20.0, None, 10.0),  # Breite NULL → ueberspringen
            ("OBJ_0007", None, 20.0, 10.0),  # Laenge NULL → ueberspringen
            ("OBJ_0008", 30.0, 20.0, None),  # Hoehe NULL → nur erstes Paar
        ],
    )
    c.commit()
    rep = check_integrity(c)
    inverted = {(oid, pair, big, small)
                for oid, pair, big, small in rep.dimension_order_inverted}
    assert ("OBJ_0001", "Laenge_mm<Breite_mm", 10.0, 20.0) in inverted
    assert ("OBJ_0002", "Breite_mm<Hoehe_mm", 20.0, 25.0) in inverted
    # Beide Paare invertiert: Laenge=5 < Breite=10 UND Breite=10 < Hoehe=20.
    assert ("OBJ_0003", "Laenge_mm<Breite_mm", 5.0, 10.0) in inverted
    assert ("OBJ_0003", "Breite_mm<Hoehe_mm", 10.0, 20.0) in inverted
    # Konventionsgerecht und Wuerfel: keine Meldung.
    assert not any(row[0] == "OBJ_0004" for row in rep.dimension_order_inverted)
    assert not any(row[0] == "OBJ_0005" for row in rep.dimension_order_inverted)
    # Halb leere Eintraege werden uebergangen (keine falsch-positiven), das
    # gesetzte Paar in OBJ_0008 bleibt konsistent und wird nicht gemeldet.
    assert not any(row[0] == "OBJ_0006" for row in rep.dimension_order_inverted)
    assert not any(row[0] == "OBJ_0007" for row in rep.dimension_order_inverted)
    assert not any(row[0] == "OBJ_0008" for row in rep.dimension_order_inverted)
    assert not rep.is_clean
    c.close()


def test_dimension_order_inverted_migrierte_db_clean(migrated_conn):
    """Die migrierte DB hat (noch) keine Dimensionsdaten; clean Baseline."""
    rep = check_integrity(migrated_conn)
    assert rep.dimension_order_inverted == []


def test_alias_self_referencing_wird_erkannt(tmp_path):
    """Ein Alias auf sich selbst ist eine Inkonsistenz (Migration produziert das nie)."""
    c = open_db(tmp_path / "self.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    # Self-Alias: OBJ_0002 → OBJ_0002 (manuell, simuliert Edit-Fehler)
    c.execute(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES (?, ?)",
        ("OBJ_0002", "OBJ_0002"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.alias_self_referencing == ["OBJ_0002"]
    # Self-Alias kollidiert auch zwangslaeufig mit dem Objekt
    assert "OBJ_0002" in rep.alias_id_collisions
    assert not rep.is_clean
    c.close()


def test_alias_canonical_is_alias_wird_erkannt(tmp_path):
    """Kette A->B->C: A.canonical_id (B) ist selbst ein Alias - logisch defekt."""
    c = open_db(tmp_path / "kette.sqlite3")
    # Drei reale Objekte, damit die FK aliases.canonical_id -> objects.obj_id haelt.
    # Szenario: OBJ_0002 wurde frueher als Kanon gefuehrt (OBJ_0003 zeigt darauf),
    # spaeter wurde OBJ_0002 selbst in OBJ_0001 gemergt - jetzt ist die Referenz
    # von OBJ_0003 logisch defekt: sie sollte direkt auf OBJ_0001 zeigen.
    c.executemany(
        "INSERT INTO objects (obj_id) VALUES (?)",
        [("OBJ_0001",), ("OBJ_0002",), ("OBJ_0003",)],
    )
    c.executemany(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES (?, ?)",
        [
            ("OBJ_0002", "OBJ_0001"),  # OBJ_0002 nun Alias
            ("OBJ_0003", "OBJ_0002"),  # zeigt auf OBJ_0002 - Kette
        ],
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.alias_canonical_is_alias == [("OBJ_0003", "OBJ_0002")]
    assert not rep.is_clean
    import json
    json.dumps(rep.as_dict())
    c.close()


def test_alias_canonical_is_alias_selbstreferenz_nicht_doppelt(tmp_path):
    """Selbstreferenzen (alias_id==canonical_id) gehoeren nicht in die Ketten-Liste."""
    c = open_db(tmp_path / "self.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute(
        "INSERT INTO aliases (alias_id, canonical_id) VALUES (?, ?)",
        ("OBJ_0001", "OBJ_0001"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.alias_self_referencing == ["OBJ_0001"]
    # Selbstreferenz darf nicht zusaetzlich als Kette gemeldet werden
    assert rep.alias_canonical_is_alias == []
    c.close()


def test_alias_canonical_is_alias_migrierte_db_clean(migrated_conn):
    rep = check_integrity(migrated_conn)
    assert rep.alias_canonical_is_alias == []


def test_unknown_image_kategorie_wird_erkannt(tmp_path):
    c = open_db(tmp_path / "cat.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg"),
            ("OBJ_0001", "TypoKat", "b.jpg"),  # unbekannt
            ("OBJ_0001", "Mikroskop", "c.jpg"),
            ("OBJ_0001", "", "d.jpg"),  # leer
        ],
    )
    c.commit()
    rep = check_integrity(c)
    kats = {kat for _, kat in rep.unknown_image_kategorie}
    assert "TypoKat" in kats
    assert "" in kats
    assert "Kamera" not in kats
    assert "Mikroskop" not in kats
    assert not rep.is_clean
    c.close()


def test_migrierte_db_alle_image_kategorien_bekannt(migrated_conn):
    rep = check_integrity(migrated_conn)
    assert rep.unknown_image_kategorie == []
    assert rep.alias_self_referencing == []


def test_migrierte_db_keine_numerischen_ausreisser(migrated_conn):
    rep = check_integrity(migrated_conn)
    assert rep.numeric_out_of_range == []
    assert rep.range_inverted == []


def test_as_dict_ist_serialisierbar(migrated_conn):
    import json

    rep = check_integrity(migrated_conn)
    json.dumps(rep.as_dict())


def test_future_funddatum_wird_erkannt(tmp_path):
    """Funddaten, die nach 'today' liegen, sind verdaechtig (Tippfehler/Vorgriff)."""
    c = open_db(tmp_path / "fut.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Funddatum) VALUES (?, ?)",
        [
            ("OBJ_0001", "2020-06-13"),   # Vergangenheit → ok
            ("OBJ_0002", "2024-06-13"),   # heute → ok
            ("OBJ_0003", "2024-06-14"),   # Zukunft → flag
            ("OBJ_0004", "2099-12-31"),   # weit in der Zukunft → flag
            ("OBJ_0005", ""),             # leer → uebergangen
        ],
    )
    c.commit()
    rep = check_integrity(c, today=datetime.date(2024, 6, 13))
    flagged = {oid for oid, _ in rep.future_funddatum}
    assert flagged == {"OBJ_0003", "OBJ_0004"}
    assert ("OBJ_0004", "2099-12-31") in rep.future_funddatum
    # Zukunftsdaten zaehlen nicht als 'invalid' (parseable ISO)
    assert rep.invalid_funddatum == []
    assert not rep.is_clean
    c.close()


def test_future_funddatum_default_today_keine_falsch_positiven(migrated_conn):
    """Die echte DB enthaelt keine Zukunftsdaten (Default-today reicht aus)."""
    rep = check_integrity(migrated_conn)
    assert rep.future_funddatum == []


def test_aktiv_ohne_inhalt_wird_erkannt(tmp_path):
    """status='aktiv' ohne Daten und ohne Bilder ist eine Inkonsistenz."""
    c = open_db(tmp_path / "leer_aktiv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, status, Name) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "aktiv", "Vollstaendig"),         # ok: hat Name
            ("OBJ_0002", "aktiv", None),                    # leer + aktiv → flag
            ("OBJ_0003", "platzhalter", None),              # leer + platzhalter → ok
            ("OBJ_0004", "archiviert", None),               # leer + archiviert → ok
            ("OBJ_0005", "aktiv", "   "),                   # nur Whitespace → flag
        ],
    )
    # OBJ_0006 ist aktiv, hat keine Daten, aber ein Bild → ok
    c.execute("INSERT INTO objects (obj_id, status) VALUES ('OBJ_0006', 'aktiv')")
    c.execute(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        ("OBJ_0006", "Kamera", "a.jpg"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.aktiv_ohne_inhalt == ["OBJ_0002", "OBJ_0005"]
    assert not rep.is_clean
    # as_dict serialisierbar
    import json
    json.dumps(rep.as_dict())
    c.close()


def test_aktiv_ohne_inhalt_migrierte_db_clean(migrated_conn):
    """Die migrierte DB darf keine inkonsistenten 'aktiv'-Objekte enthalten."""
    rep = check_integrity(migrated_conn)
    assert rep.aktiv_ohne_inhalt == []


def test_platzhalter_mit_inhalt_wird_erkannt(tmp_path):
    """status='platzhalter' bei vorhandenen Daten/Bildern ist eine Inkonsistenz."""
    c = open_db(tmp_path / "ph.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, status, Name) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "platzhalter", None),         # ok: leer + platzhalter
            ("OBJ_0002", "platzhalter", "Mit Name"),   # flag: hat Name
            ("OBJ_0003", "aktiv", "Aktiv mit Name"),   # ok: aktiv + Inhalt
            ("OBJ_0004", "archiviert", "Archiv"),      # archiviert ist neutral
        ],
    )
    # OBJ_0005: platzhalter, ohne Felddaten, aber MIT Bild → flag
    c.execute("INSERT INTO objects (obj_id, status) VALUES ('OBJ_0005', 'platzhalter')")
    c.execute(
        "INSERT INTO images (obj_id, kategorie, rel_path) VALUES (?,?,?)",
        ("OBJ_0005", "Kamera", "a.jpg"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.platzhalter_mit_inhalt == ["OBJ_0002", "OBJ_0005"]
    assert not rep.is_clean
    import json
    json.dumps(rep.as_dict())
    c.close()


def test_platzhalter_mit_inhalt_migrierte_db_clean(migrated_conn):
    """Migrierte DB ist konsistent: kein 'platzhalter' hat tatsaechlichen Inhalt."""
    rep = check_integrity(migrated_conn)
    assert rep.platzhalter_mit_inhalt == []


def test_platzhalter_mit_inhalt_repariert_durch_refresh_status(tmp_path):
    """refresh_status_all entfernt die Inkonsistenz (Statusrueckfuehrung)."""
    from stonebook.db.repository import ObjectRepo
    c = open_db(tmp_path / "ph_fix.sqlite3")
    c.execute(
        "INSERT INTO objects (obj_id, status, Mineral_Primaer) VALUES (?, ?, ?)",
        ("OBJ_0001", "platzhalter", "Quarz"),
    )
    c.commit()
    rep = check_integrity(c)
    assert rep.platzhalter_mit_inhalt == ["OBJ_0001"]
    ObjectRepo(c).refresh_status_all()
    rep2 = check_integrity(c)
    assert rep2.platzhalter_mit_inhalt == []
    c.close()


def test_unknown_status_wird_erkannt(tmp_path):
    """Status ausserhalb {aktiv,platzhalter,archiviert} wird gemeldet (obj_id, status)."""
    c = open_db(tmp_path / "us.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, status) VALUES (?, ?)",
        [
            ("OBJ_0001", "aktiv"),          # ok
            ("OBJ_0002", "Aktiv"),          # Tippfehler Case
            ("OBJ_0003", "platzhalter"),    # ok
            ("OBJ_0004", "Archiv"),         # nicht ganz: kein 'archiviert'
            ("OBJ_0005", "fertig"),         # frei erfundener Status
        ],
    )
    c.commit()
    rep = check_integrity(c)
    # Sortiert nach obj_id (Reihenfolge der SELECT-Klausel)
    assert rep.unknown_status == [
        ("OBJ_0002", "Aktiv"),
        ("OBJ_0004", "Archiv"),
        ("OBJ_0005", "fertig"),
    ]
    assert not rep.is_clean
    c.close()


def test_unknown_status_migrierte_db_clean(migrated_conn):
    """Migrierte DB nutzt ausschliesslich die drei gueltigen Status-Werte."""
    rep = check_integrity(migrated_conn)
    assert rep.unknown_status == []


def test_unknown_status_in_as_dict_serialisierbar(tmp_path):
    """as_dict liefert Tuples als Listen, damit das JSON-Format roundtrip-fest ist."""
    import json
    c = open_db(tmp_path / "as.sqlite3")
    c.execute("INSERT INTO objects (obj_id, status) VALUES (?, ?)",
              ("OBJ_0001", "fertig"))
    c.commit()
    d = check_integrity(c).as_dict()
    assert d["unknown_status"] == [["OBJ_0001", "fertig"]]
    json.dumps(d, ensure_ascii=False)  # darf nicht crashen
    c.close()


def test_unknown_kategorie_wird_erkannt(tmp_path):
    """Kategorie ausserhalb des Feldwoerterbuch-Enums wird gemeldet (obj_id, kategorie).

    Schema hat keine CHECK-Klausel auf Kategorie - Tippfehler ("Handstuck" ohne
    Umlaut), Falschwerte ("Probe", "Fossil") oder Case-Varianten ("kristall")
    koennen durch direkten DB-Zugriff oder fehlerhaften CSV-/JSON-Import
    entstehen, ohne dass die Anwendung sie bemerkt. Leerstring/NULL bleiben
    legitim als "noch nicht kategorisiert".
    """
    c = open_db(tmp_path / "uk.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
        [
            ("OBJ_0001", "Handstück"),     # ok (Umlaut-Form aus Feldwoerterbuch)
            ("OBJ_0002", "Handstuck"),     # Tippfehler ohne Umlaut
            ("OBJ_0003", "Kristall"),      # ok
            ("OBJ_0004", "kristall"),      # Case-Tippfehler (Kleinbuchstabe)
            ("OBJ_0005", "Probe"),         # frei erfunden
            ("OBJ_0006", "Mineralkorn"),   # ohne Bindestrich (Soll: Mineral-Korn)
            ("OBJ_0007", None),            # legitim (noch nicht kategorisiert)
            ("OBJ_0008", ""),              # legitim (Default-Leerstring)
            ("OBJ_0009", "   "),           # legitim (Whitespace = leer)
        ],
    )
    c.commit()
    rep = check_integrity(c)
    # Sortiert nach obj_id; NULL/Leerstring/Whitespace tauchen nicht auf.
    assert rep.unknown_kategorie == [
        ("OBJ_0002", "Handstuck"),
        ("OBJ_0004", "kristall"),
        ("OBJ_0005", "Probe"),
        ("OBJ_0006", "Mineralkorn"),
    ]
    assert not rep.is_clean
    c.close()


def test_unknown_kategorie_migrierte_db_clean(migrated_conn):
    """Migrierte Beispiel-DB nutzt ausschliesslich gueltige Kategorie-Werte."""
    rep = check_integrity(migrated_conn)
    assert rep.unknown_kategorie == []


def test_unknown_kategorie_in_as_dict_serialisierbar(tmp_path):
    """as_dict liefert Tuples als Listen, damit das JSON-Format roundtrip-fest ist."""
    import json
    c = open_db(tmp_path / "ak.sqlite3")
    c.execute("INSERT INTO objects (obj_id, Kategorie) VALUES (?, ?)",
              ("OBJ_0001", "Probe"))
    c.commit()
    d = check_integrity(c).as_dict()
    assert d["unknown_kategorie"] == [["OBJ_0001", "Probe"]]
    json.dumps(d, ensure_ascii=False)  # darf nicht crashen
    c.close()


def test_unknown_kristallsystem_wird_erkannt(tmp_path):
    """Kristallsystem ausserhalb des Feldwoerterbuch-Enums wird gemeldet
    (obj_id, kristallsystem). Spiegelt unknown_kategorie auf die
    kristallographische Symmetrie-Achse: Schema hat keine CHECK-Klausel auf
    Kristallsystem, daher koennen Tippfehler ("Trigonal" mit Grossbuchstabe),
    Synonyme ("rhomboedrisch" als alternative Schreibweise zu "trigonal"),
    veraltete Schreibweisen ("rhombisch" statt "orthorhombisch") oder frei
    erfundene Werte ("hexagonal-isomorph") durch direkten DB-Zugriff oder
    fehlerhaften CSV-/JSON-Import einfliessen, ohne dass die Anwendung sie
    bemerkt. Leerstring/NULL bleiben legitim als "noch nicht eingeordnet"
    (der Normalfall vor mineralogischer Bestimmung)."""
    c = open_db(tmp_path / "uks.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
        [
            ("OBJ_0001", "trigonal"),                # ok (Feldwoerterbuch-Form)
            ("OBJ_0002", "Trigonal"),                # Case-Tippfehler
            ("OBJ_0003", "kubisch"),                 # ok
            ("OBJ_0004", "rhomboedrisch"),           # Synonym, nicht im Enum
            ("OBJ_0005", "rhombisch"),               # veraltet (statt orthorhombisch)
            ("OBJ_0006", "amorph"),                  # ok (Sonder-Klasse)
            ("OBJ_0007", "hexagonal-isomorph"),      # frei erfunden
            # Trailing-Klammer-Annotation: Basis-Symmetrie bleibt im Enum-Wert,
            # die Sub-Klassifizierung in Klammern wird vor dem Vergleich
            # gestrippt - eine mineralogisch ueblicher Notations-Stil.
            ("OBJ_0008", "trigonal (mikrokristallin)"),  # ok (Trailing-Annotation)
            ("OBJ_0009", "kubisch [grobkristallin]"),    # ok (eckige Klammern)
            ("OBJ_0010", "hexagonal {saeulenfoermig}"),  # ok (geschwungene Klammern)
            ("OBJ_0011", "Trigonal (mikrokristallin)"),  # Case-Tippfehler trotz Annotation
            ("OBJ_0012", None),                      # legitim (noch nicht eingeordnet)
            ("OBJ_0013", ""),                        # legitim (Default-Leerstring)
            ("OBJ_0014", "   "),                     # legitim (Whitespace = leer)
        ],
    )
    c.commit()
    rep = check_integrity(c)
    # Sortiert nach obj_id; NULL/Leerstring/Whitespace und Werte mit gueltigem
    # Enum-Kern (mit oder ohne Klammer-Annotation) tauchen nicht auf.
    assert rep.unknown_kristallsystem == [
        ("OBJ_0002", "Trigonal"),
        ("OBJ_0004", "rhomboedrisch"),
        ("OBJ_0005", "rhombisch"),
        ("OBJ_0007", "hexagonal-isomorph"),
        ("OBJ_0011", "Trigonal (mikrokristallin)"),
    ]
    assert not rep.is_clean
    c.close()


def test_unknown_kristallsystem_migrierte_db_clean(migrated_conn):
    """Migrierte Beispiel-DB nutzt ausschliesslich gueltige Kristallsystem-Werte
    (oder NULL/leer als "noch nicht eingeordnet")."""
    rep = check_integrity(migrated_conn)
    assert rep.unknown_kristallsystem == []


def test_unknown_kristallsystem_in_as_dict_serialisierbar(tmp_path):
    """as_dict liefert Tuples als Listen, damit das JSON-Format roundtrip-fest ist."""
    import json
    c = open_db(tmp_path / "aks.sqlite3")
    c.execute("INSERT INTO objects (obj_id, Kristallsystem) VALUES (?, ?)",
              ("OBJ_0001", "Trigonal"))
    c.commit()
    d = check_integrity(c).as_dict()
    assert d["unknown_kristallsystem"] == [["OBJ_0001", "Trigonal"]]
    json.dumps(d, ensure_ascii=False)  # darf nicht crashen
    c.close()


def test_unknown_magnetismus_wird_erkannt(tmp_path):
    """Magnetismus ausserhalb des Feldwoerterbuch-Enums wird gemeldet
    (obj_id, magnetismus). Spiegelt unknown_kristallsystem auf die magnetische
    Reaktions-Achse: Schema hat keine CHECK-Klausel auf Magnetismus, daher
    koennen Tippfehler ("Nein" mit Grossbuchstabe), englische Form ("no"),
    physikalische Sub-Klassifizierung ("ferromagnetisch", "paramagnetisch")
    oder freie Werte ("magnetisch", "kein") durch direkten DB-Zugriff oder
    fehlerhaften CSV-/JSON-Import einfliessen, ohne dass die Anwendung sie
    bemerkt. Leerstring/NULL bleibt legitim als "noch nicht geprueft" (der
    Normalfall, bevor das Stueck mit einem Magneten getestet wurde).
    """
    c = open_db(tmp_path / "umg.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
        [
            ("OBJ_0001", "nein"),                  # ok (Feldwoerterbuch-Form)
            ("OBJ_0002", "Nein"),                  # Case-Tippfehler
            ("OBJ_0003", "schwach"),               # ok
            ("OBJ_0004", "ja"),                    # ok
            ("OBJ_0005", "no"),                    # englische Form
            ("OBJ_0006", "ferromagnetisch"),       # physikalische Sub-Klassifizierung
            ("OBJ_0007", "magnetisch"),            # freier Wert (statt ja/schwach)
            ("OBJ_0008", "kein"),                  # ohne Endung
            # Trailing-Klammer-Annotation: Basis-Stufe bleibt im Enum-Wert,
            # die Sub-Klassifizierung in Klammern (Erklaerung der Reaktion,
            # vermutete Ursache) wird vor dem Vergleich gestrippt - ueblich in
            # Pruef-Notizen ("schwach (Haematit-Beimischung)").
            ("OBJ_0009", "schwach (Haematit-Beimischung)"),  # ok (Annotation)
            ("OBJ_0010", "ja [stark]"),                       # ok (eckige Klammern)
            ("OBJ_0011", "nein {gepruefter Neodym-Magnet}"),  # ok (geschwungene Klammern)
            ("OBJ_0012", "Schwach (Haematit-Beimischung)"),   # Case-Tippfehler trotz Annotation
            ("OBJ_0013", None),                    # legitim (noch nicht geprueft)
            ("OBJ_0014", ""),                      # legitim (Default-Leerstring)
            ("OBJ_0015", "   "),                   # legitim (Whitespace = leer)
        ],
    )
    c.commit()
    rep = check_integrity(c)
    # Sortiert nach obj_id; NULL/Leerstring/Whitespace und Werte mit gueltigem
    # Enum-Kern (mit oder ohne Klammer-Annotation) tauchen nicht auf.
    assert rep.unknown_magnetismus == [
        ("OBJ_0002", "Nein"),
        ("OBJ_0005", "no"),
        ("OBJ_0006", "ferromagnetisch"),
        ("OBJ_0007", "magnetisch"),
        ("OBJ_0008", "kein"),
        ("OBJ_0012", "Schwach (Haematit-Beimischung)"),
    ]
    assert not rep.is_clean
    c.close()


def test_unknown_magnetismus_migrierte_db_clean(migrated_conn):
    """Migrierte Beispiel-DB nutzt ausschliesslich gueltige Magnetismus-Werte
    (oder NULL/leer als "noch nicht geprueft")."""
    rep = check_integrity(migrated_conn)
    assert rep.unknown_magnetismus == []


def test_unknown_magnetismus_in_as_dict_serialisierbar(tmp_path):
    """as_dict liefert Tuples als Listen, damit das JSON-Format roundtrip-fest ist."""
    import json
    c = open_db(tmp_path / "amg.sqlite3")
    c.execute("INSERT INTO objects (obj_id, Magnetismus) VALUES (?, ?)",
              ("OBJ_0001", "Nein"))
    c.commit()
    d = check_integrity(c).as_dict()
    assert d["unknown_magnetismus"] == [["OBJ_0001", "Nein"]]
    json.dumps(d, ensure_ascii=False)  # darf nicht crashen
    c.close()


def test_unknown_beste_verwendung_wird_erkannt(tmp_path):
    """Beste_Verwendung ausserhalb des Feldwoerterbuch-Enums wird gemeldet
    (obj_id, beste_verwendung). Spiegelt unknown_magnetismus auf die
    Verwendungs-/Vermarktungs-Empfehlungs-Achse: Schema hat keine CHECK-Klausel
    auf Beste_Verwendung, daher koennen Tippfehler ("schmuck" mit Kleinbuchstabe),
    englische Form ("jewelry"/"collection"), Kombinationsformen ("Schmuck+Sammlung")
    oder freie/veraltete Werte ("Verkauf", "Handel", "Boerse") durch direkten
    DB-Zugriff oder fehlerhaften CSV-/JSON-Import einfliessen, ohne dass die
    Anwendung sie bemerkt. Trailing-Klammer-Annotationen und Trailing-Slash-
    Sub-Klassifikationen ("Sammlung/Lehrzwecke", "Forschung/Univ. Bern") sind
    legitime Sammler-Konvention und werden vor dem Enum-Vergleich gestrippt.
    Leerstring/NULL bleibt legitim als "noch nicht entschieden".
    """
    c = open_db(tmp_path / "ubv.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
        [
            ("OBJ_0001", "Schmuck"),                # ok (Feldwoerterbuch-Form)
            ("OBJ_0002", "schmuck"),                # Case-Tippfehler
            ("OBJ_0003", "Sammlung"),               # ok
            ("OBJ_0004", "Forschung"),              # ok
            ("OBJ_0005", "Industrie"),              # ok
            ("OBJ_0006", "Talisman"),               # ok
            ("OBJ_0007", "Dekoration"),             # ok
            ("OBJ_0008", "jewelry"),                # englische Form
            ("OBJ_0009", "collection"),             # englische Form
            ("OBJ_0010", "Schmuck+Sammlung"),       # Kombinationsform
            ("OBJ_0011", "Verkauf"),                # freier/veralteter Wert
            ("OBJ_0012", "Handel"),                 # freier/veralteter Wert
            ("OBJ_0013", "Boerse"),                 # freier/veralteter Wert
            # Trailing-Slash-Sub-Klassifikation: Basis-Verwendung vor dem
            # Slash bleibt im Enum-Wert, die Sub-Klassifikation nach dem Slash
            # (Zweck/Zielinstitution/Vertriebsweg) wird vor dem Vergleich
            # gestrippt - ueblich in DE-Sammler-Notation als Kompound-
            # Klassifikation ("Sammlung/Lehrzwecke" = Sammlung + Lehrzweck).
            ("OBJ_0014", "Sammlung/Lehrzwecke"),           # ok (Slash-Sub-Klassifikation)
            ("OBJ_0015", "Forschung/Univ. Bern"),          # ok (Zielinstitution)
            ("OBJ_0016", "schmuck/Anhaenger"),             # Case-Tippfehler trotz Slash-Sub
            # Trailing-Klammer-Annotation: Basis-Verwendung bleibt im Enum-Wert,
            # die Sub-Klassifizierung in Klammern (Vermarktungs-Details,
            # Vitrinen-Platz, Zielinstitution) wird vor dem Vergleich gestrippt
            # - ueblich in Pflege-Notizen ("Schmuck (Anhaenger)",
            # "Sammlung [Vitrine 3]", "Forschung {Uni Bern}").
            ("OBJ_0017", "Schmuck (Anhaenger)"),           # ok (Annotation)
            ("OBJ_0018", "Sammlung [Vitrine 3]"),          # ok (eckige Klammern)
            ("OBJ_0019", "Forschung {Uni Bern}"),          # ok (geschwungene Klammern)
            ("OBJ_0020", "schmuck (Anhaenger)"),           # Case-Tippfehler trotz Annotation
            ("OBJ_0021", None),                     # legitim (noch nicht entschieden)
            ("OBJ_0022", ""),                       # legitim (Default-Leerstring)
            ("OBJ_0023", "   "),                    # legitim (Whitespace = leer)
        ],
    )
    c.commit()
    rep = check_integrity(c)
    # Sortiert nach obj_id; NULL/Leerstring/Whitespace und Werte mit gueltigem
    # Enum-Kern (mit oder ohne Klammer-Annotation oder Slash-Sub-Klassifikation)
    # tauchen nicht auf.
    assert rep.unknown_beste_verwendung == [
        ("OBJ_0002", "schmuck"),
        ("OBJ_0008", "jewelry"),
        ("OBJ_0009", "collection"),
        ("OBJ_0010", "Schmuck+Sammlung"),
        ("OBJ_0011", "Verkauf"),
        ("OBJ_0012", "Handel"),
        ("OBJ_0013", "Boerse"),
        ("OBJ_0016", "schmuck/Anhaenger"),
        ("OBJ_0020", "schmuck (Anhaenger)"),
    ]
    assert not rep.is_clean
    c.close()


def test_unknown_beste_verwendung_migrierte_db_clean(migrated_conn):
    """Migrierte Beispiel-DB nutzt ausschliesslich gueltige Beste_Verwendung-
    Werte (oder NULL/leer als "noch nicht entschieden")."""
    rep = check_integrity(migrated_conn)
    assert rep.unknown_beste_verwendung == []


def test_unknown_beste_verwendung_in_as_dict_serialisierbar(tmp_path):
    """as_dict liefert Tuples als Listen, damit das JSON-Format roundtrip-fest ist."""
    import json
    c = open_db(tmp_path / "abv.sqlite3")
    c.execute("INSERT INTO objects (obj_id, Beste_Verwendung) VALUES (?, ?)",
              ("OBJ_0001", "jewelry"))
    c.commit()
    d = check_integrity(c).as_dict()
    assert d["unknown_beste_verwendung"] == [["OBJ_0001", "jewelry"]]
    json.dumps(d, ensure_ascii=False)  # darf nicht crashen
    c.close()


def test_geaendert_vor_erstellt_wird_erkannt(tmp_path):
    """geaendert_am < erstellt_am ist logisch unmoeglich und sollte gemeldet werden.

    Die App-Pipeline (create/update_fields) setzt beide Stempel monoton wachsend;
    die Inkonsistenz kann nur durch JSON-Import aus einer korrupten Quelle,
    manuelle DB-Editierung oder Clock-Skew zwischen Migrationsmaschinen entstehen.
    """
    c = open_db(tmp_path / "ts.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2024-06-13 10:00:00", "2024-06-13 10:00:00"),  # gleich → ok
            ("OBJ_0002", "2024-06-13 10:00:00", "2024-06-13 12:00:00"),  # geaendert > erstellt → ok
            ("OBJ_0003", "2024-06-13 12:00:00", "2024-06-13 10:00:00"),  # invertiert → flag
            ("OBJ_0004", "2024-06-13 10:00:00", "2023-06-13 10:00:00"),  # Jahr invertiert → flag
            ("OBJ_0005", None, None),                                     # beide leer → uebergangen
            ("OBJ_0006", "", ""),                                         # leere Strings → uebergangen
            ("OBJ_0007", "2024-06-13 10:00:00", None),                    # nur erstellt → uebergangen
            ("OBJ_0008", None, "2024-06-13 10:00:00"),                    # nur geaendert → uebergangen
        ],
    )
    c.commit()
    rep = check_integrity(c)
    flagged = {oid for oid, _, _ in rep.geaendert_vor_erstellt}
    assert flagged == {"OBJ_0003", "OBJ_0004"}
    assert ("OBJ_0003", "2024-06-13 12:00:00", "2024-06-13 10:00:00") in rep.geaendert_vor_erstellt
    assert not rep.is_clean
    # as_dict serialisierbar
    import json
    d = rep.as_dict()
    assert ["OBJ_0003", "2024-06-13 12:00:00", "2024-06-13 10:00:00"] in d["geaendert_vor_erstellt"]
    json.dumps(d, ensure_ascii=False)
    c.close()


def test_geaendert_vor_erstellt_migrierte_db_clean(migrated_conn):
    """Die migrierte Beispiel-DB hat monotone Zeitstempel (Pipeline-Garantie)."""
    rep = check_integrity(migrated_conn)
    assert rep.geaendert_vor_erstellt == []


def test_future_erstellt_am_wird_erkannt(tmp_path):
    """erstellt_am in der Zukunft ist logisch unmoeglich (Clock-Skew / JSON-Restore).

    Spiegelt future_funddatum auf die erstellt_am-Achse: das Objekt kann nicht
    "morgen" erfasst worden sein. Tritt durch Clock-Skew zwischen Migrations-
    maschinen, JSON-Restore aus einem inkonsistenten Backup, manuelle DB-
    Editierung oder Reisen mit verstellter Laptop-Zeit auf.
    """
    c = open_db(tmp_path / "fut_erstellt.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am) VALUES (?, ?)",
        [
            ("OBJ_0001", "2024-06-13 10:00:00"),  # Vergangenheit → ok
            ("OBJ_0002", "2024-06-13 11:59:59"),  # eine Sekunde vor now → ok
            ("OBJ_0003", "2024-06-13 12:00:01"),  # eine Sekunde nach now → flag
            ("OBJ_0004", "2099-12-31 23:59:59"),  # weit in der Zukunft → flag
            ("OBJ_0005", None),                    # NULL → uebergangen
            ("OBJ_0006", ""),                      # leer → uebergangen
            ("OBJ_0007", "   "),                   # Whitespace → uebergangen
        ],
    )
    c.commit()
    rep = check_integrity(
        c, now=datetime.datetime(2024, 6, 13, 12, 0, 0))
    flagged = {oid for oid, _ in rep.future_erstellt_am}
    assert flagged == {"OBJ_0003", "OBJ_0004"}
    assert ("OBJ_0004", "2099-12-31 23:59:59") in rep.future_erstellt_am
    assert not rep.is_clean
    # as_dict serialisierbar (neuer Feldname enthalten)
    import json
    d = rep.as_dict()
    assert ["OBJ_0004", "2099-12-31 23:59:59"] in d["future_erstellt_am"]
    json.dumps(d, ensure_ascii=False)
    c.close()


def test_future_erstellt_am_default_now_keine_falsch_positiven(migrated_conn):
    """Die migrierte Beispiel-DB hat keine Zukunfts-erstellt_am (Pipeline-Garantie)."""
    rep = check_integrity(migrated_conn)
    assert rep.future_erstellt_am == []


def test_future_geaendert_am_wird_erkannt(tmp_path):
    """geaendert_am in der Zukunft ist logisch unmoeglich (Clock-Skew / JSON-Restore).

    Spiegelt future_erstellt_am auf die letzte-Aenderungs-Achse und schliesst
    die Luecke, die geaendert_vor_erstellt offen liess: ein Stempel-Paar mit
    erstellt_am=2024 und geaendert_am=2099 bestaende den Inter-Stempel-Test
    (geaendert > erstellt → ok), waere aber offensichtlich falsch (Aenderung
    in der Zukunft). Das Trio future_funddatum / future_erstellt_am /
    future_geaendert_am deckt jetzt alle drei Zeit-Achsen ab.
    """
    c = open_db(tmp_path / "fut_geaendert.sqlite3")
    c.executemany(
        "INSERT INTO objects (obj_id, erstellt_am, geaendert_am) VALUES (?, ?, ?)",
        [
            ("OBJ_0001", "2020-01-01 00:00:00", "2024-06-13 10:00:00"),  # Vergangenheit → ok
            ("OBJ_0002", "2020-01-01 00:00:00", "2024-06-13 11:59:59"),  # eine Sekunde vor now → ok
            ("OBJ_0003", "2020-01-01 00:00:00", "2024-06-13 12:00:01"),  # eine Sekunde nach now → flag
            ("OBJ_0004", "2020-01-01 00:00:00", "2099-12-31 23:59:59"),  # weit in der Zukunft → flag
            ("OBJ_0005", "2020-01-01 00:00:00", None),                    # NULL → uebergangen
            ("OBJ_0006", "2020-01-01 00:00:00", ""),                      # leer → uebergangen
            ("OBJ_0007", "2020-01-01 00:00:00", "   "),                   # Whitespace → uebergangen
        ],
    )
    c.commit()
    rep = check_integrity(
        c, now=datetime.datetime(2024, 6, 13, 12, 0, 0))
    flagged = {oid for oid, _ in rep.future_geaendert_am}
    assert flagged == {"OBJ_0003", "OBJ_0004"}
    assert ("OBJ_0004", "2099-12-31 23:59:59") in rep.future_geaendert_am
    assert not rep.is_clean
    # geaendert_vor_erstellt darf NICHT triggern (geaendert > erstellt, korrekte
    # Reihenfolge) - das ist genau die Luecke, die future_geaendert_am schliesst:
    # eine Zukunfts-Aenderung mit Vergangenheits-Erstellung ist offensichtlich
    # falsch, bestand aber den relativen Reihenfolge-Test.
    assert rep.geaendert_vor_erstellt == []
    # as_dict serialisierbar (neuer Feldname enthalten)
    import json
    d = rep.as_dict()
    assert ["OBJ_0004", "2099-12-31 23:59:59"] in d["future_geaendert_am"]
    json.dumps(d, ensure_ascii=False)
    c.close()


def test_future_geaendert_am_default_now_keine_falsch_positiven(migrated_conn):
    """Die migrierte Beispiel-DB hat keine Zukunfts-geaendert_am (Pipeline-Garantie)."""
    rep = check_integrity(migrated_conn)
    assert rep.future_geaendert_am == []


def test_find_duplicate_image_sha256(tmp_path):
    """Bilder mit identischem SHA-256 werden gruppiert (id-Liste pro Hash)."""
    from stonebook.db.integrity import find_duplicate_image_sha256
    c = open_db(tmp_path / "dup.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0002')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path, sha256) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg", "aaaa"),
            ("OBJ_0002", "Kamera", "b.jpg", "aaaa"),     # Dublette zu a.jpg
            ("OBJ_0001", "Mikroskop", "c.jpg", "bbbb"),  # einmalig
            ("OBJ_0001", "UV365", "d.jpg", "cccc"),
            ("OBJ_0002", "UV365", "e.jpg", "cccc"),
            ("OBJ_0002", "UV395", "f.jpg", "cccc"),      # Dreifach-Gruppe
            ("OBJ_0001", "Sonstige", "g.jpg", None),     # NULL → ignoriert
            ("OBJ_0001", "Sonstige", "h.jpg", ""),       # leer → ignoriert
        ],
    )
    c.commit()
    dups = find_duplicate_image_sha256(c)
    assert len(dups) == 2
    # Groesste Gruppe zuerst (cccc mit 3), danach aaaa mit 2
    assert dups[0][0] == "cccc"
    assert len(dups[0][1]) == 3
    assert dups[1][0] == "aaaa"
    assert len(dups[1][1]) == 2
    # id-Listen sind aufsteigend sortiert
    assert dups[0][1] == sorted(dups[0][1])
    c.close()


def test_find_duplicate_image_sha256_keine_dubletten(tmp_path):
    from stonebook.db.integrity import find_duplicate_image_sha256
    c = open_db(tmp_path / "k.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.executemany(
        "INSERT INTO images (obj_id, kategorie, rel_path, sha256) VALUES (?,?,?,?)",
        [
            ("OBJ_0001", "Kamera", "a.jpg", "aaaa"),
            ("OBJ_0001", "Mikroskop", "b.jpg", "bbbb"),
        ],
    )
    c.commit()
    assert find_duplicate_image_sha256(c) == []
    c.close()


def test_find_duplicate_image_sha256_in_migrierter_db(migrated_conn):
    """Auf der echten DB darf der Aufruf nicht crashen und liefert eine Liste."""
    from stonebook.db.integrity import find_duplicate_image_sha256
    dups = find_duplicate_image_sha256(migrated_conn)
    assert isinstance(dups, list)
    # Format-Sanity: jede Gruppe ist (str, list[int])
    for sha, ids in dups:
        assert isinstance(sha, str) and sha
        assert all(isinstance(i, int) for i in ids)
        assert len(ids) > 1


def test_orphan_ki_analysen_wird_erkannt(tmp_path):
    """ki_analysen-Eintraege ohne zugehoeriges Objekt werden gemeldet.

    Spiegelt orphan_images auf die KI-Analyse-Tabelle: das Schema hat ein
    FK mit ON DELETE CASCADE auf objects(obj_id), daher kann die regulaere
    Anwendung keine Orphans erzeugen. Sie koennen aber durch JSON-Restore
    aus einem partiellen Backup (Analyse-Tabelle wiederhergestellt ohne
    die zugehoerigen Objekte), direkte DB-Editierung mit PRAGMA
    foreign_keys=OFF oder fehlerhafte Migrations-Skripte entstehen. Der
    Test simuliert diese Situation, indem er das FK-PRAGMA temporaer
    abschaltet und Orphans direkt einfuegt.
    """
    c = open_db(tmp_path / "orph.sqlite3")
    c.execute("INSERT INTO objects (obj_id) VALUES ('OBJ_0001')")
    c.execute(
        "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) "
        "VALUES (?, ?, ?, ?)",
        ("OBJ_0001", "2024-01-01 00:00:00", "claude-sonnet-4-6", "{}"),
    )
    c.commit()
    # FK kann nur ausserhalb einer Transaktion umgeschaltet werden - daher
    # vor und nach dem Insert committen. Simuliert partiellen Restore /
    # korrupte DB-Editierung mit deaktiviertem FK.
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) "
        "VALUES (?, ?, ?, ?)",
        ("OBJ_0099_ghost", "2024-01-02 00:00:00", "claude-sonnet-4-6", "{}"),
    )
    c.commit()
    c.execute("PRAGMA foreign_keys = ON")
    rep = check_integrity(c)
    # Nur die Geist-Analyse taucht auf; die zu OBJ_0001 gehoerige nicht.
    assert len(rep.orphan_ki_analysen) == 1
    # Reine Liste von ki_analysen.id-Werten (nicht obj_id) - spiegelt orphan_images.
    assert all(isinstance(i, int) for i in rep.orphan_ki_analysen)
    assert not rep.is_clean
    c.close()


def test_orphan_ki_analysen_migrierte_db_clean(migrated_conn):
    """Migrierte Beispiel-DB hat keine KI-Analyse-Orphans (Migration erzeugt
    ki_analysen ueberhaupt nicht, FK + ON DELETE CASCADE haelt es sauber)."""
    rep = check_integrity(migrated_conn)
    assert rep.orphan_ki_analysen == []


def test_orphan_ki_analysen_in_as_dict_serialisierbar(tmp_path):
    """as_dict serialisiert die neue Liste roundtrip-fest (spiegelt orphan_images)."""
    import json
    c = open_db(tmp_path / "ojs.sqlite3")
    # FK kann nur ausserhalb einer Transaktion umgeschaltet werden; init_db
    # hat keine Transaktion offen, daher direkt OFF schalten und Orphan
    # einfuegen.
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) "
        "VALUES (?, ?, ?, ?)",
        ("OBJ_0099_ghost", "2024-01-02 00:00:00", "claude-sonnet-4-6", "{}"),
    )
    c.commit()
    d = check_integrity(c).as_dict()
    assert "orphan_ki_analysen" in d
    assert len(d["orphan_ki_analysen"]) == 1
    json.dumps(d, ensure_ascii=False)  # darf nicht crashen
    c.close()
