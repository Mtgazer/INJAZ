# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for INJAZ (إنجاز).
Builds a standalone onedir Windows distribution bundling PySide6, PyMuPDF,
OpenPyXL, Arabic UI components, and all brand runtime assets.
"""
import os
import sys

block_cipher = None

project_root = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(project_root, 'assets'), 'assets'),
]

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'pymupdf',
    'fitz',
    'openpyxl',
    'injaz',
    'injaz.main',
    'injaz.models',
    'injaz.paths',
    'injaz.engine',
    'injaz.pdf_extractor',
    'injaz.normalizer',
    'injaz.rules',
    'injaz.duplicates',
    'injaz.supplier_matcher',
    'injaz.xlsx_exporter',
    'injaz.csv_writer',
    'injaz.ui.main_window',
    'injaz.ui.theme',
    'injaz.ui.workers',
    'injaz.ui.models',
    'injaz.ui.components.header',
    'injaz.ui.components.dialogs',
    'injaz.ui.components.supplier_dialogs',
    'injaz.ui.pages.new_process_page',
    'injaz.ui.pages.review_page',
    'injaz.ui.pages.export_page',
    'injaz.verify_cli',
]

excludes = [
    'tkinter',
    'unittest',
    'pytest',
    'IPython',
    'jupyter',
    'matplotlib',
    'numpy',
    'scipy',
    'pandas',
]

binaries = []

a = Analysis(
    [os.path.join(project_root, 'injaz', '__main__.py')],
    pathex=[project_root],
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
)

# Exclude any third-party or Anaconda ICU DLLs (e.g. icudt73.dll)
# The application cleanly utilizes native Windows 10/11 system ICU support
a.binaries = [b for b in a.binaries if not os.path.basename(b[0]).lower().startswith('icu')]

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='INJAZ',
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
    icon=os.path.join(project_root, 'assets', 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='INJAZ',
)
