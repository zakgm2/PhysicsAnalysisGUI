# PhysicsAnalysis.spec
# ---------------------
# PyInstaller build spec for the PyQt6 desktop app, onefile mode — a
# single executable instead of a folder of DLLs/data files, so CI can
# upload/attach it directly with no zip step. Trade-off: onefile
# self-extracts to a temp dir on every launch, adding startup latency on
# top of matplotlib/pyqtgraph/vispy's own import cost.
#
# vispy has no maintained PyInstaller hook (confirmed: vispy/vispy#1643) —
# it resolves its .glsl shader files and font data relative to
# site-packages at runtime, which doesn't exist in a frozen build's temp
# extraction dir, so those are collected explicitly below.
#
# sentence-transformers/torch/transformers are excluded on purpose: they're
# only reachable via one lazy import inside PhysicsLibrary's Text Field
# Study embedding feature, but PyInstaller's static scanner finds
# function-local imports too and would otherwise bundle the whole
# torch/transformers tree (hundreds of MB-1GB+) for a feature most builds
# of this app will never touch. That one function now catches the
# resulting ImportError and tells the user to `pip install
# sentence-transformers` if they want it — see PhysicsLibrary's
# text_field_study.py.
#
# Run with: pyinstaller PhysicsAnalysis.spec
#
# pathex: only needed on a machine where PhysicsLibrary is editable-
# installed via a PEP 660 import-hook finder (not a plain sys.path
# entry) — PyInstaller's static analysis can't follow that redirect, so
# it needs the sibling repo's actual source directory to find/bundle it
# at all. CI installs PhysicsLibrary as a normal (non-editable) package
# from PyPI, where PyInstaller finds it via site-packages with no help
# needed, so this only adds the local dev checkout's path when it's
# actually present on the machine running this build.
#
# icon: .ico is Windows-only; PyInstaller wants .icns on macOS (a bare
# .ico there is silently ignored). Picked per-platform below; add
# physicsanalysis_qt/assets/icon.icns to get a real icon on macOS builds.

import os
import sys

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

vispy_datas = collect_data_files('vispy', subdir='glsl')
vispy_datas += collect_data_files('vispy', subdir=os.path.join('io', '_data'))

_local_physicslibrary = r'C:\Users\zakgm\Desktop\Github\PhysicsLibrary'
_pathex = [_local_physicslibrary] if os.path.isdir(_local_physicslibrary) else []

if sys.platform == 'darwin':
    _icon_path = 'physicsanalysis_qt/assets/icon.icns'
    _icon = _icon_path if os.path.isfile(_icon_path) else None
else:
    _icon = 'physicsanalysis_qt/assets/icon.ico'

a = Analysis(
    ['run_qt.pyw'],
    pathex=_pathex,
    binaries=[],
    datas=[
        ('physicsanalysis_qt/assets', 'physicsanalysis_qt/assets'),
    ] + vispy_datas,
    # vispy.app.use_app("pyqt6") loads its backend module by string name
    # at runtime (vispy.app.application._use), which PyInstaller's static
    # analysis can't see — has to be listed explicitly.
    hiddenimports=['vispy.app.backends._pyqt6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['sentence_transformers', 'torch', 'transformers'],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PhysicsAnalysis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=_icon,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='PhysicsAnalysis.app',
        icon=_icon,
        bundle_identifier='com.zakgm2.physicsanalysis',
    )
