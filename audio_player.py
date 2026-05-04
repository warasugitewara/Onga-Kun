"""
audio_player.py
オーディオ制御モジュール。python-vlc をラップして UI から扱いやすいクラスを提供します。
"""

import vlc
import threading
from typing import Optional


class AudioPlayer:
    """
    メイン音楽の再生・停止・一時停止と、
    効果音の並列再生（サウンドボード機能）を担うクラス。
    """

    def __init__(self):
        # VLC インスタンス（--quiet でログ抑制、Windows WASAPI を優先使用）
        self._instance = vlc.Instance("--quiet", "--aout=directsound")
        # メイン音楽用プレイヤー
        self._music_player: Optional[vlc.MediaPlayer] = None
        # 出力デバイス名（空文字 = デフォルトデバイス）
        self._output_device: str = ""
        # 音量 0-100
        self._volume: int = 80
        # 効果音プレイヤープールのロック（スレッドセーフ並列再生用）
        self._effect_lock = threading.Lock()
        # 再生中の効果音プレイヤーを追跡するリスト（自動GC付き）
        self._effect_players: list[vlc.MediaPlayer] = []

    # ---------------------------------------------------------------
    # デバイス関連
    # ---------------------------------------------------------------

    def get_audio_devices(self) -> list[str]:
        """
        VLC が認識しているオーディオ出力デバイスの一覧を返します。
        VB-Cable など仮想デバイスも含みます。
        """
        # AudioOutputDeviceEnum は VLC のモジュール出力ではなくデバイスを返す
        # mlist はリンクリスト形式なので Python リストに変換します
        devices: list[str] = []
        try:
            mods = self._instance.audio_output_enumerate_devices()
            if mods is None:
                return ["default"]
            for mod in mods:
                for dev in mod.get("devices", []):
                    name = dev.get("description", "")
                    if name:
                        devices.append(name)
        except Exception:
            pass

        if not devices:
            devices.append("default")
        return devices

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
            media = self._instance.media_new(file_path)
            player = self._instance.media_player_new()
            player.set_media(media)
            player.audio_set_volume(vol)
            if self._output_device:
                self._apply_device(player, self._output_device)

            with self._effect_lock:
                # 終了済みプレイヤーをGC
                self._effect_players = [
                    p for p in self._effect_players
                    if p.get_state() not in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped)
                ]
                self._effect_players.append(player)

            player.play()

            # 再生終了を待機してから解放
            import time
            while player.get_state() not in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
                time.sleep(0.05)
            player.release()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def stop_all_effects(self) -> None:
        """現在再生中の効果音をすべて停止します。"""
        with self._effect_lock:
            for player in self._effect_players:
                player.stop()
                player.release()
            self._effect_players.clear()

    # ---------------------------------------------------------------
    # 内部ユーティリティ
    # ---------------------------------------------------------------

    def _apply_device(self, player: vlc.MediaPlayer, device_description: str) -> None:
        """
        指定プレイヤーの出力先デバイスを変更します。
        VLC の audio_output_device_set は module 名 + device_id を必要とします。
        description から device_id へのマッピングをここで行います。
        """
        try:
            mods = self._instance.audio_output_enumerate_devices()
            if mods is None:
                return
            for mod in mods:
                for dev in mod.get("devices", []):
                    if dev.get("description", "") == device_description:
                        player.audio_output_device_set(
                            mod.get("name", ""),
                            dev.get("device", "")
                        )
                        return
        except Exception:
            pass

    def release(self) -> None:
        """アプリ終了時にすべてのリソースを解放します。main.py から呼び出してください。"""
        self.stop_music()
        self.stop_all_effects()
        self._instance.release()
