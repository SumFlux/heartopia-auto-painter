## 2026-03-10：统一应用架构重构（Phase 1-3, 5）

### 重构目标
将 converter + painter + shared 收敛为单一 PySide6 桌面应用 `heartopia_app/`，四层架构（Domain / Application / Infrastructure / UI）。

### 已完成
1. **新包骨架** — `heartopia_app/` 目录结构，`python -m heartopia_app` 启动
2. **Domain 层迁移**
   - `palette.py` ← 从 `shared/palette.py` 迁移
   - `pixel_data.py` ← 从 `shared/pixel_data.py` 升级，新增 typed `Pixel` dataclass
   - `conversion.py` ← 从 `converter/heartopia_converter.py` 迁移，GUI 无关
   - `calibration.py` — 新建标定数据模型
   - `paint_plan.py` — 新建绘画计划模型
3. **Application 层** — `AppSettings` / `WorkspaceState` / `ConversionService`
4. **Infrastructure 层** — `paths.py`（统一 app-data 目录）、三个 Repository
5. **UI 层** — `MainWindow`（4 标签页）+ 4 个 Page
6. **Bootstrap** — DPI awareness、QApplication 初始化（提权/隐藏控制台默认关闭）

### 修复记录
- **Python 3.9 兼容** — 移除所有 `@dataclass(slots=True)`
- **提权闪退** — `ShellExecuteW` 参数修正为 `-m heartopia_app`；`request_admin_on_launch` / `auto_hide_console` 默认改为 `False`
- **转换卡住** — `ConvertPage` 调用 `result.preview_image()` / `result.stats()` 方法名不匹配，改为 `get_preview_image()` / `get_stats()`；给 `ConversionResult` 添加 `grid_width` / `grid_height` 属性和 `get_preview_image()` 方法
- **左侧面板挤压** — 控制面板加 `QScrollArea` 包裹，最小宽度 340px；窗口默认 1280×900

### 功能状态
| 功能 | 状态 |
|------|------|
| 图片转换（选图/参数/转换/预览/导出 JSON+CSV） | ✅ 完整 |
| 设置管理（保存/持久化） | ✅ 完整 |
| 标定页 UI | ✅ 框架就位 |
| 标定核心逻辑 | ❌ 待迁移 |
| 绘画页 UI | ✅ 框架就位 |
| 绘画核心逻辑 | ❌ 待迁移 |
| 旧入口退役 | ❌ 待完成 |

---



### 桶填充连通性修正 (`painter/paint_engine.py`)
- 按用户确认，将桶填充相关分析统一为 **4 连通**
- `_find_connected_components()` 改为 4 邻域 BFS
- `_classify_boundary_interior()` 改为 4 邻域边界判定
- `_find_4connected_subregions()` 保持 4 连通
- 结果：仅对角接触的像素会被视为两个区块，更符合游戏桶填充语义

### 调色板修正 (`shared/palette.py`)
- 用户手动重新截图校色后，更新多组颜色值
- 删除黑白灰组最后一个旧背景色 `#a8978e`
- 调色板总数从 **126 色** 改为 **125 色**
- 保留 `#feffff` 作为可绘制白色
- 为兼容旧 JSON，`CANVAS_BACKGROUND_COLORS` 仍保留 `#a8978e`，画画时会自动跳过
- 当前 `COLOR_GROUPS` 已无重复 hex

### README 分层整理
- 根 `README.md` 改为只保留项目概览、结构、快速开始、调色板总说明
- `converter/README.md` 聚焦转换参数、输出格式、125 色说明
- `painter/README.md` 聚焦当前真实 GUI 流程：4 角画布标定、调色板标定、固定坐标、工具栏、油漆桶、断点续画
- 修正旧文档中“画布 2 点标定”“126 色/组0有6色”等过时描述

---

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

---

## 2026-03-08：油漆桶填充优化修复

### 问题
油漆桶填充后画布出现大量空白区域。两个根因：
1. **连通分组使用 4-连通**：对角线相邻的同色像素被分为不同区域，导致边界不完整、油漆桶从对角缝隙漏出
2. **内部只点击一次油漆桶**：画完边界后，内部像素可能被边界分割成多个互不相连的"口袋"，只点一次只能填充一个口袋

### 修复 (`paint_engine.py`)
1. **8-连通 BFS 分组** — `_find_connected_components()` 从 4 方向扩展到 8 方向（含对角线），对角相邻的同色像素归入同一区域
2. **8-邻域边界判定** — `_classify_boundary_interior()` 检查 8 个邻居，只有全部是同色才算内部，确保边界完全密封无对角缝隙
3. **新增 `_find_4connected_subregions()`** — 对内部像素做 4-连通子区域分析（匹配游戏油漆桶的 4-连通填充行为），每个子区域各点击一次油漆桶
4. **阈值提高** — `BUCKET_FILL_MIN_AREA` 从 10 调整为 30，小区域直接逐点画更稳定

---

## 2026-03-08：修复颜色偏黄问题

### 问题
转换后的图像白色区域严重偏黄。原图纯白 `(255,255,255)` 被匹配到 `#f5e4cf`（暖黄色，橙色系 3-7），而非白色。

### 根因
1. **调色板数据错误**：黑白灰组 index 4 应为 `#feffff`（游戏内白色），实际被错误录入为 `#e0dbd9`（暖灰色）
2. **白色被排除**：`#feffff` 被放入 `CANVAS_BACKGROUND_COLORS`，导致白色像素永远不会被绘制。实际上 `#feffff` 是游戏调色板中可绘制的白色，画布背景是条纹图案非纯白

### 修复 (`shared/palette.py`)
1. 黑白灰组 index 4：`#e0dbd9` → `#feffff`
2. `CANVAS_BACKGROUND_COLORS` 移除 `#feffff`，白色现在可正常绘制

---

## 2026-03-08：画布配置按比例存储 + 进度预估 + 绘画计时日志

### 画布配置按比例绑定 (`auto_painter.py`, `fixed_positions.json`)
- `fixed_positions.json` 结构变更：`canvas` → `canvas_profiles`（dict，key 为比例字符串如 `"3:4"`、`"1:1"`）
- `palette` 和 `toolbar` 保持顶层共享（不随比例变化）
- 导入 JSON 时自动根据比例匹配已保存的画布配置并应用
- 保存固定坐标时按当前比例存入对应 key，保留其他比例的配置
- 手动「从窗口自动标定」按钮也按比例查找配置
- 兼容旧格式：检测到旧 `canvas` 字段时自动迁移

### 进度条预估剩余时间
- `_on_progress()` 根据已用时间和已画像素计算速度，推算剩余时间
- 显示格式：`当前进度: 1234/5678 — 预估剩余: 12分30秒`

### 绘画计时日志
- 开始绘画时记录：`[HH:MM:SS] 开始绘画`
- 结束绘画时记录：`[HH:MM:SS] 结束绘画 — 用时: XX分XX秒`

---

## 2026-03-08：工具栏标定显式化 + 延迟抖动 + 进度条美化

### 工具栏标定按钮 (`auto_painter.py`)
- 新增「🔧 标定工具栏（画笔+油漆桶）」按钮放在标定区域，不再隐藏在保存固定坐标流程中
- 删除旧的 `_prompt_toolbar_calibration()` 弹窗询问方式

### 延迟随机抖动 (`paint_engine.py`)
- 新增 `_jittered_delay()` 方法：在基础延迟上加 ±25% 随机波动
- 如 20ms 基础延迟实际随机在 15~25ms 之间，防止游戏检测固定间隔脚本操作
- 所有绘画延迟点统一使用此方法

### 进度条美化
- 进度条已完成部分为绿色 (`#4CAF50`)
- 进度数字后添加"色块"后缀：`当前进度: 1234/5678 色块 — 预估剩余: 12分30秒`
