@echo off
chcp 65001 >nul 2>&1
title Report Table OCR Service

echo ================================================
echo    FastAPI Server (without Paddle warmup)
echo ================================================
echo.
echo [INFO] Starting server...
echo.
echo Local:    http://localhost:8000
echo UI:       http://localhost:8000/static/index.html
echo Annotate: http://localhost:8000/annotate
echo API Docs: http://localhost:8000/docs
echo.
echo NOTE: If PaddleOCR hasn't been warmed up yet,
echo       the first OCR request will take ~40s to load.
echo       Run start_paddle.bat first for faster first load.
echo.
echo Press Ctrl+C to stop
echo ================================================
echo.

python server.py

pause
