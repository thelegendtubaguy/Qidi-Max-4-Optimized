# Changelog

## 26.10.29.1
- Fluidd is now this project's build of current Fluidd, based on Fluidd 1.37.7, instead of QIDI's Fluidd 1.30.5, which QIDI no longer updates. It keeps QIDI's Max 4 additions and the Box, temperature, and screen features from earlier versions, and adds the rest of upstream Fluidd's improvements since 1.30.5. Install and update put it in `~/tltg-fluidd` and point the printer's web server at it, even when optional OS optimizations are skipped. QIDI's `~/fluidd` is left untouched, and the earlier patches to it are undone. Your settings, macros, and dashboard layout carry over. After installing, reload any Fluidd tab that was already open; the page footer then reads `fluidd: v1.37.7-tltg-` followed by a commit ID. From then on, open Fluidd tabs switch to a newly installed version by themselves, without a hard refresh. Uninstall switches back to QIDI's Fluidd and removes `~/tltg-fluidd`. The source is at [thelegendtubaguy/fluidd](https://github.com/thelegendtubaguy/fluidd).
- Filaments added to `filament-0.4.json` in the `qidi_filament_config` folder now appear in the QIDI Box card's Vendor and Filament lists after the printer restarts, without reloading Fluidd. If the file has a JSON error, the card says so instead of showing empty lists.
- The **QidiBox** preview is now Fluidd's **QIDI Box** card. **Box settings** on the card has QIDI's detection on startup, detection on insertion, and automatic reload switches, along with the load and unload motion settings.
- Everything QIDI's **Enable Full Display** setting hid, such as the bed mesh card on the Tune page and sensors without a target temperature, is now always shown.
- Sliced `.gcode.3mf` files can now be uploaded from Fluidd, and its G-code preview opens them.
- Sliced 3MF files exported from a plate other than plate 1 now print when started from Fluidd, reprinted from history, or started by the job queue. Before, they failed with `3MF processing error: [Errno 2] No such file or directory: '/home/qidi/printer_data/.temp/shadow_native_plate_1.gcode'`, because the printer assumed plate 1 unless the slicer's upload-and-print named the plate. Install and update patch QIDI's Moonraker so a print started without a plate number uses the plate the file was sliced on. Moonraker restarts once when the patch is applied.
- Uninstall now always undoes the changes every install makes to QIDI's own files: Fluidd, the Printer screen service and web server route, the Moonraker and Klipper source fixes, and the filament configuration link. Before, answering no to the system-restoration prompt left all of them in place. The prompt, and `--keep-system-optimizations`, now cover only the optional OS optimizations it names: DNS, APT sources, disabled services, Rockchip root sync, and the QIDIClient GIFs. Files modified after installation are still preserved.

## 26.10.28.4
- Fixed the Box MCU link monitor never recording the Box's reset reason. It asked before Klipper had connected to the Box, so it logged `firmware has no reset_reason_get` for every MCU, and when it did ask, the Box's answer went to `klippy.log` instead of `tltg_box_link.log`. The monitor now asks once Klipper is connected and writes the answer as a `reset-reason mcu_boxN:` line. After a Box disconnect, the first such line when Klipper reconnects shows why the Box restarted. Turning the monitor on while Klipper is running now records the reset reason right away. `mcu` and `THR` still report `firmware has no reset_reason_get`, because their firmware doesn't have the command.

## 26.10.28.3
- Fluidd now switches to the installed version by itself. Before, after an install or update, browsers kept showing the previous Fluidd, without new cards such as **QidiBox**, until you did a hard refresh, closed every Fluidd tab, or clicked **Reload** on Fluidd's update notice. A normal reload wasn't enough. Now, when you open or reload Fluidd after installing, it reloads itself once a moment later with the new version, and Fluidd tabs left open also reload once when the browser picks up the update. Unsaved changes in Fluidd's config editor are lost if that reload happens while you're editing. Printing isn't affected. Uninstall restores QIDI's original service worker, which goes back to the **Reload** notice.

## 26.10.28.2
- The installer can now repair a printer whose Klipper is stopped with an error, such as `Section 'tltg_probe_test' is not a valid config section`. Before, it refused with `Klipper saved-variable runtime is not ready.`, because it saved settings through Klipper before installing any files, so the install that would fix Klipper could never run. When Klipper is stopped with an error, the installer now installs its files first, restarts Klipper, and then saves settings. If Klipper still doesn't start, the files stay installed and the installer tells you to fix the error shown in Fluidd and run it again.

## 26.10.28.1
- Fixed Klipper failing to start with `Section 'tltg_probe_test' is not a valid config section` after some installs and updates. The optimized configuration always loads the helper behind `TLTG_TEST_PROBE`, but the helper itself was installed with the OS optimizations, after the configuration, so an update that skipped or stopped partway through those changes left Klipper without it. The helper is now installed with the optimized configuration on every install and update, and removed with it on uninstall. If your printer shows this error, run the installer again.

## 26.10.23.2
- Added a **QidiBox** card to Fluidd's dashboard as a preview of a redesigned Box card. It shows every Box's slots and the external spool at once, with each spool's color, the tools mapped to it, and which slot is loaded; which slots back each other up for automatic reload; each Box's humidity, temperature, and heater target; a filament path from the slot inlet through the hub to the toolhead that follows the sensors; and a tool mapping diagram you can edit while the printer is idle. Select a slot to load, unload, eject, read its RFID tag, or edit its filament. **Box settings** opens the same settings as the Box card's **Config**. The existing Box card is unchanged, so you can use either. Existing dashboards get the card at the bottom of the first column. After installing, close every Fluidd tab and open Fluidd again. Feedback on the new layout is welcome in GitHub issues.
- Added a **Printer screen** card to Fluidd's dashboard that shows the printer's touchscreen live. It starts collapsed and does nothing until you expand it. The screen opens view only; choose **View only** in the card header and confirm to press the real touchscreen by clicking, tapping, or dragging on the image. **Full screen** fills your browser or phone. Only devices that can already use Fluidd can see it. Install and update add a small `tltg-remote-screen` service and a `/tltg-screen/` route to QIDI's nginx configuration for Fluidd, even when optional OS optimizations are skipped, and uninstall can remove them. Existing dashboards get the card at the bottom of the first column. After installing, close every Fluidd tab and open Fluidd again.
- Added `TLTG_TEST_PROBE CONFIRM=1`, a guided check that the nozzle load cell responds to light pressure, with no motion, homing, heating, or calibration changes. Follow the console prompts to leave the nozzle alone, press lightly, and let go; the result says whether the readings look correct and why. It does not verify the homing trigger. See the README for details.
- Added an optional QIDI Box MCU link monitor to help diagnose `Lost communication with MCU 'mcu_boxN'` reports. It is off by default and stays inert until you enable it with `SAVE_VARIABLE VARIABLE=tltg_box_link_monitor VALUE=1`. While enabled it records Box MCU serial counters and their changes, box heater and print context, the reset reason each Box MCU reports when it connects, and the first `Got EOF when reading from device`, `Timeout with MCU`, or `shutdown:` line from `klippy.log`, plus the kernel USB lines at that moment. Output goes to `printer_data/logs/tltg_box_link.log`, outside `klippy.log` so it survives log rotation, capped at 2 MB with one rotation. Setting the variable back to `0` stops recording without a restart. Nothing else about printing changes while it is off. Uninstall removes the module and leaves a modified file in place.
- When Klipper stops a print with an error, such as a heater or fan fault or a lost QIDI Box connection, the screen, Fluidd, and slicers now show that reason instead of only `MCU shutdown`. QIDI's print status module tried to switch the Z motor drivers back from print mode after Klipper had shut down, which Klipper refused, and it repeated that until Klipper crashed and restarted into a bare MCU shutdown. Install and update now patch QIDI's `print_stats_manager.py` to skip that reset after a shutdown, and Klipper restarts once. The printer still stops on the error, and `FIRMWARE_RESTART` recovers as before. This applies even when optional OS optimizations are skipped. Unrecognized versions of the file are left alone, and uninstall can restore the original.
- You can now tune how fast the QIDI Box loads and unloads filament. Open the Box card in Fluidd, choose **Config**, and use the new **Load/unload motion** section, or use `TLTG_BOX_MOTION` in the console. You can set how far and how fast the Box pushes filament before it slows down, how fast it creeps up to the toolhead sensor, how fast it pulls filament back, and how far the extruder retracts before the Box takes over. Any setting can also be changed for a single slot. Installing or updating switches to a faster profile, unless you've already changed these settings, in which case yours are kept. Clear a field, or run `TLTG_BOX_MOTION RESET=1`, to go back to QIDI's original motion. After installing, close every Fluidd tab and open Fluidd again.
- Requests to save a zero print Z offset now emit a `TLTG_Z_OFFSET_ZERO_REQUEST` warning in Fluidd's console and Klipper's log, including the previous saved offset, runtime offset, print/file state, QIDI status, captured offset, and command parameters. Screen and Fluidd adjustments and all variable saves remain unchanged, including intentional zero saves.
- Fixed cancelling a print during its start sequence wiping your saved Z offset to `0`. Start G-code clears the Z offset while homing, leveling, and meshing, then puts it back right before printing, but cancelling before that point saved the cleared `0` as your offset. A print that ends before the offset is put back now leaves the saved offset alone and shows `Z offset not saved` in the console. Prints that end after printing starts still save the offset, including any adjustments you made on the touchscreen.
- On firmware `01.01.07.01`, the Fluidd Box card's Load, Unload, and Eject buttons and RFID read work again. QIDI's Fluidd still sent commands the firmware removed, so the buttons did nothing. Unload is now available when the selected slot is loaded; before, it stayed greyed out. Older firmware keeps the original commands.
- Ejecting a QIDI Box slot no longer homes and parks the toolhead when only the Box needs to move, such as when nothing is fed past the Box hub. QIDI's eject parked over the waste chute before and after the Box pulled the filament back, which meant homing X and Y first if the printer wasn't homed. An eject that first heats and unloads filament still parks as before.
- Fluidd's Box print dialog now lets several filaments in a file use the same Box slot. Before, choosing a slot already used by another filament swapped that filament back to `?`, so a file with more filaments of a type than loaded slots of that type could never start. Slots are still matched automatically, one filament per slot, while unused slots of the right type remain; choose a slot by hand for any filament left at `?`. After installing, close every Fluidd tab and open Fluidd again.
- Fixed browsers that had opened Fluidd before an install continuing to show QIDI's unpatched Box card, with `?` slots, after a normal reload. The installer now also updates Fluidd's service worker, so browsers fetch the patched Fluidd. After installing, close every Fluidd tab and open Fluidd again. Uninstall restores the original service worker along with the Fluidd bundle.
- Thanks to [Assur92's qidi-max4-fluidd-box-fix](https://github.com/Assur92/qidi-max4-fluidd-box-fix) for identifying the Box commands, the missing Unload state, and the service worker cache.

## 26.10.23.1
- On the second Max 4 THR bootloader build, the optional FIFO fix now recovers from a failed transfer by itself instead of leaving the toolhead board for manual recovery. A short interruption resumes and finishes the fix. Otherwise the installer puts QIDI's stock THR firmware back, checks it, restarts your services, keeps your input shaper calibration, and tells you the fix was not applied, with no firmware blocker. A power loss during the few seconds of programming is still not recoverable, so keep the printer powered until the installer finishes. The first bootloader build is unchanged.

## 26.10.22.1
- An unsupported THR bootloader no longer turns the optional FIFO fix into a failed firmware operation. The installer keeps the configuration install, leaves THR firmware unchanged, restores previously active services, and leaves no firmware blocker after readiness is confirmed. It saves a private read-only capture and asks for only its shareable `report.json` in a GitHub issue, not the flash binaries.
- The optional THR FIFO fix now supports the second validated Max 4 bootloader build. Exact bootloader readback selects its transfer profile, including its different identity reply and final-packet padding; the first build's transfer behavior is unchanged.
- Documented restoring the stock THR application from retained firmware backups. Verification can compare the bootloader with the pre-transfer backup using `--original-backup-dir`; the installer always checks that it is unchanged.

## 26.10.21.2
- You can now set QIDI Box heater temperatures from Fluidd's temperature panel. Before, QIDI's Fluidd only accepted `0`. The highest temperature you can set is 65 °C, the same as on the touchscreen.  Reload Fluidd in the browser after installing.
- Fluidd now checks the filament in every slot of a Box before allowing heating, not just the first slot. If any loaded filament shouldn't be heated in the Box, such as PLA or TPU, the Box temperature field is locked instead of showing `Max 0`. You can still turn off a Box that is already heating.
- Fluidd's **Enable Full Display** setting is now on by default. It shows the bed mesh card on the Tune page and adds sensors without a target temperature, such as the chamber thermal protection and electronics sensors, to the temperature panel and chart. If you already turned it off in Fluidd's settings, it stays off. Reload Fluidd in the browser after installing.
- Removed the `TLTG_SET_BOX_TEMP` macro. Use Fluidd's temperature panel instead.
- On firmware `01.01.07.01`, the installer can now fix a bug in QIDI's toolhead board (THR) firmware that affects how it reads the accelerometer used for input shaper calibration. It is optional and off by default. The installer asks at the start, before changing anything, and you can just press Enter to skip it. If you say yes, the board is flashed after the rest of the install finishes; the printer must be idle with all heaters off. You can also opt in with `--flash-thr-fifo`. `--yes` and automatic updates never flash firmware, and the installer asks again on each run.
- **After flashing, rerun input shaper calibration before printing.** The installer turns input shaping off by clearing the old calibration from `printer.cfg`, since it was measured with the buggy firmware. A copy of the old `printer.cfg` is kept with the firmware backups. A board that already has the fix is left alone and keeps its calibration.
- Flashing only changes the toolhead board and keeps QIDI's version numbers. Before flashing, the installer saves a backup of the original firmware and afterward checks that the board holds exactly the expected firmware. If something goes wrong, your config install is kept, and the installer refuses to run again until the board is recovered using the included recovery instructions. Uninstall and config restore don't undo the firmware change.
- THR firmware operations wait up to two minutes for Klipper to become ready before stopping services. Active or paused prints and nonzero heater targets still fail admission immediately.

## 26.10.21.1
- On firmware `01.01.07.01`, install and update add a `qidi_filament_config` folder to Fluidd's configuration files, including when optional OS optimizations are skipped. It opens the touchscreen's filament list (`filament-0.4.json` and the other nozzle sizes) so entries can be added or edited from Fluidd; restart the printer after saving so the touchscreen and Box pick up the change. Firmware updates replace these files and discard custom entries.
- The folder is a link to QIDI's own files and is not included in installer configuration backups. An existing `qidi_filament_config` entry is left unchanged, and uninstall's system-restoration prompt removes only the installer's link.

## 26.10.20.2
- On firmware `01.01.07.01`, Fluidd's QIDI Box card now shows the filament, vendor, and color the printer is actually using for each slot. That firmware treats filaments chosen with the older numeric IDs, including those set in Fluidd before this release, as QIDI PLA Basic with its temperatures; such slots now show QIDI PLA Basic so they can be corrected.
- Fluidd's Box Vendor and Filament pickers now match the touchscreen on `01.01.07.01`: they list QIDI, Generic, Bambu, HATCHBOX, Overture, and Polymaker filaments from the firmware's filament list and save them the way the touchscreen does. Changing the vendor selects that vendor's filament of the same type when one exists, and colors are saved in the touchscreen's format. Older firmware keeps Fluidd's original pickers.
- Updates replace the `26.10.20.1` Fluidd patch in place; uninstall still restores the original Fluidd file. Reload Fluidd in the browser after installing.

## 26.10.20.1
- Fixed QIDI Box slots in Fluidd showing `?` and an empty spool on firmware `01.01.07.01`. That firmware saves filaments with new IDs such as `QFA90` and colors as RGB values, which QIDI's bundled Fluidd could not read. Install and update now patch the recognized Fluidd build so Box slots show the filament name and color, including when optional OS optimizations are skipped. Slots set before the firmware update display as before, and Fluidd's filament and color pickers are unchanged. Reload Fluidd in the browser after installing.
- Unrecognized Fluidd builds are left unchanged without blocking other install steps. Uninstall can restore the original Fluidd file; files modified after installation are preserved.

## 26.10.19.2
- Optimized chute wipes now release waste with their own motion instead of QIDI's `CLEAR_FLUSH`, which QIDI's `01.01.07.01` tool-change flow no longer uses. After each wipe the toolhead still leaves the chute and re-enters it so the waste drops, now with the optimized trash approach speed and with motion settings restored afterward. Wipe patterns, cleanup stages, and temperature gates are unchanged, and QIDI's own Box tool-change cleanup is untouched.
- Fixed a double filament cut on `01.01.07.01`: `26.10.19.1` let QIDI's tool-change flow cut only when the slicer passed a parameter that the published OrcaSlicer and QIDI Studio packs do not send, so both cuts ran. The macros now detect a print-time filament change on their own, so the published slicer packs cut once with no slicer update.
- On `01.01.07.01`, filament changes no longer send the toolhead to the chute before QIDI's tool-change flow cuts. The toolhead goes from the print straight forward to the cutter line, into the cutter along X, and then to the chute once. Older firmware keeps cutting with the optimized cut and then moving to the chute.

## 26.10.19.1
- Added support for QIDI firmware `01.01.07.01`, including its stock configuration snapshot, guarded configuration targets, and the unchanged optimized homing payload. Firmware `01.01.06.03` through `01.01.06.05` remain supported.
- Optimized macros and installer QIDI Box checks now recognize Boxes managed by the `01.01.07.01` flow controller, including RS-485 Boxes, as well as USB Boxes configured through `box.cfg`. Printers without an attached Box keep their non-Box paths.
- Adopted QIDI's `01.01.07.01` filament-cut sequence: the extruder motor is released and allowed to settle before a faster cutter strike, and the 4 mm retraction follows the cut. The stock 2-second dwell after leaving the cutter remains removed, and it is now also removed from QIDI's own cut macro used by `01.01.07.01` tool changes and stock print-start and unload paths on all supported firmware.
- On `01.01.07.01`, OrcaSlicer and QIDI Studio filament changes let QIDI's tool-change flow perform the single cut, unload, and load. The same slicer G-code still cuts and unloads on older firmware and with older installed macros.
- On `01.01.07.01`, end-of-print and manual QIDI Box unloads use QIDI's `UNLOAD_FILAMENT`, so filament is cut and returned to the Box; older firmware keeps the existing unload sequence.
- On `01.01.07.01`, Box resume and external-spool resume with automatic runout pausing enabled use QIDI's `TRY_RESUME_PRINT`. `TLTG_FILAMENT_SENSOR ENABLE=0` still resumes external-spool prints without a filament check; older firmware keeps its existing filament check.

## 26.09.15.1
- Fixed installer QIDI Box tool-slot string quoting so missing mappings and approved mapping corrections save without Klipper literal-parsing errors, including when Box enablement is declined.
- Fixed manual 3MF metadata rescans to use the archive extractor without deleting QIDI thumbnail files. Rescans join pending extraction instead of duplicating it; failures preserve prior metadata and return an error. The 3MF rescan path rejects escaped, reserved, or missing archives; ordinary G-code rescanning remains unchanged.
- Added a guarded Moonraker file-manager patch to normal install and update, including when optional OS optimizations are skipped. Unchanged 3MF files reuse cached metadata instead of re-extracting at every startup or filesystem notification; file size, modification time, extractor changes, and object-processing policy invalidate the cache.
- Unified 3MF and G-code metadata queue processing, fixed a cached-request loop that could hang Moonraker, and removed repeated whole-queue copies. Skipped extraction leaves cached last-printed fields and thumbnails intact.
- Retained byte-for-byte source backups, checked Moonraker restarts, and preserved modified files during reconciliation and uninstall. The first restart rebuilds unstamped 3MF metadata once; directory enumeration and processing of new or changed archives still occur.

## 26.09.09.1
- Replaced per-version upgrade metadata with one validated list of allowed patch targets and source hashes. Supported historical package versions remain explicitly listed and can upgrade directly.
- Unified configuration change planning for install, uninstall, and restore. The installer rejects files changed since planning, requires an idle printer before restore, and rolls back interrupted, uncommitted writes without replacing saved-variable files.
- Kept host optimizations in the installer flow and limited recovery-state growth across repeated checks. Recovery state retains the policy, original restoration copies, latest outcomes, and evidence needed for Rockchip recovery. Host restore preserves user-modified state.
- Moved host service and mount simulation into test fixtures. Plain and Rich output share installer summaries; Python handles command aliases, help, version reporting, and argument validation.
- Fixed a `NameError` during idle QIDI Box topology reconciliation so automatic-update checks can initialize missing tool-slot mappings after the Box count changes while preserving custom mappings.
- Saved installer defaults through Klipper's `SAVE_VARIABLE` command via Moonraker instead of replacing a stale `saved_variables.cfg` snapshot. Updates and already-current enrolled auto-update checks repair only missing defaults; existing retention values and non-empty custom QIDI Box tool-slot mappings stay unchanged.
- Blocked further installer or updater work when saved-variable verification fails after a source-patch restart. The expected values remain recorded until Klipper confirms them; dry-runs preserve the record and successful uninstall removes it. Moonraker does not support compare-and-set, so a concurrent update after the final live eligibility check can still win.
- Reduced the X and Y first-pass homing speed from 100 mm/s to 65 mm/s and the homing retraction speed from 1,000 mm/s to 500 mm/s; retained the existing 55 mm/s second pass.
- Fresh QIDI Box and external-spool print-start cleanup preserves every existing cooldown wipe while using the stock mixed-speed pre-scrape pattern. After the cooled rear-bed rectangle and three-circle scrape, the nozzle returns safely to the chute for four 200 mm/s finishing cycles and waste release before leveling.
- Retained-filament starts, non-start purge cleanup, unload cleanup, and staged end cleanup use four back-and-forth finishing passes at 200 mm/s. Manual loading, vendor commands, purge quantities, temperature gates, and slicer filament-change wiping remain unchanged.
- Added OrcaSlicer 2.4.2+ filament-profile minimum chamber temperature support so leveling and printing can begin at the minimum while heating continues toward the target, including staggered startup heating.
- Preserved existing chamber waits for zero or omitted minimums, QIDI Studio, and independent slicer-profile or optimized-macro updates.
- Exposed AP-board SoC, toolhead MCU, and mainboard MCU temperatures to Moonraker and Fluidd.

## 26.08.29.1
- Restored the stock QIDI Y395–Y397 rear-bed nozzle scrape footprint after the cable-chain orientation traverse.
- Prevented intentional end-of-print QIDI Box unloading from triggering a filament-runout pause before heater shutdown, bed lowering, nozzle wiping, and final print cleanup.

## 26.08.09.2
- Added the persistent `tltg_keep_loaded_between_prints` setting for end-of-print QIDI Box filament handling. Value `1` retains filament; `0` or a missing setting cuts and unloads it.
- The installer sets the preference to `1` when it is missing and preserves the user's existing value during updates.
- Added optional bed, chamber, then nozzle startup heating controlled by `tltg_staggered_start_heating`, with a configurable inter-stage dwell.
- Preserved no-argument `OPTIMIZED_PRINT_START_HOME` compatibility while updated slicer starts pass explicit heater targets.

## 26.08.09.1
- Added the persistent `tltg_start_bed_mesh_profile` setting so print start can load a named Klipper bed-mesh profile instead of calibrating a new mesh.
- Kept fresh adaptive KAMP calibration as the default when the setting is missing or empty. A configured profile must exist or Klipper stops print preparation.

## 26.08.06.2
- Reinstall enrolled optimized configuration automatically after QIDI firmware cleanup removes config-local installer state, while keeping unenrolled and disabled update checks non-mutating.
- Tuned hotend-fan tachometer polling to 0.75 ms across supported firmware, retaining margin for the measured 13,553 RPM maximum while reducing THR polling from firmware 01.01.06.05.

## 26.08.06.1
- Prevented the articulated cable-chain mount from striking the rear enclosure by orienting it with a full-width X traverse before rear-bed scraping and moving the scrape range to Y392–Y395.
- Increased travel to the randomized Z-home point to 750 mm/s and widened independent X/Y randomization to ±10 mm.

## 26.08.05.1
- Reset QIDI Box tool-to-slot mappings to identity after successful prints while preserving touchscreen and runout mappings during active or interrupted prints, with missing-mapping repair and an idle-only Fluidd/console reset macro.
- Added GPLv3 project licensing and bundled `LICENSE`, `THIRD_PARTY_NOTICES.md`, and component license texts under `LICENSES/`.

## 26.07.28.1
- Added guarded support for both known QIDI firmware `01.01.06.04` `homing.py` variants while preserving each variant's endstop synchronization behavior.
- Included live and accepted source hashes in unsupported managed-source drift errors.

## 26.07.03.2
- Fixed `26.07.03.1` release tooling so the publish workflow can compare the previous package version without requiring the old manifest to match the current schema.

## 26.07.03.1
- Patched Moonraker `.gcode.3mf` plate metadata extraction so plate-indexed G-code, JSON, and thumbnails resolve from `Metadata/slice_info.config`.
- Moved the front prime line ahead of first-layer object bounds when bed room exists, with the fixed front-center line retained as fallback.

## 26.06.15.1
- Tightened interactive installer prompts to accept explicit `Y/YES` or `N/NO` and re-prompt on invalid input.
- Prompted for system optimization policy again during interactive reinstall while keeping stored policy reuse for noninteractive installs and auto-update.

## 26.06.13.1
- Added dual QIDI Box tool-slot mapping support and runtime reconciliation when recorded box counts change.

## 26.06.11.1
- Added installer support for QIDI Max 4 firmware `01.01.06.04` alongside the existing `01.01.06.03` baseline.
- Added firmware-scoped stock baselines and guarded installer patch handling for supported firmware versions.

## 26.06.04.1
- Preserved the active print Z offset across startup reset, KAMP mesh save, and offset reapply.
- Kept retained-filament startup waiting at the purge chute while bed and chamber reach target temperature.
- Tracked retained QIDI Box filament from `slot_sync` so auto-runout reloads can be reused when the next print selects the reloaded slot.
- Suppressed disabled-timelapse console noise by setting stock `TIMELAPSE_TAKE_FRAME` verbose output off during install.
- Fixed QIDI Studio end G-code compatibility by avoiding unsupported indexed completion-air-filtration placeholders.
- Stopped SysV-backed services explicitly after system optimization disablement so `xl2tpd` does not remain active after install.

## 26.05.27.1
- Removed hardcoded shaper algo for x and y

## 26.05.21.1
- Fixed legacy manual install reset when stock `config/KAMP` is a symlink

## 26.05.19.1
- Removed the older QIDI Max 4 firmware baseline from installer support
- Added system optimizations (DNS, APT, qidiclient, algo_app)

## 26.05.04.1
- Added probe accuracy and screw-tilt helper macros
- Added `TLTG_SET_BOX_TEMP` macro to be able to set the box temp from fluidd
- Installer hardening
- Optimized nozzle cleaning
- Clean nozzle post print
- Finalized slicer gcode contract
