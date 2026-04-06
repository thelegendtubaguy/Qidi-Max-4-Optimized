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
6. the macro cools down over the waste chute with staged wipe passes
7. the macro returns without doing the final first-layer nozzle heat-up
8. slicer gcode moves to the front load-line start position
9. slicer gcode heats to and waits at first-layer nozzle temperature there
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
4. waits for bed and chamber targets
5. runs `Z_TILT_ADJUST` and `G29_ZSAFE`
6. moves to the rear purge area
7. returns without performing the final first-layer heat-up

Key point:

- in the reuse path, the final first-layer nozzle heat-up is deferred until the slicer is already parked at the front load-line start position

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

#### 4.3 Post-flush cooldown now stages chute wipes as temperature drops

After that flush, the macro keeps the nozzle over the waste chute, aims for the probing temperature target, and performs repeated wipe passes as it cools:

```gcode
G1 E-0.2 F1800
M104 S{km.start_extruder_probing_temp if km.start_extruder_probing_temp > 0 else 140}
TEMPERATURE_WAIT SENSOR=extruder MAXIMUM={purgetemp}
CLEAR_OOZE
CLEAR_FLUSH
TEMPERATURE_WAIT SENSOR=extruder MAXIMUM={purgetemp - 30}
CLEAR_OOZE
CLEAR_FLUSH
TEMPERATURE_WAIT SENSOR=extruder MAXIMUM={km.start_extruder_probing_temp if km.start_extruder_probing_temp > 0 else 140}
CLEAR_OOZE
CLEAR_FLUSH
```

With the current slicer profile for typical materials:

- `purgetemp` is `[nozzle_temperature_initial_layer]`
- the macro first does a small `0.2mm` retract to relieve nozzle pressure over the chute
- the first chute wipe happens after cooling back to first-layer nozzle temperature
- the second chute wipe happens after cooling to `first_layer_temp - 30C`
- the third chute wipe happens after cooling to 140C

Only after those chute-side wipe passes does it move to the bed scrape area.

Those repeated cleanup passes use the same vendor-provided `CLEAR_OOZE` and `CLEAR_FLUSH` primitives that QIDI already uses after the main rear purge, instead of a repo-local custom wipe path.

#### 4.4 Bed and chamber settle back to slicer targets

Later in the same macro, it waits for:

```gcode
M190 S{bedtemp}
M191 S{chambertemp}
```

So the bed and chamber are brought back to the slicer-provided targets before the rest of the prep finishes.

#### 4.5 Prep leaves final nozzle heat-up to the slicer

Near the end of the fresh-load branch, the macro no longer restores `PURGETEMP` before returning.

The slicer now performs the entire final first-layer heat-up at the front load-line start position, which prevents the nozzle from sitting at the rear park position while it climbs from the cleanup temperature to print temperature.

### 5. Slicer Prime-Line Block After Macro Return

[`orcaslicer_gcode/start_gcode`](../orcaslicer_gcode/start_gcode#L20-L50)

After `START_PRINT_FILAMENT_PREP` returns, the slicer continues with a centered light front load line at `Y0`.

Relevant temperature lines are:

```gcode
M140 S[bed_temperature_initial_layer_single]
M141 S[chamber_temperature]
...
M109 S[nozzle_temperature_initial_layer]
```

So the slicer itself reasserts:

- bed target = first-layer bed temp
- chamber target = chamber temp

Then it moves to the front load-line start position, waits there for the nozzle to reach first-layer temperature, drops to line height, and prints the lighter front load line. That keeps the long heat-up off the rear park position and avoids oozing during a late move to the front.

The slicer no longer performs the old single `probe samples=1` tap before this line; the active startup path already handled `Z_TILT_ADJUST` and `G29_ZSAFE` inside `START_PRINT_FILAMENT_PREP`.

## What `HOTENDTEMP` And `PURGETEMP` Mean In This Profile

In the Orca and QIDIStudio start gcode:

- `HOTENDTEMP` is the value passed into `START_PRINT_FILAMENT_PREP` for the box-prep flow
- `HOTENDTEMP` is the highest nozzle temp of all filaments in use
- `PURGETEMP` is the first-layer nozzle temperature of the first used filament
- `PURGETEMP` controls the later wait inside `START_PRINT_FILAMENT_PREP`
- `PURGETEMP` sets the first two staged post-flush cleanup thresholds: `PURGETEMP` and `PURGETEMP - 30`
- the slicer then uses that same first-layer nozzle temperature for the front prime line

For deeper QIDI reverse-engineering, see [QIDI Box Implementation Notes](box_print_start_notes.md#L1-L40).
