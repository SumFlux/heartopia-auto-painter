# 进度记录

## 2026-03-07：自动画画脚本初始架构与迭代过程

### 已完成的模块功能
1. **统一的 GUI 界面控制**（`auto_painter.py`）
   - 基于 PySide6，具备导入 JSON / 获取信息 / 标定画布 / 标定调色盘等流程向导，并带有实时进度条显示。
   - 使用 `keyboard` 模块挂死全局按键，允许使用快捷键（如 F6）强制暂停、恢复或中断正在后台执行的无头点按线程。
2. **调色板与颜色控制引擎** (`paint_engine.py` 及 `palette_navigator.py`)
   - 实现了颜色矩阵加载与跳过透明底色。
   - 同步接受 `converter` 新生成的自带专属定位坐标的数据结构 `colorId`，直接寻址对应的色块。
   - 实现**蛇形遍历（Snake Traversal）**，偶数行向右，奇数行向左以达到最小化移动间隔，缩短绘画时间。
3. **窗口拦截与获取** (`window_manager.py` 及 `config.py`)
   - 通过 `pywin32` 定位《心动小镇》进程并置顶显示。
   - 内置真实全色域 126 色的色卡常量用来提供回退（Fallback）功能。

### 已处理的技术难点
- **拒绝使用 pyautogui 软模拟（拦截问题）**：游戏（Unity 引擎）底层屏蔽了常见的 `pyautogui` API（只移动不点击）。最开始重构成 `ctypes` 调用 Windows API 的 `SendInput`，但在某些环境下会发生 C 内存段错误导致 Python `CrashSender.exe` 崩溃。最终全部切换为更安全稳妥的 `pynput` 物理鼠标级驱动外设按压模拟。
- **高 DPI 坐标映射（已宣告）**：Windows 系统的多缩放率导致点击发生微缩。现已在程序启动前强制通过 `ctypes.windll.shcore.SetProcessDpiAwareness(1)` 宣告无视系统缩放获取绝对坐标 1:1，避免大部分的缩水偏左。
- **游戏自身响应瓶颈**：点击颜色发生变更后、必须强行挂起（`sleep 0.35s+`），以等待游戏客户端本身的网格 UI 将调色盘载入和翻页。

### 遗留问题（尚未解决、等其他工具处理）
1. **绝对坐标仍然存在偏移/失准严重**：用户反馈就算在系统上使用了 DPI 宣告以及 `pynput` 的绝对屏幕移动，但如果游戏处于伪全屏或多显示器情况下，依旧会发生绘制偏移、往左偏或往上顶（切屏）。这往往是底层系统 API 获取到的游戏全屏客户区与显示器零点存在隐性偏差。
2. **切屏现象**：因为目前底层发送的坐标依然是在整个 Windows Desktop 发送，当发生上述偏移后，鼠标点击就会意外地落在游戏框外部（甚至别的显示器里），导致应用失去焦点被挂起。

**接下来可尝试的方案**：
- 此类带有独占硬件鼠标捕捉的游戏，不应直接在屏幕坐标 `(x, y)` 发送点击。
- **建议接手工具尝试**：使用 `win32api.PostMessage(hwnd, WM_LBUTTONDOWN)` 直接向目标窗口句柄的消息队列内投递非焦点下的窗体内相对客户端坐标（Client Relative Coords）的虚拟点击消息。这能够一劳永逸地解决鼠标实体飞出屏幕、不同显示器和分辨率下错位的问题！

### 2026-03-07：提取共享调色板模块，现代化 painter 架构

#### 背景
converter 和 painter 各自维护了独立的颜色数据副本。painter 的 `config.py` 包含 96 行 `COLOR_GROUPS` 定义（且有一处错误缩进），与 converter 的 `HEARTOPIA_COLORS` 本质上是同一份数据的两种写法。此外 painter 依赖 `pyautogui`（取鼠标坐标）和 `keyboard`（全局热键），两者都存在问题：`keyboard` 需要管理员权限，`pyautogui` 与 `pynput` 的 DPI 处理方式不一致可能导致坐标偏差。

#### 改动内容

##### 新建 `shared/` 共享包
- **`shared/palette.py`**：126 色调色板的唯一数据源。从 `COLOR_GROUPS` 自动派生 `FLAT_COLORS`、`COLOR_ID_MAP`、`HEX_TO_GROUP`、`PALETTE_RGB`。提供 `hex_to_rgb`、`find_closest_color`、`get_closest_color_group`、`CANVAS_BACKGROUND_COLORS`。
- **`shared/pixel_data.py`**：`PixelData` 类，封装 converter 输出 / painter 输入的 JSON 格式。内置字段校验，修复旧代码用 `len(pixels)` 当高度而非读取 `gridHeight` 的维度 bug。

##### 重构 `config.py`
- 从 96 行缩减到 ~40 行
- **删除**：`COLOR_GROUPS` 列表、`COLOR_TO_GROUP` 字典构建、`CANVAS_BACKGROUND_COLORS` 定义、`hex_to_rgb` 函数、`get_closest_color_group` 函数
- **保留**：游戏窗口参数（`GAME_PROCESS`、`GAME_WINDOW_TITLE`）、速度预设（`SPEED_PRESETS`）、热键定义
- **新增**：`sys.path` 设置 + `from shared.palette import ...` 统一导入

##### 重构 `mouse_input.py`（输入后端抽象化）
- 旧版：两个裸函数 `click_at` / `move_to`，直接使用 `pynput`
- 新版：`InputBackend` 抽象基类 + 两个实现：
  - `PynputBackend`：默认方案，物理鼠标移动（屏幕绝对坐标）
  - `PostMessageBackend`：实验性方案，Win32 消息投递（窗口客户区坐标，不移动物理鼠标）
  - `create_backend()` 工厂函数
- 所有下游模块通过接口调用，不再硬耦合具体实现

##### 重构 `canvas_locator.py`
- 移除 `import pyautogui` 和 `import json`（本模块只做坐标计算，不需要鼠标库）

##### 重构 `palette_navigator.py`（标定简化）
- 构造函数接收 `InputBackend` 实例
- **标定从 14 次 Enter 简化为 4 次**：标签左 → 标签右 → 色块左上角 → 色块右下角
- 内部根据 2 列 × 5 行布局自动计算 10 个色块中心坐标（`_compute_block_positions`）
- 序列化格式也简化为 4 个坐标点（而非 2 + 10 个）

##### 重构 `paint_engine.py`
- 构造函数接收 `InputBackend` 实例
- 新增 `load_pixel_data(PixelData)` 方法，同时保留旧的 `load_pixels(list)` 兼容接口
- **新增断点续画功能**：
  - `_save_progress` / `_load_progress` / `_clear_progress` 将进度持久化到 `paint_progress.json`
  - `start(resume_from_checkpoint=True)` 跳过已完成的颜色组，从中断处继续
  - `has_saved_progress()` 供 GUI 检查是否有可恢复的进度

##### 重构 `auto_painter.py`（GUI 主程序）
- **移除 `keyboard` 依赖**：用 `pynput.keyboard.Listener` 替代（`KeyboardListener` 类），不再需要管理员权限
- **移除 `pyautogui` 依赖**：用 `pynput.mouse.Controller` 替代（`MousePositionGetter` 类），与 InputBackend 坐标体系统一
- **标定数据持久化**：自动保存/加载 `calibration.json`，重启程序无需重新标定
- **新增断点续画按钮**：检测到 `paint_progress.json` 时自动启用
- **新增网格尺寸校验**：标定的画布尺寸与导入的 JSON 尺寸不匹配时警告并禁用开始按钮
- **引擎回调通过 Qt Signal 桥接**：避免跨线程 GUI 更新的竞态问题
- 调色板标定交互从 12 步文字提示简化为 4 步

##### 依赖清理
- `requirements.txt` 移除 `pyautogui` 和 `keyboard`
- `auto_painter_main.bat` 移除 `RunAs` 管理员提权，改为普通 `python auto_painter.py`

#### 验证结果
- 11 个 Python 文件语法检查全部通过
- `shared.palette`：126 色、COLOR_ID_MAP 映射、find_closest_color 匹配 均正常
- `shared.pixel_data`：PixelData 加载、校验、序列化 均正常
- painter 全模块导入链正常：config → mouse_input → canvas_locator → palette_navigator → paint_engine
- converter 导入链正常：heartopia_converter 使用 shared.palette 初始化和匹配行为不变

#### 遗留事项
1. `PostMessageBackend` 仅实现了骨架代码，心动小镇是否响应 PostMessage 鼠标消息尚未实测
2. 需要在实际游戏中进行端到端手动测试：导入 JSON → 标定 → 画画 → 暂停/续画 完整流程
3. 多显示器 / 高 DPI 缩放场景下的坐标准确性仍是已知痛点
