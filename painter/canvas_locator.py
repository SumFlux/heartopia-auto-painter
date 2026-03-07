"""
心动小镇自动画画脚本 — 画布定位模块

用户手动标定画布四个角，使用双线性插值计算每个像素的屏幕坐标。
支持非矩形（梯形等）画布，边缘精度更高。
向后兼容旧版 2 点标定。
"""

from typing import Tuple, Dict, Optional


class CanvasLocator:
    """画布定位器（4 角双线性插值）"""

    def __init__(self):
        self.calibrated = False
        self.top_left: Tuple[int, int] = (0, 0)
        self.top_right: Tuple[int, int] = (0, 0)
        self.bottom_left: Tuple[int, int] = (0, 0)
        self.bottom_right: Tuple[int, int] = (0, 0)
        self.grid_width: int = 0
        self.grid_height: int = 0
        # 全局偏移量（用于微调标定误差）
        self.offset_x: int = 0
        self.offset_y: int = 0

    def calibrate(self, grid_width: int, grid_height: int,
                  top_left: Tuple[int, int], bottom_right: Tuple[int, int],
                  top_right: Optional[Tuple[int, int]] = None,
                  bottom_left: Optional[Tuple[int, int]] = None):
        """
        标定画布（4 角双线性 / 向后兼容 2 角矩形）

        :param grid_width: 像素矩阵宽度
        :param grid_height: 像素矩阵高度
        :param top_left: 左上角屏幕坐标
        :param bottom_right: 右下角屏幕坐标
        :param top_right: 右上角屏幕坐标（None 则从 top_left/bottom_right 推断矩形）
        :param bottom_left: 左下角屏幕坐标（None 则从 top_left/bottom_right 推断矩形）
        """
        self.top_left = top_left
        self.bottom_right = bottom_right
        self.grid_width = grid_width
        self.grid_height = grid_height

        # 向后兼容：缺少 top_right / bottom_left 时按矩形推断
        if top_right is None:
            top_right = (bottom_right[0], top_left[1])
        if bottom_left is None:
            bottom_left = (top_left[0], bottom_right[1])

        self.top_right = top_right
        self.bottom_left = bottom_left

        self.calibrated = True

    def get_screen_pos(self, px: int, py: int) -> Tuple[int, int]:
        """
        将像素矩阵坐标转换为屏幕点击坐标（双线性插值）

        :param px: 像素 x 坐标 (0-based)
        :param py: 像素 y 坐标 (0-based)
        :return: (screen_x, screen_y)
        """
        if not self.calibrated:
            raise RuntimeError("画布尚未标定")

        # 归一化参数 u, v ∈ [0, 1]
        u = px / (self.grid_width - 1) if self.grid_width > 1 else 0.0
        v = py / (self.grid_height - 1) if self.grid_height > 1 else 0.0

        # 双线性插值: P = (1-u)(1-v)*TL + u(1-v)*TR + (1-u)v*BL + uv*BR
        tl = self.top_left
        tr = self.top_right
        bl = self.bottom_left
        br = self.bottom_right

        screen_x = round(
            (1 - u) * (1 - v) * tl[0] +
            u * (1 - v) * tr[0] +
            (1 - u) * v * bl[0] +
            u * v * br[0]
        ) + self.offset_x
        screen_y = round(
            (1 - u) * (1 - v) * tl[1] +
            u * (1 - v) * tr[1] +
            (1 - u) * v * bl[1] +
            u * v * br[1]
        ) + self.offset_y
        return (screen_x, screen_y)

    def set_offset(self, offset_x: int, offset_y: int):
        """设置全局偏移量（微调标定误差）"""
        self.offset_x = offset_x
        self.offset_y = offset_y

    def get_pixel_size(self) -> Tuple[float, float]:
        """获取每个像素在屏幕上的近似大小（用顶边和左边估算）"""
        if self.grid_width > 1:
            step_x = abs(self.top_right[0] - self.top_left[0]) / (self.grid_width - 1)
        else:
            step_x = 0.0
        if self.grid_height > 1:
            step_y = abs(self.bottom_left[1] - self.top_left[1]) / (self.grid_height - 1)
        else:
            step_y = 0.0
        return (step_x, step_y)

    def reset(self):
        """重置所有状态到初始值（清除标定时使用）"""
        self.calibrated = False
        self.top_left = (0, 0)
        self.top_right = (0, 0)
        self.bottom_left = (0, 0)
        self.bottom_right = (0, 0)
        self.grid_width = 0
        self.grid_height = 0
        self.offset_x = 0
        self.offset_y = 0

    def to_dict(self) -> Dict:
        """序列化为字典（用于持久化保存）"""
        return {
            'top_left': list(self.top_left),
            'top_right': list(self.top_right),
            'bottom_left': list(self.bottom_left),
            'bottom_right': list(self.bottom_right),
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
        }

    def from_dict(self, data: Dict):
        """从字典恢复（向后兼容旧版无 top_right/bottom_left 的 JSON）"""
        self.calibrate(
            grid_width=data['grid_width'],
            grid_height=data['grid_height'],
            top_left=tuple(data['top_left']),
            bottom_right=tuple(data['bottom_right']),
            top_right=tuple(data['top_right']) if 'top_right' in data else None,
            bottom_left=tuple(data['bottom_left']) if 'bottom_left' in data else None,
        )
        self.offset_x = data.get('offset_x', 0)
        self.offset_y = data.get('offset_y', 0)
