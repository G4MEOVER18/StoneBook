"""Berichte-Tab: vorhandene DOCX im Objektordner + Bericht erzeugen."""
import os
from pathlib import Path

from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)


class ReportsWidget(QWidget):
    def __init__(self, conn, root: Path, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.root = root
        self.obj_id: str | None = None

        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(
            lambda item: os.startfile(str(self._obj_dir() / item.text())))
        lay.addWidget(self.list, 1)

        btns = QHBoxLayout()
        gen = QPushButton("Bericht (DOCX) erzeugen")
        gen.clicked.connect(self._generate)
        btns.addWidget(gen)
        btns.addStretch()
        lay.addLayout(btns)

    def _obj_dir(self) -> Path:
        return self.root / "objects" / (self.obj_id or "")

    def load_object(self, obj_id: str) -> None:
        self.obj_id = obj_id
        self.list.clear()
        obj_dir = self._obj_dir()
        if obj_dir.is_dir():
            for f in sorted(obj_dir.glob("*.docx")):
                self.list.addItem(f.name)

    def _generate(self):
        if not self.obj_id:
            return
        from stonebook.export.docx_export import export_docx
        try:
            out = export_docx(self.conn, self.root, self.obj_id)
        except Exception as e:
            QMessageBox.critical(self, "StoneBook", f"Bericht fehlgeschlagen:\n{e}")
            return
        self.load_object(self.obj_id)
        res = QMessageBox.question(
            self, "StoneBook", f"Bericht erzeugt:\n{out.name}\n\nJetzt öffnen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            os.startfile(str(out))
