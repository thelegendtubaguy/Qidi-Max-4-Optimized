## Why

QIDI Plus 5 owners have asked for Valve Oil (GitHub issue 190), and the project's own Plus 5 arrives in a few days. The installer refuses the Plus 5 because `installer/package.yaml` `printers:` declares only Max 4 firmware.

Most of the Plus 5 is already known. Its board images are byte-identical to the Max 4's. Its host board and kernel family are the same, and 228 of 234 Klipper files match. What differs is X/Y motion: open-loop TMC2240 X/Y with sensorless homing replaces the Max 4's closed-loop drivers, and travel, positions, cutter, wiper, and slicer start G-code all change. The screen is also mounted on a portrait framebuffer. `openspec/observations/qidi-platform.md` (QIDI Plus 5) records this evidence, including two operator reports from a stock Plus 5.

This change lists what is still unknown, what must be read from a running Plus 5, and the work to admit Plus 5 firmware `01.01.02.01` once that evidence is in.

## What Changes

- Admit Plus 5 firmware `01.01.02.01` (SOC file prefix `QD_PLUS5_SOC_`) as a second printer. It gets its own stock snapshot, firmware-scoped guarded-patch variants, and source-patch expectations.
- Add `installer/klipper/printers/plus5/`. It holds the Plus 5's homing, cutter, wiper, waste-chute, and position macros under the macro names the common optimized macros already call.
- Split the start-print contract and the slicer packs per printer. The Plus 5 packs follow QIDI's Plus 5 profiles.
- Keep features tied to Max 4 hardware off on the Plus 5:
  - the closed-loop step-loss monitor and the mainboard closed-loop reply fix;
  - the 565 mm/s X/Y cap;
  - zram, until the Plus 5 kernel is verified for the modules;
  - THR and Box firmware fixes, until the Plus 5 bootloader builds are recognized.
- Show the Plus 5's rotated touchscreen upright in Fluidd's Printer screen card, with taps landing where they are shown.
- Update the README's supported printers, the operator docs, and the changelog.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `installer-lifecycle`: Plus 5 admission and baseline; which Max 4 host and firmware features a Plus 5 receives; the Printer screen card on a rotated screen.
- `optimized-printer-behavior`: Plus 5 motion, positions, and speed limits under the shared macro names.

## Impact

- `installer/package.yaml` (`printers:`, patch and source-patch variants), a new `installer/stock/qidi-plus5-defaults/`, a new `installer/klipper/printers/plus5/`, and `installer/supported_upgrade_sources.yaml`.
- The start-print contract and generated views, `orcaslicer_gcode/`, and `qidistudio_gcode/`.
- `installer/system/tltg_remote_screen.py`.
- Installer lifecycle and matrix tests, and the bundle smoke test's stock-snapshot path.
- `README.md`, `docs/`, `CHANGELOG.md`, and the Plus 5 observations.
- No change to Max 4 behavior.
