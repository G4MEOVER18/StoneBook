"""Einstellungen: API-Key (keyring), Modellwahl, max. Bilder, Repo-Root."""
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLineEdit, QSpinBox)

from stonebook import config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.resize(560, 240)
        form = QFormLayout(self)

        self.key_edit = QLineEdit(config.get_api_key())
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-ant-…")
        form.addRow("Anthropic API-Key:", self.key_edit)

        self.model_combo = QComboBox()
        self.model_combo.addItems(config.AVAILABLE_MODELS)
        idx = self.model_combo.findText(config.get_model())
        self.model_combo.setCurrentIndex(max(0, idx))
        form.addRow("KI-Modell:", self.model_combo)

        self.max_images = QSpinBox()
        self.max_images.setRange(1, 12)
        self.max_images.setValue(config.get_max_images())
        form.addRow("Max. Bilder pro Analyse:", self.max_images)

        root = config.repo_root()
        self.root_edit = QLineEdit(str(root) if root else "")
        self.root_edit.setReadOnly(True)
        form.addRow("Repo-Ordner:", self.root_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self):
        config.set_api_key(self.key_edit.text().strip())
        config.set_model(self.model_combo.currentText())
        config.set_max_images(self.max_images.value())
        self.accept()
