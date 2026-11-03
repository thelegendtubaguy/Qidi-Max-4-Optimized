from __future__ import annotations

import ast
import configparser
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from installer.tests.helpers import REPO_ROOT


spec = importlib.util.spec_from_file_location(
    "tltg_save_variables_fast", REPO_ROOT / "installer/klipper/tltg/save_variables_fast.py"
)
save_variables_fast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(save_variables_fast)

INITIAL = (
    "[Variables]\n"
    "box_count = 2\n"
    "box_drying_roll_enable = 1\n"
    "enable_box = 1\n"
    "last_load_slot = 'slot3'\n"
    "retry_step = None\n"
    "runout_0 = 0\n"
    "slot3 = 2\n"
    "tltg_spoolman_spools = {'slot0': 1, 'slot1': 2}\n"
    "\n"
)


class CommandError(Exception):
    pass


class Gcode:
    error = CommandError


class SaveVariables:
    """QIDI's save_variables: loadVariables as shipped."""

    default_values = {"box_count": 0, "enable_box": 0}

    def __init__(self, filename):
        self.filename = filename
        self.loadVariables()

    def loadVariables(self):
        varfile = configparser.ConfigParser()
        varfile.read(self.filename)
        self.allVariables = {
            name: ast.literal_eval(val) for name, val in varfile.items("Variables")}
        for key, default in self.default_values.items():
            setattr(self, key, self.allVariables.get(key, default))


class BoxExtras:
    """QIDI's box_extras/box2base save_variable, as recovered from the
    compiled modules."""

    def __init__(self, save_variables):
        self.save_variables = save_variables
        self.gcode = Gcode()
        self.saves = 0

    def save_variable(self, varname, value):
        self.saves += 1
        sv = self.save_variables
        newvars = dict(sv.allVariables)
        newvars[varname] = value
        varfile = configparser.ConfigParser()
        varfile.add_section("Variables")
        for name, val in sorted(newvars.items()):
            varfile.set("Variables", name, repr(val))
        try:
            with open(sv.filename, "w") as f:
                varfile.write(f)
        except Exception:
            raise self.gcode.error("Unable to save variable %s as %s" % (varname, value))
        sv.loadVariables()


class Printer:
    def __init__(self, objects):
        self.objects = objects

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)


def state(save_vars):
    return (
        Path(save_vars.filename).read_text(encoding="utf-8"),
        [(name, type(value), repr(value)) for name, value in save_vars.allVariables.items()],
        {name: repr(getattr(save_vars, name)) for name in save_vars.default_values},
    )


class BoxSaveTest(unittest.TestCase):
    """QIDI's Box modules save variables without SAVE_VARIABLE; the faster
    save must leave the same file and values."""

    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [p.unlink() for p in root.iterdir()] and root.rmdir())
        self.root = root

    def printer(self, name):
        path = self.root / name
        path.write_text(INITIAL, encoding="utf-8")
        save_vars = SaveVariables(str(path))
        box = BoxExtras(save_vars)
        fast = object.__new__(save_variables_fast.SaveVariablesFast)
        fast.printer = Printer({"box_extras": box})
        fast.save_vars = save_vars
        fast.gcode = Gcode()
        return save_vars, box, fast

    def test_saves_match_qidi(self) -> None:
        qidi_vars, qidi_box, _ = self.printer("qidi.cfg")
        fast_vars, fast_box, fast = self.printer("fast.cfg")
        fast._patch_vendor_saves()
        fast._patch_vendor_saves()

        saves = [
            ("last_load_slot", "slot1"),
            ("last_load_slot", "slot1"),
            # QIDI writes the name as given; the file keeps the saved
            # lowercase value and moves it to where the name sorts.
            ("BOX_DRYING_ROLL_ENABLE", 0),
            ("BOX_DRYING_ROLL_ENABLE", 0),
            ("New_Key", 5),
            ("runout_0", 0),
            ("slot3", -2),
            ("box_count", 3),
            ("retry_step", "EXTRUDER_LOAD1_slot3"),
            ("diff_mv", 0.07),
            ("nested", {"a": [1, (2, 3)], 4: None}),
            ("quote", "it's \"q\"\nnext"),
        ]
        for varname, value in saves:
            with self.subTest(save=(varname, value)):
                qidi_box.save_variable(varname, value)
                fast_box.save_variable(varname, value)
                self.assertEqual(state(fast_vars), state(qidi_vars))
        self.assertEqual(fast_box.saves, 0)

    def test_unchanged_save_leaves_the_file_alone(self) -> None:
        save_vars, box, fast = self.printer("fast.cfg")
        fast._patch_vendor_saves()
        for unchanged in ((("runout_0", 0), ("enable_box", 1), ("retry_step", None)),
                          (("BOX_DRYING_ROLL_ENABLE", 0), ("BOX_DRYING_ROLL_ENABLE", 0))):
            box.save_variable(*unchanged[0])
            os.utime(save_vars.filename, ns=(0, 0))
            for varname, value in unchanged:
                box.save_variable(varname, value)
            self.assertEqual(os.stat(save_vars.filename).st_mtime_ns, 0)

    def test_values_the_file_cant_hold_exactly_go_to_qidi(self) -> None:
        for value in ("50%", {1, 2}, float("nan"), b"x"):
            with self.subTest(value=value):
                save_vars, box, fast = self.printer("fast.cfg")
                fast._patch_vendor_saves()
                try:
                    box.save_variable("odd", value)
                except Exception:
                    pass
                self.assertEqual(box.saves, 1)

    def test_other_save_variables_go_to_qidi(self) -> None:
        save_vars, box, fast = self.printer("fast.cfg")
        fast._patch_vendor_saves()
        box.save_variables = SaveVariables(save_vars.filename)

        box.save_variable("slot3", 1)

        self.assertEqual(box.saves, 1)


class SaveVariableCommandTest(unittest.TestCase):
    def test_matches_qidi_handler(self) -> None:
        root = Path(tempfile.mkdtemp())
        path = root / "saved_variables.cfg"
        path.write_text(INITIAL, encoding="utf-8")
        self.addCleanup(lambda: [p.unlink() for p in root.iterdir()] and root.rmdir())
        save_vars = SaveVariables(str(path))
        expected = Path(root / "expected.cfg")
        expected.write_text(INITIAL, encoding="utf-8")
        qidi_vars = SaveVariables(str(expected))
        fast = object.__new__(save_variables_fast.SaveVariablesFast)
        fast.save_vars = save_vars
        fast.original = None

        class Command:
            error = CommandError

            def __init__(self, params):
                self.params = params

            def get(self, name):
                return self.params[name]

        for name, value in (("last_load_slot", "'slot5'"), ("z_offset", "0.05"), ("enable_box", "1")):
            fast.cmd_SAVE_VARIABLE(Command({"VARIABLE": name, "VALUE": value}))
            BoxExtras(qidi_vars).save_variable(name, ast.literal_eval(value))
            self.assertEqual(state(save_vars), state(qidi_vars))


if __name__ == "__main__":
    unittest.main()
