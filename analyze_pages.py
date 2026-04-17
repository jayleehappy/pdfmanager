"""分析模板和扫描件的页面结构"""
import sys
from pathlib import Path

_venv_sp = Path("d:/grsxbd/.venv_paddleocr/Lib/site-packages")
if _venv_sp.exists():
    sys.path.insert(0, str(_venv_sp))
_venv_sp2 = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_venv_sp2) not in sys.path:
    sys.path.insert(1, str(_venv_sp2))

import fitz

def analyze_pdf(path, name):
    doc = fitz.open(path)
    print(f"\n{'='*50}")
    print(f"{name}: {len(doc)} 页")
    print(f"{'='*50}")
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text().strip()[:120]
        print(f"  第{i+1}页: {page.rect.width:.0f}x{page.rect.height:.0f}pt | {repr(text)}")
    doc.close()

# 分析模板
tpl_path = Path("d:/grsxbd/templates/PDFtemplates.pdf")
analyze_pdf(str(tpl_path), "模板 PDF")

# 分析扫描件
scan_path = Path("d:/grsxbd/uploads/pdf/d618b858-519f-411a-981e-beb31b62f657.pdf")
if scan_path.exists():
    analyze_pdf(str(scan_path), "扫描件 PDF")
else:
    print(f"\n扫描件不存在: {scan_path}")

# 也分析 test_3pages
test3 = Path("d:/grsxbd/uploads/pdf/test_3pages.pdf")
if test3.exists():
    analyze_pdf(str(test3), "test_3pages")
