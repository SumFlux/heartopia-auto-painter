from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget

from heartopia_app.ui.pages.convert_page import ConvertPage
from heartopia_app.ui.pages.calibration_page import CalibrationPage
from heartopia_app.ui.pages.paint_page import PaintPage
from heartopia_app.ui.pages.settings_page import SettingsPage

if TYPE_CHECKING:
    from heartopia_app.application import ConversionService, WorkspaceState
    from heartopia_app.infrastructure import CalibrationRepository, SessionRepository, SettingsRepository


class MainWindow(QMainWindow):
    def __init__(
        self,
        state: WorkspaceState,
        conversion_service: ConversionService,
        settings_repository: SettingsRepository,
        calibration_repository: CalibrationRepository,
        session_repository: SessionRepository,
    ):
        super().__init__()
        self.state = state
        self.conversion_service = conversion_service
        self.settings_repository = settings_repository
        self.calibration_repository = calibration_repository
        self.session_repository = session_repository

        self.setWindowTitle("Heartopia Auto Painter")
        self.setMinimumSize(1100, 800)
        self.resize(1280, 900)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.setCentralWidget(self.tabs)

        self.convert_page = ConvertPage(
            state=self.state,
            conversion_service=self.conversion_service,
        )
        self.calibration_page = CalibrationPage(
            state=self.state,
            calibration_repository=self.calibration_repository,
        )
        self.paint_page = PaintPage(
            state=self.state,
            session_repository=self.session_repository,
        )
        self.settings_page = SettingsPage(
            state=self.state,
            settings_repository=self.settings_repository,
        )

        self.tabs.addTab(self.convert_page, "转换")
        self.tabs.addTab(self.calibration_page, "标定")
        self.tabs.addTab(self.paint_page, "绘画")
        self.tabs.addTab(self.settings_page, "设置")
