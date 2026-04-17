"""
端到端测试：区域裁剪 → PaddleOCR 识别
验证扫描区域 bbox 是否正确传递给 PaddleOCR 并成功识别内容
"""
import sys
from pathlib import Path

_venv_sp = Path("d:/grsxbd/.venv_paddleocr/Lib/site-packages")
if _venv_sp.exists():
    sys.path.insert(0, str(_venv_sp))
_venv_sp2 = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_venv_sp2) not in sys.path:
    sys.path.insert(1, str(_venv_sp2))

import os
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

from services.template_service import TemplateCompareService
from services.ocr_service import OCRService
import numpy as np
from PIL import Image
import tempfile, time

SCAN_PATH = "d:/grsxbd/uploads/pdf/d618b858-519f-411a-981e-beb31b62f657.pdf"
TPL_PATH  = "d:/grsxbd/templates/PDFtemplates.pdf"

# ──────────────────────────────────────────────
print("=" * 60)
print("Step 1: 加载模板（预拆分）")
print("=" * 60)
t0 = time.time()
tpl_svc = TemplateCompareService(dpi=150, template_path=TPL_PATH)
print(f"模板加载耗时: {time.time()-t0:.1f}s，共 {len(tpl_svc.template_pages)} 页")

# ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("Step 2: 扫描件第1页 → 模板页匹配 + 差异区域检测")
print("=" * 60)
t0 = time.time()
diff = tpl_svc.compare_and_extract(
    template_pdf=TPL_PATH,
    scan_pdf=SCAN_PATH,
    page=0,
    threshold=30,
    min_area=200
)
print(f"差异检测耗时: {time.time()-t0:.1f}s")
print(f"匹配模板页: 第{diff['matched_template_page']}页")
print(f"差异率: {diff['diff_ratio']:.2f}%")
print(f"差异区域数: {len(diff['regions'])}")

regions = diff['regions']
scan_img = diff['scan_img']

if not regions:
    print("未发现差异区域，测试终止")
    exit(0)

# ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("Step 3: 初始化 PaddleOCR 引擎")
print("=" * 60)
t0 = time.time()
ocr_svc = OCRService()
print(f"OCR 引擎初始化耗时: {time.time()-t0:.1f}s")

# ──────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"Step 4: 逐区域 OCR 识别（共 {len(regions)} 个区域）")
print("=" * 60)

results = []
t_total = time.time()

for i, bbox in enumerate(regions):
    x1, y1, x2, y2 = bbox
    area = abs(x2-x1) * abs(y2-y1)

    # 裁剪区域
    cropped = tpl_svc.crop_region(scan_img, bbox)

    # 保存裁剪图用于人工检查
    debug_dir = Path("d:/grsxbd/uploads/debug_regions")
    debug_dir.mkdir(exist_ok=True)
    debug_path = debug_dir / f"scan_p1_r{i+1:02d}_bbox{x1},{y1},{x2},{y2}.png"
    Image.fromarray(cropped).save(str(debug_path))

    t0 = time.time()
    ocr_result = ocr_svc.recognize_image(cropped)
    t_elapsed = time.time() - t0

    texts = ocr_result.get('texts', [])
    tables = ocr_result.get('tables', [])
    text_content = " | ".join([t['content'] for t in texts if t.get('content', '').strip()])
    table_content = " | ".join([t['content'][:50] for t in tables if t.get('content', '').strip()])

    entry = {
        "index": i + 1,
        "bbox": bbox,
        "area": area,
        "texts": texts,
        "tables": tables,
        "text_content": text_content,
        "table_content": table_content,
        "ocr_time": t_elapsed,
    }
    results.append(entry)

    # 打印结果
    tag = "表格" if tables else "文本"
    content_preview = (text_content or table_content)[:60]
    status = "OK" if (texts or tables) else "空白"
    print(f"  区域{i+1:02d}: bbox={bbox} area={area}px "
          f"[{tag}] {status} 耗时={t_elapsed:.1f}s  "
          f"内容: {repr(content_preview)}")
    if texts:
        for t in texts[:3]:
            c = t.get('content', '').strip()
            if c:
                print(f"          → {repr(c)}")

t_total = time.time() - t_total
print(f"\nOCR 总耗时: {t_total:.1f}s，平均每区域: {t_total/len(regions):.1f}s")

# ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("Step 5: 汇总统计")
print("=" * 60)
ok = sum(1 for r in results if r['texts'] or r['tables'])
empty = sum(1 for r in results if not r['texts'] and not r['tables'])
total_texts = sum(len(r['texts']) for r in results)
total_tables = sum(len(r['tables']) for r in results)

print(f"  有内容区域: {ok}/{len(results)}")
print(f"  空白区域:   {empty}/{len(results)}")
print(f"  识别文本块: {total_texts}")
print(f"  识别表格块: {total_tables}")
print(f"  调试图片已保存: {debug_dir}/")

# 保存完整结果
import json
result_path = "d:/grsxbd/uploads/debug_regions/ocr_full_result.json"
with open(result_path, "w", encoding="utf-8") as f:
    json.dump({
        "scan_page": 1,
        "matched_template_page": diff['matched_template_page'],
        "diff_ratio": diff['diff_ratio'],
        "regions_total": len(regions),
        "regions_with_content": ok,
        "regions_empty": empty,
        "total_texts": total_texts,
        "total_tables": total_tables,
        "total_time_seconds": round(t_total, 1),
        "results": results,
    }, f, ensure_ascii=False, indent=2)
print(f"\n完整结果已保存: {result_path}")
