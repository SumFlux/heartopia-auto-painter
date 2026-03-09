"""
心动小镇自动画画脚本 — GUI 控制面板（主程序入口）

集成各个模块，提供导入数据、标定画布、控制画画流程的图形界面。

架构改进：
- 使用 shared.pixel_data 统一 JSON 解析（修复维度 bug）
- 使用 InputBackend 抽象层（支持 pynput / PostMessage 切换）
- 使用 pynput.keyboard.Listener 替代 keyboard 模块（无需管理员权限）
- 使用 pynput 统一获取鼠标位置（替代 pyautogui，消除 DPI 不一致）
- 标定数据持久化到 calibration.json
- 调色板标定从 14 次简化为 4 次点击
- 支持断点续画
"""

import os
import sys
import json
import threading
import time
from typing import Optional, Tuple

# 确保能导入项目根目录的 shared 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout, QProgressBar, QTextEdit, QSpinBox,
    QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject

from shared.pixel_data import PixelData
from window_manager import find_game_window, bring_to_front, get_window_rect, capture_window
from canvas_locator import CanvasLocator
from palette_navigator import PaletteNavigator
from paint_engine import PaintEngine
from mouse_input import PynputBackend, InputBackend, create_backend
from config import SPEED_PRESETS, FIXED_POSITIONS_FILE, BUCKET_FILL_MIN_AREA


# ===== 标定数据持久化路径 =====
CALIBRATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calibration.json')


class WorkerSignals(QObject):
    """跨线程信号"""
    log_msg = Signal(str)
    calibration_done = Signal(str)
    progress_update = Signal(int, int)
    color_update = Signal(str, int, int)
    painting_finished = Signal()
    painting_error = Signal(str)


class KeyboardListener:
    """
    全局快捷键监听器（基于 pynput，不需要管理员权限）
    替代原来的 keyboard 模块
    """

    def __init__(self):
        self._callbacks = {}  # { Key: callable }
        self._listener = None

    def add_hotkey(self, key_name: str, callback):
        """注册热键回调"""
        from pynput.keyboard import Key
        key_map = {
            'f5': Key.f5,
            'f6': Key.f6,
            'f7': Key.f7,
        }
        key = key_map.get(key_name.lower())
        if key:
            self._callbacks[key] = callback

    def start(self):
        from pynput.keyboard import Listener
        self._listener = Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()

    def _on_press(self, key):
        if key in self._callbacks:
            self._callbacks[key]()


class MousePositionGetter:
    """统一的鼠标位置获取（使用 pynput，与 InputBackend 的坐标体系一致）"""

    def __init__(self):
        from pynput.mouse import Controller
        self._mouse = Controller()

    def position(self):
        """返回 (x, y) 整数元组"""
        pos = self._mouse.position
        return (int(pos[0]), int(pos[1]))


class AutoPainterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("心动小镇 — 自动画画脚本")
        self.setMinimumSize(520, 700)

        # 跨线程信号
        self.signals = WorkerSignals()
        self.signals.log_msg.connect(self._log)
        self.signals.calibration_done.connect(self._on_calibration_done)
        self.signals.progress_update.connect(self._on_progress)
        self.signals.color_update.connect(self._on_color_change)
        self.signals.painting_finished.connect(self._on_finished)
        self.signals.painting_error.connect(self._on_error)

        # 统一鼠标位置获取器
        self._mouse_getter = MousePositionGetter()

        # 输入后端
        self.backend: InputBackend = PynputBackend()

        # 核心模块
        self.locator = CanvasLocator()
        self.navigator = PaletteNavigator(self.backend)
        self.engine = PaintEngine(self.locator, self.navigator, self.backend)

        # 绑定引擎回调（通过信号桥接到 GUI 线程）
        self.engine.on_progress = lambda d, t: self.signals.progress_update.emit(d, t)
        self.engine.on_color_change = lambda c, i, n: self.signals.color_update.emit(c, i, n)
        self.engine.on_finished = lambda: self.signals.painting_finished.emit()
        self.engine.on_error = lambda e: self.signals.painting_error.emit(e)

        # 像素数据
        self.pixel_data = None

        # 绘画计时
        self._paint_start_time: float = 0.0

        self._init_ui()
        self._load_calibration()
        self._setup_hotkeys()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 1. 数据导入 ---
        data_group = QGroupBox("1. 像素数据导入")
        data_layout = QGridLayout(data_group)

        self.import_btn = QPushButton("导入 JSON 文件")
        self.import_btn.clicked.connect(self._import_json)
        data_layout.addWidget(self.import_btn, 0, 0)

        self.data_label = QLabel("未加载数据")
        data_layout.addWidget(self.data_label, 0, 1)
        main_layout.addWidget(data_group)

        # --- 2. 标定 ---
        calib_group = QGroupBox("2. 坐标标定（在游戏中操作）")
        calib_layout = QVBoxLayout(calib_group)

        self.calib_canvas_btn = QPushButton("标定画板范围（4 个角，共 4 次 Enter）")
        self.calib_canvas_btn.setToolTip("点击后切回游戏，按 Z 字形依次标定左上→右上→左下→右下四个角")
        self.calib_canvas_btn.clicked.connect(self._start_canvas_calibration)
        calib_layout.addWidget(self.calib_canvas_btn)

        self.auto_detect_btn = QPushButton("🔍 自动检测画布（4角标记点）")
        self.auto_detect_btn.setToolTip(
            "先在游戏画布的4个角各画一个醒目颜色的像素，然后点此自动检测"
        )
        self.auto_detect_btn.clicked.connect(self._auto_detect_canvas)
        calib_layout.addWidget(self.auto_detect_btn)

        self.calib_palette_btn = QPushButton("标定调色板（左右标签 + 色块区域，共 4 次 Enter）")
        self.calib_palette_btn.setToolTip("依次标定：标签最左 -> 标签最右 -> 色块左上第一格 -> 色块右下最后一格")
        self.calib_palette_btn.clicked.connect(self._start_palette_calibration)
        calib_layout.addWidget(self.calib_palette_btn)

        self.calib_status_label = QLabel("")
        calib_layout.addWidget(self.calib_status_label)

        # 操作按钮行：清除标定 + 测试标定
        btn_row = QHBoxLayout()

        self.recalib_btn = QPushButton("🗑 清除标定（重新标定）")
        self.recalib_btn.setToolTip("清除已保存的标定数据，可以重新标定画布和调色板")
        self.recalib_btn.clicked.connect(self._clear_calibration)
        self.recalib_btn.setEnabled(False)
        btn_row.addWidget(self.recalib_btn)

        self.test_calib_btn = QPushButton("🧪 测试标定（画边框）")
        self.test_calib_btn.setToolTip("沿画布最外围画一圈黑红交替边框，验证标定是否准确")
        self.test_calib_btn.clicked.connect(self._test_calibration)
        self.test_calib_btn.setEnabled(False)
        btn_row.addWidget(self.test_calib_btn)

        calib_layout.addLayout(btn_row)

        # 固定坐标按钮行
        fixed_row = QHBoxLayout()

        self.save_fixed_btn = QPushButton("📌 固定当前坐标")
        self.save_fixed_btn.setToolTip(
            "将当前标定保存为相对于游戏窗口的固定坐标，以后自动标定无需手动操作"
        )
        self.save_fixed_btn.clicked.connect(self._save_fixed_positions)
        self.save_fixed_btn.setEnabled(False)
        fixed_row.addWidget(self.save_fixed_btn)

        self.auto_fixed_btn = QPushButton("⚡ 从窗口自动标定")
        self.auto_fixed_btn.setToolTip("使用已保存的固定坐标 + 当前游戏窗口位置自动计算标定")
        self.auto_fixed_btn.clicked.connect(self._apply_fixed_positions)
        self.auto_fixed_btn.setEnabled(os.path.exists(FIXED_POSITIONS_FILE))
        fixed_row.addWidget(self.auto_fixed_btn)

        self.clear_fixed_btn = QPushButton("🗑 清除固定坐标")
        self.clear_fixed_btn.setToolTip("删除已保存的固定坐标文件")
        self.clear_fixed_btn.clicked.connect(self._clear_fixed_positions)
        self.clear_fixed_btn.setEnabled(os.path.exists(FIXED_POSITIONS_FILE))
        fixed_row.addWidget(self.clear_fixed_btn)

        calib_layout.addLayout(fixed_row)

        # 工具栏标定按钮行
        toolbar_row = QHBoxLayout()

        self.calib_toolbar_btn = QPushButton("🔧 标定工具栏（画笔+油漆桶）")
        self.calib_toolbar_btn.setToolTip("标定画笔和油漆桶工具在屏幕上的位置，用于油漆桶填充优化")
        self.calib_toolbar_btn.clicked.connect(self._start_toolbar_calibration)
        toolbar_row.addWidget(self.calib_toolbar_btn)

        calib_layout.addLayout(toolbar_row)

        # 微调偏移行
        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("微调偏移:"))

        offset_row.addWidget(QLabel("X"))
        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-20, 20)
        self.offset_x_spin.setValue(0)
        self.offset_x_spin.setSuffix(" px")
        self.offset_x_spin.setToolTip("正值=整体右移，负值=整体左移")
        self.offset_x_spin.valueChanged.connect(self._on_offset_changed)
        offset_row.addWidget(self.offset_x_spin)

        offset_row.addWidget(QLabel("Y"))
        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-20, 20)
        self.offset_y_spin.setValue(0)
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

        # --- 3. 画画控制 ---
        ctrl_group = QGroupBox("3. 画画控制")
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

        # 油漆桶优化开关
        self.bucket_fill_cb = QCheckBox("🪣 油漆桶填充（大面积同色区域自动填充）")
        self.bucket_fill_cb.setToolTip(
            f"启用后，连通区域 ≥ {BUCKET_FILL_MIN_AREA} 像素时先画边界再油漆桶填充\n"
            f"需要已保存固定坐标（含工具栏位置）"
        )
        self.bucket_fill_cb.setChecked(False)
        self.bucket_fill_cb.stateChanged.connect(self._on_bucket_fill_changed)
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

        # --- 4. 进度 ---
        prog_group = QGroupBox("4. 进度")
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

        # --- 日志 ---
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(160)
        main_layout.addWidget(self.log_text)

    def _setup_hotkeys(self):
        """注册全局快捷键（pynput，无需管理员权限）"""
        self._kb_listener = KeyboardListener()
        self._kb_listener.add_hotkey('f5', self._start_painting)
        self._kb_listener.add_hotkey('f6', self._pause_painting)
        self._kb_listener.add_hotkey('f7', self._stop_painting_hotkey)
        self._kb_listener.start()

    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        self._kb_listener.stop()
        if self.engine.is_running:
            self.engine.stop()
        super().closeEvent(event)

    # ===== 日志 =====

    def _log(self, text: str):
        self.log_text.append(text)
        self.log_text.ensureCursorVisible()

    # ===== 数据导入 =====

    def _import_json(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择像素矩阵 JSON", "", "JSON (*.json)"
        )
        if not file_path:
            return

        try:
            self.pixel_data = PixelData.from_json_file(file_path)

            ratio_str = self.pixel_data.ratio or "unknown"
            self.data_label.setText(
                f"已加载: {self.pixel_data.grid_width}x{self.pixel_data.grid_height} ({ratio_str})"
            )
            self._log(f"[OK] 成功导入 {self.pixel_data.grid_width}x{self.pixel_data.grid_height} 像素数据 (比例: {ratio_str})")

            self.engine.load_pixel_data(self.pixel_data)
            self._log(f"  需要绘制: {self.engine.total_pixels} 个像素点")

            if self.pixel_data.has_color_ids():
                self._log(f"  [OK] 数据包含 colorId，将使用精确定位")
            else:
                self._log(f"  [!] 数据不含 colorId，将使用最近邻匹配（可能有偏差）")

            # 自动切换画布配置（按比例匹配）
            self._auto_switch_canvas_profile()

            self._check_ready()

            # 检查是否有断点续画的进度
            if self.engine.has_saved_progress():
                self.resume_btn.setEnabled(True)
                self._log("  [i] 检测到上次中断的进度，可点击 [断点续画] 继续")

        except Exception as e:
            QMessageBox.critical(self, "导入错误", f"解析失败:\n{e}")

    # ===== 标定流程 =====

    def _wait_for_enter(self):
        """等待用户按下 Enter 键（使用 pynput 监听，无需管理员权限）"""
        from pynput.keyboard import Key, Listener

        pressed = threading.Event()

        def on_press(key):
            if key == Key.enter:
                pressed.set()
                return False  # 停止监听

        listener = Listener(on_press=on_press)
        listener.start()
        pressed.wait()

    def _start_canvas_calibration(self):
        if self.pixel_data is None:
            QMessageBox.warning(self, "提示", "请先导入 JSON 确定网格尺寸！")
            return

        self.calib_canvas_btn.setEnabled(False)
        self._log("--- 开始标定画布（4 角）---")
        self._log("(1/4) 请切到游戏，鼠标停在【左上角第一格】中心，按 Enter")

        def _thread():
            # 1. 左上角
            self._wait_for_enter()
            tl = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 左上角: {tl}")
            time.sleep(0.3)

            # 2. 右上角
            self.signals.log_msg.emit("(2/4) 鼠标停在【右上角最后一格】中心，按 Enter")
            self._wait_for_enter()
            tr = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 右上角: {tr}")
            time.sleep(0.3)

            # 3. 左下角
            self.signals.log_msg.emit("(3/4) 鼠标停在【左下角第一格】中心，按 Enter")
            self._wait_for_enter()
            bl = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 左下角: {bl}")
            time.sleep(0.3)

            # 4. 右下角
            self.signals.log_msg.emit("(4/4) 鼠标停在【右下角最后一格】中心，按 Enter")
            self._wait_for_enter()
            br = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 右下角: {br}")

            self.locator.calibrate(
                self.pixel_data.grid_width,
                self.pixel_data.grid_height,
                top_left=tl,
                bottom_right=br,
                top_right=tr,
                bottom_left=bl,
            )
            self._save_calibration()
            self.signals.calibration_done.emit("画布")
            QTimer.singleShot(0, lambda: self.calib_canvas_btn.setEnabled(True))

        threading.Thread(target=_thread, daemon=True).start()

    def _auto_detect_canvas(self):
        """自动检测画布4角标记点"""
        if self.pixel_data is None:
            QMessageBox.warning(self, "提示", "请先导入 JSON 确定网格尺寸！")
            return

        self.auto_detect_btn.setEnabled(False)
        self._log("--- 自动检测画布（4角标记点）---")
        self._log("正在查找游戏窗口...")

        def _thread():
            try:
                # 1. 找到游戏窗口
                hwnd = find_game_window()
                if not hwnd:
                    self.signals.log_msg.emit("[!] 未找到游戏窗口，请确保心动小镇正在运行")
                    QTimer.singleShot(0, lambda: self.auto_detect_btn.setEnabled(True))
                    return

                # 2. 窗口置前
                bring_to_front(hwnd)
                time.sleep(0.5)  # 等窗口稳定

                # 3. 获取窗口坐标
                rect = get_window_rect(hwnd)
                if rect is None:
                    self.signals.log_msg.emit("[!] 无法获取窗口坐标")
                    QTimer.singleShot(0, lambda: self.auto_detect_btn.setEnabled(True))
                    return

                window_offset = (rect[0], rect[1])
                self.signals.log_msg.emit(f"  窗口位置: ({rect[0]}, {rect[1]}) - ({rect[2]}, {rect[3]})")

                # 4. 截图
                self.signals.log_msg.emit("  正在截图...")
                screenshot = capture_window(hwnd)
                if screenshot is None:
                    self.signals.log_msg.emit("[!] 截图失败")
                    QTimer.singleShot(0, lambda: self.auto_detect_btn.setEnabled(True))
                    return

                self.signals.log_msg.emit(f"  截图尺寸: {screenshot.size}")

                # 5. 检测标记点
                self.signals.log_msg.emit("  正在检测标记点...")
                tl, tr, bl, br = CanvasLocator.detect_markers(
                    screenshot, window_offset,
                    on_log=lambda msg: self.signals.log_msg.emit(msg),
                )

                self.signals.log_msg.emit(f"  [OK] 左上角: {tl}")
                self.signals.log_msg.emit(f"  [OK] 右上角: {tr}")
                self.signals.log_msg.emit(f"  [OK] 左下角: {bl}")
                self.signals.log_msg.emit(f"  [OK] 右下角: {br}")

                # 6. 标定
                self.locator.calibrate(
                    self.pixel_data.grid_width,
                    self.pixel_data.grid_height,
                    top_left=tl,
                    bottom_right=br,
                    top_right=tr,
                    bottom_left=bl,
                )
                self._save_calibration()
                self.signals.calibration_done.emit("画布")

            except RuntimeError as e:
                self.signals.log_msg.emit(f"[!] 检测失败: {e}")
            except Exception as e:
                self.signals.log_msg.emit(f"[!] 自动检测出错: {e}")
            finally:
                QTimer.singleShot(0, lambda: self.auto_detect_btn.setEnabled(True))

        threading.Thread(target=_thread, daemon=True).start()

    def _start_palette_calibration(self):
        self.calib_palette_btn.setEnabled(False)
        self._log("--- 开始标定调色板（共 4 步）---")
        self._log("(1) 鼠标停在色系标签【最左侧可见组】，按 Enter")

        def _thread():
            # 1. 标签左侧
            self._wait_for_enter()
            tab_l = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 标签左侧: {tab_l}")
            time.sleep(0.3)

            # 2. 标签右侧
            self.signals.log_msg.emit("(2) 鼠标停在色系标签【最右侧可见组】，按 Enter")
            self._wait_for_enter()
            tab_r = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 标签右侧: {tab_r}")
            time.sleep(0.3)

            # 3. 色块区域左上角
            self.signals.log_msg.emit("(3) 鼠标停在色块区域【左上角第一格】中心，按 Enter")
            self._wait_for_enter()
            block_tl = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 色块左上角: {block_tl}")
            time.sleep(0.3)

            # 4. 色块区域右下角
            self.signals.log_msg.emit("(4) 鼠标停在色块区域【右下角最后一格】中心，按 Enter")
            self._wait_for_enter()
            block_br = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 色块右下角: {block_br}")

            self.navigator.calibrate(tab_l, tab_r, block_tl, block_br)
            self._save_calibration()
            self.signals.calibration_done.emit("调色板")
            QTimer.singleShot(0, lambda: self.calib_palette_btn.setEnabled(True))

        threading.Thread(target=_thread, daemon=True).start()

    # ===== 标定持久化 =====

    def _save_calibration(self):
        """保存标定数据到文件"""
        data = {
            'canvas': self.locator.to_dict() if self.locator.calibrated else None,
            'palette': self.navigator.to_dict() if self.navigator.calibrated else None,
        }
        try:
            with open(CALIBRATION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.signals.log_msg.emit(f"  [save] 标定数据已保存到 {os.path.basename(CALIBRATION_FILE)}")
        except Exception as e:
            self.signals.log_msg.emit(f"  [!] 保存标定数据失败: {e}")

    def _load_calibration(self):
        """启动时自动加载标定数据"""
        if not os.path.exists(CALIBRATION_FILE):
            return

        try:
            with open(CALIBRATION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            canvas_data = data.get('canvas')
            palette_data = data.get('palette')

            if canvas_data:
                self.locator.from_dict(canvas_data)
                self._log(f"[OK] 已加载画布标定（{canvas_data['grid_width']}x{canvas_data['grid_height']}）")
                # 恢复微调偏移到 UI
                self.offset_x_spin.setValue(self.locator.offset_x)
                self.offset_y_spin.setValue(self.locator.offset_y)

            if palette_data:
                self.navigator.from_dict(palette_data)
                self._log(f"[OK] 已加载调色板标定")

            self._update_calib_status()

        except Exception as e:
            self._log(f"[!] 加载标定数据失败: {e}")

    def _update_calib_status(self):
        """更新标定状态显示"""
        parts = []
        if self.locator.calibrated:
            parts.append("画布 OK")
        else:
            parts.append("画布 X")

        if self.navigator.calibrated:
            parts.append("调色板 OK")
        else:
            parts.append("调色板 X")

        self.calib_status_label.setText("标定状态: " + "  |  ".join(parts))

        # 有任何一项标定了就可以清除
        self.recalib_btn.setEnabled(self.locator.calibrated or self.navigator.calibrated)

        # 两项都标定了才能测试 / 固定
        both_calibrated = self.locator.calibrated and self.navigator.calibrated
        self.test_calib_btn.setEnabled(both_calibrated)
        self.save_fixed_btn.setEnabled(both_calibrated)

    def _clear_calibration(self):
        """清除所有标定数据"""
        self.locator.reset()
        self.navigator.reset()

        # 删除保存的标定文件
        if os.path.exists(CALIBRATION_FILE):
            try:
                os.remove(CALIBRATION_FILE)
            except Exception:
                pass

        # 重置微调控件
        self.offset_x_spin.setValue(0)
        self.offset_y_spin.setValue(0)

        # 确保标定按钮可用
        self.calib_canvas_btn.setEnabled(True)
        self.calib_palette_btn.setEnabled(True)

        self._update_calib_status()
        self._check_ready()
        self._log("[OK] 标定数据已清除，请重新标定画布和调色板")

    # ===== 固定坐标功能 =====

    def _save_fixed_positions(self):
        """将当前标定保存为相对于游戏窗口的固定坐标（按比例存储画布配置）"""
        if not self.locator.calibrated or not self.navigator.calibrated:
            QMessageBox.warning(self, "提示", "请先完成画布和调色板标定！")
            return

        if not self.pixel_data or not self.pixel_data.ratio:
            QMessageBox.warning(self, "提示", "请先导入 JSON 数据（需要包含比例信息）！")
            return

        hwnd = find_game_window()
        if not hwnd:
            QMessageBox.warning(self, "未找到游戏", "请确保心动小镇正在运行")
            return

        rect = get_window_rect(hwnd)
        if rect is None:
            QMessageBox.warning(self, "错误", "无法获取窗口坐标")
            return

        window_offset = (rect[0], rect[1])
        ratio = self.pixel_data.ratio

        # 计算相对坐标
        canvas_rel = self.locator.compute_relative_corners(window_offset)
        palette_rel = self.navigator.compute_relative(window_offset)

        canvas_profile = {
            **canvas_rel,
            'grid_width': self.locator.grid_width,
            'grid_height': self.locator.grid_height,
            'offset_x': self.locator.offset_x,
            'offset_y': self.locator.offset_y,
        }

        # 读取现有数据（保留其他比例的配置和工具栏数据）
        data = {'canvas_profiles': {}, 'palette': None, 'toolbar': None}
        if os.path.exists(FIXED_POSITIONS_FILE):
            try:
                with open(FIXED_POSITIONS_FILE, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                # 兼容旧格式：迁移 canvas -> canvas_profiles
                if 'canvas' in old_data and 'canvas_profiles' not in old_data:
                    old_canvas = old_data['canvas']
                    old_ratio = self._guess_ratio(old_canvas.get('grid_width', 0), old_canvas.get('grid_height', 0))
                    if old_ratio:
                        data['canvas_profiles'][old_ratio] = old_canvas
                else:
                    data['canvas_profiles'] = old_data.get('canvas_profiles', {})
                data['palette'] = old_data.get('palette')
                data['toolbar'] = old_data.get('toolbar')
            except Exception:
                pass

        # 存入当前比例的画布配置
        data['canvas_profiles'][ratio] = canvas_profile
        data['palette'] = palette_rel

        try:
            with open(FIXED_POSITIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            profiles = list(data['canvas_profiles'].keys())
            self._log(f"[OK] 固定坐标已保存 — 比例: {ratio} ({self.locator.grid_width}x{self.locator.grid_height})")
            self._log(f"  已保存的画布配置: {', '.join(profiles)}")
            self._log(f"  窗口位置: {window_offset}")

            if not data.get('toolbar'):
                self._log(f"  [!] 如需使用油漆桶，请点击「🔧 标定工具栏」按钮")

            self.auto_fixed_btn.setEnabled(True)
            self.clear_fixed_btn.setEnabled(True)
        except Exception as e:
            self._log(f"[!] 保存固定坐标失败: {e}")

    @staticmethod
    def _guess_ratio(grid_w: int, grid_h: int) -> Optional[str]:
        """根据网格尺寸猜测比例"""
        if grid_w <= 0 or grid_h <= 0:
            return None
        GRID_DIMENSIONS = {
            '16:9': [[30, 18], [50, 28], [100, 56], [150, 84]],
            '4:3': [[30, 24], [50, 38], [100, 76], [150, 114]],
            '1:1': [[30, 30], [50, 50], [100, 100], [150, 150]],
            '3:4': [[24, 30], [38, 50], [76, 100], [114, 150]],
            '9:16': [[18, 30], [28, 50], [56, 100], [84, 150]],
        }
        for ratio, levels in GRID_DIMENSIONS.items():
            for w, h in levels:
                if w == grid_w and h == grid_h:
                    return ratio
        return None

    def _start_toolbar_calibration(self):
        """标定工具栏中画笔和油漆桶的位置"""
        self._log("--- 开始标定工具栏 ---")
        self._log("(1/2) 请切到游戏，鼠标停在【画笔工具】上，按 Enter")

        def _thread():
            # 1. 画笔
            self._wait_for_enter()
            brush_pos = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 画笔工具: {brush_pos}")
            time.sleep(0.3)

            # 2. 油漆桶
            self.signals.log_msg.emit("(2/2) 鼠标停在【油漆桶工具】上，按 Enter")
            self._wait_for_enter()
            bucket_pos = self._mouse_getter.position()
            self.signals.log_msg.emit(f"  [OK] 油漆桶工具: {bucket_pos}")

            # 读取当前窗口位置，计算相对坐标
            hwnd = find_game_window()
            if hwnd:
                rect = get_window_rect(hwnd)
                if rect:
                    wx, wy = rect[0], rect[1]
                    toolbar_data = {
                        'brush': [brush_pos[0] - wx, brush_pos[1] - wy],
                        'bucket': [bucket_pos[0] - wx, bucket_pos[1] - wy],
                    }

                    # 更新固定坐标文件
                    if os.path.exists(FIXED_POSITIONS_FILE):
                        try:
                            with open(FIXED_POSITIONS_FILE, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            data['toolbar'] = toolbar_data
                            with open(FIXED_POSITIONS_FILE, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                            self.signals.log_msg.emit(f"  [OK] 工具栏位置已保存")
                            self.signals.log_msg.emit(f"  画笔相对坐标: {toolbar_data['brush']}")
                            self.signals.log_msg.emit(f"  油漆桶相对坐标: {toolbar_data['bucket']}")
                        except Exception as e:
                            self.signals.log_msg.emit(f"  [!] 保存工具栏位置失败: {e}")
                    else:
                        self.signals.log_msg.emit(f"  [!] 固定坐标文件不存在，请先保存固定坐标")

        threading.Thread(target=_thread, daemon=True).start()

    def _apply_fixed_positions(self):
        """使用已保存的固定坐标 + 当前游戏窗口位置自动标定"""
        if not os.path.exists(FIXED_POSITIONS_FILE):
            QMessageBox.warning(self, "提示", "没有保存的固定坐标，请先标定并保存")
            return

        if not self.pixel_data or not self.pixel_data.ratio:
            QMessageBox.warning(self, "提示", "请先导入 JSON 数据（需要比例信息）")
            return

        hwnd = find_game_window()
        if not hwnd:
            QMessageBox.warning(self, "未找到游戏", "请确保心动小镇正在运行")
            return

        rect = get_window_rect(hwnd)
        if rect is None:
            QMessageBox.warning(self, "错误", "无法获取窗口坐标")
            return

        window_offset = (rect[0], rect[1])
        ratio = self.pixel_data.ratio

        try:
            with open(FIXED_POSITIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 查找画布配置（优先用 canvas_profiles，兼容旧格式 canvas）
            canvas_data = None
            profiles = data.get('canvas_profiles', {})
            if ratio in profiles:
                canvas_data = profiles[ratio]
            elif 'canvas' in data:
                # 旧格式兼容
                canvas_data = data['canvas']
                self._log(f"  [i] 使用旧格式画布配置（建议重新保存固定坐标）")

            if canvas_data:
                grid_w = canvas_data.get('grid_width', 0)
                grid_h = canvas_data.get('grid_height', 0)

                if grid_w > 0 and grid_h > 0:
                    self.locator.calibrate_from_window(grid_w, grid_h, window_offset, canvas_data)
                    self.locator.set_offset(
                        canvas_data.get('offset_x', 0),
                        canvas_data.get('offset_y', 0)
                    )
                    self.offset_x_spin.setValue(self.locator.offset_x)
                    self.offset_y_spin.setValue(self.locator.offset_y)
                    self._log(f"[OK] 画布已自动标定 — {ratio} ({grid_w}x{grid_h})")
            else:
                available = list(profiles.keys())
                self._log(f"[!] 无比例 {ratio} 的画布配置（已有: {', '.join(available) if available else '无'}）")

            # 调色板和工具栏
            self._apply_palette_and_toolbar(data, window_offset)
            if data.get('palette'):
                self._log(f"[OK] 调色板已自动标定")
            if data.get('toolbar'):
                self._log(f"[OK] 工具栏已定位")
            else:
                self._log(f"[!] 无工具栏数据，油漆桶不可用")

            self._log(f"  窗口位置: {window_offset}")
            self._update_calib_status()
            self._save_calibration()
            self._check_ready()

        except Exception as e:
            self._log(f"[!] 自动标定失败: {e}")

    def _clear_fixed_positions(self):
        """清除固定坐标文件"""
        if os.path.exists(FIXED_POSITIONS_FILE):
            try:
                os.remove(FIXED_POSITIONS_FILE)
                self._log("[OK] 固定坐标已清除")
            except Exception as e:
                self._log(f"[!] 清除失败: {e}")

        self.auto_fixed_btn.setEnabled(False)
        self.clear_fixed_btn.setEnabled(False)

    def _auto_switch_canvas_profile(self):
        """根据当前 pixel_data 的比例自动切换画布配置"""
        if not self.pixel_data or not self.pixel_data.ratio:
            return
        if not os.path.exists(FIXED_POSITIONS_FILE):
            return

        ratio = self.pixel_data.ratio
        try:
            with open(FIXED_POSITIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 兼容旧格式：如果有 canvas 但没有 canvas_profiles，不处理
            profiles = data.get('canvas_profiles', {})
            if ratio in profiles:
                canvas_data = profiles[ratio]
                grid_w = canvas_data.get('grid_width', 0)
                grid_h = canvas_data.get('grid_height', 0)

                if grid_w == self.pixel_data.grid_width and grid_h == self.pixel_data.grid_height:
                    # 尺寸完全匹配，自动应用
                    hwnd = find_game_window()
                    if hwnd:
                        rect = get_window_rect(hwnd)
                        if rect:
                            window_offset = (rect[0], rect[1])
                            self.locator.calibrate_from_window(grid_w, grid_h, window_offset, canvas_data)
                            self.locator.set_offset(
                                canvas_data.get('offset_x', 0),
                                canvas_data.get('offset_y', 0)
                            )
                            self.offset_x_spin.setValue(self.locator.offset_x)
                            self.offset_y_spin.setValue(self.locator.offset_y)
                            self._log(f"  [OK] 自动切换画布配置: {ratio} ({grid_w}x{grid_h})")

                            # 同时应用调色板和工具栏
                            self._apply_palette_and_toolbar(data, window_offset)

                            self._update_calib_status()
                            self._save_calibration()
                            self._check_ready()
                            return

                self._log(f"  [i] 找到比例 {ratio} 的画布配置，但尺寸不匹配 "
                          f"(保存={grid_w}x{grid_h}, 当前={self.pixel_data.grid_width}x{self.pixel_data.grid_height})")
            else:
                available = list(profiles.keys())
                if available:
                    self._log(f"  [i] 无比例 {ratio} 的画布配置（已有: {', '.join(available)}），请手动标定")
                # 没有任何 profile 就不提示

        except Exception as e:
            self._log(f"  [!] 自动切换画布配置失败: {e}")

    def _apply_palette_and_toolbar(self, data: dict, window_offset: Tuple):
        """应用调色板和工具栏配置（从固定坐标数据）"""
        wx, wy = window_offset

        palette_data = data.get('palette')
        if palette_data:
            self.navigator.calibrate_from_window(window_offset, palette_data)

        toolbar_data = data.get('toolbar')
        if toolbar_data:
            brush_pos = (wx + toolbar_data['brush'][0], wy + toolbar_data['brush'][1])
            bucket_pos = (wx + toolbar_data['bucket'][0], wy + toolbar_data['bucket'][1])
            self.engine.set_bucket_fill(True, brush_pos, bucket_pos)
            self.bucket_fill_cb.setChecked(True)

    def _on_bucket_fill_changed(self, state):
        """油漆桶开关变化"""
        enabled = bool(state)
        if enabled:
            # 检查是否有工具栏位置
            if os.path.exists(FIXED_POSITIONS_FILE):
                try:
                    with open(FIXED_POSITIONS_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    toolbar = data.get('toolbar')
                    if toolbar:
                        hwnd = find_game_window()
                        if hwnd:
                            rect = get_window_rect(hwnd)
                            if rect:
                                wx, wy = rect[0], rect[1]
                                brush_pos = (wx + toolbar['brush'][0], wy + toolbar['brush'][1])
                                bucket_pos = (wx + toolbar['bucket'][0], wy + toolbar['bucket'][1])
                                self.engine.set_bucket_fill(True, brush_pos, bucket_pos)
                                self._log("[OK] 油漆桶填充已启用")
                                return
                except Exception:
                    pass
            self._log("[!] 需要先保存固定坐标（含工具栏位置）才能使用油漆桶")
            self.bucket_fill_cb.setChecked(False)
        else:
            self.engine.set_bucket_fill(False)
            self._log("[OK] 油漆桶填充已禁用")

    def _test_calibration(self):
        """测试标定：沿画布边框画一圈黑红交替"""
        if not self.locator.calibrated or not self.navigator.calibrated:
            QMessageBox.warning(self, "提示", "请先完成画布和调色板标定！")
            return

        hwnd = find_game_window()
        if not hwnd:
            QMessageBox.warning(self, "未找到游戏", "请确保心动小镇正在运行")
            return

        bring_to_front(hwnd)

        self.test_calib_btn.setEnabled(False)
        self._log("--- 开始测试标定（画边框）---")

        def on_log(msg):
            self.signals.log_msg.emit(msg)

        def on_done():
            QTimer.singleShot(0, lambda: self.test_calib_btn.setEnabled(True))

        self.engine.test_border(on_log=on_log, on_done=on_done)

    def _on_offset_changed(self):
        """微调偏移值变化时更新 locator 并保存"""
        ox = self.offset_x_spin.value()
        oy = self.offset_y_spin.value()
        self.locator.set_offset(ox, oy)

        # 自动保存到标定文件（不刷日志，避免频繁输出）
        if self.locator.calibrated:
            self._save_calibration_quiet()

    def _save_calibration_quiet(self):
        """静默保存标定数据（不输出日志）"""
        data = {
            'canvas': self.locator.to_dict() if self.locator.calibrated else None,
            'palette': self.navigator.to_dict() if self.navigator.calibrated else None,
        }
        try:
            with open(CALIBRATION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _reset_offset(self):
        """重置偏移到 (0, 0)"""
        self.offset_x_spin.setValue(0)
        self.offset_y_spin.setValue(0)

    # ===== 画画控制 =====

    def _check_ready(self):
        gw = self.pixel_data.grid_width if self.pixel_data else 0
        if self.locator.calibrated and self.navigator.calibrated and gw > 0:
            # 检查标定尺寸是否匹配当前数据
            if (self.locator.grid_width != self.pixel_data.grid_width or
                    self.locator.grid_height != self.pixel_data.grid_height):
                self._log(
                    f"[!] 画布标定尺寸({self.locator.grid_width}x{self.locator.grid_height}) "
                    f"与数据尺寸({self.pixel_data.grid_width}x{self.pixel_data.grid_height})不匹配，"
                    f"请重新标定画布"
                )
                self.start_btn.setEnabled(False)
                return
            self.start_btn.setEnabled(True)

    def _on_calibration_done(self, typ: str):
        self._log(f"[done] {typ}标定完成！")
        self._update_calib_status()
        self._check_ready()

    def _start_painting(self):
        if not self.locator.calibrated or not self.navigator.calibrated:
            self._log("[!] 还没标定完，拒绝启动")
            return

        if self.pixel_data is None:
            self._log("[!] 未导入数据")
            return

        hwnd = find_game_window()
        if not hwnd:
            QMessageBox.warning(self, "未找到游戏", "请确保心动小镇正在运行")
            return

        bring_to_front(hwnd)

        # 设置速度
        speed_map = {0: 'very_slow', 1: 'slow', 2: 'normal', 3: 'fast'}
        self.engine.set_speed(speed_map.get(self.speed_combo.currentIndex(), 'normal'))

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)

        now = time.strftime("%H:%M:%S")
        self._paint_start_time = time.time()
        self._log(f"[{now}] 开始绘画")
        self._log("请不要动鼠标...绘画即将开始")

        self.engine.start(resume_from_checkpoint=False)

    def _resume_painting(self):
        """断点续画"""
        if not self.locator.calibrated or not self.navigator.calibrated:
            self._log("[!] 还没标定完")
            return

        hwnd = find_game_window()
        if not hwnd:
            QMessageBox.warning(self, "未找到游戏", "请确保心动小镇正在运行")
            return

        bring_to_front(hwnd)

        speed_map = {0: 'very_slow', 1: 'slow', 2: 'normal', 3: 'fast'}
        self.engine.set_speed(speed_map.get(self.speed_combo.currentIndex(), 'normal'))

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)

        now = time.strftime("%H:%M:%S")
        self._paint_start_time = time.time()
        self._log(f"[{now}] 从上次中断处继续绘画...")

        self.engine.start(resume_from_checkpoint=True)

    def _pause_painting(self):
        if self.engine.is_running:
            if self.engine.is_paused:
                self.engine.resume()
                self.pause_btn.setText("|| 暂停 (F6)")
                self._log(">> 继续绘画")
            else:
                self.engine.pause()
                self.pause_btn.setText(">> 恢复 (F6)")
                self._log("|| 已暂停")

    def _stop_painting_hotkey(self):
        if self.engine.is_running:
            self.engine.stop()
            self._log("[stop] 收到 F7，停止绘画（进度已保存）")
            QTimer.singleShot(0, lambda: self.start_btn.setEnabled(True))
            QTimer.singleShot(0, lambda: self.pause_btn.setEnabled(False))
            QTimer.singleShot(0, lambda: self.resume_btn.setEnabled(True))

    # ===== 进度回调（通过信号在 GUI 线程执行）=====

    def _on_progress(self, drawn: int, total: int):
        # 计算预估剩余时间
        eta_str = ""
        if drawn > 0 and self._paint_start_time > 0:
            elapsed = time.time() - self._paint_start_time
            speed = drawn / elapsed  # pixels per second
            remaining = (total - drawn) / speed if speed > 0 else 0
            if remaining >= 3600:
                eta_str = f" — 预估剩余: {int(remaining // 3600)}时{int(remaining % 3600 // 60)}分"
            elif remaining >= 60:
                eta_str = f" — 预估剩余: {int(remaining // 60)}分{int(remaining % 60)}秒"
            else:
                eta_str = f" — 预估剩余: {int(remaining)}秒"

        self.prog_label.setText(f"当前进度: {drawn}/{total} 色块{eta_str}")
        if total > 0:
            self.progress_bar.setValue(int((drawn / total) * 100))

    def _on_color_change(self, group_key: str, idx: int, total: int):
        self.color_label.setText(f"当前颜色: {group_key} ({idx}/{total})")
        # 尝试从 group_key 解析颜色来显示预览
        try:
            from shared.palette import COLOR_GROUPS
            parts = group_key.split('-')
            g, c = int(parts[0]), int(parts[1])
            hex_color = COLOR_GROUPS[g][1][c]
            self.preview_box.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #999;")
        except (IndexError, ValueError):
            self.preview_box.setStyleSheet("background-color: transparent; border: 1px solid #999;")

    def _on_error(self, err_msg: str):
        self._log(f"[ERROR] {err_msg}")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)

    def _on_finished(self):
        now = time.strftime("%H:%M:%S")
        duration_str = ""
        if self._paint_start_time > 0:
            elapsed = time.time() - self._paint_start_time
            if elapsed >= 3600:
                duration_str = f"{int(elapsed // 3600)}时{int(elapsed % 3600 // 60)}分{int(elapsed % 60)}秒"
            elif elapsed >= 60:
                duration_str = f"{int(elapsed // 60)}分{int(elapsed % 60)}秒"
            else:
                duration_str = f"{int(elapsed)}秒"
        self._log(f"[{now}] 结束绘画 — 用时: {duration_str}")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)


# ===== 程序入口 =====

def main():
    import ctypes

    # ===== 自动请求管理员权限 =====
    # 心动小镇以管理员权限运行，Windows UIPI 会拦截低权限进程的鼠标点击事件。
    # 必须以管理员身份运行脚本，否则鼠标能移动但点击无效。
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    if not is_admin:
        # 用 ShellExecuteW 以 "runas" 重新启动自身
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                " ".join([f'"{arg}"' for arg in sys.argv]),
                None, 1  # SW_SHOWNORMAL
            )
        except Exception:
            pass
        sys.exit(0)

    # ===== 隐藏控制台窗口 =====
    try:
        hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd_console:
            ctypes.windll.user32.ShowWindow(hwnd_console, 0)  # SW_HIDE
    except Exception:
        pass

    # 强制 DPI 感知，确保坐标 1:1
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # 压制 Qt DPI 警告
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

    app = QApplication(sys.argv)

    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = AutoPainterGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
