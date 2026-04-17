"""
模板对比服务
通过图像差分检测扫描件中与模板不同的区域（手写内容）
支持：模板预拆分 + 扫描页与模板页最佳匹配
"""

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


class TemplateCompareService:
    """
    模板对比服务 - 检测差异区域

    核心逻辑：
    1. 启动时预加载模板 PDF，将每一页转为灰度图像数组，存入 self.template_pages
    2. 处理扫描件时，逐页与模板所有页计算结构相似度（SSIM）
    3. 选取相似度最高的模板页进行差分比对，识别差异区域
    """

    def __init__(self, dpi: int = 150, template_path: str | Path = None):
        """
        初始化：加载模板并拆分为单页图像

        Args:
            dpi: 图像分辨率，默认 150 DPI
            template_path: 模板 PDF 路径，默认使用项目内置模板
        """
        self.dpi = dpi
        self.template_pages: List[np.ndarray] = []
        self.template_path = None

        if template_path is None:
            base = Path(__file__).parent.parent
            template_path = base / "templates" / "PDFtemplates.pdf"

        self.load_template(template_path)

    def load_template(self, template_path: str | Path) -> int:
        """
        加载模板 PDF 并拆分为单页灰度图像

        Args:
            template_path: 模板 PDF 路径

        Returns:
            模板页数
        """
        p = Path(template_path)
        if not p.exists():
            logger.warning(f"[TemplateService] 模板文件不存在: {template_path}")
            return 0

        self.template_path = str(p)
        doc = fitz.open(str(p))
        self.template_pages = []

        for i in range(len(doc)):
            img = self._pdf_page_to_gray_array(doc[i])
            self.template_pages.append(img)

        doc.close()
        logger.info(f"[TemplateService] 模板加载完成，共 {len(self.template_pages)} 页")
        return len(self.template_pages)

    def _pdf_page_to_gray_array(self, page) -> np.ndarray:
        """将 PDF 单页转为灰度 numpy 数组"""
        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # 转为临时 PNG 再读取为灰度数组
        fd, temp_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        pix.save(temp_path)
        img = np.array(Image.open(temp_path).convert('L'))
        os.unlink(temp_path)
        return img

    def _compute_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """
        计算两张灰度图像的结构相似度（SSIM）

        Args:
            img1, img2: 灰度图像数组（尺寸可以不同，会自动归一化）

        Returns:
            SSIM 值，范围 [-1, 1]，越大越相似
        """
        # 归一化尺寸（以较小者为目标，防止放大）
        h1, w1 = img1.shape
        h2, w2 = img2.shape
        target_h, target_w = min(h1, h2), min(w1, w2)

        if h1 != target_h or w1 != target_w:
            img1 = np.array(Image.fromarray(img1).resize((target_w, target_h), Image.LANCZOS))
        if h2 != target_h or w2 != target_w:
            img2 = np.array(Image.fromarray(img2).resize((target_w, target_h), Image.LANCZOS))

        # 使用 skimage 的 SSIM
        try:
            from skimage.metrics import structural_similarity as ssim
            score = ssim(img1, img2, data_range=255)
            return float(score)
        except ImportError:
            # fallback: 简化版相似度（灰度直方图相关系数）
            h1_norm = img1.flatten().astype(float) / 255
            h2_norm = img2.flatten().astype(float) / 255
            correlation = np.corrcoef(h1_norm, h2_norm)[0, 1]
            return float(correlation) if not np.isnan(correlation) else 0.0

    def compare_pages(self, scan_page: np.ndarray) -> int:
        """
        找出与扫描页最相似的模板页索引

        Args:
            scan_page: 扫描件单页灰度图像

        Returns:
            最佳匹配的模板页索引（从 0 开始）
        """
        if not self.template_pages:
            logger.warning("[TemplateService] 无模板页可用")
            return 0

        best_idx = 0
        best_score = -1.0

        for i, tpl_page in enumerate(self.template_pages):
            score = self._compute_ssim(scan_page, tpl_page)
            if score > best_score:
                best_score = score
                best_idx = i

        logger.info(f"[TemplateService] 最佳匹配: 模板第 {best_idx + 1} 页 "
                    f"(SSIM={best_score:.3f}, 扫描页尺寸={scan_page.shape})")
        return best_idx

    def pdf_to_image(self, pdf_path: str | Path, page: int = 0) -> np.ndarray:
        """
        将 PDF 指定页面转为灰度图像数组

        Args:
            pdf_path: PDF 文件路径
            page: 页码（从 0 开始）

        Returns:
            灰度图像数组
        """
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))

        if page >= len(doc):
            raise ValueError(f"PDF 只有 {len(doc)} 页，请求 page {page} 超出范围")

        img = self._pdf_page_to_gray_array(doc[page])
        doc.close()
        return img

    def compute_diff_mask(
        self,
        template_img: np.ndarray,
        scan_img: np.ndarray,
        threshold: int = 30
    ) -> np.ndarray:
        """
        计算两张图像的差异遮罩

        Args:
            template_img: 模板图像（灰度数组）
            scan_img: 扫描件图像（灰度数组）
            threshold: 差异阈值，0-255，越低越敏感

        Returns:
            差异遮罩（二值数组，255=有差异）
        """
        # 尺寸已在 _normalize_image_size 中统一
        diff = np.abs(template_img.astype(int) - scan_img.astype(int))
        mask = (diff > threshold).astype(np.uint8) * 255
        return mask

    def find_diff_regions(
        self,
        mask: np.ndarray,
        min_area: int = 100,
        max_regions: int = 50
    ) -> List[Tuple[int, int, int, int]]:
        """
        从差异遮罩中找出差异区域（边界框）

        Args:
            mask: 差异遮罩（二值数组）
            min_area: 最小区域面积（像素）
            max_regions: 最大区域数量

        Returns:
            区域列表 [(x1, y1, x2, y2), ...]
        """
        from scipy import ndimage

        labeled, num_features = ndimage.label(mask)
        regions = []

        for i in range(1, num_features + 1):
            if len(regions) >= max_regions:
                break

            component = (labeled == i)
            coords = np.where(component)

            if len(coords[0]) < min_area:
                continue

            y1, y2 = int(coords[0].min()), int(coords[0].max())
            x1, x2 = int(coords[1].min()), int(coords[1].max())

            # 扩大边界（留边距）
            margin = 10
            y1 = max(0, y1 - margin)
            x1 = max(0, x1 - margin)
            y2 = min(mask.shape[0], y2 + margin)
            x2 = min(mask.shape[1], x2 + margin)

            regions.append((x1, y1, x2, y2))

        # 按面积排序，大的在前
        regions.sort(key=lambda r: (r[2]-r[0])*(r[3]-r[1]), reverse=True)
        return regions[:max_regions]

    def crop_region(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """
        从图像中裁剪区域

        Args:
            image: 原始图像
            bbox: 边界框 (x1, y1, x2, y2)

        Returns:
            裁剪后的图像
        """
        x1, y1, x2, y2 = bbox
        return image[y1:y2, x1:x2]

    def _normalize_image_size(
        self,
        img1: np.ndarray,
        img2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        将两张图像归一化到相同尺寸（通过缩放较大的图像）

        Args:
            img1, img2: 灰度图像数组

        Returns:
            (归一化后的 img1, 归一化后的 img2)
        """
        h1, w1 = img1.shape
        h2, w2 = img2.shape

        if h1 == h2 and w1 == w2:
            return img1, img2

        # 以较小尺寸为目标（避免放大引入人为差异）
        target_h, target_w = min(h1, h2), min(w1, w2)

        resized1 = img1
        if h1 != target_h or w1 != target_w:
            pil1 = Image.fromarray(img1).resize((target_w, target_h), Image.LANCZOS)
            resized1 = np.array(pil1)

        resized2 = img2
        if h2 != target_h or w2 != target_w:
            pil2 = Image.fromarray(img2).resize((target_w, target_h), Image.LANCZOS)
            resized2 = np.array(pil2)

        return resized1, resized2

    def compare_and_extract(
        self,
        template_pdf: str | Path,
        scan_pdf: str | Path,
        page: int = 0,
        threshold: int = 30,
        min_area: int = 200
    ) -> dict:
        """
        对比模板和扫描件，提取差异区域（自动页匹配版）

        Args:
            template_pdf: 模板 PDF 路径（仅用于兼容性保留，真实模板已在 __init__ 加载）
            scan_pdf: 扫描件 PDF 路径
            page: 扫描件页码（从 0 开始），用于从 PDF 读取；若传入 scan_img 则忽略
            threshold: 差异检测阈值
            min_area: 最小差异区域面积

        Returns:
            差异分析结果，包含 matched_template_page（最佳匹配模板页索引）
        """
        scan_path = Path(scan_pdf)
        if not scan_path.exists():
            raise FileNotFoundError(f"扫描件不存在: {scan_pdf}")

        doc = fitz.open(str(scan_path))
        if page >= len(doc):
            doc.close()
            raise ValueError(f"扫描件只有 {len(doc)} 页，请求 page {page} 超出范围")

        # 将扫描件指定页转为灰度图像
        scan_img = self._pdf_page_to_gray_array(doc[page])
        doc.close()

        logger.info(f"[TemplateService] 扫描件第 {page + 1} 页尺寸: {scan_img.shape}")

        # Step 1：找出最佳匹配的模板页
        matched_tpl_idx = self.compare_pages(scan_img)
        tpl_img = self.template_pages[matched_tpl_idx]

        logger.info(f"[TemplateService] 模板第 {matched_tpl_idx + 1} 页尺寸: {tpl_img.shape}，"
                    f"与扫描件进行差分比对")

        # Step 2：归一化尺寸（处理不同 DPI）
        tpl_img, scan_img_norm = self._normalize_image_size(tpl_img, scan_img)

        # Step 3：计算差分遮罩
        mask = self.compute_diff_mask(tpl_img, scan_img_norm, threshold)
        diff_pixel_count = int(np.sum(mask > 0))
        diff_ratio = diff_pixel_count / mask.size * 100

        logger.info(f"[TemplateService] 差异像素: {diff_pixel_count} ({diff_ratio:.2f}%)")

        # Step 4：提取差异区域
        regions = self.find_diff_regions(mask, min_area=min_area)
        logger.info(f"[TemplateService] 发现 {len(regions)} 个差异区域")

        return {
            "regions": regions,
            "scan_img": scan_img_norm,
            "diff_ratio": diff_ratio,
            "matched_template_page": matched_tpl_idx + 1,  # 1-indexed for readability
            "template_page_count": len(self.template_pages),
        }

    def save_debug_image(
        self,
        scan_img: np.ndarray,
        mask: np.ndarray,
        regions: List[Tuple[int, int, int, int]],
        output_path: str | Path
    ):
        """保存调试图像（显示差异区域）"""
        from PIL import ImageDraw

        pil_img = Image.fromarray(scan_img)
        draw = ImageDraw.Draw(pil_img)

        for i, (x1, y1, x2, y2) in enumerate(regions):
            draw.rectangle([x1, y1, x2, y2], outline='red', width=2)

        pil_img.save(str(output_path))
