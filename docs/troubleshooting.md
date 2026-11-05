# If something goes wrong

[← Back to the README](../README.md)

## The installer stopped

Read the installer's output first. It stops before writing anything when firmware detection, preflight, printer state, or free-space checks fail, and says why.

**`[Errno 13] Permission denied: '/home/qidi/printer_data/.tltg_optimized_installer.lock'`** or **`Could not validate previous package version.`** after an earlier run with `sudo`: versions before 26.11.02.1 ran as root when started with `sudo` and left the files they created owned by root, which a later run as `qidi` couldn't open. Install the current version, with or without `sudo`; it gives those files back to `qidi` before it starts.

**Klipper is stopped with an error,** such as `... is not a valid config section`: you can still run the installer. It installs its files first, restarts Klipper, and then updates saved settings. If Klipper still doesn't start, the installer says so; fix the error shown in Fluidd and run the installer again.

## The touchscreen says "Printer service failed to start"

QIDI's touchscreen shows `Printer service failed to start` (`QDC_400_005_015_001`) when it can't reach Moonraker for about 50 seconds, and keeps showing it after Moonraker is back. If Fluidd loads and shows the printer, Moonraker is running again: restart the touchscreen app from Fluidd's power menu (see [Restart the touchscreen app](fluidd.md#restart-the-touchscreen-app)), or reboot the printer. Install, update, and uninstall restart the touchscreen app whenever they restart Moonraker, so the message doesn't stay after them.

If Fluidd can't connect either, Moonraker isn't running. Over SSH, `systemctl status moonraker` shows why, and the end of `~/printer_data/logs/moonraker.log` usually names the error.

## Restore a backup

Every install and uninstall saves a backup `.zip` of your configuration under `/home/qidi/printer_data/`, named `tltg-optimized-macros-before-optimize-...zip` or `tltg-optimized-macros-before-uninstall-...zip`.

Restore interactively over SSH:

```bash
cd ~/tltg-optimized-macros && ./restore.sh
```

Restore a specific backup:

```bash
cd ~/tltg-optimized-macros && ./restore.sh --backup /home/qidi/printer_data/<backup-name>.zip
```

If restore completed and the recovery sentinel is still present, clear it with:

```bash
cd ~/tltg-optimized-macros && ./install.sh --clear-recovery-sentinel
```

To remove everything instead, see [Uninstall](install.md#uninstall).

## Box link monitor

When a Box drops off its USB link with `Lost communication with MCU 'mcu_boxN'`, nothing records why by default. The Box link monitor does. It's **off by default**; turn it on from Fluidd's console:

```gcode
SAVE_VARIABLE VARIABLE=tltg_box_link_monitor VALUE=1
```

It writes `printer_data/logs/tltg_box_link.log`, separate from `klippy.log` so it survives log rotation. The log is capped at 2 MB and rotates once to `tltg_box_link.log.1`. Set the variable back to `0` to stop recording; this takes effect without a restart.

**When reporting a Box disconnect,** attach this file along with the end of `klippy.log`.

**To find out why a Box dropped:**

1. Turn the Box off and on before printing.
2. After a drop, use `RESTART` or restart the Klipper service, not `FIRMWARE_RESTART`, so the monitor reads the Box before Klipper restarts it.

### Reading the log

- **Context:** Box MCU serial counters and any change to them, Box heater, Box processor temperature, and print state, for up to four Boxes.
- **The first failure line** from `klippy.log`: `Got EOF when reading from device`, `Timeout with MCU`, or `shutdown:`, plus the kernel USB lines at that moment.
- **`serial-history mcu_boxN:`** lines, written at that first failure: the last messages Klipper sent to and received from each Box, with their times. They show how long the Box went quiet before it disconnected and what Klipper last asked it to do. A `serial-history clock` line records when they were saved, for lining them up with the kernel USB lines.
- **`reset-reason mcu_boxN`** lines: what each Box reports when Klipper connects to it, or right away if you turn the monitor on while Klipper is running. The Box reports the most serious reset since it was turned on, not the latest:
  - `PowerOn`: nothing but power-on, or a power dip, since the Box was turned on.
  - `Software`: Klipper restarted the Box with `FIRMWARE_RESTART`, and nothing more serious happened.
  - `IndependentWatchdog`: the Box's firmware stopped responding and its watchdog restarted it at least once since it was turned on.

  `FIRMWARE_RESTART` changes `PowerOn` to `Software`, but it can't hide `IndependentWatchdog`.

## Reporting a problem

Open a [GitHub issue](https://github.com/thelegendtubaguy/valve-oil/issues) with the installer output or the end of `klippy.log`, your printer model and QIDI firmware version, and which slicer you used.
