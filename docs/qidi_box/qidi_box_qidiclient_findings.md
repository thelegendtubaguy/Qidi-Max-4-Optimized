# QIDI Client QIDI Box findings

## Source

- Captured binary: `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/QIDI_Client/bin/qidiclient`.
- Strings file: `tmp/qidi-box-reversing/20260507-135653-printer-capture/analysis/strings/qidiclient.strings.txt`.

## Moonraker/Klipper integration

`qidiclient` strings reference:

- `org.qidi.moonraker`
- `/org/qidi/moonraker`
- `org.qidi.klipper`
- `/org/qidi/klipper`
- `/printer/objects/query`
- `Initial klipper state: {}`
- `Updated klipper state: {}`
- `Failed to parse klipper state from response`

`qidiclient` subscribes to or queries these box-related objects:

- `save_variables`
- `box_extras`
- `aht20_f heater_box`
- `box_stepper slot`
- `heater_generic heater_box`
- `temperature_sensor heater_temp_a_box1`
- `temperature_sensor heater_temp_b_box1`
- `multi_color_controller`

These object names match the Moonraker status capture in `docs/qidi_box/qidi_box_runtime_observations.md`.

## Embedded box config template

`qidiclient` contains a template for generating box config sections:

- `[box_extras]`
- `[box_config box{B}]`
- `[box_autofeed]`


- slot 0 pins: `PA0`, `PC14`, `PC13`, `PC15`, `PA1`, `PA2`
- slot 1 pins: `PB3`, `PB9`, `PB8`, `PC0`, `PB4`, `PB5`
- slot 2 pins: `PA13`, `PC12`, `PC11`, `PD2`, `PA14`, `PA15`
- slot 3 pins: `PA7`, `PC8`, `PB2`, `PC10`, `PC4`, `PC5`
- `microsteps: 16`
- `rotation_distance: 13.6`
- `step_pulse_duration:0.000000100`
- heater pin `PA3`
- AHT20/I2C path on `i2c3`
- temperature pins `PC1` and `PC2`
- heater fan pins `PA4` and `PA5`
- controller fan pin `PA6`
- RFID chip-select pins `PC6` and `PC7`

The template also includes placeholders:

- `{B}` for box index
- `{M}` for MCU index/name suffix
- `{SLOTS}` for controller fan stepper list

## Box detection and firmware update strings

`qidiclient` searches for box devices through patterns including:

- `/dev/serial/by-id/usb-Klipper_QIDI_BOX_*`
- `/dev/serial/by-id/usb-Klipper_QIDI_MAX4-BOX-*`

Firmware/update strings reference:

- `BOX_V1`
- `BOX_V2`
- `QIDI_BOX_`
- `Update requirements - ClosedLoop: {}, SOC: {}, THR: {}, MCU: {}, BOX: {}`
- `BOX missing`
- `Update BOX firmware`
- `/home/qidi/klipper_BOX.bin`

`qidiclient` therefore participates in box config generation/detection and firmware update orchestration, but these strings do not show it owning the physical load/unload motion path.

## Client-side G-code templates

`qidiclient` contains strings for these box-related G-code commands:

- `DISABLE_BOX_DRY BOX=`
- `RFID_READ SLOT=slot`
- `SAVE_VARIABLE VARIABLE=enable_box VALUE=`
- `SET_FILAMENT_DRY END_TIME=0 BED_TEMP=0 CHAMBER_TEMP=0`
- `ENABLE_BOX_DRY BOX= TEMP=`
- `SET_FILAMENT_DRY END_TIME= BED_TEMP= CHAMBER_TEMP=`
- `SAVE_VARIABLE VARIABLE=vendor_slot VALUE=`
- `SAVE_VARIABLE VARIABLE=filament_slot VALUE=`
- `SAVE_VARIABLE VARIABLE=color_slot VALUE=`
- `SAVE_VARIABLE VARIABLE=value_t VALUE='...'`
- `SET_HEATER_TEMPERATURE HEATER=heater_box TARGET=`
- `MULTI_COLOR_LOAD SLOT=slot`
- `MULTI_COLOR_BOX_UNLOAD SLOT=slot`
- `MULTI_COLOR_UNLOAD SLOT=slot`

The client uses `MULTI_COLOR_*` commands for UI flows; `multi_color_controller.LocalAdapter` maps these to local vendor commands. The client does not need direct access to `box_stepper.so` internals.

## UI/state strings

`qidiclient` contains UI/state strings including:

- `box_count`
- `box_heater_update_task`
- `box_drying`
- `box_heater_info`
- `box_extras_info`
- `box_count_update_task`
- `box_options`
- `BOX_automatic_refill`
- `BOX_automatic_refill_content`
- `color_slot_info`
- `filament_slot_info`
- `box_stepper_info`
- `last_load_slot`
- `box_temperature`
- `box_button_state`
- `box_operate_state`
- `box_drying_state`
- `vendor_slot_info`
- `enable_box`
- `box_min_temp`
- `box_max_temp`
- `slot_sync`
- `value_t0` through `value_t15`
- `filament_slot0` through `filament_slot16`
- `color_slot0` through `color_slot16`
- `vendor_slot0` through `vendor_slot16`

These strings match the state exposed by `save_variables`, `box_extras`, `box_stepper slotN`, and `multi_color_controller`.

## Material database

`qidiclient` references:

- `/home/qidi/printer_data/config/officiall_filas_list.cfg`

This matches the material/color/vendor lookup flow documented in `docs/qidi_box/box_print_start_notes.md` and `docs/qidi_box/qidi_box_compiled_module_reference.md`.
