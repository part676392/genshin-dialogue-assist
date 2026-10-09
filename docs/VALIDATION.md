# 検証結果 / Validation

検証日 / Date: **2026-10-09**

## v3.1.0 ガードと資源管理 / Guards and resource lifecycle

- 47件中46件成功、実DLL再接続1件は同セッションの前段で5回成功済みのため省略。 / 46 of 47 tests passed; the unchanged real-DLL reconnect test had already passed five cycles earlier in the session.
- 遅い直前取得の拒否、一時停止時のUSB切断、USB未接続でも停止表示を維持、画面取得handleの一度だけの解放、30秒の状態記録周期、設定・ユーザー画像を残し古い専用tmpだけ片付けることを確認。 / Tests cover stale observations, USB disconnection on pause, paused status without USB, idempotent capture release, the 30-second status heartbeat, and cleanup that preserves settings and user pictures.
- 停止・再開UIと実USB接続の確認、容量整理、公開配布の結果はリリースノートに記載。 / Release notes record UI/USB lifecycle validation, artifact cleanup and public packaging.

## v3.0.1 画面取得の点滅・送信表示 / Capture flicker and dispatch display

- ユーザーが待機中の約0.5秒ごとの点滅を報告。アプリ終了とUSB切断後に「止まった」と回答。最新v3.0.0プロセスの送信記録は起動から0回であり、点滅をF送信と断定しない。 / The user reported roughly half-second flicker while waiting and confirmed it stopped after application shutdown. The latest process recorded zero F dispatches since launch; flicker is not treated as proof of key dispatch.
- mss 10.2.0のCAPTUREBLTをプロセス内で無効化。Windows設定やインストール済みライブラリのファイルは変更しない。関連報告: [python-mss #179](https://github.com/BoboTiG/python-mss/issues/179)。 / Disabled CAPTUREBLT in the process's pinned mss backend without changing Windows settings or installed package files.
- 修正後の実ゲーム画面取得10回、約5秒、全BitBltのROP=13369376（SRCCOPYのみ）。USBを作らずF送信0。ユーザーが「チカチカは出なかった」と確認。取得時間57.88～76.56ms。長時間・全画面設定の無点滅を保証する試験ではない。 / Ten live captures over roughly five seconds used SRCCOPY exclusively, with no USB backend or F input. The user confirmed no flicker during that bounded check; capture times were 57.88–76.56 ms. This is not an exhaustive long-duration or display-mode validation.
- 回帰41件中40件成功、実DLL再接続1件skip（同セッションで変更前に5回成功済み）。UIの送信停止表示・累計・入力前描画・停止操作時の送信拒否を確認。 / 40 of 41 tests passed; the unchanged real-DLL reconnect test was skipped after passing five cycles earlier. Checks cover explicit waiting indication, counters, pre-input painting and dispatch rejection when paused during UI update.

## v3.0.0 入力間隔UI・待機中の送信禁止 / Timing UI and waiting gate

- 「一定」の350～500msスライダー、「ランダム」の送信ごとの350～500ms選択、設定保存・読戻しを実UIで確認。350/425/500msとモード切り替えを検証し、テストのF送信数は0。 / The real UI verified fixed slider values 350/425/500 ms, per-dispatch random intervals within 350–500 ms, mode switching, settings persistence and restoration, with zero test key inputs.
- 37テスト中36件成功。実DLL再接続は同セッションの前段で5回成功しており、変更のない同試験を最終実行で繰り返さない。 / 36 of 37 tests passed; the unchanged real-DLL reconnection case had already passed five cycles earlier in the session and was not repeated in the final run.
- 待機状態に誤ってFアクションが混じるケースでも、20回の検査でUSB送信0回。送信直前に会話が終了した場合も送信を取り消す。 / Even an inconsistent F action while waiting produces zero USB dispatches over 20 checks. Dialogue ending during the pre-input check also cancels dispatch.
- 送信の早まりを防ぐ締切を追加し、画像処理時間が変わっても選んだ間隔より早い再送信を拒否。 / An input deadline rejects dispatches earlier than the chosen interval even when image-processing time changes.
- 実仮想USBキーボードからWindows Raw InputへF押下3・解放3を受信。2区間は249.87/249.36ms。予定12回の途中で前面が変わったため、ガードで以後の送信を停止した。 / Windows Raw Input received 3 F down and 3 F up events from the real virtual USB keyboard, with 249.87/249.36 ms intervals. The bounded 12-tap probe stopped early when foreground changed, so this is a three-pair reception check rather than a completed 12-tap run.

## v2.0.2 会話判定・処理時間の修正 / Detection and timing fix

2560×1440の実画面で、非表示アイコンの半透明の外周が背景に応じて変わり、従来の比較値が0.929～0.940へ下がって会話を取りこぼす現象を再現しました。外周を除いたアイコンの中身は0.954で安定していたため、履歴アイコンと同じく中身を比較します。必要な領域だけ縮小し、入力直前は会話コントロールを再確認して、選択肢の探索を重複させません。通常会話→選択肢はどちらもFで進めるため、有効な切り替わりで入力を拒否しません。

On live 2560×1440 frames, the hide-dialogue icon's translucent border varied with the scene, lowering the previous score to 0.929–0.940 and missing dialogue. Its inner glyph remained stable at 0.954. v2.0.2 matches the glyph and resizes only relevant regions. The immediate pre-input check still verifies dialogue controls, but avoids a duplicate choice search and accepts caption-to-choice transitions because both use F.

- 同じ実画面12枚の会話認識は0/12→12/12。判定処理の中央値は104.55→66.86ms（同じPC・同じ画像、初回比較）。 / Recognition on the same 12 live frames improved from 0/12 to 12/12. Median detector time changed from 104.55 to 66.86 ms in the initial comparison on the same PC and frames.
- 1440pで明暗3種類のアイコン外周、通常会話、選択肢、メニュー、探索、コントロールのない演出を検証。 / Regression coverage includes three border brightness levels at 1440p, dialogue, choices, menu, exploration, and cinematics without dialogue controls.
- 回帰テスト33件中32件成功、実DLL再接続の1件は別の実行で5回成功。 / 32 of 33 regression tests passed in the final run; the real-DLL reconnection test passed five cycles in a separate earlier run.
- 目標250ms・押下25ms・仮想USB HID入力を維持。実際の送信周期は画面取得とPC負荷にも依存します。 / The 250 ms target, 25 ms hold, and virtual USB HID transport are retained. Actual dispatch intervals also depend on capture time and PC load.

この節はv2.0.2のローカル本体検証です。全会話での台詞進行の最短時間を証明するものではありません。 / This section records local v2.0.2 validation and does not establish a minimum dialogue-advance time across all scenes.

## v2.0.1 再接続修正 / Reconnection fix

v2.0.0で同じプロセスの接続→切断→接続を試すと、1回目だけ成功し、2・3回目は「仮想USBバスを作成できませんでした」となる現象を再現しました。libVIIPER 0.8.1のCloseUSBServerはバスの割り当てを即時に解放しないため、RemoveUSBBusを明示的に呼ぶよう修正しました。

In v2.0.0, a same-process connect/close/connect sequence succeeded once and failed on the second and third attempts with “Cannot create virtual USB bus.” Because libVIIPER 0.8.1 CloseUSBServer does not immediately release bus allocations, v2.0.1 explicitly calls RemoveUSBBus during teardown.

- 同じ実DLL・同じプロセスで5回の接続・切断に成功。 / Five consecutive connect/close cycles passed using the real DLL in one process.
- 実UIのUSB設定ボタンから3回の再接続に成功。キー送信数は0。 / Three reconnections through the actual UI setup button passed with zero key inputs.
- 30件のテスト成功（実ドライバーの再接続テスト1件を含む）。 / 30 tests passed, including one real-driver reconnection test.
- 接続途中の失敗でも作成済みのバスを解放し、作成できていないバスを削除しないことを確認。 / Failed setup releases its owned bus without deleting a bus it did not create.

再現コマンド / Reproduction checks:

```powershell
$env:GENSHIN_TEST_USB='1'
.\.venv\Scripts\python.exe -m unittest test_hid_input -v
.\.venv\Scripts\python.exe tools/probe_usb_setup.py setup-result.json
```

実ドライバーテストは一時的な仮想キーボードの接続だけを行い、Fは送信しません。ゲーム画像の回帰テストには別途非公開fixturesが必要です。

The real-driver checks connect temporary virtual keyboards but send no F input. Gameplay-image regression tests additionally require the private fixtures.

## v2.0.0で確認した範囲 / Original v2.0.0 verification

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
