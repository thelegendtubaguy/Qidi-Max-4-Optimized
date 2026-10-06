# Multi-flow PA table campaign

## Result

Fourteen successful captures retained **8000 raw responses**. Every capture completed sensor-state verification, nozzle/chute clearing, and part-fan cooling until below 80 °C. No measured PA was applied and no release version was added.

The current independent implementation does **not** yet support a trustworthy three-flow adaptive table. This does not disprove the linked project's implementation. Acquisition works; model consistency and physical repeatability remain insufficient at the lower two flows. The earlier single-flow 0.055 estimate must not be promoted into a recommendation or interpolated into a table.

## Captured experiments

All trials used operator-provided PETG, a 0.4 mm nozzle, 245 °C, and 1.75 mm filament area for converting feed speed to volumetric flow. The sequence was 4→10→18→18→10→4 mm³/s for both primary campaigns. Original runtime PA and motion settings were restored after each campaign; ordinary E-only excitation does not exercise applied PA.

| Protocol | Captures | Samples each | Description |
|---|---:|---:|---|
| Short legs, modest steps | 6 | 400 | Five 0.3 s legs, low/high ±20% of mean flow; 5 mm conditioning, clearing, and 30 s wait beforehand |
| Longer low-flow lead | 1 | 400 | Flow 4, 4 s continuous low-flow lead followed by two 0.5 s high legs, each separated by 0.5 s low |
| Wider steps | 1 | 400 | Same longer lead, flow 4 between 2 and 6 mm³/s |
| Faster polling, longer lead, wider steps | 6 | 800 | Flow 4: 2↔6; flow 10: 5↔15; flow 18: 12.8↔23.2 mm³/s; mean flows remain 4, 10, 18 |

The last protocol schedules each raw request relative to its prior send, rather than adding a full polling interval after receiving the response. It achieved approximately **5 ms median spacing**, versus approximately 10 ms previously. Full state checks remained periodic at 100 ms, with per-exchange shutdown checks. Nominal segment times and a print/host anchor are recorded; no ADC conversion timestamps are claimed.

The longer low-flow lead was queued before sensor capture. Ordinary lookahead throttling allowed some lead extrusion to execute before capture began, while the two measured transitions remained in the captured interval. The six-second capture deadline was unchanged. Waste clearing occurred after the measured pair and fan cooling occurred at shutdown; no fan ran during the fitted measurement window.

Artifacts `evidence/petg-table-{4,10,18}-{a,b}.json` retain the initial six traces. `petg-table-4-settled.json` and `petg-table-4-wide.json` retain the two waveform diagnostics. `petg-table-{4,10,18}-{fast,fast-b}.json` retain the final six traces.

## Offline estimator checks

[Executable analysis](evidence/offline/analyze_adaptive_campaign.py) requires NumPy/SciPy and performs no printer access. It emits [the retained JSON report](evidence/adaptive-campaign-analysis.json). Run it directly with Python to reproduce the whole-waveform and integral fits.

Three views were compared:

1. The earlier delayed exponential plus linear drift, fitted separately to a rising edge. Window changes materially change some estimates.
2. A shared first-order response fit to both rises and both falls, with baseline, gain, linear drift, and a common timing offset. All transitions constrain the same time constant.
3. An independently implemented integral form of the first-order equation, solved by linear least squares with a quadratic time term for drift. This follows the physical modeling idea, not copied external implementation code or constants.

Raw and centered median-three input are compared for the whole-waveform model. Median filtering never changes retained evidence or controls runtime safety. Raw R² is often dominated by enormous isolated acquisition excursions; robust fitting and filtering can improve residual quality without proving model correctness.

Whole-waveform median-three results:

| Mean flow | First run τ | Reverse-order run τ | R² first / reverse |
|---|---:|---:|---:|
| 4 mm³/s | 0.00417 s | 0.00648 s | 0.545 / 0.732 |
| 10 mm³/s | 0.03950 s | 0.07403 s | 0.919 / 0.920 |
| 18 mm³/s | 0.02839 s | 0.02642 s | 0.990 / 0.925 |

The 4 mm³/s whole-waveform estimate approaches the sample interval and fits poorly. At 10 mm³/s, high fit quality coexists with nearly a factor-of-two change between repetitions. At 18 mm³/s, whole-waveform repetition is closer, but rising-edge/integral estimates differ from the shared rise/fall estimate; that point is not independently print-validated either.

The integral estimator also produces negative, window-sensitive, and inconsistent estimates at 10 mm³/s. Thus selecting a different fitting method alone does not recover a dependable table. Neither high R² nor a plausible-looking PA value is enough. The report intentionally emits `orca_table: null`, rather than filling unsupported rows or borrowing values from the operator's existing table.

## Source and restoration

The retained append sources are `evidence/offline/tltg_table_trial_append.py`, `tltg_table_settled_append.py`, and `tltg_table_fast_append.py`. Each was appended to repository extra SHA-256 `02c80955071dc25fc601c0993b6dc14e01db4f3f3a466984538f371719c174f7`, with temporary raw bounds of 400/250 or 800/250 requests/Hz. The fast variant also uses send-relative scheduling. They are experimental evidence, not packaged calibration or an operator-ready Fluidd workflow.

After analysis, the temporary module/include and remote trial artifacts were removed. Original config SHA-256 `0324fbdc4f636abcc6ef8df94181df4e1dc3e6706a0a93b88d7197f06220c4b1` was verified. One final service restart unloaded the command, without another homing operation. The pre-experiment runtime PA 0.052 and motion limits were restored; this is not an endorsement of 0.052 for the operator's adaptive PETG profile. Heater targets were zero and measured nozzle temperature was 35.5 °C.

The operator has prohibited repeated Z homing. Further experiments must avoid the capture-per-process restart cycle rather than repeating homing overhead. Remaining work is a repeatable acquisition/conditioning and analysis transaction, then an operator-facing runner that produces supported table points. The current dataset supports investigation, not a completed calibration product.
