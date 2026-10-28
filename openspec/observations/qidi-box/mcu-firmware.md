# QIDI Box MCU firmware observations

Evidence qualifiers are defined in `openspec/observations/README.md`. Firmware images examined: `QD_MAX4_BOX_02.03.01.21` (USB Box MCU) and `QD_MAX4_BOX485_02.04.01.01` (RS-485 Box MCU), both shipped in the same update bundle.

## Image identification

Both files are raw ARM Cortex-M application images with no container or header. The vector table is at file offset `0`, so the link address follows from the first vector entry.

| Property | `QD_MAX4_BOX_02.03.01.21` | `QD_MAX4_BOX485_02.04.01.01` |
|---|---|---|
| MCU | `stm32f401xc` (reported by the firmware's own config dictionary) | STM32F103 high-density (60 IRQ entries, GPIO at `0x40010800`, no USB peripheral) |
| Link base | `0x08008000` (32 KiB below it is not part of the image) | `0x08008000` |
| Initial stack | `0x20010000` | `0x200020c0` |
| Clock | 84 MHz | — |
| Transport | USB OTG FS | USART/UART only |
| Lineage | Klipper MCU fork, `"app":"Klipper"`, `"license":"GNU GPLv3"` | Not Klipper: no protocol dictionary, no Klipper strings, `__DATE__`/`__TIME__` build stamp |
| Toolchain | `gcc (GNU Arm Embedded) 10.3.1 20210824`, binutils 2.36.1 | — |
| Interrupt use | Klipper interrupt-driven (`SysTick`, timers, USB, I2C) | Vector table is almost entirely default handlers; polled firmware |

The USB image also embeds its USB identity strings: manufacturer `Klipper`, product `QIDI_BOX_V2_1.2.1`, VID:PID `1d50:614e`.

**Runtime-confirmed.** Both attached boxes report `Loaded MCU 'mcu_box1' 140 commands (02.03.01.21 / gcc (GNU Arm Embedded) 10.3.1 …)` and the same for `mcu_box2`. 140 is the full dictionary count of this image (92 commands plus 48 response and output ids), so the analysed image is the firmware running on the machine, including the `reset_reason_get` command.

## Recovering the protocol dictionary

`buildcommands.py` compresses the MCU data dictionary with zlib and stores it as `command_identify_data`. It is present verbatim in the image at file offset `0x83f8` (address `0x080103f8`) and decompresses to JSON containing `app`, `version`, `build_versions`, `config`, `commands`, `responses`, `output`, and `enumerations`.

```bash
python3 - <<'EOF'
import zlib
d = open('QD_MAX4_BOX_02.03.01.21_20260124.bin', 'rb').read()
print(zlib.decompressobj().decompress(d[0x83f8:]))
EOF
```

This dictionary is the authoritative command surface of the box MCU: 92 command message ids, 45 response ids, 1 non-response output id, all build constants, and all `shutdown()` string ids. The remainder of this file is derived from it plus targeted disassembly of the handler bodies it names.

## Build constants

| Constant | Value |
|---|---|
| `MCU` | `stm32f401xc` |
| `CLOCK_FREQ` | `84000000` |
| `STEPPER_BOTH_EDGE` | `1` |
| `ADC_MAX` / `PWM_MAX` | `4095` / `255` |
| `RESERVE_PINS_USB` | `PA11,PA12` |
| `RESERVE_PINS_crystal` | `PH0,PH1` |
| `BUS_PINS_i2c3` | `PA8,PC9` |
| `INITIAL_PINS` | `!PA1,!PA2,!PB4,!PB5,!PA14,!PA15,!PC4,!PC5` |

`BUS_PINS_i2c3` matching the AHT20 pins in `config/box.cfg` means the heater sensor uses the STM32 hardware I2C3 peripheral rather than a software bus. `INITIAL_PINS` is the eight slot LEDs driven low at boot.

## Command surface

Stock Klipper messages present: steppers (`config_stepper`, `queue_step`, `stepper_*`), endstops and `trsync`, `digital_out`, hard/soft PWM, `neopixel_*`, `buttons_*`, `config_counter`/`query_counter`, `adc`, `i2c_*` (including `i2c_set_software_bus`), `spi_*` (including `spi_set_software_bus`, `config_spi_shutdown`), `sdio_*`, `tmcuart_send`, `sensor_bulk_*`, and base commands.

Messages added by QIDI, absent from mainline Klipper:

| Command | Response(s) |
|---|---|
| `set_limit_a oid=%c state=%c` | — |
| `mcb_config oid=%c`, `mcb_config_stepper oid=%c stepper_oid=%c`, `mcb_auto_start oid=%c v=%u a=%u lmax=%u dir=%i enable=%i invert=%i`, `mcb_auto_abort oid=%c`, `mcb_query oid=%c clock=%u rest_ticks=%u retransmit_count=%c invert=%c` | `MCB_CONFIG_STEPPER`, `MCB_QUERY`, `MCB_STATE`, `MCB_DONE`, `MCB_ABORT`, `MCB_ERR` |
| `config_fm17550 oid=%c spi_oid=%c`, `query_fm17550 oid=%c rest_ticks=%u`, `fm17550_init_cb`, `fm17550_read_regs_cb`, `fm17550_read_fifo_cb`, `fm17550_read_card_cb`, `fm17550_write_card_cb` | `fm17550_init_return`, `..._read_regs_return`, `..._read_fifo_return`, `..._read_card_return`, `..._write_card_return` |
| `config_irq_button oid=%c pin=%u pull_up=%u debounce_us=%u invert=%u`, `irq_button_query oid=%c`, `irq_button_ack oid=%c count=%c` | `irq_button_state oid=%c count=%c state=%*s` |
| `reset_reason_get oid=%c` | `reset_reason_return oid=%c reason=%s` |
| — | `!!warnning:%s` (non-response output; misspelling is in the firmware) |

Consequences: the box MCU protocol is not mainline-compatible in either direction. A mainline host does not know these ids, and mainline MCU firmware has no autofeed, RFID, button, or reset-reason logic.

## MCB autofeed module

**Static-recovered.** `mcb_auto_start` stores its arguments into a per-device structure (`v` at `+0x34`, `a` at `+0x38`, `lmax` at `+0x3c`, direction as a 64-bit value at `+0x40`, the `enable` pin via `gpio_out_setup`, and `invert` at `+0x64`), sets state `1`, and arms a timer. The bound limit pin is read through the same endstop-style query protocol as an endstop (`mcb_query` carries `clock`, `rest_ticks`, `retransmit_count`, `invert`).

Observed timer-state behaviour (disassembled at `0x0800b780`):

- step interval is computed as `CLOCK_FREQ / velocity` and clamped (interval ceiling `8400000` ticks = 0.1 s, i.e. a 10 steps/s floor);
- a step run is emitted in chunks capped at 128 steps;
- `a == 0` selects the constant-velocity path, which is the stock configuration (`a_feed: 0.0`);
- `lmax` is enforced against an elapsed-length counter and terminates the run;
- completion writes the enable pin, stores state `1`, and emits `MCB_DONE oid, steps, limit_state`;
- a coast/stop state arms a fixed 10 ms (`0xCD140` ticks) dwell before finishing;
- `mcb_auto_abort` sets state `5`.

Registered host commands for the same module are `MCB_CONFIG`, `MCB_QUERY`, `SET_LIMIT_A`, `MCB_AUTO_START`, `MCB_AUTO_ABORT`. `MCB_AUTO_START` accepts velocity, acceleration, and maximum length per call, so the compiled motion is re-parameterisable at runtime rather than fixed.

This module does not perform the primary slot load/unload motion; that motion lives in `box_stepper.so` on the host (see `hardware-and-protocols.md`).

## RFID

**Static-recovered.** The FM17550 reader is driven from the MCU over an SPI bus allocated by the host. `fm17550_init_cb` toggles a reset/select line with fixed delays, writes a one-byte command sequence, then reads one status byte and checks its low two bits. Raw register, FIFO, and card payloads are returned to the host as byte buffers.

## Host-side companion modules

Vendor Cython modules are built with `CYTHON_COMPRESS_STRINGS`, so most string literals are stored as one zlib stream inside the shared object rather than as plain text. They decompress to the module's full literal table, including G-code fragments, error-code text, and config-key names:

```bash
python3 - <<'EOF'
import zlib
d = open('box_stepper.so', 'rb').read()
for i in range(len(d) - 2):
    if d[i] == 0x78 and d[i + 1] in (0x01, 0x9c, 0xda, 0x5e):
        try:
            out = zlib.decompressobj().decompress(d[i:i + 2000000])
            if len(out) > 200:
                print(out.decode('utf-8', 'replace'))
        except zlib.error:
            pass
EOF
```

`box_stepper.so` carries a debug build (`box_stepper.c`, `-g -O2`) with a `.debug_info` unit built in `/builds/qidi/3dprinter_m4/resources/py2so/klipper/build`, and its literal table preserves the `BoxExtruderStepper` method inventory.

## Watchdog and fault posture

**Static-recovered.** The USB image starts the independent watchdog during init: `IWDG->KR = 0x5555`, `PR = 0`, `RLR = 0x0FFF`, `KR = 0xCCCC`, giving roughly 512 ms at the ~32 kHz LSI. A reload (`KR = 0xAAAA`) runs from the task loop.

The RS-485 image contains no IWDG or WWDG reference at all.

Klipper's fault handlers fall through to a default handler that loops in place, so on the USB image a hard fault or a scheduler stall longer than the reload period becomes a watchdog reset, and a watchdog reset on a USB CDC device is indistinguishable, from the host, from a cable or power event.

## Shutdown reasons

**Static-recovered.** The `static_string_id` enumeration is complete for the linked image: 46 reasons, ids 2 through 48.

Reasons reachable from the box's own hardware surface include `ADC out of range` (the only `try_shutdown`), `Missed scheduling of next digital out event`, `Scheduled digital out event will exceed max_duration`, `Scheduled pwm event will exceed max_duration`, `Can not set soft pwm cycle ticks while updates pending`, `update_digital_out not valid with active queue`, `Move queue overflow`, `Stepper too far in past`, `Can't reset time when stepper active`, and `Can't add signal that is already active`.

Two differences from mainline are significant:

- `Timer too close` and `Rescheduled timer in the past` are absent. `sched_try_shutdown` is inlined at exactly one call site, the ADC range check, so the timer-lateness shutdowns are not compiled in. A late timer on this MCU does not shut it down.
- I2C failures no longer shut the MCU down. Mainline emits `shutdown("I2C NACK")`, `"I2C START NACK"`, `"I2C START READ NACK"`, or `"I2C Timeout"`; none of those strings exist in this image. The only two uses of the `!!warnning:%s` output are in I2C paths, carrying the literals `soft_i2c NACK` and `i2c timeout`, emitted and then ignored. The hardware-I2C setup path is the one that can raise `i2c timeout`, on a bounded wait for the peripheral reset bit to clear.

The practical consequence is that an AHT20 or I2C bus fault on the box degrades silently instead of aborting the print, and the corresponding `verify_heater` supervision for `heater_boxN` becomes the only thing that notices.

## Reset reason

QIDI replaced mainline's static `RESET_REASON` constant with a runtime command. The reason strings in the image are `PowerOn`, `Unknown`, `LowPower`, `WindowWatchdog`, `IndependentWatchdog`, `Software`, `NRST_Pin`. `reset_reason_get` is never issued by the vendor host modules, so the box's reset reason is not recorded anywhere by default.
