"""
background.py
--------------
Off-main-thread execution for slow, pure-compute work (parsing a large
TDT tank or Oxysoft export), on by default via
ctx.settings["background_loading"] (see Options dialog for when to turn
it off).

Qt widgets must only be touched from the main thread, so `fn` must be pure
compute (no ctx.win/ctx.ax/etc access) — the result is handed back to
on_success/on_error, which run on the main thread via Qt's queued signal
delivery, safe to touch widgets from there.
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .toasts import show_window_toast


class _Worker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            result = self.fn()
        except Exception as e:
            self.failed.emit(str(e))
        else:
            self.finished.emit(result)


def run_in_background(ctx, fn, on_success, on_error=None):
    """
    Run fn() and deliver its result via on_success(result) / on_error(msg).

    If ctx.settings["background_loading"] is off, runs synchronously
    (identical to calling fn() directly).

    Refuses to start a second background load while one is already
    running — ctx._bg_thread/_bg_worker hold only one load's references at
    a time, so a second call while busy would silently orphan the first
    thread (it keeps running with nothing left tracking it) rather than
    queuing or erroring cleanly.
    """
    if not ctx.settings.get("background_loading"):
        try:
            result = fn()
        except Exception as e:
            if on_error:
                on_error(str(e))
        else:
            on_success(result)
        return

    if ctx._bg_thread is not None and ctx._bg_thread.isRunning():
        show_window_toast(ctx, "A file is already loading — wait for it to finish first.")
        return

    thread = QThread()
    worker = _Worker(fn)
    worker.moveToThread(thread)

    # thread.finished only fires once the QThread has actually stopped
    # running (i.e. after thread.quit() below has taken effect) — dropping
    # ctx's references to it any earlier (e.g. in the worker.finished
    # handler) frees the last Python reference to a QThread that Qt still
    # considers alive, which is a hard "QThread: Destroyed while thread is
    # still running" abort with no Python traceback, not a catchable
    # exception. Keep ctx._bg_thread/_bg_worker alive until here.
    def _cleanup():
        ctx._bg_thread = None
        ctx._bg_worker = None

    thread.started.connect(worker.run)
    worker.finished.connect(on_success)
    if on_error:
        worker.failed.connect(on_error)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(_cleanup)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    # Keep references alive on ctx so they aren't garbage-collected mid-run.
    ctx._bg_thread = thread
    ctx._bg_worker = worker
    thread.start()
