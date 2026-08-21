"""
analysis/auc.py
------------------
Area-Under-Curve window analysis — same click-triggered dispatch as FFT/
Z-Score (double-click near an event with "AUC" selected in the
toolbar's plot-type combo). Mirrors fft.py's per-source branching
(Oxysoft dual/triple-channel vs. TDT/Generic single-channel). Generic/
double-click tools like this one deliberately analyze whichever signal
the "Plot:" dropdown currently shows (get_active_signal) rather than
always the normalized signal — that's reserved for the dataset-specific
tools under Custom Statistics (Event PETH, Find Significant Peaks),
which always analyze the corrected/normalized signal regardless of
what's on screen.
"""

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton

import PhysicsLibrary as pl

from ..context import get_active_signal
from ..fonts import fig_font_sizes
from ..toasts import show_window_toast
from .dispatch import add_stats_export_buttons, export_figure_to_file, get_window


def launch_auc(ctx, center_t):
    if ctx.cache is None:
        return
    pre, post = get_window(ctx)
    cache = ctx.cache
    x = cache['x']

    channels = []  # list of (label, color)
    if cache.get('source') == 'Oxysoft':
        o2hb = pl.mean_channels(cache['o2hb'])
        hhb = pl.mean_channels(cache['hhb'])
        channels.append(('Mean O2Hb', o2hb, '#CC0000'))
        channels.append(('Mean HHb', hhb, '#0033CC'))
        if 'thb' in cache:
            thb = pl.mean_channels(cache['thb'])
            channels.append(('Mean tHb', thb, '#228B22'))
    elif 'corr' in cache or 'raw' in cache:
        # TDT (and any other single-signal cache carrying corr/raw) —
        # whichever signal the "Plot:" dropdown currently displays.
        _, label, y, color = get_active_signal(ctx)
        channels.append((label, y, color))
    else:
        # Generic source: no 'signals'/'corr'/'raw' — same first-column
        # fallback fft.py uses for a Generic multi-column file.
        y = next(iter(cache['y_columns'].values()))
        channels.append(('Signal', y, '#2196F3'))

    last_auc_results = []
    for label, y, color in channels:
        result = pl.compute_auc_window(x, y, center_t, pre, post)
        last_auc_results.append({"channel": label, "color": color, **result})

    dlg = QDialog(ctx.win)
    dlg.setWindowTitle(
        f"AUC — {cache['store']}  |  centre {center_t:.1f}s  |  -{pre:.0f}s/+{post:.0f}s"
    )
    dlg.resize(700, 650)
    layout = QVBoxLayout(dlg)

    result_lbl = QLabel()
    result_lbl.setFont(QFont("Consolas", 9))
    result_lbl.setWordWrap(True)
    result_lbl.setFrameShape(QFrame.Shape.Panel)
    result_lbl.setStyleSheet("background-color: white; color: black; padding: 8px;")
    lines = []
    for r in last_auc_results:
        lines.append(
            f"[{r['channel']}]\n"
            f"  Total (net) AUC:    {r['total_auc']:.4f}\n"
            f"  Positive-only AUC:  {r['positive_auc']:.4f}\n"
            f"  Negative-only AUC:  {r['negative_auc']:.4f}"
        )
    lines.append(f"Window: -{pre:.1f}s / +{post:.1f}s around {center_t:.2f}s")
    result_lbl.setText("\n\n".join(lines))
    layout.addWidget(result_lbl)

    n = len(last_auc_results)
    fig = Figure(figsize=(8, 3.5 * n), dpi=100)
    axes = fig.subplots(n, 1) if n > 1 else [fig.add_subplot(111)]
    for ax, r in zip(axes, last_auc_results):
        seg_x, seg_y = r['seg_x'], r['seg_y']
        rel_x = seg_x - center_t
        ax.plot(rel_x, seg_y, color=r['color'], lw=1.5)
        ax.fill_between(rel_x, seg_y, 0, where=(seg_y >= 0), color='green', alpha=0.25)
        ax.fill_between(rel_x, seg_y, 0, where=(seg_y <= 0), color='red', alpha=0.25)
        ax.axhline(0, color='black', lw=0.8, alpha=0.6)
        ax.axvline(0, color='gray', lw=1.0, linestyle='--', alpha=0.6)
        tfs, lfs, _ = fig_font_sizes(fig)
        ax.set_ylabel(r['channel'], fontweight='bold', fontsize=lfs)
    axes[-1].set_xlabel("Time from Center (s)", fontweight='bold', fontsize=lfs)
    fig.suptitle("AUC", fontsize=tfs, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    canvas = FigureCanvasQTAgg(fig)
    layout.addWidget(canvas, stretch=1)

    btn_row = QHBoxLayout()
    add_stats_export_buttons(
        ctx, dlg, btn_row,
        get_clipboard_text=lambda: result_lbl.text(),
        csv_default_name=f"AUC_{cache['store']}_{int(center_t)}s",
        csv_header=["Channel", "Total AUC", "Positive AUC", "Negative AUC", "Window Pre (s)", "Window Post (s)"],
        get_csv_rows=lambda: [
            [r["channel"], f"{r['total_auc']:.6g}", f"{r['positive_auc']:.6g}",
             f"{r['negative_auc']:.6g}", f"{pre:.4f}", f"{post:.4f}"]
            for r in last_auc_results
        ],
    )
    btn_plot = QPushButton("Export Plot")
    btn_plot.clicked.connect(lambda: export_figure_to_file(ctx, fig, "AUC", f"{int(center_t)}s"))
    btn_row.addWidget(btn_plot)
    layout.addLayout(btn_row)

    show_window_toast(ctx, f"AUC computed at {center_t:.1f}s")
    dlg.exec()
