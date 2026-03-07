# 进度记录

## 2026-03-07：修复图片转换乱码问题

### 问题描述
图片转换后的预览图显示为完全乱码（随机噪点），无法辨认原图内容。

### 根因分析
经过对原工程 [zerochansy/Heartopia-Painting-Tools](https://github.com/zerochansy/Heartopia-Painting-Tools) 的完整代码对比，发现三个问题：

1. **颜色调色板完全错误**：原先硬编码了 48 种标准色（如纯红 `#FF0000`、纯蓝 `#0000FF`），与游戏实际颜色截然不同。原工程从 `color.svg` 中提取了 13 组共 125 种经过精心调配的游戏内颜色。
2. **NumPy uint8 溢出**（核心 Bug）：PIL 图片转 numpy 数组默认是 `uint8` 类型，在颜色距离计算中做减法时会溢出。例如 `np.uint8(50) - 200 = 216`（正确值应为 -40），导致颜色匹配变为随机结果。
3. **缺少中心裁剪**：原工程在处理图片时会先按目标比例做中心裁剪再缩放，我们直接拉伸导致变形。

### 修复内容

#### `heartopia_converter.py` — 核心转换器（重构）
- 替换为从原工程 `color.svg` 中提取的 125 种真实游戏颜色
- 使用 `int32` 类型读取图像数组，距离计算使用 Python 原生 `int`，彻底解决 uint8 溢出
- 添加 `_center_crop()` 方法，按目标比例中心裁剪图片
- 添加 EXIF 旋转处理（解决手机照片方向问题）
- 预计算调色板 RGB 值，使用平方距离代替 `sqrt` 提升性能
- 新增 `get_preview_image()` 和 `get_stats()` 方法供 GUI 使用

#### `gui.py` — GUI 界面（重构）
- 使用 converter 提供的 `get_preview_image()` 统一生成预览
- 通过 numpy 数组直接创建 QImage，避免 `setPixel` 格式问题
- 动态计算预览缩放比以适应窗口
- 统计信息通过 `get_stats()` 方法获取

### 验证结果
- 30×30 测试转换使用了 46 种颜色（修复前错误使用全部 125 种）
- 主要颜色为浅橙色 `#fece92`（16.2%）和红色 `#a6263d`（10.2%），与原图内容吻合
- 预览图清晰可辨认原图主体（麦当劳公仔和薯条）

### 2026-03-07：添加图像处理高级选项（增强与抖动）

#### 问题描述
修复颜色匹配后，虽然颜色提取准确，但因为使用的是“最近邻颜色匹配”（Nearest Neighbor），颜色过渡区域缺少混合，导致出现成块的“脏”色感。

#### 解决方案与改动
为转换器和 GUI 增加两个高级图像处理选项，以彻底改善像素画的观感和细节：

1. **图像增强（预处理）**
   - **原理**：在缩小和量化图像前，使用 PIL `ImageEnhance` 提升图像的饱和度（默认 1.3）、对比度（默认 1.2）和锐度（默认 1.3），使得主体颜色更鲜明，减少灰色调或中间混合色的随机匹配。
   - **改动**：在 `heartopia_converter.py` 的 `process_image` 中插入 `_enhance_image` 方法；在 GUI 中增添 QCheckBox 以及三个直观联动的 QSlider 和“恢复默认”按钮，允许手动微调增强参数。

2. **抖动模式（Floyd-Steinberg 误差扩散）**
   - **原理**：将当前像素量化后产生的颜色误差，按 7/16、3/16、5/16、1/16 的权重“扩散”给右侧和下方的 4 个相邻像素。这种光学混合效果能大幅改善色阶断层，让颜色过渡变得非常平滑自然。
   - **改动**：在核心转换器中新增 `_quantize_dither` 方法，并在计算误差时使用 `float32` 数组以正确累积正负误差，避免整数截断问题。在 GUI 中暴露此选项。

#### 结论
通过以上改动，用户可选择更鲜艳（增强）或更自然平缓（抖动）的像素输出效果，解决了色块“脏点”问题。

### 2026-03-07：同步真实调色板与新增专属 colorId

#### 问题描述
转换器的预置 125 色与游戏实际截图的色卡由于环境不同出现颜色数值误差，导致依靠 HEX 获取组别和颜色位置以控制自动画板切换时频繁报错”未知的颜色”。

#### 解决方案与改动
1. **统一调色板数据**：使用提取脚本直接从游戏调色板截图中提取所有的 126 个特征颜色（组 1 为 6 色，组 2-13 各 10 色），替换掉了 `HEARTOPIA_COLORS` 中旧的估计色值。
2. **生成独占定位 ID**：由于单纯获取最相近颜色依然会存在兼容性问题，转换器现在会在解析图像并在匹配完成后，在生成的 `pixels` JSON 列表中，给每一个字典自带计算好的 `colorId`（格式如 `”1-0”` 即对应游戏画板第二排第一格）。画笔程序将完全依靠此绝对位置去点击颜色，避开任何匹配失误。

### 2026-03-07：提取共享调色板模块，消除重复数据源

#### 问题描述
converter 和 painter 各自维护了一份独立的颜色数据（converter 的 `HEARTOPIA_COLORS` 28 行 + painter 的 `COLOR_GROUPS` 96 行）。两份数据需要人工同步，且 converter 内部自行实现了 `_hex_to_rgb`、`_rgb_to_hex` 等辅助函数，与 painter 的 `config.py` 中的同名函数重复。

#### 改动内容

##### 新建 `shared/palette.py`（唯一调色板数据源）
- 集中定义 `COLOR_GROUPS`（13 组，126 色）、`FLAT_COLORS`（一维列表）
- 自动构建派生数据：`COLOR_ID_MAP`、`HEX_TO_GROUP`、`PALETTE_RGB`
- 提供公共工具函数：`hex_to_rgb`、`find_closest_color`、`get_closest_color_group`
- 定义 `CANVAS_BACKGROUND_COLORS`（画布背景色集合）

##### 新建 `shared/pixel_data.py`（JSON 读写契约）
- `PixelData` 类封装了 converter 导出 / painter 导入的 JSON 格式
- 内置字段校验（`gridWidth`、`gridHeight`、`pixels` 必须存在且合法）
- 修复了旧代码中 painter 用 `len(pixels)` 当高度而非读取 `gridHeight` 的维度 bug

##### 重构 `heartopia_converter.py`
- **删除**：`HEARTOPIA_COLORS` 硬编码列表（28 行）
- **删除**：`_hex_to_rgb`、`_rgb_to_hex` 静态方法
- **删除**：`__init__` 中手动构建 `_palette_rgb` 和 `_hex_to_id` 的代码
- **改为**：`from shared.palette import PALETTE_RGB, COLOR_ID_MAP, hex_to_rgb, find_closest_color`
- `_find_closest_color` 简化为调用 `find_closest_color(r, g, b)` 取 hex 返回
- `export_json` 中 `self._hex_to_id.get` 改为 `COLOR_ID_MAP.get`

##### 修改 `gui.py`
- 添加 `sys.path.insert(0, 项目根目录)` 以支持 `from shared.xxx` 导入

#### 验证结果
- 所有 11 个 Python 文件语法检查通过
- `shared.palette` 模块功能测试通过：126 色、COLOR_ID_MAP 映射、find_closest_color 匹配
- converter 导入链正常工作，HeartopiaPixelArt 初始化和颜色匹配行为不变

