"""
analysis/fft.py
-------------------
FFT viewer window — dual-axis for Oxysoft (O2Hb/HHb), single-axis for
TDT/Generic sources.
"""

import datetime

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QFileDialog

import PhysicsLibrary as pl

from ..fonts import fig_font_sizes
from ..toasts import show_window_toast
from .dispatch import get_window


def launch_fft(ctx, center_t):
    if ctx.cache is None:
        return
    pre, post = get_window(ctx)
    cache = ctx.cache
    fs = cache['fs']

    dlg = QDialog(ctx.win)
    dlg.setWindowTitle(
        f"FFT — {cache['store']}  |  centre {center_t:.1f}s  |  -{pre:.0f}s/+{post:.0f}s"
    )
    dlg.resize(700, 650)
    layout = QVBoxLayout(dlg)

    if cache.get('source') == 'Oxysoft':
        x = cache['x']
        o2hb = cache['o2hb'].mean(axis=0)
        hhb = cache['hhb'].mean(axis=0)
        fig_fft = Figure(figsize=(8, 7), dpi=100)
        ax_o2, ax_hh = fig_fft.subplots(2, 1)
        lfs_f = 10
        for sig, ax_f, color, label in [
            (o2hb, ax_o2, '#CC0000', 'Mean O2Hb'),
            (hhb, ax_hh, '#0033CC', 'Mean HHb'),
        ]:
            freqs, power, _, _ = pl.compute_fft_slice(x, sig, center_t, fs, pre=pre, post=post)
            if len(freqs) > 0:
                ax_f.plot(freqs, power, color=color, lw=1.5)
                pl.annotate_fft_peaks(ax_f, freqs, power, color)
            tfs_f, lfs_f, _ = fig_font_sizes(fig_fft)
            ax_f.set_ylabel("Power", fontweight='bold', fontsize=lfs_f)
            ax_f.set_title(label, fontweight='bold', fontsize=tfs_f)
            ax_f.set_xlim(0.05, fs / 2)
            ax_f.autoscale(axis='y')
        ax_hh.set_xlabel("Frequency (Hz)", fontweight='bold', fontsize=lfs_f)
    else:
        # 'corr'/'raw' are TDT-only keys; Generic-source data instead
        # carries its Y columns in cache['y_columns'] — fall back to the
        # first one so FFT doesn't KeyError on non-TDT single-signal data.
        if 'corr' in cache or 'raw' in cache:
            signal = cache['corr'] if ctx.show_corrected else cache['raw']
        else:
            signal = next(iter(cache['y_columns'].values()))
        freqs, power, _, _ = pl.compute_fft_slice(cache['x'], signal, center_t, fs, pre=pre, post=post)
        fig_fft = Figure(figsize=(8, 4), dpi=100)
        ax_f = fig_fft.add_subplot(111)
        if len(freqs) > 0:
            ax_f.plot(freqs, power, color='blue', lw=1.5)
            pl.annotate_fft_peaks(ax_f, freqs, power, 'blue')
        tfs_f, lfs_f, _ = fig_font_sizes(fig_fft)
        ax_f.set_xlabel("Frequency (Hz)", fontweight='bold', fontsize=lfs_f)
        ax_f.set_ylabel("Power", fontweight='bold', fontsize=lfs_f)
        ax_f.set_title(f"FFT — {cache['store']}", fontweight='bold', fontsize=tfs_f)
        ax_f.set_xlim(0.05, fs / 2)
        ax_f.autoscale(axis='y')

    fig_fft.suptitle(f"centre {center_t:.1f}s  |  -{pre:.0f}s/+{post:.0f}s", fontsize=10, color='gray')
    fig_fft.tight_layout(rect=[0, 0.03, 1, 0.97])
    canvas_fft = FigureCanvasQTAgg(fig_fft)
    layout.addWidget(canvas_fft)

    def save_fft_action():
        ts = datetime.datetime.now().strftime("%H%M%S")
        fpath, _ = QFileDialog.getSaveFileName(
            dlg, "Export FFT", f"FFT_{cache['store']}_{int(center_t)}s_{ts}.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)"
        )
        if fpath:
            fig_fft.savefig(fpath, dpi=300, bbox_inches='tight')
            show_window_toast(ctx, "FFT Exported")

    btn_export = QPushButton("Export FFT")
    btn_export.clicked.connect(save_fft_action)
    layout.addWidget(btn_export)

    show_window_toast(ctx, f"FFT at {center_t:.1f}s")
    dlg.exec()
