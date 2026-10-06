# Bounded cold raw-capture experiments

## First trial: ten requests

**Runtime-confirmed:** the independently implemented collector completed ten cold-idle raw requests at a maximum requested rate of 10 Hz. All ten returned four-byte payloads within the 100 ms deadline. No overflow, empty payload, sentinel classification, timeout, or additional response was reported.

[Raw evidence](evidence/raw-cold-idle.json) retains every callback, request ordinal, and relative host/transport timestamp. It does not assign conversion timestamps or deduplicate equal values.

| Measurement | Result |
|---|---|
| Raw responses | 10 / 10 |
| Effective callback cadence | 9.39 Hz |
| Send-to-callback latency | 1.76–2.77 ms; median 1.99 ms |
| Count range | -895063 to -892929 |
| Median count | -894871.5 |
| Stored reference before / after | `f658f200` / `f658f200` |
| Homing flag before / after | 0 / 0 |
| Trigger clock before / after | unchanged |

The first sample differed noticeably from later values. Ten points are insufficient to classify that difference or establish a noise model, sustained rate, or conversion freshness. The result demonstrates a working non-zeroing host capture path, not useful PA discrimination or full probing safety.

## Longer trial: 100 planned requests

**Runtime-confirmed:** a subsequent cold trial requested 100 readings at a maximum 25 Hz, with the same 100 ms deadline and unchanged collector. It stopped after the 19th request. All 19 sent requests received four-byte responses; the remaining 81 requests were never sent. This is not 81 lost responses.

[Longer-trial raw evidence](evidence/raw-cold-long.json) records `RAW_RESPONSE_DEADLINE`. The final response reached the host serial queue 1.27 ms after sending, but the Python callback ran 207.83 ms after sending: a 206.57 ms delivery delay between those timestamps. The captured transport receipt intervals were 1.09–1.74 ms across all replies; median send-to-callback latency was 2.25 ms. The first 18 callbacks averaged 20.95 Hz, below the requested ceiling. Transport metadata is not an ADC conversion timestamp, but it distinguishes this observed callback delay from an absent reply. The cause of the delay is unresolved; the trial ran shortly after service startup, so startup activity is a possible confounder, not an established explanation.

The second raw reading was `f9ffff00`, or -7 counts, between readings near -895000. Across all 19 payloads, the median was -895191 counts and median absolute deviation was 64 counts; the range was -895408 to -7. These are descriptive statistics, not a production outlier filter. The isolated near-zero excursion was retained without interpolation or suppression. The collector's `freshness_unknown` label does not establish signal validity.

Post-capture verification completed: stored reference remained `f658f200`, homing remained zero, and trigger clock was unchanged. The then-current implementation invoked its generic stock-state shutdown guard for every capture issue. Its shutdown wording therefore overstated this result: the evidence showed a callback-deadline failure with unchanged checked state, not demonstrated sensor corruption. Firmware restart was required to recover from that deliberate shutdown; no second capture was attempted during that deployment. The refined collector described below now separates timing-only failure from verified sensor state.

### Consequences for the change

- Distinguish planned, sent, received, transport-timed, and callback-timed data. A delayed callback must not be mislabeled as a missing MCU reply or converted into a precise ADC timestamp.
- Separate bounded host callback allowance for cold characterization from PA signal-quality acceptance. Do not merely increase all deadlines until tests pass, or require perfect timing before further bounded experiments.
- Report capture failure separately from verified/changed/unverifiable stock state. Retain shutdown on unsafe or unverifiable ownership/state; qualify a less disruptive stop policy for timing-only failures with verified cleanup.
- Retain anomalous raw values and add quality summaries. Establish how repeat measurements tolerate isolated bad readings without hiding real force transitions or fabricating a clean trace.
- Repeat the longer cold trial after these refinements and a documented post-startup settling interval. This partial run does not establish sustained usable rate or qualify heated PA measurement.

### Longer-trial restoration

The original config was restored byte-for-byte, the temporary module/include removed, and `FIRMWARE_RESTART` returned Klipper to `ready`. The temporary G-code command was absent afterward. Pre-test PA `0.052`, smooth time `0.03`, and motion limits were restored and verified; heater targets remained zero, homed axes remained empty, and logical position matched the pre-test zero position. Config SHA-256 matched the first trial's original hash. No homing, heating, or extrusion was commanded.

## Settled repeat: 100 completed requests

**Runtime-confirmed:** after loading the refined collector and waiting 120.44 seconds from observed Klipper readiness, a third cold-idle trial completed 100/100 requests at a maximum 25 Hz with no issues. [Settled-trial evidence](evidence/raw-cold-settled.json) reports planned, sent, and received counts separately; all were 100, with zero unsent and zero unanswered sent requests.

| Measurement | Result |
|---|---|
| Transport receipt after send | 0.97–1.65 ms; median 1.21 ms |
| Callback after send | 1.73–4.35 ms; median 1.97 ms |
| Callback after transport receipt | 0.64–2.96 ms; median 0.77 ms |
| Callbacks after 100 ms with timely transport | 0 |
| Count range | -895279 to -17 |
| Median / median absolute deviation | -894931.5 / 75.5 counts |
| Stored reference before / after | `00000000` / `00000000` |
| Homing state / trigger clock | unchanged |

The run establishes sustained bounded request/response operation at this rate under settled cold-idle conditions. It does not establish conversion timing or conversion freshness. The stored reference differed from earlier trials but was unchanged within this trial; service/firmware restarts between trials are a confounder, so no cross-process reference conclusion is drawn.

Request 21 returned -17 counts, the only descriptive outer-fence excursion, amid ordinary values near -895000. This independently reproduces the earlier -7 excursion. The implementation preserved and flagged it, removed/interpolated zero samples, and labels the descriptive rule as not validated for force. A production classifier remains unresolved because true loaded force transitions must not be discarded.

The collector now allows up to 250 ms for Python callback delivery while retaining the 100 ms transport-evidence deadline. The two thresholds are reported separately; neither is a PA timing-quality acceptance criterion. The tested revision stopped raw requests on missing or transport-late responses. Subsequent offline review found that an unanswered request must remain unresolved rather than dropping its handler and issuing verification queries. Package `26.09.17.2` now shuts down on that path, enforces the callback limit after host stalls, and validates payloads before timing-only recovery. Received timing-only failures avoid global shutdown only after unchanged reference/homing state and owned-handler cleanup are verified; unsafe or unverifiable state still requires shutdown. These fixes have offline failure-matrix coverage, not a new hardware trial. Another capture remains blocked until process restart.

The original config was restored byte-for-byte, temporary files were removed, and the trial command was absent after restart. PA, smoothing, motion limits, homing state, logical position, and zero heater targets matched pre-test values. No homing, heating, movement, or extrusion was commanded.

## Consequences for the next stage

- Sustained cold-idle acquisition at 25 Hz is qualified enough to continue bounded investigation; the prior callback stall did not recur after settling, but one comparison cannot prove settling caused the difference.
- Near-zero excursions recur. They do not block bounded experimentation or require perfect raw data. Preserve raw traces and compare an offline isolated-spike filter against unfiltered analysis; reject a measurement when contamination materially changes the result. Neither filtering nor interpolation may suppress safety checks or hide sustained force changes.
- The operator authorized further probing and bounded PETG extrusion. Heated capture still requires its own guarded acquisition/extrusion transaction; do not bypass the cold collector's heater precondition. Production recommendations remain gated on repeatability and printed comparison.

## Cold stock-probing check

**Runtime-confirmed:** with the experimental module already removed and Klipper restarted, full `G28`, five center `PROBE_ACCURACY` samples, `Z_TILT_ADJUST`, and a final `G28 Z` all completed successfully. [Probing evidence](evidence/cold-stock-probing.json) retains the responses and selected before/after runtime state.

Center probe results were 0.024688, 0.003984, -0.005859, -0.008750, and -0.009922 mm. Reported range was 0.034609 mm and standard deviation 0.012894 mm. Z tilt completed without retry, with a probed-point range of 0.004805 mm against the installed 0.05 mm tolerance.

This demonstrates functioning installed probing after recovery/restart, not immediately after capture in the same process. Mesh and a same-process capture-to-probe sequence remain untested.

The printer was left homed at `X135 Y403 Z200`, over the chute. PA `0.052`, smoothing `0.03`, velocity `800`, acceleration `10000`, minimum cruise ratio `0.5`, square-corner velocity `8`, coordinate/extrusion modes, and feed/extrusion factors matched their pre-test values. Heater targets remained zero; no heating or extrusion occurred. The changed XYZ and Z-tilt state are intentional results of this authorized probing test, not restored pre-test positions.

## First-trial scope and restoration

The operator authorized a cold experiment with loaded filament, no homing, and no heating. Initial API state was standby with no homed axes and zero heater targets. THR reported `02.02.01.08`; the CS1237 module hash matched the firmware findings.

A temporary copy of our module enabled only the new source gate, loaded through a temporary include. The original config was backed up before adding that single include. A Klipper service restart took longer than the initial state-check timeout; access paused until the operator reconfirmed idleness. No sensor requests were sent until standby was confirmed again.

The trial sent read-only homing/reference queries, then raw reads, then read-only verification. It sent no zeroing, configuration, periodic-polling, homing, motion, or heater commands. During capture, position, PA, smoothing, and motion limits remained unchanged.

After capture, the temporary module/include were removed and the original `printer.cfg` restored byte-for-byte. Its SHA-256 before and after was `0324fbdc4f636abcc6ef8df94181df4e1dc3e6706a0a93b88d7197f06220c4b1`. The service was restarted to unload the trial. Restarts had reset volatile PA and acceleration to config defaults, so the recorded pre-test values were restored: PA `0.052`, smooth time `0.03`, maximum acceleration `10000`, velocity `800`, minimum cruise ratio `0.5`, and square-corner velocity `8`. The printer remained unhomed and unheated. Restart resets unhomed logical coordinates; no physical repositioning was performed.

## Implementation and licensing boundary

The collector in `installer/klipper/extras/tltg_pa_calibration.py` derives from our recovered QIDI command mapping and host transport inspection. No external calibration-project source, comments, constants, or fixtures were copied. Its raw read path uses non-retrying sends and bounded serial callbacks rather than the synchronous query wrapper.

Limits are 100 raw requests, maximum rate 100 Hz, a 20–500 ms transport-evidence deadline, a bounded 250 ms callback allowance, a six-second session deadline, and bounded callback storage. All callbacks are preserved up to the record limit; overflow invalidates capture. The conservative quarantine remains one attempt per sensor per Klipper process, including successful captures. Another attempt requires a process restart. Unsafe or unverifiable state invokes the stock-state shutdown guard; timing-only failure does not when unchanged state and owned-handler cleanup verify. Empty raw buffers remain explicit evidence, not fresh samples.

`CALIBRATION_ENABLED`, `DIRECT_CAPTURE_ENABLED`, `ORIGIN_CAPTURE_ENABLED`, and `RAW_CAPTURE_ENABLED` remain false in packaged source. The legacy origin read now rejects capture before calling the reference-mutating vendor method.

## Local validation

- 68 focused PA tests passed, including the raw lifecycle failure matrix and rejection of origin zeroing.
- 164 installer-core tests passed; bundle smoke, known-version metadata, config formatting, and strict OpenSpec validation passed.
- Core-suite timing was 6.03 seconds; the unmodified HEAD baseline was 5.91 seconds on the same machine. Both exceed the repository's five-second target on this machine; no unrelated performance changes were made.
- Offline command-map, MCU, and retry-wrapper results matched retained JSON evidence; the isolated compiled-host probe reconfirmed command bindings.
- Package `26.09.17.1` pins the refined extra and retains disabled capture/calibration defaults.

## Remaining experiments

- Cold 25 Hz capture completed 100/100 after a 120-second post-ready interval, with no transport/callback timing failures and unchanged within-trial reference/homing state.
- The independently repeated -17 near-zero excursion confirms that signal validity—not sustained cadence—is now the primary raw-acquisition uncertainty.
- Separately authorize stock probing validation, then characterize anomalies under controlled force before heated extrusion.
- Operator supplied the next experiment's inputs: 0.4 mm nozzle, PETG, 245 °C. These are session inputs, not package defaults or evidence that heated testing has occurred. The production workflow must collect these through Fluidd with confirmation.
- Use bounded conditioned extrusion and repeated/reordered PA trials only after the idle findings support progression. Keep chute clearing, extrusion budgets, and restoration intact.
- Produce Orca-ready recommendations only after repeated measurements and printed comparison support them; this trial produced no PA recommendation.
