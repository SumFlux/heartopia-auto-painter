from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication

from heartopia_app.application import ConversionService, WorkspaceState
from heartopia_app.infrastructure import CalibrationRepository, SessionRepository, SettingsRepository, ensure_app_data_dir
from heartopia_app.ui.main_window import MainWindow


@dataclass
class BootstrapContext:
    app: QApplication
    state: WorkspaceState
    settings_repository: SettingsRepository
    calibration_repository: CalibrationRepository
    session_repository: SessionRepository
    conversion_service: ConversionService
    main_window: MainWindow


def _configure_runtime(auto_hide_console: bool = False, request_admin_on_launch: bool = False) -> None:
    try:
        import ctypes

        if request_admin_on_launch:
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            except Exception:
                is_admin = False
            if not is_admin:
                try:
                    # 使用 -m heartopia_app 来重新启动，而不是直接传 __main__.py
                    ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "runas",
                        sys.executable,
                        "-m heartopia_app",
                        None,
                        1,
                    )
                except Exception:
                    pass
                sys.exit(0)

        if auto_hide_console:
            try:
                hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd_console:
                    ctypes.windll.user32.ShowWindow(hwnd_console, 0)
            except Exception:
                pass

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    except Exception:
        pass

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")


def create_application() -> BootstrapContext:
    app_data_dir = ensure_app_data_dir()
    settings_repository = SettingsRepository(app_data_dir)
    calibration_repository = CalibrationRepository(app_data_dir)
    session_repository = SessionRepository(app_data_dir)
    settings = settings_repository.load()

    _configure_runtime(
        auto_hide_console=settings.auto_hide_console,
        request_admin_on_launch=settings.request_admin_on_launch,
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    state = WorkspaceState(app_data_dir=app_data_dir, settings=settings)
    canvas, palette, toolbar = calibration_repository.load()
    state.canvas_calibration = canvas
    state.palette_calibration = palette
    state.toolbar_calibration = toolbar

    conversion_service = ConversionService()
    main_window = MainWindow(
        state=state,
        conversion_service=conversion_service,
        settings_repository=settings_repository,
        calibration_repository=calibration_repository,
        session_repository=session_repository,
    )

    return BootstrapContext(
        app=app,
        state=state,
        settings_repository=settings_repository,
        calibration_repository=calibration_repository,
        session_repository=session_repository,
        conversion_service=conversion_service,
        main_window=main_window,
    )
