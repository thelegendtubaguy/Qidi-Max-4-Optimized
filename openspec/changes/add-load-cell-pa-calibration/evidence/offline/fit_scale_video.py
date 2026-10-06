"""Reproduce loaded-point force-scale fits from retained video transcriptions.

Requires NumPy/SciPy. Reads evidence only; does not access a printer or video.
"""
import datetime
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

root = Path(__file__).resolve().parent.parent
report = json.loads((root / "scale-calibration-analysis.json").read_text())
rows = [json.loads(line) for line in (root / "scale-calibration-live.jsonl").read_text().splitlines()]
rows = [row for row in rows if row.get("record", {}).get("kind") == "raw"]
epoch = datetime.datetime(2026, 9, 17, 22, 12, 10, 750000, tzinfo=datetime.timezone.utc).timestamp()
t = np.array([row["wall_time"]-epoch for row in rows])
v = np.array([row["record"]["counts"] for row in rows])
v = np.array([np.median(v[max(0,i-1):i+2]) for i in range(len(v))])
seconds = np.array([row["video_seconds"] for row in report["readings"]])
grams = np.array([row["grams"] for row in report["readings"]])
selections = {
    "all_loaded": grams > 100,
    "below_2200": (grams > 100) & (grams < 2200),
    "below_2000": (grams > 100) & (grams < 2000),
    "held_loads": ((seconds >= 16) & (seconds <= 40)) | ((seconds >= 72) & (seconds <= 82)),
}
results = {}
for name, mask in selections.items():
    candidates = []
    g = grams[mask]
    for offset in np.arange(-2, 0.001, 0.01):
        y = np.interp(seconds[mask]+offset, t, v)
        fit = least_squares(lambda p: (p[0]+p[1]*g-y)/1000,
                            [-929000, 160], loss="soft_l1", f_scale=5)
        candidates.append((fit.cost, float(offset), float(fit.x[0]), float(fit.x[1])))
    _, offset, intercept, slope = min(candidates)
    y = np.interp(seconds[mask]+offset, t, v)
    residual = y-(intercept+slope*g)
    results[name] = {"offset_seconds": offset, "intercept": intercept,
                     "counts_per_gf": slope, "n": len(y),
                     "r_squared_all_selected": float(1-sum(residual**2)/sum((y-y.mean())**2))}
print(json.dumps(results, indent=2))
