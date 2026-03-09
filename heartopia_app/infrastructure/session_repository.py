from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .constants import SESSION_FILE_NAME


class SessionRepository:
    def __init__(self, app_data_dir: Path):
        self.path = app_data_dir / SESSION_FILE_NAME

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, data: Dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
