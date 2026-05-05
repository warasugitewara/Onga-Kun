"""
main.py  ―  イベント管理・結合モジュール
ui.py（見た目）と audio_player.py（音の処理）をつなぎ合わせます。
グローバルホットキーの登録・解除もここで管理します。
"""

import json
import os
import threading

import customtkinter as ctk
import keyboard

from audio_player import AudioPlayer
from mic_passthrough import MicPassthrough, get_input_device_names
from ui import App
from updater import check_latest, download_and_launch
from version import VERSION

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


# ── 設定ファイルの読み書き ──────────────────────────────────────────────────

def load_settings() -> dict:
    default: dict = {
        "output_device": "", "volume": 50,
        "mic_input_device": "", "mic_volume": 80,
        "soundboard": [],
    }
    if not os.path.exists(SETTINGS_PATH):
        return default
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[警告] 設定保存失敗: {e}")


def _next_id(settings: dict) -> int:
    """settings の soundboard リスト内で最大の id + 1 を返す"""
    ids = [item["id"] for item in settings.get("soundboard", [])]
    return max(ids, default=0) + 1


# ── ホットキー管理 ─────────────────────────────────────────────────────────

# 登録済みホットキーハンドルを保持するリスト（unhook_all_hotkeys の代替）
_hotkey_handles: list = []


def register_hotkeys(settings: dict, player: AudioPlayer) -> None:
    """
    soundboard エントリのホットキーを一括登録します。
    呼ぶ前に既存フックをすべて解除するので、設定変更後に再呼び出しするだけでOKです。
    ゲームなど他ウィンドウが前面でも検知できます（管理者権限推奨）。
    """
    global _hotkey_handles
    # 既存のホットキーを個別に解除（unhook_all_hotkeys は Python 3.11+ で不安定）
    for handle in _hotkey_handles:
        try:
            keyboard.remove_hotkey(handle)
        except Exception:
            pass
    _hotkey_handles.clear()

    count = 0
    for item in settings.get("soundboard", []):
        hotkey = item.get("hotkey", "").strip()
        file   = item.get("file",    "").strip()
        if not hotkey or not file or not os.path.exists(file):
            continue
        # suppress=False → 他アプリへのキー入力はブロックしない
        handle = keyboard.add_hotkey(hotkey, lambda f=file: player.play_effect(f), suppress=False)
        _hotkey_handles.append(handle)
        count += 1
    print(f"[ホットキー] {count} 件登録")


# ── メインエントリポイント ─────────────────────────────────────────────────

def main():
    settings = load_settings()
    player   = AudioPlayer()
    mic      = MicPassthrough()
    app      = App()

    # VLC デバイス列挙はバックグラウンドで実行
    def _load_devices():
        devices = player.get_audio_devices()
        saved   = settings.get("output_device", "")
        # ← 保存済みデバイスを player にも反映（これがないと起動後は常にデフォルト出力になる）
        if saved:
            player.set_output_device(saved)
        app.after(0, lambda: app.set_devices(devices, saved))

    threading.Thread(target=_load_devices, daemon=True).start()

    # マイク入力デバイス列挙もバックグラウンドで実行
    def _load_mic_devices():
        mic_devs = get_input_device_names()
        current  = settings.get("mic_input_device", "")
        app.after(0, lambda: app.set_mic_devices(mic_devs, current))

    threading.Thread(target=_load_mic_devices, daemon=True).start()

    # 初期値を UI と音声エンジンに反映
    app.set_volume(settings.get("volume", 80))
    player.set_volume(settings.get("volume", 80))
    app.set_mic_volume(settings.get("mic_volume", 80))
    mic.set_volume(settings.get("mic_volume", 80))
    app.set_soundboard(settings.get("soundboard", []))

    register_hotkeys(settings, player)

    # ── アップデートチェック（バックグラウンド、起動を妨げない）──────────────
    def _check_update():
        result = check_latest()
        if result:
            latest_tag, dl_url = result
            app.after(0, lambda: _show_update_dialog(latest_tag, dl_url))

    threading.Thread(target=_check_update, daemon=True).start()

    def _show_update_dialog(latest_tag: str, dl_url: str):
        dlg = ctk.CTkToplevel(app)
        dlg.title("アップデートがあります")
        dlg.geometry("380x170")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

        ctk.CTkLabel(
            dlg,
            text=f"🎉  v{VERSION} → {latest_tag}  のアップデートがあります",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(pady=(22, 6))
        ctk.CTkLabel(
            dlg,
            text="今すぐインストーラをダウンロードしますか？",
            text_color="#8b93a8",
        ).pack(pady=(0, 16))

        progress = ctk.CTkProgressBar(dlg, width=320)

        def _do_update():
            btn_yes.configure(state="disabled")
            btn_no.configure(state="disabled")
            progress.pack(pady=(0, 10))
            progress.set(0)

            def _on_progress(pct: int):
                app.after(0, lambda p=pct: progress.set(p / 100))

            threading.Thread(
                target=lambda: download_and_launch(dl_url, _on_progress),
                daemon=True,
            ).start()

        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack()
        btn_yes = ctk.CTkButton(row, text="ダウンロード & 更新", width=160, command=_do_update)
        btn_yes.pack(side="left", padx=6)
        btn_no = ctk.CTkButton(
            row, text="今はしない", width=120,
            fg_color="#3a3a4a", hover_color="#4a4a5a",
            command=dlg.destroy,
        )
        btn_no.pack(side="left", padx=6)

    # ── コールバック定義 ────────────────────────────────────────────────────

    def on_play(file_path: str):
        player.play_music(file_path)

    def on_pause():
        player.pause_music()

    def on_stop():
        player.stop_music()

    def on_stop_all():
        """サウンドボードで鳴らしている効果音をすべて停止（BGM は止めない）"""
        player.stop_all_effects()

    def on_volume(volume: int):
        settings["volume"] = volume
        player.set_volume(volume)

    def on_device(device_name: str):
        settings["output_device"] = device_name
        player.set_output_device(device_name)

    def on_effect(item_id: int):
        for item in settings.get("soundboard", []):
            if item["id"] == item_id:
                file = item.get("file", "").strip()
                if file and os.path.exists(file):
                    player.play_effect(file)
                else:
                    print(f"[警告] ファイル未設定または見つかりません id={item_id}")
                return

    def on_edit_sound(updated: dict):
        for i, item in enumerate(settings["soundboard"]):
            if item["id"] == updated["id"]:
                settings["soundboard"][i] = updated
                break
        register_hotkeys(settings, player)
        app.update_sound_item(updated)
        save_settings(settings)

    def on_delete_sound(item_id: int):
        settings["soundboard"] = [it for it in settings["soundboard"] if it["id"] != item_id]
        register_hotkeys(settings, player)
        app.remove_sound_item(item_id)
        save_settings(settings)

    def on_add_sound(item_data: dict):
        """EditDialog から渡された item_data に ID を付与して追加する"""
        item_data["id"] = _next_id(settings)
        settings["soundboard"].append(item_data)
        register_hotkeys(settings, player)
        app.add_sound_item(item_data)
        save_settings(settings)

    # ── マイク パス送信コールバック ─────────────────────────────────────────

    def on_mic_toggle(enabled: bool):
        if enabled:
            mic_in_name = settings.get("mic_input_device", "")
            out_name    = settings.get("output_device", "")
            try:
                mic.start(mic_in_name, out_name)
            except Exception as e:
                print(f"[エラー] マイクパス送信開始失敗: {e}")
                app.after(0, lambda: app.set_mic_active(False))
        else:
            mic.stop()

    def on_mic_device(device_name: str):
        settings["mic_input_device"] = device_name
        save_settings(settings)
        # パス送信中ならデバイスを切り替えて再起動
        if mic.active:
            out_name = settings.get("output_device", "")
            try:
                mic.start(device_name, out_name)
                app.set_mic_active(True)
            except Exception as e:
                print(f"[エラー] マイクパス送信再起動失敗: {e}")
                app.after(0, lambda: app.set_mic_active(False))
        # モニター中も再起動
        if mic.monitor_active:
            try:
                mic.start_monitor(device_name)
                app.set_mic_monitor_active(True)
            except Exception as e:
                print(f"[エラー] モニター再起動失敗: {e}")
                app.after(0, lambda: app.set_mic_monitor_active(False))

    def on_mic_volume(volume: int):
        settings["mic_volume"] = volume
        mic.set_volume(volume)
        save_settings(settings)

    def on_mic_monitor(enabled: bool):
        if enabled:
            mic_in_name = settings.get("mic_input_device", "")
            try:
                mic.start_monitor(mic_in_name)
            except Exception as e:
                print(f"[エラー] モニタリング開始失敗: {e}")
                app.after(0, lambda: app.set_mic_monitor_active(False))
        else:
            mic.stop_monitor()

    # ── コールバック注入 ────────────────────────────────────────────────────
    app.set_callbacks(
        on_play=on_play,
        on_pause=on_pause,
        on_stop=on_stop,
        on_stop_all=on_stop_all,
        on_volume=on_volume,
        on_device=on_device,
        on_effect=on_effect,
        on_edit_sound=on_edit_sound,
        on_delete_sound=on_delete_sound,
        on_add_sound=on_add_sound,
        on_mic_toggle=on_mic_toggle,
        on_mic_device=on_mic_device,
        on_mic_volume=on_mic_volume,
        on_mic_monitor=on_mic_monitor,
    )

    # ── メインループ ────────────────────────────────────────────────────────
    try:
        app.mainloop()
    finally:
        for handle in _hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        mic.release()
        player.release()
        save_settings(settings)
        print("[終了] 設定を保存しました")


if __name__ == "__main__":
    main()
