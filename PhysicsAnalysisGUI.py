import sys
sys.path.insert(0, r'C:\Users\zakgm\anaconda3\Lib\site-packages')

import tkinter as tk
from tkinter import filedialog
import os
import json
import PhysicsLibrary as pl
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

# Persisted plot customisations — survive redraws
plot_attrs = {
    "title":     None,   # str or None = use auto title
    "xlabel":    None,
    "ylabel":    None,
    "title_fs":  14,
    "xlabel_fs": 12,
    "ylabel_fs": 12,
    "leg_fs":    8,
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
        show_success(f"Markers saved")
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

    # Colour picker (simple preset list)
    tk.Label(win, text="Colour:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
    color_var = tk.StringVar(value="green")
    color_frame = tk.Frame(win)
    color_frame.grid(row=1, column=1, padx=10, pady=5, sticky="w")
    for col in ["green", "red", "blue", "orange", "purple"]:
        tk.Radiobutton(color_frame, text=col, variable=color_var,
                       value=col, fg=col).pack(side="left")

    def _confirm():
        label = e_name.get().strip() or "Marker"
        color = color_var.get()
        cache['markers'].append({"time": t, "label": label, "color": color})
        simple_plot()
        win.destroy()

    tk.Button(win, text="Add", command=_confirm,
              bg="#4CAF50", fg="white",
              font=('Helvetica', 9, 'bold'),
              padx=20).grid(row=2, column=0, columnspan=2, pady=10)

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
        win.title("Rename Marker")
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text="New name:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        e = tk.Entry(win, width=25)
        e.insert(0, marker['label'])
        e.grid(row=0, column=1, padx=10, pady=10)
        e.focus_set()
        e.select_range(0, tk.END)
        def _ok():
            marker['label'] = e.get().strip() or marker['label']
            simple_plot()
            win.destroy()
        tk.Button(win, text="OK", command=_ok,
                  bg="#4CAF50", fg="white",
                  font=('Helvetica', 9, 'bold'),
                  padx=20).grid(row=1, column=0, columnspan=2, pady=10)
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
            "title_fs": 14, "xlabel_fs": 12, "ylabel_fs": 12,
            "leg_fs": 8, "leg_loc": "upper left", "leg_entries": None,
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
        cache = {
            "source":  "Oxysoft",
            "x":       x,
            "o2hb":    o2hb,
            "hhb":     hhb,
            "fs":      dataset.sample_rate,
            "store":   os.path.splitext(os.path.basename(file_path))[0],
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
    x1, y1 = eclick.xdata,   eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    if None in [x1, x2, y1, y2] or abs(x1 - x2) < 0.1:
        return
    ax.set_xlim(min(x1, x2), max(x1, x2))
    ax.set_ylim(min(y1, y2), max(y1, y2))
    rect_selector.clear()
    canvas.draw_idle()
    show_window_toast("Zoomed to Selection")

def on_press(event):
    global is_dragging, press_x, press_y
    if event.inaxes != ax:
        return

    # --- Marker mode: left-click places, right-click context menu, nothing else ---
    if marker_mode:
        if event.button == 1 and not event.dblclick and event.xdata is not None:
            _place_marker(event.xdata)
        elif event.button == 3 and event.xdata is not None:
            _right_click_marker_menu(event)
        return   # block ALL other interactions while in marker mode

    # --- Right-click: context menu if near a marker, else pan ---
    if event.button == 3:
        if event.xdata is not None and _find_nearest_marker(event.xdata) is not None:
            _right_click_marker_menu(event)
        else:
            is_dragging      = True
            press_x, press_y = event.x, event.y
        return

    # --- Double left-click: analysis ---
    if event.dblclick and event.button == 1 and event.xdata is not None:
        analysis_type(event.xdata)
        return

    # --- Middle-click: reset zoom ---
    if event.button == 2:
        reset_zoom()

def on_motion(event):
    global press_x, press_y
    if not is_dragging or event.inaxes != ax:
        return
    if event.x is None or event.y is None:
        return
    dx, dy        = event.x - press_x, event.y - press_y
    press_x, press_y = event.x, event.y
    cur_xlim      = ax.get_xlim()
    cur_ylim      = ax.get_ylim()
    bbox          = ax.get_window_extent()
    shift_x       = (dx / bbox.width)  * (cur_xlim[1] - cur_xlim[0])
    shift_y       = (dy / bbox.height) * (cur_ylim[1] - cur_ylim[0])
    ax.set_xlim(cur_xlim[0] - shift_x, cur_xlim[1] - shift_x)
    ax.set_ylim(cur_ylim[0] - shift_y, cur_ylim[1] - shift_y)
    canvas.draw_idle()

def on_release(event):
    global is_dragging
    is_dragging = False

def zoom_factory(ax, base_scale=1.2):
    def zoom_fun(event):
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
        canvas.draw_idle()
    return zoom_fun


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

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
    fig_peth         = Figure(figsize=(8, 7), dpi=100)
    ax_heat, ax_line = fig_peth.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [1, 1]})
    ax_heat.imshow(z_binned.reshape(1, -1), aspect='auto', cmap='YlGnBu_r',
                   extent=[-30, 30, 0, 1], vmin=-5, vmax=5, interpolation='bilinear')
    ax_heat.set_yticks([])
    ax_heat.set_ylabel("Intensity", fontweight='bold')
    ax_line.plot(slice_x - center_t, z_seg, color='black', linewidth=1.5)
    ax_line.axvline(0, color='red', linestyle='--', alpha=0.8)
    ax_line.set_xlim([-15, 15])
    ax_line.set_ylim([-5, 5])
    ax_line.set_ylabel(f"Z-Score ({mode_str})", fontweight='bold')
    ax_line.set_xlabel("Time from Center (s)", fontweight='bold')
    fig_peth.suptitle("Z-score PETH", fontsize=14, fontweight='bold')
    fig_peth.tight_layout(rect=[0, 0.05, 1, 0.95])
    canvas_peth = FigureCanvasTkAgg(fig_peth, master=pop)
    canvas_peth.get_tk_widget().pack(fill="both", expand=True)
    def save_peth_action():
        ts = datetime.datetime.now().strftime("%H%M%S")
        fpath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
            initialfile=f"PETH_{mode_str}_{int(center_t)}s_{ts}.png", title="Export PETH"
        )
        if fpath:
            try:
                fig_peth.savefig(fpath, dpi=300, bbox_inches='tight')
                show_window_toast("✅ PETH Exported")
            except Exception as e:
                show_error(f"Export Failed: {str(e)}")
    btn_frame = tk.Frame(pop)
    btn_frame.pack(side="bottom", fill="x", pady=10)
    tk.Button(btn_frame, text=f"💾 Export {mode_str} PETH",
              command=save_peth_action, bg="#2196F3", fg="white",
              font=('Helvetica', 10, 'bold'), padx=20).pack()
    show_window_toast(f"PETH Generated at {center_t:.1f}s")

def _get_window():
    try:
        val = float(window_entry.get())
        return val if val > 0 else 30.0
    except ValueError:
        return 30.0

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
            ax_f.set_ylabel("Power", fontweight='bold')
            ax_f.set_title(label, fontweight='bold')
            ax_f.set_xlim(0.05, fs / 2)
            ax_f.autoscale(axis='y')
        ax_hh.set_xlabel("Frequency (Hz)", fontweight='bold')
    else:
        signal = cache['corr'] if show_corrected else cache['raw']
        freqs, power, _, _ = pl.compute_fft_slice(cache['x'], signal, center_t, fs, window=window)
        fig_fft = Figure(figsize=(8, 4), dpi=100)
        ax_f    = fig_fft.add_subplot(111)
        if len(freqs) > 0:
            ax_f.plot(freqs, power, color='blue', lw=1.5)
            pl.annotate_fft_peaks(ax_f, freqs, power, 'blue')
        ax_f.set_xlabel("Frequency (Hz)", fontweight='bold')
        ax_f.set_ylabel("Power", fontweight='bold')
        ax_f.set_title(f"FFT — {cache['store']}", fontweight='bold')
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

def analysis_type(data):
    choice = plot_type_var.get()
    if choice == "Z-Score PETH":
        launch_zscore_peth(data)
    elif choice == "FFT":
        launch_fft(data)


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
                rotation=90, va='top', clip_on=True, fontsize=8,
                color=m['color'], fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))


def _apply_plot_attrs():
    """Re-apply persisted label/legend customisations after any redraw."""
    if plot_attrs["title"]:
        ax.set_title(plot_attrs["title"], fontweight='bold', pad=15,
                     fontsize=plot_attrs["title_fs"])
    if plot_attrs["xlabel"]:
        ax.set_xlabel(plot_attrs["xlabel"], fontweight='bold',
                      fontsize=plot_attrs["xlabel_fs"])
    if plot_attrs["ylabel"]:
        ax.set_ylabel(plot_attrs["ylabel"], fontweight='bold',
                      fontsize=plot_attrs["ylabel_fs"])

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
                    label='O₂Hb channels' if i == 0 else '_')
            ax.plot(x, hhb[i],  color='#99BBFF', lw=0.8, alpha=0.5,
                    label='HHb channels'  if i == 0 else '_')
        ax.plot(x, o2hb.mean(axis=0), color='#CC0000', lw=2.0, label='Mean O₂Hb')
        ax.plot(x, hhb.mean(axis=0),  color='#0033CC', lw=2.0, label='Mean HHb')
        ax.set_ylabel("Δ Concentration (μM)", fontweight='bold')
        ax.set_title(f"NIRS — {cache['store']}", fontweight='bold', pad=15)
    else:
        data_to_plot = cache['corr'] if show_corrected else cache['raw']
        color_choice = 'blue' if show_corrected else 'gray'
        label_text   = 'ΔF/F (corrected)' if show_corrected else 'Raw signal'
        ax.axvline(0, color='black', linewidth=1.0, alpha=0.4, zorder=1)
        ax.plot(cache['x'], data_to_plot, color=color_choice,
                lw=1, alpha=0.8, label=label_text)
        ax.set_ylabel("Amplitude", fontweight='bold')
        ax.set_title(f"{label_text} — {cache['store']}", fontweight='bold', pad=15)

    _update_plot_with_notes(cache['markers'])
    ax.set_xlabel("Time (s)", fontweight='bold')
    ax.legend(loc='upper left', fontsize=8)
    ax.set_xlim(cache['x'][0], cache['x'][-1])
    _apply_plot_attrs()
    if draw_now:
        canvas.draw()

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

    # ---- current values ------------------------------------------------
    cur_title  = ax.get_title()
    cur_xlabel = ax.get_xlabel()
    cur_ylabel = ax.get_ylabel()

    def _fsize(getter):
        try:    return int(getter().get_size())
        except: return 12

    cur_title_fs  = _fsize(ax.title.get_fontproperties) if ax.get_title() else 12
    cur_xlabel_fs = _fsize(ax.xaxis.label.get_fontproperties)
    cur_ylabel_fs = _fsize(ax.yaxis.label.get_fontproperties)

    leg = ax.get_legend()
    cur_leg_fs = int(leg.get_texts()[0].get_fontsize()) if leg and leg.get_texts() else 8

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

    e_title,  e_title_fs  = _row(lf, "Title:",   0,
                                 cur_title,  cur_title_fs)
    e_xlabel, e_xlabel_fs = _row(lf, "X Label:", 1,
                                 cur_xlabel, cur_xlabel_fs)
    e_ylabel, e_ylabel_fs = _row(lf, "Y Label:", 2,
                                 cur_ylabel, cur_ylabel_fs)

    # ---- legend section ------------------------------------------------
    lf2 = tk.LabelFrame(win, text="Legend", padx=8, pady=6)
    lf2.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

    tk.Label(lf2, text="Font size:").grid(row=0, column=0, sticky="e", **pad)
    e_leg_fs = tk.Entry(lf2, width=4)
    e_leg_fs.insert(0, str(cur_leg_fs))
    e_leg_fs.grid(row=0, column=1, sticky="w", **pad)

    tk.Label(lf2, text="Position:").grid(row=0, column=2, sticky="e", padx=(20,2))
    leg_loc_var = tk.StringVar(value="upper left")
    leg_locs = ["upper left", "upper right", "lower left", "lower right",
                "upper center", "lower center", "center left", "center right",
                "center", "best"]
    tk.OptionMenu(lf2, leg_loc_var, *leg_locs).grid(row=0, column=3, padx=(0,10))

    # --- per-entry show/hide + rename ---
    # collect current legend handles and labels from the axes
    handles, labels = ax.get_legend_handles_labels()
    # filter out _nolegend_ entries
    entries = [(h, l) for h, l in zip(handles, labels) if not l.startswith('_')]

    entry_vars   = []   # (BooleanVar, StringVar) per entry
    entry_frame  = tk.Frame(lf2)
    entry_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6,0))

    if entries:
        tk.Label(entry_frame, text="Show", width=4).grid(row=0, column=0, padx=4)
        tk.Label(entry_frame, text="Label").grid(row=0, column=1, padx=4, sticky="w")

        for i, (h, l) in enumerate(entries):
            bv = tk.BooleanVar(value=True)
            sv = tk.StringVar(value=l)
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
        canvas.draw_idle()
        win.destroy()

    btn_row = tk.Frame(win)
    btn_row.grid(row=2, column=0, columnspan=2, pady=10)

    tk.Button(btn_row, text="Apply", command=_apply,
              bg="#4CAF50", fg="white",
              font=('Helvetica', 9, 'bold'),
              padx=20).pack(side="left", padx=5)

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

# --- Open buttons ---
tk.Button(options_frame, text="📁 Open Folder",
          command=open_folder, bg="#e1e1e1",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=(10, 2), pady=10)

tk.Button(options_frame, text="📄 Open File",
          command=open_file, bg="#e1e1e1",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=(2, 2), pady=10)

tk.Button(options_frame, text="🔄 Reload",
          command=load_data_action, bg="#e1e1e1",
          font=('Helvetica', 9, 'bold')).pack(side="left", padx=(2, 10), pady=10)

tk.Label(options_frame, text="|").pack(side="left", padx=5)

# --- Analysis dropdown + window ---
plot_type_var = tk.StringVar(root)
plot_type_var.set("Analysis")
tk.OptionMenu(options_frame, plot_type_var, "Z-Score PETH", "FFT").pack(side="left", padx=10)
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

f_zoom = zoom_factory(ax, base_scale=1.2)
fig.canvas.mpl_connect('scroll_event', f_zoom)

global rect_selector
rect_selector = RectangleSelector(
    ax, on_select, useblit=True, button=[1],
    minspanx=5, minspany=0.001,
    props=dict(facecolor='yellow', edgecolor='black', alpha=0.3, fill=True),
    interactive=True
)
rect_selector.set_active(True)

root.mainloop()