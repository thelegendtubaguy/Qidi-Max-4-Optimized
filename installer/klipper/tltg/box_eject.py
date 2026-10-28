# QIDI Box eject without a toolhead park for QIDI Max 4 Optimized.
#
# QIDI's eject step parks the toolhead over the waste chute before the slot
# pulls its filament back, and the flow's completion script parks it again
# before turning the hotend and extruder off. MOVE_TO_TRASH homes X and Y
# first, so ejecting on an unhomed printer homes the toolhead.
#
# QIDI runs the eject step alone only when the ejected slot's filament is not
# in the toolhead path: the hub sensor is clear, or another slot's filament is
# loaded. The park serves no purpose then, so during an eject-only flow a
# leading MOVE_TO_TRASH line is dropped from the scripts QIDI's Box controller
# and Box adapter send. Everything else runs unchanged, and flows that heat
# and unload before ejecting keep the park.

import logging

PARK = "MOVE_TO_TRASH\n"
EJECT_ONLY = ["BOX_EJECT"]


class _ParkFilter:
    """QIDI's G-code object, minus the park during an eject-only flow."""

    def __init__(self, gcode, eject_only):
        self._gcode = gcode
        self._eject_only = eject_only

    def run_script_from_command(self, script, *args, **kwargs):
        if isinstance(script, str) and script.startswith(PARK) \
                and self._eject_only():
            logging.info("tltg_box_eject: eject without a toolhead park")
            script = script[len(PARK):]
            if not script.strip():
                return None
        return self._gcode.run_script_from_command(script, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._gcode, name)


class BoxEject:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.controller = None
        self.manager = None
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        controller = self.printer.lookup_object("multi_color_controller", None)
        manager = getattr(controller, "task_queue_manager", None)
        start_flow = getattr(manager, "start_flow", None)
        if not callable(start_flow) or not hasattr(manager, "current_task"):
            logging.info("tltg_box_eject: inactive: QIDI Box flow controller "
                         "not found")
            return
        self.controller = controller
        self.manager = manager
        manager.start_flow = self._wrap_start_flow(start_flow)
        logging.info("tltg_box_eject: active")

    def _wrap_start_flow(self, original):
        # QIDI creates its Box adapter after Klipper is ready, so the filter
        # goes on whichever controller and adapter start each flow.
        def start_flow(*args, **kwargs):
            try:
                self._filter_scripts()
            except Exception:
                logging.exception("tltg_box_eject: filter install failed")
            return original(*args, **kwargs)
        return start_flow

    def _filter_scripts(self):
        for owner in (self.controller,
                      getattr(self.controller, "box_adapter", None),
                      getattr(self.manager, "operation_adapter", None)):
            gcode = getattr(owner, "gcode", None)
            if gcode is None or isinstance(gcode, _ParkFilter) \
                    or not callable(getattr(gcode, "run_script_from_command",
                                            None)):
                continue
            owner.gcode = _ParkFilter(gcode, self._eject_only)
            logging.info("tltg_box_eject: filtering %s scripts",
                         type(owner).__name__)

    def _eject_only(self):
        try:
            task = self.manager.current_task
            return task is not None and list(task.queue) == EJECT_ONLY
        except Exception:
            logging.exception("tltg_box_eject: flow check failed")
            return False


def load_config(config):
    return BoxEject(config)
