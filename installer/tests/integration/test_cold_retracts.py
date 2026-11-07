from __future__ import annotations

import importlib.util
import sys
import threading
import types
import unittest

from installer.tests.helpers import REPO_ROOT

spec = importlib.util.spec_from_file_location(
    "tltg_cold_cut", REPO_ROOT / "installer/klipper/tltg/cold_cut.py"
)
cold_cut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cold_cut)

# Klipper's greenlet, which only names the running command here.
sys.modules.setdefault("greenlet", types.SimpleNamespace(getcurrent=lambda: None))
spec = importlib.util.spec_from_file_location(
    "tltg_box_flow_recovery", REPO_ROOT / "installer/klipper/tltg/box_flow_recovery.py"
)
box_flow_recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(box_flow_recovery)

MIN_EXTRUDE_TEMP = 135.


class CommandError(Exception):
    pass


class Heater:
    """QIDI's heater: can_extrude follows every temperature reading."""

    def __init__(self, temp):
        self.lock = threading.Lock()
        self.min_extrude_temp = MIN_EXTRUDE_TEMP
        self.smoothed_temp = temp
        self.can_extrude = temp >= MIN_EXTRUDE_TEMP

    def temperature_callback(self):
        with self.lock:
            self.can_extrude = self.smoothed_temp >= self.min_extrude_temp


class Extruder:
    """QIDI's extruder check, which refuses retracts too."""

    def __init__(self, heater):
        self.heater = heater

    def get_heater(self):
        return self.heater

    def check_move(self, move):
        if not self.heater.can_extrude:
            raise CommandError("Extrude below minimum temp")


class Printer:
    def __init__(self, temp, print_state="standby", task=None, cut_error=None):
        self.heater = Heater(temp)
        self.extruder = Extruder(self.heater)
        self.command_error = CommandError
        self.scripts = []
        self.moves = []
        self.cut_error = cut_error
        printer = self
        toolhead = types.SimpleNamespace(
            get_extruder=lambda: self.extruder,
            get_status=lambda e: {"max_accel": 20000.},
        )
        statuses = {
            "toolhead": toolhead,
            "print_stats": types.SimpleNamespace(get_status=lambda e: {"state": print_state}),
            "multi_color_controller": types.SimpleNamespace(
                get_status=lambda e: {"task": task or {"flow_id": None, "current_queue": [],
                                                       "current_step": None, "is_paused": False}}),
        }

        class GCode:
            def register_command(self, name, handler, desc=None):
                printer.handler = handler

            def run_script_from_command(self, script):
                printer.scripts.append(script)
                if script == cold_cut.CUT_MACRO:
                    printer.heater.temperature_callback()
                    printer.move(-4.)
                    if printer.cut_error:
                        raise CommandError(printer.cut_error)

        self.objects = dict(statuses, gcode=GCode())

    def move(self, e):
        self.extruder.check_move(types.SimpleNamespace(axes_d=[0., 0., 0., e]))
        self.moves.append(e)

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def get_reactor(self):
        return types.SimpleNamespace(monotonic=lambda: 0.)

    def is_shutdown(self):
        return False


class GCmd:
    def __init__(self):
        self.messages = []

    def error(self, message):
        return CommandError(message)

    def respond_info(self, message):
        self.messages.append(message)


def make(printer):
    config = types.SimpleNamespace(get_printer=lambda: printer)
    return cold_cut.ColdCut(config)


class ColdRetractsTest(unittest.TestCase):
    """Only retracts get past the cold-extrusion check, and only while held."""

    def test_cold_nozzle_retracts_but_does_not_extrude_while_held(self) -> None:
        printer = Printer(25.)
        module = make(printer)
        with self.assertRaises(CommandError):
            printer.move(-4.)
        with module.cold_retracts():
            printer.heater.temperature_callback()
            printer.move(-4.)
            printer.move(-120.)
            with self.assertRaises(CommandError):
                printer.move(5.)
        with self.assertRaises(CommandError):
            printer.move(-4.)
        printer.heater.temperature_callback()
        self.assertEqual(printer.moves, [-4., -120.])
        self.assertEqual(printer.heater.min_extrude_temp, MIN_EXTRUDE_TEMP)
        self.assertFalse(printer.heater.can_extrude)
        self.assertNotIn("check_move", vars(printer.extruder))

    def test_hot_nozzle_still_extrudes_while_held(self) -> None:
        printer = Printer(200.)
        with make(printer).cold_retracts():
            printer.move(5.)
        printer.move(5.)
        self.assertEqual(printer.moves, [5., 5.])
        self.assertTrue(printer.heater.can_extrude)

    def test_error_inside_restores_the_check(self) -> None:
        printer = Printer(25.)
        with self.assertRaises(RuntimeError):
            with make(printer).cold_retracts():
                raise RuntimeError("step failed")
        with self.assertRaises(CommandError):
            printer.move(-4.)


class ColdCutCommandTest(unittest.TestCase):
    def run_cut(self, printer):
        make(printer)
        gcmd = GCmd()
        printer.handler(gcmd)
        return gcmd

    def test_cuts_cold_after_homing_and_restores_state(self) -> None:
        printer = Printer(25.)
        gcmd = self.run_cut(printer)
        self.assertEqual(printer.scripts, [
            "SAVE_GCODE_STATE NAME=tltg_cut_filament",
            "G28 O X Y",
            "_OPTIMIZED_CUT_FILAMENT_MOTION",
            "SET_VELOCITY_LIMIT ACCEL=20000.000\nRESTORE_GCODE_STATE NAME=tltg_cut_filament",
        ])
        self.assertEqual(printer.moves, [-4.])
        self.assertEqual(gcmd.messages, ["Filament cut."])
        with self.assertRaises(CommandError):
            printer.move(-4.)

    def test_failed_cut_still_restores_state_and_the_check(self) -> None:
        printer = Printer(25., cut_error="Move out of range")
        with self.assertRaises(CommandError):
            self.run_cut(printer)
        self.assertEqual(printer.scripts[-1],
                         "SET_VELOCITY_LIMIT ACCEL=20000.000\nRESTORE_GCODE_STATE NAME=tltg_cut_filament")
        with self.assertRaises(CommandError):
            printer.move(-4.)

    def test_refused_during_a_print_or_box_flow(self) -> None:
        for kwargs in ({"print_state": "printing"}, {"print_state": "paused"},
                       {"task": {"flow_id": 3, "current_queue": ["BOX_UNLOAD"],
                                 "current_step": "BOX_UNLOAD", "is_paused": False}},
                       {"task": {"flow_id": 1, "current_queue": [],
                                 "current_step": "BOX_LOAD", "is_paused": True}}):
            with self.subTest(**kwargs):
                printer = Printer(25., **kwargs)
                with self.assertRaises(CommandError):
                    self.run_cut(printer)
                self.assertEqual((printer.scripts, printer.moves), ([], []))



class Dispatcher:
    """Klipper's G-code dispatch: registered handlers, G1 E moves, and the
    rest recorded."""

    def __init__(self, printer):
        self.printer = printer
        self.handlers = {}
        self.gcode_help = {}
        self.sent = []
        self.heated = []
        self.messages = []
        self.handlers["M109"] = lambda gcmd: self.heated.append(gcmd.line)

    def register_command(self, name, handler, desc=None):
        if handler is None:
            return self.handlers.pop(name, None)
        assert name not in self.handlers, name
        self.handlers[name] = handler
        if desc is not None:
            self.gcode_help[name] = desc

    def run_script_from_command(self, script):
        for line in script.split("\n"):
            line = line.strip()
            if not line:
                continue
            self.sent.append(line)
            command = line.split()[0]
            if command == "G1" and " E" in line:
                self.printer.move(float(line.split(" E")[1].split()[0]))
            elif command == "CUT_FILAMENT_1":
                self.printer.move(-4.)
            elif command in self.handlers:
                self.handlers[command](types.SimpleNamespace(line=line, get_commandline=lambda: line))

    def respond_info(self, message):
        self.messages.append(message)


class Task:
    def __init__(self, steps):
        self.queue = list(steps)
        self.current_step = None
        self.is_paused = False
        self.is_cancelled = False


class Manager:
    """QIDI's TaskQueueManager on firmware 01.01.07.01, as the harness ran it."""

    FLOW_MAP = {0: [], 3: ["BOX_HEAT", "BOX_CUT", "BOX_UNLOAD"], 4: ["BOX_EJECT"],
                5: ["BOX_HEAT", "BOX_CUT", "BOX_UNLOAD", "BOX_EJECT"],
                7: ["EXT_HEAT", "EXT_CUT", "EXT_UNLOAD"]}

    def __init__(self, gcode, unload_failures, unload_errors):
        self.gcode = gcode
        self.current_task = None
        self.current_flow_temp = None
        self.unload_failures = unload_failures
        self.unload_errors = unload_errors
        run = gcode.run_script_from_command
        self.method_map = {
            "BOX_HEAT": lambda: run("MOVE_TO_TRASH\nM109 S%s" % (self.current_flow_temp,)) or True,
            "BOX_CUT": lambda: run("CUT_FILAMENT_1") or True,
            "BOX_UNLOAD": self.unload,
            "BOX_EJECT": lambda: run("MOVE_TO_TRASH\n") or True,
            "EXT_HEAT": lambda: run("MOVE_TO_TRASH\nM109 S%s" % (self.current_flow_temp,)) or True,
            "EXT_CUT": lambda: run("CUT_FILAMENT_1") or True,
            "EXT_UNLOAD": lambda: run("M83\nG1 E-60 F300") or True,
        }

    def unload(self):
        run = self.gcode.run_script_from_command
        run("MOVE_TO_TRASH\n")
        run("M109 S%s" % (self.current_flow_temp if self.current_flow_temp is not None else 0,))
        for line in ("M83", "G1 E-30 F300", "M400", "G1 E-120 F600", "M400"):
            run(line)
        if self.unload_errors:
            self.unload_errors -= 1
            raise CommandError("Error during homing b_endstop: Communication timeout during homing")
        if self.unload_failures:
            self.unload_failures -= 1
            return False
        return True

    def start_flow(self, flow_id, on_complete):
        self.current_task = Task(self.FLOW_MAP[flow_id])
        self.on_complete = on_complete
        self._run()

    def _run(self):
        task = self.current_task
        while task.queue:
            task.current_step = task.queue[0]
            if not self.method_map[task.current_step]():
                task.is_paused = True
                self.gcode.respond_info("Step %s failed. Pausing flow." % (task.current_step,))
                return
            task.queue.pop(0)
        self.on_complete(task)
        self.current_task = None
        self.current_flow_temp = None

    def retry(self, can_next=0):
        if self.current_flow_temp is not None:
            self.gcode.run_script_from_command("M109 S%s\n" % (self.current_flow_temp,))
        self.current_task.is_paused = False
        self._run()

    def stop(self):
        self.current_task = None


class Controller:
    def __init__(self, gcode, flow, unload_failures=0, unload_errors=0):
        self.gcode = gcode
        self.flow = flow
        self.task_queue_manager = Manager(gcode, unload_failures, unload_errors)
        for name in ("UNLOAD_FILAMENT_CONTROL", "EJECT_FILAMENT_CONTROL"):
            gcode.register_command(name, self.cmd_FILAMENT_CONTROL)
        gcode.register_command("FLOW_STOP", lambda gcmd: self.task_queue_manager.stop())
        gcode.register_command("FLOW_RETRY", lambda gcmd: self.task_queue_manager.retry())
        gcode.register_command("T_MANAGER", lambda gcmd: None)

    def cmd_FILAMENT_CONTROL(self, gcmd):
        manager = self.task_queue_manager
        manager.current_flow_temp = 260
        manager.start_flow(self.flow, self.normal_complete_script)

    def normal_complete_script(self, task):
        self.gcode.run_script_from_command(
            "MOVE_TO_TRASH\nM104 S0\nSET_STEPPER_ENABLE STEPPER=extruder enable=0\n")
        if self.task_queue_manager.current_flow_temp is not None:
            self.gcode.run_script_from_command("G4 P5000\nWIPE_NOZZLE_DROP\n")


class FilamentCommand:
    def __init__(self, **params):
        self.params = params

    def get_int(self, name, default=None, minval=None, maxval=None):
        return int(self.params.get(name, default)) if self.params.get(name, default) is not None else None

    def get(self, name, default=None):
        return self.params.get(name, default)

    def error(self, message):
        return CommandError(message)

    def respond_info(self, message):
        pass


class ColdBoxFlowTest(unittest.TestCase):
    """COLD=1 unloads and ejects run QIDI's flow without heating, retracting cold."""

    def setup(self, flow=3, unload_failures=0, unload_errors=0, print_state="standby"):
        printer = Printer(25., print_state=print_state)
        gcode = printer.objects["gcode"] = Dispatcher(printer)
        controller = Controller(gcode, flow, unload_failures, unload_errors)
        printer.objects["multi_color_controller"] = controller
        config = types.SimpleNamespace(get_printer=lambda: printer)
        printer.objects["tltg_cold_cut"] = cold_cut.ColdCut(config)
        printer.objects["toolhead"].get_status = lambda e: {"max_accel": 20000.}
        printer.register_event_handler = lambda event, handler: None
        recovery = box_flow_recovery.BoxFlowRecovery(config)
        recovery._handle_ready()
        return printer, gcode, controller.task_queue_manager

    def unload(self, gcode, **params):
        gcode.handlers["UNLOAD_FILAMENT_CONTROL"](FilamentCommand(SLOT=2, **params))

    def test_cold_unload_cuts_and_pulls_back_without_heating(self) -> None:
        printer, gcode, manager = self.setup()
        self.unload(gcode, COLD=1)
        self.assertEqual(gcode.heated, [])
        self.assertEqual(printer.moves, [-4., -30., -120.])
        self.assertIsNone(manager.current_task)
        self.assertIn("M104 S0", gcode.sent)
        self.assertNotIn("WIPE_NOZZLE_DROP", gcode.sent)
        with self.assertRaises(CommandError):
            printer.move(-4.)
        gcode.run_script_from_command("M109 S240")
        self.assertEqual(gcode.heated, ["M109 S240"])

    def test_unload_without_cold_heats_as_before(self) -> None:
        printer, gcode, manager = self.setup()
        printer.heater.smoothed_temp = 260.
        printer.heater.temperature_callback()
        self.unload(gcode)
        self.assertEqual(gcode.heated, ["M109 S260", "M109 S260"])
        self.assertIn("WIPE_NOZZLE_DROP", gcode.sent)

    def test_retry_of_a_paused_cold_unload_stays_cold(self) -> None:
        for failure in ({"unload_failures": 1}, {"unload_errors": 1}):
            with self.subTest(**failure):
                printer, gcode, manager = self.setup(**failure)
                try:
                    self.unload(gcode, COLD=1)
                except CommandError:
                    pass
                self.assertTrue(manager.current_task.is_paused)
                with self.assertRaises(CommandError):
                    printer.move(-4.)
                gcode.handlers["FLOW_RETRY"](FilamentCommand())
                self.assertIsNone(manager.current_task)
                self.assertEqual(gcode.heated, [])
                self.assertEqual(printer.moves, [-4., -30., -120., -30., -120.])

    def test_flow_with_other_steps_heats_and_says_so(self) -> None:
        printer, gcode, manager = self.setup(flow=7)
        printer.heater.smoothed_temp = 260.
        printer.heater.temperature_callback()
        self.unload(gcode, COLD=1)
        self.assertEqual(gcode.heated, ["M109 S260"])
        self.assertTrue(any("heats the nozzle" in message for message in gcode.messages))

    def test_cold_refused_during_a_print(self) -> None:
        for state in ("printing", "paused"):
            with self.subTest(state=state):
                printer, gcode, manager = self.setup(print_state=state)
                with self.assertRaises(CommandError):
                    self.unload(gcode, COLD=1)
                self.assertEqual((gcode.sent, printer.moves), ([], []))


if __name__ == "__main__":
    unittest.main()
