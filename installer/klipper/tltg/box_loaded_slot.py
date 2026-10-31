# QIDI Box loaded-slot recovery for QIDI Max 4 Optimized.
#
# QIDI saves a slot as last_load_slot as soon as a Box load brings its
# filament to the Box hub sensor, before the filament reaches the toolhead,
# so a load that stops short of the toolhead still names that slot. Filament
# can also reach the hub without any load: inserting filament runs an
# automatic slot load up to the hub sensor, and a Box that disconnects
# partway leaves the filament there with last_load_slot still slot16. A Box
# load with the toolhead empty and the hub occupied runs QIDI's BOX_UNLOAD
# step first, and that step refuses with 无法识别到已进料耗材 ("can't
# identify the loaded filament") while last_load_slot is slot16 or missing,
# on every retry.
#
# Each slot's own motion that brings filament to the hub sensor is recorded
# as tltg_box_hub_slot, and a motion that leaves the hub clear clears it.
# When QIDI's unload is about to refuse, the Box state goes to klippy.log.
# If the recorded slot, or the only slot holding filament, still has
# filament at its inlet, it is saved as last_load_slot and QIDI's unload
# retracts it. Otherwise the console explains how to name the slot, and an
# idle nozzle is turned off; FLOW_RETRY heats it again.

import logging

HUB_SLOT_VARIABLE = "tltg_box_hub_slot"
EXTERNAL_SLOT = "slot16"
UNLOAD_STEP = "BOX_UNLOAD"
# Slot motion entry points, looked up by name on each `box_stepper slotN`
# when QIDI's Box code moves a slot.
MOTION_METHODS = ("do_home", "do_move", "do_home_double_steps",
                  "do_home_three_steps", "do_move_double_steps",
                  "do_move_triple_steps")


def _slot_number(slot):
    if isinstance(slot, str) and slot.startswith("slot") \
            and slot[4:].isdigit():
        return int(slot[4:])
    return None


def slot_label(slot):
    """Name a slot the way the QIDI Box card does: slot5 is 2B."""
    number = _slot_number(slot)
    if number is None:
        return str(slot)
    return "%d%s" % (number // 4 + 1, "ABCD"[number % 4])


class BoxLoadedSlot:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.slots = {}
        self.manager = None
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    # ----------------------------------------------------------------- setup
    def _handle_ready(self):
        slots = {}
        for name, obj in self.printer.lookup_objects("box_stepper"):
            slot = name.split()[-1]
            if _slot_number(slot) is None:
                continue
            for attr in MOTION_METHODS:
                method = getattr(obj, attr, None)
                if callable(method):
                    setattr(obj, attr, self._wrap_motion(slot, method))
            slots[slot] = obj
        controller = self.printer.lookup_object("multi_color_controller", None)
        manager = getattr(controller, "task_queue_manager", None)
        start_flow = getattr(manager, "start_flow", None)
        if not slots or not callable(start_flow) \
                or not isinstance(getattr(manager, "method_map", None), dict):
            logging.info("tltg_box_loaded_slot: inactive: QIDI Box slots or "
                         "flow controller not found")
            return
        self.slots = slots
        self.manager = manager
        manager.start_flow = self._wrap_start_flow(start_flow)
        logging.info("tltg_box_loaded_slot: active, %d slots", len(slots))

    def _wrap_start_flow(self, original):
        # QIDI's Box adapter registers its steps after Klipper is ready, and
        # each flow runs the step functions in method_map, so the unload step
        # is wrapped there before every flow starts.
        def start_flow(*args, **kwargs):
            try:
                self._install_unload_check()
            except Exception:
                logging.exception("tltg_box_loaded_slot: unload check install "
                                  "failed")
            return original(*args, **kwargs)
        return start_flow

    def _install_unload_check(self):
        method_map = self.manager.method_map
        unload = method_map.get(UNLOAD_STEP)
        if not callable(unload) or getattr(unload, "tltg_box_loaded_slot",
                                           False):
            return
        # Only the USB Box adapter refuses on last_load_slot.
        adapter = getattr(unload, "__self__", None)
        if type(adapter).__name__ != "BoxAdapterV1":
            return
        method_map[UNLOAD_STEP] = self._wrap_unload(unload)
        logging.info("tltg_box_loaded_slot: checking Box unloads")

    # ----------------------------------------------------------------- state
    def variables(self):
        save_vars = self.printer.lookup_object("save_variables", None)
        return getattr(save_vars, "allVariables", None) or {}

    def save(self, name, value):
        save_vars = self.printer.lookup_object("save_variables")
        gcmd = self.gcode.create_gcode_command(
            "SAVE_VARIABLE", "SAVE_VARIABLE",
            {"VARIABLE": name, "VALUE": repr(value)})
        save_vars.cmd_SAVE_VARIABLE(gcmd)

    def hub_occupied(self):
        # QIDI's Box adapter reads the hub filament sensor from box_extras;
        # 0 means filament is at the hub.
        extras = self.printer.lookup_object("box_extras", None)
        state = getattr(extras, "b_endstop_state", None)
        if state is None:
            return None
        return not state

    def inlets(self):
        """Each slot's inlet sensor: True with filament, None if unknown."""
        inlets = {}
        for slot, obj in self.slots.items():
            state = getattr(obj, "r_endstop_state", None)
            inlets[slot] = None if state is None else not state
        return inlets

    def toolhead_filament(self):
        sensor = self.printer.lookup_object(
            "filament_switch_sensor filament_switch_sensor", None)
        return getattr(getattr(sensor, "runout_helper", None),
                       "filament_present", None)

    def idle(self):
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is None:
            return False
        eventtime = self.printer.get_reactor().monotonic()
        state = print_stats.get_status(eventtime).get("state")
        return state not in ("printing", "paused")

    # ---------------------------------------------------------- hub record
    def _wrap_motion(self, slot, original):
        def motion(*args, **kwargs):
            before = None
            try:
                before = self.hub_occupied()
            except Exception:
                logging.exception("tltg_box_loaded_slot: hub check failed")
            try:
                return original(*args, **kwargs)
            finally:
                try:
                    self.record_motion(slot, before)
                except Exception:
                    logging.exception("tltg_box_loaded_slot: hub record "
                                      "failed")
        return motion

    def record_motion(self, slot, before):
        # Also called by tltg_box_slot_jog, whose moves bypass QIDI's methods.
        if self.printer.is_shutdown():
            return
        after = self.hub_occupied()
        if after is None:
            return
        if after and before is False:
            value = slot
        elif not after:
            value = ""
        else:
            return
        if self.variables().get(HUB_SLOT_VARIABLE, "") == value:
            return
        self.save(HUB_SLOT_VARIABLE, value)
        if value:
            logging.info("tltg_box_loaded_slot: %s (%s) fed filament to the "
                         "Box hub", slot, slot_label(slot))
        else:
            logging.info("tltg_box_loaded_slot: Box hub is clear")

    # ---------------------------------------------------------- unload check
    def _wrap_unload(self, original):
        def unload_filament(*args, **kwargs):
            refused = False
            try:
                refused = self._before_unload()
            except Exception:
                logging.exception("tltg_box_loaded_slot: unload check failed")
            result = original(*args, **kwargs)
            if refused and not result:
                try:
                    self._after_refusal()
                except Exception:
                    logging.exception("tltg_box_loaded_slot: unload refusal "
                                      "handling failed")
            return result
        unload_filament.tltg_box_loaded_slot = True
        return unload_filament

    def _before_unload(self):
        """Name the hub's slot if QIDI would refuse; True if it still will."""
        variables = self.variables()
        if not self.hub_occupied() \
                or variables.get("last_load_slot", EXTERNAL_SLOT) \
                != EXTERNAL_SLOT:
            return False
        recorded = variables.get(HUB_SLOT_VARIABLE, "")
        inlets = self.inlets()
        task = getattr(self.manager, "current_task", None)
        logging.info(
            "tltg_box_loaded_slot: Box unload has no loaded slot: hub "
            "filament, last_load_slot=%r slot_sync=%r %s=%r toolhead "
            "filament=%r inlet filament=%s flow=%r target_load_slot=%r "
            "target_unload_slot=%r",
            variables.get("last_load_slot"), variables.get("slot_sync"),
            HUB_SLOT_VARIABLE, recorded, self.toolhead_filament(),
            ", ".join("%s:%s" % (s, inlets[s])
                      for s in sorted(inlets, key=_slot_number)),
            getattr(task, "queue", None),
            getattr(self.manager, "target_load_slot", None),
            getattr(self.manager, "target_unload_slot", None))
        loaded = [s for s, present in inlets.items() if present]
        if inlets.get(recorded):
            slot, reason = recorded, "the last slot to feed filament to it"
        elif len(loaded) == 1 and None not in inlets.values():
            slot, reason = loaded[0], "the only slot with filament"
        else:
            return True
        self.save("last_load_slot", slot)
        message = ("Box: no slot was recorded as loaded, but filament is at "
                   "the Box hub. Unloading %s, %s." % (slot_label(slot),
                                                       reason))
        logging.info("tltg_box_loaded_slot: %s", message)
        self.gcode.respond_info(message)
        return False

    def _after_refusal(self):
        loaded = sorted((s for s, present in self.inlets().items()
                         if present), key=_slot_number)
        example = loaded[0] if loaded else min(self.slots, key=_slot_number)
        lines = [
            "Box unload stopped: filament is at the Box hub, but no slot is "
            "recorded as loaded.",
            "Find the slot whose filament runs into the hub, save it, then "
            "run FLOW_RETRY. For example, if it's %s:"
            % (slot_label(example),),
            "SAVE_VARIABLE VARIABLE=last_load_slot VALUE='\"%s\"'"
            % (example,),
            "slot0 is 1A, slot1 is 1B, and so on.",
        ]
        if loaded:
            lines.append("Slots with filament: %s."
                         % ", ".join(slot_label(s) for s in loaded))
        if self.idle():
            self.gcode.run_script_from_command("M104 S0")
            lines.append("The nozzle is off until then; FLOW_RETRY heats it "
                         "again.")
        message = "\n".join(lines)
        logging.info("tltg_box_loaded_slot: %s", message)
        self.gcode.respond_info(message)


def load_config(config):
    return BoxLoadedSlot(config)
