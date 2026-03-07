# Heartopia Auto Painter

心动小镇自动画画工具 - 将图片转换为像素画并自动在游戏中绘制

## 项目简介

这个项目基于 [Heartopia Painting Tools](https://github.com/zerochansy/Heartopia-Painting-Tools) 开发，提供两个核心功能：

1. **图片转换器** - 将任意图片转换为心动小镇游戏像素画矩阵
2. **自动画画脚本**（开发中）- 根据像素矩阵自动在游戏中绘制

## 项目结构

```
heartopia-auto-painter/
├── converter/              # 图片转换器
│   ├── heartopia_converter.py  # 核心转换逻辑
│   ├── gui.py                  # GUI 图形界面
│   ├── requirements.txt
│   └── README.md
├── painter/               # 自动画画脚本（开发中）
│   └── (待开发)
├── examples/              # 示例图片和输出
│   └── (待添加)
└── README.md
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/SumFlux/heartopia-auto-painter.git
cd heartopia-auto-painter
```

### 2. 安装依赖

```bash
cd converter
pip install -r requirements.txt

# 如需 GUI 界面
pip install PySide6
```

### 3. 转换图片

```bash
# 命令行方式
python heartopia_converter.py your_image.jpg

# GUI 方式
python gui.py
```

## 功能特性

### 图片转换器

- ✅ 支持 5 种画布比例（16:9, 4:3, 1:1, 3:4, 9:16）
- ✅ 支持 4 个精细度等级（30x30 到 150x150）
- ✅ 使用心动小镇游戏原生颜色（13 组 125 色）
- ✅ 自动中心裁剪适应目标比例
- ✅ 自动处理手机照片 EXIF 旋转
- ✅ 导出 JSON 和 CSV 格式
- ✅ GUI 图形界面（实时预览）

### 自动画画脚本（开发中）

- ⏳ 自动标定游戏画布
- ⏳ 自动选择颜色
- ⏳ 自动点击绘制
- ⏳ 支持暂停/继续
- ⏳ 防检测随机化

## 使用文档

详细使用说明请查看各模块的 README：

- [图片转换器使用说明](./converter/README.md)
- [自动画画脚本使用说明](./painter/README.md)（开发中）

## 技术栈

- **Python 3.8+**
- **Pillow** - 图片处理
- **NumPy** - 数值计算
- **PySide6**（可选）- GUI 界面
- **PyAutoGUI**（计划中）- 自动化操作

## 开发计划

- [x] 图片转换器
- [x] GUI 界面
- [ ] 自动画画脚本
- [ ] 批量处理
- [ ] 颜色优化算法

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 致谢

- [Heartopia Painting Tools](https://github.com/zerochansy/Heartopia-Painting-Tools) - 原始项目（颜色数据来源）
- 心动小镇游戏开发团队

## 联系方式

- GitHub: [@SumFlux](https://github.com/SumFlux)
- 项目主页: https://github.com/SumFlux/heartopia-auto-painter

---

**免责声明**：本工具仅供学习和研究使用，请遵守游戏规则，不要用于作弊或破坏游戏平衡。
