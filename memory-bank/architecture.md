# 系统架构 (Architecture)

## 项目总览

heartopia-auto-painter 是一个《心动小镇》游戏的自动像素画绘制工具。

当前正在进行**统一应用重构**，从旧的双系统架构迁移到单一 PySide6 桌面应用。

### 新架构（进行中）

```
heartopia-auto-painter/
├── heartopia_app/               ← 新统一包（python -m heartopia_app 启动）
│   ├── __main__.py              ← 包入口
│   ├── bootstrap.py             ← 启动引导（DPI、QApplication 初始化）
│   ├── domain/                  ← 领域层
│   │   ├── palette.py           ← 125 色调色板数据 + 工具函数
│   │   ├── pixel_data.py        ← Pixel / PixelData 数据模型（含 JSON/CSV 序列化）
│   │   ├── conversion.py        ← 图片转换引擎（ConversionRequest / Result / PixelArtConverter）
│   │   ├── calibration.py       ← 标定数据模型（Canvas / Palette / Toolbar Calibration）
│   │   └── paint_plan.py        ← 绘画计划模型（PaintGroup / PaintPlan）
│   ├── application/             ← 应用层
│   │   ├── app_state.py         ← AppSettings + WorkspaceState（全局共享状态）
│   │   └── conversion_service.py ← 转换服务（包装 domain 逻辑）
│   ├── infrastructure/          ← 基础设施层
│   │   ├── constants.py         ← 应用名、文件名常量
│   │   ├── paths.py             ← 应用数据目录（%LOCALAPPDATA%\heartopia-auto-painter）
│   │   ├── settings_repository.py    ← 设置持久化
│   │   ├── calibration_repository.py ← 标定数据持久化
│   │   └── session_repository.py     ← 绘画会话持久化
│   └── ui/                      ← UI 层
│       ├── main_window.py       ← 主窗口（QTabWidget 标签页切换）
│       └── pages/
│           ├── convert_page.py      ← 转换页（完整功能）
│           ├── calibration_page.py  ← 标定页（UI 就位，核心功能待迁移）
│           ├── paint_page.py        ← 绘画页（UI 就位，核心功能待迁移）
│           └── settings_page.py     ← 设置页（完整功能）
├── converter/               ← [旧] 图片转换器（待退役）
├── painter/                 ← [旧] 自动画画脚本（待退役）
├── shared/                  ← [旧] 共享数据层（已迁移到 domain/）
├── JsonOutput/              ← converter 输出的 JSON 文件
└── memory-bank/             ← 项目记忆库
```

### 旧架构（待退役）

```
converter/                ← 独立图片转换器（gui.py + heartopia_converter.py）
painter/                  ← 独立画画脚本（auto_painter.py + paint_engine.py + ...）
shared/                   ← 共享数据层（palette.py + pixel_data.py）
```

---

## 新架构分层说明

### Domain 层
- **palette.py** — 125 色唯一数据源。`COLOR_GROUPS`（13 组）→ 自动派生 `FLAT_COLORS`、`COLOR_ID_MAP`、`HEX_TO_GROUP`、`PALETTE_RGB`
- **pixel_data.py** — 类型化 `Pixel` dataclass + `PixelData` 模型，支持 JSON/CSV 序列化
- **conversion.py** — 图片量化转换引擎，支持中心裁剪、EXIF、增强、Floyd-Steinberg 抖动
- **calibration.py** — 标定数据模型（CanvasCalibration / PaletteCalibration / ToolbarCalibration）

### Application 层
- **app_state.py** — `AppSettings`（应用配置）+ `WorkspaceState`（运行时共享状态）
- **conversion_service.py** — 转换服务包装

### Infrastructure 层
- **paths.py** — 应用数据统一存储在 `%LOCALAPPDATA%\heartopia-auto-painter`
- **repositories** — 设置 / 标定 / 会话的 JSON 持久化

### UI 层
- **main_window.py** — 4 标签页主窗口（转换 / 标定 / 绘画 / 设置）
- **convert_page.py** — 完整转换功能（选图、参数、转换、预览、导出）
- **calibration_page.py** — 标定 UI 框架（功能待接入旧逻辑）
- **paint_page.py** — 绘画控制 UI 框架（功能待接入旧逻辑）
- **settings_page.py** — 设置管理

---

## 关键改进

1. **消除 `sys.path.insert(...)` 反模式** — 全部使用包内导入
2. **统一应用数据目录** — 不再在代码目录存放运行时 JSON
3. **typed 数据模型** — `Pixel` dataclass 替代原始 dict
4. **GUI 无关的 domain** — 转换引擎不依赖 PySide6
5. **单一入口** — `python -m heartopia_app`

---

## 遗留事项（待迁移）

1. 画布标定功能（canvas_locator.py 逻辑待接入 calibration_page）
2. 调色板标定功能（palette_navigator.py 逻辑待接入 calibration_page）
3. 绘画引擎（paint_engine.py 逻辑待接入 paint_page）
4. 输入后端（mouse_input.py 待迁移到 infrastructure）
5. 窗口管理（window_manager.py 待迁移到 infrastructure）
6. 旧入口退役（converter/gui.py、painter/auto_painter.py）
