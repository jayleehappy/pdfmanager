# -*- coding: utf-8 -*-
"""
PaddleOCR-VL 直接测试 (paddleocr.PaddleOCRVL, CPU)
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, r"D:/grsxbd/.venv_paddleocr/Lib/site-packages")
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import paddleocr

# 检查 PaddleOCRVL 是否可用
try:
    from paddleocr import PaddleOCRVL
    print(f"[OK] PaddleOCRVL 可导入")
except ImportError as e:
    print(f"[ERROR] PaddleOCRVL 不可用: {e}")
    sys.exit(1)

# 检查参数
import inspect
sig = inspect.signature(PaddleOCRVL.__init__)
print(f"PaddleOCRVL 参数: {list(sig.parameters.keys())}")

OUTPUT_DIR = Path(r"D:/grsxbd/tests/paddle_official_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 渲染测试图
import fitz
pdf_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/page_003.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
mat = fitz.Matrix(1.0, 1.0)
pix = page.get_pixmap(matrix=mat)
img_path = OUTPUT_DIR / "page_003_vl2.png"
pix.save(str(img_path))
doc.close()

# 顶部裁剪
doc2 = fitz.open(pdf_path)
crop_pix = doc2[0].get_pixmap(matrix=mat, clip=fitz.Rect(0, 0, 594, 280))
crop_path = OUTPUT_DIR / "page_003_top2.png"
crop_pix.save(str(crop_path))
doc2.close()
print(f"[INFO] 图片: {img_path}")

# 加载 PaddleOCRVL
print("\n" + "=" * 60)
print("加载 PaddleOCRVL (CPU)...")
print("=" * 60)

start = time.time()
try:
    vl = PaddleOCRVL(device="cpu")
    print(f"[OK] PaddleOCRVL 加载: {time.time()-start:.1f}s")
except Exception as e:
    print(f"[ERROR] 加载失败: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# 测试1: 顶部裁剪
print("\n" + "=" * 60)
print("测试1: 顶部裁剪")
print("=" * 60)
t0 = time.time()
try:
    result1 = vl.predict(str(crop_path))
    rec_time1 = time.time() - t0
    print(f"[耗时] {rec_time1:.1f}s")
    texts1 = []
    for res in result1:
        print(f"[结果 type] {type(res)}")
        print(f"[结果 dir] {[x for x in dir(res) if not x.startswith('_')]}")
        # 尝试获取文本
        if hasattr(res, 'str'):
            print(f"[str] {res.str}")
        if hasattr(res, 'json'):
            print(f"[json keys] {list(res.json.keys()) if isinstance(res.json, dict) else type(res.json)}")
        if hasattr(res, 'print'):
            res.print()
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback; traceback.print_exc()

# 测试2: 全页
print("\n" + "=" * 60)
print("测试2: 全页")
print("=" * 60)
t0 = time.time()
try:
    result2 = vl.predict(str(img_path))
    rec_time2 = time.time() - t0
    print(f"[耗时] {rec_time2:.1f}s")
    for res in result2:
        if hasattr(res, 'str'):
            print(f"[结果] {res.str}")
        if hasattr(res, 'print'):
            res.print()
except Exception as e:
    print(f"[ERROR] {e}")

print("\n完成!")
