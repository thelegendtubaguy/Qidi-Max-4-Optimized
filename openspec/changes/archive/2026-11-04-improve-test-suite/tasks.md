# Tasks

## 1. Reduce lifecycle runs

- [x] 1.1 Run the historical update and uninstall scenario from the oldest version only.
- [x] 1.2 Limit restore-path source matrices to one standard and one sync-reset case, and run migration and auto-update installation once.
- [x] 1.3 Remove the drift-helper and mocked invalid-uninstall-plan tests that end-to-end tests already cover.
- [x] 1.4 Copy only the version-bump script's inputs, and drop an unused fixture setup.

## 2. Validation

- [x] 2.1 Run `python3 scripts/run_installer_core_tests.py` five times on the same host, before and after, and report the times.
- [x] 2.2 Run `openspec validate --all --strict`.
