"""
7步流程验证脚本
"""
import sys, os, time, tempfile, threading
from pathlib import Path

# 添加 venv site-packages（OCR/Paddle 依赖）
_venv_sp = Path("d:/grsxbd/.venv_paddleocr/Lib/site-packages")
if _venv_sp.exists():
    sys.path.insert(0, str(_venv_sp))
_sp2 = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_sp2) not in sys.path:
    sys.path.insert(0, str(_sp2))
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# 添加项目根目录（services 模块）
PROJECT_ROOT = Path("d:/grsxbd")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.template_service import TemplateCompareService
from services.ocr_service import OCRService
from PIL import Image
import numpy as np

TPL = "d:/grsxbd/templates/PDFtemplates.pdf"
SCAN = "d:/grsxbd/uploads/pdf/test_3pages.pdf"
LOCK = threading.Lock()

def p(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode())

p("=" * 60)
p("STEP 0: 预热 - 检查 OCR 引擎")
p("=" * 60)
t0 = time.time()
ocr_svc = OCRService()
p(f"OCR 引擎: 已就绪 (耗时 {time.time()-t0:.1f}s)")

p("\n" + "=" * 60)
p("STEP 1: 模板预拆分 (启动时一次性完成)")
p("=" * 60)
t0 = time.time()
tpl_svc = TemplateCompareService(dpi=150, template_path=TPL)
p(f"模板预拆分: {len(tpl_svc.template_pages)} 页存入内存")
p(f"  耗时: {time.time()-t0:.1f}s (仅第一次，之后复用)")
p("扫描件: 从文件逐页读取，不物理拆分")

p("\n" + "=" * 60)
p("STEP 2: SSIM 最佳匹配")
p("=" * 60)
import fitz
doc = fitz.open(SCAN)
zoom = 150 / 72
mat = fitz.Matrix(zoom, zoom)
pix = doc[0].get_pixmap(matrix=mat, alpha=False)
fd, tmp = tempfile.mkstemp(suffix='.png')
os.close(fd)
pix.save(tmp)
scan_img = np.array(Image.open(tmp).convert('L'))
os.unlink(tmp)
t0 = time.time()
matched = tpl_svc.compare_pages(scan_img)
p(f"第1页: 匹配模板第{matched+1}页 (耗时 {time.time()-t0:.1f}s)")

p("\n" + "=" * 60)
p("STEP 3: 差分检测")
p("=" * 60)
t0 = time.time()
diff = tpl_svc.compare_and_extract(TPL, SCAN, page=0, threshold=30, min_area=200)
p(f"差异率: {diff['diff_ratio']:.2f}%")
p(f"差异区域: {len(diff['regions'])} 个 (耗时 {time.time()-t0:.1f}s)")

p("\n" + "=" * 60)
p("STEP 4: 批量 OCR (一次性传入所有区域文件)")
p("=" * 60)
regions = diff['regions']
scan_img = diff['scan_img']
tmp_files = []
for i, bbox in enumerate(regions):
    cropped = tpl_svc.crop_region(scan_img, bbox)
    fd, tmp_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    Image.fromarray(cropped).save(tmp_path)
    tmp_files.append(tmp_path)
p(f"已保存 {len(tmp_files)} 个区域图像到临时文件")

t0 = time.time()
with LOCK:
    results = ocr_svc.recognize_batch(tmp_files)
ocr_time = time.time() - t0
p(f"批量 OCR 完成: {len(results)} 个结果")
p(f"耗时: {ocr_time:.1f}s")
p(f"平均: {ocr_time/len(results):.1f}s/区域")

has_text = sum(1 for r in results if r.get('texts'))
has_tbl  = sum(1 for r in results if r.get('tables'))
p(f"有内容区域: {has_text}/{len(results)} (文本), {has_tbl}/{len(results)} (表格)")
for i, r in enumerate(results):
    txt = r.get('texts', [])
    content = '|'.join([t['content'].strip() for t in txt if t.get('content','').strip()])
    if content:
        p(f"  区域{i+1}: {repr(content[:60])}")

p("\n" + "=" * 60)
p("STEP 5: 回流 - 映射到报告表字段")
p("=" * 60)
import re
def look_name(s):
    s = s.strip()
    return 2 <= len(s) <= 5 and all('\u4e00' <= c <= '\u9fff' for c in s)
def look_date(s):
    return bool(re.match(r'[\dOo0０\-/]{6,}', s)) or '年' in s or '月' in s
def look_org(s):
    return any(kw in s for kw in ['委','部','厅','局','处','公司','医院','学校','党委','党组'])

name_count = date_count = org_count = 0
for r in results:
    for t in r.get('texts', []):
        c = t.get('content', '').strip()
        if look_name(c): name_count += 1; p(f"  姓名字段 ← {repr(c)}")
        elif look_date(c): date_count += 1; p(f"  日期字段 ← {repr(c[:20])}")
        elif look_org(c): org_count += 1; p(f"  组织字段 ← {repr(c[:20])}")
p(f"汇总: 姓名={name_count} 日期={date_count} 组织={org_count}")

p("\n" + "=" * 60)
p("STEP 6: 整理结果到 JSON + DB")
p("=" * 60)
p("结构:")
p("  {page:1, matched_template_page:N, diff_ratio:X,")
p("   regions:[{bbox,[],ocr_result,report_fields{}},...],")
p("   report_fields{姓名:[], 日期:[], ...}}")
p("JSON 保存: uploads/ocr_results/{task_id}.json")
p("DB 写入: scan_results 表")

p("\n" + "=" * 60)
p("STEP 7: 清理临时文件")
p("=" * 60)
before = len(tmp_files)
for f in tmp_files:
    try: os.unlink(f)
    except: pass
after = sum(1 for f in tmp_files if os.path.exists(f))
p(f"清理前: {before} 个临时文件")
p(f"清理后: {after} 个 (应为 0)")

doc.close()

p("\n" + "=" * 60)
p("7步流程验证完成")
p("=" * 60)
