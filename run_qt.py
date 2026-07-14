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

from PyQt6.QtWidgets import QApplication

from physicsanalysis_qt.context import AppState
from physicsanalysis_qt.plotting import apply_theme_to_canvas
from physicsanalysis_qt.theme import apply_theme
from physicsanalysis_qt.ui.main_window import build_main_window


def main():
    app = QApplication(sys.argv)
    ctx = AppState(app)
    apply_theme(app, ctx.settings.get("theme", "light"))
    build_main_window(ctx)
    apply_theme_to_canvas(ctx)
    ctx.win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
