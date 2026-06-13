"""Konsistenzprüfungen über die Objekt-DB (für Wartung/Diagnose)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from stonebook.migration.validators import parse_iso_date

# Wertbereiche pro Feld. Ungleich angegebene Felder werden nicht geprueft.
# Format: feldname -> (untergrenze | None, obergrenze | None)
NUMERIC_RANGES: dict[str, tuple[float | None, float | None]] = {
    "Mohs_Haerte_min": (0.0, 10.0),
    "Mohs_Haerte_max": (0.0, 10.0),
    "Dichte_min_gcm3": (0.0, 25.0),  # Iridium ~22.6 g/cm3 → realistische Obergrenze
    "Dichte_max_gcm3": (0.0, 25.0),
    "Laenge_mm": (0.0, None),
    "Breite_mm": (0.0, None),
    "Hoehe_mm": (0.0, None),
    "Gewicht_g": (0.0, None),
    "Wert_CHF_roh": (0.0, None),
    "Wert_CHF_poliert": (0.0, None),
    "Wert_CHF_Schmuck": (0.0, None),
    "Wert_USD_Talisman": (0.0, None),
    "Marktwert_Industrie": (0.0, None),
    "Wissenschaftlicher_Wert_CHF": (0.0, None),
    "Seltenheit_global_1_10": (1.0, 10.0),
    "Seltenheit_Fundort_1_10": (1.0, 10.0),
    "Nachfrage_1_10": (1.0, 10.0),
    "Confidence_Prozent": (0.0, 100.0),
}

# (min-Feld, max-Feld) Paare, bei denen min <= max gelten muss
RANGE_PAIRS: tuple[tuple[str, str], ...] = (
    ("Mohs_Haerte_min", "Mohs_Haerte_max"),
    ("Dichte_min_gcm3", "Dichte_max_gcm3"),
)


@dataclass
class IntegrityReport:
    orphan_images: list[int] = field(default_factory=list)          # image.id
    alias_to_missing: list[str] = field(default_factory=list)       # alias_id
    alias_id_collisions: list[str] = field(default_factory=list)    # alias_id existiert auch als Objekt
    invalid_funddatum: list[str] = field(default_factory=list)      # obj_id
    missing_image_files: list[tuple[int, str]] = field(default_factory=list)  # (id, rel_path)
    numeric_out_of_range: list[tuple[str, str, float]] = field(default_factory=list)
    range_inverted: list[tuple[str, str]] = field(default_factory=list)  # (obj_id, feldpaar)

    @property
    def is_clean(self) -> bool:
        return not (self.orphan_images or self.alias_to_missing
                    or self.alias_id_collisions or self.invalid_funddatum
                    or self.missing_image_files or self.numeric_out_of_range
                    or self.range_inverted)

    def as_dict(self) -> dict:
        return {
            "orphan_images": list(self.orphan_images),
            "alias_to_missing": list(self.alias_to_missing),
            "alias_id_collisions": list(self.alias_id_collisions),
            "invalid_funddatum": list(self.invalid_funddatum),
            "missing_image_files": [list(t) for t in self.missing_image_files],
            "numeric_out_of_range": [list(t) for t in self.numeric_out_of_range],
            "range_inverted": [list(t) for t in self.range_inverted],
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

    cols = ", ".join(NUMERIC_RANGES)
    for row in conn.execute(f"SELECT obj_id, {cols} FROM objects").fetchall():
        for field_name, (lo, hi) in NUMERIC_RANGES.items():
            v = row[field_name]
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if (lo is not None and fv < lo) or (hi is not None and fv > hi):
                rep.numeric_out_of_range.append((row["obj_id"], field_name, fv))

    pair_cols = {c for pair in RANGE_PAIRS for c in pair}
    cols2 = ", ".join(pair_cols)
    for row in conn.execute(f"SELECT obj_id, {cols2} FROM objects").fetchall():
        for lo_field, hi_field in RANGE_PAIRS:
            lo, hi = row[lo_field], row[hi_field]
            if lo is None or hi is None:
                continue
            if float(lo) > float(hi):
                rep.range_inverted.append((row["obj_id"], f"{lo_field}>{hi_field}"))

    if check_files and root is not None:
        for row in conn.execute("SELECT id, rel_path FROM images").fetchall():
            full = root / row["rel_path"]
            if not full.is_file():
                rep.missing_image_files.append((row["id"], row["rel_path"]))

    return rep
