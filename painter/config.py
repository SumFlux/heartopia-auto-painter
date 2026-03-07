"""
心动小镇自动画画脚本 — 配置常量

颜色组映射、游戏窗口参数、速度预设
"""

# ── 游戏窗口参数 ──
GAME_PROCESS = "xdt.exe"
GAME_WINDOW_TITLE = "心动小镇"
GAME_WIDTH = 1920
GAME_HEIGHT = 1080

# ── 速度预设（每次点击后的延迟，单位毫秒） ──
SPEED_PRESETS = {
    'fast': 20,
    'normal': 50,
    'slow': 100,
    'very_slow': 200,
}

# ── 颜色组定义（从截图提取，与 converter 一致） ──
# 每组: (组名, [hex颜色列表])
COLOR_GROUPS = [
    # 组 1 - 黑白灰 (6色)
    ("黑白灰", ['#051616', '#434747', '#828484', '#b9b7b6', '#e0dbd9', '#a8978e']),
    # 组 2 - 红色系 (10色)
    ("红色系", ['#cf354d', '#ee6f72', '#a6263d', '#f5ada8', '#ca8988', '#9f6d6b', '#7b5859', '#9c857e', '#8c746c', '#75584d']),
    # 组 3 - 橙红色系 (10色)
    ("橙红色系", ['#e95e2b', '#f98358', '#ab4226', '#feba9f', '#d9947d', '#af7868', '#825951', '#b09a92', '#998179', '#795e54']),
    # 组 4 - 橙色系 (10色)
    ("橙色系", ['#f49e16', '#feae3b', '#b16f16', '#fece92', '#daa76c', '#b3814b', '#7a542c', '#f5e4cf', '#c1b0a1', '#88776b']),
    # 组 5 - 黄色系 (10色)
    ("黄色系", ['#edca16', '#f9d838', '#b39416', '#fae792', '#d3bf74', '#a89460', '#827150', '#a59282', '#8f796c', '#765a4f']),
    # 组 6 - 黄绿色系 (10色)
    ("黄绿色系", ['#a9bd20', '#b3bf50', '#818745', '#a29575', '#8f8067', '#775c50', '#75584d', '#75584d', '#75584d', '#74574c']),
    # 组 7 - 绿色系 (10色)
    ("绿色系", ['#05a25d', '#41b97b', '#057447', '#9edaaf', '#81b694', '#6c8772', '#646a5d', '#918478', '#7f685e', '#75584d']),
    # 组 8 - 青绿色系 (10色)
    ("青绿色系", ['#058781', '#05aba0', '#056966', '#82cec3', '#65aaa3', '#5b7f79', '#5d6662', '#8d8178', '#7e685e', '#75584d']),
    # 组 9 - 青色系 (10色)
    ("青色系", ['#05729c', '#0599ba', '#055878', '#79bbca', '#5193a5', '#2d7082', '#235767', '#b8c3c4', '#969998', '#796c66']),
    # 组 10 - 蓝色系 (10色)
    ("蓝色系", ['#055ea6', '#2b83c1', '#054782', '#84a8c9', '#6283a3', '#556c85', '#525c68', '#9b908e', '#887671', '#775c52']),
    # 组 11 - 蓝紫色系 (10色)
    ("蓝紫色系", ['#534da1', '#7577bd', '#3e387e', '#a2a0c7', '#787aa1', '#5c5d82', '#4c4e67', '#b5afb3', '#958989', '#7b6762']),
    # 组 12 - 紫色系 (10色)
    ("紫色系", ['#813d8b', '#a167a9', '#602c6c', '#ba9fbb', '#98809b', '#7d6674', '#715e60', '#89716a', '#795e54', '#75584d']),
    # 组 13 - 粉色系 (10色)
    ("粉色系", ['#ad356f', '#cf6b8f', '#862658', '#d9a3b5', '#b88594', '#8f6771', '#795e61', '#98827c', '#82685f', '#75584d']),
]

        # ── 颜色 → (组号, 组内索引) 的反向映射 ──
# 组号从 0 开始，组内索引从 0 开始
# 布局：2 列，从上到下从左到右
# 索引 0=左上, 1=右上, 2=左2, 3=右2, 4=左3, 5=右3, ...
COLOR_TO_GROUP = {}
for group_idx, (group_name, colors) in enumerate(COLOR_GROUPS):
    for color_idx, hex_color in enumerate(colors):
        COLOR_TO_GROUP[hex_color.lower()] = (group_idx, color_idx)

# ── 画布背景色（不需要绘制的颜色） ──
# 根据用户反馈，x, y 也被视作不可绘制的色带背景废弃色。
CANVAS_BACKGROUND_COLORS = {'#feffff', 'transparent', 'x', 'y'}

# ── 热键 ──
HOTKEY_START_RESUME = 'f5'
HOTKEY_PAUSE = 'f6'
HOTKEY_STOP = 'f7'

def hex_to_rgb(hex_str: str):
    """转换 hex 为 RGB 整数元组"""
    h = hex_str.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def get_closest_color_group(target_hex: str) -> tuple:
    """如果找不到精确匹配，返回最近的颜色 (组号, 索引)"""
    target_hex = target_hex.lower()
    if target_hex in COLOR_TO_GROUP:
        return COLOR_TO_GROUP[target_hex]
    
    try:
        tr, tg, tb = hex_to_rgb(target_hex)
    except ValueError:
        return (0, 0) # 解析失败返回默认黑色
        
    min_dist = float('inf')
    best_match = (0, 0)
    for h, group_info in COLOR_TO_GROUP.items():
        cr, cg, cb = hex_to_rgb(h)
        dist = (tr - cr)**2 + (tg - cg)**2 + (tb - cb)**2
        if dist < min_dist:
            min_dist = dist
            best_match = group_info
    
    return best_match
