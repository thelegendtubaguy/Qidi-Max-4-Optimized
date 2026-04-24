# Qidi Max 4 Optimized

Optimized Klipper macros and slicer machine G-code for the QIDI Max 4.

## Install

### Printer Configs

You will need to SSH into the printer `qidi@<printer-ip>`.

From a shell on the printer, fetch the latest published installer from GitHub and run it:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)"
```

If you'd rather do a dry-run before committing to a full install, you can run this:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)" -- --dry-run
```

Before installing or uninstalling, the installer will run preflight checks to ensure safety.  It will also take a backup of your config directory before installing or uninstalling.  You will be prompted to install or uninstall after the preflight checks.

After a successful install, the installer asks whether to enable hourly automatic optimized config updates before asking whether to restart Klipper. Answering no to auto-updates still proceeds to the Klipper restart prompt. Auto-updates use a system-level systemd timer. Enabling auto-updates requires sudo once to install `/etc/systemd/system/tltg-optimized-auto-update.service` and `/etc/systemd/system/tltg-optimized-auto-update.timer`. Each hourly run checks the latest GitHub release checksum, skips while the printer is printing or paused, and then runs the normal installer with preflight checks and auto-approval. If the latest release checksum is unavailable during setup, the timer is still installed and the first successful check initializes update state without installing.

Disable auto-updates:

```bash
~/tltg-optimized-macros/auto-update.sh --disable-systemd
```

Run one auto-update check manually:

```bash
~/tltg-optimized-macros/auto-update.sh --run
```

### Slicer Machine GCode Updates
You will need to manually copy the machine GCode to your slicer of choice to take advantage of the optimized path.  The stock print path remains in place for backwards compatibility, safety, and general user happiness :)

Use the pack that matches your slicer. The two packs are functionally aligned, but their placeholder syntax is different due to variable type differences.
   - OrcaSlicer: `orcaslicer_gcode/`
   - QIDI Studio: `qidistudio_gcode/`

Use the pack that matches your slicer. The two packs are functionally aligned, but their placeholder syntax is different.

## Uninstall

Uninstall removes the auto-update systemd timer when it was installed by this package before asking whether to restart Klipper.

If `~/tltg-optimized-macros/` is still present on the printer:

```bash
~/tltg-optimized-macros/install.sh --uninstall --plain
```

If you want the same one-line GitHub fetch-and-run flow for uninstall:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)" -- --uninstall
```

## If something goes wrong

Read the installer output first. The installer stops before writing when firmware detection, preflight, printer state, or free-space checks fail.

Installer-created backup `.zip` files are stored under `/home/qidi/printer_data/` with `tltg-optimized-macros-before-optimize-...zip` and `tltg-optimized-macros-before-uninstall-...zip` labels.

Restore interactively:

```bash
ssh -t qidi@"$PRINTER_HOST" 'cd ~/tltg-optimized-macros && ./restore.sh'
```

Restore a specific backup:

```bash
ssh -t qidi@"$PRINTER_HOST" 'cd ~/tltg-optimized-macros && ./restore.sh --backup /home/qidi/printer_data/<backup-name>.zip'
```

If restore completed and the recovery sentinel is still present, clear it with:

```bash
ssh -t qidi@"$PRINTER_HOST" 'cd ~/tltg-optimized-macros && ./install.sh --clear-recovery-sentinel'
```

## Documentation

- [Verified behavior differences versus stock](docs/current_config_results_vs_stock_qidi_configs.md)
- [QIDI box internals and `BOX_PRINT_START`](docs/box_print_start_notes.md)
- [Optimized slicer temperature/print flow](docs/optimized_slicer_start_temperature_flow.md)

## Development

For development documentation, see [DEVELOPMENT](DEVELOPMENT.md).
