# -*- coding: utf-8 -*-
"""
官方 PaddleOCR PP-OCRv5_server_rec 识别质量测试
方法: 用高分辨率渲染提取文字裁剪区，对比识别效果
"""
import sys, os, time, json
from pathlib import Path

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
sys.path.insert(0, r"D:/grsxbd/.venv_paddleocr/Lib/site-packages")

import fitz
import paddleocr
from paddleocr import TextRecognition
from PIL import Image
import numpy as np

OUTPUT_DIR = Path(r"D:/grsxbd/tests/paddle_official_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════
# 1. 用 PaddleOCR-json 的结果提取裁剪区域
# ══════════════════════════════════════════════════════════
jsonl_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/[OCR]_page_003_20260416_0156.jsonl")
with open(jsonl_path, encoding="utf-8") as f:
    gt_data = json.load(f)
gt_items = gt_data["data"]
print(f"[INFO] PaddleOCR-json 结果: {len(gt_items)} 个区域, 耗时 {gt_data.get('time','N/A')}s")

# 渲染PDF: 高分辨率以确保文字清晰
pdf_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/page_003.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
render_dpi = 72
zoom = 1.0  # fitz base is 72 DPI, zoom=1 gives 72 DPI
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat, alpha=False)
img_path = OUTPUT_DIR / "page_003_72dpi.png"
pix.save(img_path)
rendered_w, rendered_h = pix.width, pix.height
doc.close()
long_side = max(rendered_w, rendered_h)
print(f"[INFO] 渲染: {rendered_w}x{rendered_h} (DPI={render_dpi})")

# PaddleOCR-json 的 limit_side_len=960
# 当渲染图 < 960px 时, OCR 不进行缩放, 直接处理原图
# 坐标无需转换，直接使用
print(f"[INFO] OCR坐标系统: 直接像素坐标 (因 {long_side}px < 960px, 无缩放)")
ocr_scale = 1.0  # 无缩放

# 提取裁剪
# PaddleOCR-json 的 box 是多边形 [[x,y],[x,y],[x,y],[x,y]]
# 坐标在 OCR 内部坐标系 (max 960px), 与72DPI渲染图1:1对应
crop_infos = []
doc2 = fitz.open(pdf_path)
page2 = doc2[0]

for i, item in enumerate(gt_items):
    text = item["text"].strip()
    if not text:
        continue

    box = item["box"]
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    x0_ocr, x1_ocr = min(xs), max(xs)
    y0_ocr, y1_ocr = min(ys), max(ys)

    # 转换到 300 DPI 渲染图坐标
    pad = 5
    rx0 = max(0.0, x0_ocr / ocr_scale - pad)
    ry0 = max(0.0, y0_ocr / ocr_scale - pad)
    rx1 = min(float(rendered_w), x1_ocr / ocr_scale + pad)
    ry1 = min(float(rendered_h), y1_ocr / ocr_scale + pad)

    crop_w = rx1 - rx0
    crop_h = ry1 - ry0
    if crop_w < 20 or crop_h < 10:
        continue

    try:
        clip = fitz.Rect(rx0, ry0, rx1, ry1)
        crop_pix = page2.get_pixmap(matrix=mat, clip=clip)
        if crop_pix.width < 15 or crop_pix.height < 8:
            continue
        crop_path = OUTPUT_DIR / f"crop_{i:03d}.png"
        crop_pix.save(str(crop_path))
        crop_infos.append({
            "index": i,
            "paddleocr_json_text": text,
            "paddleocr_json_score": item.get("score", 0),
            "crop_path": str(crop_path),
            "crop_size": [crop_pix.width, crop_pix.height],
            "box_ocr": [x0_ocr, y0_ocr, x1_ocr, y1_ocr],
        })
    except Exception as e:
        print(f"  [WARN] 跳过区域 {i}: {e}")

doc2.close()
print(f"[INFO] 提取裁剪: {len(crop_infos)} 个 (共 {len(gt_items)} 个区域)")

# ══════════════════════════════════════════════════════════
# 2. 加载 PP-OCRv5_server_rec 模型
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PP-OCRv5_server_rec TextRecognition 测试")
print("=" * 60)

start = time.time()
model = TextRecognition(model_name="PP-OCRv5_server_rec", device="cpu")
load_time = time.time() - start
print(f"模型加载: {load_time:.1f}s")

crop_paths = [c["crop_path"] for c in crop_infos]
print(f"识别 {len(crop_paths)} 个区域...")

start = time.time()
results = model.predict(input=crop_paths, batch_size=8)
rec_time = time.time() - start
print(f"识别耗时: {rec_time:.2f}s ({rec_time/len(crop_paths)*1000:.1f}ms/区域)")

# ══════════════════════════════════════════════════════════
# 3. 整理结果
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("识别结果对比")
print("=" * 60)

correct = 0
partial = 0
total = 0
details = []

for i, res in enumerate(results):
    gt_text = crop_infos[i]["paddleocr_json_text"]
    pp5_text = res['rec_text'].strip()
    pp5_score = res['rec_score']

    # 完全匹配
    match = (pp5_text == gt_text.strip())
    # 部分匹配
    gt_clean = gt_text.strip()
    partial_match = (
        (gt_clean and pp5_text and (
            gt_clean in pp5_text or
            pp5_text in gt_clean or
            # 检查共同字符比例
            (len(set(gt_clean) & set(pp5_text)) >= min(3, len(gt_clean)) and
             len(set(gt_clean) & set(pp5_text)) / max(len(set(gt_clean)), 1) >= 0.5)
        ))
    )

    if gt_clean:
        total += 1
        if match:
            correct += 1
        elif partial_match:
            partial += 1

    details.append({
        "index": i,
        "gt_text": gt_text,
        "pp5_text": pp5_text,
        "pp5_score": float(pp5_score),
        "match": match,
        "partial": partial_match and not match,
    })

acc = correct / total * 100 if total > 0 else 0
partial_acc = (correct + partial) / total * 100 if total > 0 else 0

print(f"\n完全一致: {correct}/{total} = {acc:.1f}%")
print(f"部分一致: {correct+partial}/{total} = {partial_acc:.1f}%")
print(f"识别耗时: {rec_time:.2f}s ({rec_time/total*1000:.1f}ms/区域)")

print("\n对比详情 (前30个):")
print("-" * 80)
for i, d in enumerate(details[:30]):
    flag = "OK" if d["match"] else ("~" if d["partial"] else "XX")
    print(f"  [{i+1:2d}] [{flag}] GT: {d['gt_text'][:20]:<22s} PP5: {d['pp5_text'][:20]:<22s} conf:{d['pp5_score']:.3f}")

# 错误分析
errors = [d for d in details if d["gt_text"] and not d["match"] and not d["partial"]]
partials = [d for d in details if d["gt_text"] and d["partial"] and not d["match"]]
print(f"\n完全错误 ({len(errors)} 个):")
for d in errors[:10]:
    print(f"  GT: {d['gt_text']!r:25s}  PP5: {d['pp5_text']!r:25s}  conf:{d['pp5_score']:.3f}")
print(f"\n部分匹配 ({len(partials)} 个):")
for d in partials[:10]:
    print(f"  GT: {d['gt_text']!r:25s}  PP5: {d['pp5_text']!r:25s}  conf:{d['pp5_score']:.3f}")

# ══════════════════════════════════════════════════════════
# 4. 保存结果
# ══════════════════════════════════════════════════════════
summary = {
    "model": "PP-OCRv5_server_rec (TextRecognition)",
    "device": "cpu",
    "test_source": "PaddleOCR-json results on page_003 (200 DPI render)",
    "render_dpi": render_dpi,
    "ocr_scale_ratio": ocr_scale,
    "total_gt": len(gt_items),
    "extracted_crops": len(crop_infos),
    "tested": total,
    "load_time_s": round(load_time, 1),
    "rec_time_s": round(rec_time, 2),
    "ms_per_crop": round(rec_time / len(crop_infos) * 1000, 1),
    "accuracy_full": round(acc, 1),
    "accuracy_partial": round(partial_acc, 1),
    "correct": correct,
    "partial": partial,
    "errors": len(errors),
    "paddleocr_json_info": {
        "total_regions": len(gt_items),
        "rec_time_s": gt_data.get("time", 0),
    },
    "details": details,
}

with open(OUTPUT_DIR / "pp5_recognition_test.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n[OK] 结果已保存: {OUTPUT_DIR / 'pp5_recognition_test.json'}")
print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
