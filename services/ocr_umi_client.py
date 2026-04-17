"""
Umi-OCR HTTP 客户端 — 调用局域网 Umi-OCR 服务进行文字识别
"""
import base64
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

UMI_URL = "http://127.0.0.1:1224/api/ocr"
UMI_TIMEOUT = 60  # 秒


class UmiOcrClient:
        """
        Umi-OCR HTTP API 客户端。

        API 文档：
          POST http://127.0.0.1:1224/api/ocr
          Body: {"base64": "<img_b64>", "options": {...}}
          Options:
            - ocr.angle: bool   # 是否启用方向分类
            - ocr.limit_side_len: int  # 图像限长（默认960）
            - tbpu.parser: str   # 排版解析 none/multi_para/single_line 等
            - data.format: str   # dict（默认，含坐标）/ text（纯文本）
        """

        def __init__(self, url: str = UMI_URL, timeout: int = UMI_TIMEOUT):
                self.url = url
                self.timeout = timeout

        def recognize(self, image_path: str | bytes) -> list[dict]:
                """
                识别图像中的文字。

                Args:
                        image_path: 图片路径或 bytes（图片二进制）

                Returns:
                        list[dict]: OCR 结果列表，每项格式：
                        {"box": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], "score": float, "text": str, "end": str}
                        与 RapidOCR 的 [[box, text, score], ...] 兼容。
                """
                if isinstance(image_path, bytes):
                        b64 = base64.b64encode(image_path).decode("utf-8")
                else:
                        with open(image_path, "rb") as f:
                                b64 = base64.b64encode(f.read()).decode("utf-8")

                resp = requests.post(
                        self.url,
                        json={
                                "base64": b64,
                                "options": {
                                        "ocr.angle": False,
                                        "ocr.limit_side_len": 960,
                                        "tbpu.parser": "none",   # PreOCR 不需要排版解析
                                        "data.format": "dict",   # 返回含坐标的字典
                                },
                        },
                        timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 100:
                        logger.warning(f"Umi-OCR 返回错误: code={data.get('code')}, data={data.get('data')}")
                        return []

                items = data.get("data", [])
                return items

        def recognize_texts(self, image_path: str | bytes) -> list[str]:
                """仅返回文本列表（不含坐标）"""
                items = self.recognize(image_path)
                return [item["text"].strip() for item in items if item.get("text", "").strip()]
