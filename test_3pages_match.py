"""
专项测试：test_3pages.pdf 与模板的匹配 + 差异检测
该文件第1页与模板第1页（封面）一致，验证差异率是否接近0
"""
import sys
from pathlib import Path
_venv_sp = Path("d:/grsxbd/.venv_paddleocr/Lib/site-packages")
if _venv_sp.exists():
    sys.path.insert(0, str(_venv_sp))
_venv_sp2 = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_venv_sp2) not in sys.path:
    sys.path.insert(1, str(_venv_sp2))

from services.template_service import TemplateCompareService
import fitz
import time

TPL_PATH = "d:/grsxbd/templates/PDFtemplates.pdf"
SCAN_PATH = "d:/grsxbd/uploads/pdf/test_3pages.pdf"

print("=" * 60)
print("加载模板")
print("=" * 60)
t0 = time.time()
svc = TemplateCompareService(dpi=150, template_path=TPL_PATH)
print(f"耗时: {time.time()-t0:.1f}s，共 {len(svc.template_pages)} 页")

print("\n" + "=" * 60)
print("逐页分析 test_3pages.pdf")
print("=" * 60)

import tempfile, os, numpy as np
from PIL import Image

doc = fitz.open(SCAN_PATH)
print(f"扫描件总页数: {len(doc)}")

for page_num in range(len(doc)):
    page = doc[page_num]
    zoom = 150 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    fd, tmp = tempfile.mkstemp(suffix='.png'); os.close(fd)
    pix.save(tmp)
    scan_img = np.array(Image.open(tmp).convert('L'))
    os.unlink(tmp)

    # 计算与所有模板页的相似度
    best_idx, best_score = 0, -1.0
    scores = []
    for i, tpl in enumerate(svc.template_pages):
        score = svc._compute_ssim(scan_img, tpl)
        scores.append((i+1, score))
        if score > best_score:
            best_score = score
            best_idx = i

    print(f"\n第{page_num+1}页 (尺寸 {scan_img.shape}):")
    print(f"  最佳匹配: 模板第{best_idx+1}页, SSIM={best_score:.4f}")

    # 前5高分
    top5 = sorted(scores, key=lambda x: -x[1])[:5]
    print(f"  Top5: " + " | ".join(f"模板{i}={s:.3f}" for i,s in top5))

    # 差分比对
    t0 = time.time()
    diff = svc.compare_and_extract(
        template_pdf=TPL_PATH,
        scan_pdf=SCAN_PATH,
        page=page_num,
        threshold=30,
        min_area=200
    )
    print(f"  差异率: {diff['diff_ratio']:.2f}%, 区域数: {len(diff['regions'])}, "
          f"匹配模板页: 第{diff['matched_template_page']}页, 耗时: {time.time()-t0:.1f}s")

doc.close()
