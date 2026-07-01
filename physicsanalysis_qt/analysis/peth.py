"""
analysis/peth.py
-------------------
Z-score PETH (peri-event time histogram) window, TDT-only.
"""

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton

import PhysicsLibrary as pl

from ..fonts import fig_font_sizes
from ..toasts import show_error, show_window_toast
from .dispatch import export_figure_to_file


def launch_zscore_peth(ctx, center_t):
    if ctx.cache is None or ctx.cache.get('source') != 'TDT':
        show_error(ctx, "PETH is only available for TDT data.")
        return
    data_source = ctx.cache['corr'] if ctx.show_corrected else ctx.cache['raw']
    clean_signal = pl.smooth_signal(data_source, ctx.cache['fs'])
    slice_x, z_seg = pl.get_zscore_slice(ctx.cache['x'], clean_signal, center_t, window=30)
    if z_seg is None:
        return
    z_binned = pl.bin_for_heatmap(z_seg)
    mode_str = "Corrected" if ctx.show_corrected else "Raw"

    dlg = QDialog(ctx.win)
    dlg.setWindowTitle(f"PETH Analysis ({mode_str}) - {center_t:.2f}s")
    dlg.resize(700, 650)
    layout = QVBoxLayout(dlg)

    fig_peth = Figure(figsize=(8, 7), dpi=100)
    ax_heat, ax_line = fig_peth.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [1, 1]})

    ax_heat.imshow(z_binned.reshape(1, -1), aspect='auto', cmap='YlGnBu_r',
                   extent=[-30, 30, 0, 1], vmin=-5, vmax=5, interpolation='bilinear')
    ax_heat.set_yticks([])
    tfs_p, lfs_p, _ = fig_font_sizes(fig_peth)
    ax_heat.set_ylabel("Intensity", fontweight='bold', fontsize=lfs_p)

    ax_line.plot(slice_x - center_t, z_seg, color='black', linewidth=1.5)
    ax_line.axvline(0, color='red', linestyle='--', alpha=0.8)
    ax_line.set_xlim([-15, 15])
    ax_line.set_ylim([-5, 5])
    ax_line.set_ylabel(f"Z-Score ({mode_str})", fontweight='bold', fontsize=lfs_p)
    ax_line.set_xlabel("Time from Center (s)", fontweight='bold', fontsize=lfs_p)

    fig_peth.suptitle("Z-score PETH", fontsize=tfs_p, fontweight='bold')
    fig_peth.tight_layout(rect=[0, 0.05, 1, 0.95])

    canvas_peth = FigureCanvasQTAgg(fig_peth)
    layout.addWidget(canvas_peth)

    btn_export = QPushButton(f"Export {mode_str} PETH")
    btn_export.clicked.connect(
        lambda: export_figure_to_file(ctx, fig_peth, f"PETH_{mode_str}", f"{int(center_t)}s")
    )
    layout.addWidget(btn_export)

    show_window_toast(ctx, f"PETH Generated at {center_t:.1f}s")
    dlg.exec()
