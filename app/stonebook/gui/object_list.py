"""Objektliste mit FTS-Suche, Filtern und Tabelle."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QHeaderView,
                               QLineEdit, QMenu, QTableView, QVBoxLayout, QWidget)

from stonebook.db.repository import ObjectRepo

COLUMNS = [
    ("obj_id", "ID"),
    ("Name", "Name"),
    ("Mineral_Primaer", "Mineral"),
    ("Fundort", "Fundort"),
    ("bilder", "Bilder"),
    ("status", "Status"),
    ("Confidence_Prozent", "Conf. %"),
]


class ObjectTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows: list = []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        value = self.rows[index.row()][COLUMNS[index.column()][0]]
        return "" if value is None else str(value)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][1]
        return None

    def obj_id_at(self, row: int) -> str | None:
        if 0 <= row < len(self.rows):
            return self.rows[row]["obj_id"]
        return None


class ObjectListWidget(QWidget):
    objectSelected = Signal(str)
    openFolderRequested = Signal(str)
    archiveRequested = Signal(str)

    def __init__(self, objects: ObjectRepo, parent=None):
        super().__init__(parent)
        self.objects = objects

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Suche (Name, Mineral, Fundort, Notizen) …")
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)

        filt = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Alle Status", "aktiv", "platzhalter", "archiviert"])
        self.status_filter.currentIndexChanged.connect(self.refresh)
        filt.addWidget(self.status_filter)

        self.mineral_filter = QComboBox()
        self.mineral_filter.addItem("Alle Minerale")
        self.mineral_filter.currentIndexChanged.connect(self.refresh)
        filt.addWidget(self.mineral_filter)

        self.images_only = QCheckBox("nur mit Bildern")
        self.images_only.stateChanged.connect(self.refresh)
        filt.addWidget(self.images_only)
        lay.addLayout(filt)

        self.model = ObjectTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().currentRowChanged.connect(self._row_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        lay.addWidget(self.table, 1)

        self.refresh_minerals()
        self.refresh()

    def refresh_minerals(self):
        current = self.mineral_filter.currentText()
        self.mineral_filter.blockSignals(True)
        self.mineral_filter.clear()
        self.mineral_filter.addItem("Alle Minerale")
        self.mineral_filter.addItems(self.objects.distinct_values("Mineral_Primaer"))
        idx = self.mineral_filter.findText(current)
        if idx >= 0:
            self.mineral_filter.setCurrentIndex(idx)
        self.mineral_filter.blockSignals(False)

    def refresh(self):
        status = self.status_filter.currentText()
        mineral = self.mineral_filter.currentText()
        rows = self.objects.list_objects(
            search=self.search.text(),
            status="" if status.startswith("Alle") else status,
            mineral="" if mineral.startswith("Alle") else mineral,
            only_images=self.images_only.isChecked(),
        )
        self.model.set_rows(rows)

    def _row_changed(self, current: QModelIndex, _previous: QModelIndex):
        obj_id = self.model.obj_id_at(current.row())
        if obj_id:
            self.objectSelected.emit(obj_id)

    def selected_obj_id(self) -> str | None:
        idx = self.table.currentIndex()
        return self.model.obj_id_at(idx.row()) if idx.isValid() else None

    def _context_menu(self, pos):
        obj_id = self.selected_obj_id()
        if not obj_id:
            return
        menu = QMenu(self)
        act_open = menu.addAction("Ordner im Explorer öffnen")
        act_archive = menu.addAction("Archivieren")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_open:
            self.openFolderRequested.emit(obj_id)
        elif chosen == act_archive:
            self.archiveRequested.emit(obj_id)

    def select_object(self, obj_id: str) -> None:
        for i, row in enumerate(self.model.rows):
            if row["obj_id"] == obj_id:
                self.table.selectRow(i)
                return
