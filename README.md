# Heartopia Auto Painter

心动小镇自动画画工具。当前仓库只支持统一桌面应用架构 `heartopia_app/`。

## 当前状态

- 唯一受支持架构：`heartopia_app/`
- 唯一官方启动方式：`python -m heartopia_app`
- 旧 split architecture（`converter/` + `painter/` + `shared/`）已退役
- 旧入口脚本与旧实现代码不再受支持，并已从主运行链路中移除

## 项目结构

```text
heartopia-auto-painter/
├── heartopia_app/
│   ├── __main__.py
│   ├── bootstrap.py
│   ├── application/
│   ├── domain/
│   ├── infrastructure/
│   └── ui/
├── JsonOutput/
├── memory-bank/
└── README.md
```

## 当前能力

统一应用 `heartopia_app` 提供完整的「图片转换 → 标定 → 自动绘制 → 截图验证 / 补画」工作流：

- 图片转换
  - 5 种画布比例：`16:9`、`4:3`、`1:1`、`3:4`、`9:16`
  - 4 档精细度：Level 0–3
  - 基于游戏调色板的最近邻量化
  - Floyd-Steinberg 抖动
  - 图像增强（饱和度 / 对比度 / 锐度）
  - 导出 JSON（含 `colorId`）和 CSV
- 统一桌面应用
  - 单窗口多页面工作流（转换 / 标定 / 绘画 / 设置）
  - 画布、调色板、工具栏标定
  - 固定坐标保存 / 自动应用
  - 自动绘制、断点续画、油漆桶填充
  - 手动截图验证、验证预览、手动 repair

## 启动方式

在仓库根目录执行：

```bash
python -m heartopia_app
```

这是当前唯一官方入口。根 README 不再提供任何旧 split architecture 的启动方式。

## 推荐使用流程

1. 在统一应用中导入图片并完成转换
2. 打开心动小镇并进入画画界面
3. 在标定页完成画布、调色板、工具栏标定
4. 在绘画页导入像素数据并开始绘制
5. 按需执行截图验证与补画

## 调色板说明

全项目当前使用 `heartopia_app/domain/palette.py` 作为唯一调色板来源。

- 共 13 组颜色
- 第 0 组（黑白灰）为 **5 色**
- 第 1–12 组各 10 色
- 当前总计 **125 色**

说明：
- `#feffff` 作为白色可正常参与生成和绘制
- 旧背景色 `#a8978e` 已从调色板移除
- 为兼容旧数据，绘制阶段仍会把 `#a8978e` 视为背景并跳过

## 环境要求

- Windows
- Python 3.8+
- 心动小镇客户端

## 架构说明

当前仓库已经完成从旧 split architecture 到统一应用 `heartopia_app` 的收口：

- `heartopia_app/__main__.py` 与 `heartopia_app/bootstrap.py` 组成完整启动链路
- 领域模型、应用服务、基础设施、UI 全部以 `heartopia_app/` 为准
- 旧的 `converter/`、`painter/`、`shared/` 不再是当前架构说明的一部分

## 致谢

- [Heartopia Painting Tools](https://github.com/zerochansy/Heartopia-Painting-Tools)

---

免责声明：本工具仅供学习和研究使用，请遵守游戏规则。
