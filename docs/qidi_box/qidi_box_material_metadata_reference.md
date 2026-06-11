# QIDI Box material metadata reference

## Source

Captured file:

- `tmp/qidi-box-reversing/20260507-135653-printer-capture/root/home/qidi/printer_data/config/officiall_filas_list.cfg`

Runtime consumers:

- `multi_color_controller.so`
- `qidiclient`
- saved variables: `filament_slotN`, `color_slotN`, `vendor_slotN`

## Lookup path

Slot metadata is stored in saved variables:

```text
filament_slotN = <fila id>
color_slotN = <color id>
vendor_slotN = <vendor id>
```

The IDs are resolved through `officiall_filas_list.cfg` sections:

- `[fila<ID>]`
- `[colordict]`
- `[vendor_list]`

Runtime status in `docs/qidi_box/qidi_box_runtime_observations.md` showed:

- `filament_slot2 = 18` -> `[fila18]` -> `ASA`
- `color_slot2 = 2` -> `[colordict] 2 = #060606`
- `vendor_slot2 = 0` -> `[vendor_list] 0 = Generic`

## Filament ID map

| ID | Filament | Type | Nozzle min | Nozzle max | Box min | Box max |
|---:|---|---|---:|---:|---:|---:|
| `1` | `PLA Rapido` | `PLA` | `190` | `240` | `0` | `0` |
| `2` | `PLA Matte` | `PLA` | `190` | `240` | `0` | `0` |
| `3` | `PLA Metal` | `PLA` | `190` | `240` | `0` | `0` |
| `4` | `PLA Silk` | `PLA` | `190` | `240` | `0` | `0` |
| `5` | `PLA-CF` | `PLA-CF` | `210` | `250` | `0` | `0` |
| `6` | `PLA-Wood` | `PLA` | `190` | `240` | `0` | `45` |
| `7` | `PLA Basic` | `PLA` | `190` | `240` | `0` | `0` |
| `8` | `PLA Matte Basic` | `PLA` | `190` | `230` | `0` | `0` |
| `9` | empty | empty | empty | empty | empty | empty |
| `10` | `Support For PLA` | `PLA-S` | `210` | `240` | `0` | `0` |
| `11` | `ABS Rapido` | `ABS` | `240` | `280` | `0` | `45` |
| `12` | `ABS-GF` | `ABS-GF` | `240` | `280` | `0` | `45` |
| `13` | `ABS-Metal` | `ABS` | `240` | `280` | `0` | `45` |
| `14` | `ABS-Odorless` | `ABS` | `240` | `280` | `0` | `45` |
| `15` | `TPU-GF` | `TPU-GF` | `240` | `270` | `0` | `0` |
| `16` | empty | empty | empty | empty | empty | empty |
| `17` | empty | empty | empty | empty | empty | empty |
| `18` | `ASA` | `ASA` | `240` | `280` | `0` | `45` |
| `19` | `ASA-Aero` | `ASA-AERO` | `240` | `280` | `0` | `45` |
| `20` | `ASA-CF` | `ASA-CF` | `240` | `280` | `0` | `45` |
| `21` | empty | empty | empty | empty | empty | empty |
| `22` | empty | empty | empty | empty | empty | empty |
| `23` | `PC` | `PC` | `240` | `280` | `0` | `0` |
| `24` | `UltraPA` | `UltraPA` | `260` | `300` | `0` | `55` |
| `25` | `PA6-CF` | `PA6-CF` | `260` | `300` | `0` | `65` |
| `26` | `UltraPA-CF25` | `UltraPA-CF25` | `300` | `320` | `0` | `65` |
| `27` | `PA12-CF` | `PA12-CF` | `260` | `300` | `0` | `65` |
| `28` | empty | empty | empty | empty | empty | empty |
| `29` | empty | empty | empty | empty | empty | empty |
| `30` | `PAHT-CF` | `PAHT-CF` | `300` | `320` | `0` | `65` |
| `31` | `PAHT-GF` | `PAHT-GF` | `300` | `320` | `0` | `65` |
| `32` | `Support For PAHT` | `PAHT-S` | `260` | `280` | `0` | `65` |
| `33` | `Support For PET/PA` | `PA-S` | `260` | `280` | `0` | `65` |
| `34` | `PC/ABS-FR` | `PC-ABS-FR` | `260` | `280` | `0` | `50` |
| `35` | `TPEE` | `TPEE` | `230` | `260` | `0` | `0` |
| `36` | `PEBA` | `PEBA` | `230` | `260` | `0` | `0` |
| `37` | `PET-CF` | `PET-CF` | `280` | `320` | `0` | `65` |
| `38` | `PET-GF` | `PET-GF` | `280` | `320` | `0` | `50` |
| `39` | `PETG Basic` | `PETG` | `240` | `280` | `0` | `45` |
| `40` | `PETG-Tough` | `PETG` | `240` | `275` | `0` | `45` |
| `41` | `PETG Rapido` | `PETG` | `220` | `270` | `0` | `45` |
| `42` | `PETG-CF` | `PETG-CF` | `240` | `270` | `0` | `45` |
| `43` | `PETG-GF` | `PETG-GF` | `240` | `270` | `0` | `45` |
| `44` | `PPS-CF` | `PPS-CF` | `300` | `350` | `0` | `65` |
| `45` | `PETG Translucent` | `PETG` | `240` | `280` | `0` | `45` |
| `46` | `PPS-GF` | `PPS-GF` | `300` | `350` | `0` | `65` |
| `47` | `PVA` | `PVA` | `210` | `250` | `0` | `50` |
| `48` | `TPU-AERO 64D` | `TPU-AERO 64D` | `200` | `250` | `0` | `0` |
| `49` | `TPU-Aero` | `TPU-AERO` | `200` | `250` | `0` | `0` |
| `50` | `TPU 95A-HF` | `TPU` | `200` | `250` | `0` | `0` |

## Color ID map

| ID | Hex color |
|---:|---|
| `1` | `#FAFAFA` |
| `2` | `#060606` |
| `3` | `#D9E3ED` |
| `4` | `#5CF30F` |
| `5` | `#63E492` |
| `6` | `#2850FF` |
| `7` | `#FE98FE` |
| `8` | `#DFD628` |
| `9` | `#228332` |
| `10` | `#99DEFF` |
| `11` | `#1714B0` |
| `12` | `#CEC0FE` |
| `13` | `#CADE4B` |
| `14` | `#1353AB` |
| `15` | `#5EA9FD` |
| `16` | `#A878FF` |
| `17` | `#FE717A` |
| `18` | `#FF362D` |
| `19` | `#E2DFCD` |
| `20` | `#898F9B` |
| `21` | `#6E3812` |
| `22` | `#CAC59F` |
| `23` | `#F28636` |
| `24` | `#B87F2B` |

## Vendor ID map

| ID | Vendor |
|---:|---|
| `0` | `Generic` |
| `1` | `QIDI` |
