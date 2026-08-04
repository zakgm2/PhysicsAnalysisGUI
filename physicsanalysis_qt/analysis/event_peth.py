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
from matplotlib.ticker import MaxNLocator
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QWidget,
)

import PhysicsLibrary as pl

from ..background import run_in_background
from ..context import get_active_signal, signal_short_label
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
        self.resize(940, 720)
        outer = QHBoxLayout(self)

        left = QVBoxLayout()
        outer.addLayout(left, stretch=1)
        layout = left

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

        # Right side: per-trial include/exclude checklist — no automatic
        # rejection (std/threshold cutoffs), just a manual way to drop a
        # trial that looks contaminated (movement, a marker that fired on
        # a false trigger, ...) from the heatmap and mean/SEM trace without
        # having to change the event or window. Rebuilt fresh (all checked)
        # every time _run() computes a new trial set, since checkbox state
        # tied to a row index wouldn't mean anything for a different event
        # or window's trial count.
        right = QVBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setFixedWidth(180)
        outer.addWidget(right_widget)

        right.addWidget(QLabel("Trials"))
        trial_btn_row = QHBoxLayout()
        btn_select_all = QPushButton("All")
        btn_select_all.clicked.connect(lambda: self._set_all_trials_checked(True))
        trial_btn_row.addWidget(btn_select_all)
        btn_select_none = QPushButton("None")
        btn_select_none.clicked.connect(lambda: self._set_all_trials_checked(False))
        trial_btn_row.addWidget(btn_select_none)
        right.addLayout(trial_btn_row)

        self.trial_list = QListWidget()
        self.trial_list.itemChanged.connect(self._redraw)
        right.addWidget(self.trial_list, stretch=1)

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
        key, _, data_source, _ = get_active_signal(ctx)
        self.mode_str = signal_short_label(key)
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
            self._populate_trial_list(result)
            self.setWindowTitle(f"Event PETH — {event_name} ({self.mode_str})")
            show_window_toast(ctx, f"Event PETH: {result['trial_matrix'].shape[0]} trial(s) for '{event_name}'")
            self._redraw()

        def _on_error(msg):
            self.combo_event.setEnabled(True)
            show_error(ctx, f"Event PETH failed: {msg}")

        if ctx.settings.get("background_loading"):
            show_window_toast(ctx, f"Computing Event PETH for '{event_name}'…")
        run_in_background(ctx, _work, _on_success, _on_error)

    def _populate_trial_list(self, result):
        """Rebuild the trial checklist (all checked) for a freshly computed
        trial set — called once per _run(), never mutated in place, since
        checkbox state tied to a row index wouldn't carry over correctly
        to a different event or window's trial count."""
        self.trial_list.blockSignals(True)
        self.trial_list.clear()
        for i, t in enumerate(result["trial_event_times"]):
            item = QListWidgetItem(f"Trial {i + 1} — {t:.2f}s")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.trial_list.addItem(item)
        self.trial_list.blockSignals(False)

    def _set_all_trials_checked(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.trial_list.blockSignals(True)
        for i in range(self.trial_list.count()):
            self.trial_list.item(i).setCheckState(state)
        self.trial_list.blockSignals(False)
        self._redraw()

    def _selected_trial_indices(self):
        return [i for i in range(self.trial_list.count())
                if self.trial_list.item(i).checkState() == Qt.CheckState.Checked]

    def _row_order(self, sub_matrix):
        n = sub_matrix.shape[0]
        if self.sort_combo.currentText() == self.SORT_PEAK_AMPLITUDE:
            peak = np.abs(sub_matrix).max(axis=1) if n else np.array([])
            return np.argsort(peak)[::-1]
        return np.arange(n)

    def _redraw(self):
        if self.peth_result is None:
            return
        result = self.peth_result
        time_axis = result["time_axis"]
        matrix = result["trial_matrix"]

        # Mean/SEM recomputed here from just the checked trials — not
        # result["mean_trace"]/["sem_trace"], which cover every usable
        # trial regardless of the checklist. Same formula
        # compute_event_zscore_peth() uses (ddof=1, zero SEM if <2 trials).
        selected = self._selected_trial_indices()
        sub_matrix = matrix[selected] if selected else matrix[:0]
        n_total = matrix.shape[0]
        n_selected = sub_matrix.shape[0]
        if n_selected > 0:
            mean_trace = sub_matrix.mean(axis=0)
            sem_trace = (sub_matrix.std(axis=0, ddof=1) / np.sqrt(n_selected)
                         if n_selected > 1 else np.zeros_like(mean_trace))
        else:
            mean_trace = np.zeros_like(time_axis)
            sem_trace = np.zeros_like(time_axis)

        self.lbl_trials.setText(f"{n_selected} of {n_total} trial(s)")

        # Must remove the colorbar before clearing ax_heat — it restores
        # ax_heat's original (pre-colorbar) subplot geometry on removal,
        # which breaks if ax_heat's state has already changed underneath it.
        if self._colorbar is not None:
            self._colorbar.remove()
            self._colorbar = None
        self.ax_heat.clear()
        self.ax_line.clear()

        if n_selected == 0:
            self.ax_heat.text(0.5, 0.5, "No trials selected",
                               ha='center', va='center', transform=self.ax_heat.transAxes)
        else:
            order = self._row_order(sub_matrix)
            im = self.ax_heat.imshow(
                sub_matrix[order], aspect='auto', cmap='YlGnBu_r',
                extent=[-self.pre, self.post, n_selected, 0],
                vmin=-5, vmax=5, interpolation='nearest',
            )
            self._colorbar = self.fig.colorbar(im, ax=self.ax_heat, fraction=0.046, pad=0.04, label="Z-score")

        tfs, lfs, _ = fig_font_sizes(self.fig)
        self.ax_heat.set_ylabel("Trial", fontweight='bold', fontsize=lfs)
        # Trial rows are a count, not a continuous quantity — matplotlib's
        # default locator can otherwise land on fractional ticks (e.g. 2.5)
        # for small trial counts, which reads as meaningless for "Trial".
        self.ax_heat.yaxis.set_major_locator(MaxNLocator(integer=True))
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
