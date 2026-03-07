"""
心动小镇自动画画脚本 — 绘画引擎模块

加载 JSON 数据，按颜色分组，蛇形遍历坐标并调用 InputBackend 自动化。
支持暂停、恢复、停止与断点续画。
"""

import os
import sys
import json
import threading
import time
from typing import List, Dict, Tuple, Optional, Callable

# 确保能导入 shared
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.palette import CANVAS_BACKGROUND_COLORS, get_closest_color_group
from shared.pixel_data import PixelData
from mouse_input import InputBackend
from canvas_locator import CanvasLocator
from palette_navigator import PaletteNavigator
from config import SPEED_PRESETS


class PaintEngine:
    """绘画引擎，控制整个画画流程"""

    # 断点续画进度文件
    PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'paint_progress.json')

    def __init__(self, locator: CanvasLocator, navigator: PaletteNavigator, backend: InputBackend):
        self.locator = locator
        self.navigator = navigator
        self.backend = backend

        # 状态控制
        self.is_running = False
        self.is_paused = False
        self._stop_event = threading.Event()

        # 绘画数据
        self.pixel_data: Optional[PixelData] = None
        # 按颜色分组的坐标: { color_id: [(px, py), ...] }
        self.color_groups: Dict[str, List[Tuple[int, int]]] = {}
        # 排序后的组 key 列表（按组号排序以减少翻页）
        self.sorted_group_keys: List[str] = []

        # 进度跟踪
        self.total_pixels = 0
        self.drawn_pixels = 0
        self.current_color = ""
        # 断点续画：记录已完成的 group_key 和当前 group 内已画的数量
        self._completed_groups: List[str] = []
        self._current_group_offset: int = 0

        # 配置
        self.delay_ms = SPEED_PRESETS['normal']

        # 回调函数（供 GUI 更新进度）
        self.on_progress: Optional[Callable[[int, int], None]] = None
        self.on_color_change: Optional[Callable[[str, int, int], None]] = None
        self.on_finished: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    def load_pixel_data(self, pixel_data: PixelData):
        """
        从 PixelData 对象加载像素数据并预处理

        :param pixel_data: 通过 shared.pixel_data.PixelData.from_json_file() 加载的数据
        """
        self.pixel_data = pixel_data
        self.color_groups = {}
        self.total_pixels = 0
        self.drawn_pixels = 0
        self._completed_groups = []
        self._current_group_offset = 0

        for p in pixel_data.pixels:
            px = p.get('x', 0)
            py = p.get('y', 0)
            hex_color = p.get('color', '').lower()
            color_id = p.get('colorId')

            # 跳过背景色
            if hex_color in CANVAS_BACKGROUND_COLORS or hex_color == 'transparent':
                continue

            # 确定分组 key
            if color_id:
                group_key = color_id
            else:
                g_idx, c_idx = get_closest_color_group(hex_color)
                group_key = f"{g_idx}-{c_idx}"

            if group_key not in self.color_groups:
                self.color_groups[group_key] = []

            self.color_groups[group_key].append((px, py))
            self.total_pixels += 1

        # 蛇形排序：偶数行从左往右，奇数行从右往左
        for coords in self.color_groups.values():
            coords.sort(key=lambda c: (c[1], c[0] if c[1] % 2 == 0 else -c[0]))

        # 按组号排序以减少翻页次数
        def sort_key(g_key):
            if '-' in g_key:
                return int(g_key.split('-')[0])
            return 999

        self.sorted_group_keys = sorted(self.color_groups.keys(), key=sort_key)

    # 兼容旧接口
    def load_pixels(self, pixels: list):
        """兼容旧的 pixels 列表格式（内部转换为 PixelData）"""
        pd = PixelData()
        pd.pixels = pixels
        pd.grid_width = max((p.get('x', 0) for p in pixels), default=0) + 1
        pd.grid_height = max((p.get('y', 0) for p in pixels), default=0) + 1
        pd.total_pixels = len(pixels)
        self.load_pixel_data(pd)

    def set_speed(self, preset_name: str):
        """设置绘画速度"""
        if preset_name in SPEED_PRESETS:
            self.delay_ms = SPEED_PRESETS[preset_name]

    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True

    def resume(self):
        if self.is_running and self.is_paused:
            self.is_paused = False

    def stop(self):
        self._stop_event.set()
        self.is_running = False
        self.is_paused = False

    def start(self, resume_from_checkpoint: bool = False):
        """
        在独立线程中开始绘画

        :param resume_from_checkpoint: 是否从上次中断处继续
        """
        if self.is_running:
            return

        if not self.locator.calibrated:
            if self.on_error:
                self.on_error("画布尚未标定！")
            return

        if not self.navigator.calibrated:
            if self.on_error:
                self.on_error("调色板尚未标定！")
            return

        if self.total_pixels == 0:
            if self.on_error:
                self.on_error("像素数据为空！")
            return

        self.is_running = True
        self.is_paused = False
        self._stop_event.clear()

        if resume_from_checkpoint:
            self._load_progress()
        else:
            self.drawn_pixels = 0
            self._completed_groups = []
            self._current_group_offset = 0

        worker = threading.Thread(target=self._paint_loop, daemon=True)
        worker.start()

    def _wait_if_paused(self):
        while self.is_paused and not self._stop_event.is_set():
            time.sleep(0.1)

    def _paint_loop(self):
        """主绘制循环（在工作线程中运行）"""
        try:
            time.sleep(1)  # 给用户切窗口的缓冲

            # 复位调色板到第 0 组
            self.navigator.reset_group()

            delay_sec = self.delay_ms / 1000.0

            for color_idx, group_key in enumerate(self.sorted_group_keys):
                # 断点续画：跳过已完成的组
                if group_key in self._completed_groups:
                    continue

                self._wait_if_paused()
                if self._stop_event.is_set():
                    break

                self.current_color = group_key
                if self.on_color_change:
                    self.on_color_change(group_key, color_idx + 1, len(self.sorted_group_keys))

                # 选色
                if '-' in group_key:
                    g_idx, c_idx = group_key.split('-')
                    self.navigator.select_color(int(g_idx), int(c_idx))
                else:
                    print(f"Warning: unknown color ID {group_key}, skipping")

                time.sleep(0.15)

                # 逐点绘制
                coords_list = self.color_groups[group_key]
                start_offset = self._current_group_offset if group_key not in self._completed_groups else 0
                self._current_group_offset = 0  # 只有第一个未完成组需要 offset

                for i in range(start_offset, len(coords_list)):
                    self._wait_if_paused()
                    if self._stop_event.is_set():
                        # 保存断点
                        self._current_group_offset = i
                        self._save_progress()
                        break

                    px, py = coords_list[i]
                    screen_x, screen_y = self.locator.get_screen_pos(px, py)
                    self.backend.click(screen_x, screen_y, press_duration=0.015)

                    self.drawn_pixels += 1
                    if self.on_progress:
                        self.on_progress(self.drawn_pixels, self.total_pixels)

                    time.sleep(delay_sec)
                else:
                    # for 正常结束（没有 break），标记此组完成
                    self._completed_groups.append(group_key)
                    continue

                # 如果是 break 出来的（stop），外层也 break
                break

        except Exception as e:
            if self.on_error:
                self.on_error(f"绘画过程中出错: {e}")
        finally:
            self.is_running = False
            if not self._stop_event.is_set() and self.on_finished:
                self.on_finished()
                # 完成后清理进度文件
                self._clear_progress()

    # ===== 断点续画：进度持久化 =====

    def _save_progress(self):
        """保存当前绘画进度到文件"""
        data = {
            'drawn_pixels': self.drawn_pixels,
            'completed_groups': self._completed_groups,
            'current_group_offset': self._current_group_offset,
            'current_color': self.current_color,
        }
        try:
            with open(self.PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_progress(self):
        """从文件恢复绘画进度"""
        if not os.path.exists(self.PROGRESS_FILE):
            return

        try:
            with open(self.PROGRESS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.drawn_pixels = data.get('drawn_pixels', 0)
            self._completed_groups = data.get('completed_groups', [])
            self._current_group_offset = data.get('current_group_offset', 0)
        except Exception:
            self.drawn_pixels = 0
            self._completed_groups = []
            self._current_group_offset = 0

    def _clear_progress(self):
        """清理进度文件"""
        try:
            if os.path.exists(self.PROGRESS_FILE):
                os.remove(self.PROGRESS_FILE)
        except Exception:
            pass

    def has_saved_progress(self) -> bool:
        """检查是否有未完成的绘画进度"""
        return os.path.exists(self.PROGRESS_FILE)
