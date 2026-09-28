# -*- mode: python ; coding: utf-8 -*-
"""TubeLens tek dosya exe (onefile) olusturma.

Kullanim:
    pyinstaller tubelens.spec
Cikti:
    dist/TubeLens.exe  -> indir, cift tikla; panel acilir, tarayici acilir.
"""

from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("edge_tts") + collect_submodules("gtts") + [
    "mutagen",
    "imageio_ffmpeg",
    "certifi",
]

datas = [
    ("tubelens/data/product_catalog.json", "tubelens/data"),
    ("tubelens/assets/retro_bg.png", "tubelens/assets"),
]

binaries = []
try:
    import imageio_ffmpeg

    binaries = [(imageio_ffmpeg.get_ffmpeg_exe(), "imageio_ffmpeg")]
except Exception:
    pass

a = Analysis(
    ["tubelens_entry.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TubeLens",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="tubelens.ico",
)
