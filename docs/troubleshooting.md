# If something goes wrong

[← Back to the README](../README.md)

## The installer stopped

Read the installer's output first. It stops before writing anything when firmware detection, preflight, printer state, or free-space checks fail, and says why.

**`[Errno 13] Permission denied: '/home/qidi/printer_data/.tltg_optimized_installer.lock'`** or **`Could not validate previous package version.`** after an earlier run with `sudo`: versions before 26.11.02.1 ran as root when started with `sudo` and left the files they created owned by root, which a later run as `qidi` couldn't open. Install the current version, with or without `sudo`; it gives those files back to `qidi` before it starts.

**Klipper is stopped with an error,** such as `... is not a valid config section`: you can still run the installer. It installs its files first, restarts Klipper, and then updates saved settings. If Klipper still doesn't start, the installer says so; fix the error shown in Fluidd and run the installer again.

## The touchscreen says "Printer service failed to start"

QIDI's touchscreen shows `Printer service failed to start` (`QDC_400_005_015_001`) when it can't reach Moonraker for about 50 seconds, and keeps showing it after Moonraker is back. If Fluidd loads and shows the printer, Moonraker is running again: restart the touchscreen app from Fluidd's power menu (see [Restart the touchscreen app](fluidd.md#restart-the-touchscreen-app)), or reboot the printer. Install, update, and uninstall restart the touchscreen app whenever they restart Moonraker, so the message doesn't stay after them.

If Fluidd can't connect either, Moonraker isn't running. Over SSH, `systemctl status moonraker` shows why, and the end of `~/printer_data/logs/moonraker.log` usually names the error.

## The camera doesn't show in Fluidd

At boot, QIDI's `makerbase-webcam.service` writes the camera into `~/printer_data/config/crowsnest.conf`. It could run before the camera's device link existed and write an empty `device:` line instead, and then crowsnest, which streams the camera, doesn't start and Fluidd shows no camera. The package makes it wait for the camera, so the next reboot fills the line in again.

To fix it without rebooting, run `sudo systemctl restart makerbase-webcam` over SSH. The camera comes back about 30 seconds later. If it still doesn't, `systemctl status crowsnest` and the end of `~/printer_data/logs/crowsnest.log` show why.

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

Open a [GitHub issue](https://github.com/thelegendtubaguy/valve-oil/issues/new/choose) and pick the form that fits. Each form asks for the printer details below, and for the logs that show what happened.

### Printer details

SSH into the printer, paste this whole block, and copy everything it prints into the issue. It only reads files; it changes nothing and works whether or not Valve Oil is installed.

```bash
python3 - <<'PY'
import json, os, re, subprocess
def run(*cmd):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as exc: return f"unavailable ({exc.__class__.__name__})"
home = os.path.expanduser("~")
state = os.path.join(home, "printer_data/config/tltg_optimized_state.yaml")
try:
    text = open(state).read()
    print("Valve Oil:", re.search(r"^  version: *'?([0-9.]+)", text, re.M).group(1),
          "installed", re.search(r"^installed_at: *'?([^'\n]+)", text, re.M).group(1))
except Exception:
    print("Valve Oil: not installed")
try:
    for name, part in json.load(open("/home/qidi/update/firmware_manifest.json")).items():
        print(f"{name}: {part.get('version')} ({part.get('file')})")
except Exception as exc:
    print("Firmware manifest: unreadable", exc.__class__.__name__)
try:
    print("USB Boxes in box.cfg:", len(re.findall(r"^\[mcu mcu_box", open(os.path.join(home, "printer_data/config/box.cfg")).read(), re.M)))
except OSError:
    print("USB Boxes in box.cfg: no box.cfg")
print("Kernel:", run("uname", "-rv"))
print("Auto-updates:", run("systemctl", "is-enabled", "tltg-optimized-auto-update.timer") or "off")
print("zram:", "on" if "zram" in open("/proc/swaps").read() else "off")
print("AI detection:", run("systemctl", "is-active", "algo_app.service") or "unknown")
print("THR fix backups:", "yes" if os.path.isdir(os.path.join(home, "printer_data/.tltg_thr_firmware_backups")) else "no")
try:
    import urllib.request
    q = "http://127.0.0.1:7125/printer/objects/query?print_stats=state&webhooks=state,state_message"
    s = json.load(urllib.request.urlopen(q, timeout=5))["result"]["status"]
    print("Klipper:", s["webhooks"]["state"], "/", s["print_stats"]["state"])
except Exception as exc:
    print("Klipper: no answer from Moonraker", exc.__class__.__name__)
PY
```

It prints the installed Valve Oil version, QIDI's firmware versions for every board, how many USB Boxes `box.cfg` lists, the kernel, whether automatic updates, zram, QIDI AI detection, and the toolhead firmware fix are on, and Klipper's state.

### Logs

- **`klippy.log`:** in Fluidd, open **Configuration**, switch the file list to **logs**, and download `klippy.log`; or copy `~/printer_data/logs/klippy.log` over SSH. Attach it right after the problem, before restarting Klipper again, since each restart starts a new log. If it's too big to attach, zip it.
- **Installer output:** copy everything the installer printed, from the command to the end. To get more detail, run it again with `--debug` added, for example `~/tltg-optimized-macros/install.sh --debug`.
- **Automatic update output:** `journalctl -u tltg-optimized-auto-update.service --since "2 days ago"`.
- **`moonraker.log`:** `~/printer_data/logs/moonraker.log`, for Fluidd or file upload problems.
- **The sliced file**, for print problems: attach the `.gcode` or `.gcode.3mf`, zipped.
