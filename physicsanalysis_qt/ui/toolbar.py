"""
ui/toolbar.py
---------------
Builds the top toolbar: Open menu, grid toggle, analysis mode dropdown,
marker controls, view controls.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QMenu, QCheckBox, QLabel,
    QComboBox,
)

from ..loaders.tdt import open_folder, reload_folder
from ..loaders.oxysoft import open_file, reload_file
from ..loaders.generic import launch_generic_file_loader, reload_generic
from ..loaders.pt2 import launch_pt2_viewer
from ..markers import toggle_marker_mode
from ..sidecar import save_markers
from ..interaction import reset_zoom
from ..plotting import export_canvas_action, set_grid_visibility
from ..attributes import open_attributes_window
from ..options import open_options_dialog
from ..toasts import show_error
from ..analysis.window_settings import init_window_settings, open_window_dialog, _window_button_text
from ..analysis.intervals import launch_intervals


def _toggle_grid(ctx, state):
    set_grid_visibility(ctx, state)


def _reload_current(ctx):
    """Re-read whatever's currently loaded from disk, in place — not the
    same thing as Open, which always prompts a file picker. Falls back to
    Open only when nothing's loaded yet (there's nothing to reload)."""
    if ctx.cache is None:
        open_folder(ctx)
        return
    source = ctx.cache.get('source')
    path = ctx.cache.get('source_path')
    if not path:
        show_error(ctx, "Nothing to reload — no source file/folder on record.")
        return
    if source == 'TDT':
        reload_folder(ctx, path)
    elif source == 'Oxysoft':
        reload_file(ctx, path)
    elif source == 'Generic':
        reload_generic(ctx, path)
    else:
        show_error(ctx, f"Reload isn't supported for '{source}' data.")


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
    btn_reload.clicked.connect(lambda: _reload_current(ctx))
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

    init_window_settings(ctx)
    ctx.btn_window = QPushButton(_window_button_text(ctx))
    ctx.btn_window.clicked.connect(lambda: open_window_dialog(ctx))
    layout.addWidget(ctx.btn_window)

    layout.addWidget(QLabel("|"))

    ctx.btn_add_marker = QPushButton("Add Marker")
    ctx.btn_add_marker.clicked.connect(lambda: toggle_marker_mode(ctx))
    layout.addWidget(ctx.btn_add_marker)

    btn_save_markers = QPushButton("Save Markers")
    btn_save_markers.clicked.connect(lambda: save_markers(ctx))
    layout.addWidget(btn_save_markers)

    btn_intervals = QPushButton("Measure Intervals")
    btn_intervals.clicked.connect(lambda: launch_intervals(ctx))
    layout.addWidget(btn_intervals)

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
