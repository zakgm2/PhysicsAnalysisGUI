# Physics Analysis GUI

A desktop application for loading, visualising, and analysing physics lab data. Built with Python, tkinter, and matplotlib.

Supports TDT fibre photometry recordings, Oxysoft / Artinis NIRS exports, and generic tabular data (Excel, CSV, TSV, plain text).

---

## Features

- **Multi-format loading** — TDT tank folders, Oxysoft `.txt` exports, and any Excel/CSV/TSV file via a unified open menu
- **Sub-table detection** — automatically finds multiple side-by-side tables in a single Excel sheet
- **Interactive plot** — scroll to zoom, right-click drag to pan, rectangle select to zoom into a region
- **Hover snap** — tracker dots snap to the nearest plotted line and display exact values
- **Curve fitting** — click two points to fit a model (linear, exponential, Gaussian, sinusoidal, …) to that segment; copy or export parameters as CSV
- **Slope analysis** — two-click slope measurement with annotation
- **FFT viewer** — frequency analysis window with automatic peak annotation
- **PETH / Z-score** — peri-event time histogram for TDT data
- **Markers** — click to place event markers with custom name, colour, and font size; right-click to edit or delete; auto-saved as a `.markers.json` sidecar
- **Edit Attributes** — customise plot title, axis labels, font sizes, and legend entries
- **Grid toggle** — show/hide background grid from the toolbar
- **TSI Fit Factor** — extracted automatically from Oxysoft files and shown in the legend

---

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`

---

## Installation

```bash
# Clone the repo
git clone https://github.com/zakgm2/PhysicsAnalysis.git
cd PhysicsAnalysis

# Install dependencies
pip install -r requirements.txt
```

> **Note:** `tkinter` ships with the standard Python installer on Windows and macOS.  
> On Linux install it with `sudo apt install python3-tk`.

---

## Running

```bash
python PhysicsAnalysisGUI.py
```

---

## Loading Data

| Button | What it opens |
|--------|---------------|
| **Open TDT folder** | A TDT tank directory (`.Tbk`, `.tev`, … files) |
| **Open TXT (Oxysoft)** | A single Oxysoft / Artinis `.txt` export |
| **Open Excel** | Any `.xlsx`, `.csv`, `.tsv`, or `.txt` table — a dialog lets you pick X and Y columns |

After selecting a file, click **Load** to plot it.

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

---

## Version History

See `PhysicsLibrary/pyproject.TOML` for the full changelog.

| Version | Summary |
|---------|---------|
| 1.1.0 | Generic file parser, Excel support, blit hover, curve fit export, marker editing |
| 1.0.0 | Full GUI with TDT and Oxysoft support |
| 0.1.0 | Initial file parser and plotting prototype |
