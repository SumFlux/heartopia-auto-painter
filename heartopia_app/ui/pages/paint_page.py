from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heartopia_app.application import WorkspaceState
    from heartopia_app.infrastructure import SessionRepository


class PaintPage(QWidget):
    def __init__(self, state: WorkspaceState, session_repository: SessionRepository):
        super().__init__()
        self.state = state
        self.session_repository = session_repository

        self._setup_ui()
        self._update_ui_state()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # 数据导入
        data_group = QGroupBox("1. 像素数据导入")
        data_layout = QGridLayout(data_group)

        self.import_btn = QPushButton("导入 JSON 文件")
        self.import_btn.clicked.connect(self._import_json)
        data_layout.addWidget(self.import_btn, 0, 0)

        self.data_label = QLabel("未加载数据")
        data_layout.addWidget(self.data_label, 0, 1)
        main_layout.addWidget(data_group)

        # 画画控制
        ctrl_group = QGroupBox("2. 画画控制")
        ctrl_layout = QGridLayout(ctrl_group)

        ctrl_layout.addWidget(QLabel("绘画速度:"), 0, 0)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([
            "极慢 (200ms) - 安全稳定",
            "慢速 (100ms)",
            "正常 (50ms)",
            "快速 (20ms)"
        ])
        self.speed_combo.setCurrentIndex(2)
        ctrl_layout.addWidget(self.speed_combo, 0, 1)

        self.bucket_fill_cb = QCheckBox("🪣 油漆桶填充（大面积同色区域自动填充）")
        self.bucket_fill_cb.setToolTip("启用后，连通区域 ≥ 50 像素时先画边界再油漆桶填充")
        self.bucket_fill_cb.setChecked(False)
        ctrl_layout.addWidget(self.bucket_fill_cb, 1, 0, 1, 2)

        self.start_btn = QPushButton(">> 开始画画 (F5)")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_painting)
        ctrl_layout.addWidget(self.start_btn, 2, 0)

        self.pause_btn = QPushButton("|| 暂停 (F6)")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._pause_painting)
        ctrl_layout.addWidget(self.pause_btn, 2, 1)

        self.resume_btn = QPushButton("~ 断点续画")
        self.resume_btn.setEnabled(False)
        self.resume_btn.setToolTip("从上次中断的位置继续绘画")
        self.resume_btn.clicked.connect(self._resume_painting)
        ctrl_layout.addWidget(self.resume_btn, 3, 0, 1, 2)

        main_layout.addWidget(ctrl_group)

        # 进度
        prog_group = QGroupBox("3. 进度")
        prog_layout = QVBoxLayout(prog_group)

        self.prog_label = QLabel("当前进度: 0/0")
        prog_layout.addWidget(self.prog_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #4CAF50; }"
        )
        prog_layout.addWidget(self.progress_bar)

        color_row = QHBoxLayout()
        self.color_label = QLabel("当前颜色: 无")
        color_row.addWidget(self.color_label)

        self.preview_box = QLabel()
        self.preview_box.setFixedSize(30, 30)
        self.preview_box.setStyleSheet("background-color: transparent; border: 1px solid #999;")
        color_row.addWidget(self.preview_box)
        color_row.addStretch()

        prog_layout.addLayout(color_row)
        main_layout.addWidget(prog_group)

        # 日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(160)
        main_layout.addWidget(self.log_text)

    def _update_ui_state(self) -> None:
        has_data = self.state.pixel_data is not None
        has_canvas = self.state.canvas_calibration.calibrated
        has_palette = self.state.palette_calibration.calibrated

        can_start = has_data and has_canvas and has_palette
        self.start_btn.setEnabled(can_start)

        if has_data:
            pd = self.state.pixel_data
            ratio_str = pd.ratio or "unknown"
            self.data_label.setText(f"已加载: {pd.grid_width}x{pd.grid_height} ({ratio_str})")
        else:
            self.data_label.setText("未加载数据")

    def _log(self, text: str) -> None:
        self.log_text.append(text)
        self.log_text.ensureCursorVisible()

    def _import_json(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择像素矩阵 JSON", "", "JSON (*.json)"
        )
        if not file_path:
            return

        try:
            from heartopia_app.domain import PixelData
            self.state.pixel_data = PixelData.from_json_file(file_path)
            self.state.pixel_data_path = Path(file_path)

            ratio_str = self.state.pixel_data.ratio or "unknown"
            self._log(f"[OK] 成功导入 {self.state.pixel_data.grid_width}x{self.state.pixel_data.grid_height} 像素数据 (比例: {ratio_str})")

            if self.state.pixel_data.has_color_ids():
                self._log(f"  [OK] 数据包含 colorId，将使用精确定位")
            else:
                self._log(f"  [!] 数据不含 colorId，将使用最近邻匹配（可能有偏差）")

            self._update_ui_state()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败:\n{e}")
            self._log(f"[ERROR] 导入失败: {e}")

    def _start_painting(self) -> None:
        self._log("[TODO] 开始绘画功能待实现")
        QMessageBox.information(self, "提示", "开始绘画功能待实现")

    def _pause_painting(self) -> None:
        self._log("[TODO] 暂停绘画功能待实现")
        QMessageBox.information(self, "提示", "暂停绘画功能待实现")

    def _resume_painting(self) -> None:
        self._log("[TODO] 断点续画功能待实现")
        QMessageBox.information(self, "提示", "断点续画功能待实现")
