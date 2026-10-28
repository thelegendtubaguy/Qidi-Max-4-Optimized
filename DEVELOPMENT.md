# Running the dev branch

The `dev` branch is where new changes land before they make it into a release. Every push to `dev` builds a fresh installer and publishes it to the [`prerelease`](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/tag/prerelease) release on GitHub, so you can run the newest work on your printer without building anything yourself.

The catch is that it hasn't had the same testing as a release. On any given day something might be half-finished or just broken. If you only want a printer that works, use the normal install in the [README](README.md) instead.

> [!CAUTION]
> I refuse to be responsible for your printer. PLEASE watch prints start ensuring the printer doesn't do something horrible like gouge your bed and be ready to cut power at a moment's notice. That goes double on dev.

## Installing

1. SSH into your printer: `ssh qidi@<your printer's ip>`
2. Paste this in and run it. It's one command split across two lines, so copy both:

   ```bash
   TLTG_INSTALLER_ARCHIVE_URL=https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/download/prerelease/tltg-optimized-macros-dev.tar.gz \
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/thelegendtubaguy/Qidi-Max-4-Optimized/dev/installer/release/install-latest.sh)"
   ```

3. Follow the prompts. They're the same as a normal install with one exception: **answer No to automatic updates.** Auto-updates only follow stable releases, so with them on, your printer will quietly drift back to the stable version.
4. Update your slicer. Copy the machine G-code from the `dev` branch so it matches the macros you just installed: [`orcaslicer_gcode/`](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/tree/dev/orcaslicer_gcode) for OrcaSlicer, or [`qidistudio_gcode/`](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/tree/dev/qidistudio_gcode) for QIDI Studio.

To pick up newer dev changes later, run the same command again. Do the same with the slicer G-code if it has changed.

### Already have auto-updates turned on?

Turn them off before (or right after) installing dev, or the next stable release will replace your dev install:

```bash
~/tltg-optimized-macros/auto-update.sh --disable-systemd
```

### Want a look before anything changes?

Add `-- --dry-run` to the end of the command. The installer will show what it would do without writing anything:

```bash
TLTG_INSTALLER_ARCHIVE_URL=https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/download/prerelease/tltg-optimized-macros-dev.tar.gz \
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/thelegendtubaguy/Qidi-Max-4-Optimized/dev/installer/release/install-latest.sh)" -- --dry-run
```

## Going back to stable

Run the normal install command from the [README](README.md). It replaces the dev install with the latest release, and you can turn auto-updates back on then if you want them.

To remove everything instead:

```bash
~/tltg-optimized-macros/install.sh --uninstall --plain
```

Backups, restore, and recovery all work the same as on a release. See [If something goes wrong](README.md#if-something-goes-wrong) in the README.

## Telling me how it went

Good or bad, I want to hear about it. [TESTING.md](TESTING.md) covers what's useful to include. Open an issue here on GitHub or come chat in the [TubaMakes Discord](https://l.tubaguy.com/tmdiscord).

## Working on the code

The rest of this page is for people changing the repo itself.

### Test a local build on your printer

This builds a dev bundle from your checkout, copies it to the printer, and runs a dry-run there:

```bash
scripts/build_copy_dry_run.sh --host <printer-ip>
```

It connects as `qidi` by default. Use `--user <name>` to change that, `--password '<password>'` if you aren't using SSH keys (this needs `sshpass` installed locally), and `--debug` for extra installer output.

### Checks to run before opening a PR

Run the ones that match what you touched:

```bash
# Installer behavior
python3 scripts/run_installer_core_tests.py

# installer/package.yaml or installer/supported_upgrade_sources.yaml
python3 scripts/check_installer_known_versions.py

# Slicer G-code in orcaslicer_gcode/ or qidistudio_gcode/
python3 scripts/check_optimized_slicer_macros.py

# Anything in installer/klipper/tltg-optimized-macros/
python3 scripts/format_klipper_configs.py

# Bundle or launcher changes: build and smoke-test the dev and release bundles
python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id local --smoke-test
python3 scripts/build_installer_bundle.py --output-dir dist --channel release --smoke-test
```

### THR firmware

Building and checking the Max 4 LIS2DW FIFO fix is covered in [`firmware/README.md`](firmware/README.md). The firmware is separate from the macro installer bundle, and building or checking it never flashes a printer.

### Pointing the installer at a fake printer

`installer/runtime/cli.py` reads these environment variables, so tests can run against a fixture directory instead of a live printer:

- `TLTG_OPTIMIZED_PRINTER_DATA_ROOT`
- `TLTG_OPTIMIZED_FIRMWARE_MANIFEST`
- `TLTG_OPTIMIZED_MOONRAKER_URL`

`installer/tests/helpers.py` and `scripts/smoke_test_installer_bundle.py` both use them.
