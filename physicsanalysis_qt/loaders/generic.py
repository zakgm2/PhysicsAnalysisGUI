"""
loaders/generic.py
--------------------
Generic tabular file loading (Excel/CSV/TSV/plain text) via
PhysicsLibrary's sub-table detection, with a picker dialog for
table/X/Y column selection.
"""

import os

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QComboBox,
    QTextEdit, QPushButton, QFileDialog, QAbstractItemView,
)

import PhysicsLibrary as pl

from ..toasts import show_error, show_success


class GenericLoaderDialog(QDialog):
    """Table/column picker for the generic tabular parser."""

    def __init__(self, parent, ctx, tables, path):
        super().__init__(parent)
        self.ctx = ctx
        self.tables = tables
        self.path = path
        self.current_table = None

        self.setWindowTitle(f"Generic Loader — {os.path.basename(path)}")
        self.resize(780, 540)
        layout = QHBoxLayout(self)

        # Left: table list
        left = QVBoxLayout()
        left.addWidget(QLabel("Detected tables:"))
        self.tbl_list = QListWidget()
        self.tbl_list.addItems([t.name for t in tables])
        self.tbl_list.currentRowChanged.connect(self._on_table_select)
        left.addWidget(self.tbl_list)
        layout.addLayout(left, stretch=1)

        # Right: column pickers + preview
        right = QVBoxLayout()

        xrow = QHBoxLayout()
        xrow.addWidget(QLabel("X:"))
        self.x_combo = QComboBox()
        xrow.addWidget(self.x_combo, stretch=1)
        right.addLayout(xrow)

        right.addWidget(QLabel("Y (multi-select):"))
        self.y_list = QListWidget()
        self.y_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.y_list.setFixedHeight(120)
        right.addWidget(self.y_list)

        right.addWidget(QLabel("Preview:"))
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFontFamily("Consolas")
        right.addWidget(self.preview, stretch=1)

        btn_row = QHBoxLayout()
        btn_load = QPushButton("Load to Main Plot")
        btn_load.clicked.connect(self._do_load)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_close)
        right.addLayout(btn_row)

        layout.addLayout(right, stretch=2)

        self.tbl_list.setCurrentRow(0)

    def _refresh_preview(self, t):
        lines = ["\t".join(t.headers), "-" * 60]
        for ri in range(min(8, t.data.shape[0])):
            cells = [f"{v:.5g}" if not np.isnan(v) else "—" for v in t.data[ri]]
            lines.append("\t".join(cells))
        self.preview.setPlainText("\n".join(lines))

    def _on_table_select(self, row):
        if row < 0:
            return
        t = self.tables[row]
        self.current_table = t

        self.x_combo.clear()
        self.x_combo.addItems(t.headers)

        self.y_list.clear()
        self.y_list.addItems(t.headers)
        for i in range(1, len(t.headers)):
            self.y_list.item(i).setSelected(True)

        self._refresh_preview(t)

    def _do_load(self):
        from ..plotting import simple_plot

        t = self.current_table
        if t is None:
            return
        y_indices = [self.y_list.row(item) for item in self.y_list.selectedItems()]
        if not y_indices:
            show_error(self.ctx, "Select at least one Y column.")
            return

        x_idx = self.x_combo.currentIndex()
        if x_idx < 0:
            x_idx = 0

        x_data = t.data[:, x_idx]
        valid = ~np.isnan(x_data)
        x_data = x_data[valid]

        y_columns = {}
        for yi in y_indices:
            y_columns[t.headers[yi]] = t.data[valid, yi]

        fs = float(1.0 / np.median(np.diff(x_data))) if len(x_data) > 1 else 1.0

        self.ctx.cache = {
            "source":      "Generic",
            "source_path": self.path,
            "x":           x_data,
            "y_columns":   y_columns,
            "x_label":     t.headers[x_idx],
            "store":       t.name,
            "fs":          fs,
            "markers":     [],
        }
        self.accept()
        simple_plot(self.ctx)
        show_success(self.ctx, f"Loaded: {t.name}")


def launch_generic_file_loader(ctx):
    start_dir = ctx.last_dir or ctx.settings["default_folder"]
    path, _ = QFileDialog.getOpenFileName(
        ctx.win, "Open Any Tabular File", start_dir,
        "All tabular (*.xlsx *.xls *.csv *.tsv *.txt *.dat);;Excel (*.xlsx *.xls);;"
        "CSV / TSV (*.csv *.tsv);;Text / data (*.txt *.dat);;All files (*.*)"
    )
    if not path:
        return
    ctx.last_dir = os.path.dirname(path)
    try:
        tables = pl.load_any_file(path)
    except Exception as e:
        show_error(ctx, f"Could not parse file:\n{e}")
        return
    if not tables:
        show_error(ctx, "No usable tabular data found in this file.")
        return

    dlg = GenericLoaderDialog(ctx.win, ctx, tables, path)
    dlg.exec()
