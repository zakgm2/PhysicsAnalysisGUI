"""
markers.py
----------
Add/Edit Marker dialog, marker placement, nearest-marker lookup, and the
right-click rename/delete context menu.
"""

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QGridLayout, QVBoxLayout, QLabel, QLineEdit, QWidget, QHBoxLayout,
    QRadioButton, QButtonGroup, QPushButton, QMenu, QGroupBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
)
from PyQt6.QtCore import Qt

from .context import _MARKER_COLORS
from .toasts import show_error, show_success, show_window_toast


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


class AddMarkerDialog(QDialog):
    """Add Marker entry point: bulk-add every auto-detected marker of a
    chosen store, or configure a custom name/colour/fontsize and start
    repeated click-to-place stamping (Snipping-Tool style)."""

    def __init__(self, ctx):
        super().__init__(ctx.win)
        self.ctx = ctx
        self.start_requested = False
        self.setWindowTitle("Add Marker")
        self.setModal(True)
        layout = QVBoxLayout(self)

        # ---- bulk-add auto-detected markers (multi-select stores) --------
        detected = (ctx.cache or {}).get('detected_markers', [])
        stores = sorted({m['store'] for m in detected if m.get('store')})

        box1 = QGroupBox("Add / Remove Auto-Detected Markers")
        l1 = QVBoxLayout(box1)
        if stores:
            l1.addWidget(QLabel("Select one or more stores (ctrl/shift-click to "
                                 "multi-select) and Add Selected or Remove Selected."))
            self.store_list = QListWidget()
            self.store_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.store_list.addItems(stores)
            self.store_list.setFixedHeight(min(120, 22 * len(stores) + 4))
            l1.addWidget(self.store_list)
            store_btn_row = QHBoxLayout()
            btn_add_selected = QPushButton("Add Selected")
            btn_add_selected.clicked.connect(self._add_selected_stores)
            store_btn_row.addWidget(btn_add_selected)
            btn_remove_selected_stores = QPushButton("Remove Selected")
            btn_remove_selected_stores.clicked.connect(self._remove_selected_stores)
            store_btn_row.addWidget(btn_remove_selected_stores)
            l1.addLayout(store_btn_row)
        else:
            self.store_list = None
            l1.addWidget(QLabel("No auto-detected markers for this dataset."))
        layout.addWidget(box1)

        # ---- remove markers currently on the plot (multi-select) ---------
        box3 = QGroupBox("Remove Markers")
        l3 = QVBoxLayout(box3)
        current = ctx.cache.get('markers', []) if ctx.cache else []
        if current:
            l3.addWidget(QLabel("Covers both auto-detected and custom-placed markers. "
                                 "Ctrl/shift-click to multi-select."))
            self.marker_list = QListWidget()
            self.marker_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            for i, m in enumerate(current):
                text = f"{m['label']}  @ {m['time']:.2f}s"
                if m.get('store'):
                    text += f"   [{m['store']}]"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.marker_list.addItem(item)
            self.marker_list.setFixedHeight(min(160, 22 * len(current) + 4))
            l3.addWidget(self.marker_list)
            btn_row = QHBoxLayout()
            btn_select_all = QPushButton("Select All")
            btn_select_all.clicked.connect(self.marker_list.selectAll)
            btn_row.addWidget(btn_select_all)
            btn_remove_selected = QPushButton("Remove Selected")
            btn_remove_selected.clicked.connect(self._remove_selected_markers)
            btn_row.addWidget(btn_remove_selected)
            l3.addLayout(btn_row)
        else:
            self.marker_list = None
            l3.addWidget(QLabel("No markers currently on the plot."))
        layout.addWidget(box3)

        # ---- configure + start custom placement --------------------------
        box2 = QGroupBox("Place Custom Markers")
        l2 = QGridLayout(box2)
        stamp = ctx.marker_stamp

        l2.addWidget(QLabel("Marker name:"), 0, 0)
        self.e_name = QLineEdit(stamp["label"])
        self.e_name.selectAll()
        l2.addWidget(self.e_name, 0, 1)

        l2.addWidget(QLabel("Colour:"), 1, 0)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        self.color_group = QButtonGroup(self)
        for i, col in enumerate(_MARKER_COLORS):
            rb = QRadioButton(col)
            rb.setStyleSheet(f"color: {col};")
            if col == stamp["color"]:
                rb.setChecked(True)
            self.color_group.addButton(rb, i)
            color_layout.addWidget(rb)
        l2.addWidget(color_row, 1, 1)

        l2.addWidget(QLabel("Font size:"), 2, 0)
        self.e_fontsize = QLineEdit(str(stamp["fontsize"]))
        self.e_fontsize.setFixedWidth(50)
        l2.addWidget(self.e_fontsize, 2, 1)

        l2.addWidget(QLabel("Click the plot to stamp a marker with this name/colour "
                             "repeatedly; click 'Add Marker' again to stop."),
                     3, 0, 1, 2)

        btn_start = QPushButton("Start Placing")
        btn_start.setDefault(True)
        btn_start.clicked.connect(self._start)
        l2.addWidget(btn_start, 4, 0, 1, 2)
        layout.addWidget(box2)

        self.e_name.setFocus()

    def _add_selected_stores(self):
        selected_stores = {item.text() for item in self.store_list.selectedItems()}
        if not selected_stores:
            show_error(self.ctx, "Select at least one store first.")
            return
        detected = self.ctx.cache.get('detected_markers', [])
        to_add = [dict(m) for m in detected if m.get('store') in selected_stores]
        self.ctx.cache['markers'].extend(to_add)
        from .plotting import simple_plot
        simple_plot(self.ctx)
        show_success(self.ctx, f"Added {len(to_add)} marker(s) from "
                                f"{len(selected_stores)} store(s)")
        self.accept()

    def _remove_selected_stores(self):
        selected_stores = {item.text() for item in self.store_list.selectedItems()}
        if not selected_stores:
            show_error(self.ctx, "Select at least one store first.")
            return
        before = len(self.ctx.cache['markers'])
        self.ctx.cache['markers'] = [m for m in self.ctx.cache['markers']
                                      if m.get('store') not in selected_stores]
        removed = before - len(self.ctx.cache['markers'])
        from .plotting import simple_plot
        simple_plot(self.ctx)
        show_success(self.ctx, f"Removed {removed} marker(s) from "
                                f"{len(selected_stores)} store(s)")
        self.accept()

    def _remove_selected_markers(self):
        selected_items = self.marker_list.selectedItems()
        if not selected_items:
            show_error(self.ctx, "Select at least one marker first.")
            return
        indices = sorted((item.data(Qt.ItemDataRole.UserRole) for item in selected_items),
                          reverse=True)
        for i in indices:
            self.ctx.cache['markers'].pop(i)
        from .plotting import simple_plot
        simple_plot(self.ctx)
        show_success(self.ctx, f"Removed {len(indices)} marker(s)")
        self.accept()

    def _start(self):
        label = self.e_name.text().strip() or "Marker"
        checked = self.color_group.checkedButton()
        color = checked.text() if checked else "green"
        try:
            fontsize = max(4, int(self.e_fontsize.text()))
        except ValueError:
            fontsize = 8
        self.ctx.marker_stamp = {"label": label, "color": color, "fontsize": fontsize}
        self.start_requested = True
        self.accept()


def toggle_marker_mode(ctx):
    """Turn placement mode off, or (when off) open the Add Marker dialog to
    configure and start it."""
    if ctx.marker_mode:
        ctx.marker_mode = False
        ctx.btn_add_marker.setStyleSheet("")
        ctx.btn_add_marker.setText("Add Marker")
        show_window_toast(ctx, "Marker mode OFF")
        return

    if ctx.cache is None:
        show_error(ctx, "Load a dataset first.")
        return

    dlg = AddMarkerDialog(ctx)
    if dlg.exec() == QDialog.DialogCode.Accepted and dlg.start_requested:
        ctx.marker_mode = True
        label = ctx.marker_stamp["label"]
        ctx.btn_add_marker.setStyleSheet("background-color: #FFD54F;")
        ctx.btn_add_marker.setText(f"Placing '{label}'…")
        show_window_toast(ctx, f"Placing '{label}' markers — click the plot, "
                                "click Add Marker again to stop")


def place_marker(ctx, t):
    """Stamp a marker at time t using the currently configured marker_stamp.
    No dialog — placement mode stays active for repeated clicks until the
    user explicitly turns Add Marker off (Snipping-Tool style)."""
    from .plotting import simple_plot
    if ctx.cache is None:
        return
    ctx.cache['markers'].append({"time": t, **ctx.marker_stamp})
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
