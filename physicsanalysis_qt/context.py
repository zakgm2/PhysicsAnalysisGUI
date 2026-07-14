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

import json
import os
from pathlib import Path

_MARKER_COLORS = ["green", "red", "blue", "orange", "purple", "black"]

_PHI = 1.6180339887  # golden ratio

_SETTINGS_PATH = Path.home() / ".physicsanalysis" / "settings.json"


def load_settings():
    settings = default_settings()
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        settings.update({k: v for k, v in saved.items() if k in settings})
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return settings


def save_settings(settings):
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)


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
        "theme":               "light",       # "light" | "dark"
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

        # Store id -> renamed display name (e.g. 'PP1_' -> 'Left Lever'),
        # set via right-click Edit Marker's "rename all" toggle — see
        # marker_labels.py. The store id itself never changes, only how
        # it's displayed everywhere (plot, dialogs, Event Intervals table).
        self.store_labels = {}

        # Data
        self.cache = None
        self.selected_path = None
        self.last_dir = None  # last folder browsed in any Open dialog
        self.show_corrected = True
        self.show_grid = True
        self.plot_attrs = default_plot_attrs()

        # Text field study data (see loaders/text_field_study.py) — a
        # pandas DataFrame, not the x/y/markers shape ctx.cache holds for
        # every signal-plot source, so it gets its own attribute rather
        # than overloading ctx.cache (which plotting/marker/analysis code
        # throughout the app assumes has that shape).
        self.study_data = None
        self.study_data_path = None
        self.study_data_config = None  # the field_study_config.py dict used for this load

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

        # Manual double-click detection for the matplotlib canvas (see
        # interaction.py's on_press) — matplotlib's own event.dblclick can
        # miss pairs because RectangleSelector's press handler also sees
        # the first click of a would-be double-click before we know it's
        # part of one, occasionally leaving its internal state out of sync
        # with matplotlib's click-timing tracker.
        self._last_click_time = 0.0
        self._last_click_xy = None

        # Settings (Options dialog) — persisted to disk, see load_settings/save_settings
        self.settings = load_settings()

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
