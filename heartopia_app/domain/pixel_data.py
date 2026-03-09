from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .palette import COLOR_ID_MAP


@dataclass
class Pixel:
    x: int
    y: int
    color: str
    color_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pixel":
        if not isinstance(data, dict):
            raise ValueError(
                f"pixels 元素应为字典，实际类型: {type(data).__name__}。请确认 JSON 由转换器生成"
            )
        for key in ("x", "y", "color"):
            if key not in data:
                raise ValueError(f"像素字典缺少必需字段: '{key}'")
        color = str(data["color"]).lower()
        color_id = data.get("colorId") or COLOR_ID_MAP.get(color)
        return cls(x=int(data["x"]), y=int(data["y"]), color=color, color_id=color_id)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "x": self.x,
            "y": self.y,
            "color": self.color,
        }
        if self.color_id:
            data["colorId"] = self.color_id
        return data


@dataclass
class PixelData:
    ratio: str = ""
    level: int = 0
    grid_width: int = 0
    grid_height: int = 0
    pixels: List[Pixel] = field(default_factory=list)
    total_pixels: int = 0
    color_count: int = 0
    colors: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_json_file(cls, file_path: str | Path) -> "PixelData":
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PixelData":
        required_fields = ["gridWidth", "gridHeight", "pixels"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"JSON 缺少必需字段: '{field_name}'")

        obj = cls(
            ratio=str(data.get("ratio", "")),
            level=int(data.get("level", 0)),
            grid_width=int(data["gridWidth"]),
            grid_height=int(data["gridHeight"]),
            total_pixels=int(data.get("totalPixels", 0)),
            color_count=int(data.get("colorCount", 0)),
            colors={str(k).lower(): int(v) for k, v in data.get("colors", {}).items()},
            pixels=[Pixel.from_dict(item) for item in data.get("pixels", [])],
        )
        obj.validate()
        obj.recalculate_summary()
        return obj

    @classmethod
    def from_pixel_grid(cls, ratio: str, level: int, pixel_grid: List[List[str]]) -> "PixelData":
        if not pixel_grid or not pixel_grid[0]:
            raise ValueError("像素矩阵为空")

        pixels: List[Pixel] = []
        for y, row in enumerate(pixel_grid):
            for x, color in enumerate(row):
                color_lower = color.lower()
                pixels.append(Pixel(x=x, y=y, color=color_lower, color_id=COLOR_ID_MAP.get(color_lower)))

        obj = cls(
            ratio=ratio,
            level=level,
            grid_width=len(pixel_grid[0]),
            grid_height=len(pixel_grid),
            pixels=pixels,
        )
        obj.recalculate_summary()
        return obj

    def validate(self) -> None:
        if self.grid_width <= 0 or self.grid_height <= 0:
            raise ValueError(f"无效的网格尺寸: {self.grid_width}x{self.grid_height}")
        if not self.pixels:
            raise ValueError("像素列表为空")

    def recalculate_summary(self) -> None:
        color_counts: Dict[str, int] = {}
        for pixel in self.pixels:
            color_counts[pixel.color] = color_counts.get(pixel.color, 0) + 1
        self.colors = color_counts
        self.total_pixels = len(self.pixels)
        self.color_count = len(self.colors)

    def has_color_ids(self) -> bool:
        return bool(self.pixels and self.pixels[0].color_id)

    def to_dict(self) -> Dict[str, Any]:
        self.recalculate_summary()
        return {
            "ratio": self.ratio,
            "level": self.level,
            "gridWidth": self.grid_width,
            "gridHeight": self.grid_height,
            "totalPixels": self.total_pixels,
            "colorCount": self.color_count,
            "colors": self.colors,
            "pixels": [pixel.to_dict() for pixel in self.pixels],
        }

    def save_json(self, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)

    def export_csv(self, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write("x,y,color\n")
            for pixel in self.pixels:
                handle.write(f"{pixel.x},{pixel.y},{pixel.color}\n")

    def iter_pixel_dicts(self) -> Iterable[Dict[str, Any]]:
        for pixel in self.pixels:
            yield pixel.to_dict()
