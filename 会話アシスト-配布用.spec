# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['auto_dialogue.py'],pathex=[],binaries=[('vendor/libVIIPER.dll','vendor')],
    datas=[('assets/history.png','assets'),('assets/eye.png','assets'),
           ('assets/choice.png','assets'),('assets/attention.wav','assets'),
           ('assets/dialogue-assist.ico','assets'),('vendor/USBip-0.9.8.1-x64.exe','vendor')],
    hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['tkinter','matplotlib','IPython','pytest','scipy','torch'],
    noarchive=False,optimize=0,
)
# Use Windows ICU; avoid a same-named, incompatible Poppler DLL from PATH.
a.binaries=[e for e in a.binaries if e[0].lower() not in ('icuuc.dll','icudt78.dll')]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='会話アシスト',
    debug=False,bootloader_ignore_signals=False,strip=False,upx=True,
    console=False,disable_windowed_traceback=False,runtime_tmpdir=None,
    uac_admin=True,icon=['assets/dialogue-assist.ico'])
