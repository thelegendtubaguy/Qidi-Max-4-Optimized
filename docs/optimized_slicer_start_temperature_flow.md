# Optimized_Slicer_Start_Temperature_Flow

Active paths:
- `orcaslicer_gcode/start.gcode`
- `qidistudio_gcode/start.gcode`
- `installer/klipper/tltg-optimized-macros/start_end.cfg`
- `installer/klipper/tltg-optimized-macros/filament.cfg`
- `installer/klipper/tltg-optimized-macros/heaters.cfg`

## Slicer inputs

Both slicer packs pass first-layer and rear-purge nozzle temperatures into `OPTIMIZED_START_PRINT_FILAMENT_PREP`:

- `FIRSTLAYERTEMP=[nozzle_temperature_initial_layer]`
- `PURGETEMP={nozzle_temperature_range_high[initial_tool]}`

Shared bed and chamber inputs:
- `BEDTEMP=[bed_temperature_initial_layer_single]`
- OrcaSlicer: `CHAMBER=[chamber_temperature]`
- QIDI Studio: `CHAMBER=[chamber_temperatures]`

`PURGETEMP` drives vendor box load temperature, rear trash purge temperature, and later cooldown thresholds.
`FIRSTLAYERTEMP` records the slicer first-layer nozzle temperature for the start path; `M109 S[nozzle_temperature_initial_layer]` after `OPTIMIZED_START_PRINT_FILAMENT_PREP` performs the actual wait for the front prime line and first layer.

## Start sequence

### 1. Slicer preheat block

`orcaslicer_gcode/start.gcode` and `qidistudio_gcode/start.gcode` begin with:

- `M140` to first-layer bed temperature
- `M141` to chamber temperature
- `G29.0`
- `OPTIMIZED_PRINT_START_HOME`

### 2. `OPTIMIZED_PRINT_START_HOME`

`installer/klipper/tltg-optimized-macros/start_end.cfg`:

- sets `M104` to `km.start_extruder_probing_temp` when configured
- otherwise sets `M104 S140`
- sets print sub-status `tool_head_reset`
- calls `G28`; optimized `[homing_override]` handles the homing flow

Nozzle preheat starts before homing. Final first-layer nozzle heat is not done here.

### 3. `OPTIMIZED_START_PRINT_FILAMENT_PREP`

`installer/klipper/tltg-optimized-macros/filament.cfg` first runs `G31` to set `_km_globals.bedmesh_before_print=1` for stock `g29` compatibility, then splits into retained-filament reuse, box fresh-load, and no-box external-spool paths. Each optimized print-start branch runs an inline `BED_MESH_CLEAR` -> `_OPTIMIZED_G29_HOME_Z_OR_FULL` -> `BED_MESH_CALIBRATE PROFILE=kamp` -> `SAVE_CONFIG_QD` sequence after `Z_TILT_ADJUST` and does not branch on `_km_globals.bedmesh_before_print`.

## Reuse path

`reuse_loaded` requires all of:

- `_tltg_optimized_globals.keep_loaded_between_prints`
- `enable_box == 1`
- `printer["box_extras"] is defined`
- `retained_tool_ready`
- requested tool equals `retained_tool`
- filament-present sensor is true
- `retained_slot == value_t<tool>`
- `last_load_slot == retained_slot`
- `slot_sync == retained_slot`
- current slot filament ID equals `retained_filament_id`
- current slot vendor ID equals `retained_vendor_id`

Reuse-path temperature flow:

- computes `reuse_nozzle_target = start_extruder_probing_temp` when configured, else `ceil(start_extruder_preheat_scale * PURGETEMP)`
- sets `M104 S{reuse_nozzle_target}`
- reasserts `M140` and `M141` from slicer inputs
- waits with `OPTIMIZED_WAIT_BED` and `OPTIMIZED_WAIT_CHAMBER`
- moves to the chute with `OPTIMIZED_MOVE_TO_TRASH`
- waits for the nozzle with `OPTIMIZED_WAIT_HOTEND S={reuse_nozzle_target} STATUS=clear_nozzle`
- runs chute-side `CLEAR_OOZE` and `CLEAR_FLUSH`
- runs `Z_TILT_ADJUST`
- runs `M400`
- runs an inline `BED_MESH_CALIBRATE PROFILE=kamp` sequence
- returns without calling `BOX_PRINT_START`
- returns without doing the final front-of-bed first-layer `M109`
- returns without doing the later bed-scrape cleanup sequence used by the fresh-load path

## Box fresh-load path

### `FIRSTLAYERTEMP` and `PURGETEMP` use

Box fresh-load entry:

- `BOX_PRINT_START EXTRUDER={tool} HOTENDTEMP={purge_temp}`
- `OPTIMIZED_EXTRUSION_AND_FLUSH PURGETEMP={purge_temp} CHAMBER={chamber_target}`

`PURGETEMP` is the high end of the slicer material range for the initial tool. It is passed to vendor `BOX_PRINT_START` as that command's required `HOTENDTEMP` parameter and to the rear purge/flush path as `PURGETEMP`. `FIRSTLAYERTEMP` is the slicer first-layer nozzle temperature; the optimized prep macro does not use it for rear purge.

### Rear flush

`OPTIMIZED_EXTRUSION_AND_FLUSH`:

- moves to the chute with `OPTIMIZED_MOVE_TO_TRASH`
- waits for nozzle temperature with `OPTIMIZED_WAIT_HOTEND S={purge_temp} STATUS=flush_filament`
- primes with `G1 E10 F300`
- runs two `G1 E60 F300` flush loops with retracts
- runs `OPTIMIZED_M1004`
- holds `G4 P5000`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH`

This is not the stock `EXTRUSION_AND_FLUSH` sequence. Stock `config/klipper-macros-qd/filament.cfg` uses `M109 S{hotendtemp}`, `G1 E50 F300`, different fan staging, and `G4 P6000`.

### Cooldown and cleanup after rear flush

After the rear flush, the box fresh-load path:

- sets `M104 S{scrape_target}` where `scrape_target = start_extruder_probing_temp` when configured, else `140`
- waits until nozzle temperature is at or below `PURGETEMP`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH`
- waits until nozzle temperature is at or below `PURGETEMP - 30` when that threshold is still above `scrape_target`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH` again
- waits until nozzle temperature is at or below `scrape_maximum = scrape_target + 10`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH` again
- re-homes Z with `_OPTIMIZED_HOME_Z_FROM_SAFE_POINT`
- moves back to the trash/wipe position with `OPTIMIZED_MOVE_TO_TRASH`
- runs the bed-scrape sequence at `Y395` / `X188`

Bed and chamber waits happen after the scrape sequence:

- `OPTIMIZED_WAIT_BED S={bed_target} STATUS=wait_bed_temp`
- `OPTIMIZED_WAIT_CHAMBER S={chamber_target} STATUS=wait_chamber_temp`

The macro then runs:

- `Z_TILT_ADJUST`
- `M400`
- an inline `BED_MESH_CALIBRATE PROFILE=kamp` sequence
- `M1002 A1`
- `G1 X380 Y5 F20000`
- `ENABLE_ALL_SENSOR`

The macro returns without restoring first-layer nozzle temperature. Final first-layer nozzle heat remains in slicer start G-code.

## No-box external-spool path

When `enable_box != 1` or `printer["box_extras"]` is not defined, `OPTIMIZED_START_PRINT_FILAMENT_PREP` does not call `BOX_PRINT_START`, `OPTIMIZED_EXTRUSION_AND_FLUSH`, or any rear extrusion purge.

No-box path sequence:

- clears retained box-tool state variables
- reasserts `M140 S{BEDTEMP}` and `M141 S{CHAMBER}` when those inputs are nonzero
- runs `OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE TARGET={scrape_target}`
- sets chamber exhaust fan `P3` on when `CHAMBER=0`, otherwise off
- waits with `OPTIMIZED_WAIT_BED S={BEDTEMP} STATUS=wait_bed_temp`
- waits with `OPTIMIZED_WAIT_CHAMBER S={CHAMBER} STATUS=wait_chamber_temp` when chamber input is nonzero
- runs `Z_TILT_ADJUST`
- runs `M400`
- runs an inline `BED_MESH_CALIBRATE PROFILE=kamp` sequence
- runs `M1002 A1`
- moves to `X380 Y5`
- runs `ENABLE_ALL_SENSOR`

`OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE` heats the active hotend to `TARGET`, waits until the nozzle is no hotter than `TARGET + 10`, calls `CLEAR_OOZE` and `CLEAR_FLUSH` only when `printer["box_extras"]` is defined, re-homes Z with `_OPTIMIZED_HOME_Z_FROM_SAFE_POINT`, moves back to the trash/wipe position with `OPTIMIZED_MOVE_TO_TRASH`, then runs the rear-bed scrape sequence at `Y395` / `X188`. It does not contain any `G1 E...` extrusion move.

The no-box path relies on the slicer front prime-line block for final first-layer nozzle heat and front-of-bed priming.

## Bed mesh behavior

The retained-filament, box fresh-load, and no-box external-spool paths run `M400` after `Z_TILT_ADJUST`, then inline the mesh sequence: `SET_STEPPER_ENABLE STEPPER=extruder enable=0`, `BED_MESH_CLEAR`, `_OPTIMIZED_G29_HOME_Z_OR_FULL`, `BED_MESH_CALIBRATE PROFILE=kamp`, `SAVE_VARIABLE VARIABLE=profile_name VALUE='"kamp"'`, `G4 P500`, and `SAVE_CONFIG_QD`. The wrapped `BED_MESH_CALIBRATE` macro uses `exclude_object` polygons for adaptive bounds when objects are available and falls back to the full configured bed mesh range when no print object is detected.

## Front prime-line block

After `OPTIMIZED_START_PRINT_FILAMENT_PREP` returns, both slicer packs:

- call `OPTIMIZED_SELECT_INITIAL_TOOL T=[initial_tool]`, which calls `T<tool>` only when `enable_box == 1`, `printer["box_extras"]` is defined, and the matching `T<tool>` macro is defined
- reassert `M140` and `M141`
- move to `X210 Y0`
- wait with `M109 S[nozzle_temperature_initial_layer]`
- use relative extrusion with `M83` and reset with `G92 E0`
- move to `X218 Y0`
- extrude `G1 E6 F300` to load the nozzle and absorb heat-up ooze
- run the purge line from `X218` to `X178` with `G1 X178 E20 F1200`
- taper/finish from `X178` to `X173` with `G1 X173 E0.8`
- retract `0.2mm`
- lift Z and return to print setup state

The front prime line owns the final first-layer nozzle heat-up and purges accumulated high-temperature ooze from the `M109` wait.

## Current meaning of `FIRSTLAYERTEMP` and `PURGETEMP`

- `FIRSTLAYERTEMP` = first-layer nozzle temperature from the slicer
- `PURGETEMP` = high-end nozzle temperature from the slicer material range for the initial tool
- `PURGETEMP` is forwarded to vendor `BOX_PRINT_START` as `HOTENDTEMP` only in the box fresh-load path because `HOTENDTEMP` is the vendor command's parameter name
- `PURGETEMP` is consumed by `OPTIMIZED_EXTRUSION_AND_FLUSH` and controls the first two cooldown waits after the rear purge/flush in the box fresh-load path
- `PURGETEMP` is not used for rear extrusion in the no-box path; the no-box path heats only to `scrape_target` for wipe/scrape before the slicer front prime-line block performs final first-layer heat and priming
- slicer `M109 S[nozzle_temperature_initial_layer]` performs the final first-layer wait at the front prime-line standby point

Related note:
- `docs/box_print_start_notes.md`
