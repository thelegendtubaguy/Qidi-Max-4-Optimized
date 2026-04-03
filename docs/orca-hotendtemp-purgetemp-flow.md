# Temperature Flow From Orca And QIDIStudio Start G-Code

This note traces the actual startup temperature flow used by the Orca and QIDIStudio gcode in this repository.

For this discussion, Orca and QIDIStudio behave the same way and we'll only point to one of them for examples. Their start-gcode files are effectively identical for temperature flow. The only relevant difference here is the chamber placeholder name: Orca uses `[chamber_temperature]` and QIDIStudio uses `[chamber_temperatures]`.

The startup flow is split across:

- [`orcaslicer_gcode/start_gcode`](../orcaslicer_gcode/start_gcode#L12-L50)
- [`config/klipper-macros-qd/filament.cfg`](../config/klipper-macros-qd/filament.cfg#L78-L189) via `START_PRINT_FILAMENT_PREP`

## Summary

The slicer startup temperature flow is:

1. bed starts heating to first-layer bed temp
2. chamber starts heating to chamber temp
3. `START_PRINT_FILAMENT_PREP` begins the box/material prep path
4. QIDI box-start logic uses `HOTENDTEMP = nozzle_temperature_range_high[initial_tool]`
5. visible rear flush uses that same `HOTENDTEMP`
6. the macro cools down toward `PURGETEMP - 30`
7. the macro returns the nozzle to `PURGETEMP = nozzle_temperature_initial_layer`
8. slicer gcode reasserts first-layer nozzle temperature
9. slicer gcode waits at first-layer nozzle temperature
10. slicer gcode runs the front prime line

## Actual Slicer Entry Point

The slicer start gcode in [`orcaslicer_gcode/start_gcode`](../orcaslicer_gcode/start_gcode#L12-L50) does this:

```gcode
M140 S[bed_temperature_initial_layer_single]
M141 S[chamber_temperature]
START_PRINT_FILAMENT_PREP EXTRUDER=[initial_no_support_extruder] HOTENDTEMP={nozzle_temperature_range_high[initial_tool]} PURGETEMP=[nozzle_temperature_initial_layer] BEDTEMP=[bed_temperature_initial_layer_single] CHAMBER=[chamber_temperature]
...
M104 S[nozzle_temperature_initial_layer]
...
M109 S[nozzle_temperature_initial_layer]
```

## What The Slicer Passes

The active start gcode passes two different nozzle temperatures on purpose:

- `HOTENDTEMP={nozzle_temperature_range_high[initial_tool]}`
- `PURGETEMP=[nozzle_temperature_initial_layer]`

That means:

- `HOTENDTEMP` is the high end of the selected filament's nozzle range in the slicer
- `PURGETEMP` is the first-layer nozzle temperature from the slicer

## Temperature Timeline

### 1. Slicer Init Block

[`orcaslicer_gcode/start_gcode`](../orcaslicer_gcode/start_gcode#L12-L15)

Temperature actions:

- `M140 S[bed_temperature_initial_layer_single]`
- `M141 S[chamber_temperature]` or `M141 S[chamber_temperatures]`

At this point:

- the bed starts heating to the first-layer bed target
- the chamber starts heating if a chamber target is configured
- the nozzle is not explicitly heated yet by this slicer init block

### 2. Box Prep Entry

[`orcaslicer_gcode/start_gcode`](../orcaslicer_gcode/start_gcode#L17-L18)

The next notable call is:

```gcode
START_PRINT_FILAMENT_PREP EXTRUDER=[initial_no_support_extruder] HOTENDTEMP={nozzle_temperature_range_high[initial_tool]} PURGETEMP=[nozzle_temperature_initial_layer] BEDTEMP=[bed_temperature_initial_layer_single] CHAMBER=[chamber_temperature]
```

This is the handoff from slicer start gcode into the Klipper macro layer for startup filament prep.

### 3. `START_PRINT_FILAMENT_PREP` Reuse Path

[`config/klipper-macros-qd/filament.cfg`](../config/klipper-macros-qd/filament.cfg#L78-L120)

If the machine is reusing already-loaded filament, the macro takes the `reuse_loaded` branch.

This reuse behavior is enabled by default in [`config/klipper-macros-qd/globals.cfg`](../config/klipper-macros-qd/globals.cfg#L66-L68).

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

### 4. `START_PRINT_FILAMENT_PREP` Fresh Load Path

[`config/klipper-macros-qd/filament.cfg`](../config/klipper-macros-qd/filament.cfg#L121-L189)

If filament is not being reused, the macro takes the fresh-load path.

This path is a little more complicated.

#### 4.1 QIDI box start uses `HOTENDTEMP`

The macro calls:

```gcode
BOX_PRINT_START EXTRUDER={tool} HOTENDTEMP={hotendtemp}
```

With the current slicer profile, that is `{nozzle_temperature_range_high[initial_tool]}`.

So the QIDI box-start path is driven from the slicer's configured high-end nozzle temperature.

#### 4.2 Visible flush also uses `HOTENDTEMP`

Immediately after `BOX_PRINT_START`, the macro calls:

```gcode
EXTRUSION_AND_FLUSH HOTENDTEMP={hotendtemp} CHAMBER={chambertemp}
```

Inside `EXTRUSION_AND_FLUSH`:

```gcode
M109 S{hotendtemp}
```

The rear flush also heats to `HOTENDTEMP`, which in the current slicer profile is the top of the nozzle temperature range.

#### 4.3 Post-flush cooldown uses `PURGETEMP - 30`

After that flush, the macro does:

```gcode
M104 S{km.start_extruder_probing_temp if km.start_extruder_probing_temp > 0 else 140}
M109.1 S{purgetemp - 30}
```

With the current slicer profile:

- `purgetemp` is `[nozzle_temperature_initial_layer]`
- The printer waits for `first_layer_temp - 30C`

#### 4.4 Bed and chamber settle back to slicer targets

Later in the same macro, it waits for:

```gcode
M190 S{bedtemp}
M191 S{chambertemp}
```

So the bed and chamber are brought back to the slicer-provided targets before the rest of the prep finishes.

#### 4.5 Final wait inside prep returns to `PURGETEMP`

Near the end of the fresh-load branch, the macro does:

```gcode
M109 S{purgetemp}
```

So before `START_PRINT_FILAMENT_PREP` returns to the slicer, the nozzle is brought back up to:

- `PURGETEMP = [nozzle_temperature_initial_layer]`

### 5. Slicer Prime-Line Block After Macro Return

[`orcaslicer_gcode/start_gcode`](../orcaslicer_gcode/start_gcode#L20-L50)

After `START_PRINT_FILAMENT_PREP` returns, the slicer continues with the front prime line.

Relevant temperature lines are:

```gcode
M140 S[bed_temperature_initial_layer_single]
M104 S[nozzle_temperature_initial_layer]
M141 S[chamber_temperature]
...
M109 S[nozzle_temperature_initial_layer]
```

So the slicer itself reasserts:

- bed target = first-layer bed temp
- nozzle target = first-layer nozzle temp
- chamber target = chamber temp

Then it waits for the nozzle to be fully at first-layer temperature before printing the front prime line and then continuing with the rest of the print.

## What `HOTENDTEMP` And `PURGETEMP` Mean In This Profile

In the Orca and QIDIStudio start gcode:

- `HOTENDTEMP` is the value passed into `START_PRINT_FILAMENT_PREP` for the box-prep flow
- `HOTENDTEMP` is the highest nozzle temp of all filaments in use
- `PURGETEMP` is the first-layer nozzle temperature of the first used filament
- `PURGETEMP` controls the later wait inside `START_PRINT_FILAMENT_PREP`
- `PURGETEMP` also sets the post-flush cooldown threshold through `PURGETEMP - 30`
- the slicer then uses that same first-layer nozzle temperature for the front prime line

For deeper QIDI reverse-engineering, see [QIDI Box Implementation Notes](box_print_start_notes.md#L1-L40).
