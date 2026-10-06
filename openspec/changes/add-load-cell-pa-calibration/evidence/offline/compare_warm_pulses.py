"""Descriptive raw/median-three comparison; no PA fitting or safety decisions."""
import json
from pathlib import Path
from statistics import median

root = Path(__file__).resolve().parent.parent
results = []
for name in ("warm-petg-success", "warm-petg-repeat1", "warm-petg-repeat2",
             "warm-petg-conditioned1", "warm-petg-conditioned2"):
    doc = json.loads((root / (name + ".json")).read_text())
    rows = [row for row in doc["capture"]["records"] if row["kind"] == "raw"]
    raw = [row["counts"] for row in rows]
    filtered = [median(raw[max(0, i-1):min(len(raw), i+2)]) for i in range(len(raw))]
    metrics = {}
    for label, values in (("raw", raw), ("median3", filtered)):
        baseline = median(values[:20])
        amplitude = baseline - min(values)
        above_half = [i for i, value in enumerate(values) if baseline-value >= amplitude/2]
        metrics[label] = {
            "baseline_counts": baseline,
            "peak_excursion_counts": amplitude,
            "tail_minus_baseline_counts": median(values[-10:]) - baseline,
            "half_amplitude_span_host_seconds": (
                rows[above_half[-1]]["arrival"]-rows[above_half[0]]["arrival"]
            ) if above_half else None,
        }
    results.append({"trace": name, "samples": len(rows), "metrics": metrics})
print(json.dumps({"description": "Median-three is an offline sensitivity comparison, not a validated filter. Host times are not conversion times.", "runs": results}, indent=2))
