# 原神 会話アシスト / Genshin Dialogue Assist

日本語版の原神の会話をローカルの画像処理で検出し、会話中だけ **F** を送るWindows用アプリです。AI・APIキー・Pythonのインストールは不要です。

A Windows desktop app that detects dialogue in the Japanese Genshin Impact UI using local image processing, then sends **F** while dialogue is visible. The packaged app needs no AI service, API key, or Python installation.

## ダウンロード / Download

[Releases](https://github.com/part676392/genshin-dialogue-assist/releases) からWindows x64用ZIPを取得し、**すべて展開**して `会話アシスト.exe` を起動します。原神を前面にすると自動検出が始まります。

Download the Windows x64 ZIP from [Releases](https://github.com/part676392/genshin-dialogue-assist/releases), **extract all files**, and run `会話アシスト.exe`. Bring Genshin Impact to the foreground to enable detection.

| 操作 / Action | キー / Key |
|---|---|
| 一時停止・再開 / Pause or resume | F8 |
| 終了 / Quit | F9 |
| 会話・認識した選択肢を進める / Advance detected dialogue and choices | F, 250 ms interval |

会話終了・別アプリへの切り替え・最小化で入力を止めます。マウスを動かしたり、カーソルの範囲や表示を変更したりしません。画面の進行が30秒または60秒止まると、一度だけ通知できます。

Input stops when dialogue ends, another app becomes active, or the game is minimized. The app does not move, confine, or hide the mouse cursor. An optional one-shot alert reports 30 or 60 seconds without progress.

## 対応範囲 / Scope

- Windows x64、16:9、日本語版の通常会話UI。/ Windows x64, 16:9, standard Japanese dialogue UI.
- 選択肢の内容を理解せず、Fで決定します。/ Choices are confirmed with F; their meaning is not interpreted.
- スキップ不可の演出を強制終了する機能ではありません。/ Unskippable scenes remain unskippable.
- 会話画面を外部へ送信・保存しません。/ Game frames are neither uploaded nor saved.
- このプロジェクトはHoYoverseの公式・公認ソフトではありません。特定入力方式のBANリスク低下や不可検知性を保証しません。/ This is an independent, unofficial project. It makes no claim of anti-cheat invisibility or reduced account-ban risk.

## v1 / Original version

`v1.0.0` は既存の `2026.09.28.4` の公開保存版です。Windowsの `SendInput` を使用し、管理者として動くゲームへ送るためWindowsの管理者確認が表示されます。

`v1.0.0` archives the original `2026.09.28.4` application. It uses Windows `SendInput`; Windows requests administrator permission to match an elevated game.

## 開発 / Development

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist 会話アシスト-配布用.spec
```

実際のプレイヤー画面を含む回帰テスト画像は公開しません。所有している画像で検証する場合は `GENSHIN_TEST_FIXTURES` に画像フォルダーを指定してください。画像なしでも公開の単体テストを実行できます。

Private gameplay regression screenshots are excluded from the repository. To run those tests with your own fixtures, set `GENSHIN_TEST_FIXTURES` to the fixture directory. Public unit tests can run without those screenshots.

設定と状態は `%LOCALAPPDATA%\GenshinDialogue` に保存されます。公開ZIPへ個人設定を同梱しないでください。

Settings and status live in `%LOCALAPPDATA%\GenshinDialogue`. Do not include your personal settings in redistributed ZIPs.

## ライセンス / License

アプリのコードはGPL-3.0です。依存ソフト・ゲームのUI素材の権利はそれぞれの権利者に帰属します。[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照してください。

Application code is licensed under GPL-3.0. Dependencies and game UI material retain their respective licenses and ownership. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
