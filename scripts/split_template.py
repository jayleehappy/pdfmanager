"""
模板 PDF 预拆分脚本
1. 删除第4页（已知空白）
2. 逐页拆分为单页 PDF + 灰度 PNG
3. 生成 manifest.json
4. 迁移已有标注到每页独立文件
"""
import sys, os, json, tempfile
from pathlib import Path

_venv = Path("C:/Users/jay/.venv_paddleocr/Lib/site-packages")
if str(_venv) not in sys.path:
    sys.path.insert(0, str(_venv))

import fitz
import numpy as np
from PIL import Image

SRC_TEMPLATE = Path("d:/grsxbd/templates/PDFtemplates.pdf")
OUT_DIR = Path("d:/grsxbd/templates")
PAGES_DIR = OUT_DIR / "pages"
REGIONS_DIR = OUT_DIR / "regions"
ANN_OLD = OUT_DIR / "PDFtemplates_regions.json"

PAGES_DIR.mkdir(exist_ok=True)
REGIONS_DIR.mkdir(exist_ok=True)

DPI = 150


def p(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode())


# ── Step 1: 删除第4页，生成干净模板 ──────────────
p("=" * 50)
p("Step 1: 删除第4页（空白），生成干净模板")
doc = fitz.open(str(SRC_TEMPLATE))
p(f"  原始页数: {len(doc)}")
doc.delete_page(3)  # 0-based，删除原第4页
p(f"  删除后页数: {len(doc)}")
clean_path = PAGES_DIR / "_clean_template.pdf"
doc.save(str(clean_path))
doc.close()
p(f"  干净模板已保存: {clean_path}")


# ── Step 2: 拆分 21 页 ─────────────────────────
p("\n" + "=" * 50)
p("Step 2: 拆分单页 PDF + 灰度 PNG")
doc = fitz.open(str(clean_path))
zoom = DPI / 72
mat = fitz.Matrix(zoom, zoom)

manifest_pages = {}

for i in range(len(doc)):
    page_num = i + 1  # 1-based，新页号

    # 保存单页 PDF
    single = fitz.open()
    single.insert_pdf(doc, from_page=i, to_page=i)
    single.save(str(PAGES_DIR / f"PDFtemplates_{page_num:03d}.pdf"))
    single.close()

    # 保存灰度 PNG（供 SSIM 备用）
    pix = doc[i].get_pixmap(matrix=mat, alpha=False)
    pix.save(str(PAGES_DIR / f"page_{page_num:03d}.png"))

    manifest_pages[str(page_num)] = {
        "pdf": f"PDFtemplates_{page_num:03d}.pdf",
        "image": f"page_{page_num:03d}.png"
    }

doc.close()
p(f"  已拆分 {len(manifest_pages)} 页")


# ── Step 3: 生成 manifest.json ──────────────────
p("\n" + "=" * 50)
p("Step 3: 生成 manifest.json")
manifest = {
    "name": "PDFtemplates",
    "original_pages": 22,
    "effective_pages": 21,
    "blank_pages_removed": [4],
    "page_order": list(range(1, 22)),
    "pages": manifest_pages
}
manifest_path = OUT_DIR / "manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
p(f"  manifest.json 已保存: {manifest_path}")


# ── Step 4: 迁移已有标注 ─────────────────────────
p("\n" + "=" * 50)
p("Step 4: 迁移已有标注到单页文件")
if ANN_OLD.exists():
    with open(ANN_OLD, "r", encoding="utf-8") as f:
        old = json.load(f)

    for pg in old["pages"]:
        page = pg["page"]  # 1-based，原页号（不变）
        fname = REGIONS_DIR / f"PDFtemplates_{page:03d}_regions.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump({
                "template": "PDFtemplates",
                "page": page,
                "dpi": 150,
                "regions": pg["regions"]
            }, f, ensure_ascii=False, indent=2)
        p(f"  迁移: 第{page}页 -> {fname.name}")
else:
    p("  无已有标注，跳过")


# ── 清理临时文件 ───────────────────────────────────
clean_path.unlink()
p(f"\n临时文件已清理: {clean_path.name}")


# ── 汇总 ──────────────────────────────────────────
p("\n" + "=" * 50)
p("拆分完成!")
p(f"  模板页数: 21 (删除原第4页)")
p(f"  PDF 文件: {PAGES_DIR}/PDFtemplates_001.pdf ~ PDFtemplates_021.pdf")
p(f"  PNG 文件: {PAGES_DIR}/page_001.png ~ page_021.png")
p(f"  manifest: {manifest_path}")
p(f"  标注迁移: {len(list(REGIONS_DIR.glob('*_regions.json')))} 个文件")
