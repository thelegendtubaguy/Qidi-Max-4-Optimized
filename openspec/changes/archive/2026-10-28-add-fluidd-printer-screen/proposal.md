## Why

Operators often want what only the touchscreen shows, or a touchscreen-only control, while away from the printer. Fluidd shows Klipper state but not QIDI's screen. On the Max 4, `qidiclient` draws the touchscreen into the Linux framebuffer and reads touches from the kernel input device, so the screen can be shown and pressed remotely without changing QIDI's software. QIDI no longer maintains its bundled Fluidd, so the dashboard can carry this view.

## What Changes

- A collapsible **Printer screen** card on the Fluidd dashboard shows the live touchscreen. It starts collapsed and does nothing until expanded. Expanded, it starts in view-only mode; after the operator confirms, clicks, taps, and drags on the image press the real touchscreen. It can go full screen.
- A package-owned screen service on the printer captures the framebuffer only while someone watches, sends a new image only when the screen changes, and injects touches through the touchscreen's input device. It listens only on the printer's loopback address.
- Fluidd's nginx site gains a `/tltg-screen/` route to the service. Each connection is checked against Moonraker's own authorization, so the screen is available to exactly the clients Moonraker trusts.
- Install and update deploy the card, service, and route as guarded host changes with the existing ownership, drift preservation, and uninstall restoration, independently of optional OS optimization policy.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `installer-lifecycle`: installs, updates, and restores the Fluidd printer-screen card, its screen service, and its nginx route.

## Impact

- `installer/runtime/fluidd_box_filaments.py` and a new `installer/runtime/fluidd_remote_screen.js` for the dashboard card.
- New `installer/runtime/remote_screen.py` (guarded unit, server, and nginx patches) and `installer/system/tltg_remote_screen.py` (the service), wired into `installer/runtime/system_optimizations.py`.
- Installer lifecycle tests and fixtures; `README.md`; `CHANGELOG.md` under the unreleased `26.10.23.2`.
- `openspec/observations/qidi-platform.md` for the touchscreen display and input stack.
- No Klipper config, macro, slicer, or QIDI binary changes.
