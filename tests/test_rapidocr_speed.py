"""
RapidOCR 速度测试 — 用于 PreOCR 轻量文字识别
"""
import sys, os
sys.path.insert(0, "D:/grsxbd")
sys.path.insert(0, r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")

os.environ["OMP_NUM_THREADS"] = "2"

import time
from pathlib import Path

TEST_DIR = Path("d:/grsxbd/uploads/debug_regions")
IMAGES = sorted(TEST_DIR.glob("scan_p*.png"))[:10]

print(f"{'='*60}")
print("RapidOCR 速度测试")
print(f"{'='*60}")

# 加载模型
t0 = time.time()
from rapidocr_onnxruntime import RapidOCR
ocr = RapidOCR()
print(f"加载耗时: {time.time()-t0:.1f}s")

results = []
for img_path in IMAGES:
    t1 = time.time()
    try:
        raw_result, elapse = ocr(str(img_path))
        elapsed = time.time() - t1

        texts = []
        if raw_result:
            for line in raw_result:
                if line and len(line) >= 2:
                    text = line[1]
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())

        result_str = " | ".join(texts[:5]) if texts else "(无文本)"
        total_elapse = sum(elapse) if isinstance(elapse, list) else (elapsed or 0)
        print(f"  {img_path.name}: total={elapsed:.3f}s (det+rec={total_elapse:.3f}s) -> {result_str[:60]}")
        results.append(elapsed)
    except Exception as ex:
        elapsed = time.time() - t1
        print(f"  {img_path.name}: ERROR {elapsed:.3f}s -> {ex}")
        results.append(elapsed)

avg = sum(results) / len(results)
total = sum(results)
print(f"\n汇总: 平均 {avg:.3f}s/图, 总计 {total:.2f}s ({len(results)}张)")
print(f"对比 PaddleOCRVL (含版面): ~9.25s/图")
if avg > 0:
    print(f"速度提升: ~{9.25/avg:.0f}x")
