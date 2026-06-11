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



#####################        
# ---  Globals  --- #
#####################

show_corrected = True
folder_path    = None
current_data   = None
cache          = None       # Always initialized — prevents crash before first load
is_dragging    = False
press_x, press_y = None, None
  
root = tk.Tk()
root.title("Physics Analysis - " + str(folder_path))

def show_window_toast(message, duration=2500):
    """
    Displays a non-blocking toast notification in the bottom-right corner of the GUI.

    This function creates a temporary, borderless Tkinter window that provides
    lightweight user feedback without interrupting workflow (e.g., replacing modal popups).

    The toast automatically positions itself relative to the main application window
    and disappears after a specified duration.

    Parameters
    ----------
    message : str
        Text message displayed in the toast notification.
        Typically used for success, status updates, or soft warnings.

    duration : int, optional
        Time (in milliseconds) before the toast automatically closes.
        Default is 2500 ms (2.5 seconds).

    Behavior
    --------
    - Creates a topmost Tkinter Toplevel window
    - Removes window decorations (no title bar or buttons)
    - Positions itself at bottom-right of main window
    - Auto-destroys after timeout
    - Does not block user interaction

    Use Case
    --------
    Ideal for:
    - Success confirmations (e.g., "Export complete")
    - Background process updates
    - Non-critical user feedback

    Avoid using for:
    - Critical errors requiring user action
    - Input validation failures
    """
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    
    label = tk.Label(toast, text=message, bg="#333333", fg="white", 
                     padx=20, pady=10, font=("Helvetica", 10, "bold"))
    label.pack()

    root.update_idletasks()
    toast.update_idletasks()
    
    root_x = root.winfo_x()
    root_y = root.winfo_y()
    root_w = root.winfo_width()
    root_h = root.winfo_height()
    t_w    = toast.winfo_width()
    t_h    = toast.winfo_height()
    
    pos_x = root_x + root_w - t_w - 20
    pos_y = root_y + root_h - t_h - 20
    
    toast.geometry(f"+{pos_x}+{pos_y}")
    toast.after(duration, toast.destroy)
    
def on_select(eclick, erelease):
    """
    Handles rectangle selection (box zoom) on the main signal plot.

    This function is triggered by Matplotlib's RectangleSelector when the user
    drags a selection box over the signal plot. It interprets the selected
    region and updates the axis limits to zoom into that area.

    Parameters
    ----------
    eclick : matplotlib.backend_bases.MouseEvent
        Mouse press event defining the first corner of the selection box.

    erelease : matplotlib.backend_bases.MouseEvent
        Mouse release event defining the opposite corner of the selection box.
    """
    x1, y1 = eclick.xdata, eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata

    if None in [x1, x2, y1, y2]:
        return

    if abs(x1 - x2) < 0.1:
        return

    ax.set_xlim(min(x1, x2), max(x1, x2))
    ax.set_ylim(min(y1, y2), max(y1, y2))
    
    rect_selector.clear()
    canvas.draw_idle()
    show_window_toast("Zoomed to Selection")

def on_press(event):
    """
    Handles mouse press events on the main Matplotlib canvas.

    Parameters
    ----------
    event : matplotlib.backend_bases.MouseEvent
        Mouse event object.
    """
    global is_dragging, press_x, press_y
    
    if event.inaxes != ax: 
        return
    
    if event.button == 3: 
        is_dragging = True
        press_x, press_y = event.x, event.y

    elif event.dblclick and event.button == 1:
        if event.xdata is not None:
            analysis_type(event.xdata)
            
    if event.button == 2: 
        reset_zoom()
        
def on_motion(event):
    """
    Handles mouse movement events for interactive panning of the signal plot.

    Parameters
    ----------
    event : matplotlib.backend_bases.MouseEvent
        Mouse motion event.
    """
    global press_x, press_y
    
    if not is_dragging or event.inaxes != ax: 
        return
    if event.x is None or event.y is None: 
        return

    dx = event.x - press_x
    dy = event.y - press_y
    press_x, press_y = event.x, event.y

    cur_xlim = ax.get_xlim()
    cur_ylim = ax.get_ylim()
    bbox     = ax.get_window_extent()
    
    shift_x = (dx / bbox.width)  * (cur_xlim[1] - cur_xlim[0])
    shift_y = (dy / bbox.height) * (cur_ylim[1] - cur_ylim[0])

    ax.set_xlim(cur_xlim[0] - shift_x, cur_xlim[1] - shift_x)
    ax.set_ylim(cur_ylim[0] - shift_y, cur_ylim[1] - shift_y)

    canvas.draw_idle()
    
def on_release(event):
    """
    Handles mouse button release events for interactive panning.

    Parameters
    ----------
    event : matplotlib.backend_bases.MouseEvent
        Mouse release event.
    """
    global is_dragging
    is_dragging = False

def launch_zscore_peth(center_t):
    """
    Launches a peri-event time histogram (PETH) analysis window centered on a selected event time.

    Parameters
    ----------
    center_t : float
        Time (in seconds) of the event around which the peri-event analysis is centered.
    """
    if cache is None: return
    
    data_source  = cache['corr'] if show_corrected else cache['raw']
    clean_signal = pl.smooth_signal(data_source, cache['fs'])
    
    slice_x, z_seg = pl.get_zscore_slice(cache['x'], clean_signal, center_t, window=30)
    
    if z_seg is not None:
        z_binned = pl.bin_for_heatmap(z_seg)
        mode_str = "Corrected" if show_corrected else "Raw"

        pop = tk.Toplevel(root)
        pop.title(f"PETH Analysis ({mode_str}) - {center_t:.2f}s")
        
        fig_peth             = Figure(figsize=(8, 7), dpi=100)
        ax_heat, ax_line     = fig_peth.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [1, 1]})
        
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
        
        fig_peth.suptitle("Z-score Peth", fontsize=14, fontweight='bold')
        fig_peth.tight_layout(rect=[0, 0.05, 1, 0.95]) 
        
        canvas_peth = FigureCanvasTkAgg(fig_peth, master=pop)
        canvas_peth.get_tk_widget().pack(fill="both", expand=True)

        def save_peth_action():
            ts         = datetime.datetime.now().strftime("%H%M%S")
            default_fn = f"PETH_{mode_str}_{int(center_t)}s_{ts}.png"
            
            fpath = filedialog.asksaveasfilename(
                initialdir=os.path.dirname(folder_path) if folder_path else os.getcwd(),
                defaultextension=".png",
                filetypes=[
                    ("PNG Image (Standard)", "*.png"), 
                    ("PDF Document (Vector)", "*.pdf"), 
                    ("SVG Vector (Editable)", "*.svg")
                ],
                initialfile=default_fn,
                title="Export PETH Analysis"
            )

            if fpath:
                try:
                    fig_peth.savefig(fpath, dpi=300, bbox_inches='tight')
                    show_window_toast("✅ PETH Exported Successfully")
                except Exception as e:
                    show_error(f"Export Failed: {str(e)}")

        btn_frame = tk.Frame(pop)
        btn_frame.pack(side="bottom", fill="x", pady=10)
        
        tk.Button(btn_frame, text=f"💾 Export {mode_str} PETH", 
                  command=save_peth_action, bg="#2196F3", fg="white", 
                  font=('Helvetica', 10, 'bold'), padx=20).pack()
        
        show_window_toast(f"PETH Generated at {center_t:.1f}s")
        
def zoom_factory(ax, base_scale=1.2):
    """
    Creates a custom scroll-wheel zoom handler for a Matplotlib axis.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    base_scale : float, optional
    """
    def zoom_fun(event):
        if event.x is None or event.y is None: return
        
        bbox       = ax.get_window_extent()
        is_on_x    = event.y < bbox.ymin  
        is_on_y    = event.x < bbox.xmin  
        is_inside  = event.inaxes == ax      

        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            return

        cur_xlim, cur_ylim = ax.get_xlim(), ax.get_ylim()

        if is_on_x and not is_on_y:
            xdata     = event.xdata if event.xdata is not None else (cur_xlim[0] + cur_xlim[1]) / 2
            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            rel_x     = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
            ax.set_xlim([xdata - new_width * (1 - rel_x), xdata + new_width * rel_x])

        elif is_on_y and not is_on_x:
            ydata      = event.ydata if event.ydata is not None else (cur_ylim[0] + cur_ylim[1]) / 2
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

def show_error(msg):
    tk.messagebox.showerror("NeuroData Error", f"❌ {msg}")

def show_success(msg):
    show_window_toast(f"✅ {msg}")

def choose_folder():
    """
    Opens folder dialog via file_parser, updates the global folder_path,
    and refreshes the window title.
    """
    global folder_path
    path, name = pl.choose_file()
    if path is None:
        return  # User cancelled — do nothing
    folder_path = path
    root.title(f"NeuroData Interface - {name}")
    show_success(f"Linked to: {name}")


def load_data_action():
    """
    Detects the format of the selected folder, runs the appropriate loading
    pipeline, and stores results in the global cache.

    - TDT   → runs the full fiber photometry pipeline via process_tdt_folder,
              returns a dict (same shape as before so the rest of the GUI is untouched)
    - Oxysoft → loads via file_parser and adapts the Dataset into the same
                dict shape so simple_plot / PETH work without changes
    """
    global cache

    if folder_path is None:
        show_error("Please select a folder first!")
        return

    try:
        fmt = pl.detect_format(folder_path)

        if fmt == pl.DataFormat.TDT:
            cache = pl.process_tdt_folder(folder_path)

        elif fmt == pl.DataFormat.OXYSOFT:
            import numpy as np
            dataset = pl.load_dataset(folder_path, fmt)

            x = np.arange(dataset.num_samples) / dataset.sample_rate
            cache = {
                "x":       x,
                "raw":     dataset.signals[0] if dataset.signals is not None else np.array([]),
                "corr":    dataset.signals[0] if dataset.signals is not None else np.array([]),
                "dff":     dataset.signals[0] if dataset.signals is not None else np.array([]),
                "f0":      np.zeros(dataset.num_samples),
                "fs":      dataset.sample_rate,
                "store":   dataset.folder_name,
                "markers": [
                    {"time":  ev["sample"] / dataset.sample_rate,
                     "label": ev["label"],
                     "color": "black"}
                    for ev in dataset.events
                ],
            }

        else:
            show_error(
                "Unrecognised folder format.\n"
                "Expected a TDT tank (.Tbk/.tev/…) or an Oxysoft .txt export."
            )
            return

        msg = f"Loaded {cache['store']} ({cache['fs']:.1f} Hz)"
        show_success(msg)
        simple_plot()

    except Exception as e:
        show_error(f"Processing Failed: {str(e)}")


def load_data_set():
    """
    One-click entry point: opens folder dialog then immediately loads data.
    """
    choose_folder()
    if folder_path:
        load_data_action()

def _update_plot_with_notes(markers):
    """
    Overlays behavioral event markers onto the main signal plot.

    Parameters
    ----------
    markers : list of dict
        Each dict: {'time': float, 'label': str, 'color': str}
    """
    import matplotlib.transforms as transforms
    trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
    
    unique_labels = set()
    
    for m in markers:
        label_id = m['label'] if m['label'] not in unique_labels else "_nolegend_"
        unique_labels.add(m['label'])
        
        ax.axvline(x=m['time'], color=m['color'], linestyle='--', alpha=0.3, label=label_id)
        ax.text(m['time'], 0.98, f" {m['label']}", 
                transform=trans, rotation=90, va='top', clip_on=True,
                fontsize=8, color=m['color'], fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))

def simple_plot(draw_now=True):
    """
    Renders the main time-series signal plot in the GUI.

    Parameters
    ----------
    draw_now : bool, optional
    """
    if cache is None: return
    
    ax.clear()
    
    data_to_plot = cache['corr'] if show_corrected else cache['raw']
    label_text   = "Signal" 
    color_choice = "blue" if show_corrected else "gray"

    ax.axhline(0, color='black', linewidth=1.2, alpha=0.5, zorder=1)
    ax.axvline(0, color='black', linewidth=1.2, alpha=0.5, zorder=1)
    
    ax.plot(cache['x'], data_to_plot, color=color_choice, lw=1, alpha=0.8, label=label_text)
    
    _update_plot_with_notes(cache['markers'])
    
    ax.set_title(f"{label_text} - {cache['store']}", fontweight='bold', pad=15)
    ax.set_ylabel("Amplitude")
    ax.set_xlabel("Time (s)")
    
    if draw_now:
        canvas.draw()

def export_canvas_action():
    """
    Exports the current main visualization canvas to an external file.
    """
    if cache is None:
        show_error("No data loaded to export!")
        return

    timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    initial_name = f"{cache['store']}_Plot_{timestamp}.png"
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[
            ("PNG Image (Standard)", "*.png"), 
            ("PDF Document (Vector)", "*.pdf"), 
            ("SVG Vector (Editable)", "*.svg")
        ],
        initialfile=initial_name,
        title="Export Current View"
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
center_x = int(screen_width  / 2 - window_width  / 2)
center_y = int(screen_height / 2 - window_height / 2)
root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

options_frame = tk.LabelFrame(root, text="Controls & Analysis")
options_frame.pack(pady=10, padx=10, fill="x")

btn_choose = tk.Button(options_frame, text="1. Select & Load Folder", 
                       command=load_data_set, bg="#e1e1e1")
btn_choose.pack(side="left", padx=10, pady=10)

tk.Label(options_frame, text="|").pack(side="left", padx=5)

plot_type_var = tk.StringVar(root)
plot_type_var.set("Analysis")
plot_options = ["Z-Score PETH"]
dropdown = tk.OptionMenu(options_frame, plot_type_var, *plot_options)
dropdown.pack(side="left", padx=10)

def analysis_type(data):
    choice = plot_type_var.get()
    if choice == "Z-Score PETH":
        launch_zscore_peth(data)

def reset_zoom():
    if cache is None: return
    ax.clear()
    simple_plot()
    if 'rect_selector' in globals():
        rect_selector.ax = ax
        rect_selector.set_active(True)
    canvas.draw_idle()
        
btn_reset = tk.Button(options_frame, text="Reset Zoom", command=reset_zoom)
btn_reset.pack(side="left", padx=10)

btn_export = tk.Button(
    options_frame, text="Export View (PNG/PDF)", 
    command=export_canvas_action, 
    bg="#2196F3", fg="white", font=('Helvetica', 9, 'bold')
)
btn_export.pack(side="left", padx=10)

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
    ax, on_select, useblit=True,
    button=[1], minspanx=5, minspany=0.001,
    props=dict(facecolor='yellow', edgecolor='black', alpha=0.3, fill=True),
    interactive=True
)
rect_selector.set_active(True)

root.mainloop()