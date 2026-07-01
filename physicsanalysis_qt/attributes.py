"""
attributes.py
-------------
Edit Attributes dialog: title/label text and font sizes, legend font
size/position, and per-legend-entry show/hide + rename.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QCheckBox, QPushButton,
)

from . import plotting
from .interaction import _refresh_hover_bg


class AttributesDialog(QDialog):
    """Edit graph labels, font sizes, legend size/position, and per-entry legend edits."""

    LEG_LOCS = ["upper left", "upper right", "lower left", "lower right",
                "upper center", "lower center", "center left", "center right",
                "center", "best"]

    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Edit Graph Attributes")
        layout = QVBoxLayout(self)

        plot_attrs = ctx.plot_attrs
        ax = ctx.ax
        cur_title = plot_attrs["title"] or ax.get_title()
        cur_xlabel = plot_attrs["xlabel"] or ax.get_xlabel()
        cur_ylabel = plot_attrs["ylabel"] or ax.get_ylabel()

        # Labels & font sizes
        lf = QGroupBox("Labels & Font Sizes")
        grid = QGridLayout(lf)
        self.e_title, self.e_title_fs = self._row(grid, 0, "Title:", cur_title, plot_attrs["title_fs"])
        self.e_xlabel, self.e_xlabel_fs = self._row(grid, 1, "X Label:", cur_xlabel, plot_attrs["xlabel_fs"])
        self.e_ylabel, self.e_ylabel_fs = self._row(grid, 2, "Y Label:", cur_ylabel, plot_attrs["ylabel_fs"])
        layout.addWidget(lf)

        # Legend
        lf2 = QGroupBox("Legend")
        lf2_layout = QVBoxLayout(lf2)
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Font size:"))
        self.e_leg_fs = QLineEdit(str(plot_attrs["leg_fs"]))
        self.e_leg_fs.setFixedWidth(50)
        top_row.addWidget(self.e_leg_fs)
        top_row.addWidget(QLabel("Position:"))
        self.leg_loc_combo = QComboBox()
        self.leg_loc_combo.addItems(self.LEG_LOCS)
        self.leg_loc_combo.setCurrentText(plot_attrs["leg_loc"])
        top_row.addWidget(self.leg_loc_combo)
        top_row.addStretch(1)
        lf2_layout.addLayout(top_row)

        handles, labels = ax.get_legend_handles_labels()
        entries = [(h, l) for h, l in zip(handles, labels) if not l.startswith('_')]
        saved_entry_map = {}
        if plot_attrs["leg_entries"]:
            saved_entry_map = {orig: (new, vis) for orig, new, vis in plot_attrs["leg_entries"]}

        self.entry_widgets = []  # (checkbox, lineedit, original_label)
        if entries:
            entry_grid = QGridLayout()
            entry_grid.addWidget(QLabel("Show"), 0, 0)
            entry_grid.addWidget(QLabel("Label"), 0, 1)
            for i, (h, l) in enumerate(entries):
                saved_label, saved_vis = saved_entry_map.get(l, (l, True))
                cb = QCheckBox()
                cb.setChecked(saved_vis)
                le = QLineEdit(saved_label)
                entry_grid.addWidget(cb, i + 1, 0)
                entry_grid.addWidget(le, i + 1, 1)
                self.entry_widgets.append((cb, le, l))
            lf2_layout.addLayout(entry_grid)
        else:
            no_entries = QLabel("No legend entries found — load data first.")
            no_entries.setStyleSheet("color: gray;")
            lf2_layout.addWidget(no_entries)

        layout.addWidget(lf2)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _row(self, grid, row, label_text, default_text, default_size):
        grid.addWidget(QLabel(label_text), row, 0)
        e_text = QLineEdit(default_text)
        e_text.setFixedWidth(220)
        grid.addWidget(e_text, row, 1)
        grid.addWidget(QLabel("Size:"), row, 2)
        e_size = QLineEdit(str(default_size))
        e_size.setFixedWidth(40)
        grid.addWidget(e_size, row, 3)
        return e_text, e_size

    def _safe_int(self, entry, default):
        try:
            return max(6, int(entry.text()))
        except ValueError:
            return default

    def _apply(self):
        ctx = self.ctx
        plot_attrs = ctx.plot_attrs
        if self.e_title.text().strip():
            plot_attrs["title"] = self.e_title.text().strip()
            plot_attrs["title_fs"] = self._safe_int(self.e_title_fs, plot_attrs["title_fs"])
        if self.e_xlabel.text().strip():
            plot_attrs["xlabel"] = self.e_xlabel.text().strip()
            plot_attrs["xlabel_fs"] = self._safe_int(self.e_xlabel_fs, plot_attrs["xlabel_fs"])
        if self.e_ylabel.text().strip():
            plot_attrs["ylabel"] = self.e_ylabel.text().strip()
            plot_attrs["ylabel_fs"] = self._safe_int(self.e_ylabel_fs, plot_attrs["ylabel_fs"])

        plot_attrs["leg_fs"] = self._safe_int(self.e_leg_fs, plot_attrs["leg_fs"])
        plot_attrs["leg_loc"] = self.leg_loc_combo.currentText()

        if self.entry_widgets:
            plot_attrs["leg_entries"] = [
                (orig_l, le.text() or orig_l, cb.isChecked())
                for cb, le, orig_l in self.entry_widgets
            ]

        plotting._apply_plot_attrs(ctx)
        _refresh_hover_bg(ctx)
        self.accept()


def open_attributes_window(ctx):
    dlg = AttributesDialog(ctx.win, ctx)
    dlg.exec()
