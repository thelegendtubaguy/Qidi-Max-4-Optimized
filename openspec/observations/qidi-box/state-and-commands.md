# QIDI Box state and command observations

Evidence qualifiers are defined in `openspec/observations/README.md`. Runtime captures apply to QIDI Max 4 firmware `01.01.06.04`; `01.01.06.05` findings are explicitly config-confirmed, harness-recovered, or static-recovered.

## Saved-variable model

| Variable family | Meaning |
|---|---|
| `enable_box`, `box_count` | Vendor Box enablement and detected count. |
| `value_t0` through `value_t15` | Logical tool-to-slot mapping. Missing mappings default to `slot16` in recovered `BOX_PRINT_START`. |
| `slot0` through `slot15` | Physical-slot `BoxState` values. |
| `last_load_slot` | Last loaded slot according to vendor state. |
| `slot_sync` | Slot currently trusted/bound to the extruder. |
| `extrude_state` | Aggregate loaded state. |
| `filament_slotN`, `color_slotN`, `vendor_slotN` | IDs resolved through `officiall_filas_list.cfg`; slot metadata extends through `slot16`. |
| `runout_0` through `runout_15` | Per-slot runout counters. |
| `load_retry_num`, `retry_step` | Vendor retry state. |
| `retained_slot`, `retained_tool`, `retained_tool_ready`, `retained_filament_id`, `retained_vendor_id` | Repository-managed between-print reuse state. |
| `is_tool_change`, `was_interrupted` | Vendor operation context. |

`slot16` is direct-feed/external-spool metadata and is not a physical slot state. `slot-1` is the observed unsynced/no-active-target sentinel.

## State values

| State | Value |
|---|---:|
| `ERROR` | `-1` |
| `UNKNOWN` | `-2` |
| `PENDING` | `-3` |
| `EMPTY` | `0` |
| `LOADED` | `1` |
| `IN_EXTRUDER` | `2` |
| `IN_FEEDER` | `3` |

Runtime alignment on the one-Box capture:

```text
last_load_slot = slot2
slot_sync = slot2
extrude_state = 2
slot2 = 2
```

`multi_color_controller.slots.states.slot2=2`, `extruder.loaded=true`, `extruder.filament_detected=true`, and `BoxState.IN_EXTRUDER=2` confirm the loaded-to-extruder interpretation.

Loaded `slot2` reported `runout_button=0`; empty slots reported `1`. Box slot runout/pre-gate polarity is inverted relative to an intuitive `filament present = 1` assumption.

## Moonraker status schema

Visible object names include:

```text
box_extras
multi_color_controller
save_variables
box_stepper slotN
heater_generic heater_boxN
temperature_sensor heater_temp_a_boxN
temperature_sensor heater_temp_b_boxN
mcu mcu_boxN
```

`box_autofeed` returned `{}` when queried but was absent from object lists. Generated `box_rfid card_reader_N` objects were not Moonraker-visible in captures.

### `box_extras`

```text
box_button_state
b_endstop_state
e_endstop_state
box_operate_state
box_drying_state.boxN.{dry_state,end_time}
is_tool_change
```

### `box_stepper slotN`

```text
runout_button
rfid_state
```

### `multi_color_controller`

| Section | Captured shape |
|---|---|
| `system` | `ready`, `mode` |
| `hardware` | `box_count`, `connected` |
| `slots` | `states.slot0..slot15`, `materials.slot0..slot16`, `last_loaded`; each material resolves `filament.{filament,min_temp,max_temp,box_min_temp,box_max_temp,type}`, `color`, and `vendor`. |
| `extruder` | `loaded`, hotend `target`, `filament_detected` |
| `operation` | `current`, `progress`, `error`, button/operate state, `steps`, `is_waiting_user` |
| `print` | `printing`, `current_tool`, `next_tool` |
| `rfid` | `reading`, `results` |
| `drying` | `boxN.dry_state`, `end_time` |
| `sensors` | `b_endstop`, `e_endstop`, `runout_sensors.slotN`, `pressure_sensor` |
| `config` | Saved Box, mapping, metadata, runout, retry, retained-filament, and interruption variables. |
| `config_summary` | `enable_box`, `auto_reload_detect`, `auto_read_rfid`, `auto_init_detect`, `slot_sync`, `retry_step`, `load_retry_num` |

The `.07.01` `box.b_endstop_state` polarity and its discrepancy with `/printer/query_endstops/status` are documented in [hardware and protocol observations](hardware-and-protocols.md#slot-hardware).

`save_variables` should be consumed through its `variables` dictionary; duplicated top-level fields are a Moonraker representation detail.

`heater_generic heater_boxN.target` is authoritative for heater target. Captures showed `target=45` while both vendor drying-state surfaces reported `dry_state=0`.

Stock Fluidd cannot set a nonzero Box heater target on `01.01.07.01`:

- **Runtime-confirmed:** `configfile.settings` omits `heater_generic heater_boxN` because `box_config.py` builds generated sections with a private access-tracking map. Fluidd's target validation then compares against undefined minimum and maximum values, so only `0` is submitted. Sharing Klipper's tracking map for the generated heater published `min_temp -100`, `max_temp 100`, and `target_max_temp 90` without configuration warnings.
- **Runtime-confirmed:** QIDI's `SET_HEATER_TEMPERATURE` enforces `target_min_temp` and `target_max_temp` only for `heater_generic chamber`. `SET_HEATER_TEMPERATURE HEATER=heater_box2 TARGET=70` was accepted with `target_max_temp 65`; Box heater targets are bounded only by `max_temp`.
- **Config-confirmed:** Fluidd's `getMinMaxTempOfBox` limits Box `N` to the lowest `box_max_temp` among loaded filaments, but selects slots with `u/4===N-1`, so only the first slot of each Box is considered. `officiall_filas_list.cfg` and the `01.01.07.01` filament database give `box_max_temp` `0` for PLA, TPU, PEBA, and some other filaments, which Fluidd reports as `Max 0`.

The observed `mcu_box1` reported firmware `02.03.01.21`, MCU `stm32f401xc`, clock `84000000`, and both-edge stepping enabled.

## `BOX_PRINT_START`

Stock start dispatch is:

```gcode
BOX_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temperature>
```

Every harnessed call first:

1. emits `CLEAR_TOOLCHANGE_STATE`;
2. writes `load_retry_num=0`;
3. writes `retry_step=None`;
4. clears `runout_0` through `runout_15`;
5. writes `extrude_state=-1`;
6. reads `enable_box` and `value_t<tool>`, defaulting a missing mapping to `slot16`.

Harnessed branch families used `MOVE_TO_TRASH`, `M109`, `M400` where required, and downstream `EXTRUDER_LOAD` / `EXTRUDER_UNLOAD`. The fake harness emitted an unload from `slot-1` in one unsynced case; exact live predicates for same-slot, changed-slot, cut-before-unload, unsynced, and `slot16` handling remain unresolved.

When `enable_box=0`, recovered setup runs and the command returns without feeder motion. Repository code must still distinguish `enable_box` from object existence.

## Firmware `01.01.06.05` compiled-module differences

- **Harness-recovered:** `BoxExtras.detect_filament_loaded()` adds `M400` plus escalating `G1 E10 F600` and `G1 E20 F900` retries. Worst-case probing increases from `75 mm` on `.04` to `140 mm` on `.05`; physical sensor response and failure outcomes were not exercised.
- **Harness-recovered:** `BoxExtruderStepper.cmd_EXTRUDER_LOAD()` adds state paths named `diff_mv`, `box_autofeed`, `retry_success`, and `box_autofeed.limit_a_state`, with waste-area recovery extrusions of `30 mm` or `50 mm`. Exact retry thresholds and branch order remain unresolved.
- **Harness-recovered:** `BoxExtruderStepper.cmd_EXTRUDER_UNLOAD()` resolves `printer.lookup_object("virtual_sdcard", None)` into `v_sd` while printing. Downstream effects of the resolved object remain unresolved.
- **Harness-recovered:** `BoxExtruderStepper.switch_next_slot()` scans `value_t0` through `value_t15` rather than using `get_key_by_value(...)` for the next logical tool mapping. Physical auto-reload movement remains unresolved.
- **Harness-recovered:** `TaskQueueManager._decide_flow_id()` selects flow `6` (`EXT_HEAT`, `EXT_LOAD`, `EXT_BITE`, `EXT_WIPE`) for external-spool `LOAD` with slot `16`, filament present, and empty `last_load_slot`; `.04` selected flow `0` for the same controlled input.
- **Static-recovered:** public classes, methods, signatures, defaults, and recovered error-code sets are unchanged. `box_autofeed.so`, `box_detect.so`, and `box_rfid.so` have no confirmed source-level functional change beyond rebuilt binaries.

## Firmware `01.01.07.01` Box stack

- **Config-confirmed:** stock `T0`–`T15` macros call `T_MANAGER T=<n>`; stock `RESUME` always calls `TRY_RESUME_PRINT`; `INIT_RFID_READ` runs at startup without a Box check; stock runout auto-reload checks only `enable_box`.
- **Runtime-confirmed (two USB Boxes, 2026-10-19):** the update regenerated `box.cfg` with `[box_config boxN]`, `[box_extras]`, `[box_autofeed]`, and `[mcu mcu_boxN]` only. `T{n}`, `UNLOAD_T{n}`, and `UNLOAD_FILAMENT` macros are no longer generated.
- **Runtime-confirmed:** `gcode.commands` does not contain `CUT_FILAMENT` or `UNLOAD_T{n}`. It contains `T_MANAGER`, `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, `SLOT_UNLOAD`, compiled `UNLOAD_FILAMENT`, `UNLOAD_FILAMENT_CONTROL`, `LOAD_FILAMENT_CONTROL`, `EJECT_FILAMENT_CONTROL`, `TRY_RESUME_PRINT`, `INIT_RFID_READ`, `CLEAR_FLUSH`, `CLEAR_OOZE`, `BOX_PRINT_START`, `TOOL_CHANGE_START`, `TOOL_CHANGE_END`, `AUTO_RELOAD_FILAMENT`, `DISABLE_BOX_HEATER`, `FLOW_RETRY`, `FLOW_STOP`, `INTERNAL_BOX_UNLOAD`, and `QUERY_CURRENT_BOX_CHANNEL_FILAMENT`.
- **Runtime-confirmed:** `multi_color_controller` status adds top-level `box_count`, `enable_box`, `auto_reload_detect`, `load_retry_num`, `task` (`flow_id`, `current_queue`, `current_step`, `is_paused`), `box` (`identity`, `box_count`, `loaded_slot`, `last_load_slot`, `is_tool_change`, buffer fields, and flattened per-Box fields), `extra` (external spool), and `operation.active_slot`. USB Boxes report `box.identity` `box_v1`. `box485` status reports `box_count` and `boxes`; `box2base` publishes no status.
- **Runtime-confirmed (2026-10-26):** `box_extras` status no longer publishes `b_endstop_state`; it publishes `buffer` (`hall0_adc`, `hall1_adc`, `photo0`, `photo1`, `version`), `last_load_slot`, `loaded_slot`, `is_tool_change`, and per-Box `boxes` entries. The hub filament sensor is `multi_color_controller.box.b_endstop_state`. An idle controller reports `task` as `flow_id: None`, `current_queue: []`, `current_step: ''`.
- **Runtime-confirmed (2026-10-26):** klippy logs `检查到！！错误，恢复默认状态！！` ("error detected, restoring default state") after a G-code command error and repeatedly while Klipper connects at startup; the observed effect was a print sub-status reset.
- **Static-recovered:** `box_extras.so` no longer has `CUT_FILAMENT`, `INIT_RFID_READ`, `RETRY`, `DISABLE_BOX_DRY`, `TRY_RESUME_PRINT`, `AUTO_RELOAD_FILAMENT`, `BOX_PRINT_START`, or `TOOL_CHANGE_START`/`END` handlers. `multi_color_controller.so` implements `BoxAdapterV1` (USB), `BoxAdapterV2` (RS-485), and `ExternalAdapter`, each with cut, unload, load, wipe, eject, print-start, tool-change, try-resume, and auto-reload operations driven by `FlowTask`. Its embedded scripts call stock `CUT_FILAMENT_1`, `MOVE_TO_TRASH`, `WIPE_NOZZLE_DROP`, and `DROP_TRASH`.
- **Runtime-confirmed (two USB Boxes, 2026-10-26):** `gcode/help` lists `LOAD_FILAMENT_CONTROL`, `UNLOAD_FILAMENT_CONTROL`, `EJECT_FILAMENT_CONTROL`, `READ_RFID`, and `UPDATE_FILAMENT_INFORMATION`, and omits `E_BOX`, `E_LOAD`, `E_UNLOAD`, and `RFID_READ`, which stock Fluidd's Box card sends. `box_extras` status carries `auto_refill`, `boxes`, `buffer`, `is_tool_change`, `last_load_slot`, and `loaded_slot`, but no `b_endstop_state`, `e_endstop_state`, or `box_button_state`; `multi_color_controller.box.b_endstop_state` is published. `box_extras.boxes[N].filament_info` mirrors the resolved per-slot filament fields.
- **Static-recovered:** qidiclient sends `EJECT_FILAMENT_CONTROL SLOT=`, `LOAD_FILAMENT_CONTROL SLOT=`, `UNLOAD_FILAMENT_CONTROL SLOT=`, and `READ_RFID SLOT=` with a numeric slot.
- **Runtime-confirmed:** QIDI's Fluidd `sw.js` precaches `assets/index-DlFvHGAh.js` with revision `null`, so a browser whose service worker already cached the bundle keeps serving it after the file changes on disk until `sw.js` changes.
- **Unresolved:** whether `UPDATE_FILAMENT_INFORMATION` has effects beyond the `SAVE_VARIABLE` slot updates, for example on RS-485 Boxes.
- **Static-recovered:** QIDI Studio `v2.07.02.73` still emits `CUT_FILAMENT T=`, `MOVE_TO_TRASH`, `UNLOAD_T[current_extruder]`, and `T[next_extruder]` for filament change and `UNLOAD_FILAMENT T=` at print end. On `.07.01` the first and third are ignored as unknown commands.
- **Runtime-confirmed (2026-10-19, stock `.07.01` config, QIDI Studio stock filament-change G-code, two USB Boxes):** during a print, `T[n]` → `T_MANAGER` cut once (the extruder stepper was disabled at the start of the change, matching `CUT_FILAMENT_1`), unloaded the previous filament, and attempted the new load; the ignored `CUT_FILAMENT T=` and `UNLOAD_T[n]` lines caused no second cut. A load that never reached the toolhead sensor reported `QDE_004_006` (`Extruder loading failure.`) with `b_endstop_state = 1` and `e_endstop_state = 0` and paused the print; the same code paused print-start loading. The operator attributed both failures to filament quality. Operator `RESUME` retried the load and printing continued.
- **Runtime-confirmed (same print):** each of five further tool changes showed exactly one extruder-stepper disable, consistent with one flow cut per change. Stock end G-code `UNLOAD_FILAMENT T=` cut once (extruder disable one second after `print_end`), unloaded to the Box, and the print reached `ready` about 65 seconds after `print_end`; afterward `loaded_slot` and `last_load_slot` were `slot16`, the toolhead sensor reported no filament, and the extruder target was `0`. Whether the vendor unload wipes the nozzle was not observed.
- **Runtime-confirmed (2026-10-19, optimized `26.10.19.1` on `.07.01`, job G-code containing `OPTIMIZED_CUT_FILAMENT TOOLCHANGE=1` at each of four tool changes):** at the first tool change one extruder-stepper disable was logged and the operator observed exactly one cut, made by the vendor flow (flow `13`, queue `BOX_CUT`, `BOX_UNLOAD`, `BOX_LOAD`) through the optimized `CUT_FILAMENT_1`; the optimized cut was skipped as intended. The job then paused on `QDE_004_006` while loading and was cancelled; the operator attributed the failure to causes outside the cut path.
- **Unresolved:** whether vendor `UNLOAD_FILAMENT` wipes the nozzle or changes the hotend target itself; whether `TRY_RESUME_PRINT` refuses an external-spool resume with the toolhead sensor empty (`ExternalAdapter` contains `No filament detected. Please insert filament and try again.`); and RS-485 `BoxAdapterV2` status and behavior on hardware.

## Task queue

**Harness-recovered (`.07.01`, `TaskQueueManager.FLOW_MAP` read from the imported module, 2026-10-28):**

| Flow | Ordered steps |
|---:|---|
| `0` | none / idle |
| `1` | `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE` |
| `2` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_LOAD`, `BOX_WIPE` |
| `3` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD` |
| `4` | `BOX_EJECT` |
| `5` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_EJECT` |
| `6` | `EXT_HEAT`, `EXT_BITE`, `EXT_LOAD`, `EXT_WIPE` |
| `7` | `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD` |
| `8` | `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD`, `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE` |
| `9` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `EXT_HEAT`, `EXT_BITE`, `EXT_LOAD`, `EXT_WIPE` |
| `10` | `BOX_HEAT`, `BOX_UNLOAD`, `BOX_LOAD`, `BOX_WIPE` |
| `11` | `BOX_HEAT`, `BOX_UNLOAD`, `BOX_EJECT` |
| `12` | `BOX_HEAT`, `BOX_UNLOAD`, `EXT_HEAT`, `EXT_BITE`, `EXT_LOAD`, `EXT_WIPE` |
| `13` | `BOX_CUT`, `BOX_UNLOAD`, `BOX_LOAD` |

The `.04` harness recorded flows `0`–`9` only, with `EXT_LOAD` before `EXT_BITE` and a `WAIT_USER` step between the extruder and Box halves of flows `8` and `9`.

Firmware `.04` fake-manager `_decide_flow_id()` results:

- uppercase `LOAD`: flow `1` without filament; flow `2` with filament when `last_load_slot != slot16`;
- uppercase `UNLOAD`: flow `3` with filament when `last_load_slot != slot16`; flow `7` when `last_load_slot=slot16`;
- uppercase `EJECT`: flow `4` in all harnessed states;
- lowercase and adapter-like action strings returned flow `0` in direct harnessing;
- `LOAD` with filament and `last_load_slot=slot16` raised `TypeError`; `last_load_slot=None` raised `AttributeError`.

`start_flow()` sets the flow ID, copies steps, initializes operation index `0`, and clears waiting/active-step state. Default-state `tick()` completed box-side flows `1`, `2`, `3`, and `5` but not extruder/mixed flows `6` through `9`; this is harness behavior, not live operation proof.

### `.07.01` flow pause, stop, and retry

- **Harness-recovered (2026-10-31, `TaskQueueManager` and `MultiColorController` with fake objects):** a step that returns `False` responds `Step <step> failed. Pausing flow.` and leaves `current_task` with `is_paused` true and `current_step` the failed step; the G-code command that started the flow returns then. `multi_color_controller.operation.active_slot` stays the flow's target slot while paused. Starting another flow while one is paused replaces it without a stop.
- **Harness-recovered:** `cmd_FLOW_STOP` and the `multi_color_controller/flow_stop` endpoint call `TaskQueueManager.stop()`, which clears `current_task` (status `flow_id` `None`), sends `M104 S0` through its own `gcode` attribute with `run_script()` when `current_flow_temp` is set, whatever the print state, then responds `Flow stop requested.` It runs no completion script. With no flow it does nothing and says nothing.
- **Config-confirmed (QIDI `klippy/gcode.py`):** `run_script()` takes the G-code mutex, which a command sent through Moonraker's `gcode/script` already holds, while `run_script_from_command()` does not. `FLOW_STOP` sent as G-code therefore waits on its own lock after clearing the flow, before `Flow stop requested.`; the harness reproduces this with a lock that refuses re-entry.
- **Harness-recovered:** `cmd_FLOW_RETRY` sends `M109 S<current_flow_temp>` with `run_script_from_command()`, or nothing without a flow temperature, then reruns the paused step; with no paused flow it responds `No failed step to retry.` It does not take the G-code lock again.
- **Harness-recovered (2026-10-31):** a step that raises instead of returning `False` propagates out of `start_flow()` and `retry()` to the command that ran the flow and leaves `current_task` with `current_step` the failed step but `is_paused` false, so `cmd_FLOW_RETRY` has no failed step to retry. Setting the task's `is_paused` to true then lets `retry()` rerun the step and finish the flow with the same end state as after a step that returned `False`.
- **Runtime-confirmed (test printer `klippy.log`, 2026-10-31 08:42 UTC, `.07.01`, two USB Boxes):** during a `BOX_LOAD` whose approach missed the toolhead sensor, `Error during homing e_endstop: Communication timeout during homing` ended `LOAD_FILAMENT_CONTROL` with an error, followed by `检查到！！错误，恢复默认状态！！` ("error detected, restoring default state"). The task stayed flow `1` at `BOX_LOAD` with `is_paused` false and the hotend target 240 °C; MCU statistics showed no retransmits and no Box disconnect. `FLOW_STOP` cleared it.
- **Runtime-confirmed (same session):** when the `BOX_LOAD` approach misses the toolhead sensor, the step runs about a minute of toolhead moves with small extruder moves before `QDE_004_006`; with a 140 mm push past the hub, about 640 mm had to be retracted to clear the hub afterwards. `FLOW_RETRY` of that step first pulled the filament back until the hub sensor cleared (`loaded_slot` `slot16`), then fed it to the hub again and ran the load.
- **Config-confirmed (QIDI `klippy/extras/filament_switch_sensor.py`) and runtime-confirmed (test printer, 2026-10-31):** the toolhead sensor's `runout_helper.filament_present` starts as `False`, but `note_filament_present()` stores the button callback's raw state, so after the sensor first changes it holds `0` or `1`. Its status `filament_detected` is `bool()` of it. A check that compares it with `False` by identity stopped matching once the sensor had changed since Klipper started.
- **Static-recovered:** `box_extras.so` names no `stop` method; its only `stop` strings are log messages. No other vendor G-code command reached `TaskQueueManager.stop()` in the harness.
- **Runtime-confirmed (operator `klippy.log` and `moonraker.log`, 2026-10-31, `.07.01`, two USB Boxes, package `26.10.29.1`):** after `Step BOX_LOAD failed. Pausing flow.` (06:56:21 UTC) the task showed flow `1`, `current_step` `BOX_LOAD`, `is_paused` true, with the nozzle at 240 °C. `FLOW_STOP` at 07:00:48 cleared the task to `flow_id` `None`, but its `gcode/script` request never returned, `Flow stop requested.` was never logged, the nozzle stayed at 240 °C, and toolhead print time stopped advancing. `UNLOAD_FILAMENT_CONTROL SLOT=1` (07:00:57), `EJECT_FILAMENT_CONTROL SLOT=1` (07:01:17), and fifteen `TLTG_BOX_SLOT_JOG` requests were each logged by Moonraker as `Request 'gcode/script' pending` 60 s after they were sent, with nothing in `klippy.log`, so none of them ran. Restarting `klipper.service` with the heater on left the THR board shut down (`Can not update MCU 'THR' config as it is shutdown`) until `FIRMWARE_RESTART`.

### `.07.01` load and unload with filament at the hub

- **Harness-recovered (2026-10-30, USB `BoxAdapterV1`, fake objects):** `flow_decision_func(action, slot)` reads the toolhead `filament_switch_sensor`, `box1base.b_endstop_state` (hub, `0` = filament), and saved `last_load_slot` (default `slot16`). For slot 2:

  | Action | Toolhead | Hub | `last_load_slot` | Flow |
  |---|---|---|---|---:|
  | `LOAD` | empty | filament | any | `10` |
  | `LOAD` | empty | clear | any | `1` |
  | `LOAD` | filament | any | `slot16` or missing | `8` |
  | `LOAD` | filament | filament | another slot | `2` |
  | `LOAD` | filament | clear | another slot | `-1` |
  | `UNLOAD` | filament | any | `slot16` or missing | `7` |
  | `UNLOAD` | filament | filament | another slot | `3` |
  | `UNLOAD` | filament | clear | another slot | `-1` |
  | `UNLOAD` | empty | any | any | `0` |

- **Harness-recovered:** `BoxAdapterV1.unload_filament()` sends `MOVE_TO_TRASH`, then returns `True` with nothing else when the hub is clear. With filament at the hub and `last_load_slot` `slot16` or missing, it responds `无法识别到已进料耗材` ("can't identify the loaded filament") and returns `False`, so the flow pauses with `Step BOX_UNLOAD failed. Pausing flow.` Otherwise it sends `M109 S<current_flow_temp>` and calls `extruder_unload_single_func()` on `box_stepper <target_unload_slot>`, or on `last_load_slot` when `target_unload_slot` is empty, as it is in flow `10`.
- **Harness-recovered:** `BoxAdapterV1.init_steps_method(task_queue_manager)` sets `box1base` to the `box_extras` object and stores the adapter's step functions in `task_queue_manager.method_map`, which `start_flow()` runs; replacing an adapter attribute afterward does not change a flow. `cmd_FLOW_RETRY` passes `RETRY` (default `0`) as `can_next`. `retry()` sends `M109 S<current_flow_temp>`, then reruns the paused step, or skips it when `can_next` is set.
- **Harness-recovered:** `BoxExtruderStepper.get_status()` publishes `r_endstop_state` as `runout_button`. `BoxExtras.update_b_endstop()` drives the hub LED from `b_endstop_state`. `BoxExtras.cmd_INIT_BOX_STATE` clears a saved `slot_sync` when the hub is clear and resynchronizes it otherwise; it does not change `last_load_slot`.
- **Runtime-confirmed (operator `klippy.log`, 2026-10-30, package `26.10.28.3`, one USB Box):** with the Box heater off and no G-code running, slot 1 (1B) moved at 18:00:59, consistent with the automatic slot load on insertion. 12 s later Klipper logged `Got EOF when reading from device`, then `Lost communication with MCU 'mcu_box1'`. After restarting, three insertion loads of 1B failed with `1B did not recognize the filament` and `QDE_004_001`, and a later request failed with `QDE_004_011`. Over the next three hours, across several restarts and with the nozzle heated to 240–280 °C, `BOX_UNLOAD` refused ten times with `无法识别到已进料耗材`; none passed that step, and the operator reported the hotend staying hot. The saved `last_load_slot` was not captured. A Box reset partway through the automatic slot load, leaving 1B's filament at the hub, fits the vendor predicate above but is not proven.

- **Runtime-confirmed (2026-10-31, `.07.01`, two USB Boxes, 2 s status polling plus `klippy.log`):** during a Box load, `box_extras.loaded_slot` and `last_load_slot` changed to the loading slot when its filament reached the Box hub, early in `BOX_LOAD` and before the extruder moved. This happened in a flow `1` load whose filament never reached the toolhead sensor and that paused with `QDE_004_006`; both values stayed on that slot afterwards. In a flow `2` change from slot 1 to slot 0, both read `slot16` once the hub cleared during `BOX_UNLOAD`, then `slot0` when slot 0 reached the hub. The extruder pulled back 4 mm at the cut and 110 mm during the unload, then moved 164.2 mm forward during slot 0's load and wipe.
- **Runtime-confirmed (same session):** a flow paused at `BOX_LOAD` kept the hotend target at 240 °C. Neither QIDI's touchscreen nor Fluidd offered a retry or stop. `FLOW_STOP` cleared the task (`flow_id None`) but its G-code request had not returned eight minutes later, and every later G-code command waited behind it until `klipper.service` was restarted; the THR MCU then reported shutdown until `FIRMWARE_RESTART`. In a later flow `2` change, `FLOW_RETRY` after `QDE_004_009` (`Extruder unloading failure`) at `BOX_UNLOAD` returned and the flow completed.

### `.07.01` eject

- **Harness-recovered (2026-10-28, fake objects):** `cmd_EJECT_FILAMENT_CONTROL` reads `SLOT`, asks `box_adapter.flow_decision_func("EJECT", slot)` for the flow, and calls `task_queue_manager.start_flow(flow_id, self.normal_complete_script)`. `BoxAdapterV1.flow_decision_func` reads the toolhead `filament_switch_sensor`, saved `last_load_slot`, and `box1base.b_endstop_state`. For an eject of slot 2 it returned:

  | Hub (`b_endstop_state`) | `last_load_slot` | Toolhead sensor | Flow |
  |---|---|---|---:|
  | clear (`1`) | any harnessed value | either | `4` |
  | occupied (`0`) | `slot16` | either | `0` |
  | occupied | `slot2` | filament | `5` |
  | occupied | `slot2` | empty | `11` |
  | occupied | another slot | filament | `4` |
  | occupied | another slot | empty | `11` |

- **Harness-recovered:** `BoxAdapterV1.eject()` first sends `MOVE_TO_TRASH` through its own `gcode` attribute, then reads `b_endstop_state` and `task_queue_manager.targer_eject_slot`. `BoxAdapterV2.eject()` returned `True` without sending G-code. `normal_complete_script(flow_task)` sends `MOVE_TO_TRASH`, `M104 S0`, and `SET_STEPPER_ENABLE STEPPER=extruder enable=0` through the controller's `gcode` attribute, adds `G4 P5000` and `WIPE_NOZZLE_DROP` when `current_flow_temp` is set, then waits for moves. The completion callback runs before `_cleanup_completed_task()`.
- **Runtime-confirmed (2026-10-28, two USB Boxes, X and Y unhomed):** `EJECT_FILAMENT_CONTROL SLOT=2` with the toolhead sensor clear and `loaded_slot` `slot16` homed X and Y through `MOVE_TO_TRASH` in about 20 s, retracted slot 2, parked again, set the hotend target to 0, and disabled the extruder. Nothing heated or cut.
- **Runtime-confirmed (2026-10-28):** `box_adapter` and `task_queue_manager.operation_adapter` were still `None` when a package module's `klippy:ready` handler and a reactor callback it scheduled ran, and `MultiColorController is ready.` was logged after them. Later both held the same `BoxAdapterV1`, and `task_queue_manager` stayed the same object. During flow `4`, `task_queue_manager.current_task.queue` was `['BOX_EJECT']` both when the eject step and when the completion script sent G-code.
- **Unresolved:** live eject flows `5` and `11` were not exercised.

### `.07.01` filament between the hub and the toolhead

- **Harness-recovered (2026-10-31, `BoxExtruderStepper` methods on a fake `self`):** `extruder_load_single_func()` saves the slot state `3`, homes the slot toward the hub sensor (up to 3000 mm at 85 mm/s), and saves `last_load_slot` as that slot as soon as the hub stage succeeds, before the three-stage feed to the toolhead sensor. A failed hub stage saves the slot state `-2` and reports `QDE_004_006`; a failed toolhead stage takes a retry path that moves the toolhead and extruder.
- **Runtime-confirmed (2026-10-31 incident):** the hub record logged 1B reaching the hub at 06:54:51, and a test module that follows the loaded slot logged `1B loaded` in the same second; the extruder then drew filament without it reaching the toolhead sensor, and `QDE_004_006` followed at 06:56:19. Saved state afterwards was `last_load_slot` `slot1`, `slot_sync` `slot-1`, `extrude_state` `2`, `slot1` `-2`, and `retained_slot` `slot1`, with the hub sensor `0` (filament) and the toolhead sensor empty. The operator had lengthened the tube from the hub to the toolhead without raising `FAST_LENGTH` (570).
- **Harness-recovered:** with the toolhead sensor empty and filament at the hub, `UNLOAD_FILAMENT_CONTROL` gets flow `0`: no steps run, then the completion script sends `MOVE_TO_TRASH`, `M104 S0`, and the extruder disable and responds `Flow completed successfully.` `EJECT_FILAMENT_CONTROL` of `last_load_slot` gets flow `11`: `BOX_HEAT` heats the nozzle, and `BOX_UNLOAD` calls `extruder_unload_single_func()` on that slot.
- **Harness-recovered:** `extruder_unload_single_func()` with the toolhead sensor empty and filament at the hub skips the extruder and saves the slot state `3`, then homes the slot back on the hub sensor (`-350` mm at 65 mm/s, then `-1150` mm at 85 mm/s, accel 100). When the hub clears it saves `last_load_slot` `slot16`, retracts 260 mm more at 80 mm/s, saves the slot state `1`, disables the slot motor, and sends `MOVE_TO_TRASH`. Otherwise it moves the toolhead and homes again up to 1500 mm with the extruder synced.
- **Harness-recovered:** the eject step's `slot_unload_single_func()` saves the slot state `3` and homes the slot back up to 3000 mm at 100 mm/s until its inlet sensor clears; on failure it reports `QDE_004_003` and saves the slot state `-1`.
- **Harness-recovered:** `BoxExtras.print_sensor_state_to_log()` sends its message to the console with `respond_raw('!! ' + message)` and logs it with a `last sensor state:` block. The block logged at the 2026-10-31 failure read `b_endstop_state = 1`, while the controller's hub field read `0` afterwards; which value the block prints is **unresolved**.
- **Runtime-confirmed (2026-10-31):** `multi_color_controller` status also publishes `box_warning_info`, an empty list on an idle printer. What fills it is **unresolved**; the controller's strings include the Box heater-timeout and humidity-sensor warnings.
- **Unresolved:** whether flow `11` would have cleared the hub on the printer; it never ran.

### `.07.01` tool change

- **Harness-recovered (2026-10-29, USB `BoxAdapterV1`, fake objects):** `T_MANAGER` returns without a flow when saved `enable_box` is not `1`. Otherwise `BoxExtras.filament_printing_manager_box1` decides. It first returns if `tool_change.exclude_tool` is truthy. It then treats saved `extrude_state` as the previous tool. If that is not `-1` and `value_t<previous>` equals `value_t<T>`, it calls `slot_sync(True)` on the target slot stepper, saves `extrude_state = T`, and returns. That check reads neither `last_load_slot` nor the toolhead sensor.
- **Harness-recovered:** when the mappings differ or `extrude_state` is `-1`, it saves `extrude_state = T`. A target beyond `box_count * 4`, including `slot16`, or a missing or `slot16` `last_load_slot` reports `QDE_004_027` and sends `PAUSE`. If `last_load_slot` equals the target and the toolhead sensor detects filament, it returns after `slot_sync(True)`. If the target matches but the toolhead is empty, it runs flow `13` without a cut. Any other target runs flow `13` with `CUT_FILAMENT_1` and `MOVE_TO_TRASH`, then unloads `last_load_slot`.
- **Harness-recovered:** the no-flow returns send no G-code, change no heater target, and write only `extrude_state` and `slot_sync`. `slot_sync(True)` unbinds every slot stepper from the extruder and calls `box_autofeed.auto_start`; the physical effect was not traced.
- **Runtime-confirmed (operator `klippy.log`, 2026-10-29, two USB Boxes):** in a print whose four tools Fluidd mapped to one slot, each `T_MANAGER T=<n>` returned in 1–5 ms. In a print with distinct slots on 2026-10-28, each blocked for 62–66 s.
- **Unresolved:** RS-485 `BoxAdapterV2` tool-change predicates, and whether `multi_color_controller.box.loaded_slot` names the new slot by the time a flow-`13` `T_MANAGER` returns.

### `.07.01` filament IDs in Box flows

- **Harness-recovered (2026-10-29, fake objects with a two-entry `filament-0.4.json`):** `BoxAdapterV1.flow_decision_func` reads the target slot's and the last-loaded slot's saved filament IDs through `get_save_vars_filament_id`, then compares them with `MaterialDatabaseJosn.get_max_temp_id`, which reads `nozzle_temperature` (`[min, max]`, default `[0, 240]`) from each ID's entry. `get_save_vars_filament_id` returns `QFA00` for a missing or non-string value and any string unchanged, including `'None'`, `''`, and `'7'`. `get_max_temp_id` raises `AttributeError` for a string ID missing from the database and `TypeError` for a non-string; `get_max_temp_by_single_id` falls back to `240` for an unknown string ID.
- **Harness-recovered:** `LOAD_FILAMENT_CONTROL SLOT=16` with `filament_slot16 = 'None'` raised in `get_max_temp_id` for every harnessed toolhead-sensor and hub state. With `QFA00` substituted it selected flow `9` with filament at the toolhead and `last_load_slot` another slot, and flow `6` with the toolhead empty.
- **Harness-recovered:** the controller's `fila_json` database exists from controller construction, and `ExternalAdapter` (`controller.extre`, also created then) and the `BoxAdapterV1` created at ready hold that same object as `material_db`.
- **Runtime-confirmed (operator `klippy.log`, 2026-10-29, package `26.10.23.1`, one USB Box):** three `LOAD_FILAMENT_CONTROL SLOT=16` requests, with `filament_slot16 = 'None'` and `last_load_slot = 'slot16'` saved, each failed with `Internal error on command:"LOAD_FILAMENT_CONTROL"` from `MaterialDatabaseJosn.get_max_temp_id` (`AttributeError: 'NoneType' object has no attribute 'get'`) and shut Klipper down. The automatic restart that followed failed with `Can not update MCU 'mcu' config as it is shutdown`. The requests repeated one to four seconds apart after each shutdown; which client sent them was not recorded.

## Command risk boundary

### Runtime-confirmed query/idle-safe captures

```text
QUERY_MULTI_COLOR
QUERY_SAVE_VARIABLES
GET_MULTI_COLOR_STATUS
MCB_QUERY
SLOT_RFID_READ
INIT_RFID_READ
MULTI_COLOR_INIT_RFID
MULTI_COLOR_READ_RFID
```

The RFID commands were idle-safe only in captures with no valid visible tag result. Successful-tag behavior remains unresolved.

### State-changing or motion-adjacent

```text
MULTI_COLOR_SYNC
MULTI_COLOR_CLEAR_RUNOUT
SET_SAVE_VARIABLE
RESET_MULTI_COLOR_VARS
CLEAR_RUNOUT_NUM
MCB_CONFIG
SET_LIMIT_A
MCB_AUTO_ABORT
```

An already-matching sync or already-clear runout capture produced no delta; that does not prove no-op behavior for other state.

### Heater/dryer

```text
ENABLE_BOX_DRY DISABLE_BOX_DRY DISABLE_BOX_HEATER BOX_TEMP_SET
MULTI_COLOR_DRY MULTI_COLOR_DISABLE_HEATER MULTI_COLOR_SET_TEMP
```

### Toolhead/extruder motion

```text
CLEAR_FLUSH CLEAR_OOZE CUT_FILAMENT MOVE_TO_TRASH
MULTI_COLOR_CLEAR_FLUSH MULTI_COLOR_CLEAR_OOZE MULTI_COLOR_CUT_FILAMENT
```

### Box motion or motion-capable

```text
EXTRUDER_LOAD EXTRUDER_UNLOAD SLOT_UNLOAD E_LOAD E_UNLOAD E_BOX
BOX_PRINT_START MULTI_COLOR_PRINT_START
MULTI_COLOR_LOAD MULTI_COLOR_UNLOAD MULTI_COLOR_SWAP MULTI_COLOR_BOX_UNLOAD
MCB_AUTO_START
```

### Retry/recovery runtime gaps

```text
TRY_MOVE_AGAIN TRY_RESUME_PRINT RESUME_PRINT_1 AUTO_RELOAD_FILAMENT
RELOAD_ALL TIGHTEN_FILAMENT
MULTI_COLOR_RELOAD_ALL MULTI_COLOR_AUTO_RELOAD MULTI_COLOR_RETRY
MULTI_COLOR_TIGHTEN MULTI_COLOR_TRY_RESUME MULTI_COLOR_RESUME_PRINT
```

Moonraker command help is incomplete: callable compiled commands such as `BOX_PRINT_START`, `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, `SLOT_UNLOAD`, `SLOT_RFID_READ`, `CLEAR_FLUSH`, and `CLEAR_OOZE` were absent from the filtered help capture.

Additional registered controller surface:

```text
MULTI_COLOR_CONFIG MULTI_COLOR_SYNC MULTI_COLOR_READ_RFID
MULTI_COLOR_INIT_RFID MULTI_COLOR_INIT_MAPPING QUERY_MULTI_COLOR
QUERY_SAVE_VARIABLES MULTI_COLOR_CLEAR_RUNOUT
SET_SAVE_VARIABLE RESET_MULTI_COLOR_VARS
MCB_AUTO_ABORT MCB_AUTO_START MCB_CONFIG MCB_QUERY SET_LIMIT_A
```

## Runtime-confirmed idle effects

- `QUERY_MULTI_COLOR`, `QUERY_SAVE_VARIABLES`, and `GET_MULTI_COLOR_STATUS` preserved saved state and operation state.
- `MULTI_COLOR_SYNC SLOT=slot2` preserved state when already synced to slot 2.
- `MULTI_COLOR_CLEAR_RUNOUT` preserved state when counters were already zero.
- RFID commands returned `ok`, left slot metadata unchanged, ended with `rfid.reading=false` and `rfid.results={}`, and exposed no raw FM17550 payload.
- `MCB_CONFIG SLOT=slot2`, `MCB_QUERY`, `SET_LIMIT_A STATE=0/1/0`, and idle `MCB_AUTO_ABORT` returned `ok`, preserved saved variables, and exposed no `MCB_STATE`, `MCB_DONE`, or `MCB_ERROR` payload.

## Error surface

Owner and message strings are static-recovered. `QDE_004_006` was seen live on 2026-10-19 and 2026-10-31; the console line is `!! Code:<code>; Message:<message>`.

| Code | Owner | Message |
|---|---|---|
| `QDE_004_001` | `box_stepper.so` | `Slot loading failure, please check the trigger, please reload %s.` |
| `QDE_004_002` | `box_stepper.so` | `Extruder has been loaded, cannot load %s.` |
| `QDE_004_003` | `box_stepper.so` | `Slot unloading failure, please unload %s again.` |
| `QDE_004_004` | `box_stepper.so` | `Please unload extruder first.` |
| `QDE_004_005` | `box_stepper.so` | `Please load the filament to %s first.` |
| `QDE_004_006` | `box_stepper.so` | `Extruder loading failure.` |
| `QDE_004_007` | `box_stepper.so` | `Extruder not loaded.` |
| `QDE_004_008` | `box_stepper.so` | `Extruder unloading failure.` |
| `QDE_004_009` | `box_stepper.so` | `Extruder unloading failure.` |
| `QDE_004_010` | `box_extras.so` | `The current feeding status is incorrect. Please exit the filament from the extruder.` |
| `QDE_004_011` | `box_stepper.so` | `Detected that filament have been loaded, please unload filament first` |
| `QDE_004_013` | `box_autofeed.so` | `Detected wrapping filament,please check the filament.` |
| `QDE_004_014` | `box_extras.so` | `Parameter setting error, please reset.` |
| `QDE_004_016` | `box_stepper.so` | `The filament has been exhausted, please load the filament to %s.` |
| `QDE_004_017` | `box_stepper.so` | `Filament flush failed, please clean and then load the filament in %s.` |
| `QDE_004_018` | `box_stepper.so` | `No filament specified, %s cannot be automatically replaced.` |
| `QDE_004_019` | `box_stepper.so` | `Please check if your PTFE Tube is bent` |
| `QDE_004_020` | `box_stepper.so` | `Detected that the filament has been unloaded, please reload.` |
| `QDE_004_021` | `box_extras.so` | `Unable to recognize loaded filament.` |
| `QDE_004_022` | `box_stepper.so` | `No replaceable slot found.` |
| `QDE_004_023` | `box_extras.so` | `Auto reload failed.` |
| `QDE_004_024` | `box_stepper.so` | `The filament failed to enter the extruder.` |
| `QDE_004_025` | `box_stepper.so` | `Extruder unloading failure.` |

`QDE_004_012` and `QDE_004_015` were absent from captured module strings. Exact live predicates for all codes remain unresolved.
