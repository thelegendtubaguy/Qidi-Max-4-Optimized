from __future__ import annotations

import json
from functools import lru_cache

from .errors import InstallerError


OPERATION = "fluidd_box_filament_ids"
PATCH_MARKER = "/*tltg-optimized:fluidd-box-filament-ids*/"

# QIDI firmware 01.01.07.01 filament-0.4.json: ID, name, type, nozzle min/max, box min/max.
QIDI_FILAMENTS = (
    ("QFA00", "QIDI PLA Basic", "PLA", "190", "240", "0", "0"),
    ("QFA01", "QIDI PLA Matte Basic", "PLA", "190", "240", "0", "0"),
    ("QFA02", "QIDI PLA Rapido", "PLA", "190", "240", "0", "0"),
    ("QFA03", "QIDI PLA Rapido Matte", "PLA", "190", "240", "0", "0"),
    ("QFA04", "QIDI PLA Rapido Metal", "PLA", "190", "240", "0", "0"),
    ("QFA05", "QIDI PLA Silk", "PLA", "190", "240", "0", "0"),
    ("QFA16", "QIDI WOOD Rapido", "PLA", "190", "220", "0", "0"),
    ("QFA50", "QIDI PLA-CF", "PLA-CF", "210", "250", "0", "0"),
    ("QFB01", "QIDI ASA", "ASA", "240", "280", "0", "45"),
    ("QFB02", "QIDI ASA-Aero", "ASA-AERO", "240", "280", "0", "45"),
    ("QFB50", "QIDI ABS-GF", "ABS-GF", "240", "280", "0", "45"),
    ("QFB51", "QIDI ASA-CF20 Core", "ASA-CF", "260", "280", "0", "45"),
    ("QFB53", "QIDI ABS Odorless", "ABS", "240", "280", "0", "45"),
    ("QFB54", "QIDI ABS Rapido", "ABS", "240", "280", "0", "45"),
    ("QFB55", "QIDI ABS Rapido Metal", "ABS", "240", "280", "0", "45"),
    ("QFC02", "QIDI PC/ABS-FR", "PC-ABS-FR", "240", "280", "0", "50"),
    ("QFG00", "QIDI PETG Basic", "PETG", "240", "280", "0", "45"),
    ("QFG02", "QIDI PETG Rapido", "PETG", "240", "275", "0", "45"),
    ("QFG03", "QIDI PETG Tough", "PETG", "220", "270", "0", "45"),
    ("QFG04", "QIDI PETG Translucent", "PETG", "240", "280", "0", "45"),
    ("QFG50", "QIDI PETG-CF", "PETG-CF", "240", "270", "0", "45"),
    ("QFG51", "QIDI PETG-GF", "PETG-GF", "240", "270", "0", "45"),
    ("QFN04", "QIDI PAHT-CF", "PAHT-CF", "300", "320", "0", "65"),
    ("QFN05", "QIDI PA6-CF", "PA6-CF", "280", "300", "0", "65"),
    ("QFN12", "QIDI PA12-CF", "PA12-CF", "280", "300", "0", "65"),
    ("QFN14", "QIDI PAHT-GF", "PAHT-GF", "300", "320", "0", "65"),
    ("QFN20", "QIDI UltraPA", "UltraPA", "250", "290", "0", "55"),
    ("QFN21", "QIDI UltraPA-CF25", "UltraPA-CF25", "300", "320", "0", "65"),
    ("QFP01", "QIDI PPS-CF", "PPS-CF", "300", "350", "0", "65"),
    ("QFP02", "QIDI PPS-GF", "PPS-GF", "300", "350", "0", "65"),
    ("QFS01", "QIDI Support For PET/PA", "PA-S", "260", "280", "0", "65"),
    ("QFS03", "QIDI Support For PAHT", "PAHT-S", "260", "280", "0", "65"),
    ("QFT01", "QIDI PET-CF", "PET-CF", "280", "320", "0", "65"),
    ("QFT02", "QIDI PET-GF", "PET-GF", "280", "320", "0", "50"),
    ("QFU00", "QIDI TPU-Aero", "TPU-AERO", "230", "270", "0", "0"),
    ("QFU01", "QIDI TPU 95A-HF", "TPU", "200", "250", "0", "0"),
    ("QFU02", "QIDI TPU-GF", "TPU-GF", "240", "270", "0", "0"),
    ("QFU03", "QIDI PEBA 95A", "PEBA", "230", "260", "0", "0"),
    ("QFB91", "Generic ABS", "ABS", "240", "280", "0", "45"),
    ("QFC90", "Generic PC", "PC", "260", "290", "0", "65"),
    ("QFG90", "Generic PETG", "PETG", "220", "270", "0", "45"),
    ("QFA90", "Generic PLA", "PLA", "190", "240", "0", "0"),
    ("QFA92", "Generic PLA Silk", "PLA", "190", "240", "0", "0"),
    ("QFA91", "Generic PLA+", "PLA", "190", "240", "0", "0"),
    ("QFU91", "Generic TPU 95A", "TPU", "200", "250", "0", "0"),
    ("QFL32", "Bambu ABS", "ABS", "240", "280", "0", "45"),
    ("QFL31", "Bambu PETG", "PETG", "220", "270", "0", "45"),
    ("QFL30", "Bambu PLA", "PLA", "190", "240", "0", "0"),
    ("QFL12", "HATCHBOX ABS", "ABS", "240", "280", "0", "45"),
    ("QFL11", "HATCHBOX PETG", "PETG", "220", "270", "0", "45"),
    ("QFL10", "HATCHBOX PLA", "PLA", "190", "240", "0", "0"),
    ("QFL62", "Overture ABS", "ABS", "240", "280", "0", "45"),
    ("QFL60", "Overture PLA", "PLA", "190", "240", "0", "45"),
    ("QFL22", "Polymaker ABS", "ABS", "240", "280", "0", "45"),
    ("QFL20", "Polymaker PLA", "PLA", "190", "240", "0", "0"),
    ("QFL24", "Polymaker PLA-HT", "PLA", "190", "240", "0", "0"),
)

SLOT_PARSE_STOCK = (
    'if(g.startsWith("color_slot")){const v=parseInt(g.replace("color_slot",""),10);s[v]=parseInt(e[g]??"0",10)}'
    'else if(g.startsWith("filament_slot")){const v=parseInt(g.replace("filament_slot",""),10);n[v]=parseInt(e[g]??"0",10)}'
)
# Firmware 01.01.07.01 saves colors as ["RRGGBB"] and filaments as "QFxnn"; legacy numeric IDs remain valid.
SLOT_PARSE_PATCHED = (
    'if(g.startsWith("color_slot")){const v=parseInt(g.replace("color_slot",""),10);'
    's[v]=(x=>{x=Array.isArray(x)?x[0]:x;return typeof x=="string"&&/^#?[0-9A-Fa-f]{6}$/.test(x)?x.replace("#","").toUpperCase():parseInt(x??"0",10)})(e[g])}'
    'else if(g.startsWith("filament_slot")){const v=parseInt(g.replace("filament_slot",""),10);'
    'n[v]=typeof e[g]=="string"&&/^[A-Z]+[0-9]+$/.test(e[g])?e[g]:parseInt(e[g]??"0",10)}'
)
FILAS_LIST_STOCK = 'setOfficiallFilasList(r,e){$.set(r,"officiallFilasList",e)}'


def _filas_list_patched() -> str:
    table = ",".join(f"{item[0]}:{json.dumps(list(item[1:]), ensure_ascii=False, separators=(',', ':'))}" for item in QIDI_FILAMENTS)
    # Proxies resolve new IDs without adding entries to the stock filament picker.
    return (
        'setOfficiallFilasList(r,e){$.set(r,"officiallFilasList",' + PATCH_MARKER + '(d=>{'
        'if(!d||typeof d!="object")return d;'
        'const q={' + table + '},c=d.colordict;'
        'c&&typeof c=="object"&&(d.colordict=new Proxy(c,{get(t,k,p){'
        'if(typeof k!="string"||k in t)return Reflect.get(t,k,p);'
        'const h=k.split(",")[0].replace(/^#/,"");'
        'return/^[0-9A-Fa-f]{6}$/.test(h)?"#"+h.toUpperCase():void 0}}));'
        'return new Proxy(d,{get(t,k,p){'
        'const m=typeof k=="string"&&!(k in t)&&/^fila([A-Z]+[0-9]+)$/.exec(k);'
        'if(!m)return Reflect.get(t,k,p);'
        'const f=q[m[1]];'
        'return f?{filament:f[0],type:f[1],min_temp:f[2],max_temp:f[3],box_min_temp:f[4],box_max_temp:f[5]}:{filament:m[1],type:""}}})'
        '})(e))}'
    )


class FluiddBundleError(InstallerError):
    pass


@lru_cache(maxsize=4)
def patch_fluidd_bundle(text: str) -> str:
    replacements = ((SLOT_PARSE_STOCK, SLOT_PARSE_PATCHED), (FILAS_LIST_STOCK, _filas_list_patched()))
    stock_counts = [text.count(stock) for stock, _patched in replacements]
    patched_counts = [text.count(patched) for _stock, patched in replacements]
    if stock_counts == [0, 0] and patched_counts == [1, 1] and text.count(PATCH_MARKER) == 1:
        return text
    if stock_counts != [1, 1] or patched_counts != [0, 0] or PATCH_MARKER in text:
        raise FluiddBundleError("Fluidd bundle does not match the reviewed QIDI box source; preserving it.")
    for stock, patched in replacements:
        text = text.replace(stock, patched, 1)
    return text
