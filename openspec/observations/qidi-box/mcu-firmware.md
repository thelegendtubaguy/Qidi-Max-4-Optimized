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

## Firmware update path

**Static-recovered** from `qidiclient` (aarch64). The Box update copies the image to `/home/qidi/klipper_BOX.bin`, opens the Box's Klipper port, looks up the `reset` message id in the Box's data dictionary, and sends a hand-built Klipper `reset` frame; there is no 1200-baud request. After the reset the Box presents the `0483:5740` startup device (see Reset reason), and the client talks to it with the same framing as the THR bootloader: `A5`, kind, big-endian length, payload, big-endian CRC16. The sequence is a basic query (reply `Model=` or `NEW: Model=…, Version=V%u.%u`), a start packet carrying the image size, indexed data pages, then End or Abort. Odd-length images are padded with one `0xFF`. The client sends no image checksum, signature, or version; whether the bootloader validates the application is **Unresolved**, because the code below `0x08008000` is not in the update image.

**Static-recovered.** The application's 1200-baud request is a separate path: it writes `USB BOOT` at `0x2000fc00` and resets, and startup then enters the STM32 ROM DFU loader at `0x1fff0000`.

**Static-recovered.** Startup copies `.data` and zeroes only `.bss` (`0x20000038`–`0x200004c4`); the stack occupies `0x2000fe00`–`0x20010000`, and Klipper's allocator limit is the literal `0x2000fe00`. The image ends at `0x080119e0`, leaving about 58 KiB free below `0x08020000`.

**Emulated** (real bootloader code in unicorn, USB stack and delays stubbed, flash controller modelled) **and runtime-confirmed on one Box** (2026-10-29). The bootloader (`COLOR BOOT`, 32 KiB at `0x08000000`, SHA-256 `64962da860449bd3af7ead7cc194ec01192493b0b3e7eedc70e384f61bf7b1e4`) holds the USB pins low for 100 ms, then runs a 2 s timer that any received frame reloads. When it expires, it jumps to `0x08008000` if any word in the first 4 KiB of the application is not erased, after sending an unprompted `0202` frame and waiting 1 s; otherwise it stays resident. It has no RAM magic, button, stack-pointer, checksum, version, or signature check. Identity (kind 0, payload `01 00`) is answered once per boot with `0112`. Start erases sectors 2–5 (`0x08008000`–`0x0803FFFF`) whatever the declared size; data packets are written at a write pointer that advances 1 KiB per packet, starts at `0x08008000` only at reset, and ignores the packet index except for bounds and duplicate checks; resending the previous packet is acknowledged without writing, while a second start or a resent packet 0 shifts the image. A 2 s session timeout, abort, or short end erases sector 2, so the bootloader stays resident on the next reset. No path erases or writes sectors 0–1. Read protection is level 0 with no write protection. On the test printer, a Klipper `reset` followed by an identity within the window, and a full transfer and readback, behaved as emulated.

**Static-recovered.** The application's `USB BOOT` check at `0x2000FC00` is in its own reset handler (`0x0800d9f4`), so ROM DFU entry needs a running application.

## Watchdog and fault posture

**Static-recovered.** The USB image starts the independent watchdog during init: `IWDG->KR = 0x5555`, `PR = 0`, `RLR = 0x0FFF`, `KR = 0xCCCC`, giving roughly 512 ms at the ~32 kHz LSI. A reload (`KR = 0xAAAA`) runs from the task loop.

The RS-485 image contains no IWDG or WWDG reference at all.

Klipper's fault handlers fall through to a default handler that loops in place, so on the USB image a hard fault or a scheduler stall longer than the reload period becomes a watchdog reset. Until that reset, the USB peripheral keeps the device attached while the firmware sends nothing, so a stall shows on the host as a silence of one reload period (512 ms at the nominal LSI frequency; the STM32F401 LSI range of 17–47 kHz allows roughly 0.35–0.96 s) before the USB disconnect. A supply or cable event drops the device without that silence.

## Stall sources

**Static-recovered.** The only unbounded wait that depends on an external device is the FM17550 transceive routine (`0x0800a970`). Its loop (`0x0800aa38`–`0x0800ac88`) polls the reader's ComIrq register over SPI and exits only on chip-reported TimerIRq, IdleIRq, RxIRq, or FIFO-alert bits. It has no cycle or iteration bound and does not treat ErrIRq as an exit. A reader that resets or stops answering mid-exchange therefore holds the MCU until the IWDG resets it. The routine runs from the main-loop card-search task (`0x0800aeb8`, armed by `query_fm17550`) and from the `fm17550_read_card_cb` and `fm17550_write_card_cb` handlers.

**Static-recovered.** Hardware I2C transfers to the AHT20 share a 5 ms cycle-counter deadline per command. A failed start resets the peripheral and retries up to three times within it, then emits `!!warnning:i2c timeout`; other timeouts reset the peripheral silently, and `i2c_read` returns its bytes regardless. There is no bus recovery, so a held bus costs each command up to 5 ms and returns bad data, but does not stall the MCU. Hardware SPI waits (`0x0800cc8a`, `0x0800cc9c`) and USB and clock-ready waits are unbounded but depend only on on-chip state.

**Static-recovered.** All fault vectors, NMI, and unused interrupts branch to a self-loop (`0x0800d2f4`). The clock security system is off and the PLL runs from the external crystal, so a fault, a supply-induced bus error, or a stopped crystal also ends in an IWDG reset. The SysTick timer dispatcher (`0x0800dad0`) has no "Rescheduled timer in the past" shutdown, so timer overload starves the task loop instead of shutting the MCU down. An `IndependentWatchdog` reading therefore shows that the MCU stopped reloading the watchdog, not which of these caused it.

## Shutdown handling

**Static-recovered.** `shutdown()` (`0x0800831c`) disables interrupts and longjmps into `sched_main` (setjmp at `0x0800903c`), which runs the inlined shutdown handlers (`0x08009048`–`0x08009396`) and then returns to the task loop, where the IWDG reload (`0x0800880c`) runs on every pass. QIDI's MCB autofeed handler, second in the list, clears a byte on each MCB object, then at `0x080090b6` (`movs r4, #0`) continues using the now-NULL loop pointer as an MCB object: it reads an oid from address `0x11` and passes it to the stepper lookup. Unless that byte happens to name a stepper, the lookup raises `shutdown("Invalid oid type")`, which longjmps back into the same handler list and repeats with interrupts disabled. The shutdown message is never sent, USB is not serviced, and the IWDG resets the MCU. Every shutdown reaches this block, including `emergency_stop` (`0x08008380`, task context) and the `max_duration` and missed-scheduling checks raised from the SysTick handler.

**Runtime-confirmed.** A Box that received `emergency_stop` reset through the IWDG 0.65 s later, and a Box whose heater `max_duration` expired did the same (see `link-failures.md`, Drop at print end with the serial history).

**Emulated.** Replacing the two bytes at file offset `0x10b6` with `19 e0` (`b.n 0x080090ec`) skips the faulty block, which in stock firmware never completes, and continues with the next handler. Run from a Box's live RAM (read through `debug_read` while configured), the stock handler list re-enters `shutdown()` with `Invalid oid type` for every reason tried, and the patched list reaches the `shutdown` report with the original reason. **Runtime-confirmed (2026-10-29):** a Box flashed with that change plus a marked version string loads in Klipper as `02.03.01.21-tltg-shutdownfix1`; on `emergency_stop` it replied `shutdown clock=… static_string_id=Command request` and kept its USB link, while a stock Box on the same printer, on the hub path to it, went silent, disconnected 0.56 s later, and returned through the `0483:5740` stage. Other shutdown reasons on the patched image, and its behavior under load, are **Unresolved**.

## Shutdown reasons

**Static-recovered.** The `static_string_id` enumeration is complete for the linked image: 46 reasons, ids 2 through 48.

Reasons reachable from the box's own hardware surface include `ADC out of range` (the only `try_shutdown`), `Missed scheduling of next digital out event`, `Scheduled digital out event will exceed max_duration`, `Scheduled pwm event will exceed max_duration`, `Can not set soft pwm cycle ticks while updates pending`, `update_digital_out not valid with active queue`, `Move queue overflow`, `Stepper too far in past`, `Can't reset time when stepper active`, and `Can't add signal that is already active`.

Two differences from mainline are significant:

- `Timer too close` and `Rescheduled timer in the past` are absent. `sched_try_shutdown` is inlined at exactly one call site, the ADC range check, so the timer-lateness shutdowns are not compiled in. A late timer on this MCU does not shut it down.
- I2C failures no longer shut the MCU down. Mainline emits `shutdown("I2C NACK")`, `"I2C START NACK"`, `"I2C START READ NACK"`, or `"I2C Timeout"`; none of those strings exist in this image. The only two uses of the `!!warnning:%s` output are in I2C paths, carrying the literals `soft_i2c NACK` and `i2c timeout`, emitted and then ignored. Hardware I2C raises `i2c timeout` when a start condition still fails after its retries (see Stall sources below).

The practical consequence is that an AHT20 or I2C bus fault on the box degrades silently instead of aborting the print, and the corresponding `verify_heater` supervision for `heater_boxN` becomes the only thing that notices.

## Reset reason

QIDI replaced mainline's static `RESET_REASON` constant with a runtime command. `reset_reason_get` is never issued by the vendor host modules, so the box's reset reason is not recorded anywhere by default.

**Static-recovered.** The handler (`0x0800d46c`) reads `RCC->CSR` and returns the name of the first flag set, in this order: `LPWRRSTF` → `LowPower`, `WWDGRSTF` → `WindowWatchdog`, `IWDGRSTF` → `IndependentWatchdog`, `SFTRSTF` → `Software`, `PORRSTF` → `PowerOn`, `PINRSTF` → `NRST_Pin`, otherwise `Unknown`. `BORRSTF` is not tested. The only `RCC->CSR` access in the image is that read: nothing sets `RMVF`, so the flags accumulate from one reset to the next until a power-on reset clears them, and the answer is the highest-ranked reset since power-on rather than the most recent one.

**Static-recovered.** The `reset` command (`0x0800dd60`) is mainline Klipper's `command_reset`: it writes the Katapult bypass request (`0x7b06ec45a9a8243d`) only when the image below `0x08008000` carries the `CanBoot!` signature, then calls `NVIC_SystemReset`. It does not wait for the watchdog. `NVIC_SystemReset` is the image's only reset path, also used by the 1200-baud USB bootloader request.

**Runtime-confirmed (2026-10-29, two USB Boxes).** With the host already running, each Box was powered on and then read without any reset in between: both returned `PowerOn`. After one `FIRMWARE_RESTART`, both returned `Software`. The reading is therefore the highest-ranked reset since the Box was last powered on. `FIRMWARE_RESTART` replaces `PowerOn` with `Software` but cannot hide an earlier `IndependentWatchdog`.

**Runtime-confirmed (2026-10-29, two USB Boxes).** Every Box start, including a cold power-on, first enumerates as USB `0483:5740` (STMicroelectronics Virtual COM Port) for about 2.3–2.6 s. The Box then disconnects and enumerates again as the Klipper application, `1d50:614e`. The two-step enumeration is the startup path below `0x08008000` handing over to the application, not a second reset: the cold-boot reading stayed `PowerOn` across it. `qidiclient` matches `/dev/serial/by-id/usb-*_Virtual_ComPort_*`, which fits that device being the update bootloader.

**Runtime-confirmed.** Before that power cycle, both Boxes read `IndependentWatchdog`, even though dmesg showed only host-commanded Box resets, and no Box power cycle, since the host booted that day. The Boxes are powered separately from the printer, so those IWDG resets predate that boot. One Box on another printer read `IndependentWatchdog` after `FIRMWARE_RESTART` (operator report, GitHub issue 159). Each of those Boxes had at least one IWDG reset since it was last powered on. When those resets happened, and what preceded them, is **Unresolved**.
