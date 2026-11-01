# Background SAVE_CONFIG_QD for QIDI Max 4 Optimized.
#
# QIDI's SAVE_CONFIG_QD writes pending SAVE_CONFIG values to printer.cfg without
# restarting. It re-reads and parses the whole include tree twice and runs
# `sync` on Klipper's main thread, which stalls Klipper for over two seconds at
# print start, longer than a heater holding a steady power can go without a
# refresh before its MCU shuts down.
#
# TLTG_SAVE_CONFIG_QD writes the same file in a background thread. The backup is
# a hard link and the new file replaces printer.cfg atomically, so a restart
# during the save always finds a complete printer.cfg. SAVE_CONFIG,
# SAVE_CONFIG_QD, and a second TLTG_SAVE_CONFIG_QD wait for a save in progress
# so two writers never replace printer.cfg at once.

import logging
import os
import threading
import time

import configfile

WAIT_INTERVAL = 0.05

# Module-level so a save started before a Klipper RESTART is still waited for
# afterwards; RESTART keeps imported modules.
_save_thread = None


class BackgroundSaveConfig:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        for name in ("SAVE_CONFIG", "SAVE_CONFIG_QD"):
            original = self.gcode.register_command(name, None)
            if original is not None:
                self.gcode.register_command(
                    name, self._waiting(original),
                    desc="Overwrite config file (waits for a background save)")
        self.gcode.register_command(
            "TLTG_SAVE_CONFIG_QD", self.cmd_TLTG_SAVE_CONFIG_QD,
            desc="Save pending SAVE_CONFIG values without blocking Klipper")

    def _waiting(self, original):
        def handler(gcmd):
            self._wait_for_save()
            return original(gcmd)
        return handler

    def _wait_for_save(self):
        while _save_thread is not None and _save_thread.is_alive():
            self.reactor.pause(self.reactor.monotonic() + WAIT_INTERVAL)

    def cmd_TLTG_SAVE_CONFIG_QD(self, gcmd):
        global _save_thread
        self._wait_for_save()
        pconfig = self.printer.lookup_object("configfile")
        if not pconfig.autosave.fileconfig.sections():
            return
        autosave_text = pconfig._build_config_string(pconfig.autosave)
        cfgname = self.printer.get_start_args()["config_file"]
        _save_thread = threading.Thread(
            target=self._save, args=(pconfig, autosave_text, cfgname),
            name="tltg-save-config")
        _save_thread.start()

    def _save(self, pconfig, autosave_text, cfgname):
        start = time.monotonic()
        try:
            self._write(pconfig, autosave_text, cfgname)
        except Exception as e:
            logging.exception("TLTG_SAVE_CONFIG_QD failed")
            msg = "!! TLTG_SAVE_CONFIG_QD: unable to save config: %s" % (e,)
            self.reactor.register_async_callback(
                lambda eventtime: self.gcode.respond_raw(msg))
            return
        logging.info("TLTG_SAVE_CONFIG_QD: saved '%s' in %.3f s",
                     cfgname, time.monotonic() - start)

    def _write(self, pconfig, autosave_text, cfgname):
        # Same file contents and checks as QIDI's SAVE_CONFIG_QD, against a
        # snapshot of the pending values taken when the command ran.
        lines = [("#*# " + l).strip() for l in autosave_text.split("\n")]
        lines.insert(0, "\n" + configfile.AUTOSAVE_HEADER.rstrip())
        lines.append("")
        autosave_data = "\n".join(lines)
        data = pconfig._read_config_file(cfgname)
        regular_data, _old_autosave = pconfig._find_autosave_data(data)
        pconfig._build_config_wrapper(regular_data, cfgname)
        autosave = pconfig._build_config_wrapper(autosave_text, cfgname)
        regular_data = pconfig._strip_duplicates(regular_data, autosave)
        included = pconfig._build_config_wrapper(regular_data, cfgname)
        for section in autosave.fileconfig.sections():
            for option in autosave.fileconfig.options(section):
                if included.fileconfig.has_option(section, option):
                    raise configfile.error(
                        "SAVE_CONFIG section '%s' option '%s' conflicts with"
                        " included value" % (section, option))
        data = regular_data.rstrip() + autosave_data
        datestr = time.strftime("-%Y%m%d_%H%M%S")
        backup_name = cfgname + datestr
        temp_name = cfgname + "_autosave"
        if cfgname.endswith(".cfg"):
            backup_name = cfgname[:-4] + datestr + ".cfg"
            temp_name = cfgname[:-4] + "_autosave.cfg"
        logging.info("TLTG_SAVE_CONFIG_QD to '%s' (backup in '%s')",
                     cfgname, backup_name)
        with open(temp_name, "w") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if os.path.lexists(backup_name):
            os.unlink(backup_name)
        os.link(cfgname, backup_name)
        os.replace(temp_name, cfgname)
        dir_fd = os.open(os.path.dirname(os.path.abspath(cfgname)), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def load_config(config):
    return BackgroundSaveConfig(config)
