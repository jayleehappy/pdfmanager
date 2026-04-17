"""
PaddleOCR V5 引擎封装

使用 PaddleOCR Python 包，集成 PP-OCRv5 模型。
参考：https://www.paddleocr.ai/latest/version3.x/pipeline_usage/OCR.html
"""
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# 模型目录（使用 PaddleX 下载的模型）
PADDLEX_MODELS_PATH = Path(__file__).parent.parent / ".paddlex" / "official_models"

# 单例模式
_paddle_ocr_instance: Optional["PaddleOcrV5Engine"] = None


class PaddleOcrV5Engine:
    """
    PaddleOCR V5 引擎封装类

    使用 PaddleOCR Python 包，调用 PP-OCRv5 模型进行 OCR 识别。
    """

    def __init__(
        self,
        det_model_dir: str = None,
        rec_model_dir: str = None,
        lang: str = "ch",
        enable_mkldnn: bool = True,
        cpu_threads: int = 8,
        use_angle_cls: bool = False,
        use_doc_orientation_classify: bool = False,
        use_doc_unwarping: bool = False,
        use_textline_orientation: bool = False,
    ):
        """
        初始化 OCR 引擎

        Args:
            det_model_dir: 文本检测模型目录路径，默认使用 V5 服务端检测模型
            rec_model_dir: 文本识别模型目录路径，默认使用 V5 服务端识别模型
            lang: 语言，默认中文 "ch"
            enable_mkldnn: 是否启用 MKL-DNN 加速（默认 True，提升 CPU 性能）
            cpu_threads: CPU 线程数，默认 8
            use_angle_cls: 是否启用方向分类（默认 False）
            use_doc_orientation_classify: 是否启用文档方向分类（默认 False）
            use_doc_unwarping: 是否启用文档去扭曲（默认 False）
            use_textline_orientation: 是否启用文本行方向分类（默认 False）
        """
        self._ocr = None
        self._enable_mkldnn = enable_mkldnn
        self._cpu_threads = cpu_threads
        self._init_engine(
            det_model_dir=det_model_dir,
            rec_model_dir=rec_model_dir,
            lang=lang,
            use_angle_cls=use_angle_cls,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
        )

    def _init_engine(self, **kwargs):
        """初始化 PaddleOCR 引擎"""
        try:
            from paddleocr import PaddleOCR

            # 默认使用 V5 模型
            ocr_params = {
                "ocr_version": "PP-OCRv5",
                "enable_mkldnn": self._enable_mkldnn,
                "cpu_threads": self._cpu_threads,
                "use_angle_cls": kwargs.get("use_angle_cls", False),
                "use_doc_orientation_classify": kwargs.get("use_doc_orientation_classify", False),
                "use_doc_unwarping": kwargs.get("use_doc_unwarping", False),
                "use_textline_orientation": kwargs.get("use_textline_orientation", False),
                "show_log": False,  # 关闭日志输出
            }

            # 设置语言
            lang = kwargs.get("lang", "ch")
            if lang == "ch":
                ocr_params["lang"] = "ch"
            elif lang == "en":
                ocr_params["lang"] = "en"
            elif lang == "japan":
                ocr_params["lang"] = "japan"
            elif lang == "korean":
                ocr_params["lang"] = "korean"
            elif lang == "chinese_cht":
                ocr_params["lang"] = "chinese_cht"

            # 如果指定了模型目录，使用本地模型
            det_model_dir = kwargs.get("det_model_dir")
            rec_model_dir = kwargs.get("rec_model_dir")

            if det_model_dir and os.path.exists(det_model_dir):
                ocr_params["det_model_dir"] = det_model_dir
                logger.info(f"使用本地检测模型: {det_model_dir}")

            if rec_model_dir and os.path.exists(rec_model_dir):
                ocr_params["rec_model_dir"] = rec_model_dir
                logger.info(f"使用本地识别模型: {rec_model_dir}")

            # 初始化引擎
            self._ocr = PaddleOCR(**ocr_params)
            logger.info(f"PaddleOCR V5 引擎初始化成功，参数: {ocr_params}")

        except Exception as e:
            logger.error(f"PaddleOCR V5 引擎初始化失败: {e}")
            raise

    def recognize(self, image_path: str) -> list[dict]:
        """
        识别图片中的文字

        Args:
            image_path: 图片路径

        Returns:
            list[dict]: OCR 结果列表，每项格式：
            {
                "text": "识别的文本",
                "score": 0.998,
                "box": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            }
        """
        if self._ocr is None:
            logger.error("OCR 引擎未初始化")
            return []

        try:
            result = self._ocr.ocr(image_path, cls=False)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return []

    def recognize_array(self, image: np.ndarray) -> list[dict]:
        """
        识别 numpy 数组格式的图片

        Args:
            image: numpy.ndarray 格式的图片

        Returns:
            list[dict]: OCR 结果列表
        """
        if self._ocr is None:
            logger.error("OCR 引擎未初始化")
            return []

        try:
            result = self._ocr.ocr(image, cls=False)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return []

    def _parse_result(self, result) -> list[dict]:
        """
        解析 PaddleOCR 返回结果

        Args:
            result: PaddleOCR 返回的原始结果

        Returns:
            list[dict]: 标准化后的结果列表
        """
        if result is None or len(result) == 0:
            logger.debug("未识别到任何结果")
            return []

        items = []
        # PaddleOCR 返回格式: [[box, text, score], ...] 或 [[[box, text, score], ...]]
        for page_result in result:
            if page_result is None:
                continue
            for line in page_result:
                if line is None or len(line) < 3:
                    continue
                box = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text = line[1]  # 识别的文本
                score = line[2] if len(line) > 2 else 1.0  # 置信度

                # 转换 box 格式为整数
                box_int = [[int(x), int(y)] for x, y in box]

                items.append({
                    "text": str(text).strip(),
                    "score": float(score),
                    "box": box_int
                })

        return items

    def extract_text(self, image_path: str) -> str:
        """
        仅提取文本内容（不含坐标）

        Args:
            image_path: 图片路径

        Returns:
            str: 拼接的文本内容
        """
        items = self.recognize(image_path)
        return "".join(item["text"] for item in items)

    def __del__(self):
        """清理资源"""
        if hasattr(self, "_ocr"):
            self._ocr = None


def get_paddle_ocr_engine() -> PaddleOcrV5Engine:
    """
    获取 PaddleOCR V5 引擎单例

    Returns:
        PaddleOcrV5Engine: OCR 引擎实例
    """
    global _paddle_ocr_instance
    if _paddle_ocr_instance is None:
        _paddle_ocr_instance = PaddleOcrV5Engine()
    return _paddle_ocr_instance


def recognize_image(image_path: str) -> list[dict]:
    """识别图片（便捷函数）"""
    return get_paddle_ocr_engine().recognize(image_path)


def extract_text_from_image(image_path: str) -> str:
    """提取图片文本（便捷函数）"""
    return get_paddle_ocr_engine().extract_text(image_path)
