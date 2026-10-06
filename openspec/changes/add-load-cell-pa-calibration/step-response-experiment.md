# Independent response-time PA experiment

## Outcome

**Subsequent evidence:** the [multi-flow campaign](adaptive-table-experiment.md) did not reproduce a stable PA table across conditioning and estimator choices. The candidate below is a historical exploratory result, not a current recommendation.

**Runtime-confirmed:** three conditioned PETG experiments captured 400/400 responses each with two rising extrusion-rate steps per run. All three completed cleanup and unchanged sensor-state verification. No external project code, constants, comments, or fixtures were copied or installed.

**Local-harness-confirmed:** an independently authored nonlinear exponential-plus-linear-drift fit produces a preliminary PA estimate around **0.055 seconds**, with later-transition estimates spanning approximately **0.048–0.067 seconds** for the 0.18–0.24 second fit windows. This is a candidate for printed comparison, not a qualified recommendation, proof of the external project's complete implementation, or an adaptive table.

The external project's central modeling hypothesis is useful here: infer K from the response time of ordinary extrusion steps rather than sweep applied K. The data do not yet establish that the fitted load-cell time constant equals optimal printed PA. Current PA 0.052 was restored, not replaced by the fit.

## Acquisition

- Operator inputs: 0.4 mm nozzle, PETG, 245 °C; 1.75 mm filament is assumed when discussing volumetric flow, not measured in this trial.
- Conditioning: 5 mm ordinary extrusion at 1 mm/s, vendor nozzle/chute clearing, 30-second host-side wait, then verified ready state.
- Measurement: five contiguous nominal 0.3-second legs at 0.4, 1.2, 0.4, 1.2, and 0.4 mm/s, total 1.08 mm filament. This provides two rising transitions before clearing.
- Segments were queued together through ordinary G-code lookahead, not flushed independently at each boundary. Segment boundary times are nominal; the artifact records total queued end time and a host/print-time anchor.
- Sampling: 400 requests at maximum 250 Hz, one outstanding request, unchanged six-second session bound. Actual median host-receipt spacing was 9.4–10.2 ms, not 4 ms. All readings are retained.
- Expensive full parked/temperature/filament checks ran every 100 ms during capture; shutdown checks remained per exchange. The temporary harness increased only its request/rate bounds, not packaged defaults.
- Cleanup: after the two measured high legs, wait for motion, `CLEAR_OOZE`, `CLEAR_FLUSH`, restore modes/limits, and turn heaters off.

[Run 1](evidence/petg-step-response-1.json), [run 2](evidence/petg-step-response-2.json), [run 3](evidence/petg-step-response-3.json), and [temporary append source](evidence/offline/step_trial_append.py) preserve the experiment. Append source uses repository extra SHA-256 `02c80955071dc25fc601c0993b6dc14e01db4f3f3a466984538f371719c174f7` with temporary raw bounds increased to 400 requests and 250 Hz.

## Independent estimator and sensitivity

The fitted model is an offset, optional linear baseline drift, and a delayed first-order step. Parameters are optimized with bounded nonlinear least squares and robust residual loss; this is not the external repository's integral-regression implementation. Tau, onset offset, amplitude, baseline, and optional drift are fitted independently. Multiple starting tau values reduce local-minimum sensitivity but do not prove a unique solution.

[Reproduction script](evidence/offline/fit_step_response.py) requires NumPy/SciPy and emits [all fits](evidence/step-response-fits.json), including raw/median-three, drift/no-drift, both rising transitions, and three fit windows. Raw evidence is unchanged. Host receipt times are not ADC conversion times. A median-three sensitivity check smooths isolated spikes but can also alter a short response; it is not a runtime safety filter.

Later rising transition, median-three with linear drift:

| Run | Tau, 0.18 s window | Tau, 0.24 s window | R², 0.18 / 0.24 s |
|---|---:|---:|---:|
| 1 | 0.0533 | 0.0530 | 0.994 / 0.989 |
| 2 | 0.0565 | 0.0480 | 0.979 / 0.972 |
| 3 | 0.0665 | 0.0666 | 0.989 / 0.979 |

Shortening the fit to 0.12 s gives 0.061–0.077 s, exposing remaining window sensitivity. Ignoring drift can produce much smaller estimates despite similar-looking traces. Optimizer fits have some local sensitivity; the retained reproduction output, not interim console values, is authoritative for these numbers.

The first rising transition includes a large startup/history response and gives much larger, less stable time constants. Treat it as conditioning rather than silently averaging it with the later transition. This observation supports the external project's repeated conditioned-step approach, but one later rise per run is still limited evidence.

## Decision

Continue with the response-time method, not the previous applied-K sweep or whole-pulse-width objective. A rounded **0.055** is an experimental single-flow PA candidate; **roughly 0.05–0.07** is a more honest description of the current evidence. Do not automatically apply it, manufacture a flow table, or claim printed accuracy. Additional conditioned transitions can improve precision; printed comparison must determine whether the estimate is useful.

The nozzle/chute were cleared after every measured pair. The temporary module/include were removed and original config restored byte-for-byte. After service restart, PA 0.052, smoothing 0.03, velocity 800, acceleration 10000, minimum cruise ratio 0.5, and square-corner velocity 8 were restored; heaters were verified off. No package version changed.
