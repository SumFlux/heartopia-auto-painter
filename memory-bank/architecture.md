# 系统架构 (Architecture)

## 项目总览

heartopia-auto-painter 是一个《心动小镇》游戏的自动像素画绘制工具，由两大子系统组成：

```
heartopia-auto-painter/
├── shared/                  ← 共享数据层（唯一真理源）
│   ├── palette.py           ← 126 色调色板数据 + 工具函数
│   └── pixel_data.py        ← PixelData JSON 契约类
├── converter/               ← 图片→像素矩阵 转换器
│   ├── heartopia_converter.py  ← 核心转换引擎
│   └── gui.py               ← PySide6 转换器 GUI
├── painter/                 ← 自动画画脚本
│   ├── auto_painter.py      ← GUI 主程序入口
│   ├── canvas_locator.py    ← 画布定位（4角双线性插值 + 红色标记自动检测）
│   ├── paint_engine.py      ← 绘画引擎（蛇形遍历、断点续画、油漆桶优化）
│   ├── palette_navigator.py ← 调色板导航（标签切换 + 色块点击）
│   ├── mouse_input.py       ← 输入后端抽象层（PynputBackend / PostMessageBackend）
│   ├── window_manager.py    ← 游戏窗口定位与截图
│   └── config.py            ← painter 专属配置（薄封装，re-export shared.palette）
├── JsonOutput/              ← converter 输出的 JSON 文件
└── memory-bank/             ← 项目记忆库（本目录）
```

---

## Converter 模块

### 图片量化转换器 (`heartopia_converter.py`)
- **定位**：图片分析与处理引擎，解析用户图片以符合游戏画板需求。
- **色彩空间约束**：游戏共 13 组调色系（126 色），底层使用 `shared.palette` 作为唯一真理表，配合 `colorId` 作为唯一标识。
- **数据流协议**：导出 `{'x': X, 'y': Y, 'color': HEX, 'colorId': 'GroupIndex-ColorIndex'}`，使架构从颜色检索模式变为基于 UI 排布的数据绑定模式。

### GUI 界面 (`gui.py`)
- 提供图像增强预处理（饱和度/对比度/锐度滑块）
- Floyd-Steinberg 误差扩散抖动算法，改善色阶过渡

---

## Painter 模块

### 坐标与点击模拟 (`mouse_input.py`)
技术选型经历三次迭代：
1. ~~`pyautogui`~~：被 Unity 引擎屏蔽（只移动不点击）
2. ~~`ctypes.windll.user32.SendInput`~~：C 内存对齐问题 + 高 DPI 坐标映射崩溃
3. **`pynput`（最终方案）**：安全的物理鼠标级模拟，配合 `SetProcessDpiAwareness(1)` 实现 1:1 坐标映射

架构：
```
mouse_input.py
├── InputBackend (ABC)       ← 抽象接口：click / move / get_position
├── PynputBackend            ← 默认：物理鼠标移动（屏幕绝对坐标）
├── PostMessageBackend       ← 实验性：Win32 消息投递（窗口客户区坐标）
└── create_backend()         ← 工厂函数
```

### 画布定位 (`canvas_locator.py`)
- **手动标定**：4 角双线性插值，支持非矩形画布
- **自动检测**：在截图居中 1200px 区域内搜索红色像素（R>180, G<80, B<80），BFS 连通分量聚类，取最大 4 簇按几何位置分配四角
- 全局偏移微调 + 窗口相对坐标持久化（`fixed_positions.json`，画布按比例分 profile）

### 绘画引擎 (`paint_engine.py`)
- 蛇形遍历（偶数行右→左，奇数行左→右）
- 断点续画（`paint_progress.json`）
- 油漆桶填充优化：
  - 8-连通 BFS 分组 + 8-邻域边界判定（密封轮廓）
  - 内部像素做 4-连通子区域分析（匹配游戏油漆桶行为），每个子区域单独点击
  - 连通区域 ≥ 30 像素时自动使用油漆桶，小区域逐点画

### GUI 主程序 (`auto_painter.py`)
- 数据导入：加载 JSON 后自动根据比例匹配画布配置
- 固定坐标：按比例存储画布配置（`canvas_profiles`），调色板/工具栏共享
- 绘画控制：速度预设、油漆桶开关、断点续画
- 进度显示：预估剩余时间（基于实时绘画速度）
- 日志：带时间戳的开始/结束记录，含总用时统计
- 4 次点击标定（标签左右 + 色块区域左上右下）
- 2 列 × 5 行布局自动计算 10 个色块中心坐标
- 标签翻页 + 色块点击

### 共享数据层 (`shared/`)
- **`palette.py`**：126 色唯一数据源。`COLOR_GROUPS`（13 组）→ 自动派生 `FLAT_COLORS`、`COLOR_ID_MAP`、`HEX_TO_GROUP`、`PALETTE_RGB`
- **`pixel_data.py`**：`PixelData` 类封装 JSON 读写 + 字段校验

---

## 遗留事项
1. `PostMessageBackend` 仅骨架代码，心动小镇是否响应 PostMessage 鼠标消息未实测
2. 多显示器 / 高 DPI 缩放场景下的坐标准确性仍是已知痛点
3. 物理鼠标占用桌面指针，游戏失焦会导致点击落在窗口外
