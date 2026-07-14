"""
analysis/splice.py
---------------------
GUI orchestration for non-destructive time-range edits — the actual
array/marker math (trim vs. cut-and-stitch) lives in PhysicsLibrary's
splice.py (splice_keep_inside / splice_cut_out); this module is just
the dialogs, click-capture wiring, and sidecar persistence tied to
ctx.cache.

Every analysis tool in the app (FFT, PETH, Curve Fit, Event PETH, Peak
Finder, markers) reads straight from ctx.cache, so swapping ctx.cache
for an edited copy makes them all "just work" on it with no changes to
any of them. The full original recording is kept in ctx.original_cache
and can be restored at any time.

Flow: pick a mode first (small dialog, no time fields), then click two
points directly on the plot — same click-to-anchor pattern as Curve
Fit. No typed start/end numbers anywhere in this path.

TDT-only for now: Oxysoft/Generic sources have a different cache shape
(o2hb/hhb/thb arrays, y_columns dict) this doesn't handle yet.
"""

import json
import os

import PhysicsLibrary as pl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup,
)

from ..toasts import show_error, show_window_toast

MODE_KEEP_INSIDE = "keep_inside"
MODE_CUT_OUT = "cut_out"


class _SpliceModePickerDialog(QDialog):
    """Just the mode choice — no time fields. Closing this (Start
    Clicking) is what hands control back to the plot for the two-click
    point selection."""

    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.mode = None
        self.setWindowTitle("Splice Recording")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Works on a copy — the original recording is kept untouched and\n"
            "restorable at any time. Choose what to do, then click two points\n"
            "on the graph to mark the range."
        ))

        self.rb_keep = QRadioButton("Keep only this range")
        self.rb_keep.setChecked(True)
        self.rb_cut = QRadioButton("Cut out this range (remove an artifact, stitch the rest together)")
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.rb_keep)
        mode_group.addButton(self.rb_cut)
        layout.addWidget(self.rb_keep)
        layout.addWidget(self.rb_cut)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Start Clicking…")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _accept(self):
        self.mode = MODE_CUT_OUT if self.rb_cut.isChecked() else MODE_KEEP_INSIDE
        self.accept()


def start_splice_flow(ctx):
    """Entry point for both the sidebar's scissors icon and picking
    'Splice' from the plot-type combo: asks the mode first, then hands
    control to the plot for two clicks (see interaction.py's on_release
    Splice-mode handling, which calls apply_splice_at_points below once
    it has both points)."""
    if ctx.cache is None or ctx.cache.get('source') != 'TDT':
        show_error(ctx, "Splicing is only available for TDT data.")
        return False

    dlg = _SpliceModePickerDialog(ctx.win, ctx)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return False

    ctx._pending_splice_mode = dlg.mode
    ctx.slope_clicks.clear()
    show_window_toast(ctx, "Click two points on the graph to mark the range")
    return True


def _apply_splice(ctx, mode, start, end, announce=True):
    """Core apply, shared by the click-driven flow and sidecar reload —
    records the operation on ctx._active_splice so it can be written out
    by save_splice()."""
    from ..plotting import simple_plot

    source_cache = ctx.original_cache if ctx.original_cache is not None else ctx.cache
    splice_fn = pl.splice_cut_out if mode == MODE_CUT_OUT else pl.splice_keep_inside

    result = splice_fn(
        source_cache['x'], source_cache['raw'], source_cache['corr'],
        source_cache['markers'], source_cache.get('detected_markers', []),
        start, end,
    )
    if result is None:
        if announce:
            msg = ("Can't cut that range — need usable signal on both sides of the cut."
                   if mode == MODE_CUT_OUT else
                   "That range doesn't contain enough samples to analyze.")
            show_error(ctx, msg)
        return False

    spliced = dict(source_cache)
    spliced['x'] = result['x']
    spliced['raw'] = result['raw']
    spliced['corr'] = result['corr']
    spliced['markers'] = result['markers']
    spliced['detected_markers'] = result['detected_markers']
    tag = "cut" if mode == MODE_CUT_OUT else "spliced"
    spliced['store'] = f"{source_cache['store']} [{tag} {start:.1f}s-{end:.1f}s]"

    if ctx.original_cache is None:
        ctx.original_cache = ctx.cache

    ctx.cache = spliced
    ctx._active_splice = {"mode": mode, "start": start, "end": end}
    simple_plot(ctx)
    if announce:
        verb = f"Cut out {start:.1f}s–{end:.1f}s, {result['n_samples']} samples remain" \
            if mode == MODE_CUT_OUT else \
            f"Spliced to {start:.1f}s–{end:.1f}s ({result['n_samples']} samples)"
        show_window_toast(ctx, verb)
    return True


def apply_splice_at_points(ctx, t1, t2):
    """Called once two points have been clicked in Splice mode — applies
    immediately using the mode chosen in start_splice_flow, no further
    dialog."""
    mode = getattr(ctx, '_pending_splice_mode', None) or MODE_KEEP_INSIDE
    start, end = sorted((t1, t2))
    _apply_splice(ctx, mode, start, end)


def restore_full_recording(ctx):
    if ctx.original_cache is None:
        show_error(ctx, "No splice active — nothing to restore.")
        return

    from ..plotting import simple_plot

    ctx.cache = ctx.original_cache
    ctx.original_cache = None
    ctx._active_splice = None
    simple_plot(ctx)
    show_window_toast(ctx, "Restored full recording")


def is_spliced(ctx):
    return ctx.original_cache is not None


def splice_sidecar_path(ctx):
    """A splice.json next to markers.json in the same JSON saves/
    folder (see sidecar.py) — only ever describes the one active splice,
    since splicing again always starts fresh from the original recording
    rather than stacking on top of a previous splice. sidecar_path()
    reads ctx.cache['source_path'], which stays the same whether or not
    a splice is currently active (source_cache is carried through via
    `dict(source_cache)` in _apply_splice above), so no special-casing
    needed here for the spliced-vs-not state."""
    from ..sidecar import sidecar_path
    path = sidecar_path(ctx)
    if not path:
        return None
    return os.path.join(os.path.dirname(path), "splice.json")


def save_splice(ctx):
    """Writes the active splice (if any) to splice.json; removes it if
    no splice is active, so 'Save Changes' with nothing spliced doesn't
    leave a stale splice.json implying an edit that's no longer there."""
    if ctx.cache is None:
        return
    path = splice_sidecar_path(ctx)
    if not path:
        show_error(ctx, "No source file/folder path to save the splice next to.")
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if is_spliced(ctx) and getattr(ctx, '_active_splice', None):
            with open(path, 'w') as f:
                json.dump(ctx._active_splice, f, indent=2)
            show_window_toast(ctx, "Splice saved -> JSON saves/splice.json")
        elif os.path.exists(path):
            os.remove(path)
    except Exception as e:
        show_error(ctx, f"Could not save splice: {e}")


def load_splice_from_sidecar(ctx):
    """Called right after a fresh load (see loaders/tdt.py) — if a
    splice.json exists, reapplies it against the just-loaded full
    recording with no dialog, same as markers restoring silently."""
    path = splice_sidecar_path(ctx)
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, 'r') as f:
            saved = json.load(f)
        ok = _apply_splice(ctx, saved["mode"], saved["start"], saved["end"], announce=False)
        if ok:
            show_window_toast(ctx, "Splice restored")
    except Exception as e:
        show_error(ctx, f"Could not restore saved splice: {e}")
