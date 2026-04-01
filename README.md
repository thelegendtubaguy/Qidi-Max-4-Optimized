# QIDI Max 4 Combo Config Repository

> [!CAUTION]
> Use at your own risk!  If you brick your printer, that's a bad day.

> [!WARNING]
> This repo contains config files that have values tuned for the Max 4 Combo (with Qidi Box).  If you do not have a Qidi Box connected to your Max 4, you may need different values.

This repository has two goals:

1. Maintain an optimized QIDI Max 4 configuration set for daily printing.
2. Preserve QIDI-shipped configuration files from firmware releases as a reference archive.

## What's in this repo

- `config/`: active Klipper configuration, macros, machine settings, and included support configs.
- `docs/`: repo-local technical notes, flow documentation, and branch/reference notes.
- `orcaslicer_gcode/`: OrcaSlicer custom G-code snippets for this machine.
- `qidistudio_gcode/`: QIDI Studio custom G-code snippets for this machine.

## Documentation

- `docs/orca-hotendtemp-purgetemp-flow.md`: temperature timeline from the OrcaSlicer and QIDI Studio start gcode through the active box-prep and prime-line sequence.
- `docs/box_print_start_notes.md`: reverse-engineering notes for QIDI's vendor-implemented `BOX_PRINT_START` and related box internals.
- `docs/optimized-vs-main.md`: summary of optimized-branch behavior changes and estimated time impact versus stock `main`.

## How to use this repo

- Use the current files in `config/` as the optimized baseline for QIDI Max 4 tuning and macro behavior.
- As part of the optimization pass, original QIDI Chinese comments were translated to English for readability and maintenance.
- Use git tags/history to inspect config snapshots associated with QIDI firmware releases.
- Compare your local printer files against this repo before applying changes; merge intentionally rather than copying everything blindly.

## Formatting

- Use `python3 scripts/format_klipper_configs.py` to format editable Klipper config files in `config/`.
- The formatter intentionally skips `config/fluidd.cfg` and `config/saved_variables.cfg`, and preserves the auto-generated `SAVE_CONFIG` block.

## Slicer G-code

- This repo includes custom slicer G-code in `orcaslicer_gcode/` and `qidistudio_gcode/`.
- Use these snippets as the baseline for start/end, layer-change, pause, timelapse, and filament-change hooks on this printer.

## Firmware reference snapshots

- QIDI-shipped configurations are tracked in repository history and tags.
- To inspect a specific firmware snapshot, check out the relevant tag and review the files under `config/`.

## Important notes

- This repo is QIDI Max 4 specific; treat it as a platform-focused reference, not a universal Klipper profile.
- The active macro flow in this repo assumes a QIDI Box is present and enabled (`box_count >= 1`, `enable_box = 1`).
- If you are not using a QIDI Box, review and adjust box-related startup/filament macros before using this config set as-is.
- Some values remain machine-specific (offsets, wiring assumptions, saved state).
- Main printer and box MCU serial identifiers are redacted where applicable.
- On-device, `config/fluidd.cfg` is read-only; behavior changes should be implemented in other files under `config/`.
- Vendor-specific features/macros are present (for example `multi_color_controller`, `box_config`, `probe_air`, `closed_loop`).
