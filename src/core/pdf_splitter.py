"""
PDF 拆分引擎 - 按书签拆分为目录结构和多个 PDF 文件
"""
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Optional, Callable
from pathlib import Path

from pypdf import PdfReader, PdfWriter


class OutlineNode:
    """书签树节点"""
    def __init__(self, title: str, page_index: Optional[int] = None,
                 raw_item=None):
        self.title = title
        self.page_index = page_index
        self.start_page: Optional[int] = None
        self.end_page: Optional[int] = None
        self.children: List['OutlineNode'] = []
        self.parent: Optional['OutlineNode'] = None
        self.raw_item = raw_item  # 原始书签对象

    def add_child(self, child: 'OutlineNode') -> None:
        child.parent = self
        self.children.append(child)

    def is_leaf(self) -> bool:
        """叶子节点：无子节点"""
        return len(self.children) == 0


class PDFSplitter:
    """
    PDF 拆分引擎

    书签结构（merged.pdf 使用扁平 + 内嵌子列表格式）：
    outline = [DEST, LIST, DEST, LIST, ...]
    LIST = [DEST, LIST, DEST, LIST, DEST, LIST, ...]

    规则：
    - 顶级交替：[DEST(目录), LIST(其子节点们)]
    - 子节点中：[目录A, LIST(A的子), 目录B, LIST(B的子), 叶子, 叶子, ...]
    - Count>0 = 目录，Count=0 = 叶子
    - 合并的逆过程：目录节点建文件夹，叶子节点提取为 PDF
    """

    def __init__(self):
        self._reader: Optional[PdfReader] = None

    def split_by_outline(self,
                         input_path: str,
                         output_dir: str,
                         progress_callback: Optional[Callable[[int, int, str], None]] = None
                         ) -> bool:
        try:
            self._reader = PdfReader(input_path)
            num_pages = len(self._reader.pages)

            outline = self._reader.outline
            if not outline or len(outline) == 0:
                if progress_callback:
                    progress_callback(1, 1, "无书签，整体复制")
                self._copy_pdf(self._reader, output_dir, "完整文档.pdf")
                if progress_callback:
                    progress_callback(1, 1, "完成")
                return True

            # 构建书签树
            root = self._build_outline_tree(outline)

            if not root.children:
                self._copy_pdf(self._reader, output_dir, "完整文档.pdf")
                # 导出空书签 XML
                xml_path = str(Path(output_dir) / "outline.xml")
                self._export_outline_to_xml(root, xml_path)
                if progress_callback:
                    progress_callback(1, 1, "完成")
                return True

            leaf_count = self._count_leaves(root)
            if leaf_count == 0:
                self._copy_pdf(self._reader, output_dir, "完整文档.pdf")
                xml_path = str(Path(output_dir) / "outline.xml")
                self._export_outline_to_xml(root, xml_path)
                if progress_callback:
                    progress_callback(1, 1, "完成")
                return True

            # 分配页面范围
            self._assign_page_ranges(root, num_pages)

            Path(output_dir).mkdir(parents=True, exist_ok=True)

            if progress_callback:
                progress_callback(0, leaf_count, "开始拆分")

            counter = [0]
            self._extract_leaves(root, Path(output_dir), progress_callback, counter, leaf_count)

            # 导出书签结构为 XML
            xml_path = str(Path(output_dir) / "outline.xml")
            self._export_outline_to_xml(root, xml_path)

            if progress_callback:
                progress_callback(leaf_count, leaf_count, "完成")

            return True

        except Exception as e:
            import traceback
            print(f"拆分 PDF 失败：{e}")
            traceback.print_exc()
            if progress_callback:
                progress_callback(0, 0, f"错误: {e}")
            return False

    def _build_outline_tree(self, outline) -> OutlineNode:
        """从 outline 扁平结构构建书签树"""
        root = OutlineNode("root")
        i = 0
        while i < len(outline):
            item = outline[i]
            if isinstance(item, list):
                i += 1
                continue
            count = item.get("/Count", 0)
            title = self._get_title(item)
            page_idx = self._resolve_page_index(item)
            if count > 0 and i + 1 < len(outline) and isinstance(outline[i + 1], list):
                dir_node = OutlineNode(title[:100], page_idx, raw_item=item)
                root.add_child(dir_node)
                self._parse_child_list(outline[i + 1], dir_node)
                i += 2
            elif count == 0:
                leaf_node = OutlineNode(title[:100], page_idx, raw_item=item)
                root.add_child(leaf_node)
                i += 1
            else:
                i += 1
        return root

    def _parse_child_list(self, child_list, parent_node) -> None:
        """递归下降解析子列表"""
        i = 0
        while i < len(child_list):
            item = child_list[i]
            if isinstance(item, list):
                i += 1
                continue
            title = self._get_title(item)
            count = item.get("/Count", 0)
            page_idx = self._resolve_page_index(item)
            if count > 0:
                dir_node = OutlineNode(title[:100], page_idx, raw_item=item)
                parent_node.add_child(dir_node)
                if i + 1 < len(child_list) and isinstance(child_list[i + 1], list):
                    self._parse_child_list(child_list[i + 1], dir_node)
                    i += 2
                else:
                    i += 1
            else:
                leaf_node = OutlineNode(title[:100], page_idx, raw_item=item)
                parent_node.add_child(leaf_node)
                i += 1

    def _get_title(self, item) -> str:
        try:
            return str(item.title) if hasattr(item, 'title') else "未命名书签"
        except:
            return "未命名书签"

    def _resolve_page_index(self, item) -> Optional[int]:
        """解析书签项的页码索引（0-based）"""
        try:
            page_obj = item.page
            if page_obj is None:
                return None
            # 获取书签引用的间接引用
            item_ref = getattr(page_obj, 'indirect_reference', None)
            if item_ref is None:
                return None
            for idx, pg in enumerate(self._reader.pages):
                pg_ref = getattr(pg, 'indirect_reference', None)
                if pg_ref is not None and pg_ref == item_ref:
                    return idx
            return None
        except:
            return None

    def _count_leaves(self, node: OutlineNode) -> int:
        if not node.children:
            return 1
        return sum(self._count_leaves(c) for c in node.children)

    def _assign_page_ranges(self, node: OutlineNode, total_pages: int) -> None:
        """
        为所有节点分配页面范围 [start, end)

        规则（合并的逆过程）：
        - 叶子节点（Count=0）：提取 bookmark 页码 ~ 下一个同级叶子页码
        - 目录节点（Count>0）：start=第一个子节点start，end=最后一个子节点end
        """
        if not node.children:
            # 叶子节点
            if node.page_index is None:
                node.page_index = 0
            node.start_page = node.page_index
            node.end_page = node.page_index + 1
            return

        # 目录节点：先递归计算所有子节点范围
        for child in node.children:
            self._assign_page_ranges(child, total_pages)

        # 目录节点的范围 = 子节点范围
        node.start_page = self._first_child_start(node)
        node.end_page = self._last_child_end(node)

        # 直接修正叶子兄弟节点之间的边界
        # （只修当前层的叶子，子层已由递归修正）
        siblings = node.children
        for j in range(len(siblings) - 1):
            curr = siblings[j]
            next_sib = siblings[j + 1]
            if curr.end_page is not None and next_sib.start_page is not None:
                if curr.end_page > next_sib.start_page:
                    # curr 是叶子：直接修正
                    if not curr.children:
                        curr.end_page = next_sib.start_page
                    else:
                        # curr 是目录：修正其最后一个叶子
                        self._set_last_leaf_end(curr, next_sib.start_page)

        # 顶层最后一个叶子到文档末尾
        if node.parent is None:
            if siblings:
                last = siblings[-1]
                if not last.children:
                    last.end_page = total_pages
                else:
                    self._set_last_leaf_end(last, total_pages)

    def _first_child_start(self, node: OutlineNode) -> int:
        if not node.children:
            return node.start_page if node.start_page is not None else 0
        return self._first_child_start(node.children[0])

    def _last_child_end(self, node: OutlineNode) -> int:
        if not node.children:
            return node.end_page if node.end_page is not None else node.start_page + 1
        return self._last_child_end(node.children[-1])

    def _find_last_leaf_node(self, node: OutlineNode) -> OutlineNode:
        if not node.children:
            return node
        return self._find_last_leaf_node(node.children[-1])

    def _set_last_leaf_end(self, node: OutlineNode, end: int) -> None:
        if not node.children:
            node.end_page = end
        else:
            self._set_last_leaf_end(node.children[-1], end)

    def _first_leaf_start(self, node: OutlineNode) -> Optional[int]:
        if not node.children:
            return node.start_page
        return self._first_leaf_start(node.children[0])

    def _extract_leaves(self, node: OutlineNode, base_path: Path,
                       progress_callback: Optional[Callable],
                       counter: list, total: int) -> None:
        """递归创建目录结构并提取叶子 PDF"""
        for child in node.children:
            safe_name = self._sanitize_filename(child.title)
            if not safe_name:
                safe_name = "未命名"

            if child.children:  # is_dir
                dir_path = base_path / safe_name
                dir_path.mkdir(parents=True, exist_ok=True)
                self._extract_leaves(child, dir_path, progress_callback, counter, total)
            else:  # is_leaf
                counter[0] += 1
                if progress_callback:
                    progress_callback(counter[0], total, safe_name)

                sp = child.start_page if child.start_page is not None else 0
                ep = child.end_page if child.end_page is not None else sp + 1
                # 书签标题可能已含 .pdf，避免生成 .pdf.pdf 双后缀
                if safe_name.lower().endswith('.pdf'):
                    pdf_filename = safe_name
                else:
                    pdf_filename = f"{safe_name}.pdf"
                pdf_path = base_path / pdf_filename
                self._extract_pages(sp, ep, pdf_path)

    def _extract_pages(self, start_page: int, end_page: int, output_path: Path) -> None:
        """提取页面范围到 PDF"""
        writer = PdfWriter()
        total_pages = len(self._reader.pages)
        sp = max(0, min(start_page, total_pages - 1))
        ep = max(sp + 1, min(end_page, total_pages))
        for page_num in range(sp, ep):
            writer.add_page(self._reader.pages[page_num])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer.write(str(output_path))

    def _copy_pdf(self, reader: PdfReader, output_dir: str, filename: str) -> None:
        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.write(str(output_path))

    def _sanitize_filename(self, filename: str) -> str:
        safe = re.sub(r'[/\\:*?"<>|]', '', filename)
        safe = safe.strip(' .')
        return safe[:100] if safe else ""

    def _export_outline_to_xml(self, root: OutlineNode, output_path: str) -> None:
        """
        将书签树导出为 XML 文件（与 xml_handler 格式兼容）

        Args:
            root: 书签树根节点
            output_path: 输出路径
        """
        try:
            xml_root = ET.Element("pdf-outline")
            xml_root.set("version", "1.0")
            self._outline_node_to_xml(root, xml_root)

            rough = ET.tostring(xml_root, encoding='utf-8')
            pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

            # 去掉 minidom 多余的空行
            lines = [l for l in pretty.splitlines() if l.strip()]
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            print(f"导出书签 XML 失败：{e}")

    def _outline_node_to_xml(self, node: OutlineNode, xml_parent: ET.Element) -> None:
        """递归将 OutlineNode 转换为 XML"""
        for child in node.children:
            elem = ET.SubElement(xml_parent, "outline-item")
            elem.set("title", child.title)
            elem.set("path", "")  # 拆分后的虚拟节点无实际文件路径
            elem.set("is-dir", "true" if child.children else "false")
            self._outline_node_to_xml(child, elem)


def split_pdf(input_path: str,
              output_dir: str,
              progress_callback: Optional[Callable[[int, int, str], None]] = None
              ) -> bool:
    """便捷函数"""
    splitter = PDFSplitter()
    return splitter.split_by_outline(input_path, output_dir, progress_callback)
