# QIDI Box vendor behavior index

## Overview

- [`qidi_box_current_conclusions.md`](qidi_box/qidi_box_current_conclusions.md): active stock stack, module ownership, captured runtime state, RFID/autofeed findings, status schema summary, and unresolved vendor-behavior gaps.
- [`box_print_start_notes.md`](qidi_box/box_print_start_notes.md): `BOX_PRINT_START` call path, state reads, branch families, cleanup commands, RFID/material mapping, saved-variable model, sync semantics, and compiled-module findings.
- [`qidi_box_stock_call_graph.md`](qidi_box/qidi_box_stock_call_graph.md): public command paths through `box.cfg`, `box_extras.so`, `box_stepper.so`, `box_autofeed.so`, `box_rfid.so`, and `multi_color_controller.so`.
- [`qidi_box_control_ownership_matrix.md`](qidi_box/qidi_box_control_ownership_matrix.md): vendor ownership table for motion, print-start, cleanup, wrapper macros, multi-color commands, task queue flows, hardware detection, RFID, autofeed, dryer, and remote serial behavior.

## Config and generated objects

- [`qidi_box_active_include_wiring.md`](qidi_box/qidi_box_active_include_wiring.md): active `[include box.cfg]` and `[multi_color_controller]` graph, objects created by those sections, include-order effects, and stock object names.
- [`qidi_box_stock_config_surface.md`](qidi_box/qidi_box_stock_config_surface.md): stock `box.cfg` sections, pin mapping, heater/fan/RFID config, `box_extras`, `box_autofeed`, MCU declaration, and tool wrapper macros.
- [`qidi_box_generated_config_reference.md`](qidi_box/qidi_box_generated_config_reference.md): `box_config.py` generated object graph for slots, heaters, temperature sensors, fans, RFID readers, and multi-box naming.
- [`qidi_box_material_metadata_reference.md`](qidi_box/qidi_box_material_metadata_reference.md): `officiall_filas_list.cfg` filament, color, vendor, drying, and saved-variable metadata mappings.

## Commands, status, and runtime observations

- [`qidi_box_gcode_command_surface.md`](qidi_box/qidi_box_gcode_command_surface.md): Moonraker-visible vendor/autofeed/multi-color commands and runtime query observations.
- [`qidi_box_command_risk_matrix.md`](qidi_box/qidi_box_command_risk_matrix.md): command risk classes, observed safe queries, RFID commands, autofeed commands, motion commands, cleanup commands, heater/dryer commands, and retry/resume commands.
- [`qidi_box_status_schema_reference.md`](qidi_box/qidi_box_status_schema_reference.md): captured Moonraker object names and field schemas for `box_extras`, `box_stepper slotN`, `multi_color_controller`, `save_variables`, heaters, temperature sensors, and `mcu mcu_box1`.
- [`qidi_box_runtime_observations.md`](qidi_box/qidi_box_runtime_observations.md): non-motion runtime captures, saved variables, object status, query command captures, RFID idle captures, and autofeed idle captures.
- [`qidi_box_qidiclient_findings.md`](qidi_box/qidi_box_qidiclient_findings.md): QIDI Client strings, Moonraker subscriptions, embedded box config template, client-side G-code templates, UI/state strings, and material database references.

## Module references

- [`qidi_box_compiled_module_reference.md`](qidi_box/qidi_box_compiled_module_reference.md): module formats, class/method inventories, constants, hardcoded motion fragments, MCU command formats, task queue maps, detection paths, and control conclusions.
- [`qidi_box_compiled_symbol_map.md`](qidi_box/qidi_box_compiled_symbol_map.md): symbol-priority tables for `box_stepper.so`, `box_extras.so`, `box_autofeed.so`, `box_rfid.so`, `multi_color_controller.so`, and `box_detect.so`.
- [`qidi_box_static_disassembly_notes.md`](qidi_box/qidi_box_static_disassembly_notes.md): disassembly coverage, DWARF status, targeted function artifacts, Cython string markers, and `QDE_004_*` strings.
- [`qidi_box_error_code_reference.md`](qidi_box/qidi_box_error_code_reference.md): `QDE_004_*` owner/message map and behavior grouping.

## Subsystems

- [`qidi_box_stepper_branch_matrix.md`](qidi_box/qidi_box_stepper_branch_matrix.md): harnessed `box_stepper.so` branch predicates and movement calls for `slot_load`, `SLOT_UNLOAD`, `EXTRUDER_LOAD`, and `EXTRUDER_UNLOAD`.
- [`qidi_box_stepper_state_methods_reference.md`](qidi_box/qidi_box_stepper_state_methods_reference.md): `slot_sync`, `init_slot_sync`, `sync_unbind_extruder`, `SLOT_PROMPT_MOVE`, `SLOT_RFID_READ`, `flush_all_filament`, and `switch_next_slot` behavior.
- [`qidi_box_extras_orchestration_reference.md`](qidi_box/qidi_box_extras_orchestration_reference.md): `CLEAR_FLUSH`, `CLEAR_OOZE`, `CLEAR_RUNOUT_NUM`, `BOX_PRINT_START` setup writes, harnessed start branches, and other `box_extras.so` command notes.
- [`qidi_box_task_queue_flow_reference.md`](qidi_box/qidi_box_task_queue_flow_reference.md): `BoxState` enum, `TaskQueueManager.FLOW_MAP`, `_decide_flow_id()` harness results, state transitions, and harness caveats.
- [`qidi_box_autofeed_reference.md`](qidi_box/qidi_box_autofeed_reference.md): `box_autofeed.so` config keys, defaults, runtime fields, MCU config/query formats, payload conversion, and idle command captures.
- [`qidi_box_rfid_reference.md`](qidi_box/qidi_box_rfid_reference.md): `box_rfid.so` class/methods, runtime fields, FM17550 MCU commands, reader topology, retry timing, metadata path, and idle command captures.
- [`qidi_box_detect_reference.md`](qidi_box/qidi_box_detect_reference.md): `box_detect.so` serial detection, config mutation paths, detection strings, symbol priorities, and firmware update strings.
- [`qidi_box_remote_adapter_reference.md`](qidi_box/qidi_box_remote_adapter_reference.md): `multi_color_controller.RemoteAdapter` JSON envelope, captured command map, slot normalization, and local-vs-remote adapter differences.

## Consolidated values

- [`qidi_box_recovered_constants.md`](qidi_box/qidi_box_recovered_constants.md): module constants, slot stepper hardware values, movement defaults, `BOX_PRINT_START` setup writes, runtime states, metadata IDs, heater/dryer values, RFID constants, autofeed constants, and cleanup G-code constants.
- [`qidi_box_speed_timing_control_matrix.md`](qidi_box/qidi_box_speed_timing_control_matrix.md): recovered speed, distance, acceleration, timing, script, autofeed, and RFID values with source categories.
