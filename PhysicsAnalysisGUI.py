import sys
sys.path.insert(0, r'C:\Users\zakgm\anaconda3\Lib\site-packages')

import tkinter as tk
from tkinter import filedialog
import os
import json
import PhysicsLibrary as pl
import matplotlib as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import RectangleSelector
import datetime
import numpy as np


#####################
# ---  Globals  --- #
#####################

show_corrected   = True
selected_path    = None
cache            = None
is_dragging      = False
press_x, press_y = None, None
marker_mode      = False   # True when "Add Marker" is active
tracker_dots = []
connecting_line = None
slope_mode_active = False
slope_clicks = []  # Temporary storage to catch your 2 clicks for slope math
active_snap_line  = None
_hover_bg        = None   # blitting background cache
_hover_bg_timer  = None   # debounce handle for background recapture
show_grid        = True

# Persisted plot customisations — survive redraws
_PHI = 1.6180339887   # golden ratio

def _fig_font_sizes(fig):
    """
    Return (title_fs, label_fs, legend_fs) using the golden ratio.

    Title scales linearly with the figure diagonal.
    Each tier down is title / φ, then title / φ².
    Anchor: 8×4 in diagonal (≈ 8.94 in) → title ≈ 24 pt.
    Halved when the figure contains multiple subplots.
    """
    diag     = (fig.get_figwidth() ** 2 + fig.get_figheight() ** 2) ** 0.5
    title_fs = max(8, round(diag * (24 / ((8**2 + 4**2) ** 0.5))))
    label_fs = max(6, round(title_fs / _PHI))
    leg_fs   = max(5, round(label_fs / _PHI))
    if len(fig.axes) > 1:
        title_fs = max(6, title_fs // 2)
        label_fs = max(5, label_fs // 2)
        leg_fs   = max(4, leg_fs   // 2)
    return title_fs, label_fs, leg_fs


plot_attrs = {
    "title":     None,   # str or None = use auto title
    "xlabel":    None,
    "ylabel":    None,
    "title_fs":  24,
    "xlabel_fs": 16,
    "ylabel_fs": 16,
    "leg_fs":    14,
    "leg_loc":   "upper left",
    "leg_entries": None,   # list of (label, visible) or None = show all
}

root = tk.Tk()
root.title("Physics Analysis")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def show_window_toast(message, duration=2500):
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    tk.Label(toast, text=message, bg="#333333", fg="white",
             padx=20, pady=10, font=("Helvetica", 10, "bold")).pack()
    root.update_idletasks()
    toast.update_idletasks()
    root_x, root_y = root.winfo_x(), root.winfo_y()
    root_w, root_h = root.winfo_width(), root.winfo_height()
    t_w,    t_h    = toast.winfo_width(), toast.winfo_height()
    toast.geometry(f"+{root_x + root_w - t_w - 20}+{root_y + root_h - t_h - 20}")
    toast.after(duration, toast.destroy)

def show_error(msg):
    tk.messagebox.showerror("Physics Analysis Error", f"❌ {msg}")

def show_success(msg):
    show_window_toast(f"✅ {msg}")


# ---------------------------------------------------------------------------
# Marker sidecar  (JSON file next to the data file)
# ---------------------------------------------------------------------------

def _sidecar_path():
    """Return the .markers.json path for the currently loaded file."""
    if selected_path and os.path.isfile(selected_path):
        base = os.path.splitext(selected_path)[0]
        return base + ".markers.json"
    elif selected_path and os.path.isdir(selected_path):
        return os.path.join(selected_path, ".markers.json")
    return None

def save_markers():
    """Save cache['markers'] to a JSON sidecar next to the data file."""
    if cache is None:
        show_error("No data loaded.")
        return
    path = _sidecar_path()
    if path is None:
        show_error("Cannot determine save location.")
        return
    try:
        with open(path, 'w') as f:
            json.dump(cache['markers'], f, indent=2, default=float)
        show_success("Markers saved")
    except Exception as e:
        show_error(f"Save failed: {str(e)}")

def load_markers_from_sidecar():
    """Load markers from sidecar if it exists, merge into cache."""
    if cache is None:
        return
    path = _sidecar_path()
    if path and os.path.isfile(path):
        try:
            with open(path, 'r') as f:
                markers = json.load(f)
            cache['markers'] = markers
            simple_plot()
            show_success(f"Markers restored ({len(markers)})")
        except Exception as e:
            show_error(f"Could not load markers: {str(e)}")


# ---------------------------------------------------------------------------
# Marker mode
# ---------------------------------------------------------------------------

def toggle_marker_mode():
    """Toggle add-marker mode on/off."""
    global marker_mode
    marker_mode = not marker_mode
    if marker_mode:
        btn_add_marker.config(bg="#FF9800", relief="sunken",
                              text="🖊 Adding Marker  (click plot)")
        rect_selector.set_active(False)   # disable zoom while placing markers
    else:
        btn_add_marker.config(bg="#e1e1e1", relief="raised",
                              text="🖊 Add Marker")
        rect_selector.set_active(True)


def _place_marker(t):
    """Ask for a name and add a marker at time t."""
    win = tk.Toplevel(root)
    win.title("New Marker")
    win.resizable(False, False)
    win.grab_set()

    tk.Label(win, text="Marker name:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
    e_name = tk.Entry(win, width=25)
    e_name.insert(0, "Marker")
    e_name.grid(row=0, column=1, padx=10, pady=10)
    e_name.focus_set()
    e_name.select_range(0, tk.END)

    # Colour picker
    _MARKER_COLORS = ["green", "red", "blue", "orange", "purple", "black"]
    tk.Label(win, text="Colour:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
    color_var = tk.StringVar(value="green")
    color_frame = tk.Frame(win)
    color_frame.grid(row=1, column=1, padx=10, pady=5, sticky="w")
    for col in _MARKER_COLORS:
        tk.Radiobutton(color_frame, text=col, variable=color_var,
                       value=col, fg=col).pack(side="left")

    # Font size
    tk.Label(win, text="Font size:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
    e_fontsize = tk.Entry(win, width=6)
    e_fontsize.insert(0, "8")
    e_fontsize.grid(row=2, column=1, padx=10, pady=5, sticky="w")

    def _confirm():
        label = e_name.get().strip() or "Marker"
        color = color_var.get()
        try:
            fontsize = max(4, int(e_fontsize.get()))
        except ValueError:
            fontsize = 8
        cache['markers'].append({"time": t, "label": label, "color": color, "fontsize": fontsize})
        simple_plot()
        win.destroy()

    tk.Button(win, text="Add", command=_confirm,
              bg="#4CAF50", fg="white",
              font=('Helvetica', 9, 'bold'),
              padx=20).grid(row=3, column=0, columnspan=2, pady=10)

    win.bind("<Return>", lambda e: _confirm())


def _find_nearest_marker(t, tol_s=2.0):
    """Return the index of the marker closest to t within tol_s, or None."""
    if cache is None or not cache['markers']:
        return None
    dists = [abs(m['time'] - t) for m in cache['markers']]
    idx   = int(np.argmin(dists))
    return idx if dists[idx] <= tol_s else None


def _right_click_marker_menu(event):
    """Show rename/delete context menu if right-click is near a marker."""
    if cache is None or event.xdata is None:
        return
    idx = _find_nearest_marker(event.xdata)
    if idx is None:
        return

    marker = cache['markers'][idx]
    menu   = tk.Menu(root, tearoff=0)

    def _rename():
        win = tk.Toplevel(root)
        win.title("Edit Marker")
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text="Name:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        e = tk.Entry(win, width=25)
        e.insert(0, marker['label'])
        e.grid(row=0, column=1, padx=10, pady=10)
        e.focus_set()
        e.select_range(0, tk.END)
        _MARKER_COLORS = ["green", "red", "blue", "orange", "purple", "black"]
        tk.Label(win, text="Colour:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        color_var = tk.StringVar(value=marker.get('color', 'green'))
        color_frame = tk.Frame(win)
        color_frame.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        for col in _MARKER_COLORS:
            tk.Radiobutton(color_frame, text=col, variable=color_var,
                           value=col, fg=col).pack(side="left")
        tk.Label(win, text="Font size:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        e_fs = tk.Entry(win, width=6)
        e_fs.insert(0, str(marker.get('fontsize', 8)))
        e_fs.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        def _ok():
            marker['label'] = e.get().strip() or marker['label']
            marker['color'] = color_var.get()
            try:
                marker['fontsize'] = max(4, int(e_fs.get()))
            except ValueError:
                pass
            simple_plot()
            win.destroy()
        tk.Button(win, text="OK", command=_ok,
                  bg="#4CAF50", fg="white",
                  font=('Helvetica', 9, 'bold'),
                  padx=20).grid(row=3, column=0, columnspan=2, pady=10)
        win.bind("<Return>", lambda ev: _ok())

    def _delete():
        cache['markers'].pop(idx)
        simple_plot()

    menu.add_command(label=f"✏️  Rename  '{marker['label']}'", command=_rename)
    menu.add_command(label=f"🗑  Delete  '{marker['label']}'", command=_delete)
    menu.tk_popup(event.guiEvent.x_root, event.guiEvent.y_root)


# ---------------------------------------------------------------------------
# File / Folder selection
# ---------------------------------------------------------------------------

def open_folder():
    global selected_path
    path = filedialog.askdirectory(title="Open Data Folder")
    if not path:
        return
    selected_path = path
    name = os.path.basename(path)
    root.title(f"Physics Analysis — {name}")
    show_success(f"Folder: {name}")
    load_data_action()

def open_file():
    global selected_path
    path = filedialog.askopenfilename(
        title="Open Data File",
        filetypes=[
            ("All supported", "*.txt *.csv *.tsv"),
            ("Text files",    "*.txt"),
            ("CSV files",     "*.csv"),
            ("All files",     "*.*"),
        ]
    )
    if not path:
        return
    selected_path = path
    name = os.path.basename(path)
    root.title(f"Physics Analysis — {name}")
    show_success(f"File: {name}")
    load_data_action()


# ---------------------------------------------------------------------------
# Generic file loader (any tabular format)
# ---------------------------------------------------------------------------

def launch_generic_file_loader():
    """Open any tabular file, detect sub-tables, let user pick columns and plot."""
    import PhysicsLibrary.file_parser_generic as _gen

    path = filedialog.askopenfilename(
        title="Open Any Tabular File",
        filetypes=[
            ("All tabular", "*.xlsx *.xls *.csv *.tsv *.txt *.dat"),
            ("Excel",       "*.xlsx *.xls"),
            ("CSV / TSV",   "*.csv *.tsv"),
            ("Text / data", "*.txt *.dat"),
            ("All files",   "*.*"),
        ]
    )
    if not path:
        return

    try:
        tables = _gen.load_any_file(path)
    except Exception as e:
        show_error(f"Could not parse file:\n{e}")
        return

    if not tables:
        show_error("No usable tabular data found in this file.")
        return

    # ── Picker dialog ──────────────────────────────────────────────────────
    dlg = tk.Toplevel(root)
    dlg.title(f"Generic Loader — {os.path.basename(path)}")
    dlg.geometry("780x540")
    dlg.resizable(True, True)

    # Left column: table list
    left = tk.Frame(dlg, width=200)
    left.pack(side="left", fill="y", padx=(10, 4), pady=10)
    left.pack_propagate(False)

    tk.Label(left, text="Detected tables:", font=('Helvetica', 9, 'bold')).pack(anchor="w")
    tbl_lb = tk.Listbox(left, selectmode="single", font=("Consolas", 8))
    tbl_lb.pack(fill="both", expand=True)
    for t in tables:
        tbl_lb.insert("end", t.name)

    # Right column: column pickers + preview
    right = tk.Frame(dlg)
    right.pack(side="left", fill="both", expand=True, padx=(4, 10), pady=10)

    # X column
    xrow = tk.Frame(right)
    xrow.pack(fill="x", pady=(0, 4))
    tk.Label(xrow, text="X:", font=('Helvetica', 9, 'bold'), width=12, anchor="w").pack(side="left")
    x_var = tk.StringVar()
    x_menu = tk.OptionMenu(xrow, x_var, "")
    x_menu.config(width=30)
    x_menu.pack(side="left")

    # Y columns (multi-select)
    yrow = tk.Frame(right)
    yrow.pack(fill="x", pady=(0, 4))
    tk.Label(yrow, text="Y (multi-select):", font=('Helvetica', 9, 'bold'), width=12, anchor="w").pack(side="left")
    y_lb = tk.Listbox(yrow, selectmode="extended", height=6, font=("Consolas", 8), width=34)
    y_lb.pack(side="left", fill="x", expand=True)
    y_scroll = tk.Scrollbar(yrow, orient="vertical", command=y_lb.yview)
    y_scroll.pack(side="left", fill="y")
    y_lb.config(yscrollcommand=y_scroll.set)

    # Error-bar column (optional)
    erow = tk.Frame(right)
    erow.pack(fill="x", pady=(0, 8))
    tk.Label(erow, text="Error bars (opt):", font=('Helvetica', 9, 'bold'), width=12, anchor="w").pack(side="left")
    err_var = tk.StringVar(value="— none —")
    err_menu = tk.OptionMenu(erow, err_var, "— none —")
    err_menu.config(width=30)
    err_menu.pack(side="left")

    # Data preview
    tk.Label(right, text="Preview:", font=('Helvetica', 9, 'bold')).pack(anchor="w")
    preview = tk.Text(right, height=8, font=("Consolas", 8), state="disabled",
                      bg="#f8f8f8", relief="groove")
    preview.pack(fill="both", expand=True)

    current_table: list = [None]

    def _refresh_preview(t: "_gen.GenericTable"):
        preview.config(state="normal")
        preview.delete("1.0", "end")
        preview.insert("end", "\t".join(t.headers) + "\n")
        preview.insert("end", "─" * 60 + "\n")
        for ri in range(min(8, t.data.shape[0])):
            cells = []
            for v in t.data[ri]:
                cells.append(f"{v:.5g}" if not np.isnan(v) else "—")
            preview.insert("end", "\t".join(cells) + "\n")
        preview.config(state="disabled")

    def _on_table_select(event=None):
        sel = tbl_lb.curselection()
        if not sel:
            return
        t = tables[sel[0]]
        current_table[0] = t

        # Rebuild X menu
        x_menu['menu'].delete(0, 'end')
        for h in t.headers:
            x_menu['menu'].add_command(label=h, command=lambda h=h: x_var.set(h))
        x_var.set(t.headers[0] if t.headers else "")

        # Rebuild Y listbox
        y_lb.delete(0, 'end')
        for h in t.headers:
            y_lb.insert('end', h)
        for i in range(1, len(t.headers)):       # default: all columns except X
            y_lb.selection_set(i)

        # Rebuild error bar menu
        err_menu['menu'].delete(0, 'end')
        err_menu['menu'].add_command(label="— none —", command=lambda: err_var.set("— none —"))
        for h in t.headers:
            err_menu['menu'].add_command(label=h, command=lambda h=h: err_var.set(h))
        err_var.set("— none —")

        _refresh_preview(t)

    tbl_lb.bind("<<ListboxSelect>>", _on_table_select)
    tbl_lb.selection_set(0)
    _on_table_select()

    def _do_load():
        global cache
        t = current_table[0]
        if t is None:
            return

        y_indices = list(y_lb.curselection())
        if not y_indices:
            show_error("Select at least one Y column.")
            return

        try:
            x_idx = t.headers.index(x_var.get())
        except ValueError:
            x_idx = 0

        x_data = t.data[:, x_idx]
        # Remove rows where X is NaN
        valid = ~np.isnan(x_data)
        x_data = x_data[valid]

        y_columns = {}
        for yi in y_indices:
            col_name = t.headers[yi]
            y_col    = t.data[valid, yi]
            y_columns[col_name] = y_col

        # Estimate sample rate from X spacing
        if len(x_data) > 1:
            fs = float(1.0 / np.median(np.diff(x_data)))
        else:
            fs = 1.0

        cache = {
            "source":    "Generic",
            "x":         x_data,
            "y_columns": y_columns,
            "x_label":   x_var.get(),
            "store":     t.name,
            "fs":        fs,
            "markers":   [],
        }

        dlg.destroy()
        simple_plot()
        show_success(f"Loaded: {t.name}")

    # Bottom buttons
    brow = tk.Frame(dlg)
    brow.pack(side="bottom", fill="x", padx=10, pady=8)
    tk.Button(brow, text="▶  Load to Main Plot", command=_do_load,
              bg="#4CAF50", fg="white",
              font=('Helvetica', 10, 'bold'), padx=20).pack(side="left", padx=4)
    tk.Button(brow, text="Close", command=dlg.destroy,
              bg="#e1e1e1", font=('Helvetica', 10, 'bold'), padx=20).pack(side="left", padx=4)


# ---------------------------------------------------------------------------
# Terranova / Prospa .pt2 EFNMR image viewer
# ---------------------------------------------------------------------------

def launch_pt2_viewer():
    """Open and display a Terranova EFNMR .pt2 2D image in a new window."""
    path = filedialog.askopenfilename(
        title="Open EFNMR / MRI Image (.pt2)",
        filetypes=[("Prospa 2D image", "*.pt2"), ("All files", "*.*")]
    )
    if not path:
        return

    try:
        img = pl.load_pt2(path)
    except Exception as e:
        show_error(str(e))
        return

    win = tk.Toplevel(root)
    win.title(f"EFNMR Image — {os.path.basename(path)}")
    win.resizable(True, True)

    # ── Toolbar ────────────────────────────────────────────────────────────
    tb = tk.Frame(win, bg="#e1e1e1")
    tb.pack(side="top", fill="x", padx=4, pady=4)

    tk.Label(tb, text="Colormap:", bg="#e1e1e1").pack(side="left", padx=(4, 2))
    cmap_var = tk.StringVar(value="viridis")
    tk.OptionMenu(tb, cmap_var, "gray", "hot", "viridis", "plasma", "bone", "inferno").pack(side="left")

    tk.Label(tb, text="Title:", bg="#e1e1e1").pack(side="left", padx=(12, 2))
    default_title = os.path.splitext(os.path.basename(path))[0]
    title_var = tk.StringVar(value=default_title)
    title_entry = tk.Entry(tb, textvariable=title_var, width=28)
    title_entry.pack(side="left")

    def _update_title(*_):
        ax2.set_title(title_var.get(), fontsize=_tfs_2, fontweight='bold')
        canvas2.draw_idle()

    title_var.trace_add("write", _update_title)

    # ── Figure ─────────────────────────────────────────────────────────────
    fig2 = Figure(figsize=(5.5, 5.5), tight_layout=True)
    ax2  = fig2.add_subplot(111)
    im   = ax2.imshow(img, cmap="viridis", origin="lower", aspect="equal")
    cbar = fig2.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
    _tfs_2, _lfs_2, _ = _fig_font_sizes(fig2)
    cbar.set_label("Signal intensity (a.u.)", fontsize=_lfs_2)
    ax2.set_title(os.path.splitext(os.path.basename(path))[0], fontsize=_tfs_2, fontweight='bold')
    ax2.set_xlabel("Z (pixels)", fontsize=_lfs_2)
    ax2.set_ylabel("Y (pixels)", fontsize=_lfs_2)

    canvas2 = FigureCanvasTkAgg(fig2, master=win)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=(0, 4))

    def _update_cmap(*_):
        im.set_cmap(cmap_var.get())
        canvas2.draw_idle()

    cmap_var.trace_add("write", _update_cmap)

    def _export():
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        name = f"{os.path.splitext(os.path.basename(path))[0]}_{ts}.png"
        dst  = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
            initialfile=name, title="Export Image"
        )
        if dst:
            fig2.savefig(dst, dpi=300, bbox_inches='tight')
            show_window_toast(f"✅ Exported: {os.path.basename(dst)}")

    tk.Button(tb, text="🖼 Export", command=_export,
              bg="#e1e1e1", font=('Helvetica', 9)).pack(side="right", padx=4)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data_action():
    global cache
    if selected_path is None:
        show_error("Please select a file or folder first!")
        return
    try:
        if os.path.isfile(selected_path):
            _load_single_file(selected_path)
        else:
            _load_folder(selected_path)

        # Reset persisted attributes for the new file
        plot_attrs.update({
            "title": None, "xlabel": None, "ylabel": None,
            "title_fs": 24, "xlabel_fs": 16, "ylabel_fs": 16,
            "leg_fs": 14, "leg_loc": "upper left", "leg_entries": None,
        })

        # Auto-restore markers from sidecar if it exists
        sidecar = _sidecar_path()
        if sidecar and os.path.isfile(sidecar):
            try:
                with open(sidecar, 'r') as f:
                    cache['markers'] = json.load(f)
                show_window_toast(f"📍 Markers restored ({len(cache['markers'])})")
            except Exception:
                pass

        msg = f"Loaded {cache['store']} ({cache['fs']:.1f} Hz)"
        show_success(msg)
        simple_plot()
    except Exception as e:
        show_error(f"Processing Failed: {str(e)}")

def _load_folder(folder_path):
    global cache
    fmt = pl.detect_format(folder_path)
    if fmt == pl.DataFormat.TDT:
        cache = pl.process_tdt_folder(folder_path)
        cache['source'] = 'TDT'
    else:
        raise ValueError(
            "Unrecognised folder format.\n"
            "Expected a TDT tank (.Tbk/.tev/…).\n"
            "For Oxysoft files use 'Open File' instead."
        )

def _load_single_file(file_path):
    global cache
    fmt = pl.detect_format_file(file_path)
    if fmt == pl.DataFormat.OXYSOFT:
        dataset = pl.load_dataset_file(file_path)
        n_ch    = dataset.metadata.get("n_channels", dataset.num_channels // 2)
        x       = np.arange(dataset.num_samples) / dataset.sample_rate
        o2hb    = dataset.signals[:n_ch]
        hhb     = dataset.signals[n_ch:]
        thb = o2hb + hhb
        cache = {
            "source":         "Oxysoft",
            "x":              x,
            "o2hb":           o2hb,
            "hhb":            hhb,
            "thb":            thb,
            "fs":             dataset.sample_rate,
            "store":          os.path.splitext(os.path.basename(file_path))[0],
            "fit_factor_mean": dataset.metadata.get("fit_factor_mean", None),
            "markers": [
                {"time":  ev["sample"] / dataset.sample_rate,
                 "label": ev["label"],
                 "color": "black"}
                for ev in dataset.events
            ],
        }
    else:
        raise ValueError(
            f"Unrecognised file format: {os.path.basename(file_path)}\n"
            "Currently supported: Oxysoft .txt export."
        )


# ---------------------------------------------------------------------------
# Plot interaction
# ---------------------------------------------------------------------------

def on_select(eclick, erelease):
    # Ignore double-clicks and any drag smaller than 10 px in both axes
    if eclick.dblclick:
        return
    if abs(eclick.x - erelease.x) < 10 or abs(eclick.y - erelease.y) < 10:
        return
    x1, y1 = eclick.xdata,   eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    if None in [x1, x2, y1, y2]:
        return
    ax.set_xlim(min(x1, x2), max(x1, x2))
    ax.set_ylim(min(y1, y2), max(y1, y2))
    rect_selector.clear()
    _refresh_hover_bg()
    show_window_toast("Zoomed to Selection")

def on_press(event):
    global is_dragging, press_x, press_y, slope_clicks
    if event.inaxes != ax:
        return

    if 'slope_clicks' not in globals():
        slope_clicks = []

    # --- Double left-click: analysis (Runs for FFT & Z-Score PETH) ---
    # Moved to the VERY TOP of the checks so it intercepts cleanly before mode flags get in the way
    if event.dblclick and event.button == 1 and event.xdata is not None:
        if 'slope_clicks' in globals():
            slope_clicks.clear()
        analysis_type(event.xdata)
        return

    # --- Marker mode: left-click places, right-click context menu, nothing else ---
    if marker_mode:
        if event.button == 1 and not event.dblclick and event.xdata is not None:
            _place_marker(event.xdata)
        elif event.button == 3 and event.xdata is not None:
            _right_click_marker_menu(event)
        return

    # --- Right-click: context menu if near a marker, else pan ---
    if event.button == 3:
        if event.xdata is not None and _find_nearest_marker(event.xdata) is not None:
            _right_click_marker_menu(event)
        else:
            is_dragging      = True
            press_x, press_y = event.x, event.y
        return

    # --- Curve Fit Mode: record mouse-down pixel position, act on release ---
    if plot_type_var.get() == "Curve Fit":
        if event.button == 1 and not event.dblclick:
            press_x, press_y = event.x, event.y   # store for drag-detection in on_release
        return

    # --- Middle-click: reset zoom ---
    if event.button == 2:
        reset_zoom()

def on_motion(event):
    global press_x, press_y, tracker_dots, connecting_line, active_snap_line, _hover_bg

    # ── 1. Panning (right-click drag) ───────────────────────────────────────
    if is_dragging and event.inaxes == ax and event.x is not None:
        dx, dy = event.x - press_x, event.y - press_y
        press_x, press_y = event.x, event.y
        bbox    = ax.get_window_extent()
        xlim    = ax.get_xlim()
        ylim    = ax.get_ylim()
        shift_x = (dx / bbox.width)  * (xlim[1] - xlim[0])
        shift_y = (dy / bbox.height) * (ylim[1] - ylim[0])
        ax.set_xlim(xlim[0] - shift_x, xlim[1] - shift_x)
        ax.set_ylim(ylim[0] - shift_y, ylim[1] - shift_y)
        canvas.draw_idle()
        return   # skip hover while dragging

    # ── 2. Hover tracker (blit-based for speed) ─────────────────────────────
    hover_ready = (tracker_dots and connecting_line is not None and _hover_bg is not None)
    if not hover_ready or event.inaxes != ax or event.xdata is None:
        if hover_ready and not is_dragging:
            # cursor left axes — hide all overlays via blit
            canvas.restore_region(_hover_bg)
            for dot in tracker_dots:
                dot.set_visible(False)
                ax.draw_artist(dot)
            connecting_line.set_visible(False)
            ax.draw_artist(connecting_line)
            canvas.blit(fig.bbox)
            coord_var.set("X: -- | Y: -- | Pt: --")
        return

    target_x      = event.xdata
    y_values_at_x = []
    snap_x        = None
    closest_idx   = None
    best_y_dist   = float('inf')

    visible_lines = [
        l for l in ax.get_lines()
        if not str(l.get_label()).startswith('_')
        and len(l.get_xdata()) > 2
        and l.get_linewidth() >= 1.5
    ]

    for i, line in enumerate(visible_lines):
        x_data = np.asarray(line.get_xdata())
        y_data = np.asarray(line.get_ydata())
        if len(x_data) == 0:
            continue
        idx    = int(np.abs(x_data - target_x).argmin())
        snap_x = float(x_data[idx])
        snap_y = float(y_data[idx])
        closest_idx = idx
        y_values_at_x.append(snap_y)

        if i < len(tracker_dots):
            tracker_dots[i].set_data([snap_x], [snap_y])
            tracker_dots[i].set_color(line.get_color())
            tracker_dots[i].set_visible(True)

        y_dist = abs(snap_y - event.ydata)
        if y_dist < best_y_dist:
            best_y_dist      = y_dist
            active_snap_line = line

    for j in range(len(visible_lines), len(tracker_dots)):
        tracker_dots[j].set_visible(False)

    if len(y_values_at_x) >= 2 and snap_x is not None:
        connecting_line.set_data([snap_x, snap_x],
                                  [min(y_values_at_x), max(y_values_at_x)])
        connecting_line.set_visible(True)
    else:
        connecting_line.set_visible(False)

    # Blit: restore clean background, draw only the overlay artists
    canvas.restore_region(_hover_bg)
    for dot in tracker_dots:
        ax.draw_artist(dot)
    ax.draw_artist(connecting_line)
    canvas.blit(fig.bbox)

    # Update coordinate readout (cheap — just a tk StringVar)
    raw_xlbl  = ax.get_xlabel() or plot_attrs.get("xlabel") or "X"
    raw_ylbl  = ax.get_ylabel() or plot_attrs.get("ylabel") or "Y"
    clean_x   = str(raw_xlbl).strip() or "X"
    clean_y   = str(raw_ylbl).strip() or "Y"
    pt_str    = str(closest_idx) if closest_idx is not None else "--"
    coord_var.set(f"{clean_x}: {event.xdata:.2f} | {clean_y}: {event.ydata:.4f} | Pt: {pt_str}")

def _refresh_hover_bg():
    """Full redraw + recapture blit background. Call after view changes settle."""
    global _hover_bg, _hover_bg_timer
    _hover_bg_timer = None

    # Save current dot/connector positions, clear for clean draw
    saved_dots = [(list(d.get_xdata()), list(d.get_ydata())) for d in tracker_dots]
    saved_conn = (list(connecting_line.get_xdata()), list(connecting_line.get_ydata())) \
                 if connecting_line is not None else ([], [])
    for dot in tracker_dots:
        dot.set_data([], [])
    if connecting_line is not None:
        connecting_line.set_data([], [])

    _apply_plot_attrs()
    canvas.draw()
    _hover_bg = canvas.copy_from_bbox(fig.bbox)

    # Restore positions and re-blit so dots stay visible after zoom
    for dot, (xd, yd) in zip(tracker_dots, saved_dots):
        dot.set_data(xd, yd)
    if connecting_line is not None:
        connecting_line.set_data(*saved_conn)

    if any(len(d.get_xdata()) > 0 for d in tracker_dots):
        canvas.restore_region(_hover_bg)
        for dot in tracker_dots:
            ax.draw_artist(dot)
        if connecting_line is not None and len(connecting_line.get_xdata()) > 0:
            ax.draw_artist(connecting_line)
        canvas.blit(fig.bbox)

def _schedule_hover_bg_refresh(delay_ms=150):
    """Debounced background recapture — coalesces rapid scroll/zoom events."""
    global _hover_bg_timer
    if _hover_bg_timer is not None:
        root.after_cancel(_hover_bg_timer)
    _hover_bg_timer = root.after(delay_ms, _refresh_hover_bg)

def on_release(event):
    global is_dragging, slope_clicks
    was_dragging = is_dragging
    is_dragging  = False
    if was_dragging:
        _refresh_hover_bg()   # pan finished — recapture clean background

    # Curve Fit: only register a click if the mouse barely moved (not a drag/zoom)
    if (plot_type_var.get() == "Curve Fit"
            and event.button == 1
            and event.inaxes == ax
            and event.xdata is not None):

        dx = abs(event.x - press_x) if press_x is not None else 999
        dy = abs(event.y - press_y) if press_y is not None else 999
        if dx > 5 or dy > 5:
            return   # was a drag (rect-select / pan) — ignore

        try:
            snap_line = active_snap_line
            if snap_line is None:
                all_lines = ax.get_lines()
                for line in all_lines:
                    label = str(line.get_label()).lower()
                    if 'mean' in label or 'average' in label or 'avg' in label:
                        snap_line = line
                        break
                if snap_line is None:
                    valid = [l for l in all_lines if len(l.get_xdata()) > 2
                             and l.get_linewidth() >= 1.5]
                    snap_line = valid[-1] if valid else None

            if snap_line is None:
                show_error("No active data trace found to analyze.")
                return

            x_data      = snap_line.get_xdata()
            nearest_idx = int(np.abs(x_data - event.xdata).argmin())
            slope_clicks.append((nearest_idx, event.xdata))
            show_window_toast(f"📍 Point {len(slope_clicks)}: {event.xdata:.2f}s")

            if len(slope_clicks) == 2:
                launch_curve_fit(snap_line, slope_clicks[0], slope_clicks[1])
                slope_clicks.clear()
        except Exception as e:
            show_error(f"Curve fit capture failed: {str(e)}")
            slope_clicks.clear()

def zoom_factory(ax, base_scale=1.2):
    def zoom_fun(event):
        global _hover_bg
        if event.x is None or event.y is None:
            return
        bbox         = ax.get_window_extent()
        is_on_x      = event.y < bbox.ymin
        is_on_y      = event.x < bbox.xmin
        is_inside    = event.inaxes == ax
        scale_factor = 1 / base_scale if event.button == 'up' else \
                       base_scale     if event.button == 'down' else None
        if scale_factor is None:
            return
        cur_xlim, cur_ylim = ax.get_xlim(), ax.get_ylim()
        if is_on_x and not is_on_y:
            xdata     = event.xdata if event.xdata is not None else sum(cur_xlim) / 2
            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            rel_x     = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
            ax.set_xlim([xdata - new_width * (1 - rel_x), xdata + new_width * rel_x])
        elif is_on_y and not is_on_x:
            ydata      = event.ydata if event.ydata is not None else sum(cur_ylim) / 2
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
            rel_y      = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
            ax.set_ylim([ydata - new_height * (1 - rel_y), ydata + new_height * rel_y])
        elif is_inside and event.xdata is not None and event.ydata is not None:
            new_width  = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
            rel_x      = (cur_xlim[1] - event.xdata) / (cur_xlim[1] - cur_xlim[0])
            rel_y      = (cur_ylim[1] - event.ydata) / (cur_ylim[1] - cur_ylim[0])
            ax.set_xlim([event.xdata - new_width * (1 - rel_x), event.xdata + new_width * rel_x])
            ax.set_ylim([event.ydata - new_height * (1 - rel_y), event.ydata + new_height * rel_y])
        _hover_bg = None   # invalidate stale background so on_motion doesn't blit it
        canvas.draw_idle()
        _schedule_hover_bg_refresh()
    return zoom_fun


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def _get_window():
    """Helper to parse the time-window length configuration from the UI entry."""
    try:
        val = float(window_entry.get())
        return val if val > 0 else 30.0
    except (ValueError, NameError):
        return 30.0


def export_figure_to_file(fig_obj, default_prefix, tracking_info=""):
    """
    Consolidated file-save dashboard routine for pipeline graphics.
    Automatically handles formatting filenames and writing high-DPI images to disk.
    """
    import datetime
    from tkinter import filedialog
    
    ts = datetime.datetime.now().strftime("%H%M%S")
    store_name = cache.get('store', 'Data') if cache else 'Data'
    suffix = f"_{tracking_info}" if tracking_info else ""
    
    fpath = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG Image", "*.png"), ("PDF Document", "*.pdf"), ("SVG Vector", "*.svg")],
        initialfile=f"{default_prefix}_{store_name}{suffix}_{ts}.png",
        title=f"Export {default_prefix} Visualization"
    )
    if fpath:
        try:
            fig_obj.savefig(fpath, dpi=300, bbox_inches='tight')
            show_window_toast(f"✅ {default_prefix} Exported")
        except Exception as e:
            show_error(f"Export Failed: {str(e)}")

def launch_curve_fit(source_line, p1_tuple, p2_tuple):
    """
    Curve fitting popup — two single-clicks define the window.
    Choose any model from the registry dropdown; results update on every Fit click.

    ── HOW TO ADD A NEW MODEL ──────────────────────────────────────────────────
    Edit CURVE_FIT_MODELS below.  Each entry:
        "Display Name": (model_fn, p0_fn, ["param1", "param2", ...])
    where
        model_fn  – a function f(x, *params) -> y  (defined in models.py)
        p0_fn     – a function f(x_seg, y_seg) -> list of initial guesses
        param list– human-readable name for every parameter, in order
    ────────────────────────────────────────────────────────────────────────────
    """
    import PhysicsLibrary.models as _models

    # =========================================================================
    # CURVE FIT MODEL REGISTRY
    # Add / remove / reorder entries here — nothing else needs to change.
    # =========================================================================
    CURVE_FIT_MODELS = {
        "Linear  (y = mx + b)": (
            _models.linear_model,
            lambda x, y: [(y[-1]-y[0])/(x[-1]-x[0]) if (x[-1]-x[0]) != 0 else 0, y[0]],
            ["m (slope)", "b (intercept)"],
        ),
        "Exponential Decay  (a·e^(-bx) + c)": (
            _models.single_exponential_model,
            lambda x, y: [y.max()-y.min(), 0.1, y.min()],
            ["a (amplitude)", "b (decay rate)", "c (offset)"],
        ),
        "Exponential Rise  (a·(1-e^(-bx)) + c)": (
            _models.exponential_rise_model,
            lambda x, y: [y.max()-y.min(), 0.1, y.min()],
            ["a (amplitude)", "b (rise rate)", "c (offset)"],
        ),
        "Gaussian  (a·exp(-(x-μ)²/2σ²))": (
            _models.gaussian_model,
            lambda x, y: [y.max(), x[y.argmax()], (x[-1]-x[0])/4],
            ["a (amplitude)", "μ (centre)", "σ (width)"],
        ),
        "Sinusoidal  (a·sin(2πfx + φ) + c)": (
            _models.sinusoidal_model,
            lambda x, y: [(y.max()-y.min())/2, 1.0, 0.0, y.mean()],
            ["a (amplitude)", "f (frequency Hz)", "φ (phase)", "c (offset)"],
        ),
        "Double Exponential  (a·e^(-bx) + c·e^(-dx) + k)": (
            _models.double_exponential_model,
            lambda x, y: [y.max()*0.6, 0.05, y.max()*0.4, 0.001, y.min()],
            ["a", "b (fast rate)", "c", "d (slow rate)", "k (offset)"],
        ),
    }
    # =========================================================================

    p1_idx = p1_tuple[0]
    p2_idx = p2_tuple[0]
    i1, i2 = sorted([p1_idx, p2_idx])

    raw_xlbl = ax.get_xlabel() or plot_attrs.get("xlabel") or ""
    raw_ylbl = ax.get_ylabel() or plot_attrs.get("ylabel") or ""
    clean_xlbl = str(raw_xlbl).replace(" (s)", "").replace("(s)", "").strip() or "Time"
    clean_ylbl = str(raw_ylbl).strip() or "Signal"

    # Build channel data from cache
    x_data = cache['x']
    raw_channel_data = {}
    if 'o2hb' in cache and 'hhb' in cache:
        raw_channel_data['Mean O₂Hb'] = {
            'y':     cache['o2hb'].mean(axis=0) if cache['o2hb'].ndim > 1 else cache['o2hb'],
            'color': '#CC0000',
        }
        raw_channel_data['Mean HHb'] = {
            'y':     cache['hhb'].mean(axis=0) if cache['hhb'].ndim > 1 else cache['hhb'],
            'color': '#0033CC',
        }
        if 'thb' in cache:
            raw_channel_data['Mean tHb'] = {
                'y':     cache['thb'].mean(axis=0) if cache['thb'].ndim > 1 else cache['thb'],
                'color': '#228B22',
            }
    else:
        sig = cache.get('corr', cache.get('raw'))
        lbl = 'ΔF/F (corrected)' if 'corr' in cache else 'Raw signal'
        raw_channel_data[lbl] = {'y': sig, 'color': '#2196F3'}

    pop = tk.Toplevel(root)
    pop.title("Curve Fit")
    pop.geometry("720x680")
    pop.minsize(580, 800)

    # ── Control row: model dropdown + recalculate button + window entry ─────
    ctrl = tk.Frame(pop)
    ctrl.pack(fill="x", padx=12, pady=(10, 4))

    tk.Label(ctrl, text="Model:", font=('Helvetica', 10, 'bold')).pack(side="left", padx=(0, 4))
    model_var = tk.StringVar(value=list(CURVE_FIT_MODELS.keys())[0])
    model_menu = tk.OptionMenu(ctrl, model_var, *CURVE_FIT_MODELS.keys())
    model_menu.config(width=36)
    model_menu.pack(side="left", padx=(0, 8))

    recalc_btn = tk.Button(ctrl, text="▶ Recalculate Fit", command=lambda: _run_fit(),
                           bg="#4CAF50", fg="white",
                           font=('Helvetica', 9, 'bold'), padx=10)
    recalc_btn.pack(side="left", padx=(0, 16))
    
    # 2. Bind the Enter key to the popup window ('pop') using the correct variable name
    pop.bind("<Return>", lambda event: recalc_btn.invoke())

    tk.Label(ctrl, text="Window (s):", font=('Helvetica', 9)).pack(side="left", padx=(0, 4))
    win_entry = tk.Entry(ctrl, width=5)
    win_entry.insert(0, str(int(_get_window())))
    win_entry.pack(side="left")

    # ── Metrics readout ─────────────────────────────────────────────────────
    info_frame = tk.Frame(pop, bg="#ffffff", bd=1, relief="groove")
    info_frame.pack(fill="x", padx=12, pady=4)
    result_lbl = tk.Label(info_frame, text="Results will appear here after fitting.",
                          font=("Consolas", 9), justify="left",
                          bg="#ffffff", padx=10, pady=8, anchor="w")
    result_lbl.pack(fill="x")

    # ── Plot area ───────────────────────────────────────────────────────────
    pf = tk.Frame(pop)
    pf.pack(fill="both", expand=True, padx=12, pady=4)
    sub_fig    = Figure(figsize=(6, 3.5), dpi=100)
    sub_ax     = sub_fig.add_subplot(111)
    sub_canvas = FigureCanvasTkAgg(sub_fig, master=pf)
    sub_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _run_fit():
        model_name              = model_var.get()
        model_fn, p0_fn, pnames = CURVE_FIT_MODELS[model_name]
        is_linear               = model_name.startswith("Linear")

        # Window context from the popup's own entry
        try:
            win_sec = max(1.0, float(win_entry.get()))
        except ValueError:
            win_sec = 30.0
        half_win = win_sec / 2

        t1    = float(x_data[i1])
        t2    = float(x_data[i2])
        t_mid = (t1 + t2) / 2

        # Clamp window to data bounds
        view_start = max(float(x_data[0]),  t_mid - half_win)
        view_end   = min(float(x_data[-1]), t_mid + half_win)
        # Ensure the selected segment is always fully visible
        view_start = min(view_start, t1)
        view_end   = max(view_end,   t2)

        w_start = int(np.searchsorted(x_data, view_start))
        w_end   = int(np.searchsorted(x_data, view_end))
        w_end   = min(w_end, len(x_data) - 1)

        sub_ax.clear()
        lines_text = []
        fit_rows   = []

        for lname, cfg in raw_channel_data.items():
            y_full = cfg['y']
            color  = cfg['color']

            x_seg = x_data[i1:i2+1]
            y_seg = y_full[i1:i2+1]

            if len(x_seg) < 4:
                continue

            delta_x = t2 - t1
            delta_y = float(y_seg[-1] - y_seg[0])

            # Context window — full faded trace
            sub_ax.plot(x_data[w_start:w_end+1], y_full[w_start:w_end+1],
                        color=color, lw=1.0, alpha=0.3)
            # Selected segment — bright
            sub_ax.plot(x_seg, y_seg, color=color, lw=2.0,
                        label=f"{lname}")

            res = pl.fit_model_to_segment(x_seg, y_seg, model_fn, p0_fn)

            header = (
                f"【{lname}】\n"
                f"   P1: ({t1:.2f}s, {float(y_seg[0]):.4f})"
                f"  |  P2: ({t2:.2f}s, {float(y_seg[-1]):.4f})\n"
                f"   Δ{clean_xlbl}: {delta_x:.3f} s"
                f"  |  Δ{clean_ylbl}: {delta_y:.5f}\n"
            )

            if res["success"]:
                param_str = "   ".join(
                    f"{n} = {v:.4g}" for n, v in zip(pnames, res["popt"])
                )
                entry = header + f"   {param_str}\n   R² = {res['r2']:.4f}"
                sub_ax.plot(x_seg, res["y_fit"], color=color, lw=2.5,
                            linestyle='--',
                            label=f"{lname} fit  R²={res['r2']:.3f}")
                if is_linear:
                    sub_ax.plot([t1, t2], [float(y_seg[0]), float(y_seg[-1])],
                                'o', color=color, markersize=6, zorder=5)
                fit_rows.append({
                    "channel":      lname,
                    "model":        model_name,
                    "param_names":  pnames,
                    "param_values": list(res["popt"]),
                    "r2":           res["r2"],
                    "t1":           t1,
                    "t2":           t2,
                })
            else:
                entry = header + f"   ⚠ Fit failed: {res['error']}"

            lines_text.append(entry)

        # Shade the fit region and mark endpoints
        sub_ax.axvspan(t1, t2, alpha=0.10, color='gold', zorder=0)
        sub_ax.axvline(t1, color='gray', lw=1.0, linestyle='--', alpha=0.6)
        sub_ax.axvline(t2, color='gray', lw=1.0, linestyle='--', alpha=0.6)

        _tfs, _lfs, _lgfs = _fig_font_sizes(sub_fig)
        sub_ax.set_xlabel(f"{clean_xlbl} (s)", fontweight='bold', fontsize=_lfs)
        sub_ax.set_ylabel(clean_ylbl, fontweight='bold', fontsize=_lfs)
        sub_ax.legend(fontsize=_lgfs, loc='best')
        sub_ax.set_title(f"Curve Fit — {model_name.split('(')[0].strip()}",
                         fontweight='bold', fontsize=_tfs)
        sub_ax.grid(True, linestyle=':', alpha=0.5)
        sub_fig.tight_layout()
        # Set xlim AFTER tight_layout so it isn't overridden
        sub_ax.set_xlim(view_start, view_end)
        sub_canvas.draw()

        divider = chr(10) + "—" * 60 + chr(10)
        result_lbl.config(text=divider.join(lines_text) or "No data found.")
        last_fit_results[:] = fit_rows   # expose for export buttons

    # ── Bottom buttons ───────────────────────────────────────────────────────
    last_fit_results = []   # filled by _run_fit: list of dicts per channel

    def _copy_params():
        txt = result_lbl.cget("text")
        if not txt or txt == "Results will appear here after fitting.":
            return
        pop.clipboard_clear()
        pop.clipboard_append(txt)
        show_window_toast("📋 Parameters copied to clipboard")

    def _export_csv():
        if not last_fit_results:
            show_error("Run the fit first.")
            return
        import csv as _csv, datetime as _dt
        ts   = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt")],
            initialfile=f"CurveFit_{ts}.csv",
            title="Export fit parameters",
            parent=pop,
        )
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8') as fh:
            writer = _csv.writer(fh)
            writer.writerow(["Channel", "Model", "Parameter", "Value", "R²",
                             "t1 (s)", "t2 (s)", "Δt (s)"])
            for row in last_fit_results:
                for pname, pval in zip(row["param_names"], row["param_values"]):
                    writer.writerow([row["channel"], row["model"], pname,
                                     f"{pval:.6g}", f"{row['r2']:.4f}",
                                     f"{row['t1']:.4f}", f"{row['t2']:.4f}",
                                     f"{row['t2']-row['t1']:.4f}"])
        show_window_toast(f"✅ Saved {os.path.basename(path)}")

    btn_frame = tk.Frame(pop)
    btn_frame.pack(fill="x", pady=8, padx=12)
    tk.Button(btn_frame, text="📋 Copy",
              command=_copy_params,
              bg="#e1e1e1",
              font=('Helvetica', 10, 'bold'), padx=14).pack(side="left", padx=4)
    tk.Button(btn_frame, text="📄 Export CSV",
              command=_export_csv,
              bg="#e1e1e1",
              font=('Helvetica', 10, 'bold'), padx=14).pack(side="left", padx=4)
    tk.Button(btn_frame, text="🖼 Export Plot",
              command=lambda: export_figure_to_file(sub_fig, "CurveFit"),
              bg="#2196F3", fg="white",
              font=('Helvetica', 10, 'bold'), padx=14).pack(side="left", padx=4)
    tk.Button(btn_frame, text="Close", command=pop.destroy,
              bg="#e1e1e1", font=('Helvetica', 10, 'bold'), padx=14).pack(side="left", padx=4)

    _run_fit()


def launch_zscore_peth(center_t):
    if cache is None or cache.get('source') != 'TDT':
        show_error("PETH is only available for TDT data.")
        return
    data_source  = cache['corr'] if show_corrected else cache['raw']
    clean_signal = pl.smooth_signal(data_source, cache['fs'])
    slice_x, z_seg = pl.get_zscore_slice(cache['x'], clean_signal, center_t, window=30)
    if z_seg is None:
        return
    z_binned = pl.bin_for_heatmap(z_seg)
    mode_str = "Corrected" if show_corrected else "Raw"
    
    pop = tk.Toplevel(root)
    pop.title(f"PETH Analysis ({mode_str}) - {center_t:.2f}s")
    
    fig_peth = Figure(figsize=(8, 7), dpi=100)
    ax_heat, ax_line = fig_peth.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [1, 1]})
    
    ax_heat.imshow(z_binned.reshape(1, -1), aspect='auto', cmap='YlGnBu_r',
                    extent=[-30, 30, 0, 1], vmin=-5, vmax=5, interpolation='bilinear')
    ax_heat.set_yticks([])
    _tfs_p, _lfs_p, _ = _fig_font_sizes(fig_peth)
    ax_heat.set_ylabel("Intensity", fontweight='bold', fontsize=_lfs_p)

    ax_line.plot(slice_x - center_t, z_seg, color='black', linewidth=1.5)
    ax_line.axvline(0, color='red', linestyle='--', alpha=0.8)
    ax_line.set_xlim([-15, 15])
    ax_line.set_ylim([-5, 5])
    ax_line.set_ylabel(f"Z-Score ({mode_str})", fontweight='bold', fontsize=_lfs_p)
    ax_line.set_xlabel("Time from Center (s)", fontweight='bold', fontsize=_lfs_p)

    fig_peth.suptitle("Z-score PETH", fontsize=_tfs_p, fontweight='bold')
    fig_peth.tight_layout(rect=[0, 0.05, 1, 0.95])
    
    canvas_peth = FigureCanvasTkAgg(fig_peth, master=pop)
    canvas_peth.get_tk_widget().pack(fill="both", expand=True)
    
    btn_frame = tk.Frame(pop)
    btn_frame.pack(side="bottom", fill="x", pady=10)
    tk.Button(btn_frame, text=f"💾 Export {mode_str} PETH",
              command=lambda: export_figure_to_file(fig_peth, f"PETH_{mode_str}", f"{int(center_t)}s"),
              bg="#2196F3", fg="white", font=('Helvetica', 10, 'bold'), padx=20).pack()
              
    show_window_toast(f"PETH Generated at {center_t:.1f}s")

def launch_fft(center_t):
    if cache is None:
        return
    window = _get_window()
    fs     = cache['fs']
    pop    = tk.Toplevel(root)
    pop.title(f"FFT — {cache['store']}  |  centre {center_t:.1f}s  |  window {window:.0f}s")

    if cache.get('source') == 'Oxysoft':
        x    = cache['x']
        o2hb = cache['o2hb'].mean(axis=0)
        hhb  = cache['hhb'].mean(axis=0)
        fig_fft      = Figure(figsize=(8, 7), dpi=100)
        ax_o2, ax_hh = fig_fft.subplots(2, 1)
        for sig, ax_f, color, label in [
            (o2hb, ax_o2, '#CC0000', 'Mean O2Hb'),
            (hhb,  ax_hh, '#0033CC', 'Mean HHb'),
        ]:
            freqs, power, _, _ = pl.compute_fft_slice(x, sig, center_t, fs, window=window)
            if len(freqs) > 0:
                ax_f.plot(freqs, power, color=color, lw=1.5)
                pl.annotate_fft_peaks(ax_f, freqs, power, color)
            _tfs_f, _lfs_f, _ = _fig_font_sizes(fig_fft)
            ax_f.set_ylabel("Power", fontweight='bold', fontsize=_lfs_f)
            ax_f.set_title(label, fontweight='bold', fontsize=_tfs_f)
            ax_f.set_xlim(0.05, fs / 2)
            ax_f.autoscale(axis='y')
        ax_hh.set_xlabel("Frequency (Hz)", fontweight='bold', fontsize=_lfs_f)
    else:
        signal = cache['corr'] if show_corrected else cache['raw']
        freqs, power, _, _ = pl.compute_fft_slice(cache['x'], signal, center_t, fs, window=window)
        fig_fft = Figure(figsize=(8, 4), dpi=100)
        ax_f    = fig_fft.add_subplot(111)
        if len(freqs) > 0:
            ax_f.plot(freqs, power, color='blue', lw=1.5)
            pl.annotate_fft_peaks(ax_f, freqs, power, 'blue')
        _tfs_f, _lfs_f, _ = _fig_font_sizes(fig_fft)
        ax_f.set_xlabel("Frequency (Hz)", fontweight='bold', fontsize=_lfs_f)
        ax_f.set_ylabel("Power", fontweight='bold', fontsize=_lfs_f)
        ax_f.set_title(f"FFT — {cache['store']}", fontweight='bold', fontsize=_tfs_f)
        ax_f.set_xlim(0.05, fs / 2)
        ax_f.autoscale(axis='y')

    fig_fft.suptitle(f"centre {center_t:.1f}s  |  window {window:.0f}s",
                     fontsize=10, color='gray')
    fig_fft.tight_layout(rect=[0, 0.03, 1, 0.97])
    canvas_fft = FigureCanvasTkAgg(fig_fft, master=pop)
    canvas_fft.get_tk_widget().pack(fill="both", expand=True)
    def save_fft_action():
        ts = datetime.datetime.now().strftime("%H%M%S")
        fpath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
            initialfile=f"FFT_{cache['store']}_{int(center_t)}s_{ts}.png", title="Export FFT"
        )
        if fpath:
            try:
                fig_fft.savefig(fpath, dpi=300, bbox_inches='tight')
                show_window_toast("FFT Exported")
            except Exception as e:
                show_error(f"Export Failed: {str(e)}")
    btn_frame = tk.Frame(pop)
    btn_frame.pack(side="bottom", fill="x", pady=10)
    tk.Button(btn_frame, text="💾 Export FFT",
              command=save_fft_action, bg="#2196F3", fg="white",
              font=('Helvetica', 10, 'bold'), padx=20).pack()
    show_window_toast(f"FFT at {center_t:.1f}s")


def analysis_type(clicked_x):
    """
    Central router that handles double-click events, ensures timestamps 
    are clean floats, and routes to the correct localized window.
    """
    if clicked_x is None:
        return

    try:
        center_timestamp = float(clicked_x)
    except (ValueError, TypeError):
        show_error("Invalid coordinate format captured.")
        return

    current_mode = plot_type_var.get()

    if current_mode == "FFT":
        launch_fft(center_timestamp)
    elif current_mode == "Z-Score PETH" or current_mode == "PETH":
        launch_zscore_peth(center_timestamp)
    elif current_mode == "Curve Fit":
        show_window_toast("ℹ️ In Curve Fit Mode: Use single-clicks to anchor two points.")
# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _update_plot_with_notes(markers):
    import matplotlib.transforms as transforms
    trans         = transforms.blended_transform_factory(ax.transData, ax.transAxes)
    unique_labels = set()
    for m in markers:
        label_id = m['label'] if m['label'] not in unique_labels else "_nolegend_"
        unique_labels.add(m['label'])
        ax.axvline(x=m['time'], color=m['color'], linestyle='--', alpha=0.6, label=label_id)
        ax.text(m['time'], 0.98, f" {m['label']}", transform=trans,
                rotation=90, va='top', clip_on=True, fontsize=m.get('fontsize', 8),
                color=m['color'], fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))


def _apply_plot_attrs():
    """Re-apply persisted label/legend customisations after any redraw."""
    # Always apply font sizes; only override text when the user has set a custom value.
    title_text  = plot_attrs["title"]  or ax.get_title()
    xlabel_text = plot_attrs["xlabel"] or ax.get_xlabel()
    ylabel_text = plot_attrs["ylabel"] or ax.get_ylabel()
    ax.set_title(title_text,  fontweight='bold', pad=15, fontsize=plot_attrs["title_fs"])
    ax.set_xlabel(xlabel_text, fontweight='bold', fontsize=plot_attrs["xlabel_fs"])
    ax.set_ylabel(ylabel_text, fontweight='bold', fontsize=plot_attrs["ylabel_fs"])

    # Rebuild legend with persisted settings
    handles, labels = ax.get_legend_handles_labels()
    entries = [(h, l) for h, l in zip(handles, labels) if not l.startswith('_')]
    if not entries:
        return

    if plot_attrs["leg_entries"]:
        # Filter/rename based on saved entries list: [(original_label, new_label, visible), ...]
        label_map = {orig: (new, vis) for orig, new, vis in plot_attrs["leg_entries"]}
        new_h, new_l = [], []
        for h, l in entries:
            if l in label_map:
                new_label, visible = label_map[l]
                if visible:
                    new_h.append(h)
                    new_l.append(new_label)
            else:
                new_h.append(h)
                new_l.append(l)
        if new_h:
            ax.legend(new_h, new_l,
                      fontsize=plot_attrs["leg_fs"],
                      loc=plot_attrs["leg_loc"])
        else:
            leg = ax.get_legend()
            if leg: leg.remove()
    else:
        ax.legend(fontsize=plot_attrs["leg_fs"],
                  loc=plot_attrs["leg_loc"])


def simple_plot(draw_now=True):
    global tracker_dots, connecting_line, _hover_bg
    
    if cache is None:
        return
    ax.clear()
    ax.axhline(0, color='black', linewidth=1.0, alpha=0.4, zorder=1)

    if cache.get('source') == 'Oxysoft':
        x    = cache['x']
        o2hb = cache['o2hb']
        hhb  = cache['hhb']
        for i in range(o2hb.shape[0]):
            ax.plot(x, o2hb[i], color='#FF9999', lw=0.8, alpha=0.5,
                    label='O₂Hb channels' if i == 0 else '_nolegend_')
            ax.plot(x, hhb[i],  color='#99BBFF', lw=0.8, alpha=0.5,
                    label='HHb channels'  if i == 0 else '_nolegend_')
        ff = cache.get('fit_factor_mean')
        ff_tag = f"  [FF: {ff:.1f}%]" if ff is not None else ""
        ax.plot(x, o2hb.mean(axis=0), color='#CC0000', lw=2.0, label=f'Mean O₂Hb{ff_tag}')
        ax.plot(x, hhb.mean(axis=0),  color='#0033CC', lw=2.0, label=f'Mean HHb{ff_tag}')
        if 'thb' in cache:
            thb = cache['thb']
            ax.plot(x, thb.mean(axis=0), color='#228B22', lw=2.0, label=f'Mean tHb{ff_tag}')
        ax.set_ylabel("Δ Concentration (μM)", fontweight='bold')
        ax.set_title(f"NIRS — {cache['store']}", fontweight='bold', pad=15)
        x_label = "Time (s)"
    elif cache.get('source') == 'Generic':
        x = cache['x']
        _GEN_COLORS = ['#CC0000', '#0033CC', '#228B22', '#CC6600',
                       '#6600CC', '#008888', '#AA0055', '#005588']
        for i, (col_name, y) in enumerate(cache['y_columns'].items()):
            mask = ~np.isnan(y)
            ax.plot(x[mask], y[mask], 'o-', lw=1.8, markersize=4,
                    color=_GEN_COLORS[i % len(_GEN_COLORS)], label=col_name)
        ax.set_ylabel("Value", fontweight='bold')
        ax.set_title(cache['store'], fontweight='bold', pad=15)
        x_label = cache.get('x_label', 'X')
    else:
        data_to_plot = cache['corr'] if show_corrected else cache['raw']
        color_choice = 'blue' if show_corrected else 'gray'
        label_text   = 'ΔF/F (corrected)' if show_corrected else 'Raw signal'
        ax.axvline(0, color='black', linewidth=1.0, alpha=0.4, zorder=1)
        ax.plot(cache['x'], data_to_plot, color=color_choice,
                lw=1.5, alpha=0.8, label=label_text)
        ax.set_ylabel("Amplitude", fontweight='bold')
        ax.set_title(f"{label_text} — {cache['store']}", fontweight='bold', pad=15)
        x_label = "Time (s)"

    _update_plot_with_notes(cache['markers'])
    ax.set_xlabel(x_label, fontweight='bold')
    ax.legend(loc='upper left', fontsize=plot_attrs["leg_fs"])
    ax.set_xlim(cache['x'][0], cache['x'][-1])
    _apply_plot_attrs()

    # Grid
    if show_grid:
        ax.grid(True, linestyle=':', alpha=0.4, color='gray')

    # ── Hover tracker dots — one per snappable line ─────────────────────────
    _snap_lines = [
        l for l in ax.get_lines()
        if not str(l.get_label()).startswith('_')
        and len(l.get_xdata()) > 2
        and l.get_linewidth() >= 1.5
    ]
    tracker_dots = []
    for _ in _snap_lines:
        dot, = ax.plot([], [], 'o', markersize=8, zorder=5, animated=True)
        tracker_dots.append(dot)

    connecting_line, = ax.plot([], [], ':', color='gray', lw=1.0, alpha=0.7,
                               label='_connector', zorder=4, animated=True)

    if draw_now:
        canvas.draw()
        _hover_bg = canvas.copy_from_bbox(fig.bbox)

def reset_zoom():
    if cache is None:
        return
    simple_plot()
    if 'rect_selector' in globals():
        rect_selector.ax = ax
        rect_selector.set_active(True)
    canvas.draw_idle()

def export_canvas_action():
    if cache is None:
        show_error("No data loaded to export!")
        return
    timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    initial_name = f"{cache['store']}_Plot_{timestamp}.png"
    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
        initialfile=initial_name, title="Export Current View"
    )
    if file_path:
        try:
            fig.savefig(file_path, dpi=300, bbox_inches='tight', transparent=False)
            show_window_toast(f"✅ Exported: {os.path.basename(file_path)}")
        except Exception as e:
            show_error(f"Export Failed: {str(e)}")

def open_attributes_window():
    """
    Edit graph labels, font sizes, legend size, and legend position.
    """
    win = tk.Toplevel(root)
    win.title("Edit Graph Attributes")
    win.resizable(False, False)
    win.grab_set()

    pad = {'padx': 10, 'pady': 5}

    # ---- seed values from saved plot_attrs, fall back to live axes ------
    cur_title  = plot_attrs["title"]  or ax.get_title()
    cur_xlabel = plot_attrs["xlabel"] or ax.get_xlabel()
    cur_ylabel = plot_attrs["ylabel"] or ax.get_ylabel()

    cur_title_fs  = plot_attrs["title_fs"]
    cur_xlabel_fs = plot_attrs["xlabel_fs"]
    cur_ylabel_fs = plot_attrs["ylabel_fs"]
    cur_leg_fs    = plot_attrs["leg_fs"]

    # ---- helpers -------------------------------------------------------
    def _row(parent, label_text, row, default_text='', default_size=12):
        tk.Label(parent, text=label_text).grid(
            row=row, column=0, sticky="e", **pad)
        e_text = tk.Entry(parent, width=28)
        e_text.insert(0, default_text)
        e_text.grid(row=row, column=1, **pad)
        tk.Label(parent, text="Size:").grid(row=row, column=2, sticky="e", padx=(10,2))
        e_size = tk.Entry(parent, width=4)
        e_size.insert(0, str(default_size))
        e_size.grid(row=row, column=3, padx=(0,10))
        return e_text, e_size

    # ---- label section -------------------------------------------------
    lf = tk.LabelFrame(win, text="Labels & Font Sizes", padx=8, pady=6)
    lf.grid(row=0, column=0, columnspan=2, padx=10, pady=(10,5), sticky="ew")

    e_title,  e_title_fs  = _row(lf, "Title:",   0, cur_title,  cur_title_fs)
    e_xlabel, e_xlabel_fs = _row(lf, "X Label:", 1, cur_xlabel, cur_xlabel_fs)
    e_ylabel, e_ylabel_fs = _row(lf, "Y Label:", 2, cur_ylabel, cur_ylabel_fs)

    # ---- legend section ------------------------------------------------
    lf2 = tk.LabelFrame(win, text="Legend", padx=8, pady=6)
    lf2.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

    tk.Label(lf2, text="Font size:").grid(row=0, column=0, sticky="e", **pad)
    e_leg_fs = tk.Entry(lf2, width=4)
    e_leg_fs.insert(0, str(cur_leg_fs))
    e_leg_fs.grid(row=0, column=1, sticky="w", **pad)

    tk.Label(lf2, text="Position:").grid(row=0, column=2, sticky="e", padx=(20,2))
    leg_loc_var = tk.StringVar(value=plot_attrs["leg_loc"])
    leg_locs = ["upper left", "upper right", "lower left", "lower right",
                "upper center", "lower center", "center left", "center right",
                "center", "best"]
    tk.OptionMenu(lf2, leg_loc_var, *leg_locs).grid(row=0, column=3, padx=(0,10))

    # --- per-entry show/hide + rename ---
    handles, labels = ax.get_legend_handles_labels()
    entries = [(h, l) for h, l in zip(handles, labels) if not l.startswith('_')]

    # Build lookup from previously saved state
    saved_entry_map = {}
    if plot_attrs["leg_entries"]:
        saved_entry_map = {orig: (new, vis) for orig, new, vis in plot_attrs["leg_entries"]}

    entry_vars  = []
    entry_frame = tk.Frame(lf2)
    entry_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6,0))

    if entries:
        tk.Label(entry_frame, text="Show", width=4).grid(row=0, column=0, padx=4)
        tk.Label(entry_frame, text="Label").grid(row=0, column=1, padx=4, sticky="w")

        for i, (h, l) in enumerate(entries):
            saved_label, saved_vis = saved_entry_map.get(l, (l, True))
            bv = tk.BooleanVar(value=saved_vis)
            sv = tk.StringVar(value=saved_label)
            tk.Checkbutton(entry_frame, variable=bv).grid(
                row=i+1, column=0, padx=4)
            e = tk.Entry(entry_frame, textvariable=sv, width=28)
            e.grid(row=i+1, column=1, padx=4, pady=2, sticky="w")
            entry_vars.append((bv, sv, h, l))  # l = original label
    else:
        tk.Label(entry_frame, text="No legend entries found — load data first.",
                 fg="gray").grid(row=0, column=0, columnspan=4, pady=4)

    # ---- apply / cancel ------------------------------------------------
    def _apply():
        def _safe_int(entry, default):
            try:    return max(6, int(entry.get()))
            except: return default

        # Save into plot_attrs so settings survive redraws
        if e_title.get().strip():
            plot_attrs["title"]    = e_title.get().strip()
            plot_attrs["title_fs"] = _safe_int(e_title_fs, cur_title_fs)
        if e_xlabel.get().strip():
            plot_attrs["xlabel"]    = e_xlabel.get().strip()
            plot_attrs["xlabel_fs"] = _safe_int(e_xlabel_fs, cur_xlabel_fs)
        if e_ylabel.get().strip():
            plot_attrs["ylabel"]    = e_ylabel.get().strip()
            plot_attrs["ylabel_fs"] = _safe_int(e_ylabel_fs, cur_ylabel_fs)

        plot_attrs["leg_fs"]  = _safe_int(e_leg_fs, cur_leg_fs)
        plot_attrs["leg_loc"] = leg_loc_var.get()

        # Save legend entries as (original_label, new_label, visible)
        if entry_vars:
            plot_attrs["leg_entries"] = [
                (orig_l, sv.get() or orig_l, bv.get())
                for bv, sv, h, orig_l in entry_vars
            ]

        _apply_plot_attrs()
        _refresh_hover_bg()
        win.destroy()

    btn_row = tk.Frame(win)
    btn_row.grid(row=2, column=0, columnspan=2, pady=10)

    recalc_btn = tk.Button(btn_row, text="Apply", command=_apply,
              bg="#4CAF50", fg="white",
              font=('Helvetica', 9, 'bold'),
              padx=20)

    recalc_btn.pack(side="left", padx=5)


    win.bind("<Return>", lambda event: recalc_btn.invoke())
    
    tk.Button(btn_row, text="Cancel", command=win.destroy,
              bg="#e1e1e1",
              font=('Helvetica', 9, 'bold'),
              padx=20).pack(side="left", padx=5)


#####################
# --- GUI SETUP --- #
#####################

window_width  = 1250
window_height = 850
screen_width  = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
root.geometry(f'{window_width}x{window_height}+'
              f'{int(screen_width/2 - window_width/2)}+'
              f'{int(screen_height/2 - window_height/2)}')
root.state('zoomed')
options_frame = tk.LabelFrame(root, text="Controls & Analysis")
options_frame.pack(pady=10, padx=10, fill="x")

# --- Open dropdown + Reload ---
open_mb = tk.Menubutton(options_frame, text="📂 Open ▾",
                         bg="#e1e1e1", font=('Helvetica', 9, 'bold'),
                         relief="raised", padx=8)
open_mb.pack(side="left", padx=(10, 2), pady=10)
open_menu = tk.Menu(open_mb, tearoff=0)
open_mb.config(menu=open_menu)
open_menu.add_command(label="Open TDT folder",     command=open_folder)
open_menu.add_command(label="Open TXT (Oxysoft)",  command=open_file)
open_menu.add_command(label="Open Excel",          command=launch_generic_file_loader)
open_menu.add_command(label="Open PT2 (EFNMR)",   command=launch_pt2_viewer)

tk.Button(options_frame, text="🔄 Reload",
          command=load_data_action, bg="#e1e1e1",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=(2, 10), pady=10)

tk.Label(options_frame, text="|").pack(side="left", padx=5)

# --- Grid toggle ---
_grid_var = tk.BooleanVar(value=True)
def _toggle_grid():
    global show_grid
    show_grid = _grid_var.get()
    if cache is not None:
        simple_plot()
tk.Checkbutton(options_frame, text="Grid", variable=_grid_var,
               command=_toggle_grid,
               font=('Helvetica', 9, 'bold')).pack(side="left", padx=(0, 8))

tk.Label(options_frame, text="|").pack(side="left", padx=5)

# --- Analysis dropdown + window ---
plot_type_var = tk.StringVar(root)
plot_type_var.set("Analysis")
tk.OptionMenu(options_frame, plot_type_var, "Z-Score PETH", "FFT", "Curve Fit").pack(side="left", padx=10)
tk.Label(options_frame, text="Window (s):").pack(side="left", padx=(10, 2))
window_entry = tk.Entry(options_frame, width=5)
window_entry.insert(0, "30")
window_entry.pack(side="left", padx=(0, 10))

tk.Label(options_frame, text="|").pack(side="left", padx=5)

# --- Marker controls ---
btn_add_marker = tk.Button(options_frame, text="🖊 Add Marker",
                           command=toggle_marker_mode, bg="#e1e1e1",
                           font=('Helvetica', 9, 'bold'))
btn_add_marker.pack(side="left", padx=(10, 2))

tk.Button(options_frame, text="🗑 Undo Last",
          command=lambda: (cache['markers'].pop() if cache and cache['markers'] else None,
                           simple_plot()) if cache else None,
          bg="#e1e1e1",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=(2, 2))

tk.Button(options_frame, text="💾 Save Markers",
          command=save_markers, bg="#e1e1e1",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=(2, 10))

tk.Label(options_frame, text="|").pack(side="left", padx=5)

# --- View controls ---
tk.Button(options_frame, text="Reset Zoom",
          command=reset_zoom).pack(side="left", padx=10)

tk.Button(options_frame, text="Export View (PNG/PDF)",
          command=export_canvas_action,
          bg="#2196F3", fg="white",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=10)

tk.Button(options_frame, text="🎨 Edit Attributes",
          command=open_attributes_window,
          bg="#e1e1e1",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=10)

# --- Plot area ---
plot_frame = tk.Frame(root)
plot_frame.pack(side="bottom", fill="both", expand=True, pady=10)

fig    = Figure(figsize=(8, 4), dpi=100)
ax     = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=plot_frame)
canvas.draw()
canvas.get_tk_widget().pack(fill="both", expand=True)

fig.canvas.mpl_connect('button_press_event',   on_press)
fig.canvas.mpl_connect('motion_notify_event',  on_motion)
fig.canvas.mpl_connect('button_release_event', on_release)

f_zoom = zoom_factory(ax, base_scale=1.1)
fig.canvas.mpl_connect('scroll_event', f_zoom)

global rect_selector
rect_selector = RectangleSelector(
    ax, on_select, useblit=True, button=[1],
    minspanx=5, minspany=0.001,
    props=dict(facecolor='yellow', edgecolor='black', alpha=0.3, fill=True),
    interactive=True
)
rect_selector.set_active(True)

# ---------------------------------------------------------------------------
# Status Bar for Coordinates
# ---------------------------------------------------------------------------
coord_var = tk.StringVar(value="X: -- | Y: -- | Pt: --")
status_bar = tk.Label(root, textvariable=coord_var, bd=1, relief="sunken", 
                      anchor="w", font=("Consolas", 9), bg="#f0f0f0", padx=10, pady=3)
status_bar.pack(side="bottom", fill="x")

root.mainloop()