## Context

On firmware `01.01.07.01`, `qidiclient` is an LVGL application. It holds `/dev/fb0` (800×480, 32 bpp XRGB, stride 3200, no panning) and the Goodix touchscreen's evdev node `/dev/input/event0`, whose absolute axes span 0–799 and 0–479, the same as the framebuffer. The `qidi` user is in `video` but not `input`. Writing events to the evdev node reaches `qidiclient` as real touches. The host is a four-core RK3308 with about 486 MB of RAM, shared with Klipper and Moonraker. Moonraker's virtualenv ships Pillow 10 with libjpeg-turbo. nginx serves Fluidd, has `auth_request`, and forwards the client address to Moonraker, which honors it for trusted-client checks. Evidence is in `openspec/observations/qidi-platform.md`.

Measured on the host: a full framebuffer copy through `mmap` costs about 28 ms of CPU, every eighth row about 5 ms, and a quality-80 JPEG of the frame about 20 ms. Continuous `ffmpeg` MJPEG encoding used about 66% of a core at 4 fps.

## Goals / Non-Goals

**Goals:**

- See and operate the touchscreen from Fluidd with no cost while nobody watches and little while the screen is idle.
- Grant the screen to exactly the clients Moonraker authorizes, with no new LAN port.
- Same install, update, drift, and restore guarantees as the other guarded host patches.

**Non-Goals:**

- A standalone page, link sharing, or QR codes outside Fluidd.
- Multi-touch, pinch, or audio.
- Changing `qidiclient` or its display stack.

## Decisions

### Change-driven JPEG over one WebSocket

The service samples a rotating eighth of the framebuffer rows every 100 ms against the last full frame. When a sample differs it copies the full frame and, if that differs, encodes a JPEG and sends it to every viewer, at most about eight frames a second. Any change taller than eight rows is seen on the next tick, and every row is checked within 0.8 s. Each viewer always receives the newest frame; slow viewers skip frames instead of queueing them. Capture runs only while a viewer is connected.

One WebSocket carries frames to the browser and touches back, so authorization happens once per session and taps have low latency. The protocol is a small stdlib implementation: text control messages and binary JPEG frames, a 4 KiB client message limit, periodic pings, and at most four viewers.

Rejected: continuous `ffmpeg` (constant CPU while watching), MJPEG over HTTP with separate tap requests (per-request authorization and no presence signal for taps), WebP (about 350 ms per frame).

### Touch injection

The service finds the direct-touch evdev device that reports multi-touch positions, maps screen pixels to its axis ranges, and writes slot-0 multi-touch events plus `BTN_TOUCH` and single-touch axes, as the Goodix driver does. `qidiclient` acts on the final state of each batch of queued events, so a press released within the same batch is lost; the service holds each press at least 80 ms and starts a press at least 50 ms after the previous release. Only the viewer that started a press can move or release it. A release is sent whenever a pressing viewer disconnects or the service stops. The browser gates control behind an explicit confirmation; view-only is the default for every new session.

### Service isolation

The unit runs as `qidi` with supplementary groups `video` and `input`, with `NoNewPrivileges`, a read-only system and home, private `/tmp`, a lower CPU priority, and a CPU quota. It runs Moonraker's virtualenv Python for Pillow. It binds only `127.0.0.1:7130`. The service rejects WebSocket handshakes whose `Origin` host differs from the request host, so other web pages cannot drive the screen through a visitor's browser. Missing devices or Pillow are reported to the viewer instead of crashing the service.

### Authorization through nginx and Moonraker

nginx routes `/tltg-screen/` to the service after an `auth_request` subrequest to Moonraker's `/access/user`, forwarding the client address and the connection's `token` query value. The card obtains a Moonraker one-shot token through Fluidd's authenticated client before connecting. Trusted LAN clients pass by address; with logins enforced, the one-shot token proves the Fluidd session. No credentials are stored by the service.

### Lifecycle

Four guarded host operations, always selected regardless of optional OS optimization policy:

1. The systemd unit file, created when absent. Apply reloads systemd, enables the unit, and restarts it. Restore disables and stops it before removing the file, then reloads systemd. The unit carries a `ConditionPathExists` on the server, so restarting it before the server exists, or after the server is removed, is a clean no-op.
2. The server script, created when absent. Apply and restore restart the unit.
3. The nginx site route, inserted once before the stock `/webcam/` location of the recognized site. Apply and restore restart nginx.
4. The Fluidd bundle steps, added to the existing Fluidd bundle patch: the card in the default dashboard layout (collapsed), its component registration, and the component itself. Fluidd's saved-layout merge appends new default cards to existing layouts and drops unknown ones, so existing dashboards gain the card and a restored stock bundle drops it.

Created files are recognized by a first-line marker so later package versions replace earlier ones; anything else at those paths is preserved and recorded as unsupported. An unrecognized nginx site is preserved the same way; the card then reports that the screen is unavailable.

## Risks / Trade-offs

- CPU contention with Klipper while watching an animating screen → change-driven encoding, frame cap, `Nice`, and a CPU quota.
- A future firmware could move the display to DRM planes or change the input device → the service detects geometry and devices per session and reports what is missing instead of guessing.
- Remote taps during a print are real presses → view-only by default, explicit confirmation, and the same reach as Fluidd itself.
- nginx restarts on install and restore briefly drop Fluidd connections.
