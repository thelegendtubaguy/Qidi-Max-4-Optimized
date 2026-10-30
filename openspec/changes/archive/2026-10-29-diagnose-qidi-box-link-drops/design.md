## Context

Evidence lives in the QIDI Box observations; this design records decisions and handoff state only.

- `mcu-firmware.md`: reset-reason semantics (flags are never cleared; the reading is the highest-ranked reset since power-on), the `0483:5740` startup stage, stall sources, Shutdown handling (the MCB handler bug and its candidate 2-byte fix), and the firmware update path.
- `link-failures.md`: the controlled power and link loss calibration, the captured print-end drop with its timeline, and the candidate-cause table.
- GitHub issue 159: one USB Box, drops at print start with the Box heater at full power and at print end; the requester's `IndependentWatchdog` reading is a real watchdog reset since that Box's last power-on.

Cause chain established on 2026-10-29: a Box heater at a steady duty is resent only every `0.75 * MAX_HEAT_TIME` (3.75 s; QIDI sets `MAX_HEAT_TIME = 5.0`), so a host stall over about 1.25 s lets the Box's 5 s `max_duration` expire; the resulting MCU shutdown loops in QIDI's MCB shutdown handler until the IWDG resets the Box. Klipper's `emergency_stop` after the timeout resets every other Box the same way.

## Goals / Non-Goals

**Goals:**

- Record enough on every drop to attribute it: which Box, how long it was silent before the kernel saw the USB loss, what the host last sent it, and its reset reason.
- Remove the trigger: keep host stalls at print start and end short, and widen the heater refresh margin.
- Make a Box shutdown report its reason instead of resetting the Box.

**Non-Goals:**

- RS-485 Boxes (`box485`), which have no Klipper MCU.
- Changing `MAX_HEAT_TIME`, heater verification, or any heater safety limit.
- Vendor Box motion, RFID, or drying behavior.

## Decisions

- **Box processor sensors come from a package module, not config.** QIDI's Box detection rewrites the Box sections for however many Boxes it finds and restarts Klipper, so a fixed `[temperature_sensor]` naming `mcu_box2` would stop Klipper on a one-Box printer. `tltg_box_mcu_temperature` creates `temperature_sensor BoxN_MCU` for each configured `mcu mcu_boxN` at config time, the same way QIDI's `box_config.py` creates its Box sensors, with no limits so the ADC range check cannot add a shutdown path.
- **The monitor's history comes from Klipper's serial queue.** `mcu._serial.dump_debug()` returns the last 100 sent and received messages with host monotonic times. Klipper only logs it for MCUs that report a shutdown, which a lost Box never does, so the monitor saves it at the first trigger line. The `serial-history clock` line gives monotonic and boot time for aligning with dmesg. Silence before a loss is measured from the last received message to the first kernel USB error for that path (a dying hub logs `error -71` before the `USB disconnect` line); normal gaps are under 0.2 s, a watchdog stall shows about one IWDG period (nominally 512 ms).
- **The print-start mesh save runs in a background thread.** QIDI's power-loss resume loads the mesh named by `profile_name`, so the fresh `kamp` mesh must still reach `printer.cfg`. `tltg_background_save_config` snapshots the pending values on the main thread and does QIDI's read, checks, and write in a thread, keeping the backup as a hard link and replacing `printer.cfg` atomically so a restart mid-save never finds it missing. It wraps `SAVE_CONFIG` and `SAVE_CONFIG_QD` to wait for a save in progress. A failed save is reported in the console instead of stopping the print. Only the optimized mesh macros use it; QIDI's calibration macros keep `SAVE_CONFIG_QD`, since they never run during a print.
- **Box heaters resend every second, from a package module.** QIDI's `heaters.py` resends an unchanged output once `read_time` passes `pwm_time + 0.75 * MAX_HEAT_TIME`; with the AHT20 read about every 0.75 s on the main reactor, a steady Box heater is resent every 4.5 s against a limit of `pwm_time + 5`, so 0.5–1.25 s of stall can expire it. `tltg_box_heater_refresh` wraps `set_pwm` on each `heater_boxN` at `klippy:connect` and, after any send, pulls `next_pwm_time` in to `pwm_time + 1.0`. QIDI's `heaters.py` is not patched, so no per-firmware hashes are needed; a heater without `set_pwm`, `next_pwm_time`, or `pwm_delay` is logged and left alone. Other heaters keep Klipper's schedule: their ADC sensors report on the serial thread and are not starved by reactor stalls. A simulation with QIDI's `Heater.set_pwm` and 0.75 s readings at full power: a 2.2 s stall expires the stock heater in 43 % of phases and never with the module; the module holds to about 3.4 s. Cost: about one 10-byte message per second per heating Box.
- **Box AHT20 polling stops after a shutdown.** A patched Box stays connected in its shutdown state and refuses `i2c_read`; QIDI's `aht20_f` lets the resulting `CommandError` escape its reactor timer, which crashed Klippy about 1 s after an emergency stop and, after systemd restarted it, replaced the reason with `Can not update MCU 'mcu' config as it is shutdown`. `tltg_box_heater_refresh` wraps each Box heater sensor's `sample_timer.callback` at `klippy:ready`; after `printer.is_shutdown()` a failure returns `NEVER`, otherwise it re-raises. Wrapping before any shutdown also covers a read already in flight.
- **Reset-reason handlers are registered per MCU.** Each Box numbers its object ids independently, so Boxes with the same config share oids; the label comes from the MCU the handler was registered on.

## Open decisions
- **Host stall fixes.** Measured at print end: eight `SAVE_VARIABLE` calls at 55–65 ms each (QIDI's `save_variables.py` rewrites and re-parses the whole 129-line file per call) and end-macro bursts of 0.2–0.4 s account for about 1 s of a 2.1 s stall. Print end on 2026-10-29: 1.77 s when `OPTIMIZED_END` starts (step generation for the park and trash moves plus five `_TLTG_SAVE_VARIABLE_BASE` writes at 55–70 ms each), and 1.20 s of macro template evaluation copying printer objects about 70 s later. A second print end (20:39, 1 s resend active) stalled 2.19 s at the same point: 50 of 68 samples were step generation for the moves still buffered when the end macro forces a lookahead flush, which repository macros cannot avoid; the Box stayed connected. With the drop's measured 0.1 s `pwm_delay` and 0.75 s AHT20 polling, QIDI's resend leaves 0.5–1.25 s of stall margin depending on phase, and the 1 s resend about 3.25 s. At print start (2026-10-29, fresh adaptive mesh), the largest stall was 2.39 s in `SAVE_CONFIG_QD` after `BED_MESH_CALIBRATE PROFILE=kamp` in `_OPTIMIZED_PREPARE_PRINT_MESH`: it re-reads and re-parses the whole include tree to persist the mesh. That alone exceeds the 1.25 s slack. The next largest was 1.15 s of `SAVE_VARIABLE` writes plus step generation; the rest stayed under 0.61 s. The mesh save is handled (see Decisions). Remaining candidates: skip `SAVE_VARIABLE` when the value is unchanged, batch writes, and defer non-urgent writes until after the end macros.
- **Box firmware fix.** Built and running on one test Box (see Handoff state). The bootloader (`COLOR BOOT`, SHA-256 `64962da8…`) checks nothing but per-packet CRC16, erases only sectors 2–5, never writes below `0x08008000`, and gives a 2 s window on every reset; it stays resident while the first application sector is blank. Rules for any flasher: one start per boot, never resend start or packet 0 (the write pointer rewinds only at reset), resending the previous data packet is safe. Open: shipping. That needs the generator and emulation checks in the repository, a Box variant of the THR flasher with bootloader admission and readback, operator recovery documentation, and `firmware-artifacts` deltas. The marked version is `02.03.01.21-tltg-shutdownfix1`; QIDI's `box_detect` keys updates on the USB name (`QIDI_BOX_V2_1.2.1`) and an empty tools folder, not this string, and the touchscreen's online check may offer QIDI's Box image as an update, which restores stock.

## Handoff state

Local, uncommitted changes in this worktree implement the Box processor sensors and monitor changes under `26.10.29.1`; they are installed on the project test printer.

Local-only diagnostics on the test printer, not in the repository:

- Stall profiler: removed from the test printer on 2026-10-29 after the print-start and print-end captures.
- Heater refresh test: retired. QIDI's `heaters.py` was restored from `~/tltg-local-backups/heaters.py.qidi-stock` (sha256 `aeb8130c…dd8d00`) and `tltg_box_heater_refresh` installed in its place on 2026-10-29.
- The test printer's `~/klipper/klippy/extras/box_config.py` carries `TLTG_BOXCAP` G-code logging from another session's work. It is not part of this repository and adds work during macro bursts; remove it when that work ends.

- **Both Boxes on the test printer run patched firmware** `02.03.01.21-tltg-shutdownfix1` (readback verified, 2026-10-29), last installed through `box-firmware.sh install` after a verified `restore`; backups are under `~/printer_data/.tltg_box_firmware_backups/`. `./box-firmware.sh restore` from the installed bundle puts stock back on both. Snapshots (bootloader, application region, RAM) and the tool, stock image, and patched image are in `~/tltg-box-fw/` on the printer. To restore stock: stop `qidi-client` and `klipper` through Moonraker's service API, then run `~/klippy-env/bin/python ~/tltg-box-fw/tool/flash_box_firmware.py transfer --usb 2-1.4.1.2 --image ~/tltg-box-fw/tool/QD_MAX4_BOX_02.03.01.21_20260124.bin --confirm-write`. If the application does not start, use `rescue` with the same arguments and power-cycle Box 2 when prompted: every reset opens a 2 s bootloader window, and a blank first application sector keeps the bootloader resident. QIDI's own Box update also restores stock.

Unchanged GitHub state: no reply has been posted to issue 159.

## Follow-ups outside this change

- Shorten the remaining print-end stall sources in repository macros, starting with unchanged `SAVE_VARIABLE` writes (five at 55–70 ms each at `OPTIMIZED_END` entry). Most of that 1.8–2.2 s stall is Klipper's own step generation for buffered moves, which macros cannot avoid; the Box heater refresh covers it.
- Run a full print with the packaged `tltg_box_heater_refresh` module (the 2026-10-29 prints used the equivalent local `heaters.py` change).
- GitHub issue 159: draft a reply for operator approval (the `IndependentWatchdog` reading is a real watchdog reset; the cause chain; the optional Box firmware fix), then ask the requester to install the build, power-cycle the Box, enable the monitor, and post `tltg_box_link.log` after any further drop.
