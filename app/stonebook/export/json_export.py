"""JSON-Vollexport: objects + images + aliases (Backup/Re-Import)."""
import json
from pathlib import Path


def export_json(conn, path: Path) -> dict:
    def rows(table: str) -> list[dict]:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]

    data = {
        "objects": rows("objects"),
        "images": rows("images"),
        "aliases": rows("aliases"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {k: len(v) for k, v in data.items()}
