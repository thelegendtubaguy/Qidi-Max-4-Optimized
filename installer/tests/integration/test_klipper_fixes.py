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
             for name in ("mcu", "reactor", "serialhdl", "extras", "extras.heaters", "extras.tmc")}
    for name in ("mcu", "reactor", "serialhdl"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["serialhdl"].error = SerialError
    package = types.ModuleType("extras")
    package.__path__ = []
    sys.modules["extras"] = package
    for name in ("heaters", "tmc"):
        module = types.ModuleType("extras." + name)
        sys.modules["extras." + name] = module
        setattr(package, name, module)
    sys.modules["extras.heaters"].MAX_HEAT_TIME = 5.
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


class TimerTest(unittest.TestCase):
    def test_running_timer_is_not_rescheduled(self) -> None:
        reactor = types.SimpleNamespace(_next_timer=50.)
        timer = types.SimpleNamespace(waketime=10., timer_is_running=True)

        klipper_fixes._update_timer(reactor, timer, 0.)
        self.assertEqual(timer.waketime, 10.)

        timer.timer_is_running = False
        klipper_fixes._update_timer(reactor, timer, 0.)
        self.assertEqual((timer.waketime, reactor._next_timer), (0., 0.))


if __name__ == "__main__":
    unittest.main()
