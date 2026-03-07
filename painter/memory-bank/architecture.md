# 架构说明 (Architecture)

## 核心重构与系统级洞察

### 1. 坐标与点击模拟系统的选型更迭 (`mouse_input.py`)
自动画笔最核心的问题是如何稳定地绕过以 Unity 引擎开发的游戏（如《心动小镇》）自带的鼠标硬件输入拦截，以及如何规避 Windows 在多显示器、高 DPI 缩放下的坐标漂移。

我们在这方面探索了三次技术更迭路线：
- **方案一（失败）**：普通的高层模拟库 `pyautogui.click()`
  - **原因**：产生的事件信号层级过高，被游戏底层直接剥离了 Click 这个事件点，表现为”看见指针移过去了，但并未产生点击效果”。

- **方案二（勉强可用但脆弱）**：底层 Windows C 接口硬调用 `ctypes.windll.user32.SendInput`
  - **优点**：发送的是纯硬件级的鼠标中断，游戏 100% 能够识别。
  - **严重缺陷**：
    1. Python 与 C 数据结构体的对齐在不同位数的系统上存在差异，极易导致指针越界并引发 `python has stopped working` 和 `CrashSender.exe` 层面的毁灭性内存错误。
    2. 这个 API 在移动鼠标（MOUSEEVENTF_ABSOLUTE）时，它要求的是一个强范围在 `0~65535` 之间的虚拟屏幕百分比。在系统开启了 125%~150% 等 DPI 放大，或者有另一块异形扩展屏时，此推算法完全破产，造成严重的全局偏移。

- **最终决定方案**：使用成熟的高级封装层 `pynput`
  - 完全避开了自写结构体带来的 C 语言内存段错误。
  - 将坐标直接发送为其内部处理完善的物理像素绝对光标寻址，确保了与系统 DPI（需搭配 `SetProcessDpiAwareness(1)` 宣告）实现真正的 1:1 坐标对齐映射。

### 2. 画笔引擎色彩协议大一统 (`paint_engine.py`)
- 在之前的版本中，这块完全依赖于图像预处理侧输送过来的十六进制（Hex）值进行颜色碰撞，这极度依赖色彩的 100% 不可变性。
- 通过重构协议，引入从 `converter` 直接透传下来的物理 UI 排布标识符（即 `colorId`, 格式为 “横向组别-纵向组别序号”），将图像算法与控制算法完全剥离解耦。

### 3. 输入后端抽象层（2026-03-07 重构新增）

#### 重构前的问题
`mouse_input.py` 只暴露了 `click_at` 和 `move_to` 两个裸函数，所有模块直接 `from mouse_input import click_at` 硬耦合。如果要切换到 PostMessage 后端，需要改动多个文件。

#### 重构后的架构
```
mouse_input.py
├── InputBackend (ABC)       ← 抽象接口：click / move / get_position
├── PynputBackend            ← 默认：物理鼠标移动（屏幕绝对坐标）
├── PostMessageBackend       ← 实验性：Win32 消息投递（窗口客户区坐标）
└── create_backend()         ← 工厂函数
```

**关键设计决策**：
- `PaletteNavigator` 和 `PaintEngine` 构造时接收 `InputBackend` 实例，不再直接导入具体函数
- 切换后端只需在 `auto_painter.py` 中改一行 `create_backend('postmessage', hwnd)` 即可
- PostMessage 后端标注为实验性：Unity 游戏对 PostMessage 鼠标消息的响应未经验证

### 4. 调色板标定简化（2026-03-07 重构新增）

#### 重构前
用户需要 **14 次 Enter**：2 次标签翻页点 + 10 次逐个色块点击 + 2 次画布角。

#### 重构后
用户只需 **6 次 Enter**（画布 2 次 + 调色板 4 次）：
1. 画布左上角 → 右下角（2 次，不变）
2. 标签最左可见组 → 标签最右可见组 → 色块区域左上角 → 色块区域右下角（4 次）

`PaletteNavigator` 根据已知的 **2 列 × 5 行** 布局自动从两个角点计算出 10 个色块的中心坐标。

### 5. 共享数据层 (`shared/`)

```
shared/
├── palette.py      ← 126 色唯一数据源（全项目共享）
└── pixel_data.py   ← PixelData 类：converter 输出 / painter 输入的 JSON 契约
```

painter 的 `config.py` 不再维护自己的 `COLOR_GROUPS`（96 行），改为从 `shared.palette` 薄封装导入。

### 遗留瓶颈：失去焦点的窗外悬空投递
目前的鼠标实体仍需移动接管用户桌面的物理指针。但如果系统出现特殊情况导致依然坐标越界，那么点击游戏外缘将导致焦点切屏。
这从根本上的最佳解法应不属于此宏观级别，未来应当使用类似 Win32 消息投递（`PostMessage` 并代入 `HWND`）机制去发送不占鼠标的后台内部相对坐标事件。

> **注**：`PostMessageBackend` 已在 `mouse_input.py` 中实现骨架代码，但需要实际测试心动小镇是否响应 PostMessage 的鼠标消息。
