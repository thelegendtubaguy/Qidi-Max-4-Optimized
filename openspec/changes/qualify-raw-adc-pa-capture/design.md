## Context

[Local firmware findings](local-firmware-findings.md) correct the CS1237 handler map using table layout, dispatcher instructions, host bindings, and synthetic execution. Raw reads attempt acquisition but can return old or empty buffers. Responses have no conversion timestamp, sequence, or freshness flag. Origin reads mutate the probing reference. The stock synchronous wrapper can retransmit after receiving a response during its wait.

These findings justify an acquisition experiment, not production calibration. Recorded physical force response and repeatability failures remain observations. The old identity filter cannot prove distinct conversion counts or transport loss. No printer was contacted during this local correction.

## Goals / Non-Goals

Goals:
- Determine whether stock non-zeroing raw acquisition yields a useful, repeatable PA signal.
- Preserve probing state and retain enough evidence to separate payload anomalies, host timing, and physical variation.
- Build a bounded offline-tested harness before seeking hardware authorization.
- Judge eventual PA candidates through repeated/reordered trials and printed comparisons, accepting a useful range rather than insisting on exact timestamps.

Non-goals:
- Enable calibration, automatically apply PA, or change production start/homing behavior.
- Replace MCU firmware, use homing acquisition, or claim process-local ownership prevents every vendor-side collision.
- Port autopa wholesale, introduce XY wobble, or reuse AGPL source without a separate licensing decision.

## Decisions

### Use nonblocking raw requests, not the origin adapter

Use the correctly mapped raw command through a non-retrying send path and temporary OID-scoped response handling. Keep at most one request outstanding. Record a local request ordinal and host send/receive times as bookkeeping, never as proof of conversion identity. Preserve every callback, including equal payloads/timestamps and unexpected or late responses, within a fixed record budget. Overflow invalidates and ends capture instead of silently dropping evidence.

Set explicit request, duration, response, and per-request deadline limits before taking ownership. Deadline failure stops without host retransmission or further requests. Firmware-internal retry behavior remains a documented limitation. Do not use `read_origin_data()`, zeroing, configuration-register reads, ADC reconfiguration, homing setup, or periodic polling start/stop as acquisition or cleanup operations.

### Make ownership and cleanup testable

Reject an existing response-handler owner rather than replacing it. Acquire the process-local lease before capture, release it idempotently on every terminal path, and unregister only the owned handler. Shutdown, cancellation, timeout, malformed input, and disconnect all stop sends. Distinguish empty, invalid/sentinel, stale-possible, unexpected, and timed-out responses; equal values alone cannot classify staleness.

Late responses have no request token. Define a bounded drain/quarantine policy that prevents their attribution to a later capture; if safe separation cannot be established, refuse another capture until explicit recovery. Never silently commandeer stock handling. Offline tests must cover this boundary before selecting the runtime API.

### Begin with read-only state checks and cold-idle capture

Verify supported firmware/bindings without sensor configuration reads. Observe correctly mapped homing status and stored reference before and after capture. Check commands must also have bounded, non-retrying behavior. A reference change, armed homing state, or unverifiable post-state invalidates capture and blocks continued experimentation pending recovery. These checks do not by themselves prove physical safety or exclusive MCU pin ownership.

The first separately authorized hardware test requires the printer skill's first-contact print-state guard, idle printer, cold heaters, no motion/extrusion, and no zero/configuration/periodic-start commands. A raw sensor sentinel can trigger firmware shutdown; cold testing is not risk-free.

### Qualify practical usefulness in stages

After successful cold-idle characterization, seek separate authorization for bounded conditioned extrusion with existing motion, chute-clearing, extrusion-budget, and restoration safeguards. Establish repeatability at fixed K, then repeat and reorder K trials to expose drift and conditioning effects. Record noise, payload anomalies, effective rate, host stalls, signal discrimination, and uncertainty without assigning receive time as conversion time.

Printed comparisons must show a stable useful PA value or range. Exact conversion timestamps are not an independent acceptance goal, but timing/staleness uncertainty must not dominate the recommendation. If the signal is inconclusive, report inconclusive and retain disabled gates. Firmware changes are considered only after stock acquisition is exhausted. The broader calibration change's deterministic timing/grid requirements need an explicit later reconciliation, not silent weakening here.

## Risks / Trade-offs

- No conversion identity → one outstanding request limits ambiguity but cannot prove fresh conversions; hardware characterization remains necessary.
- MCU-internal zero/all-ones retries and `weight_error` shutdown → retain raw records and stop on anomalies; no automatic retry loops.
- Shared vendor sensor ownership → process-local leases are insufficient proof; restrict experiments to guarded idle operation and inspect state before/after.
- Reference-mutating origin implementation still exists → leave `CALIBRATION_ENABLED`, `DIRECT_CAPTURE_ENABLED`, and `ORIGIN_CAPTURE_ENABLED` false; new harness access must be independently source-gated and off by default.
- Scratch evidence is not durable → preserve sanitized reproducible scripts/results before relying on them for hardware qualification; do not bundle vendor firmware or private hardware identifiers.

## Migration Plan

This documentation-only change has no installation or version bump. Future installed-code changes must advance the package version and changelog, retain disabled gates, and pass core and bundle validation. Rollback of experimental capture is removal/disablement of its source gate, not zeroing or ADC reconfiguration. State uncertainty requires an explicit recovery procedure before probing resumes.

## Open Questions

- What fraction of raw replies are stale, empty, invalid, or physically noisy at conservative rates?
- Can the host API provide bounded handler ownership and late-response quarantine without disrupting stock code?
- Does sustained idle capture preserve probing state and subsequent stock probe behavior?
- Which conditioning and excitation schedule separates K effects from drift well enough for print validation?
