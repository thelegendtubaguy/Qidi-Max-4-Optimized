# Current_Config_Results_Vs_Stock_QIDI_Configs

Stock baseline for this file:
- `../Qidi-Max4-Defaults/config`
- `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`

Installer-managed optimized macro source paths in this file:
- `installer/klipper/tltg-optimized-macros/*.cfg`
- runtime destination on the printer: `config/tltg-optimized-macros/*.cfg`

Excluded from this file:
- comment translation only
- redacted hardware IDs in `config/MCU_ID.cfg` and `config/box.cfg`
- `SAVE_CONFIG` state blocks in `config/printer.cfg`
- state drift in `config/saved_variables.cfg` and `config/officiall_filas_list.cfg`

## Verified functional differences

### `config/printer.cfg`

- Adds `[include tltg-optimized-macros/*.cfg]` after `[include klipper-macros-qd/*.cfg]`.
- `installer/package.yaml` applies guarded runtime homing patches for supported firmware `01.01.06.02`:
  - `[stepper_x] homing_speed`: stock `50` -> repo `65`
  - `[stepper_x] second_homing_speed`: stock `50.0` -> repo `55.0`
  - `[stepper_x] homing_retract_dist`: stock `50.0` -> repo `20.0`
  - `[stepper_x] homing_retract_speed`: stock `200.0` -> repo `1000.0`
  - `[stepper_y] homing_speed`: stock `50` -> repo `65`
  - `[stepper_y] second_homing_speed`: stock `50.0` -> repo `55.0`
  - `[stepper_y] homing_retract_dist`: stock `50.0` -> repo `20.0`
  - `[stepper_y] homing_retract_speed`: stock `200.0` -> repo `1000.0`
  - `[stepper_z] homing_retract_dist`: stock `10.0` -> repo `5.0`

### `installer/klipper/tltg-optimized-macros/globals.cfg` -> runtime `config/tltg-optimized-macros/globals.cfg`

Adds optimized-only knobs that do not exist in stock `config/klipper-macros-qd/globals.cfg`:

- `variable_keep_loaded_between_prints: True`
- `variable_homing_settle_short: 20`
- `variable_homing_settle_long: 50`
- `variable_z_home_randomize_enable: True`
- `variable_z_home_randomize_radius: 6`
- `variable_move_to_z_travel_speed_xy: 40000`

### `installer/klipper/tltg-optimized-macros/kinematics.cfg` -> runtime `config/tltg-optimized-macros/kinematics.cfg`

- `OPTIMIZED_G28` replaces stock `homing_override` behavior for repo-managed entrypoints.
- `OPTIMIZED_G28` supports single-axis `X`, `Y`, and `Z` requests without collapsing them into the stock full-home path.
- `OPTIMIZED_G28` runs a Z-only path when `X` and `Y` are already homed; stock `G28 Z` falls back to the stock homing logic in `config/klipper-macros-qd/kinematics.cfg`.
- `OPTIMIZED_G28` uses `20/50ms` settle waits from `_tltg_optimized_globals`; stock `homing_override` uses `200/400ms` waits.
- `OPTIMIZED_G28` shortens XY backoff moves from stock `Y100` / `X-100` to `Y20` / `X-20` at `F24000`.
- `OPTIMIZED_G28` restores `printer.max_accel` at the end of homing; stock `homing_override` leaves runtime accel at `10000`.
- `_OPTIMIZED_MOVE_TO_Z_HOME_POINT` randomizes the XY touch point within `z_home_randomize_radius` around bed center before Z homing.

### `installer/klipper/tltg-optimized-macros/motion.cfg` -> runtime `config/tltg-optimized-macros/motion.cfg`

- `OPTIMIZED_MOVE_TO_TRASH` uses `OPTIMIZED_G28 O X Y` instead of stock `G28 O X Y`.
- `OPTIMIZED_MOVE_TO_TRASH` increases the final two chute-approach moves from stock `F2000` to `F3500`.

### `installer/klipper/tltg-optimized-macros/bed_mesh.cfg` -> runtime `config/tltg-optimized-macros/bed_mesh.cfg`

- `OPTIMIZED_G29_ZSAFE` skips redundant XY rehome when `X` and `Y` are already homed.
- `OPTIMIZED_G29_ZSAFE` reduces the post-mesh wait before `SAVE_CONFIG_QD` from stock `G4 P5000` to `G4 P500`.
- `OPTIMIZED_G29_ZSAFE` is called by the optimized print-start filament-prep path; stock `config/klipper-macros-qd/start_end.cfg` uses `g29`.

### `installer/klipper/tltg-optimized-macros/filament.cfg` -> runtime `config/tltg-optimized-macros/filament.cfg`

- `OPTIMIZED_CUT_FILAMENT` removes the stock cutter tail sequence `G1 X15 F3000` + `G4 P2000` and exits at `G1 X15 F8000`.
- `OPTIMIZED_START_PRINT_FILAMENT_PREP` adds a retained-filament reuse branch.
- The reuse branch is gated by all of:
  - `keep_loaded_between_prints`
  - `retained_tool_ready`
  - matching tool index
  - filament-present sensor state
  - matching `retained_slot`
  - matching `last_load_slot`
  - matching `slot_sync`
  - matching retained/current filament ID
  - matching retained/current vendor ID
- When the reuse gate passes, `OPTIMIZED_START_PRINT_FILAMENT_PREP` bypasses `BOX_PRINT_START` and runs chute-side cleanup plus `Z_TILT_ADJUST` and `OPTIMIZED_G29_ZSAFE`.
- When the reuse gate fails, `OPTIMIZED_START_PRINT_FILAMENT_PREP` calls `BOX_PRINT_START`, then `OPTIMIZED_EXTRUSION_AND_FLUSH`, then runs the later scrape/wipe sequence.
- `OPTIMIZED_EXTRUSION_AND_FLUSH` changes the stock flush sequence:
  - starts with `G1 E10 F300` instead of stock `G1 E50 F300`
  - runs two `G1 E60 F300` flush loops instead of stock two loops bracketed by `M106 S255` / `M106 S60`
  - keeps a fixed `G4 P5000` cleanup wait instead of stock `G4 P6000`
  - uses `OPTIMIZED_M1004`
- `OPTIMIZED_END_PRINT_FILAMENT_PREP` can retain the active box filament between prints instead of always unloading.
- `OPTIMIZED_UNLOAD_FILAMENT` clears retained-tool state before unloading and routes unload travel through `OPTIMIZED_MOVE_TO_TRASH`.

### `installer/klipper/tltg-optimized-macros/heaters.cfg` -> runtime `config/tltg-optimized-macros/heaters.cfg`

- Adds `OPTIMIZED_WAIT_HOTEND`, `OPTIMIZED_WAIT_BED`, and `OPTIMIZED_WAIT_CHAMBER`.
- These wrappers preserve explicit sub-status values during waits and are used by the optimized print-start path.
- `OPTIMIZED_WAIT_CHAMBER` explicitly stops `chamber_circulation_fan` before waiting on chamber heat.

### `installer/klipper/tltg-optimized-macros/cooling.cfg` -> runtime `config/tltg-optimized-macros/cooling.cfg`

- `OPTIMIZED_M1004` changes the unset default for `enable_polar_cooler` from stock `1` to `0`.
- `OPTIMIZED_END_FAN_COOLDOWN` adds a timed post-print `P3` chamber/exhaust fan run with delayed shutdown.

### `orcaslicer_gcode/` and `qidistudio_gcode/`

Both slicer packs now call repo-only optimized entrypoints.

Start G-code:
- `OPTIMIZED_PRINT_START_HOME`
- `OPTIMIZED_START_PRINT_FILAMENT_PREP`

Change-filament G-code:
- `OPTIMIZED_CUT_FILAMENT`
- `OPTIMIZED_MOVE_TO_TRASH`

Layer-change G-code:
- `OPTIMIZED_MOVE_TO_TRASH`

End G-code:
- `OPTIMIZED_END_PRINT_FILAMENT_PREP`
- `OPTIMIZED_MOVE_TO_TRASH`
- `OPTIMIZED_END_FAN_COOLDOWN`

The stock-named macros remain in `config/klipper-macros-qd/` for runtime compatibility. Repo-only behavior is sourced from `installer/klipper/tltg-optimized-macros/`, installed to runtime `config/tltg-optimized-macros/`, and called by the repo slicer packs.

## Not currently valid as config differences

Not found in current repo config:
- `resume_purge_length`
- `resume_idle_timeout`
- `start_box_flush_after_load`
- board-fan speed change from `0.6` to `0.9`
- controller-fan idle-timeout addition beyond stock baseline
