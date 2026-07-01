"""
analysis/dispatch.py
----------------------
Routes double-clicks on the main plot to the right analysis window, and
the shared figure-export helper used by all of them.
"""

import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog

from ..toasts import show_error, show_window_toast


def get_window(ctx):
    try:
        val = float(ctx.window_entry.text())
        return val if val > 0 else 30.0
    except ValueError:
        return 30.0


def export_figure_to_file(ctx, fig_obj, default_prefix, tracking_info=""):
    ts = datetime.datetime.now().strftime("%H%M%S")
    store_name = ctx.cache.get('store', 'Data') if ctx.cache else 'Data'
    suffix = f"_{tracking_info}" if tracking_info else ""
    fpath, _ = QFileDialog.getSaveFileName(
        ctx.win, f"Export {default_prefix} Visualization",
        f"{default_prefix}_{store_name}{suffix}_{ts}.png",
        "PNG Image (*.png);;PDF Document (*.pdf);;SVG Vector (*.svg)"
    )
    if fpath:
        try:
            fig_obj.savefig(fpath, dpi=300, bbox_inches='tight')
            show_window_toast(ctx, f"{default_prefix} Exported")
        except Exception as e:
            show_error(ctx, f"Export Failed: {e}")


def analysis_type(ctx, clicked_x):
    from .fft import launch_fft
    from .peth import launch_zscore_peth

    if clicked_x is None:
        return
    try:
        center_timestamp = float(clicked_x)
    except (ValueError, TypeError):
        show_error(ctx, "Invalid coordinate format captured.")
        return

    current_mode = ctx.plot_type_combo.currentText()
    if current_mode == "Curve Fit":
        show_window_toast(ctx, "In Curve Fit Mode: use single-clicks to anchor two points.")
        return

    # The dialogs below block via QDialog.exec() while this call is still
    # inside on_press's double-click handler. matplotlib dispatches
    # button_press_event to callbacks in registration order — ours runs
    # first, RectangleSelector's own handler runs second — so its handler
    # for this same press hasn't fired yet. Deactivating it now means that
    # pending dispatch is a no-op. Reactivating must NOT happen synchronously
    # in a `finally` here: that would still run before this function returns
    # control to matplotlib's dispatcher, so RectangleSelector's press handler
    # would immediately start a fresh drag with no release event left to end
    # it (the real release already got consumed inside the dialog's nested
    # event loop). Defer reactivation to the next Qt tick instead.
    ctx.rect_selector.set_active(False)
    try:
        if current_mode == "FFT":
            launch_fft(ctx, center_timestamp)
        elif current_mode in ("Z-Score PETH", "PETH"):
            launch_zscore_peth(ctx, center_timestamp)
    finally:
        def _reactivate():
            ctx.rect_selector.clear()
            ctx.rect_selector.set_active(True)
        QTimer.singleShot(0, _reactivate)
