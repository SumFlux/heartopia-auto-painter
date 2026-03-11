from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

from heartopia_app.domain import CanvasCalibration, PaletteCalibration, ToolbarCalibration

from .constants import CALIBRATION_FILE_NAME


class CalibrationRepository:
    def __init__(self, app_data_dir: Path):
        self.path = app_data_dir / CALIBRATION_FILE_NAME

    def load(self) -> Tuple[CanvasCalibration, PaletteCalibration, ToolbarCalibration]:
        if not self.path.exists():
            return CanvasCalibration(), PaletteCalibration(), ToolbarCalibration()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        canvas = CanvasCalibration.from_dict(data["canvas"]) if data.get("canvas") else CanvasCalibration()
        palette = PaletteCalibration.from_dict(data["palette"]) if data.get("palette") else PaletteCalibration()
        toolbar = ToolbarCalibration.from_dict(data["toolbar"]) if data.get("toolbar") else ToolbarCalibration()
        return canvas, palette, toolbar

    def save(self, canvas: CanvasCalibration, palette: PaletteCalibration, toolbar: ToolbarCalibration) -> None:
        payload = {
            "canvas": canvas.to_dict() if canvas.calibrated else None,
            "palette": palette.to_dict() if palette.calibrated else None,
            "toolbar": toolbar.to_dict() if toolbar.calibrated else None,
        }
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
