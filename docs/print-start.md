# Print start and end

[← Back to the README](../README.md)

Prints sliced with this project's [start G-code](install.md#slicer-start-g-code) use the optimized start. Files sliced with QIDI's stock G-code still print the stock way.

## What's faster

- **Homing:** print preparation doesn't home anything twice. On the Max 4, X and Y home at 65 mm/s instead of 50 and back off 20 mm instead of 50, and QIDI's closed-loop homing checks stay in place.
- **Leveling and bed mesh:** the moves between probe points run at 565 mm/s instead of 150, at your printer's full acceleration (30000 mm/s² on the Max 4) instead of QIDI's 10000. Saving the new mesh no longer freezes Klipper for over two seconds.
- **Filament handling:** less fixed waiting around the cutter, chute wipes, and saving settings. The [QIDI Box](qidi-box.md#load-and-unload-speed) loads and unloads faster.
- **Filament stays loaded** between prints, so the next print with the same slot skips the unload and reload. See [below](#end-of-print-filament).
- **Filament changes** to a slot that's already loaded skip heating to the filament-change temperature and waiting to cool back down, saving about 25 seconds per change.

The start also cleans the nozzle at the rear chute and scrapes it on the rear of the bed before leveling, and draws the front prime line just ahead of your print when there's room.

### No input shaper calibration

If an axis has no input shaper, for example because no calibration is saved, Klipper gives it QIDI's stock calibration for your printer; on the Max 4, that's EI at 54.4 Hz on X and MZV at 36.2 Hz on Y. It's applied at startup and after every X/Y home, before the toolhead moves to home Z. Nothing is written to `printer.cfg`, so your own calibration replaces QIDI's as soon as it runs.

Until a calibration is saved for both axes, homing keeps acceleration at QIDI's 10000 mm/s² instead of raising it to 30000, so leveling and bed mesh moves run at QIDI's acceleration. Fluidd shows a red banner on every page, and the console warns at startup and after every home: `WARNING: No input shaper calibration is saved. TLTG Optimizations is utilizing Qidi's default shaper and limiting acceleration during homing and meshing to 10000 mm/s².` A calibration you've just run counts as saved before `SAVE_CONFIG`, so the next home goes back to full acceleration without a restart. While an axis has no input shaper at all, before the next home applies QIDI's, or for good if `printer.cfg` has no `[input_shaper]` section, the warning says `Input shaping is off.` instead, with the same acceleration limit.

Without any input shaping, moves at full speed and acceleration shake the toolhead hard enough that some printers may skip belts or lose position. QIDI's calibration is close on most printers but not tuned to yours, so run input shaper calibration when possible. Run it on its own: the touchscreen's calibration page runs bed leveling first when both are checked. Accelerations your slicer sets during a print are not limited, and no slicer G-code changes are needed.

## Reuse a saved bed mesh

By default, each print start measures a fresh adaptive mesh over the area being printed. To load a saved Klipper bed-mesh profile instead, save its exact name:

```gcode
SAVE_VARIABLE VARIABLE=tltg_start_bed_mesh_profile VALUE='"default"'
```

To go back to a fresh mesh each print:

```gcode
SAVE_VARIABLE VARIABLE=tltg_start_bed_mesh_profile VALUE='""'
```

This works with files you've already sliced. The console says which one the start is using. The profile must exist, or Klipper stops the print start.

## Minimum chamber temperature

Needs OrcaSlicer 2.4.2 or later with this project's start G-code.

Set the filament profile's chamber **Target** and **Minimal** temperatures. With Target `60°C` and Minimal `50°C`, leveling and printing begin once the chamber reaches `50°C`, while heating continues toward `60°C`. The first tool's filament sets the minimum, and a minimum above the target is capped at the target.

A Minimal of `0`, QIDI Studio, and older start G-code all keep the usual wait for 3 °C below the target.

## Exhaust fan while heating the chamber

Turning on the exhaust fan (`M106 P3`) no longer turns off the chamber heater. QIDI's turned it off, so a filament profile with its exhaust fan (air filtration) on during the print stopped heating the chamber as soon as the exhaust fan came on, without saying so. The heater now keeps its target, and when the exhaust fan turns on while the chamber heats, the console warns:

`WARNING: Exhaust fan turned on at 40% while the chamber heater is set to 60°C. The heater stays on. If your filament profile turned it on, turn off the profile's exhaust fan (air filtration) to heat the chamber fully.`

The exhaust pulls heat out of the chamber. If the chamber stays more than 5 °C below its target for long, or stops gaining while it heats, Klipper stops the print with `Heater chamber not heating at expected rate`. Before that can happen, the exhaust fan is turned off for the rest of the print, and the console warns:

`WARNING: Exhaust fan turned off for the rest of the print. The chamber is at 56°C against its 60°C target and isn't keeping up; if it stays more than 5°C below for long, Klipper stops the print with 'Heater chamber not heating at expected rate'.`

The fan is turned off when a chamber that had reached its target falls back to 4 °C below it, or when one that's still heating has gone 4 minutes without gaining 1 °C, half the 8 minutes Klipper allows. Later requests to turn the exhaust on during that print are ignored while the chamber heater is on, with a console note; the end-of-print exhaust still runs, since the chamber heater is off by then. The next print starts fresh. For filaments that need a heated chamber, turn off the exhaust fan in the filament profile.

## Staggered heating

Off by default. Heats the bed, then the chamber, then the nozzle, with a pause between stages:

```gcode
SAVE_VARIABLE VARIABLE=tltg_staggered_start_heating VALUE=1
SAVE_VARIABLE VARIABLE=tltg_staggered_start_heating_dwell_seconds VALUE=10
```

The pause is in seconds; `0` keeps the order without pausing. With a [minimum chamber temperature](#minimum-chamber-temperature), the nozzle starts heating once the chamber reaches the minimum. Turn it off with:

```gcode
SAVE_VARIABLE VARIABLE=tltg_staggered_start_heating VALUE=0
```

Needs files sliced with the current start G-code from this repo or the OrcaCloud bundle.

## End-of-print filament

After a completed print, the Box filament stays loaded. The installer turns this on unless you've already chosen, and updates keep your choice.

To cut and unload after each print the way QIDI does:

```gcode
SAVE_VARIABLE VARIABLE=tltg_keep_loaded_between_prints VALUE=0
```

To keep filament loaded again:

```gcode
SAVE_VARIABLE VARIABLE=tltg_keep_loaded_between_prints VALUE=1
```

This works with files you've already sliced and survives Klipper restarts.

## Z offset

Your Z offset, including adjustments made on the touchscreen during a print, is kept through the start's homing, leveling, and mesh. Cancelling a print during its start no longer wipes the saved offset to `0`; the console shows `Z offset not saved` instead.
