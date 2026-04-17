"""
PaddleOCR Warmup Script
将模型文件预加载到 OS 文件缓存，避免首次请求延迟
"""
import sys, os
from pathlib import Path

_venv = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
if str(_venv) not in sys.path:
    sys.path.insert(0, str(_venv))

sys.path.insert(0, "d:/grsxbd")

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["OMP_NUM_THREADS"] = "1"

print("[INFO] Initializing PaddleOCR engine...")
from services.ocr_service import OCRService

ocr = OCRService()
print("[OK] PaddleOCR warmup complete!")
print("[OK] OS file cache is now warm.")
print("[OK] You can now start the server with start_server.bat")
