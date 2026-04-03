"""
诊断脚本：测试 QFileDialog 在 onefile 环境下是否正常
"""
import sys
import os

# 在 onefile 模式下打印路径信息
print("=== PyInstaller 环境诊断 ===")
print(f"frozen: {getattr(sys, 'frozen', False)}")
print(f"MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
print(f"executable: {sys.executable}")
print(f"argv[0]: {sys.argv[0]}")
print(f"CWD: {os.getcwd()}")
print()

# 打印 DLL 搜索路径（Python 3.8+）
if hasattr(os, 'add_dll_directory'):
    print("DLL search dirs (via os.add_dll_directory):")
    # 这不会打印所有路径，但能确认函数存在
    print(f"  os.add_dll_directory: {os.add_dll_directory}")
print()

# 测试 PySide6 加载
print("=== PySide6 测试 ===")
try:
    from PySide6 import QtCore, QtWidgets, QtGui
    print(f"PySide6 loaded: Qt {QtCore.qVersion()}")
    print(f"libraryPaths: {QtCore.QCoreApplication.libraryPaths()}")
except Exception as e:
    print(f"PySide6 FAILED: {e}")
print()

# 测试 Qt 平台插件
print("=== Qt 平台插件 ===")
plugin_path = os.environ.get('QT_PLUGIN_PATH', 'NOT SET')
print(f"QT_PLUGIN_PATH: {plugin_path}")
platforms_dir = os.path.join(plugin_path, "platforms") if plugin_path != 'NOT SET' else None
if platforms_dir and os.path.isdir(platforms_dir):
    print(f"platforms dir exists: {platforms_dir}")
    for f in os.listdir(platforms_dir):
        print(f"  {f}")
else:
    print("platforms dir NOT FOUND")
print()

# 测试 QFileDialog
print("=== QFileDialog 测试 ===")
try:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        print("Created QApplication")
    else:
        print("Using existing QApplication")

    # 尝试非原生对话框（一定可以工作）
    print("Testing non-native dialog (QFileDialog.DontUseNativeDialog)...")
    path = QtWidgets.QFileDialog.getExistingDirectory(
        None, "测试-非原生", os.getcwd(),
        QtWidgets.QFileDialog.DontUseNativeDialog
    )
    print(f"Non-native dialog result: '{path}'")

    # 尝试原生对话框（这里会失败）
    print("Testing native dialog (QFileDialog.ShowDirsOnly)...")
    try:
        path2 = QtWidgets.QFileDialog.getExistingDirectory(
            None, "测试-原生", os.getcwd(),
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks
        )
        print(f"Native dialog result: '{path2}'")
    except Exception as e:
        print(f"Native dialog FAILED: {type(e).__name__}: {e}")

    print()
    print("=== 诊断完成 ===")

except Exception as e:
    import traceback
    print(f"QFileDialog test FAILED: {e}")
    traceback.print_exc()

input("按回车键退出...")
