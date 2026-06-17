# Changelog — Physics Analysis GUI

---

## v1.3.0
**Improvements:**
- Golden-ratio font sizing: all secondary figure windows (PETH, FFT, PT2 viewer, curve fit) now scale title, axis label, and legend fonts proportionally to the figure diagonal, with each tier related by φ ≈ 1.618.
- Font sizes apply from first load — no longer require opening Edit Attributes first.
- Figures with multiple subplots (PETH, Oxysoft FFT) automatically halve font sizes to avoid crowding.

---

## v1.2.0
**New features:**
- Terranova EFNMR `.pt2` image viewer: opens 2D NMR/MRI images in a dedicated window with colormap selector, editable title, and PNG/PDF/SVG export. Supports all square power-of-two image sizes (16×16 through 256×256) with automatic dimension detection.

**Bug fixes:**
- Scroll zoom no longer snaps back and forth: stale blit background is invalidated immediately on scroll so `on_motion` cannot restore a stale frame before the refresh fires.
- Double-click no longer triggers rect-select zoom: `on_select` now checks `eclick.dblclick` and uses a 10-pixel distance threshold (replaces the 0.1 data-unit threshold that failed on long recordings).
- Marker colour is now editable via right-click → Edit Marker.
- Added black as a marker colour option (matches TDT default).

---

## v1.1.0
**New features:**
- Generic file parser: supports Excel (`.xlsx`), CSV, TSV, and plain text with automatic sub-table detection for side-by-side data layouts.
- Open button consolidated into a single dropdown menu (Open TDT / Open TXT Oxysoft / Open Excel).
- Excel/generic data loads directly into the main GUI plot with full snap and hover support.
- TSI Fit Factor extracted from Oxysoft `.txt` files and displayed as `[FF: x.x%]` in the legend.
- Curve fit parameters can be copied to clipboard or exported as a CSV file.
- Grid toggle checkbox added to the toolbar.
- Marker enhancements: font size and colour editable when adding and via right-click. Colour options: green, red, blue, orange, purple, black.

**Bug fixes and performance:**
- Blit-based hover animation: tracker dots drawn via `restore_region` / `draw_artist` / `blit` instead of `canvas.draw_idle()`, making hover ~20–50× faster.
- Scroll zoom debounced (150 ms) and scale reduced to 1.1× per tick for smoother zooming.
- Tracker dots no longer disappear during scroll zoom; dots no longer cause autoscale zoom.
- Rect-select drag no longer accidentally triggers a curve fit click on release.
- Oxysoft hover snap now correctly targets mean lines (O₂Hb, HHb, tHb) by linewidth filter.
- Edit Attributes changes now persist correctly across all view interactions (zoom, pan, hover).

---

## v1.0.0
- Full GUI with TDT and Oxysoft NIRS support.
- Interactive plot with scroll zoom, right-click pan, and rectangle select zoom.
- Curve fitting, slope analysis, FFT viewer, and PETH/Z-score windows.
- Event markers with colour picker, sidecar save/load.

---

## v0.1.0
- Initial prototype: file parser and basic plotting.
