#!/usr/bin/env python3
"""Merge StoneBoock split ZIP parts into one repo folder.

Usage (Windows PowerShell):
  python scripts\merge_parts.py --parts-dir . --out-dir StoneBoock_REPO

Put all split zip files in one directory, then run this.
"""
import argparse, zipfile
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", default=".", help="Directory containing split ZIP parts")
    ap.add_argument("--out-dir", default="StoneBoock_REPO", help="Output directory")
    args = ap.parse_args()

    parts_dir = Path(args.parts_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zips = sorted(parts_dir.glob("StoneBoock_*.zip"))
    if not zips:
        raise SystemExit("No StoneBoock_*.zip files found in parts-dir")

    for zp in zips:
        print(f"Extracting {zp.name} ...")
        with zipfile.ZipFile(zp, "r") as z:
            z.extractall(out_dir)

    print("\nDone. Repo assembled at:", out_dir.resolve())

if __name__ == "__main__":
    main()
