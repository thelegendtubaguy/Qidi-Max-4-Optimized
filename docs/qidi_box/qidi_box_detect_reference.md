# QIDI Box detection reference

## Source

Captured module:

- `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/klipper/klippy/extras/box_detect.so`

String and symbol artifacts:

- `tmp/qidi-box-reversing/20260507-135653-printer-capture/analysis/strings/box_detect.so.strings.txt`
- `tmp/qidi-box-reversing/symbol-dumps/box_detect.objdump-symbols.txt`

## Role

`box_detect.so` monitors QIDI Box USB serial devices, updates box config includes, writes `box_count`, and requests Klipper restart when detected box topology changes.

It is relevant to stock runtime detection and config mutation. It is not part of load/unload speed, distance, or timing control.

## Recovered class and functions

| Symbol/function | Role implied by name and strings |
|---|---|
| `BoxDetect.__init__` | initializes detection state, config paths, timers, and event handlers |
| `BoxDetect._handle_ready` | handles `klippy:ready` |
| `BoxDetect.get_config_mcu_serials` | reads configured MCU serials from config |
| `BoxDetect.monitor_serial_by_id` | monitors `/dev/serial/by-id/` devices |
| `BoxDetect._update_config_file` | writes/updates box config include/config content |
| `BoxDetect._request_restart` | requests firmware restart through G-code |
| `BoxDetect.get_check_serials_id` | builds/filters serial IDs to check |
| `BoxDetect.count_box_includes` | counts active `[include boxN.cfg]` lines |
| `monitor_serial_devices` | module-level serial monitor helper |
| `is_monitor_config_file_empty` | checks monitor config file content |
| `update_monitor_config_file` | updates monitor config file |
| `add_printer_objects` | module-level object registration helper, from symbol table |

## Detection strings and paths

Recovered strings include:

```text
/dev/serial/by-id/
QIDI_BOX_V1
QIDI_BOX_V2
mcu_box
mcu mcu_box
mcu_box_to_v2
serial_by_id
config_serial
config_serial_1
config_serial_2
config_serial_3
config_serial_4
firmware_restart
gcode:request_restart
klippy:ready
SAVE_VARIABLE VARIABLE=box_count VALUE=%d
SAVE_VARIABLE VARIABLE=box_count VALUE=0
```

Config paths recovered from strings:

```text
/home/qidi/printer_data/config/box.cfg
/home/qidi/printer_data/config/box1.cfg
/home/qidi/printer_data/config/box2.cfg
/home/qidi/printer_data/config/saved_variables.cfg
```

Include matcher recovered from strings:

```text
\[include box(\d+)\.cfg\]
```

Firmware update helper recovered from strings:

```text
/home/qidi/QIDI_Client/tools/mcu_update_BOX_to_v2.sh /home/qidi/QIDI_Client/tools/
```

Exact captured by-id serial values are intentionally not copied into tracked docs.

## Symbol priority

| Function symbol | Size | Relevance |
|---|---:|---|
| `BoxDetect.monitor_serial_by_id` | `0xb418` | primary USB serial monitor and topology update path |
| `monitor_serial_devices` | `0x7b5c` | module-level device scan helper |
| `update_monitor_config_file` | `0x2c28` | writes monitor config state |
| `BoxDetect._update_config_file` | `0x1558` | mutates box config/include content |
| `BoxDetect.get_config_mcu_serials` | `0x1064` | reads configured serials |
| `BoxDetect.__init__` | `0x1060` | setup, paths, timers, event registration |
| `BoxDetect.count_box_includes` | `0xb40` | counts included box config files |
| `BoxDetect.get_check_serials_id` | `0xa58` | derives serial IDs to check |
| `is_monitor_config_file_empty` | `0x818` | monitor config helper |
| `BoxDetect._handle_ready` | `0x610` | ready event hook |
| `BoxDetect._request_restart` | `0x60c` | firmware restart request path |

## Stock behavior implications

- Stock QIDI firmware treats the box as a USB Klipper MCU visible under `/dev/serial/by-id/`.
- `box_detect.so` can mutate config files and saved variables when box presence changes.
- The stock path can distinguish box firmware families through `QIDI_BOX_V1`, `QIDI_BOX_V2`, and `mcu_box_to_v2` strings.
- The module can request Klipper restart after config updates.
- `box_count` is persisted through `SAVE_VARIABLE` commands.
