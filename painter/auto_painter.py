"""
心动小镇自动画画脚本 — GUI 控制面板（主程序入口）

集成各个模块，提供导入数据、标定画布、控制画画流程的图形界面。
"""

import sys
import json
import logging
import threading
import time
import pyautogui
import keyboard

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout, QProgressBar, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject

from window_manager import find_game_window, bring_to_front
from canvas_locator import CanvasLocator
from palette_navigator import PaletteNavigator
from paint_engine import PaintEngine
from config import SPEED_PRESETS


class WorkerSignals(QObject):
    log_msg = Signal(str)
    calibration_done = Signal(str)
    
class AutoPainterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("心动小镇 — 自动画画脚本")
        self.setMinimumSize(500, 600)

        # 信号
        self.signals = WorkerSignals()
        self.signals.log_msg.connect(self.log)
        self.signals.calibration_done.connect(self._on_calibration_done)

        # 核心模块
        self.locator = CanvasLocator()
        self.navigator = PaletteNavigator()
        self.engine = PaintEngine(self.locator, self.navigator)

        # 绑定引擎回调
        self.engine.on_progress = self._on_progress
        self.engine.on_color_change = self._on_color_change
        self.engine.on_finished = self._on_finished
        self.engine.on_error = self._on_error

        # 主网格像素数据
        self.pixels = []
        self.grid_width = 0
        self.grid_height = 0

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 1. 数据导入 ---
        data_group = QGroupBox("1. 像素数据导入")
        data_layout = QGridLayout(data_group)

        self.import_btn = QPushButton("导入 JSON 文件")
        self.import_btn.clicked.connect(self.import_json)
        data_layout.addWidget(self.import_btn, 0, 0)

        self.data_label = QLabel("未加载数据")
        data_layout.addWidget(self.data_label, 0, 1)
        main_layout.addWidget(data_group)

        # --- 2. 标定 ---
        calib_group = QGroupBox("2. 坐标标定（在游戏中操作）")
        calib_layout = QVBoxLayout(calib_group)

        # 这里简略，需要完善交互体验...
        self.calib_canvas_btn = QPushButton("标定画板范围 (左上角 -> 右下角)")
        self.calib_canvas_btn.setToolTip("点击后切回游戏，鼠标移动到画布左上角按 Enter，再移动到右下角按 Enter")
        self.calib_canvas_btn.clicked.connect(self._start_canvas_calibration)
        calib_layout.addWidget(self.calib_canvas_btn)

        self.calib_palette_btn = QPushButton("标定调色板选项")
        self.calib_palette_btn.setToolTip("标定翻页按钮、色块区域")
        self.calib_palette_btn.clicked.connect(self._start_palette_calibration)
        calib_layout.addWidget(self.calib_palette_btn)
        main_layout.addWidget(calib_group)

        # --- 3. 颜色组验证与速度 ---
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

        self.start_btn = QPushButton("开始画画 (F5)")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_painting)
        ctrl_layout.addWidget(self.start_btn, 1, 0)

        self.pause_btn = QPushButton("暂停 (F6)")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_painting)
        ctrl_layout.addWidget(self.pause_btn, 1, 1)

        main_layout.addWidget(ctrl_group)

        # --- 4. 进度条 ---
        prog_group = QGroupBox("4. 进度")
        prog_layout = QVBoxLayout(prog_group)
        self.prog_label = QLabel("当前进度: 0/0")
        prog_layout.addWidget(self.prog_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        self.color_label = QLabel("当前颜色: 无")
        prog_layout.addWidget(self.color_label)

        self.preview_box = QLabel()
        self.preview_box.setFixedSize(50, 50)
        self.preview_box.setStyleSheet("background-color: transparent; border: 1px solid black;")
        prog_layout.addWidget(self.preview_box)

        main_layout.addWidget(prog_group)

        # 日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        main_layout.addWidget(self.log_text)

        # 注册全局热键（防止阻塞，在主线程跑）
        keyboard.add_hotkey('F5', self.start_painting)
        keyboard.add_hotkey('F6', self.pause_painting)
        keyboard.add_hotkey('F7', self._stop_painting_hotkey)

    def log(self, text: str):
        self.log_text.append(text)
        self.log_text.ensureCursorVisible()

    def _stop_painting_hotkey(self):
        if self.engine.is_running:
            self.engine.stop()
            self.log("⏹ 接收到快捷键，强制停止绘画")
            QTimer.singleShot(0, lambda: self.start_btn.setEnabled(True))
            QTimer.singleShot(0, lambda: self.pause_btn.setEnabled(False))

    def import_json(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择像素矩阵 JSON", "", "JSON (*.json)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'pixels' not in data:
                QMessageBox.warning(self, "错误", "这不是有效的像素矩阵 JSON (缺少 'pixels' 字段)")
                return

            self.pixels = data['pixels']
            self.grid_height = len(self.pixels)
            self.grid_width = len(self.pixels[0]) if self.grid_height > 0 else 0

            self.data_label.setText(f"已加载: {self.grid_width}x{self.grid_height} 矩阵")
            self.log(f"成功导入 {self.grid_width}x{self.grid_height} 像素数据。")

            # 将像素加载到引擎，计算总掉落点等
            self.engine.load_pixels(self.pixels)
            self.log(f"总计需要绘制像素点: {self.engine.total_pixels}")
            
            # 后续需要等标定后才启用开始按钮
            # self.start_btn.setEnabled(True) 
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解析失败:\n{e}")

    # ===== 回调方法 =====
    def _on_progress(self, drawn: int, total: int):
        self.prog_label.setText(f"当前进度: {drawn}/{total}")
        if total > 0:
            pct = int((drawn / total) * 100)
            self.progress_bar.setValue(pct)

    def _on_color_change(self, hex_color: str, color_idx: int, total_colors: int):
        self.color_label.setText(f"当前颜色: {hex_color} ({color_idx}/{total_colors})")
        self.preview_box.setStyleSheet(f"background-color: {hex_color}; border: 1px solid black;")

    def _on_error(self, err_msg: str):
        self.signals.log_msg.emit(f"错误: {err_msg}")
        QMessageBox.critical(self, "执行错误", err_msg)

    def _on_finished(self):
        self.signals.log_msg.emit("✅ 绘画完成！")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)

    def _check_ready(self):
        if self.locator.calibrated and self.navigator.calibrated and self.grid_width > 0:
            self.start_btn.setEnabled(True)

    def _on_calibration_done(self, typ: str):
        self.log(f"🎉 {typ}标定完成！")
        self._check_ready()

    # ===== 标定流程 =====
    def _wait_for_enter(self):
        """安全地等待 Enter 键按下，并在释放前阻塞"""
        while keyboard.is_pressed('enter'):
            time.sleep(0.05)
        while not keyboard.is_pressed('enter'):
            time.sleep(0.05)

    def _start_canvas_calibration(self):
        if self.grid_width == 0:
            QMessageBox.warning(self, "提示", "请先导入 JSON 确定网格尺寸！")
            return
            
        self.calib_canvas_btn.setEnabled(False)
        self.log("--- 开始标定画布 ---")
        self.log("请点击游戏窗口，把鼠标停留在【左上角第一个画格】的中心，然后按 Enter 键")

        def _calib_thread():
            # 左上角
            self._wait_for_enter()
            p1 = pyautogui.position()
            self.signals.log_msg.emit(f"✓ 记录左上角: {p1}")
            time.sleep(0.3)
            self.signals.log_msg.emit("请把鼠标停留在【右下角最后一个画格】的中心，按 Enter 键")

            # 右下角
            self._wait_for_enter()
            p2 = pyautogui.position()
            self.signals.log_msg.emit(f"✓ 记录右下角: {p2}")

            self.locator.calibrate(self.grid_width, self.grid_height, (p1.x, p1.y), (p2.x, p2.y))
            self.signals.calibration_done.emit("画布")
            
            # 恢复按钮
            QTimer.singleShot(0, lambda: self.calib_canvas_btn.setEnabled(True))

        threading.Thread(target=_calib_thread, daemon=True).start()

    def _start_palette_calibration(self):
        self.calib_palette_btn.setEnabled(False)
        self.log("--- 开始调色板标定 ---")
        self.log("鼠标移动到上方色系标签中【最左侧可见的组】，按 Enter (翻页起点)")

        def _calib_thread():
            # 1. 向左翻页点
            self._wait_for_enter()
            ptab_l = pyautogui.position()
            self.signals.log_msg.emit(f"✓ 记录标签左侧: {ptab_l}")
            time.sleep(0.3)
            
            self.signals.log_msg.emit("鼠标移动到上方色系标签中【最右侧可见的组】，按 Enter (用作向右翻页点)")
            self._wait_for_enter()
            ptab_r = pyautogui.position()
            self.signals.log_msg.emit(f"✓ 记录标签右侧: {ptab_r}")
            time.sleep(0.3)

            tabs = {
                'left_tab': (ptab_l.x, ptab_l.y),
                'right_tab': (ptab_r.x, ptab_r.y)
            }
            self.navigator.calibrate_tabs(tabs)

            self.signals.log_msg.emit("接下来录入 10 个色块坐标（从第 1排左 依次到 第 5排右）")
            blocks = {}
            for i in range(10):
                self.signals.log_msg.emit(f"请指向上方第 {i//2 + 1}排 {'左' if i%2==0 else '右'}侧色块，按 Enter:")
                self._wait_for_enter()
                pb = pyautogui.position()
                blocks[i] = (pb.x, pb.y)
                self.signals.log_msg.emit(f"✓ 记录色块 {i}: {blocks[i]}")
                time.sleep(0.2)
                
            self.navigator.calibrate_blocks(blocks)
            self.signals.calibration_done.emit("调色板")
            QTimer.singleShot(0, lambda: self.calib_palette_btn.setEnabled(True))

        threading.Thread(target=_calib_thread, daemon=True).start()

    def start_painting(self):
        if not self.locator.calibrated or not self.navigator.calibrated:
            self.log("⚠️ 还没标定完，拒绝启动。")
            return
            
        hwnd = find_game_window()
        if not hwnd:
            QMessageBox.warning(self, "未找到游戏", "请确保心动小镇游戏正处于运行状态。")
            return
        
        bring_to_front(hwnd)
        
        speed_idx = self.speed_combo.currentIndex()
        if speed_idx == 0: self.engine.set_speed('very_slow')
        elif speed_idx == 1: self.engine.set_speed('slow')
        elif speed_idx == 2: self.engine.set_speed('normal')
        else: self.engine.set_speed('fast')

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        
        self.log("请不要动鼠标...绘画即将开始。")
        self.engine.start()

    def pause_painting(self):
        if self.engine.is_running:
            if self.engine.is_paused:
                self.engine.resume()
                self.pause_btn.setText("暂停 (F6)")
                self.log("▶ 继续绘画")
            else:
                self.engine.pause()
                self.pause_btn.setText("恢复 (F6)")
                self.log("⏸ 已暂停")


def main():
    import ctypes
    import os
    # 强制声明进程 DPI 感知，避免因为 Windows 系统的 125% 或 150% 缩放导致 pyautogui 取到的坐标变小、变偏
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    
    # 压制 Qt 控制台对 DPI Context 的警告
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    
    app = QApplication(sys.argv)
    
    # 全局字体
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)
    
    window = AutoPainterGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
