"""
audio_player.py
オーディオ制御モジュール。python-vlc をラップして UI から扱いやすいクラスを提供します。
"""

import os
import vlc
import threading
from typing import Optional


def _find_vlc_dir() -> Optional[str]:
    """VLC のインストールディレクトリを返す（なければ None）。"""
    for path in [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ]:
        if os.path.exists(os.path.join(path, "libvlc.dll")):
            return path
    return None


# VLC DLL を PATH に追加（python-vlc が libvlc.dll を見つけられるようにする）
_vlc_dir = _find_vlc_dir()
if _vlc_dir and _vlc_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _vlc_dir + os.pathsep + os.environ.get("PATH", "")


class AudioPlayer:
    """
    メイン音楽の再生・停止・一時停止と、
    効果音の並列再生（サウンドボード機能）を担うクラス。
    """

    # VLC の Windows 向け WASAPI/MMDevice モジュール名（優先順）
    _WIN_AUDIO_MODULES = (b"mmdevice", b"wasapi", b"directsound", b"waveout")

    def __init__(self):
        # VLC インスタンス（--quiet でログ抑制）
        self._instance = vlc.Instance("--quiet")
        # メイン音楽用プレイヤー
        self._music_player: Optional[vlc.MediaPlayer] = None
        # 選択中の出力デバイス description（空文字 = デフォルト）
        self._output_device: str = ""
        # 音量 0-100
        self._volume: int = 80
        # 効果音プレイヤープールのロック（スレッドセーフ並列再生用）
        self._effect_lock = threading.Lock()
        # 再生中の効果音プレイヤーを追跡するリスト（自動GC付き）
        self._effect_players: list[vlc.MediaPlayer] = []
        # description → (module_bytes, device_id_bytes) のキャッシュ
        self._device_map: dict[str, tuple[bytes, bytes]] = {}

    # ---------------------------------------------------------------
    # デバイス関連
    # ---------------------------------------------------------------

    def _build_device_map(self) -> None:
        """
        利用可能な全出力デバイスを列挙して self._device_map を更新します。
        VLC の AudioOutputDevice はリンクリスト構造のため .contents で辿ります。
        """
        self._device_map = {}
        for mod in self._WIN_AUDIO_MODULES:
            ptr = self._instance.audio_output_device_list_get(mod)
            if not ptr:
                continue
            node = ptr
            while node and node.contents:
                raw_dev  = node.contents.device       # bytes | None
                raw_desc = node.contents.description  # bytes | None
                if raw_dev and raw_desc:
                    desc = raw_desc.decode("utf-8", errors="replace")
                    self._device_map[desc] = (mod, raw_dev)
                nxt = node.contents.next
                if not nxt:
                    break
                node = nxt
            # libvlc_audio_output_device_list_release はバインディング未対応のため
            # python-vlc の vlc.AudioOutputDevice.__del__ に任せる
            break  # 最初に成功したモジュールだけ使えば十分

    def get_audio_devices(self) -> list[str]:
        """
        VLC が認識しているオーディオ出力デバイスの一覧を返します。
        VB-Cable など仮想デバイスも含みます。
        先頭要素は常に「デフォルト」（空文字キー）です。
        """
        self._build_device_map()
        names = list(self._device_map.keys())
        # 先頭に「デフォルト（システム規定）」を挿入
        default_label = "デフォルト（システム規定）"
        if default_label not in names:
            names.insert(0, default_label)
        return names

    def set_output_device(self, device_description: str) -> None:
        """
        次回再生から使用するオーディオデバイスを設定します。
        device_description は get_audio_devices() が返した文字列を渡してください。
        現在再生中のプレイヤーにも即時反映します。
        """
        self._output_device = device_description
        if self._music_player is not None:
            self._apply_device(self._music_player, device_description)

    # ---------------------------------------------------------------
    # 音楽プレイヤー
    # ---------------------------------------------------------------

    def play_music(self, file_path: str) -> None:
        """音楽ファイルを再生します。すでに再生中の場合は停止してから再生します。"""
        self.stop_music()
        media = self._instance.media_new(file_path)
        self._music_player = self._instance.media_player_new()
        self._music_player.set_media(media)
        self._music_player.audio_set_volume(self._volume)
        if self._output_device:
            self._apply_device(self._music_player, self._output_device)
        self._music_player.play()

    def pause_music(self) -> None:
        """再生中は一時停止、一時停止中は再開します（トグル）。"""
        if self._music_player is not None:
            self._music_player.pause()

    def stop_music(self) -> None:
        """音楽を停止してプレイヤーを解放します。"""
        if self._music_player is not None:
            self._music_player.stop()
            self._music_player.release()
            self._music_player = None

    def set_volume(self, volume: int) -> None:
        """
        音量を 0–100 の範囲で設定します。
        メイン音楽プレイヤーに即時反映します（効果音は発火時の音量が適用されます）。
        """
        self._volume = max(0, min(100, volume))
        if self._music_player is not None:
            self._music_player.audio_set_volume(self._volume)

    def get_music_state(self) -> str:
        """再生状態を "playing" / "paused" / "stopped" で返します。"""
        if self._music_player is None:
            return "stopped"
        state = self._music_player.get_state()
        if state == vlc.State.Playing:
            return "playing"
        if state == vlc.State.Paused:
            return "paused"
        return "stopped"

    # ---------------------------------------------------------------
    # 効果音（並列再生）
    # ---------------------------------------------------------------

    def play_effect(self, file_path: str, volume: Optional[int] = None) -> None:
        """
        効果音を非同期・並列で再生します（サウンドボード機能）。
        音楽の再生に割り込まずに重ね再生できます。
        再生終了後にプレイヤーを自動解放するためスレッドを使います。
        """
        vol = volume if volume is not None else self._volume

        def _run():
            import time
            media = self._instance.media_new(file_path)
            player = self._instance.media_player_new()
            player.set_media(media)
            player.audio_set_volume(vol)
            if self._output_device:
                self._apply_device(player, self._output_device)

            with self._effect_lock:
                # 終了済みプレイヤーをGC（解放済みオブジェクトに触らないよう try/except）
                alive = []
                for p in self._effect_players:
                    try:
                        if p.get_state() not in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
                            alive.append(p)
                    except Exception:
                        pass
                self._effect_players = alive
                self._effect_players.append(player)

            player.play()

            # 再生終了を待機してから解放
            # ※ stop_all_effects() は stop() のみ呼ぶ（release はここで行う）
            while True:
                try:
                    state = player.get_state()
                except Exception:
                    break
                if state in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
                    break
                time.sleep(0.05)
            try:
                player.release()
            except Exception:
                pass

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def stop_all_effects(self) -> None:
        """現在再生中の効果音をすべて停止します。"""
        with self._effect_lock:
            for player in self._effect_players:
                try:
                    player.stop()
                    # release() は _run スレッドに委ねる（二重解放によるアクセス違反を防ぐ）
                except Exception:
                    pass
            self._effect_players.clear()

    # ---------------------------------------------------------------
    # 内部ユーティリティ
    # ---------------------------------------------------------------

    def _apply_device(self, player: vlc.MediaPlayer, device_description: str) -> None:
        """
        指定プレイヤーの出力先デバイスを変更します。
        デフォルト選択時や未登録デバイス名は何もしない（VLC 既定デバイスを使用）。
        """
        if not device_description or device_description == "デフォルト（システム規定）":
            return
        if device_description not in self._device_map:
            # キャッシュが古い可能性があるので再取得
            self._build_device_map()
        entry = self._device_map.get(device_description)
        if entry is None:
            return
        mod_bytes, dev_id_bytes = entry
        try:
            # audio_output_device_set(module, device_id)
            # module は str か bytes どちらでも受け付ける
            player.audio_output_device_set(
                mod_bytes.decode("ascii"),
                dev_id_bytes.decode("ascii"),
            )
        except Exception as e:
            print(f"[警告] デバイス設定失敗 ({device_description}): {e}")

    def release(self) -> None:
        """アプリ終了時にすべてのリソースを解放します。main.py から呼び出してください。"""
        try:
            self.stop_music()
        except Exception:
            pass
        try:
            self.stop_all_effects()
        except Exception:
            pass
        try:
            self._instance.release()
        except Exception:
            pass
