"""
updater.py  ―  GitHub Releases を使った自動アップデートチェッカー
urllib（標準ライブラリ）のみで動作します。requests は不要です。
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Optional

from version import GITHUB_REPO, VERSION


def _parse_ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def check_latest() -> Optional[tuple[str, str]]:
    """
    GitHub Releases API で最新バージョンを確認します。
    アップデートがある場合は (latest_tag, installer_download_url) を返します。
    なければ None を返します。
    ネットワークエラーなど例外は握り潰して None を返します（起動を妨げないため）。
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": f"onga-kun/{VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data: dict = json.loads(resp.read())

        latest_tag: str = data.get("tag_name", "")
        if not latest_tag:
            return None

        if _parse_ver(latest_tag) <= _parse_ver(VERSION):
            return None

        # .exe アセット（インストーラ）を探す
        for asset in data.get("assets", []):
            if asset["name"].lower().endswith(".exe"):
                return latest_tag, asset["browser_download_url"]

    except Exception:
        pass

    return None


def download_and_launch(
    download_url: str,
    on_progress: Optional[callable] = None,
) -> None:
    """
    インストーラを一時ディレクトリにダウンロードして起動します。
    起動後、現在のプロセスを終了します（インストーラが上書きするため）。
    on_progress(pct: int) が指定されていれば 0-100 の進捗を渡します。
    """
    tmp_path = os.path.join(tempfile.gettempdir(), "onga-kun-setup.exe")

    def _hook(count: int, block_size: int, total: int):
        if on_progress and total > 0:
            pct = min(100, int(count * block_size * 100 / total))
            on_progress(pct)

    urllib.request.urlretrieve(download_url, tmp_path, reporthook=_hook)
    subprocess.Popen([tmp_path])
    sys.exit(0)
