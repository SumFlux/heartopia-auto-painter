"""
心动小镇自动画画脚本 — 画布定位模块

用户手动标定画布四个角，使用双线性插值计算每个像素的屏幕坐标。
支持非矩形（梯形等）画布，边缘精度更高。
向后兼容旧版 2 点标定。
"""

from typing import Tuple, Dict, Optional
import numpy as np


def _connected_components(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    """
    对二值 mask 做 4-连通分量标记（纯 numpy 实现，无需 scipy）。

    优化：先提取非零像素坐标到 set，只遍历非零像素做 BFS，
    避免遍历整个百万级像素的图像。

    :param mask: bool 二维数组
    :return: (labeled, num_features)
        labeled: 与 mask 同形状的 int 数组，0=背景，1..N=各连通分量
        num_features: 连通分量总数
    """
    h, w = mask.shape
    labeled = np.zeros((h, w), dtype=np.int32)

    # 提取所有非零像素坐标
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return labeled, 0

    remaining = set(zip(ys.tolist(), xs.tolist()))
    current_label = 0

    while remaining:
        current_label += 1
        # BFS from an arbitrary unvisited pixel
        seed = next(iter(remaining))
        queue = [seed]
        remaining.discard(seed)

        while queue:
            cy, cx = queue.pop()
            labeled[cy, cx] = current_label
            # 4-connected neighbors
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if (ny, nx) in remaining:
                    remaining.discard((ny, nx))
                    queue.append((ny, nx))

    return labeled, current_label


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

    def calibrate_from_window(self, grid_width: int, grid_height: int,
                              window_offset: Tuple[int, int],
                              relative_corners: Dict):
        """
        根据窗口位置 + 固定的窗口内相对坐标自动标定画布

        :param grid_width: 像素矩阵宽度
        :param grid_height: 像素矩阵高度
        :param window_offset: 游戏窗口客户区左上角屏幕坐标 (x, y)
        :param relative_corners: 四角相对于窗口客户区的偏移 {
            'top_left': [rx, ry], 'top_right': [rx, ry],
            'bottom_left': [rx, ry], 'bottom_right': [rx, ry]
        }
        """
        wx, wy = window_offset
        tl = (wx + relative_corners['top_left'][0], wy + relative_corners['top_left'][1])
        tr = (wx + relative_corners['top_right'][0], wy + relative_corners['top_right'][1])
        bl = (wx + relative_corners['bottom_left'][0], wy + relative_corners['bottom_left'][1])
        br = (wx + relative_corners['bottom_right'][0], wy + relative_corners['bottom_right'][1])
        self.calibrate(grid_width, grid_height, top_left=tl, bottom_right=br,
                       top_right=tr, bottom_left=bl)

    def compute_relative_corners(self, window_offset: Tuple[int, int]) -> Dict:
        """
        计算当前标定的四角相对于窗口客户区左上角的偏移量

        :param window_offset: 游戏窗口客户区左上角屏幕坐标 (x, y)
        :return: 四角相对偏移字典
        """
        wx, wy = window_offset
        return {
            'top_left': [self.top_left[0] - wx, self.top_left[1] - wy],
            'top_right': [self.top_right[0] - wx, self.top_right[1] - wy],
            'bottom_left': [self.bottom_left[0] - wx, self.bottom_left[1] - wy],
            'bottom_right': [self.bottom_right[0] - wx, self.bottom_right[1] - wy],
        }

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
        on_log=None,
    ) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """
        自动检测画布4角红色标记点的屏幕坐标。

        策略：直接在整个截图中搜索红色像素（R>180, G<80, B<80），
        然后对红色像素做聚类（DBSCAN），找到4个簇的质心，
        按几何位置分配为左上/右上/左下/右下。

        不再依赖背景色检测画布区域，因此无论画布是空白还是已画满内容都能工作。

        :param screenshot: 游戏窗口截图 (PIL Image)
        :param window_offset: 窗口左上角的屏幕坐标 (x, y)
        :param on_log: 可选日志回调 (str) -> None
        :return: (top_left, top_right, bottom_left, bottom_right) 各点的屏幕坐标
        :raises RuntimeError: 找不到足够的红色标记簇
        """
        def _log(msg):
            if on_log:
                on_log(msg)

        img_array = np.array(screenshot)[:, :, :3]
        img_h, img_w = img_array.shape[:2]
        _log(f"  截图尺寸: {img_w}x{img_h}")

        # Step 1: 限定搜索区域 — 只在水平居中的 1200px 宽度内搜索，排除两侧 UI（如调色板）
        search_w = min(1200, img_w)
        margin = (img_w - search_w) // 2
        search_left, search_right = margin, margin + search_w
        _log(f"  搜索区域: x=[{search_left},{search_right}] (居中 {search_w}px)")

        search_area = img_array[:, search_left:search_right, :]
        r, g, b = search_area[:, :, 0], search_area[:, :, 1], search_area[:, :, 2]
        red_mask_local = (r > 180) & (g < 80) & (b < 80)

        # 构建全图大小的 mask（坐标需要加回 search_left 偏移）
        red_mask = np.zeros((img_h, img_w), dtype=bool)
        red_mask[:, search_left:search_right] = red_mask_local

        red_count = int(np.sum(red_mask))
        _log(f"  红色像素总数: {red_count}")

        if red_count == 0:
            raise RuntimeError(
                "截图中未找到红色像素，请确保在画布4个角各画了一个红色标记点"
            )

        # 获取红色像素坐标
        ys, xs = np.where(red_mask)
        _log(f"  红色像素范围: x=[{int(xs.min())},{int(xs.max())}], y=[{int(ys.min())},{int(ys.max())}]")

        # Step 2: 聚类红色像素，找到4个标记点簇
        # 对红色 mask 做连通分量标记（纯 numpy 实现，无需 scipy）
        labeled, num_features = _connected_components(red_mask)
        _log(f"  连通分量数: {num_features}")

        if num_features < 4:
            raise RuntimeError(
                f"只找到 {num_features} 个红色区域，需要 4 个角标记点。"
                f"请确保画布4个角都画了红色标记"
            )

        # 计算每个连通分量的质心和面积
        clusters = []
        for i in range(1, num_features + 1):
            cy, cx = np.where(labeled == i)
            area = len(cx)
            centroid_x = float(np.mean(cx))
            centroid_y = float(np.mean(cy))
            clusters.append({
                'id': i,
                'area': area,
                'cx': centroid_x,
                'cy': centroid_y,
            })

        # 按面积排序，取最大的 4 个（标记点应该是最醒目的红色区域）
        clusters.sort(key=lambda c: c['area'], reverse=True)

        # 日志输出前几个簇的信息
        for c in clusters[:min(8, len(clusters))]:
            _log(f"  簇#{c['id']}: 面积={c['area']}, 质心=({c['cx']:.1f}, {c['cy']:.1f})")

        top4 = clusters[:4]
        if len(top4) < 4:
            raise RuntimeError(f"红色区域不足4个（找到{len(top4)}个）")

        _log(f"  选取最大的4个簇: {[c['id'] for c in top4]}")

        # Step 3: 按几何位置分配四角
        # 先按 y 排序分成上下两组，再在每组内按 x 排序分左右
        top4.sort(key=lambda c: c['cy'])
        upper = sorted(top4[:2], key=lambda c: c['cx'])  # y 较小的两个 = 上方
        lower = sorted(top4[2:], key=lambda c: c['cx'])  # y 较大的两个 = 下方

        tl_img = (upper[0]['cx'], upper[0]['cy'])
        tr_img = (upper[1]['cx'], upper[1]['cy'])
        bl_img = (lower[0]['cx'], lower[0]['cy'])
        br_img = (lower[1]['cx'], lower[1]['cy'])

        _log(f"  图像坐标 — 左上:({tl_img[0]:.1f},{tl_img[1]:.1f}) "
             f"右上:({tr_img[0]:.1f},{tr_img[1]:.1f}) "
             f"左下:({bl_img[0]:.1f},{bl_img[1]:.1f}) "
             f"右下:({br_img[0]:.1f},{br_img[1]:.1f})")

        # Step 4: 图像坐标 → 屏幕坐标
        def to_screen(img_x, img_y):
            screen_x = int(round(img_x)) + window_offset[0]
            screen_y = int(round(img_y)) + window_offset[1]
            return (screen_x, screen_y)

        top_left = to_screen(*tl_img)
        top_right = to_screen(*tr_img)
        bottom_left = to_screen(*bl_img)
        bottom_right = to_screen(*br_img)

        return (top_left, top_right, bottom_left, bottom_right)
