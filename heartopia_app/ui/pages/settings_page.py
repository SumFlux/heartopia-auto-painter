from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heartopia_app.application import WorkspaceState
    from heartopia_app.infrastructure import SettingsRepository


class SettingsPage(QWidget):
    def __init__(self, state: WorkspaceState, settings_repository: SettingsRepository):
        super().__init__()
        self.state = state
        self.settings_repository = settings_repository

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # 运行时设置
        runtime_group = QGroupBox("运行时设置")
        runtime_layout = QVBoxLayout(runtime_group)

        self.auto_hide_console_cb = QCheckBox("自动隐藏控制台窗口")
        self.auto_hide_console_cb.setChecked(self.state.settings.auto_hide_console)
        self.auto_hide_console_cb.setToolTip("启动时自动隐藏控制台窗口（需要重启生效）")
        runtime_layout.addWidget(self.auto_hide_console_cb)

        self.request_admin_cb = QCheckBox("启动时请求管理员权限")
        self.request_admin_cb.setChecked(self.state.settings.request_admin_on_launch)
        self.request_admin_cb.setToolTip("某些输入模拟功能可能需要管理员权限（需要重启生效）")
        runtime_layout.addWidget(self.request_admin_cb)

        main_layout.addWidget(runtime_group)

        # 保存按钮
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self._save_settings)
        main_layout.addWidget(save_btn)

        # 信息
        info_label = QLabel(f"应用数据目录: {self.state.app_data_dir}")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        main_layout.addWidget(info_label)

        main_layout.addStretch()

    def _save_settings(self) -> None:
        self.state.settings.auto_hide_console = self.auto_hide_console_cb.isChecked()
        self.state.settings.request_admin_on_launch = self.request_admin_cb.isChecked()

        try:
            self.settings_repository.save(self.state.settings)
            QMessageBox.information(self, "成功", "设置已保存，部分设置需要重启应用后生效")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败:\n{e}")
