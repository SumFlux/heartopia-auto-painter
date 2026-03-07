"""
shared/pixel_data.py — 像素矩阵 JSON 的统一读写与校验

定义了 converter 输出、painter 导入的 JSON 数据格式契约。
两边都通过此模块读写，避免各自解析导致的不一致。

JSON Schema:
{
    "ratio": "1:1",
    "level": 2,
    "gridWidth": 30,
    "gridHeight": 30,
    "totalPixels": 900,
    "colorCount": 46,
    "colors": { "#hex": count, ... },
    "pixels": [
        { "x": 0, "y": 0, "color": "#hex", "colorId": "0-3" },
        ...
    ]
}
"""

import json
from typing import Dict, List, Optional, Any


class PixelData:
    """像素矩阵数据容器，提供校验和便捷访问"""

    def __init__(self):
        self.ratio: str = ""
        self.level: int = 0
        self.grid_width: int = 0
        self.grid_height: int = 0
        self.total_pixels: int = 0
        self.color_count: int = 0
        self.colors: Dict[str, int] = {}
        self.pixels: List[Dict[str, Any]] = []  # [{"x","y","color","colorId"}, ...]

    @classmethod
    def from_json_file(cls, file_path: str) -> 'PixelData':
        """从 JSON 文件加载并校验"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> 'PixelData':
        """从字典加载并校验"""
        obj = cls()

        # 必须字段校验
        required_fields = ['gridWidth', 'gridHeight', 'pixels']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"JSON 缺少必需字段: '{field}'")

        obj.ratio = data.get('ratio', '')
        obj.level = data.get('level', 0)
        obj.grid_width = int(data['gridWidth'])
        obj.grid_height = int(data['gridHeight'])
        obj.total_pixels = int(data.get('totalPixels', 0))
        obj.color_count = int(data.get('colorCount', 0))
        obj.colors = data.get('colors', {})
        obj.pixels = data.get('pixels', [])

        # 合理性校验
        if obj.grid_width <= 0 or obj.grid_height <= 0:
            raise ValueError(f"无效的网格尺寸: {obj.grid_width}x{obj.grid_height}")

        if len(obj.pixels) == 0:
            raise ValueError("像素列表为空")

        # 抽样校验第一个像素的字段
        first = obj.pixels[0]
        if not isinstance(first, dict):
            raise ValueError(
                f"pixels 元素应为字典，实际类型: {type(first).__name__}。"
                f"请确认 JSON 由 converter 生成"
            )
        for key in ('x', 'y', 'color'):
            if key not in first:
                raise ValueError(f"像素字典缺少必需字段: '{key}'")

        # 自动修正 total_pixels
        if obj.total_pixels == 0:
            obj.total_pixels = len(obj.pixels)

        return obj

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            'ratio': self.ratio,
            'level': self.level,
            'gridWidth': self.grid_width,
            'gridHeight': self.grid_height,
            'totalPixels': self.total_pixels,
            'colorCount': self.color_count,
            'colors': self.colors,
            'pixels': self.pixels,
        }

    def save_json(self, file_path: str):
        """保存为 JSON 文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def has_color_ids(self) -> bool:
        """检查像素数据是否包含 colorId 字段"""
        if not self.pixels:
            return False
        return 'colorId' in self.pixels[0]
