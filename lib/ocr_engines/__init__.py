"""
OCR 引擎统一接口

所有 OCR 引擎实现必须继承 BaseOCREngine 并实现以下方法：
- recognize(image_path) -> list[dict]
- recognize_batch(image_paths) -> list[list[dict]]
- extract_text(image_path) -> str

引擎模式：
- "fast": PP-OCRv5 ONNX Runtime（默认，速度快，多进程池）

用法示例：
    from lib.ocr_engines import get_ocr_engine

    # 获取默认引擎（fast）
    engine = get_ocr_engine()

    # 识别单张图片
    results = engine.recognize("/path/to/image.png")
    # -> [{'text': 'hello', 'score': 0.99, 'box': [[0,0],[100,0],[100,20],[0,20]]}, ...]

    # 批量识别
    results = engine.recognize_batch(["/path/img1.png", "/path/img2.png"])
    # -> [[result1, result2, ...], [result3, result4, ...]]
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class OCREngineInfo:
    """引擎元信息"""
    name: str                      # 引擎名称，如 "PP-OCRv5-ONNX"
    mode: str                      # 模式标识，如 "fast"
    description: str               # 描述
    device: str                    # "cpu" / "gpu" / "docker"
    speed: str                     # "fast" / "medium" / "slow"
    accuracy: str                  # "high" / "medium" / "highest"
    supports_batch: bool = True    # 是否支持批量识别
    requires_docker: bool = False  # 是否需要 Docker 环境


class BaseOCREngine(ABC):
    """
    OCR 引擎基类

    所有引擎实现必须继承此类。
    """

    @classmethod
    @abstractmethod
    def engine_info(cls) -> OCREngineInfo:
        """返回引擎元信息"""
        ...

    @abstractmethod
    def recognize(self, image_path: str) -> list[dict]:
        """
        识别单张图片

        Args:
            image_path: 图片路径

        Returns:
            list[dict]: OCR 结果列表，每项格式：
            {
                "text": "识别的文本",
                "score": 0.998,
                "box": [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            }
        """
        ...

    @abstractmethod
    def recognize_array(self, image: np.ndarray) -> list[dict]:
        """
        识别 numpy 数组格式的图片

        Args:
            image: numpy.ndarray 格式的图片 (H, W, C) BGR 或灰度

        Returns:
            list[dict]: 同 recognize() 格式
        """
        ...

    @abstractmethod
    def recognize_batch(self, image_paths: list[str]) -> list[list[dict]]:
        """
        批量识别多张图片

        Args:
            image_paths: 图片路径列表

        Returns:
            list[list[dict]]: 每张图片的 OCR 结果列表
        """
        ...

    def extract_text(self, image_path: str) -> str:
        """
        仅提取文本内容（不含坐标）

        默认实现：拼接所有识别文本
        子类可覆盖以优化性能
        """
        items = self.recognize(image_path)
        return "".join(item["text"] for item in items if item.get("text"))

    def close(self):
        """
        释放引擎资源

        默认空实现，子类按需覆盖
        """
        pass

    def __repr__(self):
        info = self.engine_info()
        return f"<{self.__class__.__name__} mode={info.mode} device={info.device}>"


# ── 全局引擎单例 ──────────────────────────────────────────────

_engine_instances: dict[str, BaseOCREngine] = {}


def get_ocr_engine(
    mode: str = "fast",
    **kwargs
) -> BaseOCREngine:
    """
    获取 OCR 引擎实例（单例，按模式缓存）

    Args:
        mode: 引擎模式，支持：
            - "fast": PP-OCRv5 ONNX Runtime（默认，多进程池，~6-11s/页，CPU）
            - "docker-gpu": PaddleOCR v3 Docker GPU 模式（高质量，GPU 加速）

        **kwargs: 传递给引擎的额外参数

    Returns:
        BaseOCREngine: OCR 引擎实例

    Raises:
        ValueError: 不支持的引擎模式
    """
    global _engine_instances

    # 检查缓存
    cache_key = f"{mode}"
    if cache_key in _engine_instances:
        return _engine_instances[cache_key]

    # 按需创建引擎
    if mode == "fast":
        from lib.ocr_engines.ppocrv5_onnx import PPOCRv5ONNXEngine
        engine = PPOCRv5ONNXEngine(**kwargs)
    elif mode == "docker-gpu":
        from lib.ocr_engines.ppocr_docker_gpu import PaddleDockerGPUEngine
        engine = PaddleDockerGPUEngine(**kwargs)
    else:
        available = ["fast", "docker-gpu"]
        raise ValueError(
            f"不支持的 OCR 引擎模式: {mode!r}。"
            f"支持的模式: {available}"
        )

    _engine_instances[cache_key] = engine
    return engine


def reset_ocr_engine(mode: str = "fast"):
    """
    重置引擎实例（下次调用时重新初始化）

    Args:
        mode: 要重置的引擎模式
    """
    global _engine_instances
    if mode in _engine_instances:
        _engine_instances[mode].close()
        del _engine_instances[mode]


def list_engines() -> list[OCREngineInfo]:
    """返回所有可用引擎的信息列表"""
    from lib.ocr_engines.ppocrv5_onnx import PPOCRv5ONNXEngine
    from lib.ocr_engines.ppocr_docker_gpu import PaddleDockerGPUEngine

    return [PPOCRv5ONNXEngine.engine_info(), PaddleDockerGPUEngine.engine_info()]
