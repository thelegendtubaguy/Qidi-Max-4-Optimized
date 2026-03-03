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
- `orcaslicer_gcode/`: optimized OrcaSlicer custom G-code snippets for this machine.
- `qidistudio_gcode/`: QIDI Studio custom G-code snippets retained for reference.

## How to use this repo

- Use the current files in `config/` as the optimized baseline for QIDI Max 4 tuning and macro behavior.
- As part of the optimization pass, original QIDI Chinese comments were translated to English for readability and maintenance.
- Use git tags/history to inspect config snapshots associated with QIDI firmware releases.
- Compare your local printer files against this repo before applying changes; merge intentionally rather than copying everything blindly.

## Optimized branch results vs `main`

- Print start and tool prep spend less fixed dead time. Key waits were trimmed in homing, cutter, and probe flows (for example: mesh save wait reduced from `5.0s` to `0.5s`, and one cutter sequence reduced from about `3.2s` of fixed waits to about `0.22s`).
- XY homing runs faster and with shorter post-home clearances, reducing non-print travel time before calibration and print start.
- Bed mesh flow now supports a Z-safe path (`G29_ZSAFE`) that skips redundant XY re-home when XY is already homed, so recalibration overhead is lower in common start sequences.
- Nozzle cleaning now uses tunable purge volumes with lower defaults (`CLEAR_NOZZLE` defaults changed from heavy purge behavior to `prime=4mm`, `purge=50mm`, `retract=4mm`), reducing filament waste while keeping the wipe/cool routine.
- Multi-color/toolchange flow is more controllable: `CUT_FILAMENT_TC` adds a wrapper for cutter mode selection, and startup box flush is now optional (`start_box_flush_after_load`) instead of always forced.
- End-of-print cooling is improved with a timed chamber/exhaust fan cooldown macro (`END_FAN_COOLDOWN`), so post-print heat is evacuated without leaving fans running indefinitely.
- Electronics cooling was strengthened by increasing board fan run speed (`0.6` to `0.9`) and adding a controller fan idle timeout.
- Slicer integration is now explicit in-repo: complete optimized custom G-code packs for OrcaSlicer and QIDI Studio are included and aligned with the branch macros.

### Estimated time impact (vs `main`)

> These are command-time estimates from fixed waits and commanded extrusion/motion; real wall-clock time still depends on heating, planner behavior, and print conditions.

| Phase | Optimization | Estimated time saved | Typical trigger |
| --- | --- | ---: | --- |
| Start: box prep loop | `16x` wait reduced from `G4 P100` to `G4 P10` | `~1.44s` | Box-enabled startup |
| Homing (`G28` full XYZ) | Homing settle waits moved to shorter globals (`400/200ms` class waits to `50/20ms`) | `~1.95s` per full home | Print/calibration homing |
| Bed mesh save (`g29`/`g29_zsafe`) | Post-mesh wait reduced from `G4 P5000` to `G4 P500` | `~4.5s` | When a mesh is recalculated |
| Preheat stabilization | `start_bed_heat_delay` reduced from `2000` to `1000` | `~1.0s` | When bed is not already at target |
| Filament cut cycle (`CUT_FILAMENT_1`) | Multiple waits reduced + faster cutter exit move | `~3.1s` per cut | Print start/toolchange cut |
| Nozzle clean (`CLEAR_NOZZLE` defaults) | Prime/purge defaults changed from `5/250` to `4/50` mm | `~40.8s` per default clean | Any default `CLEAR_NOZZLE` call |
| Startup box flush | Flush after load is now optional (`start_box_flush_after_load`) | Variable (often `10s+`) | If disabled |

## OrcaSlicer G-code

- This repo includes optimized OrcaSlicer custom G-code in `orcaslicer_gcode/`.
- Use these snippets as the baseline for OrcaSlicer start/end, layer-change, pause, timelapse, and filament-change hooks on this printer.

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
