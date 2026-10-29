# QIDI Box filament ID guard for QIDI Max 4 Optimized.
#
# Before a Box load, QIDI's controller compares the nozzle temperatures of the
# target slot's saved filament ID and the last-loaded slot's. Its material
# lookup raises when either ID is missing from filament-0.4.json, and the
# command handler lets that through as an internal error that shuts Klipper
# down. QIDI already uses QIDI PLA Basic (QFA00) for saved IDs that aren't
# strings; the comparison now uses it for any ID the database doesn't know,
# such as the string 'None'.
#
# Setting the external spool's filament to a name and vendor missing from
# filament-0.4.json saved filament_slot16 = 'None', then raised. QIDI refuses
# the same request for a Box slot and saves nothing; the external spool now
# does too.

import logging

FALLBACK_ID = "QFA00"
FALLBACK_NAME = "QIDI PLA Basic"


class BoxFilamentGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.database = None
        self._reported = set()
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        controller = self.printer.lookup_object("multi_color_controller", None)
        # QIDI's controller, external spool adapter, and Box adapter share
        # this database object.
        database = getattr(controller, "fila_json", None)
        max_temp = getattr(database, "get_max_temp_id", None)
        if not callable(max_temp) or not callable(
                getattr(database, "get_filament_info_by_id", None)):
            logging.info("tltg_box_filament_guard: inactive: QIDI filament "
                         "database not found")
            return
        self.database = database
        database.get_max_temp_id = self._wrap_max_temp(max_temp)
        external = getattr(controller, "extre", None)
        set_info = getattr(external, "set_filament_information", None)
        find_id = getattr(getattr(external, "material_db", None),
                          "get_fila_id", None)
        if callable(set_info) and callable(find_id):
            external.set_filament_information = self._wrap_set_info(set_info,
                                                                    find_id)
            logging.info("tltg_box_filament_guard: active")
        else:
            logging.info("tltg_box_filament_guard: active; external spool "
                         "filament updates not found")

    def _report(self, message):
        logging.info("tltg_box_filament_guard: %s", message)
        if message in self._reported:
            return
        self._reported.add(message)
        self.gcode.respond_info(message)

    def _known(self, filament_id):
        database = self.database
        if isinstance(filament_id, str) \
                and database.get_filament_info_by_id(filament_id):
            return filament_id
        if not database.get_filament_info_by_id(FALLBACK_ID):
            return filament_id
        self._report("Box: saved filament ID %r is not in QIDI's filament "
                     "list, so %s temperatures are used. Set the slot's "
                     "filament to fix this." % (filament_id, FALLBACK_NAME))
        return FALLBACK_ID

    def _wrap_max_temp(self, original):
        def get_max_temp_id(*args, **kwargs):
            try:
                if not kwargs and len(args) == 2:
                    args = tuple(self._known(i) for i in args)
            except Exception:
                logging.exception("tltg_box_filament_guard: filament ID "
                                  "check failed")
            return original(*args, **kwargs)
        return get_max_temp_id

    def _wrap_set_info(self, original, find_id):
        # Called as (slot, color, filament, vendor) by UPDATE_FILAMENT_
        # INFORMATION and the set_filament_info web request.
        def set_filament_information(*args, **kwargs):
            try:
                if not kwargs and len(args) == 4:
                    _slot, _color, filament, vendor = args
                    if not find_id(filament, vendor):
                        message = ("External spool filament not changed: %s "
                                   "%s is not in QIDI's filament list"
                                   % (vendor, filament))
                        logging.info("tltg_box_filament_guard: %s", message)
                        self.gcode.respond_info(message)
                        return None
            except Exception:
                logging.exception("tltg_box_filament_guard: external spool "
                                  "filament check failed")
            return original(*args, **kwargs)
        return set_filament_information


def load_config(config):
    return BoxFilamentGuard(config)
