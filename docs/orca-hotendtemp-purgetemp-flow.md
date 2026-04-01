# Temperature Flow From Orca And QIDI Studio Start G-Code

This note traces the actual startup temperature flow used by the in-repo OrcaSlicer and QIDI Studio profiles.

For this discussion, OrcaSlicer and QIDI Studio behave the same way. Their start-gcode files are effectively identical for temperature flow. The only relevant difference here is the chamber placeholder name: OrcaSlicer uses `[chamber_temperature]` and QIDI Studio uses `[chamber_temperatures]`.

The startup flow is split across:

- `orcaslicer_gcode/start_gcode`
- `qidistudio_gcode/start_gcode`
- `config/klipper-macros-qd/filament.cfg` via `START_PRINT_FILAMENT_PREP`

## Practical Summary

The current in-repo OrcaSlicer and QIDI Studio startup temperature flow is:

1. bed starts heating to first-layer bed temp
2. chamber starts heating to chamber temp
3. `START_PRINT_FILAMENT_PREP` begins the box/material prep path
4. vendor box-start logic uses `HOTENDTEMP = nozzle_temperature_range_high[initial_tool]`
5. visible rear flush uses that same `HOTENDTEMP`
6. the macro cools down toward `PURGETEMP - 30`
7. the macro returns the nozzle to `PURGETEMP = nozzle_temperature_initial_layer`
8. slicer gcode reasserts first-layer nozzle temperature
9. slicer gcode waits at first-layer nozzle temperature
10. slicer gcode runs the front prime line

In this profile:

- `HOTENDTEMP` is the high end of the selected filament's nozzle temperature range
- `PURGETEMP` is the first-layer nozzle temperature
- the visible `30C` offset is a cooldown threshold after the flush, not a `+30C` bump

## Actual Slicer Entry Point

The in-repo OrcaSlicer start gcode does this:

```gcode
M140 S[bed_temperature_initial_layer_single]
M141 S[chamber_temperature]
START_PRINT_FILAMENT_PREP EXTRUDER=[initial_no_support_extruder] HOTENDTEMP={nozzle_temperature_range_high[initial_tool]} PURGETEMP=[nozzle_temperature_initial_layer] BEDTEMP=[bed_temperature_initial_layer_single] CHAMBER=[chamber_temperature]
...
M104 S[nozzle_temperature_initial_layer]
...
M109 S[nozzle_temperature_initial_layer]
```

QIDI Studio uses the same flow, with the same `START_PRINT_FILAMENT_PREP` call shape and the same temperature roles.

## What The Slicer Passes

The active start gcode passes two different nozzle temperatures on purpose:

- `HOTENDTEMP={nozzle_temperature_range_high[initial_tool]}`
- `PURGETEMP=[nozzle_temperature_initial_layer]`

That means:

- `HOTENDTEMP` is the high end of the selected filament's nozzle range in the slicer
- `PURGETEMP` is the first-layer nozzle temperature from the slicer

This is not the same as passing one nozzle value through the whole startup.

## Temperature Timeline

## 1. Slicer Init Block

Files:

- `orcaslicer_gcode/start_gcode`
- `qidistudio_gcode/start_gcode`

Temperature actions:

- `M140 S[bed_temperature_initial_layer_single]`
- `M141 S[chamber_temperature]` or `M141 S[chamber_temperatures]`

At this point:

- the bed starts heating to the first-layer bed target
- the chamber starts heating if a chamber target is configured
- the nozzle is not explicitly heated yet by this slicer init block

## 2. Box Prep Entry

Files:

- `orcaslicer_gcode/start_gcode`
- `qidistudio_gcode/start_gcode`

The next major call is:

```gcode
START_PRINT_FILAMENT_PREP EXTRUDER=[initial_no_support_extruder] HOTENDTEMP={nozzle_temperature_range_high[initial_tool]} PURGETEMP=[nozzle_temperature_initial_layer] BEDTEMP=[bed_temperature_initial_layer_single] CHAMBER=[chamber_temperature]
```

QIDI Studio uses the same call with its chamber placeholder.

This is the handoff from slicer start gcode into the Klipper macro layer for startup filament prep.

## 3. `START_PRINT_FILAMENT_PREP` Reuse Path

File: `config/klipper-macros-qd/filament.cfg`

If the machine is reusing already-loaded filament, the macro takes the `reuse_loaded` branch.

This reuse behavior is enabled by default in `config/klipper-macros-qd/globals.cfg`:

```text
variable_keep_loaded_between_prints: True
```

In that path it:

1. computes `preheat_temp`
2. sets the nozzle target with `M104 S{preheat_temp}`
3. reheats bed and chamber if needed
4. runs `Z_TILT_ADJUST` and `G29_ZSAFE`
5. waits for bed and chamber targets
6. moves to the rear purge area
7. waits for `M109 S{purgetemp}`

Key point:

- in the reuse path, the final nozzle wait inside the macro is `PURGETEMP`

With the current slicer start gcode, that means it waits for:

- `PURGETEMP = [nozzle_temperature_initial_layer]`

before returning to slicer gcode.

## 4. `START_PRINT_FILAMENT_PREP` Fresh Load Path

File: `config/klipper-macros-qd/filament.cfg`

If filament is not being reused, the macro takes the fresh-load path.

That path is where most visible temperature changes happen.

### 4.1 Vendor box start uses `HOTENDTEMP`

The macro calls:

```gcode
BOX_PRINT_START EXTRUDER={tool} HOTENDTEMP={hotendtemp}
```

Important:

- this receives `HOTENDTEMP`
- with the current slicer profile, that is `{nozzle_temperature_range_high[initial_tool]}`
- it does not receive `PURGETEMP`

So the vendor box-start path is driven from the slicer's configured high-end nozzle temperature, not the first-layer nozzle temperature.

## 4.2 Visible flush also uses `HOTENDTEMP`

Immediately after `BOX_PRINT_START`, the macro calls:

```gcode
EXTRUSION_AND_FLUSH HOTENDTEMP={hotendtemp} CHAMBER={chambertemp}
```

Inside `EXTRUSION_AND_FLUSH`:

```gcode
M109 S{hotendtemp}
```

So the visible rear flush also heats to `HOTENDTEMP`, which in the current slicer profile is the top of the nozzle temperature range.

## 4.3 Post-flush cooldown uses `PURGETEMP - 30`

After that flush, the macro does:

```gcode
M104 S{km.start_extruder_probing_temp if km.start_extruder_probing_temp > 0 else 140}
M109.1 S{purgetemp - 30}
```

With the current slicer profile:

- `purgetemp` is `[nozzle_temperature_initial_layer]`
- the wait threshold is `first_layer_temp - 30C`

This is the visible `30C` offset in the active startup macro path.

It is a cooldown threshold after the flush, not a `+30C` bump.

## 4.4 Bed and chamber settle back to slicer targets

Later in the same macro, it waits for:

```gcode
M190 S{bedtemp}
M191 S{chambertemp}
```

So the bed and chamber are brought back to the slicer-provided targets before the rest of the prep finishes.

## 4.5 Final wait inside prep returns to `PURGETEMP`

Near the end of the fresh-load branch, the macro does:

```gcode
M109 S{purgetemp}
```

So before `START_PRINT_FILAMENT_PREP` returns to the slicer, the nozzle is brought back up to:

- `PURGETEMP = [nozzle_temperature_initial_layer]`

## 5. Slicer Prime-Line Block After Macro Return

Files:

- `orcaslicer_gcode/start_gcode`
- `qidistudio_gcode/start_gcode`

After `START_PRINT_FILAMENT_PREP` returns, the slicer continues with its own front-edge prime-line block.

Relevant temperature lines are:

```gcode
M140 S[bed_temperature_initial_layer_single]
M104 S[nozzle_temperature_initial_layer]
M141 S[chamber_temperature]
...
M109 S[nozzle_temperature_initial_layer]
```

QIDI Studio uses the same sequence with its chamber placeholder.

So the slicer itself reasserts:

- bed target = first-layer bed temp
- nozzle target = first-layer nozzle temp
- chamber target = chamber temp

Then it waits for the nozzle to be fully at first-layer temperature before the front prime line.

## 6. Front Prime Line Uses First-Layer Temperature

Still in the slicer start gcode, the front-edge prime line runs after:

```gcode
M109 S[nozzle_temperature_initial_layer]
```

So the front prime line is run at the slicer's first-layer nozzle temperature.

That is separate from the earlier box-prep flush path, which used `HOTENDTEMP={nozzle_temperature_range_high[initial_tool]}`.

## What `HOTENDTEMP` And `PURGETEMP` Mean In This Profile

In this repo's OrcaSlicer and QIDI Studio start gcode:

- `HOTENDTEMP` is the value passed into `START_PRINT_FILAMENT_PREP` for the box-prep flow
- that value is currently the slicer's nozzle temperature range high
- `PURGETEMP` is currently the first-layer nozzle temperature
- `PURGETEMP` controls the later wait inside `START_PRINT_FILAMENT_PREP`
- `PURGETEMP` also sets the post-flush cooldown threshold through `PURGETEMP - 30`
- the slicer then uses that same first-layer nozzle temperature for the front prime line

For deeper vendor reverse-engineering, see `docs/box_print_start_notes.md`.
