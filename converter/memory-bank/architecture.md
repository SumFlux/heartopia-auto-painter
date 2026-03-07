# 系统架构洞察 (Architecture)

## Converter 模块核心数据流与重构说明

### 1. 图片量化转换器 (`heartopia_converter.py`)
- **定位**：图片分析与处理引擎，解析用户图片以符合游戏画板需求。
- **色彩空间约束机制**：不再使用模糊的相近十六进制去硬碰硬。游戏共13组调色系，我们在底层维护了 `HEARTOPIA_COLORS` 作为唯一真理表，配合生成的 `colorId` 作为唯一标识。
- **重要数据流变更（Pixels JSON 协议）**：
  原先仅导出 `{'x': X, 'y': Y, 'color': HEX}`，导致依赖于色彩识别。
  经过本次重构，导出的协议升级为：
  `{'x': X, 'y': Y, 'color': HEX, 'colorId': 'GroupIndex-ColorIndex'}`。
  这使得整个架构从**基于颜色的检索模式**变成了**基于硬件排版的数据绑定模式**，大大降低了耦合性和报错率。

### 2. GUI 界面 (`gui.py`)
- **定位**：给用户提供便捷的视觉反馈与参数调优界面。
- **视觉反馈的提升**：新增了图像增强预处理系统（饱和度/色带增幅）以及 Floyd-Steinberg 像素级防突变抖动算法，使画面转换观感极大改善。

### 3. 共享调色板架构（2026-03-07 重构）

#### 重构前的问题
converter 内部维护了一份独立的 `HEARTOPIA_COLORS` 硬编码列表（28 行颜色数据），同时自行实现了 `_hex_to_rgb`、`_rgb_to_hex`、`_palette_rgb`、`_hex_to_id` 等辅助方法。painter 的 `config.py` 里又维护了另一份 `COLOR_GROUPS` 列表（96 行）。两份数据需要人工保持同步，是典型的重复数据源问题。

#### 重构后的架构
```
shared/
├── __init__.py
├── palette.py      ← 唯一调色板数据源（126 色）
└── pixel_data.py   ← converter 输出 / painter 输入的 JSON 契约

converter/
├── heartopia_converter.py  ← 从 shared.palette 导入颜色数据
└── gui.py                  ← sys.path 设置以支持 shared 导入

painter/
├── config.py               ← 薄封装，re-export shared.palette + painter 专属常量
└── ...
```

**关键设计决策**：
- `shared/palette.py` 是整个项目颜色数据的**唯一真理源**。任何调色板变更只需修改此文件
- `shared/pixel_data.py` 定义了 `PixelData` 类，统一 JSON 的读写和校验逻辑，确保 converter 输出的 JSON 能被 painter 正确解析
- converter 删除了所有内联的颜色数据和辅助函数，改为从 `shared.palette` 导入 `PALETTE_RGB`、`COLOR_ID_MAP`、`hex_to_rgb`、`find_closest_color`
- `sys.path.insert(0, 项目根目录)` 在 converter 和 painter 的入口文件中各设置一次，使 `from shared.xxx import ...` 可用
