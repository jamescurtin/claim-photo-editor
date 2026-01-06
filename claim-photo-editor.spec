# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Claim Photo Editor."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Get the source directory
src_dir = Path('src/claim_photo_editor')

# Include the resources directory (icon, etc.)
datas = []
resources_dir = src_dir / 'resources'
if resources_dir.exists():
    datas.append((str(resources_dir), 'claim_photo_editor/resources'))

# Collect all piexif data
piexif_datas, piexif_binaries, piexif_hiddenimports = collect_all('piexif')
datas.extend(piexif_datas)

# Collect PIL/Pillow submodules
pil_hiddenimports = collect_submodules('PIL')

a = Analysis(
    [str(src_dir / 'main.py')],
    pathex=[str(Path('src').absolute())],
    binaries=piexif_binaries,
    datas=datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PIL',
        'PIL.Image',
        'PIL.ImageOps',
        'PIL.ExifTags',
        'piexif',
        'piexif._exif',
        'piexif._webp',
        'reportlab',
        'reportlab.lib',
        'reportlab.lib.colors',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.lib.utils',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
    ] + piexif_hiddenimports + pil_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Claim Photo Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Claim Photo Editor',
)

# macOS app bundle
if sys.platform == 'darwin':
    # Use .icns icon if available (SVG not supported by PyInstaller)
    icon_path = src_dir / 'resources' / 'icon.icns'
    icon_file = str(icon_path) if icon_path.exists() else None

    app = BUNDLE(
        coll,
        name='Claim Photo Editor.app',
        icon=icon_file,
        bundle_identifier='com.jamescurtin.claim-photo-editor',
        info_plist={
            'CFBundleDisplayName': 'Claim Photo Editor',
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
        },
    )
