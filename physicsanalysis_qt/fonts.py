"""
fonts.py
--------
Golden-ratio figure font sizing. Pure matplotlib logic — no Qt dependency,
so this is identical for the tkinter and PyQt6 versions of the GUI. Also
includes main-plot font scaling shared by both plot engines.
"""

from .context import _PHI

# Reference plot-widget size the main-plot font sizes in ctx.plot_attrs
# were tuned against. Scaling relative to this (rather than using the
# configured sizes as fixed absolute values) keeps text proportional to
# the plot area as the window is resized, and keeps the two engines
# visually consistent — matplotlib renders text into a fixed-DPI raster
# image, PyQtGraph renders native Qt fonts at the OS's own DPI, so the
# same literal point size looks different in each; scaling both from the
# same widget-size ratio is what actually keeps them looking the same.
_MAIN_PLOT_REF_W = 1180
_MAIN_PLOT_REF_H = 700


def main_plot_scale(widget):
    """Scale factor for main-plot fonts, relative to _MAIN_PLOT_REF_*."""
    if widget is None:
        return 1.0
    w, h = widget.width(), widget.height()
    if w <= 0 or h <= 0:
        return 1.0
    diag = (w ** 2 + h ** 2) ** 0.5
    ref_diag = (_MAIN_PLOT_REF_W ** 2 + _MAIN_PLOT_REF_H ** 2) ** 0.5
    return diag / ref_diag


def fig_font_sizes(fig):
    """
    Return (title_fs, label_fs, legend_fs) using the golden ratio.

    Title scales linearly with the figure diagonal. Each tier down is
    title / phi, then title / phi^2. Anchor: 8x4 in diagonal (~8.94 in)
    -> title ~ 24 pt. Halved when the figure contains multiple subplots.
    """
    diag = (fig.get_figwidth() ** 2 + fig.get_figheight() ** 2) ** 0.5
    title_fs = max(8, round(diag * (24 / ((8**2 + 4**2) ** 0.5))))
    label_fs = max(6, round(title_fs / _PHI))
    leg_fs = max(5, round(label_fs / _PHI))
    if len(fig.axes) > 1:
        title_fs = max(6, title_fs // 2)
        label_fs = max(5, label_fs // 2)
        leg_fs = max(4, leg_fs // 2)
    return title_fs, label_fs, leg_fs
