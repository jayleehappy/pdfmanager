# -*- coding: utf-8 -*-
"""
测试 PaddleOCR 分离模型组合:
检测: PP-OCRv4 (轻量) + 识别: PP-OCRv5_server_rec (高精度)
对比:
  A. PP-OCRv3 检测 + PP-OCRv3 识别 (纯v3)
  B. PP-OCRv4 检测 + PP-OCRv5_server_rec 识别
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, r"D:/grsxbd/.venv_paddleocr/Lib/site-packages")
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import fitz
from paddleocr import PaddleOCR

OUTPUT_DIR = Path(r"D:/grsxbd/tests/paddle_official_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载 GT
jsonl_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/[OCR]_page_003_20260416_0156.jsonl")
with open(jsonl_path, encoding="utf-8") as f:
    gt_data = json.load(f)
gt_items = gt_data["data"]

# 渲染 PDF (300 DPI，与 UmiOCR 处理时的分辨率接近)
pdf_path = Path(r"D:/grsxbd/uploads/pdf/temp_split/page_003.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
mat = fitz.Matrix(200/72, 200/72)  # 200 DPI
pix = page.get_pixmap(matrix=mat, alpha=False)
img_path = OUTPUT_DIR / "page_003_200dpi.png"
pix.save(str(img_path))
doc.close()

w, h = pix.width, pix.height
print(f"[INFO] 图片尺寸: {w}x{h} ({200} DPI)")

# 提取 GT 裁剪区域 (坐标按 200 DPI 换算)
# UmiOCR 用 72 DPI 坐标，这里 200 DPI 需要 x200/72 缩放
scale = 200 / 72
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
    x0, x1 = min(xs)*scale, max(xs)*scale
    y0, y1 = min(ys)*scale, max(ys)*scale
    pad = 10
    rx0 = max(0, x0 - pad)
    ry0 = max(0, y0 - pad)
    rx1 = min(w, x1 + pad)
    ry1 = min(h, y1 + pad)
    if rx1-rx0 < 20 or ry1-ry0 < 10:
        continue
    try:
        clip = fitz.Rect(rx0, ry0, rx1, ry1)
        crop_pix = page2.get_pixmap(matrix=mat, clip=clip)
        if crop_pix.width < 15 or crop_pix.height < 8:
            continue
        crop_path = OUTPUT_DIR / f"paddle_crop_{i:03d}.png"
        crop_pix.save(str(crop_path))
        crops.append({
            "index": i, "gt_text": text,
            "crop_path": str(crop_path),
            "crop_size": [crop_pix.width, crop_pix.height],
        })
    except:
        pass
doc2.close()
print(f"[INFO] 提取裁剪: {len(crops)} 个")

crop_paths = [c["crop_path"] for c in crops]

# ── 测试A: PP-OCRv3 检测+识别 (轻量) ──
print("\n" + "=" * 60)
print("测试A: PP-OCRv3 (det+rec) — 轻量版")
print("=" * 60)
start = time.time()
ocrA = PaddleOCR(lang="ch", ocr_version="PP-OCRv3", use_textline_orientation=False)
loadA = time.time() - start
print(f"加载: {loadA:.1f}s")

start = time.time()
resultsA = ocrA.ocr(str(img_path))
timeA = time.time() - start
print(f"全页检测: {timeA:.1f}s")
n_detected = len(resultsA[0]) if resultsA and resultsA[0] else 0
print(f"检测到: {n_detected} 个区域")

# ── 测试B: PP-OCRv4 检测 + PP-OCRv5_server_rec 识别 ──
print("\n" + "=" * 60)
print("测试B: PP-OCRv4 检测 + PP-OCRv5_server_rec 识别")
print("=" * 60)
start = time.time()
ocrB = PaddleOCR(
    text_detection_model_name="PP-OCRv4",
    text_recognition_model_name="PP-OCRv5_server_rec",
    use_textline_orientation=False,
)
loadB = time.time() - start
print(f"加载: {loadB:.1f}s")

start = time.time()
resultsB = ocrB.ocr(str(img_path))
timeB = time.time() - start
print(f"全页检测: {timeB:.1f}s")
n_detected_B = len(resultsB[0]) if resultsB and resultsB[0] else 0
print(f"检测到: {n_detected_B} 个区域")

# ── 单独测试: 用 PP-OCRv5_server_rec 识别 UmiOCR 的检测框 ──
print("\n" + "=" * 60)
print("测试C: UmiOCR 检测框 + PP-OCRv5_server_rec 识别")
print("=" * 60)
from paddleocr import TextRecognition
start = time.time()
recModel = TextRecognition(model_name="PP-OCRv5_server_rec", device="cpu")
loadC = time.time() - start
print(f"加载识别模型: {loadC:.1f}s")

start = time.time()
resultsC = recModel.predict(input=crop_paths, batch_size=8)
timeC = time.time() - start
print(f"识别 {len(crop_paths)} 个裁剪: {timeC:.1f}s ({timeC/len(crop_paths)*1000:.1f}ms/区域)")

# ── 评估 ──
def calc_acc(results, crops, label):
    correct = partial = total = 0
    errors = []
    for i, res in enumerate(results):
        if isinstance(res, list) and res:
            rec_text = res[0][1][0] if res else ""
        else:
            rec_text = str(res).strip()
        gt = crops[i]["gt_text"].strip()
        if not gt:
            continue
        total += 1
        match = (rec_text == gt)
        chars = set(gt) & set(rec_text)
        partial_ok = gt in rec_text or rec_text in gt or (
            len(chars) >= min(3, len(gt)) and len(chars)/max(len(set(gt)),1) >= 0.5
        )
        if match:
            correct += 1
        elif partial_ok:
            partial += 1
        else:
            errors.append((gt, rec_text))
    acc = correct/total*100 if total else 0
    pacc = (correct+partial)/total*100 if total else 0
    print(f"\n{label}: 完全={correct}/{total}={acc:.1f}% | 部分={correct+partial}/{total}={pacc:.1f}%")
    if errors:
        print("  错误示例:")
        for e in errors[:5]:
            print(f"    GT:{e[0][:20]!r:22s}  Rec:{e[1][:20]!r}")
    return acc, pacc

if n_detected > 0:
    accA, _ = calc_acc([r[1] for r in resultsA[0]], crops[:len(resultsA[0])], "A PP-OCRv3")
if n_detected_B > 0:
    accB, _ = calc_acc([r[1] for r in resultsB[0]], crops[:len(resultsB[0])], "B PP-OCRv4+PP5")

accC, _ = calc_acc(resultsC, crops, "C UmiOCR检测+PP5识别")

# 总结
print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print(f"  A. PP-OCRv3 检测+识别: {timeA:.1f}s/页, 检测{n_detected}个区域")
print(f"  B. PP-OCRv4 检测+PP5识别: {timeB:.1f}s/页, 检测{n_detected_B}个区域")
print(f"  C. UmiOCR检测+PP5识别: {gt_data.get('time',0):.2f}s(检测)+{timeC:.1f}s(识别)")
print(f"\n  UmiOCR纯检测: {gt_data.get('time',0):.2f}s")
