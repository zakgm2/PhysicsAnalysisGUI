"""
options.py
----------
Options dialog: default folder for Open dialogs, performance settings
(render decimation, background loading), and plot engine selection
(matplotlib/CPU vs PyQtGraph/GPU).
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QSpinBox, QComboBox, QFileDialog, QGroupBox,
    QMessageBox,
)


_ENGINE_LABELS = {
    "matplotlib": "Matplotlib (CPU)",
    "pyqtgraph":  "PyQtGraph (GPU-accelerated)",
}
_ENGINE_VALUES = {v: k for k, v in _ENGINE_LABELS.items()}


class OptionsDialog(QDialog):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Options")
        self.resize(480, 340)
        layout = QVBoxLayout(self)

        gb_engine = QGroupBox("Plot Engine (main plot only)")
        g0 = QGridLayout(gb_engine)
        g0.addWidget(QLabel("Engine:"), 0, 0)
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(list(_ENGINE_LABELS.values()))
        self.combo_engine.setCurrentText(_ENGINE_LABELS[ctx.settings["plot_engine"]])
        g0.addWidget(self.combo_engine, 0, 1)
        engine_note = QLabel(
            "PyQtGraph is GPU-accelerated and handles large recordings much better.\n"
            "Legend position (below) is matplotlib-only. FFT/PETH/Curve Fit/PT2\n"
            "windows always use matplotlib either way."
        )
        engine_note.setStyleSheet("color: gray;")
        engine_note.setWordWrap(True)
        g0.addWidget(engine_note, 1, 0, 1, 2)
        layout.addWidget(gb_engine)

        gb_folder = QGroupBox("File Dialogs")
        g1 = QGridLayout(gb_folder)
        g1.addWidget(QLabel("Default folder:"), 0, 0)
        self.e_folder = QLineEdit(ctx.settings["default_folder"])
        g1.addWidget(self.e_folder, 0, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        g1.addWidget(btn_browse, 0, 2)
        layout.addWidget(gb_folder)

        gb_perf = QGroupBox("Performance (matplotlib engine)")
        g2 = QGridLayout(gb_perf)
        g2.addWidget(QLabel("Max rendered points per trace:"), 0, 0)
        self.spin_points = QSpinBox()
        self.spin_points.setRange(200, 20000)
        self.spin_points.setSingleStep(200)
        self.spin_points.setValue(ctx.settings["decimate_max_points"])
        g2.addWidget(self.spin_points, 0, 1)

        self.cb_threaded = QCheckBox(
            "Load data files on a background thread (default: on)\n"
            "Keeps the UI responsive during large TDT/Oxysoft loads instead\n"
            "of freezing until they finish."
        )
        self.cb_threaded.setChecked(ctx.settings["background_loading"])
        g2.addWidget(self.cb_threaded, 1, 0, 1, 2)

        threaded_note = QLabel(
            "Turn this off only if a load ever behaves strangely (hangs, wrong\n"
            "data, or a crash) — that would point to a thread-safety issue in\n"
            "the TDT/Oxysoft parsing code, and running on the main thread\n"
            "instead rules that out. Also useful when debugging a load error\n"
            "yourself: off gives the real traceback instead of a summarized\n"
            "error message."
        )
        threaded_note.setStyleSheet("color: gray;")
        threaded_note.setWordWrap(True)
        g2.addWidget(threaded_note, 2, 0, 1, 2)

        layout.addWidget(gb_perf)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._apply)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Default Folder", self.e_folder.text())
        if path:
            self.e_folder.setText(path)

    def _apply(self):
        folder = self.e_folder.text().strip()
        if folder and os.path.isdir(folder):
            self.ctx.settings["default_folder"] = folder
        self.ctx.settings["decimate_max_points"] = self.spin_points.value()
        self.ctx.settings["background_loading"] = self.cb_threaded.isChecked()

        new_engine = _ENGINE_VALUES[self.combo_engine.currentText()]
        engine_changed = new_engine != self.ctx.settings["plot_engine"]
        self.ctx.settings["plot_engine"] = new_engine
        self.accept()

        if engine_changed:
            from .ui.main_window import switch_plot_engine
            switch_plot_engine(self.ctx)


def open_options_dialog(ctx):
    dlg = OptionsDialog(ctx.win, ctx)
    dlg.exec()
