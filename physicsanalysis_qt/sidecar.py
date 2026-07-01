"""
sidecar.py
----------
Marker persistence: a `.markers.json` file saved next to the loaded
data file/folder.
"""

import json
import os

from .toasts import show_error, show_window_toast


def sidecar_path(ctx):
    if ctx.cache is None or not ctx.cache.get('source_path'):
        return None
    return ctx.cache['source_path'] + ".markers.json"


def save_markers(ctx):
    if ctx.cache is None:
        return
    path = sidecar_path(ctx)
    if not path:
        show_error(ctx, "No source file/folder path to save markers next to.")
        return
    try:
        with open(path, 'w') as f:
            json.dump(ctx.cache['markers'], f, indent=2)
        show_window_toast(ctx, f"Markers saved -> {os.path.basename(path)}")
    except Exception as e:
        show_error(ctx, f"Could not save markers: {e}")


def load_markers_from_sidecar(ctx):
    """Overwrite cache['markers'] from the sidecar if one exists; otherwise
    leave whatever markers the loader already populated (e.g. TDT epoc
    events or Oxysoft dataset events) untouched."""
    path = sidecar_path(ctx)
    if path and os.path.exists(path):
        try:
            with open(path, 'r') as f:
                ctx.cache['markers'] = json.load(f)
            show_window_toast(ctx, f"Markers restored ({len(ctx.cache['markers'])})")
        except Exception as e:
            show_error(ctx, f"Could not load markers: {e}")
