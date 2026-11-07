# Installing, updating, and uninstalling

[← Back to the README](../README.md)

## Install

SSH into your printer as `qidi@<your printer's ip>` and run:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/valve-oil/releases/latest/download/install-latest.sh)"
```

Running it with `sudo` works the same: the installer switches to `qidi` and asks for `sudo` itself when it needs it, so every file it writes belongs to `qidi` either way. The same goes for `restore.sh`, `auto-update.sh`, and `box-firmware.sh`.

The installer checks which printer it's on and its firmware (see [Supported printers](../README.md#supported-printers)), the printer's state, and free space before writing anything, and makes a backup of your configuration first. Along the way it asks about:

- **Toolhead board firmware fix** (Max 4 with firmware `01.01.07.01` only): asked first, before anything changes. The default is No. See [Firmware fixes](firmware.md).
- **Disable QIDI AI detection**, only while it's on: turns off QIDI's `algo_app` service. When the installer has finished its system changes, it reminds you to also turn off Spaghetti Detection and Foreign Object Detection in the touchscreen's Settings -> Printing Options, so the screen matches.
- **Automatic updates**: see [below](#automatic-updates).
- **QIDI Box setup**, when Box support is off or tool numbers don't match slot numbers.
- **Restarting Klipper** to apply the changes.

It applies the [OS optimizations](#os-optimizations) without asking. The system changes, including restarting Moonraker and the touchscreen, take a little over a minute on a first install; the installer names each one as it goes. When they need a reboot, the installer reboots the printer about 10 seconds after it finishes.

After installing, close every Fluidd tab and open Fluidd again.

### Dry run

To see what the installer would do without changing anything:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/valve-oil/releases/latest/download/install-latest.sh)" -- --dry-run
```

### OS optimizations

Every install and update applies these, including on printers where an earlier install skipped them. The printer has little memory and CPU to spare, and each release is tested with them on. Uninstall asks whether to undo them:

- Adding `1.1.1.1` and `8.8.8.8` as fallback DNS servers.
- Pointing the printer's package sources at Debian's official servers.
- Turning off services the printer doesn't use: `xl2tpd`, `bluetooth`, and QIDI AI detection if you choose.
- Turning off [ADB](#adb), which gives anyone on your network a root shell on the printer without a password.
- Stopping a broken QIDI boot service from leaving the printer's storage in slow synchronous mode.
- Compressed swap in memory ([zram](#zram-swap)), so the printer doesn't run out of memory.
- Running the CPU at full speed, so Klipper's short bursts of work don't start at a third of it. With a 65 °C chamber, the processor ran about 1 °C warmer, 11 °C below where it starts slowing itself down.
- Still images instead of animations on the touchscreen.

When an install or update turns on zram swap, the CPU setting, the service priorities, or the storage repair, they take effect straight away, and the printer then reboots by itself, never during a print, to confirm they start at boot:

- An install reboots the printer about 10 seconds after it finishes, without asking, unless a print is running or paused. It checks again just before rebooting.
- An automatic update reboots only once Klipper has been idle for 10 minutes: no print running or paused, no command running, the toolhead still, and every heater, including the Box dryers, off. Until then, each hourly check tries again.

### Zram swap

The Max 4 has 486 MB of memory and no swap. QIDI's AI detection alone can hold about 190 MB during a print, and when memory runs out, Linux makes room by dropping program code that has to be read back from storage. Klipper then stalls for seconds at a time, and a stall during a print can end it with `MCU 'mcu' shutdown: Missed scheduling of next digital out event`, often right when a print is cancelled.

Zram gives Linux a compressed swap area in memory instead: 256 MB of swap that holds about 2.3 MB of idle data per MB of memory it uses. On a Max 4, with memory filled the way it was on a printer that hit this shutdown, Klipper's longest delay went from 405 ms to 4 ms, and the program that filled memory was no longer killed.

QIDI's kernel has no zram, so the package carries its own modules, built for the Max 4's kernel `5.10.160 #4 SMP PREEMPT Wed Sep 3 15:21:57 CST 2025`. They load only on that exact kernel; on any other, including after a QIDI update that changes it, the printer runs without zram until a package release supports that kernel. To check that zram is on, run `cat /proc/swaps` over SSH and look for `/dev/zram0`.

### ADB

QIDI's system image runs ADB (Android Debug Bridge) as `root` on TCP port 5555, on every network the printer joins, with no authentication. Anyone who can reach the printer can run commands on it as root, and changing the `qidi` password doesn't stop them, since ADB doesn't use it. It comes from `usbdevice.service`, a leftover from Rockchip's board image whose only function is ADB. Nothing QIDI ships uses it, and the USB port for flash drives is separate and keeps working.

The installer stops and disables `usbdevice.service`. To check that ADB is off, run `sudo ss -tlnp | grep 5555` over SSH; it should print nothing. If QIDI support asks for ADB, `sudo systemctl start usbdevice` turns it back on until the printer reboots or the next install or automatic update check turns it off again.

## Slicer start G-code

> [!TIP]
> On the Max 4, in OrcaSlicer 2.4.0 or later, subscribe to the [OrcaCloud bundle](https://cloud.orcaslicer.com/b/4c4b3b74c745). Your slicer then gets updates by itself, with nothing to copy and paste.

Otherwise, copy the machine G-code into your slicer by hand from the folder for your slicer and printer:

| Slicer | QIDI Max 4 | QIDI Plus 5 |
|---|---|---|
| OrcaSlicer | [`orcaslicer_gcode/`](../orcaslicer_gcode/) | [`orcaslicer_gcode/plus5/`](../orcaslicer_gcode/plus5/) |
| QIDI Studio | [`qidistudio_gcode/`](../qidistudio_gcode/) | [`qidistudio_gcode/plus5/`](../qidistudio_gcode/plus5/) |

The two do the same thing; only their placeholder syntax differs. Files sliced with QIDI's stock G-code still print normally after installing, without the faster start.

## Updating

Run the install command again. Updates keep your settings.

### Automatic updates

If you turn them on, the printer checks for a new release every hour and installs it, skipping any check while a print is running or paused. Each update runs the same checks as a normal install, applies the [OS optimizations](#os-optimizations), and reboots the printer when they need it, once Klipper has been idle for 10 minutes.

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
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/valve-oil/releases/latest/download/install-latest.sh)" -- --uninstall
```

Uninstall always puts back everything an install changes in QIDI's own files: Fluidd goes back to QIDI's Fluidd, the Printer screen service is removed, and QIDI's Moonraker and Klipper files are restored. It then asks whether to also undo the [OS optimizations](#os-optimizations); `--keep-system-optimizations` keeps them without asking. Files you changed after installing are left alone and listed.

Uninstall does not change firmware. To go back to stock firmware, see [Firmware fixes](firmware.md).
