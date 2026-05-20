# QIDI Box active include wiring

## Active graph

Source: `config/printer.cfg`.

The active QIDI Box stack is loaded by the `Multi-color configuration` block:

```ini
[include box.cfg]
[multi_color_controller]
```

`[include box.cfg]` loads the vendor hardware objects, stock wrapper macros, heater objects, RFID readers, autofeed helper, and `box_extras` object.

`[multi_color_controller]` loads `multi_color_controller.so`, publishes the Moonraker `multi_color_controller` status object, and registers the public `MULTI_COLOR_*`, `QUERY_MULTI_COLOR`, `QUERY_SAVE_VARIABLES`, and saved-variable helper commands.

Active optimized macros are included earlier by:

```ini
[include tltg-optimized-macros/*.cfg]
```

Those macros call the vendor QIDI Box stack when box operations are needed.

## Objects created by `[include box.cfg]`

The stock include creates these QIDI Box objects:

```text
[mcu mcu_box1]
[box_stepper slot0]
[box_stepper slot1]
[box_stepper slot2]
[box_stepper slot3]
[heater_generic heater_box1]
[temperature_sensor box1_env]
[box_rfid card_reader_1]
[box_rfid card_reader_2]
[box_autofeed]
[box_extras]
```

`box.cfg` also defines stock wrapper macros including `T0`..`T15`, `UNLOAD_T0`..`UNLOAD_T15`, `UNLOAD_FILAMENT`, material helpers, and status helpers.

## Objects created by `[multi_color_controller]`

`[multi_color_controller]` creates the Moonraker-visible `multi_color_controller` object and registers high-level multi-color commands.

The captured machine reports:

```text
multi_color_controller.system.mode = local
multi_color_controller.hardware.box_count = 1
```

In local mode, `MULTI_COLOR_*` commands dispatch to local QIDI G-code commands such as `E_LOAD`, `E_UNLOAD`, `E_BOX`, `BOX_PRINT_START`, `SLOT_RFID_READ`, `CLEAR_FLUSH`, `CLEAR_OOZE`, and `CUT_FILAMENT`.

## Include-order effects

`box.cfg` is included after optimized macros in `config/printer.cfg`, but command names must still be unique across the final Klipper config. The vendor command names owned by `box.cfg`, `box_extras.so`, `box_stepper.so`, `box_autofeed.so`, `box_rfid.so`, and `multi_color_controller.so` should be treated as occupied when adding repo macros.

Stock QIDI Box object names visible through Moonraker include:

```text
box_extras
multi_color_controller
box_stepper slot0
box_stepper slot1
box_stepper slot2
box_stepper slot3
heater_generic heater_box1
temperature_sensor box1_env
mcu mcu_box1
```
