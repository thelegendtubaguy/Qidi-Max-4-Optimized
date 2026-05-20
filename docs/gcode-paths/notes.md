# G-code path notes

Generated path maps live under `docs/gcode-paths/generated/` and are produced from `docs/gcode-paths/*.path.json` plus parsed `.gcode` / `.cfg` files with:

```bash
python3 scripts/check_gcode_paths.py --write
```

Path contract checks run with:

```bash
python3 scripts/check_gcode_paths.py
```

`enable_box` is read from `printer.save_variables.variables.enable_box`; it is not the same signal as `printer["box_extras"] is defined`.

`BOX_PRINT_START`, `CLEAR_OOZE`, `CLEAR_FLUSH`, and `EXTRUDER_LOAD` are QIDI/vendor commands outside the visible optimized macro tree.

`OPTIMIZED_PRINT_START_HOME` cancels `_optimized_end_fan_cooldown_off` before homing so a previous print's delayed `P3` fan shutdown cannot fire during the next optimized start path.

`OPTIMIZED_START_PRINT_FILAMENT_PREP` owns the branch split between retained-filament reuse, QIDI Box fresh-load, and no-box external-spool startup.

Slicer start G-code passes `FIRSTLAYERTEMP=[nozzle_temperature_initial_layer]` and `PURGETEMP={nozzle_temperature_range_high[initial_tool]}` to `OPTIMIZED_START_PRINT_FILAMENT_PREP`; `T[initial_tool]` runs before the front prime line so startup extrusion is attributed to the selected initial object filament; the front prime line waits with `M109 S[nozzle_temperature_initial_layer]` after rear purge, Z tilt, and bed mesh, then runs the centered fat purge sequence `G1 E6 F300`, `G1 X178 E20 F1200`, and `G1 X173 E0.8` to consume heat-up ooze.

`docs/gcode-paths/start-print.path.json` records branch-level invariants only; exact command order comes from `orcaslicer_gcode/start.gcode`, `qidistudio_gcode/start.gcode`, and `installer/klipper/tltg-optimized-macros/*.cfg`.
