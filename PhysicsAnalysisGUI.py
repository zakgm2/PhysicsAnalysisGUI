import sys
sys.path.insert(0, r'C:\Users\zakgm\anaconda3\Lib\site-packages')

import tkinter as tk
from tkinter import filedialog
import os
import PhysicsLibrary as pl
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import RectangleSelector
import datetime
import numpy as np


#####################        
# ---  Globals  --- #
#####################

show_corrected    = True
selected_path     = None   # can be a file OR a folder
cache             = None
is_dragging       = False
press_x, press_y  = None, None

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
# File / Folder selection
# ---------------------------------------------------------------------------

def open_folder():
    """Opens a folder dialog — used for TDT tanks."""
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
    """Opens a file dialog — used for Oxysoft .txt, CSV, or any single file."""
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
        # If a single file was picked, work in its parent folder
        # but pass the file path directly to the loader
        if os.path.isfile(selected_path):
            _load_single_file(selected_path)
        else:
            _load_folder(selected_path)

        msg = f"Loaded {cache['store']} ({cache['fs']:.1f} Hz)"
        show_success(msg)
        simple_plot()

    except Exception as e:
        show_error(f"Processing Failed: {str(e)}")


def _load_folder(folder_path):
    """Handle folder-based formats (TDT)."""
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
    """Handle single-file formats (Oxysoft .txt, future CSV, etc.)."""
    global cache

    # Wrap the single file in a temp folder context for the parser
    # by passing its parent dir and letting detect_format find it
    parent = os.path.dirname(file_path)
    fmt    = pl.detect_format_file(file_path)   # new helper — detects from a single file

    if fmt == pl.DataFormat.OXYSOFT:
        dataset = pl.load_dataset_file(file_path)   # new helper — loads a single file

        n_ch = dataset.metadata.get("n_channels", dataset.num_channels // 2)
        x    = np.arange(dataset.num_samples) / dataset.sample_rate
        o2hb = dataset.signals[:n_ch]
        hhb  = dataset.signals[n_ch:]

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
    if event.button == 3:
        is_dragging = True
        press_x, press_y = event.x, event.y
    elif event.dblclick and event.button == 1 and event.xdata is not None:
        analysis_type(event.xdata)
    if event.button == 2:
        reset_zoom()

def on_motion(event):
    global press_x, press_y
    if not is_dragging or event.inaxes != ax:
        return
    if event.x is None or event.y is None:
        return
    dx, dy    = event.x - press_x, event.y - press_y
    press_x, press_y = event.x, event.y
    cur_xlim  = ax.get_xlim()
    cur_ylim  = ax.get_ylim()
    bbox      = ax.get_window_extent()
    shift_x   = (dx / bbox.width)  * (cur_xlim[1] - cur_xlim[0])
    shift_y   = (dy / bbox.height) * (cur_ylim[1] - cur_ylim[0])
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
        bbox      = ax.get_window_extent()
        is_on_x   = event.y < bbox.ymin
        is_on_y   = event.x < bbox.xmin
        is_inside = event.inaxes == ax
        scale_factor = 1 / base_scale if event.button == 'up' else base_scale if event.button == 'down' else None
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
        ts         = datetime.datetime.now().strftime("%H%M%S")
        default_fn = f"PETH_{mode_str}_{int(center_t)}s_{ts}.png"
        fpath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
            initialfile=default_fn, title="Export PETH"
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

def analysis_type(data):
    choice = plot_type_var.get()
    if choice == "Z-Score PETH":
        launch_zscore_peth(data)


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
        ax.axvline(x=m['time'], color=m['color'], linestyle='--', alpha=0.3, label=label_id)
        ax.text(m['time'], 0.98, f" {m['label']}", transform=trans,
                rotation=90, va='top', clip_on=True, fontsize=8,
                color=m['color'], fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))

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

options_frame = tk.LabelFrame(root, text="Controls & Analysis")
options_frame.pack(pady=10, padx=10, fill="x")

# --- Open buttons ---
btn_open_folder = tk.Button(options_frame, text="📁 Open Folder",
                            command=open_folder, bg="#e1e1e1",
                            font=('Helvetica', 9, 'bold'))
btn_open_folder.pack(side="left", padx=(10, 2), pady=10)

btn_open_file = tk.Button(options_frame, text="📄 Open File",
                          command=open_file, bg="#e1e1e1",
                          font=('Helvetica', 9, 'bold'))
btn_open_file.pack(side="left", padx=(2, 10), pady=10)

tk.Label(options_frame, text="|").pack(side="left", padx=5)

# --- Analysis dropdown ---
plot_type_var = tk.StringVar(root)
plot_type_var.set("Analysis")
tk.OptionMenu(options_frame, plot_type_var, "Z-Score PETH").pack(side="left", padx=10)

tk.Label(options_frame, text="|").pack(side="left", padx=5)

# --- Zoom reset + export ---
tk.Button(options_frame, text="Reset Zoom",
          command=reset_zoom).pack(side="left", padx=10)

tk.Button(options_frame, text="Export View (PNG/PDF)",
          command=export_canvas_action,
          bg="#2196F3", fg="white",
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