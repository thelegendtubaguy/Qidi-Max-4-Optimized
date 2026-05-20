# QIDI Box speed and timing values

## Evidence sources

- `docs/qidi_box/qidi_box_compiled_module_reference.md` records recovered method signatures, constants, harnessed movement calls, and MCU command formats.
- `docs/qidi_box/box_print_start_notes.md` records `BOX_PRINT_START`, `CLEAR_FLUSH`, `CLEAR_OOZE`, `box_autofeed`, RFID, and adapter findings.
- `tmp/qidi-box-reversing/box_stepper_probe_output.json` records harnessed `box_stepper.so` calls; `docs/qidi_box/qidi_box_stepper_branch_matrix.md` summarizes branch predicates and movement calls.
- `tmp/qidi-box-reversing/box_autofeed_methods_probe.json` records harnessed `box_autofeed.so` MCU payloads; `docs/qidi_box/qidi_box_autofeed_reference.md` summarizes commands and fields.
- `tmp/qidi-box-reversing/box_extras_methods_probe.json` records harnessed `box_extras.so` scripts; `docs/qidi_box/qidi_box_extras_orchestration_reference.md` summarizes cleanup commands and `BOX_PRINT_START` setup.

## Value source categories

| Category | Meaning |
|---|---|
| Stock config | Value is present in stock-visible config or G-code parameters. |
| Compiled module | Value was recovered from compiled module behavior and is not exposed in stock-visible config. |
| Runtime state | Value is an initialized or published state value. |
| Unresolved | Evidence names the behavior but does not recover exact gates or all values. |

## `box_stepper.so` constants

| Constant | Value | Source |
|---|---:|---|
| `DISABLE_DELAY` | `0.05` | compiled module |
| `HOMING_START_DELAY` | `0.001` | compiled module |
| `ENDSTOP_SAMPLE_COUNT` | `4` | compiled module |
| `ENDSTOP_SAMPLE_TIME` | `0.000015` | compiled module |

## `box_stepper.so` movement values

| Behavior | Recovered value | Source |
|---|---:|---|
| `slot_load()` home distance | `3000` | compiled module / harness |
| `slot_load()` home speed | `80` | compiled module / harness |
| `slot_load()` home accel | `50` | compiled module / harness |
| `slot_load()` post-home move | `-260` | compiled module / harness |
| `slot_load()` post-home speed | `80` | compiled module / harness |
| `slot_load()` post-home accel | `50` | compiled module / harness |
| `SLOT_UNLOAD` home distance | `-3000` | compiled module / harness |
| `SLOT_UNLOAD` home speed | `100` | compiled module / harness |
| `SLOT_UNLOAD` home accel | `50` | compiled module / harness |
| `EXTRUDER_LOAD` home distance | `3000` | compiled module / harness |
| `EXTRUDER_LOAD` home speed | `85` | compiled module / harness |
| `EXTRUDER_LOAD` home accel | `50` | compiled module / harness |
| `EXTRUDER_LOAD` dwell | `0.05 s` | compiled module / harness |
| `EXTRUDER_UNLOAD` first sync distance 1 | `-350` | compiled module / harness |
| `EXTRUDER_UNLOAD` first sync distance 2 | `-1150` | compiled module / harness |
| `EXTRUDER_UNLOAD` first sync speed 1 | `65` | compiled module / harness |
| `EXTRUDER_UNLOAD` first sync speed 2 | `85` | compiled module / harness |
| `EXTRUDER_UNLOAD` first sync accel | `100` | compiled module / harness |
| `EXTRUDER_UNLOAD` follow-up home distance | `-1500` twice | compiled module / harness |
| `EXTRUDER_UNLOAD` follow-up home speed | `65` | compiled module / harness |
| `EXTRUDER_UNLOAD` follow-up home accel | `50` | compiled module / harness |
| `slot_sync()` hub-load length | `18` | compiled module / harness |
| `slot_sync()` hub-load speed | `40` | compiled module / harness |
| `slot_sync()` hub-load accel | `40` | compiled module / harness |

## `box_stepper.so` visible toolhead scripts

| Script owner | Recovered G-code |
|---|---|
| `cmd_EXTRUDER_UNLOAD` pre-cleanup | `G1 Y380 F9000`, `G1 X3 F9000`, `G1 X3 Y17 F15000`, `M400` |
| `shake_for_unload_toolhead` | `M204 S10000`, `M83`, multiple `G1 X/Y E-6.5 F30000` and `G1 E-1 F60` moves |
| `shake_for_load_toolhead` | `M204 S10000`, `M83`, multiple `G1 X/Y E6.5 F30000` and `G1 E1 F60` moves |
| `shake_for_enter_extruder` | `M204 S10000`, `M83`, multiple `G1 X/Y E3 F30000` moves |
| `shake_toolhead` | repeated X/Y wiping moves at `F30000` and `F15000` |

## `box_extras.so` timing and motion values

| Behavior | Recovered value | Source |
|---|---|---|
| `BOX_PRINT_START` hotend wait | `M109 S<hotendtemp>` | `HOTENDTEMP` G-code parameter |
| `BOX_PRINT_START` load branch | `MOVE_TO_TRASH`, `M109 S<temp>`, `EXTRUDER_LOAD SLOT=<target>` | harnessed branch |
| `BOX_PRINT_START` unload branch | `MOVE_TO_TRASH`, `M109 S<temp>`, `M400`, `EXTRUDER_UNLOAD SLOT=<unload_slot>` | harnessed branch |
| `CLEAR_FLUSH` acceleration | `M204 S10000` | harnessed script |
| `CLEAR_FLUSH` move | `G1 X180 F10000` | harnessed script |
| `CLEAR_FLUSH` final command | `MOVE_TO_TRASH` | harnessed script |
| `CLEAR_OOZE` acceleration | `M204 S10000` | harnessed script |
| `CLEAR_OOZE` wipe feedrates | `F8000`, `F5000`, `F6000` | harnessed script |
| `cmd_CLEAR_RUNOUT_NUM` | writes `runout_0`..`runout_15 = 0` | harnessed state writes |
| `cmd_CUT_FILAMENT` strings | `CUT_FILAMENT_1`, `MOVE_TO_TRASH`, `M83`, `G1 E-60 F300` | strings / harness fragments |
| `TRY_RESUME_PRINT` failure path | `M118 Printer resume failed` | harnessed branch |

## `box_autofeed.so` values

| Behavior | Recovered value | Source |
|---|---:|---|
| `limit_pin` | `^!mcu_box1:PB0` | stock config |
| `debounce_us` | default `200000.0` | compiled module / harness |
| `limit_polarity` | default `0` | compiled module / harness |
| `default_ticks` | default `8400` | compiled module / harness |
| `v_feed` | default `2000`, stock config `100` | compiled module + stock config |
| `lmax` | default `10000`, stock config `120` | compiled module + stock config |
| `dir` | default `1`, stock config `0` | compiled module + stock config |
| `a_feed` | default `0.0` | compiled module / harness |
| `mcb_auto_start` velocity conversion | `v / step_dist` | compiled module / harness |
| `mcb_auto_start` acceleration conversion | `a / step_dist` | compiled module / harness |
| `mcb_auto_start` length conversion | `lmax / step_dist` | compiled module / harness |
| `enable` pin encoding | parsed pin index, e.g. `PC15 -> 47` | compiled module / harness |
| `invert` encoding | `!` prefix -> `1` | compiled module / harness |

## `box_rfid.so` timing and retry values

| Behavior | Recovered value | Source |
|---|---:|---|
| `max_read_time` | `30.0 s` | compiled module / harness |
| `rfid_read_attempts` initial value | `0` | runtime state |
| `rfid_read_start_time` initial value | `0` | runtime state |
| `get_message_count` initial value | `1` | runtime state |
| `query_fm17550` restart behavior | `rest_ticks=0`, `on_restart=True` | compiled module / harness |
| `fm17550_read_card_cb` payload | `[oid]` | compiled module / harness |
| RFID response | `status=%c data=%*s` | compiled module / harness |

RFID details are summarized in `docs/qidi_box/qidi_box_rfid_reference.md`.
