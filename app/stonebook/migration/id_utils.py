"""Normalisierung der Objekt-IDs: OBJ-001 / OBJ_0001 / 'Objekt 1' / 1 → OBJ_0001."""
import re

# Reihenfolge ist Priorität: spezifischere/strengere Muster zuerst, damit
# allgemeinere (z.B. ``^(\d+)$``) nicht ein anderes Muster ueberschatten.
_PATTERNS = [
    # Voll qualifiziert mit Separator: ``OBJ-001``, ``OBJ_0001``, ``obj-43``.
    re.compile(r"^OBJ[-_](\d+)$", re.IGNORECASE),
    # Kompaktform ohne Separator: ``OBJ001``, ``obj43`` -- verbreitet in
    # Datei-/Ordnernamen, in denen ``-``/``_`` weggelassen wird.
    re.compile(r"^OBJ(\d+)$", re.IGNORECASE),
    # Deutsche Langform mit Whitespace: ``Objekt 7``.
    re.compile(r"^Objekt\s+(\d+)$", re.IGNORECASE),
    # Englische Langform (Foto-Captions / EN-Notizen): ``Object 43``.
    re.compile(r"^Object\s+(\d+)$", re.IGNORECASE),
    # DE-Nummerierungs-Praefix: ``Nr. 43`` / ``Nr 43`` / ``Nr.43`` (mit/ohne Punkt/Whitespace).
    re.compile(r"^Nr\.?\s*(\d+)$", re.IGNORECASE),
    # Hash-Praefix (Foto-/Tagebuch-Notizen): ``#43`` / ``# 43``.
    re.compile(r"^#\s*(\d+)$"),
    # Reine Zahl: ``43``.
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
