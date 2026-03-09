"""
心动小镇自动画画脚本 — 调色板导航模块

管理 13 组颜色的切换定位，以及组内色块坐标的点击。
依赖 InputBackend 接口发送点击，不直接调用具体鼠标库。

标定简化说明：
  旧版需要用户手动标定 14 个点（2个标签 + 10个色块）
  新版只需 4 个点：标签左侧 + 标签右侧 + 色块区域左上角 + 色块区域右下角
  然后根据已知的 2列x5行 网格布局自动计算每个色块中心坐标
"""

import time
from typing import Tuple, Dict, Optional

from mouse_input import InputBackend


class PaletteNavigator:
    """调色板导航与颜色选择器"""

    # 色块网格布局常量（2 列 x 5 行）
    BLOCK_COLS = 2
    BLOCK_ROWS = 5
    BLOCK_COUNT = BLOCK_COLS * BLOCK_ROWS  # 10

    def __init__(self, backend: InputBackend):
        self.backend = backend
        self.calibrated = False

        # 标签翻页坐标
        self.left_tab: Optional[Tuple[int, int]] = None
        self.right_tab: Optional[Tuple[int, int]] = None

        # 色块区域的边界（左上角和右下角）
        self.blocks_top_left: Optional[Tuple[int, int]] = None
        self.blocks_bottom_right: Optional[Tuple[int, int]] = None

        # 自动计算的 10 个色块中心坐标 { index: (x, y) }
        self.color_blocks: Dict[int, Tuple[int, int]] = {}

        # 当前选中的组号 (0-based)
        self.current_group_idx = 0

    def reset(self):
        """重置所有状态到初始值（清除标定时使用）"""
        self.calibrated = False
        self.left_tab = None
        self.right_tab = None
        self.blocks_top_left = None
        self.blocks_bottom_right = None
        self.color_blocks = {}
        self.current_group_idx = 0

    def calibrate(self,
                  left_tab: Tuple[int, int],
                  right_tab: Tuple[int, int],
                  blocks_top_left: Tuple[int, int],
                  blocks_bottom_right: Tuple[int, int]):
        """
        一次性标定调色板（4 个点）

        :param left_tab: 色系标签最左侧可见组的坐标（用于向左翻页）
        :param right_tab: 色系标签最右侧可见组的坐标（用于向右翻页）
        :param blocks_top_left: 色块区域左上角第一个色块的中心坐标
        :param blocks_bottom_right: 色块区域右下角最后一个色块的中心坐标
        """
        self.left_tab = left_tab
        self.right_tab = right_tab
        self.blocks_top_left = blocks_top_left
        self.blocks_bottom_right = blocks_bottom_right

        # 根据 2x5 网格自动计算 10 个色块中心
        self._compute_block_positions()
        self.calibrated = True

    def _compute_block_positions(self):
        """从左上角和右下角自动计算 10 个色块中心坐标"""
        if not self.blocks_top_left or not self.blocks_bottom_right:
            return

        tl_x, tl_y = self.blocks_top_left
        br_x, br_y = self.blocks_bottom_right

        # 列间距和行间距
        if self.BLOCK_COLS > 1:
            col_step = (br_x - tl_x) / (self.BLOCK_COLS - 1)
        else:
            col_step = 0

        if self.BLOCK_ROWS > 1:
            row_step = (br_y - tl_y) / (self.BLOCK_ROWS - 1)
        else:
            row_step = 0

        # 索引布局：从上到下，从左到右
        # [0] [1]
        # [2] [3]
        # [4] [5]
        # [6] [7]
        # [8] [9]
        self.color_blocks = {}
        for row in range(self.BLOCK_ROWS):
            for col in range(self.BLOCK_COLS):
                idx = row * self.BLOCK_COLS + col
                x = round(tl_x + col * col_step)
                y = round(tl_y + row * row_step)
                self.color_blocks[idx] = (x, y)

    def reset_group(self):
        """将调色板重置回第 0 组（黑白灰）
        通过连续点击左侧标签 13 次确保回到最左边"""
        if not self.calibrated or not self.left_tab:
            return

        for _ in range(13):
            self.backend.click(self.left_tab[0], self.left_tab[1])
            time.sleep(0.1)

        self.current_group_idx = 0
        time.sleep(0.5)

    def switch_to_group(self, target_group_idx: int):
        """
        切换到目标颜色组（相对翻页）。
        需要在开始绘画前调用 reset_group 确保当前在第 0 组。
        """
        if not self.calibrated:
            raise RuntimeError("调色板尚未标定")

        if target_group_idx == self.current_group_idx:
            return

        diff = target_group_idx - self.current_group_idx

        if diff > 0:
            for _ in range(diff):
                self.backend.click(self.right_tab[0], self.right_tab[1])
                time.sleep(0.3)
        else:
            for _ in range(abs(diff)):
                self.backend.click(self.left_tab[0], self.left_tab[1])
                time.sleep(0.3)

        self.current_group_idx = target_group_idx
        time.sleep(0.2)

    def select_color(self, target_group_idx: int, color_idx: int):
        """
        选择指定颜色：先切换组，再点击组内色块

        :param target_group_idx: 目标颜色组号（0-12）
        :param color_idx: 组内色块索引（0-9，组0为0-4）
        """
        if not self.calibrated:
            raise RuntimeError("调色板尚未标定")

        # 切换组
        self.switch_to_group(target_group_idx)

        # 点击色块
        if color_idx not in self.color_blocks:
            raise ValueError(f"无效的色块索引: {color_idx}（已标定索引: {list(self.color_blocks.keys())}）")

        bx, by = self.color_blocks[color_idx]
        self.backend.click(bx, by)
        time.sleep(0.35)  # 等待游戏 UI 响应

    def to_dict(self) -> dict:
        """序列化标定数据（用于持久化保存）"""
        return {
            'left_tab': list(self.left_tab) if self.left_tab else None,
            'right_tab': list(self.right_tab) if self.right_tab else None,
            'blocks_top_left': list(self.blocks_top_left) if self.blocks_top_left else None,
            'blocks_bottom_right': list(self.blocks_bottom_right) if self.blocks_bottom_right else None,
        }

    def from_dict(self, data: dict):
        """从字典恢复标定数据"""
        lt = data.get('left_tab')
        rt = data.get('right_tab')
        btl = data.get('blocks_top_left')
        bbr = data.get('blocks_bottom_right')

        if lt and rt and btl and bbr:
            self.calibrate(
                left_tab=tuple(lt),
                right_tab=tuple(rt),
                blocks_top_left=tuple(btl),
                blocks_bottom_right=tuple(bbr),
            )

    def compute_relative(self, window_offset: Tuple[int, int]) -> dict:
        """计算调色板各点相对于窗口客户区的偏移"""
        wx, wy = window_offset
        return {
            'left_tab': [self.left_tab[0] - wx, self.left_tab[1] - wy],
            'right_tab': [self.right_tab[0] - wx, self.right_tab[1] - wy],
            'blocks_top_left': [self.blocks_top_left[0] - wx, self.blocks_top_left[1] - wy],
            'blocks_bottom_right': [self.blocks_bottom_right[0] - wx, self.blocks_bottom_right[1] - wy],
        }

    def calibrate_from_window(self, window_offset: Tuple[int, int], relative_data: dict):
        """根据窗口位置 + 固定的窗口内相对坐标自动标定"""
        wx, wy = window_offset
        self.calibrate(
            left_tab=(wx + relative_data['left_tab'][0], wy + relative_data['left_tab'][1]),
            right_tab=(wx + relative_data['right_tab'][0], wy + relative_data['right_tab'][1]),
            blocks_top_left=(wx + relative_data['blocks_top_left'][0], wy + relative_data['blocks_top_left'][1]),
            blocks_bottom_right=(wx + relative_data['blocks_bottom_right'][0], wy + relative_data['blocks_bottom_right'][1]),
        )
