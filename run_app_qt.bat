@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title AI Khmer Movie Studio - High Performance Qt Edition (PySide6)
color 0b
echo ========================================================
echo   AI Khmer Movie Studio - High Performance Qt Edition
echo   (Hardware-Accelerated 60fps UI / Smooth Resizing / Zooming)
echo ========================================================
echo.
echo កំពុងបើកកម្មវិធី Qt Edition...
python app_qt.py
pause
