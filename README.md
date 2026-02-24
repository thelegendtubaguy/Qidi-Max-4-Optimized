# QIDI Max 4 Klipper/Fluidd Config Dump

This repository is a straight dump of my QIDI Max 4 `printer_data/config` directory.

It exists as a backup/reference for this specific machine, not as a universal profile for other printers.

> Host/UI note: this printer is running QIDI's forked Fluidd build: `v1.30.5-ab46ef6`.

## What is in this repo

- `config/printer.cfg`: main Klipper printer definition (kinematics, steppers, heaters, fans, probe, bed mesh, includes).
- `config/MCU_ID.cfg`: main MCU serial mapping (serial value redacted).
- `config/moonraker.conf`: Moonraker server/auth/timelapse settings.
- `config/crowsnest.conf`: webcam streaming configuration.
- `config/timelapse.cfg`: timelapse and hyperlapse macros.
- `config/fluidd.cfg`: client-side pause/resume/cancel macro wrappers.
- `config/klipper-macros-qd/`: main QIDI-focused macro library (start/end flow, status handling, homing, parking, temp/fan wrappers, filament actions).
- `config/KAMP/`: KAMP adaptive mesh/purge helper macros.
- `config/box.cfg`, `config/box1.cfg`, `config/box2.cfg`, `config/box3.cfg`, `config/box4.cfg`: multi-color box/feed system configs and tool macros (`T0` to `T15`), with box MCU serial redacted.
- `config/officiall_filas_list.cfg` and `config/drying.conf`: filament and drying preset data.
- `config/saved_variables.cfg`: runtime state snapshot (slot mappings, offsets, toggles, last profile, etc.).

## Public repo notes

- To see config files as shipped by QIDI for specific firmware versions, browse this repo's tags.
- Main printer MCU and box MCU serial identifiers have been intentionally redacted.
- This repo is safe to read as reference, but still reflects one physical machine's environment and wiring.
- If you publish your own dump, review it for hardware IDs, host/network details, and device paths before pushing.

## What this is (and is not)

This is a machine-specific snapshot. It includes hardware IDs, pin mappings, offsets, and stateful values from one printer.

Use it as a reference or backup source, not as a drop-in config for another system.

Do not copy these files wholesale to your printer. Copy only the sections/macros you understand and intentionally want, then merge them into your own config.

## Compatibility notes

- The config and macro comments are a mix of English and Chinese.
- Some sections/macros are vendor-specific or vendor-extended (for example: `multi_color_controller`, `box_config`, `probe_air`, `closed_loop`).
- Upstream Klipper/Fluidd docs are still useful, but behavior can differ on QIDI's forked stack.
