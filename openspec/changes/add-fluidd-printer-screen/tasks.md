## 1. Feasibility

- [x] 1.1 Confirm framebuffer capture as `qidi` and the display geometry and pixel format on `01.01.07.01`.
- [x] 1.2 Confirm that evdev writes to the touchscreen node reach `qidiclient` as presses, and record the axis ranges.
- [x] 1.3 Measure capture and encode cost, and confirm nginx `auth_request` and Moonraker forwarded-address authorization.

## 2. Implementation

- [x] 2.1 Add the screen service (framebuffer capture, change detection, JPEG, WebSocket, touch injection, origin check).
- [x] 2.2 Add guarded unit, server, and nginx route patches with systemd enable/disable lifecycle, wired into host operations independently of OS optimization policy.
- [x] 2.3 Add the Fluidd dashboard card to the bundle patch: default layout entry, component registration, and component.
- [x] 2.4 Extend lifecycle tests and fixtures for install, update, and uninstall of the new operations.
- [x] 2.5 Update `README.md`, `CHANGELOG.md` under `26.10.23.2`, and QIDI platform observations.

## 3. Verification

- [x] 3.1 Installer core tests, OpenSpec validation, known-versions check, and the bundle smoke test pass.
- [x] 3.2 Install on the test printer; the card shows the live screen, updates on change, and is idle when collapsed.
- [x] 3.3 With control confirmed, taps operate the touchscreen; view-only clicks do not.
- [x] 3.6 With control confirmed, a drag scrolls a touchscreen list (Print Files scrolled one row from a browser drag, without opening a file).
- [x] 3.4 A client outside Moonraker's trusted ranges without a token is refused; a cross-origin WebSocket is refused.
- [x] 3.5 Measure service CPU while watching an idle and a changing screen (no viewer: none; idle screen: about 2% of a core; screen changing every 0.5 s: about 25%, 41 frames in 12 s; 20 MB resident).
