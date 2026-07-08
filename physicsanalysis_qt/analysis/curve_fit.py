"""
analysis/curve_fit.py
------------------------
Curve Fit dialog: two anchor points on the main plot define a segment,
fit any registered model to it, view R^2/params, export CSV or copy to
clipboard, export the fit plot.
"""

import csv
import datetime
import os

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QFrame, QFileDialog, QApplication,
)

import PhysicsLibrary as pl

from ..fonts import fig_font_sizes
from ..toasts import show_error, show_window_toast
from .dispatch import get_window, export_figure_to_file
from .models_registry import CURVE_FIT_MODELS


class CurveFitDialog(QDialog):
    def __init__(self, parent, ctx, source_line, p1_tuple, p2_tuple):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Curve Fit")
        self.resize(720, 680)
        self.last_fit_results = []

        p1_idx = p1_tuple[0]
        p2_idx = p2_tuple[0]
        self.i1, self.i2 = sorted([p1_idx, p2_idx])

        ax = ctx.ax
        raw_xlbl = ax.get_xlabel() or ctx.plot_attrs.get("xlabel") or ""
        raw_ylbl = ax.get_ylabel() or ctx.plot_attrs.get("ylabel") or ""
        self.clean_xlbl = str(raw_xlbl).replace(" (s)", "").replace("(s)", "").strip() or "Time"
        self.clean_ylbl = str(raw_ylbl).strip() or "Signal"

        cache = ctx.cache
        self.x_data = cache['x']
        self.raw_channel_data = {}
        if 'o2hb' in cache and 'hhb' in cache:
            self.raw_channel_data['Mean O2Hb'] = {
                'y': cache['o2hb'].mean(axis=0) if cache['o2hb'].ndim > 1 else cache['o2hb'],
                'color': '#CC0000',
            }
            self.raw_channel_data['Mean HHb'] = {
                'y': cache['hhb'].mean(axis=0) if cache['hhb'].ndim > 1 else cache['hhb'],
                'color': '#0033CC',
            }
            if 'thb' in cache:
                self.raw_channel_data['Mean tHb'] = {
                    'y': cache['thb'].mean(axis=0) if cache['thb'].ndim > 1 else cache['thb'],
                    'color': '#228B22',
                }
        else:
            sig = cache.get('corr', cache.get('raw'))
            lbl = 'dF/F (corrected)' if 'corr' in cache else 'Raw signal'
            self.raw_channel_data[lbl] = {'y': sig, 'color': '#2196F3'}

        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(list(CURVE_FIT_MODELS.keys()))
        ctrl.addWidget(self.model_combo)

        recalc_btn = QPushButton("Recalculate Fit")
        recalc_btn.setDefault(True)
        recalc_btn.clicked.connect(self._run_fit)
        ctrl.addWidget(recalc_btn)

        ctrl.addWidget(QLabel("Window (s):"))
        pre, post = get_window(ctx)
        self.win_entry = QLineEdit(str(int(pre + post)))
        self.win_entry.setFixedWidth(50)
        ctrl.addWidget(self.win_entry)
        ctrl.addStretch(1)
        layout.addLayout(ctrl)

        self.result_lbl = QLabel("Results will appear here after fitting.")
        self.result_lbl.setFont(QFont("Consolas", 9))
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setFrameShape(QFrame.Shape.Panel)
        self.result_lbl.setStyleSheet("background-color: white; color: black; padding: 8px;")
        layout.addWidget(self.result_lbl)

        self.sub_fig = Figure(figsize=(6, 3.5), dpi=100)
        self.sub_ax = self.sub_fig.add_subplot(111)
        self.sub_canvas = FigureCanvasQTAgg(self.sub_fig)
        layout.addWidget(self.sub_canvas, stretch=1)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("Copy")
        btn_copy.clicked.connect(self._copy_params)
        btn_csv = QPushButton("Export CSV")
        btn_csv.clicked.connect(self._export_csv)
        btn_plot = QPushButton("Export Plot")
        btn_plot.clicked.connect(lambda: export_figure_to_file(ctx, self.sub_fig, "CurveFit"))
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        for b in (btn_copy, btn_csv, btn_plot, btn_close):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._run_fit()

    def _run_fit(self):
        model_name = self.model_combo.currentText()
        model_fn, p0_fn, pnames = CURVE_FIT_MODELS[model_name]
        is_linear = model_name.startswith("Linear")
        i1, i2 = self.i1, self.i2
        x_data = self.x_data

        try:
            win_sec = max(1.0, float(self.win_entry.text()))
        except ValueError:
            win_sec = 30.0
        half_win = win_sec / 2

        t1 = float(x_data[i1])
        t2 = float(x_data[i2])
        t_mid = (t1 + t2) / 2

        view_start = max(float(x_data[0]), t_mid - half_win)
        view_end = min(float(x_data[-1]), t_mid + half_win)
        view_start = min(view_start, t1)
        view_end = max(view_end, t2)

        w_start = int(np.searchsorted(x_data, view_start))
        w_end = int(np.searchsorted(x_data, view_end))
        w_end = min(w_end, len(x_data) - 1)

        self.sub_ax.clear()
        lines_text = []
        fit_rows = []

        for lname, cfg in self.raw_channel_data.items():
            y_full = cfg['y']
            color = cfg['color']
            x_seg = x_data[i1:i2 + 1]
            y_seg = y_full[i1:i2 + 1]
            if len(x_seg) < 4:
                continue

            delta_x = t2 - t1
            delta_y = float(y_seg[-1] - y_seg[0])

            self.sub_ax.plot(x_data[w_start:w_end + 1], y_full[w_start:w_end + 1],
                              color=color, lw=1.0, alpha=0.3)
            self.sub_ax.plot(x_seg, y_seg, color=color, lw=2.0, label=f"{lname}")

            res = pl.fit_model_to_segment(x_seg, y_seg, model_fn, p0_fn)
            header = (
                f"[{lname}]\n"
                f"   P1: ({t1:.2f}s, {float(y_seg[0]):.4f})"
                f"  |  P2: ({t2:.2f}s, {float(y_seg[-1]):.4f})\n"
                f"   d{self.clean_xlbl}: {delta_x:.3f} s"
                f"  |  d{self.clean_ylbl}: {delta_y:.5f}\n"
            )

            if res["success"]:
                param_str = "   ".join(f"{n} = {v:.4g}" for n, v in zip(pnames, res["popt"]))
                entry = header + f"   {param_str}\n   R2 = {res['r2']:.4f}"
                self.sub_ax.plot(x_seg, res["y_fit"], color=color, lw=2.5,
                                  linestyle='--', label=f"{lname} fit  R2={res['r2']:.3f}")
                if is_linear:
                    self.sub_ax.plot([t1, t2], [float(y_seg[0]), float(y_seg[-1])],
                                      'o', color=color, markersize=6, zorder=5)
                fit_rows.append({
                    "channel": lname, "model": model_name, "param_names": pnames,
                    "param_values": list(res["popt"]), "r2": res["r2"],
                    "t1": t1, "t2": t2,
                })
            else:
                entry = header + f"   Fit failed: {res['error']}"

            lines_text.append(entry)

        self.sub_ax.axvspan(t1, t2, alpha=0.10, color='gold', zorder=0)
        self.sub_ax.axvline(t1, color='gray', lw=1.0, linestyle='--', alpha=0.6)
        self.sub_ax.axvline(t2, color='gray', lw=1.0, linestyle='--', alpha=0.6)

        tfs, lfs, lgfs = fig_font_sizes(self.sub_fig)
        self.sub_ax.set_xlabel(f"{self.clean_xlbl} (s)", fontweight='bold', fontsize=lfs)
        self.sub_ax.set_ylabel(self.clean_ylbl, fontweight='bold', fontsize=lfs)
        self.sub_ax.legend(fontsize=lgfs, loc='best')
        self.sub_ax.set_title(f"Curve Fit — {model_name.split('(')[0].strip()}",
                               fontweight='bold', fontsize=tfs)
        self.sub_ax.grid(True, linestyle=':', alpha=0.5)
        self.sub_fig.tight_layout()
        self.sub_ax.set_xlim(view_start, view_end)
        self.sub_canvas.draw()

        divider = "\n" + "-" * 60 + "\n"
        self.result_lbl.setText(divider.join(lines_text) or "No data found.")
        self.last_fit_results = fit_rows

    def _copy_params(self):
        txt = self.result_lbl.text()
        if not txt or txt == "Results will appear here after fitting.":
            return
        QApplication.clipboard().setText(txt)
        show_window_toast(self.ctx, "Parameters copied to clipboard")

    def _export_csv(self):
        if not self.last_fit_results:
            show_error(self.ctx, "Run the fit first.")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        start_dir = self.ctx.last_dir or self.ctx.settings["default_folder"]
        path, _ = QFileDialog.getSaveFileName(
            self, "Export fit parameters", os.path.join(start_dir, f"CurveFit_{ts}.csv"),
            "CSV (*.csv);;Text (*.txt)"
        )
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(["Channel", "Model", "Parameter", "Value", "R2",
                              "t1 (s)", "t2 (s)", "dt (s)"])
            for row in self.last_fit_results:
                for pname, pval in zip(row["param_names"], row["param_values"]):
                    writer.writerow([row["channel"], row["model"], pname,
                                      f"{pval:.6g}", f"{row['r2']:.4f}",
                                      f"{row['t1']:.4f}", f"{row['t2']:.4f}",
                                      f"{row['t2'] - row['t1']:.4f}"])
        show_window_toast(self.ctx, f"Saved {os.path.basename(path)}")


def launch_curve_fit(ctx, source_line, p1_tuple, p2_tuple):
    dlg = CurveFitDialog(ctx.win, ctx, source_line, p1_tuple, p2_tuple)
    dlg.exec()
