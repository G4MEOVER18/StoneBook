"""Pfade, Repo-Root-Erkennung und App-Einstellungen."""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings

ORG = "G4MEOVER"
APP = "StoneBook"

KEYRING_SERVICE = "StoneBook"
KEYRING_USER = "anthropic_api_key"

DEFAULT_MODEL = "claude-sonnet-4-6"
AVAILABLE_MODELS = ["claude-sonnet-4-6", "claude-opus-4-7"]


def settings() -> QSettings:
    return QSettings(ORG, APP)


def _dev_repo_root() -> Path | None:
    # Paketlage: <repo>\app\stonebook\config.py
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "objects").is_dir() and (candidate / "data").is_dir():
        return candidate
    return None


def repo_root() -> Path | None:
    """Repo-Root: im Dev-Modus aus der Paketlage, sonst aus QSettings."""
    if not getattr(sys, "frozen", False):
        dev = _dev_repo_root()
        if dev:
            return dev
    stored = settings().value("repo_root", "")
    if stored:
        p = Path(stored)
        if (p / "objects").is_dir():
            return p
    return None


def set_repo_root(path: Path) -> None:
    settings().setValue("repo_root", str(path))


def db_path(root: Path) -> Path:
    return root / "data" / "db" / "stonebook.sqlite3"


def thumbs_dir(root: Path) -> Path:
    return root / "data" / "thumbs"


def resources_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "stonebook" / "resources"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "resources"


def get_api_key() -> str:
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
    except Exception:
        return ""


def set_api_key(key: str) -> None:
    import keyring
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        except Exception:
            pass


def get_model() -> str:
    return str(settings().value("ai_model", DEFAULT_MODEL))


def set_model(model: str) -> None:
    settings().setValue("ai_model", model)


def get_max_images() -> int:
    return int(settings().value("ai_max_images", 6))


def set_max_images(n: int) -> None:
    settings().setValue("ai_max_images", n)
