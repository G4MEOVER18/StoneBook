"""Dashboard: Kennzahlen und Verteilungen der Sammlung."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QProgressBar, QScrollArea, QVBoxLayout, QWidget)

from stonebook.db.repository import ObjectRepo
from stonebook.gui.theme import ACCENT, ACCENT_HOVER, BG_CARD, TEXT_MUTED

STATUS_LABELS = {"aktiv": "Aktiv", "platzhalter": "Platzhalter", "archiviert": "Archiviert"}


def _stat_card(title: str, value: str, subtitle: str = "") -> QWidget:
    card = QGroupBox()
    card.setStyleSheet(
        f"QGroupBox {{ background-color: {BG_CARD}; border-radius: 10px; padding: 14px; }}")
    lay = QVBoxLayout(card)
    t = QLabel(title.upper())
    t.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;")
    v = QLabel(value)
    v.setStyleSheet(f"color: {ACCENT_HOVER}; font-size: 26px; font-weight: 700;")
    lay.addWidget(t)
    lay.addWidget(v)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        lay.addWidget(s)
    return card


class DashboardWidget(QWidget):
    def __init__(self, objects: ObjectRepo, parent=None):
        super().__init__(parent)
        self.objects = objects
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.inner = QWidget()
        self.layout_v = QVBoxLayout(self.inner)
        scroll.setWidget(self.inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh(self) -> None:
        while self.layout_v.count():
            item = self.layout_v.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        s = self.objects.statistics()
        header = QLabel("Sammlungs-Übersicht")
        header.setStyleSheet("font-size: 20px; font-weight: 700; padding: 4px 0;")
        self.layout_v.addWidget(header)

        cards = QGridLayout()
        aktiv = s["status"].get("aktiv", 0)
        cards.addWidget(_stat_card("Objekte gesamt", str(s["gesamt"]),
                                   f"{aktiv} aktiv dokumentiert"), 0, 0)
        cards.addWidget(_stat_card("Mit Bildern", str(s["mit_bildern"]),
                                   f"{s['bilder_gesamt']} Fotos gesamt"), 0, 1)
        cards.addWidget(_stat_card("Gemergte Duplikate", str(s["aliase"]),
                                   "als Alias verknüpft"), 0, 2)
        conf = s["durchschnitt_confidence"]
        cards.addWidget(_stat_card("Ø Confidence",
                                   f"{conf} %" if conf is not None else "–",
                                   "Bestimmungssicherheit"), 1, 0)
        cards.addWidget(_stat_card("Schätzwert (roh)",
                                   f"{s['wert_roh_chf']:.0f} CHF", "Summe Rohwerte"), 1, 1)
        mineral_count = len(self.objects.distinct_values("Mineral_Primaer"))
        cards.addWidget(_stat_card("Mineral-Arten", str(mineral_count),
                                   "verschiedene Hauptminerale"), 1, 2)
        self.layout_v.addLayout(cards)

        self.layout_v.addWidget(self._status_box(s["status"], s["gesamt"]))
        self.layout_v.addWidget(self._minerals_box(s["top_minerals"]))
        self.layout_v.addStretch()

    def _status_box(self, status: dict, total: int) -> QWidget:
        box = QGroupBox("Verteilung nach Status")
        lay = QVBoxLayout(box)
        for key in ("aktiv", "platzhalter", "archiviert"):
            n = status.get(key, 0)
            lay.addLayout(self._bar_row(STATUS_LABELS[key], n, total))
        return box

    def _minerals_box(self, minerals: list) -> QWidget:
        box = QGroupBox("Häufigste Minerale (Top 10)")
        lay = QVBoxLayout(box)
        if not minerals:
            lay.addWidget(QLabel("Noch keine Mineraldaten erfasst."))
            return box
        top = minerals[0][1]
        for name, n in minerals:
            lay.addLayout(self._bar_row(name, n, top))
        return box

    def _bar_row(self, label: str, value: int, maximum: int) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(170)
        row.addWidget(lbl)
        bar = QProgressBar()
        bar.setMaximum(max(1, maximum))
        bar.setValue(value)
        bar.setTextVisible(False)
        bar.setFixedHeight(16)
        bar.setStyleSheet(
            f"QProgressBar {{ background: {BG_CARD}; border-radius: 8px; }}"
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 8px; }}")
        row.addWidget(bar, 1)
        count = QLabel(str(value))
        count.setMinimumWidth(40)
        count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(count)
        return row
