"""
OCR 协调器

整合区域裁剪和 OCR 识别，处理扫描件的完整流程：
1. 加载模板的区域定义
2. 根据区域坐标裁剪图片
3. 调用 PaddleOCR-json 识别裁剪区域
4. 返回结构化结果
"""
import logging
import time
from typing import Optional

import cv2
import numpy as np

from api.region_crop import crop_regions, image_to_base64, load_regions
from lib.paddle_ocr_engine import get_paddle_ocr_engine

logger = logging.getLogger(__name__)


class OcrCoordinator:
    """
    OCR 协调器

    整合区域裁剪和 OCR 识别，提供统一的扫描件处理接口。
    """

    def __init__(self):
        """初始化 OCR 协调器"""
        self.ocr_engine = get_paddle_ocr_engine()
        logger.info("OCR 协调器初始化完成")

    def process_page(self, image: np.ndarray, template_id: int) -> dict[str, str]:
        """
        处理单页扫描件

        Args:
            image: 扫描页图片 (H, W, C) RGB 格式
            template_id: 模板 ID（1-21）

        Returns:
            dict[str, str]: 字段名到识别文本的映射
            {
                "报告日期": "2024-01-01",
                "阅签日期": "2024-01-15",
                ...
            }
        """
        start_time = time.time()

        # 1. 加载区域定义
        regions = load_regions(template_id)
        if not regions:
            logger.warning(f"模板 {template_id} 没有定义区域")
            return {}

        # 2. 区域裁剪
        cropped = crop_regions(image, regions)
        if not cropped:
            logger.warning(f"模板 {template_id} 裁剪结果为空")
            return {}

        # 3. 逐个区域 OCR
        results = {}
        for label, img in cropped:
            # BGR 格式（PaddleOCR 内部用 OpenCV）
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            _, buf = cv2.imencode('.png', img_bgr)
            import base64
            b64 = base64.b64encode(buf).decode('utf-8')

            # OCR 识别
            ocr_items = self.ocr_engine.recognize_base64(b64)

            # 拼接文本
            text = self._concat_text(ocr_items)
            results[label] = text.strip()

        elapsed = time.time() - start_time
        logger.info(f"模板 {template_id} 处理完成，{len(results)} 个字段，耗时 {elapsed:.2f}s")

        return results

    def process_image_path(self, image_path: str, template_id: int) -> dict[str, str]:
        """
        处理图片文件

        Args:
            image_path: 图片路径
            template_id: 模板 ID

        Returns:
            dict[str, str]: 字段名到识别文本的映射
        """
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"无法加载图片: {image_path}")
            return {}

        # BGR -> RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return self.process_page(img_rgb, template_id)

    def _concat_text(self, ocr_items: list[dict]) -> str:
        """
        从 OCR 结果拼接文本

        Args:
            ocr_items: OCR 识别结果列表

        Returns:
            拼接后的文本
        """
        if not ocr_items:
            return ""

        # 按从上到下、从左到右的顺序拼接
        return "".join(item["text"] for item in ocr_items if item.get("text"))

    def process_batch(
        self, images: list[np.ndarray], template_ids: list[int]
    ) -> list[dict]:
        """
        批量处理多页扫描件

        Args:
            images: 扫描页图片列表
            template_ids: 对应的模板 ID 列表

        Returns:
            list[dict]: 每页的处理结果
            [
                {"page": 1, "template_id": 1, "fields": {...}},
                {"page": 2, "template_id": 2, "fields": {...}},
                ...
            ]
        """
        results = []
        total_time = time.time()

        for i, (img, tpl_id) in enumerate(zip(images, template_ids)):
            page_start = time.time()
            fields = self.process_page(img, tpl_id)
            page_time = time.time() - page_start

            results.append({
                "page": i + 1,
                "template_id": tpl_id,
                "fields": fields,
                "elapsed": page_time,
            })

        total_time = time.time() - total_time
        logger.info(f"批量处理完成，{len(results)} 页，总耗时 {total_time:.2f}s")

        return results
