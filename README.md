# Heartopia Auto Painter

心动小镇自动画画工具。这个仓库提供完整的「图片 → 像素数据 → 游戏内自动绘制」工作流。

## 项目概览

项目分成两部分：

1. `converter/`：把图片量化到游戏调色板，导出 JSON / CSV
2. `painter/`：读取 JSON，在游戏里自动选色并绘制

共享契约统一放在 `shared/`：

- `shared/palette.py`：调色板唯一数据源
- `shared/pixel_data.py`：像素 JSON 读写契约

## 项目结构

```text
heartopia-auto-painter/
├── shared/
│   ├── palette.py
│   └── pixel_data.py
├── converter/
│   ├── heartopia_converter.py
│   ├── gui.py
│   ├── requirements.txt
│   └── README.md
├── painter/
│   ├── auto_painter.py
│   ├── paint_engine.py
│   ├── palette_navigator.py
│   ├── canvas_locator.py
│   ├── mouse_input.py
│   ├── window_manager.py
│   ├── config.py
│   ├── requirements.txt
│   └── README.md
└── README.md
```

## 当前能力

### 转换器

- 5 种画布比例：`16:9`、`4:3`、`1:1`、`3:4`、`9:16`
- 4 档精细度：Level 0–3
- 基于游戏调色板的最近邻量化
- Floyd-Steinberg 抖动
- 图像增强（饱和度 / 对比度 / 锐度）
- 导出 JSON（含 `colorId`）和 CSV
- GUI 实时预览

### 画画器

- GUI 控制面板（PySide6）
- 画布 4 角标定
- 调色板标定（左右标签 + 色块区域）
- 自动检测画布四角标记点
- 固定坐标保存 / 自动应用
- 工具栏标定（画笔 + 油漆桶）
- 油漆桶填充优化
- 快捷键控制：F5 / F6 / F7
- 断点续画

## 调色板说明

全项目使用 `shared/palette.py` 作为唯一调色板来源。

- 共 13 组颜色
- 第 0 组（黑白灰）现在为 **5 色**
- 第 1–12 组各 10 色
- 当前总计 **125 色**

说明：
- `#feffff` 作为白色可正常参与生成和绘制
- 旧背景色 `#a8978e` 已从调色板移除
- 为兼容旧数据，画画阶段仍会把 `#a8978e` 视为背景并跳过

## 快速开始

### 1. 转图

```bash
cd converter
pip install -r requirements.txt
python gui.py
```

也可以使用命令行：

```bash
python heartopia_converter.py your_image.jpg 1:1 2
```

详细说明见 [converter/README.md](./converter/README.md)。

### 2. 自动画画

```bash
cd painter
pip install -r requirements.txt
python auto_painter.py
```

详细操作说明见 [painter/README.md](./painter/README.md)。

## 推荐使用流程

1. 在 `converter/` 中导入图片并导出 JSON
2. 打开心动小镇并进入画画界面
3. 在 `painter/` 中导入 JSON
4. 标定画布、调色板
5. 如需要，保存固定坐标 / 标定工具栏
6. 开始绘制或使用断点续画

## 环境要求

- Windows
- Python 3.8+
- 心动小镇客户端

## 子文档分工

- 根 `README.md`：项目概览、结构、快速开始
- `converter/README.md`：图片转换参数、输出格式、注意事项
- `painter/README.md`：标定、自动绘制、固定坐标、油漆桶、故障排查

## 致谢

- [Heartopia Painting Tools](https://github.com/zerochansy/Heartopia-Painting-Tools)

---

免责声明：本工具仅供学习和研究使用，请遵守游戏规则。