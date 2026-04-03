"""
树结构管理器 - 管理树节点数据结构、增删改、拖拽排序
"""
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import copy


@dataclass
class TreeItem:
    """
    树项数据结构
    用于在 UI 和逻辑层之间传递数据
    """
    name: str                          # 显示名称（用于 UI 展示）
    path: str                          # 完整路径（对于虚拟节点可能为空）
    is_dir: bool                       # 是否为目录
    children: List['TreeItem'] = field(default_factory=list)
    parent: Optional['TreeItem'] = None

    def clone(self) -> 'TreeItem':
        """深拷贝"""
        new_item = TreeItem(
            name=self.name,
            path=self.path,
            is_dir=self.is_dir
        )
        for child in self.children:
            child_clone = child.clone()
            child_clone.parent = new_item
            new_item.children.append(child_clone)
        return new_item

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            'name': self.name,
            'path': self.path,
            'is_dir': self.is_dir,
            'children': [child.to_dict() for child in self.children]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: 'TreeItem' = None) -> 'TreeItem':
        """从字典创建（PDF 文件名自动去掉 .pdf 后缀用于显示）"""
        raw_name = data['name']
        # PDF 文件名去掉 .pdf 后缀用于显示
        if raw_name.lower().endswith('.pdf'):
            display_name = raw_name[:-4]
        else:
            display_name = raw_name
        item = cls(
            name=display_name,
            path=data.get('path', ''),
            is_dir=data["is_dir"],
            parent=parent
        )
        for child_data in data.get('children', []):
            item.children.append(cls.from_dict(child_data, parent=item))
        return item

    def resolve_path(self, work_dir: str = "") -> str:
        """
        解析文件完整路径。
        - 有 path → 直接返回
        - path 为空 → 沿父链构建相对路径，末尾补 .pdf 后缀
        """
        if self.path:
            return self.path
        if not work_dir or self.is_dir:
            return self.path
        parts = []
        node = self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        rel_parts = list(reversed(parts[1:]))
        rel_path = '/'.join(rel_parts) if rel_parts else ''
        filename = self.name
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        full = os.path.join(work_dir, rel_path, filename) if rel_path else os.path.join(work_dir, filename)
        return full

    def get_all_pdf_files(self, work_dir: str = "") -> List[str]:
        """获取该项下所有 PDF 文件路径（按顺序）"""
        files = []
        if not self.is_dir:
            resolved = self.resolve_path(work_dir)
            if resolved.lower().endswith('.pdf'):
                files.append(resolved)
        else:
            for child in self.children:
                files.extend(child.get_all_pdf_files(work_dir))
        return files

    def find_node_by_path(self, target_path: str) -> Optional['TreeItem']:
        """根据路径查找节点"""
        if self.path == target_path:
            return self
        for child in self.children:
            result = child.find_node_by_path(target_path)
            if result:
                return result
        return None


class TreeManager:
    """
    树结构管理器
    处理树的增删改查、拖拽排序等操作
    """

    def __init__(self):
        self.root_items: List[TreeItem] = []
        self._path_to_item: Dict[str, TreeItem] = {}
        self._update_path_map()

    def load_from_nodes(self, nodes: List) -> None:
        """
        从扫描器节点加载树结构

        Args:
            nodes: DirectoryScanner 返回的 TreeNode 列表
        """
        self.root_items = []
        for node in nodes:
            item = self._convert_to_item(node)
            self.root_items.append(item)
        self._update_path_map()

    def _convert_to_item(self, node, parent: Optional[TreeItem] = None) -> TreeItem:
        """转换 TreeNode 为 TreeItem（display_name 用于显示名称）"""
        item = TreeItem(
            name=node.display_name,  # display_name 已处理过后缀和 INI 映射
            path=node.path,
            is_dir=node.is_dir,
            parent=parent
        )
        for child_node in node.children:
            child_item = self._convert_to_item(child_node, parent=item)
            item.children.append(child_item)
        return item

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """
        从字典数据加载树结构（用于导入标签）

        Args:
            data: 包含树结构的字典
        """
        self.root_items = []
        if 'children' in data:
            for child_data in data['children']:
                item = TreeItem.from_dict(child_data)
                self.root_items.append(item)
        else:
            # 直接是节点列表
            for item_data in data:
                item = TreeItem.from_dict(item_data)
                self.root_items.append(item)
        self._update_path_map()

    def _update_path_map(self) -> None:
        """更新路径到项的映射"""
        self._path_to_item = {}
        for item in self.root_items:
            self._index_item(item)

    def _index_item(self, item: TreeItem) -> None:
        """递归索引项"""
        if item.path:
            self._path_to_item[item.path] = item
        for child in item.children:
            self._index_item(child)

    def add_item(self, parent_item: Optional[TreeItem], new_item: TreeItem, index: int = -1) -> bool:
        """
        添加新项

        Args:
            parent_item: 父项，None 表示添加到根级别
            new_item: 新项
            index: 插入位置，-1 表示追加

        Returns:
            是否成功
        """
        if parent_item is None:
            if index < 0 or index >= len(self.root_items):
                self.root_items.append(new_item)
            else:
                self.root_items.insert(index, new_item)
            new_item.parent = None
        else:
            if index < 0 or index >= len(parent_item.children):
                parent_item.children.append(new_item)
            else:
                parent_item.children.insert(index, new_item)
            new_item.parent = parent_item

        self._update_path_map()
        return True

    def remove_item(self, item: TreeItem) -> bool:
        """
        删除项

        Args:
            item: 要删除的项

        Returns:
            是否成功
        """
        if item.parent is None:
            if item in self.root_items:
                self.root_items.remove(item)
            else:
                return False
        else:
            if item in item.parent.children:
                item.parent.children.remove(item)
            else:
                return False

        self._update_path_map()
        return True

    def move_item(self, item: TreeItem, new_parent: Optional[TreeItem], new_index: int) -> bool:
        """
        移动项到新位置

        Args:
            item: 要移动的项
            new_parent: 新父项，None 表示移动到根级别
            new_index: 新位置索引

        Returns:
            是否成功
        """
        # 不能移动到自己或自己的子项下
        current = new_parent
        while current:
            if current == item:
                return False
            current = current.parent

        # 从原位置移除
        self.remove_item(item)

        # 添加到新位置
        self.add_item(new_parent, item, new_index)

        return True

    def rename_item(self, item: TreeItem, new_name: str) -> bool:
        """
        重命名项

        Args:
            item: 要重命名的项
            new_name: 新名称

        Returns:
            是否成功
        """
        if not new_name or not new_name.strip():
            return False
        item.name = new_name.strip()
        return True

    def get_item_by_path(self, path: str) -> Optional[TreeItem]:
        """根据路径获取项"""
        return self._path_to_item.get(path)

    def get_all_items(self) -> List[TreeItem]:
        """获取所有项（扁平列表）"""
        items = []
        for root in self.root_items:
            self._collect_items(root, items)
        return items

    def _collect_items(self, item: TreeItem, result: List[TreeItem]) -> None:
        """递归收集所有项"""
        result.append(item)
        for child in item.children:
            self._collect_items(child, result)

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            'children': [item.to_dict() for item in self.root_items]
        }

    def get_flat_structure(self) -> List[Dict[str, Any]]:
        """
        获取扁平化的树结构（用于 XML 导出）
        包含每个文件的层级路径信息
        """
        result = []
        for root in self.root_items:
            self._flatten_structure(root, "", result)
        return result

    def _flatten_structure(self, item: TreeItem, parent_path: str, result: List[Dict[str, Any]]) -> None:
        """递归扁平化结构"""
        current_path = f"{parent_path}/{item.name}" if parent_path else item.name
        result.append({
            'name': item.name,
            'path': item.path,
            'is_dir': item.is_dir,
            'full_path': current_path
        })
        for child in item.children:
            self._flatten_structure(child, current_path, result)

    def get_all_pdf_files(self, items: Optional[List[TreeItem]] = None) -> List[str]:
        """
        获取所有 PDF 文件路径

        Args:
            items: 树项列表，默认为 root_items

        Returns:
            PDF 文件路径列表
        """
        if items is None:
            items = self.root_items

        files = []
        for item in items:
            self._collect_pdf_files(item, files)
        return files

    def _collect_pdf_files(self, item: TreeItem, files: List[str]) -> None:
        """递归收集 PDF 文件"""
        if not item.is_dir:
            if item.path.endswith('.pdf'):
                files.append(item.path)
        else:
            for child in item.children:
                self._collect_pdf_files(child, files)
