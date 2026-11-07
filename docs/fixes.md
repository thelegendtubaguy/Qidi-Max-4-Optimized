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

## Klipper slowing down during long Box prints

Every QIDI Box load left three of QIDI's timers behind in Klipper, from the load-cell check that confirms the filament reached the nozzle. Klipper checks every timer many times a second, so it got busier with each filament change. After about 400 changes it was busy most of the time even while idle, and a Box motor move could fail with `Communication timeout during homing`, which cancelled the print. Those timers are now removed once QIDI is done with them, and a filament change that fails that way [pauses the print](qidi-box.md#failed-tool-changes-during-a-print) instead.

Klipper also watches how busy it is. If its timers keep piling up, or it stays more than 45% busy for five minutes, the console says so, at most once an hour. If a homing move times out, the console says which board's sync timed out, how far apart each board sent its status reports and Klipper received them, and how busy Klipper was just before. That includes the nozzle load-cell probe's `WEIGHT sensor error`, which is how QIDI reports a timed-out probe move, not a fault in the load cell. A move that involves more than one board stays armed only while each board reports every 15 ms. Reports sent far apart point at the board; reports sent on time but received far apart point at the connection or the printer's CPU. `klippy.log` also gets each board's last reports. `klippy.log` gets a `tltg_klipper_health` line every minute with the timer count and how busy Klipper was.

In Fluidd, the **System Utilization** card on the System page charts both: **Klipper Main Thread** under Klipper Load, and **Klipper Timers**. Klipper Load counts all of Klipper's threads; the main thread is the one that has to keep up. The timer count stays around 60.

Klipper also does less work on its main loop, so Box motor moves keep more headroom:

- QIDI's Box modules save their own settings the slow way that `SAVE_VARIABLE` used to: a full rewrite of `saved_variables.cfg` and a re-read, even when nothing changed. Box print start saved about 20 settings, holding Klipper for about 1.3 seconds, and every filament change saved about 8 more. They now skip unchanged settings and write the file safely, as `SAVE_VARIABLE` does.
- The optimized filament-change, temperature-wait, and homing macros no longer copy QIDI's large Box and configuration status each time they run, which held Klipper for 10–50 ms each.
- QIDI's Box status, which Fluidd and the touchscreen read every second, takes about half as long to build, and every macro, QIDI's included, reads printer settings and status faster. QIDI's start-up macro, which held Klipper for about 0.8 seconds after every start, is faster too.
- With USB Boxes only, QIDI's software looks for an RS-485 adapter every 30 seconds instead of every 2.
- Spoolman's slot tracking reads the loaded slot directly instead of building QIDI's Box status twice a second.
- Klipper checks its timers, about 70 of them, many times a second; that now takes about a third less time.
- QIDI's once-a-second status update for Fluidd and the touchscreen skips macros whose values haven't changed and compares QIDI's Box status faster. Fluidd and the touchscreen receive the same updates.

The timer and status changes come from the same module as the [fixes from newer Klipper](#fixes-from-newer-klipper), with the same check: each is skipped, and listed as skipped in `klippy.log`, if QIDI's code isn't exactly the version it was written for.

## Klipper sharing the CPU with the touchscreen

QIDI runs Klipper, Moonraker, and the touchscreen app at the same CPU priority, so a busy touchscreen app or Moonraker could delay Klipper. Klipper now gets the CPU first, then Moonraker, then the touchscreen app.

## Fixes from newer Klipper

QIDI's Klipper is upstream Klipper from August 2024 with QIDI's changes. These later upstream fixes are applied to it when Klipper starts:

- Homing moves, including the Box's, set up their endstop sync for the start of the move. Before, the setup could wait behind the move's own step messages.
- A Box or toolhead board that restarts by itself now stops Klipper with `MCU '…' spontaneous restart`. Before, Klipper carried on and failed later with a misleading error.
- Once Klipper loses contact with a Box or board, commands waiting on it fail with `No communication with MCU` instead of waiting forever and holding up every later command.
- A stepper disable that arrives while its driver is still being enabled waits for the enable to finish.
- Heaters turn off if Klipper's main loop stops for 5 seconds while temperature readings keep arriving. A heater's temperature reads 0 only 7 seconds after its last reading, instead of 5, so a lost board is reported as lost rather than as a heater fault.
- A Klipper timer can't be started again while an earlier run of it is still waiting.
- Python's garbage collector skips everything Klipper set up at startup, so its periodic full collections have less to check.

`klippy.log` lists the fixes applied at each start. A fix is skipped, and listed as skipped, if the Klipper code it replaces isn't exactly the version it was written for.

## Motors turning on late

On the Max 4, QIDI's Klipper turns a motor on 0.3 seconds before it moves, so the motor holds its position first. After homing turns X and Y off, the first homing move starts only about 0.16 seconds ahead, so the turn-on was scheduled in the past. The mainboard ran it as soon as it arrived and logged `Timer too close` in `klippy.log`, nearly always between the `ENABLE delay: stepper=stepper_x` and `stepper_y` lines. The turn-on now goes as early as the mainboard can still take it on time, about 0.14 seconds before the move during homing, and never after the move. When 0.3 seconds early is still possible, nothing changes. QIDI's `ENABLE delay` line in `klippy.log` shows the time used. It comes from the same module as the [fixes from newer Klipper](#fixes-from-newer-klipper), with the same check. The Plus 5's Klipper turns motors on at the move, so it needs no change.

A few `Timer too close` lines during prints have no known cause yet. When Klipper sends a board a command, such as a pin or fan change, whose time has already passed or is under 5 ms away, `klippy.log` gets a `late MCU command` warning naming the board, the command, how late it was, and the Klipper code that sent it, at most once every 10 seconds for each command. Please include those lines when reporting a problem.

## X/Y motors skipping at top speed

QIDI sets the Max 4's top speed to 800 mm/s, but that limit applies to the toolhead, not to each motor. The Max 4 is a CoreXY: a diagonal move turns one X/Y motor up to 1.41 times as fast as the toolhead moves, so at 800 mm/s one motor's belt runs at about 1130 mm/s. On the test printer, back-and-forth diagonals at 800 mm/s and 30000 mm/s² made the X motor skip about 60 mm of belt, loudly, and the printer didn't notice. At 500 mm/s, where the motor's belt runs at about 710 mm/s, nothing skipped.

The top speed is now 565 mm/s, which keeps every motor at or below 800 mm/s of belt in any direction. Moves between bed mesh and leveling points, and this project's fastest travel moves, run at 565 mm/s instead of 600 and 750. A slicer or command that sets a higher speed with `SET_VELOCITY_LIMIT VELOCITY=` or `M203` gets 565 mm/s and a console note, as QIDI's Klipper already does for acceleration. The slicer's own speeds, up to 500 mm/s travel in QIDI's Max 4 profile, are unchanged. Install and update lower any `max_velocity`, bed mesh `speed`, or Z-tilt `speed` in `printer.cfg` above 565 to 565, including ones you set yourself; lower values are kept, and uninstall puts back the values you had. The [X/Y step-loss monitor](tools.md#xy-step-loss-monitor) can tell you if a motor skips anyway.

## Unknown Box filaments shutting Klipper down

Loading a slot whose saved filament isn't in QIDI's list no longer shuts Klipper down. See [QIDI Box](qidi-box.md#filaments-missing-from-qidis-list).

## Box loads stuck at `无法识别到已进料耗材`

A Box load no longer stalls on every try when a slot's filament is at the Box hub but no slot is recorded as loaded. See [QIDI Box](qidi-box.md#stuck-box-loads).

## `FLOW_STOP` hanging Klipper

Stopping a failed Box load with `FLOW_STOP` no longer leaves every later command waiting and the nozzle hot until Klipper is restarted. See [QIDI Box](qidi-box.md#failed-box-loads-and-unloads).

## Box filament stranded between the hub and the toolhead

Unload and Eject now pull back a slot's filament that a failed load left between the Box hub and the toolhead. See [QIDI Box](qidi-box.md#filament-stopped-between-the-hub-and-the-toolhead).

## Multi-plate 3MF files

A 3MF file started without a plate number, for example from Fluidd, a reprint, or the job queue, prints the plate it was sliced on instead of plate 1. Before, files exported from a plate other than plate 1 failed with `3MF processing error: [Errno 2] No such file or directory`.

## Filaments a file uses

Fluidd's Box print dialog lists the filaments Moonraker says a file uses. Moonraker now reads them from what the slicer wrote for that file: for a 3MF, the filaments its plate uses; for an OrcaSlicer G-code file, the filaments it gives a length. Before, OrcaSlicer G-code files named none, and when OrcaSlicer exported several plates into one 3MF, only the plate selected in OrcaSlicer named any, and it named every plate's filaments.

## Faster Moonraker startup

Unchanged 3MF files reuse their metadata instead of being re-extracted every time Moonraker starts. The first restart after installing rebuilds it once, and after that only new or changed files are read. Manual metadata rescans keep QIDI's thumbnails, and a failed rescan keeps the previous metadata.

## Z offset reset to 0

Cancelling a print during its start no longer wipes your saved Z offset to `0`. See [Print start](print-start.md#z-offset).

## Box eject homing the toolhead

An eject that only needs the Box to pull filament back no longer homes and parks the toolhead. See [QIDI Box](qidi-box.md#eject).
