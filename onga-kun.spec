# onga-kun.spec  ─  PyInstaller ビルド定義
# sounddevice + soundfile + numpy + customtkinter 版
# build.bat から自動実行されます。手動実行: pyinstaller onga-kun.spec

import os
from PyInstaller.utils.hooks import collect_data_files

# ── ランタイム DLL を含むデータパッケージを収集 ────────────────────────────

# CustomTkinter: テーマ JSON・画像など（これがないと起動時に KeyError/FileNotFoundError）
datas = collect_data_files("customtkinter")

# sounddevice: PortAudio DLL（libportaudio64bit.dll）
datas += collect_data_files("_sounddevice_data")

# soundfile: libsndfile DLL（libsndfile_x64.dll）
datas += collect_data_files("_soundfile_data")

# 配布用サンプル設定（settings.json 本体は exe 隣に置くので同梱しない）
if os.path.exists("settings.example.json"):
    datas += [("settings.example.json", ".")]

# アイコンファイル
if os.path.exists("assets/icon.ico"):
    datas += [("assets/icon.ico", "assets")]

# ── Analysis ─────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "customtkinter",
        "darkdetect",
        "keyboard",
        "sounddevice",
        "soundfile",
        "_sounddevice",
        "_sounddevice_data",
        "_soundfile",
        "_soundfile_data",
        "numpy",
        "cffi",
        "_cffi_backend",
        "winreg",        # startup.py で使用
        "psutil",        # パフォーマンスモニター
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "matplotlib", "pandas", "scipy",
        "tkinter.test", "unittest",
        "vlc",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="onga-kun",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # コンソールウィンドウを出さない
    icon="assets/icon.ico", # アプリアイコン
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="onga-kun",
)
