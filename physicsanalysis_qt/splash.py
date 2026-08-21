"""
splash.py
---------
A tiny frameless loading screen — just the app logo itself, with a thin
white border tracing its own silhouette (no rectangular card around
it) — shown the instant the QApplication exists, before the heavier
one-time work (building the matplotlib/PyQtGraph widgets, wiring up
every dialog) has a chance to leave the user staring at nothing.

The window is clipped to the logo's own shape via a QRegion window mask
built from the pixmap's alpha channel (QPixmap.mask()), dilated a few
pixels outward (_dilate_region) so the white card backing shows through
as a deliberate border around the logo's contour — the old, always-
reliable-on-Windows "opaque region" technique, same as the update-
prompt card below uses for its rounded rect, just shaped to the logo
instead of a rectangle. Not real per-pixel alpha compositing
(WA_TranslucentBackground) — that was tried for a "just the logo, no
background at all" look and broke in the real windowed app ("just
flashes"): true alpha compositing on a Qt SplashScreen-type window is
known to be flaky on Windows (DWM sometimes never composites it). The
region mask has no such failure mode.

Also doubles as the update-available prompt: prompt_update() swaps this
same window's content from the plain logo to a message + Download
Update / Continue Anyway button row, resizing/re-masking in place,
instead of opening a second top-level dialog. That second-window
approach used to actually break: this splash is WindowStaysOnTopHint,
so a separate QMessageBox popped *behind* it — invisible, but still
modal and still waiting for a click nothing could reach, which is what
made update checks feel like they hung. One window, one z-order, no way
for that to happen again.

Usage (see run_qt.py):
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    ... do the slow setup ...
    if outdated:
        keep_going = splash.prompt_update(message, url)
        if not keep_going:
            return  # Download Update or the corner X was clicked; splash already closed itself
    splash.finish(main_window)
"""

import os
import time

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QEventLoop, QTimer, QRectF, QUrl
from PyQt6.QtGui import QPixmap, QIcon, QPainterPath, QRegion, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QApplication, QSizePolicy,
)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "icon.png")

_BG = "#ffffff"  # Continue Anyway button's own fill — stays light for contrast on a dark card
_LOGO_BG = "#000000"  # backs the logo page's silhouette mask
_BORDER = "#000000"  # Continue Anyway button's own border
_TEXT_COLOR = "#1a1a1a"  # Continue Anyway button's own (dark, on its light fill) text
_ACCENT = "#c22626"  # matches the logo's red — used for the Download Update button

_UPDATE_BG = "#2b2b2b"  # update-prompt card fill — dark gray
_UPDATE_BORDER = "#ffffff"  # update-prompt card border, for contrast against a dark fill
_UPDATE_TEXT_COLOR = "#f0f0f0"  # update-prompt message text, readable on the dark card

_LOGO_HEIGHT = 250  # rendered logo pixmap height
_SILHOUETTE_BORDER_PX = 1  # dilating this rounds off the logo's sharp spiky tips a little — see _dilate_region
_LOGO_SIZE = (_LOGO_HEIGHT + 2 * _SILHOUETTE_BORDER_PX, _LOGO_HEIGHT + 2 * _SILHOUETTE_BORDER_PX)
_CARD_MARGIN = 24  # padding between the card's border and its content — update page only
_UPDATE_SIZE = (420, 240)
_BORDER_RADIUS = 16
_BORDER_WIDTH = 3

# However fast startup actually is, the splash stays up at least this
# long — this app's setup (settings + widget construction) is fast
# enough that without a floor, finish() could close it before the pulse
# animation has even completed one cycle, or before a human eye has time
# to register the logo at all. Only applies to the plain-logo loading
# state; the update prompt stays up for as long as it takes to click one
# of its buttons.
_MIN_DISPLAY_MS = 3000


def app_icon():
    """QIcon for the taskbar/window icon — same logo file the splash uses,
    so both agree without a second asset to keep in sync."""
    return QIcon(LOGO_PATH) if os.path.exists(LOGO_PATH) else QIcon()


def _dilate_region(region, px):
    """Grows a QRegion outward by px in every direction (circular
    structuring element) — QRegion has no built-in dilate, so this
    unions the region with copies of itself translated to every offset
    within that radius. Used to turn the logo's own tight alpha-mask
    silhouette into a window a few pixels larger than the logo itself,
    so the white card backing shows through as a deliberate border
    tracing the logo's own contour, instead of just the logo's natural
    (barely-there) edge fringe. O(px^2) region unions — fine for the
    small border widths this is actually used with, not meant for large
    radii."""
    if px <= 0:
        return QRegion(region)
    dilated = QRegion(region)
    for dx in range(-px, px + 1):
        for dy in range(-px, px + 1):
            if dx * dx + dy * dy <= px * px:
                dilated = dilated.united(region.translated(dx, dy))
    return dilated


class SplashScreen(QWidget):
    def __init__(self):
        # SplashScreen window type: no frame, always on top, and (unlike
        # a plain frameless widget) excluded from the taskbar/alt-tab on
        # every platform that distinguishes it — exactly the "briefly
        # shown while real UI isn't ready yet" contract a loading screen
        # needs.
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
        self._shown_at = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QWidget(self)
        self.card.setObjectName("splashCard")
        outer.addWidget(self.card)

        self._card_layout = QVBoxLayout(self.card)
        self._card_layout.setContentsMargins(0, 0, 0, 0)

        # --- Page 1: plain logo, the default loading state ---
        self.logo_label = QLabel(self.card)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("background: transparent;")
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            self.logo_label.setPixmap(pixmap.scaledToHeight(
                _LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation))

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

        # --- Page 2: update-available message + action buttons, built
        # up front but not shown until prompt_update() swaps to it ---
        self.update_page = QWidget(self.card)
        update_layout = QVBoxLayout(self.update_page)
        update_layout.setContentsMargins(_CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN, _CARD_MARGIN)
        update_layout.setSpacing(16)

        self.update_message_label = QLabel(self.update_page)
        self.update_message_label.setWordWrap(True)
        self.update_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_message_label.setStyleSheet(f"color: {_UPDATE_TEXT_COLOR}; font-size: 10pt; background: transparent;")
        update_layout.addWidget(self.update_message_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_download = QPushButton("Download Update", self.update_page)
        self.btn_download.setStyleSheet(
            f"QPushButton {{ background-color: {_ACCENT}; color: white; padding: 6px 14px; "
            "border-radius: 6px; font-weight: 600; }}"
        )
        self.btn_continue = QPushButton("Continue Anyway", self.update_page)
        self.btn_continue.setStyleSheet(
            f"QPushButton {{ background-color: {_BG}; color: {_TEXT_COLOR}; padding: 6px 14px; "
            f"border-radius: 6px; border: 1px solid {_BORDER}; }}"
        )
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_continue)
        btn_row.addWidget(self.btn_download)
        btn_row.addStretch(1)
        update_layout.addLayout(btn_row)

        self.update_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.update_page.hide()

        # Top-right "just close the app" corner button — a child of the
        # card directly (not update_layout) since it's positioned by
        # absolute coordinates in the corner, not part of the normal
        # top-to-bottom message/buttons flow. Only shown/positioned
        # while the update page is (see _show_update_page/_show_logo_page).
        self.btn_close_x = QPushButton("✕", self.card)
        self.btn_close_x.setFixedSize(24, 24)
        self.btn_close_x.setToolTip("Close")
        self.btn_close_x.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_UPDATE_TEXT_COLOR}; border: none; "
            "font-size: 12pt; }}"
            f"QPushButton:hover {{ color: {_ACCENT}; }}"
        )
        self.btn_close_x.hide()

        self._card_layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self._card_layout.addWidget(self.update_page)

        self._show_logo_page()
        # Fully transparent until pump() confirms the window has actually
        # settled (native handle created, mask applied, first paint done)
        # — winId()-before-setMask alone cut down the startup flash but
        # didn't fully kill it; nothing is ever shown half-formed this
        # way, regardless of the exact remaining cause. windowOpacity is
        # a whole-window compositing property, universally supported
        # unlike the per-pixel WA_TranslucentBackground that broke
        # earlier — this isn't the same risk again.
        self.setWindowOpacity(0.0)

    def _show_logo_page(self):
        """Plain-logo state: window masked to the logo pixmap's own
        silhouette, dilated by _SILHOUETTE_BORDER_PX so the white card
        backing shows through as a deliberate border tracing the logo's
        own contour — not a rectangular card, just the logo and a ring
        around its actual shape."""
        self.update_page.hide()
        self.btn_close_x.hide()
        self.logo_label.show()
        self.card.setStyleSheet(f"background-color: {_LOGO_BG}; border: none;")
        self.setFixedSize(*_LOGO_SIZE)
        # Layout must actually run once before logo_label's position is
        # correct — the mask is built in window coordinates and has to
        # line up with wherever AlignCenter ends up placing the label.
        QApplication.processEvents()
        self.winId()  # see _show_update_page's comment on why this precedes setMask
        pixmap = self.logo_label.pixmap()
        if pixmap is not None and not pixmap.isNull():
            region = QRegion(pixmap.mask())
            region.translate(self.logo_label.x(), self.logo_label.y())
            self.setMask(_dilate_region(region, _SILHOUETTE_BORDER_PX))
        else:
            self.clearMask()
        self._center_on_screen()

    def _show_update_page(self):
        """Update-prompt state: opaque white card with a black border,
        masked to a rounded rect — this page has real text/buttons on it
        that need a solid, legible rectangular background under them,
        unlike the logo-silhouette mask the plain-logo state uses."""
        self.logo_label.hide()
        self.update_page.show()
        self.setFixedSize(*_UPDATE_SIZE)
        self.btn_close_x.move(_UPDATE_SIZE[0] - self.btn_close_x.width() - 6, 6)
        self.btn_close_x.show()
        self.btn_close_x.raise_()
        # Forces the native window handle to exist before setMask() below
        # — setMask() on a widget with no native window yet only takes
        # full effect once one gets created (typically on first show()),
        # which showed up as a one-frame flash of the full square window
        # before the mask "caught up" and clipped it down.
        self.winId()
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), _BORDER_RADIUS, _BORDER_RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        self.card.setStyleSheet(f"""
            #splashCard {{
                background-color: {_UPDATE_BG};
                border-radius: {_BORDER_RADIUS}px;
                border: {_BORDER_WIDTH}px solid {_UPDATE_BORDER};
            }}
        """)
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
        alive for the full duration.

        Also reveals the window at the end (windowOpacity 0 -> 1) —
        __init__ leaves it fully transparent specifically so this is the
        first moment anything becomes visible, once the wait above has
        given the window manager time to actually finish creating/
        masking/painting it. A no-op if it's already visible (e.g. a
        later pump() call, such as the one in prompt_update())."""
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
        self.setWindowOpacity(1.0)

    def prompt_update(self, message, url):
        """Swaps this window from the plain logo to the update-available
        message + buttons, in place — no second window, so there's no
        way for it to end up stuck behind this one (WindowStaysOnTopHint
        means a separate QMessageBox here would open *behind* the
        splash, unreachable — that's what made update checks feel hung).

        Blocks (via a nested event loop, same pattern as finish()) until
        one of three things is clicked. "Download Update" opens the
        release page and closes this splash the same way finish() would.
        The corner "✕" also closes it, but skips opening anything — for
        someone who just wants out, not an update and not this version
        either. Either way the caller should exit right after, same as
        if the app had launched and then closed normally. "Continue
        Anyway" swaps back to the logo page and returns control to the
        caller, which should carry on with a normal launch.

        Returns True for "continue with the current version", False for
        "not continuing — download was opened, or the user just closed
        it; either way the caller should exit"."""
        self.update_message_label.setText(message)
        self._show_update_page()
        self.pump()

        result = {}

        def _choose(outcome):
            result["outcome"] = outcome
            loop.quit()

        self.btn_continue.clicked.connect(lambda: _choose("continue"))
        self.btn_download.clicked.connect(lambda: _choose("download"))
        self.btn_close_x.clicked.connect(lambda: _choose("quit"))

        loop = QEventLoop()
        loop.exec()

        self.btn_continue.clicked.disconnect()
        self.btn_download.clicked.disconnect()
        self.btn_close_x.clicked.disconnect()

        if result["outcome"] == "continue":
            self._show_logo_page()
            return True

        if result["outcome"] == "download":
            QDesktopServices.openUrl(QUrl(url))
        self._pulse.stop()
        self.close()
        return False

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
