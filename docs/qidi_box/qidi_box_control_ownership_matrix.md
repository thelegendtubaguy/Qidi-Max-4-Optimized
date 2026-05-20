# QIDI Box vendor ownership matrix

## Primary motion ownership

| Command / behavior | Vendor owner | Notes |
|---|---|---|
| `EXTRUDER_LOAD SLOT=slotN` | `box_stepper.so` | Loads the selected QIDI Box slot toward the extruder path. Movement distances, speeds, acceleration, and the `0.05 s` disable dwell are hardcoded. |
| `EXTRUDER_UNLOAD SLOT=slotN` | `box_stepper.so` | Runs the unload path, including toolhead cleanup scripts and repeated recovery homing phases in the harnessed branch. |
| `SLOT_UNLOAD SLOT=slotN` | `box_stepper.so` | Ejects material from the selected slot using a `-3000` home/eject move at speed `100`, accel `50` in the harnessed branch. |
| `E_LOAD SLOT=N` | `config/box.cfg` wrapper | Resolves numeric slot input and calls `EXTRUDER_LOAD`. |
| `E_UNLOAD SLOT=N` | `config/box.cfg` wrapper | Resolves numeric slot input and calls `EXTRUDER_UNLOAD`. |
| `E_BOX SLOT=N` | `config/box.cfg` wrapper | Resolves numeric slot input and calls the slot-eject path. |
| `slot_load()` | `box_stepper.so` | Internal preload helper; harnessed loaded-state branch homes `3000` at speed `80`, then parks `-260` at speed `80`. |
| `slot_sync()` / `init_slot_sync()` | `box_stepper.so` | Maintains slot-to-extruder sync state and saved-variable side effects. |

Core movement values are summarized in `docs/qidi_box/qidi_box_speed_timing_control_matrix.md`; harnessed branch predicates are summarized in `docs/qidi_box/qidi_box_stepper_branch_matrix.md`.

## Print-start and cleanup ownership

| Command / behavior | Vendor owner | Notes |
|---|---|---|
| `BOX_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temp>` | `box_extras.so` | Resets retry/runout state, resolves tool-to-slot mapping, and calls downstream stock motion commands. |
| `CLEAR_FLUSH` | `box_extras.so` | Runs `M204 S10000`, `G1 X180 F10000`, then `MOVE_TO_TRASH`. |
| `CLEAR_OOZE` | `box_extras.so` | Runs an X-axis wipe pattern using feedrates `F8000`, `F5000`, and `F6000`. |
| `CLEAR_RUNOUT_NUM` | `box_extras.so` | Writes `runout_0 = 0` through `runout_15 = 0`. |
| `CUT_FILAMENT T=<tool>` | `box_extras.so` plus cutter macros | Performs cutter/tip handling using the active tool mapping. |
| `DISABLE_BOX_HEATER` | `box_extras.so` | Clears box heater targets. |
| `TOOL_CHANGE_START` / `TOOL_CHANGE_END` | `box_extras.so` | Handles vendor tool-change state markers. |
| `TRY_RESUME_PRINT` / `RESUME_PRINT_1` | `box_extras.so` | Handles vendor resume/recovery state. |

## Wrapper macro ownership in `box.cfg`

| Macro | Vendor path |
|---|---|
| `T0`..`T15` | Resolve `value_tN` saved variables and call the corresponding load path. |
| `UNLOAD_T0`..`UNLOAD_T15` | Resolve `value_tN` saved variables and call the corresponding unload path. |
| `UNLOAD_FILAMENT` | Uses cutter, unload, ooze cleanup, and flush cleanup helpers. |
| Material helper macros | Read/write saved variables for slot material, color, vendor, and mapping state. |

## Multi-color controller ownership

| Public command | Vendor owner | Local adapter dispatch |
|---|---|---|
| `MULTI_COLOR_LOAD SLOT=slotN` | `multi_color_controller.so` | `E_LOAD SLOT=N` |
| `MULTI_COLOR_UNLOAD SLOT=slotN` | `multi_color_controller.so` | `E_UNLOAD SLOT=N` |
| `MULTI_COLOR_SWAP` | `multi_color_controller.so` | `E_UNLOAD`, then `E_LOAD` |
| `MULTI_COLOR_BOX_UNLOAD SLOT=slotN` | `multi_color_controller.so` | `E_BOX SLOT=N` |
| `MULTI_COLOR_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temp>` | `multi_color_controller.so` | `BOX_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temp>` |
| `MULTI_COLOR_READ_RFID SLOT=slotN` | `multi_color_controller.so` | `SLOT_RFID_READ SLOT=slotN` |
| `MULTI_COLOR_INIT_RFID` | `multi_color_controller.so` | `INIT_RFID_READ` |
| `MULTI_COLOR_DRY` | `multi_color_controller.so` | `ENABLE_BOX_DRY` / `DISABLE_BOX_DRY` |
| `MULTI_COLOR_SET_TEMP` | `multi_color_controller.so` | `BOX_TEMP_SET` |
| `MULTI_COLOR_CLEAR_RUNOUT` | `multi_color_controller.so` | `CLEAR_RUNOUT_NUM` |
| `MULTI_COLOR_CLEAR_FLUSH` | `multi_color_controller.so` | `CLEAR_FLUSH` |
| `MULTI_COLOR_CLEAR_OOZE` | `multi_color_controller.so` | `CLEAR_OOZE` |
| `MULTI_COLOR_CUT_FILAMENT T=<tool>` | `multi_color_controller.so` | `CUT_FILAMENT T=<tool>` |
| `QUERY_MULTI_COLOR` | `multi_color_controller.so` | Prints controller status summary. |
| `QUERY_SAVE_VARIABLES` | `multi_color_controller.so` | Prints saved QIDI Box variables. |

The captured machine runs `multi_color_controller` in `local` mode.

## Task queue ownership

`multi_color_controller.TaskQueueManager.FLOW_MAP` uses these flow IDs:

| Flow ID | Steps |
|---:|---|
| `0` | no steps |
| `1` | `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE` |
| `2` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_LOAD`, `BOX_WIPE` |
| `3` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD` |
| `4` | `BOX_EJECT` |
| `5` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `BOX_EJECT` |
| `6` | `EXT_HEAT`, `EXT_LOAD`, `EXT_BITE`, `EXT_WIPE` |
| `7` | `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD` |
| `8` | `EXT_HEAT`, `EXT_CUT`, `EXT_UNLOAD`, `WAIT_USER`, `BOX_HEAT`, `BOX_LOAD`, `BOX_WIPE` |
| `9` | `BOX_HEAT`, `BOX_CUT`, `BOX_UNLOAD`, `WAIT_USER`, `EXT_HEAT`, `EXT_LOAD`, `EXT_BITE`, `EXT_WIPE` |

`docs/qidi_box/qidi_box_task_queue_flow_reference.md` records harnessed `_decide_flow_id()` results.

## Hardware and detection ownership

| Behavior | Vendor owner |
|---|---|
| Box MCU serial detection | `box_detect.so` |
| `box.cfg` include mutation / detection state | `box_detect.so` |
| `box_count` persistence | `box_detect.so` / `multi_color_controller.so` |
| QIDI Client box UI state | `qidiclient` consuming Moonraker objects |
| Material/color/vendor lookup | saved variables plus `config/officiall_filas_list.cfg` |
| RFID reads | `box_rfid.so` FM17550 SPI path |
| Autofeed / anti-wrap | `box_autofeed.so` `mcb_*` MCU helper |
| Dryer/heater state | `box_extras.so`, heater objects, and QIDI Client UI |
| Remote serial JSON box path | `multi_color_controller.RemoteAdapter` |
