@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title 音ガくん ビルド

echo.
echo ╔══════════════════════════════════════════╗
echo ║         音ガくん  リリースビルド              ║
echo ╚══════════════════════════════════════════╝
echo.

:: ── 仮想環境チェック ──────────────────────────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo [エラー] .venv が見つかりません。先に setup.bat を実行してください。
    pause & exit /b 1
)
call .venv\Scripts\activate.bat

:: ── PyInstaller インストール ──────────────────────────────────────────────
echo [1/4] PyInstaller を確認中...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo         PyInstaller をインストールします...
    pip install pyinstaller --quiet
)
echo [OK] PyInstaller 準備完了

:: ── VLC パスの特定 ────────────────────────────────────────────────────────
echo [2/4] VLC を確認中...
set VLC_DIR=
if exist "C:\Program Files\VideoLAN\VLC\libvlc.dll" (
    set VLC_DIR=C:\Program Files\VideoLAN\VLC
)
if "!VLC_DIR!"=="" (
    if exist "C:\Program Files (x86)\VideoLAN\VLC\libvlc.dll" (
        set VLC_DIR=C:\Program Files (x86)\VideoLAN\VLC
    )
)
if "!VLC_DIR!"=="" (
    echo [エラー] VLC が見つかりません。VLC をインストールしてから再実行してください。
    pause & exit /b 1
)
echo [OK] VLC: !VLC_DIR!

:: VLC パスを spec ファイルが参照できるよう環境変数にセット
set ONGA_VLC_DIR=!VLC_DIR!

:: ── PyInstaller ビルド ────────────────────────────────────────────────────
echo [3/4] ビルド中...（数分かかる場合があります）
if exist "dist\onga-kun" rmdir /s /q "dist\onga-kun"
pyinstaller onga-kun.spec
if errorlevel 1 (
    echo [エラー] ビルドに失敗しました。上記のエラーを確認してください。
    pause & exit /b 1
)
echo [OK] ビルド完了 → dist\onga-kun\

:: ── Inno Setup（インストーラ作成）─────────────────────────────────────────
echo [4/4] インストーラを作成中...
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

if "!ISCC!"=="" (
    echo [スキップ] Inno Setup が見つかりません。
    echo            https://jrsoftware.org/isinfo.php からインストール後、再度 build.bat を実行すると
    echo            installer\Output\onga-kun-setup.exe が生成されます。
) else (
    "!ISCC!" installer\setup.iss
    if errorlevel 1 (
        echo [エラー] インストーラ作成に失敗しました。
    ) else (
        echo [OK] インストーラ → installer\Output\onga-kun-setup.exe
    )
)

echo.
echo ════════════ ビルド完了 ════════════
echo  実行ファイル: dist\onga-kun\onga-kun.exe
if not "!ISCC!"=="" echo  インストーラ: installer\Output\onga-kun-setup.exe
echo.
pause
endlocal
