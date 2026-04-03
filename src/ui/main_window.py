"""
主窗口 - 程序主界面
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QFrame, QStatusBar, QApplication
)
from PySide6.QtCore import Qt, QSize, QSettings
from PySide6.QtGui import QFont

import sys
import os
from pathlib import Path
from typing import Optional

# 仅在非打包环境下添加父目录到路径
# 打包后（frozen=True）rthook.py 已正确设置 sys.path
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import (
    APP_TITLE, APP_VERSION, APP_AUTHOR, APP_DATE,
    WINDOW_WIDTH, WINDOW_HEIGHT, DEFAULT_WORK_DIR, DEFAULT_OUTPUT_DIR
)
from src.core.directory_scanner import scan_directory
from src.core.tree_manager import TreeManager
from src.core.pdf_merger import merge_pdfs, PDFMerger
from src.core.pdf_splitter import split_pdf
from src.core.pdf_page_splitter import split_pdf_to_single_pages
from src.core.xml_handler import export_to_xml, import_from_xml, validate_xml, XMLHandler, items_to_tree_items
from src.ui.tree_widget import TreeWidget
from src.ui.preview_widget import PreviewWidget
from src.ui.dialogs import (
    DirectorySelectionDialog, FileSaveDialog, FileOpenDialog,
    ProgressDialog, ValidationReportDialog, ConfirmDialog
)


class BannerLabel(QLabel):
    """Banner 标签 - 显示程序名称和版本信息"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #0078d4;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 4px;
            }
        """)
        self.setText(APP_TITLE)
        self.setMaximumHeight(60)

    def set_info(self, version: str, author: str, date: str) -> None:
        """更新版本信息"""
        self.setText(f"{APP_TITLE}  v{version}  |  {author}  |  {date}")


class ToolbarFrame(QFrame):
    """工具栏框架"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.NoFrame)
        self.setMaximumHeight(45)  # 限制工具栏高度
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 按钮样式
        button_style = """
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """

        # 选择工作目录按钮
        self.btn_select_dir = QPushButton("📁 选择工作目录")
        self.btn_select_dir.setStyleSheet(button_style)
        layout.addWidget(self.btn_select_dir)

        # 导入标签按钮
        self.btn_import = QPushButton("📥 导入标签")
        self.btn_import.setStyleSheet(button_style)
        layout.addWidget(self.btn_import)

        # 保存标签按钮
        self.btn_export = QPushButton("📤 保存标签")
        self.btn_export.setStyleSheet(button_style)
        layout.addWidget(self.btn_export)

        # 开始合并按钮
        self.btn_merge = QPushButton("🔗 开始合并")
        self.btn_merge.setStyleSheet(button_style)
        self.btn_merge.setMinimumWidth(100)
        layout.addWidget(self.btn_merge)

        # 拆分 PDF 按钮
        self.btn_split = QPushButton("📤 拆分 PDF")
        self.btn_split.setStyleSheet(button_style)
        self.btn_split.setMinimumWidth(100)
        layout.addWidget(self.btn_split)

        # 拆分单页 PDF 按钮
        self.btn_split_pages = QPushButton("📑 拆分单页")
        self.btn_split_pages.setStyleSheet(button_style)
        self.btn_split_pages.setMinimumWidth(100)
        layout.addWidget(self.btn_split_pages)

        # 排序管理按钮
        self.btn_sort = QPushButton("⚙ 排序管理")
        self.btn_sort.setStyleSheet(button_style)
        self.btn_sort.setMinimumWidth(90)
        layout.addWidget(self.btn_sort)

        # 右侧弹簧
        layout.addStretch()

        # 工作目录显示
        self.lbl_work_dir = QLabel("工作目录：未选择")
        self.lbl_work_dir.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        self.lbl_work_dir.setMaximumWidth(350)
        layout.addWidget(self.lbl_work_dir)


class MainWindow(QMainWindow):
    """
    主窗口
    """

    def __init__(self):
        super().__init__()
        self.work_dir: Optional[Path] = None
        self.tree_manager = TreeManager()
        self.settings = QSettings("PDFMC", "MainWindow")

        self._init_window()
        self._init_ui()
        self._connect_signals()
        self._restore_state()

    def _init_window(self) -> None:
        """初始化窗口"""
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1000, 700)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

    def _init_ui(self) -> None:
        """初始化 UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Banner - 约 10% 高度
        self.banner = BannerLabel()
        self.banner.set_info(APP_VERSION, APP_AUTHOR, APP_DATE)
        main_layout.addWidget(self.banner)

        # 工具栏 - 约 5% 高度
        self.toolbar = ToolbarFrame()
        main_layout.addWidget(self.toolbar)

        # 左右分栏 - 占满剩余空间
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)
        self.splitter.setOpaqueResize(True)  # 拖动时实时显示

        # 左侧树形结构 - 1/3
        tree_frame = QFrame()
        tree_frame.setFrameStyle(QFrame.StyledPanel)
        tree_frame.setStyleSheet("background-color: #fafafa;")
        tree_layout = QVBoxLayout(tree_frame)
        tree_layout.setContentsMargins(3, 3, 3, 3)
        tree_layout.setSpacing(2)

        tree_label = QLabel("📂 目录结构")
        tree_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        tree_layout.addWidget(tree_label)

        self.tree_widget = TreeWidget()
        self.tree_widget.setMinimumWidth(200)
        tree_layout.addWidget(self.tree_widget)

        self.splitter.addWidget(tree_frame)

        # 右侧预览区 - 2/3
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.StyledPanel)
        preview_frame.setStyleSheet("background-color: #fafafa;")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(3, 3, 3, 3)
        preview_layout.setSpacing(2)

        preview_label = QLabel("📄 文件预览")
        preview_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        preview_layout.addWidget(preview_label)

        self.preview_widget = PreviewWidget()
        self.preview_widget.setMinimumWidth(250)
        preview_layout.addWidget(self.preview_widget)

        self.splitter.addWidget(preview_frame)

        # 设置分割比例 - 树形 1/3，预览 2/3
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        # 初始分割位置
        self.splitter.setSizes([int(WINDOW_WIDTH * 0.33), int(WINDOW_WIDTH * 0.67)])

        main_layout.addWidget(self.splitter)

        # 设置主区域拉伸因子，让 splitter 占满剩余空间
        main_layout.setStretch(0, 0)  # Banner 不拉伸
        main_layout.setStretch(1, 0)  # Toolbar 不拉伸
        main_layout.setStretch(2, 1)  # Splitter 拉伸

    def _connect_signals(self) -> None:
        """连接信号"""
        # 工具栏按钮
        self.toolbar.btn_select_dir.clicked.connect(self._on_select_directory)
        self.toolbar.btn_import.clicked.connect(self._on_import_xml)
        self.toolbar.btn_export.clicked.connect(self._on_export_xml)
        self.toolbar.btn_merge.clicked.connect(self._on_merge_pdf)
        self.toolbar.btn_split.clicked.connect(self._on_split_pdf)
        self.toolbar.btn_split_pages.clicked.connect(self._on_split_pages)
        self.toolbar.btn_sort.clicked.connect(self._on_sort_management)

        # 树形组件信号
        self.tree_widget.request_preview.connect(self._on_preview_request)
        self.tree_widget.structure_changed.connect(self._on_tree_structure_changed)

    def _save_state(self) -> None:
        """保存窗口状态和分割器位置"""
        try:
            self.settings.setValue("window/geometry", self.saveGeometry())
            self.settings.setValue("window/state", self.saveState())
            self.settings.setValue("splitter/sizes", self.splitter.sizes())
        except Exception as e:
            print(f"保存状态失败：{e}")

    def _restore_state(self) -> None:
        """恢复窗口状态和分割器位置"""
        try:
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            state = self.settings.value("window/state")
            if state:
                self.restoreState(state)
            sizes = self.settings.value("splitter/sizes")
            if sizes:
                # 转换为 List[int]
                sizes_list = [int(s) for s in sizes]
                self.splitter.setSizes(sizes_list)
        except Exception as e:
            print(f"恢复状态失败：{e}")

    def _on_preview_request(self, tree_item) -> None:
        """
        处理预览请求。

        从 TreeItem 的父链回溯构建完整路径：
        - 有 path → 直接用
        - path 为空（如 XML 导入），沿父链向上找到所有目录名，
          拼出相对路径 work_dir/父目录/.../文件名，再拼接
        """
        # 防御：忽略 None 或非 TreeItem 对象
        if tree_item is None:
            return

        try:
            is_dir = tree_item.is_dir
            item_path = tree_item.path
            item_name = tree_item.name
        except Exception:
            return

        if is_dir:
            return

        if not item_path:
            # path 为空（XML 导入），沿父链向上构建相对路径
            if self.work_dir and item_name:
                parts = []
                node = tree_item
                while node is not None:
                    parts.append(node.name)
                    node = node.parent
                rel_parts = list(reversed(parts[1:]))
                rel_path = '/'.join(rel_parts) if rel_parts else ''
                filename = item_name
                if not filename.lower().endswith('.pdf'):
                    filename += '.pdf'
                full_path = str(self.work_dir / rel_path / filename) if rel_path else str(self.work_dir / filename)
                if full_path:
                    self.preview_widget.show_file(full_path)
        else:
            self.preview_widget.show_file(item_path)

    def _load_xml_into_tree(self, xml_path: str) -> None:
        """从 XML 文件加载书签到树"""
        items, success = import_from_xml(xml_path)
        if not success or not items:
            ConfirmDialog.error(self, "错误", "加载 XML 失败，文件格式可能不正确")
            return

        self.tree_manager.load_from_dict({'children': items})
        tree_items = items_to_tree_items(items)
        self.tree_widget.load_data(tree_items)

        issues = validate_xml(items, str(self.work_dir))
        if issues:
            dialog = ValidationReportDialog(self, issues)
            dialog.exec()
            self.statusBar.showMessage(f"加载完成，发现 {len(issues)} 个问题节点")
        else:
            self.statusBar.showMessage(f"书签已加载：{Path(xml_path).name}")

    def _on_select_directory(self) -> None:
        """选择工作目录"""
        default_dir = str(self.work_dir) if self.work_dir else str(DEFAULT_WORK_DIR)

        # 始终弹出目录选择对话框，让用户自由选择任意目录
        dir_path = DirectorySelectionDialog.select_directory(self, default_dir)

        if dir_path:
            self.work_dir = Path(dir_path)
            self._scan_and_load_directory()
            self.statusBar.showMessage(f"工作目录：{dir_path}")

    def _scan_and_load_directory(self) -> None:
        """扫描并加载目录"""
        if not self.work_dir:
            return

        # 更新工作目录显示
        self.toolbar.lbl_work_dir.setText(f"工作目录：{self.work_dir}")

        # 检测目录中是否有 XML 文件
        xml_files = sorted(self.work_dir.glob("*.xml"))

        if xml_files:
            # 有 XML 文件，询问用户
            if len(xml_files) == 1:
                msg = f"在目录中发现书签文件：\n{xml_files[0].name}\n\n是否加载该书签？\n（选择" + "\u201c否\u201d" + "将扫描目录）"
            else:
                names = "\n".join(f.name for f in xml_files)
                msg = f"在目录中发现 {len(xml_files)} 个书签文件：\n{names}\n\n是否加载第一个书签？\n（选择" + "\u201c否\u201d" + "将扫描目录）"

            reply = ConfirmDialog.ask(self, "检测到书签文件", msg)

            if reply:
                # 加载 XML 书签
                self._load_xml_into_tree(str(xml_files[0]))
                return

        # 扫描目录
        self.statusBar.showMessage("正在扫描目录...")
        nodes = scan_directory(str(self.work_dir))

        # 加载到树管理器
        self.tree_manager.load_from_nodes(nodes)

        # 加载到树形组件
        self.tree_widget.load_data(self.tree_manager.root_items)

        self.statusBar.showMessage(f"扫描完成，找到 {len(self.tree_manager.get_all_items())} 个项目")

    def _on_import_xml(self) -> None:
        """导入 XML 标签"""
        if not self.work_dir:
            ConfirmDialog.warning(self, "提示", "请先选择工作目录")
            return

        # 选择 XML 文件
        xml_path = FileOpenDialog.open_xml(self, str(DEFAULT_OUTPUT_DIR))
        if not xml_path:
            return

        # 导入 XML
        items, success = import_from_xml(xml_path)
        if not success or not items:
            ConfirmDialog.error(self, "错误", "导入 XML 失败，文件格式可能不正确")
            return

        # 加载到树管理器
        self.tree_manager.load_from_dict({'children': items})

        # 转换为 TreeItem 并加载到 UI
        tree_items = items_to_tree_items(items)
        self.tree_widget.load_data(tree_items)

        # 验证文件对应性
        issues = validate_xml(items, str(self.work_dir))

        if issues:
            # 显示验证报告
            dialog = ValidationReportDialog(self, issues)
            dialog.exec()
            self.statusBar.showMessage(f"导入完成，发现 {len(issues)} 个问题节点")
        else:
            ConfirmDialog.info(self, "导入成功", "所有节点均找到对应文件")
            self.statusBar.showMessage("导入完成")

    def _on_export_xml(self) -> None:
        """导出 XML 标签"""
        if not self.tree_manager.root_items:
            ConfirmDialog.warning(self, "提示", "没有可导出的标签结构")
            return

        # 选择保存位置
        save_path = FileSaveDialog.save_xml(self, str(DEFAULT_OUTPUT_DIR))
        if not save_path:
            return

        # 确保扩展名
        if not save_path.endswith('.xml'):
            save_path += '.xml'

        # 导出
        success = export_to_xml(self.tree_manager.root_items, save_path)

        if success:
            ConfirmDialog.info(self, "导出成功", f"标签已保存到:\n{save_path}")
            self.statusBar.showMessage(f"标签已导出：{save_path}")
        else:
            ConfirmDialog.error(self, "导出失败", "保存 XML 文件时出错")

    def _on_merge_pdf(self) -> None:
        """合并 PDF"""
        if not self.work_dir:
            ConfirmDialog.warning(self, "提示", "请先选择工作目录")
            return

        if not self.tree_manager.root_items:
            ConfirmDialog.warning(self, "提示", "没有可合并的文件")
            return

        # 选择保存位置
        save_path = FileSaveDialog.save_pdf(self, str(DEFAULT_OUTPUT_DIR))
        if not save_path:
            return

        # 确保扩展名
        if not save_path.endswith('.pdf'):
            save_path += '.pdf'

        # 收集所有 PDF 文件用于进度计算
        current_items = self.tree_widget.get_current_structure()
        all_files = []
        for item in current_items:
            self._collect_pdf_files(item, all_files)

        # 预检：收集缺失 PDF 的真实文件节点
        merger = PDFMerger()
        merger.work_dir = str(self.work_dir) if self.work_dir else ""
        missing = merger._collect_missing_nodes(current_items)

        pregenerated_paths: set = set()
        if missing:
            names = '\n'.join(f"• {item.name}" for item, _ in missing)
            reply = ConfirmDialog.ask(
                self, "发现缺失文件",
                f"以下节点没有对应的 PDF 文件：\n{names}\n\n"
                f"是否生成 {len(missing)} 个空白页占位并继续合并？\n"
                f"（空白 PDF 将保存到对应目录）"
            )
            if not reply:
                return
            # 生成空白页 PDF，收集路径用于合并器去重（使用规范化路径确保格式一致）
            for item, resolved_path in missing:
                try:
                    norm_path = os.path.normpath(resolved_path)
                    merger._write_blank_pdf(norm_path)
                    pregenerated_paths.add(norm_path)
                except Exception as e:
                    ConfirmDialog.error(self, "生成空白页失败", f"无法生成：{resolved_path}\n{e}")
                    return

        total_files = len(all_files)
        if total_files == 0:
            ConfirmDialog.warning(self, "提示", "没有找到可合并的 PDF 文件")
            return

        # 显示进度对话框 - 可关闭，带取消按钮
        self.progress_dialog = ProgressDialog(
            self,
            "合并 PDF",
            "正在合并文件...",
            total_files
        )
        self.progress_dialog.show()

        # 已处理的文件计数
        processed_count = [0]

        # 进度回调
        def progress_callback(current: int, total: int, message: str):
            processed_count[0] = current + 1
            self.progress_dialog.set_value(processed_count[0])
            self.progress_dialog.set_label(f"正在处理：{message} ({processed_count[0]}/{total_files})")
            # 处理窗口事件，保持界面响应
            QApplication.processEvents()

        # 执行合并 - 使用编辑后的树结构
        success = merge_pdfs(
            current_items,
            save_path,
            str(self.work_dir) if self.work_dir else "",
            progress_callback,
            pregenerated_paths
        )

        # 关闭进度对话框
        self.progress_dialog.close()

        if success:
            ConfirmDialog.info(self, "合并成功", f"PDF 已保存到:\n{save_path}")
            self.statusBar.showMessage(f"PDF 合并完成：{save_path}")
        else:
            ConfirmDialog.error(self, "合并失败", "合并 PDF 时出错，请查看控制台日志")

    def _on_split_pdf(self) -> None:
        """拆分 PDF"""
        # 选择要拆分的 PDF 文件
        input_path = FileOpenDialog.open_pdf(self, str(DEFAULT_OUTPUT_DIR))
        if not input_path:
            return

        # 选择输出目录
        output_dir = DirectorySelectionDialog.select_directory(self, str(DEFAULT_OUTPUT_DIR))
        if not output_dir:
            return

        # 显示进度对话框
        self.progress_dialog = ProgressDialog(
            self,
            "拆分 PDF",
            "正在拆分文件...",
            100
        )
        self.progress_dialog.show()

        # 进度回调
        def progress_callback(current: int, total: int, message: str):
            if total > 0:
                progress = int((current / total) * 100)
            else:
                progress = current
            self.progress_dialog.set_value(progress)
            self.progress_dialog.set_label(f"正在处理：{message}")
            QApplication.processEvents()

        # 执行拆分
        success = split_pdf(input_path, output_dir, progress_callback)

        # 关闭进度对话框
        self.progress_dialog.close()

        if success:
            ConfirmDialog.info(self, "拆分成功", f"PDF 已按书签拆分为多个文件\n保存在：\n{output_dir}")
            self.statusBar.showMessage(f"PDF 拆分完成：{output_dir}")
        else:
            ConfirmDialog.error(self, "拆分失败", "拆分 PDF 时出错，请查看控制台日志")

    def _on_split_pages(self) -> None:
        """拆分单页 PDF - 将多页 PDF 拆分为多个单页 PDF"""
        # 选择要拆分的 PDF 文件
        input_path = FileOpenDialog.open_pdf(self, str(DEFAULT_OUTPUT_DIR))
        if not input_path:
            return

        # 选择输出目录
        output_dir = DirectorySelectionDialog.select_directory(self, str(DEFAULT_OUTPUT_DIR))
        if not output_dir:
            return

        # 获取总页数用于进度
        try:
            from pypdf import PdfReader
            reader = PdfReader(input_path)
            total_pages = len(reader.pages)
            if total_pages == 0:
                ConfirmDialog.warning(self, "提示", "PDF 文件没有页面")
                return
        except Exception as e:
            ConfirmDialog.error(self, "错误", f"无法读取 PDF 文件：{e}")
            return

        # 显示进度对话框
        self.progress_dialog = ProgressDialog(
            self,
            "拆分单页 PDF",
            "正在拆分文件...",
            total_pages
        )
        self.progress_dialog.show()

        # 进度回调
        def progress_callback(current: int, total: int, message: str):
            if total > 0:
                self.progress_dialog.set_value(current)
            self.progress_dialog.set_label(f"正在处理：{message}")
            QApplication.processEvents()

        # 执行拆分
        success = split_pdf_to_single_pages(input_path, output_dir, progress_callback)

        # 关闭进度对话框
        self.progress_dialog.close()

        if success:
            ConfirmDialog.info(
                self, "拆分成功",
                f"PDF 已拆分为 {total_pages} 个单页文件\n保存在：\n{output_dir}"
            )
            self.statusBar.showMessage(f"PDF 拆分完成：{output_dir}")
        else:
            ConfirmDialog.error(self, "拆分失败", "拆分 PDF 时出错，请查看控制台日志")

    def _on_sort_management(self) -> None:
        """用系统记事本打开 sort_order.ini"""
        import subprocess, sys
        ini_path = Path(__file__).resolve().parent.parent.parent / "sort_order.ini"
        if not ini_path.exists():
            ini_path.write_text(
                "[SortOrder]\n; 自定义排序顺序（从上到下依次排列）\n"
                "; 名称必须与目录/文件名完全一致（不含 .pdf 后缀）\n\n"
                "[DisplayNames]\n; 显示名称映射（可选）：实际名称 → 显示名称\n",
                encoding="utf-8"
            )
        try:
            if sys.platform == "win32":
                subprocess.Popen(["notepad.exe", str(ini_path)])
            else:
                subprocess.Popen(["xdg-open", str(ini_path)])
        except Exception as e:
            ConfirmDialog.error(self, "打开失败", f"无法打开 sort_order.ini：\n{e}")

    def _collect_pdf_files(self, item, files: list) -> None:
        """递归收集 PDF 文件"""
        if item.is_dir:
            for child in item.children:
                self._collect_pdf_files(child, files)
            return

        resolved = item.resolve_path(str(self.work_dir) if self.work_dir else "")
        if resolved.lower().endswith('.pdf'):
            files.append(resolved)

    def _on_tree_structure_changed(self) -> None:
        """树结构发生变化"""
        # 同步数据
        self.tree_manager.root_items = self.tree_widget.get_current_structure()
        self.statusBar.showMessage("树结构已更新")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            self._save_state()
        except:
            pass
        event.accept()
