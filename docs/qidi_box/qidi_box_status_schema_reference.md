# QIDI Box status schema reference

## Source

Runtime captures:

- `tmp/qidi-box-reversing/runtime-20260507-145246-status/box-objects-query.json`
- `tmp/qidi-box-reversing/runtime-20260507-153309-autofeed-query2/status-after.json`
- `tmp/qidi-box-reversing/runtime-20260507-163127-current-nonmotion/status-summary.tsv`
- `tmp/qidi-box-reversing/runtime-20260507-164102-box-stepper-status/status.json`

Related references:

- `docs/qidi_box/qidi_box_runtime_observations.md`
- `docs/qidi_box/qidi_box_task_queue_flow_reference.md`
- `docs/qidi_box/qidi_box_qidiclient_findings.md`

## Moonraker object names

Captured QIDI Box-related objects:

```text
box_extras
multi_color_controller
save_variables
filament_switch_sensor filament_switch_sensor
box_stepper slot0
box_stepper slot1
box_stepper slot2
box_stepper slot3
heater_generic heater_box1
temperature_sensor heater_temp_a_box1
temperature_sensor heater_temp_b_box1
```

`box_autofeed` was queried in later captures and returned `{}`, but `tmp/qidi-box-reversing/runtime-20260507-163831-current-box-sensors/objects-list.json` did not list `box_autofeed` as a Moonraker object.

`box_rfid card_reader_N` objects were not present in the captured Moonraker object lists even though `box_config.py` creates reader objects internally.

## `box_extras` status

Captured keys:

| Path | Captured value / shape |
|---|---|
| `box_button_state` | `0` |
| `b_endstop_state` | `0` |
| `e_endstop_state` | `1` |
| `box_operate_state` | `0` |
| `box_drying_state.box1.dry_state` | `0` |
| `box_drying_state.box1.end_time` | `0` |
| `is_tool_change` | `0` |



## `box_stepper slotN` status

Captured keys:

| Object | `runout_button` | `rfid_state` |
|---|---:|---:|
| `box_stepper slot0` | `1` | `0` |
| `box_stepper slot1` | `1` | `0` |
| `box_stepper slot2` | `0` | `0` |
| `box_stepper slot3` | `1` | `0` |

`slot2` was the loaded/synced slot during the capture. This confirms the active pre-gate/runout polarity observed elsewhere: loaded slot2 reports `runout_button=0`; empty visible slots report `runout_button=1`.


- `rfid_state` was `0` for all visible physical slots during capture.

## `multi_color_controller` status top-level keys

Captured shape:

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

## `multi_color_controller.system`

| Key | Captured value |
|---|---|
| `ready` | `true` |
| `mode` | `local` |



## `multi_color_controller.hardware`

| Key | Captured value |
|---|---:|
| `box_count` | `1` |
| `connected` | `true` |



## `multi_color_controller.slots`

Captured shape:

```text
states: slot0..slot15 -> integer BoxState
materials: slot0..slot16 -> filament/color/vendor resolved metadata
last_loaded: slot name
```

Captured state values:

| Slot | State |
|---|---:|
| `slot0` | `0` / `EMPTY` |
| `slot1` | `0` / `EMPTY` |
| `slot2` | `2` / `IN_EXTRUDER` |
| `slot3` | `0` / `EMPTY` |
| `slot4`..`slot15` | `0` / `EMPTY` |

Captured `last_loaded`:

```text
slot2
```

Captured material object shape:

```json
{
  "filament": {
    "filament": "ASA",
    "min_temp": "240",
    "max_temp": "280",
    "box_min_temp": "0",
    "box_max_temp": "45",
    "type": "ASA"
  },
  "color": "#060606",
  "vendor": "Generic"
}
```


- Slot state integers should use `BoxState` values from `docs/qidi_box/qidi_box_task_queue_flow_reference.md` when preserving QIDI UI semantics.
- Material metadata should resolve through the saved-variable IDs documented in `docs/qidi_box/qidi_box_material_metadata_reference.md`.
- `slot16` appears in `materials` but not in `states`; it is a direct-feed metadata sentinel, not a physical box slot state.

## `multi_color_controller.extruder`

| Key | Captured value |
|---|---|
| `loaded` | `true` |
| `target` | `0.0` |
| `filament_detected` | `true` |


- `filament_detected` should mirror the toolhead/extruder filament sensor.
- `target` tracked current hotend target in the captured idle state.

## `multi_color_controller.operation`

Captured shape:

| Key | Captured value |
|---|---|
| `current` | `-1` |
| `progress` | `0` |
| `error` | `null` |
| `box_button_state` | `0` |
| `operate_state` | `0` |
| `steps` | `[]` |
| `is_waiting_user` | `false` |


- Live task-queue captures are required before exact in-operation `current`, `progress`, and `steps` semantics can be duplicated.

## `multi_color_controller.print`

| Key | Captured value |
|---|---|
| `printing` | `false` |
| `current_tool` | `-1` |
| `next_tool` | `-1` |



## `multi_color_controller.rfid`

| Key | Captured value |
|---|---|
| `reading` | `false` |
| `results` | `{}` |

Runtime RFID command captures in `docs/qidi_box/qidi_box_runtime_observations.md` also ended with `reading=false` and `results={}`.


- Successful-tag result shape remains unresolved.

## `multi_color_controller.drying`

Captured shape:

```text
box1.dry_state = 0
box1.end_time = 0
```

The 2026-05-07 16:31 non-motion refresh still reported `box1.dry_state=0` and `box1.end_time=0` while `heater_generic heater_box1.target=45.0` and `temperature=45.01`.


- `multi_color_controller.drying.box1.dry_state=0` does not prove the physical box heater target is `0`; query `heater_generic heater_box1.target` when heater state matters.
- Material `box_max_temp` limits are documented in `docs/qidi_box/qidi_box_material_metadata_reference.md`.

## `multi_color_controller.sensors`

Captured shape:

| Path | Captured value |
|---|---:|
| `b_endstop` | `0` |
| `e_endstop` | `1` |
| `runout_sensors.slot0` | `1` |
| `runout_sensors.slot1` | `1` |
| `runout_sensors.slot2` | `0` |
| `runout_sensors.slot3` | `1` |
| `pressure_sensor` | `0` |


- `pressure_sensor` is the visible status field related to the autofeed/anti-wrap path; idle captures kept it at `0`.

## `multi_color_controller.config`

Captured `config` mirrors many saved variables, including:

```text
enable_box
auto_reload_detect
auto_read_rfid
auto_init_detect
box_count
extrude_state
last_load_slot
slot_sync
load_retry_num
retry_step
slot0..slot15
value_t0..value_t15
filament_slot0..filament_slot16
color_slot0..color_slot16
vendor_slot0..vendor_slot16
runout_0..runout_15
retained_slot
retained_tool
retained_tool_ready
retained_filament_id
retained_vendor_id
is_tool_change
was_interrupted
```




## `multi_color_controller.config_summary`

Captured shape:

| Key | Captured value |
|---|---|
| `enable_box` | `1` |
| `auto_reload_detect` | `1` |
| `auto_read_rfid` | `1` |
| `auto_init_detect` | `0` |
| `slot_sync` | `slot2` |
| `retry_step` | `None` |
| `load_retry_num` | `0` |



## `save_variables` object shape

Captured `save_variables` status includes a top-level `variables` dict and also individual saved-variable keys duplicated at the top level.


- Docs should reference saved-variable names, not rely on the duplicated top-level Moonraker shape.

## Heater and temperature status

Captured shapes:

```text
heater_generic heater_box1:
  temperature
  target
  power

temperature_sensor heater_temp_a_box1:
  temperature
  measured_min_temp
  measured_max_temp

temperature_sensor heater_temp_b_box1:
  temperature
  measured_min_temp
  measured_max_temp
```



## `mcu mcu_box1` status

Captured in `tmp/qidi-box-reversing/runtime-20260507-164102-box-stepper-status/status.json`:

| Path | Captured value |
|---|---|
| `mcu_version` | `02.03.01.21` |
| `mcu_constants.MCU` | `stm32f401xc` |
| `mcu_constants.CLOCK_FREQ` | `84000000` |
| `mcu_constants.STEPPER_BOTH_EDGE` | `1` |
| `last_stats.bytes_invalid` | `0` |
| `last_stats.bytes_retransmit` | `9` |
