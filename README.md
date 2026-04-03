# PDF 名册管理生成工具

基于文件目录结构管理和合并 PDF 的桌面工具。

## 功能特点

- 📁 **目录扫描**: 自动扫描工作目录下的所有 PDF 文件和子目录
- 🌳 **树形结构**: 可视化展示目录结构，支持拖拽排序
- 🏷️ **标签管理**: 导入/导出 XML 格式的 PDF 书签标签
- 🔗 **PDF 合并**: 按树结构顺序合并 PDF，自动生成嵌套书签
- 📄 **文件预览**: 查看 PDF 文件信息和元数据

## 系统要求

- Windows 10/11
- Python 3.8+

## 安装

### 开发环境运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行程序
python main.py
```

### 打包为独立可执行文件

```bash
# 使用 PyInstaller 打包
pyinstaller pdfmc.spec

# 生成的 exe 在 dist/ 目录下
```

## 使用说明

### 1. 选择工作目录

点击"选择工作目录"按钮，选择包含 PDF 文件的目录。程序会扫描该目录下的所有子目录和 PDF 文件。

### 2. 调整目录结构

- 拖拽节点调整顺序
- 右键菜单支持：
  - 全部展开/收起
  - 节点展开/收起
  - 重命名文件夹
  - 删除节点
  - 添加子文件夹

### 3. 导入/导出标签

- **导入标签**: 加载之前保存的 XML 标签文件
- **保存标签**: 将当前目录结构导出为 XML 格式

### 4. 合并 PDF

点击"开始合并"按钮，程序会按照树结构的顺序合并所有 PDF 文件，并生成对应的书签。

## 项目结构

```
pdfmc/
├── main.py                 # 程序入口
├── config.py              # 配置文件
├── requirements.txt       # 依赖列表
├── pdfmc.spec            # PyInstaller 打包配置
├── work/                 # 默认工作目录
├── output/               # 默认输出目录
└── src/
    ├── ui/
    │   ├── main_window.py      # 主窗口
    │   ├── tree_widget.py      # 树形组件
    │   ├── preview_widget.py   # 预览组件
    │   └── dialogs.py          # 对话框
    ├── core/
    │   ├── directory_scanner.py    # 目录扫描器
    │   ├── tree_manager.py         # 树管理器
    │   ├── pdf_merger.py           # PDF 合并器
    │   └── xml_handler.py          # XML 处理器
    └── utils/
        └── __init__.py
```

## XML 标签格式

```xml
<?xml version="1.0" encoding="UTF-8"?>
<pdf-outline version="1.0">
  <outline-item title="文件夹 1" path="D:/work/folder1" is-dir="true">
    <outline-item title="file1.pdf" path="D:/work/folder1/file1.pdf" is-dir="false"/>
    <outline-item title="file2.pdf" path="D:/work/folder1/file2.pdf" is-dir="false"/>
  </outline-item>
  <outline-item title="file3.pdf" path="D:/work/file3.pdf" is-dir="false"/>
</pdf-outline>
```

## 技术栈

- **GUI 框架**: PySide6
- **PDF 处理**: pypdf
- **XML 处理**: 内置 xml.etree.ElementTree
- **打包工具**: PyInstaller

## 许可证

MIT License
