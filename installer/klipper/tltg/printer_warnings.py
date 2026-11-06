# Printer warnings for Valve Oil.
#
# Publishes the problems an operator should fix before printing as Klipper
# status, so Fluidd shows them on every page until they are gone, and the
# optimized macros print the same text in the console at startup and after
# every home:
#
#   warnings  a list of {"id", "level", "title", "message"}, with level
#             "warning" or "error"; empty when nothing is wrong

import logging


class PrinterWarnings:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.failed = False

    def _unshaped_accel(self, macro_status):
        optimized = self.printer.lookup_object(
            "gcode_macro _tltg_optimized_globals", None)
        variables = getattr(optimized, "variables", {})
        try:
            return min(macro_status.max_accel,
                       float(variables.get("unshaped_accel", 10000)))
        except (TypeError, ValueError):
            return macro_status.max_accel

    def _input_shaper(self):
        macro_status = self.printer.lookup_object("tltg_macro_status", None)
        if macro_status is None:
            return []
        shaper = macro_status.input_shaper()
        if shaper["saved"] and not shaper["unshaped_axes"]:
            return []
        limit = ("limiting acceleration during homing and meshing to %d mm/s²."
                 " Run input shaper calibration when possible."
                 % self._unshaped_accel(macro_status))
        if shaper["unshaped_axes"]:
            return [{
                "id": "input_shaper_off",
                "level": "error",
                "title": "Input shaping is off.",
                "message": "TLTG Optimizations is " + limit,
            }]
        return [{
            "id": "input_shaper_uncalibrated",
            "level": "error",
            "title": "No input shaper calibration is saved.",
            "message": "TLTG Optimizations is utilizing Qidi's default shaper"
                       " and " + limit,
        }]

    def get_status(self, eventtime=None):
        try:
            warnings = self._input_shaper()
        except Exception:
            if not self.failed:
                logging.exception("tltg_printer_warnings: check failed")
            self.failed = True
            return {"warnings": []}
        self.failed = False
        return {"warnings": warnings}


def load_config(config):
    return PrinterWarnings(config)
