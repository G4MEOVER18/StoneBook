#!/usr/bin/env python3
Merge StoneBoock split ZIP parts into one repo folder (Windows-safe).

Usage (PowerShell):
  python MERGE_StoneBoock_Parts.py --parts-dir . --out-dir StoneBoock_REPO

Expected files in parts-dir:
  StoneBoock_objects_OBJ_*.zip
  StoneBoock_docs_chat_exports.zip
  StoneBoock_meta_mapping_manifest.zip
Optional:
  StoneBoock_legacy_originals.zip  (or parts to rejoin first)

This script extracts all StoneBoock_*.zip into out-dir.

import argparse, zipfile
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", default=".", help="Ordner mit den StoneBoock_*.zip Dateien")
    ap.add_argument("--out-dir", default="StoneBoock_REPO", help="Zielordner (Repo)")
    args = ap.parse_args()

    parts_dir = Path(args.parts_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zips = sorted(parts_dir.glob("StoneBoock_*.zip"))
    if not zips:
        raise SystemExit("Keine StoneBoock_*.zip gefunden.")

    for zp in zips:
        print(f"Extract: {zp.name}")
        with zipfile.ZipFile(zp, "r") as z:
            z.extractall(out_dir)

    print("\nOK. Repo gebaut unter:", out_dir.resolve())

if __name__ == "__main__":
    main()
