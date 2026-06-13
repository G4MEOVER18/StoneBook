"""KI-Analyse-Tab: Bildauswahl, Analyse-Lauf, Vorschlags-Tabelle."""
import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from stonebook import config
from stonebook.ai.analysis_schema import AI_FIELDS
from stonebook.ai.image_prep import default_selection
from stonebook.db.repository import AnalysisRepo, ImageRepo, ObjectRepo
from stonebook.fields import CATEGORY_LABELS, FIELD_BY_NAME, is_empty

CONF_GREEN = QColor("#d1e7dd")
CONF_YELLOW = QColor("#fff3cd")
CONF_RED = QColor("#f8d7da")


class AIPanel(QWidget):
    applyRequested = Signal(dict)

    def __init__(self, objects: ObjectRepo, images: ImageRepo,
                 analyses: AnalysisRepo, root: Path, parent=None):
        super().__init__(parent)
        self.objects = objects
        self.images = images
        self.analyses = analyses
        self.root = root
        self.obj_id: str | None = None
        self.worker = None
        self._analysis_id: int | None = None

        lay = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Vertical)

        top = QWidget()
        top_lay = QVBoxLayout(top)
        top_lay.addWidget(QLabel("Bilder für die Analyse (max. Auswahl in den Einstellungen):"))
        self.image_list = QListWidget()
        top_lay.addWidget(self.image_list)
        btns = QHBoxLayout()
        self.start_btn = QPushButton("KI-Analyse starten")
        self.start_btn.clicked.connect(self.start_analysis)
        btns.addWidget(self.start_btn)
        self.status_label = QLabel("")
        btns.addWidget(self.status_label)
        btns.addStretch()
        top_lay.addLayout(btns)
        split.addWidget(top)

        bottom = QWidget()
        bot_lay = QVBoxLayout(bottom)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        bot_lay.addWidget(self.summary_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Feld", "Aktuell", "KI-Vorschlag", "Conf. %", "Übernehmen"])
        self.table.setColumnWidth(0, 190)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 260)
        bot_lay.addWidget(self.table, 1)
        apply_btn = QPushButton("Ausgewählte übernehmen")
        apply_btn.clicked.connect(self._apply_selected)
        bot_lay.addWidget(apply_btn, 0, Qt.AlignmentFlag.AlignRight)
        split.addWidget(bottom)
        split.setSizes([260, 480])
        lay.addWidget(split)

        self._update_key_state()

    def _update_key_state(self):
        has_key = bool(config.get_api_key())
        running = self.worker is not None and self.worker.isRunning()
        self.start_btn.setEnabled(has_key and not running and self.obj_id is not None)
        self.start_btn.setToolTip(
            "" if has_key else "API-Key in den Einstellungen hinterlegen")

    def load_object(self, obj_id: str) -> None:
        self.obj_id = obj_id
        self.image_list.clear()
        rows = self.images.for_object(obj_id)
        preselected = {r["rel_path"] for r in
                       default_selection(rows, config.get_max_images())}
        for r in rows:
            label = f"{CATEGORY_LABELS.get(r['kategorie'], r['kategorie'])} – {r['dateiname']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, dict(r))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if r["rel_path"] in preselected
                               else Qt.CheckState.Unchecked)
            self.image_list.addItem(item)
        self.table.setRowCount(0)
        self.summary_label.setText("")
        self.status_label.setText("")
        self._update_key_state()

    def _checked_images(self) -> list[dict]:
        result = []
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def start_analysis(self):
        if not self.obj_id:
            return
        images = self._checked_images()
        max_n = config.get_max_images()
        if not images:
            QMessageBox.information(self, "KI-Analyse",
                                    "Bitte mindestens ein Bild auswählen.")
            return
        if len(images) > max_n:
            QMessageBox.information(
                self, "KI-Analyse",
                f"Maximal {max_n} Bilder pro Analyse (Einstellungen) — "
                f"ausgewählt sind {len(images)}.")
            return
        row = self.objects.get(self.obj_id)
        object_data = {f.name: row[f.name] for f in AI_FIELDS}
        from stonebook.ai.client import AnalysisWorker
        self.worker = AnalysisWorker(
            config.get_api_key(), config.get_model(), self.root, images, object_data)
        self.worker.finished_ok.connect(self._on_result)
        self.worker.failed.connect(self._on_error)
        self.status_label.setText(f"Analyse läuft ({config.get_model()}) …")
        self._update_key_state()
        self.worker.start()

    def _on_error(self, message: str):
        self.status_label.setText("Fehler.")
        self._update_key_state()
        QMessageBox.critical(self, "KI-Analyse", f"Analyse fehlgeschlagen:\n{message}")

    def _on_result(self, result: dict):
        self.status_label.setText("Analyse abgeschlossen.")
        self._update_key_state()
        if self.obj_id:
            self._analysis_id = self.analyses.add(
                self.obj_id, config.get_model(), json.dumps(result, ensure_ascii=False))
        self.summary_label.setText(
            f"Gesamt-Confidence: {result.get('gesamt_confidence', '–')} %\n"
            f"{result.get('zusammenfassung', '')}")

        current = self.objects.get(self.obj_id) if self.obj_id else None
        self.table.setRowCount(0)
        for fdef in AI_FIELDS:
            entry = result.get(fdef.name)
            if not isinstance(entry, dict):
                continue
            wert = entry.get("wert")
            if is_empty(wert):
                continue
            conf = int(entry.get("confidence_prozent") or 0)
            old = current[fdef.name] if current else None
            r = self.table.rowCount()
            self.table.insertRow(r)
            name_item = QTableWidgetItem(fdef.label)
            name_item.setData(Qt.ItemDataRole.UserRole, fdef.name)
            if entry.get("begruendung"):
                name_item.setToolTip(entry["begruendung"])
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, QTableWidgetItem("" if old is None else str(old)))
            sug_item = QTableWidgetItem(str(wert))
            sug_item.setData(Qt.ItemDataRole.UserRole, wert)
            if entry.get("begruendung"):
                sug_item.setToolTip(entry["begruendung"])
            self.table.setItem(r, 2, sug_item)
            conf_item = QTableWidgetItem(str(conf))
            conf_item.setBackground(CONF_GREEN if conf >= 80
                                    else CONF_YELLOW if conf >= 50 else CONF_RED)
            self.table.setItem(r, 3, conf_item)
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            empty_before = is_empty(old)
            check_item.setCheckState(
                Qt.CheckState.Checked if (empty_before and conf >= 70)
                else Qt.CheckState.Unchecked)
            self.table.setItem(r, 4, check_item)

    def _apply_selected(self):
        values = {}
        for r in range(self.table.rowCount()):
            if self.table.item(r, 4).checkState() != Qt.CheckState.Checked:
                continue
            name = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            wert = self.table.item(r, 2).data(Qt.ItemDataRole.UserRole)
            fdef = FIELD_BY_NAME[name]
            if fdef.ftype in ("int", "scale") and wert is not None:
                wert = int(float(wert))
            values[name] = wert
        if not values:
            QMessageBox.information(self, "KI-Analyse", "Nichts zum Übernehmen ausgewählt.")
            return
        if self._analysis_id is not None:
            self.analyses.set_uebernommen(
                self._analysis_id, json.dumps(values, ensure_ascii=False, default=str))
        self.applyRequested.emit(values)
        QMessageBox.information(
            self, "KI-Analyse",
            f"{len(values)} Felder ins Datenblatt übernommen — dort speichern nicht vergessen.")
