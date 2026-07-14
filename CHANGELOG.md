# Changelog — Physics Analysis GUI

---

## v2.6.0
**New: Splice Recording**
- New left-side icon sidebar (📍 Add Marker, ✂ Splice, 💾 Save Changes, ↺ Undo All Changes), collapsible via a small arrow handle — tools that change how the data looks/is analyzed without ever touching the original raw data, moved out of the top toolbar rather than duplicated.
- **Splice Recording**: pick a mode (Keep only this range / Cut out this range — removes an artifact from the middle and stitches the remainder together, shifting everything after the cut so the timeline stays contiguous) then click two points directly on the plot to mark the range, same click-to-anchor pattern as Curve Fit. No typed start/end numbers. Works on a copy — the original recording is never mutated, restorable at any time via the same icon (becomes "Restore Full Recording").
- The active splice can now be saved (`JSON saves/splice.json`, alongside the markers sidecar) via Save Changes, and is automatically reapplied the next time the folder is opened — previously it was memory-only and lost on restart/reload.
- "Undo All Changes": discards marker/splice changes (including previously-saved ones) with a confirmation dialog, clears the `JSON saves/` folder's contents (not the folder itself), and re-reads the file fresh.
- Architecture: the actual splice computation (trim, cut-and-stitch, timeline-shifting, marker filtering) lives in PhysicsLibrary 1.7.0's new `splice_keep_inside`/`splice_cut_out` — this module is GUI orchestration only (dialogs, click capture, sidecar I/O), matching how Event PETH/Peak Finder already split GUI vs. computation.

**Event PETH / Peak Finder improvements**
- Fixed the results heatmap's colorbar stacking a new one on every row-order change or event switch instead of replacing the old one (needed to remove it before, not after, clearing the axes — order mattered because it restores the axes' pre-colorbar geometry on removal).
- Event PETH no longer requires closing and reopening to look at a different event — an Event dropdown right in the results dialog switches and recomputes in place. Also gained its own local pre/post window fields (defaulting to the global Window setting) with a Recalculate button, same pattern Curve Fit already used, instead of only ever using the global window.
- Peak Finder reworked: default scope now scans every event type at once and shows a summary (occurrences/hit-rate/avg z-score per type, sorted so likely-real events float to the top) with nothing added to the plot until you choose to — instead of requiring you to already know which single event to check. Both Event PETH's and Peak Finder's event lists now pull from every event TDT actually detected in the recording, not just what's already been added to the plot as a marker.

**Fixed**
- Grid toggle (Edit Attributes → Show Grid) didn't actually toggle — `ax.grid(False, color=..., linestyle=...)` is a matplotlib gotcha where passing style kwargs alongside `False` makes it force the grid back **on** regardless. Only pass those kwargs when actually turning it on.
- `RectangleSelector` (drag-to-zoom) visibly flashed while resizing the selection — the hover-tracker dot was doing its own independent canvas blit on every mouse-move tick during the drag, racing `RectangleSelector`'s own blit for the same region. Suppressed the hover tracker for the duration of a rect-select drag.
- The 📍 Add Marker icon lost its pin glyph and became clipped/garbled text ("Placing 'Marker'…" in a 44×44 square) while placing, and never got its icon back afterward — `toggle_marker_mode()` was overwriting the button's text directly, a leftover from when it was a full-width text button. Now reflects state via tooltip + background color only, never touches the icon's text.
- Oxysoft loader: a file whose Legend block doesn't match the expected `O2Hb`/`HHb` column format failed with a cryptic `not enough values to unpack` instead of saying what's actually wrong (PhysicsLibrary 1.7.0).

---

## v2.5.0
**New: Event PETH (GuPPy-style, stacked heatmap + trial average)**
- **Advanced Analysis ▾ → Event PETH**: pick an event/marker name and Z-score every occurrence of it against its own pre-event baseline, stacked as one row per trial in a heatmap (colorbar included) with the trial-averaged trace ± SEM plotted below — lets you actually see whether a response is consistent across trials, not just look at one clicked moment. Row order is sortable (trial order vs. peak amplitude) without recomputing. Distinct from the existing single-click PETH, which stays as-is.
- Event names are pulled from every event TDT actually detected in the recording (not just what's already been added to the plot), so this works on a freshly loaded file with zero markers placed yet.

**New: Find Significant Peaks**
- **Advanced Analysis ▾ → Find Significant Peaks…**: auto-detects statistically significant transients straight from the signal instead of trusting that event markers line up with real neural activity. Four scopes: scan every event type at once (a summary table — occurrences, hit rate, average z-score per event type, sorted so likely-real events float to the top, nothing added to the plot until you choose to), all occurrences of one chosen event type, one specific event instance, or a blind whole-recording scan unrelated to any marker. Event-scoped modes report per-occurrence found/latency/z-score. Found peaks are added as `AutoPeak`/`AutoTrough` markers, which work immediately with Event PETH.
- New PhysicsLibrary 1.6.0 functions backing both features: `compute_event_zscore_peth`, `find_significant_peaks`, `find_peak_near_events`.

**Fixed**
- Toasts were a separate top-level window pinned to a screen position instead of a child of the main window — didn't move/stack with it. Now a real child widget.
- Double-click-triggered analysis (FFT/PETH/Curve Fit hint) occasionally needed an extra click — matplotlib's own double-click detection could desync from `RectangleSelector`'s press handler seeing the same clicks. Replaced with a manual time+position double-click detector.
- Options dialog settings (including the default folder) only lived in memory and reset every restart — now persisted to `~/.physicsanalysis/settings.json`.
- Marker sidecar JSON was saved as a sibling file next to the raw data folder instead of inside it — now saved to a `JSON saves/` subfolder within the loaded folder (old sidecar locations still load as a fallback).
- A TDT epoc store with a level/buffered logic signal already "high" the instant recording started got a spurious onset marker at exactly t=0 (TDT's synthetic starting-state entry, not a real event) — now filtered out, mirroring the existing `offset == inf` guard for the opposite edge case.

**New: double-click to rename plot text; light/dark mode; Grid moved into Edit Attributes**
- Double-click the title, X/Y axis label, or a legend entry directly on the plot to retype just that one — updates the same values the Edit Attributes dialog shows.
- New Options → Appearance → Theme (Light/Dark): a Qt palette swap for every dialog plus matching matplotlib figure/axes/legend/grid colors, persisted like other settings. Applies to the empty canvas at startup too, not just after a file loads.
- The Grid toggle moved out of the toolbar into Edit Attributes ("Show Grid," next to Bold) — no longer a standalone toolbar checkbox.
- Toolbar reorganized: Advanced Analysis ▾, the Analysis mode combo, and the Window button now sit together in one section.

---

## v2.4.1
**Fixed: Curve Fit results invisible under Windows dark mode**
- The results box only set `background-color: white`, not the text color — on a system with Windows dark mode enabled, Qt6's automatic dark palette rendered the label text white as well, so fitted parameters were computed and displayed on the plot correctly but unreadable (white on white) above it. Text color is now explicitly pinned to black.

---

## v2.4.0
**New: text field study analysis**
- New **Text Field Study ▾** toolbar menu (its own dropdown, not mixed into the marker controls or the main Open menu — a study is a completely separate workflow from the main signal plot): **Open Study Folder**, **View Results**, **Statistical Validation**.
- **Open Study Folder**: pick a folder of one-JSON-file-per-subject data (any study, not a fixed schema — see PhysicsLibrary 1.5.0's `run_field_study_pipeline`). Every file matching the folder's naming pattern is loaded into one DataFrame, one row per subject.
- Field comparisons are set up inline, right after picking the folder: a dialog shows the actual field names found in that folder's own files (via `peek_fields`), and you just pick pairs of fields to compare directly (e.g. "does this answer track that one") — add as many comparisons as you want, plus an optional "how much did the response change between these two fields" measurement and a configurable low-word-count quality-flag threshold. No grouping concept to learn — pick two fields, name the comparison, done. Saved locally and pre-fills next time you open a folder.
- **View Results** (reopens without rerunning): a table of the analysis columns — word counts, data-quality flags, delta magnitude, paired similarity, a permutation-test p-value/effect size per pair, and a word-count-confound check — plus full-DataFrame CSV export.
- The actual field configuration for a given study (which fields, which pairs) is study-specific and lives in a local config file outside this repo (`~/.physicsanalysis/`), not in source — nothing about what any particular study measures ships with the app.
- New `ctx.study_data`/`ctx.study_data_path`/`ctx.study_data_config` — kept separate from `ctx.cache`, whose x/y/markers shape every plotting/marker/analysis module elsewhere assumes; a DataFrame doesn't fit that.
- New dependency: pandas.

**New: statistical validation for text field studies**
- **Statistical Validation** (in the same menu, and directly in the results dialog once a study has at least one comparison): re-runs the pipeline through PhysicsLibrary's `run_validation_pipeline` and shows one row per field pair — permutation-test p-value with Benjamini-Hochberg FDR correction across every pair, Cohen's d effect size, a word-count-controlled OLS regression coefficient/p-value per field, a bootstrap 95% confidence interval on the mean similarity, and leave-one-out sensitivity flags, plus a plain-language "Verdict" column (a quick-glance read, not a substitute for the actual numbers). Full CSV export.
- Fixed the results table forcing every column to equal width regardless of content (`Stretch` resize mode) — with this many columns, long header names were getting squeezed into columns far too narrow to hold them, reading as overlapping/garbled text. Columns now size to their own content, with horizontal scrolling for the rest.
- Fixed PhysicsLibrary's word-count confound check crashing outright (`pearsonr` needs at least 2 subjects) instead of returning `NaN` for a statistic that's genuinely undefined with too little data — same fix applied to Cohen's d, the word-count regression, and leave-one-out for the same reason.
- Clarified the whole workflow: the menu is numbered ("1. Open Study Folder…", "2. Statistical Validation") with tooltips explaining what each step does and that results already open automatically after step 1; both dialogs now explain in plain language what the similarity score and the statistics actually mean, not just their column names.

**Fixed: every Export/Save dialog opening to System32**
- None of the app's Export/Save dialogs (View, plot images, CSVs across curve fit, FFT, event intervals, and both new text field study dialogs) passed a starting directory to `QFileDialog.getSaveFileName`, so it fell back to the process's working directory — which on Windows can resolve to `System32` depending on how the app was launched. Every one of them now opens to the last folder you browsed to (or Desktop by default), matching how the Open dialogs already behaved.

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
