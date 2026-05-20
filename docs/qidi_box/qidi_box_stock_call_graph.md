# QIDI Box stock call graph

## Scope

This call graph maps public stock commands, QIDI Client commands, slicer tool commands, and generated config objects to the compiled-module owner that performs the behavior.

Sources:

- `docs/qidi_box/qidi_box_compiled_module_reference.md`
- `docs/qidi_box/qidi_box_control_ownership_matrix.md`
- `docs/qidi_box/qidi_box_extras_orchestration_reference.md`
- `docs/qidi_box/qidi_box_gcode_command_surface.md`
- `docs/qidi_box/qidi_box_generated_config_reference.md`
- `docs/qidi_box/qidi_box_stock_config_surface.md`
- `tmp/qidi-box-reversing/multi_color_adapter_probe.json`
- `tmp/qidi-box-reversing/box_extras_methods_probe.json`
- `tmp/qidi-box-reversing/box_stepper_probe_output.json`

## Generated object root

```text
[include box.cfg]
  [box_config box0]
    box_config.py
      box_stepper slot0 -> box_stepper.so BoxExtruderStepper(slot_num=0)
      box_stepper slot1 -> box_stepper.so BoxExtruderStepper(slot_num=1)
      box_stepper slot2 -> box_stepper.so BoxExtruderStepper(slot_num=2)
      box_stepper slot3 -> box_stepper.so BoxExtruderStepper(slot_num=3)
      heater_generic heater_box1
      temperature_sensor heater_temp_a_box1
      temperature_sensor heater_temp_b_box1
      box_heater_fan heater_fan_a_box1
      box_heater_fan heater_fan_b_box1
      controller_fan board_fan_box1
      box_rfid card_reader_1 -> box_rfid.so BoxRFID(cs_pin_box_rfid_0)
      box_rfid card_reader_2 -> box_rfid.so BoxRFID(cs_pin_box_rfid_1)
  [box_extras]
    box_extras.so BoxExtras
  [box_autofeed]
    box_autofeed.so MCBAutoFeed
  [multi_color_controller]
    multi_color_controller.so MultiColorController
```

## Slicer tool command path

```text
T0..T15
  stock macro in box.cfg
    slot = save_variables.value_tN default slotN
    if enable_box == 1:
      EXTRUDER_LOAD SLOT=<slot>
        box_stepper.so BoxExtruderStepper.cmd_EXTRUDER_LOAD()
          slot/load branch predicates
          do_home(..., 3000, 85, 50, False)
          dwell(0.05)
          sync_print_time()
```

```text
UNLOAD_T0..UNLOAD_T15
  stock macro in box.cfg
    slot = save_variables.value_tN default slotN
    if enable_box == 1:
      EXTRUDER_UNLOAD SLOT=<slot>
        box_stepper.so BoxExtruderStepper.cmd_EXTRUDER_UNLOAD()
          pre-cleanup scripts
          do_home_double_steps(..., -350, -1150, 65, 85, 100, True)
          do_home(..., -1500, 65, 50, True)
          do_home(..., -1500, 65, 50, True)
```

## Start-print command path

```text
BOX_PRINT_START EXTRUDER=<tool> HOTENDTEMP=<temp>
  box_extras.so BoxExtras.cmd_BOX_PRINT_START()
    CLEAR_TOOLCHANGE_STATE
    SAVE_VARIABLE load_retry_num=0
    SAVE_VARIABLE retry_step=None
    SAVE_VARIABLE runout_0..runout_15=0
    SAVE_VARIABLE extrude_state=-1
    target_slot = save_variables.value_t<tool>
    MOVE_TO_TRASH
    M109 S<temp>
    branch:
      EXTRUDER_LOAD SLOT=<target_slot>
        box_stepper.so cmd_EXTRUDER_LOAD()
      or EXTRUDER_UNLOAD SLOT=<loaded_slot>
        box_stepper.so cmd_EXTRUDER_UNLOAD()
      or cut/unload/load branch, exact live predicate unresolved
```

`BOX_PRINT_START` is orchestration only; core load/unload speed, distance, acceleration, and dwell values are downstream in `box_stepper.so`.

## Multi-color local adapter path

`multi_color_controller.so` in `local` mode dispatches to stock G-code:

| Public command / adapter method | Local script | Motion owner |
|---|---|---|
| `MULTI_COLOR_LOAD SLOT=slotN` / `load_filament(slotN)` | `E_LOAD SLOT=N` | stock alias to `EXTRUDER_LOAD`, then `box_stepper.so` |
| `MULTI_COLOR_UNLOAD SLOT=slotN` / `unload_filament(slotN)` | `E_UNLOAD SLOT=N` | stock alias to `EXTRUDER_UNLOAD`, then `box_stepper.so` |
| `MULTI_COLOR_SWAP FROM_SLOT=slotA TO_SLOT=slotB` / `swap_filament(slotA, slotB)` | `E_UNLOAD SLOT=A`, `E_LOAD SLOT=B` | `box_stepper.so` |
| `MULTI_COLOR_BOX_UNLOAD SLOT=slotN` / `box_unload(slotN)` | `E_BOX SLOT=N` | stock alias to `SLOT_UNLOAD`, then `box_stepper.so` |
| `MULTI_COLOR_PRINT_START EXTRUDER=N HOTENDTEMP=T` / `print_start(N,T)` | `BOX_PRINT_START EXTRUDER=N HOTENDTEMP=T` | `box_extras.so`, then `box_stepper.so` |
| `MULTI_COLOR_READ_RFID SLOT=slotN` / `read_rfid(slotN)` | `SLOT_RFID_READ SLOT=slotN` | `box_stepper.so` + `box_rfid.so` path |
| `MULTI_COLOR_INIT_RFID` / `init_rfid()` | `INIT_RFID_READ` | `box_extras.so` + `box_rfid.so` path |
| `MULTI_COLOR_CLEAR_FLUSH` / `clear_flush()` | `CLEAR_FLUSH` | `box_extras.so`, macro-equivalent |
| `MULTI_COLOR_CLEAR_OOZE` / `clear_ooze()` | `CLEAR_OOZE` | `box_extras.so`, macro-equivalent |
| `MULTI_COLOR_CLEAR_RUNOUT` / `clear_runout()` | `CLEAR_RUNOUT_NUM` | `box_extras.so`, saved-variable helper |
| `MULTI_COLOR_CUT_FILAMENT T=N` / `cut_filament(N)` | `CUT_FILAMENT T=N` | `box_extras.so` + cutter macros |
| `MULTI_COLOR_DRY` / `start_drying()` | `ENABLE_BOX_DRY BOX=<n> TEMP=<c> END_TIME=<h>` | `box_extras.so` + heater objects |
| stop drying | `DISABLE_BOX_DRY BOX=<n>` | `box_extras.so` + heater objects |

## Remote adapter path

`multi_color_controller.RemoteAdapter` sends JSON dictionaries over serial instead of local G-code:

```text
load_filament(slot0)
  {"cmd":"load_filament","slot":0,"options":{},"timestamp":...,"id":"cmd_..."}

unload_filament(slot0)
  {"cmd":"unload_filament","slot":0,"options":{},"timestamp":...,"id":"cmd_..."}

swap_filament(slot0, slot1)
  {"cmd":"swap_filament","from_slot":0,"to_slot":1,"options":{},"timestamp":...,"id":"cmd_..."}

print_start(3, 240)
  {"cmd":"print_start","extruder":3,"hotendtemp":240,"timestamp":...,"id":"cmd_..."}
```

Runtime status in `docs/qidi_box/qidi_box_runtime_observations.md` showed `multi_color_controller.system.mode = local`; the remote path is not active on this machine.

## Direct stock motion commands

```text
EXTRUDER_LOAD SLOT=slotN
  box_stepper.so cmd_EXTRUDER_LOAD()
    gate/pre-gate branch predicate from fake harness
    do_home(..., 3000, 85, 50, False)
    disable_stepper()
    dwell(0.05)
    sync_print_time()
```

```text
EXTRUDER_UNLOAD SLOT=slotN
  box_stepper.so cmd_EXTRUDER_UNLOAD()
    pre-cleanup G-code scripts
    unload shake scripts
    do_home_double_steps(..., -350, -1150, 65, 85, 100, True)
    do_home(..., -1500, 65, 50, True)
    do_home(..., -1500, 65, 50, True)
    disable_stepper()
```

```text
SLOT_UNLOAD SLOT=slotN
  box_stepper.so cmd_SLOT_UNLOAD()
    do_home(..., -3000, 100, 50, True)
    disable_stepper()
```

```text
SLOT_RFID_READ SLOT=slotN
  box_stepper.so cmd_SLOT_RFID_READ()
    reader/stepper selection path
    box_rfid.so BoxRFID.start_rfid_read(stepper)
      fm17550_read_card_cb oid=%c
      fm17550_read_card_return oid=%c status=%c data=%*s
```

The fake `cmd_SLOT_RFID_READ` harness and live idle RFID captures disagree on the loaded-filament guard. Use live evidence for this branch.

## Macro-equivalent stock helpers

```text
CLEAR_FLUSH
  box_extras.so cmd_CLEAR_FLUSH()
    M204 S10000
    G1 X180 F10000
    MOVE_TO_TRASH
```

```text
CLEAR_OOZE
  box_extras.so cmd_CLEAR_OOZE()
    M204 S10000
    G1 X163 F8000
    G1 X145 F5000
    G1 X163 F8000
    G1 X145 F5000
    G1 X175 F6000
    G1 X163 / X175 repeated
```

```text
CLEAR_RUNOUT_NUM
  box_extras.so cmd_CLEAR_RUNOUT_NUM()
    SAVE_VARIABLE runout_0=0
    ...
    SAVE_VARIABLE runout_15=0
```

```text
flush_all_filament()
  box_stepper.so helper
    G1 E25 F300
    disable_stepper()
```

These helpers are visible G-code/state helper behaviors.

## Autofeed command path

```text
MCB_CONFIG SLOT=slotN
  box_autofeed.so cmd_config()
    select slot stepper MCU
    mcb_config_stepper oid=%c stepper_oid=%c
```

```text
MCB_QUERY
  box_autofeed.so cmd_query()
    mcb_query oid=%c clock=%u rest_ticks=%u retransmit_count=%c invert=%c
```

```text
SET_LIMIT_A STATE=0|1
  box_autofeed.so cmd_SET_LIMIT_A()
    set_limit_a oid=%c state=%c
```

```text
MCB_AUTO_START SLOT=slotN
  box_autofeed.so cmd_auto_start()
    auto_start(v_mm_s, a_mm_s2, lmax_mm, dir, sync_stepper)
      mcb_auto_start oid=%c v=%u a=%u lmax=%u dir=%i enable=%i invert=%i
```

Runtime idle captures accepted `MCB_CONFIG`, `MCB_QUERY`, and `SET_LIMIT_A` without status or saved-variable changes. `MCB_AUTO_START` remains motion-risking and untested.

## Retry/resume/recovery path

```text
TRY_MOVE_AGAIN RFID=<n>
  multi_color_controller LocalAdapter.retry()
    TRY_MOVE_AGAIN RFID=<n>
      box_extras.so cmd_RETRY()
```

```text
TRY_RESUME_PRINT
  box_extras.so cmd_TRY_RESUME_PRINT()
    checks extrude_state
    fake harness failure path emitted M118 Printer resume failed
```

```text
RESUME_PRINT_1 S=<temp>
  box_extras.so cmd_RESUME_PRINT_1()
    checks extrude_state
    fake harness failure path emitted M118 Printer resume failed
```

Retry/resume exact live behavior remains a runtime gap.
