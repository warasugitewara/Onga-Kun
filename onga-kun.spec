# onga-kun.spec  ─  PyInstaller ビルド定義
# build.bat から自動実行されます。手動実行: pyinstaller onga-kun.spec

import glob
import os
import sys

# ── VLC バイナリの収集 ────────────────────────────────────────────────────
# build.bat が ONGA_VLC_DIR 環境変数をセットします。
# 手動実行時はここを直接書き換えてください。
vlc_dir = os.environ.get("ONGA_VLC_DIR", r"C:\Program Files\VideoLAN\VLC")

binaries = []
datas    = []

if os.path.isdir(vlc_dir):
    # libvlc.dll / libvlccore.dll などを直下に配置
    for dll in glob.glob(os.path.join(vlc_dir, "*.dll")):
        binaries.append((dll, "."))
    # plugins フォルダをそのまま同梱（コーデック等）
    plugins = os.path.join(vlc_dir, "plugins")
    if os.path.isdir(plugins):
        datas.append((plugins, "plugins"))
    # locale フォルダ（任意）
    locale = os.path.join(vlc_dir, "locale")
    if os.path.isdir(locale):
        datas.append((locale, "locale"))
else:
    print(f"[spec 警告] VLC ディレクトリが見つかりません: {vlc_dir}")

# ── アプリ本体のデータファイル ─────────────────────────────────────────────
# settings.json は exe 隣に置く（書き込みが発生するため datas に含めない）
# アイコンがあれば追加（icon.ico を用意した場合）
app_datas = []
# app_datas.append(("assets", "assets"))  # ← アイコン画像などを入れる場合

# ── Analysis ─────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas + app_datas,
    hiddenimports=[
        "customtkinter",
        "vlc",
        "keyboard",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "matplotlib", "numpy", "pandas", "scipy",
        "tkinter.test", "unittest",
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
    # icon="assets/icon.ico",  # ← アイコンを用意したら有効化
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
