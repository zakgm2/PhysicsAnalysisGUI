"""
interaction.py
---------------
Mouse/view interaction: rect-select zoom, right-click pan, blit-based
hover tracker, scroll zoom, resize-safe zoom, reset zoom.
"""

import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QCursor

from . import plotting
from .markers import place_marker, find_nearest_marker, right_click_marker_menu
from .toasts import show_error, show_window_toast


def on_select(ctx, eclick, erelease):
    if eclick.dblclick:
        return
    if abs(eclick.x - erelease.x) < 10 or abs(eclick.y - erelease.y) < 10:
        return
    x1, y1 = eclick.xdata, eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    if None in [x1, x2, y1, y2]:
        return
    ctx.ax.set_xlim(min(x1, x2), max(x1, x2))
    ctx.ax.set_ylim(min(y1, y2), max(y1, y2))
    ctx.rect_selector.clear()
    _refresh_hover_bg(ctx)
    show_window_toast(ctx, "Zoomed to Selection")


def on_press(ctx, event):
    from .analysis.dispatch import analysis_type

    if event.inaxes != ctx.ax:
        return

    # Double left-click: routed analysis (FFT / PETH / Curve Fit hint)
    if event.dblclick and event.button == 1 and event.xdata is not None:
        ctx.slope_clicks.clear()
        analysis_type(ctx, event.xdata)
        return

    # Marker mode: left-click places, right-click edits, nothing else
    if ctx.marker_mode:
        if event.button == 1 and not event.dblclick and event.xdata is not None:
            place_marker(ctx, event.xdata)
        elif event.button == 3 and event.xdata is not None:
            right_click_marker_menu(ctx, event.xdata, QCursor.pos())
        return

    # Right-click: marker context menu if near one, else pan
    if event.button == 3:
        if event.xdata is not None and find_nearest_marker(ctx, event.xdata) is not None:
            right_click_marker_menu(ctx, event.xdata, QCursor.pos())
        else:
            ctx.is_dragging = True
            ctx.press_x, ctx.press_y = event.x, event.y
        return

    # Curve Fit mode: record mouse-down pixel position for drag detection
    if ctx.plot_type_combo.currentText() == "Curve Fit":
        if event.button == 1 and not event.dblclick:
            ctx.press_x, ctx.press_y = event.x, event.y
        return

    # Middle-click: reset zoom
    if event.button == 2:
        reset_zoom(ctx)


def on_motion(ctx, event):
    ax, canvas, fig = ctx.ax, ctx.canvas, ctx.fig

    # 1. Panning (right-click drag)
    if ctx.is_dragging and event.inaxes == ax and event.x is not None:
        dx, dy = event.x - ctx.press_x, event.y - ctx.press_y
        ctx.press_x, ctx.press_y = event.x, event.y
        bbox = ax.get_window_extent()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        shift_x = (dx / bbox.width) * (xlim[1] - xlim[0])
        shift_y = (dy / bbox.height) * (ylim[1] - ylim[0])
        ax.set_xlim(xlim[0] - shift_x, xlim[1] - shift_x)
        ax.set_ylim(ylim[0] - shift_y, ylim[1] - shift_y)
        canvas.draw_idle()
        return

    # 2. Hover tracker (blit-based)
    hover_ready = (ctx.tracker_dots and ctx.connecting_line is not None and ctx._hover_bg is not None)
    if not hover_ready or event.inaxes != ax or event.xdata is None:
        if hover_ready and not ctx.is_dragging:
            canvas.restore_region(ctx._hover_bg)
            for dot in ctx.tracker_dots:
                dot.set_visible(False)
                ax.draw_artist(dot)
            ctx.connecting_line.set_visible(False)
            ax.draw_artist(ctx.connecting_line)
            canvas.blit(fig.bbox)
            ctx.status_bar.showMessage("X: -- | Y: -- | Pt: --")
        return

    target_x = event.xdata
    y_values_at_x = []
    snap_x = None
    closest_idx = None
    best_y_dist = float('inf')

    visible_lines = [
        l for l in ax.get_lines()
        if not str(l.get_label()).startswith('_')
        and len(l.get_xdata()) > 2
        and l.get_linewidth() >= 1.5
    ]

    for i, line in enumerate(visible_lines):
        x_data = np.asarray(line.get_xdata())
        y_data = np.asarray(line.get_ydata())
        if len(x_data) == 0:
            continue
        idx = int(np.abs(x_data - target_x).argmin())
        snap_x = float(x_data[idx])
        snap_y = float(y_data[idx])
        closest_idx = idx
        y_values_at_x.append(snap_y)

        if i < len(ctx.tracker_dots):
            ctx.tracker_dots[i].set_data([snap_x], [snap_y])
            ctx.tracker_dots[i].set_color(line.get_color())
            ctx.tracker_dots[i].set_visible(True)

        y_dist = abs(snap_y - event.ydata)
        if y_dist < best_y_dist:
            best_y_dist = y_dist
            ctx.active_snap_line = line

    for j in range(len(visible_lines), len(ctx.tracker_dots)):
        ctx.tracker_dots[j].set_visible(False)

    if len(y_values_at_x) >= 2 and snap_x is not None:
        ctx.connecting_line.set_data([snap_x, snap_x],
                                      [min(y_values_at_x), max(y_values_at_x)])
        ctx.connecting_line.set_visible(True)
    else:
        ctx.connecting_line.set_visible(False)

    canvas.restore_region(ctx._hover_bg)
    for dot in ctx.tracker_dots:
        ax.draw_artist(dot)
    ax.draw_artist(ctx.connecting_line)
    canvas.blit(fig.bbox)

    raw_xlbl = ax.get_xlabel() or ctx.plot_attrs.get("xlabel") or "X"
    raw_ylbl = ax.get_ylabel() or ctx.plot_attrs.get("ylabel") or "Y"
    clean_x = str(raw_xlbl).strip() or "X"
    clean_y = str(raw_ylbl).strip() or "Y"
    pt_str = str(closest_idx) if closest_idx is not None else "--"
    ctx.status_bar.showMessage(f"{clean_x}: {event.xdata:.2f} | {clean_y}: {event.ydata:.4f} | Pt: {pt_str}")


def _refresh_hover_bg(ctx):
    """Full redraw + recapture blit background. Call after view changes settle."""
    ctx._hover_bg_timer = None

    saved_dots = [(list(d.get_xdata()), list(d.get_ydata())) for d in ctx.tracker_dots]
    saved_conn = (list(ctx.connecting_line.get_xdata()), list(ctx.connecting_line.get_ydata())) \
        if ctx.connecting_line is not None else ([], [])
    for dot in ctx.tracker_dots:
        dot.set_data([], [])
    if ctx.connecting_line is not None:
        ctx.connecting_line.set_data([], [])

    plotting._apply_plot_attrs(ctx)
    ctx.canvas.draw()
    ctx._hover_bg = ctx.canvas.copy_from_bbox(ctx.fig.bbox)

    for dot, (xd, yd) in zip(ctx.tracker_dots, saved_dots):
        dot.set_data(xd, yd)
    if ctx.connecting_line is not None:
        ctx.connecting_line.set_data(*saved_conn)

    if any(len(d.get_xdata()) > 0 for d in ctx.tracker_dots):
        ctx.canvas.restore_region(ctx._hover_bg)
        for dot in ctx.tracker_dots:
            ctx.ax.draw_artist(dot)
        if ctx.connecting_line is not None and len(ctx.connecting_line.get_xdata()) > 0:
            ctx.ax.draw_artist(ctx.connecting_line)
        ctx.canvas.blit(ctx.fig.bbox)


def _schedule_hover_bg_refresh(ctx, delay_ms=150):
    if ctx._hover_bg_timer is not None:
        ctx._hover_bg_timer.stop()
    ctx._hover_bg_timer = QTimer()
    ctx._hover_bg_timer.setSingleShot(True)
    ctx._hover_bg_timer.timeout.connect(lambda: _refresh_hover_bg(ctx))
    ctx._hover_bg_timer.start(delay_ms)


def on_release(ctx, event):
    from .analysis.curve_fit import launch_curve_fit

    was_dragging = ctx.is_dragging
    ctx.is_dragging = False
    if was_dragging:
        _refresh_hover_bg(ctx)

    if (ctx.plot_type_combo.currentText() == "Curve Fit"
            and event.button == 1
            and event.inaxes == ctx.ax
            and event.xdata is not None):

        dx = abs(event.x - ctx.press_x) if ctx.press_x is not None else 999
        dy = abs(event.y - ctx.press_y) if ctx.press_y is not None else 999
        if dx > 5 or dy > 5:
            return

        try:
            snap_line = ctx.active_snap_line
            if snap_line is None:
                all_lines = ctx.ax.get_lines()
                for line in all_lines:
                    label = str(line.get_label()).lower()
                    if 'mean' in label or 'average' in label or 'avg' in label:
                        snap_line = line
                        break
                if snap_line is None:
                    valid = [l for l in all_lines if len(l.get_xdata()) > 2
                             and l.get_linewidth() >= 1.5]
                    snap_line = valid[-1] if valid else None

            if snap_line is None:
                show_error(ctx, "No active data trace found to analyze.")
                return

            x_data = snap_line.get_xdata()
            nearest_idx = int(np.abs(x_data - event.xdata).argmin())
            ctx.slope_clicks.append((nearest_idx, event.xdata))
            show_window_toast(ctx, f"Point {len(ctx.slope_clicks)}: {event.xdata:.2f}s")

            if len(ctx.slope_clicks) == 2:
                launch_curve_fit(ctx, snap_line, ctx.slope_clicks[0], ctx.slope_clicks[1])
                ctx.slope_clicks.clear()
        except Exception as e:
            show_error(ctx, f"Curve fit capture failed: {e}")
            ctx.slope_clicks.clear()


def zoom_factory(ctx, base_scale=1.2):
    ax = ctx.ax

    def zoom_fun(event):
        if event.x is None or event.y is None:
            return
        bbox = ax.get_window_extent()
        is_on_x = event.y < bbox.ymin
        is_on_y = event.x < bbox.xmin
        is_inside = event.inaxes == ax
        scale_factor = 1 / base_scale if event.button == 'up' else \
            base_scale if event.button == 'down' else None
        if scale_factor is None:
            return
        cur_xlim, cur_ylim = ax.get_xlim(), ax.get_ylim()
        if is_on_x and not is_on_y:
            xdata = event.xdata if event.xdata is not None else sum(cur_xlim) / 2
            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            rel_x = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
            ax.set_xlim([xdata - new_width * (1 - rel_x), xdata + new_width * rel_x])
        elif is_on_y and not is_on_x:
            ydata = event.ydata if event.ydata is not None else sum(cur_ylim) / 2
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
            rel_y = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
            ax.set_ylim([ydata - new_height * (1 - rel_y), ydata + new_height * rel_y])
        elif is_inside and event.xdata is not None and event.ydata is not None:
            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
            rel_x = (cur_xlim[1] - event.xdata) / (cur_xlim[1] - cur_xlim[0])
            rel_y = (cur_ylim[1] - event.ydata) / (cur_ylim[1] - cur_ylim[0])
            ax.set_xlim([event.xdata - new_width * (1 - rel_x), event.xdata + new_width * rel_x])
            ax.set_ylim([event.ydata - new_height * (1 - rel_y), event.ydata + new_height * rel_y])
        ctx._hover_bg = None
        ctx.canvas.draw_idle()
        _schedule_hover_bg_refresh(ctx)

    return zoom_fun


def on_resize(ctx, event):
    ctx._hover_bg = None
    _schedule_hover_bg_refresh(ctx, delay_ms=250)


def reset_zoom(ctx):
    if ctx.cache is None:
        return
    ctx.ax.set_xlim(ctx.cache['x'][0], ctx.cache['x'][-1])
    ctx.ax.autoscale(axis='y')
    _refresh_hover_bg(ctx)
    ctx.canvas.draw_idle()
