@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   PDF2CSV Setup
echo ============================================
echo.

set PYCMD=

python -c "import sys; print(sys.version)" > nul 2>&1
if !errorlevel! equ 0 ( set PYCMD=python & goto check_version )

py -c "import sys; print(sys.version)" > nul 2>&1
if !errorlevel! equ 0 ( set PYCMD=py & goto check_version )

python3 -c "import sys; print(sys.version)" > nul 2>&1
if !errorlevel! equ 0 ( set PYCMD=python3 & goto check_version )

goto no_python

:check_version
!PYCMD! -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" > nul 2>&1
if !errorlevel! neq 0 goto old_python

echo Python found. Starting installer...
echo.
!PYCMD! installer.py
exit /b 0

:no_python
echo.
echo [ERROR] Python was not found on this computer.
echo.
echo PDF2CSV requires Python 3.10 or later.
echo.
echo  1. Open: https://www.python.org/downloads/
echo  2. Click [Download Python] and run the installer
echo  3. IMPORTANT: Check [Add Python to PATH] before installing
echo  4. After install, restart your PC and run setup.bat again
echo.
start https://www.python.org/downloads/
pause
exit /b 1

:old_python
echo.
echo [ERROR] The installed Python version is too old.
echo.
echo PDF2CSV requires Python 3.10 or later.
echo Please install the latest version:
echo     https://www.python.org/downloads/
echo.
start https://www.python.org/downloads/
pause
exit /b 1
