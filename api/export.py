"""
导出 API 路由
将 OCR 结果、反馈数据、比對结果导出为 PDF
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import uuid
import json

from services.pdf_export_service import PDFExportService

router = APIRouter()
pdf_service = PDFExportService()


def _check_file_exists(path: Path, name: str = "文件"):
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name}不存在: {path}")


@router.get("/scan-pdf/{task_id}")
async def export_scan_pdf(task_id: str):
    """
    导出 OCR 识别结果为表单式 PDF

    Args:
        task_id: OCR 任务 ID

    Returns:
        PDF 文件
    """
    BASE_DIR = Path(__file__).parent.parent
    ocr_dir = BASE_DIR / "uploads/ocr_results"
    result_file = ocr_dir / f"{task_id}.json"
    _check_file_exists(result_file, "OCR 结果文件")

    output_file = ocr_dir / f"{task_id}_form.pdf"
    try:
        pdf_path = pdf_service.export_scan_result(result_file, output_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"OCR识别结果_{task_id[:8]}.pdf"
    )


@router.get("/feedback-pdf/{file_id}")
async def export_feedback_pdf(file_id: str):
    """
    导出反馈 Excel 数据为表单式 PDF

    Args:
        file_id: Excel 文件 ID（不含扩展名）

    Returns:
        PDF 文件
    """
    BASE_DIR = Path(__file__).parent.parent
    excel_dir = BASE_DIR / "uploads/excel"

    # 查找 Excel 文件（格式：{uuid}_{原名}.xlsx）
    excel_file = None
    for f in excel_dir.glob(f"{file_id}_*"):
        if f.suffix.lower() in (".xlsx", ".xls"):
            excel_file = f
            break

    if not excel_file:
        raise HTTPException(status_code=404, detail="Excel 文件不存在")

    output_file = excel_dir / f"{file_id}_form.pdf"
    try:
        pdf_path = pdf_service.export_feedback(excel_file, output_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"反馈数据_{file_id}.pdf"
    )


@router.get("/compare-pdf/{compare_id}")
async def export_compare_pdf(compare_id: str):
    """
    导出比对结果为表单式 PDF

    Args:
        compare_id: 比对结果 ID

    Returns:
        PDF 文件
    """
    BASE_DIR = Path(__file__).parent.parent
    compare_dir = BASE_DIR / "uploads/compare_results"
    result_file = compare_dir / f"compare_{compare_id}.json"

    # 也支持不带前缀的 ID
    if not result_file.exists():
        result_file = compare_dir / f"{compare_id}.json"

    _check_file_exists(result_file, "比对结果文件")

    output_file = compare_dir / f"{compare_id}_report.pdf"
    try:
        pdf_path = pdf_service.export_compare_result(result_file, output_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"核查比对报告_{compare_id[:8]}.pdf"
    )
