# 第三者のソフト・素材 / Third-party software and materials

アプリのソースは同じリリースのGitタグから取得できます。ビルド手順はREADMEを参照してください。下記は元の配布元・ライセンスへの参照です。

Corresponding application source is available from the Git tag matching each release. Build instructions are in README. Upstream source and license references follow.

| Component | License / Source |
|---|---|
| libVIIPER 0.8.1 | GPL-3.0; https://github.com/Alia5/VIIPER/tree/v0.8.1 |
| usbip-win2 0.9.8.1 | BSD-2-Clause; https://github.com/vadimgrn/usbip-win2/tree/v.0.9.8.1 |
| PySide6 / Qt 6 | LGPL-3.0 / GPL-3.0 / Qt commercial options; https://code.qt.io/pyside/pyside-setup.git/ ; https://code.qt.io/qt/ |
| PySide6-Fluent-Widgets | GPL-3.0; https://github.com/zhiyiYo/PyQt-Fluent-Widgets |
| PySideSix-Frameless-Window | LGPL-3.0; https://github.com/zhiyiYo/PyQt-Frameless-Window |
| OpenCV | Apache-2.0; https://github.com/opencv/opencv ; wheels: https://github.com/opencv/opencv-python |
| NumPy | BSD-3-Clause; https://github.com/numpy/numpy |
| Pillow | HPND; https://github.com/python-pillow/Pillow |
| MSS | MIT; https://github.com/BoboTiG/python-mss |
| PyInstaller bootloader | GPL-2.0-or-later with the bootloader exception; https://github.com/pyinstaller/pyinstaller |
| Python | PSF license; https://github.com/python/cpython |

`assets/history.png`, `eye.png`, `choice.png` は検出用の小さなゲームUIテンプレートです。原神の商標・ゲーム素材はHoYoverse等の権利者に帰属し、アプリのGPLライセンスを適用するものではありません。アプリの図柄はQtのベクター描画です。

`assets/history.png`, `eye.png`, and `choice.png` are small game UI templates used for detection. Genshin Impact trademarks and game materials belong to their respective owners, including HoYoverse, and are not relicensed under the application's GPL. App illustrations are drawn with Qt vector primitives.

依存パッケージのライセンス本文は `licenses/` に同梱しています。配布EXEのソースは各タグから取得し、READMEの手順で変更・再ビルドできます。GPL/LGPL部品の改変やデバッグのためのリバースエンジニアリングを禁止しません。Qtの商用ライセンスは取得していません。オープンソースのライセンス選択肢を使用します。

License texts are included in `licenses/`. Application source is available at each release tag and can be modified and rebuilt using README instructions. Reverse engineering for modifications/debugging of GPL/LGPL components is not prohibited. No Qt commercial license is claimed; the open-source licensing options are used.

## 対応するソース / Corresponding sources

リリースには上流未改変のVIIPER・usbip-win2・Fluent Widgets・Frameless Windowのソースをまとめた `third-party-sources.zip` も置きます。Qt/PySideの対応する6.11.2ソースは以下の上流サーバーから取得できます。アプリのビルドに使ったバージョンは `requirements.txt` に固定しています。

Releases also provide `third-party-sources.zip` with unmodified VIIPER, usbip-win2, Fluent Widgets, and Frameless Window sources. Corresponding Qt/PySide 6.11.2 sources are available from the upstream servers below. Build versions are pinned in `requirements.txt`.

- [PySide / Shiboken 6.11.2](https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.11.2)
- [PySide / Shiboken source archives / ソースアーカイブ](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/)
- [Qt Base 6.11.2](https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v6.11.2)
- [Qt Declarative 6.11.2](https://code.qt.io/cgit/qt/qtdeclarative.git/tree/?h=v6.11.2)
- [Qt SVG 6.11.2](https://code.qt.io/cgit/qt/qtsvg.git/tree/?h=v6.11.2)
- [Qt PDF / WebEngine 6.11.2](https://code.qt.io/cgit/qt/qtwebengine.git/tree/?h=v6.11.2)
- [Qt Virtual Keyboard 6.11.2](https://code.qt.io/cgit/qt/qtvirtualkeyboard.git/tree/?h=v6.11.2)
- [Qt source archives / ソースアーカイブ](https://download.qt.io/archive/qt/6.11/6.11.2/single/)

Qt Virtual KeyboardはQtの画面入力プラグインとしてバンドルされる依存物で、このアプリのUSB HID入力実装ではありません。

Qt Virtual Keyboard is bundled as a Qt platform input dependency; it is not the USB HID input backend implemented by this app.
