"""Anwendungsstart: QApplication, Repo-Root-Ermittlung, Hauptfenster."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from stonebook import config
from stonebook.db.database import open_db


def _ask_repo_root() -> Path | None:
    QMessageBox.information(
        None, "StoneBook",
        "Bitte den StoneBook-Repo-Ordner wählen\n"
        "(der Ordner, der 'objects' und 'data' enthält).")
    while True:
        chosen = QFileDialog.getExistingDirectory(None, "StoneBook-Repo-Ordner wählen")
        if not chosen:
            return None
        p = Path(chosen)
        if (p / "objects").is_dir():
            config.set_repo_root(p)
            return p
        QMessageBox.warning(None, "StoneBook",
                            f"'{chosen}' enthält keinen 'objects'-Ordner.")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("StoneBook")
    app.setOrganizationName(config.ORG)

    root = config.repo_root()
    if root is None:
        root = _ask_repo_root()
        if root is None:
            return 1

    conn = open_db(config.db_path(root))

    from stonebook.gui.main_window import MainWindow
    win = MainWindow(conn, root)
    win.show()
    return app.exec()
