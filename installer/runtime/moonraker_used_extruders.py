from __future__ import annotations

from .errors import InstallerError


OPERATION = "moonraker_metadata_used_extruders"
FILE = "/home/qidi/moonraker/moonraker/components/file_manager/metadata.py"
RESTART_SERVICE = "moonraker.service"

# Fluidd's Box slot dialog lists the tools in a file's used_extruders. QIDI's metadata.py reads them from a
# `; used_extruders =` line that OrcaSlicer never writes, so OrcaSlicer G-code named no tools. A G-code file
# without that line now names the filaments its `; filament used [mm]` footer gives a length.
GCODE_STOCK = (
    "            except ValueError:",
    "                extruders = []",
    "                return extruders",
    "        extruders = []",
    "        return extruders",
)
GCODE_PATCHED = (
    "            except ValueError:",
    "                extruders = []",
    "                return extruders",
    "        # tltg-optimized: OrcaSlicer writes no used_extruders line; the filaments it used have a length",
    "        line = regex_find_string(r'filament\\sused\\s\\[mm\\]\\s=\\s(%S)\\n', self.footer_data)",
    '        return [i for i, mm in enumerate(regex_find_floats(r"(%F)", line or "")) if mm > 0]',
)
# A 3MF took them from Metadata/plate_N.json, but when OrcaSlicer exports several plates together it writes
# every plate's filaments into the plate selected in its window and none into the others. slice_info.config
# lists each plate's own filaments, numbered from 1.
SLICE_INFO_STOCK = (
    '                    plate_num = len(xml_root.findall("plate"))',
)
SLICE_INFO_PATCHED = (
    '                    plate_num = len(xml_root.findall("plate"))',
    "                    # tltg-optimized: each plate's own filaments; plate_N.json can hold another plate's",
    "                    metadata['used_extruders'] = sorted({",
    '                        int(filament.get("id")) - 1',
    '                        for filament in plate.findall("filament")',
    '                        if (filament.get("id") or "").isdigit() and int(filament.get("id")) > 0',
    "                    })",
)
PLATE_JSON_STOCK = (
    "                metadata['used_extruders'] = plate_json.get('filament_ids')",
)
PLATE_JSON_PATCHED = (
    "                if not metadata.get('used_extruders'):",
    "                    metadata['used_extruders'] = plate_json.get('filament_ids')",
)
BLOCKS = (
    (GCODE_STOCK, GCODE_PATCHED),
    (SLICE_INFO_STOCK, SLICE_INFO_PATCHED),
    (PLATE_JSON_STOCK, PLATE_JSON_PATCHED),
)
# The 3MF blocks are shaped by the plate-selection patch, which runs first.
PLATE_SELECTION_MARKER = "def _3mf_selected_plate_index(xml_data: str) -> int:"


class MoonrakerUsedExtrudersError(InstallerError):
    pass


def patch_used_extruders(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    blocks = [(newline.join(stock) + newline, newline.join(patched) + newline) for stock, patched in BLOCKS]
    recognized = "def parse_used_extruders(self)" in text and PLATE_SELECTION_MARKER in text
    if recognized and all(text.count(patched) == 1 for _, patched in blocks):
        return text
    if recognized and all(text.count(stock) == 1 for stock, _ in blocks):
        result = text
        for stock, patched in blocks:
            result = result.replace(stock, patched, 1)
        compile(result, "metadata.py", "exec")
        return result
    raise MoonrakerUsedExtrudersError("Moonraker metadata.py does not match the reviewed QIDI source; preserving it.")
