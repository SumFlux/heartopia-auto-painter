# Heartopia 像素画转换器

将图片转换为心动小镇像素画矩阵，供 [自动画画脚本](../painter/README.md) 使用。

## 功能

- 5 种画布比例（`16:9`、`4:3`、`1:1`、`3:4`、`9:16`）
- 4 个精细度等级（Level 0–3）
- 基于游戏调色板的最近邻量化
- Floyd-Steinberg 抖动（可选）
- 图像增强（饱和度 / 对比度 / 锐度）
- 自动中心裁剪
- 自动处理 EXIF 旋转
- 导出 JSON（含 `colorId`）和 CSV
- GUI 实时预览

## 安装

```bash
pip install -r requirements.txt
```

依赖主要包括：Pillow、NumPy、PySide6。

## 使用方法

### GUI（推荐）

```bash
python gui.py
```

流程：

1. 点击「导入图片」
2. 选择画布比例和精细度
3. 视需要开启「图像增强」和「抖动模式」
4. 预览结果
5. 导出 JSON 或 CSV

### 命令行

```bash
python heartopia_converter.py image.jpg
python heartopia_converter.py image.jpg 1:1 3
python heartopia_converter.py image.jpg 16:9 2 -o output.json
```

## 画布比例与网格尺寸

| 比例 | Level 0 | Level 1 | Level 2 | Level 3 |
|:----:|:-------:|:-------:|:-------:|:-------:|
| 16:9 | 30×18 | 50×28 | 100×56 | 150×84 |
| 4:3 | 30×24 | 50×38 | 100×76 | 150×114 |
| 1:1 | 30×30 | 50×50 | 100×100 | 150×150 |
| 3:4 | 24×30 | 38×50 | 76×100 | 114×150 |
| 9:16 | 18×30 | 28×50 | 56×100 | 84×150 |

## 图像增强参数

| 参数 | 默认值 | 说明 |
|------|:------:|------|
| 饱和度 | 1.3 | >1 更鲜艳，<1 更灰 |
| 对比度 | 1.2 | >1 更分明，<1 更柔和 |
| 锐度 | 1.3 | >1 更锐利，<1 更模糊 |

## 输出格式

### JSON

```json
{
  "ratio": "1:1",
  "level": 2,
  "gridWidth": 100,
  "gridHeight": 100,
  "totalPixels": 8523,
  "colorCount": 45,
  "colors": {
    "#fece92": 234,
    "#a6263d": 189
  },
  "pixels": [
    {"x": 0, "y": 0, "color": "#fece92", "colorId": "3-3"},
    {"x": 1, "y": 0, "color": "#cf354d", "colorId": "1-0"}
  ]
}
```

### CSV

```csv
x,y,color
0,0,#fece92
1,0,#cf354d
```

## 关键字段

| 字段 | 说明 |
|------|------|
| `gridWidth` / `gridHeight` | 像素矩阵尺寸 |
| `totalPixels` | 导出像素总数 |
| `color` | 匹配到的调色板颜色 |
| `colorId` | 调色板定位标识，格式为 `组号-组内索引` |

> `colorId` 是画画器优先使用的精确定位信息。

## 调色板说明

调色板统一定义在 `shared/palette.py`：

- 共 13 组
- 第 0 组（黑白灰）为 **5 色**
- 第 1–12 组各 10 色
- 当前总计 **125 色**

补充说明：
- `#feffff` 为可用白色
- 旧背景色 `#a8978e` 已从调色板中移除，不会再被新生成数据使用
- 旧数据如果仍包含 `#a8978e`，画画器会把它当作背景跳过

## 注意事项

- 图片会先按目标比例中心裁剪，再缩放到网格尺寸
- 抖动会让过渡更自然，但通常会增加颜色种类数
- 增强在低精细度下通常更明显
- 如果 JSON 中包含 `colorId`，后续画画时会优先按 `colorId` 精确定位

## 相关文档

- 项目总览：[`../README.md`](../README.md)
- 自动画画：[`../painter/README.md`](../painter/README.md)