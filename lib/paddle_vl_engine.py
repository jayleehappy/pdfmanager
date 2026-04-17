"""
PaddleOCR-VL 引擎封装

使用 PaddleOCRVL 视觉-语言模型，支持手写识别。
参考：https://github.com/PaddlePaddle/PaddleOCR

注意：PaddleOCR-VL 在 Windows 上可能需要 GPU 支持。
模型位于：D:\grsxbd\.paddlex\official_models\PaddleOCR-VL\
"""
import logging
import os
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

# 默认模型路径（当未传入 model_path 时使用）
DEFAULT_MODEL_PATH = Path(__file__).parent.parent / ".paddlex" / "official_models" / "PaddleOCR-VL"

# 单例模式
_paddle_vl_instance: Optional["PaddleVLEngine"] = None
_paddle_vl_model_path: Optional[str] = None


class PaddleVLEngine:
    """
    PaddleOCR-VL 引擎封装类

    使用视觉-语言模型进行 OCR 识别，特别擅长手写文字识别。
    """

    def __init__(
        self,
        task_type: str = "ocr",
        device: str = "cpu",
        model_path: Optional[str] = None,
    ):
        """
        初始化 PaddleOCR-VL 引擎

        Args:
            task_type: 任务类型，支持 "ocr", "table", "formula", "chart"
            device: 运行设备，"cpu" 或 "gpu"
            model_path: 模型路径，未指定时使用默认路径
        """
        self._model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._pipeline = None
        self._task_type = task_type
        self._device = device
        self._init_engine()

    def _init_engine(self):
        """初始化 PaddleOCRVL 引擎"""
        try:
            from paddleocr import PaddleOCRVL

            # 设置设备
            device = self._device if self._device == "gpu" else "cpu"

            # 使用本地模型路径
            model_dir = str(self._model_path)
            logger.info(f"使用模型路径: {model_dir}")

            # 初始化引擎
            self._pipeline = PaddleOCRVL(model_dir=model_dir, device=device)
            logger.info(f"PaddleOCR-VL 引擎初始化成功，任务类型: {self._task_type}, 设备: {device}")

        except ImportError as e:
            logger.error(f"PaddleOCR-VL 导入失败，请确保已安装 paddleocr: {e}")
            raise
        except Exception as e:
            logger.error(f"PaddleOCR-VL 引擎初始化失败: {e}")
            raise

    def recognize(self, image_path: str) -> List[dict]:
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
        if self._pipeline is None:
            logger.error("OCR 引擎未初始化")
            return []

        try:
            result = self._pipeline.predict(image_path)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"PaddleOCR-VL 识别失败: {e}")
            return []

    def recognize_bytes(self, image_bytes: bytes) -> List[dict]:
        """
        识别字节流格式的图片

        Args:
            image_bytes: 图片的字节数据

        Returns:
            list[dict]: OCR 结果列表
        """
        import tempfile

        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(image_bytes)
            return self.recognize(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _parse_result(self, result) -> List[dict]:
        """
        解析 PaddleOCRVL 返回结果

        Args:
            result: PaddleOCRVL 返回的原始结果

        Returns:
            list[dict]: 标准化后的结果列表
        """
        if result is None:
            return []

        items = []

        try:
            for res in result:
                # PaddleOCRVL 返回的是 Result 对象
                if hasattr(res, "json"):
                    json_data = res.json
                else:
                    json_data = res

                if isinstance(json_data, dict):
                    # 提取文本结果
                    rec_texts = json_data.get("rec_texts", [])
                    rec_scores = json_data.get("rec_scores", [])
                    rec_boxes = json_data.get("rec_boxes", [])

                    for i, text in enumerate(rec_texts):
                        score = rec_scores[i] if i < len(rec_scores) else 1.0
                        box = rec_boxes[i] if i < len(rec_boxes) else [[0, 0], [100, 0], [100, 20], [0, 20]]

                        # 转换 box 格式
                        if isinstance(box, (list, tuple)) and len(box) > 0:
                            if len(box) == 4 and isinstance(box[0], (int, float)):
                                # [x1, y1, x2, y2] -> [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                                box = [
                                    [int(box[0]), int(box[1])],
                                    [int(box[2]), int(box[1])],
                                    [int(box[2]), int(box[3])],
                                    [int(box[0]), int(box[3])]
                                ]
                            elif len(box) == 2:
                                # 单点坐标，转换为矩形
                                x, y = int(box[0]), int(box[1])
                                box = [[x, y], [x + 100, y], [x + 100, y + 20], [x, y + 20]]
                            else:
                                # 确保所有坐标都是整数
                                box = [[int(p[0]), int(p[1])] for p in box]

                        items.append({
                            "text": str(text).strip() if text else "",
                            "score": float(score) if score else 1.0,
                            "box": box
                        })

        except Exception as e:
            logger.error(f"解析结果失败: {e}")

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

    @property
    def pid(self) -> Optional[int]:
        """获取引擎进程 ID（如果可用）"""
        return None

    def __del__(self):
        """清理资源"""
        if hasattr(self, "_pipeline"):
            self._pipeline = None


def get_paddle_vl_engine(
    task_type: str = "ocr",
    device: str = "cpu",
    model_path: Optional[str] = None,
) -> PaddleVLEngine:
    """
    获取 PaddleOCR-VL 引擎单例

    Args:
        task_type: 任务类型
        device: 运行设备
        model_path: 模型路径，未指定时使用默认路径

    Returns:
        PaddleVLEngine: OCR 引擎实例
    """
    global _paddle_vl_instance, _paddle_vl_model_path

    if _paddle_vl_instance is None or _paddle_vl_model_path != model_path:
        _paddle_vl_instance = PaddleVLEngine(
            task_type=task_type,
            device=device,
            model_path=model_path
        )
        _paddle_vl_model_path = model_path
    return _paddle_vl_instance


def recognize_image(image_path: str) -> List[dict]:
    """识别图片（便捷函数）"""
    return get_paddle_vl_engine().recognize(image_path)


def extract_text_from_image(image_path: str) -> str:
    """提取图片文本（便捷函数）"""
    return get_paddle_vl_engine().extract_text(image_path)
