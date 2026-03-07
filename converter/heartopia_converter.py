#!/usr/bin/env python3
"""
Heartopia Painting Tools - Python 版本
将图片转换为心动小镇像素画矩阵
"""

import json
import sys
from PIL import Image
import numpy as np
from typing import List, Tuple, Dict

class HeartopiaPixelArt:
    # 网格尺寸配置（比例: [[level0], [level1], [level2], [level3]]）
    GRID_DIMENSIONS = {
        '16:9': [[30, 18], [50, 28], [100, 56], [150, 84]],
        '4:3': [[30, 24], [50, 38], [100, 76], [150, 114]],
        '1:1': [[30, 30], [50, 50], [100, 100], [150, 150]],
        '3:4': [[24, 30], [38, 50], [76, 100], [114, 150]],
        '9:16': [[18, 30], [28, 50], [56, 100], [84, 150]]
    }
    
    # 心动小镇游戏原生颜色（从游戏中提取）
    GAME_COLORS = [
        # 黑色系
        '#000000', '#1A1A1A', '#333333', '#4D4D4D', '#666666',
        # 白色系
        '#FFFFFF', '#F2F2F2', '#E6E6E6', '#D9D9D9', '#CCCCCC',
        # 红色系
        '#8B0000', '#B22222', '#DC143C', '#FF0000', '#FF6347',
        # 橙色系
        '#FF8C00', '#FFA500', '#FFB347', '#FFC966',
        # 黄色系
        '#FFD700', '#FFFF00', '#FFFFE0', '#FFFACD',
        # 绿色系
        '#006400', '#228B22', '#32CD32', '#00FF00', '#7FFF00',
        # 青色系
        '#008B8B', '#00CED1', '#00FFFF', '#AFEEEE',
        # 蓝色系
        '#00008B', '#0000CD', '#0000FF', '#1E90FF', '#87CEEB',
        # 紫色系
        '#4B0082', '#8B008B', '#9370DB', '#BA55D3', '#DDA0DD',
        # 粉色系
        '#FF1493', '#FF69B4', '#FFB6C1', '#FFC0CB',
        # 棕色系
        '#8B4513', '#A0522D', '#D2691E', '#CD853F', '#DEB887',
    ]
    
    def __init__(self, ratio: str = '1:1', level: int = 2):
        """
        初始化
        :param ratio: 画布比例 ('16:9', '4:3', '1:1', '3:4', '9:16')
        :param level: 精细度等级 (0-3)
        """
        if ratio not in self.GRID_DIMENSIONS:
            raise ValueError(f"不支持的比例: {ratio}")
        if level < 0 or level > 3:
            raise ValueError(f"精细度等级必须在 0-3 之间")
        
        self.ratio = ratio
        self.level = level
        self.grid_width, self.grid_height = self.GRID_DIMENSIONS[ratio][level]
        self.pixel_grid = []
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """十六进制颜色转 RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """RGB 转十六进制颜色"""
        return f'#{r:02X}{g:02X}{b:02X}'
    
    def find_closest_color(self, r: int, g: int, b: int) -> str:
        """找到最接近的游戏颜色"""
        min_distance = float('inf')
        closest_color = self.GAME_COLORS[0]
        
        for hex_color in self.GAME_COLORS:
            pr, pg, pb = self.hex_to_rgb(hex_color)
            distance = np.sqrt((r - pr)**2 + (g - pg)**2 + (b - pb)**2)
            
            if distance < min_distance:
                min_distance = distance
                closest_color = hex_color
        
        return closest_color
    
    def process_image(self, image_path: str):
        """处理图片，生成像素矩阵"""
        # 打开图片
        img = Image.open(image_path)
        
        # 转换为 RGB 模式
        img = img.convert('RGB')
        
        # 调整大小到网格尺寸
        img_resized = img.resize((self.grid_width, self.grid_height), Image.Resampling.LANCZOS)
        
        # 转换为 numpy 数组
        img_array = np.array(img_resized)
        
        # 初始化像素网格
        self.pixel_grid = []
        
        # 处理每个像素
        for y in range(self.grid_height):
            row = []
            for x in range(self.grid_width):
                r, g, b = img_array[y, x]
                closest_color = self.find_closest_color(r, g, b)
                row.append(closest_color)
            self.pixel_grid.append(row)
        
        return self.pixel_grid
    
    def export_json(self, output_path: str):
        """导出为 JSON 格式"""
        # 统计颜色使用情况
        color_count = {}
        pixels = []
        
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                color = self.pixel_grid[y][x]
                if color != '#FFFFFF':  # 跳过白色（空白）
                    pixels.append({
                        'x': x,
                        'y': y,
                        'color': color
                    })
                    color_count[color] = color_count.get(color, 0) + 1
        
        data = {
            'ratio': self.ratio,
            'level': self.level,
            'gridWidth': self.grid_width,
            'gridHeight': self.grid_height,
            'totalPixels': len(pixels),
            'colorCount': len(color_count),
            'colors': color_count,
            'pixels': pixels
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return data
    
    def export_csv(self, output_path: str):
        """导出为 CSV 格式（方便 Excel 查看）"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('x,y,color\n')
            for y in range(self.grid_height):
                for x in range(self.grid_width):
                    color = self.pixel_grid[y][x]
                    if color != '#FFFFFF':
                        f.write(f'{x},{y},{color}\n')
    
    def preview_ascii(self):
        """ASCII 预览（调试用）"""
        print(f"\n画布尺寸: {self.grid_width}x{self.grid_height}")
        print(f"比例: {self.ratio}, 精细度: Level {self.level}\n")
        
        # 简化显示（用字符表示不同颜色）
        for y in range(min(self.grid_height, 20)):  # 最多显示 20 行
            for x in range(min(self.grid_width, 40)):  # 最多显示 40 列
                color = self.pixel_grid[y][x]
                if color == '#FFFFFF':
                    print(' ', end='')
                else:
                    print('█', end='')
            print()

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python heartopia_converter.py <图片路径> [比例] [精细度]")
        print("比例: 16:9, 4:3, 1:1, 3:4, 9:16 (默认: 1:1)")
        print("精细度: 0-3 (默认: 2)")
        print("\n示例:")
        print("  python heartopia_converter.py image.jpg")
        print("  python heartopia_converter.py image.jpg 1:1 2")
        sys.exit(1)
    
    image_path = sys.argv[1]
    ratio = sys.argv[2] if len(sys.argv) > 2 else '1:1'
    level = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    
    try:
        # 创建转换器
        converter = HeartopiaPixelArt(ratio=ratio, level=level)
        
        print(f"正在处理图片: {image_path}")
        print(f"画布配置: {ratio} 比例, Level {level} 精细度")
        print(f"网格尺寸: {converter.grid_width}x{converter.grid_height}")
        
        # 处理图片
        converter.process_image(image_path)
        
        # ASCII 预览
        converter.preview_ascii()
        
        # 导出 JSON
        json_path = image_path.rsplit('.', 1)[0] + '_heartopia.json'
        data = converter.export_json(json_path)
        print(f"\n✅ JSON 已导出: {json_path}")
        print(f"   总像素数: {data['totalPixels']}")
        print(f"   使用颜色: {data['colorCount']} 种")
        
        # 导出 CSV
        csv_path = image_path.rsplit('.', 1)[0] + '_heartopia.csv'
        converter.export_csv(csv_path)
        print(f"✅ CSV 已导出: {csv_path}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
