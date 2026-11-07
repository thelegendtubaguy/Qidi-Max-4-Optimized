# QIDI Box

[← Back to the README](../README.md)

The **QIDI Box** card in [this project's Fluidd](fluidd.md) shows every Box's slots, the filament path, and tool mapping, and controls loading, the Box heater, and Box settings. See [thelegendtubaguy/fluidd](https://github.com/thelegendtubaguy/fluidd) for how to use it.

This page covers what the optimized configuration changes for the Box.

## Tool mapping

A normal print end restores the default tool mapping, T0 → 1A, T1 → 1B, and so on. `TLTG_RESET_TOOL_MAPPINGS` restores it while the printer is idle.

## Tool changes outside a print

`T0` through `T15`, which are also the tool buttons in Fluidd's Tool card, are QIDI's print-time tool change: they cut the loaded filament, unload it, and load the tool's slot without heating the nozzle. Outside a print they ran anyway, with the nozzle cold or cooling, and could leave the Box busy and the printer paused with no print. They now run only while a print is running or paused. Otherwise nothing moves and the console says:

```text
T4 not run: QIDI's tool change runs only during a print. To load a slot, use Load on the QIDI Box card or LOAD_FILAMENT_CONTROL SLOT=<n>.
```

**Load** on the QIDI Box card heats the nozzle for the slot's filament and swaps out whatever is loaded.

## Box heater

Box heater targets can be set from Fluidd, up to 65 °C, the Box's advertised maximum.

Each Box's processor temperature shows in Fluidd's temperature card as **Box1 MCU** through **Box4 MCU**. These sensors have no limits, so they never stop a print.

## Load and unload speed

A load pushes filament fast for most of the way, then approaches slowly until the toolhead filament sensor trips. An unload has the extruder pull the filament back before the Box retracts it.

These settings work on the Max 4 only. On the Plus 5, QIDI's Box code loads and unloads with different moves, so the settings stay off there and `TLTG_BOX_MOTION` reports them inactive.

The installer saves this project's defaults, unless you've already saved any of these settings, in which case all of yours are kept. The fast and unload speeds match QIDI's; the shorter extruder pull-back and the faster approach save time. Earlier versions saved faster speeds, 120/100 mm/s for the fast push and 115/120 mm/s for the unload, and a 50 mm extruder pull-back. Updating lowers either speed pair to QIDI's speeds if both of its speeds are still at those values, raises a pull-back still at 50 mm to 55 mm, and keeps anything you've changed. Change them in Fluidd's QIDI Box card, or with `TLTG_BOX_MOTION` in the console. Run `TLTG_BOX_MOTION` with no parameters to see the current settings and each slot's profile.

| Parameter | What it sets | This project | QIDI | Allowed |
|---|---|---|---|---|
| `FAST_LENGTH` | How far the fast push goes, in mm | 950 | 930 | 100–2000 |
| `FAST_SPEED_1` | Speed of the first fast stage, in mm/s | 85 | 85 | 10–150 |
| `FAST_SPEED_2` | Speed of the second fast stage, in mm/s | 65 | 65 | 10–150 |
| `APPROACH_SPEED` | Speed for the rest of the way to the toolhead sensor, in mm/s | 15 | 10 | 2–40, below both fast speeds |
| `LOAD_ACCEL` | Load acceleration | QIDI's | 100 | 20–400 |
| `UNLOAD_SPEED_1`, `UNLOAD_SPEED_2` | Speeds of the two unload stages, in mm/s | 65, 85 | 65, 85 | 10–150, must differ |
| `UNLOAD_ACCEL` | Unload acceleration | QIDI's | 100 | 20–400 |
| `UNLOAD_EXTRUDER_LENGTH` | How far the extruder pulls filament back before the Box takes over, in mm. All slots only. | 55 | 120 | 20–300 |

```gcode
TLTG_BOX_MOTION FAST_SPEED_1=100 FAST_SPEED_2=100 APPROACH_SPEED=20
```

Settings take effect on the next load or unload, without a restart. The command refuses a combination the Box can't run and says why.

- **One setting back to QIDI's:** `PARAM=vendor`, for example `FAST_SPEED_1=vendor`.
- **Everything back to QIDI's,** including slot settings: `TLTG_BOX_MOTION RESET=1`. Updates won't reapply this project's defaults after that.

### Per-slot settings

Any setting can also be set for one slot, which overrides the all-slots setting. For example, to load slot 2 more gently:

```gcode
TLTG_BOX_MOTION SLOT=2 FAST_SPEED_1=60 FAST_SPEED_2=60 APPROACH_SPEED=8
```

Slots are numbered from 0, the same as `LOAD_FILAMENT_CONTROL SLOT=`, so the card's 1A is slot 0 and 2A is slot 4. `SLOT=2 FAST_SPEED_1=global` makes slot 2 follow the all-slots setting again, and `SLOT=2 RESET=1` clears all of slot 2's settings.

### Choosing values

- **`FAST_LENGTH`** is used exactly as set. On a Max 4, filament reached the toolhead sensor 1001–1016 mm into the push, so QIDI's 930 mm leaves about 70–85 mm for the slow approach. Set it past the sensor and filament reaches the toolhead at full speed.
- **`UNLOAD_EXTRUDER_LENGTH`:** an unload starts with the extruder pulling the cut filament back 30 mm, then this much more at 10 mm/s, before the Box takes over. The sensor sits above the extruder gears, so once it clears, the filament is out of the gears. How far that takes varies between printers. On one Max 4 the filament left the sensor 34 mm into the unload, about 4 mm into this second pull; on another, it once left only as a 50 mm pull ended. The 55 mm default keeps some margin over that and saves about 6.5 seconds per unload over QIDI's 120 mm. If unloads fail with `QDE_004_008` (`Extruder unloading failure.`) and nothing is caught between the Box and the toolhead, set it back to QIDI's with `TLTG_BOX_MOTION UNLOAD_EXTRUDER_LENGTH=vendor`.

If a setting saved with `SAVE_VARIABLE` is invalid, the affected load or unload uses QIDI's motion and the console says why. If a QIDI firmware update changes how the Box moves filament in a way these settings don't recognize, the Box keeps QIDI's motion and the console says so.

## Eject

QIDI's eject parks the toolhead over the waste chute before and after the Box pulls the filament back, so it homes X and Y on a printer that isn't homed. When the eject only needs the Box to pull filament back, because nothing is fed past the Box hub or another slot's filament is loaded, the toolhead now stays where it is. An eject that first has to heat and unload filament from the toolhead still parks the way QIDI does. Either way the eject turns the hotend off and disables the extruder motor afterward.

## Cutting the filament

`TLTG_CUT_FILAMENT`, and **Cut** on the QIDI Box card, cuts the filament at the toolhead without heating the nozzle, for example to free Box filament caught in the hub from Fluidd. It homes X and Y first if either isn't homed, then runs the same cutter moves as a filament change. On the Max 4, the cutter cuts cold filament and the extruder sits above the cutter, so the extruder's 4 mm pull-back after the cut moves only filament that never enters the hotend. The piece below the cut stays in the hotend until the next load pushes it out, as after any cut.

- The nozzle heater isn't changed. Klipper normally refuses every extruder move, pull-backs included, with the nozzle below `min_extrude_temp` (135 °C on the Max 4). During the cut it allows pull-backs and still refuses pushing filament forward.
- The acceleration and positioning mode are put back afterwards, even if the cut stops with an error.
- It's refused while a print is running or paused, or while the Box is busy, including while a failed Box step waits for `FLOW_RETRY` or `FLOW_STOP`.

### Unloading and ejecting cold

QIDI's Box unload and eject first heat the nozzle to the top of the filament's printing range, 280 °C for some ASA, then cut and pull the filament back. With `COLD=1` they run the same steps without heating:

```gcode
UNLOAD_FILAMENT_CONTROL SLOT=1 COLD=1
EJECT_FILAMENT_CONTROL SLOT=1 COLD=1
```

**Unload** and **Eject** on the QIDI Box card send `COLD=1` unless a print is paused. The toolhead parks over the waste chute, homing X and Y first if needed, then the filament is cut and pulled back as usual. The nozzle heater stays off, and with no heat there's no ooze, so QIDI's 5 second wait and nozzle wipe at the end are skipped. Only pull-backs are allowed with the nozzle cold, as for the cut.

- `COLD=1` is refused while a print is running or paused.
- If a step fails, **Retry** (`FLOW_RETRY`) runs it cold again.
- An unload that would also unload the external spool still heats, and the console says so.
- If a cold unload keeps failing, for example because the cut didn't go all the way through, **Stop** it, then unload from the console without `COLD=1` to heat the nozzle as QIDI does.

## Moving a slot by hand

`TLTG_BOX_SLOT_JOG` moves a slot's filament toward the toolhead or back toward the spool, for example to back filament off the Box hub or work a tangle loose:

```gcode
TLTG_BOX_SLOT_JOG SLOT=1 DISTANCE=-10
```

The QIDI Box card in Fluidd has **In** and **Out** buttons that jog the selected slot 10 mm.

`DISTANCE` is in mm, positive toward the toolhead, up to 1500 either way. `SPEED` is optional: 20 mm/s by default, up to 100. Slots are numbered from 0, so 1B is slot 1.

- The slot moves whatever its sensors read and whatever the printer has recorded as loaded. QIDI's saved Box state, such as which slot is loaded, isn't changed.
- The extruder doesn't turn during a jog, so jogging the filament that's in the extruder pushes or pulls against its gears.
- A jog is refused while a print is running or paused or the Box is busy, including while a failed Box step waits for `FLOW_RETRY` or `FLOW_STOP`.
- Jogging out until the slot's inlet sensor no longer sees filament takes the filament out of the slot's feeder, and jogging in won't grab it again. Push it back into the inlet by hand, and the Box loads it as it does any newly inserted filament. With long tubes to the hub, that can take well over a meter of jogging.
- A jog that brings filament to the Box hub, or clears it, updates the printer's record of which slot is at the hub, as for [stuck Box loads](#stuck-box-loads).

## Editing QIDI's filament list

On Max 4 firmware `01.01.07.01`, the Vendor and Filament lists on the touchscreen and in Fluidd come from QIDI's filament files. Fluidd's **Filaments** page in the sidebar edits the list for the 0.4 mm nozzle, `filament-0.4.json`, the one Klipper and the touchscreen read:

- **Add** or **Duplicate** a filament, then set its vendor, name, type, nozzle temperatures, Box heating limit, chamber temperature, and whether it's a support material. A new vendor name adds that vendor to the pickers. The new filament gets the next free ID and takes its drying and other settings from the filament you duplicated, or else from Generic's filament of the same type.
- **Edit** changes the same fields of any filament. Its ID stays as it is, because Box slots refer to filaments by ID. **Remove** names any Box slot set to the filament before deleting it.
- Each change is saved to the printer straight away. Klipper, the Box, and the touchscreen use it once Klipper and `qidi-client` restart: choose **Restart Klipper and touchscreen** on the page, or reboot the printer.
- **Export** downloads the list, and **Import** puts filaments from an exported file back. Import selects the filaments missing from the list, and leaves unselected the ones that differ from it, as the difference may be QIDI's.

The installer makes this possible by adding a `qidi_filament_config` folder to Fluidd's configuration files, linked to QIDI's filament files. The other nozzle sizes' files are there too, and any of them can be edited by hand: right-click a file and choose **Edit**. Keep it valid JSON, as a missing comma or bracket can break the touchscreen's filament list.

> [!WARNING]
> These are QIDI's own files, not copies. Firmware updates replace them and remove your changes, so **Export** the list before updating and **Import** it afterwards. They aren't part of the installer's backups.

If `qidi_filament_config` already exists, the installer leaves it alone. Uninstall removes the link but never your edits.

## Filaments missing from QIDI's list

If a Box slot or the external spool has a saved filament that isn't in QIDI's list, such as `None`, QIDI's load fails with `Internal error on command:"LOAD_FILAMENT_CONTROL"` and shuts Klipper down. The load now uses QIDI PLA Basic temperatures instead, the way QIDI already does for some older saved values, and the console names the saved filament. Choose the slot's filament again to clear it.

Setting the external spool to a filament that isn't in QIDI's list is refused with `External spool filament not changed`, as QIDI already does for Box slots.

## Stuck Box loads

If a slot's filament sits at the Box hub but the printer has no slot recorded as loaded, a Box load has QIDI unload the hub first, and QIDI's unload stops with `无法识别到已进料耗材` ("can't identify the loaded filament") and `Step BOX_UNLOAD failed. Pausing flow.` It does the same on every retry. This can happen when a Box disconnects while it feeds newly inserted filament up to the hub.

The printer now remembers which slot fed filament to the hub, in the saved variable `tltg_box_hub_slot`. When that slot, or the only slot holding filament, still has filament at its inlet, the load unloads it and carries on, and the console names the slot.

Otherwise the console says so and lists the slots with filament, and the nozzle is turned off unless a print is running or paused. Follow the filament from the hub back to its slot, then save that slot and continue the load:

```gcode
SAVE_VARIABLE VARIABLE=last_load_slot VALUE='"slot1"'
FLOW_RETRY
```

Slots are numbered from 0: `slot0` is 1A, `slot1` is 1B, and `slot4` is 2A. `FLOW_RETRY` heats the nozzle again and repeats the unload. Each time, `klippy.log` gets a `tltg_box_loaded_slot: Box unload has no loaded slot` line with the Box's state; include it when [reporting a problem](troubleshooting.md#reporting-a-problem).

## Failed Box loads and unloads

When a step of a Box load, unload, or eject fails, QIDI pauses it with a line such as `Step BOX_LOAD failed. Pausing flow.`, usually after an error such as `Code:QDE_004_006; Message:Extruder loading failure.` The nozzle stays at the load temperature. The touchscreen offers no way out, but the QIDI Box card in Fluidd does, and so does the console:

- **`FLOW_RETRY`** heats the nozzle again and repeats the failed step.
- **`FLOW_STOP`** ends the paused flow. With no print running or paused, it also turns the nozzle off. During a print, the nozzle stays hot so the print can resume.

With QIDI's own code, `FLOW_STOP` on a paused flow never finished: every later command waited behind it, and only restarting Klipper, followed by `FIRMWARE_RESTART`, got the printer back. It now finishes straight away.

A step can also end with an error instead of failing, such as `Error during homing e_endstop: Communication timeout during homing` from a Box motor move. QIDI then left the flow running with the nozzle hot, and neither the card nor `FLOW_RETRY` could do anything with it. The flow is now paused on that step, with `Step BOX_LOAD failed. Pausing flow.` before the error, so Retry and Stop work as for any failed step.

QIDI's Box moves, such as the park over the waste chute, assume absolute positioning but don't set it. If relative positioning was left on, for example by a command that stopped with an error before switching back, every heat step failed with `Move out of range` until Klipper restarted. A load, unload, or eject started or retried with no print running or paused now switches to absolute positioning first, as `G90` does. During a print, positioning is left as the print set it.

### Failed tool changes during a print

When a step of a filament change during a print fails, QIDI pauses the print, and **Resume** finishes the change from wherever the filament stopped, then carries on printing. A step that ended with an error instead, such as `Error during homing b_endstop: Communication timeout during homing` while unloading, cancelled the print. It now pauses the print the same way, and the console says which step failed and why, for example `T1 failed at BOX_UNLOAD: Error during homing b_endstop: Communication timeout during homing. The print is paused; RESUME tries the tool change again.` Only a Klipper shutdown, such as a lost Box connection, still ends the print.

### Filament stopped between the hub and the toolhead

A load that gets the filament to the Box hub but not to the toolhead, for example because the tube to the toolhead is longer than `FAST_LENGTH` allows for, leaves the filament in the tube between them. QIDI already counts that slot as loaded. Its Unload then does nothing but park the toolhead and report success, and its Eject heats the nozzle first.

With no print running or paused, **Unload** and **Eject** of that slot now pull its filament back out of the hub, a paused flow is stopped first, and the nozzle isn't heated:

- **Unload** pulls the filament back until the hub sensor clears, then about 220–260 mm further, which parks it in the Box as QIDI's unload does. The slot is then ready to load again.
- **Eject** pulls it back until the hub sensor clears, then runs QIDI's eject, which pulls the filament out of the slot's feeder.

The slot is the one that last fed filament to the hub, or the one QIDI last loaded, as long as its inlet sensor still detects filament. When neither tells, the only slot with filament is used. Otherwise, or when you ask for a different slot, nothing moves and the console says why. If the slot's filament leaves its inlet sensor while the hub sensor still detects filament, the filament at the hub isn't that slot's, or it broke. The pull stops there, and the console says so.

Unload of a slot whose filament isn't past the hub doesn't run. The console says so, instead of QIDI parking the toolhead and reporting success.

## Resuming a paused print

Pausing turns the nozzle off. With the Box, **Resume** first moves the toolhead to the waste chute and heats the nozzle back to the temperature it had when the print paused, then runs QIDI's resume, which reloads the filament and carries on printing. QIDI's resume cuts before it heats, so after a pause long enough for the nozzle to cool below 135 °C it stopped with `Extrude below minimum temp`, and the print stayed paused until the nozzle was heated by hand.

## Box disconnects

See [Fixes](fixes.md#qidi-box-disconnects) for what this project changes, and [Troubleshooting](troubleshooting.md#box-link-monitor) to record why a Box drops.

## RS-485 Boxes

QIDI's Max 4 firmware `01.01.07.01` includes support for Boxes, buffers, and filament racks that connect over RS-485 through a USB adapter, alongside the USB Boxes that run Klipper. This project hasn't been tested with RS-485 hardware yet, so it watches for it:

- **If you have RS-485 hardware,** the console asks you to open a [GitHub issue](https://github.com/thelegendtubaguy/valve-oil/issues) once per Klipper start. Attach `tltg_box485_report.json` and `tltg_box485.log` from the `logs` folder in Fluidd. The log records what QIDI's code sends to and receives from each device, and the report summarizes the setup. Chip ids and USB serial numbers are replaced with codes that can't be traced back to your hardware. Nothing about how the hardware works is changed.
- **To write the report yourself,** run `TLTG_RS_BOX_REPORT`. It says whether RS-485 hardware was found.
- **Without RS-485 hardware,** nothing is written. QIDI's software looks for an RS-485 adapter and logs `Can not find 485 device` each time it's missing. That's normal for USB Boxes. Until RS-485 hardware has been seen, it now looks every 30 seconds instead of every 2, so a newly connected adapter can take up to 30 seconds to be found, and `klippy.log` gets that line once an hour, with a count.

> [!WARNING]
> Don't put a USB Box's id from `box.cfg` into `[box485] serial_port` in `printer.cfg`. It stops the `Can not find 485 device` lines, but QIDI's RS-485 code then reads that Box's connection and takes Klipper's messages, so the Box drops. The optimized configuration keeps the RS-485 code from opening a Klipper port and says so in the console. Set `serial_port` back to `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`.
