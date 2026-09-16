# Corrected CS1237 firmware findings

## Status and provenance

This local investigation corrects the earlier command-handler mapping in [the original research](reverse-engineering.md). No printer was contacted, flashed, heated, moved, or configured. Static recovery and synthetic execution establish code paths, not physical safety, sensor performance, or PA accuracy.

The input was `QD_MAX4_01.01.06.05_20260804_Release.zip`:

| Artifact | SHA-256 |
|---|---|
| Release ZIP | `b1826d1aed274c7233b4a23a3a3e5c0b4e9655c5d03188a8b6f3561f0d3f2de7` |
| THR `02.02.01.08` | `1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62` |
| `cs1237.so` | `7beb56413a902356d0aee2d0580e820342083b3b7f7194d1f5d7217f4b7ff4b5` |
| Current `air.so` | `6d7af36d1061216b7aa5f1cd0eb9ae1c25158f8df9926ec7e69be7e411c67d69` |

THR and CS1237 hashes match the earlier analysis. The current air extension differs from the earlier capture. The corrected interpretation is not a firmware upgrade.

## Command table correction

**Static-recovered:** THR flash base is `0x08008000`. The command table at `0x080101c4` has 16-byte records with the handler at offset `+12`, not immediately before the message ID. The dispatcher confirms that offset. Dictionary decompression at file offset `0x7534`, all 89 command records, response IDs, compiled host bindings, and synthetic execution corroborate the corrected map.

| Command | ID | Handler | Recovered behavior |
|---|---:|---|---|
| `query_cs1237_config_r` | 80 | `0x0800d738` | GPIO configuration-register read through `0x0800d4c8` |
| `query_cs1237_begin` | 81 | `0x0800d780` | Configures ADC |
| `query_cs1237_zero_read_only` | 82 | `0x0800bd74` | Returns stored reference without acquisition |
| `query_cs1237_zero` | 83 | `0x0800dc20` | Ten successful reads; updates probing reference |
| `cs1237_setup_home` | 84 | `0x0800b91c` | Arms or clears homing state |
| `query_cs1237` | 85 | `0x0800c00c` | Starts or stops periodic polling; no host stream |
| `query_cs1237_home_state` | 86 | `0x0800bd28` | Returns homing bit and trigger clock |
| `query_cs1237_read` | 87 | `0x0800dbcc` | Attempts ADC read; returns sample buffer |
| `config_cs1237` | 88 | `0x0800d478` | Allocates/configures sensor and pins |

Earlier assignments of `0x0800bd28` to raw reads and `0x0800bd74` to zeroing were incorrect. Earlier configuration-read addresses and the proposed `0x08003000` image base are also superseded.

## Acquisition and reference state

**Static-recovered / harness-confirmed:** raw handler `0x0800dbcc` calls reader `0x0800db14`, whose bit-reader `0x0800da7c` clocks 24 data bits plus three additional clocks. Advertised `reg` and `read_len` parameters are unused. Response `query_cs1237_data` has ID `-8`.

- A ready conversion updates the returned buffer.
- Not-ready input returns the old buffer, or an empty payload if uninitialized.
- Zero/all-ones results cause retries inside the MCU reader. Four zeros retain the old buffer; the fourth all-ones result can escape as `ffffff00`.
- `0x800000` enters shutdown reason 39 (`weight_error`); the already-shutdown path returns the sentinel.
- Tested raw paths did not modify stored zero or homing references. This is not proof of safe concurrent probing.

**Compiled-host-harness / MCU-harness-confirmed:** `read_origin_data()` and `zero_home()` both send `query_cs1237_zero`. The zeroing handler attempts ten successful ADC reads, changes SRAM `0x20000174` and object reference `+0x88`, and emits response `-12`. Permanently not-ready synthetic input exhausts the emulator budget without returning. The read-only reference command emits response `-13` without acquisition.

The old origin adapter's passive-read assumption is unsafe. Its disabled code is not corrected by this documentation change and must not be enabled.

## Polling and host transport

**Static-recovered / harness-confirmed:** nonzero `query_cs1237` `rest_ticks` selects a fixed 36,000-tick interval (0.5 ms at 72 MHz); zero stops polling. Timer callback `0x0800b6ec` marks work; task branch `0x08008e92` reads ADC and conditionally performs homing filtering/trigger decisions. Requested host values do not set a variable ADC polling period.

**Static-recovered:** `sensor_bulk_data` is used by other sensors; no CS1237 producer was identified. Expected `cs1237_data` is absent from the dictionary. **Compiled-host-harness-confirmed:** current `air.PrinterAirProbe.add_client()` remains a no-op.

**Source-inspected:** serial `#sent_time` is acknowledgement bookkeeping, not a unique conversion or request token. Equal timestamps and values are not grounds to discard a response. Historical counts after such filtering do not independently establish transport loss.

**Host-harness-confirmed:** the extracted `SerialRetryCommand` sends once for an immediate response, twice if the response arrives during its initial 10 ms wait, and six times with no response before failing after waits totaling 0.31 s. A capture harness must not use this synchronous retry wrapper.

## Evidence limits and reproduction

Local evidence consisted of `decode_protocol.py` and `protocol-map.json`, focused `thr-*.txt` disassembly, `host_probe.py`, `air_probe.py`, `emulate_cs1237.py`, and `edge_cases.py` with their results. Nine initial synthetic MCU cases, ten additional bit/control-flow cases, and three retry-wrapper scenarios passed their assertions. These scratch scripts and extracted vendor binaries are not bundled in this change; this document preserves their conclusions and provenance, not a self-contained reproducibility package. Retaining a sanitized offline reproduction is an implementation task before hardware qualification.

Host harnesses ran the compiled ARM64 extension in Python 3.9 containers with networking disabled, read-only filesystem/mounts, dropped capabilities, and resource limits. MCU execution used Unicorn 2.1.4 and Capstone 5.0.9 with synthetic SRAM/GPIO, ADC values, scheduler calls, response sending, and cycle counter. Peripheral behavior was not reproduced. Whole-image Radare2 analysis crashed; focused disassembly and independent checks supplied the evidence instead.

Historical heated captures, force response, cleanup, and repeatability failures remain observations. Their cache-only and passive-origin explanations are withdrawn. Actual stale-read frequency, sustained usable rate, probing safety, and useful PA discrimination remain hardware questions.

## Next experiment, not authorization

First implement and test a source-gated, bounded nonblocking raw collector. Keep one outstanding request, an explicit deadline, no host retransmission, and all response records. Check homing status and stored reference through the correctly mapped read-only commands before and after capture. Do not configure, zero, arm homing, or start periodic polling.

Only with separate authorization and the printer-state guard should the first physical run occur: idle and cold, without movement or extrusion. Later conditioned extrusion and repeated/reordered K trials must retain bounded extrusion, chute clearing, state restoration, and printed comparison. A repeatable useful PA range is sufficient; absence of perfect timestamps alone does not prove infeasibility.
