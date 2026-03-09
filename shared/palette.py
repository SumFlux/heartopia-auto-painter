"""
shared/palette.py — 心动小镇调色板唯一数据源

全项目（converter + painter）统一从此模块导入颜色数据。
任何调色板变更只需修改此文件。

数据结构：
- COLOR_GROUPS: 13 组颜色，每组包含 (组名, [hex颜色列表])
  - 组 0（黑白灰）: 6 色
  - 组 1-12: 各 10 色
  - 总计 126 色

- FLAT_COLORS: 所有颜色的一维列表（126 色，按组顺序排列）

- COLOR_ID_MAP: { hex_color -> "组号-组内索引" } 的反向映射
  - 组号从 0 开始（0 = 黑白灰，1 = 红色系 ...）
  - 组内索引从 0 开始

- PALETTE_RGB: [(r, g, b, hex_color, color_id), ...] 预计算列表，供快速匹配
"""

from typing import Dict, List, Tuple

# ======================================================
#  13 组调色板（来自游戏截图实际取色）
# ======================================================
COLOR_GROUPS: List[Tuple[str, List[str]]] = [
    # 组 0 - 黑白灰 (6色)
    ("黑白灰", [
        '#051616', '#414545', '#808282', '#bebfbf', '#feffff', '#a8978e',#最后一个为背景色，画画用不上，也不能拿来上色
    ]),
    # 组 1 - 红色系 (10色)
    ("红色系", [
        '#cf354d', '#ee6f72', '#a6263d', '#f5aca6', '#c98483',
        '#a35d5e', '#69313b', '#e7d5d5', '#c0acab', '#755e5e',
    ]),
    # 组 2 - 橙红色系 (10色)
    ("橙红色系", [
        '#e95e2b', '#f98358', '#ab4226', '#feba9f', '#d9937c',
        '#af6c58', '#753b31', '#e9d5d0', '#c1aca6', '#755e59',
    ]),
    # 组 3 - 橙色系 (10色)
    ("橙色系", [
        '#f49e16', '#feae3b', '#b16f16', '#fece92', '#daa76d',
        '#b3814b', '#795126', '#f5e4cf', '#cdbca9', '#806f5e',
    ]),
    # 组 4 - 黄色系 (10色)
    ("黄色系", [
        '#edca16', '#f9d838', '#b39416', '#fae791', '#d3be6f',
        '#ab954b', '#756326', '#eee7c7', '#c6bfa2', '#787259',
    ]),
    # 组 5 - 黄绿色系 (10色)
    ("黄绿色系", [
        '#a8bc16', '#b6c931', '#758616', '#d8df93', '#adb76d',
        '#85914b', '#535e2b', '#e6e9c7', '#bcc2a3', '#6e745d',
    ]),
    # 组 6 - 绿色系 (10色)
    ("绿色系", [
        '#05a25d', '#41b97b', '#057447', '#9cdaad', '#76b28b',
        '#4f8969', '#245640', '#c3e0cc', '#9db7a6', '#53695d',
    ]),
    # 组 7 - 青绿色系 (10色)
    ("青绿色系", [
        '#058781', '#05aba0', '#056966', '#7ecdc2', '#55a49c',
        '#2b7e78', '#054b4b', '#bee0da', '#98b7b2', '#4e6b66',
    ]),
    # 组 8 - 青色系 (10色)
    ("青色系", [
        '#05729c', '#0599ba', '#055878', '#79bbca', '#5193a5',
        '#246d7f', '#05495b', '#c6dde2', '#9eb5ba', '#4f676f',
    ]),
    # 组 9 - 蓝色系 (10色)
    ("蓝色系", [
        '#055ea6', '#2b83c1', '#054782', '#83a8c9', '#5d80a1',
        '#365b7f', '#193b56', '#c1cdd5', '#9ba6b0', '#4c5967',
    ]),
    # 组 10 - 蓝紫色系 (10色)
    ("蓝紫色系", [
        '#534da1', '#7577bd', '#3e387e', '#a2a0c7', '#787aa1',
        '#55567e', '#333555', '#c9cad5', '#a2a3b0', '#565869',
    ]),
    # 组 11 - 紫色系 (10色)
    ("紫色系", [
        '#813d8b', '#a167a9', '#602b6c', '#b89bb9', '#907395',
        '#6c4d73', '#432e4b', '#cfc9d1', '#aba1ac', '#605665',
    ]),
    # 组 12 - 粉色系 (10色)
    ("粉色系", [
        '#ad356f', '#cf6b8f', '#862658', '#d9a1b4', '#b47a8c',
        '#8b5367', '#60354b', '#e4d5da', '#bcadb1', '#725e66',
    ]),
]

# 每组的色块数量
GROUP_SIZES: List[int] = [len(colors) for _, colors in COLOR_GROUPS]
TOTAL_GROUPS: int = len(COLOR_GROUPS)

# ======================================================
#  派生数据（自动从 COLOR_GROUPS 构建）
# ======================================================

def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """十六进制颜色转 RGB"""
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _build_derived_data():
    """一次性构建所有派生数据结构"""
    flat_colors = []
    color_id_map = {}       # hex -> "group-index"
    palette_rgb = []        # [(r, g, b, hex, color_id), ...]
    hex_to_group = {}       # hex -> (group_idx, color_idx)

    for group_idx, (_, colors) in enumerate(COLOR_GROUPS):
        for color_idx, hex_color in enumerate(colors):
            hex_lower = hex_color.lower()
            color_id = f"{group_idx}-{color_idx}"

            flat_colors.append(hex_lower)
            color_id_map[hex_lower] = color_id
            hex_to_group[hex_lower] = (group_idx, color_idx)

            r, g, b = _hex_to_rgb(hex_lower)
            palette_rgb.append((r, g, b, hex_lower, color_id))

    return flat_colors, color_id_map, palette_rgb, hex_to_group


FLAT_COLORS, COLOR_ID_MAP, PALETTE_RGB, HEX_TO_GROUP = _build_derived_data()


# ======================================================
#  工具函数
# ======================================================

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """公开的 hex -> RGB 转换"""
    return _hex_to_rgb(hex_str)


def find_closest_color(r: int, g: int, b: int) -> Tuple[str, str]:
    """
    找到最接近的游戏颜色（欧几里得 RGB 平方距离）

    :param r, g, b: 目标颜色的 RGB 值（Python int）
    :return: (hex_color, color_id)
    """
    min_dist = float('inf')
    best_hex = PALETTE_RGB[0][3]
    best_id = PALETTE_RGB[0][4]

    for pr, pg, pb, hex_color, color_id in PALETTE_RGB:
        dr = r - pr
        dg = g - pg
        db = b - pb
        dist = dr * dr + dg * dg + db * db
        if dist < min_dist:
            min_dist = dist
            best_hex = hex_color
            best_id = color_id

    return best_hex, best_id


def get_closest_color_group(target_hex: str) -> Tuple[int, int]:
    """
    获取最接近颜色的 (组号, 组内索引)
    精确匹配优先，否则最近邻匹配
    """
    target_hex = target_hex.lower()
    if target_hex in HEX_TO_GROUP:
        return HEX_TO_GROUP[target_hex]

    try:
        r, g, b = _hex_to_rgb(target_hex)
    except (ValueError, IndexError):
        return (0, 0)

    _, color_id = find_closest_color(r, g, b)
    parts = color_id.split('-')
    return (int(parts[0]), int(parts[1]))


# ======================================================
#  画布背景色（这些颜色不需要绘制）
# ======================================================
CANVAS_BACKGROUND_COLORS = frozenset({'transparent', 'x', 'y'})
