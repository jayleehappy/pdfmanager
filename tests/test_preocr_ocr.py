"""
PreOCR 真实 OCR 识别测试
对合并图做 PaddleOCR 识别，验证区域文本匹配效果
"""
import sys, os
sys.path.insert(0, "D:/grsxbd")
sys.path.insert(0, r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")

os.environ["MKL_THREADING_LAYER"] = "GNU"
os.environ["OMP_NUM_THREADS"] = "2"

import json
from pathlib import Path
from PIL import Image
import numpy as np

BASE_DIR = Path("D:/grsxbd")
OUTPUT_DIR = BASE_DIR / "temp" / "preocr_debug"
MANIFEST_FILE = BASE_DIR / "templates" / "manifest.json"

# 预期文本
EXPECTED_TEXT = {
    1: "领导干部个人有关事项报告表",
    2: "填表须知",
    3: "目录",
}
for pg in range(4, 22):
    EXPECTED_TEXT[pg] = str(pg - 3)

def text_match_score(text: str, expected: str) -> float:
    """字符级评分"""
    if not text or not expected:
        return 0.0
    t = text.upper().strip()
    e = expected.upper().strip()
    if e in t:
        return 1.0
    overlap = sum(1 for c in e if c in t) / len(e)
    return min(overlap, 1.0)

# 加载 PaddleOCRVL
print("加载 PaddleOCRVL...")
from paddleocr import PaddleOCRVL
ocr = PaddleOCRVL()
print("PaddleOCRVL 加载完成")

# 对合并图做识别
import glob
composite_files = sorted(OUTPUT_DIR.glob("page_*_composite.png"))
print(f"\n找到 {len(composite_files)} 个合并图\n")

for f in composite_files:
    print(f"{'='*50}")
    print(f"文件: {f.name}")

    # 识别
    result = ocr.predict(str(f))
    texts = []
    for r in result:
        r_data = r.tojson() if hasattr(r, 'tojson') else {}
        if isinstance(r_data, dict) and 'parsing_res_list' in r_data:
            for item in r_data['parsing_res_list']:
                content = item.get('block_content', '')
                if content and isinstance(content, str) and content.strip():
                    texts.append(content.strip())
        elif isinstance(r_data, dict) and 'text' in r_data:
            texts.append(str(r_data['text']).strip())

    # 备用：直接从 result 对象提取
    if not texts:
        try:
            if hasattr(result, '__iter__') and not isinstance(result, (str, dict)):
                for item in result:
                    if hasattr(item, 'Text'):
                        texts.append(str(item.Text).strip())
                    elif hasattr(item, 'text'):
                        texts.append(str(item.text).strip())
        except:
            pass

    combined = " ".join(texts)
    print(f"识别文本: \"{combined[:120]}\"")

    # 评分匹配
    best_score = 0.0
    best_tpl = 1
    for tpl_page, expected_text in EXPECTED_TEXT.items():
        score = text_match_score(combined, expected_text)
        if score > best_score:
            best_score = score
            best_tpl = tpl_page
        if score > 0.3:
            print(f"  -> 模板页{tpl_page} (期望\"{expected_text}\") 得分={score:.2f}")

    print(f"[匹配结果] -> 模板页{best_tpl} (最高分={best_score:.2f})")

print("\n完成")
