# QIDI Box stepper branch matrix

## Source

Harness output:

- `tmp/qidi-box-reversing/box_stepper_probe_output.json`
- `tmp/qidi-box-reversing/box_stepper_state_methods_probe.json`

State-method reference:

- `docs/qidi_box/qidi_box_stepper_state_methods_reference.md`

The harness monkey-patched motion primitives in `box_stepper.so` and exercised methods with fake state combinations. It recorded method calls and generated G-code without moving hardware.

State columns:

- `loaded`: fake harness object's local loaded flag.
- `b`: fake `b_endstop` value supplied to the module.
- `e`: fake `e_endstop` value supplied to the module.

Runtime status in `docs/qidi_box/qidi_box_runtime_observations.md` showed the current live machine loaded to `slot2` with `b_endstop_state = 0`, `e_endstop_state = 1`, and `extruder.filament_detected = true`.

## Branch matrix

| Method | Harness state | Motion/script behavior |
|---|---|---|
| `slot_load` | `loaded=false`, `b=0`, `e=0` | `disable_stepper()` only |
| `slot_load` | `loaded=true`, `b=1`, `e=1` | `do_home(..., 3000, 80, 50, False)`, `do_move(-260, 80, 50)`, `disable_stepper()` |
| `slot_load` | `loaded=false`, `b=1`, `e=0` | `do_home(..., 3000, 80, 50, False)`, `do_move(-260, 80, 50)`, `disable_stepper()` |
| `slot_load` | `loaded=false`, `b=0`, `e=1` | `disable_stepper()` only |
| `cmd_SLOT_UNLOAD` | all harnessed states | `do_home(..., -3000, 100, 50, True)`, `disable_stepper()` |
| `cmd_EXTRUDER_LOAD` | `loaded=false`, `b=0`, `e=0` | `disable_stepper()`, `dwell(0.05)`, `sync_print_time()` |
| `cmd_EXTRUDER_LOAD` | `loaded=true`, `b=1`, `e=1` | `do_home(..., 3000, 85, 50, False)`, `disable_stepper()`, `dwell(0.05)`, `sync_print_time()` |
| `cmd_EXTRUDER_LOAD` | `loaded=false`, `b=1`, `e=0` | `do_home(..., 3000, 85, 50, False)`, `disable_stepper()`, `dwell(0.05)`, `sync_print_time()` |
| `cmd_EXTRUDER_LOAD` | `loaded=false`, `b=0`, `e=1` | `disable_stepper()`, `dwell(0.05)`, `sync_print_time()` |
| `cmd_EXTRUDER_UNLOAD` | `loaded=false`, `b=0`, `e=0` | pre-cleanup script, unload shake script, `MOVE_TO_TRASH`, `do_home_double_steps(..., -350, -1150, 65, 85, 100, True)`, `do_home(..., -1500, 65, 50, True)` twice, `disable_stepper()` |
| `cmd_EXTRUDER_UNLOAD` | `loaded=true`, `b=1`, `e=1` | no captured motion calls |
| `cmd_EXTRUDER_UNLOAD` | `loaded=false`, `b=1`, `e=0` | no captured motion calls |
| `cmd_EXTRUDER_UNLOAD` | `loaded=false`, `b=0`, `e=1` | pre-cleanup script, unload shake script, `MOVE_TO_TRASH`, `do_home_double_steps(..., -350, -1150, 65, 85, 100, True)`, `do_home(..., -1500, 65, 50, True)` twice, `disable_stepper()` |
| `cmd_SLOT_PROMPT_MOVE` | all harnessed states | no captured motion calls |

## Inferred predicates from harnessed states

`slot_load()` and `cmd_EXTRUDER_LOAD()` appear gated by the fake `b` state:

- `b=1` allowed the load/home branch in harnessed states.
- `b=0` skipped the load/home branch, even when `e=1`.

`cmd_EXTRUDER_UNLOAD()` appears gated by the fake `b=0` condition in the harness:

- `b=0` ran the unload branch for both `e=0` and `e=1`.
- `b=1` skipped the unload branch for both harnessed `e` values.

`cmd_SLOT_UNLOAD()` did not branch on the harnessed state values; every harnessed state produced the same slot-runout homing call.

`cmd_SLOT_PROMPT_MOVE()` produced no captured calls in this harness; either its interesting work requires a different fake environment, non-default parameters, or live runtime state.

## Recovered movement constants from this matrix

| Path | Distance | Speed | Accel | Endstop polarity flag |
|---|---:|---:|---:|---|
| `slot_load` home | `3000` | `80` | `50` | `False` |
| `slot_load` park | `-260` | `80` | `50` | n/a |
| `SLOT_UNLOAD` home | `-3000` | `100` | `50` | `True` |
| `EXTRUDER_LOAD` home | `3000` | `85` | `50` | `False` |
| `EXTRUDER_UNLOAD` phase 1 | `-350` | `65` | `100` | `True` |
| `EXTRUDER_UNLOAD` phase 2 | `-1150` | `85` | `100` | `True` |
| `EXTRUDER_UNLOAD` recovery home | `-1500` twice | `65` | `50` | `True` |
| `EXTRUDER_LOAD` post-load dwell | `0.05 s` | n/a | n/a | n/a |
