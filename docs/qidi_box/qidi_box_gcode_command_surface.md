# QIDI Box G-code command surface

## Source

Moonraker command help capture:

- `tmp/qidi-box-reversing/runtime-20260507-145404-gcode-help/gcode-help.json`
- `tmp/qidi-box-reversing/runtime-20260507-145404-gcode-help/box-gcode-help.txt`

Capture result:

```text
commands=343 matched=59
```

## Vendor box/autofeed commands visible through Moonraker help

| Command | Description from help |
|---|---|
| `MCB_AUTO_ABORT` | `中止自动进料` |
| `MCB_AUTO_START` | `启动自动进料，支持 SLOT=slotN 动态切换` |
| `MCB_CONFIG` | `配置 mcb autofeed 模块 (动态切换 SLOT -> stepper_mcu)` |
| `MCB_QUERY` | `开始限位轮询（发到当前 stepper_mcu）` |
| `SET_LIMIT_A` | `设置虚拟限位状态，并同步到当前 stepper_mcu` |

These commands are registered by `box_autofeed.so` and match the MCU command formats in `docs/qidi_box/qidi_box_compiled_module_reference.md`.

## Multi-color controller commands visible through Moonraker help

| Command | Description from help |
|---|---|
| `QUERY_MULTI_COLOR` | `查询多色盒子状态` |
| `MULTI_COLOR_LOAD` | `加载材料到挤出机` |
| `MULTI_COLOR_UNLOAD` | `卸载材料` |
| `MULTI_COLOR_SWAP` | `切换材料` |
| `MULTI_COLOR_DRY` | `控制材料烘干` |
| `MULTI_COLOR_READ_RFID` | `读取RFID标签` |
| `MULTI_COLOR_SYNC` | `控制材料同步` |
| `MULTI_COLOR_CONFIG` | `配置多色控制器` |
| `MULTI_COLOR_BOX_UNLOAD` | `从盒子卸载材料` |
| `MULTI_COLOR_INIT_RFID` | `初始化RFID读取` |
| `MULTI_COLOR_RELOAD_ALL` | `重新加载所有槽位` |
| `MULTI_COLOR_AUTO_RELOAD` | `断料自动重载` |
| `MULTI_COLOR_RETRY` | `重试上一步操作` |
| `MULTI_COLOR_TIGHTEN` | `收紧材料` |
| `MULTI_COLOR_PRINT_START` | `打印开始前的材料准备` |
| `MULTI_COLOR_TRY_RESUME` | `尝试恢复打印` |
| `MULTI_COLOR_RESUME_PRINT` | `恢复打印（断电恢复）` |
| `MULTI_COLOR_INIT_MAPPING` | `初始化工具映射` |
| `MULTI_COLOR_DISABLE_HEATER` | `禁用盒子加热器` |
| `MULTI_COLOR_SET_TEMP` | `设置盒子温度` |
| `MULTI_COLOR_CLEAR_RUNOUT` | `清除断料计数` |
| `MULTI_COLOR_CLEAR_FLUSH` | `清理挤出机` |
| `MULTI_COLOR_CLEAR_OOZE` | `清理喷嘴垂涎` |
| `MULTI_COLOR_CUT_FILAMENT` | `剪断材料` |
| `QUERY_SAVE_VARIABLES` | `查询SaveVariables中的变量` |
| `SET_SAVE_VARIABLE` | `设置SaveVariables中的变量` |
| `RESET_MULTI_COLOR_VARS` | `重置多色相关的SaveVariables` |

These commands are registered by `multi_color_controller.so`. On this machine `multi_color_controller.LocalAdapter` maps them back to local vendor commands such as `BOX_PRINT_START`, `E_LOAD`, `E_UNLOAD`, `SLOT_RFID_READ`, `CLEAR_FLUSH`, and `CUT_FILAMENT`.

## Repo optimized box-related commands visible through Moonraker help

| Command | Description from help |
|---|---|
| `OPTIMIZED_CUT_FILAMENT` | `Faster cutter macro without the stock exit dwell.` |
| `OPTIMIZED_DISABLE_BOX_HEATER` | `Disables the QIDI Box heater when the box stack is available.` |
| `OPTIMIZED_END_PRINT_FILAMENT_PREP` | `Optionally keeps the current box filament loaded between prints.` |
| `OPTIMIZED_SELECT_INITIAL_TOOL` | `Selects the initial box tool when the QIDI Box stack is enabled.` |
| `OPTIMIZED_UNLOAD_FILAMENT` | `Box unload wrapper that also clears retained-tool state.` |
| `TLTG_SET_BOX_TEMP` | `Sets a QIDI Box heater target by box number.` |
| `_PRINT_START_BOX_PREPAR` | `Preparation of box filament` |

## Other relevant command help entries

| Command | Description from help |
|---|---|
| `CUT_FILAMENT_1` | `G-Code macro` |
| `CLEAR_NOZZLE` | `G-Code macro` |
| `CLEAR_NOZZLE_PLR` | `G-Code macro` |
| `PRINT_START` | `Usage: PRINT_START BED=<temp> HOTEND=<temp> [CHAMBER=<temp>] EXTRUDER = <num> [MESH_MIN=<x,y>] [MESH_MAX=<x,y>] [LAYERS=<num>] [NOZZLE_SIZE=<mm>]` |
| `SAVE_VARIABLE` | `Save arbitrary variables to disk` |
| `SYNC_EXTRUDER_MOTION` | `Set extruder stepper motion queue` |

`BOX_PRINT_START`, `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, `SLOT_UNLOAD`, `SLOT_RFID_READ`, `CLEAR_FLUSH`, and `CLEAR_OOZE` are callable vendor commands recovered from compiled modules, but they did not appear in the filtered Moonraker help output. Treat Moonraker help as a registered public command surface, not as a complete list of vendor callable commands.

## Runtime query observations

`docs/qidi_box/qidi_box_runtime_observations.md` records a non-motion capture of:

```gcode
QUERY_MULTI_COLOR
QUERY_SAVE_VARIABLES
```

`QUERY_MULTI_COLOR` logged local mode, one connected box, `slot2: IN_EXTRUDER`, loaded extruder state, and material/color metadata. `QUERY_SAVE_VARIABLES` logged persisted box variables including `extrude_state = 2`, `last_load_slot = slot2`, `slot_sync = slot2`, and `slot2 = 2`.
