from __future__ import annotations

import importlib.util
from types import SimpleNamespace
import unittest

from installer.tests.helpers import REPO_ROOT


spec = importlib.util.spec_from_file_location(
    "tltg_probe_test", REPO_ROOT / "installer/klipper/tltg/probe_test.py"
)
probe_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_test)

# Isolated corrupt readings captured from a Max 4 whose sensor otherwise read about -939000.
HARDWARE_GLITCHES = (-917505, -3, -2, 6955391)


class CommandError(Exception):
    pass


def vendor_line(value: int) -> str:
    """Format a reading the way QIDI's cs1237 module reports it."""
    return "// 传感器数据(%s): %d / %d / %.6f(mV)" % (
        "-" if value < 0 else "+", value % (1 << 24), value, value * 2.5 / 128 / ((1 << 23) - 1) * 1000,
    )


def trace(*, base=-939000, change=250000, release=0, glitches=()):
    """Twelve baseline, twelve pressed, and twelve released readings with light noise."""
    noise = [n % 3 * 50 - 50 for n in range(12)]
    readings = [base + n for n in noise] + [base + change + n for n in noise] + [base + release + n for n in noise]
    for index, value in glitches:
        readings[index] = value
    return readings


class Printer:
    """Just enough of Klipper for the helper: console output, reactor time, and status objects."""

    def __init__(self, readings, confirm=1):
        self.readings = iter(readings)
        self.confirm = confirm
        self.time = 0.0
        self.console = []
        self.queries = []
        self.commands = {}
        self.on_pause = lambda: None
        self.on_query = lambda: None
        self.command_error = CommandError
        self.objects = {
            "print_stats": {"state": "standby"},
            "pause_resume": {"is_paused": False},
            "virtual_sdcard": {"is_active": False},
            "idle_timeout": {"state": "Ready"},
            "heaters": {"available_heaters": ["extruder", "heater_bed", "heater_generic chamber"]},
            "extruder": {"temperature": 25.0, "target": 0},
            "heater_bed": {"temperature": 25.0, "target": 0},
            "heater_generic chamber": {"target": 0},
        }
        self.gcode = SimpleNamespace(
            output_callbacks=[lambda message: self.console.append((self.time, message))],
            register_command=lambda name, handler, **kwargs: self.commands.update({name: handler}),
            get_status=lambda eventtime: {"commands": {"WEIGHTING_DEBUG_QUERY": {}, **self.commands}},
            gcode_handlers={"WEIGHTING_DEBUG_QUERY": self.query},
            create_gcode_command=lambda command, commandline, params: SimpleNamespace(),
            run_script_from_command=self.run_script,
        )
        self.reactor = SimpleNamespace(monotonic=lambda: self.time, pause=self.pause)
        self.check = probe_test.load_config(SimpleNamespace(get_printer=lambda: self))
        self.gcmd = SimpleNamespace(
            get_int=lambda name, default: default if self.confirm is None else self.confirm,
            error=CommandError,
            respond_info=lambda message: self.respond_raw("// " + message),
        )

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name):
        if name == "gcode":
            return self.gcode
        return SimpleNamespace(get_status=lambda eventtime: self.objects[name])

    def respond_raw(self, message):
        for callback in self.gcode.output_callbacks:
            callback(message)

    def pause(self, until):
        self.time = until
        self.on_pause()

    def run_script(self, script):
        raise AssertionError("Unexpected G-code script: " + script)

    def query(self, gcmd):
        self.queries.append(self.time)
        self.on_query()
        value = next(self.readings)
        if isinstance(value, Exception):
            raise value
        for line in value if isinstance(value, list) else [value]:
            self.respond_raw(vendor_line(line) if isinstance(line, int) else line)

    def run(self):
        self.commands["_TLTG_TEST_PROBE"](self.gcmd)
        return self.check.result

    def messages(self):
        return [message for _, message in self.console]


class LoadCellResponseCheckTests(unittest.TestCase):
    def test_guided_check_detects_response_in_either_direction_without_raw_console_output(self):
        for change in (250000, -250000):
            with self.subTest(change=change):
                printer = Printer(trace(change=change))
                self.assertEqual(printer.run(), "RESPONSE_DETECTED")
                self.assertFalse(printer.check.active)
                self.assertFalse(any("传感器" in message for message in printer.messages()))
                self.assertTrue(any("does not verify the homing trigger" in message for message in printer.messages()))

                reminders = [time for time, message in printer.console
                             if message in ("// DO NOT TOUCH", "// GET READY TO PRESS")]
                cues = [(time, message) for time, message in printer.console
                        if message in ("// Measuring...", "// PRESS")]
                self.assertEqual([message for _, message in cues],
                                 ["// Measuring..."] * 3 + ["// PRESS"] * 3 + ["// Measuring..."] * 3)
                self.assertEqual(len(printer.queries), 36)
                for phase in range(3):
                    phase_reminders = reminders[3 * phase:3 * phase + 3]
                    phase_queries = printer.queries[12 * phase:12 * phase + 12]
                    self.assertEqual([b - a for a, b in zip(phase_reminders, phase_reminders[1:])], [1.0, 1.0])
                    self.assertGreaterEqual(phase_queries[0] - phase_reminders[-1], 5)
                    self.assertEqual(phase_queries[-1] - phase_queries[0], 5.5)
                    self.assertEqual([time for time, _ in cues[3 * phase:3 * phase + 3]],
                                     [time - 0.5 for time in phase_queries[0::4]])

    def test_isolated_corrupt_readings_do_not_decide_the_result(self):
        glitches = tuple(zip((9, 14, 26, 33), HARDWARE_GLITCHES))
        for change, expected in ((250000, "RESPONSE_DETECTED"), (0, "INCONCLUSIVE")):
            with self.subTest(change=change):
                self.assertEqual(Printer(trace(change=change, glitches=glitches)).run(), expected)

    def test_unreliable_signals_never_pass(self):
        cases = {
            "frozen": ([1000] * 36, "INCONCLUSIVE"),
            "noise": ([1000 + (100 if n % 2 else -100) for n in range(12)] + [1050] * 12 + [1000] * 12,
                      "INCONCLUSIVE"),
            "intermittent": (trace(glitches=[(index, -939000) for index in range(21, 24)]),
                             "NO_RELIABLE_RESPONSE"),
            "unreleased": (trace(release=250000), "NO_RELIABLE_RESPONSE"),
            "minimum_change_without_release": ([0] * 12 + [64] * 24, "NO_RELIABLE_RESPONSE"),
            "unstable_release": (trace(glitches=[(index, -839000) for index in range(33, 36)]),
                                 "NO_RELIABLE_RESPONSE"),
            "saturated": (trace(base=(1 << 23) - 1000, change=-10000), "NO_RELIABLE_RESPONSE"),
        }
        for name, (readings, expected) in cases.items():
            with self.subTest(name=name):
                printer = Printer(readings)
                self.assertEqual(printer.run(), expected)
                self.assertTrue(any("Do not home or probe" in message for message in printer.messages()))

    def test_bad_readout_stops_the_check_and_the_next_check_starts_cleanly(self):
        # QIDI's handler raises IndexError when the MCU returns an empty reading.
        for reading in ("", "// unrelated output", [1, 2], 1 << 23, CommandError("sensor timeout"),
                        IndexError("index out of range")):
            with self.subTest(reading=reading):
                printer = Printer([reading] * 3)
                with self.assertLogs(level="WARNING"):
                    self.assertEqual(printer.run(), "INCONCLUSIVE")
                self.assertEqual(len(printer.queries), 3)
                self.assertFalse(printer.check.active)
                if reading == "// unrelated output":
                    self.assertIn(reading, printer.messages())
                printer.readings = iter(trace())
                self.assertEqual(printer.run(), "RESPONSE_DETECTED")

    def test_transient_readout_failure_is_retried(self):
        printer = Printer([IndexError("index out of range")] + trace())
        with self.assertLogs(level="WARNING"):
            self.assertEqual(printer.run(), "RESPONSE_DETECTED")
        self.assertEqual(len(printer.queries), 37)

    def test_unsafe_or_unconfirmed_start_is_refused_without_querying(self):
        cases = [("print_stats", "state", state) for state in ("printing", "paused", "unknown")]
        cases += [("pause_resume", "is_paused", True), ("virtual_sdcard", "is_active", True),
                  ("idle_timeout", "state", "Printing")]
        cases += [(heater, "target", 1) for heater in ("extruder", "heater_bed", "heater_generic chamber")]
        cases += [(heater, "temperature", value) for heater in ("extruder", "heater_bed") for value in (40, float("nan"))]
        for obj, key, value in cases:
            with self.subTest(obj=obj, key=key, value=value):
                printer = Printer(trace())
                printer.objects[obj][key] = value
                with self.assertRaises(CommandError):
                    printer.run()
                self.assertEqual(printer.queries, [])
        for confirm in (None, 0, 2):
            with self.subTest(confirm=confirm):
                printer = Printer(trace(), confirm=confirm)
                with self.assertRaises(CommandError):
                    printer.run()
                self.assertEqual(printer.queries, [])
        printer = Printer(trace())
        printer.gcode.get_status = lambda eventtime: {"commands": {}}
        with self.assertRaises(CommandError):
            printer.run()
        self.assertEqual(printer.queries, [])

    def test_changed_safety_state_aborts_without_altering_the_printer(self):
        for obj, key, value, change_at in (("print_stats", "state", "printing", 4),
                                           ("extruder", "target", 200, 21), ("extruder", "temperature", 40, 30)):
            with self.subTest(obj=obj, key=key):
                printer = Printer(trace())

                def change_state():
                    if printer.time >= change_at:
                        printer.objects[obj][key] = value

                printer.on_pause = change_state
                self.assertEqual(printer.run(), "INCONCLUSIVE")
                self.assertLess(len(printer.queries), 36)
                self.assertEqual(printer.objects[obj][key], value)
                self.assertFalse(printer.check.active)

    def test_reentrant_request_cannot_replace_the_active_measurements(self):
        printer = Printer(trace())

        def reenter():
            with self.assertRaises(CommandError):
                printer.run()

        printer.on_query = reenter
        self.assertEqual(printer.run(), "RESPONSE_DETECTED")

