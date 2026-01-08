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
        # Unused Python packages
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        # Unused PySide6/Qt modules - saves ~23MB per architecture
        # PDF handling (reportlab is used instead)
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        # QML/Quick (declarative UI not used - app uses QtWidgets)
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQml',
        'PySide6.QtQmlModels',
        'PySide6.QtQmlMeta',
        'PySide6.QtQmlWorkerScript',
        # Network (requests library handles HTTP)
        'PySide6.QtNetwork',
        'PySide6.QtNetworkAuth',
        # Platform-specific / unused
        'PySide6.QtDBus',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtVirtualKeyboard',
        # Multimedia
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        # 3D
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DExtras',
        # Other unused modules
        'PySide6.QtBluetooth',
        'PySide6.QtCharts',
        'PySide6.QtConcurrent',
        'PySide6.QtDataVisualization',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtPrintSupport',
        'PySide6.QtRemoteObjects',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtScxml',
        'PySide6.QtTest',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtXml',
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
    strip=True,  # Strip debug symbols to reduce size
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch='arm64',  # ARM-only binary (Apple Silicon)
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,  # Strip debug symbols to reduce size
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
