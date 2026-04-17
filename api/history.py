"""
历史记录 API 路由
从数据库检索历史 OCR 任务、反馈文件、比对结果
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

from services.db_service import DBService

router = APIRouter()
db = DBService()

BASE_DIR = Path(__file__).parent.parent


# === 系统摘要 ===
@router.get("/summary")
async def get_summary():
    """获取系统统计摘要"""
    return db.get_summary()


# === OCR 任务历史 ===
@router.get("/tasks")
async def list_tasks(limit: int = 50):
    """列出最近的 OCR 任务"""
    return {"tasks": db.list_scan_tasks(limit=limit)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取单个 OCR 任务详情"""
    task = db.get_scan_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """获取 OCR 任务结果"""
    result = db.get_scan_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="结果不存在")
    return {"task_id": task_id, "result": result}


# === 反馈文件历史 ===
@router.get("/feedback")
async def list_feedback(limit: int = 50):
    """列出已上传的反馈文件"""
    return {"files": db.list_feedback_files(limit=limit)}


@router.get("/feedback/{file_id}")
async def get_feedback(file_id: str):
    """获取反馈文件详情和章节数据"""
    file_info = db.get_feedback_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="反馈文件不存在")

    chapters = db.get_feedback_chapters(file_id)
    return {
        "file": file_info,
        "chapters": chapters,
    }


# === 比对结果历史 ===
@router.get("/compare")
async def list_compare(limit: int = 50):
    """列出历史比对结果"""
    return {"results": db.list_compare_results(limit=limit)}


@router.get("/compare/{compare_id}")
async def get_compare(compare_id: str):
    """获取比对结果详情"""
    result = db.get_compare_result(compare_id)
    if not result:
        # 尝试从文件系统读取
        result_dir = BASE_DIR / "uploads" / "compare_results"
        result_file = result_dir / f"compare_{compare_id}.json"
        if not result_file.exists():
            result_file = result_dir / f"{compare_id}.json"
        if result_file.exists():
            with open(result_file, "r", encoding="utf-8") as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="比对结果不存在")
    return result
