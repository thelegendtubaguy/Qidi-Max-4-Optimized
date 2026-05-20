# Installer_Restore_Helper

- Release bundles place `restore.sh` beside `install.sh` at the extracted bundle root.
- `restore.sh` launches `python3 -I -S installer/runtime/bootstrap.py restore-backup` from the bundle root.
- `restore.sh` uses `RichReporter` for backup selection, selected-backup details, restore warning, and restore verification output when stdout is an interactive TTY and `TERM` is not `dumb`; `restore.sh --plain`, non-TTY stdout, `TERM=dumb`, or a missing vendored Rich dependency use `PlainReporter`.
- `restore.sh` without arguments lists installer-created backup archives from `/home/qidi/printer_data/` by parsed archive timestamp, label, and path.
- Install and uninstall archives use `tltg-optimized-macros-before-optimize-...zip` and `tltg-optimized-macros-before-uninstall-...zip` labels under `/home/qidi/printer_data/`.
- `restore.sh --backup /path/to/archive.zip` restores the specified archive only when it contains a valid, non-empty archived `config/` snapshot.
- The helper stages the selected archive in a temporary directory, validates the staged `config/` payload there, copies the staged snapshot to a full replacement tree under `/home/qidi/printer_data/`, and only then swaps the replacement tree into `/home/qidi/printer_data/config` with directory renames.
- The helper restores the archived `config/` snapshot from the selected zip, including `config/printer.cfg`, `config/tltg_optimized_state.yaml`, `config/tltg-optimized-macros/`, patched stock files, include-line state, recorded `system_ledger` metadata, and any other archived files under `config/`.
- The helper replaces the live `config/` tree with the archived snapshot, so runtime files absent from the selected archive are removed by the directory swap instead of by per-file deletion before replacement writes complete; ignored direct `config/KAMP` and `config/fluidd.cfg` symlinks are preserved when absent from the selected archive.
- The helper prints a destructive warning for `/home/qidi/printer_data/config` and requires typing `RESTORE` before writing.
- The helper verifies `/home/qidi/printer_data/config` byte-matches the selected archive before printing success, excluding ignored direct `config/KAMP` and `config/fluidd.cfg` symlinks.
- The helper does not restore `/etc/resolv.conf`, `/etc/resolvconf/resolv.conf.d/*`, `/etc/apt/sources.list`, systemd service state, or `/home/qidi/QIDI_Client/access` files by itself; system setting restore is handled by `install.sh --uninstall` when the operator accepts the system restore prompt.
- The helper does not clear `/home/qidi/printer_data/.tltg_optimized_recovery_required`.
- After restoring the correct archive and verifying `/home/qidi/printer_data/config`, clear the recovery sentinel with `install.sh --clear-recovery-sentinel`.
