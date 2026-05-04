@echo off
setlocal enabledelayedexpansion
title Onga-Kun Setup

echo.
echo ============================================
echo        Onga-Kun  Development Setup
echo ============================================
echo.

:: -- Python check --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Please install Python 3.11+ from https://www.python.org/
    pause ^& exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if !PY_MAJOR! LSS 3 (
    echo [ERROR] Python 3.11+ required  (found: !PY_VER!)
    pause ^& exit /b 1
)
if !PY_MINOR! LSS 11 (
    echo [ERROR] Python 3.11+ required  (found: !PY_VER!)
    pause ^& exit /b 1
)
echo [OK] Python !PY_VER!

:: -- VLC check --
set VLC_FOUND=0
if exist "C:\Program Files\VideoLAN\VLC\libvlc.dll"       set VLC_FOUND=1
if exist "C:\Program Files (x86)\VideoLAN\VLC\libvlc.dll" set VLC_FOUND=1

if !VLC_FOUND!==0 (
    echo.
    echo [WARN] VLC not found. Please install from https://www.videolan.org/
    echo        Audio output will not work without VLC.
    echo.
    pause
) else (
    echo [OK] VLC found
)

:: -- VB-Cable notice --
echo.
echo [INFO] If you want to route audio to Discord/games, install VB-Cable:
echo        https://vb-audio.com/Cable/
echo        Then select CABLE Input as the output device in Onga-Kun.
echo.

:: -- Create virtual environment --
if not exist ".venv" (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 ( echo [ERROR] Failed to create venv ^& pause ^& exit /b 1 )
    echo [OK] Virtual environment created
) else (
    echo [1/3] Virtual environment already exists, skipping
)

:: -- Install dependencies --
echo [2/3] Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] pip install failed ^& pause ^& exit /b 1 )
echo [OK] Dependencies installed

:: -- Done --
echo [3/3] Setup complete!
echo.
echo  To launch manually:
echo    .venv\Scripts\activate
echo    python main.py
echo.
set /p LAUNCH=Launch now? [y/N]: 
if /i "!LAUNCH!"=="y" python main.py

endlocal