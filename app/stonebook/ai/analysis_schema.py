"""Tool-Use-Schema für die strukturierte KI-Analyse-Antwort."""
from stonebook.fields import DATA_FIELDS, NUMERIC_TYPES

# Felder, die die KI nicht befüllen soll (Pfade, Fundkontext)
EXCLUDED = {"Foto_Uebersicht", "Foto_UV395", "Foto_UV365", "Funddatum"}

AI_FIELDS = [f for f in DATA_FIELDS if f.name not in EXCLUDED]


def _wert_schema(fdef) -> dict:
    if fdef.ftype in NUMERIC_TYPES:
        return {"type": ["number", "null"]}
    return {"type": ["string", "null"]}


def build_tool() -> dict:
    properties = {}
    for fdef in AI_FIELDS:
        properties[fdef.name] = {
            "type": "object",
            "description": f"{fdef.label}: {fdef.description}",
            "properties": {
                "wert": _wert_schema(fdef),
                "confidence_prozent": {"type": "integer", "minimum": 0, "maximum": 100},
                "begruendung": {"type": "string"},
            },
            "required": ["wert", "confidence_prozent"],
        }
    properties["gesamt_confidence"] = {
        "type": "integer", "minimum": 0, "maximum": 100,
        "description": "Gesamt-Sicherheit der Bestimmung in Prozent",
    }
    properties["zusammenfassung"] = {
        "type": "string",
        "description": "Kurze Zusammenfassung der Bestimmung (2-4 Sätze, Deutsch)",
    }
    return {
        "name": "analyse_ergebnis",
        "description": "Strukturiertes Ergebnis der mineralogischen Analyse. "
                       "Felder ohne belastbare Aussage mit wert=null zurückgeben.",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": ["gesamt_confidence", "zusammenfassung"],
        },
    }


def field_definitions_text() -> str:
    lines = []
    for fdef in AI_FIELDS:
        extra = f" Mögliche Werte: {', '.join(v for v in fdef.enum_values if v)}." \
            if fdef.enum_values else ""
        lines.append(f"- {fdef.name} ({fdef.ftype}): {fdef.description}{extra}")
    return "\n".join(lines)
