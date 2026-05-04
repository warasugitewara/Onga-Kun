"""
ui.py  ―  音ガくん UIモジュール
Voicemod / Discord サウンドボード風のモダンダーク UI
"""

import customtkinter as ctk
from tkinter import filedialog, Menu
from typing import Callable, Optional

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── カラー定数 ──────────────────────────────────────────────────────────────
BG          = "#111318"
SURFACE     = "#1e2029"
TOOLBAR     = "#16181f"
BORDER      = "#2e3140"
TEXT        = "#e8eaed"
TEXT_SUB    = "#8b93a8"
RED_BTN     = "#8b2020"
RED_HOVER   = "#a52828"
GREEN_BTN   = "#1e6b3c"
GREEN_HOVER = "#278b4f"

# サウンドボタンのカラーパレット（ボタン id % len でインデックスを決定）
PALETTE = [
    "#c0392b", "#2980b9", "#27ae60", "#8e44ad",
    "#d35400", "#16a085", "#e91e63", "#0097a7",
    "#a93226", "#1e8bc3", "#1d8348", "#76448a",
    "#ca6f1e", "#0e6655", "#b03a2e", "#1a5276",
]


def _lighten(hex_color: str, amount: int = 28) -> str:
    """ホバーエフェクト用に色を明るくする"""
    h = hex_color.lstrip("#")
    r = min(255, int(h[0:2], 16) + amount)
    g = min(255, int(h[2:4], 16) + amount)
    b = min(255, int(h[4:6], 16) + amount)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── サウンドボードボタン ────────────────────────────────────────────────────
class SoundboardButton(ctk.CTkFrame):
    """Voicemod 風のカード型サウンドボタン"""

    def __init__(
        self, parent, item: dict, color: str,
        on_play: Callable, on_edit: Callable, on_delete: Callable, **kw
    ):
        super().__init__(
            parent, width=148, height=88,
            corner_radius=10, fg_color=color, **kw
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        self.item       = item
        self._on_play   = on_play
        self._on_edit   = on_edit
        self._on_delete = on_delete
        self._base      = color
        self._hover     = _lighten(color)

        self.name_lbl = ctk.CTkLabel(
            self, text=item["name"],
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white", wraplength=130, justify="center",
        )
        self.name_lbl.place(relx=0.5, rely=0.42, anchor="center")

        hotkey = item.get("hotkey", "")
        self.key_lbl = ctk.CTkLabel(
            self,
            text=f"[{hotkey}]" if hotkey else "─",
            font=ctk.CTkFont(size=10),
            text_color="#cccccc",
        )
        self.key_lbl.place(relx=0.5, rely=0.78, anchor="center")

        for w in (self, self.name_lbl, self.key_lbl):
            w.bind("<Button-1>", self._click)
            w.bind("<Button-3>", self._right_click)
            w.bind("<Enter>",    self._enter)
            w.bind("<Leave>",    self._leave)

    def _click(self, _e):
        # クリック時のフラッシュエフェクト
        self.configure(fg_color="white")
        self.after(90, lambda: self.configure(fg_color=self._base))
        self._on_play(self.item["id"])

    def _right_click(self, event):
        m = Menu(
            self.winfo_toplevel(), tearoff=0,
            bg="#252831", fg="white",
            activebackground="#363a4a", activeforeground="white",
            font=("Segoe UI", 10),
        )
        m.add_command(label="✏  編集 / ファイル割り当て", command=lambda: self._on_edit(self.item))
        m.add_separator()
        m.add_command(label="🗑  削除", command=lambda: self._on_delete(self.item["id"]))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _enter(self, _e): self.configure(fg_color=self._hover)
    def _leave(self, _e): self.configure(fg_color=self._base)

    def update_item(self, item: dict):
        self.item = item
        self.name_lbl.configure(text=item["name"])
        hotkey = item.get("hotkey", "")
        self.key_lbl.configure(text=f"[{hotkey}]" if hotkey else "─")


# ── 編集ダイアログ ─────────────────────────────────────────────────────────
class EditDialog(ctk.CTkToplevel):
    """効果音の名前・ファイル・ホットキーを編集するモーダルダイアログ"""

    def __init__(self, parent, item: dict, on_save: Callable):
        super().__init__(parent)
        self.title("効果音を編集")
        self.geometry("440x280")
        self.resizable(False, False)
        self.configure(fg_color=SURFACE)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._item    = dict(item)
        self._on_save = on_save

        F = {"padx": 24, "pady": 5}

        ctk.CTkLabel(
            self, text="表示名", font=ctk.CTkFont(size=11), text_color=TEXT_SUB
        ).pack(anchor="w", padx=24, pady=(18, 2))
        self.name_ent = ctk.CTkEntry(self, width=392, placeholder_text="例: 草生える")
        self.name_ent.insert(0, item.get("name", ""))
        self.name_ent.pack(**F)

        ctk.CTkLabel(
            self, text="音声ファイル", font=ctk.CTkFont(size=11), text_color=TEXT_SUB
        ).pack(anchor="w", padx=24, pady=(8, 2))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", **F)
        self.file_ent = ctk.CTkEntry(row, width=330, placeholder_text="ファイルを選択してください")
        self.file_ent.insert(0, item.get("file", ""))
        self.file_ent.pack(side="left")
        ctk.CTkButton(row, text="…", width=52, command=self._browse).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(
            self, text="ホットキー", font=ctk.CTkFont(size=11), text_color=TEXT_SUB
        ).pack(anchor="w", padx=24, pady=(8, 2))
        self.key_ent = ctk.CTkEntry(
            self, width=392, placeholder_text="例: F1  /  ctrl+1  /  alt+g"
        )
        self.key_ent.insert(0, item.get("hotkey", ""))
        self.key_ent.pack(**F)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=16)
        ctk.CTkButton(btn_row, text="保存", width=130, command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(
            btn_row, text="キャンセル", width=130,
            fg_color="#3a3a4a", hover_color="#4a4a5a",
            command=self.destroy,
        ).pack(side="left", padx=6)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="音声ファイルを選択",
            filetypes=[("音声ファイル", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("すべて", "*.*")],
        )
        if path:
            self.file_ent.delete(0, "end")
            self.file_ent.insert(0, path)

    def _save(self):
        name = self.name_ent.get().strip()
        self._item["name"]   = name if name else self._item["name"]
        self._item["file"]   = self.file_ent.get().strip()
        self._item["hotkey"] = self.key_ent.get().strip()
        self._on_save(self._item)
        self.destroy()


# ── メインウィンドウ ────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("音ガくん")
        self.geometry("960x640")
        self.minsize(800, 520)
        self.configure(fg_color=BG)

        # コールバック格納（main.py から set_callbacks() で注入）
        self._cb_play:       Optional[Callable[[str], None]] = None
        self._cb_pause:      Optional[Callable[[], None]]    = None
        self._cb_stop:       Optional[Callable[[], None]]    = None
        self._cb_stop_all:   Optional[Callable[[], None]]    = None
        self._cb_volume:     Optional[Callable[[int], None]] = None
        self._cb_device:     Optional[Callable[[str], None]] = None
        self._cb_effect:     Optional[Callable[[int], None]] = None
        self._cb_edit:       Optional[Callable[[dict], None]] = None
        self._cb_delete:     Optional[Callable[[int], None]] = None
        self._cb_add:        Optional[Callable[[dict], None]] = None
        # マイク パス送信
        self._cb_mic_toggle: Optional[Callable[[bool], None]] = None
        self._cb_mic_device: Optional[Callable[[str], None]]  = None
        self._cb_mic_volume: Optional[Callable[[int], None]]  = None

        self._music_file = ""
        self._all_items: list[dict] = []
        self._mic_active = False

        self._build()

    # ── UI構築 ─────────────────────────────────────────────────────────────

    def _build(self):
        self._build_header()
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x")
        self._build_main()
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", side="bottom")
        self._build_player_strip()
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", side="bottom")
        self._build_mic_strip()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=TOOLBAR, height=54, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="🎛  音ガくん",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT,
        ).pack(side="left", padx=18)

        # 右端から詰める：音量ラベル → スライダー → 🔊 → デバイス名ラベル → ComboBox
        self.vol_label = ctk.CTkLabel(
            header, text="80", width=28,
            text_color=TEXT_SUB, font=ctk.CTkFont(size=12),
        )
        self.vol_label.pack(side="right", padx=(0, 12))

        self.vol_slider = ctk.CTkSlider(
            header, from_=0, to=100, width=110, command=self._on_volume
        )
        self.vol_slider.set(80)
        self.vol_slider.pack(side="right", padx=(0, 4))

        ctk.CTkLabel(header, text="🔊", text_color=TEXT_SUB).pack(side="right", padx=(0, 4))

        ctk.CTkLabel(
            header, text="出力先:", text_color=TEXT_SUB, font=ctk.CTkFont(size=12)
        ).pack(side="right", padx=(0, 6))

        self.device_cb = ctk.CTkComboBox(
            header, width=230, values=["読み込み中…"], command=self._on_device
        )
        self.device_cb.pack(side="right", padx=(0, 16))

    def _build_main(self):
        # アクションバー（検索・追加・全停止）
        bar = ctk.CTkFrame(self, fg_color=BG, height=46)
        bar.pack(fill="x", padx=16, pady=(8, 4))
        bar.pack_propagate(False)

        self.search_entry = ctk.CTkEntry(
            bar, placeholder_text="🔍  サウンドを検索…", width=220
        )
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(
            bar, text="⏹  すべて停止", width=120,
            fg_color=RED_BTN, hover_color=RED_HOVER,
            command=self._on_stop_all,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bar, text="＋  サウンドを追加", width=148,
            command=self._on_add,
        ).pack(side="left")

        # スクロール可能なサウンドグリッド
        self.grid_frame = ctk.CTkScrollableFrame(self, fg_color=BG)
        self.grid_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    def _build_mic_strip(self):
        """マイク パス送信コントロールストリップ（BGM ストリップの上）"""
        strip = ctk.CTkFrame(self, fg_color=TOOLBAR, height=44, corner_radius=0)
        strip.pack(fill="x", side="bottom")
        strip.pack_propagate(False)

        # トグルボタン
        self.mic_btn = ctk.CTkButton(
            strip, text="🎤  OFF", width=90, height=30,
            fg_color=BORDER, hover_color="#3e4160",
            command=self._on_mic_toggle,
        )
        self.mic_btn.pack(side="left", padx=(14, 8))

        ctk.CTkLabel(
            strip, text="マイク入力:", text_color=TEXT_SUB, font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 6))

        self.mic_input_cb = ctk.CTkComboBox(
            strip, width=210, values=["読み込み中…"], command=self._on_mic_device
        )
        self.mic_input_cb.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(strip, text="🎚️", text_color=TEXT_SUB).pack(side="left", padx=(0, 4))

        self.mic_vol_slider = ctk.CTkSlider(
            strip, from_=0, to=100, width=90, command=self._on_mic_volume
        )
        self.mic_vol_slider.set(80)
        self.mic_vol_slider.pack(side="left", padx=(0, 4))

        self.mic_vol_label = ctk.CTkLabel(
            strip, text="80", width=28, text_color=TEXT_SUB, font=ctk.CTkFont(size=12)
        )
        self.mic_vol_label.pack(side="left")

    def _build_player_strip(self):
        """下部の BGM プレイヤーストリップ"""
        strip = ctk.CTkFrame(self, fg_color=SURFACE, height=52, corner_radius=0)
        strip.pack(fill="x", side="bottom")
        strip.pack_propagate(False)

        ctk.CTkLabel(
            strip, text="BGM:", text_color=TEXT_SUB, font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(14, 4))

        ctk.CTkButton(
            strip, text="📁", width=36, height=30,
            fg_color="transparent", hover_color=BORDER,
            command=self._on_select_music,
        ).pack(side="left", padx=(0, 6))

        self.music_label = ctk.CTkLabel(
            strip, text="ファイル未選択",
            font=ctk.CTkFont(size=12), text_color=TEXT_SUB,
            width=310, anchor="w",
        )
        self.music_label.pack(side="left")

        # 右端：⏹ → ⏸ → ▶ の順（右から詰める）
        ctk.CTkButton(
            strip, text="⏹", width=36, height=30,
            fg_color=RED_BTN, hover_color=RED_HOVER,
            command=self._on_stop_music,
        ).pack(side="right", padx=(0, 14))

        ctk.CTkButton(
            strip, text="⏸", width=36, height=30,
            fg_color=BORDER, hover_color="#3e4160",
            command=self._on_pause_music,
        ).pack(side="right", padx=(0, 4))

        ctk.CTkButton(
            strip, text="▶", width=36, height=30,
            fg_color=GREEN_BTN, hover_color=GREEN_HOVER,
            command=self._on_play_music,
        ).pack(side="right", padx=(0, 4))

    # ── public API（main.py から呼ぶ）──────────────────────────────────────

    def set_callbacks(
        self, *,
        on_play, on_pause, on_stop, on_stop_all,
        on_volume, on_device, on_effect,
        on_edit_sound, on_delete_sound, on_add_sound,
        on_mic_toggle=None, on_mic_device=None, on_mic_volume=None,
    ):
        self._cb_play       = on_play
        self._cb_pause      = on_pause
        self._cb_stop       = on_stop
        self._cb_stop_all   = on_stop_all
        self._cb_volume     = on_volume
        self._cb_device     = on_device
        self._cb_effect     = on_effect
        self._cb_edit       = on_edit_sound
        self._cb_delete     = on_delete_sound
        self._cb_add        = on_add_sound
        self._cb_mic_toggle = on_mic_toggle
        self._cb_mic_device = on_mic_device
        self._cb_mic_volume = on_mic_volume

    def set_devices(self, devices: list[str], current: str = ""):
        self.device_cb.configure(values=devices)
        target = current if (current and current in devices) else (devices[0] if devices else "")
        if target:
            self.device_cb.set(target)

    def set_volume(self, volume: int):
        self.vol_slider.set(volume)
        self.vol_label.configure(text=str(volume))

    def set_mic_devices(self, devices: list[str], current: str = ""):
        """マイク入力デバイスのドロップダウンを更新します。"""
        self.mic_input_cb.configure(values=devices if devices else ["(デバイスなし)"])
        target = current if (current and current in devices) else (devices[0] if devices else "")
        if target:
            self.mic_input_cb.set(target)

    def set_mic_active(self, active: bool):
        """パス送信ボタンの表示状態を更新します（外部から呼ぶ用）。"""
        self._mic_active = active
        if active:
            self.mic_btn.configure(text="🎤  ON", fg_color=GREEN_BTN, hover_color=GREEN_HOVER)
        else:
            self.mic_btn.configure(text="🎤  OFF", fg_color=BORDER, hover_color="#3e4160")

    def set_mic_volume(self, volume: int):
        self.mic_vol_slider.set(volume)
        self.mic_vol_label.configure(text=str(volume))

    def set_soundboard(self, items: list[dict]):
        self._all_items = list(items)
        self._render_grid(items)

    def update_sound_item(self, item: dict):
        """編集後に特定ボタンのラベルを更新する"""
        for i, it in enumerate(self._all_items):
            if it["id"] == item["id"]:
                self._all_items[i] = item
                break
        q = self.search_entry.get().strip().lower()
        shown = [it for it in self._all_items if q in it["name"].lower()] if q else self._all_items
        self._render_grid(shown)

    def add_sound_item(self, item: dict):
        self._all_items.append(item)
        self._render_grid(self._all_items)

    def remove_sound_item(self, item_id: int):
        self._all_items = [it for it in self._all_items if it["id"] != item_id]
        self._render_grid(self._all_items)

    # ── 内部イベントハンドラ ───────────────────────────────────────────────

    def _render_grid(self, items: list[dict]):
        """items をグリッドに描画する（検索フィルタでも使用）"""
        for w in self.grid_frame.winfo_children():
            w.destroy()

        cols = 5
        for i, item in enumerate(items):
            color = PALETTE[item["id"] % len(PALETTE)]
            btn = SoundboardButton(
                self.grid_frame, item=item, color=color,
                on_play=self._proxy_effect,
                on_edit=self._open_edit,
                on_delete=self._on_delete,
            )
            btn.grid(row=i // cols, column=i % cols, padx=6, pady=6, sticky="nsew")

        for c in range(cols):
            self.grid_frame.grid_columnconfigure(c, weight=1)

    def _proxy_effect(self, item_id: int):
        if self._cb_effect:
            self._cb_effect(item_id)
        else:
            print(f"[mock] 効果音 id={item_id}")

    def _open_edit(self, item: dict):
        def _save(updated: dict):
            if self._cb_edit:
                self._cb_edit(updated)
        EditDialog(self, item, _save)

    def _on_delete(self, item_id: int):
        if self._cb_delete:
            self._cb_delete(item_id)

    def _on_search(self, _event):
        q = self.search_entry.get().strip().lower()
        filtered = [it for it in self._all_items if q in it["name"].lower()] if q else self._all_items
        self._render_grid(filtered)

    # ── マイク パス送信コントロール ────────────────────────────────────────────

    def _on_mic_toggle(self):
        new_state = not self._mic_active
        self.set_mic_active(new_state)
        if self._cb_mic_toggle:
            self._cb_mic_toggle(new_state)

    def _on_mic_device(self, selected: str):
        if self._cb_mic_device:
            self._cb_mic_device(selected)

    def _on_mic_volume(self, val: float):
        v = int(val)
        self.mic_vol_label.configure(text=str(v))
        if self._cb_mic_volume:
            self._cb_mic_volume(v)

    def _on_volume(self, val: float):
        v = int(val)
        self.vol_label.configure(text=str(v))
        if self._cb_volume:
            self._cb_volume(v)
        else:
            print(f"[mock] 音量: {v}")

    def _on_device(self, selected: str):
        if self._cb_device:
            self._cb_device(selected)

    def _on_stop_all(self):
        if self._cb_stop_all:
            self._cb_stop_all()

    def _on_add(self):
        template = {"id": -1, "name": "新しい効果音", "file": "", "hotkey": ""}
        def _save(item_data: dict):
            if self._cb_add:
                self._cb_add(item_data)
        EditDialog(self, template, _save)

    # ── BGM プレイヤーコントロール ─────────────────────────────────────────

    def _on_select_music(self):
        path = filedialog.askopenfilename(
            title="音楽ファイルを選択",
            filetypes=[("音声ファイル", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("すべて", "*.*")],
        )
        if path:
            self._music_file = path
            fname = path.split("\\")[-1]
            display = fname if len(fname) <= 42 else fname[:39] + "…"
            self.music_label.configure(text=display, text_color=TEXT)

    def _on_play_music(self):
        if not self._music_file:
            self.music_label.configure(text="⚠ ファイルを先に選択してください", text_color="#e74c3c")
            self.after(2500, lambda: self.music_label.configure(
                text="ファイル未選択", text_color=TEXT_SUB
            ))
            return
        if self._cb_play:
            self._cb_play(self._music_file)

    def _on_pause_music(self):
        if self._cb_pause:
            self._cb_pause()

    def _on_stop_music(self):
        if self._cb_stop:
            self._cb_stop()
