from __future__ import annotations

from .errors import InstallerError


OPERATION = "moonraker_spoolman_box_slots"
FILE = "/home/qidi/moonraker/moonraker/components/spoolman.py"
RESTART_SERVICE = "moonraker.service"

# QIDI ships Moonraker 0.9.3's Spoolman component unchanged. Upstream later fixed two problems that a QIDI Box hits
# (Arksine/moonraker b3f9566 and 06cdffa): usage after a filament change was charged only once the extruder passed
# the furthest point the previous spool reached, so every Box unload's extruder pull went uncharged on the new spool,
# and Tornado before 6.5, which QIDI ships, can drop a pinged websocket early. The ready handler also seeds the last
# extruder position, because tltg_spoolman switches spools as soon as Klipper starts, before the toolhead reports a
# move. A spool picked in Fluidd while a Box slot is loaded is passed to tltg_spoolman as that slot's spool.
IMPORT_STOCK = (
    "import tornado.websocket as tornado_ws",
    "from ..common import RequestType, HistoryFieldData",
)
IMPORT_PATCHED = (
    "import tornado.websocket as tornado_ws",
    "from tornado import version_info as tornado_version",
    "from ..common import RequestType, HistoryFieldData",
)
INIT_STOCK = (
    "        self._highest_epos: float = 0",
    '        self._current_extruder: str = "extruder"',
)
INIT_PATCHED = (
    "        self._highest_epos: float = 0",
    "        self._last_epos: float = 0",
    "        self._tltg_slot_tasks: set = set()",
    '        self._current_extruder: str = "extruder"',
)
PING_STOCK = (
    "                    ping_interval=20.,",
    "                    ping_timeout=60.",
)
PING_PATCHED = (
    "                    # tltg-optimized: Tornado before 6.5 can close a pinged websocket early",
    "                    ping_interval=None if tornado_version < (6, 5) else 20.",
)
READY_STOCK = ("            self._highest_epos = initial_e_pos",)
READY_PATCHED = ("            self._highest_epos = self._last_epos = initial_e_pos",)
STATUS_STOCK = (
    '        epos: float = toolhead.get("position", [0, 0, 0, self._highest_epos])[3]',
    '        extr = toolhead.get("extruder", self._current_extruder)',
)
STATUS_PATCHED = (
    '        epos: float = toolhead.get("position", [0, 0, 0, self._highest_epos])[3]',
    "        self._last_epos = epos",
    '        extr = toolhead.get("extruder", self._current_extruder)',
)
SET_STOCK = (
    "        self.database.insert_item(DB_NAMESPACE, ACTIVE_SPOOL_KEY, spool_id)",
    "        self.server.send_event(",
)
SET_PATCHED = (
    "        self.database.insert_item(DB_NAMESPACE, ACTIVE_SPOOL_KEY, spool_id)",
    "        # tltg-optimized: charge the new spool from the current extruder position",
    "        self._highest_epos = self._last_epos",
    "        self.server.send_event(",
)
REQUEST_STOCK = (
    '            spool_id = web_request.get_int("spool_id", None)',
    "            self.set_active_spool(spool_id)",
    "        # For GET requests we will simply return the spool_id",
    '        return {"spool_id": self.spool_id}',
)
REQUEST_PATCHED = (
    '            spool_id = web_request.get_int("spool_id", None)',
    "            self.set_active_spool(spool_id)",
    "            # tltg-optimized: a spool picked while a QIDI Box slot is loaded is that slot's spool",
    "            task = self.eventloop.create_task(self._tltg_assign_loaded_slot(spool_id))",
    "            self._tltg_slot_tasks.add(task)",
    "            task.add_done_callback(self._tltg_slot_tasks.discard)",
    "        # For GET requests we will simply return the spool_id",
    '        return {"spool_id": self.spool_id}',
    "",
    "    async def _tltg_assign_loaded_slot(self, spool_id: Optional[int]) -> None:",
    "        try:",
    "            result = await self.klippy_apis.query_objects(",
    '                {"tltg_spoolman": ["loaded_slot"]}, default={}',
    "            )",
    '            if result.get("tltg_spoolman", {}).get("loaded_slot") is None:',
    "                return",
    "            await self.klippy_apis.run_gcode(",
    '                f"TLTG_SPOOLMAN_SLOT SPOOL={spool_id or 0}"',
    "            )",
    "        except Exception:",
    '            logging.exception("Unable to assign the spool to the loaded QIDI Box slot")',
)
BLOCKS = (
    (IMPORT_STOCK, IMPORT_PATCHED),
    (INIT_STOCK, INIT_PATCHED),
    (PING_STOCK, PING_PATCHED),
    (READY_STOCK, READY_PATCHED),
    (STATUS_STOCK, STATUS_PATCHED),
    (SET_STOCK, SET_PATCHED),
    (REQUEST_STOCK, REQUEST_PATCHED),
)


class MoonrakerSpoolmanError(InstallerError):
    pass


def patch_spoolman(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    blocks = [(newline.join(stock) + newline, newline.join(patched) + newline) for stock, patched in BLOCKS]
    recognized = "class SpoolManager:" in text and 'ACTIVE_SPOOL_KEY = "spoolman.spool_id"' in text
    if recognized and all(text.count(patched) == 1 and text.count(stock) == 0 for stock, patched in blocks):
        return text
    if recognized and all(text.count(stock) == 1 for stock, _ in blocks):
        result = text
        for stock, patched in blocks:
            result = result.replace(stock, patched, 1)
        compile(result, "spoolman.py", "exec")
        return result
    raise MoonrakerSpoolmanError("Moonraker spoolman.py does not match the reviewed QIDI source; preserving it.")
