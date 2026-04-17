"""
PaddleOCRVL use_layout_detection=False 速度测试
"""
import sys, os
sys.path.insert(0, "D:/grsxbd")
sys.path.insert(0, r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")

os.environ["MKL_THREADING_LAYER"] = "GNU"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import time
from pathlib import Path

TEST_DIR = Path("d:/grsxbd/uploads/debug_regions")
IMAGES = sorted(TEST_DIR.glob("scan_p*.png"))[:5]

print(f"{'='*60}")
print("PaddleOCRVL use_layout_detection=False 速度测试")
print(f"{'='*60}")

# 加载模型（禁用版面分析）
t0 = time.time()
print("加载 PaddleOCRVL (use_layout_detection=False)...")
from paddleocr import PaddleOCRVL
ocr = PaddleOCRVL(use_layout_detection=False)  # 禁用版面分析
print(f"加载耗时: {time.time()-t0:.1f}s")

results = []
for img_path in IMAGES:
    t1 = time.time()
    output = ocr.predict(str(img_path))
    elapsed = time.time() - t1

    texts = []
    for res in output:
        data = res.tojson() if hasattr(res, 'tojson') else {}
        if isinstance(data, dict):
            pl = data.get('parsing_res_list', [])
            for item in pl:
                content = item.get('block_content', '')
                if content and isinstance(content, str):
                    texts.append(content.strip())
            if 'text' in data:
                txt = str(data['text']).strip()
                if txt:
                    texts.append(txt)

    result_str = " | ".join(texts[:3]) if texts else "(无文本)"
    print(f"  {img_path.name}: {elapsed:.2f}s -> {result_str[:60]}")
    results.append(elapsed)

avg = sum(results) / len(results)
print(f"\n汇总: 平均 {avg:.2f}s/图, 总计 {sum(results):.1f}s ({len(results)}张)")
print(f"对比 use_layout_detection=True (默认): ~9.25s/图")
if avg > 0:
    print(f"速度提升: ~{9.25/avg:.1f}x")
