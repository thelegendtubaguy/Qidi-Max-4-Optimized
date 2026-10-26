# Motion-free QIDI nozzle load-cell diagnostics.
import math
import re
import statistics


_RAW_RE = re.compile(
    r"^(?://\s*)?传感器数据\([+-]\):\s*(\d+)\s*/\s*(-?\d+)\s*/\s*(-?\d+(?:\.\d+)?)\(mV\)$"
)
_PHASES = (
    ("baseline", "Will measure load cell without force, please do not touch the nozzle.", "DO NOT TOUCH", "Measuring..."),
    ("pressed", "Next you will press up on the nozzle, get ready to press.", "GET READY TO PRESS", "PRESS"),
    ("released", "Stop pressing, do not touch the nozzle.", "DO NOT TOUCH", "Measuring..."),
)
_RESULT_MESSAGES = {
    "RESPONSE_DETECTED": "Your load cell readings look correct.",
    "NO_RELIABLE_RESPONSE": "Your load cell did not respond appropriately, please check it further.",
    "INCONCLUSIVE": "There wasn't enough difference between you pressing and not pressing to determine.  Please check it further or measure again.",
}
_SAMPLE_PERIOD = 0.5
_PREPARE_SECONDS = 5.0
_SAMPLES = 12
_ADC_LIMIT = 1 << 23
_MIN_CHANGE = 64
_WARNING = "This checks sensor response only, NOT the MCU homing-trigger path or safe homing."


class TestAborted(Exception):
    pass


def assess_response(samples):
    baseline, pressed, released = (samples[phase[0]] for phase in _PHASES)
    if any(len(values) != _SAMPLES for values in (baseline, pressed, released)):
        return "INCONCLUSIVE", "Incomplete sensor readings.", {}
    if any(abs(value) >= _ADC_LIMIT * 0.99 for values in (baseline, pressed, released) for value in values):
        return "NO_RELIABLE_RESPONSE", "Sensor readings are near the ADC limit.", {}
    center = statistics.median(baseline)
    noise = 1.4826 * statistics.median(abs(value - center) for value in baseline)
    spread = max(baseline) - min(baseline)
    threshold = max(_MIN_CHANGE, 8 * noise, 3 * spread)
    delta = statistics.median(pressed) - center
    recovery = abs(statistics.median(released) - center)
    metrics = {"change_counts": abs(delta), "noise_counts": noise,
               "required_change_counts": threshold, "release_error_counts": recovery}
    if abs(delta) < threshold:
        if any(abs(value - center) >= threshold for value in pressed):
            return "NO_RELIABLE_RESPONSE", "Only a transient pressure response was detected.", metrics
        return "INCONCLUSIVE", "No pressure change clearly above baseline noise was detected. Do not press harder.", metrics
    direction = 1 if delta > 0 else -1
    sustained = sum((value - center) * direction >= threshold for value in pressed)
    if sustained < math.ceil(_SAMPLES * 0.8):
        return "NO_RELIABLE_RESPONSE", "The pressure response was not sustained.", metrics
    tolerance = abs(delta) * 0.25
    if (sum(abs(value - center) <= tolerance for value in released) < math.ceil(_SAMPLES * 0.8)
            or max(released) - min(released) > abs(delta) * 0.5):
        return "NO_RELIABLE_RESPONSE", "The signal did not settle near baseline after release.", metrics
    return "RESPONSE_DETECTED", "The load-cell signal changed under light pressure and recovered on release.", metrics


class ProbeSignalTest:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.active = False
        self.result = None
        self.metrics = {}
        self._readings = None
        self.gcode.register_output_handler(self._capture_reading)
        self.gcode.register_command("_TLTG_TEST_PROBE", self.cmd_TEST_PROBE,
                                    desc="Guided, motion-free nozzle load-cell response check")

    def get_status(self, eventtime):
        return {"active": self.active, "result": self.result, "metrics": dict(self.metrics)}

    def _capture_reading(self, message):
        if self._readings is None:
            return
        for line in message.splitlines():
            match = _RAW_RE.fullmatch(line.strip())
            if match:
                unsigned, signed = int(match[1]), int(match[2])
                millivolts = float(match[3])
                encodings = (signed % (1 << 24), signed % (1 << 32))
                if not -_ADC_LIMIT <= signed < _ADC_LIMIT or unsigned not in encodings or not math.isfinite(millivolts):
                    self._readings.append(None)
                else:
                    self._readings.append(signed)

    def _check_safe(self):
        now = self.reactor.monotonic()
        status = lambda name: self.printer.lookup_object(name).get_status(now)
        if (status("print_stats").get("state") not in ("standby", "complete", "cancelled", "error")
                or status("pause_resume").get("is_paused", True)
                or status("virtual_sdcard").get("is_active", True)
                or status("idle_timeout").get("state") not in ("Idle", "Ready")):
            raise TestAborted("An idle printer with no active or paused print is required.")
        if "WEIGHTING_DEBUG_QUERY" not in self.gcode.get_status(now)["commands"]:
            raise TestAborted("This firmware does not expose the raw load-cell readout.")
        for name in status("heaters")["available_heaters"]:
            if status(name).get("target") != 0:
                raise TestAborted("All heater targets must be off.")
        for name in ("extruder", "heater_bed"):
            temperature = status(name).get("temperature", math.nan)
            if not math.isfinite(temperature) or temperature >= 40:
                raise TestAborted("The nozzle and bed must be below 40 C.")

    def _wait(self, seconds):
        deadline = self.reactor.monotonic() + seconds
        while self.reactor.monotonic() < deadline:
            self.reactor.pause(min(deadline, self.reactor.monotonic() + 0.25))
            self._check_safe()

    def _read(self):
        self._check_safe()
        self._readings = []
        try:
            self.gcode.run_script_from_command("WEIGHTING_DEBUG_QUERY")
            readings = self._readings
        finally:
            self._readings = None
        self._check_safe()
        if len(readings) != 1 or readings[0] is None:
            raise TestAborted("Missing, malformed, or ambiguous raw sensor reading.")
        return readings[0]

    def cmd_TEST_PROBE(self, gcmd):
        if self.active:
            raise gcmd.error("A probe signal test is already running.")
        self.result = None
        self.metrics = {}
        try:
            self._check_safe()
            if gcmd.get_int("CONFIRM", 0) != 1:
                raise TestAborted("Ensure the cold nozzle is accessible and clear of the bed without homing. Then run TLTG_TEST_PROBE CONFIRM=1.")
        except TestAborted as exc:
            raise gcmd.error(str(exc))
        self.active = True
        try:
            gcmd.respond_info("Probe signal test: no motion, heating, or calibration changes. Do not home or jog during the test. Use only light upward pressure when prompted, never force the nozzle. " + _WARNING)
            samples = {}
            for name, prompt, reminder, measuring in _PHASES:
                gcmd.respond_info(prompt)
                for repeat in range(3):
                    if repeat:
                        self._wait(1.0)
                    gcmd.respond_info(reminder)
                self._wait(_PREPARE_SECONDS)
                samples[name] = []
                for sample in range(_SAMPLES):
                    if sample % (_SAMPLES // 3) == 0:
                        gcmd.respond_info(measuring)
                    self._wait(_SAMPLE_PERIOD)
                    samples[name].append(self._read())
            self.result, reason, self.metrics = assess_response(samples)
            gcmd.respond_info("TLTG_TEST_PROBE %s: %s" % (self.result, reason))
            if self.metrics:
                gcmd.respond_info("ADC counts: change=%.1f, baseline_noise=%.1f, required_change=%.1f, release_error=%.1f" % (
                    self.metrics["change_counts"], self.metrics["noise_counts"],
                    self.metrics["required_change_counts"], self.metrics["release_error_counts"]))
            gcmd.respond_info(_RESULT_MESSAGES[self.result])
            gcmd.respond_info(_WARNING)
            if self.result != "RESPONSE_DETECTED":
                gcmd.respond_info("Do not home or probe until the cause is understood. Check sensor/wiring or repeat with correct light-pressure timing. Do not apply more force.")
        except (TestAborted, self.printer.command_error) as exc:
            self.result = "INCONCLUSIVE"
            self.metrics = {}
            gcmd.respond_info("TLTG_TEST_PROBE INCONCLUSIVE: %s Stop touching the nozzle. Do not home or probe until the cause is understood. %s" % (exc, _WARNING))
        finally:
            self.active = False
            self._readings = None


def load_config(config):
    return ProbeSignalTest(config)
