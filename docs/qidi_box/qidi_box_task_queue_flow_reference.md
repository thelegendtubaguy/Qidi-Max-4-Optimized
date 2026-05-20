# QIDI Box task queue flow reference

## Source

Runtime harness executed on the printer against `multi_color_controller.so` without sending motion G-code:

- probe: `tmp/qidi-box-reversing/probe_taskqueue_manager.py`
- output: `tmp/qidi-box-reversing/taskqueue_manager_probe.txt`
- expanded output: `tmp/qidi-box-reversing/taskqueue_manager_probe2.txt`

The harness imports `multi_color_controller.so`, instantiates `TaskQueueManager` with a fake printer/gcode object, inspects class state, and directly calls `_decide_flow_id(action, target_slot, filament_present, last_load_slot)`.

## `BoxState` enum

| Name | Value |
|---|---:|
| `ERROR` | `-1` |
| `UNKNOWN` | `-2` |
| `PENDING` | `-3` |
| `EMPTY` | `0` |
| `LOADED` | `1` |
| `IN_EXTRUDER` | `2` |
| `IN_FEEDER` | `3` |

The live runtime capture in `docs/qidi_box/qidi_box_runtime_observations.md` confirms `slot2 = 2` and `slot2: IN_EXTRUDER` on the current machine.

## `TaskQueueManager.FLOW_MAP`

| Flow ID | Steps |
|---:|---|
| `0` | `[]` |
| `1` | `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE` |
| `2` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_LOAD`, `BOX_WIPE` |
| `3` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD` |
| `4` | `BOX_EJECT` |
| `5` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_EJECT` |
| `6` | `EXT_HEAT`, `EXT_LOAD`, `EXT_BITE`, `EXT_WIPE` |
| `7` | `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD` |
| `8` | `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD`, `WAIT_USER`, `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE` |
| `9` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `WAIT_USER`, `EXT_HEAT`, `EXT_LOAD`, `EXT_BITE`, `EXT_WIPE` |

Flow `0` is the idle/no-op flow.

Flow IDs `1` through `5` use QIDI Box-side steps. Flow IDs `6` through `9` use extruder-side recovery/load/unload steps and optional `WAIT_USER` handoff.

## `_decide_flow_id()` harness results

Accepted action strings found by the harness:

| Action | Observed result |
|---|---|
| `LOAD` | returns flow `1` when `filament_present` is false; returns flow `2` when `filament_present` is true and `last_load_slot` is not `slot16` |
| `UNLOAD` | returns flow `3` when `filament_present` is true and `last_load_slot` is not `slot16`; returns flow `7` when `filament_present` is true and `last_load_slot` is `slot16` |
| `EJECT` | returns flow `4` regardless of `filament_present`, `target_slot`, or `last_load_slot` in the harnessed cases |

Harnessed `LOAD` examples:

| Action | Target | `filament_present` | `last_load_slot` | Flow ID |
|---|---|---:|---|---:|
| `LOAD` | `slot0` | `false` | `slot0` | `1` |
| `LOAD` | `slot0` | `false` | `slot2` | `1` |
| `LOAD` | `slot2` | `false` | `slot0` | `1` |
| `LOAD` | `slot2` | `false` | `slot2` | `1` |
| `LOAD` | `slot0` | `true` | `slot0` | `2` |
| `LOAD` | `slot0` | `true` | `slot2` | `2` |
| `LOAD` | `slot2` | `true` | `slot0` | `2` |
| `LOAD` | `slot2` | `true` | `slot2` | `2` |

Harnessed `UNLOAD` examples:

| Action | Target | `filament_present` | `last_load_slot` | Flow ID |
|---|---|---:|---|---:|
| `UNLOAD` | `slot0` | `true` | `slot0` | `3` |
| `UNLOAD` | `slot0` | `true` | `slot2` | `3` |
| `UNLOAD` | `slot2` | `true` | `slot0` | `3` |
| `UNLOAD` | `slot2` | `true` | `slot2` | `3` |
| `UNLOAD` | `slot0` | `true` | `slot16` | `7` |
| `UNLOAD` | `slot2` | `true` | `slot16` | `7` |

Harnessed `EJECT` examples:

| Action | Target | `filament_present` | `last_load_slot` | Flow ID |
|---|---|---:|---|---:|
| `EJECT` | `slot0` | `false` | `slot0` | `4` |
| `EJECT` | `slot0` | `true` | `slot2` | `4` |
| `EJECT` | `slot2` | `false` | `slot16` | `4` |
| `EJECT` | `slot2` | `true` | `slot16` | `4` |

Other tested action strings such as `load`, `unload`, `load_filament`, `unload_filament`, `BOX_LOAD`, `BOX_UNLOAD`, `EXT_LOAD`, `EXT_UNLOAD`, `FILAMENT_RUNOUT`, and `SKIP_EXTRUDE` returned flow `0` in the fake-manager harness when `last_load_slot` was non-null.

## State and transition harness

Additional harness output:

- probe: `tmp/qidi-box-reversing/probe_taskqueue_transitions.py`
- output: `tmp/qidi-box-reversing/taskqueue_transitions_probe.json`

`UnifiedState()` defaults from the compiled module:

| Field | Default |
|---|---|
| `system_ready` | `False` |
| `operating_mode` | `ConnectionMode.LOCAL` |
| `box_count` | `0` |
| `box_connected` | `False` |
| `box_temperature` | `{}` |
| `slot_states` | `{}` |
| `slot_materials` | `{}` |
| `last_loaded_slot` | `None` |
| `extruder_loaded` | `False` |
| `extruder_temp` | `0` |
| `extruder_target` | `0` |
| `filament_detected` | `False` |
| `operation_progress` | `0` |
| `operation_error` | `None` |
| `box_button_state` | `0` |
| `box_operate_state` | `0` |
| `operate_state` | `0` |
| `current_operation` | `None` |
| `steps` | `[]` |
| `is_waiting_user` | `False` |
| `printing` | `False` |
| `current_tool` | `-1` |
| `next_tool` | `-1` |
| `rfid_reading` | `False` |
| `rfid_results` | `{}` |
| `drying_states` | `{}` |
| `sensors` | `{'b_endstop': 0, 'e_endstop': 0, 'runout_sensors': {}, 'pressure_sensor': 0}` |
| `config_vars` | `{}` |
| `slot_sync` | `slot16` |
| `retry_step` | `None` |
| `load_retry_num` | `0` |
| `enable_box` | `0` |
| `auto_reload_detect` | `0` |
| `auto_read_rfid` | `0` |
| `auto_init_detect` | `0` |
| `main_status` | empty string |
| `sub_status` | empty string |

`TaskQueueManager.start_flow(flow_id)` behavior in the fake-manager harness:

- sets `operate_state` to the flow ID
- copies `FLOW_MAP[flow_id]` into `steps`
- sets `current_operation` to `0` for non-empty flows
- leaves `is_waiting_user = False`
- leaves `active_step_locked = False`
- emits `RESPOND:Start Flow Group: <flow_id>` for non-empty flows

`TaskQueueManager._move_next()` behavior in the fake-manager harness:

- on flow `0`, leaves the manager idle and emits `RESPOND:Flow Group 0 Completed.`
- on one-step flow `4`, completes immediately from operation `0` and emits `RESPOND:Flow Group 4 Completed.`
- on multi-step flows, advances `current_operation` from `0` to `1`
- does not emit G-code movement scripts in the fake-manager harness

`TaskQueueManager.tick(UnifiedState())` behavior in the fake-manager harness:

- after `_move_next()` on box-side flows `1`, `2`, `3`, and `5`, the all-default `UnifiedState()` caused the manager to reset to idle; this indicates `_is_group_completed()` can classify those flows as complete based on state predicates, not only by the operation index.
- after `_move_next()` on extruder-side or mixed flows `6`, `7`, `8`, and `9`, the all-default `UnifiedState()` did not reset the manager; this indicates ext-side completion predicates require different state fields.

`confirm_user_wait()` did not alter state in the harness unless the manager was already in a waiting-user state.

## Harness caveats

- `_decide_flow_id()` calls `.replace()` on `last_load_slot`; `last_load_slot=None` raises `AttributeError` in direct harnessing.
- `LOAD` with `filament_present=true` and `last_load_slot=slot16` raised a Python `TypeError` in the direct harness for the tested target values; this may be an invalid state combination or may require controller context not present in the fake harness.
- The harness did not execute `_move_next()`, `_check_step_finished()`, or adapter step dispatch; it only resolved flow IDs.
- Runtime confirmation is still required while real operations are active because the live command path may normalize action strings, target slots, and persisted `slot_sync`/`last_load_slot` before calling `_decide_flow_id()`.
