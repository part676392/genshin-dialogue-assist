# 検証結果 / Validation

検証日 / Date: **2026-09-30**

## 確認済み / Verified

- Windows 11 x64、Python 3.13.3、libVIIPER 0.8.1、usbip-win2 0.9.8.1。 / Windows 11 x64, Python 3.13.3, libVIIPER 0.8.1, usbip-win2 0.9.8.1.
- 同梱USBipインストーラーのSHA-256一致とWindows Authenticode署名Validを確認。通常のWindows管理者起動で導入。 / Verified pinned SHA-256 and a valid Authenticode signature; installed through standard Windows elevation.
- 仮想キーボードの接続・切断に成功。 / Virtual keyboard connection and removal succeeded.
- 専用のローカルテスト画面に12回のFを送信し、Windows Raw Inputで **押下12・解放12** を受信。受信元は新しいHIDデバイスのパス。 / Sent 12 F taps to an owned test window; Windows Raw Input received **12 down + 12 up** events from the new HID device.
- テストの送信開始間隔は **249.01〜250.82 ms**。原神の会話進行の最小時間を測った値ではありません。 / Probe dispatch intervals were **249.01–250.82 ms**. This is not a measurement of the game's minimum dialogue-advance time.
- 26件のテスト成功。以前報告された薄い履歴アイコン・短い字幕、会話終了、選択肢、画面遷移、別アプリへの切り替え、一時停止、キー解放失敗時の切断、旧入力への無断フォールバックがないことを確認。 / 26 tests passed, covering prior detection reports, boundaries, choices, focus isolation, pause, key-release failure cleanup, and no silent fallback.
- 非公開のゲーム画面テスト画像は配布物・Gitから除外。 / Private gameplay test fixtures are excluded from Git and distributions.
- 配布用EXEを管理者として起動し、UIの描画・正常終了に成功。起動前後で入力先・マウス座標・カーソル制限に変更なし。 / Packaged EXE launched with elevation, rendered its UI, and exited successfully. Foreground window, cursor position, and cursor confinement were unchanged on launch.

## 検証の限界 / Limits

この作業時点では原神が起動していなかったため、新しいUSB入力を実際のゲーム内会話へ送る検証は行っていません。回帰検出テストとWindowsの実入力テストを組み合わせた結果です。検出精度は日本語16:9の収集済み画面に対するもので、すべての会話・画面設定を網羅しません。

Genshin was not running during this work, so the new USB transport was not exercised in a live game dialogue. Evidence combines detector regression tests with real Windows input reception. Detection coverage is limited to collected Japanese 16:9 scenes, not every dialogue or display configuration.

ドライバーの導入ログは再起動を要求しました。仮想キーボードとRaw Inputは再起動前でも動作しましたが、初回導入後はWindowsの再起動を推奨します。自動再起動は行いません。

The driver installer reported that a restart was required. Virtual keyboard and Raw Input tests worked before restarting; a Windows restart is recommended after initial installation. No automatic restart is performed.

検証結果はアンチチートの許可、検知不能、BANリスク低下を示すものではありません。

These results do not establish anti-cheat approval, invisibility, or reduced account-ban risk.
