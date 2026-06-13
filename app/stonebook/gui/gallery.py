"""Bildergalerie pro Objekt: Kategorie-Tabs, Thumbnails, Vollbild-Ansicht."""
import shutil
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QScrollArea,
                               QTabWidget, QVBoxLayout, QWidget)

from stonebook import config
from stonebook.db.repository import ImageRepo, ObjectRepo
from stonebook.fields import CATEGORY_FOLDERS, CATEGORY_LABELS, IMAGE_CATEGORIES

THUMB_SIZE = 192


class ImageViewer(QDialog):
    """Vollbild-Dialog mit einfachem Zoom (Mausrad)."""

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(path.name)
        self.resize(1100, 800)
        self._scale = 1.0
        self._pix = QPixmap(str(path))
        lay = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.label)
        lay.addWidget(self.scroll)
        self._apply()

    def _apply(self):
        if self._pix.isNull():
            self.label.setText("Bild kann nicht geladen werden.")
            return
        scaled = self._pix.scaled(
            self._pix.size() * self._scale,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.label.setPixmap(scaled)
        self.label.resize(scaled.size())

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self._scale = max(0.1, min(8.0, self._scale * (1.15 if delta > 0 else 1 / 1.15)))
        self._apply()


def thumbnail_for(root: Path, rel_path: str, sha256: str) -> QPixmap:
    """Thumbnail mit Cache unter data/thumbs/<sha>.jpg."""
    cache_dir = config.thumbs_dir(root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{sha256 or rel_path.replace('/', '_')}.jpg"
    if cache.is_file():
        return QPixmap(str(cache))
    src = root / rel_path
    pix = QPixmap(str(src))
    if pix.isNull():
        return pix
    thumb = pix.scaled(THUMB_SIZE, THUMB_SIZE,
                       Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    thumb.save(str(cache), "JPG", 85)
    return thumb


class CategoryGallery(QWidget):
    imageActivated = Signal(str)  # rel_path

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setSpacing(8)
        self.list.itemDoubleClicked.connect(
            lambda item: self.imageActivated.emit(item.data(Qt.ItemDataRole.UserRole)))
        lay.addWidget(self.list)

    def set_images(self, root: Path, rows) -> None:
        self.list.clear()
        for r in rows:
            item = QListWidgetItem(QIcon(thumbnail_for(root, r["rel_path"], r["sha256"])),
                                   r["dateiname"] or Path(r["rel_path"]).name)
            item.setData(Qt.ItemDataRole.UserRole, r["rel_path"])
            if r["herkunft_obj_id"]:
                item.setToolTip(f"Ursprünglich {r['herkunft_obj_id']}")
            self.list.addItem(item)

    def selected_rel_path(self) -> str | None:
        items = self.list.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None


class GalleryWidget(QWidget):
    def __init__(self, objects: ObjectRepo, images: ImageRepo, root: Path, parent=None):
        super().__init__(parent)
        self.objects = objects
        self.images = images
        self.root = root
        self.obj_id: str | None = None

        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.galleries: dict[str, CategoryGallery] = {}
        for cat in IMAGE_CATEGORIES:
            g = CategoryGallery()
            g.imageActivated.connect(self._open_viewer)
            self.galleries[cat] = g
            self.tabs.addTab(g, CATEGORY_LABELS[cat])
        lay.addWidget(self.tabs, 1)

        btns = QHBoxLayout()
        self.cat_combo = QComboBox()
        self.cat_combo.addItems([CATEGORY_LABELS[c] for c in IMAGE_CATEGORIES if c != "Sonstige"])
        btns.addWidget(self.cat_combo)
        add_btn = QPushButton("Bilder hinzufügen …")
        add_btn.clicked.connect(self._add_images)
        btns.addWidget(add_btn)
        cover_btn = QPushButton("Als Übersichtsfoto setzen")
        cover_btn.clicked.connect(self._set_cover)
        btns.addWidget(cover_btn)
        btns.addStretch()
        lay.addLayout(btns)

    def load_object(self, obj_id: str) -> None:
        self.obj_id = obj_id
        counts = {}
        for cat in IMAGE_CATEGORIES:
            rows = self.images.for_object(obj_id, cat)
            self.galleries[cat].set_images(self.root, rows)
            counts[cat] = len(rows)
        for i, cat in enumerate(IMAGE_CATEGORIES):
            label = CATEGORY_LABELS[cat]
            self.tabs.setTabText(i, f"{label} ({counts[cat]})" if counts[cat] else label)
        # ersten Tab mit Bildern aktivieren
        for i, cat in enumerate(IMAGE_CATEGORIES):
            if counts[cat]:
                self.tabs.setCurrentIndex(i)
                break

    def _open_viewer(self, rel_path: str):
        ImageViewer(self.root / rel_path, self).exec()

    def _current_category(self) -> str:
        return IMAGE_CATEGORIES[self.tabs.currentIndex()]

    def _add_images(self):
        if not self.obj_id:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Bilder hinzufügen", "",
            "Bilder (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.heic)")
        if not files:
            return
        label = self.cat_combo.currentText()
        cat = next(c for c, lab in CATEGORY_LABELS.items() if lab == label)
        folder_name = CATEGORY_FOLDERS[cat]
        target_dir = self.root / "objects" / self.obj_id
        if folder_name:
            target_dir = target_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        from stonebook.migration.image_indexer import _exif_and_size, _sha256
        for f in files:
            src = Path(f)
            dest = target_dir / src.name
            if dest.exists():
                QMessageBox.warning(self, "StoneBook",
                                    f"{src.name} existiert bereits — übersprungen.")
                continue
            shutil.copy2(src, dest)
            rel = dest.relative_to(self.root).as_posix()
            exif_datum, w, h = _exif_and_size(dest)
            self.images.add(self.obj_id, cat, rel, dateiname=dest.name,
                            sha256=_sha256(dest), exif_datum=exif_datum,
                            breite_px=w, hoehe_px=h)
        self.objects.refresh_status(self.obj_id)
        self.load_object(self.obj_id)

    def _set_cover(self):
        if not self.obj_id:
            return
        rel = self.galleries[self._current_category()].selected_rel_path()
        if not rel:
            QMessageBox.information(self, "StoneBook", "Bitte zuerst ein Bild auswählen.")
            return
        self.objects.update_fields(self.obj_id, {"Foto_Uebersicht": rel})
        QMessageBox.information(self, "StoneBook", f"Übersichtsfoto gesetzt:\n{rel}")
