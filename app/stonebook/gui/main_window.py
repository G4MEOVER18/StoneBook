"""Hauptfenster: Toolbar, Objektliste links, Detail rechts."""
import os
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QMainWindow, QMessageBox, QPlainTextEdit,
                               QSplitter, QStackedWidget, QToolBar, QVBoxLayout,
                               QDialog, QDialogButtonBox)

from stonebook import config
from stonebook.db.repository import ObjectRepo
from stonebook.gui.object_detail import ObjectDetail
from stonebook.gui.object_list import ObjectListWidget


class MigrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Datenbank neu aufbauen")
        self.resize(700, 400)
        lay = QVBoxLayout(self)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self.accept)
        lay.addWidget(self.buttons)

    def append(self, text: str):
        self.log.appendPlainText(text)


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, root: Path):
        super().__init__()
        self.conn = conn
        self.root = root
        self.objects = ObjectRepo(conn)

        self.setWindowTitle("StoneBook V3 – Sammlungsverwaltung")
        self.resize(1400, 860)

        toolbar = QToolBar("Hauptleiste")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.action_browse = QAction("Sammlung", self)
        self.action_browse.triggered.connect(lambda: self._show_page(0))
        toolbar.addAction(self.action_browse)

        self.action_dashboard = QAction("Dashboard", self)
        self.action_dashboard.triggered.connect(lambda: self._show_page(1))
        toolbar.addAction(self.action_dashboard)

        toolbar.addSeparator()

        self.action_new = QAction("Neues Objekt", self)
        self.action_new.triggered.connect(self.new_object)
        toolbar.addAction(self.action_new)

        self.action_export = QAction("Export", self)
        self.action_export.triggered.connect(self.show_export_menu)
        toolbar.addAction(self.action_export)

        self.action_rebuild = QAction("DB neu aufbauen", self)
        self.action_rebuild.triggered.connect(self.rebuild_db)
        toolbar.addAction(self.action_rebuild)

        self.action_settings = QAction("Einstellungen", self)
        self.action_settings.triggered.connect(self.open_settings)
        toolbar.addAction(self.action_settings)

        self.stack = QStackedWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.object_list = ObjectListWidget(self.objects)
        self.detail = ObjectDetail(conn, root)
        self.object_list.objectSelected.connect(self._object_selected)
        self.object_list.openFolderRequested.connect(self.open_object_folder)
        self.object_list.archiveRequested.connect(self._archive_object)
        self.detail.datasheet.saved.connect(self._object_saved)
        splitter.addWidget(self.object_list)
        splitter.addWidget(self.detail)
        splitter.setSizes([520, 880])
        self.stack.addWidget(splitter)

        from stonebook.gui.dashboard import DashboardWidget
        self.dashboard = DashboardWidget(self.objects)
        self.stack.addWidget(self.dashboard)
        self.setCentralWidget(self.stack)

        self._update_status()

    def _show_page(self, index: int):
        if index == 1:
            self.dashboard.refresh()
        self.stack.setCurrentIndex(index)

    # --- Navigation -------------------------------------------------------

    def _object_selected(self, obj_id: str):
        if self.detail.datasheet.is_dirty():
            res = QMessageBox.question(
                self, "Ungespeicherte Änderungen",
                "Änderungen am aktuellen Objekt speichern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.Yes:
                self.detail.datasheet.save()
        self.detail.load_object(obj_id)

    def _object_saved(self, obj_id: str):
        self.object_list.refresh()
        self.object_list.refresh_minerals()
        self.object_list.select_object(obj_id)
        self._update_status()

    def _update_status(self):
        total = self.objects.count()
        aktiv = len(self.objects.list_objects(status="aktiv"))
        self.statusBar().showMessage(
            f"{total} Objekte ({aktiv} aktiv) – DB: {config.db_path(self.root)}")

    # --- Aktionen ---------------------------------------------------------

    def rebuild_db(self):
        res = QMessageBox.question(
            self, "Datenbank neu aufbauen",
            "Die Datenbank wird gelöscht und aus den Repo-Quellen (CSVs, Objektordner)\n"
            "komplett neu aufgebaut. Manuelle Änderungen seit dem letzten CSV-Export\n"
            "gehen dabei verloren.\n\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res != QMessageBox.StandardButton.Yes:
            return
        from stonebook.db.database import open_db
        from stonebook.migration.migrate import migrate

        dlg = MigrationDialog(self)
        dlg.show()
        self.conn.close()
        try:
            migrate(self.root, config.db_path(self.root), log=dlg.append)
        finally:
            self.conn = open_db(config.db_path(self.root))
            self._rewire(self.conn)
        dlg.exec()
        self.object_list.refresh()
        self.object_list.refresh_minerals()
        self._update_status()

    def _rewire(self, conn: sqlite3.Connection):
        self.objects.conn = conn
        self.object_list.objects.conn = conn
        d = self.detail
        d.objects.conn = conn
        d.images.conn = conn
        d.aliases.conn = conn
        d.analyses.conn = conn
        d.reports.conn = conn
        self.dashboard.objects.conn = conn

    def show_export_menu(self):
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QFileDialog, QMenu

        menu = QMenu(self)
        act_csv_std = menu.addAction("CSV → data\\csv\\export_latest.csv")
        act_csv = menu.addAction("CSV exportieren nach …")
        act_json = menu.addAction("JSON-Vollexport nach …")
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        try:
            if chosen == act_csv_std:
                from stonebook.export.csv_export import export_csv
                path = self.root / "data" / "csv" / "export_latest.csv"
                n = export_csv(self.conn, path)
                QMessageBox.information(self, "Export", f"{n} Objekte exportiert:\n{path}")
            elif chosen == act_csv:
                target, _ = QFileDialog.getSaveFileName(self, "CSV exportieren",
                                                        "stonebook_export.csv", "CSV (*.csv)")
                if target:
                    from stonebook.export.csv_export import export_csv
                    n = export_csv(self.conn, Path(target))
                    QMessageBox.information(self, "Export", f"{n} Objekte exportiert:\n{target}")
            elif chosen == act_json:
                target, _ = QFileDialog.getSaveFileName(self, "JSON exportieren",
                                                        "stonebook_export.json", "JSON (*.json)")
                if target:
                    from stonebook.export.json_export import export_json
                    counts = export_json(self.conn, Path(target))
                    QMessageBox.information(
                        self, "Export",
                        f"Exportiert: {counts['objects']} Objekte, "
                        f"{counts['images']} Bilder, {counts['aliases']} Aliase\n{target}")
        except Exception as e:
            QMessageBox.critical(self, "Export", f"Export fehlgeschlagen:\n{e}")

    def open_settings(self):
        from stonebook.gui.settings_dialog import SettingsDialog
        if SettingsDialog(self).exec():
            self.detail.ai_panel._update_key_state()

    def _archive_object(self, obj_id: str):
        self.objects.set_status(obj_id, "archiviert")
        self.object_list.refresh()
        self._update_status()

    def new_object(self):
        from stonebook.gui.new_object_wizard import NewObjectWizard
        wiz = NewObjectWizard(self.detail.objects, self.detail.images, self.root, self)
        if wiz.exec() and wiz.created_obj_id:
            self.object_list.refresh()
            self.object_list.select_object(wiz.created_obj_id)
            self._update_status()

    def open_object_folder(self, obj_id: str):
        folder = self.root / "objects" / obj_id
        if folder.is_dir():
            os.startfile(str(folder))  # noqa: S606 - lokale Ordneranzeige
