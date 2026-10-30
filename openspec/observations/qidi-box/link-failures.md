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

The physical cause is also unresolved. A USB drop, a brown-out on the box's own supply, and a firmware hard fault that ends in an IWDG reset all end in the same kernel disconnect. They differ only in what precedes it; see the candidate table below.

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
- The Box disconnected twice. The second disconnect came while Klipper had stopped reading the Box (after the EOF and before any restart), so the host's Klipper did not cause it. The same pair follows every Box start, including a cold power-on: the startup path enumerates as `0483:5740` for about 2.5 s, then hands over to the Klipper application (see `mcu-firmware.md`, Reset reason). So the Box MCU restarted. A USB-only glitch with the MCU still running is not expected to produce the pair.
- `mcu` and `THR` stayed at baseline throughout.
- The same operator reports the same double re-enumeration in earlier drops on 2026-10-25. Across five drops, the Box heater was at full power while ramping from about 38–43 °C in three, all heaters were switching off at print end in one, and the Box was holding 65 °C during a print start in one. A rerun of the same plate, started with the Box already holding 65 °C (about 36 % heater power), completed without a drop, including print end.

### What this does not establish

Why the Box MCU reset. A supply sag or noise event on the Box while its heater switches, and a firmware stall ending in an IWDG reset, both fit the timeline. The monitor samples once per second, which cannot resolve whether the Box went silent for a watchdog period before the disconnect. The heater correlation comes from five events on one machine and is not a controlled test.

## Drop at print end with the serial history

**Runtime-confirmed (2026-10-29, two USB Boxes, link monitor with serial history).** A print reached its end macros with `heater_box2` holding its 65 °C target at a steady `pwm=0.012`. Host times below are monotonic seconds, the same clock as dmesg.

| Host time | Source | Event |
|---|---|---|
| 3883.146 | Box 2 history | Last heater command to Box 2 (`queue_digital_out oid=40`, scheduled for Box clock 3873008134) |
| 3886.6 → 3889.4 | klippy | No `Stats` lines: the host was running the print-end macros, including several `SAVE_VARIABLE` writes, and sent nothing to either Box from 3886.86 (Box 2) and 3887.24 (Box 1) until 3889.4 |
| 3888.163 | Box 2 history | Last message from Box 2; its 0.3 s ADC reports were due again at 3888.287 and never arrived |
| ≈3888.245 | derived | Box clock 4293032499: the heater command's 5 s `max_duration` (`MAX_HEAT_TIME = 5.0` in QIDI's `heaters.py`) runs out |
| ≈3888.268 | derived | Box 2's 32-bit clock wraps, from a fit of seven `clock` replies (residuals under 35 µs) |
| 3888.696 | kernel | Box 2 `USB disconnect`, 0.533 s after its last message, against a normal maximum gap of 0.18 s |
| 3889.416 / 3892.280 | kernel | Startup stage, then the application: Box 2 restarted |
| 3929.518 | Box 1 history | The host sends `emergency_stop` to every MCU after the timeout |
| 3930.167 | kernel | Box 1 `USB disconnect`, 0.65 s later, followed by the startup stage |

After `FIRMWARE_RESTART`, both Boxes read `IndependentWatchdog`. Box 1 had read `PowerOn` before the print and was reset by nothing else, so receiving `emergency_stop` ended in an IWDG reset. Box 2 had read `Software`.

### What this establishes

- On firmware `02.03.01.21`, a commanded MCU shutdown (`emergency_stop`) ends in an IWDG reset instead of the MCU remaining connected in the shutdown state.
- Box 2 went silent inside the 0.12 s window that contains both the heater's `max_duration` expiry and its clock wrap, then reset the same way. A heater `max_duration` expiry is an MCU shutdown in Klipper, so this drop fits the same shutdown-ends-in-reset behavior.
- Klipper resends an unchanged heater value only every `0.75 * MAX_HEAT_TIME` (3.75 s) and suppresses changes under 0.05. A Box heater at a steady duty, including full power, is resent at the first sensor reading after that point; with readings about every 0.75 s that is about every 4.5 s against a limit 5 s after the last send's `pwm_time`, so a host stall of 0.5–1.25 s, depending on where it falls in the cycle, can reach the limit.
- The Box heater's control sensor is `AHT20_F` (QIDI's compiled `aht20_f.so`) on the Box MCU's I2C bus. The serial history shows a host-initiated `i2c_read`/`i2c_write` pair about every 0.75 s, each followed by the heater's `queue_digital_out` when the value changed or a resend was due, so Box heater control runs on Klipper's main reactor. The bed and extruder use ADC sensors, whose reports are handled on the serial thread. That is why a reactor stall starves the Box heaters and not the main heaters.

### What this does not establish

- Why the shutdown path ends in a watchdog reset rather than a reported shutdown at runtime; disassembly points to the MCB shutdown handler (see `mcu-firmware.md`, Shutdown handling).
- Whether the clock wrap plays any part; the `max_duration` expiry alone accounts for a shutdown at that moment.
- That the requester's drops follow the same chain; their timing (heater at a steady full power during print start, and at print end) fits it.

## Controlled power and link loss

**Runtime-confirmed (2026-10-29, two USB Boxes, printer idle, link monitor on).** The Boxes are daisy-chained: Box 1's USB hub (`2-1.4`) connects to the printer, with Box 1's MCU on its port 2 (`2-1.4.2`); Box 2's hub (`2-1.4.1`) connects to Box 1's hub, with Box 2's MCU at `2-1.4.1.2`. Box 1 was switched off for about 5 s and back on. That cut Box 1's MCU power and, through its hub, Box 2's USB link, while Box 2's MCU stayed powered.

| | Box 1 (power loss) | Box 2 (link loss, MCU running) |
|---|---|---|
| Normal gap between received messages (8 s of history) | median 0.08 s, max 0.15 s | median 0.09 s, max 0.17 s |
| Last received message before the first USB error | 0.10 s | 0.06 s |
| Re-enumeration | `0483:5740` startup stage, then the application 2.6 s later | application only, once |
| Reset reason afterwards | `PowerOn` | `Software`, unchanged from before the test |

The hubs logged `clear tt ... error -71` from 0.15 s before the kernel's `USB disconnect` line, so the first USB error, not the disconnect line, marks when the link failed. Neither Box went quiet for longer than its normal message gap before the failure. A watchdog stall is expected to show a silence of about one reload period (nominally 512 ms) instead.

Because the Boxes share a USB chain, a power loss or hub fault in one Box also drops every Box behind it, without resetting their MCUs.

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
- `reset_reason_get` is never issued by any vendor module, so stock software does not record the Box's reset reason. The optional link monitor reads it. The firmware never clears the STM32 reset flags, so the reading is the highest-ranked reset since the Box was last powered on, not the most recent one (see `mcu-firmware.md`, Reset reason). It only attributes a drop when the Box was powered off and on beforehand.
- After a Box link loss, `FIRMWARE_RESTART` does not reset that Box. **Static-recovered** from QIDI's `klippy/mcu.py`: `_restart_via_command` skips the `reset` command when the MCU's clock sync is no longer active and logs `Unable to issue reset command on MCU '<name>'`.
- The Box MCU's last received message is not recorded with sub-second timing. Klipper's shutdown dump lists the send and receive queues only for MCUs that are still connected, and the link monitor samples counters once per second.
- The `!!warnning:%s` MCU output has no matching handler in the retrieved vendor shared objects or `klippy` Python tree, so MCU-side I2C warnings are not known to be surfaced anywhere.
- `box_stepper <slot>` status exposes only `runout_button` and `rfid_state`, so feeder motion parameters are not readable from the running printer.

## Candidate causes and discriminating evidence

| Candidate | Distinguishing evidence |
|---|---|
| USB link loss with the MCU still running (cable, connector, EMI on the shared hub tree) | Kernel `USB disconnect` followed by a single enumeration as `1d50:614e`, without the `0483:5740` startup stage |
| Box MCU lock-up ending in a watchdog reset | `reset_reason` reads `IndependentWatchdog` when it read `PowerOn` or `Software` before the drop. The Box stops sending while still attached, for about one IWDG reload period (nominally 512 ms), before the kernel `USB disconnect` |
| Box MCU stuck in the FM17550 RFID wait (see `mcu-firmware.md`, Stall sources) | As for a watchdog reset, and the Box's last commands in the serial history are `query_fm17550` or `fm17550_read_card_cb` / `fm17550_write_card_cb` |
| Box MCU brown-out, power loss, or external reset pulse | `reset_reason` still reads `PowerOn` when it read `PowerOn` before the drop and no `FIRMWARE_RESTART` reached the Box since. Box messages continue until the kernel `USB disconnect` |
| Drive-by host-side serial stall | `Got EOF` absent before the timeout; other MCUs also stop progressing |

`reset_reason` separates the second and third rows only from a known baseline: the Box powered off and on, so it starts at `PowerOn`, and a reading taken after the drop, before any `FIRMWARE_RESTART`. A brown-out sets only `BORRSTF` and `PINRSTF`; the firmware does not test `BORRSTF`, and `PORRSTF` from the earlier power-on still outranks `PINRSTF`, so the reading stays `PowerOn`. Last-message timing, at well under the reload period and aligned with the kernel disconnect time, would separate the two rows without a baseline. The 2026-10-28 capture shows the startup-stage re-enumeration, which rules out the first row for that drop. The fourth row is excluded by the 2026-10-22 capture.
