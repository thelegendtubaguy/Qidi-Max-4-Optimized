# Qidi Max 4 Optimized

Opinionated and tuned configs to make your QIDI Max 4 run the way it should.

> [!NOTE]
> If you want to help support content like this, consider subscribing over on [YouTube](https://youtube.com/@TubaMakes)!

For stock QIDI-shipped configs and firmware-version snapshots, see [Qidi-Max4-Defaults](https://github.com/thelegendtubaguy/Qidi-Max4-Defaults).

> [!NOTE]
> Stock slicer G-code and stock machine files remain compatible with the current config changes. The repo's custom slicer G-code packs are optional and opt in to the optimized flow through separate `OPTIMIZED_*` macros.

> [!WARNING]
> If you update the printer's firmware, it will wipe these changes away.

> [!WARNING]
> These configurations were created and tested using a printer with a single Qidi box.  They likely work with no Qidi box and multiple Qidi boxes, just something to keep in mind.

## What's in this repo

- `config/`: Klipper configuration, macros, machine settings, and included support configs.
- `docs/`: repo-local technical notes, flow documentation, and reference notes.
- `orcaslicer_gcode/`: OrcaSlicer custom G-code snippets for this machine.
- `qidistudio_gcode/`: QIDI Studio custom G-code snippets for this machine.
- `scripts/`: local formatting and validation helpers used by this repo.

## Documentation

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
