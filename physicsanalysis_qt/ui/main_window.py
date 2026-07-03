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
    QMainWindow, QWidget, QVBoxLayout, QSizePolicy, QStatusBar, QStackedWidget,
)

from .. import interaction
from ..pg_engine import build_pg_widget, sync_pg_margins
from .toolbar import build_toolbar


class _PlotStack(QStackedWidget):
    """QStackedWidget that debounce-triggers a re-render on resize when
    the PyQtGraph engine is active, so its fonts stay scaled to the
    current widget size — matplotlib gets this for free via its own
    resize_event (see interaction.on_resize). Also keeps the PyQtGraph
    plot's inset margins matched to matplotlib's subplot margins on every
    resize, so both engines frame their plot the same distance from the
    edges — the widget itself stays full size either way; only how much
    of it the axes/data occupy changes."""

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
        if ctx.settings.get("plot_engine") == "pyqtgraph":
            from ..pg_engine import pg_refresh_fonts
            pg_refresh_fonts(ctx)
        sync_pg_margins(ctx, reprobe=False)
        self._timer.start(150)

    def _replot(self):
        from ..pg_engine import pg_simple_plot
        ctx = self._ctx
        sync_pg_margins(ctx, reprobe=True)
        if ctx.settings.get("plot_engine") == "pyqtgraph":
            pg_simple_plot(ctx)


def build_main_window(ctx):
    ctx.win = QMainWindow()
    ctx.win.setWindowTitle("Physics Analysis GUI (PyQt6)")
    ctx.win.resize(1250, 850)

    central = QWidget()
    ctx.win.setCentralWidget(central)
    root_layout = QVBoxLayout(central)
    root_layout.setContentsMargins(0, 0, 0, 0)

    toolbar = build_toolbar(ctx)
    root_layout.addWidget(toolbar)

    ctx.stacked_plot_widget = _PlotStack(ctx)
    root_layout.addWidget(ctx.stacked_plot_widget, stretch=1)

    _build_matplotlib_canvas(ctx)
    ctx.stacked_plot_widget.addWidget(ctx.canvas)

    build_pg_widget(ctx)  # sets ctx.pg_widget / ctx.pg_plot_item
    ctx.stacked_plot_widget.addWidget(ctx.pg_widget)

    ctx.stacked_plot_widget.setCurrentWidget(
        ctx.pg_widget if ctx.settings.get("plot_engine") == "pyqtgraph" else ctx.canvas
    )
    sync_pg_margins(ctx)

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

    target = ctx.pg_widget if ctx.settings.get("plot_engine") == "pyqtgraph" else ctx.canvas
    ctx.stacked_plot_widget.setCurrentWidget(target)
    sync_pg_margins(ctx)
    if ctx.cache is not None:
        simple_plot(ctx)
