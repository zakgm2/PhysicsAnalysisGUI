"""
analysis/field_study_validation.py
-------------------------------------
Statistical validation results viewer (see PhysicsLibrary's
run_validation_pipeline / build_validation_summary): permutation
p-values (+ FDR correction across pairs), Cohen's d, word-count-
controlled regression, bootstrap confidence interval, and leave-one-out
sensitivity flags for the study's paired-similarity metrics.

Re-runs embeddings + similarity in the background rather than reusing
anything from the main results table — see launch_field_study_validation.
Same dialog + QTableWidget + CSV export shape as
analysis/text_field_study.py's results viewer.
"""

import datetime
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFileDialog, QHeaderView,
)

import PhysicsLibrary as pl

from ..background import run_in_background
from ..toasts import show_error, show_window_toast


def _verdict(p_fdr, ci_lower):
    """Plain-language read of the numbers, for a quick glance before
    digging into the actual columns. Not a substitute for looking at
    p_value_fdr/cohens_d/ci_lower/ci_upper yourself — just a starting point."""
    import math
    if math.isnan(p_fdr):
        return "Not enough data yet"
    if p_fdr < 0.05 and ci_lower > 0:
        return "Likely a real effect"
    if p_fdr < 0.10:
        return "Weak/borderline — worth more subjects"
    return "No evidence of an effect"


class ValidationSummaryDialog(QDialog):
    """One row per field pair — see PhysicsLibrary.build_validation_summary's
    docstring for what each column means (also the source for a
    write-up-ready explanation of each statistic). Plus full CSV export."""

    def __init__(self, ctx, summary_df):
        super().__init__(ctx.win)
        self.ctx = ctx
        self.df = summary_df
        self.setWindowTitle("Statistical Validation")
        self.resize(1050, 400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            f"{len(summary_df)} pair(s). \"Verdict\" is a plain-language quick read, based on "
            "p_value_fdr (is it likely real, after correcting for testing multiple pairs) and "
            "whether the confidence interval clears zero — check the actual numbers before "
            "trusting it. See PhysicsLibrary.build_validation_summary's docstring for what "
            "every column means."
        ))

        columns = ["verdict"] + list(summary_df.columns)
        table = QTableWidget(len(summary_df), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for r in range(len(summary_df)):
            row = summary_df.iloc[r]
            verdict = _verdict(row["p_value_fdr"], row["ci_lower"])
            table.setItem(r, 0, QTableWidgetItem(verdict))
            for c, col in enumerate(summary_df.columns, start=1):
                value = row[col]
                text = f"{value:.4f}" if isinstance(value, float) else str(value)
                table.setItem(r, c, QTableWidgetItem(text))
        # See text_field_study.py's results dialog for why ResizeToContents
        # (not Stretch) — same reasoning applies here.
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_csv = QPushButton("Export CSV")
        btn_csv.clicked.connect(self._export_csv)
        btn_row.addWidget(btn_csv)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _export_csv(self):
        ts = datetime.datetime.now().strftime("%H%M%S")
        start_dir = self.ctx.last_dir or self.ctx.settings["default_folder"]
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Statistical Validation",
            os.path.join(start_dir, f"StatisticalValidation_{ts}.csv"),
            "CSV (*.csv);;Text (*.txt)"
        )
        if not path:
            return
        try:
            self.df.to_csv(path, index=False)
            show_window_toast(self.ctx, "Statistical Validation Exported")
        except Exception as e:
            show_error(self.ctx, f"Export Failed: {e}")


def launch_field_study_validation(ctx):
    if ctx.study_data is None or ctx.study_data_path is None or ctx.study_data_config is None:
        show_error(ctx, "No text field study loaded — use Text Field Study ▾ → 1. Open Study Folder first.")
        return
    config = ctx.study_data_config
    paired_fields = config.get("paired_fields")
    if not paired_fields:
        show_error(ctx, "No field comparisons configured for this study — statistical "
                        "validation needs at least one comparison.")
        return

    def _work():
        return pl.run_validation_pipeline(
            ctx.study_data_path,
            text_fields=config["text_fields"],
            paired_fields=paired_fields,
            file_glob=config.get("file_glob", "P-*.json"),
        )

    def _on_success(summary_df):
        dlg = ValidationSummaryDialog(ctx, summary_df)
        dlg.exec()

    def _on_error(msg):
        show_error(ctx, msg)

    if ctx.settings.get("background_loading"):
        # Re-embeds from scratch (doesn't reuse the main results table's
        # embeddings, which aren't kept around) plus a bootstrap and a
        # leave-one-out pass per pair — can take a while.
        show_window_toast(ctx, "Running statistical validation… this can take a while")
    run_in_background(ctx, _work, _on_success, _on_error)
