"""Claude-API-Anbindung: Analyse-Worker auf eigenem Thread."""
import json
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from stonebook.ai.analysis_schema import build_tool, field_definitions_text
from stonebook.ai.image_prep import prepare_image
from stonebook.fields import CATEGORY_LABELS

SYSTEM_PROMPT = """Du bist ein erfahrener Mineraloge und bestimmst Gesteins- und \
Mineralproben anhand von Fotos (Tageslicht, Mikroskop/Makro, UV 365/395 nm) und \
vorhandenen Felddaten einer privaten Sammlung aus der Schweiz (v.a. Region St. Gallen, \
Geröll/Schotter-Funde).

Regeln:
- Antworte ausschließlich über das Tool analyse_ergebnis.
- Nur belegbare Aussagen treffen; bei Unsicherheit konservative Confidence-Werte vergeben.
- Felder ohne belastbare Grundlage: wert=null.
- Maße/Gewicht nur schätzen, wenn ein Maßstab erkennbar ist (kariertes Papier 5mm, Lineal); \
sonst null.
- Wertangaben (CHF/USD) sind grobe Schätzungen für Sammlerstücke dieser Art und Größe.
- Alle Texte auf Deutsch.

Felddefinitionen:
{felder}"""


class AnalysisWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, api_key: str, model: str, root: Path,
                 image_rows: list, object_data: dict, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model = model
        self.root = root
        self.image_rows = image_rows
        self.object_data = object_data

    def run(self):
        try:
            self.finished_ok.emit(self._analyse())
        except Exception as e:
            self.failed.emit(str(e))

    def _analyse(self) -> dict:
        import anthropic

        content = []
        for i, row in enumerate(self.image_rows, 1):
            label = CATEGORY_LABELS.get(row["kategorie"], row["kategorie"])
            content.append({"type": "text", "text": f"Bild {i}: {label} ({row['dateiname']})"})
            data, media_type = prepare_image(self.root / row["rel_path"])
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })

        known = {k: v for k, v in self.object_data.items()
                 if v is not None and str(v).strip()}
        content.append({
            "type": "text",
            "text": "Bereits erfasste Felddaten des Objekts (als Kontext, ggf. korrigieren):\n"
                    + json.dumps(known, ensure_ascii=False, indent=1)
                    + "\n\nBestimme das Objekt und fülle alle ableitbaren Felder über das Tool aus.",
        })

        client = anthropic.Anthropic(api_key=self.api_key)
        tool = build_tool()
        msg = client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=SYSTEM_PROMPT.format(felder=field_definitions_text()),
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": content}],
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == tool["name"]:
                return block.input
        raise RuntimeError("Keine strukturierte Antwort vom Modell erhalten.")
