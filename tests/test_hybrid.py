# -*- coding: utf-8 -*-
"""
混合方案测试: UmiOCR 检测 + PP-OCRv5_server_rec 识别
思路: UmiOCR(PaddleOCR-json) 负责文字区域检测,
      官方 PP-OCRv5_server_rec 负责文字识别 (精度更高)
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, r"D:/grsxbd/.venv_paddleocr/Lib/site-packages")
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import fitz
import paddleocr
from paddleocr import TextRecognition

OUTPUT_DIR = Path(r"D:/grsxbd/tests/paddle_official_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 加载 Ground Truth (UmiOCR 检测结果) ──────────────────
jsonl_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/[OCR]_page_003_20260416_0156.jsonl")
with open(jsonl_path, encoding="utf-8") as f:
    gt_data = json.load(f)
gt_items = gt_data["data"]
print(f"[INFO] UmiOCR 检测: {len(gt_items)} 个区域, 耗时 {gt_data.get('time','N/A')}s")

# ── 渲染 PDF (72 DPI, 与 UmiOCR 坐标一致) ─────────────────
pdf_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/page_003.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
mat = fitz.Matrix(1.0, 1.0)
pix = page.get_pixmap(matrix=mat)
img_path = OUTPUT_DIR / "page_003_hybrid.png"
pix.save(str(img_path))
doc.close()

# 提取裁剪区域 (坐标 1:1)
crops = []
doc2 = fitz.open(pdf_path)
page2 = doc2[0]

for i, item in enumerate(gt_items):
    text = item["text"].strip()
    if not text:
        continue
    box = item["box"]
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)

    pad = 5
    rx0 = max(0, x0 - pad)
    ry0 = max(0, y0 - pad)
    rx1 = min(pix.width, x1 + pad)
    ry1 = min(pix.height, y1 + pad)

    if rx1 - rx0 < 15 or ry1 - ry0 < 8:
        continue

    try:
        clip = fitz.Rect(rx0, ry0, rx1, ry1)
        crop_pix = page2.get_pixmap(matrix=mat, clip=clip)
        if crop_pix.width < 15 or crop_pix.height < 8:
            continue
        crop_path = OUTPUT_DIR / f"hybrid_crop_{i:03d}.png"
        crop_pix.save(str(crop_path))
        crops.append({
            "index": i,
            "gt_text": text,
            "gt_score": item.get("score", 0),
            "crop_path": str(crop_path),
            "crop_size": [crop_pix.width, crop_pix.height],
        })
    except Exception as e:
        print(f"  [WARN] 跳过 {i}: {e}")

doc2.close()
print(f"[INFO] 提取裁剪: {len(crops)} 个")

# ══════════════════════════════════════════════════════════
# 混合识别: PP-OCRv5_server_rec
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("混合方案: UmiOCR 检测 + PP-OCRv5_server_rec 识别")
print("=" * 60)

start = time.time()
model = TextRecognition(model_name="PP-OCRv5_server_rec", device="cpu")
load_time = time.time() - start
print(f"模型加载: {load_time:.1f}s")

crop_paths = [c["crop_path"] for c in crops]
print(f"识别 {len(crop_paths)} 个区域...")

start = time.time()
results = model.predict(input=crop_paths, batch_size=8)
rec_time = time.time() - start

# 解析
correct = 0
partial = 0
total = 0
details = []

for i, res in enumerate(results):
    gt = crops[i]["gt_text"]
    pp5 = res['rec_text'].strip()
    score = res['rec_score']

    match = (pp5 == gt.strip())
    gt_clean = gt.strip()
    partial_match = (
        gt_clean and pp5 and (
            gt_clean in pp5 or pp5 in gt_clean or
            (len(set(gt_clean) & set(pp5)) >= min(3, len(gt_clean)) and
             len(set(gt_clean) & set(pp5)) / max(len(set(gt_clean)), 1) >= 0.5)
        )
    )

    if gt_clean:
        total += 1
        if match:
            correct += 1
        elif partial_match:
            partial += 1

    details.append({
        "index": i,
        "gt_text": gt,
        "pp5_text": pp5,
        "pp5_score": float(score),
        "match": match,
        "partial": partial_match and not match,
    })

acc = correct / total * 100 if total > 0 else 0
partial_acc = (correct + partial) / total * 100 if total > 0 else 0

print(f"\n识别耗时: {rec_time:.2f}s | {rec_time/len(crops)*1000:.1f}ms/区域")
print(f"完全一致: {correct}/{total} = {acc:.1f}%")
print(f"部分一致: {correct+partial}/{total} = {partial_acc:.1f}%")

print("\n对比 (前25个):")
print("-" * 80)
for i, d in enumerate(details[:25]):
    flag = "OK" if d["match"] else ("~" if d["partial"] else "XX")
    print(f"  [{i+1:2d}] [{flag}] GT-UmiOCR: {d['gt_text'][:20]:<22s}  PP5-Rec: {d['pp5_text'][:20]:<22s} conf:{d['pp5_score']:.3f}")

errors = [d for d in details if d["gt_text"] and not d["match"] and not d["partial"]]
print(f"\n完全错误 ({len(errors)} 个):")
for d in errors[:10]:
    print(f"  GT: {d['gt_text']!r:28s}  PP5: {d['pp5_text']!r:28s}  {d['pp5_score']:.3f}")

# 总结
print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print(f"  检测引擎: UmiOCR (PaddleOCR-json)")
print(f"  识别引擎: PP-OCRv5_server_rec (官方)")
print(f"  总耗时: {gt_data.get('time',0):.3f}s (检测) + {rec_time:.2f}s (识别)")
print(f"  完全准确率: {acc:.1f}%")
print(f"  部分准确率: {partial_acc:.1f}%")

# 对比: 纯 UmiOCR
import unicodedata
def is_readable(t):
    return all(unicodedata.category(c) != 'Co' for c in t) and len(t.strip()) > 0

umi_readable = sum(1 for item in gt_items if is_readable(item['text']))
print(f"\n  纯 UmiOCR 有效率: {umi_readable}/{len(gt_items)} = {umi_readable/len(gt_items)*100:.0f}%")

# 保存
out = {
    "method": "Hybrid: UmiOCR detection + PP-OCRv5_server_rec recognition",
    "detection": {"engine": "UmiOCR (PaddleOCR-json)", "time_s": gt_data.get("time", 0), "regions": len(gt_items)},
    "recognition": {"model": "PP-OCRv5_server_rec", "load_time_s": round(load_time, 1), "rec_time_s": round(rec_time, 2), "ms_per_region": round(rec_time/len(crops)*1000, 1)},
    "accuracy": {"full": round(acc, 1), "partial": round(partial_acc, 1), "correct": correct, "total": total},
    "pure_umiocr_readable": f"{umi_readable}/{len(gt_items)} = {umi_readable/len(gt_items)*100:.0f}%",
    "details": details,
}
with open(OUTPUT_DIR / "hybrid_test.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n[OK] 结果: {OUTPUT_DIR / 'hybrid_test.json'}")
print("\n完成!")
