"""
心动小镇自动画画脚本 — 画布定位模块

用户手动标定画布两个角，根据像素矩阵尺寸计算每个像素的屏幕坐标。
不依赖任何特定鼠标库（纯坐标计算）。
"""

from typing import Tuple, Dict


class CanvasLocator:
    """画布定位器"""

    def __init__(self):
        self.calibrated = False
        self.top_left: Tuple[int, int] = (0, 0)
        self.bottom_right: Tuple[int, int] = (0, 0)
        self.grid_width: int = 0
        self.grid_height: int = 0
        self.pixel_step_x: float = 0.0
        self.pixel_step_y: float = 0.0
        # 全局偏移量（用于微调标定误差）
        self.offset_x: int = 0
        self.offset_y: int = 0

    def calibrate(self, grid_width: int, grid_height: int,
                  top_left: Tuple[int, int], bottom_right: Tuple[int, int]):
        """
        标定画布

        :param grid_width: 像素矩阵宽度
        :param grid_height: 像素矩阵高度
        :param top_left: 画布左上角第一个像素的屏幕坐标
        :param bottom_right: 画布右下角最后一个像素的屏幕坐标
        """
        self.top_left = top_left
        self.bottom_right = bottom_right
        self.grid_width = grid_width
        self.grid_height = grid_height

        if grid_width > 1:
            self.pixel_step_x = (bottom_right[0] - top_left[0]) / (grid_width - 1)
        else:
            self.pixel_step_x = 0

        if grid_height > 1:
            self.pixel_step_y = (bottom_right[1] - top_left[1]) / (grid_height - 1)
        else:
            self.pixel_step_y = 0

        self.calibrated = True

    def get_screen_pos(self, px: int, py: int) -> Tuple[int, int]:
        """
        将像素矩阵坐标转换为屏幕点击坐标

        :param px: 像素 x 坐标 (0-based)
        :param py: 像素 y 坐标 (0-based)
        :return: (screen_x, screen_y)
        """
        if not self.calibrated:
            raise RuntimeError("画布尚未标定")

        screen_x = round(self.top_left[0] + px * self.pixel_step_x) + self.offset_x
        screen_y = round(self.top_left[1] + py * self.pixel_step_y) + self.offset_y
        return (screen_x, screen_y)

    def set_offset(self, offset_x: int, offset_y: int):
        """设置全局偏移量（微调标定误差）"""
        self.offset_x = offset_x
        self.offset_y = offset_y

    def reset(self):
        """重置所有状态到初始值（清除标定时使用）"""
        self.calibrated = False
        self.top_left = (0, 0)
        self.bottom_right = (0, 0)
        self.grid_width = 0
        self.grid_height = 0
        self.pixel_step_x = 0.0
        self.pixel_step_y = 0.0
        self.offset_x = 0
        self.offset_y = 0

    def get_pixel_size(self) -> Tuple[float, float]:
        """获取每个像素在屏幕上的大小"""
        return (abs(self.pixel_step_x), abs(self.pixel_step_y))

    def to_dict(self) -> Dict:
        """序列化为字典（用于持久化保存）"""
        return {
            'top_left': list(self.top_left),
            'bottom_right': list(self.bottom_right),
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
        }

    def from_dict(self, data: Dict):
        """从字典恢复"""
        self.calibrate(
            grid_width=data['grid_width'],
            grid_height=data['grid_height'],
            top_left=tuple(data['top_left']),
            bottom_right=tuple(data['bottom_right']),
        )
        self.offset_x = data.get('offset_x', 0)
        self.offset_y = data.get('offset_y', 0)
