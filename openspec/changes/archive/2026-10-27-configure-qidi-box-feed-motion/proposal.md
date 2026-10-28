## Why

QIDI Box loads and unloads use fixed vendor motion. Operators can't shorten tool changes, push faster to near the toolhead, or tune the final approach to the toolhead filament switch for their filament and PTFE path.

The vendor load already pushes filament through three stages: 550 mm at 85 mm/s, 380 mm at 65 mm/s, then up to 240 mm at 10 mm/s until the toolhead switch trips. On slot 2, the switch tripped after about 1005 mm, so roughly the last 75 mm run at 10 mm/s. The unload is a two-stage retract to the hub sensor. Live traces on `.07.01` show that a Python wrapper on each slot's multi-step home method receives this profile and can replace it, and that the vendor flow completes normally with the replacement (`openspec/observations/qidi-box/hardware-and-protocols.md`).

## What Changes

- Every Box load pushes fast to a configurable distance near the toolhead switch, then approaches at a configurable speed until the switch trips. Operators set the fast distance, the speed of each fast stage, the approach speed, and load acceleration, plus unload stage speeds and acceleration, through saved variables and a `TLTG_BOX_MOTION` command. Absent settings keep vendor motion.
- Settings are checked as a whole profile, including any vendor values they mix with. A profile that fails falls back to vendor motion entirely, and the operator is told why.
- The integration wraps only the vendor's three-stage load home and two-stage unload home wherever QIDI's Box code provides them and the calls match the traced shape. Vendor flow control is unchanged: task queue, heating, the load pre-stage, cut, extruder bite, purge, wipe, retries, error codes, RFID, feed assist, and status.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `optimized-printer-behavior`: QIDI Box load and unload stages become operator-configurable within validated limits, globally and per slot, with a Fluidd panel.
- `installer-lifecycle`: only if the packaged Klipper extra needs lifecycle behavior beyond existing package-owned modules.

## Impact

- New Klipper extra under `installer/klipper/tltg/` and a config section under `installer/klipper/tltg-optimized-macros/`, with `installer/package.yaml` metadata.
- `openspec/observations/qidi-box/topology-and-control.md` "Repository-controlled integration boundary", which says repository code doesn't tune compiled feeder motion.
- `README.md` for the settings, and `CHANGELOG.md` with a package version bump.
- No slicer G-code, `config/box.cfg`, `config/printer.cfg`, stock-mapped macro, or vendor binary changes.
