# AGENTS.md

## What this repo is

- This repository is a machine-specific dump of QIDI Max 4 Klipper/Fluidd configuration and macros.
- It is a reference/backup source for this printer, not a universal profile for other printers.
- The host UI stack is QIDI's forked Fluidd (`v1.30.5-ab46ef6`).

## Rules for agents working in this repo

1. Never modify `config/fluidd.cfg`.
   - That file is read-only on the printer.
   - Any requested behavior changes must be implemented in other config/macro files.

2. If a request would normally change `config/fluidd.cfg`, do this instead:
   - Explain that `config/fluidd.cfg` is immutable on-device.
   - Implement the change in another appropriate file under `config/`.

3. Preserve machine-specific and vendor-specific behavior unless the user explicitly asks to change it.

4. Keep redacted hardware identifiers redacted.

5. When a user asks you to find, verify, or compare behavior against what QIDI shipped, use the stock-configs repo as the baseline.
   - Stock QIDI-shipped configs and firmware-version snapshots for this machine live at `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`.
   - Treat that repo's configs, docs, tags, and release snapshots as the definition of "stock" unless the user says otherwise.
   - `docs/current_config_results_vs_stock_qidi_configs.md` is not a changelog of local edits. It should only record behavior/config differences between this repo and stock.
   - Before updating `docs/current_config_results_vs_stock_qidi_configs.md`, check the stock baseline in `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`.

6. If you edit Klipper config files under `installer/klipper/tltg-optimized-macros/`, run `python3 scripts/format_klipper_configs.py` before finishing.
   - The formatter is intentionally limited to `installer/klipper/tltg-optimized-macros/**/*.cfg` and must not rewrite stock-mapped config files.
   - Do not use it as a broad formatter for `config/`; stock-mapped files should stay one-for-one with the printer except for intentional edits such as `printer.cfg` include wiring and approved comment translation.

7. Never add, restore, or commit unredacted hardware identifiers.
   - This includes MCU serials, USB `by-id` paths, board IDs, and any other machine-unique hardware identifier.
   - If a file in this repo needs an identifier for reference, keep the existing `REDACTED` form or redact the value before saving.
   - Treat `config/MCU_ID.cfg` and `config/box.cfg` as especially sensitive: do not ever store the real IDs in those files in this repo.

8. When you change Klipper configs or slicer G-code, update repo documentation where needed.
   - This applies to edits under `config/`, `installer/klipper/`, `orcaslicer_gcode/`, and `qidistudio_gcode/`.
   - Update existing notes in `docs/` or add new ones when the change alters behavior, assumptions, or integration details that future agents or operators would need.

9. Keep the OrcaSlicer and QIDI Studio G-code packs in sync functionally.
   - This applies to matching files under `orcaslicer_gcode/` and `qidistudio_gcode/`.
   - Preserve the slicer-specific variable syntax and placeholders each slicer requires.
   - When one slicer's custom G-code behavior changes, update the other slicer's equivalent file so the two flows still behave the same unless the user explicitly wants them to diverge.
   - Exception: do not add polar cooler controls to `qidistudio_gcode/` unless the user explicitly asks for that divergence to be removed.

10. Keep stock-named macros aligned with the printer's current runtime config, and keep repo custom behavior in installer-managed optimized paths.
   - `config/` is the printer-derived runtime/base tree.
   - `installer/klipper/tltg-optimized-macros/` is the repo source for installer-managed runtime `config/tltg-optimized-macros/` on the printer.
   - Do not assume `/home/qidi/printer_data/config` is pure stock. First check whether it already contains `OPTIMIZED_*` or other repo-specific customizations.
   - Treat the printer config as the source of truth for what is currently running, but use the stock-configs repo as the baseline when the task is specifically about QIDI-shipped behavior.
   - Prefer implementing custom behavior in `OPTIMIZED_*` macros, slicer G-code, or clearly custom helper macros instead of changing stock-named macros.
   - If a requested change truly requires editing a stock-named macro, call that out explicitly and keep the diff as small as possible.

## Fast repo orientation

- Active runtime include graph is in `config/printer.cfg`:
  - `MCU_ID.cfg`
  - `timelapse.cfg`
  - `klipper-macros-qd/*.cfg`
  - `tltg-optimized-macros/*.cfg` on-printer, sourced from repo `installer/klipper/tltg-optimized-macros/*.cfg`
  - `box.cfg`
- `config/KAMP/*.cfg` exists as upstream-style macros, but this machine's active adaptive mesh flow is in `config/klipper-macros-qd/bed_mesh.cfg`.
- `config/box1.cfg` contains similar tool macros, but `config/box.cfg` is the actively included box file.

## Where common behavior lives

- Stock print start/end phases: `config/klipper-macros-qd/start_end.cfg`
- Optimized print start/end helpers: `installer/klipper/tltg-optimized-macros/start_end.cfg`
- Homing override and homing mode/current sequencing: `config/klipper-macros-qd/kinematics.cfg`
- Stock filament load/unload/cut flow: `config/klipper-macros-qd/filament.cfg`
- Optimized filament helpers: `installer/klipper/tltg-optimized-macros/filament.cfg`
- Adaptive mesh wrapper and `g29`: `config/klipper-macros-qd/bed_mesh.cfg`
- Optimized cooling helpers: `installer/klipper/tltg-optimized-macros/cooling.cfg`
- Pause/resume/cancel flow: `config/klipper-macros-qd/pause_resume_cancel.cfg`

## Vendor reverse-engineering notes

- `docs/box_print_start_notes.md` is a repo-local technical note about QIDI's vendor-implemented `BOX_PRINT_START` command.
- It documents the current evidence trail across macros, visible Python modules, compiled Klipper extras on the printer, and inferred call paths.
- Read it when working on box or multi-color startup behavior, tracing `BOX_PRINT_START`, `box_extras`, `multi_color_controller`, or other vendor box internals.
- Read it before claiming how box print-start material prep works; the implementation is partly in compiled vendor modules and is not obvious from the config files alone.

## Timing and tuning notes

- `G4 P...` is fixed dead time; `M400` waits only for queued motion to finish.
- For conservative speedups, trim fixed `G4` waits before changing motion speeds/accelerations.
- Stock timing and behavior knobs remain in `config/klipper-macros-qd/globals.cfg`; optimized-only globals live in `installer/klipper/tltg-optimized-macros/globals.cfg`.
- Treat apparently unused globals in `config/klipper-macros-qd/globals.cfg` as potentially externally consumed unless proven otherwise. In particular, be cautious about removing or renaming `bed_surface_max_name_length`, `bed_surfaces`, `load_length`, `load_min_temp`, `load_priming_length`, `load_priming_speed`, `menu_show_octoprint`, `menu_show_sdcard`, `menu_temperature`, and `start_end_park_y`.

## Start-sequence terminology

- Use `purge` only for extrusion over the waste chute / wiper area at the rear of the machine.
- Use `prime line` for the front-of-bed extrusion in slicer start gcode.
- Keep that distinction explicit when describing, tracing, or editing print-start behavior.

## Localization guardrail

- If asked to translate Chinese text, only translate comments unless explicitly instructed otherwise.
- Leave runtime/status/warning strings unchanged by default to avoid breaking UI integrations or expected messages.
- Do not translate runtime/status/warning strings in this repo unless the user explicitly approves each affected string set after review.
