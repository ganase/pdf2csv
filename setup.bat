@echo off
cd /d "%~dp0"
echo ============================================
echo  PDF2CSV セットアップ
echo ============================================
echo.

rem ── Python チェック ──────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません。
    echo.
    echo  以下の手順で Python をインストールしてください:
    echo  1. https://www.python.org/downloads/ を開く
    echo  2. Download Python ボタンでインストーラーをダウンロード
    echo  3. インストール時に Add Python to PATH にチェックを入れる
    echo  4. インストール完了後、このファイルを再度ダブルクリック
    echo.
    pause & exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo Python: %PYVER%

rem ── 依存パッケージインストール ────────────────
echo.
echo 依存パッケージをインストールしています...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] パッケージのインストールに失敗しました。
    pause & exit /b 1
)
echo インストール完了。

rem ── .env 生成 ─────────────────────────────────
if not exist .env (
    echo.
    echo Rakuten AI Gateway の API キーを入力してください。
    echo （入力した内容は画面に表示されません）
    echo.
    set /p APIKEY=API キー:
    echo RAKUTEN_AI_GATEWAY_KEY=%APIKEY%> .env
    echo API キーを保存しました。
) else (
    echo .env が既に存在します。API キーの設定はスキップします。
)

rem ── 完了 ──────────────────────────────────────
echo.
echo ============================================
echo  セットアップ完了！
echo  web.bat をダブルクリックして起動してください。
echo ============================================
echo.
pause
