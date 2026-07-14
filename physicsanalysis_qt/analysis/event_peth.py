"""
analysis/event_peth.py
-------------------------
GuPPy-style event-triggered PETH: pick one event/marker name, Z-score
every occurrence of it against its own pre-event baseline, stack every
trial as a row in a heatmap (so trial-to-trial consistency is visible
at a glance), and plot the trial-averaged trace below it. TDT-only —
event markers are a TDT-specific concept elsewhere in this app too.

Distinct from peth.py's launch_zscore_peth, which analyzes a single
arbitrary clicked point rather than every occurrence of a named event.
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit,
)

import PhysicsLibrary as pl

from ..background import run_in_background
from ..fonts import fig_font_sizes
from ..marker_labels import marker_display_label
from ..toasts import show_error, show_window_toast
from .dispatch import export_figure_to_file, get_window


def _group_markers_by_name(ctx):
    """{display_name: [sorted event times]} across every event TDT
    actually detected in this recording (ctx.cache['detected_markers']),
    plus anything manually placed or already added to the plot
    (ctx.cache['markers']) — deduped by (name, time) so a marker that's
    both detected and already plotted doesn't get double-counted. This
    intentionally does NOT require an event to already be on the plot:
    the whole point is finding out which event types are worth plotting
    in the first place. High/low phase markers count as separate event
    names (their display label already differs by the ¹/⁰ suffix)."""
    groups = {}
    seen = set()
    for m in ctx.cache.get('detected_markers', []) + ctx.cache['markers']:
        name = marker_display_label(ctx, m)
        key = (name, m['time'])
        if key in seen:
            continue
        seen.add(key)
        groups.setdefault(name, []).append(m['time'])
    for name in groups:
        groups[name].sort()
    return groups


class _EventPethResultsDialog(QDialog):
    """Stays open across event switches — picking a different event from
    the combo re-runs the computation in place instead of requiring you
    to close this and reopen a separate picker dialog."""

    SORT_TRIAL_ORDER = "Trial order"
    SORT_PEAK_AMPLITUDE = "Peak amplitude"

    def __init__(self, parent, ctx, groups, initial_event_name):
        super().__init__(parent)
        self.ctx = ctx
        self.groups = groups
        self.event_name = initial_event_name
        self.peth_result = None
        self._colorbar = None

        self.setWindowTitle("Event PETH")
        self.resize(750, 720)
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Event:"))
        self.combo_event = QComboBox()
        for name in sorted(groups.keys()):
            self.combo_event.addItem(f"{name}  ({len(groups[name])} occurrences)", userData=name)
        self.combo_event.setCurrentIndex(self.combo_event.findData(initial_event_name))
        self.combo_event.currentIndexChanged.connect(self._on_event_changed)
        top_row.addWidget(self.combo_event, stretch=1)

        self.lbl_trials = QLabel("")
        top_row.addWidget(self.lbl_trials)

        top_row.addWidget(QLabel("Row order:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([self.SORT_TRIAL_ORDER, self.SORT_PEAK_AMPLITUDE])
        self.sort_combo.currentTextChanged.connect(self._redraw)
        top_row.addWidget(self.sort_combo)
        layout.addLayout(top_row)

        window_row = QHBoxLayout()
        window_row.addWidget(QLabel("Window — pre (s):"))
        self.e_pre = QLineEdit(str(int(ctx.window_pre or get_window(ctx)[0])))
        self.e_pre.setFixedWidth(50)
        window_row.addWidget(self.e_pre)
        window_row.addWidget(QLabel("post (s):"))
        self.e_post = QLineEdit(str(int(ctx.window_post or get_window(ctx)[1])))
        self.e_post.setFixedWidth(50)
        window_row.addWidget(self.e_post)
        btn_recalc = QPushButton("Recalculate")
        btn_recalc.clicked.connect(lambda: self._run(self.event_name))
        window_row.addWidget(btn_recalc)
        window_row.addStretch(1)
        layout.addLayout(window_row)

        self.fig = Figure(figsize=(8, 7), dpi=100)
        self.ax_heat, self.ax_line = self.fig.subplots(
            2, 1, sharex=True, gridspec_kw={'height_ratios': [2, 1]}
        )
        self.canvas = FigureCanvasQTAgg(self.fig)
        layout.addWidget(self.canvas, stretch=1)

        self.btn_export = QPushButton("Export Event PETH")
        self.btn_export.clicked.connect(
            lambda: export_figure_to_file(ctx, self.fig, "EventPETH", self.event_name)
        )
        layout.addWidget(self.btn_export)

        self._run(initial_event_name)

    def _on_event_changed(self):
        name = self.combo_event.currentData()
        if name and name != self.event_name:
            self._run(name)

    def _read_window(self):
        default_pre, default_post = get_window(self.ctx)
        try:
            pre = max(0.1, float(self.e_pre.text()))
        except ValueError:
            pre = default_pre
        try:
            post = max(0.1, float(self.e_post.text()))
        except ValueError:
            post = default_post
        return pre, post

    def _run(self, event_name):
        ctx = self.ctx
        self.event_name = event_name
        self.combo_event.setEnabled(False)

        event_times = self.groups[event_name]
        self.pre, self.post = self._read_window()
        self.mode_str = "Corrected" if ctx.show_corrected else "Raw"
        data_source = ctx.cache['corr'] if ctx.show_corrected else ctx.cache['raw']
        time_array = ctx.cache['x']
        fs = ctx.cache['fs']
        pre, post = self.pre, self.post

        def _work():
            clean_signal = pl.smooth_signal(data_source, fs)
            return pl.compute_event_zscore_peth(time_array, clean_signal, event_times, pre, post)

        def _on_success(result):
            self.combo_event.setEnabled(True)
            if result["trial_matrix"].shape[0] == 0:
                show_error(ctx, f"No usable trials for '{event_name}' — all occurrences were "
                                 f"too close to the start/end of the recording for the current window.")
                return
            self.peth_result = result
            self.setWindowTitle(f"Event PETH — {event_name} ({self.mode_str})")
            show_window_toast(ctx, f"Event PETH: {result['trial_matrix'].shape[0]} trial(s) for '{event_name}'")
            self._redraw()

        def _on_error(msg):
            self.combo_event.setEnabled(True)
            show_error(ctx, f"Event PETH failed: {msg}")

        if ctx.settings.get("background_loading"):
            show_window_toast(ctx, f"Computing Event PETH for '{event_name}'…")
        run_in_background(ctx, _work, _on_success, _on_error)

    def _row_order(self):
        matrix = self.peth_result["trial_matrix"]
        n = matrix.shape[0]
        if self.sort_combo.currentText() == self.SORT_PEAK_AMPLITUDE:
            peak = np.abs(matrix).max(axis=1) if n else np.array([])
            return np.argsort(peak)[::-1]
        return np.arange(n)

    def _redraw(self):
        if self.peth_result is None:
            return
        result = self.peth_result
        time_axis = result["time_axis"]
        matrix = result["trial_matrix"]
        mean_trace = result["mean_trace"]
        sem_trace = result["sem_trace"]

        self.lbl_trials.setText(f"{matrix.shape[0]} trial(s)")

        # Must remove the colorbar before clearing ax_heat — it restores
        # ax_heat's original (pre-colorbar) subplot geometry on removal,
        # which breaks if ax_heat's state has already changed underneath it.
        if self._colorbar is not None:
            self._colorbar.remove()
            self._colorbar = None
        self.ax_heat.clear()
        self.ax_line.clear()

        if matrix.shape[0] == 0:
            self.ax_heat.text(0.5, 0.5, "No usable trials (too close to recording edges?)",
                               ha='center', va='center', transform=self.ax_heat.transAxes)
        else:
            order = self._row_order()
            im = self.ax_heat.imshow(
                matrix[order], aspect='auto', cmap='YlGnBu_r',
                extent=[-self.pre, self.post, matrix.shape[0], 0],
                vmin=-5, vmax=5, interpolation='nearest',
            )
            self._colorbar = self.fig.colorbar(im, ax=self.ax_heat, fraction=0.046, pad=0.04, label="Z-score")

        tfs, lfs, _ = fig_font_sizes(self.fig)
        self.ax_heat.set_ylabel("Trial", fontweight='bold', fontsize=lfs)
        self.ax_heat.axvline(0, color='red', linestyle='--', alpha=0.7)

        self.ax_line.plot(time_axis, mean_trace, color='black', linewidth=1.5, label="Mean")
        self.ax_line.fill_between(time_axis, mean_trace - sem_trace, mean_trace + sem_trace,
                                    color='black', alpha=0.2, label="SEM")
        self.ax_line.axvline(0, color='red', linestyle='--', alpha=0.7)
        self.ax_line.set_xlim([-self.pre, self.post])
        self.ax_line.set_ylabel(f"Z-Score ({self.mode_str})", fontweight='bold', fontsize=lfs)
        self.ax_line.set_xlabel("Time from Event (s)", fontweight='bold', fontsize=lfs)
        self.ax_line.legend(fontsize=lfs * 0.8, loc='upper right')

        self.fig.suptitle(f"Event PETH — {self.event_name}", fontsize=tfs, fontweight='bold')
        self.fig.tight_layout(rect=[0, 0, 1, 0.96])
        self.canvas.draw_idle()


def launch_event_peth(ctx):
    if ctx.cache is None or ctx.cache.get('source') != 'TDT':
        show_error(ctx, "Event PETH is only available for TDT data.")
        return

    groups = _group_markers_by_name(ctx)
    if not groups:
        show_error(ctx, "No events found in this recording.")
        return

    initial_name = sorted(groups.keys())[0]
    dlg = _EventPethResultsDialog(ctx.win, ctx, groups, initial_name)
    dlg.exec()
