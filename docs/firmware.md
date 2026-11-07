# Optional firmware fixes

[← Back to the README](../README.md)

Three optional fixes for QIDI's firmware. None is installed unless you ask for it, and uninstalling this project doesn't change firmware.

All three need an idle, ready printer with every heater target at zero. **Keep the printer powered on until the fix finishes.**

## Toolhead accelerometer fix

On the Max 4 with QIDI firmware `01.01.07.01`, the toolhead board (THR) reads its accelerometer incorrectly, which affects input shaper calibration. This fixes the LIS2DW FIFO bug. It isn't offered on other printers or firmware.

**How to install:** the installer asks about it first, before changing anything. **The default is No**; press Enter to skip it. If you say yes, it flashes after the rest of the install finishes. To opt in from the command line instead:

```bash
~/tltg-optimized-macros/install.sh --flash-thr-fifo
```

Add `--dry-run` for a preview without touching the board. `--yes` alone and automatic updates never flash firmware.

> [!IMPORTANT]
> **After flashing, run input shaper calibration before bed leveling or printing.** Your saved calibration stays in use, but it was measured with the buggy firmware. Run input shaper calibration on its own first: the screen's calibration page runs bed leveling before input shaping when both are checked. The installer does not run calibration for you.

**What it checks:** the installer checks the board's firmware and bootloader before flashing. A board that already has the fix is left alone and keeps its calibration. It saves the stock firmware under `~/printer_data/.tltg_thr_firmware_backups/`, flashes only the toolhead board, and verifies the result before restarting services.

**If your board isn't supported:** the firmware is left unchanged, your services are restored, and the configuration install is kept. The installer saves a capture and points to a shareable `report.json`; attach that to a GitHub issue, but not its flash binaries.

**To go back to stock firmware:** see [Restore the stock THR firmware from backup](../firmware/README.md#restore-the-stock-thr-firmware-from-backup). Details on supported bootloaders and recovery are in [THR-only operations](../firmware/FLASHING.md).

## QIDI Box shutdown fix

QIDI's USB Box firmware turns every Klipper shutdown of the Box, such as an emergency stop or a heater safety limit, into a restart. Klipper then reports `Lost communication with MCU 'mcu_boxN'` instead of the reason, and every other Box drops too. This fix keeps the Box connected, so Klipper shows what actually happened.

**How to install:** the installer never installs or offers it. Run it yourself over SSH from the installer folder:

```sh
cd ~/tltg-optimized-macros
./box-firmware.sh status    # which Boxes have the fix
./box-firmware.sh install   # flash it to every USB Box (or --box N)
./box-firmware.sh restore   # put QIDI's stock Box firmware back
```

The script asks you to type `FLASH`, and stops Klipper and the touchscreen for about four minutes per Box. It only flashes Box bootloader and firmware builds it recognizes, reads the result back to verify it, and keeps the stock firmware under `~/printer_data/.tltg_box_firmware_backups/`.

A fixed Box reports its version as `02.03.01.21-tltg-shutdownfix1` in Fluidd and `klippy.log`.

**If a flash fails:** see [QIDI Box firmware shutdown fix](../firmware/BOX_FIRMWARE.md).

## Mainboard closed-loop reply fix

On the Max 4, the X and Y motors are closed-loop: each one's driver knows where the motor is and answers questions about it over a bus that the mainboard runs. QIDI's mainboard firmware (`02.01.01.12`) passes an answer on to Klipper the moment it ends only for the status and version questions. Every other answer, including position error, encoder position, temperature, and the acknowledgement of each setting QIDI sends while homing, waits for 50 ms of silence on the bus, so it takes about 70 ms. This fix tells the mainboard how long each of those answers is, so it passes them on at their last byte. Answers it doesn't list are handled exactly as before. On the test printer, position-error, encoder, and temperature answers came back in a median 7–8 ms instead of 68–73 ms. Homing takes as long as before. The [X/Y step-loss monitor](tools.md#xy-step-loss-monitor) and QIDI's own motor checks work with or without it.

**How to install:** the installer never installs or offers it. Run it yourself over SSH from the installer folder:

```sh
cd ~/tltg-optimized-macros
./mainboard-firmware.sh status    # whether the mainboard has the fix
./mainboard-firmware.sh install   # flash it
./mainboard-firmware.sh restore   # put QIDI's stock mainboard firmware back
```

The script asks you to type `FLASH`, and stops Klipper and the touchscreen for about three minutes; the printer can't move or heat until they start again. It only flashes the mainboard bootloader and firmware build it recognizes, reads the result back to verify it, and keeps the stock firmware under `~/printer_data/.tltg_mainboard_firmware_backups/`.

A fixed mainboard reports its version as `02.01.01.12-tltg-clreplies1` in Fluidd and `klippy.log`.

**If a flash fails:** see [Max 4 mainboard closed-loop reply fix](../firmware/MAINBOARD_FIRMWARE.md).
