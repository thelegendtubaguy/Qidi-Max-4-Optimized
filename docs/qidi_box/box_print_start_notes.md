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

The optimized start path bypasses `BOX_PRINT_START` in the reuse branch and no-box branch, and calls it only in the box-enabled non-reuse branch. Slicer start G-code passes `FIRSTLAYERTEMP=[nozzle_temperature_initial_layer]` and `PURGETEMP={nozzle_temperature_range_high[initial_tool]}` to `OPTIMIZED_START_PRINT_FILAMENT_PREP`; `PURGETEMP` is forwarded to vendor `BOX_PRINT_START` as its required `HOTENDTEMP` parameter and to the rear purge path. Slicer start G-code emits `T[initial_tool]` before the front prime line so Orca/QIDI Studio annotate the startup extrusion with the selected initial object filament. The final first-layer temperature remains the later slicer `M109 S[nozzle_temperature_initial_layer]` before the front prime line.

`OPTIMIZED_END_PRINT_FILAMENT_PREP` records retained filament from `slot_sync` when QIDI Box reports an active synced slot. The macro reverse-maps that slot through `value_t0`..`value_t15` before writing `retained_tool`, so a vendor auto-runout reload from `slot0` to `slot1` can be reused by a later print whose slicer initial tool maps to `slot1`.

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
  - during staged post-flush cleanup in the `OPTIMIZED_START_PRINT_FILAMENT_PREP` box-enabled branch before `OPTIMIZED_WAIT_BED`, `Z_TILT_ADJUST`, and `_OPTIMIZED_G29_HOME_Z_OR_FULL`
  - inside `OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE` when `printer["box_extras"]` is defined; the helper runs `CLEAR_OOZE` and `CLEAR_FLUSH` before the rear-bed scrape motion without Z rehoming
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
- optimized retained-filament state uses `slot_sync` as the active loaded-slot signal at end print and requires `slot_sync == retained_slot` at the next start before bypassing `BOX_PRINT_START`

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

## Vendor commands visible in config and binaries

Commands visible in config or recovered from vendor modules:

- `BOX_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temp>`
- `EXTRUDER_LOAD SLOT=slotN`
- `EXTRUDER_UNLOAD SLOT=slotN`
- `SLOT_UNLOAD SLOT=slotN`
- `SLOT_RFID_READ SLOT=slotN`
- `E_LOAD SLOT=N S=<temp>`
- `E_UNLOAD SLOT=N`
- `E_BOX SLOT=N`
- `CUT_FILAMENT T=<tool>`
- `CUT_FILAMENT_1`
- `INIT_BOX_STATE`
- `INIT_RFID_READ`
- `CLEAR_TOOLCHANGE_STATE`
- `CLEAR_FLUSH`
- `CLEAR_OOZE`
- `CLEAR_RUNOUT_NUM`
- `RUN_STEPPER STEPPER=...`
- `ENABLE_BOX_DRY BOX=...`
- `DISABLE_BOX_DRY BOX=...`
- `RELOAD_ALL`
- `AUTO_RELOAD_FILAMENT`
- `RETRY`
- `TRY_RESUME_PRINT`
- `RESUME_PRINT_1`
- `TIGHTEN_FILAMENT`
- `TOOL_CHANGE_START`
- `TOOL_CHANGE_END`
- `MCB_CONFIG SLOT=slotN`
- `MCB_QUERY`
- `MCB_AUTO_START`
- `MCB_AUTO_ABORT`
- `SET_LIMIT_A STATE=<0|1>`

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

## Additional compiled-module findings from local capture

Current conclusions: `docs/qidi_box/qidi_box_current_conclusions.md`.
Active include wiring: `docs/qidi_box/qidi_box_active_include_wiring.md`.
Recovered constants: `docs/qidi_box/qidi_box_recovered_constants.md`.
Compiled-module reference: `docs/qidi_box/qidi_box_compiled_module_reference.md`.
Static disassembly notes: `docs/qidi_box/qidi_box_static_disassembly_notes.md`.
Error code reference: `docs/qidi_box/qidi_box_error_code_reference.md`.
Speed/timing control matrix: `docs/qidi_box/qidi_box_speed_timing_control_matrix.md`.
Stepper state-method reference: `docs/qidi_box/qidi_box_stepper_state_methods_reference.md`.
QIDI Box reversing artifact validator: `scripts/check_qidi_box_reversing_artifacts.py`.
Runtime capture analyzer: `scripts/analyze_qidi_box_runtime_capture.py`.
Stock config surface: `docs/qidi_box/qidi_box_stock_config_surface.md`.
Generated config reference: `docs/qidi_box/qidi_box_generated_config_reference.md`.
Control ownership matrix: `docs/qidi_box/qidi_box_control_ownership_matrix.md`.
Stock call graph: `docs/qidi_box/qidi_box_stock_call_graph.md`.
Runtime observations: `docs/qidi_box/qidi_box_runtime_observations.md`.
G-code command surface: `docs/qidi_box/qidi_box_gcode_command_surface.md`.
Command risk matrix: `docs/qidi_box/qidi_box_command_risk_matrix.md`.
Status schema reference: `docs/qidi_box/qidi_box_status_schema_reference.md`.
QIDI Client findings: `docs/qidi_box/qidi_box_qidiclient_findings.md`.

Local capture artifacts are under `tmp/qidi-box-reversing/20260507-135653-printer-capture/`; `tmp/` is ignored by git and contains unredacted runtime config/log captures.

`box_stepper.so` exposes these module constants through Python introspection:

- `DISABLE_DELAY = 0.05`
- `HOMING_START_DELAY = 0.001`
- `ENDSTOP_SAMPLE_COUNT = 4`
- `ENDSTOP_SAMPLE_TIME = 0.000015`

`BoxExtruderStepper` method signatures recovered by importing the module in the printer's Klipper Python environment:

- `do_move(self, movepos, speed, accel=50)`
- `do_move_double_steps(self, v1, l1, v2, l2, accel)`
- `do_move_triple_steps(self, v1, l1, v2, l2, v3, l3, accel)`
- `do_home(self, endstops, movepos, speed, accel, triggered)`
- `do_home_double_steps(self, endstops, l1, l2, v1, v2, accel, triggered)`
- `do_home_three_steps(self, endstops, l1, l2, l3, v1, v2, v3, accel, triggered)`
- `slot_load(self)`
- `cmd_SLOT_UNLOAD(self, gcmd)`
- `cmd_EXTRUDER_LOAD(self, gcmd)`
- `cmd_EXTRUDER_UNLOAD(self, gcmd, need_output_state=False)`
- `slot_sync(self, value, sync_to_extruder=False)`
- `init_slot_sync(self)`

A monkeypatched harness around `box_stepper.so` recovered these low-level motion calls for common branches:

- `slot_load()` with the slot runout/endstop state set calls `do_home(..., 3000, 80, 50, False)`, then `do_move(-260, 80, 50)`, then `disable_stepper()`.
- `slot_load()` without the slot runout/endstop state set calls `disable_stepper()` only in the harnessed branch.
- `cmd_SLOT_UNLOAD SLOT=slot0` calls `do_home(..., -3000, 100, 50, True)`, then `disable_stepper()`.
- `cmd_EXTRUDER_LOAD SLOT=slot0` calls `do_home(..., 3000, 85, 50, False)` only when the harnessed `b_endstop_state` is set, then `disable_stepper()`, `dwell(0.05)`, and `sync_print_time()`.
- `cmd_EXTRUDER_UNLOAD SLOT=slot0` calls `do_home_double_steps(..., -350, -1150, 65, 85, 100, True)`, then two `do_home(..., -1500, 65, 50, True)` calls, then `disable_stepper()`.
- `cmd_EXTRUDER_UNLOAD SLOT=slot0` runs visible toolhead cleanup scripts containing `G1 Y380 F9000`, `G1 X3 F9000`, `G1 X3 Y17 F15000`, the `shake_for_unload_toolhead` wipe pattern, `MOVE_TO_TRASH`, and `M400`.

The harnessed `box_stepper.so` branches show that load/unload speeds and distances are hardcoded inside `box_stepper.so`; `config/box.cfg` exposes pin mapping, `rotation_distance`, `microsteps`, and heater/sensor pins, but does not expose `slot_load_length_*`, `extruder_load_length_*`, `extruder_unload_length_*`, or `multi_extruder_*` values as config options.

`multi_color_controller.LocalAdapter` maps controller operations to local Klipper/vendor G-code commands:

- `load_filament('slot0')` -> `E_LOAD SLOT=0`
- `unload_filament('slot0')` -> `E_UNLOAD SLOT=0`
- `swap_filament('slot0', 'slot1')` -> `E_UNLOAD SLOT=0`, then `E_LOAD SLOT=1`
- `start_drying(1, 50, 2)` -> `ENABLE_BOX_DRY BOX=1 TEMP=50 END_TIME=2`
- `stop_drying(1)` -> `DISABLE_BOX_DRY BOX=1`
- `read_rfid('slot0')` -> `SLOT_RFID_READ SLOT=slot0`
- `sync_to_extruder('slot0')` -> `SAVE_VARIABLE VARIABLE=slot_sync VALUE='slot0'`
- `unsync_from_extruder()` -> `SAVE_VARIABLE VARIABLE=slot_sync VALUE='slot16'`
- `box_unload('slot0')` -> `E_BOX SLOT=0`
- `init_rfid()` -> `INIT_RFID_READ`
- `reload_all(1)` -> `RELOAD_ALL FIRST=1`
- `auto_reload()` -> `AUTO_RELOAD_FILAMENT`
- `retry(1)` -> `TRY_MOVE_AGAIN RFID=1`
- `tighten(2)` -> `TIGHTEN_FILAMENT T=2`
- `print_start(3, 240)` -> `BOX_PRINT_START EXTRUDER=3 HOTENDTEMP=240`
- `try_resume()` -> `TRY_RESUME_PRINT`
- `resume_print(220)` -> `RESUME_PRINT_1 S=220`
- `init_mapping()` -> `INIT_MAPPING_VALUE`
- `disable_heater()` -> `DISABLE_BOX_HEATER`
- `set_temp({'BOX': 1, 'TARGET': 55})` -> `BOX_TEMP_SET BOX=1 TARGET=55`
- `clear_runout()` -> `CLEAR_RUNOUT_NUM`
- `clear_flush()` -> `CLEAR_FLUSH`
- `clear_ooze()` -> `CLEAR_OOZE`
- `cut_filament(2)` -> `CUT_FILAMENT T=2`

`multi_color_controller.RemoteAdapter` maps controller operations to USB JSON command dictionaries before newline-delimited serial transport:

- `load_filament('slot0')` -> `{"cmd":"load_filament","slot":0,"options":{},"timestamp":...,"id":"cmd_..."}`
- `unload_filament('slot0')` -> `{"cmd":"unload_filament","slot":0,"options":{},"timestamp":...,"id":"cmd_..."}`
- `swap_filament('slot0','slot1')` -> `{"cmd":"swap_filament","from_slot":0,"to_slot":1,"options":{},"timestamp":...,"id":"cmd_..."}`
- `start_drying(1,50,2)` -> `{"cmd":"start_drying","box":1,"temp":50,"hours":2,"timestamp":...,"id":"cmd_..."}`
- `stop_drying(1)` -> `{"cmd":"stop_drying","box":1,"timestamp":...,"id":"cmd_..."}`
- `read_rfid('slot0')` -> `{"cmd":"read_rfid","slot":0,"timestamp":...,"id":"cmd_..."}`
- `sync_to_extruder('slot0')` -> `{"cmd":"sync_to_extruder","slot":0,"timestamp":...,"id":"cmd_..."}`
- `unsync_from_extruder()` -> `{"cmd":"unsync_from_extruder","timestamp":...,"id":"cmd_..."}`
- `box_unload('slot0')` -> `{"cmd":"box_unload","slot":0,"timestamp":...,"id":"cmd_..."}`
- `init_rfid()` -> `{"cmd":"init_rfid","timestamp":...,"id":"cmd_..."}`
- `reload_all(1)` -> `{"cmd":"reload_all","first":1,"timestamp":...,"id":"cmd_..."}`
- `auto_reload()` -> `{"cmd":"auto_reload","timestamp":...,"id":"cmd_..."}`
- `retry(1)` -> `{"cmd":"retry","rfid":1,"timestamp":...,"id":"cmd_..."}`
- `tighten(2)` -> `{"cmd":"tighten","tool":2,"timestamp":...,"id":"cmd_..."}`
- `print_start(3,240)` -> `{"cmd":"print_start","extruder":3,"hotendtemp":240,"timestamp":...,"id":"cmd_..."}`
- `try_resume()` -> `{"cmd":"try_resume","timestamp":...,"id":"cmd_..."}`
- `resume_print(220)` -> `{"cmd":"resume_print","temp":220,"timestamp":...,"id":"cmd_..."}`
- `init_mapping()` -> `{"cmd":"init_mapping","timestamp":...,"id":"cmd_..."}`
- `disable_heater()` -> `{"cmd":"disable_heater","timestamp":...,"id":"cmd_..."}`
- `set_temp({'BOX':1,'TARGET':55})` -> `{"cmd":"set_temp","temp_params":{"BOX":1,"TARGET":55},"timestamp":...,"id":"cmd_..."}`
- `clear_runout()` -> `{"cmd":"clear_runout","timestamp":...,"id":"cmd_..."}`
- `clear_flush()` -> `{"cmd":"clear_flush","timestamp":...,"id":"cmd_..."}`
- `clear_ooze()` -> `{"cmd":"clear_ooze","timestamp":...,"id":"cmd_..."}`
- `cut_filament(2)` -> `{"cmd":"cut_filament","tool":2,"timestamp":...,"id":"cmd_..."}`

The remote path uses `RemoteAdapter(port=None, baudrate=115200)`, searches `/dev/ttyACM*` and `/dev/ttyUSB*`, and sends a literal heartbeat/probe frame `{"cmd":"ping"}\n`.

`multi_color_controller.BoxState` enum values recovered by introspection:

- `EMPTY = 0`
- `LOADED = 1`
- `IN_EXTRUDER = 2`
- `IN_FEEDER = 3`
- `ERROR = -1`
- `UNKNOWN = -2`
- `PENDING = -3`

`multi_color_controller.ConnectionMode` enum values recovered by introspection:

- `LOCAL = "local"`
- `REMOTE = "remote"`

`multi_color_controller.UnifiedState().to_dict()` default state contains these top-level sections:

- `system`: `ready`, `mode`
- `hardware`: `box_count`, `connected`
- `slots`: `states`, `materials`, `last_loaded`
- `extruder`: `loaded`, `target`, `filament_detected`
- `operation`: `current`, `progress`, `error`, `box_button_state`, `operate_state`, `steps`, `is_waiting_user`
- `print`: `printing`, `current_tool`, `next_tool`
- `rfid`: `reading`, `results`
- `drying`: per-box drying state map
- `sensors`: `b_endstop`, `e_endstop`, `runout_sensors`, `pressure_sensor`
- `config_summary`: `enable_box`, `auto_reload_detect`, `auto_read_rfid`, `auto_init_detect`, `slot_sync`, `retry_step`, `load_retry_num`

`multi_color_controller.TaskQueueManager.FLOW_MAP` recovered by introspection:

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

Additional `box_extras.so` command behavior recovered by a fake Klipper harness:

- `cmd_CLEAR_FLUSH` runs `M204 S10000\nG1 X180 F10000\nMOVE_TO_TRASH`.
- `cmd_CLEAR_OOZE` runs `M204 S10000` followed by the X-axis wipe pattern `G1 X163 F8000`, `G1 X145 F5000`, `G1 X163 F8000`, `G1 X145 F5000`, `G1 X175 F6000`, then repeated `G1 X163` / `G1 X175` moves ending at `G1 X163`.
- `cmd_CLEAR_RUNOUT_NUM` writes `runout_0 = 0` through `runout_15 = 0` via `save_variable()`.
- `cmd_BOX_PRINT_START` first runs `CLEAR_TOOLCHANGE_STATE`.
- `cmd_BOX_PRINT_START` writes `load_retry_num = 0`, `retry_step = None`, `runout_0`..`runout_15 = 0`, and `extrude_state = -1` before testing `enable_box`.
- `cmd_BOX_PRINT_START` returns after initialization when `enable_box` resolves to `0`.
- Harnessed `cmd_BOX_PRINT_START EXTRUDER=0 HOTENDTEMP=240` with `enable_box=1`, `value_t0=slot0`, `last_load_slot=slot-1`, `slot_sync=slot-1`, `b_endstop_state=0`, and `e_endstop_state=0` emitted `MOVE_TO_TRASH\nM109 S240\nM400\nEXTRUDER_UNLOAD SLOT=slot-1\n` before the harness stopped at missing `toolhead.wait_moves`.
- Harnessed `cmd_BOX_PRINT_START EXTRUDER=0 HOTENDTEMP=240` with `enable_box=1`, `b_endstop_state=1`, and `e_endstop_state=1` emitted `MOVE_TO_TRASH\nM109 S240\nEXTRUDER_LOAD SLOT=<target>\n` for `value_t0` targets `slot0`, `slot1`, and `slot16`.
- The `cmd_BOX_PRINT_START` harness is not a complete branch proof because object state from `BoxExtras.__init__`, real `toolhead`, real filament sensor helpers, and real stepper objects were substituted with fakes.

`box_autofeed.so` config reads and defaults recovered by a fake Klipper harness:

- `limit_pin`: required; current runtime value in `config/box.cfg` is `^!mcu_box1:PB0`
- `debounce_us`: default `200000.0`
- `limit_polarity`: default `0`
- `default_ticks`: default `8400`
- `v_feed`: default `2000`; current runtime value in `config/box.cfg` is `100`
- `lmax`: default `10000`; current runtime value in `config/box.cfg` is `120`
- `dir`: default `1`; current runtime value in `config/box.cfg` is `0`
- `a_feed`: default `0.0`

`box_autofeed.parse_pin_desc()` converts STM32-style pin strings into `PinSpec(chip, index, invert, pullup, opendrain, port, pin)` records:

- `^!mcu_box1:PB0` -> `chip=mcu_box1`, `port=B`, `pin=0`, `index=16`, `invert=1`, `pullup=1`, `opendrain=0`
- `mcu_box1:PC14` -> `chip=mcu_box1`, `port=C`, `pin=14`, `index=46`, `invert=0`, `pullup=0`, `opendrain=0`
- `!mcu_box1:PC15` -> `chip=mcu_box1`, `port=C`, `pin=15`, `index=47`, `invert=1`, `pullup=0`, `opendrain=0`
- `^PA0` -> `chip=""`, `port=A`, `pin=0`, `index=0`, `invert=0`, `pullup=1`, `opendrain=0`

`box_autofeed.so` registers G-code commands:

- `MCB_CONFIG`
- `MCB_QUERY`
- `SET_LIMIT_A`
- `MCB_AUTO_START`
- `MCB_AUTO_ABORT`

`box_autofeed.so` registers these MCU response handlers per autofeed device OID:

- `MCB_STATE` -> `MCBAutoFeed._on_state`
- `MCB_DONE` -> `MCBAutoFeed._on_done`
- `MCB_ERROR` -> `MCBAutoFeed._on_error`

`box_autofeed.so` emits these MCU config/runtime commands:

- config command: `mcb_config oid=<oid>`
- command lookup: `mcb_config_stepper oid=%c stepper_oid=%c`
- command lookup: `mcb_query oid=%c clock=%u rest_ticks=%u retransmit_count=%c invert=%c`
- command lookup: `mcb_auto_start oid=%c v=%u a=%u lmax=%u dir=%i enable=%i invert=%i`
- command lookup: `mcb_auto_abort oid=%c`
- command lookup: `set_limit_a oid=%c state=%c`

Harnessed `box_autofeed.auto_start(100, 200, 120, 0, slot0_stepper)` with a fake `step_dist=0.01` and `enable_pin=!mcu_box1:PC15` sent:

```text
mcb_config_stepper [oid, 77]
mcb_query [oid, 0, 8400, 0, 0]
mcb_auto_start [oid, 10000, 20000, 12000, 0, 47, 1]
```

The `mcb_auto_start` values imply `v`, `a`, and `lmax` are converted from millimeters to step units by dividing by `step_dist`; `enable=47` is the parsed `PC15` index and `invert=1` comes from the `!` prefix.

`MCBAutoFeed` tracks these runtime fields in `__dict__`:

- `a_pin`
- `debounce_us`
- `limit_polarity`
- `default_ticks`
- `v_feed`
- `lmax`
- `dir`
- `a_feed`
- `limit_a_state`
- `wrapping_num`
- `bind_stepper`
- `active_slot`
- `_last_limit_a_event_time`
- `_dev_by_mcu`
- `_slot_mcu_cache`
- `stepper_dev`
- `irq_btn`

`box_autofeed.so` string evidence maps wrapping detection to `Code:QDE_004_013; Message:Detected wrapping filament,please check the filament.` and `send_pause_command`; the exact event-count gate remains unresolved.

`box_rfid.so` config/runtime behavior recovered by a fake Klipper harness:

- object name `box_rfid card_reader_1` sets `name = card_reader_1`
- `max_read_time = 30.0`
- `rfid_read_attempts = 0` at initialization
- `rfid_read_start_time = 0` at initialization
- `get_message_count = 1` at initialization
- `had_get_value = False` at initialization

`box_rfid.so` emits these MCU commands:

- startup command: `query_fm17550 oid=<oid> rest_ticks=0` with `on_restart=True`
- config command: `config_fm17550 oid=<oid> spi_oid=<spi_oid>`
- query command: `fm17550_read_card_cb oid=%c` / response `fm17550_read_card_return oid=%c status=%c data=%*s`

Harnessed `read_card()`, `read_card_from_slot()`, and `_schedule_rfid_read()` each sent `[oid]` through the `fm17550_read_card_cb` query command. `start_rfid_read(stepper)` stores the passed stepper reference before scheduling reads.

Behavior implication: local RFID reads are MCU-attached FM17550 SPI queries; Python receives `status` plus raw `data` bytes through `fm17550_read_card_return`, then higher layers map RFID identifiers through `config/officiall_filas_list.cfg`.

Unresolved compiled-module questions after this pass:

- exact branch predicates inside `cmd_EXTRUDER_LOAD` beyond the harnessed `b_endstop_state` cases
- exact branch predicates inside `cmd_EXTRUDER_UNLOAD` for retry/error handling
- exact `box_autofeed.auto_start()` MCU command payload and wrapping-detection state machine
- exact `box_rfid.read_card()` raw data bytes and material/color/vendor decoding before `officiall_filas_list.cfg` lookup
- exact `TaskQueueManager` flow IDs and state transitions in `multi_color_controller.so`

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
