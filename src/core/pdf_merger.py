"""
PDF 合并引擎 - 按树结构顺序合并 PDF 并生成嵌套书签
"""
import os
from typing import List, Optional, Callable, Dict, Any
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from .tree_manager import TreeItem


class PDFMerger:
    """
    PDF 合并引擎
    按照树结构的顺序合并 PDF 文件，并生成对应的书签/大纲
    """

    def __init__(self):
        self.writer = None
        self.page_offset = 0  # 当前页码偏移量
        self.bookmarks = []   # 书签列表
        self.progress_callback = None
        self.total_files = 0
        self.processed_files = 0
        self.work_dir = ""
        self._pregenerated_paths: set = set()  # 预生成空白页的路径集合

    def merge_with_outline(self,
                           tree_items: List[TreeItem],
                           output_path: str,
                           work_dir: str = "",
                           progress_callback: Optional[Callable[[int, int, str], None]] = None,
                           pregenerated_paths: Optional[set] = None
                           ) -> bool:
        """
        合并 PDF 文件并生成嵌套书签

        Args:
            tree_items: 树项列表（包含目录结构）
            output_path: 输出文件路径
            work_dir: 工作目录（resolve_path 为空时使用）
            progress_callback: 进度回调函数
            pregenerated_paths: 预生成空白页的路径集合（跳过读取，直接追加空白页）

        Returns:
            是否成功
        """
        self.work_dir = work_dir
        self._pregenerated_paths = pregenerated_paths or set()
        try:
            self.writer = PdfWriter()
            self.page_offset = 0
            self.bookmarks = []
            self.progress_callback = progress_callback

            # 先统计 PDF 文件数量
            self.total_files = self._count_pdf_files(tree_items)
            self.processed_files = 0

            # 递归处理树结构，添加文件和书签
            for item in tree_items:
                self._process_tree_item(item)

            # 写入输出文件
            self.writer.write(output_path)

            # 完成进度
            if progress_callback:
                progress_callback(self.total_files, self.total_files, "完成")

            return True

        except Exception as e:
            print(f"合并 PDF 失败：{e}")
            return False

    def _count_pdf_files(self, items: List[TreeItem]) -> int:
        """统计 PDF 文件数量（含虚拟书签占位节点）"""
        count = 0
        for item in items:
            resolved = item.resolve_path(self.work_dir)
            if not item.is_dir:
                # 虚拟书签（path 为空）也计入，合并时将插入空白页占位
                if resolved.lower().endswith('.pdf') or not resolved:
                    count += 1
            else:
                count += self._count_pdf_files(item.children)
        return count

    def _process_tree_item(self, item: TreeItem, parent_bookmark=None) -> None:
        """
        递归处理树项

        Args:
            item: 树项
            parent_bookmark: 父书签引用
        """
        if not item.is_dir:
            # 文件节点
            resolved = item.resolve_path(self.work_dir)

            # 判断是否为虚拟书签
            # 注意：XML导入的节点 path='' 但 resolve_path 可以重建路径，此时应作为真实文件处理
            is_virtual = not item.path  # path为空可能是虚拟书签
            if is_virtual:
                # 检查 resolve 后的路径是否存在文件
                norm_resolved = os.path.normpath(resolved)
                file_exists = os.path.exists(norm_resolved)
                if file_exists:
                    # path为空但文件存在，说明是XML导入丢失path的情况，按真实文件处理
                    is_virtual = False

            if is_virtual:
                # 真正的虚拟书签：直接插入一页空白页占位
                self._add_blank_page_with_bookmark(item.name, parent_bookmark)
            elif resolved.lower().endswith('.pdf'):
                self._add_pdf_with_bookmark(item, resolved, parent_bookmark)
        else:
            # 目录节点 - 创建书签（如果有内容）
            bookmark = None
            has_pdf_children = self._has_pdf_descendants(item)

            if has_pdf_children:
                # 创建目录书签 - 使用当前的 item.name（可能是重命名后的）
                bookmark = self._create_bookmark(item.name, self.page_offset, parent_bookmark)

            # 递归处理子项
            for child in item.children:
                self._process_tree_item(child, bookmark)

    def _has_pdf_descendants(self, item: TreeItem) -> bool:
        """检查项是否有 PDF 后代（含虚拟书签占位节点）"""
        if not item.is_dir:
            # 虚拟书签（path=""）或真实文件节点均算有内容
            return not item.path or item.resolve_path(self.work_dir).lower().endswith('.pdf')
        for child in item.children:
            if self._has_pdf_descendants(child):
                return True
        return False

    def _add_pdf_with_bookmark(self, item: TreeItem, resolved_path: str, parent_bookmark) -> None:
        """
        添加 PDF 文件并创建书签

        Args:
            item: 树项（文件）
            resolved_path: 已解析的完整路径
            parent_bookmark: 父书签
        """
        # 预生成的空白页：不再读取内容，直接追加空白页（内容已在预检时生成到磁盘）
        # 使用规范化路径进行比较，确保格式一致
        norm_resolved = os.path.normpath(resolved_path)
        if norm_resolved in self._pregenerated_paths:
            self._add_blank_page_with_bookmark(item.name, parent_bookmark)
            return

        if not os.path.exists(norm_resolved):
            print(f"警告：文件不存在 - {resolved_path}")
            return

        start_page = self.page_offset

        # 添加 PDF
        self._add_pdf_to_writer(resolved_path)

        # 创建书签 - 使用 item.name（重命名后的显示名称）
        self._create_bookmark(item.name, start_page, parent_bookmark)

        # 更新进度
        self.processed_files += 1
        if self.progress_callback:
            self.progress_callback(self.processed_files, self.total_files, item.name)

    def _add_blank_page_with_bookmark(self, title: str, parent_bookmark) -> None:
        """
        为虚拟书签插入一页空白页并创建书签占位

        Args:
            title: 书签标题
            parent_bookmark: 父书签
        """
        from pypdf import PageObject
        # 创建空白页（A4）
        blank_page = PageObject.create_blank_page(width=595.28, height=841.89)
        self.writer.add_page(blank_page)
        start_page = self.page_offset
        self.page_offset += 1
        self._create_bookmark(f"[{title}]", start_page, parent_bookmark)
        self.processed_files += 1
        if self.progress_callback:
            self.progress_callback(self.processed_files, self.total_files, f"[{title}]（空白页）")

    def _add_pdf_to_writer(self, pdf_path: str) -> None:
        """
        添加 PDF 文件到写入器

        Args:
            pdf_path: PDF 文件路径
        """
        reader = PdfReader(pdf_path)
        self.writer.append_pages_from_reader(reader)
        self.page_offset += len(reader.pages)

    def _create_bookmark(self, title: str, page_number: int, parent=None):
        """
        创建书签

        Args:
            title: 书签标题（使用重命名后的名称）
            page_number: 页码（0-based）
            parent: 父书签

        Returns:
            书签引用
        """
        try:
            # pypdf 6.x API: add_outline_item
            bookmark = self.writer.add_outline_item(title, page_number, parent=parent)
            return bookmark
        except Exception as e:
            print(f"创建书签失败：{e}")
            return None


    def _collect_missing_nodes(self, items: List['TreeItem']) -> List[tuple]:
        """
        收集 resolved 路径不存在的文件节点（用于预生成空白页占位）。

        Args:
            items: 树项列表

        Returns:
            [(TreeItem, resolved_path), ...] — resolved 路径不存在的文件节点
        """
        missing = []
        for item in items:
            if item.is_dir:
                missing.extend(self._collect_missing_nodes(item.children))
            else:
                resolved = item.resolve_path(self.work_dir)
                norm_resolved = os.path.normpath(resolved)
                exists = os.path.exists(norm_resolved)
                # 新添加的虚拟书签: path为空 且 resolve后文件不存在
                if not item.path and not exists:
                    missing.append((item, resolved))
        return missing

    def _write_blank_pdf(self, output_path: str) -> None:
        """将一页空白 PDF 写入磁盘（作为缺失文件的占位）"""
        from pypdf import PageObject
        writer = PdfWriter()
        blank_page = PageObject.create_blank_page(width=595.28, height=841.89)
        writer.add_page(blank_page)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        writer.write(output_path)


def merge_pdfs(tree_items: List[TreeItem],
               output_path: str,
               work_dir: str = "",
               progress_callback: Optional[Callable[[int, int, str], None]] = None,
               pregenerated_paths: Optional[set] = None
               ) -> bool:
    """
    便捷函数：合并 PDF 文件（带书签）

    Args:
        tree_items: 树项列表
        output_path: 输出路径
        work_dir: 工作目录
        progress_callback: 进度回调
        pregenerated_paths: 预生成空白页的路径集合

    Returns:
        是否成功
    """
    merger = PDFMerger()
    return merger.merge_with_outline(tree_items, output_path, work_dir, progress_callback, pregenerated_paths)
