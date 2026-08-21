"""
analysis/fft.py
-------------------
FFT viewer window — dual/triple-axis for Oxysoft (O2Hb/HHb/optional tHb),
single-axis for TDT/Generic sources. Same click-triggered dispatch as
AUC/Z-Score (double-click near a point with "FFT" selected in the
toolbar's plot-type combo). Mirrors auc.py's/peth.py's per-source
branching (build a `channels` list, then one shared render loop) rather
than special-casing Oxysoft's figure layout separately, so a channel
either tool supports (e.g. tHb) isn't silently unreachable here too.
Generic/double-click tools like this one deliberately analyze whichever
signal the "Plot:" dropdown currently shows (get_active_signal) rather
than always the normalized signal — that's reserved for the dataset-
specific tools under Custom Statistics (Event PETH, Find Significant
Peaks), which always analyze the corrected/normalized signal regardless
of what's on screen.
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


def launch_fft(ctx, center_t):
    if ctx.cache is None:
        return
    pre, post = get_window(ctx)
    cache = ctx.cache
    fs = cache['fs']

    channels = []  # (label, y, color)
    if cache.get('source') == 'Oxysoft':
        channels.append(('Mean O2Hb', pl.mean_channels(cache['o2hb']), '#CC0000'))
        channels.append(('Mean HHb', pl.mean_channels(cache['hhb']), '#0033CC'))
        if 'thb' in cache:
            channels.append(('Mean tHb', pl.mean_channels(cache['thb']), '#228B22'))
    elif 'corr' in cache or 'raw' in cache:
        # TDT (and any other single-signal cache carrying corr/raw) —
        # whichever signal the "Plot:" dropdown currently displays.
        _, label, y, color = get_active_signal(ctx)
        channels.append((label, y, color))
    else:
        # Generic source: no 'signals'/'corr'/'raw' — same first-column
        # fallback auc.py uses for a Generic multi-column file.
        y = next(iter(cache['y_columns'].values()))
        channels.append(('Signal', y, '#2196F3'))

    last_fft_results = []  # [{"channel": str, "peaks": [{"freq_hz","power","bpm"}, ...]}, ...]
    for label, y, color in channels:
        freqs, power, _, _ = pl.compute_fft_slice(cache['x'], y, center_t, fs, pre=pre, post=post)
        peaks = pl.find_fft_peaks(freqs, power) if len(freqs) > 0 else []
        last_fft_results.append({"channel": label, "peaks": peaks, "freqs": freqs, "power": power, "color": color})

    dlg = QDialog(ctx.win)
    dlg.setWindowTitle(
        f"FFT — {cache['store']}  |  centre {center_t:.1f}s  |  -{pre:.0f}s/+{post:.0f}s"
    )
    dlg.resize(700, 650)
    layout = QVBoxLayout(dlg)

    n = len(last_fft_results)
    fig_fft = Figure(figsize=(8, 3.5 * n), dpi=100)
    axes = fig_fft.subplots(n, 1) if n > 1 else [fig_fft.add_subplot(111)]
    lfs_f = 10
    for ax_f, r in zip(axes, last_fft_results):
        freqs, power = r["freqs"], r["power"]
        if len(freqs) > 0:
            ax_f.plot(freqs, power, color=r["color"], lw=1.5)
            pl.annotate_fft_peaks(ax_f, freqs, power, r["color"])
        tfs_f, lfs_f, _ = fig_font_sizes(fig_fft)
        ax_f.set_ylabel("Power", fontweight='bold', fontsize=lfs_f)
        ax_f.set_title(r["channel"], fontweight='bold', fontsize=tfs_f)
        ax_f.set_xlim(0.05, fs / 2)
        ax_f.autoscale(axis='y')
    axes[-1].set_xlabel("Frequency (Hz)", fontweight='bold', fontsize=lfs_f)

    fig_fft.suptitle(f"centre {center_t:.1f}s  |  -{pre:.0f}s/+{post:.0f}s", fontsize=10, color='gray')
    fig_fft.tight_layout(rect=[0, 0.03, 1, 0.97])
    canvas_fft = FigureCanvasQTAgg(fig_fft)
    layout.addWidget(canvas_fft)

    result_lbl = QLabel()
    result_lbl.setFont(QFont("Consolas", 9))
    result_lbl.setWordWrap(True)
    result_lbl.setFrameShape(QFrame.Shape.Panel)
    result_lbl.setStyleSheet("background-color: white; color: black; padding: 8px;")
    blocks = []
    for r in last_fft_results:
        if not r["peaks"]:
            blocks.append(f"[{r['channel']}]\n  No significant peaks found.")
            continue
        peak_lines = "\n".join(
            f"  Peak {i + 1}: {p['freq_hz']:.2f} Hz ({p['bpm']:.0f} bpm)  power={p['power']:.4f}"
            for i, p in enumerate(r["peaks"])
        )
        blocks.append(f"[{r['channel']}]\n{peak_lines}")
    result_lbl.setText("\n\n".join(blocks))
    layout.addWidget(result_lbl)

    btn_row = QHBoxLayout()
    add_stats_export_buttons(
        ctx, dlg, btn_row,
        get_clipboard_text=lambda: result_lbl.text(),
        csv_default_name=f"FFT_{cache['store']}_{int(center_t)}s",
        csv_header=["Channel", "Peak Rank", "Frequency (Hz)", "BPM", "Power"],
        get_csv_rows=lambda: [
            [r["channel"], i + 1, f"{p['freq_hz']:.4f}", f"{p['bpm']:.1f}", f"{p['power']:.4f}"]
            for r in last_fft_results for i, p in enumerate(r["peaks"])
        ],
    )
    btn_export = QPushButton("Export Plot")
    btn_export.clicked.connect(lambda: export_figure_to_file(ctx, fig_fft, "FFT", f"{int(center_t)}s"))
    btn_row.addWidget(btn_export)
    layout.addLayout(btn_row)

    show_window_toast(ctx, f"FFT at {center_t:.1f}s")
    dlg.exec()
