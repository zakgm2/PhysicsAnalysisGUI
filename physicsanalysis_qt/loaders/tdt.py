"""
loaders/tdt.py
---------------
TDT tank folder loading. TDT's own event markers (epocs) are populated
automatically via PhysicsLibrary's process_tdt_folder().
"""

import os

from PyQt6.QtWidgets import QFileDialog

import PhysicsLibrary as pl

from ..background import run_in_background
from ..sidecar import load_markers_from_sidecar
from ..toasts import show_error, show_success, show_window_toast


def open_folder(ctx):
    start_dir = ctx.last_dir or ctx.settings["default_folder"]
    path = QFileDialog.getExistingDirectory(ctx.win, "Open Data Folder", start_dir)
    if path:
        ctx.last_dir = path
        _load_folder(ctx, path)


def reload_folder(ctx, folder_path):
    """Re-run the load for a folder already on disk — no file dialog,
    used by the toolbar's Reload button to re-read the currently loaded
    TDT folder from scratch instead of asking the user to pick it again."""
    _load_folder(ctx, folder_path)


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

    def _work():
        valid, msg = pl.validate_tdt_folder(folder_path)
        if not valid:
            raise ValueError(f"TDT validation failed: {msg}")
        return pl.process_tdt_folder(folder_path)

    def _on_success(result):
        ctx.cache = {
            'source':      'TDT',
            'source_path': folder_path,
            'store':       os.path.basename(folder_path.rstrip('/\\')),
            'x':           result['x'],
            'raw':         result['raw'],
            'corr':        result['corr'],
            'fs':          result['fs'],
            'detected_markers': result.get('markers', []),
            'markers':     [],
        }
        load_markers_from_sidecar(ctx)
        simple_plot(ctx)
        show_success(ctx, f"Folder: {ctx.cache['store']}")

    def _on_error(msg):
        show_error(ctx, msg)

    if ctx.settings.get("background_loading"):
        show_window_toast(ctx, "Loading TDT folder…")
    run_in_background(ctx, _work, _on_success, _on_error)
