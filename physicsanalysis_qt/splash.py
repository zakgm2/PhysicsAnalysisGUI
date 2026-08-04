"""
splash.py
---------
A Discord-style loading screen: a small frameless, rounded dark card with
the app logo (pulsing gently) and a status line, shown the instant the
QApplication exists — before the heavier one-time work (building the
matplotlib/PyQtGraph widgets, wiring up every dialog) has a chance to
leave the user staring at nothing.

Usage (see run_qt.py):
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    splash.set_status("Loading interface...")
    ... do the slow setup ...
    splash.finish(main_window)
"""

import os
import time

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QEventLoop, QTimer, QRectF
from PyQt6.QtGui import QPixmap, QIcon, QPainterPath, QRegion
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect, QApplication,
)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "icon.png")

_CARD_BG = "#1e1e1e"
_TEXT_COLOR = "#e8e8e8"
_STATUS_COLOR = "#9a9a9a"
_ACCENT = "#c22626"  # matches the logo's red

# However fast startup actually is, the splash stays up at least this
# long — this app's setup (settings + widget construction) is fast
# enough that without a floor, finish() could close it before the pulse
# animation has even completed one cycle, or before a human eye has time
# to register the logo at all.
_MIN_DISPLAY_MS = 3000


def app_icon():
    """QIcon for the taskbar/window icon — same logo file the splash uses,
    so both agree without a second asset to keep in sync."""
    return QIcon(LOGO_PATH) if os.path.exists(LOGO_PATH) else QIcon()


class SplashScreen(QWidget):
    def __init__(self):
        # SplashScreen window type: no frame, always on top, and (unlike
        # a plain frameless widget) excluded from the taskbar/alt-tab on
        # every platform that distinguishes it — exactly the "briefly
        # shown while real UI isn't ready yet" contract a loading screen
        # needs.
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(420, 300)
        # Rounded corners via a window mask rather than
        # WA_TranslucentBackground: real per-pixel alpha compositing on a
        # SplashScreen-flagged window is flaky on Windows (DWM sometimes
        # never composites it, leaving only a bare outline with nothing
        # painted inside) — a mask just clips the window to a shape using
        # the old, always-supported opaque-region technique, no
        # compositing required.
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 18, 18)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        self._shown_at = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget(self)
        card.setObjectName("splashCard")
        card.setStyleSheet(f"""
            #splashCard {{
                background-color: {_CARD_BG};
                border-radius: 18px;
                border: 1px solid #3a3a3a;
            }}
        """)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 36, 32, 28)
        layout.setSpacing(4)
        layout.addStretch(1)

        self.logo_label = QLabel(card)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            self.logo_label.setPixmap(pixmap.scaledToHeight(
                120, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Gentle opacity pulse on the logo — the one bit of motion that
        # reads as "still working" on a screen with no real progress bar
        # (loading here is a fixed handful of setup calls, not something
        # with a meaningful percentage to report).
        self._opacity_effect = QGraphicsOpacityEffect(self.logo_label)
        self.logo_label.setGraphicsEffect(self._opacity_effect)
        self._pulse = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._pulse.setStartValue(1.0)
        self._pulse.setKeyValueAt(0.5, 0.55)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(1600)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse.setLoopCount(-1)
        self._pulse.start()

        layout.addSpacing(18)

        title = QLabel("Physics Analysis GUI", card)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {_TEXT_COLOR}; font-size: 15pt; font-weight: 600; "
                             "background: transparent;")
        layout.addWidget(title)

        self.status_label = QLabel("Starting...", card)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {_STATUS_COLOR}; font-size: 9pt; "
                                         "background: transparent;")
        layout.addWidget(self.status_label)

        layout.addStretch(1)

        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(QPoint(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        ))

    def showEvent(self, event):
        super().showEvent(event)
        if self._shown_at is None:
            self._shown_at = time.monotonic()

    def pump(self, ms=50):
        """Spins a nested event loop for a short, fixed stretch so the
        window manager gets a real chance to composite this window on
        screen. Call once right after show(), before any blocking setup
        work starts — a single processEvents() call only drains whatever
        is already queued at that instant, which on some Windows
        compositor timings runs before the first paint has actually made
        it to the screen; that made the splash's entire on-screen time
        equal to however long the following blocking call took, which
        reads as "flashes instantly" even though the widget itself was
        alive for the full duration."""
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def set_status(self, text):
        """Updates the status line and forces an immediate repaint —
        every caller is about to run a blocking setup step on the same
        thread, so without this the label would just queue the text
        change and never actually draw it until that step finishes."""
        self.status_label.setText(text)
        QApplication.processEvents()

    def finish(self, main_window):
        """Closes the splash once the real window is ready to take over.
        Named to match QSplashScreen's own finish() for anyone used to
        that API, even though this isn't a QSplashScreen subclass (we
        need a custom widget layout for the card/pulse, which
        QSplashScreen's single-pixmap-plus-message model can't do).

        Tops up to _MIN_DISPLAY_MS first if setup finished faster than
        that. Waits via a nested QEventLoop quit by a QTimer rather than
        a manual processEvents()+sleep() poll loop — the manual loop only
        processes whatever's already queued each iteration, which isn't
        a reliable way to keep a window actually composited on screen;
        exec()'ing a real (nested) event loop is what Qt/the OS expect
        and is what keeps the pulse animation and the window's own paint
        events flowing correctly for the whole wait."""
        if self._shown_at is not None:
            remaining_ms = _MIN_DISPLAY_MS - (time.monotonic() - self._shown_at) * 1000
            if remaining_ms > 0:
                loop = QEventLoop()
                QTimer.singleShot(int(remaining_ms), loop.quit)
                loop.exec()
        self._pulse.stop()
        self.close()
