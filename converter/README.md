# Heartopia 像素画转换器

将图片转换为心动小镇游戏像素画矩阵。

## 功能

- 支持 5 种画布比例（16:9, 4:3, 1:1, 3:4, 9:16）
- 支持 4 个精细度等级（Level 0-3）
- 使用心动小镇游戏原生颜色
- 导出 JSON 和 CSV 格式

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
python heartopia_converter.py image.jpg
```

默认使用 1:1 比例，Level 2 精细度（100x100 网格）

### 指定比例和精细度

```bash
python heartopia_converter.py image.jpg 1:1 2
```

### 参数说明

- **比例**：
  - `16:9` - 宽屏（30x18, 50x28, 100x56, 150x84）
  - `4:3` - 标准（30x24, 50x38, 100x76, 150x114）
  - `1:1` - 正方形（30x30, 50x50, 100x100, 150x150）
  - `3:4` - 竖屏（24x30, 38x50, 76x100, 114x150）
  - `9:16` - 手机竖屏（18x30, 28x50, 56x100, 84x150）

- **精细度**：
  - `0` - 最低（最小网格）
  - `1` - 低
  - `2` - 中（推荐）
  - `3` - 高（最大网格）

## 输出文件

### JSON 格式

```json
{
  "ratio": "1:1",
  "level": 2,
  "gridWidth": 100,
  "gridHeight": 100,
  "totalPixels": 8523,
  "colorCount": 45,
  "colors": {
    "#FF0000": 234,
    "#00FF00": 189
  },
  "pixels": [
    {"x": 0, "y": 0, "color": "#FF5733"},
    {"x": 1, "y": 0, "color": "#33FF57"}
  ]
}
```

### CSV 格式

```csv
x,y,color
0,0,#FF5733
1,0,#33FF57
```

## 示例

```bash
# 生成 100x100 的正方形像素画
python heartopia_converter.py photo.jpg 1:1 2

# 生成 150x150 的高精细度像素画
python heartopia_converter.py photo.jpg 1:1 3

# 生成 100x56 的宽屏像素画
python heartopia_converter.py photo.jpg 16:9 2
```

## 输出说明

- `image_heartopia.json` - 像素数据（用于自动画画脚本）
- `image_heartopia.csv` - CSV 格式（方便 Excel 查看）
- 控制台会显示 ASCII 预览和统计信息

## 注意事项

- 图片会自动调整到指定的网格尺寸
- 颜色会自动匹配到游戏原生颜色
- 白色（#FFFFFF）表示空白，不会导出到像素列表中
