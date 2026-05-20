# QIDI Box vendor behavior summary

## Active stack

The current config loads the vendor QIDI Box stack through `config/printer.cfg`:

```ini
[include box.cfg]
[multi_color_controller]
```

`[include box.cfg]` creates the QIDI Box MCU, four `box_stepper` slots, heater, temperature sensors, RFID readers, `box_autofeed`, `box_extras`, and stock wrapper macros. `[multi_color_controller]` registers the public multi-color commands and publishes the Moonraker `multi_color_controller` status object.

## Motion ownership

`box_stepper.so` owns stock `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, `SLOT_UNLOAD`, slot preload, slot sync, homing, and stepper disable timing.

`config/box.cfg` exposes QIDI Box hardware pins, `rotation_distance=13.6`, `microsteps=16`, `step_pulse_duration=0.000000100`, heater/fan/RFID pins, and `box_autofeed` helper values. It does not expose the core load/unload phase distances, speeds, accelerations, or dwell values.

Harnessed stock movement values:

| Path | Distance | Speed | Accel | Notes |
|---|---:|---:|---:|---|
| slot preload home | `3000` | `80` | `50` | `box_stepper.slot_load()` |
| slot preload park | `-260` | `80` | `50` | `box_stepper.slot_load()` |
| extruder load home | `3000` | `85` | `50` | `EXTRUDER_LOAD` |
| extruder load dwell | `0.05 s` | n/a | n/a | `EXTRUDER_LOAD` |
| unload phase 1 | `-350` | `65` | `100` | `EXTRUDER_UNLOAD` |
| unload phase 2 | `-1150` | `85` | `100` | `EXTRUDER_UNLOAD` |
| unload recovery | `-1500` repeated twice | `65` | `50` | `EXTRUDER_UNLOAD` |
| slot eject | `-3000` | `100` | `50` | `SLOT_UNLOAD` |
| slot sync hub move defaults | `18` | `40` | `40` | fake-harness `slot_sync(..., sync_to_extruder=False)` lookups |

## Start-print behavior

`box_extras.so` owns stock `BOX_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temp>` orchestration.

Harnessed `BOX_PRINT_START` setup writes:

```text
load_retry_num = 0
retry_step = None
runout_0..runout_15 = 0
extrude_state = -1
```

Harnessed `BOX_PRINT_START` branches call downstream stock motion commands such as `EXTRUDER_LOAD` and `EXTRUDER_UNLOAD`. Exact live branch predicates for same-slot, different-slot, synced, unsynced, cut-before-unload, and `slot16` direct-feed cases remain unresolved.

## Runtime state captured on this machine

Latest captured runtime state showed:

```text
enable_box = 1
box_count = 1
last_load_slot = slot2
slot_sync = slot2
extrude_state = 2
slot2 = 2
filament_slot2 = 18
color_slot2 = 2
vendor_slot2 = 0
```

`extrude_state=2`, `slot2=2`, and `multi_color_controller` status indicate `2 = IN_EXTRUDER`.

The loaded/synced physical slot was `slot2`. `box_stepper slot2.runout_button=0` while empty visible slots reported `1`, indicating inverted stock pre-gate/runout status polarity.

## RFID

`box_rfid.so` owns FM17550 SPI RFID reads.

Recovered command formats:

```text
query_fm17550 oid=<oid> rest_ticks=0
config_fm17550 oid=<oid> spi_oid=<spi_oid>
fm17550_read_card_cb oid=%c
fm17550_read_card_return oid=%c status=%c data=%*s
```

Idle runtime captures for these commands returned `ok` and did not change saved variables:

```gcode
SLOT_RFID_READ SLOT=slot2
INIT_RFID_READ
MULTI_COLOR_READ_RFID SLOT=slot2
```

Existing `slot2` metadata was not cleared by no-visible-result RFID reads. Valid QIDI RFID tag payload bytes remain unresolved.

## Autofeed and anti-wrap

`box_autofeed.so` owns `mcb_*` MCU helper commands for feed assist and anti-wrap behavior.

Recovered stock-visible helper config:

```text
limit_pin = ^!mcu_box1:PB0
v_feed = 100
lmax = 120
dir = 0
a_feed = 0.0
debounce_us = 200000
default_ticks = 8400
```

Idle runtime captures for these commands returned `ok` and did not change saved variables:

```gcode
MCB_CONFIG SLOT=slot2
MCB_QUERY
SET_LIMIT_A STATE=0
SET_LIMIT_A STATE=1
SET_LIMIT_A STATE=0
```

`box_autofeed` published `{}` in Moonraker status. `MCB_STATE`, `MCB_DONE`, and `MCB_ERROR` payloads remain unresolved because `MCB_AUTO_START` or a physical anti-wrap event is required.

## Status schema

`multi_color_controller.so` is the local/remote command facade and Moonraker status publisher. On this machine it runs in `local` mode and dispatches back to stock G-code.

Captured `multi_color_controller` status shape includes:

```text
system
hardware
slots
extruder
operation
print
rfid
drying
sensors
config
config_summary
```

`docs/qidi_box/qidi_box_status_schema_reference.md` records the captured field names and representative values.

## Remaining vendor-behavior gaps

| Gap | Required evidence |
|---|---|
| live `BOX_PRINT_START` branch predicates | controlled start-branch captures |
| live `EXTRUDER_LOAD` retry/endstop behavior | operator-preflighted load capture |
| live `EXTRUDER_UNLOAD` retry/endstop behavior | operator-preflighted unload capture |
| live `SLOT_UNLOAD` behavior | operator-preflighted eject capture |
| RFID valid tag payload | known tagged QIDI spool aligned to reader |
| autofeed callback payloads | `MCB_AUTO_START` or real anti-wrap event |
