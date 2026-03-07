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
    QGroupBox, QGridLayout, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
from PIL import Image
import numpy as np

from heartopia_converter import HeartopiaPixelArt


class ConversionThread(QThread):
    """转换线程（避免 UI 卡顿）"""
    finished = Signal(object, object)  # 转换完成信号
    error = Signal(str)  # 错误信号
    
    def __init__(self, image_path, ratio, level):
        super().__init__()
        self.image_path = image_path
        self.ratio = ratio
        self.level = level
    
    def run(self):
        try:
            converter = HeartopiaPixelArt(ratio=self.ratio, level=self.level)
            converter.process_image(self.image_path)
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
        
        # 禁用按钮
        self.convert_btn.setEnabled(False)
        self.status_label.setText("正在转换...")
        
        # 启动转换线程
        self.thread = ConversionThread(self.image_path, ratio, level)
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
        if not self.pixel_grid:
            return
        
        height = len(self.pixel_grid)
        width = len(self.pixel_grid[0])
        
        # 创建 QImage
        img = QImage(width, height, QImage.Format_RGB888)
        
        # 填充颜色
        for y in range(height):
            for x in range(width):
                hex_color = self.pixel_grid[y][x]
                r = int(hex_color[1:3], 16)
                g = int(hex_color[3:5], 16)
                b = int(hex_color[5:7], 16)
                img.setPixel(x, y, (r << 16) | (g << 8) | b)
        
        # 放大显示（每个像素放大 5 倍）
        scale = 5
        pixmap = QPixmap.fromImage(img).scaled(
            width * scale,
            height * scale,
            Qt.KeepAspectRatio,
            Qt.FastTransformation
        )
        
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setMinimumSize(pixmap.size())
    
    def update_stats(self):
        """更新统计信息"""
        if not self.converter:
            return
        
        # 统计颜色
        color_count = {}
        total_pixels = 0
        
        for row in self.pixel_grid:
            for color in row:
                if color != '#FFFFFF':
                    color_count[color] = color_count.get(color, 0) + 1
                    total_pixels += 1
        
        stats_text = f"""
网格尺寸: {self.converter.grid_width} × {self.converter.grid_height}
总像素数: {total_pixels}
使用颜色: {len(color_count)} 种
画布比例: {self.converter.ratio}
精细度: Level {self.converter.level}
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
