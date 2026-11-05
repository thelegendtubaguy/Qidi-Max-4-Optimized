# Cheap printer facts for Valve Oil macros.
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
#   input_shaper   loaded: [input_shaper] exists, so SET_INPUT_SHAPER works
#                  unshaped_axes: axes whose live shaper has no frequency, so
#                  calibration and SET_INPUT_SHAPER count without a restart
#                  saved: both axes have a frequency in printer.cfg, including
#                  a calibration waiting for SAVE_CONFIG

import logging

VENDOR_TOOL_CHANGE = "T_MANAGER"
SHAPER_AXES = ("x", "y")


class MacroStatus:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.max_accel = config.getsection("printer").getfloat("max_accel")
        self.startup_shaper_freq = {}
        if config.has_section("input_shaper"):
            section = config.getsection("input_shaper")
            for axis in SHAPER_AXES:
                self.startup_shaper_freq[axis] = section.getfloat(
                    "shaper_freq_" + axis, 0., note_valid=False)
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

    def unshaped_axes(self, input_shaper):
        if input_shaper is None:
            return "".join(SHAPER_AXES)
        try:
            return "".join(shaper.axis for shaper in input_shaper.get_shapers()
                           if not shaper.params.shaper_freq > 0.)
        except Exception:
            if "input_shaper" not in self.status_failed:
                logging.exception("tltg_macro_status: input_shaper check failed")
            self.status_failed.add("input_shaper")
            return ""

    def saved_shaper_freq(self, axis):
        # SHAPER_CALIBRATE stores its result in configfile's autosave, which
        # also holds the SAVE_CONFIG values printer.cfg was loaded with.
        configfile = self.printer.lookup_object("configfile", None)
        autosave = getattr(getattr(configfile, "autosave", None), "fileconfig", None)
        option = "shaper_freq_" + axis
        try:
            if autosave is not None and autosave.has_option("input_shaper", option):
                return float(autosave.get("input_shaper", option))
        except ValueError:
            return 0.
        return self.startup_shaper_freq.get(axis, 0.)

    def input_shaper(self):
        input_shaper = self.printer.lookup_object("input_shaper", None)
        return {
            "loaded": input_shaper is not None,
            "unshaped_axes": self.unshaped_axes(input_shaper),
            "saved": all(self.saved_shaper_freq(axis) > 0. for axis in SHAPER_AXES),
        }

    def get_status(self, eventtime=None):
        if eventtime is None:
            eventtime = self.printer.get_reactor().monotonic()
        return {
            "box_available": self.box_available(eventtime),
            "vendor_flow": self.vendor_flow(),
            "loaded_slot": self.loaded_slot(eventtime),
            "max_accel": self.max_accel,
            "input_shaper": self.input_shaper(),
        }


def load_config(config):
    return MacroStatus(config)
