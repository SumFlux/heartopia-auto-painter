from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QComboBox,
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
    from heartopia_app.application import WorkspaceState, CalibrationService
    from heartopia_app.infrastructure import CalibrationRepository


class _Signals(QObject):
    """Thread-safe Qt signals for cross-thread communication."""
    log = Signal(str)
    canvas_done = Signal(object)  # CanvasCalibration
    palette_done = Signal(object)  # PaletteCalibration
    toolbar_done = Signal(object)  # ToolbarCalibration
    error = Signal(str)
    test_done = Signal()


class CalibrationPage(QWidget):
    def __init__(
        self,
        state: WorkspaceState,
        calibration_repository: CalibrationRepository,
        calibration_service: CalibrationService,
    ):
        super().__init__()
        self.state = state
        self.calibration_repository = calibration_repository
        self.calibration_service = calibration_service
        self._stop_event = threading.Event()

        self._signals = _Signals()
        self._signals.log.connect(self._log)
        self._signals.canvas_done.connect(self._on_canvas_done)
        self._signals.palette_done.connect(self._on_palette_done)
        self._signals.toolbar_done.connect(self._on_toolbar_done)
        self._signals.error.connect(self._on_error)
        self._signals.test_done.connect(self._on_test_done)

        self._setup_ui()
        self._update_ui_state()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # --- Calibration controls ---
        calib_group = QGroupBox("坐标标定")
        calib_layout = QVBoxLayout(calib_group)

        self.calib_canvas_btn = QPushButton("标定画板范围（4 个角，共 4 次 Enter）")
        self.calib_canvas_btn.setToolTip("点击后切回游戏，按 Z 字形依次标定左上→右上→左下→右下四个角")
        self.calib_canvas_btn.clicked.connect(self._start_canvas_calibration)
        calib_layout.addWidget(self.calib_canvas_btn)

        self.auto_detect_btn = QPushButton("🔍 自动检测画布（4角标记点）")
        self.auto_detect_btn.setToolTip("先在游戏画布的4个角各画一个醒目红色标记，然后点此自动检测")
        self.auto_detect_btn.clicked.connect(self._auto_detect_canvas)
        calib_layout.addWidget(self.auto_detect_btn)

        self.calib_palette_btn = QPushButton("标定调色板（左右标签 + 色块区域，共 4 次 Enter）")
        self.calib_palette_btn.setToolTip("依次标定：标签最左 -> 标签最右 -> 色块左上第一格 -> 色块右下最后一格")
        self.calib_palette_btn.clicked.connect(self._start_palette_calibration)
        calib_layout.addWidget(self.calib_palette_btn)

        self.calib_toolbar_btn = QPushButton("🔧 标定工具栏（画笔+油漆桶）")
        self.calib_toolbar_btn.setToolTip("标定画笔和油漆桶工具在屏幕上的位置")
        self.calib_toolbar_btn.clicked.connect(self._start_toolbar_calibration)
        calib_layout.addWidget(self.calib_toolbar_btn)

        self.calib_status_label = QLabel("")
        calib_layout.addWidget(self.calib_status_label)

        # Action buttons row
        btn_row = QHBoxLayout()

        self.recalib_btn = QPushButton("🗑 清除标定（重新标定）")
        self.recalib_btn.clicked.connect(self._clear_calibration)
        btn_row.addWidget(self.recalib_btn)

        self.test_calib_btn = QPushButton("🧪 测试标定（画边框）")
        self.test_calib_btn.clicked.connect(self._test_calibration)
        btn_row.addWidget(self.test_calib_btn)

        calib_layout.addLayout(btn_row)

        # Offset adjustment row
        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("微调偏移:"))

        offset_row.addWidget(QLabel("X"))
        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-20, 20)
        self.offset_x_spin.setValue(self.state.canvas_calibration.offset_x)
        self.offset_x_spin.setSuffix(" px")
        self.offset_x_spin.valueChanged.connect(self._on_offset_changed)
        offset_row.addWidget(self.offset_x_spin)

        offset_row.addWidget(QLabel("Y"))
        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-20, 20)
        self.offset_y_spin.setValue(self.state.canvas_calibration.offset_y)
        self.offset_y_spin.setSuffix(" px")
        self.offset_y_spin.valueChanged.connect(self._on_offset_changed)
        offset_row.addWidget(self.offset_y_spin)

        self.reset_offset_btn = QPushButton("归零")
        self.reset_offset_btn.setFixedWidth(50)
        self.reset_offset_btn.clicked.connect(self._reset_offset)
        offset_row.addWidget(self.reset_offset_btn)

        offset_row.addStretch()
        calib_layout.addLayout(offset_row)

        main_layout.addWidget(calib_group)

        # --- Fixed positions ---
        fixed_group = QGroupBox("固定坐标（跨会话复用）")
        fixed_layout = QVBoxLayout(fixed_group)

        ratio_row = QHBoxLayout()
        ratio_row.addWidget(QLabel("画布比例:"))
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(["16:9", "4:3", "1:1", "3:4", "9:16"])
        self.ratio_combo.setCurrentText("1:1")
        # Auto-select ratio from loaded pixel_data
        if self.state.pixel_data and self.state.pixel_data.ratio:
            idx = self.ratio_combo.findText(self.state.pixel_data.ratio)
            if idx >= 0:
                self.ratio_combo.setCurrentIndex(idx)
        ratio_row.addWidget(self.ratio_combo)
        ratio_row.addStretch()
        fixed_layout.addLayout(ratio_row)

        btn_row_fixed = QHBoxLayout()

        self.save_fixed_btn = QPushButton("💾 保存当前标定为固定坐标")
        self.save_fixed_btn.setToolTip("将当前标定的相对坐标保存，下次自动应用")
        self.save_fixed_btn.clicked.connect(self._save_fixed_positions)
        btn_row_fixed.addWidget(self.save_fixed_btn)

        self.apply_fixed_btn = QPushButton("📌 应用固定坐标")
        self.apply_fixed_btn.setToolTip("根据当前游戏窗口位置 + 保存的相对坐标自动标定")
        self.apply_fixed_btn.clicked.connect(self._apply_fixed_positions)
        btn_row_fixed.addWidget(self.apply_fixed_btn)

        self.clear_fixed_btn = QPushButton("清除固定坐标")
        self.clear_fixed_btn.clicked.connect(self._clear_fixed_positions)
        btn_row_fixed.addWidget(self.clear_fixed_btn)

        fixed_layout.addLayout(btn_row_fixed)

        main_layout.addWidget(fixed_group)

        # --- Log ---
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(250)
        main_layout.addWidget(self.log_text)

        main_layout.addStretch()

    def _update_ui_state(self) -> None:
        has_canvas = self.state.canvas_calibration.calibrated
        has_palette = self.state.palette_calibration.calibrated
        has_toolbar = self.state.toolbar_calibration.calibrated

        self.recalib_btn.setEnabled(has_canvas or has_palette or has_toolbar)
        self.test_calib_btn.setEnabled(has_canvas and has_palette)
        self.save_fixed_btn.setEnabled(has_canvas or has_palette or has_toolbar)

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

    def _on_canvas_done(self, canvas) -> None:
        self.state.canvas_calibration = canvas
        self._save_calibration()
        self._update_ui_state()

    def _on_palette_done(self, palette) -> None:
        self.state.palette_calibration = palette
        self._save_calibration()
        self._update_ui_state()

    def _on_toolbar_done(self, toolbar) -> None:
        self.state.toolbar_calibration = toolbar
        self._save_calibration()
        self._update_ui_state()

    def _on_error(self, msg: str) -> None:
        self._log(f"[ERROR] {msg}")

    def _on_test_done(self) -> None:
        self._log("[测试标定] 流程结束")
        self._stop_test_hotkey_listener()
        self.test_calib_btn.setEnabled(True)

    def _save_calibration(self) -> None:
        self.calibration_repository.save(
            self.state.canvas_calibration,
            self.state.palette_calibration,
            self.state.toolbar_calibration,
        )

    def _get_grid_dimensions(self):
        """Get grid dimensions from loaded pixel data, or return defaults."""
        if self.state.pixel_data:
            return self.state.pixel_data.grid_width, self.state.pixel_data.grid_height
        # If already calibrated, use existing dimensions
        if self.state.canvas_calibration.calibrated:
            return self.state.canvas_calibration.grid_width, self.state.canvas_calibration.grid_height
        return None, None

    # ----- Calibration actions -----

    def _start_canvas_calibration(self) -> None:
        grid_w, grid_h = self._get_grid_dimensions()
        if grid_w is None:
            QMessageBox.warning(self, "提示", "请先在「绘画」页导入像素数据，或先完成一次画布标定")
            return
        self._log(f"[画布标定] 网格: {grid_w}x{grid_h}，请切换到游戏窗口...")
        self.calibration_service.calibrate_canvas_manual(
            grid_w=grid_w,
            grid_h=grid_h,
            on_log=self._signals.log.emit,
            on_done=self._signals.canvas_done.emit,
            on_error=self._signals.error.emit,
        )

    def _auto_detect_canvas(self) -> None:
        grid_w, grid_h = self._get_grid_dimensions()
        if grid_w is None:
            QMessageBox.warning(self, "提示", "请先在「绘画」页导入像素数据")
            return
        self._log(f"[自动检测] 网格: {grid_w}x{grid_h}")
        self.calibration_service.calibrate_canvas_auto_detect(
            grid_w=grid_w,
            grid_h=grid_h,
            on_log=self._signals.log.emit,
            on_done=self._signals.canvas_done.emit,
            on_error=self._signals.error.emit,
        )

    def _start_palette_calibration(self) -> None:
        self._log("[调色板标定] 请切换到游戏窗口...")
        self.calibration_service.calibrate_palette(
            on_log=self._signals.log.emit,
            on_done=self._signals.palette_done.emit,
            on_error=self._signals.error.emit,
        )

    def _start_toolbar_calibration(self) -> None:
        self._log("[工具栏标定] 请切换到游戏窗口...")
        self.calibration_service.calibrate_toolbar(
            on_log=self._signals.log.emit,
            on_done=self._signals.toolbar_done.emit,
            on_error=self._signals.error.emit,
        )

    def _clear_calibration(self) -> None:
        reply = QMessageBox.question(
            self, "确认", "确定要清除所有标定数据吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.state.canvas_calibration.reset()
            self.state.palette_calibration.reset()
            self.state.toolbar_calibration.reset()
            self._save_calibration()
            self._update_ui_state()
            self._log("[OK] 已清除所有标定数据")

    def _test_calibration(self) -> None:
        if not self.state.canvas_calibration.calibrated or not self.state.palette_calibration.calibrated:
            QMessageBox.warning(self, "提示", "请先完成画布和调色板标定")
            return

        # Sync grid dimensions: pixel_data > ratio combo lookup > existing canvas
        target_w, target_h = None, None
        if self.state.pixel_data:
            target_w = self.state.pixel_data.grid_width
            target_h = self.state.pixel_data.grid_height
        else:
            # Infer from ratio combo using max-level grid dimensions
            from heartopia_app.domain.conversion import GRID_DIMENSIONS
            ratio = self.ratio_combo.currentText()
            if ratio in GRID_DIMENSIONS:
                dims = GRID_DIMENSIONS[ratio][-1]  # max level
                target_w, target_h = dims[0], dims[1]

        if target_w and target_h:
            cc = self.state.canvas_calibration
            if (cc.grid_width, cc.grid_height) != (target_w, target_h):
                self._log(f"[测试标定] 网格尺寸同步: {cc.grid_width}x{cc.grid_height} → {target_w}x{target_h}")
                cc.grid_width = target_w
                cc.grid_height = target_h

        self.test_calib_btn.setEnabled(False)
        self._stop_event.clear()

        # Start F7 keyboard listener for interruption
        self._start_test_hotkey_listener()

        self.calibration_service.test_border(
            canvas=self.state.canvas_calibration,
            palette=self.state.palette_calibration,
            on_log=self._signals.log.emit,
            on_done=self._signals.test_done.emit,
            stop_event=self._stop_event,
        )

    def _on_offset_changed(self) -> None:
        self.state.canvas_calibration.offset_x = self.offset_x_spin.value()
        self.state.canvas_calibration.offset_y = self.offset_y_spin.value()
        self._save_calibration()
        self._log(f"[OK] 偏移已更新: X={self.offset_x_spin.value()}, Y={self.offset_y_spin.value()}")

    def _reset_offset(self) -> None:
        self.offset_x_spin.setValue(0)
        self.offset_y_spin.setValue(0)

    # ----- Test hotkey listener -----

    def _start_test_hotkey_listener(self) -> None:
        """Start a pynput keyboard listener to allow F7 interruption during test calibration."""
        try:
            from pynput.keyboard import Key, Listener

            def on_press(key):
                try:
                    if key == Key.f7:
                        self._stop_event.set()
                        self._signals.log.emit("[热键] F7 - 中断测试标定")
                        return False  # stop listener
                except Exception:
                    pass

            self._test_key_listener = Listener(on_press=on_press)
            self._test_key_listener.daemon = True
            self._test_key_listener.start()
        except Exception:
            pass

    def _stop_test_hotkey_listener(self) -> None:
        """Stop the test calibration F7 listener if running."""
        listener = getattr(self, "_test_key_listener", None)
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
            self._test_key_listener = None

    # ----- Fixed positions -----

    def _save_fixed_positions(self) -> None:
        """Save current calibration as window-relative fixed positions, keyed by ratio."""
        try:
            from heartopia_app.infrastructure.window_backend import find_game_window, get_window_rect
            hwnd = find_game_window()
            if hwnd is None:
                QMessageBox.warning(self, "提示", "未找到游戏窗口，请确保心动小镇已运行")
                return
            rect = get_window_rect(hwnd)
            if rect is None:
                QMessageBox.warning(self, "提示", "无法获取窗口位置")
                return

            window_offset = (rect[0], rect[1])
            ratio = self.ratio_combo.currentText()

            # Load existing file to preserve other ratio profiles
            fixed_path = self.state.app_data_dir / "fixed_positions.json"
            if fixed_path.exists():
                with fixed_path.open("r", encoding="utf-8") as f:
                    fixed_data = json.load(f)
            else:
                fixed_data = {}

            # Ensure canvas_profiles dict exists
            if "canvas_profiles" not in fixed_data:
                fixed_data["canvas_profiles"] = {}

            if self.state.canvas_calibration.calibrated:
                # Sync grid dimensions before saving
                target_w, target_h = None, None
                if self.state.pixel_data:
                    target_w = self.state.pixel_data.grid_width
                    target_h = self.state.pixel_data.grid_height
                else:
                    from heartopia_app.domain.conversion import GRID_DIMENSIONS
                    if ratio in GRID_DIMENSIONS:
                        dims = GRID_DIMENSIONS[ratio][-1]
                        target_w, target_h = dims[0], dims[1]
                if target_w and target_h:
                    cc = self.state.canvas_calibration
                    if (cc.grid_width, cc.grid_height) != (target_w, target_h):
                        self._log(f"  [同步] 网格尺寸: {cc.grid_width}x{cc.grid_height} → {target_w}x{target_h}")
                        cc.grid_width = target_w
                        cc.grid_height = target_h
                fixed_data["canvas_profiles"][ratio] = self.state.canvas_calibration.compute_relative_corners(window_offset)
                # Remove legacy 'canvas' key if present
                fixed_data.pop("canvas", None)
            if self.state.palette_calibration.calibrated:
                fixed_data['palette'] = self.state.palette_calibration.compute_relative(window_offset)
            if self.state.toolbar_calibration.calibrated:
                fixed_data['toolbar'] = self.state.toolbar_calibration.compute_relative(window_offset)

            has_any = bool(fixed_data.get("canvas_profiles")) or "palette" in fixed_data or "toolbar" in fixed_data
            if not has_any:
                QMessageBox.warning(self, "提示", "没有可保存的标定数据")
                return

            with fixed_path.open("w", encoding="utf-8") as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)

            self._log(f"[OK] 固定坐标已保存到 {fixed_path}（比例: {ratio}）")
        except Exception as e:
            self._log(f"[ERROR] 保存固定坐标失败: {e}")

    def _apply_fixed_positions(self) -> None:
        """Apply saved fixed positions based on current window location and selected ratio."""
        try:
            fixed_path = self.state.app_data_dir / "fixed_positions.json"
            if not fixed_path.exists():
                QMessageBox.warning(self, "提示", "未找到保存的固定坐标文件")
                return

            from heartopia_app.infrastructure.window_backend import find_game_window, get_window_rect
            hwnd = find_game_window()
            if hwnd is None:
                QMessageBox.warning(self, "提示", "未找到游戏窗口")
                return
            rect = get_window_rect(hwnd)
            if rect is None:
                QMessageBox.warning(self, "提示", "无法获取窗口位置")
                return

            window_offset = (rect[0], rect[1])

            with fixed_path.open("r", encoding="utf-8") as f:
                fixed_data = json.load(f)

            from heartopia_app.domain.calibration import CanvasCalibration, PaletteCalibration, ToolbarCalibration

            ratio = self.ratio_combo.currentText()

            # Try canvas_profiles[ratio] first, fall back to legacy 'canvas'
            canvas_rel = None
            if "canvas_profiles" in fixed_data and ratio in fixed_data["canvas_profiles"]:
                canvas_rel = fixed_data["canvas_profiles"][ratio]
            elif "canvas" in fixed_data:
                canvas_rel = fixed_data["canvas"]
                self._log(f"  [!] 未找到比例 {ratio} 的画布配置，使用旧格式 canvas")

            if canvas_rel:
                self.state.canvas_calibration = CanvasCalibration.from_window_relative(
                    window_offset, canvas_rel
                )
                # Sync grid dimensions: pixel_data > ratio lookup > stored value
                target_w, target_h = None, None
                if self.state.pixel_data:
                    target_w = self.state.pixel_data.grid_width
                    target_h = self.state.pixel_data.grid_height
                else:
                    from heartopia_app.domain.conversion import GRID_DIMENSIONS
                    if ratio in GRID_DIMENSIONS:
                        dims = GRID_DIMENSIONS[ratio][-1]
                        target_w, target_h = dims[0], dims[1]
                if target_w and target_h:
                    cc = self.state.canvas_calibration
                    if (cc.grid_width, cc.grid_height) != (target_w, target_h):
                        self._log(f"  [同步] 网格尺寸: {cc.grid_width}x{cc.grid_height} → {target_w}x{target_h}")
                        cc.grid_width = target_w
                        cc.grid_height = target_h
                self._log(f"  ✓ 画布标定已应用（比例: {ratio}）")
            else:
                self._log(f"  [!] 未找到比例 {ratio} 的画布配置")

            if 'palette' in fixed_data:
                self.state.palette_calibration = PaletteCalibration.from_window_relative(
                    window_offset, fixed_data['palette']
                )
                self._log(f"  ✓ 调色板标定已应用")
            if 'toolbar' in fixed_data:
                self.state.toolbar_calibration = ToolbarCalibration.from_window_relative(
                    window_offset, fixed_data['toolbar']
                )
                self._log(f"  ✓ 工具栏标定已应用")

            self._save_calibration()
            self._update_ui_state()
            self._log(f"[OK] 固定坐标已应用（窗口位置: {window_offset}）")
        except Exception as e:
            self._log(f"[ERROR] 应用固定坐标失败: {e}")

    def _clear_fixed_positions(self) -> None:
        fixed_path = self.state.app_data_dir / "fixed_positions.json"
        if fixed_path.exists():
            fixed_path.unlink()
            self._log("[OK] 已清除固定坐标文件")
        else:
            self._log("[!] 没有固定坐标文件")
