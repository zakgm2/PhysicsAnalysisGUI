"""
ui/toolbar.py
---------------
Builds the top toolbar: Open menu, grid toggle, analysis mode dropdown,
marker controls, view controls.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QMenu, QCheckBox, QLabel,
    QComboBox, QLineEdit,
)

from ..loaders.tdt import open_folder
from ..loaders.oxysoft import open_file
from ..loaders.generic import launch_generic_file_loader
from ..loaders.pt2 import launch_pt2_viewer
from ..markers import toggle_marker_mode
from ..sidecar import save_markers
from ..interaction import reset_zoom
from ..plotting import simple_plot, export_canvas_action
from ..attributes import open_attributes_window
from ..options import open_options_dialog


def _toggle_grid(ctx, state):
    ctx.show_grid = bool(state)
    if ctx.cache is not None:
        simple_plot(ctx)


def _undo_last_marker(ctx):
    if ctx.cache and ctx.cache['markers']:
        ctx.cache['markers'].pop()
        simple_plot(ctx)


def build_toolbar(ctx):
    toolbar = QWidget()
    layout = QHBoxLayout(toolbar)
    layout.setContentsMargins(8, 6, 8, 6)

    open_menu_btn = QPushButton("Open ▾")
    open_menu = QMenu(open_menu_btn)
    open_menu.addAction("Open TDT Folder", lambda: open_folder(ctx))
    open_menu.addAction("Open TXT (Oxysoft)", lambda: open_file(ctx))
    open_menu.addAction("Open Excel/CSV/TSV", lambda: launch_generic_file_loader(ctx))
    open_menu.addAction("Open PT2 (EFNMR)", lambda: launch_pt2_viewer(ctx))
    open_menu_btn.setMenu(open_menu)
    layout.addWidget(open_menu_btn)

    btn_reload = QPushButton("Reload")
    btn_reload.clicked.connect(lambda: open_folder(ctx))
    layout.addWidget(btn_reload)

    layout.addWidget(QLabel("|"))

    grid_check = QCheckBox("Grid")
    grid_check.setChecked(True)
    grid_check.stateChanged.connect(lambda state: _toggle_grid(ctx, state))
    layout.addWidget(grid_check)

    layout.addWidget(QLabel("|"))

    ctx.plot_type_combo = QComboBox()
    ctx.plot_type_combo.addItems(["Analysis", "Z-Score PETH", "FFT", "Curve Fit"])
    layout.addWidget(ctx.plot_type_combo)

    layout.addWidget(QLabel("Window (s):"))
    ctx.window_entry = QLineEdit("30")
    ctx.window_entry.setFixedWidth(50)
    layout.addWidget(ctx.window_entry)

    layout.addWidget(QLabel("|"))

    ctx.btn_add_marker = QPushButton("Add Marker")
    ctx.btn_add_marker.clicked.connect(lambda: toggle_marker_mode(ctx))
    layout.addWidget(ctx.btn_add_marker)

    btn_undo_marker = QPushButton("Undo Last")
    btn_undo_marker.clicked.connect(lambda: _undo_last_marker(ctx))
    layout.addWidget(btn_undo_marker)

    btn_save_markers = QPushButton("Save Markers")
    btn_save_markers.clicked.connect(lambda: save_markers(ctx))
    layout.addWidget(btn_save_markers)

    layout.addWidget(QLabel("|"))

    btn_reset_zoom = QPushButton("Reset Zoom")
    btn_reset_zoom.clicked.connect(lambda: reset_zoom(ctx))
    layout.addWidget(btn_reset_zoom)

    btn_export_view = QPushButton("Export View (PNG/PDF)")
    btn_export_view.clicked.connect(lambda: export_canvas_action(ctx))
    layout.addWidget(btn_export_view)

    btn_edit_attrs = QPushButton("Edit Attributes")
    btn_edit_attrs.clicked.connect(lambda: open_attributes_window(ctx))
    layout.addWidget(btn_edit_attrs)

    layout.addWidget(QLabel("|"))

    btn_options = QPushButton("Options")
    btn_options.clicked.connect(lambda: open_options_dialog(ctx))
    layout.addWidget(btn_options)

    layout.addStretch(1)
    return toolbar
