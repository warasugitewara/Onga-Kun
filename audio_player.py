"""
audio_player.py
soundfile + sounddevice ベースのオーディオ制御モジュール。

VLC の audio_output_device_set は play() 前後どちらで呼んでも
信頼性が低く CABLE Input へのルーティングに失敗するケースがあった。
sounddevice は WASAPI デバイスインデックスを直接指定でき、
mic_passthrough.py で実証済みの確実なルーティングが可能。
"""

import os
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


# ── WASAPI ユーティリティ ────────────────────────────────────────────────────

def _wasapi_idx() -> Optional[int]:
    for i, api in enumerate(sd.query_hostapis()):
        if "WASAPI" in api["name"]:
            return i
    return None


def _find_output_device(name: str) -> Optional[int]:
    """WASAPI 出力デバイスを名前（部分一致）で検索してインデックスを返す。"""
    wi = _wasapi_idx()
    lower = name.lower()
    for i, d in enumerate(sd.query_devices()):
        if wi is not None and d["hostapi"] != wi:
            continue
        if d["max_output_channels"] > 0 and lower in d["name"].lower():
            return i
    return None


def _out_channels(idx: Optional[int]) -> int:
    if idx is None:
        return 2
    try:
        return max(1, min(int(sd.query_devices(idx)["max_output_channels"]), 2))
    except Exception:
        return 2


def _out_samplerate(idx: Optional[int]) -> int:
    if idx is None:
        return 48000
    try:
        sr = int(sd.query_devices(idx)["default_samplerate"])
        return sr if sr > 0 else 48000
    except Exception:
        return 48000


def _to_device_format(
    data: np.ndarray, file_sr: int, out_idx: Optional[int]
) -> tuple[np.ndarray, int]:
    """
    音声データを出力デバイス向けに整形する。
    返り値: (float32 配列 shape=(n, out_ch), 出力サンプルレート)
    """
    data = data.astype(np.float32)
    if data.ndim == 1:
        data = data.reshape(-1, 1)

    out_ch = _out_channels(out_idx)
    out_sr = _out_samplerate(out_idx)

    # チャンネル調整
    if data.shape[1] < out_ch:
        data = np.repeat(data[:, :1], out_ch, axis=1)
    elif data.shape[1] > out_ch:
        data = data[:, :out_ch]

    # サンプルレート変換（必要な場合のみ）
    if file_sr != out_sr and file_sr > 0:
        n_out = int(round(len(data) * out_sr / file_sr))
        x_in  = np.arange(len(data))
        x_out = np.linspace(0.0, len(data) - 1, n_out)
        data  = np.column_stack([
            np.interp(x_out, x_in, data[:, c]).astype(np.float32)
            for c in range(data.shape[1])
        ])

    return data, out_sr


def _open_output_stream(out_idx, samplerate, channels) -> sd.OutputStream:
    """低遅延 → 高遅延の順でストリームを開こうとする。"""
    for latency in ("low", "high"):
        try:
            return sd.OutputStream(
                device=out_idx,
                samplerate=samplerate,
                channels=channels,
                dtype="float32",
                latency=latency,
            )
        except Exception:
            pass
    raise RuntimeError(f"出力ストリームを開けませんでした (device={out_idx}, sr={samplerate})")


# ── _EffectPlayer ────────────────────────────────────────────────────────────

class _EffectPlayer:
    """
    1 つの効果音を別スレッドで再生するクラス。
    チャンク書き込みループで stop() を確認することで即時停止をサポートする。
    """
    _CHUNK = 2048

    def __init__(self, out_idx: Optional[int], data: np.ndarray, samplerate: int):
        self._out_idx    = out_idx
        self._data       = data        # shape (n, ch) float32
        self._samplerate = samplerate
        self._stop_evt   = threading.Event()
        self._thread     = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        try:
            stream = _open_output_stream(
                self._out_idx, self._samplerate, self._data.shape[1]
            )
            with stream:
                pos = 0
                while pos < len(self._data) and not self._stop_evt.is_set():
                    chunk = self._data[pos : pos + self._CHUNK]
                    stream.write(chunk)
                    pos += self._CHUNK
        except Exception as e:
            print(f"[エラー] 効果音再生失敗: {e}")


# ── AudioPlayer ──────────────────────────────────────────────────────────────

class AudioPlayer:
    """
    soundfile + sounddevice ベースのオーディオプレイヤー。
    公開 API は旧 VLC 版と互換。
    """

    def __init__(self):
        self._out_idx:  Optional[int] = None
        self._out_name: str           = ""
        self._volume:   int           = 80    # 0–100

        # BGM
        self._bgm_stop  = threading.Event()
        self._bgm_pause = threading.Event()
        self._bgm_thread: Optional[threading.Thread] = None
        self._bgm_state = "stopped"   # "playing" | "paused" | "stopped"

        # 効果音
        self._eff_lock    = threading.Lock()
        self._eff_players: list[_EffectPlayer] = []

    # ── デバイス ──────────────────────────────────────────────────────────

    def get_audio_devices(self) -> list[str]:
        """
        WASAPI 出力デバイス名一覧（重複なし）を返します。
        先頭は「デフォルト（システム規定）」です。
        """
        wi = _wasapi_idx()
        seen: set[str] = set()
        result = ["デフォルト（システム規定）"]
        for d in sd.query_devices():
            if wi is not None and d["hostapi"] != wi:
                continue
            if d["max_output_channels"] > 0 and d["name"] not in seen:
                seen.add(d["name"])
                result.append(d["name"])
        return result

    def set_output_device(self, device_description: str) -> None:
        """出力デバイスを設定します。次回 play から反映されます。"""
        if not device_description or device_description == "デフォルト（システム規定）":
            self._out_idx  = None
            self._out_name = ""
        else:
            idx = _find_output_device(device_description)
            self._out_idx  = idx
            self._out_name = device_description
            print(f"[デバイス] 出力先: {device_description} (idx={idx})")

    # ── 音楽プレイヤー ────────────────────────────────────────────────────

    def play_music(self, file_path: str) -> None:
        self.stop_music()
        self._bgm_stop.clear()
        self._bgm_pause.clear()
        self._bgm_state  = "playing"
        self._bgm_thread = threading.Thread(
            target=self._bgm_run, args=(file_path,), daemon=True
        )
        self._bgm_thread.start()

    def _bgm_run(self, file_path: str) -> None:
        CHUNK = 4096
        try:
            with sf.SoundFile(file_path) as f:
                out_idx = self._out_idx
                out_ch  = _out_channels(out_idx)
                file_sr = f.samplerate
                out_sr  = _out_samplerate(out_idx)

                need_resample = (file_sr != out_sr)

                # WASAPI shared mode (latency="high") は Windows が自動リサンプリングするので
                # まずファイルのネイティブレートで試みる
                opened_sr = file_sr
                try:
                    stream = _open_output_stream(out_idx, file_sr, out_ch)
                except Exception:
                    # 失敗時はデバイスネイティブレートにフォールバック
                    stream = _open_output_stream(out_idx, out_sr, out_ch)
                    opened_sr = out_sr
                    need_resample = (file_sr != opened_sr)

                with stream:
                    while not self._bgm_stop.is_set():
                        # 一時停止中はスリープ
                        while self._bgm_pause.is_set() and not self._bgm_stop.is_set():
                            time.sleep(0.05)
                        if self._bgm_stop.is_set():
                            break

                        chunk = f.read(CHUNK, dtype="float32", always_2d=True)
                        if len(chunk) == 0:
                            break

                        # チャンネル調整
                        if chunk.shape[1] < out_ch:
                            chunk = np.repeat(chunk[:, :1], out_ch, axis=1)
                        elif chunk.shape[1] > out_ch:
                            chunk = chunk[:, :out_ch]

                        # リサンプル（必要な場合）
                        if need_resample:
                            n_out = int(round(len(chunk) * opened_sr / file_sr))
                            x_in  = np.arange(len(chunk))
                            x_out = np.linspace(0.0, len(chunk) - 1, n_out)
                            chunk = np.column_stack([
                                np.interp(x_out, x_in, chunk[:, c]).astype(np.float32)
                                for c in range(chunk.shape[1])
                            ])

                        stream.write(chunk * (self._volume / 100.0))

        except Exception as e:
            print(f"[エラー] BGM 再生失敗: {e}")
        finally:
            self._bgm_state = "stopped"

    def pause_music(self) -> None:
        if self._bgm_state == "playing":
            self._bgm_pause.set()
            self._bgm_state = "paused"
        elif self._bgm_state == "paused":
            self._bgm_pause.clear()
            self._bgm_state = "playing"

    def stop_music(self) -> None:
        self._bgm_stop.set()
        self._bgm_pause.clear()
        if self._bgm_thread and self._bgm_thread.is_alive():
            self._bgm_thread.join(timeout=2.0)
        self._bgm_thread = None
        self._bgm_state  = "stopped"

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))

    def get_music_state(self) -> str:
        return self._bgm_state

    # ── 効果音（並列再生）────────────────────────────────────────────────

    def play_effect(self, file_path: str, volume: Optional[int] = None) -> None:
        """効果音を非同期・並列で再生します。"""
        vol     = (volume if volume is not None else self._volume) / 100.0
        out_idx = self._out_idx

        try:
            raw, file_sr = sf.read(file_path, dtype="float32", always_2d=True)
        except Exception as e:
            print(f"[エラー] 効果音読み込み失敗: {e}")
            return

        data, out_sr = _to_device_format(raw, file_sr, out_idx)
        data = (data * vol).astype(np.float32)

        ep = _EffectPlayer(out_idx, data, out_sr)
        with self._eff_lock:
            self._eff_players = [p for p in self._eff_players if p.is_alive()]
            self._eff_players.append(ep)
        ep.start()

    def stop_all_effects(self) -> None:
        with self._eff_lock:
            for ep in self._eff_players:
                ep.stop()
            self._eff_players.clear()

    # ── 解放 ─────────────────────────────────────────────────────────────

    def release(self) -> None:
        try:
            self.stop_music()
        except Exception:
            pass
        try:
            self.stop_all_effects()
        except Exception:
            pass

