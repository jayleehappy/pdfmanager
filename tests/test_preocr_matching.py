"""
PreOCR 页匹配独立测试
渲染扫描页 -> 裁剪 preocr_region.json 区域 -> 拼接合并图 -> 显示区域内容
验证区域坐标是否对准模板特征
"""
import sys, os
sys.path.insert(0, "D:/grsxbd")
sys.path.insert(0, r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")

import json
import time
from pathlib import Path
from PIL import Image
import numpy as np
import fitz

BASE_DIR = Path("D:/grsxbd")
TEMPLATE_BASE = BASE_DIR / "templates"
SCAN_FILE = BASE_DIR / "uploads" / "pdf" / "5452341e-a887-4296-ab87-5c0ad68ffa15.pdf"
MANIFEST_FILE = TEMPLATE_BASE / "manifest.json"
OUTPUT_DIR = BASE_DIR / "temp" / "preocr_debug"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载 manifest
with open(MANIFEST_FILE, encoding="utf-8") as f:
    manifest = json.load(f)

# 加载 preOCR 区域
preocr_cfg_path = TEMPLATE_BASE / "pre_ocr_region.json"
with open(preocr_cfg_path, encoding="utf-8") as f:
    preocr_cfg = json.load(f)
preocr_regions = preocr_cfg["regions"]
print(f"[Config] 预OCR区域数量: {len(preocr_regions)}")
for r in preocr_regions:
    print(f"  区域{r['index']}: {r['label']} x1={r['x1']} y1={r['y1']} x2={r['x2']} y2={r['y2']}")

# 加载模板页1的尺寸（基准）
pages_dict = manifest["pages"]
tpl_png_path = TEMPLATE_BASE / "pages" / pages_dict["1"]["image"]
with Image.open(tpl_png_path) as tpl_img:
    tpl_w, tpl_h = tpl_img.size
print(f"\n[Template] 基准页尺寸: {tpl_w}x{tpl_h}")

# 打开扫描件
doc = fitz.open(str(SCAN_FILE))
total_pages = len(doc)
print(f"\n[Scan] PDF总页数: {total_pages}")

# 空白检测
non_blank = []
for i in range(total_pages):
    page = doc[i]
    text = page.get_text().strip()
    pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = arr[:, :, 0] if pix.n > 2 else arr[:, :, 0]
    white_ratio = (gray > 230).sum() / gray.size
    if white_ratio < 0.95 or text:
        non_blank.append(i + 1)
    else:
        print(f"  页{i+1}: 空白 (white_ratio={white_ratio:.2f})")
print(f"\n[Scan] 非空白页: {len(non_blank)} 页: {non_blank}")

# 预期文本
EXPECTED_TEXT = {
    1: "领导干部个人有关事项报告表",
    2: "填表须知",
    3: "目录",
}
for pg in range(4, 22):
    EXPECTED_TEXT[pg] = str(pg - 3)

print("\n" + "=" * 60)
print("逐页预OCR区域渲染测试（前6页）")
print("=" * 60)

for page_idx in non_blank[:6]:
    page = doc[page_idx - 1]
    # 渲染到 150 DPI（与 ocr_engine.py 一致）
    pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
    img_w, img_h = pix.width, pix.height
    sx, sy = img_w / tpl_w, img_h / tpl_h

    print(f"\n页{page_idx} (渲染尺寸: {img_w}x{img_h}, scale=({sx:.3f},{sy:.3f}))")

    # 裁剪每个区域
    page_crops = []
    for reg in preocr_regions:
        x1 = max(0, min(img_w, int(reg["x1"] * sx)))
        y1 = max(0, min(img_h, int(reg["y1"] * sy)))
        x2 = max(0, min(img_w, int(reg["x2"] * sx)))
        y2 = max(0, min(img_h, int(reg["y2"] * sy)))
        if x2 <= x1 or y2 <= y1:
            print(f"  区域{reg['index']} ({reg['label']}): 无效坐标 {x1},{y1}-{x2},{y2}")
            continue

        # 从 pixmap 裁剪
        full_arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if full_arr.ndim == 2:
            crop = full_arr[y1:y2, x1:x2]
        else:
            crop = full_arr[y1:y2, x1:x2, :]

        page_crops.append({
            "index": reg["index"],
            "label": reg["label"],
            "crop": crop,
            "bbox": (x1, y1, x2, y2)
        })
        print(f"  区域{reg['index']} ({reg['label']}): 裁剪 {x1},{y1}-{x2},{y2} -> shape={crop.shape}")

    if not page_crops:
        continue

    # 拼接为合并图（垂直排列，灰度）
    sep = 4
    total_h = sum(c["crop"].shape[0] for c in page_crops) + (len(page_crops) - 1) * sep
    max_w = max(c["crop"].shape[1] for c in page_crops)
    if page_crops[0]["crop"].ndim == 3:
        composite = np.full((total_h, max_w, 3), 255, dtype=np.uint8)
    else:
        composite = np.full((total_h, max_w), 255, dtype=np.uint8)

    y_off = 0
    for c in page_crops:
        h, w = c["crop"].shape[:2]
        if c["crop"].ndim == 3:
            composite[y_off:y_off+h, :w, :] = c["crop"]
        else:
            composite[y_off:y_off+h, :w] = c["crop"]
        y_off += h + sep

    # 保存合并图
    out_path = OUTPUT_DIR / f"page_{page_idx:03d}_composite.png"
    Image.fromarray(composite).save(str(out_path))
    print(f"  合并图: {out_path} ({composite.shape})")

    # 保存原始渲染图（前2页）
    if page_idx <= 2:
        full = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        full_path = OUTPUT_DIR / f"page_{page_idx:03d}_full.png"
        Image.fromarray(full).save(str(full_path))
        print(f"  完整页: {full_path} ({full.shape})")

doc.close()

print(f"\n输出目录: {OUTPUT_DIR}")
print("请打开合并图检查区域是否对准正确内容")
