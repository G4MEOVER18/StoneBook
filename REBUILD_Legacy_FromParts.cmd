@echo off
setlocal enabledelayedexpansion
set OUT=StoneBoock_legacy_originals.zip

echo Rejoin: StoneBoock_legacy_originals.part*  ->  %OUT%
if not exist StoneBoock_legacy_originals.part001 (
  echo ERROR: StoneBoock_legacy_originals.part001 nicht gefunden im aktuellen Ordner.
  exit /b 1
)

copy /b StoneBoock_legacy_originals.part* "%OUT%" >nul
if errorlevel 1 (
  echo ERROR: copy /b fehlgeschlagen.
  exit /b 1
)
echo Fertig: %OUT%
