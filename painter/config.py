"""
心动小镇自动画画脚本 — 配置常量

从 shared.palette 导入颜色数据，本文件只保留 painter 专用的配置。
"""

import os
import sys

# 让 Python 能找到项目根目录的 shared 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从共享调色板导入（唯一数据源）
from shared.palette import (
    COLOR_GROUPS,
    FLAT_COLORS,
    COLOR_ID_MAP,
    HEX_TO_GROUP,
    PALETTE_RGB,
    CANVAS_BACKGROUND_COLORS,
    hex_to_rgb,
    find_closest_color,
    get_closest_color_group,
)

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

# ── 热键 ──
HOTKEY_START_RESUME = 'f5'
HOTKEY_PAUSE = 'f6'
HOTKEY_STOP = 'f7'

# ── 固定坐标配置文件 ──
# 存储画布/调色板/工具栏相对于游戏窗口客户区的固定偏移量
FIXED_POSITIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixed_positions.json')

# ── 油漆桶优化 ──
# 连通区域面积 >= 此阈值时使用油漆桶填充，否则逐点画
BUCKET_FILL_MIN_AREA = 30
