"""
test_3pages.pdf 完整 OCR 速度测试 (ASCII safe)
"""
import sys, os, time, json, threading
from pathlib import Path

_venv_sp = Path("d:/grsxbd/.venv_paddleocr/Lib/site-packages")
if _venv_sp.exists():
    sys.path.insert(0, str(_venv_sp))
_venv_sp2 = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_venv_sp2) not in sys.path:
    sys.path.insert(1, str(_venv_sp2))
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

from services.template_service import TemplateCompareService
from services.ocr_service import OCRService
import fitz
import numpy as np
from PIL import Image

TPL_PATH  = "d:/grsxbd/templates/PDFtemplates.pdf"
SCAN_PATH = "d:/grsxbd/uploads/pdf/test_3pages.pdf"
DEBUG_DIR = Path("d:/grsxbd/uploads/debug_test3pages")
DEBUG_DIR.mkdir(exist_ok=True)

_ocr_lock = threading.Lock()

def p(msg):
    """Safe print for Windows GBK console"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8'))

# ── 1. 模板加载 ───────────────────────────────
p("=" * 60)
p("Step 1: Load template")
t0 = time.time()
tpl_svc = TemplateCompareService(dpi=150, template_path=TPL_PATH)
p(f"Template: {len(tpl_svc.template_pages)} pages, time={time.time()-t0:.1f}s")

# ── 2. OCR 引擎 ───────────────────────────────
p("=" * 60)
p("Step 2: Init PaddleOCR")
t0 = time.time()
ocr_svc = OCRService()
p(f"OCR engine init time={time.time()-t0:.1f}s")

# ── 3. 逐页处理 ──────────────────────────────
p("=" * 60)
p("Step 3: Process pages")
doc = fitz.open(SCAN_PATH)
p(f"Scan pages: {len(doc)}")

all_pages = []
grand_ocr_time = 0.0

for page_num in range(len(doc)):
    t_page = time.time()

    # 差异检测
    t_diff = time.time()
    diff = tpl_svc.compare_and_extract(
        template_pdf=TPL_PATH,
        scan_pdf=SCAN_PATH,
        page=page_num,
        threshold=30,
        min_area=200
    )
    t_diff = time.time() - t_diff
    regions  = diff['regions']
    scan_img = diff['scan_img']

    p(f"\n=== Page {page_num+1} ===")
    p(f"  Matched template p{diff['matched_template_page']}, "
      f"diff={diff['diff_ratio']:.2f}%, regions={len(regions)}, diff_time={t_diff:.1f}s")

    page_results = []
    t_ocr_total = 0.0

    if not regions:
        p("  No diff regions, skip OCR")
    else:
        t_ocr_start = time.time()
        with _ocr_lock:
            for i, bbox in enumerate(regions):
                cropped = tpl_svc.crop_region(scan_img, bbox)

                # 保存裁剪图
                cropped_pil = Image.fromarray(cropped)
                cropped_path = DEBUG_DIR / f"p{page_num+1}_r{i+1:02d}.png"
                cropped_pil.save(str(cropped_path))

                t0 = time.time()
                ocr_result = ocr_svc.recognize_image(cropped)
                t_ocr = time.time() - t0
                t_ocr_total += t_ocr

                texts  = ocr_result.get('texts', [])
                tables = ocr_result.get('tables', [])
                # 提取纯文本内容，ASCII-safe
                content_parts = []
                for t in texts:
                    c = t.get('content', '').strip()
                    if c:
                        # 只取可见 ASCII + 中文范围
                        safe = c.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        content_parts.append(safe[:80])

                entry = {
                    "region": i + 1,
                    "bbox": list(bbox),
                    "ocr_time_s": round(t_ocr, 1),
                    "text_count": len(texts),
                    "table_count": len(tables),
                    "content_preview": " | ".join(content_parts)[:150],
                }
                page_results.append(entry)

                has_content = "[OK]" if content_parts else "[EMPTY]"
                t_str = f"{t_ocr:.1f}s"
                preview = content_parts[0][:50] if content_parts else ""
                p(f"  R{i+1:02d} bbox={bbox} {len(texts)}txt {len(tables)}tbl "
                  f"{has_content} {t_str}  {preview}")

        grand_ocr_time += t_ocr_total

    t_page_total = time.time() - t_page
    all_pages.append({
        "scan_page": page_num + 1,
        "matched_template_page": diff['matched_template_page'],
        "diff_ratio": round(diff['diff_ratio'], 2),
        "regions_count": len(regions),
        "page_time_s": round(t_page_total, 1),
        "diff_time_s": round(t_diff, 1),
        "ocr_time_s": round(t_ocr_total, 1),
        "avg_ocr_per_region_s": round(t_ocr_total / len(regions), 1) if regions else 0,
        "results": page_results,
    })

doc.close()

# ── 4. 汇总 ───────────────────────────────
p("\n" + "=" * 60)
p("SUMMARY")
p("=" * 60)

total_regions = sum(p['regions_count'] for p in all_pages)
total_time    = sum(p['page_time_s'] for p in all_pages)
regions_with_text = sum(
    sum(1 for r in p['results'] if r['text_count'] > 0 or r['table_count'] > 0)
    for p in all_pages
)

for p in all_pages:
    r = p['regions_count']
    p(f"  Page{p['scan_page']}: {r} regions diff={p['diff_ratio']}%  "
      f"total={p['page_time_s']}s (diff={p['diff_time_s']}s + ocr={p['ocr_time_s']}s "
      f"avg={p['avg_ocr_per_region_s']}s/r)")

p(f"\n  Total pages: {len(all_pages)}")
p(f"  Total regions: {total_regions}")
p(f"  Regions with content: {regions_with_text}/{total_regions}")
p(f"  Total time: {total_time:.1f}s")
p(f"  OCR time: {grand_ocr_time:.1f}s")
p(f"  Avg per region: {grand_ocr_time/total_regions:.1f}s")
p(f"  Speed: {total_regions/(grand_ocr_time/60):.1f} regions/min")

report = {
    "scan_file": str(SCAN_PATH),
    "pages": all_pages,
    "summary": {
        "total_pages": len(all_pages),
        "total_regions": total_regions,
        "regions_with_content": regions_with_text,
        "total_time_s": round(total_time, 1),
        "ocr_time_s": round(grand_ocr_time, 1),
        "avg_per_region_s": round(grand_ocr_time / total_regions, 1) if total_regions else 0,
        "speed_regions_per_min": round(total_regions / (grand_ocr_time / 60), 1) if grand_ocr_time else 0,
    }
}

report_path = DEBUG_DIR / "test3pages_report.json"
with open(str(report_path), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
p(f"\nFull report: {report_path}")
