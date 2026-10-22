# Proposal

## Why

A second Max 4 on firmware `01.01.07.01` has the same THR MCU and the stock `02.02.01.08` application, but a different THR bootloader build. The installer correctly refuses it before reset, so that printer keeps the LIS2DW FIFO bug. The refusal is reported as a failed firmware operation even though nothing changed, and the tool saves no bootloader capture, so diagnosing an unknown bootloader currently requires a separate manual dump.

## What Changes

- Recover the second bootloader's identity reply, start/erase range, packet programming, acknowledgement, retry, and timeout behavior from its captured image, and execute it in bounded emulation.
- Generalize offline transfer checks from one hard-coded bootloader model to a per-bootloader profile, and run the same transfer, recovery, and admission scenarios against every profile.
- Admit a bootloader only when its exact identity has a validated profile; the tool selects transfer behavior from the bootloader identified by readback.
- When readback finds an unrecognized bootloader, retain a private read-only capture with the recovery files, send no reset, restore services, and report that the FIFO fix is unavailable for that bootloader and THR firmware was not changed.
- Derive everything possible offline from the existing capture. The operator with the second bootloader is available for one more script run with no follow-up, so every remaining live fact is collected by a single self-contained, fail-closed evidence script.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `thr-firmware-transfer`: admission covers each bootloader with a validated transfer profile; unrecognized bootloaders are captured without reset.
- `installer-lifecycle`: an unrecognized bootloader is reported as unsupported with unchanged firmware and no firmware blocker.

## Impact

`scripts/flash_thr_firmware.py`, `scripts/check_thr_flashing.py`, `installer/runtime/thr_firmware.py`, THR documentation, and an installer version with changelog. No bootloader binaries or operator-identifying evidence enter the repository. Other boards and the patched application image are unchanged.
