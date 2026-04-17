"""
比对分析 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json

from services.excel_service import ExcelService
from services.db_service import DBService

router = APIRouter()
excel_service = ExcelService()
db_service = DBService()


class CompareRequest(BaseModel):
    report_result_file: str  # OCR 结果文件路径
    feedback_file_id: str     # 反馈 Excel 文件 ID
    edited_result: list | None = None  # 用户编辑后的结果（优先使用）


@router.post("")
async def compare_report(request: CompareRequest):
    """
    执行比对分析

    Args:
        report_result_file: 报告表 OCR 结果文件路径
        feedback_file_id: 反馈 Excel 文件 ID

    Returns:
        比对结果
    """
    from services.compare_service import CompareService

    # 直接读取 OCR 结果文件（优先使用用户编辑后的结果）
    task_result = request.edited_result
    if task_result is None:
        ocr_result_file = Path(request.report_result_file)
        if not ocr_result_file.exists():
            raise HTTPException(status_code=404, detail="报告表 OCR 结果文件不存在")
        with open(ocr_result_file, "r", encoding="utf-8") as f:
            task_result = json.load(f)

    # 查找反馈 Excel 文件
    BASE_DIR = Path(__file__).parent.parent
    excel_dir = BASE_DIR / "uploads" / "excel"
    excel_file = None

    for f in excel_dir.glob(f"{request.feedback_file_id}_*.xlsx"):
        excel_file = f
        break

    if not excel_file:
        raise HTTPException(status_code=404, detail="反馈 Excel 文件不存在")

    # 读取反馈数据
    feedback_data = excel_service.get_all_feedback_data(excel_file)

    # 提取报告表数据
    report_data = extract_report_data(task_result)

    # 执行比对
    compare_service = CompareService()
    result = compare_service.compare(report_data, feedback_data)

    # 保存结果
    result_dir = BASE_DIR / "uploads" / "compare_results"
    result_file = compare_service.save_result(result, result_dir)
    result["result_file"] = str(result_file)

    # 存入数据库
    try:
        db_service.save_compare_result(
            compare_id=result.get("compare_id", ""),
            task_id=request.report_result_file,
            feedback_file_id=request.feedback_file_id,
            stats=result.get("summary", {}).get("statistics", {}),
            diff_items=result.get("diff_items", [])
        )
    except Exception as db_err:
        import logging
        logging.warning(f"[Compare API] DB 保存失败: {db_err}")

    return result


def extract_report_data(ocr_result: list) -> dict:
    """
    从 OCR 结果中提取报告表数据

    Args:
        ocr_result: OCR 识别结果列表

    Returns:
        报告表数据字典
    """
    # 这是一个简化版的提取逻辑
    # 实际需要根据报告表的版面结构进行更精细的提取

    report_data = {}

    for page_result in ocr_result:
        if not page_result:
            continue

        result_data = page_result.get("result", {})
        if not result_data:
            continue

        # 提取文本
        texts = result_data.get("texts", [])
        tables = result_data.get("tables", [])

        # 根据内容类型分类（简化版）
        for text_item in texts:
            content = text_item.get("content", "")

            # 房产相关
            if "房产" in content or "住宅" in content:
                if "境内房产" not in report_data:
                    report_data["境内房产"] = {"properties": []}
                # 后续需要更精细的提取逻辑

            # 护照相关
            if "护照" in content:
                if "本人护照" not in report_data:
                    report_data["本人护照"] = {"passports": []}

            # 基金相关
            if "基金" in content:
                if "境内基金" not in report_data:
                    report_data["境内基金"] = {"funds": []}

            # 保险相关
            if "保险" in content:
                if "境内投资型保险" not in report_data:
                    report_data["境内投资型保险"] = {"insurance": []}

            # 企业相关
            if "投资" in content and "企业" in content:
                if "投资企业" not in report_data:
                    report_data["投资企业"] = {"companies": []}

    return report_data


@router.get("/result/{compare_id}")
async def get_compare_result(compare_id: str):
    """
    获取比对结果
    """
    BASE_DIR = Path(__file__).parent.parent
    result_dir = BASE_DIR / "uploads" / "compare_results"

    result_file = result_dir / f"compare_{compare_id}.json"

    if not result_file.exists():
        raise HTTPException(status_code=404, detail="比对结果不存在")

    with open(result_file, "r", encoding="utf-8") as f:
        result = json.load(f)

    return result
