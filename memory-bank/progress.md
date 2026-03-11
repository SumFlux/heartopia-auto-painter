## 2026-03-11：截图验证改为手动按钮 + 画板区域预览 + 调色板归位时序修正

### 背景
原先的“画后截图验证 + 保守自动补画”第一版仍带有较强自动流程色彩，而且手动点击截图验证时会阻塞 UI；同时验证预览显示整张窗口，不利于人工只看画板区域。另一个实际使用问题是调色板从最后几页归位到第一页时，左翻页点击间隔太短，游戏来不及翻页，导致归位停在中间页。

### 改动

#### 1. PaintPage 改为纯手动验证/补画流程（`heartopia_app/ui/pages/paint_page.py`）
- 移除主绘制完成后的自动验证、自动补画、补后自动终验主链路
- 新增两个独立按钮：
  - `截图验证`
  - `补画白点`
- 主绘制完成后恢复为普通完成提示；是否验证、是否补画完全由用户手动决定

#### 2. 验证结果缓存 + UI 预览区
- 在 Paint 页新增“验证预览”区域，复用 `QScrollArea + QLabel` 模式显示验证图
- 缓存最近一次 `VerificationResult` 与预览图，仅当存在最近一次有效验证且包含 `missing_background_like` 候选时才允许点击“补画白点”
- 当重新导入 JSON、开始新一轮主绘制/断点续画、或关键标定上下文变化时，会清空旧验证缓存，避免旧结果误用于新画面

#### 3. 新增验证标记图（`heartopia_app/application/post_paint_verifier.py`）
- 新增 `build_annotated_verification_image()`
- 在截图上直接叠加 mismatch 标记：
  - `missing_background_like`：红色
  - `wrong_palette_color`：橙色
  - `uncertain`：黄色
- 标记以逻辑格采样中心为基础绘制小框和十字，优先保证人工可读性

#### 4. 截图验证改为后台线程执行（`heartopia_app/ui/pages/paint_page.py`）
- 新增 `VerificationThread(QThread)`
- 点击 `截图验证` 后，不再在 UI 主线程直接执行窗口查找、截图、采样和标记图生成
- 修复“点击截图验证后窗口未响应”的问题

#### 5. 验证预览只显示画板区域（方案 A）
- 验证采样仍然基于整张游戏窗口截图，不改变验证逻辑
- 但验证完成后会根据当前 `CanvasCalibration` 四角坐标，取画板的最小外接矩形
- 预览区只显示裁剪后的画板区域标记图，更方便人工检查漏点

#### 6. 补画流程保持保守策略
- “补画白点”只消费最近一次验证结果中的 `repair_candidates`
- repair pass 继续强制：
  - `very_slow`
  - `brush-only`
  - `no bucket`
- 为了验证是否存在轻微坐标偏差，repair-only 路径新增 **九宫格补点**：每个 repair candidate 会按中心 + 八邻域共 9 个点点击一次
- 主绘制逻辑保持不变，九宫格补点只作用于 repair pass
- repair 完成后不自动再验证，只提示用户可按需再次截图验证
- repair pass 停止时仍不会覆盖主绘制断点

#### 7. Paint 页改为左右布局（`heartopia_app/ui/pages/paint_page.py`）
- 参考 Convert 页，把 Paint 页从上下堆叠改成左右分栏
- 左侧放：数据导入、绘画控制、进度、日志
- 右侧放：验证预览摘要 + 验证图片
- 总窗口宽度保持主窗口原配置不变，仅调整页面内部布局

#### 8. 调色板归位时序修正（`heartopia_app/application/paint_session.py`）
- `_reset_palette()` 中每次点击左翻页后的等待时间：`0.1s -> 0.4s`
- 归位完成后的最终等待保持 `0.6s`
- 目的是让游戏 UI 有足够时间真正翻页，避免从最后一页回到第一页时停在中间页

### 验证
- `paint_page.py` / `post_paint_verifier.py` / `paint_session.py` 均通过 IDE diagnostics
- 针对上述文件执行 `python -m compileall` 通过

---

## 2026-03-11：画后截图验证 + 保守自动补画闭环（V1）

### 背景
正式绘制已经基本稳定，但仍会偶发少量“漏几个白点 / 未填满的小缺口”。继续只调点击偏移收益下降，因此新增“画后校验 + 保守补画”的闭环：主绘制完成后截图，按当前标定重建逻辑网格，与目标 JSON 对比；V1 只识别并修复“目标应有颜色、实际看起来像背景/漏白点”的像素，不自动纠正任意错色。

### 改动

#### 1. 新增纯逻辑验证模块（`heartopia_app/application/post_paint_verifier.py`）
- 新增 `verify_painted_canvas()`：
  - 对每个逻辑格调用 `CanvasCalibration.get_screen_pos()` 取样
  - 使用小邻域采样（默认 3x3）而非整图 resize/quantize
  - 对采样结果做中位数 / 多数投票，重建“观察到的逻辑网格”
- 新增 `VerificationResult` / `VerificationMismatch` 数据结构
- mismatch 分类分为：
  - `missing_background_like`
  - `wrong_palette_color`
  - `uncertain`
- 新增 `build_repair_pixel_data()`：仅根据保守 repair candidates 构造 repair-only 的 `PixelData`

#### 2. 窗口截图接口补充（`heartopia_app/infrastructure/window_backend.py`）
- 新增 `capture_window_with_rect()`，一次返回截图和窗口客户区矩形，避免页面层重复查 rect

#### 3. PaintSession 增加显式 bucket 开关（`heartopia_app/application/paint_session.py`）
- 新增 `use_bucket_fill` 字段和 `set_bucket_fill_enabled()`
- 主循环中的 bucket 模式从“只看 toolbar 是否标定”改为“UI 开关 + toolbar 已标定”共同决定
- 顺手修复了一个旧问题：此前 `PaintPage` 上的“油漆桶填充”复选框实际上没有真正控制 `PaintSession`

#### 4. PaintPage 接管完整状态机（`heartopia_app/ui/pages/paint_page.py`）
- 新增两个开关：
  - `完成后截图验证`
  - `发现漏白点后自动补画（实验）`
- 新增 `_PaintRunContext`，区分主绘制 / repair pass
- 主绘制完成后不再立刻弹完成，而是：
  1. 可选截图验证
  2. 输出 mismatch 摘要和前若干条明细日志
  3. 若启用自动补画且存在 repair candidates，则启动 repair pass
  4. repair pass 完成后可选再做一次最终验证
  5. 最后再清 session / 弹完成提示
- 增加“绘画成功但后处理失败”的告警路径：验证/补画失败时，不把整次绘画误报成失败

#### 5. Repair pass 约束
- repair pass 强制：
  - `click-only`
  - `brush-only`
  - `very_slow`
  - 只执行一轮
- 停止 repair pass 时不会覆盖主绘制断点，避免把小补画进度误存成正式断点

### 保守策略（V1）
- 仅 `missing_background_like` 进入自动补画候选
- `wrong_palette_color` 和 `uncertain` 只统计、只记日志，不自动纠正
- 对目标本身是白色 / 极浅色的格子，默认排除自动补画，避免把“画对的白色”误判为漏白点

### 验证
- `python -m compileall heartopia_app` 通过
- `python -m py_compile` 针对本次改动文件通过
- IDE diagnostics 未报告本次修改文件的错误

---

## 2026-03-11：绘制策略回退 — 全面禁用拖动，改为纯点击 + 桶填充左偏补偿

### 背景
拖动绘制在边框测试中有效，但迁移到正式绘制后，bucket boundary 的 snake_sort 点序不是连续轮廓，拖动无法保证封闭，导致桶填外溢。经多轮迭代后决定全面回退为纯点击。

### 改动（`heartopia_app/application/paint_session.py`）
1. **全面禁用 drag** — 所有绘制路径不再调用 `drag_path`，恢复逐点 click
2. **桶填充左偏双击** — bucket 模式下每次桶工具点击前先点 `(x-1, y)` 再点 `(x, y)`
3. **ring 像素补画** — `shrink_interior_away_from_boundary` 缩掉的那圈像素用 brush 补画，修复进度只到 87% 就显示完成的 bug
4. **小子区域改用 brush** — safe_interior 中 <4 像素的子区域改用 brush 逐点 click，修复桶工具对极小区域不生效的问题
5. 新增 `_click_points()` 通用点击辅助方法，返回 `(stopped, painted_count)` 支持 resume offset

### 遗留
- `CalibrationService.test_border()` 仍使用拖动（drag_path），后续需改为纯 click 并彻底删除 drag 相关代码

---

## 2026-03-10：Phase 4 补丁 — 4 个 Bug / 功能改进

### 问题 1: 标定按比例存储
- `calibration_page.py`: 固定坐标 GroupBox 新增比例 `QComboBox`（16:9 / 4:3 / 1:1 / 3:4 / 9:16）
- `_save_fixed_positions()`: `canvas` → `canvas_profiles[ratio]`，保留其他比例配置
- `_apply_fixed_positions()`: 优先从 `canvas_profiles[ratio]` 查找，兼容旧 `canvas` 格式
- `paint_page.py`: `_import_json()` 成功后自动尝试应用匹配比例的固定坐标

### 问题 2: 油漆桶连通性 Bug
- `paint_algorithms.py`: `find_connected_components()` 4-连通 → 8-连通（含对角线）
- `classify_boundary_interior()` 4-邻域 → 8-邻域
- `find_4connected_subregions()` 保持 4-连通不变（匹配游戏桶填充语义）

### 问题 3: 测试标定简化 + 加速 + 热键中断
- `calibration_service.py`: `test_border()` 改为只用黑色通刷，点击间隔 0.03s → 0.015s
- `calibration_page.py`: 测试标定期间启动 pynput keyboard listener 监听 F7 中断

### 问题 4: 断点续画手动指定起始点
- `paint_session.py`: `PaintProgress` 新增 `from_pixel_offset(plan, pixel_offset)` classmethod
- `paint_page.py`: 断点续画按钮旁新增 `QSpinBox`（范围 0 ~ total_pixels），支持手动输入起始像素

---

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
| 标定页 UI + 核心逻辑 | ✅ 完整（含 F7 中断、比例存储、网格同步） |
| 绘画页 UI + 核心逻辑 | ✅ 完整（含断点续画、油漆桶、手动起点） |
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
