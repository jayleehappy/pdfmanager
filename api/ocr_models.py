"""
OCR API 数据模型定义
"""

from typing import Optional
from pydantic import BaseModel


class OCRRequest(BaseModel):
        """OCR 识别请求"""
        file_id: str
        template_file_id: Optional[str] = None
        pages: Optional[list[int]] = None


class OCRResponse(BaseModel):
        """OCR 识别响应"""
        task_id: str
        status: str
        message: str = ""
        progress: int = 0


class OCRStatusResponse(BaseModel):
        """OCR 状态查询响应"""
        task_id: str
        status: str
        progress: int
        result_file: Optional[str] = None
        error: Optional[str] = None
