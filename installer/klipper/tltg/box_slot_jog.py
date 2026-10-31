# QIDI Box slot jog for QIDI Max 4 Optimized.
#
# TLTG_BOX_SLOT_JOG SLOT=<n> DISTANCE=<mm> [SPEED=<mm/s>] moves one Box
# slot's filament toward the toolhead (positive DISTANCE) or back toward the
# spool (negative), whatever the slot, hub, and toolhead sensors read and
# whatever QIDI's saved slot state says. It refuses only while a print is
# running or paused or a QIDI Box task is running, because those own the slot
# motors.
#
# The slot motor is borrowed from QIDI's Box code for the move and handed
# back afterwards, the way the cold feed measurements in
# openspec/observations/qidi-box/hardware-and-protocols.md drove it. QIDI's
# saved slot state is left alone; tltg_box_loaded_slot's hub record is
# updated as it is for QIDI's own slot motion.

import logging

import chelper
from . import force_move

SENSOR_NAME = "filament_switch_sensor filament_switch_sensor"
ACCEL = 100.
DEFAULT_SPEED = 20.
MAX_SPEED = 100.
MAX_DISTANCE = 1500.
ENABLE_LEAD = 0.300
ENABLE_SETTLE = 0.100
HUB_SETTLE = 0.100


def slot_label(slot):
    """Name a slot the way the QIDI Box card does: slot 5 is 2B."""
    return "%d%s" % (slot // 4 + 1, "ABCD"[slot % 4])


class BoxSlotJog:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        ffi_main, ffi_lib = chelper.get_ffi()
        self.trapq = ffi_main.gc(ffi_lib.trapq_alloc(), ffi_lib.trapq_free)
        self.sk = ffi_main.gc(ffi_lib.cartesian_stepper_alloc(b"x"),
                              ffi_lib.free)
        self.trapq_append = ffi_lib.trapq_append
        self.trapq_finalize_moves = ffi_lib.trapq_finalize_moves
        self.printer.lookup_object("gcode").register_command(
            "TLTG_BOX_SLOT_JOG", self.cmd_TLTG_BOX_SLOT_JOG,
            desc="Move a QIDI Box slot's filament in (+) or out (-) by "
                 "DISTANCE mm")

    def _status(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None or not hasattr(obj, "get_status"):
            return {}
        try:
            status = obj.get_status(self.reactor.monotonic())
        except Exception:
            logging.exception("tltg_box_slot_jog: %s get_status failed", name)
            return {}
        return status if hasattr(status, "get") else {}

    def _blocker(self):
        state = self._status("print_stats").get("state")
        if state in ("printing", "paused"):
            return "a print is %s" % state
        # Idle reports flow_id None with an empty queue and step.
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

    def _move(self, stepper, distance, speed, until=None, piece=None):
        """Move the slot motor up to DISTANCE mm, in PIECE mm moves when
        given, stopping after the first move that leaves UNTIL() true.
        Return (mm moved, whether UNTIL() ended it, and False if QIDI's Box
        code took the motor during the move)."""
        toolhead = self.printer.lookup_object("toolhead")
        toolhead.flush_step_generation()
        enable = self.printer.lookup_object("stepper_enable").lookup_enable(
            stepper.get_name())
        was_enabled = enable.is_motor_enabled()
        sensor = getattr(self.printer.lookup_object(SENSOR_NAME, None),
                         "runout_helper", None)
        sensor_enabled = getattr(sensor, "sensor_enabled", None)
        old_tq = stepper.set_trapq(None)
        old_sk = stepper.set_stepper_kinematics(self.sk)
        stepper.set_trapq(self.trapq)
        stepper.set_position([0., 0., 0.])
        # The move counts as printing to Klipper's idle timeout, so filament
        # leaving the toolhead sensor would otherwise run QIDI's runout pause.
        if sensor is not None:
            sensor.sensor_enabled = False
        owned = True
        moved = 0.
        stopped = False
        try:
            # QIDI's stepper_enable switches a motor on ENABLE_LEAD before
            # the time it is given, so leave that much room ahead of it.
            toolhead.dwell(ENABLE_LEAD)
            start = toolhead.get_last_move_time()
            enable.motor_enable(start)
            start += ENABLE_SETTLE
            step = abs(piece or distance)
            while abs(distance - moved) >= 0.01:
                if not (stepper.get_stepper_kinematics() == self.sk
                        and stepper.get_trapq() == self.trapq):
                    break
                length = min(step, abs(distance - moved))
                length = length if distance > 0 else -length
                axis_r, accel_t, cruise_t, cruise_v = \
                    force_move.calc_move_time(length, speed, ACCEL)
                self.trapq_append(self.trapq, start, accel_t, cruise_t,
                                  accel_t, moved, 0., 0., axis_r, 0., 0.,
                                  0., cruise_v, ACCEL)
                end = start + accel_t + cruise_t + accel_t
                toolhead.note_mcu_movequeue_activity(end,
                                                     set_step_gen_time=True)
                toolhead.dwell(end - toolhead.get_last_move_time())
                toolhead.flush_step_generation()
                toolhead.wait_moves()
                self.trapq_finalize_moves(self.trapq, end + 99999.9,
                                          end + 99999.9)
                moved += length
                if until is not None:
                    self.reactor.pause(self.reactor.monotonic() + HUB_SETTLE)
                    if until():
                        stopped = True
                        break
                start = toolhead.get_last_move_time()
        finally:
            try:
                toolhead.flush_step_generation()
                owned = (stepper.get_stepper_kinematics() == self.sk
                         and stepper.get_trapq() == self.trapq)
                if owned:
                    stepper.set_trapq(None)
                    stepper.set_stepper_kinematics(old_sk)
                    stepper.set_trapq(old_tq)
                    if not was_enabled:
                        enable.motor_disable(toolhead.get_last_move_time())
            finally:
                if sensor is not None:
                    sensor.sensor_enabled = sensor_enabled
        return moved, stopped, owned

    def blocker(self):
        """Why a slot can't move now, or None."""
        return self._blocker()

    def move(self, slot, distance, speed=DEFAULT_SPEED, until=None,
             piece=None):
        """Move slot number SLOT as TLTG_BOX_SLOT_JOG does, optionally in
        PIECE mm moves until UNTIL() is true, and update the hub record.
        Return (mm moved, whether UNTIL() ended it). Raises a command error
        if the slot is missing or QIDI's Box code takes the motor."""
        name = "slot%d" % slot
        stepper = getattr(self.printer.lookup_object("box_stepper " + name,
                                                     None), "stepper", None)
        if stepper is None or not hasattr(stepper, "set_stepper_kinematics"):
            raise self.printer.command_error("No QIDI Box slot %s"
                                             % slot_label(slot))
        tracker = self.printer.lookup_object("tltg_box_loaded_slot", None)
        before = None
        if tracker is not None:
            try:
                before = tracker.hub_occupied()
            except Exception:
                logging.exception("tltg_box_slot_jog: hub check failed")
        moved, stopped, owned = self._move(stepper, distance, speed, until,
                                           piece)
        if not owned:
            logging.warning("tltg_box_slot_jog: %s motor was taken during "
                            "the move", name)
            raise self.printer.command_error(
                "QIDI's Box code took slot %s's motor during the move. Run "
                "FIRMWARE_RESTART before using the Box." % slot_label(slot))
        if tracker is not None:
            if until is None:
                self.reactor.pause(self.reactor.monotonic() + HUB_SETTLE)
            try:
                tracker.record_motion(name, before)
            except Exception:
                logging.exception("tltg_box_slot_jog: hub record failed")
        return moved, stopped

    def cmd_TLTG_BOX_SLOT_JOG(self, gcmd):
        slot = gcmd.get_int("SLOT", minval=0, maxval=15)
        distance = gcmd.get_float("DISTANCE", minval=-MAX_DISTANCE,
                                  maxval=MAX_DISTANCE)
        speed = gcmd.get_float("SPEED", DEFAULT_SPEED, above=0.,
                               maxval=MAX_SPEED)
        if abs(distance) < 0.01:
            raise gcmd.error("DISTANCE must not be 0")
        stepper = getattr(self.printer.lookup_object(
            "box_stepper slot%d" % slot, None), "stepper", None)
        if stepper is None or not hasattr(stepper, "set_stepper_kinematics"):
            raise gcmd.error("No QIDI Box slot %s" % slot_label(slot))
        blocker = self._blocker()
        if blocker is not None:
            raise gcmd.error("Box slot not moved: %s" % blocker)
        self.move(slot, distance, speed)
        gcmd.respond_info("Box slot %s moved %s %.1f mm"
                          % (slot_label(slot), "in" if distance > 0 else "out",
                             abs(distance)))


def load_config(config):
    return BoxSlotJog(config)
