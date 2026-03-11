from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from heartopia_app.domain import CanvasCalibration, PaletteCalibration, PixelData, ToolbarCalibration

if TYPE_CHECKING:
    from heartopia_app.infrastructure.input_backend import InputBackend


@dataclass
class AppSettings:
    input_backend: str = "pynput"
    auto_hide_console: bool = False
    request_admin_on_launch: bool = False
    default_open_dir: str = ""
    default_export_dir: str = ""
    last_image_path: str = ""
    last_pixel_data_path: str = ""


@dataclass
class WorkspaceState:
    app_data_dir: Path
    settings: AppSettings = field(default_factory=AppSettings)
    pixel_data: Optional[PixelData] = None
    pixel_data_path: Optional[Path] = None
    source_image_path: Optional[Path] = None
    canvas_calibration: CanvasCalibration = field(default_factory=CanvasCalibration)
    palette_calibration: PaletteCalibration = field(default_factory=PaletteCalibration)
    toolbar_calibration: ToolbarCalibration = field(default_factory=ToolbarCalibration)
    input_backend: Optional[InputBackend] = None
    active_session_path: Optional[Path] = None

    @property
    def has_pixel_data(self) -> bool:
        return self.pixel_data is not None

    @property
    def is_paint_ready(self) -> bool:
        return self.has_pixel_data and self.canvas_calibration.calibrated and self.palette_calibration.calibrated
