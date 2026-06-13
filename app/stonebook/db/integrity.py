"""Konsistenzprüfungen über die Objekt-DB (für Wartung/Diagnose)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from stonebook.migration.validators import parse_iso_date


@dataclass
class IntegrityReport:
    orphan_images: list[int] = field(default_factory=list)          # image.id
    alias_to_missing: list[str] = field(default_factory=list)       # alias_id
    alias_id_collisions: list[str] = field(default_factory=list)    # alias_id existiert auch als Objekt
    invalid_funddatum: list[str] = field(default_factory=list)      # obj_id
    missing_image_files: list[tuple[int, str]] = field(default_factory=list)  # (id, rel_path)

    @property
    def is_clean(self) -> bool:
        return not (self.orphan_images or self.alias_to_missing
                    or self.alias_id_collisions or self.invalid_funddatum
                    or self.missing_image_files)

    def as_dict(self) -> dict:
        return {
            "orphan_images": list(self.orphan_images),
            "alias_to_missing": list(self.alias_to_missing),
            "alias_id_collisions": list(self.alias_id_collisions),
            "invalid_funddatum": list(self.invalid_funddatum),
            "missing_image_files": [list(t) for t in self.missing_image_files],
            "is_clean": self.is_clean,
        }


def check_integrity(conn: sqlite3.Connection, root: Path | None = None,
                    check_files: bool = False) -> IntegrityReport:
    """Sammelt typische Inkonsistenzen.

    ``check_files=True`` und ``root`` gesetzt → prüft zusätzlich, ob die in
    ``images.rel_path`` referenzierten Dateien auf der Platte existieren.
    """
    rep = IntegrityReport()

    rep.orphan_images = [r[0] for r in conn.execute(
        "SELECT i.id FROM images i "
        "LEFT JOIN objects o ON o.obj_id = i.obj_id "
        "WHERE o.obj_id IS NULL ORDER BY i.id"
    ).fetchall()]

    rep.alias_to_missing = [r[0] for r in conn.execute(
        "SELECT a.alias_id FROM aliases a "
        "LEFT JOIN objects o ON o.obj_id = a.canonical_id "
        "WHERE o.obj_id IS NULL ORDER BY a.alias_id"
    ).fetchall()]

    rep.alias_id_collisions = [r[0] for r in conn.execute(
        "SELECT a.alias_id FROM aliases a "
        "JOIN objects o ON o.obj_id = a.alias_id ORDER BY a.alias_id"
    ).fetchall()]

    for row in conn.execute(
        "SELECT obj_id, Funddatum FROM objects "
        "WHERE Funddatum IS NOT NULL AND TRIM(Funddatum) != ''"
    ).fetchall():
        if parse_iso_date(row["Funddatum"]) is None:
            rep.invalid_funddatum.append(row["obj_id"])

    if check_files and root is not None:
        for row in conn.execute("SELECT id, rel_path FROM images").fetchall():
            full = root / row["rel_path"]
            if not full.is_file():
                rep.missing_image_files.append((row["id"], row["rel_path"]))

    return rep
