"""Pfade, Repo-Root-Erkennung und App-Einstellungen."""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings

ORG = "G4MEOVER"
APP = "StoneBook"

KEYRING_SERVICE = "StoneBook"
KEYRING_USER = "anthropic_api_key"
KEYRING_USER_LOCAL = "local_api_key"

DEFAULT_MODEL = "claude-sonnet-4-6"
AVAILABLE_MODELS = ["claude-sonnet-4-6", "claude-opus-4-7"]

# KI-Backends
BACKEND_ANTHROPIC = "anthropic"
BACKEND_LOCAL = "local"

# Vorlagen für lokale/OpenAI-kompatible Endpunkte (Base-URL, Beispielmodell)
LOCAL_PRESETS = {
    "Ollama (lokal)": ("http://localhost:11434/v1", "gemma3:27b"),
    "Open-WebUI": ("http://localhost:3000/api", "gemma3:27b"),
    "LM Studio": ("http://localhost:1234/v1", "local-model"),
    "OpenClaw-Gateway / KI-Core": ("http://192.168.0.14:18789/v1", "openclaw/main"),
    "Benutzerdefiniert": ("", ""),
}


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


# --- KI-Backend ---------------------------------------------------------

def get_backend() -> str:
    return str(settings().value("ai_backend", BACKEND_ANTHROPIC))


def set_backend(backend: str) -> None:
    settings().setValue("ai_backend", backend)


def get_local_base_url() -> str:
    return str(settings().value("ai_local_base_url", "http://localhost:11434/v1"))


def set_local_base_url(url: str) -> None:
    settings().setValue("ai_local_base_url", url)


def get_local_model() -> str:
    return str(settings().value("ai_local_model", "gemma3:27b"))


def set_local_model(model: str) -> None:
    settings().setValue("ai_local_model", model)


def get_local_api_key() -> str:
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER_LOCAL) or ""
    except Exception:
        return ""


def set_local_api_key(key: str) -> None:
    import keyring
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER_LOCAL, key)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USER_LOCAL)
        except Exception:
            pass


def get_timeout() -> float:
    return float(settings().value("ai_timeout", 180))


def set_timeout(seconds: float) -> None:
    settings().setValue("ai_timeout", seconds)


def ai_is_configured() -> bool:
    """True, wenn das aktuell gewählte Backend nutzbar konfiguriert ist."""
    if get_backend() == BACKEND_LOCAL:
        return bool(get_local_base_url() and get_local_model())
    return bool(get_api_key())


def build_provider():
    """Erzeugt den konfigurierten Provider (oder wirft bei fehlender Konfiguration)."""
    from stonebook.ai.providers import AnthropicProvider, OpenAICompatProvider
    timeout = get_timeout()
    if get_backend() == BACKEND_LOCAL:
        if not get_local_base_url() or not get_local_model():
            raise RuntimeError("Lokales Backend nicht konfiguriert (Base-URL/Modell fehlt).")
        return OpenAICompatProvider(get_local_base_url(), get_local_model(),
                                    get_local_api_key(), timeout)
    if not get_api_key():
        raise RuntimeError("Kein Anthropic-API-Key hinterlegt.")
    return AnthropicProvider(get_api_key(), get_model(), timeout)


def backend_label() -> str:
    if get_backend() == BACKEND_LOCAL:
        return f"Lokal: {get_local_model()}"
    return f"Claude: {get_model()}"
