"""
基于预定义区域标注的 OCR 识别测试
使用 PDFtemplates_regions.json 中的标注区域
"""
import sys, os, time, json
from pathlib import Path

_venv_sp = Path("d:/grsxbd/.venv_paddleocr/Lib/site-packages")
if _venv_sp.exists():
    sys.path.insert(0, str(_venv_sp))
_venv_sp2 = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_venv_sp2) not in sys.path:
    sys.path.insert(0, str(_venv_sp2))
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

from services.template_service import TemplateCompareService
from services.ocr_service import OCRService
import fitz
import numpy as np
from PIL import Image
import tempfile, threading

TPL_PATH  = "d:/grsxbd/templates/PDFtemplates.pdf"
SCAN_PATH = "d:/grsxbd/uploads/pdf/test_3pages.pdf"
ANN_FILE  = "d:/grsxbd/templates/PDFtemplates_regions.json"
DPI = 150

def p(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode())

# ── 加载标注配置 ───────────────────────────────
with open(ANN_FILE, "r", encoding="utf-8") as f:
    ann_cfg = json.load(f)
p(f"标注配置: {len(ann_cfg['pages'])} 页已标注")

# ── 加载模板 ──────────────────────────────────
p("\n" + "=" * 60)
p("Step 1: 加载模板服务")
t0 = time.time()
tpl_svc = TemplateCompareService(dpi=DPI, template_path=TPL_PATH)
p(f"  模板页数: {len(tpl_svc.template_pages)}, 耗时: {time.time()-t0:.1f}s")

# ── 加载 OCR ─────────────────────────────────
p("\n" + "=" * 60)
p("Step 2: 初始化 OCR 引擎")
t0 = time.time()
ocr_svc = OCRService()
p(f"  OCR 引擎就绪, 耗时: {time.time()-t0:.1f}s")

_ocr_lock = threading.Lock()

# ── 找最佳匹配且有标注的模板页 ────────────────────
p("\n" + "=" * 60)
p("Step 3: SSIM 页面匹配（优先使用有标注的模板页）")

# 加载扫描件第1页
doc = fitz.open(SCAN_PATH)
zoom = DPI / 72
mat = fitz.Matrix(zoom, zoom)
pix = doc[0].get_pixmap(matrix=mat, alpha=False)
fd, tmp = tempfile.mkstemp(suffix='.png'); os.close(fd)
pix.save(tmp)
scan_img = np.array(Image.open(tmp).convert('L'))
os.unlink(tmp)

ann_pages = {pg["page"]: pg["regions"] for pg in ann_cfg["pages"]}
annotated_page_nums = sorted(ann_pages.keys())
p(f"  已标注的模板页: {annotated_page_nums}")

t0 = time.time()
best_idx, best_score = 0, -1.0
for i, tpl in enumerate(tpl_svc.template_pages):
    s = tpl_svc._compute_ssim(scan_img, tpl)
    if s > best_score:
        best_score = s
        best_idx = i
match_time = time.time() - t0
p(f"  全局最佳: 模板第 {best_idx+1} 页, SSIM={best_score:.4f}, 耗时: {match_time:.2f}s")

# 如果全局最佳页没有标注，依次尝试其他有标注的页
matched_template_page = best_idx + 1  # 1-based
if matched_template_page not in ann_pages:
    p(f"  模板第 {matched_template_page} 页无标注，尝试备选...")
    # 按 SSIM 排序所有页，找第一个有标注的
    all_scores = [(i+1, tpl_svc._compute_ssim(scan_img, t)) for i, t in enumerate(tpl_svc.template_pages)]
    all_scores.sort(key=lambda x: -x[1])
    for try_page, try_score in all_scores:
        if try_page in ann_pages:
            matched_template_page = try_page
            p(f"  选用: 模板第 {try_page} 页 (SSIM={try_score:.4f})，已标注 {len(ann_pages[try_page])} 个区域")
            break

# ── 获取该模板页的标注区域 ────────────────────
p("\n" + "=" * 60)
p(f"Step 4: 提取预定义区域（模板第 {matched_template_page} 页）")

regions = ann_pages.get(matched_template_page, [])
if not regions:
    p(f"  警告: 模板第 {matched_template_page} 页尚无标注！")
    doc.close()
    exit()

p(f"  标注区域数: {len(regions)}")
for r in regions:
    w, h = r['x2']-r['x1'], r['y2']-r['y1']
    p(f"    [{r['index']:2d}] {r['label']:<12s} bbox=[{r['x1']:4d},{r['y1']:4d},{r['x2']:4d},{r['y2']:4d}]  size={w}x{h}")

# ── 裁剪并保存区域图像 ────────────────────────
p("\n" + "=" * 60)
p("Step 5: 裁剪区域图像（等比缩放标注坐标）")

# 模板标注尺寸 vs 实际扫描件尺寸
ann_w, ann_h = ann_cfg['page_width'], ann_cfg['page_height']
scan_h, scan_w = scan_img.shape  # H x W
p(f"  标注基准: {ann_w}x{ann_h}, 扫描件: {scan_w}x{scan_h}")

scale_x = scan_w / ann_w
scale_y = scan_h / ann_h
p(f"  缩放系数: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")

tmp_files = []
DEBUG_DIR = Path("d:/grsxbd/uploads/debug_annotation")
DEBUG_DIR.mkdir(exist_ok=True)

for i, r in enumerate(regions):
    # 标注坐标 → 扫描件坐标
    x1 = int(r['x1'] * scale_x)
    y1 = int(r['y1'] * scale_y)
    x2 = int(r['x2'] * scale_x)
    y2 = int(r['y2'] * scale_y)
    # 边界保护
    x1, x2 = max(0, x1), min(scan_w, x2)
    y1, y2 = max(0, y1), min(scan_h, y2)
    w, h = x2-x1, y2-y1
    if w <= 0 or h <= 0:
        p(f"    [{r['index']:2d}] {r['label']}: 跳过（宽/高为0）")
        continue
    cropped = scan_img[y1:y2, x1:x2]
    cropped_pil = Image.fromarray(cropped)
    out_path = DEBUG_DIR / f"scan_p1_r{i+1:02d}_{r['label']}.png"
    cropped_pil.save(str(out_path))
    tmp_files.append(str(out_path))
    p(f"    [{r['index']:2d}] {r['label']:<12s}: [{x1:4d},{y1:4d},{x2:4d},{y2:4d}] {w}x{h}")

p(f"  已保存 {len(tmp_files)} 个区域裁剪图到 {DEBUG_DIR}")

# ── 批量 OCR ────────────────────────────────
p("\n" + "=" * 60)
p("Step 6: 批量 OCR")
t0 = time.time()
with _ocr_lock:
    ocr_results = ocr_svc.recognize_batch(tmp_files)
ocr_total = time.time() - t0

p(f"  总耗时: {ocr_total:.1f}s")
p(f"  平均每区域: {ocr_total/len(ocr_results):.1f}s")

# ── 输出结果 ────────────────────────────────
p("\n" + "=" * 60)
p("Step 7: OCR 结果")
total_texts = 0
for i, (r, res) in enumerate(zip(regions, ocr_results)):
    texts = res.get('texts', [])
    tables = res.get('tables', [])
    total_texts += len(texts)
    content = ' | '.join([t['content'].strip() for t in texts if t.get('content','').strip()])
    icon = "[OK]" if content else "[  ]"
    t_ocr = res.get('_ocr_time_ms', 0)
    p(f"  {icon} {r['label']:<12s}: {repr(content[:80])}  ({t_ocr:.0f}ms)")

p(f"\n  汇总: {total_texts} 段文本, {ocr_total:.1f}s 总耗时")

# ── 保存报告 ────────────────────────────────
report = {
    "scan_page": 1,
    "matched_template_page": matched_template_page,
    "total_regions": len(regions),
    "ocr_total_time_s": round(ocr_total, 1),
    "avg_per_region_s": round(ocr_total / len(regions), 1),
    "regions": [
        {
            "index": r['index'],
            "label": r['label'],
            "bbox": [r['x1'], r['y1'], r['x2'], r['y2']],
            "ocr_time_ms": res.get('_ocr_time_ms', 0),
            "texts": [t['content'].strip() for t in res.get('texts',[]) if t.get('content','').strip()],
            "tables_count": len(res.get('tables',[])),
        }
        for r, res in zip(regions, ocr_results)
    ]
}
report_path = DEBUG_DIR / "annotation_test_report.json"
with open(str(report_path), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
p(f"\n报告已保存: {report_path}")

doc.close()
p("\n完成！")
