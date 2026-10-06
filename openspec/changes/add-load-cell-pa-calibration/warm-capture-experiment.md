# Bounded PETG extrusion capture

## Successful run

**Runtime-confirmed:** the independently authored temporary harness completed one ordinary E-only pulse with the operator's 0.4 mm nozzle, PETG, and 245 °C inputs. It captured 100/100 raw responses, verified unchanged stored reference and homing state, drained motion, completed `CLEAR_OOZE` and `CLEAR_FLUSH`, restored modal state and motion limits, and turned heaters off.

- Pulse: 2 mm filament at 1 mm/s, about 2.002 seconds of queued extrusion.
- Position: X135 Y403 Z200 throughout measurement; clearing occurs afterward.
- Requested maximum sampling rate: 40 Hz. Actual first-to-last callback span: 4.339 seconds, about 22.8 Hz. Per-request state checks and response waits contribute overhead.
- Transport latency: 1.00–3.85 ms; median 1.21 ms.
- Callback latency: 1.62–7.33 ms; median 2.11 ms.
- First 20 sample median: -882901 counts. Minimum during the response: -950263, a 67362-count negative excursion from baseline.
- Final ten sample median: -882990, approaching the initial baseline.
- No descriptive outer-fence excursions in this run; no samples deleted or interpolated.

[Successful raw trace](evidence/warm-petg-success.json) retains all measurements and motion markers. This is a broad extrusion-associated response, not one isolated payload spike. There are no claimed conversion timestamps or calibrated force units. One run does not establish repeatability or a PA recommendation. Ordinary E-only G-code does not exercise the PA transform in this Klipper implementation.

## Failures and corrections

The [first aborted run](evidence/warm-petg-aborted.json) queued extrusion after 20 baseline samples, then its idle-only guard rejected the resulting motion. That prevented post-state verification and deliberately shut Klipper down. The fix permits `idle_timeout=Printing` only after this harness has queued its own bounded pulse, while still requiring an inactive `print_stats` state, exact parked XYZ, valid loaded-filament status, and the temperature envelope. Focused offline checks covered owned motion, actual printing, paused jobs, and unowned motion.

The [25 Hz rerun](evidence/warm-petg-duration-limit.json) captured all 100 responses and unchanged post-state, but exceeded the six-second session cap during final verification/drain. It entered shutdown and skipped chute clearing. It contains two isolated readings near -524289 as well as a broad extrusion response. Global distribution-based excursion flags also marked portions of that response: those flags must not be treated as a force-safe sample filter.

Recovery used `FIRMWARE_RESTART`. The successful repeat requested 40 Hz to shorten the trace without increasing the session duration cap. Before that repeat, vendor clearing removed material left by the aborted run; this was recovery cleanup, not a proposed production pre-pulse stage. The successful repeat completed final clearing normally.

## Restoration and reproduction

The temporary module/include were removed and the original config restored byte-for-byte (SHA-256 `0324fbdc4f636abcc6ef8df94181df4e1dc3e6706a0a93b88d7197f06220c4b1`). A service restart unloaded the command. PA 0.052, smoothing 0.03, velocity 800, acceleration 10000, minimum cruise ratio 0.5, and square-corner velocity 8 were restored and verified. Heater targets were zero; the nozzle was still cooling. Restart cleared homing status; no physical repositioning followed the completed chute cleanup.

[Temporary harness source](evidence/offline/warm_trial_append.py) was appended to the repository extra at SHA-256 `02c80955071dc25fc601c0993b6dc14e01db4f3f3a466984538f371719c174f7`. It overrides the temporary module's loader, not the packaged gates. It is experimental evidence, not an installed or auto-run tool. No release/version changes were made for these trials.

## Repeats and controlled conditioning

Two further 2 mm measurements, each after nozzle/chute clearing and a 30-second host-side wait, completed 100/100 responses with verified state and final cleanup. Their raw amplitudes were 32872.5 and 27752.5 counts. One contained a -2 reading; the other contained three consecutive -786433 readings and a -4 reading. A global outlier fence is not sufficient to classify these during changing force.

The first attempt to run that settling interval as `G4` followed immediately by capture rejected `idle_timeout=Printing` before any sensor capture. The temporary command did not convert the preflight exception into a normal G-code error and Klipper shut down. Recovery used firmware restart. Successful repetitions used a host-side wait and verified `Ready` before issuing capture separately. This preflight exception-handling defect remains in the retained experimental harness; it is not packaged software.

Two subsequent runs added exactly 5 mm conditioning extrusion at 1 mm/s before `CLEAR_OOZE`, `CLEAR_FLUSH`, and the same 30-second host-side wait. Each then measured the same 2 mm pulse and completed final cleaning with heaters off.

| Measurement | Conditioned run 1 | Conditioned run 2 |
|---|---:|---:|
| Raw replies | 100/100 | 100/100 |
| Raw baseline | -875783 | -880990 |
| Raw peak excursion | 71216 | 70908 |
| Median-three peak excursion | 69508 | 70261 |
| Median-three half-amplitude span, host seconds | 0.7942 | 0.7892 |
| Median-three tail relative to baseline | -1300 | -860 |

Raw amplitudes differ by 0.43% of their mean; median-three amplitudes differ by 1.08%. The corresponding half-amplitude spans differ by about 0.62%. This is encouraging repeatability from two runs, not a validated PA estimator or proof of causation. Process restarts and homing occurred between runs. One conditioned run retained an isolated -4 reading; the other had no global outer-fence excursions.

[Comparison output](evidence/warm-pulse-comparison.json) and [reproduction script](evidence/offline/compare_warm_pulses.py) compare all five successful traces without altering them. Median-three is an offline sensitivity check, not a safety filter or a validated transition-time correction. The three-sample plateau in an earlier run survives that filter.

Raw traces: [repeat 1](evidence/warm-petg-repeat1.json), [repeat 2](evidence/warm-petg-repeat2.json), [conditioned 1](evidence/warm-petg-conditioned1.json), [conditioned 2](evidence/warm-petg-conditioned2.json).

After each campaign the temporary module/include were removed, config restored, heaters verified off, and original PA/motion settings restored. No package versions were added. The next meaningful measurement is actual PA-enabled excitation with this conditioning sequence retained, rather than changing K during ordinary E-only moves that do not exercise PA. Same-process capture-to-probe validation and a repeatable PA recommendation remain open.
