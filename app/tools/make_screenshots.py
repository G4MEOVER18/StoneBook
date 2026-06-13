"""Erzeugt Screenshots des laufenden Tools (headless, offscreen) für die Doku.

Aufruf:  python tools/make_screenshots.py
Ergebnis: docs/screenshots/*.png im Repo-Root.
"""
import os
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from stonebook.db.database import open_db  # noqa: E402
from stonebook.gui.theme import QSS  # noqa: E402
from stonebook.migration.migrate import migrate  # noqa: E402

OUT_DIR = REPO / "docs" / "screenshots"

SAMPLE_RESULT = {
    "Mineral_Primaer": {"wert": "Quarz", "confidence_prozent": 88,
                        "begruendung": "Muscheliger Bruch, Glasglanz, Härte ~7."},
    "Varietaet": {"wert": "Milchquarz", "confidence_prozent": 72,
                  "begruendung": "Weißlich-trübe Erscheinung."},
    "Farbe_beobachtet": {"wert": "weiß mit braunen Adern", "confidence_prozent": 90},
    "Glanz": {"wert": "glasig", "confidence_prozent": 80},
    "Transparenz": {"wert": "durchscheinend", "confidence_prozent": 65},
    "Mohs_Haerte_min": {"wert": 6.5, "confidence_prozent": 75},
    "Mohs_Haerte_max": {"wert": 7.0, "confidence_prozent": 75},
    "UV_365nm": {"wert": "schwache grünliche Fluoreszenz", "confidence_prozent": 55,
                 "begruendung": "Leichtes Leuchten im UV-Bild erkennbar."},
    "gesamt_confidence": 82,
    "zusammenfassung": "Massiver Quarz (wahrscheinlich Milchquarz) mit Eisenoxidadern. "
                       "Härte und Bruchverhalten passen zu Quarz; UV-Reaktion schwach.",
}


def _grab(widget, name, app, size=(1440, 880)):
    widget.resize(*size)
    widget.show()
    for _ in range(6):
        app.processEvents()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    widget.grab().save(str(path), "PNG")
    print(f"  geschrieben: {path.relative_to(REPO)}")


def _load_font(app) -> None:
    """Sorgt für echte Glyphen (auch unter dem offscreen-Backend)."""
    for fname in ("segoeui.ttf", "arial.ttf", "tahoma.ttf"):
        fpath = Path(r"C:\Windows\Fonts") / fname
        if fpath.is_file():
            fid = QFontDatabase.addApplicationFont(str(fpath))
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                app.setFont(QFont(families[0], 10))
                return


def main() -> int:
    app = QApplication(sys.argv)
    _load_font(app)
    app.setStyleSheet(QSS)

    tmp_db = Path(tempfile.mkdtemp()) / "shots.sqlite3"
    migrate(REPO, tmp_db, log=lambda *_: None)
    conn = open_db(tmp_db)

    from stonebook.gui.main_window import MainWindow
    win = MainWindow(conn, REPO)
    win.resize(1440, 880)
    win.show()
    for _ in range(6):
        app.processEvents()

    # Objekt mit Daten + Bildern auswählen
    win.object_list.search.setText("Quarz")
    for _ in range(4):
        app.processEvents()
    win.object_list.select_object("OBJ_0043")
    for _ in range(6):
        app.processEvents()

    # 1) Sammlung + Datenblatt
    win.detail.setCurrentIndex(0)
    _grab(win, "01_sammlung_datenblatt.png", app)

    # 2) Galerie
    win.detail.setCurrentIndex(1)
    for _ in range(6):
        app.processEvents()
    _grab(win, "02_galerie.png", app)

    # 3) KI-Analyse mit Beispielvorschlägen
    win.detail.setCurrentIndex(2)
    win.detail.ai_panel._on_result(SAMPLE_RESULT)
    for _ in range(6):
        app.processEvents()
    _grab(win, "03_ki_analyse.png", app)

    # 4) Dashboard
    win._show_page(1)
    for _ in range(8):
        app.processEvents()
    _grab(win, "04_dashboard.png", app)

    # 5) Einstellungen (lokales Backend)
    from stonebook.gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(win)
    dlg.backend_combo.setCurrentIndex(1)
    dlg._toggle_backend()
    for _ in range(4):
        app.processEvents()
    _grab(dlg, "05_einstellungen_lokal.png", app, size=(640, 540))

    conn.close()
    print("Fertig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
