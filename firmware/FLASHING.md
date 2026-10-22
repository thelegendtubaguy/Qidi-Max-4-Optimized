# Max 4 THR-only operations

`scripts/flash_thr_firmware.py` operates only on `/dev/ttyS4`, using the known Max 4 THR application and an admitted bootloader profile. It does not manage services, change printer configuration, run motion or heater commands, or update other boards. Run hardware operations on the printer with its existing `/home/qidi/klippy-env/bin/python`; retain the repository layout so the script can read its firmware manifest.

**Do not erase firmware until a board-specific recovery entry has been verified.** Both admitted bootloaders have short startup receive windows, and Linux startup can exceed them. A whole-printer power cycle is not a verified recovery procedure. Stock-image and bootloader backups do not by themselves establish physical recovery access.

## Installer opt-in

On supported firmware `01.01.07.01`, interactive installation asks whether to flash the FIFO fix, defaulting to No. An explicit y/yes authorizes only that invocation. After flashing THR, rerun input shaper calibration before printing; the installer does not run calibration. `install.sh --flash-thr-fifo` provides the same opt-in without answering the question; `--yes` alone and automatic updates never authorize firmware access. `--flash-thr-fifo --dry-run` previews without UART access or service changes.

The installer reads the actual application and bootloader before deciding whether to program. An already-patched application is verified without resetting or reflashing it. For stock firmware, the installer preserves recovery files, generates the hash-locked patch from the readback, transfers only THR, and verifies complete readback. Private evidence stays under `~/printer_data/.tltg_thr_firmware_backups/`; configuration restore and uninstall do not revert MCU firmware. An unrecognized bootloader is captured without reset or programming, then previously active services are restored and readiness is checked. It does not leave a firmware blocker or invalidate the configuration install. Attach only the capture's `report.json` to a GitHub issue; keep the flash binaries private.

An interrupted or unverified firmware operation retains `~/printer_data/.tltg_thr_firmware_pending.json` and blocks further installer operations. Its record identifies the recovery directory and previous service states. If programming may have begun, serial-owning services remain stopped. Use the stock application and bootloader in that directory's `before/` snapshot for the manual recovery procedure below. Remove the pending marker only after complete application/bootloader verification, restoration of the recorded service states, and confirmed printer readiness with zero heater targets. Do not use the configuration recovery-sentinel command to bypass a firmware blocker.

## Ownership and backups

Before contacting the printer, query its print state. Stop if the state is unavailable or indicates an active or paused print. After confirming idle, check Klipper readiness and all heater targets, including the chamber heater; all targets must be zero.

Record which services are active. Stop the optimized update timer, touchscreen client, and Klipper before opening the UART:

```bash
sudo systemctl stop tltg-optimized-auto-update.timer
sudo systemctl stop qidi-client.service
sudo systemctl stop klipper.service
```

The tool refuses UART access unless all three are inactive. `--printer-idle-confirmed` is an operator assertion of the preceding checks, not an API check by the tool. Keep the printer attended and do not start a job during these operations.

From the repository root on the printer, create a new backup directory:

```bash
/home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py snapshot \
  --output-dir dist/thr-before --printer-idle-confirmed
```

Snapshot reads the bootloader and complete 35,056-byte application through the installed Klipper transport. It does not reset or write the MCU. Copy the directory to a separate computer before proceeding. The stock recovery directory must contain:

- `bootloader.bin`: 32,768 bytes, SHA-256 `46358f306156edbdee1822dcca17206f78241b01a7e96587215860c4b0d34fc6` or `31f8344db7b091df5429960bc9cd06065e2188c3b8092e43fb65eb3f2833723c`.
- `application.bin`: stock THR SHA-256 `1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62`.
- `snapshot.json`: the captured hashes.

The snapshot command also accepts the known patched application for post-transfer readback. Erasing operations admit only the exact validated bootloader hashes above, not identity replies alone.

Snapshot of an unrecognized bootloader saves `bootloader.bin`, `application.bin`, the complete `application-region.bin`, and a shareable `report.json`, then exits with status `3`. Files have mode `0600`; the summary contains hashes, per-page bootloader hashes, Klipper build information, and non-unique MCU ID registers, but no flash binaries or unique-device-ID reads. No reset, erase, or programming command is sent. The manual tool does not restore services; restore the recorded active services and confirm readiness after this no-change outcome. Unknown application bytes never authorize a transfer. Keep private backups out of Git.

## Non-erasing bootloader probe

With services still stopped and the stock backup preserved:

```bash
/home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py probe \
  --backup-dir dist/thr-before --reset --printer-idle-confirmed
```

`--reset` first reads and admits the installed application and bootloader, then sends only the THR application's `reset` command. Probe sends the basic identity request at 115,200 baud; it does not send the erasing start command or any firmware data. The expected response payload is `01020102` (model `02`, bootloader `1.2`) for the `46358f30…` build and `0102` for the `31f8344d…` build.

After a successful probe, allow at least twelve seconds for the bootloader to return to the application. Take another snapshot in a new directory and verify it against the stock image to establish unchanged flash bytes. Do not resume normal service if the application does not return.

## Confirmed transfer and readback

Only after verifying non-erasing entry, application return, and independent recovery access, transfer an admitted image:

```bash
/home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py transfer \
  --image dist/max4-thr-fifo-v1/QD_MAX4_THR_02.02.01.08_20260303_TLTG_FIFO_v1.bin \
  --backup-dir dist/thr-before --reset \
  --printer-idle-confirmed --confirm-write
```

The start command erases the entire application region `0x08008000`–`0x0801ffff`, including bytes beyond the supplied image. The bootloader region is not an update target. The tool admits only the pinned stock and patched images and validates acknowledgements against each packet's index and byte count. It stops rather than blindly retrying an ambiguous packet-zero acknowledgement, because that retry is not idempotent in either validated bootloader.

A successful transfer reports `transfer_acknowledged: true` and `verified: false`. After allowing the application to return, take and verify a complete readback:

```bash
/home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py snapshot \
  --output-dir dist/thr-after --printer-idle-confirmed
/home/qidi/klippy-env/bin/python scripts/flash_thr_firmware.py verify \
  --image dist/max4-thr-fifo-v1/QD_MAX4_THR_02.02.01.08_20260303_TLTG_FIFO_v1.bin \
  --backup-dir dist/thr-after --original-backup-dir dist/thr-before
```

Verification is offline and requires the selected application bytes and an admitted bootloader. `--original-backup-dir` additionally compares the bootloader byte-for-byte with its pre-transfer backup; the installer always makes this comparison. Bytes beyond the application image are not installation evidence: different bootloaders can leave different final-packet padding. The vendor version string remains unchanged and is not installation evidence.

On failure, keep the serial-owning services stopped. Do not immediately resend a start or data packet from another program. In bounded emulation, both bootloaders erase the first application page after an interrupted data session times out. The `46358f30…` build permits stock retransmission; the `31f8344d…` build requests a system reset, reopening its four-second startup receive window. That does not prove recovery after power loss: a cold boot can jump into a partially programmed application. Use the independently verified board-specific recovery entry, then transfer `dist/thr-before/application.bin` with the same tool and stock backup. Omit `--reset` only when recovery has already placed the board in its bootloader. Read back and verify the stock image before restoring service.

## Restore normal service

Restore only services that were active before the operation. After verified application return:

```bash
sudo systemctl start klipper.service
sudo systemctl start qidi-client.service
sudo systemctl start tltg-optimized-auto-update.timer
```

Confirm printer readiness and zero heater targets before any measurement. If print state cannot be determined, stop printer access and confirm idle state locally. A stationary accelerometer capture can then compare delivered sample rate and error counters; it requires no homing, heating, motion, or resonance sweep.

## Offline transfer checks

On a development computer, install `firmware/check-requirements.txt`, then run:

```bash
python3 scripts/check_thr_flashing.py \
  --stock-image stock-thr.bin \
  --patched-image dist/max4-thr-fifo-v1/QD_MAX4_THR_02.02.01.08_20260303_TLTG_FIFO_v1.bin
```

Add `--bootloader-backup bootloader.bin` to execute a captured bootloader's actual parser, erase loop, programming bounds, and reply construction. Repeat that option to check both exact profiles in `scripts/thr_bootloaders.py`. Both profiles are checked for full transfers, interruption recovery, duplicate packets, lost acknowledgements, non-erasing identity sessions, and admission boundaries. The first leaves short-packet padding erased; the second programs zeros. UART output, flash-controller register operations, application jumps, and system resets are emulated; these checks do not validate electrical behavior or physical recovery access. No bootloader binary is shipped in the repository.
