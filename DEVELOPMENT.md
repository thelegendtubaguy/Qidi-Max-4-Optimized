# Running the dev branch

Every push to `dev` publishes a fresh installer to the [`prerelease`](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/tag/prerelease) release. It hasn't had a release's testing, so something may be half-finished or broken. If you only want a printer that works, use the [README](README.md) install instead.

> [!CAUTION]
> I refuse to be responsible for your printer. PLEASE watch prints start ensuring the printer doesn't do something horrible like gouge your bed and be ready to cut power at a moment's notice. That goes double on dev.

## Install

1. SSH into your printer: `ssh qidi@<your printer's ip>`
2. Run this. It's one command on two lines, so copy both. Add `-- --dry-run` to the end to preview without changing anything.

   ```bash
   TLTG_INSTALLER_ARCHIVE_URL=https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/download/prerelease/tltg-optimized-macros-dev.tar.gz \
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/thelegendtubaguy/Qidi-Max-4-Optimized/dev/installer/release/install-latest.sh)"
   ```

3. **Answer No to automatic updates.** They follow stable releases and would replace your dev install. If they're already on, run `~/tltg-optimized-macros/auto-update.sh --disable-systemd`.
4. Copy the slicer G-code from the `dev` branch: [`orcaslicer_gcode/`](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/tree/dev/orcaslicer_gcode) or [`qidistudio_gcode/`](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/tree/dev/qidistudio_gcode).

Run both again to pick up newer dev changes.

**Going back to stable:** run the [README](README.md) install command, then turn automatic updates back on if you want them. To remove everything, see [Uninstall](docs/install.md#uninstall). Backups and restore work as on a release; see [If something goes wrong](docs/troubleshooting.md).

**Tell me how it went,** good or bad: see [TESTING.md](TESTING.md), open an issue, or come chat in the [TubaMakes Discord](https://l.tubaguy.com/tmdiscord).

## Working on the code

- **Try a local build on your printer:** `scripts/build_copy_dry_run.sh --host <printer-ip>` builds a dev bundle from your checkout, copies it over, and runs a dry run. Options: `--user <name>` (default `qidi`), `--password '<password>'` (needs `sshpass`), `--debug`.
- **Before opening a PR,** run the checks for what you touched, listed under **Validation** in [AGENTS.md](AGENTS.md#validation).
- **THR firmware:** building and checking the FIFO fix is in [`firmware/README.md`](firmware/README.md). It never flashes a printer.
- **Fake printer:** `TLTG_OPTIMIZED_PRINTER_DATA_ROOT`, `TLTG_OPTIMIZED_FIRMWARE_MANIFEST`, and `TLTG_OPTIMIZED_MOONRAKER_URL` point the installer at a fixture directory instead of a live printer, as `installer/tests/helpers.py` and `scripts/smoke_test_installer_bundle.py` do.
