# QIDI Box evidence and unresolved behavior

Runtime QIDI Box evidence applies to QIDI Max 4 firmware `01.01.06.04`; `01.01.06.05` findings are config-confirmed, harness-recovered, or static-recovered where explicitly labeled. Runtime evidence from `01.01.07.01` is labeled by capture date.

Box MCU firmware identity, command surface, watchdog, and shutdown reasons are recorded in `mcu-firmware.md`. Link-loss behaviour, transport identity, and observability limits are recorded in `link-failures.md`.

## Evidence inventory

| Evidence | Scope | Limitation |
|---|---|---|
| 2026-05-07 live one-Box config and non-motion Moonraker captures | Include graph, saved state, status schema, heater/sensor values, query/RFID/autofeed idle command effects | No feeder motion, valid RFID result, anti-wrap event, retry, or failure path occurred. |
| 2026-06-13 live two-Box topology refresh | Two MCU/Box object graph, `box_count=2`, missing second-Box tool mappings, slot16 fallback | No physical second-Box load/unload operation was captured. |
| Captured `box.cfg`, `box_config.py`, `officiall_filas_list.cfg`, and qidiclient strings | Hardware pins, generated topology, metadata maps, UI/object names, detection/update strings | Strings prove references, not execution. |
| Fake Klipper harnesses for compiled modules | Script fragments, constants, command formats, saved-variable writes, branch candidates | Fake objects can select invalid branches or omit required context. |
| Aarch64 symbols, strings, and disassembly | Function boundaries, ownership, error strings, unresolved target locations | Cython source-level DWARF was absent; instruction flow alone is not a reliable high-level predicate source. |
| `01.01.06.04`/`.05` ARM64 Python 3.9 differential execution | Changed command traces, flow selection, mapping scan, and virtual-SD lookup for identical controlled inputs | Fake Klipper objects do not prove physical outcomes or all native branch predicates. |
| `01.01.06.05` `save_variables.py` source | Missing metadata-key defaults | Persisted runtime values bypass these defaults. |
| `QD_MAX4_BOX_02.03.01.21` and `QD_MAX4_BOX485_02.04.01.01` images, including the embedded zlib `identify` dictionary | MCU part, clock, build constants, full command/response surface, `shutdown()` string ids, USB identity, watchdog setup | Proves presence and ownership, not execution. Handler behaviour is read from disassembly of the addresses the dictionary names. |
| Decompressed Cython literal tables from the retrieved vendor shared objects | `box_stepper` method inventory, G-code fragments, `QDE_004_*` text, config-key names; module ownership of `料盒急停` and `Can not find 485 device` | String presence only. Config keys prove a readable surface, not effective values. |
| 2026-10-22 klippy.log capture of a live box link failure | Failure ordering, per-MCU serial counters, heater and sensor state at failure | The kernel USB record for that window no longer exists, and the EOF line carries no MCU name. |
| 2026-10-24 instrumented `box_config.py` position trace of a vendor slot 2 load and unload | Slot and extruder motion segments, motion-queue attachment, embedded G-code timing | 50 ms position polling; speeds are approximate and one slot was captured. |
| 2026-10-26 cold feed runs on slot 2 with a development feeder test, plus klippy.log | Park-to-toolhead-switch distance, hub and limit-input transitions, slot motion-queue ownership after auto-load | Repository-driven motion, not vendor flows; two runs on one slot, 2 mm resolution. |
| 2026-10-28 `.07.01` `multi_color_controller` import and fake-object eject harness, plus live empty-toolhead ejects of slots 2 and 4 | Flow map, eject flow selection, eject and completion scripts, adapter creation timing | Only flow `4` ran live; the slot 4 eject had a package module dropping the park. |
| 2026-10-29 operator `klippy.log` and `saved_variables.cfg` of repeated external-spool load shutdowns, plus a `.07.01` `multi_color_controller` harness with a two-entry filament database | Load flow filament-ID comparison, unknown-ID failures, external-spool filament updates, shared material database | The writer of the operator's `'None'` was not captured; harness filament entries are synthetic. |

Captured extension modules were aarch64 Cython shared objects with debug-info markers but no useful Cython line/variable DWARF. Static function address/size inventories are intentionally not retained because readable harness/runtime behavior supersedes them.

## Evidence precedence

1. Controlled live before/after state and logs.
2. Captured stock config or generated Python source.
3. Fake-harness scripts, constants, and protocol payloads.
4. Static symbols, names, strings, and disassembly.

A command returning `ok` proves acceptance in that captured state; it does not prove a successful physical operation. An unchanged already-matching state does not prove that a command is generally side-effect free.

## Resolved conflicts

- The 2026-10-22 box loss was not an MCU shutdown. No `MCU 'mcu_box2' shutdown: <reason>` line exists; the failure is a serial EOF followed by exponential-backoff retransmits and a host timeout.
- Box MCU I2C errors do not shut the MCU down. The mainline `I2C NACK` family of `shutdown()` strings is absent from the firmware, and the only two `!!warnning:%s` call sites are I2C paths.
- Box MCU timer lateness does not shut the MCU down. `Timer too close` and `Rescheduled timer in the past` are absent from the compiled `shutdown()` string set.
- The USB Box MCU is Klipper-derived and reports `QIDI_BOX_V2_1.2.1`; `QD_MAX4_BOX485` is a separate non-Klipper image, so observations about one image do not transfer to the other.

- Live loaded-slot RFID commands were accepted without `QDE_004_011`; the conflicting fake-harness guard is not treated as live behavior.
- `slot16` can reach `EXTRUDER_LOAD` when a tool mapping is absent; any special behavior is downstream and remains unresolved.
- **Harness-recovered:** `BOX_PRINT_START` writes saved-variable state; prior uncertainty about the emitted writes is obsolete, while live mutation remains unresolved.
- Generated and runtime sensor names `heater_temp_a_boxN` / `heater_temp_b_boxN` supersede the incomplete `box1_env` inventory.
- Heater target may be active while `dry_state=0`; `heater_generic heater_boxN.target` is the heater-state source.
- The 2026-06-13 two-Box topology supersedes one-Box assumptions about maximum active slots but does not invalidate the earlier loaded-slot state/schema capture.
- **Harness-recovered for `.05`:** `switch_next_slot()` scans `value_t0` through `value_t15` instead of relying on `get_key_by_value(...)`.
- **Harness-recovered for `.05`:** external-spool `LOAD` with slot `16`, filament present, and empty `last_load_slot` selects flow `6` instead of flow `0`.
- **Static-recovered for `.05`:** public Box classes, method signatures, defaults, and recovered `QDE_004_*` code sets are unchanged; this does not establish unchanged internal behavior.

## Unresolved behavior

### Box MCU firmware and link

- Whether a box link loss originates in the box supply or a box firmware stall. The double re-enumeration in the 2026-10-28 capture shows the Box MCU reset; what reset it is open. See `link-failures.md` for the timing evidence that would separate them.
- Which device raised the `Got EOF when reading from device` on 2026-10-22. The timeout names `mcu_box2`, but the EOF line carries no MCU name.
- When the IWDG resets recorded on three Boxes happened, and what preceded them. The firmware keeps reset flags until power-off, so an `IndependentWatchdog` reading dates only from the Box's last power-on. See `mcu-firmware.md`, Reset reason.
- The consumer of the MCU's `!!warnning:%s` output, and therefore whether MCU-side I2C warnings reach any log.
- Whether a non-fatal I2C fault leaves `heater_boxN` supervision to be the only observer of a failed heater sensor.

### Feeder and print start

- Exact live `BOX_PRINT_START` predicates for same-slot reuse, changed slot, unsynced state, cut-before-unload, and direct-feed `slot16`.
- Live `EXTRUDER_LOAD`, `EXTRUDER_UNLOAD`, and `SLOT_UNLOAD` sensor gates, retries, state writes, and failure recovery.
- Exact `.05` `EXTRUDER_LOAD` retry threshold/order around `diff_mv`, `box_autofeed`, `retry_success`, and `limit_a_state`.
- Real slot/extruder synchronization movement, unbind behavior, prompt movement, and `.05` `switch_next_slot()` auto-reload movement after target selection.
- Live task-queue normalization before `_decide_flow_id()`, flow progress semantics, and completion predicates.
- What the `.07.01` load pre-stage (`extruder_load_length_1`) homes against, and whether the three-stage home therefore starts from a repeatable position.
- The cause of the 16 mm difference in park-to-toolhead-switch distance between the 40 mm/s and 100 mm/s cold feed runs.

### RFID and metadata

- Valid QIDI tag payload bytes and `status` interpretation.
- Successful `multi_color_controller.rfid.results` schema.
- Reader order, four-slot-to-two-chip-select multiplexing, and slot-to-reader mapping.
- Raw tag conversion into filament/color/vendor IDs.
- Which client wrote the operator's `filament_slot16 = 'None'`, and whether qidiclient sends `UPDATE_FILAMENT_INFORMATION SLOT=16` with a filament name `get_fila_id` does not match or saves `filament_slotN` itself.
- Whether `BOX_PRINT_START` initiates RFID reads directly.
- Whether failed/no-result reads preserve prior metadata in every state; they did so in the observed loaded-slot capture.

### Autofeed and anti-wrap

- `MCB_STATE`, `MCB_DONE`, and `MCB_ERROR` payload schemas.
- `MCB_AUTO_START` physical behavior and active abort semantics.
- `limit_a_event`, wrapping count/event gate, `QDE_004_013`, and pause behavior.
- The physical input behind `limit_a_event` during box-only motion, and whether MCU feed-assist steps are reflected in the slot stepper's MCU position.
- Whether pressure-sensor status reflects all autofeed/anti-wrap states.

### Recovery, dryer, and failures

- Live `TRY_MOVE_AGAIN`, `TRY_RESUME_PRINT`, `RESUME_PRINT_1`, `AUTO_RELOAD_FILAMENT`, `RELOAD_ALL`, and `TIGHTEN_FILAMENT` behavior.
- Exact live predicates for each `QDE_004_*` code.
- Dryer timer/state transitions and their relationship to direct heater targets.
- Box button, tool-change, interruption, and power-loss resume transitions.

## Validation boundary

- Status queries and documented idle commands may be recaptured without motion.
- Heater/dryer validation requires temperature and target monitoring.
- RFID validation requires a known tagged QIDI spool aligned to a confirmed reader.
- Autofeed, feeder movement, retry, resume, and failure-path validation require operator-approved physical preflight and live stop capability.
- Changes based only on fake-harness predicates must remain guarded until live evidence exists.
- `.05` load/retry, slot-selection, external-spool, and unload findings may guide compatibility tests but do not authorize live motion tests or repository replacements for vendor modules.
