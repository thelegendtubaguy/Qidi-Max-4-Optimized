"""Independent nonlinear step-response fits; requires NumPy and SciPy.

Raw data remain unchanged. Median-three and drift choices are sensitivity
comparisons, not production filters. Host receipt time is not conversion time.
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares


def fit_transition(t, y, edge, window, drift):
    mask = (t >= edge - 0.1) & (t <= edge + window)
    tt, yy = t[mask] - edge, y[mask]
    baseline = np.median(yy[tt < 0])
    scale = max(np.percentile(yy, 80) - np.percentile(yy, 20), 1000)
    z = (yy - baseline) / scale

    def residual(p):
        b, amplitude, log_tau, onset = p[:4]
        elapsed = np.maximum(0, tt - onset)
        predicted = b + amplitude * (-np.expm1(-elapsed / np.exp(log_tau)))
        if drift:
            predicted += p[4] * tt
        return predicted - z

    best = None
    for tau in (0.008, 0.03, 0.09, 0.25):
        initial = [0, -1, np.log(tau), 0]
        lower = [-10, -20, np.log(0.002), -0.08]
        upper = [10, 20, np.log(0.5), 0.08]
        if drift:
            initial += [0]
            lower += [-30]
            upper += [30]
        result = least_squares(residual, initial, bounds=(lower, upper),
                               loss="soft_l1", f_scale=0.05, max_nfev=2000)
        if best is None or result.cost < best.cost:
            best = result
    error = residual(best.x)
    return {
        "samples": len(tt), "tau_seconds": float(np.exp(best.x[2])),
        "onset_offset_seconds": float(best.x[3]),
        "amplitude_counts": float(best.x[1] * scale),
        "r_squared_including_all_window_samples": float(
            1 - np.sum(error**2) / max(np.sum((z - np.mean(z))**2), 1e-12)),
        "optimizer_success": bool(best.success),
    }


root = Path(__file__).resolve().parent.parent
runs = []
for index in (1, 2, 3):
    name = "petg-step-response-%s.json" % index
    doc = json.loads((root / name).read_text())
    assert doc["complete"] and doc["cleanup_complete"]
    rows = [r for r in doc["capture"]["records"] if r["kind"] == "raw"]
    t = np.array([r["#receive_time"] for r in rows])
    y = np.array([r["counts"] for r in rows], dtype=float)
    filtered = np.array([np.median(y[max(0, i-1):i+2]) for i in range(len(y))])
    motion = doc["motion"]
    start = (motion["host_anchor_offset"] + motion["start_print_time_before_flush"]
             - motion["print_anchor"])
    fits = []
    for leg in (1, 3):
        for window in (0.12, 0.18, 0.24):
            for drift in (False, True):
                for label, values in (("raw", y), ("median3", filtered)):
                    fits.append({"rising_leg": leg, "window_seconds": window,
                                 "linear_drift": drift, "input": label,
                                 **fit_transition(t, values, start + leg*0.3,
                                                  window, drift)})
    runs.append({"trace": name, "samples": len(y),
                 "median_receipt_spacing_seconds": float(np.median(np.diff(t))),
                 "fits": fits})
print(json.dumps({"model": "offset + linear drift + delayed first-order step",
                  "nominal_segment_seconds": 0.3,
                  "conversion_timestamps": False,
                  "runs": runs}, indent=2))
