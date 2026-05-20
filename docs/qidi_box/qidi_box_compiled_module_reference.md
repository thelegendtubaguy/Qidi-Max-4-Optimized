# QIDI Box compiled-module reference

## Evidence sources

- Captured binaries: `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/klipper/klippy/extras/`.
- Introspection output: `tmp/qidi-box-reversing/module_introspection_summary.md`.
- Harness outputs: `tmp/qidi-box-reversing/box_stepper_probe_output.json`, `box_stepper_state_methods_probe.json`, `box_autofeed_probe.json`, `box_autofeed_methods_probe.json`, `box_rfid_probe.json`, `box_extras_methods_probe.json`, `multi_color_adapter_probe.json`, `remote_adapter_probe.json`.
- Symbol map: `docs/qidi_box/qidi_box_compiled_symbol_map.md`.
- Static disassembly notes: `docs/qidi_box/qidi_box_static_disassembly_notes.md`.
- Task queue flow reference: `docs/qidi_box/qidi_box_task_queue_flow_reference.md`.
- Stepper branch matrix: `docs/qidi_box/qidi_box_stepper_branch_matrix.md`.
- Stepper state-method reference: `docs/qidi_box/qidi_box_stepper_state_methods_reference.md`.
- Autofeed reference: `docs/qidi_box/qidi_box_autofeed_reference.md`.
- RFID reference: `docs/qidi_box/qidi_box_rfid_reference.md`.
- Box extras orchestration reference: `docs/qidi_box/qidi_box_extras_orchestration_reference.md`.
- Box detection reference: `docs/qidi_box/qidi_box_detect_reference.md`.
- Remote adapter reference: `docs/qidi_box/qidi_box_remote_adapter_reference.md`.
- Error code reference: `docs/qidi_box/qidi_box_error_code_reference.md`.
- Runtime observations: `docs/qidi_box/qidi_box_runtime_observations.md`.
- Runtime config capture: `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/printer_data/config/`.
- Generated config reference: `docs/qidi_box/qidi_box_generated_config_reference.md`.

## Module formats

- `box_autofeed.so`: ELF 64-bit LSB shared object, ARM aarch64, dynamically linked, debug info present, not stripped.
- `box_detect.so`: ELF 64-bit LSB shared object, ARM aarch64, dynamically linked, debug info present, not stripped.
- `box_extras.so`: ELF 64-bit LSB shared object, ARM aarch64, dynamically linked, debug info present, not stripped.
- `box_rfid.so`: ELF 64-bit LSB shared object, ARM aarch64, dynamically linked, debug info present, not stripped.
- `box_stepper.so`: ELF 64-bit LSB shared object, ARM aarch64, dynamically linked, debug info present, not stripped.
- `multi_color_controller.so`: ELF 64-bit LSB shared object, ARM aarch64, dynamically linked, debug info present, not stripped.

## `box_stepper.so`

### Constants

- `DISABLE_DELAY = 0.05`
- `HOMING_START_DELAY = 0.001`
- `ENDSTOP_SAMPLE_COUNT = 4`
- `ENDSTOP_SAMPLE_TIME = 0.000015`

### Class `BoxExtruderStepper`

- `__init__(self, config, print_config, slot_num)`
- `get_stepper_enable_pin(self)`
- `cmd_DIS_STEP(self, gcmd)`
- `runout_button_callback(self, eventtime, state)`
- `get_status(self, eventtime=None)`
- `sync_print_time(self)`
- `do_move(self, movepos, speed, accel=50)`
- `do_move_double_steps(self, v1, l1, v2, l2, accel)`
- `do_move_triple_steps(self, v1, l1, v2, l2, v3, l3, accel)`
- `dwell(self, delay)`
- `drip_move(self, newpos, speed, accel, drip_completion)`
- `disable_stepper(self)`
- `_calc_endstop_rate(self, mcu_endstop, movepos, speed)`
- `multi_complete(self, completions)`
- `do_home(self, endstops, movepos, speed, accel, triggered)`
- `do_home_double_steps(self, endstops, l1, l2, v1, v2, accel, triggered)`
- `do_home_three_steps(self, endstops, l1, l2, l3, v1, v2, v3, accel, triggered)`
- `get_mcu_endstops(self)`
- `slot_load(self)`
- `cmd_SLOT_UNLOAD(self, gcmd)`
- `cmd_EXTRUDER_LOAD(self, gcmd)`
- `cmd_EXTRUDER_UNLOAD(self, gcmd, need_output_state=False)`
- `cmd_SLOT_PROMPT_MOVE(self, gcmd)`
- `slot_sync(self, value, sync_to_extruder=False)`
- `init_slot_sync(self)`
- `sync_unbind_extruder(self)`
- `flush_all_filament(self)`
- `switch_next_slot(self)`
- `cmd_SLOT_RFID_READ(self, gcmd)`
- `set_led(self, eventtime)`
- `led_handle_connect(self)`

### Hardcoded motion fragments

- `slot_load()` branch: `do_home(..., 3000, 80, 50, False)`, `do_move(-260, 80, 50)`, `disable_stepper()`.
- `cmd_SLOT_UNLOAD SLOT=slot0`: `do_home(..., -3000, 100, 50, True)`, `disable_stepper()`.
- `cmd_EXTRUDER_LOAD SLOT=slot0`: `do_home(..., 3000, 85, 50, False)`, `disable_stepper()`, `dwell(0.05)`, `sync_print_time()`.
- `cmd_EXTRUDER_UNLOAD SLOT=slot0`: `do_home_double_steps(..., -350, -1150, 65, 85, 100, True)`, `do_home(..., -1500, 65, 50, True)` twice, `disable_stepper()`.

### State-method fragments

- `slot_sync()` fake harness writes the owning stepper object's physical slot name to `slot_sync`.
- `slot_sync(..., sync_to_extruder=False)` looks up `hub_load_length=18`, `hub_load_v=40`, and `hub_load_a=40` before saving `slot_sync`.
- `flush_all_filament()` emits `G1 E25 F300` and calls `disable_stepper()`.
- `cmd_SLOT_RFID_READ()` fake harness logged `QDE_004_011` while loaded, but live runtime RFID commands were accepted without that log line; runtime evidence is stronger for that branch.

### Motion ownership

`box_stepper.so` owns the movement distances, speeds, accelerations, sync, homing, and retry behavior for QIDI `EXTRUDER_LOAD` / `EXTRUDER_UNLOAD`.

## `box_extras.so`

### Classes

- `BoxButton.__init__(self, config, pin, bc)`
- `BoxEndstop.__init__(self, config, name, pin, reuse=False)`
- `BoxEndstop.add_stepper(self, stepper)`
- `BoxEndstop.get_endstops(self)`
- `BoxEndstop.set_scram(self, value)`
- `BoxOutput.__init__(self, config, pin)`
- `BoxOutput.set_pin(self, value)`
- `ToolChange.__init__(self, config)`
- `ToolChange.cmd_TOOL_CHANGE_START(self, gcmd)`
- `ToolChange.cmd_TOOL_CHANGE_END(self, gcmd)`
- `ToolChange.cmd_CLEAR_TOOLCHANGE_STATE(self, gcmd)`
- `ToolChange.move(self, newpos, speed)`
- `ToolChange.get_position(self)`

### Class `BoxExtras`

- `__init__(self, config)`
- `init_probe_data(self)`
- `_init_probe_data_advance(self, eventtime)`
- `auto_detect_filament(self)`
- `auto_detect_filament_advance(self)`
- `detect_filament_loaded(self)`
- `b_button_callback(self, eventtime, state)`
- `handle_connect(self)`
- `delayed_init_error_raw(self, eventtime)`
- `update_b_endstop(self, eventtime)`
- `update_e_endstop(self, eventtime)`
- `cmd_RELOAD_ALL(self, gcmd)`
- `cmd_CLEAR_FLUSH(self, gcmd)`
- `cmd_CLEAR_OOZE(self, gcmd)`
- `cmd_CUT_FILAMENT(self, gcmd)`
- `cmd_AUTO_RELOAD_FILAMENT(self, gcmd)`
- `cmd_RETRY(self, gcmd)`
- `button_extruder_load(self, gcmd)`
- `button_extruder_unload(self, gcmd, steppername='16', from_box_unload=False)`
- `button_box_unload(self, gcmd)`
- `cmd_RUN_STEPPER(self, gcmd)`
- `cmd_ENABLE_BOX_DRY(self, gcmd)`
- `cmd_DISABLE_BOX_DRY(self, gcmd)`
- `cmd_INIT_BOX_STATE(self, gcmd)`
- `cmd_INIT_RFID_READ(self, gcmd)`
- `set_box_temp(self, gcmd)`
- `get_probe_mv(self)`
- `get_status(self, eventtime=None)`
- `save_variable(self, varname, value)`
- `get_value_by_key(self, varname, default_value=0)`
- `get_key_by_value(self, value, default=None, keyword=None)`
- `get_temp_by_num(self, num)`
- `get_temp_by_slot(self, slot)`
- `cmd_TRY_RESUME_PRINT(self, gcmd)`
- `cmd_BOX_PRINT_START(self, gcmd)`
- `cmd_RESUME_PRINT_1(self, gcmd)`
- `cmd_INIT_MAPPING_VALUE(self, gcmd)`
- `get_load_length_by_slot(self, slot)`
- `cmd_disable_box_heater(self, gcmd)`
- `add_data(self, data, new_value)`
- `search_index_by_value(self, value)`
- `_read_wei_timer(self, eventtime)`
- `get_box_temp_by_slot(self, slot)`
- `heating_handler(self, eventtime, box_num, start_time, end_time)`
- `_create_drying_state_setter(self)`
- `cmd_CLEAR_RUNOUT_NUM(self, gcmd)`
- `print_sensor_state_to_log(self, error_msg, eventtime=None)`

### Script fragments

- `CLEAR_FLUSH`: `M204 S10000`, `G1 X180 F10000`, `MOVE_TO_TRASH`.
- `CLEAR_OOZE`: `M204 S10000` followed by `G1 X163 F8000`, `G1 X145 F5000`, `G1 X163 F8000`, `G1 X145 F5000`, `G1 X175 F6000`, then repeated `G1 X163` / `G1 X175` moves.
- `BOX_PRINT_START` initialization: `CLEAR_TOOLCHANGE_STATE`, `load_retry_num = 0`, `retry_step = None`, `runout_0`..`runout_15 = 0`, `extrude_state = -1`.
- `BOX_PRINT_START` load branch: `MOVE_TO_TRASH`, `M109 S<temp>`, `EXTRUDER_LOAD SLOT=<target>`.
- `BOX_PRINT_START` unload branch: `MOVE_TO_TRASH`, `M109 S<temp>`, `M400`, `EXTRUDER_UNLOAD SLOT=<unload_slot>`.

## `box_autofeed.so`

### Class `PinSpec`

- `PinSpec(chip: str, index: int, invert: int, pullup: int, opendrain: int, port: str, pin: int)`

### Function

- `parse_pin_desc(pin_desc, pins_per_port=16)` converts pin strings into `PinSpec`.

### Class `MCBAutoFeed`

- `__init__(self, config)`
- `_precreate_devs_from_printer_objects(self)`
- `_iter_box_stepper_objects(self)`
- `_query_limit_retry(self, tries=3, interval=0.1)`
- `_on_ready(self)`
- `_mcu_name(self, mcu)`
- `_create_dev_for_mcu(self, mcu)`
- `_get_dev_for_mcu(self, mcu)`
- `_build_config_for_dev(self, dev)`
- `_get_slot_stepper(self, slot)`
- `_get_stepper_mcu_and_enable(self, bs)`
- `_select_slot(self, slot)`
- `_normalize_limit_state(self, raw_state)`
- `_sync_limit_to_active_dev(self)`
- `limit_a_event(self, eventtime, state)`
- `cmd_config(self, gcmd)`
- `cmd_query(self, gcmd)`
- `cmd_SET_LIMIT_A(self, gcmd)`
- `_get_slot_enable_pin_params(self, gcmd)`
- `qd_get_slot_enable_pin_params(self, sync_stepper)`
- `cmd_auto_start(self, gcmd)`
- `auto_start(self, v_mm_s, a_mm_s2, lmax_mm, dir, sync_stepper)`
- `cmd_auto_abort(self, gcmd)`
- `auto_abort(self)`
- `init_auto_abort(self)`
- `_on_state(self, params)`
- `_on_done(self, params)`
- `_on_error(self, params)`
- `wrapping_operate(self)`
- `wrapping_detection(self, state)`

### Config and runtime fields

- Config keys: `limit_pin`, `debounce_us`, `limit_polarity`, `default_ticks`, `v_feed`, `lmax`, `dir`, `a_feed`.
- Runtime fields: `a_pin`, `debounce_us`, `limit_polarity`, `default_ticks`, `v_feed`, `lmax`, `dir`, `a_feed`, `limit_a_state`, `wrapping_num`, `bind_stepper`, `active_slot`, `_last_limit_a_event_time`, `_dev_by_mcu`, `_slot_mcu_cache`, `stepper_dev`, `irq_btn`.

### MCU command formats

- `mcb_config oid=<oid>`
- `mcb_config_stepper oid=%c stepper_oid=%c`
- `mcb_query oid=%c clock=%u rest_ticks=%u retransmit_count=%c invert=%c`
- `mcb_auto_start oid=%c v=%u a=%u lmax=%u dir=%i enable=%i invert=%i`
- `mcb_auto_abort oid=%c`
- `set_limit_a oid=%c state=%c`

### Response handlers

- `MCB_STATE` -> `_on_state`
- `MCB_DONE` -> `_on_done`
- `MCB_ERROR` -> `_on_error`

### Runtime command capture

`MCB_CONFIG SLOT=slot2`, `MCB_QUERY`, and `SET_LIMIT_A STATE=0/1/0` were accepted while idle with no saved-variable diff and no `MCB_STATE`, `MCB_DONE`, or `MCB_ERROR` payload in captured log tails. Live callback payloads still require `MCB_AUTO_START` or a physical anti-wrap event.

## `box_rfid.so`

### Class `BoxRFID`

- `__init__(self, config)`
- `_build_config(self)`
- `read_card(self)`
- `read_card_from_slot(self)`
- `_schedule_rfid_read(self, eventtime)`
- `start_rfid_read(self, stepper)`
- `stop_read(self)`

### Runtime fields

- `name`
- `oid`
- `fm17550_read_card`
- `gcode`
- `read_rfid_timer`
- `rfid_read_attempts`
- `rfid_read_start_time`
- `max_read_time = 30.0`
- `get_message_count = 1`
- `temp_message_1`
- `temp_message_2`
- `stepper`
- `had_get_value`

### MCU command formats

- `query_fm17550 oid=<oid> rest_ticks=0`, with `on_restart=True`
- `config_fm17550 oid=<oid> spi_oid=<spi_oid>`
- query command: `fm17550_read_card_cb oid=%c`
- response format: `fm17550_read_card_return oid=%c status=%c data=%*s`

### Runtime command capture

`SLOT_RFID_READ SLOT=slot2`, `INIT_RFID_READ`, and `MULTI_COLOR_READ_RFID SLOT=slot2` were accepted while idle with no saved-variable diff, `multi_color_controller.rfid.results = {}`, and no raw FM17550 `status/data` payload in captured log tails. Existing slot2 metadata was not cleared.

## `multi_color_controller.so`

### Enums

- `BoxState.EMPTY = 0`
- `BoxState.LOADED = 1`
- `BoxState.IN_EXTRUDER = 2`
- `BoxState.IN_FEEDER = 3`
- `BoxState.ERROR = -1`
- `BoxState.UNKNOWN = -2`
- `BoxState.PENDING = -3`
- `ConnectionMode.LOCAL = "local"`
- `ConnectionMode.REMOTE = "remote"`

### Adapter command mapping

Local adapter calls QIDI/vendor G-code:

- `load_filament(slot0)` -> `E_LOAD SLOT=0`
- `unload_filament(slot0)` -> `E_UNLOAD SLOT=0`
- `swap_filament(slot0, slot1)` -> `E_UNLOAD SLOT=0`, `E_LOAD SLOT=1`
- `read_rfid(slot0)` -> `SLOT_RFID_READ SLOT=slot0`
- `sync_to_extruder(slot0)` -> `SAVE_VARIABLE VARIABLE=slot_sync VALUE='slot0'`
- `unsync_from_extruder()` -> `SAVE_VARIABLE VARIABLE=slot_sync VALUE='slot16'`
- `print_start(3, 240)` -> `BOX_PRINT_START EXTRUDER=3 HOTENDTEMP=240`

Remote adapter sends JSON dictionaries over serial:

- `{"cmd":"load_filament","slot":0,"options":{},"timestamp":...,"id":"cmd_..."}`
- `{"cmd":"unload_filament","slot":0,"options":{},"timestamp":...,"id":"cmd_..."}`
- `{"cmd":"swap_filament","from_slot":0,"to_slot":1,"options":{},"timestamp":...,"id":"cmd_..."}`
- `{"cmd":"read_rfid","slot":0,"timestamp":...,"id":"cmd_..."}`
- `{"cmd":"sync_to_extruder","slot":0,"timestamp":...,"id":"cmd_..."}`
- `{"cmd":"unsync_from_extruder","timestamp":...,"id":"cmd_..."}`
- `{"cmd":"print_start","extruder":3,"hotendtemp":240,"timestamp":...,"id":"cmd_..."}`

### TaskQueueManager flow map

- `0`: no steps
- `1`: `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE`
- `2`: `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_LOAD`, `BOX_WIPE`
- `3`: `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`
- `4`: `BOX_EJECT`
- `5`: `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_EJECT`
- `6`: `EXT_HEAT`, `EXT_LOAD`, `EXT_BITE`, `EXT_WIPE`
- `7`: `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD`
- `8`: `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD`, `WAIT_USER`, `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE`
- `9`: `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `WAIT_USER`, `EXT_HEAT`, `EXT_LOAD`, `EXT_BITE`, `EXT_WIPE`

## `box_detect.so`

### Class `BoxDetect`

- `__init__(self, config)`
- `_handle_ready(self)`
- `get_config_mcu_serials(self)`
- `get_check_serials_id(self, config_path, box_index)`
- `monitor_serial_by_id(self, eventtime)`
- `_update_config_file(self, current_devices, box_index=1)`
- `_request_restart(self)`
- `count_box_includes(self, file_path)`

### Module functions

- `is_monitor_config_file_empty(file_path)`
- `update_monitor_config_file(file_path, current_devices, box_index=1)`

### Paths referenced by strings

- `/home/qidi/printer_data/config/box.cfg`
- `/home/qidi/printer_data/config/box1.cfg`
- `/home/qidi/printer_data/config/box2.cfg`
- `/home/qidi/printer_data/config/saved_variables.cfg`

## `box_config.py`

`box_config.py` is plain Python, not a compiled module, but it is part of the stock QIDI Box object graph. It expands `[box_config boxN]` into generated runtime objects:

- `box_stepper slot<N*4>` through `box_stepper slot<N*4+3>`
- `heater_generic heater_box<N+1>`
- `temperature_sensor heater_temp_a_box<N+1>`
- `temperature_sensor heater_temp_b_box<N+1>`
- `box_heater_fan heater_fan_a_box<N+1>`
- `box_heater_fan heater_fan_b_box<N+1>`
- `controller_fan board_fan_box<N+1>`
- `box_rfid card_reader_<N*2+1>` and `box_rfid card_reader_<N*2+2>`

Generated-object key mapping is in `docs/qidi_box/qidi_box_generated_config_reference.md`.

## Control conclusion

- QIDI stock control uses local Klipper MCU primitives wrapped by compiled Cython modules.
- `box_stepper.so` contains the hardcoded stock load/unload distances, speeds, acceleration values, branch logic, and sync behavior.
- `box_autofeed.so` owns a separate MCU helper protocol for feed assist / anti-wrap behavior.
- `box_rfid.so` owns FM17550 SPI RFID reads and passes `status` plus raw `data` bytes back to Python.
- `multi_color_controller.so` does not add tunable local motion; it maps UI/state operations to the same vendor G-code commands on this machine.
