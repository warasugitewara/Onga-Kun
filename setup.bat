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

:: -- ffmpeg check / install --
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo [INFO] ffmpeg not found. Required for MP4/M4A audio files.
    set /p INST_FF=Install ffmpeg via winget? [y/N]: 
    if /i "!INST_FF!"=="y" (
        winget install --id Gyan.FFmpeg -e --silent
        if errorlevel 1 (
            echo [WARN] winget install failed. Install manually: https://ffmpeg.org/download.html
        ) else (
            echo [OK] ffmpeg installed
        )
    ) else (
        echo [SKIP] ffmpeg skipped. MP4/M4A files will not play.
    )
) else (
    echo [OK] ffmpeg found
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