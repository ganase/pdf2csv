@echo off
chcp 65001 > nul
echo.
echo ============================================
echo   PDF2CSV セットアップ
echo ============================================
echo.

REM ── Python がインストールされているか確認 ──────────────
where python > nul 2>&1
if %errorlevel% neq 0 (
    goto :no_python
)

REM ── Python でバージョンチェックスクリプトを実行 ─────────
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" > nul 2>&1
if %errorlevel% neq 0 (
    goto :old_python
)

REM ── OK：GUIインストーラーを起動 ─────────────────────────
for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version.split()[0])"') do set PYVER=%%v
echo [OK] Python %PYVER% を確認しました。セットアップを開始します...
echo.
python installer.py
exit /b 0


REM ── エラー処理 ──────────────────────────────────────────

:no_python
echo [エラー] Python が見つかりませんでした。
echo.
echo PDF2CSV を使うには Python 3.10 以上が必要です。
echo 以下の手順でインストールしてください。
echo.
echo  1. 次のページを開く:
echo     https://www.python.org/downloads/
echo.
echo  2. 「Download Python」ボタンを押してインストーラーをダウンロード
echo.
echo  3. インストーラーを起動し、
echo     必ず「Add Python to PATH」にチェックを入れてからインストール
echo.
echo  4. インストール完了後、この setup.bat をもう一度実行してください
echo.
start https://www.python.org/downloads/
pause
exit /b 1

:old_python
for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version.split()[0])"') do set PYVER=%%v
echo [エラー] Python %PYVER% は対応バージョン外です。
echo.
echo PDF2CSV には Python 3.10 以上が必要です。
echo 以下のページから最新版をインストールしてください。
echo.
echo     https://www.python.org/downloads/
echo.
start https://www.python.org/downloads/
pause
exit /b 1
