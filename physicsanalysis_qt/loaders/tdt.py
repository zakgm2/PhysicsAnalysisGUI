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
from ..analysis.splice import load_splice_from_sidecar
from ..plot_signal import refresh_plot_signal_options
from ..toasts import show_error, show_success, show_window_toast

# Colors for the raw per-wavelength channels in the Plot dropdown/legend —
# keyed by the 'channels' entry key PhysicsLibrary's process_tdt_folder()
# reports, so a recording with a differently-named stream (any wavelength,
# any experimental setup) still gets a sensible, consistent color; only
# the two roles that function ever emits need an entry here.
_CHANNEL_COLORS = {
    "main_driver": "#2E7D32",  # green — conventional for the probe/signal channel
    "isosbestic":  "#7B1FA2",  # purple — conventional for the isosbestic control
}


def _build_signal_options(result):
    """Plot-option choices for the toolbar's "Plot:" dropdown: the
    computed normalized trace plus whatever raw per-wavelength channels
    this recording's process_tdt_folder() call found. Not hardcoded to
    exactly "Normalized/Isosbestic/Main Driver" — a block with no
    isosbestic reference stream just won't have that key, and any future
    channel role PhysicsLibrary reports shows up automatically with a
    fallback color."""
    options = {
        "normalized": {"label": "Normalized (dF/F)", "y": result["corr"], "color": "blue"},
    }
    for ch in result.get("channels", []):
        options[ch["key"]] = {
            "label": ch["label"],
            "y":     ch["y"],
            "color": _CHANNEL_COLORS.get(ch["key"], "#555555"),
        }
    return options


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
        # A stale splice from whatever was loaded before this must not
        # carry over — Open (unlike Reload, which already clears this)
        # can load an entirely different folder.
        ctx.original_cache = None
        ctx._active_splice = None
        ctx._data_generation += 1
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
            'signals':     _build_signal_options(result),
        }
        ctx.plot_signal = "normalized"  # reset — a prior dataset's pick may not exist here
        load_markers_from_sidecar(ctx)
        load_splice_from_sidecar(ctx)
        refresh_plot_signal_options(ctx)
        simple_plot(ctx)
        show_success(ctx, f"Folder: {ctx.cache['store']}")

    def _on_error(msg):
        show_error(ctx, msg)

    if ctx.settings.get("background_loading"):
        show_window_toast(ctx, "Loading TDT folder…")
    run_in_background(ctx, _work, _on_success, _on_error)
