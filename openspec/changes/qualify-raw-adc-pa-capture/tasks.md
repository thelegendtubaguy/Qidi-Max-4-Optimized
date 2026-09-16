## 1. Correct and preserve evidence

- [x] 1.1 Record corrected handler mapping, artifact hashes, local harness results, and limitations; retract cache-only raw and passive-origin conclusions without rewriting physical measurements.
- [ ] 1.2 Preserve sanitized offline reproduction scripts and results for table/dispatcher mapping, host bindings, raw/zero/read-only cases, and retry-wrapper behavior; exclude vendor binaries and private identifiers.

## 2. Implement an offline-tested characterization harness

- [ ] 2.1 Inspect host send/handler APIs and implement independently source-gated, bounded nonblocking raw capture with one outstanding request, explicit deadlines, and no host retransmission. Keep all three existing capture/calibration gates false.
- [ ] 2.2 Add exclusive ownership, owned-handler cleanup, cancellation/shutdown handling, and bounded late-response quarantine; refuse subsequent capture when separation is uncertain.
- [ ] 2.3 Add bounded read-only homing/reference pre/post checks and raw evidence output; distinguish empty, malformed/sentinel, unexpected, missing, and stale-possible data without timestamp/payload deduplication.
- [ ] 2.4 Extend existing offline lifecycle coverage for success, ownership conflict, deadlines, cancellation/disconnect, late replies, equal payload/timestamps, limits, and unverifiable state. Confirm no zero/configuration/periodic-start commands are sent.
- [ ] 2.5 Correct or retire misleading disabled origin-adapter assumptions without enabling it. Advance package version/changelog if installed contents change; run core tests, known-version checks, bundle smoke, and strict OpenSpec validation.

## 3. Separately authorized hardware qualification

- [ ] 3.1 Obtain explicit authorization and apply the printer skill's first-contact guard; perform conservative cold-idle raw capture with no motion, extrusion, zeroing, configuration, or periodic-start command. Record firmware identity and before/after homing/reference state.
- [ ] 3.2 Characterize usable cadence, host stalls, empty/invalid/stale-possible replies, reference stability, cleanup, and safe recovery. Stop on uncertainty; separately authorize any stock probing validation.
- [ ] 3.3 Only after idle qualification and further authorization, test bounded conditioned extrusion with chute clearing and restoration; establish fixed-K repeatability before sweeping.
- [ ] 3.4 Repeat and reorder K trials and compare prints; report a useful PA range or an inconclusive result with uncertainty, rather than demanding perfect timestamps or automatically applying PA.

## 4. Reconcile the calibration decision

- [ ] 4.1 Update observations and the pending broader calibration design with hardware evidence; explicitly reconcile timing/grid acceptance criteria before any later enablement proposal.
- [ ] 4.2 Record whether stock acquisition is adequate, needs further bounded experiments, or is exhausted. Keep production disabled until the broader calibration safety and quality requirements are independently met.
