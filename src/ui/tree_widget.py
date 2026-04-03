"""
树形组件 - QTreeWidget 实现，支持右键菜单、拖拽排序、增删改
"""
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QLineEdit,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QInputDialog,
    QStyle
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QCursor, QIcon

from typing import Optional, List, Callable
from pathlib import Path

from ..core.tree_manager import TreeItem


# 全局图标缓存
_folder_icon = None
_file_icon = None

def get_icons(widget):
    """获取图标（全局缓存）"""
    global _folder_icon, _file_icon
    if _folder_icon is None:
        _folder_icon = widget.style().standardIcon(QStyle.SP_DirIcon)
        _file_icon = widget.style().standardIcon(QStyle.SP_FileIcon)
    return _folder_icon, _file_icon


class FileTreeItem(QTreeWidgetItem):
    """
    树项组件
    扩展 QTreeWidgetItem，关联 TreeItem 数据
    """

    def __init__(self, parent=None, tree_item=None):
        super().__init__(parent)
        self.tree_item = tree_item  # 关联的数据模型
        if tree_item:
            self.setText(0, tree_item.name)  # 显示名称（已处理后缀）

    def update_name(self, new_name: str) -> None:
        """更新显示名称"""
        self.setText(0, new_name)


class TreeWidget(QTreeWidget):
    """
    树形结构组件
    支持：
    - 右键菜单（全部展开/收起、节点展开/收起）
    - 拖拽排序
    - 增删改操作
    """

    # 信号
    item_selected = Signal(TreeItem)      # 项被选中
    structure_changed = Signal()           # 结构发生变化
    request_preview = Signal(object)       # 传递 TreeItem，计算完整路径由主窗口处理

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_items: List[TreeItem] = []

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        """初始化 UI"""
        # 设置基本属性
        self.setHeaderLabels(["名称"])
        self.setExpandsOnDoubleClick(False)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QTreeWidget.InternalMove)

        # 右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        # 列设置
        self.setColumnCount(1)
        self.setIndentation(20)

        # 样式
        self.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                font-size: 13px;
            }
            QTreeWidget::item {
                height: 28px;
                padding: 2px;
            }
            QTreeWidget::item:hover {
                background-color: #e8e8e8;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

    def _connect_signals(self) -> None:
        """连接信号"""
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def load_data(self, tree_items: List[TreeItem]) -> None:
        """
        加载树形数据

        Args:
            tree_items: TreeItem 列表
        """
        self.clear()
        self.setCurrentItem(None)   # 防止 clear 后 Qt 自动选中第一个 item 触发 preview
        self.root_items = tree_items

        for item in tree_items:
            self._add_tree_item(item, None)

    def _add_tree_item(self, tree_item: TreeItem, parent_widget: Optional[QTreeWidgetItem]) -> None:
        """
        添加树项到组件

        Args:
            tree_item: 数据模型
            parent_widget: 父组件项
        """
        widget_item = FileTreeItem(parent_widget, tree_item)
        # 设置图标
        folder_icon, file_icon = get_icons(self)
        if tree_item.is_dir:
            widget_item.setIcon(0, folder_icon)
        else:
            widget_item.setIcon(0, file_icon)

        # 递归添加子项
        for child in tree_item.children:
            self._add_tree_item(child, widget_item)

        if parent_widget is None:
            self.addTopLevelItem(widget_item)

    def _show_context_menu(self, position) -> None:
        """显示右键菜单"""
        item = self.itemAt(position)

        menu = QMenu(self)

        # 展开/收起菜单
        expand_all_action = menu.addAction("全部展开")
        expand_all_action.triggered.connect(self.expandAll)

        collapse_all_action = menu.addAction("全部收起")
        collapse_all_action.triggered.connect(self.collapseAll)

        menu.addSeparator()

        # 节点操作菜单（只有选中项时可用）
        if item:
            expand_action = menu.addAction("展开")
            expand_action.triggered.connect(lambda: self.setItemExpanded(item, True))

            collapse_action = menu.addAction("收起")
            collapse_action.triggered.connect(lambda: self.setItemExpanded(item, False))

            menu.addSeparator()

            # 重命名
            rename_action = menu.addAction("重命名")
            rename_action.triggered.connect(lambda: self._rename_item(item))

            # 删除
            delete_action = menu.addAction("删除")
            delete_action.triggered.connect(lambda: self._delete_item(item))

            menu.addSeparator()

            # 添加子文件夹
            add_folder_action = menu.addAction("添加子文件夹")
            add_folder_action.triggered.connect(lambda: self._add_folder(item))

            # 添加书签（虚拟书签节点，可无对应 PDF）
            add_bookmark_action = menu.addAction("添加书签")
            add_bookmark_action.triggered.connect(lambda: self._add_bookmark(item))

            # 添加 PDF 文件
            add_file_action = menu.addAction("添加 PDF 文件")
            add_file_action.triggered.connect(lambda: self._add_file(item))

        menu.addSeparator()

        # 刷新
        refresh_action = menu.addAction("刷新")
        refresh_action.triggered.connect(self._refresh)

        # 显示菜单
        menu.exec_(self.viewport().mapToGlobal(position))

    def _on_item_clicked(self, widget_item: QTreeWidgetItem, column: int) -> None:
        """项被点击"""
        if isinstance(widget_item, FileTreeItem) and widget_item.tree_item:
            tree_item = widget_item.tree_item
            if not tree_item.is_dir:
                self.item_selected.emit(tree_item)
                self.request_preview.emit(tree_item)

    def _on_item_double_clicked(self, widget_item: QTreeWidgetItem, column: int) -> None:
        """项被双击"""
        # 切换展开/收起状态
        widget_item.setExpanded(not widget_item.isExpanded())

    def _rename_item(self, widget_item: QTreeWidgetItem) -> None:
        """重命名项"""
        if not isinstance(widget_item, FileTreeItem):
            return

        tree_item = widget_item.tree_item
        if not tree_item:
            return

        new_name, ok = QInputDialog.getText(
            self, "重命名", "请输入新名称:\n（仅修改显示名称，不影响实际文件）",
            text=tree_item.name
        )

        if ok and new_name.strip():
            tree_item.name = new_name.strip()
            widget_item.setText(0, new_name.strip())
            self.structure_changed.emit()

    def _delete_item(self, widget_item: QTreeWidgetItem) -> None:
        """删除项"""
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除选中的项吗？\n此操作仅影响标签结构，不会删除实际文件。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            parent = widget_item.parent()
            if parent:
                parent.removeChild(widget_item)
            else:
                index = self.indexOfTopLevelItem(widget_item)
                if index >= 0:
                    self.takeTopLevelItem(index)

            self.structure_changed.emit()

    def _add_folder(self, parent_widget_item: QTreeWidgetItem) -> None:
        """添加子文件夹"""
        if not isinstance(parent_widget_item, FileTreeItem):
            return

        parent_tree_item = parent_widget_item.tree_item
        if not parent_tree_item or not parent_tree_item.is_dir:
            QMessageBox.warning(self, "提示", "请选择一个文件夹节点")
            return

        # 输入文件夹名称
        folder_name, ok = QInputDialog.getText(
            self, "新建文件夹", "请输入文件夹名称:"
        )

        if ok and folder_name.strip():
            new_tree_item = TreeItem(
                name=folder_name.strip(),
                path="",  # 虚拟文件夹，无实际路径
                is_dir=True
            )
            parent_tree_item.children.append(new_tree_item)

            # 添加到 UI
            child_widget = FileTreeItem(parent_widget_item, new_tree_item)
            self.setItemExpanded(parent_widget_item, True)
            self.structure_changed.emit()

    def _add_bookmark(self, context_item: QTreeWidgetItem) -> None:
        """添加虚拟书签节点（无对应 PDF，合并时插入空白页占位）"""
        if not isinstance(context_item, FileTreeItem):
            return

        name, ok = QInputDialog.getText(
            self, "添加书签", "请输入书签名称："
        )
        if not (ok and name.strip()):
            return

        new_tree_item = TreeItem(
            name=name.strip(),
            path="",          # 虚拟书签，path 为空
            is_dir=False
        )

        tree_item = context_item.tree_item
        if tree_item.is_dir:
            # 目录节点 → 作为子节点添加
            tree_item.children.append(new_tree_item)
            new_tree_item.parent = tree_item
            new_widget = FileTreeItem(context_item, new_tree_item)
            context_item.addChild(new_widget)
            self.setItemExpanded(context_item, True)
        else:
            # 文件节点 → 作为兄弟节点添加（同级）
            parent_widget = context_item.parent()
            if parent_widget is None:
                new_widget = FileTreeItem(None, new_tree_item)
                self.addTopLevelItem(new_widget)
            else:
                parent_tree = parent_widget.tree_item
                parent_tree.children.append(new_tree_item)
                new_tree_item.parent = parent_tree
                new_widget = FileTreeItem(parent_widget, new_tree_item)
                parent_widget.addChild(new_widget)

        self.structure_changed.emit()

    def _add_file(self, context_item: QTreeWidgetItem) -> None:
        """添加 PDF 文件（弹出文件选择框，路径自动解析到对应目录）"""
        if not isinstance(context_item, FileTreeItem):
            return

        # 从选中节点推算初始目录：
        # - 文件节点 → 取其所在目录
        # - 目录节点 → 取该目录
        tree_item = context_item.tree_item
        if tree_item.is_dir:
            base_dir = tree_item.path if tree_item.path else ""
        else:
            base_dir = str(Path(tree_item.path).parent) if tree_item.path else ""

        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 PDF 文件",
            base_dir,
            "PDF 文件 (*.pdf)"
        )
        if not file_path:
            return

        # 文件名（去后缀）作为显示名
        filename = Path(file_path).name
        if filename.lower().endswith('.pdf'):
            display_name = filename[:-4]
        else:
            display_name = filename

        new_tree_item = TreeItem(
            name=display_name,
            path=file_path,   # 完整路径，resolve_path 会直接返回它
            is_dir=False
        )

        # 点击目录 → 作为子节点；点击文件 → 作为兄弟节点
        if tree_item.is_dir:
            tree_item.children.append(new_tree_item)
            new_tree_item.parent = tree_item
            new_widget = FileTreeItem(context_item, new_tree_item)
            context_item.addChild(new_widget)
            self.setItemExpanded(context_item, True)
        else:
            parent_widget = context_item.parent()
            if parent_widget is None:
                new_widget = FileTreeItem(None, new_tree_item)
                self.addTopLevelItem(new_widget)
            else:
                parent_tree = parent_widget.tree_item
                parent_tree.children.append(new_tree_item)
                new_tree_item.parent = parent_tree
                new_widget = FileTreeItem(parent_widget, new_tree_item)
                parent_widget.addChild(new_widget)

        self.structure_changed.emit()

    def _refresh(self) -> None:
        """刷新（占位，实际刷新由主窗口处理）"""
        self.structure_changed.emit()

    def get_current_structure(self) -> List[TreeItem]:
        """
        获取当前树结构（从 UI 递归重建）

        Returns:
            TreeItem 列表
        """
        result = []
        for i in range(self.topLevelItemCount()):
            widget_item = self.topLevelItem(i)
            if isinstance(widget_item, FileTreeItem):
                tree_item = self._rebuild_tree_item(widget_item)
                result.append(tree_item)
        return result

    def _rebuild_tree_item(self, widget_item: 'FileTreeItem') -> TreeItem:
        """
        从 QTreeWidgetItem 递归重建 TreeItem

        Args:
            widget_item: QTreeWidgetItem

        Returns:
            TreeItem
        """
        tree_item = widget_item.tree_item

        # 清空子项并从 UI 重建
        tree_item.children = []
        for i in range(widget_item.childCount()):
            child_widget = widget_item.child(i)
            if isinstance(child_widget, FileTreeItem):
                child_item = self._rebuild_tree_item(child_widget)
                child_item.parent = tree_item
                tree_item.children.append(child_item)

        return tree_item

    def dropEvent(self, event):
        """处理拖拽放置"""
        super().dropEvent(event)
        # 拖拽后更新内部数据结构
        self._sync_structure()
        self.structure_changed.emit()

    def _sync_structure(self) -> None:
        """同步 UI 结构到内部数据"""
        self.root_items = []
        for i in range(self.topLevelItemCount()):
            widget_item = self.topLevelItem(i)
            if isinstance(widget_item, FileTreeItem):
                self.root_items.append(widget_item.tree_item)

    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        super().dragMoveEvent(event)
        event.accept()

    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        super().dragEnterEvent(event)
        event.accept()
