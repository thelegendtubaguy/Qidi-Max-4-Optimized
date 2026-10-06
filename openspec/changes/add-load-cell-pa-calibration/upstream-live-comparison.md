# Live upstream comparison

## Result

Two live runs of the **unmodified** Buddman69 measurement and table modules produced accepted PA estimates on the operator's Max 4. This is evidence that our earlier shortened experiments were not an equivalent implementation of that workflow. It is not printed validation of the returned PA.

| Flow, mm³/s | Run 1 K | Run 2 K | Upstream two-run mean | Accepted rising transitions, combined |
|---|---:|---:|---:|---:|
| 4 | 0.029392 | 0.036338 | 0.032865 | 113 |
| 10 | 0.031467 | 0.033355 | 0.032411 | 118 |
| 18 | 0.029306 | 0.031337 | 0.030322 | 111 |

Upstream confidence scores were 74–77. These are its heuristic scores, not independently calibrated probabilities. The second low-flow estimate was about 24% above the first. Flow dependence in the averaged table is small compared with that low-flow repeatability spread. No result was applied or persisted as printer PA.

Retained outputs:

- [Upstream measurement reports](evidence/upstream-pa-results.json): both runs, point-level spread, accepted counts, confidence, rejected-read counts, and the transition details that upstream itself stores.
- [Upstream table report](evidence/upstream-orca-results.json): means, standard deviation, standard error, and emitted rows.
- [Copyable experimental Orca rows](evidence/upstream-orca-table.txt): `PA,flow,acceleration`.

Upstream does not preserve the complete raw time series in these reports. Do not describe them as full raw captures or claim that every accepted transition can be independently replayed from the stored detail subset.

## Reproduction and isolation

Source: https://github.com/Buddman69/Automm3AdaptivePA at `3fc24b4aeac966af3eb8503a5b0898605faff652`.

Byte-for-byte verification against the local checkout and deployed files:

- `qidi_pa_measure.py`: `ab56c48da91bd6ce5ed5d3e8876392d2c4f9f5a603b4d1312ff5bd8e3cf935a0`
- `qidi_pa_table.py`: `297b16172ed852eb9b7875078bab5b26a3847dc11cdb325de555dbec021d7f67`

The operator explicitly authorized executing the external project for comparison. Its source was temporarily installed on the printer, not copied into this repository or bundled into our installer. A separate, independently written wrapper provided G-code-state restoration, waste clearing, heater shutdown, and part-fan cooling below 80 °C on normal/error exits while Klipper remained operational. It did not alter the upstream acquisition, fitting, or scoring functions.

Conditions: PETG, 0.4 mm nozzle, 245 °C, Box-fed filament, and provisional `counts_per_gf: 158.5` from the [video-assisted calibration](scale-calibration.md). The test did not run the maximum-flow search. An explicit envelope supplied flows 4, 10, and 18 with nominal XY acceleration 5000 and no line geometry; upstream's missing-geometry fallback used **300 mm/s² E acceleration**. These are not measurements of a matrix of XY accelerations.

Each pass ran `QIDI_PA_MEASURE TEMP=245 BLOCKS=12 AMP=0.5`, with the upstream defaults of five cycles and 200 ms legs. Upstream defines this amplitude as a total low-to-high difference of 50% of mean feed: the peaks were 5, 12.5, and 22.5 mm³/s, not 6, 15, and 27. Its own priming and inter-block wiping remained active.

The table command was `QIDI_PA_TABLE RUNS=2 ACCEL_LO=2000 ACCEL_HI=10000`. Duplicate K values at both acceleration endpoints make the output acceleration-independent. They do not demonstrate acceleration independence on this printer.

There was one initial G28 and no homing between flows or runs. Both passes completed successfully, including fan-assisted cooldown below 80 °C. Temporary modules and include wiring were removed afterward; original config SHA-256 `0324fbdc4f636abcc6ef8df94181df4e1dc3e6706a0a93b88d7197f06220c4b1` was verified before restoration. A final service restart unloaded the commands, and pre-test runtime PA/motion settings were restored. The run uses origin taring internally; no same-process capture-to-probe equivalence or post-test probe-accuracy result is claimed.

## Why the earlier comparison was insufficient

The upstream implementation differs materially from our earlier prototypes:

- Twelve blocks provide roughly 60 candidate rising transitions per flow, versus only a few in the shortened experiments.
- It primes 100 mm³ at the point's own flow and uses its own wipe/reprime schedule. Our initial conditioning was much smaller and included a 30-second wait.
- It estimates K from rising transitions, leaving falling transitions as diagnostics. A shared rise/fall time constant was therefore not an equivalent estimator.
- It uses actual queued block duration for transition boundaries, corrected request timing, direct integral regression, and its own rejection rules.

These differences are plausible contributors, not individually proven causes. The live comparison supports reproducing and isolating those methodological differences before declaring response-time calibration unworkable. An independently authored implementation and printed validation remain outstanding.

## Additional Q2 evidence

Inspected https://github.com/jordy1597/qidi-q2-stock-autopa at `f22209a4ce10350f6aa1e877f24763517e4ca4d9`; no Q2 code was installed or executed on the Max 4.

That project reports the CS1237/`probe_air` path at approximately 37–40 host samples/s and adapts G0BL1N/autopa. Its documented sweep uses 17 applied-PA candidates, five repetitions each, longer segments, and a small X wobble to make moves PA-eligible. This is **not** the Buddman69 response-time estimator. Its field report gives PETG K = 0.0334 at 265 °C, but that different printer, material setup, and temperature are not validation of this Max 4's result.

Its adapter calls `sensor_helper.read_origin_data()` and describes itself as read-only. Our Max 4 firmware investigation found reference-changing behavior on that path; the Q2 description must not be assumed to establish read-only behavior here. Shared interface names do not prove identical firmware semantics or load-cell scaling.
