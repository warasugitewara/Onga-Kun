# Onga-Kun

Windows 向けのサウンドボード・BGM プレイヤーです。  
VB-Cable と組み合わせて、ゲームのボイスチャットや Discord のマイク経由で効果音・BGM をリアルタイムに流せます。

---

## 機能

| 機能 | 説明 |
|---|---|
| 🎵 サウンドボード | ボタンまたはホットキーで効果音を即再生 |
| 🎶 BGM プレイヤー | バックグラウンドで BGM を再生・一時停止・停止 |
| 🎤 マイクパス送信 | マイク音声を VB-Cable に直接ルーティング |
| 🎧 自己モニター | 効果音をヘッドホンで同時に確認しながら送信 |
| ⌨ グローバルホットキー | ゲームが前面にあっても反応（Minecraft 式キャプチャ・同時押しコンボ対応） |
| ⚙ 自動起動 | Windows 起動時にバックグラウンド待機（デフォルト: OFF） |
| 🔄 自動アップデート | 起動時に GitHub Releases を確認して通知 |

## 対応音声フォーマット

`WAV` `FLAC` `MP3` `OGG` — ネイティブ対応  
`MP4` `M4A` — ffmpeg がインストールされている場合に対応

---

## インストール（配布版）

1. [Releases](https://github.com/warasugitewara/Onga-Kun/releases) から `onga-kun-setup-vX.X.X.exe` をダウンロード
2. インストーラーを実行
3. [VB-Cable](https://vb-audio.com/Cable/) をインストール（マイクルーティングに必要）

> **ffmpeg について**  
> MP4 / M4A を再生したい場合は別途 [ffmpeg](https://ffmpeg.org/download.html) のインストールが必要です。  
> `winget install Gyan.FFmpeg` でも導入できます。WAV / FLAC / MP3 のみなら不要です。

---

## VB-Cable との連携方法

```
[マイク] ─→ Onga-Kun (マイクパス送信 ON) ─→ [CABLE Input]
                                                     ↓
                              Discord / ゲーム の マイク入力 ← [CABLE Output]
```

1. Onga-Kun の **出力先** を `CABLE Input (VB-Audio Virtual Cable)` に設定
2. Discord 等の**マイク入力**を `CABLE Output (VB-Audio Virtual Cable)` に設定
3. マイクパス送信ボタン (`🎤 OFF → ON`) を有効にすると自分の声も一緒に送信される

---

## 開発環境セットアップ

**必要なもの**

| ソフトウェア | バージョン |
|---|---|
| Python | 3.11 以上 |
| VB-Cable | 最新版 |
| ffmpeg | 任意（MP4/M4A 再生時） |

```bat
setup.bat
```

`setup.bat` は仮想環境の作成・依存パッケージのインストール・ffmpeg の確認を自動で行います。

**依存パッケージ** (`requirements.txt`)

```
customtkinter>=5.2.0
keyboard>=0.13.5
sounddevice>=0.4.6
soundfile>=0.12.1
numpy>=1.24.0
```

**手動起動**

```bat
.venv\Scripts\activate
python main.py
```

---

## EXE / インストーラーのビルド

[Inno Setup 6](https://jrsoftware.org/isinfo.php) をインストールした上で：

```bat
build.bat
```

| 出力ファイル | パス |
|---|---|
| 実行ファイル | `dist\onga-kun\onga-kun.exe` |
| インストーラー | `installer\Output\onga-kun-setup-vX.X.X.exe` |

---

## プロジェクト構成

```
Onga-Kun/
├── main.py            # エントリポイント・ホットキー管理・コールバック結合
├── ui.py              # CustomTkinter GUI
├── audio_player.py    # sounddevice + soundfile 音声エンジン
├── mic_passthrough.py # マイクパス送信
├── startup.py         # Windows スタートアップ登録（レジストリ）
├── updater.py         # GitHub Releases 自動アップデート
├── version.py         # バージョン定義
├── setup.bat          # 開発環境セットアップ
├── build.bat          # EXE + インストーラービルド
├── onga-kun.spec      # PyInstaller 定義
└── installer/
    └── setup.iss      # Inno Setup 定義
```

---

## ライセンス

MIT

## 著者

- **warasugitewara** (https://github.com/warasugitewara) — 開発
- **sushi-m4a** (https://github.com/sushi-m4a) — アイデア・企画協力

### Contact
- 連絡は Discord で取れます。

