"""
输入后端抽象层

定义 InputBackend 接口，隔离具体的鼠标模拟实现。
"""

import time
from abc import ABC, abstractmethod
from typing import Callable, Iterable, Optional, Tuple


class InputBackend(ABC):
    """鼠标输入的抽象接口"""

    @abstractmethod
    def click(self, x: int, y: int, press_duration: float = 0.015):
        ...

    @abstractmethod
    def move(self, x: int, y: int):
        ...

    @abstractmethod
    def mouse_down(self, x: int, y: int, press_delay: float = 0.01):
        ...

    @abstractmethod
    def mouse_up(self, x: int, y: int):
        ...

    @abstractmethod
    def get_position(self) -> Tuple[int, int]:
        ...

    @staticmethod
    def _interpolate_path(points: Iterable[Tuple[int, int]]) -> list[Tuple[int, int]]:
        path = [(int(x), int(y)) for x, y in points]
        if not path:
            return []

        expanded: list[Tuple[int, int]] = [path[0]]
        for end_x, end_y in path[1:]:
            start_x, start_y = expanded[-1]
            dx = end_x - start_x
            dy = end_y - start_y
            steps = max(abs(dx), abs(dy))
            if steps == 0:
                continue
            for step in range(1, steps + 1):
                x = round(start_x + dx * step / steps)
                y = round(start_y + dy * step / steps)
                point = (x, y)
                if point != expanded[-1]:
                    expanded.append(point)
        return expanded

    def drag_path(
        self,
        points: Iterable[Tuple[int, int]],
        *,
        press_delay: float = 0.02,
        move_delay: float = 0.002,
        release_delay: float = 0.02,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        path = self._interpolate_path(points)
        if not path:
            return

        start_x, start_y = path[0]
        self.move(start_x, start_y)
        if press_delay > 0:
            time.sleep(press_delay)

        is_pressed = False
        try:
            if should_stop and should_stop():
                return
            self.mouse_down(start_x, start_y, press_delay=0.0)
            is_pressed = True
            if move_delay > 0:
                time.sleep(move_delay)
            for x, y in path[1:]:
                if should_stop and should_stop():
                    break
                self.move(x, y)
                if move_delay > 0:
                    time.sleep(move_delay)
            if release_delay > 0:
                time.sleep(release_delay)
        finally:
            if is_pressed:
                end_x, end_y = self.get_position()
                self.mouse_up(end_x, end_y)


class PynputBackend(InputBackend):
    """基于 pynput 的物理鼠标模拟后端"""

    def __init__(self):
        import ctypes
        from pynput.mouse import Controller, Button
        self._mouse = Controller()
        self._button = Button.left
        self._user32 = ctypes.windll.user32

    def click(self, x: int, y: int, press_duration: float = 0.015):
        self.mouse_down(x, y)
        time.sleep(press_duration)
        self.mouse_up(x, y)

    def move(self, x: int, y: int):
        self._mouse.position = (int(x), int(y))

    def _emit_drag_move(self, x: int, y: int):
        current_x, current_y = self.get_position()
        target_x = int(x)
        target_y = int(y)
        dx = target_x - current_x
        dy = target_y - current_y
        if dx == 0 and dy == 0:
            return
        self._user32.mouse_event(0x0001, dx, dy, 0, 0)

    def mouse_down(self, x: int, y: int, press_delay: float = 0.01):
        self._mouse.position = (int(x), int(y))
        if press_delay > 0:
            time.sleep(press_delay)
        self._mouse.press(self._button)

    def mouse_up(self, x: int, y: int):
        self._mouse.position = (int(x), int(y))
        self._mouse.release(self._button)

    def drag_path(
        self,
        points: Iterable[Tuple[int, int]],
        *,
        press_delay: float = 0.02,
        move_delay: float = 0.002,
        release_delay: float = 0.02,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        path = self._interpolate_path(points)
        if not path:
            return

        start_x, start_y = path[0]
        self.move(start_x, start_y)
        if press_delay > 0:
            time.sleep(press_delay)

        is_pressed = False
        current_x, current_y = start_x, start_y
        try:
            if should_stop and should_stop():
                return
            self.mouse_down(start_x, start_y, press_delay=0.0)
            is_pressed = True
            if move_delay > 0:
                time.sleep(move_delay)
            for x, y in path[1:]:
                if should_stop and should_stop():
                    break
                self._emit_drag_move(x, y)
                current_x, current_y = int(x), int(y)
                if move_delay > 0:
                    time.sleep(move_delay)
            if release_delay > 0:
                time.sleep(release_delay)
        finally:
            if is_pressed:
                self.mouse_up(current_x, current_y)

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
        self.move(x, y)
        time.sleep(0.005)
        self.mouse_down(x, y, press_delay=0.0)
        time.sleep(press_duration)
        self.mouse_up(x, y)

    def move(self, x: int, y: int):
        lparam = self._make_lparam(x, y)
        self._user32.PostMessageW(self._hwnd, self.WM_MOUSEMOVE, 0, lparam)
        self._last_x = x
        self._last_y = y

    def mouse_down(self, x: int, y: int, press_delay: float = 0.01):
        self.move(x, y)
        if press_delay > 0:
            time.sleep(press_delay)
        lparam = self._make_lparam(x, y)
        self._user32.PostMessageW(self._hwnd, self.WM_LBUTTONDOWN, self.MK_LBUTTON, lparam)
        self._last_x = x
        self._last_y = y

    def mouse_up(self, x: int, y: int):
        lparam = self._make_lparam(x, y)
        self._user32.PostMessageW(self._hwnd, self.WM_MOUSEMOVE, self.MK_LBUTTON, lparam)
        self._user32.PostMessageW(self._hwnd, self.WM_LBUTTONUP, 0, lparam)
        self._last_x = x
        self._last_y = y

    def drag_path(
        self,
        points: Iterable[Tuple[int, int]],
        *,
        press_delay: float = 0.02,
        move_delay: float = 0.002,
        release_delay: float = 0.02,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        path = self._interpolate_path(points)
        if not path:
            return

        start_x, start_y = path[0]
        self.move(start_x, start_y)
        if press_delay > 0:
            time.sleep(press_delay)

        is_pressed = False
        current_x, current_y = start_x, start_y
        try:
            if should_stop and should_stop():
                return
            self.mouse_down(start_x, start_y, press_delay=0.0)
            is_pressed = True
            if move_delay > 0:
                time.sleep(move_delay)
            for x, y in path[1:]:
                if should_stop and should_stop():
                    break
                lparam = self._make_lparam(x, y)
                self._user32.PostMessageW(self._hwnd, self.WM_MOUSEMOVE, self.MK_LBUTTON, lparam)
                self._last_x = x
                self._last_y = y
                current_x, current_y = int(x), int(y)
                if move_delay > 0:
                    time.sleep(move_delay)
            if release_delay > 0:
                time.sleep(release_delay)
        finally:
            if is_pressed:
                self.mouse_up(current_x, current_y)

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
