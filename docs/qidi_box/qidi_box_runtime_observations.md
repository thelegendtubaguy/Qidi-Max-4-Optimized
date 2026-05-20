# QIDI Box runtime observations

## Non-motion capture 2026-05-07 14:51

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-145130-nonmotion/`

Captured without motion commands:

- `services.txt`
- `klippy-tail.log`
- `moonraker-tail.log`
- `saved_variables.cfg`
- `box-events.txt`

`box-events.txt` contained only saved-variable matches in the tailed log/config window; no recent `BOX_PRINT_START`, `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, `SLOT_RFID_READ`, `MCB_*`, or `QDE_004` log lines appeared in the captured tails.

## Saved-variable state

Current non-motion state from `saved_variables.cfg`:

| Variable | Value |
|---|---|
| `enable_box` | `1` |
| `box_count` | `1` |
| `auto_read_rfid` | `1` |
| `auto_reload_detect` | `1` |
| `auto_init_detect` | `0` |
| `extrude_state` | `2` |
| `last_load_slot` | `slot2` |
| `slot_sync` | `slot2` |
| `load_retry_num` | `0` |
| `retry_step` | `None` |
| `is_tool_change` | `0` |
| `retained_slot` | `slot-1` |
| `retained_tool` | `-1` |
| `retained_tool_ready` | `0` |

`runout_0` through `runout_15` are all `0`.

`slot2 = 2`; other visible `slotN` state variables are `0`.

Tool mapping in the captured state:

| Tool variable | Slot |
|---|---|
| `value_t0` | `slot0` |
| `value_t1` | `slot1` |
| `value_t2` | `slot2` |
| `value_t3` | `slot3` |

Material/color/vendor metadata in the captured state indicates slot metadata is already populated for slots `0`..`16`. Slot `2` is the currently loaded/synced slot according to `last_load_slot` and `slot_sync`.

## Moonraker object status capture 2026-05-07 14:52

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-145246-status/`

Captured through Moonraker without motion commands:

- `objects-list.json`
- `box-object-names.txt`
- `box-objects-query.json`

Queried objects:

- `box_extras`
- `multi_color_controller`
- `save_variables`
- `filament_switch_sensor filament_switch_sensor`
- `box_stepper slot0`
- `box_stepper slot1`
- `box_stepper slot2`
- `box_stepper slot3`
- `heater_generic heater_box1`
- `temperature_sensor heater_temp_a_box1`
- `temperature_sensor heater_temp_b_box1`

### `box_extras` status

| Field | Value |
|---|---|
| `box_button_state` | `0` |
| `b_endstop_state` | `0` |
| `e_endstop_state` | `1` |
| `box_operate_state` | `0` |
| `box_drying_state.box1.dry_state` | `0` |
| `box_drying_state.box1.end_time` | `0` |
| `is_tool_change` | `0` |

### `multi_color_controller` status

| Field | Value |
|---|---|
| `system.ready` | `true` |
| `system.mode` | `local` |
| `hardware.box_count` | `1` |
| `hardware.connected` | `true` |
| `slots.last_loaded` | `slot2` |
| `slots.states.slot2` | `2` |
| `slots.states.slot0` | `0` |
| `slots.states.slot1` | `0` |
| `slots.states.slot3` | `0` |
| `extruder.loaded` | `true` |
| `extruder.target` | `0.0` |
| `extruder.filament_detected` | `true` |
| `operation.current` | `-1` |
| `operation.progress` | `0` |
| `operation.error` | `None` |
| `operation.is_waiting_user` | `false` |
| `print.printing` | `false` |
| `print.current_tool` | `-1` |
| `print.next_tool` | `-1` |
| `rfid.reading` | `false` |
| `sensors.b_endstop` | `0` |
| `sensors.e_endstop` | `1` |
| `sensors.runout_sensors.slot0` | `1` |
| `sensors.runout_sensors.slot1` | `1` |
| `sensors.runout_sensors.slot2` | `0` |
| `sensors.runout_sensors.slot3` | `1` |
| `config_summary.slot_sync` | `slot2` |

Slot material lookup through `multi_color_controller` resolved `slot2` as Generic ASA with color `#060606`; `slot16` also resolves to ASA metadata in the captured status. Slot metadata is resolved through saved variables and `config/officiall_filas_list.cfg`.

### Stepper and sensor status

| Object | Status |
|---|---|
| `filament_switch_sensor filament_switch_sensor` | `filament_detected=true`, `enabled=false` |
| `box_stepper slot0` | `runout_button=1`, `rfid_state=0` |
| `box_stepper slot1` | `runout_button=1`, `rfid_state=0` |
| `box_stepper slot2` | `runout_button=0`, `rfid_state=0` |
| `box_stepper slot3` | `runout_button=1`, `rfid_state=0` |

The active loaded/synced `slot2` corresponds to `box_stepper slot2.runout_button=0` while other visible slots report `runout_button=1`; this indicates the vendor runout polarity is inverted relative to the intuitive `filament present = 1` wording.

### Heater status

| Object | Status |
|---|---|
| `heater_generic heater_box1` | `temperature=23.91`, `target=0.0`, `power=0.0` |
| `temperature_sensor heater_temp_a_box1` | `temperature=24.98`, `measured_min_temp=24.79`, `measured_max_temp=45.21` |
| `temperature_sensor heater_temp_b_box1` | `temperature=25.45`, `measured_min_temp=25.24`, `measured_max_temp=43.92` |

## Interpretation

- The machine currently reports QIDI Box enabled with one box configured.
- The active loaded path is trusted/synced to `slot2`.
- `extrude_state = 2`, `multi_color_controller.slots.states.slot2 = 2`, and `BoxState.IN_EXTRUDER = 2` align with the current loaded-to-extruder condition.
- `e_endstop_state = 1` and `extruder.filament_detected = true` align with a loaded extruder path.
- `box_stepper slot2.runout_button = 0` with `slot2` loaded indicates inverted slot runout/pre-gate active polarity.
- The retained-filament fields are idle/reset in this snapshot.
- No new runtime branch predicates were proven by the non-motion log tail because no recent box operations appeared in the captured log tails.

## Current non-motion status refresh 2026-05-07 16:31

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-163127-current-nonmotion/`

Generated analyzer outputs:

- `box-events.txt`
- `status-summary.tsv`

Captured without motion commands:

| Field | Value |
|---|---|
| `print_stats.state` | `standby` |
| `idle_timeout.state` | `Ready` |
| `multi_color_controller.system.ready` | `true` |
| `multi_color_controller.system.mode` | `local` |
| `multi_color_controller.slots.last_loaded` | `slot2` |
| `save_variables.slot_sync` | `slot2` |
| `save_variables.extrude_state` | `2` |
| `multi_color_controller.extruder.loaded` | `true` |
| `multi_color_controller.extruder.filament_detected` | `true` |
| `multi_color_controller.operation.current` | `-1` |
| `multi_color_controller.operation.steps` | `[]` |
| `multi_color_controller.rfid.results` | `{}` |
| `box_extras.b_endstop_state` | `0` |
| `box_extras.e_endstop_state` | `1` |
| `filament_switch_sensor filament_switch_sensor.enabled` | `false` |
| `filament_switch_sensor filament_switch_sensor.filament_detected` | `true` |
| `box_stepper slot0.runout_button` | `1` |
| `box_stepper slot1.runout_button` | `1` |
| `box_stepper slot2.runout_button` | `0` |
| `box_stepper slot3.runout_button` | `1` |
| `heater_generic heater_box1.temperature` | `45.01` |
| `heater_generic heater_box1.target` | `45.0` |

The refreshed status confirms the same loaded/synced slot2 state as the earlier non-motion captures. The box heater target was `45.0` at this refresh while `box_drying_state.box1.dry_state=0` and `multi_color_controller.drying.box1.dry_state=0`; `docs/qidi_box/qidi_box_status_schema_reference.md` records this mismatch. This is heater/dryer state only and does not resolve load/unload motion predicates.

`box-events.txt` contained saved-variable/status matches only; no new live `BOX_PRINT_START`, `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, `SLOT_UNLOAD`, RFID payload, or `MCB_*` operation appeared in the captured tails.

## No-motion helper capture 2026-05-07 16:44

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-164421-current-helper-nonmotion/`

Command:

```bash
python3 scripts/capture_qidi_box_runtime_snapshot.py --moonraker-url http://192.168.20.165:7125 --label current-helper-nonmotion --timeout 5
```

Generated files:

- `objects-list.json`
- `status.json`
- `capture-metadata.json`
- `box-events.txt`
- `status-summary.tsv`
- `capture-summary.md`

`capture-metadata.json` records `motion_commands_sent=false`. The helper captured `244` Moonraker objects and the same stock QIDI Box ownership objects seen in prior captures. The latest status still reported `print_stats.state=standby`, `idle_timeout.state=Ready`, `last_loaded=slot2`, `slot_sync=slot2`, `extrude_state=2`, `heater_generic heater_box1.target=45.0`, and `heater_generic heater_box1.temperature=45.04`.

## Box stepper and MCU status refresh 2026-05-07 16:41

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-164102-box-stepper-status/`

Generated analyzer outputs:

- `box-events.txt`
- `status-summary.tsv`
- `capture-summary.md`, including box stepper and QIDI Box MCU status tables

Captured without motion commands:

| Object / field | Value |
|---|---|
| `box_stepper slot0.runout_button` | `1` |
| `box_stepper slot0.rfid_state` | `0` |
| `box_stepper slot1.runout_button` | `1` |
| `box_stepper slot1.rfid_state` | `0` |
| `box_stepper slot2.runout_button` | `0` |
| `box_stepper slot2.rfid_state` | `0` |
| `box_stepper slot3.runout_button` | `1` |
| `box_stepper slot3.rfid_state` | `0` |
| `mcu mcu_box1.mcu_version` | `02.03.01.21` |
| `mcu mcu_box1.mcu_constants.MCU` | `stm32f401xc` |
| `mcu mcu_box1.mcu_constants.CLOCK_FREQ` | `84000000` |
| `mcu mcu_box1.last_stats.bytes_invalid` | `0` |
| `mcu mcu_box1.last_stats.bytes_retransmit` | `9` |

`slot2` remained the loaded/synced slot. The `box_stepper slotN.runout_button` values matched `multi_color_controller.sensors.runout_sensors`: loaded slot2 reported `0`, and empty visible slots reported `1`. `rfid_state` stayed `0` for all four physical slots.

The QIDI Box board exposes a standard Klipper MCU status object as `mcu mcu_box1` in the stock include graph.

## Current box sensor/heater status refresh 2026-05-07 16:38

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-163831-current-box-sensors/`

Generated analyzer outputs:

- `box-events.txt`
- `status-summary.tsv`
- `capture-summary.md`, including QIDI Box object inventory from `objects-list.json`

Captured without motion commands:

| Object / field | Value |
|---|---|
| `box_autofeed` query result | `{}` |
| `box_autofeed` in object list | not listed |
| `box_rfid` in object list | not listed |
| `heater_generic heater_box1.temperature` | `45.02` |
| `heater_generic heater_box1.target` | `45.0` |
| `heater_generic heater_box1.power` | `0.0931935870672915` |
| `temperature_sensor heater_temp_a_box1.temperature` | `51.51` |
| `temperature_sensor heater_temp_a_box1.measured_max_temp` | `80.18` |
| `temperature_sensor heater_temp_b_box1.temperature` | `51.23` |
| `temperature_sensor heater_temp_b_box1.measured_max_temp` | `93.55` |
| `box_extras.box_drying_state.box1.dry_state` | `0` |
| `box_extras.box_drying_state.box1.end_time` | `0` |
| `multi_color_controller.drying.box1.dry_state` | `0` |
| `multi_color_controller.drying.box1.end_time` | `0` |

The object list contained stock box hardware/status objects such as `mcu mcu_box1`, `box_extras`, `box_stepper slot0`..`slot3`, `aht20_f heater_box1`, `heater_generic heater_box1`, `temperature_sensor heater_temp_a_box1`, `temperature_sensor heater_temp_b_box1`, `box_heater_fan heater_fan_a_box1`, `box_heater_fan heater_fan_b_box1`, and `controller_fan board_fan_box1`.

The object list did not expose `box_autofeed` or `box_rfid` objects, even though querying `box_autofeed` returned an empty object. This matches earlier captures where `box_autofeed` status was `{}` and RFID reader objects were not Moonraker-visible status objects.

## Query command capture 2026-05-07 14:55

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-145511-query-commands/`

Commands sent through Moonraker G-code script endpoint:

```gcode
QUERY_MULTI_COLOR
QUERY_SAVE_VARIABLES
```

Moonraker accepted both commands with empty JSON response bodies; output appeared in `klippy-after.log`.

`QUERY_MULTI_COLOR` logged:

- mode: `local`
- box count: `1`
- connection: connected
- `slot2: IN_EXTRUDER`
- `slot0`, `slot1`, and `slot3` through `slot15`: `EMPTY`
- slot2 material: ASA, color `#060606`
- extruder material loaded: yes
- extruder temperature: `27.0°C / 0.0°C` at capture time
- filament detected: yes
- current operation: `-1`
- operation progress: `0%`

`QUERY_SAVE_VARIABLES` logged the same saved-variable state as the non-motion file capture, including:

- `enable_box = 1`
- `box_count = 1`
- `extrude_state = 2`
- `last_load_slot = slot2`
- `slot_sync = slot2`
- `load_retry_num = 0`
- `retry_step = None`
- `slot2 = 2`
- `value_t0 = slot0`
- `value_t1 = slot1`
- `value_t2 = slot2`
- `value_t3 = slot3`

Runtime command-surface implication:

- `QUERY_MULTI_COLOR` is a safe non-motion status command for confirming the controller's enum names and material resolution.
- `QUERY_SAVE_VARIABLES` is a safe non-motion status command for confirming persisted box state without copying `saved_variables.cfg`.
- `slot2 = 2`, `extrude_state = 2`, and `QUERY_MULTI_COLOR` `slot2: IN_EXTRUDER` confirm that numeric state `2` maps to `IN_EXTRUDER` in the current local controller state.

## Command helper `QUERY_MULTI_COLOR` capture 2026-05-07 17:24

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-172428-query-multi-color-helper/`

Command:

```bash
python3 scripts/capture_qidi_box_command.py --moonraker-url http://192.168.20.165:7125 --command 'QUERY_MULTI_COLOR' --label query-multi-color-helper
```

Generated files:

- `objects-list.json`
- `status-before.json`
- `saved_variables-before.cfg`
- `command-response.json`
- `status-after.json`
- `saved_variables-after.cfg`
- `capture-metadata.json`
- `box-events.txt`
- `saved_variables.diff`
- `status-summary.tsv`
- `capture-summary.md`

Observed results:

| Field | Value |
|---|---|
| `command-response.json.result` | `ok` |
| `capture-metadata.command_risk` | `no_motion` |
| `capture-metadata.motion_commands_sent` | `false` |
| `saved_variables.diff` size | `0` bytes |
| `print_stats.state` before/after | `standby` / `standby` |
| `idle_timeout.state` before/after | `Ready` / `Ready` |
| `multi_color_controller.system.mode` before/after | `local` / `local` |
| `multi_color_controller.operation.current` before/after | `-1` / `-1` |
| `multi_color_controller.slots.last_loaded` before/after | `slot2` / `slot2` |
| `save_variables.slot_sync` before/after | `slot2` / `slot2` |
| `save_variables.extrude_state` before/after | `2` / `2` |
| `multi_color_controller.extruder.loaded` before/after | `true` / `true` |
| `multi_color_controller.extruder.filament_detected` before/after | `true` / `true` |
| `multi_color_controller.sensors.runout_sensors` before/after | `slot0=1, slot1=1, slot2=0, slot3=1` / same |
| `heater_generic heater_box1.target` | `45.0` |
| `heater_generic heater_box1.temperature` | `44.94` |

`objects-list.json` contained `244` Moonraker objects. Stock QIDI Box ownership objects were present, including `mcu mcu_box1`, `box_extras`, `box_stepper slot0`..`slot3`, `heater_generic heater_box1`, `temperature_sensor heater_temp_a_box1`, `temperature_sensor heater_temp_b_box1`, `aht20_f heater_box1`, `box_heater_fan heater_fan_a_box1`, `box_heater_fan heater_fan_b_box1`, and `controller_fan board_fan_box1`. `box_autofeed` and `box_rfid card_reader_1`..`card_reader_4` were not listed as Moonraker objects.

This capture validates `scripts/capture_qidi_box_command.py` against the live printer for a no-motion QIDI command and confirms the helper's before/after status and saved-variable snapshot format. It does not add new movement branch predicates because no motion-risk command was sent.

## Command helper `QUERY_SAVE_VARIABLES` capture 2026-05-07 17:28

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-172816-query-save-variables-helper/`

Command:

```bash
python3 scripts/capture_qidi_box_command.py --moonraker-url http://192.168.20.165:7125 --command 'QUERY_SAVE_VARIABLES' --label query-save-variables-helper
```

Generated files:

- `objects-list.json`
- `status-before.json`
- `saved_variables-before.cfg`
- `command-response.json`
- `status-after.json`
- `saved_variables-after.cfg`
- `capture-metadata.json`
- `box-events.txt`
- `saved_variables.diff`
- `status-summary.tsv`
- `capture-summary.md`

Observed results:

| Field | Value |
|---|---|
| `command-response.json.result` | `ok` |
| `capture-metadata.command_risk` | `no_motion` |
| `capture-metadata.motion_commands_sent` | `false` |
| `capture-metadata.state_change_command_sent` | `false` |
| `saved_variables.diff` size | `0` bytes |
| `print_stats.state` before/after | `standby` / `standby` |
| `idle_timeout.state` before/after | `Ready` / `Ready` |
| `multi_color_controller.operation.current` before/after | `-1` / `-1` |
| `multi_color_controller.slots.last_loaded` before/after | `slot2` / `slot2` |
| `save_variables.slot_sync` before/after | `slot2` / `slot2` |
| `save_variables.extrude_state` before/after | `2` / `2` |
| `multi_color_controller.extruder.loaded` before/after | `true` / `true` |
| `multi_color_controller.extruder.filament_detected` before/after | `true` / `true` |
| `heater_generic heater_box1.target` | `45.0` |
| `heater_generic heater_box1.temperature` | `45.03` |

`objects-list.json` again contained `244` Moonraker objects with stock QIDI Box ownership present. `box_autofeed` and `box_rfid card_reader_1`..`card_reader_4` were not listed as Moonraker objects.

This capture validates `QUERY_SAVE_VARIABLES` as a no-motion command.

## Command helper `GET_MULTI_COLOR_STATUS` capture 2026-05-07 17:49

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-174925-get-multi-color-status-helper/`

Command:

```bash
python3 scripts/capture_qidi_box_command.py --moonraker-url http://192.168.20.165:7125 --command 'GET_MULTI_COLOR_STATUS' --label get-multi-color-status-helper
```

Observed results:

| Field | Value |
|---|---|
| `command-response.json.result` | `ok` |
| `capture-metadata.command_risk` | `no_motion` |
| `capture-metadata.motion_commands_sent` | `false` |
| `capture-metadata.state_change_command_sent` | `false` |
| `saved_variables.diff` size | `0` bytes |
| `print_stats.state` before/after | `standby` / `standby` |
| `idle_timeout.state` before/after | `Ready` / `Ready` |
| `multi_color_controller.operation.current` before/after | `-1` / `-1` |
| `multi_color_controller.slots.last_loaded` before/after | `slot2` / `slot2` |
| `save_variables.slot_sync` before/after | `slot2` / `slot2` |
| `save_variables.extrude_state` before/after | `2` / `2` |
| `multi_color_controller.extruder.loaded` before/after | `true` / `true` |
| `multi_color_controller.extruder.filament_detected` before/after | `true` / `true` |
| `heater_generic heater_box1.target` | `45.0` |
| `heater_generic heater_box1.temperature` | `44.97` |

`GET_MULTI_COLOR_STATUS` returned `ok` through Moonraker without a response payload. The command did not publish a status delta or saved-variable mutation in the helper capture.

## Command helper `MULTI_COLOR_SYNC SLOT=slot2` capture 2026-05-07 17:56

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-175645-multi-color-sync-slot2-helper/`

Command:

```bash
python3 scripts/capture_qidi_box_command.py --moonraker-url http://192.168.20.165:7125 --command 'MULTI_COLOR_SYNC SLOT=slot2' --label multi-color-sync-slot2-helper --allow-state-change
```

Observed results:

| Field | Value |
|---|---|
| `command-response.json.result` | `ok` |
| `capture-metadata.command_risk` | `state_change` |
| `capture-metadata.motion_commands_sent` | `false` |
| `capture-metadata.state_change_command_sent` | `true` |
| `saved_variables.diff` size | `0` bytes |
| `print_stats.state` before/after | `standby` / `standby` |
| `idle_timeout.state` before/after | `Ready` / `Ready` |
| `multi_color_controller.operation.current` before/after | `-1` / `-1` |
| `multi_color_controller.slots.last_loaded` before/after | `slot2` / `slot2` |
| `save_variables.slot_sync` before/after | `slot2` / `slot2` |
| `save_variables.extrude_state` before/after | `2` / `2` |
| `multi_color_controller.extruder.loaded` before/after | `true` / `true` |
| `multi_color_controller.extruder.filament_detected` before/after | `true` / `true` |

`MULTI_COLOR_SYNC SLOT=slot2` was accepted while the persisted sync slot already matched `slot2`; no status or saved-variable delta was visible. The command remains classified as state-changing because other target slots or unsync paths can mutate `slot_sync`.

## Command helper `MULTI_COLOR_CLEAR_RUNOUT` capture 2026-05-07 18:14

Capture directory:

- `tmp/qidi-box-reversing/runtime-20260507-181439-multi-color-clear-runout-helper/`

Command:

```bash
python3 scripts/capture_qidi_box_command.py --moonraker-url http://192.168.20.165:7125 --command 'MULTI_COLOR_CLEAR_RUNOUT' --label multi-color-clear-runout-helper --allow-state-change
```

Observed results:

| Field | Value |
|---|---|
| `command-response.json.result` | `ok` |
| `capture-metadata.command_risk` | `state_change` |
| `capture-metadata.motion_commands_sent` | `false` |
| `capture-metadata.state_change_command_sent` | `true` |
| `saved_variables.diff` size | `0` bytes |
| `print_stats.state` before/after | `standby` / `standby` |
| `idle_timeout.state` before/after | `Ready` / `Ready` |
| `multi_color_controller.operation.current` before/after | `-1` / `-1` |
| `multi_color_controller.slots.last_loaded` before/after | `slot2` / `slot2` |
| `save_variables.slot_sync` before/after | `slot2` / `slot2` |
| `save_variables.extrude_state` before/after | `2` / `2` |
| `multi_color_controller.extruder.loaded` before/after | `true` / `true` |
| `multi_color_controller.extruder.filament_detected` before/after | `true` / `true` |
| `multi_color_controller.sensors.runout_sensors` before/after | `slot0=1, slot1=1, slot2=0, slot3=1` / same |

`MULTI_COLOR_CLEAR_RUNOUT` was accepted through Moonraker and produced no visible saved-variable or status delta in the idle capture. The command remains classified as state-changing because non-zero runout counters would be cleared by the stock path.

## RFID command captures 2026-05-07 15:29-15:30

Capture directories:

- `tmp/qidi-box-reversing/runtime-20260507-152936-rfid-slot2/`
- `tmp/qidi-box-reversing/runtime-20260507-153017-rfid-init/`
- `tmp/qidi-box-reversing/runtime-20260507-153044-rfid-multicolor-slot2/`

Preflight status in `tmp/qidi-box-reversing/runtime-20260507-152922-rfid-preflight/` showed:

| Field | Value |
|---|---|
| `print_stats.state` | `standby` |
| `idle_timeout.state` | `Idle` |
| `multi_color_controller.operation.current` | `-1` |
| `multi_color_controller.operation.error` | `None` |
| `last_load_slot` | `slot2` |
| `slot_sync` | `slot2` |
| `filament_slot2` | `18` |
| `color_slot2` | `2` |
| `vendor_slot2` | `0` |

Commands sent through the Moonraker G-code script endpoint:

```gcode
SLOT_RFID_READ SLOT=slot2
INIT_RFID_READ
MULTI_COLOR_READ_RFID SLOT=slot2
```

Moonraker accepted all three commands with `{"result": "ok"}`.

Additional command-helper captures:

| Capture | Command | Result | Saved-variable diff | Status delta |
|---|---|---|---|---|
| `tmp/qidi-box-reversing/runtime-20260507-173405-slot-rfid-read-slot2-helper/` | `SLOT_RFID_READ SLOT=slot2` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-173526-multi-color-read-rfid-slot2-helper/` | `MULTI_COLOR_READ_RFID SLOT=slot2` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-175337-multi-color-read-rfid-slot2-polled-helper/` | `MULTI_COLOR_READ_RFID SLOT=slot2` with `--poll-interval 0.2 --poll-duration 3` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-173646-init-rfid-read-helper/` | `INIT_RFID_READ` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-175150-multi-color-init-rfid-helper/` | `MULTI_COLOR_INIT_RFID` | `ok` | `0` bytes | none |

The helpers recorded `capture-metadata.command_risk=no_motion`, `motion_commands_sent=false`, `state_change_command_sent=false`, `heater_command_sent=false`, and unchanged `status-before.json` / `status-after.json` values for `last_loaded=slot2`, `slot_sync=slot2`, `extrude_state=2`, `operation.current=-1`, and `multi_color_controller.sensors.runout_sensors={"slot0":1,"slot1":1,"slot2":0,"slot3":1}`.

Observed after each command:

- `saved_variables.diff` was empty.
- `filament_slot2` remained `18`.
- `color_slot2` remained `2`.
- `vendor_slot2` remained `0`.
- `multi_color_controller.rfid.reading` was `false` after capture wait.
- `multi_color_controller.rfid.results` was `{}` after capture wait.
- The polled `MULTI_COLOR_READ_RFID SLOT=slot2` helper wrote three intermediate `status-*.json` files; all reported `multi_color_controller.rfid.reading=false` and `multi_color_controller.rfid.results={}`.
- `print_stats.state` remained `standby`.
- `idle_timeout.state` remained `Idle`.
- `multi_color_controller.operation.error` remained `None`.

Interpretation:

- The RFID-facing commands were non-motion in these idle capture windows.
- The commands did not clear existing slot2 metadata when no new visible RFID result was produced.
- No raw `fm17550_read_card_return status/data` payload appeared in the captured log tails.
- The command-helper captures confirm `SLOT_RFID_READ SLOT=slot2`, `MULTI_COLOR_READ_RFID SLOT=slot2`, `INIT_RFID_READ`, and `MULTI_COLOR_INIT_RFID` can be captured with before/after status and saved-variable snapshots while preserving idle state.
- These captures do not prove valid-tag payload format; they only prove no visible saved-variable change and no visible status result for the current slot2/tag state.

## Autofeed command capture 2026-05-07 15:32-15:33

Capture directories:

- `tmp/qidi-box-reversing/runtime-20260507-153214-autofeed-preflight/`
- `tmp/qidi-box-reversing/runtime-20260507-153309-autofeed-query2/`

Preflight status showed:

| Field | Value |
|---|---|
| `print_stats.state` | `standby` |
| `idle_timeout.state` | `Idle` |
| `multi_color_controller.operation.current` | `-1` |
| `multi_color_controller.operation.error` | `None` |
| `last_load_slot` | `slot2` |
| `slot_sync` | `slot2` |
| `multi_color_controller.sensors.pressure_sensor` | `0` |
| `box_autofeed` Moonraker status | `{}` |

Commands sent through the Moonraker G-code script endpoint:

```gcode
MCB_CONFIG SLOT=slot2
MCB_QUERY
SET_LIMIT_A STATE=0
SET_LIMIT_A STATE=1
SET_LIMIT_A STATE=0
```

Moonraker accepted all five commands with `{"result": "ok"}`. The final `SET_LIMIT_A STATE=0` restored the virtual limit state after the `STATE=1` probe.

Observed after the commands:

- `saved_variables.diff` was empty.
- `print_stats.state` remained `standby`.
- `idle_timeout.state` remained `Idle`.
- `multi_color_controller.operation.current` remained `-1`.
- `multi_color_controller.operation.error` remained `None`.
- `multi_color_controller.sensors.pressure_sensor` remained `0`.
- `box_autofeed` still returned `{}` in Moonraker object status.
- No `MCB_STATE`, `MCB_DONE`, or `MCB_ERROR` payload appeared in the captured log tails.

Additional command-helper captures:

| Capture | Command | Risk | Result | Saved-variable diff | Status delta |
|---|---|---|---|---|---|
| `tmp/qidi-box-reversing/runtime-20260507-173819-mcb-query-helper/` | `MCB_QUERY` | `no_motion` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-173939-mcb-config-slot2-helper/` | `MCB_CONFIG SLOT=slot2` | `state_change` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-174109-set-limit-a-state0-helper/` | `SET_LIMIT_A STATE=0` | `state_change` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-174240-set-limit-a-state1-helper/` | `SET_LIMIT_A STATE=1` | `state_change` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-174244-set-limit-a-state0-restore-helper/` | `SET_LIMIT_A STATE=0` restore | `state_change` | `ok` | `0` bytes | none |
| `tmp/qidi-box-reversing/runtime-20260507-174536-mcb-auto-abort-idle-helper/` | `MCB_AUTO_ABORT` | `state_change` | `ok` | `0` bytes | none |

The helpers recorded `motion_commands_sent=false`, `command-response.json.result=ok`, and unchanged `status-before.json` / `status-after.json` values for `last_loaded=slot2`, `slot_sync=slot2`, `extrude_state=2`, `operation.current=-1`, and `multi_color_controller.sensors.pressure_sensor=0`. `MCB_CONFIG SLOT=slot2`, `SET_LIMIT_A STATE=0/1`, and `MCB_AUTO_ABORT` required the explicit `--allow-state-change` gate in `scripts/capture_qidi_box_command.py`. The final limit helper command restored `SET_LIMIT_A STATE=0` after the `STATE=1` probe.

Interpretation:

- `MCB_CONFIG`, `MCB_QUERY`, and `SET_LIMIT_A` were accepted in an idle state without saved-variable changes or visible multi-color operation changes.
- The stock `box_autofeed` object does not publish useful Moonraker status fields in this captured configuration.
- This capture confirms the safe command path but does not recover MCU callback payloads; `MCB_AUTO_START` or a real anti-wrap event is still required for `MCB_STATE`, `MCB_DONE`, and `MCB_ERROR` payloads.

## Next runtime evidence

The lowest-risk next captures remain:

1. RFID capture with a known tagged QIDI spool whose tag location is physically confirmed.
2. `BOX_PRINT_START` no-motion branch only after setting or confirming `enable_box=0` in a controlled idle state.
3. Controlled load/unload/eject captures with physical preflight.
