"""
pg_engine.py
------------
GPU-accelerated (OpenGL-backed rendering pipeline, CPU-side compiled
downsampling) main-plot engine using PyQtGraph, selectable as an
alternative to the matplotlib engine via Options -> Plot engine.

Scope: building/rendering the MAIN plot view only (font/margin scaling,
lines, markers, legend, grid, export). Mouse interaction (hover snap,
click dispatch, right-click marker menu) lives in pg_interaction.py —
mirrors the matplotlib engine's own plotting.py / interaction.py split.
FFT/PETH/Curve Fit/PT2 windows stay matplotlib-rendered regardless of
engine — they open fresh small figures each time and aren't the
performance bottleneck; both analysis_type() and launch_curve_fit() are
cache-driven (not tied to matplotlib Line2D objects), so they work
unchanged from either engine.

PyQtGraph's PlotDataItem does its own compiled min/max downsampling
(setDownsampling) at paint time, which is why this engine doesn't need
the manual _min_max_decimate() from plotting.py — that logic is
specific to matplotlib's Agg renderer, which has no equivalent built-in.
"""

import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters  # noqa: F401 — registers pg.exporters.ImageExporter
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog

from .fonts import main_plot_scale
from .pg_interaction import on_pg_mouse_moved, on_pg_mouse_clicked
from .toasts import show_error, show_window_toast


class _PanZoomViewBox(pg.ViewBox):
    """Left-drag = rectangle zoom (pyqtgraph's own RectMode default).
    Right-drag = simple pan, to match the matplotlib engine's mouse
    mapping instead of pyqtgraph's default (right-drag scales)."""

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == Qt.MouseButton.RightButton:
            ev.accept()
            tr = self.childGroup.transform()
            tr_inv = pg.functions.invertQTransform(tr)
            delta = tr_inv.map(ev.pos()) - tr_inv.map(ev.lastPos())
            self.translateBy(x=-delta.x(), y=-delta.y())
            return
        super().mouseDragEvent(ev, axis=axis)


def build_pg_widget(ctx):
    """Create the PlotWidget and wire mouse handling. Call once at startup."""
    vb = _PanZoomViewBox()
    vb.setMouseMode(pg.ViewBox.RectMode)
    vb.setMenuEnabled(False)  # we implement our own right-click marker menu

    widget = pg.PlotWidget(viewBox=vb)
    widget.setBackground('w')
    plot_item = widget.getPlotItem()
    plot_item.showGrid(x=True, y=True, alpha=0.3)

    ctx.pg_widget = widget
    ctx.pg_plot_item = plot_item
    ctx.pg_viewbox = vb
    ctx.pg_lines = []
    ctx.pg_hover_scatter = pg.ScatterPlotItem(size=8, brush='k', pen=None)
    ctx.pg_hover_scatter.setZValue(10)
    plot_item.addItem(ctx.pg_hover_scatter)
    ctx.pg_hover_scatter.hide()

    widget.scene().sigMouseMoved.connect(lambda pos: on_pg_mouse_moved(ctx, pos))
    widget.scene().sigMouseClicked.connect(lambda ev: on_pg_mouse_clicked(ctx, ev))
    return widget


_GEN_COLORS = ['#CC0000', '#0033CC', '#228B22', '#CC6600',
               '#6600CC', '#008888', '#AA0055', '#005588']


def _scaled_font_sizes(ctx):
    """(title_fs, xlabel_fs, ylabel_fs, leg_fs) in points, scaled the same
    way for whoever needs them (pg_simple_plot and sync_pg_margins both
    need the title size — the latter to reserve the right amount of
    space for it)."""
    plot_attrs = ctx.plot_attrs
    scale = main_plot_scale(ctx.stacked_plot_widget)
    return (
        max(8, round(plot_attrs["title_fs"] * scale)),
        max(6, round(plot_attrs["xlabel_fs"] * scale)),
        max(6, round(plot_attrs["ylabel_fs"] * scale)),
        max(5, round(plot_attrs["leg_fs"] * scale)),
    )


def _title_row_height(title_fs):
    return max(30, round(title_fs * 2.2))


def _set_legend_font_size(legend, leg_fs):
    """LegendItem.setLabelTextSize() only stores the new size in opts —
    it never re-renders the already-displayed label text (a pyqtgraph
    bug: LabelItem.setAttr() just updates opts, only setText() actually
    rebuilds the HTML and re-measures the item), so the legend visually
    never resizes. Re-set each label's text explicitly to force it."""
    if legend is None:
        return
    size = f'{leg_fs}pt'
    legend.opts['labelTextSize'] = size
    for _, label in legend.items:
        label.setText(label.text, size=size)


def sync_pg_margins(ctx, reprobe=True):
    """Make the PlotItem's actual data area (viewbox) the same pixel size
    as matplotlib's axes box would be at this widget size.

    matplotlib's subplot fractions (left=0.125, right=0.10, top=0.12,
    bottom=0.11 — read from ctx.fig so this tracks any future change)
    measure from the canvas edge to the axes box, and already include
    whatever space matplotlib needs for tick/axis labels. PyQtGraph is
    different: setContentsMargins() reserves space *in addition to*
    whatever its own AxisItems already auto-size themselves to fit their
    tick/axis label text. Applying the full matplotlib fraction as a pg
    margin therefore double-counts that space and makes the pg plot area
    noticeably smaller than matplotlib's for the same widget size.

    Fix: measure how much width/height pg's own left/bottom axes actually
    consume, and only reserve the remainder as margin. The top margin is
    similarly reduced by the title row's height (see pg_simple_plot) since
    that row is also additional space, not included in PlotItem's own axis
    auto-sizing. There's no axis on the right, so that side needs no such
    correction.

    reprobe=True (default) does a two-pass measurement — zero the margins,
    force a layout pass, read the axes' real geometry — which is accurate
    but briefly flashes the plot to fill the whole widget for one frame
    unless repaints are frozen around it, so it's relatively expensive.
    reprobe=False reuses the last measured axis size instead of
    re-measuring, so it's cheap enough to call on every tick of a live
    resize drag (axis label width rarely changes mid-drag — only the tick
    values' digit count could shift it, a one-pixel-scale concern) and
    keeps the plot area tracking the widget size continuously instead of
    jumping once after the drag settles."""
    plot_item = ctx.pg_plot_item
    if plot_item is None or ctx.pg_widget is None or ctx.fig is None:
        return
    sp = ctx.fig.subplotpars
    w, h = ctx.pg_widget.width(), ctx.pg_widget.height()
    if w <= 0 or h <= 0:
        return

    title_fs, _, _, _ = _scaled_font_sizes(ctx)
    target_left = round(sp.left * w)
    target_right = round((1 - sp.right) * w)
    target_top = max(0, round((1 - sp.top) * h) - _title_row_height(title_fs))
    target_bottom = round(sp.bottom * h)

    if reprobe or ctx._pg_axis_probe is None:
        # Pass 1 briefly zeroes out left/bottom margins to measure the
        # axes' real geometry, which would otherwise flash the plot to fill
        # the whole widget for one frame before pass 2 corrects it. Freeze
        # repaints for the probe so that intermediate state never shows.
        ctx.pg_widget.setUpdatesEnabled(False)
        try:
            plot_item.setContentsMargins(0, target_top, 0, 0)
            plot_item.layout.activate()
            left_axis_w = plot_item.getAxis('left').geometry().width()
            bottom_axis_h = plot_item.getAxis('bottom').geometry().height()
            ctx._pg_axis_probe = (left_axis_w, bottom_axis_h)

            left = max(0, target_left - round(left_axis_w))
            bottom = max(0, target_bottom - round(bottom_axis_h))
            plot_item.setContentsMargins(left, target_top, target_right, bottom)
        finally:
            ctx.pg_widget.setUpdatesEnabled(True)
    else:
        # Cheap path: reuse the last measured axis size, single pass, no
        # flash-prone zero-margin step — safe to call every resize tick.
        left_axis_w, bottom_axis_h = ctx._pg_axis_probe
        left = max(0, target_left - round(left_axis_w))
        bottom = max(0, target_bottom - round(bottom_axis_h))
        plot_item.setContentsMargins(left, target_top, target_right, bottom)


def pg_simple_plot(ctx):
    cache = ctx.cache
    plot_item = ctx.pg_plot_item
    if cache is None or plot_item is None:
        return

    zoom_key = ("pyqtgraph", id(cache))
    is_new_dataset = zoom_key != ctx._last_zoomed_key
    prev_range = None if is_new_dataset else plot_item.vb.viewRange()

    # While autorange is on, every single addItem() call below re-fits the
    # view to whatever's been added *so far* — with several lines plus
    # markers added one at a time, that's a rapid-fire zoom-out/zoom-in
    # flash before the final range (set at the end of this function) ever
    # takes effect. Disable it for the whole rebuild; it gets explicitly
    # re-enabled (new dataset) or replaced with an explicit setRange
    # (redraw of existing view) once, after everything is back in place.
    plot_item.vb.disableAutoRange()

    plot_item.clear()
    ctx.pg_lines = []
    plot_item.addItem(ctx.pg_hover_scatter)
    ctx.pg_hover_scatter.hide()

    legend = plot_item.addLegend()
    plot_attrs = ctx.plot_attrs
    label_map = {}
    if plot_attrs["leg_entries"]:
        label_map = {orig: (new, vis) for orig, new, vis in plot_attrs["leg_entries"]}
    raw_names = []

    def _add_line(x, y, color, width, raw_name):
        pen = pg.mkPen(color=color, width=width)
        item = pg.PlotDataItem(x, y, pen=pen)
        item.setDownsampling(auto=True, method='peak')
        # NOT setClipToView(True): triggers a real pyqtgraph bug (reproduces
        # on bare PlotWidget, all recent versions incl. 0.13.7/0.14.0) where
        # PlotDataItem._getDisplayDataset() resolves `view` to the PlotWidget
        # instead of its ViewBox and calls view.autoRangeEnabled(), which
        # PlotWidget.__getattr__ doesn't proxy -> AttributeError, spammed to
        # the console on every clear()+rebuild. setDownsampling alone already
        # bounds rendered points to ~pixel count; clip-to-view was a minor
        # extra optimization, not worth the crash.
        plot_item.addItem(item)
        ctx.pg_lines.append((item, x, y))
        # Legend entries are resolved here (not via PlotDataItem's own
        # `name=`) so the show/hide + rename map from Edit Attributes can
        # be applied without needing to touch the line's underlying data —
        # matplotlib's engine works the same way (line labels never
        # change, only what the legend displays for them).
        if raw_name is not None:
            raw_names.append(raw_name)
            display_name, visible = label_map.get(raw_name, (raw_name, True))
            if visible:
                legend.addItem(item, display_name)
        return item

    if cache.get('source') == 'Oxysoft':
        x = cache['x']
        o2hb = cache['o2hb']
        hhb = cache['hhb']
        for i in range(o2hb.shape[0]):
            _add_line(x, o2hb[i], '#FF9999', 1, 'O2Hb channels' if i == 0 else None)
            _add_line(x, hhb[i], '#99BBFF', 1, 'HHb channels' if i == 0 else None)
        ff = cache.get('fit_factor_mean')
        ff_tag = f"  [FF: {ff:.1f}%]" if ff is not None else ""
        _add_line(x, o2hb.mean(axis=0), '#CC0000', 2, f'Mean O2Hb{ff_tag}')
        _add_line(x, hhb.mean(axis=0), '#0033CC', 2, f'Mean HHb{ff_tag}')
        if 'thb' in cache:
            _add_line(x, cache['thb'].mean(axis=0), '#228B22', 2, f'Mean tHb{ff_tag}')
        y_label, title = "Delta Concentration (uM)", f"NIRS — {cache['store']}"
        x_label = "Time (s)"
    elif cache.get('source') == 'Generic':
        x = cache['x']
        for i, (col_name, y) in enumerate(cache['y_columns'].items()):
            mask = ~np.isnan(y)
            _add_line(x[mask], y[mask], _GEN_COLORS[i % len(_GEN_COLORS)], 2, col_name)
        y_label, title = "Value", cache['store']
        x_label = cache.get('x_label', 'X')
    else:
        data_to_plot = cache['corr'] if ctx.show_corrected else cache['raw']
        color = 'b' if ctx.show_corrected else 'gray'
        label_text = 'dF/F (corrected)' if ctx.show_corrected else 'Raw signal'
        _add_line(cache['x'], data_to_plot, color, 1, label_text)
        y_label, title = "Amplitude", f"{label_text} — {cache['store']}"
        x_label = "Time (s)"

    for m in cache['markers']:
        line = pg.InfiniteLine(
            pos=m['time'], angle=90, movable=False,
            pen=pg.mkPen(color=m['color'], width=1, style=Qt.PenStyle.DashLine),
            label=m['label'],
            labelOpts={'position': 0.95, 'color': m['color'], 'rotateAxis': (1, 0)},
        )
        plot_item.addItem(line)

    ctx._legend_entries = raw_names
    ctx._last_title = title
    ctx._last_xlabel = x_label
    ctx._last_ylabel = y_label

    title_text = plot_attrs["title"] or title
    xlabel_text = plot_attrs["xlabel"] or x_label
    ylabel_text = plot_attrs["ylabel"] or y_label

    # Scaled relative to the plot widget's actual on-screen size (same
    # reference matplotlib's engine uses) so the two engines look the same
    # size and both stay proportional as the window is resized, instead of
    # each interpreting the configured "24pt" through a different renderer
    # (matplotlib: fixed-DPI raster; PyQtGraph: native Qt font at OS DPI).
    title_fs, xlabel_fs, ylabel_fs, leg_fs = _scaled_font_sizes(ctx)
    weight = 'bold' if plot_attrs.get("bold", True) else 'normal'

    plot_item.setTitle(title_text, size=f'{title_fs}pt', color='#000',
                        **{'font-weight': weight})
    # PlotItem.setTitle() hardcodes its title row to a fixed 30px height
    # regardless of the font size passed in — with anything bigger than
    # the ~11pt default it was written for, the title text overflows
    # downward into the plot area. Override the cap it sets internally.
    # (sync_pg_margins() below accounts for the extra height this reserves
    # so the top margin doesn't also grow and shrink the plot area twice.)
    plot_item.titleLabel.setMaximumHeight(16777215)  # Qt's widget max height
    plot_item.layout.setRowFixedHeight(0, _title_row_height(title_fs))

    plot_item.setLabel('bottom', xlabel_text,
                        **{'font-size': f'{xlabel_fs}pt', 'font-weight': weight, 'color': '#000'})
    plot_item.setLabel('left', ylabel_text,
                        **{'font-size': f'{ylabel_fs}pt', 'font-weight': weight, 'color': '#000'})
    _set_legend_font_size(legend, leg_fs)

    plot_item.showGrid(x=ctx.show_grid, y=ctx.show_grid, alpha=0.3)
    if is_new_dataset:
        plot_item.enableAutoRange()
        ctx._last_zoomed_key = zoom_key
    else:
        (xr, yr) = prev_range
        plot_item.vb.setRange(xRange=xr, yRange=yr, padding=0)
    sync_pg_margins(ctx)


def pg_refresh_fonts(ctx):
    """Re-apply title/axis-label/legend font sizes for the current widget
    size without touching line data, markers, grid, or view range — cheap
    enough to call on every tick of a live resize drag (see sync_pg_margins'
    reprobe=False path, which this mirrors) so text keeps scaling smoothly
    instead of jumping once after the drag settles."""
    plot_item = ctx.pg_plot_item
    if plot_item is None or ctx.cache is None:
        return
    plot_attrs = ctx.plot_attrs
    title_text = plot_attrs["title"] or ctx._last_title or ""
    xlabel_text = plot_attrs["xlabel"] or ctx._last_xlabel or ""
    ylabel_text = plot_attrs["ylabel"] or ctx._last_ylabel or ""

    title_fs, xlabel_fs, ylabel_fs, leg_fs = _scaled_font_sizes(ctx)
    weight = 'bold' if plot_attrs.get("bold", True) else 'normal'

    plot_item.setTitle(title_text, size=f'{title_fs}pt', color='#000',
                        **{'font-weight': weight})
    plot_item.titleLabel.setMaximumHeight(16777215)
    plot_item.layout.setRowFixedHeight(0, _title_row_height(title_fs))

    plot_item.setLabel('bottom', xlabel_text,
                        **{'font-size': f'{xlabel_fs}pt', 'font-weight': weight, 'color': '#000'})
    plot_item.setLabel('left', ylabel_text,
                        **{'font-size': f'{ylabel_fs}pt', 'font-weight': weight, 'color': '#000'})
    _set_legend_font_size(plot_item.legend, leg_fs)


def pg_set_grid_visibility(ctx):
    if ctx.pg_plot_item is not None:
        ctx.pg_plot_item.showGrid(x=ctx.show_grid, y=ctx.show_grid, alpha=0.3)


def pg_reset_zoom(ctx):
    if ctx.pg_plot_item is not None:
        ctx.pg_plot_item.enableAutoRange()


def pg_export_view(ctx):
    if ctx.cache is None:
        show_error(ctx, "No plot to export.")
        return
    file_path, _ = QFileDialog.getSaveFileName(
        ctx.win, "Export View", f"{ctx.cache['store']}_view.png", "PNG (*.png)"
    )
    if file_path:
        exporter = pg.exporters.ImageExporter(ctx.pg_plot_item)
        exporter.export(file_path)
        show_window_toast(ctx, "View Exported")
