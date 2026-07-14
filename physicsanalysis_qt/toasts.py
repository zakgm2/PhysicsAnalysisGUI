"""
toasts.py
---------
Small on-screen notifications: a self-dismissing toast widget, plus
thin wrappers around QMessageBox for errors/success dialogs.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox


def show_window_toast(ctx, message, duration=2500):
    # A plain child widget (no top-level window flags) so it's positioned
    # in the window's own coordinate space and moves/stacks with it,
    # instead of a separate top-level window pinned to a screen position.
    toast = QWidget(ctx.win)
    toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    toast.setStyleSheet(
        "background-color: #333; border-radius: 6px; padding: 8px;"
    )
    layout = QVBoxLayout(toast)
    label = QLabel(message)
    label.setStyleSheet("color: white; font-weight: bold;")
    layout.addWidget(label)
    toast.adjustSize()

    x = ctx.win.width() - toast.width() - 30
    y = ctx.win.height() - toast.height() - 60
    toast.move(x, y)
    toast.show()
    toast.raise_()
    QTimer.singleShot(duration, toast.close)


def show_error(ctx, msg):
    QMessageBox.critical(ctx.win, "Error", msg)


def show_success(ctx, msg):
    QMessageBox.information(ctx.win, "Success", msg)
