@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title 音ガくん セットアップ

echo.
echo ╔══════════════════════════════════════════╗
echo ║       音ガくん  開発環境セットアップ          ║
echo ╚══════════════════════════════════════════╝
echo.

:: ── Python チェック ────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [エラー] Python が見つかりません。
    echo         https://www.python.org/ から 3.11 以上をインストールしてください。
    pause & exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if !PY_MAJOR! LSS 3 (
    echo [エラー] Python 3.11 以上が必要です（現在: !PY_VER!）
    pause & exit /b 1
)
if !PY_MINOR! LSS 11 (
    echo [エラー] Python 3.11 以上が必要です（現在: !PY_VER!）
    pause & exit /b 1
)
echo [OK] Python !PY_VER! を確認しました

:: ── VLC チェック ─────────────────────────────────────────────────────────
set VLC_FOUND=0
if exist "C:\Program Files\VideoLAN\VLC\libvlc.dll"   set VLC_FOUND=1
if exist "C:\Program Files (x86)\VideoLAN\VLC\libvlc.dll" set VLC_FOUND=1

if !VLC_FOUND!==0 (
    echo.
    echo [警告] VLC が見つかりません。
    echo         https://www.videolan.org/ から VLC をインストールしてください。
    echo         ※ VLC がないと音声出力が動作しません。
    echo.
    pause
) else (
    echo [OK] VLC を確認しました
)

:: ── VB-Cable の案内 ───────────────────────────────────────────────────────
echo.
echo [情報] VB-Cable が必要な場合は以下からインストールしてください：
echo        https://vb-audio.com/Cable/
echo        インストール後、音ガくん内で出力先デバイスとして選択してください。
echo.

:: ── 仮想環境の作成 ────────────────────────────────────────────────────────
if not exist ".venv" (
    echo [1/3] 仮想環境を作成中...
    python -m venv .venv
    if errorlevel 1 ( echo [エラー] 仮想環境の作成に失敗しました & pause & exit /b 1 )
    echo [OK] 仮想環境を作成しました
) else (
    echo [1/3] 仮想環境は既に存在します（スキップ）
)

:: ── 依存パッケージのインストール ─────────────────────────────────────────
echo [2/3] 依存パッケージをインストール中...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 ( echo [エラー] パッケージインストールに失敗しました & pause & exit /b 1 )
echo [OK] パッケージインストール完了

:: ── 起動確認 ─────────────────────────────────────────────────────────────
echo [3/3] セットアップ完了！
echo.
echo  起動するには:
echo    .venv\Scripts\activate
echo    python main.py
echo.
set /p LAUNCH=今すぐ起動しますか？ [y/N]: 
if /i "!LAUNCH!"=="y" python main.py

endlocal
