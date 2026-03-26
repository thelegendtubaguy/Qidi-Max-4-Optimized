# QIDI Box Implementation Notes

This document is a structured dump of what is currently known about the QIDI box implementation, especially:

- `BOX_PRINT_START`
- the local box control stack in Klipper vendor modules
- the controller/state-machine layer in `multi_color_controller.so`
- the remote USB JSON protocol used by the second-generation box path
- RFID reading and material/color/vendor mapping

This is based on static inspection of the printer-side payloads and client payloads, using:

- `file`
- `strings`
- `llvm-nm`
- `llvm-objdump`
- `radare2`

This note uses printer-native paths such as `/home/qidi/klipper/...` and `/home/qidi/QIDI_Client/...`.

## Reading this note

Confidence labels used here:

- `CONFIRMED` - directly supported by disassembly, symbols, strings, or visible config
- `HIGH CONFIDENCE` - not verbatim source, but tightly supported by multiple pieces of evidence
- `STRONGLY IMPLIED` - likely from control flow and nearby strings, but not fully decompiled to source-equivalent logic
- `SPECULATIVE` - plausible, but not yet well pinned down

## Executive view

The current best model of the QIDI box stack is:

1. visible Klipper macros trigger high-level vendor commands
2. `box_extras.so` owns most of the hidden local print-start orchestration
3. `multi_color_controller.so` provides a broader controller/state-machine layer with both local and remote backends
4. `box_stepper.so`, `box_rfid.so`, and `box_autofeed.so` implement the real low-level mechanics, RFID, and wrapping/autofeed logic
5. `/home/qidi/QIDI_Client/bin/qidiclient` is mainly a UI/client process that talks to Moonraker/Klipper and understands the same saved-state/material model

Most important practical conclusion:

- the box can likely be controlled from custom macros without relying on `BOX_PRINT_START`
- but it cannot be controlled without vendor binaries entirely, because the real feeder, RFID, and autofeed logic live in compiled modules

## Runtime entry points and active path on this machine

### What calls `BOX_PRINT_START`

`config/klipper-macros-qd/start_end.cfg` contains `_PRINT_START_BOX_PREPAR`, which calls:

```gcode
BOX_PRINT_START EXTRUDER={EXTRUDER} HOTENDTEMP={HOTENDTEMP}
```

That happens during print start, before later preheat/probing phases.

### Why this machine is on the local box path

`config/printer.cfg` includes `config/box.cfg` and declares `[multi_color_controller]`.

`config/box.cfg` declares:

- `[box_config box0]`
- `[box_extras]`
- `[box_autofeed]`
- `[mcu mcu_box1]`

`config/box.cfg` also defines `T0`..`T15` and `UNLOAD_T0`..`UNLOAD_T15` wrappers that call:

- `EXTRUDER_LOAD`
- `EXTRUDER_UNLOAD`

That is strong evidence that this printer is using the local MCU-backed box path, not only the higher-level `multi_color_controller` abstraction.

## What `BOX_PRINT_START` is not

- it is not a normal `[gcode_macro ...]` in this config repo
- it is not defined in these visible Python files:
  - `/home/qidi/klipper/klippy/extras/color_feeder.py`
  - `/home/qidi/klipper/klippy/extras/feed_slot.py`
  - `/home/qidi/klipper/klippy/extras/box_config.py`

## Relevant file and module inventory

### Printer-side Klipper vendor modules

Active box-related files under `/home/qidi/klipper/klippy/extras/`:

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

All compiled vendor modules examined here are:

- ELF 64-bit
- `aarch64`
- dynamically linked
- built with debug info present
- not stripped

### Client-side files

The main QIDI client process is:

- `/home/qidi/QIDI_Client/bin/qidiclient`

`/home/qidi/QIDI_Client/bin/start.sh` launches:

```text
taskset -c 0 /home/qidi/QIDI_Client/bin/qidiclient
```

`/home/qidi/QIDI_Client/bin/tuning.sh` also treats `qidiclient` as a pinned, performance-managed process alongside `klippy`, `moonraker`, `nginx`, and `ustreamer`.

## Layered architecture

Best current architecture model:

1. Klipper macros in `config/`
2. high-level local orchestration in `box_extras.so`
3. controller/state-machine layer in `multi_color_controller.so`
4. low-level mechanics and sensing in:
   - `box_stepper.so`
   - `box_rfid.so`
   - `box_autofeed.so`

`box_detect.so` appears separate. It looks like detection/config glue, not the core material-prep path.

## `box_detect.so`

`box_detect.so` exports a `BoxDetect` class with methods such as:

- `get_config_mcu_serials`
- `get_check_serials_id`
- `monitor_serial_by_id`
- `_update_config_file`
- `_request_restart`

Strings reference:

- `/home/qidi/QIDI_Client/tools/cfg/*.cfg`
- `/home/qidi/QIDI_Client/tools/mcu...`

Best current conclusion:

- `box_detect.so` is box MCU detection and config-file update plumbing
- it is not the main print-start/material-prep implementation

## `multi_color_controller.so`

`multi_color_controller.so` is much broader than a single print-start helper.

### Major classes

- `UnifiedState`
- `TaskQueueManager`
- `BaseAdapter`
- `LocalAdapter`
- `RemoteAdapter`
- `MultiColorController`

This is a general multi-color state machine and UI/status bridge, not just a startup helper.

### Local vs remote backend split

Embedded descriptions are revealing:

- `LocalAdapter` - direct control of existing Klipper components
- `RemoteAdapter` - communicates with the second-generation box

Best current interpretation:

- local backend: use Klipper/vendor commands already present on the printer
- remote backend: speak a USB JSON protocol to a second-generation box controller

### Controller command surface

Confirmed controller handler names:

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

### Controller state model

Confirmed state-field vocabulary includes:

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

### Controller/local wrapper print-start path

`MultiColorController.cmd_multi_color_print_start` parses `EXTRUDER` and `HOTENDTEMP` and then dispatches to an adapter print-start path.

Best current interpretation:

- `LocalAdapter.print_start` formats a local Klipper gcode equivalent to `BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...`
- `RemoteAdapter.print_start` builds a remote JSON command with action `print_start` and params equivalent to `extruder` and `hotendtemp`

## Remote USB JSON protocol (`RemoteAdapter`)

### Transport model

`RemoteAdapter` clearly contains serial/JSON transport logic.

Relevant strings include:

- `/dev/ttyACM*`
- `/dev/ttyUSB*`
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
- `command_queue`
- `response_queue`
- `_send_command`
- `_process_message`
- `_send_heartbeat`
- `_find_box_port`

Best current conclusion:

- the second-generation box path uses newline-delimited JSON over USB serial
- the controller scans `/dev/ttyACM*` and `/dev/ttyUSB*`
- the remote protocol is implemented in `multi_color_controller.so`, not in `qidiclient`

### Confirmed literal frame

One exact frame is present in the binary:

```json
{"cmd":"ping"}\n
```

The literal `pong` is also present.

### Best current command frame shape

Not fully proven byte-for-byte, but the strongest current model is:

```json
{"cmd_id":"...","action":"load_filament","params":{...}}\n
```

because the same code path contains:

- `cmd_id`
- `action`
- `params`
- `command`
- `response`
- `event_type`
- `result`
- `results`
- `success`

### Confirmed remote action names

Best current set of action-like strings:

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

### Best current action-to-parameter map

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

- `set_temp` -> likely `temp_params`
- `init_mapping` -> likely `mapping`
- some commands may accept additional optional fields merged into `params`

One useful detail:

- slot-bearing remote methods appear to normalize `slotN` strings into numeric slot indexes before sending them onward

### `cmd_id`

Best current reconstruction:

```python
cmd_id = f"cmd_{int(time.time() * 1000)}_{hash(threading.current_thread().ident) % 10000:05d}"
```

This is reconstructed, not verbatim source, but strongly supported by the arithmetic and string fragments in the binary.

### Inbound message classes

Confirmed message/category strings include:

- `command_response`
- `status_update`
- `connected`
- `loaded`
- `drying_started`
- `drying_stopped`
- `pong`

Best current event labels additionally include:

- `filament_runout`
- `filament_loaded`
- `filament_unloaded`
- `operation_error`

### Inbound schema model

Best current high-level model:

- `_process_message` parses a JSON line
- branches on at least `command_response` and `status_update`
- passes a selected `response` object into `_update_state_from_response`
- stores replies in `response_queue` keyed by `cmd_id`

Best current response payload model:

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

Highest-confidence field path:

- `response.slot_states[]`

Observed state/enum vocabulary includes:

- `LOADED`
- `EMPTY`
- `ERROR`
- `PENDING`
- `UNKNOWN`
- `IN_FEEDER`
- `WAIT_USER`

### `RemoteAdapter.connect`

Best current reconstruction:

1. check `self.port`
2. if missing, call `_find_box_port()` and store the result
3. if still missing, return early
4. open `serial.Serial(self.port, baudrate=self.baudrate, timeout=1, write_timeout=1)`
5. store the serial object
6. set `self.connected = True`
7. start a `_communication_loop` thread
8. start a `_send_heartbeat` thread

### `_communication_loop`

Best current reconstruction:

- runs while connected
- uses the stored serial object
- checks something consistent with `in_waiting > 0`
- accumulates text into a buffer
- splits on newline boundaries
- strips complete lines
- parses JSON
- dispatches into `_process_message`
- exits on disconnect/error rather than reconnecting in-loop

## `/home/qidi/QIDI_Client/`

### What the client appears to do

`qidiclient` looks Moonraker/Klipper-facing, not like the component that directly emits the USB JSON box protocol.

Useful strings include:

- `org.qidi.moonraker`
- `org.qidi.klipper`
- `jsonrpc`
- `application/json`
- `Initial klipper state: {}`
- `Updated klipper state: {}`
- `Failed to parse klipper state from response`

Best current conclusion:

- `qidiclient` is mainly a UI/client integration layer
- the USB serial JSON box protocol is concentrated in `multi_color_controller.so`

### Client box config awareness

`qidiclient` contains an embedded `/home/qidi/printer_data/config/box.cfg` template including:

- `[box_config box{B}]`
- `[box_extras]`
- `[box_autofeed]`
- `/dev/serial/by-id/usb-Klipper_QIDI_BOX_*`
- `/dev/serial/by-id/usb-Klipper_QIDI_MAX4-BOX-*`

So the client is involved in box config creation/repair.

### Client save-variable awareness

`qidiclient` contains these variable names:

- `enable_box`
- `last_load_slot`
- `slot_sync`
- `filament_slot16`
- `color_slot16`
- `vendor_slot16`
- `box_extras`
- `box_stepper slot`

### Client-side gcode templates

Recovered client-side templates include:

- `MULTI_COLOR_LOAD SLOT=slot`
- `MULTI_COLOR_UNLOAD SLOT=slot`
- `MULTI_COLOR_BOX_UNLOAD SLOT=slot`
- `SAVE_VARIABLE VARIABLE=enable_box VALUE=`
- `SAVE_VARIABLE VARIABLE=filament_slot`
- `SET_HEATER_TEMPERATURE HEATER=heater_box`

Important negative finding:

- `BOX_PRINT_START` was not found in `qidiclient`
- `MULTI_COLOR_PRINT_START` was not found in `qidiclient`

Best current conclusion:

- the client likely drives lower-level or mid-level `MULTI_COLOR_*` box actions for manual UI flows
- print-start material preparation still appears to enter from Klipper macros through `BOX_PRINT_START`

### Client UI strings that line up with low-level mechanics

- `cut_off_filament`
- `pull_back_filament`
- `send_new_filament_to_extruder`
- `wash_away_old_filament`
- `eject_filament`
- `bit_in_filament`
- `ejecting_filament_in_progress`

### Client error catalog value

The client ships localized error JSON for the box path. Useful examples:

- `QDE_004_019` - RFID read failed; check PTFE tube installation
- `QDE_004_022` - auto-loading failed; no replaceable slot found
- `QDE_004_023` - auto-loading failed; filament may be blocked
- `QDE_004_024` - load filament failed; filament failed to enter the extruder

## `box_stepper.so`

`box_stepper.so` appears to be the real per-slot mechanics layer.

### Confirmed command handlers

- `cmd_SLOT_UNLOAD`
- `cmd_EXTRUDER_LOAD`
- `cmd_EXTRUDER_UNLOAD`
- `cmd_SLOT_PROMPT_MOVE`
- `cmd_SLOT_RFID_READ`
- `cmd_DIS_STEP`

### Other confirmed methods/concepts

- `slot_load`
- `slot_sync`
- `init_slot_sync`
- `switch_next_slot`
- `flush_all_filament`
- `runout_button_callback`
- `get_mcu_endstops`
- `disable_stepper`

### Embedded tuning names

Recovered tuning-like names include:

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

### Useful error messages

Recovered examples:

- `QDE_004_001` - slot loading failure
- `QDE_004_002` - extruder already loaded, cannot load another slot
- `QDE_004_003` - slot unloading failure
- `QDE_004_004` - please unload extruder first
- `QDE_004_005` - please load filament to a given slot first
- `QDE_004_006` - extruder loading failure
- `QDE_004_007` - extruder not loaded
- `QDE_004_008` - extruder unloading failure
- `QDE_004_009` - extruder unloading failure
- `QDE_004_011` - filament already loaded, unload first
- `QDE_004_016` - filament exhausted, load the named slot
- `QDE_004_017` - filament flush failed
- `QDE_004_020` - filament unloaded unexpectedly, reload
- `QDE_004_022` - no replaceable slot found
- `QDE_004_025` - extruder unloading failure

Best current conclusion:

- most of the real safety logic for direct load/unload already lives in `box_stepper.so`

## `box_extras.so`

`box_extras.so` appears to be the high-level local QIDI orchestration layer.

### Classes

- `BoxButton`
- `BoxEndstop`
- `BoxExtras`
- `BoxOutput`
- `ToolChange`

### `BoxExtras` commands

- `cmd_BOX_PRINT_START`
- `cmd_INIT_BOX_STATE`
- `cmd_INIT_RFID_READ`
- `cmd_CLEAR_FLUSH`
- `cmd_CLEAR_OOZE`
- `cmd_CLEAR_RUNOUT_NUM`
- `cmd_TIGHTEN_FILAMENT`
- `cmd_RELOAD_ALL`
- `cmd_CUT_FILAMENT`
- `cmd_AUTO_RELOAD_FILAMENT`
- `cmd_RETRY`
- `cmd_RUN_STEPPER`
- `cmd_ENABLE_BOX_DRY`
- `cmd_DISABLE_BOX_DRY`
- `cmd_TRY_RESUME_PRINT`
- `cmd_RESUME_PRINT_1`
- `cmd_disable_box_heater`

### `ToolChange` commands

- `cmd_TOOL_CHANGE_START`
- `cmd_TOOL_CHANGE_END`
- `cmd_CLEAR_TOOLCHANGE_STATE`

### Important embedded strings

Recovered gcode/script fragments include:

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

Best current conclusion:

- `cmd_BOX_PRINT_START` is not a tiny pass-through
- it builds and runs substantial internal gcode scripts

### `CLEAR_FLUSH` and `CLEAR_OOZE`

These two commands are now much better understood.

#### What they are not

- they are not persisted save-variable clears
- they are not large orchestration handlers like `cmd_BOX_PRINT_START`
- they are not implemented by `M1004`

#### Local implementation in `box_extras.so`

Both local handlers are tiny wrappers that resolve `self.gcode` and then call:

- `self.gcode.run_script_from_command(...)`

with a fixed embedded script string.

Best current reconstruction:

```python
def cmd_CLEAR_FLUSH(self, gcmd):
    self.gcode.run_script_from_command(
        "M204 S10000\nG1 X180 F10000\nMOVE_TO_TRASH"
    )
```

```python
def cmd_CLEAR_OOZE(self, gcmd):
    self.gcode.run_script_from_command(
        "M204 S10000\n"
        "G1 X163 F8000\n"
        "G1 X145 F5000\n"
        "G1 X163 F8000\n"
        "G1 X145 F5000\n"
        "G1 X175 F6000\n"
        "G1 X163\n"
        "G1 X175\n"
        "G1 X163\n"
        "G1 X175\n"
        "G1 X163\n"
    )
```

That means these commands do issue real motion locally.

Best current physical interpretation:

- `CLEAR_FLUSH` performs a fast X move and then sends the toolhead to the trash position
- `CLEAR_OOZE` performs a short nozzle-wipe style X oscillation sequence

So despite the names sounding like hidden-state resets, the local implementations are actual canned cleanup motions.

#### Controller-layer behavior

`multi_color_controller.so` contains:

- `cmd_multi_color_clear_flush`
- `cmd_multi_color_clear_ooze`
- `LocalAdapter.clear_flush`
- `LocalAdapter.clear_ooze`
- `RemoteAdapter.clear_flush`
- `RemoteAdapter.clear_ooze`

Best current controller model:

- controller handlers are thin wrappers
- local adapter emits `CLEAR_FLUSH` or `CLEAR_OOZE`
- remote adapter sends remote actions `clear_flush` or `clear_ooze`
- controller code appears to unpack a `(success, message)` style result and report it

I do not currently have proof that the controller wrappers themselves mutate `UnifiedState` directly.

#### Best current semantic meaning

These commands now look like cleanup primitives for vendor-managed purge/wipe phases:

- `CLEAR_FLUSH` is most likely the cleanup motion for the flush/purge phase, probably corresponding to the vendor wipe/old-filament-removal stage
- `CLEAR_OOZE` is most likely the cleanup motion for residual nozzle ooze/drip, implemented as a short wipe pattern

They may still also act as implicit acknowledgements of hidden vendor state, but the strongest direct evidence now is the local motion scripts above.

#### Macro placement

In visible config, they are always called as a pair, always in this order:

- `CLEAR_OOZE`
- `CLEAR_FLUSH`

Visible call sites:

- `config/klipper-macros-qd/filament.cfg` after `M1004` and `G4 P5000` inside `EXTRUSION_AND_FLUSH`
- `config/box.cfg` after unload, small extrusion, and heater-off inside `UNLOAD_FILAMENT`

That placement still supports the idea that they are post-purge/post-unload cleanup motions.

#### `M1004`

`M1004` is not one of the hidden box cleanup handlers.

In this repo, `M1004` is a normal macro in `config/klipper-macros-qd/qd_macro.cfg` that drives:

- `M106 P4`

which maps to the `Polar_cooler` output.

Best current interpretation:

- `M1004` is a cooling aid before the delayed cleanup sequence
- it is not itself the thing that clears flush/ooze state

### `cmd_BOX_PRINT_START` size and significance

Recovered symbol sizes:

- `box_extras.BoxExtras.cmd_BOX_PRINT_START` - about `0x3260`
- `multi_color_controller.MultiColorController.cmd_multi_color_print_start` - about `0x0d6c`
- `multi_color_controller.LocalAdapter.print_start` - about `0x0e94`

Best current conclusion:

- `cmd_BOX_PRINT_START` owns a lot of real sequencing itself
- it does not look like a trivial one-line delegate

### Decoded Cython slots around `cmd_BOX_PRINT_START`

Recovered mstate slot meanings:

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

### Small helper behavior

Best current helper models:

- `get_value_by_key` -> effectively `self.save_variables.allVariables.get(key, default)`
- `get_key_by_value` -> reverse lookup over saved variables, with optional filtering by allowed keys
- `search_index_by_value` -> reverse-maps a stored value back to a generated slot-style key such as `slotN`

Best current conclusion:

- `cmd_BOX_PRINT_START` is reading state from the QIDI `save_variables` model, not hard-coding slot mappings

## `BOX_PRINT_START` behavior

### Call path

Best current active local call path:

- `config/klipper-macros-qd/start_end.cfg:_print_start_box_prepar`
- clear retry/toolchange/runout state
- `BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...`
- `box_extras.BoxExtras.cmd_BOX_PRINT_START`
- hidden scripted orchestration using:
  - `EXTRUDER_UNLOAD`
  - `EXTRUDER_LOAD`
  - `CUT_FILAMENT` / `CUT_FILAMENT_1`
  - `MOVE_TO_TRASH`
  - `M109 S{hotendtemp}`
  - related sensor/init helpers
- low-level execution in `box_stepper.so`
- optional visible `EXTRUSION_AND_FLUSH` after `BOX_PRINT_START` returns

### State that `BOX_PRINT_START` reads

Best current proven read chain:

- target slot -> `get_value_by_key("value_t<EXTRUDER>", "slot16")`
- current slot -> `get_value_by_key("last_load_slot", "slot16")`
- nearby sync state -> `get_value_by_key("slot_sync", "slot-1")`

### High-level branch map

Best current high-level branch map:

- if `target_slot == slot16`: special direct-feed/sentinel path
- else if there is no active loaded path: load-only family
- else if `target_slot == current_slot`: same-slot path
- else: unload-before-load path, with an extra gated choice between:
  - plain unload-before-load
  - cut-then-unload-before-load

### Current best branch/predicate interpretation

Best current interpretation of key business-logic probes:

- one early boolean is most likely a filament-sensor-style `filament_detected` probe
- a later boolean on a looked-up `box_stepper<slot>` object is most likely a loaded-filament state such as `filament_present`
- a saved-variable-driven branch compares `slot_sync` against `last_load_slot`

The `slot_sync` branch is best understood as sync-state validation:

- it uses `get_value_by_key("slot_sync", "slot-1")`
- it happens only after `target_slot == current_slot`
- if `slot_sync != current_slot`, the code appears to take a same-slot reload/resync path instead of trusting the already-loaded state

### Concrete script/template families

Recovered main template families:

#### Load-only

```text
MOVE_TO_TRASH
M109 S{temp}
EXTRUDER_LOAD SLOT={init_load_slot}
```

#### Unload-only

```text
MOVE_TO_TRASH
M109 S{temp}
M400
EXTRUDER_UNLOAD SLOT={unload_slot}
```

#### Cut-then-unload

```text
MOVE_TO_TRASH
M109 S{temp}
M400
CUT_FILAMENT
MOVE_TO_TRASH
EXTRUDER_UNLOAD SLOT={unload_slot}
```

Best current reading:

- the unload families are not the final load step themselves
- the code appears to run one unload family first, then reuse the load-only family afterward

#### Additional prelude templates

Sensor-disable prelude:

```text
DISABLE_ALL_SENSOR
_CG28
MOVE_TO_TRASH
M109 S{hotendtemp}
```

Cut-script prelude:

```text
CUT_FILAMENT_1
MOVE_TO_TRASH
M83
G1 E-60 F300
```

### `slot16` special path

Best current understanding of the `target_slot == slot16` path:

- it is not a no-op
- it is not an immediate load-only fast path
- it executes a short special gcode-side prelude first
- it then falls back into the shared `BOX_PRINT_START` state machine

What that first special block does not seem to do:

- no `box_stepper<slot>` lookup
- no direct formatting of the recovered load/unload templates
- no direct use of `init_load_slot` / `unload_slot` formatter keys in that first block

Best current conclusion:

- `slot16` triggers a distinct direct-feed prelude, then common logic still decides later handling

### What is definitely inside `cmd_BOX_PRINT_START`

- heat/load/unload orchestration
- target/current slot resolution from saved variables
- conditional script selection
- temperature-gating logic
- filament-recognition/error gating around loaded state

### What is not yet proven inside `cmd_BOX_PRINT_START`

- direct `SLOT_RFID_READ` invocation
- direct `BoxRFID` low-level calls
- direct `SAVE_VARIABLE` writes
- exact placement of `CUT_FILAMENT_1` and `DISABLE_ALL_SENSOR` in every branch
- exact predicate that chooses plain unload vs cut-then-unload

### Additional error clues in `box_extras.so`

Recovered examples:

- `QDE_004_010` - current feeding status is incorrect; exit filament from extruder first
- `QDE_004_021` - unable to recognize loaded filament
- `The temperature at the hot end is unstable. Wait for the temperature to stabilize before trying again.`
- `No step to retry`
- `Invalid retry_step format`

Best current conclusion:

- `box_extras.so` owns retry state, recognition checks, and temperature gating around print start

### What `cmd_BOX_PRINT_START` probably does not write

Current best reading:

- it reads `save_variables`
- it does not appear to directly write `SAVE_VARIABLE`
- state resets like `load_retry_num`, `retry_step`, and runout counters happen in `_PRINT_START_BOX_PREPAR`, not inside `cmd_BOX_PRINT_START`

## `box_autofeed.so`

`box_autofeed.so` appears to handle wrapping detection and limit-sensor-driven assist behavior.

### Command surface

- `MCB_CONFIG`
- `MCB_AUTO_START`
- `MCB_AUTO_ABORT`
- `SET_LIMIT_A`
- `cmd_query`

### Related methods

- `_select_slot`
- `_get_slot_stepper`
- `_get_slot_enable_pin_params`
- `qd_get_slot_enable_pin_params`
- `limit_a_event`
- `auto_start`
- `auto_abort`
- `wrapping_detection`
- `wrapping_operate`

### Useful message

- `QDE_004_013` - detected wrapping filament, please check the filament

## `box_rfid.so`

`box_rfid.so` appears to be the low-level RFID reader module.

### Class and methods

- `BoxRFID`
- `_build_config`
- `read_card`
- `read_card_from_slot`
- `_schedule_rfid_read`
- `start_rfid_read`
- `stop_read`

### Low-level reader clues

Recovered FM17550-related strings:

- `config_fm17550 oid=`
- `query_fm17550 oid=%d rest_ticks=0`
- `fm17550_read_card`
- `fm17550_read_card_cb oid=%c`
- `fm17550_read_card_return oid=%c status=%c data=%*s`

Best current conclusion:

- RFID is handled by an MCU-attached FM17550 reader path with asynchronous callback-style reads

### Best current raw return schema

Best current conservative model for `read_card()` / `read_card_from_slot()` return values:

```python
{
    "status": int,
    "data": bytes | str | sequence,
}
```

Best current conclusions:

- `read_card` appears to return the raw FM17550 result object
- `read_card_from_slot` appears to be a thin proxy returning the same shape
- later code parses `data` into higher-level material/color/vendor meaning

### Parsing clues

Recovered parsing-related strings include:

- `split`
- `filament_`
- `color_`
- `vendor_`
- `Unrecognized label read in %s`
- `%s did not recognize the filament`

Best current inference:

- the reader path recognizes symbolic labels like `filament_`, `color_`, and `vendor_`
- values are most likely numeric IDs, not final human-readable names

### Relationship to print start

Current best understanding:

- `cmd_BOX_PRINT_START` is not yet proven to call `BoxRFID` methods directly
- explicit RFID control is more likely through:
  - `cmd_INIT_RFID_READ` in `box_extras.so`
  - `cmd_SLOT_RFID_READ` in `box_stepper.so`
- print start probably consumes recognition results indirectly rather than doing raw RFID I/O inline

### `cmd_INIT_RFID_READ`

Best current understanding:

- `cmd_INIT_RFID_READ` is a high-level slot-scan/init routine in `box_extras.so`
- it does not appear to be the low-level FM17550 parser
- it likely iterates slots, initializes per-slot RFID/material state, and hands later mapping/persistence off to higher-level code

## RFID/material/color/vendor mapping

### What was not found

No static raw RFID UID table or direct tag-value-to-material/color/vendor mapping table was found in:

- `box_rfid.so`
- `multi_color_controller.so`
- `qidiclient`
- client `access/` assets
- client `resource/` assets

### Actual local lookup database

The real material/color/vendor lookup database is:

- `/home/qidi/printer_data/config/officiall_filas_list.cfg`

This path is referenced by both:

- `/home/qidi/klipper/klippy/extras/multi_color_controller.so`
- `/home/qidi/QIDI_Client/bin/qidiclient`

### Best current mapping model

Best current interpretation:

1. `box_rfid.so` reads a spool tag and yields data corresponding to `filament_`, `color_`, and `vendor_`
2. higher-level code maps those numeric IDs through `officiall_filas_list.cfg`
3. results are persisted in saved variables such as:
   - `filament_slotN`
   - `color_slotN`
   - `vendor_slotN`

### `MaterialDatabase`

`multi_color_controller.so` appears to own the config-backed material lookup layer through:

- `MaterialDatabase.load_config`
- `MaterialDatabase.get_fila_dict`
- `MaterialDatabase.get_color_val`
- `MaterialDatabase.get_vendor_val`

Best current source-equivalent model:

- load `/home/qidi/printer_data/config/officiall_filas_list.cfg` with `ConfigParser`
- build in-memory dictionaries for:
  - filament records from `[filaN]`
  - color records from `[colordict]`
  - vendor records from `[vendor_list]`
- expose thin `dict.get(...)` lookup helpers for those maps

Observed edge cases:

- color `0` behaves like `unset` because `[colordict]` has no `0` entry
- vendor `0` is valid and maps to `Generic`
- missing IDs generally look like `None`

### What `officiall_filas_list.cfg` contains

Best current summary:

- `[filaN]` sections with fields such as:
  - `filament`
  - `type`
  - `min_temp`
  - `max_temp`
  - `box_min_temp`
  - `box_max_temp`
- `[colordict]` mapping numeric IDs to hex colors
- `[vendor_list]` mapping numeric IDs to vendor names

Recovered vendor examples:

- `0=Generic`
- `1=QIDI`
- `2=Polymaker`
- `3=Elegoo`
- `4=Bambu`
- `5=Sunlu`
- `6=Ziro`

Recovered filament examples:

- `PLA Rapido`
- `PLA Basic`
- `PETG Basic`
- `PA-CF`
- `PPS-CF`

### Current saved-variable examples on this machine

Best current examples of resolved slot meaning:

- `slot0` -> `PLA Basic`, black, `Generic`
- `slot1` -> `PPS-CF`, black, `Generic`
- `slot2` -> `PLA Basic`, red, `Generic`
- `slot3` -> `PLA Basic`, yellow, `Generic`
- `slot16` -> `PLA Rapido`, vendor `QIDI`, color effectively unset

### Persistence model for RFID-derived values

Best current conclusion:

- RFID read/init itself does not appear to automatically persist the full triplet
- persistence is more likely a separate explicit save-variable path

Best current write sequence:

1. `MULTI_COLOR_INIT_RFID`
2. `MULTI_COLOR_READ_RFID SLOT=<n>`
3. resolve the RFID result into material/color/vendor IDs
4. explicit save calls for:
   - `filament_slot<n>`
   - `color_slot<n>`
   - `vendor_slot<n>`

Current best state-write interpretation:

- `cmd_BOX_PRINT_START` itself appears to read `save_variables`, not write them directly
- `slot_sync` writes appear to happen in lower-level `box_stepper.so` paths such as `slot_sync()` and `sync_unbind_extruder()`
- `last_load_slot` is more likely updated after successful load flows in higher-level controller code, not directly inside `cmd_BOX_PRINT_START`

### Drying metadata

Drying recommendations do not appear to be carried as per-tag RFID metadata in the recovered assets.

Best current conclusion:

- drying presets live separately in `/home/qidi/printer_data/config/drying.conf`
- they are keyed by material type rather than raw RFID value

## Saved-variable model and special sentinels

QIDI extends Klipper `save_variables` with box-specific fields.

Important defaults in `/home/qidi/klipper/klippy/extras/save_variables.py` include:

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
- `filament_slot16`
- `color_slot16`
- `vendor_slot16`

These are directly relevant to `BOX_PRINT_START` because it resolves target/current state through:

- `value_t*`
- `last_load_slot`
- `slot_sync`

### Sentinel meanings

Best current interpretation:

- `slot16` - special non-box/direct-feed sentinel
- `slot-1` - special "no active sync target" sentinel

Current machine examples in `config/saved_variables.cfg`:

- `last_load_slot = 'slot16'`
- `slot_sync = 'slot-1'`

Visible macro evidence that `slot16` is a real direct-feed path:

- `E_UNLOAD SLOT=16` in `M603`
- `E_LOAD SLOT=16 S={hotendtemp}` in `M604`

## Commands and control points useful for direct macros

### Already used in visible config

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

### Present in binaries but not yet exercised here from custom macros

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

If the goal is to use the controller layer but not `BOX_PRINT_START`, useful confirmed controller entry points include:

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

### Controller-side argument clues

Recovered argument requirements include:

- `cmd_multi_color_load` / `cmd_multi_color_unload` / `cmd_multi_color_box_unload` use `SLOT`
- `cmd_multi_color_swap` requires `FROM` and `TO`
- `cmd_multi_color_sync` uses `ACTION`, and starting sync requires `SLOT`
- `cmd_multi_color_set_temp` requires temperature parameters
- `cmd_multi_color_print_start` uses `EXTRUDER` and `HOTENDTEMP`
- `cmd_multi_color_cut_filament` uses `T`
- `cmd_multi_color_tighten` uses `T`
- `cmd_set_save_variable` uses `VARIABLE` and `VALUE`
- `cmd_multi_color_config` appears to accept `MODE`, `PORT`, and `BAUDRATE`

Recovered validation strings include:

- `必须指定SLOT参数` - must specify `SLOT`
- `启动同步必须指定SLOT参数` - starting sync must specify `SLOT`
- `必须指定FROM和TO参数` - must specify `FROM` and `TO`
- `必须指定T参数（工具号）` - must specify `T`
- `未指定温度参数` - no temperature parameter specified
- `未知的ACTION参数:` - unknown `ACTION` parameter

## Practical direct-control conclusion

Best current practical answer:

- it is likely possible to bypass `BOX_PRINT_START` and much of `multi_color_controller` by building custom macros around lower-level vendor commands
- it is not realistic to avoid vendor binaries entirely, because the real feeder, RFID, and autofeed logic live in compiled modules

What can likely be bypassed:

- `BOX_PRINT_START`
- most of `MultiColorController.cmd_multi_color_print_start`
- some retry/resume orchestration

What cannot currently be bypassed in practice:

- `box_stepper.so`
- `box_rfid.so`
- `box_autofeed.so`
- parts of `box_extras.so`

## Best direct-macro strategy

If the goal is to own the sequence instead of using `BOX_PRINT_START`, the cleanest path is probably:

1. keep QIDI's low-level box binaries
2. stop calling `BOX_PRINT_START` for the custom flow
3. build custom macros around a subset of:
   - `INIT_BOX_STATE`
   - `INIT_RFID_READ`
   - optional `CUT_FILAMENT_1` or `CUT_FILAMENT T=<tool>`
   - `EXTRUDER_UNLOAD SLOT=<old-slot>` if needed
   - `EXTRUDER_LOAD SLOT=<new-slot>`
   - `SLOT_RFID_READ SLOT=<slot>` if verification is wanted
   - `EXTRUSION_AND_FLUSH ...` or a custom purge sequence
   - optional `CLEAR_FLUSH`, `CLEAR_OOZE`, `CLEAR_RUNOUT_NUM`

## What is still unresolved

The static reversing has gotten far, but the remaining gaps are mostly in exact branch detail and runtime payloads.

Most important unresolved items:

- the exact remaining truthiness gates inside `cmd_BOX_PRINT_START`
- the exact special gcode/method used in the first `slot16` prelude block
- the exact predicate that selects plain unload vs cut-then-unload
- whether `SLOT_RFID_READ` is ever called directly inside `cmd_BOX_PRINT_START`
- the exact raw RFID `data` payload format beyond `status` + `data`
- whether raw card UIDs are used at all, or whether cards directly encode structured numeric IDs

## Best next evidence source

The next highest-value move is probably not more static disassembly.

Best next step would be live capture or runtime traces while running:

1. `BOX_PRINT_START`
2. `MULTI_COLOR_READ_RFID`
3. `INIT_RFID_READ`

That would likely settle the remaining open questions faster than more static reversing.

## Files referenced in this note

- `config/box.cfg`
- `config/printer.cfg`
- `config/klipper-macros-qd/start_end.cfg`
- `config/klipper-macros-qd/filament.cfg`
- `config/saved_variables.cfg`
- `config/officiall_filas_list.cfg`
- `config/drying.conf`
- `/home/qidi/klipper/klippy/extras/box_config.py`
- `/home/qidi/klipper/klippy/extras/box_extras.so`
- `/home/qidi/klipper/klippy/extras/multi_color_controller.so`
- `/home/qidi/klipper/klippy/extras/box_stepper.so`
- `/home/qidi/klipper/klippy/extras/box_autofeed.so`
- `/home/qidi/klipper/klippy/extras/box_rfid.so`
- `/home/qidi/klipper/klippy/extras/box_detect.so`
- `/home/qidi/klipper/klippy/extras/color_feeder.py`
- `/home/qidi/klipper/klippy/extras/feed_slot.py`
- `/home/qidi/klipper/klippy/extras/save_variables.py`
- `/home/qidi/QIDI_Client/bin/qidiclient`
- `/home/qidi/QIDI_Client/bin/start.sh`
- `/home/qidi/QIDI_Client/bin/tuning.sh`
- `/home/qidi/QIDI_Client/resource/qidi_client_error/...`
