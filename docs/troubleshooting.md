# If something goes wrong

[← Back to the README](../README.md)

## The installer stopped

Read the installer's output first. It stops before writing anything when firmware detection, preflight, printer state, or free-space checks fail, and says why.

**Klipper is stopped with an error,** such as `... is not a valid config section`: you can still run the installer. It installs its files first, restarts Klipper, and then updates saved settings. If Klipper still doesn't start, the installer says so; fix the error shown in Fluidd and run the installer again.

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

Open a [GitHub issue](https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/issues) with the installer output or the end of `klippy.log`, your QIDI firmware version, and which slicer you used.
