# Motion-free nozzle load-cell response check.
#
# QIDI's closed cs1237 module reports raw load-cell readings only as console
# text from WEIGHTING_DEBUG_QUERY. Each reading is captured from that output
# and kept out of the console; klippy.log still records it.
import logging
import re
import statistics

# "传感器数据" means "sensor data": "<unsigned> / <signed> / <millivolts>(mV)".
_READING_RE = re.compile(r"^// 传感器数据\([+-]\):\s*\d+\s*/\s*(-?\d+)\s*/\s*\S+\(mV\)$")
_ADC_LIMIT = 1 << 23
_SAMPLES = 12
_SAMPLE_PERIOD = 0.5
_PREPARE_SECONDS = 5.0
# The MCU has returned an empty reading; retry briefly before stopping the test.
_QUERY_ATTEMPTS = 3
_RETRY_DELAY = 0.1
# The sensor occasionally returns an isolated corrupt reading; tolerate this many per phase.
_MAX_OUTLIERS = 2
_MIN_CHANGE = 64
_RELEASE_FRACTION = 0.25

# (operator instruction, repeated reminder, measurement cue)
_PHASES = (
    ("Measuring the unloaded sensor. Do not touch the nozzle.", "DO NOT TOUCH", "Measuring..."),
    ("Next, press lightly upward on the nozzle and hold until told to stop.", "GET READY TO PRESS", "PRESS"),
    ("Stop pressing and let go of the nozzle.", "DO NOT TOUCH", "Measuring..."),
)
_SUMMARIES = {
    "RESPONSE_DETECTED": "Your load cell readings look correct.",
    "NO_RELIABLE_RESPONSE": "Your load cell did not respond as expected.",
    "INCONCLUSIVE": "There was not enough difference between pressing and not pressing to tell.",
}
_HOMING_CAVEAT = "This checks the sensor signal only; it does not verify the homing trigger."
_FAILURE_ADVICE = (
    "Do not home or probe until the cause is understood. Check the sensor and wiring, "
    "or repeat the test with steady light pressure. Do not press harder."
)


class TestAborted(Exception):
    pass


def assess_response(baseline, pressed, released):
    """Classify a light-press trace. Returns (result, reason, metrics)."""
    if any(abs(statistics.median(values)) >= _ADC_LIMIT * 0.99 for values in (baseline, pressed, released)):
        return "NO_RELIABLE_RESPONSE", "The readings are at the sensor's limit.", {}
    center = statistics.median(baseline)
    # Median absolute deviation, scaled to a standard deviation, ignores corrupt readings.
    noise = 1.4826 * statistics.median(abs(value - center) for value in baseline)
    threshold = max(_MIN_CHANGE, 8 * noise)
    delta = statistics.median(pressed) - center
    direction = 1 if delta >= 0 else -1
    tolerance = max(threshold, abs(delta) * _RELEASE_FRACTION)
    metrics = {
        "change": abs(delta),
        "required_change": threshold,
        "noise": noise,
        "release_error": abs(statistics.median(released) - center),
    }
    required = _SAMPLES - _MAX_OUTLIERS
    displaced = sum((value - center) * direction >= threshold for value in pressed)
    returned = sum(abs(value - center) < tolerance for value in released)
    if displaced <= _MAX_OUTLIERS:
        return "INCONCLUSIVE", "No pressure change clearly above baseline noise was detected.", metrics
    if displaced < required:
        return "NO_RELIABLE_RESPONSE", "The signal did not stay changed while pressing.", metrics
    if returned < required:
        return "NO_RELIABLE_RESPONSE", "The signal did not return to baseline after release.", metrics
    return "RESPONSE_DETECTED", "The signal changed under light pressure and returned to baseline on release.", metrics


class LoadCellResponseCheck:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.active = False
        self.result = None
        self.metrics = {}
        self.gcode.register_command("_TLTG_TEST_PROBE", self.cmd_TEST_PROBE,
                                    desc="Guided, motion-free nozzle load-cell response check")

    def get_status(self, eventtime):
        return {"active": self.active, "result": self.result, "metrics": dict(self.metrics)}

    def _check_safe(self):
        eventtime = self.reactor.monotonic()

        def status(name):
            return self.printer.lookup_object(name).get_status(eventtime)

        if (status("print_stats").get("state") not in ("standby", "complete", "cancelled", "error")
                or status("pause_resume").get("is_paused", True)
                or status("virtual_sdcard").get("is_active", True)
                or status("idle_timeout").get("state") not in ("Idle", "Ready")):
            raise TestAborted("An idle printer with no active or paused print is required.")
        if "WEIGHTING_DEBUG_QUERY" not in self.gcode.get_status(eventtime)["commands"]:
            raise TestAborted("This firmware does not provide the raw load-cell readout.")
        if any(status(name).get("target") != 0 for name in status("heaters")["available_heaters"]):
            raise TestAborted("All heater targets must be off.")
        for name in ("extruder", "heater_bed"):
            # Written so that a missing or NaN temperature also aborts.
            if not status(name).get("temperature", float("nan")) < 40:
                raise TestAborted("The nozzle and bed must be below 40 C.")

    def _wait(self, seconds):
        deadline = self.reactor.monotonic() + seconds
        while self.reactor.monotonic() < deadline:
            self.reactor.pause(min(deadline, self.reactor.monotonic() + 0.25))
            self._check_safe()

    def _query(self):
        """One WEIGHTING_DEBUG_QUERY; returns the signed reading, or None if it failed."""
        handler = self.gcode.gcode_handlers.get("WEIGHTING_DEBUG_QUERY")
        if handler is None:
            raise TestAborted("This firmware does not provide the raw load-cell readout.")
        console = self.gcode.output_callbacks
        readings = []

        def capture(message):
            match = _READING_RE.match(message)
            if match is None:
                for callback in console:
                    callback(message)
            else:
                readings.append(int(match.group(1)))

        self.gcode.output_callbacks = [capture]
        try:
            # Called directly rather than through run_script_from_command: QIDI's
            # handler raises IndexError when the MCU returns no data, and Klipper
            # shuts down on any non-command error raised inside a G-code script.
            handler(self.gcode.create_gcode_command(
                "WEIGHTING_DEBUG_QUERY", "WEIGHTING_DEBUG_QUERY", {}))
        except Exception:
            logging.exception("TLTG_TEST_PROBE: WEIGHTING_DEBUG_QUERY failed")
            return None
        finally:
            self.gcode.output_callbacks = console
        if len(readings) != 1 or not -_ADC_LIMIT <= readings[0] < _ADC_LIMIT:
            logging.warning("TLTG_TEST_PROBE: unexpected WEIGHTING_DEBUG_QUERY readings %r", readings)
            return None
        return readings[0]

    def _read(self):
        for attempt in range(_QUERY_ATTEMPTS):
            if attempt:
                self._wait(_RETRY_DELAY)
            self._check_safe()
            reading = self._query()
            self._check_safe()
            if reading is not None:
                return reading
        raise TestAborted("The load cell returned no usable reading.")

    def _measure(self, gcmd, instruction, reminder, cue):
        gcmd.respond_info(instruction)
        for repeat in range(3):
            if repeat:
                self._wait(1.0)
            gcmd.respond_info(reminder)
        self._wait(_PREPARE_SECONDS)
        readings = []
        for sample in range(_SAMPLES):
            if sample % (_SAMPLES // 3) == 0:
                gcmd.respond_info(cue)
            self._wait(_SAMPLE_PERIOD)
            readings.append(self._read())
        return readings

    def cmd_TEST_PROBE(self, gcmd):
        if self.active:
            raise gcmd.error("A load-cell response check is already running.")
        self.result = None
        self.metrics = {}
        try:
            self._check_safe()
        except TestAborted as exc:
            raise gcmd.error(str(exc))
        if gcmd.get_int("CONFIRM", 0) != 1:
            raise gcmd.error("Make sure the cold nozzle is accessible and clear of the bed, without homing. "
                             "Then run TLTG_TEST_PROBE CONFIRM=1.")
        self.active = True
        try:
            gcmd.respond_info("Load-cell response check: the printer will not move, heat, or change calibration. "
                              "Do not home or jog during the test. Press lightly only when prompted; "
                              "never force the nozzle.")
            traces = [self._measure(gcmd, *phase) for phase in _PHASES]
            self.result, reason, self.metrics = assess_response(*traces)
        except (TestAborted, self.printer.command_error) as exc:
            self.result = "INCONCLUSIVE"
            message = "Test stopped: %s Stop touching the nozzle." % (exc,)
        else:
            message = "%s %s" % (_SUMMARIES[self.result], reason)
        finally:
            self.active = False
        gcmd.respond_info("TLTG_TEST_PROBE %s: %s" % (self.result, message))
        if self.metrics:
            gcmd.respond_info("Signal change %.0f counts (needed %.0f); baseline noise %.0f; release error %.0f." % (
                self.metrics["change"], self.metrics["required_change"],
                self.metrics["noise"], self.metrics["release_error"]))
        if self.result == "RESPONSE_DETECTED":
            gcmd.respond_info(_HOMING_CAVEAT)
        else:
            gcmd.respond_info("%s %s" % (_FAILURE_ADVICE, _HOMING_CAVEAT))


def load_config(config):
    return LoadCellResponseCheck(config)
