from __future__ import annotations

import os
from pathlib import Path

from .constants import APP_DIR_NAME


def ensure_app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    app_dir = base / APP_DIR_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir
