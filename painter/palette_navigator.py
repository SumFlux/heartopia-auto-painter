"""
心动小镇自动画画脚本 — 调色板导航模块

管理 13 组颜色的切换定位，以及组内色块坐标的点击
"""

import time
from typing import Tuple, Dict

import pyautogui
from mouse_input import click_at


class PaletteNavigator:
    """调色板导航与颜色选择器

    需要用户手动标定两组坐标：
    1. 颜色组标签坐标列表 (group_tabs): 上方横排的 13 个颜色组切换按钮的屏幕坐标
    2. 色块坐标矩阵 (color_blocks): 下方 2列 x 5行 的 10 个颜色块的屏幕坐标
    """

    def __init__(self):
        self.calibrated = False

        # --- 需标定的坐标 ---
        # 13 个颜色组标签的屏幕坐标。索引 0-12 对应组 1-13
        # 由于屏幕上同时只能看到约 5 个，这里保存的是“点击后能切换到该组”的固定坐标
        # 实际上用户只需标定可见的 5 个位置即可，但为了方便，目前要求标定"切换下一组"的常用位置
        self.group_tabs: Dict[int, Tuple[int, int]] = {}

        # 调色板上的 10 个色块坐标
        # 索引 0-9 对应:
        # [0] [1]
        # [2] [3]
        # [4] [5]
        # [6] [7]
        # [8] [9]
        self.color_blocks: Dict[int, Tuple[int, int]] = {}

        # 当前选中的组号 (0-based)
        self.current_group_idx = 0

    def calibrate_tabs(self, tabs_coords: Dict[int, Tuple[int, int]]):
        """标定上方组标签的坐标(这里目前要求传入可见视口的固定切换点)
        对于心动小镇，其实只需两个坐标：可见的最左侧色块用于向左翻，可见的最右侧用于向右翻。
        为了简化：要求传入左、右两个翻页点击点的坐标。
        """
        self.group_tabs = tabs_coords

    def calibrate_blocks(self, blocks_coords: Dict[int, Tuple[int, int]]):
        """标定下方 10 个色块的坐标"""
        self.color_blocks = blocks_coords
        if len(self.color_blocks) > 0 and 'left_tab' in self.group_tabs and 'right_tab' in self.group_tabs:
            self.calibrated = True

    def reset_group(self):
        """将调色板重置回第 1 组（黑白灰）
        通过连续点击左侧可见标签 13 次实现，确保回到最左边
        """
        if not self.calibrated:
            return

        left_tab = self.group_tabs.get('left_tab')
        if not left_tab:
            return

        for _ in range(13):
            click_at(left_tab[0], left_tab[1])
            time.sleep(0.1)

        self.current_group_idx = 0
        time.sleep(0.5) # 等待 UI 稳定

    def switch_to_group(self, target_group_idx: int):
        """
        切换到目标颜色组。
        依靠 'left_tab' 和 'right_tab' 进行相对移动。
        注意：需要在开始绘画前调用 reset_group 确保当前在第 0 组。
        """
        if not self.calibrated:
            raise RuntimeError("调色板尚未标定")

        if target_group_idx == self.current_group_idx:
            return

        diff = target_group_idx - self.current_group_idx

        # 需要向右平移
        if diff > 0:
            right_tab = self.group_tabs['right_tab']
            for _ in range(diff):
                click_at(right_tab[0], right_tab[1])
                time.sleep(0.3)  # 等待平移动画
        # 需要向左平移
        else:
            left_tab = self.group_tabs['left_tab']
            for _ in range(abs(diff)):
                click_at(left_tab[0], left_tab[1])
                time.sleep(0.3)

        self.current_group_idx = target_group_idx
        time.sleep(0.2)  # 给最后的色盘加载一点时间

    def select_color(self, target_group_idx: int, color_idx: int):
        """
        选择指定颜色：先切换组，再点击组内色块
        """
        if not self.calibrated:
            raise RuntimeError("调色板尚未标定")

        # 1. 切换组
        self.switch_to_group(target_group_idx)

        # 2. 点击组内色块
        if color_idx not in self.color_blocks:
            raise ValueError(f"无效的色块索引: {color_idx}")

        block_pos = self.color_blocks[color_idx]
        click_at(block_pos[0], block_pos[1])
        time.sleep(0.35) # 等待游戏内部 UI 响应切换颜色的耗时

    def to_dict(self) -> Dict:
        """保存配置"""
        return {
            'group_tabs': self.group_tabs,
            'color_blocks': self.color_blocks
        }

    def from_dict(self, data: Dict):
        """加载配置"""
        self.group_tabs = data.get('group_tabs', {})
        # JSON 的 key 在反序列化时变成了 string，需要转回 int 
        raw_blocks = data.get('color_blocks', {})
        self.color_blocks = {int(k): tuple(v) for k, v in raw_blocks.items()}

        if len(self.color_blocks) > 0 and 'left_tab' in self.group_tabs and 'right_tab' in self.group_tabs:
            self.calibrated = True
