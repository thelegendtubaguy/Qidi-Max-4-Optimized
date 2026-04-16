# Current Config Results Vs Stock QIDI Configs

For stock baselines and firmware-version snapshots, see `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`.

## Behavior Changes

- Print start and tool prep spend less fixed dead time. Key waits were trimmed in homing, cutter, and probe flows.
- XY homing runs faster and with shorter post-home clearances, reducing non-print travel time before calibration and print start.
- Axis-specific homing no longer silently no-ops: `G28 X` and `G28 Y` run dedicated single-axis routines, and `G28 Z` now uses a safe Z-only path when XY is known or falls back to full home otherwise.
- Homing now restores the configured printer `max_accel` after `G28` instead of leaving runtime acceleration at the stock `10000` limit.
- Bed mesh flow now supports a Z-safe path (`G29_ZSAFE`) that skips redundant XY re-home when XY is already homed.
- Nozzle cleaning now uses tunable purge volumes with lower defaults (`prime=4mm`, `purge=50mm`, `retract=4mm`), reducing filament waste while keeping the wipe/cool routine.
- Front prime-line heat-up now waits `8mm` left of the real line start, then lowers to `Z0.5` and slides onto the start point before dropping to first-layer Z and printing the line.
- Front prime-line ending now adds a small `0.2mm` retract before the Z-lift so the nozzle is not left pressurized during the post-line setup block.
- Fresh-load startup still targets `140C` before probing, but it now leaves the waste chute for the bed-scrape phase once the nozzle cools to `150C` instead of hard-waiting to `140C` first.
- Retained-tool startup reuse now does a chute-side wipe-only cleanup before probing, without re-running the later nozzle-on-bed scrape path.
- Retained-tool startup reuse is now guarded by slot mapping, sync state, and saved slot material/vendor IDs instead of trusting only the last retained tool index.
- Rear cleanup polar-cooler use now honors the saved `enable_polar_cooler` flag and defaults off when that value is unset.
- Paused-print recovery now uses a tunable waste-chute purge length (`resume_purge_length=100mm`) instead of the stock fixed `250mm` resume purge.
- Paused-print recovery now restores a tunable idle timeout (`resume_idle_timeout=43200s`) instead of leaving the 72-hour pause timeout in place.
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
| Filament cut cycle (`CUT_FILAMENT_1`) | Skips stock's final `G4 P2000` dwell and keeps a faster cutter exit move | `~1.9s` per cut | Print start/toolchange cut |
| Nozzle clean (`CLEAR_NOZZLE` defaults) | Prime/purge defaults changed from `5/250` to `4/50` mm | `~40.8s` per default clean | Any default `CLEAR_NOZZLE` call |
| Pause resume | `resume_purge_length` reduced from stock `250` to `100` mm at `F300` | `~30s` per resume | After manual pause resumes |
| Startup box flush | Flush after load is now optional (`start_box_flush_after_load`) | Variable, often `10s+` | If disabled |
