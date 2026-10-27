# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ('cloned_voices.json', '.'),
]
binaries = []
hiddenimports = [
    'customtkinter',
    'tkinterdnd2',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'cv2',
    'pygame',
    'pydub',
    'srt',
    'edge_tts',
    'faster_whisper',
    'ctranslate2',
    'requests',
    'urllib3',
    'yt_dlp',
    'deep_translator',
    'services',
    'models',
    'utils',
    'ui_v_PyQt6',
    'ui',
    'config',
]

# Collect assets, dynamic libs, and submodules for critical packages
for pkg in ['customtkinter', 'tkinterdnd2', 'faster_whisper', 'ctranslate2', 'edge_tts', 'yt_dlp', 'deep_translator']:
    try:
        d, b, h = collect_all(pkg)
        datas.extend(d)
        binaries.extend(b)
        hiddenimports.extend(h)
    except Exception as e:
        print(f"Warning collecting {pkg}: {e}")

# Exclude massive unrelated packages to drastically reduce build time and file size
excludes = [
    'PySide6',
    'PySide6_Essentials',
    'PySide6_Addons',
    'PySide6_Pdf',
    'PySide6_WebEngine',
    'shiboken6',
    'kivy',
    'Kivy',
    'kivy_deps',
    'gradio',
    'gradio_client',
    'fastapi',
    'uvicorn',
    'scipy',
    'pandas',
    'matplotlib',
    'pytest',
    'openpyxl',
    'docx2pdf',
    'pypdf',
    'PyMuPDF',
    'fitz',
    'buildozer',
    'tensorboardX',
    'IPython',
    'jupyter',
    'notebook',
    'sphinx',
]

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 1. Standalone Folder (onedir) - High Performance & Instant Startup
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI_Khmer_Movie_Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_dir,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AI_Khmer_Movie_Studio'
)

# 2. Single Portable Executable (onefile) - Easy Sharing as a single file
exe_single = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AI_Khmer_Movie_Studio_Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
