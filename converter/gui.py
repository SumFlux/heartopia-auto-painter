#!/usr/bin/env python3
"""
Heartopia Painting Tools - GUI 版本
图形化界面，支持图片导入、参数选择、实时预览
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout, QScrollArea, QCheckBox, QSlider
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import numpy as np

from heartopia_converter import HeartopiaPixelArt


class ConversionThread(QThread):
    """转换线程（避免 UI 卡顿）"""
    finished = Signal(object, object)  # 转换完成信号
    error = Signal(str)  # 错误信号

    def __init__(self, image_path, ratio, level, enhance=False, dither=False,
                 saturation=1.3, contrast=1.2, sharpness=1.3):
        super().__init__()
        self.image_path = image_path
        self.ratio = ratio
        self.level = level
        self.enhance = enhance
        self.dither = dither
        self.saturation = saturation
        self.contrast = contrast
        self.sharpness = sharpness

    def run(self):
        try:
            converter = HeartopiaPixelArt(ratio=self.ratio, level=self.level)
            converter.process_image(
                self.image_path,
                enhance=self.enhance,
                dither=self.dither,
                saturation=self.saturation,
                contrast=self.contrast,
                sharpness=self.sharpness
            )
            self.finished.emit(converter, converter.pixel_grid)
        except Exception as e:
            self.error.emit(str(e))


class HeartopiaGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_path = None
        self.converter = None
        self.pixel_grid = None

        self.init_ui()

    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle('Heartopia Painting Tools - 图片转换器')
        self.setMinimumSize(1000, 700)

        # 主窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 左侧：控制面板
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, stretch=1)

        # 右侧：预览区域
        right_panel = self.create_preview_panel()
        main_layout.addWidget(right_panel, stretch=2)

    def create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 1. 图片选择
        image_group = QGroupBox("1. 选择图片")
        image_layout = QVBoxLayout()

        self.image_label = QLabel("未选择图片")
        self.image_label.setWordWrap(True)
        image_layout.addWidget(self.image_label)

        select_btn = QPushButton("选择图片")
        select_btn.clicked.connect(self.select_image)
        image_layout.addWidget(select_btn)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group)

        # 2. 参数配置
        config_group = QGroupBox("2. 配置参数")
        config_layout = QGridLayout()

        # 画布比例
        config_layout.addWidget(QLabel("画布比例:"), 0, 0)
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(['16:9', '4:3', '1:1', '3:4', '9:16'])
        self.ratio_combo.setCurrentText('1:1')
        self.ratio_combo.currentTextChanged.connect(self.update_grid_info)
        config_layout.addWidget(self.ratio_combo, 0, 1)

        # 精细度
        config_layout.addWidget(QLabel("精细度:"), 1, 0)
        self.level_combo = QComboBox()
        self.level_combo.addItems([
            'Level 0 (最快)',
            'Level 1 (快)',
            'Level 2 (中等)',
            'Level 3 (精细)'
        ])
        self.level_combo.setCurrentIndex(2)
        self.level_combo.currentTextChanged.connect(self.update_grid_info)
        config_layout.addWidget(self.level_combo, 1, 1)

        # 网格尺寸显示
        self.grid_info_label = QLabel()
        self.update_grid_info()
        config_layout.addWidget(self.grid_info_label, 2, 0, 1, 2)

        # 图像增强复选框与恢复默认按钮
        enhance_layout = QHBoxLayout()
        enhance_layout.setContentsMargins(0, 0, 0, 0)

        self.enhance_check = QCheckBox("图像增强")
        self.enhance_check.setToolTip("勾选后启用下方的饱和度/对比度/锐度调节")
        self.enhance_check.stateChanged.connect(self._on_enhance_toggled)
        enhance_layout.addWidget(self.enhance_check)

        self.reset_btn = QPushButton("恢复默认")
        self.reset_btn.setToolTip("恢复饱和度1.3、对比度1.2、锐度1.3的默认值")
        self.reset_btn.setEnabled(False)
        self.reset_btn.setMaximumWidth(80)
        self.reset_btn.clicked.connect(self._reset_sliders)
        enhance_layout.addWidget(self.reset_btn)
        
        enhance_layout.addStretch()
        config_layout.addLayout(enhance_layout, 3, 0, 1, 2)

        # 饱和度滑块
        config_layout.addWidget(QLabel("饱和度:"), 4, 0)
        sat_layout = QHBoxLayout()
        sat_layout.setContentsMargins(0, 0, 0, 0)
        self.sat_slider = QSlider(Qt.Horizontal)
        self.sat_slider.setRange(0, 40)   # 0~40 映射到 0.0~4.0
        self.sat_slider.setValue(13)       # 默认 1.3
        self.sat_slider.setEnabled(False)
        self.sat_label = QLabel("1.3")
        self.sat_label.setFixedWidth(30)
        self.sat_slider.valueChanged.connect(lambda v: self.sat_label.setText(f"{v/10:.1f}"))
        sat_layout.addWidget(self.sat_slider)
        sat_layout.addWidget(self.sat_label)
        config_layout.addLayout(sat_layout, 4, 1)

        # 对比度滑块
        config_layout.addWidget(QLabel("对比度:"), 5, 0)
        con_layout = QHBoxLayout()
        con_layout.setContentsMargins(0, 0, 0, 0)
        self.con_slider = QSlider(Qt.Horizontal)
        self.con_slider.setRange(0, 40)
        self.con_slider.setValue(12)       # 默认 1.2
        self.con_slider.setEnabled(False)
        self.con_label = QLabel("1.2")
        self.con_label.setFixedWidth(30)
        self.con_slider.valueChanged.connect(lambda v: self.con_label.setText(f"{v/10:.1f}"))
        con_layout.addWidget(self.con_slider)
        con_layout.addWidget(self.con_label)
        config_layout.addLayout(con_layout, 5, 1)

        # 锐度滑块
        config_layout.addWidget(QLabel("锐度:"), 6, 0)
        sha_layout = QHBoxLayout()
        sha_layout.setContentsMargins(0, 0, 0, 0)
        self.sha_slider = QSlider(Qt.Horizontal)
        self.sha_slider.setRange(0, 40)
        self.sha_slider.setValue(13)       # 默认 1.3
        self.sha_slider.setEnabled(False)
        self.sha_label = QLabel("1.3")
        self.sha_label.setFixedWidth(30)
        self.sha_slider.valueChanged.connect(lambda v: self.sha_label.setText(f"{v/10:.1f}"))
        sha_layout.addWidget(self.sha_slider)
        sha_layout.addWidget(self.sha_label)
        config_layout.addLayout(sha_layout, 6, 1)

        # 抖动复选框
        self.dither_check = QCheckBox("抖动模式（Floyd-Steinberg，过渡更自然）")
        self.dither_check.setToolTip("将颜色量化误差扩散到相邻像素，颜色过渡区域更平滑，但颜色种类更多")
        config_layout.addWidget(self.dither_check, 7, 0, 1, 2)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 3. 转换按钮
        convert_group = QGroupBox("3. 开始转换")
        convert_layout = QVBoxLayout()

        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        convert_layout.addWidget(self.convert_btn)

        self.status_label = QLabel("等待选择图片...")
        self.status_label.setAlignment(Qt.AlignCenter)
        convert_layout.addWidget(self.status_label)

        convert_group.setLayout(convert_layout)
        layout.addWidget(convert_group)

        # 4. 导出按钮
        export_group = QGroupBox("4. 导出结果")
        export_layout = QVBoxLayout()

        self.export_json_btn = QPushButton("导出 JSON")
        self.export_json_btn.setEnabled(False)
        self.export_json_btn.clicked.connect(self.export_json)
        export_layout.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton("导出 CSV")
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(self.export_csv)
        export_layout.addWidget(self.export_csv_btn)

        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # 5. 统计信息
        self.stats_group = QGroupBox("统计信息")
        self.stats_layout = QVBoxLayout()
        self.stats_label = QLabel("暂无数据")
        self.stats_layout.addWidget(self.stats_label)
        self.stats_group.setLayout(self.stats_layout)
        layout.addWidget(self.stats_group)

        layout.addStretch()
        return panel

    def create_preview_panel(self):
        """创建预览面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 标题
        title = QLabel("预览")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)

        # 预览标签
        self.preview_label = QLabel("等待转换...")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; border: 2px dashed #cccccc;")
        self.preview_label.setMinimumSize(400, 400)

        scroll.setWidget(self.preview_label)
        layout.addWidget(scroll)

        return panel

    def update_grid_info(self):
        """更新网格尺寸信息"""
        ratio = self.ratio_combo.currentText()
        level = self.level_combo.currentIndex()

        dimensions = HeartopiaPixelArt.GRID_DIMENSIONS[ratio][level]
        width, height = dimensions

        self.grid_info_label.setText(f"网格尺寸: {width} × {height} 像素")

    def _on_enhance_toggled(self, state):
        """增强复选框切换时启用/禁用三个滑块和恢复按钮"""
        enabled = bool(state)
        self.sat_slider.setEnabled(enabled)
        self.con_slider.setEnabled(enabled)
        self.sha_slider.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)

    def _reset_sliders(self):
        """恢复滑块到默认位置"""
        self.sat_slider.setValue(13)
        self.con_slider.setValue(12)
        self.sha_slider.setValue(13)

    def select_image(self):
        """选择图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.gif)"
        )

        if file_path:
            self.image_path = file_path
            self.image_label.setText(f"已选择:\n{Path(file_path).name}")
            self.convert_btn.setEnabled(True)
            self.status_label.setText("准备就绪，点击开始转换")

    def start_conversion(self):
        """开始转换"""
        if not self.image_path:
            return

        ratio = self.ratio_combo.currentText()
        level = self.level_combo.currentIndex()
        enhance = self.enhance_check.isChecked()
        dither = self.dither_check.isChecked()
        saturation = self.sat_slider.value() / 10
        contrast = self.con_slider.value() / 10
        sharpness = self.sha_slider.value() / 10

        # 禁用按钮
        self.convert_btn.setEnabled(False)
        mode_hints = []
        if enhance:
            mode_hints.append(f"增强(饱和{saturation}/对比{contrast}/锐{sharpness})")
        if dither:
            mode_hints.append("抖动")
        hint = f"（{'+'.join(mode_hints)}）" if mode_hints else ""
        self.status_label.setText(f"正在转换{hint}...")

        # 启动转换线程
        self.thread = ConversionThread(
            self.image_path, ratio, level,
            enhance=enhance, dither=dither,
            saturation=saturation, contrast=contrast, sharpness=sharpness
        )
        self.thread.finished.connect(self.on_conversion_finished)
        self.thread.error.connect(self.on_conversion_error)
        self.thread.start()

    def on_conversion_finished(self, converter, pixel_grid):
        """转换完成"""
        self.converter = converter
        self.pixel_grid = pixel_grid

        # 生成预览图
        self.generate_preview()

        # 更新统计信息
        self.update_stats()

        # 启用导出按钮
        self.export_json_btn.setEnabled(True)
        self.export_csv_btn.setEnabled(True)
        self.convert_btn.setEnabled(True)

        self.status_label.setText("✅ 转换完成！")

    def on_conversion_error(self, error_msg):
        """转换错误"""
        QMessageBox.critical(self, "错误", f"转换失败:\n{error_msg}")
        self.convert_btn.setEnabled(True)
        self.status_label.setText("转换失败")

    def generate_preview(self):
        """生成预览图"""
        if not self.converter:
            return

        # 使用 converter 提供的预览方法生成 RGB 数组
        scale = max(1, min(10, 600 // max(self.converter.grid_width, self.converter.grid_height)))
        rgb_array = self.converter.get_preview_image(scale=scale)

        height, width = rgb_array.shape[:2]

        # 确保内存连续
        rgb_array = np.ascontiguousarray(rgb_array)

        # 从 numpy 数组创建 QImage
        bytes_per_line = 3 * width
        img = QImage(rgb_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
        img = img.copy()  # 复制一份，防止 numpy 数组被回收

        pixmap = QPixmap.fromImage(img)
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setMinimumSize(pixmap.size())

    def update_stats(self):
        """更新统计信息"""
        if not self.converter:
            return

        stats = self.converter.get_stats()

        stats_text = f"""
网格尺寸: {stats['grid_width']} × {stats['grid_height']}
总像素数: {stats['total_pixels']}
使用颜色: {stats['color_count']} 种
画布比例: {stats['ratio']}
精细度: Level {stats['level']}
        """.strip()

        self.stats_label.setText(stats_text)

    def export_json(self):
        """导出 JSON"""
        if not self.converter:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 JSON",
            f"{Path(self.image_path).stem}_heartopia.json",
            "JSON 文件 (*.json)"
        )

        if file_path:
            try:
                self.converter.export_json(file_path)
                QMessageBox.information(self, "成功", f"JSON 已导出:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败:\n{e}")

    def export_csv(self):
        """导出 CSV"""
        if not self.converter:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 CSV",
            f"{Path(self.image_path).stem}_heartopia.csv",
            "CSV 文件 (*.csv)"
        )

        if file_path:
            try:
                self.converter.export_csv(file_path)
                QMessageBox.information(self, "成功", f"CSV 已导出:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败:\n{e}")


def main():
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    window = HeartopiaGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
