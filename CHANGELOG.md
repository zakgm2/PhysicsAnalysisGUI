# Changelog — Physics Analysis GUI

---

## v2.0.0
**New:**
- `run_qt.py` — full PyQt6 port of the GUI, added alongside the existing tkinter version (`PhysicsAnalysisGUI.py`). Full feature parity: file loading (TDT/Oxysoft/Generic/PT2), blit-based hover/zoom/pan, rect-select zoom, resize-safe zoom, Add/Edit Marker, Edit Attributes, Curve Fit, PETH, FFT, PT2 viewer.
- Golden-ratio font sizing carried over unchanged from v1.3.0 (pure matplotlib logic, framework-agnostic).

**Bug fixes (found during Qt port testing):**
- Fixed a phantom rectangle-selector: double-click → analysis dialog (FFT/PETH) → close, then moving the mouse would draw a selection rectangle following the cursor. `RectangleSelector` never received the button-release event for that click because it was consumed inside the modal dialog's nested event loop. Fixed by deactivating the selector before the dialog opens and deferring reactivation to the next Qt event-loop tick.
- Fixed `launch_fft` crashing with `KeyError: 'corr'` on Generic-source (CSV/Excel) data — it assumed TDT-only cache keys. Falls back to the first Y-column for Generic data. (Pre-existing bug, also present in the tkinter version.)
- Fixed TDT folders and Oxysoft files no longer auto-placing their native event markers on load — the loader was hardcoding `markers: []` instead of using the epoc/event data already returned by `process_tdt_folder()` / `load_dataset_file()`, and the sidecar loader was unconditionally wiping markers to `[]` when no `.markers.json` sidecar existed.

**Known issue:**
- Do not run `run_qt.py` from inside Spyder's console/Run button — Spyder's own UI is built on PyQt5, and loading PyQt6 in the same process causes a `DLL load failed while importing QtWidgets` crash. Edit the file in Spyder as normal, but launch it from a plain terminal (`python run_qt.py`).

Both GUI versions are kept side by side for now; the tkinter version remains the fallback until the Qt version has more real-world use.

---

## v1.3.0
**Improvements:**
- Golden-ratio font sizing: all secondary figure windows (PETH, FFT, PT2 viewer, curve fit) now scale title, axis label, and legend fonts proportionally to the figure diagonal, with each tier related by φ ≈ 1.618.
- Font sizes apply from first load — no longer require opening Edit Attributes first.
- Figures with multiple subplots (PETH, Oxysoft FFT) automatically halve font sizes to avoid crowding.

**Bug fixes:**
- Window resize no longer breaks zoom/scroll: canvas `resize_event` now invalidates the blit background and reschedules a fresh capture.

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
