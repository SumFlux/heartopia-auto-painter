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
        '#051616', '#434747', '#828484', '#b9b7b6', '#feffff', '#a8978e',
    ]),
    # 组 1 - 红色系 (10色)
    ("红色系", [
        '#cf354d', '#ee6f72', '#a6263d', '#f5ada8', '#ca8988',
        '#9f6d6b', '#7b5859', '#9c857e', '#8c746c', '#75584d',
    ]),
    # 组 2 - 橙红色系 (10色)
    ("橙红色系", [
        '#e95e2b', '#f98358', '#ab4226', '#feba9f', '#d9947d',
        '#af7868', '#825951', '#b09a92', '#998179', '#795e54',
    ]),
    # 组 3 - 橙色系 (10色)
    ("橙色系", [
        '#f49e16', '#feae3b', '#b16f16', '#fece92', '#daa76c',
        '#b3814b', '#7a542c', '#f5e4cf', '#c1b0a1', '#88776b',
    ]),
    # 组 4 - 黄色系 (10色)
    ("黄色系", [
        '#edca16', '#f9d838', '#b39416', '#fae792', '#d3bf74',
        '#a89460', '#827150', '#a59282', '#8f796c', '#765a4f',
    ]),
    # 组 5 - 黄绿色系 (10色)
    ("黄绿色系", [
        '#a9bd20', '#b3bf50', '#818745', '#a29575', '#8f8067',
        '#775c50', '#75584d', '#75584d', '#75584d', '#74574c',
    ]),
    # 组 6 - 绿色系 (10色)
    ("绿色系", [
        '#05a25d', '#41b97b', '#057447', '#9edaaf', '#81b694',
        '#6c8772', '#646a5d', '#918478', '#7f685e', '#75584d',
    ]),
    # 组 7 - 青绿色系 (10色)
    ("青绿色系", [
        '#058781', '#05aba0', '#056966', '#82cec3', '#65aaa3',
        '#5b7f79', '#5d6662', '#8d8178', '#7e685e', '#75584d',
    ]),
    # 组 8 - 青色系 (10色)
    ("青色系", [
        '#05729c', '#0599ba', '#055878', '#79bbca', '#5193a5',
        '#2d7082', '#235767', '#b8c3c4', '#969998', '#796c66',
    ]),
    # 组 9 - 蓝色系 (10色)
    ("蓝色系", [
        '#055ea6', '#2b83c1', '#054782', '#84a8c9', '#6283a3',
        '#556c85', '#525c68', '#9b908e', '#887671', '#775c52',
    ]),
    # 组 10 - 蓝紫色系 (10色)
    ("蓝紫色系", [
        '#534da1', '#7577bd', '#3e387e', '#a2a0c7', '#787aa1',
        '#5c5d82', '#4c4e67', '#b5afb3', '#958989', '#7b6762',
    ]),
    # 组 11 - 紫色系 (10色)
    ("紫色系", [
        '#813d8b', '#a167a9', '#602c6c', '#ba9fbb', '#98809b',
        '#7d6674', '#715e60', '#89716a', '#795e54', '#75584d',
    ]),
    # 组 12 - 粉色系 (10色)
    ("粉色系", [
        '#ad356f', '#cf6b8f', '#862658', '#d9a3b5', '#b88594',
        '#8f6771', '#795e61', '#98827c', '#82685f', '#75584d',
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
