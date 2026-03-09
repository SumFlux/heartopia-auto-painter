"""
纯算法函数 — 从旧版 painter 代码中提取。

所有函数均为纯函数，不依赖 self / IO / 线程。
"""

from __future__ import annotations

from collections import deque
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

import numpy as np

if TYPE_CHECKING:
    from PIL import Image


# ---------------------------------------------------------------------------
# 坐标排序
# ---------------------------------------------------------------------------

def snake_sort(coords: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """蛇形排序：偶数行从左到右，奇数行从右到左。

    返回排序后的新列表，不修改原列表。
    """
    return sorted(coords, key=lambda c: (c[1], c[0] if c[1] % 2 == 0 else -c[0]))


# ---------------------------------------------------------------------------
# 连通分量
# ---------------------------------------------------------------------------

def find_connected_components(
    coords: List[Tuple[int, int]],
) -> List[List[Tuple[int, int]]]:
    """对 (x, y) 坐标列表做 8-连通 BFS，返回各连通分量列表。"""
    coord_set: Set[Tuple[int, int]] = set(coords)
    visited: Set[Tuple[int, int]] = set()
    components: List[List[Tuple[int, int]]] = []

    for start in coords:
        if start in visited:
            continue
        component: List[Tuple[int, int]] = []
        queue: deque[Tuple[int, int]] = deque([start])
        visited.add(start)
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for nx, ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1),(x+1,y+1),(x+1,y-1),(x-1,y+1),(x-1,y-1)]:
                if (nx, ny) in coord_set and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
        components.append(component)

    return components


# ---------------------------------------------------------------------------
# 边界 / 内部 分类
# ---------------------------------------------------------------------------

def classify_boundary_interior(
    component: List[Tuple[int, int]],
    group_key: str,
    pixel_color_map: Dict[Tuple[int, int], str],
    grid_w: int,
    grid_h: int,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """将连通分量拆分为 边界像素 和 内部像素。

    判定规则：
    - 像素的 8-邻域超出网格范围 → 边界
    - 像素的 8-邻域不在同一分量且颜色不同 → 边界
    - 其余 → 内部

    返回 (boundary, interior)，各自按蛇形排序。
    """
    comp_set: Set[Tuple[int, int]] = set(component)
    boundary: List[Tuple[int, int]] = []
    interior: List[Tuple[int, int]] = []

    for x, y in component:
        is_boundary = False
        for nx, ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1),(x+1,y+1),(x+1,y-1),(x-1,y+1),(x-1,y-1)]:
            if nx < 0 or ny < 0 or nx >= grid_w or ny >= grid_h:
                is_boundary = True
                break
            if (nx, ny) not in comp_set:
                neighbor_color = pixel_color_map.get((nx, ny))
                if neighbor_color != group_key:
                    is_boundary = True
                    break
        if is_boundary:
            boundary.append((x, y))
        else:
            interior.append((x, y))

    boundary = snake_sort(boundary)
    interior = snake_sort(interior)
    return boundary, interior


# ---------------------------------------------------------------------------
# 子区域分析
# ---------------------------------------------------------------------------

def find_4connected_subregions(
    pixels: List[Tuple[int, int]],
) -> List[List[Tuple[int, int]]]:
    """对像素列表做 4-连通 BFS，返回子区域列表。"""
    pixel_set: Set[Tuple[int, int]] = set(pixels)
    visited: Set[Tuple[int, int]] = set()
    regions: List[List[Tuple[int, int]]] = []

    for start in pixels:
        if start in visited:
            continue
        region: List[Tuple[int, int]] = []
        queue: deque[Tuple[int, int]] = deque([start])
        visited.add(start)
        while queue:
            x, y = queue.popleft()
            region.append((x, y))
            for nx, ny in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                if (nx, ny) in pixel_set and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
        regions.append(region)

    return regions


# ---------------------------------------------------------------------------
# 校准用边框点
# ---------------------------------------------------------------------------

def build_border_points(grid_w: int, grid_h: int) -> List[Tuple[int, int]]:
    """生成顺时针边框坐标序列，用于校准测试。

    顺序：上边(左→右) → 右边(上→下) → 下边(右→左) → 左边(下→上)。
    """
    border_points: List[Tuple[int, int]] = []

    # 上边
    for x in range(grid_w):
        border_points.append((x, 0))
    # 右边
    for y in range(1, grid_h):
        border_points.append((grid_w - 1, y))
    # 下边
    for x in range(grid_w - 2, -1, -1):
        border_points.append((x, grid_h - 1))
    # 左边
    for y in range(grid_h - 2, 0, -1):
        border_points.append((0, y))

    return border_points


# ---------------------------------------------------------------------------
# numpy 辅助 — 布尔 mask 连通分量
# ---------------------------------------------------------------------------

def _connected_components_mask(
    mask: np.ndarray,
) -> Tuple[np.ndarray, int]:
    """对 numpy 布尔 mask 做 BFS 连通分量标记。

    返回 (labeled, num_labels)：
    - labeled: 与 mask 同形状的 int32 数组，每个连通分量赋唯一标签 (从 1 开始)
    - num_labels: 连通分量数量
    """
    h, w = mask.shape
    labeled = np.zeros((h, w), dtype=np.int32)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return labeled, 0

    remaining: Set[Tuple[int, int]] = set(zip(ys.tolist(), xs.tolist()))
    current_label = 0

    while remaining:
        current_label += 1
        seed = next(iter(remaining))
        queue = [seed]
        remaining.discard(seed)
        while queue:
            cy, cx = queue.pop()
            labeled[cy, cx] = current_label
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if (ny, nx) in remaining:
                    remaining.discard((ny, nx))
                    queue.append((ny, nx))

    return labeled, current_label


# ---------------------------------------------------------------------------
# 红色标记点检测
# ---------------------------------------------------------------------------

def detect_canvas_markers(
    screenshot: "Image.Image",
    window_offset: Tuple[int, int],
    on_log: Optional[Callable[[str], None]] = None,
) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
    """从截图中检测 4 个红色标记点，返回屏幕坐标 (左上, 右上, 左下, 右下)。

    Parameters
    ----------
    screenshot : PIL.Image.Image
        截图图像。
    window_offset : (int, int)
        窗口左上角在屏幕上的偏移 (x, y)。
    on_log : callable, optional
        日志回调。

    Raises
    ------
    RuntimeError
        找不到足够的红色标记点时抛出。
    """

    def _log(msg: str) -> None:
        if on_log:
            on_log(msg)

    img_array = np.array(screenshot)[:, :, :3]
    img_h, img_w = img_array.shape[:2]
    _log(f"  截图尺寸: {img_w}x{img_h}")

    # 居中搜索区域
    search_w = min(1200, img_w)
    margin = (img_w - search_w) // 2
    search_left, search_right = margin, margin + search_w
    _log(f"  搜索区域: x=[{search_left},{search_right}] (居中 {search_w}px)")

    search_area = img_array[:, search_left:search_right, :]
    r, g, b = search_area[:, :, 0], search_area[:, :, 1], search_area[:, :, 2]

    # 红色阈值
    red_mask_local = (r > 180) & (g < 80) & (b < 80)
    red_mask = np.zeros((img_h, img_w), dtype=bool)
    red_mask[:, search_left:search_right] = red_mask_local

    red_count = int(np.sum(red_mask))
    _log(f"  红色像素总数: {red_count}")
    if red_count == 0:
        raise RuntimeError("截图中未找到红色像素，请确保在画布4个角各画了一个红色标记点")

    ys, xs = np.where(red_mask)
    _log(
        f"  红色像素范围: x=[{int(xs.min())},{int(xs.max())}], "
        f"y=[{int(ys.min())},{int(ys.max())}]"
    )

    # 连通分量
    labeled, num_features = _connected_components_mask(red_mask)
    _log(f"  连通分量数: {num_features}")

    if num_features < 4:
        raise RuntimeError(
            f"只找到 {num_features} 个红色区域，需要 4 个角标记点。"
            "请确保画布4个角都画了红色标记"
        )

    # 聚类信息
    clusters = []
    for i in range(1, num_features + 1):
        cy, cx = np.where(labeled == i)
        area = len(cx)
        centroid_x = float(np.mean(cx))
        centroid_y = float(np.mean(cy))
        clusters.append({"id": i, "area": area, "cx": centroid_x, "cy": centroid_y})

    clusters.sort(key=lambda c: c["area"], reverse=True)

    for c in clusters[: min(8, len(clusters))]:
        _log(f"  簇#{c['id']}: 面积={c['area']}, 质心=({c['cx']:.1f}, {c['cy']:.1f})")

    top4 = clusters[:4]
    if len(top4) < 4:
        raise RuntimeError(f"红色区域不足4个（找到{len(top4)}个）")

    _log(f"  选取最大的4个簇: {[c['id'] for c in top4]}")

    # 按 y 分上下，再按 x 分左右
    top4.sort(key=lambda c: c["cy"])
    upper = sorted(top4[:2], key=lambda c: c["cx"])
    lower = sorted(top4[2:], key=lambda c: c["cx"])

    tl_img = (upper[0]["cx"], upper[0]["cy"])
    tr_img = (upper[1]["cx"], upper[1]["cy"])
    bl_img = (lower[0]["cx"], lower[0]["cy"])
    br_img = (lower[1]["cx"], lower[1]["cy"])

    _log(
        f"  图像坐标 — 左上:({tl_img[0]:.1f},{tl_img[1]:.1f}) "
        f"右上:({tr_img[0]:.1f},{tr_img[1]:.1f}) "
        f"左下:({bl_img[0]:.1f},{bl_img[1]:.1f}) "
        f"右下:({br_img[0]:.1f},{br_img[1]:.1f})"
    )

    def to_screen(img_x: float, img_y: float) -> Tuple[int, int]:
        screen_x = int(round(img_x)) + window_offset[0]
        screen_y = int(round(img_y)) + window_offset[1]
        return (screen_x, screen_y)

    top_left = to_screen(*tl_img)
    top_right = to_screen(*tr_img)
    bottom_left = to_screen(*bl_img)
    bottom_right = to_screen(*br_img)

    return (top_left, top_right, bottom_left, bottom_right)
