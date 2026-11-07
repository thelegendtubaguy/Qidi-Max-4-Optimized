## 1. Before the printer arrives

- [x] 1.1 Record the operator reports from issue 190 in the Plus 5 observations.
- [x] 1.2 Add `installer/stock/qidi-plus5-defaults/firmwares/01.01.02.01/` from `Qidi-Plus5-Defaults` `25001402`, and check it against the payload hashes.
- [x] 1.3 Compare Plus 5 and Max 4 `box_extras.so` and `box_stepper.so` in the vendor harness, covering every method a package Box module wraps or calls. Record the result in the QIDI Box observations. Only `tltg_box_feed_motion` depended on the changed code; it now stays inactive on unlisted `box_stepper.so` builds.
- [x] 1.4 Classify every guarded patch, source patch, and extra module for the Plus 5: applies unchanged, needs a Plus 5 variant, or Max 4-only. Draft the `01.01.02.01` variants.
- [x] 1.5 Draft `installer/klipper/printers/plus5/` (`homing.cfg`, `nozzle_motion.cfg`, `printer_profile.cfg`) from QIDI's Plus 5 macros, with stock currents and dwells.
- [x] 1.6 Split the start-print contract per printer (`start-print-plus5.path.json`), and draft the Plus 5 OrcaSlicer and QIDI Studio packs in `orcaslicer_gcode/plus5/` and `qidistudio_gcode/plus5/` from QIDI's Plus 5 profiles.
- [ ] 1.7 Add screen rotation and touch mapping to the Printer screen service, with the direction as a per-printer setting.
- [x] 1.8 Extend the lifecycle and patch matrix tests to run against the Plus 5 snapshot.

## 2. On the Plus 5, read-only

- [ ] 2.1 Run the collection script from issue 190 on the stock printer.
- [ ] 2.2 Capture the boot image and `/proc/kallsyms`, and compare the kernel with the `#4` build the zram modules target.
- [ ] 2.3 Capture `/dev/fb0` on a known screen and read `event0`'s axis ranges; record the rotation direction and touch orientation.
- [ ] 2.4 Diff the live `printer.cfg` against stock `01.01.02.01`.
- [ ] 2.5 List Klipper objects and record fan, chamber, and sensor names.
- [ ] 2.6 Time stock `G28` repeatedly and keep the `klippy.log` lines.
- [ ] 2.7 Watch stock cut, wipe, chute, and park moves for clearances, and check the toolhead geometry the cold cut depends on.
- [ ] 2.8 Run `WEIGHTING_DEBUG_QUERY` and `PROBE_ACCURACY`.
- [ ] 2.9 Measure idle and printing main-thread load and memory, as was done on the Max 4.
- [ ] 2.10 Take photos of the mainboard and THR board revisions.
- [ ] 2.11 Check whether `BEEP` beeps during QIDI's stock homing, whether the Plus 5 has a polar cooler on `PA14`, and the bed screws' thread.

## 3. On the Plus 5, with services stopped

- [ ] 3.1 Snapshot the THR bootloader and classify it against the admitted builds.
- [ ] 3.2 If a Box is attached, snapshot its bootloader, then load, unload, and change tools with stock firmware.

## 4. Admission and validation

- [ ] 4.1 Add the `plus5` printer to `installer/package.yaml` with its variants, macro folder, and stock snapshot. Update `installer/supported_upgrade_sources.yaml`.
- [ ] 4.2 Run the installer core tests, the known-versions check, the config formatter, the slicer macro check, the start-print contract check, OpenSpec validation, and the bundle smoke test.
- [ ] 4.3 Install on the Plus 5. Confirm admission, guarded patches, full, XY, and single-axis homing, print start through each slicer pack, cut, wipe, chute, rear-bed scrape, end print, and the screen card.
- [ ] 4.4 Exercise update, uninstall, restore, and recovery after a QIDI firmware update on the Plus 5.
- [ ] 4.5 Decide zram and the THR fix for the Plus 5 from 2.2 and 3.1, and record the decision.
- [ ] 4.6 Update the README supported printers, `docs/`, the version, and `CHANGELOG.md`.
