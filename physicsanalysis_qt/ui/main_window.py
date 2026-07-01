"""
ui/main_window.py
--------------------
Assembles the QMainWindow: toolbar, matplotlib canvas, mouse/scroll/
resize event wiring, rectangle selector, status bar.
"""

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.widgets import RectangleSelector
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSizePolicy, QStatusBar

from .. import interaction
from .toolbar import build_toolbar


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

    ctx.fig = Figure(figsize=(8, 4), dpi=100)
    ctx.ax = ctx.fig.add_subplot(111)
    ctx.canvas = FigureCanvasQTAgg(ctx.fig)
    ctx.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    root_layout.addWidget(ctx.canvas, stretch=1)

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

    ctx.status_bar = QStatusBar()
    ctx.win.setStatusBar(ctx.status_bar)
    ctx.status_bar.showMessage("X: -- | Y: -- | Pt: --")

    ctx.canvas.draw()
    return ctx.win
