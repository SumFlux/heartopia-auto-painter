from __future__ import annotations

from pathlib import Path

APP_NAME = "Heartopia Auto Painter"
APP_DIR_NAME = "heartopia-auto-painter"
SETTINGS_FILE_NAME = "settings.json"
CALIBRATION_FILE_NAME = "calibration_profiles.json"
SESSION_FILE_NAME = "paint_session.json"

# 游戏窗口参数
GAME_WINDOW_TITLE = "心动小镇"
GAME_WIDTH = 1920
GAME_HEIGHT = 1080

# 速度预设（每次点击后的延迟，单位毫秒）
SPEED_PRESETS = {
    'fast': 20,
    'normal': 50,
    'slow': 100,
    'very_slow': 200,
}

# 油漆桶优化：连通区域面积 >= 此阈值时使用油漆桶填充
BUCKET_FILL_MIN_AREA = 30
