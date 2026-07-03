"""
context.py
----------
Shared application state, passed explicitly to every function that needs
it. Replaces the module-level globals from the single-file version — a
plain object works fine here (this is a small desktop app, not a service),
but keeping it in one place instead of scattered globals means every
module can see exactly what state exists without hunting for `global`
statements.
"""

import os

_MARKER_COLORS = ["green", "red", "blue", "orange", "purple", "black"]

_PHI = 1.6180339887  # golden ratio


def default_plot_attrs():
    return {
        "title":       None,
        "xlabel":      None,
        "ylabel":      None,
        "title_fs":    24,
        "xlabel_fs":   16,
        "ylabel_fs":   16,
        "leg_fs":      14,
        "leg_loc":     "upper left",
        "leg_entries": None,
        "bold":        True,
    }


def default_settings():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    return {
        "default_folder":      desktop if os.path.isdir(desktop) else os.path.expanduser("~"),
        "decimate_max_points": 2000,
        "background_loading":  True,
        "plot_engine":         "matplotlib",  # "matplotlib" | "pyqtgraph"
    }


class AppState:
    """Holds every piece of mutable state the GUI needs, plus references
    to the widgets built in ui/main_window.py. Widget fields start as
    None and are filled in once during startup."""

    def __init__(self, app):
        # Qt
        self.app = app
        self.win = None
        self.status_bar = None

        # Matplotlib
        self.fig = None
        self.ax = None
        self.canvas = None
        self.rect_selector = None

        # PyQtGraph (GPU) engine — only populated if that engine is used
        self.stacked_plot_widget = None  # QStackedWidget holding both canvases
        self.pg_widget = None
        self.pg_plot_item = None
        self.pg_viewbox = None
        self.pg_lines = []            # (PlotDataItem, full_x, full_y)
        self._pg_axis_probe = None    # (left_axis_w, bottom_axis_h) cache — see sync_pg_margins
        self.pg_hover_scatter = None

        # Toolbar widgets (assigned in ui/toolbar.py)
        self.plot_type_combo = None
        self.btn_window = None
        self.btn_add_marker = None

        # Analysis window (pre/post seconds around a clicked event) — see
        # analysis/window_settings.py for the toolbar button + dialog
        self.window_pre = None
        self.window_post = None
        self.window_symmetric = True

        # Data
        self.cache = None
        self.selected_path = None
        self.last_dir = None  # last folder browsed in any Open dialog
        self.show_corrected = True
        self.show_grid = True
        self.plot_attrs = default_plot_attrs()

        # (engine, id(cache)) the view was last reset-to-fit for. Redraws
        # triggered by things that aren't a fresh data load (grid toggle,
        # marker add/edit, attribute changes) compare against this so they
        # can preserve the current zoom/pan instead of snapping back to the
        # full-data view every time — an actual new dataset OR switching
        # engines (the other engine's view never had valid data in it)
        # resets it.
        self._last_zoomed_key = None

        # Marker mode
        self.marker_mode = False
        self.marker_stamp = {"label": "Marker", "color": "green", "fontsize": 8}

        # Hover / blit
        self.tracker_dots = []
        self.connecting_line = None
        self.active_snap_line = None
        self._hover_bg = None
        self._hover_bg_timer = None  # QTimer instance

        # Pan / drag
        self.is_dragging = False
        self.press_x = None
        self.press_y = None
        self._last_pan_draw_time = 0.0

        # Decimation: (line, full_x, full_y) for every plotted trace, so its
        # rendered vertex count can be kept bounded to the visible pixel
        # range regardless of how many samples the recording actually has.
        self._decim_lines = []

        # Curve fit click capture
        self.slope_clicks = []

        # Settings (Options dialog)
        self.settings = default_settings()

        # Engine-agnostic cache of the computed default title/labels and
        # legend entry order, so Edit Attributes can read/apply consistent
        # values regardless of which engine actually rendered them.
        self._last_title = ""
        self._last_xlabel = ""
        self._last_ylabel = ""
        self._legend_entries = []  # list of label strings, in plotted order

        # Background loading (Options: "Load data files on a background thread")
        self._bg_thread = None
        self._bg_worker = None
