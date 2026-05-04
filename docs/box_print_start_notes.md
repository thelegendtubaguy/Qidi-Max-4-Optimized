# QIDI Box and `BOX_PRINT_START`

## Current config-visible path on this machine

### Stock print-start path

`config/klipper-macros-qd/start_end.cfg`:

```gcode
BOX_PRINT_START EXTRUDER={EXTRUDER} HOTENDTEMP={HOTEND}
M400
EXTRUSION_AND_FLUSH HOTEND={HOTEND}
```

This happens in `_print_start_box_prepar` before later preheat/probing phases.

### Optimized print-start path in this repo

`installer/klipper/tltg-optimized-macros/filament.cfg`:

- reuse branch: does not call `BOX_PRINT_START`
- box-enabled non-reuse branch: calls `BOX_PRINT_START`
- no-box branch: does not call `BOX_PRINT_START`

```gcode
BOX_PRINT_START EXTRUDER={tool} HOTENDTEMP={purge_temp}
M400
OPTIMIZED_EXTRUSION_AND_FLUSH PURGETEMP={purge_temp} CHAMBER={chamber_target}
```

The optimized start path bypasses `BOX_PRINT_START` in the reuse branch and no-box branch, and calls it only in the box-enabled non-reuse branch. Slicer start G-code passes `FIRSTLAYERTEMP=[nozzle_temperature_initial_layer]` and `PURGETEMP={nozzle_temperature_range_high[initial_tool]}` to `OPTIMIZED_START_PRINT_FILAMENT_PREP`; `PURGETEMP` is forwarded to vendor `BOX_PRINT_START` as its required `HOTENDTEMP` parameter and to the rear purge path. The final first-layer temperature remains the later slicer `M109 S[nozzle_temperature_initial_layer]` before the front prime line.

## Active box stack on this machine

`config/printer.cfg` includes `config/box.cfg` and declares `[multi_color_controller]`.

`config/box.cfg` declares:

- `[box_config box0]`
- `[box_extras]`
- `[box_autofeed]`
- `[mcu mcu_box1]`

`config/box.cfg` also defines:

- `T0`..`T15` wrappers around `EXTRUDER_LOAD SLOT={slot}`
- `UNLOAD_T0`..`UNLOAD_T15` wrappers around `EXTRUDER_UNLOAD SLOT={slot}`
- `UNLOAD_FILAMENT`, which uses:
  - `CUT_FILAMENT`
  - `MOVE_TO_TRASH`
  - `UNLOAD_T{T}`
  - `CLEAR_OOZE`
  - `CLEAR_FLUSH`

This printer uses the local MCU-backed box path.

## What `BOX_PRINT_START` is not

- not a visible `[gcode_macro ...]` in repo config
- not defined in the visible Python files:
  - `/home/qidi/klipper/klippy/extras/box_config.py`
  - `/home/qidi/klipper/klippy/extras/color_feeder.py`
  - `/home/qidi/klipper/klippy/extras/feed_slot.py`
- not a client-side gcode template found in `qidiclient`

## Relevant printer-side vendor modules

Under `/home/qidi/klipper/klippy/extras/`:

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

The compiled modules examined for this note are `aarch64` ELF binaries with debug info present.

## Module roles

### `box_extras.so`

Local high-level orchestration layer.

Recovered commands include:

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

`ToolChange` commands:

- `cmd_TOOL_CHANGE_START`
- `cmd_TOOL_CHANGE_END`
- `cmd_CLEAR_TOOLCHANGE_STATE`

### `box_stepper.so`

Low-level feeder / slot / extruder mechanics layer.

Recovered handlers include:

- `cmd_SLOT_UNLOAD`
- `cmd_EXTRUDER_LOAD`
- `cmd_EXTRUDER_UNLOAD`
- `cmd_SLOT_PROMPT_MOVE`
- `cmd_SLOT_RFID_READ`
- `cmd_DIS_STEP`

Other recovered names:

- `slot_load`
- `slot_sync`
- `init_slot_sync`
- `switch_next_slot`
- `flush_all_filament`
- `sync_unbind_extruder`
- `disable_stepper`

### `box_rfid.so`

Low-level RFID reader path.

Recovered names include:

- `BoxRFID`
- `read_card`
- `read_card_from_slot`
- `_schedule_rfid_read`
- `start_rfid_read`
- `stop_read`

FM17550-related strings indicate an MCU-attached, callback-driven reader path.

### `box_autofeed.so`

Autofeed / wrapping-detection / assist path.

Recovered commands include:

- `MCB_CONFIG`
- `MCB_AUTO_START`
- `MCB_AUTO_ABORT`
- `SET_LIMIT_A`
- `cmd_query`

Related names include:

- `_select_slot`
- `_get_slot_stepper`
- `limit_a_event`
- `auto_start`
- `auto_abort`
- `wrapping_detection`
- `wrapping_operate`

### `box_detect.so`

Box MCU detection and config-file update plumbing, not the main material-prep path.

Recovered names include:

- `get_config_mcu_serials`
- `get_check_serials_id`
- `monitor_serial_by_id`
- `_update_config_file`
- `_request_restart`

## `multi_color_controller.so`

General controller/state-machine layer, not just a print-start helper.

Recovered classes include:

- `UnifiedState`
- `TaskQueueManager`
- `BaseAdapter`
- `LocalAdapter`
- `RemoteAdapter`
- `MultiColorController`

Recovered handlers include:

- `cmd_query_multi_color`
- `cmd_multi_color_load`
- `cmd_multi_color_unload`
- `cmd_multi_color_swap`
- `cmd_multi_color_dry`
- `cmd_multi_color_read_rfid`
- `cmd_multi_color_sync`
- `cmd_multi_color_config`
- `cmd_multi_color_box_unload`
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

Recovered state vocabulary includes:

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

### Local vs remote backend split

Recovered descriptions explicitly refer to:

- `LocalAdapter` - direct control of existing Klipper components
- `RemoteAdapter` - communicates with the second-generation box

Active path on this printer: local MCU-backed.

## Remote USB JSON path

The second-generation remote path uses newline-delimited JSON over USB serial.

Strings in `multi_color_controller.so` include:

- `/dev/ttyACM*`
- `/dev/ttyUSB*`
- `json`
- `dumps`
- `loads`
- `Serial`
- `baudrate`
- `timeout`
- `write_timeout`
- `readline`
- `in_waiting`
- `_send_command`
- `_process_message`
- `_send_heartbeat`
- `_find_box_port`

A literal frame present in the binary:

```json
{"cmd":"ping"}\n
```

General frame model:

```json
{"cmd_id":"...","action":"print_start","params":{...}}\n
```

Recovered action-like strings include:

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

## `qidiclient`

Main process:

- `/home/qidi/QIDI_Client/bin/qidiclient`

Launch script:

```text
taskset -c 0 /home/qidi/QIDI_Client/bin/qidiclient
```

Useful strings show it is primarily a Moonraker/Klipper-facing UI/client process:

- `org.qidi.moonraker`
- `org.qidi.klipper`
- `jsonrpc`
- `application/json`
- `Initial klipper state: {}`
- `Updated klipper state: {}`
- `Failed to parse klipper state from response`

It also contains awareness of:

- `/home/qidi/printer_data/config/box.cfg`
- `/home/qidi/printer_data/config/officiall_filas_list.cfg`
- save-variable names such as `enable_box`, `last_load_slot`, `slot_sync`, `filament_slot16`, `color_slot16`, `vendor_slot16`
- client-side `MULTI_COLOR_*` gcode templates for manual UI flows

`BOX_PRINT_START` was not found in `qidiclient`.
`MULTI_COLOR_PRINT_START` was not found in `qidiclient`.

Print-start material preparation enters through Klipper/vendor command paths.

## `BOX_PRINT_START` behavior

### Local call path

```text
macro/slicer call
-> BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...
-> box_extras.BoxExtras.cmd_BOX_PRINT_START
-> hidden local script selection/orchestration
-> lower-level feeder/extruder work in box_stepper.so
-> later visible purge/cleanup path
```

Later visible purge/cleanup is:

- stock path: `EXTRUSION_AND_FLUSH`
- optimized path: `OPTIMIZED_EXTRUSION_AND_FLUSH`

### State it reads

State reads visible from recovered strings and call structure:

- target slot -> `value_t<EXTRUDER>`
- current slot -> `last_load_slot`
- sync state -> `slot_sync`

Meaning:

- target slot = what the requested tool should use
- current slot = last loaded slot
- sync state = whether the loaded path is bound/trusted

### High-level branch map

Branch model:

- if `target_slot == slot16`: special direct-feed sentinel path
- else if there is no active loaded path: load-only family
- else if `target_slot == current_slot`: same-slot path
- else: unload-before-load family
  - with an additional gated choice between plain unload and cut-then-unload

### Recovered script/template families

#### Load-only family

```text
MOVE_TO_TRASH
M109 S{temp}
EXTRUDER_LOAD SLOT={init_load_slot}
```

#### Unload-only family

```text
MOVE_TO_TRASH
M109 S{temp}
M400
EXTRUDER_UNLOAD SLOT={unload_slot}
```

#### Cut-then-unload family

```text
MOVE_TO_TRASH
M109 S{temp}
M400
CUT_FILAMENT
MOVE_TO_TRASH
EXTRUDER_UNLOAD SLOT={unload_slot}
```

The unload families appear to run before the later load step.

### Additional preludes

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

### `slot16`

`slot16` is not a no-op and not just a normal slot.

Reading of the `slot16` path:

- it is a direct-feed sentinel path
- it triggers a distinct prelude before common logic continues
- it does not look like a simple ordinary `EXTRUDER_LOAD SLOT=slot16` path

Visible macro evidence for `slot16` as the direct-feed/sentinel path:

- `E_UNLOAD SLOT=16` in `config/klipper-macros-qd/filament.cfg`
- `E_LOAD SLOT=16 S={hotendtemp}` in `config/klipper-macros-qd/filament.cfg`

### What `cmd_BOX_PRINT_START` clearly owns

- slot resolution from saved variables
- temperature-gated load/unload orchestration
- script/template selection
- gating around loaded-state / recognition / retry conditions

### Unresolved

- exact truthiness gates for every branch
- exact first special prelude used by the `slot16` path
- exact predicate choosing plain unload vs cut-then-unload
- whether `SLOT_RFID_READ` is called directly inside `cmd_BOX_PRINT_START`
- whether `cmd_BOX_PRINT_START` writes saved variables directly

## `CLEAR_FLUSH` and `CLEAR_OOZE`

These are not visible config macros. They are vendor commands implemented in `box_extras.so`.

They are not:

- save-variable cleanup helpers
- `M1004`
- large orchestration handlers like `cmd_BOX_PRINT_START`

### Local implementation shape

Recovered local behavior is small and motion-oriented.

Approximate local `CLEAR_FLUSH` behavior:

```python
self.gcode.run_script_from_command(
    "M204 S10000\nG1 X180 F10000\nMOVE_TO_TRASH"
)
```

Approximate local `CLEAR_OOZE` behavior:

```python
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

Behavior implied by the recovered local scripts:

- `CLEAR_FLUSH` = flush cleanup move that ends by sending the toolhead back to the trash/wipe position
- `CLEAR_OOZE` = short X-axis wipe pattern for residual ooze

### Current visible placement in this repo

Current visible call sites include:

- `installer/klipper/tltg-optimized-macros/filament.cfg`
  - after `OPTIMIZED_M1004` + `G4 P5000` inside `OPTIMIZED_EXTRUSION_AND_FLUSH`
  - during staged post-flush cleanup in `OPTIMIZED_START_PRINT_FILAMENT_PREP`; that path re-homes Z with `_OPTIMIZED_HOME_Z_FROM_SAFE_POINT` before the rear-bed scrape motion
  - inside `OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE` when `printer["box_extras"]` is defined; that helper re-homes Z with `_OPTIMIZED_HOME_Z_FROM_SAFE_POINT` before the rear-bed scrape motion
  - after `OPTIMIZED_UNLOAD_FILAMENT`
- `config/box.cfg`
  - after unload / short extrusion / heater-off inside `UNLOAD_FILAMENT`

## `M1004`

In this repo, `M1004` is a normal visible macro in `config/klipper-macros-qd/qd_macro.cfg` that drives:

- `M106 P4`

In the optimized layer, `OPTIMIZED_M1004` does the same thing but defaults the polar cooler off when the saved variable is unset.

`M1004` is a polar-cooler helper, not a hidden vendor cleanup primitive.

## RFID, material, color, vendor mapping

### Low-level reader side

The low-level reader lives in `box_rfid.so`.

Raw return model:

```python
{
    "status": int,
    "data": bytes | str | sequence,
}
```

### Lookup database

Actual local lookup DB used by both printer-side and client-side code:

- `config/officiall_filas_list.cfg`

Material, color, and vendor IDs are resolved through `config/officiall_filas_list.cfg`.

Mapping flow:

1. RFID path yields identifiers corresponding to material/color/vendor
2. higher-level code resolves those IDs through `officiall_filas_list.cfg`
3. results are stored in save variables such as:
   - `filament_slotN`
   - `color_slotN`
   - `vendor_slotN`

### `MaterialDatabase`

`multi_color_controller.so` contains a config-backed lookup layer with methods like:

- `MaterialDatabase.load_config`
- `MaterialDatabase.get_fila_dict`
- `MaterialDatabase.get_color_val`
- `MaterialDatabase.get_vendor_val`

### Drying metadata

Drying presets appear separate from RFID data and live in:

- `config/drying.conf`

## Saved-variable model and sentinels

Important QIDI box-related save-variable extensions include:

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

Sentinel meanings:

- `slot16` = direct-feed / non-box sentinel path
- `slot-1` = unsynced / no active sync target sentinel

These matter directly to `BOX_PRINT_START` branch selection.

## Sync semantics

`slot_sync` is not just metadata.

Observed branch behavior:

- if `target_slot == current_slot` but `slot_sync != current_slot`, print start does not trust the already-loaded path
- same-slot state can still trigger reload/resync behavior

Recovered lower-level sync methods in `box_stepper.so`:

- `slot_sync`
- `init_slot_sync`
- `sync_unbind_extruder`

Recovered method names imply:

- `slot_sync` = bind/sync operation between slot and extruder path
- `sync_unbind_extruder` = unbind path
- both persisted `slot_sync` and in-memory sync state matter

Recovered controller-side sync surface:

- `cmd_multi_color_sync`
- `sync_to_extruder`
- `unsync_from_extruder`

Controller-side operation names imply:

- `sync_to_extruder(slot)` binds a slot to the active extruder path
- `unsync_from_extruder()` clears that binding and returns toward the unsynced sentinel state

## Commands visible in config and usable from custom macros

### Already visible in config

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

### Repo custom wrappers

- `TLTG_SET_BOX_TEMP BOX=<number> TARGET=<temp>` validates `heater_generic heater_box<number>` and calls `SET_HEATER_TEMPERATURE HEATER=heater_box<number> TARGET=<temp>`.
- `OPTIMIZED_DISABLE_BOX_HEATER` calls `DISABLE_BOX_HEATER` only when `printer["box_extras"]` is defined.

### Present in binaries but not central to the current custom flow here

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
- `MCB_CONFIG SLOT=slotN`
- `MCB_AUTO_START`
- `MCB_AUTO_ABORT`
- `SET_LIMIT_A`

## What can be bypassed and what cannot

### Can be bypassed

Higher-level sequencing in this repo already bypasses:

- `BOX_PRINT_START`
- much of the higher-level `MultiColorController` print-start wrapper logic
- some vendor retry/resume orchestration

### Cannot realistically be bypassed

Physical box mechanics depend on vendor binaries:

- `box_stepper.so`
- `box_rfid.so`
- `box_autofeed.so`
- at least some vendor logic in `box_extras.so`

## Custom macro path without `BOX_PRINT_START`

Sequence:

1. keep QIDI low-level box binaries
2. do not call `BOX_PRINT_START` in the custom path
3. build custom macros around selected lower-level commands

Useful building blocks:

- `INIT_BOX_STATE`
- `INIT_RFID_READ`
- optional `CUT_FILAMENT_1` or `CUT_FILAMENT T=<tool>`
- `EXTRUDER_UNLOAD SLOT=<old-slot>` if needed
- `EXTRUDER_LOAD SLOT=<new-slot>`
- optional `SLOT_RFID_READ SLOT=<slot>` if verification is needed
- `OPTIMIZED_EXTRUSION_AND_FLUSH ...` or another custom purge sequence
- optional `CLEAR_FLUSH`, `CLEAR_OOZE`, `CLEAR_RUNOUT_NUM`

## Highest-value unresolved questions

- exact remaining gates inside `cmd_BOX_PRINT_START`
- exact first `slot16` prelude block
- exact predicate for plain unload vs cut-then-unload
- whether `SLOT_RFID_READ` is ever called directly inside `cmd_BOX_PRINT_START`
- exact raw RFID `data` format beyond `status` + `data`
- whether raw tag UIDs are used directly at all, or whether tags already encode structured material/color/vendor IDs

Next evidence source: runtime capture while executing:

1. `BOX_PRINT_START`
2. `MULTI_COLOR_READ_RFID`
3. `INIT_RFID_READ`

## Files referenced here

Current repo files:

- `config/printer.cfg`
- `config/box.cfg`
- `config/klipper-macros-qd/start_end.cfg`
- `config/klipper-macros-qd/filament.cfg`
- `installer/klipper/tltg-optimized-macros/filament.cfg`
- `config/officiall_filas_list.cfg`
- `config/drying.conf`
- `config/saved_variables.cfg`

Vendor/client/runtime paths referenced by reversing work:

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
