# -*- coding: utf-8 -*-
"""
PyInstaller 运行时钩子
"""
import sys
import os
from pathlib import Path

# ============ 0. 强制 _internal 在 sys.path 最前端（解决包导入优先级问题）============
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _internal = sys._MEIPASS
    # 从 sys.path 中移除 _internal（如果已在其中）
    while _internal in sys.path:
        sys.path.remove(_internal)
    # 插入到最前面，确保 bundled 包优先于系统 site-packages
    sys.path.insert(0, _internal)

# ============ 1. Windows DLL 搜索路径（Python 3.8+ 必须）============
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    candidates = []
    # onefile: exe 同目录；onedir: exe 同目录（包含 _internal/）
    exe_dir = os.path.dirname(sys.executable)
    candidates.append(exe_dir)
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass and meipass != exe_dir:
            candidates.append(meipass)
    # 开发环境
    for p in sys.path:
        if p and os.path.isfile(os.path.join(p, "python311.dll")):
            candidates.append(p)
    added = set()
    for d in candidates:
        if d and d not in added and os.path.isdir(d):
            try:
                os.add_dll_directory(d)
                added.add(d)
            except Exception:
                pass

# ============ 2. Windows COM 初始化（SHBrowseForFolder 需要）============
if sys.platform == "win32":
    try:
        import ctypes
        ole32 = ctypes.WinDLL("ole32")
        ole32.OleInitialize(None)
    except Exception:
        pass

# ============ 3. Qt 插件路径 ============================================
# onedir: exe 在 dist/pdfmc/，_internal 在 dist/pdfmc/_internal/（sys._MEIPASS=_internal）
# onefile: sys._MEIPASS 指向资源解压目录
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    meipass = sys._MEIPASS
    # 判断是 onedir 还是 onefile：onedir 时 _MEIPASS 含 _internal 子目录
    if os.path.basename(meipass) == "_internal":
        # onedir: exe_dir = _internal 的父目录
        exe_dir = os.path.dirname(meipass)
        bundle_dir = meipass  # _internal 就是资源根目录
    else:
        # onefile: exe_dir = exe 所在目录
        exe_dir = os.path.dirname(sys.executable)
        bundle_dir = meipass
else:
    exe_dir = os.path.dirname(os.path.abspath(__file__))
    bundle_dir = exe_dir

# PySide6 插件路径
_internal = os.path.join(exe_dir, "_internal")
plugin_path_internal = os.path.join(_internal, "PySide6", "plugins")
plugin_path_flat = os.path.join(bundle_dir, "PySide6", "plugins")

if os.path.isdir(plugin_path_internal):
    plugin_path = plugin_path_internal
elif os.path.isdir(plugin_path_flat):
    plugin_path = plugin_path_flat
else:
    plugin_path = None

if plugin_path:
    os.environ['QT_PLUGIN_PATH'] = plugin_path
    try:
        from PySide6 import QtCore
        QtCore.QCoreApplication.setLibraryPaths([plugin_path])
    except Exception:
        pass
