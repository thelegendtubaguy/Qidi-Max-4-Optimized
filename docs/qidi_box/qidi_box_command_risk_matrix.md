# QIDI Box command risk matrix

## Source

- `docs/qidi_box/qidi_box_gcode_command_surface.md`
- `docs/qidi_box/qidi_box_stock_call_graph.md`
- `docs/qidi_box/qidi_box_runtime_observations.md`

## Risk classes

| Class | Meaning |
|---|---|
| `Safe query` | no intended motion, no saved-variable mutation expected |
| `State mutation` | changes saved variables or internal state but should not move hardware |
| `Heater/dryer` | changes heater/fan state and may require temperature checks |
| `Toolhead motion` | moves toolhead/extruder but not QIDI Box slot steppers |
| `Box motion` | moves QIDI Box slot steppers or filament path |
| `Runtime gap` | exact behavior depends on live hardware state and remains undocumented by current captures |

## Confirmed safe query / low-risk commands

| Command | Observed behavior | Evidence |
|---|---|---|
| `QUERY_MULTI_COLOR` | accepted; logged status only | `docs/qidi_box/qidi_box_runtime_observations.md` |
| `QUERY_SAVE_VARIABLES` | accepted; logged saved variables only | `docs/qidi_box/qidi_box_runtime_observations.md` |
| `GET_MULTI_COLOR_STATUS` | accepted; returned `ok` without response payload or status mutation | `docs/qidi_box/qidi_box_runtime_observations.md` |
| `MULTI_COLOR_SYNC SLOT=slot2` | accepted; no diff when target already matched `slot_sync=slot2` | `docs/qidi_box/qidi_box_runtime_observations.md` |
| `MULTI_COLOR_CLEAR_RUNOUT` | accepted; no diff when runout counters were already clear | `docs/qidi_box/qidi_box_runtime_observations.md` |
| Moonraker object query for `multi_color_controller`, `box_extras`, `box_stepper slotN`, sensors, and heater objects | status only | `docs/qidi_box/qidi_box_runtime_observations.md` |

## RFID commands

| Command | Risk class | Observed/captured behavior | Remaining gap |
|---|---|---|---|
| `SLOT_RFID_READ SLOT=slot2` | Safe query in idle capture; runtime gap for valid tag | returned `ok`, no saved-variable diff, no raw payload | valid tag bytes/status |
| `INIT_RFID_READ` | Safe query in idle capture; runtime gap for valid tag | returned `ok`, no saved-variable diff, no raw payload | reader order and valid tag writes |
| `MULTI_COLOR_INIT_RFID` | Safe query in idle capture; runtime gap for valid tag | returned `ok`, no saved-variable diff, no raw payload | reader order and valid tag writes |
| `MULTI_COLOR_READ_RFID SLOT=slot2` | Safe query in idle capture; runtime gap for valid tag | returned `ok`, no saved-variable diff, `rfid.results={}`; polled capture saw `rfid.reading=false` | successful result schema |

## Autofeed commands

| Command | Risk class | Observed/captured behavior | Remaining gap |
|---|---|---|---|
| `MCB_CONFIG SLOT=slot2` | State mutation / low risk | returned `ok`, no saved-variable diff | exact MCU config side effects only visible in firmware |
| `MCB_QUERY` | Safe query / low risk | returned `ok`, no saved-variable diff | `MCB_STATE` callback payload not observed |
| `SET_LIMIT_A STATE=0` | State mutation / low risk | returned `ok`, no saved-variable diff | virtual limit state not published in status |
| `SET_LIMIT_A STATE=1` | State mutation / low risk | returned `ok`, no saved-variable diff; restored to `0` afterward | virtual limit state not published in status |
| `MCB_AUTO_START SLOT=slotN` | Box motion / runtime gap | not run | `MCB_STATE`, `MCB_DONE`, `MCB_ERROR`, anti-wrap behavior |
| `MCB_AUTO_ABORT` | State mutation / motion-adjacent | idle capture returned `ok`, no saved-variable diff, no published status change | abort behavior during active auto-start |

## Motion-bearing stock commands

| Command | Risk class | Vendor owner | Dispatch path |
|---|---|---|---|
| `EXTRUDER_LOAD SLOT=slotN` | Box motion | `box_stepper.so` | direct compiled command |
| `EXTRUDER_UNLOAD SLOT=slotN` | Box motion + toolhead/extruder motion | `box_stepper.so` | direct compiled command |
| `SLOT_UNLOAD SLOT=slotN` | Box motion | `box_stepper.so` | direct compiled command |
| `E_LOAD SLOT=N` | Box motion alias | `config/box.cfg` macro | calls `EXTRUDER_LOAD` |
| `E_UNLOAD SLOT=N` | Box motion alias | `config/box.cfg` macro | calls `EXTRUDER_UNLOAD` |
| `E_BOX SLOT=N` | Box motion alias | `config/box.cfg` macro | calls `SLOT_UNLOAD` / box-unload path |
| `BOX_PRINT_START EXTRUDER=N HOTENDTEMP=T` | Runtime gap; may heat and move | `box_extras.so` | calls `EXTRUDER_LOAD` / `EXTRUDER_UNLOAD` branches |
| `MULTI_COLOR_LOAD` | Box motion alias | `multi_color_controller.so` | local adapter emits `E_LOAD` |
| `MULTI_COLOR_UNLOAD` | Box motion alias | `multi_color_controller.so` | local adapter emits `E_UNLOAD` |
| `MULTI_COLOR_SWAP` | Box motion alias | `multi_color_controller.so` | local adapter emits `E_UNLOAD`, then `E_LOAD` |
| `MULTI_COLOR_BOX_UNLOAD` | Box motion alias | `multi_color_controller.so` | local adapter emits `E_BOX` |
| `MULTI_COLOR_PRINT_START` | Runtime gap; may heat and move | `multi_color_controller.so` | local adapter emits `BOX_PRINT_START` |

## Cleanup commands

| Command | Risk class | Vendor behavior |
|---|---|---|
| `CLEAR_FLUSH` | Toolhead motion | `M204 S10000`, `G1 X180 F10000`, `MOVE_TO_TRASH` |
| `CLEAR_OOZE` | Toolhead motion | X wipe sequence at `F8000`, `F5000`, `F6000` |
| `CLEAR_RUNOUT_NUM` | State mutation | writes `runout_0`..`runout_15 = 0` |
| `CUT_FILAMENT T=N` | Toolhead/extruder motion | cutter and retract path |
| `MOVE_TO_TRASH` | Toolhead motion | rear purge/wipe positioning |

## Heater/dryer commands

| Command | Risk class | Vendor owner | Notes |
|---|---|---|---|
| `ENABLE_BOX_DRY BOX=N TEMP=T END_TIME=H` | Heater/dryer | `box_extras.so` plus heater objects | starts dryer/heater behavior for a box |
| `DISABLE_BOX_DRY BOX=N` | Heater/dryer | `box_extras.so` plus heater objects | stops dryer behavior for a box |
| `DISABLE_BOX_HEATER` | Heater/dryer | `box_extras.so` | clears box heater target |
| `BOX_TEMP_SET BOX=N TARGET=T` | Heater/dryer | `box_extras.so` | sets box heater target |

## Retry/resume/recovery commands

| Command | Risk class | Evidence |
|---|---|---|
| `TRY_MOVE_AGAIN RFID=N` | Runtime gap | stock adapter emits command; exact branch unresolved |
| `TRY_RESUME_PRINT` | Runtime gap | fake harness failure emitted `M118 Printer resume failed` |
| `RESUME_PRINT_1 S=T` | Runtime gap | fake harness failure emitted `M118 Printer resume failed` |
| `AUTO_RELOAD_FILAMENT` | Runtime gap / box motion possible | fake harness incomplete |
| `RELOAD_ALL FIRST=N` | Runtime gap / box motion possible | fake harness incomplete |
| `TIGHTEN_FILAMENT T=N` | Runtime gap / box motion possible | stock adapter emits command |
