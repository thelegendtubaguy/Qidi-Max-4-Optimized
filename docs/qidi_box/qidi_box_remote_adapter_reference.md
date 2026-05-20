# QIDI Box remote adapter reference

## Source

Harness output:

- `tmp/qidi-box-reversing/remote_adapter_probe.json`

Compiled module:

- `multi_color_controller.so`

The harness monkey-patched `RemoteAdapter._send_command()` and captured generated JSON-style command dictionaries without opening a serial port or moving hardware.

## Role

`multi_color_controller.RemoteAdapter` is the second-generation/remote-box command path. It sends JSON-like command dictionaries over a serial connection and updates `UnifiedState` from responses/events.

The current Max 4 runtime status in `docs/qidi_box/qidi_box_runtime_observations.md` reports `multi_color_controller.system.mode = local`, so this path is not the active QIDI Box movement path on this machine.

## Command envelope

Every captured remote command includes:

| Field | Meaning |
|---|---|
| `cmd` | remote command name |
| `timestamp` | generated send timestamp |
| `id` | generated command ID such as `cmd_<millis>_<suffix>` |

Every harnessed `_send_command()` call used:

```text
timeout = 5.0
```

## Captured command map

| Adapter method | Remote `cmd` | Additional fields |
|---|---|---|
| `load_filament('slot0')` | `load_filament` | `slot: 0`, `options: {}` |
| `unload_filament('slot0')` | `unload_filament` | `slot: 0`, `options: {}` |
| `swap_filament('slot0', 'slot1')` | `swap_filament` | `from_slot: 0`, `to_slot: 1`, `options: {}` |
| `start_drying(1, 50, 2)` | `start_drying` | `box: 1`, `temp: 50`, `hours: 2` |
| `stop_drying(1)` | `stop_drying` | `box: 1` |
| `read_rfid('slot0')` | `read_rfid` | `slot: 0` |
| `sync_to_extruder('slot0')` | `sync_to_extruder` | `slot: 0` |
| `unsync_from_extruder()` | `unsync_from_extruder` | none |
| `box_unload('slot0')` | `box_unload` | `slot: 0` |
| `init_rfid()` | `init_rfid` | none |
| `reload_all(1)` | `reload_all` | `first: 1` |
| `auto_reload()` | `auto_reload` | none |
| `retry(1)` | `retry` | `rfid: 1` |
| `tighten(2)` | `tighten` | `tool: 2` |
| `print_start(3, 240)` | `print_start` | `extruder: 3`, `hotendtemp: 240` |
| `try_resume()` | `try_resume` | none |
| `resume_print(220)` | `resume_print` | `temp: 220` |
| `init_mapping()` | `init_mapping` | none |
| `disable_heater()` | `disable_heater` | none |
| `set_temp({'BOX': 1, 'TARGET': 55})` | `set_temp` | `temp_params: {'BOX': 1, 'TARGET': 55}` |
| `clear_runout()` | `clear_runout` | none |
| `clear_flush()` | `clear_flush` | none |
| `clear_ooze()` | `clear_ooze` | none |
| `cut_filament(2)` | `cut_filament` | `tool: 2` |

## Slot normalization

Remote adapter methods normalize `slotN` strings to numeric slot fields:

| Input | Remote field |
|---|---:|
| `slot0` | `0` |
| `slot1` | `1` |

The same normalization appears in `load_filament`, `unload_filament`, `swap_filament`, `read_rfid`, `sync_to_extruder`, and `box_unload`.

## Local vs remote adapter contrast

| Operation | LocalAdapter dispatch | RemoteAdapter dispatch |
|---|---|---|
| load | `E_LOAD SLOT=0` | `{'cmd': 'load_filament', 'slot': 0}` |
| unload | `E_UNLOAD SLOT=0` | `{'cmd': 'unload_filament', 'slot': 0}` |
| box unload | `E_BOX SLOT=0` | `{'cmd': 'box_unload', 'slot': 0}` |
| RFID read | `SLOT_RFID_READ SLOT=slot0` | `{'cmd': 'read_rfid', 'slot': 0}` |
| print start | `BOX_PRINT_START EXTRUDER=3 HOTENDTEMP=240` | `{'cmd': 'print_start', 'extruder': 3, 'hotendtemp': 240}` |
| clear flush | `CLEAR_FLUSH` | `{'cmd': 'clear_flush'}` |
| clear ooze | `CLEAR_OOZE` | `{'cmd': 'clear_ooze'}` |
| cutter | `CUT_FILAMENT T=2` | `{'cmd': 'cut_filament', 'tool': 2}` |
