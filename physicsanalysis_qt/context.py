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

        # Toolbar widgets (assigned in ui/toolbar.py)
        self.plot_type_combo = None
        self.window_entry = None
        self.btn_add_marker = None

        # Data
        self.cache = None
        self.selected_path = None
        self.last_dir = None  # last folder browsed in any Open dialog
        self.show_corrected = True
        self.show_grid = True
        self.plot_attrs = default_plot_attrs()

        # Marker mode
        self.marker_mode = False

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

        # Curve fit click capture
        self.slope_clicks = []
