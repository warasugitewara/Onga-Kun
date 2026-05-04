"""
mic_passthrough.py
マイクのリアルタイム パス送信モジュール。

WASAPI デバイスのみを使用することで HostAPI 不一致エラー
(PaErrorCode -9993 paBadIODeviceCombination) を回避します。

技術仕様:
  - サンプルレート : 48000 Hz（Discord / WebRTC 標準）
  - チャンネル     : 1ch（モノラル）
  - ブロックサイズ : 512 サンプル ≒ 10ms
  - 内部フォーマット: float32
  - HostAPI       : WASAPI に統一（MME / DirectSound は除外）
"""

import threading
from typing import Optional

import numpy as np
import sounddevice as sd

SAMPLERATE = 48000
CHANNELS   = 1
BLOCKSIZE  = 512   # 256 は一部デバイスで不安定なため 512 を使用


# ── HostAPI ユーティリティ ─────────────────────────────────────────────────────

def _wasapi_idx() -> Optional[int]:
    """WASAPI HostAPI のインデックスを返す。なければ None。"""
    for i, api in enumerate(sd.query_hostapis()):
        if "WASAPI" in api["name"]:
            return i
    return None


def _wasapi_default_output() -> Optional[int]:
    """WASAPI のデフォルト出力デバイスインデックスを返す。"""
    wi = _wasapi_idx()
    if wi is None:
        return None
    api = sd.query_hostapis(wi)
    dod = api.get("default_output_device", -1)
    return dod if dod >= 0 else None


def _find_wasapi(name: str, is_input: bool) -> Optional[int]:
    """
    WASAPI デバイスの中から name（部分一致）で検索し、
    最初に見つかったインデックスを返す。
    """
    wi = _wasapi_idx()
    if wi is None:
        return None
    ch_key = "max_input_channels" if is_input else "max_output_channels"
    lower  = name.lower()
    for i, d in enumerate(sd.query_devices()):
        if d["hostapi"] == wi and d[ch_key] > 0 and lower in d["name"].lower():
            return i
    return None


# ── デバイス列挙（UI 向け） ────────────────────────────────────────────────────

def get_input_device_names() -> list[str]:
    """
    WASAPI 入力デバイス名の一覧（重複なし）を返します。
    WASAPI デバイスが存在しない場合は全デバイスを返します（フォールバック）。
    """
    wi = _wasapi_idx()
    seen, result = set(), []
    for d in sd.query_devices():
        if wi is not None and d["hostapi"] != wi:
            continue
        if d["max_input_channels"] > 0 and d["name"] not in seen:
            seen.add(d["name"])
            result.append(d["name"])
    if not result:
        # フォールバック：全HostAPI から取得
        seen2, result2 = set(), []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0 and d["name"] not in seen2:
                seen2.add(d["name"])
                result2.append(d["name"])
        return result2
    return result


# ── MicPassthrough クラス ─────────────────────────────────────────────────────

class MicPassthrough:
    """
    マイク入力をリアルタイムで出力デバイスに転送するクラス。
    passthrough（CABLE Input 等）と monitor（手元スピーカー確認）を独立管理します。
    """

    def __init__(self):
        self._pt_stream:  Optional[sd.Stream] = None  # passthrough
        self._mon_stream: Optional[sd.Stream] = None  # monitor
        self._active         = False
        self._monitor_active = False
        self._volume         = 1.0   # ゲイン 0.0–2.0（50→等倍, 100→2倍）
        self._lock           = threading.Lock()

    # ----------------------------------------------------------------
    # 音量
    # ----------------------------------------------------------------

    def set_volume(self, volume: int) -> None:
        """0–100。50 = 等倍ゲイン、100 = 2 倍ゲイン。"""
        with self._lock:
            self._volume = max(0.0, min(2.0, volume / 50.0))

    # ----------------------------------------------------------------
    # パス送信（マイク → CABLE Input 等）
    # ----------------------------------------------------------------

    def start(self, input_name: str, output_name: str) -> None:
        """
        マイク → 指定出力デバイスへのパス送信を開始します。
        デバイスは名前で渡してください（WASAPI 内で自動マッチング）。
        output_name が空または "デフォルト（システム規定）" の場合は
        WASAPI デフォルト出力を使用します。
        """
        self.stop()

        in_idx = _find_wasapi(input_name, True) if input_name else None
        if output_name and output_name != "デフォルト（システム規定）":
            out_idx = _find_wasapi(output_name, False)
        else:
            out_idx = _wasapi_default_output()

        self._pt_stream = self._make_stream(in_idx, out_idx)
        self._pt_stream.start()
        self._active = True

    def stop(self) -> None:
        """パス送信を停止します。"""
        if self._pt_stream is not None:
            try:
                self._pt_stream.stop()
                self._pt_stream.close()
            except Exception:
                pass
            self._pt_stream = None
        self._active = False

    # ----------------------------------------------------------------
    # モニタリング（マイク → 手元スピーカーで確認）
    # ----------------------------------------------------------------

    def start_monitor(self, input_name: str) -> None:
        """
        マイク → WASAPI デフォルト出力（ヘッドホン/スピーカー）へルーティング。
        自分の声が正しく拾えているか確認するためのモニタリング機能です。
        """
        self.stop_monitor()
        in_idx  = _find_wasapi(input_name, True) if input_name else None
        out_idx = _wasapi_default_output()

        self._mon_stream = self._make_stream(in_idx, out_idx)
        self._mon_stream.start()
        self._monitor_active = True

    def stop_monitor(self) -> None:
        if self._mon_stream is not None:
            try:
                self._mon_stream.stop()
                self._mon_stream.close()
            except Exception:
                pass
            self._mon_stream = None
        self._monitor_active = False

    # ----------------------------------------------------------------
    # 内部ユーティリティ
    # ----------------------------------------------------------------

    def _make_stream(
        self, in_idx: Optional[int], out_idx: Optional[int]
    ) -> sd.Stream:
        def _callback(indata, outdata, frames, time_info, status):
            with self._lock:
                vol = self._volume
            np.multiply(indata, vol, out=outdata)

        return sd.Stream(
            device=(in_idx, out_idx),
            samplerate=SAMPLERATE,
            channels=CHANNELS,
            blocksize=BLOCKSIZE,
            dtype="float32",
            callback=_callback,
            latency="low",
        )

    # ----------------------------------------------------------------
    # プロパティ / 解放
    # ----------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._active

    @property
    def monitor_active(self) -> bool:
        return self._monitor_active

    def release(self) -> None:
        self.stop()
        self.stop_monitor()
