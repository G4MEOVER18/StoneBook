# StoneBook V3 — Sammlungsverwaltung

Offline-Desktop-App (Windows 11) zur Verwaltung der Gesteins-/Mineraliensammlung
"StoneBoock". Python + PySide6 + SQLite, mit KI-gestützter Mineral-Analyse über die
Claude-API.

## Funktionen

- **Objektdatenbank** mit 43 Standardfeldern (Feldwörterbuch v2), Volltextsuche (FTS5),
  Filter nach Status/Mineral/Bildern
- **Bildergalerie** pro Objekt (Übersicht, Kamera, Mikroskop, UV 365/395 nm, Sonderaufnahmen)
  mit Thumbnail-Cache und Vollbild-Zoom
- **KI-Analyse**: Fotos + Felddaten an Claude (Vision) senden, strukturierte Vorschläge für
  alle Felder mit Confidence-Werten, selektive Übernahme
- **Neues-Objekt-Assistent**: Bilder aus Quellordner automatisch kategorisieren, Ordnerstruktur
  anlegen (ersetzt das alte MakeObject-Tool)
- **Export**: CSV (44 Spalten), JSON-Vollexport, DOCX-Analysebericht pro Objekt
- **Duplikat-Merge**: ~30 dokumentierte Duplikat-Gruppen werden bei der Migration automatisch
  zusammengeführt (alte IDs als Aliase)

## Start (Entwicklung)

```bash
pip install -r requirements.txt
python -m stonebook                       # GUI starten
python -m stonebook.migration.migrate     # Datenbank (neu) aufbauen
pytest tests                              # Tests
```

Die App erkennt den Repo-Ordner automatisch (der Ordner mit `objects\` und `data\`).
Die SQLite-DB unter `data\db\stonebook.sqlite3` ist nicht versioniert und jederzeit aus den
CSV-Quellen regenerierbar — versioniert wird der CSV-Export `data\csv\export_latest.csv`.

## KI-Analyse einrichten

In **Einstellungen** den Anthropic-API-Key hinterlegen (wird im Windows Credential Manager
gespeichert, nie im Klartext). Modell wählbar: `claude-sonnet-4-6` (Standard) oder
`claude-opus-4-7`.

## Build (EXE + Installer)

```bash
pip install pyinstaller
pyinstaller build/stonebook.spec --noconfirm
# danach build/installer.iss mit Inno Setup kompilieren → StoneBook_V3_Setup.exe
```
