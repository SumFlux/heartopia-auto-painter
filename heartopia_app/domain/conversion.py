from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from .palette import hex_to_rgb, find_closest_color
from .pixel_data import PixelData


GRID_DIMENSIONS: Dict[str, List[List[int]]] = {
    '16:9': [[30, 18], [50, 28], [100, 56], [150, 84]],
    '4:3': [[30, 24], [50, 38], [100, 76], [150, 114]],
    '1:1': [[30, 30], [50, 50], [100, 100], [150, 150]],
    '3:4': [[24, 30], [38, 50], [76, 100], [114, 150]],
    '9:16': [[18, 30], [28, 50], [56, 100], [84, 150]],
}


@dataclass
class ConversionRequest:
    ratio: str = '1:1'
    level: int = 2
    enhance: bool = False
    dither: bool = False
    saturation: float = 1.3
    contrast: float = 1.2
    sharpness: float = 1.3


@dataclass
class ConversionResult:
    pixel_data: PixelData
    pixel_grid: List[List[str]]

    @property
    def grid_width(self) -> int:
        return self.pixel_data.grid_width

    @property
    def grid_height(self) -> int:
        return self.pixel_data.grid_height

    def get_stats(self) -> Dict[str, object]:
        return {
            'grid_width': self.pixel_data.grid_width,
            'grid_height': self.pixel_data.grid_height,
            'total_pixels': self.pixel_data.total_pixels,
            'color_count': self.pixel_data.color_count,
            'colors': self.pixel_data.colors,
            'ratio': self.pixel_data.ratio,
            'level': self.pixel_data.level,
        }

    def get_preview_image(self, scale: int = 5) -> np.ndarray:
        if not self.pixel_grid:
            return np.zeros((1, 1, 3), dtype=np.uint8)
        height = len(self.pixel_grid)
        width = len(self.pixel_grid[0])
        rgb_array = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                r, g, b = hex_to_rgb(self.pixel_grid[y][x])
                rgb_array[y, x] = [r, g, b]
        if scale > 1:
            return np.repeat(np.repeat(rgb_array, scale, axis=0), scale, axis=1)
        return rgb_array


class PixelArtConverter:
    def __init__(self, ratio: str = '1:1', level: int = 2):
        if ratio not in GRID_DIMENSIONS:
            raise ValueError(f"不支持的比例: {ratio}")
        if level < 0 or level > 3:
            raise ValueError("精细度等级必须在 0-3 之间")

        self.ratio = ratio
        self.level = level
        self.grid_width, self.grid_height = GRID_DIMENSIONS[ratio][level]
        self.pixel_grid: List[List[str]] = []
        self.pixel_data: PixelData | None = None

    def _find_closest_color(self, r: int, g: int, b: int) -> str:
        hex_color, _ = find_closest_color(r, g, b)
        return hex_color

    def _center_crop(self, img: Image.Image) -> Image.Image:
        nw, nh = img.size
        desired_aspect = self.grid_width / self.grid_height
        img_aspect = nw / nh

        if img_aspect > desired_aspect:
            sh = nh
            sw = round(sh * desired_aspect)
            sx = round((nw - sw) / 2)
            sy = 0
        else:
            sw = nw
            sh = round(sw / desired_aspect)
            sx = 0
            sy = round((nh - sh) / 2)

        return img.crop((sx, sy, sx + sw, sy + sh))

    def _enhance_image(self, img: Image.Image, saturation: float, contrast: float, sharpness: float) -> Image.Image:
        img = ImageEnhance.Color(img).enhance(saturation)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
        return img

    def _quantize_simple(self, arr: np.ndarray) -> List[List[str]]:
        grid = []
        for y in range(self.grid_height):
            row = []
            for x in range(self.grid_width):
                r, g, b = int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2])
                row.append(self._find_closest_color(r, g, b))
            grid.append(row)
        return grid

    def _quantize_dither(self, arr: np.ndarray) -> List[List[str]]:
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

                pr, pg, pb = hex_to_rgb(color_hex)
                err = np.array([r - pr, g - pg, b - pb], dtype=np.float32)
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

    def process_image(self, image_path: str, enhance: bool = False, dither: bool = False,
                      saturation: float = 1.3, contrast: float = 1.2, sharpness: float = 1.3) -> List[List[str]]:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')
        img = self._center_crop(img)
        if enhance:
            img = self._enhance_image(img, saturation=saturation, contrast=contrast, sharpness=sharpness)

        img_resized = img.resize((self.grid_width, self.grid_height), Image.Resampling.LANCZOS)
        img_array = np.array(img_resized, dtype=np.int32)
        self.pixel_grid = self._quantize_dither(img_array) if dither else self._quantize_simple(img_array)
        self.pixel_data = PixelData.from_pixel_grid(self.ratio, self.level, self.pixel_grid)
        return self.pixel_grid

    def convert(self, image_path: str, request: ConversionRequest | None = None) -> ConversionResult:
        req = request or ConversionRequest(ratio=self.ratio, level=self.level)
        self.process_image(
            image_path,
            enhance=req.enhance,
            dither=req.dither,
            saturation=req.saturation,
            contrast=req.contrast,
            sharpness=req.sharpness,
        )
        return ConversionResult(pixel_data=self.pixel_data, pixel_grid=self.pixel_grid)

    def get_preview_image(self, scale: int = 5) -> np.ndarray:
        if not self.pixel_grid:
            return np.zeros((1, 1, 3), dtype=np.uint8)

        height = len(self.pixel_grid)
        width = len(self.pixel_grid[0])
        rgb_array = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                r, g, b = hex_to_rgb(self.pixel_grid[y][x])
                rgb_array[y, x] = [r, g, b]
        if scale > 1:
            return np.repeat(np.repeat(rgb_array, scale, axis=0), scale, axis=1)
        return rgb_array

    def get_stats(self) -> Dict[str, object]:
        if not self.pixel_data:
            return {}
        return {
            'grid_width': self.pixel_data.grid_width,
            'grid_height': self.pixel_data.grid_height,
            'total_pixels': self.pixel_data.total_pixels,
            'color_count': self.pixel_data.color_count,
            'colors': self.pixel_data.colors,
            'ratio': self.pixel_data.ratio,
            'level': self.pixel_data.level,
        }

    def export_json(self, output_path: str) -> Dict[str, object]:
        if not self.pixel_data:
            raise ValueError("尚未处理图片")
        self.pixel_data.save_json(output_path)
        return self.pixel_data.to_dict()

    def export_csv(self, output_path: str) -> None:
        if not self.pixel_data:
            raise ValueError("尚未处理图片")
        self.pixel_data.export_csv(output_path)
