# QIDI Max 4 Combo Config Repository

> [!CAUTION]
> Use at your own risk!  If you brick your printer, that's a bad day.

> [!WARNING]
> This repo contains config files that have values tuned for the Max 4 Combo (with Qidi Box).  If you do not have a Qidi Box connected to your Max 4, you may need different values.

This repository has two goals:

1. Maintain an optimized QIDI Max 4 configuration set for daily printing.
2. Preserve QIDI-shipped configuration files from firmware releases as a reference archive.

> Host/UI note: this stack uses QIDI's forked Fluidd build (`v1.30.5-ab46ef6`).

## What's in this repo

- `config/printer.cfg`: main Klipper configuration (motion, heaters, fans, probe, bed mesh, includes).
- `config/klipper-macros-qd/`: QIDI-focused macro library (print start/end, status handling, homing, parking, filament and tool workflows).
- `config/KAMP/`: adaptive meshing and purge helpers.
- `config/box.cfg`, `config/box1.cfg`, `config/box2.cfg`, `config/box3.cfg`, `config/box4.cfg`: multi-color box/feed and tool macros (`T0` to `T15`).
- `config/moonraker.conf`, `config/crowsnest.conf`, `config/timelapse.cfg`: host, camera, and timelapse settings.
- `config/officiall_filas_list.cfg`, `config/drying.conf`: filament and drying presets.
- `config/MCU_ID.cfg`, `config/saved_variables.cfg`: MCU mapping and runtime state values.
- `config/fluidd.cfg`: included for completeness from the printer config set.

## How to use this repo

- Use the current files in `config/` as the optimized baseline for QIDI Max 4 tuning and macro behavior.
- As part of the optimization pass, original QIDI Chinese comments were translated to English for readability and maintenance.
- Use git tags/history to inspect config snapshots associated with QIDI firmware releases.
- Compare your local printer files against this repo before applying changes; merge intentionally rather than copying everything blindly.

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
