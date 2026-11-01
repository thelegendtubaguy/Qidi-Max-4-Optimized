# QIDI RS-485 device stack

Evidence qualifiers are defined in `openspec/observations/README.md`. Sources: the `01.01.07.01` Klipper extras (`box485.py`, `box485_multicolor.so`, `box_protocol.so`, `box485_buffer.so`, `box485_rack.so`, `box2base.so`) and the firmware manifest. No RS-485 device has been observed on a printer.

## Hardware and firmware

- **Runtime-confirmed:** the `01.01.07.01` firmware manifest lists `BOX485` `02.04.01.01` and `BUFFER` `02.05.01.01` alongside the USB Box's `BOX` `02.03.01.21`.
- **Static-recovered:** the RS-485 Box image is a polled STM32F103 application with no USB peripheral and no Klipper protocol (see `mcu-firmware.md`). An RS-485 Box is a different device from the USB Box, not a USB Box on a different link.
- **Config-confirmed:** `[box485]` opens `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` (a CH340 USB serial adapter) at 115200 baud. On a printer with only USB Boxes no such device exists, and `/dev/serial/by-id` lists only the Klipper MCUs.
- **Static-recovered:** `box2base` strings describe a brushless feed motor with an encoder, a five-way hub, a buffer with Hall sensors, RFID reads at power-on, drying, and a factory test mode (`BOX_TEST_MODE`). One error string names its Bambu Lab counterpart.

## Host module

- **Harness-recovered:** `box485.load_config` returns `box485_multicolor.Box485Manager`, a plain Python class. It reads `serial_port`, `baud`, `serial_timeout`, `hall_value`, `extrude_timeout`, `extrude_length`, `address_start`, `address_end` (default 247), `detect_pin`, and `rack_uuid`, and registers `klippy:ready` (`connect`), `klippy:disconnect`, and `klippy:shutdown` handlers.
- **Harness-recovered:** `connect` opens the port with pyserial `serial.Serial(port, baud, timeout=0.0)`. When the open fails it logs `【通信-串口】无法打开串口 <port>: <error>, 稍后重试...` once and `Can not find 485 device` from a reconnect timer every 2 s. Once open, receive and transmit run on reactor timers in Klipper's main thread (receive poll 0.5 s, transmit poll 0.1 s, 0.2 s gap between frames), with a 3 s heartbeat and 10 s discovery.
- **Harness-recovered:** registered commands: `BOX_ADDR_ASSIGN`, `BOX_ADDR_RELEASE`, `BOX_CLEAR_MCU_IDS`, `BOX_LIST`, `BOX_RESET_DEVICE`, `BOX_SAVE`, `GET_BUFFER_HALL`, `GET_MATERIAL_RACK_STATUS`, `GET_MATERIAL_RACK_STEPPER_DRIVER_CONFIG`, `GET_MATERIAL_RACK_STEPPER_MOTOR_CONFIG`, `GET_UUID`, `GET_VERSION`, `MATERIAL_RACK_LED_CONTROL`, `MATERIAL_RACK_SET_HALL_THRESHOLD`, `MATERIAL_RACK_STEPPER_MOTOR_CONTROL`, `QUERY_CURRENT_BOX_CHANNEL_FILAMENT`, `RACK_LIST`, `RACK_STEPPER_MOTOR_STOP`, the `SET_BUFFER_SINGLE_HALL_*` family, `SET_HALL_THRESHOLD`, `SET_MATERIAL_RACK_STEPPER_DRIVER_CONFIG`, `SET_MATERIAL_RACK_STEPPER_MOTOR_CONFIG`, `START_HALL_LOG`, `STOP_HALL_LOG`, and `TEST_HALL`.
- **Harness-recovered:** with no device, `get_status` returns `{"box_count": 0, "boxes": [], "buffer": {}}`.
- **Harness-recovered:** QIDI's log lines from these modules carry no module attribution: Cython creates no Python frames, so a `LogRecord` names whatever Python code called into them.

## Frame format

- **Harness-recovered:** a frame is `AA 55`, the device address, the command id, the payload length, the payload, and a CRC-16/ARC (polynomial `0xA001` reflected, initial value 0) of everything before it, big-endian. `box_protocol.CMD` maps command names to ids and `REV_SLAVE_CMD` maps them back. Device types are `multicolor` 1, `buffer` 2, and `rack` 3. Addresses `1`–`127` are leased to Boxes, `128` is the rack, and `129` the buffer.
- **Harness-recovered:** discovery broadcasts `GET_UUID` (command 1) to address 0 with a 4-byte payload that changes between broadcasts. A device answers `UUID_ACK` (command 2) whose payload starts with its 12-byte chip id. The host then saves that id as `box0_mcu_id` through `box3_mcu_id` (`MAX_PERSIST_BOX_SLOTS` 4) and keeps address leases in `box485_leases` (24 h default lease). Printers that have only had USB Boxes have none of these variables.

## Misconfigured port

- **Unresolved, user report:** owners on firmware `1.1.3.x` reported that pointing `[box485] serial_port` at the USB Box id from `box.cfg` stops the `Can not find 485 device` lines, and that Box `bytes_retransmit` then climbs and the Box restarts mid-print. This fits the harness behavior, since box485 then reads that Klipper MCU's port every 0.5 s and takes bytes meant for Klipper, but it has not been reproduced here.

## Main MCU RS-485 diagnostics

- **Runtime-confirmed:** the main MCU (`QIDI_MAIN_V2_1.0.12`, firmware `02.01.01.12`) emits `#output: rs485_diag rb_drop=… uart_ore=… checksum_err=… resync=… discard=… frame_too_long=… tx_overflow=…` into `klippy.log` on a printer with only USB Boxes. Eleven lines appeared on 2026-10-30, with `checksum_err` between 1 and 9 and `resync` up to 4 while idle.
- **Unresolved:** which bus this is. It is not the `[box485]` adapter path, which runs on the host. The closed-loop motors (`CLOSED_LOOP_MOTOR` `03.01.10.15` in the manifest) are a candidate.
