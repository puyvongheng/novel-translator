@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title AI Khmer Movie Translator & CC Tool
color 0b
echo ========================================================
echo   AI Khmer Movie Translator ^& Modern CC Generator
echo   ឧបករណ៍បកប្រែរឿង (ចិន/បរទេស) ជាភាសាខ្មែរ + CC
echo ========================================================
echo.
echo កំពុងបើកកម្មវិធី...
python app.py
pause
