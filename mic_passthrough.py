"""
mic_passthrough.py
マイクのリアルタイム パス送信モジュール。
選択したマイクの音声を出力デバイス（CABLE Input 等）にルーティングします。

技術仕様:
  - サンプルレート : 48000 Hz（Discord / WebRTC 標準）
  - チャンネル     : 1ch（モノラル）
  - ブロックサイズ : 256 サンプル ≒ 5ms 低レイテンシ
  - 内部フォーマット: float32
"""

import threading
from typing import Optional

import numpy as np
import sounddevice as sd

SAMPLERATE = 48000
CHANNELS   = 1
BLOCKSIZE  = 256


# ── デバイス列挙ユーティリティ ────────────────────────────────────────────────

def get_input_device_names() -> list[str]:
    """入力チャンネルを持つデバイス名の一覧を返します。"""
    return [
        d["name"]
        for d in sd.query_devices()
        if d["max_input_channels"] > 0
    ]


def get_output_device_names() -> list[str]:
    """出力チャンネルを持つデバイス名の一覧を返します。"""
    return [
        d["name"]
        for d in sd.query_devices()
        if d["max_output_channels"] > 0
    ]


def find_input_index(name: str) -> Optional[int]:
    """デバイス名（部分一致）から入力デバイスのインデックスを返します。"""
    lower = name.lower()
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and lower in d["name"].lower():
            return i
    return None


def find_output_index(vlc_device_name: str) -> Optional[int]:
    """
    VLC で選択された出力デバイス名（部分一致）から sounddevice の
    出力デバイスインデックスを返します。
    "デフォルト（システム規定）" または空文字の場合は None（既定デバイス）。
    """
    if not vlc_device_name or vlc_device_name == "デフォルト（システム規定）":
        return None
    lower = vlc_device_name.lower()
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0 and lower in d["name"].lower():
            return i
    return None


# ── MicPassthrough クラス ─────────────────────────────────────────────────────

class MicPassthrough:
    """
    マイク入力をリアルタイムで出力デバイスに転送するクラス。
    sounddevice の低レイテンシ Stream を使用します。
    """

    def __init__(self):
        self._stream: Optional[sd.Stream] = None
        self._active = False
        self._volume = 1.0   # 内部ゲイン（0.0 – 2.0）
        self._lock = threading.Lock()

    # ----------------------------------------------------------------
    # public API
    # ----------------------------------------------------------------

    def set_volume(self, volume: int) -> None:
        """
        マイク音量を 0–100 で設定します。
        50 が原音量（等倍ゲイン）、100 で 2倍ゲインになります。
        """
        with self._lock:
            self._volume = max(0.0, min(2.0, volume / 50.0))

    def start(
        self,
        input_device: Optional[int],
        output_device: Optional[int],
    ) -> None:
        """
        マイクパス送信を開始します。
        input_device / output_device は sounddevice デバイスインデックス
        （None = システム既定）。
        """
        self.stop()

        def _callback(indata, outdata, frames, time_info, status):
            with self._lock:
                vol = self._volume
            np.multiply(indata, vol, out=outdata)

        self._stream = sd.Stream(
            device=(input_device, output_device),
            samplerate=SAMPLERATE,
            channels=CHANNELS,
            blocksize=BLOCKSIZE,
            dtype="float32",
            callback=_callback,
            latency="low",
        )
        self._stream.start()
        self._active = True

    def stop(self) -> None:
        """マイクパス送信を停止します。"""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def release(self) -> None:
        self.stop()
