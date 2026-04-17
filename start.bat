@echo off
chcp 65001 >nul
title Report Table OCR Service

echo ================================================
echo    OCR Recognition and Compare Service
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

:: Check venv
if not exist ".venv_paddleocr" (
    echo [WARNING] .venv_paddleocr not found
)

:: Start server
echo [INFO] Starting server...
echo.
echo Local:    http://localhost:8000
echo UI:       http://localhost:8000/static/index.html
echo Annotate: http://localhost:8000/annotate
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo ================================================
echo.

python server.py

pause
