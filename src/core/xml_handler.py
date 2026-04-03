"""
XML 处理器 - PDF 标签格式导入/导出和校验
"""
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from .tree_manager import TreeItem, TreeManager


@dataclass
class ValidationIssue:
    """验证问题"""
    node_name: str           # 节点名称
    node_path: str           # 节点在 XML 中的路径
    issue_type: str          # 问题类型：missing_file, missing_dir, extra_file, type_mismatch
    description: str         # 问题描述


class XMLHandler:
    """
    XML 处理器
    处理 PDF 标签格式的 XML 导入/导出和校验
    """

    # PDF 标签 XML 标准格式
    # 根元素：<pdf-outline>
    # 子元素：<outline-item> 或 <bookmark>
    # 属性：title, path, is-dir

    def __init__(self):
        self.root_tag = 'pdf-outline'
        self.item_tag = 'outline-item'
        self.attrs = {
            'title': 'title',
            'path': 'path',
            'is_dir': 'is-dir'
        }

    def export_to_xml(self, tree_items: List[TreeItem], output_path: str) -> bool:
        """
        导出树结构到 XML 文件

        Args:
            tree_items: 树项列表
            output_path: 输出文件路径

        Returns:
            是否成功
        """
        try:
            # 创建根元素
            root = ET.Element(self.root_tag)
            root.set('version', '1.0')

            # 添加树项
            for item in tree_items:
                self._add_item_to_xml(root, item)

            # 生成格式化的 XML
            xml_string = self._prettify_xml(root)

            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_string)

            return True

        except Exception as e:
            print(f"导出 XML 失败：{e}")
            return False

    def _add_item_to_xml(self, parent: ET.Element, item: TreeItem) -> ET.Element:
        """
        添加树项到 XML 元素

        Args:
            parent: 父 XML 元素
            item: 树项

        Returns:
            创建的 XML 元素
        """
        elem = ET.SubElement(parent, self.item_tag)
        elem.set(self.attrs['title'], item.name)
        elem.set(self.attrs['path'], item.path)
        elem.set(self.attrs['is_dir'], str(item.is_dir).lower())

        # 递归添加子项
        for child in item.children:
            self._add_item_to_xml(elem, child)

        return elem

    def _prettify_xml(self, elem: ET.Element) -> str:
        """
        生成格式化的 XML 字符串

        Args:
            elem: XML 元素

        Returns:
            格式化的 XML 字符串
        """
        rough_string = ET.tostring(elem, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

    def import_from_xml(self, xml_path: str) -> Tuple[List[Dict[str, Any]], bool]:
        """
        从 XML 文件导入树结构

        Args:
            xml_path: XML 文件路径

        Returns:
            (树结构字典列表，是否成功)
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            if root.tag != self.root_tag:
                print(f"警告：XML 根标签不是 '{self.root_tag}'，但尝试解析...")

            items = []
            for child in root.findall(self.item_tag):
                item = self._parse_xml_item(child)
                if item:
                    items.append(item)

            return items, True

        except Exception as e:
            print(f"导入 XML 失败：{e}")
            return [], False

    def _parse_xml_item(self, elem: ET.Element) -> Dict[str, Any]:
        """
        解析 XML 元素为字典

        Args:
            elem: XML 元素

        Returns:
            字典
        """
        item = {
            'name': elem.get(self.attrs['title'], ''),
            'path': elem.get(self.attrs['path'], ''),
            'is_dir': elem.get(self.attrs['is_dir'], 'false').lower() == 'true',
            'children': []
        }

        # 递归解析子项
        for child in elem.findall(self.item_tag):
            child_item = self._parse_xml_item(child)
            item['children'].append(child_item)

        return item

    def validate(self, xml_items: List[Dict[str, Any]], work_dir: str) -> List[ValidationIssue]:
        """
        验证 XML 节点与实际文件的对应性

        Args:
            xml_items: XML 导入的树结构
            work_dir: 工作目录

        Returns:
            验证问题列表
        """
        issues = []

        for item in xml_items:
            self._validate_item(item, work_dir, issues, "")

        return issues

    def _validate_item(self, item: Dict[str, Any], work_dir: str,
                       issues: List[ValidationIssue], parent_path: str) -> None:
        """
        递归验证项

        Args:
            item: 项字典（name 为显示名，可能已去掉 .pdf）
            work_dir: 工作目录
            issues: 问题列表
            parent_path: 父节点相对路径
        """
        name = item.get('name', '')
        path = item.get('path', '')
        is_dir = item.get('is_dir', False)

        # XML 导入时 name 已去掉 .pdf，文件节点需补回后缀再查找
        check_names = [name]
        if not is_dir and name and not name.lower().endswith('.pdf'):
            check_names.append(name + '.pdf')

        def _find_existing(base: Path, names: list) -> str:
            """依次尝试各名称，返回第一个存在的路径，无则返回 None"""
            for n in names:
                # 用 os.path.join 避免 Path / string 含正斜杠导致 exists() 失效
                p = os.path.join(str(base), n)
                if os.path.exists(p):
                    return p
            return None

        full_path = f"{parent_path}/{name}" if parent_path else name

        # 检查路径存在性
        if path:
            # 用 normpath 规范化正/反斜杠，确保 Windows 下 exists() 正确
            norm = os.path.normpath(path)
            if is_dir:
                if not os.path.exists(norm):
                    issues.append(ValidationIssue(
                        node_name=name,
                        node_path=full_path,
                        issue_type='missing_dir',
                        description=f"目录不存在：{path}"
                    ))
                elif not os.path.isdir(norm):
                    issues.append(ValidationIssue(
                        node_name=name,
                        node_path=full_path,
                        issue_type='type_mismatch',
                        description=f"类型不匹配，应为目录：{path}"
                    ))
            else:
                if not os.path.exists(norm):
                    issues.append(ValidationIssue(
                        node_name=name,
                        node_path=full_path,
                        issue_type='missing_file',
                        description=f"文件不存在：{path}"
                    ))
                elif os.path.isdir(norm):
                    issues.append(ValidationIssue(
                        node_name=name,
                        node_path=full_path,
                        issue_type='type_mismatch',
                        description=f"类型不匹配，应为文件：{path}"
                    ))
        else:
            # 没有路径，尝试在工作目录中查找（用 parent_path 补全嵌套目录）
            base_dir = (Path(work_dir) / parent_path) if parent_path else Path(work_dir)
            existing = _find_existing(base_dir, check_names)
            if is_dir:
                if not existing:
                    issues.append(ValidationIssue(
                        node_name=name,
                        node_path=full_path,
                        issue_type='missing_dir',
                        description=f"目录不存在（在工作目录中未找到）：{full_path}"
                    ))
            else:
                if not existing:
                    issues.append(ValidationIssue(
                        node_name=name,
                        node_path=full_path,
                        issue_type='missing_file',
                        description=f"文件不存在（在工作目录中未找到）：{full_path}"
                    ))

        # 递归验证子项
        for child in item.get('children', []):
            self._validate_item(child, work_dir, issues, full_path)

    def items_to_tree_items(self, xml_items: List[Dict[str, Any]]) -> List[TreeItem]:
        """
        将 XML 导入的字典列表转换为 TreeItem 列表

        Args:
            xml_items: XML 导入的字典列表

        Returns:
            TreeItem 列表
        """
        result = []
        for item_data in xml_items:
            item = TreeItem.from_dict(item_data)
            result.append(item)
        return result


def export_to_xml(tree_items: List[TreeItem], output_path: str) -> bool:
    """便捷函数：导出到 XML"""
    handler = XMLHandler()
    return handler.export_to_xml(tree_items, output_path)


def import_from_xml(xml_path: str) -> Tuple[List[Dict[str, Any]], bool]:
    """便捷函数：从 XML 导入"""
    handler = XMLHandler()
    return handler.import_from_xml(xml_path)


def validate_xml(xml_items: List[Dict[str, Any]], work_dir: str) -> List[ValidationIssue]:
    """便捷函数：验证 XML"""
    handler = XMLHandler()
    return handler.validate(xml_items, work_dir)


def items_to_tree_items(xml_items: List[Dict[str, Any]]) -> List[TreeItem]:
    """便捷函数：将 XML 字典列表转换为 TreeItem 列表"""
    handler = XMLHandler()
    return handler.items_to_tree_items(xml_items)
