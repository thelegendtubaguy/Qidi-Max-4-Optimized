# Chamber exhaust guard for QIDI Max 4 Optimized.
#
# The optimized M106 leaves the chamber heater on when the exhaust fan (P3)
# turns on. The exhaust can then pull the chamber far enough below its target
# that Klipper's verify_heater check stops the printer with "Heater chamber
# not heating at expected rate". This module reads that check's own state each
# second and turns the exhaust fan off before it fails:
#
#   holding   the chamber is inside the check's hysteresis band; turn the fan
#             off once the chamber falls back to within 1 °C of the band's
#             lower edge, or the check starts counting a shortfall. Below that
#             edge the check counts the shortfall every second and only clears
#             it once the chamber is back inside, so a chamber that falls
#             through it while the exhaust runs fails unless it recovers fast.
#   heating   the chamber is still approaching its target; turn the fan off
#             once half of check_gain_time has passed without the required gain
#
# The fan then stays off for the rest of the print: M106 P3 reads `stopped`
# and leaves the fan off while the chamber heater has a target. `stopped`
# clears when no print is running or paused. The heater and the check itself
# are unchanged.

import logging

CHECK_TIME = 1.0
MARGIN = 1.0
VERIFY_HEATER = "verify_heater chamber"
HEATER = "chamber"
FAN = "chamber_circulation_fan"
REQUIRED = ("error", "hysteresis", "approaching_target", "goal_systime",
            "check_gain_time")


class ChamberExhaustGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.check = self.heater = self.fan = self.print_stats = None
        # stopping: a stop is queued and the fan hasn't reported 0 yet; QIDI's
        # fan applies SET_FAN_SPEED only once queued moves reach it.
        self.stopped = False
        self.stopping = False
        # Highest chamber temperature since it last stopped approaching target.
        self.peak = self.peak_target = None
        self.printer.register_event_handler("klippy:ready", self._ready)

    def _ready(self):
        check = self.printer.lookup_object(VERIFY_HEATER, None)
        fan = self.printer.lookup_object("fan_generic " + FAN, None)
        if check is None or fan is None:
            logging.info("tltg_chamber_exhaust_guard: no chamber heater check"
                         " or exhaust fan; guard off")
            return
        if not all(hasattr(check, attr) for attr in REQUIRED):
            logging.warning("tltg_chamber_exhaust_guard: %s has an unexpected"
                            " layout; guard off", VERIFY_HEATER)
            return
        self.check = check
        self.fan = fan
        self.heater = self.printer.lookup_object("heaters").lookup_heater(HEATER)
        self.print_stats = self.printer.lookup_object("print_stats", None)
        self.reactor.register_timer(self._sample, self.reactor.NOW)

    def _printing(self, eventtime):
        if self.print_stats is None:
            return False
        state = self.print_stats.get_status(eventtime).get("state")
        return state in ("printing", "paused")

    def at_risk(self, eventtime, temp, target):
        """True once the chamber check is close to counting toward a failure."""
        check = self.check
        if check.approaching_target or target != self.peak_target:
            self.peak, self.peak_target = temp, target
        self.peak = max(self.peak, temp)
        if check.approaching_target:
            return eventtime >= check.goal_systime - check.check_gain_time / 2.
        edge = target - check.hysteresis + MARGIN
        return check.error > 0. or (self.peak >= edge and temp < edge)

    def _sample(self, eventtime):
        if self.printer.is_shutdown():
            return self.reactor.NEVER
        if self.stopped and not self._printing(eventtime):
            self.stopped = False
        temp, target = self.heater.get_temp(eventtime)
        speed = self.fan.get_status(eventtime).get("speed", 0.)
        risk = target > 0. and self.at_risk(eventtime, temp, target)
        if speed <= 0.:
            self.stopping = False
        elif risk and not self.stopping:
            self.stopping = True
            self.reactor.register_callback(
                lambda e: self._stop_fan(temp, target))
        return eventtime + CHECK_TIME

    def _stop_fan(self, temp, target):
        try:
            self.gcode.run_script("SET_FAN_SPEED FAN=%s SPEED=0" % FAN)
        except Exception:
            logging.exception("tltg_chamber_exhaust_guard: could not stop the"
                              " exhaust fan")
            self.stopping = False
            return
        self.stopped = self._printing(self.reactor.monotonic())
        message = ("WARNING: Exhaust fan turned off%s. The chamber is at"
                   " %.0f°C against its %.0f°C target and isn't keeping up;"
                   " if it stays more than %.0f°C below for long, Klipper"
                   " stops the print with 'Heater chamber not heating at"
                   " expected rate'." % (
                       " for the rest of the print" if self.stopped else "",
                       temp, target, self.check.hysteresis))
        logging.info("tltg_chamber_exhaust_guard: %s", message)
        self.gcode.respond_info(message)

    def get_status(self, eventtime=None):
        return {"stopped": self.stopped}


def load_config(config):
    return ChamberExhaustGuard(config)
