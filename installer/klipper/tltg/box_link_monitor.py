# QIDI Box MCU link monitor for QIDI Max 4 Optimized.
#
# Records Box MCU link health to a dedicated file so a lost Box MCU can be
# attributed after the fact. The module is inert until the saved variable
# `tltg_box_link_monitor` exists and is truthy; while it is absent or false the
# module reads the variable once per sample and writes nothing.
#
# Output deliberately lives outside klippy.log so it survives log rotation.

import logging
import os
import subprocess
import time

ENABLE_VARIABLE = "tltg_box_link_monitor"
OUTPUT_NAME = "tltg_box_link.log"
ROTATED_NAME = "tltg_box_link.log.1"

# Lines that mark a link failure in klippy.log. The chelper serial reader
# reports the lost endpoint before Klipper raises a timeout, so the EOF line is
# the earliest host-visible symptom.
TRIGGER_PATTERNS = (
    "Got EOF when reading from device",
    "Timeout with MCU",
    "Lost communication with MCU",
    "shutdown:",
)

# Counters that stay put in healthy operation. Recorded baseline:
# bytes_retransmit=9, bytes_invalid=0, rto=0.025, send_seq == receive_seq,
# upcoming_bytes=0.
INTEGER_FIELDS = (
    "bytes_retransmit",
    "bytes_invalid",
    "send_seq",
    "receive_seq",
    "retransmit_seq",
    "ready_bytes",
    "upcoming_bytes",
)
FLOAT_FIELDS = ("rto", "srtt", "rttvar", "mcu_awake")
STATUS_FIELDS = INTEGER_FIELDS + FLOAT_FIELDS

# QIDI supports up to four Boxes; objects for absent Boxes are skipped.
MAX_BOXES = 4
CONTEXT_OBJECTS = tuple(
    item for box in range(1, MAX_BOXES + 1) for item in (
        ("heater_generic heater_box%d" % box,
         ("target", "temperature", "power")),
        ("temperature_sensor heater_temp_a_box%d" % box, ("temperature",)),
        ("temperature_sensor heater_temp_b_box%d" % box, ("temperature",)),
        ("temperature_sensor Box%d_MCU" % box, ("temperature",)),
    )
) + (
    ("temperature_sensor AP_Board_SOC", ("temperature",)),
    ("temperature_sensor Mainboard_MCU", ("temperature",)),
)

TRUE_WORDS = ("1", "true", "yes", "on", "enable", "enabled")


def _is_true(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in TRUE_WORDS
    return False


def _decode(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _format(values):
    parts = []
    for key in sorted(values):
        value = values[key]
        if value is not None:
            parts.append("%s=%s" % (key, value))
    return " ".join(parts) if parts else "-"


class BoxLinkMonitor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.sample_interval = config.getfloat(
            "sample_interval", 1.0, minval=0.25)
        self.heartbeat_interval = config.getfloat(
            "heartbeat_interval", 60.0, minval=0.0)
        self.max_log_bytes = config.getint(
            "max_log_bytes", 2 * 1024 * 1024, minval=64 * 1024)
        self.capture_dmesg = config.getboolean("capture_dmesg", True)
        self.keepalive_interval = config.getfloat(
            "keepalive_interval", 300.0, minval=0.0)
        self.path = os.path.join(self._log_dir(), OUTPUT_NAME)
        self._handle = None
        self._log_offset = 0
        self._log_identity = None
        self._variables_object = None
        self._enabled = False
        self._last_enabled = None
        self._last_heartbeat = 0.0
        self._last_keepalive = 0.0
        self._previous = {}
        self._mcus = {}
        self._reset_oid = {}
        self._reset_requested = set()
        self._serial_dumped = False
        self._connected = False
        # MCU objects exist before any other section loads, so object ids must
        # be reserved here to be included in allocate_oids.
        for name, mcu in self._discover_mcus().items():
            try:
                oid = mcu.create_oid()
            except Exception:
                continue
            self._reset_oid[name] = oid
        self.printer.register_event_handler("klippy:connect",
                                            self._handle_connect)
        self.printer.register_event_handler("klippy:disconnect",
                                            self._handle_disconnect)
        self.printer.register_event_handler("klippy:shutdown",
                                            self._handle_shutdown)
        self.reactor.register_timer(self._sample, self.reactor.NOW)

    # ---------------------------------------------------------------- helpers
    def _log_dir(self):
        args = self.printer.get_start_args()
        log_file = args.get("log_file")
        if log_file:
            return os.path.dirname(os.path.abspath(log_file))
        return os.getcwd()

    def _klippy_log_path(self):
        return self.printer.get_start_args().get("log_file")

    def _variables(self):
        if self._variables_object is None:
            self._variables_object = self.printer.lookup_object(
                "save_variables", None)
        if self._variables_object is None:
            return {}
        try:
            variables = self._variables_object.get_status(0.0).get("variables")
        except Exception:
            variables = None
        if isinstance(variables, dict):
            return variables
        return getattr(self._variables_object, "allVariables", {}) or {}

    def _open(self):
        if self._handle is not None:
            return
        try:
            self._rotate_if_needed()
            self._handle = open(self.path, "a", encoding="utf-8")
        except Exception:
            logging.exception("tltg_box_link_monitor: cannot open %s", self.path)

    def _rotate_if_needed(self):
        try:
            if os.path.getsize(self.path) < self.max_log_bytes:
                return
        except OSError:
            return
        try:
            os.replace(self.path, os.path.join(
                os.path.dirname(self.path), ROTATED_NAME))
        except OSError:
            pass

    def _close(self):
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None

    def _write(self, message, durable=False):
        self._open()
        if self._handle is None:
            return
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self._handle.write("%s %s\n" % (stamp, message))
            self._handle.flush()
            if durable:
                os.fsync(self._handle.fileno())
        except Exception:
            logging.exception("tltg_box_link_monitor: write failed")

    # ------------------------------------------------------------------ mcus
    def _discover_mcus(self):
        found = {}
        objects = getattr(self.printer, "objects", None) or {}
        for name in sorted(objects):
            if name == "mcu" or name.startswith("mcu "):
                mcu = self.printer.lookup_object(name, None)
                if mcu is not None:
                    found[name] = mcu
        return found

    def _mcu_objects(self):
        if not self._mcus:
            self._mcus = self._discover_mcus()
        return self._mcus

    def _label(self, name):
        return name.split(" ", 1)[1] if name.startswith("mcu ") else name

    def _stats(self, mcu):
        try:
            return mcu.get_status(0.0).get("last_stats") or {}
        except Exception:
            return {}

    def _request_reset_reason(self, name, mcu):
        if name in self._reset_requested or name not in self._reset_oid:
            return
        self._reset_requested.add(name)
        try:
            command = mcu.try_lookup_command("reset_reason_get oid=%c")
        except Exception:
            command = None
        if command is None:
            self._write("reset-reason %s: firmware has no reset_reason_get"
                        % self._label(name))
            return
        oid = self._reset_oid[name]
        label = self._label(name)
        # Each MCU numbers its object ids independently, so Boxes with the same
        # config get the same oid; the label must come from the MCU, not the oid.
        try:
            mcu.register_response(
                lambda params: self._handle_reset_reason(label, params),
                "reset_reason_return", oid)
            command.send([oid])
        except Exception as exc:
            self._write("reset-reason %s: query failed: %s"
                        % (self._label(name), exc))

    def _handle_reset_reason(self, label, params):
        try:
            self._write("reset-reason %s: %s"
                        % (label, _decode(params.get("reason", ""))),
                        durable=True)
        except Exception:
            logging.exception("tltg_box_link_monitor: reset reason handler")

    # --------------------------------------------------------------- capture
    def _context(self):
        parts = []
        try:
            state = self.printer.lookup_object("print_stats").get_status(0.0)
            parts.append("print=%s" % state.get("state"))
        except Exception:
            pass
        try:
            virtual_sd = self.printer.lookup_object("virtual_sdcard")
            parts.append("sd_progress=%.3f"
                         % virtual_sd.get_status(0.0).get("progress", 0.0))
        except Exception:
            pass
        for object_name, fields in CONTEXT_OBJECTS:
            try:
                status = self.printer.lookup_object(object_name).get_status(0.0)
            except Exception:
                continue
            label = object_name.split(" ", 1)[-1]
            for field in fields:
                if field in status:
                    parts.append("%s.%s=%s" % (label, field, status[field]))
        for name, mcu in self._mcu_objects().items():
            stats = self._stats(mcu)
            if stats:
                parts.append("%s.freq=%s/%s" % (self._label(name),
                                                 stats.get("freq"),
                                                 stats.get("adj")))
        return " ".join(parts)

    def _dump_box_serial(self):
        # Klipper writes an MCU's recent message history to klippy.log only when
        # that MCU reports a shutdown, which a lost Box never does. The history
        # holds the messages exchanged before the link failed, with host
        # monotonic times; the clock line aligns them with dmesg.
        if self._serial_dumped:
            return
        self._serial_dumped = True
        clocks = ["monotonic=%.6f" % time.monotonic()]
        if hasattr(time, "CLOCK_BOOTTIME"):
            clocks.append("boottime=%.6f"
                          % time.clock_gettime(time.CLOCK_BOOTTIME))
        self._write("serial-history clock %s" % " ".join(clocks))
        for name, mcu in self._mcu_objects().items():
            label = self._label(name)
            if not label.startswith("mcu_box"):
                continue
            try:
                history = mcu._serial.dump_debug()
            except Exception as exc:
                self._write("serial-history %s: dump failed: %s"
                            % (label, exc))
                continue
            for line in history.splitlines():
                self._write("serial-history %s: %s" % (label, line))
        self._write("serial-history end", durable=True)
        self._dmesg()

    def _dmesg(self):
        if not self.capture_dmesg:
            return
        try:
            result = subprocess.run(
                ["dmesg"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=3.0)
            lines = [line.strip()
                     for line in _decode(result.stdout).splitlines()
                     if "usb" in line.lower()]
        except Exception as exc:
            self._write("dmesg: capture failed: %s" % exc)
            return
        # A dying hub logs a burst of errors before the disconnect itself, and
        # the first of them marks when the link failed.
        for line in lines[-60:]:
            self._write("dmesg: %s" % line)
        self._write("dmesg: end", durable=True)

    def _read_klippy_log(self):
        path = self._klippy_log_path()
        if not path:
            return
        try:
            stat = os.stat(path)
        except OSError:
            return
        identity = (stat.st_dev, stat.st_ino)
        if identity != self._log_identity or stat.st_size < self._log_offset:
            self._log_identity = identity
            self._log_offset = max(0, stat.st_size - 65536)
        if stat.st_size == self._log_offset:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self._log_offset)
                chunk = handle.read(262144)
                self._log_offset = handle.tell()
        except OSError:
            return
        for line in chunk.splitlines():
            if not any(pattern in line for pattern in TRIGGER_PATTERNS):
                continue
            if "tltg_box_link" in line:
                continue
            self._write("klippy: %s" % line.strip(), durable=True)
            self._dump_box_serial()

    def _snapshot(self):
        for name, mcu in self._mcu_objects().items():
            stats = self._stats(mcu)
            if not stats:
                continue
            label = self._label(name)
            current = {key: stats.get(key) for key in STATUS_FIELDS}
            previous = self._previous.get(name)
            self._previous[name] = current
            if previous is None:
                self._write("mcu %s baseline %s" % (label, _format(current)))
                continue
            changed = {key: current[key] for key in current
                       if current[key] is not None
                       and previous.get(key) != current[key]}
            if changed:
                self._write("mcu %s changed %s" % (label, _format(changed)))

    # ---------------------------------------------------------------- events
    def _handle_connect(self):
        # MCU command dictionaries are loaded only once identification is
        # done, so the reset reason cannot be looked up before this event.
        self._connected = True
        self._serial_dumped = False
        if self._enabled:
            self._write("connected %s" % self._context())

    def _handle_disconnect(self):
        if self._enabled:
            self._write("final: klippy disconnect", durable=True)
            self._write("final: context %s" % self._context(), durable=True)
            self._dmesg()
        self._close()

    def _handle_shutdown(self):
        if not self._enabled:
            self._close()
            return
        self._write("final: klippy shutdown", durable=True)
        for name, mcu in self._mcu_objects().items():
            self._write("final: %s %s"
                        % (self._label(name), _format(self._stats(mcu))),
                        durable=True)
        self._write("final: context %s" % self._context(), durable=True)
        self._read_klippy_log()
        self._dmesg()
        self._close()

    # ---------------------------------------------------------------- sample
    def _sample(self, eventtime):
        try:
            enabled = _is_true(self._variables().get(ENABLE_VARIABLE, False))
            previous = self._last_enabled
            if enabled != previous:
                self._last_enabled = enabled
                self._enabled = enabled
                if enabled:
                    self._write("enabled via saved variable %s; output %s"
                                % (ENABLE_VARIABLE, self.path), durable=True)
                    self._write("context %s" % self._context())
                elif previous is not None:
                    self._write("disabled: saved variable %s absent or false"
                                % ENABLE_VARIABLE, durable=True)
                    self._close()
            if not enabled:
                return eventtime + self.sample_interval
            if self._connected:
                for name, mcu in self._mcu_objects().items():
                    self._request_reset_reason(name, mcu)
            self._snapshot()
            self._read_klippy_log()
            if (self.heartbeat_interval
                    and eventtime - self._last_heartbeat
                    >= self.heartbeat_interval):
                self._last_heartbeat = eventtime
                summary = []
                for name, mcu in self._mcu_objects().items():
                    stats = self._stats(mcu)
                    if stats:
                        summary.append("%s[%s]" % (
                            self._label(name),
                            _format({key: stats.get(key)
                                     for key in ("rto", "bytes_retransmit",
                                                 "send_seq", "receive_seq",
                                                 "upcoming_bytes")})))
                self._write("heartbeat %s" % " ".join(summary))
            if (self.keepalive_interval
                    and eventtime - self._last_keepalive
                    >= self.keepalive_interval):
                self._last_keepalive = eventtime
                self._write("context %s" % self._context())
        except Exception:
            logging.exception("tltg_box_link_monitor: sample failed")
        return eventtime + self.sample_interval


def load_config(config):
    return BoxLinkMonitor(config)
