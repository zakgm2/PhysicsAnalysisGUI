"""
update_check.py
-----------------
Checks GitHub for a PhysicsAnalysis release newer than the one currently
running, shown as a status line on the splash screen. Only checks this
app's own repo — not PhysicsLibrary, which is developed locally here and
would never match whatever's published on PyPI/GitHub during active work
on it.

The GitHub call runs on a background QThread so the splash's pulse
animation and event loop stay responsive while it's in flight.
"""

import json
import os
import re
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal
from packaging.version import Version

_REPO = "zakgm2/PhysicsAnalysis"
_RELEASES_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"
_TIMEOUT_S = 4

_PYPROJECT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml")


def local_version():
    with open(_PYPROJECT_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    return re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE).group(1)


class UpdateCheckWorker(QThread):
    """Emits a short status string once the check settles: "Up to
    date", "Update available: vX.Y.Z", or an empty string. Empty covers
    every case with nothing useful to say — no releases published yet
    (404, true right now since this repo has none), offline, GitHub
    unreachable, a malformed tag — none of those are the user's fault or
    actionable from a splash screen, so they're silent rather than shown
    as an error on every single launch."""
    checked = pyqtSignal(str)

    def run(self):
        try:
            current = Version(local_version())
            req = urllib.request.Request(
                _RELEASES_URL, headers={"User-Agent": "PhysicsAnalysis-update-check"})
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                data = json.loads(resp.read())
            latest = Version(data["tag_name"].lstrip("v"))
            if latest > current:
                self.checked.emit(f"Update available: v{latest}")
            else:
                self.checked.emit("Up to date")
        except Exception:
            self.checked.emit("")
