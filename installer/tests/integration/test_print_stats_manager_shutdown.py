from __future__ import annotations

import unittest

from installer.runtime.klipper_print_stats_manager import patch_print_stats_manager
from installer.tests.helpers import FIXTURES_ROOT


STOCK = (FIXTURES_ROOT / "klipper_print_stats_manager.py").read_text(encoding="utf-8")


class CommandError(Exception):
    pass


class Printer:
    """Klipper's command-error path: a refused command responds, fires gcode:command_error, then raises."""

    command_error = CommandError

    def __init__(self, *, shutdown):
        self.shutdown = shutdown
        self.tmc_fails = False
        self.handlers = {}
        self.commands = []

    def get_printer(self):
        return self

    def get_reactor(self):
        return None

    def lookup_object(self, name):
        return self

    def register_command(self, *args, **kwargs):
        pass

    def register_event_handler(self, event, callback):
        self.handlers.setdefault(event, []).append(callback)

    def send_event(self, event, *params):
        return [callback(*params) for callback in self.handlers.get(event, [])]

    def is_shutdown(self):
        return self.shutdown

    def respond_info(self, msg):
        pass

    def run_script_from_command(self, script):
        for line in script.split("\n"):
            self.commands.append(line)
            if self.shutdown or self.tmc_fails:
                self.send_event("gcode:command_error")
                raise CommandError("Printer is shutdown" if self.shutdown else "Unable to write tmc spi")


def manager(source, printer):
    namespace = {}
    exec(compile(source, "print_stats_manager.py", "exec"), namespace)
    status = namespace["load_config"](printer)
    status.set_main_status("printing")
    printer.commands.clear()
    return status


class PrintStatsManagerShutdownTests(unittest.TestCase):
    def test_stock_reset_loops_after_shutdown_while_printing(self):
        printer = Printer(shutdown=False)
        manager(STOCK, printer)
        printer.shutdown = True
        with self.assertRaises(RecursionError):
            printer.send_event("gcode:command_error")

    def test_patched_reset_keeps_shutdown_reason(self):
        printer = Printer(shutdown=False)
        status = manager(patch_print_stats_manager(STOCK), printer)
        printer.shutdown = True
        printer.send_event("gcode:command_error")
        self.assertEqual(printer.commands, [])
        self.assertEqual(status.get_main_status(), "printing")

    def test_patched_reset_stops_after_a_refused_tmc_restore(self):
        printer = Printer(shutdown=False)
        status = manager(patch_print_stats_manager(STOCK), printer)
        printer.tmc_fails = True
        with self.assertRaises(CommandError):
            printer.send_event("gcode:command_error")
        self.assertEqual(len(printer.commands), 1)
        printer.tmc_fails = False
        printer.send_event("gcode:command_error")
        self.assertEqual(status.get_main_status(), "ready")
        self.assertEqual(printer.commands[1:], [
            "SET_TMC_FIELD STEPPER=stepper_z FIELD=tpwmthrs VELOCITY=9999999999",
            "SET_TMC_FIELD STEPPER=stepper_z1 FIELD=tpwmthrs VELOCITY=9999999999",
        ])


if __name__ == "__main__":
    unittest.main()
