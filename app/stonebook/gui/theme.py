"""Modernes dunkles Theme (QSS) für StoneBook."""

ACCENT = "#4a9d7f"      # gedämpftes Mineral-Grün
ACCENT_HOVER = "#5bb392"
BG = "#1e2228"
BG_ALT = "#262b33"
BG_CARD = "#2d333d"
BORDER = "#3a414c"
TEXT = "#e4e7eb"
TEXT_MUTED = "#9aa3ad"

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog, QWidget {{
    background-color: {BG};
}}
QToolBar {{
    background-color: {BG_ALT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    spacing: 6px;
}}
QToolBar QToolButton {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
    color: {TEXT};
}}
QToolBar QToolButton:hover {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: white;
}}
QStatusBar {{
    background-color: {BG_ALT};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: none;
}}
QPushButton {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: {BORDER}; }}
QPushButton:pressed {{ background-color: {ACCENT}; color: white; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; background-color: {BG_ALT}; }}
QGroupBox {{
    background-color: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT_HOVER};
}}
QTableView, QListWidget, QTreeView {{
    background-color: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
    alternate-background-color: {BG_CARD};
    outline: none;
}}
QHeaderView::section {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-weight: 600;
}}
QTableView::item {{ padding: 4px; }}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    top: -1px;
    background-color: {BG_ALT};
}}
QTabBar::tab {{
    background-color: {BG};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    padding: 8px 18px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {BG_ALT};
    color: {ACCENT_HOVER};
    border-bottom: 2px solid {ACCENT};
}}
QScrollBar:vertical {{
    background: {BG}; width: 11px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: {BG}; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QSplitter::handle {{ background: {BORDER}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER}; border-radius: 4px;
    background: {BG_CARD};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT};
    border: 1px solid {ACCENT};
    padding: 6px;
    border-radius: 4px;
}}
"""
