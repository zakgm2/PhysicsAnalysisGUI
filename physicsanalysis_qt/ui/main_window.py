"""
ui/main_window.py
--------------------
Assembles the QMainWindow: toolbar, plot canvas (matplotlib and
PyQtGraph both built up front, stacked in a QStackedWidget so switching
engines in Options is instant), mouse/scroll/resize event wiring,
rectangle selector, status bar.
"""

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.widgets import RectangleSelector
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy, QStatusBar, QStackedWidget,
)

from .. import interaction
from ..pg_engine import build_pg_widget, sync_pg_margins
from ..update_check import local_version
from ..vispy_engine import build_vispy_widget, sync_vispy_margins
from .toolbar import build_toolbar
from .edit_toolbar import build_edit_toolbar


def _widget_for_engine(ctx):
    engine = ctx.settings.get("plot_engine")
    if engine == "pyqtgraph":
        return ctx.pg_widget
    if engine == "vispy":
        return ctx.vispy_canvas.native
    return ctx.canvas


class _PlotStack(QStackedWidget):
    """QStackedWidget that debounce-triggers a re-render on resize when
    the PyQtGraph or VisPy engine is active, so their fonts stay scaled
    to the current widget size — matplotlib gets this for free via its
    own resize_event (see interaction.on_resize). Also keeps each
    engine's inset margins matched to matplotlib's subplot margins on
    every resize, so all three engines frame their plot the same
    distance from the edges — the widget itself stays full size either
    way; only how much of it the axes/data occupy changes."""

    def __init__(self, ctx):
        super().__init__()
        self._ctx = ctx
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._replot)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        ctx = self._ctx
        if ctx.cache is None:
            return
        # Cheap margin + font sync on every tick (reuses the last measured
        # axis size, single pass, no flash-prone zero-margin probe, and no
        # touching line data) so the plot area and title/axis/legend text
        # track the widget size live and continuously during the drag,
        # matching how matplotlib's own canvas already redraws live. The
        # accurate two-pass reprobe + full data replot are debounced to
        # once after the drag settles, since both are more expensive.
        engine = ctx.settings.get("plot_engine")
        if engine == "pyqtgraph":
            from ..pg_engine import pg_refresh_fonts
            pg_refresh_fonts(ctx)
        elif engine == "vispy":
            from ..vispy_engine import vispy_refresh_fonts
            vispy_refresh_fonts(ctx)
        sync_pg_margins(ctx, reprobe=False)
        sync_vispy_margins(ctx)
        self._timer.start(150)

    def _replot(self):
        # Not a full pg_simple_plot() — this settle-tick only exists to
        # get an accurate (reprobe=True) margin/font pass once the drag
        # stops; pg_refresh_fonts already does that without touching line
        # data, markers, or view range. A full rebuild here was pure
        # overkill for that and paid for it with a one-frame flash on
        # every resize settle, including the layout reflow a fresh TDT
        # load triggers by revealing the Plot dropdown for the first time
        # — same class of bug pg_set_grid_visibility's docstring already
        # covers for grid toggles.
        ctx = self._ctx
        engine = ctx.settings.get("plot_engine")
        if engine == "pyqtgraph":
            from ..pg_engine import pg_refresh_fonts
            pg_refresh_fonts(ctx)
        elif engine == "vispy":
            from ..vispy_engine import vispy_refresh_fonts
            vispy_refresh_fonts(ctx)
        sync_pg_margins(ctx, reprobe=True)
        sync_vispy_margins(ctx)


def build_main_window(ctx):
    ctx.win = QMainWindow()
    try:
        version = local_version("physicsanalysis_qt")
    except Exception:
        version = None  # missing/unreadable pyproject.toml (e.g. a packaged build) — title still works without it
    title = "Physics Analysis GUI (PyQt6)" + (f" — v{version}" if version else "")
    ctx.win.setWindowTitle(title)
    ctx.win.resize(1250, 850)

    central = QWidget()
    ctx.win.setCentralWidget(central)
    outer_layout = QHBoxLayout(central)
    outer_layout.setContentsMargins(0, 0, 0, 0)
    outer_layout.setSpacing(0)

    edit_toolbar = build_edit_toolbar(ctx)
    outer_layout.addWidget(edit_toolbar)

    right_column = QWidget()
    root_layout = QVBoxLayout(right_column)
    root_layout.setContentsMargins(0, 0, 0, 0)
    outer_layout.addWidget(right_column, stretch=1)

    toolbar = build_toolbar(ctx)
    root_layout.addWidget(toolbar)

    ctx.stacked_plot_widget = _PlotStack(ctx)
    root_layout.addWidget(ctx.stacked_plot_widget, stretch=1)

    _build_matplotlib_canvas(ctx)
    ctx.stacked_plot_widget.addWidget(ctx.canvas)

    build_pg_widget(ctx)  # sets ctx.pg_widget / ctx.pg_plot_item
    ctx.stacked_plot_widget.addWidget(ctx.pg_widget)

    vispy_native = build_vispy_widget(ctx)  # sets ctx.vispy_canvas / ctx.vispy_view
    ctx.stacked_plot_widget.addWidget(vispy_native)

    ctx.stacked_plot_widget.setCurrentWidget(_widget_for_engine(ctx))
    sync_pg_margins(ctx)
    sync_vispy_margins(ctx)

    ctx.status_bar = QStatusBar()
    ctx.win.setStatusBar(ctx.status_bar)
    ctx.status_bar.showMessage("X: -- | Y: -- | Pt: --")

    return ctx.win


def _build_matplotlib_canvas(ctx):
    ctx.fig = Figure(figsize=(8, 4), dpi=100)
    ctx.ax = ctx.fig.add_subplot(111)
    ctx.canvas = FigureCanvasQTAgg(ctx.fig)
    ctx.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    ctx.canvas.mpl_connect('button_press_event', lambda e: interaction.on_press(ctx, e))
    ctx.canvas.mpl_connect('motion_notify_event', lambda e: interaction.on_motion(ctx, e))
    ctx.canvas.mpl_connect('button_release_event', lambda e: interaction.on_release(ctx, e))

    zoom_fun = interaction.zoom_factory(ctx, base_scale=1.1)
    ctx.canvas.mpl_connect('scroll_event', zoom_fun)
    ctx.canvas.mpl_connect('resize_event', lambda e: interaction.on_resize(ctx, e))

    ctx.rect_selector = RectangleSelector(
        ctx.ax, lambda eclick, erelease: interaction.on_select(ctx, eclick, erelease),
        useblit=True, button=[1],
        minspanx=5, minspany=0.001,
        props=dict(facecolor='yellow', edgecolor='black', alpha=0.3, fill=True),
        interactive=True
    )
    ctx.rect_selector.set_active(True)
    ctx.canvas.draw()


def switch_plot_engine(ctx):
    """Called by Options when the user changes the plot engine. Swaps the
    visible widget in the stack and re-renders the current dataset with
    the newly selected engine."""
    from ..plotting import simple_plot

    ctx.stacked_plot_widget.setCurrentWidget(_widget_for_engine(ctx))
    sync_pg_margins(ctx)
    sync_vispy_margins(ctx)
    if ctx.cache is not None:
        simple_plot(ctx)
