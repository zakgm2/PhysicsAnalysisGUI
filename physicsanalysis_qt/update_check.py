"""
update_check.py
-----------------
Two entirely different update paths, gated on whether this is a
packaged/frozen build (sys.frozen — see is_frozen()) or a dev/editable
install:

  Frozen (packaged .exe, distributed from the website): fully automatic,
  no user interaction. check_and_apply_update_if_frozen() checks GitHub
  for a newer release, and if one exists, downloads its installer,
  verifies its SHA256 against a checksum published in the same release,
  and spawns it silently (Inno Setup /VERYSILENT) — the caller
  (run_qt.py/.pyw) then exits immediately so the installer's own
  post-install launch takes over cleanly, rather than two versions
  fighting over the Start Menu shortcut. This happens at the very start
  of startup, before any data is loaded or work begins, specifically so
  it can never lose in-progress user work by relaunching mid-session.
  Every failure mode (offline, GitHub unreachable, timeout, a checksum
  mismatch, a malformed manifest) falls through to "just launch
  normally" — never raises, never blocks longer than its own timeout.

  Dev/editable install: unchanged from before — UpdateCheckWorker checks
  both PhysicsAnalysis and PhysicsLibrary and shows a blocking
  "here's a download link" dialog (show_update_required_dialog) if
  PhysicsAnalysis itself is outdated, or a quiet splash status line
  otherwise. This path makes no sense for a packaged build (there's no
  "please download and run the installer yourself" step to point at —
  that's exactly what the frozen path now automates), and PhysicsLibrary
  drift is a developer-only concern (it's bundled into the packaged exe,
  invisible to an end user) — so it stays dev-only.

Neither project reliably uses GitHub Releases as a matter of course for
version *comparison* (PhysicsLibrary currently has none at all), so the
dev-mode "latest version" check prefers the tag of the repo's latest
published Release when one exists, falling back to the version string
committed in pyproject.toml on the default branch when it doesn't. The
frozen path is different: it requires an actual Release with a
latest.json manifest (see Deployment Steps.md) — there's no pyproject.toml
fallback available to a packaged build in the first place.

The GitHub calls run on a background QThread so the splash's pulse
animation and event loop stay responsive while they're in flight.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox
from packaging.version import Version

_TIMEOUT_S = 4
_ANALYSIS_REPO = "zakgm2/PhysicsAnalysis"


def is_frozen():
    """True for a PyInstaller-packaged build, False for a normal
    source/editable-install run — the standard way PyInstaller apps
    detect this about themselves (it sets sys.frozen)."""
    return getattr(sys, "frozen", False)

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _parse_version(pyproject_text):
    match = _VERSION_RE.search(pyproject_text)
    return match.group(1) if match else None


def local_version(name):
    """Reads the version out of a package's own pyproject.toml, found
    relative to its installed location — works the same whether that
    package is this app itself or an editable-installed dependency like
    PhysicsLibrary, and always reflects the actual source on disk rather
    than possibly-stale install metadata. Also used directly by
    ui/main_window.py to show this app's own version in the title bar.

    Tried first, ahead of any hardcoded __version__ string a package might
    also define (physicsanalysis_qt does, as of the packaged-build work —
    see its __init__.py), specifically to avoid trusting a constant that
    could silently drift from pyproject.toml's own value during
    development. Only falls back to __version__ when pyproject.toml can't
    be read at all, which is exactly the case for a frozen/packaged
    build — there's no source tree on disk there, so there's nothing for
    that constant to drift from."""
    import importlib
    import os

    module = importlib.import_module(name)
    pkg_dir = os.path.dirname(os.path.abspath(module.__file__))
    pyproject_path = os.path.join(os.path.dirname(pkg_dir), "pyproject.toml")
    version = None
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            version = _parse_version(f.read())
    except OSError:
        pass
    # Falls through here both when the file couldn't be opened at all
    # (frozen build — no source tree on disk) and when it opened but
    # didn't contain a recognizable version line (a frozen build's
    # module.__file__ can resolve to some other real-but-irrelevant path
    # that happens not to raise OSError) — either way, nothing usable
    # was read, so fall back the same way.
    if version is None:
        version = getattr(module, "__version__", None)
    if version is None:
        raise ValueError(f"could not determine {name}'s version")
    return version


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
    ("PhysicsAnalysis", "physicsanalysis_qt", _ANALYSIS_REPO),
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
                local = Version(local_version(package_name))
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


def _fetch_latest_manifest():
    """The frozen-build update manifest — a small latest.json published
    as a fixed-name asset on every release (see Deployment Steps.md),
    fetched via the same stable non-API redirect URL pattern as the
    installer itself: {"version": "X.Y.Z", "installer": "<exact current
    asset filename>", "sha256": "<installer's checksum>"}. Deliberately
    NOT api.github.com — that's rate-limited to 60 req/hour *shared per
    source IP*, a real risk for "every user, every launch" checks from
    behind a shared lab/university NAT; the plain releases/.../download/
    URL is a normal web request with no such cap."""
    req = urllib.request.Request(
        f"https://github.com/{_ANALYSIS_REPO}/releases/latest/download/latest.json",
        headers={"User-Agent": "PhysicsAnalysis-update-check"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        return json.loads(resp.read())


def _download_and_verify_installer(manifest, timeout_s=90):
    """Downloads the installer named in manifest to a temp file and
    verifies its SHA256 against manifest['sha256'] before returning its
    path — returns None on absolutely any failure (network, a missing
    manifest field, a checksum mismatch), and critically, NEVER returns
    a path to content that didn't verify. This is the one integrity
    check standing between "GitHub said there's an update" and silently
    executing whatever was actually downloaded with zero user
    confirmation — a mismatch here must never be treated as "close
    enough."""
    installer_name = manifest.get("installer")
    expected_sha256 = manifest.get("sha256")
    if not installer_name or not expected_sha256:
        return None

    url = f"https://github.com/{_ANALYSIS_REPO}/releases/latest/download/{installer_name}"
    req = urllib.request.Request(url, headers={"User-Agent": "PhysicsAnalysis-update-check"})
    tmp_path = os.path.join(tempfile.gettempdir(), installer_name)
    hasher = hashlib.sha256()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp, open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                hasher.update(chunk)
    except Exception:
        return None

    if hasher.hexdigest().lower() != expected_sha256.strip().lower():
        return None
    return tmp_path


def check_and_apply_update_if_frozen():
    """The whole frozen-build auto-update sequence, run synchronously —
    call this from AutoUpdateWorker (a background thread), not directly
    from the main thread, since the download step can take a while.

    Returns True if an update installer was successfully verified and
    spawned — the caller MUST exit the process immediately afterward
    (see run_qt.py/.pyw), before doing anything else, so the installer
    (writing into a brand new versioned directory — see installer.iss —
    never touches this process's own open files) and its own
    post-install launch of the new version aren't racing this old
    process for the Start Menu shortcut.

    Returns False for absolutely everything else — not frozen, up to
    date, offline, GitHub unreachable, a malformed manifest, a checksum
    mismatch, spawning the installer failed. This function never raises;
    every failure mode here means "just launch normally," matching the
    requirement that a missing internet connection (or anything else
    going wrong) must never block startup."""
    if not is_frozen():
        return False

    try:
        manifest = _fetch_latest_manifest()
        remote = Version(manifest["version"])
        local = Version(local_version("physicsanalysis_qt"))
        if remote <= local:
            return False
    except Exception:
        return False

    installer_path = _download_and_verify_installer(manifest)
    if installer_path is None:
        return False

    try:
        subprocess.Popen(
            [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except Exception:
        return False
    return True


class AutoUpdateWorker(QThread):
    """Runs check_and_apply_update_if_frozen() on a background thread —
    the download step in particular can take a while, and this keeps the
    splash's pulse animation and event loop responsive (and Windows from
    flagging the process as hung) while it's in flight. Emits
    finished(bool): True means an installer was spawned and the caller
    must exit immediately; False means nothing to do, proceed with
    startup as normal."""
    finished_ = pyqtSignal(bool)

    def run(self):
        self.finished_.emit(check_and_apply_update_if_frozen())
