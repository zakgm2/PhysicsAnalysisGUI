# Physics Analysis GUI

A desktop application for loading, visualising, and analysing physics lab data.

Supports TDT fibre photometry recordings, Oxysoft / Artinis NIRS exports, generic tabular data (Excel, CSV, TSV, plain text), and Terranova Prospa EFNMR/MRI `.pt2` images.

Two interchangeable GUI implementations are included:

| File | Framework | Status |
|------|-----------|--------|
| `PhysicsAnalysisGUI.py` | tkinter | Stable, full feature set |
| `run_qt.py` | PyQt6 | Full feature parity with the tkinter version |

Both share the same underlying logic from [PhysicsLibrary](https://github.com/zakgm2/PhysicsLibrary) — only the widget/window layer differs.

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
- **Markers** — click to place event markers with custom name, colour, and font size; right-click to edit or delete; auto-saved as a `.markers.json` sidecar; TDT/Oxysoft native event markers load automatically
- **Edit Attributes** — customise plot title, axis labels, font sizes, and legend entries; changes persist across zoom/pan/hover
- **Golden-ratio font scaling** — all figure text scales proportionally to figure size
- **Grid toggle** — show/hide background grid from the toolbar
- **TSI Fit Factor** — extracted automatically from Oxysoft files and shown in the legend

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

> **Note:** `tkinter` ships with the standard Python installer on Windows and macOS.
> On Linux install it with `sudo apt install python3-tk`.

---

## Running

```bash
# tkinter version
python PhysicsAnalysisGUI.py

# PyQt6 version
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
| Place marker | Enable **Add Marker**, then left-click the plot |
| Edit / delete marker | Right-click near a marker |
| Fit curve | Select **Curve Fit** mode, click two points |
| Run FFT / PETH | Select mode from dropdown, double-click the plot |

---

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the full changelog.

| Version | Summary |
|---------|---------|
| 2.0.0 | PyQt6 GUI port added alongside the tkinter version |
| 1.3.0 | Golden-ratio proportional font sizing, resize-safe zoom |
| 1.2.0 | PT2 EFNMR image viewer, scroll/double-click zoom fixes |
| 1.1.0 | Generic file parser, Excel support, blit hover, curve fit export, marker editing |
| 1.0.0 | Full GUI with TDT and Oxysoft support |
| 0.1.0 | Initial file parser and plotting prototype |
