"""
PDF 名册管理生成工具 - 配置文件
"""
import os
from pathlib import Path

# 程序根目录
BASE_DIR = Path(__file__).parent.resolve()

# 默认工作目录
DEFAULT_WORK_DIR = BASE_DIR / "work"

# 默认输出目录
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"

# 程序标题
APP_TITLE = "PDF 名册管理生成工具"

# 版本信息
APP_VERSION = "1.7"
APP_AUTHOR = "李中杰"
APP_DATE = "2026.4.4"

# 窗口大小
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

# 支持的文件类型
SUPPORTED_FILES = [".pdf"]

# XML 标签文件扩展名
XML_EXTENSION = ".xml"
