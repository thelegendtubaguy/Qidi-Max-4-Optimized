# Qidi Max 4 Optimized

This repository is an opinionated, tuned configuration set for the QIDI Max 4.

It is:

- a curated Klipper macro and config set aimed at the behavior this repo wants from the printer
- a place to keep the paired OrcaSlicer and QIDI Studio custom G-code in sync with those configs
- a reference for the docs and reverse-engineering notes needed to maintain that setup

For stock QIDI-shipped configs and firmware-version snapshots, see [Qidi-Max4-Defaults](https://github.com/thelegendtubaguy/Qidi-Max4-Defaults).

> [!WARNING]
> These configs are tuned around a Max 4 Combo setup with a QIDI Box. If you are running a plain Max 4 or different hardware, review the box, startup, and filament flows before using them.

## What's in this repo

- `config/`: active Klipper configuration, macros, machine settings, and included support configs.
- `docs/`: repo-local technical notes, flow documentation, and reference notes.
- `orcaslicer_gcode/`: OrcaSlicer custom G-code snippets for this machine.
- `qidistudio_gcode/`: QIDI Studio custom G-code snippets for this machine.

## Documentation

- [Temperature Flow From Orca And QIDI Studio Start G-Code](docs/orca-hotendtemp-purgetemp-flow.md): temperature timeline from the OrcaSlicer and QIDI Studio start gcode through the active box-prep and prime-line sequence.
- [QIDI Box Implementation Notes](docs/box_print_start_notes.md): reverse-engineering notes for QIDI's vendor-implemented `BOX_PRINT_START` and related box internals.
- [Current Config Results Vs Stock QIDI Configs](docs/current-config-results-vs-stock-qidi-configs.md): summary of behavior changes and estimated time impact versus the stock configs shipped by QIDI.

## How to use this repo

- Treat the files in `config/` as this repo's intended tuned baseline, not as a drop-in stock profile.
- Compare against [Qidi-Max4-Defaults](https://github.com/thelegendtubaguy/Qidi-Max4-Defaults) if you want to see what QIDI shipped for a given firmware version.
- Review changes and merge intentionally rather than copying everything blindly onto a printer.
- Expect some values to remain machine-specific, especially offsets, saved state, and hardware integration details.

## Formatting

- Use `python3 scripts/format_klipper_configs.py` to format editable Klipper config files in `config/`.
- The formatter intentionally skips `config/fluidd.cfg` and `config/saved_variables.cfg`, and preserves the auto-generated `SAVE_CONFIG` block.

## Slicer G-code

- This repo includes custom slicer G-code in `orcaslicer_gcode/` and `qidistudio_gcode/`.
- The two slicer packs are meant to behave the same way, even though their placeholder syntax differs.
- Use these snippets as the baseline for start/end, layer-change, pause, timelapse, and filament-change hooks on this printer.

## Stock Configs

- Stock QIDI-shipped configs and firmware-version snapshots are tracked at [Qidi-Max4-Defaults](https://github.com/thelegendtubaguy/Qidi-Max4-Defaults).
- Use that repo when you want to compare the tuned configs here against what QIDI shipped for a given firmware release.

## Important notes

- This repo is QIDI Max 4 specific; treat it as a platform-focused reference, not a universal Klipper profile.
- The active macro flow here assumes a QIDI Box is present and enabled (`box_count >= 1`, `enable_box = 1`).
- If you are not using a QIDI Box, review and adjust box-related startup and filament macros before using this config set as-is.
- Main printer and box MCU serial identifiers are redacted where applicable.
- On-device, `config/fluidd.cfg` is read-only; behavior changes should be implemented in other files under `config/`.
- Vendor-specific features and macros are present, including `multi_color_controller`, `box_config`, `probe_air`, and `closed_loop`.
