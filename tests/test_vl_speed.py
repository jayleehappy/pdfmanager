# -*- coding: utf-8 -*-
"""
PaddleOCR-VL 速度对比测试
对比:
  A. 整页 + use_layout_detection=True (默认, 全流程)
  B. 整页 + use_layout_detection=False (跳过版面检测, prompt='ocr')
  C. 裁剪区域 + use_layout_detection=False (只处理感兴趣区域)
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, r"D:/grsxbd/.venv_paddleocr/Lib/site-packages")
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import fitz
import numpy as np
from paddleocr import PaddleOCRVL

OUTPUT_DIR = Path(r"D:/grsxbd/tests/paddle_official_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载 GT 获取裁剪区域
jsonl_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/[OCR]_page_003_20260416_0156.jsonl")
with open(jsonl_path, encoding="utf-8") as f:
    gt_data = json.load(f)
gt_items = gt_data["data"]

# 渲染 PDF (72 DPI)
pdf_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/page_003.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
mat = fitz.Matrix(1.0, 1.0)
pix = page.get_pixmap(matrix=mat)
img_path = OUTPUT_DIR / "page_003_vl_full.png"
pix.save(str(img_path))
doc.close()

# 生成顶部裁剪 (上半页)
doc2 = fitz.open(pdf_path)
crop_pix = doc2[0].get_pixmap(matrix=mat, clip=fitz.Rect(0, 0, 594, 450))
crop_path = OUTPUT_DIR / "page_003_top_crop.png"
crop_pix.save(str(crop_path))
doc2.close()

print(f"全页尺寸: {pix.width}x{pix.height}")
print(f"裁剪尺寸: {crop_pix.width}x{crop_pix.height}")

# 加载 VL 模型 (v1, 只加载一次)
print("\n" + "=" * 60)
print("加载 PaddleOCR-VL v1...")
print("=" * 60)
start = time.time()
vl = PaddleOCRVL(pipeline_version="v1", device="cpu")
load_time = time.time() - start
print(f"加载: {load_time:.1f}s\n")

results = {}

# ── 测试A: 整页 + use_layout_detection=True (默认) ──
print("=" * 60)
print("测试A: 整页 + 版面检测 (默认)")
print("=" * 60)
start = time.time()
resA = vl.predict(str(img_path), use_layout_detection=True)
timeA = time.time() - start
n_boxesA = len(list(resA)[0].json["res"]["layout_det_res"]["boxes"])
results["A"] = {"time": timeA, "boxes": n_boxesA}
print(f"耗时: {timeA:.1f}s | 检测区域: {n_boxesA}个")

# ── 测试B: 整页 + use_layout_detection=False ──
print("\n" + "=" * 60)
print("测试B: 整页 + 无版面检测 (use_layout_detection=False)")
print("=" * 60)
start = time.time()
resB = vl.predict(str(img_path), use_layout_detection=False, prompt_label="ocr")
timeB = time.time() - start
print(f"耗时: {timeB:.1f}s")

# 提取结果
rB = list(resB)[0].json
parsingB = rB.get("res", {}).get("parsing_res_list", [])
print(f"解析块数: {len(parsingB)}")
for p in parsingB[:3]:
    content = p.get("block_content", "")[:80]
    print(f"  [{p.get('block_label')}] {content}")

results["B"] = {"time": timeB, "blocks": len(parsingB)}

# ── 测试C: 裁剪区域 + 无版面检测 ──
print("\n" + "=" * 60)
print("测试C: 裁剪区 + 无版面检测 (use_layout_detection=False)")
print("=" * 60)
start = time.time()
resC = vl.predict(str(crop_path), use_layout_detection=False, prompt_label="ocr")
timeC = time.time() - start
print(f"耗时: {timeC:.1f}s")

rC = list(resC)[0].json
parsingC = rC.get("res", {}).get("parsing_res_list", [])
print(f"解析块数: {len(parsingC)}")
for p in parsingC[:3]:
    content = p.get("block_content", "")[:80]
    print(f"  [{p.get('block_label')}] {content}")

results["C"] = {"time": timeC, "blocks": len(parsingC)}

# ── 总结 ──
print("\n" + "=" * 60)
print("速度对比总结")
print("=" * 60)
print(f"{'方案':<35s} {'耗时':>8s} {'加速比':>8s}")
print("-" * 60)
t_baseline = results["A"]["time"]
print(f"{'A. 整页+版面检测 (默认)':<35s} {results['A']['time']:>7.1f}s 基准")
print(f"{'B. 整页+无版面检测':<35s} {results['B']['time']:>7.1f}s  {t_baseline/results['B']['time']:.2f}x")
print(f"{'C. 裁剪区+无版面检测':<35s} {results['C']['time']:>7.1f}s  {t_baseline/results['C']['time']:.2f}x")
print(f"\n对比 UmiOCR: ~0.88s/页 | VL最快: {min(timeB, timeC):.1f}s")
print(f"VL vs UmiOCR: {min(timeB, timeC)/0.88:.0f}x 更慢")
