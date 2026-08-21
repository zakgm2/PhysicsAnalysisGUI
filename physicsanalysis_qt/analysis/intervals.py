"""
analysis/intervals.py
-----------------------
Event Intervals: measures the time between whatever markers are
currently displayed on the plot, universal to any marker source (TDT
epocs, Oxysoft events, or manually-placed markers) — it only looks at
cache['markers'], not any format-specific structure.

One row per marker, with two interval columns:
  - "Δt since previous (same store)": for a store with alternating
    high/low phases (e.g. a pump or lever), a low row's value here IS
    its on-duration (time since its own high). For a store with no
    phase concept, it's just the interval since that store's last event.
  - "Δt since previous (any marker)": the interval since whatever
    marker came before it, regardless of store — useful when several
    different event types are interleaved on the same plot.
No special-casing for phase is needed — both columns are computed the
same generic way (diff against the previous timestamp in the relevant
sequence), and duration falls out of that automatically wherever high/
low pairs happen to alternate.
"""

import csv
import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView,
)

import PhysicsLibrary as pl

from ..context import export_file
from ..toasts import show_error, show_window_toast


class IntervalsDialog(QDialog):
    """Table of every currently-displayed marker with time-since-previous
    columns, plus CSV export."""

    _HEADERS = ["Time (s)", "Store", "Label", "Phase",
                "Δt since prev. (same store)", "Δt since prev. (any marker)"]

    def __init__(self, ctx, rows):
        super().__init__(ctx.win)
        self.rows = rows
        self.setWindowTitle("Event Intervals")
        self.resize(720, 480)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"{len(rows)} marker(s) currently on the plot."))

        table = QTableWidget(len(rows), len(self._HEADERS))
        table.setHorizontalHeaderLabels(self._HEADERS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        from ..marker_labels import store_display_name
        for r, row in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(f"{row['time']:.3f}"))
            table.setItem(r, 1, QTableWidgetItem(store_display_name(ctx, row['store'])))
            table.setItem(r, 2, QTableWidgetItem(row['label']))
            table.setItem(r, 3, QTableWidgetItem(row['phase']))
            table.setItem(r, 4, QTableWidgetItem(
                "" if row['dt_store'] is None else f"{row['dt_store']:.3f}"))
            table.setItem(r, 5, QTableWidgetItem(
                "" if row['dt_global'] is None else f"{row['dt_global']:.3f}"))
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_csv = QPushButton("Export CSV")
        btn_csv.clicked.connect(self._export_csv)
        btn_row.addWidget(btn_csv)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self.ctx = ctx

    def _export_csv(self):
        def _write(path):
            with open(path, 'w', newline='') as fh:
                writer = csv.writer(fh)
                writer.writerow(["time_s", "store", "label", "phase",
                                  "dt_since_prev_same_store_s", "dt_since_prev_any_s"])
                for row in self.rows:
                    writer.writerow([
                        f"{row['time']:.6f}", row['store'], row['label'], row['phase'],
                        "" if row['dt_store'] is None else f"{row['dt_store']:.6f}",
                        "" if row['dt_global'] is None else f"{row['dt_global']:.6f}",
                    ])

        ts = datetime.datetime.now().strftime("%H%M%S")
        store_name = self.ctx.cache.get('store', 'Data') if self.ctx.cache else 'Data'
        export_file(self.ctx, self, "Export Event Intervals",
                     f"EventIntervals_{store_name}_{ts}.csv", "CSV (*.csv);;Text (*.txt)", _write)


def launch_intervals(ctx):
    if ctx.cache is None or not ctx.cache.get('markers'):
        show_error(ctx, "No markers currently on the plot to measure.")
        return
    rows = pl.compute_marker_intervals(ctx.cache['markers'])
    dlg = IntervalsDialog(ctx, rows)
    dlg.exec()
