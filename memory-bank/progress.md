# 进度记录

## 2026-03-07：图片转换器修复与增强

### 修复图片转换乱码问题
**根因**：
1. 颜色调色板完全错误（硬编码 48 种标准色 vs 游戏实际 126 色）
2. NumPy uint8 溢出导致颜色距离计算随机化
3. 缺少中心裁剪导致变形

**修复**：替换为真实游戏颜色、使用 int32 计算、添加中心裁剪和 EXIF 旋转处理。

### 添加图像处理高级选项
- **图像增强**：饱和度/对比度/锐度预处理，减少灰色调随机匹配
- **Floyd-Steinberg 抖动**：误差扩散算法，改善色阶过渡

### 同步真实调色板与 colorId
从游戏截图提取 126 色替换旧估计值，JSON 输出新增 `colorId` 字段实现绝对定位。

---

## 2026-03-07：提取共享调色板模块

### 问题
converter 和 painter 各自维护独立的颜色数据副本（converter 28 行 + painter 96 行），需人工同步。

### 改动
- 新建 `shared/palette.py`（唯一数据源）+ `shared/pixel_data.py`（JSON 契约）
- converter 删除内联颜色数据，改为 `from shared.palette import ...`
- painter `config.py` 从 96 行缩减到 ~40 行

---

## 2026-03-07：Painter 架构现代化重构

### 输入后端抽象化 (`mouse_input.py`)
- 旧版裸函数 → `InputBackend` ABC + `PynputBackend` / `PostMessageBackend`
- 所有下游模块通过接口调用

### 调色板标定简化 (`palette_navigator.py`)
- 14 次 Enter → 4 次（标签左右 + 色块左上右下）
- 自动计算 2×5 色块网格坐标

### 绘画引擎增强 (`paint_engine.py`)
- 新增断点续画（`paint_progress.json`）
- 新增 `load_pixel_data(PixelData)` 方法

### GUI 主程序重构 (`auto_painter.py`)
- `keyboard` → `pynput.keyboard.Listener`（无需管理员权限）
- `pyautogui` → `pynput.mouse.Controller`（统一坐标体系）
- 标定数据持久化到 `calibration.json`
- 新增断点续画按钮、网格尺寸校验

### 依赖清理
- 移除 `pyautogui`、`keyboard`
- 移除管理员提权批处理

---

## 2026-03-08：画布自动检测与 GUI 增强

### 新增自动检测画布功能 (`canvas_locator.py`)
- `detect_markers()` 静态方法：截图 → 检测红色标记点 → 自动标定四角
- GUI 新增「🔍 自动检测画布（4角标记点）」按钮

### 新增固定坐标功能 (`auto_painter.py`)
- 「📌 固定当前坐标」：保存画布/调色板相对于窗口的偏移到 `fixed_positions.json`
- 「⚡ 从窗口自动标定」：使用固定坐标 + 当前窗口位置一键标定
- 工具栏标定（画笔 + 油漆桶位置）

### 新增油漆桶填充优化 (`paint_engine.py`)
- 连通区域 ≥ 阈值时使用油漆桶填充
- GUI 开关 + 自动加载工具栏位置

### 新增测试标定功能
- 「🧪 测试标定（画边框）」：沿画布最外围画黑红交替边框验证准确性

### 新增微调偏移 UI
- X/Y 偏移 SpinBox（±20px），实时更新并自动保存

---

## 2026-03-08：修复画布自动检测误识别

### 问题
`detect_markers()` 旧逻辑先用背景色 `#feffff` 的 30% 行/列阈值找画布区域，再在内部找标记。当画布已画满内容时，背景色占比低于阈值，导致 UI 面板被误识别为画布（检测到 501×145 的区域，实际画布远大于此）。

### 修复
完全重写 `detect_markers()`：
1. **不再依赖背景色** — 直接在截图中搜索红色像素（R>180, G<80, B<80）
2. **BFS 连通分量聚类** — 纯 numpy 实现 `_connected_components()`，只遍历红色像素
3. **取最大 4 簇** — 按面积排序，取 top4 按几何位置分配四角
4. **限定搜索区域** — 只在水平居中 1200px 范围内搜索，排除两侧调色板 UI 的红色干扰

### 技术细节
- 无新依赖（不需要 scipy）
- BFS 优化：先 `np.where` 提取红色坐标到 set，只遍历非零像素
- 四角分配：先按 Y 分上下两组，每组内按 X 分左右
