from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heartopia_app.application import WorkspaceState
    from heartopia_app.infrastructure import CalibrationRepository


class CalibrationPage(QWidget):
    def __init__(self, state: WorkspaceState, calibration_repository: CalibrationRepository):
        super().__init__()
        self.state = state
        self.calibration_repository = calibration_repository

        self._setup_ui()
        self._update_ui_state()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # 标定控制
        calib_group = QGroupBox("坐标标定")
        calib_layout = QVBoxLayout(calib_group)

        self.calib_canvas_btn = QPushButton("标定画板范围（4 个角，共 4 次 Enter）")
        self.calib_canvas_btn.setToolTip("点击后切回游戏，按 Z 字形依次标定左上→右上→左下→右下四个角")
        self.calib_canvas_btn.clicked.connect(self._start_canvas_calibration)
        calib_layout.addWidget(self.calib_canvas_btn)

        self.auto_detect_btn = QPushButton("🔍 自动检测画布（4角标记点）")
        self.auto_detect_btn.setToolTip("先在游戏画布的4个角各画一个醒目颜色的像素，然后点此自动检测")
        self.auto_detect_btn.clicked.connect(self._auto_detect_canvas)
        calib_layout.addWidget(self.auto_detect_btn)

        self.calib_palette_btn = QPushButton("标定调色板（左右标签 + 色块区域，共 4 次 Enter）")
        self.calib_palette_btn.setToolTip("依次标定：标签最左 -> 标签最右 -> 色块左上第一格 -> 色块右下最后一格")
        self.calib_palette_btn.clicked.connect(self._start_palette_calibration)
        calib_layout.addWidget(self.calib_palette_btn)

        self.calib_toolbar_btn = QPushButton("🔧 标定工具栏（画笔+油漆桶）")
        self.calib_toolbar_btn.setToolTip("标定画笔和油漆桶工具在屏幕上的位置，用于油漆桶填充优化")
        self.calib_toolbar_btn.clicked.connect(self._start_toolbar_calibration)
        calib_layout.addWidget(self.calib_toolbar_btn)

        self.calib_status_label = QLabel("")
        calib_layout.addWidget(self.calib_status_label)

        # 操作按钮行
        btn_row = QHBoxLayout()

        self.recalib_btn = QPushButton("🗑 清除标定（重新标定）")
        self.recalib_btn.setToolTip("清除已保存的标定数据，可以重新标定画布和调色板")
        self.recalib_btn.clicked.connect(self._clear_calibration)
        btn_row.addWidget(self.recalib_btn)

        self.test_calib_btn = QPushButton("🧪 测试标定（画边框）")
        self.test_calib_btn.setToolTip("沿画布最外围画一圈黑红交替边框，验证标定是否准确")
        self.test_calib_btn.clicked.connect(self._test_calibration)
        btn_row.addWidget(self.test_calib_btn)

        calib_layout.addLayout(btn_row)

        # 微调偏移行
        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("微调偏移:"))

        offset_row.addWidget(QLabel("X"))
        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-20, 20)
        self.offset_x_spin.setValue(self.state.canvas_calibration.offset_x)
        self.offset_x_spin.setSuffix(" px")
        self.offset_x_spin.setToolTip("正值=整体右移，负值=整体左移")
        self.offset_x_spin.valueChanged.connect(self._on_offset_changed)
        offset_row.addWidget(self.offset_x_spin)

        offset_row.addWidget(QLabel("Y"))
        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-20, 20)
        self.offset_y_spin.setValue(self.state.canvas_calibration.offset_y)
        self.offset_y_spin.setSuffix(" px")
        self.offset_y_spin.setToolTip("正值=整体下移，负值=整体上移")
        self.offset_y_spin.valueChanged.connect(self._on_offset_changed)
        offset_row.addWidget(self.offset_y_spin)

        self.reset_offset_btn = QPushButton("归零")
        self.reset_offset_btn.setFixedWidth(50)
        self.reset_offset_btn.clicked.connect(self._reset_offset)
        offset_row.addWidget(self.reset_offset_btn)

        offset_row.addStretch()
        calib_layout.addLayout(offset_row)

        main_layout.addWidget(calib_group)

        # 日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        main_layout.addWidget(self.log_text)

        main_layout.addStretch()

    def _update_ui_state(self) -> None:
        has_canvas = self.state.canvas_calibration.calibrated
        has_palette = self.state.palette_calibration.calibrated
        has_toolbar = self.state.toolbar_calibration.calibrated

        self.recalib_btn.setEnabled(has_canvas or has_palette or has_toolbar)
        self.test_calib_btn.setEnabled(has_canvas)

        if has_canvas and has_palette and has_toolbar:
            self.calib_status_label.setText("✅ 画布、调色板、工具栏已标定")
        elif has_canvas and has_palette:
            self.calib_status_label.setText("✅ 画布和调色板已标定")
        elif has_canvas:
            self.calib_status_label.setText("⚠️ 仅画布已标定")
        else:
            self.calib_status_label.setText("❌ 未标定")

    def _log(self, text: str) -> None:
        self.log_text.append(text)
        self.log_text.ensureCursorVisible()

    def _start_canvas_calibration(self) -> None:
        self._log("[TODO] 画布标定功能待实现")
        QMessageBox.information(self, "提示", "画布标定功能待实现")

    def _auto_detect_canvas(self) -> None:
        self._log("[TODO] 自动检测画布功能待实现")
        QMessageBox.information(self, "提示", "自动检测画布功能待实现")

    def _start_palette_calibration(self) -> None:
        self._log("[TODO] 调色板标定功能待实现")
        QMessageBox.information(self, "提示", "调色板标定功能待实现")

    def _start_toolbar_calibration(self) -> None:
        self._log("[TODO] 工具栏标定功能待实现")
        QMessageBox.information(self, "提示", "工具栏标定功能待实现")

    def _clear_calibration(self) -> None:
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要清除所有标定数据吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.state.canvas_calibration.reset()
            self.state.palette_calibration.reset()
            self.state.toolbar_calibration.reset()
            self.calibration_repository.save(
                self.state.canvas_calibration,
                self.state.palette_calibration,
                self.state.toolbar_calibration,
            )
            self._update_ui_state()
            self._log("[OK] 已清除所有标定数据")

    def _test_calibration(self) -> None:
        self._log("[TODO] 测试标定功能待实现")
        QMessageBox.information(self, "提示", "测试标定功能待实现")

    def _on_offset_changed(self) -> None:
        self.state.canvas_calibration.offset_x = self.offset_x_spin.value()
        self.state.canvas_calibration.offset_y = self.offset_y_spin.value()
        self.calibration_repository.save(
            self.state.canvas_calibration,
            self.state.palette_calibration,
            self.state.toolbar_calibration,
        )
        self._log(f"[OK] 偏移已更新: X={self.state.canvas_calibration.offset_x}, Y={self.state.canvas_calibration.offset_y}")

    def _reset_offset(self) -> None:
        self.offset_x_spin.setValue(0)
        self.offset_y_spin.setValue(0)
