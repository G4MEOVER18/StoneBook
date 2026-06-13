"""Normalisierung der Objekt-IDs: OBJ-001 / OBJ_0001 / 'Objekt 1' / 1 → OBJ_0001."""
import re

_PATTERNS = [
    re.compile(r"^OBJ[-_](\d+)$", re.IGNORECASE),
    re.compile(r"^Objekt\s+(\d+)$", re.IGNORECASE),
    re.compile(r"^(\d+)$"),
]


def normalize_id(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return f"OBJ_{raw:04d}" if raw > 0 else None
    text = str(raw).strip()
    for pat in _PATTERNS:
        m = pat.match(text)
        if m:
            return f"OBJ_{int(m.group(1)):04d}"
    return None


def obj_number(obj_id: str) -> int:
    return int(obj_id.split("_")[1])


def display_name(obj_id: str) -> str:
    return f"Objekt {obj_number(obj_id)}"
