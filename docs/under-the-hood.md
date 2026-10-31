# What the installer changes

[← Back to the README](../README.md)

For anyone who wants to know exactly what's touched on the printer. The rules behind every change:

- **Only recognized files are changed.** If a QIDI file doesn't match a version the installer knows, it's left alone and reported, and the feature that needed it is skipped.
- **Your changes win.** A setting you changed from QIDI's value is kept. A file you change after installing is kept and reported by uninstall.
- **Everything is backed up first.** See [Restore a backup](troubleshooting.md#restore-a-backup).
- **The printer must be idle** for any change that restarts Klipper or Moonraker.

## Klipper configuration

| What | Change |
|---|---|
| `printer.cfg` | Adds `[include tltg-optimized-macros/*.cfg]`, and changes recognized QIDI values for homing speed and retraction, Z-tilt and mesh travel speed, closed-loop homing timing, and a few others. |
| `config/tltg-optimized-macros/` | The optimized macros. QIDI's own macros in `klipper-macros-qd/` stay in place, so files sliced with stock G-code print as before. |
| QIDI's `RESUME`, `CUT_FILAMENT_1`, `M109.0`, `homing_override`, `_km_apply_print_offset`, and external spool sensor sections | Removed from QIDI's files and replaced by optimized versions. |
| `saved_variables.cfg` | Adds missing defaults for [this project's settings](settings.md) and repairs missing QIDI Box tool mappings. Existing values are kept. |
| `config/qidi_filament_config` | A link to QIDI's filament files, for [editing them in Fluidd](qidi-box.md#editing-qidis-filament-list). Firmware `01.01.07.01` only. |

## Klipper and Moonraker source

| What | Change | Restarts |
|---|---|---|
| `klippy/extras/tltg_*.py` | Added modules for the Box link monitor, Box processor temperature, Box heater refresh, background mesh save, faster `SAVE_VARIABLE`, Box load/unload speed, Box eject, unknown Box filaments, stuck Box loads, Box slot jogs, [Spoolman spools for each slot](spoolman.md), the [RS-485 Box monitor](qidi-box.md#rs-485-boxes), and the load-cell check. | Klipper |
| `klippy/extras/homing.py` | Replaced with this project's version of QIDI's homing code, for the faster homing. QIDI's closed-loop homing checks stay in place. | Klipper |
| `klippy/extras/print_stats_manager.py` | Keeps the [real shutdown reason](fixes.md#the-real-error-instead-of-mcu-shutdown) on screen. | Klipper, once |
| `klippy/extras/box_config.py` | Lets Fluidd set Box heater targets, capped at 65 °C. | Klipper, once |
| Moonraker `file_manager.py` and `metadata.py` | The [3MF metadata cache and plate fix](fixes.md#multi-plate-3mf-files). | Moonraker, when the patch changes |
| Moonraker `spoolman.py` | Charges the new spool from the start of each filament change, keeps the Spoolman connection from dropping, and passes a spool picked in Fluidd to the [loaded slot](spoolman.md). | Moonraker, once |

## Fluidd and the web server

| What | Change |
|---|---|
| `~/tltg-fluidd` | This project's [Fluidd build](fluidd.md). Updates replace it whole. |
| `~/fluidd` | QIDI's Fluidd, left untouched as the fallback. |
| Fluidd's nginx configuration | Serves `~/tltg-fluidd` instead of `~/fluidd`, and adds a `/tltg-screen/` route for the Printer screen card. |
| `tltg-remote-screen` service | Streams the touchscreen to the [Printer screen](fluidd.md#printer-screen) card, sending a new image only when the screen changes. It only listens on the printer itself, and Moonraker checks every connection. |
| `~/printer_data/moonraker.asvc` | Adds `qidi-client`, so Fluidd can [restart the touchscreen app](fluidd.md#restart-the-touchscreen-app). Moonraker restarts once. |

## System

| What | Change |
|---|---|
| `~/tltg-optimized-macros/` | The installer, `restore.sh`, `auto-update.sh`, and `box-firmware.sh`. |
| `/etc/systemd/system/tltg-optimized-auto-update.{service,timer}` | Only if you turn on [automatic updates](install.md#automatic-updates). |
| `~/printer_data/logs/tltg_box485.log`, `tltg_box485_report.json`, and `~/printer_data/.tltg_box485_salt` | Written only when [RS-485 Box hardware](qidi-box.md#rs-485-boxes) is detected or `TLTG_RS_BOX_REPORT` runs. The salt keeps the codes that replace hardware ids the same on this printer. |
| DNS, package sources, `xl2tpd`, `bluetooth`, `algo_app`, `rockchip.service`, touchscreen images | Only if you choose the [OS optimizations](install.md#os-optimizations). |

## What uninstall does

Uninstall removes the optimized macros and added modules, restores every QIDI file above, points the web server back at QIDI's Fluidd, removes `~/tltg-fluidd`, the Printer screen service, and the filament folder link, and restores Moonraker's service list. It asks before undoing the OS optimizations. Files you changed after installing are kept and listed.

Firmware is never changed by install, update, or uninstall unless you [ask for it](firmware.md).
