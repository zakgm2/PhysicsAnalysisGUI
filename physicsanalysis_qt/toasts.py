"""
toasts.py
---------
Small on-screen notifications: a self-dismissing toast widget, plus
thin wrappers around QMessageBox for errors/success dialogs.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox


def show_window_toast(ctx, message, duration=2500):
    toast = QWidget(ctx.win, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
    toast.setStyleSheet(
        "background-color: #333; border-radius: 6px; padding: 8px;"
    )
    layout = QVBoxLayout(toast)
    label = QLabel(message)
    label.setStyleSheet("color: white; font-weight: bold;")
    layout.addWidget(label)
    toast.adjustSize()

    parent_geom = ctx.win.geometry()
    x = parent_geom.x() + parent_geom.width() - toast.width() - 30
    y = parent_geom.y() + parent_geom.height() - toast.height() - 60
    toast.move(x, y)
    toast.show()
    QTimer.singleShot(duration, toast.close)


def show_error(ctx, msg):
    QMessageBox.critical(ctx.win, "Error", msg)


def show_success(ctx, msg):
    QMessageBox.information(ctx.win, "Success", msg)
