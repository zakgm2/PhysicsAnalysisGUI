"""
loaders/tdt.py
---------------
TDT tank folder loading. TDT's own event markers (epocs) are populated
automatically via PhysicsLibrary's process_tdt_folder().
"""

import os

from PyQt6.QtWidgets import QFileDialog

import PhysicsLibrary as pl

from ..sidecar import load_markers_from_sidecar
from ..toasts import show_error, show_success


def open_folder(ctx):
    start_dir = ctx.last_dir or os.path.expanduser("~")
    path = QFileDialog.getExistingDirectory(ctx.win, "Open Data Folder", start_dir)
    if path:
        ctx.last_dir = path
        _load_folder(ctx, path)


def _load_folder(ctx, folder_path):
    from ..plotting import simple_plot

    try:
        fmt = pl.detect_format(folder_path)
    except Exception as e:
        show_error(ctx, str(e))
        return

    if fmt.name != "TDT":
        show_error(ctx, "Only TDT folders are supported via 'Open TDT Folder'.")
        return

    try:
        valid, msg = pl.validate_tdt_folder(folder_path)
        if not valid:
            show_error(ctx, f"TDT validation failed: {msg}")
            return
        result = pl.process_tdt_folder(folder_path)
    except Exception as e:
        show_error(ctx, str(e))
        return

    ctx.cache = {
        'source':      'TDT',
        'source_path': folder_path,
        'store':       os.path.basename(folder_path.rstrip('/\\')),
        'x':           result['x'],
        'raw':         result['raw'],
        'corr':        result['corr'],
        'fs':          result['fs'],
        'markers':     result.get('markers', []),
    }
    load_markers_from_sidecar(ctx)
    simple_plot(ctx)
    show_success(ctx, f"Folder: {ctx.cache['store']}")
