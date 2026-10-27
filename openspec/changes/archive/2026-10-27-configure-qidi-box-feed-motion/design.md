## Context

A Box load moves filament from the slot's park position, just behind the hub filament sensor, through the hub buffer and PTFE tube to the toolhead filament switch. The vendor then syncs the slot to the extruder for a hot bite. An unload is a hot synced retract followed by a Box-only retract to park. Evidence is in `openspec/observations/qidi-box/hardware-and-protocols.md`.

What we know on `.07.01`, from live wrapper traces of vendor slot 2 loads and unloads:

- **Load** runs a pre-stage (`extruder_load_length_1`, about +317 mm and −31 mm in an earlier position trace), then `do_home_three_steps(endstops, l1, l2, l3, v1, v2, v3, accel, False)`. That home calls `do_move_triple_steps` with its own arguments and returns `True` when the toolhead switch (`e_endstop`) is reached. Vendor values are 550/380/240 mm at 85/65/10 mm/s with acceleration 100.
- **Unload** runs `do_home_double_steps(endstops, l1, l2, v1, v2, accel, True)` toward the hub sensor (`b_endstop`) after the synced retract. Vendor values are −350/−1150 mm at 65/85 mm/s with acceleration 100.
- **Settings lookup.** Each value comes from `box_extras.get_value_by_key(name, default)`, which returns the live saved variable of the same name (`multi_extruder_load_*`, `multi_extruder_unload_*`) or the compiled default.
- **Wrappers work.** Wrappers set on each `box_stepper slotN` instance are called, and replacing `do_home_*_steps` arguments changed the motion. A load at 85/85/20 mm/s reached the switch after 1004.9 mm of slot travel in 16.5 s, against about 21 s for the vendor profile, and the vendor flow completed normally.
- **Planner limits.** The vendor planner rejects infeasible profiles. Earlier tests hit a minimum-final-stage error with speeds 150/120/30 and an 80 mm final stage, and a division by zero when both unload speeds were equal. A final stage too short to reach the switch (a 105 mm patch) returned `False` and sent the load into the vendor retry path.

## Goals / Non-Goals

**Goals:**

- Every load pushes fast to a configurable distance near the toolhead switch, then approaches at a configurable speed until the switch trips.
- Operators control the fast distance, the speed of each fast stage, the approach speed, and acceleration for loads, and the stage speeds and acceleration for unloads.
- Absent, invalid, or unsupported settings keep vendor motion.

**Non-Goals:**

- The load pre-stage and the stages after the home: cut, synced retract, bite, purge, wipe.
- Vendor flows, retries, `QDE_004_*` errors, RFID, feed assist, dryer, or status.
- The automatic slot load at filament insertion.
- RS-485 Box (`box485`/`box2base`).
- Slicer G-code.

## Decisions

### Wrap the multi-step home methods

The package wraps `do_home_three_steps` and `do_home_double_steps` on each `box_stepper slotN` instance. Each wrapper takes the profile the vendor passed, applies validated operator settings, and calls the vendor method with the result. `do_move_*_steps` follows automatically, because the home passes it the same values. Plain `do_home` and `do_move` are not wrapped, because they also run the pre-stages, the slot auto-load, and recovery.

The vendor arguments are the baseline, so vendor defaults are never hard-coded and each wrapper call knows its slot. Removing the package removes the wrappers and returns to vendor motion.

Rejected:

- **Vendor key names** (`SAVE_VARIABLE multi_extruder_*`). This works without code, but the vendor planner receives the values unvalidated, it has no per-slot limit, and the values outlive uninstall. The package doesn't write these keys. `TLTG_BOX_MOTION` reports any it finds, because they change the baseline the wrapper receives.
- **Wrapping `box_extras.get_value_by_key` for the Box motion.** This is proven, but it has no slot argument, so per-slot settings can't be applied. It is used only for the extruder retract below, which is global.
- **Patching `box_stepper.so`.** This is the fallback if wrappers stop working on a later firmware. It isn't needed on `.07.01`.
- **Forwarding through generated `[box_stepper slotN]` config.** This didn't change the load.

Wrappers install on any QIDI Box code whose slots have both methods; the `box_stepper.so` build is named in status when it is a known one (01.01.06.01–06.04, 06.05, 07.01), but activation doesn't depend on it. The 06.x builds carry the same methods and `exl_2` lookup, but only 07.01 has been traced live. Each call must match the traced shape (argument count and endstop name, `e_endstop` for load, `b_endstop` for unload) and look plausible (load stage lengths 50–3000 mm with the approach speed below both fast speeds and speeds up to 300 mm/s; unload lengths negative), or it passes through unchanged with a report. The vendor's actual arguments become the published baseline. Until a load or unload supplies them after a restart, status and `TLTG_BOX_MOTION` validation use the values traced on 07.01.

### Settings

Settings are saved variables, so they apply to the next operation without a restart:

| Setting | `TLTG_BOX_MOTION` parameter | Maps to | Vendor value | Bounds |
|---|---|---|---|---|
| `tltg_box_load_fast_length` | `FAST_LENGTH` | stage 1 + stage 2 length | 930 mm | 100–2000 |
| `tltg_box_load_fast_speed_1` | `FAST_SPEED_1` | stage 1 speed | 85 mm/s | 10–150 |
| `tltg_box_load_fast_speed_2` | `FAST_SPEED_2` | stage 2 speed | 65 mm/s | 10–150 |
| `tltg_box_load_approach_speed` | `APPROACH_SPEED` | stage 3 speed | 10 mm/s | 2–40 |
| `tltg_box_load_accel` | `LOAD_ACCEL` | load acceleration | 100 | 20–400 |
| `tltg_box_unload_speed_1`, `_2` | `UNLOAD_SPEED_1`, `_2` | unload stage speeds | 65 / 85 mm/s | 10–150 |
| `tltg_box_unload_accel` | `UNLOAD_ACCEL` | unload acceleration | 100 | 20–400 |
| `tltg_box_unload_extruder_length` | `UNLOAD_EXTRUDER_LENGTH` | second extruder retract (`exl_2`, `G1 E-120 F600`) | 120 mm | 20–300 |

Values are whole numbers, because the vendor passes integers. A setting that is absent or `None` is unset. QIDI's `SAVE_VARIABLE` can't delete a variable, so `TLTG_BOX_MOTION` unsets a value by saving `None` (`PARAM=vendor`, or `RESET=1` for all).

### Extruder retract

An unload starts with two vendor extruder retracts, `G1 E-30 F300` (`exl_1`) and `G1 E-120 F600` (`exl_2`), before the Box-only home. Neither stops on the toolhead switch. On slot 2 the switch cleared 34 mm into the extruder retract, about 4 mm into the second move, so the rest of that move pulls filament that is already free of the gears at the vendor's 10 mm/s. `UNLOAD_EXTRUDER_LENGTH` sets the second retract's length by wrapping `box_extras.get_value_by_key` for `exl_2` only. Its speed and the first retract stay vendor. The lookup carries no slot, and the operator wants one value for every slot, so it is global-only: `SLOT=` refuses it and slot resets leave it alone. It is validated on its own bounds, independent of the unload speed profile, and an invalid saved value falls back to the vendor length with a report.

### Per-slot overrides

Each setting can be overridden for one slot. The override is a saved variable named after the global one with the slot appended, for example `tltg_box_load_fast_speed_slot2`. The bounds are the same. For each slot and each setting, the value used is the slot override if set, then the global setting if set, then the vendor argument. Load and unload profiles are combined and validated per slot. An invalid value, or an infeasible combination for one slot, sends only that slot's affected profile back to vendor motion.

Commands:

- `TLTG_BOX_MOTION SLOT=2 FAST_SPEED_1=100` sets an override. `SLOT` accepts `2` or `slot2`.
- `SLOT=2 FAST_SPEED_1=global` clears an override, so the slot follows the global value again.
- `SLOT=2 RESET=1` clears all of that slot's overrides.
- `RESET=1` without `SLOT` clears the global settings and every slot override.

`PARAM=vendor` is accepted only without `SLOT`, and `PARAM=global` only with it, so a slot can't be pinned to vendor values while globals are set.

Before saving a global change, `TLTG_BOX_MOTION` validates the global profile and the combined profile of every slot with overrides. It refuses the change if a slot that runs today would fail, and names the slot. A slot that already falls back, for example after a hand-saved invalid override, doesn't block global changes. Setting an override validates that slot. Clearing overrides is never refused, because it only returns the slot to the global profile.

### Published status

`tltg_box_feed_motion` implements `get_status()` so Moonraker and Fluidd can subscribe to it, since Fluidd subscribes to every listed printer object. The status is computed from the saved variables. It is cached and recomputed only when `save_variables.allVariables` is a different dict object, because QIDI's `SAVE_VARIABLE` replaces the dict on every save. Setting keys are the lower-case `TLTG_BOX_MOTION` parameter names.

```
{
  "active": bool,
  "status": str,
  "firmware": "01.01.07.01" | "box_stepper.so <hash>" | null,
  "limits": {"fast_length": {"min": 100, "max": 2000, "unit": "mm", "direction": "load"}, ...},
  "vendor": {"fast_length": 930, "fast_speed_1": 85, "fast_speed_2": 65, "approach_speed": 10, "approach_length": 240, "load_accel": 100,
             "unload_speed_1": 65, "unload_speed_2": 85, "unload_accel": 100, "unload_length_1": 350, "unload_length_2": 1150} | null,
  "settings": {"fast_length": int|null, "fast_speed_1": ..., "fast_speed_2": ..., "approach_speed": ..., "load_accel": ..., "unload_speed_1": ..., "unload_speed_2": ..., "unload_accel": ...},
  "problems": [str],
  "vendor_keys": [str],
  "slots": {
    "slot2": {
      "overrides": {"fast_speed_1": 100},
      "load": {"state": "vendor"|"custom"|"error", "error": str|null,
               "fast_length": int, "fast_speed_1": int, "fast_speed_2": int, "approach_speed": int, "approach_length": int, "accel": int},
      "unload": {"state": "vendor"|"custom"|"error", "error": str|null,
                 "speed_1": int, "speed_2": int, "accel": int, "length_1": int, "length_2": int},
    }, ...
  }
}
```

`slots` contains every wrapped `box_stepper` slot. `settings` and `overrides` show an invalid saved value as its repr string so it stays visible and clearable. `problems` covers only the global profile; per-slot failures are in each slot's `error`. A status that fails to build is logged and replaced with a minimal one. Per-slot load and unload values are what the next operation would use, given the vendor values for the recognized firmware. `error` means the profile falls back to vendor motion for the reason in `error`. Inactive firmware publishes `active: false`, `vendor: null`, and empty `slots`.

### Fluidd panel

QIDI's bundled Fluidd gets a "Load/unload motion" section at the end of its existing Box Config view. It's delivered as another guarded step in `installer/runtime/fluidd_box_filaments.py`, with the same all-or-nothing anchors, `sw.js` revision, and uninstall restore as the existing Box patches. The panel reads `printer.tltg_box_feed_motion` from Fluidd's store and edits only through `TLTG_BOX_MOTION`. It posts to `/printer/gcode/script` so it can show a refused command's reason inline. It shows:

- the global settings, with blank fields meaning vendor and the vendor value as placeholder, plus Apply and Reset;
- one row per slot, labelled as the Box card labels slots, with the effective load and unload profile, marked overrides, and the reason when a profile falls back to vendor motion;
- per-slot editing, where a blank field follows the global value, plus Reset slot.

Editing is disabled while printing or paused, or while Klipper's live `webhooks` state isn't ready. QIDI's Box flags and Fluidd's cached server info are not used, because a tab could stay locked after a Box operation or a Klipper restart until reloaded; settings are read at the start of each operation, so editing during one is harmless. When the object is absent or inactive, the section shows the status text and no controls. A panel failure must not break the rest of the Box card.

Stage 2 gets the vendor's stage-2 length, shortened only as far as the fast distance requires, and never shorter than the speed changes from stage 1 to stage 2 and from stage 2 to the approach speed. Stage 1 covers the rest. Stage 3's cap grows by however much the fast distance is shortened, so total reach never falls below the vendor's. Unload lengths stay vendor-defined, because the unload stops on the hub sensor.

Operators set values with `TLTG_BOX_MOTION`, which shows the effective profile for each slot with overrides, and refuses invalid input. `SAVE_VARIABLE` also works, and the wrapper validates whatever it finds. Hand-editing `saved_variables.cfg` while Klipper runs isn't supported, because Klipper rewrites the file on every save.

### Validate the whole profile

Load and unload are separate profiles. Each profile's settings are combined with the vendor arguments for anything unset, then checked:

- each value a whole number within its bounds;
- an approach speed below both fast stage speeds;
- each stage long enough to reach and leave its speed, and stage 2 long enough for the change to the approach speed;
- unload speeds that differ.

If the combined profile fails, that whole profile falls back to the vendor arguments, and the operator is told once which check failed. Keeping only the valid settings was rejected, because a mix of custom and default values can produce a profile the planner rejects mid-print.

### The fast distance is the operator's

`FAST_LENGTH` applies as set, within its bounds. If it reaches the toolhead switch, the filament arrives at fast speed. On slot 2, the switch tripped 1001–1016 mm after the home started, so the vendor's 930 mm fast push leaves roughly 70–85 mm for the approach.

Rejected: recording each slot's distance to the switch on every load, and holding a longer fast distance until three records at the current speeds allowed it, minus a spread-based margin. It was built and live-verified on slot 2, then removed at the operator's request as more safety than wanted.

## Risks / Trade-offs

- [A failed tool change during a print pauses with `QDE_004_006`] → Whole-profile validation, fallback to vendor arguments, and live print checks before release.
- [A fast distance past the toolhead switch pushes filament into the extruder at fast speed] → Operator-owned; the README gives the measured distances.
- [Firmware updates change vendor internals] → Method, argument-shape, and plausibility checks; anything unexpected keeps vendor motion and is reported. Untraced builds may differ in ways those checks can't see.

### Release defaults

Install, update, and idle automatic-update repair save a package profile when none of the motion settings exist in saved variables: fast length 950 mm, fast speeds 120 and 100 mm/s, approach 15 mm/s, unload speeds 115 and 120 mm/s, and extruder retract 50 mm, with both accelerations left to the vendor. If any motion setting exists, including one saved as `None` by a reset, nothing is written, so operator values are never mixed with defaults or reapplied after a reset. It reuses the installer's live saved-variable default path, which accepts whole numbers up to four digits for these values.

## Migration Plan

The release defaults apply on install or update to printers without motion settings. Uninstall removes the package runtime and leaves saved variables in place; nothing reads the `tltg_box_*` keys after uninstall. Rolling back the version behaves the same way.

## Open Questions

- What does the load pre-stage home against, and why did consecutive slot 2 distances climb from 1001 to 1016 mm?
- Is the toolhead-switch endstop armed during the fast stages, so that a fast distance past the switch still stops on it?
