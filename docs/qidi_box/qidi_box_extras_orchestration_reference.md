# QIDI Box extras orchestration reference

## Source

Harness output:

- `tmp/qidi-box-reversing/box_extras_methods_probe.json`

Compiled symbol priority:

- `docs/qidi_box/qidi_box_compiled_symbol_map.md`

The harness instantiated `box_extras.so` with fake Klipper/G-code/saved-variable objects and captured generated scripts, saved-variable writes, value lookups, and failure points without moving hardware.

## Small macro-equivalent commands

| Method | Harnessed behavior |
|---|---|
| `cmd_CLEAR_FLUSH` | emits `M204 S10000`, `G1 X180 F10000`, `MOVE_TO_TRASH` |
| `cmd_CLEAR_OOZE` | emits `M204 S10000`, repeated X wipes at `F8000`, `F5000`, `F6000`, and inherited feedrate moves |
| `cmd_CLEAR_RUNOUT_NUM` | writes `runout_0` through `runout_15` to `0` |
| `cmd_TRY_RESUME_PRINT` | looks up `extrude_state` default `-2`; fake state emitted `M118 Printer resume failed` |
| `cmd_RESUME_PRINT_1 S=220` | looks up `extrude_state` default `-2`; fake state emitted `M118 Printer resume failed` |
| `cmd_disable_box_heater` | looks up `box_count` default `0`; no fake-harness script emitted |

## `CLEAR_FLUSH` script

```gcode
M204 S10000
G1 X180 F10000
MOVE_TO_TRASH
```

## `CLEAR_OOZE` script

```gcode
M204 S10000
G1 X163 F8000
G1 X145 F5000
G1 X163 F8000
G1 X145 F5000
G1 X175 F6000
G1 X163
G1 X175
G1 X163
G1 X175
G1 X163
```

## `CLEAR_RUNOUT_NUM` writes

`cmd_CLEAR_RUNOUT_NUM` writes these saved variables:

```text
runout_0 = 0
runout_1 = 0
runout_2 = 0
runout_3 = 0
runout_4 = 0
runout_5 = 0
runout_6 = 0
runout_7 = 0
runout_8 = 0
runout_9 = 0
runout_10 = 0
runout_11 = 0
runout_12 = 0
runout_13 = 0
runout_14 = 0
runout_15 = 0
```

## `BOX_PRINT_START` common setup

Every harnessed `cmd_BOX_PRINT_START` case performed these setup actions before branch-specific scripts:

- emits `CLEAR_TOOLCHANGE_STATE`
- writes `load_retry_num = 0`
- writes `retry_step = None`
- writes `runout_0` through `runout_15` to `0`
- writes `extrude_state = -1`
- looks up `enable_box` default `0`
- looks up `value_t0` default `slot16` for the harnessed `EXTRUDER=0` cases

`BOX_PRINT_START` receives a hotend parameter and emitted `M109 S240` in the harnessed cases.

## `BOX_PRINT_START` branch matrix from harness

| `enable_box` | `value_t0` | `last_load_slot` | `slot_sync` | `b_endstop_state` | `e_endstop_state` | Script |
|---:|---|---|---|---:|---:|---|
| `1` | `slot0` | `slot-1` | `slot-1` | `0` | `0` | `MOVE_TO_TRASH`, `M109 S240`, `M400`, `EXTRUDER_UNLOAD SLOT=slot-1` |
| `1` | `slot0` | `slot0` | `slot0` | `1` | `1` | `MOVE_TO_TRASH`, `M109 S240`, `EXTRUDER_LOAD SLOT=slot0` |
| `1` | `slot1` | `slot0` | `slot0` | `1` | `1` | `MOVE_TO_TRASH`, `M109 S240`, `EXTRUDER_LOAD SLOT=slot1` |
| `1` | `slot16` | `slot0` | `slot0` | `1` | `1` | `MOVE_TO_TRASH`, `M109 S240`, `EXTRUDER_LOAD SLOT=slot16` |
| `1` | `slot0` | `slot0` | `slot-1` | `1` | `1` | `MOVE_TO_TRASH`, `M109 S240`, `EXTRUDER_LOAD SLOT=slot0` |

The fake harness did not prove all real `BOX_PRINT_START` branches. It did show that vendor startup always resets retry/runout state and uses `EXTRUDER_LOAD` / `EXTRUDER_UNLOAD` as the downstream movement commands.

## Other command harness notes

| Method | Harness result | Notes |
|---|---|---|
| `cmd_RELOAD_ALL` | failed with missing fake `print_stats` | needs print-state context |
| `cmd_AUTO_RELOAD_FILAMENT` | failed with missing fake `respond_raw` | needs real G-code response context |
| `cmd_RUN_STEPPER STEPPER=slot0 DISTANCE=10 SPEED=5` | `ValueError` converting `slot0` to int | parameter expects a numeric stepper/tool form, not literal `slot0`, in the harnessed path |
| `cmd_CUT_FILAMENT T=1` | looked up `value_t1` default `slot1` and `slot1` default `-1`, then failed due to missing fake `gcode_move` | cutter path needs tool mapping, slot state, and `gcode_move` context |
| `cmd_ENABLE_BOX_DRY BOX=1 TEMP=50 END_TIME=2` | failed with missing fake reactor | dryer path uses reactor/timer context |
| `cmd_DISABLE_BOX_DRY BOX=1` | failed with missing fake reactor | dryer path uses reactor/timer context |
