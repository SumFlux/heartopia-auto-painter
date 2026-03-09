"""
输入后端抽象层

定义 InputBackend 接口，隔离具体的鼠标模拟实现。
"""

import time
from abc import ABC, abstractmethod
from typing import Tuple, Optional


class InputBackend(ABC):
    """鼠标输入的抽象接口"""

    @abstractmethod
    def click(self, x: int, y: int, press_duration: float = 0.015):
        ...

    @abstractmethod
    def move(self, x: int, y: int):
        ...

    @abstractmethod
    def get_position(self) -> Tuple[int, int]:
        ...


class PynputBackend(InputBackend):
    """基于 pynput 的物理鼠标模拟后端"""

    def __init__(self):
        from pynput.mouse import Controller, Button
        self._mouse = Controller()
        self._button = Button.left

    def click(self, x: int, y: int, press_duration: float = 0.015):
        self._mouse.position = (int(x), int(y))
        time.sleep(0.01)
        self._mouse.press(self._button)
        time.sleep(press_duration)
        self._mouse.release(self._button)

    def move(self, x: int, y: int):
        self._mouse.position = (int(x), int(y))

    def get_position(self) -> Tuple[int, int]:
        pos = self._mouse.position
        return (int(pos[0]), int(pos[1]))


class PostMessageBackend(InputBackend):
    """基于 Win32 PostMessage 的后台消息投递后端（实验性）"""

    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_MOUSEMOVE = 0x0200
    MK_LBUTTON = 0x0001

    def __init__(self, hwnd: int):
        import ctypes
        self._user32 = ctypes.windll.user32
        self._hwnd = hwnd
        self._last_x = 0
        self._last_y = 0

    @staticmethod
    def _make_lparam(x: int, y: int) -> int:
        return (y << 16) | (x & 0xFFFF)

    def click(self, x: int, y: int, press_duration: float = 0.015):
        lparam = self._make_lparam(x, y)
        self._user32.PostMessageW(self._hwnd, self.WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.005)
        self._user32.PostMessageW(self._hwnd, self.WM_LBUTTONDOWN, self.MK_LBUTTON, lparam)
        time.sleep(press_duration)
        self._user32.PostMessageW(self._hwnd, self.WM_LBUTTONUP, 0, lparam)
        self._last_x = x
        self._last_y = y

    def move(self, x: int, y: int):
        lparam = self._make_lparam(x, y)
        self._user32.PostMessageW(self._hwnd, self.WM_MOUSEMOVE, 0, lparam)
        self._last_x = x
        self._last_y = y

    def get_position(self) -> Tuple[int, int]:
        return (self._last_x, self._last_y)

    def test_postmessage(self) -> bool:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        if not self._user32.GetClientRect(self._hwnd, ctypes.byref(rect)):
            return False
        center_x = rect.right // 2
        center_y = rect.bottom // 2
        try:
            self.click(center_x, center_y)
            return True
        except Exception:
            return False


def create_backend(backend_type: str = 'pynput', hwnd: Optional[int] = None) -> InputBackend:
    """工厂函数：创建输入后端"""
    if backend_type == 'pynput':
        return PynputBackend()
    elif backend_type == 'postmessage':
        if hwnd is None:
            raise ValueError("PostMessage 后端需要提供窗口句柄 (hwnd)")
        return PostMessageBackend(hwnd)
    else:
        raise ValueError(f"未知的后端类型: {backend_type}")
