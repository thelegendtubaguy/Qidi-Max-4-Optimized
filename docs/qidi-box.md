# QIDI Box

[← Back to the README](../README.md)

The **QIDI Box** card in [this project's Fluidd](fluidd.md) shows every Box's slots, the filament path, and tool mapping, and controls loading, the Box heater, and Box settings. See [thelegendtubaguy/fluidd](https://github.com/thelegendtubaguy/fluidd) for how to use it.

This page covers what the optimized configuration changes for the Box.

## Tool mapping

A normal print end restores the default tool mapping, T0 → 1A, T1 → 1B, and so on. `TLTG_RESET_TOOL_MAPPINGS` restores it while the printer is idle.

## Box heater

Box heater targets can be set from Fluidd, up to 65 °C, the Box's advertised maximum.

Each Box's processor temperature shows in Fluidd's temperature card as **Box1 MCU** through **Box4 MCU**. These sensors have no limits, so they never stop a print.

## Load and unload speed

A load pushes filament fast for most of the way, then approaches slowly until the toolhead filament sensor trips. An unload has the extruder pull the filament back before the Box retracts it.

The installer saves faster defaults, unless you've already saved any of these settings, in which case all of yours are kept. Change them in Fluidd's QIDI Box card, or with `TLTG_BOX_MOTION` in the console. Run `TLTG_BOX_MOTION` with no parameters to see the current settings and each slot's profile.

| Parameter | What it sets | This project | QIDI | Allowed |
|---|---|---|---|---|
| `FAST_LENGTH` | How far the fast push goes, in mm | 950 | 930 | 100–2000 |
| `FAST_SPEED_1` | Speed of the first fast stage, in mm/s | 120 | 85 | 10–150 |
| `FAST_SPEED_2` | Speed of the second fast stage, in mm/s | 100 | 65 | 10–150 |
| `APPROACH_SPEED` | Speed for the rest of the way to the toolhead sensor, in mm/s | 15 | 10 | 2–40, below both fast speeds |
| `LOAD_ACCEL` | Load acceleration | QIDI's | 100 | 20–400 |
| `UNLOAD_SPEED_1`, `UNLOAD_SPEED_2` | Speeds of the two unload stages, in mm/s | 115, 120 | 65, 85 | 10–150, must differ |
| `UNLOAD_ACCEL` | Unload acceleration | QIDI's | 100 | 20–400 |
| `UNLOAD_EXTRUDER_LENGTH` | How far the extruder pulls filament back before the Box takes over, in mm. All slots only. | 50 | 120 | 20–300 |

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

- **`FAST_LENGTH`** is used exactly as set. On the test printer, filament reached the toolhead sensor 1001–1016 mm into the push, so QIDI's 930 mm leaves about 70–85 mm for the slow approach. Set it past the sensor and filament reaches the toolhead at full speed.
- **`UNLOAD_EXTRUDER_LENGTH`:** an unload starts with the extruder pulling the cut filament back 30 mm, then this much more at 10 mm/s, before the Box takes over. On the test printer the filament left the toolhead sensor 34 mm into the unload, about 4 mm into this second pull, so most of QIDI's 120 mm is slow pulling of free filament. The sensor sits above the extruder gears, so once it clears, the filament is out of the gears. A value of 20–30 mm keeps a margin and saves about 9 seconds per unload.

If a setting saved with `SAVE_VARIABLE` is invalid, the affected load or unload uses QIDI's motion and the console says why. If a QIDI firmware update changes how the Box moves filament in a way these settings don't recognize, the Box keeps QIDI's motion and the console says so.

## Eject

QIDI's eject parks the toolhead over the waste chute before and after the Box pulls the filament back, so it homes X and Y on a printer that isn't homed. When the eject only needs the Box to pull filament back, because nothing is fed past the Box hub or another slot's filament is loaded, the toolhead now stays where it is. An eject that first has to heat and unload filament from the toolhead still parks the way QIDI does. Either way the eject turns the hotend off and disables the extruder motor afterward.

## Moving a slot by hand

`TLTG_BOX_SLOT_JOG` moves a slot's filament toward the toolhead or back toward the spool, for example to back filament off the Box hub or work a tangle loose:

```gcode
TLTG_BOX_SLOT_JOG SLOT=1 DISTANCE=-10
```

The QIDI Box card in Fluidd has **In** and **Out** buttons that jog the selected slot 10 mm.

`DISTANCE` is in mm, positive toward the toolhead, up to 1500 either way. `SPEED` is optional: 20 mm/s by default, up to 100. Slots are numbered from 0, so 1B is slot 1.

- The slot moves whatever its sensors read and whatever the printer has recorded as loaded. QIDI's saved Box state, such as which slot is loaded, isn't changed.
- The extruder doesn't turn during a jog, so jogging the filament that's in the extruder pushes or pulls against its gears.
- A jog is refused while a print is running or paused or the Box is busy.
- Jogging out until the slot's inlet sensor no longer sees filament takes the filament out of the slot's feeder, and jogging in won't grab it again. Push it back into the inlet by hand, and the Box loads it as it does any newly inserted filament. With long tubes to the hub, that can take well over a meter of jogging.
- A jog that brings filament to the Box hub, or clears it, updates the printer's record of which slot is at the hub, as for [stuck Box loads](#stuck-box-loads).

## Editing QIDI's filament list

On firmware `01.01.07.01`, the Vendor and Filament lists on the touchscreen and in Fluidd come from QIDI's filament files. The installer adds a `qidi_filament_config` folder to Fluidd's configuration files that opens them:

- `filament-0.4.json` is the list for the 0.4 mm nozzle; the other files cover the other nozzle sizes. Right-click a file and choose **Edit**.
- **To add a filament,** copy an entry of the same material and give it a new name, an unused `filament_id`, and the vendor to list it under. A new vendor name adds that vendor to the pickers.
- **Keep the material letter** of the copied entry's `filament_id`: the letter after `QF` is `A` for PLA, `B` for ABS and ASA, `C` for PC, `G` for PETG, `N` for PA, `U` for TPU, and so on. For example, a new PLA could use `QFA93` if no other entry has it.
- **Keep it valid JSON.** A missing comma or bracket can break the touchscreen's filament list.
- **After saving,** restart Klipper so the Box and Fluidd pick up the change, and restart `qidi-client` from Fluidd's power menu, or reboot the printer, so the touchscreen does too.
- If you change the `filament_id` of a filament a Box slot is set to, choose that filament for the slot again.

> [!WARNING]
> These are QIDI's own files, not copies. Firmware updates replace them, so keep a copy of any entries you add. They aren't part of the installer's backups, and deleting one in Fluidd deletes it from the printer.

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

## Box disconnects

See [Fixes](fixes.md#qidi-box-disconnects) for what this project changes, and [Troubleshooting](troubleshooting.md#box-link-monitor) to record why a Box drops.

## RS-485 Boxes

QIDI's firmware `01.01.07.01` includes support for Boxes, buffers, and filament racks that connect over RS-485 through a USB adapter, alongside the USB Boxes that run Klipper. This project hasn't been tested with RS-485 hardware yet, so it watches for it:

- **If you have RS-485 hardware,** the console asks you to open a [GitHub issue](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/issues) once per Klipper start. Attach `tltg_box485_report.json` and `tltg_box485.log` from the `logs` folder in Fluidd. The log records what QIDI's code sends to and receives from each device, and the report summarizes the setup. Chip ids and USB serial numbers are replaced with codes that can't be traced back to your hardware. Nothing about how the hardware works is changed.
- **To write the report yourself,** run `TLTG_RS_BOX_REPORT`. It says whether RS-485 hardware was found.
- **Without RS-485 hardware,** nothing is written. QIDI's software looks for an RS-485 adapter every 2 seconds and logs `Can not find 485 device` each time. That's normal for USB Boxes; `klippy.log` now gets that line once an hour, with a count.

> [!WARNING]
> Don't put a USB Box's id from `box.cfg` into `[box485] serial_port` in `printer.cfg`. It stops the `Can not find 485 device` lines, but QIDI's RS-485 code then reads that Box's connection and takes Klipper's messages, so the Box drops. The optimized configuration keeps the RS-485 code from opening a Klipper port and says so in the console. Set `serial_port` back to `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`.
