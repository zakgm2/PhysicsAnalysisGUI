"""
physicsanalysis_qt
-------------------
PyQt6 implementation of the Physics Analysis GUI. Split by concern:

  context.py          - shared AppState object passed to every function
  fonts.py             - golden-ratio figure font sizing
  toasts.py            - toast/error/success notifications
  sidecar.py           - marker .json save/load
  markers.py           - Add/Edit Marker dialog + placement/lookup
  plotting.py          - simple_plot(), attribute re-application, view export
  interaction.py       - zoom/pan/hover/rect-select/resize
  attributes.py        - Edit Attributes dialog
  loaders/             - TDT, Oxysoft, generic tabular, PT2 file loading
  analysis/            - Curve Fit, PETH, FFT windows + click dispatch
  ui/                  - toolbar + main window assembly

Entry point: PhysicsAnalysisGUI_qt.py at the repo root.
"""
