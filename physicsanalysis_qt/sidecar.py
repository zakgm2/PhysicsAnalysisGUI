"""
sidecar.py
----------
Marker persistence: a `.markers.json` file saved next to the loaded
data file/folder.
"""

import json
import os

from .toasts import show_error, show_window_toast


def _legacy_sidecar_path(ctx):
    """Pre-JSON-saves-folder location: a sibling file next to the raw
    data folder/file, e.g. <FolderPath>.markers.json. Kept read-only for
    loading sidecars saved before markers moved into a JSON saves/
    subfolder, so old studies don't lose their saved markers."""
    if ctx.cache is None or not ctx.cache.get('source_path'):
        return None
    return ctx.cache['source_path'] + ".markers.json"


def sidecar_path(ctx):
    if ctx.cache is None or not ctx.cache.get('source_path'):
        return None
    source = ctx.cache['source_path']
    if os.path.isdir(source):
        json_dir = os.path.join(source, "JSON saves")
        return os.path.join(json_dir, "markers.json")
    json_dir = os.path.join(os.path.dirname(source), "JSON saves")
    return os.path.join(json_dir, os.path.basename(source) + ".markers.json")


def save_markers(ctx):
    if ctx.cache is None:
        return
    path = sidecar_path(ctx)
    if not path:
        show_error(ctx, "No source file/folder path to save markers next to.")
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(ctx.cache['markers'], f, indent=2)
        show_window_toast(ctx, f"Markers saved -> JSON saves/{os.path.basename(path)}")
    except Exception as e:
        show_error(ctx, f"Could not save markers: {e}")


def clear_json_saves(ctx):
    """Deletes every file inside the JSON saves/ folder (not the folder
    itself) — used by Undo All Changes so a previously-saved sidecar
    doesn't get silently reloaded right back after the undo."""
    path = sidecar_path(ctx)
    if not path:
        return
    json_dir = os.path.dirname(path)
    if not os.path.isdir(json_dir):
        return
    for name in os.listdir(json_dir):
        entry = os.path.join(json_dir, name)
        if os.path.isfile(entry):
            try:
                os.remove(entry)
            except OSError as e:
                show_error(ctx, f"Could not clear {name}: {e}")


def load_markers_from_sidecar(ctx):
    """Overwrite cache['markers'] from the sidecar if one exists; otherwise
    leave whatever markers the loader already populated (e.g. TDT epoc
    events or Oxysoft dataset events) untouched."""
    path = sidecar_path(ctx)
    if not path or not os.path.exists(path):
        path = _legacy_sidecar_path(ctx)  # fall back to pre-JSON-saves-folder location
    if path and os.path.exists(path):
        try:
            with open(path, 'r') as f:
                ctx.cache['markers'] = json.load(f)
            show_window_toast(ctx, f"Markers restored ({len(ctx.cache['markers'])})")
        except Exception as e:
            show_error(ctx, f"Could not load markers: {e}")
