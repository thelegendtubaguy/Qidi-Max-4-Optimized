# QIDI Box recovered constants

## Module constants

Source: `tmp/qidi-box-reversing/module_introspection_summary.md`.

| Module | Constant | Value |
|---|---|---:|
| `box_stepper.so` | `DISABLE_DELAY` | `0.05` |
| `box_stepper.so` | `HOMING_START_DELAY` | `0.001` |
| `box_stepper.so` | `ENDSTOP_SAMPLE_COUNT` | `4` |
| `box_stepper.so` | `ENDSTOP_SAMPLE_TIME` | `0.000015` |

## Stock slot stepper hardware

Source: `docs/qidi_box/qidi_box_stock_config_surface.md`.

| Slot | Step pin | Dir pin | Enable pin | Runout/pre-gate pin | White pin | Red pin |
|---:|---|---|---|---|---|---|
| `0` | `mcu_box1:PC14` | `mcu_box1:PC13` | `!mcu_box1:PC15` | `mcu_box1:PA0` | `mcu_box1:PA1` | `mcu_box1:PA2` |
| `1` | `mcu_box1:PB9` | `mcu_box1:PB8` | `!mcu_box1:PC0` | `mcu_box1:PB3` | `mcu_box1:PB4` | `mcu_box1:PB5` |
| `2` | `mcu_box1:PC12` | `mcu_box1:PC11` | `!mcu_box1:PD2` | `mcu_box1:PA13` | `mcu_box1:PA14` | `mcu_box1:PA15` |
| `3` | `mcu_box1:PC8` | `mcu_box1:PB2` | `!mcu_box1:PC10` | `mcu_box1:PA7` | `mcu_box1:PC4` | `mcu_box1:PC5` |

Shared stepper values:

| Key | Value |
|---|---:|
| `rotation_distance` | `13.6` |
| `microsteps` | `16` |
| `step_pulse_duration` | `0.000000100` |

## Recovered motion defaults

Sources: `docs/qidi_box/qidi_box_stepper_branch_matrix.md`, `docs/qidi_box/qidi_box_stepper_state_methods_reference.md`.

| Config key / phase | Stock owner | Value |
|---|---|---:|
| `preload_homing_distance` | `slot_load()` | `3000` |
| `preload_homing_speed` | `slot_load()` | `80` |
| `preload_homing_accel` | `slot_load()` | `50` |
| `preload_parking_distance` | `slot_load()` | `-260` |
| `preload_parking_speed` | `slot_load()` | `80` |
| `preload_parking_accel` | `slot_load()` | `50` |
| `slot_unload_distance` | `cmd_SLOT_UNLOAD()` | `-3000` |
| `slot_unload_speed` | `cmd_SLOT_UNLOAD()` | `100` |
| `slot_unload_accel` | `cmd_SLOT_UNLOAD()` | `50` |
| `load_homing_distance` | `cmd_EXTRUDER_LOAD()` | `3000` |
| `load_homing_speed` | `cmd_EXTRUDER_LOAD()` | `85` |
| `load_homing_accel` | `cmd_EXTRUDER_LOAD()` | `50` |
| `post_load_dwell` | `cmd_EXTRUDER_LOAD()` | `0.05` |
| `unload_phase1_distance` | `cmd_EXTRUDER_UNLOAD()` | `-350` |
| `unload_phase1_speed` | `cmd_EXTRUDER_UNLOAD()` | `65` |
| `unload_phase2_distance` | `cmd_EXTRUDER_UNLOAD()` | `-1150` |
| `unload_phase2_speed` | `cmd_EXTRUDER_UNLOAD()` | `85` |
| `unload_phase_accel` | `cmd_EXTRUDER_UNLOAD()` | `100` |
| `unload_recovery_distance` | `cmd_EXTRUDER_UNLOAD()` | `-1500` |
| `unload_recovery_repeats` | `cmd_EXTRUDER_UNLOAD()` | `2` |
| `unload_recovery_speed` | `cmd_EXTRUDER_UNLOAD()` | `65` |
| `unload_recovery_accel` | `cmd_EXTRUDER_UNLOAD()` | `50` |
| `hub_load_length` | `slot_sync()` lookup | `18` |
| `hub_load_v` | `slot_sync()` lookup | `40` |
| `hub_load_a` | `slot_sync()` lookup | `40` |

## `BOX_PRINT_START` setup writes

Source: `docs/qidi_box/qidi_box_extras_orchestration_reference.md`.

| Saved variable | Value |
|---|---:|
| `load_retry_num` | `0` |
| `retry_step` | `None` |
| `runout_0`..`runout_15` | `0` |
| `extrude_state` | `-1` |

## Runtime state constants

Source: `docs/qidi_box/qidi_box_runtime_observations.md`.

| Name | Value |
|---|---:|
| `BoxState.EMPTY` | `0` |
| `BoxState.LOADED` | `1` |
| `BoxState.IN_EXTRUDER` | `2` |
| `BoxState.IN_FEEDER` | `3` |
| `BoxState.ERROR` | `-1` |
| `BoxState.UNKNOWN` | `-2` |
| `BoxState.PENDING` | `-3` |

Runtime-confirmed state:

```text
extrude_state = 2
slot2 = 2
last_load_slot = slot2
slot_sync = slot2
```

## Stock metadata IDs observed at runtime

Sources: `docs/qidi_box/qidi_box_material_metadata_reference.md`, `docs/qidi_box/qidi_box_runtime_observations.md`.

| Variable | Value | Meaning |
|---|---:|---|
| `filament_slot2` | `18` | ASA |
| `color_slot2` | `2` | `#060606` |
| `vendor_slot2` | `0` | Generic |

## Box heater and dryer hardware values

Source: `docs/qidi_box/qidi_box_stock_config_surface.md`.

| Key | Value |
|---|---|
| `heater_pin_heater_generic` | `mcu_box1:PA3` |
| `sensor_type_heater_generic` | `AHT20_F` |
| `i2c_bus_heater_generic` | `i2c3` |
| `i2c_address_heater_generic` | `56` |
| `pid_Kp_heater_generic` | `63.418` |
| `pid_Ki_heater_generic` | `1.342` |
| `pid_Kd_heater_generic` | `749.125` |
| `target_max_temp_heater_generic` | `90` |
| `heater_temp_box_heater_fan_0` | `35` |
| `idle_timeout_box_heater_fan_0` | `60` |
| `heater_temp_box_heater_fan_1` | `35` |
| `idle_timeout_box_heater_fan_1` | `60` |

## RFID constants

Sources: `docs/qidi_box/qidi_box_rfid_reference.md`, `docs/qidi_box/qidi_box_stock_config_surface.md`.

| Key | Value |
|---|---|
| `cs_pin_box_rfid_0` | `mcu_box1:PC6` |
| `cs_pin_box_rfid_1` | `mcu_box1:PC7` |
| `max_read_time` | `30.0` |
| `get_message_count` | `1` |
| `query_fm17550 rest_ticks` | `0` |
| `query_fm17550 on_restart` | `True` |
| response format | `fm17550_read_card_return oid=%c status=%c data=%*s` |

## Autofeed constants

Source: `docs/qidi_box/qidi_box_autofeed_reference.md`.

| Key | Stock/harness value |
|---|---:|
| `limit_pin` | `^!mcu_box1:PB0` |
| `debounce_us` | `200000.0` |
| `limit_polarity` | `0` |
| `default_ticks` | `8400` |
| `v_feed` | `100` |
| `lmax` | `120` |
| `dir` | `0` |
| `a_feed` | `0.0` |
| encoded `PC15` enable pin | `47` |
| encoded enable invert | `1` |

## Macro-equivalent G-code constants

Source: `docs/qidi_box/qidi_box_extras_orchestration_reference.md`.

`CLEAR_FLUSH`:

```gcode
M204 S10000
G1 X180 F10000
MOVE_TO_TRASH
```

`CLEAR_OOZE`:

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

`flush_all_filament()`:

```gcode
G1 E25 F300
```
