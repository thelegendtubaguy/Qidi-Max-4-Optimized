# Spoolman spools for QIDI Box slots for QIDI Max 4 Optimized.
#
# Moonraker's Spoolman integration charges extrusion to one active spool.
# This module keeps a spool for each Box slot, and for the external spool,
# in the saved variable tltg_spoolman_spools, and makes the loaded slot's
# spool the active one whenever the slot QIDI records as loaded changes.
# A loaded slot without a spool makes no spool active, so its filament isn't
# charged to another slot's spool. With no spools saved, the active spool is
# left alone, as without this module.
#
# TLTG_SPOOLMAN_SLOT SLOT=<n> SPOOL=<id> sets a slot's spool; SPOOL=0 clears
# it. Without SLOT it sets the loaded slot's spool, which is how the
# installer's Moonraker patch passes on a spool picked in Fluidd. With no
# parameters it lists the spools.

import logging

SPOOLS_VARIABLE = "tltg_spoolman_spools"
EXTERNAL_SLOT = 16
SET_ACTIVE_METHOD = "spoolman_set_active_spool"
CHECK_INTERVAL = 0.5
UNSET = object()


def slot_label(slot):
    """Name a slot the way the QIDI Box card does: slot 5 is 2B."""
    if slot == EXTERNAL_SLOT:
        return "External spool"
    return "%d%s" % (slot // 4 + 1, "ABCD"[slot % 4])


def _slot_number(value):
    if isinstance(value, str) and value.startswith("slot") \
            and value[4:].isdigit():
        number = int(value[4:])
        if 0 <= number <= EXTERNAL_SLOT:
            return number
    return None


class Spoolman:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.webhooks = self.printer.lookup_object("webhooks")
        self.synced = UNSET
        self.status_failed = False
        self.timer = None
        self.gcode.register_command(
            "TLTG_SPOOLMAN_SLOT", self.cmd_TLTG_SPOOLMAN_SLOT,
            desc="Set or list the Spoolman spool for each QIDI Box slot")
        self.printer.register_event_handler("klippy:ready", self._ready)

    def _ready(self):
        self.timer = self.reactor.register_timer(self._check,
                                                 self.reactor.NOW)

    # ----------------------------------------------------------------- state
    def _variables(self):
        save_vars = self.printer.lookup_object("save_variables", None)
        return getattr(save_vars, "allVariables", None) or {}

    def spools(self):
        """Saved spools by slot number, ignoring anything malformed."""
        saved = self._variables().get(SPOOLS_VARIABLE)
        spools = {}
        if isinstance(saved, dict):
            for key, spool in saved.items():
                slot = _slot_number(key)
                if slot is not None and isinstance(spool, int) \
                        and not isinstance(spool, bool) and spool > 0:
                    spools[slot] = spool
        return spools

    def _save(self, spools):
        save_vars = self.printer.lookup_object("save_variables")
        value = dict(("slot%d" % slot, spool)
                     for slot, spool in sorted(spools.items()))
        gcmd = self.gcode.create_gcode_command(
            "SAVE_VARIABLE", "SAVE_VARIABLE",
            {"VARIABLE": SPOOLS_VARIABLE, "VALUE": repr(value)})
        save_vars.cmd_SAVE_VARIABLE(gcmd)

    def loaded_slot(self):
        """The slot QIDI records as feeding the toolhead, or None."""
        if self._variables().get("enable_box") != 1:
            return EXTERNAL_SLOT
        box = self.printer.lookup_object("box_extras", None)
        if box is None:
            return EXTERNAL_SLOT
        try:
            status = box.get_status(self.reactor.monotonic())
        except Exception:
            if not self.status_failed:
                logging.exception("tltg_spoolman: box_extras get_status "
                                  "failed")
            self.status_failed = True
            return None
        self.status_failed = False
        if not hasattr(status, "get"):
            return None
        return _slot_number(status.get("loaded_slot"))

    # ------------------------------------------------------------ following
    def _check(self, eventtime):
        if self.printer.is_shutdown():
            return self.reactor.NEVER
        try:
            self.sync()
        except Exception:
            logging.exception("tltg_spoolman: spool sync failed")
        return eventtime + CHECK_INTERVAL

    def sync(self):
        spools = self.spools()
        if not spools:
            self.synced = UNSET
            return
        slot = self.loaded_slot()
        if slot is None:
            return
        spool = spools.get(slot)
        if self.synced == (slot, spool):
            return
        try:
            self.webhooks.call_remote_method(SET_ACTIVE_METHOD,
                                             spool_id=spool)
        except self.printer.command_error:
            # Moonraker isn't connected or has no [spoolman] section; try
            # again on the next check.
            return
        self.synced = (slot, spool)
        logging.info("tltg_spoolman: %s loaded, active spool %s",
                     slot_label(slot), spool)

    def get_status(self, eventtime):
        slot = self.loaded_slot()
        return {
            "loaded_slot": None if slot is None else "slot%d" % slot,
            "spools": dict(("slot%d" % slot, spool)
                           for slot, spool in self.spools().items()),
        }

    # -------------------------------------------------------------- command
    def cmd_TLTG_SPOOLMAN_SLOT(self, gcmd):
        spools = self.spools()
        if gcmd.get_int("RESET", 0, minval=0, maxval=1):
            self._save({})
            gcmd.respond_info("Spoolman: cleared every slot's spool. The "
                              "active spool no longer follows the loaded "
                              "slot.")
            return
        spool = gcmd.get_int("SPOOL", None, minval=0)
        if spool is None:
            gcmd.respond_info(self._listing(spools))
            return
        slot = gcmd.get_int("SLOT", None, minval=0, maxval=EXTERNAL_SLOT)
        if slot is None:
            slot = self.loaded_slot()
            if slot is None:
                raise gcmd.error("Spoolman: no slot is recorded as loaded; "
                                 "name one with SLOT=")
        if spool:
            spools[slot] = spool
            message = "Spoolman: %s is spool %d." % (slot_label(slot), spool)
        else:
            spools.pop(slot, None)
            message = "Spoolman: %s has no spool." % (slot_label(slot),)
        self._save(spools)
        self.sync()
        gcmd.respond_info(message)

    def _listing(self, spools):
        if not spools:
            return ("Spoolman: no slot has a spool, so the active spool "
                    "doesn't follow the loaded slot. Set one with "
                    "TLTG_SPOOLMAN_SLOT SLOT=<n> SPOOL=<id>.")
        lines = ["Spoolman spools:"]
        for slot in sorted(spools):
            lines.append("%s: spool %d" % (slot_label(slot), spools[slot]))
        loaded = self.loaded_slot()
        if loaded is not None:
            spool = spools.get(loaded)
            lines.append("Loaded: %s, %s" % (
                slot_label(loaded),
                "spool %d" % spool if spool else "no spool"))
        methods = getattr(self.webhooks, "_remote_methods", None)
        if isinstance(methods, dict) and SET_ACTIVE_METHOD not in methods:
            lines.append("Moonraker's Spoolman integration isn't connected; "
                         "add [spoolman] to moonraker.conf.")
        return "\n".join(lines)


def load_config(config):
    return Spoolman(config)
