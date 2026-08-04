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

Splices stack: each new one applies on top of whatever's currently
shown rather than always restarting from the pristine original, so
removing several separate artifacts from the same recording doesn't
mean the second attempt undoes the first. ctx._active_splices records
every applied splice in order — see remove_splice()/open_splice_manager
for reviewing or removing one without discarding the rest, and
restore_full_recording() for discarding all of them at once.

TDT-only for now: Oxysoft/Generic sources have a different cache shape
(o2hb/hhb/thb arrays, y_columns dict) this doesn't handle yet.
"""

import json
import os

import PhysicsLibrary as pl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QListWidget,
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
    """Entry point for the sidebar's scissors icon: asks the mode first,
    then hands control to the plot for two clicks (see interaction.py's
    on_release Splice-mode handling, which calls apply_splice_at_points
    below once it has both points). Called fresh on every click of the
    icon — always reopens the mode picker, even if a previous splice
    flow is still mid-click-capture (starting over just discards those
    stray clicks, same as re-picking Curve Fit would)."""
    if ctx.cache is None or ctx.cache.get('source') != 'TDT':
        show_error(ctx, "Splicing is only available for TDT data.")
        return False

    dlg = _SpliceModePickerDialog(ctx.win, ctx)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return False

    ctx._pending_splice_mode = dlg.mode
    ctx.slope_clicks.clear()
    ctx.splice_click_mode = True
    show_window_toast(ctx, "Click two points on the graph to mark the range")
    return True


def _splice_once(source_cache, mode, start, end):
    """Pure computation: apply one splice to source_cache, returning the
    new spliced cache dict, or None if the range isn't usable. No ctx
    mutation, no toast/redraw — shared by _apply_splice (one interactive
    step) and remove_splice/load_splice_from_sidecar (replaying several
    steps in a row from the pristine original)."""
    splice_fn = pl.splice_cut_out if mode == MODE_CUT_OUT else pl.splice_keep_inside

    # The Plot dropdown's raw per-wavelength channels (main driver,
    # isosbestic, ...) are sample-aligned with x/raw/corr and must be
    # trimmed/cut identically or they'd end up the wrong length (and
    # showing the wrong span of samples) after this splice — 'normalized'
    # is excluded since it's already the freshly-spliced 'corr' below.
    source_signals = source_cache.get('signals', {})
    extra_channels = {k: sig['y'] for k, sig in source_signals.items() if k != 'normalized'}

    result = splice_fn(
        source_cache['x'], source_cache['raw'], source_cache['corr'],
        source_cache['markers'], source_cache.get('detected_markers', []),
        start, end, extra_channels=extra_channels,
    )
    if result is None:
        return None

    spliced = dict(source_cache)
    spliced['x'] = result['x']
    spliced['raw'] = result['raw']
    spliced['corr'] = result['corr']
    spliced['markers'] = result['markers']
    spliced['detected_markers'] = result['detected_markers']
    if source_signals:
        spliced['signals'] = {
            key: {**sig, 'y': result['corr'] if key == 'normalized' else result['extra_channels'][key]}
            for key, sig in source_signals.items()
        }
    return spliced


def _spliced_store_name(base_name, splices):
    """Store label reflecting every splice currently applied, in order —
    derived fresh from the splice list each time (rather than appending a
    tag onto whatever the previous label happened to be) so it stays
    correct after remove_splice() changes which ones are still active."""
    if not splices:
        return base_name
    tags = ", ".join(
        f"{'cut' if s['mode'] == MODE_CUT_OUT else 'kept'} {s['start']:.1f}s-{s['end']:.1f}s"
        for s in splices
    )
    return f"{base_name} [{tags}]"


def _apply_splice(ctx, mode, start, end, announce=True):
    """Applies one splice on top of whatever's currently shown — splices
    stack rather than each one restarting from the pristine original, so
    removing a second artifact doesn't undo the first. Records the
    operation on ctx._active_splices so it can be written out by
    save_splice() and later reviewed/removed via remove_splice()."""
    from ..plotting import simple_plot

    spliced = _splice_once(ctx.cache, mode, start, end)
    if spliced is None:
        if announce:
            msg = ("Can't cut that range — need usable signal on both sides of the cut."
                   if mode == MODE_CUT_OUT else
                   "That range doesn't contain enough samples to analyze.")
            show_error(ctx, msg)
        return False

    if ctx.original_cache is None:
        ctx.original_cache = ctx.cache

    new_splices = ctx._active_splices + [{"mode": mode, "start": start, "end": end}]
    spliced['store'] = _spliced_store_name(ctx.original_cache['store'], new_splices)

    ctx._data_generation += 1
    ctx.cache = spliced
    ctx._active_splices = new_splices
    simple_plot(ctx)
    if announce:
        n_samples = len(spliced['x'])
        verb = f"Cut out {start:.1f}s–{end:.1f}s, {n_samples} samples remain" \
            if mode == MODE_CUT_OUT else \
            f"Spliced to {start:.1f}s–{end:.1f}s ({n_samples} samples)"
        show_window_toast(ctx, verb)
    return True


def apply_splice_at_points(ctx, t1, t2):
    """Called once two points have been clicked in Splice mode — applies
    immediately using the mode chosen in start_splice_flow, no further
    dialog."""
    ctx.splice_click_mode = False  # the flow that started with start_splice_flow() is done
    mode = getattr(ctx, '_pending_splice_mode', None) or MODE_KEEP_INSIDE
    start, end = sorted((t1, t2))
    _apply_splice(ctx, mode, start, end)


def remove_splice(ctx, index):
    """Removes one splice from the stack and recomputes ctx.cache by
    replaying every remaining splice, in order, from the pristine
    original — the only correct way to reflect removing a middle splice,
    since each one's start/end were recorded relative to whatever the
    recording looked like right before it was applied. Note: removing an
    earlier splice can shift what a later one's saved range actually
    lines up with, the same way deleting a step from any sequential edit
    history can (Undo-stack tools all share this tradeoff).

    Returns True if the removal (and any needed recompute) succeeded.
    """
    from ..plotting import simple_plot

    if not (0 <= index < len(ctx._active_splices)):
        return False

    remaining = ctx._active_splices[:index] + ctx._active_splices[index + 1:]
    if not remaining:
        restore_full_recording(ctx)
        return True

    cache = ctx.original_cache
    for s in remaining:
        cache = _splice_once(cache, s["mode"], s["start"], s["end"])
        if cache is None:
            show_error(ctx, "Removing that splice makes an earlier range invalid — "
                             "try removing a different one, or Restore Full Recording.")
            return False

    cache['store'] = _spliced_store_name(ctx.original_cache['store'], remaining)
    ctx._data_generation += 1
    ctx.cache = cache
    ctx._active_splices = remaining
    simple_plot(ctx)
    show_window_toast(ctx, f"Removed splice — {len(remaining)} remaining")
    return True


def restore_full_recording(ctx):
    if ctx.original_cache is None:
        show_error(ctx, "No splice active — nothing to restore.")
        return

    from ..plotting import simple_plot

    ctx._data_generation += 1
    ctx.cache = ctx.original_cache
    ctx.original_cache = None
    ctx._active_splices = []
    simple_plot(ctx)
    show_window_toast(ctx, "Restored full recording")


def is_spliced(ctx):
    return ctx.original_cache is not None


class _SpliceManagerDialog(QDialog):
    """Lists every splice currently stacked on the recording, each
    removable individually (see remove_splice() for why removing an
    earlier one can shift what a later one's saved range lines up
    with), plus a one-click full restore."""

    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Manage Splices")
        self.resize(440, 320)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Applied in order, top to bottom. Removing one replays the rest\n"
            "from the original recording — removing an earlier splice can shift\n"
            "what a later splice's saved range actually lines up with."
        ))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, stretch=1)

        btn_row = QHBoxLayout()
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(btn_remove)
        btn_restore_all = QPushButton("Restore Full Recording")
        btn_restore_all.clicked.connect(self._restore_all)
        btn_row.addWidget(btn_restore_all)
        btn_close = QPushButton("Close")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        for i, s in enumerate(self.ctx._active_splices):
            verb = "Cut out" if s["mode"] == MODE_CUT_OUT else "Kept"
            self.list_widget.addItem(f"{i + 1}. {verb} {s['start']:.1f}s–{s['end']:.1f}s")

    def _remove_selected(self):
        row = self.list_widget.currentRow()
        if row < 0:
            show_error(self.ctx, "Select a splice to remove first.")
            return
        if remove_splice(self.ctx, row):
            if self.ctx._active_splices:
                self._refresh_list()
            else:
                self.accept()

    def _restore_all(self):
        restore_full_recording(self.ctx)
        self.accept()


def open_splice_manager(ctx):
    if not ctx._active_splices:
        show_error(ctx, "No splices active.")
        return
    dlg = _SpliceManagerDialog(ctx.win, ctx)
    dlg.exec()


def splice_sidecar_path(ctx):
    """A splice.json next to markers.json in the same JSON saves/
    folder (see sidecar.py) — describes every splice currently stacked,
    in order. sidecar_path() reads ctx.cache['source_path'], which stays
    the same whether or not a splice is currently active (source_cache
    is carried through via `dict(source_cache)` in _splice_once above),
    so no special-casing needed here for the spliced-vs-not state."""
    from ..sidecar import sidecar_path
    path = sidecar_path(ctx)
    if not path:
        return None
    return os.path.join(os.path.dirname(path), "splice.json")


def save_splice(ctx):
    """Writes every active splice (if any) to splice.json as a list;
    removes it if no splice is active, so 'Save Changes' with nothing
    spliced doesn't leave a stale splice.json implying an edit that's no
    longer there."""
    if ctx.cache is None:
        return
    path = splice_sidecar_path(ctx)
    if not path:
        show_error(ctx, "No source file/folder path to save the splice next to.")
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if is_spliced(ctx) and ctx._active_splices:
            with open(path, 'w') as f:
                json.dump(ctx._active_splices, f, indent=2)
            n = len(ctx._active_splices)
            show_window_toast(ctx, f"{n} splice{'s' if n != 1 else ''} saved -> JSON saves/splice.json")
        elif os.path.exists(path):
            os.remove(path)
    except Exception as e:
        show_error(ctx, f"Could not save splice: {e}")


def load_splice_from_sidecar(ctx):
    """Called right after a fresh load (see loaders/tdt.py) — if a
    splice.json exists, replays every saved splice against the
    just-loaded full recording, in order, with no dialog, same as
    markers restoring silently. Accepts both the current format (a list
    of splices) and the old single-splice format (a flat
    {"mode", "start", "end"} dict, from before splices could stack)."""
    path = splice_sidecar_path(ctx)
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, 'r') as f:
            saved = json.load(f)
        splices = [saved] if isinstance(saved, dict) else saved
        applied = 0
        for s in splices:
            if _apply_splice(ctx, s["mode"], s["start"], s["end"], announce=False):
                applied += 1
        if applied:
            show_window_toast(ctx, f"Restored {applied} splice{'s' if applied != 1 else ''}")
    except Exception as e:
        show_error(ctx, f"Could not restore saved splice: {e}")
