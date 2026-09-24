"""
toasts.py
---------
Small on-screen notifications: a self-dismissing toast widget in the
window's bottom-RIGHT corner, plus thin wrappers around QMessageBox for
errors/success dialogs.

Only ONE toast is ever on screen — a new one replaces whatever is showing
(and cancels its dismiss timer) instead of piling up on top of it.

The pinned panel (show_pinned_panel) is separate: a message and a button in
the bottom-LEFT corner that stays until hide_pinned_panel(). Toasts never
replace or hide it, and it never times out. The Analysis picker uses it to
keep a "Done" button on screen for as long as an analysis tool is armed.
"""

from PyQt6.QtCore import Qt, QTimer, QObject, QEvent
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox

_MARGIN_RIGHT = 30
_MARGIN_LEFT = 76    # clears the Tools sidebar down the window's left edge
_MARGIN_BOTTOM = 60  # clears the status bar


class _Repositioner(QObject):
    """Keeps the toast and the pinned panel in their corners across window
    resizes (the panel can outlive many of them)."""

    def __init__(self, ctx):
        super().__init__(ctx.win)
        self._ctx = ctx

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            _place_toast(self._ctx)
            _place_panel(self._ctx)
        return False


def _ensure_repositioner(ctx):
    if ctx._toast_repositioner is None:
        ctx._toast_repositioner = _Repositioner(ctx)
        ctx.win.installEventFilter(ctx._toast_repositioner)


def _place_toast(ctx):
    toast = ctx._toast
    if toast is None:
        return
    toast.adjustSize()
    toast.move(ctx.win.width() - toast.width() - _MARGIN_RIGHT,
               ctx.win.height() - toast.height() - _MARGIN_BOTTOM)
    toast.raise_()


def _place_panel(ctx):
    panel = ctx._pinned_panel
    if panel is None:
        return
    panel.adjustSize()
    panel.move(_MARGIN_LEFT, ctx.win.height() - panel.height() - _MARGIN_BOTTOM)
    panel.raise_()


def _close_toast(ctx):
    """Dismiss the toast that's showing, and its pending timer."""
    if ctx._toast_timer is not None:
        ctx._toast_timer.stop()
        ctx._toast_timer = None
    if ctx._toast is not None:
        ctx._toast.hide()
        ctx._toast.deleteLater()
        ctx._toast = None


def show_window_toast(ctx, message, duration=2500):
    _close_toast(ctx)  # one at a time: a new toast replaces the current one
    # A plain child widget (no top-level window flags) so it's positioned
    # in the window's own coordinate space and moves/stacks with it,
    # instead of a separate top-level window pinned to a screen position.
    toast = QWidget(ctx.win)
    toast.setObjectName("windowToast")
    # Purely informational, so clicks pass straight through to the plot.
    toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    toast.setStyleSheet(
        "background-color: #333; border-radius: 6px; padding: 8px;"
    )
    layout = QVBoxLayout(toast)
    label = QLabel(message)
    label.setStyleSheet("color: white; font-weight: bold;")
    layout.addWidget(label)

    _ensure_repositioner(ctx)
    ctx._toast = toast
    _place_toast(ctx)
    toast.show()
    toast.raise_()

    timer = QTimer(toast)  # child of the toast, so it can never outlive it
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: _close_toast(ctx) if ctx._toast is toast else None)
    ctx._toast_timer = timer
    timer.start(duration)


def show_pinned_panel(ctx, message, button_text, on_click):
    """Pin a message + button in the window's bottom-left corner until
    hide_pinned_panel(). Replaces an earlier pinned panel; toasts don't
    affect it."""
    hide_pinned_panel(ctx)
    panel = QWidget(ctx.win)
    panel.setObjectName("pinnedPanel")
    panel.setStyleSheet("#pinnedPanel { background-color: #333; border-radius: 6px; padding: 8px; }")
    layout = QVBoxLayout(panel)
    label = QLabel(message)
    label.setStyleSheet("color: white; font-weight: bold;")
    layout.addWidget(label)
    button = QPushButton(button_text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton { background-color: #FFD54F; color: black; font-weight: bold; "
        "border: none; border-radius: 4px; padding: 5px 16px; }"
        "QPushButton:hover { background-color: #FFE082; }")
    button.clicked.connect(on_click)
    layout.addWidget(button)  # bottom of the panel

    _ensure_repositioner(ctx)
    ctx._pinned_panel = panel
    _place_panel(ctx)
    panel.show()
    panel.raise_()


def hide_pinned_panel(ctx):
    if ctx._pinned_panel is not None:
        ctx._pinned_panel.hide()
        ctx._pinned_panel.deleteLater()
        ctx._pinned_panel = None


def show_error(ctx, msg):
    QMessageBox.critical(ctx.win, "Error", msg)


def show_success(ctx, msg):
    QMessageBox.information(ctx.win, "Success", msg)
