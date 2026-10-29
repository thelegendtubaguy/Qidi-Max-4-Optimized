from __future__ import annotations

from .errors import InstallerError


OPERATION = "moonraker_print_start_3mf_plate"
FILE = "/home/qidi/moonraker/moonraker/components/klippy_apis.py"
RESTART_SERVICE = "moonraker.service"

# QIDI's printer.print.start defaults a missing plate to 1, so a 3MF sliced from another plate fails in
# virtual_sdcard with a missing plate_1.gcode. Slicer uploads pass the plate; Fluidd, history reprints, and the
# job queue do not. A start without a plate now prints the plate the 3MF was sliced on, which is also the plate
# its metadata and preview describe.
REQUEST_STOCK = ("        plateindex: str = web_request.get_str('plateindex', '1')",)
REQUEST_PATCHED = ("        plateindex: Optional[str] = web_request.get_str('plateindex', None)",)
# QIDI's cloud download always sends a plate and publishes it; keep its value defined.
CLOUD_STOCK = ("                plateindex,          # plateindex",)
CLOUD_PATCHED = ('                plateindex or "1",   # plateindex',)
START_STOCK = (
    "    async def start_print(",
    "        self,",
    "        filename: str,",
    "        wait_klippy_started: bool = False,",
    "        user: Optional[UserInfo] = None,",
    '        plateindex: str = "1",',
    '        uid: str = "native",',
    "        need_extract: bool = True,",
    "    ) -> str:",
)
START_PATCHED = (
    "    def _tltg_3mf_plate_index(self, filename: str) -> str:",
    "        # tltg-optimized: a 3MF started without a plate prints the plate it was sliced on",
    '        if not filename.lower().endswith(".3mf"):',
    '            return "1"',
    "        import xml.etree.ElementTree as ET",
    '        path = os.path.join(os.path.expanduser("~"), "printer_data", "gcodes", filename)',
    "        try:",
    "            with zipfile.ZipFile(path) as zf:",
    '                root = ET.fromstring(zf.read("Metadata/slice_info.config"))',
    '            for item in root.findall(".//metadata"):',
    '                if item.get("key") == "index":',
    '                    index = int(item.get("value", "1"))',
    '                    return str(index) if index > 0 else "1"',
    "        except Exception as e:",
    '            logging.warning(f"Unable to read the sliced plate of {filename}: {e}")',
    '        return "1"',
    "",
    "    async def start_print(",
    "        self,",
    "        filename: str,",
    "        wait_klippy_started: bool = False,",
    "        user: Optional[UserInfo] = None,",
    "        plateindex: Optional[str] = None,",
    '        uid: str = "native",',
    "        need_extract: bool = True,",
    "    ) -> str:",
    "        if plateindex is None:",
    "            plateindex = self._tltg_3mf_plate_index(filename)",
)
BLOCKS = ((REQUEST_STOCK, REQUEST_PATCHED), (CLOUD_STOCK, CLOUD_PATCHED), (START_STOCK, START_PATCHED))


class MoonrakerKlippyApisError(InstallerError):
    pass


def patch_klippy_apis(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    blocks = [(newline.join(stock) + newline, newline.join(patched) + newline) for stock, patched in BLOCKS]
    recognized = "class KlippyAPI(APITransport):" in text and "import zipfile" in text
    if recognized and all(text.count(patched) == 1 and text.count(stock) == 0 for stock, patched in blocks):
        return text
    if recognized and all(text.count(stock) == 1 for stock, _ in blocks):
        result = text
        for stock, patched in blocks:
            result = result.replace(stock, patched, 1)
        compile(result, "klippy_apis.py", "exec")
        return result
    raise MoonrakerKlippyApisError("Moonraker klippy_apis.py does not match the reviewed QIDI source; preserving it.")
