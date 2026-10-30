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

import ast
import configparser
import copy
import logging
import os
import re

NAME = re.compile(r"[a-z0-9_]+\Z")


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
        gcode = self.printer.lookup_object("gcode")
        gcode.register_command("SAVE_VARIABLE", None)
        gcode.register_command(
            "SAVE_VARIABLE", self.cmd_SAVE_VARIABLE,
            desc=getattr(self.save_vars, "cmd_SAVE_VARIABLE_help", None))
        # Modules that call the handler directly, such as box feed motion.
        self.save_vars.cmd_SAVE_VARIABLE = self.cmd_SAVE_VARIABLE

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
        path = os.path.realpath(save_vars.filename)
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
            msg = "Unable to save variable"
            logging.exception(msg)
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise gcmd.error(msg)
        # New objects, as QIDI's reload makes, so status updates see the change.
        save_vars.allVariables = variables
        if name in getattr(save_vars, "default_values", {}):
            setattr(save_vars, name, value)


def load_config(config):
    return SaveVariablesFast(config)
