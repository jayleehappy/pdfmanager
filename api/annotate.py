"""
区域标注工具 API（重构版）

支持：
- 多模板目录切换
- 单页标注文件独立存储
- 标注自动加载和叠加预览
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import fitz, json, base64, os, tempfile

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent


def _get_template_base(name: str) -> Path:
    """获取模板目录路径"""
    base = BASE_DIR / "templates"
    if not base.exists():
        raise HTTPException(status_code=404, detail="templates 目录不存在")
    return base


def _render_page(tmpl_base: Path, page_num: int, dpi: int = 150):
    """
    渲染指定模板的某页为 PNG，返回 (bytes, width, height)
    page_num: 1-based
    """
    # 从 manifest 找到对应的 PDF 文件
    manifest_path = tmpl_base / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="manifest.json 不存在")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    pages = manifest.get("pages", {})
    if str(page_num) not in pages:
        raise HTTPException(status_code=400, detail=f"页码 {page_num} 不存在")

    pdf_file = tmpl_base / "pages" / pages[str(page_num)]["pdf"]
    img_file = tmpl_base / "pages" / pages[str(page_num)]["image"]

    # 如果灰度 PNG 已存在，直接使用（快速路径）
    if img_file.exists():
        w = int(1241 * dpi / 150)  # 近似：模板按 150DPI 渲染
        h = int(1754 * dpi / 150)
        # 读取实际尺寸
        from PIL import Image
        pil_img = Image.open(img_file)
        w, h = pil_img.size
        if dpi != 150:
            # 需要重新渲染
            pass
        else:
            with open(img_file, "rb") as f:
                img_bytes = f.read()
            return img_bytes, w, h

    # 渲染 PDF
    doc = fitz.open(str(pdf_file))
    page = doc[0]
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    fd, tmp = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    pix.save(tmp)
    with open(tmp, 'rb') as f:
        img_bytes = f.read()
    os.unlink(tmp)
    w, h = pix.width, pix.height
    doc.close()
    return img_bytes, w, h


def _get_regions_file(tmpl_base: Path, page_num: int) -> Path:
    """获取某页标注文件路径"""
    manifest_path = tmpl_base / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    # 推断标注文件名
    return tmpl_base / "regions" / f"{manifest['name']}_{page_num:03d}_regions.json"


# ── API 路由 ─────────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    """返回可用模板列表（目前只有 PDFtemplates）"""
    tmpl_base = _get_template_base("PDFtemplates")
    manifest_path = tmpl_base / "manifest.json"
    if not manifest_path.exists():
        return {"templates": [], "message": "无 manifest.json"}

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    # 统计已标注页数
    regions_dir = tmpl_base / "regions"
    annotated = 0
    if regions_dir.exists():
        annotated = len(list(regions_dir.glob("*_regions.json")))

    return {
        "templates": [{
            "name": manifest["name"],
            "effective_pages": manifest["effective_pages"],
            "annotated_pages": annotated,
        }]
    }


@router.get("/template/{name}/manifest")
async def get_manifest(name: str):
    """返回指定模板的 manifest"""
    tmpl_base = _get_template_base(name)
    manifest_path = tmpl_base / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="manifest.json 不存在")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    # 标注状态
    regions_dir = tmpl_base / "regions"
    annotated = {}
    if regions_dir.exists():
        for rf in regions_dir.glob(f"{name}_*_regions.json"):
            pg = int(rf.stem.split('_')[-2])
            annotated[str(pg)] = True

    # 合并标注状态到 pages
    for pg_num, pg_info in manifest.get("pages", {}).items():
        pg_info["annotated"] = pg_num in annotated

    return manifest


@router.get("/template/{name}/page/{page_num}")
async def get_page_image(name: str, page_num: int, dpi: int = 150):
    """获取某页渲染图像（Base64 PNG）"""
    tmpl_base = _get_template_base(name)
    try:
        img_bytes, width, height = _render_page(tmpl_base, page_num, dpi)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "page": page_num,
        "dpi": dpi,
        "width": width,
        "height": height,
        "image": base64.b64encode(img_bytes).decode("ascii"),
    }


@router.get("/template/{name}/page/{page_num}/regions")
async def get_page_regions(name: str, page_num: int):
    """获取某页标注区域"""
    tmpl_base = _get_template_base(name)
    manifest_path = tmpl_base / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    if str(page_num) not in manifest.get("pages", {}):
        raise HTTPException(status_code=400, detail=f"页码 {page_num} 不存在")

    rf = _get_regions_file(tmpl_base, page_num)
    if rf.exists():
        with open(rf, encoding="utf-8") as f:
            data = json.load(f)
        return {"page": page_num, "regions": data.get("regions", [])}

    return {"page": page_num, "regions": []}


class RegionRect(BaseModel):
    index: int
    label: str
    x1: int
    y1: int
    x2: int
    y2: int
    page: int | None = None


class PageAnnotationPayload(BaseModel):
    page: int
    regions: list[RegionRect]


@router.post("/template/{name}/page/{page_num}/regions")
async def save_page_regions(name: str, page_num: int, payload: PageAnnotationPayload):
    """保存某页标注（全量覆盖）"""
    tmpl_base = _get_template_base(name)
    manifest_path = tmpl_base / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    if str(page_num) not in manifest.get("pages", {}):
        raise HTTPException(status_code=400, detail=f"页码 {page_num} 不存在")

    # 确保 regions 目录存在
    regions_dir = tmpl_base / "regions"
    regions_dir.mkdir(exist_ok=True)

    # 获取模板名（从 manifest）
    tmpl_name = manifest["name"]

    # 保存单页标注文件
    rf = regions_dir / f"{tmpl_name}_{page_num:03d}_regions.json"
    regions_data = [{
        "index": r.index,
        "label": r.label,
        "x1": r.x1,
        "y1": r.y1,
        "x2": r.x2,
        "y2": r.y2,
        "page": page_num,
    } for r in payload.regions]

    with open(rf, "w", encoding="utf-8") as f:
        json.dump({
            "template": tmpl_name,
            "page": page_num,
            "dpi": 150,
            "regions": regions_data
        }, f, ensure_ascii=False, indent=2)

    return {"saved": True, "file": str(rf), "regions_count": len(regions_data)}


@router.delete("/template/{name}/page/{page_num}/region/{region_index}")
async def delete_region(name: str, page_num: int, region_index: int):
    """删除某页的指定区域"""
    tmpl_base = _get_template_base(name)
    rf = _get_regions_file(tmpl_base, page_num)
    if not rf.exists():
        return {"deleted": True, "message": "标注文件不存在"}

    with open(rf, encoding="utf-8") as f:
        data = json.load(f)

    data["regions"] = [r for r in data.get("regions", [])
                       if r.get("index") != region_index]
    # 重新编号
    for i, r in enumerate(data["regions"]):
        r["index"] = i + 1

    with open(rf, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {"deleted": True}


@router.delete("/template/{name}/page/{page_num}")
async def clear_page_regions(name: str, page_num: int):
    """清除某页所有标注"""
    tmpl_base = _get_template_base(name)
    rf = _get_regions_file(tmpl_base, page_num)
    if rf.exists():
        rf.unlink()
    return {"cleared": True}


@router.get("/export")
async def export_all():
    """导出所有标注（全量 JSON）"""
    tmpl_base = _get_template_base("PDFtemplates")
    manifest_path = tmpl_base / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    all_pages = []
    regions_dir = tmpl_base / "regions"
    for pg_num_str in manifest["pages"]:
        pg_num = int(pg_num_str)
        rf = regions_dir / f"{manifest['name']}_{pg_num:03d}_regions.json"
        regions = []
        if rf.exists():
            with open(rf, encoding="utf-8") as f:
                data = json.load(f)
                regions = data.get("regions", [])
        all_pages.append({"page": pg_num, "regions": regions})

    return {
        "template": manifest["name"],
        "effective_pages": manifest["effective_pages"],
        "pages": all_pages,
    }
