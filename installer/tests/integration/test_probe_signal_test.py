from __future__ import annotations

import importlib.util
from types import SimpleNamespace
import unittest

from installer.tests.helpers import REPO_ROOT


spec = importlib.util.spec_from_file_location(
    "probe_signal_test", REPO_ROOT / "installer/klipper/qidi/tltg_probe_test.py"
)
probe_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_test)


class CommandError(Exception):
    pass


class SignalHarness:
    def __init__(self, readings, confirm=1, sign_extend=False):
        self.readings = iter(readings)
        self.confirm = confirm
        self.sign_extend = sign_extend
        self.messages = []
        self.events = []
        self.commands = {}
        self.outputs = []
        self.calls = []
        self.time = 0.0
        self.on_pause = lambda: None
        self.on_query = lambda: None
        self.objects = {
            "print_stats": {"state": "standby"},
            "pause_resume": {"is_paused": False},
            "virtual_sdcard": {"is_active": False},
            "idle_timeout": {"state": "Ready"},
            "heaters": {"available_heaters": ["extruder", "heater_bed", "heater_generic chamber", "heater_generic heater_box1"]},
            "extruder": {"temperature": 25.0, "target": 0},
            "heater_bed": {"temperature": 25.0, "target": 0},
            "heater_generic chamber": {"target": 0},
            "heater_generic heater_box1": {"target": 0},
        }
        self.gcode = SimpleNamespace(
            register_command=lambda name, handler, **kw: self.commands.update({name: handler}),
            register_output_handler=self.outputs.append,
            get_status=lambda now: {"commands": {"WEIGHTING_DEBUG_QUERY": {}, **self.commands}},
            run_script_from_command=self.query,
        )
        reactor = SimpleNamespace(monotonic=lambda: self.time, pause=self.pause)
        printer = SimpleNamespace(
            lookup_object=self.lookup, get_reactor=lambda: reactor, command_error=CommandError
        )
        self.helper = probe_test.load_config(SimpleNamespace(get_printer=lambda: printer))
        self.gcmd = SimpleNamespace(
            get_int=lambda name, default: default if self.confirm is None else self.confirm,
            error=CommandError, respond_info=self.respond,
        )

    def respond(self, message):
        self.messages.append(message)
        self.events.append((self.time, "message", message))

    def lookup(self, name):
        if name == "gcode":
            return self.gcode
        return SimpleNamespace(get_status=lambda now: self.objects[name])

    def pause(self, until):
        self.time = until
        self.on_pause()

    def query(self, script):
        self.calls.append(script)
        self.events.append((self.time, "reading", script))
        if script != "WEIGHTING_DEBUG_QUERY":
            raise AssertionError("Unexpected motion, heating, or calibration command: " + script)
        self.on_query()
        value = next(self.readings)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, int):
            value = "// 传感器数据(%s): %d / %d / %.6f(mV)" % (
                "-" if value < 0 else "+", value % (1 << (32 if self.sign_extend else 24)), value,
                value * 2.5 / 128 / ((1 << 23) - 1) * 1000,
            )
        for output in self.outputs:
            output(value)

    def run(self):
        self.commands["_TLTG_TEST_PROBE"](self.gcmd)
        return self.helper.get_status(self.time)


def trace(base=1000, delta=1000, recovery=0):
    return [base + n % 3 - 1 for n in range(12)] + [base + delta + n % 3 - 1 for n in range(12)] + [base + recovery + n % 3 - 1 for n in range(12)]


class ProbeSignalTestTests(unittest.TestCase):
    def test_complete_guided_test_detects_response_in_either_direction(self):
        for delta, sign_extend in ((1000, False), (-1000, False), (-1000, True)):
            with self.subTest(delta=delta, sign_extend=sign_extend):
                harness = SignalHarness(trace(base=-100, delta=delta), sign_extend=sign_extend)
                status = harness.run()
                self.assertEqual(status["result"], "RESPONSE_DETECTED")
                self.assertFalse(status["active"])
                self.assertEqual(len(harness.calls), 36)
                starts = [next(i for i, event in enumerate(harness.events)
                               if event[1] == "message" and event[2].startswith(prefix))
                          for prefix in ("Will measure", "Next you", "Stop pressing")]
                for phase, start in enumerate(starts):
                    end = starts[phase + 1] if phase < 2 else len(harness.events)
                    events = harness.events[start:end]
                    reminders = [event for event in events if event[1] == "message" and event[2] in ("DO NOT TOUCH", "GET READY TO PRESS")]
                    cue = "PRESS" if phase == 1 else "Measuring..."
                    cues = [i for i, event in enumerate(events) if event[1:] == ("message", cue)]
                    self.assertEqual(len(reminders), 3)
                    self.assertEqual(len(cues), 3)
                    self.assertGreaterEqual(events[cues[0]][0] - reminders[-1][0], 5)
                    self.assertFalse(any(event[1] == "reading" for event in events[:cues[0]]))
                    for first, last in zip(cues, cues[1:] + [len(events)]):
                        self.assertTrue(any(event[1] == "reading" for event in events[first:last]))
                self.assertTrue(any("NOT the MCU homing-trigger path" in message for message in harness.messages))

    def test_frozen_noisy_transient_saturated_and_unreleased_signals_never_pass(self):
        cases = {
            "frozen": [1000] * 36,
            "noise": [1000 + (100 if n % 2 else -100) for n in range(12)] + [1050] * 12 + [1000] * 12,
            "spike": [1000] * 12 + [1000] * 11 + [100000] + [1000] * 12,
            "intermittent": [1000] * 12 + [2000] * 9 + [1000] * 3 + [1000] * 12,
            "unreleased": trace(recovery=1000),
            "minimum_change_without_release": [0] * 12 + [64] * 24,
            "unstable_release": [0] * 12 + [1000] * 12 + [0] * 10 + [5000] * 2,
            "saturated": trace(base=(1 << 23) - 1000, delta=-10000),
        }
        for name, readings in cases.items():
            with self.subTest(name=name):
                harness = SignalHarness(readings)
                expected = "INCONCLUSIVE" if name in ("frozen", "noise") else "NO_RELIABLE_RESPONSE"
                self.assertEqual(harness.run()["result"], expected)
                self.assertTrue(any("Do not home or probe" in message for message in harness.messages))

    def test_bad_missing_or_ambiguous_readouts_fail_and_next_test_starts_cleanly(self):
        for reading in ("", "// unrelated output", "// 传感器数据(+): 1 / 2 / 0.001(mV)",
                        "// 传感器数据(+): 1 / 1 / nan(mV)",
                        "// 传感器数据(+): 1 / 1 / 0.001(mV)\n// 传感器数据(+): 2 / 2 / 0.002(mV)",
                        CommandError("sensor timeout")):
            with self.subTest(reading=reading):
                harness = SignalHarness([reading])
                self.assertEqual(harness.run()["result"], "INCONCLUSIVE")
                self.assertEqual(len(harness.calls), 1)
                self.assertFalse(harness.helper.active)
                harness.readings = iter(trace())
                self.assertEqual(harness.run()["result"], "RESPONSE_DETECTED")

    def test_unsafe_or_unconfirmed_start_is_refused_without_querying(self):
        cases = [("print_stats", "state", state) for state in ("printing", "paused", "unknown")]
        cases += [("pause_resume", "is_paused", True), ("virtual_sdcard", "is_active", True),
                  ("idle_timeout", "state", "Printing")]
        cases += [(heater, "target", 1) for heater in ("extruder", "heater_bed", "heater_generic chamber", "heater_generic heater_box1")]
        cases += [(heater, "temperature", value) for heater in ("extruder", "heater_bed") for value in (40, float("nan"))]
        for obj, key, value in cases:
            with self.subTest(obj=obj, key=key, value=value):
                harness = SignalHarness(trace())
                harness.objects[obj][key] = value
                with self.assertRaises(CommandError):
                    harness.run()
                self.assertEqual(harness.calls, [])
        for confirm in (None, 0, 2):
            harness = SignalHarness(trace(), confirm=confirm)
            with self.assertRaises(CommandError):
                harness.run()
            self.assertEqual(harness.calls, [])
        harness = SignalHarness(trace())
        harness.gcode.get_status = lambda now: {"commands": {}}
        with self.assertRaises(CommandError):
            harness.run()
        self.assertEqual(harness.calls, [])

    def test_changed_safety_state_aborts_without_altering_the_printer(self):
        for obj, key, value, change_at in (("print_stats", "state", "printing", 4),
                                           ("extruder", "target", 200, 21), ("extruder", "temperature", 40, 30)):
            with self.subTest(obj=obj, key=key):
                harness = SignalHarness(trace())
                def change_state():
                    if harness.time >= change_at:
                        harness.objects[obj][key] = value
                harness.on_pause = change_state
                self.assertEqual(harness.run()["result"], "INCONCLUSIVE")
                self.assertLess(len(harness.calls), 36)
                self.assertEqual(harness.objects[obj][key], value)
                self.assertFalse(harness.helper.active)

    def test_reentrant_request_cannot_replace_the_active_measurements(self):
        harness = SignalHarness(trace())
        def reenter():
            with self.assertRaises(CommandError):
                harness.run()
        harness.on_query = reenter
        self.assertEqual(harness.run()["result"], "RESPONSE_DETECTED")
