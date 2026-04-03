"""
对话框模块 - 目录选择、进度条、差异报告对话框
"""
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QProgressDialog, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QDialogButtonBox, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QMessageBox, QCompleter, QLineEdit, QFileSystemModel, QTreeView
)
from PySide6.QtCore import Qt, QDir, QModelIndex, QItemSelectionModel, QTimer
from PySide6.QtGui import QFont
from PySide6.QtGui import QIcon

from typing import List, Optional, Callable
from pathlib import Path

from ..core.xml_handler import ValidationIssue


class DirectorySelectionDialog:
    """
    目录选择对话框（静态方法版，保留用于其他场景）
    """
    @staticmethod
    def select_directory(parent=None, default_dir: str = None) -> Optional[str]:
        dir_path = QFileDialog.getExistingDirectory(
            parent,
            "选择工作目录",
            default_dir or "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        return dir_path if dir_path else None


class SelectDirectoryDialog(QDialog):
    """
    自定义目录选择对话框（完全不依赖 Windows Shell COM）
    使用 QFileSystemModel + QTreeView 实现，100% Qt 绘制
    """
    def __init__(self, parent=None, default_dir: str = None):
        super().__init__(parent)
        self._selected_path = None
        self.setWindowTitle("选择工作目录")
        self.setMinimumSize(550, 450)
        self._init_ui(default_dir)

    def _init_ui(self, default_dir: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # 路径输入框（可编辑）
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("路径:"))
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(False)
        path_layout.addWidget(self.path_edit)
        layout.addLayout(path_layout)

        # 目录树视图
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(False)
        self.tree_view.setFont(QFont("Microsoft YaHei UI", 10))
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)

        # 使用文件系统模型
        self.model = QFileSystemModel()
        self.model.setRootPath("")  # 从根目录开始
        self.tree_view.setModel(self.model)

        # 只显示目录
        self.tree_view.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)

        # 隐藏 Size/Type/Date 列，只保留 Name
        for i in range(1, self.model.columnCount()):
            self.tree_view.hideColumn(i)

        self.tree_view.setIndentation(20)
        self.tree_view.setAnimated(True)

        # 默认路径：优先给定目录，其次 C:\
        start_path = default_dir if default_dir and Path(default_dir).exists() else "C:\\"
        idx = self.model.index(start_path)
        if idx.isValid():
            self.tree_view.expand(idx)
            self.tree_view.scrollTo(idx, QTreeView.NearestItem)
            self.path_edit.setText(QDir.toNativeSeparators(start_path))

        # 双击进入目录
        self.tree_view.doubleClicked.connect(self._on_double_clicked)
        # 单击选中
        self.tree_view.clicked.connect(self._on_clicked)

        layout.addWidget(self.tree_view)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_ok = QPushButton("  确 定  ")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        # 路径输入框回车确认
        self.path_edit.returnPressed.connect(self._on_path_edited)

    def _get_selected_path(self) -> Optional[str]:
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            return None
        idx = indexes[0]
        if idx.isValid():
            return self.model.filePath(idx)
        return None

    def _on_clicked(self, idx: QModelIndex) -> None:
        if idx.isValid():
            path = self.model.filePath(idx)
            self.path_edit.setText(QDir.toNativeSeparators(path))

    def _on_double_clicked(self, idx: QModelIndex) -> None:
        """双击展开/进入目录"""
        if idx.isValid():
            path = self.model.filePath(idx)
            if Path(path).is_dir():
                child_idx = self.model.index(path)
                if child_idx.isValid():
                    self.tree_view.expand(child_idx)

    def _on_path_edited(self) -> None:
        """用户在路径框中输入路径"""
        text = self.path_edit.text().strip()
        if not text:
            return
        path = QDir.cleanPath(text)
        idx = self.model.index(path)
        if idx.isValid() and Path(path).is_dir():
            self.tree_view.expand(idx)
            self.tree_view.scrollTo(idx, QTreeView.NearestItem)
            self.tree_view.setCurrentIndex(idx)
            self.path_edit.setText(QDir.toNativeSeparators(path))
        else:
            self.path_edit.setStyleSheet("background-color: #ffe0e0;")
            # 恢复样式
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.path_edit.setStyleSheet(""))

    def _on_ok(self) -> None:
        path = self._get_selected_path()
        if path and Path(path).is_dir():
            self._selected_path = path
            self.accept()
        else:
            # 尝试路径框中的路径
            text = self.path_edit.text().strip()
            if text and Path(text).is_dir():
                self._selected_path = text
                self.accept()
            else:
                QMessageBox.warning(self, "提示", "请先选择一个有效目录")

    def selectedPath(self) -> Optional[str]:
        return self._selected_path


class FileSaveDialog:
    """
    文件保存对话框
    """

    @staticmethod
    def save_xml(parent=None, default_dir: str = None, default_name: str = "outline.xml") -> Optional[str]:
        """
        显示 XML 保存对话框

        Args:
            parent: 父窗口
            default_dir: 默认目录
            default_name: 默认文件名

        Returns:
            保存路径，取消则返回 None
        """
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "保存标签",
            str(Path(default_dir or "") / default_name),
            "XML 文件 (*.xml);;所有文件 (*)"
        )
        return file_path if file_path else None

    @staticmethod
    def save_pdf(parent=None, default_dir: str = None, default_name: str = "merged.pdf") -> Optional[str]:
        """
        显示 PDF 保存对话框

        Args:
            parent: 父窗口
            default_dir: 默认目录
            default_name: 默认文件名

        Returns:
            保存路径，取消则返回 None
        """
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "保存合并后的 PDF",
            str(Path(default_dir or "") / default_name),
            "PDF 文件 (*.pdf);;所有文件 (*)"
        )
        return file_path if file_path else None


class FileOpenDialog:
    """
    文件打开对话框
    """

    @staticmethod
    def open_xml(parent=None, default_dir: str = None) -> Optional[str]:
        """
        显示 XML 打开对话框

        Args:
            parent: 父窗口
            default_dir: 默认目录

        Returns:
            文件路径，取消则返回 None
        """
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "导入标签",
            default_dir or "",
            "XML 文件 (*.xml);;所有文件 (*)"
        )
        return file_path if file_path else None

    @staticmethod
    def open_pdf(parent=None, default_dir: str = None) -> Optional[str]:
        """
        显示 PDF 打开对话框

        Args:
            parent: 父窗口
            default_dir: 默认目录

        Returns:
            文件路径，取消则返回 None
        """
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "选择要拆分的 PDF 文件",
            default_dir or "",
            "PDF 文件 (*.pdf);;所有文件 (*)"
        )
        return file_path if file_path else None


class ProgressDialog(QProgressDialog):
    """
    进度条对话框
    使用 QProgressDialog 原生组件，支持取消操作
    """

    def __init__(self, parent=None, title: str = "进度", label_text: str = "正在处理...", total: int = 100):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setLabelText(label_text)
        self.setMinimum(0)
        self.setMaximum(total)
        self.setValue(0)
        self.setModal(True)
        self.setCancelButtonText("取消")
        self.setMinimumWidth(450)
        self.setMinimumHeight(150)

        # 设置取消按钮（由 setCancelButtonText 启用）
        self.setCancelButtonText("取消")

        # 设置窗口标志为普通对话框，不带帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def set_value(self, value: int) -> None:
        """设置进度值"""
        self.setValue(value)

    def set_label(self, text: str) -> None:
        """设置标签文本"""
        self.setLabelText(text)

    def wasCanceled(self) -> bool:
        """检查是否被取消"""
        return super().wasCanceled()


class ValidationReportDialog(QDialog):
    """
    验证报告对话框 - 显示 XML 节点与文件的差异
    """

    def __init__(self, parent=None, issues: List[ValidationIssue] = None):
        super().__init__(parent)
        self.setWindowTitle("节点验证报告")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # 说明标签
        info_label = QLabel("以下节点在工作目录中未找到对应的文件或目录：")
        layout.addWidget(info_label)

        # 树形列表显示问题
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["问题类型", "节点名称", "描述"])
        self.tree.setColumnWidth(0, 100)
        self.tree.setColumnWidth(1, 150)
        layout.addWidget(self.tree)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        # 填充问题
        if issues:
            self._populate_issues(issues)

    def _populate_issues(self, issues: List[ValidationIssue]) -> None:
        """填充问题列表"""
        icon_map = {
            'missing_file': '📄',
            'missing_dir': '📁',
            'type_mismatch': '⚠️',
            'extra_file': '➕'
        }

        for issue in issues:
            item = QTreeWidgetItem([
                issue.issue_type,
                issue.node_name,
                issue.description
            ])
            self.tree.addTopLevelItem(item)


class ConfirmDialog:
    """
    确认对话框
    """

    @staticmethod
    def ask(parent=None, title: str = "确认", message: str = "") -> bool:
        """
        显示确认对话框

        Args:
            parent: 父窗口
            title: 标题
            message: 消息

        Returns:
            用户是否确认
        """
        reply = QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    @staticmethod
    def info(parent=None, title: str = "信息", message: str = "") -> None:
        """显示信息对话框"""
        QMessageBox.information(parent, title, message)

    @staticmethod
    def warning(parent=None, title: str = "警告", message: str = "") -> None:
        """显示警告对话框"""
        QMessageBox.warning(parent, title, message)

    @staticmethod
    def error(parent=None, title: str = "错误", message: str = "") -> None:
        """显示错误对话框"""
        QMessageBox.critical(parent, title, message)
