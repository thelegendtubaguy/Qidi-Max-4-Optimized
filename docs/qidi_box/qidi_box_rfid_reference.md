# QIDI Box RFID reference

## Source

Harness output:

- `tmp/qidi-box-reversing/box_rfid_probe.json`

Compiled symbol priority:

- `docs/qidi_box/qidi_box_compiled_symbol_map.md`

The harness instantiated `box_rfid.so` with fake Klipper/MCU/SPI objects and captured config commands, query command formats, runtime fields, and timeout defaults without requiring a physical RFID tag read.

## Class and methods

`box_rfid.so` exposes class `BoxRFID` with these recovered methods:

| Method | Harness result |
|---|---|
| `__init__(config)` | initializes runtime fields and allocates an OID |
| `_build_config()` | adds MCU FM17550 config commands |
| `read_card()` | sends an FM17550 read query |
| `read_card_from_slot()` | sends an FM17550 read query for the selected stepper slot path |
| `_schedule_rfid_read(eventtime)` | callback-driven read scheduling; fake harness raised `TypeError` because no real response payload existed |
| `start_rfid_read(stepper)` | starts a scheduled read for a stepper; fake harness raised `AttributeError` with a string stepper because real stepper/reactor context was absent |
| `stop_read()` | stops/clears read state |

## Runtime fields

Harnessed initial fields:

| Field | Value |
|---|---|
| `name` | `card_reader_1` |
| `oid` | `21` |
| `fm17550_read_card` | `None` before query object assignment |
| `gcode` | `None` in fake harness |
| `read_rfid_timer` | `None` in fake harness |
| `rfid_read_attempts` | `0` |
| `rfid_read_start_time` | `0` |
| `max_read_time` | `30.0` |
| `get_message_count` | `1` |
| `temp_message_1` | `None` |
| `temp_message_2` | `None` |
| `stepper` | `None` initially; `slot0` after fake `start_rfid_read()` call |
| `had_get_value` | `False` |

## MCU config commands

`_build_config()` adds these MCU config commands:

```text
query_fm17550 oid=21 rest_ticks=0
config_fm17550 oid=21 spi_oid=55
```

The `query_fm17550` config command is added with:

```text
on_restart=True
```

## MCU query format

The read command object uses:

```text
fm17550_read_card_cb oid=%c
fm17550_read_card_return oid=%c status=%c data=%*s
```

Harnessed query sends:

```text
[21]
[21]
[21]
[21]
```

Payload field order:

```text
[oid]
```

## Reader topology

Stock/QIDI Client strings and `config/box.cfg` identify two RFID chip-select pins for one QIDI Box MCU:

| Config key | Pin |
|---|---|
| `cs_pin_box_rfid_0` | `mcu_box1:PC6` |
| `cs_pin_box_rfid_1` | `mcu_box1:PC7` |

`multi_color_controller.LocalAdapter.connect()` looks up four logical reader objects for one four-slot box:

```text
box_rfid card_reader_1
box_rfid card_reader_2
box_rfid card_reader_3
box_rfid card_reader_4
```

The exact mapping from four logical readers to the two chip-select pins is not proven by the fake harness.

## Known timing and retry behavior

| Behavior | Value | Evidence |
|---|---:|---|
| max read duration | `30.0 s` | runtime field `max_read_time` |
| initial attempts | `0` | runtime field `rfid_read_attempts` |
| duplicate-message count | `1` | runtime field `get_message_count` |
| initial read start time | `0` | runtime field `rfid_read_start_time` |
| query restart behavior | `rest_ticks=0`, `on_restart=True` | MCU config command |

## Material metadata path

Material ID mappings are documented in `docs/qidi_box/qidi_box_material_metadata_reference.md`.

RFID data ultimately feeds the same saved-variable/material lookup path used by the rest of the box stack:

- `filament_slotN`
- `color_slotN`
- `vendor_slotN`
- `config/officiall_filas_list.cfg`

Runtime status in `docs/qidi_box/qidi_box_runtime_observations.md` shows material metadata can exist without a fresh captured RFID read, because saved variables already held slot metadata.

## Runtime command captures

Runtime captures in `docs/qidi_box/qidi_box_runtime_observations.md` executed these commands while the printer was idle and synced to `slot2`:

```gcode
SLOT_RFID_READ SLOT=slot2
INIT_RFID_READ
MULTI_COLOR_READ_RFID SLOT=slot2
```

Observed behavior:

- Moonraker accepted each command with `{"result": "ok"}`.
- `saved_variables.diff` was empty after each command.
- `filament_slot2 = 18`, `color_slot2 = 2`, and `vendor_slot2 = 0` remained unchanged.
- `multi_color_controller.rfid.reading = false` after the capture waits.
- `multi_color_controller.rfid.results = {}` after the capture waits.
- No raw FM17550 `status` / `data` payload appeared in the captured log tails.

This runtime capture shows that failed/no-visible-result reads did not clear existing slot2 metadata in that state. It does not recover valid QIDI tag payload bytes.
