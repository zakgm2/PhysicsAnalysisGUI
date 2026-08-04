"""
PhysicsAnalysisGUI_qt.py
------------------------
Entry point for the PyQt6 version of the Physics Analysis GUI.

All the actual implementation lives in the physicsanalysis_qt/ package,
split by concern (loaders, plotting, interaction, analysis dialogs, UI
assembly) — see physicsanalysis_qt/__init__.py for the module map.

Do not run this from inside Spyder's console/Run button — Spyder's own
UI is built on PyQt5, and loading PyQt6 in the same process causes a
"DLL load failed while importing QtWidgets" crash. Launch it from a
plain terminal instead.
"""

import sys

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from physicsanalysis_qt.context import AppState
from physicsanalysis_qt.plotting import apply_theme_to_canvas
from physicsanalysis_qt.splash import SplashScreen, app_icon
from physicsanalysis_qt.theme import apply_theme
from physicsanalysis_qt.ui.main_window import build_main_window
from physicsanalysis_qt.update_check import UpdateCheckWorker, show_update_required_dialog


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())

    # Shown before any of the setup below so there's something on screen
    # immediately instead of a blank moment while the matplotlib/PyQtGraph
    # widgets and every dialog get built.
    splash = SplashScreen()
    splash.show()
    splash.pump()  # let the window manager actually paint it before the blocking setup below
    splash.set_status("Loading settings...")

    ctx = AppState(app)
    apply_theme(app, ctx.settings.get("theme", "light"))

    splash.set_status("Checking for updates...")
    update_worker = UpdateCheckWorker()
    update_result = {}
    update_worker.checked.connect(update_result.update)
    wait_loop = QEventLoop()
    update_worker.checked.connect(wait_loop.quit)
    QTimer.singleShot(5000, wait_loop.quit)  # don't hold up startup if GitHub is slow/unreachable
    update_worker.start()
    wait_loop.exec()

    # A PhysicsAnalysis update blocks launch entirely — the app never
    # gets built, just a dialog pointing at where to download the new
    # version. A PhysicsLibrary update (or "up to date", or nothing
    # found at all) is only ever a quiet splash status line below.
    if update_result.get("block"):
        splash.close()
        show_update_required_dialog(update_result["message"], update_result["url"])
        return
    if update_result.get("status"):
        splash.set_status(update_result["status"])
    ctx._update_check_worker = update_worker  # keeps it alive if it's still running past the timeout

    splash.set_status("Building interface...")
    build_main_window(ctx)
    apply_theme_to_canvas(ctx)

    splash.finish(ctx.win)
    ctx.win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
