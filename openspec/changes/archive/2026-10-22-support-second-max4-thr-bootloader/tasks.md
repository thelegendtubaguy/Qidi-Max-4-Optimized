# Tasks

The operator with the second bootloader can run exactly one more script, with no follow-up questions or iterations. Do everything possible from the existing private capture first. Do not request additional reads, photos, logs, or reruns from that operator outside the single evidence run in group 4.

## 1. Recover the second bootloader offline

- [x] 1.1 Statically recover its entry point, UART receive/send paths, frame parser, identity reply, start/erase routine, flash programming routine, and application jump.
- [x] 1.2 Using bounded emulation, determine its erase range, short-final-packet and duplicate-packet programming, packet-zero retry semantics, data-session timeout, and startup receive window. Check that the zero-filled final-packet remainder in the capture is consistent with the recovered programming.
- [x] 1.3 Confirm statically that the bootloader hash is a shared build identity, without requesting another dump.
- [x] 1.4 List every behavior that static analysis and emulation could not establish; this list defines the scope of the live evidence run.
- [x] 1.5 Update `openspec/observations/qidi-platform.md` with recovered behavior and evidence qualifiers.

## 2. Profile-based offline checks

- [x] 2.1 Move first-bootloader hook addresses and expectations into a profile without changing its checked behavior.
- [x] 2.2 Add the second bootloader profile and run the full transfer, interruption, retry, and admission scenarios against both captured images.
- [x] 2.3 Keep bootloader binaries out of the repository; checks accept an operator-supplied capture per profile.

## 3. Tool and installer

- [x] 3.1 Admit the set of validated bootloader identities and select transfer behavior from readback identity. Add the second bootloader to that set only after groups 2 and 4 validate it; tasks 3.2–3.4 ship regardless.
- [x] 3.2 Capture unrecognized bootloaders privately without reset or unique-ID reads, including a shareable summary with no flash binaries.
- [x] 3.3 Report an unrecognized bootloader as unsupported with unchanged firmware, restored services, and no firmware blocker, and ask the operator to attach the shareable summary to a GitHub issue. Put the exact wording up for review in the PR.
- [x] 3.4 Extend installer THR lifecycle coverage for the unrecognized-bootloader outcome and second-profile admission.

## 4. Single live evidence run

- [x] 4.1 Write one self-contained, fail-closed, non-erasing script covering only the facts from 1.4 plus a stationary accelerometer sample rate, as described in the design. It never erases or programs the THR; flashing ships in the next installer version.
- [x] 4.2 Exercise every path on a first-bootloader printer, including a failed check, Ctrl-C, and a dropped SSH session during the THR read, and confirm after each that the printer is usable: Klipper ready, previously active services running, THR connected, and heater targets zero. Exercise every bootloader exchange in emulation against the second profile.
- [x] 4.3 Publish the script as a secret gist at a pinned revision and give the maintainer the single command to send the operator, which downloads, hash-checks, and runs it. Confirm that exact command works on a first-bootloader printer, then interpret the returned archive without follow-up.

## 5. Documentation and release

- [x] 5.1 Update `firmware/FLASHING.md`, `firmware/README.md`, and README THR guidance for multiple bootloaders.
- [x] 5.2 Bump the installer version, add the changelog section, and run THR, installer, bundle, and OpenSpec validation.
