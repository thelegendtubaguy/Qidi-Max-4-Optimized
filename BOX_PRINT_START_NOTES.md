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

#### Deeper routine-level observations

From deeper reversing of `RemoteAdapter._send_command`, `RemoteAdapter._process_message`, and `RemoteAdapter._handle_event`:

- `_send_command` sits directly on the `json.dumps` / `encode` / `write` / `write_timeout` path.
- `_send_command` also appears to generate a command ID when one is not already present.
- `_process_message` sits directly on the `json.loads` path.
- `_process_message` branches on at least `command_response` and `status_update`.
- `_process_message` appears to extract a `response` object and pass it into `_update_state_from_response`.
- `_process_message` also appears to store parsed replies in `response_queue` keyed by `cmd_id`.
- `_handle_event` dispatches on `event_type`.
- `_handle_event` appears to expect a scalar-like payload value for at least some events, not only a nested object, because it has explicit formatting paths for `str`, `int`, and `float` payloads.
- `_generate_command_id` appears to synthesize a unique string ID per request.

That makes the most likely remote flow:

- send newline-delimited JSON command with `cmd_id`
- receive `command_response` matched by `cmd_id`
- also receive async `status_update` and event messages

#### Best current reconstruction of `cmd_id`

`cmd_id` now looks like a generated string, not a plain integer.

Best current reconstruction:

```python
cmd_id = f"cmd_{int(time.time() * 1000)}_{hash(threading.current_thread().ident) % 10000:05d}"
```

That exact source form is still reconstructed rather than recovered verbatim, but the visible arithmetic and strings strongly support:

- `cmd_` prefix
- current time in milliseconds
- a thread-derived suffix reduced modulo `10000`
- zero-padded decimal formatting

That fits the observed use of `cmd_id` as the correlation key into `response_queue`.

#### Best current reconstruction of inbound schemas

`command_response` most likely looks roughly like:

```json
{
  "command_response": {
    "response": {
      "box_status": "...",
      "main_status": "...",
      "sub_status": "...",
      "slot_states": ...,
      "drying_states": ...
    }
  }
}
```

`status_update` most likely looks roughly like:

```json
{
  "status_update": {
    "box_status": "...",
    "main_status": "...",
    "sub_status": "...",
    "slot_states": ...,
    "drying_states": ...
  }
}
```

The exact nesting is still partly inferred, but these field names are now strongly grounded in the binary.

The strongest current refinement is that `_update_state_from_response` appears to consume the selected `response` object directly, not a second nested `state` wrapper.

Best current reconstruction:

```json
{
  "response": {
    "slot_states": [
      {
        "slot_num": 1,
        "slot_state": "LOADED",
        "slot_name": "...",
        "slot_sync": "slot-1",
        "slot_info": {"...": "..."}
      }
    ],
    "drying_states": [
      {
        "drying_state": "...",
        "dry_state": "..."
      }
    ],
    "box_status": "...",
    "main_status": "...",
    "sub_status": "...",
    "operation_progress": "...",
    "operation_error": "...",
    "target_slot": "..."
  }
}
```

The highest-confidence path is `response.slot_states[]`. That collection appears to be iterated and normalized into internal `slot-<n>` keyed state.

#### Confirmed or strongly implied event labels

These are the strongest current candidates for actual event values handled by `_handle_event`:

- `filament_runout`
- `filament_loaded`
- `filament_unloaded`
- `drying_started`
- `drying_stopped`
- `operation_error`

The state/enum vocabulary visible in the same controller binary includes:

- `LOADED`
- `EMPTY`
- `ERROR`
- `PENDING`
- `UNKNOWN`
- `IN_FEEDER`
- `WAIT_USER`

Those likely appear in `slot_state`, `slot_states`, drying state, or other inbound status payloads.

#### Important current conclusion

The machine-to-box USB protocol is now best understood as:

- serial over `/dev/ttyACM*` or `/dev/ttyUSB*`
- newline-delimited JSON frames
- `ping` / `pong` heartbeat or liveness path
- command messages keyed by `cmd_id`, `action`, and probably `params`
- async inbound messages split between `command_response` and `status_update`

That is the clearest evidence so far for how QIDI talks to the box without going through visible Klipper macros.

#### Best current picture of the serial receive loop

`RemoteAdapter._communication_loop` now looks like a dedicated serial-reader thread that:

- runs while `self.connected` is true
- uses the stored serial object from `connect`
- checks a property consistent with `in_waiting > 0`
- accumulates incoming text into a buffer
- looks for newline-delimited message boundaries
- strips complete lines and parses them as JSON
- dispatches parsed messages into `_process_message`
- exits on disconnect or communication error instead of reconnecting itself

The serial open/setup path appears to live in `RemoteAdapter.connect`, not in the hot loop. That is where `baudrate`, `timeout`, `write_timeout`, and the serial object itself appear to be configured.

#### Best current picture of `RemoteAdapter.connect`

`RemoteAdapter.connect` now looks roughly like:

1. check `self.port`
2. if missing, call `_find_box_port()` and store the result
3. if still missing, return early
4. open `serial.Serial(self.port, baudrate=self.baudrate, timeout=1, write_timeout=1)`
5. store the serial object
6. set `self.connected = True`
7. start a `_communication_loop` thread
8. start a `_send_heartbeat` thread

The current evidence suggests `_ping` exists as a separate method, but is not started as its own thread from `connect`.

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

### Decoded Cython string and method slots used by `cmd_BOX_PRINT_START`

The key Cython mstate offsets around `cmd_BOX_PRINT_START` now decode to concrete names:

- `+0x1508` -> `slot16`
- `+0xf40` -> `gcode`
- `+0xfe0` -> `get_value_by_key`
- `+0x1198` -> `lookup_object`
- `+0x1408` -> `run_script_from_command`
- `+0x15f0` -> `temp`
- `+0x1660` -> `unload_slot`
- `+0x1080` -> `init_load_slot`
- `+0xb48` -> `box_stepper`
- `+0x840` -> `MOVE_TO_TRASH\nM109 S`
- `+0x16a8` -> `value_t`

That materially sharpens the implementation picture.

The early mapping path now looks like:

- build `value_t<EXTRUDER>`
- call `get_value_by_key(...)`
- compare the result against `slot16`
- build `box_stepper<slot>`
- call `lookup_object(...)`
- run formatted scripts via `gcode.run_script_from_command(...)`

### What the small mapping helpers do

The most relevant small helpers in `box_extras.so` now look like this:

- `get_value_by_key` -> thin `save_variables` lookup helper; effectively `self.save_variables.allVariables.get(key, default)`
- `get_key_by_value` -> inverse lookup over saved variables, with optional filtering by allowed keys
- `search_index_by_value` -> reverse-maps a stored value back to a generated slot-style key such as `slotN`

That means `cmd_BOX_PRINT_START` is not hard-coding slot mappings. It is reading them from the QIDI `save_variables` model.

### Best current breakdown of `BOX_PRINT_START`

This is the best current picture of the local print-start path.

Confirmed:

- `_print_start_box_prepar` in `config/klipper-macros-qd/start_end.cfg` clears retry/toolchange/runout state first.
- It then calls `BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...`.
- `box_extras.BoxExtras.cmd_BOX_PRINT_START` is the implementation that owns the hidden sequence.
- `box_extras.so` contains embedded script fragments for:
  - `EXTRUDER_LOAD SLOT={init_load_slot}`
  - `EXTRUDER_UNLOAD SLOT={unload_slot}`
  - `MOVE_TO_TRASH`
  - `CUT_FILAMENT_1`
  - `M109 S{hotendtemp}`
- Actual feeder mechanics then run in `box_stepper.so` through `cmd_EXTRUDER_LOAD`, `cmd_EXTRUDER_UNLOAD`, and likely optional `cmd_SLOT_RFID_READ`.

Strongly implied normal sequence:

1. Reset controller/toolchange/runout state
2. Evaluate whether the current path is already loaded and whether unload is required
3. Move to chute-side handling position if needed
4. Heat or wait for hotend temperature stability when required
5. Cut and/or unload previous filament when required
6. Load the requested slot into the extruder path
7. Verify loaded state, and possibly RFID/material identity
8. Return to the visible print-start macro, which may then call `EXTRUSION_AND_FLUSH`

Strongly implied decision points inside `cmd_BOX_PRINT_START`:

- whether there is already filament in the extruder path
- whether the hotend is at a stable usable temperature
- whether the loaded filament can be recognized
- whether a retry/resume path should be armed

Useful supporting evidence:

- `QDE_004_010`: feeding status incorrect; exit filament from extruder first
- `QDE_004_021`: unable to recognize loaded filament
- explicit hotend temperature instability warning string
- paired embedded unload/load templates in the same function

### Deeper branch structure inside `cmd_BOX_PRINT_START`

More detailed reversal now suggests this structure:

- `CONFIRMED` parse two gcode parameters early
- `STRONGLY IMPLIED` those are `EXTRUDER` and `HOTENDTEMP`
- `CONFIRMED` derive a target slot-like identifier by building `value_t<EXTRUDER>` and resolving it through `get_value_by_key`
- `CONFIRMED` read a current-slot-like value into a separate variable
- `CONFIRMED` compare the current-slot value against a fixed sentinel constant
- `HIGH CONFIDENCE` that sentinel is `slot16`, not `slot-1`
- `CONFIRMED` compare current slot against target slot
- `STRONGLY IMPLIED` if current slot differs from target slot, build a 3-key script template using values equivalent to `hotendtemp`, `unload_slot`, and `init_load_slot`
- `STRONGLY IMPLIED` if current slot matches target slot, build a 2-key script template using values equivalent to `hotendtemp` and `init_load_slot`
- `CONFIRMED` perform repeated `run_script_from_command`-style execution of those formatted gcode strings

That is the strongest current evidence that unload is conditionally skipped when the already-loaded slot matches the requested slot.

The repeated embedded template family in `box_extras.so` is consistent with at least these two main paths:

- same-slot or no-current-slot path: heat and load
- different-slot path: unload old slot, then load target slot

Current best guess for the three main script families is:

- load-only family
- unload-then-load family
- cut-then-unload-then-load family

There is also evidence for a special-case path around the sentinel slot handling, but that branch is not fully decoded yet.

### Placement of cut, sensor, RFID, and tighten logic

Current best understanding:

- `CUT_FILAMENT_1` is present in the same `BOX_PRINT_START` script cluster, but is not yet proven unconditional in the normal path
- `DISABLE_ALL_SENSOR` is present in a prelude-like start script and appears to occur before chute move and hotend wait in at least one branch
- `SLOT_RFID_READ` is not yet proven to be called directly by `cmd_BOX_PRINT_START`
- `TIGHTEN_FILAMENT` looks like a separate command path, not proven to run inside normal `BOX_PRINT_START`
- filament-recognition helpers such as `detect_filament_loaded` and `auto_detect_filament` exist in `box_extras.so`, but their direct call placement from `cmd_BOX_PRINT_START` is still not fully proven

So the strongest current evidence is:

- heat/load/unload logic is definitely inside `cmd_BOX_PRINT_START`
- cut/sensor/recognition logic is partly inside or adjacent, but still branch-dependent and not fully pinned down

### What is still missing for a full source-equivalent breakdown

I still do not have a complete source-equivalent branch map for `cmd_BOX_PRINT_START`.

What is still unresolved:

- the exact current-slot read chain
- the exact meaning of every truthiness gate around the major branch blocks
- the exact placement of `CUT_FILAMENT_1` and `DISABLE_ALL_SENSOR` relative to each major template family
- whether `SLOT_RFID_READ` is called directly in `cmd_BOX_PRINT_START`
- whether `retry_step` and `load_retry_num` are only prepared by visible macros or also touched inside the function

What is now much clearer:

- the sentinel is very likely `slot16`
- `cmd_BOX_PRINT_START` uses `save_variables`-backed mapping through `value_t*`
- `get_value_by_key` is part of the real print-start resolution path

So the current note now has a much better structural breakdown, but not yet a fully complete decompilation-grade one.

### Local vs remote print-start implementations

`multi_color_controller.so` contains two different adapter implementations of print start:

- `LocalAdapter.print_start`
- `RemoteAdapter.print_start`

Best current interpretation:

- `LocalAdapter.print_start` formats a Klipper gcode command string equivalent to `BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...` and executes it locally.
- `RemoteAdapter.print_start` builds a remote JSON command with action `print_start` and parameters equivalent to `extruder` and `hotendtemp`.

So the controller layer abstracts two backends:

- local backend: call Klipper/vendor commands directly
- remote backend: send USB JSON to a second-generation box

For this printer configuration, the local backend is the one that matters most.

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

Those `value_t*` keys are now directly relevant to `BOX_PRINT_START`: current reversal suggests the function builds `value_t<EXTRUDER>` and resolves it through `get_value_by_key(...)` to determine the target slot mapping.

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

### Best current action-to-parameter map for the USB JSON path

This is the best current reconstruction of the remote `action` payloads.

Confirmed or strongly implied:

- `load_filament` -> `slot`
- `unload_filament` -> `slot`
- `swap_filament` -> `from_slot`, `to_slot`
- `read_rfid` -> `slot`
- `sync_to_extruder` -> `slot`
- `unsync_from_extruder` -> no required parameter known
- `box_unload` -> `slot`
- `init_rfid` -> no required parameter known
- `reload_all` -> `first`
- `auto_reload` -> no required parameter known
- `retry` -> likely `rfid`
- `tighten` -> `tool`
- `print_start` -> `extruder`, `hotendtemp`
- `try_resume` -> no required parameter known
- `resume_print` -> likely `temp`
- `disable_heater` -> no required parameter known
- `clear_runout` -> no required parameter known
- `clear_flush` -> no required parameter known
- `clear_ooze` -> no required parameter known
- `cut_filament` -> `tool`

Still less certain:

- `set_temp` -> likely a `temp_params` object; exact inner keys are still unknown
- `init_mapping` -> likely a `mapping` object; exact shape still unknown
- some commands may merge extra optional values into `params` beyond the required fields above

One extra detail from reversal: slot-bearing remote methods appear to normalize `slotN` strings into numeric slot indexes before sending them onward. So the public gcode layer may accept `slotN`, but the USB JSON payload may use plain slot numbers.

### `set_temp` and `init_mapping` payload notes

`RemoteAdapter.set_temp` and `RemoteAdapter.init_mapping` now look more like simple remote send wrappers than complex field-derivers.

Best current reconstruction:

- `set_temp` sends top-level `action="set_temp"` plus a `temp_params` object
- `init_mapping` sends top-level `action="init_mapping"` plus a `mapping` object

For `set_temp`, the strongest current clue is that the controller-side wrapper appears to build a sparse dict keyed by `value_t0`..`value_t15` before handing it to the adapter. I do not yet have proof that the remote payload instead expands those into `bed_temp`, `chamber_temp`, `extruder_temp`, `target_temp`, or `box_num`.

For `init_mapping`, I do not yet have the exact inner shape of the `mapping` object. `FLOW_MAP` and related names exist in the controller binary, but I cannot yet prove that they are the final on-wire key names.

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

The most likely active local print-start path is:

- `config/klipper-macros-qd/start_end.cfg:_print_start_box_prepar`
- clear retry/toolchange/runout state
- `BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...`
- `box_extras.BoxExtras.cmd_BOX_PRINT_START`
- hidden scripted orchestration using commands such as:
  - `EXTRUDER_UNLOAD`
  - `EXTRUDER_LOAD`
  - `CUT_FILAMENT` / `CUT_FILAMENT_1`
  - `MOVE_TO_TRASH`
  - `M109 S{hotendtemp}`
  - sensor/init/reset helpers
- low-level execution in `box_stepper.so`
- optional visible `EXTRUSION_AND_FLUSH` after `BOX_PRINT_START` returns

`multi_color_controller.so` exists alongside that path, but this no longer looks like a simple chain where `BOX_PRINT_START` immediately delegates to `multi_color_print_start`.

Instead:

- `BOX_PRINT_START` itself appears to contain substantial orchestration logic
- `MultiColorController.cmd_multi_color_print_start` is better understood as a separate controller-layer entry point with local and remote backends
- `LocalAdapter.print_start` likely emits local `BOX_PRINT_START ...`
- `RemoteAdapter.print_start` likely emits remote JSON `action="print_start"`

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
