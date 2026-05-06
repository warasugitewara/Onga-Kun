"""
audio_player.py
soundfile + sounddevice ベースのオーディオ制御モジュール。

対応形式: WAV, FLAC, MP3, OGG (soundfile ネイティブ)
          MP4, M4A, その他 (ffmpeg フォールバック)
"""

import os
import shutil
import subprocess
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


# ── 音声ファイル読み込み（マルチフォーマット対応）────────────────────────────

# soundfile がネイティブに扱える拡張子
_SF_EXTS = {".wav", ".flac", ".mp3", ".ogg", ".aiff", ".aif"}

# ffmpeg の候補パス（PATH にない場合の検索先）
_FFMPEG_CANDIDATES = [
    "ffmpeg",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    os.path.expanduser(r"~\scoop\shims\ffmpeg.exe"),
    os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"),
]


def _find_ffmpeg() -> Optional[str]:
    for candidate in _FFMPEG_CANDIDATES:
        found = shutil.which(candidate) or (os.path.isfile(candidate) and candidate)
        if found:
            return found
    return None


def read_audio_file(file_path: str) -> tuple[np.ndarray, int]:
    """
    音声ファイルを読み込んで (float32 ndarray shape=(n,ch), samplerate) を返す。

    soundfile 対応形式 (WAV/FLAC/MP3/OGG) はそのまま読む。
    MP4/M4A など非対応形式は ffmpeg 経由で float32 raw PCM に変換する。
    """
    ext = os.path.splitext(file_path)[1].lower()

    # ── soundfile で直接読める場合 ────────────────────────────────────────
    if ext in _SF_EXTS:
        try:
            data, sr = sf.read(file_path, dtype="float32", always_2d=True)
            return data, sr
        except Exception:
            pass  # 失敗したら ffmpeg へフォールバック

    # ── ffmpeg フォールバック ─────────────────────────────────────────────
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError(
            f"'{os.path.basename(file_path)}' の読み込みに失敗しました。\n"
            "MP4/M4A ファイルには ffmpeg が必要です。\n"
            "インストール方法: winget install ffmpeg  または setup.bat を実行"
        )

    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-i", file_path,
        "-f", "f32le",   # float32 LE raw PCM
        "-ac", "2",      # stereo に統一
        "-ar", "48000",  # 48 kHz に統一（CABLE Input ネイティブ）
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg タイムアウト（ファイルが大きすぎる可能性）")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg エラー: {result.stderr.decode(errors='replace')}")

    raw = np.frombuffer(result.stdout, dtype=np.float32)
    if raw.size == 0:
        raise RuntimeError("ffmpeg が空データを返しました")
    data = raw.reshape(-1, 2)
    return data, 48000


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
    """
    WASAPI 共有モード (latency="high") でストリームを開く。
    共有モードは Windows オーディオミキサーを経由するため、
    システム音量が適用され他アプリと共存できる。
    排他モード (low) はミキサーをバイパスして爆音になるため使用しない。
    """
    try:
        return sd.OutputStream(
            device=out_idx,
            samplerate=samplerate,
            channels=channels,
            dtype="float32",
            latency="high",
        )
    except Exception as e:
        raise RuntimeError(f"出力ストリームを開けませんでした (device={out_idx}, sr={samplerate}): {e}")


# ── _EffectPlayer ────────────────────────────────────────────────────────────

class _EffectPlayer:
    """
    1 つの効果音を別スレッドで再生するクラス。
    チャンク書き込みループで stop() を確認することで即時停止をサポートする。
    """
    # 8192 サンプル (@48kHz ≈ 170ms) — ゲーム高負荷時のスケジューリング遅延への耐性を高める
    _CHUNK = 8192

    def __init__(
        self,
        out_idx: Optional[int],
        data: np.ndarray,
        samplerate: int,
        on_finish: Optional[callable] = None,
    ):
        self._out_idx    = out_idx
        self._data       = data        # shape (n, ch) float32
        self._samplerate = samplerate
        self._stop_evt   = threading.Event()
        self._on_finish  = on_finish
        self._thread     = threading.Thread(target=self._run, daemon=True)
        self.peak: float = 0.0  # 直近チャンクのピークレベル（0.0–1.0）

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
                    if len(chunk) > 0:
                        self.peak = float(np.abs(chunk).max())
                    stream.write(chunk)
                    pos += self._CHUNK
        except Exception as e:
            print(f"[エラー] 効果音再生失敗: {e}")
        finally:
            self.peak = 0.0
            if self._on_finish:
                try:
                    self._on_finish()
                except Exception:
                    pass


# ── AudioPlayer ──────────────────────────────────────────────────────────────

class AudioPlayer:
    """
    soundfile + sounddevice ベースのオーディオプレイヤー。
    公開 API は旧 VLC 版と互換。
    """

    def __init__(self):
        self._out_idx:  Optional[int] = None
        self._out_name: str           = ""
        self._volume:   int           = 50    # 0–100
        self._monitor_idx: Optional[int] = None  # 自己モニター用デバイス

        # BGM
        self._bgm_stop  = threading.Event()
        self._bgm_pause = threading.Event()
        self._bgm_thread: Optional[threading.Thread] = None
        self._bgm_state = "stopped"   # "playing" | "paused" | "stopped"
        self._bgm_peak: float = 0.0   # BGM の直近ピーク

        # 効果音（アイテム ID → メインプレイヤー）
        self._eff_lock    = threading.Lock()
        self._active_by_id: dict[int, _EffectPlayer] = {}
        self._monitor_players: list[_EffectPlayer]   = []  # モニター用（fire-and-forget）

        # デコード済みオーディオのキャッシュ（ファイルパス → (data, samplerate)）
        self._file_cache: dict[str, tuple[np.ndarray, int]] = {}

        # 効果音の開始・終了を通知するコールバック（item_id を引数に取る）
        self._on_effect_start: Optional[callable] = None
        self._on_effect_end:   Optional[callable] = None

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

    def set_monitor_device(self, name: str) -> None:
        """自己モニター用の出力デバイスを設定します。"なし" または空文字でモニター無効。"""
        if not name or name == "なし" or name == "デフォルト（システム規定）":
            self._monitor_idx = None
            print("[モニター] 無効")
        else:
            idx = _find_output_device(name)
            self._monitor_idx = idx
            dev = sd.query_devices(idx)["name"] if idx is not None else "未検出"
            print(f"[モニター] {dev} (idx={idx})")

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
        ext   = os.path.splitext(file_path)[1].lower()
        try:
            if ext in _SF_EXTS:
                # soundfile ネイティブ形式: チャンク単位でストリーミング再生
                self._bgm_run_streaming(file_path, CHUNK)
            else:
                # MP4/M4A など: ffmpeg で全データを一括読み込みしてから再生
                data, file_sr = read_audio_file(file_path)
                self._bgm_run_from_array(data, file_sr, CHUNK)
        except Exception as e:
            print(f"[エラー] BGM 再生失敗: {e}")
        finally:
            self._bgm_state = "stopped"

    def _bgm_run_streaming(self, file_path: str, chunk_size: int) -> None:
        """soundfile でチャンク単位ストリーミング再生（WAV/FLAC/MP3/OGG 用）。"""
        with sf.SoundFile(file_path) as f:
            out_idx = self._out_idx
            out_ch  = _out_channels(out_idx)
            file_sr = f.samplerate
            out_sr  = _out_samplerate(out_idx)
            opened_sr = file_sr
            try:
                stream = _open_output_stream(out_idx, file_sr, out_ch)
            except Exception:
                stream = _open_output_stream(out_idx, out_sr, out_ch)
                opened_sr = out_sr
            need_resample = (file_sr != opened_sr)

            with stream:
                while not self._bgm_stop.is_set():
                    while self._bgm_pause.is_set() and not self._bgm_stop.is_set():
                        time.sleep(0.05)
                    if self._bgm_stop.is_set():
                        break
                    chunk = f.read(chunk_size, dtype="float32", always_2d=True)
                    if len(chunk) == 0:
                        break
                    if chunk.shape[1] < out_ch:
                        chunk = np.repeat(chunk[:, :1], out_ch, axis=1)
                    elif chunk.shape[1] > out_ch:
                        chunk = chunk[:, :out_ch]
                    if need_resample:
                        n_out = int(round(len(chunk) * opened_sr / file_sr))
                        x_in  = np.arange(len(chunk))
                        x_out = np.linspace(0.0, len(chunk) - 1, n_out)
                        chunk = np.column_stack([
                            np.interp(x_out, x_in, chunk[:, c]).astype(np.float32)
                            for c in range(chunk.shape[1])
                        ])
                    scaled = chunk * (self._volume / 100.0)
                    self._bgm_peak = float(np.abs(scaled).max()) if len(scaled) else 0.0
                    stream.write(scaled)

    def _bgm_run_from_array(self, data: np.ndarray, file_sr: int, chunk_size: int) -> None:
        """ndarray から再生（ffmpeg で事前デコード済みデータ用）。"""
        out_idx = self._out_idx
        data, out_sr = _to_device_format(data, file_sr, out_idx)
        out_ch = data.shape[1]

        with _open_output_stream(out_idx, out_sr, out_ch) as stream:
            pos = 0
            while pos < len(data) and not self._bgm_stop.is_set():
                while self._bgm_pause.is_set() and not self._bgm_stop.is_set():
                    time.sleep(0.05)
                if self._bgm_stop.is_set():
                    break
                chunk = data[pos:pos + chunk_size] * (self._volume / 100.0)
                self._bgm_peak = float(np.abs(chunk).max()) if len(chunk) else 0.0
                stream.write(chunk.astype(np.float32))
                pos += chunk_size

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
        self._bgm_peak   = 0.0

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))

    def get_music_state(self) -> str:
        return self._bgm_state

    # ── コールバック設定 ──────────────────────────────────────────────────

    def set_effect_callbacks(
        self,
        on_start: Optional[callable] = None,
        on_end:   Optional[callable] = None,
    ) -> None:
        """効果音の開始・終了を通知するコールバックを登録します（引数: item_id: int）。"""
        self._on_effect_start = on_start
        self._on_effect_end   = on_end

    # ── 効果音（並列再生）────────────────────────────────────────────────

    def play_effect(
        self,
        file_path: str,
        item_id:   Optional[int] = None,
        volume:    Optional[int] = None,
    ) -> None:
        """
        効果音を再生します。

        同じ item_id がすでに再生中の場合は停止して最初から再生し直します（重ね鳴り防止）。
        デコード済みデータはキャッシュするため、2 回目以降は即座に再生が始まります。
        """
        vol     = (volume if volume is not None else self._volume) / 100.0
        out_idx = self._out_idx

        # 同一アイテムが再生中なら停止してから再スタート（重ね鳴り防止）
        if item_id is not None:
            self._stop_effect_by_id_no_callback(item_id)

        # デコード済みキャッシュを利用（ファイル I/O を省略して即再生）
        if file_path not in self._file_cache:
            try:
                raw, file_sr = read_audio_file(file_path)
                self._file_cache[file_path] = (raw, file_sr)
            except Exception as e:
                print(f"[エラー] 効果音読み込み失敗: {e}")
                return

        raw, file_sr = self._file_cache[file_path]
        data, out_sr = _to_device_format(raw, file_sr, out_idx)
        data = np.clip(data * vol, -1.0, 1.0).astype(np.float32)

        dev_name = sd.query_devices(out_idx)["name"] if out_idx is not None else "デフォルト"
        print(
            f"[再生] {os.path.basename(file_path)}"
            f"  vol={vol:.0%}  peak={float(np.abs(data).max()):.3f}"
            f"  device=[{out_idx}]{dev_name}  sr={out_sr}"
        )

        # 再生終了時のクリーンアップ（再スタート時は発火しない）
        ep_ref: list[_EffectPlayer] = []  # forward reference

        def _on_finish():
            fire = False
            with self._eff_lock:
                if item_id is not None and self._active_by_id.get(item_id) is ep_ref[0]:
                    del self._active_by_id[item_id]
                    fire = True
            if fire and self._on_effect_end:
                self._on_effect_end(item_id)

        ep_main = _EffectPlayer(out_idx, data, out_sr, on_finish=_on_finish if item_id is not None else None)
        ep_ref.append(ep_main)

        with self._eff_lock:
            # モニター（手元確認用）
            mon_idx = self._monitor_idx
            if mon_idx is not None and mon_idx != out_idx:
                mon_data, mon_sr = _to_device_format(raw, file_sr, mon_idx)
                mon_data = np.clip(mon_data * vol, -1.0, 1.0).astype(np.float32)
                mon_ep = _EffectPlayer(mon_idx, mon_data, mon_sr)
                self._monitor_players = [p for p in self._monitor_players if p.is_alive()]
                self._monitor_players.append(mon_ep)
                mon_ep.start()

            if item_id is not None:
                self._active_by_id[item_id] = ep_main

        ep_main.start()

        if item_id is not None and self._on_effect_start:
            self._on_effect_start(item_id)

    def _stop_effect_by_id_no_callback(self, item_id: int) -> None:
        """item_id の再生を停止します。終了コールバックは発火しません（再スタート用）。"""
        with self._eff_lock:
            ep = self._active_by_id.pop(item_id, None)
        if ep:
            ep.stop()

    def stop_effect_by_id(self, item_id: int) -> None:
        """item_id の再生を停止し、終了コールバックを発火します。"""
        with self._eff_lock:
            ep = self._active_by_id.pop(item_id, None)
        if ep:
            ep.stop()
            if self._on_effect_end:
                self._on_effect_end(item_id)

    def stop_all_effects(self) -> None:
        """再生中の効果音をすべて停止し、各アイテムの終了コールバックを発火します。"""
        with self._eff_lock:
            items  = list(self._active_by_id.items())
            mons   = list(self._monitor_players)
            self._active_by_id.clear()
            self._monitor_players.clear()

        for item_id, ep in items:
            ep.stop()
            if self._on_effect_end:
                self._on_effect_end(item_id)
        for ep in mons:
            ep.stop()

    def get_peak(self) -> float:
        """現在再生中の効果音 + BGM のピークレベル（0.0–1.0）を返します。"""
        with self._eff_lock:
            eff_peaks = [ep.peak for ep in self._active_by_id.values() if ep.is_alive()]
        all_peaks = eff_peaks + ([self._bgm_peak] if self._bgm_peak > 0 else [])
        return max(all_peaks) if all_peaks else 0.0

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
        self._file_cache.clear()

