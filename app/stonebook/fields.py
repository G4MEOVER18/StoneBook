"""Die 43 Standardfelder aus data/csv/Stonebock__stoneboock_feldwoerterbuch_v2.csv (Projektstandard)."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldDef:
    name: str          # DB-Spaltenname, exakt wie Feldwörterbuch
    label: str         # deutsches GUI-Label
    ftype: str         # str | text | float | int | enum | date | path | scale
    group: str
    description: str = ""
    enum_values: tuple = ()
    editable: bool = True


G_ID = "Identifikation"
G_MIN = "Mineralogie"
G_PHY = "Physikalische Eigenschaften"
G_UV = "UV & Reaktionen"
G_FUND = "Fund"
G_FOTO = "Fotos"
G_MASS = "Masse & Gewicht"
G_WERT = "Bewertung & Wert"
G_SONST = "Sonstiges"

FIELDS: list[FieldDef] = [
    FieldDef("ID", "Objekt-ID", "str", G_ID, "Eindeutige Objekt-ID (OBJ_0001)", editable=False),
    FieldDef("Name", "Name", "str", G_ID, "Kurzname/Label"),
    FieldDef("Kategorie", "Kategorie", "enum", G_ID, "Art des Objekts",
             ("", "Mineral-Korn", "Handstück", "Dünnschliff", "Kristall", "Geröll", "Sonstiges")),
    FieldDef("Mineral_Primaer", "Hauptmineral", "str", G_MIN, "Hauptmineral"),
    FieldDef("Varietaet", "Varietät", "str", G_MIN, "z.B. Milchquarz, Jaspis"),
    FieldDef("Gesteinsart", "Gesteinsart", "str", G_MIN, "Petrologischer Zusammenhang"),
    FieldDef("Kristallsystem", "Kristallsystem", "enum", G_MIN, "Kristallsystem",
             ("", "kubisch", "tetragonal", "hexagonal", "trigonal", "orthorhombisch",
              "monoklin", "triklin", "amorph")),
    FieldDef("Mohs_Haerte_min", "Mohs-Härte min", "float", G_PHY, "Untere Mohs-Härtegrenze"),
    FieldDef("Mohs_Haerte_max", "Mohs-Härte max", "float", G_PHY, "Obere Mohs-Härtegrenze"),
    FieldDef("Dichte_min_gcm3", "Dichte min (g/cm³)", "float", G_PHY, "Mindestdichte"),
    FieldDef("Dichte_max_gcm3", "Dichte max (g/cm³)", "float", G_PHY, "Maximaldichte"),
    FieldDef("Spaltbarkeit", "Spaltbarkeit", "enum", G_PHY, "Spaltbarkeit",
             ("", "vollkommen", "gut", "deutlich", "undeutlich", "keine")),
    FieldDef("Bruch", "Bruch", "enum", G_PHY, "Bruchverhalten",
             ("", "muschelig", "uneben", "splittrig", "faserig", "erdig", "glatt")),
    FieldDef("Glanz", "Glanz", "enum", G_PHY, "Glanz",
             ("", "glasig", "wachsig", "matt", "metallisch", "fettig", "seidig", "perlmutt")),
    FieldDef("Transparenz", "Transparenz", "enum", G_PHY, "Lichtdurchlässigkeit",
             ("", "durchsichtig", "durchscheinend", "opak")),
    FieldDef("Farbe_beobachtet", "Farbe (beobachtet)", "str", G_PHY, "Tatsächlich gesehene Farbe(n)"),
    FieldDef("Strichfarbe", "Strichfarbe", "str", G_PHY, "Farbe des Pulvers auf Porzellantäfelchen"),
    FieldDef("UV_365nm", "UV 365 nm", "str", G_UV, "Fluoreszenzreaktion bei 365 nm"),
    FieldDef("UV_254nm", "UV 254 nm", "str", G_UV, "Fluoreszenzreaktion bei 254 nm"),
    FieldDef("Magnetismus", "Magnetismus", "enum", G_UV, "magnetisch ja/nein/schwach",
             ("", "nein", "schwach", "ja")),
    FieldDef("HCl_Reaktion", "HCl-Reaktion", "str", G_UV, "keine/schwach/stark; kalt/warm"),
    FieldDef("Reaktionshinweis", "Reaktionshinweis", "text", G_UV, "Erklärender Kommentar"),
    FieldDef("Fundort", "Fundort", "str", G_FUND, "Ort/Koordinate"),
    FieldDef("Funddatum", "Funddatum", "date", G_FUND, "YYYY-MM-DD"),
    FieldDef("Foto_Uebersicht", "Foto Übersicht", "path", G_FOTO, "Pfad zum Übersichtsbild"),
    FieldDef("Foto_UV395", "Foto UV 395", "path", G_FOTO, "Bild unter 395 nm"),
    FieldDef("Foto_UV365", "Foto UV 365", "path", G_FOTO, "Bild unter 365 nm"),
    FieldDef("Laenge_mm", "Länge (mm)", "float", G_MASS, "Maximale Ausdehnung"),
    FieldDef("Breite_mm", "Breite (mm)", "float", G_MASS, "Zweite Ausdehnung"),
    FieldDef("Hoehe_mm", "Höhe (mm)", "float", G_MASS, "Dritte Ausdehnung"),
    FieldDef("Gewicht_g", "Gewicht (g)", "float", G_MASS, "Masse"),
    FieldDef("Seltenheit_global_1_10", "Seltenheit global (1–10)", "scale", G_WERT, "1=häufig, 10=sehr selten global"),
    FieldDef("Seltenheit_Fundort_1_10", "Seltenheit Fundort (1–10)", "scale", G_WERT, "Bezogen auf Standort"),
    FieldDef("Nachfrage_1_10", "Nachfrage (1–10)", "scale", G_WERT, "Marktnachfrage"),
    FieldDef("Wert_CHF_roh", "Wert roh (CHF)", "float", G_WERT, "Schätzwert roh"),
    FieldDef("Wert_CHF_poliert", "Wert poliert (CHF)", "float", G_WERT, "Schätzwert poliert"),
    FieldDef("Wert_CHF_Schmuck", "Wert Schmuck (CHF)", "float", G_WERT, "Schätzwert Schmuck"),
    FieldDef("Wert_USD_Talisman", "Wert Talisman (USD)", "float", G_WERT, "Schätzwert Talisman"),
    FieldDef("Marktwert_Industrie", "Marktwert Industrie", "float", G_WERT, "Industrieller Marktwert"),
    FieldDef("Wissenschaftlicher_Wert_CHF", "Wissenschaftlicher Wert (CHF)", "float", G_WERT, "Einschätzung in CHF"),
    FieldDef("Beste_Verwendung", "Beste Verwendung", "enum", G_SONST, "Empfohlene Verwendung",
             ("", "Schmuck", "Sammlung", "Forschung", "Industrie", "Talisman", "Dekoration")),
    FieldDef("Pruefempfehlungen", "Prüfempfehlungen", "text", G_SONST, "Empfohlene Bestätigungstests"),
    FieldDef("Confidence_Prozent", "Confidence (%)", "int", G_SONST, "Sicherheitsgrad der Bestimmung"),
]

assert len(FIELDS) == 43  # alle Feldwörterbuch-Felder; ID liegt in der DB als obj_id-PK

FIELD_GROUPS: list[str] = [G_ID, G_MIN, G_PHY, G_UV, G_FUND, G_FOTO, G_MASS, G_WERT, G_SONST]

# Felder ohne ID (= DB-Spalten neben obj_id)
DATA_FIELDS: list[FieldDef] = [f for f in FIELDS if f.name != "ID"]
FIELD_BY_NAME: dict[str, FieldDef] = {f.name: f for f in FIELDS}

NUMERIC_TYPES = {"float", "int", "scale"}


def is_empty(value) -> bool:
    """True für None und für Strings, die nach trim() leer sind."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False

IMAGE_CATEGORIES = ["Uebersicht", "Kamera", "Mikroskop", "UV365", "UV395", "Sonderaufnahmen", "Sonstige"]
CATEGORY_LABELS = {
    "Uebersicht": "Übersicht",
    "Kamera": "Kamera",
    "Mikroskop": "Mikroskop",
    "UV365": "UV 365 nm",
    "UV395": "UV 395 nm",
    "Sonderaufnahmen": "Sonderaufnahmen",
    "Sonstige": "Sonstige",
}
# Kategorie → physischer Unterordnername (bestehende Repo-Konvention)
CATEGORY_FOLDERS = {
    "Uebersicht": "Übersicht",
    "Kamera": "Kamera",
    "Mikroskop": "Mikroskop",
    "UV365": "UV 365 nm",
    "UV395": "UV 395 nm",
    "Sonderaufnahmen": "Sonderaufnahmen",
    "Sonstige": "",
}
