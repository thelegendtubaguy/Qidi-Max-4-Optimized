## 1. Diagnosis

- [x] 1.1 Recover the Box reset-reason handler, the flag order, and that flags are never cleared; confirm on the test printer that a cold power-on reads `PowerOn` and `FIRMWARE_RESTART` reads `Software`.
- [x] 1.2 Identify the `0483:5740` startup stage and the double enumeration it causes after every Box start.
- [x] 1.3 Calibrate power loss and link loss on the daisy-chained test Boxes.
- [x] 1.4 Search the Box firmware for stall sources and recover the update path.
- [x] 1.5 Capture a print-end drop with serial history and attribute it to the heater `max_duration` expiry during a host stall.
- [x] 1.6 Confirm on the test printer that `emergency_stop` resets a Box through the IWDG, and recover the MCB shutdown-handler bug.

## 2. Monitor and Box processor sensors

- [x] 2.1 Label reset reasons per MCU.
- [x] 2.2 Cover up to four Boxes in monitor context, including `BoxN_MCU`.
- [x] 2.3 Record each Box's serial history and the kernel USB lines at the first trigger line.
- [x] 2.4 Add `tltg_box_mcu_temperature` and wire it into `installer/package.yaml` and the bundle smoke test.
- [x] 2.5 Update `README.md`, `CHANGELOG.md` (`26.10.29.1`), and the QIDI Box observations.
- [x] 2.6 Installer core tests, version check, config formatting, OpenSpec validation, and the bundle smoke test pass; install on the test printer shows `Box1_MCU` and `Box2_MCU` and captures serial history on a real drop.
- [x] 2.7 Commit and open a PR to `dev`.

## 3. Host stalls at print start and end

- [x] 3.1 Install the local stall profiler on the test printer.
- [x] 3.2 Capture a print start and a print end with a Box heater on, and attribute every stall over 0.25 s (2026-10-29: start `SAVE_CONFIG_QD` 2.39 s; end 1.77 s at `OPTIMIZED_END` entry, 1.20 s template evaluation).
- [x] 3.3 List every `SAVE_CONFIG_QD` caller and reader of the saved mesh: optimized print start (fresh mesh) and the unused `OPTIMIZED_G29_ZSAFE`; stock `g29`, `M4029 R=0`, `M901 R=0`, and `M4032`; QIDI's power-loss resume loads the mesh named by `profile_name`.
- [x] 3.4 Add `tltg_background_save_config` (`TLTG_SAVE_CONFIG_QD`) and use it in the optimized mesh macros; output matches QIDI's `SAVE_CONFIG_QD` in a local harness against QIDI's `configfile.py`.
- [x] 3.5 Install on the test printer and confirm with the profiler that a fresh-mesh print start has no `SAVE_CONFIG_QD` stall and that `printer.cfg` gains the new mesh (2026-10-29 20:23: the mesh save ran in the background in 1.71 s and `printer.cfg` holds the new `kamp` mesh; the worst stall around it fell from 2.39 s to 0.90 s, mostly step generation for the first print moves, overlapping the save thread).
- [x] 3.7 Remove the local profiler from the test printer.

## 4. Heater refresh margin

- [x] 4.1 Apply a local 1 s resend to `heaters.py` on the test printer, with QIDI's original backed up.
- [x] 4.2 Confirm a steady Box heater is refreshed about every second during a print (2026-10-29 20:21: at a steady full power Box 2 writes about 10 B/s more than idle, against about 1–6 B/s under QIDI's 3.75 s resend; a 2.19 s print-end stall at 20:39 left the Box connected).
- [x] 4.3 Decide the scope: Box heaters only, from the `tltg_box_heater_refresh` module rather than a source patch; simulated against QIDI's `Heater.set_pwm`.
- [x] 4.5 Install on the test printer with QIDI's `heaters.py` restored and confirm the module logs each Box heater.
- [x] 4.4 Restore QIDI's `heaters.py` on the test printer before installing the module (stock hash confirmed 2026-10-29; the module logs `heater_box1` and `heater_box2`).

## 5. Box firmware shutdown fix

- [x] 5.1 Dump the Box bootloader read-only through `debug_read` and record its identity, application checks, erase range, and RAM use (Box 2, 2026-10-29: bootloader SHA-256 `64962da8…`, RDP level 0, no write protection; app region equals QIDI's release plus zero padding to 1 KiB).
- [x] 5.2 Build the patched image and verify the shutdown path in emulation (`02.03.01.21-tltg-shutdownfix1`, SHA-256 `bbd5c025…`: the 2-byte branch, the version marker in the zopfli-recompressed data dictionary, and the three `identify` size constants; from Box 2's live RAM the stock handlers re-enter `shutdown()` with `Invalid oid type` and the patched ones reach the shutdown report with the original reason).
- [x] 5.3 Adapt the THR flasher to the Box's USB startup stage, with recovery through that stage (local tool `~/tltg-box-fw/tool/flash_box_firmware.py` on the test printer: probe, transfer, rescue, readback; checked against the real bootloader code in emulation, including lost acknowledgements and a packet-0 failure; non-erasing probe passed on Box 2).
- [x] 5.4a Flash Box 2 on the test printer and verify by readback; Klipper loads `mcu_box2` as `02.03.01.21-tltg-shutdownfix1`.
- [x] 5.4b On the test printer, confirm `emergency_stop` leaves the patched Box connected and reporting `shutdown` (2026-10-29: Box 2 replied `shutdown: Command request` and kept its USB link; stock Box 1 went silent, disconnected 0.56 s later, and returned through the `0483:5740` stage; `FIRMWARE_RESTART` then reloaded both).
- [x] 5.5 Move the generator, checks, and flasher into the repository (`scripts/build_box_firmware.py`, `scripts/check_box_firmware.py`, `scripts/flash_box_firmware.py`, `firmware/max4-box-shutdown-fix-v1.json`) with spec deltas and `firmware/BOX_FIRMWARE.md`.
- [x] 5.6 Ship `box-firmware.sh` (status, install, restore, rescue) in the bundle, never run by install, update, or automatic updates; integration test `installer/tests/integration/test_box_firmware_flow.py`.
- [x] 5.7 Admit Box 1's bootloader build (`1e00811d…`, `COLOR_BOOT`) after the same analysis and emulated transfer checks; before admission, `box-firmware.sh install` on the test printer captured it as unsupported and left Box 1 unchanged (2026-10-29).
- [x] 5.7b Flash Box 1 through `box-firmware.sh install` on the test printer (2026-10-29: 39 packets, no retries, readback verified, bootloader unchanged; Klipper loads both Boxes as `02.03.01.21-tltg-shutdownfix1`).
- [x] 5.8 Exercise `restore` and `install` through `box-firmware.sh` on the test printer, and an emergency stop with both Boxes patched.
