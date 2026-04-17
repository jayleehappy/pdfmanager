@echo off
chcp 65001 >nul 2>&1
title Report Table OCR Service (GPU Mode)

echo ================================================
echo    PaddleOCR Docker GPU Mode + FastAPI Server
echo ================================================
echo.
echo [INFO] Using docker-gpu OCR engine (PaddleOCR v3 GPU)
echo [INFO] Requires paddle container running with GPU
echo.
echo    Server: http://localhost:8000
echo    UI:     http://localhost:8000/
echo    Annotate: http://localhost:8000/annotate
echo.
echo Press Ctrl+C to stop
echo ================================================
echo.

cd /d "%~dp0"
set OCR_ENGINE_MODE=docker-gpu
python server.py --warmup

pause
