"""Bildaufbereitung für die Claude-Vision-API."""
import base64
import io
from pathlib import Path

MAX_SIDE = 1568
JPEG_QUALITY = 80


def prepare_image(path: Path) -> tuple[str, str]:
    """Liefert (base64_jpeg, media_type). Verkleinert auf max. 1568 px lange Kante."""
    from PIL import Image
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = MAX_SIDE / max(w, h)
        if scale < 1:
            img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=JPEG_QUALITY)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


def default_selection(image_rows, max_images: int) -> list:
    """Vorauswahl: je 1 Bild pro Kategorie in sinnvoller Reihenfolge, dann auffüllen."""
    order = ["Uebersicht", "Kamera", "Mikroskop", "UV365", "UV395", "Sonderaufnahmen", "Sonstige"]
    selected, used = [], set()
    for cat in order:
        for r in image_rows:
            if r["kategorie"] == cat:
                selected.append(r)
                used.add(r["rel_path"])
                break
        if len(selected) >= max_images:
            return selected
    for r in image_rows:
        if len(selected) >= max_images:
            break
        if r["rel_path"] not in used:
            selected.append(r)
            used.add(r["rel_path"])
    return selected
