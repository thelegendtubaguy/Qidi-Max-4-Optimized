# Qidi Max 4 Optimized

Optimized Klipper macros and slicer machine G-code for the QIDI Max 4.

This repository is a machine-specific QIDI Max 4 configuration and installer, not a universal profile for every printer.

Current installer support: firmware `01.01.06.02`.

## Install

These commands assume SSH access to `qidi@<printer-ip>`.

From a shell on the printer, fetch the latest published installer from GitHub and run it:

```bash
rm -rf ~/tltg-optimized-macros && curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/tltg-optimized-macros.tar.gz | tar -xz -C ~ && ~/tltg-optimized-macros/install.sh --plain
```

Dry-run variant:

```bash
rm -rf ~/tltg-optimized-macros && curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/tltg-optimized-macros.tar.gz | tar -xz -C ~ && ~/tltg-optimized-macros/install.sh --dry-run --plain
```

`--plain` is the recommended mode for now because it produces cleaner terminal output than the current TUI path.

TUI preview only:

```bash
~/tltg-optimized-macros/install.sh --demo-tui
~/tltg-optimized-macros/install.sh --uninstall --demo-tui
```

`--demo-tui` renders the normal install or uninstall status screens without touching `/home/qidi/printer_data/config` and waits 5 seconds between screens.

Real install and uninstall runs prompt for confirmation after preflight checks and ask whether to restart Klipper after the changes are written.

Manual copy-and-run flow from another machine:

1. Download the latest release asset: `tltg-optimized-macros.tar.gz`.
2. Copy it to the printer:

```bash
PRINTER_HOST=<printer-ip>
INSTALLER_TARBALL=~/Downloads/tltg-optimized-macros.tar.gz
scp "$INSTALLER_TARBALL" qidi@"$PRINTER_HOST":~/
```

3. Extract it on the printer:

```bash
ssh qidi@"$PRINTER_HOST" 'rm -rf ~/tltg-optimized-macros && tar -xzf ~/tltg-optimized-macros.tar.gz -C ~/'
```

4. Optional dry run:

```bash
ssh -t qidi@"$PRINTER_HOST" 'cd ~/tltg-optimized-macros && ./install.sh --dry-run --plain'
```

5. Install for real:

```bash
ssh -t qidi@"$PRINTER_HOST" 'cd ~/tltg-optimized-macros && ./install.sh --plain'
```

6. Replace your slicer machine G-code with the matching pack from this repo:
   - OrcaSlicer: `orcaslicer_gcode/`
   - QIDI Studio: `qidistudio_gcode/`

Use the pack that matches your slicer. The two packs are functionally aligned, but their placeholder syntax is different.

## Uninstall

If `~/tltg-optimized-macros/` is still present on the printer:

```bash
~/tltg-optimized-macros/install.sh --uninstall --plain
```

If you want the same one-line GitHub fetch-and-run flow for uninstall:

```bash
rm -rf ~/tltg-optimized-macros && curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/tltg-optimized-macros.tar.gz | tar -xz -C ~ && ~/tltg-optimized-macros/install.sh --uninstall --plain
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

## Technical notes

- Verified behavior differences versus stock: `docs/current_config_results_vs_stock_qidi_configs.md`
- QIDI box internals and `BOX_PRINT_START`: `docs/box_print_start_notes.md`
- Optimized slicer temperature flow: `docs/optimized_slicer_start_temperature_flow.md`

## Development

For development documentation, see [DEVELOPMENT.md](DEVELOPMENT.md).
