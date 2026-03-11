from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heartopia_app.application import CalibrationService, VerificationResult, WorkspaceState
    from heartopia_app.infrastructure import CalibrationRepository, SessionRepository


SPEED_MAP = {
    0: 'very_slow',
    1: 'slow',
    2: 'normal',
    3: 'fast',
}


@dataclass
class _PaintRunContext:
    mode: str = "main"
    clear_session_on_success: bool = True
    final_message: str = "绘画已全部完成！"


class _Signals(QObject):
    """Thread-safe Qt signals for cross-thread communication."""
    log = Signal(str)
    progress = Signal(int, int)
    color_change = Signal(str, int, int)
    finished = Signal()
    error = Signal(str)


class VerificationThread(QThread):
    finished = Signal(object, object, object)
    error = Signal(str)

    def __init__(self, pixel_data, canvas_calibration):
        super().__init__()
        self.pixel_data = pixel_data
        self.canvas_calibration = canvas_calibration

    def run(self):
        try:
            from heartopia_app.application import build_annotated_verification_image, verify_painted_canvas
            from heartopia_app.domain.paint_plan import build_paint_plan
            from heartopia_app.infrastructure.window_backend import capture_window_with_rect, find_game_window

            if self.pixel_data is None:
                raise RuntimeError("尚未加载像素数据")

            hwnd = find_game_window()
            if hwnd is None:
                raise RuntimeError("未找到游戏窗口，无法执行截图验证")

            captured = capture_window_with_rect(hwnd)
            if captured is None:
                raise RuntimeError("截图失败，无法执行截图验证")

            image, rect = captured
            plan = build_paint_plan(self.pixel_data)
            result = verify_painted_canvas(
                image,
                rect,
                self.canvas_calibration,
                plan,
                ratio=self.pixel_data.ratio,
                level=self.pixel_data.level,
            )
            annotated_image = build_annotated_verification_image(
                image,
                self.canvas_calibration,
                plan,
                result,
            )
            self.finished.emit(result, annotated_image, rect)
        except Exception as e:
            self.error.emit(str(e))


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
        self._session = None
        self._hotkey_listener = None
        self._run_context = _PaintRunContext()
        self._last_verification_result: VerificationResult | None = None
        self._last_verification_pixmap: QPixmap | None = None
        self._last_verification_summary = "尚未执行截图验证"
        self._verification_context_key = self._current_verification_context_key()
        self._verification_thread: VerificationThread | None = None

        self._signals = _Signals()
        self._signals.log.connect(self._log)
        self._signals.progress.connect(self._on_progress)
        self._signals.color_change.connect(self._on_color_change)
        self._signals.finished.connect(self._on_finished)
        self._signals.error.connect(self._on_error)

        self._setup_ui()
        self._update_verification_preview()
        self._update_ui_state()
        self._setup_hotkeys()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        left_panel = self._create_control_panel()
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_panel)
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(340)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(left_scroll, stretch=1)

        right_panel = self._create_preview_panel()
        main_layout.addWidget(right_panel, stretch=2)

    def _create_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        data_group = QGroupBox("1. 像素数据导入")
        data_layout = QGridLayout(data_group)

        self.import_btn = QPushButton("导入 JSON 文件")
        self.import_btn.clicked.connect(self._import_json)
        data_layout.addWidget(self.import_btn, 0, 0)

        self.data_label = QLabel("未加载数据")
        data_layout.addWidget(self.data_label, 0, 1)
        layout.addWidget(data_group)

        ctrl_group = QGroupBox("2. 画画控制")
        ctrl_layout = QGridLayout(ctrl_group)

        ctrl_layout.addWidget(QLabel("绘画速度:"), 0, 0)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([
            "极慢 (200ms) - 安全稳定",
            "慢速 (100ms)",
            "正常 (50ms)",
            "快速 (20ms)",
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

        self.verify_btn = QPushButton("截图验证")
        self.verify_btn.setEnabled(False)
        self.verify_btn.clicked.connect(self._run_manual_verification)
        ctrl_layout.addWidget(self.verify_btn, 4, 0)

        self.repair_btn = QPushButton("补画白点")
        self.repair_btn.setEnabled(False)
        self.repair_btn.clicked.connect(self._start_manual_repair)
        ctrl_layout.addWidget(self.repair_btn, 4, 1)

        resume_offset_row = QHBoxLayout()
        resume_offset_row.addWidget(QLabel("起始像素:"))
        self.resume_offset_spin = QSpinBox()
        self.resume_offset_spin.setRange(0, 0)
        self.resume_offset_spin.setValue(0)
        self.resume_offset_spin.setToolTip("手动指定断点续画的起始像素编号（0 表示从头开始）")
        resume_offset_row.addWidget(self.resume_offset_spin)
        resume_offset_row.addStretch()
        ctrl_layout.addLayout(resume_offset_row, 5, 0, 1, 2)

        layout.addWidget(ctrl_group)

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
        layout.addWidget(prog_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(220)
        layout.addWidget(self.log_text)

        layout.addStretch()
        return panel

    def _create_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("验证预览")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.verification_summary_label = QLabel("尚未执行截图验证")
        self.verification_summary_label.setWordWrap(True)
        self.verification_summary_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.verification_summary_label)

        self.verification_scroll = QScrollArea()
        self.verification_scroll.setWidgetResizable(True)
        self.verification_scroll.setAlignment(Qt.AlignCenter)

        self.verification_image_label = QLabel("等待截图验证...")
        self.verification_image_label.setAlignment(Qt.AlignCenter)
        self.verification_image_label.setStyleSheet("background-color: #f0f0f0; border: 2px dashed #cccccc;")
        self.verification_image_label.setMinimumSize(400, 400)

        self.verification_scroll.setWidget(self.verification_image_label)
        layout.addWidget(self.verification_scroll)

        return panel

    def _current_verification_context_key(self) -> tuple:
        pixel_data = self.state.pixel_data
        canvas = self.state.canvas_calibration
        palette = self.state.palette_calibration
        toolbar = self.state.toolbar_calibration
        return (
            str(self.state.pixel_data_path) if self.state.pixel_data_path else None,
            pixel_data.grid_width if pixel_data else None,
            pixel_data.grid_height if pixel_data else None,
            pixel_data.ratio if pixel_data else None,
            pixel_data.level if pixel_data else None,
            canvas.calibrated,
            canvas.grid_width,
            canvas.grid_height,
            canvas.top_left,
            canvas.top_right,
            canvas.bottom_left,
            canvas.bottom_right,
            canvas.offset_x,
            canvas.offset_y,
            canvas.subpixel_phase_x,
            canvas.subpixel_phase_y,
            palette.calibrated,
            palette.left_tab,
            palette.right_tab,
            palette.blocks_top_left,
            palette.blocks_bottom_right,
            toolbar.calibrated,
            toolbar.brush,
            toolbar.bucket,
        )

    def _clear_verification_cache(self, *, reason: str | None = None) -> None:
        had_cache = self._last_verification_result is not None or self._last_verification_pixmap is not None
        self._last_verification_result = None
        self._last_verification_pixmap = None
        self._last_verification_summary = "尚未执行截图验证"
        self._update_verification_preview()
        if reason and had_cache:
            self._log(f"[验证缓存] 已清空：{reason}")

    def _update_verification_preview(self) -> None:
        self.verification_summary_label.setText(self._last_verification_summary)
        if self._last_verification_pixmap is None:
            self.verification_image_label.setPixmap(QPixmap())
            self.verification_image_label.setText("尚未执行截图验证")
            self.verification_image_label.setMinimumSize(400, 260)
            return

        self.verification_image_label.setText("")
        self.verification_image_label.setPixmap(self._last_verification_pixmap)
        self.verification_image_label.setMinimumSize(self._last_verification_pixmap.size())

    def _pil_image_to_pixmap(self, image: Image.Image) -> QPixmap:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        data = rgb_image.tobytes("raw", "RGB")
        qimage = QImage(data, width, height, width * 3, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(qimage)

    def _crop_image_to_canvas_bounds(self, image: Image.Image, window_rect: tuple[int, int, int, int]) -> Image.Image:
        canvas = self.state.canvas_calibration
        if not canvas.calibrated:
            return image

        corners = [
            canvas.top_left,
            canvas.top_right,
            canvas.bottom_left,
            canvas.bottom_right,
        ]
        xs = [point[0] - window_rect[0] for point in corners]
        ys = [point[1] - window_rect[1] for point in corners]

        crop_left = max(0, min(xs))
        crop_top = max(0, min(ys))
        crop_right = min(image.width, max(xs))
        crop_bottom = min(image.height, max(ys))

        if crop_right <= crop_left or crop_bottom <= crop_top:
            return image

        return image.crop((crop_left, crop_top, crop_right, crop_bottom))

    def _update_ui_state(self) -> None:
        current_context_key = self._current_verification_context_key()
        if current_context_key != self._verification_context_key:
            self._verification_context_key = current_context_key
            self._clear_verification_cache(reason="像素数据或标定已变化")

        has_data = self.state.pixel_data is not None
        has_canvas = self.state.canvas_calibration.calibrated
        has_palette = self.state.palette_calibration.calibrated
        is_running = self._session is not None and self._session.is_running

        is_verifying = self._verification_thread is not None and self._verification_thread.isRunning()

        can_start = has_data and has_canvas and has_palette and not is_running and not is_verifying
        self.start_btn.setEnabled(can_start)
        self.pause_btn.setEnabled(is_running)
        self.stop_btn.setEnabled(is_running)

        saved = self.session_repository.load()
        bucket_ready = self.state.toolbar_calibration.calibrated
        self.bucket_fill_cb.setEnabled(can_start or is_running)
        if self.bucket_fill_cb.isChecked() and not bucket_ready:
            self.bucket_fill_cb.setChecked(False)
        self.bucket_fill_cb.setToolTip(
            "启用后，需要先标定工具栏（画笔+油漆桶位置）"
            if not bucket_ready
            else "已标定工具栏，可启用油漆桶优化"
        )

        self.resume_btn.setEnabled(can_start)
        self.verify_btn.setEnabled(can_start)
        self.repair_btn.setEnabled(
            can_start
            and self._last_verification_result is not None
            and bool(self._last_verification_result.repair_candidates)
        )

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
            self._verification_context_key = self._current_verification_context_key()
            self._clear_verification_cache(reason="重新导入了 JSON")

            ratio_str = self.state.pixel_data.ratio or "unknown"
            self._log(f"[OK] 成功导入 {self.state.pixel_data.grid_width}x{self.state.pixel_data.grid_height} 像素数据 (比例: {ratio_str})")

            if self.state.pixel_data.has_color_ids():
                self._log("  [OK] 数据包含 colorId，将使用精确定位")
            else:
                self._log("  [!] 数据不含 colorId，将使用最近邻匹配")

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
                self._log("  [自动应用] 调色板固定坐标已应用")
            if "toolbar" in fixed_data:
                self.state.toolbar_calibration = ToolbarCalibration.from_window_relative(
                    window_offset, fixed_data["toolbar"]
                )
                self._log("  [自动应用] 工具栏固定坐标已应用")

            self.calibration_repository.save(
                self.state.canvas_calibration,
                self.state.palette_calibration,
                self.state.toolbar_calibration,
            )
            self._verification_context_key = self._current_verification_context_key()
            self._clear_verification_cache(reason="自动应用了固定标定")
        except Exception as e:
            self._log(f"  [!] 自动应用固定坐标失败: {e}")

    def _create_session(self, pixel_data=None, *, speed_name: str | None = None, use_bucket_fill: bool | None = None, use_repair_nine_tap: bool = False):
        from heartopia_app.application.paint_session import PaintSession
        from heartopia_app.domain.paint_plan import build_paint_plan

        backend = self.state.input_backend
        if backend is None:
            raise RuntimeError("输入后端未初始化")

        pixel_data = pixel_data or self.state.pixel_data
        plan = build_paint_plan(pixel_data)
        if plan.total_pixels == 0:
            raise RuntimeError("没有需要绘制的像素（全部是背景色？）")

        session = PaintSession(
            canvas=self.state.canvas_calibration,
            palette=self.state.palette_calibration,
            toolbar=self.state.toolbar_calibration,
            backend=backend,
        )
        session.load_plan(plan)

        selected_speed_name = speed_name or SPEED_MAP.get(self.speed_combo.currentIndex(), 'normal')
        session.set_speed(selected_speed_name)
        session.set_bucket_fill_enabled(
            self.bucket_fill_cb.isChecked() if use_bucket_fill is None else use_bucket_fill
        )
        session.set_repair_nine_tap_enabled(use_repair_nine_tap)

        session.on_progress = self._signals.progress.emit
        session.on_color_change = self._signals.color_change.emit
        session.on_finished = self._signals.finished.emit
        session.on_error = self._signals.error.emit

        return session, plan

    def _start_painting(self) -> None:
        try:
            self._clear_verification_cache(reason="开始了新一轮主绘制")
            self._run_context = _PaintRunContext(mode="main", clear_session_on_success=True, final_message="绘画已全部完成！")
            self._session, plan = self._create_session()
            self._log(f"[开始绘画] 共 {plan.total_pixels} 像素, {len(plan.groups)} 种颜色")
            self._log(f"  速度: {SPEED_MAP.get(self.speed_combo.currentIndex(), 'normal')}")
            self._log(f"  油漆桶: {'开启' if self.bucket_fill_cb.isChecked() else '关闭'}")

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
        if self._session and self._session.is_running:
            progress = self._session.stop()
            if self._run_context.mode == "main" and progress.drawn_pixels > 0:
                self.session_repository.save(progress.to_dict())

    def _stop_painting(self) -> None:
        if self._session and self._session.is_running:
            progress = self._session.stop()
            if self._run_context.mode == "main" and progress.drawn_pixels > 0:
                self.session_repository.save(progress.to_dict())
                self._log(f"[停止] 进度已保存 ({progress.drawn_pixels} 像素)")
            elif self._run_context.mode == "repair":
                self._log("[停止] 已停止补画轮次（未覆盖主绘制断点）")
            else:
                self._log("[停止] 绘画已停止")
            self._session = None
            self.pause_btn.setText("⏸ 暂停 (F6)")
            self._update_ui_state()

    def _resume_painting(self) -> None:
        try:
            from heartopia_app.application.paint_session import PaintProgress

            self._clear_verification_cache(reason="开始了新的断点续画")
            self._run_context = _PaintRunContext(mode="main", clear_session_on_success=True, final_message="绘画已全部完成！")
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

    def _run_manual_verification(self) -> None:
        if self._verification_thread is not None and self._verification_thread.isRunning():
            return

        if self.state.pixel_data is None:
            QMessageBox.warning(self, "截图验证失败", "尚未加载像素数据")
            return

        self._log("[验证] 正在截图并生成标记图...")
        self._last_verification_summary = "正在执行截图验证..."
        self._update_verification_preview()

        self._verification_thread = VerificationThread(
            self.state.pixel_data,
            self.state.canvas_calibration,
        )
        self._verification_thread.finished.connect(self._on_verification_finished)
        self._verification_thread.error.connect(self._on_verification_error)
        self._verification_thread.finished.connect(self._verification_thread.deleteLater)
        self._verification_thread.error.connect(self._verification_thread.deleteLater)
        self._verification_thread.start()
        self._update_ui_state()

    def _on_verification_finished(self, result, annotated_image, window_rect) -> None:
        self._last_verification_result = result
        preview_image = self._crop_image_to_canvas_bounds(annotated_image, window_rect)
        self._last_verification_pixmap = self._pil_image_to_pixmap(preview_image)
        self._last_verification_summary = result.summary_text()
        self._update_verification_preview()

        self._log(f"[验证] {result.summary_text()}")
        for mismatch in result.mismatches[:10]:
            x, y = mismatch.coord
            self._log(
                f"  [{mismatch.classification}] ({x},{y}) target={mismatch.target_group_key} "
                f"observed={mismatch.observed_color_id} screenshot={mismatch.screenshot_pos}"
            )
        if len(result.mismatches) > 10:
            self._log(f"  ... 其余 {len(result.mismatches) - 10} 个 mismatch 省略")

        if result.repair_candidates:
            self._log(f"[补画候选] 共 {len(result.repair_candidates)} 个漏白点候选，可手动点击“补画白点”")
        else:
            self._log("[补画候选] 当前没有可补画的漏白点候选")

        self._verification_thread = None
        self._update_ui_state()

    def _on_verification_error(self, error_msg: str) -> None:
        self._last_verification_summary = "截图验证失败"
        self._update_verification_preview()
        self._log(f"[ERROR] 截图验证失败: {error_msg}")
        self._verification_thread = None
        self._update_ui_state()
        QMessageBox.warning(self, "截图验证失败", f"截图验证失败：\n{error_msg}")

    def _start_repair_pass(self, repair_pixel_data) -> None:
        self._run_context = _PaintRunContext(
            mode="repair",
            clear_session_on_success=False,
            final_message="补画白点已完成！",
        )
        self._session, plan = self._create_session(
            repair_pixel_data,
            speed_name="very_slow",
            use_bucket_fill=False,
            use_repair_nine_tap=True,
        )
        self.progress_bar.setMaximum(plan.total_pixels)
        self.progress_bar.setValue(0)
        self._log(f"[补画开始] 共 {plan.total_pixels} 像素，使用 very_slow + brush-only + no bucket + 九宫格补点")
        self._session.start()
        self._update_ui_state()

    def _start_manual_repair(self) -> None:
        try:
            from heartopia_app.application import build_repair_pixel_data

            result = self._last_verification_result
            if result is None:
                raise RuntimeError("请先执行截图验证")
            if not result.repair_candidates:
                raise RuntimeError("最近一次验证结果中没有可补画的漏白点候选")
            if self.state.pixel_data is None:
                raise RuntimeError("尚未加载像素数据")

            repair_pixel_data = build_repair_pixel_data(self.state.pixel_data, result.repair_candidates)
            self._start_repair_pass(repair_pixel_data)
        except Exception as e:
            self._log(f"[ERROR] 启动补画失败: {e}")
            QMessageBox.warning(self, "补画失败", f"启动补画失败：\n{e}")

    def _finalize_success(self, message: str, *, clear_session: bool) -> None:
        if clear_session:
            self.session_repository.clear()
        self._session = None
        self.pause_btn.setText("⏸ 暂停 (F6)")
        self._update_ui_state()
        QMessageBox.information(self, "完成", message)

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
        mode = self._run_context.mode
        self._log("[完成] 当前绘制轮次已完成")
        self._session = None
        self.pause_btn.setText("⏸ 暂停 (F6)")
        self._update_ui_state()

        if mode == "repair":
            self._finalize_success("补画白点已完成，请按需再次点击截图验证复查。", clear_session=False)
            return

        self._finalize_success(self._run_context.final_message, clear_session=self._run_context.clear_session_on_success)

    def _on_error(self, msg: str) -> None:
        self._log(f"[ERROR] {msg}")
        self._session = None
        self.pause_btn.setText("⏸ 暂停 (F6)")
        self._update_ui_state()
        QMessageBox.critical(self, "绘画错误", msg)
