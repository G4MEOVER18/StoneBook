"""Neues-Objekt-Assistent: ersetzt das alte MakeObject-Tool."""
import re
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWizard, QWizardPage)

from stonebook.db.repository import ImageRepo, ObjectRepo
from stonebook.fields import CATEGORY_FOLDERS, CATEGORY_LABELS, IMAGE_CATEGORIES
from stonebook.migration.image_indexer import IMG_EXT, _exif_and_size, _sha256

_KEYWORDS = [
    (re.compile(r"uv[_\- ]?365|365 ?nm", re.I), "UV365"),
    (re.compile(r"uv[_\- ]?395|395 ?nm", re.I), "UV395"),
    (re.compile(r"mikro|macro|makro", re.I), "Mikroskop"),
    (re.compile(r"übersicht|uebersicht|overview|gesamt", re.I), "Uebersicht"),
    (re.compile(r"sonder|detail|einschluss", re.I), "Sonderaufnahmen"),
]


def suggest_category(filename: str) -> str:
    for pat, cat in _KEYWORDS:
        if pat.search(filename):
            return cat
    return "Kamera"


class BasePage(QWizardPage):
    def __init__(self, objects: ObjectRepo):
        super().__init__()
        self.setTitle("Neues Objekt anlegen")
        self.setSubTitle("Grunddaten — die Objekt-ID wird automatisch vergeben.")
        form = QFormLayout(self)
        self.id_edit = QLineEdit(objects.next_free_id())
        form.addRow("Objekt-ID:", self.id_edit)
        self.name_edit = QLineEdit()
        form.addRow("Name:", self.name_edit)
        self.fundort_edit = QLineEdit()
        form.addRow("Fundort:", self.fundort_edit)
        self.datum_edit = QLineEdit()
        self.datum_edit.setPlaceholderText("YYYY-MM-DD (leer = EXIF-Vorschlag)")
        form.addRow("Funddatum:", self.datum_edit)


class ImagesPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Bilder zuordnen")
        self.setSubTitle("Quellordner wählen — Kategorien werden aus Dateinamen vorgeschlagen.")
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_edit.setReadOnly(True)
        row.addWidget(self.src_edit)
        btn = QPushButton("Quellordner …")
        btn.clicked.connect(self._pick)
        row.addWidget(btn)
        lay.addLayout(row)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Datei", "Kategorie"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 380)
        lay.addWidget(self.table)
        self.exif_label = QLabel("")
        lay.addWidget(self.exif_label)
        self.exif_datum = ""

    def _pick(self):
        folder = QFileDialog.getExistingDirectory(self, "Quellordner wählen")
        if not folder:
            return
        self.src_edit.setText(folder)
        self.table.setRowCount(0)
        oldest = None
        for f in sorted(Path(folder).rglob("*")):
            if not f.is_file() or f.suffix.lower() not in IMG_EXT:
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            item = QTableWidgetItem(str(f))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, item)
            combo = QComboBox()
            for cat in IMAGE_CATEGORIES:
                if cat != "Sonstige":
                    combo.addItem(CATEGORY_LABELS[cat], cat)
            idx = combo.findData(suggest_category(f.name))
            combo.setCurrentIndex(max(0, idx))
            self.table.setCellWidget(r, 1, combo)
            datum, _, _ = _exif_and_size(f)
            if datum and (oldest is None or datum < oldest):
                oldest = datum
        self.exif_datum = (oldest or "")[:10]
        self.exif_label.setText(
            f"Ältestes EXIF-Datum: {self.exif_datum}" if self.exif_datum
            else "Keine EXIF-Daten gefunden.")
        self.completeChanged.emit()

    def entries(self) -> list[tuple[Path, str]]:
        result = []
        for r in range(self.table.rowCount()):
            path = Path(self.table.item(r, 0).text())
            combo = self.table.cellWidget(r, 1)
            result.append((path, combo.currentData()))
        return result


class NewObjectWizard(QWizard):
    def __init__(self, objects: ObjectRepo, images: ImageRepo, root: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Neues Objekt")
        self.resize(760, 560)
        self.objects = objects
        self.images = images
        self.root = root
        self.created_obj_id: str | None = None

        self.base_page = BasePage(objects)
        self.images_page = ImagesPage()
        self.addPage(self.base_page)
        self.addPage(self.images_page)

        summary = QWizardPage()
        summary.setTitle("Zusammenfassung")
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        QVBoxLayout(summary).addWidget(self._summary_label)
        self.addPage(summary)
        self.currentIdChanged.connect(self._update_summary)

    def _update_summary(self, page_id: int):
        if page_id != 2:
            return
        entries = self.images_page.entries()
        obj_id = self.base_page.id_edit.text().strip()
        datum = self.base_page.datum_edit.text().strip() or self.images_page.exif_datum
        self._summary_label.setText(
            f"Objekt-ID: {obj_id}\n"
            f"Name: {self.base_page.name_edit.text().strip() or '—'}\n"
            f"Fundort: {self.base_page.fundort_edit.text().strip() or '—'}\n"
            f"Funddatum: {datum or '—'}\n"
            f"Bilder: {len(entries)}\n\n"
            f"Beim Abschluss wird objects\\{obj_id}\\ mit den Standard-Unterordnern\n"
            f"angelegt, die Bilder werden kopiert und in der Datenbank registriert.")

    def accept(self):
        obj_id = self.base_page.id_edit.text().strip()
        if not re.match(r"^OBJ_\d{4}$", obj_id) or self.objects.exists(obj_id):
            self.base_page.id_edit.setText(self.objects.next_free_id())
            self.back()
            self.back()
            return
        obj_dir = self.root / "objects" / obj_id
        for folder in CATEGORY_FOLDERS.values():
            if folder:
                (obj_dir / folder).mkdir(parents=True, exist_ok=True)
        fundort = self.base_page.fundort_edit.text().strip()
        (obj_dir / "Fundort.txt").write_text(fundort, encoding="utf-8")

        datum = self.base_page.datum_edit.text().strip() or self.images_page.exif_datum
        self.objects.create(
            obj_id,
            folder_path=f"objects/{obj_id}",
            Name=self.base_page.name_edit.text().strip() or None,
            Fundort=fundort or None,
            Funddatum=datum or None,
        )
        for src, cat in self.images_page.entries():
            target_dir = obj_dir / CATEGORY_FOLDERS[cat] if CATEGORY_FOLDERS[cat] else obj_dir
            dest = target_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
            rel = dest.relative_to(self.root).as_posix()
            exif_datum, w, h = _exif_and_size(dest)
            self.images.add(obj_id, cat, rel, dateiname=dest.name, sha256=_sha256(dest),
                            exif_datum=exif_datum, breite_px=w, hoehe_px=h)
        self.objects.refresh_status(obj_id)
        self.created_obj_id = obj_id
        super().accept()
