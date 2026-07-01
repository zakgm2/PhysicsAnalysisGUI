"""
background.py
--------------
Optional off-main-thread execution for slow, pure-compute work (parsing a
large TDT tank or Oxysoft export). Controlled by
ctx.settings["background_loading"] via the Options dialog.

Qt widgets must only be touched from the main thread, so `fn` must be pure
compute (no ctx.win/ctx.ax/etc access) — the result is handed back to
on_success/on_error, which run on the main thread via Qt's queued signal
delivery, safe to touch widgets from there.
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal


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
    (identical to calling fn() directly) — this is the default, since most
    loads are fast enough that a worker thread isn't worth the complexity.
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

    thread = QThread()
    worker = _Worker(fn)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(on_success)
    if on_error:
        worker.failed.connect(on_error)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    # Keep references alive on ctx so they aren't garbage-collected mid-run.
    ctx._bg_thread = thread
    ctx._bg_worker = worker
    thread.start()
