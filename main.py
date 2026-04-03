"""
PDF 名册管理生成工具 - 程序入口
"""
import sys
import os
from pathlib import Path

# ============ 诊断：打印环境信息 ============
def _print_diag():
    print("=== PDFMC 启动诊断 ===", flush=True)
    print(f"frozen={getattr(sys,'frozen',False)}", flush=True)
    print(f"MEIPASS={getattr(sys,'_MEIPASS','N/A')}", flush=True)
    print(f"executable={sys.executable}", flush=True)
    print(f"QT_PLUGIN_PATH={os.environ.get('QT_PLUGIN_PATH','NOT SET')}", flush=True)
    try:
        from PySide6 import QtCore
        print(f"Qt version={QtCore.qVersion()}  libraryPaths={QtCore.QCoreApplication.libraryPaths()}", flush=True)
    except Exception as e:
        print(f"PySide6 import FAILED: {e}", flush=True)
    print("=" * 40, flush=True)

if getattr(sys, 'frozen', False):
    _print_diag()
# ==========================================

# 添加项目根目录到路径
current_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow
from config import APP_TITLE, DEFAULT_WORK_DIR, DEFAULT_OUTPUT_DIR


def ensure_directories():
    """确保默认目录存在"""
    DEFAULT_WORK_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    """主函数"""
    # 确保目录存在
    ensure_directories()

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyle('Fusion')

    # 设置全局样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QFrame {
            background-color: white;
        }
    """)

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 运行应用
    try:
        sys.exit(app.exec())
    except SystemExit:
        # 清理资源
        window.close()
        del window
        del app


if __name__ == '__main__':
    main()
