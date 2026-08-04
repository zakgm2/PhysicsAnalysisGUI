"""
plot_signal.py
--------------
The toolbar's "Plot:" dropdown — lets the user pick which computed signal
to display for a dataset that offers more than one (currently TDT: the
normalized dF/F trace, plus whatever raw per-wavelength channels
PhysicsLibrary's process_tdt_folder() found — a main driver/probe channel
always, an isosbestic/control channel too if the recording has a 415
reference stream). Built once in the toolbar; repopulated by the loader
after each successful load since which options exist depends on the
recording, not on any fixed experimental setup.

Kept as its own module (not folded into ui/toolbar.py or loaders/tdt.py)
because both of those need it and importing across them directly would be
circular — toolbar.py already imports loaders/tdt.py for the Open/Reload
actions.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox


def build_plot_signal_control(ctx):
    """Toolbar widget: a "Plot:" label + combo box. Hidden until a load
    populates it with at least one option (see refresh_plot_signal_options)."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(QLabel("Plot:"))
    ctx.plot_signal_combo = QComboBox()
    ctx.plot_signal_combo.currentIndexChanged.connect(lambda _: _on_changed(ctx))
    layout.addWidget(ctx.plot_signal_combo)
    row.setVisible(False)
    ctx.plot_signal_row = row
    return row


def _on_changed(ctx):
    key = ctx.plot_signal_combo.currentData()
    if key is None or key == ctx.plot_signal:
        return
    ctx.plot_signal = key
    if ctx.cache is None:
        return

    if ctx.settings.get("plot_engine") == "pyqtgraph":
        # Swap the line's data in place instead of a full pg_simple_plot()
        # clear()+rebuild — see pg_update_active_signal's docstring: the
        # rebuild briefly shows an intermediate frame that Qt can paint as
        # a one-frame flash on every switch. Falls back to a full render
        # below only if there's no line yet to update (nothing rendered
        # this session).
        from .pg_engine import pg_update_active_signal
        if pg_update_active_signal(ctx):
            return

    # Different signals can have wildly different scale/units (raw
    # fluorescence vs. dF/F) and there's no reason a pan/zoom on one
    # would still make sense on another — always fit to the newly
    # selected signal's full data, same as a fresh load, rather than
    # trying to carry over whatever view was active before.
    ctx._data_generation += 1
    from .plotting import simple_plot
    simple_plot(ctx)


def refresh_plot_signal_options(ctx):
    """Call once after any load finishes. Repopulates the dropdown from
    cache['signals'] (only present for sources that offer more than one
    plottable signal — currently TDT) and hides the whole control for
    everything else (Oxysoft, Generic, ...) instead of leaving stale
    options from whatever was loaded before."""
    cache = ctx.cache
    signals = cache.get('signals') if cache else None
    combo = ctx.plot_signal_combo

    if not signals:
        ctx.plot_signal_row.setVisible(False)
        return

    combo.blockSignals(True)
    combo.clear()
    for key, sig in signals.items():
        combo.addItem(sig['label'], key)
    idx = combo.findData(ctx.plot_signal)
    combo.setCurrentIndex(idx if idx >= 0 else 0)
    ctx.plot_signal = combo.currentData()
    combo.blockSignals(False)
    ctx.plot_signal_row.setVisible(True)
