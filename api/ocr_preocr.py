"""
PreOCR 批量匹配模块 —— 三步级联识别策略
────────────────────────────────────────────
Step 1: 仅识别页脚区（y≈1628-1732）→ 页码 1-18 → 模板 4-21
Step 2: 识别标题区（y≈343-460）  → 标题 → 模板 1/3（封面/目录）
Step 3: 识别说明区（y≈125-249）  → 填表须知 → 模板 2
        无法识别 → 提示用户手动指定模板页码
"""

import json
import logging
import re
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

from rapidocr_onnxruntime import RapidOCR
from api.ocr_utils import match_page_orb

# ── Step 1: 页码 → 模板映射 ──────────────────────────────────
# 页码 1-18（OCR 可能输出 "1"、"— 1 —"、"—1—" 等格式）
PAGE_NUM_TO_TEMPLATE: dict[str, int] = {}
for i in range(1, 19):
        PAGE_NUM_TO_TEMPLATE[str(i)] = i + 3          # "1"→4, "4"→7, "10"→13, "18"→21
        PAGE_NUM_TO_TEMPLATE[f"— {i} —"] = i + 3    # "— 10 —"
        PAGE_NUM_TO_TEMPLATE[f"—{i}—"] = i + 3       # "—10—"
        PAGE_NUM_TO_TEMPLATE[f"— {i}"] = i + 3      # "— 10"
        PAGE_NUM_TO_TEMPLATE[f"{i} —"] = i + 3      # "10 —"

# ── Step 2: 标题 → 模板映射 ────────────────────────────────────
TITLE_TO_TEMPLATE: dict[str, int] = {
        "领导干部个人有关事项报告表": 1,
        "领导干部个人有关事项报告": 1,   # OCR部分截断
        "报告表": 1,                      # 保守回退
        "目": 3,                          # OCR只识别出"目"
        "目录": 3,
        "一、报告人基本情况": 3,
        "《规定》所列报告事项": 3,
}

# ── Step 3: 说明区 → 模板映射 ─────────────────────────────────
DESC_TO_TEMPLATE: dict[str, int] = {
        "填表须知": 2,
        "填表须": 2,     # OCR部分识别
        "须知": 2,
}


def _normalize(text: str) -> str:
        """去除空格后的文本"""
        return text.replace(" ", "").replace("\u3000", "").replace("\xa0", "").replace("\n", "").strip()


def _extract_page_num(text: str) -> str | None:
        """从 OCR 文本中提取页码 key（字典中的原始格式）。

        处理噪声：OCR 可能输出 "7 一"、"— 10 — 一" 等，需要去掉汉字后再匹配。
        """
        # 去掉所有汉字（CJK统一汉字）
        digits_only = re.sub(r'[\u4e00-\u9fff\u3000\xa0\u2014\u2018\u2019\u201c\u201d\u002d]+', '', text)
        norm = _normalize(digits_only)

        # 尝试完整匹配
        if norm in PAGE_NUM_TO_TEMPLATE:
                return norm
        # 去掉"—"后匹配
        stripped = norm.strip("—").strip("-").strip()
        if stripped in PAGE_NUM_TO_TEMPLATE:
                return stripped
        return None


# ── RapidOCR 全局单例 ──────────────────────────────────────────
_rapid_ocr = None


def _get_rapid_ocr():
        global _rapid_ocr
        if _rapid_ocr is None:
                _rapid_ocr = RapidOCR()
        return _rapid_ocr


# ── 三步级联识别 ────────────────────────────────────────────────
def _recognize_region(img_rgb: np.ndarray, region: dict) -> list[str]:
        """识别指定区域，返回文本列表。"""
        x1, y1 = max(0, region["x1"]), max(0, region["y1"])
        x2 = min(img_rgb.shape[1], region["x2"])
        y2 = min(img_rgb.shape[0], region["y2"])
        cropped = img_rgb[y1:y2, x1:x2]
        img_pil = Image.fromarray(cropped)
        raw_result, _ = _get_rapid_ocr()(img_pil)
        texts = []
        if raw_result:
                for line in raw_result:
                        if line and len(line) >= 2:
                                txt = line[1]
                                if isinstance(txt, str) and txt.strip():
                                        texts.append(txt.strip())
        return texts


def run_preocr_batch(
        scan_imgs: dict,
        tpl_orb_cache: dict,
        manifest: dict,
        task_id: str,
        TEMPLATE_BASE: Path,
) -> tuple[
        list[tuple[int, int, float, str]],  # (seq_idx, best_tpl, best_score, method)
        list[str],                            # PreOCR 临时文件路径，供调用方清理
]:
        """
        三步级联预OCR：
          Step 1: 仅识别页脚区 → 页码 1-18 → 模板 4-21
          Step 2: 识别标题区 → 封面(模板1)/目录(模板3)
          Step 3: 识别说明区 → 填表须知(模板2)，无法识别则提示用户
        """
        import time as _time
        import tempfile

        logger.info(f"[OCR Task {task_id}] PreOCR三步级联开始，{len(scan_imgs)} 页")

        # ── 加载三步区域配置 ──────────────────────────────────────
        cfg_path = TEMPLATE_BASE / "pre_ocr_region.json"
        if not cfg_path.exists():
                logger.warning(f"[OCR Task {task_id}] pre_ocr_region.json 不存在，回退到纯ORB")
                return [
                        (seq_idx, *match_page_orb(scan_imgs[seq_idx], tpl_orb_cache, seq_idx), "orb")
                        for seq_idx in sorted(scan_imgs)
                ], []

        with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
        regions = {r["index"]: r for r in cfg.get("regions", [])}

        # 三步各自对应哪个区域
        FOOTER_IDX = 2    # 公共特征区域2：页脚区（x=12,y=1628,x=1216,y=1732）
        TITLE_IDX  = 1    # 公共特征区域1：标题区（x=263,y=343,x=997,y=460）
        DESC_IDX   = 3    # 公共特征区域3：说明区（x=376,y=125,x=880,y=249）

        if FOOTER_IDX not in regions or TITLE_IDX not in regions or DESC_IDX not in regions:
                logger.warning(f"[OCR Task {task_id}] 区域定义不完整，回退到纯ORB")
                return [
                        (seq_idx, *match_page_orb(scan_imgs[seq_idx], tpl_orb_cache, seq_idx), "orb")
                        for seq_idx in sorted(scan_imgs)
                ], []

        seq_list = sorted(scan_imgs.keys())
        if not seq_list:
                return [], []

        # ── Step 1: 批量识别所有页的页脚区（最快的识别）────────
        footer_region = regions[FOOTER_IDX]
        logger.info(f"[OCR Task {task_id}] Step1: 批量识别页脚区（{len(seq_list)} 页）...")
        t0 = _time.time()
        ocr = _get_rapid_ocr()
        footer_results: list[list[str]] = []
        for seq_idx in seq_list:
                img = scan_imgs[seq_idx]
                if len(img.shape) == 2:
                        img = np.stack([img, img, img], axis=-1)
                # 仅裁剪页脚区
                x1, y1 = max(0, footer_region["x1"]), max(0, footer_region["y1"])
                x2 = min(img.shape[1], footer_region["x2"])
                y2 = min(img.shape[0], footer_region["y2"])
                cropped = img[y1:y2, x1:x2]
                img_pil = Image.fromarray(cropped)
                raw, _ = ocr(img_pil)
                texts = []
                if raw:
                        for line in raw:
                                if line and len(line) >= 2:
                                        txt = line[1]
                                        if isinstance(txt, str) and txt.strip():
                                                texts.append(txt.strip())
                footer_results.append(texts)
        t_step1 = _time.time() - t0
        logger.info(f"[OCR Task {task_id}] Step1 完成，耗时={t_step1:.1f}s")

        # ── 逐页三步级联匹配 ────────────────────────────────────
        results: list[tuple[int, int, float, str]] = []
        unresolved: list[tuple[int, np.ndarray]] = []  # 无法确定的页：seq_idx + 原始图
        tmp_files: list[str] = []
        SAVE_DEBUG = True
        debug_dir = Path("D:/grsxbd/tmp/preocr_debug")
        debug_dir.mkdir(parents=True, exist_ok=True)

        for i, seq_idx in enumerate(seq_list):
                all_text_f1 = " ".join(footer_results[i])
                logger.info(f"[PreOCR] seq={seq_idx} Step1页脚: \"{all_text_f1}\"")

                matched_tpl: int | None = None
                method = "page_num"

                # ── Step 1: 页码匹配 ─────────────────────────────
                page_key = _extract_page_num(all_text_f1)
                if page_key is not None:
                        matched_tpl = PAGE_NUM_TO_TEMPLATE[page_key]
                        logger.info(f"[PreOCR] seq={seq_idx} Step1 页码\"{page_key}\" → 模板{matched_tpl}")
                        results.append((seq_idx, matched_tpl, 1.0, "page_num"))
                        continue

                # ── Step 2: 标题区匹配 ──────────────────────────
                img = scan_imgs[seq_idx]
                if len(img.shape) == 2:
                        img_rgb = np.stack([img, img, img], axis=-1)
                else:
                        img_rgb = img

                title_texts = _recognize_region(img_rgb, regions[TITLE_IDX])
                all_text_f2 = " ".join(title_texts)
                logger.info(f"[PreOCR] seq={seq_idx} Step2 标题: \"{all_text_f2[:60]}\"")

                norm_f2 = _normalize(all_text_f2)
                for title, tpl in TITLE_TO_TEMPLATE.items():
                        if title in norm_f2 or norm_f2 in title:
                                matched_tpl = tpl
                                logger.info(f"[PreOCR] seq={seq_idx} Step2 标题\"{title}\" → 模板{tpl}")
                                results.append((seq_idx, matched_tpl, 1.0, "title"))
                                break

                if matched_tpl is not None:
                        continue

                # ── Step 3: 说明区匹配 ──────────────────────────
                desc_texts = _recognize_region(img_rgb, regions[DESC_IDX])
                all_text_f3 = " ".join(desc_texts)
                logger.info(f"[PreOCR] seq={seq_idx} Step3 说明: \"{all_text_f3[:60]}\"")

                norm_f3 = _normalize(all_text_f3)
                for kw, tpl in DESC_TO_TEMPLATE.items():
                        if kw in norm_f3 or norm_f3 in kw:
                                matched_tpl = tpl
                                logger.info(f"[PreOCR] seq={seq_idx} Step3 说明\"{kw}\" → 模板{tpl}")
                                results.append((seq_idx, matched_tpl, 1.0, "desc"))
                                break

                if matched_tpl is not None:
                        continue

                # ── 全部无法识别：ORB 兜底 ───────────────────────
                logger.warning(f"[PreOCR] seq={seq_idx} 三步均无法匹配 → ORB兜底")
                unresolved.append((seq_idx, img_rgb))

        # 批量 ORB 处理无法确定的页
        if unresolved:
                logger.info(f"[OCR Task {task_id}] {len(unresolved)} 页无法文字匹配，启动ORB兜底...")
                t_orb = _time.time()
                for seq_idx, img_rgb in unresolved:
                        orb_tpl, orb_score = match_page_orb(img_rgb, tpl_orb_cache, seq_idx)
                        logger.info(f"[PreOCR] seq={seq_idx} ORB→模板{orb_tpl}({orb_score:.1f})")
                        results.append((seq_idx, orb_tpl, orb_score, "orb"))
                logger.info(f"[OCR Task {task_id}] ORB兜底完成，耗时={_time.time()-t_orb:.1f}s")

        logger.info(f"[OCR Task {task_id}] PreOCR全部完成，results={len(results)}")
        return results, tmp_files
