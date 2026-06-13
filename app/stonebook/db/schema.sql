PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS objects (
    obj_id TEXT PRIMARY KEY,
    Name TEXT, Kategorie TEXT, Mineral_Primaer TEXT, Varietaet TEXT,
    Gesteinsart TEXT, Kristallsystem TEXT,
    Mohs_Haerte_min REAL, Mohs_Haerte_max REAL,
    Dichte_min_gcm3 REAL, Dichte_max_gcm3 REAL,
    Spaltbarkeit TEXT, Bruch TEXT, Glanz TEXT, Transparenz TEXT,
    Farbe_beobachtet TEXT, Strichfarbe TEXT,
    UV_365nm TEXT, UV_254nm TEXT, Magnetismus TEXT,
    HCl_Reaktion TEXT, Reaktionshinweis TEXT,
    Fundort TEXT, Funddatum TEXT,
    Foto_Uebersicht TEXT, Foto_UV395 TEXT, Foto_UV365 TEXT,
    Laenge_mm REAL, Breite_mm REAL, Hoehe_mm REAL, Gewicht_g REAL,
    Seltenheit_global_1_10 INTEGER, Seltenheit_Fundort_1_10 INTEGER,
    Nachfrage_1_10 INTEGER,
    Wert_CHF_roh REAL, Wert_CHF_poliert REAL, Wert_CHF_Schmuck REAL,
    Wert_USD_Talisman REAL, Marktwert_Industrie REAL,
    Wissenschaftlicher_Wert_CHF REAL,
    Beste_Verwendung TEXT, Pruefempfehlungen TEXT,
    Confidence_Prozent INTEGER,
    status TEXT NOT NULL DEFAULT 'platzhalter',
    folder_path TEXT,
    erstellt_am TEXT,
    geaendert_am TEXT,
    notizen TEXT
);

CREATE TABLE IF NOT EXISTS aliases (
    alias_id TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL REFERENCES objects(obj_id) ON DELETE CASCADE,
    merge_quelle TEXT
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY,
    obj_id TEXT NOT NULL REFERENCES objects(obj_id) ON DELETE CASCADE,
    kategorie TEXT NOT NULL,
    rel_path TEXT NOT NULL UNIQUE,
    dateiname TEXT,
    sha256 TEXT,
    exif_datum TEXT,
    breite_px INTEGER,
    hoehe_px INTEGER,
    herkunft_obj_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_images_obj ON images(obj_id);

CREATE TABLE IF NOT EXISTS ki_analysen (
    id INTEGER PRIMARY KEY,
    obj_id TEXT NOT NULL REFERENCES objects(obj_id) ON DELETE CASCADE,
    zeitpunkt TEXT,
    modell TEXT,
    antwort_json TEXT,
    uebernommen_json TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS objects_fts USING fts5(
    obj_id UNINDEXED,
    Name, Mineral_Primaer, Varietaet, Gesteinsart,
    Farbe_beobachtet, Fundort, Reaktionshinweis, Beste_Verwendung, notizen,
    content='objects', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS objects_ai AFTER INSERT ON objects BEGIN
    INSERT INTO objects_fts(rowid, obj_id, Name, Mineral_Primaer, Varietaet, Gesteinsart,
                            Farbe_beobachtet, Fundort, Reaktionshinweis, Beste_Verwendung, notizen)
    VALUES (new.rowid, new.obj_id, new.Name, new.Mineral_Primaer, new.Varietaet, new.Gesteinsart,
            new.Farbe_beobachtet, new.Fundort, new.Reaktionshinweis, new.Beste_Verwendung, new.notizen);
END;

CREATE TRIGGER IF NOT EXISTS objects_ad AFTER DELETE ON objects BEGIN
    INSERT INTO objects_fts(objects_fts, rowid, obj_id, Name, Mineral_Primaer, Varietaet, Gesteinsart,
                            Farbe_beobachtet, Fundort, Reaktionshinweis, Beste_Verwendung, notizen)
    VALUES ('delete', old.rowid, old.obj_id, old.Name, old.Mineral_Primaer, old.Varietaet, old.Gesteinsart,
            old.Farbe_beobachtet, old.Fundort, old.Reaktionshinweis, old.Beste_Verwendung, old.notizen);
END;

CREATE TRIGGER IF NOT EXISTS objects_au AFTER UPDATE ON objects BEGIN
    INSERT INTO objects_fts(objects_fts, rowid, obj_id, Name, Mineral_Primaer, Varietaet, Gesteinsart,
                            Farbe_beobachtet, Fundort, Reaktionshinweis, Beste_Verwendung, notizen)
    VALUES ('delete', old.rowid, old.obj_id, old.Name, old.Mineral_Primaer, old.Varietaet, old.Gesteinsart,
            old.Farbe_beobachtet, old.Fundort, old.Reaktionshinweis, old.Beste_Verwendung, old.notizen);
    INSERT INTO objects_fts(rowid, obj_id, Name, Mineral_Primaer, Varietaet, Gesteinsart,
                            Farbe_beobachtet, Fundort, Reaktionshinweis, Beste_Verwendung, notizen)
    VALUES (new.rowid, new.obj_id, new.Name, new.Mineral_Primaer, new.Varietaet, new.Gesteinsart,
            new.Farbe_beobachtet, new.Fundort, new.Reaktionshinweis, new.Beste_Verwendung, new.notizen);
END;

PRAGMA user_version = 1;
