# 音ガくん (Onga-Kun)

Windows 向けのサウンドボード・BGM プレイヤーアプリです。  
VB-Cable と組み合わせて Discord やゲーム中にマイク経由で効果音・BGM を流すことができます。

## 必要なもの

| ソフトウェア | 用途 | 備考 |
|---|---|---|
| [Python 3.11+](https://www.python.org/) | 実行環境 | 開発時のみ必要 |
| [VLC](https://www.videolan.org/) | 音声出力エンジン | インストール必須 |
| [VB-Cable](https://vb-audio.com/Cable/) | 仮想オーディオデバイス | マイクルーティングに使用 |

## セットアップ（開発環境）

```bat
setup.bat
```

## ビルド (exe)

[Inno Setup 6](https://jrsoftware.org/isinfo.php) をインストールした上で：

```bat
build.bat
```

`installer\Output\onga-kun-setup-vX.X.X.exe` が生成されます。

## VB-Cable との連携方法

1. 音ガくんの出力先デバイスを **CABLE Input (VB-Audio Virtual Cable)** に設定
2. Discord 等のマイク入力を **CABLE Output (VB-Audio Virtual Cable)** に設定

## ライセンス

MIT

## 著者

- **warasugitewara** (https://github.com/warasugitewara) — 開発
- **sushi-m4a** (https://github.com/sushi-m4a) — アイデア・企画協力  
  Contact: chaco831miku@gmail.com
