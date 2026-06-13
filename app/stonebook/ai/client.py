"""Analyse-Worker auf eigenem Thread — nutzt den konfigurierten Provider."""
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from stonebook.ai.image_prep import prepare_image
from stonebook.fields import CATEGORY_LABELS


class AnalysisWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, provider, root: Path, image_rows: list, object_data: dict, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.root = root
        self.image_rows = image_rows
        self.object_data = object_data

    def run(self):
        try:
            images = []
            for i, row in enumerate(self.image_rows, 1):
                label = CATEGORY_LABELS.get(row["kategorie"], row["kategorie"])
                b64, media_type = prepare_image(self.root / row["rel_path"])
                images.append((f"Bild {i}: {label} ({row['dateiname']})", b64, media_type))
            result = self.provider.analyse(images, self.object_data)
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))
