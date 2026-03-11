"""
窗口管理模块 — 查找游戏窗口、获取窗口信息、截图
"""

import ctypes
from ctypes import wintypes
import time
from typing import Optional, Tuple

from PIL import ImageGrab

from .constants import GAME_WINDOW_TITLE, GAME_WIDTH, GAME_HEIGHT


user32 = ctypes.windll.user32


def find_game_window() -> Optional[int]:
    """查找心动小镇游戏窗口句柄"""
    hwnd = user32.FindWindowW(None, GAME_WINDOW_TITLE)
    if hwnd == 0:
        return None
    return hwnd


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """获取窗口的屏幕坐标（客户区）"""
    rect = wintypes.RECT()
    if user32.GetClientRect(hwnd, ctypes.byref(rect)):
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
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.3)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.1)


def capture_window(hwnd: int) -> Optional['PIL.Image.Image']:
    """截取游戏窗口的当前画面"""
    rect = get_window_rect(hwnd)
    if rect is None:
        return None
    return ImageGrab.grab(bbox=rect)


def capture_window_with_rect(hwnd: int) -> Optional[tuple['PIL.Image.Image', Tuple[int, int, int, int]]]:
    """截取游戏窗口并返回截图及客户区矩形。"""
    rect = get_window_rect(hwnd)
    if rect is None:
        return None
    return ImageGrab.grab(bbox=rect), rect


def get_window_size(hwnd: int) -> Optional[Tuple[int, int]]:
    """获取窗口客户区尺寸"""
    rect = get_window_rect(hwnd)
    if rect is None:
        return None
    return (rect[2] - rect[0], rect[3] - rect[1])
