"""Indexiert Bilder unter objects/ in die images-Tabelle."""
import hashlib
import json
import unicodedata
from pathlib import Path

from stonebook.db.repository import ImageRepo

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".heic"}

_FOLDER_TO_CATEGORY = {
    "übersicht": "Uebersicht",
    "uebersicht": "Uebersicht",
    "├£bersicht": "Uebersicht",  # Mojibake-Altlast (UTF-8 als CP850 fehlinterpretiert)
    "kamera": "Kamera",
    "mikroskop": "Mikroskop",
    "uv 365 nm": "UV365",
    "uv365": "UV365",
    "uv 395 nm": "UV395",
    "uv395": "UV395",
    "sonderaufnahmen": "Sonderaufnahmen",
}


def folder_category(folder_name: str) -> str:
    key = unicodedata.normalize("NFC", folder_name).strip().lower()
    return _FOLDER_TO_CATEGORY.get(key, "Sonstige")


def _exif_and_size(path: Path) -> tuple[str, int | None, int | None]:
    try:
        from PIL import Image
        with Image.open(path) as img:
            w, h = img.size
            exif = img.getexif()
            # 36867 = DateTimeOriginal, 306 = DateTime
            raw = exif.get(36867) or exif.get(306) or ""
            datum = ""
            if raw:
                datum = str(raw).replace(":", "-", 2)[:19]
            return datum, w, h
    except Exception:
        return "", None, None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(root: Path) -> dict[str, str]:
    manifest = root / "meta" / "manifest_sha256.json"
    if manifest.is_file():
        return json.loads(manifest.read_text(encoding="utf-8"))
    return {}


def index_images(root: Path, images: ImageRepo, known_ids: set[str],
                 alias_map: dict[str, str], log) -> int:
    """alias_map: gemergte ID → kanonische ID (Ordner der Aliase existieren physisch weiter)."""
    manifest = load_manifest(root)
    objects_dir = root / "objects"
    count = 0
    unknown_folders: set[str] = set()
    for obj_dir in sorted(objects_dir.iterdir()):
        if not obj_dir.is_dir() or not obj_dir.name.startswith("OBJ_"):
            continue
        target_id = alias_map.get(obj_dir.name, obj_dir.name)
        herkunft = obj_dir.name if obj_dir.name in alias_map else ""
        if target_id not in known_ids:
            log(f"  Hinweis: {obj_dir.name} nicht in DB (übersprungen)")
            continue
        for f in sorted(obj_dir.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in IMG_EXT:
                continue
            rel = f.relative_to(root).as_posix()
            # Kategorie aus dem ersten Pfadsegment unter dem Objektordner
            # (Unterordner wie Sonderaufnahmen\<Detailname>\ erben die Kategorie)
            parts = f.relative_to(obj_dir).parts
            if len(parts) == 1:
                cat = "Sonstige"
            else:
                cat = folder_category(parts[0])
                if cat == "Sonstige":
                    unknown_folders.add(parts[0])
            sha = manifest.get(rel) or _sha256(f)
            exif_datum, w, h = _exif_and_size(f)
            images.add(target_id, cat, rel, dateiname=f.name, sha256=sha,
                       exif_datum=exif_datum, breite_px=w, hoehe_px=h,
                       herkunft_obj_id=herkunft)
            count += 1
    for name in sorted(unknown_folders):
        log(f"  Unbekannter Kategorie-Ordner: '{name}' → Sonstige")
    return count
