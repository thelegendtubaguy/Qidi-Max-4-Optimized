# Installing, updating, and uninstalling

[← Back to the README](../README.md)

## Install

SSH into your printer as `qidi@<your printer's ip>` and run:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)"
```

The installer checks your firmware, the printer's state, and free space before writing anything, and makes a backup of your configuration first. Along the way it asks about:

- **Toolhead board firmware fix** (firmware `01.01.07.01` only): asked first, before anything changes. The default is No. See [Firmware fixes](firmware.md).
- **System hardening and OS optimizations**: see [below](#os-optimizations).
- **Disable QIDI AI detection**: turns off QIDI's `algo_app` service.
- **Automatic updates**: see [below](#automatic-updates).
- **QIDI Box setup**, when Box support is off or tool numbers don't match slot numbers.
- **Restarting Klipper** to apply the changes.

After installing, close every Fluidd tab and open Fluidd again.

### Dry run

To see what the installer would do without changing anything:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)" -- --dry-run
```

### OS optimizations

These are optional, and uninstall asks whether to undo them:

- Adding `1.1.1.1` and `8.8.8.8` as fallback DNS servers.
- Pointing the printer's package sources at Debian's official servers.
- Turning off services the printer doesn't use: `xl2tpd`, `bluetooth`, and optionally QIDI AI detection.
- Stopping a broken QIDI boot service from leaving the printer's storage in slow synchronous mode. The installer may offer a reboot to confirm the repair.
- Still images instead of animations on the touchscreen.

Everything else in [What you get](../README.md#what-you-get) is installed whether or not you choose these.

## Slicer start G-code

> [!TIP]
> In OrcaSlicer 2.4.0 or later, subscribe to the [OrcaCloud bundle](https://cloud.orcaslicer.com/b/4c4b3b74c745). Your slicer then gets updates by itself, with nothing to copy and paste.

Otherwise, copy the machine G-code into your slicer by hand from the folder for your slicer:

- OrcaSlicer: [`orcaslicer_gcode/`](../orcaslicer_gcode/)
- QIDI Studio: [`qidistudio_gcode/`](../qidistudio_gcode/)

The two do the same thing; only their placeholder syntax differs. Files sliced with QIDI's stock G-code still print normally after installing, without the faster start.

## Updating

Run the install command again. Updates keep your settings.

### Automatic updates

If you turn them on, the printer checks for a new release every hour and installs it, skipping any check while a print is running or paused. Each update runs the same checks as a normal install.

Turning them on needs `sudo` once. The installer uses QIDI's public default password (`qiditech`), or the `TLTG_OPTIMIZED_SUDO_PASSWORD` environment variable if set, and asks for a password if that doesn't work.

```bash
# Turn automatic updates off
~/tltg-optimized-macros/auto-update.sh --disable-systemd

# Check for an update now
~/tltg-optimized-macros/auto-update.sh --run
```

## Uninstall

If `~/tltg-optimized-macros/` is still on the printer:

```bash
~/tltg-optimized-macros/install.sh --uninstall --plain
```

Or fetch the latest installer and uninstall with it:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)" -- --uninstall
```

Uninstall always puts back everything an install changes in QIDI's own files: Fluidd goes back to QIDI's Fluidd, the Printer screen service is removed, and QIDI's Moonraker and Klipper files are restored. It then asks whether to also undo the [OS optimizations](#os-optimizations); `--keep-system-optimizations` keeps them without asking. Files you changed after installing are left alone and listed.

Uninstall does not change firmware. To go back to stock firmware, see [Firmware fixes](firmware.md).
