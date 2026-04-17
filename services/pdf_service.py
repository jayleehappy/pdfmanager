"""
PDF 处理服务
将 PDF 转换为图片
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Optional
import uuid
import os


class PDFService:
    """PDF 处理服务"""

    def __init__(self, dpi: int = 200):
        """
        初始化

        Args:
            dpi: 图片分辨率，默认 200 DPI
        """
        self.dpi = dpi

    def pdf_to_images(
        self,
        pdf_path: str | Path,
        pages: Optional[List[int]] = None,
        output_dir: Optional[Path] = None
    ) -> List[str]:
        """
        将 PDF 转换为图片

        Args:
            pdf_path: PDF 文件路径
            pages: 要转换的页面列表，None 表示全部
            output_dir: 输出目录，默认使用临时目录

        Returns:
            图片路径列表
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        # 创建临时输出目录
        if output_dir is None:
            output_dir = pdf_path.parent / "temp_images"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 打开 PDF
        doc = fitz.open(pdf_path)

        # 确定要处理的页面
        if pages is None:
            page_indices = list(range(len(doc)))
        else:
            # 转换为 0 基索引
            page_indices = [p - 1 for p in pages if 1 <= p <= len(doc)]

        images = []

        for i, page_idx in enumerate(page_indices):
            page = doc[page_idx]

            # 计算缩放因子
            zoom = self.dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            # 渲染页面为图片
            clip = page.rect
            pix = page.get_pixmap(matrix=mat, clip=clip)

            # 生成输出文件名
            output_path = output_dir / f"page_{page_idx + 1:03d}.png"
            pix.save(str(output_path))
            images.append(str(output_path))

        doc.close()

        return images

    def get_page_count(self, pdf_path: str | Path) -> int:
        """
        获取 PDF 页数

        Args:
            pdf_path: PDF 文件路径

        Returns:
            页数
        """
        pdf_path = Path(pdf_path)
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    def extract_text(
        self,
        pdf_path: str | Path,
        pages: Optional[List[int]] = None
    ) -> dict:
        """
        提取 PDF 文本（不使用 OCR）

        Args:
            pdf_path: PDF 文件路径
            pages: 要提取的页面列表，None 表示全部

        Returns:
            包含每页文本的字典
        """
        pdf_path = Path(pdf_path)
        doc = fitz.open(pdf_path)

        if pages is None:
            page_indices = list(range(len(doc)))
        else:
            page_indices = [p - 1 for p in pages if 1 <= p <= len(doc)]

        result = {}
        for i, page_idx in enumerate(page_indices):
            page = doc[page_idx]
            text = page.get_text()
            result[page_idx + 1] = text

        doc.close()
        return result
