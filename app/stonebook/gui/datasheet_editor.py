"""Datenblatt-Formular: alle Standardfelder, gruppiert, mit Dirty-Tracking."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from stonebook.db.repository import AliasRepo, ObjectRepo
from stonebook.fields import DATA_FIELDS, FIELD_GROUPS, FieldDef, G_SONST
from stonebook.gui.widgets import FieldEditor
from stonebook.migration.id_utils import display_name

NOTIZEN_FIELD = FieldDef("notizen", "Notizen", "text", G_SONST, "Freie Notizen zum Objekt")


class DatasheetEditor(QWidget):
    saved = Signal(str)

    def __init__(self, objects: ObjectRepo, aliases: AliasRepo, parent=None):
        super().__init__(parent)
        self.objects = objects
        self.aliases = aliases
        self.obj_id: str | None = None
        self._dirty = False

        outer = QVBoxLayout(self)

        self.header = QLabel("")
        self.header.setStyleSheet("font-size: 16px; font-weight: bold;")
        outer.addWidget(self.header)

        self.alias_banner = QLabel("")
        self.alias_banner.setStyleSheet(
            "background: #fff3cd; color: #664d03; padding: 6px; border-radius: 4px;")
        self.alias_banner.setVisible(False)
        outer.addWidget(self.alias_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)

        self.editors: dict[str, FieldEditor] = {}
        all_fields = [f for f in DATA_FIELDS] + [NOTIZEN_FIELD]
        for group in FIELD_GROUPS:
            group_fields = [f for f in all_fields if f.group == group]
            if not group_fields:
                continue
            box = QGroupBox(group)
            form = QFormLayout(box)
            for fdef in group_fields:
                ed = FieldEditor(fdef)
                ed.changed.connect(self._mark_dirty)
                self.editors[fdef.name] = ed
                form.addRow(fdef.label + ":", ed)
            inner_lay.addWidget(box)
        inner_lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        self.save_btn = QPushButton("Speichern (Ctrl+S)")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        outer.addWidget(self.save_btn, 0, Qt.AlignmentFlag.AlignRight)

        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)

    def _mark_dirty(self):
        if self.obj_id:
            self._dirty = True
            self.save_btn.setEnabled(True)

    def is_dirty(self) -> bool:
        return self._dirty

    def load_object(self, obj_id: str) -> None:
        row = self.objects.get(obj_id)
        if row is None:
            return
        self.obj_id = obj_id
        self.header.setText(f"{display_name(obj_id)}  ({obj_id})")
        alias_list = self.aliases.aliases_for(obj_id)
        if alias_list:
            nums = ", ".join(str(int(a.split("_")[1])) for a in alias_list)
            self.alias_banner.setText(
                f"Enthält gemergte Objekte: {nums} (gleicher Stein, andere Fotos)")
            self.alias_banner.setVisible(True)
        else:
            self.alias_banner.setVisible(False)
        for name, ed in self.editors.items():
            ed.set_value(row[name])
        self._dirty = False
        self.save_btn.setEnabled(False)

    def save(self) -> None:
        if not self.obj_id or not self._dirty:
            return
        fields = {name: ed.value() for name, ed in self.editors.items()}
        self.objects.update_fields(self.obj_id, fields)
        self.objects.refresh_status(self.obj_id)
        self._dirty = False
        self.save_btn.setEnabled(False)
        self.saved.emit(self.obj_id)

    def apply_values(self, values: dict) -> None:
        """Setzt Werte (z.B. KI-Vorschläge) ins Formular, ohne zu speichern."""
        for name, val in values.items():
            if name in self.editors:
                self.editors[name].set_value(val)
        self._mark_dirty()
