# QIDI Box static disassembly notes

## Source modules

Captured compiled modules:

- `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/klipper/klippy/extras/box_stepper.so`
- `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/klipper/klippy/extras/box_extras.so`
- `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/klipper/klippy/extras/multi_color_controller.so`

Generated static artifacts:

- `tmp/qidi-box-reversing/symbol-dumps/box_stepper.objdump-symbols.txt`
- `tmp/qidi-box-reversing/disassembly/box_stepper.slot_load.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_stepper.cmd_SLOT_UNLOAD.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_stepper.cmd_EXTRUDER_LOAD.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_stepper.cmd_EXTRUDER_UNLOAD.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_stepper.slot_sync.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_stepper.init_slot_sync.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_stepper.sync_unbind_extruder.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_extras.cmd_BOX_PRINT_START.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_extras.cmd_RETRY.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_extras.cmd_TRY_RESUME_PRINT.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_extras.cmd_RESUME_PRINT_1.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_autofeed.cmd_auto_start.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_autofeed.auto_start.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_autofeed.limit_a_event.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_autofeed.wrapping_operate.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_autofeed.wrapping_detection.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_rfid.schedule_rfid_read.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_rfid.start_rfid_read.disasm.txt`
- `tmp/qidi-box-reversing/disassembly/box_rfid.stop_read.disasm.txt`
- `tmp/qidi-box-reversing/taskqueue-decide-flow.disasm.txt`

## DWARF status

`box_stepper.so` reports `with debug_info` from `file`, but `dwarfdump --debug-info` only exposes compile units for `crti.S` and `crtn.S` from the toolchain startup objects. The Cython-generated `box_stepper.c` line/variable debug info is not available through DWARF.

`strings box_stepper.so` still exposes:

- source filename `box_stepper.c`
- Cython runtime names
- local string-table names for methods, variables, G-code snippets, and error messages
- AArch64 GNU toolchain version `10.2.1 20201103`

## `box_stepper.so` disassembly coverage

| Function | Symbol map address | Size | Disassembly artifact | Line count |
|---|---:|---:|---|---:|
| `BoxExtruderStepper.slot_load` | `0x32750` | `0x2f2c` | `tmp/qidi-box-reversing/disassembly/box_stepper.slot_load.disasm.txt` | `3025` |
| `BoxExtruderStepper.cmd_SLOT_UNLOAD` | `0x35a08` | `0x27d4` | `tmp/qidi-box-reversing/disassembly/box_stepper.cmd_SLOT_UNLOAD.disasm.txt` | `2555` |
| `BoxExtruderStepper.cmd_EXTRUDER_LOAD` | `0x38568` | `0x7738` | `tmp/qidi-box-reversing/disassembly/box_stepper.cmd_EXTRUDER_LOAD.disasm.txt` | `7636` |
| `BoxExtruderStepper.cmd_EXTRUDER_UNLOAD` | `0x400d8` | `0xca90` | `tmp/qidi-box-reversing/disassembly/box_stepper.cmd_EXTRUDER_UNLOAD.disasm.txt` | `12970` |
| `BoxExtruderStepper.slot_sync` | `0x4d898` | `0x22a0` | `tmp/qidi-box-reversing/disassembly/box_stepper.slot_sync.disasm.txt` | `2222` |
| `BoxExtruderStepper.init_slot_sync` | `0x4fe5c` | `0x1118` | `tmp/qidi-box-reversing/disassembly/box_stepper.init_slot_sync.disasm.txt` | `1100` |
| `BoxExtruderStepper.sync_unbind_extruder` | `0x51298` | `0x0398` | `tmp/qidi-box-reversing/disassembly/box_stepper.sync_unbind_extruder.disasm.txt` | `236` |
| `TaskQueueManager._decide_flow_id` | `0x1ef3c` | `0xcac` | `tmp/qidi-box-reversing/taskqueue-decide-flow.disasm.txt` | generated earlier |

`cmd_EXTRUDER_UNLOAD` is the largest public motion-owner function; the static artifact now exists, but branch predicates should still be taken from harness/runtime evidence rather than raw Cython AArch64 control flow alone.

## `box_extras.so` disassembly coverage

| Function | Symbol map address | Size | Disassembly artifact | Line count |
|---|---:|---:|---|---:|
| `BoxExtras.cmd_BOX_PRINT_START` | `0x563d0` | `0x3260` | `tmp/qidi-box-reversing/disassembly/box_extras.cmd_BOX_PRINT_START.disasm.txt` | `3230` |
| `BoxExtras.cmd_RETRY` | `0x2c22c` | `0x2a94` | `tmp/qidi-box-reversing/disassembly/box_extras.cmd_RETRY.disasm.txt` | `2731` |
| `BoxExtras.cmd_TRY_RESUME_PRINT` | `0x51a84` | `0x45bc` | `tmp/qidi-box-reversing/disassembly/box_extras.cmd_TRY_RESUME_PRINT.disasm.txt` | `4469` |
| `BoxExtras.cmd_RESUME_PRINT_1` | `0x599c0` | `0x3b34` | `tmp/qidi-box-reversing/disassembly/box_extras.cmd_RESUME_PRINT_1.disasm.txt` | `3795` |

These artifacts cover the high-value orchestration/recovery functions that call into stock load/unload, retry, and resume flows. Harness output in `docs/qidi_box/qidi_box_extras_orchestration_reference.md` remains the source for readable scripts and saved-variable writes.

## `box_autofeed.so` disassembly coverage

| Function | Symbol map address | Size | Disassembly artifact | Line count |
|---|---:|---:|---|---:|
| `MCBAutoFeed.cmd_auto_start` | `0x21b6c` | `0x3afc` | `tmp/qidi-box-reversing/disassembly/box_autofeed.cmd_auto_start.disasm.txt` | `3781` |
| `MCBAutoFeed.auto_start` | `0x25b84` | `0x33d8` | `tmp/qidi-box-reversing/disassembly/box_autofeed.auto_start.disasm.txt` | `3324` |
| `MCBAutoFeed.limit_a_event` | `0x1b8f8` | `0x1e20` | `tmp/qidi-box-reversing/disassembly/box_autofeed.limit_a_event.disasm.txt` | `1934` |
| `MCBAutoFeed.wrapping_operate` | `0x2c490` | `0x1aac` | `tmp/qidi-box-reversing/disassembly/box_autofeed.wrapping_operate.disasm.txt` | `1713` |
| `MCBAutoFeed.wrapping_detection` | `0x2e764` | `0x5cc` | `tmp/qidi-box-reversing/disassembly/box_autofeed.wrapping_detection.disasm.txt` | `377` |

These artifacts cover the anti-wrap/autofeed functions whose live callback payloads remain unresolved. Harness output in `docs/qidi_box/qidi_box_autofeed_reference.md` remains the source for readable MCU command formats and converted payloads.

## `box_rfid.so` disassembly coverage

| Function | Symbol map address | Size | Disassembly artifact | Line count |
|---|---:|---:|---|---:|
| `BoxRFID._schedule_rfid_read` | `0x7e1c` | `0x2764` | `tmp/qidi-box-reversing/disassembly/box_rfid.schedule_rfid_read.disasm.txt` | `2527` |
| `BoxRFID.start_rfid_read` | `0xa90c` | `0x7bc` | `tmp/qidi-box-reversing/disassembly/box_rfid.start_rfid_read.disasm.txt` | `501` |
| `BoxRFID.stop_read` | `0xb3ec` | `0x6ec` | `tmp/qidi-box-reversing/disassembly/box_rfid.stop_read.disasm.txt` | `449` |

These artifacts cover the RFID scheduling functions. Harness output in `docs/qidi_box/qidi_box_rfid_reference.md` remains the source for readable FM17550 command formats. Valid tag payload decoding still requires runtime capture.

## Cython string table markers in `box_stepper.so`

`box_stepper.so` contains these motion/state variable names in the string table:

```text
slot_load_length_1
slot_load_length_2
slot_load_length_3
slot_load_length_4
slot_unload_length_1
extruder_load_length_1
extruder_unload_length_1
extruder_unload_length_2
slot_load_length_1_accel
slot_load_length_1_speed
slot_load_length_2_accel
slot_load_length_2_speed
slot_load_length_3_accel
slot_load_length_3_speed
slot_load_length_4_accel
slot_load_length_4_speed
slot_unload_length_1_accel
slot_unload_length_1_speed
extruder_load_length_1_accel
extruder_load_length_1_speed
multi_extruder_load_length_1
multi_extruder_load_length_2
multi_extruder_load_length_3
multi_extruder_unload_speed_1
multi_extruder_unload_speed_2
multi_extruder_unload_accel
extruder_unload_length_1_accel
extruder_unload_length_1_speed
extruder_unload_length_2_accel
extruder_unload_length_2_speed
multi_extruder_unload_length_1
multi_extruder_unload_length_2
hub_load_length
hub_load_v
hub_load_a
```

Harnessed values in `docs/qidi_box/qidi_box_stepper_branch_matrix.md` resolve the visible public-command paths. Some string-table names imply additional multi-step or internal paths that are not fully exercised by the fake harness.

## QDE error strings in `box_stepper.so`

Complete cross-module error mapping: `docs/qidi_box/qidi_box_error_code_reference.md`.

| Code | Message text |
|---|---|
| `QDE_004_001` | `Slot loading failure, please check the trigger, please reload %s.` |
| `QDE_004_002` | `Extruder has been loaded, cannot load %s.` |
| `QDE_004_003` | `Slot unloading failure, please unload %s again.` |
| `QDE_004_004` | `Please unload extruder first.` |
| `QDE_004_005` | `Please load the filament to %s first.` |
| `QDE_004_006` | `Extruder loading failure.` |
| `QDE_004_007` | `Extruder not loaded.` |
| `QDE_004_008` | `Extruder unloading failure.` |
| `QDE_004_009` | `Extruder unloading failure.` |
| `QDE_004_011` | `Detected that filament have been loaded, please unload filament first` |
| `QDE_004_016` | `The filament has been exhausted, please load the filament to %s.` |
| `QDE_004_017` | `Filament flush failed, please clean and then load the filament in %s.` |
| `QDE_004_018` | `No filament specified, %s cannot be automatically replaced.` |
| `QDE_004_019` | `Please check if your PTFE Tube is bent` |
| `QDE_004_020` | `Detected that the filament has been unloaded, please reload.` |
| `QDE_004_022` | `No replaceable slot found.` |
| `QDE_004_024` | `The filament failed to enter the extruder.` |
| `QDE_004_025` | `Extruder unloading failure.` |

Runtime capture should map these codes to live predicates.

## Static-to-runtime gap

The static disassembly confirms function boundaries and string-table vocabulary, but Cython-generated AArch64 instruction streams are not a reliable standalone source for high-level branch predicates without either:

- live runtime logs/status around real sensor/endstop states, or
- a stronger dynamic harness that executes each branch with realistic Klipper objects.

Harnessed constants and live captures are the source of behavior; disassembly is a target locator when a runtime branch remains unexplained.
