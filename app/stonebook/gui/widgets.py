"""Generische Feld-Editoren für die 43 Standardfelder."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QWidget, QHBoxLayout

from stonebook.fields import FieldDef


class FieldEditor(QWidget):
    """Wrapper um den passenden Qt-Editor; value() liefert DB-taugliche Werte."""
    changed = Signal()

    def __init__(self, fdef: FieldDef, parent=None):
        super().__init__(parent)
        self.fdef = fdef
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        if fdef.ftype == "enum":
            self._w = QComboBox()
            self._w.setEditable(True)
            self._w.addItems(list(fdef.enum_values) or [""])
            self._w.currentTextChanged.connect(lambda _: self.changed.emit())
            self._w.editTextChanged.connect(lambda _: self.changed.emit())
        elif fdef.ftype == "scale":
            self._w = QComboBox()
            self._w.addItems([""] + [str(i) for i in range(1, 11)])
            self._w.currentTextChanged.connect(lambda _: self.changed.emit())
        elif fdef.ftype == "text":
            self._w = QPlainTextEdit()
            self._w.setFixedHeight(60)
            self._w.textChanged.connect(self.changed.emit)
        else:
            self._w = QLineEdit()
            if fdef.ftype == "float":
                v = QDoubleValidator()
                v.setNotation(QDoubleValidator.Notation.StandardNotation)
                self._w.setValidator(v)
            elif fdef.ftype == "int":
                self._w.setValidator(QIntValidator(0, 1000000))
            elif fdef.ftype == "date":
                self._w.setPlaceholderText("YYYY-MM-DD")
            self._w.textChanged.connect(lambda _: self.changed.emit())

        if not fdef.editable:
            self._w.setEnabled(False)
        if fdef.description:
            self._w.setToolTip(fdef.description)
        lay.addWidget(self._w)

    def value(self):
        t = self.fdef.ftype
        if t in ("enum", "scale"):
            text = self._w.currentText().strip()
        elif t == "text":
            text = self._w.toPlainText().strip()
        else:
            text = self._w.text().strip()
        if not text:
            return None
        if t == "float":
            try:
                return float(text.replace(",", "."))
            except ValueError:
                return None
        if t in ("int", "scale"):
            try:
                return int(float(text.replace(",", ".")))
            except ValueError:
                return None
        return text

    def set_value(self, value) -> None:
        text = "" if value is None else str(value)
        if self.fdef.ftype == "float" and text.endswith(".0"):
            text = text[:-2]
        self._w.blockSignals(True)
        if self.fdef.ftype in ("enum", "scale"):
            self._w.setCurrentText(text)
        elif self.fdef.ftype == "text":
            self._w.setPlainText(text)
        else:
            self._w.setText(text)
        self._w.blockSignals(False)
