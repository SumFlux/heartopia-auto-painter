"""
heartopia_app.domain.palette — unified palette source.
"""

from typing import List, Tuple

COLOR_GROUPS: List[Tuple[str, List[str]]] = [
    ("黑白灰", [
        '#051616', '#414545', '#808282', '#bebfbf', '#feffff',
    ]),
    ("红色系", [
        '#cf354d', '#ee6f72', '#a6263d', '#f5aca6', '#c98483',
        '#a35d5e', '#69313b', '#e7d5d5', '#c0acab', '#755e5e',
    ]),
    ("橙红色系", [
        '#e95e2b', '#f98358', '#ab4226', '#feba9f', '#d9937c',
        '#af6c58', '#753b31', '#e9d5d0', '#c1aca6', '#755e59',
    ]),
    ("橙色系", [
        '#f49e16', '#feae3b', '#b16f16', '#fece92', '#daa76d',
        '#b3814b', '#795126', '#f5e4cf', '#cdbca9', '#806f5e',
    ]),
    ("黄色系", [
        '#edca16', '#f9d838', '#b39416', '#fae791', '#d3be6f',
        '#ab954b', '#756326', '#eee7c7', '#c6bfa2', '#787259',
    ]),
    ("黄绿色系", [
        '#a8bc16', '#b6c931', '#758616', '#d8df93', '#adb76d',
        '#85914b', '#535e2b', '#e6e9c7', '#bcc2a3', '#6e745d',
    ]),
    ("绿色系", [
        '#05a25d', '#41b97b', '#057447', '#9cdaad', '#76b28b',
        '#4f8969', '#245640', '#c3e0cc', '#9db7a6', '#53695d',
    ]),
    ("青绿色系", [
        '#058781', '#05aba0', '#056966', '#7ecdc2', '#55a49c',
        '#2b7e78', '#054b4b', '#bee0da', '#98b7b2', '#4e6b66',
    ]),
    ("青色系", [
        '#05729c', '#0599ba', '#055878', '#79bbca', '#5193a5',
        '#246d7f', '#05495b', '#c6dde2', '#9eb5ba', '#4f676f',
    ]),
    ("蓝色系", [
        '#055ea6', '#2b83c1', '#054782', '#83a8c9', '#5d80a1',
        '#365b7f', '#193b56', '#c1cdd5', '#9ba6b0', '#4c5967',
    ]),
    ("蓝紫色系", [
        '#534da1', '#7577bd', '#3e387e', '#a2a0c7', '#787aa1',
        '#55567e', '#333555', '#c9cad5', '#a2a3b0', '#565869',
    ]),
    ("紫色系", [
        '#813d8b', '#a167a9', '#602b6c', '#b89bb9', '#907395',
        '#6c4d73', '#432e4b', '#cfc9d1', '#aba1ac', '#605665',
    ]),
    ("粉色系", [
        '#ad356f', '#cf6b8f', '#862658', '#d9a1b4', '#b47a8c',
        '#8b5367', '#60354b', '#e4d5da', '#bcadb1', '#725e66',
    ]),
]

GROUP_SIZES = [len(colors) for _, colors in COLOR_GROUPS]
TOTAL_GROUPS = len(COLOR_GROUPS)


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _build_derived_data():
    flat_colors = []
    color_id_map = {}
    palette_rgb = []
    hex_to_group = {}

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


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    return _hex_to_rgb(hex_str)


def find_closest_color(r: int, g: int, b: int) -> Tuple[str, str]:
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
    target_hex = target_hex.lower()
    if target_hex in HEX_TO_GROUP:
        return HEX_TO_GROUP[target_hex]

    try:
        r, g, b = _hex_to_rgb(target_hex)
    except (ValueError, IndexError):
        return 0, 0

    _, color_id = find_closest_color(r, g, b)
    parts = color_id.split('-')
    return int(parts[0]), int(parts[1])


CANVAS_BACKGROUND_COLORS = frozenset({'transparent', 'x', 'y', '#a8978e'})
