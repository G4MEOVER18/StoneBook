"""Datenbank-Neuaufbau aus den Repo-Quellen (idempotent: DB wird neu erstellt).

CLI:  python -m stonebook.migration.migrate [repo_root]
"""
import csv
import json
import sys
from pathlib import Path

from stonebook.db.database import open_db
from stonebook.db.repository import AliasRepo, ImageRepo, ObjectRepo
from stonebook.fields import is_empty
from stonebook.migration import csv_loaders
from stonebook.migration.id_utils import normalize_id
from stonebook.migration.image_indexer import index_images

DUPLIKAT_JSON = Path(__file__).resolve().parent / "duplikat_gruppen.json"

CSV_V1 = "Stonebock__stoneboock_daten_objekte_1-42.csv"
CSV_V2 = "Stonebock__stoneboock_daten_v2_objekte_1-42.csv"
CSV_043 = "Stonebock__StoneBoock_Objekt_043_FULL__StoneBoock_Objekt_043.csv"
OBJECT_INDEX = "object_index.csv"


def migrate(root: Path, db_file: Path, log=print) -> dict:
    """Baut die DB komplett neu auf. Gibt Kennzahlen-Dict zurück."""
    if db_file.exists():
        db_file.unlink()
    conn = open_db(db_file)
    objects = ObjectRepo(conn)
    images = ImageRepo(conn)
    aliases = AliasRepo(conn)
    csv_dir = root / "data" / "csv"

    # 1. Skelett aus object_index.csv
    log("1/5 Objekt-Skelett aus object_index.csv …")
    index_file = csv_dir / OBJECT_INDEX
    with index_file.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            obj_id = normalize_id(row.get("obj_id"))
            if obj_id and not objects.exists(obj_id):
                objects.create(obj_id, folder_path=f"objects/{obj_id}")
    log(f"   {objects.count()} Objekte angelegt")

    # 2. CSV-Schichten (spätere Schicht überschreibt nur nicht-leere Werte nicht-leerer Quellen)
    log("2/5 CSV-Daten einspielen (v1 → v2 → Objekt-043) …")
    layers = [
        ("v1", csv_dir / CSV_V1, csv_loaders.load_v1),
        ("v2", csv_dir / CSV_V2, csv_loaders.load_v2),
        ("043", csv_dir / CSV_043, csv_loaders.load_obj043),
    ]
    parse_errors = 0
    for name, path, loader in layers:
        if not path.is_file():
            log(f"   Schicht {name}: Datei fehlt ({path.name}) — übersprungen")
            continue
        try:
            data = loader(path)
        except Exception as e:
            log(f"   [FEHLER] Schicht {name}: {e}")
            parse_errors += 1
            continue
        applied = 0
        for obj_id, fields in data.items():
            if not objects.exists(obj_id):
                objects.create(obj_id, folder_path=f"objects/{obj_id}")
            # Schichtprinzip: spätere (verlässlichere) Quelle überschreibt
            clean = {k: v for k, v in fields.items() if not is_empty(v)}
            objects.update_fields(obj_id, clean)
            applied += 1
        log(f"   Schicht {name}: {applied} Objekte aktualisiert")

    # 3. Duplikat-Merge
    log("3/5 Duplikat-Merge …")
    groups = json.loads(DUPLIKAT_JSON.read_text(encoding="utf-8"))["gruppen"]
    alias_map: dict[str, str] = {}
    conflicts_total = 0
    for grp in groups:
        canonical = normalize_id(grp["canonical"])
        for member in grp["members"]:
            member_id = normalize_id(member)
            if member_id == canonical:
                continue
            alias_map[member_id] = canonical
            row = objects.get(member_id)
            if row is not None:
                fields = {k: row[k] for k in row.keys()
                          if k not in ("obj_id", "status", "folder_path",
                                       "erstellt_am", "geaendert_am")}
                conflicts = objects.merge_nonempty(canonical, fields)
                if conflicts:
                    conflicts_total += len(conflicts)
                    log(f"   Konflikt {member_id} → {canonical}: {', '.join(conflicts)} (Kanon behalten)")
                objects.delete(member_id)
            aliases.add(member_id, canonical, "duplikat_gruppen.json")
    log(f"   {len(groups)} Gruppen, {aliases.count()} Aliase, {conflicts_total} Feldkonflikte")

    # 4. Bild-Indexierung
    log("4/5 Bilder indexieren …")
    known_ids = {r["obj_id"] for r in objects.list_objects()}
    img_count = index_images(root, images, known_ids, alias_map, log)
    log(f"   {img_count} Bilder indexiert")

    # 5. Status aktualisieren
    log("5/5 Objektstatus berechnen …")
    for obj_id in sorted(known_ids):
        objects.refresh_status(obj_id)
    aktiv = len(objects.list_objects(status="aktiv"))

    report = {
        "objekte": objects.count(),
        "aktiv": aktiv,
        "platzhalter": objects.count() - aktiv,
        "aliase": aliases.count(),
        "bilder": images.count(),
        "konflikte": conflicts_total,
        "parse_fehler": parse_errors,
    }
    log(f"Fertig: {report['objekte']} Objekte ({report['aktiv']} aktiv), "
        f"{report['aliase']} Aliase, {report['bilder']} Bilder")
    conn.close()
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    else:
        root = Path(__file__).resolve().parents[3]
    if not (root / "objects").is_dir():
        print(f"Kein StoneBook-Repo unter: {root}")
        return 1
    db_file = root / "data" / "db" / "stonebook.sqlite3"
    migrate(root, db_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
