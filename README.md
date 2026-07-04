# Physics Analysis GUI

A PyQt6 desktop application for loading, visualising, and analysing physics lab data.

Supports TDT fibre photometry recordings, Oxysoft / Artinis NIRS exports, generic tabular data (Excel, CSV, TSV, plain text), and Terranova Prospa EFNMR/MRI `.pt2` images.

Built on shared logic from [PhysicsLibrary](https://github.com/zakgm2/PhysicsLibrary) — this repo is the widget/window layer.

The main plot can render with either **matplotlib** (CPU) or **PyQtGraph** (GPU-accelerated, handles large recordings much better) — switch anytime in **Options**. FFT/PETH/Curve Fit/PT2 windows always use matplotlib regardless of the main-plot engine.

> A tkinter version of this GUI existed prior to v2.2.0 and has been removed — the PyQt6 version now has full feature parity plus the GPU engine, Options dialog, and background loading. Its history remains in `git log -- PhysicsAnalysisGUI.py` if ever needed.

---

## Features

- **Multi-format loading** — TDT tank folders, Oxysoft `.txt` exports, any Excel/CSV/TSV file, and Terranova `.pt2` EFNMR/MRI images, via a unified open menu
- **Sub-table detection** — automatically finds multiple side-by-side tables in a single Excel sheet
- **Interactive plot** — scroll to zoom, right-click drag to pan, rectangle select to zoom into a region, resize-safe
- **Hover snap** — tracker dots snap to the nearest plotted line and display exact values
- **Curve fitting** — click two points to fit a model (linear, exponential, Gaussian, sinusoidal, …) to that segment; copy or export parameters as CSV
- **FFT viewer** — frequency analysis window with automatic peak annotation
- **PETH / Z-score** — peri-event time histogram for TDT data
- **PT2 image viewer** — colormap selector, live title editing, PNG/PDF/SVG export
- **Markers** — a fresh load starts with no markers on screen; use **Add Marker** to bulk-add auto-detected event markers by store (multi-select, add/remove in one action, High/Low phase checkboxes), or configure a custom name/colour/font size once and stamp repeated markers Snipping-Tool style (click, click, click, then stop); a separate multi-select **Remove Markers** list handles batch cleanup; right-click a marker to rename/delete it (or delete every marker sharing that name) individually; markers auto-save as a `.markers.json` sidecar
- **High/low phase** — auto-detected markers show both onset (high, superscript ¹) and offset (low, superscript ⁰) by default High-only; useful for anything where on-duration matters (a pump, a light), not just the press
- **Rename stores** — right-click a marker → Rename → "Rename all" applies to every marker from that store at once (or just the one instance); the Add Marker dialog's store list supports the same inline (right-click a store, type, Enter); **Reset Name** reverts back to the raw store id
- **Measure Intervals** — a table of every marker currently on the plot, sorted by time, with time-since-previous-in-store (on-duration for high/low pairs) and time-since-previous-any-marker columns; exportable as CSV
- **Analysis window** — a single **Window** button opens a dialog for the pre/post seconds around an FFT/PETH/Curve Fit click: symmetric (one total size, split evenly) or asymmetric (independent before/after, e.g. 10s before, 20s after)
- **Edit Attributes** — customise plot title, axis labels, font sizes, and legend entries; changes persist across zoom/pan/hover
- **Golden-ratio font scaling** — all figure text scales proportionally to figure/widget size and stays live during window resize, on both plot engines
- **Grid toggle** — show/hide background grid from the toolbar
- **TSI Fit Factor** — extracted automatically from Oxysoft files and shown in the legend
- **Options dialog** — default folder for Open dialogs, main-plot render decimation, background-thread loading, and CPU/GPU plot engine selection

---

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt` / `pyproject.toml`

---

## Installation

```bash
git clone https://github.com/zakgm2/PhysicsAnalysis.git
cd PhysicsAnalysis
pip install -r requirements.txt
```

---

## Running

```bash
python run_qt.py
```

> **Spyder users:** do not run `run_qt.py` via Spyder's Run button or console — Spyder's own UI is built on PyQt5, and loading PyQt6 in the same process causes a `DLL load failed while importing QtWidgets` crash. Edit the file in Spyder normally, but launch it from a plain terminal.

---

## Loading Data

| Menu item | What it opens |
|-----------|----------------|
| **Open TDT Folder** | A TDT tank directory (`.Tbk`, `.tev`, … files) |
| **Open TXT (Oxysoft)** | A single Oxysoft / Artinis `.txt` export |
| **Open Excel/CSV/TSV** | Any tabular file — a dialog lets you pick X and Y columns |
| **Open PT2 (EFNMR)** | A Terranova Prospa `.pt2` 2D image file |

---

## Keyboard & Mouse

| Action | How |
|--------|-----|
| Zoom in / out | Scroll wheel |
| Pan | Right-click drag |
| Zoom to region | Left-click drag (rectangle select) |
| Reset zoom | **Reset Zoom** button |
| Place markers | **Add Marker** → *Place Custom Markers* → Start Placing, then left-click the plot repeatedly; click **Add Marker** again to stop |
| Add auto-detected markers | **Add Marker** → *Add / Remove Auto-Detected Markers* → select store(s) → Add Selected |
| Remove markers | **Add Marker** → *Remove Markers* → select marker(s) → Remove Selected |
| Edit / delete a single marker | Right-click near it |
| Rename / reset / delete all of one name | Right-click near it → Rename (with "all" toggle) / Reset Name / Delete all |
| Rename a store inline | Add Marker → right-click a store in the list → type → Enter |
| Measure time between events | **Measure Intervals** button |
| Set analysis window | **Window** button → symmetric size or independent before/after |
| Fit curve | Select **Curve Fit** mode, click two points |
| Run FFT / PETH | Select mode from dropdown, double-click the plot |

---

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the full changelog.

| Version | Summary |
|---------|---------|
| 2.3.0 | High/low phase markers, store renaming, Measure Intervals, working Reload, inline-rename Qt bug fixes |
| 2.2.0 | Redesigned opt-in marker workflow, asymmetric analysis window, live-resize fonts/margins, tkinter version removed |
| 2.1.0 | PyQtGraph (GPU) plot engine option, Options dialog, background loading |
| 2.0.0 | PyQt6 GUI port added alongside the tkinter version |
| 1.3.0 | Golden-ratio proportional font sizing, resize-safe zoom |
| 1.2.0 | PT2 EFNMR image viewer, scroll/double-click zoom fixes |
| 1.1.0 | Generic file parser, Excel support, blit hover, curve fit export, marker editing |
| 1.0.0 | Full GUI with TDT and Oxysoft support |
| 0.1.0 | Initial file parser and plotting prototype |
