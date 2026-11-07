from __future__ import annotations

import collections
import copy
import importlib.util
import json
import sys
import types
import unittest

from installer.tests.helpers import REPO_ROOT


spec = importlib.util.spec_from_file_location(
    "tltg_klipper_health", REPO_ROOT / "installer/klipper/tltg/klipper_health.py"
)
klipper_health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(klipper_health)

NEVER = 9999999999999999.


class Timer:
    def __init__(self, callback, waketime):
        self.callback = callback
        self.waketime = waketime


class Reactor:
    """Klipper's timer list semantics."""

    NEVER = NEVER

    def __init__(self):
        self._timers = []

    def register_timer(self, callback, waketime=NEVER):
        timer = Timer(callback, waketime)
        self._timers = self._timers + [timer]
        return timer

    def unregister_timer(self, timer):
        timers = list(self._timers)
        timers.pop(timers.index(timer))
        self._timers = timers


class BoxExtras:
    """The shape of QIDI's load-cell checks: each check registers a new
    timer and keeps only the latest."""

    def __init__(self, reactor):
        self.reactor = reactor
        self.read_wei_timer = None
        self.init_probe_data_advance_timer = None
        self.heating_timers = {}

    def _read_wei_timer(self, eventtime):
        return NEVER

    def _init_probe_data_advance(self, eventtime):
        return NEVER

    def detect_filament_loaded(self):
        if self.read_wei_timer is not None:
            self.read_wei_timer.waketime = NEVER
        self.read_wei_timer = self.reactor.register_timer(self._read_wei_timer, 0.)
        self.read_wei_timer.waketime = NEVER

    def auto_detect_filament_advance(self, finish=True):
        self.init_probe_data_advance_timer = self.reactor.register_timer(
            self._init_probe_data_advance, 0.)
        if finish:
            self.init_probe_data_advance_timer.waketime = NEVER
            self.init_probe_data_advance_timer = None


class FinishedTimerCleanupTest(unittest.TestCase):
    def cleanup(self, reactor):
        health = object.__new__(klipper_health.KlipperHealth)
        health.reactor = reactor
        health.removed = 0
        return health.cleanup()

    def test_removes_only_timers_qidi_can_no_longer_run(self) -> None:
        reactor = Reactor()
        live = reactor.register_timer(lambda eventtime: eventtime + 1., 0.)
        stopped = reactor.register_timer(lambda eventtime: NEVER, NEVER)
        extras = BoxExtras(reactor)
        for _ in range(3):
            extras.auto_detect_filament_advance()
            extras.detect_filament_loaded()
            extras.detect_filament_loaded()
        held = extras.read_wei_timer
        # A baseline still sampling is live and held.
        extras.auto_detect_filament_advance(finish=False)
        sampling = extras.init_probe_data_advance_timer
        # A stopped timer QIDI keeps in a container stays too.
        extras.heating_timers["box1"] = reactor.register_timer(extras._read_wei_timer, NEVER)

        self.assertEqual(self.cleanup(reactor), 8)

        self.assertEqual(
            set(map(id, reactor._timers)),
            {id(live), id(stopped), id(held), id(sampling), id(extras.heating_timers["box1"])})
        self.assertEqual(self.cleanup(reactor), 0)

    def test_timer_count_stays_flat_across_loads(self) -> None:
        reactor = Reactor()
        extras = BoxExtras(reactor)
        counts = []
        for _ in range(50):
            extras.auto_detect_filament_advance()
            extras.detect_filament_loaded()
            extras.detect_filament_loaded()
            self.cleanup(reactor)
            counts.append(len(reactor._timers))
        self.assertEqual(set(counts), {1})


class BoxStatusCopyTest(unittest.TestCase):
    """QIDI's multi_color_controller deep-copies its flattened Box status on
    every get_status."""

    def controller(self):
        module = types.ModuleType("tltg_test_multi_color_controller")
        module.copy = copy
        source = (
            "class MultiColorController:\n"
            "    def __init__(self):\n"
            "        self.flat = {'loaded_slot': 'slot3', 'box_count': 2, 'temp': 29.5, 'ok': True,\n"
            "                     'retry_step': None, 'box0_color_rgb_str': ['#FF0000'],\n"
            "                     'nested': {'drying': {'end_time': 0.0}, 'slots': [(1, 2), [3]]}}\n"
            "        self.extra = {}\n"
            "    def get_status(self, eventtime=None):\n"
            "        return {'box': copy.deepcopy(self.flat), 'extra': copy.deepcopy(self.extra)}\n"
        )
        exec(source, module.__dict__)
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__)
        return module, module.MultiColorController()

    def test_status_is_the_same_independent_copy(self) -> None:
        module, controller = self.controller()
        stock = controller.get_status()

        self.assertTrue(klipper_health.lighten_status_copy(controller))
        self.assertTrue(klipper_health.lighten_status_copy(controller))
        status = controller.get_status()

        self.assertEqual(json.dumps(status, sort_keys=True), json.dumps(stock, sort_keys=True))
        self.assertEqual(type(status["box"]["nested"]["slots"][0]), tuple)
        Coord = collections.namedtuple("Coord", "x y z e")
        position = Coord(1., 2., 3., 0.)
        self.assertIs(klipper_health._deepcopy({"position": position})["position"], position)
        self.assertEqual(klipper_health._deepcopy({"p": Coord([1.], 2., 3., 0.)}),
                         copy.deepcopy({"p": Coord([1.], 2., 3., 0.)}))
        controller.flat["box0_color_rgb_str"][0] = "#00FF00"
        controller.flat["nested"]["drying"]["end_time"] = 5.0
        self.assertEqual(status["box"]["box0_color_rgb_str"], ["#FF0000"])
        self.assertEqual(status["box"]["nested"]["drying"]["end_time"], 0.0)
        self.assertIs(module.copy.copy, copy.copy)

    def test_other_values_keep_deepcopy(self) -> None:
        _module, controller = self.controller()
        klipper_health.lighten_status_copy(controller)
        shared = [1]
        controller.extra = {"a": shared, "b": shared, "slots": {1, 2}}

        extra = controller.get_status()["extra"]

        self.assertEqual(extra["slots"], {1, 2})
        self.assertIs(extra["a"], extra["b"])
        self.assertIsNot(extra["a"], shared)

    def test_module_without_copy_is_left_alone(self) -> None:
        module, controller = self.controller()
        module.copy = types.ModuleType("copy")

        self.assertFalse(klipper_health.lighten_status_copy(controller))
        self.assertIsNot(getattr(module.copy, "deepcopy", None), klipper_health._deepcopy)


class LoadCellProbeSyncFailureTest(unittest.TestCase):
    """QIDI's load-cell probe (extras/air) raises "WEIGHT sensor error" for
    any failed endstop sync, the timeout included."""

    def setUp(self) -> None:
        class MCU:
            def __init__(self, name, freq):
                self.name = name
                self.freq = freq

            def get_name(self):
                return self.name

            def seconds_to_clock(self, time):
                return int(time * self.freq)

        class MCU_trsync:
            """The shape of Klipper's MCU_trsync."""

            REASON_ENDSTOP_HIT = 1
            REASON_HOST_REQUEST = 2
            REASON_PAST_END_TIME = 3
            REASON_COMMS_TIMEOUT = 4

            def __init__(self, mcu):
                self.mcu = mcu
                self.reason = None

            def get_mcu(self):
                return self.mcu

            def start(self, print_time, report_offset, trigger_completion, expire_timeout):
                pass

            def _handle_trsync_state(self, params):
                pass

            def stop(self):
                return self.reason

        saved = (MCU_trsync.start, MCU_trsync._handle_trsync_state, MCU_trsync.stop)
        self.assertTrue(klipper_health._wrap_trsync(MCU_trsync))
        self.assertTrue(klipper_health._wrap_trsync(MCU_trsync))
        self.assertIsNot(MCU_trsync.stop, saved[2])
        self.thr = MCU_trsync(MCU("THR", 72000000))
        self.mcu = MCU_trsync(MCU("mcu", 168000000))
        trsyncs = [self.thr, self.mcu]

        class WeighEndstopWrapper:
            def __init__(self):
                self._dispatch = types.SimpleNamespace(_trsyncs=trsyncs)
                self.error = None

            def home_wait(self, home_end_time):
                for trsync in self._dispatch._trsyncs:
                    trsync.stop()
                if self.error:
                    raise RuntimeError(self.error)
                return home_end_time

        air = types.ModuleType("extras.air")
        air.WeighEndstopWrapper = WeighEndstopWrapper
        sys.modules["extras.air"] = air
        self.addCleanup(sys.modules.pop, "extras.air")

        health = object.__new__(klipper_health.KlipperHealth)
        health.printer = types.SimpleNamespace(lookup_object=lambda name, default=None: default)
        health.reactor = Reactor()
        health.reactor.monotonic = lambda: 20.
        health.samples = collections.deque([(10., 1., 0.002), (15., 2.5, 0.040)])
        self.messages = []
        health.gcode = types.SimpleNamespace(respond_info=self.messages.append)
        klipper_health._current[0] = health
        self.addCleanup(klipper_health._current.__setitem__, 0, None)
        health._connect()
        self.endstop = WeighEndstopWrapper()

    @staticmethod
    def report(trsync, receive_time, clock, can_trigger=1, reason=0):
        trsync._handle_trsync_state({
            "#receive_time": receive_time, "clock": clock & 0xffffffff,
            "can_trigger": can_trigger, "trigger_reason": reason})

    def test_sync_failure_reports_context_and_keeps_the_error(self) -> None:
        self.assertEqual(self.endstop.home_wait(3.), 3.)
        self.endstop.error = "WEIGHT sensor error"

        with self.assertRaisesRegex(RuntimeError, "^WEIGHT sensor error$"):
            self.endstop.home_wait(3.)

        self.assertEqual(len(self.messages), 1)
        self.assertIn('"WEIGHT sensor error"', self.messages[0])
        self.assertIn("on THR and mcu", self.messages[0])
        self.assertIn("30% busy", self.messages[0])
        self.assertIn("40 ms late", self.messages[0])

    def test_sync_failure_names_the_board_that_timed_out_and_report_gaps(self) -> None:
        # THR sends one report 20 ms after the last, across its 32-bit clock
        # wrap, and its next reaches Klipper 52 ms after that one; the
        # mainboard's sync times out meanwhile.
        for trsync in (self.thr, self.mcu):
            trsync.start(100., 0., None, 0.050)
        thr_clock = 2**32 - 2 * 1080000
        for sent_ms, receive_time in ((0, 5.000), (15, 5.015), (35, 5.035), (50, 5.087)):
            self.report(self.thr, receive_time, thr_clock + sent_ms * 72000)
        for i in range(5):
            self.report(self.mcu, 5.005 + i * 0.015, 900000000 + i * 2520000)
        self.report(self.mcu, 5.076, 900000000 + 5 * 2520000 - 1680000,
                    can_trigger=0, reason=4)
        self.report(self.thr, 5.088, 0, can_trigger=0, reason=2)
        self.mcu.reason, self.thr.reason = 4, 2
        self.endstop.error = "WEIGHT sensor error"

        with self.assertLogs(level="INFO") as logs, \
                self.assertRaisesRegex(RuntimeError, "^WEIGHT sensor error$"):
            self.endstop.home_wait(3.)

        message = self.messages[0]
        self.assertIn("The sync timed out on mcu (50 ms limit).", message)
        self.assertIn("THR sent them up to 20 ms apart and Klipper read them up to 52 ms apart", message)
        self.assertIn("mcu sent them up to 15 ms apart and Klipper read them up to 15 ms apart", message)
        detail = "\n".join(logs.output)
        self.assertIn("THR (5 reports, result 2)", detail)
        self.assertIn("reason=4", detail)

    def test_other_probe_errors_are_not_reported(self) -> None:
        self.endstop.error = "Probe triggered prior to movement"

        with self.assertRaises(RuntimeError):
            self.endstop.home_wait(3.)

        self.assertEqual(self.messages, [])


class LateCommandTest(unittest.TestCase):
    """Commands sent with their MCU clock already past, which QIDI's
    mainboard reports only as "Timer too close"."""

    FREQ = 168000000

    def setUp(self) -> None:
        test = self
        self.now = [100.]
        self.sent = []

        class CommandWrapper:
            def __init__(self, msgformat):
                self.msgformat = msgformat

            def send(self, data=(), minclock=0, reqclock=0):
                test.sent.append((self.msgformat.split()[0], list(data), minclock))

        class MCU:
            """The shape of Klipper's MCU."""

            def __init__(self):
                reactor = types.SimpleNamespace(monotonic=lambda: test.now[0])
                self._clocksync = types.SimpleNamespace(
                    get_clock=lambda eventtime: int(eventtime * test.FREQ))
                self.get_printer = lambda: types.SimpleNamespace(get_reactor=lambda: reactor)

            def get_name(self):
                return "mcu"

            def seconds_to_clock(self, time):
                return int(time * test.FREQ)

            def lookup_command(self, msgformat, cq=None):
                return CommandWrapper(msgformat)

            def lookup_query_command(self, msgformat, respformat, oid=None, cq=None, is_async=False):
                return CommandWrapper(msgformat)

        self.assertTrue(klipper_health._watch_late_commands(MCU))
        self.assertTrue(klipper_health._watch_late_commands(MCU))
        self.mcu = MCU()
        health = object.__new__(klipper_health.KlipperHealth)
        health.reactor = types.SimpleNamespace(monotonic=lambda: test.now[0])
        health.late_commands = {}
        klipper_health._current[0] = health
        self.addCleanup(klipper_health._current.__setitem__, 0, None)
        self.pin = self.mcu.lookup_command("queue_digital_out oid=%c clock=%u on_ticks=%u")

    def clock(self, seconds):
        return int(seconds * self.FREQ)

    def set_enable(self, clock, minclock=0):
        # A caller whose name the report should show.
        self.pin.send([3, clock, 1], minclock=minclock, reqclock=clock)

    def test_late_commands_name_the_command_and_caller(self) -> None:
        cases = (
            (self.clock(99.862), 0, "queue_digital_out on 'mcu' 138.0 ms late when sent"),
            # Past only in the MCU's 32-bit clock, as a truncated clock is.
            (self.clock(99.97) & 0xffffffff, 0, "30.0 ms late"),
            # Ahead of the MCU, but held behind the pin's change 40 ms later.
            (self.clock(100.02), self.clock(100.06), "40.0 ms late"),
            (self.clock(100.003), 0, "only 3.0 ms ahead"),
        )
        for clock, minclock, expected in cases:
            with self.subTest(expected=expected):
                klipper_health._current[0].late_commands.clear()
                with self.assertLogs(level="WARNING") as logs:
                    self.set_enable(clock, minclock)
                self.assertIn(expected, logs.output[0])
                self.assertIn("test_klipper_health.py", logs.output[0])
                self.assertIn(" set_enable < ", logs.output[0])
                self.assertEqual(self.sent[-1], ("queue_digital_out", [3, clock, 1], minclock))

    def test_commands_on_time_or_without_a_clock_are_not_reported(self) -> None:
        trsync = self.mcu.lookup_command(
            "trsync_start oid=%c report_clock=%u report_ticks=%u expire_reason=%c")
        stop = self.mcu.lookup_command(
            "endstop_home oid=%c clock=%u sample_ticks=%u sample_count=%c rest_ticks=%u "
            "pin_value=%c trsync_oid=%c trigger_reason=%c")
        plain = self.mcu.lookup_command("set_digital_out pin=%u value=%c")

        with self.assertNoLogs(level="WARNING"):
            self.set_enable(self.clock(100.02), self.clock(100.))
            trsync.send([1, self.clock(100.05), 1000, 4])
            stop.send([1, 0, 0, 0, 0, 0, 0, 0])
            plain.send([5, 1])

        self.assertEqual(len(self.sent), 4)

    def test_reports_are_rate_limited_and_count_the_rest(self) -> None:
        with self.assertLogs(level="WARNING") as logs:
            for step in range(5):
                self.now[0] = 100. + step
                self.set_enable(self.clock(self.now[0] - .1))
            self.now[0] = 110.5
            self.set_enable(self.clock(self.now[0] - .1))

        self.assertEqual(len(logs.output), 2)
        self.assertIn("(4 more since the last report)", logs.output[1])
        self.assertEqual(len(self.sent), 6)


if __name__ == "__main__":
    unittest.main()
