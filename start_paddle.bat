@echo off
chcp 65001 >nul 2>&1
title PaddleOCR Warmup

echo ================================================
echo    PaddleOCR Warmup (OS File Cache)
echo ================================================
echo.
echo [INFO] Loading PaddleOCR model into OS file cache...
echo [INFO] This takes ~30-50s on first run.
echo.

py "%~dp0scripts\paddle_warmup.py"

echo.
echo Press any key to close this window...
pause >nul
