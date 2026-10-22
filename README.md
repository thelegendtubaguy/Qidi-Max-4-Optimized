![Tuba Makes](.github/images/tuba-makes-logo.png)

# Qidi Max 4 Optimized

Opinionated and Optimized Klipper macros and slicer machine GCode for the QIDI Max 4.

> [!NOTE]
> If you want to help support content like this, consider subscribing over on [YouTube](https://youtube.com/@TubaMakes)!

> [!CAUTION]
> I refuse to be responsible for your printer.  PLEASE watch prints start ensuring the printer doesn't do something horrible like gouge your bed and be ready to cut power at a moment's notice.

## tl;dr
1. SSH into your printer `qidi@<your printer's ip>`.
2. Run this on your printer:
```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)"
```
3. Follow the prompts
4. Use Orca and subscribe to the OrcaCloud bundle shared [here](https://cloud.orcaslicer.com/b/4c4b3b74c745).  If you're not using Orca >= 2.4.0, see [the section on slicer configs](#slicer-machine-gcode-updates).
5. Slice using the printer profile `Qidi X-Max 4 0.4 nozzle - TLTG Optimized GCode`
6. Optional: Make a copy and customize the machine profile to your liking.


### Installer Dry-Run
If you'd rather do a dry-run before committing to a full install, you can run this:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)" -- --dry-run
```

### Optional THR accelerometer firmware fix

On QIDI firmware `01.01.07.01`, the interactive installer asks early, before changing any configuration, whether to flash the THR toolhead board's LIS2DW FIFO bug fix. **The default is No**: press Enter to leave firmware unchanged. Answering yes flashes after the configuration install finishes. The installer checks the actual application and bootloader hashes; a board that already has the fix is verified without another reset or flash. **After flashing THR, rerun input shaper calibration before printing.** The installer clears the saved input shaper calibration from `printer.cfg`, so input shaping stays off until you recalibrate; the previous `printer.cfg` is kept with the THR recovery files. The installer does not run calibration.

Flashing requires an idle, ready printer with every heater target at zero. Keep printer power on until verification completes. The installer preserves stock recovery files under `~/printer_data/.tltg_thr_firmware_backups/`, flashes only THR, and verifies the complete application and unchanged bootloader before restoring services. If the bootloader is unsupported, THR firmware is left unchanged and previously active services are restored without a firmware blocker; the configuration install is kept. The installer saves a private read-only capture and identifies a shareable `report.json` to attach to a GitHub issue. Do not attach its flash binaries. See [THR-only operations](firmware/FLASHING.md) for admitted bootloader identities and recovery requirements.

`--yes` alone and automatic updates never authorize firmware programming. To opt in explicitly from the command line, use `~/tltg-optimized-macros/install.sh --flash-thr-fifo`; add `--dry-run` for a preview without serial access or service changes. Configuration restore and uninstall do not revert MCU firmware.

### Automatic Updates

The installer asks whether to enable hourly automatic optimized config updates before asking whether to restart Klipper. Auto-updates use a system-level systemd timer. Enabling auto-updates requires sudo once to install `/etc/systemd/system/tltg-optimized-auto-update.service` and `/etc/systemd/system/tltg-optimized-auto-update.timer`; the installer uses QIDI's public default sudo password (`qiditech`) unless the environment variable `TLTG_OPTIMIZED_SUDO_PASSWORD` is set, then prompts for a password if the initial sudo attempt fails.

If those systemd units already exist from a dev installer, a release install refreshes them to the current `~/tltg-optimized-macros` bundle, clears auto-update URL environment overrides, seeds the latest release checksum when GitHub is reachable, and re-enables/restarts the timer.

Each hourly run checks the latest GitHub release checksum, skips while the printer is printing or paused, and then runs the normal installer with preflight checks and auto-approval.

Disable auto-updates:

```bash
~/tltg-optimized-macros/auto-update.sh --disable-systemd
```

Run one auto-update check manually:

```bash
~/tltg-optimized-macros/auto-update.sh --run
```

### Moonraker 3MF metadata cache

Install and update patch recognized QIDI Moonraker source so unchanged 3MF files reuse their metadata instead of being re-extracted at every startup. This applies even when optional OS optimizations are skipped. Moonraker restarts when its file-manager patch changes; installation requires an idle printer.

The first restart rebuilds existing 3MF metadata once. Later scans still enumerate directories, but only new, changed, or invalidated archives need extraction. Changing the metadata extractor or object-processing policy invalidates the cache. This does not bypass print preparation or archive decompression needed by the printer itself.

Manual 3MF metadata rescans use the archive extractor and keep existing QIDI thumbnail files. A rescan joins extraction already pending for the same archive rather than starting another copy; failures report an error and preserve prior metadata. Ordinary G-code rescans are unchanged.

Unrecognized source is preserved and reported. Uninstall can restore the original source through its system-restoration prompt; files modified after installation are preserved.

### QIDI Box filaments in Fluidd

QIDI firmware `01.01.07.01` stores Box filaments with new IDs such as `QFA90`, colors as RGB values, and brands such as Bambu, HATCHBOX, Overture, and Polymaker through the filament itself. Its bundled Fluidd still expects the older numeric IDs: loaded slots show `?`, and filaments chosen in Fluidd are treated by the printer as QIDI PLA Basic.

Install and update patch QIDI's Fluidd, including when optional OS optimizations are skipped:

- Box slots show the filament, vendor, and color the printer is actually using. A slot set with an older numeric ID shows QIDI PLA Basic, because that is how `01.01.07.01` treats it; pick the filament again to fix it.
- The Vendor and Filament pickers match the touchscreen: choose a vendor, then one of its filaments. Changing the vendor switches to that vendor's filament of the same type when one exists.
- Colors chosen in Fluidd are saved the same way as on the touchscreen.

Older supported firmware keeps Fluidd's original pickers. Reload Fluidd in the browser after installing; a hard refresh may be needed if the browser cached the old page.

A Fluidd build the installer does not recognize is left unchanged. Uninstall can restore the original Fluidd through its system-restoration prompt; files modified after installation are preserved.

### Editing the QIDI filament list

On `01.01.07.01`, the touchscreen's Vendor and Filament lists come from QIDI's filament files. Install and update add a `qidi_filament_config` folder to Fluidd's configuration files that opens them, so you can add or adjust filaments from Fluidd:

- `filament-0.4.json` is the list for the 0.4 mm nozzle; the other files cover the other nozzle sizes. Right-click a file and choose Edit.
- To add a filament, copy an entry of the same material and give it a new name, a new unused `filament_id`, and the vendor to list it under. A new vendor name adds that vendor to the pickers.
- The file must stay valid JSON; a missing comma or bracket can break the touchscreen's filament list.
- Restart the printer after saving so the touchscreen and Box pick up the change, then reload Fluidd.

Firmware updates replace these files, so keep a copy of any entries you add. Files in this folder are QIDI's own files, not copies: they are not part of the installer's configuration backups, and deleting one in Fluidd deletes it from the printer. If `qidi_filament_config` already exists, the installer leaves it alone. Uninstall's system-restoration prompt removes the link but never your edits.

### QIDI Box temperature from Fluidd

Set a QIDI Box heater target from the `Heater Box1`/`Heater Box2` rows in Fluidd's temperature panel. The highest target allowed is the lowest Box temperature limit among the filaments loaded in that Box; an empty Box allows up to 65 °C, the Box's advertised maximum. If a loaded filament does not allow Box heating, the target field is locked; a Box that is already heating can still be set to `0`.

### Fluidd full display

Install and update turn on QIDI's **Enable Full Display** setting in Fluidd by default. It shows the bed mesh card on the Tune page and adds sensors without a target temperature, such as the chamber thermal protection and electronics sensors, to the temperature panel and chart. Turning it off in Fluidd's settings is remembered across updates.

### Helpful Klipper tools

After install and Klipper restart, the optimized macro set includes:

```gcode
TLTG_PROBE_ACCURACY_CENTER
TLTG_CORNER_BED_SCREW_CHECK
SCREWS_TILT_CALCULATE
TLTG_RESET_TOOL_MAPPINGS
```

`TLTG_PROBE_ACCURACY_CENTER [SAMPLES=20]` homes, moves to `X195 Y195 Z10`, and runs Klipper `PROBE_ACCURACY`.

`TLTG_CORNER_BED_SCREW_CHECK` homes, runs `Z_TILT_ADJUST`, and runs `SCREWS_TILT_CALCULATE`.

`TLTG_RESET_TOOL_MAPPINGS` restores QIDI Box tool-to-slot identity mappings while the printer is idle. It is rejected while printing or paused.

### Print-start bed mesh

Each optimized print start calibrates a fresh adaptive KAMP mesh by default. To reuse an existing Klipper bed-mesh profile for every optimized start, save its exact name from the Klipper console:

```gcode
SAVE_VARIABLE VARIABLE=tltg_start_bed_mesh_profile VALUE='"default"'
```

Restore fresh adaptive calibration by saving an empty value:

```gcode
SAVE_VARIABLE VARIABLE=tltg_start_bed_mesh_profile VALUE='""'
```

The setting applies to existing sliced files and requires no change to slicer gcode. The console reports whether start preparation is loading the named profile or calibrating a fresh adaptive mesh. A configured profile must already exist; Klipper stops print preparation if it cannot load the name.

### Minimum chamber temperature

With OrcaSlicer 2.4.2 or later, use the updated `orcaslicer_gcode/start.gcode` and set the filament profile's chamber **Target** and **Minimal** temperatures. For example, Target `60°C` and Minimal `50°C` allow leveling and printing once the chamber reaches `50°C`, while heating continues toward `60°C`. The initial tool's filament supplies the minimum; values above the target are capped at the target.

Minimal `0` keeps the existing target-minus-3°C wait. Older start G-code and QIDI Studio retain that behavior with updated macros; updated Orca start G-code also works with older optimized macros, which ignore the minimum and retain their existing wait. Both the start G-code and optimized macros must be updated to use the shorter wait.

The minimum also applies to the chamber stage of staggered heating. A lower minimum allows nozzle heating to begin while the chamber is still heating toward its target.

### Staggered print-start heating

Staggered heating is disabled by default. Enable bed, chamber, then nozzle warm-up with a 10-second dwell between active stages:

```gcode
SAVE_VARIABLE VARIABLE=tltg_staggered_start_heating VALUE=1
SAVE_VARIABLE VARIABLE=tltg_staggered_start_heating_dwell_seconds VALUE=10
```

Set the dwell to another non-negative number of seconds, or use `0` to retain ordered heating without fixed dwell time. To disable staggered heating:

```gcode
SAVE_VARIABLE VARIABLE=tltg_staggered_start_heating VALUE=0
```

You will need to slice files with the latest slicer gcode from this repo (or Orca cloud).

### End-of-print filament handling

The installer sets `tltg_keep_loaded_between_prints` to `1` if the setting does not already exist. That makes filament retention the default after installation.

- `1`: Keep the current QIDI Box filament loaded after a completed print.
- `0` or not set: Cut and unload the filament after a completed print.

To disable filament retention and use the stock-style cut-and-unload behavior:

```gcode
SAVE_VARIABLE VARIABLE=tltg_keep_loaded_between_prints VALUE=0
```

To turn filament retention back on:

```gcode
SAVE_VARIABLE VARIABLE=tltg_keep_loaded_between_prints VALUE=1
```

The installer preserves an existing setting during updates. The setting survives Klipper restarts, works with existing sliced files, and does not require any slicer G-code changes.

### Filament runout sensor

```gcode
TLTG_FILAMENT_SENSOR ENABLE=0
TLTG_FILAMENT_SENSOR ENABLE=1
```

`ENABLE=0` keeps toolhead filament-sensor events and external-spool runout status reporting active while suppressing automatic external-spool pausing. `ENABLE=1` restores automatic external-spool pausing. The setting resets enabled after a Klipper restart. QIDI Box runout handling remains enabled in both modes.

> [!WARNING]
> With `ENABLE=0`, ignore filament-runout warnings on the printer screen. Do not interact with those warnings; the print continues and the warning remains only as sensor-event status.

The console identifies the toolhead sensor trip and the active pause policy.

![Filament sensor console output](.github/images/tltg-filament-sensor-console.png)

### Slicer Machine GCode Updates

> [!TIP]
> If you're using Orca >= 2.4.0, use the OrcaCloud [shared bundle you can subscribe to](https://cloud.orcaslicer.com/b/4c4b3b74c745)!  It will let you get future updates in your slicer easily and you don't have to manually copy/paste anything!

You will need to manually copy the machine GCode to your slicer of choice to take advantage of the optimized path.  The stock print path remains in place for backwards compatibility, safety, and general user happiness :)

Use the pack that matches your slicer. The two packs are functionally aligned, but their placeholder syntax differs because of variable type differences.
   - OrcaSlicer: `orcaslicer_gcode/`
   - QIDI Studio: `qidistudio_gcode/`

## Uninstall

If `~/tltg-optimized-macros/` is still present on the printer:

```bash
~/tltg-optimized-macros/install.sh --uninstall --plain
```

You can also run uninstall by fetching the latest script directly from the web:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh)" -- --uninstall
```

## If something goes wrong

Read the installer output first. The installer stops before writing when firmware detection, preflight, printer state, or free-space checks fail.

Installer-created backup `.zip` files are stored under `/home/qidi/printer_data/` with `tltg-optimized-macros-before-optimize-...zip` and `tltg-optimized-macros-before-uninstall-...zip` labels.

You can restore interactively when SSH'd into the printer.

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

## Testing

See [TESTING](TESTING.md) to help validate releases.

## Development

For development documentation, see [DEVELOPMENT](DEVELOPMENT.md).

## License

Repository-authored content is licensed under [GPLv3](LICENSE). Third-party components and license texts are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
