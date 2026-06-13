"""Objektdetail: Tabs für Datenblatt, Galerie, KI-Analyse, Berichte."""
from pathlib import Path

from PySide6.QtWidgets import QTabWidget

from stonebook.db.repository import AliasRepo, AnalysisRepo, ImageRepo, ObjectRepo
from stonebook.gui.ai_dialog import AIPanel
from stonebook.gui.datasheet_editor import DatasheetEditor
from stonebook.gui.gallery import GalleryWidget
from stonebook.gui.reports import ReportsWidget


class ObjectDetail(QTabWidget):
    def __init__(self, conn, root: Path, parent=None):
        super().__init__(parent)
        self.root = root
        self.objects = ObjectRepo(conn)
        self.images = ImageRepo(conn)
        self.aliases = AliasRepo(conn)
        self.analyses = AnalysisRepo(conn)
        self.obj_id: str | None = None

        self.datasheet = DatasheetEditor(self.objects, self.aliases)
        self.addTab(self.datasheet, "Datenblatt")
        self.gallery = GalleryWidget(self.objects, self.images, root)
        self.addTab(self.gallery, "Galerie")
        self.ai_panel = AIPanel(self.objects, self.images, self.analyses, root)
        self.ai_panel.applyRequested.connect(self.datasheet.apply_values)
        self.addTab(self.ai_panel, "KI-Analyse")
        self.reports = ReportsWidget(conn, root)
        self.addTab(self.reports, "Berichte")

    def load_object(self, obj_id: str) -> None:
        self.obj_id = obj_id
        self.datasheet.load_object(obj_id)
        self.gallery.load_object(obj_id)
        self.ai_panel.load_object(obj_id)
        self.reports.load_object(obj_id)
