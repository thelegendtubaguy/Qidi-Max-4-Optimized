# QIDI Box stock config surface

## Source

Captured file:

- `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/printer_data/config/box.cfg`

Generated-object mapping:

- `docs/qidi_box/qidi_box_generated_config_reference.md`

Sensitive runtime serial values are redacted from this reference.

## Active sections

| Section | Role |
|---|---|
| `[box_config box0]` | QIDI Box MCU pin map and generated heater/fan/RFID config inputs |
| `[box_extras]` | QIDI Box button/endstop pins for high-level orchestration |
| `[box_autofeed]` | autofeed / anti-wrap visible tuning inputs |
| `[mcu mcu_box1]` | QIDI Box MCU serial and restart method |
| `[gcode_macro UNLOAD_FILAMENT]` | stock box unload wrapper |
| `[gcode_macro T0]`..`[gcode_macro T15]` | tool-to-slot load wrappers |
| `[gcode_macro UNLOAD_T0]`..`[gcode_macro UNLOAD_T15]` | tool-to-slot unload wrappers |

## `[box_config box0]` slot hardware

| Slot | Runout pin | Step pin | Dir pin | Enable pin | White pin | Red pin |
|---:|---|---|---|---|---|---|
| `0` | `mcu_box1:PA0` | `mcu_box1:PC14` | `mcu_box1:PC13` | `!mcu_box1:PC15` | `mcu_box1:PA1` | `mcu_box1:PA2` |
| `1` | `mcu_box1:PB3` | `mcu_box1:PB9` | `mcu_box1:PB8` | `!mcu_box1:PC0` | `mcu_box1:PB4` | `mcu_box1:PB5` |
| `2` | `mcu_box1:PA13` | `mcu_box1:PC12` | `mcu_box1:PC11` | `!mcu_box1:PD2` | `mcu_box1:PA14` | `mcu_box1:PA15` |
| `3` | `mcu_box1:PA7` | `mcu_box1:PC8` | `mcu_box1:PB2` | `!mcu_box1:PC10` | `mcu_box1:PC4` | `mcu_box1:PC5` |

Stepper shared values:

| Key | Value |
|---|---:|
| `microsteps` | `16` |
| `rotation_distance` | `13.6` |
| `step_pulse_duration` | `0.000000100` |

## `[box_config box0]` heater and temperature hardware

| Key | Value |
|---|---|
| `heater_pin_heater_generic` | `mcu_box1:PA3` |
| `sensor_type_heater_generic` | `AHT20_F` |
| `i2c_bus_heater_generic` | `i2c3` |
| `i2c_mcu_heater_generic` | `mcu_box1` |
| `i2c_address_heater_generic` | `56` |
| `control_heater_generic` | `pid` |
| `pid_Kp_heater_generic` | `63.418` |
| `pid_Ki_heater_generic` | `1.342` |
| `pid_Kd_heater_generic` | `749.125` |
| `min_temp_heater_generic` | `-100` |
| `max_temp_heater_generic` | `100` |
| `target_max_temp_heater_generic` | `90` |
| `max_error_verify_heater` | `400` |
| `check_gain_time_verify_heater` | `600` |
| `is_box_heater_verify_heater` | `True` |

Additional temperature sensors:

| Sensor | Type | Pin | Min temp | Max temp |
|---|---|---|---:|---:|
| `temperature_sensor_0` | `NTC 100K MGB18-104F39050L32` | `mcu_box1:PC1` | `-100` | `130` |
| `temperature_sensor_1` | `NTC 100K MGB18-104F39050L32` | `mcu_box1:PC2` | `-100` | `130` |

## `[box_config box0]` fans and RFID

| Component | Key/value |
|---|---|
| Heater fan 0 pin | `mcu_box1:PA4` |
| Heater fan 0 heater | `heater_box1` |
| Heater fan 0 threshold | `35` |
| Heater fan 0 idle timeout | `60` |
| Heater fan 1 pin | `mcu_box1:PA5` |
| Heater fan 1 heater | `heater_box1` |
| Heater fan 1 threshold | `35` |
| Heater fan 1 idle timeout | `60` |
| Controller fan pin | `mcu_box1:PA6` |
| Controller fan heater | `heater_box1` |
| Controller fan steppers | `slot0, slot1, slot2, slot3` |
| RFID CS 0 | `mcu_box1:PC6` |
| RFID CS 1 | `mcu_box1:PC7` |

## `[box_extras]`

| Key | Value |
|---|---|
| `b_button_pin` | `^mcu_box1:PB1` |
| `b_endstop_pin` | `mcu_box1:PA9` |
| `e_endstop_pin` | `mcu_box1:PA10` |

## `[box_autofeed]`

| Key | Value |
|---|---:|
| `limit_pin` | `^!mcu_box1:PB0` |
| `v_feed` | `100` |
| `lmax` | `120` |
| `dir` | `0` |

Additional `box_autofeed.so` defaults not present in stock config are documented in `docs/qidi_box/qidi_box_autofeed_reference.md`.

## `[mcu mcu_box1]`

| Key | Value |
|---|---|
| `serial` | `<redacted>` |
| `restart_method` | `command` |

## Tool wrappers

`T0` through `T15` resolve a saved-variable slot and call `EXTRUDER_LOAD` when `enable_box == 1`:

```gcode
{% set slot = printer.save_variables.variables.value_tN|default('slotN') %}
{% if printer.save_variables.variables.enable_box == 1 %}
EXTRUDER_LOAD SLOT={slot}
{% endif %}
```

`UNLOAD_T0` through `UNLOAD_T15` resolve the same saved-variable slot and call `EXTRUDER_UNLOAD` when `enable_box == 1`:

```gcode
{% set slot = printer.save_variables.variables.value_tN|default('slotN') %}
{% if printer.save_variables.variables.enable_box == 1 %}
EXTRUDER_UNLOAD SLOT={slot}
{% endif %}
```

## `UNLOAD_FILAMENT`

Stock wrapper sequence when `enable_box == 1`:

```gcode
{% set T = params.T|int %}
CUT_FILAMENT T={T}
MOVE_TO_TRASH
UNLOAD_T{T}
G1 E25 F300
M104 S0
CLEAR_OOZE
CLEAR_FLUSH
```
