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
        "plot_engine":         "matplotlib",  # "matplotlib" | "pyqtgraph" | "vispy"
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

        # VisPy (OpenGL, GPU-native) engine — only populated if that
        # engine is used. Built incrementally alongside pg_* above as
        # vispy_engine.py grows (see the VisPy build-stage plan).
        self.vispy_canvas = None        # vispy.scene.SceneCanvas
        self.vispy_view = None          # grid.add_view() result
        self.vispy_line_visuals = []    # (Line visual, full_x, full_y, raw_name)
        self.vispy_legend_widget = None # hand-built Qt overlay, not part of the scene
        self.vispy_marker_lines = []    # (Line visual, Text visual, marker_dict)
        self._vispy_press_pos = None    # (x, y) screen pixel — click-vs-drag detection
        self._vispy_press_button = None

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
        # The unspliced full recording, saved off the first time Splice
        # Recording is used, so Restore Full Recording can bring it back
        # without re-loading from disk. None when no splice is active.
        self.original_cache = None
        # List of {"mode": ..., "start": ..., "end": ...}, one per splice
        # currently applied, in the order they were applied — several can
        # stack (e.g. removing more than one artifact from the same
        # recording). What save_splice() (analysis/splice.py) writes to
        # the JSON saves/ sidecar. Empty when no splice is active.
        self._active_splices = []
        # Set by analysis/splice.py's start_splice_flow() while the user
        # is choosing what kind of splice, read by apply_splice_at_points().
        self._pending_splice_mode = None
        # True from a successful start_splice_flow() until the two clicks
        # it's waiting for are both in (apply_splice_at_points) — the
        # click handlers (interaction.py, pg_interaction.py) check this
        # directly rather than plot_type_combo.currentText() == "Splice",
        # since "Splice" isn't a combo entry (only the sidebar's scissors
        # icon starts a splice) and, previously, re-setting the combo to
        # a value it was already showing didn't fire currentTextChanged —
        # which meant clicking the scissors a second time in a row did
        # nothing.
        self.splice_click_mode = False
        self.selected_path = None
        self.last_dir = None  # last folder browsed in any Open dialog
        # Which entry of cache['signals'] the main plot (and every
        # TDT-only analysis dialog) currently shows — e.g. "normalized",
        # "isosbestic", "main_driver". Only meaningful for a cache that
        # actually has a 'signals' map; see get_active_signal() below.
        # Reset to "normalized" on every fresh load (loaders/tdt.py) so a
        # previous dataset's selection (e.g. "isosbestic") never silently
        # carries over to one that doesn't have that channel.
        self.plot_signal = "normalized"
        self.plot_signal_row = None     # QWidget row wrapping the combo below
        self.plot_signal_combo = None   # toolbar "Plot:" dropdown, see plot_signal.py
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

        # (engine, generation) the view was last reset-to-fit for. Redraws
        # triggered by things that aren't a fresh data load (grid toggle,
        # marker add/edit, attribute changes, switching the Plot signal
        # dropdown) compare against this so they can preserve the current
        # zoom/pan instead of snapping back to the full-data view every
        # time — an actual new dataset OR switching engines (the other
        # engine's view never had valid data in it) resets it.
        #
        # Uses an explicit counter (below), not id(cache): a freed cache
        # dict's memory address can be reused by the very next dict CPython
        # allocates (same size/shape, back-to-back Open/Reload), which
        # would make id(new_cache) == id(old_cache) by pure coincidence —
        # silently treating a brand new recording as "unchanged" and
        # snapping the view to whatever was zoomed in the previous one.
        self._last_zoomed_key = None
        # Bumped exactly once every time ctx.cache is replaced with a
        # genuinely new dataset (Open/Reload, splice apply, restore full
        # recording) — never for an in-place redraw of the same dataset
        # (e.g. switching the Plot signal dropdown, which must NOT reset
        # the zoom). See _last_zoomed_key above.
        self._data_generation = 0

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
        # True while RectangleSelector's own drag-to-zoom is in progress
        # (see interaction.py's on_press/on_motion/on_release) — suppresses
        # the hover tracker's own blit for the duration so the two blit
        # systems don't fight over the same canvas region.
        self._rect_dragging = False
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


def get_active_signal(ctx):
    """Resolve which signal the main plot (and every TDT-only analysis
    dialog — FFT, Z-Score PETH, Event PETH, Peak Finder) should currently
    use, as (key, label, y, color).

    cache['signals'] is a dict built by the loader (see loaders/tdt.py)
    mapping a plot-option key ("normalized", "isosbestic", "main_driver",
    ...) to {"label", "y", "color"} — deliberately not hardcoded to
    exactly those three: a recording with no isosbestic reference stream
    just won't have that key, and this still works. Sources that don't
    offer more than one plottable signal (Oxysoft, Generic — they already
    plot every channel at once) have no 'signals' map at all, so this
    falls back to the cache's default normalized trace directly.
    """
    cache = ctx.cache
    signals = cache.get('signals')
    if not signals:
        y = cache['corr'] if 'corr' in cache else cache['raw']
        return "normalized", "dF/F (corrected)", y, 'blue'
    key = ctx.plot_signal if ctx.plot_signal in signals else next(iter(signals))
    sig = signals[key]
    return key, sig['label'], sig['y'], sig['color']


def signal_short_label(key):
    """"main_driver" -> "Main Driver" — a compact form of an active-signal
    key for dialog titles/export filenames, where the full descriptive
    label (e.g. "Isosbestic (415A)") would be redundant/unwieldy."""
    return key.replace('_', ' ').title()
