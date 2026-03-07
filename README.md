# Heartopia Auto Painter

心动小镇自动画画工具 — 将图片转换为像素画并自动在游戏中绘制。

## 项目简介

基于 [Heartopia Painting Tools](https://github.com/zerochansy/Heartopia-Painting-Tools) 开发，提供完整的「图片 → 像素数据 → 游戏内自动绘制」工作流：

1. **图片转换器** (`converter/`) — 将任意图片转换为心动小镇游戏调色板的像素矩阵
2. **自动画画脚本** (`painter/`) — 读取像素矩阵，自动在游戏中选色、点击绘制

## 项目结构

```
heartopia-auto-painter/
├── shared/                    # 共享模块（converter 和 painter 的公共依赖）
│   ├── palette.py             #   126 色调色板唯一数据源
│   └── pixel_data.py          #   像素数据 JSON 读写契约
├── converter/                 # 图片转换器
│   ├── heartopia_converter.py #   核心转换逻辑
│   ├── gui.py                 #   GUI 图形界面
│   ├── requirements.txt
│   └── README.md
├── painter/                   # 自动画画脚本
│   ├── auto_painter.py        #   GUI 主程序入口
│   ├── paint_engine.py        #   绘画引擎（蛇形遍历、断点续画）
│   ├── palette_navigator.py   #   调色板导航（选色、翻页）
│   ├── canvas_locator.py      #   画布坐标映射
│   ├── mouse_input.py         #   输入后端抽象层
│   ├── window_manager.py      #   游戏窗口管理
│   ├── config.py              #   painter 专属配置
│   ├── requirements.txt
│   └── README.md
└── README.md
```

## 快速开始

### 环境要求

- **Windows 系统**（painter 依赖 Win32 API）
- **Python 3.8+**
- 心动小镇游戏客户端

### 第一步：转换图片

```bash
cd converter
pip install -r requirements.txt

# GUI 方式（推荐）
python gui.py

# 或命令行方式
python heartopia_converter.py your_image.jpg 1:1 2
```

选择比例和精细度后导出 JSON 文件，详见 [转换器文档](./converter/README.md)。

### 第二步：自动画画

```bash
cd painter
pip install -r requirements.txt

# 启动 GUI
python auto_painter.py
```

或者直接双击 `auto_painter_main.bat`。

操作流程：导入 JSON → 标定画布（2 次 Enter）→ 标定调色板（4 次 Enter）→ 开始画画。

详见 [画画脚本文档](./painter/README.md)。

## 功能特性

### 图片转换器

- ✅ 5 种画布比例（16:9、4:3、1:1、3:4、9:16）
- ✅ 4 个精细度等级（30×30 到 150×150）
- ✅ 游戏原生 126 色调色板匹配
- ✅ Floyd-Steinberg 抖动（更平滑的颜色过渡）
- ✅ 图像增强（饱和度、对比度、锐度可调）
- ✅ 自动中心裁剪 + EXIF 旋转处理
- ✅ 导出 JSON（含 colorId 精确定位）和 CSV
- ✅ GUI 实时预览

### 自动画画脚本

- ✅ GUI 控制面板（PySide6）
- ✅ 画布 + 调色板坐标标定（共 6 次 Enter）
- ✅ 标定数据持久化（重启无需重新标定）
- ✅ 按颜色分组 + 蛇形遍历（最优绘制路径）
- ✅ 快捷键控制（F5 开始 / F6 暂停恢复 / F7 停止）
- ✅ 断点续画（中断后可从上次位置继续）
- ✅ 无需管理员权限
- 🧪 PostMessage 后台投递（实验性，不移动鼠标）

## 颜色系统

全项目使用统一的 126 色调色板（`shared/palette.py`），来源于游戏截图实际取色：

| 组号 | 名称 | 色数 |
|:----:|------|:----:|
| 0 | 黑白灰 | 6 |
| 1 | 红色系 | 10 |
| 2 | 橙红色系 | 10 |
| 3 | 橙色系 | 10 |
| 4 | 黄色系 | 10 |
| 5 | 黄绿色系 | 10 |
| 6 | 绿色系 | 10 |
| 7 | 青绿色系 | 10 |
| 8 | 青色系 | 10 |
| 9 | 蓝色系 | 10 |
| 10 | 蓝紫色系 | 10 |
| 11 | 紫色系 | 10 |
| 12 | 粉色系 | 10 |

## 技术栈

| 依赖 | 用途 |
|------|------|
| Pillow | 图片处理 |
| NumPy | 数值计算（颜色匹配、抖动） |
| PySide6 | GUI 界面 |
| pynput | 鼠标模拟 + 键盘监听 |
| pywin32 | Windows 窗口管理 |

## 开发计划

- [x] 图片转换器 + GUI
- [x] 自动画画脚本 + GUI
- [x] 共享调色板模块
- [x] 断点续画
- [ ] PostMessage 后台绘制（不占用鼠标）
- [ ] 批量转换
- [ ] 更多颜色匹配算法（CIEDE2000 等）

## 致谢

- [Heartopia Painting Tools](https://github.com/zerochansy/Heartopia-Painting-Tools) — 原始项目（颜色数据来源）
- 心动小镇游戏开发团队

## 联系方式

- GitHub: [@SumFlux](https://github.com/SumFlux)
- 项目主页: https://github.com/SumFlux/heartopia-auto-painter

---

**免责声明**：本工具仅供学习和研究使用，请遵守游戏规则，不要用于作弊或破坏游戏平衡。
