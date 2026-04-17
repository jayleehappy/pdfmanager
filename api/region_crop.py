"""
区域裁剪模块

根据模板的区域定义，裁剪扫描件中的指定区域。
"""
import json
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# 区域定义文件目录
REGIONS_BASE_PATH = Path(__file__).parent.parent / "templates" / "regions"


def load_regions(template_id: int) -> list[dict]:
    """
    加载模板的区域定义

    Args:
        template_id: 模板页号（1-21）

    Returns:
        list[dict]: 区域列表，每项包含 label, x1, y1, x2, y2 等
    """
    # 模板文件命名规则：PDFtemplates_XXX_regions.json
    region_file = REGIONS_BASE_PATH / f"PDFtemplates_{template_id:03d}_regions.json"

    if not region_file.exists():
        logger.warning(f"区域定义文件不存在: {region_file}")
        return []

    try:
        data = json.loads(region_file.read_text(encoding="utf-8"))
        regions = data.get("regions", [])
        logger.debug(f"加载模板 {template_id} 的 {len(regions)} 个区域")
        return regions
    except Exception as e:
        logger.error(f"加载区域定义失败: {e}")
        return []


def crop_regions(image: np.ndarray, regions: list[dict]) -> list[tuple[str, np.ndarray]]:
    """
    裁剪图片中的指定区域

    Args:
        image: 原始图片 (H, W, C) 或 (H, W)
        regions: 区域列表，每项包含 x1, y1, x2, y2

    Returns:
        list of (label, cropped_image)
    """
    results = []

    for region in regions:
        label = region.get("label", f"region_{region.get('index', 0)}")
        x1, y1 = region.get("x1", 0), region.get("y1", 0)
        x2, y2 = region.get("x2", 0), region.get("y2", 0)

        # 边界检查
        h, w = image.shape[:2]
        x1, x2 = max(0, min(x1, x2, w)), max(0, min(x2, w))
        y1, y2 = max(0, min(y1, y2, h)), max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            logger.warning(f"区域 {label} 坐标无效: ({x1},{y1})-({x2},{y2})")
            continue

        # 裁剪
        cropped = image[y1:y2, x1:x2]

        # 转为 RGB（如果是灰度图）
        if len(cropped.shape) == 2:
            cropped = cv2.cvtColor(cropped, cv2.COLOR_GRAY2RGB)
        elif cropped.shape[2] == 4:
            # RGBA -> RGB
            cropped = cv2.cvtColor(cropped, cv2.COLOR_BGRA2BGR)

        results.append((label, cropped))

    logger.debug(f"裁剪了 {len(results)} 个区域")
    return results


def crop_single_region(image: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    """
    裁剪单个区域

    Args:
        image: 原始图片
        x1, y1: 左上角坐标
        x2, y2: 右下角坐标

    Returns:
        裁剪后的图片
    """
    # 边界检查
    h, w = image.shape[:2]
    x1, x2 = max(0, min(x1, x2, w)), max(0, min(x2, w))
    y1, y2 = max(0, min(y1, y2, h)), max(0, min(y2, h))

    return image[y1:y2, x1:x2]


def save_cropped_image(cropped: np.ndarray, output_path: str) -> bool:
    """
    保存裁剪后的图片

    Args:
        cropped: 裁剪后的图片
        output_path: 输出路径

    Returns:
        bool: 是否成功保存
    """
    try:
        cv2.imwrite(output_path, cropped)
        return True
    except Exception as e:
        logger.error(f"保存裁剪图片失败: {e}")
        return False


def image_to_base64(image: np.ndarray, format: str = ".png") -> str:
    """
    将图片转为 base64 字符串

    Args:
        image: 图片 (H, W, C)
        format: 输出格式 (.png 或 .jpg)

    Returns:
        base64 编码字符串（不含 data:image 前缀）
    """
    import base64

    _, buf = cv2.imencode(format, image)
    return base64.b64encode(buf).decode("utf-8")


def load_image(image_path: str) -> Optional[np.ndarray]:
    """
    加载图片

    Args:
        image_path: 图片路径

    Returns:
        图片数组，或 None（如果加载失败）
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"无法加载图片: {image_path}")
            return None
        # BGR -> RGB
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as e:
        logger.error(f"加载图片失败: {e}")
        return None
