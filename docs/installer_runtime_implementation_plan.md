# Installer_Runtime_Implementation_Plan

## Scope

- Runtime target: `/home/qidi/printer_data/config`.
- Behavioral requirements live in `docs/installer_runtime_contract.md`.
- Manifest inputs live in `installer/package.yaml` and `installer/supported_upgrade_sources.yaml`.
- Installed-state ledger path is `config/tltg_optimized_state.yaml`.
- Installed-state ledger format is `schema_version: 1`.
- `config/fluidd.cfg` remains untouched.

## Current Baseline

- `installer/runtime/` provides install, uninstall, dry-run, recovery-sentinel-clear, debug, backup-retention, rollback-diagnostics, and restore-helper flows.
- `installer/release/install.sh` launches `python3 -I -S installer/runtime/bootstrap.py <mode>` from the extracted bundle root and supports `--plain`, `--debug`, `--dry-run`, `--demo-tui`, `--uninstall`, and `--clear-recovery-sentinel`.
- `installer/release/restore.sh` launches `python3 -I -S installer/runtime/bootstrap.py restore-backup` from the extracted bundle root and supports interactive backup selection plus `--backup <path>`.
- `installer/runtime/reporter.py` provides the Rich terminal UI path for install, uninstall, dry-run, clear-recovery-sentinel, and restore-helper flows plus plain fallback; the Rich path renders live status panels, preflight counters, operation counters, confirmation prompts, detail groups, backup tables, and success/error panels.
- `installer/runtime/demo.py` provides the no-op TUI preview path for install and uninstall; the per-screen delay defaults to `5` seconds and `TLTG_OPTIMIZED_DEMO_TUI_DELAY_SECONDS` shortens it for smoke tests.
- `installer/runtime/vendor/` vendors the required pure-Python runtime dependencies.
- `scripts/build_installer_bundle.py` builds the self-contained release bundle and includes `restore.sh`.
- `scripts/check_installer_known_versions.py` validates `installer/package.yaml` against `installer/supported_upgrade_sources.yaml`.
- `scripts/smoke_test_installer_bundle.py` smoke-tests archive extraction, launcher execution, rich/plain launcher behavior, and restore-helper behavior against fixture runtime trees.
- `scripts/run_installer_core_tests.py` runs the focused always-on suite for install, uninstall, dry-run immutability, fail-closed install and uninstall checks, restore-helper snapshot restore, recovery-sentinel clearing, and rollback sentinel creation.
- `.github/workflows/check-installer-bundle.yml` runs the focused core suite, validates compatibility metadata, and smoke-tests the release bundle in pull requests.
- `.github/workflows/publish-dev-installer.yml` runs the focused core suite, validates compatibility metadata, and publishes dev prerelease assets from `dev`.
- `.github/workflows/publish-release-installer.yml` runs the focused core suite, validates compatibility metadata, smoke-tests the release bundle, and publishes release assets from `main`.
- On-device printer validation remains manual and is not enforced by repository automation.

## Remaining Work

- None.

## Validation Commands

```bash
python3 scripts/run_installer_core_tests.py
python3 scripts/build_installer_bundle.py --output-dir dist --channel release --smoke-test
python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id local
```
