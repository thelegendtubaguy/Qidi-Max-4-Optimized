# PA-enabled PETG pulse comparison

## Measured campaign

Four successful captures used K order **0, 0.05, 0.05, 0**, each with 100/100 responses, unchanged checked sensor state, final nozzle/chute clearing, heater shutdown, and restoration of the original PA setting. Inputs were a 0.4 mm nozzle and PETG at 245 °C.

Every trial used 5 mm ordinary conditioning extrusion at 1 mm/s, `CLEAR_OOZE`, `CLEAR_FLUSH`, then a 30-second host-side settling wait. Measurement used a stationary, PA-eligible direct-extruder trapezoid: 0→1 mm/s over 0.1 s, 1.9 s cruise, 0.1 s deceleration, nominal distance 2 mm. Smoothing was 0.03 s. The previously validated CFFI append path set the PA eligibility field; nominal extruder/toolhead E bookkeeping and step-generation timing were advanced together. XYZ stayed parked at X135 Y403 Z200 during measurement.

## Descriptive results

Metrics below use an offline centered three-point median, retaining endpoints with the available neighbor. Baseline is the first 20 filtered readings; amplitude is baseline minus minimum. Half-amplitude span is the time between first and last filtered samples exceeding half that amplitude, using host callback time. Tail offset is the last ten filtered samples' median minus baseline. No stored raw trace is modified.

| K | Order | Amplitude, counts | Half-amplitude span, s | Tail offset, counts |
|---|---:|---:|---:|---:|
| 0 | 1 | 56087 | 0.7652 | 162 |
| 0.05 | 2 | 55549 | 0.8467 | -1142 |
| 0.05 | 3 | 57858 | 0.8662 | -14.5 |
| 0 | 4 | 60433.25 | 0.7274 | -1410.75 |

The filtered width is larger at K=0.05 in both comparisons, including reversed order. This is preliminary discrimination evidence, not an optimum-K decision: sampling granularity, callback timing, pressure history, and filtering affect the measured widths. Tail offsets and peak amplitude do not consistently favor one K. Raw spikes remain, including near-zero values and bit-pattern-like excursions. These four traces do not justify setting PA to zero or recommending 0.05.

Evidence: [K0 first](evidence/pa-pulse-k0-first.json), [K0.05 first](evidence/pa-pulse-k005-first.json), [K0.05 repeat](evidence/pa-pulse-k005-repeat.json), [K0 repeat](evidence/pa-pulse-k0-repeat.json). The next useful comparison is an intermediate K with repetitions and transition-specific analysis, not choosing a setting from peak amplitude or total width alone.

## Runtime compatibility and setup corrections

The first compatibility check rejected the live Python/C source hashes before capture. All five copied live sources were CRLF while the pinned sources were LF. SHA-256 after CRLF→LF normalization matched every expected source hash exactly, and compiled `c_helper.so` matched without normalization. The temporary harness pinned the verified live byte hashes; packaged code was unchanged.

Live source hashes:

- `extruder.py`: `eb840b6a2c25d3bc45d521735e5ee27a383b0eac0c538d7d27ff2634ac6829b7`
- `toolhead.py`: `70d5b4ba94bccdb90eb01b6d1743f3d833e42f798152ba47c98663ea188af04d`
- `chelper/__init__.py`: `9b6bc5013883122c7995199b47e8e14c9e1fccc0eaedc7cf4a01347df59d551c`
- `trapq.c`: `ea0e1964fdf61b626fb2821ea361ce85fcb1f7aa4bbfb66b6beb4454c10892cf`
- `kin_extruder.c`: `c9f24b00fd117d664ed257cd3b663d1e6a08568b4a4643963beeea19e63cbd67`

A subsequent [pre-capture rejection](evidence/pa-pulse-preflight-rejected.json) showed that setting PA itself changes idle bookkeeping. The temporary harness now marks its own PA preparation as owned activity, but continues to reject active prints, unhomed/off-chute positions, incorrect heater state, or unloaded filament. That rejection completed cleanup without sensor or pulse commands. A later service restart briefly returned HTTP 502; a further readiness check succeeded before any motion request.

[Retained temporary source](evidence/offline/pa_pulse_append.py) appends to repository extra SHA-256 `02c80955071dc25fc601c0993b6dc14e01db4f3f3a466984538f371719c174f7`, with only the five verified source pins replaced as above. It is experimental evidence, not an installed production backend.

## Restoration

The temporary module/include were removed; original config SHA-256 was restored to `0324fbdc4f636abcc6ef8df94181df4e1dc3e6706a0a93b88d7197f06220c4b1`. A service restart unloaded the trial. PA 0.052, smoothing 0.03, velocity 800, acceleration 10000, minimum cruise ratio 0.5, and square-corner velocity 8 were restored. Heater targets were verified zero. The nozzle was cooling and restart cleared homing status. No package versions were added and no recommendation was applied.
