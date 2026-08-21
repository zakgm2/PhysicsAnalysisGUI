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

import vispy.app
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from physicsanalysis_qt.context import AppState
from physicsanalysis_qt.plotting import apply_theme_to_canvas
from physicsanalysis_qt.splash import SplashScreen, app_icon
from physicsanalysis_qt.theme import apply_theme
from physicsanalysis_qt.ui.main_window import build_main_window
from physicsanalysis_qt.update_check import UpdateCheckWorker


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    vispy.app.use_app("pyqt6")  # pin VisPy to reuse this QApplication, not create its own

    # Shown before any of the setup below so there's something on screen
    # immediately instead of a blank moment while the matplotlib/PyQtGraph
    # widgets and every dialog get built.
    splash = SplashScreen()
    splash.show()
    splash.pump()  # let the window manager actually paint it before the blocking setup below

    ctx = AppState(app)
    apply_theme(app, ctx.settings.get("theme", "light"))

    update_worker = UpdateCheckWorker()
    update_result = {}
    update_worker.checked.connect(update_result.update)
    wait_loop = QEventLoop()
    update_worker.checked.connect(wait_loop.quit)
    QTimer.singleShot(5000, wait_loop.quit)  # don't hold up startup if GitHub is slow/unreachable/no internet
    update_worker.start()
    wait_loop.exec()

    # An available PhysicsAnalysis update swaps the splash itself into
    # the message + Download Update / Continue Anyway prompt (see
    # splash.py's prompt_update) rather than opening a second dialog —
    # this window is WindowStaysOnTopHint, so a separate QMessageBox
    # would've opened *behind* it, unreachable. No internet, GitHub
    # down, or already up to date all land here as a no-op: update_result
    # only ever has "outdated" set to True after a real successful
    # comparison against a fetched remote version, never as a fallback
    # for a failed check — see UpdateCheckWorker's own docstring.
    if update_result.get("outdated"):
        if not splash.prompt_update(update_result["message"], update_result["url"]):
            return  # Download Update was clicked; prompt_update already closed the splash
    ctx._update_check_worker = update_worker  # keeps it alive if it's still running past the timeout

    build_main_window(ctx)
    apply_theme_to_canvas(ctx)

    splash.finish(ctx.win)
    ctx.win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
