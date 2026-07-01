"""
analysis/models_registry.py
-----------------------------
Curve fit model registry consumed by CurveFitDialog. To add a model,
add an entry here — nothing else needs to change.

Each entry: "Display Name": (model_fn, p0_fn, [param names]) where
  model_fn  - f(x, *params) -> y   (defined in PhysicsLibrary.models)
  p0_fn     - f(x_seg, y_seg) -> list of initial guesses
  param list- human-readable name for every parameter, in order
"""

import PhysicsLibrary.models as _models

CURVE_FIT_MODELS = {
    "Linear  (y = mx + b)": (
        _models.linear_model,
        lambda x, y: [(y[-1] - y[0]) / (x[-1] - x[0]) if (x[-1] - x[0]) != 0 else 0, y[0]],
        ["m (slope)", "b (intercept)"],
    ),
    "Exponential Decay  (a*e^(-bx) + c)": (
        _models.single_exponential_model,
        lambda x, y: [y.max() - y.min(), 0.1, y.min()],
        ["a (amplitude)", "b (decay rate)", "c (offset)"],
    ),
    "Exponential Rise  (a*(1-e^(-bx)) + c)": (
        _models.exponential_rise_model,
        lambda x, y: [y.max() - y.min(), 0.1, y.min()],
        ["a (amplitude)", "b (rise rate)", "c (offset)"],
    ),
    "Gaussian  (a*exp(-(x-u)^2/2s^2))": (
        _models.gaussian_model,
        lambda x, y: [y.max(), x[y.argmax()], (x[-1] - x[0]) / 4],
        ["a (amplitude)", "u (centre)", "s (width)"],
    ),
    "Sinusoidal  (a*sin(2*pi*f*x + phi) + c)": (
        _models.sinusoidal_model,
        lambda x, y: [(y.max() - y.min()) / 2, 1.0, 0.0, y.mean()],
        ["a (amplitude)", "f (frequency Hz)", "phi (phase)", "c (offset)"],
    ),
    "Double Exponential  (a*e^(-bx) + c*e^(-dx) + k)": (
        _models.double_exponential_model,
        lambda x, y: [y.max() * 0.6, 0.05, y.max() * 0.4, 0.001, y.min()],
        ["a", "b (fast rate)", "c", "d (slow rate)", "k (offset)"],
    ),
}
