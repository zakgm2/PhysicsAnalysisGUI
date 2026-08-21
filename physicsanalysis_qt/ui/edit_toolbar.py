"""
ui/edit_toolbar.py
---------------------
Left-side icon toolbar for tools that change how the loaded data looks
or gets analyzed WITHOUT touching the original raw data on disk (or, for
Splice, without mutating the original in-memory recording either) —
Rescale, Add Marker, Splice/Restore, Save Changes, Undo All Changes,
Measure Intervals, and anywhere else this grows. Small square icon
buttons (emoji glyphs, no external image assets needed) in a
fixed-width vertical strip, collapsible via a small arrow handle so it
doesn't have to stay in view.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QMessageBox, QMenu
from PyQt6.QtGui import QFont

from ..interaction import reset_zoom
from ..markers import toggle_marker_mode
from ..sidecar import save_markers, clear_json_saves
from ..analysis.splice import (
    restore_full_recording, is_spliced, save_splice, open_splice_manager, start_splice_flow,
)
from ..analysis.intervals import launch_intervals

_ICON_SIZE = 44
_HANDLE_WIDTH = 18


def _icon_button(glyph, tooltip):
    btn = QPushButton(glyph)
    btn.setFont(QFont("Segoe UI Emoji", 16))
    btn.setFixedSize(_ICON_SIZE, _ICON_SIZE)
    btn.setToolTip(tooltip)
    return btn


def _on_splice_clicked(ctx):
    # Always starts another splice — splices stack (e.g. removing more
    # than one artifact from the same recording) instead of each new one
    # restarting from the pristine original. Calls start_splice_flow
    # directly (rather than routing through plot_type_combo) so every
    # click reopens the mode picker — setCurrentText("Splice") only
    # fired the combo's changed signal the first time, since re-setting
    # a combo to the value it's already showing is a no-op change-wise.
    # Right-click this icon to review/remove what's already applied, or
    # restore everything.
    start_splice_flow(ctx)


def _on_splice_right_clicked(ctx, btn, pos):
    menu = QMenu(ctx.win)
    n = len(ctx._active_splices)
    act_manage = menu.addAction(f"Manage Splices… ({n} active)" if n else "No splices active")
    act_manage.setEnabled(n > 0)
    act_restore = menu.addAction("Restore Full Recording")
    act_restore.setEnabled(is_spliced(ctx))
    chosen = menu.exec(btn.mapToGlobal(pos))
    if chosen == act_manage:
        open_splice_manager(ctx)
    elif chosen == act_restore:
        restore_full_recording(ctx)


def _on_undo_all_clicked(ctx):
    from .toolbar import _reload_current

    if ctx.cache is None:
        return
    reply = QMessageBox.question(
        ctx.win, "Undo All Changes",
        "This discards every marker/splice change, including anything already "
        "saved via Save Changes — clears the JSON saves folder's contents (the "
        "folder itself stays) and re-reads the recording from disk. The original "
        "raw data file/folder is never touched by anything in this app. "
        "This can't be undone. Continue?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
        clear_json_saves(ctx)
        _reload_current(ctx)


def build_edit_toolbar(ctx):
    container = QWidget()
    container.setFixedWidth(_ICON_SIZE + 12)
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 8, 0, 8)
    outer.setSpacing(6)

    handle_row = QVBoxLayout()
    btn_handle = QPushButton("◂")
    btn_handle.setFixedSize(_HANDLE_WIDTH, _ICON_SIZE)
    btn_handle.setToolTip("Collapse/expand this toolbar")
    handle_row.addWidget(btn_handle)
    outer.addLayout(handle_row)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(6, 0, 6, 0)
    content_layout.setSpacing(6)

    btn_rescale = _icon_button(
        "⛶", "Rescale — fit the view to the full recording (was \"Reset Zoom\")")
    btn_rescale.clicked.connect(lambda: reset_zoom(ctx))
    content_layout.addWidget(btn_rescale)

    btn_intervals = _icon_button(
        "📏", "Measure Intervals — time between whatever markers are "
              "currently on the plot")
    btn_intervals.clicked.connect(lambda: launch_intervals(ctx))
    content_layout.addWidget(btn_intervals)

    # Add Marker — reuses the existing ctx.btn_add_marker contract:
    # toggle_marker_mode() (markers.py) sets its text/style directly to
    # reflect placement-mode state (e.g. "Placing 'X'…"), unchanged by
    # moving the button here — it'll just show that text in a small
    # square instead of a full-width button.
    ctx.btn_add_marker = _icon_button(
        "📍", "Add Marker — click the plot to place markers (non-destructive, "
              "stored separately from the raw recording)")
    ctx.btn_add_marker.clicked.connect(lambda: toggle_marker_mode(ctx))
    content_layout.addWidget(ctx.btn_add_marker)

    btn_splice = _icon_button(
        "✂", "Splice Recording — work on a copy of a chosen time range, "
             "original stays untouched. Splices stack; right-click to "
             "review/remove one or restore everything.")
    btn_splice.clicked.connect(lambda: _on_splice_clicked(ctx))
    btn_splice.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    btn_splice.customContextMenuRequested.connect(
        lambda pos: _on_splice_right_clicked(ctx, btn_splice, pos))
    content_layout.addWidget(btn_splice)

    btn_save_changes = _icon_button(
        "💾", "Save Changes — writes current markers and any active splice to "
              "JSON files next to the recording, doesn't touch the original raw data")
    btn_save_changes.clicked.connect(lambda: (save_markers(ctx), save_splice(ctx)))
    content_layout.addWidget(btn_save_changes)

    btn_undo_all = _icon_button(
        "↺", "Undo All Changes — discards marker/splice changes since the last "
             "load or save and re-reads the file fresh (asks to confirm first)")
    btn_undo_all.clicked.connect(lambda: _on_undo_all_clicked(ctx))
    content_layout.addWidget(btn_undo_all)

    content_layout.addStretch(1)
    outer.addWidget(content, stretch=1)

    state = {"expanded": True}

    def _toggle():
        state["expanded"] = not state["expanded"]
        content.setVisible(state["expanded"])
        container.setFixedWidth(_ICON_SIZE + 12 if state["expanded"] else _HANDLE_WIDTH)
        btn_handle.setText("◂" if state["expanded"] else "▸")

    btn_handle.clicked.connect(_toggle)

    return container
