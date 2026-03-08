"""
心动小镇自动画画脚本 — 画布定位模块

用户手动标定画布四个角，使用双线性插值计算每个像素的屏幕坐标。
支持非矩形（梯形等）画布，边缘精度更高。
向后兼容旧版 2 点标定。
"""

from typing import Tuple, Dict, Optional
import numpy as np


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

    @staticmethod
    def detect_markers(
        screenshot: 'PIL.Image.Image',
        window_offset: Tuple[int, int],
    ) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """
        自动检测画布4角标记点的屏幕坐标。

        用户需要事先在游戏画布的4个角各画1个醒目颜色的像素（如纯红/纯黑），
        本方法从截图中自动识别这4个标记点的位置。

        :param screenshot: 游戏窗口截图 (PIL Image)
        :param window_offset: 窗口左上角的屏幕坐标 (x, y)
        :return: (top_left, top_right, bottom_left, bottom_right) 各点的屏幕坐标
        :raises RuntimeError: 找不到画布区域或某象限无标记
        """
        # Step 1: 找画布区域 — 背景色 #feffff = RGB(254,255,255)
        img_array = np.array(screenshot)[:, :, :3]
        bg = np.array([254, 255, 255])
        bg_mask = np.all(np.abs(img_array.astype(int) - bg) <= 3, axis=2)

        # 按行/列统计背景色像素数，超过30%阈值的行列构成画布区域
        row_counts = np.sum(bg_mask, axis=1)
        col_counts = np.sum(bg_mask, axis=0)
        canvas_rows = np.where(row_counts > 0.3 * bg_mask.shape[1])[0]
        canvas_cols = np.where(col_counts > 0.3 * bg_mask.shape[0])[0]

        if len(canvas_rows) == 0 or len(canvas_cols) == 0:
            raise RuntimeError("未找到画布区域，请确保游戏画布可见")

        canvas_top, canvas_bottom = int(canvas_rows[0]), int(canvas_rows[-1])
        canvas_left, canvas_right = int(canvas_cols[0]), int(canvas_cols[-1])

        # Step 2: 在画布区域内找非背景像素
        # 注意：标记点通常就画在画布最角落，不能收缩边距，否则会裁掉标记
        ct = canvas_top
        cb = canvas_bottom
        cl = canvas_left
        cr = canvas_right

        canvas_bg = bg_mask[ct:cb + 1, cl:cr + 1]
        marker_mask = ~canvas_bg  # 非背景 = 候选标记

        canvas_h, canvas_w = marker_mask.shape

        # Step 3: 四象限分区，每个象限找质心
        mid_x = canvas_w // 2
        mid_y = canvas_h // 2

        quadrant_defs = {
            '左上': (0, 0, mid_x, mid_y),
            '右上': (mid_x, 0, canvas_w, mid_y),
            '左下': (0, mid_y, mid_x, canvas_h),
            '右下': (mid_x, mid_y, canvas_w, canvas_h),
        }

        centroids = {}
        for name, (x1, y1, x2, y2) in quadrant_defs.items():
            quad_mask = marker_mask[y1:y2, x1:x2]
            ys, xs = np.where(quad_mask)
            if len(xs) == 0:
                raise RuntimeError(f"未在{name}找到标记点，请确保4个角都画了标记")
            # 质心（相对于画布子区域）
            cx = float(np.mean(xs)) + x1
            cy = float(np.mean(ys)) + y1
            centroids[name] = (cx, cy)

        # Step 4: 图像坐标 → 屏幕坐标
        # 质心坐标是相对于裁剪后的画布子区域(ct, cl)，需加回偏移
        def to_screen(cx, cy):
            img_x = cx + cl
            img_y = cy + ct
            screen_x = int(round(img_x)) + window_offset[0]
            screen_y = int(round(img_y)) + window_offset[1]
            return (screen_x, screen_y)

        # Step 5: 返回 (top_left, top_right, bottom_left, bottom_right)
        top_left = to_screen(*centroids['左上'])
        top_right = to_screen(*centroids['右上'])
        bottom_left = to_screen(*centroids['左下'])
        bottom_right = to_screen(*centroids['右下'])

        return (top_left, top_right, bottom_left, bottom_right)
