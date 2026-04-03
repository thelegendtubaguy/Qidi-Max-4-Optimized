# Current Config Results Vs Stock QIDI Configs

For stock baselines and firmware-version snapshots, see `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`.

## Behavior Changes

- Print start and tool prep spend less fixed dead time. Key waits were trimmed in homing, cutter, and probe flows.
- XY homing runs faster and with shorter post-home clearances, reducing non-print travel time before calibration and print start.
- Bed mesh flow now supports a Z-safe path (`G29_ZSAFE`) that skips redundant XY re-home when XY is already homed.
- Nozzle cleaning now uses tunable purge volumes with lower defaults (`prime=4mm`, `purge=50mm`, `retract=4mm`), reducing filament waste while keeping the wipe/cool routine.
- Multi-color/toolchange flow is more controllable: `CUT_FILAMENT_TC` adds a wrapper for cutter mode selection, and startup box flush is now optional (`start_box_flush_after_load`) instead of always forced.
- End-of-print cooling is improved with a timed chamber/exhaust fan cooldown macro (`END_FAN_COOLDOWN`), so post-print heat is evacuated without leaving fans running indefinitely.
- Electronics cooling was strengthened by increasing board fan run speed (`0.6` to `0.9`) and adding a controller fan idle timeout.
- Slicer integration is explicit in-repo: custom G-code packs for OrcaSlicer and QIDI Studio are included and aligned with the current macros.

## Estimated Time Impact

> These are command-time estimates from fixed waits and commanded extrusion or motion. Real wall-clock time still depends on heating, planner behavior, and print conditions.

| Phase | Optimization | Estimated time saved | Typical trigger |
| --- | --- | ---: | --- |
| Start: box prep loop | `16x` wait reduced from `G4 P100` to `G4 P10` | `~1.44s` | Box-enabled startup |
| Homing (`G28` full XYZ) | Homing settle waits moved to shorter globals (`400/200ms` class waits to `50/20ms`) | `~1.95s` per full home | Print/calibration homing |
| Bed mesh save (`g29`/`g29_zsafe`) | Post-mesh wait reduced from `G4 P5000` to `G4 P500` | `~4.5s` | When a mesh is recalculated |
| Preheat stabilization | `start_bed_heat_delay` reduced from `2000` to `1000` | `~1.0s` | When bed is not already at target |
| Filament cut cycle (`CUT_FILAMENT_1`) | Multiple waits reduced plus faster cutter exit move | `~3.1s` per cut | Print start/toolchange cut |
| Nozzle clean (`CLEAR_NOZZLE` defaults) | Prime/purge defaults changed from `5/250` to `4/50` mm | `~40.8s` per default clean | Any default `CLEAR_NOZZLE` call |
| Startup box flush | Flush after load is now optional (`start_box_flush_after_load`) | Variable, often `10s+` | If disabled |
