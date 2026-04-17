@echo off
chcp 65001 > nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo 
    pause
    exit /b 1
)

python process.py
pause
