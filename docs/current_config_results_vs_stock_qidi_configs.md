# Current_Config_Results_Vs_Stock_QIDI_Configs

Stock baseline for this file:
- `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`

Installer-managed optimized macro source paths in this file:
- `installer/klipper/tltg-optimized-macros/*.cfg`

Excluded from this file:
- comment translation only
- redacted hardware IDs in `config/MCU_ID.cfg` and `config/box.cfg`
- `SAVE_CONFIG` state blocks in `config/printer.cfg`
- state drift in `config/saved_variables.cfg` and `config/officiall_filas_list.cfg`

## Functional differences

### `config/printer.cfg`

- Adds `[include tltg-optimized-macros/*.cfg]` after `[include klipper-macros-qd/*.cfg]`.
- `installer/package.yaml` applies guarded runtime stock-value patches for supported firmware `01.01.06.02`:
  - `[stepper_x] homing_speed`: stock `50` -> installer runtime `65`
  - `[stepper_x] second_homing_speed`: stock `50.0` -> installer runtime `55.0`
  - `[stepper_x] homing_retract_dist`: stock `50.0` -> installer runtime `20.0`
  - `[stepper_x] homing_retract_speed`: stock `200.0` -> installer runtime `1000.0`
  - `[stepper_y] homing_speed`: stock `50` -> installer runtime `65`
  - `[stepper_y] second_homing_speed`: stock `50.0` -> installer runtime `55.0`
  - `[stepper_y] homing_retract_dist`: stock `50.0` -> installer runtime `20.0`
  - `[stepper_y] homing_retract_speed`: stock `200.0` -> installer runtime `1000.0`
  - `[stepper_z] homing_retract_dist`: stock `10.0` -> installer runtime `5.0`
  - `[z_tilt] speed`: stock `150` -> installer runtime `600`
  - `[bed_mesh] speed`: stock `150` -> installer runtime `600`
  - `[virtual_sdcard] on_error_gcode`: stock `CANCEL_PRINT` -> installer runtime `OPTIMIZED_CANCEL_PRINT_ON_ERROR`
  - `config/klipper-macros-qd/kinematics.cfg [homing_override]`: stock section is deleted after its normalized SHA-256 matches `6a924478b351dea193bf1060f5747b151bba3de4c5627c7faac741ad7b164cf4`; normalization removes comments and whitespace outside quoted strings. Uninstall restores the stored section text when the section is still absent.

### `installer/klipper/tltg-optimized-macros/globals.cfg` -> runtime `config/tltg-optimized-macros/globals.cfg`

Adds optimized-only knobs that do not exist in stock `config/klipper-macros-qd/globals.cfg`:

- `variable_keep_loaded_between_prints: True`
- `variable_homing_settle_short: 20`
- `variable_homing_settle_long: 50`
- `variable_z_home_randomize_enable: True`
- `variable_z_home_randomize_radius: 6`
- `variable_move_to_z_travel_speed_xy: 40000`
- Adds `[delayed_gcode _tltg_optimized_startup_banner]` with `initial_duration: 6`.
- `_tltg_optimized_startup_banner` emits `TLTG Optimized Configs Installed v<package_version>` to the Klipper console after startup; `variable_package_version` in `installer/klipper/tltg-optimized-macros/globals.cfg` must match `installer/package.yaml package.version`.

### `installer/klipper/tltg-optimized-macros/kinematics.cfg` -> runtime `config/tltg-optimized-macros/kinematics.cfg`

- `installer/klipper/tltg-optimized-macros/kinematics.cfg [homing_override]` owns Fluidd/plain `G28` requests after the installer deletes QIDI's stock `[homing_override]` from `config/klipper-macros-qd/kinematics.cfg`.
- Optimized homing is invoked through `G28`; no `OPTIMIZED_G28` macro is installed.
- Optimized `[homing_override]` supports single-axis `X`, `Y`, and `Z` requests without collapsing them into the stock full-home path.
- Optimized `[homing_override]` runs a Z-only path when `X` and `Y` are already homed; stock `G28 Z` falls back to the stock homing logic in `config/klipper-macros-qd/kinematics.cfg`.
- Optimized `[homing_override]` uses `20/50ms` settle waits from `_tltg_optimized_globals`; stock `homing_override` uses `200/400ms` waits.
- Optimized `[homing_override]` shortens XY backoff moves from stock `Y100` / `X-100` to `Y20` / `X-20` at `F24000`.
- Optimized `[homing_override]` restores `printer.max_accel` at the end of homing; stock `homing_override` leaves runtime accel at `10000`.
- `_OPTIMIZED_MOVE_TO_Z_HOME_POINT` randomizes the XY touch point within `z_home_randomize_radius` around bed center before Z homing.

### `installer/klipper/tltg-optimized-macros/motion.cfg` -> runtime `config/tltg-optimized-macros/motion.cfg`

- `OPTIMIZED_MOVE_TO_TRASH` uses `G28 O X Y`; optimized `[homing_override]` handles the request.
- `OPTIMIZED_CANCEL_PRINT_ON_ERROR` cancels virtual-SD errors without parking or moving the toolhead; it turns off heaters/fans, disables the box heater through `OPTIMIZED_DISABLE_BOX_HEATER`, calls `_KM_CANCEL_PRINT_BASE`, restores pause state without movement when paused, runs `G31` to re-enable bed mesh on the next print start, and clears pause.
- `OPTIMIZED_MOVE_TO_TRASH` increases the final two chute-approach moves from stock `F2000` to `F3500`.
- `OPTIMIZED_MOVE_TO_TRASH` saves caller G-code state, forces `G90` for its absolute park moves, stores `printer.toolhead.max_accel`, and restores acceleration plus caller G-code state before returning.

### `installer/klipper/tltg-optimized-macros/bed_mesh.cfg` -> runtime `config/tltg-optimized-macros/bed_mesh.cfg`

- `OPTIMIZED_G29_ZSAFE` skips redundant XY rehome when `X` and `Y` are already homed.
- `OPTIMIZED_G29_ZSAFE` always clears the active bed mesh, homes Z or full axes through `_OPTIMIZED_G29_HOME_Z_OR_FULL`, and runs `BED_MESH_CALIBRATE PROFILE=kamp`; it does not load the saved `default` mesh based on `_km_globals.bedmesh_before_print`.
- `OPTIMIZED_G29_ZSAFE` reduces the post-mesh wait before `SAVE_CONFIG_QD` from stock `G4 P5000` to `G4 P500`.
- `OPTIMIZED_START_PRINT_FILAMENT_PREP` runs `M400` after each print-start `Z_TILT_ADJUST`, then inlines the same `BED_MESH_CLEAR` -> `_OPTIMIZED_G29_HOME_Z_OR_FULL` -> `BED_MESH_CALIBRATE PROFILE=kamp` -> `SAVE_CONFIG_QD` sequence instead of delegating through `OPTIMIZED_G29_ZSAFE`; stock `config/klipper-macros-qd/start_end.cfg` uses `g29`.

### `installer/klipper/tltg-optimized-macros/helpers.cfg` -> runtime `config/tltg-optimized-macros/helpers.cfg`

- Adds `[screws_tilt_adjust]`, which enables Klipper `SCREWS_TILT_CALCULATE` when `[include tltg-optimized-macros/*.cfg]` is active in `config/printer.cfg`.
- Reuses stock `[bed_screws]` positions from `config/printer.cfg`: `30,30`, `345,30`, `345,345`, and `30,345`.
- Sets `screw1_name: Front left`, `screw2_name: Front right`, `screw3_name: Rear right`, and `screw4_name: Rear left`; `screw1` is the calculation reference screw.
- Sets `speed: 150`, `horizontal_move_z: 5`, and `screw_thread: CW-M4`.
- Adds `TLTG_PROBE_ACCURACY_CENTER`, which homes with `G28`, moves to `X195 Y195 Z10`, and runs `PROBE_ACCURACY` with `SAMPLES=20` unless overridden.
- Adds `TLTG_CORNER_BED_SCREW_CHECK`, which homes with `G28`, runs `Z_TILT_ADJUST`, and runs `SCREWS_TILT_CALCULATE`.

### `installer/klipper/tltg-optimized-macros/filament.cfg` -> runtime `config/tltg-optimized-macros/filament.cfg`

- `OPTIMIZED_CUT_FILAMENT` removes the stock cutter tail sequence `G1 X15 F3000` + `G4 P2000` and exits at `G1 X15 F8000`.
- `OPTIMIZED_CUT_FILAMENT` saves caller G-code state, forces `G90` for cutter travel, forces `M83` for the cutter retract, stores `printer.toolhead.max_accel`, and restores acceleration plus caller G-code state before returning.
- `OPTIMIZED_START_PRINT_FILAMENT_PREP` runs `G31` before retained-filament branch selection for compatibility with stock `g29` state; the optimized print-start mesh sequence always runs `BED_MESH_CALIBRATE PROFILE=kamp` and does not branch on `_km_globals.bedmesh_before_print`.
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
- When the reuse gate passes, `OPTIMIZED_START_PRINT_FILAMENT_PREP` bypasses `BOX_PRINT_START` and runs chute-side cleanup plus `Z_TILT_ADJUST` and an inline `BED_MESH_CALIBRATE PROFILE=kamp` sequence.
- When the reuse gate fails and the QIDI Box stack is enabled, `OPTIMIZED_START_PRINT_FILAMENT_PREP` calls vendor `BOX_PRINT_START` with `HOTENDTEMP={purge_temp}`, then `OPTIMIZED_EXTRUSION_AND_FLUSH` with `PURGETEMP={purge_temp}`, then re-homes Z before running the later scrape/wipe sequence.
- The box fresh-load branch stages from the post-scrape rear-bed position to the first `Z_TILT_ADJUST` point with `G1 X15 Y202.5 F36000`.
- `_OPTIMIZED_HOME_Z_FROM_SAFE_POINT` routes Z homing through the active `G28 Z` / `[homing_override]` path; raw `G28.6245197 Z` is confined to `_OPTIMIZED_HOME_Z_FROM_SAFE_POINT_RAW`, which is called only from `[homing_override]`, so print-start cleanup and mesh helpers do not recursively call `_OPTIMIZED_HOME_Z_FROM_SAFE_POINT`.
- When `enable_box != 1` or `printer["box_extras"]` is not defined, `OPTIMIZED_START_PRINT_FILAMENT_PREP` skips `BOX_PRINT_START`, `OPTIMIZED_EXTRUSION_AND_FLUSH`, and rear extrusion purge, then runs `OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE TARGET={scrape_target}`, bed/chamber waits, `Z_TILT_ADJUST`, and an inline `BED_MESH_CALIBRATE PROFILE=kamp` sequence.
- `OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE` heats the active hotend to `TARGET` defaulting to `start_extruder_probing_temp` or `140`, waits until the nozzle is no hotter than `TARGET + 10`, calls `CLEAR_OOZE` and `CLEAR_FLUSH` only when `printer["box_extras"]` is defined, re-homes Z, moves back to the trash/wipe position, then runs the rear-bed scrape sequence without any `G1 E...` extrusion move.
- `OPTIMIZED_EXTRUSION_AND_FLUSH` changes the stock flush sequence:
  - starts with `G1 E10 F300` instead of stock `G1 E50 F300`
  - runs two `G1 E60 F300` flush loops instead of stock two loops bracketed by `M106 S255` / `M106 S60`
  - keeps a fixed `G4 P5000` cleanup wait instead of stock `G4 P6000`
  - uses `OPTIMIZED_M1004`
- `OPTIMIZED_END_PRINT_FILAMENT_PREP` can retain the active box filament between prints instead of always unloading.
- `OPTIMIZED_END_PRINT_FILAMENT_PREP` runs its end retract under `M83` inside `SAVE_GCODE_STATE` / `RESTORE_GCODE_STATE` so the `G1 E-3 F1800` move remains a relative retract regardless of caller extrusion mode.
- `OPTIMIZED_UNLOAD_FILAMENT` clears retained-tool state before unloading and routes unload travel through `OPTIMIZED_MOVE_TO_TRASH`.
- `OPTIMIZED_UNLOAD_FILAMENT` wraps the unload sequence in `SAVE_GCODE_STATE` / `RESTORE_GCODE_STATE`, forces `G90` and `M83` for its internal moves, restores `printer.toolhead.max_accel`, and keeps the post-unload `G1 E25 F300` move relative regardless of caller extrusion mode.

### `installer/klipper/tltg-optimized-macros/heaters.cfg` -> runtime `config/tltg-optimized-macros/heaters.cfg`

- Adds `OPTIMIZED_WAIT_HOTEND`, `OPTIMIZED_WAIT_BED`, and `OPTIMIZED_WAIT_CHAMBER`.
- These wrappers preserve explicit sub-status values during waits and are used by the optimized print-start path.
- `OPTIMIZED_WAIT_CHAMBER` explicitly stops `chamber_circulation_fan` before waiting on chamber heat.

### `installer/klipper/tltg-optimized-macros/cooling.cfg` -> runtime `config/tltg-optimized-macros/cooling.cfg`

- `OPTIMIZED_M1004` changes the unset default for `enable_polar_cooler` from stock `1` to `0`.
- `OPTIMIZED_DISABLE_BOX_HEATER` calls vendor `DISABLE_BOX_HEATER` only when `printer["box_extras"]` is defined.
- `TLTG_SET_BOX_TEMP BOX=<number> TARGET=<temp>` sets `SET_HEATER_TEMPERATURE HEATER=heater_box<number> TARGET=<temp>` after validating the runtime heater object and `target_max_temp_heater_generic` from `box_config box<number-1>`.
- `OPTIMIZED_END_FAN_COOLDOWN` adds a timed post-print `P3` chamber/exhaust fan run with delayed shutdown; the delayed shutdown skips `M106 P3 S0` while a print is active or paused.

### `orcaslicer_gcode/` and `qidistudio_gcode/`

Both slicer packs now call repo-only optimized entrypoints.

Start G-code:
- `OPTIMIZED_PRINT_START_HOME`; cancels any pending `_optimized_end_fan_cooldown_off` timer before homing.
- `OPTIMIZED_START_PRINT_FILAMENT_PREP`
- `OPTIMIZED_START_PRINT_FILAMENT_PREP` receives `FIRSTLAYERTEMP=[nozzle_temperature_initial_layer]` and `PURGETEMP={nozzle_temperature_range_high[initial_tool]}`; the later front prime-line `M109` still uses `[nozzle_temperature_initial_layer]`.
- `T[initial_tool]` runs before the front prime line so slicer-generated startup extrusion and firmware tool state both use the initial object filament.
- The front prime line is a purge sequence at `Y0`: `G1 E6 F300`, `G1 X178 E20 F1200`, and `G1 X173 E0.8`.

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
