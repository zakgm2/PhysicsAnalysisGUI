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
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
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


class _EventPickerDialog(QDialog):
    def __init__(self, parent, ctx, groups):
        super().__init__(parent)
        self.ctx = ctx
        self.groups = groups
        self.chosen_name = None
        self.setWindowTitle("Event PETH — Choose Event")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Z-scores every occurrence of the chosen event against its own\n"
            "pre-event baseline, stacks each occurrence as a row in a heatmap,\n"
            "and plots the trial-averaged trace below it."
        ))

        row = QHBoxLayout()
        row.addWidget(QLabel("Event:"))
        self.combo = QComboBox()
        for name in sorted(groups.keys()):
            self.combo.addItem(f"{name}  ({len(groups[name])} occurrences)", userData=name)
        row.addWidget(self.combo, stretch=1)
        layout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Run")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _accept(self):
        self.chosen_name = self.combo.currentData()
        self.accept()


class _EventPethResultsDialog(QDialog):
    SORT_TRIAL_ORDER = "Trial order"
    SORT_PEAK_AMPLITUDE = "Peak amplitude"

    def __init__(self, parent, ctx, event_name, peth_result, mode_str, pre, post):
        super().__init__(parent)
        self.ctx = ctx
        self.event_name = event_name
        self.peth_result = peth_result
        self.mode_str = mode_str
        self.pre, self.post = pre, post

        self.setWindowTitle(f"Event PETH — {event_name} ({mode_str})")
        self.resize(750, 700)
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        n_trials = peth_result["trial_matrix"].shape[0]
        top_row.addWidget(QLabel(f"{n_trials} trial(s)"))
        top_row.addWidget(QLabel("Row order:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([self.SORT_TRIAL_ORDER, self.SORT_PEAK_AMPLITUDE])
        self.sort_combo.currentTextChanged.connect(self._redraw)
        top_row.addWidget(self.sort_combo)
        top_row.addStretch(1)
        layout.addLayout(top_row)

        self.fig = Figure(figsize=(8, 7), dpi=100)
        self.ax_heat, self.ax_line = self.fig.subplots(
            2, 1, sharex=True, gridspec_kw={'height_ratios': [2, 1]}
        )
        self.canvas = FigureCanvasQTAgg(self.fig)
        layout.addWidget(self.canvas, stretch=1)

        btn_export = QPushButton(f"Export {mode_str} Event PETH")
        btn_export.clicked.connect(
            lambda: export_figure_to_file(ctx, self.fig, f"EventPETH_{mode_str}", event_name)
        )
        layout.addWidget(btn_export)

        self._redraw()

    def _row_order(self):
        matrix = self.peth_result["trial_matrix"]
        n = matrix.shape[0]
        if self.sort_combo.currentText() == self.SORT_PEAK_AMPLITUDE:
            peak = np.abs(matrix).max(axis=1) if n else np.array([])
            return np.argsort(peak)[::-1]
        return np.arange(n)

    def _redraw(self):
        result = self.peth_result
        time_axis = result["time_axis"]
        matrix = result["trial_matrix"]
        mean_trace = result["mean_trace"]
        sem_trace = result["sem_trace"]

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
            self.fig.colorbar(im, ax=self.ax_heat, fraction=0.046, pad=0.04, label="Z-score")

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

    picker = _EventPickerDialog(ctx.win, ctx, groups)
    if picker.exec() != QDialog.DialogCode.Accepted or not picker.chosen_name:
        return

    event_name = picker.chosen_name
    event_times = groups[event_name]
    pre, post = get_window(ctx)
    mode_str = "Corrected" if ctx.show_corrected else "Raw"

    data_source = ctx.cache['corr'] if ctx.show_corrected else ctx.cache['raw']
    time_array = ctx.cache['x']
    fs = ctx.cache['fs']

    def _work():
        clean_signal = pl.smooth_signal(data_source, fs)
        return pl.compute_event_zscore_peth(time_array, clean_signal, event_times, pre, post)

    def _on_success(result):
        if result["trial_matrix"].shape[0] == 0:
            show_error(ctx, f"No usable trials for '{event_name}' — all occurrences were "
                             f"too close to the start/end of the recording for the current window.")
            return
        dlg = _EventPethResultsDialog(ctx.win, ctx, event_name, result, mode_str, pre, post)
        show_window_toast(ctx, f"Event PETH: {result['trial_matrix'].shape[0]} trial(s) for '{event_name}'")
        dlg.exec()

    def _on_error(msg):
        show_error(ctx, f"Event PETH failed: {msg}")

    if ctx.settings.get("background_loading"):
        show_window_toast(ctx, f"Computing Event PETH for '{event_name}'…")
    run_in_background(ctx, _work, _on_success, _on_error)
