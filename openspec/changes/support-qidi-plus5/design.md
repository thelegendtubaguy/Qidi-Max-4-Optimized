## Context

Evidence lives in `openspec/observations/qidi-platform.md` under QIDI Plus 5. In short:

- **Same as the Max 4:**
  - Board images: MCU, THR, BOX, BOX485, and BUFFER in `01.01.02.01` are byte-identical to Max 4 `01.01.07.01`. A stock Plus 5 runs mainboard `02.01.01.12` (STM32F407) and THR `02.02.01.08` (STM32F103xE on `/dev/ttyS4`).
  - Host: RK3308BS board with 486 MB RAM, the same partition names, and kernel 5.10.160 from the same builder and toolchain. The build is `#3 … Aug 23`, not the Max 4's `#4 … Sep 3`.
  - Host defects: the unauthenticated `adbd` root shell on port 5555 and the `rockchip.service` `rk3208` failure that leaves `/` mounted `sync`.
  - Klipper: 228 of 234 `klippy` files, Fluidd, the Klipper and Moonraker virtualenvs, `box.cfg`, the `[box485]` stack, and the SOC package's maintainer scripts. Those scripts also wipe the config directory on update, as on the Max 4.
- **Different:**
  - `printer.cfg`:
    - X/Y: open-loop TMC2240 with sensorless homing.
    - Travel and Z: travel X −7–326 and Y −5–340, Z 310, Z `rotation_distance` 4.
    - Extruder: direction inverted, current doubled.
    - THR pins: filament switch and hotend fan move to other THR pins.
    - Limits: `max_velocity` 600 and `max_accel` 20000.
  - Stock macros: homing, `M84`, park, cutter, wiper, and fans.
  - Klipper files: `print_stats_manager.py` without the `tpwmthrs` reset, `stepper_enable.py` without the 0.3 s early enable, and changed `box_extras.so` and `box_stepper.so`.
  - Screen and camera: a 480×800 framebuffer behind a landscape-mounted screen, and an icSpring camera at 640×480.
  - AI detection: none.
  - Slicer start G-code: different, using `M1006 Z`.
- **Stock Plus 5 firmware history:** `01.01.01.06` and `01.01.01.07` ship no BOX485 or BUFFER image. `01.01.02.01` is the current release.

## Goals / Non-Goals

**Goals:**

- One installer that admits Plus 5 `01.01.02.01` with its own baseline, and leaves Max 4 behavior unchanged.
- The same optimized macro names on both printers, with Plus 5 internals derived from QIDI's Plus 5 macros.
- No Max 4-specific hardware assumption reaches a Plus 5: closed-loop commands, the X/Y belt-speed cap, zram modules, or THR and Box bootloader admissions.

**Non-Goals:**

- Plus 5 firmware `01.01.01.06` and `01.01.01.07`. Owners update to `01.01.02.01` first.
- New optimizations specific to the Plus 5. The first release ports existing behavior; Plus 5 tuning follows measurement.
- RS-485 Box support beyond what the Max 4 already has.

## Decisions

**D1. Develop on a feature branch, and admit only after a hardware pass.** Admission, stock snapshot, patch variants, and the Plus 5 macro folder land together, because a firmware listed in `printers:` is installable. Work that can't run without the printer stays on the feature branch until the hardware tasks pass. Work that is printer-neutral, such as screen rotation, can merge to `dev` earlier.

**D2. The baseline comes from `Qidi-Plus5-Defaults` commit `25001402`.** The snapshot is the `config/` tree of the `01.01.02.01` payload, laid out like `installer/stock/qidi-max4-defaults/`. Patch variants are computed against it. Where a Plus 5 value differs from the Max 4 value a patch expects, the patch either gets a Plus 5 variant or doesn't apply to the Plus 5. It never matches on the Max 4 value.

**D3. Gate on hardware facts, not on the printer name, where a fact exists.**
- The step-loss monitor already stays inert without `cl_interface`.
- zram already loads only on a declared kernel build string.
- THR and Box fixes already require a recognized bootloader.
- The 565 mm/s cap comes from the closed-loop motors' belt-speed limit, so its patch variants are Max 4-only. The Plus 5 keeps QIDI's 600 unless measurement says otherwise.
- The mainboard closed-loop fix is offered only on printers with closed-loop X/Y.

**D4. Plus 5 homing ports QIDI's sequence first.** That sequence is: both drivers at 0.9 A, `G28.6245197` per axis, Y-X-Y, 10 mm backoff, and a 2 s settle. The first port keeps every current and dwell. Trimming dwells, as the Max 4 work did (`G4` before speed), waits for timed stock and optimized homing on the printer. Sensorless homing depends on current and speed, so no speed or current change ships without repeated homing checks.

**D4a. What the Plus 5 port changes from QIDI's macros.**
- `G28 X`, `G28 Y`, and `G28 Z` home that one axis with the same per-axis steps. QIDI's override ignores them, and the common macros expect them to work.
- Homing clears the bed mesh, as on the Max 4. It doesn't call QIDI's undefined `BEEP`.
- The cut drops QIDI's 2 s exit dwell, as on the Max 4.
- Every other coordinate, speed, current, and dwell is QIDI's Plus 5 value. The waste-chute final approach uses the shared `trash_final_approach_speed_xy`.
- Of the printer.cfg patches, the Plus 5 gets Z homing retract 5 mm, the error cancel macro, the hotend-fan tachometer interval, and quiet timelapse frames. Its Z homing is the same load-cell probe as the Max 4's.

**D4b. Slicer packs live in `plus5/` subfolders.** The Max 4 packs stay where operators' links point. The Plus 5 packs follow QIDI's Plus 5 profiles:
- Temperature compensation uses `M1006 Z`.
- The prime-line fallback is X180 to X140.
- Filament changes use QIDI's Plus 5 wipe.
- They leave out the Max 4 OrcaSlicer pack's `M106 P4` polar-cooler line until the Plus 5 is known to have one.

**D5. The screen card rotates in the service.** The service knows the framebuffer's geometry and the touchscreen's axis ranges. A portrait framebuffer on a printer whose UI is landscape is rotated before encoding. Taps are mapped back through the same rotation, and the touchscreen's own axis ranges decide whether the touch coordinates are portrait or landscape. Any portrait framebuffer is turned by one constant, `PORTRAIT_UI_ROTATION`. Its 90° clockwise value is a guess until 2.3 observes the direction, and the tap mapping assumes the touchscreen reports framebuffer coordinates.

## Data to collect on a running Plus 5

All read-only unless noted. Results go into the Plus 5 observations.

| Question | How | Unblocks |
|---|---|---|
| Kernel `#3` against the zram modules built for `#4` | `boot` partition image and `/proc/kallsyms` (sudo) | zram on the Plus 5 |
| UI rotation direction | capture `/dev/fb0` while the screen shows a known page | screen card |
| Touchscreen axis ranges and orientation | `EVIOCGABS` on `event0`; record one tap at a known corner | screen card taps |
| THR bootloader build | `flash_thr_firmware.py snapshot` (stops Klipper and the screen) | THR FIFO fix |
| Box bootloader build, if a Box is attached | `flash_box_firmware.py snapshot` | Box shutdown fix |
| Stock `printer.cfg` against the live file | diff, with serials redacted | patch variants, preflight |
| Stock homing duration and reliability | timed `G28` repeated, `klippy.log` | D4 |
| Cutter, wiper, chute, and park clearances | watch stock `CUT_FILAMENT`, wipe, and chute moves | macro folder |
| Load cell responds like the Max 4 | `WEIGHTING_DEBUG_QUERY`, `PROBE_ACCURACY` | probe diagnostics |
| Idle and printing host load, memory | the main-thread and memory measurements used on the Max 4 | zram need, priorities |
| Fan and chamber objects | `printer/objects/list` | cooling and exhaust guard |
| Box behavior with Plus 5 `box_extras.so` | harness first, then a load, unload, and tool change if a Box is attached | Box modules |
| Mainboard and THR board revisions | photos of board silkscreen | observations only |

## Risks / Trade-offs

- **[`box_extras.so` changed with the same strings]** → Package Box modules wrap its methods. Compare both binaries in the vendor harness before admission. Any wrapped method whose behavior differs gets a Plus 5 decision.
- **[Sensorless homing is sensitive to current and speed]** → Port stock values unchanged (D4).
- **[A patch that matches by section and option can still mean something else on the Plus 5]** → Variants are computed from the Plus 5 snapshot (D2), and the lifecycle matrix runs every patch against both printers' snapshots.
- **[One project printer]** → Admission waits for the hardware pass. Owner reports from issue 190 cover only read-only data.

## Open Questions

- Does the THR on shipping Plus 5s carry a bootloader build already admitted for the Max 4?
- Does Plus 5 `box_stepper.so`'s `extruder_load_length_2`/`_3` change load lengths that the package's Box feed-motion settings assume?
- Is the Plus 5's toolhead geometry, which the cold cut and the cutter position depend on, the same as the Max 4's?
- Is there a Plus 5 rear-bed cable-collision risk like the Max 4's, which the optimized rear-bed scrape avoids?
- Does an idle Plus 5 without AI detection need zram at all?
- Does the icSpring camera link `index0` to the stream node the way the Max 4 camera does?
