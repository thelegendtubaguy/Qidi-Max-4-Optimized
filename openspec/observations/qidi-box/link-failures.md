# QIDI Box MCU link failures

Evidence qualifiers are defined in `openspec/observations/README.md`. This file records how a box MCU link failure appears on the host, what the host does and does not attribute, and which signals can be observed without root access.

## Transport identity

**Runtime-confirmed.** Both attached boxes are USB CDC-ACM Klipper MCUs. The USB product string is the firmware's own identity string, which matches the value embedded in the `QD_MAX4_BOX` image:

| Klipper object | USB product string | USB path | `/dev` node |
|---|---|---|---|
| `mcu` | `QIDI_MAIN_V2_1.0.12` | `2-1.3` | `ttyACM0` |
| `mcu_box2` | `QIDI_BOX_V2_1.2.1` | `2-1.4.2` (on hub `2-1.4`) | `ttyACM1` |
| `mcu_box1` | `QIDI_BOX_V2_1.2.1` | `2-1.4.1.2` (behind hub `2-1.4.1`) | `ttyACM2` |

`THR` is not on USB (`/dev/ttyS4`, 500000 baud).

Both boxes therefore hang off the same internal hub tree, and one of them sits behind a nested hub. Identifier suffixes in `/dev/serial/by-id` are hardware serials and are not reproduced here.

The RS-485 stack is also loaded on a two-USB-Box machine: `box485_multicolor` polls for a 485 device about every two seconds and logs `Can not find 485 device`. In one capture that line appeared 5362 times in a single klippy.log. It is background noise, not a fault, and it means the presence of 485-stack log lines does not imply an RS-485 Box is attached.

## Observed failure

**Runtime-confirmed.** A print in progress lost `mcu_box2` on 2026-10-22. The sequence, in klippy.log order:

| Time | Event |
|---|---|
| 18:08:00 | `Stats` line: `heater_box2: target=45 temp=36.9 pwm=1.000`, `heater_temp_a_box2: temp=75.9`, `heater_temp_b_box2: temp=90.3`; `mcu_box2: bytes_retransmit=9 ... send_seq=12686 receive_seq=12686 retransmit_seq=2 rto=0.025 upcoming_bytes=0` |
| 18:08:46 | print status changes to `printing` |
| 18:08:16 | `Got EOF when reading from device` |
| 18:08:56 | `Timeout with MCU 'mcu_box2' (eventtime=262858.038956)` |
| 18:08:56 | `Transition to shutdown state: Lost communication with MCU 'mcu_box2'`, followed by `料盒急停` and 158 repetitions of `Lost communication with MCU 'mcu_box2'` |
| 18:08:56 | final `Stats`: `mcu_box2: bytes_retransmit=203 ... send_seq=12821 receive_seq=12815 retransmit_seq=12821 rto=0.400 ready_bytes=0 upcoming_bytes=1487` |

`mcu`, `THR`, and `mcu_box1` kept normal counters through the same window (`send_seq == receive_seq`, `bytes_retransmit=9`).

### What this establishes

- The MCU did not report a shutdown. A firmware-initiated stop emits `MCU '<name>' shutdown: <reason>` with one of the 46 compiled reasons; no such line exists. The link simply stopped.
- `Got EOF when reading from device` comes from `klippy/chelper/serialqueue.c`; it is raised when `read()` returns 0 on the MCU's serial descriptor, and it is followed by a poll-reactor exit. For a CDC-ACM device that means the device end-point went away, not that the MCU sent an error.
- By the timeout, the link counters had degraded: `bytes_retransmit` went from 9 to 203, `receive_seq` fell six messages behind `send_seq`, and `rto` backed off from 25 ms to 400 ms. `upcoming_bytes=1487` shows unacknowledged data still queued. The only earlier sample is the baseline `Stats` line 16 s before the EOF, so this capture cannot show whether the degradation started before the EOF or only after it. The 2026-10-28 capture below, sampled every second, shows it starting at the disconnect.
- The heater load was at maximum at the time: `pwm=1.000` on `heater_box2` with both box NTCs above 75 °C.

### What this does not establish

`mcu_box2` is the MCU the host *names* in the timeout, not necessarily the device that raised the EOF. The EOF line carries no MCU name, and once the reactor stops reading, any MCU with an outstanding request can time out. Attribution to `mcu_box2` rests on that MCU's counters being the only degraded set in the same window, which is consistent but not proven.

The physical cause is also unresolved. A USB drop, a brown-out on the box's own supply, and a firmware hard fault that ends in an IWDG reset all look identical from the host, because a watchdog reset removes the CDC device from the bus.

## Monitor capture with one USB Box

**Runtime-confirmed (operator report, GitHub issue 159).** Firmware `01.01.07.01`, one USB Box on firmware `02.03.01.21` at USB path `2-1.4.2`, with the optional link monitor sampling once per second. A print start lost `mcu_box1` on 2026-10-28, about one minute into the adaptive mesh. The Box had cooled after the previous print, so `heater_box1` had been at `power=1.0` toward a 65 °C target for about ten minutes.

| Time | Source | Event |
|---|---|---|
| 05:55:32 | monitor | `heater_box1.target=65.0 temperature=50.88 power=1.0`, `heater_temp_a_box1=82.74`, `heater_temp_b_box1=96.91` |
| 05:59:32 | monitor | `mcu_box1` at baseline: `bytes_retransmit=9 rto=0.025 send_seq == receive_seq upcoming_bytes=0` |
| 05:59:35 | monitor | sequence numbers advance normally, `send_seq == receive_seq` |
| ≈05:59:35.5 | kernel | `usb 2-1.4.2: USB disconnect` |
| ≈05:59:36.0 | kernel | `usb 2-1.4.2: new full-speed USB device` (0.46 s after the disconnect) |
| 05:59:36 | monitor | `bytes_retransmit=44 rto=0.05`; `Got EOF when reading from device` |
| 05:59:37 | monitor | `bytes_retransmit=225 rto=0.2 upcoming_bytes=73` |
| ≈05:59:38.8 | kernel | second `USB disconnect` on `2-1.4.2` (3.3 s after the first) |
| ≈05:59:39.0 | kernel | second `new full-speed USB device` |
| 06:00:15 | klippy | `Timeout with MCU 'mcu_box1'`, `Lost communication with MCU 'mcu_box1'` |
| 06:00:16 | monitor | `heater_box1 temperature=58.13 power=1.0`, `heater_temp_a_box1=89.17`, `heater_temp_b_box1=102.11` |

The kernel times are dmesg monotonic seconds, aligned to wall-clock time through the timeout's `eventtime`.

### What this establishes

- The link went from baseline counters to lost within about one second. Retransmits started in the same second as the kernel disconnect, not before it.
- The Box disconnected twice. The second disconnect came while Klipper had stopped reading the Box (after the EOF and before any restart), so the host's Klipper did not cause it.
- `mcu` and `THR` stayed at baseline throughout.
- The same operator reports the same double re-enumeration in earlier drops on 2026-10-25. Across five drops, the Box heater was at full power while ramping from about 38–43 °C in three, all heaters were switching off at print end in one, and the Box was holding 65 °C during a print start in one. A rerun of the same plate, started with the Box already holding 65 °C (about 36 % heater power), completed without a drop, including print end.

### What this does not establish

Whether the Box MCU reset, and why. A supply sag or noise event on the Box while its heater switches, and a firmware stall ending in an IWDG reset, both fit the timeline. The heater correlation comes from five events on one machine and is not a controlled test.

## Regression baseline

Across the retained logs (2026-10-17 through 2026-10-24) there were two `Got EOF when reading from device` events, both on 2026-10-22 and 85 seconds apart (18:08:16 and 18:08:57), and exactly one `Timeout with MCU`. Every other day had zero of either. Baseline values in healthy operation, from the periodic `Stats` line:

- `bytes_retransmit` settles at 9 and stays there for every MCU;
- `bytes_invalid` is 0;
- `rto` is 0.025;
- `send_seq == receive_seq` and `transmit_seq == 2`;
- `upcoming_bytes` is 0;
- measured `freq` sits within roughly 40 ppm of `adj` (for example `84004872` against `84001929`).

Any departure from that baseline on a box MCU is worth recording.

## Observability gaps

**Runtime-confirmed** unless noted.

- Kernel USB evidence is effectively unavailable after the fact. `/var/log/kern.log` is empty, `syslog` contains no `usb` lines at all, and the `dmesg` ring held only 390 lines, all from the most recent boot. The 2026-10-22 window was already gone.
- `journalctl -k` needs root and the `qidi` user cannot read the journal.
- `reset_reason_get` is implemented on the box MCU and the running firmware is `02.03.01.21` with the full 140-command dictionary, but the command is never issued by any vendor module, so the box's reset reason is unrecorded by stock software. `reset_reason` appears in no log, no vendor shared object, and no klipper Python file. A value read from a Box has not yet been captured.
- After a Box link loss, `FIRMWARE_RESTART` does not reset that Box. **Static-recovered** from QIDI's `klippy/mcu.py`: `_restart_via_command` skips the `reset` command when the MCU's clock sync is no longer active and logs `Unable to issue reset command on MCU '<name>'`. The first reset reason read after reconnecting therefore reflects the Box's own last reset, not a host-issued one. Whether the firmware clears the STM32 reset flags after reading them is **Unresolved**.
- The `!!warnning:%s` MCU output has no matching handler in the retrieved vendor shared objects or `klippy` Python tree, so MCU-side I2C warnings are not known to be surfaced anywhere.
- `box_stepper <slot>` status exposes only `runout_button` and `rfid_state`, so feeder motion parameters are not readable from the running printer.

## Candidate causes and discriminating evidence

| Candidate | Distinguishing evidence |
|---|---|
| USB link loss (cable, connector, EMI on the shared hub tree, box-side 5 V sag while its heater switches) | Kernel `USB disconnect` for the box's path without a following software reset reason; the device reappears on the bus; `reset_reason` reads `PowerOn` / `NRST_Pin` |
| Box MCU lock-up ending in a watchdog reset | `reset_reason` reads `IndependentWatchdog`; the device re-enumerates and reads back to normal counters |
| Box MCU brown-out or external reset pulse | `reset_reason` reads `PowerOn` or `NRST_Pin` without a kernel disconnect (the device may reset without dropping off the bus) |
| Drive-by host-side serial stall | `Got EOF` absent before the timeout; other MCUs also stop progressing |

Only the first three need kernel or firmware-side evidence. The fourth is excluded by the 2026-10-22 capture.
