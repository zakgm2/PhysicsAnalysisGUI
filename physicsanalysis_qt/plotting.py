"""
plotting.py
-----------
Drawing the main plot: simple_plot() builds the figure from cache,
_apply_plot_attrs() re-applies persisted label/font/legend customisations
after any redraw, and export_canvas_action() saves the current view.
"""

import numpy as np
import matplotlib.transforms as transforms
from PyQt6.QtWidgets import QFileDialog

from .toasts import show_error, show_window_toast


def _update_plot_with_notes(ctx, markers):
    trans = transforms.blended_transform_factory(ctx.ax.transData, ctx.ax.transAxes)
    unique_labels = set()
    for m in markers:
        label_id = m['label'] if m['label'] not in unique_labels else "_nolegend_"
        unique_labels.add(m['label'])
        ctx.ax.axvline(x=m['time'], color=m['color'], linestyle='--', alpha=0.6, label=label_id)
        ctx.ax.text(m['time'], 0.98, f" {m['label']}", transform=trans,
                     rotation=90, va='top', clip_on=True, fontsize=m.get('fontsize', 8),
                     color=m['color'], fontweight='bold',
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))


def _apply_plot_attrs(ctx):
    """Always apply persisted font sizes; only override text when the user set one."""
    ax = ctx.ax
    plot_attrs = ctx.plot_attrs
    title_text = plot_attrs["title"] or ax.get_title()
    xlabel_text = plot_attrs["xlabel"] or ax.get_xlabel()
    ylabel_text = plot_attrs["ylabel"] or ax.get_ylabel()
    ax.set_title(title_text, fontweight='bold', pad=15, fontsize=plot_attrs["title_fs"])
    ax.set_xlabel(xlabel_text, fontweight='bold', fontsize=plot_attrs["xlabel_fs"])
    ax.set_ylabel(ylabel_text, fontweight='bold', fontsize=plot_attrs["ylabel_fs"])

    handles, labels = ax.get_legend_handles_labels()
    entries = [(h, l) for h, l in zip(handles, labels) if not l.startswith('_')]
    if not entries:
        return

    if plot_attrs["leg_entries"]:
        label_map = {orig: (new, vis) for orig, new, vis in plot_attrs["leg_entries"]}
        new_h, new_l = [], []
        for h, l in entries:
            if l in label_map:
                new_label, visible = label_map[l]
                if visible:
                    new_h.append(h)
                    new_l.append(new_label)
            else:
                new_h.append(h)
                new_l.append(l)
        if new_h:
            ax.legend(new_h, new_l, fontsize=plot_attrs["leg_fs"], loc=plot_attrs["leg_loc"])
        else:
            leg = ax.get_legend()
            if leg:
                leg.remove()
    else:
        ax.legend(fontsize=plot_attrs["leg_fs"], loc=plot_attrs["leg_loc"])


def simple_plot(ctx, draw_now=True):
    cache = ctx.cache
    ax = ctx.ax
    if cache is None:
        return
    ax.clear()
    ax.axhline(0, color='black', linewidth=1.0, alpha=0.4, zorder=1)

    if cache.get('source') == 'Oxysoft':
        x = cache['x']
        o2hb = cache['o2hb']
        hhb = cache['hhb']
        for i in range(o2hb.shape[0]):
            ax.plot(x, o2hb[i], color='#FF9999', lw=0.8, alpha=0.5,
                    label='O2Hb channels' if i == 0 else '_nolegend_')
            ax.plot(x, hhb[i], color='#99BBFF', lw=0.8, alpha=0.5,
                    label='HHb channels' if i == 0 else '_nolegend_')
        ff = cache.get('fit_factor_mean')
        ff_tag = f"  [FF: {ff:.1f}%]" if ff is not None else ""
        ax.plot(x, o2hb.mean(axis=0), color='#CC0000', lw=2.0, label=f'Mean O2Hb{ff_tag}')
        ax.plot(x, hhb.mean(axis=0), color='#0033CC', lw=2.0, label=f'Mean HHb{ff_tag}')
        if 'thb' in cache:
            thb = cache['thb']
            ax.plot(x, thb.mean(axis=0), color='#228B22', lw=2.0, label=f'Mean tHb{ff_tag}')
        ax.set_ylabel("Delta Concentration (uM)", fontweight='bold')
        ax.set_title(f"NIRS — {cache['store']}", fontweight='bold', pad=15)
        x_label = "Time (s)"
        n_snap_lines = 3 if 'thb' in cache else 2
    elif cache.get('source') == 'Generic':
        x = cache['x']
        _GEN_COLORS = ['#CC0000', '#0033CC', '#228B22', '#CC6600',
                       '#6600CC', '#008888', '#AA0055', '#005588']
        for i, (col_name, y) in enumerate(cache['y_columns'].items()):
            mask = ~np.isnan(y)
            ax.plot(x[mask], y[mask], 'o-', lw=1.8, markersize=4,
                    color=_GEN_COLORS[i % len(_GEN_COLORS)], label=col_name)
        ax.set_ylabel("Value", fontweight='bold')
        ax.set_title(cache['store'], fontweight='bold', pad=15)
        x_label = cache.get('x_label', 'X')
        n_snap_lines = len(cache['y_columns'])
    else:
        data_to_plot = cache['corr'] if ctx.show_corrected else cache['raw']
        color_choice = 'blue' if ctx.show_corrected else 'gray'
        label_text = 'dF/F (corrected)' if ctx.show_corrected else 'Raw signal'
        ax.axvline(0, color='black', linewidth=1.0, alpha=0.4, zorder=1)
        ax.plot(cache['x'], data_to_plot, color=color_choice,
                lw=1.5, alpha=0.8, label=label_text)
        ax.set_ylabel("Amplitude", fontweight='bold')
        ax.set_title(f"{label_text} — {cache['store']}", fontweight='bold', pad=15)
        x_label = "Time (s)"
        n_snap_lines = 1

    _update_plot_with_notes(ctx, cache['markers'])
    ax.set_xlabel(x_label, fontweight='bold')
    ax.legend(loc='upper left', fontsize=ctx.plot_attrs["leg_fs"])
    ax.set_xlim(cache['x'][0], cache['x'][-1])
    _apply_plot_attrs(ctx)

    if ctx.show_grid:
        ax.grid(True, linestyle=':', alpha=0.4, color='gray')

    # Hover tracker dots — one per snappable line, drawn via blit
    ctx.tracker_dots = [
        ax.plot([], [], 'o', markersize=6, animated=True, zorder=6)[0]
        for _ in range(n_snap_lines)
    ]
    ctx.connecting_line, = ax.plot([], [], color='black', lw=1.0, alpha=0.6,
                                    animated=True, zorder=5)
    ctx._hover_bg = None

    if draw_now:
        ctx.canvas.draw()
        ctx._hover_bg = ctx.canvas.copy_from_bbox(ctx.fig.bbox)


def export_canvas_action(ctx):
    if ctx.cache is None:
        show_error(ctx, "No plot to export.")
        return
    file_path, _ = QFileDialog.getSaveFileName(
        ctx.win, "Export View", f"{ctx.cache['store']}_view.png",
        "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)"
    )
    if file_path:
        ctx.fig.savefig(file_path, dpi=300, bbox_inches='tight')
        show_window_toast(ctx, "View Exported")
