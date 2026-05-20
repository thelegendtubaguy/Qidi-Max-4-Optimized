# QIDI Box stepper state-method reference

## Source

Harness script:

- `tmp/qidi-box-reversing/probe_box_stepper_state_methods.py`

Harness output:

- `tmp/qidi-box-reversing/box_stepper_state_methods_probe.json`

The harness imported `box_stepper.so` on the printer under `/home/qidi/klippy-env/bin/python` and substituted fake Klipper motion/toolhead objects. No real Klipper objects, steppers, heaters, or sensors were used.

## `slot_sync(value, sync_to_extruder=False)`

Harnessed for `slot_num=0` and `slot_num=2` with `value` set to `slot0`, `slot2`, `slot16`, and `slot-1`.

Observed behavior:

| Object slot | `sync_to_extruder` | Lookups | Saved variable |
|---:|---:|---|---|
| `0` | `False` | `box_count`, `hub_load_length`, `hub_load_v`, `hub_load_a` | `slot_sync = 'slot0'` |
| `0` | `True` | `box_count` | `slot_sync = 'slot0'` |
| `2` | `False` | `box_count`, `hub_load_length`, `hub_load_v`, `hub_load_a` | `slot_sync = 'slot2'` |
| `2` | `True` | `box_count` | `slot_sync = 'slot2'` |

The `value` argument did not change the saved slot name in the fake harness. The saved slot came from the `BoxExtruderStepper` object's own slot number.

Default hub-sync values recovered through lookups:

| Key | Default |
|---|---:|
| `hub_load_length` | `18` |
| `hub_load_v` | `40` |
| `hub_load_a` | `40` |

`sync_to_extruder=False` performed the hub-load lookups before the `slot_sync` write. `sync_to_extruder=True` skipped those hub-load lookups in the fake harness.

No `do_move`/`do_home` call was captured from `slot_sync()` in this harness. This may be because the fake toolhead/extruder objects are not complete enough to exercise the real synchronized movement path.

## `init_slot_sync()`

Harnessed with these initial stores:

```text
{}
last_load_slot='slot2', slot_sync='slot2'
last_load_slot='slot2', slot_sync='slot-1'
last_load_slot='slot16', slot_sync='slot16'
```

Observed behavior for `slot_num=0`:

- looked up `box_count`, `hub_load_length`, `hub_load_v`, and `hub_load_a`
- saved `slot_sync = 'slot0'`
- did not preserve an existing `slot_sync = 'slot2'` or `slot_sync = 'slot16'` in the fake harness

This probe does not prove real startup behavior because the fake harness only instantiated one `box_stepper` object at a time and did not model the full included `box_stepper slot0`..`slot3` object graph.

## `sync_unbind_extruder()`

Harnessed with the same initial stores as `init_slot_sync()`.

Observed behavior:

- no saved-variable writes were captured
- no G-code scripts were emitted
- no patched motion primitive calls were captured

This probe does not prove real unbind behavior because real extruder-stepper binding methods were faked.

## `cmd_SLOT_PROMPT_MOVE(gcmd)`

Harnessed parameter sets:

```text
{}
SLOT=slot0
SLOT=slot0 DISTANCE=10 SPEED=5
SLOT=0 DISTANCE=10 SPEED=5
DISTANCE=10 SPEED=5
```

Observed behavior:

- looked up saved variable `slot0` with default `0`
- emitted no G-code script
- captured no patched motion primitive calls
- made no saved-variable writes

The interesting path likely depends on real saved slot state, non-default command parameters not covered here, or a fuller fake object graph.

## `cmd_SLOT_RFID_READ(gcmd)`

Harnessed parameter sets:

```text
SLOT=slot0
SLOT=slot2
SLOT=0
{}
```

Initial fake state:

```text
last_load_slot='slot2'
slot_sync='slot2'
```

Observed behavior:

```text
Code:QDE_004_011; Message:Detected that filament have been loaded, please unload filament first
```

The harness captured the message through `box_extras.print_sensor_state_to_log(...)` and captured no RFID scheduling call.

Runtime captures in `docs/qidi_box/qidi_box_runtime_observations.md` differ: `SLOT_RFID_READ SLOT=slot2`, `INIT_RFID_READ`, and `MULTI_COLOR_READ_RFID SLOT=slot2` were accepted through Moonraker with `{"result": "ok"}` while the live machine was loaded/synced to `slot2`, and no `QDE_004_011` appeared in the captured log tails. The fake harness predicate for `cmd_SLOT_RFID_READ` is therefore not strong enough to claim live behavior.

## `flush_all_filament()`

Observed behavior:

```gcode
G1 E25 F300
```

Additional harness observations:

- looked up `box_count` default `0`
- called patched `disable_stepper()`
- made no saved-variable writes

## `switch_next_slot()`

Initial fake state:

```text
last_load_slot='slot2'
slot_sync='slot2'
slot2=2
```

Observed behavior:

- looked up `auto_reload_detect` default `False`
- emitted no G-code script
- captured no patched motion primitive calls
- made no saved-variable writes

A real auto-reload branch requires fuller saved-variable slot state and likely real print/runout context.
