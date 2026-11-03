from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
