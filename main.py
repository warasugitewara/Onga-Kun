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
from ui import App
from updater import check_latest, download_and_launch
from version import VERSION

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


# ── 設定ファイルの読み書き ──────────────────────────────────────────────────

def load_settings() -> dict:
    default: dict = {"output_device": "", "volume": 80, "soundboard": []}
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

def register_hotkeys(settings: dict, player: AudioPlayer) -> None:
    """
    soundboard エントリのホットキーを一括登録します。
    呼ぶ前に既存フックをすべて解除するので、設定変更後に再呼び出しするだけでOKです。
    ゲームなど他ウィンドウが前面でも検知できます（管理者権限推奨）。
    """
    keyboard.unhook_all_hotkeys()
    count = 0
    for item in settings.get("soundboard", []):
        hotkey = item.get("hotkey", "").strip()
        file   = item.get("file",    "").strip()
        if not hotkey or not file or not os.path.exists(file):
            continue
        # suppress=False → 他アプリへのキー入力はブロックしない
        keyboard.add_hotkey(hotkey, lambda f=file: player.play_effect(f), suppress=False)
        count += 1
    print(f"[ホットキー] {count} 件登録")


# ── メインエントリポイント ─────────────────────────────────────────────────

def main():
    settings = load_settings()
    player   = AudioPlayer()
    app      = App()

    # VLC のデバイス列挙は少し重いのでバックグラウンドで実行
    def _load_devices():
        devices = player.get_audio_devices()
        app.after(0, lambda: app.set_devices(devices, settings.get("output_device", "")))

    threading.Thread(target=_load_devices, daemon=True).start()

    # 初期値を UI と音声エンジンに反映
    app.set_volume(settings.get("volume", 80))
    player.set_volume(settings.get("volume", 80))
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
    )

    # ── メインループ ────────────────────────────────────────────────────────
    try:
        app.mainloop()
    finally:
        keyboard.unhook_all()
        player.release()
        save_settings(settings)
        print("[終了] 設定を保存しました")


if __name__ == "__main__":
    main()
