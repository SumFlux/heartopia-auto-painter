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

# 确保能导入项目根目录的 shared 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout, QProgressBar, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject

from shared.pixel_data import PixelData
from window_manager import find_game_window, bring_to_front
from canvas_locator import CanvasLocator
from palette_navigator import PaletteNavigator
from paint_engine import PaintEngine
from mouse_input import PynputBackend, InputBackend, create_backend
from config import SPEED_PRESETS


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

        self.calib_palette_btn = QPushButton("标定调色板（左右标签 + 色块区域，共 4 次 Enter）")
        self.calib_palette_btn.setToolTip("依次标定：标签最左 -> 标签最右 -> 色块左上第一格 -> 色块右下最后一格")
        self.calib_palette_btn.clicked.connect(self._start_palette_calibration)
        calib_layout.addWidget(self.calib_palette_btn)

        self.calib_status_label = QLabel("")
        calib_layout.addWidget(self.calib_status_label)

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

        self.start_btn = QPushButton(">> 开始画画 (F5)")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_painting)
        ctrl_layout.addWidget(self.start_btn, 1, 0)

        self.pause_btn = QPushButton("|| 暂停 (F6)")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._pause_painting)
        ctrl_layout.addWidget(self.pause_btn, 1, 1)

        self.resume_btn = QPushButton("~ 断点续画")
        self.resume_btn.setEnabled(False)
        self.resume_btn.setToolTip("从上次中断的位置继续绘画")
        self.resume_btn.clicked.connect(self._resume_painting)
        ctrl_layout.addWidget(self.resume_btn, 2, 0, 1, 2)

        main_layout.addWidget(ctrl_group)

        # --- 4. 进度 ---
        prog_group = QGroupBox("4. 进度")
        prog_layout = QVBoxLayout(prog_group)

        self.prog_label = QLabel("当前进度: 0/0")
        prog_layout.addWidget(self.prog_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
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

            self.data_label.setText(
                f"已加载: {self.pixel_data.grid_width}x{self.pixel_data.grid_height} 矩阵"
            )
            self._log(f"[OK] 成功导入 {self.pixel_data.grid_width}x{self.pixel_data.grid_height} 像素数据")

            self.engine.load_pixel_data(self.pixel_data)
            self._log(f"  需要绘制: {self.engine.total_pixels} 个像素点")

            if self.pixel_data.has_color_ids():
                self._log(f"  [OK] 数据包含 colorId，将使用精确定位")
            else:
                self._log(f"  [!] 数据不含 colorId，将使用最近邻匹配（可能有偏差）")

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
        self._log("从上次中断处继续绘画...")

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
        self.prog_label.setText(f"当前进度: {drawn}/{total}")
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
        self._log("[DONE] 绘画完成！")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)


# ===== 程序入口 =====

def main():
    import ctypes

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
