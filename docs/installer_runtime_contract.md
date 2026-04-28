# Installer_Runtime_Contract

Installer metadata used by the runtime:
- `installer/package.yaml package.version` is the bundle package version.
- `installer/package.yaml package.known_versions` contains the installed package versions accepted from `config/tltg_optimized_state.yaml` during install and must exactly match the supported prior-version keys in `installer/supported_upgrade_sources.yaml`.
- `installer/package.yaml firmware.supported` contains the install-supported firmware versions.
- `installer/package.yaml backup.source_directory` is `config`.
- `installer/package.yaml backup.label_prefix` is the install backup label prefix.
- `installer/package.yaml state.record_file` is `config/tltg_optimized_state.yaml`.
- `installer/package.yaml preflight.required_files`, `preflight.required_sections`, and `preflight.required_lines` define aggregated install preflight targets.
- `config/box.cfg` and `[box_extras]` are not install preflight targets; `OPTIMIZED_START_PRINT_FILAMENT_PREP` branches around the QIDI Box stack when `printer["box_extras"]` is not defined or `enable_box != 1`.
- During interactive install, when `config/box.cfg` contains `[box_extras]`, `config/saved_variables.cfg [Variables] box_count` is greater than `0`, and `[Variables] enable_box` is `0`, the runtime prompts to set `enable_box = 1`; this saved-variable edit is not recorded in `config/tltg_optimized_state.yaml` and uninstall does not revert it.
- During interactive install, when existing `config/saved_variables.cfg [Variables] value_tN` entries do not equal `'slotN'`, the runtime prompts to rewrite each mismatched existing `value_tN` to `'slotN'`; this saved-variable edit is not recorded in `config/tltg_optimized_state.yaml` and uninstall does not revert it.
- `installer/package.yaml install.ensure_directories`, `install.managed_tree`, and `install.ensure_lines` define the installer-managed runtime changes under `config/`.
- `installer/package.yaml patches.set_options[]` defines guarded `file + section + option` runtime value patches.
- `installer/package.yaml patches.delete_sections[]` defines guarded `file + section` runtime section deletion patches; each variant stores `expected_normalized_sha256` for the normalized section text that must be present before deletion.
- `installer/package.yaml install.managed_tree` defines the managed-tree file set validated during install postflight.
- `installer/package.yaml postflight.verify_lines` defines additional final install line-verification targets.
- `installer/supported_upgrade_sources.yaml` defines the supported prior installed package versions and the exact uninstall-allowed guarded patch target tuples (`file + section + option`) for each version.

State-file contract:
- Public installer bundles write `config/tltg_optimized_state.yaml schema_version: 1`.
- `config/tltg_optimized_state.yaml` stores package identity, install timestamp, detected install firmware, backup label, managed-tree file hashes, and the guarded patch ledger used for uninstall.
- Public installer bundles accept only schema-valid installed-state ledgers compatible with `schema_version: 1`.
- Pre-ledger dev installs that do not provide the managed-tree file hashes and guarded patch ledger are unsupported inputs for public uninstall bundles.
- External tamper detection is not yet implemented, so uninstall trusts a schema-valid local installed-state ledger subject to tuple allowlists and live-value checks.
- Uninstall validates that every ledger patch target matches an explicit uninstall-allowed `file + section + option` tuple for the stored installed package version from `installer/supported_upgrade_sources.yaml`.
- Newer public bundles may uninstall older supported installs only when that stored installed package version and its allowed tuple set are present in `installer/supported_upgrade_sources.yaml`.

Managed-tree drift semantics:
- Install/reinstall compares current `config/tltg-optimized-macros/` file hashes against the existing `config/tltg_optimized_state.yaml managed_tree.files[]` hashes to detect local drift.
- Install/reinstall compares the same existing `managed_tree.files[]` hashes against the new bundle contents to detect expected bundle-version changes.
- Differences between the prior installed-state ledger and the new bundle contents are expected bundle changes by themselves and are not reported as local managed-tree drift.

Patch manifest semantics:
- Manifest validation rejects any `installer/package.yaml patches.set_options[]` or `patches.delete_sections[]` block unless it provides exactly one matching `variants[]` entry for every `installer/package.yaml firmware.supported[]` value.
- A supported firmware with zero matching `variants[]` entries or multiple matching `variants[]` entries is a manifest validation failure.
- Because of that manifest constraint, install preflight validates every unique patch target from `patches.set_options[]` and `patches.delete_sections[]` regardless of detected firmware; variant selection changes `expected`/`desired` values for option patches and `expected_normalized_sha256` for section deletion patches.

Install statuses and terminal messages:
- Status `checking firmware version` covers reading `/home/qidi/update/firmware_manifest.json`, parsing `SOC.version`, and comparing it against `installer/package.yaml firmware.supported`.
- Failure during install `checking firmware version` returns `Could not detect firmware version.` when `/home/qidi/update/firmware_manifest.json` is missing, corrupt, or does not contain a valid `SOC.version`, and stops before `config/tltg_optimized_state.yaml`, backup creation, or any write under `config/`.
- Failure during install `checking firmware version` returns `Your firmware version is not supported.` when the detected firmware is not present in `installer/package.yaml firmware.supported`, and stops before `config/tltg_optimized_state.yaml`, backup creation, or any write under `config/`.
- Status `checking package version` covers reading and validating `config/tltg_optimized_state.yaml` when that file already exists.
- Missing `config/tltg_optimized_state.yaml` is a fresh-install path and does not block the run.
- Failure during `checking package version` returns `Could not validate previous package version.` when `config/tltg_optimized_state.yaml` is unreadable, malformed, schema-incompatible, missing required install-state fields, or stores a package version not present in `installer/package.yaml package.known_versions`.
- Status `performing preflight checks` covers `installer/package.yaml preflight.required_files`, `preflight.required_sections`, `preflight.required_lines`, every unique patch target from `patches.set_options[]` and `patches.delete_sections[]`, the local Moonraker printer-state query, and free-space checks.
- Failure during `performing preflight checks` returns `Cannot continue because you're missing these things.` and prints the full target report grouped by files, sections, lines, and patch targets; patch-target entries may be missing or ambiguous.
- Failure during `performing preflight checks` returns `Could not determine printer state.` when local Moonraker `print_stats.state` data is unavailable, malformed, or inconsistent.
- Failure during `performing preflight checks` returns `Cannot continue while a print is active or paused.` when local Moonraker `print_stats.state` is `printing` or `paused`.
- Failure during `performing preflight checks` returns `There is not enough free space to continue.` when available free space is less than the reserved total for zip backup bytes, rollback preimages, new/rewritten files, same-directory atomic temp files, and a safety margin of `max(64 MiB, 20% of the subtotal)`.
- After install preflight succeeds and before backup creation when `--dry-run` is not active, the runtime prompts `Would you like us to take a backup of your configs and proceed with installation?` and accepts `Y` or `Yes` case-insensitively.
- Any other install confirmation input returns `Installation cancelled.` and exits zero before backup creation or any write under `config/`.
- Status `creating backup` covers backup label creation and `.zip` archive creation for `/home/qidi/printer_data/config`.
- During `install` only, when `--dry-run` is not active and one or more installer-created backup zip files already exist under `/home/qidi/printer_data/`, the runtime may emit exactly one extra non-status line chosen at random from the approved backup-history message pool.
- The backup-history voice line must not replace required status strings, success strings, recovery guidance, or error messages.
- The backup-history voice line must not appear during `uninstall`, `--dry-run`, or preflight failures that stop before backup creation.
- After a successful new installer backup is created during `install`, the runtime prunes installer-created backup zip files under `/home/qidi/printer_data/` to retain only the newest three archives across install and uninstall backup prefixes; unrelated `.zip` files are ignored and `--dry-run` never prunes.
- Status `installing` starts before the first runtime write under `config/` and stays active through optional `config/saved_variables.cfg [Variables] enable_box = 1` and `value_tN = 'slotN'` prompt/writes, drift detection, `install.managed_tree`, `install.ensure_lines`, `patches.set_options[]`, `patches.delete_sections[]`, managed-tree postflight verification, `postflight.verify_lines`, and the final state-file write.
- Final install success returns `Installed.` after `config/tltg_optimized_state.yaml` is written.
- Final install success output lists only the `patches.set_options[]` targets skipped as user-modified.
- Final install success output lists `Managed tree drift overwritten:` only when existing `config/tltg-optimized-macros/` files differed from the prior installed-state ledger before mirror mode overwrote or removed them.
- Final install success output does not list `patches.set_options[]` targets that already matched `desired` before the run.
- Before managed-tree writes during `installing`, install prompts `We see {box_count} QIDI Box unit(s) recorded in saved_variables.cfg, but enable_box is 0. Would you like to enable QIDI Box support now?` when `[box_extras]` exists, `box_count > 0`, `enable_box == 0`, and input is interactive.
- Accepted QIDI Box enablement writes `enable_box = 1` in `config/saved_variables.cfg [Variables]`, prints `QIDI Box support enabled in saved_variables.cfg.`, and leaves the change out of the optimized install-state ledger.
- Any other QIDI Box enablement input prints `QIDI Box support left disabled.` and preserves the existing saved variable.
- Before managed-tree writes during `installing`, install prints each mismatched `value_tN: <current> -> slotN` and prompts `Tool numbers do not line up with slot numbers. Would you like us to correct this?` when any existing `config/saved_variables.cfg [Variables] value_tN` does not resolve to `slotN` after stripping surrounding string quotes.
- Accepted tool-slot correction writes each mismatched existing `value_tN = 'slotN'` in `config/saved_variables.cfg [Variables]`, prints `Tool-slot mappings corrected in saved_variables.cfg.`, and leaves the change out of the optimized install-state ledger.
- Any other tool-slot correction input prints `Tool-slot mappings left unchanged.` and preserves the existing saved variables.
- After final install success output, install prompts `Would you like to enable hourly automatic optimized config updates using a systemd timer?` when input is interactive.
- Accepted auto-update confirmation attempts to fetch the latest release `.sha256`; when the fetch succeeds it writes `config/tltg_optimized_auto_update_state.json`, and when the fetch fails it prints `Could not seed the latest release checksum; the first successful timer run will initialize auto-update state without installing.`.
- Accepted auto-update confirmation runs sudo commands through `sudo -S -p ''` using `TLTG_OPTIMIZED_SUDO_PASSWORD` when set, otherwise QIDI's public default password `qiditech`; if the initial `sudo -v` attempt fails and input is interactive, it prints `Initial sudo authentication failed.`, prompts `Enter sudo password to continue:`, retries `sudo -v` with that password, then uses that password for the remaining sudo commands.
- Accepted auto-update confirmation installs `/etc/systemd/system/tltg-optimized-auto-update.service` and `/etc/systemd/system/tltg-optimized-auto-update.timer`, runs `systemctl daemon-reload`, and runs `systemctl enable --now tltg-optimized-auto-update.timer` through sudo.
- Auto-update systemd setup failure prints `Could not enable auto-updates. <reason>` and does not change the successful install result.
- After the auto-update prompt returns or when auto-update prompting is skipped, the runtime prompts `Would you like me to restart Klipper to apply changes?` and accepts `Y` or `Yes` case-insensitively.
- Accepted restart confirmation triggers a local Moonraker `POST /printer/restart` request.
- Failed automatic restart prints `Could not restart Klipper automatically. Restart Klipper to apply changes.` and does not change the successful install result.
- Any other restart confirmation input returns without restarting and prints `Restart Klipper to apply changes.`.
- `install.sh --yes` suppresses interactive install confirmation, restart confirmation, and auto-update setup prompts; preflight checks still run. If QIDI Box enablement or tool-slot correction is detected, `--yes` applies the saved-variable change without prompting.

Auto-update runtime behavior:
- `auto-update.sh --run` calls installer mode `auto-update-check`.
- `auto-update-check` fetches the latest release checksum from GitHub and compares it to `config/tltg_optimized_auto_update_state.json latest_checksum`.
- Checksum fetch failure prints `Auto-update skipped because the latest release checksum could not be fetched.`, exits zero, and does not run the installer.
- Matching checksums print `Auto-update check: already current.` and do not run the installer.
- Missing checksum state writes the fetched checksum to `config/tltg_optimized_auto_update_state.json`, prints `Auto-update check: initialized latest release state.`, and does not run the installer.
- Changed checksums query local Moonraker `print_stats.state`; `printing` or `paused` prints `Auto-update skipped because a print is active or paused.` and does not run the installer.
- Unknown printer state prints `Auto-update skipped because printer state could not be determined.` and does not run the installer.
- Idle changed checksums fetch `install-latest.sh` from GitHub and run it as `/bin/sh <downloaded-script> --yes --plain`; the child installer still performs firmware, package-version, target, Moonraker idle, and free-space preflight checks before writing.
- Successful auto-update writes the new checksum to `config/tltg_optimized_auto_update_state.json` and prints `Auto-update complete.`.
- `auto-update.sh --enable-systemd` installs and enables the systemd service/timer through sudo without running the main install flow; sudo uses `TLTG_OPTIMIZED_SUDO_PASSWORD` when set, otherwise QIDI's public default password `qiditech`, and prompts for a password when the initial sudo attempt fails and input is interactive.
- `auto-update.sh --disable-systemd` disables `tltg-optimized-auto-update.timer`, removes the service/timer unit files from `/etc/systemd/system/`, reloads systemd, and removes `config/tltg_optimized_auto_update_state.json`; sudo uses `TLTG_OPTIMIZED_SUDO_PASSWORD` when set, otherwise QIDI's public default password `qiditech`, and prompts for a password when the initial sudo attempt fails and input is interactive.

Uninstall statuses and terminal messages:
- Status `checking firmware version` covers best-effort current firmware detection from `/home/qidi/update/firmware_manifest.json` for audit/reporting during uninstall.
- Missing or corrupt current firmware metadata does not block uninstall when `config/tltg_optimized_state.yaml` contains a valid installed-state ledger.
- Status `checking installed package` covers checking install markers from state-file path presence, managed-tree presence, and the active include line, plus reading and validating `config/tltg_optimized_state.yaml` when it exists.
- Guarded patch targets are checked as additional install markers only after a valid installed-state ledger has been loaded.
- Failure during `checking installed package` returns `Could not validate installed package state.` when any non-patch installation marker remains but `config/tltg_optimized_state.yaml` is missing, corrupt, schema-incompatible, lacks the required uninstall ledger fields, or contains patch tuples outside the explicit allowed tuple set for the stored installed package version in `installer/supported_upgrade_sources.yaml`.
- Missing install markers returns `Nothing to uninstall.` and exits zero before backup creation or any write under `config/`.
- Status `performing uninstall preflight checks` covers managed-tree paths, every patch target from the installed-state ledger, the local Moonraker printer-state query, and free-space checks.
- Failure during `performing uninstall preflight checks` returns `Could not determine printer state.` when local Moonraker `print_stats.state` data is unavailable, malformed, or inconsistent.
- Failure during `performing uninstall preflight checks` returns `Cannot continue while a print is active or paused.` when local Moonraker `print_stats.state` is `printing` or `paused`.
- Failure during `performing uninstall preflight checks` returns `There is not enough free space to continue.` when available free space is less than the reserved total for zip backup bytes, rollback preimages, new/rewritten files, same-directory atomic temp files, and a safety margin of `max(64 MiB, 20% of the subtotal)`.
- After uninstall preflight succeeds and before backup creation when `--dry-run` is not active, the runtime prompts `Are you sure you want to uninstall?` and accepts `Y` or `Yes` case-insensitively.
- Any other uninstall confirmation input returns `Uninstall cancelled.` and exits zero before backup creation or any write under `config/`.
- Status `creating backup` covers uninstall backup label creation and `.zip` archive creation for `/home/qidi/printer_data/config`.
- After a successful new installer backup is created during `uninstall`, the runtime prunes installer-created backup zip files under `/home/qidi/printer_data/` to retain only the newest three archives across install and uninstall backup prefixes; unrelated `.zip` files are ignored and `--dry-run` never prunes.
- Status `uninstalling` starts before the first uninstall write under `config/` and stays active through guarded patch reversal, include removal, managed-tree removal, uninstall postflight, and final state-file deletion.
- Final uninstall success returns `Uninstalled.` after uninstall postflight succeeds and `config/tltg_optimized_state.yaml` is deleted.
- Final uninstall success output lists only guarded patch targets preserved as user-modified.
- Final uninstall success output lists managed-tree drift only when `config/tltg-optimized-macros/` contained local modifications before removal.
- After final uninstall success output, uninstall removes `/etc/systemd/system/tltg-optimized-auto-update.service` and `/etc/systemd/system/tltg-optimized-auto-update.timer` through sudo when either unit file exists; sudo uses `TLTG_OPTIMIZED_SUDO_PASSWORD` when set, otherwise QIDI's public default password `qiditech`, and prompts for a password when the initial sudo attempt fails and input is interactive.
- Auto-update removal failure prints `Could not disable auto-updates. <reason>` and does not change the successful uninstall result.
- After auto-update removal returns or when no auto-update unit is installed, the runtime prompts `Would you like me to restart Klipper to apply changes?` and accepts `Y` or `Yes` case-insensitively.
- Accepted restart confirmation triggers a local Moonraker `POST /printer/restart` request.
- Failed automatic restart prints `Could not restart Klipper automatically. Restart Klipper to apply changes.` and does not change the successful uninstall result.
- Any other restart confirmation input returns without restarting and prints `Restart Klipper to apply changes.`.

Interrupt handling:
- `Ctrl+C` raises `KeyboardInterrupt`, prints `Interrupted. No further installer actions will run.`, returns exit code `130`, and does not print a Python traceback.

Rich terminal UI:
- When stdout is an interactive TTY and `TERM` is not `dumb`, `installer/runtime/reporter.py` renders the install, uninstall, dry-run, clear-recovery-sentinel, and restore-helper flows through the vendored Rich dependency under `installer/runtime/vendor/rich`.
- `--plain`, non-TTY stdout, `TERM=dumb`, or a missing vendored Rich dependency select `PlainReporter` and preserve the line-oriented status output.
- Rich install and uninstall status panels show `stage N/5`, the current status string, preflight target counters, and install/uninstall operation counters emitted by `installer/runtime/preflight.py`, `installer/runtime/runner.py`, and `installer/runtime/uninstall.py`.
- Rich confirmation prompts render the required question and instruction strings in a prompt panel before reading the same stdin response accepted by `installer/runtime/interaction.py`.
- Rich detail output renders preflight target reports, dry-run plans, user-modified patch reports, managed-tree drift, rollback recovery actions, restore backup lists, restore warnings, and restore verification in Rich panels or tables.
- Contract-required status strings, prompt strings, success strings, warning strings, recovery strings, and error strings remain present in Rich output and unchanged in `--plain` output.

Demo-TUI mode:
- `install.sh --demo-tui` renders the install status sequence `checking firmware version`, `checking package version`, `performing preflight checks`, `creating backup`, and `installing` without reading `/home/qidi/update/firmware_manifest.json`, `/home/qidi/printer_data/config`, or Moonraker.
- `install.sh --uninstall --demo-tui` renders the uninstall status sequence `checking firmware version`, `checking installed package`, `performing uninstall preflight checks`, `creating backup`, and `uninstalling` without reading `/home/qidi/update/firmware_manifest.json`, `/home/qidi/printer_data/config`, or Moonraker.
- Demo-TUI mode does not acquire `/home/qidi/printer_data/.tltg_optimized_installer.lock`, does not inspect `/home/qidi/printer_data/.tltg_optimized_recovery_required`, does not create backup archives under `/home/qidi/printer_data/`, and does not write under `/home/qidi/printer_data/config`.
- Demo-TUI mode waits 5 seconds after each visible status change before advancing to the next screen.
- Demo-TUI mode finishes with `Installed.` for install and `Uninstalled.` for uninstall.
- Demo-TUI mode does not emit confirmation prompts, backup-history lines, `Nothing to uninstall.`, or restart prompts.

Internal lock and recovery behavior:
- A single-run advisory lock is acquired before visible status changes and is not represented as a visible status.
- Lock acquisition does not reorder the visible install or uninstall status flow.
- The runtime checks `/home/qidi/printer_data/.tltg_optimized_recovery_required` before visible status changes.
- When the recovery sentinel exists, the run returns `Previous recovery did not complete. Restore from backup before continuing.` and stops before any further action.
- The documented safe clear path is `install.sh --clear-recovery-sentinel` only after restoring from the printed backup and verifying the runtime tree is consistent.
- `install.sh --clear-recovery-sentinel` clears `/home/qidi/printer_data/.tltg_optimized_recovery_required` only when the current `config/` tree byte-matches the recorded backup zip path stored in that sentinel.

Debug logging:
- `install.sh --debug` emits human-readable `debug | event=...` lines to stdout only.
- Debug output is terminal-only and is never persisted under `/home/qidi/printer_data/`.
- Contract-required status strings, success strings, recovery guidance, and error messages remain unchanged when `--debug` is not set.

Manual restore helper:
- Release bundles ship `restore.sh` beside `install.sh`.
- `restore.sh` uses `RichReporter` for restore backup lists, selected-backup details, destructive restore warning, and restore verification output when stdout is an interactive TTY and `TERM` is not `dumb`; `restore.sh --plain`, non-TTY stdout, `TERM=dumb`, or a missing vendored Rich dependency use `PlainReporter`.
- `restore.sh` lists installer-created backup zip files from `/home/qidi/printer_data/` by archive timestamp and label when no `--backup <path>` argument is provided.
- `restore.sh --backup <path>` restores the specified archive only when it contains a valid, non-empty archived `config/` snapshot.
- `restore.sh` warns that restore overwrites current config changes under `/home/qidi/printer_data/config`, requires an explicit `RESTORE` confirmation, stages the selected archive through a temporary directory, validates the staged `config/` snapshot before any live write, mirrors the staged snapshot into the live runtime tree, and verifies the restored tree before success output.
- `restore.sh` does not clear `/home/qidi/printer_data/.tltg_optimized_recovery_required`.
- After a valid restore when the recovery sentinel exists, the clear step remains `install.sh --clear-recovery-sentinel`.
Required install flow:
1. Acquire the single-run advisory lock before visible status changes.
2. Stop the run before visible status changes when `/home/qidi/printer_data/.tltg_optimized_recovery_required` exists.
3. Set the visible status to `checking firmware version` before reading `/home/qidi/printer_data/config`.
4. Detect the printer firmware from `/home/qidi/update/firmware_manifest.json` field `SOC.version` with installer-owned logic.
5. Stop the run before reading `config/tltg_optimized_state.yaml`, creating a backup, or writing any file under `config/` when firmware detection fails.
6. Compare the detected firmware string against `installer/package.yaml firmware.supported`.
7. Stop the run before reading `config/tltg_optimized_state.yaml`, creating a backup, or writing any file under `config/` when the detected firmware is not present in `installer/package.yaml firmware.supported`.
8. Set the visible status to `checking package version` after firmware support is confirmed.
9. Read and validate `config/tltg_optimized_state.yaml` when that file already exists.
10. Continue as a fresh install when `config/tltg_optimized_state.yaml` does not exist.
11. Compare the stored package version from `config/tltg_optimized_state.yaml` against `installer/package.yaml package.known_versions` when `config/tltg_optimized_state.yaml` exists.
12. Stop the run before backup or writes when previous install-state validation fails.
13. Set the visible status to `performing preflight checks` after package-version validation passes.
14. Validate every path in `installer/package.yaml preflight.required_files` before creating a backup or modifying runtime files.
15. Validate every `file + section` target in `installer/package.yaml preflight.required_sections` before creating a backup or modifying runtime files.
16. Validate every `file + line` target in `installer/package.yaml preflight.required_lines` before creating a backup or modifying runtime files.
17. Validate every unique `file + section + option` target in `installer/package.yaml patches.set_options[]` and every unique `file + section` target in `installer/package.yaml patches.delete_sections[]` before creating a backup or modifying runtime files.
18. Query local Moonraker `http://127.0.0.1:7125/printer/objects/query?print_stats` and inspect `print_stats.state` during preflight.
19. Preflight free space for zip backup bytes, rollback preimages, new/rewritten files, same-directory atomic temp files, and the configured safety margin before creating a backup or modifying runtime files.
20. Collect every missing file, section, line, and patch-target result in one pass instead of stopping on the first missing target.
21. Stop the run before backup or writes when any install preflight target is missing, printer-state data cannot be trusted, the printer is printing or paused, or free space is insufficient.
22. During non-dry-run install, prompt `Would you like us to take a backup of your configs and proceed with installation?` and accept only `Y` or `Yes` case-insensitively.
23. During non-dry-run install, print `Installation cancelled.` and exit zero before backup or writes when the confirmation input is anything else.
24. Set the visible status to `creating backup` after aggregated preflight checks pass and install confirmation succeeds.
25. Build the backup label from `installer/package.yaml backup.label_prefix`, the detected install firmware, `installer/package.yaml package.version`, and an install timestamp.
26. Create a `.zip` backup of `/home/qidi/printer_data/config` before any write to any file under `config/`.
27. Set the visible status to `installing` after the `.zip` backup completes.
28. When an existing installed-state ledger is present, compare current managed-tree file hashes against `managed_tree.files[]` from that ledger and record local managed-tree drift before mirror mode.
29. Compare prior `managed_tree.files[]` ledger hashes against the new bundle contents to distinguish expected bundle-version changes from local drift.
30. When `config/box.cfg [box_extras]` exists, `config/saved_variables.cfg [Variables] box_count > 0`, and `[Variables] enable_box == 0`, prompt to set `enable_box = 1` before managed-tree writes; accepted confirmation writes only `config/saved_variables.cfg` and does not add the value to `config/tltg_optimized_state.yaml`.
31. When existing `config/saved_variables.cfg [Variables] value_tN` entries do not equal `'slotN'`, prompt to rewrite each mismatched existing entry to `'slotN'` before managed-tree writes; accepted confirmation writes only `config/saved_variables.cfg` and does not add the values to `config/tltg_optimized_state.yaml`.
32. Create each directory listed in `installer/package.yaml install.ensure_directories` before mirroring installer-managed files.
33. Mirror `installer/klipper/tltg-optimized-macros/` into runtime `config/tltg-optimized-macros/` according to `installer/package.yaml install.managed_tree`.
34. Ensure `[include tltg-optimized-macros/*.cfg]` exists in runtime `config/printer.cfg` after `[include klipper-macros-qd/*.cfg]` according to `installer/package.yaml install.ensure_lines`, moving or deduping active include lines as needed.
35. Select the matching `variants[]` entry in each `installer/package.yaml patches.set_options[]` block with a matching `variants[].firmwares[]` entry.
36. Read the current value for each `file + section + option` target in `installer/package.yaml patches.set_options[]` from the runtime file before writing.
37. Write `desired` when the current runtime value equals `expected` in the selected `variants[]` entry.
38. Record a silent no-op for that patch when the current runtime value already equals `desired` in the selected `variants[]` entry.
39. Record that patch as user-modified when the current runtime value differs from both `expected` and `desired` in the selected `variants[]` entry.
40. For each `installer/package.yaml patches.delete_sections[]` target, delete the runtime section only when the current normalized section text SHA-256 equals the selected `variants[].expected_normalized_sha256`; store the deleted section text in `config/tltg_optimized_state.yaml patch_ledger[].expected` and store `__TLTG_SECTION_DELETED__` in `patch_ledger[].desired`.
41. Treat a missing `patches.delete_sections[]` target as an install no-op only when a prior valid installed-state ledger already contains that section-deletion patch target.
42. Record a section deletion patch as user-modified when the current section exists and its normalized SHA-256 does not match `variants[].expected_normalized_sha256`.
43. Validate every runtime file implied by `installer/package.yaml install.managed_tree` and every `file + line` target in `installer/package.yaml postflight.verify_lines` after the managed tree mirror and guarded patches complete.
44. Write `config/tltg_optimized_state.yaml` only after the install postflight checks pass.
45. Store `package.id`, `package.version`, detected install firmware, backup label, install timestamp, managed-tree file hashes, and the guarded patch ledger in `config/tltg_optimized_state.yaml`.
46. Trigger automatic rollback on any failure after the first runtime write, not only on postflight failure.
47. Leave the previous `config/tltg_optimized_state.yaml` content unchanged when the run stops before install postflight completion.
48. Print `Installed.`, then the final user-modified patch report, then `Managed tree drift overwritten:` when present.
49. Prompt for auto-update setup when input is interactive.
50. During accepted auto-update setup confirmation, attempt to fetch and store the latest release checksum, authenticate with sudo, install the systemd service/timer units, reload systemd, and enable/start `tltg-optimized-auto-update.timer`.
51. Continue systemd timer setup when the initial checksum seed fails; the first successful timer check initializes `config/tltg_optimized_auto_update_state.json` without installing.
52. Treat auto-update setup failure as non-fatal after install success.
53. Prompt `Would you like me to restart Klipper to apply changes?` and accept only `Y` or `Yes` case-insensitively.
54. During accepted restart confirmation, request local Moonraker `POST /printer/restart`.
55. Print `Could not restart Klipper automatically. Restart Klipper to apply changes.` when the restart request fails.
56. Print `Restart Klipper to apply changes.` and exit without restarting when the restart confirmation input is anything else.

Approved install backup-history message pool:
- `Change your mind, huh?`
- `Couldn't leave it alone, could you?`
- `We found old backups. Commitment issues?`
- `Well, well. Look who came crawling back.`
- `Existing rollback archives found. This is becoming a pattern.`
- `Prior backups located. This was apparently not a one-time event.`
- `Another reinstall. Must've gone great last time.`
- `Backup inventory is non-empty. Operator intent appears cyclical.`
- `Previous backup archives detected. Your confidence is noted.`
- `Existing backups located. This suggests prior dissatisfaction with your own decisions.`
- `Historical backup state located. The definition of "final" remains under review.`
- `Prior rollback points are available. Your optimism continues to exceed the evidence.`
- `Backup inventory is non-empty. Proceeding as though this was intentional.`

Required uninstall flow:
1. Acquire the single-run advisory lock before visible status changes.
2. Stop the run before visible status changes when `/home/qidi/printer_data/.tltg_optimized_recovery_required` exists.
3. Set the visible status to `checking firmware version`.
4. Attempt best-effort current firmware detection from `/home/qidi/update/firmware_manifest.json` for audit/reporting without requiring supported current firmware.
5. Set the visible status to `checking installed package`.
6. Check non-patch installation markers from state-file path presence, managed-tree presence, and the active `[include tltg-optimized-macros/*.cfg]` line.
7. Read and validate `config/tltg_optimized_state.yaml` when it exists.
8. Validate the stored installed package version against `installer/supported_upgrade_sources.yaml` when a state-file ledger is present.
9. Validate that every ledger patch target matches an explicit uninstall-allowed `file + section + option` tuple for that stored installed package version from `installer/supported_upgrade_sources.yaml`.
10. When a valid installed-state ledger is available, additionally treat guarded patch targets currently at recorded `desired` values as install markers.
11. Print `Nothing to uninstall.` and exit zero before backup or writes when no installation markers are present after the non-patch marker check and any valid-ledger patch-marker check.
12. Stop the run before backup or writes when any non-patch installation marker remains but the installed-state ledger is missing, corrupt, schema-incompatible, lacks the required uninstall ledger fields, stores an unsupported installed package version, or contains patch tuples outside the explicit allowed tuple set for that stored installed package version.
13. Set the visible status to `performing uninstall preflight checks`.
14. Validate `config/printer.cfg`, managed-tree paths, and every patch target from the installed-state ledger.
15. Resolve every uninstall patch target to exactly one active section and exactly one active option assignment; zero matches are missing targets and multiple matches are ambiguous targets.
16. Query local Moonraker `http://127.0.0.1:7125/printer/objects/query?print_stats` and inspect `print_stats.state` during uninstall preflight.
17. Preflight free space for zip backup bytes, rollback preimages, new/rewritten files, same-directory atomic temp files, and the configured safety margin before creating a backup or modifying runtime files.
18. Detect and record managed-tree drift against the installed-state file manifest before deletion.
19. Stop the run before backup or writes when uninstall preflight targets are missing or ambiguous, printer-state data cannot be trusted, the printer is printing or paused, or free space is insufficient.
20. During non-dry-run uninstall, prompt `Are you sure you want to uninstall?` and accept only `Y` or `Yes` case-insensitively.
21. During non-dry-run uninstall, print `Uninstall cancelled.` and exit zero before backup or writes when the confirmation input is anything else.
22. Set the visible status to `creating backup`.
23. Build the uninstall backup label as `tltg-optimized-macros-before-uninstall-<current-firmware-or-unknown-firmware>-<stored-package.version>-<timestamp>`, where the exact fallback token is `unknown-firmware`.
24. Create a `.zip` backup of `/home/qidi/printer_data/config` before any uninstall write to any file under `config/`.
25. Set the visible status to `uninstalling`.
26. For each guarded patch target from the installed-state ledger, write recorded `expected` only when the current runtime value still matches the recorded `desired` value.
27. Record a silent no-op for uninstall when the current runtime value already matches the recorded `expected` value.
28. Record that patch as user-modified when the current runtime value differs from both recorded `expected` and recorded `desired` values.
29. Remove the active `[include tltg-optimized-macros/*.cfg]` line from runtime `config/printer.cfg`.
30. Remove runtime `config/tltg-optimized-macros/` after managed-tree drift reporting.
31. Validate uninstall postflight: the include line is absent, the managed tree is absent, and reverted patch targets are at recorded `expected` values unless recorded as user-modified.
32. Delete `config/tltg_optimized_state.yaml` only after uninstall postflight passes.
33. Trigger automatic rollback on any failure after the first uninstall write, not only on uninstall postflight failure.
34. Keep `config/tltg_optimized_state.yaml` unchanged when uninstall stops before uninstall postflight completion.
35. Print `Uninstalled.`, then preserved user-modified patch targets, then managed-tree drift when present.
36. Remove the auto-update systemd service/timer after successful uninstall when either unit file exists.
37. Treat auto-update removal failure as non-fatal after uninstall success.
38. Prompt `Would you like me to restart Klipper to apply changes?` and accept only `Y` or `Yes` case-insensitively.
39. During accepted restart confirmation, request local Moonraker `POST /printer/restart`.
40. Print `Could not restart Klipper automatically. Restart Klipper to apply changes.` when the restart request fails.
41. Print `Restart Klipper to apply changes.` and exit without restarting when the restart confirmation input is anything else.

Patch semantics:
- Manifest validation requires every `installer/package.yaml patches.set_options[]` and `patches.delete_sections[]` block to provide exactly one matching `variants[]` entry for every `installer/package.yaml firmware.supported[]` value.
- `installer/package.yaml patches.set_options[] variants[].expected` is the runtime value the installer expects to find before writing a guarded install patch.
- `installer/package.yaml patches.set_options[] variants[].desired` is the runtime value the installer writes when the current runtime value still matches `expected`.
- Patch target section resolution requires exactly one active section header with the requested name.
- Patch target option resolution requires exactly one active assignment for the requested option inside the resolved section.
- Patch option matching trims surrounding whitespace around key and value, ignores inline comments, and does not numerically coerce values.
- Zero matching sections or options make the patch target missing.
- Multiple matching sections or options make the patch target ambiguous.
- Missing or ambiguous patch targets fail closed during preflight; the runtime never guesses which target to read or write.
- `installer/package.yaml patches.set_options[]` targets that already match `desired` are install silent no-ops.
- `installer/package.yaml patches.set_options[]` targets that match neither `expected` nor `desired` are treated as install user-modified and are reported after installation completes.
- `installer/package.yaml patches.delete_sections[] variants[].expected_normalized_sha256` is the SHA-256 of the normalized section text from `installer/runtime/klipper_cfg.py`, which removes comments and whitespace outside quoted strings.
- `installer/package.yaml patches.delete_sections[]` targets are deleted only when the live normalized section text hash matches `expected_normalized_sha256`.
- `installer/package.yaml patches.delete_sections[]` targets that are missing during reinstall are install silent no-ops only when the prior `config/tltg_optimized_state.yaml patch_ledger[]` already contains the same `file + section + __section__` tuple.
- `installer/package.yaml patches.delete_sections[]` targets whose live normalized section hash does not match `expected_normalized_sha256` are treated as install user-modified and fail install preflight before backup or writes.
- Uninstall uses the recorded `expected` and `desired` values from `config/tltg_optimized_state.yaml`, not the current bundle manifest, to decide guarded patch reversal.
- Uninstall accepts a ledger patch target only when its `file + section + option` tuple is explicitly allowed for the stored installed package version in `installer/supported_upgrade_sources.yaml`.
- Schema-valid installed-state ledgers are trusted as uninstall inputs; uninstall still refuses to overwrite a live runtime value unless that value matches the recorded `desired` value exactly.
