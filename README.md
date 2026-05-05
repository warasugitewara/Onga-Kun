# Onga-Kun

Windows 向けのサウンドボード・BGM プレイヤーです。  
VB-Cable と組み合わせて、ゲームのボイスチャットや Discord のマイク経由で効果音・BGM をリアルタイムに流せます。

---

## 機能

| 機能 | 説明 |
|---|---|
| 🎵 サウンドボード | ボタンまたはキーボードショートカットで効果音を即再生 |
| 🎶 BGM プレイヤー | バックグラウンドで BGM を再生・一時停止・停止 |
| 🎤 マイク転送 | 自分のマイク音声と効果音を同時に相手へ送信 |
| 🎧 手元モニター | 送信している音を自分のヘッドホンでも確認できる |
| ⌨ ショートカットキー | ゲーム中でも反応。クリックしてキーを押すだけで割り当て・複数キーの同時押しにも対応 |
| ⚙ 自動起動 | Windows 起動時にバックグラウンドで待機（デフォルト: OFF） |
| 🔄 自動アップデート | 起動時に新バージョンを確認して通知 |

## 対応音声フォーマット

`WAV` `FLAC` `MP3` `OGG` — そのまま使用可能  
`MP4` `M4A` — ffmpeg がインストールされている場合に対応

---

## インストール（配布版）

1. [Releases](https://github.com/warasugitewara/Onga-Kun/releases) から `onga-kun-setup-vX.X.X.exe` をダウンロード
2. インストーラーを実行
3. [VB-Cable](https://vb-audio.com/Cable/) をインストール（無料）

> **MP4 / M4A を使いたい場合**  
> [ffmpeg](https://ffmpeg.org/download.html) を別途インストールしてください。  
> `winget install Gyan.FFmpeg` でも導入できます。WAV / FLAC / MP3 のみなら不要です。

---

## VB-Cable との連携方法

VB-Cable は「仮想マイク」として機能します。Onga-Kun から VB-Cable に音を送り、Discord 等ではその VB-Cable をマイクとして選択することで、効果音を相手に届けられます。

1. Onga-Kun の **出力先** を `CABLE Input (VB-Audio Virtual Cable)` に設定
2. Discord 等の**マイク**を `CABLE Output (VB-Audio Virtual Cable)` に設定
3. **🎤 マイク転送ボタン** を ON にすると、自分の声も一緒に送信される

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
├── main.py            # エントリポイント・ショートカットキー管理
├── ui.py              # GUI
├── audio_player.py    # 音声エンジン
├── mic_passthrough.py # マイク転送
├── startup.py         # Windows スタートアップ登録
├── updater.py         # 自動アップデート
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

