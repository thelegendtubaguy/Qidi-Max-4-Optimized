# QIDI Box hardware and protocol observations

Evidence qualifiers are defined in `openspec/observations/README.md`. These observations apply to QIDI Max 4 firmware `01.01.06.04`. Hardware identifiers are redacted; stock pin names and protocol fields are retained.

## Slot hardware

| Slot | Runout | Step | Direction | Enable | White LED | Red LED |
|---:|---|---|---|---|---|---|
| `0` | `mcu_box1:PA0` | `mcu_box1:PC14` | `mcu_box1:PC13` | `!mcu_box1:PC15` | `mcu_box1:PA1` | `mcu_box1:PA2` |
| `1` | `mcu_box1:PB3` | `mcu_box1:PB9` | `mcu_box1:PB8` | `!mcu_box1:PC0` | `mcu_box1:PB4` | `mcu_box1:PB5` |
| `2` | `mcu_box1:PA13` | `mcu_box1:PC12` | `mcu_box1:PC11` | `!mcu_box1:PD2` | `mcu_box1:PA14` | `mcu_box1:PA15` |
| `3` | `mcu_box1:PA7` | `mcu_box1:PC8` | `mcu_box1:PB2` | `!mcu_box1:PC10` | `mcu_box1:PC4` | `mcu_box1:PC5` |

Shared stepper config:

| Key | Value |
|---|---:|
| `rotation_distance` | `13.6` |
| `microsteps` | `16` |
| `step_pulse_duration` | `0.000000100` |

`box_extras` pins:

| Key | Value |
|---|---|
| `b_button_pin` | `^mcu_box1:PB1` |
| `b_endstop_pin` | `mcu_box1:PA9` |
| `e_endstop_pin` | `mcu_box1:PA10` |

- **Runtime-confirmed (2026-10-25, firmware `01.01.07.01`, two USB Boxes):** `multi_color_controller.box.b_endstop_state` reported `0` with filament actuating the hub sensor and changed to `1` after the operator removed the filament. The operator observed the hub's blue LED on without filament and off when filament actuated the sensor, including a removal/reinsertion check. This establishes active-low filament-presence semantics for that status field on the observed setup. The captured hub pin was `mcu_box2:PA9`; the hub pin configuration and `box_extras.so` matched stock, while feeder tuning was modified.
- **Runtime-confirmed (same check):** `/printer/query_endstops/status` reported `b_endstop: open` both with filament actuating the hub sensor and after removal, despite the controller status changing from `0` to `1`. That endpoint's label did not distinguish filament presence in this capture; use the controller field for the observed hub state. The cause of the reporting discrepancy remains **unresolved**.

## Heater, sensors, fans, and RFID pins

| Component | Stock value |
|---|---|
| Box heater pin | `mcu_box1:PA3` |
| Heater sensor | `AHT20_F`, `i2c3`, address `56`, MCU `mcu_box1` |
| PID | `63.418 / 1.342 / 749.125` |
| Heater range | min `-100`, max `100`, target max `90` |
| Verify heater | max error `400`, gain time `600`, `is_box_heater=True` |
| NTC sensor A/B | `NTC 100K MGB18-104F39050L32`, pins `PC1` / `PC2`, range `-100..130` |
| Heater fan A/B | pins `PA4` / `PA5`, threshold `35`, idle timeout `60` |
| Controller fan | pin `PA6`, heater `heater_box1`, steppers `slot0..slot3` |
| RFID chip selects | `PC6`, `PC7` |

## Compiled stepper constants

| Constant | Value |
|---|---:|
| `DISABLE_DELAY` | `0.05` |
| `HOMING_START_DELAY` | `0.001` |
| `ENDSTOP_SAMPLE_COUNT` | `4` |
| `ENDSTOP_SAMPLE_TIME` | `0.000015` |

## Harness-recovered primary motion

| Operation | Distance | Speed | Acceleration | Notes |
|---|---:|---:|---:|---|
| slot preload home | `3000` | `80` | `50` | endstop flag `False` |
| slot preload park | `-260` | `80` | `50` | after preload home |
| slot unload/eject | `-3000` | `100` | `50` | endstop flag `True` |
| extruder load home | `3000` | `85` | `50` | endstop flag `False` |
| post-load dwell | n/a | n/a | n/a | `0.05 s` |
| unload phase 1 | `-350` | `65` | `100` | double-step path |
| unload phase 2 | `-1150` | `85` | `100` | double-step path |
| unload recovery | `-1500`, twice | `65` | `50` | endstop flag `True` |
| hub sync defaults | `18` | `40` | `40` | `hub_load_length`, `hub_load_v`, `hub_load_a` |

Visible toolhead script fragments include unload pre-positioning at `Y380`, `X3`, `X3 Y17`, `M400`, and shake routines with explicit relative extrusion and high-speed X/Y wiping. Exact live branch execution is not proven by static fragments.

### Feeder motion settings

**Static-recovered.** `box_stepper.so` names these motion settings:

| Group | Keys |
|---|---|
| Extruder load | `extruder_load_length_1`, `extruder_load_length_1_speed`, `extruder_load_length_1_accel` |
| Extruder unload | `extruder_unload_length_1` and `_2`, with `_speed` and `_accel` per phase |
| Slot load | `slot_load_length_1..4`, with `_speed` and `_accel` per phase |
| Slot unload | `slot_unload_length_1`, with `_speed` and `_accel` |
| Multi-slot load | `multi_extruder_load_length_1..3`, `multi_extruder_load_speed_1..3`, `multi_extruder_load_accel` |
| Multi-slot unload | `multi_extruder_unload_length_1..2`, `multi_extruder_unload_speed_1..2`, `multi_extruder_unload_accel` |
| Hub sync | `hub_load_length`, `hub_load_v`, `hub_load_a` |
| Retry and detection | `retry_num`, `load_retry_num`, `auto_reload`, `auto_reload_detect`, `auto_detect_filament`, `auto_detect_filament_advance`, `endstop_triggers`, `disable_delay`, `home_start`, `home_wait`, `motor_disable` |
| Toolhead shake | `shake_toolhead`, `shake_for_load_toolhead`, `shake_for_unload_toolhead`, `shake_for_enter_extruder` |

Where the values come from on `.07.01`:

- **Runtime-confirmed (2026-10-26, vendor `box_stepper.so`, a log-only wrapper on the live `box_extras` instance):** load and unload ask `box_extras.get_value_by_key(name, default)` for each value at the time of the operation, passing the compiled default. The lookup returns the live `[save_variables]` value when the key is saved and the default otherwise. `SAVE_VARIABLE` therefore reaches the next operation without a restart. No motion key is saved on a stock printer.
- **Runtime-confirmed:** patching those compiled defaults changed live load motion. A printer patched this way (load defaults `120`/`120`/`20` mm/s with a `105` mm final stage, unload `120`/`100` mm/s) was restored to the vendor file on 2026-10-26. With the `105` mm final stage, the three-stage home returned without reaching the toolhead switch and the load entered its `load_retry_num` / `diff_mv` retry path.

Keys read by a vendor slot 2 load and unload, in call order, with the defaults passed:

| Step | Keys and defaults |
|---|---|
| Load pre-stage | `extruder_load_length_1` `3000`, `_speed` `85`, `_accel` `50` |
| Load three-stage home | `multi_extruder_load_length_1..3` `550`/`380`/`240`, `multi_extruder_load_speed_1..3` `85`/`65`/`10`, `multi_extruder_load_accel` `100` |
| Load hub sync | `hub_load_length` `18`, `hub_load_v` `40`, `hub_load_a` `40` |
| Unload extruder retract | `exl_1` `30` at `exl_1_speed` `300`, `exl_2` `120` at `exl_2_speed` `600`; runtime-confirmed as `G1 E-30 F300` then `G1 E-120 F600`, each followed by `M400`, with no toolhead-switch stop. On slot 2 (2026-10-27), polling `motion_report` and the switch showed it clearing 34 mm into the retract, about 4 mm into the second move |
| Unload pre-stage | `extruder_unload_length_1` `-1500`, `_speed` `65`, `_accel` `50` |
| Unload two-stage home | `multi_extruder_unload_length_1..2` `-350`/`-1150`, `multi_extruder_unload_speed_1..2` `65`/`85`, `multi_extruder_unload_accel` `100` |
| Unload after home | `extruder_unload_length_2` `-260`, `_speed` `80`, `_accel` `50` |

Whether the load pre-stage moves, and what stops it, is **unresolved**; a 2026-10-24 position trace (below) shows about +317 mm and −31 mm before the three-stage move.
- **Config-confirmed:** stock `config/box.cfg` sets none of these settings. `box_config.py` builds each `[box_stepper slotN]` section from pins and step settings only (`runout_pin`, `step_pin`, `dir_pin`, `enable_pin`, `white_pin`, `red_pin`, `step_pulse_duration`, `rotation_distance`, `microsteps`) and passes the `[box_config boxN]` section to `BoxExtruderStepper` separately.
- **Static-recovered:** the only motion timing constants compiled as doubles are `0.05` (`DISABLE_DELAY`), `0.001` (`HOMING_START_DELAY`), and `0.000015` (`ENDSTOP_SAMPLE_TIME`).

**Runtime-confirmed (2026-10-24, two USB Boxes).** Supplying settings through generated config does not change the main load. An instrumented `box_config.py` copied settings from `[box_config boxN]` into each generated `[box_stepper slotN]` section:

| Change | Result |
|---|---|
| `extruder_unload_length_1_speed` added directly to `[box_config box0]` | Klipper refused to start: invalid option. |
| Load speeds (`slot_load_length_1..3_speed`, `multi_extruder_load_speed_1..2`) forwarded at `200`, `350`, and `50` | The values reached the slot config, but load motion did not change. The three load stages stayed near `85`, `62`, and `9.5` mm/s. |
| `slot_unload_length_1_speed: 200` forwarded | Slot MCU traffic during unload roughly doubled (`492` → `1032` B/s), so this override probably took effect. Traffic is not a direct speed measurement. |
| `[box_autofeed] v_feed` `100` → `350` | Feed-assist traffic rose (`767` → `1100` B/s). This is feed assist, not the main load. |
| `multi_extruder_load_accel: 150` | Inconclusive: the sampled window was mostly constant-speed motion. |

The captures are `klippy.capture`, `klippy.speed200`, `klippy.accel150`, and `klippy.vfeed`. In `klippy.vfeed`, the `50` load speeds were loaded at `05:00:32` and the `350` speeds at `05:11:05`.

**Static-recovered (`.07.01`).** Load and unload reach their moves through these calls:

| Operation | Call path |
|---|---|
| Three-stage load to the toolhead | `extruder_load_single_func` → `do_home_three_steps` → `do_move_triple_steps` |
| Two-stage unload from the toolhead | `extruder_unload_single_func` → `do_home_double_steps` → `do_move_double_steps` |
| Other load and unload branches | the same outer functions, through `do_home` and `do_move` |
| Slot unload and eject | `slot_unload_single_func` → `do_home` |
| Automatic slot load at insertion | `slot_load` → `do_home`, `do_move` |

**Runtime-confirmed (2026-10-26, vendor `box_stepper.so`, slot 2):** these methods are looked up by name at call time. Python wrappers set on each `box_stepper slotN` instance and on the `box_extras` instance were called by vendor loads and unloads. Every slot holds the same `box_extras` object.

| Call | Arguments | Observed |
|---|---|---|
| `do_home_three_steps` | `endstops, l1, l2, l3, v1, v2, v3, accel, False`; endstops `[(MCU_endstop, 'e_endstop')]` | Calls `do_move_triple_steps(v1, l1, v2, l2, v3, l3, accel)` with its own arguments. Returns `True` when the toolhead switch is reached. |
| `do_home_double_steps` | `endstops, l1, l2, v1, v2, accel, True`; endstops `[(MCU_endstop, 'b_endstop')]` | Calls `do_move_double_steps(v1, l1, v2, l2, accel)` with its own arguments. Returns `True` when the hub sensor is reached. |

`do_move_*_steps` returned without slot travel; the travel happens inside `do_home_*_steps`. Replacing the arguments of `do_home_*_steps` in a wrapper changed the motion, and the vendor flow, purge, and park completed normally:

| Run | Load stages | Load home | Unload stages | Unload home |
|---|---|---|---|---|
| Vendor | `85`/`65`/`10` mm/s | about `21 s` | `65`/`85` mm/s | about `14 s` |
| Wrapper substitution | `85`/`85`/`20` mm/s | `1004.9 mm` in `16.5 s`, `True` | `65`/`100` mm/s | `-799.0 mm` in `12.4 s`, `True` |

Travel is the slot stepper's MCU position change across the call. The outer functions also handle sync, scripts, and recovery, and `do_home`/`do_move` also serve slot auto-load and recovery, so only the multi-step methods are Box-only load and unload moves.

- **Static-recovered:** `box_stepper.so` references `filament_switch_sensor filament_switch_sensor`, `runout_helper`, `filament_present`, `drip_move`, and `drip_completion`. These suggest the load polls the toolhead switch from the host, but the live three-stage home receives an `MCU_endstop` named `e_endstop` (table above). Which mechanism stops the motion is **unresolved**. `do_move_triple_steps` carries the messages `l1 is too short to reach v1.` and `l2 is too short for v1->v2 change + v2->v3 change.`, so the three-stage profile has length and speed constraints between stages.
- **Runtime-confirmed (2026-10-26):** the motion settings are not plain Python attributes on `BoxExtruderStepper` instances. A boot-time dump showed only `slot_not_unload` and the `shake_for_unload_toolhead` script.

Harness branch observations:

- `slot_load()` and `EXTRUDER_LOAD` ran their home branch when fake `b_endstop=1` and skipped it when `b_endstop=0`; fake `e_endstop` did not change those observed outcomes.
- `EXTRUDER_UNLOAD` ran its captured unload branch when fake `b_endstop=0` and skipped it when `b_endstop=1`.
- `SLOT_UNLOAD` ran the same slot-runout home in all harnessed states.
- `SLOT_PROMPT_MOVE` produced no captured motion.
- Live loaded state reported `b_endstop=0`, `e_endstop=1`; fake predicates must not be promoted to live semantics without controlled motion evidence.

Harnessed `slot_sync()` saved the owning stepper's slot name regardless of its `value` argument. Non-extruder sync looked up the hub defaults above; no real synchronized movement was proven. `init_slot_sync()` overwrote fake prior sync state, but the harness lacked the full multi-stepper graph. `sync_unbind_extruder()`, `switch_next_slot()`, prompt movement, and auto-reload movement remain unresolved.

### Live feed path

**Runtime-confirmed (2026-10-26, firmware `01.01.07.01`, two USB Boxes).** The operator described the slot path as: slot inlet and runout sensor, hub filament sensor (`b_endstop`, published as `multi_color_controller.box.b_endstop_state`), then the hub buffer, a spring-loaded tension mechanism with its own second sensor, then the PTFE tube to the toolhead filament switch `!THR:PA0`. The buffer meters feed during printing: the Box feeds into tension and the spring's release trips the buffer sensor to request more feed. The hub filament sensor precedes the buffer sensor.

- Inserting filament runs an automatic slot load: the Box pulls to the hub filament sensor, backs off, re-approaches the sensor, backs off, and parks behind it (`b_endstop_state=1`).
- After that load, `box_stepper slot2`'s stepper stayed attached to a motion queue that was neither the toolhead's nor the extruder's, with the motor disabled. A Klipper service restart left it with no queue. The vendor attaches slot steppers to its own queue for box-only moves and to the extruder queue only while synchronized.
- `[MCB] limit_a_event` callbacks (`[box_autofeed]` `limit_pin`) changed state during the box-only motion below. Attributing them to the buffer sensor rests on the operator's description and timing correlation.

### Cold feed measurements

**Runtime-confirmed (2026-10-26, slot 2, `rotation_distance 13.6`).** A development test drove the slot stepper on a private motion queue from the auto-load park position to the toolhead switch and back, polling the switch between 2 mm increments, with the extruder stationary and the nozzle cold.

| Fast / return speed | Increment speed | Toolhead switch tripped at | Load | Return |
|---:|---:|---:|---:|---:|
| `40 mm/s` | `10 mm/s` | `1272 mm` (within −2 mm) | `259.7 s` | `33.0 s` |
| `100 mm/s` | `30 mm/s` | `1256 mm` (within −2 mm) | `29.0 s` | `15.0 s` |

- `b_endstop_state` read `1` at park, `0` at the toolhead trip, and `1` after returning to park on both runs.
- The limit input changed state for about 40 mm of travel about 400–440 mm from park on both runs. On the 40 mm/s run it also changed state about 30 mm before the toolhead trip and reverted when the return began. Whether buffer take-up explains the 16 mm difference between runs is **unresolved**.
- No `MCB_AUTO_START` occurred, and the slot MCU's step position matched host step generation after every move.

**Runtime-confirmed (2026-10-24, `.07.01`, instrumented `box_config.py` position trace of a vendor slot 2 load and unload).** After heating, the slot moved about +317 mm, −31 mm, then about +997 mm on its own queue at an average of about 50 mm/s, and backed off 2.7 mm. It then followed the extruder queue for `G1 E25`, `E5`, `E10`, `E5`, `E20` before being detached for the `E100` purge. The unload followed the extruder for `G1 E-30` and `E-120`, then retracted about 1055 mm on its own queue. Positions came from 50 ms polling, so speeds are approximate.

### Retraction past the slot inlet

**Runtime-confirmed (2026-10-30, `.07.01`, two USB Boxes, slot 0, `TLTG_BOX_SLOT_JOG` on a private motion queue, idle, nozzle cold).** Slot 1B was loaded to the toolhead, so the hub sensor stayed occupied throughout. Slot 0 started from where it rested with filament at its inlet; its distance from park was not measured.

- Slot 0 retracted in 10–50 mm moves at 20–40 mm/s. The operator saw its filament move back, and `runout_button` stayed `0` until it read `1` after about 1860 mm in total.
- At that point the operator found the filament tip out of the slot feeder. Driving the slot 100 mm forward in 10 mm moves did not return filament to the inlet sensor.
- The slot inlet clearing while idle started no vendor task, and saved Box state was unchanged.
- Pushing the filament back into the inlet by hand ran the vendor's normal automatic slot load.
- **Config-confirmed:** QIDI's `klippy/extras/stepper_enable.py` sets `ENABLE_DELAY_TIME = 0.300`. `motor_enable(print_time)` schedules the enable pin `0.3 s` before `print_time` and logs `ENABLE delay: stepper=<name> enable=<time> move=<time>`.

## Cleanup scripts

`CLEAR_FLUSH`:

```gcode
M204 S10000
G1 X180 F10000
MOVE_TO_TRASH
```

`CLEAR_OOZE`:

```gcode
M204 S10000
G1 X163 F8000
G1 X145 F5000
G1 X163 F8000
G1 X145 F5000
G1 X175 F6000
G1 X163
G1 X175
G1 X163
G1 X175
G1 X163
```

`flush_all_filament()`:

```gcode
G1 E25 F300
```

Recovered cutter strings include `CUT_FILAMENT_1`, `MOVE_TO_TRASH`, `M83`, and `G1 E-60 F300`. Exact cutter branching remains vendor-owned.

- **Static-recovered (`.07.01`):** `CLEAR_FLUSH` and `CLEAR_OOZE` strings remain only in `box_extras.so`; `multi_color_controller.so` and `box2base.so` no longer contain them. The stock `filament.cfg` adds `DROP_TRASH` and `WIPE_NOZZLE_DROP` with identical bodies: `MOVE_TO_TRASH`, `M204 S5000`, the `CLEAR_OOZE` X145–X175 strokes with slower `F3000`/`F2000` passes, `G1 X180 F8000`, then `Y380`, `X116`, `G4 P2000`, `Y403 F3000`, and `MOVE_TO_TRASH`. Embedded script strings place `DROP_TRASH` after purge extrusion (`multi_color_controller.so`, `box_extras.so`, `box2base.so`) and `WIPE_NOZZLE_DROP` after unload and before the nozzle-cleaning completion message (`multi_color_controller.so`).
- **Static-recovered (`.07.01`):** stock `filament.cfg` also adds `MOVE_ANOTHER_POINT_CHANGE_FILAMENT` (trash position, then `X30 Y125`) and `TRY_INTO_EXTRUDER` (fast XY strokes with `E3` extrusion near X30, containing `G1 P1000`, which Klipper's `G1` ignores). Only `box2base.so` references them; one recovered script string contains `CUT_FILAMENT_1`, `MOVE_TO_TRASH`, `MOVE_ANOTHER_POINT_CHANGE_FILAMENT`, `G1 E10 F300`, and `G1 E-80 F600` in that order.

## Autofeed and anti-wrap protocol

Stock-visible `[box_autofeed]` values:

| Field | Module default | Stock value |
|---|---:|---:|
| `limit_pin` | required | `^!mcu_box1:PB0` |
| `debounce_us` | `200000.0` | `200000.0` |
| `limit_polarity` | `0` | `0` |
| `default_ticks` | `8400` | `8400` |
| `v_feed` | `2000` | `100` |
| `lmax` | `10000` | `120` |
| `dir` | `1` | `0` |
| `a_feed` | `0.0` | `0.0` |

These values configure feed assist, not compiled primary load/unload motion.

Registered commands:

```text
MCB_CONFIG MCB_QUERY SET_LIMIT_A MCB_AUTO_START MCB_AUTO_ABORT
```

MCU command formats:

```text
mcb_config oid=<oid>
mcb_config_stepper oid=%c stepper_oid=%c
mcb_query oid=%c clock=%u rest_ticks=%u retransmit_count=%c invert=%c
mcb_auto_start oid=%c v=%u a=%u lmax=%u dir=%i enable=%i invert=%i
mcb_auto_abort oid=%c
set_limit_a oid=%c state=%c
```

Response names are `MCB_STATE`, `MCB_DONE`, and `MCB_ERROR`.

Harness payload ordering:

```text
mcb_config_stepper: [oid, stepper_oid]
mcb_query: [oid, clock, rest_ticks, retransmit_count, invert]
mcb_auto_start: [oid, velocity_steps, acceleration_steps, max_length_steps, direction, enable_pin, invert]
mcb_auto_abort: [oid]
set_limit_a: [oid, state]
```

Velocity, acceleration, and max length are converted from visible millimeter units through step distance. The fake setup encoded `!PC15` as pin `47`, invert `1`.

Runtime fields included `limit_a_state`, `wrapping_num`, `bind_stepper`, `active_slot`, and selected stepper/MCU caches. `QDE_004_013` and a pause-command string associate this path with wrapped-filament handling; callback payloads, event-count gate, and physical anti-wrap behavior are unresolved.

## RFID protocol

`box_rfid.so` initializes each reader with:

```text
query_fm17550 oid=<oid> rest_ticks=0
config_fm17550 oid=<oid> spi_oid=<spi_oid>
```

The query is registered `on_restart=True`. Read command and response formats:

```text
fm17550_read_card_cb oid=%c
fm17550_read_card_return oid=%c status=%c data=%*s
```

Recovered fields:

| Field | Value |
|---|---:|
| `max_read_time` | `30.0 s` |
| initial `rfid_read_attempts` | `0` |
| initial `rfid_read_start_time` | `0` |
| `get_message_count` | `1` |
| initial `had_get_value` | `False` |

Idle commands were accepted without a visible result and did not clear stored material metadata. Raw valid-tag bytes, status interpretation, reader ordering, tag-to-metadata decoding, and the four-logical-reader/two-chip-select relationship remain unresolved.

A fake `SLOT_RFID_READ` path emitted `QDE_004_011` when loaded, but live loaded-slot commands were accepted without that error. Live evidence outranks the fake predicate.
