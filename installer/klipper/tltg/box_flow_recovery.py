# QIDI Box flow recovery for QIDI Max 4 Optimized.
#
# Stopping a paused Box flow: QIDI's TaskQueueManager.stop() clears the flow,
# then sends M104 S0 with gcode.run_script(), which waits for Klipper's G-code
# lock. FLOW_STOP already holds that lock, so the command never returned and
# every later command queued behind it, with the nozzle left hot. While
# FLOW_STOP runs, the stop's scripts go through run_script_from_command
# instead; the multi_color_controller/flow_stop endpoint, which doesn't hold
# the lock, keeps run_script. Either way the nozzle is turned off after a stop
# only when no print is running or paused; a print keeps its heat for resume.
#
# A Box flow step that raises, such as a Box motor move ending with
# "Communication timeout during homing", escapes QIDI's flow runner and
# leaves the flow running, not paused, with the nozzle hot: FLOW_RETRY
# refuses it, and Fluidd shows a busy Box with no way out. Such a flow is
# paused on the failed step, as QIDI pauses a step that fails, before the
# error goes on to the command that ran it.
#
# Filament stranded between the Box hub and the toolhead: a load that reaches
# the hub but not the toolhead leaves the hub sensor occupied and the toolhead
# sensor empty. QIDI's unload then runs no steps and reports success, and its
# eject heats the nozzle and pulls back whichever slot last_load_slot names.
# For an idle printer, UNLOAD_FILAMENT_CONTROL and EJECT_FILAMENT_CONTROL of
# the hub's slot pull that slot back with tltg_box_slot_jog's motion until
# the hub sensor clears, stopping if the slot's inlet sensor empties first.
# An unload then parks the filament in the Box and saves the slot state
# QIDI's own slot unload saves; an eject hands over to QIDI's eject, which now
# runs as its eject step alone. The hub's slot comes from
# tltg_box_loaded_slot's record and last_load_slot, or is the only slot with
# filament at its inlet; anything else is refused with the reason. Whenever
# neither QIDI nor this module would move anything, the console says why.

import logging

import greenlet

EXTERNAL_SLOT = "slot16"
HEATER_OFF = "M104 S0"
HUB_SLOT_VARIABLE = "tltg_box_hub_slot"
# Slot motion for stranded filament, mm and mm/s.
RETRACT_SPEED = 60.
RETRACT_PIECE = 40.
MAX_HUB_RETRACT = 1500.
# QIDI's slot unload retracts 260 mm once the hub sensor clears; the hub can
# clear anywhere in the last piece, so park that much less.
PARK_DISTANCE = 260. - RETRACT_PIECE
SLOT_STATE_LOADED = 1


def _slot_number(slot):
    if isinstance(slot, str) and slot.startswith("slot") \
            and slot[4:].isdigit():
        return int(slot[4:])
    return None


def slot_label(slot):
    """Name a slot the way the QIDI Box card does: slot5 is 2B."""
    number = _slot_number(slot)
    if number is None or number >= 16:
        return "the external spool" if slot == EXTERNAL_SLOT else str(slot)
    return "%d%s" % (number // 4 + 1, "ABCD"[number % 4])


class _StopScripts:
    """QIDI's G-code object for the duration of a flow stop: the heater-off
    line is held back for the caller to decide, and the rest runs without
    taking the G-code lock when the caller already holds it."""

    def __init__(self, gcode, holds_lock):
        self._gcode = gcode
        self.holds_lock = holds_lock

    def _filter(self, script):
        if not isinstance(script, str):
            return script
        lines = [line for line in script.split("\n")
                 if line.strip().upper() != HEATER_OFF]
        return "\n".join(lines)

    def run_script(self, script):
        script = self._filter(script)
        if isinstance(script, str) and not script.strip():
            return None
        if self.holds_lock:
            return self._gcode.run_script_from_command(script)
        return self._gcode.run_script(script)

    def run_script_from_command(self, script):
        script = self._filter(script)
        if isinstance(script, str) and not script.strip():
            return None
        return self._gcode.run_script_from_command(script)

    def __getattr__(self, name):
        return getattr(self._gcode, name)


class BoxFlowRecovery:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.controller = None
        self.manager = None
        self.originals = {}
        # Greenlets running FLOW_STOP, which hold Klipper's G-code lock.
        self._locked = set()
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    # ----------------------------------------------------------------- setup
    def _handle_ready(self):
        controller = self.printer.lookup_object("multi_color_controller", None)
        manager = getattr(controller, "task_queue_manager", None)
        if not callable(getattr(manager, "stop", None)) \
                or not hasattr(manager, "gcode") \
                or not hasattr(manager, "current_task"):
            logging.info("tltg_box_flow_recovery: inactive: QIDI Box flow "
                         "controller not found")
            return
        self.controller = controller
        self.manager = manager
        manager.stop = self._wrap_stop(manager.stop)
        for name in ("start_flow", "retry"):
            if callable(getattr(manager, name, None)):
                setattr(manager, name,
                        self._wrap_flow_runner(getattr(manager, name)))
        for name, handler in (
                ("FLOW_STOP", self.cmd_FLOW_STOP),
                ("UNLOAD_FILAMENT_CONTROL", self.cmd_UNLOAD_FILAMENT_CONTROL),
                ("EJECT_FILAMENT_CONTROL", self.cmd_EJECT_FILAMENT_CONTROL)):
            original = self.gcode.register_command(name, None)
            if original is None:
                logging.info("tltg_box_flow_recovery: %s not found", name)
                continue
            self.originals[name] = original
            self.gcode.register_command(name, handler,
                                        desc=self.gcode.gcode_help.get(name))
        logging.info("tltg_box_flow_recovery: active")

    # ------------------------------------------------------------------ state
    def _print_state(self):
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is None:
            return None
        return print_stats.get_status(self.reactor.monotonic()).get("state")

    def _task(self):
        return getattr(self.manager, "current_task", None)

    def _flow_paused(self):
        task = self._task()
        return task is not None and bool(getattr(task, "is_paused", False))

    def _tracker(self):
        tracker = self.printer.lookup_object("tltg_box_loaded_slot", None)
        return tracker if getattr(tracker, "slots", None) else None

    # ------------------------------------------------------- failed steps
    def _wrap_flow_runner(self, original):
        def run(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except Exception as e:
                try:
                    self._pause_after_error(e)
                except Exception:
                    logging.exception("tltg_box_flow_recovery: pausing the "
                                      "flow after a step error failed")
                raise
        return run

    def _pause_after_error(self, error):
        task = self._task()
        step = getattr(task, "current_step", None)
        if task is None or not step or self.printer.is_shutdown() \
                or getattr(task, "is_paused", False) \
                or getattr(task, "is_cancelled", False):
            return
        task.is_paused = True
        logging.info("tltg_box_flow_recovery: step %s raised %s: %s; flow "
                     "paused", step, type(error).__name__, error)
        # QIDI's own words for a failed step, which Fluidd's Box card reads.
        self.gcode.respond_info("Step %s failed. Pausing flow." % (step,))

    # -------------------------------------------------------------- flow stop
    def _wrap_stop(self, original):
        def stop(*args, **kwargs):
            had_task = self._task() is not None
            state = self._print_state()
            holds_lock = greenlet.getcurrent() in self._locked
            real = self.manager.gcode
            scripts = _StopScripts(real, holds_lock)
            self.manager.gcode = scripts
            try:
                result = original(*args, **kwargs)
            finally:
                if self.manager.gcode is scripts:
                    self.manager.gcode = real
            if had_task:
                try:
                    self._after_stop(scripts, state)
                except Exception:
                    logging.exception("tltg_box_flow_recovery: heater "
                                      "handling after a flow stop failed")
            return result
        return stop

    def _after_stop(self, scripts, state):
        if state in ("printing", "paused"):
            message = ("Box flow stopped. The nozzle stays hot because a "
                       "print is %s." % (state,))
        else:
            if scripts.holds_lock:
                self.gcode.run_script_from_command(HEATER_OFF)
            else:
                self.gcode.run_script(HEATER_OFF)
            message = "Box flow stopped. Nozzle heater off."
        logging.info("tltg_box_flow_recovery: %s", message)
        self.gcode.respond_info(message)

    def _stop_from_command(self):
        """Stop QIDI's current flow from inside a G-code command."""
        current = greenlet.getcurrent()
        self._locked.add(current)
        try:
            self.manager.stop()
        finally:
            self._locked.discard(current)

    def cmd_FLOW_STOP(self, gcmd):
        if self._task() is None:
            gcmd.respond_info("No Box flow is running or paused, so there's "
                              "nothing to stop.")
        current = greenlet.getcurrent()
        self._locked.add(current)
        try:
            return self.originals["FLOW_STOP"](gcmd)
        finally:
            self._locked.discard(current)

    # --------------------------------------------------- unload and eject
    def cmd_UNLOAD_FILAMENT_CONTROL(self, gcmd):
        self._filament_command("UNLOAD", gcmd)

    def cmd_EJECT_FILAMENT_CONTROL(self, gcmd):
        self._filament_command("EJECT", gcmd)

    def _filament_command(self, action, gcmd):
        original = self.originals[action + "_FILAMENT_CONTROL"]
        try:
            plan = self._plan(action, gcmd)
        except Exception:
            logging.exception("tltg_box_flow_recovery: %s check failed",
                              action.lower())
            plan = None
        if plan is None:
            return original(gcmd)
        kind, slot, detail = plan
        if kind == "refuse":
            self._refuse(action, slot, detail)
            # QIDI's command would have replaced a paused flow; end it so
            # the nozzle cools and the slot can be jogged.
            if self._flow_paused() \
                    and self._print_state() not in ("printing", "paused"):
                self._stop_from_command()
            return None
        self._retract(action, slot, detail, gcmd, original)
        return None

    def _plan(self, action, gcmd):
        """None to run QIDI's command, ("refuse", slot, reason), or
        ("retract", slot, reason)."""
        adapter = getattr(self.controller, "box_adapter", None)
        tracker = self._tracker()
        if type(adapter).__name__ != "BoxAdapterV1" or tracker is None:
            return None
        number = gcmd.get_int("SLOT", None)
        slot = "slot%d" % number if number is not None else None
        if slot not in tracker.slots:
            return None
        task = self._task()
        if task is not None and not self._flow_paused():
            return None
        toolhead = tracker.toolhead_filament()
        hub = tracker.hub_occupied()
        if toolhead is not False or hub is None:
            return None
        state = self._print_state()
        if not hub:
            if action != "UNLOAD":
                return None
            # QIDI runs no steps here, then parks and reports success.
            return ("refuse", slot,
                    "%s's filament isn't fed past the Box hub, so there's "
                    "nothing to unload. It's already in the Box; Eject "
                    "removes it." % slot_label(slot))
        if state in ("printing", "paused"):
            if action != "UNLOAD":
                return None
            return ("refuse", slot,
                    "filament is stopped between the Box hub and the "
                    "toolhead, but a print is %s. RESUME tries the load "
                    "again, or cancel the print and then unload." % state)
        hub_slot, reason = self._hub_slot(tracker)
        if hub_slot is None:
            return ("refuse", slot, reason)
        if hub_slot != slot:
            return ("refuse", slot,
                    "the filament stopped between the Box hub and the "
                    "toolhead is %s's (%s). %s %s first."
                    % (slot_label(hub_slot), reason,
                       "Unload" if action == "UNLOAD" else "Unload or eject",
                       slot_label(hub_slot)))
        return ("retract", slot, reason)

    def _hub_slot(self, tracker):
        """The slot whose filament is at the hub, and why; or None and why
        it can't be told."""
        variables = tracker.variables()
        inlets = tracker.inlets()
        with_filament = sorted((s for s, present in inlets.items()
                                if present), key=_slot_number)
        recorded = variables.get(HUB_SLOT_VARIABLE, "")
        last = variables.get("last_load_slot", EXTERNAL_SLOT)
        named = []
        for slot, why in ((recorded, "the last slot to feed filament to "
                                     "the hub"),
                          (last, "the slot QIDI last loaded")):
            if inlets.get(slot) and slot not in [s for s, _ in named]:
                named.append((slot, why))
        if len(named) == 1:
            return named[0]
        listed = ", ".join(slot_label(s) for s in with_filament) or "none"
        if len(named) > 1:
            return (None, "the filament at the Box hub could be %s's or "
                          "%s's. Pull the wrong one back with "
                          "TLTG_BOX_SLOT_JOG, or remove the filament by hand"
                    % (slot_label(named[0][0]), slot_label(named[1][0])))
        if len(with_filament) == 1 and None not in inlets.values():
            return with_filament[0], "the only slot with filament"
        return (None, "no slot is recorded as feeding the filament at the "
                      "Box hub. Slots with filament: %s. Follow the "
                      "filament back to its slot and pull it back with "
                      "TLTG_BOX_SLOT_JOG SLOT=<n> DISTANCE=-100" % listed)

    def _refuse(self, action, slot, reason):
        verb = "unload" if action == "UNLOAD" else "eject"
        message = "Box %s of %s not run: %s" % (verb, slot_label(slot),
                                                reason)
        if not message.endswith("."):
            message += "."
        logging.info("tltg_box_flow_recovery: %s", message)
        self.gcode.respond_info(message)

    def _retract(self, action, slot, reason, gcmd, original):
        tracker = self._tracker()
        jog = self.printer.lookup_object("tltg_box_slot_jog", None)
        number = _slot_number(slot)
        label = slot_label(slot)
        if jog is None:
            raise gcmd.error("Box %s of %s not run: tltg_box_slot_jog is "
                             "missing." % (action.lower(), label))
        if self._flow_paused():
            self._stop_from_command()
        blocker = jog.blocker()
        if blocker is not None:
            raise gcmd.error("Box %s of %s not run: %s."
                             % (action.lower(), label, blocker))
        message = ("Box: %s's filament is stopped between the Box hub and "
                   "the toolhead (%s). Pulling it back out of the hub."
                   % (label, reason))
        logging.info("tltg_box_flow_recovery: %s", message)
        gcmd.respond_info(message)

        def hub_clear_or_inlet_empty():
            return tracker.hub_occupied() is False \
                or tracker.inlets().get(slot) is False

        moved, _ = jog.move(number, -MAX_HUB_RETRACT, RETRACT_SPEED,
                            until=hub_clear_or_inlet_empty,
                            piece=RETRACT_PIECE)
        hub = tracker.hub_occupied()
        inlet = tracker.inlets().get(slot)
        logging.info("tltg_box_flow_recovery: %s retracted %.0f mm, hub "
                     "filament=%r inlet filament=%r", slot, moved, hub, inlet)
        if hub is not False:
            if inlet is False:
                raise gcmd.error(
                    "%s's filament left its inlet sensor after %.0f mm while "
                    "the Box hub still detects filament, so the filament at "
                    "the hub isn't %s's, or it broke. Remove it by hand. "
                    "%s's filament is out of its feeder; push it back into "
                    "the inlet to load it again."
                    % (label, abs(moved), label, label))
            raise gcmd.error(
                "Pulled %s back %.0f mm, but the Box hub still detects "
                "filament. Check the tube between the hub and the toolhead "
                "and remove the filament by hand." % (label, abs(moved)))
        variables = tracker.variables()
        if variables.get("last_load_slot") == slot:
            tracker.save("last_load_slot", EXTERNAL_SLOT)
        if action == "EJECT":
            gcmd.respond_info("Box: %s's filament is clear of the hub. "
                              "Ejecting it." % (label,))
            return original(gcmd)
        parked, _ = jog.move(number, -PARK_DISTANCE, RETRACT_SPEED,
                             until=lambda: tracker.inlets().get(slot)
                             is False,
                             piece=RETRACT_PIECE)
        if tracker.inlets().get(slot) is False:
            raise gcmd.error(
                "%s's filament left its inlet sensor %.0f mm after the Box "
                "hub cleared, so it's out of the feeder. Push it back into "
                "the inlet to load it again." % (label, abs(parked)))
        tracker.save(slot, SLOT_STATE_LOADED)
        message = ("Box: unloaded %s. Its filament is parked in the Box."
                   % (label,))
        logging.info("tltg_box_flow_recovery: %s", message)
        gcmd.respond_info(message)
        return None


def load_config(config):
    return BoxFlowRecovery(config)
