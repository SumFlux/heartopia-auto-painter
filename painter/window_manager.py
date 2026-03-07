"""
心动小镇自动画画脚本 — 窗口管理模块

查找游戏窗口、获取窗口信息、截图
"""

import ctypes
from ctypes import wintypes
import time
from typing import Optional, Tuple

from PIL import ImageGrab

from config import GAME_WINDOW_TITLE, GAME_WIDTH, GAME_HEIGHT


# Windows API
user32 = ctypes.windll.user32


def find_game_window() -> Optional[int]:
    """
    查找心动小镇游戏窗口句柄
    :return: 窗口句柄 (HWND)，未找到返回 None
    """
    hwnd = user32.FindWindowW(None, GAME_WINDOW_TITLE)
    if hwnd == 0:
        return None
    return hwnd


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """
    获取窗口的屏幕坐标（客户区）
    :return: (left, top, right, bottom) 或 None
    """
    rect = wintypes.RECT()
    # 获取客户区坐标（不含标题栏和边框）
    if user32.GetClientRect(hwnd, ctypes.byref(rect)):
        # 将客户区左上角转换为屏幕坐标
        point = wintypes.POINT(rect.left, rect.top)
        user32.ClientToScreen(hwnd, ctypes.byref(point))
        left = point.x
        top = point.y

        point2 = wintypes.POINT(rect.right, rect.bottom)
        user32.ClientToScreen(hwnd, ctypes.byref(point2))
        right = point2.x
        bottom = point2.y

        return (left, top, right, bottom)
    return None


def bring_to_front(hwnd: int):
    """将游戏窗口置于最前"""
    # 如果窗口最小化，先恢复
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.3)

    user32.SetForegroundWindow(hwnd)
    time.sleep(0.1)


def capture_window(hwnd: int) -> Optional['PIL.Image.Image']:
    """
    截取游戏窗口的当前画面
    :return: PIL Image 对象
    """
    rect = get_window_rect(hwnd)
    if rect is None:
        return None
    return ImageGrab.grab(bbox=rect)


def get_window_size(hwnd: int) -> Optional[Tuple[int, int]]:
    """获取窗口客户区尺寸"""
    rect = get_window_rect(hwnd)
    if rect is None:
        return None
    return (rect[2] - rect[0], rect[3] - rect[1])
