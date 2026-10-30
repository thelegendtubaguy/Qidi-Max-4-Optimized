## Why

USB QIDI Boxes drop off the printer with `Lost communication with MCU 'mcu_boxN'`, most often at print start or end while a Box heater holds or ramps (GitHub issue 159, and the project test printer). The link monitor could not say why: it labeled both Boxes' reset reasons as `mcu_box2`, it kept no record of what the Box was doing before it went quiet, and the reset reason it relied on is cumulative since power-on.

A drop captured on 2026-10-29 with the serial history in this change explains the chain (`openspec/observations/qidi-box/link-failures.md`, Drop at print end with the serial history):

1. A Box heater at a steady duty is refreshed only every 3.75 s, against the Box MCU's 5 s `max_duration`.
2. Print-start and print-end macros stall the Klipper host for longer than the 1.25 s of slack.
3. The Box MCU shuts down, as designed, but QIDI's Box firmware turns every shutdown into a watchdog reset (`openspec/observations/qidi-box/mcu-firmware.md`, Shutdown handling), so the operator sees a lost connection instead of the shutdown reason.

## What Changes

- The link monitor labels each Box's reset reason with the Box that answered, covers up to four Boxes, and at the first link-failure line records each Box's recent message history and the kernel USB lines.
- Each Box heater resends an unchanged output every second instead of every 3.75 s, from a package module (`tltg_box_heater_refresh`).
- Optimized print start saves a freshly calibrated mesh to `printer.cfg` in the background (`TLTG_SAVE_CONFIG_QD`) instead of through QIDI's `SAVE_CONFIG_QD`, which stalled Klipper for 2.4 s.
- Each configured Box gets a `BoxN_MCU` temperature sensor for its processor, shown in Fluidd and recorded by the monitor.
- Pending decisions, tracked in `design.md` and `tasks.md`: shorten the remaining host stalls at print start and end, and ship a Box firmware fix for the shutdown-to-reset bug.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `optimized-printer-behavior`: Box processor temperature sensors, and the optional link monitor's recorded evidence.
- `firmware-artifacts`: only if the Box firmware fix ships.

## Impact

- `installer/klipper/tltg/box_link_monitor.py`, new `installer/klipper/tltg/box_mcu_temperature.py`, `installer/klipper/tltg/background_save_config.py`, `installer/klipper/tltg/box_heater_refresh.py`, and their `.cfg` files, `installer/klipper/tltg-optimized-macros/bed_mesh.cfg`, the start-print contract, `installer/package.yaml`, and `scripts/smoke_test_installer_bundle.py`.
- `README.md` and `CHANGELOG.md` under the unreleased `26.10.29.1`.
- QIDI Box observations: `mcu-firmware.md`, `link-failures.md`, `evidence-and-open-questions.md`.
- No slicer G-code, `config/` file, or stock-mapped macro changes; QIDI's `configfile.py` is not patched.
