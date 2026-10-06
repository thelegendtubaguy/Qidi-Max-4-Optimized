"""Analyze retained multi-flow traces without contacting or modifying a printer.

Requires numpy and scipy. Emits JSON, not an approved Orca table. Both estimators
are independently implemented from the first-order response equation. Median
filtering is an offline sensitivity comparison, never a force-safety decision.
"""
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares


def whole_waveform(t, y):
    mask = (t >= 3.7) & (t <= 5.9)
    t, y = t[mask], y[mask]
    center = np.median(y)
    scale = max(np.percentile(y, 90) - np.percentile(y, 10), 1000)
    z = (y - center) / scale

    def residual(p):
        offset, gain, slope, log_tau, delay = p
        response = np.zeros_like(t)
        for edge, sign in ((4, 1), (4.5, -1), (5, 1), (5.5, -1)):
            response += sign * (-np.expm1(-np.maximum(0, t-edge-delay) / np.exp(log_tau)))
        return offset + gain*response + slope*(t-4.8) - z

    best = None
    for tau in (0.005, 0.015, 0.05, 0.15):
        for delay in (-0.015, 0.015):
            fit = least_squares(
                residual, [0, -1, 0, np.log(tau), delay],
                bounds=([-10, -20, -10, np.log(0.002), -0.08],
                        [10, 20, 10, np.log(0.4), 0.08]),
                loss="soft_l1", f_scale=0.05, max_nfev=1500)
            if best is None or fit.cost < best.cost:
                best = fit
    error = residual(best.x)
    return {
        "tau_seconds": float(np.exp(best.x[3])),
        "delay_seconds": float(best.x[4]),
        "amplitude_counts": float(best.x[1]*scale),
        "r_squared_all_samples": float(1 - np.sum(error**2)/np.sum((z-z.mean())**2)),
        "sample_count": len(t),
    }


def integral_step(t, y, edge, window):
    mask = (t >= edge+0.005) & (t <= edge+window)
    t, y = t[mask], y[mask]
    t, y = t-t[0], y-y[0]
    integral = np.r_[0, np.cumsum(np.diff(t)*(y[1:]+y[:-1])/2)]
    design = np.column_stack([np.ones(len(t)), integral, t, t*t])
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y-design@coefficients
    return {
        "tau_seconds": float(-1/coefficients[1]),
        "r_squared_all_samples": float(1-np.sum(residual**2)/np.sum((y-y.mean())**2)),
        "sample_count": len(t),
    }


def analyze(root):
    results = []
    for flow in (4, 10, 18):
        for suffix in ("fast", "fast-b"):
            path = root / ("petg-table-%s-%s.json" % (flow, suffix))
            doc = json.loads(path.read_text())
            assert doc["complete"] and doc["cleanup_complete"]
            assert doc["cooled_below_80_with_part_fan"]
            rows = [r for r in doc["capture"]["records"] if r["kind"] == "raw"]
            motion = doc["motion"]
            start = (motion["host_anchor_offset"] + motion["start_print_time_before_flush"]
                     - motion["print_anchor"])
            t = np.array([r["#receive_time"]-start for r in rows])
            raw = np.array([r["counts"] for r in rows], dtype=float)
            filtered = np.array([np.median(raw[max(0,i-1):i+2]) for i in range(len(raw))])
            fits = []
            for edge in (4.0, 5.0):
                for window in (0.12, 0.18, 0.24):
                    fits.append({"edge_seconds": edge, "window_seconds": window,
                                 **integral_step(t, filtered, edge, window)})
            results.append({
                "trace": path.name, "mean_flow_mm3_s": flow,
                "samples": len(raw), "median_spacing_seconds": float(np.median(np.diff(t))),
                "whole_waveform_raw": whole_waveform(t, raw),
                "whole_waveform_median3": whole_waveform(t, filtered),
                "integral_rising_steps_median3": fits,
            })
    return {"status": "inconclusive_multi_flow_repeatability",
            "orca_table": None, "conversion_timestamps": False,
            "numpy_version": np.__version__, "scipy_version": scipy.__version__,
            "note": "Negative/boundary-sensitive or inconsistent fits are retained, not converted to PA recommendations.",
            "runs": results}


if __name__ == "__main__":
    print(json.dumps(analyze(Path(__file__).resolve().parent.parent), indent=2))
