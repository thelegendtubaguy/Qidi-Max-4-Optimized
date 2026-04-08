# Qidi Max 4 Optimized

Opinionated and tuned configs to make your QIDI Max 4 run the way it should.

> [!NOTE]
> If you want to help support content like this, consider subscribing over on [YouTube](https://youtube.com/@TubaMakes)!

For stock QIDI-shipped configs and firmware-version snapshots, see [Qidi-Max4-Defaults](https://github.com/thelegendtubaguy/Qidi-Max4-Defaults).

> [!WARNING]
> If you use this current configuration, the files included on the printer will not work.  I may fix this in the future.

> [!WARNING]
> If you update the printer's firmware, it will wipe these changes away.

> [!WARNING]
> These configurations were created and tested using a printer with a single Qidi box.  They likely work with no Qidi box and multiple Qidi boxes, just something to keep in mind.

## What's in this repo

- `config/`: Klipper configuration, macros, machine settings, and included support configs.
- `docs/`: repo-local technical notes, flow documentation, and reference notes.
- `orcaslicer_gcode/`: OrcaSlicer custom G-code snippets for this machine.
- `qidistudio_gcode/`: QIDI Studio custom G-code snippets for this machine.

## Documentation

- [Temperature Flow From Orca And QIDIStudio Start G-Code](docs/orca-hotendtemp-purgetemp-flow.md): temperature timeline from the OrcaSlicer and QIDIStudio start gcode through the active box-prep and prime-line sequence.
- [QIDI Box Implementation Notes](docs/box_print_start_notes.md): reverse-engineering notes for QIDI's vendor-implemented `BOX_PRINT_START` and related box internals.
- [Current Config Results Vs Stock QIDI Configs](docs/current-config-results-vs-stock-qidi-configs.md): summary of behavior changes and estimated time impact versus the stock configs shipped by QIDI.

## How to use this repo

_There will be a scripted installer in the future if you'd rather wait for that_

- Review changes between your configs and what's present in `config` and merge intentionally rather than copying everything blindly onto a printer.
- Expect some values to remain machine-specific, especially offsets, saved state, and hardware integration details.
- Copy over the slicer gcode for either Orca (`orcaslicer_gcode/`) or QIDIStudio (`qidistudio_gcode/`) into your printer's machine gcode inside the slicer.  Both Orca and QIDIStudio changes should behave the same way, even though some syntax differs.

## Formatting

- Use `python3 scripts/format_klipper_configs.py` to format editable Klipper config files in `config/`.
- The formatter intentionally skips `config/fluidd.cfg` and `config/saved_variables.cfg`, and preserves the auto-generated `SAVE_CONFIG` block.

## Important notes

- Main printer and box MCU serial identifiers are redacted where applicable.
- On-device, `config/fluidd.cfg` is read-only; behavior changes should be implemented in other files under `config/`.
- Vendor-specific features and macros are present, including `multi_color_controller`, `box_config`, `probe_air`, and `closed_loop`.
- This machine uses nozzle contact probing via `probe_air`, so `SCREWS_TILT_CALCULATE` can use the direct screw XY positions in `config/printer.cfg`.
