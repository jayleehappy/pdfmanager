"""
PP-OCRv4 vs PaddleOCR-VL 速度对比测试
测试文件: d:/grsxbd/uploads/debug_regions/ 目录下的区域裁剪图
"""
import sys, os
sys.path.insert(0, "D:/grsxbd")
sys.path.insert(0, r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")

os.environ["MKL_THREADING_LAYER"] = "GNU"
os.environ["OMP_NUM_THREADS"] = "2"

import time
from pathlib import Path

TEST_DIR = Path("d:/grsxbd/uploads/debug_regions")
IMAGES = sorted(TEST_DIR.glob("scan_p*.png"))[:5]  # 测试前5张
OUTPUT = TEST_DIR / "speed_test_result.txt"

results = []

# ============================================================
# 测试1: PaddleOCR-VL (当前使用的模型，含版面分析)
# ============================================================
print(f"\n{'='*60}")
print("测试1: PaddleOCR-VL (含版面分析，适合全页OCR)")
print(f"{'='*60}")

try:
    from paddleocr import PaddleOCRVL

    t0 = time.time()
    print("加载 PaddleOCRVL 模型...")
    vl = PaddleOCRVL()
    load_time = time.time() - t0
    print(f"加载耗时: {load_time:.1f}s")

    for img_path in IMAGES:
        t1 = time.time()
        output = vl.predict(str(img_path))
        elapsed = time.time() - t1
        texts = []
        for res in output:
            data = res.tojson() if hasattr(res, 'tojson') else {}
            if isinstance(data, dict) and 'parsing_res_list' in data:
                for item in data['parsing_res_list']:
                    content = item.get('block_content', '')
                    if content and isinstance(content, str):
                        texts.append(content.strip())
            elif isinstance(data, dict) and 'text' in data:
                texts.append(str(data['text']).strip())
        result_str = " | ".join(texts[:5]) if texts else "(无文本)"
        print(f"  {img_path.name}: {elapsed:.1f}s -> {result_str[:60]}")
        results.append(("PaddleOCR-VL", img_path.name, elapsed))
    del vl
except Exception as e:
    print(f"PaddleOCR-VL 测试失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 测试2: PP-OCRv4 (轻量级，仅文字检测+识别，无版面分析)
# ============================================================
print(f"\n{'='*60}")
print("测试2: PP-OCRv4 (轻量级，仅文字检测+识别)")
print(f"{'='*60}")

try:
    from paddleocr import PaddleOCR

    t0 = time.time()
    print("加载 PP-OCRv4 模型...")
    # use_angle_cls=True 使用角度分类器，lang='ch' 中文
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False)
    load_time = time.time() - t0
    print(f"加载耗时: {load_time:.1f}s")

    for img_path in IMAGES:
        t1 = time.time()
        result = ocr.ocr(str(img_path), cls=True)
        elapsed = time.time() - t1
        texts = []
        if result and isinstance(result, list):
            for line in result:
                if line:
                    for item in line:
                        if item and len(item) >= 2:
                            text = item[1][0] if isinstance(item[1], (list, tuple)) else item[1]
                            if text and isinstance(text, str) and text.strip():
                                texts.append(text.strip())
        result_str = " | ".join(texts[:5]) if texts else "(无文本)"
        print(f"  {img_path.name}: {elapsed:.2f}s -> {result_str[:60]}")
        results.append(("PP-OCRv4", img_path.name, elapsed))
    del ocr
except Exception as e:
    print(f"PP-OCRv4 测试失败: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 汇总对比
# ============================================================
print(f"\n{'='*60}")
print("速度对比汇总")
print(f"{'='*60}")

by_model = {}
for model, img, elapsed in results:
    by_model.setdefault(model, []).append(elapsed)

for model, times in by_model.items():
    avg = sum(times) / len(times)
    print(f"  {model}: 平均 {avg:.2f}s/图, 总 {sum(times):.1f}s ({len(times)}张)")

# 保存结果
with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("PP-OCRv4 vs PaddleOCR-VL 速度对比\n")
    f.write("="*60 + "\n")
    for model, img, elapsed in results:
        f.write(f"{model}: {img} -> {elapsed:.2f}s\n")
    f.write("="*60 + "\n")
    for model, times in by_model.items():
        avg = sum(times) / len(times)
        f.write(f"{model}: 平均 {avg:.2f}s/图, 总 {sum(times):.1f}s ({len(times)}张)\n")
print(f"\n结果已保存到: {OUTPUT}")
