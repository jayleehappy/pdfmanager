@echo off
chcp 65001 >nul 2>&1
title Report Table OCR Service

echo ================================================
echo    OCR Engine + FastAPI Server
echo ================================================
echo.
echo [INFO] OCR Engine mode is set by OCR_ENGINE_MODE env var.
echo [INFO] Current: OCR_ENGINE_MODE=%OCR_ENGINE_MODE%
echo.
echo    Mode options:
echo      (not set)  = PP-OCRv5 ONNX Runtime CPU (default)
echo      docker-gpu = PaddleOCR v3 Docker GPU (high quality)
echo.
echo    Server: http://localhost:8000
echo    UI:     http://localhost:8000/
echo    Annotate: http://localhost:8000/annotate
echo.
echo Press Ctrl+C to stop
echo ================================================
echo.

cd /d "%~dp0"
python server.py --warmup

pause
