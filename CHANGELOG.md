# Changelog — Physics Analysis GUI

---

## v2.3.0
**New: high/low phase for auto-detected markers**
- Every TDT epoc is a state that goes high (onset — a press, a light/pump turning on) and later low (offset — the release, turning off). `get_event_markers()` (PhysicsLibrary 1.4.0) now surfaces both instead of only onset.
- The Add Marker dialog's auto-detected section has **High**/**Low** checkboxes (High on by default) controlling which edges get bulk-added — most stores (lever presses, etc.) only need the press; a pump or light also benefits from the release/off edge for computing on-duration.
- Every phase-tagged marker on the plot now shows a superscript **¹** (high) or **⁰** (low) next to its label.

**New: rename auto-detected store names**
- Right-click a marker → **Rename** now offers "Rename all '\<store\>' markers" (checked by default) — applies to every marker from that store, past and future, instead of just the one instance. The store's raw id (e.g. `PP1_`) stays the internal grouping key everywhere; only the display changes.
- The Add Marker dialog's store list supports the same thing inline: right-click a store to turn it into an editable text box, Enter to save — no separate dialog needed. Left-click still multi-selects normally.
- **Reset Name** — in the Edit Marker dialog (only shown once a store has a custom name) and as a **Reset Selected Names** button in the Add Marker dialog's store list — reverts back to the raw store id.
- New **"Delete all '\<name\>' markers"** action in the right-click menu, next to the existing single Delete — removes every marker sharing that name (both phases together for a renamed/auto-detected store, since they're "the same name" once renamed, just a different superscript).
- Note markers (free-text annotations like 'Clap') and manually-placed markers are never affected by store renames — their label was never derived from a store name to begin with.

**New: Measure Intervals**
- New **Measure Intervals** toolbar button: a table of every marker currently on the plot (any source — TDT, Oxysoft, or manually placed), sorted by time, with two interval columns — time since the previous event in the same store (which is exactly the on-duration for a store with alternating high/low phases) and time since the previous marker of any kind (useful when several event types are interleaved). Exportable as CSV.

**New: single Reload actually reloads**
- **Reload** previously just re-opened the same file picker as Open. It now re-reads the currently loaded folder/file from disk in place: TDT/Oxysoft skip the dialog entirely, Generic (Excel/CSV/TSV) re-parses the same file and reopens the table/column picker (skipping only the file-choice step). Falls back to Open if nothing's loaded yet.

**Fixes**
- Fixed several real Qt bugs found while building the inline store-rename box: the built-in item-editing delegate (`editItem()`) painted the old text underneath/offset from the new editor rather than replacing it — replaced with a manually-managed `QLineEdit` overlay; committing on Enter was falling through to the dialog's default button ("Start Placing"), dropping the user straight into marker-placement mode, because the editor was torn down synchronously while still inside its own Return-keypress dispatch; clicking a dialog button (e.g. "Add Selected") while a rename was still uncommitted needed two clicks to register, because auto-committing on focus-loss destroyed the editor mid-dispatch of its own focus-out event, corrupting that same click's delivery to the button. Renaming now only auto-commits from inside the editor on Enter/Escape; any other dialog action explicitly flushes a pending rename first (silently, folded into that action's own single redraw) before proceeding — so renaming and then immediately clicking Add/Remove/Start Placing now takes exactly one click.

---

## v2.2.0
**New: redesigned marker workflow**
- Fresh loads (TDT and Oxysoft) no longer auto-populate the plot with every detected event marker — a busy TDT recording can easily have a dozen+ epoc stores (I/O strobes, Tick, Epoch Event Storage, …) that used to overlap into an unreadable mess. Auto-detected markers are now kept separately (`detected_markers`) and only added when you ask for them.
- **Add Marker** now opens a dialog instead of immediately entering placement mode:
  - **Add / Remove Auto-Detected Markers** — multi-select one or more stores (ctrl/shift-click) and Add Selected or Remove Selected in one action.
  - **Place Custom Markers** — configure a name/colour/font size once, then **Start Placing**: click the plot repeatedly to stamp markers with that config (Snipping-Tool style) until you toggle Add Marker off again — no more re-opening a dialog for every single marker.
  - **Remove Markers** — a multi-select list of every marker currently on the plot (auto-detected or custom), with Select All + Remove Selected for fast batch cleanup.
- Removed the "Undo Last" toolbar button — redundant now that removal is multi-select and immediate.

**New: asymmetric analysis window**
- The always-visible "Window (s)" field is now a single **Window** toolbar button showing the current setting, opening a small dialog: **Symmetric** (default, one "window size" field = the total span, split evenly before/after the event) or untick it for independent Before/After fields — e.g. 10s before an event, 20s after.
- `PhysicsLibrary`'s `get_zscore_slice()`/`compute_fft_slice()` gained matching `pre`/`post` parameters (see PhysicsLibrary CHANGELOG).
- Fixed PETH silently ignoring the window setting entirely — it hardcoded a 30s window and hardcoded plot axis ranges regardless of what was configured; it now honours the same Window setting FFT already did.

**Fixes: resize smoothness (PyQtGraph engine)**
- Fixed the PyQtGraph plot flashing to fill the whole widget for one frame on every resize and on any redraw (e.g. Edit Attributes) — its margin-measurement pass briefly zeroed out margins to probe axis geometry; repaints are now frozen for that probe so the intermediate state is never shown.
- Resize is now smooth and live instead of snapping once after the drag settles: a cheap per-tick margin/font update (reusing the last-measured axis size, no flash-prone probe) runs on every resize event, with the more expensive accurate re-measurement + full replot debounced to once after the drag ends.
- Matplotlib engine's title/axis-label/legend fonts now also rescale live during resize — previously only the plot area itself resized live; text stayed a fixed size until the next full redraw.
- Fixed a genuine pyqtgraph bug where `LegendItem.setLabelTextSize()` never actually re-rendered the legend text (it only updated internal state) — legend font size now visibly updates by forcing each label's `setText()`.

**Fixes: other**
- Fixed **Reload** just re-opening the same file picker as **Open** — it now re-reads the currently loaded folder/file from disk in place instead. TDT/Oxysoft skip the dialog entirely; Generic (Excel/CSV/TSV) re-parses the same file and reopens the table/column picker (sub-tables or columns may have changed since last load), skipping only the file-choice step. Falls back to Open when nothing's loaded yet.

**Cleanup**
- Removed the legacy tkinter GUI (`PhysicsAnalysisGUI.py`) — the PyQt6 version (`run_qt.py`) is now the only supported app. Full tkinter history remains in git log for reference.
- Split `pg_engine.py`'s mouse-interaction code (hover snap, click dispatch, right-click marker menu) into a new `pg_interaction.py`, mirroring the matplotlib engine's existing `plotting.py`/`interaction.py` split.
- Added the missing `pyqtgraph` dependency to `requirements.txt`/`pyproject.toml` — it was already required by the GPU engine (added in v2.1.0) but never listed.

---

## v2.1.0
**New: PyQtGraph (GPU) plot engine**
- The PyQt6 main plot can now render with either matplotlib (CPU) or PyQtGraph (GPU-accelerated), switchable anytime in the new **Options** dialog. Covers pan/zoom, hover snap + coordinate readout, event markers, and rectangle-select zoom. FFT/PETH/Curve Fit/PT2 windows always stay matplotlib-rendered — they open fresh, small figures each time and aren't the performance bottleneck.
- Edit Attributes (title/label text, font sizes, bold toggle, legend show/hide + rename) now applies identically to both engines via the shared `plot_attrs` state.
- Font sizes and plot margins scale to the actual on-screen widget size (shared formula/reference for both engines), so the two engines render at matching proportions and stay correct across window resizes instead of each interpreting a literal point size through a different renderer.
- New "Bold" checkbox in Edit Attributes for title/axis label weight.

**New: Options dialog**
- Default folder for all Open dialogs (now defaults to Desktop instead of the process's working directory, which could land on `System32`).
- Main-plot render decimation: traces are min/max-decimated to the visible x-range on every pan/zoom, independent of dataset size, with a configurable max-points-per-trace setting. Fixes large TDT/Oxysoft recordings making panning unusably slow.
- Background-thread loading for TDT/Oxysoft files (on by default) — keeps the UI responsive during large loads instead of freezing until they finish. Guarded against starting a second load while one is already in flight.

**Bug fixes**
- Fixed a genuine pyqtgraph bug: `setClipToView(True)` crashes `PlotDataItem._getDisplayDataset()` on every redraw (reproduces on a bare `PlotWidget`, all recent pyqtgraph versions, not caused by anything project-specific) — removed it; `setDownsampling` alone still bounds render cost.
- Fixed `PlotItem.setTitle()` hardcoding its title row to a fixed 30px height regardless of font size, which made larger titles overlap the plot area — row height and plot margins now account for the actual title size.
- Fixed the PyQtGraph plot area rendering at a different size than matplotlib's for the same widget size — matplotlib's subplot margins already include room for tick/axis labels, but PyQtGraph's margins are in addition to what its own axes auto-reserve; margins are now measured in two passes so the two engines' actual data areas match.
- Fixed zoom/pan resetting on every redraw (grid toggle, marker add/edit, attribute changes) in both engines — the view now only resets on an actual new dataset or an engine switch, not a same-data redraw.
- Fixed grid toggle visibly flashing/snapping in the PyQtGraph engine — it no longer routes through a full clear+rebuild; it's now a direct `showGrid()`/`ax.grid()` call with nothing else touched.
- Fixed a silent hard crash (process exits with no traceback) when a background load finished: cleanup was dropping the last Python reference to a `QThread` before it had actually finished, which Qt treats as a fatal error rather than a catchable exception.

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
