"""
loaders/oxysoft.py
--------------------
Oxysoft / Artinis NIRS .txt export loading. Native dataset events are
populated automatically as markers.
"""

import os

import numpy as np
from PyQt6.QtWidgets import QFileDialog

import PhysicsLibrary as pl

from ..background import run_in_background
from ..sidecar import load_markers_from_sidecar
from ..toasts import show_error, show_success, show_window_toast


def open_file(ctx):
    start_dir = ctx.last_dir or ctx.settings["default_folder"]
    path, _ = QFileDialog.getOpenFileName(
        ctx.win, "Open Data File", start_dir,
        "All supported (*.txt *.csv *.tsv);;Text files (*.txt);;CSV files (*.csv);;All files (*.*)"
    )
    if path:
        ctx.last_dir = os.path.dirname(path)
        _load_single_file(ctx, path)


def _load_single_file(ctx, file_path):
    from ..plotting import simple_plot

    def _work():
        return pl.load_dataset_file(file_path)

    def _on_success(ds):
        n_ch = ds.metadata.get('n_channels', ds.num_channels // 2)
        o2hb = ds.signals[:n_ch]
        hhb = ds.signals[n_ch:]
        ctx.cache = {
            'source':          'Oxysoft',
            'source_path':     file_path,
            'store':           ds.folder_name,
            'x':               np.arange(ds.num_samples) / ds.sample_rate,
            'o2hb':            o2hb,
            'hhb':             hhb,
            'fs':              ds.sample_rate,
            'fit_factor_mean': ds.metadata.get('fit_factor_mean'),
            'markers': [
                {"time": ev["sample"] / ds.sample_rate, "label": ev["label"], "color": "black"}
                for ev in ds.events
            ],
        }
        if 'thb' in ds.metadata:
            ctx.cache['thb'] = ds.metadata['thb']

        load_markers_from_sidecar(ctx)
        simple_plot(ctx)
        show_success(ctx, f"File: {os.path.basename(file_path)}")

    def _on_error(msg):
        show_error(ctx, msg)

    if ctx.settings.get("background_loading"):
        show_window_toast(ctx, "Loading Oxysoft file…")
    run_in_background(ctx, _work, _on_success, _on_error)
