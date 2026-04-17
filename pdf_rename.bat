@echo off
chcp 65001 > nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo エラー: Python が見つかりません。Python をインストールしてください。
    pause
    exit /b 1
)

python pdf_rename.py
