# Optimized_Slicer_Start_Temperature_Flow

Active paths:
- `orcaslicer_gcode/start.gcode`
- `qidistudio_gcode/start.gcode`
- `installer/klipper/tltg-optimized-macros/start_end.cfg`
- `installer/klipper/tltg-optimized-macros/filament.cfg`
- `installer/klipper/tltg-optimized-macros/heaters.cfg`

## Slicer inputs

Both slicer packs pass two nozzle temperatures into `OPTIMIZED_START_PRINT_FILAMENT_PREP`:

- `HOTENDTEMP={nozzle_temperature_range_high[initial_tool]}`
- `PURGETEMP=[nozzle_temperature_initial_layer]`

Shared bed and chamber inputs:
- `BEDTEMP=[bed_temperature_initial_layer_single]`
- OrcaSlicer: `CHAMBER=[chamber_temperature]`
- QIDI Studio: `CHAMBER=[chamber_temperatures]`

`HOTENDTEMP` drives box-side load and rear flush temperature.
`PURGETEMP` drives the later cooldown thresholds and matches the final front-of-bed `M109` target used by the slicer.

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
- calls `OPTIMIZED_G28 STATUS=tool_head_reset LAZY=0`

Nozzle preheat starts before homing. Final first-layer nozzle heat is not done here.

### 3. `OPTIMIZED_START_PRINT_FILAMENT_PREP`

`installer/klipper/tltg-optimized-macros/filament.cfg` splits into a retained-filament reuse path and a fresh-load path.

## Reuse path

`reuse_loaded` requires all of:

- `_tltg_optimized_globals.keep_loaded_between_prints`
- `enable_box == 1`
- `printer["box_extras"]`
- `retained_tool_ready`
- requested tool equals `retained_tool`
- filament-present sensor is true
- `retained_slot == value_t<tool>`
- `last_load_slot == retained_slot`
- `slot_sync == retained_slot`
- current slot filament ID equals `retained_filament_id`
- current slot vendor ID equals `retained_vendor_id`

Reuse-path temperature flow:

- computes `preheat_temp = start_extruder_probing_temp` when configured, else `ceil(start_extruder_preheat_scale * PURGETEMP)`
- sets `M104 S{preheat_temp}`
- reasserts `M140` and `M141` from slicer inputs
- waits with `OPTIMIZED_WAIT_BED` and `OPTIMIZED_WAIT_CHAMBER`
- moves to the chute with `OPTIMIZED_MOVE_TO_TRASH`
- waits for the nozzle with `OPTIMIZED_WAIT_HOTEND S={preheat_temp} STATUS=clear_nozzle`
- runs chute-side `CLEAR_OOZE` and `CLEAR_FLUSH`
- runs `Z_TILT_ADJUST`
- runs `OPTIMIZED_G29_ZSAFE`
- returns without calling `BOX_PRINT_START`
- returns without doing the final front-of-bed first-layer `M109`
- returns without doing the later bed-scrape cleanup sequence used by the fresh-load path

## Fresh-load path

### `HOTENDTEMP` use

Fresh-load entry:

- `BOX_PRINT_START EXTRUDER={tool} HOTENDTEMP={hotendtemp}`
- `OPTIMIZED_EXTRUSION_AND_FLUSH HOTENDTEMP={hotendtemp} CHAMBER={chambertemp}`

`HOTENDTEMP` is the high end of the slicer material range for the initial tool. It is used for both vendor box-start loading and the rear flush.

### Rear flush

`OPTIMIZED_EXTRUSION_AND_FLUSH`:

- moves to the chute with `OPTIMIZED_MOVE_TO_TRASH`
- waits for nozzle temperature with `OPTIMIZED_WAIT_HOTEND S={hotendtemp} STATUS=flush_filament`
- primes with `G1 E10 F300`
- runs two `G1 E60 F300` flush loops with retracts
- runs `OPTIMIZED_M1004`
- holds `G4 P5000`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH`

This is not the stock `EXTRUSION_AND_FLUSH` sequence. Stock `config/klipper-macros-qd/filament.cfg` uses `M109 S{hotendtemp}`, `G1 E50 F300`, different fan staging, and `G4 P6000`.

### Cooldown and cleanup after rear flush

After the rear flush, `OPTIMIZED_START_PRINT_FILAMENT_PREP`:

- sets `M104 S{cooldown_temp}` where `cooldown_temp = start_extruder_probing_temp` when configured, else `140`
- waits until nozzle temperature is at or below `PURGETEMP`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH`
- waits until nozzle temperature is at or below `PURGETEMP - 30` when that threshold is still above `cooldown_temp`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH` again
- waits until nozzle temperature is at or below `scrape_move_temp = cooldown_temp + 10`
- runs `CLEAR_OOZE` and `CLEAR_FLUSH` again
- then leaves the chute and runs the bed-scrape sequence at `Y395` / `X188`

Bed and chamber waits happen after the scrape sequence:

- `OPTIMIZED_WAIT_BED S={bedtemp} STATUS=wait_bed_temp`
- `OPTIMIZED_WAIT_CHAMBER S={chambertemp} STATUS=wait_chamber_temp`

The macro then runs:

- `Z_TILT_ADJUST`
- `OPTIMIZED_G29_ZSAFE`
- `M1002 A1`
- `G1 X380 Y5 F20000`
- `ENABLE_ALL_SENSOR`

The macro returns without restoring first-layer nozzle temperature. Final first-layer nozzle heat remains in slicer start G-code.

## Front prime-line block

After `OPTIMIZED_START_PRINT_FILAMENT_PREP` returns, both slicer packs:

- select `T[initial_tool]`
- reassert `M140` and `M141`
- move to `X147 Y0`
- wait with `M109 S[nozzle_temperature_initial_layer]`
- move to `X155`
- print the front prime line from `X155` to `X230`
- taper the last `5mm` from `X230` to `X235`
- retract `0.2mm`
- lift Z and return to print setup state

The front prime line now owns the final first-layer nozzle heat-up.

## Current meaning of `HOTENDTEMP` and `PURGETEMP`

- `HOTENDTEMP` = high-end nozzle temperature from the slicer material range for the initial tool
- `HOTENDTEMP` is consumed by `BOX_PRINT_START` and `OPTIMIZED_EXTRUSION_AND_FLUSH`
- `PURGETEMP` = first-layer nozzle temperature from the slicer
- `PURGETEMP` controls the first two cooldown waits after the rear flush
- slicer `M109 S[nozzle_temperature_initial_layer]` performs the final first-layer wait at the front prime-line standby point

Related note:
- `docs/box_print_start_notes.md`
