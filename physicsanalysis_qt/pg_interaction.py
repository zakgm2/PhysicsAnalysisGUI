"""
pg_interaction.py
------------------
Mouse interaction for the PyQtGraph main-plot engine: hover snap +
coordinate readout, click dispatch (analysis/marker-place/curve-fit),
and the right-click marker rename/delete menu. Split out of pg_engine.py,
which now only builds/renders the plot — mirrors the matplotlib engine's
own plotting.py / interaction.py split.
"""

import numpy as np
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMenu

from .markers import MARKER_HIT_PX, place_marker, find_nearest_marker, open_edit_marker_dialog
from .toasts import show_error, show_window_toast


def _nearest_index(full_x, x):
    return int(np.abs(full_x - x).argmin())


def _marker_hit_tolerance(ctx):
    """MARKER_HIT_PX on-screen pixels -> data-space seconds under the
    ViewBox's current view range, so the hit-test radius around a marker
    stays a constant size on screen instead of ballooning at high zoom —
    see interaction.py's own copy of this for the matplotlib engine."""
    vb = ctx.pg_viewbox
    width_px = vb.width()
    if not width_px:
        return 2.0
    (x0, x1), _ = vb.viewRange()
    return MARKER_HIT_PX * (x1 - x0) / width_px


def on_pg_mouse_moved(ctx, scene_pos):
    plot_item = ctx.pg_plot_item
    if plot_item is None or ctx.cache is None or not ctx.pg_lines:
        return
    if not plot_item.sceneBoundingRect().contains(scene_pos):
        ctx.pg_hover_scatter.hide()
        ctx.status_bar.showMessage("X: -- | Y: -- | Pt: --")
        return

    view_pos = ctx.pg_viewbox.mapSceneToView(scene_pos)
    target_x, target_y = view_pos.x(), view_pos.y()

    points = []
    best_idx = None
    best_y_dist = float('inf')
    for item, fx, fy in ctx.pg_lines:
        if len(fx) == 0:
            continue
        idx = _nearest_index(fx, target_x)
        snap_x, snap_y = float(fx[idx]), float(fy[idx])
        points.append((snap_x, snap_y))
        y_dist = abs(snap_y - target_y)
        if y_dist < best_y_dist:
            best_y_dist = y_dist
            best_idx = idx

    if points:
        ctx.pg_hover_scatter.setData(pos=points)
        ctx.pg_hover_scatter.show()

    x_label = plot_item.getAxis('bottom').labelText or "X"
    y_label = plot_item.getAxis('left').labelText or "Y"
    pt_str = str(best_idx) if best_idx is not None else "--"
    ctx.status_bar.showMessage(f"{x_label}: {target_x:.2f} | {y_label}: {target_y:.4f} | Pt: {pt_str}")


def on_pg_mouse_clicked(ctx, ev):
    from PyQt6.QtCore import Qt
    from .analysis.dispatch import analysis_type
    from .analysis.curve_fit import launch_curve_fit

    plot_item = ctx.pg_plot_item
    if plot_item is None or ctx.cache is None:
        return
    if not plot_item.sceneBoundingRect().contains(ev.scenePos()):
        return

    view_pos = ctx.pg_viewbox.mapSceneToView(ev.scenePos())
    x = view_pos.x()

    if ev.double() and ev.button() == Qt.MouseButton.LeftButton:
        ctx.slope_clicks.clear()
        analysis_type(ctx, x)
        return

    if ctx.marker_mode:
        if ev.button() == Qt.MouseButton.LeftButton:
            place_marker(ctx, x)
        elif ev.button() == Qt.MouseButton.RightButton:
            _right_click_marker_menu(ctx, x, ev.screenPos(), _marker_hit_tolerance(ctx))
        return

    if ev.button() == Qt.MouseButton.RightButton:
        tol_s = _marker_hit_tolerance(ctx)
        if find_nearest_marker(ctx, x, tol_s) is not None:
            _right_click_marker_menu(ctx, x, ev.screenPos(), tol_s)
        return

    if ctx.plot_type_combo.currentText() == "Curve Fit" and ev.button() == Qt.MouseButton.LeftButton:
        if not ctx.pg_lines:
            return
        # Pick whichever tracked line is closest in y to the click, same
        # heuristic the matplotlib engine uses for active_snap_line.
        best_line, best_dist = None, float('inf')
        for item, fx, fy in ctx.pg_lines:
            idx = _nearest_index(fx, x)
            dist = abs(float(fy[idx]) - view_pos.y())
            if dist < best_dist:
                best_dist = dist
                best_line = (fx, fy)
        if best_line is None:
            show_error(ctx, "No active data trace found to analyze.")
            return
        fx, _ = best_line
        idx = _nearest_index(fx, x)
        ctx.slope_clicks.append((idx, x))
        show_window_toast(ctx, f"Point {len(ctx.slope_clicks)}: {x:.2f}s")
        if len(ctx.slope_clicks) == 2:
            launch_curve_fit(ctx, None, ctx.slope_clicks[0], ctx.slope_clicks[1])
            ctx.slope_clicks.clear()
        return

    if ctx.splice_click_mode and ev.button() == Qt.MouseButton.LeftButton:
        # Never wired up for this engine — only interaction.py (matplotlib)
        # had the click-to-anchor handling, so Splice mode silently did
        # nothing here. No line-snapping needed (unlike Curve Fit above):
        # a splice range is a time boundary, not tied to a signal's value.
        from .analysis.splice import apply_splice_at_points

        ctx.slope_clicks.append(x)
        show_window_toast(ctx, f"Point {len(ctx.slope_clicks)}: {x:.2f}s")
        if len(ctx.slope_clicks) == 2:
            t1, t2 = ctx.slope_clicks
            ctx.slope_clicks.clear()
            apply_splice_at_points(ctx, t1, t2)


def _right_click_marker_menu(ctx, xdata, global_pos, tol_s=2.0):
    from .pg_engine import pg_simple_plot  # local import: avoid module cycle at import time
    from .marker_labels import marker_display_label
    from .markers import delete_all_same_name
    from .toasts import show_success

    idx = find_nearest_marker(ctx, xdata, tol_s)
    if idx is None:
        return
    marker = ctx.cache['markers'][idx]
    name = marker_display_label(ctx, marker)

    menu = QMenu(ctx.win)
    act_rename = menu.addAction(f"Rename '{name}'")
    act_delete = menu.addAction(f"Delete '{name}'")
    act_delete_all = menu.addAction(f"Delete all '{name}' markers")
    chosen = menu.exec(QPoint(int(global_pos.x()), int(global_pos.y())))

    if chosen == act_rename:
        if open_edit_marker_dialog(ctx, marker):
            pg_simple_plot(ctx)
    elif chosen == act_delete:
        ctx.cache['markers'].pop(idx)
        pg_simple_plot(ctx)
    elif chosen == act_delete_all:
        removed = delete_all_same_name(ctx, marker)
        pg_simple_plot(ctx)
        show_success(ctx, f"Deleted {removed} '{name}' marker(s)")
