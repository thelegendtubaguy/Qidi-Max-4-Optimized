# Design

## Context

`scripts/flash_thr_firmware.py` admits one bootloader SHA-256, and `scripts/check_thr_flashing.py` executes that captured image with hard-coded entry points, flash-controller and UART hook addresses, RAM receive-buffer and state addresses, and an expected full erase of `0x08008000`–`0x0801ffff`. The erase, packet-zero retry hazard, data-session timeout recovery, startup receive window, and identity reply `01020102` were all established for that image only.

A read-only dump from a second printer (see `openspec/observations/qidi-platform.md`) shows the same MCU registers and stock application with an unrelated bootloader build: different code length, stack pointer, and every code page, sharing only a CRC16 table. Its flash also holds zeros after the stock image through the end of the final 1,024-byte packet, where the first board is erased. None of the first bootloader's validated properties transfer.

### Evidence constraint

The operator with the second bootloader can run one more script and cannot answer follow-up questions or run iterations. The available evidence is their earlier read-only capture: the 32 KiB bootloader, flash from `0x08000000` through `0x0801ffff`, Klipper identify data, and CPUID/IDCODE/flash-size registers. The capture is kept outside version control in the maintainer checkout at `tltg-local/thr-captures/second-bootloader-report.tar.gz`; treat it as untrusted input and never commit its contents. Work proceeds offline first, and live access is reserved for facts that static analysis and emulation cannot establish.

## Goals / Non-Goals

**Goals:**

- Flash and verify the FIFO fix on boards with the second bootloader with the same safety evidence as the first.
- Make each admitted bootloader an explicit profile so further builds can be added without weakening admission.
- Turn an unrecognized bootloader into a diagnosable, clearly reported no-change outcome.

**Non-Goals:**

- Admitting bootloaders by heuristic, partial hash, or probe reply.
- Programming or modifying any bootloader.
- Establishing physical recovery entry; that boundary remains unverified for both builds.

## Decisions

### Per-bootloader profiles own validated behavior

A profile records the exact bootloader SHA-256, expected identity reply, start and data acknowledgement forms, erase range, programmed-byte expectations after a short final packet, packet-zero retry semantics, and emulation hook points. The checker runs the existing scenario suite against each profile; the admission set is the profiles that pass. Readback identity selects the profile; a probe reply only confirms it. Alternatives considered: one tolerant transfer path for all builds, rejected because the packet-zero and erase behavior that determine safety differ by implementation.

### Pin only a shared build identity

Before pinning, confirm statically that the second bootloader hash is a build identity rather than device-specific content: no data region, no reads of the unique-ID area stored into its own flash, and no writes to the bootloader region. A matching independent dump, such as a later unrecognized-bootloader capture from another operator, corroborates but is not required and must not be requested from this operator. Pinned hashes are build identities, not hardware identifiers; evidence remains anonymous.

### Offline first, one live evidence run

Static analysis and bounded emulation of the captured image establish the identity reply, frame and acknowledgement handling, erase range, programming of short and duplicate packets, packet-zero retry, data-session timeout, startup receive window, and application jump. Each conclusion records whether it came from code or emulation, and remaining unknowns are listed explicitly before any live script is written.

A single self-contained script then resolves only those remaining unknowns in one unattended run. Typical candidates are the live identity reply after the application `reset` command, the time for the application to return, and a stationary accelerometer sample rate. The script:

- is started by exactly one command that the maintainer sends the operator, run over SSH as `qidi`. That command downloads a pinned revision, checks its SHA-256, and runs it, with no repository checkout, arguments, file edits, or follow-up steps. Questions are limited to a `sudo` password when QIDI's default has been changed. It ends by printing the single archive path to send back;
- MUST leave the printer usable on every exit path, including success, a failed check, Ctrl-C, hangup, termination, and lost terminal output: THR application intact and running, previously active services restored, Klipper confirmed ready with zero heater targets, and no configuration, firmware-pending, or service-enablement changes;
- performs every preflight before stopping services, and restores services before printing anything that could fail on a lost terminal;
- if it cannot confirm that state, states one concrete recovery action (reboot, or power cycle if the THR does not reconnect) and records the unconfirmed state in the summary;
- never reads the MCU unique-ID region or identifying configuration such as `MCU_ID.cfg` or `box.cfg`;
- sends the application `reset` command only if emulation shows the second bootloader returns to an intact application after an identity-only session; otherwise that check stays offline-only;
- compares every live observation with the emulated profile and stops at the first mismatch, still packaging the evidence collected so far;
- writes one archive whose summary states each check as matched, mismatched, or not reached, so maintainers can interpret it without asking questions;
- is exercised before distribution on a first-bootloader printer for every non-erasing path, and in emulation against the second bootloader for every bootloader exchange.

The evidence run never erases or programs the THR. Admission of the second bootloader rests on the validated emulation profile plus that run's matching non-erasing evidence. Operators with that bootloader first flash the fix through the next installer version's opt-in, which keeps stock recovery files and requires complete readback verification.

### Verification compares the application image

Readback verification stays limited to the image length plus the unchanged bootloader. Bytes after the image may legitimately differ by bootloader, as the zero-filled final-packet remainder shows; profile emulation asserts each build's expected post-image bytes instead.

### Packet-zero stays non-retried until proven otherwise

The transfer keeps stopping on an ambiguous packet-zero acknowledgement for every profile unless that build's emulation shows the retry is idempotent.

### Unrecognized bootloader is a captured, non-fatal outcome

On an unrecognized bootloader, the tool writes the bootloader and application-region readback to the private recovery directory with mode `0600`, never reads the MCU unique-ID region, and sends no reset. Because firmware cannot have changed, the installer restores previously active services, leaves no pending firmware blocker, keeps the configuration result, and reports that the FIFO fix is unavailable for this bootloader and THR firmware was not changed. New and changed operator strings require approval before implementation.

### Maintainer decisions

- **Release gate:** the unrecognized-bootloader capture and reporting ship in the next installer version even if the second bootloader is not yet validated. Admission of the second bootloader ships only after the offline profile passes and the live evidence run matches it; otherwise it waits for a later version.
- **Sharing a capture:** the installer's unrecognized-bootloader capture includes a shareable summary like the evidence script's `report.json`. It holds hashes, per-page bootloader hashes, Klipper identify data, and ID registers, but no flash binaries, unique-ID data, or identifying configuration. The operator message asks the operator to attach that summary to a GitHub issue; binaries are requested privately only when needed. This direction is approved; the exact operator wording is reviewed in the implementation PR.
- **Evidence script hosting:** a secret gist pinned by revision and SHA-256, kept out of the repository and release bundle.
- **Live testing:** the maintainer's first-bootloader test printer is pre-authorized for evidence-script testing while idle, including service stops, deliberate SSH drops, and the default `sudo` password. Testing never erases or programs its THR.

## Risks / Trade-offs

- [Emulation fidelity] → Hooks replace only flash-controller, UART, and jump operations, matching the existing model; live validation is still required before release.
- [Startup or timeout recovery differs] → A build without data-session timeout recovery leaves a weaker recovery story; document it per profile and do not admit a build whose interrupted-transfer behavior is unbounded.
- [More builds exist] → Unrecognized-bootloader capture makes each new build diagnosable without manual tooling.
- [Single live run] → Live evidence cannot be iterated. Exhaust offline analysis first, make the script fail-closed and self-explaining, and treat any unresolved fact as blocking admission rather than as a reason for a second request.
- [No live transfer before release] → The first real transfer with the second bootloader happens through the released installer. Mitigate by admitting it only when every emulated scenario passes and every live non-erasing observation matches the profile; the installer's stock backup, pending-operation blocker, and readback verification still apply.

## Open Questions

- What determines which bootloader a board ships with: production batch, board revision, or MCU vendor?
- Does QIDI's touchscreen updater use different transfer behavior for the second bootloader?
