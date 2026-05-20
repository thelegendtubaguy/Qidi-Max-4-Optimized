# QIDI Box autofeed and anti-wrap reference

## Source

Harness outputs:

- `tmp/qidi-box-reversing/box_autofeed_probe.json`
- `tmp/qidi-box-reversing/box_autofeed_methods_probe.json`

Compiled symbol priority:

- `docs/qidi_box/qidi_box_compiled_symbol_map.md`

The harness instantiated `box_autofeed.so` with fake Klipper objects and fake MCU command objects. It captured registered G-code commands, config keys, runtime fields, MCU command formats, and payloads without moving hardware.

## Registered G-code commands

| Command | Handler | Description from module |
|---|---|---|
| `MCB_CONFIG` | `cmd_config` | `配置 mcb autofeed 模块 (动态切换 SLOT -> stepper_mcu)` |
| `MCB_QUERY` | `cmd_query` | `开始限位轮询（发到当前 stepper_mcu）` |
| `SET_LIMIT_A` | `cmd_SET_LIMIT_A` | `设置虚拟限位状态，并同步到当前 stepper_mcu` |
| `MCB_AUTO_START` | `cmd_auto_start` | `启动自动进料，支持 SLOT=slotN 动态切换` |
| `MCB_AUTO_ABORT` | `cmd_auto_abort` | `中止自动进料` |

## Config keys and defaults

| Field | Module default | Captured stock value | Notes |
|---|---:|---:|---|
| `limit_pin` | none | `^!mcu_box1:PB0` | anti-wrap/limit sensor pin |
| `debounce_us` | `200000.0` | `200000.0` | debounce interval in microseconds |
| `limit_polarity` | `0` | `0` | passed as `invert` to `mcb_query` |
| `default_ticks` | `8400` | `8400` | polling/rest interval ticks |
| `v_feed` | `2000` | `100` | feed-assist speed input |
| `lmax` | `10000` | `120` | max feed-assist length input |
| `dir` | `1` | `0` | feed-assist direction |
| `a_feed` | `0.0` | `0.0` | feed-assist acceleration input |

`v_feed`, `lmax`, `dir`, and `a_feed` are visible config knobs for the autofeed helper, not for the main `EXTRUDER_LOAD` / `EXTRUDER_UNLOAD` path owned by `box_stepper.so`.

## Runtime fields

Harnessed fields after initialization:

| Field | Captured value |
|---|---|
| `a_pin` | `^!mcu_box1:PB0` |
| `debounce_us` | `200000.0` |
| `limit_polarity` | `0` |
| `default_ticks` | `8400` |
| `v_feed` | `100` |
| `lmax` | `120` |
| `dir` | `0` |
| `a_feed` | `0.0` |
| `limit_a_state` | `0` before method probe, `1` after method probe setup |
| `wrapping_num` | `0` |
| `bind_stepper` | `slot-1` before slot selection, `slot0` after method probe setup |
| `active_slot` | `None` before slot selection, `slot0` after method probe setup |
| `_last_limit_a_event_time` | `0.0` |
| `stepper_dev` | `None` before method probe setup, fake device after setup |
| `irq_btn` | `None` |

## MCU config and command formats

The module adds a config command:

```text
mcb_config oid=<oid>
```

The module registers MCU response callbacks:

| MCU response | Handler |
|---|---|
| `MCB_STATE` | `_on_state` |
| `MCB_DONE` | `_on_done` |
| `MCB_ERROR` | `_on_error` |

The module resolves per-MCU command objects with these formats:

```text
mcb_config_stepper oid=%c stepper_oid=%c
mcb_query oid=%c clock=%u rest_ticks=%u retransmit_count=%c invert=%c
mcb_auto_start oid=%c v=%u a=%u lmax=%u dir=%i enable=%i invert=%i
mcb_auto_abort oid=%c
set_limit_a oid=%c state=%c
```

## Harnessed MCU payloads

`mcb_config_stepper` payloads:

```text
[12, 77]
[12, 77]
```

`mcb_query` payloads:

```text
[12, 0, 8400, 0, 0]
[12, 0, 8400, 0, 0]
```

Payload field order:

```text
[oid, clock, rest_ticks, retransmit_count, invert]
```

`mcb_auto_start` payloads:

```text
[12, 10000, 20000, 12000, 0, 47, 1]
[12, 11000, 21000, 13000, 1, 47, 1]
```

Payload field order:

```text
[oid, v, a, lmax, dir, enable, invert]
```

The fake harness uses a step distance that converts the stock-visible millimeter values into MCU step units. The first payload corresponds to `v=100`, `a=200`, `lmax=120`, `dir=0`, `enable_pin=PC15`, `invert=1` under the fake stepper environment.

`mcb_auto_abort` payloads:

```text
[12]
[12]
```

`set_limit_a` payloads:

```text
[12, 0]
[12, 0]
[12, 1]
```

Payload field order:

```text
[oid, state]
```

## Pin encoding observed in harness

The fake setup encoded `enable_pin=!mcu_box1:PC15` as:

| Encoded field | Value |
|---|---:|
| `enable` | `47` |
| `invert` | `1` |

`PC15 -> 47` matches STM32-style bank/offset encoding where port C starts at `32` and pin `15` adds `15`.

## Function priority from symbol map

| Symbol | Size | Relevance |
|---|---:|---|
| `cmd_auto_start` | `0x3afc` | parses G-code, selects slot/device, dispatches auto-start |
| `auto_start` | `0x33d8` | converts motion units and sends `mcb_auto_start` |
| `limit_a_event` | `0x1e20` | handles limit sensor events |
| `wrapping_operate` | `0x1aac` | anti-wrap operation path |
| `cmd_config` | `0xef4` | selects/configures slot stepper MCU |
| `cmd_query` | `0x860` | starts limit polling |
| `wrapping_detection` | `0x5cc` | public wrapping-detection entry point |
| `cmd_SET_LIMIT_A` | `0x3cc` | sets virtual limit state and syncs to active device |

## Runtime command captures

Runtime captures in `docs/qidi_box/qidi_box_runtime_observations.md` executed these commands while the printer was idle and synced to `slot2`:

```gcode
MCB_CONFIG SLOT=slot2
MCB_QUERY
SET_LIMIT_A STATE=0
SET_LIMIT_A STATE=1
SET_LIMIT_A STATE=0
MCB_AUTO_ABORT
```

Observed behavior:

- Moonraker accepted each command with `{"result": "ok"}`.
- `saved_variables.diff` was empty.
- `print_stats.state` stayed `standby`; `idle_timeout.state` stayed in the non-printing ready/idle state captured by each snapshot.
- `multi_color_controller.operation.current` stayed `-1` and `operation.error` stayed `None`.
- `multi_color_controller.sensors.pressure_sensor` stayed `0`.
- `box_autofeed` published `{}` through Moonraker object status.
- No `MCB_STATE`, `MCB_DONE`, or `MCB_ERROR` payload appeared in captured log tails.

This runtime capture confirms the accepted non-motion command path for config/query/virtual-limit commands and the idle abort command path for `MCB_AUTO_ABORT`. It does not recover live MCU callback payloads because no `MCB_AUTO_START` or physical anti-wrap event occurred.
