"""
markers.py
----------
Add/Edit Marker dialog, marker placement, nearest-marker lookup, and the
right-click rename/delete context menu.
"""

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QLineEdit, QWidget, QHBoxLayout,
    QRadioButton, QButtonGroup, QPushButton, QMenu,
)

from .context import _MARKER_COLORS
from .toasts import show_window_toast


class MarkerDialog(QDialog):
    """Add-or-edit marker dialog: name, colour radio group, font size."""

    def __init__(self, parent, title, initial_label="Marker",
                 initial_color="green", initial_fontsize=8):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        layout = QGridLayout(self)

        layout.addWidget(QLabel("Marker name:"), 0, 0)
        self.e_name = QLineEdit(initial_label)
        self.e_name.selectAll()
        layout.addWidget(self.e_name, 0, 1)

        layout.addWidget(QLabel("Colour:"), 1, 0)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        self.color_group = QButtonGroup(self)
        for i, col in enumerate(_MARKER_COLORS):
            rb = QRadioButton(col)
            rb.setStyleSheet(f"color: {col};")
            if col == initial_color:
                rb.setChecked(True)
            self.color_group.addButton(rb, i)
            color_layout.addWidget(rb)
        layout.addWidget(color_row, 1, 1)

        layout.addWidget(QLabel("Font size:"), 2, 0)
        self.e_fontsize = QLineEdit(str(initial_fontsize))
        self.e_fontsize.setFixedWidth(50)
        layout.addWidget(self.e_fontsize, 2, 1)

        btn = QPushButton("OK")
        btn.setDefault(True)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, 3, 0, 1, 2)

        self.e_name.setFocus()

    def values(self):
        label = self.e_name.text().strip() or "Marker"
        checked = self.color_group.checkedButton()
        color = checked.text() if checked else "green"
        try:
            fontsize = max(4, int(self.e_fontsize.text()))
        except ValueError:
            fontsize = 8
        return label, color, fontsize


def toggle_marker_mode(ctx):
    from .plotting import simple_plot  # local import: avoid module cycle at import time
    ctx.marker_mode = not ctx.marker_mode
    ctx.btn_add_marker.setStyleSheet(
        "background-color: #FFD54F;" if ctx.marker_mode else ""
    )
    show_window_toast(ctx, "Marker mode ON — click the plot" if ctx.marker_mode
                       else "Marker mode OFF")


def place_marker(ctx, t):
    from .plotting import simple_plot
    if ctx.cache is None:
        return
    dlg = MarkerDialog(ctx.win, "New Marker")
    if dlg.exec() == QDialog.DialogCode.Accepted:
        label, color, fontsize = dlg.values()
        ctx.cache['markers'].append({"time": t, "label": label, "color": color, "fontsize": fontsize})
        simple_plot(ctx)


def find_nearest_marker(ctx, t, tol_s=2.0):
    if ctx.cache is None or not ctx.cache['markers']:
        return None
    dists = [abs(m['time'] - t) for m in ctx.cache['markers']]
    idx = int(np.argmin(dists))
    return idx if dists[idx] <= tol_s else None


def right_click_marker_menu(ctx, xdata, global_pos):
    from .plotting import simple_plot
    if ctx.cache is None or xdata is None:
        return
    idx = find_nearest_marker(ctx, xdata)
    if idx is None:
        return
    marker = ctx.cache['markers'][idx]

    menu = QMenu(ctx.win)
    act_rename = menu.addAction(f"Rename '{marker['label']}'")
    act_delete = menu.addAction(f"Delete '{marker['label']}'")
    chosen = menu.exec(global_pos)

    if chosen == act_rename:
        dlg = MarkerDialog(ctx.win, "Edit Marker", marker['label'],
                            marker.get('color', 'green'), marker.get('fontsize', 8))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            label, color, fontsize = dlg.values()
            marker['label'], marker['color'], marker['fontsize'] = label, color, fontsize
            simple_plot(ctx)
    elif chosen == act_delete:
        ctx.cache['markers'].pop(idx)
        simple_plot(ctx)
