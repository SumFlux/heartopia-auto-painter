from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from heartopia_app.application.app_state import AppSettings

from .constants import SETTINGS_FILE_NAME


class SettingsRepository:
    def __init__(self, app_data_dir: Path):
        self.path = app_data_dir / SETTINGS_FILE_NAME

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        settings = AppSettings()
        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        return settings

    def save(self, settings: AppSettings) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(settings), handle, indent=2, ensure_ascii=False)
