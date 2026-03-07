"""
心动小镇自动画画脚本 — 输入后端抽象层

定义 InputBackend 接口，隔离具体的鼠标模拟实现。
PaintEngine / PaletteNavigator 只依赖此接口，不关心底层是 pynput 还是 PostMessage。

可用后端：
- PynputBackend: 物理鼠标移动 + 点击（屏幕绝对坐标），当前默认方案
- PostMessageBackend: Win32 消息投递（窗口客户区相对坐标），实验性方案
"""

import time
from abc import ABC, abstractmethod
from typing import Tuple, Optional


class InputBackend(ABC):
    """鼠标输入的抽象接口"""

    @abstractmethod
    def click(self, x: int, y: int, press_duration: float = 0.015):
        """
        在指定坐标执行一次点击

        :param x: x 坐标
        :param y: y 坐标
        :param press_duration: 按住时长（秒）
        """
        ...

    @abstractmethod
    def move(self, x: int, y: int):
        """移动到指定坐标（不点击）"""
        ...

    @abstractmethod
    def get_position(self) -> Tuple[int, int]:
        """获取当前鼠标位置"""
        ...


class PynputBackend(InputBackend):
    """
    基于 pynput 的物理鼠标模拟后端

    使用屏幕绝对坐标，通过物理移动鼠标实现点击。
    需要配合 SetProcessDpiAwareness(1) 使用以确保坐标准确。

    优点：游戏 100% 识别（硬件级输入）
    缺点：画画期间鼠标被占用，多显示器下可能偏移
    """

    def __init__(self):
        from pynput.mouse import Controller, Button
        self._mouse = Controller()
        self._button = Button.left

    def click(self, x: int, y: int, press_duration: float = 0.015):
        self._mouse.position = (int(x), int(y))
        time.sleep(0.01)  # 给系统坐标刷新留时间
        self._mouse.press(self._button)
        time.sleep(press_duration)
        self._mouse.release(self._button)

    def move(self, x: int, y: int):
        self._mouse.position = (int(x), int(y))

    def get_position(self) -> Tuple[int, int]:
        pos = self._mouse.position
        return (int(pos[0]), int(pos[1]))


class PostMessageBackend(InputBackend):
    """
    基于 Win32 PostMessage 的后台消息投递后端（实验性）

    使用窗口客户区相对坐标，不移动物理鼠标。
    需要传入游戏窗口句柄 (hwnd)。

    优点：不占用鼠标、不受 DPI/多显示器影响
    缺点：某些游戏（尤其是 Unity）可能不响应 PostMessage 的鼠标消息

    WARNING: 此方案对心动小镇（Unity引擎）的兼容性尚未验证！
    请用户先用 test_postmessage() 方法测试游戏是否响应。
    """

    # Windows 消息常量
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_MOUSEMOVE = 0x0200
    MK_LBUTTON = 0x0001

    def __init__(self, hwnd: int):
        """
        :param hwnd: 目标游戏窗口句柄
        """
        import ctypes
        self._user32 = ctypes.windll.user32
        self._hwnd = hwnd
        self._last_x = 0
        self._last_y = 0

    @staticmethod
    def _make_lparam(x: int, y: int) -> int:
        """将 (x, y) 打包为 LPARAM (低16位=x, 高16位=y)"""
        return (y << 16) | (x & 0xFFFF)

    def click(self, x: int, y: int, press_duration: float = 0.015):
        lparam = self._make_lparam(x, y)

        # 先发送鼠标移动
        self._user32.PostMessageW(self._hwnd, self.WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.005)

        # 按下
        self._user32.PostMessageW(self._hwnd, self.WM_LBUTTONDOWN, self.MK_LBUTTON, lparam)
        time.sleep(press_duration)

        # 松开
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
        """
        测试 PostMessage 是否对目标窗口有效。
        在窗口中心位置发送一次点击。

        :return: True 表示消息发送成功（不代表游戏一定响应）
        """
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
    """
    工厂函数：创建输入后端

    :param backend_type: 'pynput' 或 'postmessage'
    :param hwnd: 游戏窗口句柄（仅 postmessage 需要）
    :return: InputBackend 实例
    """
    if backend_type == 'pynput':
        return PynputBackend()
    elif backend_type == 'postmessage':
        if hwnd is None:
            raise ValueError("PostMessage 后端需要提供窗口句柄 (hwnd)")
        return PostMessageBackend(hwnd)
    else:
        raise ValueError(f"未知的后端类型: {backend_type}")
