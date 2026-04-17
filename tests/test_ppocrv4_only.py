"""
PP-OCRv4 速度测试（禁用 PIR，执行模式）
"""
import sys, os
sys.path.insert(0, "D:/grsxbd")
sys.path.insert(0, r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")

os.environ["MKL_THREADING_LAYER"] = "GNU"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import paddle
# 禁用 PIR，使用旧版静态图执行
try:
    paddle.base.disablePir()
    print("PIR 已禁用")
except Exception as e:
    print(f"PIR 禁用失败（可能已禁用）: {e}")

import time
from pathlib import Path

TEST_DIR = Path("d:/grsxbd/uploads/debug_regions")
IMAGES = sorted(TEST_DIR.glob("scan_p*.png"))[:10]

print(f"{'='*60}")
print("PP-OCRv4 速度测试 (禁用PIR)")
print(f"{'='*60}")
print(f"测试图片: {len(IMAGES)} 张")

t0 = time.time()
from paddleocr import PaddleOCR
ocr = PaddleOCR(
    lang='ch',
    ocr_version='PP-OCRv4',
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)
print(f"加载耗时: {time.time()-t0:.1f}s")

results = []
for img_path in IMAGES:
    t1 = time.time()
    try:
        ocr_result = ocr.predict(str(img_path))
        elapsed = time.time() - t1
        texts = []
        if ocr_result:
            for item in ocr_result:
                if isinstance(item, dict):
                    for key in ['text', 'transcription', 'content']:
                        if key in item and item[key]:
                            txt = str(item[key]).strip()
                            if txt:
                                texts.append(txt)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    txt = item[1][0] if isinstance(item[1], (list, tuple)) else item[1]
                    if isinstance(txt, str) and txt.strip():
                        texts.append(txt.strip())
        result_str = " | ".join(texts[:5]) if texts else "(无文本)"
    except Exception as ex:
        elapsed = time.time() - t1
        result_str = f"错误: {ex}"
    print(f"  {img_path.name}: {elapsed:.2f}s -> {result_str[:60]}")
    results.append(elapsed)

avg = sum(results) / len(results)
total = sum(results)
print(f"\n汇总: 平均 {avg:.2f}s/图, 总计 {total:.1f}s ({len(results)}张)")
print(f"对比 PaddleOCR-VL: ~9.25s/图")
if avg > 0:
    print(f"速度提升: ~{9.25/avg:.0f}x")
