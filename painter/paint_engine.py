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

from collections import deque

from shared.palette import CANVAS_BACKGROUND_COLORS, get_closest_color_group
from shared.pixel_data import PixelData
from mouse_input import InputBackend
from canvas_locator import CanvasLocator
from palette_navigator import PaletteNavigator
from config import SPEED_PRESETS, BUCKET_FILL_MIN_AREA


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

        # 油漆桶优化
        self.use_bucket_fill = False
        self.bucket_tool_pos: Optional[Tuple[int, int]] = None  # 油漆桶工具屏幕坐标
        self.brush_tool_pos: Optional[Tuple[int, int]] = None   # 画笔工具屏幕坐标
        # 像素颜色映射 (x, y) -> color_id，用于连通分析
        self._pixel_color_map: Dict[Tuple[int, int], str] = {}
        self._grid_width: int = 0
        self._grid_height: int = 0

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
        self._pixel_color_map = {}
        self._grid_width = pixel_data.grid_width
        self._grid_height = pixel_data.grid_height

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
            self._pixel_color_map[(px, py)] = group_key
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

    def set_bucket_fill(self, enabled: bool, brush_pos: Optional[Tuple[int, int]] = None,
                        bucket_pos: Optional[Tuple[int, int]] = None):
        """
        启用/禁用油漆桶填充优化

        :param enabled: 是否启用
        :param brush_pos: 画笔工具屏幕坐标
        :param bucket_pos: 油漆桶工具屏幕坐标
        """
        self.use_bucket_fill = enabled
        self.brush_tool_pos = brush_pos
        self.bucket_tool_pos = bucket_pos

    def _find_connected_components(self, group_key: str, coords: List[Tuple[int, int]]) -> List[List[Tuple[int, int]]]:
        """
        对同色像素进行连通区域分析（4-连通）

        :param group_key: 颜色 ID
        :param coords: 该颜色所有像素坐标
        :return: 连通区域列表，每个区域是坐标列表
        """
        coord_set = set(coords)
        visited = set()
        components = []

        for start in coords:
            if start in visited:
                continue

            # BFS 洪水填充
            component = []
            queue = deque([start])
            visited.add(start)

            while queue:
                x, y = queue.popleft()
                component.append((x, y))

                for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                    if (nx, ny) in coord_set and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny))

            components.append(component)

        return components

    def _classify_boundary_interior(self, component: List[Tuple[int, int]], group_key: str
                                    ) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """
        将连通区域的像素分为边界像素和内部像素

        边界像素：4-邻域中存在不同颜色的像素（或位于画布边缘）
        内部像素：4-邻域全部是同色

        :return: (boundary_pixels, interior_pixels)
        """
        comp_set = set(component)
        boundary = []
        interior = []

        for x, y in component:
            is_boundary = False
            for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                # 画布边缘算边界
                if nx < 0 or ny < 0 or nx >= self._grid_width or ny >= self._grid_height:
                    is_boundary = True
                    break
                # 邻居不在本区域
                if (nx, ny) not in comp_set:
                    # 邻居是不同颜色（或背景）
                    neighbor_color = self._pixel_color_map.get((nx, ny))
                    if neighbor_color != group_key:
                        is_boundary = True
                        break

            if is_boundary:
                boundary.append((x, y))
            else:
                interior.append((x, y))

        # 蛇形排序
        boundary.sort(key=lambda c: (c[1], c[0] if c[1] % 2 == 0 else -c[0]))
        interior.sort(key=lambda c: (c[1], c[0] if c[1] % 2 == 0 else -c[0]))

        return boundary, interior

    def _switch_tool(self, tool: str):
        """
        切换到画笔或油漆桶工具

        :param tool: 'brush' 或 'bucket'
        """
        if tool == 'brush' and self.brush_tool_pos:
            self.backend.click(self.brush_tool_pos[0], self.brush_tool_pos[1], press_duration=0.02)
            time.sleep(0.15)
        elif tool == 'bucket' and self.bucket_tool_pos:
            self.backend.click(self.bucket_tool_pos[0], self.bucket_tool_pos[1], press_duration=0.02)
            time.sleep(0.15)

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

            # 判断是否可用油漆桶模式
            bucket_mode = (self.use_bucket_fill and
                           self.brush_tool_pos is not None and
                           self.bucket_tool_pos is not None)

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

                coords_list = self.color_groups[group_key]
                start_offset = self._current_group_offset if group_key not in self._completed_groups else 0
                self._current_group_offset = 0  # 只有第一个未完成组需要 offset

                if bucket_mode and start_offset == 0:
                    # 油漆桶优化模式：按连通区域处理
                    stopped = self._paint_group_with_bucket(group_key, coords_list, delay_sec)
                    if stopped:
                        break
                else:
                    # 传统逐点模式（含断点续画偏移）
                    stopped = self._paint_group_sequential(group_key, coords_list, start_offset, delay_sec)
                    if stopped:
                        break

                # 正常完成该组
                self._completed_groups.append(group_key)

        except Exception as e:
            if self.on_error:
                self.on_error(f"绘画过程中出错: {e}")
        finally:
            self.is_running = False
            if not self._stop_event.is_set() and self.on_finished:
                self.on_finished()
                # 完成后清理进度文件
                self._clear_progress()

    def _paint_group_sequential(self, group_key: str, coords_list: List[Tuple[int, int]],
                                start_offset: int, delay_sec: float) -> bool:
        """
        逐点绘制一组颜色（传统模式）

        :return: True 表示被中断（stop），False 表示正常完成
        """
        for i in range(start_offset, len(coords_list)):
            self._wait_if_paused()
            if self._stop_event.is_set():
                self._current_group_offset = i
                self._save_progress()
                return True

            px, py = coords_list[i]
            screen_x, screen_y = self.locator.get_screen_pos(px, py)
            self.backend.click(screen_x, screen_y, press_duration=0.015)

            self.drawn_pixels += 1
            if self.on_progress:
                self.on_progress(self.drawn_pixels, self.total_pixels)

            time.sleep(delay_sec)

        return False

    def _paint_group_with_bucket(self, group_key: str, coords_list: List[Tuple[int, int]],
                                 delay_sec: float) -> bool:
        """
        使用油漆桶优化绘制一组颜色

        策略：
        1. 对同色像素做连通区域分析
        2. 小区域（< BUCKET_FILL_MIN_AREA）→ 逐点画
        3. 大区域 → 先画笔画边界，再油漆桶填内部

        :return: True 表示被中断，False 表示正常完成
        """
        components = self._find_connected_components(group_key, coords_list)

        # 确保当前是画笔工具
        current_tool = 'brush'
        self._switch_tool('brush')

        for component in components:
            if self._stop_event.is_set():
                self._save_progress()
                return True

            if len(component) < BUCKET_FILL_MIN_AREA:
                # 小区域：逐点画
                if current_tool != 'brush':
                    self._switch_tool('brush')
                    current_tool = 'brush'

                # 蛇形排序
                sorted_comp = sorted(component, key=lambda c: (c[1], c[0] if c[1] % 2 == 0 else -c[0]))
                for px, py in sorted_comp:
                    self._wait_if_paused()
                    if self._stop_event.is_set():
                        self._save_progress()
                        return True

                    screen_x, screen_y = self.locator.get_screen_pos(px, py)
                    self.backend.click(screen_x, screen_y, press_duration=0.015)
                    self.drawn_pixels += 1
                    if self.on_progress:
                        self.on_progress(self.drawn_pixels, self.total_pixels)
                    time.sleep(delay_sec)
            else:
                # 大区域：边界+填充
                boundary, interior = self._classify_boundary_interior(component, group_key)

                # 第一步：画笔画边界
                if current_tool != 'brush':
                    self._switch_tool('brush')
                    current_tool = 'brush'

                for px, py in boundary:
                    self._wait_if_paused()
                    if self._stop_event.is_set():
                        self._save_progress()
                        return True

                    screen_x, screen_y = self.locator.get_screen_pos(px, py)
                    self.backend.click(screen_x, screen_y, press_duration=0.015)
                    self.drawn_pixels += 1
                    if self.on_progress:
                        self.on_progress(self.drawn_pixels, self.total_pixels)
                    time.sleep(delay_sec)

                # 第二步：油漆桶填充内部
                if interior:
                    self._switch_tool('bucket')
                    current_tool = 'bucket'

                    # 点击一个内部像素即可填充整个区域
                    fill_px, fill_py = interior[0]
                    screen_x, screen_y = self.locator.get_screen_pos(fill_px, fill_py)
                    self.backend.click(screen_x, screen_y, press_duration=0.015)
                    # 油漆桶一次填充所有内部像素
                    self.drawn_pixels += len(interior)
                    if self.on_progress:
                        self.on_progress(self.drawn_pixels, self.total_pixels)
                    time.sleep(delay_sec * 2)  # 填充可能需要稍长的等待

        # 结束后确保切回画笔
        if current_tool != 'brush':
            self._switch_tool('brush')

        return False

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

    def test_border(self, on_log=None, on_done=None):
        """
        测试标定：沿画布最外围画一圈边框，黑红交替

        用于验证标定准确性，检查是否所有边缘格子都能点到。
        使用两种颜色（黑色 0-0, 红色 1-0）交替绘制，便于观察。

        :param on_log: 日志回调 (str) -> None
        :param on_done: 完成回调 () -> None
        """
        if not self.locator.calibrated or not self.navigator.calibrated:
            if on_log:
                on_log("[!] 标定未完成，无法测试")
            return

        def _log(msg):
            if on_log:
                on_log(msg)

        def _worker():
            try:
                W = self.locator.grid_width
                H = self.locator.grid_height

                # 构建边框坐标序列（顺时针：顶→右→底→左）
                border_points = []

                # 顶边: (0,0) → (W-1, 0)
                for x in range(W):
                    border_points.append((x, 0))

                # 右边: (W-1, 1) → (W-1, H-1)
                for y in range(1, H):
                    border_points.append((W - 1, y))

                # 底边: (W-2, H-1) → (0, H-1)
                for x in range(W - 2, -1, -1):
                    border_points.append((x, H - 1))

                # 左边: (0, H-2) → (0, 1)
                for y in range(H - 2, 0, -1):
                    border_points.append((0, y))

                total = len(border_points)
                _log(f"[测试标定] 边框共 {total} 个点，黑红交替绘制...")

                time.sleep(1)  # 给用户切窗口的缓冲

                # 重置调色板到第0组
                self.navigator.reset_group()

                # 分两轮画：先画偶数索引（黑色 0-0），再画奇数索引（红色 1-0）
                # 这样只需切 2 次颜色，比每个点都切高效得多
                even_points = [(i, pt) for i, pt in enumerate(border_points) if i % 2 == 0]
                odd_points = [(i, pt) for i, pt in enumerate(border_points) if i % 2 == 1]

                drawn = 0

                # 第一轮：黑色
                _log(f"  第1轮: 选择黑色，绘制 {len(even_points)} 个点...")
                self.navigator.select_color(0, 0)
                time.sleep(0.15)

                for orig_idx, (px, py) in even_points:
                    if self._stop_event.is_set():
                        _log("[测试标定] 已中止")
                        return

                    screen_x, screen_y = self.locator.get_screen_pos(px, py)
                    self.backend.click(screen_x, screen_y, press_duration=0.015)
                    drawn += 1
                    time.sleep(0.03)

                # 第二轮：红色
                _log(f"  第2轮: 选择红色，绘制 {len(odd_points)} 个点...")
                self.navigator.select_color(1, 0)
                time.sleep(0.15)

                for orig_idx, (px, py) in odd_points:
                    if self._stop_event.is_set():
                        _log("[测试标定] 已中止")
                        return

                    screen_x, screen_y = self.locator.get_screen_pos(px, py)
                    self.backend.click(screen_x, screen_y, press_duration=0.015)
                    drawn += 1
                    time.sleep(0.03)

                _log(f"[测试标定] 完成！共绘制 {drawn} 个点")
                _log(f"  请检查游戏中边框是否完整覆盖画布四周")
                _log(f"  如果有缺口或偏移，可用微调功能调整后重新测试")

            except Exception as e:
                _log(f"[测试标定] 出错: {e}")
            finally:
                if on_done:
                    on_done()

        self._stop_event.clear()
        threading.Thread(target=_worker, daemon=True).start()
