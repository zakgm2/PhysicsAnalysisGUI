"""
update_check.py
-----------------
Checks GitHub for a newer version of PhysicsAnalysis and PhysicsLibrary
than what's currently running. Neither project reliably uses GitHub
Releases (PhysicsLibrary currently has none at all), so "latest version"
prefers the tag of the repo's latest published Release when one exists,
and falls back to the version string committed in pyproject.toml on the
default branch (fetched straight from raw.githubusercontent.com) when it
doesn't — covering a project whether or not its owner bothers publishing
formal releases.

A PhysicsAnalysis update blocks startup entirely (see
show_update_required_dialog, called from run_qt.py/.pyw before the main
window gets built) — running an old copy of the app itself isn't
something to just note and move past. A PhysicsLibrary update is only
ever a quiet splash status line: it's developed locally alongside this
app, so local-vs-GitHub drift is expected mid-work, not something that
should block launching the app that depends on it.

The GitHub calls run on a background QThread so the splash's pulse
animation and event loop stay responsive while they're in flight.
"""

import json
import re
import urllib.error
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox
from packaging.version import Version

_TIMEOUT_S = 4

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _parse_version(pyproject_text):
    match = _VERSION_RE.search(pyproject_text)
    return match.group(1) if match else None


def _local_version(name):
    """Reads the version out of a package's own pyproject.toml, found
    relative to its installed location — works the same whether that
    package is this app itself or an editable-installed dependency like
    PhysicsLibrary, and always reflects the actual source on disk rather
    than possibly-stale install metadata."""
    import importlib
    import os

    module = importlib.import_module(name)
    pkg_dir = os.path.dirname(os.path.abspath(module.__file__))
    pyproject_path = os.path.join(os.path.dirname(pkg_dir), "pyproject.toml")
    with open(pyproject_path, "r", encoding="utf-8") as f:
        return _parse_version(f.read())


def _remote_version(repo):
    """(version, url) for the latest published Release if one exists —
    url points straight at that release page — else the version
    committed in pyproject.toml on the default branch, with url falling
    back to the repo's own page."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"User-Agent": "PhysicsAnalysis-update-check"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
            return data["tag_name"].lstrip("v"), data["html_url"]
    except urllib.error.HTTPError as e:
        if e.code != 404:  # 404 = no releases published, the expected fallback case
            raise

    req = urllib.request.Request(
        f"https://raw.githubusercontent.com/{repo}/main/pyproject.toml",
        headers={"User-Agent": "PhysicsAnalysis-update-check"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        return _parse_version(resp.read().decode()), f"https://github.com/{repo}"


# (display name, importable package name, GitHub "owner/repo")
_PROJECTS = [
    ("PhysicsAnalysis", "physicsanalysis_qt", "zakgm2/PhysicsAnalysis"),
    ("PhysicsLibrary", "PhysicsLibrary", "zakgm2/PhysicsLibrary"),
]


class UpdateCheckWorker(QThread):
    """Emits one dict once both checks settle:
        {"block": True, "message": str, "url": str}
            — PhysicsAnalysis itself is outdated; caller should refuse
              to launch and point the user at url.
        {"block": False, "status": str}
            — nothing blocking. status is a splash status line: "Up to
              date", "PhysicsLibrary update available: vX.Y.Z", or ""
              if every check failed (offline, GitHub unreachable, a
              missing/malformed pyproject.toml) — none of those are the
              user's fault or actionable from a splash screen, so
              they're silent rather than shown as an error on every
              single launch."""
    checked = pyqtSignal(dict)

    def run(self):
        results = {}
        for display_name, package_name, repo in _PROJECTS:
            try:
                local = Version(_local_version(package_name))
                remote_str, url = _remote_version(repo)
                remote = Version(remote_str)
            except Exception:
                continue
            results[display_name] = {
                "outdated": remote > local, "local": local, "remote": remote, "url": url,
            }

        analysis = results.get("PhysicsAnalysis")
        if analysis and analysis["outdated"]:
            self.checked.emit({
                "block": True,
                "message": (f"A newer version of Physics Analysis GUI is available "
                            f"(v{analysis['remote']} — you have v{analysis['local']})."),
                "url": analysis["url"],
            })
            return

        library = results.get("PhysicsLibrary")
        if library and library["outdated"]:
            status = f"PhysicsLibrary update available: v{library['remote']}"
        elif results:
            status = "Up to date"
        else:
            status = ""
        self.checked.emit({"block": False, "status": status})


def show_update_required_dialog(message, url):
    """Blocking dialog telling the user PhysicsAnalysis itself is out of
    date, with a button to open the download link — used to refuse
    launching the app entirely rather than just noting it and moving on,
    since running a stale copy of the app itself isn't something to
    quietly proceed past."""
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Update Available")
    box.setText(f"{message}\n\nPlease download the latest version here:\n{url}")
    open_btn = box.addButton("Open Download Page", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is open_btn:
        QDesktopServices.openUrl(QUrl(url))
