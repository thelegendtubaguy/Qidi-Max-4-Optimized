# QIDI Box feeder load/unload test for QIDI Max 4 Optimized.
#
# Development tool, not part of the installed package. The bundle ships this
# file but no manifest entry installs it. Repeatedly feeds one Box slot from its
# parked position to the toolhead filament sensor and back, without heating or
# moving the extruder.
#
# Why it exists: it measures a slot's park-to-toolhead-sensor distance, its
# spread between runs, and Box-only load/unload timing at chosen speeds, cold,
# with no vendor flow involved. It produced the cold feed measurements in
# openspec/observations/qidi-box/hardware-and-protocols.md and is the tool to
# reach for when re-measuring the feed path, for example after a PTFE change,
# or when checking Box motion on new firmware before tuning
# tltg_box_feed_motion. It does not use or change tltg_box_feed_motion
# settings, and vendor loads measure from a later start point (after the
# vendor's load pre-stage), so its distances are longer than vendor
# three-stage-home travel.
#
# Install for testing (printer idle, nozzle cold, filament parked in the slot):
#   1. Copy this file to ~/klipper/klippy/extras/tltg_box_feed_test.py.
#   2. Create ~/printer_data/config/tltg-optimized-macros/box_feed_test.cfg
#      containing the single section line: [tltg_box_feed_test]
#   3. Restart the Klipper service (a host RESTART keeps an already imported
#      module), then run TLTG_BOX_FEED_CHECK SLOT=<n> before any motion.
# Remove: delete the .cfg first, then the .py, then restart the Klipper service.
# Running the package installer also deletes the .cfg, because it mirrors
# tltg-optimized-macros/, which leaves the .py inert.
#
# This test polls the toolhead sensor rather than homing on it, so each load
# runs a fast move that stops short of the last observed trip point and then
# inches in STEP increments, reading the sensor after each increment completes.
# Overshoot past the sensor is bounded by STEP.
#
# The vendor slot motor is borrowed for each cycle and handed back afterwards.
# Each move is checked for interference from vendor Box behavior (auto-reload,
# feed assist, task flows); any sign of it ends the session.
#
# Commands:
#   TLTG_BOX_FEED_CHECK SLOT=<n>          preflight report, no motion
#   TLTG_BOX_FEED_TEST SLOT=<n> [...]     start a session; optional CYCLES,
#       LOAD_SPEED, LOAD_ACCEL, UNLOAD_SPEED, UNLOAD_ACCEL, STEP, STEP_SPEED,
#       FAST, MAX, MARGIN, MIN_MARGIN, MARGIN_STEP, PAUSE, RESET (see cmd_TEST)
#   TLTG_BOX_FEED_STOP                    stop after the current cycle
#
# Results append to tltg_box_feed_test.csv beside klippy.log.

import logging
import math
import os
import time

import chelper
from . import force_move

CSV_NAME = "tltg_box_feed_test.csv"
SENSOR_NAME = "filament_switch_sensor filament_switch_sensor"
ENABLE_SETTLE = 0.100
STEP_TOLERANCE = 2
CSV_FIELDS = (
    "time", "session", "cycle", "slot", "result",
    "load_speed", "load_accel", "unload_speed", "unload_accel",
    "step", "step_speed", "fast_mm", "trip_mm", "trip_delta_mm",
    "increments", "load_s", "unload_s",
    "hub_parked", "hub_loaded", "hub_unloaded", "note",
)


class FeedTestError(Exception):
    pass


class Interference(FeedTestError):
    pass


def _is_null(ptr):
    if ptr is None:
        return True
    ffi_main, ffi_lib = chelper.get_ffi()
    return ptr == ffi_main.NULL


class BoxFeedTest:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.settle_time = config.getfloat(
            "sensor_settle_time", 0.100, minval=0.020, maxval=1.0)
        ffi_main, ffi_lib = chelper.get_ffi()
        self.trapq = ffi_main.gc(ffi_lib.trapq_alloc(), ffi_lib.trapq_free)
        self.sk = ffi_main.gc(ffi_lib.cartesian_stepper_alloc(b"x"),
                              ffi_lib.free)
        self.trapq_append = ffi_lib.trapq_append
        self.trapq_finalize_moves = ffi_lib.trapq_finalize_moves
        self.next_cmd_time = 0.
        self.trips = {}
        self.session = None
        self.session_count = 0
        self.timer = self.reactor.register_timer(self._cycle_timer)
        self.printer.register_event_handler("klippy:shutdown",
                                            self._handle_shutdown)
        self.gcode.register_command(
            "TLTG_BOX_FEED_CHECK", self.cmd_CHECK,
            desc="Report Box feeder test preconditions without motion")
        self.gcode.register_command(
            "TLTG_BOX_FEED_TEST", self.cmd_TEST,
            desc="Cycle a Box slot between park and the toolhead sensor")
        self.gcode.register_command(
            "TLTG_BOX_FEED_STOP", self.cmd_STOP,
            desc="Stop the Box feeder test after the current cycle")
        self.gcode.register_command("_TLTG_BOX_FEED_CYCLE", self.cmd_CYCLE)

    # Object access
    def _slot(self, slot):
        obj = self.printer.lookup_object("box_stepper slot%d" % slot, None)
        if obj is None:
            raise FeedTestError("box_stepper slot%d not found" % slot)
        stepper = getattr(obj, "stepper", None)
        if stepper is None or not hasattr(stepper, "set_stepper_kinematics"):
            raise FeedTestError("box_stepper slot%d has no usable stepper"
                                % slot)
        return obj, stepper

    def _sensor(self):
        sensor = self.printer.lookup_object(SENSOR_NAME, None)
        if sensor is None:
            raise FeedTestError("%s not found" % SENSOR_NAME)
        return sensor.runout_helper

    def _filament_at_toolhead(self):
        return bool(self._sensor().filament_present)

    def _status(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None or not hasattr(obj, "get_status"):
            return {}
        try:
            status = obj.get_status(self.reactor.monotonic())
        except Exception:
            logging.exception("tltg_box_feed_test: %s get_status failed", name)
            return {}
        return status if hasattr(status, "get") else {}

    def _hub(self):
        # 01.01.07.01 publishes the hub sensor under the controller's box
        # section; older firmware published it on box_extras.
        box = self._status("multi_color_controller").get("box")
        if hasattr(box, "get") and "b_endstop_state" in box:
            return box["b_endstop_state"]
        return self._status("box_extras").get("b_endstop_state")

    def _flow_id(self):
        # Idle reports flow_id None with an empty queue and step.
        task = self._status("multi_color_controller").get("task")
        if not hasattr(task, "get"):
            return None
        flow = task.get("flow_id")
        if flow in (None, 0) and (task.get("current_queue")
                                  or task.get("current_step")):
            return "%s (queue %s, step %s)" % (
                flow, task.get("current_queue"), task.get("current_step"))
        return flow

    def _print_state(self):
        return self._status("print_stats").get("state")

    def _mcu_drift(self, stepper):
        # Raw MCU step count minus the host's commanded count. Constant unless
        # something steps the motor outside host step generation.
        params = stepper._get_position_cmd.send([stepper._oid])
        pos = params["pos"]
        if stepper._invert_dir:
            pos = -pos
        return pos - stepper.get_mcu_position()

    def _queue_owner(self, stepper):
        # After its own moves the vendor leaves a slot on a private motion
        # queue; only the extruder and toolhead queues make other motion drive
        # the slot.
        tq = stepper.get_trapq()
        if _is_null(tq):
            return "none"
        if tq == self.trapq:
            return "test"
        toolhead = self.printer.lookup_object("toolhead")
        if tq == toolhead.get_trapq():
            return "toolhead"
        extruder = toolhead.get_extruder()
        if hasattr(extruder, "get_trapq") and tq == extruder.get_trapq():
            return "extruder"
        return "vendor"

    def _box_snapshot(self):
        snap = {}
        for name, obj in self.printer.lookup_objects("box_stepper"):
            stepper = getattr(obj, "stepper", None)
            status = {}
            try:
                status = obj.get_status(self.reactor.monotonic()) or {}
            except Exception:
                pass
            snap[name] = (
                stepper.get_mcu_position() if stepper is not None else None,
                stepper.get_trapq() if stepper is not None else None,
                status.get("runout_button"),
            )
        return snap

    # Preconditions
    def _blockers(self, slot, obj, stepper):
        blockers = []
        state = self._print_state()
        if state in ("printing", "paused"):
            blockers.append("print_stats state is %s" % state)
        if self.session is not None and self.session.get("slot") != slot:
            blockers.append("a session is running on slot%d"
                            % self.session["slot"])
        if self._filament_at_toolhead():
            blockers.append("toolhead sensor reports filament")
        owner = self._queue_owner(stepper)
        if owner in ("extruder", "toolhead"):
            blockers.append("slot%d follows the %s motion queue (synced)"
                            % (slot, owner))
        if stepper.get_stepper_kinematics() == self.sk:
            blockers.append("slot%d is still held by this test" % slot)
        flow = self._flow_id()
        if flow not in (None, 0):
            blockers.append("vendor task flow %s is active" % flow)
        runout = self._status("box_stepper slot%d" % slot).get("runout_button")
        if runout != 0:
            blockers.append("slot%d runout_button=%s (0 means filament "
                            "present)" % (slot, runout))
        return blockers

    # Motor ownership
    def _take(self, stepper):
        toolhead = self.printer.lookup_object("toolhead")
        toolhead.flush_step_generation()
        sensor = self._sensor()
        enable = self.printer.lookup_object("stepper_enable").lookup_enable(
            stepper.get_name())
        old_tq = stepper.set_trapq(None)
        held = {
            "stepper": stepper,
            "old_tq": old_tq,
            "old_sk": stepper.set_stepper_kinematics(self.sk),
            "sensor_enabled": sensor.sensor_enabled,
            "enable": enable,
            "was_enabled": enable.is_motor_enabled(),
        }
        stepper.set_trapq(self.trapq)
        stepper.set_position([0., 0., 0.])
        # Runout handling treats any toolhead activity as printing, so each
        # unload would otherwise run PAUSE and the Box auto-reload path.
        sensor.sensor_enabled = False
        print_time = toolhead.get_last_move_time()
        enable.motor_enable(print_time)
        self.next_cmd_time = print_time + ENABLE_SETTLE
        return held

    def _owned(self, held):
        stepper = held["stepper"]
        return (stepper.get_stepper_kinematics() == self.sk
                and stepper.get_trapq() == self.trapq)

    def _release(self, held):
        stepper = held["stepper"]
        toolhead = self.printer.lookup_object("toolhead")
        restored = False
        try:
            toolhead.flush_step_generation()
            if self._owned(held):
                stepper.set_trapq(None)
                stepper.set_stepper_kinematics(held["old_sk"])
                stepper.set_trapq(held["old_tq"])
                if not held["was_enabled"]:
                    held["enable"].motor_disable(
                        toolhead.get_last_move_time())
                restored = True
        finally:
            self._sensor().sensor_enabled = held["sensor_enabled"]
        return restored

    # Motion
    def _move(self, held, movepos, speed, accel):
        stepper = held["stepper"]
        toolhead = self.printer.lookup_object("toolhead")
        if not self._owned(held):
            raise Interference("slot motor was re-routed before a move")
        start = max(toolhead.get_last_move_time(), self.next_cmd_time)
        startpos = stepper.get_commanded_position()
        dist = movepos - startpos
        if abs(dist) < 1e-6:
            return 0.
        axis_r, accel_t, cruise_t, cruise_v = force_move.calc_move_time(
            dist, speed, accel)
        self.trapq_append(self.trapq, start, accel_t, cruise_t, accel_t,
                          startpos, 0., 0., axis_r, 0., 0.,
                          0., cruise_v, accel)
        end = start + accel_t + cruise_t + accel_t
        self.next_cmd_time = end
        toolhead.note_mcu_movequeue_activity(end, set_step_gen_time=True)
        toolhead.dwell(end - toolhead.get_last_move_time())
        toolhead.flush_step_generation()
        toolhead.wait_moves()
        self.trapq_finalize_moves(self.trapq, end + 99999.9, end + 99999.9)
        return end - start

    def _settle(self):
        self.reactor.pause(self.reactor.monotonic() + self.settle_time)

    def _verify(self, held, session):
        if not self._owned(held):
            raise Interference("slot motor was re-routed during the move")
        drift = self._mcu_drift(held["stepper"])
        if abs(drift - session["drift"]) > STEP_TOLERANCE:
            raise Interference("slot motor moved outside host control "
                               "(%+d steps)" % (drift - session["drift"]))
        snap = self._box_snapshot()
        own = "box_stepper slot%d" % session["slot"]
        for name, before in session["snapshot"].items():
            after = snap.get(name)
            if after is None:
                raise Interference("%s disappeared" % name)
            if name != own and after[:2] != before[:2]:
                raise Interference("%s moved or was re-routed" % name)
            if after[2] != before[2]:
                raise Interference("%s runout_button changed %s -> %s"
                                   % (name, before[2], after[2]))
        flow = self._flow_id()
        if flow not in (None, 0):
            raise Interference("vendor task flow %s started" % flow)
        state = self._print_state()
        if state in ("printing", "paused"):
            raise Interference("print_stats state became %s" % state)

    # Cycle
    def _fast_target(self, session):
        trip = self.trips.get(session["slot"])
        if trip is None:
            return min(session["fast"], session["max"])
        margin = max(session["min_margin"], session["margin"])
        return max(0., min(trip - margin, session["max"]))

    def _load(self, held, session, row):
        fast = self._fast_target(session)
        row["fast_mm"] = round(fast, 2)
        started = time.time()
        self._move(held, fast, session["load_speed"], session["load_accel"])
        self._verify(held, session)
        self._settle()
        if self._filament_at_toolhead():
            raise FeedTestError(
                "toolhead sensor tripped during the fast move to %.1f mm; "
                "the trip point moved closer than the margin" % fast)
        position = fast
        increments = 0
        while position < session["max"] - 1e-6:
            position = min(position + session["step"], session["max"])
            self._move(held, position, session["step_speed"],
                       session["load_accel"])
            increments += 1
            self._verify(held, session)
            self._settle()
            if self._filament_at_toolhead():
                row["load_s"] = round(time.time() - started, 2)
                row["increments"] = increments
                return position
        raise FeedTestError("toolhead sensor did not trip within %.1f mm"
                            % session["max"])

    def _unload(self, held, session, row):
        started = time.time()
        self._move(held, 0., session["unload_speed"], session["unload_accel"])
        self._verify(held, session)
        self._settle()
        row["unload_s"] = round(time.time() - started, 2)
        if self._filament_at_toolhead():
            raise FeedTestError("toolhead sensor still reports filament "
                                "after returning to park")

    def _run_cycle(self, gcmd, session):
        slot = session["slot"]
        obj, stepper = self._slot(slot)
        blockers = self._blockers(slot, obj, stepper)
        if blockers:
            raise FeedTestError("; ".join(blockers))
        cycle = session["done"] + 1
        row = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "session": session["id"], "cycle": cycle, "slot": slot,
            "result": "fail",
            "hub_parked": self._hub(),
        }
        for key in ("load_speed", "load_accel", "unload_speed",
                    "unload_accel", "step", "step_speed"):
            row[key] = session[key]
        held = self._take(stepper)
        error = None
        try:
            session["drift"] = self._mcu_drift(stepper)
            session["snapshot"] = self._box_snapshot()
            load_error = None
            try:
                trip = self._load(held, session, row)
                row["trip_mm"] = round(trip, 2)
                row["hub_loaded"] = self._hub()
                first = session["first_trip"]
                if first is None:
                    session["first_trip"] = first = trip
                row["trip_delta_mm"] = round(trip - first, 2)
                known = self.trips.get(slot)
                self.trips[slot] = trip if known is None else min(known, trip)
                session["trip_list"].append(trip)
                session["margin"] -= session["margin_step"]
            except Interference:
                raise
            except FeedTestError as e:
                load_error = e
            # Return to park after any non-interference failure.
            try:
                self._unload(held, session, row)
                row["hub_unloaded"] = self._hub()
            except FeedTestError as e:
                if load_error is None or isinstance(e, Interference):
                    raise
                raise FeedTestError("%s; return to park failed: %s"
                                    % (load_error, e))
            error = load_error
        except Interference as e:
            error = Interference(
                "%s; filament left about %.1f mm past park"
                % (e, stepper.get_commanded_position()))
        except FeedTestError as e:
            error = e
        except Exception as e:
            error = e
            raise
        finally:
            restored = False
            session["done"] = cycle
            try:
                restored = self._release(held)
            finally:
                if error is None:
                    row["result"] = "ok"
                else:
                    row["note"] = str(error)
                    if isinstance(error, Interference):
                        row["result"] = "interference"
                if not restored:
                    row["note"] = ("%s; motor not handed back"
                                   % row.get("note", "")).lstrip("; ")
                self._write_row(row)
        if not restored:
            raise FeedTestError(
                "slot%d motor was taken by another owner and was NOT handed "
                "back; run FIRMWARE_RESTART before using the Box" % slot)
        if error is not None:
            raise FeedTestError("cycle %d: %s" % (cycle, error))
        gcmd.respond_info(
            "TLTG_BOX_FEED_TEST slot%d cycle %d/%d: trip %.2f mm "
            "(%+.2f vs first, within -%.2f mm) fast %.1f mm, %d increments, "
            "load %.1fs, unload %.1fs"
            % (slot, cycle, session["cycles"], row["trip_mm"],
               row["trip_delta_mm"], session["step"], row["fast_mm"],
               row["increments"], row["load_s"], row["unload_s"]))

    # Session
    def _write_row(self, row):
        path = os.path.join(self._log_dir(), CSV_NAME)
        try:
            new = not os.path.exists(path)
            with open(path, "a", encoding="utf-8") as handle:
                if new:
                    handle.write(",".join(CSV_FIELDS) + "\n")
                handle.write(",".join(
                    '"%s"' % str(row.get(key, "")).replace('"', "'")
                    for key in CSV_FIELDS) + "\n")
        except Exception:
            logging.exception("tltg_box_feed_test: cannot write %s", path)

    def _log_dir(self):
        log_file = self.printer.get_start_args().get("log_file")
        if log_file:
            return os.path.dirname(os.path.abspath(log_file))
        return os.getcwd()

    def _summary(self, session):
        trips = session["trip_list"]
        if not trips:
            return "no completed loads"
        mean = sum(trips) / len(trips)
        spread = math.sqrt(sum((t - mean) ** 2 for t in trips) / len(trips))
        return ("%d loads, trip min %.2f max %.2f mean %.2f sd %.2f mm"
                % (len(trips), min(trips), max(trips), mean, spread))

    def _end_session(self, reason):
        session = self.session
        self.session = None
        self.reactor.update_timer(self.timer, self.reactor.NEVER)
        if session is None:
            return
        self.gcode.respond_info(
            "TLTG_BOX_FEED_TEST slot%d session %d ended (%s): %s. Results: %s"
            % (session["slot"], session["id"], reason, self._summary(session),
               os.path.join(self._log_dir(), CSV_NAME)))

    def _cycle_timer(self, eventtime):
        session = self.session
        if session is None:
            return self.reactor.NEVER
        try:
            self.gcode.run_script("_TLTG_BOX_FEED_CYCLE")
        except Exception as e:
            logging.exception("tltg_box_feed_test: cycle failed")
            self._end_session("error: %s" % e)
            return self.reactor.NEVER
        if session["stop"]:
            self._end_session("stopped")
            return self.reactor.NEVER
        if session["done"] >= session["cycles"]:
            self._end_session("complete")
            return self.reactor.NEVER
        return self.reactor.monotonic() + session["pause"]

    def _handle_shutdown(self):
        self.session = None

    # Commands
    def cmd_CHECK(self, gcmd):
        slot = gcmd.get_int("SLOT", minval=0, maxval=15)
        obj, stepper = self._slot(slot)
        lines = [
            "slot%d: stepper %s on %s, step %.6f mm, %s kinematics, "
            "motion queue %s, motor %s"
            % (slot, stepper.get_name(), stepper.get_mcu().get_name(),
               stepper.get_step_dist(),
               "test" if stepper.get_stepper_kinematics() == self.sk
               else "vendor",
               self._queue_owner(stepper),
               "enabled" if self.printer.lookup_object("stepper_enable")
               .lookup_enable(stepper.get_name()).is_motor_enabled()
               else "disabled"),
            "runout_button=%s toolhead_filament=%s hub(b_endstop_state)=%s "
            "flow_id=%s print=%s mcu_drift=%d"
            % (self._status("box_stepper slot%d" % slot).get("runout_button"),
               self._filament_at_toolhead(), self._hub(), self._flow_id(),
               self._print_state(), self._mcu_drift(stepper)),
        ]
        controller = self.printer.lookup_object("multi_color_controller",
                                                None)
        status = self._status("multi_color_controller")
        lines.append("controller: object %s, status keys %s, task %r"
                     % (type(controller).__name__,
                        sorted(status.keys())[:12], status.get("task")))
        trip = self.trips.get(slot)
        lines.append("known trip: %s" % ("none" if trip is None
                                         else "%.2f mm" % trip))
        blockers = self._blockers(slot, obj, stepper)
        lines.append("READY" if not blockers
                     else "BLOCKED: " + "; ".join(blockers))
        gcmd.respond_info("\n".join(lines))

    def cmd_TEST(self, gcmd):
        if self.session is not None:
            raise gcmd.error("A Box feeder test is already running; "
                             "use TLTG_BOX_FEED_STOP")
        slot = gcmd.get_int("SLOT", minval=0, maxval=15)
        obj, stepper = self._slot(slot)
        if gcmd.get_int("RESET", 0):
            self.trips.pop(slot, None)
        load_speed = gcmd.get_float("LOAD_SPEED", 50., above=0., maxval=300.)
        load_accel = gcmd.get_float("LOAD_ACCEL", 50., above=0., maxval=2000.)
        step = gcmd.get_float("STEP", 2., minval=0.2, maxval=10.)
        session = {
            "id": self.session_count + 1,
            "slot": slot,
            "cycles": gcmd.get_int("CYCLES", 1, minval=1, maxval=10000),
            "fast": gcmd.get_float("FAST", 0., minval=0.),
            "max": gcmd.get_float("MAX", 1500., above=0., maxval=2500.),
            "load_speed": load_speed,
            "load_accel": load_accel,
            "unload_speed": gcmd.get_float("UNLOAD_SPEED", load_speed,
                                           above=0., maxval=300.),
            "unload_accel": gcmd.get_float("UNLOAD_ACCEL", load_accel,
                                           above=0., maxval=2000.),
            "step": step,
            "step_speed": gcmd.get_float("STEP_SPEED", 10., above=0.,
                                         maxval=50.),
            "margin": gcmd.get_float("MARGIN", 50., minval=step),
            "min_margin": gcmd.get_float("MIN_MARGIN", 10., minval=step),
            "margin_step": gcmd.get_float("MARGIN_STEP", 10., minval=0.),
            "pause": gcmd.get_float("PAUSE", 1., minval=0., maxval=600.),
            "done": 0,
            "stop": False,
            "first_trip": None,
            "trip_list": [],
        }
        if session["fast"] >= session["max"]:
            raise gcmd.error("FAST must be less than MAX")
        blockers = self._blockers(slot, obj, stepper)
        if blockers:
            raise gcmd.error("Box feeder test blocked: " + "; ".join(blockers))
        self.session_count += 1
        self.session = session
        trip = self.trips.get(slot)
        gcmd.respond_info(
            "TLTG_BOX_FEED_TEST slot%d session %d: %d cycle(s); first fast "
            "move %.1f mm (%s), then %.1f mm steps at %.1f mm/s up to %.1f mm"
            % (slot, session["id"], session["cycles"],
               self._fast_target(session),
               "FAST" if trip is None else "known trip %.2f mm" % trip,
               step, session["step_speed"], session["max"]))
        self.reactor.update_timer(self.timer, self.reactor.NOW)

    def cmd_STOP(self, gcmd):
        if self.session is None:
            gcmd.respond_info("No Box feeder test is running")
            return
        self.session["stop"] = True
        gcmd.respond_info("Box feeder test will stop after the current cycle")

    def cmd_CYCLE(self, gcmd):
        session = self.session
        if session is None:
            raise gcmd.error("No Box feeder test is running")
        try:
            self._run_cycle(gcmd, session)
        except FeedTestError as e:
            raise gcmd.error(str(e))


def load_config(config):
    return BoxFeedTest(config)
