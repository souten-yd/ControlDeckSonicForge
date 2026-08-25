from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _path_env(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


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
    repo_root = Path(__file__).resolve().parents[2]
    data = _path_env("SONICFORGE_DATA_DIR", Path.home() / ".local/share/control-deck-sonic-forge")
    cache = _path_env("SONICFORGE_CACHE_DIR", Path.home() / ".cache/control-deck-sonic-forge")
    return Settings(
        host=os.environ.get("SONICFORGE_HOST", "127.0.0.1"),
        port=int(os.environ.get("SONICFORGE_PORT", "9140")),
        data_dir=data, cache_dir=cache, repo_root=repo_root,
        ui_locale=os.environ.get("SONICFORGE_UI_LOCALE", "auto"),
        enable_fake_worker=os.environ.get("SONICFORGE_ENABLE_FAKE", "0") == "1",
        setup_test_mode=os.environ.get("SONICFORGE_SETUP_TEST_MODE", "0") == "1",
        control_deck_url=os.environ.get("SONICFORGE_CONTROLDECK_URL", "http://127.0.0.1:8765"),
    )


def ensure_directories(settings: Settings) -> None:
    for path in (settings.data_dir, settings.cache_dir, settings.assets_dir, settings.runtime_dir, settings.models_dir, settings.logs_dir):
        path.mkdir(parents=True, exist_ok=True)
