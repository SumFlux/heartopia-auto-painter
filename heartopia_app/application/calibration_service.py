from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Callable, Tuple

from heartopia_app.domain.calibration import CanvasCalibration, PaletteCalibration, ToolbarCalibration

if TYPE_CHECKING:
    from heartopia_app.infrastructure.input_backend import InputBackend


class CalibrationService:
    def __init__(self, backend: InputBackend):
        self.backend = backend
        # pynput keyboard listener for Enter key detection during calibration
        self._enter_event = threading.Event()
        self._key_listener = None

    def _get_mouse_position(self) -> Tuple[int, int]:
        return self.backend.get_position()

    def _wait_for_enter(self, timeout: float = 60.0) -> bool:
        """Block until user presses Enter. Returns True if Enter was pressed, False on timeout."""
        self._enter_event.clear()

        from pynput.keyboard import Key, Listener

        def on_press(key):
            if key == Key.enter:
                self._enter_event.set()
                return False  # stop listener

        listener = Listener(on_press=on_press)
        listener.start()
        result = self._enter_event.wait(timeout=timeout)
        listener.stop()
        return result

    def calibrate_canvas_manual(
        self,
        grid_w: int,
        grid_h: int,
        on_log: Callable[[str], None],
        on_done: Callable[[CanvasCalibration], None],
        on_error: Callable[[str], None],
    ) -> None:
        """4-corner manual canvas calibration in a daemon thread.

        User moves mouse to each corner and presses Enter:
        1. Top-left (0,0)
        2. Top-right (W-1, 0)
        3. Bottom-left (0, H-1)
        4. Bottom-right (W-1, H-1)
        """
        def _worker():
            try:
                corners = ['左上角', '右上角', '左下角', '右下角']
                positions = []

                for i, name in enumerate(corners):
                    on_log(f"[{i+1}/4] 请将鼠标移到画布{name}，然后按 Enter ...")
                    if not self._wait_for_enter(timeout=120.0):
                        on_error(f"等待超时（{name}）")
                        return
                    pos = self._get_mouse_position()
                    positions.append(pos)
                    on_log(f"  ✓ {name}: ({pos[0]}, {pos[1]})")

                top_left, top_right, bottom_left, bottom_right = positions

                canvas = CanvasCalibration()
                canvas.calibrate(
                    grid_width=grid_w,
                    grid_height=grid_h,
                    top_left=top_left,
                    bottom_right=bottom_right,
                    top_right=top_right,
                    bottom_left=bottom_left,
                )

                on_log(f"[OK] 画布标定完成: {grid_w}x{grid_h}")
                on_done(canvas)

            except Exception as e:
                on_error(f"画布标定出错: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def calibrate_canvas_auto_detect(
        self,
        grid_w: int,
        grid_h: int,
        on_log: Callable[[str], None],
        on_done: Callable[[CanvasCalibration], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Auto-detect canvas via red markers in daemon thread."""
        def _worker():
            try:
                from heartopia_app.infrastructure.window_backend import (
                    find_game_window, get_window_rect, capture_window,
                )

                on_log("[自动检测] 查找游戏窗口...")
                hwnd = find_game_window()
                if hwnd is None:
                    on_error("未找到游戏窗口，请确保心动小镇已运行")
                    return

                rect = get_window_rect(hwnd)
                if rect is None:
                    on_error("无法获取窗口位置")
                    return

                window_offset = (rect[0], rect[1])
                on_log(f"  窗口位置: ({rect[0]}, {rect[1]})")

                on_log("[自动检测] 截取窗口...")
                screenshot = capture_window(hwnd)
                if screenshot is None:
                    on_error("截图失败")
                    return

                on_log("[自动检测] 搜索红色标记点...")
                from heartopia_app.domain.paint_algorithms import detect_canvas_markers
                top_left, top_right, bottom_left, bottom_right = detect_canvas_markers(
                    screenshot, window_offset, on_log=on_log
                )

                canvas = CanvasCalibration()
                canvas.calibrate(
                    grid_width=grid_w,
                    grid_height=grid_h,
                    top_left=top_left,
                    bottom_right=bottom_right,
                    top_right=top_right,
                    bottom_left=bottom_left,
                )

                on_log(f"[OK] 自动检测完成: 左上{top_left} 右下{bottom_right}")
                on_done(canvas)

            except Exception as e:
                on_error(f"自动检测出错: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def calibrate_palette(
        self,
        on_log: Callable[[str], None],
        on_done: Callable[[PaletteCalibration], None],
        on_error: Callable[[str], None],
    ) -> None:
        """4-point palette calibration in a daemon thread.

        User marks: left_tab, right_tab, blocks_top_left, blocks_bottom_right.
        """
        def _worker():
            try:
                points = [
                    ('标签最左侧', 'left_tab'),
                    ('标签最右侧', 'right_tab'),
                    ('色块区域左上角第一格中心', 'blocks_top_left'),
                    ('色块区域右下角最后一格中心', 'blocks_bottom_right'),
                ]
                positions = {}

                for i, (name, key) in enumerate(points):
                    on_log(f"[{i+1}/4] 请将鼠标移到{name}，然后按 Enter ...")
                    if not self._wait_for_enter(timeout=120.0):
                        on_error(f"等待超时（{name}）")
                        return
                    pos = self._get_mouse_position()
                    positions[key] = pos
                    on_log(f"  ✓ {name}: ({pos[0]}, {pos[1]})")

                palette = PaletteCalibration()
                palette.calibrate(
                    left_tab=positions['left_tab'],
                    right_tab=positions['right_tab'],
                    blocks_top_left=positions['blocks_top_left'],
                    blocks_bottom_right=positions['blocks_bottom_right'],
                )

                on_log(f"[OK] 调色板标定完成（{len(palette.color_blocks)} 个色块已计算）")
                on_done(palette)

            except Exception as e:
                on_error(f"调色板标定出错: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def calibrate_toolbar(
        self,
        on_log: Callable[[str], None],
        on_done: Callable[[ToolbarCalibration], None],
        on_error: Callable[[str], None],
    ) -> None:
        """2-point toolbar calibration in a daemon thread."""
        def _worker():
            try:
                tools = [('画笔工具', 'brush'), ('油漆桶工具', 'bucket')]
                positions = {}

                for i, (name, key) in enumerate(tools):
                    on_log(f"[{i+1}/2] 请将鼠标移到{name}，然后按 Enter ...")
                    if not self._wait_for_enter(timeout=120.0):
                        on_error(f"等待超时（{name}）")
                        return
                    pos = self._get_mouse_position()
                    positions[key] = pos
                    on_log(f"  ✓ {name}: ({pos[0]}, {pos[1]})")

                toolbar = ToolbarCalibration(
                    brush=positions['brush'],
                    bucket=positions['bucket'],
                )

                on_log("[OK] 工具栏标定完成")
                on_done(toolbar)

            except Exception as e:
                on_error(f"工具栏标定出错: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def test_border(
        self,
        canvas: CanvasCalibration,
        palette: PaletteCalibration,
        on_log: Callable[[str], None],
        on_done: Callable[[], None],
        stop_event: threading.Event,
    ) -> None:
        """Draw a test border around the canvas (black-only).

        Uses palette navigation to select black color, then draws all border points sequentially.
        """
        def _worker():
            try:
                W = canvas.grid_width
                H = canvas.grid_height

                from heartopia_app.domain.paint_algorithms import build_border_points
                border_points = build_border_points(W, H)
                total = len(border_points)

                on_log(f"[测试标定] 边框共 {total} 个点，黑色通刷...")
                on_log("  请在 3 秒内切换到游戏窗口...（F7 可中断）")

                # Interruptible 3s wait
                for _ in range(30):
                    if stop_event.is_set():
                        on_log("[测试标定] 已中止")
                        return
                    time.sleep(0.1)

                # Reset palette to group 0
                if palette.left_tab:
                    for _ in range(13):
                        self.backend.click(palette.left_tab[0], palette.left_tab[1])
                        time.sleep(0.1)
                    time.sleep(0.5)

                # Select black (group 0, color 0)
                if 0 in palette.color_blocks:
                    bx, by = palette.color_blocks[0]
                    self.backend.click(bx, by)
                    time.sleep(0.35)

                drawn = 0
                for px, py in border_points:
                    if stop_event.is_set():
                        on_log("[测试标定] 已中止")
                        return
                    screen_x, screen_y = canvas.get_screen_pos(px, py)
                    self.backend.click(screen_x, screen_y, press_duration=0.015)
                    drawn += 1
                    time.sleep(0.015)

                on_log(f"[测试标定] 完成！共绘制 {drawn} 个点")
                on_log("  请检查游戏中边框是否完整覆盖画布四周")

            except Exception as e:
                on_log(f"[测试标定] 出错: {e}")
            finally:
                on_done()

        threading.Thread(target=_worker, daemon=True).start()
