"""
报告表 OCR 识别与比对服务
主入口文件

使用 FastAPI 构建 RESTful API
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

# ── 添加 venv site-packages 路径 ─────────────────────────
_venv_sp = Path(__file__).parent / ".venv_paddleocr" / "Lib" / "site-packages"
if _venv_sp.exists() and str(_venv_sp) not in sys.path:
    sys.path.insert(0, str(_venv_sp))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import os
from pathlib import Path

# 导入 API 路由
from api import upload, ocr, compare, report, export, history, annotate

# 项目根目录
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
TEMP_DIR = BASE_DIR / "temp"

# 确保目录存在
UPLOAD_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# ── Lifespan：管理 OCR 引擎生命周期 ──────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
        """在 uvicorn 子进程中管理 OCR 引擎"""
        print("=" * 60)
        print("[INFO] 报告表 OCR 识别与比对服务启动中...")
        print("[INFO] OCR 引擎: PP-OCRv5 ONNX Runtime + 多进程池")
        print("=" * 60)
        print(f"[DIR] 上传目录: {UPLOAD_DIR}")
        print(f"[DIR] 临时目录: {TEMP_DIR}")
        print("=" * 60)

        # warmup 模式：预热 OCR 引擎
        if "--warmup" in sys.argv:
                import os as _os
                ocr_mode = _os.environ.get("OCR_ENGINE_MODE", "fast")
                print(f"[INFO] 预热模式：启动 OCR 引擎（mode={ocr_mode}）...")
                from lib.ocr_engines import get_ocr_engine
                engine = get_ocr_engine(mode=ocr_mode)
                print("[INFO] OCR 引擎预热完成，服务已就绪！")

        yield  # 应用运行中

        # 应用关闭时：关闭引擎
        import os as _os
        ocr_mode = _os.environ.get("OCR_ENGINE_MODE", "fast")
        print(f"[INFO] 正在关闭 OCR 引擎（mode={ocr_mode}）...")
        from lib.ocr_engines import reset_ocr_engine
        reset_ocr_engine(mode=ocr_mode)


# 创建 FastAPI 应用
app = FastAPI(
    title="报告表 OCR 识别与比对系统",
    description="领导干部个人有关事项报告表 OCR 识别与查核反馈比对服务",
    version="2.0.0",
    lifespan=lifespan,
)

# 配置静态文件服务
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# 模板文件（templates目录）作为静态资源
app.mount("/templates", StaticFiles(directory=str(BASE_DIR / "templates"), html=False), name="templates")

# 配置 CORS，允许局域网访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境可限制为具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(upload.router, prefix="/api/upload", tags=["文件上传"])
app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR识别"])
app.include_router(compare.router, prefix="/api/compare", tags=["比对分析"])
app.include_router(report.router, prefix="/api/report", tags=["报告生成"])
app.include_router(export.router, prefix="/api/export", tags=["导出"])
app.include_router(history.router, prefix="/api/history", tags=["历史记录"])
app.include_router(annotate.router, prefix="/api/annotate", tags=["区域标注"])


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    html_path = BASE_DIR / "templates" / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <html>
        <head><title>报告表比对系统</title></head>
        <body>
            <h1>报告表 OCR 识别与比对系统</h1>
            <p>请访问 <a href="/static/index.html">/static/index.html</a> 使用前端界面</p>
            <p><a href="/annotate">打开区域标注工具</a></p>
        </body>
    </html>
    """


@app.get("/annotate", response_class=HTMLResponse)
async def annotate_page():
    """区域标注工具页面"""
    html_path = BASE_DIR / "templates" / "annotate.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="标注工具页面不存在")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "报告表比对系统",
        "version": "2.0.0",
        "ocr_engine": "PP-OCRv5-ONNX"
    }


def main():
    """启动服务"""
    import argparse

    parser = argparse.ArgumentParser(description="报告表 OCR 服务")
    parser.add_argument("--warmup", action="store_true",
                        help="启动前先预热 PP-OCRv5 ONNX Worker 池（加载模型到内存）")
    args = parser.parse_args(sys.argv[1:])

    print("\n" + "=" * 60)
    print("[INFO] 报告表 OCR 识别与比对服务 v2.0")
    print("[INFO] OCR 引擎: PP-OCRv5 ONNX Runtime + 多进程池")
    print("=" * 60)

    if args.warmup:
        print("[INFO] 预热模式：将在 uvicorn 子进程中启动 ONNX Worker 池...")

    print("本地访问: http://localhost:8000")
    print("前端界面: http://localhost:8000/static/index.html")
    print("API 文档: http://localhost:8000/docs")
    print("标注工具: http://localhost:8000/annotate")
    print("=" * 60 + "\n")

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
