"""
心动小镇自动画画脚本 — 绘画引擎模块

加载 JSON 数据，按颜色分组，蛇形遍历坐标并调用鼠标自动化
支持暂停、恢复与停止
"""

import threading
import time
from typing import List, Dict, Tuple
import pyautogui
from mouse_input import click_at
from config import COLOR_TO_GROUP, CANVAS_BACKGROUND_COLORS, SPEED_PRESETS, get_closest_color_group
from canvas_locator import CanvasLocator
from palette_navigator import PaletteNavigator


class PaintEngine:
    """绘画引擎，控制整个画画流程"""

    def __init__(self, locator: CanvasLocator, navigator: PaletteNavigator):
        self.locator = locator
        self.navigator = navigator

        # 状态控制
        self.is_running = False
        self.is_paused = False
        self._stop_event = threading.Event()

        # 绘画数据
        self.pixels: List[List[str]] = []
        # 按颜色分组的坐标: { hex_color: [(px, py), ...] }
        self.color_groups: Dict[str, List[Tuple[int, int]]] = {}

        # 进度跟踪
        self.total_pixels = 0
        self.drawn_pixels = 0
        self.current_color = ""

        # 配置
        self.delay_ms = SPEED_PRESETS['normal']

        # 回调函数（供 GUI 更新进度）
        self.on_progress = None
        self.on_color_change = None
        self.on_finished = None
        self.on_error = None

    def load_pixels(self, pixels: list):
        """加载像素列表并预处理
        期望的 pixels 元素结构：{'x': int, 'y': int, 'color': string, 'colorId': 'group-index' }
        旧版本没有 colorId 时会提取 fallbacks。
        """
        self.pixels = pixels
        self.color_groups = {} # 格式 { "colorId" 或者 "hex_color": [(px, py)] }
        self.total_pixels = 0
        self.drawn_pixels = 0

        # 分离出背景色和透明色
        for p in pixels:
            px = p.get('x', 0)
            py = p.get('y', 0)
            hex_color = p.get('color', '').lower()
            color_id = p.get('colorId') # 类似 "0-3" (第1组第4个色)
            
            # 如果是明确背景色则跳过
            if hex_color in CANVAS_BACKGROUND_COLORS or hex_color == 'transparent':
                continue
                
            # 分组依据：有自带的 ID 则必须用内置精确 ID，否则用降级获取的组别自己拼 ID
            if color_id:
                group_key = color_id
            else:
                group_idx, color_idx = get_closest_color_group(hex_color)
                group_key = f"{group_idx}-{color_idx}"

            if group_key not in self.color_groups:
                self.color_groups[group_key] = []
            
            self.color_groups[group_key].append((px, py))
            self.total_pixels += 1

        # 对每个颜色的坐标进行排序，实现“蛇形遍历”以减少鼠标移动
        # 偶数行从左往右，奇数行从右往左
        for group_key, coords in self.color_groups.items():
            coords.sort(key=lambda c: (c[1], c[0] if c[1] % 2 == 0 else -c[0]))

    def set_speed(self, preset_name: str):
        """设置绘画速度（点击间隔）"""
        if preset_name in SPEED_PRESETS:
            self.delay_ms = SPEED_PRESETS[preset_name]

    def pause(self):
        """暂停"""
        if self.is_running and not self.is_paused:
            self.is_paused = True

    def resume(self):
        """恢复"""
        if self.is_running and self.is_paused:
            self.is_paused = False

    def stop(self):
        """停止"""
        self._stop_event.set()
        self.is_running = False
        self.is_paused = False

    def start(self):
        """在独立线程中开始绘画"""
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
        self.drawn_pixels = 0

        # 启动工作线程
        worker = threading.Thread(target=self._paint_loop, daemon=True)
        worker.start()

    def _wait_if_paused(self):
        """如果暂停则阻塞等待"""
        while self.is_paused and not self._stop_event.is_set():
            time.sleep(0.1)

    def _paint_loop(self):
        """主绘制循环（在工作线程中运行）"""
        try:
            # 1. 确保游戏窗口处于前台
            # (在此省略，应由调用者或 auto_painter 控制)
            time.sleep(1)  # 给用户切窗口的缓冲

            # 2. 将调色板复位到第 1 组
            self.navigator.reset_group()

            # 3. 按颜色组顺序排序需要画的颜色，减少翻页次数
            # 从 group_key（格式 "组号-索引"） 提取组号用来排序
            def sort_key(g_key):
                if '-' in g_key:
                    return int(g_key.split('-')[0])
                return 999 

            sorted_group_keys = sorted(self.color_groups.keys(), key=sort_key)

            delay_sec = self.delay_ms / 1000.0

            # 4. 开始按颜色分批绘制
            for color_idx, group_key in enumerate(sorted_group_keys):
                self._wait_if_paused()
                if self._stop_event.is_set():
                    break

                self.current_color = group_key
                drawn_for_this_color = len(self.color_groups[group_key])
                if self.on_color_change:
                    self.on_color_change(group_key, color_idx + 1, len(sorted_group_keys))

                # --- a. 选色 ---
                if '-' in group_key:
                    g_idx_str, c_idx_str = group_key.split('-')
                    self.navigator.select_color(int(g_idx_str), int(c_idx_str))
                else:
                    print(f"警告：未知的颜色 ID {group_key}，跳过选择调色板")

                time.sleep(0.15)  # 选完颜色后稍微停留

                # --- b. 逐点绘制 ---
                for coords in self.color_groups[group_key]:
                    self._wait_if_paused()
                    if self._stop_event.is_set():
                        break

                    # 坐标转换
                    px, py = coords
                    screen_x, screen_y = self.locator.get_screen_pos(px, py)

                    # 移动并使用硬件级模拟点击
                    click_at(screen_x, screen_y, delay=0.015)

                    # 更新进度
                    self.drawn_pixels += 1
                    if self.on_progress:
                        self.on_progress(self.drawn_pixels, self.total_pixels)

                    # 间隔延时
                    time.sleep(delay_sec)

        except Exception as e:
            if self.on_error:
                self.on_error(f"绘画过程中出错: {e}")
        finally:
            self.is_running = False
            if self.on_finished and not self._stop_event.is_set():
                self.on_finished()
