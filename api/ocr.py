"""
OCR 识别 API 路由
支持模板对比优化：只识别扫描件中与模板不同的区域

模块拆分说明（2026-04-15）:
  - ocr_models.py  : Pydantic 模型定义
  - ocr_utils.py   : 工具函数（字段判断/ORB/文本归一化/评分）
  - ocr_preocr.py  : PreOCR 批量匹配逻辑
  - ocr_engine.py  : process_ocr_task 主任务函数
  - paddle_ocr_engine.py : PaddleOCR-json 引擎封装（C++ 子进程模式）
"""

from pathlib import Path
import uuid
import logging
import threading

from fastapi import APIRouter, HTTPException

from services.pdf_service import PDFService
from services.template_service import TemplateCompareService
from services.db_service import DBService
from api.ocr_models import OCRRequest, OCRResponse, OCRStatusResponse

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# 服务实例（懒加载）
pdf_service = PDFService()
_db_service = None
_template_service = None


def _get_db_service():
        global _db_service
        if _db_service is None:
                _db_service = DBService()
        return _db_service


def _get_template_service():
        global _template_service
        if _template_service is None:
                _base_dir = Path(__file__).parent.parent
                _template_path = _base_dir / "templates" / "PDFtemplates.pdf"
                _template_service = TemplateCompareService(dpi=150, template_path=str(_template_path))
                logger.info(f"[OCR] 模板已加载，共 {len(_template_service.template_pages)} 页")
        return _template_service


# 任务存储（内存 + 数据库双写）
tasks = {}

# 任务日志存储
task_logs: dict[str, list[str]] = {}

# Thread-local 存储当前线程的 task_id
_task_id_local = threading.local()


def get_current_task_id() -> str | None:
        """获取当前线程对应的 task_id"""
        return getattr(_task_id_local, 'task_id', None)


def log_to_task(text: str):
        """将日志写入当前任务"""
        tid = get_current_task_id()
        if tid:
                if tid not in task_logs:
                        task_logs[tid] = []
                task_logs[tid].append(text)


# ── API 路由 ─────────────────────────────────────────────

@router.post("/recognize", response_model=OCRResponse)
async def recognize_pdf(request: OCRRequest):
        """执行 PDF OCR 识别"""
        logger.info(f"[OCR API] 收到识别请求, file_id: {request.file_id}, "
                                                        f"template: {request.template_file_id}, pages: {request.pages}")

        BASE_DIR = Path(__file__).parent.parent
        pdf_dir = BASE_DIR / "uploads" / "pdf"

        pdf_file = None
        for f in pdf_dir.glob(f"{request.file_id}.pdf"):
                pdf_file = f
                break

        if not pdf_file:
                logger.warning(f"[OCR API] PDF 文件不存在: {request.file_id}")
                raise HTTPException(status_code=404, detail="PDF 文件不存在")

        template_file = None
        if request.template_file_id:
                for f in pdf_dir.glob(f"{request.template_file_id}.pdf"):
                                        template_file = f
                                        break
                if not template_file:
                                        raise HTTPException(status_code=404, detail="模板文件不存在")

        task_id = str(uuid.uuid4())
        tasks[task_id] = {
                "status": "pending",
                "progress": 0,
                "result": None,
                "file_id": request.file_id,
                "pdf_file": str(pdf_file),
                "template_file": str(template_file) if template_file else None,
                "pages": request.pages,
        }

        try:
                mode = "template" if template_file else "normal"
                _get_db_service().create_scan_task(request.file_id, mode, task_id)
        except Exception as db_err:
                logger.warning(f"[OCR API] DB 创建任务失败: {db_err}")

        def _thread_wrapper():
                """包装器：捕获 process_ocr_task 的所有异常并记录"""
                _task_id_local.task_id = task_id
                # 添加日志捕获 handler
                _handler = logging.Handler()
                _handler.setFormatter(logging.Formatter('%(levelname)s] %(message)s'))
                def _emit(record):
                        msg = _handler.format(record)
                        tid = get_current_task_id()
                        if tid:
                                if tid not in task_logs:
                                        task_logs[tid] = []
                                task_logs[tid].append(msg)
                _handler.emit = _emit  # noqa
                logging.getLogger().addHandler(_handler)
                try:
                        from api.ocr_engine import process_ocr_task
                        print(f"[THREAD] 即将调用 process_ocr_task...")
                        process_ocr_task(task_id, str(pdf_file), request.pages,
                                          str(template_file) if template_file else None,
                                          tasks=tasks)
                        print(f"[THREAD] process_ocr_task 正常返回")
                except Exception:
                        logger.exception(f"[OCR Task {task_id}] 线程异常:")

        thread = threading.Thread(target=_thread_wrapper)
        thread.daemon = True
        thread.start()

        return {"task_id": task_id, "status": "pending", "message": "OCR 识别任务已创建"}


@router.get("/status/{task_id}", response_model=OCRStatusResponse)
async def get_status(task_id: str):
        """查询 OCR 任务状态"""
        if task_id not in tasks:
                raise HTTPException(status_code=404, detail="任务不存在")
        task = tasks[task_id]
        response = {"task_id": task_id, "status": task["status"], "progress": task["progress"]}
        if task["status"] == "completed":
                response["result_file"] = task.get("result_file")
        elif task["status"] == "failed":
                response["error"] = task.get("error")
        return response


@router.get("/result/{task_id}")
async def get_result(task_id: str):
        """获取 OCR 识别结果"""
        if task_id not in tasks:
                raise HTTPException(status_code=404, detail="任务不存在")
        task = tasks[task_id]
        if task["status"] != "completed":
                return {"status": task["status"], "progress": task["progress"]}
        return {"status": "completed", "result": task.get("result"), "result_file": task.get("result_file")}


@router.get("/logs/{task_id}")
async def get_task_logs(task_id: str, limit: int = 200):
        """获取 OCR 任务日志"""
        if task_id not in tasks:
                raise HTTPException(status_code=404, detail="任务不存在")
        logs = task_logs.get(task_id, [])
        return {"logs": logs[-limit:] if limit > 0 else logs}
