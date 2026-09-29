# 入力方式の調査 / Input transport research

調査日 / Reviewed: **2026-09-30**

## 結論 / Findings

原神・スターレイル・ゼンゼロをリモートで遊んでいる当事者の報告は複数あります。ただし「そのサービスで遊べる」「特定の仮想キーボードが公認」「マクロ入力のリスクが下がる」は別々の主張です。この調査で確認できたのは主に最初の点です。利用者数やBANの確率は算出できません。

There are multiple firsthand reports of remote play in Genshin Impact, Honkai: Star Rail, and Zenless Zone Zero. A working remote-play service, approval of a particular virtual keyboard, and reduced macro-related account risk are separate claims. This research mainly supports the first. It does not establish user counts or a ban probability.

## 当事者報告と公開実装 / Firsthand reports and public implementations

| 対象 / Subject | 確認したこと / Evidence | 限界 / Limits |
|---|---|---|
| [GameAwaiter](https://github.com/Guerra24/GameAwaiter) | Moonlight/SunshineでHoYoゲームを起動する専用OSS。READMEにGenshinImpact・StarRail・BH3の例。 / An open-source launcher specifically handles HoYo games with Moonlight/Sunshine, including examples for Genshin, HSR, and HI3. | 起動・UAC待ちへの対処。キーボードドライバーの承認を示さない。 / Addresses startup and UAC waits; not driver approval. |
| [原神・Steam Deck / Genshin on Steam Deck, 2024-05-12](https://www.reddit.com/r/MoonlightStreaming/comments/1cqfh4q/weird_hiccough_streaming_genshin_to_steam_deck/) | SunshineからMoonlightで起動し、最初の画面でPC側クリックが必要、その後は動くとの利用者報告。 / A user reports successful streaming after a host-side click on the first screen. | ホスト側入力ドライバーの版・種類は未特定。 / Exact host input driver/version unspecified. |
| [原神・Vita / Genshin on Vita, 2023-12-14](https://www.reddit.com/r/Genshin_Impact/comments/18i96st/) | Moonlightを使ったPCからのストリーミングとの説明。 / The post identifies Moonlight PC streaming. | コントローラーの例をキーボード実績に数えない。 / Not evidence for a specific keyboard transport. |
| [スターレイル・HoYoLAB / HSR community post, 2023-06-13](https://www.hoyolab.com/article/19305773) | Steam Deckでの遊び方としてMoonlight/Sunshineを勧めるコミュニティ投稿。 / A community post recommends Moonlight/Sunshine for Steam Deck play. | HoYoLAB上のユーザー投稿であり運営の回答ではない。 / User content, not an official HoYo response. |
| [スターレイル・Moonlight issue #1457](https://github.com/moonlight-stream/moonlight-android/issues/1457) | Android TV→Sunshine PCでHSRを試し、8BitDoコントローラーの一時的な入力停止を報告。 / HSR is used in an Android TV→Sunshine setup with intermittent controller input loss. | ゲームパッドの不具合報告。BAN報告ではない。 / Controller issue, not a ban report. |
| [ゼンゼロ・Apollo/Artemis, 2025-07-12](https://www.reddit.com/r/MoonlightStreaming/comments/1ly0s2u/) | 投稿者はApollo・Artemis・Tailscaleを使い、外出先からゼンゼロ等を遊ぶ使用感を説明。 / The author describes remote play including ZZZ using Apollo, Artemis, and Tailscale. | Sunshine派生環境。仮想キーボードの方式は不明。 / A Sunshine-derived setup; exact keyboard backend unknown. |
| [原神・Parsec, 2020-11](https://www.reddit.com/r/Genshin_Impact/comments/jp2azx/) | Windowsホスト→Linuxクライアントでキーボード・マウスでも遊べるという当事者コメント。 / A firsthand comment describes keyboard/mouse use from Linux to a Windows host. | 古い版の自己申告で、現在の実装や公認を示さない。 / An older self-report; not current implementation or approval evidence. |
| [原神・Steam Link, 2020-2021](https://www.reddit.com/r/Genshin_Impact/comments/j4po5x/) | NVIDIA ShieldのUSBキーボード・マウスで動作したというコメント。 / A comment describes USB keyboard/mouse play through NVIDIA Shield. | 入力ドライバーの同定はできない。 / Does not identify the host driver. |

この検索で、Sunshine/Moonlightによる通常の遠隔操作だけが原因と確認できるHoYoアカウント停止の事例は見つかりませんでした。「今まで一件もない」「今後も安全」とは結論づけていません。

This search did not find a causally verified HoYo ban attributable solely to ordinary Sunshine/Moonlight remote control. That is not a finding that no case has ever occurred or that future use is guaranteed safe.

## 入力実装の確認 / Input implementation checks

- [Sunshine libvirtualhid](https://github.com/LizardByte/libvirtualhid/blob/master/docs/platform-support.md): Windowsの仮想キーボード経路はライセンスが必要。新機能であり、古いMoonlight使用報告からこのドライバーが承認済みとは推定できません。 / The Windows virtual-keyboard path requires a license. Older Moonlight reports cannot validate this newer driver.
- [Parsec公式トラブルシューティング](https://support.parsec.app/hc/en-us/articles/32381827815188-Mouse-and-Keyboard-Isn-t-Working-Correctly-When-Connected): 管理者権限の違いが入力失敗の原因になることを説明。Virtual Mouseはカーソル表示のための機能で、仮想キーボードの公認根拠ではありません。 / Documents elevation-related input failures. Its Virtual Mouse feature concerns cursor availability, not approval of a virtual keyboard.
- [IbInputSimulator](https://github.com/Chaoses-Ib/IbInputSimulator): Genshin行のSendInput欄の「High」は高整合性権限の意味。他のドライバー欄の空白を、Logitech等の動作確認済みと解釈しません。 / The Genshin table's “High” entry refers to integrity level; blank entries for other backends are not compatibility confirmations.
- [NVIDIA Genshin FAQ](https://nvidia.custhelp.com/app/answers/detail/a_id/5300), [HSR 4.1 streaming announcement](https://blogs.nvidia.com/blog/geforce-now-thursday-screamer/), [ZZZ announcement](https://blogs.nvidia.com/blog/geforce-now-thursday-nier-franchise/): 対応クラウドサービスの実例ですが、ローカルで複製できる公認入力ドライバーの公開を意味しません。 / Examples of supported cloud services, not a published local driver approval list.

## v2の採用方式 / v2 implementation choice

無料で再配布でき、公開ソースとC APIがある [VIIPER v0.8.1](https://github.com/Alia5/VIIPER/releases/tag/v0.8.1) と、署名済み [usbip-win2 v0.9.8.1](https://github.com/vadimgrn/usbip-win2/releases/tag/v.0.9.8.1) を採用しました。アプリ内のUSB/IPサーバーとWindowsのUSB/IPクライアントをループバックでつなぎ、独立したキーボードを作ります。既存Sunshine環境の置き換え・更新は行いません。

v2 uses the freely redistributable, open-source VIIPER C API and the signed usbip-win2 driver. An in-process USB/IP server connects to the Windows USB/IP client over loopback and creates a separate keyboard. Existing Sunshine installations are not replaced or upgraded.

VID/PIDは上流の既定値を使います。ローカルにあるELECOMやLogitech機器の識別情報を複製せず、ドライバーや接続元を隠しません。この方式のWindows上の実動を検証しましたが、この組み合わせのHoYoによる公認、BANリスク低下、物理機器との識別不能性は確認していません。

The upstream default VID/PID is retained. The app does not clone a local ELECOM/Logitech device or hide its driver or connection origin. Windows operation was tested; HoYo approval, reduced account risk, and indistinguishability from physical hardware were not established.
