## 1. Baseline Inputs

- [x] 1.1 Confirm `../Qidi-Max4-Defaults` is at commit `5da5767379ac22fc4fbe1606ec7093ce056229ae` or tag `qidi-max4-firmware-01.01.06.04`.
- [x] 1.2 Capture `.03` and `.04` stock deltas for `config/printer.cfg`, `config/klipper-macros-qd/idle.cfg`, `config/klipper-macros-qd/pause_resume_cancel.cfg`, and `config/officiall_filas_list.cfg`.
- [x] 1.3 Keep existing optimized X/Y homing desired values for `.04`; validate on hardware after implementation.
- [x] 1.4 Adopt `.04` base-last cleanup ordering in `OPTIMIZED_CANCEL_PRINT_ON_ERROR` while preserving no-park/no-toolhead-move behavior.

## 2. Installer Manifest

- [x] 2.1 Add `01.01.06.04` to `installer/package.yaml firmware.supported`.
- [x] 2.2 Add `.04` variants to every existing `patches.set_options[]` target.
- [x] 2.3 Add `.04` variants to every existing `patches.delete_sections[]` target.
- [x] 2.4 Add guarded manifest coverage for `.04` stock options required by the firmware baseline, including X/Y closed-loop `query_cycle`, `trigger_current`, `trigger_time`, `trigger_speed`, chamber thermal protection max temp, idle pause target, and official filament rename where represented as installer patches.
- [x] 2.5 Ensure `.03` variants do not require `.04`-only `trigger_*` options.

## 3. Firmware-Specific Stock Snapshots

- [x] 3.1 Add a stock snapshot layout that can store separate `01.01.06.03` and `01.01.06.04` config trees under `installer/stock/`.
- [x] 3.2 Preserve the `.03` stock snapshot for `.03` legacy reset.
- [x] 3.3 Add the `.04` stock snapshot from `../Qidi-Max4-Defaults/config/`.
- [x] 3.4 Update `installer/runtime/legacy_manual_install.py` to select the stock snapshot by detected firmware.
- [x] 3.5 Add tests for legacy reset selecting `.03`, selecting `.04`, and failing before overwrite when a supported firmware snapshot is missing.

## 4. Stock-Mapped Runtime Files

- [x] 4.1 Update local stock-mapped baseline files only where required for `.04` support and call out any direct `config/` edits.
- [x] 4.2 Preserve `config/fluidd.cfg`, `config/MCU_ID.cfg`, and `config/box.cfg` sensitivity rules.
- [x] 4.3 Keep QIDI Studio and OrcaSlicer G-code packs unchanged unless a slicer-flow impact is found.

## 5. Documentation

- [x] 5.1 Update `docs/installer_runtime_contract.md` with `.03`/`.04` firmware support and firmware-specific stock snapshot selection.
- [x] 5.2 Update `docs/installer_restore_helper.md` if restore or recovery wording changes due to snapshot layout.
- [x] 5.3 Update `docs/optimized_vs_stock.md` with behavior-level notes for relevant `.04` baseline differences.
- [x] 5.4 Update local docs/tests that assert official `[fila25]` names to use `PA6-CF`, while leaving `drying.conf` references unchanged unless QIDI changes them upstream.

## 6. Validation

- [x] 6.1 Run `python3 scripts/check_installer_known_versions.py`.
- [x] 6.2 Run `python3 scripts/run_installer_core_tests.py`.
- [x] 6.3 Run `python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id local --smoke-test` if bundle or stock snapshot packaging changes.
- [x] 6.4 Run `openspec validate support-qidi-firmware-01-01-06-04`.
- [x] 6.5 Review final diff for unredacted hardware identifiers and unintended stock-mapped edits.
