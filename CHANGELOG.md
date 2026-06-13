# Changelog

## v3.0 — Sammlungsverwaltung (2026-06)

Neue Desktop-App unter `app/` als Nachfolger des früheren MakeObject-Stubs.

### Neu
- **SQLite-Datenmodell** mit 43 Standardfeldern (Feldwörterbuch v2) und FTS5-Volltextsuche.
- **Migration**: vereinheitlicht die 4 historischen CSV-Schemata, merged ~30 Duplikat-Gruppen
  automatisch (600 → 546 Objekte, 54 Aliase), indexiert die Bilder (SHA256-Manifest, EXIF).
- **GUI** (PySide6): Objektliste mit Filtern, generisches Datenblatt, Bildergalerie,
  Neues-Objekt-Assistent, Berichte.
- **KI-Analyse**: Bildbestimmung mit Confidence pro Feld und selektiver Übernahme.
  Backend wählbar zwischen **Claude (Cloud)** und **lokalen Modellen** (Ollama, Open-WebUI,
  LM Studio, KI-Core / OpenClaw-Gateway).
- **Dashboard** mit Kennzahlen und Verteilungen.
- **Modernes dunkles Theme**.
- **Export** CSV / JSON / DOCX.
- **Packaging**: PyInstaller-Spec (onedir) + Inno-Setup-Installer.
- **30 Tests** (Migration, CSV-Parser, Duplikate, Export, KI-Parser, Statistik).

### Vorher (v1–v2)
- Split-Archive-Edition mit Rekonstruktion aus ZIP-Teilen, inkonsistente CSV-Schemata,
  keine Datenbank oder GUI.
