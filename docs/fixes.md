# Fixes for QIDI bugs

[← Back to the README](../README.md)

These are installed whether or not you choose the optional OS optimizations, and uninstall puts QIDI's original behavior back.

## The real error instead of `MCU shutdown`

When Klipper stopped on an error, such as a heater or fan fault or a lost Box connection, QIDI's print status module could crash Klipper during the shutdown, so the screen, Fluidd, and slicers showed only `MCU shutdown`. Now the original reason stays on screen. `FIRMWARE_RESTART` recovers as usual.

## QIDI Box disconnects

Boxes dropped with `Lost communication with MCU 'mcu_boxN'`, most often at print start or end with the Box heater on. Klipper was too busy to tell the Box heater it was still in control, and QIDI's Box firmware restarts the Box instead of reporting that. This project:

- Has each Box heater check in every second instead of every 3.75, so it rides out pauses of about three seconds.
- Saves the bed mesh at print start in the background, instead of freezing Klipper for over two seconds.
- Makes `SAVE_VARIABLE` skip saves that change nothing and stop re-reading the file it just wrote, so print end takes under 10 ms to save settings instead of about 0.4 s. Turning the printer off during a save can no longer leave the file empty or half written.
- Stops reading Box heater sensors after a shutdown, which crashed Klipper and hid the real error.

For a Box that still drops, the optional [Box firmware fix](firmware.md#qidi-box-shutdown-fix) keeps it connected so Klipper shows why, and the [Box link monitor](troubleshooting.md#box-link-monitor) records what happened.

## Unknown Box filaments shutting Klipper down

Loading a slot whose saved filament isn't in QIDI's list no longer shuts Klipper down. See [QIDI Box](qidi-box.md#filaments-missing-from-qidis-list).

## Box loads stuck at `无法识别到已进料耗材`

A Box load no longer stalls on every try when a slot's filament is at the Box hub but no slot is recorded as loaded. See [QIDI Box](qidi-box.md#stuck-box-loads).

## Multi-plate 3MF files

A 3MF file started without a plate number, for example from Fluidd, a reprint, or the job queue, prints the plate it was sliced on instead of plate 1. Before, files exported from a plate other than plate 1 failed with `3MF processing error: [Errno 2] No such file or directory`.

## Faster Moonraker startup

Unchanged 3MF files reuse their metadata instead of being re-extracted every time Moonraker starts. The first restart after installing rebuilds it once, and after that only new or changed files are read. Manual metadata rescans keep QIDI's thumbnails, and a failed rescan keeps the previous metadata.

## Z offset reset to 0

Cancelling a print during its start no longer wipes your saved Z offset to `0`. See [Print start](print-start.md#z-offset).

## Box eject homing the toolhead

An eject that only needs the Box to pull filament back no longer homes and parks the toolhead. See [QIDI Box](qidi-box.md#eject).
