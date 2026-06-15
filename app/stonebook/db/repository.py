"""CRUD-Schicht über der SQLite-DB."""
import datetime
import sqlite3

from stonebook.fields import DATA_FIELDS, is_empty

DATA_COLS = [f.name for f in DATA_FIELDS]

VALID_STATUSES: frozenset[str] = frozenset({"aktiv", "platzhalter", "archiviert"})

# Whitelist für Sortierung in list_objects (verhindert SQL-Injection bei freier Spalte).
SORTABLE_COLUMNS: frozenset[str] = frozenset({
    "obj_id", "Name", "Mineral_Primaer", "Fundort", "status",
    "Confidence_Prozent", "Funddatum", "Gewicht_g",
    "erstellt_am", "geaendert_am",
    "bilder", "gesamtwert_chf",
})

# Berechnete Aliase im SELECT (kein o.-Prefix beim ORDER BY).
_COMPUTED_COLUMNS: frozenset[str] = frozenset({"bilder", "gesamtwert_chf"})


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fts_query(text: str) -> str:
    tokens = [t.replace('"', "") for t in text.split() if t.strip()]
    return " ".join(f'"{t}"*' for t in tokens)


def _like_escape(text: str) -> str:
    """Escapt SQL-LIKE-Metazeichen (``%``/``_``/``\\``) im Nutzereingabe-Pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _order_by_clause(sort_by: str | None, sort_desc: bool) -> str:
    if not sort_by:
        return " ORDER BY o.obj_id"
    if sort_by not in SORTABLE_COLUMNS:
        raise ValueError(f"Unzulaessige Sortierspalte: {sort_by}")
    direction = "DESC" if sort_desc else "ASC"
    # Berechnete Aliase (z.B. 'bilder', 'gesamtwert_chf') stehen ohne o.-Prefix.
    prefix = "" if sort_by in _COMPUTED_COLUMNS else "o."
    # NULLs hinten + stabile Zweitsortierung nach ID
    return (f" ORDER BY ({prefix}{sort_by} IS NULL), "
            f"{prefix}{sort_by} {direction}, o.obj_id")


class ObjectRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_objects(self, search: str = "", status: str = "", mineral: str = "",
                     kategorie: str = "", only_images: bool = False,
                     has_bilder: bool | None = None,
                     min_confidence: int | None = None,
                     max_confidence: int | None = None,
                     has_confidence: bool | None = None,
                     has_funddatum: bool | None = None,
                     has_mineral: bool | None = None,
                     has_notizen: bool | None = None,
                     funddatum_jahr_min: int | None = None,
                     funddatum_jahr_max: int | None = None,
                     funddatum_min: str | None = None,
                     funddatum_max: str | None = None,
                     fundort: str = "",
                     fundort_contains: str = "",
                     wert_min: float | None = None,
                     wert_max: float | None = None,
                     gewicht_min: float | None = None,
                     gewicht_max: float | None = None,
                     kristallsystem: str = "",
                     beste_verwendung: str = "",
                     varietaet: str = "",
                     gesteinsart: str = "",
                     sort_by: str | None = None,
                     sort_desc: bool = False) -> list[sqlite3.Row]:
        from stonebook.db.stats import wert_pro_objekt_sql
        wert_sql = wert_pro_objekt_sql()
        sql = f"""
            SELECT o.obj_id, o.Name, o.Mineral_Primaer, o.Fundort, o.status,
                   o.Confidence_Prozent, o.Funddatum,
                   (SELECT COUNT(*) FROM images i WHERE i.obj_id = o.obj_id) AS bilder,
                   {wert_sql} AS gesamtwert_chf
            FROM objects o
        """
        where, params = [], []
        if search.strip():
            where.append("o.rowid IN (SELECT rowid FROM objects_fts WHERE objects_fts MATCH ?)")
            params.append(_fts_query(search))
        if status:
            where.append("o.status = ?")
            params.append(status)
        if mineral:
            where.append("o.Mineral_Primaer = ?")
            params.append(mineral)
        if kategorie:
            where.append("o.Kategorie = ?")
            params.append(kategorie)
        # has_bilder ist die kanonische Form (True/False/None); only_images bleibt
        # als Legacy-Alias erhalten und mappt auf has_bilder=True, falls dieses
        # noch nicht gesetzt ist (kein Konflikt zwischen den beiden Flags).
        effective_has_bilder = has_bilder if has_bilder is not None else (
            True if only_images else None)
        if effective_has_bilder is True:
            where.append("EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id)")
        elif effective_has_bilder is False:
            where.append("NOT EXISTS (SELECT 1 FROM images i WHERE i.obj_id = o.obj_id)")
        if min_confidence is not None:
            where.append("o.Confidence_Prozent >= ?")
            params.append(int(min_confidence))
        if max_confidence is not None:
            where.append("o.Confidence_Prozent <= ?")
            params.append(int(max_confidence))
        if has_confidence is True:
            where.append("o.Confidence_Prozent IS NOT NULL")
        elif has_confidence is False:
            where.append("o.Confidence_Prozent IS NULL")
        if has_funddatum is True:
            where.append("o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != ''")
        elif has_funddatum is False:
            where.append("(o.Funddatum IS NULL OR TRIM(o.Funddatum) = '')")
        if has_mineral is True:
            where.append("o.Mineral_Primaer IS NOT NULL AND TRIM(o.Mineral_Primaer) != ''")
        elif has_mineral is False:
            where.append("(o.Mineral_Primaer IS NULL OR TRIM(o.Mineral_Primaer) = '')")
        if has_notizen is True:
            where.append("o.notizen IS NOT NULL AND TRIM(o.notizen) != ''")
        elif has_notizen is False:
            where.append("(o.notizen IS NULL OR TRIM(o.notizen) = '')")
        if funddatum_jahr_min is not None or funddatum_jahr_max is not None:
            where.append("substr(o.Funddatum, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'")
            if funddatum_jahr_min is not None:
                where.append("CAST(substr(o.Funddatum, 1, 4) AS INTEGER) >= ?")
                params.append(int(funddatum_jahr_min))
            if funddatum_jahr_max is not None:
                where.append("CAST(substr(o.Funddatum, 1, 4) AS INTEGER) <= ?")
                params.append(int(funddatum_jahr_max))
        # Funddatum-Bereich auf Tagesgenauigkeit: ISO YYYY-MM-DD lexikographisch
        # vergleichbar. Akzeptiert auch YYYY-MM oder YYYY allein.
        if funddatum_min is not None:
            where.append("o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != '' "
                         "AND o.Funddatum >= ?")
            params.append(str(funddatum_min))
        if funddatum_max is not None:
            where.append("o.Funddatum IS NOT NULL AND TRIM(o.Funddatum) != '' "
                         "AND o.Funddatum <= ?")
            params.append(str(funddatum_max))
        if fundort:
            where.append("o.Fundort = ?")
            params.append(fundort)
        if fundort_contains:
            # Substring-Filter fuer Sammel-Regionen ("St. Gallen, Sitter" + "St. Gallen, Bahnhof").
            # LIKE ist case-insensitive fuer ASCII; fuer Umlaute reicht das in der CH-Praxis aus.
            where.append("o.Fundort LIKE ? ESCAPE '\\'")
            params.append("%" + _like_escape(fundort_contains) + "%")
        if wert_min is not None:
            where.append(f"{wert_sql} >= ?")
            params.append(float(wert_min))
        if wert_max is not None:
            where.append(f"{wert_sql} <= ?")
            params.append(float(wert_max))
        if gewicht_min is not None:
            where.append("o.Gewicht_g >= ?")
            params.append(float(gewicht_min))
        if gewicht_max is not None:
            where.append("o.Gewicht_g <= ?")
            params.append(float(gewicht_max))
        if kristallsystem:
            where.append("o.Kristallsystem = ?")
            params.append(kristallsystem)
        if beste_verwendung:
            where.append("o.Beste_Verwendung = ?")
            params.append(beste_verwendung)
        if varietaet:
            where.append("o.Varietaet = ?")
            params.append(varietaet)
        if gesteinsart:
            where.append("o.Gesteinsart = ?")
            params.append(gesteinsart)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += _order_by_clause(sort_by, sort_desc)
        return self.conn.execute(sql, params).fetchall()

    def get(self, obj_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM objects WHERE obj_id = ?", (obj_id,)).fetchone()

    def exists(self, obj_id: str) -> bool:
        return self.get(obj_id) is not None

    def create(self, obj_id: str, **fields) -> None:
        cols = ["obj_id", "erstellt_am", "geaendert_am"]
        vals = [obj_id, _now(), _now()]
        for k, v in fields.items():
            cols.append(k)
            vals.append(v)
        sql = f"INSERT INTO objects ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        self.conn.execute(sql, vals)
        self.conn.commit()

    def update_fields(self, obj_id: str, fields: dict) -> None:
        if not fields:
            return
        fields = dict(fields)
        fields["geaendert_am"] = _now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE objects SET {sets} WHERE obj_id = ?",
                          [*fields.values(), obj_id])
        self.conn.commit()

    def merge_nonempty(self, obj_id: str, fields: dict) -> list[str]:
        """Setzt nur nicht-leere Werte; gibt Liste der Konfliktfelder zurück (vorhandener Wert != neuer Wert)."""
        current = self.get(obj_id)
        if current is None:
            return []
        conflicts, updates = [], {}
        for k, v in fields.items():
            if is_empty(v):
                continue
            old = current[k]
            if not is_empty(old) and str(old) != str(v):
                conflicts.append(k)
                continue
            updates[k] = v
        if updates:
            self.update_fields(obj_id, updates)
        return conflicts

    def delete(self, obj_id: str) -> None:
        self.conn.execute("DELETE FROM objects WHERE obj_id = ?", (obj_id,))
        self.conn.commit()

    def set_status(self, obj_id: str, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Ungueltiger Status: {status!r} "
                f"(erwartet einen aus {sorted(VALID_STATUSES)})")
        self.update_fields(obj_id, {"status": status})

    def archive(self, obj_id: str) -> None:
        """Markiert ein Objekt als ``archiviert`` (refresh_status laesst es danach in Ruhe)."""
        self.set_status(obj_id, "archiviert")

    def unarchive(self, obj_id: str) -> None:
        """Hebt eine Archivierung auf; Folgestatus (aktiv/platzhalter) wird automatisch bestimmt."""
        row = self.get(obj_id)
        if row is None:
            return
        if row["status"] == "archiviert":
            # Auf platzhalter zuruecksetzen, damit refresh_status den passenden Status berechnet
            self.conn.execute(
                "UPDATE objects SET status = 'platzhalter' WHERE obj_id = ?", (obj_id,))
            self.conn.commit()
            self.refresh_status(obj_id)

    def refresh_status(self, obj_id: str) -> None:
        """platzhalter → aktiv, sobald Felddaten oder Bilder vorhanden sind."""
        row = self.get(obj_id)
        if row is None or row["status"] == "archiviert":
            return
        has_data = any(not is_empty(row[c]) for c in DATA_COLS)
        has_images = self.conn.execute(
            "SELECT 1 FROM images WHERE obj_id = ? LIMIT 1", (obj_id,)).fetchone() is not None
        status = "aktiv" if (has_data or has_images) else "platzhalter"
        if status != row["status"]:
            self.conn.execute("UPDATE objects SET status = ? WHERE obj_id = ?", (status, obj_id))
            self.conn.commit()

    def refresh_status_all(self) -> int:
        """Setzt status fuer alle nicht-archivierten Objekte in einem SQL-Statement.

        Aequivalent zu :meth:`refresh_status` ueber alle Objekte, aber O(1)
        Roundtrips statt O(N). Liefert die Anzahl tatsaechlich geaenderter
        Zeilen. ``archiviert`` bleibt erhalten.
        """
        data_check = " OR ".join(
            f"(TRIM(COALESCE({c}, '')) != '')" for c in DATA_COLS
        )
        # Ziel-Status berechnen; nur schreiben, wenn er sich aendert (sonst
        # erzeugt das UPDATE unnoetige FTS-Trigger-Aktivitaet).
        sql = (
            "UPDATE objects SET status = CASE "
            f"WHEN ({data_check}) OR EXISTS("
            "  SELECT 1 FROM images i WHERE i.obj_id = objects.obj_id"
            ") THEN 'aktiv' ELSE 'platzhalter' END "
            "WHERE status != 'archiviert' "
            f"  AND status != CASE WHEN ({data_check}) OR EXISTS("
            "    SELECT 1 FROM images i WHERE i.obj_id = objects.obj_id"
            "  ) THEN 'aktiv' ELSE 'platzhalter' END"
        )
        cur = self.conn.execute(sql)
        self.conn.commit()
        return cur.rowcount

    def next_free_id(self) -> str:
        rows = self.conn.execute(
            "SELECT obj_id FROM objects UNION SELECT alias_id FROM aliases").fetchall()
        max_n = 0
        for r in rows:
            try:
                max_n = max(max_n, int(str(r[0]).split("_")[1]))
            except (IndexError, ValueError):
                pass
        return f"OBJ_{max_n + 1:04d}"

    def distinct_values(self, column: str) -> list[str]:
        if column not in DATA_COLS:
            raise ValueError(f"Unbekannte Spalte: {column}")
        rows = self.conn.execute(
            f"SELECT DISTINCT {column} FROM objects "
            f"WHERE {column} IS NOT NULL AND TRIM({column}) != '' ORDER BY {column}").fetchall()
        return [r[0] for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]

    def statistics(self) -> dict:
        """Legacy-Adapter mit fixierter Dict-Form fuer das Dashboard.

        Delegiert an :func:`stonebook.db.stats.compute_statistics`; behaelt die
        bisherigen Schluessel bei (gesamt/status/top_minerals/mit_bildern/...).
        """
        from stonebook.db.stats import compute_statistics

        st = compute_statistics(self.conn, top_fundorte=0, top_wert=0)
        avg = st.durchschnitt_confidence_prozent
        return {
            "gesamt": st.objekte_total,
            "status": dict(st.by_status),
            "top_minerals": list(st.by_mineral.items())[:10],
            "mit_bildern": st.objekte_mit_bildern,
            "bilder_gesamt": st.bilder_total,
            "aliase": st.aliase_total,
            "wert_roh_chf": round(st.wert_roh_summe_chf, 2),
            "durchschnitt_confidence": round(avg, 1) if avg is not None else None,
        }


class ImageRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, obj_id: str, kategorie: str, rel_path: str, dateiname: str = "",
            sha256: str = "", exif_datum: str = "", breite_px: int | None = None,
            hoehe_px: int | None = None, herkunft_obj_id: str = "") -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO images
               (obj_id, kategorie, rel_path, dateiname, sha256, exif_datum,
                breite_px, hoehe_px, herkunft_obj_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (obj_id, kategorie, rel_path, dateiname, sha256, exif_datum,
             breite_px, hoehe_px, herkunft_obj_id))
        self.conn.commit()

    def for_object(self, obj_id: str, kategorie: str = "") -> list[sqlite3.Row]:
        sql = "SELECT * FROM images WHERE obj_id = ?"
        params: list = [obj_id]
        if kategorie:
            sql += " AND kategorie = ?"
            params.append(kategorie)
        sql += " ORDER BY kategorie, dateiname"
        return self.conn.execute(sql, params).fetchall()

    def reassign(self, from_obj: str, to_obj: str) -> None:
        self.conn.execute(
            "UPDATE images SET obj_id = ?, herkunft_obj_id = ? WHERE obj_id = ?",
            (to_obj, from_obj, from_obj))
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]


class AliasRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, alias_id: str, canonical_id: str, quelle: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO aliases (alias_id, canonical_id, merge_quelle) VALUES (?,?,?)",
            (alias_id, canonical_id, quelle))
        self.conn.commit()

    def canonical_for(self, alias_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT canonical_id FROM aliases WHERE alias_id = ?", (alias_id,)).fetchone()
        return row[0] if row else None

    def aliases_for(self, canonical_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT alias_id FROM aliases WHERE canonical_id = ? ORDER BY alias_id",
            (canonical_id,)).fetchall()
        return [r[0] for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]


class AnalysisRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, obj_id: str, modell: str, antwort_json: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO ki_analysen (obj_id, zeitpunkt, modell, antwort_json) VALUES (?,?,?,?)",
            (obj_id, _now(), modell, antwort_json))
        self.conn.commit()
        return cur.lastrowid

    def set_uebernommen(self, analysis_id: int, uebernommen_json: str) -> None:
        self.conn.execute("UPDATE ki_analysen SET uebernommen_json = ? WHERE id = ?",
                          (uebernommen_json, analysis_id))
        self.conn.commit()

    def for_object(self, obj_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM ki_analysen WHERE obj_id = ? "
            "ORDER BY zeitpunkt DESC, id DESC",
            (obj_id,)).fetchall()

    def get(self, analysis_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM ki_analysen WHERE id = ?", (analysis_id,)).fetchone()

    def delete(self, analysis_id: int) -> bool:
        """Loescht eine einzelne KI-Analyse; gibt True zurueck, wenn etwas geloescht wurde."""
        cur = self.conn.execute("DELETE FROM ki_analysen WHERE id = ?", (analysis_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def prune(self, obj_id: str, keep: int) -> int:
        """Behaelt nur die ``keep`` neuesten Analysen je Objekt; loescht aeltere.

        ``keep < 0`` wirft ``ValueError``; ``keep == 0`` loescht alle Analysen
        des Objekts. Gibt die Zahl tatsaechlich geloeschter Zeilen zurueck.
        """
        if keep < 0:
            raise ValueError("keep muss >= 0 sein")
        cur = self.conn.execute(
            "DELETE FROM ki_analysen WHERE obj_id = ? AND id NOT IN ("
            " SELECT id FROM ki_analysen WHERE obj_id = ?"
            " ORDER BY zeitpunkt DESC, id DESC LIMIT ?)",
            (obj_id, obj_id, keep))
        self.conn.commit()
        return cur.rowcount

    def count_for(self, obj_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM ki_analysen WHERE obj_id = ?", (obj_id,)).fetchone()[0]
