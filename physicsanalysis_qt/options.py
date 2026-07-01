"""
options.py
----------
Options dialog: default folder for Open dialogs, and performance settings
(render decimation, background loading).
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QSpinBox, QFileDialog, QGroupBox,
)


class OptionsDialog(QDialog):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Options")
        self.resize(480, 260)
        layout = QVBoxLayout(self)

        gb_folder = QGroupBox("File Dialogs")
        g1 = QGridLayout(gb_folder)
        g1.addWidget(QLabel("Default folder:"), 0, 0)
        self.e_folder = QLineEdit(ctx.settings["default_folder"])
        g1.addWidget(self.e_folder, 0, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        g1.addWidget(btn_browse, 0, 2)
        layout.addWidget(gb_folder)

        gb_perf = QGroupBox("Performance")
        g2 = QGridLayout(gb_perf)
        g2.addWidget(QLabel("Max rendered points per trace:"), 0, 0)
        self.spin_points = QSpinBox()
        self.spin_points.setRange(200, 20000)
        self.spin_points.setSingleStep(200)
        self.spin_points.setValue(ctx.settings["decimate_max_points"])
        g2.addWidget(self.spin_points, 0, 1)

        self.cb_threaded = QCheckBox(
            "Load data files on a background thread\n"
            "(keeps the UI responsive during large TDT/Oxysoft loads)"
        )
        self.cb_threaded.setChecked(ctx.settings["background_loading"])
        g2.addWidget(self.cb_threaded, 1, 0, 1, 2)
        layout.addWidget(gb_perf)

        note = QLabel(
            "Note: plotting runs on matplotlib's CPU (Agg) renderer — there is no\n"
            "GPU-accelerated backend for this library. The settings above reduce\n"
            "how much CPU work is needed per frame/load instead of using the GPU."
        )
        note.setStyleSheet("color: gray;")
        note.setWordWrap(True)
        layout.addWidget(note)

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
        self.accept()


def open_options_dialog(ctx):
    dlg = OptionsDialog(ctx.win, ctx)
    dlg.exec()
