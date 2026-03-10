from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


Point = Tuple[int, int]


@dataclass
class CanvasCalibration:
    grid_width: int = 0
    grid_height: int = 0
    top_left: Point = (0, 0)
    top_right: Point = (0, 0)
    bottom_left: Point = (0, 0)
    bottom_right: Point = (0, 0)
    offset_x: int = 0
    offset_y: int = 0
    subpixel_phase_x: int = 0
    subpixel_phase_y: int = 0
    calibrated: bool = False

    def calibrate(self, grid_width: int, grid_height: int, top_left: Point, bottom_right: Point,
                  top_right: Optional[Point] = None, bottom_left: Optional[Point] = None) -> None:
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.top_left = top_left
        self.bottom_right = bottom_right
        self.top_right = top_right or (bottom_right[0], top_left[1])
        self.bottom_left = bottom_left or (top_left[0], bottom_right[1])
        self.calibrated = True

    def reset(self) -> None:
        self.__dict__.update(CanvasCalibration().__dict__)

    def set_offset(self, offset_x: int, offset_y: int) -> None:
        self.offset_x = offset_x
        self.offset_y = offset_y

    def set_subpixel_phase(self, phase_x: int, phase_y: int) -> None:
        self.subpixel_phase_x = 1 if phase_x else 0
        self.subpixel_phase_y = 1 if phase_y else 0

    def get_screen_pos(self, px: int, py: int) -> Point:
        if not self.calibrated:
            raise RuntimeError("画布尚未标定")
        u = px / (self.grid_width - 1) if self.grid_width > 1 else 0.0
        v = py / (self.grid_height - 1) if self.grid_height > 1 else 0.0
        tl, tr, bl, br = self.top_left, self.top_right, self.bottom_left, self.bottom_right
        base_x = (1 - u) * (1 - v) * tl[0] + u * (1 - v) * tr[0] + (1 - u) * v * bl[0] + u * v * br[0]
        base_y = (1 - u) * (1 - v) * tl[1] + u * (1 - v) * tr[1] + (1 - u) * v * bl[1] + u * v * br[1]
        screen_x = int(base_x) + self.offset_x + self.subpixel_phase_x
        screen_y = int(base_y) + self.offset_y + self.subpixel_phase_y
        return screen_x, screen_y

    def compute_relative_corners(self, window_offset: Point) -> Dict[str, list[int]]:
        wx, wy = window_offset
        return {
            'top_left': [self.top_left[0] - wx, self.top_left[1] - wy],
            'top_right': [self.top_right[0] - wx, self.top_right[1] - wy],
            'bottom_left': [self.bottom_left[0] - wx, self.bottom_left[1] - wy],
            'bottom_right': [self.bottom_right[0] - wx, self.bottom_right[1] - wy],
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
            'subpixel_phase_x': self.subpixel_phase_x,
            'subpixel_phase_y': self.subpixel_phase_y,
        }

    @classmethod
    def from_window_relative(cls, window_offset: Point, relative_corners: Dict[str, list[int]]) -> "CanvasCalibration":
        wx, wy = window_offset
        obj = cls()
        obj.calibrate(
            grid_width=relative_corners['grid_width'],
            grid_height=relative_corners['grid_height'],
            top_left=(wx + relative_corners['top_left'][0], wy + relative_corners['top_left'][1]),
            bottom_right=(wx + relative_corners['bottom_right'][0], wy + relative_corners['bottom_right'][1]),
            top_right=(wx + relative_corners['top_right'][0], wy + relative_corners['top_right'][1]),
            bottom_left=(wx + relative_corners['bottom_left'][0], wy + relative_corners['bottom_left'][1]),
        )
        obj.set_offset(relative_corners.get('offset_x', 0), relative_corners.get('offset_y', 0))
        obj.set_subpixel_phase(relative_corners.get('subpixel_phase_x', 0), relative_corners.get('subpixel_phase_y', 0))
        return obj

    def to_dict(self) -> Dict[str, object]:
        return {
            'top_left': list(self.top_left),
            'top_right': list(self.top_right),
            'bottom_left': list(self.bottom_left),
            'bottom_right': list(self.bottom_right),
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
            'subpixel_phase_x': self.subpixel_phase_x,
            'subpixel_phase_y': self.subpixel_phase_y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "CanvasCalibration":
        obj = cls()
        obj.calibrate(
            grid_width=int(data['grid_width']),
            grid_height=int(data['grid_height']),
            top_left=tuple(data['top_left']),
            bottom_right=tuple(data['bottom_right']),
            top_right=tuple(data.get('top_right', (data['bottom_right'][0], data['top_left'][1]))),
            bottom_left=tuple(data.get('bottom_left', (data['top_left'][0], data['bottom_right'][1]))),
        )
        obj.set_offset(int(data.get('offset_x', 0)), int(data.get('offset_y', 0)))
        obj.set_subpixel_phase(int(data.get('subpixel_phase_x', 0)), int(data.get('subpixel_phase_y', 0)))
        return obj


@dataclass
class PaletteCalibration:
    left_tab: Optional[Point] = None
    right_tab: Optional[Point] = None
    blocks_top_left: Optional[Point] = None
    blocks_bottom_right: Optional[Point] = None
    current_group_idx: int = 0
    calibrated: bool = False
    color_blocks: Dict[int, Point] = field(default_factory=dict)

    BLOCK_COLS = 2
    BLOCK_ROWS = 5

    def calibrate(self, left_tab: Point, right_tab: Point, blocks_top_left: Point, blocks_bottom_right: Point) -> None:
        self.left_tab = left_tab
        self.right_tab = right_tab
        self.blocks_top_left = blocks_top_left
        self.blocks_bottom_right = blocks_bottom_right
        self.current_group_idx = 0
        self._compute_block_positions()
        self.calibrated = True

    def _compute_block_positions(self) -> None:
        if not self.blocks_top_left or not self.blocks_bottom_right:
            self.color_blocks = {}
            return
        tl_x, tl_y = self.blocks_top_left
        br_x, br_y = self.blocks_bottom_right
        col_step = (br_x - tl_x) / (self.BLOCK_COLS - 1) if self.BLOCK_COLS > 1 else 0
        row_step = (br_y - tl_y) / (self.BLOCK_ROWS - 1) if self.BLOCK_ROWS > 1 else 0
        self.color_blocks = {}
        for row in range(self.BLOCK_ROWS):
            for col in range(self.BLOCK_COLS):
                idx = row * self.BLOCK_COLS + col
                self.color_blocks[idx] = (round(tl_x + col * col_step), round(tl_y + row * row_step))

    def reset(self) -> None:
        self.__dict__.update(PaletteCalibration().__dict__)

    def compute_relative(self, window_offset: Point) -> Dict[str, list[int]]:
        wx, wy = window_offset
        return {
            'left_tab': [self.left_tab[0] - wx, self.left_tab[1] - wy],
            'right_tab': [self.right_tab[0] - wx, self.right_tab[1] - wy],
            'blocks_top_left': [self.blocks_top_left[0] - wx, self.blocks_top_left[1] - wy],
            'blocks_bottom_right': [self.blocks_bottom_right[0] - wx, self.blocks_bottom_right[1] - wy],
        }

    @classmethod
    def from_window_relative(cls, window_offset: Point, relative_data: Dict[str, list[int]]) -> "PaletteCalibration":
        wx, wy = window_offset
        obj = cls()
        obj.calibrate(
            left_tab=(wx + relative_data['left_tab'][0], wy + relative_data['left_tab'][1]),
            right_tab=(wx + relative_data['right_tab'][0], wy + relative_data['right_tab'][1]),
            blocks_top_left=(wx + relative_data['blocks_top_left'][0], wy + relative_data['blocks_top_left'][1]),
            blocks_bottom_right=(wx + relative_data['blocks_bottom_right'][0], wy + relative_data['blocks_bottom_right'][1]),
        )
        return obj

    def to_dict(self) -> Dict[str, object]:
        return {
            'left_tab': list(self.left_tab) if self.left_tab else None,
            'right_tab': list(self.right_tab) if self.right_tab else None,
            'blocks_top_left': list(self.blocks_top_left) if self.blocks_top_left else None,
            'blocks_bottom_right': list(self.blocks_bottom_right) if self.blocks_bottom_right else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "PaletteCalibration":
        obj = cls()
        if data.get('left_tab') and data.get('right_tab') and data.get('blocks_top_left') and data.get('blocks_bottom_right'):
            obj.calibrate(
                left_tab=tuple(data['left_tab']),
                right_tab=tuple(data['right_tab']),
                blocks_top_left=tuple(data['blocks_top_left']),
                blocks_bottom_right=tuple(data['blocks_bottom_right']),
            )
        return obj


@dataclass
class ToolbarCalibration:
    brush: Optional[Point] = None
    bucket: Optional[Point] = None

    @property
    def calibrated(self) -> bool:
        return self.brush is not None and self.bucket is not None

    def to_dict(self) -> Dict[str, object]:
        return {
            'brush': list(self.brush) if self.brush else None,
            'bucket': list(self.bucket) if self.bucket else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "ToolbarCalibration":
        brush = tuple(data['brush']) if data.get('brush') else None
        bucket = tuple(data['bucket']) if data.get('bucket') else None
        return cls(brush=brush, bucket=bucket)

    def compute_relative(self, window_offset: Point) -> Dict[str, list[int]]:
        wx, wy = window_offset
        return {
            'brush': [self.brush[0] - wx, self.brush[1] - wy],
            'bucket': [self.bucket[0] - wx, self.bucket[1] - wy],
        }

    @classmethod
    def from_window_relative(cls, window_offset: Point, relative_data: Dict[str, list[int]]) -> "ToolbarCalibration":
        wx, wy = window_offset
        return cls(
            brush=(wx + relative_data['brush'][0], wy + relative_data['brush'][1]),
            bucket=(wx + relative_data['bucket'][0], wy + relative_data['bucket'][1]),
        )
