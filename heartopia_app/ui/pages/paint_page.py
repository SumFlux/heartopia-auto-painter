from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QObject
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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heartopia_app.application import CalibrationService, WorkspaceState
    from heartopia_app.infrastructure import CalibrationRepository, SessionRepository


SPEED_MAP = {
    0: 'very_slow',
    1: 'slow',
    2: 'normal',
    3: 'fast',
}


class _Signals(QObject):
    """Thread-safe Qt signals for cross-thread communication."""
    log = Signal(str)
    progress = Signal(int, int)
    color_change = Signal(str, int, int)
    finished = Signal()
    error = Signal(str)


class PaintPage(QWidget):
    def __init__(
        self,
        state: WorkspaceState,
        session_repository: SessionRepository,
        calibration_service: CalibrationService,
        calibration_repository: CalibrationRepository,
    ):
        super().__init__()
        self.state = state
        self.session_repository = session_repository
        self.calibration_service = calibration_service
        self.calibration_repository = calibration_repository
        self._session = None  # PaintSession instance
        self._hotkey_listener = None

        self._signals = _Signals()
        self._signals.log.connect(self._log)
        self._signals.progress.connect(self._on_progress)
        self._signals.color_change.connect(self._on_color_change)
        self._signals.finished.connect(self._on_finished)
        self._signals.error.connect(self._on_error)

        self._setup_ui()
        self._update_ui_state()
        self._setup_hotkeys()

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
        self.bucket_fill_cb.setToolTip("启用后，需要先标定工具栏（画笔+油漆桶位置）")
        self.bucket_fill_cb.setChecked(False)
        ctrl_layout.addWidget(self.bucket_fill_cb, 1, 0, 1, 2)

        self.start_btn = QPushButton("▶ 开始画画 (F5)")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_painting)
        ctrl_layout.addWidget(self.start_btn, 2, 0)

        self.pause_btn = QPushButton("⏸ 暂停 (F6)")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._pause_painting)
        ctrl_layout.addWidget(self.pause_btn, 2, 1)

        self.stop_btn = QPushButton("⏹ 停止 (F7)")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_painting)
        ctrl_layout.addWidget(self.stop_btn, 3, 0)

        self.resume_btn = QPushButton("↻ 断点续画")
        self.resume_btn.setEnabled(False)
        self.resume_btn.setToolTip("从上次中断的位置继续绘画")
        self.resume_btn.clicked.connect(self._resume_painting)
        ctrl_layout.addWidget(self.resume_btn, 3, 1)

        # Manual pixel offset for resume
        resume_offset_row = QHBoxLayout()
        resume_offset_row.addWidget(QLabel("起始像素:"))
        self.resume_offset_spin = QSpinBox()
        self.resume_offset_spin.setRange(0, 0)
        self.resume_offset_spin.setValue(0)
        self.resume_offset_spin.setToolTip("手动指定断点续画的起始像素编号（0 表示从头开始）")
        resume_offset_row.addWidget(self.resume_offset_spin)
        resume_offset_row.addStretch()
        ctrl_layout.addLayout(resume_offset_row, 4, 0, 1, 2)

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
        is_running = self._session is not None and self._session.is_running

        can_start = has_data and has_canvas and has_palette and not is_running
        self.start_btn.setEnabled(can_start)
        self.pause_btn.setEnabled(is_running)
        self.stop_btn.setEnabled(is_running)

        # Check for saved progress
        saved = self.session_repository.load()
        self.resume_btn.setEnabled(can_start)

        # Update resume offset SpinBox
        if has_data:
            from heartopia_app.domain.paint_plan import build_paint_plan
            try:
                plan = build_paint_plan(self.state.pixel_data)
                self.resume_offset_spin.setRange(0, plan.total_pixels)
            except Exception:
                pass
            if saved:
                self.resume_offset_spin.setValue(saved.get("drawn_pixels", 0))
        else:
            self.resume_offset_spin.setRange(0, 0)
            self.resume_offset_spin.setValue(0)

        if has_data:
            pd = self.state.pixel_data
            ratio_str = pd.ratio or "unknown"
            self.data_label.setText(f"已加载: {pd.grid_width}x{pd.grid_height} ({ratio_str})")
        else:
            self.data_label.setText("未加载数据")

    def _log(self, text: str) -> None:
        self.log_text.append(text)
        self.log_text.ensureCursorVisible()

    def _setup_hotkeys(self) -> None:
        """Setup F5/F6/F7 hotkeys using pynput."""
        try:
            from pynput.keyboard import Key, Listener

            def on_press(key):
                try:
                    if key == Key.f5:
                        if self._session and self._session.is_running and self._session.is_paused:
                            self._session.resume()
                            self._signals.log.emit("[热键] F5 - 继续绘画")
                        elif not (self._session and self._session.is_running):
                            self._signals.log.emit("[热键] F5 - 请用按钮开始绘画")
                    elif key == Key.f6:
                        if self._session and self._session.is_running and not self._session.is_paused:
                            self._session.pause()
                            self._signals.log.emit("[热键] F6 - 暂停绘画")
                    elif key == Key.f7:
                        if self._session and self._session.is_running:
                            self._stop_painting_internal()
                            self._signals.log.emit("[热键] F7 - 停止绘画")
                except Exception:
                    pass

            self._hotkey_listener = Listener(on_press=on_press)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as e:
            self._log(f"[WARN] 热键初始化失败: {e}")

    def _get_color_hex(self, group_key: str) -> str:
        """Get hex color string from group_key like '1-0'."""
        try:
            from heartopia_app.domain.palette import COLOR_GROUPS
            if '-' in group_key:
                g_idx, c_idx = group_key.split('-')
                g_idx, c_idx = int(g_idx), int(c_idx)
                if 0 <= g_idx < len(COLOR_GROUPS):
                    _, colors = COLOR_GROUPS[g_idx]
                    if 0 <= c_idx < len(colors):
                        return colors[c_idx]
        except Exception:
            pass
        return "#999999"

    # ----- Import -----

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
                self._log(f"  [!] 数据不含 colorId，将使用最近邻匹配")

            # Auto-apply fixed positions if matching ratio profile exists
            self._try_auto_apply_fixed_positions()

            self._update_ui_state()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败:\n{e}")
            self._log(f"[ERROR] 导入失败: {e}")

    def _try_auto_apply_fixed_positions(self) -> None:
        """Try to auto-apply fixed positions matching the imported pixel data's ratio."""
        try:
            import json as _json
            fixed_path = self.state.app_data_dir / "fixed_positions.json"
            if not fixed_path.exists():
                return

            ratio = self.state.pixel_data.ratio if self.state.pixel_data else ""
            if not ratio:
                return

            with fixed_path.open("r", encoding="utf-8") as f:
                fixed_data = _json.load(f)

            canvas_profiles = fixed_data.get("canvas_profiles", {})
            if ratio not in canvas_profiles:
                return

            from heartopia_app.infrastructure.window_backend import find_game_window, get_window_rect
            hwnd = find_game_window()
            if hwnd is None:
                return
            rect = get_window_rect(hwnd)
            if rect is None:
                return

            window_offset = (rect[0], rect[1])

            from heartopia_app.domain.calibration import CanvasCalibration, PaletteCalibration, ToolbarCalibration

            self.state.canvas_calibration = CanvasCalibration.from_window_relative(
                window_offset, canvas_profiles[ratio]
            )
            # Sync grid dimensions from pixel_data (fixed positions may store stale grid size)
            if self.state.pixel_data:
                pw, ph = self.state.pixel_data.grid_width, self.state.pixel_data.grid_height
                cc = self.state.canvas_calibration
                if (cc.grid_width, cc.grid_height) != (pw, ph):
                    self._log(f"  [同步] 网格尺寸: {cc.grid_width}x{cc.grid_height} → {pw}x{ph}")
                    cc.grid_width = pw
                    cc.grid_height = ph
            self._log(f"  [自动应用] 画布固定坐标已匹配比例 {ratio}")

            if "palette" in fixed_data:
                self.state.palette_calibration = PaletteCalibration.from_window_relative(
                    window_offset, fixed_data["palette"]
                )
                self._log(f"  [自动应用] 调色板固定坐标已应用")
            if "toolbar" in fixed_data:
                self.state.toolbar_calibration = ToolbarCalibration.from_window_relative(
                    window_offset, fixed_data["toolbar"]
                )
                self._log(f"  [自动应用] 工具栏固定坐标已应用")

            self.calibration_repository.save(
                self.state.canvas_calibration,
                self.state.palette_calibration,
                self.state.toolbar_calibration,
            )
        except Exception as e:
            self._log(f"  [!] 自动应用固定坐标失败: {e}")

    # ----- Paint controls -----

    def _create_session(self):
        """Create a new PaintSession."""
        from heartopia_app.application.paint_session import PaintSession
        from heartopia_app.domain.paint_plan import build_paint_plan

        backend = self.state.input_backend
        if backend is None:
            raise RuntimeError("输入后端未初始化")

        plan = build_paint_plan(self.state.pixel_data)
        if plan.total_pixels == 0:
            raise RuntimeError("没有需要绘制的像素（全部是背景色？）")

        session = PaintSession(
            canvas=self.state.canvas_calibration,
            palette=self.state.palette_calibration,
            toolbar=self.state.toolbar_calibration,
            backend=backend,
        )
        session.load_plan(plan)

        # Set speed
        speed_name = SPEED_MAP.get(self.speed_combo.currentIndex(), 'normal')
        session.set_speed(speed_name)

        # Wire callbacks via signals
        session.on_progress = self._signals.progress.emit
        session.on_color_change = self._signals.color_change.emit
        session.on_finished = self._signals.finished.emit
        session.on_error = self._signals.error.emit

        return session, plan

    def _start_painting(self) -> None:
        try:
            self._session, plan = self._create_session()
            self._log(f"[开始绘画] 共 {plan.total_pixels} 像素, {len(plan.groups)} 种颜色")
            self._log(f"  速度: {SPEED_MAP.get(self.speed_combo.currentIndex(), 'normal')}")

            self.progress_bar.setMaximum(plan.total_pixels)
            self.progress_bar.setValue(0)

            self._session.start()
            self._update_ui_state()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动绘画失败:\n{e}")
            self._log(f"[ERROR] {e}")

    def _pause_painting(self) -> None:
        if self._session and self._session.is_running:
            if self._session.is_paused:
                self._session.resume()
                self.pause_btn.setText("⏸ 暂停 (F6)")
                self._log("[继续] 绘画已继续")
            else:
                self._session.pause()
                self.pause_btn.setText("▶ 继续 (F6)")
                self._log("[暂停] 绘画已暂停")

    def _stop_painting_internal(self) -> None:
        """Stop painting and save progress (can be called from any thread)."""
        if self._session and self._session.is_running:
            progress = self._session.stop()
            if progress.drawn_pixels > 0:
                self.session_repository.save(progress.to_dict())

    def _stop_painting(self) -> None:
        if self._session and self._session.is_running:
            progress = self._session.stop()
            if progress.drawn_pixels > 0:
                self.session_repository.save(progress.to_dict())
                self._log(f"[停止] 进度已保存 ({progress.drawn_pixels} 像素)")
            else:
                self._log("[停止] 绘画已停止")
            self._session = None
            self.pause_btn.setText("⏸ 暂停 (F6)")
            self._update_ui_state()

    def _resume_painting(self) -> None:
        try:
            from heartopia_app.application.paint_session import PaintProgress

            self._session, plan = self._create_session()

            pixel_offset = self.resume_offset_spin.value()
            resume_progress = PaintProgress.from_pixel_offset(plan, pixel_offset)

            self._log(f"[断点续画] 从第 {pixel_offset} 像素处继续")

            self.progress_bar.setMaximum(plan.total_pixels)
            self.progress_bar.setValue(resume_progress.drawn_pixels)

            self._session.start(resume_progress=resume_progress)
            self._update_ui_state()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"断点续画失败:\n{e}")
            self._log(f"[ERROR] {e}")

    # ----- Callbacks -----

    def _on_progress(self, drawn: int, total: int) -> None:
        self.progress_bar.setValue(drawn)
        pct = drawn * 100 // total if total > 0 else 0
        self.prog_label.setText(f"当前进度: {drawn}/{total} ({pct}%)")

    def _on_color_change(self, group_key: str, idx: int, total: int) -> None:
        hex_color = self._get_color_hex(group_key)
        self.color_label.setText(f"当前颜色: {group_key} ({idx}/{total})")
        self.preview_box.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #999;"
        )

    def _on_finished(self) -> None:
        self._log("[完成] 绘画已全部完成！🎉")
        self.session_repository.clear()
        self._session = None
        self.pause_btn.setText("⏸ 暂停 (F6)")
        self._update_ui_state()
        QMessageBox.information(self, "完成", "绘画已全部完成！")

    def _on_error(self, msg: str) -> None:
        self._log(f"[ERROR] {msg}")
        self._session = None
        self.pause_btn.setText("⏸ 暂停 (F6)")
        self._update_ui_state()
        QMessageBox.critical(self, "绘画错误", msg)
