# AGENTS.md

## Mandatory rules

1. Never modify `config/fluidd.cfg`; it is read-only on the printer. Implement related behavior elsewhere.
2. Preserve machine/vendor behavior unless explicitly asked to change it.
3. Never add, restore, or commit unredacted hardware identifiers. Treat `config/MCU_ID.cfg` and `config/box.cfg` as sensitive.
4. Keep stock-mapped config files stock:
   - `config/` is stock-mapped except redactions, approved comment translation, generated state blocks, and minimal include wiring.
   - Do not tune values directly in `config/printer.cfg` or stock-mapped `config/klipper-macros-qd/*.cfg`.
   - Stock-value changes belong in guarded `installer/package.yaml patches.*` entries.
   - Klipper behavior changes belong in `installer/klipper/tltg-optimized-macros/`.
   - Slicer behavior changes belong in `orcaslicer_gcode/` and `qidistudio_gcode/`.
   - Installer/runtime metadata belongs under `installer/`.
   - If a stock-mapped `config/` edit is unavoidable, call it out before editing and keep the diff minimal.
5. Use QIDI stock baseline for comparisons: `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`.
6. Do not update slicer G-code in `orcaslicer_gcode/` or `qidistudio_gcode/` when the behavior can reasonably be implemented printer-side through Klipper config, optimized macros, or installer patches.
7. Keep OrcaSlicer and QIDI Studio G-code packs functionally aligned while preserving each slicer's syntax/placeholders. Exception: do not add polar cooler controls to `qidistudio_gcode/` unless explicitly asked.
8. Update docs under `docs/` when behavior, assumptions, config flow, slicer flow, installer behavior, or integration details change.
9. Translate comments only unless explicitly told otherwise. Leave runtime/status/warning strings unchanged unless the affected string set is approved.

## Git workflow

- Create feature, bugfix, and general work branches from the latest `origin/dev` unless explicitly told otherwise.
- Open PRs against `dev` unless the PR is a release merge.

## QIDI Studio slicer G-code constraints

- QIDI Studio is not OrcaSlicer with identical placeholder parsing; keep `qidistudio_gcode/` syntax separately tested instead of copying Orca expressions verbatim.
- Do not use `activate_air_filtration_on_completion[...]` or `complete_print_exhaust_fan_speed[...]` in `qidistudio_gcode/`; QIDI Studio 2.6 reports `Not a variable name` for indexed completion-air-filtration placeholders in end G-code. Use a constant `EXHAUST_SPEED=0` unless a QIDI Studio-tested replacement exists.
- Keep QIDI Studio `{if}`, `{else}`, and `{endif}` blocks on separate lines when editing conditionals; this is the tested style used by `qidistudio_gcode/*.gcode`.
- Do not add direct polar cooler controls such as `M106 P4 ...` to `qidistudio_gcode/` unless explicitly requested and validated in QIDI Studio.

## Required references

- Stock-vs-optimized behavior: `docs/optimized_vs_stock.md`
- Start/end/filament/mesh/slicer flow:
  - `docs/gcode-paths/notes.md`
  - `docs/gcode-paths/start-print.path.json`
  - `docs/gcode-paths/generated/start-print.md`
- QIDI Box, multi-color, `BOX_PRINT_START`, `box_extras`, or vendor box internals: `docs/qidi_box/box_print_start_notes.md`
- Installer state, guarded patches, uninstall, recovery, restore helper, and auto-update:
  - `docs/installer_runtime_contract.md`
  - `docs/installer_restore_helper.md`

## Stock-vs-optimized prose

When editing `docs/optimized_vs_stock.md`:

- Write functional behavior summaries, not raw config diffs. Prefer `Faster X/Y homing with reduced retractions` over listing each `[stepper_*] homing_*` value.
- Group related settings by observed printer behavior: homing, Z tilt, bed mesh, filament cut, purge/prime, wipe/scrape, cancel, fan cooldown, QIDI Box handling, and slicer entrypoints.
- Include source paths for traceability, but do not turn the doc into a manifest dump of options, hashes, or line-by-line macro deltas unless the exact value is the behavior.
- Describe what changes for the operator or print sequence: skipped redundant homing, randomized Z probing point, reduced fixed waits, faster measurement travel, retained filament reuse, no-box scrape without purge, or safer cancel without movement.
- Keep stock value details in `installer/package.yaml`, tests, or targeted implementation notes; use the stock-vs-optimized doc for behavior-level comparisons.

## Start-print path contract

Before changing start-print behavior:

1. Read `docs/gcode-paths/notes.md`, `docs/gcode-paths/start-print.path.json`, and `docs/gcode-paths/generated/start-print.md`.
2. Update `docs/gcode-paths/start-print.path.json` when a branch-level invariant changes.
3. Regenerate and check generated docs:

   ```bash
   python3 scripts/check_gcode_paths.py --write
   python3 scripts/check_gcode_paths.py
   ```

4. Include regenerated `docs/gcode-paths/generated/start-print.md` and `docs/gcode-paths/generated/start-print.mmd` when they change.
5. If generated views do not change after a concrete start-path command change, state why the command is not a branch-level invariant.

Contracted start-path sources include `orcaslicer_gcode/start.gcode`, `qidistudio_gcode/start.gcode`, `config/box.cfg`, `config/klipper-macros-qd/*.cfg`, and `installer/klipper/tltg-optimized-macros/*.cfg`.

## Common paths

- Active runtime include graph: `config/printer.cfg`
  - `MCU_ID.cfg`, `timelapse.cfg`, `klipper-macros-qd/*.cfg`, `tltg-optimized-macros/*.cfg`, `box.cfg`
- Runtime optimized macro source: `installer/klipper/tltg-optimized-macros/`
- Start/end: `config/klipper-macros-qd/start_end.cfg`, `installer/klipper/tltg-optimized-macros/start_end.cfg`
- Homing: `config/klipper-macros-qd/kinematics.cfg`, `installer/klipper/tltg-optimized-macros/kinematics.cfg`
- Filament: `config/klipper-macros-qd/filament.cfg`, `installer/klipper/tltg-optimized-macros/filament.cfg`
- Adaptive mesh: `config/klipper-macros-qd/bed_mesh.cfg`, optimized wrappers under `installer/klipper/tltg-optimized-macros/`
- Cooling: `installer/klipper/tltg-optimized-macros/cooling.cfg`
- Pause/resume/cancel: `config/klipper-macros-qd/pause_resume_cancel.cfg`
- `config/KAMP/*.cfg` exists but is not this machine's active adaptive mesh path.
- `config/box.cfg` is actively included.

## Validation

- If editing `installer/klipper/tltg-optimized-macros/**/*.cfg`, run:

  ```bash
  python3 scripts/format_klipper_configs.py
  ```

- If editing `installer/package.yaml` or `installer/supported_upgrade_sources.yaml`, run:

  ```bash
  python3 scripts/check_installer_known_versions.py
  ```

- If editing slicer G-code, run:

  ```bash
  python3 scripts/check_optimized_slicer_macros.py
  ```

- If changing installer behavior, run:

  ```bash
  python3 scripts/run_installer_core_tests.py
  ```

- If editing launcher, bundle, or release plumbing, run:

  ```bash
  python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id local --smoke-test
  ```

- If changing start-print behavior, follow the start-print path contract above.

## Timing and terminology

- `G4 P...` is fixed dead time; `M400` waits only for queued motion to finish.
- For conservative speedups, trim fixed `G4` waits before changing motion speeds/accelerations.
- Stock timing/behavior knobs remain in `config/klipper-macros-qd/globals.cfg`; optimized-only globals live in `installer/klipper/tltg-optimized-macros/globals.cfg`.
- Treat apparently unused stock globals as externally consumed unless proven otherwise.
- Use `purge` only for extrusion over the rear waste chute / wiper area.
- Use `prime line` for the front-of-bed extrusion in slicer start G-code.
