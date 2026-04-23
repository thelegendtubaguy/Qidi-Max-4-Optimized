# Qidi Max 4 Optimized

An opinionated QIDI Max 4 Klipper and slicer configuration.

## Install

1. On the printer, run the repo installer command for this repository.
2. In your slicer, replace the machine G-code with the files from this repo:
   - OrcaSlicer: `orcaslicer_gcode/`
   - QIDI Studio: `qidistudio_gcode/`
3. Use the slicer pack that matches your slicer. OrcaSlicer and QIDI Studio use different placeholder syntax.

## Summary

- Installs optimized Klipper macros for supported QIDI Max 4 firmware and expects the matching slicer machine G-code from this repo.
- Keeps the OrcaSlicer and QIDI Studio machine G-code packs functionally aligned while preserving each slicer's own variable syntax.
- Uses the stock QIDI Max 4 defaults repo as the baseline for stock behavior and firmware snapshots: `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`

## Documentation

<<<<<<< HEAD
- [`docs/current_config_results_vs_stock_qidi_configs.md`](docs/current_config_results_vs_stock_qidi_configs.md)
  - Verified config and behavior differences between this repo and the stock QIDI Max 4 baseline.
- [`docs/optimized_slicer_start_temperature_flow.md`](docs/optimized_slicer_start_temperature_flow.md)
  - `HOTENDTEMP` / `PURGETEMP` flow through the optimized slicer start path and the related optimized macros.
- [`docs/box_print_start_notes.md`](docs/box_print_start_notes.md)
  - Reverse-engineering notes for `BOX_PRINT_START`, box-side filament prep behavior, and the vendor box stack.
- [`docs/installer_runtime_contract.md`](docs/installer_runtime_contract.md)
  - Installer runtime plan, TUI statuses, package version validation, zipped backup flow, and guarded patch reporting.
=======
- [Temperature Flow From The Optimized Orca And QIDIStudio Start G-Code](docs/orca-hotendtemp-purgetemp-flow.md): temperature timeline for the repo's optimized slicer packs through the active box-prep and prime-line sequence.
- [QIDI Box Implementation Notes](docs/box_print_start_notes.md): reverse-engineering notes for QIDI's vendor-implemented `BOX_PRINT_START` and related box internals.
- [Current Config Results Vs Stock QIDI Configs](docs/current-config-results-vs-stock-qidi-configs.md): summary of behavior changes and estimated time impact versus the stock configs shipped by QIDI.

## How to use this repo

_There will be a scripted installer in the future if you'd rather wait for that_

- Review changes between your configs and what's present in `config` and merge intentionally rather than copying everything blindly onto a printer.
- Expect some values to remain machine-specific, especially offsets, saved state, and hardware integration details.
- If you keep the stock slicer machine G-code, the stock-named Klipper macro flow will continue to work.
- If you want the optimized start, end, and toolchange flow, copy over the slicer G-code for either Orca (`orcaslicer_gcode/`) or QIDI Studio (`qidistudio_gcode/`) into your slicer's machine settings. Both packs are kept functionally in sync even though their placeholder syntax differs.

## Validation

- Use `python3 scripts/format_klipper_configs.py` to format editable Klipper config files in `config/`.
- The formatter intentionally skips `config/fluidd.cfg` and `config/saved_variables.cfg`, and preserves the auto-generated `SAVE_CONFIG` block.
- Use `python3 scripts/check_optimized_slicer_macros.py` to verify that the optimized OrcaSlicer and QIDI Studio G-code packs only reference commands and macros that exist in this repo.
- GitHub Actions runs both checks on pull requests.

## Important notes

- Main printer and box MCU serial identifiers are redacted where applicable.
- If you need to recover your own machine's specific device IDs, inspect `/dev/serial/by-id` on the printer via ssh with `ls -l /dev/serial/by-id/` and use the matching entries.
- On-device, `config/fluidd.cfg` is read-only; behavior changes should be implemented in other files under `config/`.
- Vendor-specific features and macros are present, including `multi_color_controller`, `box_config`, `probe_air`, and `closed_loop`.
- This machine uses nozzle contact probing via `probe_air`, so `SCREWS_TILT_CALCULATE` can use the direct screw XY positions in `config/printer.cfg`.
>>>>>>> 652c2a2c0ea6397351fc97cdf83db589aef9b051
