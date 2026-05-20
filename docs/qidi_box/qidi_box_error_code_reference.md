# QIDI Box error code reference

## Source

String captures:

- `tmp/qidi-box-reversing/20260507-135653-printer-capture/analysis/strings/box_stepper.so.strings.txt`
- `tmp/qidi-box-reversing/20260507-135653-printer-capture/analysis/strings/box_autofeed.so.strings.txt`
- `tmp/qidi-box-reversing/20260507-135653-printer-capture/analysis/strings/box_extras.so.strings.txt`

Runtime captures in `docs/qidi_box/qidi_box_runtime_observations.md` did not trigger any `QDE_004_*` errors.

## Error strings by owner

| Code | Owner module | Message |
|---|---|---|
| `QDE_004_001` | `box_stepper.so` | `Slot loading failure, please check the trigger, please reload %s.` |
| `QDE_004_002` | `box_stepper.so` | `Extruder has been loaded, cannot load %s.` |
| `QDE_004_003` | `box_stepper.so` | `Slot unloading failure, please unload %s again.` |
| `QDE_004_004` | `box_stepper.so` | `Please unload extruder first.` |
| `QDE_004_005` | `box_stepper.so` | `Please load the filament to %s first.` |
| `QDE_004_006` | `box_stepper.so` | `Extruder loading failure.` |
| `QDE_004_007` | `box_stepper.so` | `Extruder not loaded.` |
| `QDE_004_008` | `box_stepper.so` | `Extruder unloading failure.` |
| `QDE_004_009` | `box_stepper.so` | `Extruder unloading failure.` |
| `QDE_004_010` | `box_extras.so` | `The current feeding status is incorrect. Please exit the filament from the extruder.` |
| `QDE_004_011` | `box_stepper.so` | `Detected that filament have been loaded, please unload filament first` |
| `QDE_004_013` | `box_autofeed.so` | `Detected wrapping filament,please check the filament.` |
| `QDE_004_014` | `box_extras.so` | `Parameter setting error, please reset.` |
| `QDE_004_016` | `box_stepper.so` | `The filament has been exhausted, please load the filament to %s.` |
| `QDE_004_017` | `box_stepper.so` | `Filament flush failed, please clean and then load the filament in %s.` |
| `QDE_004_018` | `box_stepper.so` | `No filament specified, %s cannot be automatically replaced.` |
| `QDE_004_019` | `box_stepper.so` | `Please check if your PTFE Tube is bent` |
| `QDE_004_020` | `box_stepper.so` | `Detected that the filament has been unloaded, please reload.` |
| `QDE_004_021` | `box_extras.so` | `Unable to recognize loaded filament.` |
| `QDE_004_022` | `box_stepper.so` | `No replaceable slot found.` |
| `QDE_004_023` | `box_extras.so` | `Auto reload failed.` |
| `QDE_004_024` | `box_stepper.so` | `The filament failed to enter the extruder.` |
| `QDE_004_025` | `box_stepper.so` | `Extruder unloading failure.` |

`QDE_004_012` and `QDE_004_015` were not found in the captured module strings.

## Behavior grouping

| Behavior area | Codes |
|---|---|
| Slot load/pre-gate failure | `QDE_004_001`, `QDE_004_005`, `QDE_004_016` |
| Extruder already loaded / wrong feed state | `QDE_004_002`, `QDE_004_004`, `QDE_004_010`, `QDE_004_011` |
| Slot unload/eject failure | `QDE_004_003` |
| Extruder load failure | `QDE_004_006`, `QDE_004_024` |
| Extruder unload failure | `QDE_004_007`, `QDE_004_008`, `QDE_004_009`, `QDE_004_020`, `QDE_004_025` |
| Autofeed/anti-wrap failure | `QDE_004_013` |
| Config/parameter failure | `QDE_004_014` |
| Filament recognition/changeover failure | `QDE_004_017`, `QDE_004_018`, `QDE_004_021`, `QDE_004_022`, `QDE_004_023` |
| PTFE/path failure | `QDE_004_019` |

## Runtime gaps

Exact predicates for each code still require live captures around failure cases.
