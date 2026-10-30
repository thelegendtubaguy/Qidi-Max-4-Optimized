# AGENTS.md

## Safety and ownership

- Never modify `config/fluidd.cfg` (read-only on the printer); implement related behavior elsewhere.
- Preserve machine/vendor behavior unless explicitly asked; compare against `https://github.com/thelegendtubaguy/Qidi-Max4-Defaults`.
- Never add, restore, or commit unredacted hardware identifiers. Treat `config/MCU_ID.cfg` and `config/box.cfg` as sensitive.
- `kevin@koconnor.net` is permitted only in upstream Klipper GPL copyright headers.
- Translate comments only unless told otherwise. Leave runtime/status/warning strings unchanged unless the affected string set is approved.
- Keep `config/` stock-mapped except redactions, approved comment translation, generated state blocks, and minimal include wiring. Never tune `config/printer.cfg` or `config/klipper-macros-qd/*.cfg`. Put changes where they belong:
  - stock values: guarded `installer/package.yaml patches.*`, or a guarded host-file patch under `installer/runtime/` when the file is QIDI-generated with varying sections (e.g. `config/box.cfg`);
  - Klipper behavior: `installer/klipper/tltg-optimized-macros/`;
  - slicer behavior: `orcaslicer_gcode/` and `qidistudio_gcode/`;
  - installer/runtime metadata: `installer/`.

  Call out unavoidable stock-mapped edits first and keep them minimal.

## Fluidd

This project owns Fluidd. Make changes in the fork of upstream `fluidd-core/fluidd` (`https://github.com/thelegendtubaguy/fluidd`, branch `qidi`), rebased onto upstream releases. Installer releases pin a fork release in `installer/package.yaml` (`system_optimizations.fluidd_build`), installed alongside QIDI's Fluidd so QIDI's copy stays the rollback. The guarded patches of QIDI's bundle in `installer/runtime/fluidd_box_filaments.py` apply only when that build can't be served and take fixes only. Document Fluidd's UI in the fork, not here.

## Docs

- `README.md` is a short landing page: install, then one-line feature summaries linking to `docs/`. Keep it operator-focused and don't link `openspec/` unless asked.
- Put operator detail in the matching `docs/<topic>.md` (index: `docs/README.md`), new settings and commands in `docs/settings.md`, and new files or services the installer touches in `docs/under-the-hood.md`.

## Git

Branch from latest `origin/dev` unless told otherwise. Target PRs to `dev` except release merges.

## Slicers

- Keep OrcaSlicer and QIDI Studio packs functionally aligned, each in its own syntax and placeholders.
- QIDI Studio syntax is tested separately: don't copy Orca expressions verbatim; keep `{if}`, `{else}`, and `{endif}` on separate lines.
- In `qidistudio_gcode/`, don't use `activate_air_filtration_on_completion[...]` or `complete_print_exhaust_fan_speed[...]` (QIDI Studio 2.6: `Not a variable name`); use `EXHAUST_SPEED=0` unless a QIDI Studio-tested replacement exists. Don't add direct polar-cooler controls such as `M106 P4 ...` unless requested and validated in QIDI Studio.

## OpenSpec

Read as applicable: `openspec/specs/{installer-lifecycle,optimized-printer-behavior,firmware-artifacts,thr-firmware-transfer}/spec.md`, `openspec/contracts/gcode-paths/start-print.path.json` with its `generated/start-print.md`, `openspec/observations/qidi-platform.md`, and `openspec/observations/qidi-box/*.md`.

- `specs/` hold desired repository behavior: behavioral requirements, testable scenarios. Manifests, tests, and code own exhaustive non-operator-visible data.
- `contracts/` hold machine-checked invariants; generated views are outputs, not authority.
- `observations/` describe external/vendor behavior with the qualifiers from `openspec/observations/README.md`; don't promote harness/static inference to requirements or confirmed vendor behavior.
- Keep all three current, not append-only, without duplicate rules. Describe behavior, not diffs; include paths only when they help traceability.

## Start-print changes

Read the printer spec, contract, and generated view first. Update `start-print.path.json` for branch-level invariants, run `python3 scripts/check_gcode_paths.py --write` then `python3 scripts/check_gcode_paths.py`, and include changed generated `.md`/`.mmd` files. If a command change leaves generated views unchanged, say why it isn't a branch-level invariant. Contracted sources: both slicers' `start.gcode`, `config/box.cfg`, `config/klipper-macros-qd/*.cfg`, `installer/klipper/tltg-optimized-macros/*.cfg`.

## Runtime paths

- Include graph: `config/printer.cfg` → `MCU_ID.cfg`, `timelapse.cfg`, `klipper-macros-qd/*.cfg`, `tltg-optimized-macros/*.cfg`, `box.cfg` (active).
- Stock/optimized pairs: `start_end.cfg`, `kinematics.cfg` (homing), `filament.cfg`, `bed_mesh.cfg` plus optimized wrappers (adaptive mesh). `config/KAMP/*.cfg` is not the active mesh path.
- Cooling: `installer/klipper/tltg-optimized-macros/cooling.cfg`; pause/resume/cancel: `config/klipper-macros-qd/pause_resume_cancel.cfg`.

## Versions and changelog

- Changes to installed macros, installer behavior, or release-bundle contents must advance the package version with `python3 scripts/bump_installer_version.py <version>`, which keeps `installer/package.yaml` and `tltg-optimized-macros/globals.cfg` aligned. The installer admits state from any version of this package, so renumbering or folding an unreleased version needs no compatibility bookkeeping.
- Update `installer/supported_upgrade_sources.yaml` by hand only when adding a guarded patch target or source-patch provenance; its cumulative envelope must cover the current manifest.
- Every version needs a matching `CHANGELOG.md` section in the same change, covering every operator-visible change shipped under it. Before finishing, check the headings against `installer/package.yaml` and run `python3 scripts/check_installer_known_versions.py`.

## Validation

- Optimized macro `.cfg`: `python3 scripts/format_klipper_configs.py`
- `installer/package.yaml` or `supported_upgrade_sources.yaml`: `python3 scripts/check_installer_known_versions.py`
- Slicer G-code: `python3 scripts/check_optimized_slicer_macros.py`
- Installer behavior: `python3 scripts/run_installer_core_tests.py`
- THR firmware generator or patch manifest: `scripts/check_thr_firmware.py` against a fresh `scripts/build_thr_firmware.py` build (setup in `firmware/README.md`)
- THR flashing tool or protocol: `scripts/check_thr_flashing.py` (with `--bootloader-backup` when available) and `scripts/check_thr_recovery.py` with a recoverable build's `--bootloader-backup` (see `firmware/FLASHING.md`)
- Launcher, bundle, or release plumbing: `python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id local --smoke-test`
- OpenSpec: `openspec validate --all --strict`
- Start-print behavior or contract paths: see **Start-print changes**.

## Tests

- Test durable behavior, safety boundaries, and release contracts, not implementation detail. Don't test private helpers, call order, constants, exact status wording, standard-library behavior, or synthetic examples unless enforcing a security boundary.
- Extend existing lifecycle, contract, matrix, or smoke coverage first; prefer end-to-end scenarios and parameterized firmware/source matrices. Run checkers directly; don't wrap them. Put static invariants in contracts or standalone checkers.
- Add a test module only for a distinct boundary; net growth needs an unrepresented operator-visible behavior or safety invariant. Remove or merge superseded and overlapping tests with behavior changes.
- Keep `python3 scripts/run_installer_core_tests.py` under six seconds on a typical machine (bundle smoke excluded).

## Timing and terminology

- `G4 P...` is fixed dead time; `M400` waits only for queued motion. For conservative speedups, trim `G4` before changing speeds or acceleration.
- Stock timing/behavior globals stay in `config/klipper-macros-qd/globals.cfg`; optimized-only globals go in `installer/klipper/tltg-optimized-macros/globals.cfg`. Treat seemingly unused stock globals as externally consumed unless proven otherwise.
- "Purge" means rear waste-chute/wiper extrusion only; "prime line" means front-of-bed slicer-start extrusion.
