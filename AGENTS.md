# AGENTS.md

## What this repo is

- This repository is a machine-specific dump of QIDI Max 4 Klipper/Fluidd configuration and macros.
- It is a reference/backup source for this printer, not a universal profile for other printers.
- The host UI stack is QIDI's forked Fluidd (`v1.30.5-ab46ef6`).

## Rules for agents working in this repo

1. Never modify `config/fluidd.cfg`.
   - That file is read-only on the printer.
   - Any requested behavior changes must be implemented in other config/macro files.

2. If a request would normally change `config/fluidd.cfg`, do this instead:
   - Explain that `config/fluidd.cfg` is immutable on-device.
   - Implement the change in another appropriate file under `config/`.

3. Preserve machine-specific and vendor-specific behavior unless the user explicitly asks to change it.

4. Keep redacted hardware identifiers redacted.
