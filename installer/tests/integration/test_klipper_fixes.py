from __future__ import annotations

import importlib.util
import sys
import types
import unittest

from installer.tests.helpers import REPO_ROOT


class SerialError(Exception):
    pass


class CommandError(Exception):
    pass


def _load():
    """Import tltg_klipper_fixes with stand-ins for the Klipper modules it
    patches; the tests attach the classes they need."""
    saved = {name: sys.modules.get(name)
             for name in ("mcu", "reactor", "serialhdl", "webhooks", "extras", "extras.heaters",
                          "extras.stepper_enable", "extras.tmc")}
    for name in ("mcu", "reactor", "serialhdl", "webhooks"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["serialhdl"].error = SerialError
    sys.modules["webhooks"].DEEP_COMPARISON_MODULES = ["multi_color_controller"]
    sys.modules["webhooks"].SUBSCRIPTION_REFRESH_TIME = 1.
    package = types.ModuleType("extras")
    package.__path__ = []
    sys.modules["extras"] = package
    for name in ("heaters", "stepper_enable", "tmc"):
        module = types.ModuleType("extras." + name)
        sys.modules["extras." + name] = module
        setattr(package, name, module)
    sys.modules["extras.heaters"].MAX_HEAT_TIME = 5.
    sys.modules["extras.stepper_enable"].ENABLE_DELAY_TIME = .3
    try:
        spec = importlib.util.spec_from_file_location(
            "extras.tltg_klipper_fixes", REPO_ROOT / "installer/klipper/tltg/klipper_fixes.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


klipper_fixes = _load()


class Completion:
    def __init__(self):
        self.result = "pending"

    def complete(self, result):
        self.result = result

    def wait(self):
        return None if self.result == "pending" else self.result


class GuardTest(unittest.TestCase):
    def test_only_the_expected_original_is_replaced(self) -> None:
        class Target:
            def method(self):
                return "original"

        def fixed(self):
            return "fixed"

        label = "MCU_trsync.start"
        saved = klipper_fixes.ORIGINALS[label]
        self.addCleanup(klipper_fixes.ORIGINALS.__setitem__, label, saved)

        self.assertFalse(klipper_fixes._replace(Target, "method", label, fixed))
        self.assertEqual(Target().method(), "original")

        klipper_fixes.ORIGINALS[label] = klipper_fixes.source_hash(Target.method)
        self.assertTrue(klipper_fixes._replace(Target, "method", label, fixed))
        self.assertTrue(klipper_fixes._replace(Target, "method", label, fixed))
        self.assertEqual(Target().method(), "fixed")


class LostMcuTest(unittest.TestCase):
    class Serial:
        def __init__(self):
            self.last_notify_id = 0
            self.pending_notifications = {}
            self.serialqueue = object()
            self.reactor = types.SimpleNamespace(completion=Completion)
            self.ffi_lib = types.SimpleNamespace(serialqueue_send=lambda *args: None)

        def _error(self, msg):
            raise SerialError(msg)

    def test_waits_fail_once_communication_is_lost(self) -> None:
        serial = self.Serial()
        waiting = Completion()
        serial.pending_notifications[1] = waiting

        klipper_fixes._abort_wait_acks(serial)

        self.assertIsNone(waiting.result)
        with self.assertRaisesRegex(SerialError, "No communication with MCU"):
            klipper_fixes._raw_send_wait_ack(serial, b"", 0, 0, None)

    def test_wait_failure_is_a_command_error(self) -> None:
        serial = self.Serial()
        klipper_fixes._abort_wait_acks(serial)
        wrapper = types.SimpleNamespace(
            _cmd=types.SimpleNamespace(encode=lambda data: b""),
            _serial=types.SimpleNamespace(raw_send_wait_ack=lambda *args: klipper_fixes._raw_send_wait_ack(serial, *args)),
            _cmd_queue=None)
        saved = klipper_fixes._COMMAND_ERROR[0]
        klipper_fixes._COMMAND_ERROR[0] = CommandError
        self.addCleanup(klipper_fixes._COMMAND_ERROR.__setitem__, 0, saved)

        with self.assertRaisesRegex(CommandError, "No communication with MCU"):
            klipper_fixes._send_wait_ack(wrapper)


class HeaterTest(unittest.TestCase):
    class Heater:
        def __init__(self):
            self.target_temp = 200.
            self.is_shutdown = False
            self.next_pwm_time = 0.
            self.last_pwm_value = 0.
            self.pwm_delay = .1
            self.sent = []
            self.mcu_pwm = types.SimpleNamespace(
                set_pwm=lambda time, value: self.sent.append(value),
                get_mcu=lambda: types.SimpleNamespace(estimated_print_time=lambda eventtime: eventtime))

    def test_output_stops_when_the_main_loop_stops(self) -> None:
        heater = self.Heater()
        heater._tltg_mainthread_time = 105.

        klipper_fixes._heater_set_pwm(heater, 100., 1.)
        klipper_fixes._heater_set_pwm(heater, 106., 1.)

        self.assertEqual(heater.sent, [1., 0.])

    def test_untracked_heater_keeps_qidi_behavior(self) -> None:
        heater = self.Heater()

        klipper_fixes._heater_set_pwm(heater, 1000., 1.)

        self.assertEqual(heater.sent, [1.])

    def test_temperature_reads_zero_only_after_seven_seconds(self) -> None:
        heater = self.Heater()
        class Lock:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False
        heater.lock = Lock()
        heater.smoothed_temp = 210.
        heater.last_temp_time = 100.

        self.assertEqual(klipper_fixes._heater_get_temp(heater, 106.)[0], 210.)
        self.assertEqual(klipper_fixes._heater_get_temp(heater, 107.5)[0], 0.)


class StepperEnableTest(unittest.TestCase):
    """QIDI enables a stepper 0.3 s before its first step, which must still
    be ahead of the MCU when the enable is sent."""

    FREQ = 1000000

    class Pin:
        """Klipper's MCU_digital_out as stepper_enable uses it."""

        def __init__(self, mcu):
            self.mcu = mcu
            self._last_clock = 0
            self.sent = []

        def get_mcu(self):
            return self.mcu

        def set_digital(self, print_time, value):
            self._last_clock = int(print_time * StepperEnableTest.FREQ)
            self.sent.append((print_time, value))

    class EnablePin:
        """QIDI's StepperEnablePin: a pin shared by several steppers, or none."""

        def __init__(self, mcu_enable, enable_count=0):
            self.mcu_enable = mcu_enable
            self.enable_count = enable_count

        def set_enable(self, print_time):
            if not self.enable_count:
                self.mcu_enable.set_digital(print_time, 1)
            self.enable_count += 1

        def set_disable(self, print_time):
            self.enable_count -= 1
            if not self.enable_count:
                self.mcu_enable.set_digital(print_time, 0)

    def setUp(self) -> None:
        now = self.now = [10.]
        reactor = types.SimpleNamespace(monotonic=lambda: now[0])
        self.mcu = types.SimpleNamespace(
            get_printer=lambda: types.SimpleNamespace(get_reactor=lambda: reactor),
            estimated_print_time=lambda eventtime: eventtime,
            clock_to_print_time=lambda clock: clock / self.FREQ)

    def tracking(self, enable):
        stepper = types.SimpleNamespace(get_mcu=lambda: self.mcu, get_name=lambda: "stepper_y")
        callbacks = []
        tracking = types.SimpleNamespace(stepper=stepper, enable=enable, is_enabled=False,
                                         callbacks=[lambda time, on: callbacks.append(time)])
        return tracking, callbacks

    def test_enable_is_never_scheduled_in_the_past(self) -> None:
        # (first step, pin's previous change, expected enable), with the MCU at 10 s.
        cases = (
            (11., None, .7),             # 0.3 s early is still ahead: QIDI's time
            (10.16, None, .02),          # first homing move after a disable: 20 ms ahead
            (10.3, 10.1, .12),           # after the disable still pending on the pin
            (10.01, None, .01),          # never after the step itself
        )
        for print_time, last_change, expected in cases:
            with self.subTest(print_time=print_time, last_change=last_change):
                pin = self.Pin(self.mcu)
                if last_change is not None:
                    pin.set_digital(last_change, 0)
                tracking, callbacks = self.tracking(self.EnablePin(pin))

                with self.assertLogs(level="INFO") as logs:
                    klipper_fixes._motor_enable(tracking, print_time)

                self.assertAlmostEqual(pin.sent[-1][0], 10. + expected)
                self.assertEqual(pin.sent[-1][1], 1)
                self.assertAlmostEqual(callbacks[0], pin.sent[-1][0])
                self.assertTrue(tracking.is_enabled)
                self.assertIn("ENABLE delay: stepper=stepper_y enable=%.6f move=%.6f"
                              % (10. + expected, print_time), logs.output[0])

    def test_steppers_without_their_own_pin_still_enable(self) -> None:
        # No enable pin, and a shared pin another stepper already enabled.
        pin = self.Pin(self.mcu)
        for enable in (self.EnablePin(None, 9999), self.EnablePin(pin, 1)):
            with self.subTest(enable=enable):
                tracking, callbacks = self.tracking(enable)

                with self.assertLogs(level="INFO"):
                    klipper_fixes._motor_enable(tracking, 10.16)

                self.assertAlmostEqual(callbacks[0], 10.02)
                self.assertTrue(tracking.is_enabled)
        self.assertEqual(pin.sent, [])


class TimerTest(unittest.TestCase):
    def test_running_timer_is_not_rescheduled(self) -> None:
        reactor = types.SimpleNamespace(_next_timer=50.)
        timer = types.SimpleNamespace(waketime=10., timer_is_running=True)

        klipper_fixes._update_timer(reactor, timer, 0.)
        self.assertEqual(timer.waketime, 10.)

        timer.timer_is_running = False
        klipper_fixes._update_timer(reactor, timer, 0.)
        self.assertEqual((timer.waketime, reactor._next_timer), (0., 0.))

    def test_scan_runs_due_timers_and_finds_the_next_wake(self) -> None:
        never = 1e99
        reactor = types.SimpleNamespace(NEVER=never, _next_timer=0., _g_dispatch=None)
        later = types.SimpleNamespace(waketime=20.)
        idle = types.SimpleNamespace(waketime=never)

        def run_due(eventtime):
            klipper_fixes._update_timer(reactor, idle, 15.)
            return 30.
        due = types.SimpleNamespace(waketime=5., callback=run_due)
        reactor._timers = [due, later, idle]

        klipper_fixes._check_timers(reactor, 10., False)

        self.assertEqual((due.waketime, idle.waketime, reactor._next_timer), (30., 15., 15.))


class StatusUpdateTest(unittest.TestCase):
    """Moonraker's once-a-second update carries only what changed."""

    class Helper:
        def __init__(self, objects):
            self.printer = types.SimpleNamespace(lookup_object=lambda name, default=None: objects.get(name, default))
            self.clients = {}
            self.pending_queries = []
            self.last_query = {}

        def _get_diff_recursive(self, now, last):
            # QIDI's nested comparison for multi_color_controller.
            if not isinstance(now, dict) or not isinstance(last, dict):
                return now if now != last else None
            diff = {}
            for k, v in now.items():
                if k not in last:
                    diff[k] = v
                else:
                    res = self._get_diff_recursive(v, last[k])
                    if res is not None:
                        diff[k] = res
            return diff if diff else None

    def test_updates_carry_only_changes(self) -> None:
        macro = {"run": False}
        state = {"sensor": {"temperature": 20.}, "box": {"slot0": "PLA", "temp": 28.7}}
        objects = {
            "gcode_macro M": types.SimpleNamespace(get_status=lambda e: macro),
            "temperature_sensor s": types.SimpleNamespace(get_status=lambda e: dict(state["sensor"])),
            "multi_color_controller": types.SimpleNamespace(
                get_status=lambda e: {"box": dict(state["box"]), "task": {}}),
        }
        helper = self.Helper(objects)
        sent = []
        class Connection:
            def is_closed(self):
                return False
        conn = Connection()
        helper.clients[conn] = (conn, {name: None for name in objects}, sent.append, {})

        klipper_fixes._do_query(helper, 1.)
        klipper_fixes._do_query(helper, 2.)
        state["sensor"]["temperature"] = 21.
        state["box"]["temp"] = 28.8
        klipper_fixes._do_query(helper, 3.)

        updates = [message["params"]["status"] for message in sent]
        self.assertEqual(updates, [
            {"gcode_macro M": {"run": False}, "temperature_sensor s": {"temperature": 20.},
             "multi_color_controller": {"box": {"slot0": "PLA", "temp": 28.7}, "task": {}}},
            {"temperature_sensor s": {"temperature": 21.},
             "multi_color_controller": {"box": {"temp": 28.8}}},
        ])


if __name__ == "__main__":
    unittest.main()
