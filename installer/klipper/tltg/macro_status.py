# Cheap printer facts for QIDI Max 4 Optimized macros.
#
# Klipper deep-copies an object's whole status the first time a macro reads
# it, on its main thread. The optimized Box macros checked for a Box with
# printer["box_extras"], printer.gcode.commands, and
# printer.multi_color_controller, which together copy about 40 ms of status
# on every filament change, temperature wait, and cut, and the homing
# override read printer.configfile, about 50 ms, on every G28. QIDI's Box
# motor moves allow only 50 ms for Klipper to keep their endstops in sync.
#
# This module gives macros the same answers from a status of a few bytes:
#   box_available  a USB Box is configured, or QIDI's tool change is present
#                  with an RS-485 or multi_color_controller Box counted
#   vendor_flow    QIDI's tool change, T_MANAGER, is registered
#   loaded_slot    the slot multi_color_controller reports as loaded, or ""
#                  without it
#   max_accel      [printer] max_accel from printer.cfg

import logging

VENDOR_TOOL_CHANGE = "T_MANAGER"


class MacroStatus:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.max_accel = config.getsection("printer").getfloat("max_accel")
        self.status_failed = set()

    def _status(self, name, eventtime):
        obj = self.printer.lookup_object(name, None)
        if obj is None or not hasattr(obj, "get_status"):
            return {}
        try:
            status = obj.get_status(eventtime)
        except Exception:
            if name not in self.status_failed:
                logging.exception("tltg_macro_status: %s get_status failed",
                                  name)
            self.status_failed.add(name)
            return {}
        self.status_failed.discard(name)
        return status if hasattr(status, "get") else {}

    def vendor_flow(self):
        commands = getattr(self.gcode, "status_commands", None)
        if commands is None:
            commands = self.gcode.get_status(None).get("commands", {})
        return VENDOR_TOOL_CHANGE in commands

    def box_available(self, eventtime):
        if self.printer.lookup_object("box_extras", None) is not None:
            return True
        if not self.vendor_flow():
            return False
        # box485's status is tiny; multi_color_controller's is not.
        for name in ("box485", "multi_color_controller"):
            try:
                if int(self._status(name, eventtime).get("box_count", 0)) > 0:
                    return True
            except (TypeError, ValueError):
                pass
        return False

    def loaded_slot(self, eventtime):
        controller = self.printer.lookup_object("multi_color_controller", None)
        if controller is None:
            return ""
        # With a USB Box, multi_color_controller reports box_extras'
        # loaded_slot, which is the saved last_load_slot.
        box_extras = self.printer.lookup_object("box_extras", None)
        adapter = getattr(controller, "box_adapter", None)
        save_vars = self.printer.lookup_object("save_variables", None)
        variables = getattr(save_vars, "allVariables", None)
        if box_extras is not None and getattr(controller, "_initialized", False) \
                and getattr(adapter, "box1base", None) is box_extras \
                and isinstance(variables, dict):
            return variables.get("last_load_slot", "slot16")
        box = self._status("multi_color_controller", eventtime).get("box")
        return box.get("loaded_slot", "") if hasattr(box, "get") else ""

    def get_status(self, eventtime=None):
        if eventtime is None:
            eventtime = self.printer.get_reactor().monotonic()
        return {
            "box_available": self.box_available(eventtime),
            "vendor_flow": self.vendor_flow(),
            "loaded_slot": self.loaded_slot(eventtime),
            "max_accel": self.max_accel,
        }


def load_config(config):
    return MacroStatus(config)
