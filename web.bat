@echo off
chcp 65001 > nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python が見つかりません。インストールしてください。
    pause & exit /b 1
)

pip show uvicorn >nul 2>&1
if errorlevel 1 (
    echo Web UI の依存パッケージをインストールしています...
    pip install "fastapi>=0.111.0" "uvicorn[standard]>=0.29.0" "python-multipart>=0.0.9"
)

echo PDF2CSV Web UI を起動します: http://localhost:8000
timeout /t 2 >nul
start "" http://localhost:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
