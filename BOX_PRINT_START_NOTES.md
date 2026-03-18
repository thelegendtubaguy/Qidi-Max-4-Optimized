# BOX_PRINT_START Notes

This note captures what is currently known about `BOX_PRINT_START` on the QIDI Max 4.

## What calls it

- `_PRINT_START_BOX_PREPAR` in `config/klipper-macros-qd/start_end.cfg` calls:

  ```gcode
  BOX_PRINT_START EXTRUDER={EXTRUDER} HOTENDTEMP={HOTEND}
  ```

- That macro runs during the print start sequence, before the preheat and probing phases.

## What it is not

- `BOX_PRINT_START` is not defined as a normal `[gcode_macro ...]` in this config repo.
- It is not registered in these visible Python files:
  - `/home/qidi/klipper/klippy/extras/color_feeder.py`
  - `/home/qidi/klipper/klippy/extras/feed_slot.py`
  - `/home/qidi/klipper/klippy/extras/box_config.py`

## Implementation path

- The active Klipper process runs from:

  ```text
  /home/qidi/klippy-env/bin/python /home/qidi/klipper/klippy/klippy.py
  ```

- `config/box.cfg` defines a `[box_extras]` section, so the feature is part of QIDI's vendor box integration.
- `box_config.py` imports `box_stepper` and constructs `BoxExtruderStepper` objects.
- The box stack on the printer includes these vendor modules:

  ```text
  /home/qidi/klipper/klippy/extras/box_rfid.so
  /home/qidi/klipper/klippy/extras/feed_slot.py
  /home/qidi/klipper/klippy/extras/box_config.py
  /home/qidi/klipper/klippy/extras/box_stepper.so
  /home/qidi/klipper/klippy/extras/box_heater_fan.py
  /home/qidi/klipper/klippy/extras/box_autofeed.so
  /home/qidi/klipper/klippy/extras/box_extras.so
  /home/qidi/klipper/klippy/extras/box_detect.so
  /home/qidi/klipper/klippy/extras/color_feeder.py
  /home/qidi/klipper/klippy/extras/multi_color_controller.so
  ```

- The low-level box stepper backend exists as:

  ```text
  /home/qidi/klipper/klippy/extras/box_stepper.so
  ```

- `box_stepper.so` is an ELF shared object for `aarch64`, with debug info present and not stripped.

## What is now confirmed

- `BOX_PRINT_START` exists as a literal string in both:

  ```text
  /home/qidi/klipper/klippy/extras/box_extras.so
  /home/qidi/klipper/klippy/extras/multi_color_controller.so
  ```

- `box_extras.so` contains:
  - `cmd_BOX_PRINT_START`
  - `BoxExtras.cmd_BOX_PRINT_START`

- `multi_color_controller.so` contains:
  - `cmd_multi_color_print_start`
  - `MultiColorController.cmd_multi_color_print_start`

- This strongly indicates that `BOX_PRINT_START` is part of the high-level QIDI box and multi-color orchestration layer, not just a low-level box-stepper primitive.

- `box_extras.so` can be imported successfully with the active Klipper virtualenv:

  ```text
  /home/qidi/klippy-env/bin/python
  ```

- Importing it with the system `python3` failed because the module depends on `pyudev` at initialization time.

- The module exports these Python-visible classes:
  - `BoxButton`
  - `BoxEndstop`
  - `BoxExtras`
  - `BoxOutput`
  - `ToolChange`

- These methods are confirmed to exist on `BoxExtras`, each with the Klipper-style handler signature `(self, gcmd)`:
  - `cmd_BOX_PRINT_START`
  - `cmd_INIT_BOX_STATE`
  - `cmd_INIT_RFID_READ`
  - `cmd_CLEAR_RUNOUT_NUM`
  - `cmd_TIGHTEN_FILAMENT`

- `MultiColorController.cmd_multi_color_print_start` also exists with the same `(self, gcmd)` signature.
- Its docstring is:

  ```text
  打印开始前的材料准备
  ```

- In English, that means: `material preparation before print start`.

## Evidence from the compiled module

Running `strings` on `box_stepper.so` shows these command handlers:

- `cmd_SLOT_UNLOAD`
- `cmd_EXTRUDER_LOAD`
- `cmd_EXTRUDER_UNLOAD`
- `cmd_SLOT_PROMPT_MOVE`
- `cmd_SLOT_RFID_READ`
- `cmd_DIS_STEP`

It also shows the related `BoxExtruderStepper` method names.

Running `strings` on `box_extras.so` shows these directly relevant handlers and related commands:

- `cmd_BOX_PRINT_START`
- `cmd_RELOAD_ALL`
- `cmd_CLEAR_FLUSH`
- `cmd_CLEAR_OOZE`
- `cmd_CUT_FILAMENT`
- `cmd_AUTO_RELOAD_FILAMENT`
- `cmd_RETRY`
- `cmd_INIT_RFID_READ`
- `cmd_INIT_BOX_STATE`
- `cmd_RUN_STEPPER`
- `cmd_ENABLE_BOX_DRY`
- `cmd_DISABLE_BOX_DRY`
- `cmd_CLEAR_RUNOUT_NUM`
- `cmd_TIGHTEN_FILAMENT`
- `cmd_TRY_RESUME_PRINT`
- `cmd_RESUME_PRINT_1`
- `cmd_disable_box_heater`
- `cmd_TOOL_CHANGE_START`
- `cmd_TOOL_CHANGE_END`
- `cmd_CLEAR_TOOLCHANGE_STATE`
- lower-level names such as `cmd_SLOT_UNLOAD`, `cmd_EXTRUDER_LOAD`, `cmd_EXTRUDER_UNLOAD`, and `cmd_SLOT_RFID_READ`

Running `strings` on `multi_color_controller.so` shows a parallel high-level interface with:

- `cmd_multi_color_print_start`
- `cmd_multi_color_load`
- `cmd_multi_color_unload`
- `cmd_multi_color_swap`
- `cmd_multi_color_retry`
- `cmd_multi_color_tighten`
- `cmd_multi_color_clear_flush`
- `cmd_multi_color_clear_ooze`
- `cmd_multi_color_cut_filament`
- `cmd_multi_color_init_rfid`
- `cmd_multi_color_read_rfid`
- `cmd_multi_color_box_unload`
- `cmd_multi_color_auto_reload`
- `cmd_multi_color_try_resume`
- `cmd_multi_color_resume_print`
- `cmd_multi_color_disable_heater`

It also exposes operation names that look like internal phases or action labels:

- `BOX_LOAD`
- `BOX_UNLOAD`
- `BOX_CUT`
- `BOX_WIPE`
- `BOX_EJECT`
- `BOX_HEAT`
- `BOX_TEMP_SET`

## Best current conclusion

`BOX_PRINT_START` is almost certainly a high-level vendor command that prepares the box filament path for printing. Based on the command names exposed by `box_stepper.so`, it likely orchestrates some combination of:

- selecting the requested slot/tool
- reading slot RFID
- unloading the current filament or path if needed
- moving the slot feeder into place
- loading filament into the extruder path
- disabling box stepper drive when complete

Based on the additional evidence from `box_extras.so` and `multi_color_controller.so`, it likely also coordinates some combination of:

- initializing box state and RFID handling
- clearing prior runout, ooze, flush, and toolchange state
- cutting filament when needed
- tightening filament after loading
- retry and resume logic
- heater or dry-box control when relevant

The most likely call chain is:

- print-start macro in `config/klipper-macros-qd/start_end.cfg`
- `BOX_PRINT_START EXTRUDER=... HOTENDTEMP=...`
- `box_extras.BoxExtras.cmd_BOX_PRINT_START`
- delegation into `multi_color_controller` and lower-level box modules such as `box_stepper`

The docstring on `MultiColorController.cmd_multi_color_print_start` aligns with that conclusion: this path is specifically for material preparation before printing starts.

## What remains unknown

- The exact implementation of `BOX_PRINT_START`
- The exact order of the internal steps
- The conditions for when it unloads, loads, or skips actions
- Whether `box_extras.so` directly owns the full sequence or delegates most of it to `multi_color_controller.so`

## Most likely next steps on the printer

- Use a disassembler such as `objdump` or `gdb` to inspect how `cmd_BOX_PRINT_START` and `cmd_multi_color_print_start` are wired together
- If safe on the printer, inspect Python-visible metadata such as method docs or importable symbol names from `box_extras.so`

## Files involved so far

- `config/klipper-macros-qd/start_end.cfg`
- `config/box.cfg`
- `/home/qidi/klipper/klippy/extras/box_config.py`
- `/home/qidi/klipper/klippy/extras/box_extras.so`
- `/home/qidi/klipper/klippy/extras/multi_color_controller.so`
- `/home/qidi/klipper/klippy/extras/color_feeder.py`
- `/home/qidi/klipper/klippy/extras/feed_slot.py`
- `/home/qidi/klipper/klippy/extras/box_stepper.so`
