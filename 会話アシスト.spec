# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['auto_dialogue.py'],
    pathex=[],
    binaries=[('vendor/libVIIPER.dll', 'vendor')],
    datas=[('assets/history.png', 'assets'), ('assets/eye.png', 'assets'), ('assets/choice.png', 'assets'), ('assets/attention.wav', 'assets'), ('assets/dialogue-assist.ico', 'assets'), ('vendor/USBip-0.9.8.1-x64.exe', 'vendor')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'pytest', 'scipy', 'torch'],
    noarchive=False,
    optimize=0,
)
# Qt 6.11 uses Windows' unversioned ICU exports. A developer-tool PATH may
# contain Poppler's same-named ICU with versioned exports; never bundle it.
a.binaries = [entry for entry in a.binaries
              if entry[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='会話アシスト',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon=['assets/dialogue-assist.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='会話アシスト',
)
