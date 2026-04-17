"""测试模板页面匹配和差分比对"""
import sys
from pathlib import Path
_venv_sp = Path("d:/grsxbd/.venv_paddleocr/Lib/site-packages")
if _venv_sp.exists():
    sys.path.insert(0, str(_venv_sp))
_venv_sp2 = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_venv_sp2) not in sys.path:
    sys.path.insert(1, str(_venv_sp2))

from services.template_service import TemplateCompareService

# 加载模板（会在服务启动时做一次）
print("=== 加载模板 ===")
svc = TemplateCompareService(dpi=150, template_path="d:/grsxbd/templates/PDFtemplates.pdf")
print(f"模板页数: {len(svc.template_pages)}")

# 测试：扫描件第1页应该匹配模板第1页（封面）
print("\n=== 分析扫描件页面 ===")
scan_path = "d:/grsxbd/uploads/pdf/d618b858-519f-411a-981e-beb31b62f657.pdf"
import fitz
doc = fitz.open(scan_path)
for page_num in range(min(3, len(doc))):
    page = doc[page_num]
    zoom = 150 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    from PIL import Image
    import tempfile, os, numpy as np
    fd, tmp = tempfile.mkstemp(suffix='.png'); os.close(fd)
    pix.save(tmp)
    scan_img = np.array(Image.open(tmp).convert('L'))
    os.unlink(tmp)

    # 逐一与所有模板页比较 SSIM
    print(f"\n扫描件第{page_num+1}页 (尺寸 {scan_img.shape}) 与模板各页的相似度:")
    for i, tpl in enumerate(svc.template_pages):
        score = svc._compute_ssim(scan_img, tpl)
        print(f"  模板第{i+1}页: SSIM={score:.4f}")
doc.close()

# 测试：差分比对
print("\n=== 差分比对测试 ===")
scan_path = "d:/grsxbd/uploads/pdf/d618b858-519f-411a-981e-beb31b62f657.pdf"
result = svc.compare_and_extract(
    template_pdf="d:/grsxbd/templates/PDFtemplates.pdf",
    scan_pdf=scan_path,
    page=0,
    threshold=30,
    min_area=200
)
print(f"匹配模板页: 第{result['matched_template_page']}页")
print(f"差异率: {result['diff_ratio']:.2f}%")
print(f"差异区域数: {len(result['regions'])}")
for r in result['regions']:
    x1, y1, x2, y2 = r
    print(f"  区域 bbox=({x1},{y1},{x2},{y2}) 面积={abs(x2-x1)*abs(y2-y1)} px")
