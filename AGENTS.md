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

5. When a user asks you to find, verify, or compare behavior against what QIDI shipped, check the `main` branch.
   - In this repo, `main` is the stock QIDI-shipped branch for this machine.
   - Treat configs and macros from `main` as the baseline definition of "stock" unless the user says otherwise.

6. If you edit Klipper config files while on the `optimized` branch, run `python3 scripts/format_klipper_configs.py` before finishing.
   - This applies to editable `.cfg` files under `config/`.
   - Do not run it against `config/fluidd.cfg` or `config/saved_variables.cfg`; the script already skips them.

7. On the `optimized` branch, never add, restore, or commit unredacted hardware identifiers.
   - This includes MCU serials, USB `by-id` paths, board IDs, and any other machine-unique hardware identifier.
   - If a file on `optimized` needs an identifier for reference, keep the existing `REDACTED` form or redact the value before saving.
   - Treat `config/MCU_ID.cfg` and `config/box.cfg` as especially sensitive: do not ever store the real IDs in those files on `optimized`.

## Fast repo orientation

- Active runtime include graph is in `config/printer.cfg`:
  - `MCU_ID.cfg`
  - `timelapse.cfg`
  - `klipper-macros-qd/*.cfg`
  - `box.cfg`
- `config/KAMP/*.cfg` exists as upstream-style macros, but this machine's active adaptive mesh flow is in `config/klipper-macros-qd/bed_mesh.cfg`.
- `config/box1.cfg` contains similar tool macros, but `config/box.cfg` is the actively included box file.

## Where common behavior lives

- Print start/end phases: `config/klipper-macros-qd/start_end.cfg`
- Homing override and homing mode/current sequencing: `config/klipper-macros-qd/kinematics.cfg`
- Filament load/unload/cut flow: `config/klipper-macros-qd/filament.cfg`
- Adaptive mesh wrapper and `g29`: `config/klipper-macros-qd/bed_mesh.cfg`
- Pause/resume/cancel flow: `config/klipper-macros-qd/pause_resume_cancel.cfg`

## Timing and tuning notes

- `G4 P...` is fixed dead time; `M400` waits only for queued motion to finish.
- For conservative speedups, trim fixed `G4` waits before changing motion speeds/accelerations.
- Common timing knobs are exposed in `config/klipper-macros-qd/globals.cfg` (`*_settle*`, `start_bed_heat_delay`, etc.).

## Localization guardrail

- If asked to translate Chinese text, only translate comments unless explicitly instructed otherwise.
- Leave runtime/status/warning strings unchanged by default to avoid breaking UI integrations or expected messages.
- Do not translate runtime/status/warning strings in this repo unless the user explicitly approves each affected string set after review.
