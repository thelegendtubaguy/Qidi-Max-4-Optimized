## Why

Corrected command-table analysis shows that stock `query_cs1237_read` attempts ADC acquisition, while `read_origin_data()` performs zeroing and changes the probing reference. Earlier cache-only and passive-origin interpretations are invalid. Historical noisy captures remain useful evidence, but do not settle whether a bounded stock raw collector can support a repeatable, practically useful PA recommendation.

## What Changes

- Correct the old research notes without rewriting physical measurements or claiming hardware validation.
- Plan a source-gated, bounded nonblocking raw-read characterization harness with exclusive ownership, explicit deadlines, no host retransmission, and preserved responses.
- Exclude origin zeroing, ADC configuration, periodic-start commands, and timestamp/payload deduplication from this capture path.
- Establish offline checks, then separately authorized cold-idle characterization before any conditioned extrusion or repeated/reordered PA trials.
- Keep production calibration and existing developer capture gates disabled. A useful, repeatable PA range validated by prints is the eventual objective, not perfect conversion timestamps.

## Capabilities

### New Capabilities

- `raw-adc-pa-qualification`: bounded experimental capture and staged evidence gates for stock CS1237 raw acquisition.

### Modified Capabilities

None. This follow-up qualifies an acquisition candidate; it does not enable or replace production printer behavior. The pending `add-load-cell-pa-calibration` change retains the broader calibration lifecycle and must reconcile its acceptance criteria with qualification evidence before enablement.

## Impact

This proposal updates research and planning only. Future implementation affects the experimental adapter and offline tests under `installer/`, with a package-version bump and changelog if installed contents change. It does not require stock config edits, MCU replacement, upstream autopa code reuse, slicer changes, or printer contact. No implementation or hardware test is authorized by creating these artifacts.

All load-cell research notes and capture evidence live in this change: [local firmware findings](local-firmware-findings.md), [reverse engineering](reverse-engineering.md), [observations and autopa assessment](qidi-load-cell.md), and `evidence/`. Other documents link here rather than maintain separate research notes. Scratch scripts are not yet a durable reproduction package. The existing disabled origin adapter remains unsafe to enable despite the corrected documentation.
