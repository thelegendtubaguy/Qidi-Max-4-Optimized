# Settings and commands

[← Back to the README](../README.md)

Every setting this project adds, in one place. Run these from Fluidd's console.

## Saved settings

Set with `SAVE_VARIABLE VARIABLE=<name> VALUE=<value>`. They survive restarts and updates, and work with files you've already sliced unless noted.

| Setting | Default | What it does |
|---|---|---|
| [`tltg_keep_loaded_between_prints`](print-start.md#end-of-print-filament) | `1` | `1` keeps Box filament loaded after a print; `0` cuts and unloads it. |
| [`tltg_start_bed_mesh_profile`](print-start.md#reuse-a-saved-bed-mesh) | `""` | A profile name loads that saved bed mesh at print start; empty measures a fresh mesh. Quote it: `VALUE='"default"'`. |
| [`tltg_staggered_start_heating`](print-start.md#staggered-heating) | `0` | `1` heats the bed, chamber, then nozzle in turn. Needs current start G-code. |
| [`tltg_staggered_start_heating_dwell_seconds`](print-start.md#staggered-heating) | `10` | Pause between staggered heating stages, in seconds. |
| [`tltg_box_link_monitor`](troubleshooting.md#box-link-monitor) | `0` | `1` records Box disconnect details to `tltg_box_link.log`. |

## Commands

| Command | What it does |
|---|---|
| [`TLTG_BOX_MOTION`](qidi-box.md#load-and-unload-speed) | Shows or sets QIDI Box load and unload speeds, for all slots or one. |
| [`TLTG_BOX_SLOT_JOG SLOT= DISTANCE=`](qidi-box.md#moving-a-slot-by-hand) | Moves a QIDI Box slot's filament in or out by a set distance. |
| [`TLTG_FILAMENT_SENSOR ENABLE=0\|1`](tools.md#external-spool-runout-sensor) | Stops or restores external spool runout pauses until Klipper restarts. |
| [`TLTG_SPOOLMAN_SLOT SLOT= SPOOL=`](spoolman.md#giving-each-slot-its-spool) | Sets the Spoolman spool for a QIDI Box slot or the external spool, which becomes the active spool whenever that slot is loaded. No parameters lists them. |
| [`TLTG_RS_BOX_REPORT`](qidi-box.md#rs-485-boxes) | Writes the QIDI RS-485 Box report to `logs/tltg_box485_report.json` and says whether RS-485 hardware was found. |
| [`TLTG_RESET_TOOL_MAPPINGS`](tools.md) | Restores the default Box tool-to-slot mapping. Idle only. |
| [`TLTG_TEST_PROBE CONFIRM=1`](tools.md#nozzle-load-cell-check) | Checks the nozzle load cell without moving. |
| [`TLTG_PROBE_ACCURACY_CENTER`](tools.md) | Probe accuracy at the bed center. |
| [`TLTG_CORNER_BED_SCREW_CHECK`](tools.md) | Levels, then shows bed screw adjustments. |

## In your slicer

| Setting | Where | What it does |
|---|---|---|
| [Chamber **Minimal** temperature](print-start.md#minimum-chamber-temperature) | OrcaSlicer 2.4.2+ filament profile | Starts printing once the chamber reaches this, while it keeps heating toward the target. |

## Installer options

See [Installing, updating, and uninstalling](install.md) for the dry run, OS optimizations, and automatic updates.
