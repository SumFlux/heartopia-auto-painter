# 系统架构 (Architecture)

## 项目总览

heartopia-auto-painter 是一个《心动小镇》游戏的自动像素画绘制工具。

当前仓库已完成统一应用收口，**`heartopia_app/` 是唯一受支持的正式架构**。标准启动方式为：

```bash
python -m heartopia_app
```

旧 split architecture（`converter/` + `painter/` + `shared/`）已正式退役，不再作为运行时或架构设计的一部分。

## 当前正式架构

```text
heartopia-auto-painter/
├── heartopia_app/               ← 唯一正式应用包（python -m heartopia_app）
│   ├── __main__.py              ← 包入口
│   ├── bootstrap.py             ← 启动引导（DPI、QApplication 初始化）
│   ├── domain/                  ← 领域层
│   │   ├── palette.py           ← 125 色调色板数据 + 工具函数
│   │   ├── pixel_data.py        ← Pixel / PixelData 数据模型（含 JSON/CSV 序列化）
│   │   ├── conversion.py        ← 图片转换引擎（ConversionRequest / Result / PixelArtConverter）
│   │   ├── calibration.py       ← 标定数据模型（Canvas / Palette / Toolbar Calibration）
│   │   ├── paint_algorithms.py  ← 绘制相关算法
│   │   └── paint_plan.py        ← 绘画计划模型（PaintGroup / PaintPlan）
│   ├── application/             ← 应用层
│   │   ├── app_state.py         ← AppSettings + WorkspaceState（全局共享状态）
│   │   ├── calibration_service.py ← 标定服务
│   │   ├── conversion_service.py ← 转换服务
│   │   └── paint_session.py     ← 绘画会话与执行编排
│   ├── infrastructure/          ← 基础设施层
│   │   ├── input_backend.py     ← 输入后端
│   │   ├── window_backend.py    ← 窗口查找 / 截图后端
│   │   ├── constants.py         ← 应用名、文件名常量
│   │   ├── paths.py             ← 应用数据目录（%LOCALAPPDATA%\heartopia-auto-painter）
│   │   ├── settings_repository.py    ← 设置持久化
│   │   ├── calibration_repository.py ← 标定数据持久化
│   │   └── session_repository.py     ← 绘画会话持久化
│   └── ui/                      ← UI 层
│       ├── main_window.py       ← 主窗口（QTabWidget 标签页切换）
│       └── pages/
│           ├── convert_page.py      ← 转换页
│           ├── calibration_page.py  ← 标定页
│           ├── paint_page.py        ← 绘画页
│           └── settings_page.py     ← 设置页
├── JsonOutput/                  ← 导出产物
└── memory-bank/                 ← 项目记忆库
```

## 已退役旧架构

以下旧 split architecture 已退役：

```text
converter/                ← 旧独立图片转换器
painter/                  ← 旧独立画画脚本
shared/                   ← 旧共享数据层
```

退役结论：
- 旧 GUI / CLI / bat 入口不再受支持
- 旧 `shared/` 共享层已被 `heartopia_app/domain/*` 取代
- 旧 painter 运行时实现已被 `heartopia_app/application/*`、`domain/*`、`infrastructure/*` 承接
- 仓库对外只保留一种架构叙事：`heartopia_app`

---

## 当前分层说明

### Domain 层
- **palette.py** — 125 色唯一数据源。`COLOR_GROUPS`（13 组）→ 自动派生 `FLAT_COLORS`、`COLOR_ID_MAP`、`HEX_TO_GROUP`、`PALETTE_RGB`
- **pixel_data.py** — 类型化 `Pixel` dataclass + `PixelData` 模型，支持 JSON/CSV 序列化
- **conversion.py** — 图片量化转换引擎，支持中心裁剪、EXIF、增强、Floyd-Steinberg 抖动
- **calibration.py** — 标定数据模型（CanvasCalibration / PaletteCalibration / ToolbarCalibration）
- **paint_algorithms.py** — 绘制计划与桶填充相关算法
- **paint_plan.py** — 绘画计划模型（PaintGroup / PaintPlan）

### Application 层
- **app_state.py** — `AppSettings`（应用配置）+ `WorkspaceState`（运行时共享状态）
- **conversion_service.py** — 转换服务包装
- **calibration_service.py** — 标定功能与测试绘制逻辑
- **paint_session.py** — 绘画会话、断点续画、repair pass、执行编排

### Infrastructure 层
- **input_backend.py** — 输入抽象与具体后端
- **window_backend.py** — 游戏窗口查找、截图与窗口矩形信息
- **paths.py** — 应用数据统一存储在 `%LOCALAPPDATA%\heartopia-auto-painter`
- **repositories** — 设置 / 标定 / 会话的 JSON 持久化

### UI 层
- **main_window.py** — 4 标签页主窗口（转换 / 标定 / 绘画 / 设置），并在切回“绘画”页时主动触发 `PaintPage` 刷新当前上下文
- **convert_page.py** — 完整转换功能（选图、参数、转换、预览、导出）
- **calibration_page.py** — 标定页，支持画布/调色板/工具栏标定、offset 微调、subpixel phase 切换、固定坐标保存/应用、测试标定
- **paint_page.py** — 绘画控制页，已包含主绘制、断点续画、手动截图验证、验证预览、手动 repair、验证缓存失效控制
- **settings_page.py** — 设置管理

---

## 当前架构结论

1. **单一入口** — `python -m heartopia_app`
2. **无旧架构桥接层** — 统一使用包内导入，不再依赖 `sys.path.insert(...)`
3. **统一数据模型** — 调色板与像素数据均以 `heartopia_app/domain/*` 为准
4. **统一运行时目录** — 不再以旧脚本目录作为主要运行环境
5. **统一产品叙事** — 仓库、文档、memory-bank 只描述 `heartopia_app`

### 已验证的绘制稳定性结论（2026-03）
- 拖动绘制在边框测试中有效，但在正式绘制（尤其是 bucket boundary）中不够稳定，snake_sort 点序不是连续轮廓，拖动无法保证封闭。
- **当前正式绘制已全面回退为逐点 click**，不再使用 drag_path。
- 桶填充（bucket fill）策略：
  - boundary 用 brush 逐点 click 封边
  - `shrink_interior_away_from_boundary` 缩掉的 ring 像素也用 brush 补画（否则进度计数会缺失）
  - safe_interior 大子区域（≥4 像素）用桶工具填充，每次点击前先点 (x-1, y) 再点 (x, y)（左偏 1px 双击补偿）
  - safe_interior 小子区域（<4 像素）改用 brush 逐点 click（桶工具对极小区域不可靠）
- 当前截图验证/repair 架构：
  - `PaintPage` 持有最近一次 `VerificationResult`、验证预览图、当前页面 `context key`
  - 额外单独记录“最近一次验证结果生成时的 context key”，用于判断结果是否仍有效
  - 当重新验证、补画开始/完成/中断/异常结束、或标定/像素数据上下文变化时，会主动清空旧验证缓存
  - `MainWindow` 在切回“绘画”页时触发 `PaintPage.refresh_for_current_context()`，确保标定页改动能让绘画页上的旧验证结果失效
- 当前 repair 策略：
  - 仍为 `brush-only + no bucket`
  - repair 点击模式已从九宫格降为**十字补点**（中心 + 上下左右）
  - repair 候选已从仅 `missing_background_like` 扩展为 `missing_background_like + wrong_palette_color`
  - `uncertain` 仍不自动修复
  - repair 速度复用 UI 速度选择；若用户选 `fast`，repair 会保守钳到 `normal`
- **TODO**: `CalibrationService.test_border()` 仍使用拖动方式（drag_path），后续需改为纯 click 并彻底删除 drag 相关代码。
