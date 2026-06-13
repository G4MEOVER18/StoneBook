"""Einstellungen: KI-Backend (Claude oder lokal), Modell, Keys, Repo-Root."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from stonebook import config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.resize(620, 520)
        outer = QVBoxLayout(self)

        # --- Backend-Auswahl ---
        backend_box = QGroupBox("KI-Backend")
        bform = QFormLayout(backend_box)
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Claude (Anthropic Cloud)", config.BACKEND_ANTHROPIC)
        self.backend_combo.addItem("Lokal / OpenAI-kompatibel (Ollama, Open-WebUI, KI-Core)",
                                   config.BACKEND_LOCAL)
        idx = self.backend_combo.findData(config.get_backend())
        self.backend_combo.setCurrentIndex(max(0, idx))
        self.backend_combo.currentIndexChanged.connect(self._toggle_backend)
        bform.addRow("Backend:", self.backend_combo)
        outer.addWidget(backend_box)

        # --- Claude-Bereich ---
        self.cloud_box = QGroupBox("Claude (Cloud)")
        cform = QFormLayout(self.cloud_box)
        self.key_edit = QLineEdit(config.get_api_key())
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-ant-…")
        cform.addRow("Anthropic API-Key:", self.key_edit)
        self.model_combo = QComboBox()
        self.model_combo.addItems(config.AVAILABLE_MODELS)
        midx = self.model_combo.findText(config.get_model())
        self.model_combo.setCurrentIndex(max(0, midx))
        cform.addRow("Modell:", self.model_combo)
        outer.addWidget(self.cloud_box)

        # --- Lokal-Bereich ---
        self.local_box = QGroupBox("Lokal / OpenAI-kompatibel")
        lform = QFormLayout(self.local_box)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(config.LOCAL_PRESETS.keys())
        self.preset_combo.activated.connect(self._apply_preset)
        lform.addRow("Vorlage:", self.preset_combo)
        self.base_url_edit = QLineEdit(config.get_local_base_url())
        self.base_url_edit.setPlaceholderText("http://localhost:11434/v1")
        lform.addRow("Base-URL:", self.base_url_edit)
        self.local_model_edit = QLineEdit(config.get_local_model())
        self.local_model_edit.setPlaceholderText("z.B. gemma3:27b, llava, qwen2.5-vl")
        lform.addRow("Modell:", self.local_model_edit)
        self.local_key_edit = QLineEdit(config.get_local_api_key())
        self.local_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.local_key_edit.setPlaceholderText("optional (z.B. Bearer-Token)")
        lform.addRow("API-Key (optional):", self.local_key_edit)
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Verbindung testen")
        self.test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_btn)
        self.test_label = QLabel("")
        test_row.addWidget(self.test_label, 1)
        lform.addRow("", self._wrap(test_row))
        hint = QLabel("Vision-fähiges Modell nötig (z.B. gemma3, llava, qwen2.5-vl, llama3.2-vision).")
        hint.setStyleSheet("color: #6c757d; font-size: 11px;")
        lform.addRow("", hint)
        outer.addWidget(self.local_box)

        # --- Allgemein ---
        gen_box = QGroupBox("Allgemein")
        gform = QFormLayout(gen_box)
        self.max_images = QSpinBox()
        self.max_images.setRange(1, 12)
        self.max_images.setValue(config.get_max_images())
        gform.addRow("Max. Bilder pro Analyse:", self.max_images)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(30, 600)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setValue(config.get_timeout())
        gform.addRow("Timeout:", self.timeout_spin)
        root = config.repo_root()
        self.root_edit = QLineEdit(str(root) if root else "")
        self.root_edit.setReadOnly(True)
        gform.addRow("Repo-Ordner:", self.root_edit)
        outer.addWidget(gen_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._toggle_backend()

    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _toggle_backend(self):
        is_local = self.backend_combo.currentData() == config.BACKEND_LOCAL
        self.local_box.setVisible(is_local)
        self.cloud_box.setVisible(not is_local)

    def _apply_preset(self):
        name = self.preset_combo.currentText()
        base, model = config.LOCAL_PRESETS.get(name, ("", ""))
        if base:
            self.base_url_edit.setText(base)
        if model:
            self.local_model_edit.setText(model)

    def _test_connection(self):
        from stonebook.ai.providers import OpenAICompatProvider
        self.test_label.setText("Teste …")
        self.test_btn.setEnabled(False)
        try:
            provider = OpenAICompatProvider(
                self.base_url_edit.text().strip(), self.local_model_edit.text().strip(),
                self.local_key_edit.text().strip())
            msg = provider.test_connection()
            self.test_label.setText(msg)
            self.test_label.setStyleSheet("color: #198754;")
        except Exception as e:
            self.test_label.setText(f"Fehler: {e}")
            self.test_label.setStyleSheet("color: #dc3545;")
        finally:
            self.test_btn.setEnabled(True)

    def _save(self):
        config.set_backend(self.backend_combo.currentData())
        config.set_api_key(self.key_edit.text().strip())
        config.set_model(self.model_combo.currentText())
        config.set_local_base_url(self.base_url_edit.text().strip())
        config.set_local_model(self.local_model_edit.text().strip())
        config.set_local_api_key(self.local_key_edit.text().strip())
        config.set_max_images(self.max_images.value())
        config.set_timeout(self.timeout_spin.value())
        self.accept()
