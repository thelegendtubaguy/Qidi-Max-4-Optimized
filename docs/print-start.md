# Print start and end

[← Back to the README](../README.md)

Prints sliced with this project's [start G-code](install.md#slicer-start-g-code) use the optimized start. Files sliced with QIDI's stock G-code still print the stock way.

## What's faster

- **Homing:** X and Y home at 65 mm/s instead of 50, back off 20 mm instead of 50, and print preparation doesn't home anything twice. QIDI's closed-loop homing checks stay in place.
- **Leveling and bed mesh:** the moves between probe points run at 600 mm/s instead of 150. Saving the new mesh no longer freezes Klipper for over two seconds.
- **Filament handling:** less fixed waiting around the cutter, chute wipes, and saving settings. The [QIDI Box](qidi-box.md#load-and-unload-speed) loads and unloads faster.
- **Filament stays loaded** between prints, so the next print with the same slot skips the unload and reload. See [below](#end-of-print-filament).
- **Filament changes** to a slot that's already loaded skip heating to the filament-change temperature and waiting to cool back down, saving about 25 seconds per change.

The start also cleans the nozzle at the rear chute and scrapes it on the rear of the bed before leveling, and draws the front prime line just ahead of your print when there's room.

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
