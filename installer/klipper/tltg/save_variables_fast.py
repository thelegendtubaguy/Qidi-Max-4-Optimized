# Faster SAVE_VARIABLE for QIDI Max 4 Optimized.
#
# QIDI's SAVE_VARIABLE rewrites saved_variables.cfg from the values it holds in
# memory, then reads and parses the whole file back. That takes about 40 ms on
# Klipper's main thread for every variable, even when the value is unchanged,
# and print start and end save several variables in a row.
#
# This handler writes the same file and keeps the same values in memory, but it
# skips a save that would not change the stored value, takes the new value from
# memory instead of re-reading the file it just wrote, and replaces the file
# atomically so a power cut during the write cannot leave it half written.
# Variable names and values whose trip through the file is not exact, and any
# error, go to QIDI's handler unchanged.
#
# QIDI's Box modules save their own variables the same slow way, without
# SAVE_VARIABLE: box_extras and box2base through save_variable, box485 through
# _save_variable. Box print start saves about 20 variables, most of them
# unchanged, which held Klipper's main loop for 1.3 s, and every tool change
# saves about 8 more. Those methods get the same treatment. They write a name
# as given and let the file lowercase it, so a name whose lowercase form is
# already saved keeps the saved value and moves to where the name sorts; the
# faster save reproduces that, and falls back to QIDI's method for anything
# else it can't reproduce exactly.

import ast
import configparser
import copy
import logging
import math
import os
import re

NAME = re.compile(r"[a-z0-9_]+\Z")
VENDOR_NAME = re.compile(r"[A-Za-z0-9_]+\Z")
# Box modules: object name, save method, attribute holding save_variables.
VENDOR_SAVES = (("box_extras", "save_variable", "save_variables"),
                ("box2base", "save_variable", "save_variables"),
                ("box485", "_save_variable", "sv"))
_SCALARS = (str, int, bool, type(None))


def _exact(value):
    """Whether value comes back from its repr unchanged."""
    kind = type(value)
    if kind in _SCALARS:
        return True
    if kind is float:
        return math.isfinite(value)
    if kind is list or kind is tuple:
        return all(_exact(item) for item in value)
    if kind is dict:
        return all(type(key) in _SCALARS
                   or (type(key) is float and math.isfinite(key))
                   for key in value) \
            and all(_exact(item) for item in value.values())
    return False


def _write(path, varfile):
    """Replace the file at path with varfile, keeping its mode and group."""
    path = os.path.realpath(path)
    temp = os.path.join(os.path.dirname(path),
                        ".%s.tltg-tmp" % (os.path.basename(path),))
    try:
        with open(temp, "w") as f:
            varfile.write(f)
        try:
            st = os.stat(path)
        except FileNotFoundError:
            pass
        else:
            os.chmod(temp, st.st_mode & 0o7777)
            try:
                os.chown(temp, -1, st.st_gid)
            except OSError:
                pass
        os.replace(temp, path)
    except Exception:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


class SaveVariablesFast:
    def __init__(self, config):
        self.printer = config.get_printer()
        if not config.has_section("save_variables"):
            logging.info("tltg_save_variables_fast: [save_variables] is not"
                         " configured; SAVE_VARIABLE unchanged")
            return
        self.save_vars = self.printer.load_object(config, "save_variables")
        if not all(hasattr(self.save_vars, name) for name in
                   ("allVariables", "filename", "cmd_SAVE_VARIABLE")):
            logging.info("tltg_save_variables_fast: unrecognized save_variables"
                         " module; SAVE_VARIABLE unchanged")
            return
        self.original = self.save_vars.cmd_SAVE_VARIABLE
        self.gcode = gcode = self.printer.lookup_object("gcode")
        gcode.register_command("SAVE_VARIABLE", None)
        gcode.register_command(
            "SAVE_VARIABLE", self.cmd_SAVE_VARIABLE,
            desc=getattr(self.save_vars, "cmd_SAVE_VARIABLE_help", None))
        # Modules that call the handler directly, such as box feed motion.
        self.save_vars.cmd_SAVE_VARIABLE = self.cmd_SAVE_VARIABLE
        self.printer.register_event_handler("klippy:connect",
                                            self._patch_vendor_saves)

    def cmd_SAVE_VARIABLE(self, gcmd):
        save_vars = self.save_vars
        name = gcmd.get("VARIABLE")
        try:
            text = repr(ast.literal_eval(gcmd.get("VALUE")))
            value = ast.literal_eval(text)
        except Exception:
            return self.original(gcmd)
        # QIDI's file reader lowercases names and expands "%", and some values
        # do not parse back from their repr; leave those to QIDI's handler.
        if not NAME.match(name) or "%" in text or repr(value) != text:
            return self.original(gcmd)
        current = save_vars.allVariables
        if name in current and repr(current[name]) == text:
            return
        variables = copy.deepcopy(current)
        variables[name] = value
        # Sorted, the order QIDI's reload of the written file produces.
        variables = dict(sorted(variables.items()))
        try:
            varfile = configparser.ConfigParser()
            varfile.add_section("Variables")
            for key, val in variables.items():
                varfile.set("Variables", key, repr(val))
        except Exception:
            return self.original(gcmd)
        try:
            _write(save_vars.filename, varfile)
        except Exception:
            msg = "Unable to save variable"
            logging.exception(msg)
            raise gcmd.error(msg)
        # New objects, as QIDI's reload makes, so status updates see the change.
        save_vars.allVariables = variables
        if name in getattr(save_vars, "default_values", {}):
            setattr(save_vars, name, value)

    # ------------------------------------------------------------ Box saves
    def _patch_vendor_saves(self):
        for obj_name, method, attr in VENDOR_SAVES:
            owner = self.printer.lookup_object(obj_name, None)
            original = getattr(owner, method, None)
            if owner is None or not callable(original):
                continue
            if getattr(original, "_tltg_save_variables_fast", False):
                continue
            try:
                setattr(owner, method, self._vendor_save(owner, attr, original))
            except (AttributeError, TypeError):
                logging.info("tltg_save_variables_fast: %s.%s can't be "
                             "replaced; its saves are unchanged",
                             obj_name, method)

    def _vendor_save(self, owner, attr, original):
        def save_variable(varname, value):
            if getattr(owner, attr, None) is not self.save_vars \
                    or not self._save_vendor_value(varname, value):
                return original(varname, value)
        save_variable._tltg_save_variables_fast = True
        return save_variable

    def _save_vendor_value(self, varname, value):
        """Save as QIDI's Box modules do. Returns False to leave the save to
        QIDI's method."""
        save_vars = self.save_vars
        current = save_vars.allVariables
        if type(current) is not dict or type(varname) is not str \
                or not VENDOR_NAME.match(varname):
            return False
        variables = dict(current)
        variables[varname] = value
        try:
            items = sorted(variables.items())
        except TypeError:
            return False
        # QIDI writes the names in this order and the file lowercases them;
        # a later name equal to an earlier one once lowercased replaces its
        # value but keeps its place.
        saved = {}
        texts = {}
        for name, val in items:
            if type(name) is not str or not VENDOR_NAME.match(name) \
                    or not _exact(val):
                return False
            text = repr(val)
            if "%" in text:
                return False
            key = name.lower()
            saved[key] = val
            texts[key] = text
        key = varname.lower()
        if list(saved) == list(current) \
                and texts[key] == repr(current[key]) \
                and all(saved[k] is current[k] for k in saved if k != key):
            return True
        try:
            varfile = configparser.ConfigParser()
            varfile.add_section("Variables")
            for name, text in texts.items():
                varfile.set("Variables", name, text)
        except Exception:
            return False
        try:
            _write(save_vars.filename, varfile)
        except Exception:
            logging.exception("Unable to save variable")
            raise self.gcode.error("Unable to save variable %s as %s"
                                   % (varname, value))
        # New objects with the defaults refreshed, as QIDI's reload leaves.
        save_vars.allVariables = variables = copy.deepcopy(saved)
        for name, default in getattr(save_vars, "default_values", {}).items():
            setattr(save_vars, name, variables.get(name, default))
        return True


def load_config(config):
    return SaveVariablesFast(config)
