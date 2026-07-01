"""
fonts.py
--------
Golden-ratio figure font sizing. Pure matplotlib logic — no Qt dependency,
so this is identical for the tkinter and PyQt6 versions of the GUI.
"""

from .context import _PHI


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
