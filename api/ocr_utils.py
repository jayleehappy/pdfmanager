"""
OCR 工具函数模块
包含：序列化、字段判断、ORB特征匹配、文本归一化
"""

import re
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────
PREOCR_THRESHOLD = 0.6


# ── 序列化 ───────────────────────────────────────────────
def to_serializable(obj):
        """将 numpy 类型转换为 Python 原生类型（用于 JSON 序列化）"""
        if isinstance(obj, np.integer):
                return int(obj)
        if isinstance(obj, np.floating):
                return float(obj)
        if isinstance(obj, np.ndarray):
                return obj.tolist()
        if isinstance(obj, dict):
                return {k: to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
                return [to_serializable(v) for v in obj]
        return obj


# ── 字段识别 ─────────────────────────────────────────────
def looks_like_name(s: str) -> bool:
        """判断是否为姓名（2-4个汉字）"""
        s = s.strip()
        return 2 <= len(s) <= 5 and all('\u4e00' <= c <= '\u9fff' for c in s)


def looks_like_date(s: str) -> bool:
        """判断是否为日期"""
        return bool(re.match(r'[\dO0０\-/]{6,}', s)) or '年' in s or '月' in s


def looks_like_org(s: str) -> bool:
        """判断是否为组织名称"""
        org_keywords = ['委', '部', '厅', '局', '处', '公司', '医院', '学校', '党委', '党组']
        return any(kw in s for kw in org_keywords)


# ── ORB 特征匹配 ─────────────────────────────────────────
def orb_features(gray):
        """提取灰度图的 ORB 特征"""
        import cv2
        orb = cv2.ORB_create(nfeatures=2000)  # type: ignore[attr-defined]
        return orb.detectAndCompute(gray, None)


def match_score(qdes, tkp, tdes, num_query_kp):
        """计算两个 ORB 描述子集合的匹配分数（归一化 Lowe ratio test）

        Args:
                qdes: query descriptors (scan image descriptors)
                tdes: train descriptors (template descriptors)
                num_query_kp: scan image 的 keypoint 总数，用于归一化
        """
        import cv2
        if qdes is None or tdes is None:
                return 0.0
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches = bf.knnMatch(qdes, tdes, k=2)
        good = [m for m, n in matches if m.distance < 0.6 * n.distance]
        # 归一化：避免扫描页keypoint少时得分系统性偏低
        return len(good) / max(num_query_kp, 1)


def match_page_orb(scan_img, tpl_orb_cache, seq_idx):
        """ORB 打分匹配（页数!=21 时的 fallback）"""
        kp, qdes = orb_features(scan_img)
        if qdes is None:
                return 1, 0.0
        num_kp = len(kp)
        best_score = 0.0
        best_tpl = 1
        for tpl_page, (_, tdes) in tpl_orb_cache.items():
                score = match_score(qdes, None, tdes, num_kp)
                if score > best_score:
                        best_score = score
                        best_tpl = tpl_page
        return best_tpl, best_score


# ── PreOCR 文本归一化与评分 ───────────────────────────────
def normalize_ocr_text(text: str) -> str:
        """OCR文本归一化：去空格/标点，处理数字-字母OCR混淆"""
        text = re.sub(r'[\s\u3000\x20]+', '', text)
        text = text.replace('O', '0').replace('０', '0')
        text = text.replace('I', '1').replace('１', '1').replace('l', '1').replace('｜', '1').replace('丨', '1')
        return text


def text_match_score(recognized_text: str, expected_text: str) -> float:
        """归一化文本匹配得分（0.0~1.0）基于 expected_text 在 recognized_text 中的覆盖率"""
        norm_rec = normalize_ocr_text(recognized_text)
        norm_exp = normalize_ocr_text(expected_text)
        if not norm_exp:
                return 0.0
        if norm_exp in norm_rec:
                return 1.0
        exp_chars = norm_exp
        score = 0.0
        rec_idx = 0
        for ch in exp_chars:
                while rec_idx < len(norm_rec):
                        if norm_rec[rec_idx] == ch:
                                score += 1.0
                                rec_idx += 1
                                break
                        rec_idx += 1
        return score / len(exp_chars)
