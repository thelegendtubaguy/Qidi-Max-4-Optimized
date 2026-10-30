# QIDI Box firmware shutdown fix

`max4-box-shutdown-fix-v1` fixes how the USB QIDI Box (firmware `02.03.01.21`) handles a Klipper shutdown. In QIDI's firmware, every shutdown of the Box's processor, whether from an emergency stop, a heater safety limit, or any other Klipper MCU error, loops in QIDI's Box feeder shutdown code until the Box's watchdog restarts it. Klipper then reports `Lost communication with MCU 'mcu_boxN'` instead of the reason, and every other Box restarts the same way. With the fix, a Box that shuts down stays connected and Klipper shows the real reason, such as `Scheduled pwm event will exceed max_duration`.

The patched firmware reports its version as `02.03.01.21-tltg-shutdownfix1`. You can see it in `klippy.log` (`Loaded MCU 'mcu_boxN' … (02.03.01.21-tltg-shutdownfix1 …`), in Fluidd's system information, and with `./box-firmware.sh status`.

The fix changes two instruction bytes and the version string. Nothing else about the Box changes. RS-485 Boxes have no Klipper processor and are not affected.

## Commands

Run these from the unpacked installer folder (`~/tltg-optimized-macros`) over SSH. The normal installer, updates, and automatic updates never flash Box firmware, and `--yes` cannot authorize it.

```sh
./box-firmware.sh status               # read-only: each USB Box and its firmware
./box-firmware.sh install              # flash the fix to every USB Box that needs it
./box-firmware.sh install --box 1      # only Box 1 (repeat --box for more)
./box-firmware.sh restore              # put QIDI's stock firmware back
./box-firmware.sh rescue --box 1       # recover a Box that is stuck in its bootloader
```

`install` and `restore` show each Box's firmware and what they will do, then ask you to type `FLASH`. They need an idle, ready printer with every heater target at zero. Klipper and the touchscreen stop for about four minutes per Box. Keep the printer and every Box powered on until the script finishes.

For each Box the script:

1. Reads the Box's bootloader and firmware through Klipper's connection to it, and admits them only if both match a validated build exactly.
2. Saves the read-back under `~/printer_data/.tltg_box_firmware_backups/`.
3. Builds the patched image from the Box's own stock firmware, flashes it, reads it back, and checks it matches exactly, with the bootloader unchanged.

A Box that already has the requested firmware is skipped. A Box whose bootloader or firmware the script does not recognize is not changed: the script saves a read-only capture and points to a shareable `report.json` in it. Attach only `report.json` to a GitHub issue; the `.bin` files stay private.

## If a flash fails

The Box's bootloader is never erased or written. If a transfer stops part way, the Box erases the start of its firmware and stays in its bootloader, waiting for a new transfer. The script then leaves Klipper and the touchscreen stopped, keeps `~/printer_data/.tltg_box_firmware_pending.json`, and prints the command to run:

```sh
./box-firmware.sh rescue --box N
```

Rescue waits for the Box's bootloader, flashes QIDI's stock firmware from the backup or from `~/update`, verifies it, and starts the services again. If the Box is not already waiting, turn that Box off and on again when the script asks. Until the pending record is cleared, the installer refuses other operations.

Uninstall and `restore.sh` do not change Box firmware. Use `./box-firmware.sh restore`. A QIDI firmware update that reflashes the Box also restores stock firmware.

## Checks for developers

`scripts/check_box_firmware.py` checks the patch against QIDI's stock image, including the data dictionary the Box serves to Klipper, which it runs in emulation. Install `firmware/check-requirements.txt` first.

```sh
python3 scripts/check_box_firmware.py --stock-image QD_MAX4_BOX_02.03.01.21_20260124.bin \
  [--bootloader-backup bootloader.bin [--ram-dump ram.bin]]
```

With a captured bootloader, it runs the transfer tool against that bootloader's own code: stock and patched transfers, lost acknowledgements, an unacknowledged first packet, a non-erasing identity probe, and a bootloader already waiting. With a RAM dump read from a configured Box, it runs the firmware's shutdown handlers: stock must re-enter shutdown, the patched image must report the original reason. No bootloader or RAM binary is shipped in the repository.
