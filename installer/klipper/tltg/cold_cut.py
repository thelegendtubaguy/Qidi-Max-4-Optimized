# Filament cut and retract with the nozzle cold, for Valve Oil.
#
# The Max 4's cutter cuts cold filament, and its extruder sits above the
# cutter, so after a cut the extruder's gears move only filament that never
# enters the hotend. Klipper still refuses every extruder move, retracts
# included, while the nozzle is below min_extrude_temp, so a cut with the
# nozzle cold cut the filament and then stopped with "Extrude below minimum
# temp" at its 4 mm retract, skipping the restore of the acceleration it
# raised.
#
# cold_retracts() lets extruder retracts past that check for as long as it is
# held, and still refuses extrusion while the nozzle is below
# min_extrude_temp. Klipper checks a move when the G-code command queues it,
# and runs one command at a time, so holding it around one command's moves
# lets nothing else retract cold.
#
# TLTG_CUT_FILAMENT cuts while no print is running or paused and no QIDI Box
# flow is running or paused, at any nozzle temperature and without changing
# the heater: it homes X and Y if either isn't homed, runs the optimized cut
# inside cold_retracts(), and restores the acceleration and G-code state
# whether or not the cut finishes.

import contextlib
import logging

CUT_STATE = "tltg_cut_filament"
CUT_MACRO = "_OPTIMIZED_CUT_FILAMENT_MOTION"


class ColdCut:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self._held = False
        self.gcode.register_command(
            "TLTG_CUT_FILAMENT", self.cmd_TLTG_CUT_FILAMENT,
            desc="Cut the filament at the toolhead outside a print, at any "
                 "nozzle temperature")

    def _status(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None or not hasattr(obj, "get_status"):
            return {}
        try:
            status = obj.get_status(self.reactor.monotonic())
        except Exception:
            logging.exception("tltg_cold_cut: %s get_status failed", name)
            return {}
        return status if hasattr(status, "get") else {}

    # ------------------------------------------------------- cold retracts
    @contextlib.contextmanager
    def cold_retracts(self):
        """Let extruder retracts past Klipper's cold-extrusion check while
        held; extrusion below min_extrude_temp is still refused."""
        if self._held:
            yield
            return
        extruder = self.printer.lookup_object("toolhead").get_extruder()
        heater = extruder.get_heater()
        minimum = heater.min_extrude_temp
        previous = extruder.__dict__.get("check_move")
        check_original = extruder.check_move
        command_error = self.printer.command_error

        def check_move(move):
            if move.axes_d[3] > 0. and heater.smoothed_temp < minimum:
                raise command_error(
                    "Extrude below minimum temp\n"
                    "See the 'min_extrude_temp' config option for details")
            return check_original(move)

        self._held = True
        with heater.lock:
            heater.min_extrude_temp = float("-inf")
            heater.can_extrude = True
        extruder.check_move = check_move
        logging.info("tltg_cold_cut: cold retracts allowed")
        try:
            yield
        finally:
            if previous is None:
                extruder.__dict__.pop("check_move", None)
            else:
                extruder.check_move = previous
            with heater.lock:
                heater.min_extrude_temp = minimum
                heater.can_extrude = minimum <= 0. \
                    or heater.smoothed_temp >= minimum
            self._held = False
            logging.info("tltg_cold_cut: cold retracts refused again")

    # ----------------------------------------------------------------- cut
    def blocker(self):
        """Why a cut outside a print can't run now, or None."""
        state = self._status("print_stats").get("state")
        if state in ("printing", "paused"):
            return "a print is %s" % state
        task = self._status("multi_color_controller").get("task")
        if hasattr(task, "get") and task.get("is_paused"):
            return ("a QIDI Box flow is paused at %s. FLOW_RETRY tries that "
                    "step again and FLOW_STOP ends the flow"
                    % (task.get("current_step") or "a failed step",))
        if hasattr(task, "get") and (task.get("flow_id") not in (None, 0)
                                     or task.get("current_queue")
                                     or task.get("current_step")):
            return "a QIDI Box task is running"
        return None

    def cmd_TLTG_CUT_FILAMENT(self, gcmd):
        blocker = self.blocker()
        if blocker is not None:
            raise gcmd.error("TLTG_CUT_FILAMENT not run: %s." % (blocker,))
        accel = self._status("toolhead").get("max_accel")
        self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=%s"
                                           % (CUT_STATE,))
        try:
            # Rendered after homing, so the cut starts from where X and Y are.
            self.gcode.run_script_from_command("G28 O X Y")
            with self.cold_retracts():
                self.gcode.run_script_from_command(CUT_MACRO)
        finally:
            if not self.printer.is_shutdown():
                restore = "RESTORE_GCODE_STATE NAME=%s" % (CUT_STATE,)
                if accel:
                    restore = "SET_VELOCITY_LIMIT ACCEL=%.3f\n%s" % (accel,
                                                                     restore)
                self.gcode.run_script_from_command(restore)
        gcmd.respond_info("Filament cut.")


def load_config(config):
    return ColdCut(config)
