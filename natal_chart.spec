# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from glob import glob

block_cipher = None


app = 'app.py'


added_files = [
    ('templates/*.html', 'templates'),
    ('static/*', 'static'),
    ('LICENSE', '.'),
]

sefstars = next(
    (
        p
        for p in Path('venv').glob(
            'lib/python*/site-packages/pyswisseph/sweph/sefstars.txt'
        )
    ),
    None,
)
if sefstars:
    added_files.append((str(sefstars), 'sweph'))


a = Analysis(
    [app],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'pyswisseph',
        'matplotlib.backends.backend_tkagg',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    name='NatalChart',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(Path('icons/icon.ico')) if Path('icons/icon.ico').exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NatalChart'
)

# For Mac, create app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='NatalChart.app',
        icon='icons/icon.icns',
        bundle_identifier='com.yourname.natalchart',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '1.0.0',
        },
    )
