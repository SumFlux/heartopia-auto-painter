#!/usr/bin/env python3
"""
Heartopia Painting Tools - Python 版本
将图片转换为心动小镇像素画矩阵

颜色数据从原工程 zerochansy/Heartopia-Painting-Tools 的 color.svg 中提取
"""

import json
import sys
import math
from PIL import Image
import numpy as np
from typing import List, Tuple, Dict, Optional


class HeartopiaPixelArt:
    # 网格尺寸配置（比例: [[level0], [level1], [level2], [level3]]）
    GRID_DIMENSIONS = {
        '16:9': [[30, 18], [50, 28], [100, 56], [150, 84]],
        '4:3': [[30, 24], [50, 38], [100, 76], [150, 114]],
        '1:1': [[30, 30], [50, 50], [100, 100], [150, 150]],
        '3:4': [[24, 30], [38, 50], [76, 100], [114, 150]],
        '9:16': [[18, 30], [28, 50], [56, 100], [84, 150]]
    }

    # 13 组，共 126 种心动小镇原版调色盘精选颜色（来自实际截图取色）
    HEARTOPIA_COLORS = [
        # 组1 - 黑白灰 (6色)
        '#051616', '#434747', '#828484', '#b9b7b6', '#e0dbd9', '#a8978e',
        # 组2 - 红色系 (10色)
        '#cf354d', '#ee6f72', '#a6263d', '#f5ada8', '#ca8988', '#9f6d6b', '#7b5859', '#9c857e', '#8c746c', '#75584d',
        # 组3 - 橙红色系 (10色)
        '#e95e2b', '#f98358', '#ab4226', '#feba9f', '#d9947d', '#af7868', '#825951', '#b09a92', '#998179', '#795e54',
        # 组4 - 橙色系 (10色)
        '#f49e16', '#feae3b', '#b16f16', '#fece92', '#daa76c', '#b3814b', '#7a542c', '#f5e4cf', '#c1b0a1', '#88776b',
        # 组5 - 黄色系 (10色)
        '#edca16', '#f9d838', '#b39416', '#fae792', '#d3bf74', '#a89460', '#827150', '#a59282', '#8f796c', '#765a4f',
        # 组6 - 黄绿色系 (10色)
        '#a9bd20', '#b3bf50', '#818745', '#a29575', '#8f8067', '#775c50', '#75584d', '#75584d', '#75584d', '#74574c',
        # 组7 - 绿色系 (10色)
        '#05a25d', '#41b97b', '#057447', '#9edaaf', '#81b694', '#6c8772', '#646a5d', '#918478', '#7f685e', '#75584d',
        # 组8 - 青绿色系 (10色)
        '#058781', '#05aba0', '#056966', '#82cec3', '#65aaa3', '#5b7f79', '#5d6662', '#8d8178', '#7e685e', '#75584d',
        # 组9 - 青色系 (10色)
        '#05729c', '#0599ba', '#055878', '#79bbca', '#5193a5', '#2d7082', '#235767', '#b8c3c4', '#969998', '#796c66',
        # 组10 - 蓝色系 (10色)
        '#055ea6', '#2b83c1', '#054782', '#84a8c9', '#6283a3', '#556c85', '#525c68', '#9b908e', '#887671', '#775c52',
        # 组11 - 蓝紫色系 (10色)
        '#534da1', '#7577bd', '#3e387e', '#a2a0c7', '#787aa1', '#5c5d82', '#4c4e67', '#b5afb3', '#958989', '#7b6762',
        # 组12 - 紫色系 (10色)
        '#813d8b', '#a167a9', '#602c6c', '#ba9fbb', '#98809b', '#7d6674', '#715e60', '#89716a', '#795e54', '#75584d',
        # 组13 - 粉色系 (10色)
        '#ad356f', '#cf6b8f', '#862658', '#d9a3b5', '#b88594', '#8f6771', '#795e61', '#98827c', '#82685f', '#75584d'
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
        self.pixel_grid: List[List[str]] = []

        # 预计算调色板 RGB 值（使用 int 类型，避免 uint8 溢出）
        self._palette_rgb = []
        self._hex_to_id = {}
        for i, hex_color in enumerate(self.HEARTOPIA_COLORS):
            # 组号推算：
            # 组 1 = index 0~5
            # 组 2~13 = 每个10个
            if i < 6:
                group_idx = 0
                color_idx = i
            else:
                group_idx = (i - 6) // 10 + 1
                color_idx = (i - 6) % 10
                
            color_id = f"{group_idx}-{color_idx}"
            r, g, b = self._hex_to_rgb(hex_color)
            
            self._palette_rgb.append((r, g, b, hex_color))
            self._hex_to_id[hex_color] = color_id

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """十六进制颜色转 RGB（返回 Python int，不是 numpy uint8）"""
        hex_color = hex_color.lstrip('#')
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16)
        )

    @staticmethod
    def _rgb_to_hex(r: int, g: int, b: int) -> str:
        """RGB 转十六进制颜色"""
        return f'#{r:02x}{g:02x}{b:02x}'

    def _find_closest_color(self, r: int, g: int, b: int) -> str:
        """
        找到最接近的游戏颜色（欧几里得 RGB 距离）
        注意：所有参数必须是 Python int，不能是 numpy uint8
        """
        min_distance = float('inf')
        closest_color = self._palette_rgb[0][3]

        for pr, pg, pb, hex_color in self._palette_rgb:
            # 使用 Python 原生 int 运算，避免 numpy uint8 溢出
            dr = r - pr
            dg = g - pg
            db = b - pb
            distance = dr * dr + dg * dg + db * db  # 不需要 sqrt，比较用平方距离即可

            if distance < min_distance:
                min_distance = distance
                closest_color = hex_color

        return closest_color

    def _center_crop(self, img: Image.Image) -> Image.Image:
        """
        中心裁剪图片以适应目标网格比例（与原工程 autoCropCenter 逻辑一致）
        """
        nw, nh = img.size
        desired_aspect = self.grid_width / self.grid_height
        img_aspect = nw / nh

        if img_aspect > desired_aspect:
            # 图片更宽：使用全部高度，裁剪两侧
            sh = nh
            sw = round(sh * desired_aspect)
            sx = round((nw - sw) / 2)
            sy = 0
        else:
            # 图片更高：使用全部宽度，裁剪上下
            sw = nw
            sh = round(sw / desired_aspect)
            sx = 0
            sy = round((nh - sh) / 2)

        return img.crop((sx, sy, sx + sw, sy + sh))

    def _enhance_image(self, img: Image.Image,
                       saturation: float = 1.0,
                       contrast: float = 1.0,
                       sharpness: float = 1.0) -> Image.Image:
        """
        预处理增强：提升饱和度、对比度和锐化，减少颜色"脏"感
        """
        from PIL import ImageEnhance
        img = ImageEnhance.Color(img).enhance(saturation)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
        return img

    def _quantize_simple(self, arr: np.ndarray) -> List[List[str]]:
        """简单最近邻颜色量化"""
        grid = []
        for y in range(self.grid_height):
            row = []
            for x in range(self.grid_width):
                r, g, b = int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2])
                row.append(self._find_closest_color(r, g, b))
            grid.append(row)
        return grid

    def _quantize_dither(self, arr: np.ndarray) -> List[List[str]]:
        """
        Floyd-Steinberg 误差扩散抖动量化
        将量化误差按权重扩散给相邻像素，使颜色过渡更自然
        """
        buf = arr.astype(np.float32)
        grid = []

        for y in range(self.grid_height):
            row = []
            for x in range(self.grid_width):
                r = int(max(0, min(255, buf[y, x, 0])))
                g = int(max(0, min(255, buf[y, x, 1])))
                b = int(max(0, min(255, buf[y, x, 2])))

                color_hex = self._find_closest_color(r, g, b)
                row.append(color_hex)

                pr, pg, pb = self._hex_to_rgb(color_hex)
                err = np.array([r - pr, g - pg, b - pb], dtype=np.float32)

                # Floyd-Steinberg 误差扩散
                if x + 1 < self.grid_width:
                    buf[y, x + 1, :3] += err * (7 / 16)
                if y + 1 < self.grid_height:
                    if x > 0:
                        buf[y + 1, x - 1, :3] += err * (3 / 16)
                    buf[y + 1, x, :3] += err * (5 / 16)
                    if x + 1 < self.grid_width:
                        buf[y + 1, x + 1, :3] += err * (1 / 16)

            grid.append(row)
        return grid

    def process_image(self, image_path: str,
                      enhance: bool = False,
                      dither: bool = False,
                      saturation: float = 1.3,
                      contrast: float = 1.2,
                      sharpness: float = 1.3) -> List[List[str]]:
        """
        处理图片，生成像素矩阵
        :param image_path: 图片路径
        :param enhance: 是否进行预处理增强
        :param dither: 是否使用 Floyd-Steinberg 误差扩散抖动
        :param saturation: 饱和度倍数（1.0=原始）
        :param contrast: 对比度倍数（1.0=原始）
        :param sharpness: 锐度倍数（1.0=原始）
        """
        img = Image.open(image_path)

        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')
        img = self._center_crop(img)

        if enhance:
            img = self._enhance_image(img, saturation=saturation, contrast=contrast, sharpness=sharpness)

        img_resized = img.resize(
            (self.grid_width, self.grid_height),
            Image.Resampling.LANCZOS
        )

        img_array = np.array(img_resized, dtype=np.int32)

        if dither:
            self.pixel_grid = self._quantize_dither(img_array)
        else:
            self.pixel_grid = self._quantize_simple(img_array)

        return self.pixel_grid

    def get_preview_image(self, scale: int = 5) -> np.ndarray:
        """
        生成预览用的 RGB numpy 数组
        :param scale: 每个像素放大倍数
        :return: (height*scale, width*scale, 3) 的 uint8 数组
        """
        if not self.pixel_grid:
            return np.zeros((1, 1, 3), dtype=np.uint8)

        height = len(self.pixel_grid)
        width = len(self.pixel_grid[0])

        # 先创建原始尺寸的 RGB 数组
        rgb_array = np.zeros((height, width, 3), dtype=np.uint8)

        for y in range(height):
            for x in range(width):
                hex_color = self.pixel_grid[y][x]
                r, g, b = self._hex_to_rgb(hex_color)
                rgb_array[y, x] = [r, g, b]

        # 如果需要放大，使用最近邻插值
        if scale > 1:
            scaled = np.repeat(np.repeat(rgb_array, scale, axis=0), scale, axis=1)
            return scaled

        return rgb_array

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self.pixel_grid:
            return {}

        color_count = {}
        total_pixels = 0

        for row in self.pixel_grid:
            for color in row:
                color_count[color] = color_count.get(color, 0) + 1
                total_pixels += 1

        return {
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'total_pixels': total_pixels,
            'color_count': len(color_count),
            'colors': color_count,
            'ratio': self.ratio,
            'level': self.level
        }

    def export_json(self, output_path: str) -> Dict:
        """导出为 JSON 格式"""
        color_count = {}
        pixels = []

        for y in range(self.grid_height):
            for x in range(self.grid_width):
                color = self.pixel_grid[y][x]
                color_id = self._hex_to_id.get(color, "")
                pixels.append({
                    'x': x,
                    'y': y,
                    'color': color,
                    'colorId': color_id
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
        """导出为 CSV 格式"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('x,y,color\n')
            for y in range(self.grid_height):
                for x in range(self.grid_width):
                    color = self.pixel_grid[y][x]
                    f.write(f'{x},{y},{color}\n')


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

        # 统计
        stats = converter.get_stats()
        print(f"\n总像素数: {stats['total_pixels']}")
        print(f"使用颜色: {stats['color_count']} 种")

        # 导出 JSON
        json_path = image_path.rsplit('.', 1)[0] + '_heartopia.json'
        converter.export_json(json_path)
        print(f"\n✅ JSON 已导出: {json_path}")

        # 导出 CSV
        csv_path = image_path.rsplit('.', 1)[0] + '_heartopia.csv'
        converter.export_csv(csv_path)
        print(f"✅ CSV 已导出: {csv_path}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
