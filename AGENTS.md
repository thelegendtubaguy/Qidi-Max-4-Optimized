# AGENTS.md

## Scope

- This repository is a machine-specific QIDI Max 4 Klipper/Fluidd configuration, installer, and slicer G-code source.
- It is a reference/backup source for this printer, not a universal printer profile.
- The host UI stack is QIDI's forked Fluidd (`v1.30.5-ab46ef6`).

## Mandatory rules

1. Never modify `config/fluidd.cfg`.
   - The file is read-only on the printer.
   - If a request would normally require changing it, explain that constraint and implement the behavior elsewhere.

2. Preserve machine-specific and vendor-specific behavior unless the user explicitly asks to change it.

3. Never add, restore, or commit unredacted hardware identifiers.
   - Keep MCU serials, USB `by-id` paths, board IDs, and similar identifiers redacted.
   - Treat `config/MCU_ID.cfg` and `config/box.cfg` as especially sensitive.

4. Keep stock-mapped config files stock.
   - `config/` is the stock-mapped printer/base tree except for redactions, approved comment translation, generated state blocks, and minimal include wiring such as `[include tltg-optimized-macros/*.cfg]`.
   - Do not tune values directly in `config/printer.cfg` or stock-mapped `config/klipper-macros-qd/*.cfg`; stock-value changes belong in guarded `installer/package.yaml patches.*` entries.
   - Klipper behavior changes belong in `installer/klipper/tltg-optimized-macros/`; slicer behavior changes belong in `orcaslicer_gcode/` and `qidistudio_gcode/`; installer/runtime metadata belongs under `installer/`.
   - `installer/klipper/tltg-optimized-macros/` is the source for installer-managed runtime `config/tltg-optimized-macros/` on the printer.
   - Do not assume `/home/qidi/printer_data/config` is pure stock; first check whether it already contains `OPTIMIZED_*` or other repo-specific customizations.
   - If a stock-mapped `config/` edit is unavoidable, call it out before editing and keep the diff minimal.

5. For stock comparisons, use QIDI's stock baseline:
   - `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`
   - Treat that repo's configs, docs, tags, and release snapshots as the definition of stock unless the user says otherwise.
   - `docs/current_config_results_vs_stock_qidi_configs.md` records only differences between this repo and stock, not a changelog of local edits.

6. Keep OrcaSlicer and QIDI Studio G-code packs functionally aligned.
   - Preserve each slicer's variable syntax and placeholders.
   - When one slicer's custom G-code behavior changes, update the other slicer's equivalent file unless the user explicitly wants divergence.
   - Exception: do not add polar cooler controls to `qidistudio_gcode/` unless the user explicitly asks for that divergence to be removed.

7. Update docs under `docs/` when behavior, assumptions, integration details, config flow, slicer flow, or installer behavior changes.

8. Localization guardrail:
   - Translate comments only unless explicitly instructed otherwise.
   - Leave runtime/status/warning strings unchanged unless the user explicitly approves the affected string set.

## Required references by task

- Stock-vs-optimized behavior: `docs/current_config_results_vs_stock_qidi_configs.md`
- Start/end/filament/mesh/slicer flow:
  - `docs/gcode-paths/notes.md`
  - `docs/gcode-paths/start-print.path.json`
  - `docs/gcode-paths/generated/start-print.md`
  - `docs/optimized_slicer_start_temperature_flow.md`
- QIDI Box, multi-color, `BOX_PRINT_START`, `box_extras`, or vendor box internals: `docs/box_print_start_notes.md`
- Installer behavior, state, guarded patches, uninstall, recovery, restore helper, and auto-update:
  - `docs/installer_runtime_contract.md`
  - `docs/installer_restore_helper.md`

## Start-print path contract

- Before changing start-print behavior, read `docs/gcode-paths/notes.md`, `docs/gcode-paths/start-print.path.json`, and `docs/gcode-paths/generated/start-print.md`.
- Contracted start-path sources include `orcaslicer_gcode/start.gcode`, `qidistudio_gcode/start.gcode`, `config/box.cfg`, `config/klipper-macros-qd/*.cfg`, and `installer/klipper/tltg-optimized-macros/*.cfg`.
- `docs/gcode-paths/start-print.path.json` records branch-level invariants only; exact command sequences stay in `.gcode` and `.cfg` files.
- If a start-path change adds, removes, reorders, or changes a command that is or should be a branch-level invariant, update `docs/gcode-paths/start-print.path.json` in the same change.
- After any start-path behavior change, regenerate and check the generated path docs:

  ```bash
  python3 scripts/check_gcode_paths.py --write
  python3 scripts/check_gcode_paths.py
  ```

- Commit regenerated `docs/gcode-paths/generated/start-print.md` and `docs/gcode-paths/generated/start-print.mmd` when they change.
- If the generated views do not change after a concrete start-path command change, state why the changed command is not a branch-level invariant.

## Repository map

- Active runtime include graph is in `config/printer.cfg`:
  - `MCU_ID.cfg`
  - `timelapse.cfg`
  - `klipper-macros-qd/*.cfg`
  - `tltg-optimized-macros/*.cfg` on-printer, sourced from repo `installer/klipper/tltg-optimized-macros/*.cfg`
  - `box.cfg`
- `config/KAMP/*.cfg` exists as upstream-style macros, but this machine's active adaptive mesh flow is in `config/klipper-macros-qd/bed_mesh.cfg` plus optimized wrappers under `installer/klipper/tltg-optimized-macros/`.
- `config/box1.cfg` contains similar tool macros, but `config/box.cfg` is the actively included box file.

Common behavior paths:

- Stock print start/end phases: `config/klipper-macros-qd/start_end.cfg`
- Optimized print start/end helpers: `installer/klipper/tltg-optimized-macros/start_end.cfg`
- Homing override and homing mode/current sequencing: `config/klipper-macros-qd/kinematics.cfg` and `installer/klipper/tltg-optimized-macros/kinematics.cfg`
- Stock filament load/unload/cut flow: `config/klipper-macros-qd/filament.cfg`
- Optimized filament helpers: `installer/klipper/tltg-optimized-macros/filament.cfg`
- Adaptive mesh wrapper and `g29`: `config/klipper-macros-qd/bed_mesh.cfg`
- Optimized cooling helpers: `installer/klipper/tltg-optimized-macros/cooling.cfg`
- Pause/resume/cancel flow: `config/klipper-macros-qd/pause_resume_cancel.cfg`

## Validation rules

- If editing `installer/klipper/tltg-optimized-macros/**/*.cfg`, run:

  ```bash
  python3 scripts/format_klipper_configs.py
  ```

- If changing start-print behavior, follow the start-print path contract above.

- If changing installer behavior, run focused installer tests or the core suite:

  ```bash
  python3 scripts/run_installer_core_tests.py
  ```

## Timing and terminology rules

- `G4 P...` is fixed dead time; `M400` waits only for queued motion to finish.
- For conservative speedups, trim fixed `G4` waits before changing motion speeds/accelerations.
- Stock timing and behavior knobs remain in `config/klipper-macros-qd/globals.cfg`; optimized-only globals live in `installer/klipper/tltg-optimized-macros/globals.cfg`.
- Treat apparently unused globals in `config/klipper-macros-qd/globals.cfg` as potentially externally consumed unless proven otherwise, especially `bed_surface_max_name_length`, `bed_surfaces`, `load_length`, `load_min_temp`, `load_priming_length`, `load_priming_speed`, `menu_show_octoprint`, `menu_show_sdcard`, `menu_temperature`, and `start_end_park_y`.
- Use `purge` only for extrusion over the waste chute / wiper area at the rear of the machine.
- Use `prime line` for the front-of-bed extrusion in slicer start G-code.
