from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from .errors import InstallerError


OPERATION = "fluidd_box_filament_ids"
SERVICE_WORKER_OPERATION = "fluidd_service_worker"
PATCH_MARKER = "/*tltg-optimized:fluidd-box-filament-ids*/"

# QIDI firmware 01.01.07.01 filament-0.4.json: ID, name, type, nozzle min/max, box min/max, vendor.
QIDI_FILAMENTS = (
    ("QFA00", "QIDI PLA Basic", "PLA", "190", "240", "0", "0", "QIDI"),
    ("QFA01", "QIDI PLA Matte Basic", "PLA", "190", "240", "0", "0", "QIDI"),
    ("QFA02", "QIDI PLA Rapido", "PLA", "190", "240", "0", "0", "QIDI"),
    ("QFA03", "QIDI PLA Rapido Matte", "PLA", "190", "240", "0", "0", "QIDI"),
    ("QFA04", "QIDI PLA Rapido Metal", "PLA", "190", "240", "0", "0", "QIDI"),
    ("QFA05", "QIDI PLA Silk", "PLA", "190", "240", "0", "0", "QIDI"),
    ("QFA16", "QIDI WOOD Rapido", "PLA", "190", "220", "0", "0", "QIDI"),
    ("QFA50", "QIDI PLA-CF", "PLA-CF", "210", "250", "0", "0", "QIDI"),
    ("QFB01", "QIDI ASA", "ASA", "240", "280", "0", "45", "QIDI"),
    ("QFB02", "QIDI ASA-Aero", "ASA-AERO", "240", "280", "0", "45", "QIDI"),
    ("QFB50", "QIDI ABS-GF", "ABS-GF", "240", "280", "0", "45", "QIDI"),
    ("QFB51", "QIDI ASA-CF20 Core", "ASA-CF", "260", "280", "0", "45", "QIDI"),
    ("QFB53", "QIDI ABS Odorless", "ABS", "240", "280", "0", "45", "QIDI"),
    ("QFB54", "QIDI ABS Rapido", "ABS", "240", "280", "0", "45", "QIDI"),
    ("QFB55", "QIDI ABS Rapido Metal", "ABS", "240", "280", "0", "45", "QIDI"),
    ("QFC02", "QIDI PC/ABS-FR", "PC-ABS-FR", "240", "280", "0", "50", "QIDI"),
    ("QFG00", "QIDI PETG Basic", "PETG", "240", "280", "0", "45", "QIDI"),
    ("QFG02", "QIDI PETG Rapido", "PETG", "240", "275", "0", "45", "QIDI"),
    ("QFG03", "QIDI PETG Tough", "PETG", "220", "270", "0", "45", "QIDI"),
    ("QFG04", "QIDI PETG Translucent", "PETG", "240", "280", "0", "45", "QIDI"),
    ("QFG50", "QIDI PETG-CF", "PETG-CF", "240", "270", "0", "45", "QIDI"),
    ("QFG51", "QIDI PETG-GF", "PETG-GF", "240", "270", "0", "45", "QIDI"),
    ("QFN04", "QIDI PAHT-CF", "PAHT-CF", "300", "320", "0", "65", "QIDI"),
    ("QFN05", "QIDI PA6-CF", "PA6-CF", "280", "300", "0", "65", "QIDI"),
    ("QFN12", "QIDI PA12-CF", "PA12-CF", "280", "300", "0", "65", "QIDI"),
    ("QFN14", "QIDI PAHT-GF", "PAHT-GF", "300", "320", "0", "65", "QIDI"),
    ("QFN20", "QIDI UltraPA", "UltraPA", "250", "290", "0", "55", "QIDI"),
    ("QFN21", "QIDI UltraPA-CF25", "UltraPA-CF25", "300", "320", "0", "65", "QIDI"),
    ("QFP01", "QIDI PPS-CF", "PPS-CF", "300", "350", "0", "65", "QIDI"),
    ("QFP02", "QIDI PPS-GF", "PPS-GF", "300", "350", "0", "65", "QIDI"),
    ("QFS01", "QIDI Support For PET/PA", "PA-S", "260", "280", "0", "65", "QIDI"),
    ("QFS03", "QIDI Support For PAHT", "PAHT-S", "260", "280", "0", "65", "QIDI"),
    ("QFT01", "QIDI PET-CF", "PET-CF", "280", "320", "0", "65", "QIDI"),
    ("QFT02", "QIDI PET-GF", "PET-GF", "280", "320", "0", "50", "QIDI"),
    ("QFU00", "QIDI TPU-Aero", "TPU-AERO", "230", "270", "0", "0", "QIDI"),
    ("QFU01", "QIDI TPU 95A-HF", "TPU", "200", "250", "0", "0", "QIDI"),
    ("QFU02", "QIDI TPU-GF", "TPU-GF", "240", "270", "0", "0", "QIDI"),
    ("QFU03", "QIDI PEBA 95A", "PEBA", "230", "260", "0", "0", "QIDI"),
    ("QFB91", "Generic ABS", "ABS", "240", "280", "0", "45", "Generic"),
    ("QFC90", "Generic PC", "PC", "260", "290", "0", "65", "Generic"),
    ("QFG90", "Generic PETG", "PETG", "220", "270", "0", "45", "Generic"),
    ("QFA90", "Generic PLA", "PLA", "190", "240", "0", "0", "Generic"),
    ("QFA92", "Generic PLA Silk", "PLA", "190", "240", "0", "0", "Generic"),
    ("QFA91", "Generic PLA+", "PLA", "190", "240", "0", "0", "Generic"),
    ("QFU91", "Generic TPU 95A", "TPU", "200", "250", "0", "0", "Generic"),
    ("QFL32", "Bambu ABS", "ABS", "240", "280", "0", "45", "Bambu"),
    ("QFL31", "Bambu PETG", "PETG", "220", "270", "0", "45", "Bambu"),
    ("QFL30", "Bambu PLA", "PLA", "190", "240", "0", "0", "Bambu"),
    ("QFL12", "HATCHBOX ABS", "ABS", "240", "280", "0", "45", "HATCHBOX"),
    ("QFL11", "HATCHBOX PETG", "PETG", "220", "270", "0", "45", "HATCHBOX"),
    ("QFL10", "HATCHBOX PLA", "PLA", "190", "240", "0", "0", "HATCHBOX"),
    ("QFL62", "Overture ABS", "ABS", "240", "280", "0", "45", "Overture"),
    ("QFL60", "Overture PLA", "PLA", "190", "240", "0", "45", "Overture"),
    ("QFL22", "Polymaker ABS", "ABS", "240", "280", "0", "45", "Polymaker"),
    ("QFL20", "Polymaker PLA", "PLA", "190", "240", "0", "0", "Polymaker"),
    ("QFL24", "Polymaker PLA-HT", "PLA", "190", "240", "0", "0", "Polymaker"),
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

VARIABLES_RETURN_STOCK = (
    'return a[16]=1,{boxCount:t,colorSlot:s,filamentSlot:n,vendorSlot:i,slot:a,valueSlot:o,slotSync:l,rackExtra:c,lastLoadSlot:u}'
)
# 01.01.07.01 resolves every saved slot, including stale numeric IDs, through multi_color_controller; show that view.
VARIABLES_RETURN_PATCHED = (
    '{const x=r==null?void 0:r.printer,y=x&&x.box485&&x.multi_color_controller,b=y&&y.box;'
    'if(b){const w=(k,f)=>{const d=k[f+"filament_id"];if(typeof d!="string"||!d)return null;'
    'const h=k[f+"color_rgb_str"],z=Array.isArray(h)?h[0]:h;'
    'return[d,typeof z=="string"?z.replace("#","").toUpperCase():null,k[f+"vendor_str"]]};'
    'for(let g=0;g<16;g++){const z=w(b,`box${g>>2}_filament_info_${g&3}_`);z&&(n[g]=z[0],z[1]&&(s[g]=z[1]),z[2]&&(i[g]=z[2]))}'
    'const f=y.extra&&y.extra.filament_info,z=f&&w(f,"");z&&(c[1]=z[0],z[1]&&(c[0]=z[1]),z[2]&&(c[2]=z[2]))}}'
    + VARIABLES_RETURN_STOCK
)

SOCKET_NOTIFY_STOCK = (
    'Object.keys(e.payload).forEach(s=>{t[s]!==e.payload[s]&&$.set(r.printer[e.key],s,e.payload[s])})'
)
# multi_color_controller publishes partial nested updates; merge them so per-slot info is retained.
SOCKET_NOTIFY_PATCHED = (
    'Object.keys(e.payload).forEach(s=>{const v=e.payload[s],o=t[s];t[s]!==v&&$.set(r.printer[e.key],s,'
    'e.key==="multi_color_controller"&&o&&v&&typeof o=="object"&&typeof v=="object"&&!Array.isArray(v)?{...o,...v}:v)})'
)

FILAS_LIST_STOCK = 'setOfficiallFilasList(r,e){$.set(r,"officiallFilasList",e)}'


def _filas_table(columns: int) -> str:
    return ",".join(
        f"{item[0]}:{json.dumps(list(item[1:columns + 1]), ensure_ascii=False, separators=(',', ':'))}"
        for item in QIDI_FILAMENTS
    )


def _filas_list_patched_v1() -> str:
    # Package 26.10.20.1 output; recognized only so updates can replace it.
    return (
        'setOfficiallFilasList(r,e){$.set(r,"officiallFilasList",' + PATCH_MARKER + '(d=>{'
        'if(!d||typeof d!="object")return d;'
        'const q={' + _filas_table(6) + '},c=d.colordict;'
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


def _filas_list_patched() -> str:
    # Proxies resolve new IDs and vendors without adding entries to the stock legacy picker.
    return (
        'setOfficiallFilasList(r,e){$.set(r,"officiallFilasList",' + PATCH_MARKER + '(d=>{'
        'if(!d||typeof d!="object")return d;'
        'const q={' + _filas_table(7) + '},c=d.colordict,w=d.vendor_list,'
        'n=new Set(Object.values(q).map(f=>f[6]));let l;'
        'c&&typeof c=="object"&&(d.colordict=new Proxy(c,{get(t,k,p){'
        'if(typeof k!="string"||k in t)return Reflect.get(t,k,p);'
        'const h=k.split(",")[0].replace(/^#/,"");'
        'return/^[0-9A-Fa-f]{6}$/.test(h)?"#"+h.toUpperCase():void 0}}));'
        'w&&typeof w=="object"&&(d.vendor_list=new Proxy(w,{get(t,k,p){'
        'return typeof k=="string"&&!(k in t)&&n.has(k)?k:Reflect.get(t,k,p)}}));'
        'return new Proxy(d,{get(t,k,p){'
        'if(k==="tltgFilaments"&&!(k in t))return l||(l=Object.entries(q).map(([i,f])=>({id:i,name:f[0],type:f[1],vendor:f[6]})));'
        'const m=typeof k=="string"&&!(k in t)&&/^fila([A-Z]+[0-9]+)$/.exec(k);'
        'if(!m)return Reflect.get(t,k,p);'
        'const f=q[m[1]];'
        'return f?{filament:f[0],type:f[1],min_temp:f[2],max_temp:f[3],box_min_temp:f[4],box_max_temp:f[5]}:{filament:m[1],type:""}}})'
        '})(e))}'
    )


# Box card pickers. On 01.01.07.01 (box485 present) they offer the firmware filament database and save
# the touchscreen formats; otherwise the stock legacy pickers run unchanged.
FILAMENT_ITEMS_STOCK = (
    'get filamentItems(){const t=new Set;if(!this.officialFilasListDictData)return[""];'
    'for(const s in this.officialFilasListDictData)s.startsWith("fila")&&t.add(this.officialFilasListDictData[s].filament);'
    'return Array.from(t)}'
)
FILAMENT_ITEMS_PATCHED = (
    'get tltgCatalog(){const p=this.$store.state.printer.printer,d=this.officialFilasListDictData;'
    'return p&&p.box485&&d&&d.tltgFilaments||null}'
    'tltgSaveFilament(t){I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=filament_slot${this.selectIndex} VALUE=\'"${t}"\'`)}'
    'get filamentItems(){const q=this.tltgCatalog;if(q){const v=this.selectedVendor,f=q.filter(x=>x.vendor===v);'
    'return(f.length?f:q).map(x=>x.name)}'
    + FILAMENT_ITEMS_STOCK.removeprefix('get filamentItems(){')
)
VENDOR_ITEMS_STOCK = (
    'get vendorItems(){const t=new Set;if(!this.officialFilasListDictData)return[""];'
    'for(const s in this.officialFilasListDictData.vendor_list)t.add(this.officialFilasListDictData.vendor_list[s]);'
    'return Array.from(t)}'
)
VENDOR_ITEMS_PATCHED = (
    'get vendorItems(){const q=this.tltgCatalog;if(q)return Array.from(new Set(q.map(x=>x.vendor)));'
    + VENDOR_ITEMS_STOCK.removeprefix('get vendorItems(){')
)
SELECTED_VENDOR_STOCK = (
    'set selectedVendor(t){const s=this.getKeyByValue(this.officialFilasListDictData.vendor_list,t);'
    's&&(this.selectIndex===16?I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=vendor_slot16 VALUE="${s}"`)'
    ':I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=vendor_slot${this.selectIndex} VALUE="${s}"`))}'
)
# The touchscreen stores vendor only through the filament ID, so a vendor change selects a matching filament.
SELECTED_VENDOR_PATCHED = (
    'set selectedVendor(t){const q=this.tltgCatalog;if(q){const c=q.find(x=>x.name===this.selectedFilament),'
    'f=q.filter(x=>x.vendor===t),m=c&&f.find(x=>x.type===c.type)||f[0];'
    'm&&m.name!==this.selectedFilament&&this.tltgSaveFilament(m.id);return}'
    + SELECTED_VENDOR_STOCK.removeprefix('set selectedVendor(t){')
)
SELECTED_FILAMENT_STOCK = (
    'set selectedFilament(t){for(const s in this.officialFilasListDictData)s.startsWith("fila")'
    '&&this.officialFilasListDictData[s].filament===t&&(this.selectIndex===16'
    '?I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=filament_slot16 VALUE="${s.replace("fila","")}"`)'
    ':I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=filament_slot${this.selectIndex} VALUE="${s.replace("fila","")}"`))}'
)
SELECTED_FILAMENT_PATCHED = (
    'set selectedFilament(t){const q=this.tltgCatalog;if(q){const v=this.selectedVendor,'
    'm=q.find(x=>x.name===t&&x.vendor===v)||q.find(x=>x.name===t);m&&this.tltgSaveFilament(m.id);return}'
    + SELECTED_FILAMENT_STOCK.removeprefix('set selectedFilament(t){')
)
SELECTED_COLOR_STOCK = (
    'set selectedColor(t){const s=this.getKeyByValue(this.officialFilasListDictData.colordict,t);'
    's&&(this.selectIndex===16?I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=color_slot16 VALUE="${s}"`)'
    ':I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=color_slot${this.selectIndex} VALUE="${s}"`))}'
)
SELECTED_COLOR_PATCHED = (
    'set selectedColor(t){if(this.tltgCatalog&&typeof t=="string"&&/^#[0-9A-Fa-f]{6}$/.test(t)){'
    'I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=color_slot${this.selectIndex} VALUE="[\'${t.slice(1).toUpperCase()}\']"`);return}'
    + SELECTED_COLOR_STOCK.removeprefix('set selectedColor(t){')
)

BOX_TEMP_LIMIT_STOCK = (
    'getMinMaxTempOfBox:(r,e)=>t=>{const s=e.getVariables,n=s.slot.reduce((l,c,u)=>(c===1&&u/4===t-1&&l.push(u),l),[]);'
    'if(n.length===0)return-1;const i=s.filamentSlot.filter((l,c)=>n.includes(c)),a=r.officiallFilasList;if(!a)return-2;'
    'const o=i.map(l=>{var c;return(c=a["fila"+l])==null?void 0:c.box_max_temp});return Math.min(...o)}'
)
# Every loaded slot of the Box limits its heater, including a filament limit of 0; filaments without a limit are skipped.
BOX_TEMP_LIMIT_PATCHED = (
    'getMinMaxTempOfBox:(r,e)=>t=>{const s=e.getVariables,n=s.slot.reduce((l,c,u)=>(c===1&&Math.floor(u/4)===t-1&&l.push(u),l),[]);'
    'if(n.length===0)return-1;const i=s.filamentSlot.filter((l,c)=>n.includes(c)),a=r.officiallFilasList;if(!a)return-2;'
    'const o=i.map(l=>{var c;return parseFloat((c=a["fila"+l])==null?void 0:c.box_max_temp)}).filter(l=>!isNaN(l));'
    'return o.length?Math.min(...o):-1}'
)
HEATER_TARGET_STOCK = (
    'attrs:{value:s.target,rules:[e.$rules.required,e.$rules.numberValid,'
    'e.$rules.numberGreaterThanOrEqualOrZero(s.targetMinTemp?Math.max(s.targetMinTemp,s.minTemp):s.minTemp),'
    'e.$rules.numberLessThanOrEqualOrZero(s.targetMaxTemp!==void 0&&s.targetMaxTemp!==null?Math.min(s.targetMaxTemp,s.maxTemp):s.maxTemp)],'
    'type:"number",outlined:"",dense:"","single-line":"","hide-details":"auto",suffix:"°C"}'
)
# A Box whose loaded filament allows no heating locks its target input; an active target can still be set to 0.
HEATER_TARGET_PATCHED = (
    HEATER_TARGET_STOCK.removesuffix('}') + ',disabled:s.key.includes("heater_box")&&s.targetMaxTemp===0&&!s.target}'
)

# 01.01.07.01 replaced E_BOX/E_LOAD/E_UNLOAD and RFID_READ with the multi_color_controller commands qidiclient sends.
BUTTON_COMMANDS_STOCK = 'const n=["E_BOX","E_LOAD","E_UNLOAD"];I.printerGcodeScript(`${n[t-1]} slot=${s}`)'
BUTTON_COMMANDS_PATCHED = (
    'const c=this.$store.state.printer.printer.multi_color_controller,'
    'n=c?["EJECT_FILAMENT_CONTROL","LOAD_FILAMENT_CONTROL","UNLOAD_FILAMENT_CONTROL"]:["E_BOX","E_LOAD","E_UNLOAD"];'
    'I.printerGcodeScript(`${n[t-1]} ${c?"SLOT":"slot"}=${s}`)'
)
RFID_COMMAND_STOCK = 'handleRfidClick(t){I.printerGcodeScript(`RFID_READ SLOT=slot${t}`)'
RFID_COMMAND_PATCHED = (
    'handleRfidClick(t){I.printerGcodeScript(this.$store.state.printer.printer.multi_color_controller'
    '?`READ_RFID SLOT=${t}`:`RFID_READ SLOT=slot${t}`)'
)
BUTTON_STATUS_STOCK = (
    'get buttonStatus(){const t=new Array(3).fill(!0);return this.selectIndex>=16||('
    'this.$store.state.printer.printer["box_stepper slot"+this.selectIndex].runout_button===0?t[0]=!1:t[0]=!0,'
    'this.$store.state.printer.printer["box_stepper slot"+this.selectIndex].runout_button===0'
    '?this.$store.state.printer.printer.box_extras.b_endstop_state===0&&this.variables.lastLoadSlot===this.selectIndex'
    '?t[1]=!0:t[1]=!1:t[1]=!0,'
    'this.$store.state.printer.printer["box_stepper slot"+this.selectIndex].runout_button===0'
    '&&this.$store.state.printer.printer.box_extras.b_endstop_state===0&&this.variables.lastLoadSlot===this.selectIndex'
    '?t[2]=!1:t[2]=!0),t}'
)
# 01.01.07.01 publishes the Box path sensor only as multi_color_controller.box.b_endstop_state, so Unload stayed disabled.
BUTTON_STATUS_PATCHED = (
    'get tltgBEndstop(){const p=this.$store.state.printer.printer,e=p.box_extras,m=p.multi_color_controller;'
    'return e&&e.b_endstop_state!=null?e.b_endstop_state:m&&m.box&&m.box.b_endstop_state}'
    + BUTTON_STATUS_STOCK.replace('this.$store.state.printer.printer.box_extras.b_endstop_state', 'this.tltgBEndstop')
)

PRINT_SLOT_CHANGE_STOCK = (
    'onValueChange(t){this.selectedValueSlot=this.selectedValueSlot.map((s,n)=>n===t?s:'
    'JSON.stringify(s)===JSON.stringify(this.selectedValueSlot[t])?this.oldSelectedValueSlot[t]:s),'
    'this.oldSelectedValueSlot=JSON.parse(JSON.stringify(this.selectedValueSlot))}'
)
# The print dialog swapped a slot chosen for a second filament away from the first, so a file with more
# filaments of a type than loaded slots of it could never be printed. Several filaments may share a slot.
PRINT_SLOT_CHANGE_PATCHED = (
    'onValueChange(t){this.oldSelectedValueSlot=JSON.parse(JSON.stringify(this.selectedValueSlot))}'
)

FULL_DISPLAY_DEFAULT_STOCK ='enableDiagnostics:!1,enableFullDisplay:!1,thumbnailSize:32'
# QIDI's "Enable Full Display" setting defaults on; a value saved in Moonraker's database still overrides it.
FULL_DISPLAY_DEFAULT_PATCHED = 'enableDiagnostics:!1,enableFullDisplay:!0,thumbnailSize:32'


class FluiddBundleError(InstallerError):
    pass


# The Box Config view ends with its auto-reload switch; a package-owned motion section follows it.
BOX_MOTION_DEFINE_HEAD = "If=J9([L],If);"
BOX_MOTION_DEFINE_TAIL = "var Nle=function(){"
BOX_MOTION_DEFINE_STOCK = BOX_MOTION_DEFINE_HEAD + BOX_MOTION_DEFINE_TAIL
BOX_MOTION_RENDER_STOCK = 'expression:"autoReloadDetect"}})],1)],1)],1)],1)],1)},zle=[]'
BOX_MOTION_RENDER_PATCHED = 'expression:"autoReloadDetect"}})],1)],1)],1)],1),t(TltgBoxMotion)],1)},zle=[]'
BOX_MOTION_START = "/*tltg-optimized:fluidd-box-motion*/"
BOX_MOTION_END = "/*/tltg-optimized:fluidd-box-motion*/"
BOX_MOTION_SOURCE = Path(__file__).with_name("fluidd_box_motion.js")
# Any earlier package version of the section sits between the same markers and is replaced in place.
BOX_MOTION_DEFINE_PREVIOUS = re.compile(
    re.escape(BOX_MOTION_DEFINE_HEAD + BOX_MOTION_START) + ".*?" + re.escape(BOX_MOTION_END + BOX_MOTION_DEFINE_TAIL),
    re.DOTALL,
)


def _section_define(source_path: Path, head: str, start: str, end: str, tail: str, name: str) -> str:
    try:
        source = source_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise FluiddBundleError(f"Fluidd {name} is missing from the package: {exc}") from exc
    if start in source or end in source:
        raise FluiddBundleError(f"Fluidd {name} contains its own patch markers.")
    return head + start + "\n" + source + "\n" + end + tail


@lru_cache(maxsize=1)
def _box_motion_define_patched() -> str:
    return _section_define(
        BOX_MOTION_SOURCE, BOX_MOTION_DEFINE_HEAD, BOX_MOTION_START, BOX_MOTION_END, BOX_MOTION_DEFINE_TAIL, "Box motion section"
    )


# The Printer screen card joins the default dashboard collapsed, after the camera card. Fluidd appends new default
# cards to saved layouts and drops cards it does not know, so a restored stock bundle forgets it.
SCREEN_LAYOUT_STOCK = '{id:"camera-card",enabled:!0,collapsed:!1},'
SCREEN_LAYOUT_PATCHED = SCREEN_LAYOUT_STOCK + '{id:"tltg-screen-card",enabled:!0,collapsed:!0},'
SCREEN_COMPONENT_STOCK = "CameraCard:wre,"
SCREEN_COMPONENT_PATCHED = SCREEN_COMPONENT_STOCK + "TltgScreenCard:TltgScreenCard,"
# The card is defined between the Dashboard class and its decoration, which registers it.
SCREEN_DEFINE_HEAD = "!t.enabled}};"
SCREEN_DEFINE_TAIL = 'L2([Ee("columnCount")],Yu.prototype,"onColumnCount",1);'
SCREEN_DEFINE_STOCK = SCREEN_DEFINE_HEAD + SCREEN_DEFINE_TAIL
SCREEN_START = "/*tltg-optimized:fluidd-remote-screen*/"
SCREEN_END = "/*/tltg-optimized:fluidd-remote-screen*/"
SCREEN_SOURCE = Path(__file__).with_name("fluidd_remote_screen.js")
SCREEN_DEFINE_PREVIOUS = re.compile(
    re.escape(SCREEN_DEFINE_HEAD + SCREEN_START) + ".*?" + re.escape(SCREEN_END + SCREEN_DEFINE_TAIL),
    re.DOTALL,
)


@lru_cache(maxsize=1)
def _screen_define_patched() -> str:
    return _section_define(SCREEN_SOURCE, SCREEN_DEFINE_HEAD, SCREEN_START, SCREEN_END, SCREEN_DEFINE_TAIL, "printer screen card")


# The QidiBox card joins the default dashboard expanded, after the stock Box card, and hides with it when no Box
# is configured. It is defined right after the stock Box card so it can reuse that card's views.
QIDIBOX_LAYOUT_STOCK = '{id:"box-card",enabled:!0,collapsed:!1},'
QIDIBOX_LAYOUT_PATCHED = QIDIBOX_LAYOUT_STOCK + '{id:"tltg-qidi-box-card",enabled:!0,collapsed:!1},'
QIDIBOX_COMPONENT_STOCK = "BoxCard:wce,"
QIDIBOX_COMPONENT_PATCHED = QIDIBOX_COMPONENT_STOCK + "TltgQidiBoxCard:TltgQidiBoxCard,"
QIDIBOX_HIDDEN_STOCK = 't.id==="box-card"&&!this.hasBox'
QIDIBOX_HIDDEN_PATCHED = '(t.id==="box-card"||t.id==="tltg-qidi-box-card")&&!this.hasBox'
QIDIBOX_DEFINE_HEAD = "const wce=Sce.exports;"
QIDIBOX_DEFINE_TAIL = "var xce=Object.defineProperty,"
QIDIBOX_DEFINE_STOCK = QIDIBOX_DEFINE_HEAD + QIDIBOX_DEFINE_TAIL
QIDIBOX_START = "/*tltg-optimized:fluidd-qidibox-card*/"
QIDIBOX_END = "/*/tltg-optimized:fluidd-qidibox-card*/"
QIDIBOX_SOURCE = Path(__file__).with_name("fluidd_qidibox_card.js")
QIDIBOX_DEFINE_PREVIOUS = re.compile(
    re.escape(QIDIBOX_DEFINE_HEAD + QIDIBOX_START) + ".*?" + re.escape(QIDIBOX_END + QIDIBOX_DEFINE_TAIL),
    re.DOTALL,
)


@lru_cache(maxsize=1)
def _qidibox_define_patched() -> str:
    return _section_define(
        QIDIBOX_SOURCE, QIDIBOX_DEFINE_HEAD, QIDIBOX_START, QIDIBOX_END, QIDIBOX_DEFINE_TAIL, "QidiBox card"
    )


def _steps() -> tuple[tuple[str, str, tuple[str | re.Pattern[str], ...]], ...]:
    # (stock, current patch, superseded patches this release replaces)
    return (
        (SLOT_PARSE_STOCK, SLOT_PARSE_PATCHED, ()),
        (VARIABLES_RETURN_STOCK, VARIABLES_RETURN_PATCHED, ()),
        (SOCKET_NOTIFY_STOCK, SOCKET_NOTIFY_PATCHED, ()),
        (FILAS_LIST_STOCK, _filas_list_patched(), (_filas_list_patched_v1(),)),
        (FILAMENT_ITEMS_STOCK, FILAMENT_ITEMS_PATCHED, ()),
        (VENDOR_ITEMS_STOCK, VENDOR_ITEMS_PATCHED, ()),
        (SELECTED_VENDOR_STOCK, SELECTED_VENDOR_PATCHED, ()),
        (SELECTED_FILAMENT_STOCK, SELECTED_FILAMENT_PATCHED, ()),
        (SELECTED_COLOR_STOCK, SELECTED_COLOR_PATCHED, ()),
        (BOX_TEMP_LIMIT_STOCK, BOX_TEMP_LIMIT_PATCHED, ()),
        (HEATER_TARGET_STOCK, HEATER_TARGET_PATCHED, ()),
        (PRINT_SLOT_CHANGE_STOCK, PRINT_SLOT_CHANGE_PATCHED, ()),
        (FULL_DISPLAY_DEFAULT_STOCK, FULL_DISPLAY_DEFAULT_PATCHED, ()),
        (BUTTON_COMMANDS_STOCK, BUTTON_COMMANDS_PATCHED, ()),
        (RFID_COMMAND_STOCK, RFID_COMMAND_PATCHED, ()),
        (BUTTON_STATUS_STOCK, BUTTON_STATUS_PATCHED, ()),
        (BOX_MOTION_DEFINE_STOCK, _box_motion_define_patched(), (BOX_MOTION_DEFINE_PREVIOUS,)),
        (BOX_MOTION_RENDER_STOCK, BOX_MOTION_RENDER_PATCHED, ()),
        (SCREEN_LAYOUT_STOCK, SCREEN_LAYOUT_PATCHED, ()),
        (SCREEN_COMPONENT_STOCK, SCREEN_COMPONENT_PATCHED, ()),
        (SCREEN_DEFINE_STOCK, _screen_define_patched(), (SCREEN_DEFINE_PREVIOUS,)),
        (QIDIBOX_LAYOUT_STOCK, QIDIBOX_LAYOUT_PATCHED, ()),
        (QIDIBOX_COMPONENT_STOCK, QIDIBOX_COMPONENT_PATCHED, ()),
        (QIDIBOX_HIDDEN_STOCK, QIDIBOX_HIDDEN_PATCHED, ()),
        (QIDIBOX_DEFINE_STOCK, _qidibox_define_patched(), (QIDIBOX_DEFINE_PREVIOUS,)),
    )


@lru_cache(maxsize=4)
def patch_fluidd_bundle(text: str) -> str:
    edits = []
    for stock, patched, superseded in _steps():
        current = text.count(patched)
        # A superseded pattern stands for every earlier form it matches other than the current patch.
        olds = [stock]
        for old in superseded:
            olds.extend(sorted({m for m in old.findall(text) if m != patched}) if isinstance(old, re.Pattern) else (old,))
        # Some patches keep their stock span as a suffix; those matches are not unpatched source.
        counts = {old: text.count(old) - (current if old in patched else 0) for old in olds}
        present = [old for old, count in counts.items() if count]
        if current == 1 and not present:
            continue
        if current == 0 and len(present) == 1 and counts[present[0]] == 1:
            edits.append((present[0], patched))
            continue
        raise FluiddBundleError("Fluidd bundle does not match the reviewed QIDI box source; preserving it.")
    for old, patched in edits:
        text = text.replace(old, patched, 1)
    return text


# Workbox serves its precached bundle until sw.js changes, so browsers that opened Fluidd before the patch
# kept running the stock bundle. A revision derived from the bundle patch makes them fetch every new version.
SERVICE_WORKER_BUNDLE_ENTRY = re.compile(r'\{"revision":(?:null|"tltg-optimized-[0-9a-f]{16}"),"url":"assets/index-DlFvHGAh\.js"\}')


def _service_worker_bundle_entry() -> str:
    digest = hashlib.sha256("".join(patched for _, patched, _ in _steps()).encode("utf-8")).hexdigest()[:16]
    return '{"revision":"tltg-optimized-' + digest + '","url":"assets/index-DlFvHGAh.js"}'


SERVICE_WORKER_SKIP_WAITING_STOCK = 'self.addEventListener("message",s=>{s.data&&s.data.type==="SKIP_WAITING"&&self.skipWaiting()});'
# Stock Fluidd keeps a new worker waiting for its update prompt, so open and reloaded tabs kept the old bundle until
# a hard refresh. The new worker takes over once installed and reloads the tabs it now controls. The reloads are not
# held in waitUntil: their requests wait for activation to finish.
SERVICE_WORKER_TAKEOVER = (
    'self.addEventListener("install",()=>self.skipWaiting());'
    'self.addEventListener("activate",()=>{self.clients.matchAll({type:"window"})'
    '.then(c=>c.forEach(w=>w.navigate(w.url).catch(()=>{})))});'
)
SERVICE_WORKER_TAKEOVER_PATCHED = SERVICE_WORKER_TAKEOVER + SERVICE_WORKER_SKIP_WAITING_STOCK


def patch_fluidd_service_worker(text: str) -> str:
    takeover = text.count(SERVICE_WORKER_TAKEOVER)
    if (
        len(SERVICE_WORKER_BUNDLE_ENTRY.findall(text)) != 1
        or text.count(SERVICE_WORKER_SKIP_WAITING_STOCK) != 1
        or takeover != text.count(SERVICE_WORKER_TAKEOVER_PATCHED)
    ):
        raise FluiddBundleError("Fluidd service worker does not match the reviewed QIDI source; preserving it.")
    text = SERVICE_WORKER_BUNDLE_ENTRY.sub(lambda _: _service_worker_bundle_entry(), text)
    if not takeover:
        text = text.replace(SERVICE_WORKER_SKIP_WAITING_STOCK, SERVICE_WORKER_TAKEOVER_PATCHED, 1)
    return text
