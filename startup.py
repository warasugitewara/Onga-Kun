"""
startup.py  ―  Windows 自動起動（スタートアップ）管理
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run を使用します。
管理者権限は不要です。
"""

import os
import sys
import winreg

_APP_NAME = "OngaKun"
_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_startup_enabled() -> bool:
    """スタートアップに登録されているか確認します。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


def set_startup(enabled: bool) -> None:
    """スタートアップへの登録 / 解除を行います。"""
    if getattr(sys, "frozen", False):
        # PyInstaller EXE として実行中
        target = f'"{sys.executable}"'
    else:
        # 開発時: python main.py を登録
        main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        target = f'"{sys.executable}" "{main_path}"'

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, target)
                print(f"[スタートアップ] 登録: {target}")
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                    print("[スタートアップ] 解除")
                except FileNotFoundError:
                    pass
    except OSError as e:
        print(f"[スタートアップ] レジストリ操作失敗: {e}")
