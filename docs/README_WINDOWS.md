# StoneBoock – Windows Rebuilder

## A) Legacy-ZIP aus Part-Dateien zusammenbauen

### PowerShell (empfohlen)
1. Lege `StoneBoock_legacy_originals.part001`, `.part002`, ... in einen Ordner
2. Lege `REBUILD_Legacy_FromParts.ps1` in denselben Ordner
3. PowerShell im Ordner öffnen und ausführen:
```powershell
powershell -ExecutionPolicy Bypass -File .\REBUILD_Legacy_FromParts.ps1
```
Ergebnis: `StoneBoock_legacy_originals.zip`

### CMD
```cmd
REBUILD_Legacy_FromParts.cmd
```

## B) Alle StoneBoock ZIP-Parts zu einem Repo zusammenführen
Lege alle `StoneBoock_*.zip` (Objekte, Docs, Meta, optional Legacy) in einen Ordner und:
```powershell
python .\MERGE_StoneBoock_Parts.py --parts-dir . --out-dir StoneBoock_REPO
```

Danach ist `StoneBoock_REPO\` dein fertiges GitHub-Repo-Ordner.

## Hinweis
Wenn Downloads/Parts aus ChatGPT ablaufen: die Parts lokal aufbewahren und nur mit diesen Skripten arbeiten.
