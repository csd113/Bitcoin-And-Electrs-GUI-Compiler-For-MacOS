# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['compile_bitcoind_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('image.icns', '.'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'requests',
        'multiprocessing',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'pytest',
        'IPython',
        'jupyter',
        'PIL',
        'test',
    ],
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
    optimize=2,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Bitcoin Electrs Compiler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    icon='image.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='Bitcoin Electrs Compiler',
)

app = BUNDLE(
    coll,
    name='Bitcoin Electrs Compiler.app',
    icon='image.icns',
    bundle_identifier='com.bitcoin.electrs.compiler',
)
