# Tools

[← Back to the README](../README.md)

Run these from Fluidd's console or macro controls after installing and restarting Klipper.

| Command | What it does |
|---|---|
| [`TLTG_TEST_PROBE CONFIRM=1`](#nozzle-load-cell-check) | Checks that the nozzle load cell responds to light pressure. No motion. |
| `TLTG_PROBE_ACCURACY_CENTER [SAMPLES=20]` | Homes, moves to `X195 Y195 Z10`, and runs Klipper's `PROBE_ACCURACY`. |
| `TLTG_CORNER_BED_SCREW_CHECK` | Homes, runs `Z_TILT_ADJUST`, then `SCREWS_TILT_CALCULATE`. |
| `SCREWS_TILT_CALCULATE` | Klipper's bed screw adjustment helper. |
| `TLTG_RESET_TOOL_MAPPINGS` | Restores QIDI Box tool-to-slot mappings to T0 → 1A, T1 → 1B, and so on. Idle only. |
| [`TLTG_FILAMENT_SENSOR ENABLE=0`](#external-spool-runout-sensor) | Stops the external spool's runout sensor from pausing prints. |
| [`TLTG_BOX_MOTION`](qidi-box.md#load-and-unload-speed) | Shows or sets QIDI Box load and unload speeds. |

## Nozzle load-cell check

`TLTG_TEST_PROBE CONFIRM=1` checks that the nozzle load cell responds to light pressure. It does not move, home, heat, or change calibration. In Fluidd's macro controls, enter `1` in the `CONFIRM` field.

**Before you start:** the printer must be idle with all heaters off, and the nozzle and bed below 40 °C. Make sure you can reach the nozzle and it's clear of the bed. **Do not home to prepare for this test.**

Follow the console prompts. It takes about 40 seconds:

1. Leave the nozzle alone through `DO NOT TOUCH` and `Measuring...`.
2. At `GET READY TO PRESS`, get ready. At `PRESS`, press lightly upward on the nozzle and hold.
3. When told to stop pressing, let go and leave the nozzle alone through `DO NOT TOUCH` and `Measuring...`.

The result is one of:

- `RESPONSE_DETECTED`: the readings look correct.
- `NO_RELIABLE_RESPONSE`: the sensor did not respond as expected.
- `INCONCLUSIVE`: there was not enough difference between pressing and not pressing to tell, or the test stopped early.

> [!WARNING]
> **A detected response does not verify the homing trigger or certify safe homing.** For any other result, do not press harder, and do not home or probe until the cause is understood. `QUERY_PROBE` cannot check this sensor. `TLTG_PROBE_ACCURACY_CENTER` and `TLTG_CORNER_BED_SCREW_CHECK` both home, so they are not safe tests for a suspected failed sensor.

## External spool runout sensor

```gcode
TLTG_FILAMENT_SENSOR ENABLE=0
TLTG_FILAMENT_SENSOR ENABLE=1
```

`ENABLE=0` stops the external spool from pausing the print when its runout sensor trips. The toolhead sensor still reports its events and the external spool's runout status. `ENABLE=1` turns automatic pausing back on. The setting goes back to enabled when Klipper restarts. QIDI Box runout handling stays on either way.

> [!WARNING]
> With `ENABLE=0`, ignore filament-runout warnings on the printer screen. Don't interact with them; the print continues, and the warning only reports the sensor event.

The console shows when the toolhead sensor trips and whether it will pause.

![Filament sensor console output](../.github/images/tltg-filament-sensor-console.png)
