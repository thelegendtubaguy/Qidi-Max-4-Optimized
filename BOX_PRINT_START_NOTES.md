# BOX_PRINT_START Notes

This note captures what is currently known about `BOX_PRINT_START` and the QIDI box control stack on this Max 4.

This pass adds evidence from inspection of the printer-side Klipper and QIDI client payloads, including:

- `file`
- `strings`
- `llvm-nm`
- `llvm-objdump`
- `radare2`

The main goal here is not just to explain `BOX_PRINT_START`, but to answer a more practical question:

Can the box be controlled from Klipper macros directly, without relying on the highest-level hidden QIDI orchestration?

Short answer: yes, partly. You can bypass `BOX_PRINT_START` and much of `multi_color_controller` by calling lower-level vendor commands directly from macros. You cannot avoid vendor binaries entirely, because the actual box motion, RFID, autofeed, and sensor logic live in compiled modules.

## What calls it

- `_PRINT_START_BOX_PREPAR` in `config/klipper-macros-qd/start_end.cfg` calls:

  ```gcode
  BOX_PRINT_START EXTRUDER={EXTRUDER} HOTENDTEMP={HOTENDTEMP}
  ```

- That macro runs during the print start sequence, before the preheat and probing phases.

## Why this machine is on the local box path

- `config/printer.cfg` includes `config/box.cfg` and declares `[multi_color_controller]`.
- `config/box.cfg` declares these local objects:
  - `[box_config box0]`
  - `[box_extras]`
  - `[box_autofeed]`
  - `[mcu mcu_box1]`
- `config/box.cfg` also defines `T0`..`T15` and `UNLOAD_T0`..`UNLOAD_T15` wrappers that call `EXTRUDER_LOAD` and `EXTRUDER_UNLOAD` directly.

That strongly suggests this printer is using the local MCU-backed box path, not only the higher-level `multi_color_controller` abstraction.

## What it is not

- `BOX_PRINT_START` is not defined as a normal `[gcode_macro ...]` in this config repo.
- It is not registered in these visible Python files:
  - `/home/qidi/klipper/klippy/extras/color_feeder.py`
  - `/home/qidi/klipper/klippy/extras/feed_slot.py`
  - `/home/qidi/klipper/klippy/extras/box_config.py`

## Vendor module inventory

The active vendor box stack in `/home/qidi/klipper/klippy/extras/` is:

- `box_autofeed.so`
- `box_detect.so`
- `box_extras.so`
- `box_rfid.so`
- `box_stepper.so`
- `multi_color_controller.so`
- `box_config.py`
- `box_heater_fan.py`
- `color_feeder.py`
- `feed_slot.py`

The compiled modules are all:

- ELF 64-bit
- `aarch64`
- dynamically linked
- built with debug info present
- not stripped

That is why `llvm-nm` and `llvm-objdump` are useful here even without source.

## High-level stack structure

There appear to be at least four layers:

1. Klipper macros in `config/`
2. High-level vendor orchestration in `box_extras.so`
3. Optional controller/state-machine layer in `multi_color_controller.so`
4. Low-level box mechanics and sensing in:
   - `box_stepper.so`
   - `box_rfid.so`
   - `box_autofeed.so`

`box_detect.so` appears separate. It looks like startup/config detection glue, not part of print-start filament prep.

## What `box_detect.so` does

`box_detect.so` exports a `BoxDetect` class with methods such as:

- `get_config_mcu_serials`
- `get_check_serials_id`
- `monitor_serial_by_id`
- `_update_config_file`
- `_request_restart`

Strings inside it reference:

- `/home/qidi/QIDI_Client/tools/cfg/*.cfg`
- `/home/qidi/QIDI_Client/tools/mcu...`

So `box_detect.so` looks like box MCU detection and config-file update plumbing, not the material-prep path.

## What `multi_color_controller.so` adds

`multi_color_controller.so` is much broader than a single print-start command. It contains:

- `UnifiedState`
- `TaskQueueManager`
- `BaseAdapter`
- `LocalAdapter`
- `RemoteAdapter`
- `MultiColorController`

This means QIDI implemented a general multi-color state machine, not only one startup helper.

### Confirmed controller command surface

`strings` and symbol inspection show these controller commands:

- `cmd_query_multi_color`
- `cmd_multi_color_load`
- `cmd_multi_color_unload`
- `cmd_multi_color_swap`
- `cmd_multi_color_dry`
- `cmd_multi_color_read_rfid`
- `cmd_multi_color_sync`
- `cmd_multi_color_config`
- `cmd_set_filament_dry`
- `cmd_multi_color_box_unload`
- `cmd_multi_color_init_rfid`
- `cmd_multi_color_reload_all`
- `cmd_multi_color_auto_reload`
- `cmd_multi_color_retry`
- `cmd_multi_color_tighten`
- `cmd_multi_color_print_start`
- `cmd_multi_color_try_resume`
- `cmd_multi_color_resume_print`
- `cmd_multi_color_init_mapping`
- `cmd_multi_color_disable_heater`
- `cmd_multi_color_set_temp`
- `cmd_multi_color_clear_runout`
- `cmd_multi_color_clear_flush`
- `cmd_multi_color_clear_ooze`
- `cmd_multi_color_cut_filament`
- `cmd_query_save_variables`
- `cmd_set_save_variable`
- `cmd_reset_save_variables`
- `cmd_user_confirm_continue`

### Confirmed controller state fields and concepts

Relevant strings show the controller tracks:

- `main_status`
- `sub_status`
- `current_operation`
- `operation_progress`
- `operation_error`
- `target_slot`
- `slot_states`
- `box_status`
- `drying_states`
- `b_endstop_state`
- `e_endstop_state`
- `box_button_state`
- `is_waiting_user`
- `flow_id`

This is not just motion control. It is a state machine and UI/status bridge.

### Local vs remote adapters

`multi_color_controller.so` clearly supports two backends:

- `LocalAdapter`
- `RemoteAdapter`

Their embedded descriptions are revealing:

- `LocalAdapter` - direct control of existing Klipper components
- `RemoteAdapter` - communicates with the second-generation box

`RemoteAdapter` strings show:

- `/dev/ttyACM*`
- `/dev/ttyUSB*`
- `json`
- `cmd_id`
- `response_queue`
- `_send_command`
- `_process_message`
- `_send_heartbeat`
- `_find_box_port`

So the remote path appears to speak a JSON message protocol over serial ports, with command IDs, responses, events, and heartbeat traffic.

For this machine, the local path is almost certainly the active one.

### What is now confirmed about the USB JSON transport

`RemoteAdapter` is no longer just a guess. The binary contains direct evidence that it implements a USB serial JSON protocol.

#### Transport implementation clues

Strings in `multi_color_controller.so` show the remote path uses:

- `json`
- `dumps`
- `loads`
- `Serial`
- `serial`
- `baudrate`
- `timeout`
- `write_timeout`
- `readline`
- `in_waiting`
- `encode`
- `decode`
- `strip`
- `communication_thread`
- `command_queue`
- `response_queue`

That is strong evidence for a line-oriented JSON protocol over a serial device.

#### Port discovery clues

The remote adapter searches ports matching:

- `/dev/ttyACM*`
- `/dev/ttyUSB*`

and also contains:

- `possible_ports`
- `test_serial`
- `_find_box_port`

So the port scan and validation logic is in `RemoteAdapter`, not only in the client UI.

#### One exact JSON frame is now confirmed

The binary contains this exact literal, including a newline terminator:

```json
{"cmd":"ping"}\n
```

It also contains the literal `pong`.

So at least the adapter health-check path is definitely newline-delimited JSON over the USB serial link.

#### Most likely general command frame shape

I do not yet have one complete non-ping JSON literal, but the following exact field names exist together in the same remote adapter code:

- `action`
- `cmd_id`
- `params`
- `command`
- `response`
- `event_type`
- `result`
- `results`
- `success`

Combined with the per-command action names below, the most likely message shape is something close to:

```json
{"cmd_id":"...","action":"load_filament","params":{...}}\n
```

That is still an inference, but now a much tighter one than before.

#### Confirmed remote action names

These exact action-like strings exist in the remote adapter path:

- `load_filament`
- `unload_filament`
- `swap_filament`
- `start_drying`
- `stop_drying`
- `read_rfid`
- `sync_to_extruder`
- `unsync_from_extruder`
- `save_variable`
- `box_unload`
- `init_rfid`
- `reload_all`
- `auto_reload`
- `retry`
- `tighten`
- `print_start`
- `try_resume`
- `resume_print`
- `init_mapping`
- `disable_heater`
- `set_temp`
- `clear_runout`
- `clear_flush`
- `clear_ooze`
- `cut_filament`

These are the strongest current candidates for the JSON `action` values sent to the box when the remote path is active.

#### Confirmed parameter and payload field names

These exact field names exist in the remote/controller code and are likely used either as command parameters, response fields, or both:

- `slot`
- `from_slot`
- `to_slot`
- `tool`
- `hotendtemp`
- `temp`
- `temp_params`
- `temp_value`
- `box_num`
- `mapping`
- `retry_step`
- `target_slot`
- `current_tool`
- `next_tool`
- `bed_temp`
- `chamber_temp`
- `extruder_temp`
- `target_temp`
- `box_info`
- `box_status`
- `slot_states`
- `rfid_results`
- `drying_states`
- `operation_progress`
- `operation_error`
- `box_connected`

#### Confirmed response/event classes

These exact message-category strings exist in the remote path:

- `command_response`
- `status_update`
- `connected`
- `loaded`
- `drying_started`
- `drying_stopped`
- `pong`

The handler also contains Chinese log strings for:

- runout events
- material load complete
- material unload complete
- drying start
- drying stop
- box error

So there are almost certainly more event types than the exact English string set visible so far.

#### Important current conclusion

The machine-to-box USB protocol is now best understood as:

- serial over `/dev/ttyACM*` or `/dev/ttyUSB*`
- newline-delimited JSON frames
- `ping` / `pong` heartbeat or liveness path
- command messages keyed by `cmd_id`, `action`, and probably `params`
- async inbound messages split between `command_response` and `status_update`

That is the clearest evidence so far for how QIDI talks to the box without going through visible Klipper macros.

## What `/home/qidi/QIDI_Client/` adds

The dumped QIDI client tree adds useful evidence even though `tools/` was empty in this dump.

### Startup and process model

- `/home/qidi/QIDI_Client/bin/start.sh` launches:

  ```text
  taskset -c 0 /home/qidi/QIDI_Client/bin/qidiclient
  ```

- `qidiclient` is a stripped `aarch64` ELF executable.
- `/home/qidi/QIDI_Client/bin/tuning.sh` also treats the client as a pinned, performance-managed process alongside `klippy`, `moonraker`, `nginx`, and `ustreamer`.

### Client transport and integration clues

Strings in `qidiclient` show:

- `org.qidi.moonraker`
- `org.qidi.klipper`
- `jsonrpc`
- `application/json`
- `Initial klipper state: {}`
- `Updated klipper state: {}`
- `Failed to parse klipper state from response`

That strongly suggests the client talks to Moonraker and/or Klipper through a QIDI wrapper layer, then reflects printer state into the UI.

It does not look like `qidiclient` is the component that directly emits the box USB JSON protocol. The client contains WebSocket and Moonraker-facing strings, while the USB serial JSON evidence is concentrated in `multi_color_controller.so`'s `RemoteAdapter`.

### Client-side box config generation clues

`qidiclient` contains an embedded template for `/home/qidi/printer_data/config/box.cfg`, including:

- `[box_config box{B}]`
- `[box_extras]`
- `[box_autofeed]`
- `/dev/serial/by-id/usb-Klipper_QIDI_BOX_*`
- `/dev/serial/by-id/usb-Klipper_QIDI_MAX4-BOX-*`

That means the client is involved in box config creation or repair, not just displaying status.

### Client-side save-variable awareness

`qidiclient` contains these exact variable names:

- `enable_box`
- `last_load_slot`
- `slot_sync`
- `filament_slot16`
- `color_slot16`
- `vendor_slot16`
- `box_extras`
- `box_stepper slot`

So the UI/client understands the same persistent state model as the Klipper-side vendor modules.

### Client-side command templates

Both `strings` and `radare2` show these embedded gcode templates in `qidiclient`:

- `MULTI_COLOR_LOAD SLOT=slot`
- `MULTI_COLOR_UNLOAD SLOT=slot`
- `MULTI_COLOR_BOX_UNLOAD SLOT=slot`
- `SAVE_VARIABLE VARIABLE=enable_box VALUE=`
- `SAVE_VARIABLE VARIABLE=filament_slot`
- `SET_HEATER_TEMPERATURE HEATER=heater_box`

Important negative finding:

- I did not find `BOX_PRINT_START` in `qidiclient`.
- I also did not find `MULTI_COLOR_PRINT_START` in `qidiclient`.

That suggests the client's manual box UI likely drives lower-level or mid-level `MULTI_COLOR_*` actions such as load, unload, and box unload, while print-start material prep is still initiated from Klipper macros through `BOX_PRINT_START`.

### Client-side UI step names line up with the low-level mechanics

Useful client strings include:

- `cut_off_filament`
- `pull_back_filament`
- `send_new_filament_to_extruder`
- `wash_away_old_filament`
- `eject_filament`
- `bit_in_filament`
- `ejecting_filament_in_progress`

These line up well with the lower-level `box_stepper.so` and `box_extras.so` mechanics and reinforce the idea that the real motion primitives sit below the UI.

### Client-side error catalog confirms more `QDE_004_*` meanings

The client ships localized JSON error resources for the box path. That gives additional meanings for codes not obvious from the Klipper-side strings alone.

Examples:

- `QDE_004_019`: RFID read failed; check PTFE tube installation
- `QDE_004_022`: auto-loading failed; no replaceable slot found
- `QDE_004_023`: auto-loading failed; filament may be blocked
- `QDE_004_024`: load filament failed; filament failed to enter the extruder

That makes the client dump useful for interpreting the vendor module error space even when the implementation is still hidden.

## What `box_stepper.so` exposes

`box_stepper.so` appears to be the real per-slot mechanics layer.

### Confirmed command handlers

- `cmd_SLOT_UNLOAD`
- `cmd_EXTRUDER_LOAD`
- `cmd_EXTRUDER_UNLOAD`
- `cmd_SLOT_PROMPT_MOVE`
- `cmd_SLOT_RFID_READ`
- `cmd_DIS_STEP`

### Other confirmed methods and internal concepts

- `slot_load`
- `slot_sync`
- `init_slot_sync`
- `switch_next_slot`
- `flush_all_filament`
- `runout_button_callback`
- `get_mcu_endstops`
- `disable_stepper`

### Embedded tuning names found in the binary

These strings suggest the load/unload path is heavily parameterized internally:

- `slot_load_length_1`..`slot_load_length_4`
- `slot_unload_length_1`
- `extruder_load_length_1`
- `extruder_unload_length_1`
- `extruder_unload_length_2`
- `multi_extruder_load_length_1`..`_3`
- `multi_extruder_unload_length_1`..`_2`
- `hub_load_length`
- `multi_extruder_load_speed_1`..`_3`
- `multi_extruder_unload_speed_1`..`_2`
- `multi_extruder_load_accel`
- `multi_extruder_unload_accel`
- `shake_for_load_toolhead`
- `shake_for_unload_toolhead`

I do not yet have source-level confirmation for where all of those values come from. The current visible `config/box.cfg` does not expose them.

### Useful error messages from `box_stepper.so`

These confirm some preconditions and failure modes:

- `QDE_004_001`: slot loading failure
- `QDE_004_002`: extruder already loaded, cannot load another slot
- `QDE_004_003`: slot unloading failure
- `QDE_004_004`: please unload extruder first
- `QDE_004_005`: please load filament to a given slot first
- `QDE_004_006`: extruder loading failure
- `QDE_004_007`: extruder not loaded
- `QDE_004_008`: extruder unloading failure
- `QDE_004_009`: extruder unloading failure
- `QDE_004_011`: filament already loaded, unload first
- `QDE_004_016`: filament exhausted, load the named slot
- `QDE_004_017`: filament flush failed
- `QDE_004_020`: filament unloaded unexpectedly, reload
- `QDE_004_022`: no replaceable slot found
- `QDE_004_025`: extruder unloading failure

Those messages are strong evidence that `box_stepper.so` already contains most of the real safety logic for direct load/unload operations.

## What `box_extras.so` exposes

`box_extras.so` looks like the QIDI-specific orchestration layer that wraps the lower-level slot mechanics with print-start, retry, heater, and toolchange behavior.

### Confirmed Python-visible classes

- `BoxButton`
- `BoxEndstop`
- `BoxExtras`
- `BoxOutput`
- `ToolChange`

### Confirmed `BoxExtras` command handlers

- `cmd_BOX_PRINT_START`
- `cmd_INIT_BOX_STATE`
- `cmd_INIT_RFID_READ`
- `cmd_CLEAR_RUNOUT_NUM`
- `cmd_TIGHTEN_FILAMENT`
- `cmd_RELOAD_ALL`
- `cmd_CLEAR_FLUSH`
- `cmd_CLEAR_OOZE`
- `cmd_CUT_FILAMENT`
- `cmd_AUTO_RELOAD_FILAMENT`
- `cmd_RETRY`
- `cmd_RUN_STEPPER`
- `cmd_ENABLE_BOX_DRY`
- `cmd_DISABLE_BOX_DRY`
- `cmd_TRY_RESUME_PRINT`
- `cmd_RESUME_PRINT_1`
- `cmd_disable_box_heater`

### Confirmed `ToolChange` command handlers

- `cmd_TOOL_CHANGE_START`
- `cmd_TOOL_CHANGE_END`
- `cmd_CLEAR_TOOLCHANGE_STATE`

### Important strings embedded in `box_extras.so`

The binary contains direct gcode-script fragments such as:

- `EXTRUDER_LOAD SLOT={init_load_slot}`
- `EXTRUDER_UNLOAD SLOT={unload_slot}`
- `RUN_STEPPER STEPPER=`
- `MOVE_TO_TRASH`
- `M109 S{hotendtemp}`
- `CUT_FILAMENT_1`
- `DISABLE_ALL_SENSOR`
- `SET_HEATER_TEMPERATURE HEATER=heater_box`
- `ENABLE_BOX_DRY BOX=`
- `DISABLE_BOX_DRY BOX=`

That matters because it means `cmd_BOX_PRINT_START` is not just a tiny pass-through. It appears to build and run substantial internal gcode scripts.

### `BOX_PRINT_START` is a large function

From symbol sizes in the disassembly:

- `box_extras.BoxExtras.cmd_BOX_PRINT_START`: about `0x3260` bytes of machine code
- `multi_color_controller.MultiColorController.cmd_multi_color_print_start`: about `0x0d6c`
- `multi_color_controller.LocalAdapter.print_start`: about `0x0e94`

That size difference strongly suggests `cmd_BOX_PRINT_START` owns a lot of real sequencing itself. It does not look like a trivial one-line delegate.

### Additional error-state clues from `box_extras.so`

Relevant strings include:

- `QDE_004_010`: current feeding status is incorrect; exit filament from extruder first
- `QDE_004_021`: unable to recognize loaded filament
- `The temperature at the hot end is unstable. Wait for the temperature to stabilize before trying again.`
- `No step to retry`
- `Invalid retry_step format`

That implies `box_extras.so` owns retry state, filament recognition checks, and some temperature gating around the high-level sequence.

## What `box_autofeed.so` exposes

`box_autofeed.so` is another important low-level module. It exports `MCBAutoFeed` and appears to handle wrapping detection and limit-sensor-driven assist behavior.

### Confirmed command surface

- `MCB_CONFIG`
- `MCB_AUTO_START`
- `MCB_AUTO_ABORT`
- `SET_LIMIT_A`
- `cmd_query`

### Confirmed related methods

- `_select_slot`
- `_get_slot_stepper`
- `_get_slot_enable_pin_params`
- `qd_get_slot_enable_pin_params`
- `limit_a_event`
- `auto_start`
- `auto_abort`
- `wrapping_detection`
- `wrapping_operate`

### Notable messages

- `QDE_004_013`: detected wrapping filament, please check the filament

That suggests `box_autofeed.so` can affect how aggressive or safe custom direct-load macros should be.

## Saved-variable model and special slots

QIDI extended `save_variables` defaults in `/home/qidi/klipper/klippy/extras/save_variables.py`.

Important defaults include:

- `box_count`
- `enable_box`
- `load_retry_num`
- `slot_sync`
- `retry_step`
- `last_load_slot`
- `filament_slot0`..`filament_slot15`
- `color_slot0`..`color_slot15`
- `vendor_slot0`..`vendor_slot15`
- `value_t0`..`value_t15`

There is also a special extra slot namespace:

- `filament_slot16`
- `color_slot16`
- `vendor_slot16`

On this machine, `config/saved_variables.cfg` currently contains:

- `last_load_slot = 'slot16'`
- `slot_sync = 'slot-1'`

That looks like QIDI uses:

- `slot16` as a special non-box/direct-feed sentinel
- `slot-1` as a special "no active sync target" sentinel

### Evidence that `slot16` is special

`config/klipper-macros-qd/filament.cfg` uses:

- `E_UNLOAD SLOT=16` in `M603`
- `E_LOAD SLOT=16 S={hotendtemp}` in `M604`

So there is definitely a special direct-feed path that is not a normal box slot `slot0`..`slot15`.

## Commands and control points that matter for direct macros

This is the most useful part if the goal is to stop depending on `BOX_PRINT_START`.

### Confirmed usable from visible config today

These are already referenced by macros in `config/`:

- `BOX_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temp>`
- `EXTRUDER_LOAD SLOT=slotN`
- `EXTRUDER_UNLOAD SLOT=slotN`
- `E_LOAD SLOT=16 S=<temp>`
- `E_UNLOAD SLOT=16`
- `CUT_FILAMENT T=<tool>`
- `CUT_FILAMENT_1`
- `INIT_BOX_STATE`
- `INIT_RFID_READ`
- `CLEAR_TOOLCHANGE_STATE`
- `CLEAR_FLUSH`
- `CLEAR_OOZE`

### Confirmed in binaries, but not yet exercised here from custom macros

These are present in symbols and/or script templates:

- `SLOT_UNLOAD SLOT=slotN`
- `SLOT_RFID_READ SLOT=slotN`
- `RUN_STEPPER STEPPER=...`
- `ENABLE_BOX_DRY BOX=...`
- `DISABLE_BOX_DRY BOX=...`
- `RELOAD_ALL`
- `AUTO_RELOAD_FILAMENT`
- `RETRY`
- `TRY_RESUME_PRINT`
- `RESUME_PRINT_1`
- `CLEAR_RUNOUT_NUM`
- `TIGHTEN_FILAMENT`
- `TOOL_CHANGE_START`
- `TOOL_CHANGE_END`
- `CLEAR_TOOLCHANGE_STATE`
- `MCB_CONFIG SLOT=slotN`
- `MCB_AUTO_START`
- `MCB_AUTO_ABORT`
- `SET_LIMIT_A`

### Hidden controller entry points that may still be useful

If you want the QIDI controller/state-machine layer but not `BOX_PRINT_START`, the confirmed handler names in `multi_color_controller.so` are:

- `cmd_multi_color_load`
- `cmd_multi_color_unload`
- `cmd_multi_color_swap`
- `cmd_multi_color_box_unload`
- `cmd_multi_color_reload_all`
- `cmd_multi_color_auto_reload`
- `cmd_multi_color_retry`
- `cmd_multi_color_print_start`
- `cmd_multi_color_try_resume`
- `cmd_multi_color_resume_print`
- `cmd_multi_color_set_temp`
- `cmd_multi_color_clear_runout`
- `cmd_multi_color_clear_flush`
- `cmd_multi_color_clear_ooze`
- `cmd_multi_color_cut_filament`
- `cmd_multi_color_sync`
- `cmd_multi_color_dry`
- `cmd_multi_color_disable_heater`
- `cmd_query_save_variables`
- `cmd_set_save_variable`
- `cmd_reset_save_variables`
- `cmd_user_confirm_continue`

Some uppercase command literals also appear in the binary, such as `MULTI_COLOR_DRY`, `MULTI_COLOR_SYNC`, `QUERY_SAVE_VARIABLES`, `SET_SAVE_VARIABLE`, `RESET_SAVE_VARIABLES`, and `USER_CONFIRM_CONTINUE`, but I have not fully mapped every registered gcode name to every handler yet.

### Confirmed controller-side argument clues

Several argument requirements are now directly visible in `multi_color_controller.so`:

- `cmd_multi_color_load` / `cmd_multi_color_unload` / `cmd_multi_color_box_unload` use `SLOT`
- `cmd_multi_color_swap` requires `FROM` and `TO`
- `cmd_multi_color_sync` uses `ACTION`, and starting sync requires `SLOT`
- `cmd_multi_color_set_temp` requires temperature parameters
- `cmd_multi_color_print_start` uses `EXTRUDER` and `HOTENDTEMP`
- `cmd_multi_color_cut_filament` uses `T`
- `cmd_multi_color_tighten` uses `T`
- `cmd_set_save_variable` uses `VARIABLE` and `VALUE`
- `cmd_multi_color_config` appears to accept `MODE`, `PORT`, and `BAUDRATE`

These exact gcode-template fragments are present in the controller binary:

- `BOX_PRINT_START EXTRUDER=`
- `E_LOAD SLOT=`
- `E_UNLOAD SLOT=`
- `E_BOX SLOT=`
- `SLOT_RFID_READ SLOT=`
- `CUT_FILAMENT T=`
- `TIGHTEN_FILAMENT T=`
- `SAVE_VARIABLE VARIABLE=`
- `ENABLE_BOX_DRY BOX=`
- `DISABLE_BOX_DRY BOX=`
- `RELOAD_ALL FIRST=`
- `TEMP=`
- `VALUE=`
- `END_TIME=`

The controller also contains these direct validation/error strings:

- `必须指定SLOT参数` - must specify `SLOT`
- `启动同步必须指定SLOT参数` - starting sync must specify `SLOT`
- `必须指定FROM和TO参数` - must specify `FROM` and `TO`
- `必须指定T参数（工具号）` - must specify `T` tool parameter
- `未指定温度参数` - no temperature parameter specified
- `未知的ACTION参数:` - unknown `ACTION` parameter

That gives a much better picture of the public command surface even before full decompilation.

## Practical answer: how direct can macro control get?

### What you can likely bypass

You can likely bypass these high-level entry points:

- `BOX_PRINT_START`
- most of `MultiColorController.cmd_multi_color_print_start`
- some of the retry/resume orchestration

by building your own macros around the lower-level slot commands.

### What you cannot bypass

You cannot currently get rid of vendor binaries completely.

The actual mechanics and sensing still live in compiled modules:

- `box_stepper.so`
- `box_rfid.so`
- `box_autofeed.so`
- parts of `box_extras.so`

So the realistic target is:

- bypass the hidden high-level sequence
- keep using the lower-level compiled command handlers

## Best current picture of the call path

The most likely print-start path is:

- `config/klipper-macros-qd/start_end.cfg`
- `BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...`
- `box_extras.BoxExtras.cmd_BOX_PRINT_START`
- lower-level scripted calls into commands such as:
  - `EXTRUDER_LOAD`
  - `EXTRUDER_UNLOAD`
  - `CUT_FILAMENT`
  - `RUN_STEPPER`
  - sensor/init/reset helpers

`multi_color_controller.so` clearly exists alongside that path, but after disassembly this no longer looks like a simple chain of:

- `BOX_PRINT_START`
- immediate delegate to `multi_color_print_start`

Instead, `BOX_PRINT_START` itself appears to contain a substantial amount of orchestration logic.

## What a direct-macro strategy probably looks like

If the goal is to own the sequence yourself, the cleanest path is probably:

1. Keep QIDI's low-level box binaries
2. Stop calling `BOX_PRINT_START` for your custom flow
3. Build your own macro sequence around a subset of these commands:
   - `INIT_BOX_STATE`
   - `INIT_RFID_READ`
   - optional `CUT_FILAMENT_1` or `CUT_FILAMENT T=<tool>`
   - `EXTRUDER_UNLOAD SLOT=<old-slot>` if needed
   - `EXTRUDER_LOAD SLOT=<new-slot>`
   - `SLOT_RFID_READ SLOT=<slot>` if you want verification
   - `EXTRUSION_AND_FLUSH ...` or your own purge sequence
   - optional `CLEAR_FLUSH`, `CLEAR_OOZE`, `CLEAR_RUNOUT_NUM`

That would let you keep the box mechanics while replacing the opaque vendor print-start choreography.

## Important caveat

I do not yet have a full argument map for every hidden command.

What is confirmed here is:

- the commands exist
- many of their gcode templates exist in the binaries
- the lower-level mechanics are implemented in `box_stepper.so`
- `BOX_PRINT_START` is large and script-heavy enough to be more than a trivial wrapper

What is still not fully confirmed is:

- every accepted parameter for every hidden command
- the exact step order inside `cmd_BOX_PRINT_START`
- whether `E_LOAD`, `E_UNLOAD`, and `E_BOX` are registered by `box_extras.so` directly or by another hidden module loaded alongside it

## Most useful concrete findings

- `BOX_PRINT_START` is real vendor code in `box_extras.so`, not a macro.
- `BOX_PRINT_START` itself appears to be large and substantial.
- `box_stepper.so` is the real low-level slot motion layer.
- `multi_color_controller.so` is a general state machine with local and remote adapters, not just a startup helper.
- `slot16` is a special direct-feed sentinel, not a normal box slot.
- `slot-1` appears to mean "no synced slot".
- `config/box.cfg` already exposes a direct macro surface around `EXTRUDER_LOAD` and `EXTRUDER_UNLOAD`.
- If the goal is to bypass hidden high-level startup logic, the best starting point is to build custom macros on top of `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, `SLOT_RFID_READ`, and related reset/flush helpers.

## Files involved so far

- `BOX_PRINT_START_NOTES.md`
- `config/box.cfg`
- `config/printer.cfg`
- `config/klipper-macros-qd/start_end.cfg`
- `config/klipper-macros-qd/filament.cfg`
- `config/klipper-macros-qd/globals.cfg`
- `config/saved_variables.cfg`
- `/home/qidi/klipper/klippy/extras/box_config.py`
- `/home/qidi/klipper/klippy/extras/box_extras.so`
- `/home/qidi/klipper/klippy/extras/multi_color_controller.so`
- `/home/qidi/klipper/klippy/extras/box_stepper.so`
- `/home/qidi/klipper/klippy/extras/box_autofeed.so`
- `/home/qidi/klipper/klippy/extras/box_detect.so`
- `/home/qidi/klipper/klippy/extras/color_feeder.py`
- `/home/qidi/klipper/klippy/extras/feed_slot.py`
- `/home/qidi/klipper/klippy/extras/save_variables.py`
- `/home/qidi/QIDI_Client/bin/qidiclient`
- `/home/qidi/QIDI_Client/bin/start.sh`
- `/home/qidi/QIDI_Client/bin/tuning.sh`
- `/home/qidi/QIDI_Client/resource/qidi_client_error/...`
