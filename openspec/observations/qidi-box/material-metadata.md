# QIDI Box material metadata observations

Numeric runtime mappings apply to QIDI Max 4 firmware `01.01.06.04`; the `.05` missing-key behavior is config-confirmed from `klipper/klippy/extras/save_variables.py`.

Saved variables store IDs:

```text
filament_slotN = <filament ID>
color_slotN = <color ID>
vendor_slotN = <vendor ID>
```

`config/officiall_filas_list.cfg` resolves `[fila<ID>]`, `[colordict]`, and `[vendor_list]`. Drying presets are separate in `drying.conf`.

Runtime-confirmed slot 2 mapping:

```text
filament_slot2 = 18 -> ASA
color_slot2 = 2 -> #060606
vendor_slot2 = 0 -> Generic
```

Firmware `01.01.06.05` changes only the fallback for absent `filament_slot0..16` and `color_slot0..16` keys from ID `0` to ID `1`. Existing persisted keys are unchanged, `vendor_slot0..16` fallback behavior is unchanged, and `config/officiall_filas_list.cfg` retains ID `1` as `PLA Rapido` and color `#FAFAFA`.

## Firmware `01.01.07.01` filament IDs

- **Config-confirmed:** the SOC payload adds `/home/qidi/QIDI_Client/resource/filament_config/filament-{0.2,0.4,0.6,0.8}.json`, keyed by display name with string `filament_id` values such as `QFA00` (`QIDI PLA Basic`) and `QFA90` (`Generic PLA`) and a `filament_vendor`. The 0.4 mm file has 56 entries from QIDI, Generic, Bambu, HATCHBOX, Overture, and Polymaker and is a superset of the other nozzle files. `officiall_filas_list.cfg` is unchanged.
- **Static-recovered:** IDs follow Bambu Studio's `GF` filament-ID families with a `QF` prefix (`A` PLA, `B` ABS/ASA, `C` PC, `G` PETG, `N` PA, `P` PPS, `S` support, `T` PET, `U` TPU, `L` other brands). QIDI Studio `02.07.02.60` profiles do not use `QF` IDs.
- **Static-recovered:** `box2base` rejects IDs not shaped like `QFA00` and colors that are not 6-digit RGB values; `multi_color_controller` references both the 0.4 mm JSON and `officiall_filas_list.cfg`, and `box_rfid`, `box2base`, and `multi_color_controller` carry `LEGACY_RFID_FILAMENT_ID_MAP` and `LEGACY_RFID_COLOR_MAP`. None of these strings occur in the `01.01.06.05` modules. qidiclient reads the 0.4 mm JSON, builds its vendor picker from it, and sends `SAVE_VARIABLE` for `filament_slot`, `color_slot`, and `vendor_slot` plus `UPDATE_FILAMENT_INFORMATION SLOT=`.
- **Runtime-confirmed:** touchscreen selections store `filament_slotN = 'QFA90'` or `'QFL30'` (Bambu PLA) and `color_slotN = ['228332']` (a list of uppercase RGB strings without `#`, including values absent from `[colordict]`); `vendor_slotN` is left unchanged. Fluidd's stock picker stores numeric IDs such as `7` and `4`.
- **Runtime-confirmed:** `multi_color_controller` status `box.boxB_filament_info_I_*` (Box `B+1`, slot `I`) and `extra.filament_info` (rack) publish the resolved `filament_id`, `filament_str` without the vendor, `vendor_str`, `filament_type`, `color_rgb_str`, temperatures, and `info_from_rfid`. Numeric filament IDs resolved to `QFA00` QIDI PLA Basic (190–240 °C) and numeric colors to `#FAFAFA` for saved values `1`, `4`, `7`, and `18` with colors `1` and `23`. Subscription updates carry only changed `box` keys.
- **Runtime-confirmed:** `SAVE_VARIABLE VARIABLE=filament_slotN VALUE='"QFA90"'` and `SAVE_VARIABLE VARIABLE=color_slotN VALUE="['FAFAFA']"` from Moonraker update the resolved slot status immediately without `UPDATE_FILAMENT_INFORMATION`.
- **Runtime-confirmed:** after appending an entry with a new vendor and unused ID `QFL70` to the 0.4 mm JSON and restarting Klipper and qidiclient, the touchscreen listed the vendor and filament, saved `filament_slotN = 'QFL70'`, and Klipper logged no filament-database errors. Loading or printing with such an entry is untested.
- **Runtime-confirmed:** with `config/qidi_filament_config` symlinked to `/home/qidi/QIDI_Client/resource/filament_config`, Moonraker lists the four JSON files as read-write in the `config` root, and saving `filament-0.4.json` from Fluidd's editor rewrote the target file in place with the edit intact. The link was preserved, and the file's mode changed from `0755` to `0644` with `qidi` ownership retained. Moonraker runs as `qidi`, which owns the directory and files; qidiclient runs as root.
- **Runtime-confirmed:** stock Fluidd shows `QF` slots as `?` with a transparent spool, because `parseInt` turns the string ID into `NaN` and the RGB value into a missing `[colordict]` key.
- **Unresolved:** the RFID legacy-to-`QF` mapping and any numeric range enforced for `QF` IDs.

## Filaments

| ID | Filament | Type | Nozzle °C | Box °C |
|---:|---|---|---|---|
| `1` | `PLA Rapido` | `PLA` | `190..240` | `0..0` |
| `2` | `PLA Matte` | `PLA` | `190..240` | `0..0` |
| `3` | `PLA Metal` | `PLA` | `190..240` | `0..0` |
| `4` | `PLA Silk` | `PLA` | `190..240` | `0..0` |
| `5` | `PLA-CF` | `PLA-CF` | `210..250` | `0..0` |
| `6` | `PLA-Wood` | `PLA` | `190..240` | `0..45` |
| `7` | `PLA Basic` | `PLA` | `190..240` | `0..0` |
| `8` | `PLA Matte Basic` | `PLA` | `190..230` | `0..0` |
| `9` | empty | empty | empty | empty |
| `10` | `Support For PLA` | `PLA-S` | `210..240` | `0..0` |
| `11` | `ABS Rapido` | `ABS` | `240..280` | `0..45` |
| `12` | `ABS-GF` | `ABS-GF` | `240..280` | `0..45` |
| `13` | `ABS-Metal` | `ABS` | `240..280` | `0..45` |
| `14` | `ABS-Odorless` | `ABS` | `240..280` | `0..45` |
| `15` | `TPU-GF` | `TPU-GF` | `240..270` | `0..0` |
| `16` | empty | empty | empty | empty |
| `17` | empty | empty | empty | empty |
| `18` | `ASA` | `ASA` | `240..280` | `0..45` |
| `19` | `ASA-Aero` | `ASA-AERO` | `240..280` | `0..45` |
| `20` | `ASA-CF` | `ASA-CF` | `240..280` | `0..45` |
| `21` | empty | empty | empty | empty |
| `22` | empty | empty | empty | empty |
| `23` | `PC` | `PC` | `240..280` | `0..0` |
| `24` | `UltraPA` | `UltraPA` | `260..300` | `0..55` |
| `25` | `PA6-CF` | `PA6-CF` | `260..300` | `0..65` |
| `26` | `UltraPA-CF25` | `UltraPA-CF25` | `300..320` | `0..65` |
| `27` | `PA12-CF` | `PA12-CF` | `260..300` | `0..65` |
| `28` | empty | empty | empty | empty |
| `29` | empty | empty | empty | empty |
| `30` | `PAHT-CF` | `PAHT-CF` | `300..320` | `0..65` |
| `31` | `PAHT-GF` | `PAHT-GF` | `300..320` | `0..65` |
| `32` | `Support For PAHT` | `PAHT-S` | `260..280` | `0..65` |
| `33` | `Support For PET/PA` | `PA-S` | `260..280` | `0..65` |
| `34` | `PC/ABS-FR` | `PC-ABS-FR` | `260..280` | `0..50` |
| `35` | `TPEE` | `TPEE` | `230..260` | `0..0` |
| `36` | `PEBA` | `PEBA` | `230..260` | `0..0` |
| `37` | `PET-CF` | `PET-CF` | `280..320` | `0..65` |
| `38` | `PET-GF` | `PET-GF` | `280..320` | `0..50` |
| `39` | `PETG Basic` | `PETG` | `240..280` | `0..45` |
| `40` | `PETG-Tough` | `PETG` | `240..275` | `0..45` |
| `41` | `PETG Rapido` | `PETG` | `220..270` | `0..45` |
| `42` | `PETG-CF` | `PETG-CF` | `240..270` | `0..45` |
| `43` | `PETG-GF` | `PETG-GF` | `240..270` | `0..45` |
| `44` | `PPS-CF` | `PPS-CF` | `300..350` | `0..65` |
| `45` | `PETG Translucent` | `PETG` | `240..280` | `0..45` |
| `46` | `PPS-GF` | `PPS-GF` | `300..350` | `0..65` |
| `47` | `PVA` | `PVA` | `210..250` | `0..50` |
| `48` | `TPU-AERO 64D` | `TPU-AERO 64D` | `200..250` | `0..0` |
| `49` | `TPU-Aero` | `TPU-AERO` | `200..250` | `0..0` |
| `50` | `TPU 95A-HF` | `TPU` | `200..250` | `0..0` |

## Colors

| ID | Color | ID | Color | ID | Color |
|---:|---|---:|---|---:|---|
| `1` | `#FAFAFA` | `9` | `#228332` | `17` | `#FE717A` |
| `2` | `#060606` | `10` | `#99DEFF` | `18` | `#FF362D` |
| `3` | `#D9E3ED` | `11` | `#1714B0` | `19` | `#E2DFCD` |
| `4` | `#5CF30F` | `12` | `#CEC0FE` | `20` | `#898F9B` |
| `5` | `#63E492` | `13` | `#CADE4B` | `21` | `#6E3812` |
| `6` | `#2850FF` | `14` | `#1353AB` | `22` | `#CAC59F` |
| `7` | `#FE98FE` | `15` | `#5EA9FD` | `23` | `#F28636` |
| `8` | `#DFD628` | `16` | `#A878FF` | `24` | `#B87F2B` |

## Vendors

| ID | Vendor |
|---:|---|
| `0` | `Generic` |
| `1` | `QIDI` |
