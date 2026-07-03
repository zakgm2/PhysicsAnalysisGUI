"""
analysis/window_settings.py
----------------------------
The analysis window (pre/post seconds around a clicked event, used by
FFT/PETH/Curve Fit) as a single toolbar button + popup dialog, instead of
always-visible entry fields. Symmetric by default (one size applies to
both sides); untick "Symmetric" to set pre/post independently.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QDialogButtonBox, QLayout,
)

_DEFAULT_PRE = 15.0
_DEFAULT_POST = 15.0


def init_window_settings(ctx):
    """Call once at startup — sets the initial pre/post/symmetric state."""
    ctx.window_pre = _DEFAULT_PRE
    ctx.window_post = _DEFAULT_POST
    ctx.window_symmetric = True


def get_window(ctx):
    """Returns (pre, post) seconds around the click/event centre."""
    return ctx.window_pre, ctx.window_post


def _window_button_text(ctx):
    if ctx.window_symmetric:
        return f"Window: {ctx.window_pre + ctx.window_post:.0f}s"
    return f"Window: {ctx.window_pre:.0f}s / {ctx.window_post:.0f}s"


def _refresh_window_button(ctx):
    if ctx.btn_window is not None:
        ctx.btn_window.setText(_window_button_text(ctx))


class WindowDialog(QDialog):
    """Symmetric size field by default; untick Symmetric to swap it out
    for independent Pre/Post fields (e.g. 10s before, 20s after) — only
    the fields that apply are shown, not disabled-but-visible."""

    def __init__(self, ctx):
        super().__init__(ctx.win)
        self.ctx = ctx
        self.setWindowTitle("Analysis Window")
        self.setModal(True)
        self.setMinimumWidth(260)

        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        # Without this, hiding/showing form rows via setRowVisible() changes
        # the layout's sizeHint but the dialog window itself doesn't shrink
        # or grow to match — SetFixedSize makes the top-level widget track
        # its layout's size on every change instead of only at construction.
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.chk_symmetric = QCheckBox("Symmetric (same length before and after)")
        self.chk_symmetric.setChecked(ctx.window_symmetric)
        self.chk_symmetric.toggled.connect(self._on_symmetric_toggled)
        outer.addWidget(self.chk_symmetric)

        form = QFormLayout()
        form.setSpacing(8)
        outer.addLayout(form)

        # "Window size" is the TOTAL span (before + after), split evenly —
        # matches how people naturally describe a window ("a 30s window
        # around the event"), not "15s on each side".
        size_default = ctx.window_pre + ctx.window_post
        self.e_size = QLineEdit(str(int(size_default)))
        self.e_size.setFixedWidth(70)
        form.addRow("Window size (s):", self.e_size)

        self.e_pre = QLineEdit(str(int(ctx.window_pre)))
        self.e_pre.setFixedWidth(70)
        form.addRow("Before event (s):", self.e_pre)

        self.e_post = QLineEdit(str(int(ctx.window_post)))
        self.e_post.setFixedWidth(70)
        form.addRow("After event (s):", self.e_post)

        self._form = form

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                    | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._on_symmetric_toggled(ctx.window_symmetric)

    def _on_symmetric_toggled(self, symmetric):
        self._form.setRowVisible(self.e_size, symmetric)
        self._form.setRowVisible(self.e_pre, not symmetric)
        self._form.setRowVisible(self.e_post, not symmetric)
        focus_target = self.e_size if symmetric else self.e_pre
        focus_target.setFocus()
        focus_target.selectAll()

    @staticmethod
    def _parse(entry, default):
        try:
            val = float(entry.text())
            return val if val > 0 else default
        except ValueError:
            return default

    def _confirm(self):
        ctx = self.ctx
        ctx.window_symmetric = self.chk_symmetric.isChecked()
        if ctx.window_symmetric:
            total = self._parse(self.e_size, _DEFAULT_PRE + _DEFAULT_POST)
            ctx.window_pre = total / 2
            ctx.window_post = total / 2
        else:
            ctx.window_pre = self._parse(self.e_pre, _DEFAULT_PRE)
            ctx.window_post = self._parse(self.e_post, _DEFAULT_POST)
        _refresh_window_button(ctx)
        self.accept()


def open_window_dialog(ctx):
    dlg = WindowDialog(ctx)
    dlg.exec()
