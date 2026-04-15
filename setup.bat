@echo off
chcp 65001 > nul
echo.
echo ============================================
echo   PDF2CSV セットアップ
echo ============================================
echo.

REM ── 使用する Python コマンドを探す ──────────────────────────
REM python / py / python3 の順に試し、実際に動くものを PYCMD に設定する。
REM Microsoft Store のダミースタブはバージョン出力が空になるため除外する。

set PYCMD=

REM --- python を試す ---
where python > nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version)" 2^>nul') do (
        if not "%%v"=="" set PYCMD=python
    )
)

REM --- py を試す（Python Launcher）---
if "%PYCMD%"=="" (
    where py > nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=*" %%v in ('py -c "import sys; print(sys.version)" 2^>nul') do (
            if not "%%v"=="" set PYCMD=py
        )
    )
)

REM --- python3 を試す ---
if "%PYCMD%"=="" (
    where python3 > nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=*" %%v in ('python3 -c "import sys; print(sys.version)" 2^>nul') do (
            if not "%%v"=="" set PYCMD=python3
        )
    )
)

REM --- どれも見つからなかった ---
if "%PYCMD%"=="" goto :no_python

REM ── バージョンが 3.10 以上か確認 ───────────────────────────
%PYCMD% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" > nul 2>&1
if %errorlevel% neq 0 goto :old_python

REM ── OK：バージョンを表示してインストーラーを起動 ────────────
for /f "tokens=*" %%v in ('%PYCMD% -c "import sys; print(sys.version.split()[0])"') do set PYVER=%%v
echo [OK] Python %PYVER% を確認しました。セットアップを開始します...
echo.
%PYCMD% installer.py
exit /b 0


REM ════════════════════════════════════════════════════════════
REM エラー処理
REM ════════════════════════════════════════════════════════════

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
echo     ★必ず「Add Python to PATH」にチェックを入れてからインストール★
echo.
echo  4. インストール完了後、この setup.bat をもう一度実行してください
echo.
echo ヒント: インストール直後は一度パソコンを再起動すると確実です。
echo.
start https://www.python.org/downloads/
pause
exit /b 1


:old_python
for /f "tokens=*" %%v in ('%PYCMD% -c "import sys; print(sys.version.split()[0])"') do set PYVER=%%v
echo [エラー] Python %PYVER% は対応バージョン外です。
echo.
echo PDF2CSV には Python 3.10 以上が必要です。
echo 以下のページから最新版をインストールしてください。
echo.
echo     https://www.python.org/downloads/
echo.
echo ヒント: 古いバージョンはアンインストールしなくても
echo         新しいバージョンを追加インストールできます。
echo.
start https://www.python.org/downloads/
pause
exit /b 1
