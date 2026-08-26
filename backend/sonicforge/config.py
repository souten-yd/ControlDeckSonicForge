from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def _path_env(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


def _control_deck_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("ControlDeck URL must be an HTTP(S) origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("ControlDeck URL must not contain a path, query, or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("plain HTTP ControlDeck URL must be loopback")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    data_dir: Path
    cache_dir: Path
    repo_root: Path
    ui_locale: str
    enable_fake_worker: bool
    setup_test_mode: bool
    control_deck_url: str

    @property
    def db_path(self) -> Path: return self.data_dir / "sonicforge.db"
    @property
    def assets_dir(self) -> Path: return self.data_dir / "assets"
    @property
    def runtime_dir(self) -> Path: return self.data_dir / "runtime-state"
    @property
    def models_dir(self) -> Path: return self.data_dir / "models"
    @property
    def logs_dir(self) -> Path: return self.data_dir / "logs"


def load_settings() -> Settings:
    feature_data = os.environ.get("CONTROL_DECK_FEATURE_DATA_DIR")
    default_data = Path(feature_data) if feature_data else Path.home() / ".local/share/control-deck-sonic-forge"
    shared_cache = os.environ.get("CONTROL_DECK_SHARED_CACHE_DIR")
    default_cache = (Path(shared_cache) / "sonic-forge") if shared_cache else Path.home() / ".cache/control-deck-sonic-forge"
    data = _path_env("SONICFORGE_DATA_DIR", default_data)
    cache = _path_env("SONICFORGE_CACHE_DIR", default_cache)
    return Settings(
        host=os.environ.get("SONICFORGE_HOST", "127.0.0.1"),
        port=int(os.environ.get("SONICFORGE_PORT", "9140")),
        data_dir=data,
        cache_dir=cache,
        repo_root=REPOSITORY_ROOT.resolve(),
        ui_locale=os.environ.get("SONICFORGE_UI_LOCALE", "auto"),
        enable_fake_worker=os.environ.get("SONICFORGE_ENABLE_FAKE", "0") == "1",
        setup_test_mode=os.environ.get("SONICFORGE_SETUP_TEST_MODE", "0") == "1",
        control_deck_url=_control_deck_origin(os.environ.get("SONICFORGE_CONTROLDECK_URL", os.environ.get("CONTROL_DECK_BASE_URL", "http://127.0.0.1:8765"))),
    )


def ensure_directories(settings: Settings) -> None:
    for path in (settings.data_dir, settings.cache_dir, settings.assets_dir, settings.runtime_dir, settings.models_dir, settings.logs_dir, settings.data_dir / "tmp", settings.data_dir / "voices"):
        path.mkdir(parents=True, exist_ok=True)
