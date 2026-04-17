"""
Paddle OCR Docker GPU 引擎

通过 HTTP API 调用 paddle 容器（GPU 模式）的 PaddleOCR v3 服务。

容器 API 端点：
  POST http://localhost:9000/ocr_v3
    请求：{"image_path": "/paddle/uploads/xxx.png", "return_word_box": true}
    响应：{"success": true, "text": "...", "boxes": [{"text": "...", "score": 0.99, "box": [[x,y],...]}]}

容器卷挂载：
  D:\\paddle\\uploads → /paddle/uploads
  D:\\paddle\\data    → /paddle/data
"""

import json
import logging
import os
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from lib.ocr_engines import BaseOCREngine, OCREngineInfo

logger = logging.getLogger(__name__)

# Paddle 容器 API
_API_BASE = os.environ.get("PADDLE_API_BASE", "http://localhost:9000")
_API_TIMEOUT = int(os.environ.get("PADDLE_API_TIMEOUT", "300"))  # 5 分钟超时


def _ensure_in_container(local_path: str) -> tuple[str, bool]:
    """
    确保图片在 Docker 卷目录中，返回 (容器内路径, 是否需要清理临时副本)。

    - D:/paddle/uploads/... → 直接使用，不复制
    - D:/paddle/data/...    → 直接使用，不复制
    - 其他路径            → 复制到 D:/paddle/uploads/，用完后需清理
    """
    p = Path(local_path).resolve()
    win_path = str(p).replace("\\", "/").replace(":", "").lower()

    # D:/paddle/uploads → /paddle/uploads
    dp = Path("D:/paddle/uploads").resolve()
    dp_str = str(dp).replace("\\", "/").lower()
    if win_path.startswith(dp_str):
        rest = win_path[len(dp_str):].lstrip("/")
        return f"/paddle/uploads/{rest}", False

    # D:/paddle/data → /paddle/data
    dp2 = Path("D:/paddle/data").resolve()
    dp2_str = str(dp2).replace("\\", "/").lower()
    if win_path.startswith(dp2_str):
        rest = win_path[len(dp2_str):].lstrip("/")
        return f"/paddle/data/{rest}", False

    # 其他路径：复制到 uploads 目录（临时文件）
    dest_dir = Path("D:/paddle/uploads")
    dest_name = f"_ocr_{os.getpid()}_{p.name}"
    dest_path = dest_dir / dest_name
    shutil.copy2(str(p), str(dest_path))
    logger.info(f"Copied {local_path} -> {dest_path} for Docker OCR")
    return f"/paddle/uploads/{dest_name}", True


def _cleanup_temp_copy(container_path: str, needed_cleanup: bool):
    """清理临时副本"""
    if not needed_cleanup:
        return
    # container_path 类似 /paddle/uploads/_ocr_123_xxx.png
    fname = Path(container_path).name
    temp_path = Path("D:/paddle/uploads") / fname
    try:
        temp_path.unlink()
        logger.info(f"Cleaned up {temp_path}")
    except OSError:
        pass


def _call_api(image_path: str, return_word_box: bool = True) -> dict:
    """调用 paddle 容器 OCR API"""
    container_path, needs_cleanup = _ensure_in_container(image_path)

    payload = json.dumps({
        "image_path": container_path,
        "return_word_box": return_word_box,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{_API_BASE}/ocr_v3",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Paddle API HTTP {e.code}: {body}")
    finally:
        _cleanup_temp_copy(container_path, needs_cleanup)

    return result


class PaddleDockerGPUEngine(BaseOCREngine):
    """
    Paddle OCR Docker GPU 引擎

    通过 HTTP API 调用 paddle 容器（GPU 模式）的 PaddleOCR v3 服务。
    特性：
      - GPU 加速（CUDA）
      - PP-OCRv5 模型
      - 高识别质量
    """

    @classmethod
    def engine_info(cls) -> OCREngineInfo:
        return OCREngineInfo(
            name="PaddleOCR-Docker-GPU",
            mode="docker-gpu",
            description="PaddleOCR v3 + Docker GPU 模式（http://localhost:9000）",
            device="gpu",
            speed="fast",
            accuracy="high",
            supports_batch=True,
            requires_docker=True,
        )

    def recognize(self, image_path: str) -> list[dict]:
        result = _call_api(image_path, return_word_box=True)
        if not result.get("success"):
            logger.error(f"Paddle API error: {result.get('error', 'unknown')}")
            return []
        return result.get("boxes", [])

    def recognize_array(self, image: np.ndarray) -> list[dict]:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        try:
            cv2.imwrite(tmp_path, image)
            return self.recognize(tmp_path)
        finally:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass

    def recognize_batch(self, image_paths: list[str]) -> list[list[dict]]:
        return [self.recognize(p) for p in image_paths]

    def extract_text(self, image_path: str) -> str:
        result = _call_api(image_path, return_word_box=False)
        if not result.get("success"):
            return ""
        return result.get("text", "")

    def close(self):
        pass

    def health_check(self) -> dict:
        """检查 paddle 容器 API 是否健康"""
        try:
            req = urllib.request.Request(
                f"{_API_BASE}/health",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def __repr__(self):
        return f"<PaddleDockerGPUEngine api={_API_BASE}>"
